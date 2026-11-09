"""Tests des sources et de la bibliographie (aucun appel réseau : Crossref / Open Library simulés)."""

from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.errors import ConflictError, ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.core.sources import person_from_text
from academic_writer.research.models import Person, SourceData
from academic_writer.research.online import verify_online
from academic_writer.research.styles import format_entry, parse_markers, render_markers
from academic_writer.research.validation import check_source, isbn_valid, issn_valid, make_key
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

ISBN = "978-0-306-40615-7"  # ISBN valide (exemple de référence)
BOOK = SourceData(authors=[Person(family="Иванов", given="Иван Иванович"), Person(family="Петров", given="Пётр Петрович")],
                  title="Теория механизмов и машин", subtitle="учебник", edition="2", place="Москва",
                  publisher="Высшая школа", year=2020, pages="320", isbn=ISBN)
ARTICLE = SourceData(authors=[Person(family="Ivanov", given="Ivan I."), Person(family="Petrov", given="Petr P.")],
                     title="Gear cutting", container="Journal of Mechanisms", year=2020, volume="5", issue="3",
                     pages="10–20", doi="10.1234/abc")


# --- identifiants et complétude ---------------------------------------------------

def test_identifier_checksums() -> None:
    assert isbn_valid(ISBN) and isbn_valid("0-306-40615-2")
    assert not isbn_valid("978-0-306-40615-8")
    assert issn_valid("0378-5955") and not issn_valid("0378-5956")


def test_local_status() -> None:
    assert check_source("book", BOOK)[0] == "well_formed"
    assert check_source("book", BOOK.model_copy(update={"publisher": None}))[0] == "incomplete"
    assert check_source("book", BOOK.model_copy(update={"year": 2999}))[0] == "suspicious"
    assert check_source("article", ARTICLE.model_copy(update={"doi": "doi-inventé"}))[0] == "suspicious"
    status, findings = check_source("book", BOOK.model_copy(update={"isbn": "978-0-306-40615-8"}))
    assert status == "suspicious" and any(f.field == "isbn" for f in findings)
    web = SourceData(title="Page", url="https://example.org/page", accessed="01.11.2026")
    assert check_source("web", web)[0] == "well_formed"


def test_keys_and_names() -> None:
    assert make_key(BOOK, set()) == "ivanov2020"
    assert make_key(BOOK, {"ivanov2020"}) == "ivanov2020a"
    assert person_from_text("Соболев Александр Николаевич") == Person(family="Соболев", given="Александр Николаевич")
    assert person_from_text("Dupont, Marie") == Person(family="Dupont", given="Marie")
    assert person_from_text("Marie Dupont") == Person(family="Dupont", given="Marie")


# --- styles -----------------------------------------------------------------------------

def test_gost_book_and_article() -> None:
    assert format_entry("gost", "book", BOOK) == (
        "Иванов, И. И. Теория механизмов и машин : учебник / И. И. Иванов, П. П. Петров. – 2-е изд. – "
        "Москва : Высшая школа, 2020. – 320 с. – ISBN 978-0-306-40615-7.")
    article = SourceData(authors=[Person(family="Сидоров", given="С. С.")], title="Нарезание зубчатых колес",
                         container="Вестник МГТУ «Станкин»", year=2021, volume="3", issue="2", pages="10–20",
                         doi="10.1234/xyz")
    assert format_entry("gost", "article", article) == (
        "Сидоров, С. С. Нарезание зубчатых колес / С. С. Сидоров // Вестник МГТУ «Станкин». – 2021. – Т. 3, № 2. – "
        "С. 10–20. – DOI 10.1234/xyz.")


def test_gost_four_authors_and_standard() -> None:
    many = BOOK.model_copy(update={"authors": [Person(family=f"Автор{i}", given="А. А.") for i in range(4)]})
    text = format_entry("gost", "book", many)
    assert text.startswith("Теория механизмов и машин : учебник / А. А. Автор0") and "[и др.]" in text
    standard = SourceData(standard_number="ГОСТ 13755-2015", title="Передачи зубчатые цилиндрические эвольвентные. "
                          "Исходные контуры", place="Москва", publisher="Стандартинформ", year=2016)
    assert format_entry("gost", "standard", standard).startswith("ГОСТ 13755-2015. Передачи зубчатые")


def test_international_styles() -> None:
    assert format_entry("apa", "article", ARTICLE) == (
        "Ivanov, I. I., & Petrov, P. P. (2020). Gear cutting. *Journal of Mechanisms*, *5*(3), 10–20. "
        "https://doi.org/10.1234/abc")
    assert format_entry("ieee", "article", ARTICLE) == (
        "I. I. Ivanov and P. P. Petrov, “Gear cutting,” *Journal of Mechanisms*, vol. 5, no. 3, pp. 10–20, 2020, "
        "doi: 10.1234/abc.")
    assert format_entry("vancouver", "article", ARTICLE) == (
        "Ivanov II, Petrov PP. Gear cutting. Journal of Mechanisms. 2020;5(3):10–20. doi:10.1234/abc")
    assert format_entry("chicago", "article", ARTICLE) == (
        "Ivanov, Ivan I., and Petr P. Petrov. 2020. “Gear cutting.” *Journal of Mechanisms* 5 (3): 10–20. "
        "https://doi.org/10.1234/abc.")


