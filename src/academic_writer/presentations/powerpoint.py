"""Microsoft PowerPoint (automatisation COM via PowerShell) : export PDF / ODP et aperçus PNG des diapositives.
Sans PowerPoint : PPTX seul. Aucun chemin n'est interpolé dans le script (variables d'environnement)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$app = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    $pres = $app.Presentations.Open($env:AW_PPTX, $true, $false, $false)
    if ($env:AW_PNG_DIR) {
        New-Item -ItemType Directory -Force $env:AW_PNG_DIR | Out-Null
        $i = 0
        foreach ($slide in $pres.Slides) {
            $i++
            $slide.Export((Join-Path $env:AW_PNG_DIR ('slide-{0:D2}.png' -f $i)), 'PNG', 1600, 900)
        }
    }
    if ($env:AW_ODP) { $pres.SaveCopyAs($env:AW_ODP, 35) }
    if ($env:AW_PDF) { $pres.SaveCopyAs($env:AW_PDF, 32) }
    $pres.Close()
    Write-Output 'OK'
} catch {
    Write-Output ('ERREUR ' + $_.Exception.Message)
} finally {
    if ($app -ne $null) { $app.Quit() | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
}
"""


def powerpoint_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\powerpnt.exe") as key:
            return Path(winreg.QueryValue(key, None)).exists()
    except OSError:
        return False


def export(pptx: Path, pdf: Path | None = None, odp: Path | None = None, png_dir: Path | None = None,
           timeout: int = 300) -> tuple[bool, str, list[Path]]:
    """(succès, message, aperçus PNG)."""
    if not powerpoint_available():
        return False, "Microsoft PowerPoint introuvable : PPTX seul (ouvrir et enregistrer en PDF à la main).", []
    import shutil
    import tempfile

    # Slide.Export refuse les chemins non ASCII (dossiers cyrilliques) : export dans un dossier temporaire ASCII.
    temp_png = Path(tempfile.mkdtemp(prefix="aw_png_")) if png_dir else None
    env = dict(os.environ, AW_PPTX=str(pptx.resolve()), AW_PDF=str(pdf.resolve()) if pdf else "",
               AW_ODP=str(odp.resolve()) if odp else "", AW_PNG_DIR=str(temp_png) if temp_png else "")
    try:
        completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],  # noqa: S603,S607
                                   capture_output=True, timeout=timeout, env=env, check=False,
                                   creationflags=0x08000000)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Automatisation de PowerPoint impossible : {exc}", []
    output = ""
    for encoding in ("utf-8", "cp866", "cp1251"):
        try:
            output = completed.stdout.decode(encoding).strip()
            break
        except UnicodeDecodeError:
            continue
    previews: list[Path] = []
    if png_dir and temp_png:
        png_dir.mkdir(parents=True, exist_ok=True)
        for image in sorted(temp_png.glob("slide-*.png")):
            previews.append(Path(shutil.move(str(image), png_dir / image.name)))
        shutil.rmtree(temp_png, ignore_errors=True)
    if output.endswith("OK"):
        done = [label for label, path in (("PDF", pdf), ("ODP", odp)) if path and path.exists()]
        return True, "PowerPoint : " + ", ".join(done + ([f"{len(previews)} aperçus"] if previews else [])) + ".", previews
    return False, f"PowerPoint n'a pas terminé : {output[-300:] or completed.stderr.decode(errors='replace')[-300:]}", previews
