"""Cohérence interne d'un document.

- figures et tableaux : renvois sans légende, légendes jamais citées, numéros en double ou manquants ;
- abréviations employées avant d'être définies, ou jamais définies ;
- termes à éviter du profil disciplinaire ;
- séparateur décimal mélangé (virgule / point) ;
- symboles recevant plusieurs valeurs (fourni par le contrôle des calculs).
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from academic_writer.domains.model import DomainProfile
from academic_writer.quality.models import QualityIssue, Segment, excerpt, sort_issues

_KINDS = {
    "figure": (r"рисунок|рис\.|figure|fig\.", "Рисунок/Figure"),
    "table": (r"таблица|табл\.|tableau|table|tabl\.", "Таблица/Tableau"),
}
_NUM = r"(\d+(?:[.\-]\d+)?)"
_ABBREVIATION = re.compile(r"(?<![\w-])([A-ZА-ЯЁ]{2,6}|[A-ZА-ЯЁ][a-zа-яё]?[A-ZА-ЯЁ]{1,4})(?![\w-])")
_NOT_ABBREVIATIONS = {
    "ГОСТ", "ОСТ", "СНИП", "ЕСКД", "ЕСПД", "ISO", "NF", "EN", "IEC", "DIN", "SI", "СИ", "РФ", "США", "СССР", "OK", "PDF",
    "DOCX", "USB", "PC", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XX", "XXI", "XIX", "XV", "XVI",
    "XVII", "XVIII", "MPA", "КПД", "ЭВМ", "TP", "TD", "ВУЗ", "МПА", "КН", "КВТ", "МГТУ", "UTF", "HTML", "URL", "DOI",
    "ISBN", "ISSN", "UDC", "УДК", "ББК", "EUR", "USD", "RUB", "CEO", "NB", "AI", "IA", "ИИ",
}
_ABBREVIATION_SECTIONS = ("сокращ", "обозначен", "abrev", "abbrev", "sigles", "glossa", "nomenclat", "notation")
_DECIMAL = re.compile(r"(?<![\d.,])\d+([.,])\d+(?![\d.,])")


class ConsistencyReport(BaseModel):
    label: str
    issues: list[QualityIssue]
    figures: dict[str, list[str]] = Field(default_factory=dict, description="Numéros des légendes et des renvois.")
    tables: dict[str, list[str]] = Field(default_factory=dict)
    abbreviations_checked: int = 0
    notice: str = "Contrôles automatiques de cohérence ; chaque constat est à confirmer par une relecture."


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("ё", "е")


def _numbering(segments: list[Segment], kind: str) -> tuple[dict[str, Segment], dict[str, list[Segment]], list[str]]:
    words, _ = _KINDS[kind]
    caption_re = re.compile(rf"^\s*(?:{words})\s*{_NUM}\s*(?:[.:–—-]|$|\s)", re.IGNORECASE)
    ref_re = re.compile(rf"(?:{words})\s*{_NUM}", re.IGNORECASE)
    captions: dict[str, Segment] = {}
    duplicates: list[str] = []
    refs: dict[str, list[Segment]] = {}
    for segment in segments:
        if segment.kind == "heading":
            continue
        caption = caption_re.match(segment.text)
        is_caption = bool(caption) and (segment.kind == "caption" or len(segment.text) < 200)
        if is_caption:
            number = caption.group(1).replace("-", ".")
            if number in captions:
                duplicates.append(number)
            captions.setdefault(number, segment)
        body = segment.text[caption.end():] if is_caption else segment.text
        for match in ref_re.finditer(body):
            refs.setdefault(match.group(1).replace("-", "."), []).append(segment)
    return captions, refs, duplicates


def _gaps(numbers: list[str]) -> list[str]:
    grouped: dict[str, set[int]] = {}
    for number in numbers:
        head, _, tail = number.rpartition(".")
        if tail.isdigit():
            grouped.setdefault(head, set()).add(int(tail))
    missing = []
    for head, values in grouped.items():
        for value in range(1, max(values) + 1):
            if value not in values:
                missing.append(f"{head}.{value}" if head else str(value))
    return missing


def check_cross_references(segments: list[Segment]) -> tuple[list[QualityIssue], dict, dict]:
    issues: list[QualityIssue] = []
    summaries = {}
    for kind, label in (("figure", "figure"), ("table", "tableau")):
        captions, refs, duplicates = _numbering(segments, kind)
        summaries[kind] = {"legendes": sorted(captions, key=_sort_key), "renvois": sorted(refs, key=_sort_key)}
        for number in sorted(set(refs) - set(captions), key=_sort_key):
            if not captions:
                break  # aucune légende détectée (PDF, images) : on ne conclut pas
            segment = refs[number][0]
            issues.append(QualityIssue(category="coherence", code=f"{kind}_missing", severity="warning",
                                       message=f"Renvoi au {label} {number}, mais aucune légende « {number} » trouvée.",
                                       location=segment.location, excerpt=excerpt(segment.text),
                                       suggestion=f"Ajouter la légende ou corriger le numéro du {label}."))
        for number in sorted(set(captions) - set(refs), key=_sort_key):
            segment = captions[number]
            issues.append(QualityIssue(category="coherence", code=f"{kind}_not_referenced", severity="info",
                                       message=f"Le {label} {number} n'est cité nulle part dans le texte.",
                                       location=segment.location, excerpt=excerpt(segment.text),
                                       suggestion=f"Citer le {label} dans le texte avant son apparition."))
        for number in sorted(set(duplicates), key=_sort_key):
            issues.append(QualityIssue(category="coherence", code=f"{kind}_duplicate", severity="warning",
                                       message=f"Numéro de {label} utilisé deux fois : {number}.",
                                       suggestion="Renuméroter."))
        missing = _gaps(list(captions))
        if missing:
            issues.append(QualityIssue(category="coherence", code=f"{kind}_gap", severity="info",
                                       message=f"Numérotation des {label}s discontinue : manque {', '.join(missing[:10])}.",
                                       suggestion="Vérifier la numérotation."))
    return issues, summaries.get("figure", {}), summaries.get("table", {})


def _sort_key(number: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in number.split("."))


def _candidate(abbr: str, language: str) -> bool:
    """Abréviation plausible : dans l'alphabet du document (en russe, « VA », « VBA » sont des symboles de
    vecteurs), au plus 5 capitales (au-delà : mot écrit en capitales)."""
    if abbr.upper() in _NOT_ABBREVIATIONS or sum(c.isupper() for c in abbr) > 5:
        return False
    cyrillic = any("А" <= c <= "я" or c == "Ё" for c in abbr)
    return cyrillic if language == "ru" else not cyrillic


def check_abbreviations(segments: list[Segment], language: str = "ru") -> tuple[list[QualityIssue], int]:
    listed: set[str] = set()
    for segment in segments:
        if segment.section and any(w in _fold(segment.section) for w in _ABBREVIATION_SECTIONS):
            listed |= {m.group(1) for m in _ABBREVIATION.finditer(segment.text)}
    first_use: dict[str, Segment] = {}
    defined_at: dict[str, int] = {}
    order: dict[str, int] = {}
    position = 0
    for segment in segments:
        if segment.kind == "heading" or (segment.section and any(w in _fold(segment.section)
                                                                 for w in _ABBREVIATION_SECTIONS)):
            continue
        text = segment.text
        letters = [c for c in text if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
            continue  # ligne en capitales (titre, en-tête d'établissement)
        for match in _ABBREVIATION.finditer(text):
            abbr = match.group(1)
            if not _candidate(abbr, language):
                continue
            position += 1
            before, rest = text[max(0, match.start() - 1):match.start()], text[match.end():]
            defined = (
                (before == "(" and rest.startswith(")"))                     # « теория машин (ТММ) »
                or bool(re.match(r"\s?\(\s?[^\W\d][^()]{3,}\)", rest))       # « ТММ (теория машин) »
                or bool(re.match(r"\s[–—-]\s[^\W\d]{3,}", rest))              # « ТММ – теория машин »
            )
            if abbr not in first_use:
                first_use[abbr] = segment
                order[abbr] = position
            if defined and abbr not in defined_at:
                defined_at[abbr] = position
    issues: list[QualityIssue] = []
    undefined: list[str] = []
    for abbr, segment in first_use.items():
        if abbr in listed:
            continue
        if abbr in defined_at:
            if defined_at[abbr] > order[abbr]:
                issues.append(QualityIssue(category="coherence", code="abbreviation_defined_late", severity="warning",
                                           message=f"L'abréviation {abbr} est employée avant d'être définie.",
                                           location=segment.location, excerpt=excerpt(segment.text),
                                           suggestion="Développer l'abréviation à sa première occurrence."))
        else:
            undefined.append(abbr)
    if undefined:
        issues.append(QualityIssue(category="coherence", code="abbreviation_undefined", severity="info",
                                   message=f"Abréviations jamais développées dans le texte : {', '.join(sorted(undefined)[:30])}.",
                                   suggestion="Les développer à la première occurrence ou les ajouter à la liste des "
                                              "abréviations (si elles ne sont pas d'usage courant)."))
    return issues, len(first_use)


def check_terms(segments: list[Segment], profile: DomainProfile | None, language: str) -> list[QualityIssue]:
    if profile is None:
        return []
    text = _fold(" ".join(s.text for s in segments))
    issues = []
    for term in profile.terminology:
        preferred = getattr(term, language, None)
        for avoid in term.avoid.get(language, []):
            if re.search(r"(?<!\w)" + re.escape(_fold(avoid)) + r"(?!\w)", text):
                issues.append(QualityIssue(category="coherence", code="term_to_avoid", severity="info",
                                           message=f"Formulation à éviter : « {avoid} »"
                                                   + (f" ; préférer « {preferred} »." if preferred else "."),
                                           suggestion="Harmoniser la terminologie du domaine."))
    return issues


def check_decimal_separator(segments: list[Segment], language: str, from_calculations: dict[str, int]) -> list[QualityIssue]:
    counts = dict(from_calculations)
    if not counts:
        for segment in segments:
            if segment.kind == "table":
                for match in _DECIMAL.finditer(segment.text):
                    key = "virgule" if match.group(1) == "," else "point"
                    counts[key] = counts.get(key, 0) + 1
    comma, point = counts.get("virgule", 0), counts.get("point", 0)
    expected = "point" if language == "en" else "virgule"
    issues = []
    if comma and point:
        issues.append(QualityIssue(category="coherence", code="decimal_separator_mixed", severity="warning",
                                   message=f"Séparateur décimal mélangé dans les calculs et tableaux : {comma} avec "
                                           f"virgule, {point} avec point.",
                                   suggestion=f"Utiliser partout la {expected} (usage de la langue du document)."
                                   if expected == "virgule" else "Utiliser partout le point décimal."))
    elif (expected == "virgule" and point >= 3) or (expected == "point" and comma >= 3):
        found = "point" if expected == "virgule" else "virgule"
        issues.append(QualityIssue(category="coherence", code="decimal_separator_unusual", severity="info",
                                   message=f"Séparateur décimal « {found} » alors que l'usage de la langue est la "
                                           f"{expected}." if expected == "virgule" else
                                           "Virgule décimale dans un document en anglais.",
                                   suggestion="Vérifier les exigences de présentation de l'établissement."))
    return issues


def check_consistency(label: str, segments: list[Segment], language: str, profile: DomainProfile | None,
                      *, calc_conflicts: list[QualityIssue], decimal_counts: dict[str, int]) -> ConsistencyReport:
    reference_issues, figures, tables = check_cross_references(segments)
    abbreviation_issues, checked = check_abbreviations(segments, language)
    issues = (list(calc_conflicts) + reference_issues + abbreviation_issues + check_terms(segments, profile, language)
              + check_decimal_separator(segments, language, decimal_counts))
    return ConsistencyReport(label=label, issues=sort_issues(issues), figures=figures, tables=tables,
                             abbreviations_checked=checked)
