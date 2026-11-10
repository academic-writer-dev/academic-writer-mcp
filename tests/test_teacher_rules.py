"""Consignes du professeur (mise en forme, plan, longueur) et normes internationales de présentation."""

from pathlib import Path

import pytest

from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.quality.academic_norms import check_norms
from academic_writer.quality.models import Segment, Target
from academic_writer.server.services import Services
from academic_writer.writing.format_instructions import overrides, parse_format

CONSIGNES = """Mémoire de master — consignes de rédaction
Le mémoire comprendra 40 à 60 pages.
Le texte sera rédigé en Arial 11, interligne double, texte justifié.
Marges : gauche 3 cm, droite 2 cm, haut 2 cm, bas 2 cm.
Les références seront présentées selon la norme APA.
Le document sera remis au format PDF.
"""


@pytest.mark.parametrize(("sentence", "expected"), [
    ("Times New Roman 12, interligne 1,5, texte justifié, marges de 2,5 cm.",
     ["font=Times New Roman", "size_pt=12", "line_spacing=1.5", "margins_mm=top:25,bottom:25,left:25,right:25",
      "align=justify"]),
    ("Шрифт Times New Roman, кегль 14, полуторный межстрочный интервал, выравнивание по ширине.",
     ["font=Times New Roman", "size_pt=14", "line_spacing=1.5", "align=justify"]),
    ("Поля: левое — 30 мм, правое — 15 мм, верхнее и нижнее — 20 мм. Абзацный отступ 1,25 см.",
     ["margins_mm=left:30,right:15,top:20,bottom:20", "first_line_indent_cm=1.25"]),
    ("Нумерация страниц — арабскими цифрами в центре нижней части листа.", ["page_numbers=bottom_center"]),
    ("Список литературы оформляется по ГОСТ Р 7.0.5-2008.", ["citation_style=gost"]),
    ("Use APA 7 for references; double-spaced, 1-inch margins, Arial 11 pt. Submit as a PDF file.",
     ["font=Arial", "size_pt=11", "line_spacing=2", "margins_mm=top:25.4,bottom:25.4,left:25.4,right:25.4",
      "citation_style=apa", "file_format=pdf"]),
    ("Les tableaux en taille 10 pt, le texte en 12 pt.", ["size_pt=12"]),  # la taille des tableaux est ignorée
])
def test_parse_format(sentence: str, expected: list[str]) -> None:
    assert parse_format(sentence) == expected


def test_overrides_last_rule_wins_and_margins_merge() -> None:
    update, applied = overrides(["size_pt=12", "margins_mm=left:30", "size_pt=14", "citation_style=apa", "x"])
    assert update == {"size_pt": 14.0, "margins_mm": {"left": 30.0}}
    assert "taille (pt) : 14" in applied and "style des références : apa" in applied


