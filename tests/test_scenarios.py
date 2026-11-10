"""Campagne des 25 scénarios du cahier des charges (§ 23), de bout en bout, avec les vrais services.

Chaque test correspond à un scénario numéroté ; le rapport est dans TEST_REPORT.md.
"""

from pathlib import Path

import pytest
from pptx import Presentation

from academic_writer.charts import ChartSpec
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.presentations.models import Criterion, Deck, KeyFigure, Slide, TitleInfo
from academic_writer.research.models import Person, SourceData
from academic_writer.server.services import Services
from tests.samples import make_scanned_pdf, make_text_pdf, make_xlsx


def _doc_id(imported) -> str:
    return imported.document.id if hasattr(imported, "document") else imported.id


def _import(services: Services, project_id: str, inbox: Path, name: str, text: str,
            role: DocumentRole = DocumentRole.INSTRUCTIONS) -> str:
    path = inbox / name
    path.write_text(text, encoding="utf-8")
    return _doc_id(services.documents.import_document(project_id, str(path), role))


def _approved(services: Services, project_id: str):
    outline = services.writing.create_outline(project_id)
    return services.writing.validate_outline(outline.id, approve=True, force=True).outline


# 1. TD de mathématiques -------------------------------------------------------------------------------------
def test_s01_td_mathematics(services: Services, inbox: Path) -> None:
    project = services.projects.create("TD analyse", DocumentType.TD, Language.FR)
    _import(services, project.id, inbox, "td.txt", "TD 4\n1. Calculer la dérivée de f(x) = x^3 sin(x).\n"
                                                    "2. Calculer l'intégrale de exp(-x^2) sur R.\n")
    analysis = services.writing.analyze_assignment(project.id)
    assert sum(r.kind in ("task", "question") for r in analysis.requirements) >= 2
    assert services.quality.solve_math("derivative", "x^3*sin(x)").verified
    assert services.quality.solve_math("integral", "exp(-x^2)", lower="-oo", upper="oo").result == "sqrt(pi)"


# 2. Exercice de mécanique (cinématique) -----------------------------------------------------------------------
def test_s02_mechanics_exercise(services: Services) -> None:
    solution = services.quality.solve_problem({"n": "1450 об/мин", "r": "0,05"}, "v", ["omega = pi*n/30", "v = omega*r"],
                                              hypotheses=["rotation uniforme"], plausible_range=[1, 20],
                                              values_as_written=True)
    assert solution.result_si == pytest.approx(7.592, abs=1e-3) and solution.verified
    assert [s.number for s in solution.steps] == list(range(1, 12))


# 3. TP de science des matériaux (essai de traction) ----------------------------------------------------------
def test_s03_materials_lab(services: Services, inbox: Path) -> None:
    from openpyxl import Workbook

    project = services.projects.create("TP traction", DocumentType.TP, Language.FR)
    spec = ChartSpec(chart_type="scatter", title="Allongement en fonction de la force", x_label="Force", x_unit="N",
                     y_label="Allongement", y_unit="mm", source="Essai", regression="linear")
    two_points = _doc_id(services.documents.import_document(project.id, str(make_xlsx(inbox / "essai.xlsx")),
                                                            DocumentRole.DATA))
    refused = services.charts.create_from_table(project.id, two_points, 1, "Force (N)", ["Allongement (mm)"], spec)
    assert not refused.regressions and any("3 points" in w for w in refused.warnings)  # jamais d'ajustement sur 2 points
    book = Workbook()
    sheet = book.active
    sheet.append(["Force (N)", "Allongement (mm)"])
    for force, elongation in ((0, 0.0), (100, 0.12), (200, 0.25), (300, 0.36), (400, 0.49), (500, 0.61)):
        sheet.append([force, elongation])
    book.save(inbox / "traction.xlsx")
    data = _doc_id(services.documents.import_document(project.id, str(inbox / "traction.xlsx"), DocumentRole.DATA))
    chart = services.charts.create_from_table(project.id, data, 1, "Force (N)", ["Allongement (mm)"], spec)
    assert chart.regressions[0].r_squared > 0.99 and Path(chart.script_path).exists()


# 4. Rapport de chimie (calculs écrits vérifiés) ---------------------------------------------------------------
def test_s04_chemistry_report(services: Services, inbox: Path) -> None:
    project = services.projects.create("Rapport chimie", DocumentType.RAPPORT_LABORATOIRE, Language.FR)
    doc = _import(services, project.id, inbox, "rapport.txt",
                  "On dissout m = 5,85 g de sel dans V = 0,5 L.\nLa concentration massique vaut c = m/V = 11,7 g/L.\n"
                  "Le rendement de la synthèse est de 92 % (titrage acido-basique, solution tampon).",
                  DocumentRole.DRAFT)
    report = services.quality.calculations(document_id=doc)
    assert report.calculations_checked >= 1 and report.mismatches == 0


