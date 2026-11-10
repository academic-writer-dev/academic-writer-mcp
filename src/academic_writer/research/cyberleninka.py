"""КиберЛенинка par son interface OFFICIELLE de moissonnage OAI-PMH (https://cyberleninka.ru/oai).

Conformité (robots.txt vérifié le 2026-11-10) : /oai est autorisé aux robots ; la recherche du site, /api/ et les
PDF sont INTERDITS aux robots → ce module ne fait que moissonner les métadonnées (titre, auteurs, éditeur, lien)
revue par revue, les conserve dans un index local et y cherche hors ligne. Le texte intégral (CC BY selon les
revues) se consulte par le lien, dans le navigateur de l'utilisateur ; aucun PDF n'est téléchargé automatiquement.
Politesse : une requête par seconde au plus, nombre de pages limité.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

BASE = "https://cyberleninka.ru/oai"
_OAI = "{http://www.openarchives.org/OAI/2.0/}"
_DC = "{http://purl.org/dc/elements/1.1/}"


class Journal(BaseModel):
    set_spec: str
    name: str


class CyberLeninkaRecord(BaseModel):
    url: str
    title: str
    authors: list[str]
    publisher: str | None
    journal: str
    set_spec: str


class HarvestResult(BaseModel):
    set_spec: str
    journal: str
    records: int
    pages: int
    complete: bool
    message: str


def _cache(data_dir: Path) -> Path:
    path = data_dir / "reference" / "cyberleninka"
    path.mkdir(parents=True, exist_ok=True)
    return path


def journals(data_dir: Path, fetch, allow_network: bool) -> list[Journal]:
    """Liste des revues (ensembles OAI), mise en cache 30 jours."""
    cache = _cache(data_dir) / "journals.json"
    fresh = cache.exists() and datetime.fromtimestamp(cache.stat().st_mtime) > datetime.now() - timedelta(days=30)
    if not fresh and allow_network:
        text = fetch(f"{BASE}?verb=ListSets") or ""
        found = [Journal(set_spec=s, name=n) for s, n in
                 re.findall(r"<setSpec>([^<]+)</setSpec>\s*<setName>([^<]+)</setName>", text) if s.startswith("journal_")]
        if found:
            cache.write_text(json.dumps([j.model_dump() for j in found], ensure_ascii=False), encoding="utf-8")
    if not cache.exists():
        raise ValueError("Liste des revues КиберЛенинка absente : mode connecté requis la première fois.")
    return [Journal.model_validate(j) for j in json.loads(cache.read_text(encoding="utf-8"))]


def find_journals(all_journals: list[Journal], query: str, limit: int = 30) -> list[Journal]:
    words = [w for w in re.findall(r"\w{3,}", query.casefold())]
    scored = []
    for journal in all_journals:
        name = journal.name.casefold()
        hits = sum(1 for w in words if w[: max(4, len(w) - 2)] in name)
        if hits:
            scored.append((hits, -len(name), journal))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [s[2] for s in scored[:limit]]


def parse_records(text: str, journal: str, set_spec: str) -> tuple[list[CyberLeninkaRecord], str | None]:
    root = ET.fromstring(text)
    records = []
    for record in root.iter(f"{_OAI}record"):
        dc = next(record.iter("{http://www.openarchives.org/OAI/2.0/oai_dc/}dc"), None)
        if dc is None:
            continue
        url = dc.findtext(f"{_DC}identifier") or ""
        title = (dc.findtext(f"{_DC}title") or "").strip()
        if not title or not url.startswith("https://cyberleninka.ru/article/"):
            continue
        records.append(CyberLeninkaRecord(url=url, title=title, journal=journal, set_spec=set_spec,
                                          authors=[c.text.strip() for c in dc.iter(f"{_DC}creator") if c.text],
                                          publisher=dc.findtext(f"{_DC}publisher")))
    token = root.findtext(f".//{_OAI}resumptionToken")
    return records, (token.strip() if token and token.strip() else None)


def harvest(data_dir: Path, fetch, set_spec: str, journal: str, max_pages: int = 60,
            delay: float = 1.0, sleep=time.sleep) -> HarvestResult:
    if not re.fullmatch(r"journal_\d{1,8}", set_spec):
        raise ValueError("Identifiant de revue invalide (ex. journal_14539).")
    url = f"{BASE}?verb=ListRecords&metadataPrefix=oai_dc&set={set_spec}"
    collected: list[CyberLeninkaRecord] = []
    pages = 0
    token = None
    while pages < max_pages:
        text = fetch(url)
        if not text:
            break
        records, token = parse_records(text, journal, set_spec)
        collected += records
        pages += 1
        if not token:
            break
        url = f"{BASE}?verb=ListRecords&resumptionToken={urllib.parse.quote(token)}"
        sleep(delay)  # politesse envers le serveur
    path = _cache(data_dir) / f"{set_spec}.json"
    path.write_text(json.dumps({"journal": journal, "harvested": datetime.now().isoformat(timespec="seconds"),
                                "complete": token is None, "records": [r.model_dump() for r in collected]},
                               ensure_ascii=False), encoding="utf-8")
    complete = token is None
    return HarvestResult(set_spec=set_spec, journal=journal, records=len(collected), pages=pages, complete=complete,
                         message=("Revue moissonnée entièrement." if complete else
                                  f"Moissonnage partiel ({pages} pages) : relancer avec max_pages plus grand si besoin."))


def harvested(data_dir: Path) -> list[CyberLeninkaRecord]:
    records = []
    for path in sorted(_cache(data_dir).glob("journal_*.json")):
        try:
            records += [CyberLeninkaRecord.model_validate(r)
                        for r in json.loads(path.read_text(encoding="utf-8"))["records"]]
        except (OSError, ValueError, KeyError):
            continue
    return records
