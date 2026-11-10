<#
.SYNOPSIS
    Installe (ou met à jour) Academic Writer MCP sur ce PC Windows 10/11 et le déclare dans Claude.

.DESCRIPTION
    Étapes : outils (uv, Git) -> téléchargement du dépôt -> Python 3.12 et dépendances verrouillées ->
    configuration (jamais écrasée si elle existe) -> diagnostic -> déclaration dans Claude Desktop et Claude Code ->
    test de démarrage du serveur. Le script peut être relancé sans risque (il met à jour ce qui existe déjà).
    Il ne manipule AUCUNE clé API : l'utilisateur les saisit lui-même ensuite.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1 -InstallDir "C:\MCP\academic-writer-mcp" -DataDir "C:\AcademicWriter-Data"
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "D:\MCP\academic-writer-mcp",
    [string]$DataDir = "D:\AcademicWriter-Data",
    [ValidateSet("connected", "local")][string]$Mode = "connected",
    [string]$RepoUrl = "https://github.com/academic-writer-dev/academic-writer-mcp.git",
    [switch]$SkipPrerequisites,
    [switch]$SkipClaudeDesktop,
    [switch]$SkipClaudeCode
)

$ErrorActionPreference = "Stop"
$script:Warnings = @()
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue  # un autre environnement Python actif ne doit pas interférer

