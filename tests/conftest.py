"""Fixtures communes.

Chaque test s'exécute dans un dossier temporaire isolé : aucun test ne lit la
configuration réelle de l'utilisateur ni n'écrit dans son dossier de données.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from academic_writer.core.config import CONFIG_ENV_VAR, ENV_PREFIX, Settings
from academic_writer.server.services import Services, build_services, set_services


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(ENV_PREFIX):
            monkeypatch.delenv(key)
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "config-absent.toml"))
    # filet de sécurité : un Settings() construit sans argument ne touche jamais au vrai dossier de données
    monkeypatch.setenv(f"{ENV_PREFIX}DATA_DIR", str(tmp_path / "default-data"))


@pytest.fixture
def inbox(tmp_path: Path) -> Path:
    """Dossier « utilisateur » autorisé pour les imports."""
    path = tmp_path / "inbox"
    path.mkdir()
    return path


@pytest.fixture
def settings(tmp_path: Path, inbox: Path) -> Settings:
    # Port inutilisé : les tests ne doivent jamais utiliser un vrai LanguageTool ou Ollama local.
    s = Settings(data_dir=tmp_path / "data", allowed_import_dirs=[inbox], languagetool_url="http://127.0.0.1:9",
                 ollama_url="http://127.0.0.1:9")
    s.ensure_dirs()
    return s


@pytest.fixture(autouse=True)
def services(settings: Settings) -> Services:
    built = build_services(settings)
    built.ai._ollama_probe = lambda: None  # tests indépendants d'un éventuel Ollama local
    set_services(built)
    yield built
    set_services(None)


# --- fabrication de fichiers de test ------------------------------------

def make_ooxml(path: Path, main_dir: str, extra: dict[str, bytes] | None = None) -> Path:
    """Crée une archive Office minimale (structure OOXML valide pour l'inspection)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        archive.writestr(f"{main_dir}document.xml", "<document>Bonjour</document>")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def make_docx(path: Path, extra: dict[str, bytes] | None = None) -> Path:
    return make_ooxml(path, "word/", extra)


def make_pdf(path: Path, body: bytes = b"") -> Path:
    path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n" + body + b"\n%%EOF\n")
    return path