def test_markers_rendering() -> None:
    text = "Selon la théorie [@ivanov2020, с. 15], et d'autres travaux [@ivanov2020; @art]. Voir [@inconnue]."
    assert [items for _, items in parse_markers(text)][1] == [("ivanov2020", None), ("art", None)]
    sources = {"ivanov2020": BOOK, "art": ARTICLE}
    numeric = render_markers(text, "gost", {"ivanov2020": 1, "art": 2}, sources)
    assert "[1, с. 15]" in numeric and "[1, 2]" in numeric and "[?inconnue]" in numeric
    apa = render_markers("Voir [@art, p. 3].", "apa", {}, sources)
    assert apa == "Voir (Ivanov & Petrov, 2020, p. 3)."
    assert render_markers("[@ivanov2020]", "chicago", {}, sources) == "(Иванов и Петров 2020)"


# --- vérification en ligne (simulée) ------------------------------------------------------

def _crossref(title: str, year: int, family: str = "Ivanov"):
    return {"message": {"title": [title], "author": [{"given": "Ivan", "family": family}],
                        "issued": {"date-parts": [[year, 1, 1]]}, "container-title": ["Journal of Mechanisms"],
                        "DOI": "10.1234/abc"}}


def test_online_doi_verified_mismatch_and_not_found() -> None:
    assert verify_online(ARTICLE, lambda url: _crossref("Gear cutting", 2020)).status == "verified_online"
    mismatch = verify_online(ARTICLE, lambda url: _crossref("Quantum chromodynamics", 2011, "Smith"))
    assert mismatch.status == "mismatch" and "titre" in mismatch.findings[0].message
    assert verify_online(ARTICLE, lambda url: None).status == "not_found"


def test_online_isbn_and_title_search() -> None:
    outcome = verify_online(BOOK.model_copy(update={"title": "The Theory of Machines"}),
                            lambda url: {"title": "The theory of machines", "publish_date": "2020"})
    assert outcome.status == "verified_online"
    absent = verify_online(BOOK, lambda url: None)
    assert absent.status is None and "non concluant" in absent.findings[0].message  # absence ≠ inexistence
    search = verify_online(SourceData(title="Gear cutting", authors=[Person(family="Ivanov")]),
                           lambda url: {"message": {"items": [_crossref("Gear cutting", 2020)["message"]]}})
    assert search.status is None and search.candidates and search.candidates[0].doi == "10.1234/abc"


# --- service : sources, citations, bibliographie, audit ----------------------------------------

