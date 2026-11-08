"""Outils MCP : gestion documentaire (import et métadonnées)."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.models import DocumentList, DocumentMetadata, DocumentRole, ImportResult
from academic_writer.server.services import get_services, user_errors

ProjectId = Annotated[str, Field(description="Identifiant du projet.")]
DocumentId = Annotated[str, Field(description="Identifiant du document.")]


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Importer un document",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                    open_world_hint=False),
    )
    def import_document(
        project_id: ProjectId,
        file_path: Annotated[str, Field(description="Chemin absolu du fichier sur l'ordinateur de l'utilisateur "
                                                    "(ex. D:\\Cours\\consignes_TP3.pdf).")],
        role: Annotated[DocumentRole, Field(description="Rôle du document : instructions (consignes), source, "
                                                        "draft (document de l'utilisateur), data, template, other.")]
        = DocumentRole.SOURCE,
        title: Annotated[str | None, Field(description="Titre lisible facultatif.")] = None,
    ) -> ImportResult:
        """Importe un fichier (DOCX, PDF, TXT, MD, XLSX, PPTX) dans un projet.

        Le fichier original n'est jamais modifié : une copie vérifiée (SHA-256) est
        stockée en lecture seule. Les fichiers suspects (macros, contenu ne correspondant
        pas à l'extension, archives anormales) sont refusés. Un fichier identique déjà
        importé n'est pas dupliqué.
        """
        with user_errors():
            return get_services().documents.import_document(project_id, file_path, role, title)

    @mcp.tool(title="Lister les documents", annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def list_documents(
        project_id: ProjectId,
        role: Annotated[DocumentRole | None, Field(description="Filtrer par rôle (facultatif).")] = None,
    ) -> DocumentList:
        """Liste les documents importés dans un projet."""
        with user_errors():
            documents = get_services().documents.list(project_id, role)
            return DocumentList(project_id=project_id, count=len(documents), documents=documents)

    @mcp.tool(title="Métadonnées d'un document",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def get_document_metadata(document_id: DocumentId) -> DocumentMetadata:
        """Renvoie les métadonnées d'un document importé et vérifie l'intégrité de sa copie protégée."""
        with user_errors():
            return get_services().documents.metadata(document_id)
