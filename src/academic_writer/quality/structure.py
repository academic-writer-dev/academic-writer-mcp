"""Structure du document : comparaison au gabarit (type de document, convention, domaine) et contrôles formels.

- sections obligatoires absentes, ordre différent du gabarit ;
- numérotation des titres (trous, doublons), sauts de niveau ;
- sections vides ou très courtes ;
- marqueurs [À COMPLÉTER] restants.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from academic_writer.domains.structures import StructureTemplate
from academic_writer.quality.models import QualityIssue, Segment, excerpt, sort_issues
from academic_writer.writing.checks import _PLACEHOLDER, word_count

_NUMBER_PREFIX = re.compile(r"^\s*(?:глава|раздел|часть|chapitre|partie|chapter|part|section)?\s*"
                            r"((?:\d+\.)*\d+)\.?\s+", re.IGNORECASE)
_UNDETECTABLE = {"title_page"}
_CONTENTS_WORDS = ("содержание", "оглавление", "table des matieres", "sommaire", "contents", "table of contents")


class SectionMatch(BaseModel):
    section_id: str
    expected_title: str
    required: bool
    found_heading: str | None
    words: int | None = None


class StructureReport(BaseModel):
    label: str
    template: str = Field(description="Gabarit utilisé (type de document, convention, domaine).")
    headings_found: int
    sections: list[SectionMatch]
    issues: list[QualityIssue]
    notice: str = ("Gabarit indicatif : les exigences de l'établissement, de la кафедра ou de la revue priment "
                   "toujours sur ce contrôle.")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("ё", "е")


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"\w+", _fold(text)) if len(w) >= 3 and not w.isdigit()}


def _clean_heading(text: str) -> str:
    return _NUMBER_PREFIX.sub("", text).strip()


def _score(heading: str, titles: list[str]) -> float:
    folded = _fold(_clean_heading(heading))
    best = 0.0
    for title in titles:
        folded_title = _fold(title)
        if len(folded_title) >= 4 and (folded_title in folded or (len(folded) >= 4 and folded in folded_title)):
            return 1.0
        expected = _stems(title)
        if expected:
            best = max(best, len(expected & _stems(heading)) / len(expected))
    return best


def check_structure(label: str, segments: list[Segment], templates: dict[str, StructureTemplate],
                    language: str) -> StructureReport:
    template = templates.get(language) or next(iter(templates.values()))
    headings = [(i, s) for i, s in enumerate(segments) if s.kind == "heading"]
    issues: list[QualityIssue] = []
    template_label = (f"{template.document_type_label} — {template.convention_label} — {template.domain_name}")

    # mots par section (jusqu'au titre suivant, quel que soit son niveau)
    words_after: dict[int, int] = {}
    for position, (index, _) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(segments)
        words_after[index] = sum(word_count(s.text) for s in segments[index + 1:end] if s.kind != "heading")

    titles_by_id: dict[str, list[str]] = {}
    for tpl in templates.values():
        for section in tpl.sections:
            titles_by_id.setdefault(section.id, []).append(section.title)
    full_text = _fold(" ".join(s.text for s in segments[:400]))

    matches: list[SectionMatch] = []
    matched_positions: list[tuple[int, str, str]] = []
    used: set[int] = set()
    for section in template.sections:
        best_index, best_score = None, 0.0
        for index, heading in headings:
            if index in used:
                continue
            score = _score(heading.text, titles_by_id.get(section.id, [section.title]))
            if score > best_score:
                best_index, best_score = index, score
        found = best_index is not None and best_score >= 0.6
        if found:
            used.add(best_index)  # type: ignore[arg-type]
            matched_positions.append((best_index, section.id, section.title))  # type: ignore[arg-type]
        present_elsewhere = section.id == "contents" and any(w in full_text for w in _CONTENTS_WORDS)
        matches.append(SectionMatch(
            section_id=section.id, expected_title=section.title, required=section.required,
            found_heading=segments[best_index].text if found else ("(détecté dans le texte)" if present_elsewhere
                                                                   else None),
            words=words_after.get(best_index) if found else None))

    if not headings:
        issues.append(QualityIssue(category="structure", code="no_headings", severity="warning",
                                   message="Aucun titre détecté : la structure ne peut pas être comparée au gabarit.",
                                   suggestion="Utiliser les styles de titre du traitement de texte (ou des signets "
                                              "dans le PDF) ; sinon, vérifier la structure à la main."))
    else:
        missing_required = [m for m in matches if m.required and m.found_heading is None
                            and m.section_id not in _UNDETECTABLE]
        for match in missing_required:
            issues.append(QualityIssue(category="structure", code="section_missing", severity="warning",
                                       message=f"Section attendue non trouvée : « {match.expected_title} ».",
                                       suggestion="L'ajouter si les consignes la demandent, ou vérifier qu'elle "
                                                  "existe sous un autre intitulé."))
        missing_optional = [m.expected_title for m in matches if not m.required and m.found_heading is None]
        if missing_optional:
            issues.append(QualityIssue(category="structure", code="optional_sections_absent", severity="info",
                                       message="Sections facultatives absentes : " + ", ".join(missing_optional) + ".",
                                       suggestion="À ajouter seulement si les consignes ou le contenu le justifient."))
        ordered = sorted(matched_positions)
        template_order = {s.id: i for i, s in enumerate(template.sections)}
        for (_, first_id, first_title), (_, second_id, second_title) in zip(ordered, ordered[1:], strict=False):
            if template_order[second_id] < template_order[first_id]:
                issues.append(QualityIssue(category="structure", code="section_order", severity="info",
                                           message=f"« {second_title} » apparaît après « {first_title} », "
                                                   "contrairement à l'ordre habituel.",
                                           suggestion="Vérifier l'ordre demandé par les consignes."))
        for match in matches:
            if match.required and match.words is not None and match.words < 20 and match.section_id not in (
                    "title_page", "contents", "references", "annexes", "appendices"):
                issues.append(QualityIssue(category="structure", code="section_short", severity="info",
                                           message=f"Section « {match.found_heading} » très courte ({match.words} mots).",
                                           suggestion="Vérifier qu'elle est complète (ou que son contenu est dans "
                                                      "des sous-sections)."))
        issues.extend(_numbering_issues(headings))
        issues.extend(_empty_sections(segments, headings))
    for segment in segments:
        for placeholder in _PLACEHOLDER.finditer(segment.text):
            issues.append(QualityIssue(category="structure", code="placeholder", severity="error",
                                       message=f"Passage à compléter : {placeholder.group(0)}",
                                       location=segment.location, excerpt=excerpt(segment.text),
                                       suggestion="Compléter avec des informations vérifiées avant la remise."))
    return StructureReport(label=label, template=template_label, headings_found=len(headings), sections=matches,
                           issues=sort_issues(issues))


def _numbering_issues(headings: list[tuple[int, Segment]]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    seen: set[str] = set()
    last_child: dict[str, int] = {}
    previous_level: int | None = None
    for _, heading in headings:
        match = _NUMBER_PREFIX.match(heading.text)
        level = heading.level
        if previous_level is not None and level is not None and level > previous_level + 1:
            issues.append(QualityIssue(category="structure", code="heading_level_jump", severity="info",
                                       message=f"Saut de niveau de titre ({previous_level} → {level}) : "
                                               f"« {heading.text[:80]} ».",
                                       location=heading.location, suggestion="Insérer le niveau intermédiaire."))
        previous_level = level if level is not None else previous_level
        if not match:
            continue
        number = match.group(1)
        if number in seen:
            issues.append(QualityIssue(category="structure", code="heading_number_duplicate", severity="warning",
                                       message=f"Numéro de titre en double : {number} (« {heading.text[:80]} »).",
                                       location=heading.location, suggestion="Renuméroter les titres."))
            continue
        seen.add(number)
        parent, _, last = number.rpartition(".")
        value = int(last)
        expected = last_child.get(parent, 0) + 1
        if value != expected and value > expected:
            issues.append(QualityIssue(category="structure", code="heading_number_gap", severity="warning",
                                       message=f"Numérotation des titres discontinue : {number} après "
                                               f"{(parent + '.' if parent else '') + str(expected - 1) if expected > 1 else 'le début'}.",
                                       location=heading.location, suggestion="Vérifier qu'aucune section ne manque."))
        last_child[parent] = value
    return issues


def _empty_sections(segments: list[Segment], headings: list[tuple[int, Segment]]) -> list[QualityIssue]:
    issues = []
    for position, (index, heading) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(segments)
        body = [s for s in segments[index + 1:end] if s.kind != "heading" and s.text.strip()]
        next_heading = headings[position + 1][1] if position + 1 < len(headings) else None
        has_children = (next_heading is not None and heading.level is not None and next_heading.level is not None
                        and next_heading.level > heading.level)
        if not body and not has_children:
            issues.append(QualityIssue(category="structure", code="section_empty", severity="warning",
                                       message=f"Section sans contenu : « {heading.text[:80]} ».",
                                       location=heading.location, suggestion="La rédiger ou la supprimer."))
    return issues
