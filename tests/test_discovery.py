"""Recherche par thème, téléchargement en libre accès légal, export de références (réseau simulé)."""

import json
from pathlib import Path

import pytest

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentType, Language
from academic_writer.research.discovery import archive_query, find_by_topic, relevance
from academic_writer.research.fulltext import DownloadRefused, resolve_pdf, to_bibtex, to_ris
from academic_writer.research.importers import parse_bibtex, parse_ris
from academic_writer.research.models import Person, SourceData
from academic_writer.server.services import Services
from tests.samples import make_text_pdf

IA = {"response": {"numFound": 2, "docs": [
    {"identifier": "tmimrz1977", "title": "ТЕОРИЯ МЕХАНИЗМОВ И МАШИН решение задач", "year": "1977",
     "creator": ["Иванов Михаил Евгеньевич"], "language": "rus"},
    {"identifier": "no-7-77-84", "title": "Планетарные передачи с цевочным зацеплением механизмов машин",
     "year": "2011", "licenseurl": "https://creativecommons.org/licenses/by-nd/4.0/"},
    {"identifier": "bruit", "title": "Уплотнители резиновые", "year": "2020"}]}}
DOAJ = {"results": [{"id": "abc123", "bibjson": {
    "title": "Research on the Root Cutting Mechanism of Involute Gears", "year": "2023",
    "author": [{"name": "Zhang Wei"}], "journal": {"title": "Mechanics", "publisher": "X", "language": ["EN"]},
    "identifier": [{"type": "doi", "id": "10.1/gear"}],
    "link": [{"type": "fulltext", "url": "https://journal.example/article.pdf"}]}}]}
ARXIV = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2101.00001v1</id>'
         "<title>Involute gear generating by rack cutter</title><published>2021-01-01T00:00:00Z</published>"
         "<author><name>Jane Doe</name></author><summary>gear cutting</summary></entry></feed>")


def fake_fetch(url: str) -> str | None:
    if "advancedsearch" in url:
        return json.dumps(IA)
    if "doaj.org/api/search" in url:
        return json.dumps(DOAJ)
    if "arxiv" in url:
        return ARXIV
    if "crossref" in url:
        return json.dumps({"message": {"items": []}})
    if "openlibrary" in url:
        return json.dumps({"docs": []})
    return None


def test_relevance_and_archive_query() -> None:
    assert relevance("теория механизмов и машин", "ТЕОРИЯ МЕХАНИЗМОВ И МАШИН решение задач") == 1.0
    assert relevance("зубчатые колеса", "Колеса Mecanum для дронов") == 0.5
    query = archive_query("нарезание зубчатых колес")
    assert "title:(нарезан*)" in query and " OR " in query and query.endswith("AND mediatype:texts")


def test_find_by_topic_merges_and_flags_open_access() -> None:
    result = find_by_topic("теория механизмов машин", fake_fetch, "books")
    titles = {w.title: w for w in result.works}
    book = titles["ТЕОРИЯ МЕХАНИЗМОВ И МАШИН решение задач"]
    assert book.item_id == "ia:tmimrz1977" and not book.open_access and book.landing_url.endswith("/tmimrz1977")
    assert book.data.authors[0] == Person(family="Иванов", given="Михаил Евгеньевич")
    assert titles["Планетарные передачи с цевочным зацеплением механизмов машин"].open_access
    assert "Уплотнители резиновые" not in titles  # hors sujet écarté
    assert any("sans licence libre" in n for n in result.notices)


def test_find_by_topic_articles_and_open_access_only() -> None:
    result = find_by_topic("involute gear cutting", fake_fetch, "articles", open_access_only=True)
    services = {w.service for w in result.works}
    assert services == {"doaj", "arxiv"} and all(w.open_access for w in result.works)
    doaj = next(w for w in result.works if w.service == "doaj")
    assert doaj.data.doi == "10.1/gear" and doaj.item_id == "doaj:abc123"


