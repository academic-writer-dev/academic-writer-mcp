"""Traitements dans des logiciels du poste : préparation des fichiers d'entrée, lancement autorisé, résultats.

Sécurité :
- lancement seulement si ``software_execution = true`` dans config.toml ET ``confirm=true`` à chaque appel ;
- uniquement des moteurs à interface documentée et DÉTECTÉS sur le poste (aucun logiciel d'automatisme
  industriel, aucune connexion à un équipement) ;
- dossier de travail propre au traitement, durée maximale, aucune élévation de droits ; fichiers d'entrée,
  commande, versions, durée et sorties conservés (traçabilité) ;
- le résultat indique toujours QUEL logiciel l'a produit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.models import new_id
from academic_writer.core.projects import ProjectService

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-][A-Za-z0-9_\-.]{0,80}$")
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# moteur → (extensions d'entrée autorisées, exécutables candidats, construction de la commande)
ENGINES: dict[str, dict] = {
    "python": {"label": "Python (environnement d'Academic Writer : NumPy, SciPy, pandas, Matplotlib)",
               "ext": {".py", ".csv", ".json", ".txt"}, "exe": [],
               "cmd": lambda exe, main: [sys.executable, "-I", main]},
    "excel": {"label": "Microsoft Excel (recalcul des formules par COM)", "ext": {".xlsx"}, "exe": [], "cmd": None},
    "octave": {"label": "GNU Octave", "ext": {".m", ".csv", ".txt"}, "exe": ["octave-cli", "octave"],
               "cmd": lambda exe, main: [exe, "--no-gui", "--quiet", main]},
    "r": {"label": "R", "ext": {".R", ".r", ".csv", ".txt"}, "exe": ["Rscript"],
          "cmd": lambda exe, main: [exe, "--vanilla", main]},
    "scilab": {"label": "Scilab", "ext": {".sce", ".sci", ".csv"}, "exe": ["scilab-cli", "WScilex-cli"],
               "cmd": lambda exe, main: [exe, "-nwni", "-quit", "-f", main]},
    "calculix": {"label": "CalculiX (ccx)", "ext": {".inp"}, "exe": ["ccx"],
                 "cmd": lambda exe, main: [exe, "-i", Path(main).stem]},
    "maxima": {"label": "Maxima", "ext": {".mac", ".txt"}, "exe": ["maxima"],
               "cmd": lambda exe, main: [exe, "--very-quiet", "-b", main]},
}
FORBIDDEN = {"tia_portal", "codesys", "openplc", "factory_io"}

_EXCEL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$excel = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $book = $excel.Workbooks.Open($env:AW_XLSX)
    $excel.CalculateFull()
    $book.SaveAs($env:AW_OUT, 51)
    $book.Close($false)
    Write-Output 'OK'
} catch {
    Write-Output ('ERREUR ' + $_.Exception.Message)
} finally {
    if ($excel -ne $null) { $excel.Quit() | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
}
"""


class SoftwareJob(BaseModel):
    job_id: str
    project_id: str
    engine: str
    engine_label: str
    folder: str
    main_file: str
    files: list[str]
    created_at: str
    status: str = Field(description="prepared, finished, failed, refused.")
    runs: list[dict] = Field(default_factory=list)


class JobResult(BaseModel):
    job_id: str
    engine: str
    executed_by: str = Field(description="Logiciel qui a réellement produit les résultats (avec version si connue).")
    return_code: int | None
    duration_s: float | None
    stdout_tail: str
    stderr_tail: str
    output_files: list[str]
    tables: list[dict] = Field(default_factory=list, description="Aperçu des tableaux produits (CSV / XLSX).")
    images: list[str] = Field(default_factory=list)
    status: str
    notice: str = ("Résultats produits par le logiciel indiqué ; à vérifier (paramètres, unités, convergence) avant "
                   "de les intégrer à un rapport.")


def _engine_exe(engine: str) -> str | None:
    spec = ENGINES[engine]
    if engine == "python":
        return sys.executable
    if engine == "excel":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe") as key:
                path = winreg.QueryValue(key, None)
                return path if Path(path).exists() else None
        except OSError:
            return None
    return next((p for p in (shutil.which(e) for e in spec["exe"]) if p), None)


