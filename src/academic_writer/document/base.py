"""Interface commune des lecteurs de documents et outils partagés."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from academic_writer.core.config import Settings
from academic_writer.document.model import ExtractedDocument, ImageInfo
from academic_writer.document.ocr import OcrEngine

OcrMode = Literal["auto", "never", "always"]

_IMAGE_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff", ".emf": "image/emf",
    ".wmf": "image/wmf", ".jp2": "image/jp2", ".webp": "image/webp", ".svg": "image/svg+xml",
}


@dataclass
class ExtractionContext:
    settings: Settings
    images_dir: Path | None = None
    ocr: OcrEngine | None = None
    ocr_mode: OcrMode = "auto"
    ocr_languages: str = "eng"
    images: list[ImageInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def can_store_image(self) -> bool:
        return self.images_dir is not None and len(self.images) < self.settings.extract_max_images

    def store_image(self, data: bytes, suffix: str, page: int | None, name: str | None = None,
                    width: int | None = None, height: int | None = None) -> ImageInfo | None:
        """Enregistre une image extraite (dossier « derived », jamais dans les originaux)."""
        if not self.can_store_image():
            if self.images_dir is not None and len(self.images) == self.settings.extract_max_images:
                self.warnings.append(f"Limite de {self.settings.extract_max_images} images atteinte : images suivantes ignorées.")
            return None
        suffix = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
        index = len(self.images) + 1
        assert self.images_dir is not None
        self.images_dir.mkdir(parents=True, exist_ok=True)
        path = self.images_dir / f"image-{index:04d}{suffix}"
        path.write_bytes(data)
        info = ImageInfo(
            index=index, page=page, name=name, mime_type=_IMAGE_MIME.get(suffix),
            width=width, height=height, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
            stored_path=self.relative(path),
        )
        self.images.append(info)
        return info

    def relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.settings.data_dir).as_posix()
        except ValueError:
            return path.as_posix()


class Extractor(Protocol):
    name: str

    def extract(self, path: Path, ctx: ExtractionContext) -> ExtractedDocument: ...


def get_extractor(extension: str, settings: Settings) -> Extractor:
    extension = extension.lower()
    if extension in (".txt", ".md"):
        from academic_writer.document.text_reader import TextExtractor
        return TextExtractor()
    if extension == ".docx":
        from academic_writer.document.docx_reader import DocxExtractor
        return DocxExtractor()
    if extension == ".pdf":
        if settings.pdf_backend == "pymupdf":
            from academic_writer.document.pdf_pymupdf import PyMuPdfExtractor
            return PyMuPdfExtractor()
        from academic_writer.document.pdf_pdfium import PdfiumExtractor
        return PdfiumExtractor()
    if extension == ".xlsx":
        from academic_writer.document.xlsx_reader import XlsxExtractor
        return XlsxExtractor()
    if extension == ".pptx":
        from academic_writer.document.pptx_reader import PptxExtractor
        return PptxExtractor()
    raise ValueError(f"Aucun lecteur pour le format {extension}")


def clean_cell(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def trim_table(rows: list[list[str]], max_rows: int, max_cols: int) -> tuple[list[list[str]], bool]:
    """Supprime lignes/colonnes vides en fin de tableau et applique les limites."""
    rows = [list(r) for r in rows]
    while rows and not any(cell for cell in rows[-1]):
        rows.pop()
    width = max((len(r) for r in rows), default=0)
    while width and not any(len(r) >= width and r[width - 1] for r in rows):
        width -= 1
    truncated = len(rows) > max_rows or width > max_cols
    rows = [(r + [""] * width)[: min(width, max_cols)] for r in rows[:max_rows]]
    return rows, truncated
