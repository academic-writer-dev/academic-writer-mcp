"""Bases scientifiques ouvertes supplémentaires (accès gratuit, automatisation autorisée par leurs conditions).

| Base            | Accès                                   | Contenu                                         |
|-----------------|-----------------------------------------|-------------------------------------------------|
| Semantic Scholar| public (clé gratuite facultative)       | métadonnées, PDF en libre accès signalés        |
| Europe PMC      | public                                  | biomédecine ; sous-ensemble Open Access (CC)    |
| PubMed (NCBI)   | public (E-utilities, 3 requêtes/s)      | biomédecine : métadonnées seulement             |
| HAL             | public                                  | archive ouverte française : dépôts en libre accès|
| DataCite        | public                                  | jeux de données, logiciels (DOI) : métadonnées  |
| Zenodo          | public                                  | publications et données, licence par dépôt      |
| CORE            | clé API gratuite obligatoire            | agrégateur de dépôts en libre accès             |
| Unpaywall       | adresse e-mail obligatoire (paramètre)  | localisation légale du texte intégral d'un DOI  |

Règle constante : ``open_access`` (téléchargeable) n'est vrai que si une licence libre (Creative Commons,
domaine public) ou un dépôt en archive ouverte est attesté par la base. « Lecture gratuite » sans licence
ouverte n'est PAS présentée comme un accès libre au texte intégral.
"""

from __future__ import annotations

import json
import re
import urllib.parse

from academic_writer.research.discovery import OPEN_LICENSE, DiscoveredWork, TextFetcher, relevance
from academic_writer.research.models import SourceData
from academic_writer.research.online import _person, _year

_CC = re.compile(r"^(?:cc[\s\-_]?|creative\s*commons|public[\s\-_]?domain|pd\b|cc0)", re.IGNORECASE)

SERVICE_INFO = {
    "semantic_scholar": ("PUBLIC_FREE", "https://api.semanticscholar.org", "Clé gratuite facultative (quota plus élevé)."),
    "europe_pmc": ("PUBLIC_FREE", "https://www.ebi.ac.uk/europepmc/webservices/rest", "Sans compte."),
    "pubmed": ("PUBLIC_FREE", "https://eutils.ncbi.nlm.nih.gov", "Sans compte ; 3 requêtes/s sans clé."),
    "hal": ("PUBLIC_FREE", "https://api.archives-ouvertes.fr", "Sans compte."),
    "datacite": ("PUBLIC_FREE", "https://api.datacite.org", "Sans compte."),
    "zenodo": ("PUBLIC_FREE", "https://zenodo.org/api", "Sans compte pour la recherche."),
    "core": ("FREE_API_KEY", "https://api.core.ac.uk/v3", "Clé API gratuite obligatoire (inscription)."),
    "unpaywall": ("FREE_ACCOUNT", "https://api.unpaywall.org/v2", "Adresse e-mail obligatoire dans chaque requête."),
}


def _json(text: str | None) -> dict:
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


def _open_license(value: str | None) -> bool:
    return bool(value) and bool(_CC.search(value) or OPEN_LICENSE.search(value))


# --- Semantic Scholar -------------------------------------------------------------------------------

S2_FIELDS = "title,authors,year,venue,externalIds,isOpenAccess,openAccessPdf,publicationTypes"


def semantic_scholar_url(query: str, limit: int, api_key: str | None = None) -> str:
    return (f"https://api.semanticscholar.org/graph/v1/paper/search?limit={limit}&fields={S2_FIELDS}&query="
            + urllib.parse.quote(query))


def parse_semantic_scholar(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for paper in _json(text).get("data", []) or []:
        title, paper_id = paper.get("title"), paper.get("paperId")
        if not title or not paper_id:
            continue
        authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]
        doi = (paper.get("externalIds") or {}).get("DOI")
        pdf = paper.get("openAccessPdf") or {}
        license_name = pdf.get("license")
        is_open = bool(pdf.get("url")) and _open_license(license_name)
        note = (f"licence {license_name}" if license_name else
                "lecture gratuite signalée, licence non précisée" if pdf.get("url") else None)
        works.append(DiscoveredWork(
            item_id=f"s2:{paper_id}", service="semantic_scholar", title=title, authors=authors, year=paper.get("year"),
            source_type="article", container=paper.get("venue") or None, doi=doi,
            landing_url=f"https://www.semanticscholar.org/paper/{paper_id}", license=note, open_access=is_open,
            relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=paper.get("venue") or None,
                            year=paper.get("year"), doi=doi)))
    return works


# --- Europe PMC ---------------------------------------------------------------------------------------

