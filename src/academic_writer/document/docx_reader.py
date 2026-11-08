"""Lecteur DOCX (python-docx, licence MIT).

Extrait dans l'ordre de lecture : titres (styles ou niveau hiérarchique), paragraphes,
listes, légendes, tableaux, images ; puis les notes de bas de page.
Les modifications suivies et commentaires sont seulement signalés (analyse en Phase 7).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path, PurePosixPath

from docx import Document as load_docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree

from academic_writer.document.base import ExtractionContext, clean_cell, trim_table
from academic_writer.document.model import Block, ExtractedDocument, TableData

_HEADING_STYLE = re.compile(r"^(heading|titre|заголовок|überschrift|título|titolo)\s*(\d)$", re.IGNORECASE)
_TITLE_STYLES = {"title", "titre", "название", "заголовок"}
_CAPTION_STYLES = {"caption", "légende", "название объекта", "подпись"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SAFE_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def _outline_level(element) -> int | None:
    ppr = element.find(qn("w:pPr")) if element is not None else None
    if ppr is None:
        return None
    lvl = ppr.find(qn("w:outlineLvl"))
    if lvl is None:
        return None
    try:
        value = int(lvl.get(qn("w:val")))
    except (TypeError, ValueError):
        return None
    return value + 1 if 0 <= value <= 8 else None


def _heading_level(paragraph: Paragraph) -> int | None:
    style = paragraph.style
    name = (style.name or "").strip() if style is not None else ""
    match = _HEADING_STYLE.match(name)
    if match:
        return int(match.group(2))
    if name.casefold() in _TITLE_STYLES:
        return 0
    level = _outline_level(paragraph._p)
    if level is None and style is not None:
        level = _outline_level(style.element)
    return level


def _is_list_item(paragraph: Paragraph) -> bool:
    ppr = paragraph._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return True
    style = paragraph.style
    return bool(style is not None and (style.name or "").lower().startswith(("list", "список", "liste")))


class DocxExtractor:
    name = "python-docx"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        document = load_docx(str(path))
        blocks: list[Block] = []
        tables: list[TableData] = []
        seen_images: set[str] = set()

        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                paragraph = Paragraph(child, document)
                self._add_images(paragraph, document, ctx, blocks, seen_images)
                text = " ".join(paragraph.text.split())
                if not text:
                    continue
                level = _heading_level(paragraph)
                style_name = paragraph.style.name if paragraph.style is not None else None
                if level is not None:
                    blocks.append(Block(type="heading", text=text, level=level, style=style_name))
                elif style_name and style_name.casefold() in _CAPTION_STYLES:
                    blocks.append(Block(type="caption", text=text, style=style_name))
                elif _is_list_item(paragraph):
                    blocks.append(Block(type="list_item", text=text, style=style_name))
                else:
                    blocks.append(Block(type="paragraph", text=text, style=style_name))
            elif child.tag == qn("w:tbl"):
                table = Table(child, document)
                index = len(tables) + 1
                rows, truncated = self._table_rows(table, ctx)
                tables.append(TableData(index=index, rows=rows, n_rows=len(rows),
                                        n_cols=len(rows[0]) if rows else 0, truncated=truncated))
                blocks.append(Block(type="table", table_index=index, text=f"[Tableau {index}]"))

        warnings = list(ctx.warnings)
        metadata, pages = self._metadata(document, path)
        blocks.extend(self._footnotes(path))
        body_xml = document.element.body
        if body_xml.find(".//" + qn("w:ins")) is not None or body_xml.find(".//" + qn("w:del")) is not None:
            warnings.append("Le document contient des modifications suivies (non acceptées) : "
                            "le texte extrait peut ne pas refléter la version finale.")
        with zipfile.ZipFile(path) as archive:
            if "word/comments.xml" in archive.namelist():
                warnings.append("Le document contient des commentaires (non extraits dans le texte).")

        return ExtractedDocument(format="docx", extractor=self.name, page_count=pages, metadata=metadata,
                                 blocks=blocks, tables=tables, images=list(ctx.images), warnings=warnings)

    def _add_images(self, paragraph, document, ctx, blocks, seen) -> None:
        for rid in paragraph._p.xpath(".//a:blip/@r:embed"):
            if rid in seen:
                continue
            seen.add(rid)
            part = document.part.related_parts.get(rid)
            if part is None or not getattr(part, "content_type", "").startswith("image/"):
                continue
            suffix = PurePosixPath(str(part.partname)).suffix or ".bin"
            info = ctx.store_image(part.blob, suffix, page=None, name=PurePosixPath(str(part.partname)).name)
            if info is not None:
                blocks.append(Block(type="image", image_index=info.index, text=f"[Image {info.index}]"))

    def _table_rows(self, table: Table, ctx: ExtractionContext) -> tuple[list[list[str]], bool]:
        rows: list[list[str]] = []
        for row in table.rows:
            cells: list[str] = []
            previous = None
            for cell in row.cells:
                # Les cellules fusionnées sont renvoyées plusieurs fois : on ne garde le texte qu'une fois.
                cells.append("" if cell._tc is previous else clean_cell(cell.text))
                previous = cell._tc
            rows.append(cells)
        return trim_table(rows, ctx.settings.extract_max_table_rows, ctx.settings.extract_max_table_cols)

    def _metadata(self, document, path: Path) -> tuple[dict[str, str], int | None]:
        props = document.core_properties
        metadata: dict[str, str] = {}
        for key in ("title", "subject", "author", "last_modified_by", "created", "modified", "revision",
                    "keywords", "category", "comments", "language", "version"):
            value = getattr(props, key, None)
            if value not in (None, ""):
                metadata[key] = value.isoformat() if hasattr(value, "isoformat") else str(value)
        pages = None
        with zipfile.ZipFile(path) as archive:
            if "docProps/app.xml" in archive.namelist():
                root = etree.fromstring(archive.read("docProps/app.xml"), _SAFE_PARSER)
                for element in root:
                    tag = etree.QName(element).localname
                    if tag in ("Pages", "Words", "Characters", "Application", "AppVersion", "TotalTime", "Company"):
                        if element.text:
                            metadata[f"app_{tag.lower()}"] = element.text.strip()
                if metadata.get("app_pages", "").isdigit():
                    pages = int(metadata["app_pages"])
        return metadata, pages

    def _footnotes(self, path: Path) -> list[Block]:
        with zipfile.ZipFile(path) as archive:
            if "word/footnotes.xml" not in archive.namelist():
                return []
            root = etree.fromstring(archive.read("word/footnotes.xml"), _SAFE_PARSER)
        notes: list[Block] = []
        for footnote in root.iter(f"{_W}footnote"):
            try:
                if int(footnote.get(f"{_W}id", "0")) <= 0:
                    continue  # séparateurs
            except ValueError:
                continue
            text = " ".join("".join(t.text or "" for t in footnote.iter(f"{_W}t")).split())
            if text:
                notes.append(Block(type="note", text=text, style="footnote"))
        return notes
