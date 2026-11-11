"""Bibliothèques gratuites supplémentaires : dépôts d'universités russophones, Amérique latine, manuels ouverts.

Vérifiées le 2026-11-11 (accès automatisé autorisé par robots.txt, User-Agent honnête) :
- БНТУ (Université technique nationale de Biélorussie, en russe), ТГУ Тольятти : dépôts DSpace 7, API de
  recherche publique (/server/api/discover/search/objects) — manuels, méthodiques (« методические указания »),
  cours de « Детали машин », ТММ, guides d'oformlenie des ВКР ;
- УрФУ (Université fédérale de l'Oural) : dépôt DSpace, OpenSearch public (Atom) ;
- La Referencia (réseau des dépôts d'Amérique latine) : API VuFind publique ;
- Open Textbook Library (Université du Minnesota) : manuels universitaires sous licence ouverte ; catalogue lu PAR
  MATIÈRE (ingénierie, génie mécanique, physique, mathématiques appliquées, rédaction et communication), gardé
  dans un index local (30 jours) et cherché hors ligne.
Les dépôts russophones ne sont interrogés que pour une recherche écrite en cyrillique.
Écartés : DOAB et OAPEN (HTTP 403), Shodhganga et KoreaScience (connexion refusée depuis le poste), Garuda et
КПИ / ХПИ (adresse introuvable), ТПУ, БГУ, КФУ, Самарский университет, СФУ, ЮУрГУ (pas d'interface de recherche
exploitable ou HTTP 403), СПбГУ (résultats sans rapport avec l'ingénierie).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from academic_writer.research.discovery import DiscoveredWork, relevance
from academic_writer.research.models import SourceData
from academic_writer.research.online import _person, _year

_ATOM = "{http://www.w3.org/2005/Atom}"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
DSPACE7 = {
    "bntu": ("БНТУ (Biélorussie)", "https://rep.bntu.by"),
    "tltsu": ("ТГУ Тольятти", "https://dspace.tltsu.ru"),
}
OPENSEARCH = {"urfu": ("УрФУ", "https://elar.urfu.ru")}
REPOSITORY_NOTE = "dépôt universitaire en libre consultation (droits selon le document) — lire sur le site"
_TYPES = {"article": "article", "book": "book", "textbook": "book", "thesis": "thesis", "dissertation": "thesis",
          "learning object": "book", "preprint": "report", "report": "report", "conference": "conference",
          "статья": "article", "учебник": "book", "учебное пособие": "book", "диссертация": "thesis"}


def _kind(raw: str | None) -> str:
    raw = (raw or "").casefold()
    return next((value for key, value in _TYPES.items() if key in raw), "other")


# --- DSpace 7 -------------------------------------------------------------------------------------------

def dspace7_url(host: str, query: str, per: int) -> str:
    return f"{host}/server/api/discover/search/objects?dsoType=ITEM&size={per}&query=" + urllib.parse.quote(query)


def dspace7_parser(service: str):
    label = DSPACE7[service][0]

    def parse(text: str | None, query: str) -> list[DiscoveredWork]:
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            return []
        objects = (((data.get("_embedded") or {}).get("searchResult") or {}).get("_embedded") or {}).get("objects", [])
        works = []
        for obj in objects:
            item = (obj.get("_embedded") or {}).get("indexableObject") or {}
            meta = item.get("metadata") or {}

            def values(key: str) -> list[str]:
                return [v.get("value", "").strip() for v in meta.get(key, []) if v.get("value")]

            title = (values("dc.title") or [item.get("name") or ""])[0]
            uuid = str(item.get("uuid") or "")
            if not title or not re.fullmatch(r"[0-9a-f\-]{36}", uuid):
                continue
            # adresse directe de la notice : certains dépôts déclarent un « handle » par défaut qui ne mène nulle part
            uri = f"{DSPACE7[service][1]}/items/{uuid}"
            authors = values("dc.contributor.author")[:10]
            year = _year((values("dc.date.issued") or [""])[0])
            subjects = " ".join(values("dc.subject") + values("dc.description.abstract")[:1])
            language = next((v for v in values("dc.language.iso") if re.fullmatch(r"[a-z]{2}", v)), None)
            publisher = (values("dc.publisher") or [None])[0]
            works.append(DiscoveredWork(
                item_id=f"{service}:{item.get('handle') or item.get('uuid')}", service=service, title=title,
                authors=authors, year=year, source_type=_kind((values("dc.type") or [""])[0]),
                publisher=publisher or label, language=language, landing_url=uri,
                license=f"{label} : {REPOSITORY_NOTE}", open_access=False,
                relevance=relevance(query, title, subjects),
                data=SourceData(authors=[_person(a) for a in authors], title=title, year=year,
                                publisher=publisher or label, url=uri, language=language)))
        return works
    parse.__name__ = f"parse_{service}"
    return parse


# --- DSpace OpenSearch (УрФУ) ------------------------------------------------------------------------

def opensearch_url(host: str, query: str, per: int) -> str:
    return f"{host}/open-search/?rpp={min(per * 2, 40)}&query=" + urllib.parse.quote(query)  # tri par date : plus de candidats


def opensearch_parser(service: str):
    label = OPENSEARCH[service][0]

    def parse(text: str | None, query: str) -> list[DiscoveredWork]:
        try:
            root = ET.fromstring(text) if text else None
        except ET.ParseError:
            return []
        if root is None:
            return []
        works = []
        for entry in root.iter(f"{_ATOM}entry"):
            title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
            link = next((l.get("href") for l in entry.iter(f"{_ATOM}link") if (l.get("href") or "").startswith("https://")),
                        None)
            if not title or not link:
                continue
            authors = [" ".join((a.findtext(f"{_ATOM}name") or "").split()) for a in entry.iter(f"{_ATOM}author")]
            authors = [a for a in authors if a][:10]
            works.append(DiscoveredWork(
                item_id=f"{service}:{link.rsplit('/handle/', 1)[-1]}", service=service, title=title, authors=authors,
                year=None,  # la date du flux est celle du dépôt, pas de la publication
                source_type="other", publisher=label, language="ru", landing_url=link,
                license=f"{label} : {REPOSITORY_NOTE}", open_access=False, relevance=relevance(query, title),
                data=SourceData(authors=[_person(a) for a in authors], title=title, publisher=label, url=link,
                                language="ru")))
        return works
    parse.__name__ = f"parse_{service}"
    return parse


# --- La Referencia (Amérique latine) -----------------------------------------------------------------------

_LAREF_FIELDS = ("id", "title", "primaryAuthors", "secondaryAuthors", "publicationDates", "urls", "formats",
                 "subjects", "languages")


def lareferencia_url(query: str, per: int) -> str:
    fields = "".join(f"&field[]={f}" for f in _LAREF_FIELDS)
    return f"https://www.lareferencia.info/vufind/api/v1/search?limit={per}{fields}&lookfor=" + urllib.parse.quote(query)


def parse_lareferencia(text: str | None, query: str) -> list[DiscoveredWork]:
    try:
        records = (json.loads(text) if text else {}).get("records") or []
    except (ValueError, AttributeError):
        return []
    works = []
    for record in records:
        title, record_id = " ".join(str(record.get("title") or "").split()), str(record.get("id") or "")
        if not title or not re.fullmatch(r"[\w.:\-]{1,120}", record_id):
            continue
        authors = [a for a in (record.get("primaryAuthors") or []) + (record.get("secondaryAuthors") or [])
                   if isinstance(a, str)][:10]
        url = next((u.get("url") for u in record.get("urls") or [] if str(u.get("url", "")).startswith("https://")),
                   None) or f"https://www.lareferencia.info/vufind/Record/{urllib.parse.quote(record_id)}"
        year = _year(" ".join(record.get("publicationDates") or []))
        subjects = " ".join(" ".join(s) if isinstance(s, list) else str(s) for s in record.get("subjects") or [])
        works.append(DiscoveredWork(
            item_id=f"lareferencia:{record_id}", service="lareferencia", title=title, authors=authors, year=year,
            source_type=_kind(" ".join(record.get("formats") or [])), language=(record.get("languages") or [None])[0],
            landing_url=url, license="La Referencia : dépôt institutionnel en libre accès (licence selon le document)",
            open_access=False, relevance=relevance(query, title, subjects),
            data=SourceData(authors=[_person(a) for a in authors], title=title, year=year, url=url)))
    return works


# --- Open Textbook Library (index local par matière) ------------------------------------------------------

OTL_SUBJECTS = {13: "Engineering & Technology", 39: "Physics", 35: "Applied Mathematics",
                33: "Literature, Rhetoric and Writing", 16: "Journalism, Media and Communications"}
_OTL = "https://open.umn.edu/opentextbooks"


def _otl_cache(data_dir: Path) -> Path:
    path = data_dir / "reference" / "open_textbooks"
    path.mkdir(parents=True, exist_ok=True)
    return path / "catalog.json"


def _otl_record(item: dict, subject: str) -> dict | None:
    title, url = item.get("title"), item.get("url") or ""
    if not title or not str(url).startswith(_OTL + "/textbooks/"):
        return None
    authors = []
    for c in item.get("contributors") or []:
        if c.get("contribution") in ("Author", "Editor") and not c.get("corporate"):
            authors.append(" ".join(p for p in (c.get("first_name"), c.get("middle_name"), c.get("last_name")) if p))
    publisher = next((p.get("name") for p in item.get("publishers") or [] if p.get("name")), None)
    return {"id": item.get("id"), "title": title, "year": item.get("copyright_year"), "isbn": item.get("isbn13"),
            "license": item.get("license"), "language": item.get("language"), "authors": authors[:8],
            "publisher": publisher, "url": url, "subject": subject,
            "subjects": [s.get("name") for s in item.get("subjects") or [] if s.get("name")],
            "description": " ".join(str(item.get("description") or "").split())[:600]}


def otl_harvest(data_dir: Path, fetch, delay: float = 1.0, sleep=time.sleep, max_pages: int = 30) -> int:
    """Télécharge le catalogue des matières retenues (une page par seconde) et l'enregistre localement."""
    records: dict[str, dict] = {}
    for subject_id, subject in OTL_SUBJECTS.items():
        url = f"{_OTL}/subjects/{subject_id}.json?page=1"
        for _ in range(max_pages):
            data = json.loads(fetch(url) or "{}")
            for item in data.get("data") or []:
                record = _otl_record(item, subject)
                if record:
                    records.setdefault(str(record["id"]), record)
            url = (data.get("links") or {}).get("next")
            if not url or not str(url).startswith(_OTL + "/"):
                break
            sleep(delay)
    if not records:
        raise ValueError("Catalogue Open Textbook Library vide ou indisponible.")
    _otl_cache(data_dir).write_text(json.dumps({"harvested": datetime.now().isoformat(timespec="seconds"),
                                                "records": list(records.values())}, ensure_ascii=False),
                                    encoding="utf-8")
    return len(records)


