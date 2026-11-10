"""Liens de vérification MANUELLE (ouverts par l'utilisateur dans son navigateur).

Aucun accès automatisé : le serveur se contente de construire des adresses de recherche. Une
consultation humaine est autorisée par tous ces services (y compris КиберЛенинка, dont le
règlement n'interdit que la collecte automatisée). Couvre les ouvrages russes absents des API.
"""

from __future__ import annotations

import re
from urllib.parse import quote, quote_plus

from academic_writer.research.models import SourceData


def _query(data: SourceData) -> str:
    parts = [data.title or data.standard_number or ""]
    if data.authors:
        parts.append(data.authors[0].family)
    if data.year:
        parts.append(str(data.year))
    return " ".join(p for p in parts if p).strip()


def manual_links(data: SourceData) -> dict[str, str]:
    """{libellé : adresse} ; les identifiants (DOI, ISBN) donnent les liens les plus précis."""
    links: dict[str, str] = {}
    query = _query(data)
    isbn = re.sub(r"[^0-9Xx]", "", data.isbn or "")
    if data.doi:
        links["DOI (page de l'éditeur)"] = "https://doi.org/" + quote(data.doi, safe="/")
    if isbn:
        links["Google Книги (ISBN)"] = "https://www.google.com/search?tbm=bks&q=isbn:" + isbn
    if query:
        links["eLIBRARY / РИНЦ (via Яндекс)"] = "https://yandex.ru/search/?text=" + quote_plus(f"{query} site:elibrary.ru")
        links["КиберЛенинка"] = "https://cyberleninka.ru/search?q=" + quote_plus(query)
        links["Google Академия (Scholar)"] = "https://scholar.google.com/scholar?q=" + quote_plus(query)
        links["Google Книги"] = "https://www.google.com/search?tbm=bks&q=" + quote_plus(query)
        links["Crossref"] = "https://search.crossref.org/search/works?q=" + quote_plus(query)
    if data.url:
        links["Adresse indiquée dans la fiche"] = data.url
    return links
