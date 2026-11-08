"""Construction du plan à partir du gabarit (convention + discipline) et des exigences ;
contrôle de couverture des exigences."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from academic_writer.domains.structures import StructureTemplate
from academic_writer.writing.models import OutlineIssue, Requirement

DEFAULT_WORDS = {
    "travaux_courts": 1200, "rapport_laboratoire": 2000, "projet": 5000, "memoire": 15000, "these": 60000,
    "article": 5000, "rapport_technique": 4000, "rapport_intervention": 2000, "cahier_des_charges": 3000,
    "procedure": 1500, "autre": 2000,
}
WORDS_PER_PAGE = 300
NO_TEXT = {"title_page", "contents", "lists", "abbreviations", "terms", "references", "appendices", "udc",
           "illustrations", "glossary", "revision_history", "publications", "contributors", "assignment",
           "title_authors", "keywords", "symbols", "funding_conflicts", "data_availability", "acknowledgements"}
SHORT = {"abstract": 0.04, "abstract_en": 0.03, "summary": 0.05, "introduction": 0.10, "conclusion": 0.06,
         "conclusions": 0.06, "objective": 0.04, "statement": 0.05, "data": 0.04, "recommendations": 0.06}
TASK_ANCHORS = {
    "travaux_courts": "solution", "rapport_laboratoire": "processing", "projet": "calculations",
    "memoire": "results", "these": "chapters", "article": "results", "rapport_technique": "body",
    "rapport_intervention": "findings", "cahier_des_charges": "requirements", "procedure": "steps", "autre": "body",
}
TASK_LABEL = {"fr": "Tâche", "ru": "Задача", "en": "Task"}
STRUCTURE_KEYWORDS = {
    "introduction": r"введени|introduction",
    "conclusion": r"заключени|conclusion|вывод",
    "references": r"список\s+(?:использованн|литератур)|bibliograph|references|sources",
    "contents": r"содержани|оглавлени|sommaire|table des matières|contents",
    "abstract": r"реферат|аннотаци|résumé|abstract",
    "appendices": r"приложени|annexe|appendi",
    "title_page": r"титульн|page de (?:garde|titre)|title page",
    "keywords": r"ключев\w* слов|mots-clés|keywords",
}
GLOBAL_KINDS = {"length", "format", "norm", "deadline", "variant", "other"}
LINKED_KINDS = ("task", "structure", "step", "question", "objective")
QUESTIONS_TITLE = {"fr": "Réponses aux questions de contrôle", "ru": "Ответы на контрольные вопросы",
                   "en": "Answers to review questions"}
PROCESSING_TITLE = {"fr": "Traitement des résultats", "ru": "Обработка результатов", "en": "Data processing"}
STEP_ANCHORS = {"rapport_laboratoire": "procedure", "procedure": "steps"}
UNCERTAINTY_HINTS = re.compile(r"погрешн|неопредел|измерен|измерит|incertitud|mesur|uncertaint|measur|error analysis",
                               re.IGNORECASE)


def task_title(text: str, limit: int = 110) -> str:
    """Titre court et propre : première phrase, coupée à une virgule ou un mot (jamais de « … »)."""
    body = re.sub(r"^\s*(?:\d{1,2}(?:\.\d{1,2})?\s*[.)]\s*)", "", text).strip()
    first = re.split(r"(?<=[.;:!?])\s", body, maxsplit=1)[0].rstrip(".;: ")
    if len(first) <= limit:
        return first
    cut = first[:limit]
    comma = max(cut.rfind(", "), cut.rfind(" — "), cut.rfind(" ("))
    if comma >= limit // 2:
        return cut[:comma].rstrip(" ,(")
    return cut[: cut.rfind(" ")].rstrip(" ,")


@dataclass
class PlannedSection:
    title: str
    level: int
    required: bool
    section_key: str | None
    guidance: str | None
    target_words: int | None
    requirement_ids: list[str] = field(default_factory=list)
    origin: str = "template"


def target_from_requirements(requirements: list[Requirement]) -> int | None:
    for req in requirements:
        if req.kind != "length" or req.status == "rejected" or not req.value:
            continue
        match = re.match(r"(\d+)(?:-(\d+))?\s+(\S+)", req.value)
        if not match:
            continue
        low, high, unit = int(match.group(1)), int(match.group(2) or match.group(1)), match.group(3).lower()
        middle = (low + high) // 2
        if unit.startswith(("page", "страниц", "лист")):
            return middle * WORDS_PER_PAGE
        if unit.startswith(("mot", "слов", "word")):
            return middle
        if unit.startswith(("caract", "знак", "charact")):
            return middle // 6
    return None


def build_sections(template: StructureTemplate, requirements: list[Requirement], language: str,
                   total_words: int | None) -> tuple[list[PlannedSection], list[str], int]:
    """Renvoie (sections, ids d'exigences globales, nombre de mots cible)."""
    active = [r for r in requirements if r.status != "rejected"]
    total = total_words or target_from_requirements(active) or DEFAULT_WORDS.get(template.family, 2000)
    sections: list[PlannedSection] = []
    text_sections = [s for s in template.sections if s.id not in NO_TEXT]
    fixed = sum(SHORT.get(s.id, 0) for s in text_sections)
    flexible = [s for s in text_sections if s.id not in SHORT]
    share = max(0.0, 1 - fixed) / max(1, len(flexible))
    for spec in template.sections:
        if spec.id in NO_TEXT:
            words = None
        else:
            words = max(50, round(total * SHORT.get(spec.id, share) / 10) * 10)
        sections.append(PlannedSection(title=spec.title, level=1, required=spec.required, section_key=spec.id,
                                       guidance=spec.guidance, target_words=words,
                                       origin=spec.origin.split(":")[0]))

    # Exigences de structure → section correspondante.
    for req in active:
        if req.kind != "structure":
            continue
        for key, pattern in STRUCTURE_KEYWORDS.items():
            if re.search(pattern, req.text, re.IGNORECASE):
                target = next((s for s in sections if s.section_key == key), None)
                if target is not None and req.id not in target.requirement_ids:
                    target.requirement_ids.append(req.id)

    def find(*keys: str) -> PlannedSection | None:
        return next((s for s in sections if s.section_key in keys), None)

    def anchor_index_for(key: str) -> int:
        index = next((i for i, s in enumerate(sections) if s.section_key == key), None)
        if index is None:
            index = next((i for i, s in enumerate(sections) if s.section_key in ("conclusion", "conclusions")),
                         len(sections)) - 1
        return max(index, 0)

    # Rapport de TP sans mesures ni incertitudes : section de traitement simplifiée, mesures facultatives.
    if template.family == "rapport_laboratoire" and not any(UNCERTAINTY_HINTS.search(r.text) for r in active):
        processing, measurements = find("processing"), find("measurements")
        if processing is not None:
            processing.title = PROCESSING_TITLE.get(language, processing.title)
            processing.guidance = None
        if measurements is not None:
            measurements.required = False

    # Objectif → section « objectif » (ou introduction).
    objective_section = find("objective", "introduction")
    for req in (r for r in active if r.kind == "objective"):
        target = objective_section or sections[0]
        target.requirement_ids.append(req.id)

    # Étapes (manipulations) → regroupées dans la section de procédure, jamais en sous-sections.
    steps = [r for r in active if r.kind == "step"]
    if steps:
        anchor = sections[anchor_index_for(STEP_ANCHORS.get(template.family, TASK_ANCHORS.get(template.family, "body")))]
        anchor.requirement_ids.extend(r.id for r in steps)

    # Questions de contrôle → une seule section de réponses (créée si le gabarit n'en a pas).
    questions = [r for r in active if r.kind == "question"]
    if questions:
        section = find("control_questions")
        if section is None:
            position = next((i for i, s in enumerate(sections) if s.section_key in ("references", "appendices")),
                            len(sections))
            section = PlannedSection(title=QUESTIONS_TITLE.get(language, QUESTIONS_TITLE["fr"]), level=1, required=True,
                                     section_key="control_questions", guidance=None, target_words=None,
                                     origin="requirement")
            sections.insert(position, section)
        section.required = True
        section.target_words = max(section.target_words or 0, 60 * len(questions))
        section.requirement_ids.extend(r.id for r in questions)

    # Tâches (livrables) → sous-sections sous la section d'ancrage de la famille.
    tasks = [r for r in active if r.kind == "task"]
    if tasks:
        anchor_index = anchor_index_for(TASK_ANCHORS.get(template.family, "body"))
        anchor = sections[anchor_index]
        per_task = max(80, round((anchor.target_words or 300) / len(tasks) / 10) * 10)
        label = TASK_LABEL.get(language, "Tâche")
        for number, req in enumerate(tasks, start=1):
            sections.insert(anchor_index + number, PlannedSection(
                title=f"{label} {number}. {task_title(req.text)}", level=2, required=True, section_key=None,
                guidance=req.text, target_words=per_task, requirement_ids=[req.id], origin="requirement"))
        anchor.requirement_ids.extend(r.id for r in active if r.kind == "data" and r.id not in anchor.requirement_ids)

    global_ids = [r.id for r in active if r.kind in GLOBAL_KINDS]
    return sections, global_ids, total


def coverage_issues(sections: list[dict], requirements: list[Requirement], global_ids: list[str],
                    template_required: dict[str, str]) -> list[OutlineIssue]:
    """Exigences non couvertes, sections obligatoires absentes, titres vides."""
    issues: list[OutlineIssue] = []
    linked = {rid for s in sections for rid in s["requirement_ids"]} | set(global_ids)
    for req in requirements:
        if req.status == "rejected" or req.kind not in LINKED_KINDS:
            continue
        if req.id not in linked:
            issues.append(OutlineIssue(severity="error", requirement_id=req.id,
                                       message=f"Exigence non couverte par le plan : « {req.text[:150]} »"))
    present = {s["section_key"] for s in sections if s["section_key"]}
    for key, title in template_required.items():
        if key not in present:
            issues.append(OutlineIssue(severity="warning",
                                       message=f"Section attendue par la convention absente : « {title} »"))
    for section in sections:
        if not section["title"].strip():
            issues.append(OutlineIssue(severity="error", section_id=section["id"], message="Section sans titre."))
    return issues
