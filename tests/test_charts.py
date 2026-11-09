"""Audit E-02 : graphiques tracés exactement à partir des données, insérés dans l'export DOCX."""

import json
from pathlib import Path

import pytest
from mcp import Client

from academic_writer.charts import ChartSpec, GanttTask, Series
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.server.app import mcp
from academic_writer.server.services import Services



@pytest.fixture
def project(services: Services):
    return services.projects.create("TP mesures", DocumentType.TP, Language.FR)


def _png_ok(path: str) -> bool:
    data = Path(path).read_bytes()
    return data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 5000


def test_scatter_with_linear_regression(services: Services, project) -> None:
    spec = ChartSpec(chart_type="scatter", title="Allongement d'un ressort", x_label="Force", x_unit="N",
                     y_label="Allongement", y_unit="mm", source="Mesures du TP",
                     series=[Series(name="essai", x=[0, 1, 2, 3, 4], y=[0.1, 2.0, 4.1, 5.9, 8.0])], regression="linear")
    result = services.charts.create(project.id, spec)
    assert _png_ok(result.png_path) and Path(result.svg_path).exists()
    fit = result.regressions[0]
    assert fit.coefficients[0] == pytest.approx(1.97, abs=0.01) and fit.r_squared > 0.99
    data = json.loads(Path(result.data_path).read_text(encoding="utf-8"))
    assert data["plotted"][0]["y"] == [0.1, 2.0, 4.1, 5.9, 8.0]  # traçabilité : données exactes
    assert result.summaries[0].y_max == 8.0 and result.markdown == f"![Allongement d'un ressort](chart:{result.chart_id})"


@pytest.mark.parametrize("kind", ["line", "step", "area", "bar", "histogram", "timeseries"])
def test_chart_types(services: Services, project, kind: str) -> None:
    x = (["2026-01-01", "2026-02-01", "2026-03-01"] if kind == "timeseries" else
         ["A", "B", "C"] if kind == "bar" else [0, 1, 2])
    spec = ChartSpec(chart_type=kind, title=f"Test {kind}", x_label="x", x_unit="m", y_label="y", y_unit="kN",
                     source="Données de test", series=[Series(name="s", x=x, y=[1.0, -2.0, 3.0])], language="ru")
    assert _png_ok(services.charts.create(project.id, spec).png_path)


def test_function_and_gantt(services: Services, project) -> None:
    fn = services.charts.create(project.id, ChartSpec(
        chart_type="function", title="Fonction", x_label="x", x_unit="", y_label="f(x)", y_unit="",
        source="Expression de l'énoncé", function_expression="x^2*exp(-x)", x_min=0, x_max=10))
    assert fn.summaries[0].x_at_y_max.startswith("2") and fn.summaries[0].y_max == pytest.approx(0.5413, abs=1e-3)
    assert any("sans unité" in w for w in fn.warnings)
    gantt = services.charts.create(project.id, ChartSpec(
        chart_type="gantt", title="Planning", source="Calendrier du mémoire",
        tasks=[GanttTask(name="Bibliographie", start="2026-01-05", end="2026-02-01"),
               GanttTask(name="Rédaction", start="2026-02-01", end="2026-04-15")]))
    assert _png_ok(gantt.png_path)


def test_invalid_data_rejected(services: Services, project) -> None:
    with pytest.raises(ValidationFailed, match="abscisses"):
        services.charts.create(project.id, ChartSpec(chart_type="line", title="t", x_label="x", y_label="y",
                                                     source="s", series=[Series(x=[1, 2], y=[1.0])]))
    with pytest.raises(ValidationFailed, match="axe x"):
        services.charts.create(project.id, ChartSpec(chart_type="line", title="t", source="s",
                                                     series=[Series(x=[1, 2], y=[1.0, 2.0])]))
    with pytest.raises(ValidationFailed, match="non autorisé|interdit"):
        services.charts.create(project.id, ChartSpec(chart_type="function", title="t", x_label="x", y_label="y",
                                                     source="s", function_expression="__import__('os')",
                                                     x_min=0, x_max=1))


def test_chart_from_document_table_and_docx_export(services: Services, project, inbox: Path) -> None:
    from tests.samples import make_xlsx

    path = make_xlsx(inbox / "mesures.xlsx")
    document = services.documents.import_document(project.id, str(path), DocumentRole.DATA)
    result = services.charts.create_from_table(
        project.id, document.document.id if hasattr(document, "document") else document.id, 1, "Force (N)",
        ["Allongement (mm)"], ChartSpec(chart_type="scatter", title="Essai de traction", x_label="Force", x_unit="N",
                                        y_label="Allongement", y_unit="mm", source="Mesures du TP", regression="linear"))
    assert "mesures.xlsx, tableau 1" in json.loads(Path(result.data_path).read_text(encoding="utf-8"))["spec"]["source"]
    assert services.charts.list(project.id).count == 1
    # insertion dans l'export DOCX
    services.domains.assign(project.id, "physique", "fr")
    outline = services.writing.create_outline(project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    section = outline.sections[1]
    revision = services.writing.save_section_draft(project.id, section.id, f"Résultats :\n\n{result.markdown}\n")
    services.writing.review_revision(revision.id, "accept")
    export = services.formatting.export(project.id, output_format="docx")
    from docx import Document

    assert len(Document(export.docx_path).inline_shapes) == 1


@pytest.mark.anyio
async def test_chart_tools_exposed() -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert {"create_chart", "list_charts"} <= names
