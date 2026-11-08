"""Outils MCP : gestion des projets."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.models import DocumentType, Language, Project, ProjectList
from academic_writer.server.services import get_services, user_errors

ProjectId = Annotated[str, Field(description="Identifiant du projet (32 caractères hexadécimaux).")]


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Créer un projet",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                    open_world_hint=False),
    )
    def create_project(
        name: Annotated[str, Field(description="Nom du projet (ex. « Mémoire Master — maintenance prédictive »).")],
        document_type: Annotated[DocumentType, Field(description="Type de document à produire.")],
        language: Annotated[Language, Field(description="Langue principale du document : fr, ru ou en.")],
        description: Annotated[str, Field(description="Description libre du projet.")] = "",
        discipline: Annotated[str | None, Field(description="Discipline (ex. « génie mécanique »), si connue.")] = None,
    ) -> Project:
        """Crée un nouveau projet de rédaction (première étape du workflow)."""
        with user_errors():
            return get_services().projects.create(name, document_type, language, description, discipline)

    @mcp.tool(title="Consulter un projet", annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def get_project(project_id: ProjectId) -> Project:
        """Renvoie les informations d'un projet."""
        with user_errors():
            return get_services().projects.get(project_id)

    @mcp.tool(title="Lister les projets", annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def list_projects(
        include_archived: Annotated[bool, Field(description="Inclure les projets archivés.")] = False,
    ) -> ProjectList:
        """Liste les projets, du plus récemment modifié au plus ancien."""
        with user_errors():
            projects = get_services().projects.list(include_archived=include_archived)
            return ProjectList(count=len(projects), projects=projects)

    @mcp.tool(
        title="Modifier un projet",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                    open_world_hint=False),
    )
    def update_project(
        project_id: ProjectId,
        name: str | None = None,
        description: str | None = None,
        document_type: DocumentType | None = None,
        language: Language | None = None,
        discipline: str | None = None,
    ) -> Project:
        """Modifie les champs indiqués d'un projet actif (les champs omis restent inchangés)."""
        with user_errors():
            return get_services().projects.update(
                project_id, name=name, description=description, document_type=document_type,
                language=language, discipline=discipline,
            )

    @mcp.tool(
        title="Archiver un projet",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                    open_world_hint=False),
    )
    def archive_project(project_id: ProjectId) -> Project:
        """Archive un projet : il devient non modifiable mais rien n'est supprimé.

        Demander la confirmation de l'utilisateur avant d'appeler cet outil.
        """
        with user_errors():
            return get_services().projects.archive(project_id)
