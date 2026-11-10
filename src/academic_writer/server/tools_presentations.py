"""Outils MCP : présentations professionnelles (plan, génération PPTX, contrôles, export PDF / ODP, aperçus)."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.presentations.models import Deck, Occasion, PresentationPlan, PresentationResult
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Planifier une présentation", annotations=_READ)
    def plan_presentation(
        project_id: str,
        occasion: Occasion,
        duration_minutes: Annotated[int, Field(ge=3, le=90)] = 15,
        document_id: Annotated[str | None, Field(description="Partir d'un document importé (mémoire, PDF, DOCX) "
                                                             "au lieu de la rédaction du projet.")] = None,
        topic: Annotated[str | None, Field(description="Sujet seul (aucun contenu disponible).")] = None,
    ) -> PresentationPlan:
        """Structure de la présentation adaptée à l'occasion (exposé, soutenance Licence / Master / doctorat,
        présentation scientifique ou professionnelle) et à la durée, avec pour chaque diapositive son rôle, son
        temps de parole, la matière SOURCÉE à condenser (rédaction ou document) et les graphiques disponibles."""
        with user_errors():
            return get_services().presentations.plan(project_id, occasion, duration_minutes,
                                                     document_id=document_id, topic=topic)

    @mcp.tool(title="Créer une présentation", annotations=_WRITE)
    def create_presentation(
        project_id: str,
        deck: Annotated[Deck, Field(description=(
            "Diapositives : title, section, bullets (≤ 6 puces courtes), two_columns, chart (chart_id), image "
            "(image_path du projet + source), table, key_figures (2-4 valeurs sourcées), quote (+ source), process "
            "(étapes), conclusion, references (vide = bibliographie du projet), questions, agenda (plan numéroté), "
            "comparison (criteria + left_title / right_title), definitions (terms), timeline (events). notes = texte à "
            "dire ; transition ; jury_questions (question + éléments de réponse fondés sur le travail). Thèmes : "
            "academique, technique, sobre, clair, minimal_premium, corporate, scientifique, industriel, futuriste "
            "(sombre), editorial. Page de titre : seulement les informations fournies."))],
        duration_minutes: Annotated[int | None, Field(ge=3, le=90)] = None,
        export_pdf: bool = True,
        export_odp: bool = False,
        preview: Annotated[bool, Field(description="Aperçus PNG de chaque diapositive (PowerPoint) pour le "
                                                  "contrôle visuel.")] = True,
    ) -> PresentationResult:
        """Génère un PPTX modifiable au design soigné (16:9, hiérarchie, couleurs, graphiques, notes du présentateur),
        puis contrôle : texte trop long, chevauchements et éléments hors cadre, chiffres absents des sources du
        projet, figures sans source, notes manquantes, durée ; export PDF / ODP et aperçus par PowerPoint si installé. Montrer les erreurs à
        l'utilisateur ; inspecter les aperçus avant de déclarer la présentation prête."""
        with user_errors():
            return get_services().presentations.create(project_id, deck, duration_minutes=duration_minutes,
                                                       export_pdf=export_pdf, export_odp=export_odp, preview=preview)
