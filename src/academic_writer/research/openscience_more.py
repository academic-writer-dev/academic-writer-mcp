"""Bases et services ouverts supplémentaires (vérifiés en réel le 2026-11-10) :

- OpenAlex (travaux ; filtres année / type ; indicateur is_retracted ; clé gratuite facultative, budget journalier) ;
- OpenAIRE Graph (publications, données, logiciels européens) ; ERIC (sciences de l'éducation) ;
- Deutsche Nationalbibliothek (catalogue, SRU) ; ORCID (identifiants de chercheurs) ;
- Crossref « updates » (rétractations, corrections, avis d'inquiétude) ;
- World Bank et Eurostat (données statistiques ouvertes).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from pydantic import BaseModel, Field

from academic_writer.research.discovery import DiscoveredWork, TextFetcher, relevance
from academic_writer.research.models import SourceData
from academic_writer.research.online import _person, _year
from academic_writer.research.openscience import _open_license

q = urllib.parse.quote
TYPE_MAP = {"article": "article", "book": "book", "book-chapter": "chapter", "dissertation": "thesis",
            "preprint": "report", "dataset": "other", "report": "report", "proceedings-article": "conference",
            "review": "article"}


def _json(text: str | None) -> dict:
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


# --- OpenAlex --------------------------------------------------------------------------------------------

def openalex_url(query: str, per: int, year_from: int | None = None, year_to: int | None = None,
                 kind: str | None = None, key: str | None = None) -> str:
    filters = []
    if year_from or year_to:
        filters.append(f"publication_year:{year_from or 1000}-{year_to or 2100}")
    if kind:
        filters.append(f"type:{kind}")
    url = f"https://api.openalex.org/works?per_page={per}&search={q(query)}"
    if filters:
        url += "&filter=" + q(",".join(filters), safe=":,-")
    return url + (f"&api_key={q(key)}" if key else "")


def parse_openalex(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in _json(text).get("results", []) or []:
        title, work_id = item.get("display_name"), str(item.get("id", "")).rsplit("/", 1)[-1]
        if not title or not work_id:
            continue
        authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])
                   if a.get("author", {}).get("display_name")]
        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        best = item.get("best_oa_location") or {}
        container = ((item.get("primary_location") or {}).get("source") or {}).get("display_name")
        is_open = bool(best.get("pdf_url")) and str(best.get("pdf_url")).startswith("https://") \
            and _open_license(best.get("license"))
        retracted = bool(item.get("is_retracted"))
        works.append(DiscoveredWork(
            item_id=f"openalex:{work_id}", service="openalex", title=("[RÉTRACTÉ] " if retracted else "") + title,
            authors=authors, year=item.get("publication_year"), source_type=TYPE_MAP.get(item.get("type"), "other"),
            container=container, language=item.get("language"), doi=doi,
            landing_url=f"https://doi.org/{doi}" if doi else item.get("id"),
            license=best.get("license") or ("lecture libre, licence non précisée" if (item.get("open_access") or {})
                                            .get("is_oa") else None),
            open_access=is_open and not retracted, relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=container,
                            year=item.get("publication_year"), doi=doi)))
    return works


# --- OpenAIRE Graph -----------------------------------------------------------------------------------------

def openaire_url(query: str, per: int) -> str:
    return f"https://api.openaire.eu/graph/v1/researchProducts?search={q(query)}&pageSize={per}"


def parse_openaire(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in _json(text).get("results", []) or []:
        title = item.get("mainTitle")
        if not title or not item.get("id"):
            continue
        authors = [a.get("fullName", "") for a in item.get("authors") or [] if a.get("fullName")]
        instances = item.get("instances") or []
        doi = next((p.get("value") for inst in instances for p in (inst.get("alternateIdentifiers") or []) + (inst.get("pids") or [])
                    if (p.get("scheme") or "").lower() == "doi"), None)
        open_instance = next((inst for inst in instances if _open_license(inst.get("license"))
                              and any(str(u).startswith("https://") for u in inst.get("urls") or [])), None)
        url = next((u for inst in instances for u in inst.get("urls") or []), None)
        kind = item.get("type") or "publication"
        works.append(DiscoveredWork(
            item_id=f"openaire:{item['id']}", service="openaire", title=title, authors=authors,
            year=_year(item.get("publicationDate") or ""),
            source_type="article" if kind == "publication" else "other",
            container=(item.get("container") or {}).get("name") if isinstance(item.get("container"), dict) else None,
            publisher=item.get("publisher"), language=(item.get("language") or {}).get("label"), doi=doi,
            landing_url=f"https://doi.org/{doi}" if doi else url,
            license=(open_instance or {}).get("license") or (item.get("bestAccessRight") or {}).get("label"),
            open_access=False,  # page de dépôt, pas un PDF garanti : consultation par le lien
            relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, publisher=item.get("publisher"),
                            year=_year(item.get("publicationDate") or ""), doi=doi, url=url)))
    return works


# --- ERIC ------------------------------------------------------------------------------------------------------

ERIC_FIELDS = "id,title,author,publicationdateyear,source,peerreviewed,publicationtype,e_fulltextauth,url,language"


def eric_url(query: str, per: int) -> str:
    return f"https://api.ies.ed.gov/eric/?format=json&rows={per}&fields={ERIC_FIELDS}&search={q(query)}"


def parse_eric(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for doc in (_json(text).get("response") or {}).get("docs", []):
        title = (doc.get("title") or "").replace("&apos;", "'")
        if not title or not doc.get("id"):
            continue
        authors = doc.get("author") or []
        url = doc.get("url")
        doi = url.split("doi.org/")[-1] if url and "doi.org/" in url else None
        full_text = doc.get("e_fulltextauth") == 1
        works.append(DiscoveredWork(
            item_id=f"eric:{doc['id']}", service="eric", title=title, authors=authors, year=doc.get("publicationdateyear"),
            source_type="article" if "Journal Articles" in (doc.get("publicationtype") or []) else "report",
            container=doc.get("source"), language=(doc.get("language") or [None])[0], doi=doi,
            landing_url=f"https://eric.ed.gov/?id={doc['id']}",
            license="; ".join(x for x in ("texte intégral diffusé par ERIC" if full_text else None,
                                          "évalué par les pairs" if doc.get("peerreviewed") == "T" else None) if x)
            or None,
            open_access=False, relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=doc.get("source"),
                            year=doc.get("publicationdateyear"), doi=doi)))
    return works


# --- Deutsche Nationalbibliothek (SRU, Dublin Core) -------------------------------------------------------------

_DC = "{http://purl.org/dc/elements/1.1/}"


def dnb_url(query: str, per: int) -> str:
    return ("https://services.dnb.de/sru/dnb?version=1.1&operation=searchRetrieve&recordSchema=oai_dc"
            f"&maximumRecords={per}&query={q(query)}")


def parse_dnb(text: str | None, query: str) -> list[DiscoveredWork]:
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    works = []
    for record in root.iter("{http://www.openarchives.org/OAI/2.0/oai_dc/}dc"):
        raw_title = record.findtext(f"{_DC}title") or ""
        title = raw_title.split(" / ")[0].strip()
        if not title:
            continue
        creators = [re.sub(r"\s*\[[^\]]*\]?|\]", "", c.text or "").strip(" [") for c in record.iter(f"{_DC}creator")]
        xsi_type = "{http://www.w3.org/2001/XMLSchema-instance}type"
        isbn = next((re.match(r"[\d\-Xx]{10,17}", (i.text or "")).group(0) for i in record.iter(f"{_DC}identifier")
                     if "ISBN" in (i.get(xsi_type) or "") and re.match(r"[\d\-Xx]{10,17}", i.text or "")), None)
        idn = next((i.text for i in record.iter(f"{_DC}identifier") if i.text and re.fullmatch(r"\d{8,9}[\dX]", i.text)), None)
        publisher = record.findtext(f"{_DC}publisher")
        year = _year(record.findtext(f"{_DC}date") or "")
        works.append(DiscoveredWork(
            item_id=f"dnb:{idn or isbn or title[:30]}", service="dnb", title=title, authors=[c for c in creators if c],
            year=year, source_type="book", publisher=publisher, language=record.findtext(f"{_DC}language"),
            landing_url=f"https://d-nb.info/{idn}" if idn else None, license=None, open_access=False,
            relevance=relevance(query, raw_title, " ".join((s.text or "") for s in record.iter(f"{_DC}subject"))),
            data=SourceData(authors=[_person(c) for c in creators[:6] if c], title=title, year=year, isbn=isbn,
                            publisher=publisher.split(" : ")[-1] if publisher else None,
                            place=publisher.split(" : ")[0] if publisher and " : " in publisher else None)))
    return works


# --- ORCID ----------------------------------------------------------------------------------------------------------

class Researcher(BaseModel):
    orcid: str
    given_names: str | None
    family_names: str | None
    institutions: list[str] = Field(default_factory=list)
    url: str


def search_orcid(family: str, given: str | None, fetch: TextFetcher, rows: int = 10) -> list[Researcher]:
    query = f"family-name:{family}" + (f" AND given-names:{given}" if given else "")
    text = fetch(f"https://pub.orcid.org/v3.0/expanded-search/?rows={rows}&q={q(query)}")
    if not text:
        return []
    ns = "{http://www.orcid.org/ns/expanded-search}"
    root = ET.fromstring(text)
    found = []
    for result in root.iter(f"{ns}expanded-result"):
        orcid = result.findtext(f"{ns}orcid-id")
        if orcid:
            found.append(Researcher(orcid=orcid, given_names=result.findtext(f"{ns}given-names"),
                                    family_names=result.findtext(f"{ns}family-names"),
                                    institutions=[i.text for i in result.iter(f"{ns}institution-name") if i.text][:5],
                                    url=f"https://orcid.org/{orcid}"))
    return found


# --- rétractations (Crossref « updates ») ------------------------------------------------------------------------------

class UpdateNotice(BaseModel):
    type: str = Field(description="retraction, withdrawal, expression_of_concern, correction…")
    notice_doi: str | None
    notice_title: str | None
    date: str | None


def crossref_updates(doi: str, fetch: TextFetcher) -> list[UpdateNotice]:
    data = _json(fetch(f"https://api.crossref.org/works?rows=10&filter=updates:{q(doi, safe='/')}"))
    notices = []
    for item in (data.get("message") or {}).get("items", []):
        for update in item.get("update-to", []):
            if (update.get("DOI") or "").casefold() == doi.casefold():
                parts = ((update.get("updated") or {}).get("date-parts") or [[None]])[0]
                notices.append(UpdateNotice(type=update.get("type", "update"), notice_doi=item.get("DOI"),
                                            notice_title=(item.get("title") or [None])[0],
                                            date="-".join(str(p) for p in parts if p) or None))
    return notices


# --- données ouvertes : World Bank, Eurostat ----------------------------------------------------------------------------

class DataPoint(BaseModel):
    dimensions: dict[str, str]
    value: float | None


class OpenDataResult(BaseModel):
    provider: str
    dataset: str
    label: str | None
    source_url: str
    updated: str | None
    points: list[DataPoint]
    notice: str = "Valeurs telles que publiées par l'organisme ; citer la source, le jeu de données et la date."


def worldbank(indicator: str, country: str, years: str | None, fetch: TextFetcher) -> OpenDataResult:
    if not re.fullmatch(r"[A-Za-z0-9.]{3,40}", indicator) or not re.fullmatch(r"[A-Za-z;]{2,40}", country):
        raise ValueError("Indicateur (ex. NY.GDP.MKTP.CD) ou pays (code ISO, ex. FR;RU) invalide.")
    url = (f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=500"
           + (f"&date={q(years, safe=':')}" if years else ""))
    data = json.loads(fetch(url) or "[]")
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        message = data[0].get("message", [{}])[0].get("value") if data and isinstance(data[0], dict) else None
        raise ValueError(f"Aucune donnée World Bank ({message or 'indicateur ou pays inconnu'}).")
    rows = data[1]
    return OpenDataResult(provider="World Bank", dataset=indicator, label=rows[0]["indicator"]["value"], source_url=url,
                          updated=data[0].get("lastupdated"),
                          points=[DataPoint(dimensions={"country": r["country"]["value"], "year": r["date"]},
                                            value=r["value"]) for r in rows])


def eurostat(dataset: str, filters: dict[str, str], fetch: TextFetcher) -> OpenDataResult:
    if not re.fullmatch(r"[A-Za-z0-9_]{3,40}", dataset):
        raise ValueError("Code de jeu de données Eurostat invalide (ex. nama_10_gdp).")
    params = "&".join(f"{q(k)}={q(v)}" for k, v in filters.items())
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?{params}"
    data = _json(fetch(url))
    if not data.get("id"):
        raise ValueError("Aucune donnée Eurostat (jeu ou filtres inconnus).")
    dims, sizes = data["id"], data["size"]
    labels = {d: {pos: (code, data["dimension"][d]["category"].get("label", {}).get(code, code))
                  for code, pos in data["dimension"][d]["category"]["index"].items()} for d in dims}
    points = []
    for flat, value in sorted(((int(k), v) for k, v in (data.get("value") or {}).items())):
        coords, rest = {}, flat
        for d, size in zip(reversed(dims), reversed(sizes), strict=True):
            coords[d] = labels[d][rest % size][1]
            rest //= size
        points.append(DataPoint(dimensions={d: coords[d] for d in dims}, value=value))
    return OpenDataResult(provider="Eurostat", dataset=dataset, label=data.get("label"), source_url=url,
                          updated=data.get("updated"), points=points[:2000])
