"""Lot 3 : OpenAlex, OpenAIRE, ERIC, DNB, ORCID, rétractations, données ouvertes, registre des fournisseurs."""

import json

from academic_writer.research import openscience_more as more
from academic_writer.research.discovery import find_by_topic
from academic_writer.research.providers import PROVIDERS

OPENALEX = {"results": [
    {"id": "https://openalex.org/W1", "display_name": "Slider crank kinematics", "publication_year": 2019,
     "type": "article", "doi": "https://doi.org/10.1/a", "authorships": [{"author": {"display_name": "Ann Lee"}}],
     "best_oa_location": {"pdf_url": "https://x.org/a.pdf", "license": "cc-by"}, "is_retracted": False},
    {"id": "https://openalex.org/W2", "display_name": "Slider crank kinematics revisited", "publication_year": 2012,
     "type": "article", "doi": "https://doi.org/10.1/b", "authorships": [{"author": {"display_name": "Bob Roe"}}],
     "best_oa_location": {"pdf_url": "https://x.org/b.pdf", "license": "cc-by"}, "is_retracted": True},
]}
DNB = """<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><records><record><recordData>
<dc xmlns="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Getriebetechnik : Grundlagen / Hans Muster</dc:title><dc:creator>Muster, Hans [Verfasser]</dc:creator>
<dc:publisher>Berlin : Springer</dc:publisher><dc:date>2020</dc:date>
<dc:identifier xsi:type="tel:ISBN">978-3-662-00000-0 : EUR 50</dc:identifier>
<dc:identifier xsi:type="dnb:IDN">1234567890</dc:identifier></dc></recordData></record></records>
</searchRetrieveResponse>"""


def fetch(url: str) -> str | None:
    if "api.openalex.org" in url:
        return json.dumps(OPENALEX)
    if "services.dnb.de" in url:
        return DNB
    return None


def test_openalex_filters_retraction_and_open_access() -> None:
    result = find_by_topic("slider crank kinematics", fetch, "articles", services_filter=["openalex"])
    titles = {w.title: w for w in result.works}
    assert titles["Slider crank kinematics"].open_access
    retracted = titles["[RÉTRACTÉ] Slider crank kinematics revisited"]
    assert not retracted.open_access and any("RÉTRACTÉ" in n for n in result.notices)
    recent = find_by_topic("slider crank kinematics", fetch, "articles", services_filter=["openalex"], year_from=2015)
    assert [w.year for w in recent.works] == [2019]
    by_author = find_by_topic("slider crank kinematics", fetch, "articles", services_filter=["openalex"], author="roe")
    assert len(by_author.works) == 1
    assert "filter=publication_year" in more.openalex_url("x", 5, 2015, None, "article", "KEY") and "api_key=KEY" in \
        more.openalex_url("x", 5, key="KEY")


def test_dnb_isbn_is_not_the_record_number() -> None:
    work = more.parse_dnb(DNB, "Getriebetechnik")[0]
    assert work.title == "Getriebetechnik : Grundlagen" and work.data.isbn == "978-3-662-00000-0"
    assert work.data.place == "Berlin" and work.data.publisher == "Springer" and work.authors == ["Muster, Hans"]


def test_crossref_retraction_notices() -> None:
    payload = {"message": {"items": [{"DOI": "10.9/notice", "title": ["Retraction"],
                                      "update-to": [{"type": "retraction", "DOI": "10.1/x",
                                                     "updated": {"date-parts": [[2010, 2, 6]]}}]}]}}
    notices = more.crossref_updates("10.1/X", lambda _url: json.dumps(payload))
    assert notices[0].type == "retraction" and notices[0].date == "2010-2-6"


def test_open_data_parsers() -> None:
    wb = [{"lastupdated": "2026-10-08"}, [{"indicator": {"value": "GDP (current US$)"}, "country": {"value": "France"},
                                           "date": "2021", "value": 2.9e12}]]
    result = more.worldbank("NY.GDP.MKTP.CD", "FR", "2021", lambda _url: json.dumps(wb))
    assert result.points[0].value == 2.9e12 and result.updated == "2026-10-08"
    es = {"id": ["geo", "time"], "size": [1, 2], "label": "GDP", "value": {"0": 1.0, "1": 2.0},
          "dimension": {"geo": {"category": {"index": {"FR": 0}, "label": {"FR": "France"}}},
                        "time": {"category": {"index": {"2020": 0, "2021": 1}}}}}
    points = more.eurostat("nama_10_gdp", {"geo": "FR"}, lambda _url: json.dumps(es)).points
    assert [(p.dimensions["time"], p.value) for p in points] == [("2020", 1.0), ("2021", 2.0)]


