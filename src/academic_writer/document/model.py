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
    ocr_confidence: float | None = None


class OcrQuality(BaseModel):
    page: int | None
    mean_confidence: float | None = Field(description="Confiance moyenne de Tesseract (0-100).")
    level: str = Field(description="fiable, à vérifier ou douteux.")
    uncertain_words: list[str] = Field(default_factory=list, description="Mots reconnus avec une confiance < 60.")


def ocr_quality(page: int | None, text) -> OcrQuality:
    confidence = getattr(text, "confidence", None)
    level = ("non mesurée" if confidence is None else "fiable" if confidence >= 85
             else "à vérifier" if confidence >= 70 else "douteux")
    return OcrQuality(page=page, mean_confidence=confidence, level=level,
                      uncertain_words=list(getattr(text, "uncertain", []))[:30])


def ocr_warning(quality: OcrQuality, label: str) -> str | None:
    if quality.level in ("fiable", "non mesurée"):
        return None
    words = f" ; mots douteux : {', '.join(quality.uncertain_words[:8])}" if quality.uncertain_words else ""
    return (f"{label} : OCR {quality.level} (confiance moyenne {quality.mean_confidence:.0f} %){words}. "
            "Vérifier ce passage sur l'original avant de l'utiliser.")


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
    ocr_quality: list[OcrQuality] = Field(default_factory=list)
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
