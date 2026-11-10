"""Tests du contrôle qualité (phase 8) : calculs, unités, formules, affirmations, cohérence, structure, audit final."""

from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.quality import expr as E
from academic_writer.quality.calculations import check_calculations, convert, evaluate_formula
from academic_writer.quality.claims import analyze_claims, standard_references
from academic_writer.quality.consistency import check_abbreviations, check_cross_references
from academic_writer.quality.models import Segment
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

GEAR = """Исходные данные: m = 2 мм, z = 20, n = 1450 об/мин.
Делительный диаметр d = m·z = 2·20 = 40 мм.
Диаметр вершин da = d + 2m = 40 + 2·2 = 45 мм.
Угловая скорость ω = π·n/30 = π·1450/30 = 151,8 рад/с.
Скорость v = 10 рад/с · 0,05 м = 0,5 м/с, что соответствует норме.
Сила F = 2 мм · 20 = 40 м.
Площадь S = 3,2·4,1 ≈ 13,1 мм².
Пусть m = 3 мм для второго колеса."""


def _segments(text: str, section: str = "Расчёт") -> list[Segment]:
    return [Segment(line, "paragraph", section, 1) for line in text.split("\n")]


# --- expressions et unités -------------------------------------------------------------------

@pytest.mark.parametrize(("text", "si", "dims_ok"), [
    ("1,5·10³ мм", 1.5, True), ("12 500 Н", 12500, True), ("1450 об/мин", 151.8436, True),
    ("sin 30°", 0.5, True), ("√(3²+4²)", 5, True), ("2,5 кВт·ч", 9e6, True), ("200 МПа", 2e8, True),
])
def test_expression_parser(text: str, si: float, dims_ok: bool) -> None:
    value = E.evaluate(E.parse(text, units=True))
    assert value.si == pytest.approx(si, rel=1e-4)


def test_parser_never_evaluates_code() -> None:
    with pytest.raises(E.ParseError):
        E.parse("__import__('os')", units=False)
    with pytest.raises(E.ParseError):
        E.parse("a; b", units=False)


# --- calculs -----------------------------------------------------------------------------------

def test_calculation_chain_checks() -> None:
    report = check_calculations("t", _segments(GEAR))
    by_right = {c.right: c for c in report.checks}
    assert by_right["40 мм"].status == "ok" and by_right["2·20"].status == "ok"  # m·z substitué
    assert by_right["45 мм"].status == "mismatch"  # 40 + 4 = 44
    assert by_right["151,8 рад/с"].status == "ok"  # formule écrite pour n en об/мин
    assert by_right["0,5 м/с"].status == "ok"
    assert by_right["40 м"].status == "unit_mismatch"  # mm oubliés
    assert by_right["13,1 мм²"].status == "ok"
    assert "3 мм" not in by_right  # redéfinition, pas un calcul
    assert report.mismatches == 1 and report.unit_mismatches == 1
    assert [c.code for c in report.conflicts] == ["symbol_redefined"]
    assert report.decimal_separators == {"virgule": 6}


def test_rounding_tolerance() -> None:
    report = check_calculations("t", _segments("x = 10/3 = 3,33\ny = 10/3 = 3,3\nk = 10/3 = 3\n"
                                               "q = 2/3 = 0,66\nw = 10/3 = 3,2"))
    statuses = {c.right: c.status for c in report.checks}
    assert statuses == {"3,33": "ok", "3,3": "ok", "3": "ok",  # arrondis corrects à la précision affichée
                        "0,66": "rounding",  # troncature (0,67 attendu) : écart de 1 %
                        "3,2": "mismatch"}  # écart de 4 %


def test_evaluate_formula_and_solve() -> None:
    result = evaluate_formula("d = m*z", {"d": "40 мм", "m": "2 мм"})
    assert result.solved_for == "z" and result.results_si == [pytest.approx(20)]
    result = evaluate_formula("v = ω*r", {"ω": "151,8 рад/с", "r": "50 мм"}, "м/с")
    assert result.results_in_target == [pytest.approx(7.59)] and result.unit_si == "m/s"
    with pytest.raises(ValueError, match="inconnue"):
        evaluate_formula("d = m*z", {"m": "2 мм"})  # deux inconnues : rien n'est supposé


def test_convert_units() -> None:
    assert convert("1450 об/мин", "рад/с").converted == pytest.approx(151.84, rel=1e-4)
    assert convert("200 МПа", "Н/мм2").converted == pytest.approx(200)
    with pytest.raises(ValueError):
        convert("2 мм", "кг")


