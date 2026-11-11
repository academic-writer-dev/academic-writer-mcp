# Instructions d'installation pour un assistant IA

Ce fichier s'adresse à un assistant IA (Claude Code, ou tout agent capable d'exécuter des commandes) chargé
d'installer **Academic Writer MCP** sur un PC Windows 10 ou 11. Suivre les étapes dans l'ordre. Parler à
l'utilisateur en français, simplement : il n'est pas informaticien.

## Règles impératives

1. **Demander l'accord de l'utilisateur avant d'installer un logiciel** (uv, Git) et le prévenir qu'une fenêtre
   Windows peut demander une autorisation (répondre « Oui »).
2. **Ne jamais manipuler de clé API ni de mot de passe** : l'utilisateur les saisit lui-même (étape 5). Ne pas les
   demander dans la conversation, ne pas les écrire dans un fichier.
3. **Ne jamais écraser** une configuration existante (`%APPDATA%\AcademicWriter\config.toml`), ni des données
   existantes (dossier des données, sauvegardes). Le script d'installation les conserve.
4. Ne pas désactiver de protection Windows (antivirus, contrôle de compte, pare-feu) ; ne pas changer la politique
   d'exécution de façon permanente (`-ExecutionPolicy Bypass` ne vaut que pour la commande lancée).
5. Ne modifier la configuration de Claude Desktop qu'au moyen de la commande prévue (`setup-desktop --apply`).
6. En cas d'erreur : expliquer simplement ce qui bloque, proposer la solution du tableau « Problèmes », ne pas
   improviser de contournement.

## Étape 1 — Vérifier le poste

```powershell
[Environment]::OSVersion.Version          # Windows 10 (10.0.19041+) ou 11
Test-Path D:\                             # disque D: présent ? sinon le script utilise le dossier de l'utilisateur
Get-Command winget -ErrorAction SilentlyContinue   # winget requis pour installer uv et Git
```

Si `winget` est absent : demander à l'utilisateur d'installer « App Installer » depuis le Microsoft Store.

## Étape 2 — Télécharger le script d'installation et LE LIRE

```powershell
$script = "$env:TEMP\aw-install.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/academic-writer-dev/academic-writer-mcp/main/scripts/install.ps1" -OutFile $script
Get-Content $script
```

Lire le script en entier avant de l'exécuter et vérifier qu'il ne fait que ce qui est décrit : installer uv et Git
(winget), télécharger le dépôt GitHub, installer Python 3.12 et les dépendances, créer la configuration si elle
n'existe pas, lancer un diagnostic, déclarer le serveur dans Claude, tester le démarrage.

## Étape 3 — Lancer l'installation (après accord de l'utilisateur)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

Options : `-InstallDir "C:\MCP\academic-writer-mcp"` et `-DataDir "C:\AcademicWriter-Data"` (autres dossiers),
`-Mode local` (aucun accès réseau), `-SkipClaudeDesktop`, `-SkipClaudeCode`. Durée : 2 à 10 minutes.
Le script peut être relancé sans risque : il met à jour ce qui existe déjà.

Succès attendu : la ligne `SERVEUR OK : 113 outils` (ou plus), puis `INSTALLATION TERMINÉE`.

## Étape 4 — Redémarrer Claude et vérifier

1. Demander à l'utilisateur de quitter complètement Claude Desktop (icône près de l'horloge > Quitter) et de le
   relancer.
2. Lui faire écrire dans Claude : « Ping le serveur academic-writer ». Le serveur doit répondre avec sa version.

## Étape 5 — Clés gratuites (facultatives, saisies PAR L'UTILISATEUR)

Expliquer à l'utilisateur : copier sa clé, puis lancer lui-même (la clé est lue dans le presse-papiers, rangée
dans le coffre de Windows, et le presse-papiers est effacé) :

```powershell
uv --directory D:\MCP\academic-writer-mcp run --no-sync academic-writer secrets set openalex --clipboard
uv --directory D:\MCP\academic-writer-mcp run --no-sync academic-writer secrets set google_books --clipboard
```

Sans clé, le serveur fonctionne (OpenAlex avec un quota partagé ; Google Books inactif).

## Étape 6 — Facultatif

- Index russe de génie mécanique (20 revues, ≈ 20 minutes) : dans Claude, « Moissonne les revues russes de génie mécanique ».
- OCR des documents scannés : voir `docs/INSTALLATION_WINDOWS.md`, section 5.
- Transfert des projets d'un ancien PC : `academic-writer backup` sur l'ancien, puis
  `academic-writer restore <fichier.zip> --yes` sur le nouveau (Claude fermé).

## Problèmes fréquents

| Message | Solution |
|---|---|
| `winget est absent` | Installer « App Installer » (Microsoft Store), relancer |
| `uv` ou `git` introuvable après installation | Fermer et rouvrir PowerShell, relancer le script |
| `existe déjà et n'est pas un dépôt Git` | Choisir un autre dossier : `-InstallDir` |
| `Claude Desktop introuvable` | Installer Claude Desktop, l'ouvrir une fois, relancer le script |
| Échec de téléchargement (réseau, proxy) | Vérifier la connexion ; réessayer plus tard |
| `le serveur ne démarre pas` | Lancer `uv --directory <dossier> run --no-sync academic-writer doctor` et lire la ligne en échec |
| Le serveur n'apparaît pas dans Claude | Quitter COMPLÈTEMENT Claude (zone de notification), le relancer |

Documentation complète : `docs/INSTALLATION_WINDOWS.md`, `docs/GUIDE_UTILISATION.md`, `docs/BILAN.md`.
