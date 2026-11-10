# Architecture

Academic Writer MCP est un serveur [Model Context Protocol](https://modelcontextprotocol.io) local (Python 3.12,
SDK officiel `mcp` 2.3, API `MCPServer`), transport **stdio** : stdout est réservé au protocole, les journaux
vont sur stderr et dans `<data_dir>/logs`. 107 outils, 8 ressources, 4 prompts.

## Couches

```
client MCP (Claude Desktop, Claude Code, VS Code)
        │ stdio (JSON-RPC)
server/      app.py (MCPServer), tools_*.py (outils), resources.py, services.py (assemblage)
        │
core/        services métier : projets, documents, extraction, domaines, rédaction, édition, sources,
             audit, qualité, mise en forme, cours / enseignants, graphiques, présentations,
             logiciels (détection + traitements), maintenance
        │
modules      document/ (lecteurs, OCR)   writing/ (exigences, plans, dossiers, contrôles)
spécialisés  research/ (sources, bases ouvertes, styles)   quality/ (calculs, SymPy, SciPy, similarité, normes)
             formatting/ (DOCX, Word)   presentations/ (PPTX, PowerPoint)   charts.py (matplotlib)
             domains/ + domain_profiles/ (40 profils YAML)   ai_detection/   forensics/   providers/ (IA)
        │
storage/     SQLite (WAL, FTS5), migrations versionnées (v12), sauvegarde automatique avant migration
security/    contrôle des chemins, inspection des fichiers importés
```

## Correspondance avec l'architecture cible

| Module cible | Implémentation |
|---|---|
| Core Orchestrator | `server/services.py` (injection de dépendances), `server/app.py` |
| Project Management | `core/projects.py`, `core/history.py`, `core/maintenance.py` |
| Document Intelligence | `document/`, `core/extraction.py` (OCR avec confiance, tableaux, recherche FTS5), `quality/compare.py` |
| Domain Adaptation | `domains/`, `domain_profiles/`, `core/domains.py` (profil principal + secondaires) |
| Professor and Course Profiles | `core/teaching.py`, `core/course.py`, `writing/constraints.py`, `writing/teacher_extract.py` |
| Academic Writing | `core/writing.py`, `writing/`, `core/editing.py` (correction, style, traduction) |
| Research and Source Manager | `core/sources.py`, `research/` (discovery, openscience, openscience_more, providers) |
| Scientific Calculation | `quality/calculations.py`, `quality/symbolic.py` (SymPy), `quality/numeric.py` (SciPy), `quality/problem.py` |
| Graph and Visualization | `charts.py`, `core/charts.py` |
| Software Interoperability Manager | `core/software.py` (catalogue, détection), `core/software_jobs.py` (traitements) |
| Standards and Compliance | `quality/standards.py`, normes des profils |
| Citation and Bibliography | `research/styles.py` (GOST, APA, IEEE, Chicago, Vancouver, Harvard, ISO 690) |
| Similarity and AI Indicator Analysis | `quality/similarity.py`, `ai_detection/` |
| Document Forensics | `forensics/`, `core/audit.py` |
| Presentation Designer | `presentations/` (models, planner, builder, powerpoint), `core/presentations.py` |
| Quality Assurance | `core/quality.py` (audit final, calculs, affirmations, cohérence, structure) |
| Document Export | `formatting/` (DOCX, PDF via Word, Markdown, texte), `export_tables` (XLSX, CSV) |
| Security and Privacy | `security/`, `providers/secrets.py` (coffre Windows), politiques de consentement |
| AI Provider Manager | `providers/` (Anthropic, OpenAI, Ollama, assistant MCP ; désactivés par défaut) |

## Base de données (SQLite)

Projets (politique de sources, enseignant, profils secondaires), documents (copie protégée, SHA-256),
extractions et index plein texte, exigences, plans et sections, révisions, sources et citations, audits et
constats, profils d'enseignants, consentements et usage des fournisseurs d'IA, historique des actions.
Graphiques, présentations et traitements logiciels sont conservés en fichiers dans le dossier du projet
(données, script, journal).

## Démarrage

Bibliothèques lourdes (python-docx, python-pptx, lxml, matplotlib, SymPy, SciPy) chargées au premier usage :
démarrage ≈ 2 s (mesuré), sous la limite de 30 s des clients.
