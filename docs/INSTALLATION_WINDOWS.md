# Installation et connexion des clients MCP (Windows 11)

Chemin du projet utilisé dans les exemples : `D:\MCP\academic-writer-mcp` (à adapter).
Chemin de uv : en général `C:\Users\<utilisateur>\.local\bin\uv.exe` (vérifier avec `(Get-Command uv).Source`).

## Installation automatique (recommandée)

**Avec une IA** (Claude Code sur le nouveau PC) : lui écrire

> Installe le serveur Academic Writer MCP sur ce PC en suivant les instructions de
> https://github.com/academic-writer-dev/academic-writer-mcp/blob/main/INSTALL_AI.md

**Sans IA** : ouvrir PowerShell et coller

```powershell
Invoke-WebRequest "https://raw.githubusercontent.com/academic-writer-dev/academic-writer-mcp/main/scripts/install.ps1" -OutFile "$env:TEMP\aw-install.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\aw-install.ps1"
```

Le script ([scripts/install.ps1](../scripts/install.ps1)) installe uv et Git, télécharge le serveur, installe Python
et les dépendances, crée la configuration (sans jamais écraser une configuration existante), le déclare dans
Claude Desktop et Claude Code, puis vérifie qu'il démarre. Il ne touche à aucune clé API.

## Autoriser l'installation sur un PC

### A. Autoriser l'IA à agir sur le PC

L'installation par IA se fait avec **Claude Code** (extension VS Code ou terminal) : Claude Desktop seul ne peut pas
lancer de commandes sur l'ordinateur.

1. Installer Claude Code sur le nouveau PC et s'y connecter avec son compte.
2. Quand Claude demande « Autoriser cette commande ? », **lire la commande** puis accepter. Pour les commandes
   répétitives et sans danger (`uv`, `git`), on peut choisir « Oui, et ne plus demander » : l'autorisation vaut
   pour ce dossier. Refuser toute commande qui n'a rien à voir avec l'installation.
3. Quand Windows affiche « Voulez-vous autoriser cette application à apporter des modifications ? » pendant
   l'installation de uv ou Git : répondre **Oui** (c'est winget, l'installateur officiel de Microsoft).
4. `-ExecutionPolicy Bypass` autorise l'exécution du script **pour cette seule commande** : aucun réglage de
   sécurité de Windows n'est modifié durablement.

### B. Contrôler QUI peut installer le serveur

Aujourd'hui, le dépôt GitHub est **public** : tout le monde peut le télécharger, même si la licence (« tous droits
réservés ») interdit de l'utiliser sans votre accord. Pour que seuls les PC que vous autorisez puissent
l'installer :

1. Rendre le dépôt privé : GitHub > dépôt `academic-writer-mcp` > **Settings** > **General** > tout en bas,
   **Danger Zone** > **Change visibility** > **Make private**.
2. Autoriser une personne : **Settings** > **Collaborators** > **Add people** > son nom d'utilisateur GitHub (elle
   reçoit une invitation à accepter). Pour vos propres PC, aucun ajout : votre compte suffit.
3. Sur le PC autorisé, lors du téléchargement, une fenêtre GitHub demande de se connecter : se connecter avec le
   compte autorisé (la connexion est mémorisée par Windows pour les mises à jour suivantes).
4. Retirer une autorisation : **Settings** > **Collaborators** > **Remove**. Le PC ne peut plus télécharger les
   mises à jour (la copie déjà installée reste sur ce PC).

Avec un dépôt privé, le lien `raw.githubusercontent.com` de l'installation automatique ne fonctionne plus sans
connexion : télécharger d'abord le dépôt (`git clone`, qui ouvre la fenêtre de connexion GitHub), puis lancer
`powershell -NoProfile -ExecutionPolicy Bypass -File D:\MCP\academic-writer-mcp\scripts\install.ps1`.

## 0. Installation sur un nouveau PC (pas à pas)

Prérequis : Windows 10 ou 11, une connexion Internet, environ 2 Go d'espace disque, et Claude Desktop (ou Claude
Code, ou VS Code) installé. Ouvrir **PowerShell** (touche Windows, taper « PowerShell », Entrée), puis :

```powershell
# 1. Outils : uv (Python) et Git
winget install --id astral-sh.uv --exact
winget install --id Git.Git --exact
# fermer puis rouvrir PowerShell pour que les commandes soient reconnues

# 2. Récupérer le serveur (dépôt GitHub)
git clone https://github.com/academic-writer-dev/academic-writer-mcp.git D:\MCP\academic-writer-mcp
cd D:\MCP\academic-writer-mcp

# 3. Installer Python 3.12 et les dépendances verrouillées (uv.lock)
uv python install 3.12
uv sync

# 4. Vérifier l'installation, puis déclarer le serveur dans Claude Desktop
uv run academic-writer doctor
uv run academic-writer setup-desktop --apply
```

5. **Configuration** : créer `%APPDATA%\AcademicWriter\config.toml` à partir de
   [config.example.toml](config.example.toml) ; au minimum :
   ```toml
   data_dir = 'D:\AcademicWriter-Data'          # dossier des projets
   mode = 'connected'                            # recherche dans les bibliothèques
   allowed_import_dirs = ['C:\Users\<VotreNom>', 'D:\']   # dossiers d'où importer des documents
   ```
6. **Clés gratuites** (facultatives, elles ne sont jamais copiées d'un PC à l'autre) :
   `uv run academic-writer secrets set openalex --clipboard` et `… secrets set google_books --clipboard`
   (copier la clé avant ; le presse-papiers est effacé ensuite).
7. **Index russe de génie mécanique** (facultatif, ≈ 20 minutes) : dans Claude, « Moissonne les revues russes de
   génie mécanique » (outil `cyberleninka_harvest_discipline`).
8. Quitter complètement Claude Desktop (zone de notification → Quitter), le relancer, puis écrire
   « Ping le serveur academic-writer ».

Mise à jour ultérieure du serveur : `cd D:\MCP\academic-writer-mcp`, `git pull`, `uv sync`, puis relancer Claude.

Le dépôt est publié « tous droits réservés » : l'installation est réservée aux ordinateurs autorisés par son
propriétaire.

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
