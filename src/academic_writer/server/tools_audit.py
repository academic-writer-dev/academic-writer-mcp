"""Outils MCP : audit documentaire et indices de rédaction par IA (indices, jamais des preuves)."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from academic_writer.ai_detection.stylometry import StyleAnalysis
from academic_writer.core.audit import AIAssessment, IntegrityReport
from academic_writer.forensics.models import Comment, MetadataReport, ProvenanceReport, TrackedChanges
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)


class RevisionHistory(BaseModel):
    document_id: str
    editing_sessions: int | None
    editing_time_minutes: str | None
    revision_number: str | None
    tracked_changes: TrackedChanges | None
    comments: list[Comment]
    notice: str = Field(default="Historique conservé par le fichier lui-même ; il peut être incomplet ou effacé.")


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Indices de rédaction par IA", annotations=_READ)
    def detect_ai_indicators(document_id: str) -> AIAssessment:
        """Analyse complète d'un document : style, métadonnées, historique, provenance, intégrité. Conclusion prudente :
        « indéterminée » par défaut ; une autre catégorie seulement si une déclaration technique explicite existe
        (C2PA, IPTC, outil nommé). Jamais de pourcentage. Indices pour un examen humain, jamais des preuves ;
        aucune décision ne doit reposer sur ce seul résultat."""
        with user_errors():
            return get_services().audit.assess(document_id)

    @mcp.tool(title="Analyser le style d'écriture", annotations=_READ)
    def analyze_writing_patterns(document_id: str) -> StyleAnalysis:
        """Indices stylistiques (fr/ru/en) : régularité des phrases, formules génériques, transitions systématiques,
        paragraphes uniformes, listes étiquetées, ruptures de style entre sections. Niveaux descriptifs non calibrés."""
        with user_errors():
            return get_services().audit.writing_patterns(document_id)

    @mcp.tool(title="Analyser les métadonnées", annotations=_READ)
    def analyze_document_metadata(document_id: str) -> MetadataReport:
        """Propriétés du fichier (auteur, dates, logiciel, durée d'édition), incohérences, outils nommés, texte masqué,
        avec les explications légitimes possibles de chaque constat."""
        with user_errors():
            return get_services().audit.metadata(document_id)

    @mcp.tool(title="Historique des révisions", annotations=_READ)
    def inspect_revision_history(document_id: str) -> RevisionHistory:
        """Sessions d'édition, durée d'édition, numéro de révision, modifications suivies (auteurs, dates) et
        commentaires conservés dans un fichier Office."""
        with user_errors():
            meta = get_services().audit.metadata(document_id)
            return RevisionHistory(document_id=document_id, editing_sessions=meta.editing_sessions,
                                   editing_time_minutes=meta.properties.get("app_TotalTime"),
                                   revision_number=meta.properties.get("revision"),
                                   tracked_changes=meta.tracked_changes, comments=meta.comments)

    @mcp.tool(title="Provenance du document", annotations=_READ)
    def inspect_document_provenance(document_id: str) -> ProvenanceReport:
        """Données de provenance : Content Credentials (C2PA), IPTC Digital Source Type (médias déclarés générés
        par IA), outils nommés dans les métadonnées XMP et les propriétés."""
        with user_errors():
            return get_services().audit.provenance(document_id)

    @mcp.tool(title="Vérifier les Content Credentials", annotations=_READ)
    def verify_content_credentials(document_id: str) -> ProvenanceReport:
        """Recherche un manifeste Content Credentials (C2PA) dans le fichier et ses médias. La signature
        cryptographique n'est pas vérifiée localement : la présence d'un manifeste n'en garantit pas l'authenticité."""
        with user_errors():
            return get_services().audit.provenance(document_id)

    @mcp.tool(title="Contrôler l'intégrité", annotations=_READ)
    def audit_document_integrity(document_id: str) -> IntegrityReport:
        """Intégrité de la copie (SHA-256), cohérence contenu / extension, éléments à risque, texte masqué et
        instructions cachées destinées à une IA."""
        with user_errors():
            return get_services().audit.integrity(document_id)

    @mcp.tool(title="Rapport d'audit IA",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=False))
    def generate_ai_audit_report(document_id: str) -> AIAssessment:
        """Produit le rapport d'audit complet (Markdown) : passage analysé, types d'indices, observations, confiance
        non calibrée, limites, conclusion, recommandations ; enregistré dans le dossier exports du projet.
        Indices pour un examen humain, jamais des preuves ; aucune décision ne doit reposer sur ce seul rapport."""
        with user_errors():
            return get_services().audit.assess(document_id, save_report=True)