@pytest.fixture
def master_project(services: Services, inbox: Path):
    project = services.projects.create("Mémoire engrenages", DocumentType.MEMOIRE_MASTER, Language.FR)
    path = inbox / "consignes.txt"
    path.write_text(CONSIGNES, encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    services.domains.assign(project.id, "genie_mecanique", "fr")
    services.writing.analyze_assignment(project.id)
    return project


def test_teacher_format_rules_are_applied(services: Services, master_project) -> None:
    preset = services.formatting.preset(None, master_project.id)
    assert preset.id.endswith("-consignes")
    assert (preset.font, preset.size_pt, preset.line_spacing, preset.align) == ("Arial", 11.0, 2.0, "justify")
    assert preset.margins_mm == {"top": 20.0, "bottom": 20.0, "left": 30.0, "right": 20.0}
    settings = services.formatting.teacher_settings(master_project.id)
    assert "citation_style=apa" in settings and "file_format=pdf" in settings


def test_rejected_rule_is_not_applied(services: Services, master_project) -> None:
    requirements = services.writing.list_requirements(master_project.id, kind="format").requirements
    font = next(r for r in requirements if r.value and r.value.startswith("font=Arial"))
    services.writing.manage_requirement(master_project.id, "reject", requirement_id=font.id)
    assert services.formatting.preset(None, master_project.id).font != "Arial"


def test_teacher_profile_structure_and_layout(services: Services, master_project) -> None:
    profile = services.course.create_profile(
        "Pr Martin", details={"expected_structure": ["Introduction générale", "1. État de l'art",
                                                     "2. Modélisation de l'engrenage", "Conclusion générale",
                                                     "Bibliographie"],
                              "layout_rules": "Times New Roman 12. Numéros de page en bas à droite."})
    services.course.set_project_teaching(master_project.id, teacher_profile_id=profile.id)
    outline = services.writing.create_outline(master_project.id)
    titles = [s.title for s in outline.sections]
    assert titles == ["Introduction générale", "État de l'art", "Modélisation de l'engrenage", "Conclusion générale",
                      "Bibliographie"]
    assert [s.section_key for s in outline.sections][0] == "introduction"
    preset = services.formatting.preset(None, master_project.id)
    # les consignes du travail (Arial 11) priment sur le profil (Times 12) ; le profil complète (pagination)
    assert (preset.font, preset.size_pt, preset.page_numbers) == ("Arial", 11.0, "bottom_right")


def test_norms_checker_on_sample() -> None:
    s = Segment
    segments = [s("Page de titre", "heading", "x"), s("Résumé", "heading", "Résumé"),
                s(" ".join(["mot"] * 620), "paragraph", "Résumé"), s("Sommaire", "heading", "s"),
                s("1 Introduction", "heading", "1"),
                s("La contrainte vaut 250MPa et la masse 12 Kg ; le CND est utilisé. Le CND permet…", "paragraph", "1"),
                s("1.1 Contexte", "heading", "1.1"), s("1.3 Objectifs", "heading", "1.3"), s("2. Méthode", "heading", "2"),
                s("Figure 1 – Schéma", "caption", "2"), s("Figure 3 – Courbe", "caption", "2"),
                s("Voir la figure 1. Essai du 03/04/2024.", "paragraph", "2"), s("Conclusion", "heading", "c"),
                s("Bibliographie", "heading", "b")]
    report = check_norms(Target("test", "p", "fr", segments), "memoire_master")
    codes = {i.code for i in report.issues}
    assert {"norm_missing_element", "norm_bilingual_abstract", "norm_abstract_long", "norm_heading_sequence",
            "norm_heading_style", "norm_caption_gap", "norm_caption_not_called", "norm_unit_space",
            "norm_unit_symbol", "norm_date_ambiguous", "norm_acronym_undefined"} <= codes
    assert not any("figure 1A" in i.message for i in report.issues)


def test_clean_document_passes() -> None:
    s = Segment
    segments = [s("Objectif du TP", "heading", "o"), s("Mesurer la vitesse d'un mobile.", "paragraph", "o"),
                s("Matériel et méthode", "heading", "m"), s("Chronomètre, règle de 2 m.", "paragraph", "m"),
                s("Résultats", "heading", "r"), s("La vitesse vaut 1,5 m/s (voir figure 1).", "paragraph", "r"),
                s("Figure 1 – Position en fonction du temps", "caption", "r"), s("Analyse", "heading", "a"),
                s("Écart de 3 % avec la valeur attendue.", "paragraph", "a"), s("Conclusion", "heading", "c"),
                s("Objectif atteint.", "paragraph", "c")]
    report = check_norms(Target("tp", "p", "fr", segments), "tp")
    assert not report.issues and all(c.status == "conforme" for c in report.checks)


def test_research_dossier(services: Services, master_project, monkeypatch) -> None:
    from academic_writer.research.discovery import DiscoveredWork, DiscoveryResult
    from academic_writer.research.models import SourceData

    asked = []

    def discover(query, kind="all", limit=10, project_id=None, **_):
        asked.append(query)
        work = DiscoveredWork(item_id="crossref:10.1/gear", service="crossref", title="Gear tooth bending fatigue",
                              authors=["A. Kahraman"], year=2020, source_type="article", doi="10.1/gear",
                              landing_url="https://doi.org/10.1/gear", open_access=False, relevance=1.0,
                              data=SourceData(title="Gear tooth bending fatigue"))
        return DiscoveryResult(query=query, services=["crossref"], count=1, works=[work],
                               notices=["Domaine reconnu : Génie mécanique — sources spécialisées ajoutées"])

    monkeypatch.setattr(services.sources, "discover", discover)
    dossier = services.dossier.build(master_project.id, "fatigue des engrenages", ["gear fatigue", "gear fatigue"])
    assert asked == ["fatigue des engrenages", "gear fatigue"]  # formulations dédoublonnées
    assert len(dossier.sources) == 1 and dossier.domain == "Génie mécanique"
    assert any(rule.startswith("Mise en forme imposée") and "Arial" in rule for rule in dossier.teacher_rules)
    assert any(rule == "Style des références imposé — apa" for rule in dossier.teacher_rules)
    assert any(n.startswith("ISO 7144") for n in dossier.norms)
    assert sum(n.startswith("ISO 690 ") for n in dossier.norms) == 1
    assert dossier.docx_path and Path(dossier.docx_path).exists() and Path(dossier.markdown_path).exists()
    text = Path(dossier.markdown_path).read_text(encoding="utf-8")
    assert "Gear tooth bending fatigue" in text and "Déclaration d'utilisation" in text
