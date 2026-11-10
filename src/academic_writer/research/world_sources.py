"""Bibliothèques gratuites hors Europe et Russie, par leurs API PUBLIQUES officielles (vérifiées le 2026-11-10).

- J-STAGE (Japon, agence JST) : API de recherche publique, sans clé (flux Atom) ;
- NDL Search (Japon, Bibliothèque nationale de la Diète) : OpenSearch public, sans clé (RSS) ; robots.txt l'autorise ;
- OSTI.GOV (États-Unis, ministère de l'Énergie) : API publique, sans clé (JSON) ; robots.txt l'autorise ;
- Érudit (Canada), AJOL (Afrique), SciELO (Amérique latine, Afrique du Sud) : recherche par l'API publique Crossref,
  restreinte au préfixe DOI de chaque plateforme (10.7202 ; 10.4314 ; 10.1590, 10.4067, 10.17159) — aucune requête
  n'est envoyée à leurs sites (AJOL demande aux robots de ne pas télécharger ses PDF).

Écartés après vérification : CiNii Research et Research Data Australia (recherche interdite aux robots par
robots.txt), Library of Congress (HTTP 403), DPLA et Trove (clé personnelle requise), Redalyc (OAI vide).
Seules des métadonnées sont lues ; les textes se consultent par leur lien, dans le navigateur.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from academic_writer.research.discovery import DiscoveredWork, parse_crossref, relevance
from academic_writer.research.models import SourceData
from academic_writer.research.online import _person, _year

_ATOM = "{http://www.w3.org/2005/Atom}"
_PRISM = "{http://prismstandard.org/namespaces/basic/2.0/}"
_DC = "{http://purl.org/dc/elements/1.1/}"
_RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"

# préfixes DOI vérifiés (éditeur indiqué par Crossref)
CROSSREF_PREFIXES = {
    "erudit": ("10.7202",),                       # Consortium Érudit (Canada)
    "ajol": ("10.4314",),                         # African Journals Online
    "scielo": ("10.1590", "10.4067", "10.17159"),  # SciELO Brésil, SciELO Chili, SciELO Afrique du Sud
}
_REGIONAL_NOTES = {
    "erudit": "Érudit (Canada) : revues savantes francophones ; accès libre ou différé selon la revue",
    "ajol": "AJOL (Afrique) : revues africaines ; licence selon la revue — lire sur le site, pas de téléchargement "
            "automatique",
    "scielo": "SciELO : revues en libre accès d'Amérique latine et d'Afrique du Sud (licence CC selon la revue)",
}


def _xml(text: str | None):
    if not text:
        return None
    try:
        return ET.fromstring(text)  # ElementTree ne résout pas les entités externes
    except ET.ParseError:
        return None


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


# --- J-STAGE ------------------------------------------------------------------------------------------

def jstage_url(query: str, per: int) -> str:
    return f"https://api.jstage.jst.go.jp/searchapi/do?service=3&count={per}&keyword=" + urllib.parse.quote(query)


def parse_jstage(text: str | None, query: str) -> list[DiscoveredWork]:
    root = _xml(text)
    if root is None:
        return []
    works = []
    for entry in root.iter(f"{_ATOM}entry"):
        def get(field: str, lang: str) -> str:  # éléments dans l'espace de noms Atom par défaut
            return _clean(entry.findtext(f"{_ATOM}{field}/{_ATOM}{lang}"))

        title_en, title_ja = get("article_title", "en"), get("article_title", "ja")
        title = title_en or title_ja
        link = get("article_link", "en") or get("article_link", "ja")
        if not title or not link.startswith("https://www.jstage.jst.go.jp/"):
            continue
        names = [_clean(n.text) for n in entry.findall(f"{_ATOM}author/{_ATOM}en/{_ATOM}name") if n.text] or \
                [_clean(n.text) for n in entry.findall(f"{_ATOM}author/{_ATOM}ja/{_ATOM}name") if n.text]
        journal = get("material_title", "en") or get("material_title", "ja") or None
        doi = _clean(entry.findtext(f"{_PRISM}doi")) or None
        year = _year(entry.findtext(f"{_ATOM}pubyear"))
        first, last = _clean(entry.findtext(f"{_PRISM}startingPage")), _clean(entry.findtext(f"{_PRISM}endingPage"))
        pages = "–".join(p for p in (first, last) if p) or None
        language = "en" if title_en and not title_ja else ("ja" if title_ja and not title_en else None)
        works.append(DiscoveredWork(
            item_id=f"jstage:{doi or link}", service="jstage", title=title, authors=names, year=year,
            source_type="article", container=journal, publisher="J-STAGE (JST)", language=language, doi=doi,
            landing_url=link, license="J-STAGE : lecture gratuite sur le site ; licence selon la revue",
            open_access=False, relevance=relevance(query, title_en, title_ja),
            data=SourceData(authors=[_person(n) for n in names[:10]], title=title, container=journal, year=year,
                            volume=_clean(entry.findtext(f"{_PRISM}volume")) or None,
                            issue=_clean(entry.findtext(f"{_PRISM}number")) or None, pages=pages, doi=doi,
                            issn=_clean(entry.findtext(f"{_PRISM}issn")) or None, url=link)))
    return works


# --- NDL Search ---------------------------------------------------------------------------------------

_NDL_TYPES = {"図書": "book", "記事": "article", "博士論文": "thesis", "雑誌": "article", "規格": "standard"}


def ndl_url(query: str, per: int) -> str:
    return f"https://ndlsearch.ndl.go.jp/api/opensearch?cnt={per}&any=" + urllib.parse.quote(query)


def parse_ndl(text: str | None, query: str) -> list[DiscoveredWork]:
    root = _xml(text)
    if root is None:
        return []
    works = []
    for item in root.iter("item"):
        title = _clean(item.findtext(f"{_DC}title")) or _clean(item.findtext("title"))
        link = _clean(item.findtext("link"))
        if not title or not link.startswith("https://ndlsearch.ndl.go.jp/"):
            continue
        creators = [_clean(c.text) for c in item.iter(f"{_DC}creator") if c.text]
        categories = [_clean(c.text) for c in item.iter("category") if c.text]
        source_type = next((_NDL_TYPES[c] for c in categories if c in _NDL_TYPES), "other")
        subjects = " ".join(_clean(s.text) for s in item.iter(f"{_DC}subject") if s.text)
        description = _clean(item.findtext(f"{_DC}description"))
        doi = None
        for see in item.iter(f"{_RDFS}seeAlso"):
            target = see.get(f"{_RDF}resource") or ""
            if target.startswith("https://doi.org/10."):
                doi = target.removeprefix("https://doi.org/")
        year = _year(item.findtext(f"{_DC}date"))
        publisher = _clean(item.findtext(f"{_DC}publisher")) or None
        works.append(DiscoveredWork(
            item_id=f"ndl:{link.rsplit('/', 1)[-1]}", service="ndl", title=title, authors=creators, year=year,
            source_type=source_type, publisher=publisher, language=None, doi=doi, landing_url=link,
            license="NDL Search : notice de catalogue ; accès au document selon la bibliothèque",
            open_access=False, relevance=relevance(query, title, subjects, description),
            data=SourceData(authors=[_person(c) for c in creators[:10]], title=title, year=year, publisher=publisher,
                            doi=doi, url=link)))
    return works


# --- OSTI.GOV -----------------------------------------------------------------------------------------

_OSTI_TYPES = {"journal article": "article", "technical report": "report", "conference": "conference",
               "thesis/dissertation": "thesis", "dataset": "dataset", "book": "book", "program document": "report"}


def osti_url(query: str, per: int) -> str:
    return f"https://www.osti.gov/api/v1/records?rows={per}&q=" + urllib.parse.quote(query)


def _osti_author(raw: str) -> str:
    return _clean(re.sub(r"\[[^\]]*\]|\(ORCID:[^)]*\)", "", raw))


def parse_osti(text: str | None, query: str) -> list[DiscoveredWork]:
    try:
        records = json.loads(text) if text else []
    except ValueError:
        return []
    works = []
    for record in records if isinstance(records, list) else []:
        title, osti_id = _clean(record.get("title")), str(record.get("osti_id") or "")
        if not title or not osti_id.isdigit():
            continue
        authors = [_osti_author(a) for a in record.get("authors") or [] if isinstance(a, str)]
        authors = [a for a in authors if a]
        landing = f"https://www.osti.gov/biblio/{osti_id}"
        has_fulltext = any(link.get("rel") == "fulltext" for link in record.get("links") or [])
        year = _year(record.get("publication_date"))
        doi = record.get("doi") or None
        journal = record.get("journal_name") or None
        language = {"english": "en", "french": "fr", "russian": "ru"}.get(str(record.get("language", "")).lower())
        works.append(DiscoveredWork(
            item_id=f"osti:{osti_id}", service="osti", title=title, authors=authors, year=year,
            source_type=_OSTI_TYPES.get(str(record.get("product_type", "")).lower(), "report"), container=journal,
            publisher=(record.get("research_orgs") or [None])[0], language=language, doi=doi, landing_url=landing,
            license=("OSTI.GOV : texte intégral consultable sur le site (droits selon le document)" if has_fulltext
                     else "OSTI.GOV : notice ; texte selon l'éditeur"),
            open_access=False, relevance=relevance(query, title, " ".join(record.get("subjects") or [])),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=journal, year=year,
                            doi=doi, url=landing, publisher=(record.get("research_orgs") or [None])[0],
                            notes=record.get("report_number") or None)))
    return works


# --- Érudit, AJOL, SciELO (via Crossref, filtre par préfixe DOI) --------------------------------------

def regional_crossref_url(service: str, query: str, per: int) -> str:
    prefixes = ",".join(f"prefix:{p}" for p in CROSSREF_PREFIXES[service])
    return f"https://api.crossref.org/works?rows={per}&filter={prefixes}&query=" + urllib.parse.quote(query)


def regional_parser(service: str):
    def parse(text: str | None, query: str) -> list[DiscoveredWork]:
        works = parse_crossref(text, query)
        for work in works:
            work.service = service
            work.license = work.license or _REGIONAL_NOTES[service]
        return works
    parse.__name__ = f"parse_{service}"
    return parse


def plans(query: str, per: int, kind: str) -> list[tuple]:
    """Plans de recherche (service, URL, analyseur) pour find_by_topic."""
    found: list[tuple] = []
    if kind in ("articles", "all"):
        found.append(("jstage", jstage_url(query, per), parse_jstage))
        found.append(("osti", osti_url(query, per), parse_osti))
        for service in CROSSREF_PREFIXES:
            found.append((service, regional_crossref_url(service, query, per), regional_parser(service)))
    if kind in ("books", "articles", "all"):
        found.append(("ndl", ndl_url(query, per), parse_ndl))
    return found
