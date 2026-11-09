"""Outils MCP : sources, vérification, citations, bibliographie, audit."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.research.discovery import DiscoveryResult
from academic_writer.research.models import (
    Bibliography,
    CitationResult,
    OpenAccessDownload,
    ReferenceExport,
    ReferenceAudit,
    Source,
    SourceData,
    SourceImport,
    SourceList,
    SourceSearch,
    SourceType,
    VerificationResult,
)
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
Style = Literal["gost", "apa", "ieee", "chicago", "vancouver", "harvard", "iso690"]


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Enregistrer une source", annotations=_WRITE)
    def register_source(
        project_id: str,
        source_type: Annotated[SourceType, Field(description="book, article, chapter, conference, thesis, standard, "
                                                             "web, report, patent, other")],
        data: Annotated[SourceData | None, Field(description="Métadonnées RÉELLES fournies par l'utilisateur ou lues "
                                                             "dans un document ; ne jamais en inventer.")] = None,
        key: Annotated[str | None, Field(description="Clé de citation (sinon générée : ivanov2020).")] = None,
        document_id: Annotated[str | None, Field(description="Document importé correspondant (pré-remplit la fiche "
                                                             "si data est vide).")] = None,
        allow_duplicate: bool = False,
    ) -> Source:
        """Enregistre une source bibliographique et la vérifie localement (champs obligatoires, ISBN, DOI, année).
        Statut honnête : « bien formée » ne signifie pas « vérifiée ». N'inventer aucun auteur, titre ou DOI."""
        with user_errors():
            services = get_services()
            if data is None:
                if not document_id:
                    from academic_writer.core.errors import ValidationFailed
                    raise ValidationFailed("Fournissez les métadonnées (data) ou un document_id.")
                return services.sources.register_from_document(project_id, document_id, source_type)
            return services.sources.register(project_id, source_type, data, key, document_id, allow_duplicate)

    @mcp.tool(title="Lister les sources", annotations=_READ)
    def list_sources(project_id: str, status: Literal["unverified", "incomplete", "well_formed", "verified_online",
                                                      "verified_manual", "mismatch", "not_found", "suspicious"]
                     | None = None) -> SourceList:
        """Liste les sources du projet avec leur statut de vérification et leur nombre de citations."""
        with user_errors():
            return get_services().sources.list(project_id, status)

    @mcp.tool(title="Compléter une source", annotations=_WRITE)
    def update_source(
        source_id: str,
        changes: Annotated[dict[str, Any], Field(description="Champs à modifier (title, year, doi, authors=[{family, "
                                                             "given}], pages…).")],
        source_type: SourceType | None = None,
    ) -> Source:
        """Complète ou corrige une fiche ; elle est revérifiée localement."""
        with user_errors():
            return get_services().sources.update(source_id, changes, source_type)

    @mcp.tool(title="Vérifier une source",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=True))
    def verify_source_metadata(
        source_id: str,
        online: Annotated[bool, Field(description="Interroger Crossref / Open Library (mode connecté uniquement ; "
                                                  "seules des métadonnées sont envoyées).")] = True,
    ) -> VerificationResult:
        """Vérifie une source : localement (complétude, identifiants) puis en ligne si autorisé (DOI via Crossref,
        ISBN via Open Library, recherche par titre). Signale les références divergentes ou introuvables."""
        with user_errors():
            return get_services().sources.verify(source_id, online)

    @mcp.tool(title="Confirmer une vérification manuelle", annotations=_WRITE)
    def confirm_source_verification(
        source_id: str,
        where: Annotated[str, Field(description="Où l'UTILISATEUR a trouvé la source : « РГБ », « eLIBRARY », "
                                                "« bibliothèque СТАНКИН », « exemplaire papier »…")],
        note: str = "",
    ) -> Source:
        """Marque une source « vérifiée manuellement » après que l'utilisateur l'a trouvée lui-même (par exemple via
        les liens manual_links de la fiche). N'appeler QUE sur confirmation explicite de l'utilisateur."""
        with user_errors():
            return get_services().sources.confirm_manual(source_id, where, note)

    @mcp.tool(title="Insérer une citation", annotations=_WRITE)
    def insert_citation(
        project_id: str,
        section_id: str,
        source_key: str,
        anchor_text: Annotated[str, Field(description="Passage exact et unique de la section après lequel citer.")],
        locator: Annotated[str | None, Field(description="Localisation : « с. 15 », « p. 15 », « chap. 2 ».")] = None,
        claim: Annotated[str | None, Field(description="Affirmation étayée par la source (traçabilité).")] = None,
        force: Annotated[bool, Field(description="Citer une source douteuse sur décision explicite de l'utilisateur.")] = False,
    ) -> CitationResult:
        """Ajoute un appel [@clé] après un passage : crée une révision PROPOSÉE (rien n'est écrasé). Refuse une source
        suspecte, introuvable ou divergente, sauf décision explicite de l'utilisateur."""
        with user_errors():
            return get_services().sources.insert_citation(project_id, section_id, source_key, anchor_text, locator,
                                                          claim, force)

    @mcp.tool(title="Générer la bibliographie", annotations=_WRITE)
    def generate_bibliography(
        project_id: str,
        style: Style = "gost",
        ordering: Annotated[Literal["appearance", "alphabetical"] | None, Field(
            description="Par défaut : ordre d'apparition (gost, ieee, vancouver), alphabétique (apa, chicago, harvard, iso690).")] = None,
        include_uncited: bool = False,
        save: Annotated[bool, Field(description="Enregistrer comme révision proposée de la section bibliographie.")] = False,
    ) -> Bibliography:
        """Met en forme la bibliographie (ГОСТ Р 7.0.100 / 7.0.5, APA 7, IEEE, Chicago, Vancouver) à partir des
        citations des sections acceptées, avec la forme des appels dans le texte. Signale les sources non vérifiées."""
        with user_errors():
            return get_services().sources.generate_bibliography(project_id, style, ordering, include_uncited, save)

    @mcp.tool(title="Rechercher des livres et articles",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True, idempotent_hint=True))
    def search_sources(
        query: Annotated[str, Field(description="Titre ou mots du titre (russe, français, anglais).")] = "",
        author: Annotated[str | None, Field(description="Nom de famille d'un auteur (facultatif).")] = None,
        isbn: str | None = None,
        kind: Annotated[Literal["books", "articles", "all"], Field(
            description="books : Google Books ; articles : OpenAlex + Crossref ; all : tous.")] = "all",
        limit: Annotated[int, Field(ge=1, le=10)] = 5,
    ) -> SourceSearch:
        """Cherche des ouvrages et articles RÉELS dans Google Books (livres, dont russes), OpenAlex et Crossref.
        Renvoie des fiches pré-remplies à présenter à l'utilisateur ; n'enregistrer (register_source) que celles
        qu'il confirme. Mode connecté uniquement ; seuls les termes de recherche sont envoyés."""
        with user_errors():
            return get_services().sources.search(query, author, isbn, kind, limit)

    @mcp.tool(title="Trouver des ouvrages par thème",
              annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True, idempotent_hint=True))
    def find_works_by_topic(
        query: Annotated[str, Field(description="Thème de recherche (ex. « нарезание зубчатых колес методом обката »). "
                                                "Essayer aussi la formulation en anglais pour plus de résultats.")],
        kind: Annotated[Literal["books", "articles", "datasets", "all"], Field(
            description="books : Internet Archive, Open Library ; articles : DOAJ, arXiv, Crossref, Semantic Scholar, "
                        "Europe PMC, PubMed, HAL, Zenodo, CORE (clé) ; datasets : DataCite, Zenodo.")] = "all",
        open_access_only: Annotated[bool, Field(description="Seulement les textes intégraux légalement téléchargeables.")] = False,
        language: Annotated[Literal["ru", "en", "fr"] | None, Field(description="Langue des livres (Internet Archive).")] = None,
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
        services: Annotated[list[str] | None, Field(
            description="Restreindre aux bases citées (ex. [\"pubmed\", \"europe_pmc\"] en médecine, [\"hal\"] pour "
                        "les travaux français).")] = None,
    ) -> DiscoveryResult:
        """Trouve des livres, manuels, articles et jeux de données RÉELS sur un thème dans des bases légales et
        gratuites (Internet Archive, Open Library, DOAJ, arXiv, Crossref, Semantic Scholar, Europe PMC, PubMed, HAL,
        Zenodo, DataCite, CORE), classés par pertinence, avec lien, licence et fiche pré-remplie. open_access = texte
        intégral sous licence libre attestée (une simple lecture gratuite n'est pas présentée comme libre accès).
        Aucune bibliothèque pirate. Présenter les résultats à l'utilisateur, qui choisit."""
        with user_errors():
            return get_services().sources.discover(query, kind, open_access_only, language, limit, services)

    @mcp.tool(title="Télécharger un texte en libre accès",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=True))  # télécharge sur Internet
    def download_open_access(
        project_id: str,
        item_id: Annotated[str, Field(description="item_id d'un résultat de find_works_by_topic marqué open_access "
                                                  "(arxiv:…, ia:…, doaj:…, hal:…, epmc:PMC…, zenodo:…, s2:…, core:…, "
                                                  "unpaywall:DOI).")],
    ) -> OpenAccessDownload:
        """Télécharge le texte intégral d'un résultat en LIBRE ACCÈS LÉGAL et l'importe dans le projet comme
        document source (copie protégée, lisible et cherchable). Licence revérifiée par le serveur ; refusé pour
        les ouvrages protégés. À faire sur demande de l'utilisateur."""
        with user_errors():
            return get_services().sources.download_open_access(project_id, item_id)

    @mcp.tool(title="Exporter les références", annotations=_WRITE)
    def export_references(
        project_id: str,
        format: Annotated[Literal["bibtex", "ris", "text"], Field(
            description="bibtex / ris : pour Zotero, Word, LaTeX ; text : liste mise en forme dans un style.")] = "bibtex",
        style: Literal["gost", "apa", "ieee", "chicago", "vancouver", "harvard", "iso690"] = "gost",
        keys: Annotated[list[str] | None, Field(description="Clés à exporter ; toutes par défaut.")] = None,
    ) -> ReferenceExport:
        """Exporte les sources du projet dans un fichier (BibTeX, RIS ou liste ГОСТ / APA / IEEE…) placé dans le
        dossier « exports » du projet, et renvoie son contenu."""
        with user_errors():
            return get_services().sources.export_references(project_id, format, style, keys)

    @mcp.tool(title="Importer des notices (RIS / BibTeX)", annotations=_WRITE)
    def import_sources_file(
        project_id: str,
        file_path: Annotated[str, Field(description="Chemin absolu d'un fichier .ris ou .bib exporté depuis un catalogue "
                                                    "(Zotero, Google Scholar, eLIBRARY, РГБ, bibliothèque…).")],
    ) -> SourceImport:
        """Importe en une fois les notices d'un fichier RIS ou BibTeX : chaque source est enregistrée et vérifiée
        localement ; les doublons sont ignorés."""
        with user_errors():
            return get_services().sources.import_file(project_id, file_path)

    @mcp.tool(title="Auditer les références", annotations=_READ)
    def audit_references(project_id: str) -> ReferenceAudit:
        """Contrôle : citations sans source, citations écrites à la main, sources jamais citées, fiches incomplètes,
        suspectes, introuvables ou divergentes, doublons."""
        with user_errors():
            return get_services().sources.audit(project_id)

    @mcp.tool(title="Sources jamais citées", annotations=_READ)
    def find_uncited_references(project_id: str) -> SourceList:
        """Sources enregistrées qui ne sont citées dans aucune section acceptée."""
        with user_errors():
            return get_services().sources.uncited(project_id)
