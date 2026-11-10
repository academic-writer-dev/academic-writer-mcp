"""Modèles de données partagés (validés par Pydantic)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def new_id() -> str:
    """Identifiant unique (UUID4, 32 caractères hexadécimaux)."""
    return uuid.uuid4().hex


def utc_now() -> str:
    """Horodatage UTC ISO 8601 à la microseconde (tri chronologique fiable)."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Language(StrEnum):
    FR = "fr"
    RU = "ru"
    EN = "en"


LANGUAGE_LABELS: dict[Language, str] = {
    Language.FR: "Français",
    Language.RU: "Русский (russe)",
    Language.EN: "English (anglais)",
}


class DocumentType(StrEnum):
    TD = "td"
    TP = "tp"
    DEVOIR = "devoir"
    RAPPORT_LABORATOIRE = "rapport_laboratoire"
    PROJET_UNIVERSITAIRE = "projet_universitaire"
    MEMOIRE_LICENCE = "memoire_licence"
    MEMOIRE_MASTER = "memoire_master"
    THESE_DOCTORAT = "these_doctorat"
    ARTICLE_SCIENTIFIQUE = "article_scientifique"
    COMMUNICATION_SCIENTIFIQUE = "communication_scientifique"
    RAPPORT_TECHNIQUE = "rapport_technique"
    RAPPORT_INSPECTION = "rapport_inspection"
    RAPPORT_MAINTENANCE = "rapport_maintenance"
    CAHIER_DES_CHARGES = "cahier_des_charges"
    ETUDE_TECHNIQUE = "etude_technique"
    DOCUMENT_CONCEPTION = "document_conception"
    PROCEDURE_OPERATIONNELLE = "procedure_operationnelle"
    RAPPORT_AUDIT = "rapport_audit"
    DOCUMENTATION_PROFESSIONNELLE = "documentation_professionnelle"
    EXPOSE = "expose"
    PRESENTATION_ORALE = "presentation_orale"
    ETUDE_DE_CAS = "etude_de_cas"
    FICHE_DE_LECTURE = "fiche_de_lecture"
    SYNTHESE_BIBLIOGRAPHIQUE = "synthese_bibliographique"
    RAPPORT_DE_STAGE = "rapport_de_stage"
    COMPTE_RENDU_TP = "compte_rendu_tp"
    RAPPORT_DE_COURS = "rapport_de_cours"
    PROJET_TECHNIQUE = "projet_technique"
    PROJET_RECHERCHE = "projet_recherche"
    AUTRE = "autre"