# 5. Devoir de biologie (statistique) -------------------------------------------------------------------------------
def test_s05_biology_statistics(services: Services) -> None:
    result = services.quality.solve_numeric("ttest", samples=[[12.1, 11.8, 12.5, 12.0, 11.9],
                                                              [13.4, 13.1, 13.8, 13.2, 13.6]])
    assert result.result["p_value"] < 0.01 and result.result_kind.startswith("estimé")


# 6. Analyse statistique en économie ----------------------------------------------------------------------------------
def test_s06_economics_analysis(services: Services) -> None:
    corr = services.quality.solve_numeric("correlation", samples=[[1, 2, 3, 4, 5, 6], [2.0, 2.9, 4.2, 5.1, 5.8, 7.1]])
    assert corr.result["pearson_r"] > 0.99
    fit = services.quality.solve_numeric("fit", expression="a + b*x", parameters=["a", "b"],
                                         x_data=[1, 2, 3, 4, 5, 6], y_data=[2.0, 2.9, 4.2, 5.1, 5.8, 7.1])
    assert fit.result["parameters"]["b"] == pytest.approx(0.98, abs=0.05)


# 7. Document de droit (domaine à haut risque) ------------------------------------------------------------------------
def test_s07_law_document(services: Services) -> None:
    project = services.projects.create("Note juridique", DocumentType.DOCUMENTATION_PROFESSIONNELLE, Language.FR)
    assignment = services.domains.assign(project.id, "droit", "fr")
    assert assignment.risk_level == "high" and "conseil juridique" in assignment.message


# 8. Rapport informatique ---------------------------------------------------------------------------------------------
def test_s08_computing_report(services: Services, inbox: Path) -> None:
    project = services.projects.create("Rapport info", DocumentType.RAPPORT_TECHNIQUE, Language.EN)
    _import(services, project.id, inbox, "spec.txt", "Design a REST API with a relational database, unit tests, "
            "continuous integration, algorithm complexity analysis and source code repository.")
    identification = services.domains.identify(project.id)
    assert identification.candidates[0].domain_id in ("informatique", "ia_data_science")


# 9. Projet d'automatisation (sécurité industrielle) -----------------------------------------------------------------
def test_s09_automation_project(services: Services) -> None:
    from academic_writer.core.errors import ValidationFailed
    from academic_writer.core.software import detect

    report = detect("automation", programs=[("Totally Integrated Automation Portal V18 - TIA Portal Single "
                                             "SetupPackage V18.0 SP1", "18.0", None)], which=lambda _: None, mcp_servers=[])
    tia = next(s for s in report.software if s.id == "tia_portal")
    assert tia.detected and tia.industrial_safety and tia.academic_writer_integration == "none"
    project = services.projects.create("Automate", DocumentType.PROJET_TECHNIQUE, Language.FR)
    with pytest.raises(ValidationFailed, match="automatisme industriel"):
        services.software_jobs.prepare(project.id, "tia_portal", {"ob1.scl": "x"})


# 10. Rapport de maintenance minière (interdisciplinaire) -------------------------------------------------------------
def test_s10_mining_maintenance_report(services: Services, inbox: Path) -> None:
    project = services.projects.create("Maintenance convoyeur", DocumentType.RAPPORT_MAINTENANCE, Language.RU)
    _import(services, project.id, inbox, "zadanie.txt", "1. Рассчитать наработку на отказ конвейера.\n")
    services.domains.assign(project.id, "maintenance_industrielle", "ru")
    services.domains.set_secondary(project.id, ["automobile_engins"])
    services.writing.analyze_assignment(project.id)
    brief = services.writing.build_brief(project.id, _approved(services, project.id).sections[0].id)
    assert "Автомобили, тракторы и тяжёлая техника" in brief.brief + brief.system_prompt


# 11. Mémoire de Licence (plan et export DOCX) ------------------------------------------------------------------------
def test_s11_bachelor_thesis_export(services: Services) -> None:
    project = services.projects.create("Mémoire L3", DocumentType.MEMOIRE_LICENCE, Language.FR)
    services.domains.assign(project.id, "genie_mecanique", "fr")
    outline = _approved(services, project.id)
    section = next(s for s in outline.sections if s.section_key == "introduction")
    revision = services.writing.save_section_draft(project.id, section.id, "Le mémoire étudie un réducteur.")
    services.writing.review_revision(revision.id, "accept")
    export = services.formatting.export(project.id, output_format="docx")
    assert Path(export.docx_path).exists() and export.unwritten_sections


