"""Recherche ciblée par discipline : sources et filtres SPÉCIALISÉS (vérifiés le 2026-11-10).

Génie mécanique (au sens large : conception, mécanique des solides, RDM, TMM, éléments de machines, fabrication,
matériaux, automobile, aéronautique, maintenance) :
- OpenAlex : sous-domaines « Mechanical Engineering » (2210), « Mechanics of Materials » (2211),
  « Industrial and Manufacturing Engineering » (2209), « Automotive » (2203), « Aerospace » (2202),
  « Computational Mechanics » (2206) ;
- DOAJ : revues classées LCC TJ (génie mécanique, machines), TL (véhicules, aéronautique), TS (fabrication),
  TA349-359 (mécanique appliquée), TA401-492 (matériaux, résistance des matériaux) ;
- J-STAGE : revues de la Société japonaise des ingénieurs mécaniciens (JSME) ;
- NASA NTRS : rapports techniques de la NASA (API publique, autorisée par robots.txt) ;
- КиберЛенинка : 18 revues russes de génie mécanique à moissonner (OAI-PMH officiel).
Les bases hors sujet (PubMed, Europe PMC, ERIC) et NDL (lente ; JSME interrogée directement) sont retirées.
Écarté : engrXiv (API OSF interdite aux robots par robots.txt).
"""

from __future__ import annotations

import json
import urllib.parse

from pydantic import BaseModel

from academic_writer.research.discovery import DiscoveredWork, relevance
from academic_writer.research.models import SourceData
from academic_writer.research.online import _person, _year


class Discipline(BaseModel):
    id: str
    name: str
    openalex_subfields: tuple[str, ...]
    doaj_lcc: tuple[str, ...]
    jstage_journals: tuple[str, ...]
    ntrs: bool
    cyberleninka_journals: dict[str, str]
    skip_services: tuple[str, ...]


_MECHANICAL_RU = {
    "journal_11101": "Вестник МГТУ им. Н. Э. Баумана. Серия «Машиностроение»",
    "journal_31042": "Известия высших учебных заведений. Машиностроение",
    "journal_31354": "Вестник ПНИПУ. Машиностроение, материаловедение",
    "journal_16168": "Вестник ЮУрГУ. Серия: Машиностроение",
    "journal_31377": "Вестник ПНИПУ. Механика",
    "journal_23401": "Транспортное машиностроение",
    "journal_6161": "Машиностроение и компьютерные технологии",
    "journal_18358": "Обработка металлов: технология, оборудование, инструменты",
    "journal_11155": "Металлообработка",
    "journal_32245": "Динамика систем, механизмов и машин",
    "journal_36953": "Механика и технология",
    "journal_36903": "Журнал теоретической и прикладной механики",
    "journal_33667": "Вестник Самарского университета. Аэрокосмическая техника, технологии и машиностроение",
    "journal_35453": "Инженерный журнал: наука и инновации",
    "journal_6567": "Физическая мезомеханика",
    "journal_32484": "Качество в обработке материалов",
    "journal_29527": "Авиационные материалы и технологии",
    "journal_7896": "Вестник РУДН. Серия: Инженерные исследования",
}

_MECHANICAL = Discipline(
    id="genie_mecanique", name="Génie mécanique",
    openalex_subfields=("2210", "2211", "2209", "2203", "2202", "2206"),
    doaj_lcc=("TJ1-1570", "TL1-4050", "TS1-2301", "TA349-359", "TA401-492"),
    jstage_journals=("mej", "jamdsm", "transjsme"),
    ntrs=True, cyberleninka_journals=_MECHANICAL_RU, skip_services=("pubmed", "europe_pmc", "eric", "ndl"))

# profils de discipline du serveur rattachés au génie mécanique général
DISCIPLINES = {"genie_mecanique": _MECHANICAL}
ALIASES = {"fabrication_mecanique": "genie_mecanique", "materiaux_metallurgie": "genie_mecanique",
           "automobile_engins": "genie_mecanique", "maintenance_industrielle": "genie_mecanique",
           "mecanique": "genie_mecanique", "mechanical_engineering": "genie_mecanique"}


def get(discipline: str | None) -> Discipline | None:
    if not discipline:
        return None
    key = ALIASES.get(discipline, discipline)
    if key not in DISCIPLINES:
        raise ValueError(f"Discipline inconnue : {discipline} (disponible : génie mécanique « genie_mecanique »).")
    return DISCIPLINES[key]


def doaj_query(query: str, profile: Discipline) -> str:
    codes = " OR ".join(f'index.schema_codes_tree:"LCC:{code}"' for code in profile.doaj_lcc)
    return f"({query}) AND ({codes})"


# --- NASA NTRS ----------------------------------------------------------------------------------------

def ntrs_url(query: str, per: int) -> str:
    return f"https://ntrs.nasa.gov/api/citations/search?page.size={per}&q=" + urllib.parse.quote(query)


def parse_ntrs(text: str | None, query: str) -> list[DiscoveredWork]:
    try:
        results = (json.loads(text) if text else {}).get("results") or []
    except (ValueError, AttributeError):
        return []
    works = []
    for record in results:
        title, record_id = " ".join(str(record.get("title") or "").split()), str(record.get("id") or "")
        if not title or not record_id.isdigit():
            continue
        authors = [((a.get("meta") or {}).get("author") or {}).get("name", "")
                   for a in record.get("authorAffiliations") or []]
        authors = [" ".join(a.split()) for a in authors if a and a.strip()]
        publication = (record.get("publications") or [{}])[0] or {}
        year = _year(publication.get("publicationDate") or record.get("distributionDate") or record.get("created"))
        landing = f"https://ntrs.nasa.gov/citations/{record_id}"
        journal = publication.get("publicationName") or None
        doi = publication.get("doi") or None
        public = record.get("distribution") == "PUBLIC" and str(record.get("downloadsAvailable")) == "True"
        works.append(DiscoveredWork(
            item_id=f"ntrs:{record_id}", service="ntrs", title=title, authors=authors, year=year,
            source_type="article" if journal else "report", container=journal,
            publisher=publication.get("publisher") or "NASA", language="en", doi=doi, landing_url=landing,
            license=("NASA NTRS : document public consultable sur le site (droits selon le document)" if public
                     else "NASA NTRS : notice"),
            open_access=False,
            relevance=relevance(query, title, " ".join(record.get("keywords") or []),
                                " ".join(record.get("subjectCategories") or [])),
            data=SourceData(authors=[_person(a) for a in authors[:10]], title=title, container=journal, year=year,
                            doi=doi, url=landing, publisher=publication.get("publisher") or "NASA",
                            volume=publication.get("volume") or None, issue=publication.get("issue") or None,
                            language="en")))
    return works


def extra_plans(profile: Discipline, query: str, per: int, kind: str) -> list[tuple]:
    from academic_writer.research import world_sources as world

    plans: list[tuple] = []
    if kind in ("articles", "all"):
        for code in profile.jstage_journals:
            plans.append(("jstage", world.jstage_url(query, per) + f"&cdjournal={code}", world.parse_jstage))
        if profile.ntrs:
            plans.append(("ntrs", ntrs_url(query, per), parse_ntrs))
    return plans
