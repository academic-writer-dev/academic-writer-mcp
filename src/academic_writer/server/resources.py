"""Ressources MCP (lecture seule, format JSON)."""

from __future__ import annotations

import json

from mcp.server import MCPServer

from academic_writer.core.models import DOCUMENT_TYPE_LABELS, LANGUAGE_LABELS
from academic_writer.server.services import get_services


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def register(mcp: MCPServer) -> None:
    @mcp.resource("academic-writer://projects", mime_type="application/json", title="Projets")
    def projects_resource() -> str:
        """Liste des projets actifs."""
        projects = get_services().projects.list()
        return _json([p.model_dump(mode="json") for p in projects])

    @mcp.resource("academic-writer://projects/{project_id}", mime_type="application/json", title="Projet")
    def project_resource(project_id: str) -> str:
        """Détail d'un projet et de ses documents."""
        services = get_services()
        project = services.projects.get(project_id)
        documents = services.documents.list(project_id)
        return _json({
            "project": project.model_dump(mode="json"),
            "documents": [d.model_dump(mode="json") for d in documents],
        })

    @mcp.resource("academic-writer://document-types", mime_type="application/json", title="Types de documents")
    def document_types_resource() -> str:
        """Types de documents pris en charge (code → libellé)."""
        return _json({t.value: label for t, label in DOCUMENT_TYPE_LABELS.items()})

    @mcp.resource("academic-writer://languages", mime_type="application/json", title="Langues")
    def languages_resource() -> str:
        """Langues prises en charge (code → libellé)."""
        return _json({lang.value: label for lang, label in LANGUAGE_LABELS.items()})