def _version(engine: str, exe: str) -> str | None:
    if engine == "python":
        return f"Python {sys.version.split()[0]}"
    if engine == "excel":
        return "Microsoft Excel"
    try:
        flag = {"r": "--version", "calculix": "-v", "maxima": "--version"}.get(engine, "--version")
        out = subprocess.run([exe, flag], capture_output=True, timeout=20, creationflags=_NO_WINDOW,
                             stdin=subprocess.DEVNULL)
        text = (out.stdout or out.stderr).decode("utf-8", "replace").strip().splitlines()
        return text[0][:120] if text else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _preview_table(path: Path) -> dict | None:
    try:
        if path.suffix.lower() == ".csv":
            import csv

            with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
                rows = [r for _, r in zip(range(21), csv.reader(handle, dialect), strict=False)]
            return {"file": path.name, "rows": rows}
        if path.suffix.lower() == ".xlsx":
            from openpyxl import load_workbook

            book = load_workbook(path, data_only=True, read_only=True)
            sheets = []
            for sheet in book.worksheets[:5]:
                rows = [["" if v is None else v for v in row] for _, row in
                        zip(range(21), sheet.iter_rows(values_only=True), strict=False)]
                sheets.append({"sheet": sheet.title, "rows": rows})
            return {"file": path.name, "sheets": sheets}
    except Exception as exc:  # noqa: BLE001 — aperçu facultatif
        return {"file": path.name, "error": str(exc)[:200]}
    return None