# --- affirmations -------------------------------------------------------------------------------

def test_claims_traceability() -> None:
    text = ("Метод планов скоростей применяется на 85 % предприятий. "
            "По данным [@artobolevsky1988, с. 15] КПД зубчатой передачи достигает 0,98. "
            "Согласно [@inconnu2020] это самый точный метод. "
            "Оформление выполнено по ГОСТ 2.105-95. "
            "Модуль m = 2 мм задан в варианте 4.")
    report = analyze_claims("t", _segments(text, "Введение"), "ru",
                            sources={"artobolevsky1988": "verified_online"},
                            project_texts={"consignes": "вариант 4: модуль 2 мм"},
                            known_standards=["ГОСТ 2.105-2019"])
    support = {c.text[:12]: c.support for c in report.claims}
    assert support["Метод планов"] == "non_etaye"
    assert support["По данным [@"] == "source_verifiee"
    assert support["Согласно [@i"] == "cle_inconnue"
    gost = next(c for c in report.claims if "ГОСТ" in c.text)
    assert any("1995" in e and "2019" in e for e in gost.evidence) and gost.severity == "warning"
    assert not any("m = 2" in c.text for c in report.claims)  # calcul, pas affirmation


def test_standard_references() -> None:
    refs = standard_references("ГОСТ 13755-2015, ISO 53:1998 et ГОСТ Р 7.0.100-2018")
    assert ("ГОСТ 13755", "2015") in [(base, year) for _, base, year in refs]
    assert ("ISO 53", "1998") in [(base, year) for _, base, year in refs]


# --- cohérence -------------------------------------------------------------------------------

def test_figures_and_tables() -> None:
    segments = [Segment("Схема показана на рис. 1 и рис. 3, данные в табл. 1.", "paragraph", "Ход работы"),
                Segment("Рисунок 1 – Схема механизма", "caption", "Ход работы"),
                Segment("Рисунок 2 – Станок", "caption", "Ход работы"),
                Segment("Таблица 1 – Результаты", "caption", "Ход работы")]
    issues, figures, _ = check_cross_references(segments)
    codes = {(i.code, i.message.split()[-1] if i.code == "figure_missing" else "") for i in issues}
    assert any(code == "figure_missing" for code, _ in codes)
    assert any(i.code == "figure_not_referenced" and "2" in i.message for i in issues)
    assert not any(i.code.startswith("table") for i in issues)
    assert figures["legendes"] == ["1", "2"]


def test_abbreviations() -> None:
    segments = [Segment("ТММ изучает механизмы.", "paragraph", "Введение"),
                Segment("Теория механизмов и машин (ТММ) — наука. САПР используется широко.", "paragraph", "Введение"),
                Segment("Расчёт по ГОСТ выполнен.", "paragraph", "Введение")]
    issues, _ = check_abbreviations(segments)
    assert any(i.code == "abbreviation_defined_late" and "ТММ" in i.message for i in issues)
    assert any(i.code == "abbreviation_undefined" and "САПР" in i.message and "ГОСТ" not in i.message for i in issues)


# --- service et outils MCP --------------------------------------------------------------------------

def _docx(path: Path) -> Path:
    from docx import Document
    document = Document()
    document.add_heading("Цель работы", level=1)
    document.add_paragraph("Изучить нарезание зубьев методом обкатки.")
    document.add_heading("Ход работы", level=1)
    document.add_paragraph("Делительный диаметр d = 2·20 = 45 мм.")
    document.add_paragraph("Этот метод используется на 90 % заводов.")
    document.add_heading("Выводы", level=1)
    document.add_paragraph("[ЗАПОЛНИТЬ: вывод]")
    document.save(str(path))
    return path


@pytest.fixture
def lab(services: Services, inbox: Path):
    project = services.projects.create("ЛР", DocumentType.RAPPORT_LABORATOIRE, Language.RU)
    document_id = services.documents.import_document(project.id, str(_docx(inbox / "lr.docx")),
                                                     DocumentRole.DRAFT).document.id
    return project, document_id


def test_final_audit_on_document(services: Services, lab) -> None:
    project, document_id = lab
    audit = services.quality.final_audit(document_id=document_id)
    assert audit.verdict == "bloquant"
    codes = {i.code for i in audit.issues}
    assert {"mismatch", "placeholder", "non_etaye", "section_missing"} <= codes
    assert audit.report_path and Path(audit.report_path).exists()
    assert "Contrôle qualité" in audit.report_markdown and "Limites" in audit.report_markdown
    with services.db.read() as conn:
        row = conn.execute("SELECT kind, conclusion FROM audits WHERE id = ?", (audit.audit_id,)).fetchone()
    assert tuple(row) == ("quality", "bloquant")


