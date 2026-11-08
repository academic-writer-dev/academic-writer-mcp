"""Modèles de données partagés (validés par Pydantic)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

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
    OTHER = "other"


class Project(BaseModel):
    id: str
    name: str
    description: str
    document_type: DocumentType
    language: Language
    discipline: str | None = None
    status: ProjectStatus
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
