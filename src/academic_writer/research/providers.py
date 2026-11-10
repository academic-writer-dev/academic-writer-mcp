"""Registre des fournisseurs documentaires et de données : statut de gratuité (A / B / C) et vérification réelle.

Statuts : PUBLIC_FREE (A), FREE_ACCOUNT / FREE_API_KEY (B), PAID_EXCLUDED, UNVERIFIED_EXCLUDED, UNAVAILABLE (C ou
non utilisable). « integration » : api (interrogé automatiquement), manual_link (lien à ouvrir par l'utilisateur,
aucune extraction automatique), excluded. Vérification réelle effectuée le 2026-11-10 depuis le poste de
l'utilisateur (mode connecté) ; les conditions peuvent changer : relancer la vérification avant de s'y fier.
"""

from __future__ import annotations

from pydantic import BaseModel

VERIFIED_ON = "2026-11-10"


class Provider(BaseModel):
    id: str
    name: str
    region: str
    content: str
    access: str
    key: str
    full_text: str
    integration: str
    verification: str
    url: str


def _p(id, name, region, content, access, key, full_text, integration, verification, url) -> Provider:
    return Provider(id=id, name=name, region=region, content=content, access=access, key=key, full_text=full_text,
                    integration=integration, verification=verification, url=url)


PROVIDERS: tuple[Provider, ...] = (
    _p("crossref", "Crossref", "international", "métadonnées DOI, rétractations", "PUBLIC_FREE", "aucune",
       "non (métadonnées)", "api", "OK (recherche, filtre updates)", "https://api.crossref.org"),
    _p("openalex", "OpenAlex", "international", "travaux, auteurs, institutions", "FREE_API_KEY",
       "facultative : sans clé, budget gratuit partagé par adresse IP (~100 requêtes/jour) ; clé gratuite ~1 000/jour",
       "liens OA signalés", "api", "OK (avis de budget dans la réponse)", "https://api.openalex.org"),
    _p("semantic_scholar", "Semantic Scholar", "international", "articles, citations", "FREE_API_KEY",
       "facultative mais demandée avec une adresse institutionnelle", "PDF OA signalés", "api",
       "HTTP 429 sans clé (quota public saturé)", "https://api.semanticscholar.org"),
    _p("core", "CORE", "international", "dépôts en libre accès", "FREE_API_KEY", "obligatoire (gratuite)",
       "oui (dépôts OA)", "api", "non testé (pas de clé)", "https://api.core.ac.uk/v3"),
    _p("base", "BASE (Bielefeld)", "international", "dépôts académiques", "UNVERIFIED_EXCLUDED",
       "accès API sur autorisation par adresse IP", "—", "excluded", "refus « Access denied for IP address »",
       "https://www.base-search.net"),
    _p("openaire", "OpenAIRE Graph", "Europe", "publications, données, logiciels", "PUBLIC_FREE", "aucune",
       "liens de dépôt", "api", "OK", "https://api.openaire.eu/graph/v1"),
    _p("doaj", "DOAJ", "international", "revues en libre accès", "PUBLIC_FREE", "aucune", "oui", "api", "OK",
       "https://doaj.org/api"),
    _p("datacite", "DataCite", "international", "jeux de données (DOI)", "PUBLIC_FREE", "aucune", "métadonnées", "api",
       "OK", "https://api.datacite.org"),
    _p("orcid", "ORCID (API publique)", "international", "identifiants de chercheurs", "PUBLIC_FREE", "aucune", "—",
       "api", "OK", "https://pub.orcid.org"),
    _p("unpaywall", "Unpaywall", "international", "localisation légale du texte intégral", "FREE_ACCOUNT",
       "adresse e-mail obligatoire (fournie par l'utilisateur)", "oui (liens légaux)", "api",
       "non utilisé sans adresse", "https://api.unpaywall.org"),
    _p("zenodo", "Zenodo", "international", "publications, données", "PUBLIC_FREE", "aucune", "selon licence du dépôt",
       "api", "OK", "https://zenodo.org/api"),
    _p("arxiv", "arXiv", "international", "prépublications", "PUBLIC_FREE", "aucune", "oui", "api", "OK",
       "https://export.arxiv.org/api"),
    _p("pubmed", "PubMed (NCBI E-utilities)", "international", "biomédecine", "PUBLIC_FREE", "aucune (3 req/s)",
       "non (métadonnées)", "api", "OK", "https://eutils.ncbi.nlm.nih.gov"),
    _p("europe_pmc", "Europe PMC / PubMed Central", "international", "biomédecine", "PUBLIC_FREE", "aucune",
       "oui pour le sous-ensemble OA", "api", "OK (PDF OA résolu)", "https://www.ebi.ac.uk/europepmc"),
    _p("eric", "ERIC", "international", "sciences de l'éducation", "PUBLIC_FREE", "aucune",
       "partiel (autorisation de l'auteur)", "api", "OK", "https://api.ies.ed.gov/eric"),
    _p("repec", "RePEc / IDEAS", "international", "économie", "UNAVAILABLE", "pas d'API publique de recherche", "—",
       "manual_link", "non intégré", "https://ideas.repec.org"),
    _p("worldbank", "World Bank Open Data", "international", "statistiques", "PUBLIC_FREE", "aucune", "données", "api",
       "OK", "https://api.worldbank.org/v2"),
    _p("eurostat", "Eurostat", "Europe", "statistiques", "PUBLIC_FREE", "aucune", "données", "api", "OK",
       "https://ec.europa.eu/eurostat/api"),
    _p("oecd", "OECD Data (SDMX)", "international", "statistiques", "UNAVAILABLE", "aucune", "données", "manual_link",
       "liste des jeux accessible ; requêtes de données refusées au client automatisé (HTTP 403)", "https://data-explorer.oecd.org"),
    _p("imf", "IMF Data", "international", "statistiques", "PUBLIC_FREE", "aucune", "données", "manual_link",
       "non intégré", "https://data.imf.org"),
    _p("nist", "NIST — constantes CODATA", "international", "constantes physiques fondamentales", "PUBLIC_FREE", "aucune",
       "données", "api", "OK (CODATA 2022, 355 constantes)", "https://physics.nist.gov/constants"),
    _p("hal", "HAL", "France", "archive ouverte", "PUBLIC_FREE", "aucune", "oui (dépôts)", "api",
       "OK (PDF téléchargé et lu)", "https://api.archives-ouvertes.fr"),
    _p("oapen", "OAPEN Library", "Europe", "livres en libre accès", "UNAVAILABLE", "—", "oui en principe", "manual_link",
       "HTTP 403 pour les requêtes automatisées", "https://library.oapen.org"),
    _p("gallica", "Gallica / BnF", "France", "patrimoine numérisé", "UNAVAILABLE", "—", "selon document",
       "manual_link", "HTTP 403 (SRU) depuis ce poste", "https://gallica.bnf.fr"),
    _p("dnb", "Deutsche Nationalbibliothek", "Allemagne", "catalogue de livres", "PUBLIC_FREE", "aucune",
       "non (catalogue)", "api", "OK (SRU)", "https://services.dnb.de/sru"),
    _p("ddb", "Deutsche Digitale Bibliothek", "Allemagne", "patrimoine numérisé", "FREE_API_KEY",
       "clé gratuite sur inscription", "selon document", "manual_link", "non intégré", "https://www.deutsche-digitale-bibliothek.de"),
    _p("europeana", "Europeana", "Europe", "patrimoine culturel", "FREE_API_KEY", "clé personnelle gratuite (la clé de "
       "démonstration n'est pas destinée à l'usage réel)", "selon licence", "api", "format vérifié ; inactif sans clé",
       "https://api.europeana.eu"),
    _p("dart_europe", "DART-Europe", "Europe", "thèses européennes", "UNAVAILABLE", "pas d'API", "liens", "manual_link",
       "pages web uniquement", "https://www.dart-europe.org"),
    _p("google_books", "Google Books", "international", "livres (métadonnées)", "FREE_API_KEY", "clé gratuite",
       "non", "api", "OK (clé configurée)", "https://www.googleapis.com/books"),
    _p("open_library", "Open Library", "international", "livres", "PUBLIC_FREE", "aucune", "prêt / domaine public",
       "api", "OK", "https://openlibrary.org"),
    _p("internet_archive", "Internet Archive", "international", "livres numérisés", "PUBLIC_FREE", "aucune",
       "seulement licence libre déclarée", "api", "OK", "https://archive.org"),
    # Asie, Amériques, Afrique, Océanie (vérifiés le 2026-11-10, User-Agent honnête, robots.txt respecté)
    _p("jstage", "J-STAGE (JST)", "Japon", "revues scientifiques japonaises", "PUBLIC_FREE", "aucune",
       "lecture sur le site (licence selon la revue)", "api", "OK : API de recherche publique (Atom)",
       "https://api.jstage.jst.go.jp/searchapi/do"),
    _p("ndl", "NDL Search (Bibliothèque nationale de la Diète)", "Japon", "livres, articles, thèses japonais",
       "PUBLIC_FREE", "aucune", "notices (document selon la bibliothèque)", "api",
       "OK : OpenSearch autorisé par robots.txt", "https://ndlsearch.ndl.go.jp/api/opensearch"),
    _p("cinii", "CiNii Research (NII)", "Japon", "articles, livres, thèses japonais", "UNAVAILABLE",
       "—", "—", "manual_link", "recherche interdite aux robots (robots.txt) ; ses notices passent par NDL Search",
       "https://cir.nii.ac.jp"),
    _p("osti", "OSTI.GOV (DOE)", "États-Unis", "rapports techniques, articles, données (énergie, sciences)",
       "PUBLIC_FREE", "aucune", "souvent sur le site (droits selon le document)", "api",
       "OK : API publique autorisée par robots.txt", "https://www.osti.gov/api/v1"),
    _p("loc", "Library of Congress", "États-Unis", "catalogue, collections numérisées", "UNAVAILABLE", "—", "—",
       "manual_link", "HTTP 403 au client automatisé (non contourné)", "https://www.loc.gov"),
    _p("dpla", "DPLA", "États-Unis", "collections patrimoniales", "FREE_API_KEY", "clé personnelle obligatoire",
       "selon institution", "manual_link", "HTTP 403 sans clé ; non intégré", "https://dp.la"),
    _p("erudit", "Érudit", "Canada", "revues savantes francophones", "PUBLIC_FREE", "aucune (via Crossref)",
       "libre ou différé selon la revue", "api", "OK : recherche Crossref, préfixe DOI 10.7202",
       "https://www.erudit.org"),
    _p("ajol", "African Journals Online (AJOL)", "Afrique", "≈ 500 revues africaines", "PUBLIC_FREE",
       "aucune (via Crossref)", "selon la revue (aucun PDF téléchargé : demande du site)", "api",
       "OK : recherche Crossref, préfixe DOI 10.4314", "https://www.ajol.info"),
    _p("scielo", "SciELO (Brésil, Chili, Afrique du Sud)", "Amérique latine / Afrique", "revues en libre accès",
       "PUBLIC_FREE", "aucune (via Crossref)", "oui (CC selon la revue)", "api",
       "OK : recherche Crossref, préfixes 10.1590, 10.4067, 10.17159", "https://scielo.org"),
    _p("redalyc", "Redalyc", "Amérique latine", "revues en libre accès", "UNAVAILABLE", "—", "sur le site",
       "manual_link", "OAI-PMH sans résultat ; revues souvent présentes dans DOAJ et OpenAlex",
       "https://www.redalyc.org"),
    _p("trove", "Trove (Bibliothèque nationale d'Australie)", "Australie", "livres, journaux, revues australiens",
       "FREE_API_KEY", "clé personnelle obligatoire (HTTP 401 sans clé)", "selon document", "manual_link",
       "non intégré (pas de clé)", "https://trove.nla.gov.au"),
    _p("rda", "Research Data Australia", "Australie", "jeux de données de recherche", "UNAVAILABLE", "—", "—",
       "manual_link", "API sous /registry/, interdite aux robots (robots.txt)", "https://researchdata.edu.au"),
    # sources russes : pas d'API publique autorisant l'automatisation → liens manuels uniquement
    _p("elibrary", "eLIBRARY.RU / РИНЦ", "Russie", "articles russes", "UNAVAILABLE", "pas d'API publique",
       "selon revue", "manual_link", "lien de recherche (via Яндекс) ; aucune extraction", "https://elibrary.ru"),
    _p("cyberleninka", "КиберЛенинка", "Russie", "articles en libre accès (≈ 4 000 revues)", "PUBLIC_FREE",
       "aucune (OAI-PMH officiel)", "sur le site (PDF interdits aux robots)", "api",
       "OK : OAI-PMH autorisé par robots.txt ; moissonnage par revue + index local", "https://cyberleninka.ru/oai"),
    _p("rsl", "РГБ (dont Электронная библиотека диссертаций)", "Russie", "catalogue, thèses", "UNAVAILABLE",
       "pas d'API publique", "consultation sur place / payante pour certaines thèses", "manual_link",
       "lien de recherche", "https://search.rsl.ru"),
    _p("nlr", "РНБ", "Russie", "catalogue", "UNAVAILABLE", "pas d'API publique", "—", "manual_link", "non intégré",
       "https://nlr.ru"),
    _p("neb", "НЭБ", "Russie", "bibliothèque numérique", "UNVERIFIED_EXCLUDED", "API sur demande (conditions non vérifiées)",
       "selon document", "manual_link", "non intégré", "https://rusneb.ru"),
    _p("gpntb", "ГПНТБ России", "Russie", "catalogue scientifique et technique", "UNAVAILABLE", "pas d'API publique", "—",
       "manual_link", "non intégré", "https://www.gpntb.ru"),
    _p("viniti", "ВИНИТИ РАН", "Russie", "bases d'analyses scientifiques", "PAID_EXCLUDED", "accès sur abonnement", "—",
       "excluded", "non intégré", "http://www.viniti.ru"),
    _p("femb", "Федеральная электронная медицинская библиотека", "Russie", "médecine", "UNAVAILABLE",
       "pas d'API publique", "selon document", "manual_link", "non intégré", "https://femb.ru"),
)


def summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for provider in PROVIDERS:
        counts[provider.access] = counts.get(provider.access, 0) + 1
    return counts