# 12. Mémoire de Master (audit final) --------------------------------------------------------------------------------
def test_s12_master_thesis_audit(services: Services, inbox: Path) -> None:
    project = services.projects.create("Mémoire M2", DocumentType.MEMOIRE_MASTER, Language.FR)
    doc = _import(services, project.id, inbox, "memoire.md", "# Introduction\n\nLa vitesse vaut v = 120/8 = 16 m/s.\n\n"
                  "# Conclusion\n\nLe travail est terminé.\n", DocumentRole.DRAFT)
    audit = services.quality.final_audit(document_id=doc)
    assert audit.verdict != "pret" or audit.counts.get("error", 0) == 0
    assert any(i.category == "calculs" for i in audit.issues)  # 120/8 = 15, pas 16


# 13. Travail doctoral (structure et similarité) -------------------------------------------------------------------------
def test_s13_doctoral_work(services: Services, inbox: Path) -> None:
    project = services.projects.create("Thèse", DocumentType.THESE_DOCTORAT, Language.FR)
    services.domains.assign(project.id, "genie_mecanique", "fr")
    titles = [s.title.casefold() for s in services.domains.structure_template(project.id).sections]
    assert any("état de l'art" in t or "revue" in t for t in titles)
    _import(services, project.id, inbox, "article.txt", "La fatigue des assemblages soudés dépend fortement de la "
            "géométrie du cordon et des contraintes résiduelles introduites par le soudage.", DocumentRole.SOURCE)
    draft = _import(services, project.id, inbox, "chapitre.md", "# Chapitre 1\n\nLa fatigue des assemblages soudés dépend "
                    "fortement de la géométrie du cordon et des contraintes résiduelles introduites par le soudage.\n",
                    DocumentRole.DRAFT)
    assert services.quality.similarity(document_id=draft).missing_citations == 1


# 14. Article scientifique (bibliographie) -------------------------------------------------------------------------------
def test_s14_scientific_article(services: Services) -> None:
    project = services.projects.create("Article", DocumentType.ARTICLE_SCIENTIFIQUE, Language.EN)
    services.sources.register(project.id, "article", SourceData(
        title="Gear cutting", container="Journal of Mechanisms", year=2020, volume="5", issue="3", pages="10–20",
        doi="10.1234/abc", authors=[Person(family="Ivanov", given="Ivan I.")]))
    for style in ("ieee", "apa", "harvard", "iso690", "vancouver", "chicago"):
        bibliography = services.sources.generate_bibliography(project.id, style=style, include_uncited=True)
        assert "Gear cutting" in bibliography.text, style


# 15-17. Documents français, russe, anglais (analyse des consignes) -----------------------------------------------------
@pytest.mark.parametrize(("language", "text"), [
    (Language.FR, "Questions\n1. Définir la vitesse angulaire.\n2. Calculer la vitesse du point B.\n"),
    (Language.RU, "Контрольные вопросы\n1. Что такое кинематическая пара?\n2. Как определить скорость точки B?\n"),
    (Language.EN, "Questions\n1. Define angular velocity.\n2. Compute the velocity of point B.\n"),
])
def test_s15_s17_multilingual_documents(services: Services, inbox: Path, language: Language, text: str) -> None:
    project = services.projects.create("Consignes", DocumentType.TD, language)
    _import(services, project.id, inbox, f"consignes-{language.value}.txt", text)
    analysis = services.writing.analyze_assignment(project.id)
    assert sum(r.kind == "question" for r in analysis.requirements) == 2


# 18. PDF avec tableaux et titres --------------------------------------------------------------------------------------------
def test_s18_pdf_with_tables(services: Services, inbox: Path) -> None:
    project = services.projects.create("PDF", DocumentType.RAPPORT_TECHNIQUE, Language.FR)
    doc = _doc_id(services.documents.import_document(project.id, str(make_text_pdf(inbox / "rapport.pdf")),
                                                     DocumentRole.SOURCE))
    tables = services.extraction.tables(doc).tables
    assert tables and tables[0].rows[0] == ["Paramètre", "Valeur"]
    exported = services.extraction.export_tables(doc, "csv")
    assert Path(exported.paths[0]).exists()


# 19. Document scanné (OCR avec indice de confiance) ---------------------------------------------------------------------
def test_s19_scanned_document(services: Services, inbox: Path) -> None:
    tessdata = Path(r"D:\AcademicWriter-Data\tessdata")
    if not (tessdata / "fra.traineddata").exists():
        pytest.skip("langues OCR absentes")
    services.settings.tessdata_dir = tessdata
    services.extraction._ocr = False  # nouvelle détection avec ce dossier de langues
    if services.extraction.ocr_engine() is None:
        pytest.skip("Tesseract absent")
    project = services.projects.create("Scan", DocumentType.TP, Language.FR)
    doc = _doc_id(services.documents.import_document(
        project.id, str(make_scanned_pdf(inbox / "scan.pdf", "Analyse cinématique du mécanisme")), DocumentRole.SOURCE))
    _, summary = services.extraction.extract(doc)
    assert summary.ocr_pages == [1] and summary.ocr_quality and summary.ocr_quality[0].mean_confidence is not None


