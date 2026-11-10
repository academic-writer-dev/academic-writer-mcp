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
    assert by_id["base"].integration == "excluded" and by_id["viniti"].access == "PAID_EXCLUDED"
    assert all(p.integration != "api" for p in PROVIDERS if p.region == "Russie")  # aucune extraction automatique
    assert all(p.integration != "api" or p.access in ("PUBLIC_FREE", "FREE_API_KEY", "FREE_ACCOUNT") for p in PROVIDERS)
