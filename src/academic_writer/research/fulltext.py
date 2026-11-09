"""Téléchargement de textes intégraux en LIBRE ACCÈS LÉGAL et export de références.

Le serveur ne télécharge jamais une adresse fournie de l'extérieur : il part de l'identifiant d'un
résultat (arxiv:…, ia:…, doaj:…), interroge lui-même la base, revérifie la licence et en déduit
l'adresse du PDF. Internet Archive : uniquement avec une licence libre déclarée (Creative Commons,
domaine public). HTTPS uniquement ; taille limitée ; le fichier est ensuite inspecté comme tout import.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from academic_writer.research import online  # noqa: F401 — active les certificats Windows (truststore)
from academic_writer.research.discovery import OPEN_LICENSE
from academic_writer.research.models import SourceData

USER_AGENT = online.USER_AGENT


class DownloadRefused(ValueError):
    """Téléchargement refusé (licence, service, format) : message destiné à l'utilisateur."""


def http_text(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (URL https construite)
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise OSError(f"HTTP {exc.code}") from exc


def http_bytes(url: str, max_bytes: int) -> bytes:
    if not url.lower().startswith("https://"):
        raise DownloadRefused("Seuls les téléchargements HTTPS sont autorisés.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            if not response.geturl().lower().startswith("https://"):
                raise DownloadRefused("Redirection vers une adresse non sécurisée : téléchargement refusé.")
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise OSError(f"HTTP {exc.code}") from exc
    if len(data) > max_bytes:
        raise DownloadRefused(f"Fichier trop volumineux (plus de {max_bytes // 1_048_576} Mo).")
    return data


def resolve_pdf(item_id: str, fetch_text=http_text, keys: dict[str, str] | None = None,
                unpaywall_email: str | None = None) -> tuple[str, str, str]:
    """(adresse du PDF, licence, nom de fichier) pour un identifiant de résultat en libre accès."""
    from academic_writer.research import openscience

    service, _, identifier = item_id.partition(":")
    if not identifier or not re.fullmatch(r"[\w.\-/:]{1,200}", identifier):
        raise DownloadRefused("Identifiant de résultat invalide.")
    if service == "unpaywall":
        if not unpaywall_email:
            raise DownloadRefused("Unpaywall nécessite une adresse e-mail (unpaywall_email dans config.toml).")
        url, license_name = openscience.unpaywall_location(identifier, unpaywall_email, fetch_text)
        if not url or not openscience._open_license(license_name) or not url.lower().startswith("https://"):
            raise DownloadRefused("Unpaywall ne localise pas de version HTTPS sous licence libre : téléchargement refusé.")
        return url, f"{license_name} (Unpaywall)", f"{identifier.replace('/', '_')[:60]}.pdf"
    try:
        resolved = openscience.resolve(service, identifier, fetch_text, keys)
    except ValueError as exc:
        raise DownloadRefused(str(exc)) from exc
    if resolved:
        return resolved
    if service == "arxiv":
        return f"https://arxiv.org/pdf/{identifier}", "arXiv (libre accès)", f"arxiv-{identifier.replace('/', '_')}.pdf"
    if service == "ia":
        meta = json.loads(fetch_text(f"https://archive.org/metadata/{urllib.parse.quote(identifier)}") or "{}")
        license_url = (meta.get("metadata") or {}).get("licenseurl") or ""
        if not OPEN_LICENSE.search(license_url):
            raise DownloadRefused("Cet ouvrage d'Internet Archive n'a pas de licence libre déclarée : téléchargement "
                                  "refusé (droit d'auteur). Consultez-le via son lien.")
        pdfs = [f for f in meta.get("files", []) if str(f.get("name", "")).lower().endswith(".pdf")]
        if not pdfs:
            raise DownloadRefused("Aucun fichier PDF dans cette notice d'Internet Archive.")
        name = sorted(pdfs, key=lambda f: ("_text" in f["name"], len(f["name"])))[0]["name"]
        return (f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}",
                license_url, name.rsplit("/", 1)[-1])
    if service == "doaj":
        record = json.loads(fetch_text(f"https://doaj.org/api/articles/{urllib.parse.quote(identifier)}") or "{}")
        links = (record.get("bibjson") or {}).get("link", [])
        url = next((link.get("url") for link in links if link.get("type") == "fulltext"), None)
        if not url or not url.lower().startswith("https://"):
            raise DownloadRefused("Pas de lien HTTPS vers le texte intégral dans la notice DOAJ.")
        return url, "revue en libre accès (DOAJ)", f"doaj-{identifier}.pdf"
    raise DownloadRefused(f"Téléchargement non pris en charge pour « {service} » (pas de libre accès garanti) : "
                          "consultez le lien de la notice.")


# --- export de références -------------------------------------------------------------------

BIB_TYPE = {"book": "book", "article": "article", "chapter": "incollection", "conference": "inproceedings",
            "thesis": "phdthesis", "standard": "misc", "web": "misc", "report": "techreport", "patent": "patent",
            "other": "misc"}
RIS_TYPE = {"book": "BOOK", "article": "JOUR", "chapter": "CHAP", "conference": "CPAPER", "thesis": "THES",
            "standard": "STAND", "web": "ELEC", "report": "RPRT", "patent": "PAT", "other": "GEN"}


def _names(people) -> list[str]:
    return [f"{p.family}, {p.given}" if p.given else p.family for p in people]


def to_bibtex(key: str, source_type: str, d: SourceData) -> str:
    fields = {
        "author": " and ".join(_names(d.authors)), "editor": " and ".join(_names(d.editors)),
        "title": d.title + (f": {d.subtitle}" if d.subtitle else "") if d.title else None,
        "journal" if source_type == "article" else "booktitle": d.container, "publisher": d.publisher,
        "address": d.place, "year": str(d.year) if d.year else None, "edition": d.edition, "volume": d.volume,
        "number": d.issue or (d.standard_number if source_type == "standard" else None),
        "pages": (d.pages or "").replace("–", "--") or None, "doi": d.doi, "isbn": d.isbn, "issn": d.issn,
        "url": d.url, "urldate": d.accessed, "langid": d.language,
    }
    lines = [f"  {name} = {{{value}}}" for name, value in fields.items() if value]
    return f"@{BIB_TYPE.get(source_type, 'misc')}{{{key},\n" + ",\n".join(lines) + "\n}"


def to_ris(key: str, source_type: str, d: SourceData) -> str:
    lines = [f"TY  - {RIS_TYPE.get(source_type, 'GEN')}", f"ID  - {key}"]
    lines += [f"AU  - {n}" for n in _names(d.authors)] + [f"ED  - {n}" for n in _names(d.editors)]
    start, _, end = (d.pages or "").replace("—", "–").partition("–")
    for tag, value in (("TI", d.title), ("T2", d.container), ("PB", d.publisher), ("CY", d.place),
                       ("PY", str(d.year) if d.year else None), ("ET", d.edition), ("VL", d.volume), ("IS", d.issue),
                       ("SP", start.strip() or None), ("EP", end.strip() or None), ("DO", d.doi),
                       ("SN", d.isbn or d.issn), ("UR", d.url), ("LA", d.language)):
        if value:
            lines.append(f"{tag}  - {value}")
    return "\n".join(lines + ["ER  - "])
