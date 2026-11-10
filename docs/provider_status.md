<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Statut des fournisseurs documentaires

Vérification réelle le 2026-11-10 depuis le poste de l'utilisateur (mode connecté). Répartition : FREE_ACCOUNT : 1, FREE_API_KEY : 8, PAID_EXCLUDED : 1, PUBLIC_FREE : 25, UNAVAILABLE : 14, UNVERIFIED_EXCLUDED : 2.

Statuts : PUBLIC_FREE (A), FREE_ACCOUNT / FREE_API_KEY (B), PAID_EXCLUDED, UNVERIFIED_EXCLUDED, UNAVAILABLE.

| Fournisseur | Région | Contenu | Statut | Clé | Texte intégral | Intégration | Vérification réelle |
|---|---|---|---|---|---|---|---|
| [Crossref](https://api.crossref.org) | international | métadonnées DOI, rétractations | `PUBLIC_FREE` | aucune | non (métadonnées) | api | OK (recherche, filtre updates) |
| [OpenAlex](https://api.openalex.org) | international | travaux, auteurs, institutions | `FREE_API_KEY` | facultative : sans clé, budget gratuit partagé par adresse IP (~100 requêtes/jour) ; clé gratuite ~1 000/jour | liens OA signalés | api | OK (avis de budget dans la réponse) |
| [Semantic Scholar](https://api.semanticscholar.org) | international | articles, citations | `FREE_API_KEY` | facultative mais demandée avec une adresse institutionnelle | PDF OA signalés | api | HTTP 429 sans clé (quota public saturé) |
| [CORE](https://api.core.ac.uk/v3) | international | dépôts en libre accès | `FREE_API_KEY` | obligatoire (gratuite) | oui (dépôts OA) | api | non testé (pas de clé) |
| [BASE (Bielefeld)](https://www.base-search.net) | international | dépôts académiques | `UNVERIFIED_EXCLUDED` | accès API sur autorisation par adresse IP | — | excluded | refus « Access denied for IP address » |
| [OpenAIRE Graph](https://api.openaire.eu/graph/v1) | Europe | publications, données, logiciels | `PUBLIC_FREE` | aucune | liens de dépôt | api | OK |
| [DOAJ](https://doaj.org/api) | international | revues en libre accès | `PUBLIC_FREE` | aucune | oui | api | OK |
| [DataCite](https://api.datacite.org) | international | jeux de données (DOI) | `PUBLIC_FREE` | aucune | métadonnées | api | OK |
| [ORCID (API publique)](https://pub.orcid.org) | international | identifiants de chercheurs | `PUBLIC_FREE` | aucune | — | api | OK |
| [Unpaywall](https://api.unpaywall.org) | international | localisation légale du texte intégral | `FREE_ACCOUNT` | adresse e-mail obligatoire (fournie par l'utilisateur) | oui (liens légaux) | api | non utilisé sans adresse |
| [Zenodo](https://zenodo.org/api) | international | publications, données | `PUBLIC_FREE` | aucune | selon licence du dépôt | api | OK |
| [arXiv](https://export.arxiv.org/api) | international | prépublications | `PUBLIC_FREE` | aucune | oui | api | OK |
| [PubMed (NCBI E-utilities)](https://eutils.ncbi.nlm.nih.gov) | international | biomédecine | `PUBLIC_FREE` | aucune (3 req/s) | non (métadonnées) | api | OK |
| [Europe PMC / PubMed Central](https://www.ebi.ac.uk/europepmc) | international | biomédecine | `PUBLIC_FREE` | aucune | oui pour le sous-ensemble OA | api | OK (PDF OA résolu) |
| [ERIC](https://api.ies.ed.gov/eric) | international | sciences de l'éducation | `PUBLIC_FREE` | aucune | partiel (autorisation de l'auteur) | api | OK |
| [RePEc / IDEAS](https://ideas.repec.org) | international | économie | `UNAVAILABLE` | pas d'API publique de recherche | — | manual_link | non intégré |
| [World Bank Open Data](https://api.worldbank.org/v2) | international | statistiques | `PUBLIC_FREE` | aucune | données | api | OK |
| [Eurostat](https://ec.europa.eu/eurostat/api) | Europe | statistiques | `PUBLIC_FREE` | aucune | données | api | OK |
| [OECD Data (SDMX)](https://data-explorer.oecd.org) | international | statistiques | `UNAVAILABLE` | aucune | données | manual_link | liste des jeux accessible ; requêtes de données refusées au client automatisé (HTTP 403) |
| [IMF Data](https://data.imf.org) | international | statistiques | `PUBLIC_FREE` | aucune | données | manual_link | non intégré |
| [NIST — constantes CODATA](https://physics.nist.gov/constants) | international | constantes physiques fondamentales | `PUBLIC_FREE` | aucune | données | api | OK (CODATA 2022, 355 constantes) |
| [HAL](https://api.archives-ouvertes.fr) | France | archive ouverte | `PUBLIC_FREE` | aucune | oui (dépôts) | api | OK (PDF téléchargé et lu) |
| [OAPEN Library](https://library.oapen.org) | Europe | livres en libre accès | `UNAVAILABLE` | — | oui en principe | manual_link | HTTP 403 pour les requêtes automatisées |
| [Gallica / BnF](https://gallica.bnf.fr) | France | patrimoine numérisé | `UNAVAILABLE` | — | selon document | manual_link | HTTP 403 (SRU) depuis ce poste |
| [Deutsche Nationalbibliothek](https://services.dnb.de/sru) | Allemagne | catalogue de livres | `PUBLIC_FREE` | aucune | non (catalogue) | api | OK (SRU) |
| [Deutsche Digitale Bibliothek](https://www.deutsche-digitale-bibliothek.de) | Allemagne | patrimoine numérisé | `FREE_API_KEY` | clé gratuite sur inscription | selon document | manual_link | non intégré |
| [Europeana](https://api.europeana.eu) | Europe | patrimoine culturel | `FREE_API_KEY` | clé personnelle gratuite (la clé de démonstration n'est pas destinée à l'usage réel) | selon licence | api | format vérifié ; inactif sans clé |
| [DART-Europe](https://www.dart-europe.org) | Europe | thèses européennes | `UNAVAILABLE` | pas d'API | liens | manual_link | pages web uniquement |
| [Google Books](https://www.googleapis.com/books) | international | livres (métadonnées) | `FREE_API_KEY` | clé gratuite | non | api | OK (clé configurée) |
| [Open Library](https://openlibrary.org) | international | livres | `PUBLIC_FREE` | aucune | prêt / domaine public | api | OK |
| [Internet Archive](https://archive.org) | international | livres numérisés | `PUBLIC_FREE` | aucune | seulement licence libre déclarée | api | OK |
| [J-STAGE (JST)](https://api.jstage.jst.go.jp/searchapi/do) | Japon | revues scientifiques japonaises | `PUBLIC_FREE` | aucune | lecture sur le site (licence selon la revue) | api | OK : API de recherche publique (Atom) |
| [NDL Search (Bibliothèque nationale de la Diète)](https://ndlsearch.ndl.go.jp/api/opensearch) | Japon | livres, articles, thèses japonais | `PUBLIC_FREE` | aucune | notices (document selon la bibliothèque) | api | OK : OpenSearch autorisé par robots.txt |
| [CiNii Research (NII)](https://cir.nii.ac.jp) | Japon | articles, livres, thèses japonais | `UNAVAILABLE` | — | — | manual_link | recherche interdite aux robots (robots.txt) ; ses notices passent par NDL Search |
| [OSTI.GOV (DOE)](https://www.osti.gov/api/v1) | États-Unis | rapports techniques, articles, données (énergie, sciences) | `PUBLIC_FREE` | aucune | souvent sur le site (droits selon le document) | api | OK : API publique autorisée par robots.txt |
| [Library of Congress](https://www.loc.gov) | États-Unis | catalogue, collections numérisées | `UNAVAILABLE` | — | — | manual_link | HTTP 403 au client automatisé (non contourné) |
| [DPLA](https://dp.la) | États-Unis | collections patrimoniales | `FREE_API_KEY` | clé personnelle obligatoire | selon institution | manual_link | HTTP 403 sans clé ; non intégré |
| [Érudit](https://www.erudit.org) | Canada | revues savantes francophones | `PUBLIC_FREE` | aucune (via Crossref) | libre ou différé selon la revue | api | OK : recherche Crossref, préfixe DOI 10.7202 |
| [African Journals Online (AJOL)](https://www.ajol.info) | Afrique | ≈ 500 revues africaines | `PUBLIC_FREE` | aucune (via Crossref) | selon la revue (aucun PDF téléchargé : demande du site) | api | OK : recherche Crossref, préfixe DOI 10.4314 |
| [SciELO (Brésil, Chili, Afrique du Sud)](https://scielo.org) | Amérique latine / Afrique | revues en libre accès | `PUBLIC_FREE` | aucune (via Crossref) | oui (CC selon la revue) | api | OK : recherche Crossref, préfixes 10.1590, 10.4067, 10.17159 |
| [Redalyc](https://www.redalyc.org) | Amérique latine | revues en libre accès | `UNAVAILABLE` | — | sur le site | manual_link | OAI-PMH sans résultat ; revues souvent présentes dans DOAJ et OpenAlex |
| [Trove (Bibliothèque nationale d'Australie)](https://trove.nla.gov.au) | Australie | livres, journaux, revues australiens | `FREE_API_KEY` | clé personnelle obligatoire (HTTP 401 sans clé) | selon document | manual_link | non intégré (pas de clé) |
| [Research Data Australia](https://researchdata.edu.au) | Australie | jeux de données de recherche | `UNAVAILABLE` | — | — | manual_link | API sous /registry/, interdite aux robots (robots.txt) |
| [eLIBRARY.RU / РИНЦ](https://elibrary.ru) | Russie | articles russes | `UNAVAILABLE` | pas d'API publique | selon revue | manual_link | lien de recherche (via Яндекс) ; aucune extraction |
| [КиберЛенинка](https://cyberleninka.ru/oai) | Russie | articles en libre accès (≈ 4 000 revues) | `PUBLIC_FREE` | aucune (OAI-PMH officiel) | sur le site (PDF interdits aux robots) | api | OK : OAI-PMH autorisé par robots.txt ; moissonnage par revue + index local |
| [РГБ (dont Электронная библиотека диссертаций)](https://search.rsl.ru) | Russie | catalogue, thèses | `UNAVAILABLE` | pas d'API publique | consultation sur place / payante pour certaines thèses | manual_link | lien de recherche |
| [РНБ](https://nlr.ru) | Russie | catalogue | `UNAVAILABLE` | pas d'API publique | — | manual_link | non intégré |
| [НЭБ](https://rusneb.ru) | Russie | bibliothèque numérique | `UNVERIFIED_EXCLUDED` | API sur demande (conditions non vérifiées) | selon document | manual_link | non intégré |
| [ГПНТБ России](https://www.gpntb.ru) | Russie | catalogue scientifique et technique | `UNAVAILABLE` | pas d'API publique | — | manual_link | non intégré |
| [ВИНИТИ РАН](http://www.viniti.ru) | Russie | bases d'analyses scientifiques | `PAID_EXCLUDED` | accès sur abonnement | — | excluded | non intégré |
| [Федеральная электронная медицинская библиотека](https://femb.ru) | Russie | médecine | `UNAVAILABLE` | pas d'API publique | selon document | manual_link | non intégré |