def test_provider_registry_is_honest() -> None:
    by_id = {p.id: p for p in PROVIDERS}
    # le registre ne contient que des bases connectées et vérifiées ; les autres ont été retirées
    assert all(p.integration == "api" and p.verification.startswith("OK") for p in PROVIDERS)
    assert not {"base", "viniti", "semantic_scholar", "core", "unpaywall", "europeana", "elibrary"} & set(by_id)
    russian_api = [p for p in PROVIDERS if p.region == "Russie" and p.integration == "api"]
    # sources russes : seulement par des interfaces publiques autorisées par robots.txt (OAI-PMH, DSpace, OpenSearch)
    assert {p.id for p in russian_api} == {"cyberleninka", "tltsu", "urfu"}
    assert all("robots.txt" in p.verification for p in russian_api)
    assert "OAI-PMH" in next(p for p in russian_api if p.id == "cyberleninka").verification
    assert all(p.integration != "api" or p.access in ("PUBLIC_FREE", "FREE_API_KEY", "FREE_ACCOUNT") for p in PROVIDERS)


CODATA = """             Fundamental Physical Constants --- Complete Listing
             2022 CODATA adjustment

  Quantity                                                       Value                 Uncertainty           Unit
-----------------------------------------------------------------------------------------------------------------------------
Avogadro constant                                           6.022 140 76 e23         (exact)                  mol^-1
electron mass                                               9.109 383 7139 e-31      0.000 000 0028 e-31      kg
Newtonian constant of gravitation                           6.674 30 e-11            0.000 15 e-11            m^3 kg^-1 s^-2
"""


def test_codata_constants_offline_cache(tmp_path) -> None:
    from academic_writer.research.reference_data import load_codata, parse_codata, search_constants

    source, constants = parse_codata(CODATA)
    assert source == "CODATA 2022 (NIST)" and len(constants) == 3
    assert search_constants(constants, "avogadro")[0].value == 6.02214076e23
    assert search_constants(constants, "electron mass")[0].uncertainty.startswith("0.000")
    loaded, origin = load_codata(tmp_path, lambda _url: CODATA, allow_network=True)
    assert origin.startswith("téléchargée") and len(loaded) == 3
    again, origin = load_codata(tmp_path, lambda _url: None, allow_network=False)  # hors connexion : copie locale
    assert origin == "copie locale" and len(again) == 3


OAI_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>
<record><header><identifier>x</identifier></header><metadata>
<oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Кинематический анализ кривошипно-ползунного механизма</dc:title><dc:creator>Иванов И. И.</dc:creator>
<dc:publisher>МГТУ</dc:publisher><dc:identifier>https://cyberleninka.ru/article/n/kinematicheskiy-analiz</dc:identifier>
</oai_dc:dc></metadata></record>
<resumptionToken cursor="10">TOKEN1</resumptionToken></ListRecords></OAI-PMH>"""
OAI_LAST = OAI_PAGE.replace("<resumptionToken cursor=\"10\">TOKEN1</resumptionToken>", "").replace(
    "kinematicheskiy-analiz", "dinamika-mashin").replace("Кинематический анализ кривошипно-ползунного механизма",
                                                          "Динамика машин с упругими звеньями")


def test_cyberleninka_oai_harvest_and_local_search(tmp_path) -> None:
    """КиберЛенинка : moissonnage OAI-PMH (avec reprise), index local, recherche sur le titre ; aucun PDF."""
    from academic_writer.research import cyberleninka as cl

    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return OAI_PAGE if "set=journal_1" in url else OAI_LAST

    result = cl.harvest(tmp_path, fetch, "journal_1", "Динамика систем, механизмов и машин", sleep=lambda _s: None)
    assert result.records == 2 and result.complete and "resumptionToken=TOKEN1" in calls[1]
    assert all("/oai?" in c for c in calls)  # seule l'interface OAI-PMH autorisée est interrogée
    records = cl.harvested(tmp_path)
    found = find_by_topic("кинематический анализ механизма", lambda _u: None, "articles", services_filter=["cyberleninka"],
                          local_records=records)
    assert [w.title for w in found.works] == ["Кинематический анализ кривошипно-ползунного механизма"]
    assert not found.works[0].open_access and found.works[0].landing_url.startswith("https://cyberleninka.ru/article/")
    import pytest
    with pytest.raises(ValueError):
        cl.harvest(tmp_path, fetch, "../etc", "x")
    assert "language:ru" in more.openalex_url("x", 5, language="ru")