def europe_pmc_url(query: str, limit: int) -> str:
    return ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core"
            f"&pageSize={limit}&query=" + urllib.parse.quote(query))


def parse_europe_pmc(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in (_json(text).get("resultList") or {}).get("result", []):
        title = (item.get("title") or "").rstrip(".")
        if not title:
            continue
        authors = [a.get("fullName", "") for a in (item.get("authorList") or {}).get("author", []) if a.get("fullName")]
        if not authors and item.get("authorString"):
            authors = [a.strip() for a in item["authorString"].rstrip(".").split(",") if a.strip()]
        journal = ((item.get("journalInfo") or {}).get("journal") or {}).get("title")
        pmcid = item.get("pmcid")
        license_name = item.get("license")
        is_open = item.get("isOpenAccess") == "Y" and bool(pmcid) and _open_license(license_name)
        works.append(DiscoveredWork(
            item_id=f"epmc:{pmcid or item.get('source', 'MED') + '/' + str(item.get('id'))}", service="europe_pmc",
            title=title, authors=authors, year=_year(str(item.get("pubYear") or "")), source_type="article",
            container=journal, language=item.get("language"), doi=item.get("doi"),
            landing_url=f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}",
            license=license_name, open_access=is_open, relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=journal,
                            year=_year(str(item.get("pubYear") or "")),
                            volume=(item.get("journalInfo") or {}).get("volume"),
                            issue=(item.get("journalInfo") or {}).get("issue"), pages=item.get("pageInfo"),
                            doi=item.get("doi"))))
    return works


# --- PubMed (deux requêtes : esearch puis esummary) ----------------------------------------------------

def search_pubmed(query: str, fetch: TextFetcher, limit: int) -> list[DiscoveredWork]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ids = (_json(fetch(f"{base}/esearch.fcgi?db=pubmed&retmode=json&tool=AcademicWriterMCP&retmax={limit}&term="
                       + urllib.parse.quote(query))).get("esearchresult") or {}).get("idlist", [])
    if not ids:
        return []
    summary = _json(fetch(f"{base}/esummary.fcgi?db=pubmed&retmode=json&tool=AcademicWriterMCP&id=" + ",".join(ids)))
    return parse_pubmed_summary(summary, query)


def parse_pubmed_summary(summary: dict, query: str) -> list[DiscoveredWork]:
    result = summary.get("result") or {}
    works = []
    for uid in result.get("uids", []):
        item = result.get(uid) or {}
        title = (item.get("title") or "").rstrip(".")
        if not title:
            continue
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        ids = {a.get("idtype"): a.get("value") for a in item.get("articleids", [])}
        doi = ids.get("doi")
        year = _year(item.get("pubdate") or "")
        pmc = ids.get("pmc")
        works.append(DiscoveredWork(
            item_id=f"pubmed:{uid}", service="pubmed", title=title, authors=authors, year=year, source_type="article",
            container=item.get("fulljournalname") or item.get("source"),
            language=(item.get("lang") or [None])[0], doi=doi, landing_url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            license=(f"version PMC disponible ({pmc}) — licence à vérifier sur Europe PMC" if pmc else None),
            open_access=False, relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title,
                            container=item.get("fulljournalname") or item.get("source"), year=year,
                            volume=item.get("volume"), issue=item.get("issue"), pages=item.get("pages"), doi=doi)))
    return works


# --- HAL ------------------------------------------------------------------------------------------------

HAL_FIELDS = ("halId_s,title_s,authFullName_s,producedDateY_i,doiId_s,uri_s,fileMain_s,docType_s,journalTitle_s,"
              "language_s,licence_s")


def hal_url(query: str, limit: int) -> str:
    return f"https://api.archives-ouvertes.fr/search/?wt=json&rows={limit}&fl={HAL_FIELDS}&q=" + urllib.parse.quote(query)


_HAL_TYPES = {"ART": "article", "COMM": "conference", "OUV": "book", "COUV": "chapter", "THESE": "thesis",
              "REPORT": "report", "HDR": "thesis", "MEM": "thesis"}


def parse_hal(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for doc in (_json(text).get("response") or {}).get("docs", []):
        titles = doc.get("title_s") or []
        title = titles[0] if isinstance(titles, list) and titles else titles if isinstance(titles, str) else None
        if not title or not doc.get("halId_s"):
            continue
        authors = doc.get("authFullName_s") or []
        file_url = doc.get("fileMain_s")
        is_open = bool(file_url) and str(file_url).lower().startswith("https://")
        source_type = _HAL_TYPES.get(doc.get("docType_s", ""), "other")
        works.append(DiscoveredWork(
            item_id=f"hal:{doc['halId_s']}", service="hal", title=title, authors=authors, year=doc.get("producedDateY_i"),
            source_type=source_type, container=doc.get("journalTitle_s"), language=(doc.get("language_s") or [None])[0],
            doi=doc.get("doiId_s"), landing_url=doc.get("uri_s"),
            license=doc.get("licence_s") or ("dépôt en archive ouverte HAL" if is_open else None), open_access=is_open,
            relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=doc.get("journalTitle_s"),
                            year=doc.get("producedDateY_i"), doi=doc.get("doiId_s"), url=doc.get("uri_s"))))
    return works


