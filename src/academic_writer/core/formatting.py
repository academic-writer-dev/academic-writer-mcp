"""Service de mise en forme et d'export (phase 9).

- export_document : assemble les sections acceptées du plan, rend les citations [@clé] dans le style
  choisi, ajoute la bibliographie, la page de titre (informations fournies seulement) et le sommaire ;
  DOCX mis en forme selon un gabarit (ГОСТ 7.32, usage francophone, APA, IEEE), PDF via Microsoft Word.
- check_formatting / apply_formatting : contrôle d'un .docx importé, ou copie mise en forme.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.domains import DomainService
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.projects import ProjectService
from academic_writer.core.sources import SourceService
from academic_writer.core.writing import WritingService
from academic_writer.formatting import word
from academic_writer.formatting.models import TITLE_FIELDS, ExportSection, FormattingApplied, FormattingCheck
from academic_writer.formatting.presets import DEFAULT_PRESET, PRESETS, FormatPreset
from academic_writer.research import styles
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.formatting")

_DEFAULT_STYLE = {"ru": "gost", "fr": "apa", "intl": "apa"}
_SAFE_NAME = re.compile(r"[^\w\-. ]+", re.UNICODE)


class PresetList(BaseModel):
    presets: list[FormatPreset]
    default_for_project: str | None = None
    title_page_fields: list[str] = Field(default_factory=lambda: list(TITLE_FIELDS))
    word_available: bool


class ExportResult(BaseModel):
    project_id: str
    docx_path: str | None
    pdf_path: str | None
    output_path: str | None = Field(default=None, description="Fichier Markdown ou texte (formats markdown, txt).")
    preset: str
    citation_style: str | None
    sections_included: int
    unwritten_sections: list[str]
    draft_sections: list[str] = Field(description="Sections reprises d'un brouillon non validé.")
    citations_rendered: int
    unknown_citation_keys: list[str]
    bibliography_entries: int
    placeholders_remaining: int
    tables: int
    word_finalized: bool
    messages: list[str]
    ready: bool = Field(description="Aucune section manquante, aucun [À COMPLÉTER], aucune clé inconnue.")
    notice: str = ("Document produit à partir des seuls contenus validés et des informations fournies ; relire la "
                   "mise en page finale dans Word (figures à insérer, sauts de page, exigences de la кафедра).")


class FormattingService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService, documents: DocumentService,
                 domains: DomainService, writing: WritingService, sources: SourceService) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.domains = domains
        self.writing = writing
        self.sources = sources

    # --- gabarits ---------------------------------------------------------------------------
    def _convention(self, project_id: str) -> str:
        return self.domains.effective_convention(self.projects.get(project_id))

    def preset(self, preset_id: str | None, project_id: str | None = None) -> FormatPreset:
        if preset_id is None:
            preset_id = DEFAULT_PRESET.get(self._convention(project_id), "apa7") if project_id else "gost_7_32"
        if preset_id not in PRESETS:
            raise ValidationFailed(f"Gabarit inconnu : {preset_id}. Disponibles : {', '.join(PRESETS)}.")
        return PRESETS[preset_id]

    def list_presets(self, project_id: str | None = None) -> PresetList:
        default = self.preset(None, project_id).id if project_id else None
        return PresetList(presets=list(PRESETS.values()), default_for_project=default,
                          word_available=word.word_available())

    # --- page de titre mémorisée ---------------------------------------------------------------
    def _title_file(self, project_id: str) -> Path:
        return self.settings.projects_dir / project_id / "title_page.json"

    def _title_fields(self, project_id: str, provided: dict[str, str] | None) -> tuple[dict[str, str], list[str]]:
        messages = []
        stored: dict[str, str] = {}
        path = self._title_file(project_id)
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stored = {}
        if provided:
            unknown = sorted(set(provided) - set(TITLE_FIELDS))
            if unknown:
                raise ValidationFailed(f"Champs de page de titre inconnus : {', '.join(unknown)}. "
                                       f"Champs possibles : {', '.join(TITLE_FIELDS)}.")
            stored.update({k: str(v).strip() for k, v in provided.items() if v is not None})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
            messages.append("Informations de la page de titre mémorisées pour les prochains exports.")
        fields = {k: v for k, v in stored.items() if v}
        if "year" not in fields:
            fields["year"] = str(datetime.now().year)
        return fields, messages

    # --- export -------------------------------------------------------------------------------
    def _export_text(self, project_id, name, output_format, sections, stem, stamp, preset_id, style, drafts, citations,
                     unknown, bibliography, messages) -> ExportResult:
        """Rédaction en Markdown (titres #, tableaux et formules conservés) ou en texte brut."""
        import re as _re

        lines: list[str] = [f"# {name}", ""]
        unwritten: list[str] = []
        for section in sections:
            if section.kind == "title_page":
                continue
            if section.title:
                lines += ["#" * min(6, section.level + 1) + " " + section.title, ""]
            if section.text:
                lines += [section.text.strip(), ""]
            elif section.title:
                unwritten.append(section.title)
                lines += ["[Section non rédigée]", ""]
        text = "\n".join(lines).strip() + "\n"
        if output_format == "txt":
            text = _re.sub(r"^#{1,6}\s+", "", text, flags=_re.MULTILINE)
            text = _re.sub(r"\*\*([^*]+)\*\*|\*([^*]+)\*", lambda m: m.group(1) or m.group(2), text)
        path = stem.with_name(f"{stem.name}-{stamp}.{'md' if output_format == 'markdown' else 'txt'}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        placeholders = len(_re.findall(r"\[(?:À COMPLÉTER|ЗАПОЛНИТЬ|TO COMPLETE)", text, _re.IGNORECASE))
        return ExportResult(project_id=project_id, docx_path=None, pdf_path=None, output_path=str(path),
                            preset=preset_id, citation_style=style, sections_included=sum(1 for s in sections if s.text),
                            unwritten_sections=unwritten, draft_sections=drafts, citations_rendered=citations,
                            unknown_citation_keys=sorted(unknown),
                            bibliography_entries=len(bibliography.entries) if bibliography else 0,
                            placeholders_remaining=placeholders, tables=text.count("\n|---") ,
                            word_finalized=False, messages=messages,
                            ready=not unwritten and not placeholders and not unknown and not drafts)

    def export(self, project_id: str, output_format: str = "docx", preset_id: str | None = None,
               citation_style: str | None = None, title_page: dict[str, str] | None = None,
               include_drafts: bool = False) -> ExportResult:
        if output_format not in ("docx", "pdf", "markdown", "txt"):
            raise ValidationFailed("Format : docx, pdf (accompagné du DOCX), markdown ou txt.")
        project = self.projects.get(project_id)
        outline = self.writing.current_outline(project_id)
        if outline is None:
            raise ValidationFailed("Aucun plan : créez et rédigez d'abord le document (create_academic_outline).")
        preset = self.preset(preset_id, project_id)
        convention = self._convention(project_id)
        style = citation_style or _DEFAULT_STYLE.get(convention, "apa")
        if style not in styles.FORMATTERS:
            raise ValidationFailed("Style de citation : gost, apa, ieee, chicago, vancouver, harvard ou iso690.")
        sources = {s.key: s for s in self.sources.list(project_id).sources}
        bibliography = self.sources.generate_bibliography(project_id, style) if sources else None
        numbers = {e.key: e.number for e in bibliography.entries if e.number} if bibliography else {}
        data = {k: s.data for k, s in sources.items()}
        fields, messages = self._title_fields(project_id, title_page)

        sections: list[ExportSection] = []
        drafts: list[str] = []
        citations = 0
        unknown: set[str] = set()
        with self.db.read() as conn:
            for section in outline.sections:
                key = section.section_key
                if key == "title_page":
                    sections.append(ExportSection(key, section.title, section.level, None, "title_page"))
                    continue
                if key == "contents":
                    sections.append(ExportSection(key, section.title, section.level, None, "contents"))
                    continue
                row = conn.execute("SELECT text FROM section_revisions WHERE section_id = ? AND status = 'accepted' "
                                   "AND language = ? ORDER BY version DESC LIMIT 1",
                                   (section.id, outline.language)).fetchone()
                if row is None and include_drafts:
                    row = conn.execute("SELECT text FROM section_revisions WHERE section_id = ? AND language = ? "
                                       "AND status = 'proposed' ORDER BY version DESC LIMIT 1",
                                       (section.id, outline.language)).fetchone()
                    if row is not None:
                        drafts.append(section.title)
                if key == "references" and bibliography and bibliography.entries:
                    sections.append(ExportSection(key, section.title, section.level, bibliography.text,
                                                  "bibliography"))
                    continue
                text = row["text"] if row else None
                if text:
                    for _, items in styles.parse_markers(text):
                        for item_key, _ in items:
                            citations += 1
                            if item_key not in sources:
                                unknown.add(item_key)
                    text = styles.render_markers(text, style, numbers, data)
                sections.append(ExportSection(key, section.title, section.level, text))
        if not any(s.kind == "title_page" for s in sections) and title_page:
            sections.insert(0, ExportSection("title_page", "", 1, None, "title_page"))

        folder = self.settings.projects_dir / project_id / "exports"
        stem = _SAFE_NAME.sub("_", project.name).strip() or "document"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        docx_path = folder / f"{stem}-{preset.id}-{stamp}.docx"
        if output_format in ("markdown", "txt"):
            return self._export_text(project_id, project.name, output_format, sections, folder / stem, stamp,
                                     preset.id, style if sources else None, drafts, citations, unknown, bibliography,
                                     messages)
        charts = self.settings.projects_dir / project_id / "charts"
        images = {f"chart:{p.stem}": p for p in charts.glob("*.png")} if charts.exists() else {}
        from academic_writer.formatting.docx_writer import build_docx  # python-docx : au premier usage
        stats = build_docx(docx_path, sections, preset, outline.language, fields, images)
        messages += stats.warnings
        if bibliography:
            messages += [f"Bibliographie : {w}" for w in bibliography.warnings]
        pdf_path = docx_path.with_suffix(".pdf") if output_format == "pdf" else None
        finalized, message = word.finalize(docx_path, pdf_path)
        messages.append(message)
        if not finalized:
            from docx import Document

            from academic_writer.formatting.docx_writer import set_update_fields_on_open
            document = Document(str(docx_path))
            set_update_fields_on_open(document)  # Word proposera la mise à jour du sommaire à l'ouverture
            document.save(str(docx_path))
            pdf_path = None
        if stats.images_missing:
            messages.append(f"{stats.images_missing} figure(s) à insérer à la main (emplacements surlignés).")
        if unknown:
            messages.append(f"Citations vers des clés inconnues, laissées visibles ([?clé]) : {', '.join(sorted(unknown))}.")
        ready = not stats.unwritten and not stats.placeholders and not unknown and not drafts
        return ExportResult(project_id=project_id, docx_path=str(docx_path),
                            pdf_path=str(pdf_path) if pdf_path and pdf_path.exists() else None, preset=preset.id,
                            citation_style=style if sources else None,
                            sections_included=sum(1 for s in sections if s.text), unwritten_sections=stats.unwritten,
                            draft_sections=drafts, citations_rendered=citations, unknown_citation_keys=sorted(unknown),
                            bibliography_entries=len(bibliography.entries) if bibliography else 0,
                            placeholders_remaining=stats.placeholders, tables=stats.tables,
                            word_finalized=finalized, messages=messages, ready=ready)

    # --- documents Word existants -----------------------------------------------------------
    def _docx(self, document_id: str):
        document = self.documents.get(document_id)
        if document.extension.lower() != ".docx":
            raise ValidationFailed("Ce contrôle porte sur un fichier Word .docx (enregistrez un .doc au format .docx).")
        return document, self.documents.stored_file(document)

    def check(self, document_id: str, preset_id: str | None = None) -> FormattingCheck:
        document, path = self._docx(document_id)
        preset = self.preset(preset_id, document.project_id)
        from academic_writer.formatting.checker import check_docx  # python-docx : au premier usage
        return check_docx(path, document_id, document.original_filename, preset)

    def apply(self, document_id: str, preset_id: str | None = None, pdf: bool = False) -> FormattingApplied:
        document, path = self._docx(document_id)
        preset = self.preset(preset_id, document.project_id)
        folder = self.settings.projects_dir / document.project_id / "exports"
        stem = _SAFE_NAME.sub("_", Path(document.original_filename).stem).strip() or "document"
        output = folder / f"{stem}-{preset.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.docx"
        folder.mkdir(parents=True, exist_ok=True)
        working = output.with_suffix(".tmp.docx")
        shutil.copyfile(path, working)  # l'original protégé n'est jamais ouvert en écriture
        try:
            from academic_writer.formatting.checker import apply_to_copy  # python-docx : au premier usage
            formatted, headings, added = apply_to_copy(working, output, preset)
        finally:
            working.unlink(missing_ok=True)
        messages = []
        pdf_path = None
        if pdf:
            target = output.with_suffix(".pdf")
            finalized, message = word.finalize(output, target)
            messages.append(message)
            pdf_path = str(target) if finalized and target.exists() else None
        return FormattingApplied(document_id=document_id, output_path=str(output), pdf_path=pdf_path,
                                 preset=preset.id, paragraphs_formatted=formatted, headings_kept=headings,
                                 page_numbers_added=added, messages=messages)
