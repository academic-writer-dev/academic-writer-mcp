"""OCR via Tesseract (programme externe, licence Apache-2.0).

Tesseract est appelé directement (sans shell), avec délai maximal. Les images
temporaires sont écrites dans un dossier temporaire supprimé après usage.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from academic_writer.core.config import Settings

logger = logging.getLogger("academic_writer.ocr")

_DEFAULT_WINDOWS_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)
_LANG_CODES = {"fr": "fra", "ru": "rus", "en": "eng"}
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class OcrError(RuntimeError):
    pass


class OcrEngine:
    def __init__(self, executable: Path, tessdata_dir: Path | None, timeout: int) -> None:
        self.executable = executable
        self.tessdata_dir = tessdata_dir
        self.timeout = timeout
        self._languages: set[str] | None = None

    @classmethod
    def detect(cls, settings: Settings) -> OcrEngine | None:
        candidates: list[Path] = []
        if settings.tesseract_cmd:
            candidates.append(settings.tesseract_cmd)
        found = shutil.which("tesseract")
        if found:
            candidates.append(Path(found))
        candidates.extend(_DEFAULT_WINDOWS_PATHS)
        for candidate in candidates:
            if candidate.is_file():
                return cls(candidate, settings.effective_tessdata_dir, settings.ocr_timeout_seconds)
        return None

    def _base_args(self) -> list[str]:
        args = [str(self.executable)]
        if self.tessdata_dir is not None:
            args += ["--tessdata-dir", str(self.tessdata_dir)]
        return args

    def _run(self, args: list[str]) -> str:
        try:
            completed = subprocess.run(
                args, capture_output=True, timeout=self.timeout, check=False,
                creationflags=_CREATE_NO_WINDOW, stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError(f"OCR interrompu : délai de {self.timeout} s dépassé.") from exc
        except OSError as exc:
            raise OcrError(f"Impossible de lancer Tesseract : {exc}") from exc
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", errors="replace").strip()[:300]
            raise OcrError(f"Tesseract a échoué (code {completed.returncode}) : {message}")
        return completed.stdout.decode("utf-8", errors="replace")

    def available_languages(self) -> set[str]:
        if self._languages is None:
            output = self._run(self._base_args() + ["--list-langs"])
            self._languages = {line.strip() for line in output.splitlines()[1:] if line.strip()}
        return self._languages

    def languages_for(self, project_language: str) -> str:
        """Langue du projet en premier, puis les autres langues prises en charge disponibles."""
        available = self.available_languages()
        primary = _LANG_CODES.get(project_language, "eng")
        ordered = [primary] + [code for code in ("eng", "fra", "rus") if code != primary]
        chosen = [code for code in ordered if code in available]
        return "+".join(chosen) if chosen else "eng"

    def recognize_file(self, image_path: Path, languages: str) -> str:
        args = self._base_args() + [str(image_path), "stdout", "-l", languages, "--psm", "3"]
        return self._run(args)

    def recognize_pil(self, image: object, languages: str) -> str:
        with tempfile.TemporaryDirectory(prefix="aw-ocr-") as tmp:
            path = Path(tmp) / "page.png"
            image.save(path, format="PNG")  # type: ignore[attr-defined]
            return self.recognize_file(path, languages)

    def recognize_bytes(self, data: bytes, suffix: str, languages: str) -> str:
        with tempfile.TemporaryDirectory(prefix="aw-ocr-") as tmp:
            path = Path(tmp) / f"image{suffix}"
            path.write_bytes(data)
            return self.recognize_file(path, languages)