# --- DataCite --------------------------------------------------------------------------------------------

def datacite_url(query: str, limit: int) -> str:
    return f"https://api.datacite.org/dois?page%5Bsize%5D={limit}&query=" + urllib.parse.quote(query)


def parse_datacite(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in _json(text).get("data", []) or []:
        attributes = item.get("attributes") or {}
        title = next((t.get("title") for t in attributes.get("titles", []) if t.get("title")), None)
        doi = attributes.get("doi") or item.get("id")
        if not title or not doi:
            continue
        authors = [c.get("name", "") for c in attributes.get("creators", []) if c.get("name")]
        publisher = attributes.get("publisher")
        publisher = publisher.get("name") if isinstance(publisher, dict) else publisher
        rights = next((r.get("rightsUri") or r.get("rights") for r in attributes.get("rightsList", [])), None)
        kind = ((attributes.get("types") or {}).get("resourceTypeGeneral") or "").lower()
        works.append(DiscoveredWork(
            item_id=f"datacite:{doi}", service="datacite", title=title, authors=authors,
            year=attributes.get("publicationYear"), source_type="article" if kind in ("journalarticle", "text") else "other",
            publisher=publisher, language=attributes.get("language"), doi=doi, landing_url=f"https://doi.org/{doi}",
            license=rights, open_access=False, relevance=relevance(query, title),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, publisher=publisher,
                            year=attributes.get("publicationYear"), doi=doi)))
    return works


# --- Zenodo -----------------------------------------------------------------------------------------------

def zenodo_url(query: str, limit: int) -> str:
    return f"https://zenodo.org/api/records?size={limit}&q=" + urllib.parse.quote(query)


def _zenodo_open(metadata: dict) -> tuple[bool, str | None]:
    license_id = (metadata.get("license") or {}).get("id") if isinstance(metadata.get("license"), dict) else None
    return metadata.get("access_right") == "open" and _open_license(license_id), license_id


def parse_zenodo(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for hit in (_json(text).get("hits") or {}).get("hits", []):
        metadata = hit.get("metadata") or {}
        title = metadata.get("title")
        if not title or not hit.get("id"):
            continue
        authors = [c.get("name", "") for c in metadata.get("creators", []) if c.get("name")]
        is_open, license_id = _zenodo_open(metadata)
        resource = (metadata.get("resource_type") or {}).get("type", "")
        works.append(DiscoveredWork(
            item_id=f"zenodo:{hit['id']}", service="zenodo", title=title, authors=authors,
            year=_year(metadata.get("publication_date") or ""),
            source_type="article" if resource == "publication" else "other", doi=metadata.get("doi") or hit.get("doi"),
            landing_url=(hit.get("links") or {}).get("self_html") or f"https://zenodo.org/records/{hit['id']}",
            license=license_id, open_access=is_open, relevance=relevance(query, title, metadata.get("description")),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title,
                            year=_year(metadata.get("publication_date") or ""), publisher="Zenodo",
                            doi=metadata.get("doi") or hit.get("doi"))))
    return works


# --- CORE (clé gratuite obligatoire) --------------------------------------------------------------------

def core_url(query: str, limit: int, api_key: str) -> str:
    return (f"https://api.core.ac.uk/v3/search/works?limit={limit}&apiKey={urllib.parse.quote(api_key)}&q="
            + urllib.parse.quote(query))


def parse_core(text: str | None, query: str) -> list[DiscoveredWork]:
    works = []
    for item in _json(text).get("results", []) or []:
        title, core_id = item.get("title"), item.get("id")
        if not title or not core_id:
            continue
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        download = item.get("downloadUrl") or ""
        is_open = download.lower().startswith("https://")
        journal = next((j.get("title") for j in item.get("journals", []) or [] if j.get("title")), None)
        works.append(DiscoveredWork(
            item_id=f"core:{core_id}", service="core", title=title, authors=authors, year=item.get("yearPublished"),
            source_type="article", container=journal, publisher=item.get("publisher"),
            language=(item.get("language") or {}).get("code") if isinstance(item.get("language"), dict) else None,
            doi=item.get("doi"), landing_url=f"https://core.ac.uk/works/{core_id}",
            license="dépôt en libre accès (agrégé par CORE)" if is_open else None, open_access=is_open,
            relevance=relevance(query, title, item.get("abstract")),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=journal,
                            publisher=item.get("publisher"), year=item.get("yearPublished"), doi=item.get("doi"))))
    return works


