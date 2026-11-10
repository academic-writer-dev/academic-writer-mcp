# Intégration des bibliothèques scientifiques

Statut détaillé de chaque fournisseur : [provider_status.md](provider_status.md) ; vérification réelle :
[access_verification_report.md](access_verification_report.md) ; exclusions : [excluded_paid_providers.md](excluded_paid_providers.md).

## Outils

| Outil | Rôle | Bases |
|---|---|---|
| `find_works_by_topic` | Recherche par thème ; filtres auteur, années, type ; `services` pour restreindre | Internet Archive, Open Library, DOAJ, arXiv, Crossref, OpenAlex, Semantic Scholar, Europe PMC, PubMed, HAL, Zenodo, OpenAIRE, ERIC, DNB, CORE (clé), DataCite (données) |
| `search_sources` | Fiche d'un ouvrage précis (titre, ISBN) | Google Books (clé), OpenAlex, Crossref |
| `verify_source_metadata` | Vérifie auteurs, titre, année, DOI d'une source enregistrée | Crossref, Open Library, Google Books |
| `check_retractions` | Rétractations, retraits, corrections, avis d'inquiétude | Crossref (updates) ; OpenAlex marque `[RÉTRACTÉ]` |
| `download_open_access` | Télécharge un texte intégral en libre accès LÉGAL (licence revérifiée) | arXiv, Internet Archive (licence libre), DOAJ, HAL, Europe PMC (OA), Zenodo, Semantic Scholar, CORE, Unpaywall |
| `find_researcher` | Identifiants ORCID | ORCID |
| `fetch_open_data` | Séries statistiques officielles | World Bank, Eurostat |
| `list_source_providers` | Registre des 40 fournisseurs et statuts | — |

## Règles

- Métadonnées gratuites ≠ texte intégral gratuit : `open_access` n'est vrai qu'avec une licence libre attestée
  ou un dépôt en archive ouverte ; « lecture gratuite » sans licence est signalée comme telle.
- Aucun scraping : les sources russes (eLIBRARY, КиберЛенинка, РГБ, НЭБ…) n'ont pas d'API autorisant
  l'automatisation et sont proposées en liens manuels (`confirm_source_verification` pour noter la vérification).
- Mode connecté requis ; seuls les termes de recherche ou les identifiants (DOI, ISBN) sont envoyés.
- Aucune référence inventée : chaque fiche vient d'un catalogue et doit être confirmée par l'utilisateur.
