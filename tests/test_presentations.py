"""Audit C-01 : module de présentations (plan, PPTX réel, contrôles de contenu, notes, références)."""

from pathlib import Path

import pytest
from mcp import Client
from pptx import Presentation

from academic_writer.charts import ChartSpec, Series
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.presentations.builder import fit_size
from academic_writer.presentations.models import Deck, KeyFigure, Slide, TitleInfo
from academic_writer.research.models import Person, SourceData
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

MEMOIRE = """Introduction

Le travail porte sur la maintenance des convoyeurs miniers. La disponibilité actuelle est de 82 %.

Méthodologie

Analyse des pannes sur 24 mois et calcul du MTBF.

Résultats

Le MTBF passe de 120 h à 168 h après la mise en place du plan préventif.

Conclusion

Le plan préventif améliore la disponibilité.
"""


@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("Mémoire maintenance", DocumentType.MEMOIRE_MASTER, Language.FR)
    path = inbox / "memoire.md"
    path.write_text(MEMOIRE.replace("\n\n", "\n\n").replace("Introduction\n", "# Introduction\n")
                    .replace("Méthodologie\n", "# Méthodologie\n").replace("Résultats\n", "# Résultats\n")
                    .replace("Conclusion\n", "# Conclusion\n"), encoding="utf-8")
    document = services.documents.import_document(project.id, str(path), DocumentRole.DRAFT)
    from types import SimpleNamespace

    return SimpleNamespace(id=project.id, document_id=document.document.id if hasattr(document, "document")
                           else document.id)


def test_plan_from_document_master_defense(services: Services, project) -> None:
    plan = services.presentations.plan(project.id, "soutenance_master", 15, document_id=project.document_id)
    types = [s.type for s in plan.slides]
    assert types[0] == "title" and types[-1] == "questions" and 10 <= plan.slide_count <= 16
    results = next(s for s in plan.slides if s.origin == "Résultats")
    assert any("168 h" in m for m in results.material)  # matière sourcée, telle qu'écrite
    assert sum(s.seconds for s in plan.slides) == pytest.approx(15 * 60, abs=15)
    assert any("aucun graphique" in w for w in plan.warnings)


def test_plan_from_topic_only_warns(services: Services) -> None:
    project = services.projects.create("Exposé", DocumentType.EXPOSE, Language.EN)
    plan = services.presentations.plan(project.id, "expose", 10, topic="Renewable energy storage")
    assert plan.slides[0].type == "title" and any("vérifiables" in w for w in plan.warnings)
    assert all(not s.material for s in plan.slides)


def _deck(chart_id: str | None = None) -> Deck:
    slides = [
        Slide(type="title"),
        Slide(type="bullets", title="Contexte", bullets=["Disponibilité actuelle : 82 %", "Pannes fréquentes"],
              notes="Je présente le contexte."),
        Slide(type="key_figures", title="Résultats", notes="Deux chiffres.",
              figures=[KeyFigure(value="168 h", label="MTBF après", source="Résultats"),
                       KeyFigure(value="95 %", label="Disponibilité visée")]),
        Slide(type="process", title="Démarche", steps=["Collecte", "Analyse", "Plan préventif"], notes="Trois étapes."),
        Slide(type="table", title="Avant / après", header=["Indicateur", "Avant", "Après"],
              rows=[["MTBF", "120 h", "168 h"]], source="Mémoire", notes="Tableau."),
        Slide(type="references"),
        Slide(type="questions"),
    ]
    if chart_id:
        slides.insert(3, Slide(type="chart", title="Évolution", chart_id=chart_id, bullets=["Hausse du MTBF"],
                               notes="Graphique."))
    return Deck(title="Maintenance des convoyeurs", language="fr", theme="technique", footer="Mémoire 2026",
                title_info=TitleInfo(institution="Université X", author="A. Auteur", event="Soutenance de Master"),
                slides=slides)


def test_create_presentation_real_pptx_with_checks(services: Services, project) -> None:
    services.sources.register(project.id, "book", SourceData(title="Maintenance industrielle", year=2019,
                                                             authors=[Person(family="Monchy", given="F.")],
                                                             publisher="Dunod"))
    chart = services.charts.create(project.id, ChartSpec(chart_type="bar", title="MTBF", x_label="Période",
                                                         y_label="MTBF", y_unit="h", source="Mémoire",
                                                         series=[Series(x=["Avant", "Après"], y=[120, 168])]))
    result = services.presentations.create(project.id, _deck(chart.chart_id), duration_minutes=6, export_pdf=False,
                                           preview=False)
    pptx = Presentation(result.pptx_path)
    assert len(pptx.slides) == 8 and result.slide_count == 8
    assert pptx.slides[1].notes_slide.notes_text_frame.text == "Je présente le contexte."
    assert any(shape.shape_type == 13 for shape in pptx.slides[3].shapes)  # graphique inséré (image)
    references = " ".join(sh.text_frame.text for sh in pptx.slides[6].shapes if sh.has_text_frame)
    assert "Monchy" in references  # diapositive des références remplie depuis le projet
    codes = {(c.slide, c.code) for c in result.checks}
    assert (3, "unsourced_number") in codes  # « 95 % » n'existe dans aucune source du projet
    assert (2, "unsourced_number") not in codes  # 82 % vient du mémoire
    assert (3, "figure_source") in codes
    assert result.errors >= 1


def test_overfull_slide_and_missing_figure_are_reported(services: Services, project) -> None:
    long = ["Une puce volontairement très longue qui décrit en détail tous les aspects du problème étudié " * 3] * 8
    deck = Deck(title="T", slides=[Slide(type="bullets", title="Trop", bullets=long, notes="x"),
                                   Slide(type="chart", title="Absent", chart_id="inexistant", notes="x")])
    result = services.presentations.create(project.id, deck, export_pdf=False, preview=False)
    codes = {c.code for c in result.checks}
    assert {"overfull", "too_many_bullets", "long_bullet", "missing_figure"} <= codes


def test_image_outside_project_refused(services: Services, project, tmp_path: Path) -> None:
    outside = tmp_path / "x.png"
    outside.write_bytes(b"\x89PNG")
    deck = Deck(title="T", slides=[Slide(type="image", title="I", image_path=str(outside), source="s")])
    with pytest.raises(ValidationFailed, match="hors du dossier"):
        services.presentations.create(project.id, deck, export_pdf=False, preview=False)


def test_fit_size_never_splits_words() -> None:
    assert fit_size(["Аналитическая проверка"], 1.2, 1.0, start=20, minimum=11, word_factor=0.68) is None
    size = fit_size(["Аналитическая проверка"], 2.4, 1.2, start=20, minimum=11, word_factor=0.68)
    assert size is not None and 13 * size * 0.68 / 72 <= 2.4


@pytest.mark.anyio
async def test_presentation_tools_exposed() -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert {"plan_presentation", "create_presentation"} <= names
