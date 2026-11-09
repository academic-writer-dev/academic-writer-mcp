"""Modèles communs du contrôle qualité."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "error"]
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Segment:
    """Un morceau de texte du document contrôlé, avec sa position."""

    text: str
    kind: str  # heading, paragraph, list_item, caption, table, note
    section: str | None = None
    page: int | None = None
    level: int | None = None

    @property
    def location(self) -> str | None:
        parts = []
        if self.section:
            parts.append(f"section « {self.section[:80]} »")
        if self.page:
            parts.append(f"p. {self.page}")
        return ", ".join(parts) or None


@dataclass
class Target:
    """Texte contrôlé : un document importé ou la rédaction (sections acceptées) d'un projet."""

    label: str
    project_id: str
    language: str
    segments: list[Segment]
    document_id: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def body(self) -> list[Segment]:
        return [s for s in self.segments if s.kind != "heading"]


class QualityIssue(BaseModel):
    category: str = Field(description="calculs, affirmations, coherence, structure, sources, exigences, redaction")
    code: str
    severity: Severity
    message: str
    location: str | None = None
    excerpt: str | None = None
    suggestion: str | None = None


def sort_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    return sorted(issues, key=lambda i: SEVERITY_ORDER[i.severity])


def excerpt(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