@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("ДЗ1", DocumentType.DEVOIR, Language.RU)
    path = inbox / "zadanie.txt"
    path.write_text("1. Определить степень подвижности механизма.", encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    services.domains.assign(project.id, "genie_mecanique", "ru")
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    services.writing.validate_outline(outline.id, approve=True, force=True)
    return project


@pytest.fixture
def section(services: Services, project):
    section = next(s for s in services.writing.current_outline(project.id).sections if s.origin == "requirement")
    draft = services.writing.save_section_draft(project.id, section.id,
                                                "Степень подвижности определяется по формуле Чебышева. Механизм плоский.")
    services.writing.review_revision(draft.id, "accept")
    return section


def test_register_duplicate_and_document_prefill(services: Services, project, inbox: Path) -> None:
    source = services.sources.register(project.id, "book", BOOK)
    assert source.key == "ivanov2020" and source.verification_status == "well_formed"
    assert "NON vérifiée" in source.status_label
    with pytest.raises(ConflictError):
        services.sources.register(project.id, "book", BOOK.model_copy(update={"title": "Autre", "year": 2019}))
    document = services.documents.list(project.id)[0]
    prefilled = services.sources.register_from_document(project.id, document.id, "other")
    assert prefilled.origin == "document" and prefilled.document_id == document.id


def test_verify_local_mode_and_connected(services: Services, project) -> None:
    source = services.sources.register(project.id, "article", ARTICLE)
    local = services.sources.verify(source.id)
    assert not local.online_checked and "Mode local" in local.online_notice
    assert local.source.verification_status == "well_formed"
    services.settings.mode = "connected"
    services.sources.fetcher = lambda url: _crossref("Gear cutting", 2020)
    online = services.sources.verify(source.id)
    assert online.online_checked and online.source.verification_status == "verified_online"
    services.sources.fetcher = lambda url: None
    assert services.sources.verify(source.id).source.verification_status == "not_found"


def test_insert_citation_creates_proposed_revision(services: Services, project, section) -> None:
    services.sources.register(project.id, "book", BOOK)
    result = services.sources.insert_citation(project.id, section.id, "ivanov2020", "по формуле Чебышева.", "с. 15")
    revision = services.writing.get_revision(result.revision_id)
    assert result.marker == "[@ivanov2020, с. 15]"
    assert "по формуле Чебышева [@ivanov2020, с. 15]." in revision.text and revision.status == "proposed"
    codes = {c.code for c in revision.checks}
    assert "citations" in codes and "fidelity_numbers" not in codes and "unsourced_numbers" not in codes
    with pytest.raises(ValidationFailed):
        services.sources.insert_citation(project.id, section.id, "ivanov2020", "absent du texte")


def test_doubtful_source_refused_unless_forced(services: Services, project, section) -> None:
    services.sources.register(project.id, "book", BOOK.model_copy(update={"year": 2999}), key="futur")
    with pytest.raises(ValidationFailed):
        services.sources.insert_citation(project.id, section.id, "futur", "Механизм плоский.")
    forced = services.sources.insert_citation(project.id, section.id, "futur", "Механизм плоский.", force=True)
    assert "Attention" in forced.message


def test_bibliography_numbering_save_and_audit(services: Services, project, section) -> None:
    services.sources.register(project.id, "article", ARTICLE, key="art")
    services.sources.register(project.id, "book", BOOK)
    services.sources.register(project.id, "web", SourceData(title="Jamais citée", url="https://example.org",
                                                            accessed="01.11.2026"), key="web1")
    first = services.sources.insert_citation(project.id, section.id, "ivanov2020", "формуле Чебышева.")
    services.writing.review_revision(first.revision_id, "accept")
    second = services.sources.insert_citation(project.id, section.id, "art", "Механизм плоский.")
    services.writing.review_revision(second.revision_id, "accept")

    bibliography = services.sources.generate_bibliography(project.id, "gost", save=True)
    assert [e.key for e in bibliography.entries] == ["ivanov2020", "art"]  # ordre d'apparition
    assert bibliography.text.startswith("1. Иванов, И. И. Теория механизмов")
    assert bibliography.entries[0].marker == "[1]"
    assert any("jamais citée" in w for w in bibliography.warnings)
    revision = services.writing.get_revision(bibliography.revision_id)
    assert revision.status == "proposed" and not any(c.code == "generated_bibliography" for c in revision.checks)

    apa = services.sources.generate_bibliography(project.id, "apa")
    assert apa.ordering == "alphabetical" and apa.entries[0].number is None

    audit = services.sources.audit(project.id)
    assert audit.cited_sources == 2 and any(i.code == "uncited" and i.source_key == "web1" for i in audit.issues)
    assert [s.key for s in services.sources.uncited(project.id).sources] == ["web1"]


def test_audit_detects_unknown_keys_and_handwritten_citations(services: Services, project, section) -> None:
    draft = services.writing.save_section_draft(project.id, section.id, "Как показано [@fantome], и ранее [3].")
    assert any(c.code == "unknown_source_keys" and c.severity == "error" for c in draft.checks)
    services.writing.review_revision(draft.id, "accept")
    codes = {i.code for i in services.sources.audit(project.id).issues}
    assert {"unknown_key", "unmanaged_citation"} <= codes


def test_brief_lists_only_citable_sources(services: Services, project, section) -> None:
    services.sources.register(project.id, "book", BOOK)
    services.sources.register(project.id, "book", BOOK.model_copy(update={"title": "Фальшивка", "year": 2999}),
                              key="faux", allow_duplicate=True)
    brief = services.writing.build_brief(project.id, section.id)
    assert "[@ivanov2020]" in brief.brief and "[@faux]" not in brief.brief
    assert "UNIQUEMENT les clés" in brief.system_prompt


@pytest.mark.anyio
async def test_mcp_source_tools(services: Services, project, section) -> None:
    async with Client(mcp) as client:
        created = await client.call_tool("register_source", {
            "project_id": project.id, "source_type": "article", "key": "art",
            "data": ARTICLE.model_dump(exclude_none=True)})
        assert not created.is_error and created.structured_content["verification_status"] == "well_formed"
        cited = await client.call_tool("insert_citation", {"project_id": project.id, "section_id": section.id,
                                                           "source_key": "art", "anchor_text": "Механизм плоский."})
        assert cited.structured_content["marker"] == "[@art]"
        await client.call_tool("review_revision", {"revision_id": cited.structured_content["revision_id"],
                                                   "decision": "accept"})
        bibliography = await client.call_tool("generate_bibliography", {"project_id": project.id, "style": "ieee"})
        assert bibliography.structured_content["text"].startswith("[1] I. I. Ivanov and P. P. Petrov")
        audit = await client.call_tool("audit_references", {"project_id": project.id})
        assert audit.structured_content["cited_sources"] == 1