def test_resolve_pdf_checks_license_and_https() -> None:
    meta_open = {"metadata": {"licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
                 "files": [{"name": "article_text.pdf"}, {"name": "article.pdf"}]}
    url, _, name = resolve_pdf("ia:item1", lambda u: json.dumps(meta_open))
    assert url == "https://archive.org/download/item1/article.pdf" and name == "article.pdf"
    with pytest.raises(DownloadRefused, match="licence libre"):
        resolve_pdf("ia:item2", lambda u: json.dumps({"metadata": {}, "files": [{"name": "x.pdf"}]}))
    assert resolve_pdf("arxiv:2101.00001v1")[0] == "https://arxiv.org/pdf/2101.00001v1"
    doaj_http = {"bibjson": {"link": [{"type": "fulltext", "url": "http://insecure.example/a.pdf"}]}}
    with pytest.raises(DownloadRefused, match="HTTPS"):
        resolve_pdf("doaj:abc", lambda u: json.dumps(doaj_http))
    for bad in ("crossref:10.1/x", "openlibrary:/works/1", "ia:a b", "inconnu"):
        with pytest.raises(DownloadRefused):
            resolve_pdf(bad, lambda u: None)


def test_bibtex_and_ris_round_trip() -> None:
    data = SourceData(authors=[Person(family="Иванов", given="И. И.")], title="Теория механизмов", publisher="Наука",
                      place="Москва", year=1977, pages="10–20", isbn="978-0-306-40615-7")
    back = parse_bibtex(to_bibtex("ivanov1977", "book", data))[0]
    assert back.key == "ivanov1977" and back.data.title == data.title and back.data.pages == "10–20"
    assert back.data.authors == data.authors and back.data.year == 1977
    ris = parse_ris(to_ris("ivanov1977", "article", data.model_copy(update={"container": "Вестник"})))[0]
    assert ris.source_type == "article" and ris.data.pages == "10–20" and ris.data.container == "Вестник"


@pytest.fixture
def project(services: Services):
    return services.projects.create("Essai", DocumentType.RAPPORT_LABORATOIRE, Language.RU)


def test_discover_and_download_require_connected_mode(services: Services, project) -> None:
    with pytest.raises(ValidationFailed, match="Mode local"):
        services.sources.discover("теория механизмов")
    with pytest.raises(ValidationFailed, match="Mode local"):
        services.sources.download_open_access(project.id, "arxiv:2101.00001")


def test_download_open_access_imports_checked_pdf(services: Services, project, tmp_path: Path) -> None:
    services.settings.mode = "connected"
    pdf = make_text_pdf(tmp_path / "article.pdf").read_bytes()
    meta = {"metadata": {"licenseurl": "https://creativecommons.org/licenses/by-nd/4.0/"}, "files": [{"name": "a.pdf"}]}
    services.sources.text_fetcher = lambda url: json.dumps(meta)
    services.sources.bytes_fetcher = lambda url, limit: pdf
    result = services.sources.download_open_access(project.id, "ia:no-7-77-84")
    assert not result.duplicate and result.original_filename == "a.pdf" and "creativecommons" in result.license
    document = services.documents.get(result.document_id)
    assert document.extension == ".pdf" and services.documents.metadata(document.id).original_protected
    assert not list((services.settings.data_dir / "tmp").iterdir())  # fichier temporaire supprimé
    assert services.sources.download_open_access(project.id, "ia:no-7-77-84").duplicate


def test_download_rejects_fake_pdf_and_protected_work(services: Services, project) -> None:
    from academic_writer.core.errors import SecurityViolation
    services.settings.mode = "connected"
    services.sources.text_fetcher = lambda url: json.dumps(
        {"metadata": {"licenseurl": "https://creativecommons.org/licenses/by/4.0/"}, "files": [{"name": "a.pdf"}]})
    services.sources.bytes_fetcher = lambda url, limit: b"<html>page de connexion</html>"
    with pytest.raises(SecurityViolation):  # contenu inspecté : ce n'est pas un PDF
        services.sources.download_open_access(project.id, "ia:item")
    services.sources.text_fetcher = lambda url: json.dumps({"metadata": {}, "files": [{"name": "a.pdf"}]})
    with pytest.raises(ValidationFailed, match="droit d'auteur"):
        services.sources.download_open_access(project.id, "ia:tmimrz1977")


def test_export_references_formats(services: Services, project) -> None:
    services.sources.register(project.id, "book", SourceData(authors=[Person(family="Иванов", given="И. И.")],
                                                            title="Теория", publisher="Наука", year=1977))
    for fmt, marker in (("bibtex", "@book{ivanov1977"), ("ris", "TY  - BOOK"), ("text", "1. Иванов, И. И. Теория")):
        export = services.sources.export_references(project.id, fmt)
        assert export.count == 1 and marker in export.content and Path(export.path).exists()
        assert "exports" in export.path
    with pytest.raises(ValidationFailed):
        services.sources.export_references(project.id, "docx")
