# Installation et connexion des clients MCP (Windows 11)

Chemin du projet utilisé dans les exemples : `D:\MCP\academic-writer-mcp` (à adapter).
Chemin de uv : en général `C:\Users\<utilisateur>\.local\bin\uv.exe` (vérifier avec `(Get-Command uv).Source`).

## 0. Installation sur un nouveau PC

```powershell
winget install --id astral-sh.uv --exact
winget install --id Git.Git --exact
git clone <URL du dépôt> D:\MCP\academic-writer-mcp
cd D:\MCP\academic-writer-mcp
uv python install 3.12
uv sync                                        # dépendances verrouillées (uv.lock)
uv run academic-writer doctor                  # état de l'installation
uv run academic-writer setup-desktop --apply   # déclarer le serveur dans Claude Desktop
```

Les données (base, projets, sauvegardes) vont par défaut dans `%LOCALAPPDATA%\AcademicWriter` ;
pour un autre emplacement, définir `data_dir` dans `%APPDATA%\AcademicWriter\config.toml`
(modèle : [config.example.toml](config.example.toml)). Pour transférer les données d'un autre PC :
`uv run academic-writer backup` sur l'ancien, puis `uv run academic-writer restore <fichier.zip> --yes`
sur le nouveau (Claude fermé). Les clés API ne sont pas transférées : les ressaisir avec
`uv run academic-writer secrets set <service>`.

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

La commande `uv run academic-writer setup-desktop` trouve ce fichier automatiquement.
Ce fichier contient aussi les préférences de l'application : n'ajouter que l'entrée
`academic-writer` dans `mcpServers`, sans toucher au reste, et faire une sauvegarde avant.

Entrée à ajouter dans `mcpServers` :

```json
{
  "mcpServers": {
    "academic-writer": {
      "command": "C:\\Users\\<utilisateur>\\.local\\bin\\uv.exe",
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
      "command": "C:\\Users\\<utilisateur>\\.local\\bin\\uv.exe",
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

## 7. Modèle local Ollama (rédaction sans envoi externe)

```powershell
# Modèles sur D: (le disque C: peut être presque plein)
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\AcademicWriter-Data\ollama\models", "User")
winget install --id Ollama.Ollama --exact
ollama pull qwen3.5:4b
```

## 8. LanguageTool local (correction fr/ru/en)

```powershell
winget install --id Microsoft.OpenJDK.21 --exact     # accepter la fenêtre UAC
# Télécharger https://languagetool.org/download/LanguageTool-stable.zip
# et l'extraire dans D:\AcademicWriter-Data\languagetool\
```
Le serveur LanguageTool démarre automatiquement à la première vérification (outil `manage_languagetool`).

## 9. Fournisseurs cloud (facultatif)

Disponibles seulement dans les pays pris en charge par Anthropic / OpenAI. Clé saisie de façon masquée :
```powershell
uv run academic-writer secrets set anthropic     # ou openai ; « secrets status » pour vérifier
```
Puis `mode = 'connected'` dans `config.toml` et consentement par projet (phrase « J'autorise l'envoi externe »).

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le client ne voit pas le serveur | `uv` introuvable pour une application graphique | Utiliser le chemin complet de `uv.exe` |
| Erreur de protocole / JSON invalide | Écriture sur stdout | Ne jamais utiliser `print()` dans le serveur ; utiliser `logging` |
| `ModuleNotFoundError: mcp.server.fastmcp` | Tutoriel v1 | Utiliser `from mcp.server import MCPServer` (SDK v2) |
| Accents illisibles dans les journaux | stderr en cp1252 | Déjà corrigé (stderr forcé en UTF-8) |
