"""Outils MCP : état des fournisseurs d'IA et consentement au traitement externe."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from academic_writer.providers.base import GenerationResult
from academic_writer.providers.manager import DATA_NOTICE, AIStatus, ConsentInfo, EngineChoice
from academic_writer.server.services import get_services, user_errors


class ConsentResult(BaseModel):
    project_id: str
    consent: ConsentInfo | None
    message: str
    data_notice: str = DATA_NOTICE


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="État des fournisseurs d'IA",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True))
    def get_ai_status(project_id: Annotated[str | None, Field(description="Projet (pour voir son consentement).")] = None) -> AIStatus:
        """Mode local/connecté, clés configurées (jamais affichées), consentement du projet, tokens consommés
        ce mois, et étapes restantes pour activer un fournisseur d'IA."""
        with user_errors():
            return get_services().ai.status(project_id)

    @mcp.tool(title="Consentement au traitement externe",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    def set_project_ai_consent(
        project_id: str,
        granted: Annotated[bool, Field(description="true pour accorder, false pour révoquer.")],
        user_confirmation: Annotated[str, Field(
            description="Pour accorder : phrase tapée PAR L'UTILISATEUR, exactement « J'autorise l'envoi externe ». "
                        "Ne jamais la remplir à sa place.")] = "",
        scope: Literal["all", "anthropic", "openai"] = "all",
    ) -> ConsentResult:
        """Accorde ou révoque l'autorisation d'envoyer des extraits de ce projet à un fournisseur d'IA externe.

        N'appeler pour accorder QUE si l'utilisateur l'a demandé explicitement et a tapé lui-même la phrase
        de confirmation, après lui avoir expliqué quelles données partent et vers qui.
        """
        with user_errors():
            consent = get_services().ai.set_consent(project_id, granted, scope, user_confirmation)
            message = (f"Consentement accordé (portée : {scope})." if consent
                       else "Consentement révoqué : plus aucun envoi externe pour ce projet.")
            return ConsentResult(project_id=project_id, consent=consent, message=message)

    @mcp.tool(title="Tester un fournisseur d'IA",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True, idempotent_hint=False))
    def test_ai_provider(provider: Literal["anthropic", "openai", "ollama"] | None = None) -> GenerationResult:
        """Vérifie un moteur par un très court appel (« Réponds OK »), sans aucune donnée de projet.
        anthropic/openai : consomme quelques tokens et nécessite le mode connecté ; ollama : local et gratuit."""
        with user_errors():
            return get_services().ai.test_provider(provider)

    @mcp.tool(title="Moteur de rédaction",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True))
    def get_writing_engine(
        project_id: Annotated[str | None, Field(description="Projet (le consentement dépend du projet).")] = None,
        engine: Annotated[Literal["auto", "assistant", "ollama", "anthropic", "openai"] | None, Field(
            description="Moteur souhaité ; vide = réglage de la configuration (auto par défaut).")] = None,
    ) -> EngineChoice:
        """Indique quel moteur rédigera (fournisseur cloud autorisé, modèle local Ollama ou assistant MCP),
        pourquoi, et l'état de chaque moteur. En mode « assistant », c'est l'assistant qui rédige à partir
        du dossier préparé par le serveur."""
        with user_errors():
            return get_services().ai.resolve_engine(project_id, engine)
