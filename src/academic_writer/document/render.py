"""Mise en texte (Markdown) et découpage en passages pour la recherche."""

from __future__ import annotations

from dataclasses import dataclass

from academic_writer.document.model import Block, ExtractedDocument, TableData

_CHUNK_TARGET = 1200


def table_to_markdown(table: TableData, max_rows: int | None = None) -> str:
    rows = table.rows if max_rows is None else table.rows[:max_rows]
    if not rows:
        return ""
    escape = lambda cell: cell.replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(escape(c) for c in rows[0]) + " |",
             "| " + " | ".join("---" for _ in rows[0]) + " |"]
    lines += ["| " + " | ".join(escape(c) for c in row) + " |" for row in rows[1:]]
    if max_rows is not None and len(table.rows) > max_rows:
        lines.append(f"*(… {len(table.rows) - max_rows} lignes supplémentaires : voir extract_document_tables)*")
    if table.truncated:
        lines.append("*(tableau tronqué aux limites configurées)*")
    return "\n".join(lines)


def block_to_markdown(block: Block, document: ExtractedDocument, table_preview_rows: int = 15) -> str:
    if block.type == "heading":
        level = max(1, min((block.level or 1) if block.level != 0 else 1, 6))
        marker = " *(titre supposé)*" if block.origin == "font_heuristic" else ""
        return "#" * level + " " + block.text + marker
    if block.type == "list_item":
        return "- " + block.text
    if block.type == "table" and block.table_index:
        table = document.tables[block.table_index - 1]
        title = f"**Tableau {table.index}**" + (f" — {table.title}" if table.title else "")
        return title + "\n\n" + table_to_markdown(table, table_preview_rows)
    if block.type == "image":
        page = f", page {block.page}" if block.page else ""
        return f"[Image {block.image_index}{page}]"
    if block.type == "caption":
        return f"*{block.text}*"
    if block.type == "note":
        return f"> [Note] {block.text}"
    prefix = "[OCR] " if block.origin == "ocr" else ""
    return prefix + block.text


@dataclass
class Chunk:
    seq: int
    page: int | None
    heading: str | None
    text: str


def build_chunks(document: ExtractedDocument) -> list[Chunk]:
    """Passages d'environ 1200 caractères, sans franchir un titre, avec le titre courant."""
    chunks: list[Chunk] = []
    heading: str | None = None
    buffer: list[str] = []
    start_page: int | None = None

    def flush() -> None:
        nonlocal buffer, start_page
        text = "\n".join(buffer).strip()
        if text:
            chunks.append(Chunk(seq=len(chunks) + 1, page=start_page, heading=heading, text=text))
        buffer = []
        start_page = None

    for block in document.blocks:
        if block.type == "heading":
            flush()
            heading = block.text
            continue
        if block.type == "image":
            continue
        if block.type == "table" and block.table_index:
            table = document.tables[block.table_index - 1]
            text = "\n".join(" | ".join(cell for cell in row if cell) for row in table.rows)
        else:
            text = block.text
        if not text.strip():
            continue
        if buffer and sum(len(b) for b in buffer) + len(text) > _CHUNK_TARGET:
            flush()
        if start_page is None:
            start_page = block.page
        buffer.append(text)
    flush()
    return chunks
