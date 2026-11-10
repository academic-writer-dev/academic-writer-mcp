"""Comparaison de deux documents (versions d'un rapport, consigne et rendu, deux supports de cours).

Résultat : similarité globale, structure (titres présents d'un seul côté), passages ajoutés / supprimés /
modifiés, nombres présents d'un seul côté, symboles définis avec des valeurs différentes (contradictions).
Constats seulement : rien n'est corrigé ni fusionné.
"""

from __future__ import annotations

import difflib
import re

from pydantic import BaseModel, Field

from academic_writer.quality.calculations import check_calculations
from academic_writer.quality.models import Segment
from academic_writer.writing.checks import numbers_in


class ChangedPassage(BaseModel):
    kind: str = Field(description="added, removed ou modified.")
    before: str | None
    after: str | None
    similarity: float | None = None


class SymbolConflict(BaseModel):
    symbol: str
    value_a: str
    value_b: str


class DocumentComparison(BaseModel):
    label_a: str
    label_b: str
    similarity: float = Field(description="Similarité globale du texte (0 à 1).")
    headings_only_in_a: list[str]
    headings_only_in_b: list[str]
    changes: list[ChangedPassage]
    numbers_only_in_a: list[str]
    numbers_only_in_b: list[str]
    symbol_conflicts: list[SymbolConflict]
    summary: str
    notice: str = "Comparaison automatique : constats à interpréter ; rien n'est modifié dans les documents."


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def compare(label_a: str, headings_a: list[str], paragraphs_a: list[str], label_b: str, headings_b: list[str],
            paragraphs_b: list[str], max_changes: int = 60) -> DocumentComparison:
    norm_a, norm_b = [_norm(p) for p in paragraphs_a], [_norm(p) for p in paragraphs_b]
    matcher = difflib.SequenceMatcher(None, norm_a, norm_b, autojunk=False)
    changes: list[ChangedPassage] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            changes += [ChangedPassage(kind="removed", before=paragraphs_a[i][:400], after=None) for i in range(i1, i2)]
        elif tag == "insert":
            changes += [ChangedPassage(kind="added", before=None, after=paragraphs_b[j][:400]) for j in range(j1, j2)]
        else:
            for offset in range(max(i2 - i1, j2 - j1)):
                a = paragraphs_a[i1 + offset] if i1 + offset < i2 else None
                b = paragraphs_b[j1 + offset] if j1 + offset < j2 else None
                ratio = difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio() if a and b else None
                kind = "modified" if a and b else "removed" if a else "added"
                changes.append(ChangedPassage(kind=kind, before=a[:400] if a else None, after=b[:400] if b else None,
                                              similarity=round(ratio, 3) if ratio is not None else None))
    text_a, text_b = "\n".join(paragraphs_a), "\n".join(paragraphs_b)
    similarity = round(difflib.SequenceMatcher(None, _norm(text_a)[:60000], _norm(text_b)[:60000],
                                               autojunk=False).ratio(), 3)
    set_a, set_b = {_norm(h) for h in headings_a}, {_norm(h) for h in headings_b}
    numbers_a, numbers_b = numbers_in(text_a), numbers_in(text_b)

    def definitions(paragraphs: list[str]) -> dict[str, tuple[float, str]]:
        report = check_calculations("x", [Segment(p, "paragraph") for p in paragraphs])
        return {d.symbol: (d.si_value, d.value) for d in report.definitions}

    defs_a, defs_b = definitions(paragraphs_a), definitions(paragraphs_b)
    conflicts = [SymbolConflict(symbol=s, value_a=defs_a[s][1], value_b=defs_b[s][1]) for s in sorted(set(defs_a) & set(defs_b))
                 if abs(defs_a[s][0] - defs_b[s][0]) > 0.02 * max(abs(defs_a[s][0]), abs(defs_b[s][0]), 1e-12)]
    counts = {k: sum(c.kind == k for c in changes) for k in ("added", "removed", "modified")}
    summary = (f"Similarité {similarity:.0%} ; {counts['added']} passage(s) ajouté(s), {counts['removed']} supprimé(s), "
               f"{counts['modified']} modifié(s) ; {len(conflicts)} symbole(s) aux valeurs différentes.")
    return DocumentComparison(
        label_a=label_a, label_b=label_b, similarity=similarity,
        headings_only_in_a=[h for h in headings_a if _norm(h) not in set_b][:50],
        headings_only_in_b=[h for h in headings_b if _norm(h) not in set_a][:50], changes=changes[:max_changes],
        numbers_only_in_a=sorted(numbers_a - numbers_b)[:60], numbers_only_in_b=sorted(numbers_b - numbers_a)[:60],
        symbol_conflicts=conflicts, summary=summary)
