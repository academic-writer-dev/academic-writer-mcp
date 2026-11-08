"""Outils MCP : vérification linguistique, correction, style, traduction."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.editing import CorrectionResult, LanguageCheck, StyleResult, TranslationResult
from academic_writer.server.services import get_services, user_errors
from academic_writer.writing.languagetool import LTStatus

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_GENERATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)
Engine = Literal["auto", "assistant", "ollama", "anthropic", "openai"]
Lang = Literal["fr", "ru", "en"]


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Vérifier la langue", annotations=_READ)
    def check_language(
        project_id: str,
        section_id: str | None = None,
        revision_id: str | None = None,
        text: Annotated[str | None, Field(description="Texte libre à vérifier (au lieu d'une section).")] = None,
        language: Lang | None = None,
    ) -> LanguageCheck:
        """Vérifie orthographe, grammaire et ponctuation avec LanguageTool LOCAL (démarré automatiquement) et
        analyse le style (phrases longues, répétitions, formulations vagues). Ne modifie rien."""
        with user_errors():
            return get_services().editing.check_language(project_id, section_id, revision_id, text, language)

    @mcp.tool(title="Corriger une section", annotations=_GENERATE)
    def correct_academic_section(
        project_id: str,
        section_id: str,
        revision_id: Annotated[str | None, Field(description="Version à corriger ; par défaut l'acceptée ou la dernière.")] = None,
        use_ai: Annotated[bool, Field(description="Compléter par l'IA (accords, cas subtils) si un moteur est disponible.")] = True,
        engine: Engine | None = None,
    ) -> CorrectionResult:
        """Propose une version corrigée : corrections LanguageTool sûres (termes du projet et formules protégés),
        puis IA. Une correction IA qui modifie un chiffre ou ajoute un nom propre est écartée. Chaque correction
        est expliquée. Le résultat est une révision PROPOSÉE."""
        with user_errors():
            return get_services().editing.correct_section(project_id, section_id, revision_id, use_ai, engine)

    @mcp.tool(title="Améliorer le style", annotations=_GENERATE)
    def improve_academic_style(
        project_id: str,
        section_id: str,
        revision_id: str | None = None,
        rewrite: Annotated[bool, Field(description="Proposer aussi une réécriture corrigeant les problèmes relevés.")] = False,
        engine: Engine | None = None,
    ) -> StyleResult:
        """Analyse le style académique (phrases trop longues, répétitions, formulations vagues, première personne,
        règles de style LanguageTool) et, sur demande, propose une réécriture contrôlée (fidélité vérifiée)."""
        with user_errors():
            return get_services().editing.improve_style(project_id, section_id, revision_id, rewrite, engine)

    @mcp.tool(title="Traduire une section", annotations=_GENERATE)
    def translate_academic_section(
        project_id: str,
        section_id: str,
        target_language: Lang,
        revision_id: str | None = None,
        engine: Engine | None = None,
    ) -> TranslationResult:
        """Traduit une section (fr/ru/en) avec le glossaire du profil disciplinaire ; vérifie que les chiffres sont
        identiques et que les termes clés sont rendus par leur équivalent. Révision PROPOSÉE dans la langue cible,
        qui ne remplace pas la version validée dans la langue du projet."""
        with user_errors():
            return get_services().editing.translate_section(project_id, section_id, target_language, revision_id, engine)

    @mcp.tool(title="Serveur LanguageTool local",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    def manage_languagetool(action: Literal["status", "start", "stop"] = "status") -> LTStatus:
        """État, démarrage ou arrêt du serveur LanguageTool LOCAL (aucun texte n'est envoyé à l'extérieur)."""
        with user_errors():
            server = get_services().editing.languagetool
            if action == "start":
                try:
                    server.start()
                except Exception as exc:  # message clair pour l'assistant
                    from academic_writer.core.errors import ValidationFailed
                    raise ValidationFailed(str(exc)) from exc
            elif action == "stop":
                server.stop()
            return server.status()
