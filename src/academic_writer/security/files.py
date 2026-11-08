"""Inspection des fichiers avant import.

Vérifie : extension autorisée, taille, cohérence entre extension et contenu réel
(signature), archives Office (zip-bomb, macros, chiffrement), fichiers texte binaires.
Les éléments à risque non bloquants (JavaScript dans un PDF, objets incorporés)
sont signalés dans ``warnings``.

Aucun fichier n'est exécuté ni décompressé sur le disque.
"""

from __future__ import annotations

import codecs
import hashlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from academic_writer.core.config import Settings
from academic_writer.core.errors import SecurityViolation, ValidationFailed

MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

_OOXML_MAIN_DIR = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}
_PDF_RISK_MARKERS = {
    b"/JavaScript": "Le PDF contient du JavaScript (il ne sera jamais exécuté).",
    b"/Launch": "Le PDF contient une action de lancement de programme (ignorée).",
    b"/EmbeddedFile": "Le PDF contient des fichiers incorporés (non extraits).",
}
_CHUNK = 1024 * 1024


@dataclass
class FileInspection:
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    warnings: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_file(path: Path, settings: Settings) -> FileInspection:
    extension = path.suffix.lower()
    if extension not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)
        raise ValidationFailed(f"Format non accepté : '{extension or '(aucune)'}'. Formats acceptés : {allowed}.")

    size = path.stat().st_size
    if size == 0:
        raise ValidationFailed("Le fichier est vide.")
    if size > settings.max_file_size_bytes:
        raise ValidationFailed(
            f"Fichier trop volumineux ({size / 1_048_576:.1f} Mo > {settings.max_file_size_mb} Mo autorisés)."
        )

    with path.open("rb") as handle:
        head = handle.read(8192)

    warnings: list[str] = []
    if extension == ".pdf":
        _check_pdf(path, head, warnings)
    elif extension in _OOXML_MAIN_DIR:
        _check_ooxml(path, extension, head, settings, warnings)
    else:
        _check_text(head, warnings)

    return FileInspection(
        extension=extension,
        mime_type=MIME_TYPES[extension],
        size_bytes=size,
        sha256=sha256_file(path),
        warnings=warnings,
    )


def _check_pdf(path: Path, head: bytes, warnings: list[str]) -> None:
    if b"%PDF-" not in head[:1024]:
        raise SecurityViolation("Le contenu ne correspond pas à un PDF (signature %PDF absente).")
    found: set[bytes] = set()
    overlap = max(len(m) for m in _PDF_RISK_MARKERS)
    previous_tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            window = previous_tail + chunk
            for marker in _PDF_RISK_MARKERS:
                if marker in window:
                    found.add(marker)
            previous_tail = chunk[-overlap:]
    warnings.extend(_PDF_RISK_MARKERS[m] for m in _PDF_RISK_MARKERS if m in found)


def _check_ooxml(path: Path, extension: str, head: bytes, settings: Settings, warnings: list[str]) -> None:
    if not head.startswith(b"PK\x03\x04"):
        raise SecurityViolation(
            f"Le contenu ne correspond pas à un fichier {extension} (archive Office attendue). "
            "Les anciens formats (.doc, .xls, .ppt) doivent d'abord être convertis."
        )
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise ValidationFailed(f"Archive {extension} corrompue : {exc}") from exc

    if len(infos) > settings.zip_max_entries:
        raise SecurityViolation(f"Archive suspecte : trop d'éléments ({len(infos)}).")

    total = 0
    names: set[str] = set()
    for info in infos:
        name = info.filename.replace("\\", "/")
        names.add(name)
        if name.startswith("/") or ".." in name.split("/") or ":" in name:
            raise SecurityViolation("Archive suspecte : chemin interne dangereux.")
        if info.flag_bits & 0x1:
            raise ValidationFailed("Le document est chiffré / protégé par mot de passe. Retirez la protection puis réimportez-le.")
        total += info.file_size
        if (
            info.file_size > 1_048_576
            and info.compress_size > 0
            and info.file_size / info.compress_size > settings.zip_max_ratio
        ):
            raise SecurityViolation("Archive suspecte : taux de compression anormal (zip-bomb possible).")
    if total > settings.zip_max_uncompressed_mb * 1_048_576:
        raise SecurityViolation("Archive suspecte : taille décompressée excessive.")

    if "[Content_Types].xml" not in names:
        raise SecurityViolation(f"Le fichier n'est pas un document Office {extension} valide.")
    if not any(n.startswith(_OOXML_MAIN_DIR[extension]) for n in names):
        raise SecurityViolation(
            f"Le contenu ne correspond pas à l'extension {extension} (fichier renommé ?)."
        )
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        raise SecurityViolation("Le document contient des macros VBA : import refusé pour raison de sécurité.")
    if any("/embeddings/" in n or "/activeX/" in n for n in names):
        warnings.append("Le document contient des objets incorporés ou ActiveX (non exécutés, non extraits).")
    if any("externalLink" in n for n in names):
        warnings.append("Le document contient des liens vers des fichiers externes (non suivis).")


def _check_text(head: bytes, warnings: list[str]) -> None:
    if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        warnings.append("Fichier texte encodé en UTF-16.")
        return
    if b"\x00" in head:
        raise SecurityViolation("Le fichier texte contient des données binaires (fichier renommé ?).")
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    try:
        decoder.decode(head, final=False)
    except UnicodeDecodeError:
        warnings.append(
            "Le fichier texte n'est pas en UTF-8 (probablement Windows-1251/1252) : "
            "l'encodage sera détecté lors de l'extraction."
        )
