"""Maintenance (phase 10) : diagnostic complet, sauvegarde / restauration, configuration des clients MCP.

La restauration remplace les données : elle n'existe qu'en ligne de commande, avec confirmation explicite, et
crée d'abord une sauvegarde complète de l'état actuel.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer import __version__
from academic_writer.core.config import Settings
from academic_writer.core.errors import ValidationFailed
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.maintenance")

CheckStatus = Literal["ok", "attention", "absent", "erreur"]
PROJECT_DIR = Path(__file__).resolve().parents[3]  # dépôt (installation depuis les sources)
SERVER_NAME = "academic-writer"
_MANIFEST = "manifest.json"
_DB_NAME = "academic_writer.db"


class ComponentCheck(BaseModel):
    component: str
    status: CheckStatus
    detail: str
    fix: str | None = None
    required: bool = Field(default=False, description="Indispensable au fonctionnement de base.")


class Diagnosis(BaseModel):
    version: str
    generated_at: str
    ready: bool = Field(description="Tous les composants indispensables sont opérationnels.")
    summary: str
    checks: list[ComponentCheck]


class BackupInfo(BaseModel):
    path: str
    kind: Literal["complete", "base"]
    size_mb: float
    created_at: str


class BackupList(BaseModel):
    folder: str
    backups: list[BackupInfo]


class RestoreResult(BaseModel):
    restored_from: str
    safety_backup: str
    projects_restored: int
    schema_version: int
    messages: list[str]


class ClientSetup(BaseModel):
    client: str
    config_path: str | None
    status: Literal["deja_configure", "a_configurer", "configure", "introuvable", "different"]
    detail: str
    entry: dict
    backup_path: str | None = None


# --- diagnostic ----------------------------------------------------------------------------------

def server_entry() -> dict:
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv.exe")
    return {"command": uv, "args": ["--directory", str(PROJECT_DIR), "run", "--no-sync", "python", "-m",
                                    "academic_writer"]}


def desktop_config_candidates() -> list[Path]:
    """Fichiers de configuration de Claude Desktop : version classique et version Microsoft Store."""
    found: list[Path] = []
    appdata, local = os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")
    if appdata:
        found.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    if local:
        found += sorted((Path(local) / "Claude-Data").glob("claude_*/claude_desktop_config.json"))
    if sys.platform == "darwin":
        found.append(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    return [p for p in found if p.exists()]


def _free_gb(path: Path) -> float:
    try:
        return shutil.disk_usage(path).free / 1024 ** 3
    except OSError:
        return -1


def diagnose(services) -> Diagnosis:  # services : Services (import circulaire évité)
    settings: Settings = services.settings
    checks: list[ComponentCheck] = []
    add = checks.append

    add(ComponentCheck(component="Python", status="ok", required=True,
                       detail=f"{platform.python_version()} ({sys.executable})"))
    free = _free_gb(settings.data_dir)
    add(ComponentCheck(component="Dossier de données", required=True,
                       status="ok" if free > 2 else "attention",
                       detail=f"{settings.data_dir} — {free:.1f} Go libres",
                       fix=None if free > 2 else "Libérer de l'espace disque sur ce lecteur."))
    try:
        with services.db.read() as conn:
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        size = settings.db_path.stat().st_size / 1024 ** 2
        add(ComponentCheck(component="Base de données", required=True,
                           status="ok" if integrity == "ok" else "erreur",
                           detail=f"schéma v{services.db.schema_version()}, {projects} projet(s), {documents} document(s), "
                                  f"{size:.1f} Mo, intégrité : {integrity}",
                           fix=None if integrity == "ok" else "Restaurer une sauvegarde (academic-writer restore)."))
    except sqlite3.Error as exc:
        add(ComponentCheck(component="Base de données", status="erreur", required=True, detail=str(exc),
                           fix="Restaurer une sauvegarde (academic-writer restore)."))
    add(ComponentCheck(component="Mode réseau", status="ok",
                       detail=("local : aucun envoi externe" if settings.mode == "local" else
                               "connecté : recherche de sources et fournisseurs d'IA autorisés"),
                       fix=None if settings.mode == "connected" else
                       "Passer en mode « connected » (config.toml) pour chercher des sources en ligne."))

    engine = services.extraction.ocr_engine()
    if engine is None:
        add(ComponentCheck(component="OCR (Tesseract)", status="absent",
                           detail="Tesseract introuvable : les PDF scannés ne seront pas lus.",
                           fix="winget install UB-Mannheim.TesseractOCR"))
    else:
        languages = engine.available_languages()
        missing = [lang for lang in ("fra", "rus", "eng") if lang not in languages]
        add(ComponentCheck(component="OCR (Tesseract)", status="attention" if missing else "ok",
                           detail=f"{engine.executable} — langues : {', '.join(sorted(languages & {'fra', 'rus', 'eng'}))}",
                           fix=f"Ajouter {', '.join(missing)}.traineddata dans le dossier tessdata." if missing else None))

    lt = services.editing.languagetool.status()
    add(ComponentCheck(component="LanguageTool (correction locale)",
                       status="ok" if lt.running or (lt.installation and lt.java) else "absent",
                       detail=lt.message, fix=None if lt.installation and lt.java else
                       "Voir docs/installation-windows.md (LanguageTool + Java 21)."))

    for item in services.ai.engines():
        label = {"ollama": "Modèle local (Ollama)", "anthropic": "Fournisseur Anthropic",
                 "openai": "Fournisseur OpenAI", "assistant": "Assistant MCP"}.get(item.engine, item.engine)
        add(ComponentCheck(component=label, status="ok" if item.available else "absent",
                           detail=(f"{item.model} — " if item.model else "") + item.reason))

    from academic_writer.providers import secrets
    for service, label in (("google_books", "Clé Google Books"), ("openalex", "Clé OpenAlex"),
                           ("core", "Clé CORE"), ("semantic_scholar", "Clé Semantic Scholar")):
        source = secrets.key_source(service)
        add(ComponentCheck(component=label, status="ok" if source else "absent",
                           detail=f"configurée ({source})" if source else "non configurée (facultative)",
                           fix=None if source else f"uv run academic-writer secrets set {service} --clipboard"))

    from academic_writer.formatting import word
    add(ComponentCheck(component="Microsoft Word (export PDF)", status="ok" if word.word_available() else "absent",
                       detail="disponible" if word.word_available() else "absent : export DOCX seulement",
                       fix=None if word.word_available() else "Ouvrir le DOCX et l'enregistrer en PDF."))

    configs = desktop_config_candidates()
    configured = [p for p in configs if SERVER_NAME in _read_json(p).get("mcpServers", {})]
    add(ComponentCheck(component="Claude Desktop", status="ok" if configured else "attention",
                       detail=f"serveur déclaré dans {configured[0]}" if configured else
                       ("configuration trouvée mais serveur non déclaré" if configs else "configuration introuvable"),
                       fix=None if configured else "uv run academic-writer setup-desktop --apply"))

    backups = list_backups(settings).backups
    if backups:
        last = datetime.fromisoformat(backups[0].created_at)
        age = (datetime.now(UTC) - last).days
        add(ComponentCheck(component="Sauvegardes", status="ok" if age <= 14 else "attention",
                           detail=f"{len(backups)} sauvegarde(s), dernière il y a {age} jour(s)",
                           fix=None if age <= 14 else "uv run academic-writer backup"))
    else:
        add(ComponentCheck(component="Sauvegardes", status="attention", detail="aucune sauvegarde",
                           fix="uv run academic-writer backup"))

    ready = all(c.status == "ok" for c in checks if c.required)
    problems = [c.component for c in checks if c.status in ("erreur", "attention")]
    summary = ("Prêt." if ready else "Composant indispensable en erreur.") + (
        f" À regarder : {', '.join(problems)}." if problems else "")
    return Diagnosis(version=__version__, generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
                     ready=ready, summary=summary, checks=checks)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# --- sauvegarde ----------------------------------------------------------------------------------

def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def create_backup(settings: Settings, db: Database, complete: bool = True, label: str = "manuelle") -> BackupInfo:
    """Base seule (copie SQLite cohérente) ou sauvegarde complète (.zip : base + dossiers des projets +
    configuration). Les clés API ne sont jamais incluses (coffre Windows)."""
    snapshot = db.backup(label)
    if not complete:
        return _info(snapshot, "base")
    archive = settings.backups_dir / f"academic-writer-complet-{_stamp()}-{label}.zip"
    manifest = {"app": "academic-writer", "version": __version__, "schema": db.schema_version(),
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "data_dir": str(settings.data_dir)}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.writestr(_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.write(snapshot, _DB_NAME)
        if settings.projects_dir.exists():
            for path in sorted(settings.projects_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, "projects/" + path.relative_to(settings.projects_dir).as_posix())
        config = _config_file()
        if config and config.exists():
            zf.write(config, "config.toml")
    snapshot.unlink(missing_ok=True)
    return _info(archive, "complete")


def _config_file() -> Path | None:
    from academic_writer.core.config import config_file_path

    return config_file_path()


def _info(path: Path, kind: str) -> BackupInfo:
    created = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")
    return BackupInfo(path=str(path), kind=kind, size_mb=round(path.stat().st_size / 1024 ** 2, 2),  # type: ignore[arg-type]
                      created_at=created)


def list_backups(settings: Settings) -> BackupList:
    folder = settings.backups_dir
    items: list[BackupInfo] = []
    if folder.exists():
        for path in folder.iterdir():
            if path.suffix == ".zip" and path.name.startswith("academic-writer-complet-"):
                items.append(_info(path, "complete"))
            elif path.suffix == ".db" and path.name.startswith("academic_writer-"):
                items.append(_info(path, "base"))
    items.sort(key=lambda b: b.created_at, reverse=True)
    return BackupList(folder=str(folder), backups=items)


def _force_remove(function, path, _exc) -> None:
    import stat

    os.chmod(path, stat.S_IWRITE)
    function(path)


def restore_backup(settings: Settings, db: Database, archive: Path) -> RestoreResult:
    """Restaure une sauvegarde COMPLÈTE (.zip). Fermer Claude Desktop / Claude Code avant."""
    archive = archive.resolve()
    if not zipfile.is_zipfile(archive):
        raise ValidationFailed("Ce fichier n'est pas une sauvegarde complète (.zip).")
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if _MANIFEST not in names or _DB_NAME not in names:
            raise ValidationFailed("Archive incomplète : manifest.json ou base absents.")
        manifest = json.loads(zf.read(_MANIFEST))
        if manifest.get("app") != "academic-writer":
            raise ValidationFailed("Cette archive n'est pas une sauvegarde d'Academic Writer.")
        for name in names:  # protection contre les chemins sortants (zip-slip)
            target = Path(name)
            if target.is_absolute() or ".." in target.parts:
                raise ValidationFailed(f"Chemin interdit dans l'archive : {name}")
        with tempfile.TemporaryDirectory(dir=settings.data_dir) as temp:
            staging = Path(temp)
            zf.extractall(staging)
            restored_db = staging / _DB_NAME
            conn = sqlite3.connect(restored_db)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValidationFailed("La base contenue dans l'archive est endommagée.")
                schema = conn.execute("PRAGMA user_version").fetchone()[0]
            except sqlite3.DatabaseError as exc:
                raise ValidationFailed(f"La base contenue dans l'archive est illisible : {exc}") from exc
            finally:
                conn.close()
            if schema > db.schema_version():
                raise ValidationFailed(f"Sauvegarde créée par une version plus récente (schéma v{schema}) : "
                                       "mettez d'abord Academic Writer à jour.")
            safety = create_backup(settings, db, complete=True, label="avant-restauration")
            for suffix in ("-wal", "-shm"):
                Path(str(settings.db_path) + suffix).unlink(missing_ok=True)
            shutil.copyfile(restored_db, settings.db_path)
            if settings.projects_dir.exists():
                shutil.rmtree(settings.projects_dir, onexc=_force_remove)  # originaux en lecture seule
            restored_projects = staging / "projects"
            if restored_projects.exists():
                shutil.copytree(restored_projects, settings.projects_dir)
            else:
                settings.projects_dir.mkdir(parents=True)
    migrated = db.initialize()  # migrations éventuelles d'une sauvegarde plus ancienne
    messages = [f"Sauvegarde de sécurité de l'état précédent : {safety.path}"]
    if migrated:
        messages.append(f"Base mise à niveau (migrations {', '.join(map(str, migrated))}).")
    projects = sum(1 for p in settings.projects_dir.iterdir() if p.is_dir())
    return RestoreResult(restored_from=str(archive), safety_backup=safety.path, projects_restored=projects,
                         schema_version=db.schema_version(), messages=messages)


# --- clients MCP ----------------------------------------------------------------------------------

def _same_entry(current: dict | None, entry: dict) -> bool:
    """Chemins comparés sans tenir compte de la casse sous Windows (« uv.EXE » = « uv.exe »)."""
    if not isinstance(current, dict):
        return False
    norm = os.path.normcase
    return (norm(str(current.get("command", ""))) == norm(entry["command"])
            and [norm(str(a)) for a in current.get("args", [])] == [norm(a) for a in entry["args"]])


def setup_desktop(apply: bool = False, config_path: Path | None = None) -> ClientSetup:
    entry = server_entry()
    candidates = [config_path] if config_path else desktop_config_candidates()
    if not candidates:
        return ClientSetup(client="Claude Desktop", config_path=None, status="introuvable", entry=entry,
                           detail="Configuration de Claude Desktop introuvable : lancez Claude Desktop une fois, "
                                  "ou ouvrez Paramètres > Développeur > Modifier la configuration.")
    path = candidates[0]
    data = _read_json(path) if path.exists() else {}
    servers = data.setdefault("mcpServers", {})
    current = servers.get(SERVER_NAME)
    if _same_entry(current, entry):
        return ClientSetup(client="Claude Desktop", config_path=str(path), status="deja_configure", entry=entry,
                           detail="Le serveur est déjà déclaré correctement.")
    if not apply:
        return ClientSetup(client="Claude Desktop", config_path=str(path),
                           status="different" if current else "a_configurer", entry=entry,
                           detail=("Déclaration existante différente : relancer avec --apply pour la remplacer."
                                   if current else "Relancer avec --apply pour ajouter le serveur.")
                           + " Les autres serveurs sont conservés ; une copie de sauvegarde est faite.")
    backup = path.with_name(f"{path.name}.bak-{_stamp()}")
    if path.exists():
        shutil.copyfile(path, backup)
    servers[SERVER_NAME] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return ClientSetup(client="Claude Desktop", config_path=str(path), status="configure", entry=entry,
                       backup_path=str(backup) if path.exists() else None,
                       detail="Serveur déclaré. Quittez complètement Claude Desktop (icône de la barre des tâches) "
                              "puis relancez-le.")


def claude_code_command() -> str:
    entry = server_entry()
    args = " ".join(f'"{a}"' if " " in a else a for a in entry["args"])
    return f'claude mcp add --scope user {SERVER_NAME} -- "{entry["command"]}" {args}'
