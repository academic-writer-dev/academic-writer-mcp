"""Audit E-03 : bases ouvertes supplémentaires (réponses d'API simulées : le mode local interdit le réseau)."""

import json

import pytest

from academic_writer.research import openscience as osc
from academic_writer.research.discovery import find_by_topic
from academic_writer.research.fulltext import DownloadRefused, resolve_pdf

Q = "fatigue of welded joints"

S2 = {"data": [
    {"paperId": "abc", "title": "Fatigue of welded joints under variable amplitude", "year": 2021, "venue": "IJF",
     "authors": [{"name": "Anna Smith"}], "externalIds": {"DOI": "10.1/s2"},
     "openAccessPdf": {"url": "https://example.org/a.pdf", "license": "CCBY", "status": "GOLD"}},
    {"paperId": "def", "title": "Welded joints fatigue design review", "year": 2019,
     "authors": [{"name": "B. Lee"}], "externalIds": {},
     "openAccessPdf": {"url": "https://publisher.org/free.pdf", "license": None, "status": "BRONZE"}},
]}
EPMC = {"resultList": {"result": [
    {"id": "PMC1", "source": "PMC", "pmcid": "PMC1", "doi": "10.1/epmc", "title": "Fatigue of welded joints in implants.",
     "authorString": "Doe J, Roe R.", "pubYear": "2020", "isOpenAccess": "Y", "license": "cc by",
     "journalInfo": {"journal": {"title": "J Biomech"}, "volume": "5"},
     "fullTextUrlList": {"fullTextUrl": [{"documentStyle": "pdf", "url": "https://europepmc.org/x.pdf"}]}},
    {"id": "123", "source": "MED", "title": "Welded joints fatigue in surgery tools.", "pubYear": "2018",
     "isOpenAccess": "N"},
]}}
HAL = {"response": {"docs": [
    {"halId_s": "hal-01", "title_s": ["Fatigue des joints soudés (welded joints fatigue)"],
     "authFullName_s": ["Jean Martin"], "producedDateY_i": 2017, "docType_s": "THESE",
     "fileMain_s": "https://hal.science/hal-01/document", "uri_s": "https://hal.science/hal-01", "language_s": ["fr"]},
]}}
ZENODO = {"hits": {"hits": [
    {"id": 77, "doi": "10.5281/zenodo.77", "links": {"self_html": "https://zenodo.org/records/77"},
     "metadata": {"title": "Welded joints fatigue dataset", "creators": [{"name": "Kim, H."}],
                  "publication_date": "2022-03-01", "access_right": "open", "license": {"id": "cc-by-4.0"},
                  "resource_type": {"type": "dataset"}}},
]}}
DATACITE = {"data": [{"id": "10.1/dc", "attributes": {
    "doi": "10.1/dc", "titles": [{"title": "Fatigue welded joints measurements"}], "creators": [{"name": "Lab X"}],
    "publicationYear": 2023, "publisher": {"name": "Lab X"}, "types": {"resourceTypeGeneral": "Dataset"},
    "rightsList": [{"rightsUri": "https://creativecommons.org/licenses/by/4.0/"}]}}]}
ESEARCH = {"esearchresult": {"idlist": ["111"]}}
ESUMMARY = {"result": {"uids": ["111"], "111": {
    "title": "Fatigue of welded joints: a clinical analogy.", "authors": [{"name": "Ng P"}], "pubdate": "2016 Mar",
    "fulljournalname": "Med Eng", "articleids": [{"idtype": "doi", "value": "10.1/pm"}, {"idtype": "pmc", "value": "PMC9"}]}}}
CORE = {"results": [{"id": 5, "title": "Fatigue assessment of welded joints", "authors": [{"name": "Ivan Petrov"}],
                     "yearPublished": 2015, "downloadUrl": "https://core.ac.uk/download/5.pdf"}]}


def fetch(url: str) -> str | None:
    table = {"api.semanticscholar.org/graph/v1/paper/search": S2, "europepmc/webservices/rest/search": EPMC,
             "api.archives-ouvertes.fr": HAL, "zenodo.org/api/records?": ZENODO, "api.datacite.org": DATACITE,
             "esearch.fcgi": ESEARCH, "esummary.fcgi": ESUMMARY, "api.core.ac.uk/v3/search": CORE,
             "doaj.org": {"results": []}, "crossref": {"message": {"items": []}}}
    for fragment, payload in table.items():
        if fragment in url:
            return json.dumps(payload)
    if "arxiv" in url:
        return "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
    return None


def test_new_services_merged_with_strict_open_access() -> None:
    result = find_by_topic(Q, fetch, "articles", keys={"core": "k" * 20, "semantic_scholar": "k" * 20})
    by_service = {}
    for work in result.works:
        by_service.setdefault(work.service, []).append(work)
    assert {"europe_pmc", "hal", "zenodo", "pubmed"} <= set(result.services)
    # services retirés le 2026-11-10 (non opérationnels) : jamais interrogés, même avec une clé
    assert not {"semantic_scholar", "core", "unpaywall"} & set(result.services)
    epmc = {w.item_id: w for w in by_service["europe_pmc"]}
    assert epmc["epmc:PMC1"].open_access and not epmc["epmc:MED/123"].open_access
    assert by_service["hal"][0].open_access and by_service["hal"][0].source_type == "thesis"
    pubmed = by_service["pubmed"][0]
    assert not pubmed.open_access and pubmed.doi == "10.1/pm" and "PMC9" in pubmed.license


def test_core_requires_key_and_datasets_kind() -> None:
    assert "core" not in find_by_topic(Q, fetch, "articles").services
    datasets = find_by_topic(Q, fetch, "datasets")
    assert set(datasets.services) == {"datacite", "zenodo"}
    datacite = next(w for w in datasets.works if w.service == "datacite")
    assert not datacite.open_access and datacite.doi == "10.1/dc"


def test_services_filter() -> None:
    result = find_by_topic(Q, fetch, "articles", services_filter=["hal", "pubmed"])
    assert set(result.services) == {"hal", "pubmed"}


def test_resolvers_refuse_without_open_license() -> None:
    def fetch_closed(url: str) -> str | None:
        if "graph/v1/paper/def" in url:
            return json.dumps({"openAccessPdf": {"url": "https://publisher.org/free.pdf", "license": None}})
        if "graph/v1/paper/abc" in url:
            return json.dumps({"openAccessPdf": {"url": "https://example.org/a.pdf", "license": "CCBY"}})
        if "zenodo.org/api/records/77" in url:
            return json.dumps({"metadata": ZENODO["hits"]["hits"][0]["metadata"],
                               "files": [{"key": "data.pdf", "links": {"self": "https://zenodo.org/f/data.pdf"}}]})
        return fetch(url)

    assert resolve_pdf("epmc:PMC1", fetch)[0] == "https://europepmc.org/x.pdf"
    with pytest.raises(DownloadRefused, match="Open Access"):
        resolve_pdf("epmc:MED/123", fetch)
    assert resolve_pdf("hal:hal-01", fetch)[0] == "https://hal.science/hal-01/document"
    assert resolve_pdf("zenodo:77", fetch_closed)[0] == "https://zenodo.org/f/data.pdf"
    for removed in ("s2:abc", "core:5", "unpaywall:10.1/x"):  # services retirés : refus explicite
        with pytest.raises(DownloadRefused, match="non pris en charge"):
            resolve_pdf(removed, fetch_closed)


def test_service_catalogue_is_free() -> None:
    assert {status for status, _, _ in osc.SERVICE_INFO.values()} <= {"PUBLIC_FREE", "FREE_API_KEY", "FREE_ACCOUNT"}
