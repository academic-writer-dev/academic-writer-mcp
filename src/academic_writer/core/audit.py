"""Audit documentaire et analyse des INDICES de rédaction par IA.

Règles :
- le style seul ne permet jamais de conclure : conclusion « indéterminée » par défaut ;
- seules des déclarations techniques explicites (C2PA, IPTC, outil nommé dans les métadonnées ou les
  modifications suivies) orientent la conclusion, avec leurs explications légitimes possibles ;
- « rédaction entièrement humaine » n'est jamais conclu automatiquement (impossible à prouver) ;
- aucun pourcentage : confiance « non calibrée » tant qu'aucune évaluation sur corpus n'existe.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.ai_detection.stylometry import Indicator, StyleAnalysis, analyze_style
from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.models import new_id, utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.forensics.models import (
    AI_TOOL,
    CORRECTION_TOOL,
    TRANSLATION_TOOL,
    ForensicFinding,
    MetadataReport,
    ProvenanceReport,
)
from academic_writer.forensics.office import analyze_office
from academic_writer.forensics.provenance import scan_provenance
from academic_writer.security.files import inspect_file
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.audit")

Conclusion = Literal["humaine", "assistance_ia", "correction_ia", "traduction_ia", "generation_partielle", "indeterminee"]
CONCLUSION_LABELS = {
    "humaine": "Rédaction entièrement humaine",
    "assistance_ia": "Assistance rédactionnelle par IA (outil déclaré)",
    "correction_ia": "Correction par un outil automatique (outil déclaré)",
    "traduction_ia": "Traduction assistée par un outil automatique (outil déclaré)",
    "generation_partielle": "Génération partielle par IA déclarée dans la provenance",
    "indeterminee": "Indéterminée : éléments insuffisants pour conclure",
}
GENERAL_LIMITS = [
    "Les détecteurs de texte IA ne sont pas fiables : aucune conclusion ne peut reposer sur le seul style.",
    "Confiance NON CALIBRÉE : aucune évaluation sur un corpus annoté (faux positifs / faux négatifs) n'a été faite.",
    "Une métadonnée peut être absente, modifiée ou effacée ; son absence ne prouve rien.",
    "Ce rapport fournit des INDICES pour un examen humain contradictoire, jamais une preuve.",
]
RECOMMENDATIONS = [
    "Ne prendre aucune décision sur la base de ce seul rapport.",
    "S'entretenir avec l'auteur : démarche, brouillons, notes, versions successives.",
    "Vérifier les sources citées (existence, exactitude) et la cohérence des calculs.",
    "Comparer avec d'autres travaux du même auteur rédigés dans des conditions connues.",
    "Tenir compte de la nature du document (technique, procédural) qui rend le style naturellement régulier.",
]


class IntegrityReport(BaseModel):
    document_id: str
    sha256_ok: bool
    original_protected: bool
    findings: list[ForensicFinding]


class AIAssessment(BaseModel):
    audit_id: str
    document_id: str
    filename: str
    conclusion: Conclusion
    conclusion_label: str
    confidence: str = "non calibrée"
    basis: str = Field(description="Ce sur quoi repose la conclusion.")
    style: StyleAnalysis
    metadata: MetadataReport
    provenance: ProvenanceReport
    integrity: IntegrityReport
    recommendations: list[str]
    limits: list[str]
    report_path: str | None = None
    report_markdown: str | None = None


class AuditService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction

    # --- briques ----------------------------------------------------------------
    def _language(self, document_id: str, text: str) -> str:
        project = self.projects.get(self.documents.get(document_id).project_id)
        letters = [c for c in text if c.isalpha()]
        if letters and sum("Ѐ" <= c <= "ӿ" for c in letters) / len(letters) > 0.5:
            return "ru"
        return project.language.value if project.language.value != "ru" else "en"

    def writing_patterns(self, document_id: str) -> StyleAnalysis:
        result, _ = self.extraction.extract(document_id)
        segments: list[tuple[str, str]] = []
        label, buffer = "Début du document", []
        for block in result.blocks:
            if block.type == "heading":
                if buffer:
                    segments.append((label, "\n\n".join(buffer)))
                label, buffer = block.text, []
            elif block.type in ("paragraph", "list_item", "note", "caption"):
                buffer.append(block.text)
        if buffer:
            segments.append((label, "\n\n".join(buffer)))
        if len(segments) <= 1 and segments:
            paragraphs = segments[0][1].split("\n\n")
            segments = [(f"Partie {i // 6 + 1}", "\n\n".join(paragraphs[i: i + 6])) for i in range(0, len(paragraphs), 6)]
        text = "\n\n".join(t for _, t in segments)
        return analyze_style(segments, self._language(document_id, text))

    def metadata(self, document_id: str) -> MetadataReport:
        document = self.documents.get(document_id)
        path = self.documents.stored_file(document)
        result, _ = self.extraction.extract(document_id)
        words = sum(len(b.text.split()) for b in result.blocks)
        limits = ["Les métadonnées peuvent être absentes, modifiées ou effacées sans laisser de trace."]
        if document.extension in (".docx", ".pptx", ".xlsx"):
            props, sessions, tracked, comments, hidden, findings = analyze_office(path, words)
            return MetadataReport(document_id=document_id, format=document.extension.lstrip("."), properties=props,
                                  editing_sessions=sessions, tracked_changes=tracked, comments=comments,
                                  hidden_text=hidden, findings=findings, limits=limits)
        props = dict(result.metadata)
        findings: list[ForensicFinding] = []
        if document.extension == ".pdf":
            created, modified = _pdf_date(props.get("creationdate")), _pdf_date(props.get("moddate"))
            if created and modified and modified < created:
                findings.append(ForensicFinding(category="metadata", severity="moyen",
                                                observation="Date de modification antérieure à la création.",
                                                evidence=[props.get("creationdate", ""), props.get("moddate", "")],
                                                explanations=["horloge déréglée", "outil de conversion"]))
            producer = " ".join(filter(None, [props.get("producer"), props.get("creator")]))
            if producer:
                findings.append(ForensicFinding(category="metadata", severity="info",
                                                observation=f"PDF produit par : {producer}",
                                                explanations=["logiciel d'export (traitement de texte, LaTeX, navigateur)"]))
            limits.append("Un PDF ne conserve en général ni l'historique d'édition ni les modifications suivies.")
        else:
            limits.append("Un fichier texte ne contient aucune métadonnée exploitable.")
        scan = " ".join(props.values())
        for pattern, label in ((AI_TOOL, "assistant d'IA"), (CORRECTION_TOOL, "outil de correction"),
                               (TRANSLATION_TOOL, "outil de traduction")):
            names = sorted({m.group(0) for m in re.finditer(pattern, scan, re.IGNORECASE)})
            if names:
                findings.append(ForensicFinding(category="provenance", severity="fort" if label == "assistant d'IA" else "moyen",
                                                observation=f"Un {label} est nommé dans les propriétés du fichier.",
                                                evidence=names, explanations=["usage déclaré de l'outil"]))
        return MetadataReport(document_id=document_id, format=document.extension.lstrip("."), properties=props,
                              findings=findings, limits=limits)

    def provenance(self, document_id: str) -> ProvenanceReport:
        document = self.documents.get(document_id)
        path = self.documents.stored_file(document)
        meta = self.metadata(document_id)
        scan = " ".join([*meta.properties.values(), *(meta.tracked_changes.authors if meta.tracked_changes else {}),
                         *(c.author or "" for c in meta.comments)])
        present, declared, tools, findings = scan_provenance(path, scan)
        limits = ["Signature C2PA non vérifiée cryptographiquement (bibliothèque dédiée non installée).",
                  "La plupart des documents texte ne portent aucune donnée de provenance : l'absence ne prouve rien."]
        return ProvenanceReport(document_id=document_id, content_credentials=present, declared_ai_media=declared,
                                declared_tools=tools, findings=findings, limits=limits)

    def integrity(self, document_id: str) -> IntegrityReport:
        document = self.documents.get(document_id)
        state = self.documents.metadata(document_id)
        findings: list[ForensicFinding] = []
        if not state.integrity_ok:
            findings.append(ForensicFinding(category="integrity", severity="fort",
                                            observation="La copie protégée ne correspond plus à son empreinte SHA-256.",
                                            explanations=["modification du fichier stocké après import"]))
        try:
            inspection = inspect_file(self.documents.stored_file(document), self.settings)
            for warning in inspection.warnings:
                findings.append(ForensicFinding(category="integrity", severity="moyen", observation=warning))
        except Exception as exc:  # contenu incohérent avec l'extension, archive suspecte…
            findings.append(ForensicFinding(category="integrity", severity="fort", observation=str(exc)))
        _, summary = self.extraction.extract(document_id)
        for warning in summary.injection_warnings[:10]:
            findings.append(ForensicFinding(category="hidden_instructions", severity="fort", observation=warning,
                                            explanations=["citation d'un exemple", "tentative de manipulation d'une IA"]))
        meta = self.metadata(document_id)
        findings += [f for f in meta.findings if f.category == "hidden_text"]
        return IntegrityReport(document_id=document_id, sha256_ok=state.integrity_ok,
                               original_protected=state.original_protected, findings=findings)

    # --- conclusion -----------------------------------------------------------------
    @staticmethod
    def _conclude(style: StyleAnalysis, meta: MetadataReport, prov: ProvenanceReport) -> tuple[Conclusion, str]:
        declared_names = " ".join(prov.declared_tools + [e for f in meta.findings if f.category == "provenance"
                                                         for e in f.evidence])
        if prov.declared_ai_media:
            scope = "des médias incorporés" if all(":" in d and "/media/" in d for d in prov.declared_ai_media) else "le fichier"
            return "generation_partielle", (f"Déclaration explicite de génération par IA dans la provenance de {scope} "
                                            "(IPTC / C2PA). Le texte lui-même n'est pas nécessairement concerné.")
        if re.search(AI_TOOL, declared_names, re.IGNORECASE):
            return "assistance_ia", ("Un assistant d'IA est nommé dans les métadonnées ou l'historique : usage déclaré, "
                                     "dont l'ampleur (idées, rédaction, relecture) reste inconnue.")
        if re.search(TRANSLATION_TOOL, declared_names, re.IGNORECASE):
            return "traduction_ia", "Un outil de traduction automatique est nommé dans les métadonnées ou l'historique."
        if re.search(CORRECTION_TOOL, declared_names, re.IGNORECASE):
            return "correction_ia", "Un outil de correction automatique est nommé dans les métadonnées ou l'historique."
        strong = sum(1 for i in style.indicators if i.strength == "fort")
        basis = (f"Aucune déclaration technique de provenance. {len(style.indicators)} indice(s) stylistique(s), dont "
                 f"{strong} fort(s) : insuffisant pour conclure, le style seul ne constitue jamais une preuve.")
        return "indeterminee", basis

    def assess(self, document_id: str, save_report: bool = False) -> AIAssessment:
        document = self.documents.get(document_id)
        style = self.writing_patterns(document_id)
        meta = self.metadata(document_id)
        prov = self.provenance(document_id)
        integrity = self.integrity(document_id)
        conclusion, basis = self._conclude(style, meta, prov)
        audit_id = new_id()
        assessment = AIAssessment(
            audit_id=audit_id, document_id=document_id, filename=document.original_filename, conclusion=conclusion,
            conclusion_label=CONCLUSION_LABELS[conclusion], basis=basis, style=style, metadata=meta, provenance=prov,
            integrity=integrity, recommendations=RECOMMENDATIONS,
            limits=GENERAL_LIMITS + style.limits + meta.limits + prov.limits)
        if save_report:
            markdown = render_report(assessment)
            folder = self.settings.projects_dir / document.project_id / "exports"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"audit-{document_id[:8]}-{utc_now()[:19].replace(':', '').replace('-', '')}.md"
            path.write_text(markdown, encoding="utf-8")
            assessment.report_path, assessment.report_markdown = str(path), markdown
        self._store(document.project_id, assessment)
        return assessment

    def _store(self, project_id: str, assessment: AIAssessment) -> None:
        findings = ([("style", i.strength, i.observation, i.passages) for i in assessment.style.indicators]
                    + [(f.category, f.severity, f.observation, f.evidence)
                       for f in assessment.metadata.findings + assessment.provenance.findings + assessment.integrity.findings])
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO audits (id, project_id, document_id, kind, conclusion, summary, report_path, "
                         "created_at) VALUES (?, ?, ?, 'ai_audit', ?, ?, ?, ?)",
                         (assessment.audit_id, project_id, assessment.document_id, assessment.conclusion,
                          json.dumps({"basis": assessment.basis, "indicators": len(assessment.style.indicators)},
                                     ensure_ascii=False), assessment.report_path, utc_now()))
            conn.executemany("INSERT INTO findings (audit_id, category, severity, observation, evidence) VALUES (?, ?, ?, ?, ?)",
                             [(assessment.audit_id, c, s, o, json.dumps(e, ensure_ascii=False)) for c, s, o, e in findings])


def _pdf_date(value: str | None) -> datetime | None:
    match = re.search(r"(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", value or "")
    if not match:
        return None
    parts = [int(p) if p else 0 for p in match.groups()]
    try:
        return datetime(*parts[:3], parts[3], parts[4], parts[5])
    except ValueError:
        return None


def _indicator_lines(indicators: list[Indicator]) -> list[str]:
    lines = []
    for indicator in indicators:
        lines.append(f"| {indicator.type} | {indicator.strength} | {indicator.observation} | "
                     f"{'; '.join(indicator.passages[:3]) or '—'} |")
    return lines


def _finding_lines(findings: list[ForensicFinding]) -> list[str]:
    return [f"| {f.category} | {f.severity} | {f.observation} | {'; '.join(f.evidence[:3]) or '—'} | "
            f"{'; '.join(f.explanations[:3]) or '—'} |" for f in findings]


def render_report(a: AIAssessment) -> str:
    lines = [
        f"# Rapport d'audit documentaire — {a.filename}", "",
        f"*Audit {a.audit_id[:8]} — {utc_now()[:10]} — Academic Writer MCP*", "",
        "> **Ce rapport présente des INDICES, pas des preuves.** Les détecteurs de texte IA ne sont pas fiables ; "
        "aucune décision ne doit reposer sur ce seul document.", "",
        "## Conclusion", "", f"**{a.conclusion_label}** — confiance : {a.confidence}.", "", a.basis, "",
        "## Passage analysé", "",
        f"Document complet : {a.style.words} mots, {a.style.sentences} phrases, langue « {a.style.language} ».", "",
        "## Indices stylistiques", "",
    ]
    if a.style.indicators:
        lines += ["| Type d'indice | Niveau | Observation | Passages |", "|---|---|---|---|", *_indicator_lines(a.style.indicators)]
    else:
        lines.append("Aucun indice stylistique relevé (ou texte trop court).")
    lines += ["", "## Métadonnées et historique", ""]
    shown = {k: v for k, v in a.metadata.properties.items() if k in (
        "creator", "lastModifiedBy", "created", "modified", "revision", "app_Application", "app_TotalTime",
        "producer", "creator", "author", "creationdate", "moddate")}
    lines += [f"- **{k}** : {v}" for k, v in shown.items()] or ["- (aucune propriété exploitable)"]
    if a.metadata.editing_sessions is not None:
        lines.append(f"- **Sessions d'édition (rsid)** : {a.metadata.editing_sessions}")
    tracked = a.metadata.tracked_changes
    if tracked and (tracked.insertions or tracked.deletions):
        lines.append(f"- **Modifications suivies** : {tracked.insertions} insertion(s), {tracked.deletions} "
                     f"suppression(s) ; auteurs : {', '.join(tracked.authors)}")
    if a.metadata.comments:
        lines.append(f"- **Commentaires** : {len(a.metadata.comments)}")
    findings = a.metadata.findings + a.provenance.findings + a.integrity.findings
    lines += ["", "## Constats techniques (provenance, intégrité)", ""]
    if findings:
        lines += ["| Catégorie | Niveau | Observation | Éléments | Explications possibles |", "|---|---|---|---|---|",
                  *_finding_lines(findings)]
    else:
        lines.append("Aucun constat technique particulier.")
    lines += ["", f"Content Credentials (C2PA) : {'manifeste détecté (signature non vérifiée)' if a.provenance.content_credentials else 'aucun'}.",
              "", "## Limites de l'analyse", "", *[f"- {limit}" for limit in dict.fromkeys(a.limits)],
              "", "## Recommandations", "", *[f"- {r}" for r in a.recommendations], ""]
    return "\n".join(lines)
