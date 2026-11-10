# Rapport de tests — version 1.2.0 (2026-11-10)

**Suite automatique : 424 réussis, 1 ignoré** (test LanguageTool réel, désactivé par défaut), 26 fichiers de tests,
durée ≈ 3 min, Windows 11, Python 3.12.15. Démarrage réel du serveur (stdio, `initialize` + `list_tools`) : 2,0 à
2,4 s pour 107 outils.

## Campagne des 25 scénarios (§ 23) — `tests/test_scenarios.py` : 25 / 25 réussis

| # | Scénario | Vérification | Résultat |
|---|---|---|---|
| 1 | TD de mathématiques | consignes analysées ; dérivée et ∫ e^(−x²) = √π vérifiées | VALIDÉ |
| 2 | Exercice de mécanique | démarche 11 étapes ; v = 7,592 m/s vérifiée par réinjection | VALIDÉ |
| 3 | TP de science des matériaux | régression refusée sur 2 points ; R² > 0,99 sur 6 points ; script conservé | VALIDÉ |
| 4 | Rapport de chimie | calcul écrit c = m/V recalculé sans écart | VALIDÉ |
| 5 | Devoir de biologie | test t (p < 0,01) contrôlé par Mann-Whitney ; marqué « estimé » | VALIDÉ |
| 6 | Analyse statistique en économie | corrélation et ajustement linéaire | VALIDÉ |
| 7 | Document de droit | profil haut risque, avertissement « pas un conseil juridique » | VALIDÉ |
| 8 | Rapport informatique | discipline détectée sur le document | VALIDÉ |
| 9 | Projet d'automatisation | TIA Portal détecté, règles de sécurité, traitement refusé | VALIDÉ |
| 10 | Maintenance minière | profil principal + secondaire (engins) dans le dossier du rédacteur | VALIDÉ |
| 11 | Mémoire de Licence | plan, section acceptée, export DOCX, sections non rédigées signalées | VALIDÉ |
| 12 | Mémoire de Master | audit final : calcul faux (120/8 ≠ 16) détecté | VALIDÉ |
| 13 | Travail doctoral | structure avec état de l'art ; passage recopié sans citation détecté | VALIDÉ |
| 14 | Article scientifique | bibliographie en 6 styles | VALIDÉ |
| 15-17 | Documents FR / RU / EN | 2 questions extraites dans chaque langue | VALIDÉ |
| 18 | PDF avec tableaux | tableau extrait et exporté en CSV | VALIDÉ |
| 19 | Document scanné | OCR réel (Tesseract) avec confiance par page | VALIDÉ |
| 20 | Travail fondé sur le cours | consigne détectée → course_only ; question non traitée signalée | VALIDÉ |
| 21 | Présentation depuis un sujet | plan + avertissement « informations vérifiables » | VALIDÉ |
| 22 | Présentation depuis un mémoire | matière chiffrée reprise du document | VALIDÉ |
| 23 | Présentation scientifique avec graphique | image du graphique insérée | VALIDÉ |
| 24 | Présentation technique avec schémas | démarche, comparaison, chiffres clés ; aucun chevauchement | VALIDÉ |
| 25 | Export PPTX et PDF | PPTX, PDF, ODP et aperçus produits par PowerPoint | VALIDÉ |

## Essais réels hors suite automatique (mode connecté, 2026-11-10)

| Domaine | Résultat |
|---|---|
| Recherche internationale | OpenAlex (avec clé), Crossref, DOAJ, arXiv, Zenodo, OpenAIRE, ERIC, Europe PMC, PubMed, HAL, DNB, DataCite : réponses correctes |
| Recherche russe | Crossref : articles russes avec DOI trouvés ; bases russes : liens manuels (pas d'API) |
| DOI et rétractations | article Wakefield (Lancet 1998) signalé RÉTRACTÉ |
| Texte intégral légal | PDF HAL (CC BY 4.0) téléchargé, importé et lu ; PDF Europe PMC (OA) résolu |
| Données ouvertes | PIB de la France (World Bank, Eurostat) |
| Quotas gratuits | OpenAlex : budget partagé sans clé, quota personnel avec clé gratuite ; Semantic Scholar : HTTP 429 sans clé (signalé, sans blocage) |
| Refus des services payants | fournisseurs d'IA payants désactivés par défaut ; VINITI exclu (abonnement) ; BASE exclu (refus IP) |
| Logiciels détectés | SolidWorks 2025, Inventor 2027, TIA Portal V18, T-FLEX CAD 17, Office 2019, Python, Tesseract |
| Échanges de fichiers | script Python exécuté (CSV + image) ; classeur recalculé par Excel 2019 |
| Présentations | aperçus inspectés visuellement (styles académique, industriel, futuriste) ; défauts corrigés |

## Non testé

- LanguageTool réel (test désactivé par défaut : serveur Java lourd ; testé manuellement en phase 5).
- Octave, R, Scilab, CalculiX, Maxima : non installés sur ce poste (lancement prévu, non exécuté).
- LibreOffice Impress : non installé (conversion faite par PowerPoint).
- CORE, Unpaywall, Europeana : pas de clé ou d'adresse configurée.
