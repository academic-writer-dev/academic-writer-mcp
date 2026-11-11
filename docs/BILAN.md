# Bilan général — Academic Writer MCP

Date du contrôle : 2026-11-10. Version 1.2.0 (et ajouts non publiés, voir [CHANGELOG](../CHANGELOG.md)).

## 1. Bibliothèques connectées et opérationnelles : 32

Test réel depuis le poste (mode connecté), 9 thèmes de domaines et de langues variés : mécanique (gear fatigue),
médecine (diabetes treatment), droit (labour law dismissal), histoire (french revolution), informatique (neural
networks), économie (inflation monetary policy), agronomie (soil erosion), français (énergie éolienne), russe
(зубчатые колеса). « Thèmes » = nombre de thèmes pour lesquels la base a fourni des références pertinentes.

### Recherche par thème (`find_works_by_topic`) : 27 bases

| Base | Région | Thèmes | Références | Rôle |
|---|---|---|---|---|
| OpenAlex | international | 9/9 | 38 | catalogue mondial (250 millions de travaux) |
| DOAJ | international | 9/9 | 33 | revues en libre accès |
| Zenodo | international | 9/9 | 37 | publications et données |
| OpenAIRE | Europe | 8/9 | 39 | publications européennes |
| Crossref | international | 8/9 | 34 | métadonnées DOI, rétractations |
| HAL | France | 8/9 | 33 | archive ouverte française |
| Open Library | international | 8/9 | 33 | livres |
| Érudit | Canada | 8/9 | 38 | revues francophones |
| Internet Archive | international | 7/9 | 35 | livres et manuels numérisés |
| arXiv | international | 7/9 | 33 | prépublications (sciences, ingénierie) |
| ERIC | États-Unis | 7/9 | 29 | éducation |
| DNB | Allemagne | 7/9 | 26 | Bibliothèque nationale allemande |
| AJOL | Afrique | 7/9 | 31 | revues africaines |
| SciELO | Amérique latine, Afrique du Sud | 7/9 | 29 | revues en libre accès |
| Europe PMC | Europe | 6/9 | 29 | biomédecine |
| J-STAGE | Japon | 6/9 | 24 | revues japonaises (dont JSME, mécanique) |
| NDL Search | Japon | 6/9 | 12 | Bibliothèque nationale du Japon |
| КиберЛенинка | Russie | 5/9 | 14 | 18 revues russes de génie mécanique (10 800 articles en index local) |
| PubMed | États-Unis | 4/9 | 9 | médecine (spécialisée : normal qu'elle ne couvre pas tout) |
| NASA NTRS | États-Unis | 4/9 | 16 | rapports techniques (ingénierie) |
| OSTI.GOV | États-Unis | 3/9 | 6 | rapports techniques (énergie, sciences) |
| DataCite | international | 3/3 (jeux de données) | 14 | jeux de données de recherche |

Ajoutées le 2026-11-11 (livres, manuels, méthodiques d'universités ; tests réels) :

| Base | Région | Test | Rôle |
|---|---|---|---|
| БНТУ (Université technique nationale de Biélorussie) | Biélorussie (en russe) | 716 documents « зубчатые колеса » ; 202 « курсовой проект детали машин » | manuels, méthodiques, articles d'ingénierie mécanique |
| ТГУ Тольятти | Russie | 155 documents « теория механизмов и машин » ; 296 guides d'oformlenie de ВКР | manuels de Детали машин, ТММ, guides |
| УрФУ (Université fédérale de l'Oural) | Russie | 1 706 documents « зубчатые колеса » | manuels, méthodiques, guides de ВКР |
| La Referencia | Amérique latine | 120 documents « mecanismos engranajes » (1,4 s) | dépôts universitaires (es, pt) |
| Open Textbook Library | États-Unis | 422 manuels ouverts indexés (dont 22 de génie mécanique) | manuels universitaires sous licence ouverte : ingénierie, physique, mathématiques, rédaction |

Les dépôts russophones ne sont interrogés que pour une recherche écrite en cyrillique.

### Guides de rédaction (`find_writing_guides`)

Guides, méthodiques et manuels réels pour rédiger un compte rendu de TP, un TD, un mémoire (licence, master,
thèse), un rapport ou un projet de cours, en français, russe et anglais. Test : mémoire en russe → « Требования к
структуре и оформлению выпускной квалификационной работы » (УрФУ), instructions du БНТУ ; projet en russe →
« Детали машин : курсовое проектирование » (БНТУ) ; mémoire en français → méthodologies de rédaction du mémoire ;
TP en anglais → guides « How to write a lab report ».

Chaque thème testé a obtenu des références de nombreuses bases : la couverture d'ensemble est assurée dans tous
les domaines testés. Une base spécialisée (PubMed, NASA, OSTI) ne couvre normalement que son domaine.

### Services de données et de vérification : 5

| Service | Test | Rôle |
|---|---|---|
| ORCID | OK (0,8 s) | identifiants des chercheurs |
| Banque mondiale | OK (0,7 s) | statistiques officielles |
| Eurostat | OK (0,7 s) | statistiques européennes |
| NIST CODATA | OK (copie locale) | 355 constantes physiques officielles |
| Google Books | OK (0,8 s, clé configurée) | fiches de livres |

Bilan détaillé par base : [provider_status.md](provider_status.md).

## 2. Services déconnectés et retirés du système

Retirés car non opérationnels (code, outils, clés et registre supprimés) : **Semantic Scholar** (refus 9/9, quota
public saturé), **CORE** et **Europeana** (clé gratuite jamais obtenue), **Unpaywall** (adresse non configurée).
Retirés aussi du registre : les 22 bases qui n'étaient que des liens manuels ou exclues (accès automatisé interdit,
refusé ou payant). Raisons : [excluded_paid_providers.md](excluded_paid_providers.md).

## 3. Sécurité

| Contrôle | Résultat |
|---|---|
| Failles connues des 235 bibliothèques Python utilisées (pip-audit, base PyPA) | **aucune** |
| Clés API dans les journaux, les données ou l'historique GitHub | **aucune trace** |
| Clés API | coffre Windows (Gestionnaire d'identification), jamais dans les fichiers |
| Réseau | **renforcé** : HTTPS obligatoire, certificats vérifiés, redirections vers une adresse non chiffrée refusées, réponses limitées à 25 Mo, User-Agent honnête, robots.txt respecté |
| Documents importés | copie protégée (SHA-256), dossiers autorisés seulement, contenu traité comme donnée (injections signalées) |
| Code | aucun `eval` / `exec`, aucun shell, calculs filtrés par liste blanche |
| Logiciels du poste | lancement seulement si autorisé dans la configuration ET confirmé à chaque fois |

Détails : [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).

## 4. État technique

- Tests automatiques : suite complète réussie (voir le dernier rapport de `pytest`).
- Démarrage du serveur : environ 2,5 s ; 115 outils MCP.
- Utilisation : [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md). Installation sur un autre ordinateur :
  [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md).
