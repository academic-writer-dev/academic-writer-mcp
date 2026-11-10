"""Données de référence : constantes physiques CODATA (NIST) et patrimoine numérisé (Europeana).

- NIST : table officielle « Fundamental Physical Constants — Complete Listing » (texte public, CODATA). Copie locale
  conservée dans <data_dir>/reference/ : utilisable hors connexion après le premier téléchargement.
- Europeana : API de recherche avec clé PERSONNELLE gratuite (la clé de démonstration n'est pas destinée à l'usage
  réel) ; licence de chaque objet indiquée, jamais présumée libre.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

NIST_URL = "https://physics.nist.gov/cuu/Constants/Table/allascii.txt"


class PhysicalConstant(BaseModel):
    name: str
    value: float
    value_text: str = Field(description="Valeur telle que publiée.")
    uncertainty: str = Field(description="Incertitude-type publiée, ou « exact ».")
    unit: str
    source: str


def parse_codata(text: str) -> tuple[str, list[PhysicalConstant]]:
    edition = re.search(r"(\d{4}) CODATA", text)
    source = f"CODATA {edition.group(1) if edition else ''} (NIST)".replace("  ", " ")
    constants = []
    started = False
    for line in text.splitlines():
        if line.startswith("-----"):
            started = True
            continue
        if not started or len(line) < 60 or not line.strip():
            continue
        name = line[:60].strip()
        rest = line[60:]
        value_text, uncertainty, unit = rest[:25].strip(), rest[25:50].strip(), rest[50:].strip()
        number = value_text.replace(" ", "").replace("...", "")
        try:
            value = float(number)
        except ValueError:
            continue
        constants.append(PhysicalConstant(name=name, value=value, value_text=value_text,
                                          uncertainty="exact" if "exact" in uncertainty else uncertainty,
                                          unit=unit or "(sans dimension)", source=source))
    return source, constants


def load_codata(cache_dir: Path, fetch, allow_network: bool) -> tuple[list[PhysicalConstant], str]:
    """(constantes, origine) ; télécharge si absent ou de plus de 180 jours, et si le réseau est autorisé."""
    cache = cache_dir / "codata_allascii.txt"
    stale = not cache.exists() or datetime.fromtimestamp(cache.stat().st_mtime) < datetime.now() - timedelta(days=180)
    note = "copie locale"
    if stale and allow_network:
        text = fetch(NIST_URL)
        if text and "CODATA" in text:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")
            note = "téléchargée depuis le NIST"
    if not cache.exists():
        raise ValueError("Table CODATA absente : passer en mode connecté une première fois (téléchargement du NIST).")
    _, constants = parse_codata(cache.read_text(encoding="utf-8"))
    return constants, note


def search_constants(constants: list[PhysicalConstant], query: str) -> list[PhysicalConstant]:
    words = [w for w in re.findall(r"\w+", query.casefold()) if len(w) > 1]
    scored = []
    for constant in constants:
        name = constant.name.casefold()
        hits = sum(1 for w in words if w in name)
        if hits:
            scored.append((hits == len(words), hits, -len(name), constant))
    scored.sort(key=lambda s: (s[0], s[1], s[2]), reverse=True)
    return [s[3] for s in scored[:15]]


# --- Europeana ------------------------------------------------------------------------------------------------

class HeritageItem(BaseModel):
    title: str
    type: str | None
    provider: str | None
    country: str | None
    year: str | None
    rights: str | None
    open_license: bool
    url: str | None
    preview: str | None


def europeana_url(query: str, key: str, rows: int = 10, media_type: str | None = None) -> str:
    url = f"https://api.europeana.eu/record/v2/search.json?wskey={urllib.parse.quote(key)}&rows={rows}" \
          f"&query={urllib.parse.quote(query)}"
    return url + (f"&qf=TYPE:{urllib.parse.quote(media_type)}" if media_type else "")


def parse_europeana(data: dict) -> list[HeritageItem]:
    from academic_writer.research.openscience import _open_license

    items = []
    for item in data.get("items", []) or []:
        title = (item.get("title") or [None])[0]
        if not title:
            continue
        rights = (item.get("rights") or [None])[0]
        guid = item.get("guid") or ""
        items.append(HeritageItem(
            title=title, type=item.get("type"), provider=(item.get("dataProvider") or [None])[0],
            country=(item.get("country") or [None])[0], year=(item.get("year") or [None])[0],
            rights=rights, open_license=_open_license(rights) and "-nc" not in (rights or "").casefold(),
            url=guid.split("?")[0] or None, preview=(item.get("edmPreview") or [None])[0]))
    return items