# --- Unpaywall (enrichissement par DOI) ------------------------------------------------------------------

def unpaywall_location(doi: str, email: str, fetch: TextFetcher) -> tuple[str | None, str | None]:
    """(adresse légale du PDF, licence) d'après Unpaywall ; (None, None) si aucune version ouverte."""
    record = _json(fetch(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"))
    best = record.get("best_oa_location") or {}
    return best.get("url_for_pdf") or None, best.get("license") or None


# --- résolution du texte intégral --------------------------------------------------------------------------

def resolve(service: str, identifier: str, fetch: TextFetcher, keys: dict[str, str] | None = None) -> tuple[str, str, str] | None:
    """(PDF, licence, nom de fichier) pour les nouvelles bases ; None si le service n'est pas concerné.
    Lève ValueError avec un message destiné à l'utilisateur si le libre accès n'est pas attesté."""
    keys = keys or {}
    if service == "s2":
        paper = _json(fetch(f"https://api.semanticscholar.org/graph/v1/paper/{urllib.parse.quote(identifier)}"
                            "?fields=openAccessPdf"))
        pdf = paper.get("openAccessPdf") or {}
        if not pdf.get("url") or not _open_license(pdf.get("license")):
            raise ValueError("Semantic Scholar ne déclare pas de licence libre pour ce texte : téléchargement refusé, "
                             "consultez le lien de la notice.")
        return pdf["url"], f"licence {pdf.get('license')}", f"s2-{identifier[:20]}.pdf"
    if service == "epmc":
        if not identifier.upper().startswith("PMC"):
            raise ValueError("Seuls les articles du sous-ensemble Open Access de PubMed Central sont téléchargeables.")
        record = _json(fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core"
                             "&query=" + urllib.parse.quote(f"PMCID:{identifier}")))
        item = next(iter((record.get("resultList") or {}).get("result", [])), {})
        if item.get("isOpenAccess") != "Y" or not _open_license(item.get("license")):
            raise ValueError("Article sans licence ouverte dans Europe PMC : téléchargement refusé.")
        links = (item.get("fullTextUrlList") or {}).get("fullTextUrl", [])
        url = next((u.get("url") for u in links if u.get("documentStyle") == "pdf"
                    and str(u.get("url", "")).lower().startswith("https://")), None)
        if not url:
            raise ValueError("Pas de PDF HTTPS déclaré par Europe PMC pour cet article.")
        return url, f"licence {item.get('license')}", f"{identifier}.pdf"
    if service == "hal":
        record = _json(fetch(f"https://api.archives-ouvertes.fr/search/?wt=json&fl=fileMain_s,licence_s&q=halId_s:"
                             + urllib.parse.quote(identifier)))
        doc = next(iter((record.get("response") or {}).get("docs", [])), {})
        url = doc.get("fileMain_s")
        if not url or not str(url).lower().startswith("https://"):
            raise ValueError("Pas de fichier déposé en libre accès dans HAL pour cette notice.")
        return url, doc.get("licence_s") or "dépôt en archive ouverte HAL", f"hal-{identifier}.pdf"
    if service == "zenodo":
        record = _json(fetch(f"https://zenodo.org/api/records/{urllib.parse.quote(identifier)}"))
        is_open, license_id = _zenodo_open(record.get("metadata") or {})
        if not is_open:
            raise ValueError("Dépôt Zenodo sans accès ouvert sous licence libre : téléchargement refusé.")
        pdf = next((f for f in record.get("files", []) if str(f.get("key", "")).lower().endswith(".pdf")), None)
        url = ((pdf or {}).get("links") or {}).get("self")
        if not url:
            raise ValueError("Aucun fichier PDF dans ce dépôt Zenodo.")
        return url, f"licence {license_id}", pdf["key"].rsplit("/", 1)[-1]
    if service == "core":
        key = keys.get("core")
        if not key:
            raise ValueError("CORE nécessite une clé API gratuite : uv run academic-writer secrets set core --clipboard")
        record = _json(fetch(f"https://api.core.ac.uk/v3/works/{urllib.parse.quote(identifier)}"
                             f"?apiKey={urllib.parse.quote(key)}"))
        url = record.get("downloadUrl") or ""
        if not url.lower().startswith("https://"):
            raise ValueError("Pas de texte intégral HTTPS déclaré par CORE.")
        return url, "dépôt en libre accès (CORE)", f"core-{identifier}.pdf"
    return None
