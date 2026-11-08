"""Reconstruction de la structure (paragraphes, titres, listes) à partir de lignes de texte.

Utilisé pour les PDF, qui ne contiennent pas de structure logique fiable.
Les titres détectés par la taille de police sont marqués ``font_heuristic`` :
ce sont des hypothèses, pas des certitudes.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable

from academic_writer.document.model import Block

BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·\-–—*]|\d{1,2}[.)]|[a-zа-я]\))\s+")
_SENTENCE_END = (".", "!", "?", ":", ";", "…")


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def heading_levels_from_sizes(lines: Iterable[tuple[str, float]]) -> dict[str, int]:
    """Associe aux lignes nettement plus grandes que le corps du texte un niveau de titre (1 à 3)."""
    lines = [(t.strip(), s) for t, s in lines if t and t.strip() and s > 0]
    if len(lines) < 3:
        return {}
    weighted: list[float] = []
    for text, size in lines:
        weighted.extend([round(size * 2) / 2] * max(1, min(len(text), 200)))
    body = statistics.median(weighted)
    candidates = [(t, round(s * 2) / 2) for t, s in lines if s >= body * 1.15 and _looks_like_heading(t)]
    if not candidates:
        return {}
    sizes = sorted({s for _, s in candidates}, reverse=True)[:3]
    level_of = {size: index + 1 for index, size in enumerate(sizes)}
    return {normalize(t): level_of[s] for t, s in candidates if s in level_of}


def _looks_like_heading(text: str) -> bool:
    if not (2 <= len(text) <= 150):
        return False
    if len(text.split()) > 18 or text.endswith((".", ",", ";")):
        return False
    # Au moins un vrai mot (3 lettres consécutives) : exclut les cotes et repères de schémas (ω1, a', B2…).
    return _WORD3.search(text) is not None and sum(ch.isalpha() for ch in text) >= 4


_WORD3 = re.compile(r"[^\W\d_]{3,}")


def blocks_from_lines(
    lines: list[str],
    page: int | None,
    heading_map: dict[str, int] | None = None,
    outline_map: dict[str, int] | None = None,
    origin_override: str | None = None,
) -> list[Block]:
    """Regroupe des lignes en blocs. ``outline_map`` (signets du PDF) est prioritaire sur ``heading_map``."""
    heading_map = heading_map or {}
    outline_map = outline_map or {}
    blocks: list[Block] = []
    buffer: list[str] = []
    buffer_is_list = False

    def flush() -> None:
        nonlocal buffer, buffer_is_list
        if buffer:
            text = _join_lines(buffer)
            if text:
                block_type = "list_item" if buffer_is_list else "paragraph"
                blocks.append(Block(type=block_type, text=text, page=page, origin=origin_override or "native"))
        buffer = []
        buffer_is_list = False

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        key = normalize(line)
        if key in outline_map or key in heading_map:
            flush()
            if key in outline_map:
                blocks.append(Block(type="heading", text=line, level=outline_map[key], page=page, origin="outline"))
            else:
                blocks.append(Block(type="heading", text=line, level=heading_map[key], page=page,
                                    origin="font_heuristic"))
            continue
        is_bullet = bool(BULLET_RE.match(line))
        if is_bullet:
            flush()
            buffer = [line]
            buffer_is_list = True
            continue
        if buffer and _starts_new_paragraph(buffer[-1], line):
            flush()
        buffer.append(line)
    flush()
    return blocks


def _starts_new_paragraph(previous: str, current: str) -> bool:
    if previous.endswith("-"):
        return False
    return previous.endswith(_SENTENCE_END) and (current[:1].isupper() or current[:1].isdigit())


def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        if not text:
            text = line
        elif text.endswith("-") and line[:1].islower():
            text = text[:-1] + line  # césure en fin de ligne
        else:
            text += " " + line
    return " ".join(text.split())
