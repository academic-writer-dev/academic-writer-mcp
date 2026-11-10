"""Lecteur PDF optionnel : PyMuPDF (AGPL-3.0 ou licence commerciale Artifex).

Activé uniquement si ``pdf_backend = 'pymupdf'`` et si le paquet est installé
(``uv sync --extra pymupdf``). Réservé à un usage compatible avec l'AGPL.
"""

from __future__ import annotations

from pathlib import Path

from academic_writer.core.errors import ValidationFailed
from academic_writer.document.base import ExtractionContext, clean_cell, trim_table
from academic_writer.document.layout import blocks_from_lines, heading_levels_from_sizes, normalize
from academic_writer.document.model import Block, ExtractedDocument, TableData, ocr_quality, ocr_warning
from academic_writer.document.ocr import OcrError


class PyMuPdfExtractor:
    name = "pymupdf"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        try:
            import pymupdf
        except ImportError as exc:
            raise ValidationFailed(
                "PyMuPDF n'est pas installé. Installez-le avec « uv sync --extra pymupdf » "
                "ou remettez pdf_backend = 'auto' dans la configuration."
            ) from exc

        settings = ctx.settings
        warnings = ctx.warnings
        try:
            document = pymupdf.open(str(path))
        except Exception as exc:
            raise ValidationFailed(f"PDF illisible : {exc}") from exc
        if document.needs_pass:
            document.close()
            raise ValidationFailed("PDF protégé par mot de passe.")

        page_lines: list[list[tuple[str, float]]] = []
        ocr_pages: list[int] = []
        ocr_qualities = []
        outline: dict[int, dict[str, int]] = {}
        tables_by_page: dict[int, list[tuple[list[list[str]], bool]]] = {}
        try:
            page_count = document.page_count
            limit = min(page_count, settings.extract_max_pages)
            if page_count > limit:
                warnings.append(f"Seules les {limit} premières pages sur {page_count} ont été lues.")
            metadata = {k.lower(): str(v) for k, v in (document.metadata or {}).items() if v}
            for level, title, page_number in document.get_toc(simple=True):
                if title and page_number > 0:
                    outline.setdefault(page_number, {})[normalize(title)] = min(level, 6)

            for index in range(limit):
                page = document[index]
                number = index + 1
                lines = _page_lines(page)
                text_len = sum(len(t) for t, _ in lines)
                needs_ocr = ctx.ocr_mode == "always" or (
                    ctx.ocr_mode == "auto" and text_len < settings.ocr_min_chars_per_page
                )
                if needs_ocr and ctx.ocr is not None and len(ocr_pages) < settings.ocr_max_pages:
                    try:
                        png = page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")
                        text = ctx.ocr.recognize_bytes(png, ".png", ctx.ocr_languages)
                        lines = [(line, 0.0) for line in text.split("\n")]
                        ocr_pages.append(number)
                        quality = ocr_quality(number, text)
                        ocr_qualities.append(quality)
                        if (message := ocr_warning(quality, f"Page {number}")):
                            warnings.append(message)
                    except OcrError as exc:
                        warnings.append(f"OCR impossible page {number} : {exc}")
                elif needs_ocr and ctx.ocr_mode != "never" and text_len == 0:
                    warnings.append(f"Page {number} sans texte extractible.")
                page_lines.append(lines)

                for found in page.find_tables().tables:
                    rows = [[clean_cell(c) for c in row] for row in found.extract()]
                    rows, truncated = trim_table(rows, settings.extract_max_table_rows, settings.extract_max_table_cols)
                    if len(rows) >= 2 and rows and len(rows[0]) >= 2:
                        tables_by_page.setdefault(number, []).append((rows, truncated))

                for image in page.get_images(full=True):
                    if not ctx.can_store_image():
                        break
                    try:
                        extracted = document.extract_image(image[0])
                    except Exception:
                        continue
                    if extracted and extracted.get("width", 0) >= 32 and extracted.get("height", 0) >= 32:
                        ctx.store_image(extracted["image"], "." + extracted.get("ext", "png"), page=number,
                                        width=extracted.get("width"), height=extracted.get("height"))
        finally:
            document.close()

        heading_map = {} if outline else heading_levels_from_sizes(
            [line for lines in page_lines for line in lines if line[1] > 0])
        blocks: list[Block] = []
        tables: list[TableData] = []
        for number, lines in enumerate(page_lines, start=1):
            origin = "ocr" if number in ocr_pages else None
            page_blocks = blocks_from_lines([t for t, _ in lines], number, heading_map, outline.get(number), origin)
            found = {normalize(b.text) for b in page_blocks if b.type == "heading"}
            for title, level in (outline.get(number) or {}).items():
                if title not in found:
                    page_blocks.insert(0, Block(type="heading", text=title, level=level, page=number, origin="outline"))
            blocks.extend(page_blocks)
            for rows, truncated in tables_by_page.get(number, []):
                index = len(tables) + 1
                tables.append(TableData(index=index, page=number, rows=rows, n_rows=len(rows),
                                        n_cols=len(rows[0]), truncated=truncated))
                blocks.append(Block(type="table", page=number, table_index=index, text=f"[Tableau {index}]"))
        for image in ctx.images:
            blocks.append(Block(type="image", page=image.page, image_index=image.index, text=f"[Image {image.index}]"))
        blocks.sort(key=lambda b: (b.page or 0))
        if heading_map:
            warnings.append("Titres déduits de la taille des caractères (heuristique, à vérifier).")
        return ExtractedDocument(format="pdf", extractor=self.name, page_count=page_count, metadata=metadata,
                                 blocks=blocks, tables=tables, images=list(ctx.images), warnings=list(warnings),
                                 ocr_pages=ocr_pages, ocr_quality=ocr_qualities)


def _page_lines(page) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if text:
                result.append((text, max(span.get("size", 0.0) for span in spans)))
        result.append(("", 0.0))  # fin de bloc = séparateur de paragraphe
    return result