def test_structure_on_document(services: Services, lab) -> None:
    _, document_id = lab
    report = services.quality.structure(document_id=document_id)
    found = {s.section_id: s.found_heading for s in report.sections}
    assert found["objective"] == "Цель работы" and found["conclusion"] == "Выводы"
    assert found["measurements"] is None


def test_target_requires_exactly_one(services: Services, lab) -> None:
    from academic_writer.core.errors import ValidationFailed
    with pytest.raises(ValidationFailed):
        services.quality.calculations()


@pytest.mark.anyio
async def test_quality_tools_exposed(lab) -> None:
    _, document_id = lab
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"validate_calculations", "evaluate_formula", "convert_units", "verify_factual_claims",
                "check_consistency", "check_document_structure", "final_quality_audit"} <= names
        result = await client.call_tool("validate_calculations", {"document_id": document_id})
        assert result.structured_content["mismatches"] == 1
        result = await client.call_tool("evaluate_formula", {"formula": "d = m*z", "values": {"m": "2 мм"}})
        assert result.is_error and "inconnue" in result.content[0].text


@pytest.mark.parametrize(("text", "checked", "errors"), [
    ("On a v = 15 m/s et t = 8 s.\nDonc a = v/t = 2,5 m/s².", 1, 1),
    ("On a v = 15 m/s et t = 8 s.\nDonc a = v/t = 1,875 m/s².", 1, 0),
    ("We have v = 15 m/s and t = 8 s, so a = v/t = 1.875 m/s².", 1, 0),
    ("Дано v = 15 м/с и t = 8 с. Тогда a = v/t = 2,5 м/с².", 1, 1),
    ("Calculer l'accélération a = v/t avec v = 15 m/s et t = 8 s : a = 2,5 m/s².", 1, 1),
    ("Le module m = 2 мм et le nombre de dents z = 20, donc d = m·z = 45 мм.", 1, 1),
])
def test_symbols_defined_in_running_text(text: str, checked: int, errors: int) -> None:
    """Audit C-03 : définitions reliées par « et / and / и / avec », formule écrite avant ses données."""
    report = check_calculations("t", [Segment(text, "paragraph")])
    assert (report.calculations_checked, report.mismatches) == (checked, errors)
    assert all(d.symbol != "m" or d.value == "2 мм" for d in report.definitions)


# --- calcul formel (audit E-01, M-02) --------------------------------------------------------------

@pytest.mark.parametrize(("operation", "expression", "options", "expected"), [
    ("derivative", "x^3*sin(x)", {}, "x**3*cos(x) + 3*x**2*sin(x)"),
    ("integral", "x^2", {}, "x**3/3"),
    ("integral", "exp(-x^2)", {"lower": "-oo", "upper": "oo"}, "sqrt(pi)"),
    ("limit", "sin(x)/x", {"point": "0"}, "1"),
    ("solve", "x^2 - 5x + 6 = 0", {}, "[{x: 2}, {x: 3}]"),
    ("solve", "2x + y = 5; x - y = 1", {"unknowns": ["x", "y"]}, "[{x: 2, y: 1}]"),
    ("dsolve", "diff(y(t), t, 2) + 4*y(t) = 0", {}, "Eq(y(t), C1*sin(2*t) + C2*cos(2*t))"),
    ("matrix", "Matrix([[2, 1], [1, 3]])", {"matrix_operation": "inverse"}, "Matrix([[3/5, -1/5], [-1/5, 2/5]])"),
    ("matrix", "Matrix([[2, 1], [1, -1]])", {"matrix_operation": "solve_linear", "vector": ["5", "1"]},
     "Matrix([[2], [1]])"),
    ("extrema", "x^3 - 3x", {"lower": "-2", "upper": "2"}, None),
])
def test_solve_math_known_results(services: Services, operation, expression, options, expected) -> None:
    result = services.quality.solve_math(operation, expression, **options)
    assert result.verified is True and result.engine == "SymPy"
    if expected:
        assert result.result == expected
    else:
        assert "maximum local, f = 2" in result.result and "minimum local, f = -2" in result.result


@pytest.mark.parametrize("payload", ["__import__('os').system('dir')", "x.__class__", "exec(1)", "open(x)",
                                     "lambda x: x", "getattr(x, y)", "().__class__.__bases__"])
