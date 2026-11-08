"""Modèles de données de la rédaction encadrée."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequirementKind = Literal["task", "step", "question", "objective", "length", "structure", "format", "norm",
                          "deadline", "variant", "data", "other"]
RequirementStatus = Literal["proposed", "confirmed", "rejected"]


class Requirement(BaseModel):
    id: str
    project_id: str
    source_document_id: str | None = None
    source_filename: str | None = None
    page: int | None = None
    kind: RequirementKind
    text: str
    value: str | None = None
    status: RequirementStatus
    origin: Literal["extracted", "user"]
    position: int = 0
    number: str | None = Field(default=None, description="Numéro dans les consignes d'origine.")
    group_label: str | None = Field(default=None, description="Intertitre sous lequel l'exigence apparaît.")


class RequirementList(BaseModel):
    project_id: str
    count: int
    by_kind: dict[str, int]
    requirements: list[Requirement]
    notice: str = ("Exigences extraites automatiquement : à confirmer ou rejeter par l'utilisateur "
                   "(manage_requirement). Les consignes originales font foi.")


class SuggestedInput(BaseModel):
    symbol: str
    name: str
    unit: str | None = None
    calculation: str = Field(description="Calcul du profil disciplinaire qui requiert cette donnée.")
    default: str | None = Field(default=None, description="Valeur normalisée proposée (à confirmer), sinon None.")
    standard: str | None = None
    status: Literal["missing", "default_proposed"]


class AssignmentAnalysis(BaseModel):
    project_id: str
    analyzed_documents: list[str]
    extracted: int
    by_kind: dict[str, int]
    variant: str | None
    length: str | None
    norms: list[str]
    deadlines: list[str]
    missing_data: list[str] = Field(default_factory=list,
                                    description="Données d'entrée nécessaires sans valeur fournie (à demander).")
    suggested_inputs: list[SuggestedInput] = Field(
        default_factory=list, description="Données d'entrée attendues par les calculs détectés, avec les valeurs "
                                          "normalisées proposées par défaut (à confirmer par l'utilisateur).")
    warnings: list[str]
    requirements: list[Requirement]
    next_step: str


class OutlineSection(BaseModel):
    id: str
    position: int
    section_key: str | None = None
    title: str
    level: int
    required: bool
    guidance: str | None = None
    target_words: int | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    status: Literal["planned", "drafted", "validated"]
    origin: str


class Outline(BaseModel):
    id: str
    project_id: str
    version: int
    status: Literal["draft", "approved", "superseded"]
    language: str
    convention: str
    domain_id: str
    target_words: int | None
    global_requirement_ids: list[str]
    sections: list[OutlineSection]
    created_at: str
    approved_at: str | None = None


class OutlineIssue(BaseModel):
    severity: Literal["error", "warning"]
    message: str
    requirement_id: str | None = None
    section_id: str | None = None


class OutlineValidation(BaseModel):
    outline: Outline
    approved: bool
    issues: list[OutlineIssue]
    message: str


class Check(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    details: list[str] = Field(default_factory=list)


class SectionRevision(BaseModel):
    id: str
    project_id: str
    section_id: str
    section_title: str
    version: int
    kind: Literal["draft", "rewrite", "translation", "correction"]
    engine: str
    model: str | None
    language: str
    text: str
    word_count: int
    checks: list[Check]
    status: Literal["proposed", "accepted", "rejected", "superseded"]
    parent_revision_id: str | None = None
    note: str = ""
    created_at: str
    decided_at: str | None = None


class SectionBrief(BaseModel):
    project_id: str
    section_id: str
    section_title: str
    language: str
    target_words: int | None
    system_prompt: str = Field(description="Règles de rédaction à respecter impérativement.")
    brief: str = Field(description="Dossier de la section : contexte, exigences, extraits de sources, terminologie.")
    source_excerpts: int
    trust_notice: str


class WriteResult(BaseModel):
    engine: str
    engine_reason: str
    revision: SectionRevision | None = Field(default=None, description="Révision proposée (moteur serveur).")
    brief: SectionBrief | None = Field(default=None, description="Dossier à rédiger (moteur assistant).")
    next_step: str


class DraftSectionStatus(BaseModel):
    section_id: str
    title: str
    level: int
    status: str
    target_words: int | None
    accepted_words: int | None
    accepted_revision_id: str | None
    pending_revision_ids: list[str]


class DraftStatus(BaseModel):
    project_id: str
    outline_id: str | None
    outline_status: str | None
    sections: list[DraftSectionStatus]
    accepted_words: int
    target_words: int | None
    progress: str
