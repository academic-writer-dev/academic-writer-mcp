"""Bibliothèques ajoutées le 2026-11-11 : dépôts russophones, La Referencia, manuels ouverts, guides de rédaction."""

import json

import pytest

from academic_writer.research import libraries_more as lib
from academic_writer.research.discovery import DiscoveredWork, DiscoveryResult, find_by_topic
from academic_writer.research.models import SourceData
from academic_writer.research.providers import PROVIDERS
from academic_writer.server.services import Services

UUID = "1c1050f8-8303-4ef8-8890-1ff881c3f6f1"
DSPACE = {"_embedded": {"searchResult": {"page": {"totalElements": 1}, "_embedded": {"objects": [
    {"_embedded": {"indexableObject": {
        "uuid": UUID, "handle": "123456789/3350", "name": "Теория механизмов и машин",
        "metadata": {"dc.title": [{"value": "Теория механизмов и машин"}],
                     "dc.contributor.author": [{"value": "Балахнина, А. А. (сост.)"}],
                     "dc.date.issued": [{"value": "2008"}],
                     "dc.identifier.uri": [{"value": "http://hdl.handle.net/123456789/3350"}],
                     "dc.subject": [{"value": "курсовые проекты"}], "dc.language.iso": [{"value": "other"}],
                     "dc.publisher": [{"value": "Тольяттинский государственный университет"}],
                     "dc.type": [{"value": "Book"}]}}}},
    {"_embedded": {"indexableObject": {"uuid": "pas-un-uuid", "name": "Rejeté"}}}]}}}}

ATOM = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Зубчатая передача</title><link href="https://elar.urfu.ru/handle/10995/83722" rel="alternate"/>
<author><name>Филимонов, И. Е.</name></author><published>2020-06-07T11:25:13Z</published></entry>
<entry><title>Sans lien sûr</title><link href="http://exemple.org/x"/></entry></feed>"""

LAREF = {"resultCount": 1, "records": [{
    "id": "MX_7631172cf3e0d9da9565f4d8d1c7d53f",
    "title": "Perfeccionamiento del diseño de transmisiones por engranajes cilíndricos",
    "primaryAuthors": ["Ana María Becerra Ferreiro"], "secondaryAuthors": ["Jorge Moya Rodríguez"],
    "publicationDates": ["2015"], "formats": ["Article"], "subjects": [["Engranajes interiores"]],
    "urls": [{"url": "https://www.redalyc.org/articulo.oa?id=504373319008"}]}]}


def otl_page(items, next_url=None):
    return json.dumps({"data": items, "links": {"next": next_url} if next_url else {}})


OTL_ITEM = {"id": 85, "title": "Strength of Materials", "copyright_year": 2020, "isbn13": "9781111111111",
            "license": "Attribution", "language": "eng", "description": "Stress, strain, beams and torsion.",
            "contributors": [{"contribution": "Author", "corporate": False, "first_name": "Ann", "last_name": "Roe"}],
            "publishers": [{"name": "Open Press"}], "subjects": [{"name": "Mechanical Engineering"}],
            "url": "https://open.umn.edu/opentextbooks/textbooks/strength-of-materials"}


def test_dspace7_parser_builds_direct_link() -> None:
    works = lib.dspace7_parser("tltsu")(json.dumps(DSPACE), "теория механизмов машин")
    assert len(works) == 1  # objet sans identifiant valide écarté
    work = works[0]
    assert work.landing_url == f"https://dspace.tltsu.ru/items/{UUID}"  # pas le handle par défaut inutilisable
    assert work.year == 2008 and work.source_type == "book" and work.language is None and work.relevance == 1.0


def test_opensearch_parser_has_no_false_year() -> None:
    works = lib.opensearch_parser("urfu")(ATOM, "зубчатая передача")
    assert [w.landing_url for w in works] == ["https://elar.urfu.ru/handle/10995/83722"]
    assert works[0].year is None and works[0].authors == ["Филимонов, И. Е."]


def test_lareferencia_parser() -> None:
    work = lib.parse_lareferencia(json.dumps(LAREF), "engranajes cilíndricos")[0]
    assert work.year == 2015 and work.authors == ["Ana María Becerra Ferreiro", "Jorge Moya Rodríguez"]
    assert work.landing_url.startswith("https://www.redalyc.org/") and work.relevance == 1.0
    assert "field[]=publicationDates" in lib.lareferencia_url("x", 5)


def test_open_textbooks_harvest_and_local_search(tmp_path) -> None:
    pages = {}
    for subject in lib.OTL_SUBJECTS:
        base = f"https://open.umn.edu/opentextbooks/subjects/{subject}.json?page=1"
        nxt = f"https://open.umn.edu/opentextbooks/subjects/{subject}.json?page=2"
        pages[base] = otl_page([OTL_ITEM], nxt if subject == 13 else None)
        pages[nxt] = otl_page([{**OTL_ITEM, "id": 86, "title": "Engineering Statics"}])
    count = lib.otl_harvest(tmp_path, lambda url: pages.get(url, otl_page([])), sleep=lambda _s: None)
    assert count == 2  # dédoublonné entre matières
    records = lib.otl_records(tmp_path)
    found = lib.otl_parser(records)(None, "strength of materials")
    assert [w.title for w in found] == ["Strength of Materials"] and found[0].authors == ["Ann Roe"]
    assert "licence ouverte" in found[0].license and not lib.otl_stale(tmp_path)


def test_russian_repositories_only_for_cyrillic_queries() -> None:
    assert not {"bntu", "tltsu", "urfu"} & {p[0] for p in lib.plans("gear fatigue", 5, "all")}
    assert {"bntu", "tltsu", "urfu", "lareferencia"} <= {p[0] for p in lib.plans("зубчатые колеса", 5, "all")}
    urls = []
    find_by_topic("зубчатые колеса", lambda u: urls.append(u), "all", services_filter=["bntu", "urfu"])
    assert all(u.startswith(("https://rep.bntu.by/", "https://elar.urfu.ru/")) for u in urls) and len(urls) == 2


def test_registry_lists_new_libraries_and_not_excluded() -> None:
    ids = {p.id for p in PROVIDERS}
    assert {"bntu", "tltsu", "urfu", "lareferencia", "open_textbooks"} <= ids
    assert not {"spbu", "doab", "oapen", "shodhganga"} & ids


def test_writing_guides(services: Services, monkeypatch) -> None:
    services.settings.mode = "connected"
    asked = []

    def fake_find(query, fetch, kind="all", **options):
        asked.append((query, tuple(options.get("services_filter") or ())))
        work = DiscoveredWork(item_id=f"urfu:{len(asked)}", service="urfu", title=f"Оформление ВКР {query}",
                              authors=[], year=None, source_type="other", open_access=False, relevance=1.0,
                              data=SourceData(title="x"))
        return DiscoveryResult(query=query, services=["urfu"], count=1, works=[work], notices=[])

    monkeypatch.setattr("academic_writer.core.sources.find_by_topic", fake_find)
    result = services.sources.writing_guides("memoire_master", "ru")
    assert [q for q, _ in asked] == lib.GUIDE_QUERIES["memoire"]["ru"]
    assert all("urfu" in services_ for _, services_ in asked) and result.count == 2
    assert any("établissement" in n for n in result.notices)
    with pytest.raises(Exception, match="Type de travail"):
        services.sources.writing_guides("poeme")
