"""Gestion des documents d'un projet.

Règle fondamentale : l'original n'est jamais modifié.
- Le fichier source de l'utilisateur est seulement lu.
- Une copie est placée dans ``<data_dir>/projects/<projet>/originals/<id><ext>``,
  vérifiée par SHA-256 puis mise en lecture seule.
- Toute modification future produira une révision distincte.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import stat
from pathlib import Path

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError, SecurityViolation, ValidationFailed
from academic_writer.core.history import record_event
from academic_writer.core.models import (
    Document,
    DocumentMetadata,
    DocumentRole,
    ImportResult,
    ProjectStatus,
    new_id,
    utc_now,
)
from academic_writer.core.projects import ProjectService
from academic_writer.security.files import inspect_file, sha256_file
from academic_writer.security.paths import ensure_outside, ensure_within, resolve_user_file, safe_child
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.documents")

_MAX_TITLE = 300


def _row_to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        project_id=row["project_id"],
        role=DocumentRole(row["role"]),
        title=row["title"],
        original_filename=row["original_filename"],
        extension=row["extension"],
        mime_type=row["mime_type"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        stored_path=row["stored_path"],
        security_notes=json.loads(row["security_notes"]),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _make_writable(path: Path) -> None:
    if path.exists():
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


class DocumentService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects

    # --- import ----------------------------------------------------------
    def import_document(
        self,
        project_id: str,
        file_path: str,
        role: DocumentRole = DocumentRole.SOURCE,
        title: str | None = None,
    ) -> ImportResult:
        project = self.projects.get(project_id)
        if project.status is ProjectStatus.ARCHIVED:
            raise ValidationFailed("Projet archivé : import impossible.")
        role = DocumentRole(role)
        if title is not None:
            title = title.strip() or None
            if title and len(title) > _MAX_TITLE:
                raise ValidationFailed(f"Titre trop long (maximum {_MAX_TITLE} caractères).")

        source = resolve_user_file(file_path)
        ensure_within(source, self.settings.allowed_import_dirs)
        ensure_outside(source, self.settings.data_dir,
                       "Import refusé : le fichier se trouve déjà dans le dossier de données d'Academic Writer.")
        inspection = inspect_file(source, self.settings)

        existing = self._find_by_hash(project_id, inspection.sha256)
        if existing is not None:
            return ImportResult(document=existing, duplicate=True,
                                message="Fichier identique déjà importé dans ce projet : aucune nouvelle copie créée.")

        document_id = new_id()
        originals = self.settings.projects_dir / project_id / "originals"
        originals.mkdir(parents=True, exist_ok=True)
        destination = safe_child(originals, f"{document_id}{inspection.extension}")
        partial = destination.with_name(destination.name + ".part")

        try:
            shutil.copyfile(source, partial)
            if sha256_file(partial) != inspection.sha256:
                raise SecurityViolation("Le fichier a changé pendant l'import : réessayez.")
            os.replace(partial, destination)
            os.chmod(destination, stat.S_IREAD)  # lecture seule
        except BaseException:
            _make_writable(partial)
            partial.unlink(missing_ok=True)
            raise

        stored_rel = destination.relative_to(self.settings.data_dir).as_posix()
        now = utc_now()
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT INTO documents (id, project_id, role, title, original_filename, source_path, "
                    "stored_path, extension, mime_type, size_bytes, sha256, security_notes, status, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (document_id, project_id, role.value, title, source.name, str(source), stored_rel,
                     inspection.extension, inspection.mime_type, inspection.size_bytes, inspection.sha256,
                     json.dumps(inspection.warnings, ensure_ascii=False), "imported", now, now),
                )
                conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
                record_event(conn, project_id=project_id, entity_type="document", entity_id=document_id,
                             action="imported",
                             details={"extension": inspection.extension, "size_bytes": inspection.size_bytes,
                                      "role": role.value, "warnings": len(inspection.warnings)})
        except sqlite3.IntegrityError:
            # Import concurrent du même fichier : on garde l'existant.
            _make_writable(destination)
            destination.unlink(missing_ok=True)
            existing = self._find_by_hash(project_id, inspection.sha256)
            if existing is None:
                raise
            return ImportResult(document=existing, duplicate=True,
                                message="Fichier identique déjà importé dans ce projet.")
        except BaseException:
            _make_writable(destination)
            destination.unlink(missing_ok=True)
            raise

        logger.info("Document importé : %s (%s, %d octets)", document_id, inspection.extension, inspection.size_bytes)
        message = "Document importé. L'original est conservé intact ; la copie de travail est en lecture seule."
        if inspection.warnings:
            message += " Avertissements de sécurité : " + " ".join(inspection.warnings)
        return ImportResult(document=self.get(document_id), duplicate=False, message=message)

    # --- lecture ---------------------------------------------------------
    def get(self, document_id: str) -> Document:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Document introuvable : {document_id}")
        return _row_to_document(row)

    def list(self, project_id: str, role: DocumentRole | None = None) -> list[Document]:
        self.projects.get(project_id)  # vérifie l'existence
        query = "SELECT * FROM documents WHERE project_id = ?"
        params: list[object] = [project_id]
        if role is not None:
            query += " AND role = ?"
            params.append(DocumentRole(role).value)
        query += " ORDER BY created_at"
        with self.db.read() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_document(r) for r in rows]

    def stored_file(self, document: Document) -> Path:
        return safe_child(self.settings.data_dir, *document.stored_path.split("/"))

    def metadata(self, document_id: str) -> DocumentMetadata:
        document = self.get(document_id)
        path = self.stored_file(document)
        if not path.exists():
            return DocumentMetadata(document=document, integrity_ok=False, original_protected=False)
        integrity_ok = sha256_file(path) == document.sha256
        protected = not (path.stat().st_mode & stat.S_IWRITE)
        if not integrity_ok:
            logger.warning("Intégrité compromise pour le document %s", document_id)
        return DocumentMetadata(document=document, integrity_ok=integrity_ok, original_protected=protected)

    def _find_by_hash(self, project_id: str, sha256: str) -> Document | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM documents WHERE project_id = ? AND sha256 = ?",
                               (project_id, sha256)).fetchone()
        return _row_to_document(row) if row else None
