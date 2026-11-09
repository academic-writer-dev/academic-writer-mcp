"""Recherche d'ouvrages et d'articles PAR THÈME dans des bases légales et ouvertes.

Bases interrogées (accès automatisé autorisé, sans compte) :
- Internet Archive (livres et manuels numérisés, dont russes et soviétiques) ;
- DOAJ (revues en libre accès) ;
- arXiv (prépublications) ;
- Crossref (métadonnées d'articles et de livres) ;
- Open Library (catalogue de livres).
Aucune bibliothèque pirate n'est utilisée. Le texte intégral n'est déclaré téléchargeable que s'il
est en libre accès légal : licence libre explicite (Creative Commons, domaine public), revue DOAJ
ou arXiv. Pour les autres ouvrages, seul le lien de consultation est fourni.
"""

from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable

from pydantic import BaseModel, Field

from academic_writer.research.models import Person, SourceData
from academic_writer.research.online import _fold, _person, _year, crossref_candidate

OPEN_LICENSE = re.compile(r"creativecommons\.org/(?:licenses|publicdomain)|publicdomain|/zero/|/mark/", re.IGNORECASE)
_STOP = {"и", "в", "на", "по", "для", "с", "о", "the", "of", "and", "in", "for", "on", "a", "de", "la", "le", "et",
         "des", "du", "les"}

TextFetcher = Callable[[str], str | None]  # texte brut (JSON ou XML), None si 404


class DiscoveredWork(BaseModel):
    item_id: str = Field(description="Identifiant à repasser à download_open_access (service:identifiant).")
    service: str
    title: str
    authors: list[str]
    year: int | None
    source_type: str
    container: str | None = None
    publisher: str | None = None
    language: str | None = None
    doi: str | None = None
    landing_url: str | None = Field(default=None, description="Page de consultation (à ouvrir dans le navigateur).")
    license: str | None = None
    open_access: bool = Field(description="Texte intégral légalement téléchargeable.")
    relevance: float = Field(description="Pertinence par rapport au thème (0 à 1).")
    data: SourceData = Field(description="Fiche pré-remplie pour register_source (à confirmer par l'utilisateur).")


class DiscoveryResult(BaseModel):
    query: str
    services: list[str]
    count: int
    works: list[DiscoveredWork]
    notices: list[str]


def relevance(query: str, *texts: str | None) -> float:
    words = {w for w in re.findall(r"\w{3,}", _fold(query)) if w not in _STOP}
    if not words:
        return 0.0
    haystack = _fold(" ".join(t for t in texts if t))
    found = sum(1 for w in words if re.search(rf"(?<!\w){re.escape(w[: max(4, len(w) - 2)])}", haystack))
    return round(found / len(words), 2)


def _json(text: str | None) -> dict:
    import json
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


# --- analyseurs ----------------------------------------------------------------------

