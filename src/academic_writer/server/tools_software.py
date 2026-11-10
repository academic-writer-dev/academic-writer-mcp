"""Outil MCP : gestionnaire central des logiciels scientifiques et techniques."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.software import SoftwareReport, detect
from academic_writer.core.software_jobs import JobResult, SoftwareJob
from academic_writer.server.services import get_services, user_errors

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

    @mcp.tool(title="Moteurs de traitement disponibles",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True))
    def list_software_engines() -> dict:
        """Moteurs que Academic Writer sait lancer (Python, Excel, Octave, R, Scilab, CalculiX, Maxima), s'ils sont
        détectés sur le poste, et état de l'autorisation (software_execution dans config.toml)."""
        services = get_services()
        return {"execution_enabled": services.settings.software_execution,
                "engines": services.software_jobs.engines(),
                "notice": "Lancement seulement si software_execution = true et confirm=true à chaque traitement. Aucun "
                          "logiciel d'automatisme industriel n'est piloté."}

    @mcp.tool(title="Préparer un traitement logiciel",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=False))
    def prepare_software_job(
        project_id: str,
        engine: Literal["python", "excel", "octave", "r", "scilab", "calculix", "maxima"],
        files: Annotated[dict[str, str] | None, Field(description="Fichiers d'entrée {nom: contenu} (script .py, .m, .R, "
                                                                  ".sce, .inp, .mac ; données .csv).")] = None,
        table: Annotated[dict | None, Field(description="Données tabulaires {header, rows, name, sheet} → XLSX (Excel, "
                                                        "formules « =… » conservées) ou CSV.")] = None,
        main_file: str | None = None,
    ) -> SoftwareJob:
        """Prépare les fichiers d'entrée d'un traitement dans un dossier dédié du projet (rien n'est exécuté). Les
        fichiers peuvent aussi être ouverts à la main dans le logiciel."""
        with user_errors():
            return get_services().software_jobs.prepare(project_id, engine, files or {}, main_file, table)

    @mcp.tool(title="Lancer un traitement logiciel",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=False))
    def run_software_job(
        project_id: str,
        job_id: str,
        confirm: Annotated[bool, Field(description="true seulement après accord explicite de l'utilisateur pour CE "
                                                   "traitement.")] = False,
        timeout_s: Annotated[int | None, Field(ge=10, le=1800)] = None,
    ) -> JobResult:
        """Lance un traitement préparé dans le logiciel détecté (autorisation software_execution requise), avec durée
        maximale ; renvoie la sortie, les fichiers produits, l'aperçu des tableaux et le logiciel (version) qui a
        RÉELLEMENT produit les résultats. Commande, versions et durée sont conservées."""
        with user_errors():
            return get_services().software_jobs.run(project_id, job_id, confirm, timeout_s)
