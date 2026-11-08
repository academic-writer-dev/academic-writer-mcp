"""Lecteur TXT et Markdown, avec détection automatique de l'encodage."""

from __future__ import annotations

import codecs
import re
from pathlib import Path

from charset_normalizer import from_bytes

from academic_writer.document.base import ExtractionContext
from academic_writer.document.layout import BULLET_RE
from academic_writer.document.model import Block, ExtractedDocument, TableData

_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_SETEXT_1 = re.compile(r"^=+\s*$")
_SETEXT_2 = re.compile(r"^-+\s*$")
_TABLE_SEP = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def decode_text(data: bytes) -> tuple[str, str]:
    """Renvoie (texte, encodage). Ordre : BOM, UTF-8 strict, détection statistique, cp1251."""
    for bom, encoding in ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                          (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            return data.decode(encoding, errors="replace"), encoding
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    best = from_bytes(data).best()
    if best is not None and best.encoding:
        return str(best), best.encoding
    return data.decode("cp1251", errors="replace"), "cp1251"


class TextExtractor:
    name = "text"

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument:
        text, encoding = decode_text(path.read_bytes())
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        is_markdown = path.suffix.lower() == ".md"
        blocks, tables = (_parse_markdown(text) if is_markdown else (_parse_plain(text), []))
        warnings = list(ctx.warnings)
        if encoding not in ("utf-8", "utf-8-sig", "ascii"):
            warnings.append(f"Encodage détecté : {encoding} (vérifier les caractères accentués/cyrilliques).")
        return ExtractedDocument(
            format="markdown" if is_markdown else "text", extractor=self.name,
            blocks=blocks, tables=tables, warnings=warnings, detected_encoding=encoding,
        )


def _parse_plain(text: str) -> list[Block]:
    blocks: list[Block] = []
    for chunk in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if all(BULLET_RE.match(line) for line in lines):
            blocks.extend(Block(type="list_item", text=line) for line in lines)
        else:
            blocks.append(Block(type="paragraph", text=" ".join(lines)))
    return blocks


def _parse_markdown(text: str) -> tuple[list[Block], list[TableData]]:
    blocks: list[Block] = []
    tables: list[TableData] = []
    paragraph: list[str] = []
    lines = text.split("\n")
    i = 0
    in_code = False

    def flush() -> None:
        if paragraph:
            blocks.append(Block(type="paragraph", text=" ".join(p.strip() for p in paragraph)))
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_code = not in_code
            i += 1
            continue
        if in_code:
            blocks.append(Block(type="paragraph", text=line, style="code"))
            i += 1
            continue
        if not stripped:
            flush()
            i += 1
            continue
        match = _ATX.match(stripped)
        if match:
            flush()
            blocks.append(Block(type="heading", text=match.group(2), level=len(match.group(1))))
            i += 1
            continue
        if i + 1 < len(lines) and paragraph == [] and lines[i + 1].strip() and (
            _SETEXT_1.match(lines[i + 1]) or (_SETEXT_2.match(lines[i + 1]) and not BULLET_RE.match(stripped))
        ):
            blocks.append(Block(type="heading", text=stripped, level=1 if _SETEXT_1.match(lines[i + 1]) else 2))
            i += 2
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            flush()
            rows = [_split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i].strip()))
                i += 1
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            index = len(tables) + 1
            tables.append(TableData(index=index, rows=rows, n_rows=len(rows), n_cols=width))
            blocks.append(Block(type="table", table_index=index, text=f"[Tableau {index}]"))
            continue
        if BULLET_RE.match(stripped):
            flush()
            blocks.append(Block(type="list_item", text=BULLET_RE.sub("", stripped, count=1)
                                if stripped[:1] in "-*+" else stripped))
            i += 1
            continue
        if stripped.startswith(">"):
            flush()
            blocks.append(Block(type="note", text=stripped.lstrip("> ").strip()))
            i += 1
            continue
        paragraph.append(stripped)
        i += 1
    flush()
    return blocks, tables


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]
