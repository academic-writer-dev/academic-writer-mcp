"""Modèles des sources bibliographiques."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["book", "article", "chapter", "conference", "thesis", "standard", "web", "report", "patent", "other"]
VerificationStatus = Literal["unverified", "incomplete", "well_formed", "verified_online", "mismatch", "not_found",
                             "suspicious"]
Style = Literal["gost", "apa", "ieee", "chicago", "vancouver"]

STATUS_LABELS = {
    "unverified": "non vérifiée",
    "incomplete": "incomplète (champs obligatoires manquants)",
    "well_formed": "bien formée localement — NON vérifiée en ligne",
    "verified_online": "vérifiée en ligne (métadonnées concordantes)",
    "mismatch": "divergente : les métadonnées en ligne ne correspondent pas",
    "not_found": "introuvable en ligne (identifiant inconnu)",
    "suspicious": "suspecte (identifiant invalide, date impossible…)",
}


class Person(BaseModel):
    family: str = Field(description="Nom de famille (Иванов, Dupont).")
    given: str | None = Field(default=None, description="Prénom(s) ou initiales (Иван Иванович, I. I., Marie).")


class SourceData(BaseModel):
    """Métadonnées bibliographiques ; seuls les champs utiles au type de source sont requis."""

    authors: list[Person] = Field(default_factory=list)
    editors: list[Person] = Field(default_factory=list)
    title: str | None = None
    subtitle: str | None = Field(default=None, description="Sous-titre ou nature (учебник, монография…).")
    container: str | None = Field(default=None, description="Revue, ouvrage collectif, actes de conférence, site web.")
    publisher: str | None = Field(default=None, description="Éditeur ou établissement (pour un mémoire, une thèse).")
    place: str | None = Field(default=None, description="Ville d'édition.")
    year: int | None = None
    edition: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = Field(default=None, description="Pages de l'article (10–20) ou nombre total de pages (320).")
    doi: str | None = None
    isbn: str | None = None
    issn: str | None = None
    url: str | None = None
    accessed: str | None = Field(default=None, description="Date de consultation (JJ.MM.AAAA) pour une ressource en ligne.")
    standard_number: str | None = Field(default=None, description="Numéro de norme (ГОСТ 7.32-2017, ISO 690:2021).")
    language: str | None = Field(default=None, description="Langue de la source (ru, fr, en…).")
    notes: str | None = None


class Finding(BaseModel):
    severity: Literal["info", "warning", "error"]
    field: str | None = None
    message: str


class Source(BaseModel):
    id: str
    project_id: str
    key: str = Field(description="Clé de citation stable, utilisée dans le texte : [@clé] ou [@clé, с. 15].")
    source_type: SourceType
    data: SourceData
    document_id: str | None = None
    origin: Literal["user", "document", "online"]
    verification_status: VerificationStatus
    status_label: str
    verification_details: list[Finding]
    verified_at: str | None = None
    citation_count: int = 0


class SourceList(BaseModel):
    project_id: str
    count: int
    by_status: dict[str, int]
    sources: list[Source]


class OnlineCandidate(BaseModel):
    title: str | None
    authors: list[str]
    year: int | None
    container: str | None
    doi: str | None
    score: float


class VerificationResult(BaseModel):
    source: Source
    online_checked: bool
    online_notice: str | None = None
    candidates: list[OnlineCandidate] = Field(default_factory=list,
                                              description="Correspondances possibles trouvées en ligne (à confirmer).")


class CitationResult(BaseModel):
    marker: str = Field(description="Marqueur inséré dans le texte (stable, indépendant du style).")
    source: Source
    revision_id: str | None = Field(default=None, description="Nouvelle révision proposée contenant le marqueur.")
    message: str


class BibliographyEntry(BaseModel):
    key: str
    number: int | None
    marker: str = Field(description="Forme de l'appel dans le texte pour ce style ([1], (Иванов, 2020)…).")
    text: str
    status: str
    cited: bool


class Bibliography(BaseModel):
    project_id: str
    style: Style
    style_label: str
    ordering: str
    entries: list[BibliographyEntry]
    text: str = Field(description="Bibliographie mise en forme (Markdown).")
    warnings: list[str]
    revision_id: str | None = Field(default=None, description="Révision proposée de la section bibliographie.")


class AuditIssue(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    source_key: str | None = None
    section_title: str | None = None


class ReferenceAudit(BaseModel):
    project_id: str
    sources: int
    cited_sources: int
    citations_in_text: int
    issues: list[AuditIssue]
    summary: str