class SoftwareJobService:
    def __init__(self, settings: Settings, projects: ProjectService) -> None:
        self.settings = settings
        self.projects = projects

    def _folder(self, project_id: str, job_id: str | None = None) -> Path:
        base = self.settings.projects_dir / project_id / "software"
        return base / job_id if job_id else base

    def engines(self) -> list[dict]:
        return [{"engine": name, "label": spec["label"], "available": bool(_engine_exe(name)),
                 "input_extensions": sorted(spec["ext"])} for name, spec in ENGINES.items()]

    def prepare(self, project_id: str, engine: str, files: dict[str, str], main_file: str | None = None,
                table: dict | None = None) -> SoftwareJob:
        self.projects.get(project_id)
        if engine in FORBIDDEN:
            raise ValidationFailed("Logiciel d'automatisme industriel : aucun traitement n'est préparé ni lancé par "
                                   "Academic Writer (simulation dans le logiciel lui-même, validation professionnelle).")
        if engine not in ENGINES:
            raise ValidationFailed(f"Moteur non pris en charge : {', '.join(ENGINES)}.")
        spec = ENGINES[engine]
        if not files and not table:
            raise ValidationFailed("Aucun fichier d'entrée.")
        job_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + new_id()[:6]
        folder = self._folder(project_id, job_id)
        folder.mkdir(parents=True)
        written: list[str] = []
        for name, content in (files or {}).items():
            if not _SAFE_NAME.match(name) or ".." in name:
                raise ValidationFailed(f"Nom de fichier refusé : « {name} » (lettres, chiffres, - _ . ; pas de dossier).")
            if Path(name).suffix not in spec["ext"]:
                raise ValidationFailed(f"Extension non autorisée pour {engine} : {sorted(spec['ext'])}.")
            (folder / name).write_text(content, encoding="utf-8")
            written.append(name)
        if table:  # données tabulaires → XLSX (Excel) ou CSV (autres moteurs)
            header, rows = table.get("header") or [], table.get("rows") or []
            name = table.get("name") or ("donnees.xlsx" if engine == "excel" else "donnees.csv")
            if not _SAFE_NAME.match(name):
                raise ValidationFailed("Nom de tableau refusé.")
            if name.endswith(".xlsx"):
                from openpyxl import Workbook

                book = Workbook()
                sheet = book.active
                sheet.title = (table.get("sheet") or "Données")[:31]
                for row in [header, *rows] if header else rows:
                    sheet.append([_cell(v) for v in row])
                book.save(folder / name)
            else:
                import csv

                with (folder / name).open("w", encoding="utf-8", newline="") as handle:
                    csv.writer(handle).writerows([header, *rows] if header else rows)
            written.append(name)
        main = main_file or next((f for f in written if Path(f).suffix in (".py", ".m", ".R", ".r", ".sce", ".inp",
                                                                            ".mac", ".xlsx")), written[0])
        if main not in written:
            raise ValidationFailed("main_file doit être l'un des fichiers préparés.")
        job = SoftwareJob(job_id=job_id, project_id=project_id, engine=engine, engine_label=spec["label"],
                          folder=str(folder), main_file=main, files=written,
                          created_at=datetime.now().isoformat(timespec="seconds"), status="prepared")
        (folder / "job.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
        return job

    def get(self, project_id: str, job_id: str) -> SoftwareJob:
        if not re.fullmatch(r"[\w\-]{6,40}", job_id):
            raise ValidationFailed("Identifiant de traitement invalide.")
        path = self._folder(project_id, job_id) / "job.json"
        if not path.exists():
            raise NotFoundError(f"Traitement introuvable : {job_id}")
        return SoftwareJob.model_validate_json(path.read_text(encoding="utf-8"))

    def run(self, project_id: str, job_id: str, confirm: bool = False, timeout_s: int | None = None) -> JobResult:
        job = self.get(project_id, job_id)
        if not self.settings.software_execution:
            raise ValidationFailed("Lancement désactivé : l'utilisateur doit l'autoriser dans config.toml "
                                   "(software_execution = true). Les fichiers préparés restent utilisables à la main "
                                   f"dans {job.folder}.")
        if not confirm:
            raise ValidationFailed("Confirmation requise : relancer avec confirm=true APRÈS accord explicite de "
                                   "l'utilisateur pour ce traitement.")
        exe = _engine_exe(job.engine)
        if not exe:
            raise ValidationFailed(f"{job.engine_label} n'est pas détecté sur ce poste : fichiers d'entrée à ouvrir "
                                   "dans le logiciel par l'utilisateur.")
        folder = Path(job.folder)
        before = {p.name for p in folder.iterdir()}
        timeout = min(timeout_s or self.settings.software_timeout_s, 1800)
        version = _version(job.engine, exe)
        started = time.monotonic()
        if job.engine == "excel":
            out_name = Path(job.main_file).stem + "-recalcule.xlsx"
            env = dict(os.environ, AW_XLSX=str(folder / job.main_file), AW_OUT=str(folder / out_name))
            command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", _EXCEL_SCRIPT]
        else:
            env = dict(os.environ)
            command = ENGINES[job.engine]["cmd"](exe, job.main_file)
        try:
            completed = subprocess.run(command, cwd=folder, capture_output=True, timeout=timeout, env=env,
                                       creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL, check=False)
            code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            status = "finished" if code == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr, status = None, exc.stdout or b"", exc.stderr or b"", "failed"
            stderr += f"\nInterrompu : durée maximale de {timeout} s dépassée.".encode()
        duration = round(time.monotonic() - started, 2)
        text_out = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else str(stdout)
        text_err = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else str(stderr)
        if job.engine == "excel" and not text_out.strip().endswith("OK"):
            status = "failed"
        outputs = sorted(p.name for p in folder.iterdir() if p.name not in before and p.name != "job.json")
        tables = [t for t in (_preview_table(folder / name) for name in outputs) if t]
        images = [str(folder / n) for n in outputs if n.lower().endswith((".png", ".jpg", ".svg"))]
        run_record = {"at": datetime.now().isoformat(timespec="seconds"), "command": [Path(c).name if i == 0 else c
                                                                                      for i, c in enumerate(command[:6])],
                      "version": version, "return_code": code, "duration_s": duration, "outputs": outputs,
                      "status": status}
        job.runs.append(run_record)
        job.status = status
        (folder / "job.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
        (folder / f"run-{len(job.runs)}.log").write_text(
            json.dumps(run_record, ensure_ascii=False, indent=2) + "\n--- stdout ---\n" + text_out
            + "\n--- stderr ---\n" + text_err, encoding="utf-8")
        return JobResult(job_id=job_id, engine=job.engine, executed_by=version or job.engine_label, return_code=code,
                         duration_s=duration, stdout_tail=text_out[-3000:], stderr_tail=text_err[-2000:],
                         output_files=[str(folder / n) for n in outputs], tables=tables, images=images, status=status)


def _cell(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("="):
            return text  # formule Excel conservée telle quelle
        try:
            return float(text.replace(",", ".")) if re.fullmatch(r"-?\d+(?:[.,]\d+)?", text) else value
        except ValueError:
            return value
    return value
