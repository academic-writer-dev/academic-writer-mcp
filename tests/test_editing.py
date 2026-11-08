"""Tests de la correction, du style et de la traduction (LanguageTool simulé ; test réel optionnel)."""

import os
from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.domains.registry import DomainRegistry
from academic_writer.providers.manager import ProviderManager
from academic_writer.providers.mock import MockProvider
from academic_writer.server.app import mcp
from academic_writer.server.services import Services
from academic_writer.writing.checks import glossary_for, translation_checks
from academic_writer.writing.languagetool import LanguageToolError, LanguageToolServer, LTMatch, LTStatus, _chunks
from academic_writer.writing.style import apply_safe_corrections, levenshtein, style_report

TEXT_RU = "Скорость точки B определяеться методом планов, ускорение кориолиса равно 0,162 м/с. Формула $W = 3n$."


def m(text: str, word: str, replacements: list[str], category: str = "TYPOS", message: str = "Опечатка") -> LTMatch:
    offset = text.index(word)
    return LTMatch(offset=offset, length=len(word), text=word, message=message, replacements=replacements,
                   rule_id="MORFOLOGIK_RULE_RU_RU", issue_type="misspelling", category=category)


class FakeLT:
    """Simule LanguageTool à partir des vraies réponses observées (LanguageTool 6.6)."""

    def __init__(self, matches=None, error: str | None = None) -> None:
        self.matches = matches or {}
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def check(self, text: str, language: str) -> list[LTMatch]:
        self.calls.append((text, language))
        if self.error:
            raise LanguageToolError(self.error)
        return [m(text, word, reps, cat) for word, reps, cat in self.matches.get(language, []) if word in text]

    def status(self) -> LTStatus:
        return LTStatus(running=self.error is None, url="http://localhost:8081", installation=None, java=None,
                        message="simulé")

    def start(self) -> None:
        return None

    def stop(self) -> bool:
        return False


RU_MATCHES = {"ru": [("определяеться", ["определяется", "определяться"], "TYPOS"),
                     ("кориолиса", ["кореопсиса", "корились"], "TYPOS")]}


