"""Modèles communs de l'analyse documentaire."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "faible", "moyen", "fort"]

AI_TOOL = (r"chat\s?gpt|openai|\bgpt-?[345o]|copilot|claude|anthropic|gemini|\bbard\b|jasper|writesonic|"
           r"gigachat|yandex\s?gpt|yandexgpt|perplexity|mistral|deepseek|notion ai|нейросет")
CORRECTION_TOOL = r"grammarly|quillbot|languagetool|wordtune|prowritingaid|орфограммка|ginger software"
TRANSLATION_TOOL = r"deepl|google translate|google переводчик|яндекс[\s.]?переводчик|yandex translate|reverso"


class ForensicFinding(BaseModel):
    category: str = Field(description="metadata, history, hidden_text, provenance, integrity…")
    severity: Severity
    observation: str
    evidence: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list,
                                    description="Explications possibles, y compris parfaitement légitimes.")


class TrackedChanges(BaseModel):
    insertions: int = 0
    deletions: int = 0
    authors: dict[str, int] = Field(default_factory=dict)
    first_date: str | None = None
    last_date: str | None = None


class Comment(BaseModel):
    author: str | None
    date: str | None
    text: str


class MetadataReport(BaseModel):
    document_id: str
    format: str
    properties: dict[str, str]
    editing_sessions: int | None = Field(default=None, description="Sessions d'édition Word enregistrées (rsid).")
    tracked_changes: TrackedChanges | None = None
    comments: list[Comment] = Field(default_factory=list)
    hidden_text: list[str] = Field(default_factory=list)
    findings: list[ForensicFinding]
    limits: list[str]


class ProvenanceReport(BaseModel):
    document_id: str
    content_credentials: bool = Field(description="Manifeste C2PA (Content Credentials) détecté.")
    signature_verified: bool = Field(default=False, description="Signature du manifeste vérifiée cryptographiquement.")
    declared_ai_media: list[str] = Field(default_factory=list,
                                         description="Éléments déclarés générés par IA (IPTC trainedAlgorithmicMedia…).")
    declared_tools: list[str] = Field(default_factory=list, description="Outils nommés dans les métadonnées.")
    findings: list[ForensicFinding]
    limits: list[str]
