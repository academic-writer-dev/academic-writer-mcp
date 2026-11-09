"""Audit E-05 : gestionnaire central des logiciels (détection réelle, statut d'intégration honnête)."""

import pytest
from mcp import Client

from academic_writer.core.software import CATALOG, INDUSTRIAL_RULES, detect
from academic_writer.server.app import mcp

PROGRAMS = [("SOLIDWORKS 2025 SP05", "33.150.0053", r"C:\Program Files\SOLIDWORKS Corp"),
            ("Totally Integrated Automation Portal V18 -  TIA Portal Single SetupPackage  V18.0 SP1", "18.00.0100", None),
            ("Microsoft Excel 2019 - fr-fr", "16.0", None), ("GNU Octave 9.2.0", "9.2.0", r"C:\Octave"),
            ("Python 3.11.9 Core Interpreter (64-bit)", "3.11.9150.0", None)]


def fake_which(name: str) -> str | None:
    return {"Rscript": r"C:\R\bin\Rscript.exe"}.get(name)


def test_detection_and_honest_integration_status() -> None:
    report = detect(programs=PROGRAMS, which=fake_which, mcp_servers=["solidworks"])
    by_id = {s.id: s for s in report.software}
    assert by_id["solidworks"].detected and by_id["solidworks"].academic_writer_integration == "mcp_server"
    assert by_id["octave"].detected and by_id["octave"].academic_writer_integration == "none"
    assert by_id["octave"].version == "9.2.0" and by_id["octave"].license.startswith("GPL")
    assert by_id["r"].detected and "Rscript.exe" in by_id["r"].evidence[0]
    assert not by_id["matlab"].detected and by_id["matlab"].free_alternative == "GNU Octave"
    assert by_id["sympy"].academic_writer_integration == "native" and by_id["sympy"].detected
    assert any("Ne jamais annoncer un calcul" in n for n in report.notices)


def test_industrial_safety_rules() -> None:
    report = detect("automation", programs=PROGRAMS, which=lambda _: None, mcp_servers=[])
    tia = next(s for s in report.software if s.id == "tia_portal")
    assert tia.detected and tia.industrial_safety == INDUSTRIAL_RULES
    assert any("simulation" in rule for rule in tia.industrial_safety)
    assert any("automatisme industriel" in n for n in report.notices)


def test_only_detected_and_category_filter() -> None:
    report = detect("cad", programs=PROGRAMS, which=lambda _: None, mcp_servers=[], only_detected=True)
    assert [s.id for s in report.software] == ["solidworks"]
    with pytest.raises(ValueError):
        detect("astrologie", programs=[], which=lambda _: None, mcp_servers=[])


def test_catalogue_covers_audit_list() -> None:
    names = {s.name.casefold() for s in CATALOG}
    for expected in ("matlab", "gnu octave", "freecad", "t-flex cad", "calculix", "siemens tia portal", "codesys",
                     "kicad", "ltspice", "r", "gretl", "open babel", "qgis", "opensees", "etabs"):
        assert any(expected in n for n in names), expected
    assert all(s.cost and s.license and s.methods for s in CATALOG)


@pytest.mark.anyio
async def test_detect_software_tool_exposed() -> None:
    async with Client(mcp) as client:
        assert "detect_software" in {t.name for t in (await client.list_tools()).tools}
