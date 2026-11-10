"""Audit C-02 : « réponds uniquement à partir des explications du professeur », profils d'enseignants."""

from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.core.teaching import Notation
from academic_writer.research.models import Person, SourceData
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

CONSIGNES = """TD 3 — Cinématique du point
Répondez uniquement à partir des explications données par le professeur dans le cours.
Questions
1. Comment calcule-t-on la vitesse moyenne d'un mobile ?
2. Quelle est la définition de l'accélération tangentielle ?
3. Expliquer le théorème de Bernoulli pour un fluide parfait.
"""
COURS = """Cours 2 — Cinématique
La vitesse moyenne d'un mobile est le rapport de la distance parcourue à la durée : v = s/t, où s est la distance (m).
L'accélération tangentielle mesure la variation de la norme de la vitesse : a = dv/dt.
Exemple : v = 15 m/s et t = 8 s.
"""
COURS_BIS = "Rappel du cours : t = 10 s pour l'exemple du mobile.\n"
EXTERNE = "Article externe : la vitesse moyenne se calcule aussi par intégration de la vitesse instantanée sur la durée."


@pytest.fixture
def course_project(services: Services, inbox: Path):
    project = services.projects.create("TD cinématique", DocumentType.TD, Language.FR)
    for name, text, role in (("consignes.txt", CONSIGNES, DocumentRole.INSTRUCTIONS),
                             ("cours2.txt", COURS, DocumentRole.COURSE),
                             ("rappel.txt", COURS_BIS, DocumentRole.COURSE),
                             ("article.txt", EXTERNE, DocumentRole.SOURCE)):
        path = inbox / name
        path.write_text(text, encoding="utf-8")
        services.documents.import_document(project.id, str(path), role)
    services.domains.assign(project.id, "physique", "fr")
    return project


def test_constraint_detected_and_policy_applied(services: Services, course_project) -> None:
    analysis = services.writing.analyze_assignment(course_project.id)
    constraints = [r for r in analysis.requirements if r.kind == "constraint"]
    assert constraints and constraints[0].value == "course_only"
    assert any("Politique appliquée : course_only" in w for w in analysis.warnings)
    assert services.projects.get(course_project.id).source_policy == "course_only"
    # une seconde analyse ne change rien et le confirme
    again = services.writing.analyze_assignment(course_project.id)
    assert any("respectée" in w for w in again.warnings)


def test_course_only_blocks_external_sources(services: Services, course_project) -> None:
    services.writing.analyze_assignment(course_project.id)
    with pytest.raises(ValidationFailed, match="uniquement à partir du cours"):
        services.sources.register(course_project.id, "book", SourceData(title="Physique", authors=[Person(family="X")],
                                                                        year=2020, publisher="P"))


