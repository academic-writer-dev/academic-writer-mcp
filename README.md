# Academic Writer MCP

Serveur [Model Context Protocol](https://modelcontextprotocol.io) local destiné à analyser,
structurer, vérifier et mettre en forme des documents académiques, scientifiques,
techniques et professionnels (FR / RU / EN).

> **Statut : Phase 1 — serveur minimal.** Seuls `ping`, la ressource `academic-writer://info`
> et le prompt `academic_analysis` sont disponibles.

## Principes

- Traitement **local par défaut** ; aucun envoi externe sans consentement explicite.
- Le serveur fournit des **outils** ; c'est l'assistant IA (Claude, ChatGPT, modèle local…)
  qui raisonne et rédige. Le serveur n'appelle pas lui-même de modèle IA dans le MVP.
- L'**original n'est jamais modifié** ; toute modification produit une révision à valider.
- Aucune donnée, citation ou référence inventée ; toute incertitude est signalée.

## Prérequis

- Windows 11, [uv](https://docs.astral.sh/uv/) ≥ 0.13, Git.
- Python 3.12 (installé et géré par uv : `uv python install 3.12`).

## Démarrage rapide (PowerShell)

```powershell
cd D:\MCP\academic-writer-mcp
uv sync                     # crée .venv et installe les dépendances verrouillées
uv run pytest               # lance les tests
uv run academic-writer      # lance le serveur en stdio (Ctrl+C pour arrêter)
uv run mcp dev src/academic_writer/server/app.py   # MCP Inspector (navigateur)
```

Configuration des clients MCP : voir [docs/installation-windows.md](docs/installation-windows.md).

## Pile technique

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.12 | Langage |
| `mcp` (SDK officiel) | 2.3.x (`<3`) | Serveur MCP — API `MCPServer` (v2) |
| Pydantic | 2.x | Validation, sortie structurée des outils |
| pytest + anyio | 9.x / 4.x | Tests (client MCP en mémoire) |

## Structure

```
src/academic_writer/
  server/     couche MCP (outils, ressources, prompts)
  core/       noyau, configuration (Phase 2)
  storage/    SQLite / FTS5 (Phase 2)
  security/   chemins, validation de fichiers, secrets (Phase 2)
  document/   lecture et extraction documentaire (Phase 3)
tests/        tests automatisés
docs/         documentation technique
data/         données locales de l'utilisateur (non versionnées)
```