DOCUMENT_TYPE_LABELS: dict[DocumentType, str] = {
    DocumentType.TD: "Travaux dirigés (TD)",
    DocumentType.TP: "Travaux pratiques (TP)",
    DocumentType.DEVOIR: "Devoir / travail de cours",
    DocumentType.RAPPORT_LABORATOIRE: "Rapport de laboratoire",
    DocumentType.PROJET_UNIVERSITAIRE: "Projet universitaire",
    DocumentType.MEMOIRE_LICENCE: "Mémoire de Licence",
    DocumentType.MEMOIRE_MASTER: "Mémoire de Master",
    DocumentType.THESE_DOCTORAT: "Thèse de Doctorat",
    DocumentType.ARTICLE_SCIENTIFIQUE: "Article scientifique",
    DocumentType.COMMUNICATION_SCIENTIFIQUE: "Communication / publication scientifique",
    DocumentType.RAPPORT_TECHNIQUE: "Rapport technique",
    DocumentType.RAPPORT_INSPECTION: "Rapport d'inspection",
    DocumentType.RAPPORT_MAINTENANCE: "Rapport de maintenance industrielle",
    DocumentType.CAHIER_DES_CHARGES: "Cahier des charges",
    DocumentType.ETUDE_TECHNIQUE: "Étude technique",
    DocumentType.DOCUMENT_CONCEPTION: "Document de conception",
    DocumentType.PROCEDURE_OPERATIONNELLE: "Procédure opérationnelle",
    DocumentType.RAPPORT_AUDIT: "Rapport d'audit",
    DocumentType.DOCUMENTATION_PROFESSIONNELLE: "Documentation professionnelle",
    DocumentType.EXPOSE: "Exposé",
    DocumentType.PRESENTATION_ORALE: "Présentation orale / soutenance",
    DocumentType.ETUDE_DE_CAS: "Étude de cas",
    DocumentType.FICHE_DE_LECTURE: "Fiche de lecture",
    DocumentType.SYNTHESE_BIBLIOGRAPHIQUE: "Synthèse bibliographique",
    DocumentType.RAPPORT_DE_STAGE: "Rapport de stage",
    DocumentType.COMPTE_RENDU_TP: "Compte rendu de TP",
    DocumentType.RAPPORT_DE_COURS: "Rapport de cours / travail de cours",
    DocumentType.PROJET_TECHNIQUE: "Projet technique",
    DocumentType.PROJET_RECHERCHE: "Projet de recherche",
    DocumentType.AUTRE: "Autre",
}


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentRole(StrEnum):
    INSTRUCTIONS = "instructions"  # consignes de l'enseignant / du responsable
    SOURCE = "source"  # source documentaire
    DRAFT = "draft"  # document de l'utilisateur à analyser / améliorer
    DATA = "data"  # données (mesures, tableaux...)
    TEMPLATE = "template"  # modèle institutionnel
    COURSE = "course"  # support de cours, notes, transcription des explications de l'enseignant
    RUBRIC = "rubric"  # barème, grille d'évaluation
    EXAMPLE = "example"  # exemple de travail fourni par l'enseignant
    OTHER = "other"


SourcePolicy = Literal["course_only", "project_sources", "external_allowed"]
SOURCE_POLICY_LABELS: dict[str, str] = {
    "course_only": "Uniquement les documents de l'enseignant (consignes, cours, barème, modèles, exemples, données)",
    "project_sources": "Documents et sources enregistrées du projet (par défaut)",
    "external_allowed": "Sources externes autorisées, toujours signalées comme telles",
}
# Rôles des documents fournis par l'enseignant : seuls autorisés quand la politique est « course_only ».
TEACHER_ROLES: tuple[str, ...] = ("instructions", "course", "rubric", "template", "example", "data")


class Project(BaseModel):
    id: str
    name: str
    description: str
    document_type: DocumentType
    language: Language
    discipline: str | None = None
    status: ProjectStatus
    domain_id: str | None = Field(default=None, description="Profil disciplinaire confirmé par l'utilisateur.")
    domain_confirmed_at: str | None = None
    convention: str | None = Field(default=None, description="Convention de présentation : ru, fr ou intl.")
    source_policy: SourcePolicy = Field(default="project_sources", description="Sources autorisées pour la rédaction.")
    teacher_profile_id: str | None = Field(default=None, description="Profil d'enseignant rattaché.")
    secondary_domain_ids: list[str] = Field(default_factory=list,
                                            description="Profils secondaires (travail interdisciplinaire).")
    created_at: str
    updated_at: str


class ProjectList(BaseModel):
    count: int
    projects: list[Project]


class Document(BaseModel):
    id: str
    project_id: str
    role: DocumentRole
    title: str | None = None
    original_filename: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    stored_path: str = Field(description="Chemin de la copie protégée, relatif au dossier de données.")
    security_notes: list[str] = Field(default_factory=list)
    status: str
    created_at: str
    updated_at: str


class DocumentList(BaseModel):
    project_id: str
    count: int
    documents: list[Document]


class ImportResult(BaseModel):
    document: Document
    duplicate: bool = Field(description="Vrai si un fichier identique (même SHA-256) existait déjà.")
    message: str


class DocumentMetadata(BaseModel):
    document: Document
    integrity_ok: bool = Field(description="La copie protégée correspond toujours à son empreinte SHA-256.")
    original_protected: bool = Field(description="La copie de l'original est en lecture seule.")