def test_solve_math_rejects_code(services: Services, payload: str) -> None:
    from academic_writer.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        services.quality.solve_math("simplify", payload)


def test_evaluate_formula_points_to_solve_math(services: Services) -> None:
    from academic_writer.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed, match="solve_math"):
        services.quality.evaluate_formula("y = integrate(x**2, x)", {})


def test_compare_documents_versions(services: Services, inbox: Path) -> None:
    """G5 : comparaison de deux versions : passages modifiés, nombres et symboles divergents."""
    project = services.projects.create("Rapport", DocumentType.RAPPORT_LABORATOIRE, Language.FR)
    v1 = inbox / "v1.md"
    v1.write_text("# Introduction\n\nÉtude du ressort.\n\n# Résultats\n\nOn mesure k = 120 N/m.\n\nL'allongement "
                  "maximal est de 35 mm.\n", encoding="utf-8")
    v2 = inbox / "v2.md"
    v2.write_text("# Introduction\n\nÉtude du ressort.\n\n# Mesures\n\nOn mesure k = 150 N/m.\n\nL'allongement "
                  "maximal est de 35 mm.\n\nUne incertitude de 5 % est estimée.\n", encoding="utf-8")
    a = services.documents.import_document(project.id, str(v1), DocumentRole.DRAFT)
    b = services.documents.import_document(project.id, str(v2), DocumentRole.DRAFT)
    ida = a.document.id if hasattr(a, "document") else a.id
    idb = b.document.id if hasattr(b, "document") else b.id
    result = services.quality.compare_documents(ida, idb)
    assert result.headings_only_in_a == ["Résultats"] and result.headings_only_in_b == ["Mesures"]
    assert any(c.kind == "modified" and "120" in c.before and "150" in c.after for c in result.changes)
    assert any(c.kind == "added" and "incertitude" in c.after for c in result.changes)
    assert "120" in result.numbers_only_in_a and "150" in result.numbers_only_in_b
    assert [(c.symbol, c.value_a, c.value_b) for c in result.symbol_conflicts] == [("k", "120 N/m", "150 N/m")]
    assert 0.5 < result.similarity < 1


def test_similarity_missing_citations_and_repetitions(services: Services, inbox: Path) -> None:
    """G12 : passage repris sans citation signalé, passage cité reconnu, répétitions ; jamais de « plagiat »."""
    project = services.projects.create("Mémoire", DocumentType.MEMOIRE_MASTER, Language.FR)
    source = inbox / "article.txt"
    source.write_text("La maintenance préventive conditionnelle repose sur la surveillance continue de "
                      "paramètres physiques comme les vibrations et la température des roulements. Les convoyeurs "
                      "miniers subissent des charges cycliques importantes qui accélèrent l'usure des tambours.",
                      encoding="utf-8")
    draft = inbox / "memoire.md"
    draft.write_text(
        "# Introduction\n\nLa maintenance préventive conditionnelle repose sur la surveillance continue de "
        "paramètres physiques comme les vibrations et la température des roulements. Ce travail étudie un convoyeur.\n\n"
        "# Analyse\n\nSelon l'auteur, « les convoyeurs miniers subissent des charges cycliques importantes qui "
        "accélèrent l'usure des tambours » [@dupont2020]. Ce travail étudie un convoyeur de la mine.\n\n"
        "# Conclusion\n\nNous proposons un plan de surveillance adapté au site. Les mesures restent à réaliser.\n",
        encoding="utf-8")
    services.documents.import_document(project.id, str(source), DocumentRole.SOURCE)
    imported = services.documents.import_document(project.id, str(draft), DocumentRole.DRAFT)
    document_id = imported.document.id if hasattr(imported, "document") else imported.id
    report = services.quality.similarity(document_id=document_id)
    missing = [p for p in report.passages if p.status == "citation_manquante"]
    cited = [p for p in report.passages if p.cited]
    assert missing and missing[0].location == "Introduction" and "surveillance continue" in missing[0].text
    assert cited and "charges cycliques" in cited[0].text
    assert report.missing_citations == 1 and report.sources[0].source.startswith("article.txt")
    assert 0 < report.overall_share < 1 and "≠ plagiat" in report.notice


# --- lot 4 : calcul numérique et démarche en 11 étapes -----------------------------------------------------------

