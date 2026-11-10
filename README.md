# Academic Writer MCP

Serveur [Model Context Protocol](https://modelcontextprotocol.io) local destiné à analyser,
structurer, vérifier et mettre en forme des documents académiques, scientifiques,
techniques et professionnels (FR / RU / EN).

> **Statut : version 1.2.0 — assistant académique universel** — 114 outils MCP, 40 disciplines, 30 types de
> travaux, profils d'enseignants (« uniquement le cours »), 24 bases de recherche gratuites vérifiées, recherche spécialisée
> génie mécanique (Europe, Russie,
> Asie, Amériques, Afrique), calcul
> formel (SymPy) et numérique (SciPy) contrôlés, graphiques reproductibles, présentations professionnelles
> (10 styles, PPTX / PDF / ODP, aperçus), traitements dans les logiciels du poste, normes, similarité.
> 424 tests ; campagne des 25 scénarios réussie ([rapport](docs/TEST_REPORT.md)). Historique : [CHANGELOG.md](CHANGELOG.md).

## Documentation

| Sujet | Document |
|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Installation (Windows) | [docs/INSTALLATION_WINDOWS.md](docs/INSTALLATION_WINDOWS.md) |
| Configuration | [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |
| Clés d'API gratuites | [docs/API_SETUP.md](docs/API_SETUP.md) |
| Bibliothèques scientifiques | [docs/LIBRARY_INTEGRATION.md](docs/LIBRARY_INTEGRATION.md), [statut des fournisseurs](docs/provider_status.md), [vérification des accès](docs/access_verification_report.md), [exclusions](docs/excluded_paid_providers.md) |
| Licences | [docs/approved_free_libraries.md](docs/approved_free_libraries.md) |
| Logiciels | [docs/SOFTWARE_INTEROPERABILITY.md](docs/SOFTWARE_INTEROPERABILITY.md), [catalogue](docs/SOFTWARE_CATALOG.md) |
| Disciplines | [docs/DOMAIN_COVERAGE.md](docs/DOMAIN_COVERAGE.md), [profils](docs/profils-disciplinaires.md) |
| Enseignants et consignes | [docs/PROFESSOR_PROFILES.md](docs/PROFESSOR_PROFILES.md) |
| Calcul | [docs/CALCULATION_MODULE.md](docs/CALCULATION_MODULE.md) |
| Présentations | [docs/PRESENTATION_MODULE.md](docs/PRESENTATION_MODULE.md) |
| Sécurité | [docs/SECURITY_AND_PRIVACY.md](docs/SECURITY_AND_PRIVACY.md) |
| Limites | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| Tests | [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| Décisions techniques | [docs/decisions.md](docs/decisions.md) |

Les catalogues (logiciels, fournisseurs, licences, disciplines) sont générés depuis le code :
`uv run python scripts/generate_docs.py`.

## Principes

- Traitement **local par défaut** ; aucun envoi externe sans consentement explicite.
- **Moteur de rédaction universel** (`writing_engine = auto`) : fournisseur cloud seulement en mode
  connecté + clé + consentement du projet ; sinon modèle local Ollama (aucun envoi) ; sinon l'assistant
  MCP rédige à partir du dossier préparé par le serveur.
- Chaque texte produit est une **révision proposée** avec contrôles automatiques (chiffres et noms
  absents des sources, bibliographie inventée, fidélité) ; l'utilisateur accepte ou refuse.
- L'**original n'est jamais modifié** : copie vérifiée (SHA-256) en lecture seule.
- Aucune donnée, citation ou référence inventée ; toute incertitude est signalée.

## Outils MCP disponibles

| Catégorie | Outils |
|---|---|
| Diagnostic et maintenance | `ping`, `system_check`, `create_backup`, `list_backups` |
| Projets | `create_project`, `get_project`, `list_projects`, `update_project`, `archive_project` |
| Documents | `import_document`, `list_documents`, `get_document_metadata` |
| Extraction et recherche | `extract_document_content`, `extract_document_tables`, `export_tables`, `extract_document_images`, `search_in_documents` |
| IA et moteurs | `get_ai_status`, `set_project_ai_consent`, `test_ai_provider`, `get_writing_engine` |
| Rédaction | `analyze_assignment`, `extract_requirements`, `manage_requirement`, `create_academic_outline`, `get_academic_outline`, `edit_academic_outline`, `validate_outline`, `write_academic_section`, `rewrite_academic_section`, `get_section_brief`, `save_section_draft`, `get_section_revision`, `review_revision`, `get_draft_status` |
| Correction et traduction | `check_language`, `correct_academic_section`, `improve_academic_style`, `translate_academic_section`, `manage_languagetool` |
| Sources et bibliographie | `register_source`, `list_sources`, `update_source`, `verify_source_metadata`, `insert_citation`, `generate_bibliography`, `audit_references`, `find_uncited_references` |
| Recherche d'ouvrages | `find_works_by_topic`, `download_open_access`, `export_references`, `search_sources`, `import_sources_file`, `confirm_source_verification`, `check_retractions`, `find_researcher`, `fetch_open_data`, `lookup_constant`, `search_heritage`, `list_source_providers` |
| Audit et indices IA | `detect_ai_indicators`, `analyze_writing_patterns`, `analyze_document_metadata`, `inspect_revision_history`, `inspect_document_provenance`, `verify_content_credentials`, `audit_document_integrity`, `generate_ai_audit_report` |
| Calcul | `solve_math` (formel, SymPy), `solve_numeric` (numérique, SciPy), `solve_problem` (démarche en 11 étapes) — résultats vérifiés |
| Graphiques | `create_chart`, `list_charts` |
| Présentations | `plan_presentation`, `create_presentation` |
| Cours et enseignants | `create_teacher_profile`, `list_teacher_profiles`, `update_teacher_profile`, `set_project_teaching`, `check_course_coverage`, `extract_course_notations`, `extract_teacher_material` |
| Logiciels du poste | `detect_software`, `list_software_engines`, `prepare_software_job`, `run_software_job` |
| Contrôle qualité | `validate_calculations`, `evaluate_formula`, `convert_units`, `verify_factual_claims`, `check_consistency`, `check_document_structure`, `final_quality_audit`, `compare_documents`, `check_similarity`, `lookup_standard`, `check_standards` |
| Mise en forme et export | `list_format_presets`, `export_document`, `check_formatting`, `apply_formatting` |
| Disciplines | `identify_domain`, `set_project_domain`, `set_secondary_domains`, `list_domain_profiles`, `get_domain_profile`, `get_document_structure_template`, `lookup_terminology`, `reload_domain_profiles` |

Ressources : `academic-writer://info`, `academic-writer://projects`,
`academic-writer://projects/{project_id}`, `academic-writer://document-types`,
`academic-writer://languages`, `academic-writer://domains`, `academic-writer://domains/{domain_id}`,
`academic-writer://conventions`. Prompts : `academic_analysis`, `rediger_rapport`,
`verifier_avant_remise`, `trouver_sources`.
Profils disciplinaires : [docs/profils-disciplinaires.md](docs/profils-disciplinaires.md).

## Pile technique

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.12 | Langage |
| `mcp` (SDK officiel) | 2.3.x (`<3`) | Serveur MCP — API `MCPServer` (v2) |
| Pydantic / pydantic-settings | 2.x | Validation, configuration, sortie structurée |
| SQLite (WAL, FTS5) | 3.53 | Stockage local et recherche plein texte multilingue |
| pypdfium2 + pdfplumber | 5.x / 0.11 | PDF, lecteur par défaut (licences BSD/Apache/MIT) |
| PyMuPDF (option `uv sync --extra pymupdf`) | 2.x | PDF, lecteur alternatif (AGPL) |
| python-docx, openpyxl, python-pptx | 1.2 / 3.1 / 1.0 | DOCX, XLSX, PPTX (MIT) |
| charset-normalizer | 3.x | Détection d'encodage TXT/MD |
| Tesseract OCR (programme externe) | 5.4 | OCR fra/rus/eng (Apache-2.0) |
| anthropic, openai (SDK officiels) | 2.x / 3.x | Fournisseurs cloud (optionnels, consentement requis) |
| keyring | 25.x | Clés API dans le Gestionnaire d'identification Windows |
| Ollama (programme externe) | 0.40 | Modèle local `qwen3.5:4b` (aucun envoi externe) |
| LanguageTool 6.6 + Java 21 (externes) | — | Correction fr/ru/en, serveur LOCAL uniquement |
| matplotlib | 3.x | Graphiques (licence PSF/BSD) |
| Microsoft PowerPoint (externe, facultatif) | 2019+ | Export PDF / ODP et aperçus des présentations |
| pytest, reportlab (tests) | 9.x / 5.x | Tests et génération de PDF de test |

## Prérequis

- Windows 11, [uv](https://docs.astral.sh/uv/) ≥ 0.13, Git.
- Python 3.12 (installé et géré par uv : `uv python install 3.12`).

## Démarrage rapide (PowerShell)

```powershell
cd D:\MCP\academic-writer-mcp
uv sync                                   # installe les dépendances verrouillées
uv run pytest                             # lance les tests
uv run python -m academic_writer          # lance le serveur en stdio (Ctrl+C pour arrêter)
uv run mcp dev src/academic_writer/server/app.py   # MCP Inspector (navigateur)
```

## Maintenance (PowerShell)

```powershell
uv run academic-writer doctor                  # état de chaque composant + correction à faire
uv run academic-writer backup                  # sauvegarde complète (.zip) ; --db-only : base seule
uv run academic-writer backups                 # liste des sauvegardes
uv run academic-writer restore <fichier.zip> --yes   # Claude fermé ; sauvegarde de sécurité faite avant
uv run academic-writer setup-desktop [--apply] # déclarer le serveur dans Claude Desktop
```

Les clés API (coffre Windows) ne sont jamais incluses dans les sauvegardes.

- Configuration : [docs/config.example.toml](docs/config.example.toml) → `%APPDATA%\AcademicWriter\config.toml`.
- Installation sur un nouveau PC et clients MCP : [docs/INSTALLATION_WINDOWS.md](docs/INSTALLATION_WINDOWS.md).
- Décisions techniques : [docs/decisions.md](docs/decisions.md).

## Données locales

```
<data_dir>/                  (ex. D:\AcademicWriter-Data)
  academic_writer.db         base SQLite (WAL)
  projects/<id>/originals/   copies protégées (lecture seule) des fichiers importés
  projects/<id>/derived/     résultats d'extraction et images extraites (régénérables)
  tessdata/                  langues de l'OCR (fra, rus, eng)
  logs/                      journaux (sans contenu de document)
  backups/                   sauvegardes de la base (.db) et complètes (.zip)
```

## Structure du code

```
src/academic_writer/
  server/     couche MCP : app.py, tools_*.py, resources.py, services.py
  core/       config, modèles, erreurs, journalisation, projets, documents, historique
  storage/    SQLite : connexion, transactions, migrations, sauvegardes
  security/   contrôle des chemins, inspection des fichiers
  document/   lecteurs (docx, pdf_pdfium, pdf_pymupdf, text, xlsx, pptx), OCR, mise en page, rendu
  domains/    schéma des profils, chargement/héritage, détection, gabarits de structure
  providers/  fournisseurs IA : Anthropic, OpenAI, Ollama, simulé ; secrets ; consentement ; usage
  writing/    exigences, plan, dossiers, contrôles, style, LanguageTool local
  ai_detection/ indices stylistiques (fr/ru/en), évaluation sur corpus annoté
  forensics/  métadonnées Office/PDF, historique, texte masqué, provenance C2PA / IPTC
  research/   sources : validation (ISBN, DOI…), vérification en ligne, styles bibliographiques
  domain_profiles/  17 profils YAML + _document_structures.yaml (3 conventions × 11 familles)
tests/        tests unitaires, sécurité, intégration MCP
docs/         documentation technique
```

## Licence

Tous droits réservés — voir [LICENSE](LICENSE). Le code est consultable publiquement, mais aucune
réutilisation n'est autorisée sans accord écrit. Les dépendances tierces gardent leurs propres licences.
