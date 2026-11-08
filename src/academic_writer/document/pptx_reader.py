"""Lecteur PPTX (python-pptx, licence MIT) : une « page » par diapositive."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from academic_writer.document.base import ExtractionContext, clean_cell, trim_table
from academic_writer.document.model import Block, ExtractedDocument, TableData


class PptxExtractor:
    name = "python-pptx"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        presentation = Presentation(str(path))
        blocks: list[Block] = []
        tables: list[TableData] = []

        for number, slide in enumerate(presentation.slides, start=1):
            title_shape = slide.shapes.title
            title = " ".join(title_shape.text_frame.text.split()) if title_shape is not None and title_shape.has_text_frame else ""
            blocks.append(Block(type="heading", text=title or f"Diapositive {number}", level=1, page=number))
            shapes = sorted(slide.shapes, key=lambda s: ((s.top or 0), (s.left or 0)))
            for shape in shapes:
                if title_shape is not None and shape.shape_id == title_shape.shape_id:
                    continue
                self._shape(shape, number, ctx, blocks, tables)
            if slide.has_notes_slide:
                notes = " ".join(slide.notes_slide.notes_text_frame.text.split())
                if notes:
                    blocks.append(Block(type="note", text=notes, page=number, style="speaker_notes"))

        props = presentation.core_properties
        metadata = {}
        for key in ("title", "subject", "author", "last_modified_by", "created", "modified", "revision", "keywords"):
            value = getattr(props, key, None)
            if value not in (None, ""):
                metadata[key] = value.isoformat() if hasattr(value, "isoformat") else str(value)
        return ExtractedDocument(format="pptx", extractor=self.name, page_count=len(presentation.slides),
                                 metadata=metadata, blocks=blocks, tables=tables, images=list(ctx.images),
                                 warnings=list(ctx.warnings))

    def _shape(self, shape, number: int, ctx: ExtractionContext, blocks: list[Block], tables: list[TableData]) -> None:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for child in shape.shapes:
                self._shape(child, number, ctx, blocks, tables)
            return
        if getattr(shape, "has_table", False) and shape.has_table:
            rows = [[clean_cell(cell.text) for cell in row.cells] for row in shape.table.rows]
            rows, truncated = trim_table(rows, ctx.settings.extract_max_table_rows, ctx.settings.extract_max_table_cols)
            if rows:
                index = len(tables) + 1
                tables.append(TableData(index=index, page=number, rows=rows, n_rows=len(rows),
                                        n_cols=len(rows[0]), truncated=truncated))
                blocks.append(Block(type="table", page=number, table_index=index, text=f"[Tableau {index}]"))
            return
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                image = shape.image
                info = ctx.store_image(image.blob, "." + image.ext, page=number, name=shape.name)
            except Exception:
                info = None
            if info is not None:
                blocks.append(Block(type="image", page=number, image_index=info.index, text=f"[Image {info.index}]"))
            return
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                text = " ".join("".join(run.text for run in paragraph.runs).split())
                if text:
                    block_type = "list_item" if paragraph.level > 0 else "paragraph"
                    blocks.append(Block(type=block_type, text=text, page=number))
