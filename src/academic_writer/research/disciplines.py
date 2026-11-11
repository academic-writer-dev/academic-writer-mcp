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
    openalex_journals: dict[str, str] = {}


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
    "journal_22732": "Записки Горного института (Санкт-Петербургский горный университет)",
    "journal_34950": "Горное оборудование и электромеханика",
}

# Revues russes de génie mécanique interrogées par l'API OpenAlex (identifiants vérifiés le 2026-11-11)
_MECHANICAL_RU_OPENALEX = {
    "S4210196529": "Вестник МГТУ «Станкин» (СТАНКИН)",
    "S4306530908": "СТИН (Станки и инструмент)",
    "S4210240895": "RUDN Journal of Engineering Research (РУДН)",
    "S4306538689": "Вестник РУДН. Серия: Инженерные исследования",
    "S4210178371": "Записки Горного института (Горный университет)",
    "S4210180145": "Горные науки и технологии (МИСИС)",
    "S4306539224": "Известия высших учебных заведений. Машиностроение",
    "S7407058982": "Технология машиностроения",
}

_MECHANICAL = Discipline(
    id="genie_mecanique", name="Génie mécanique",
    openalex_subfields=("2210", "2211", "2209", "2203", "2202", "2206", "2506", "2503"),
    doaj_lcc=("TJ1-1570", "TL1-4050", "TS1-2301", "TA349-359", "TA401-492"),
    jstage_journals=("mej", "jamdsm", "transjsme"),
    ntrs=True, cyberleninka_journals=_MECHANICAL_RU, skip_services=("pubmed", "europe_pmc", "eric", "ndl"),
    openalex_journals=_MECHANICAL_RU_OPENALEX)

# profils de discipline du serveur rattachés au génie mécanique général
DISCIPLINES = {"genie_mecanique": _MECHANICAL}
ALIASES = {"fabrication_mecanique": "genie_mecanique", "materiaux_metallurgie": "genie_mecanique",
           "automobile_engins": "genie_mecanique", "maintenance_industrielle": "genie_mecanique",
           "mecanique": "genie_mecanique", "mechanical_engineering": "genie_mecanique"}


# Autres domaines (profils du serveur) : filtre OpenAlex par champ ou sous-domaine (vérifiés le 2026-11-10)
_F, _S = "primary_topic.field.id:", "primary_topic.subfield.id:"
DOMAIN_OPENALEX = {
    "agriculture": _F + "11", "architecture": _S + "2216|2215", "arts": _S + "1213|1210",
    "audiovisuel": _S + "2214|1213", "automatisation": _S + "2207", "biologie": _F + "13|11|24",
    "chimie": _F + "16|15", "design": _S + "1213|1704", "droit": _S + "3308", "economie": _F + "20",
    "education": _S + "3304", "electronique": _S + "2208|1708|1711", "environnement": _F + "23",
    "finance_comptabilite": _F + "14|20", "genie_civil": _S + "2205|2215", "genie_electrique": _S + "2208",
    "geologie": _F + "19", "gestion": _F + "14", "histoire": _S + "1202", "ia_data_science": _S + "1702|1707|1710",
    "informatique": _F + "17", "langues_linguistique": _S + "1203|3310", "mathematiques": _F + "26",
    "medecine": _F + "27", "pharmacie": _F + "30", "philosophie": _S + "1211", "physique": _F + "31",
    "psychologie": _F + "32", "sciences_humaines": _F + "33|12", "sciences_politiques": _S + "3320|3312",
    "sociologie": _S + "3312", "sport": _S + "3612", "tourisme": _S + "1409",
}


def openalex_filter(profile: Discipline) -> str:
    return _S + "|".join(profile.openalex_subfields)


def resolve(domain_id: str | None) -> tuple[Discipline | None, str | None]:
    """Profil spécialisé (génie mécanique) et filtre OpenAlex d'un domaine du serveur ; (None, None) si inconnu."""
    if not domain_id:
        return None, None
    key = ALIASES.get(domain_id, domain_id)
    if key in DISCIPLINES:
        return DISCIPLINES[key], openalex_filter(DISCIPLINES[key])
    return None, DOMAIN_OPENALEX.get(key)


PRIORITY = "genie_mecanique"


def detect(query: str, profiles: list) -> str | None:
    """Domaine d'une recherche d'après le vocabulaire des profils (fr, ru, en) ; None si incertain."""
    from academic_writer.domains.detection import score_profiles

    scores, _ = score_profiles(query, [p for p in profiles if p.id != "generaliste"])
    if not scores or scores[0].score <= 0:
        return None
    # programme principal de l'utilisateur : le génie mécanique l'emporte s'il est presque à égalité (≥ 80 %)
    close = [s for s in scores if ALIASES.get(s.profile.id, s.profile.id) == PRIORITY
             and s.score >= 0.8 * scores[0].score]
    if close:
        return close[0].profile.id
    top = [s for s in scores if s.score == scores[0].score]
    targets = {ALIASES.get(s.profile.id, s.profile.id) for s in top}
    if len(targets) != 1:
        return None
    domain = top[0].profile.id
    return domain if resolve(domain) != (None, None) else None


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


def journals_parser():
    from academic_writer.research import openscience_more as more

    def parse(text: str | None, query: str) -> list[DiscoveredWork]:
        works = more.parse_openalex(text, query)
        for work in works:
            work.service = "revues_ru_meca"
        return works
    parse.__name__ = "parse_revues_ru_meca"
    return parse


def extra_plans(profile: Discipline, query: str, per: int, kind: str, openalex_key: str | None = None) -> list[tuple]:
    from academic_writer.research import openscience_more as more
    from academic_writer.research import world_sources as world

    plans: list[tuple] = []
    if kind in ("articles", "all"):
        for code in profile.jstage_journals:
            plans.append(("jstage", world.jstage_url(query, per) + f"&cdjournal={code}", world.parse_jstage))
        if profile.ntrs:
            plans.append(("ntrs", ntrs_url(query, per), parse_ntrs))
        if profile.openalex_journals:  # revues d'universités russes (СТАНКИН, РУДН, Горный…) par l'API OpenAlex
            journal_filter = "primary_location.source.id:" + "|".join(profile.openalex_journals)
            plans.append(("revues_ru_meca", more.openalex_url(query, per, key=openalex_key, topic_filter=journal_filter),
                          journals_parser()))
    return plans
