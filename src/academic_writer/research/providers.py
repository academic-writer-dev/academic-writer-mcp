"""Registre des bibliothèques et services de données CONNECTÉS ET OPÉRATIONNELS.

Seules y figurent les bases gratuites interrogées automatiquement et vérifiées par un test réel (2026-11-10 :
9 thèmes de domaines et de langues variés, depuis le poste de l'utilisateur, mode connecté). Statuts :
PUBLIC_FREE (sans compte) ou FREE_API_KEY (clé gratuite facultative ou configurée). Les services non
opérationnels (Semantic Scholar, CORE, Unpaywall, Europeana) et les bases sans accès automatisé autorisé ont été
retirés le 2026-11-10 (raisons dans docs/LIMITATIONS.md). Les conditions des services peuvent changer.
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
    _p("crossref", "Crossref", "international", "métadonnées DOI, rétractations", "PUBLIC_FREE", "aucune", "non (métadonnées)", "api", "OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 34 références) ; rétractations vérifiées (filtre updates)", "https://api.crossref.org"),
    _p("openalex", "OpenAlex", "international", "travaux, auteurs, institutions", "FREE_API_KEY", "facultative : sans clé, budget gratuit partagé par adresse IP (~100 requêtes/jour) ; clé gratuite ~1 000/jour", "liens OA signalés", "api", "OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 38 références)", "https://api.openalex.org"),
    _p("openaire", "OpenAIRE Graph", "Europe", "publications, données, logiciels", "PUBLIC_FREE", "aucune", "liens de dépôt", "api", "OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 39 références)", "https://api.openaire.eu/graph/v1"),
    _p("doaj", "DOAJ", "international", "revues en libre accès", "PUBLIC_FREE", "aucune", "oui", "api", "OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 33 références)", "https://doaj.org/api"),
    _p("datacite", "DataCite", "international", "jeux de données (DOI)", "PUBLIC_FREE", "aucune", "métadonnées", "api", "OK (jeux de données)", "https://api.datacite.org"),
    _p("orcid", "ORCID (API publique)", "international", "identifiants de chercheurs", "PUBLIC_FREE", "aucune", "—", "api", "OK (test du 2026-11-10 : chercheur trouvé, 0,8 s)", "https://pub.orcid.org"),
    _p("zenodo", "Zenodo", "international", "publications, données", "PUBLIC_FREE", "aucune", "selon licence du dépôt", "api", "OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 37 références)", "https://zenodo.org/api"),
    _p("arxiv", "arXiv", "international", "prépublications", "PUBLIC_FREE", "aucune", "oui", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 33 références)", "https://export.arxiv.org/api"),
    _p("pubmed", "PubMed (NCBI E-utilities)", "international", "biomédecine", "PUBLIC_FREE", "aucune (3 req/s)", "non (métadonnées)", "api", "OK (test du 2026-11-10 : résultats pour 4/9 thèmes de domaines variés, 9 références)", "https://eutils.ncbi.nlm.nih.gov"),
    _p("europe_pmc", "Europe PMC / PubMed Central", "international", "biomédecine", "PUBLIC_FREE", "aucune", "oui pour le sous-ensemble OA", "api", "OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 29 références)", "https://www.ebi.ac.uk/europepmc"),
    _p("eric", "ERIC", "international", "sciences de l'éducation", "PUBLIC_FREE", "aucune", "partiel (autorisation de l'auteur)", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 29 références)", "https://api.ies.ed.gov/eric"),
    _p("worldbank", "World Bank Open Data", "international", "statistiques", "PUBLIC_FREE", "aucune", "données", "api", "OK (test du 2026-11-10 : PIB de la France, 0,7 s)", "https://api.worldbank.org/v2"),
    _p("eurostat", "Eurostat", "Europe", "statistiques", "PUBLIC_FREE", "aucune", "données", "api", "OK (test du 2026-11-10 : PIB de la France, 0,7 s)", "https://ec.europa.eu/eurostat/api"),
    _p("nist", "NIST — constantes CODATA", "international", "constantes physiques fondamentales", "PUBLIC_FREE", "aucune", "données", "api", "OK (CODATA 2022 en copie locale, 355 constantes)", "https://physics.nist.gov/constants"),
    _p("hal", "HAL", "France", "archive ouverte", "PUBLIC_FREE", "aucune", "oui (dépôts)", "api", "OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 33 références)", "https://api.archives-ouvertes.fr"),
    _p("dnb", "Deutsche Nationalbibliothek", "Allemagne", "catalogue de livres", "PUBLIC_FREE", "aucune", "non (catalogue)", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 26 références)", "https://services.dnb.de/sru"),
    _p("google_books", "Google Books", "international", "livres (métadonnées)", "FREE_API_KEY", "clé gratuite", "non", "api", "OK (test du 2026-11-10 avec la clé configurée, 0,8 s)", "https://www.googleapis.com/books"),
    _p("open_library", "Open Library", "international", "livres", "PUBLIC_FREE", "aucune", "prêt / domaine public", "api", "OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 33 références)", "https://openlibrary.org"),
    _p("internet_archive", "Internet Archive", "international", "livres numérisés", "PUBLIC_FREE", "aucune", "seulement licence libre déclarée", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 35 références)", "https://archive.org"),
    _p("jstage", "J-STAGE (JST)", "Japon", "revues scientifiques japonaises", "PUBLIC_FREE", "aucune", "lecture sur le site (licence selon la revue)", "api", "OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 24 références)", "https://api.jstage.jst.go.jp/searchapi/do"),
    _p("ndl", "NDL Search (Bibliothèque nationale de la Diète)", "Japon", "livres, articles, thèses japonais", "PUBLIC_FREE", "aucune", "notices (document selon la bibliothèque)", "api", "OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 12 références)", "https://ndlsearch.ndl.go.jp/api/opensearch"),
    _p("osti", "OSTI.GOV (DOE)", "États-Unis", "rapports techniques, articles, données (énergie, sciences)", "PUBLIC_FREE", "aucune", "souvent sur le site (droits selon le document)", "api", "OK (test du 2026-11-10 : résultats pour 3/9 thèmes de domaines variés, 6 références)", "https://www.osti.gov/api/v1"),
    _p("ntrs", "NASA Technical Reports Server (NTRS)", "États-Unis", "rapports techniques NASA (mécanique, aéronautique, matériaux)", "PUBLIC_FREE", "aucune", "souvent sur le site (documents publics)", "api", "OK (test du 2026-11-10 : résultats pour 4/9 thèmes de domaines variés, 16 références)", "https://ntrs.nasa.gov/api/citations/search"),
    _p("erudit", "Érudit", "Canada", "revues savantes francophones", "PUBLIC_FREE", "aucune (via Crossref)", "libre ou différé selon la revue", "api", "OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 38 références)", "https://www.erudit.org"),
    _p("ajol", "African Journals Online (AJOL)", "Afrique", "≈ 500 revues africaines", "PUBLIC_FREE", "aucune (via Crossref)", "selon la revue (aucun PDF téléchargé : demande du site)", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 31 références)", "https://www.ajol.info"),
    _p("scielo", "SciELO (Brésil, Chili, Afrique du Sud)", "Amérique latine / Afrique", "revues en libre accès", "PUBLIC_FREE", "aucune (via Crossref)", "oui (CC selon la revue)", "api", "OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 29 références)", "https://scielo.org"),
    _p("cyberleninka", "КиберЛенинка", "Russie", "articles en libre accès (≈ 4 000 revues)", "PUBLIC_FREE", "aucune (OAI-PMH officiel)", "sur le site (PDF interdits aux robots)", "api", "OK (test du 2026-11-10 : résultats pour 5/9 thèmes de domaines variés, 14 références) ; OAI-PMH officiel autorisé par robots.txt ; index local de 10 800 articles de génie mécanique", "https://cyberleninka.ru/oai"),
)


def summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for provider in PROVIDERS:
        counts[provider.access] = counts.get(provider.access, 0) + 1
    return counts
