"""Outil MCP : gestionnaire central des logiciels scientifiques et techniques."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.software import SoftwareReport, detect
from academic_writer.server.services import user_errors

Category = Literal["math", "cad", "simulation", "automation", "statistics", "chemistry_biology", "data", "civil",
                   "office"]


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Logiciels du poste",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True))
    def detect_software(
        category: Annotated[Category | None, Field(description="Limiter à une catégorie.")] = None,
        only_detected: Annotated[bool, Field(description="Seulement les logiciels présents.")] = False,
    ) -> SoftwareReport:
        """Détecte les logiciels réellement installés (registre Windows, PATH, serveurs MCP de Claude Desktop) et
        indique licence, coût, méthodes d'intégration officielles et statut réel : native (Academic Writer exécute),
        mcp_server (un autre serveur MCP pilote le logiciel), none (conseils seulement — ne jamais prétendre avoir
        calculé dans ce logiciel). Règles de sécurité imposées pour les automates industriels."""
        with user_errors():
            try:
                return detect(category, only_detected=only_detected)
            except ValueError as exc:
                raise ValidationFailed(str(exc)) from exc
