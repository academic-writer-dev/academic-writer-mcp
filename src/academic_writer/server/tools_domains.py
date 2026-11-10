"""Outils MCP : intelligence disciplinaire."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.domains import DomainAssignment, DomainIdentification, DomainList, TermLookup
from academic_writer.core.models import Project
from academic_writer.domains.model import DomainProfile
from academic_writer.domains.structures import StructureTemplate
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
Lang = Literal["fr", "ru", "en"]
Conv = Literal["ru", "fr", "intl"]


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Identifier le domaine", annotations=_READ)
    def identify_domain(
        project_id: Annotated[str, Field(description="Identifiant du projet.")],
        document_id: Annotated[str | None, Field(description="Limiter l'analyse à un document (facultatif).")] = None,
    ) -> DomainIdentification:
        """Propose la discipline du projet à partir du vocabulaire de ses documents.

        Renvoie des candidats classés, les termes trouvés et un niveau de confiance.
        C'est une suggestion : présenter le résultat à l'utilisateur et lui demander de
        confirmer avant d'appeler set_project_domain.
        """
        with user_errors():
            return get_services().domains.identify(project_id, document_id)

    @mcp.tool(title="Définir le domaine du projet",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    def set_project_domain(
        project_id: Annotated[str, Field(description="Identifiant du projet.")],
        domain_id: Annotated[str, Field(description="Identifiant du profil (voir list_domain_profiles).")],
        convention: Annotated[Conv | None, Field(
            description="Convention de présentation : ru (ГОСТ/ЕСКД), fr (NF/EN) ou intl (ISO/revues). "
                        "Par défaut : déduite de la langue du projet.")] = None,
    ) -> DomainAssignment:
        """Enregistre la discipline choisie PAR L'UTILISATEUR (après identify_domain ou sur sa demande)."""
        with user_errors():
            return get_services().domains.assign(project_id, domain_id, convention)

    @mcp.tool(title="Lister les profils disciplinaires", annotations=_READ)
    def list_domain_profiles(language: Lang = "fr") -> DomainList:
        """Liste les profils disponibles (intégrés et personnalisés), avec leur niveau de risque."""
        with user_errors():
            return get_services().domains.list_domains(language)

    @mcp.tool(title="Consulter un profil disciplinaire", annotations=_READ)
    def get_domain_profile(domain_id: Annotated[str, Field(description="Identifiant du profil.")]) -> DomainProfile:
        """Renvoie un profil complet (héritage résolu) : terminologie, méthodologie, règles, normes."""
        with user_errors():
            return get_services().domains.get_domain(domain_id)

    @mcp.tool(title="Gabarit de structure du document", annotations=_READ)
    def get_document_structure_template(
        project_id: Annotated[str | None, Field(description="Projet (type, langue, domaine et convention repris du projet).")] = None,
        document_type: Annotated[str | None, Field(description="Type de document, si pas de projet ou pour le remplacer.")] = None,
        convention: Conv | None = None,
        domain_id: str | None = None,
        language: Lang | None = None,
    ) -> StructureTemplate:
        """Sections attendues pour le document selon la convention (ГОСТ, française, internationale)
        et la discipline, avec consignes de contenu, normes et styles bibliographiques recommandés.
        Les consignes de l'établissement de l'utilisateur priment toujours sur ce gabarit.
        """
        with user_errors():
            return get_services().domains.structure_template(
                project_id, document_type=document_type, convention=convention, domain_id=domain_id,
                language=language)

    @mcp.tool(title="Rechercher un terme", annotations=_READ)
    def lookup_terminology(
        query: Annotated[str, Field(description="Terme en français, russe ou anglais.")],
        domain_id: Annotated[str | None, Field(description="Limiter à un profil (facultatif).")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> TermLookup:
        """Trouve un terme spécialisé : équivalents fr/ru/en, définition et formulations à éviter."""
        with user_errors():
            return get_services().domains.lookup_terms(query, domain_id, limit)

    @mcp.tool(title="Recharger les profils",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    def reload_domain_profiles() -> DomainList:
        """Relit les fichiers de profils (après ajout ou modification d'un profil personnalisé)."""
        with user_errors():
            return get_services().domains.reload()

    @mcp.tool(title="Profils secondaires (interdisciplinaire)",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    def set_secondary_domains(
        project_id: str,
        domain_ids: Annotated[list[str], Field(description="Jusqu'à 4 profils complémentaires (ex. "
                                                           "[\"genie_electrique\", \"economie\"]) ; [] pour retirer.")],
    ) -> Project:
        """Travail interdisciplinaire : ajoute des profils secondaires au profil principal du projet. Leur terminologie
        et leurs règles de validation sont ajoutées au dossier du rédacteur. À faire sur décision de l'utilisateur."""
        with user_errors():
            return get_services().domains.set_secondary(project_id, domain_ids)
