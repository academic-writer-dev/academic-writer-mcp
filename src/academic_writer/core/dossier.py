"""Dossier de recherche : à partir d'un THÈME, tout ce qu'il faut pour rédiger un TP, un TD ou un mémoire.

Le serveur fait l'intermédiaire entre les bibliothèques et l'étudiant :
1. reconnaît le domaine (profil du projet, sinon vocabulaire du thème) ;
2. cherche dans les bases gratuites les ouvrages et articles RÉELS sur le thème (plusieurs formulations possibles,
   fr / ru / en), avec auteurs, année, DOI, lien et licence ;
3. rassemble les consignes de l'enseignant (tâches, longueur, mise en forme, plan imposé, style des références),
   le plan proposé, la démarche de la discipline et les normes applicables ;
4. produit un dossier Word mis en forme selon les consignes, que l'étudiant utilise pour rédiger son travail.
Aucune référence n'est inventée ; chaque source reste à confirmer (register_source) avant d'être citée.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DOCUMENT_TYPE_LABELS

_KIND_LABELS = {"task": "Tâches demandées", "question": "Questions", "objective": "Objectifs", "step": "Étapes",
                "length": "Longueur", "structure": "Structure demandée", "format": "Mise en forme", "norm": "Normes",
                "constraint": "Sources autorisées", "deadline": "Échéance", "variant": "Variante",
                "data": "Données fournies", "other": "Autres consignes"}
_NORMS = {
    "these": ["ISO 7144 — présentation des thèses et documents analogues", "ISO 214 — résumés",
              "ISO 2145 — numérotation des divisions", "ISO 690 — références bibliographiques",
              "ISO 80000-1 — grandeurs et unités (SI)"],
    "rapport": ["ANSI/NISO Z39.18 — rapports scientifiques et techniques", "ISO 214 — résumés",
                "ISO 2145 — numérotation des divisions", "ISO 690 — références bibliographiques",
                "ISO 80000-1 — grandeurs et unités (SI)"],
    "court": ["ISO 80000-1 — grandeurs et unités (SI)", "ISO 690 — références bibliographiques"],
}
_THESES = {"memoire_licence", "memoire_master", "these_doctorat"}
_SHORT = {"td", "tp", "compte_rendu_tp", "rapport_laboratoire", "devoir"}
AI_STATEMENT = ("Déclaration d'utilisation d'outils numériques (à adapter selon les règles de l'établissement) : "
                "la recherche documentaire, la vérification des références et le contrôle des calculs ont été "
                "assistés par un outil informatique (Academic Writer). Les sources ont été consultées, l'analyse, "
                "les choix et la rédaction relèvent de l'auteur, qui en assume la responsabilité.")


class DossierSource(BaseModel):
    item_id: str
    title: str
    authors: list[str]
    year: int | None
    container: str | None
    service: str
    doi: str | None
    link: str | None
    open_access: bool
    license: str | None
    relevance: float


class ResearchDossier(BaseModel):
    project_id: str
    topic: str
    queries: list[str]
    domain: str | None
    document_type: str
    sources: list[DossierSource]
    outline: list[str]
    teacher_rules: list[str]
    norms: list[str]
    docx_path: str | None = None
    markdown_path: str | None = None
    notices: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class DossierService:
    def __init__(self, settings, projects, writing, domains, sources, formatting) -> None:
        self.settings = settings
        self.projects = projects
        self.writing = writing
        self.domains = domains
        self.sources = sources
        self.formatting = formatting

    def build(self, project_id: str, topic: str, queries: list[str] | None = None, limit: int = 15,
              write_docx: bool = True) -> ResearchDossier:
        topic = (topic or "").strip()
        if len(topic) < 3:
            raise ValidationFailed("Indiquez le thème du travail (au moins 3 caractères).")
        project = self.projects.get(project_id)
        language = project.language.value
        document_type = str(getattr(project.document_type, "value", project.document_type))
        searches = list(dict.fromkeys([topic, *[q.strip() for q in queries or [] if q and len(q.strip()) >= 3]]))[:4]
        notices: list[str] = []
        found: dict[str, DossierSource] = {}
        domain_label = None
        for query in searches:
            result = self.sources.discover(query, "all", limit=max(5, min(limit, 25)), project_id=project_id)
            for notice in result.notices:
                if notice.startswith("Domaine reconnu"):
                    domain_label = notice.split(":", 1)[1].split("—")[0].strip()
                elif "indisponible" in notice and notice not in notices:
                    notices.append(notice)
            for work in result.works:
                key = (work.doi or "").lower() or re.sub(r"\W+", " ", work.title.casefold())[:80]
                if key in found and found[key].relevance >= work.relevance:
                    continue
                found[key] = DossierSource(item_id=work.item_id, title=work.title, authors=work.authors[:6],
                                           year=work.year, container=work.container, service=work.service,
                                           doi=work.doi, link=work.landing_url, open_access=work.open_access,
                                           license=work.license, relevance=work.relevance)
        sources = sorted(found.values(), key=lambda s: (-s.relevance, -(s.year or 0)))[: max(5, min(limit, 40))]
        if not sources:
            notices.append("Aucune source pertinente trouvée : reformuler le thème ou essayer une autre langue.")

        outline = self._outline(project_id)
        rules = self._teacher_rules(project_id)
        profile = self._profile(project, topic)
        norms = self._norms(document_type, profile, project)
        dossier = ResearchDossier(
            project_id=project_id, topic=topic, queries=searches, domain=domain_label or self._domain_name(profile),
            document_type=DOCUMENT_TYPE_LABELS.get(project.document_type, document_type), sources=sources,
            outline=outline, teacher_rules=rules, norms=norms, notices=notices,
            next_steps=["Lire les sources retenues (liens) et enregistrer celles qui seront citées (register_source).",
                        "Valider le plan (validate_outline), puis rédiger section par section en citant les sources.",
                        "Contrôler avant remise : final_quality_audit (calculs, sources, consignes, normes).",
                        "Exporter selon les consignes (export_document) ; la mise en forme de l'enseignant est "
                        "appliquée automatiquement."])
        if write_docx:
            self._write(dossier, profile, language)
        return dossier

    # --- éléments du dossier ----------------------------------------------------------------------------
    def _profile(self, project, topic: str = ""):
        from academic_writer.core.errors import NotFoundError

        domain_id = project.domain_id or self.sources._detect_domain(f"{topic} {project.name}")
        try:
            return self.domains.get_domain(domain_id) if domain_id else None
        except NotFoundError:
            return None

    @staticmethod
    def _domain_name(profile) -> str | None:
        return profile.names.get("fr") if profile else None

    def _outline(self, project_id: str) -> list[str]:
        outline = self.writing.current_outline(project_id)
        if outline is not None:
            return [("    " * (s.level - 1)) + s.title for s in outline.sections]
        from academic_writer.core.teaching import load_profile
        from academic_writer.writing.outline import teacher_template

        template = self.domains.structure_template(project_id)
        project = self.projects.get(project_id)
        with self.writing.db.read() as conn:
            teacher = load_profile(conn, project.teacher_profile_id)
        if teacher and teacher.expected_structure:
            template = teacher_template(template, teacher.expected_structure)
        return [s.title for s in template.sections]

    def _teacher_rules(self, project_id: str) -> list[str]:
        from academic_writer.writing.format_instructions import overrides, setting

        lines = []
        requirements = [r for r in self.writing.list_requirements(project_id).requirements if r.status != "rejected"]
        for kind, label in _KIND_LABELS.items():
            items = [r for r in requirements if r.kind == kind and kind != "format"]
            for r in items[:30]:
                number = f"{r.number}. " if r.number else ""
                text = r.text if len(r.text) <= 180 else r.text[:179] + "…"
                lines.append(f"{label} — {number}{text}" + (f" ({r.value})" if r.value and kind != "constraint" else ""))
        settings = self.formatting.teacher_settings(project_id)
        _, applied = overrides(settings)
        if applied:
            lines.append("Mise en forme imposée — " + "; ".join(applied))
        style = setting(settings, "citation_style")
        if style:
            lines.append(f"Style des références imposé — {style}")
        file_format = setting(settings, "file_format")
        if file_format:
            lines.append(f"Format de remise — {file_format.upper()}")
        return lines

    def _norms(self, document_type: str, profile, project) -> list[str]:
        family = "these" if document_type in _THESES else "court" if document_type in _SHORT else "rapport"
        norms = list(_NORMS[family])
        if profile:
            convention = project.convention or ("ru" if project.language.value == "ru" else "intl")
            for standard in profile.standards[:12]:
                if any(n.startswith(standard.code + " ") for n in norms):
                    continue  # déjà citée
                if standard.convention in (convention, "intl"):
                    norms.append(f"{standard.code} — {standard.title.get('fr')} (édition à vérifier)")
            minimum = profile.bibliography.min_sources.get(document_type)
            if minimum:
                norms.append(f"Nombre indicatif de sources pour ce type de travail : au moins {minimum}")
        return list(dict.fromkeys(norms))

    # --- fichier Word -------------------------------------------------------------------------------------
    def _markdown(self, dossier: ResearchDossier, profile, language: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        intro = [f"**Thème :** {dossier.topic}", f"**Type de travail :** {dossier.document_type}",
                 f"**Domaine reconnu :** {dossier.domain or 'non déterminé'}",
                 f"**Recherches effectuées :** {'; '.join(dossier.queries)}",
                 f"**Date :** {datetime.now().strftime('%d.%m.%Y')}"]
        sections.append(("Présentation du dossier", "\n\n".join(intro)))
        sections.append(("Consignes de l'enseignant à respecter",
                         "\n".join(f"- {line}" for line in dossier.teacher_rules) if dossier.teacher_rules else
                         "Aucune consigne importée : importer les consignes (import_document) puis les analyser "
                         "(analyze_assignment) pour qu'elles soient appliquées."))
        sections.append(("Plan proposé", "\n".join(f"{i}. {t.strip()}" for i, t in enumerate(dossier.outline, 1))))
        if profile and profile.methodology.get(language) or profile and profile.methodology.get("fr"):
            steps = profile.methodology.get(language) or profile.methodology.get("fr")
            sections.append(("Démarche de la discipline", "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))))
        if dossier.sources:
            rows = ["| N° | Référence | Année | Base | Accès |", "|---|---|---|---|---|"]
            for i, s in enumerate(dossier.sources, 1):
                authors = ", ".join(s.authors[:3]) + (" et al." if len(s.authors) > 3 else "")
                where = f" — {s.container}" if s.container else ""
                ident = f" DOI {s.doi}" if s.doi else ""
                reference = f"{authors + '. ' if authors else ''}{s.title}{where}.{ident}".replace("|", "/")
                access = "libre accès" if s.open_access else "lien (lecture selon licence)"
                rows.append(f"| {i} | {reference} | {s.year or '—'} | {s.service} | {access} |")
            links = "\n".join(f"- [{i}] {s.link}" for i, s in enumerate(dossier.sources, 1) if s.link)
            sections.append(("Sources trouvées (à lire et à confirmer)", "\n".join(rows) + "\n\nLiens :\n\n" + links))
        sections.append(("Normes et règles de présentation applicables", "\n".join(f"- {n}" for n in dossier.norms)))
        sections.append(("Étapes suivantes", "\n".join(f"{i}. {s}" for i, s in enumerate(dossier.next_steps, 1))))
        sections.append(("Déclaration d'utilisation d'outils numériques (modèle)", AI_STATEMENT))
        return sections

    def _write(self, dossier: ResearchDossier, profile, language: str) -> None:
        from academic_writer.formatting.docx_writer import build_docx
        from academic_writer.formatting.models import ExportSection

        sections = self._markdown(dossier, profile, language)
        folder = self.settings.projects_dir / dossier.project_id / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        markdown = "\n\n".join([f"# Dossier de recherche — {dossier.topic}"]
                               + [f"## {title}\n\n{text}" for title, text in sections])
        md_path = folder / f"dossier-recherche-{stamp}.md"
        md_path.write_text(markdown, encoding="utf-8")
        dossier.markdown_path = str(md_path)
        try:
            preset = self.formatting.preset(None, dossier.project_id)
            export = [ExportSection(f"s{i}", title, 1, text) for i, (title, text) in enumerate(sections)]
            path = folder / f"dossier-recherche-{stamp}.docx"
            build_docx(Path(path), export, preset, language, {})
            dossier.docx_path = str(path)
        except (ImportError, OSError, ValueError) as exc:
            dossier.notices.append(f"Fichier Word non produit ({exc}) : le dossier Markdown est disponible.")
