"""Gestion des projets."""

from __future__ import annotations

import logging
import sqlite3

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.history import record_event
from academic_writer.core.models import (
    DocumentType,
    Language,
    Project,
    ProjectStatus,
    new_id,
    utc_now,
)
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.projects")

_MAX_NAME = 200
_MAX_DESCRIPTION = 5000
_MAX_DISCIPLINE = 200


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValidationFailed("Le nom du projet est obligatoire.")
    if len(name) > _MAX_NAME:
        raise ValidationFailed(f"Nom trop long (maximum {_MAX_NAME} caractères).")
    return name


def _clean_optional(value: str | None, limit: int, label: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > limit:
        raise ValidationFailed(f"{label} trop long(ue) (maximum {limit} caractères).")
    return value or None


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        document_type=DocumentType(row["document_type"]),
        language=Language(row["language"]),
        discipline=row["discipline"],
        status=ProjectStatus(row["status"]),
        domain_id=row["domain_id"],
        domain_confirmed_at=row["domain_confirmed_at"],
        convention=row["convention"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ProjectService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def create(
        self,
        name: str,
        document_type: DocumentType,
        language: Language,
        description: str = "",
        discipline: str | None = None,
    ) -> Project:
        name = _clean_name(name)
        description = _clean_optional(description, _MAX_DESCRIPTION, "Description") or ""
        discipline = _clean_optional(discipline, _MAX_DISCIPLINE, "Discipline")
        document_type = DocumentType(document_type)
        language = Language(language)
        project_id = new_id()
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, description, document_type, language, discipline, "
                "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name, description, document_type.value, language.value, discipline,
                 ProjectStatus.ACTIVE.value, now, now),
            )
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id,
                         action="created", details={"document_type": document_type.value, "language": language.value})
        (self.settings.projects_dir / project_id / "originals").mkdir(parents=True, exist_ok=True)
        logger.info("Projet créé : %s", project_id)
        return self.get(project_id)

    def get(self, project_id: str) -> Project:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Projet introuvable : {project_id}")
        return _row_to_project(row)

    def list(self, include_archived: bool = False) -> list[Project]:
        query = "SELECT * FROM projects"
        params: tuple = ()
        if not include_archived:
            query += " WHERE status = ?"
            params = (ProjectStatus.ACTIVE.value,)
        query += " ORDER BY updated_at DESC"
        with self.db.read() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_project(r) for r in rows]

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        document_type: DocumentType | None = None,
        language: Language | None = None,
        discipline: str | None = None,
    ) -> Project:
        project = self.get(project_id)
        if project.status is ProjectStatus.ARCHIVED:
            raise ValidationFailed("Projet archivé : modification impossible.")
        changes: dict[str, object] = {}
        if name is not None:
            changes["name"] = _clean_name(name)
        if description is not None:
            changes["description"] = _clean_optional(description, _MAX_DESCRIPTION, "Description") or ""
        if document_type is not None:
            changes["document_type"] = DocumentType(document_type).value
        if language is not None:
            changes["language"] = Language(language).value
        if discipline is not None:
            changes["discipline"] = _clean_optional(discipline, _MAX_DISCIPLINE, "Discipline")
        if not changes:
            raise ValidationFailed("Aucune modification demandée.")
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)  # colonnes fixes ci-dessus
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE projects SET {assignments} WHERE id = ?", (*changes.values(), project_id))
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id,
                         action="updated", details={"fields": sorted(k for k in changes if k != "updated_at")})
        logger.info("Projet modifié : %s", project_id)
        return self.get(project_id)

    def set_domain(self, project_id: str, domain_id: str, convention: str | None) -> Project:
        """Enregistre le domaine choisi par l'utilisateur (et éventuellement la convention)."""
        project = self.get(project_id)
        if project.status is ProjectStatus.ARCHIVED:
            raise ValidationFailed("Projet archivé : modification impossible.")
        if convention is not None and convention not in ("ru", "fr", "intl"):
            raise ValidationFailed("Convention inconnue : utilisez ru, fr ou intl.")
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET domain_id = ?, domain_confirmed_at = ?, convention = coalesce(?, convention), "
                "updated_at = ? WHERE id = ?",
                (domain_id, now, convention, now, project_id),
            )
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id,
                         action="domain_set", details={"domain_id": domain_id, "convention": convention})
        logger.info("Domaine du projet %s : %s", project_id, domain_id)
        return self.get(project_id)

    def archive(self, project_id: str) -> Project:
        project = self.get(project_id)
        if project.status is ProjectStatus.ARCHIVED:
            return project
        with self.db.transaction() as conn:
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                         (ProjectStatus.ARCHIVED.value, utc_now(), project_id))
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id, action="archived")
        logger.info("Projet archivé : %s", project_id)
        return self.get(project_id)
