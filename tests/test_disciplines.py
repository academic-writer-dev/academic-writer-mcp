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


def _profiles():
    from academic_writer.core.config import Settings
    from academic_writer.domains.registry import DomainRegistry

    return DomainRegistry(Settings()).all()


@pytest.mark.parametrize(("query", "expected"), [
    ("расчет зубчатой передачи редуктора", "genie_mecanique"),
    ("gear tooth bending fatigue", "genie_mecanique"),
    ("résistance des matériaux poutre", "genie_mecanique"),  # priorité au programme de génie mécanique
    ("обработка резанием", "fabrication_mecanique"),
    ("béton armé poutre", "genie_civil"),
    ("diabète de type 2 traitement", "medecine"),
    ("contrat de travail licenciement", "droit"),
    ("machine learning", "ia_data_science"),
    ("histoire de la révolution française", "histoire"),
])
def test_domain_detection(query: str, expected: str) -> None:
    assert disciplines.detect(query, _profiles()) == expected


def test_auto_mode_adds_without_removing() -> None:
    urls = []

    def fetch(url: str):
        urls.append(urllib.parse.unquote(url))
        return None

    general = set(find_by_topic("gear fatigue", lambda _u: None, "all").services)
    result = find_by_topic("gear fatigue", fetch, "all", auto_domain="genie_mecanique")
    assert general <= set(result.services)  # aucune base retirée (PubMed, ERIC… restent)
    assert {"ntrs", "jstage"} <= set(result.services)
    assert any("primary_topic.subfield.id:2210" in u for u in urls)
    assert any("api.openalex.org" in u and "subfield" not in u for u in urls)  # recherche générale conservée
    urls.clear()
    other = find_by_topic("diabetes treatment", fetch, "all", auto_domain="medecine", auto_label="Médecine")
    assert any("primary_topic.field.id:27" in u for u in urls) and "ntrs" not in other.services


def test_auto_mode_ranks_specialized_first() -> None:
    def fetch(url: str):
        if "primary_topic.subfield.id" in url:
            return json.dumps({"results": [{"id": "https://openalex.org/W2", "display_name": "Gear fatigue strength"}]})
        if "api.crossref.org" in url and "prefix" not in url:
            return json.dumps({"message": {"items": [{"DOI": "10.1/x", "title": ["Gear fatigue in general"]}]}})
        return None

    result = find_by_topic("gear fatigue", fetch, "all", auto_domain="genie_mecanique", auto_label="Génie mécanique")
    assert result.works[0].title == "Gear fatigue strength"
    assert any(n.startswith("Domaine reconnu : Génie mécanique") for n in result.notices)
