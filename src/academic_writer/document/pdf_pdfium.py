"""Lecteur PDF par défaut : pypdfium2 (BSD-3/Apache-2.0) + pdfplumber (MIT).

- pypdfium2 : texte page par page, signets (titres fiables), métadonnées, images,
  rendu des pages pour l'OCR.
- pdfplumber : tableaux et tailles de police (titres supposés par heuristique).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from academic_writer.core.errors import ValidationFailed
from academic_writer.document.base import ExtractionContext, clean_cell, trim_table
from academic_writer.document.layout import blocks_from_lines, heading_levels_from_sizes, normalize
from academic_writer.document.model import Block, ExtractedDocument, TableData, ocr_quality, ocr_warning
from academic_writer.document.ocr import OcrError

logger = logging.getLogger("academic_writer.pdf")


def decode_pdf_string(value: str) -> str:
    """Décode une chaîne PDF restée en hexadécimal (« <4D6963…> ») : UTF-16 si BOM, sinon Windows-1251
    (fréquent pour les PDF russes produits par Word / Acrobat), puis Latin-1 en dernier recours."""
    stripped = value.strip()
    if not (stripped.startswith("<") and stripped.endswith(">")):
        return value
    hex_part = stripped[1:-1].replace(" ", "")
    if not hex_part or len(hex_part) % 2 or any(c not in "0123456789abcdefABCDEF" for c in hex_part):
        return value
    raw = bytes.fromhex(hex_part)
    if raw.startswith((b"\xfe\xff", b"\xff\xfe")):
        return raw.decode("utf-16", errors="replace")
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value


class PdfiumExtractor:
    name = "pypdfium2+pdfplumber"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        settings = ctx.settings
        try:
            pdf = pdfium.PdfDocument(str(path))
        except pdfium.PdfiumError as exc:
            raise ValidationFailed(f"PDF illisible ou protégé par mot de passe : {exc}") from exc

        warnings = ctx.warnings
        page_texts: list[str] = []
        ocr_pages: list[int] = []
        ocr_qualities = []
        outline: dict[int, dict[str, int]] = {}
        try:
            page_count = len(pdf)
            limit = min(page_count, settings.extract_max_pages)
            if page_count > limit:
                warnings.append(f"Seules les {limit} premières pages sur {page_count} ont été lues.")
            metadata = {k.lower(): decode_pdf_string(str(v)) for k, v in pdf.get_metadata_dict().items() if v}
            for bookmark in pdf.get_toc():
                dest = bookmark.get_dest()
                title = (bookmark.get_title() or "").strip()
                if dest is None or not title:
                    continue
                page_index = dest.get_index()
                if page_index is not None:
                    outline.setdefault(page_index + 1, {})[normalize(title)] = min(bookmark.level + 1, 6)

            for index in range(limit):
                page = pdf[index]
                try:
                    textpage = page.get_textpage()
                    text = textpage.get_text_range()
                    textpage.close()
                    self._extract_images(page, index + 1, ctx)
                    needs_ocr = ctx.ocr_mode == "always" or (
                        ctx.ocr_mode == "auto" and len(text.strip()) < settings.ocr_min_chars_per_page
                    )
                    if needs_ocr and ctx.ocr is not None and len(ocr_pages) < settings.ocr_max_pages:
                        try:
                            image = page.render(scale=settings.ocr_dpi / 72).to_pil()
                            text = ctx.ocr.recognize_pil(image, ctx.ocr_languages)
                            ocr_pages.append(index + 1)
                            quality = ocr_quality(index + 1, text)
                            ocr_qualities.append(quality)
                            if (message := ocr_warning(quality, f"Page {index + 1}")):
                                warnings.append(message)
                        except OcrError as exc:
                            warnings.append(f"OCR impossible page {index + 1} : {exc}")
                    elif needs_ocr and ctx.ocr_mode != "never" and not text.strip():
                        reason = "OCR non disponible" if ctx.ocr is None else "limite de pages OCR atteinte"
                        warnings.append(f"Page {index + 1} sans texte extractible ({reason}).")
                    page_texts.append(text)
                finally:
                    page.close()
        finally:
            pdf.close()

        tables_by_page, sizes_by_page = self._plumber_pass(path, limit, ctx)
        all_lines = [line for lines in sizes_by_page.values() for line in lines]
        heading_map = heading_levels_from_sizes(all_lines) if not outline else {}

        blocks: list[Block] = []
        tables: list[TableData] = []
        for number, text in enumerate(page_texts, start=1):
            lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            origin = "ocr" if number in ocr_pages else None
            page_blocks = blocks_from_lines(lines, number, heading_map, outline.get(number), origin)
            found = {normalize(b.text) for b in page_blocks if b.type == "heading"}
            for title, level in (outline.get(number) or {}).items():
                if title not in found:  # signet dont le texte n'apparaît pas tel quel sur la page
                    page_blocks.insert(0, Block(type="heading", text=title, level=level, page=number, origin="outline"))
            blocks.extend(page_blocks)
            for rows, truncated in tables_by_page.get(number, []):
                index = len(tables) + 1
                tables.append(TableData(index=index, page=number, rows=rows, n_rows=len(rows),
                                        n_cols=len(rows[0]) if rows else 0, truncated=truncated))
                blocks.append(Block(type="table", page=number, table_index=index, text=f"[Tableau {index}]"))
        for image in ctx.images:
            blocks.append(Block(type="image", page=image.page, image_index=image.index, text=f"[Image {image.index}]"))
        blocks.sort(key=lambda b: (b.page or 0))  # tri stable : conserve l'ordre dans chaque page

        if heading_map:
            warnings.append("Titres déduits de la taille des caractères (heuristique, à vérifier) : "
                            "le PDF ne contient pas de signets.")
        return ExtractedDocument(format="pdf", extractor=self.name, page_count=page_count, metadata=metadata,
                                 blocks=blocks, tables=tables, images=list(ctx.images), warnings=list(warnings),
                                 ocr_pages=ocr_pages, ocr_quality=ocr_qualities)

    def _extract_images(self, page, page_number: int, ctx: ExtractionContext) -> None:
        if not ctx.can_store_image():
            return
        for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
            if not ctx.can_store_image():
                break
            try:
                width, height = obj.get_px_size()
                if width < 32 or height < 32:
                    continue  # pictogrammes, puces
                buffer = io.BytesIO()
                obj.extract(buffer, fb_format="png")
                data = buffer.getvalue()
                suffix = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".jp2" if data[4:8] == b"jP  " else ".png"
                ctx.store_image(data, suffix, page=page_number, width=width, height=height)
            except Exception as exc:  # image corrompue ou format exotique : on continue
                logger.debug("Image ignorée page %d : %s", page_number, exc)

    def _plumber_pass(self, path: Path, limit: int, ctx: ExtractionContext):
        tables: dict[int, list[tuple[list[list[str]], bool]]] = {}
        sizes: dict[int, list[tuple[str, float]]] = {}
        try:
            with pdfplumber.open(path) as document:
                for number, page in enumerate(document.pages[:limit], start=1):
                    try:
                        for raw in page.extract_tables():
                            rows = [[clean_cell(c) for c in row] for row in raw if row]
                            rows, truncated = trim_table(rows, ctx.settings.extract_max_table_rows,
                                                         ctx.settings.extract_max_table_cols)
                            if rows and len(rows) >= 2 and len(rows[0]) >= 2:
                                tables.setdefault(number, []).append((rows, truncated))
                        sizes[number] = _line_sizes(page)
                    finally:
                        page.close()
        except Exception as exc:
            ctx.warnings.append(f"Analyse des tableaux et des titres incomplète : {exc}")
        return tables, sizes


def _line_sizes(page) -> list[tuple[str, float]]:
    words = page.extract_words(extra_attrs=["size"], keep_blank_chars=False, use_text_flow=True)
    lines: dict[int, list[dict]] = {}
    for word in words:
        lines.setdefault(round(word["top"]), []).append(word)
    result: list[tuple[str, float]] = []
    for _, items in sorted(lines.items()):
        items.sort(key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in items)
        size = max(w["size"] for w in items)
        result.append((text, float(size)))
    return result
