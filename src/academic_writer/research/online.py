"""Vérification EN LIGNE des métadonnées (uniquement en mode « connected »).

- Crossref (api.crossref.org) : DOI et recherche par titre ;
- Open Library (openlibrary.org) : ISBN.
Seules des métadonnées bibliographiques sont envoyées (DOI, ISBN, titre, nom d'auteur), jamais
le contenu des documents. Une absence dans ces bases n'est pas une preuve d'inexistence (ouvrages
russes, littérature grise…) : le statut l'indique.
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

from academic_writer.research.models import Finding, OnlineCandidate, SourceData
from academic_writer.research.validation import normalize_doi

USER_AGENT = "AcademicWriterMCP/0.6 (local academic writing tool)"
Fetcher = Callable[[str], dict | None]  # renvoie le JSON, None si 404 ; lève OSError si réseau indisponible


def http_fetch(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (URL fixe https)
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise OSError(f"HTTP {exc.code}") from exc


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def similarity(a: str | None, b: str | None) -> float:
    words_a = {w for w in re.findall(r"\w{3,}", _fold(a or ""))}
    words_b = {w for w in re.findall(r"\w{3,}", _fold(b or ""))}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


@dataclass
class OnlineOutcome:
    status: str | None  # verified_online, mismatch, not_found ou None (non concluant)
    findings: list[Finding] = field(default_factory=list)
    candidates: list[OnlineCandidate] = field(default_factory=list)


def _crossref_item(item: dict) -> OnlineCandidate:
    authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])][:6]
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    return OnlineCandidate(title=(item.get("title") or [None])[0], authors=authors, year=year,
                           container=(item.get("container-title") or [None])[0], doi=item.get("DOI"), score=0.0)


def verify_online(data: SourceData, fetch: Fetcher = http_fetch) -> OnlineOutcome:
    outcome = OnlineOutcome(status=None)
    if data.doi:
        doi = normalize_doi(data.doi)
        payload = fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
        if payload is None:
            outcome.status = "not_found"
            outcome.findings.append(Finding(severity="error", field="doi",
                                            message=f"DOI inconnu de Crossref : {doi} (référence possiblement erronée "
                                                    "ou fictive ; vérifiez sur le site de l'éditeur)."))
            return outcome
        found = _crossref_item(payload.get("message", {}))
        title_score = similarity(data.title, found.title)
        year_ok = data.year is None or found.year is None or abs(data.year - found.year) <= 1
        author_ok = not data.authors or not found.authors or any(
            _fold(data.authors[0].family) in _fold(name) for name in found.authors)
        found.score = round(title_score, 2)
        outcome.candidates.append(found)
        if title_score >= 0.6 and year_ok and author_ok:
            outcome.status = "verified_online"
            outcome.findings.append(Finding(severity="info", field="doi",
                                            message=f"DOI confirmé par Crossref : « {found.title} » ({found.year})."))
        else:
            outcome.status = "mismatch"
            problems = [p for p, ok in (("titre", title_score >= 0.6), ("année", year_ok), ("premier auteur", author_ok))
                        if not ok]
            outcome.findings.append(Finding(severity="error", field="doi",
                                            message=f"Le DOI renvoie à « {found.title} » ({found.year}) : divergence sur "
                                                    f"{', '.join(problems)}."))
        return outcome

    if data.isbn:
        isbn = re.sub(r"[\s-]", "", data.isbn)
        payload = fetch(f"https://openlibrary.org/isbn/{isbn}.json")
        if payload is None:
            outcome.findings.append(Finding(severity="info", field="isbn",
                                            message="ISBN absent d'Open Library (non concluant : couverture incomplète, "
                                                    "notamment pour les ouvrages russes)."))
        else:
            title_score = similarity(data.title, payload.get("title"))
            year_match = re.search(r"\d{4}", payload.get("publish_date", "") or "")
            found_year = int(year_match.group(0)) if year_match else None
            year_ok = data.year is None or found_year is None or abs(data.year - found_year) <= 1
            outcome.candidates.append(OnlineCandidate(title=payload.get("title"), authors=[], year=found_year,
                                                      container=None, doi=None, score=round(title_score, 2)))
            if title_score >= 0.5 and year_ok:
                outcome.status = "verified_online"
                outcome.findings.append(Finding(severity="info", field="isbn",
                                                message=f"ISBN confirmé par Open Library : « {payload.get('title')} »."))
            else:
                outcome.status = "mismatch"
                outcome.findings.append(Finding(severity="error", field="isbn",
                                                message=f"L'ISBN correspond à « {payload.get('title')} » ({found_year})."))
        return outcome

    if data.title:
        query = data.title + (" " + data.authors[0].family if data.authors else "")
        payload = fetch("https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(query))
        items = ((payload or {}).get("message") or {}).get("items") or []
        for item in items:
            candidate = _crossref_item(item)
            candidate.score = round(similarity(data.title, candidate.title), 2)
            if candidate.score >= 0.5:
                outcome.candidates.append(candidate)
        if outcome.candidates:
            outcome.findings.append(Finding(severity="info", field=None,
                                            message="Correspondances possibles trouvées sur Crossref : à confirmer par "
                                                    "l'utilisateur avant de compléter la fiche (DOI)."))
        else:
            outcome.findings.append(Finding(severity="info", field=None,
                                            message="Aucune correspondance sur Crossref (non concluant sans identifiant)."))
    return outcome
