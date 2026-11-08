"""Représentation commune d'un document extrait, quel que soit son format."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockType = Literal["heading", "paragraph", "list_item", "table", "image", "caption", "note"]
BlockOrigin = Literal["native", "outline", "font_heuristic", "ocr"]


class Block(BaseModel):
    """Unité de contenu, dans l'ordre de lecture."""

    type: BlockType
    text: str = ""
    level: int | None = Field(default=None, description="Niveau de titre (1 = chapitre).")
    page: int | None = Field(default=None, description="Numéro de page / diapositive / feuille (à partir de 1).")
    style: str | None = None
    origin: BlockOrigin = "native"
    table_index: int | None = None
    image_index: int | None = None


class TableData(BaseModel):
    index: int
    page: int | None = None
    title: str | None = None
    rows: list[list[str]]
    n_rows: int
    n_cols: int
    truncated: bool = False


class ImageInfo(BaseModel):
    index: int
    page: int | None = None
    name: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    stored_path: str | None = Field(default=None, description="Copie extraite, relative au dossier de données.")
    ocr_text: str | None = None


class Heading(BaseModel):
    level: int
    text: str
    page: int | None = None
    origin: BlockOrigin = "native"


class ExtractedDocument(BaseModel):
    format: str
    extractor: str
    page_count: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    blocks: list[Block] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    images: list[ImageInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ocr_pages: list[int] = Field(default_factory=list)
    detected_encoding: str | None = None

    @property
    def headings(self) -> list[Heading]:
        return [
            Heading(level=b.level if b.level is not None else 1, text=b.text, page=b.page, origin=b.origin)
            for b in self.blocks
            if b.type == "heading"
        ]

    @property
    def char_count(self) -> int:
        return sum(len(b.text) for b in self.blocks)
