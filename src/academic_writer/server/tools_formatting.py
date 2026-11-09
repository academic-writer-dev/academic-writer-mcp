"""Outils MCP : mise en forme et export (DOCX / PDF)."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from academic_writer.core.formatting import ExportResult, PresetList
from academic_writer.formatting.checker import FormattingApplied, FormattingCheck
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Gabarits de mise en forme", annotations=_READ)
    def list_format_presets(project_id: str | None = None) -> PresetList:
        """Gabarits disponibles (ГОСТ 7.32-2017 14 / 12 pt, usage universitaire francophone, APA 7, IEEE) avec
        police, interligne, marges, retraits, légendes ; gabarit par défaut du projet ; champs de page de titre ;
        disponibilité de Microsoft Word (export PDF)."""
        with user_errors():
            return get_services().formatting.list_presets(project_id)

    @mcp.tool(title="Exporter le document", annotations=_WRITE)
    def export_document(project_id: str, output_format: str = "docx", preset: str | None = None,
                        citation_style: str | None = None, title_page: dict[str, str] | None = None,
                        include_drafts: bool = False) -> ExportResult:
        """Produit le document final (DOCX, ou PDF + DOCX via Microsoft Word) à partir des sections ACCEPTÉES du
        plan : mise en forme du gabarit, titres numérotés, sommaire, citations [@clé] rendues dans le style
        (gost, apa, ieee, chicago, vancouver, harvard, iso690), bibliographie. title_page : organization, ministry, faculty,
        department, document_kind, discipline, title, variant, author, group, supervisor, supervisor_title, city,
        year — UNIQUEMENT des informations données par l'utilisateur (mémorisées pour la suite ; champs manquants
        laissés en blanc). include_drafts=true reprend les brouillons non validés (signalés)."""
        with user_errors():
            return get_services().formatting.export(project_id, output_format, preset, citation_style, title_page,
                                                    include_drafts)

    @mcp.tool(title="Contrôler la mise en forme", annotations=_READ)
    def check_formatting(document_id: str, preset: str | None = None) -> FormattingCheck:
        """Contrôle un fichier Word (.docx) importé par rapport à un gabarit (par défaut celui du projet) : police,
        taille, interligne, retrait, alignement, marges, numérotation des pages, point final des titres."""
        with user_errors():
            return get_services().formatting.check(document_id, preset)

    @mcp.tool(title="Appliquer une mise en forme", annotations=_WRITE)
    def apply_formatting(document_id: str, preset: str | None = None, pdf: bool = False) -> FormattingApplied:
        """Crée une COPIE mise en forme d'un .docx importé (marges, police, taille, interligne, retraits, numéros de
        page) dans le dossier exports ; l'original n'est jamais modifié. Texte inchangé. pdf=true : PDF via Word."""
        with user_errors():
            return get_services().formatting.apply(document_id, preset, pdf)
