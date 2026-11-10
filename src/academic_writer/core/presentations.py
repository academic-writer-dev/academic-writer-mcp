"""Service des présentations : plan, génération PPTX, contrôles de contenu, export PDF / ODP et aperçus."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from academic_writer.core.charts import ChartService
from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.projects import ProjectService
from academic_writer.core.sources import SourceService
from academic_writer.core.teaching import allowed_roles
from academic_writer.core.writing import WritingService
from academic_writer.presentations import planner, powerpoint
from academic_writer.presentations.models import Deck, PresentationPlan, PresentationResult, SlideCheck
from academic_writer.writing.checks import numbers_in

_SAFE = re.compile(r"[^\w\-]+")
_DEFAULT_SECONDS = {"title": 30, "section": 15, "questions": 0, "references": 20, "quote": 40}


def slide_text(slide) -> str:
    parts = [slide.title, slide.subtitle or "", slide.caption or "", slide.quote or ""]
    parts += slide.bullets + slide.left_bullets + slide.right_bullets + slide.steps + slide.header
    parts += [" ".join(r) for r in slide.rows] + [f"{f.value} {f.label}" for f in slide.figures]
    return "\n".join(p for p in parts if p)


class PresentationService:
    def __init__(self, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService, writing: WritingService, sources: SourceService,
                 charts: ChartService) -> None:
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction
        self.writing = writing
        self.sources = sources
        self.charts = charts

    # --- plan -------------------------------------------------------------------------------------------
    def plan(self, project_id: str, occasion: str, duration_minutes: int, *, document_id: str | None = None,
             topic: str | None = None) -> PresentationPlan:
        project = self.projects.get(project_id)
        if occasion not in planner.STRUCTURES:
            raise ValidationFailed(f"Occasion inconnue : {', '.join(planner.STRUCTURES)}.")
        if not 3 <= duration_minutes <= 90:
            raise ValidationFailed("Durée entre 3 et 90 minutes.")
        sections: list[tuple[str, str]] = []
        warnings: list[str] = []
        if document_id:
            document = self.documents.get(document_id)
            if document.project_id != project_id:
                raise ValidationFailed("Ce document n'appartient pas au projet.")
            result, _ = self.extraction.extract(document_id)
            current, buffer = document.title or document.original_filename, []
            for block in result.blocks:
                if block.type == "heading":
                    if buffer:
                        sections.append((current, " ".join(buffer)))
                    current, buffer = block.text.strip(), []
                elif block.type in ("paragraph", "list_item") and block.text.strip():
                    buffer.append(block.text.strip())
            if buffer:
                sections.append((current, " ".join(buffer)))
            if len(sections) <= 1 and not any(b.type == "heading" for b in result.blocks):
                warnings.append("Document sans titres reconnus : la matière est tirée du texte entier.")
        else:
            outline = self.writing.current_outline(project_id)
            if outline:
                for section in outline.sections:
                    revision = self.writing._latest_revision(section.id)
                    if revision and revision.status != "rejected":
                        sections.append((section.title, revision.text))
                        if revision.status != "accepted":
                            warnings.append(f"Section « {section.title} » : brouillon non validé utilisé.")
        if topic and not sections:
            warnings.append(f"Présentation à partir du seul sujet « {topic} » : proposer la structure, puis ne "
                            "remplir qu'avec des informations vérifiables (sources enregistrées, données fournies).")
        charts = [(c.chart_id, c.title) for c in self.charts.list(project_id).charts]
        citable = [] if project.source_policy == "course_only" else [
            f"[@{s.key}] {s.data.title}" for s in self.sources.list(project_id).sources]
        slides, more = planner.plan(occasion, project.language.value, duration_minutes, sections, charts, bool(citable))
        narrative = ["Problématique : quelle question, pourquoi elle compte.", "Objectifs : ce que le travail visait.",
                     "Méthode : comment on a procédé (données, outils).",
                     "Résultats : ce qu'on a trouvé, chaque résultat appuyé par une figure ou un tableau.",
                     "Conclusion : réponse à la question, apports, limites, perspectives."]
        return PresentationPlan(
            project_id=project_id, occasion=occasion, language=project.language.value,
            duration_minutes=duration_minutes, slide_count=len(slides), narrative=narrative, slides=slides,
            available_charts=[f"{cid} — {title}" for cid, title in charts], citable_sources=citable,
            warnings=warnings + more,
            next_step="Rédiger chaque diapositive à partir de la matière fournie (sans rien ajouter d'invérifiable), "
                      "avec des notes du présentateur, puis appeler create_presentation avec le deck.")

    # --- génération ---------------------------------------------------------------------------------------
    def _images(self, project_id: str, deck: Deck) -> dict[str, Path]:
        images = self.charts.images(project_id)
        root = (self.settings.projects_dir / project_id).resolve()
        for slide in deck.slides:
            if slide.image_path:
                path = Path(slide.image_path).resolve()
                if not path.is_relative_to(root):
                    raise ValidationFailed("Image hors du dossier du projet : utiliser les images extraites "
                                           "(extract_document_images) ou les graphiques du projet.")
                images[slide.image_path] = path
        return images

    def _content_checks(self, project_id: str, deck: Deck, duration_minutes: int | None) -> list[SlideCheck]:
        project = self.projects.get(project_id)
        checks: list[SlideCheck] = []
        self.extraction.index_project(project_id)  # documents importés mais pas encore lus
        sources_text = self.writing._sources_text(project_id, roles=allowed_roles(project.source_policy))
        sources_text += "\n" + "\n".join(chart.title for chart in self.charts.list(project_id).charts)
        for chart_json in (self.charts.folder(project_id).glob("*.json") if self.charts.folder(project_id).exists() else []):
            sources_text += "\n" + chart_json.read_text(encoding="utf-8")
        known = numbers_in(sources_text)
        titles: dict[str, int] = {}
        for index, slide in enumerate(deck.slides, start=1):
            text = slide_text(slide)
            if slide.type not in ("title", "references", "questions"):
                unknown = sorted(n for n in numbers_in(text) if n not in known)
                if unknown:
                    checks.append(SlideCheck(slide=index, severity="error", code="unsourced_number",
                                             message="Chiffre(s) absent(s) des documents, de la rédaction et des "
                                                     f"graphiques du projet : {', '.join(unknown[:8])}."))
            if len(slide.bullets) > 6:
                checks.append(SlideCheck(slide=index, severity="warning", code="too_many_bullets",
                                         message=f"{len(slide.bullets)} puces : 6 au plus par diapositive."))
            long = [b for b in slide.bullets if len(b) > 130]
            if long:
                checks.append(SlideCheck(slide=index, severity="warning", code="long_bullet",
                                         message=f"{len(long)} puce(s) de plus de 130 caractères : condenser."))
            if len(text.split()) > 80 and slide.type not in ("references", "table"):
                checks.append(SlideCheck(slide=index, severity="warning", code="dense_slide",
                                         message=f"{len(text.split())} mots : diapositive trop dense (≈ 40 conseillés)."))
            if slide.type not in ("title", "questions", "references", "section") and not slide.notes.strip():
                checks.append(SlideCheck(slide=index, severity="warning", code="no_notes",
                                         message="Pas de notes du présentateur."))
            if slide.title:
                key = slide.title.casefold()
                if key in titles and slide.type not in ("section",):
                    checks.append(SlideCheck(slide=index, severity="info", code="repeated_title",
                                             message=f"Même titre que la diapositive {titles[key]}."))
                titles.setdefault(key, index)
            if re.search(r"\[(?:À COMPLÉTER|ЗАПОЛНИТЬ|TO COMPLETE)", text, re.IGNORECASE):
                checks.append(SlideCheck(slide=index, severity="warning", code="placeholder",
                                         message="Marqueur à compléter présent."))
        if deck.slides[0].type != "title":
            checks.append(SlideCheck(slide=1, severity="info", code="no_title_slide", message="Pas de diapositive de titre."))
        registered = bool(self.sources.list(project_id).sources) if project.source_policy != "course_only" else False
        cited = any("[@" in slide_text(s) for s in deck.slides) or (registered and any(s.source for s in deck.slides))
        if cited and not any(s.type == "references" for s in deck.slides) and project.source_policy != "course_only":
            checks.append(SlideCheck(slide=len(deck.slides), severity="warning", code="no_references",
                                     message="Sources citées mais aucune diapositive de références."))
        if duration_minutes:
            estimated = self.estimate_minutes(deck)
            if abs(estimated - duration_minutes) > max(2.0, 0.25 * duration_minutes):
                checks.append(SlideCheck(slide=0, severity="warning", code="duration",
                                         message=f"Durée estimée {estimated:.1f} min pour {duration_minutes} min "
                                                 "prévues : ajuster le nombre de diapositives."))
        return checks

    @staticmethod
    def estimate_minutes(deck: Deck) -> float:
        seconds = 0
        for slide in deck.slides:
            if slide.duration_seconds:
                seconds += slide.duration_seconds
            elif slide.notes.strip():
                seconds += max(30, len(slide.notes.split()) / 130 * 60)  # ≈ 130 mots par minute à l'oral
            else:
                seconds += _DEFAULT_SECONDS.get(slide.type, 60)
        return round(seconds / 60, 1)

    def _fill_references(self, project_id: str, deck: Deck) -> None:
        empty = [s for s in deck.slides if s.type == "references" and not s.references and not s.bullets]
        if not empty:
            return
        style = "gost" if deck.language == "ru" else "apa"
        try:
            bibliography = self.sources.generate_bibliography(project_id, style=style, include_uncited=True)
        except ValidationFailed:
            return
        entries = [re.sub(r"^\d+\.\s*", "", e.text) for e in bibliography.entries]
        for slide in empty:
            slide.references = entries[:12]

    def create(self, project_id: str, deck: Deck, *, duration_minutes: int | None = None, export_pdf: bool = True,
               export_odp: bool = False, preview: bool = True) -> PresentationResult:
        self.writing._active_project(project_id)
        images = self._images(project_id, deck)
        self._fill_references(project_id, deck)
        folder = self.settings.projects_dir / project_id / "presentations"
        stem = (_SAFE.sub("_", deck.title).strip("_") or "presentation")[:60]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pptx = folder / f"{stem}-{stamp}.pptx"
        from academic_writer.presentations.builder import Builder  # python-pptx : chargé au premier usage

        checks = Builder(deck, images).build(pptx) + self._content_checks(project_id, deck, duration_minutes)
        messages: list[str] = []
        pdf = odp = None
        previews: list[Path] = []
        if export_pdf or export_odp or preview:
            ok, message, previews = powerpoint.export(
                pptx, pdf=pptx.with_suffix(".pdf") if export_pdf else None,
                odp=pptx.with_suffix(".odp") if export_odp else None,
                png_dir=folder / f"{stem}-{stamp}-apercu" if preview else None)
            messages.append(message)
            pdf = pptx.with_suffix(".pdf") if export_pdf and pptx.with_suffix(".pdf").exists() else None
            odp = pptx.with_suffix(".odp") if export_odp and pptx.with_suffix(".odp").exists() else None
        checks.sort(key=lambda c: ({"error": 0, "warning": 1, "info": 2}[c.severity], c.slide))
        return PresentationResult(
            pptx_path=str(pptx), pdf_path=str(pdf) if pdf else None, odp_path=str(odp) if odp else None,
            preview_paths=[str(p) for p in previews], slide_count=len(deck.slides),
            estimated_minutes=self.estimate_minutes(deck), checks=checks,
            errors=sum(c.severity == "error" for c in checks), warnings=sum(c.severity == "warning" for c in checks),
            messages=messages)
