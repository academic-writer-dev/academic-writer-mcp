"""Extraction depuis les documents de l'enseignant : barème (critères, points) et définitions du cours (fr/ru/en).

Propositions à faire confirmer : rien n'est enregistré automatiquement dans le profil de l'enseignant.
"""

from __future__ import annotations

import re

_UNIT = r"\s*(?:points?|pts?\.?|балл(?:а|ов)?|б\.|marks?)"
RUBRIC_LINE = re.compile(
    r"^\s*(?:[-–•*]|\d{1,2}[.)])?\s*(?P<crit>[^\n]{3,200}?)\s*(?:[(\[]\s*(?P<p1>\d+(?:[.,]\d+)?)" + _UNIT
    + r"\s*[)\]]|[:–—-]\s*(?P<p2>\d+(?:[.,]\d+)?)" + _UNIT + r")\s*\.?\s*$", re.IGNORECASE)
RUBRIC_HEADER = re.compile(r"crit[eè]re|criteri|критери|показател|élément évalué", re.IGNORECASE)
POINTS_HEADER = re.compile(r"points?|pts|балл|barème|score|note|marks?", re.IGNORECASE)

_TERM = r"(?P<term>[A-ZÀ-ÝА-ЯЁa-zà-ÿа-яё][\w’'\- ]{1,60}?)"
DEFINITION_AFTER = re.compile(
    r"(?:^|(?<=[.;:]\s))" + _TERM + r"\s*(?:,\s*)?(?:est\s+défini(?:e)?\s+comme|se\s+définit\s+comme|désigne|"
    r"correspond\s+à|—\s*это|–\s*это|-\s*это|is\s+defined\s+as|refers\s+to|denotes)\s+(?P<def>[^.;]{8,400})[.;]",
    re.IGNORECASE)
DEFINITION_BEFORE = re.compile(  # « … называется кинематической парой. »
    r"(?P<def>[^.;]{8,400}?)\s+называ(?:ется|ют(?:ся)?)\s+(?P<term>[^.;,]{2,60})[.;]", re.IGNORECASE)


def rubric_lines(text: str) -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    for line in text.splitlines():
        match = RUBRIC_LINE.match(line)
        if match:
            criterion = match.group("crit").strip(" :–—-")
            points = match.group("p1") or match.group("p2")
            if criterion and not criterion.isdigit():
                found.append((criterion, float(points.replace(",", "."))))
    return found


def rubric_from_table(rows: list[list[str]]) -> list[tuple[str, float | None]]:
    if not rows:
        return []
    header = rows[0]
    crit_col = next((i for i, h in enumerate(header) if RUBRIC_HEADER.search(h or "")), None)
    pts_col = next((i for i, h in enumerate(header) if POINTS_HEADER.search(h or "") and i != crit_col), None)
    if crit_col is None or pts_col is None:
        return []
    found: list[tuple[str, float | None]] = []
    for row in rows[1:]:
        if len(row) <= max(crit_col, pts_col) or not row[crit_col].strip():
            continue
        number = re.search(r"\d+(?:[.,]\d+)?", row[pts_col] or "")
        found.append((row[crit_col].strip(), float(number.group(0).replace(",", ".")) if number else None))
    return found


_ARTICLE = re.compile(r"^(?:un|une|le|la|les|l['’]|the|an?)\s*", re.IGNORECASE)


def definitions(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    clean = " ".join(text.split())
    for match in DEFINITION_AFTER.finditer(clean):
        term = _ARTICLE.sub("", match.group("term").strip(" ,"))
        if term and len(term.split()) <= 6:
            found.append((term, match.group("def").strip(" ,")))
    for match in DEFINITION_BEFORE.finditer(clean):
        found.append((match.group("term").strip(" ,"), match.group("def").strip(" ,")))
    return found
