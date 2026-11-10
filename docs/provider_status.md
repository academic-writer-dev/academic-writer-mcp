<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Statut des fournisseurs documentaires

Vérification réelle le 2026-11-10 depuis le poste de l'utilisateur (mode connecté). Répartition : FREE_ACCOUNT : 1, FREE_API_KEY : 6, PAID_EXCLUDED : 1, PUBLIC_FREE : 18, UNAVAILABLE : 10, UNVERIFIED_EXCLUDED : 3.

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
| [eLIBRARY.RU / РИНЦ](https://elibrary.ru) | Russie | articles russes | `UNAVAILABLE` | pas d'API publique | selon revue | manual_link | lien de recherche (via Яндекс) ; aucune extraction |
| [КиберЛенинка](https://cyberleninka.ru) | Russie | articles en libre accès | `UNVERIFIED_EXCLUDED` | pas d'API officielle documentée | oui (CC BY) sur le site | manual_link | lien de recherche ; aucune extraction |
| [РГБ (dont Электронная библиотека диссертаций)](https://search.rsl.ru) | Russie | catalogue, thèses | `UNAVAILABLE` | pas d'API publique | consultation sur place / payante pour certaines thèses | manual_link | lien de recherche |
| [РНБ](https://nlr.ru) | Russie | catalogue | `UNAVAILABLE` | pas d'API publique | — | manual_link | non intégré |
| [НЭБ](https://rusneb.ru) | Russie | bibliothèque numérique | `UNVERIFIED_EXCLUDED` | API sur demande (conditions non vérifiées) | selon document | manual_link | non intégré |
| [ГПНТБ России](https://www.gpntb.ru) | Russie | catalogue scientifique et technique | `UNAVAILABLE` | pas d'API publique | — | manual_link | non intégré |
| [ВИНИТИ РАН](http://www.viniti.ru) | Russie | bases d'analyses scientifiques | `PAID_EXCLUDED` | accès sur abonnement | — | excluded | non intégré |
| [Федеральная электронная медицинская библиотека](https://femb.ru) | Russie | médecine | `UNAVAILABLE` | pas d'API publique | selon document | manual_link | non intégré |
