# Installation et connexion des clients MCP (Windows 11)

Chemin du projet utilisé ci-dessous : `D:\MCP\academic-writer-mcp`.
Chemin de uv : `C:\Users\OSA Gaming\.local\bin\uv.exe` (vérifier avec `(Get-Command uv).Source`).

Le serveur utilise le transport **stdio** : le client lance lui-même le processus.
Commande de lancement commune :

```
uv --directory D:\MCP\academic-writer-mcp run --no-sync python -m academic_writer
```

Pourquoi `--no-sync` et `python -m` : voir la décision D-006 dans [decisions.md](decisions.md)
(évite le verrouillage de `academic-writer.exe` par Windows pendant le développement).
Après un ajout de dépendances : `uv sync`, puis redémarrer les clients.

## 1. Test avec MCP Inspector

```powershell
cd D:\MCP\academic-writer-mcp
uv run mcp dev src/academic_writer/server/app.py
```

Une page s'ouvre dans le navigateur → **Connect** → onglet **Tools** → `ping` → **Run Tool**.
Node.js est requis (Inspector est lancé via `npx`).

## 2. Claude Code (CLI / extension VS Code)

```powershell
claude mcp add academic-writer --scope user -- uv --directory D:\MCP\academic-writer-mcp run --no-sync python -m academic_writer
claude mcp list
```

## 3. Claude Desktop

**Attention, l'emplacement dépend de la version installée.** Pour trouver le bon fichier,
ouvrir `%LOCALAPPDATA%\Claude\logs\main.log` et chercher la ligne
`Reading claude_desktop_config.json from ...`, ou utiliser le menu
*Paramètres → Développeur → Modifier la configuration*.

| Installation | Emplacement |
|---|---|
| Microsoft Store, versions récentes (données hors paquet) | `%LOCALAPPDATA%\Claude-Data\claude_<id>\claude_desktop_config.json` |
| Microsoft Store, versions anciennes | `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| Installateur classique | `%APPDATA%\Claude\claude_desktop_config.json` |

Sur le poste de développement : `C:\Users\OSA Gaming\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json`.
Ce fichier contient aussi les préférences de l'application : n'ajouter que l'entrée
`academic-writer` dans `mcpServers`, sans toucher au reste, et faire une sauvegarde avant.

Entrée à ajouter dans `mcpServers` :

```json
{
  "mcpServers": {
    "academic-writer": {
      "command": "C:\\Users\\OSA Gaming\\.local\\bin\\uv.exe",
      "args": ["--directory", "D:\\MCP\\academic-writer-mcp", "run", "--no-sync", "python", "-m", "academic_writer"]
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
      "args": ["--directory", "D:\\MCP\\academic-writer-mcp", "run", "--no-sync", "python", "-m", "academic_writer"]
    }
  }
}
```

## 5. OCR (Tesseract) — facultatif mais recommandé

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact     # accepter la fenêtre UAC
$dir = "D:\AcademicWriter-Data\tessdata"                  # = <data_dir>\tessdata
New-Item -ItemType Directory -Force $dir
foreach ($l in "fra","rus","eng") {
  Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata/raw/main/$l.traineddata" -OutFile "$dir\$l.traineddata"
}
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --tessdata-dir $dir --list-langs
```

## 6. Lecteur PDF PyMuPDF (facultatif, licence AGPL)

```powershell
cd D:\MCP\academic-writer-mcp
uv sync --extra pymupdf
```
puis `pdf_backend = 'pymupdf'` dans `config.toml`.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le client ne voit pas le serveur | `uv` introuvable pour une application graphique | Utiliser le chemin complet de `uv.exe` |
| Erreur de protocole / JSON invalide | Écriture sur stdout | Ne jamais utiliser `print()` dans le serveur ; utiliser `logging` |
| `ModuleNotFoundError: mcp.server.fastmcp` | Tutoriel v1 | Utiliser `from mcp.server import MCPServer` (SDK v2) |
| Accents illisibles dans les journaux | stderr en cp1252 | Déjà corrigé (stderr forcé en UTF-8) |
