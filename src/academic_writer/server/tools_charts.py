"""Outils MCP : graphiques scientifiques tracés à partir des données fournies."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.charts import ChartResult, ChartSpec, ChartType, GanttTask, Regression, Series
from academic_writer.core.charts import ChartList
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Créer un graphique", annotations=_WRITE)
    def create_chart(
        project_id: str,
        chart_type: Annotated[ChartType, Field(description=(
            "line (courbe), scatter (nuage + régression), bar, histogram, function (expression mathématique), "
            "step (efforts tranchants), area (moments fléchissants), timeseries (dates ISO), gantt (tasks)."))],
        title: str,
        source: Annotated[str, Field(description="Origine des données, obligatoire (ex. « Mesures du TP 4, "
                                                 "tableau 2 »). Jamais de données inventées.")] = "",
        x_label: str = "",
        x_unit: str = "",
        y_label: str = "",
        y_unit: str = "",
        series: Annotated[list[Series] | None, Field(description="Données fournies par l'utilisateur.")] = None,
        regression: Annotated[Regression | None, Field(description="Ajustement affiché avec équation et R².")] = None,
        function_expression: Annotated[str | None, Field(description="Pour chart_type=function, ex. « x^2*exp(-x) ».")] = None,
        x_min: float | None = None,
        x_max: float | None = None,
        bins: int | None = None,
        tasks: list[GanttTask] | None = None,
        annotate_extrema: bool = False,
        language: Literal["fr", "ru", "en"] = "fr",
        table_document_id: Annotated[str | None, Field(
            description="Lire les données dans un tableau d'un document du projet (au lieu de series).")] = None,
        table_index: int | None = None,
        x_column: Annotated[str | int | None, Field(description="Colonne des abscisses : en-tête ou numéro (1 = 1re).")] = None,
        y_columns: list[str | int] | None = None,
    ) -> ChartResult:
        """Trace un graphique EXACTEMENT à partir des données fournies (ou d'un tableau d'un document importé) :
        titre, axes avec unités, légende, source en pied de figure ; PNG 300 dpi + SVG + JSON des données utilisées.
        Insérer le champ markdown (« ![titre](chart:ID) ») dans une section : export_document intègre l'image."""
        with user_errors():
            services = get_services()
            spec_data = dict(chart_type=chart_type, title=title, source=source or "—", x_label=x_label,
                             x_unit=x_unit, y_label=y_label, y_unit=y_unit, series=series or [], regression=regression,
                             function_expression=function_expression, x_min=x_min, x_max=x_max, bins=bins,
                             tasks=tasks or [], annotate_extrema=annotate_extrema, language=language)
            if table_document_id:
                if table_index is None or x_column is None or not y_columns:
                    from academic_writer.core.errors import ValidationFailed

                    raise ValidationFailed("Lecture d'un tableau : indiquez table_index, x_column et y_columns.")
                spec = ChartSpec(**(spec_data | {"source": source or "tableau"}))
                return services.charts.create_from_table(project_id, table_document_id, table_index, x_column,
                                                         y_columns, spec)
            if not source:
                from academic_writer.core.errors import ValidationFailed

                raise ValidationFailed("Indiquez l'origine des données (source) : mesures de l'utilisateur, document, "
                                       "tableau…")
            return services.charts.create(project_id, ChartSpec(**spec_data))

    @mcp.tool(title="Lister les graphiques", annotations=_READ)
    def list_charts(project_id: str) -> ChartList:
        """Graphiques du projet, avec le code markdown à insérer dans une section."""
        with user_errors():
            return get_services().charts.list(project_id)
