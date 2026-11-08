# Academic Writer MCP

Serveur [Model Context Protocol](https://modelcontextprotocol.io) local destiné à analyser,
structurer, vérifier et mettre en forme des documents académiques, scientifiques,
techniques et professionnels (FR / RU / EN).

> **Statut : Phase 3 terminée — lecture des documents (DOCX, PDF, TXT, MD, XLSX, PPTX),
> OCR (fra/rus/eng) et recherche plein texte multilingue.**

## Principes

- Traitement **local par défaut** ; aucun envoi externe sans consentement explicite.
- Le serveur fournit des **outils** ; c'est l'assistant IA (Claude, ChatGPT, modèle local…)
  qui raisonne et rédige. Le serveur n'appelle pas lui-même de modèle IA dans le MVP.
- L'**original n'est jamais modifié** : copie vérifiée (SHA-256) en lecture seule.
- Aucune donnée, citation ou référence inventée ; toute incertitude est signalée.

## Outils MCP disponibles

| Catégorie | Outils |
|---|---|
| Diagnostic | `ping` |
| Projets | `create_project`, `get_project`, `list_projects`, `update_project`, `archive_project` |
| Documents | `import_document`, `list_documents`, `get_document_metadata` |
| Extraction et recherche | `extract_document_content`, `extract_document_tables`, `extract_document_images`, `search_in_documents` |

Ressources : `academic-writer://info`, `academic-writer://projects`,
`academic-writer://projects/{project_id}`, `academic-writer://document-types`,
`academic-writer://languages`. Prompt : `academic_analysis`.

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

- Configuration : [docs/config.example.toml](docs/config.example.toml) → `%APPDATA%\AcademicWriter\config.toml`.
- Clients MCP : [docs/installation-windows.md](docs/installation-windows.md).
- Décisions techniques : [docs/decisions.md](docs/decisions.md).

## Données locales

```
<data_dir>/                  (ex. D:\AcademicWriter-Data)
  academic_writer.db         base SQLite (WAL)
  projects/<id>/originals/   copies protégées (lecture seule) des fichiers importés
  projects/<id>/derived/     résultats d'extraction et images extraites (régénérables)
  tessdata/                  langues de l'OCR (fra, rus, eng)
  logs/                      journaux (sans contenu de document)
  backups/                   sauvegardes automatiques de la base
```

## Structure du code

```
src/academic_writer/
  server/     couche MCP : app.py, tools_*.py, resources.py, services.py
  core/       config, modèles, erreurs, journalisation, projets, documents, historique
  storage/    SQLite : connexion, transactions, migrations, sauvegardes
  security/   contrôle des chemins, inspection des fichiers
  document/   lecteurs (docx, pdf_pdfium, pdf_pymupdf, text, xlsx, pptx), OCR, mise en page, rendu
tests/        tests unitaires, sécurité, intégration MCP
docs/         documentation technique
```