@pytest.mark.parametrize(("operation", "options", "key", "expected"), [
    ("minimize", {"expression": "(x-2)^2+3"}, "value", 3.0),
    ("root", {"expression": "x^3-2*x-5", "interval": [2, 3]}, "x", 2.0945514815),
    ("integrate", {"expression": "exp(-x^2)", "interval": [0, 1]}, "value", 0.746824132812),
])
def test_solve_numeric_known_values(services: Services, operation, options, key, expected) -> None:
    result = services.quality.solve_numeric(operation, **options)
    assert result.result[key] == pytest.approx(expected, rel=1e-8) and result.verified and result.engine == "SciPy"


def test_solve_numeric_ode_fit_and_statistics(services: Services) -> None:
    import math

    ode = services.quality.solve_numeric("ode", expression="v ; -4*x", variables=["t"], unknown_functions=["x", "v"],
                                         interval=[0, math.pi / 2], initial=[1, 0])
    assert ode.result["final"]["x"] == pytest.approx(-1, abs=1e-6) and ode.verified
    xs = [0, 1, 2, 3, 4, 5]
    fit = services.quality.solve_numeric("fit", expression="a*exp(b*x)", parameters=["a", "b"], x_data=xs,
                                         y_data=[2 * math.exp(0.5 * x) for x in xs])
    assert fit.result["parameters"]["b"] == pytest.approx(0.5) and fit.result_kind.startswith("estimé")
    test = services.quality.solve_numeric("ttest", samples=[[5.1, 5.3, 5.0, 5.2, 5.4], [6.0, 6.2, 5.9, 6.1, 6.3]])
    assert test.result["p_value"] < 0.001 and test.verified
    from academic_writer.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed, match="sans valeur"):
        services.quality.solve_numeric("minimize", expression="a*x^2")


def test_solve_problem_eleven_steps(services: Services) -> None:
    """Démarche en 11 étapes ; formule écrite pour n en tr/min : écart signalé en SI, juste « tel qu'écrit »."""
    si = services.quality.solve_problem({"n": "1450 об/мин", "r": "0,05"}, "v", ["omega = pi*n/30", "v = omega*r"],
                                        hypotheses=["rotation uniforme"], plausible_range=[1, 20])
    assert [s.number for s in si.steps] == list(range(1, 12))
    assert si.steps[4].status == "attention" and "values_as_written" in " ".join(si.steps[4].content)
    assert si.steps[9].status == "erreur"  # hors de l'ordre de grandeur
    written = services.quality.solve_problem({"n": "1450 об/мин", "r": "0,05"}, "v", ["omega = pi*n/30", "v = omega*r"],
                                             plausible_range=[1, 20], values_as_written=True)
    assert written.result_si == pytest.approx(7.592, abs=1e-3) and written.verified and written.steps[9].status == "ok"
    chain = services.quality.solve_problem({"s": "120 m", "t": "8 s"}, "a", ["v = s/t", "a = v/t"],
                                           target_unit="m/s^2")
    assert chain.result_si == pytest.approx(1.875) and chain.unit_si == "m/s²" and chain.verified
    missing = services.quality.solve_problem({"F": "10 kN"}, "sigma", ["sigma = F/A"])
    assert missing.result_si is None and missing.steps[7].status == "erreur"


def test_standards_catalog_and_citations(services: Services, inbox: Path) -> None:
    """Lot 5 : normes citées comparées au catalogue ; aucune norme inventée ni présentée comme gratuite à tort."""
    from academic_writer.quality.standards import CATALOG, lookup

    project = services.projects.create("Rapport", DocumentType.RAPPORT_TECHNIQUE, Language.RU)
    path = inbox / "rapport.txt"
    path.write_text("Оформление по ГОСТ 7.32-2017 и ГОСТ 2.105-95. Допуски по ISO 1101:2012, ГОСТ 12345-2020.",
                    encoding="utf-8")
    imported = services.documents.import_document(project.id, str(path), DocumentRole.DRAFT)
    document_id = imported.document.id if hasattr(imported, "document") else imported.id
    report = services.quality.check_standards(document_id=document_id)
    status = {c.code: c.status for c in report.citations}
    assert status == {"ГОСТ 7.32": "à jour", "ГОСТ 2.105": "édition antérieure", "ISO 1101": "édition antérieure",
                      "ГОСТ 12345": "non vérifiée"}
    assert lookup("ISO 690")[0].edition == "2021"
    assert all("payant" in e.access or "gratuit" in e.access or "libre" in e.access for e in CATALOG)
    assert all("payant" in e.access for e in CATALOG if e.organization in ("ISO", "IEC", "IEEE", "ASME", "CEN"))
