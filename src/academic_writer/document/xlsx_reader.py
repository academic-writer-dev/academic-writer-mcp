"""Lecteur XLSX (openpyxl, licence MIT) : chaque feuille devient un tableau.

Les valeurs lues sont celles enregistrées par Excel lors de la dernière sauvegarde
(les formules ne sont pas recalculées).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from academic_writer.document.base import ExtractionContext, clean_cell, trim_table
from academic_writer.document.model import Block, ExtractedDocument, TableData


class XlsxExtractor:
    name = "openpyxl"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        settings = ctx.settings
        workbook = load_workbook(str(path), read_only=True, data_only=True)
        blocks: list[Block] = []
        tables: list[TableData] = []
        warnings = list(ctx.warnings)
        try:
            for sheet_number, sheet in enumerate(workbook.worksheets, start=1):
                blocks.append(Block(type="heading", text=sheet.title, level=1, page=sheet_number))
                rows: list[list[str]] = []
                for row in sheet.iter_rows(values_only=True):
                    rows.append([clean_cell(v) for v in row[: settings.extract_max_table_cols + 1]])
                    if len(rows) > settings.extract_max_table_rows:
                        break
                rows, truncated = trim_table(rows, settings.extract_max_table_rows, settings.extract_max_table_cols)
                if not rows:
                    blocks.append(Block(type="paragraph", text="(feuille vide)", page=sheet_number))
                    continue
                index = len(tables) + 1
                tables.append(TableData(index=index, page=sheet_number, title=sheet.title, rows=rows,
                                        n_rows=len(rows), n_cols=len(rows[0]), truncated=truncated))
                blocks.append(Block(type="table", page=sheet_number, table_index=index, text=f"[Tableau {index}]"))
                if truncated:
                    warnings.append(f"Feuille « {sheet.title} » tronquée aux limites configurées.")
            props = workbook.properties
            metadata = {}
            for key in ("title", "subject", "creator", "lastModifiedBy", "created", "modified", "keywords",
                        "description", "category", "version"):
                value = getattr(props, key, None)
                if value not in (None, ""):
                    metadata[key] = value.isoformat() if hasattr(value, "isoformat") else str(value)
            sheet_count = len(workbook.worksheets)
        finally:
            workbook.close()
        warnings.append("Valeurs des formules : dernières valeurs enregistrées par Excel (non recalculées).")
        return ExtractedDocument(format="xlsx", extractor=self.name, page_count=sheet_count, metadata=metadata,
                                 blocks=blocks, tables=tables, warnings=warnings)