function Step([string]$Number, [string]$Text) { Write-Host ""; Write-Host "[$Number] $Text" -ForegroundColor Cyan }
function Ok([string]$Text) { Write-Host "    OK : $Text" -ForegroundColor Green }
function Warn([string]$Text) { Write-Host "    ATTENTION : $Text" -ForegroundColor Yellow; $script:Warnings += $Text }
function Fail([string]$Text) { Write-Host ""; Write-Host "ÉCHEC : $Text" -ForegroundColor Red; exit 1 }
function Has([string]$Command) { [bool](Get-Command $Command -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";" + "$env:USERPROFILE\.local\bin"
}
function Run([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { Fail "$What (code $LASTEXITCODE)" }
}

Write-Host "Installation d'Academic Writer MCP" -ForegroundColor White

# --- 0. Emplacements : pas de disque D: -> dossier de l'utilisateur ------------------------------------------
if (-not (Test-Path "D:\")) {
    if (-not $PSBoundParameters.ContainsKey("InstallDir")) { $InstallDir = "$env:USERPROFILE\MCP\academic-writer-mcp" }
    if (-not $PSBoundParameters.ContainsKey("DataDir")) { $DataDir = "$env:USERPROFILE\AcademicWriter-Data" }
}
Write-Host "    Dossier du serveur : $InstallDir"
Write-Host "    Dossier des données : $DataDir"

# --- 1. Outils ---------------------------------------------------------------------------------------------------
Step "1/7" "Outils nécessaires (uv, Git)"
Refresh-Path
if (-not $SkipPrerequisites) {
    foreach ($tool in @(@{Cmd = "uv"; Id = "astral-sh.uv"}, @{Cmd = "git"; Id = "Git.Git"})) {
        if (Has $tool.Cmd) { Ok "$($tool.Cmd) déjà installé"; continue }
        if (-not (Has "winget")) { Fail "winget est absent : installer « App Installer » depuis le Microsoft Store, puis relancer." }
        Write-Host "    Installation de $($tool.Id) (Windows peut demander une autorisation : répondre Oui)..."
        winget install --id $tool.Id --exact --silent --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (-not (Has $tool.Cmd)) { Fail "$($tool.Cmd) n'a pas pu être installé. Fermer et rouvrir PowerShell, puis relancer le script." }
        Ok "$($tool.Cmd) installé"
    }
}
foreach ($cmd in @("uv", "git")) { if (-not (Has $cmd)) { Fail "$cmd introuvable." } }

# --- 2. Dépôt ----------------------------------------------------------------------------------------------------
Step "2/7" "Téléchargement du serveur"
if (Test-Path (Join-Path $InstallDir ".git")) {
    Run "mise à jour du dépôt" { git -C $InstallDir pull --ff-only }
    Ok "serveur mis à jour"
} elseif ((Test-Path $InstallDir) -and (Get-ChildItem $InstallDir -Force | Select-Object -First 1)) {
    Fail "$InstallDir existe déjà et n'est pas un dépôt Git : choisir un autre dossier avec -InstallDir."
} else {
    New-Item -ItemType Directory -Force (Split-Path $InstallDir -Parent) | Out-Null
    Run "téléchargement du dépôt" { git clone $RepoUrl $InstallDir }
    Ok "serveur téléchargé"
}

# --- 3. Python et dépendances ------------------------------------------------------------------------------------
Step "3/7" "Python 3.12 et dépendances (quelques minutes la première fois)"
Run "installation de Python 3.12" { uv python install 3.12 }
Run "installation des dépendances" { uv --directory $InstallDir sync }
Ok "environnement prêt"

# --- 4. Configuration (jamais écrasée) ---------------------------------------------------------------------------
Step "4/7" "Configuration"
$configDir = Join-Path $env:APPDATA "AcademicWriter"
$configFile = Join-Path $configDir "config.toml"
if (Test-Path $configFile) {
    Ok "configuration existante conservée : $configFile"
} else {
    New-Item -ItemType Directory -Force $configDir, $DataDir | Out-Null
    $importDirs = @("'$env:USERPROFILE'", "'$DataDir'")
    if (Test-Path "D:\") { $importDirs += "'D:\'" }
    $toml = @(
        "# Configuration créée par scripts\install.ps1 (modèle complet : docs\config.example.toml)",
        "data_dir = '$DataDir'",
        "mode = '$Mode'",
        "allowed_import_dirs = [$($importDirs -join ', ')]",
        "software_execution = false"
    ) -join "`r`n"
    [IO.File]::WriteAllText($configFile, $toml + "`r`n", (New-Object Text.UTF8Encoding $false))
    Ok "configuration créée : $configFile (mode $Mode)"
}

# --- 5. Diagnostic -----------------------------------------------------------------------------------------------
Step "5/7" "Diagnostic"
uv --directory $InstallDir run --no-sync academic-writer doctor
if ($LASTEXITCODE -ne 0) { Warn "le diagnostic signale des éléments facultatifs absents (OCR, Word, clés) : voir ci-dessus." }

# --- 6. Clients Claude -------------------------------------------------------------------------------------------
Step "6/7" "Déclaration dans Claude"
if (-not $SkipClaudeDesktop) {
    uv --directory $InstallDir run --no-sync academic-writer setup-desktop --apply
    if ($LASTEXITCODE -eq 0) { Ok "Claude Desktop configuré (le redémarrer complètement)" }
    else { Warn "Claude Desktop introuvable : l'installer, l'ouvrir une fois, puis relancer ce script." }
}
if (-not $SkipClaudeCode) {
    if (Has "claude") {
        claude mcp get academic-writer *> $null
        if ($LASTEXITCODE -eq 0) { Ok "Claude Code : serveur déjà déclaré" }
        else {
            $uvPath = (Get-Command uv).Source
            claude mcp add academic-writer --scope user -- $uvPath --directory $InstallDir run --no-sync python -m academic_writer
            if ($LASTEXITCODE -eq 0) { Ok "Claude Code configuré" } else { Warn "déclaration dans Claude Code impossible" }
        }
    } else {
        Write-Host "    Claude Code absent : étape ignorée."
    }
}

# --- 7. Test de démarrage ----------------------------------------------------------------------------------------
Step "7/7" "Test de démarrage du serveur"
$test = Join-Path $env:TEMP "aw-install-test.py"
@'
import asyncio, sys, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "academic_writer"])
    start = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
    print(f"SERVEUR OK : {len(tools.tools)} outils, démarrage en {time.time() - start:.1f} s")

asyncio.run(main())
'@ | Set-Content -Path $test -Encoding UTF8
uv --directory $InstallDir run --no-sync python $test
$started = ($LASTEXITCODE -eq 0)
Remove-Item $test -ErrorAction SilentlyContinue
if (-not $started) { Fail "le serveur ne démarre pas : lancer « uv --directory $InstallDir run --no-sync academic-writer doctor »." }

# --- Fin ---------------------------------------------------------------------------------------------------------
Write-Host ""
Write-Host "INSTALLATION TERMINÉE" -ForegroundColor Green
Write-Host "Étapes restantes (à faire par l'utilisateur) :"
Write-Host "  1. Quitter complètement Claude Desktop (zone de notification > Quitter) puis le relancer."
Write-Host "  2. Dans Claude, écrire : « Ping le serveur academic-writer »."
Write-Host "  3. Clés gratuites facultatives (copier la clé, puis) :"
Write-Host "       uv --directory `"$InstallDir`" run --no-sync academic-writer secrets set openalex --clipboard"
Write-Host "       uv --directory `"$InstallDir`" run --no-sync academic-writer secrets set google_books --clipboard"
Write-Host "  4. Facultatif : dans Claude, « Moissonne les revues russes de génie mécanique »."
if ($script:Warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Points à vérifier :" -ForegroundColor Yellow
    $script:Warnings | ForEach-Object { Write-Host "  - $_" }
}
exit 0