def parse_internet_archive(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for doc in _json(text).get("response", {}).get("docs", []):
        identifier, title = doc.get("identifier"), doc.get("title")
        if not identifier or not title:
            continue
        title = title if isinstance(title, str) else " ".join(title)
        creators = doc.get("creator") or []
        creators = [creators] if isinstance(creators, str) else creators
        license_url = doc.get("licenseurl")
        year = _year(str(doc.get("year") or doc.get("date") or ""))
        subjects = doc.get("subject") or []
        subjects = " ".join([subjects] if isinstance(subjects, str) else subjects)
        works.append(DiscoveredWork(
            item_id=f"ia:{identifier}", service="internet_archive", title=title, authors=creators, year=year,
            source_type="book", publisher=doc.get("publisher") if isinstance(doc.get("publisher"), str) else None,
            language=(doc.get("language") if isinstance(doc.get("language"), str) else None),
            landing_url=f"https://archive.org/details/{identifier}", license=license_url,
            open_access=bool(license_url and OPEN_LICENSE.search(license_url)),
            relevance=relevance(query, title, subjects),
            data=SourceData(authors=[_person(c) for c in creators[:6]], title=title, year=year,
                            url=f"https://archive.org/details/{identifier}"),
        ))
    return works


def parse_doaj(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for result in _json(text).get("results", []):
        bib = result.get("bibjson", {})
        title = bib.get("title")
        if not title:
            continue
        journal = bib.get("journal", {})
        doi = next((i.get("id") for i in bib.get("identifier", []) if i.get("type", "").lower() == "doi"), None)
        authors = [a.get("name", "") for a in bib.get("author", []) if a.get("name")]
        fulltext = next((link.get("url") for link in bib.get("link", []) if link.get("type") == "fulltext"), None)
        year = _year(str(bib.get("year") or ""))
        pages = "–".join(p for p in (bib.get("start_page"), bib.get("end_page")) if p) or None
        works.append(DiscoveredWork(
            item_id=f"doaj:{result.get('id')}", service="doaj", title=title, authors=authors, year=year,
            source_type="article", container=journal.get("title"), publisher=journal.get("publisher"),
            language=(journal.get("language") or [None])[0], doi=doi, landing_url=fulltext,
            license="revue en libre accès (DOAJ)", open_access=bool(fulltext),
            relevance=relevance(query, title, " ".join(bib.get("keywords", []))),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=journal.get("title"),
                            publisher=journal.get("publisher"), year=year, volume=journal.get("volume"),
                            issue=journal.get("number"), pages=pages, doi=doi, url=fulltext,
                            issn=(journal.get("issns") or [None])[0]),
        ))
    return works


_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_arxiv(text: str | None, query: str) -> list[DiscoveredWork]:
    if not text:
        return []
    try:
        root = ET.fromstring(text)  # flux Atom d'arXiv (pas d'entités externes résolues par ElementTree)
    except ET.ParseError:
        return []
    works = []
    for entry in root.iter(f"{_ATOM}entry"):
        identifier = (entry.findtext(f"{_ATOM}id") or "").rsplit("/abs/", 1)[-1]
        title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
        if not identifier or not title:
            continue
        authors = [a.findtext(f"{_ATOM}name") or "" for a in entry.iter(f"{_ATOM}author")]
        year = _year(entry.findtext(f"{_ATOM}published"))
        summary = entry.findtext(f"{_ATOM}summary") or ""
        works.append(DiscoveredWork(
            item_id=f"arxiv:{identifier}", service="arxiv", title=title, authors=authors, year=year,
            source_type="report", publisher="arXiv", landing_url=f"https://arxiv.org/abs/{identifier}",
            license="arXiv (prépublication en libre accès)", open_access=True, relevance=relevance(query, title, summary),
            data=SourceData(authors=[_person(a) for a in authors[:10] if a], title=title, publisher="arXiv", year=year,
                            url=f"https://arxiv.org/abs/{identifier}"),
        ))
    return works


def parse_crossref(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in _json(text).get("message", {}).get("items", []):
        candidate = crossref_candidate(item)
        if not candidate.title:
            continue
        licenses = [lic.get("URL", "") for lic in item.get("license", [])]
        open_license = next((u for u in licenses if OPEN_LICENSE.search(u)), None)
        works.append(DiscoveredWork(
            item_id=f"crossref:{candidate.doi}", service="crossref", title=candidate.title, authors=candidate.authors,
            year=candidate.year, source_type=candidate.source_type or "other", container=candidate.container,
            publisher=candidate.publisher, doi=candidate.doi,
            landing_url=f"https://doi.org/{candidate.doi}" if candidate.doi else None, license=open_license,
            open_access=False, relevance=relevance(query, candidate.title, " ".join(item.get("subject", []))),
            data=candidate.data or SourceData(title=candidate.title),
        ))
    return works


def parse_open_library(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for doc in _json(text).get("docs", []):
        title = doc.get("title")
        if not title:
            continue
        authors = doc.get("author_name", [])
        isbn = (doc.get("isbn") or [None])[0]
        year = doc.get("first_publish_year")
        key = doc.get("key", "")
        works.append(DiscoveredWork(
            item_id=f"openlibrary:{key}", service="open_library", title=title, authors=authors, year=year,
            source_type="book", publisher=(doc.get("publisher") or [None])[0],
            language=(doc.get("language") or [None])[0], landing_url=f"https://openlibrary.org{key}" if key else None,
            license=None, open_access=False, relevance=relevance(query, title, " ".join(doc.get("subject", [])[:20])),
            data=SourceData(authors=[_person(a) for a in authors[:6]], title=title, year=year, isbn=isbn,
                            publisher=(doc.get("publisher") or [None])[0]),
        ))
    return works


# --- recherche ------------------------------------------------------------------------------

MIN_RELEVANCE = 0.5
_LANG_CODES = {"ru": ("rus", "russian", "ru", "русский"), "en": ("eng", "english", "en"), "fr": ("fre", "fra", "french", "fr")}


def archive_query(query: str) -> str:
    """Requête Internet Archive tolérante : radicaux des mots significatifs, reliés par OU, dans le titre ou
    les sujets (le tri par pertinence est fait localement)."""
    words = [w for w in re.findall(r"\w{4,}", query.casefold()) if w not in _STOP][:6]
    stems = [w[: max(5, len(w) - 2)] for w in words] or [query]
    terms = " OR ".join(f"title:({s}*) OR subject:({s}*)" for s in stems)
    return f"({terms}) AND mediatype:texts"


def find_by_topic(query: str, fetch: TextFetcher, kind: str = "all", open_access_only: bool = False,
                  language: str | None = None, limit: int = 10) -> DiscoveryResult:
    q = urllib.parse.quote
    per = max(3, min(limit, 25))
    plans: list[tuple[str, str, Callable]] = []
    if kind in ("books", "all"):
        fields = ("&fl[]=identifier&fl[]=title&fl[]=year&fl[]=date&fl[]=creator&fl[]=licenseurl&fl[]=language"
                  "&fl[]=publisher&fl[]=subject&output=json")
        if len(query.split()) >= 2:  # titre exact d'abord (manuels : « Теория механизмов и машин »)
            phrase = query.replace('"', "")
            plans.append(("internet_archive", "https://archive.org/advancedsearch.php?q="
                          + q(f'title:("{phrase}") AND mediatype:texts') + f"{fields}&rows={per}", parse_internet_archive))
        plans.append(("internet_archive", "https://archive.org/advancedsearch.php?q=" + q(archive_query(query))
                      + f"{fields}&rows={per * 4}", parse_internet_archive))
        if not open_access_only:
            plans.append(("open_library", f"https://openlibrary.org/search.json?limit={per}&q=" + q(query),
                          parse_open_library))
    if kind in ("articles", "all"):
        plans.append(("doaj", f"https://doaj.org/api/search/articles/{q(query)}?pageSize={per}", parse_doaj))
        plans.append(("arxiv", f"https://export.arxiv.org/api/query?max_results={per}&search_query="
                      + q(f"all:{query}"), parse_arxiv))
        if not open_access_only:
            plans.append(("crossref", f"https://api.crossref.org/works?rows={per}&query=" + q(query), parse_crossref))
    works: list[DiscoveredWork] = []
    services: list[str] = []
    notices: list[str] = []
    for name, url, parser in plans:
        if name not in services:
            services.append(name)
        try:
            works.extend(parser(fetch(url), query))
        except OSError as exc:
            notices.append(f"{name} indisponible : {exc}")
    if open_access_only:
        works = [w for w in works if w.open_access]
    if language in _LANG_CODES:
        codes = _LANG_CODES[language]
        works = [w for w in works if not w.language or _fold(w.language) in codes]
    discarded = sum(1 for w in works if w.relevance < MIN_RELEVANCE)
    works = [w for w in works if w.relevance >= MIN_RELEVANCE]
    if discarded:
        notices.append(f"{discarded} résultat(s) peu pertinent(s) écarté(s) (moins de la moitié des mots du thème).")
    seen: set[str] = set()
    unique: list[DiscoveredWork] = []
    for work in sorted(works, key=lambda w: (w.relevance, w.open_access), reverse=True):
        signature = _fold(work.title)[:60]
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(work)
    unique = unique[:limit]
    restricted = sum(1 for w in unique if w.service == "internet_archive" and not w.open_access)
    if restricted:
        notices.append(f"{restricted} ouvrage(s) d'Internet Archive sans licence libre déclarée : consultation via le "
                       "lien seulement ; le droit d'auteur peut s'appliquer (vérifier avant tout usage).")
    notices.append("Résultats issus de catalogues : présenter à l'utilisateur, qui choisit les ouvrages à enregistrer "
                   "(register_source) ou à télécharger s'ils sont en libre accès (download_open_access).")
    return DiscoveryResult(query=query, services=services, count=len(unique), works=unique, notices=notices)