@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("ДЗ1", DocumentType.DEVOIR, Language.RU)
    path = inbox / "zadanie.txt"
    path.write_text("1. Определить скорость точки B методом планов. Рассчитать ускорение Кориолиса.", encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    services.domains.assign(project.id, "genie_mecanique", "ru")
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    services.writing.validate_outline(outline.id, approve=True, force=True)
    return project


@pytest.fixture
def section_id(services: Services, project) -> str:
    return next(s.id for s in services.writing.current_outline(project.id).sections if s.origin == "requirement")


@pytest.fixture
def mock(services: Services) -> MockProvider:
    provider = MockProvider()
    services.ai = ProviderManager(services.db, services.settings, services.projects,
                                  factory=lambda name: provider, ollama_probe=lambda: ["qwen3.5:4b"])
    services.writing.ai = services.ai
    services.editing.ai = services.ai
    return provider


@pytest.fixture
def lt(services: Services) -> FakeLT:
    fake = FakeLT(RU_MATCHES)
    services.editing.languagetool = fake
    return fake


# --- règles de correction sûre -------------------------------------------------

def test_levenshtein() -> None:
    assert levenshtein("пастроили", "построили") == 1
    assert levenshtein("кориолиса", "кореопсиса") > 2


def test_safe_corrections_protect_terms_and_formulas() -> None:
    text = TEXT_RU
    matches = [m(text, "определяеться", ["определяется"]), m(text, "кориолиса", ["кореопсиса"]),
               m(text, "3n", ["3 n"], category="TYPOGRAPHY")]
    corrected, applied, suggested = apply_safe_corrections(text, matches, known_terms="ускорение Кориолиса")
    assert "определяется" in corrected and "кориолиса" in corrected and "$W = 3n$" in corrected
    assert len(applied) == 1 and "определяется" in applied[0]
    assert any("terme du projet conservé" in s for s in suggested) and any("[formule]" in s for s in suggested)


def test_unknown_distant_replacement_not_applied() -> None:
    text = "ускорение кориолиса"
    corrected, applied, suggested = apply_safe_corrections(text, [m(text, "кориолиса", ["кореопсиса"])], "")
    assert corrected == text and not applied and "кореопсиса" in suggested[0]


def test_style_categories_never_auto_applied() -> None:
    text = "Il y a beaucoup de choses."
    match = LTMatch(offset=0, length=6, text="Il y a", message="Style", replacements=["Il existe"],
                    rule_id="X", issue_type="style", category="STYLE")
    corrected, applied, _ = apply_safe_corrections(text, [match], "")
    assert corrected == text and not applied


def test_style_report() -> None:
    long = " ".join(["слово"] * 35) + "."
    codes = {c.code for c in style_report(long + " Я считаю, что это очень важно.", "ru")}
    assert {"long_sentences", "vague_words", "first_person"} <= codes
    repeated = " ".join(["механизма"] * 4 + ["звено"] * 3) + "."
    assert "repetitions" in {c.code for c in style_report(repeated, "ru")}
    assert [c.code for c in style_report("Le mécanisme est étudié.", "fr")] == ["style_ok"]


def test_chunks_split_on_paragraphs() -> None:
    text = ("A" * 5000 + "\n\n") * 4
    chunks = _chunks(text)
    assert "".join(c for _, c in chunks) == text and all(len(c) <= 8000 for _, c in chunks)
    assert all(text[start:start + len(c)] == c for start, c in chunks)


def test_glossary_matches_whole_words_only(settings) -> None:
    """Faux positifs observés lors de l'essai réel : « предел » dans « определяется », « кинема » dans « кинематику »."""
    profile = DomainRegistry(settings).get("genie_mecanique")
    text = "Мы исследовали кинематику механизма. Скорость определяется методом планов. Кривошипа нет."
    sources = {src for src, _ in glossary_for(text, profile, "ru", "fr")}
    assert "предел текучести" not in sources and "кинематическая пара" not in sources
    assert "кривошип" in sources  # flexion « Кривошипа » reconnue


def test_correction_keeps_parent_numbers_as_sourced(services: Services, project, section_id, lt) -> None:
    base = _draft(services, project, section_id, "Частота 52 об/мин, ускорение 0,162 м/с². Скорость определяеться.")
    result = services.editing.correct_section(project.id, section_id, base.id, use_ai=False)
    assert not any(c.code == "unsourced_numbers" for c in result.revision.checks)


def test_translation_checks(settings) -> None:
    profile = DomainRegistry(settings).get("genie_mecanique")
    original = "Кривошип вращается с частотой вращения 52 об/мин; кулиса качается."
    assert ("кривошип", "crank") in glossary_for(original, profile, "ru", "en")
    good = "The crank rotates at a rotational frequency of 52 rpm; the slotted link oscillates."
    assert translation_checks(original, good, profile, "ru", "en") == []
    bad = {c.code: c for c in translation_checks(original, "The handle turns at 25 rpm.", profile, "ru", "en")}
    assert bad["translation_numbers"].severity == "error"
    assert any("crank" in d for d in bad["translation_terms"].details)


# --- correction de section ----------------------------------------------------------

def _draft(services: Services, project, section_id: str, text: str = TEXT_RU):
    return services.writing.save_section_draft(project.id, section_id, text)


def test_correction_with_languagetool_and_ai(services: Services, project, section_id, mock, lt) -> None:
    base = _draft(services, project, section_id)
    mock.responses.append(TEXT_RU.replace("определяеться", "определяется").replace("кориолиса", "Кориолиса"))
    result = services.editing.correct_section(project.id, section_id)
    assert result.ai_used and not result.ai_discarded and result.engine == "languagetool+mock"
    revision = result.revision
    assert revision.kind == "correction" and revision.parent_revision_id == base.id and revision.status == "proposed"
    assert "Кориолиса" in revision.text and "определяется" in revision.text
    codes = {c.code for c in revision.checks}
    assert {"lt_corrections", "lt_suggestions"} <= codes
    assert "определяеться" in lt.calls[0][0] and lt.calls[0][1] == "ru"
    assert "кореопсиса" in mock.requests[-1].prompt  # signalements transmis comme indices, pas appliqués


def test_ai_correction_changing_numbers_is_discarded(services: Services, project, section_id, mock, lt) -> None:
    _draft(services, project, section_id)
    mock.responses.append(TEXT_RU.replace("0,162", "0,612").replace("методом планов", "методом Планшера"))
    result = services.editing.correct_section(project.id, section_id)
    assert result.ai_discarded
    text = result.revision.text
    assert "0,162" in text and "Планшера" not in text and "определяется" in text  # seules les corrections sûres
    assert any(c.code == "ai_correction_discarded" for c in result.revision.checks)


def test_correction_without_ai_and_without_changes(services: Services, project, section_id, mock, lt) -> None:
    _draft(services, project, section_id)
    result = services.editing.correct_section(project.id, section_id, use_ai=False)
    assert not result.ai_used and result.engine == "languagetool" and "определяется" in result.revision.text
    assert mock.requests == []
    clean = services.writing.save_section_draft(project.id, section_id, "Скорость определяется методом планов.")
    nothing = services.editing.correct_section(project.id, section_id, clean.id, use_ai=False)
    assert nothing.revision is None and "Aucune correction" in nothing.message


def test_correction_when_languagetool_unavailable(services: Services, project, section_id, mock) -> None:
    services.editing.languagetool = FakeLT(error="serveur arrêté")
    _draft(services, project, section_id)
    mock.responses.append(TEXT_RU.replace("определяеться", "определяется"))
    result = services.editing.correct_section(project.id, section_id)
    assert result.ai_used and any(c.code == "languagetool_unavailable" for c in result.revision.checks)


def test_check_language_reports_without_changing(services: Services, project, section_id, lt) -> None:
    base = _draft(services, project, section_id)
    report = services.editing.check_language(project.id, section_id)
    assert report.revision_id == base.id and len(report.matches) == 2
    assert services.writing.get_revision(base.id).text == TEXT_RU


# --- style et traduction ----------------------------------------------------------------

def test_improve_style_with_rewrite(services: Services, project, section_id, mock, lt) -> None:
    _draft(services, project, section_id, "Я думаю, что это очень важно. " + " ".join(["слово"] * 35) + ".")
    mock.responses.append("Данный аспект имеет существенное значение.")
    result = services.editing.improve_style(project.id, section_id, rewrite=True)
    assert {"long_sentences", "vague_words", "first_person"} <= {c.code for c in result.checks}
    assert result.rewrite.revision.kind == "rewrite"
    assert "Améliore le style" in mock.requests[-1].prompt


def test_translation_proposed_and_does_not_replace_original(services: Services, project, section_id, mock, lt) -> None:
    base = _draft(services, project, section_id, "Кривошип вращается с частотой вращения 52 об/мин.")
    services.writing.review_revision(base.id, "accept")
    mock.responses.append("The crank rotates at a rotational frequency of 52 rpm.")
    result = services.editing.translate_section(project.id, section_id, "en")
    revision = result.revision
    assert revision.language == "en" and revision.kind == "translation" and "кривошип → crank" in result.glossary
    assert not any(c.code.startswith("translation_") for c in revision.checks)
    assert "Glossaire obligatoire" in mock.requests[-1].prompt
    services.writing.review_revision(revision.id, "accept")
    assert services.writing.get_revision(base.id).status == "accepted"  # original russe toujours validé
    status = services.writing.draft_status(project.id)
    entry = next(s for s in status.sections if s.section_id == section_id)
    assert entry.accepted_revision_id == base.id


def test_translation_errors_flagged(services: Services, project, section_id, mock, lt) -> None:
    _draft(services, project, section_id, "Кривошип вращается с частотой 52 об/мин.")
    mock.responses.append("The handle turns at 25 rpm.")
    revision = services.editing.translate_section(project.id, section_id, "en").revision
    codes = {c.code: c for c in revision.checks}
    assert codes["translation_numbers"].severity == "error" and "translation_terms" in codes


def test_translation_assistant_brief_and_save(services: Services, project, section_id, lt) -> None:
    base = _draft(services, project, section_id, "Кривошип вращается с частотой 52 об/мин.")
    result = services.editing.translate_section(project.id, section_id, "fr", engine="assistant")
    assert result.brief and "manivelle" in result.brief.brief and "language='fr'" in result.next_step
    saved = services.writing.save_section_draft(project.id, section_id, "La manivelle tourne à 52 tr/min.",
                                                kind="translation", parent_revision_id=base.id, language="fr")
    assert saved.language == "fr" and not any(c.code == "translation_numbers" for c in saved.checks)


def test_same_language_translation_rejected(services: Services, project, section_id, lt) -> None:
    from academic_writer.core.errors import ValidationFailed
    _draft(services, project, section_id)
    with pytest.raises(ValidationFailed):
        services.editing.translate_section(project.id, section_id, "ru")


@pytest.mark.anyio
async def test_mcp_editing_tools(services: Services, project, section_id, mock, lt) -> None:
    _draft(services, project, section_id)
    async with Client(mcp) as client:
        report = await client.call_tool("check_language", {"project_id": project.id, "section_id": section_id})
        assert len(report.structured_content["matches"]) == 2
        mock.responses.append(TEXT_RU.replace("определяеться", "определяется"))
        corrected = await client.call_tool("correct_academic_section", {"project_id": project.id, "section_id": section_id})
        assert corrected.structured_content["revision"]["kind"] == "correction"
        status = await client.call_tool("manage_languagetool", {"action": "status"})
        assert status.structured_content["message"] == "simulé"


# --- test réel facultatif (AW_LT_INTEGRATION=1) ---------------------------------------------

@pytest.mark.skipif(os.environ.get("AW_LT_INTEGRATION") != "1", reason="test LanguageTool réel désactivé")
def test_real_languagetool(settings) -> None:
    real = settings.model_copy(update={"languagetool_url": "http://localhost:8081",
                                       "data_dir": Path(r"D:\AcademicWriter-Data")})
    matches = LanguageToolServer(real).check("Мы исследавали кинематику механизма.", "ru")
    assert any(x.text == "исследавали" and "исследовали" in x.replacements for x in matches)