def otl_records(data_dir: Path) -> list[dict]:
    path = _otl_cache(data_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("records", []) if path.exists() else []
    except (OSError, ValueError):
        return []


def otl_stale(data_dir: Path, days: int = 30) -> bool:
    path = _otl_cache(data_dir)
    return not path.exists() or datetime.fromtimestamp(path.stat().st_mtime) < datetime.now() - timedelta(days=days)


def otl_parser(records: list[dict]):
    def parse(_text: str | None, query: str) -> list[DiscoveredWork]:
        works = []
        for r in records:
            score = relevance(query, r["title"], " ".join(r.get("subjects") or []), r.get("description"))
            if score < 0.5:
                continue
            works.append(DiscoveredWork(
                item_id=f"otl:{r['id']}", service="open_textbooks", title=r["title"], authors=r.get("authors") or [],
                year=r.get("year"), source_type="book", publisher=r.get("publisher"),
                language={"eng": "en", "spa": "es", "fre": "fr", "fra": "fr"}.get(r.get("language") or "", None),
                landing_url=r["url"],
                license=f"manuel sous licence ouverte ({r.get('license') or 'voir la page'}) — PDF gratuit sur la page",
                open_access=False, relevance=score,
                data=SourceData(authors=[_person(a) for a in (r.get("authors") or [])], title=r["title"],
                                year=r.get("year"), publisher=r.get("publisher"), isbn=r.get("isbn"), url=r["url"])))
        return works
    parse.__name__ = "parse_open_textbooks"
    return parse


# --- plans pour find_by_topic -----------------------------------------------------------------------------

def plans(query: str, per: int, kind: str, textbooks: list[dict] | None = None) -> list[tuple]:
    found: list[tuple] = []
    if kind in ("books", "articles", "all"):
        if CYRILLIC.search(query):  # dépôts russophones : recherche en cyrillique seulement
            for service, (_, host) in DSPACE7.items():
                found.append((service, dspace7_url(host, query, per), dspace7_parser(service)))
            for service, (_, host) in OPENSEARCH.items():
                found.append((service, opensearch_url(host, query, per), opensearch_parser(service)))
        found.append(("lareferencia", lareferencia_url(query, per), parse_lareferencia))
    if textbooks and kind in ("books", "all"):
        found.append(("open_textbooks", "", otl_parser(textbooks)))
    return found


# --- guides de rédaction ------------------------------------------------------------------------------------

GUIDE_QUERIES = {
    "tp": {"fr": ["rédiger un compte rendu de travaux pratiques", "rapport de laboratoire rédaction"],
           "ru": ["оформление отчета по лабораторной работе", "методические указания к лабораторным работам"],
           "en": ["how to write a lab report", "laboratory report writing"]},
    "td": {"fr": ["méthodologie travaux dirigés exercices", "méthode de résolution de problèmes"],
           "ru": ["методические указания к практическим занятиям", "решение задач методические указания"],
           "en": ["engineering problem solving", "worked examples engineering mechanics"]},
    "memoire": {"fr": ["méthodologie rédaction mémoire", "rédiger un mémoire de master"],
                "ru": ["оформление выпускной квалификационной работы", "требования к магистерской диссертации"],
                "en": ["thesis writing guide", "writing a dissertation"]},
    "rapport": {"fr": ["rédaction rapport technique", "rédiger un rapport de stage"],
                "ru": ["оформление отчета о научно-исследовательской работе", "оформление отчета по практике"],
                "en": ["technical report writing", "technical writing for engineers"]},
    "projet": {"fr": ["projet de conception mécanique méthodologie", "cahier des charges conception"],
               "ru": ["курсовое проектирование методические указания", "курсовой проект детали машин"],
               "en": ["engineering design project report", "machine design project"]},
}
GUIDE_SERVICES = ["open_textbooks", "urfu", "bntu", "tltsu", "lareferencia", "openalex", "doaj",
                  "open_library", "internet_archive", "hal", "erudit", "cyberleninka", "zenodo"]
WORK_TYPES = {"td": "td", "tp": "tp", "compte_rendu_tp": "tp", "rapport_laboratoire": "tp",
              "memoire_licence": "memoire", "memoire_master": "memoire", "these_doctorat": "memoire",
              "rapport_technique": "rapport", "rapport_de_stage": "rapport", "projet_universitaire": "projet",
              "projet_technique": "projet", "projet_recherche": "memoire"}
