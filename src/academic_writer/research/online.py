"""Vérification et recherche EN LIGNE des métadonnées (uniquement en mode « connected »).

Services (métadonnées bibliographiques uniquement, jamais le contenu des documents) :
- Crossref (api.crossref.org) : DOI, recherche par titre ;
- OpenAlex (api.openalex.org, données CC0) : DOI absent de Crossref, articles dont revues russes ;
- Google Books (googleapis.com/books, clé gratuite) : ISBN et titres, très riche en livres russes ;
- Open Library (openlibrary.org) : ISBN.
Exclus volontairement : КиберЛенинка (son règlement, art. 6.2, interdit la collecte automatisée de
métadonnées), РГБ et eLIBRARY (aucune interface automatisée publique).
Une absence dans ces bases n'est jamais une preuve d'inexistence : le statut l'indique.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

import truststore

from academic_writer import __version__
from academic_writer.research.models import Finding, OnlineCandidate, Person, SourceData
from academic_writer.research.validation import normalize_doi

# Certificats du magasin Windows (le Python géré par uv n'en voit pas certains : archive.org, arxiv.org).
truststore.inject_into_ssl()

USER_AGENT = f"AcademicWriterMCP/{__version__} (local academic writing tool)"
Fetcher = Callable[[str], dict | None]  # JSON, None si 404 ; lève OSError si réseau indisponible ou quota


MAX_RESPONSE_BYTES = 25 * 1_048_576  # au-delà, une réponse de catalogue est anormale


class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse toute redirection vers une adresse non chiffrée (HTTPS uniquement, de bout en bout)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise urllib.error.URLError("redirection vers une adresse non HTTPS refusée")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnlyRedirect)


def secure_open(request: urllib.request.Request, timeout: float):
    """Ouvre une adresse HTTPS (certificat vérifié, redirections HTTPS seulement)."""
    if urllib.parse.urlsplit(request.full_url).scheme.lower() != "https":
        raise urllib.error.URLError("adresse non HTTPS refusée")
    return _OPENER.open(request, timeout=timeout)


def read_limited(response, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise urllib.error.URLError(f"réponse trop volumineuse (plus de {limit // 1_048_576} Mo) : refusée")
    return data


def http_fetch(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with secure_open(request, timeout=20) as response:
            return json.loads(read_limited(response).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code == 429:
            raise OSError("quota du service atteint (429) : une clé gratuite est probablement nécessaire") from exc
        if exc.code in (401, 403):
            raise OSError(f"accès refusé ({exc.code}) : {_denial_reason(exc)}") from exc
        raise OSError(f"HTTP {exc.code}") from exc


_DENIAL_HINTS = {
    "API_KEY_SERVICE_BLOCKED": "la clé est restreinte à d'autres API : dans la console Google Cloud > Identifiants > "
                               "votre clé > Restrictions d'API, ajoutez « Books API »",
    "SERVICE_DISABLED": "l'API n'est pas activée dans le projet Google Cloud : cliquez sur « Activer » sur la page de l'API",
    "API_KEY_INVALID": "clé invalide (supprimée ou mal copiée) : enregistrez-la de nouveau",
    "API_KEY_IP_ADDRESS_BLOCKED": "la clé est restreinte à certaines adresses IP",
    "API_KEY_HTTP_REFERRER_BLOCKED": "la clé est restreinte aux sites web (référents HTTP) : choisissez « Aucune » "
                                     "ou « Adresses IP » comme restriction d'application",
}


def _denial_reason(exc: urllib.error.HTTPError) -> str:
    """Cause précise d'un refus Google, sans jamais recopier la clé."""
    try:
        error = json.loads(exc.read().decode("utf-8")).get("error", {})
        reasons = [d.get("reason") for d in error.get("details", []) if isinstance(d, dict)]
    except (ValueError, OSError, AttributeError):
        return "clé absente ou invalide"
    for reason in reasons:
        if reason in _DENIAL_HINTS:
            return _DENIAL_HINTS[reason]
    return "clé absente ou invalide"


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def similarity(a: str | None, b: str | None) -> float:
    words_a = {w for w in re.findall(r"\w{3,}", _fold(a or ""))}
    words_b = {w for w in re.findall(r"\w{3,}", _fold(b or ""))}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _person(name: str) -> Person:
    name = " ".join(name.split())
    if "," in name:
        family, given = [p.strip() for p in name.split(",", 1)]
        return Person(family=family, given=given or None)
    parts = name.split(" ")
    if len(parts) == 1:
        return Person(family=parts[0])
    if re.search(r"[А-Яа-яЁё]", name) and len(parts) == 3:  # Фамилия Имя Отчество
        return Person(family=parts[0], given=" ".join(parts[1:]))
    return Person(family=parts[-1], given=" ".join(parts[:-1]))


def _year(text: str | None) -> int | None:
    match = re.search(r"(1[5-9]|20)\d{2}", text or "")
    return int(match.group(0)) if match else None


# --- analyseurs par service ---------------------------------------------------------

