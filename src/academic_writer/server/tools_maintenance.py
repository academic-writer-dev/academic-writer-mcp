"""Outils MCP de maintenance (diagnostic, sauvegardes) et prompts de travail guidés."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from academic_writer.core import maintenance
from academic_writer.core.maintenance import BackupInfo, BackupList, Diagnosis
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Diagnostic du système", annotations=_READ)
    def system_check() -> Diagnosis:
        """État de tous les composants : base de données, espace disque, mode réseau, OCR, LanguageTool, modèle
        local, fournisseurs d'IA, clés de sources, Microsoft Word, Claude Desktop, sauvegardes ; avec la
        correction à faire pour chaque composant absent."""
        with user_errors():
            return maintenance.diagnose(get_services())

    @mcp.tool(title="Créer une sauvegarde",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=False))
    def create_backup(complete: bool = True) -> BackupInfo:
        """Sauvegarde locale : complète (.zip : base + documents, rédactions, exports, configuration) ou base seule.
        Les clés API ne sont jamais incluses. La restauration se fait en ligne de commande
        (« uv run academic-writer restore <fichier.zip> --yes »), Claude fermé."""
        with user_errors():
            services = get_services()
            return maintenance.create_backup(services.settings, services.db, complete=complete)

    @mcp.tool(title="Lister les sauvegardes", annotations=_READ)
    def list_backups() -> BackupList:
        """Sauvegardes disponibles (les plus récentes d'abord), avec taille et date."""
        with user_errors():
            return maintenance.list_backups(get_services().settings)

    # --- prompts guidés ---------------------------------------------------------------------------
    @mcp.prompt(title="Rédiger un rapport de A à Z")
    def rediger_rapport(fichier_consignes: str, type_document: str = "rapport_laboratoire",
                        langue: str = "ru") -> str:
        """Parcours complet : consignes → exigences → plan → rédaction → contrôle → export."""
        return (
            f"Aide-moi à préparer un document « {type_document} » (langue : {langue}) à partir des consignes "
            f"« {fichier_consignes} ». Procède étape par étape et attends ma validation entre chaque étape :\n"
            "1. create_project puis import_document (rôle instructions) ;\n"
            "2. identify_domain et set_project_domain ; analyze_assignment ; montre-moi les exigences "
            "(objectif, étapes, questions) et les DONNÉES MANQUANTES que je dois fournir moi-même ;\n"
            "3. create_academic_outline, puis validate_outline après mon accord ;\n"
            "4. pour chaque section : write_academic_section (ou get_section_brief), je relis, review_revision ;\n"
            "5. sources : search_sources / find_works_by_topic, register_source, insert_citation ;\n"
            "6. final_quality_audit et correction des problèmes ;\n"
            "7. export_document (format pdf) avec MES informations de page de titre.\n"
            "Règles : n'invente aucune valeur, mesure, référence ni résultat ; utilise [ЗАПОЛНИТЬ: …] / "
            "[À COMPLÉTER : …] quand une donnée manque ; signale toute incertitude."
        )

    @mcp.prompt(title="Vérifier avant la remise")
    def verifier_avant_remise(document: str) -> str:
        """Contrôle complet d'un document terminé (calculs, sources, cohérence, structure, mise en forme)."""
        return (
            f"Vérifie mon document « {document} » avant la remise. Importe-le si nécessaire (import_document, "
            "rôle draft), puis :\n"
            "1. final_quality_audit (calculs, affirmations, cohérence, structure, exigences) ;\n"
            "2. check_formatting si c'est un fichier Word (gabarit du projet) ;\n"
            "3. audit_references si le projet a des sources.\n"
            "Présente d'abord les ERREURS, puis les avertissements, avec l'endroit exact et la correction "
            "proposée. Ne corrige rien sans mon accord ; ne déclare jamais le document « validé »."
        )

    @mcp.prompt(title="Trouver des sources sur un thème")
    def trouver_sources(theme: str, langue: str = "ru") -> str:
        """Recherche légale d'ouvrages et d'articles sur un thème, avec vérification."""
        return (
            f"Trouve des sources fiables sur le thème « {theme} » (langue : {langue}).\n"
            "1. find_works_by_topic (bases légales : Internet Archive, DOAJ, arXiv, Crossref, Open Library) "
            "et search_sources (Google Books / OpenAlex si une clé est configurée) — mode connecté requis ;\n"
            "2. présente les résultats avec auteur, année, éditeur et licence ; je choisis ;\n"
            "3. register_source puis verify_source_metadata pour chaque source retenue.\n"
            "Jamais de bibliothèque pirate ; aucune référence inventée."
        )
