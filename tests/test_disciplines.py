"""Recherche spécialisée génie mécanique : filtres, sources ajoutées et retirées, NASA NTRS."""

import json
import urllib.parse

import pytest

from academic_writer.research import disciplines
from academic_writer.research.discovery import find_by_topic
from academic_writer.research.providers import PROVIDERS

NTRS = {"results": [{
    "id": "20220015546", "title": "Statistical Distribution of Gear Surface Fatigue Lives at High Reliability",
    "authorAffiliations": [{"meta": {"author": {"name": "Zachary A. Kish"}}}, {"meta": {"author": {"name": " "}}}],
    "publications": [{"publicationName": "International Journal of Fatigue", "publisher": "Elsevier",
                      "publicationDate": "2023-02-01T00:00:00", "volume": "167", "doi": "10.1016/j.ijfatigue.2022.107289"}],
    "keywords": ["gear", "fatigue"], "subjectCategories": ["Mechanical Engineering"],
    "distribution": "PUBLIC", "downloadsAvailable": True}]}


def test_ntrs_parser() -> None:
    work = disciplines.parse_ntrs(json.dumps(NTRS), "gear fatigue")[0]
    assert work.service == "ntrs" and work.year == 2023 and work.authors == ["Zachary A. Kish"]
    assert work.landing_url == "https://ntrs.nasa.gov/citations/20220015546" and work.source_type == "article"
    assert work.relevance == 1.0 and not work.open_access and "document public" in work.license
    assert disciplines.parse_ntrs("<html>", "x") == []


def test_mechanical_search_plans() -> None:
    urls = []

    def fetch(url: str):
        urls.append(urllib.parse.unquote(url))
        return None

    result = find_by_topic("gear fatigue", fetch, "all", discipline="genie_mecanique")
    assert not {"pubmed", "europe_pmc", "eric", "ndl"} & set(result.services)
    assert {"ntrs", "jstage", "openalex", "doaj"} <= set(result.services)
    assert any("primary_topic.subfield.id:2210|2211" in u for u in urls if "openalex" in u)
    assert any('index.schema_codes_tree:"LCC:TJ1-1570"' in u for u in urls if "doaj.org" in u)
    assert {c for c in ("mej", "jamdsm", "transjsme") if any(f"cdjournal={c}" in u for u in urls)} == \
        {"mej", "jamdsm", "transjsme"}


def test_without_discipline_nothing_changes() -> None:
    urls = []
    find_by_topic("gear fatigue", lambda u: urls.append(urllib.parse.unquote(u)), "articles")
    assert not any("subfield" in u or "schema_codes_tree" in u or "ntrs.nasa.gov" in u for u in urls)


def test_aliases_and_unknown_discipline() -> None:
    assert disciplines.get("fabrication_mecanique").id == "genie_mecanique"
    assert disciplines.get(None) is None
    with pytest.raises(ValueError):
        disciplines.get("medecine")


def test_russian_mechanical_journals_and_registry() -> None:
    journals = disciplines.DISCIPLINES["genie_mecanique"].cyberleninka_journals
    assert len(journals) == 18 and all(k.startswith("journal_") for k in journals)
    assert "journal_11101" in journals  # Вестник МГТУ им. Баумана. Серия «Машиностроение»
    by_id = {p.id: p for p in PROVIDERS}
    assert by_id["ntrs"].integration == "api" and by_id["ntrs"].access == "PUBLIC_FREE"
    assert by_id["engrxiv"].integration == "manual_link" and "robots.txt" in by_id["engrxiv"].verification
