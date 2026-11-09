"""Service des graphiques : création à partir de données fournies ou d'un tableau d'un document du projet."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from academic_writer.charts import ChartError, ChartResult, ChartSpec, Series, render
from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.models import new_id
from academic_writer.core.projects import ProjectService


class ChartInfo(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    source: str
    png_path: str
    markdown: str


class ChartList(BaseModel):
    project_id: str
    count: int
    charts: list[ChartInfo]


class ChartService:
    def __init__(self, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService) -> None:
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction

    def folder(self, project_id: str) -> Path:
        return self.settings.projects_dir / project_id / "charts"

    def create(self, project_id: str, spec: ChartSpec) -> ChartResult:
        self.projects.get(project_id)
        try:
            return render(spec, self.folder(project_id), new_id()[:12])
        except ChartError as exc:
            raise ValidationFailed(str(exc)) from exc

    def series_from_table(self, document_id: str, table_index: int, x_column: str | int,
                          y_columns: list[str | int]) -> tuple[list[Series], str]:
        """Séries lues dans un tableau extrait (1re ligne = en-têtes) ; colonnes par nom ou par numéro (1 = 1re)."""
        document = self.documents.get(document_id)
        tables = self.extraction.tables(document_id, max_tables=200).tables
        table = next((t for t in tables if t.index == table_index), None)
        if table is None:
            raise ValidationFailed(f"Tableau {table_index} introuvable dans {document.original_filename} "
                                   f"({len(tables)} tableau(x)).")
        header, rows = table.rows[0], [r for r in table.rows[1:] if any(c.strip() for c in r)]

        def column(ref: str | int) -> int:
            if isinstance(ref, int) or str(ref).isdigit():
                index = int(ref) - 1
            else:
                matches = [i for i, h in enumerate(header) if h.strip().casefold() == str(ref).strip().casefold()]
                if not matches:
                    raise ValidationFailed(f"Colonne « {ref} » introuvable ; en-têtes : {', '.join(header)}.")
                index = matches[0]
            if not 0 <= index < len(header):
                raise ValidationFailed(f"Colonne {ref} hors du tableau ({len(header)} colonnes).")
            return index

        xi = column(x_column)
        series: list[Series] = []
        for ref in y_columns:
            yi = column(ref)
            xs, ys, skipped = [], [], 0
            for row in rows:
                cells = row + [""] * (len(header) - len(row))
                x_cell, y_cell = cells[xi].strip(), cells[yi].strip()
                try:
                    y_value = float(y_cell.replace(" ", "").replace(" ", "").replace(",", "."))
                except ValueError:
                    skipped += 1
                    continue
                xs.append(x_cell)
                ys.append(y_value)
            if not ys:
                raise ValidationFailed(f"Colonne « {header[yi]} » : aucune valeur numérique.")
            series.append(Series(name=header[yi], x=xs, y=ys))
        origin = f"{document.original_filename}, tableau {table_index}" + (f" (p. {table.page})" if table.page else "")
        return series, origin

    def create_from_table(self, project_id: str, document_id: str, table_index: int, x_column: str | int,
                          y_columns: list[str | int], spec: ChartSpec) -> ChartResult:
        document = self.documents.get(document_id)
        if document.project_id != project_id:
            raise ValidationFailed("Ce document n'appartient pas au projet.")
        series, origin = self.series_from_table(document_id, table_index, x_column, y_columns)
        spec = spec.model_copy(update={"series": series, "source": spec.source or origin})
        if origin not in spec.source:
            spec = spec.model_copy(update={"source": f"{spec.source} — {origin}"[:300]})
        return self.create(project_id, spec)

    def list(self, project_id: str) -> ChartList:
        self.projects.get(project_id)
        charts: list[ChartInfo] = []
        folder = self.folder(project_id)
        for data in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime) if folder.exists() else []:
            try:
                spec = json.loads(data.read_text(encoding="utf-8"))["spec"]
            except (OSError, ValueError, KeyError):
                continue
            charts.append(ChartInfo(chart_id=data.stem, title=spec["title"], chart_type=spec["chart_type"],
                                    source=spec["source"], png_path=str(data.with_suffix(".png")),
                                    markdown=f"![{spec['title']}](chart:{data.stem})"))
        return ChartList(project_id=project_id, count=len(charts), charts=charts)

    def images(self, project_id: str) -> dict[str, Path]:
        """Correspondance « chart:ID » → PNG, pour l'export DOCX."""
        folder = self.folder(project_id)
        return {f"chart:{p.stem}": p for p in folder.glob("*.png")} if folder.exists() else {}
