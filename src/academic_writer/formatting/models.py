"""Modèles de la mise en forme (sans dépendance à python-docx : chargés au démarrage du serveur)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from academic_writer.quality.models import QualityIssue

TITLE_FIELDS = ("ministry", "organization", "faculty", "department", "document_kind", "discipline", "title",
                "variant", "author", "group", "supervisor", "supervisor_title", "city", "year")
REQUIRED_TITLE_FIELDS = ("organization", "document_kind", "title", "author", "city", "year")


@dataclass
class ExportSection:
    key: str | None
    title: str
    level: int
    text: str | None  # None = non rédigée
    kind: str = "body"  # body, title_page, contents, bibliography


class PropertyCheck(BaseModel):
    property: str
    expected: str
    dominant: str = Field(description="Valeur la plus fréquente dans le corps du texte.")
    conforming_ratio: float = Field(description="Part des paragraphes du corps conformes (0 à 1).")
    examples: list[str] = Field(default_factory=list, description="Paragraphes non conformes (extraits).")


class FormattingCheck(BaseModel):
    document_id: str
    filename: str
    preset: str
    body_paragraphs: int
    margins_mm: dict[str, float]
    properties: list[PropertyCheck]
    issues: list[QualityIssue]
    notice: str = "Gabarit indicatif : vérifier les exigences de la кафедра / de l'établissement."


class FormattingApplied(BaseModel):
    document_id: str
    output_path: str
    pdf_path: str | None = None
    preset: str
    paragraphs_formatted: int
    headings_kept: int
    page_numbers_added: bool
    messages: list[str]
    notice: str = "Copie mise en forme : l'original est inchangé. Relire la copie (tableaux, figures, listes)."
