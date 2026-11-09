"""Finalisation par Microsoft Word (automatisation COM via PowerShell) : mise à jour du sommaire et des
champs, export PDF fidèle au DOCX. Aucun chemin n'est interpolé dans le script (variables d'environnement)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($env:AW_DOCX, $false, $false, $false)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() | Out-Null }
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() | Out-Null }
    $doc.Save()
    if ($env:AW_PDF) { $doc.ExportAsFixedFormat($env:AW_PDF, 17) }
    $doc.Close($false)
    Write-Output 'OK'
} catch {
    Write-Output ('ERREUR ' + $_.Exception.Message)
} finally {
    if ($word -ne $null) { $word.Quit() | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}
"""


def word_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe") as key:
            return Path(winreg.QueryValue(key, None)).exists()
    except OSError:
        return False


def finalize(docx_path: Path, pdf_path: Path | None, timeout: int = 240) -> tuple[bool, str]:
    """Met à jour sommaire et champs du DOCX ; exporte le PDF si demandé. (succès, message)"""
    if not word_available():
        return False, "Microsoft Word introuvable : sommaire à mettre à jour à l'ouverture (F9), pas d'export PDF."
    env = dict(os.environ, AW_DOCX=str(docx_path.resolve()), AW_PDF=str(pdf_path.resolve()) if pdf_path else "")
    try:
        completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],  # noqa: S603,S607
                                   capture_output=True, timeout=timeout, env=env, check=False,
                                   creationflags=0x08000000)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Automatisation de Word impossible : {exc}"
    output = ""
    for encoding in ("utf-8", "cp866", "cp1251"):
        try:
            output = completed.stdout.decode(encoding).strip()
            break
        except UnicodeDecodeError:
            continue
    if output.endswith("OK") and (pdf_path is None or pdf_path.exists()):
        return True, "Sommaire et champs mis à jour par Word" + (" ; PDF exporté." if pdf_path else ".")
    return False, f"Word n'a pas terminé : {output[-300:] or completed.stderr.decode(errors='replace')[-300:]}"
