"""Données de référence : constantes physiques CODATA (NIST).

- NIST : table officielle « Fundamental Physical Constants — Complete Listing » (texte public, CODATA). Copie locale
  conservée dans <data_dir>/reference/ : utilisable hors connexion après le premier téléchargement.
"""

from __future__ import annotations

import re
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