# 20. Travail fondé exclusivement sur le cours -------------------------------------------------------------------------------
def test_s20_course_only_work(services: Services, inbox: Path) -> None:
    project = services.projects.create("TD cours", DocumentType.TD, Language.FR)
    _import(services, project.id, inbox, "consignes.txt", "Répondez uniquement à partir du cours.\nQuestions\n"
            "1. Quelle est la définition de la vitesse moyenne ?\n2. Expliquer le théorème de Bernoulli.\n")
    _import(services, project.id, inbox, "cours.txt", "La vitesse moyenne est le rapport de la distance parcourue "
            "à la durée du parcours.", DocumentRole.COURSE)
    services.writing.analyze_assignment(project.id)
    assert services.projects.get(project.id).source_policy == "course_only"
    coverage = services.course.course_coverage(project.id)
    assert coverage.not_covered >= 1 and coverage.covered >= 1


# 21-25. Présentations -------------------------------------------------------------------------------------------------------
def test_s21_presentation_from_topic(services: Services) -> None:
    project = services.projects.create("Exposé", DocumentType.EXPOSE, Language.FR)
    plan = services.presentations.plan(project.id, "expose", 10, topic="Énergies renouvelables")
    assert plan.slides[0].type == "title" and any("vérifiables" in w for w in plan.warnings)


def test_s22_presentation_from_thesis(services: Services, inbox: Path) -> None:
    project = services.projects.create("Soutenance", DocumentType.PRESENTATION_ORALE, Language.FR)
    doc = _import(services, project.id, inbox, "memoire.md", "# Introduction\n\nLes convoyeurs miniers tombent souvent "
                  "en panne.\n\n# Résultats\n\nLe MTBF passe de 120 h à 168 h.\n\n# Conclusion\n\nLe plan fonctionne.\n",
                  DocumentRole.DRAFT)
    plan = services.presentations.plan(project.id, "soutenance_master", 15, document_id=doc)
    assert any("168 h" in m for s in plan.slides for m in s.material)


def test_s23_scientific_presentation_with_chart(services: Services) -> None:
    from academic_writer.charts import Series

    project = services.projects.create("Conférence", DocumentType.COMMUNICATION_SCIENTIFIQUE, Language.EN)
    chart = services.charts.create(project.id, ChartSpec(chart_type="line", title="Velocity", x_label="t", x_unit="s",
                                                         y_label="v", y_unit="m/s", source="Measurements",
                                                         series=[Series(x=[0, 1, 2], y=[0.0, 1.5, 3.0])]))
    deck = Deck(title="Results", language="en", theme="scientifique", slides=[
        Slide(type="title"), Slide(type="chart", title="Velocity", chart_id=chart.chart_id, notes="Linear increase.")])
    result = services.presentations.create(project.id, deck, export_pdf=False, preview=False)
    assert any(shape.shape_type == 13 for shape in Presentation(result.pptx_path).slides[1].shapes)


def test_s24_technical_presentation_with_diagrams(services: Services) -> None:
    project = services.projects.create("Projet technique", DocumentType.PROJET_TECHNIQUE, Language.FR)
    deck = Deck(title="Réducteur", theme="industriel", title_info=TitleInfo(author="A. Auteur"), slides=[
        Slide(type="process", title="Démarche", steps=["Cahier des charges", "Calcul", "Vérification"], notes="Étapes."),
        Slide(type="comparison", title="Variantes", left_title="Engrenages droits", right_title="Hélicoïdaux",
              criteria=[Criterion(criterion="Bruit", left="Plus élevé", right="Plus faible")], notes="Choix."),
        Slide(type="key_figures", title="Résultats", figures=[KeyFigure(value="3", label="étapes", source="démarche")],
              notes="Chiffres.")])
    result = services.presentations.create(project.id, deck, export_pdf=False, preview=False)
    assert result.slide_count == 3 and not [c for c in result.checks if c.code in ("overlap", "out_of_slide")]


def test_s25_export_pptx_and_pdf(services: Services) -> None:
    from academic_writer.presentations.powerpoint import powerpoint_available

    if not powerpoint_available():
        pytest.skip("PowerPoint absent")
    project = services.projects.create("Export", DocumentType.PRESENTATION_ORALE, Language.FR)
    deck = Deck(title="Export", slides=[Slide(type="title"), Slide(type="questions")])
    result = services.presentations.create(project.id, deck, export_pdf=True, export_odp=True, preview=True)
    assert Path(result.pptx_path).exists() and result.pdf_path and Path(result.pdf_path).exists()
    assert result.odp_path and len(result.preview_paths) == 2
