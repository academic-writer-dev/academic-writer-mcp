# Configuration

Fichier : `%APPDATA%\AcademicWriter\config.toml` (modèle commenté : [config.example.toml](config.example.toml)).
Priorité : variables d'environnement `ACADEMIC_WRITER_*` > fichier > valeurs par défaut.

| Réglage | Défaut | Effet |
|---|---|---|
| `data_dir` | `%LOCALAPPDATA%\AcademicWriter` | Base, projets, sauvegardes, journaux |
| `mode` | `local` | `local` : aucun accès réseau ; `connected` : recherche de sources et fournisseurs autorisés |
| `allowed_import_dirs` | dossier utilisateur | Seuls ces dossiers peuvent être importés |
| `max_file_size_mb` | 100 | Taille maximale d'un import |
| `software_execution` | `false` | Autorise `run_software_job` (avec `confirm=true` à chaque lancement) |
| `software_timeout_s` | 180 | Durée maximale d'un traitement logiciel |
| `writing_engine` | `auto` | Moteur de rédaction : cloud autorisé, modèle local, ou assistant MCP |
| `pdf_backend` | `pdfium` | `pymupdf` possible (licence AGPL, installation séparée) |
| `log_level` | `INFO` | Niveau des journaux (jamais de contenu de document ni de clé) |

Diagnostic : `uv run academic-writer doctor` (ou l'outil `system_check`).

## Politique de sources d'un projet

`set_project_teaching` : `course_only` (documents de l'enseignant seulement), `project_sources` (défaut),
`external_allowed` (externe permis, signalé). Appliquée automatiquement si les consignes disent
« uniquement à partir du cours » (fr / ru / en), sauf choix contraire de l'utilisateur.
