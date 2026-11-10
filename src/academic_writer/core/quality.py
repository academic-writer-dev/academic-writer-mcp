"""Service de contrôle qualité (phase 8) : calculs, affirmations, cohérence, structure, audit final.

Cible : un document importé (``document_id``) ou la rédaction d'un projet (``project_id`` : sections
acceptées du plan courant). Tous les contrôles sont locaux et déterministes ; ils produisent des constats à
confirmer par une relecture humaine, jamais une validation.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.domains import DomainService
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.models import DocumentRole, new_id, utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.core.sources import SourceService
from academic_writer.core.writing import WritingService
from academic_writer.domains.model import DomainProfile
from academic_writer.domains.structures import StructureTemplate
from academic_writer.quality import calculations as calc
from academic_writer.quality import symbolic
from academic_writer.quality.claims import ClaimsReport, analyze_claims, claim_issues
from academic_writer.quality.consistency import ConsistencyReport, check_consistency
from academic_writer.quality.models import QualityIssue, Segment, Target, sort_issues
from academic_writer.quality.structure import StructureReport, check_structure
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.quality")

Verdict = Literal["bloquant", "a_corriger", "pret_pour_relecture"]
VERDICT_LABELS = {
    "bloquant": "Bloquant : erreurs à corriger avant toute remise",
    "a_corriger": "À corriger : points à vérifier ou améliorer",
    "pret_pour_relecture": "Aucun problème automatique détecté : prêt pour la relecture humaine",
}
LIMITS = [
    "Contrôles automatiques : ils ne remplacent ni la relecture de l'enseignant / du responsable, ni la vôtre.",
    "Les calculs sont vérifiés tels qu'écrits ; le choix des formules et des données n'est pas jugé.",
    "Aucune affirmation n'est déclarée vraie : seule sa traçabilité (citation, source vérifiée) est contrôlée.",
    "Le gabarit de structure est indicatif ; les consignes de l'établissement priment.",
]
_CAPTION_START = re.compile(r"^\s*(рисунок|рис\.|таблица|figure|fig\.|tableau|table)\s*\d", re.IGNORECASE)
_STOP = {"the", "and", "les", "des", "une", "для", "что", "как", "это", "при", "или"}


class RequirementCoverage(BaseModel):
    requirement_id: str
    number: str | None
    kind: str
    text: str
    covered: bool
    matched_terms: int
    total_terms: int


class FinalAudit(BaseModel):
    audit_id: str
    label: str
    verdict: Verdict
    verdict_label: str
    counts: dict[str, int]
    by_category: dict[str, int]
    summaries: dict[str, str] = Field(description="Résumé par contrôle.")
    issues: list[QualityIssue] = Field(description="Constats triés par gravité (au plus 150).")
    requirements: list[RequirementCoverage] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=lambda: list(LIMITS))
    report_path: str | None = None
    report_markdown: str | None = None


class QualityService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService, domains: DomainService, writing: WritingService,
                 sources: SourceService) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction
        self.domains = domains
        self.writing = writing
        self.sources = sources

    # --- cible ----------------------------------------------------------------------------
    def target(self, project_id: str | None = None, document_id: str | None = None) -> Target:
        if bool(project_id) == bool(document_id):
            raise ValidationFailed("Indiquez soit document_id (document importé), soit project_id (rédaction du "
                                   "projet), mais pas les deux.")
        if document_id:
            return self._document_target(document_id)
        return self._project_target(project_id)  # type: ignore[arg-type]

    def _document_target(self, document_id: str) -> Target:
        document = self.documents.get(document_id)
        result, _ = self.extraction.extract(document_id)
        segments: list[Segment] = []
        section: str | None = None
        for block in result.blocks:
            if block.type == "heading":
                section = block.text
                segments.append(Segment(block.text, "heading", section, block.page, block.level or 1))
            elif block.type == "table" and block.table_index:
                table = result.tables[block.table_index - 1] if block.table_index <= len(result.tables) else None
                if table:
                    text = "\n".join(" | ".join(cell for cell in row) for row in table.rows)
                    segments.append(Segment(text, "table", section, block.page))
            elif block.type in ("paragraph", "list_item", "note", "caption") and block.text.strip():
                kind = "caption" if block.type == "caption" or _CAPTION_START.match(block.text) else block.type
                segments.append(Segment(block.text, kind, section, block.page))
        text = " ".join(s.text for s in segments[:300])
        return Target(label=document.original_filename, project_id=document.project_id,
                      language=self._language(document.project_id, text), segments=segments,
                      document_id=document_id)

    def _project_target(self, project_id: str) -> Target:
        project = self.projects.get(project_id)
        outline = self.writing.current_outline(project_id)
        if outline is None:
            raise ValidationFailed("Ce projet n'a pas encore de plan ni de rédaction : indiquez plutôt le "
                                   "document_id d'un document importé.")
        segments: list[Segment] = []
        unaccepted: list[str] = []
        with self.db.read() as conn:
            for section in outline.sections:
                segments.append(Segment(section.title, "heading", section.title, None, section.level))
                row = conn.execute("SELECT text FROM section_revisions WHERE section_id = ? AND status = 'accepted' "
                                   "AND language = ? ORDER BY version DESC LIMIT 1",
                                   (section.id, outline.language)).fetchone()
                if row is None:
                    row = conn.execute("SELECT text FROM section_revisions WHERE section_id = ? AND language = ? "
                                       "AND status != 'rejected' ORDER BY version DESC LIMIT 1",
                                       (section.id, outline.language)).fetchone()
                    if row is not None:
                        unaccepted.append(section.title)
                if row is not None:
                    segments.extend(_markdown_segments(row["text"], section.title, section.level))
        notes = (f"Brouillons non validés inclus : {', '.join(unaccepted)}.",) if unaccepted else ()
        return Target(label=f"Rédaction du projet « {project.name} »", project_id=project_id,
                      language=outline.language, segments=segments, notes=notes)

    def _language(self, project_id: str, text: str) -> str:
        letters = [c for c in text if c.isalpha()]
        if letters and sum("Ѐ" <= c <= "ӿ" for c in letters) / len(letters) > 0.5:
            return "ru"
        language = self.projects.get(project_id).language.value
        return "en" if language == "ru" else language

    def _profile(self, project_id: str) -> DomainProfile | None:
        project = self.projects.get(project_id)
        if not project.domain_id:
            return None
        try:
            return self.domains.get_domain(project.domain_id)
        except (NotFoundError, ValidationFailed):
            return None

    def _templates(self, project_id: str) -> dict[str, StructureTemplate]:
        templates: dict[str, StructureTemplate] = {}
        for language in ("fr", "ru", "en"):
            try:
                templates[language] = self.domains.structure_template(project_id, language=language)
            except (ValidationFailed, NotFoundError, KeyError):
                continue
        return templates

    # --- contrôles ----------------------------------------------------------------------------
    def calculations(self, project_id: str | None = None, document_id: str | None = None) -> calc.CalculationReport:
        target = self.target(project_id, document_id)
        return calc.check_calculations(target.label, target.segments)

    def claims(self, project_id: str | None = None, document_id: str | None = None) -> ClaimsReport:
        return self._claims(self.target(project_id, document_id))

    def _claims(self, target: Target) -> ClaimsReport:
        sources = {s.key: s.verification_status for s in self.sources.list(target.project_id).sources}
        profile = self._profile(target.project_id)
        standards = [s.code for s in profile.standards] if profile else []
        return analyze_claims(target.label, target.segments, target.language, sources=sources,
                              project_texts=self._project_texts(target), known_standards=standards)

    def _project_texts(self, target: Target) -> dict[str, str]:
        texts: dict[str, str] = {}
        for document in self.documents.list(target.project_id)[:30]:
            if document.id == target.document_id or document.role == DocumentRole.DRAFT:
                continue
            with self.db.read() as conn:
                rows = conn.execute("SELECT text FROM chunks WHERE document_id = ? ORDER BY seq",
                                    (document.id,)).fetchall()
            if rows:
                texts[document.original_filename] = "\n".join(r["text"] for r in rows)
        with self.db.read() as conn:
            requirement_text = "\n".join(
                f"{r['text']} {r['value'] or ''}" for r in conn.execute(
                    "SELECT text, value FROM requirements WHERE project_id = ? AND status != 'rejected'",
                    (target.project_id,)))
        if requirement_text:
            texts["consignes (exigences extraites)"] = requirement_text
        return texts

    def consistency(self, project_id: str | None = None, document_id: str | None = None) -> ConsistencyReport:
        target = self.target(project_id, document_id)
        calculations = calc.check_calculations(target.label, target.segments)
        return self._consistency(target, calculations)

    def _consistency(self, target: Target, calculations: calc.CalculationReport) -> ConsistencyReport:
        return check_consistency(target.label, target.segments, target.language, self._profile(target.project_id),
                                 calc_conflicts=calculations.conflicts,
                                 decimal_counts=calculations.decimal_separators)

    def structure(self, project_id: str | None = None, document_id: str | None = None) -> StructureReport:
        return self._structure(self.target(project_id, document_id))

    def _structure(self, target: Target) -> StructureReport:
        templates = self._templates(target.project_id)
        if not templates:
            raise ValidationFailed("Aucun gabarit de structure disponible pour ce projet (type de document ?).")
        return check_structure(target.label, target.segments, templates, target.language)

    def evaluate_formula(self, formula: str, values: dict[str, str], target_unit: str | None = None) -> calc.FormulaResult:
        operation = re.search(r"\b(integrate|integral|diff|derivative|limit|lim|solve|dsolve|series|det|inverse|"
                              r"Matrix|matrix|Integral|Derivative|Limit)\s*\(", formula)
        if operation:
            raise ValidationFailed(f"« {operation.group(1)}(…) » n'est pas pris en charge par evaluate_formula (formule à "
                                   "valeurs numériques). Utiliser solve_math (intégrales, dérivées, limites, équations, "
                                   "équations différentielles, matrices).")
        try:
            return calc.evaluate_formula(formula, values, target_unit)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

    def solve_math(self, operation: str, expression: str, **options) -> symbolic.SymbolicResult:
        try:
            return symbolic.compute(operation, expression, **options)
        except symbolic.SymbolicError as exc:
            raise ValidationFailed(str(exc)) from exc

    def convert(self, value: str, target_unit: str) -> calc.ConversionResult:
        try:
            return calc.convert(value, target_unit)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

    # --- audit final ----------------------------------------------------------------------------
    def final_audit(self, project_id: str | None = None, document_id: str | None = None,
                    save_report: bool = True) -> FinalAudit:
        target = self.target(project_id, document_id)
        calculations = calc.check_calculations(target.label, target.segments)
        claims = self._claims(target)
        consistency = self._consistency(target, calculations)
        try:
            structure: StructureReport | None = self._structure(target)
        except ValidationFailed:
            structure = None
        issues: list[QualityIssue] = []
        issues += calc.calculation_issues(calculations)
        issues += [i for i in consistency.issues if i.code != "symbol_redefined"]  # déjà dans les calculs
        issues += claim_issues(claims)
        if structure:
            issues += structure.issues
        norms = self._academic_norms(target)
        issues += norms.issues
        summaries = {
            "calculs": (f"{calculations.calculations_checked} calculs vérifiés : {calculations.ok} justes, "
                        f"{calculations.mismatches} faux, {calculations.unit_mismatches} problèmes d'unités, "
                        f"{calculations.rounding} écarts d'arrondi."),
            "affirmations": (f"{claims.claims_found} affirmations repérées ; "
                             + ", ".join(f"{k} : {v}" for k, v in sorted(claims.by_support.items())) + "."
                             if claims.claims_found else "Aucune affirmation factuelle repérée."),
            "coherence": f"{len(consistency.issues)} constats de cohérence.",
            "structure": (f"Gabarit : {structure.template} ; {structure.headings_found} titres trouvés."
                          if structure else "Structure non contrôlée (aucun gabarit disponible)."),
            "normes": f"Normes de présentation (ISO 7144, 214, 2145, 80000, 8601) et longueur : {norms.summary}",
        }
        coverage: list[RequirementCoverage] = []
        if target.document_id is None:
            issues += self._draft_issues(target.project_id)
            audit = self.sources.audit(target.project_id)
            for item in audit.issues:
                issues.append(QualityIssue(category="sources", code=item.code, severity=item.severity,
                                           message=item.message, location=item.section_title,
                                           suggestion=None))
            summaries["sources"] = audit.summary
        coverage = self._requirement_coverage(target)
        uncovered = [c for c in coverage if not c.covered]
        for item in uncovered:
            issues.append(QualityIssue(category="exigences", code="requirement_maybe_missing", severity="warning",
                                       message=f"Exigence {item.number or ''} peut-être non traitée ({item.kind}) : "
                                               f"« {item.text[:160]} »".replace("  ", " "),
                                       suggestion="Vérifier que le document y répond explicitement."))
        if coverage:
            summaries["exigences"] = (f"{len(coverage) - len(uncovered)}/{len(coverage)} exigences confirmées "
                                      "retrouvées dans le texte (recherche de mots-clés, indicative).")
        for note in target.notes:
            issues.append(QualityIssue(category="redaction", code="unaccepted_drafts", severity="warning", message=note,
                                       suggestion="Relire et valider (ou rejeter) ces brouillons."))
        issues = sort_issues(issues)
        counts = {level: sum(1 for i in issues if i.severity == level) for level in ("error", "warning", "info")}
        by_category: dict[str, int] = {}
        for issue in issues:
            by_category[issue.category] = by_category.get(issue.category, 0) + 1
        verdict: Verdict = "bloquant" if counts["error"] else "a_corriger" if counts["warning"] else "pret_pour_relecture"
        result = FinalAudit(audit_id=new_id(), label=target.label, verdict=verdict, verdict_label=VERDICT_LABELS[verdict],
                            counts=counts, by_category=by_category, summaries=summaries, issues=issues[:150],
                            requirements=coverage)
        if save_report:
            markdown = render_quality_report(result)
            folder = self.settings.projects_dir / target.project_id / "exports"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"controle-qualite-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
            path.write_text(markdown, encoding="utf-8")
            result.report_path, result.report_markdown = str(path), markdown
        self._store(target, result)
        return result

    def _draft_issues(self, project_id: str) -> list[QualityIssue]:
        status = self.writing.draft_status(project_id)
        issues = []
        for section in status.sections:
            if section.target_words and not section.accepted_revision_id:
                issues.append(QualityIssue(category="redaction", code="section_not_accepted", severity="warning",
                                           message=f"Section « {section.title} » non rédigée ou non validée.",
                                           suggestion="Rédiger la section puis valider une révision."))
        return issues

    def _requirement_coverage(self, target: Target) -> list[RequirementCoverage]:
        requirements = self.writing.list_requirements(target.project_id, status="confirmed").requirements
        if not requirements:
            return []
        text_stems = {w[:5] for w in re.findall(r"\w+", " ".join(s.text for s in target.segments).casefold())
                      if len(w) >= 4}
        coverage = []
        for requirement in requirements:
            if requirement.kind not in ("task", "step", "question", "objective"):
                continue
            stems = {w[:5] for w in re.findall(r"\w+", requirement.text.casefold())
                     if len(w) >= 4 and not w.isdigit() and w not in _STOP}
            if not stems:
                continue
            matched = len(stems & text_stems)
            coverage.append(RequirementCoverage(requirement_id=requirement.id, number=requirement.number,
                                                kind=requirement.kind, text=requirement.text,
                                                covered=matched / len(stems) >= 0.5, matched_terms=matched,
                                                total_terms=len(stems)))
        return coverage

    def _store(self, target: Target, result: FinalAudit) -> None:
        summary = {"counts": result.counts, "by_category": result.by_category, "summaries": result.summaries}
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO audits (id, project_id, document_id, kind, conclusion, summary, report_path, "
                         "created_at) VALUES (?, ?, ?, 'quality', ?, ?, ?, ?)",
                         (result.audit_id, target.project_id, target.document_id, result.verdict,
                          json.dumps(summary, ensure_ascii=False), result.report_path, utc_now()))

    # --- comparaison de documents ---------------------------------------------------------------------
    def compare_documents(self, document_a: str, document_b: str):
        from academic_writer.quality.compare import compare

        parts = []
        for document_id in (document_a, document_b):
            document = self.documents.get(document_id)
            result, _ = self.extraction.extract(document_id)
            headings = [b.text for b in result.blocks if b.type == "heading"]
            paragraphs = [b.text for b in result.blocks if b.type in ("paragraph", "list_item", "note") and b.text.strip()]
            parts.append((document.original_filename, headings, paragraphs))
        if self.documents.get(document_a).project_id != self.documents.get(document_b).project_id:
            raise ValidationFailed("Les deux documents doivent appartenir au même projet.")
        return compare(*parts[0], *parts[1])

    # --- similarité avec les sources du projet ---------------------------------------------------------
    def similarity(self, project_id: str | None = None, document_id: str | None = None, min_words: int = 8):
        from academic_writer.quality.similarity import analyze

        target = self.target(project_id, document_id)
        segments: list[tuple[str | None, str]] = []
        current: list[str] = []
        section = None
        for segment in target.segments:
            if segment.kind == "heading":
                if current:
                    segments.append((section, " ".join(current)))
                section, current = segment.text, []
            elif segment.kind != "table":
                current.append(segment.text)
        if current:
            segments.append((section, " ".join(current)))
        sources: list[tuple[str, str]] = []
        for document in self.documents.list(target.project_id):
            if document.id == document_id:
                continue
            result, _ = self.extraction.extract(document.id)
            text = "\n".join(b.text for b in result.blocks if b.text)
            if text.strip():
                sources.append((f"{document.original_filename} ({document.role.value})", text))
        if not sources:
            raise ValidationFailed("Aucun autre document dans le projet : importez les sources à comparer "
                                   "(articles, cours, versions précédentes).")
        return analyze(target.label, segments, sources, min_words, target.language)

    # --- calcul numérique et démarche de résolution ---------------------------------------------------------
    def solve_numeric(self, operation: str, **options):
        from academic_writer.quality.numeric import NumericError, compute

        try:
            return compute(operation, **options)
        except NumericError as exc:
            raise ValidationFailed(str(exc)) from exc
        except (ValueError, ArithmeticError) as exc:
            raise ValidationFailed(f"Calcul numérique impossible : {exc}") from exc

    def solve_problem(self, data: dict[str, str], unknown: str, formulas: list[str], **options):
        from academic_writer.quality.problem import solve

        if not formulas:
            raise ValidationFailed("Indiquez au moins une formule (elles ne sont jamais choisies à la place de "
                                   "l'utilisateur ou du cours).")
        return solve(data, unknown, formulas, **options)

    # --- normes ----------------------------------------------------------------------------------------
    def check_standards(self, project_id: str | None = None, document_id: str | None = None):
        from academic_writer.quality.standards import check

        target = self.target(project_id, document_id)
        return check(target.label, "\n".join(s.text for s in target.segments))

    # --- normes internationales de présentation et consignes de longueur ----------------------------------
    def academic_norms(self, project_id: str | None = None, document_id: str | None = None):
        target = self.target(project_id, document_id)
        return self._academic_norms(target)

    def _academic_norms(self, target: Target):
        from academic_writer.quality.academic_norms import NormCheck, check_norms

        project = self.projects.get(target.project_id)
        report = check_norms(target, str(project.document_type.value if hasattr(project.document_type, "value")
                                         else project.document_type))
        length = self._length_check(target)
        if length:
            check, issue = length
            report.checks.insert(0, NormCheck(**check))
            if issue:
                report.issues.insert(0, issue)
        return report

    def _length_check(self, target: Target) -> tuple[dict, QualityIssue | None] | None:
        """Longueur demandée par l'enseignant (exigence « length » non rejetée) comparée au texte."""
        requirements = [r for r in self.writing.list_requirements(target.project_id, kind="length").requirements
                        if r.status != "rejected" and r.value]
        if not requirements:
            return None
        value = requirements[-1].value or ""
        match = re.match(r"(\d+)(?:-(\d+))?\s+(\S+)", value)
        if not match:
            return None
        low, high, unit = int(match.group(1)), int(match.group(2) or match.group(1)), match.group(3).lower()
        words = sum(len(re.findall(r"\w+", s.text)) for s in target.body)
        if re.match(r"page|страниц|лист", unit):
            measured, label = round(words / 280, 1), "pages (estimation : 280 mots par page)"
        elif re.match(r"mot|слов|word", unit):
            measured, label = words, "mots"
        else:
            return None
        ok = low * 0.9 <= measured <= high * 1.1
        check = {"norm": "consignes de l'enseignant", "rule": f"longueur demandée : {value}",
                 "status": "conforme" if ok else "non_conforme", "detail": f"≈ {measured:g} {label}"}
        issue = None if ok else QualityIssue(
            category="exigences", code="length_out_of_range", severity="warning",
            message=f"Longueur ≈ {measured:g} {label.split(' (')[0]} pour {value} demandés par les consignes.",
            suggestion="Ajuster le développement des sections (sans remplissage) ou vérifier la consigne.")
        return check, issue



