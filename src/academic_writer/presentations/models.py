"""Modèles des présentations : plan proposé, diapositives, résultat de génération et contrôles."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SlideType = Literal["title", "section", "bullets", "two_columns", "chart", "image", "table", "key_figures", "quote",
                    "process", "conclusion", "references", "questions", "agenda", "comparison", "definitions",
                    "timeline"]
ThemeName = Literal["academique", "technique", "sobre", "clair", "minimal_premium", "corporate", "scientifique",
                    "industriel", "futuriste", "editorial"]
Occasion = Literal["expose", "soutenance_licence", "soutenance_master", "soutenance_doctorat", "presentation_scientifique",
                   "presentation_professionnelle"]


class KeyFigure(BaseModel):
    value: str = Field(max_length=24, description="Valeur telle qu'elle figure dans les sources (ex. « 151,8 рад/с »).")
    label: str = Field(max_length=80)
    source: str | None = Field(default=None, max_length=120)


class JuryQuestion(BaseModel):
    question: str = Field(max_length=300)
    answer: str = Field(default="", max_length=800, description="Éléments de réponse fondés sur le travail.")


class TermCard(BaseModel):
    term: str = Field(max_length=60)
    definition: str = Field(max_length=300)
    source: str | None = Field(default=None, max_length=120)


class Criterion(BaseModel):
    criterion: str = Field(max_length=60)
    left: str = Field(max_length=120)
    right: str = Field(max_length=120)


class Event(BaseModel):
    date: str = Field(max_length=30)
    label: str = Field(max_length=120)


class Slide(BaseModel):
    type: SlideType
    title: str = Field(default="", max_length=140)
    subtitle: str | None = Field(default=None, max_length=200)
    bullets: list[str] = Field(default_factory=list, description="Puces ; « - » en tête = sous-puce.")
    left_title: str | None = None
    left_bullets: list[str] = Field(default_factory=list)
    right_title: str | None = None
    right_bullets: list[str] = Field(default_factory=list)
    chart_id: str | None = Field(default=None, description="Graphique créé par create_chart.")
    image_path: str | None = Field(default=None, description="Image du projet (extract_document_images, charts).")
    caption: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=200, description="Origine d'une figure, d'un tableau, d'une citation.")
    header: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    figures: list[KeyFigure] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    quote: str | None = Field(default=None, max_length=400)
    quote_author: str | None = Field(default=None, max_length=120)
    references: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=4000, description="Notes du présentateur (texte à dire).")
    transition: str | None = Field(default=None, max_length=300, description="Phrase de transition vers la suite.")
    jury_questions: list[JuryQuestion] = Field(default_factory=list, description="Questions possibles du jury.")
    terms: list[TermCard] = Field(default_factory=list, description="Diapositive definitions (2 à 4 termes).")
    criteria: list[Criterion] = Field(default_factory=list, description="Diapositive comparison (left_title / right_title).")
    events: list[Event] = Field(default_factory=list, description="Diapositive timeline (3 à 7 jalons).")
    duration_seconds: int | None = Field(default=None, ge=10, le=900)


class TitleInfo(BaseModel):
    """Page de titre : uniquement les informations fournies par l'utilisateur."""
    institution: str | None = None
    department: str | None = None
    author: str | None = None
    supervisor: str | None = None
    city_year: str | None = None
    event: str | None = Field(default=None, description="Ex. « Soutenance de Master », « Защита ВКР ».")


class Deck(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    subtitle: str | None = None
    language: Literal["fr", "ru", "en"] = "fr"
    theme: ThemeName = "academique"
    title_info: TitleInfo = Field(default_factory=TitleInfo)
    footer: str | None = Field(default=None, max_length=90)
    slides: list[Slide] = Field(min_length=1, max_length=80)


class PlannedSlide(BaseModel):
    position: int
    type: SlideType
    title: str
    purpose: str = Field(description="Rôle de la diapositive dans le récit.")
    seconds: int
    material: list[str] = Field(default_factory=list, description="Éléments sourcés à utiliser (extraits, valeurs).")
    chart_ids: list[str] = Field(default_factory=list)
    origin: str | None = Field(default=None, description="Section ou document d'où vient le contenu.")


class PresentationPlan(BaseModel):
    project_id: str
    occasion: str
    language: str
    duration_minutes: int
    slide_count: int
    narrative: list[str] = Field(description="Fil narratif : problématique → objectifs → méthode → résultats → conclusion.")
    slides: list[PlannedSlide]
    available_charts: list[str]
    citable_sources: list[str]
    warnings: list[str]
    next_step: str


class SlideCheck(BaseModel):
    slide: int
    severity: Literal["info", "warning", "error"]
    code: str
    message: str


class PresentationResult(BaseModel):
    pptx_path: str
    pdf_path: str | None = None
    odp_path: str | None = None
    preview_paths: list[str] = Field(default_factory=list, description="Aperçus PNG de chaque diapositive (PowerPoint).")
    slide_count: int
    estimated_minutes: float
    checks: list[SlideCheck]
    errors: int
    warnings: int
    messages: list[str]
    notice: str = ("Présentation modifiable (PPTX). Les contrôles signalent les problèmes détectables ; le contenu, "
                   "les chiffres et le rendu restent à relire par l'utilisateur avant la soutenance.")
