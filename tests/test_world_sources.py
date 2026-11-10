"""Bibliothèques d'Asie, des Amériques et d'Afrique : analyseurs (extraits de réponses réelles) et honnêteté."""

import json

from academic_writer.research import world_sources as world
from academic_writer.research.discovery import find_by_topic
from academic_writer.research.providers import PROVIDERS

JSTAGE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
  <entry>
    <article_title><en><![CDATA[Experimental Study on Characteristics of Maple Seed Type Wind Turbine]]></en>
      <ja><![CDATA[カエデの種型風車の風車特性に関する実験的研究]]></ja></article_title>
    <article_link><en>https://www.jstage.jst.go.jp/article/jjsem/14/3/14_141/_article</en></article_link>
    <author><en><name><![CDATA[Kunio SHIMADA]]></name><name><![CDATA[Takehiro MIYOSHI]]></name></en></author>
    <material_title><en><![CDATA[Journal of the Japanese Society for Experimental Mechanics]]></en></material_title>
    <prism:issn>1346-4930</prism:issn><prism:volume>14</prism:volume><prism:number>3</prism:number>
    <prism:startingPage>141</prism:startingPage><prism:endingPage>146</prism:endingPage>
    <pubyear>2014</pubyear><prism:doi>10.11395/jjsem.14.141</prism:doi>
  </entry>
  <entry><article_title><en>Lien suspect</en></article_title><article_link><en>https://exemple.org/x</en></article_link></entry>
</feed>"""

NDL = """<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" version="2.0"><channel>
  <item>
    <title>直線翼ダリウス風車の出力特性</title>
    <link>https://ndlsearch.ndl.go.jp/books/R000000004-I030272956</link>
    <category>記事</category>
    <dc:title>直線翼ダリウス風車の出力特性</dc:title>
    <dc:creator>安田 進之介</dc:creator><dc:creator>濱田 健太郎</dc:creator>
    <dc:date>2019</dc:date><dc:subject>wind turbine</dc:subject>
    <rdfs:seeAlso rdf:resource="https://doi.org/10.11333/jweasympo.41.0_231"/>
  </item>
</channel></rss>"""

OSTI = [{"osti_id": "17426618", "title": "Enhancing the Computational Efficiency of FAST.Farm for wind turbines",
         "authors": ["Jonkman, Jason [National Laboratory of the Rockies, Golden, CO (United States)] "
                     "(ORCID:0000000329907362)", "Yu, Wenchao [TotalEnergies]"],
         "publication_date": "2026-10-23T00:00:00Z", "doi": "10.66816/pr6235110", "product_type": "Conference",
         "language": "English", "subjects": ["17 WIND ENERGY"], "research_orgs": ["NLR, Golden, CO (United States)"],
         "links": [{"rel": "citation", "href": "https://www.osti.gov/biblio/17426618"},
                   {"rel": "fulltext", "href": "https://www.osti.gov/servlets/purl/17426618"}]}]

CROSSREF = {"message": {"items": [{"DOI": "10.7202/1065035ar", "type": "journal-article",
                                   "title": ["La justice négociée de l’énergie éolienne au Québec"],
                                   "author": [{"given": "Marie", "family": "Tremblay"}],
                                   "container-title": ["Recherches sociographiques"], "publisher": "Consortium Erudit",
                                   "issued": {"date-parts": [[2019]]}}]}}


def test_jstage_parser() -> None:
    works = world.parse_jstage(JSTAGE, "wind turbine")
    assert len(works) == 1  # lien hors J-STAGE écarté
    work = works[0]
    assert work.service == "jstage" and work.year == 2014 and work.doi == "10.11395/jjsem.14.141"
    assert work.authors == ["Kunio SHIMADA", "Takehiro MIYOSHI"] and work.data.pages == "141–146"
    assert work.container.startswith("Journal of the Japanese") and work.relevance == 1.0 and not work.open_access


def test_ndl_parser_uses_subjects_and_doi() -> None:
    work = world.parse_ndl(NDL, "wind turbine")[0]
    assert work.service == "ndl" and work.source_type == "article" and work.year == 2019
    assert work.doi == "10.11333/jweasympo.41.0_231" and work.relevance == 1.0  # trouvé par le sujet


def test_osti_parser_cleans_authors() -> None:
    work = world.parse_osti(json.dumps(OSTI), "wind turbine")[0]
    assert work.authors == ["Jonkman, Jason", "Yu, Wenchao"] and work.source_type == "conference"
    assert work.landing_url == "https://www.osti.gov/biblio/17426618" and work.language == "en"
    assert world.parse_osti("pas du json", "x") == []


def test_regional_platforms_use_crossref_prefix() -> None:
    url = world.regional_crossref_url("scielo", "soil erosion", 5)
    assert url.startswith("https://api.crossref.org/works?") and "prefix:10.1590,prefix:10.4067,prefix:10.17159" in url
    seen = []

    def fetch(url: str) -> str:
        seen.append(url)
        return json.dumps(CROSSREF) if "prefix:10.7202" in url else "{}"

    result = find_by_topic("énergie éolienne", fetch, "articles", services_filter=["erudit"])
    assert result.services == ["erudit"] and all("api.crossref.org" in u for u in seen)  # jamais le site lui-même
    assert result.works[0].service == "erudit" and "Érudit" in result.works[0].license


def test_world_registry_matches_integration() -> None:
    planned = {p[0] for p in world.plans("x", 5, "all")}
    world_api = {p.id for p in PROVIDERS if p.integration == "api" and p.access == "PUBLIC_FREE"}
    assert {"jstage", "ndl", "osti", "erudit", "ajol", "scielo"} <= planned
    assert {"jstage", "ndl", "osti", "erudit", "ajol", "scielo"} <= world_api
    by_id = {p.id: p for p in PROVIDERS}
    # interdits aux robots ou refusés : retirés du registre et jamais interrogés
    for excluded in ("cinii", "rda", "loc", "dpla", "trove", "redalyc"):
        assert excluded not in by_id and excluded not in planned
    # recherche « libre accès seulement » : ces notices ne sont pas présentées comme libres
    assert not {p for p in planned if p in {"jstage", "ndl"}} & set(find_by_topic(
        "x", lambda _u: None, "articles", open_access_only=True).services)