_CROSSREF_TYPES = {"journal-article": "article", "book": "book", "monograph": "book", "book-chapter": "chapter",
                   "proceedings-article": "conference", "dissertation": "thesis", "report": "report",
                   "standard": "standard"}


def crossref_candidate(item: dict) -> OnlineCandidate:
    authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])][:10]
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    title = (item.get("title") or [None])[0]
    container = (item.get("container-title") or [None])[0]
    source_type = _CROSSREF_TYPES.get(item.get("type", ""), "other")
    data = SourceData(authors=[Person(family=a.get("family", ""), given=a.get("given"))
                               for a in item.get("author", []) if a.get("family")],
                      title=title, container=container, publisher=item.get("publisher"), year=year,
                      volume=item.get("volume"), issue=item.get("issue"), pages=item.get("page"),
                      doi=item.get("DOI"), isbn=(item.get("ISBN") or [None])[0], language=item.get("language"))
    return OnlineCandidate(service="crossref", title=title, authors=authors, year=year, container=container,
                           doi=item.get("DOI"), isbn=data.isbn, publisher=data.publisher, score=0.0,
                           source_type=source_type, data=data)


_OPENALEX_TYPES = {"article": "article", "book": "book", "book-chapter": "chapter", "dissertation": "thesis",
                   "report": "report", "standard": "standard", "proceedings-article": "conference"}


def openalex_candidate(work: dict) -> OnlineCandidate:
    authors = [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])][:10]
    location = (work.get("primary_location") or {}).get("source") or {}
    biblio = work.get("biblio") or {}
    pages = "–".join(p for p in (biblio.get("first_page"), biblio.get("last_page")) if p) or None
    doi = (work.get("doi") or "").replace("https://doi.org/", "") or None
    source_type = _OPENALEX_TYPES.get(work.get("type", ""), "other")
    data = SourceData(authors=[_person(a) for a in authors if a], title=work.get("display_name"),
                      container=location.get("display_name"), year=work.get("publication_year"),
                      volume=biblio.get("volume"), issue=biblio.get("issue"), pages=pages, doi=doi,
                      language=work.get("language"))
    return OnlineCandidate(service="openalex", title=work.get("display_name"), authors=authors,
                           year=work.get("publication_year"), container=location.get("display_name"), doi=doi,
                           score=0.0, source_type=source_type, data=data)


def google_candidate(item: dict) -> OnlineCandidate:
    info = item.get("volumeInfo", {})
    identifiers = {i.get("type"): i.get("identifier") for i in info.get("industryIdentifiers", [])}
    isbn = identifiers.get("ISBN_13") or identifiers.get("ISBN_10")
    year = _year(info.get("publishedDate"))
    data = SourceData(authors=[_person(a) for a in info.get("authors", [])], title=info.get("title"),
                      subtitle=info.get("subtitle"), publisher=info.get("publisher"), year=year,
                      pages=str(info["pageCount"]) if info.get("pageCount") else None, isbn=isbn,
                      language=info.get("language"))
    return OnlineCandidate(service="google_books", title=info.get("title"), authors=info.get("authors", []),
                           year=year, container=None, doi=None, isbn=isbn, publisher=info.get("publisher"),
                           score=0.0, source_type="book", data=data)


# --- vérification d'une fiche ---------------------------------------------------------------

@dataclass
class OnlineOutcome:
    status: str | None  # verified_online, mismatch, not_found ou None (non concluant)
    findings: list[Finding] = field(default_factory=list)
    candidates: list[OnlineCandidate] = field(default_factory=list)


def _compare(data: SourceData, found: OnlineCandidate, label: str, threshold: float = 0.6) -> tuple[str, Finding]:
    title_score = similarity(data.title, found.title)
    year_ok = data.year is None or found.year is None or abs(data.year - found.year) <= 1
    author_ok = not data.authors or not found.authors or any(
        _fold(data.authors[0].family)[:5] in _fold(name) for name in found.authors)
    found.score = round(title_score, 2)
    if title_score >= threshold and year_ok and author_ok:
        return "verified_online", Finding(severity="info", message=f"{label} confirmé : « {found.title} » ({found.year}).")
    problems = [p for p, ok in (("titre", title_score >= threshold), ("année", year_ok), ("premier auteur", author_ok))
                if not ok]
    return "mismatch", Finding(severity="error", message=f"{label} renvoie à « {found.title} » ({found.year}) : "
                                                         f"divergence sur {', '.join(problems)}.")


def _key_param(name: str, keys: dict[str, str]) -> str:
    key = keys.get(name)
    if not key:
        return ""
    return f"&{'key' if name == 'google_books' else 'api_key'}={urllib.parse.quote(key)}"


