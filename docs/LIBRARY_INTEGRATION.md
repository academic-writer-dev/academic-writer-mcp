# Intégration des bibliothèques scientifiques

Statut détaillé de chaque fournisseur : [provider_status.md](provider_status.md) ; vérification réelle :
[access_verification_report.md](access_verification_report.md) ; exclusions : [excluded_paid_providers.md](excluded_paid_providers.md).

## Outils

| Outil | Rôle | Bases |
|---|---|---|
| `find_works_by_topic` | Recherche par thème ; filtres auteur, années, type ; `services` pour restreindre | Internet Archive, Open Library, DOAJ, arXiv, Crossref, OpenAlex, Europe PMC, PubMed, HAL, Zenodo, OpenAIRE, ERIC, DNB, DataCite (données) ; J-STAGE et NDL Search (Japon), OSTI.GOV (États-Unis), Érudit (Canada), AJOL (Afrique), SciELO (Brésil, Chili, Afrique du Sud), La Referencia (Amérique latine), Open Textbook Library (manuels ouverts) ; en cyrillique : БНТУ, ТГУ Тольятти, УрФУ |
| `search_sources` | Fiche d'un ouvrage précis (titre, ISBN) | Google Books (clé), OpenAlex, Crossref |
| `verify_source_metadata` | Vérifie auteurs, titre, année, DOI d'une source enregistrée | Crossref, Open Library, Google Books |
| `check_retractions` | Rétractations, retraits, corrections, avis d'inquiétude | Crossref (updates) ; OpenAlex marque `[RÉTRACTÉ]` |
| `download_open_access` | Télécharge un texte intégral en libre accès LÉGAL (licence revérifiée) | arXiv, Internet Archive (licence libre), DOAJ, HAL, Europe PMC (OA), Zenodo |
| `find_researcher` | Identifiants ORCID | ORCID |
| `fetch_open_data` | Séries statistiques officielles | World Bank, Eurostat |
| `lookup_constant` | Constantes physiques fondamentales (copie locale hors connexion) | NIST — CODATA 2022 |
| `cyberleninka_harvest_discipline` | Moissonne les 18 revues russes de génie mécanique (OAI-PMH officiel) | КиберЛенинка |
| `cyberleninka_journals`, `cyberleninka_harvest` | Revues russes en libre accès : moissonnage OAI-PMH officiel, index local, recherche via `find_works_by_topic` | КиберЛенинка |
| `find_writing_guides` | Guides et méthodiques pour rédiger un TP, un TD, un mémoire, un rapport, un projet | УрФУ, БНТУ, ТГУ Тольятти, Open Textbook Library, OpenAlex, DOAJ, Open Library, Internet Archive, HAL, La Referencia |
| `update_open_textbooks` | Met à jour l'index local des manuels ouverts (par matière, ≈ 2 minutes, une fois par mois) | Open Textbook Library |
| `list_source_providers` | Registre des 32 bibliothèques connectées et statuts | — |

## Reconnaissance automatique du domaine

Sans paramètre `discipline`, `find_works_by_topic` reconnaît le domaine : celui du projet (`project_id`), sinon
le vocabulaire de la recherche (40 profils, fr / ru / en). Les sources spécialisées du domaine sont AJOUTÉES
(aucune base retirée) et leurs résultats classés en premier, à pertinence égale :

- génie mécanique (programme principal, prioritaire en cas de quasi-égalité) : tout le dispositif ci-dessous ;
- autres domaines : OpenAlex filtré sur le champ ou le sous-domaine correspondant (médecine, droit, informatique,
  génie civil, histoire, économie…).

`discipline="aucune"` : recherche générale sans spécialisation.

## Recherche spécialisée génie mécanique

Mode STRICT `find_works_by_topic(..., discipline="genie_mecanique")` (aussi `fabrication_mecanique`, `materiaux_metallurgie`,
`automobile_engins`, `maintenance_industrielle`) :

| Source | Filtre |
|---|---|
| OpenAlex | sous-domaines Mechanical Engineering, Mechanics of Materials, Industrial and Manufacturing, Automotive, Aerospace, Computational Mechanics |
| DOAJ | revues classées LCC TJ (machines), TL (véhicules, aéronautique), TS (fabrication), TA349-359 (mécanique appliquée), TA401-492 (matériaux, RDM) |
| J-STAGE | revues JSME : Mechanical Engineering Journal, Journal of Advanced Mechanical Design, Systems, and Manufacturing, Transactions of the JSME |
| NASA NTRS | rapports techniques NASA (API publique) |
| Revues d'universités russes (OpenAlex) | Вестник МГТУ «Станкин», СТИН, RUDN Journal of Engineering Research, Вестник РУДН, Записки Горного института, Горные науки и технологии, Известия вузов. Машиностроение, Технология машиностроения |
| КиберЛенинка | 20 revues russes (МГТУ им. Баумана « Машиностроение », Известия вузов. Машиностроение, Обработка металлов, Динамика систем, механизмов и машин…), après moissonnage |
| autres | Crossref, arXiv, HAL, Zenodo, OpenAIRE, OSTI, SciELO, AJOL, Érudit, Internet Archive, Open Library, DNB |

Retirées dans ce mode : PubMed, Europe PMC, ERIC (hors sujet), NDL (lente). engrXiv : API interdite aux robots.

## Règles

- Métadonnées gratuites ≠ texte intégral gratuit : `open_access` n'est vrai qu'avec une licence libre attestée
  ou un dépôt en archive ouverte ; « lecture gratuite » sans licence est signalée comme telle.
- Sources russes :
  - КиберЛенинка : interface OFFICIELLE OAI-PMH (autorisée par robots.txt) → métadonnées moissonnées revue par revue ;
    PDF interdits aux robots → jamais téléchargés, lecture par le lien ;
  - articles russes indexés par OpenAlex (`language=ru`) et Crossref (nombreuses revues russes avec DOI) ;
  - eLIBRARY, РГБ, НЭБ, РНБ, ГПНТБ : pas d'API publique autorisant l'automatisation → liens manuels
    (`confirm_source_verification` pour noter la vérification) ; РГБ, НЭБ et dépôts universitaires (УрФУ)
    n'acceptaient pas la connexion depuis l'adresse IP du poste le 2026-11-10 (délai dépassé).
- Asie, Amériques, Afrique, Océanie (vérifié le 2026-11-10) :
  - J-STAGE (API publique), NDL Search (OpenSearch autorisé par robots.txt), OSTI.GOV (API publique) ;
  - Érudit, AJOL, SciELO : recherche par l'API Crossref restreinte à leurs préfixes DOI (10.7202 ; 10.4314 ;
    10.1590, 10.4067, 10.17159) — aucune requête vers leurs sites, aucun PDF téléchargé ;
  - écartés : CiNii Research et Research Data Australia (recherche interdite aux robots), Library of Congress
    (HTTP 403), DPLA et Trove (clé personnelle obligatoire), Redalyc (OAI vide ; revues présentes dans DOAJ).
- Aucun scraping ni contournement de protection.
- Mode connecté requis ; seuls les termes de recherche ou les identifiants (DOI, ISBN) sont envoyés.
- Aucune référence inventée : chaque fiche vient d'un catalogue et doit être confirmée par l'utilisateur.
