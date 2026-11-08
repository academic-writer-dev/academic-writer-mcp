"""Outils MCP : rédaction encadrée (exigences, plan, sections, révisions)."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.writing import OutlineOperation
from academic_writer.server.services import get_services, user_errors
from academic_writer.writing.models import (
    AssignmentAnalysis,
    DraftStatus,
    Outline,
    OutlineValidation,
    Requirement,
    RequirementList,
    SectionBrief,
    SectionRevision,
    WriteResult,
)

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
_GENERATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)
Engine = Literal["auto", "assistant", "ollama", "anthropic", "openai"]
Kind = Literal["task", "length", "structure", "format", "norm", "deadline", "variant", "data", "other"]


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Analyser les consignes", annotations=_WRITE)
    def analyze_assignment(
        project_id: str,
        document_id: Annotated[str | None, Field(description="Document précis ; par défaut tous les documents "
                                                             "de rôle « instructions ».")] = None,
    ) -> AssignmentAnalysis:
        """Extrait des consignes les exigences : tâches, variante, longueur, normes, échéances, mise en forme,
        sections imposées, données. Chaque exigence garde sa source (document, page). Ce sont des propositions :
        les faire confirmer ou rejeter par l'utilisateur."""
        with user_errors():
            return get_services().writing.analyze_assignment(project_id, document_id)

    @mcp.tool(title="Lister les exigences", annotations=_READ)
    def extract_requirements(
        project_id: str,
        kind: Kind | None = None,
        status: Literal["proposed", "confirmed", "rejected"] | None = None,
    ) -> RequirementList:
        """Liste les exigences du projet (extraites ou ajoutées par l'utilisateur), filtrables par type et statut."""
        with user_errors():
            return get_services().writing.list_requirements(project_id, kind, status)

    @mcp.tool(title="Gérer une exigence", annotations=_WRITE)
    def manage_requirement(
        project_id: str,
        action: Annotated[Literal["add", "confirm", "reject", "edit"], Field(
            description="add : nouvelle exigence (confirmée) ; confirm / reject / edit : exigence existante.")],
        requirement_id: str | None = None,
        text: str | None = None,
        kind: Kind | None = None,
        value: str | None = None,
    ) -> Requirement:
        """Ajoute, confirme, rejette ou corrige une exigence, selon la décision de l'utilisateur."""
        with user_errors():
            return get_services().writing.manage_requirement(project_id, action, requirement_id, text, kind, value)

    @mcp.tool(title="Créer le plan", annotations=_WRITE)
    def create_academic_outline(
        project_id: str,
        target_words: Annotated[int | None, Field(ge=100, le=200000, description="Longueur totale visée ; par défaut "
                                                  "déduite des exigences ou du type de document.")] = None,
    ) -> Outline:
        """Construit un projet de plan : structure de la convention et de la discipline, tâches des consignes en
        sous-sections, longueur répartie. Remplace le plan précédent (conservé dans l'historique). Statut « draft »."""
        with user_errors():
            return get_services().writing.create_outline(project_id, target_words)

    @mcp.tool(title="Consulter le plan", annotations=_READ)
    def get_academic_outline(project_id: str) -> Outline:
        """Renvoie le plan actuel du projet avec l'état de chaque section."""
        with user_errors():
            outline = get_services().writing.current_outline(project_id)
            if outline is None:
                from academic_writer.core.errors import ValidationFailed
                raise ValidationFailed("Aucun plan : utilisez create_academic_outline.")
            return outline

    @mcp.tool(title="Modifier le plan", annotations=_WRITE)
    def edit_academic_outline(
        outline_id: str,
        operations: Annotated[list[OutlineOperation], Field(description="Opérations appliquées dans l'ordre.")],
    ) -> Outline:
        """Ajoute, supprime, renomme, déplace ou règle des sections. Un plan modifié repasse à l'état « draft »
        et doit être revalidé. Une section déjà rédigée ne peut pas être supprimée."""
        with user_errors():
            return get_services().writing.edit_outline(outline_id, operations)

    @mcp.tool(title="Valider le plan", annotations=_WRITE)
    def validate_outline(
        outline_id: str,
        approve: Annotated[bool, Field(description="true UNIQUEMENT si l'utilisateur a explicitement approuvé le plan.")] = False,
        force: Annotated[bool, Field(description="Approuver malgré des exigences non couvertes (sur demande "
                                                 "explicite de l'utilisateur).")] = False,
    ) -> OutlineValidation:
        """Vérifie que le plan couvre toutes les exigences et les sections attendues ; l'approuve si l'utilisateur
        le demande. La rédaction n'est possible qu'avec un plan approuvé."""
        with user_errors():
            return get_services().writing.validate_outline(outline_id, approve, force)

    @mcp.tool(title="Rédiger une section", annotations=_GENERATE)
    def write_academic_section(
        project_id: str,
        section_id: str,
        instructions: Annotated[str | None, Field(description="Précisions de l'utilisateur pour cette section.")] = None,
        engine: Annotated[Engine | None, Field(description="Moteur ; par défaut celui de la configuration (auto).")] = None,
    ) -> WriteResult:
        """Rédige une section du plan approuvé. Avec un moteur serveur (modèle local ou cloud autorisé), renvoie
        une révision PROPOSÉE avec ses contrôles automatiques. Avec le moteur « assistant », renvoie le dossier
        (system_prompt + brief) : rédiger alors soi-même puis appeler save_section_draft."""
        with user_errors():
            return get_services().writing.write_section(project_id, section_id, instructions, engine)

    @mcp.tool(title="Réécrire une section", annotations=_GENERATE)
    def rewrite_academic_section(
        project_id: str,
        section_id: str,
        instructions: Annotated[str, Field(description="Ce qu'il faut changer (ton, concision, clarté, structure...).")],
        revision_id: Annotated[str | None, Field(description="Version de départ ; par défaut la version acceptée "
                                                             "ou la dernière proposée.")] = None,
        engine: Engine | None = None,
    ) -> WriteResult:
        """Propose une nouvelle version d'une section existante. Un contrôle de fidélité signale tout chiffre,
        terme technique ou nom propre modifié, supprimé ou ajouté."""
        with user_errors():
            return get_services().writing.rewrite_section(project_id, section_id, instructions, revision_id, engine)

    @mcp.tool(title="Dossier d'une section", annotations=_READ)
    def get_section_brief(project_id: str, section_id: str,
                          instructions: str | None = None) -> SectionBrief:
        """Renvoie le dossier de rédaction d'une section (règles, exigences, extraits de sources, terminologie)."""
        with user_errors():
            return get_services().writing.build_brief(project_id, section_id, instructions=instructions)

    @mcp.tool(title="Enregistrer un brouillon", annotations=_WRITE)
    def save_section_draft(
        project_id: str,
        section_id: str,
        text: Annotated[str, Field(description="Texte de la section en Markdown (sans son titre).")],
        kind: Literal["draft", "rewrite", "translation", "correction"] = "draft",
        parent_revision_id: str | None = None,
        note: str = "",
        language: Annotated[Literal["fr", "ru", "en"] | None, Field(
            description="Langue du texte (obligatoire pour une traduction) ; par défaut celle du projet.")] = None,
    ) -> SectionRevision:
        """Enregistre un texte rédigé par l'assistant (ou fourni par l'utilisateur) comme révision PROPOSÉE,
        après contrôles automatiques. Rien n'est écrasé."""
        with user_errors():
            return get_services().writing.save_section_draft(project_id, section_id, text, kind=kind,
                                                             parent_revision_id=parent_revision_id, note=note,
                                                             language=language)

    @mcp.tool(title="Consulter une révision", annotations=_READ)
    def get_section_revision(revision_id: str) -> SectionRevision:
        """Renvoie le texte d'une révision et ses contrôles."""
        with user_errors():
            return get_services().writing.get_revision(revision_id)

    @mcp.tool(title="Accepter ou refuser une révision", annotations=_WRITE)
    def review_revision(
        revision_id: str,
        decision: Annotated[Literal["accept", "reject"], Field(description="Décision DE L'UTILISATEUR.")],
        note: str = "",
    ) -> SectionRevision:
        """Applique la décision de l'utilisateur. Accepter remplace la version acceptée précédente (conservée dans
        l'historique) et marque la section comme validée."""
        with user_errors():
            return get_services().writing.review_revision(revision_id, decision, note)

    @mcp.tool(title="Avancement de la rédaction", annotations=_READ)
    def get_draft_status(project_id: str) -> DraftStatus:
        """État de chaque section du plan : planifiée, rédigée, validée ; mots acceptés ; révisions en attente."""
        with user_errors():
            return get_services().writing.draft_status(project_id)