def verify_online(data: SourceData, fetch: Fetcher = http_fetch, keys: dict[str, str] | None = None) -> OnlineOutcome:
    keys = keys or {}
    outcome = OnlineOutcome(status=None)
    if data.doi:
        doi = normalize_doi(data.doi)
        payload = fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
        if payload is not None:
            found = crossref_candidate(payload.get("message", {}))
            outcome.status, finding = _compare(data, found, "DOI (Crossref)")
            finding.field = "doi"
            outcome.findings.append(finding)
            outcome.candidates.append(found)
            return outcome
        alex = fetch("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/")
                     + "?select=display_name,publication_year,authorships,primary_location,biblio,doi,type,language"
                     + _key_param("openalex", keys))
        if alex is None:
            outcome.status = "not_found"
            outcome.findings.append(Finding(severity="error", field="doi",
                                            message=f"DOI inconnu de Crossref et d'OpenAlex : {doi} (référence "
                                                    "possiblement erronée ou fictive ; vérifiez chez l'éditeur)."))
            return outcome
        found = openalex_candidate(alex)
        outcome.status, finding = _compare(data, found, "DOI (OpenAlex)")
        finding.field = "doi"
        outcome.findings.append(finding)
        outcome.candidates.append(found)
        return outcome

    if data.isbn:
        isbn = re.sub(r"[\s-]", "", data.isbn)
        if keys.get("google_books"):
            payload = fetch(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&maxResults=3"
                            + _key_param("google_books", keys))
            items = (payload or {}).get("items") or []
            if items:
                found = google_candidate(items[0])
                outcome.status, finding = _compare(data, found, "ISBN (Google Books)", threshold=0.5)
                finding.field = "isbn"
                outcome.findings.append(finding)
                outcome.candidates.append(found)
                return outcome
        payload = fetch(f"https://openlibrary.org/isbn/{isbn}.json")
        if payload is None:
            outcome.findings.append(Finding(severity="info", field="isbn",
                                            message="ISBN absent " + ("de Google Books et " if keys.get("google_books")
                                                                      else "") + "d'Open Library (non concluant)."))
        else:
            found = OnlineCandidate(service="openlibrary", title=payload.get("title"), authors=[],
                                    year=_year(payload.get("publish_date")), container=None, doi=None, isbn=isbn,
                                    score=0.0, source_type="book")
            outcome.status, finding = _compare(data, found, "ISBN (Open Library)", threshold=0.5)
            finding.field = "isbn"
            outcome.findings.append(finding)
            outcome.candidates.append(found)
        return outcome

    if data.title:
        result = search_online(data.title, data.authors[0].family if data.authors else None, fetch, keys,
                               kind="articles" if data.container else "all")
        outcome.candidates = [c for c in result[0] if c.score >= 0.5]
        if outcome.candidates:
            outcome.findings.append(Finding(severity="info",
                                            message="Correspondances possibles trouvées : à confirmer par l'utilisateur "
                                                    "(compléter l'ISBN ou le DOI rend la vérification concluante)."))
        else:
            outcome.findings.append(Finding(severity="info", message="Aucune correspondance trouvée (non concluant "
                                                                     "sans identifiant)."))
    return outcome


# --- recherche ---------------------------------------------------------------------------------

def search_online(title: str, author: str | None, fetch: Fetcher = http_fetch, keys: dict[str, str] | None = None,
                  kind: str = "all", isbn: str | None = None,
                  limit: int = 5) -> tuple[list[OnlineCandidate], list[str], list[str]]:
    """Recherche multi-services ; renvoie (candidats triés, services interrogés, avertissements)."""
    keys = keys or {}
    candidates: list[OnlineCandidate] = []
    services: list[str] = []
    notices: list[str] = []

    def attempt(name: str, url: str, parse) -> None:
        services.append(name)
        try:
            payload = fetch(url)
        except OSError as exc:
            notices.append(f"{name} : {exc}")
            return
        for candidate in parse(payload or {}):
            candidate.score = round(max(similarity(title, candidate.title),
                                        similarity(title, f"{candidate.title} {candidate.data.subtitle or ''}"
                                                   if candidate.data else "")), 2) if title else 1.0
            candidates.append(candidate)

    if kind in ("books", "all"):
        if keys.get("google_books"):
            query = f"isbn:{re.sub(r'[^0-9Xx]', '', isbn)}" if isbn else \
                f'intitle:"{title}"' + (f" inauthor:{author}" if author else "")
            attempt("google_books", "https://www.googleapis.com/books/v1/volumes?maxResults=" + str(limit)
                    + "&q=" + urllib.parse.quote(query) + _key_param("google_books", keys),
                    lambda p: [google_candidate(i) for i in p.get("items", [])])
        else:
            notices.append("Google Books non interrogé : aucune clé (uv run academic-writer secrets set google_books).")
    if kind in ("articles", "all") and title:
        attempt("openalex", "https://api.openalex.org/works?per-page=" + str(limit) + "&search="
                + urllib.parse.quote(title + (f" {author}" if author else "")) + _key_param("openalex", keys),
                lambda p: [openalex_candidate(w) for w in p.get("results", [])])
        attempt("crossref", "https://api.crossref.org/works?rows=" + str(limit) + "&query.bibliographic="
                + urllib.parse.quote(title + (f" {author}" if author else "")),
                lambda p: [crossref_candidate(i) for i in (p.get("message") or {}).get("items", [])])
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[: limit * 2], services, notices
