"""Tests de la rédaction encadrée : exigences, plan, rédaction, contrôles, révisions."""

from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.core.writing import OutlineOperation
from academic_writer.domains.registry import DomainRegistry
from academic_writer.providers.base import ProviderError
from academic_writer.providers.manager import ProviderManager
from academic_writer.providers.mock import MockProvider
from academic_writer.server.app import mcp
from academic_writer.server.services import Services
from academic_writer.writing.checks import check_draft, check_fidelity, numbers_in
from academic_writer.writing.requirements import classify

CONSIGNES_RU = """Домашнее задание 1. Вариант 9.
Структурный и кинематический анализ механизма.
Исходные данные: n1 = 52 об/мин, lOA = 0,1 м.
1. Определить степень подвижности механизма.
2. Построить план скоростей и план ускорений.
3. Рассчитать ускорение Кориолиса.
Пояснительная записка объёмом 10-12 страниц оформляется по ГОСТ 7.32-2017 и ГОСТ 2.105-2019.
Шрифт Times New Roman, 14 пт, интервал 1,5.
Записка должна содержать введение, заключение и список использованных источников.
Срок сдачи: до 15.12.2026."""


@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("ДЗ1 ТММ", DocumentType.DEVOIR, Language.RU)
    path = inbox / "zadanie.txt"
    path.write_text(CONSIGNES_RU, encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    services.domains.assign(project.id, "genie_mecanique", "ru")
    return project


@pytest.fixture
def mock(services: Services) -> MockProvider:
    provider = MockProvider()
    services.ai = ProviderManager(services.db, services.settings, services.projects,
                                  factory=lambda name: provider, ollama_probe=lambda: ["qwen3.5:4b"])
    services.writing.ai = services.ai
    return provider


def _approved_outline(services: Services, project):
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    return services.writing.validate_outline(outline.id, approve=True, force=True).outline


# --- non-régression : vraies consignes « ЛР4 ТММ » (structure extraite du PDF réel) -------------

def _lr4_document():
    from academic_writer.document.model import Block, ExtractedDocument
    items = [
        ("paragraph", "Лабораторная работа №4. «Нарезание эвольвентных зубчатых колес инструментом реечного типа» "
                      "Цель работы Ознакомление студентов с процессом нарезания на станке методом обката прямозубых колес."),
        ("paragraph", "Последовательность выполнения лабораторной работы"),
        ("list_item", "1. Изучить конструкцию макета."),
        ("list_item", "2. Установить на диске 9 бумажный кружок 10. Для этого следует отвернуть винт 14 и снять шайбу 13. "
                      "Бумажный кружок положить на плоскость диска и наколоть на штифты."),
        ("list_item", "3. Разомкнуть кинематическую связь каретки 2 и диска 9. При этом следует повернуть рычаг 16 на 180˚;"),
        ("list_item", "7. Установить рейку в требуемом положении (0, + х · m, – х · m). Причем положительным является "
                      "смещение рейки при ее движении от центра заготовки."),
        ("paragraph", "Для установки рейки необходимо немного отвернуть винты 7, сместить ее на требуемую величину и вновь "
                      "завернуть эти винты."),
        ("list_item", "8. Спрофилировать по 2-3 зуба без смещения рейки, с положительным и отрицательным смещением."),
        ("list_item", "9. Рассчитать основные геометрические параметры для трех модификаций зубчатого колеса."),
        ("list_item", "10. Отметить рассчитанные величины на рабочем рисунке."),
        ("list_item", "11. Подготовить отчет по лабораторной работе."),
        ("paragraph", "Вопросы для защиты лабораторной работы"),
        ("list_item", "1. Что такое зубчатое колесо?"),
        ("list_item", "5. Дайте определение окружностям: r, rb, ra, rf."),
        ("list_item", "7. Назовите основные параметры инструментальной рейки."),
    ]
    return ExtractedDocument(format="pdf", extractor="test",
                             blocks=[Block(type=kind, text=text, page=1) for kind, text in items])


def test_lr4_structural_extraction() -> None:
    from academic_writer.writing.requirements import extract_candidates, missing_symbols
    candidates = extract_candidates(_lr4_document())
    by_kind = {}
    for candidate in candidates:
        by_kind.setdefault(candidate.kind, []).append(candidate)
    assert [c.number for c in by_kind["step"]] == ["1", "2", "3", "7", "8"]  # étapes 2 et 7 présentes
    step7 = next(c for c in by_kind["step"] if c.number == "7")
    assert "Для установки рейки" in step7.text  # paragraphe de continuation rattaché
    assert [c.number for c in by_kind["task"]] == ["9", "10"]  # livrables : calcul et rabattement sur le dessin
    assert "Подготовить отчет" in by_kind["other"][0].text
    assert [c.number for c in by_kind["question"]] == ["1", "5", "7"]
    assert all(c.group_label.startswith("Вопросы") for c in by_kind["question"])
    assert by_kind["objective"][0].text.startswith("Ознакомление студентов")
    actions = [c.text for c in candidates if c.kind in ("task", "step", "objective")]
    assert missing_symbols(actions, "") == ["x", "m"]  # r, rb, ra, rf (questions = résultats) exclus


def test_lr4_outline_has_no_duplicates(settings) -> None:
    from academic_writer.domains.structures import build_template
    from academic_writer.writing.models import Requirement
    from academic_writer.writing.outline import build_sections
    from academic_writer.writing.requirements import extract_candidates
    reqs = [Requirement(id=f"r{i}", project_id="p", kind=c.kind, text=c.text, status="proposed", origin="extracted")
            for i, c in enumerate(extract_candidates(_lr4_document()))]
    template = build_template(DocumentType.RAPPORT_LABORATOIRE, "ru", DomainRegistry(settings).get("genie_mecanique"), "ru")
    sections, _, _ = build_sections(template, reqs, "ru", None)
    titles = [s.title for s in sections]
    assert [t for t in titles if t.startswith("Задача")] == [
        "Задача 1. Рассчитать основные геометрические параметры для трех модификаций зубчатого колеса",
        "Задача 2. Отметить рассчитанные величины на рабочем рисунке"]
    assert not any("…" in t for t in titles)
    assert titles.count("Ответы на контрольные вопросы") == 1
    procedure = next(s for s in sections if s.section_key == "procedure")
    assert len(procedure.requirement_ids) == 5
    assert "Обработка результатов" in titles and not any("погрешност" in t for t in titles)
    assert not next(s for s in sections if s.section_key == "measurements").required


def test_gear_inputs_from_profile(services: Services, inbox: Path) -> None:
    """z est une donnée d'entrée même absente du texte ; α, ha*, c* proposés par défaut avec leur norme."""
    project = services.projects.create("ЛР4", DocumentType.RAPPORT_LABORATOIRE, Language.RU)
    services.domains.assign(project.id, "genie_mecanique", "ru")
    path = inbox / "lr4.txt"
    path.write_text("Нарезание эвольвентных зубчатых колес.\n\nПоследовательность выполнения\n\n"
                    "7. Установить рейку в положение (0, + х · m).\n\n9. Рассчитать параметры колеса.\n\n"
                    "Вопросы для защиты\n\n5. Дайте определение окружностям: r, rb, ra, rf.", encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    analysis = services.writing.analyze_assignment(project.id)
    assert analysis.missing_data == ["m", "z", "x"]
    defaults = {s.symbol: (s.default, s.standard) for s in analysis.suggested_inputs if s.status == "default_proposed"}
    assert defaults["α"][0] == "20" and defaults["ha*"][0] == "1" and defaults["c*"][0] == "0,25"
    assert all("ГОСТ 13755-2015" in std for _, std in defaults.values())
    services.writing.manage_requirement(project.id, "add", text="m = 2 мм; z = 20", kind="data", value="m = 2; z = 20")
    again = services.writing.analyze_assignment(project.id)
    assert again.missing_data == ["x"]  # m et z fournis par l'utilisateur


def test_profile_default_requires_standard() -> None:
    from pydantic import ValidationError

    from academic_writer.domains.model import CalcInput
    with pytest.raises(ValidationError):
        CalcInput(symbol="α", name={"fr": "angle"}, default="20")


def test_lr4_analysis_reports_missing_data(services: Services, inbox: Path) -> None:
    project = services.projects.create("ЛР4", DocumentType.RAPPORT_LABORATOIRE, Language.RU)
    path = inbox / "lr4.txt"
    path.write_text("Последовательность выполнения\n\n9. Рассчитать параметры колеса при смещении (0, + х · m).",
                    encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    analysis = services.writing.analyze_assignment(project.id)
    assert analysis.missing_data == ["x", "m"]
    assert any("aucune valeur numérique" in w for w in analysis.warnings)


# --- extraction des exigences -------------------------------------------------

def test_classify_multilingual() -> None:
    assert ("task", None) in classify("2. Построить план скоростей и план ускорений.")
    assert ("task", None) in classify("Calculer la vitesse angulaire de la manivelle.")
    assert ("length", "10-12 страниц") in classify("Объём 10-12 страниц.")
    assert ("length", "5000 words") in classify("The report must not exceed 5000 words.")
    assert ("variant", "9") in classify("Вариант 9.")
    assert ("deadline", "15.12.2026") in classify("Срок сдачи: до 15.12.2026.")
    kinds = dict(classify("Mise en page : police Times New Roman 12 pt, selon la norme NF Z 41-006."))
    assert "format" in kinds and "NF Z 41-006" in kinds["norm"]
    assert dict(classify("n1 = 52 об/мин, lOA = 0,1 м"))["data"].startswith("n1 = 52 об/мин")
    assert ("structure", None) in classify("Le rapport comporte une introduction et une conclusion.")


def test_analyze_assignment(services: Services, project) -> None:
    analysis = services.writing.analyze_assignment(project.id)
    assert analysis.analyzed_documents == ["zadanie.txt"]
    assert analysis.variant == "9" and analysis.length == "10-12 страниц"
    assert "ГОСТ 7.32-2017" in analysis.norms and "ГОСТ 2.105-2019" in analysis.norms
    assert analysis.deadlines == ["15.12.2026"]
    tasks = [r for r in analysis.requirements if r.kind == "task"]
    assert len(tasks) >= 3 and all(r.source_filename == "zadanie.txt" and r.status == "proposed" for r in tasks)
    assert analysis.by_kind.get("format") and analysis.by_kind.get("structure") and analysis.by_kind.get("data")


def test_reanalysis_keeps_user_decisions(services: Services, project) -> None:
    first = services.writing.analyze_assignment(project.id)
    task = next(r for r in first.requirements if r.kind == "task")
    services.writing.manage_requirement(project.id, "reject", task.id)
    second = services.writing.analyze_assignment(project.id)
    same = [r for r in second.requirements if r.text == task.text and r.kind == "task"]
    assert len(same) == 1 and same[0].status == "rejected"


def test_manage_requirement(services: Services, project) -> None:
    added = services.writing.manage_requirement(project.id, "add", text="Inclure un schéma cinématique.", kind="task")
    assert added.origin == "user" and added.status == "confirmed"
    edited = services.writing.manage_requirement(project.id, "edit", added.id, text="Inclure le schéma à l'échelle.")
    assert edited.text == "Inclure le schéma à l'échelle."
    with pytest.raises(ValidationFailed):
        services.writing.manage_requirement(project.id, "add", text="x", kind="inconnu")
    with pytest.raises(NotFoundError):
        services.writing.manage_requirement(project.id, "confirm", "0" * 32)


def test_analyze_requires_instructions(services: Services) -> None:
    project = services.projects.create("Vide", DocumentType.TD, Language.FR)
    with pytest.raises(ValidationFailed):
        services.writing.analyze_assignment(project.id)


# --- plan -------------------------------------------------------------------------

def test_outline_from_template_and_tasks(services: Services, project) -> None:
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    assert outline.status == "draft" and outline.convention == "ru" and outline.domain_id == "genie_mecanique"
    assert outline.target_words == 11 * 300  # 10-12 pages → 11 × 300 mots
    titles = [s.title for s in outline.sections]
    solution = titles.index("Решение")
    tasks = [s for s in outline.sections if s.origin == "requirement"]
    assert len(tasks) >= 3 and all(s.level == 2 for s in tasks)
    assert titles[solution + 1].startswith("Задача 1.")
    assert any(s.section_key == "diagram" for s in outline.sections)  # section du profil génie mécanique
    assert outline.global_requirement_ids  # longueur, normes, format, variante, échéance


def test_validation_detects_uncovered_requirement(services: Services, project) -> None:
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    extra = services.writing.manage_requirement(project.id, "add", text="Comparer avec une méthode analytique.",
                                                kind="task")
    report = services.writing.validate_outline(outline.id, approve=True)
    assert not report.approved and any(i.requirement_id == extra.id for i in report.issues)
    task_section = next(s for s in outline.sections if s.origin == "requirement")
    services.writing.edit_outline(outline.id, [OutlineOperation(
        op="add", title="Comparaison analytique", level=2, after_section_id=task_section.id,
        requirement_ids=[extra.id])])
    report = services.writing.validate_outline(outline.id, approve=True)
    assert report.approved and report.outline.status == "approved"


def test_edit_outline_operations_and_reapproval(services: Services, project) -> None:
    outline = _approved_outline(services, project)
    first, second = outline.sections[0], outline.sections[1]
    edited = services.writing.edit_outline(outline.id, [
        OutlineOperation(op="rename", section_id=first.id, title="Титульный лист (форма кафедры)"),
        OutlineOperation(op="move", section_id=first.id, after_section_id=second.id),
        OutlineOperation(op="set", section_id=second.id, target_words=250),
    ])
    assert edited.status == "draft"  # modification → revalidation nécessaire
    assert edited.sections[0].id == second.id and edited.sections[0].target_words == 250
    assert edited.sections[1].title == "Титульный лист (форма кафедры)"
    with pytest.raises(NotFoundError):
        services.writing.edit_outline(outline.id, [OutlineOperation(op="remove", section_id="0" * 32)])


def test_new_outline_supersedes_previous(services: Services, project) -> None:
    services.writing.analyze_assignment(project.id)
    first = services.writing.create_outline(project.id)
    second = services.writing.create_outline(project.id, target_words=2000)
    assert services.writing.get_outline(first.id).status == "superseded"
    assert services.writing.current_outline(project.id).id == second.id and second.version == 2
    with pytest.raises(ValidationFailed):
        services.writing.validate_outline(first.id, approve=True)


# --- rédaction ----------------------------------------------------------------------

def test_writing_requires_approved_outline(services: Services, project, mock: MockProvider) -> None:
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    with pytest.raises(ValidationFailed):
        services.writing.write_section(project.id, outline.sections[1].id)


def test_assistant_engine_returns_brief(services: Services, project) -> None:
    outline = _approved_outline(services, project)
    task = next(s for s in outline.sections if s.origin == "requirement")
    result = services.writing.write_section(project.id, task.id, engine="assistant")
    assert result.engine == "assistant" and result.revision is None
    brief = result.brief
    assert "N'invente JAMAIS" in brief.system_prompt and "русский" in brief.system_prompt
    assert task.title in brief.brief
    assert "n1 = 52" in brief.brief  # données des consignes transmises au rédacteur
    assert "<source" in brief.brief and "ГОСТ 7.32-2017" in brief.brief
    assert "save_section_draft" in result.next_step


def test_local_engine_generates_proposed_revision(services: Services, project, mock: MockProvider) -> None:
    outline = _approved_outline(services, project)
    section = next(s for s in outline.sections if s.origin == "requirement")
    mock.responses.append(f"## {section.title}\nСтепень подвижности W = 3·5 − 2·7 = 1, при n1 = 52 об/мин "
                          "и угловой скорости 7,777 рад/с.")
    result = services.writing.write_section(project.id, section.id)
    assert result.engine == "ollama"  # auto : modèle local disponible, pas de cloud autorisé
    revision = result.revision
    assert revision.status == "proposed" and revision.engine == "mock" and revision.kind == "draft"
    assert not revision.text.startswith("##")  # titre répété retiré
    unsourced = next(c for c in revision.checks if c.code == "unsourced_numbers")
    assert "7.777" in unsourced.details and "52" not in unsourced.details
    request = mock.requests[-1]
    assert "Задача" in request.prompt and request.task == "section_draft"
    assert services.writing.current_outline(project.id).sections[[s.id for s in outline.sections].index(section.id)].status == "drafted"


def test_review_and_rewrite_with_fidelity(services: Services, project, mock: MockProvider) -> None:
    outline = _approved_outline(services, project)
    section = next(s for s in outline.sections if s.origin == "requirement")
    mock.responses.append("Скорость точки B определяется методом планов при n1 = 52 об/мин.")
    draft = services.writing.write_section(project.id, section.id).revision
    accepted = services.writing.review_revision(draft.id, "accept", "ok")
    assert accepted.status == "accepted"
    mock.responses.append("Скорость точки B определяется методом Планшера при n1 = 53 об/мин.")
    rewrite = services.writing.rewrite_section(project.id, section.id, "Сделать текст более формальным").revision
    assert rewrite.parent_revision_id == draft.id and rewrite.kind == "rewrite"
    codes = {c.code: c for c in rewrite.checks}
    assert "fidelity_numbers" in codes and codes["fidelity_numbers"].severity == "error"
    assert "Планшера" in codes["fidelity_new_names"].details  # l'invention réelle observée avec le modèle local
    rejected = services.writing.review_revision(rewrite.id, "reject", "invention")
    assert rejected.status == "rejected"
    assert services.writing.get_revision(draft.id).status == "accepted"  # la version validée reste en place
    with pytest.raises(ValidationFailed):
        services.writing.review_revision(rewrite.id, "accept")


def test_accepting_new_version_supersedes_old(services: Services, project, mock: MockProvider) -> None:
    outline = _approved_outline(services, project)
    section = next(s for s in outline.sections if s.origin == "requirement")
    first = services.writing.save_section_draft(project.id, section.id, "Первая версия текста.")
    services.writing.review_revision(first.id, "accept")
    second = services.writing.save_section_draft(project.id, section.id, "Вторая версия текста.",
                                                 kind="rewrite", parent_revision_id=first.id)
    services.writing.review_revision(second.id, "accept")
    assert services.writing.get_revision(first.id).status == "superseded"
    status = services.writing.draft_status(project.id)
    entry = next(s for s in status.sections if s.section_id == section.id)
    assert entry.accepted_revision_id == second.id and entry.status == "validated"
    assert status.accepted_words == 3


def test_cloud_engine_requires_consent(services: Services, project, mock: MockProvider) -> None:
    outline = _approved_outline(services, project)
    section = next(s for s in outline.sections if s.origin == "requirement")
    with pytest.raises(ProviderError):
        services.writing.write_section(project.id, section.id, engine="anthropic")
    assert mock.requests == []


# --- contrôles ---------------------------------------------------------------------

def test_numbers_normalization() -> None:
    assert numbers_in("ω = 5,445 рад/с ; n = 52 ; k = 7 ; 0,50 м") == {"5.445", "52", "0.5"}


def test_check_draft_rules(settings) -> None:
    profile = DomainRegistry(settings).get("genie_mecanique")
    checks = {c.code: c for c in check_draft(
        "La vitesse de rotation vaut 12,5 tr/min [3]. [À COMPLÉTER : masse de la bielle]",
        language="fr", target_words=100, sources_text="", profile=profile)}
    assert checks["length"].severity == "warning"
    assert checks["avoided_terms"].details and "fréquence de rotation" in checks["avoided_terms"].details[0]
    assert "12.5" in checks["unsourced_numbers"].details
    assert checks["unverified_citations"].details == ["[3]"]
    assert checks["placeholders"].severity == "info"
    russian = {c.code for c in check_draft("Hello world in English", language="ru", target_words=None,
                                           sources_text="", profile=profile)}
    assert "language" in russian


def test_check_draft_catches_real_local_model_errors(settings) -> None:
    """Erreurs réellement observées avec qwen3.5:4b sur le ДЗ1 : attribution inventée et mots anglais."""
    profile = DomainRegistry(settings).get("genie_mecanique")
    text = ("Расчет осуществляется на основе уравнения Григорьяна для плоских механизмов: $W = 3N - 2P_h$. "
            "Варианты конструкции (шатунно-ползунный mechanism) различаются; ускорение Кориолиса учитывается.")
    checks = {c.code: c for c in check_draft(text, language="ru", target_words=None,
                                             sources_text="Рассчитать ускорение Кориолиса.", profile=profile)}
    assert checks["unsourced_names"].details == ["Григорьяна"]  # Кориолиса figure dans les sources
    assert checks["mixed_language"].details == ["mechanism"]  # les formules $…$ sont ignorées


def test_generated_bibliography_and_names_noise(settings) -> None:
    """2e essai réel : bibliographie inventée en fin de section, faux positif après « *Примечание:* »."""
    profile = DomainRegistry(settings).get("genie_mecanique")
    text = ("*Примечание:* Данная классификация является гипотетической.\n\n"
            "### Список использованных источников\n\n"
            "1. Государственный стандарт ГОСТ 7.32-2017 «Библиографическая ссылка».\n"
            "2. Госстандарт СССР ГОСТ 2.105–2019 (обновленный).\n")
    checks = {c.code: c for c in check_draft(text, language="ru", target_words=None, sources_text="", profile=profile)}
    assert checks["generated_bibliography"].severity == "error" and len(checks["generated_bibliography"].details) == 2
    assert "Данная" not in checks.get("unsourced_names", type("x", (), {"details": []})()).details
    allowed = {c.code for c in check_draft(text, language="ru", target_words=None, sources_text="", profile=profile,
                                           is_references_section=True)}
    assert "generated_bibliography" not in allowed


def test_brief_includes_reference_definitions(services: Services, project) -> None:
    outline = _approved_outline(services, project)
    task = next(s for s in outline.sections if "подвижности" in s.title)
    brief = services.writing.build_brief(project.id, task.id).brief
    assert "Формула Чебышева" in brief  # définition du profil transmise au rédacteur


def test_fidelity_detects_lost_terms(settings) -> None:
    profile = DomainRegistry(settings).get("genie_mecanique")
    checks = {c.code for c in check_fidelity("Кривошип вращается, шатун движется, кулиса качается.",
                                             "Звено вращается, другое звено движется.", profile, "ru")}
    assert "fidelity_terms" in checks


@pytest.mark.anyio
async def test_mcp_writing_workflow(services: Services, project, mock: MockProvider) -> None:
    async with Client(mcp) as client:
        analysis = await client.call_tool("analyze_assignment", {"project_id": project.id})
        assert not analysis.is_error and analysis.structured_content["variant"] == "9"
        outline = (await client.call_tool("create_academic_outline", {"project_id": project.id})).structured_content
        refused = await client.call_tool("validate_outline", {"outline_id": outline["id"]})
        assert refused.structured_content["approved"] is False
        approved = await client.call_tool("validate_outline", {"outline_id": outline["id"], "approve": True, "force": True})
        assert approved.structured_content["approved"] is True
        section_id = next(s["id"] for s in outline["sections"] if s["origin"] == "requirement")
        written = await client.call_tool("write_academic_section", {"project_id": project.id, "section_id": section_id,
                                                                    "engine": "assistant"})
        assert written.structured_content["brief"]["section_id"] == section_id
        saved = await client.call_tool("save_section_draft", {"project_id": project.id, "section_id": section_id,
                                                              "text": "Степень подвижности W = 1."})
        revision_id = saved.structured_content["id"]
        reviewed = await client.call_tool("review_revision", {"revision_id": revision_id, "decision": "accept"})
        assert reviewed.structured_content["status"] == "accepted"
        status = await client.call_tool("get_draft_status", {"project_id": project.id})
        assert "1/" in status.structured_content["progress"]


def test_missing_symbols_ignore_words_units_and_elisions() -> None:
    """Audit M-01 : « sa », « et », « l' » et les unités après un nombre ne sont pas des grandeurs manquantes."""
    from academic_writer.writing.requirements import DATA, missing_symbols

    text = ("Un mobile parcourt 120 m en 8 s. Calculer sa vitesse moyenne v = s/t et l'accélération a = v/t "
            "avec t = 8 s.")
    assert missing_symbols([text], "t = 8 s") == ["v", "s"]
    assert [m.group(0) for m in DATA.finditer("Résultat : v = 120/8 = 15 m/s ; t = 8 s")] == ["t = 8 s"]