def _markdown_segments(text: str, section: str, level: int) -> list[Segment]:
    segments: list[Segment] = []
    current = section
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", block)
        if heading and "\n" not in block:
            current = heading.group(2).strip()
            segments.append(Segment(current, "heading", current, None, level + len(heading.group(1)) - 1))
            continue
        if block.startswith("|"):
            rows = [line.strip().strip("|") for line in block.splitlines() if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", line)]
            segments.append(Segment("\n".join(rows), "table", current))
            continue
        kind = "caption" if _CAPTION_START.match(block) and len(block) < 200 else (
            "list_item" if re.match(r"^\s*(?:[-*•]|\d+[.)])\s", block) else "paragraph")
        segments.append(Segment(block, kind, current))
    return segments


def render_quality_report(audit: FinalAudit) -> str:
    lines = [f"# Contrôle qualité — {audit.label}", "", f"**Verdict : {audit.verdict_label}**", "",
             f"Erreurs : {audit.counts['error']} · Avertissements : {audit.counts['warning']} · "
             f"Informations : {audit.counts['info']}", "", "## Résumé par contrôle", ""]
    lines += [f"- **{name}** : {text}" for name, text in audit.summaries.items()]
    labels = {"error": "Erreurs", "warning": "Avertissements", "info": "Informations"}
    for level in ("error", "warning", "info"):
        selected = [i for i in audit.issues if i.severity == level]
        if not selected:
            continue
        lines += ["", f"## {labels[level]}", ""]
        for issue in selected:
            where = f" — {issue.location}" if issue.location else ""
            lines.append(f"- [{issue.category}] {issue.message}{where}")
            if issue.excerpt:
                lines.append(f"  > {issue.excerpt}")
            if issue.suggestion:
                lines.append(f"  → {issue.suggestion}")
    if audit.requirements:
        lines += ["", "## Exigences confirmées", ""]
        lines += [f"- {'✔' if r.covered else '?'} {r.number or ''} {r.text[:150]}".replace("  ", " ")
                  for r in audit.requirements]
    lines += ["", "## Limites", ""] + [f"- {item}" for item in audit.limits]
    return "\n".join(lines) + "\n"
