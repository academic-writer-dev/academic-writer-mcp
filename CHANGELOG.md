# Journal des versions

## Non publié

- Bilan général (docs/BILAN.md) : 27 bibliothèques et services testés en réel sur 9 thèmes ; services non
  opérationnels retirés (Semantic Scholar, CORE, Europeana — outil search_heritage —, Unpaywall) ; registre réduit
  aux bases connectées ; liens manuels РГБ retirés.
- Sécurité renforcée : HTTPS obligatoire, redirections non chiffrées refusées, réponses limitées à 25 Mo ; audit des
  dépendances (aucune faille connue) et des secrets (aucune fuite).
- Guide d'utilisation et procédure d'installation sur un autre ordinateur.

- Consignes de l'enseignant appliquées automatiquement : mise en forme (police, taille, interligne, marges,
  retrait, alignement, pagination), style des références, format de remise, plan imposé ; priorité consignes >
  profil de l'enseignant > gabarit.
- Contrôle des normes internationales (`check_academic_norms`, inclus dans l'audit final) : ISO 7144, Z39.18,
  ISO 214, ISO 2145, ISO 80000-1, ISO 8601, figures / tableaux, sigles, longueur demandée.
- Dossier de recherche à partir d'un thème (`build_research_dossier`) : sources réelles, consignes, plan, normes,
  fichier Word.

- Reconnaissance automatique du domaine de chaque recherche (projet ou vocabulaire, 40 disciplines) : sources
  spécialisées ajoutées sans retirer de base, classées en premier ; priorité au génie mécanique.

- Recherche spécialisée génie mécanique (`discipline`) : OpenAlex et DOAJ filtrés, revues JSME, NASA NTRS,
  18 revues russes de machinostroenie (outil `cyberleninka_harvest_discipline`) ; bases hors sujet retirées.

- Bibliothèques gratuites du monde ajoutées à `find_works_by_topic` : J-STAGE et NDL Search (Japon), OSTI.GOV
  (États-Unis), Érudit (Canada), AJOL (Afrique), SciELO (Brésil, Chili, Afrique du Sud) ; registre porté à
  51 fournisseurs (CiNii, Research Data Australia, Library of Congress, DPLA, Trove, Redalyc vérifiés et écartés,
  avec la raison).
- КиберЛенинка (OAI-PMH officiel), constantes CODATA (NIST), Europeana (clé), articles russes via OpenAlex.

## 1.2.0 — 2026-11-10 — Assistant académique universel

- Profils d'enseignants structurés (définitions, structure attendue, style, règles, barème) ; extraction du barème
  et des définitions depuis les documents de l'enseignant.
- OCR avec indice de confiance par page et par image ; comparaison de deux documents.
- Similarité avec les documents du projet et citations manquantes ; exports Markdown, texte, XLSX, CSV.
- Bases ouvertes : OpenAlex (clé gratuite), OpenAIRE, ERIC, DNB ; filtres auteur / années / type ; rétractations
  (Crossref) ; ORCID ; données World Bank et Eurostat ; registre de 40 fournisseurs avec statut de gratuité.
- Calcul numérique SciPy (avec contrôle indépendant) ; démarche de résolution en 11 étapes ; script de
  régénération de chaque graphique.
- 40 disciplines (automobile / engins, génie électrique, IA / données, matériaux, sociologie) ; projets
  interdisciplinaires ; 30 types de travaux ; catalogue et contrôle des normes citées.
- Traitements dans les logiciels du poste (Python, Excel, Octave, R, Scilab, CalculiX, Maxima) avec verrous.
- Présentations : 10 styles, sommaire, comparaison, définitions, chronologie, questions du jury, contrôle des
  chevauchements ; contraste WCAG vérifié.
- Démarrage du serveur 4 fois plus rapide (≈ 2 s).
- Documentation : architecture, configuration, clés, bibliothèques, logiciels, disciplines, enseignants,
  calcul, présentations, sécurité, limites, rapport de tests ; catalogues générés depuis le code.
- 107 outils MCP ; 424 tests ; campagne des 25 scénarios réussie.

## 1.1.0 — 2026-11-10 — Corrections de l'audit général

Présentations (PPTX, PDF, aperçus), graphiques, calcul formel SymPy, consigne « uniquement le cours » et
politique de sources, 35 disciplines, 13 bases ouvertes, détection des logiciels, mode connecté vérifié.

## 1.0.0 — 2026-11-09 — Maintenance

Diagnostic, sauvegarde et restauration, déclaration dans Claude Desktop, parcours guidés.

## 0.1.0 à 0.9.0 — 2026-11-08 / 09 — Phases 1 à 9

Serveur MCP, projets et import sécurisé, lecture et OCR, profils disciplinaires, rédaction encadrée, sources et
bibliographie, audit documentaire et indices d'IA, contrôle qualité, mise en forme et export DOCX / PDF.
