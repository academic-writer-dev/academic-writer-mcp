# Installation et connexion des clients MCP (Windows 11)

Chemin du projet utilisé ci-dessous : `D:\MCP\academic-writer-mcp`.
Chemin de uv : `C:\Users\OSA Gaming\.local\bin\uv.exe` (vérifier avec `(Get-Command uv).Source`).

Le serveur utilise le transport **stdio** : le client lance lui-même le processus.
Commande de lancement commune :

```
uv --directory D:\MCP\academic-writer-mcp run academic-writer
```

## 1. Test avec MCP Inspector

```powershell
cd D:\MCP\academic-writer-mcp
uv run mcp dev src/academic_writer/server/app.py
```

Une page s'ouvre dans le navigateur → **Connect** → onglet **Tools** → `ping` → **Run Tool**.
Node.js est requis (Inspector est lancé via `npx`).

## 2. Claude Code (CLI / extension VS Code)

```powershell
claude mcp add academic-writer --scope user -- uv --directory D:\MCP\academic-writer-mcp run academic-writer
claude mcp list
```

## 3. Claude Desktop

Fichier : `%APPDATA%\Claude\claude_desktop_config.json` (le créer s'il n'existe pas) :

```json
{
  "mcpServers": {
    "academic-writer": {
      "command": "C:\\Users\\OSA Gaming\\.local\\bin\\uv.exe",
      "args": ["--directory", "D:\\MCP\\academic-writer-mcp", "run", "academic-writer"]
    }
  }
}
```

Redémarrer complètement Claude Desktop (quitter depuis la zone de notification).

## 4. VS Code (GitHub Copilot, mode Agent)

Fichier `.vscode/mcp.json` dans l'espace de travail :

```json
{
  "servers": {
    "academic-writer": {
      "type": "stdio",
      "command": "C:\\Users\\OSA Gaming\\.local\\bin\\uv.exe",
      "args": ["--directory", "D:\\MCP\\academic-writer-mcp", "run", "academic-writer"]
    }
  }
}
```

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le client ne voit pas le serveur | `uv` introuvable pour une application graphique | Utiliser le chemin complet de `uv.exe` |
| Erreur de protocole / JSON invalide | Écriture sur stdout | Ne jamais utiliser `print()` dans le serveur ; utiliser `logging` |
| `ModuleNotFoundError: mcp.server.fastmcp` | Tutoriel v1 | Utiliser `from mcp.server import MCPServer` (SDK v2) |
| Accents illisibles dans les journaux | stderr en cp1252 | Déjà corrigé (stderr forcé en UTF-8) |
