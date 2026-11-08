"""Assemblage des services de l'application (injection de dépendances simple)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError

from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.domains import DomainService
from academic_writer.core.errors import AcademicWriterError
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.projects import ProjectService
from academic_writer.storage.db import Database


@dataclass
class Services:
    settings: Settings
    db: Database
    projects: ProjectService
    documents: DocumentService
    extraction: ExtractionService
    domains: DomainService


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or Settings()
    settings.ensure_dirs()
    db = Database(settings.db_path, settings.backups_dir)
    db.initialize()
    projects = ProjectService(db, settings)
    documents = DocumentService(db, settings, projects)
    extraction = ExtractionService(db, settings, projects, documents)
    domains = DomainService(db, settings, projects, extraction)
    return Services(settings=settings, db=db, projects=projects, documents=documents, extraction=extraction,
                    domains=domains)


_services: Services | None = None
_lock = threading.Lock()


def get_services() -> Services:
    """Services partagés, créés au premier appel."""
    global _services
    if _services is None:
        with _lock:
            if _services is None:
                _services = build_services()
    return _services


def set_services(services: Services | None) -> None:
    """Remplace les services (tests) ; ``None`` force une reconstruction au prochain appel."""
    global _services
    with _lock:
        _services = services


@contextmanager
def user_errors() -> Iterator[None]:
    """Convertit les erreurs métier en ToolError : le message est transmis à l'assistant.

    Les autres exceptions restent masquées par le SDK (« Error executing tool ... »)
    et sont journalisées côté serveur.
    """
    try:
        yield
    except AcademicWriterError as exc:
        raise ToolError(str(exc)) from exc