def test_brief_uses_only_teacher_documents(services: Services, course_project) -> None:
    services.writing.analyze_assignment(course_project.id)
    outline = services.writing.create_outline(course_project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    section = next(s for s in outline.sections if "questions" in s.title.casefold())
    brief = services.writing.build_brief(course_project.id, section.id)
    assert "UNIQUEMENT à partir des documents de l'enseignant" in brief.system_prompt
    assert "[NON TRAITÉ DANS LE COURS" in brief.system_prompt
    assert "cours2.txt" in brief.brief and "article.txt" not in brief.brief  # document externe exclu
    assert "Sources citables" not in brief.brief
    revision = services.writing.save_section_draft(course_project.id, section.id,
                                                   "La vitesse moyenne est v = s/t [@dupont2020].")
    assert any(c.code == "external_source_forbidden" and c.severity == "error" for c in revision.checks)


def test_coverage_flags_unanswered_question_and_contradiction(services: Services, course_project) -> None:
    services.writing.analyze_assignment(course_project.id)
    coverage = services.course.course_coverage(course_project.id)
    by_text = {i.text.split("?")[0][-30:]: i for i in coverage.items}
    statuses = {i.text[:40]: i.status for i in coverage.items}
    bernoulli = next(i for i in coverage.items if "Bernoulli" in i.text)
    vitesse = next(i for i in coverage.items if "vitesse moyenne" in i.text)
    assert bernoulli.status == "not_covered" and not bernoulli.passages, statuses
    assert vitesse.status in ("covered", "partial") and vitesse.passages[0].document == "cours2.txt", by_text
    assert coverage.not_covered >= 1 and any("sans passage" in n for n in coverage.notices)
    contradiction = next(c for c in coverage.contradictions if c.symbol == "t")
    assert any("8 s" in v for v in contradiction.values) and any("10 s" in v for v in contradiction.values)


def test_teacher_profile_reused_in_brief(services: Services, course_project) -> None:
    profile = services.course.create_profile(
        "Mme Martin", subject="Mécanique", course="Cinématique L1", source_policy="course_only",
        notations=[Notation(symbol="v", meaning="vitesse moyenne", unit="m/s")],
        methods="Toujours écrire la formule littérale avant l'application numérique.")
    teaching = services.course.set_project_teaching(course_project.id, teacher_profile_id=profile.id)
    assert teaching.project.source_policy == "course_only" and teaching.teacher.name == "Mme Martin"
    services.writing.analyze_assignment(course_project.id)
    outline = services.writing.create_outline(course_project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    brief = services.writing.build_brief(course_project.id, outline.sections[0].id)
    assert "Notation : v = vitesse moyenne [m/s]" in brief.brief
    assert "formule littérale avant l'application numérique" in brief.brief
    updated = services.course.update_profile(profile.id, {"expectations": "Barème : 2 points par question."})
    assert updated.methods.startswith("Toujours") and updated.expectations.startswith("Barème")
    assert services.course.list_profiles().count == 1


def test_external_allowed_policy_rules(services: Services, course_project) -> None:
    services.course.set_project_teaching(course_project.id, source_policy="external_allowed")
    services.writing.analyze_assignment(course_project.id)  # la consigne course_only ne remplace pas le choix
    project = services.projects.get(course_project.id)
    assert project.source_policy == "external_allowed"
    outline = services.writing.create_outline(course_project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    brief = services.writing.build_brief(course_project.id, outline.sections[0].id)
    assert "jamais être présenté comme venant du cours" in brief.system_prompt


def test_course_notations_extracted(services: Services, course_project) -> None:
    proposals = {p.symbol: p for p in services.course.extract_notations(course_project.id).proposals}
    assert proposals["s"].meaning.startswith("la distance") and proposals["s"].unit == "m"


@pytest.mark.anyio
async def test_course_tools_exposed() -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert {"create_teacher_profile", "list_teacher_profiles", "update_teacher_profile", "set_project_teaching",
            "check_course_coverage", "extract_course_notations"} <= names


def test_structured_teacher_profile_in_brief(services: Services, course_project) -> None:
    """G3 : définitions, structure, style, règles et barème du profil transmis au rédacteur."""
    from academic_writer.core.teaching import Criterion, TermDefinition

    profile = services.course.create_profile(
        "M. Durand", subject="Mécanique", source_policy="course_only",
        details={"definitions": [TermDefinition(term="vitesse moyenne", definition="rapport distance / durée",
                                                source="cours2.txt")],
                 "expected_structure": ["Données", "Formule littérale", "Application numérique", "Conclusion"],
                 "writing_style": "phrases courtes, unités SI", "bibliography_rules": "aucune source externe",
                 "evaluation_criteria": [Criterion(criterion="Exactitude des calculs", points=6)],
                 "work_types": ["td"]})
    assert profile.definitions[0].term == "vitesse moyenne" and profile.evaluation_criteria[0].points == 6
    services.course.set_project_teaching(course_project.id, teacher_profile_id=profile.id)
    services.writing.analyze_assignment(course_project.id)
    outline = services.writing.create_outline(course_project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    brief = services.writing.build_brief(course_project.id, outline.sections[0].id).brief
    for expected in ("Définition du cours : vitesse moyenne — rapport distance / durée [cours2.txt]",
                     "Structure attendue : Données → Formule littérale", "Style attendu : phrases courtes",
                     "Critères d'évaluation : Exactitude des calculs (6 pts)"):
        assert expected in brief
    updated = services.course.update_profile(profile.id, {"detail_level": "détaillé"})
    assert updated.detail_level == "détaillé" and updated.definitions  # les autres champs sont conservés
    with pytest.raises(ValidationFailed, match="inconnus"):
        services.course.create_profile("X", details={"couleur": "bleu"})


def test_extract_rubric_and_definitions(services: Services, inbox: Path) -> None:
    project = services.projects.create("TP", DocumentType.TP, Language.RU)
    rubric = inbox / "bareme.txt"
    rubric.write_text("Критерии оценки\n- Правильность расчётов (6 баллов)\n- Оформление отчёта – 2 балла\n"
                      "- Ответы на вопросы: 2 балла\n", encoding="utf-8")
    course = inbox / "lecture.txt"
    course.write_text("Кинематическая пара — это соединение двух звеньев, допускающее их относительное движение. "
                      "Подвижное соединение звеньев называется шарниром.", encoding="utf-8")
    services.documents.import_document(project.id, str(rubric), DocumentRole.RUBRIC)
    services.documents.import_document(project.id, str(course), DocumentRole.COURSE)
    material = services.course.extract_teacher_material(project.id)
    assert [(c.criterion, c.points) for c in material.criteria] == [
        ("Правильность расчётов", 6.0), ("Оформление отчёта", 2.0), ("Ответы на вопросы", 2.0)]
    assert material.total_points == 10.0
    terms = {d.term: d for d in material.definitions}
    assert terms["Кинематическая пара"].definition.startswith("соединение двух звеньев")
    assert terms["шарниром"].document == "lecture.txt"
