<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Statut des fournisseurs documentaires

Vérification réelle le 2026-11-10 depuis le poste de l'utilisateur (mode connecté). Répartition : FREE_API_KEY : 2, PUBLIC_FREE : 25.

Statuts : PUBLIC_FREE (A), FREE_ACCOUNT / FREE_API_KEY (B), PAID_EXCLUDED, UNVERIFIED_EXCLUDED, UNAVAILABLE.

| Fournisseur | Région | Contenu | Statut | Clé | Texte intégral | Intégration | Vérification réelle |
|---|---|---|---|---|---|---|---|
| [Crossref](https://api.crossref.org) | international | métadonnées DOI, rétractations | `PUBLIC_FREE` | aucune | non (métadonnées) | api | OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 34 références) ; rétractations vérifiées (filtre updates) |
| [OpenAlex](https://api.openalex.org) | international | travaux, auteurs, institutions | `FREE_API_KEY` | facultative : sans clé, budget gratuit partagé par adresse IP (~100 requêtes/jour) ; clé gratuite ~1 000/jour | liens OA signalés | api | OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 38 références) |
| [OpenAIRE Graph](https://api.openaire.eu/graph/v1) | Europe | publications, données, logiciels | `PUBLIC_FREE` | aucune | liens de dépôt | api | OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 39 références) |
| [DOAJ](https://doaj.org/api) | international | revues en libre accès | `PUBLIC_FREE` | aucune | oui | api | OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 33 références) |
| [DataCite](https://api.datacite.org) | international | jeux de données (DOI) | `PUBLIC_FREE` | aucune | métadonnées | api | OK (jeux de données) |
| [ORCID (API publique)](https://pub.orcid.org) | international | identifiants de chercheurs | `PUBLIC_FREE` | aucune | — | api | OK (test du 2026-11-10 : chercheur trouvé, 0,8 s) |
| [Zenodo](https://zenodo.org/api) | international | publications, données | `PUBLIC_FREE` | aucune | selon licence du dépôt | api | OK (test du 2026-11-10 : résultats pour 9/9 thèmes de domaines variés, 37 références) |
| [arXiv](https://export.arxiv.org/api) | international | prépublications | `PUBLIC_FREE` | aucune | oui | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 33 références) |
| [PubMed (NCBI E-utilities)](https://eutils.ncbi.nlm.nih.gov) | international | biomédecine | `PUBLIC_FREE` | aucune (3 req/s) | non (métadonnées) | api | OK (test du 2026-11-10 : résultats pour 4/9 thèmes de domaines variés, 9 références) |
| [Europe PMC / PubMed Central](https://www.ebi.ac.uk/europepmc) | international | biomédecine | `PUBLIC_FREE` | aucune | oui pour le sous-ensemble OA | api | OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 29 références) |
| [ERIC](https://api.ies.ed.gov/eric) | international | sciences de l'éducation | `PUBLIC_FREE` | aucune | partiel (autorisation de l'auteur) | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 29 références) |
| [World Bank Open Data](https://api.worldbank.org/v2) | international | statistiques | `PUBLIC_FREE` | aucune | données | api | OK (test du 2026-11-10 : PIB de la France, 0,7 s) |
| [Eurostat](https://ec.europa.eu/eurostat/api) | Europe | statistiques | `PUBLIC_FREE` | aucune | données | api | OK (test du 2026-11-10 : PIB de la France, 0,7 s) |
| [NIST — constantes CODATA](https://physics.nist.gov/constants) | international | constantes physiques fondamentales | `PUBLIC_FREE` | aucune | données | api | OK (CODATA 2022 en copie locale, 355 constantes) |
| [HAL](https://api.archives-ouvertes.fr) | France | archive ouverte | `PUBLIC_FREE` | aucune | oui (dépôts) | api | OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 33 références) |
| [Deutsche Nationalbibliothek](https://services.dnb.de/sru) | Allemagne | catalogue de livres | `PUBLIC_FREE` | aucune | non (catalogue) | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 26 références) |
| [Google Books](https://www.googleapis.com/books) | international | livres (métadonnées) | `FREE_API_KEY` | clé gratuite | non | api | OK (test du 2026-11-10 avec la clé configurée, 0,8 s) |
| [Open Library](https://openlibrary.org) | international | livres | `PUBLIC_FREE` | aucune | prêt / domaine public | api | OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 33 références) |
| [Internet Archive](https://archive.org) | international | livres numérisés | `PUBLIC_FREE` | aucune | seulement licence libre déclarée | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 35 références) |
| [J-STAGE (JST)](https://api.jstage.jst.go.jp/searchapi/do) | Japon | revues scientifiques japonaises | `PUBLIC_FREE` | aucune | lecture sur le site (licence selon la revue) | api | OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 24 références) |
| [NDL Search (Bibliothèque nationale de la Diète)](https://ndlsearch.ndl.go.jp/api/opensearch) | Japon | livres, articles, thèses japonais | `PUBLIC_FREE` | aucune | notices (document selon la bibliothèque) | api | OK (test du 2026-11-10 : résultats pour 6/9 thèmes de domaines variés, 12 références) |
| [OSTI.GOV (DOE)](https://www.osti.gov/api/v1) | États-Unis | rapports techniques, articles, données (énergie, sciences) | `PUBLIC_FREE` | aucune | souvent sur le site (droits selon le document) | api | OK (test du 2026-11-10 : résultats pour 3/9 thèmes de domaines variés, 6 références) |
| [NASA Technical Reports Server (NTRS)](https://ntrs.nasa.gov/api/citations/search) | États-Unis | rapports techniques NASA (mécanique, aéronautique, matériaux) | `PUBLIC_FREE` | aucune | souvent sur le site (documents publics) | api | OK (test du 2026-11-10 : résultats pour 4/9 thèmes de domaines variés, 16 références) |
| [Érudit](https://www.erudit.org) | Canada | revues savantes francophones | `PUBLIC_FREE` | aucune (via Crossref) | libre ou différé selon la revue | api | OK (test du 2026-11-10 : résultats pour 8/9 thèmes de domaines variés, 38 références) |
| [African Journals Online (AJOL)](https://www.ajol.info) | Afrique | ≈ 500 revues africaines | `PUBLIC_FREE` | aucune (via Crossref) | selon la revue (aucun PDF téléchargé : demande du site) | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 31 références) |
| [SciELO (Brésil, Chili, Afrique du Sud)](https://scielo.org) | Amérique latine / Afrique | revues en libre accès | `PUBLIC_FREE` | aucune (via Crossref) | oui (CC selon la revue) | api | OK (test du 2026-11-10 : résultats pour 7/9 thèmes de domaines variés, 29 références) |
| [КиберЛенинка](https://cyberleninka.ru/oai) | Russie | articles en libre accès (≈ 4 000 revues) | `PUBLIC_FREE` | aucune (OAI-PMH officiel) | sur le site (PDF interdits aux robots) | api | OK (test du 2026-11-10 : résultats pour 5/9 thèmes de domaines variés, 14 références) ; OAI-PMH officiel autorisé par robots.txt ; index local de 10 800 articles de génie mécanique |
