"""Configuration d'Academic Writer.

Ordre de priorité (du plus fort au plus faible) :
1. paramètres passés explicitement (tests, code) ;
2. variables d'environnement préfixées ``ACADEMIC_WRITER_`` (ex. ``ACADEMIC_WRITER_DATA_DIR``) ;
3. fichier TOML : ``%APPDATA%\\AcademicWriter\\config.toml``
   (emplacement modifiable via la variable ``ACADEMIC_WRITER_CONFIG``) ;
4. valeurs par défaut ci-dessous.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

ENV_PREFIX = "ACADEMIC_WRITER_"
CONFIG_ENV_VAR = "ACADEMIC_WRITER_CONFIG"

#: Formats acceptés à l'import (l'extraction de certains arrive en Phase 3).
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".docx", ".pdf", ".txt", ".md", ".xlsx", ".pptx")


def default_config_file() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / "AcademicWriter" / "config.toml"


def default_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "AcademicWriter"


def config_file_path() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    return Path(override) if override else default_config_file()


class Settings(BaseSettings):
    """Réglages validés de l'application."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore")

    data_dir: Path = Field(
        default_factory=default_data_dir,
        description="Dossier des données locales (projets, base SQLite, journaux, sauvegardes).",
    )
    mode: Literal["local", "connected"] = Field(
        default="local",
        description="'local' : aucun accès réseau. 'connected' : services externes autorisés "
        "(vérification bibliographique, fournisseurs IA) après consentement.",
    )
    software_execution: bool = Field(
        default=False, description="Autorise le lancement de traitements dans les logiciels détectés (Python, Excel, "
        "Octave, R, Scilab, CalculiX…), toujours avec confirmation à chaque lancement. Désactivé par défaut.")
    software_timeout_s: int = Field(default=180, ge=10, le=1800, description="Durée maximale d'un traitement.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    max_file_size_mb: int = Field(default=100, ge=1, le=2048)
    allowed_extensions: list[str] = Field(default_factory=lambda: list(SUPPORTED_EXTENSIONS))
    allowed_import_dirs: list[Path] = Field(
        default_factory=lambda: [Path.home()],
        description="Seuls les fichiers situés sous ces dossiers peuvent être importés.",
    )
    zip_max_uncompressed_mb: int = Field(default=1024, ge=1)
    zip_max_entries: int = Field(default=20_000, ge=1)
    zip_max_ratio: int = Field(default=200, ge=10, description="Taux de compression maximal (anti zip-bomb).")

    # --- extraction (Phase 3) ---
    pdf_backend: Literal["auto", "pdfium", "pymupdf"] = Field(
        default="auto",
        description="'auto' et 'pdfium' : pypdfium2 + pdfplumber (licences permissives). "
        "'pymupdf' : PyMuPDF (AGPL, option installable à part : uv sync --extra pymupdf).",
    )
    extract_max_pages: int = Field(default=2000, ge=1)
    extract_max_images: int = Field(default=300, ge=0)
    extract_max_table_rows: int = Field(default=5000, ge=1)
    extract_max_table_cols: int = Field(default=100, ge=1)

    # --- OCR (Tesseract) ---
    ocr_enabled: bool = True
    tesseract_cmd: Path | None = Field(default=None, description="Chemin de tesseract.exe (détection auto si vide).")
    tessdata_dir: Path | None = Field(default=None, description="Dossier des langues (défaut : <data_dir>/tessdata s'il existe).")
    ocr_dpi: int = Field(default=300, ge=72, le=600)
    ocr_max_pages: int = Field(default=30, ge=1, le=1000)
    ocr_timeout_seconds: int = Field(default=120, ge=5)
    ocr_min_chars_per_page: int = Field(
        default=25, ge=0, description="En dessous, une page PDF est considérée comme scannée."
    )

    # --- moteur de rédaction ---
    writing_engine: Literal["auto", "assistant", "ollama", "anthropic", "openai"] = Field(
        default="auto",
        description="auto : meilleur moteur disponible (fournisseur cloud autorisé > modèle local > assistant). "
        "assistant : l'assistant MCP rédige, le serveur encadre. ollama : modèle local. anthropic/openai : cloud.",
    )

    # --- modèle local (Ollama) : aucun envoi externe ---
    ollama_url: str = Field(default="http://localhost:11434", description="Serveur Ollama LOCAL uniquement.")
    ollama_model: str = "qwen3.5:4b"
    ollama_num_ctx: int = Field(default=8192, ge=2048, le=262144, description="Contexte (limité par la mémoire vidéo).")
    ollama_think: bool | Literal["low", "medium", "high"] = False
    ollama_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    ollama_keep_alive: str = Field(default="30m", description="Durée de maintien du modèle en mémoire après un appel.")

    # --- fournisseurs IA cloud (actifs uniquement en mode 'connected' + consentement par projet) ---
    ai_default_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    anthropic_refusal_fallback: bool = Field(
        default=True, description="Repli serveur automatique en cas de refus (paramètre fallbacks='default')."
    )
    openai_model: str = "gpt-5.5"
    ai_max_output_tokens: int = Field(default=16000, ge=256, le=32000)
    ai_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    ai_monthly_token_budget: int | None = Field(
        default=None, ge=1000, description="Plafond mensuel (tokens entrée + sortie, tous fournisseurs). Vide = sans plafond."
    )
    ai_prices_per_million: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Tarifs saisis par l'utilisateur, ex. {'claude-opus-5-5': {'input': 4.0, 'output': 20.0}} "
        "(USD par million de tokens). Sans tarif, aucun coût n'est estimé.",
    )

    # --- LanguageTool local ---
    languagetool_url: str = Field(default="http://localhost:8081", description="Serveur LanguageTool LOCAL uniquement.")
    languagetool_dir: Path | None = Field(default=None, description="Défaut : <data_dir>/languagetool.")
    java_cmd: Path | None = Field(default=None, description="Chemin de java.exe (détection auto si vide).")

    @field_validator("languagetool_url", "ollama_url")
    @classmethod
    def _local_services_only(cls, value: str) -> str:
        from urllib.parse import urlparse

        host = urlparse(value).hostname or ""
        if host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Ce service doit être local (localhost) : aucun texte ne doit partir vers un serveur tiers.")
        return value.rstrip("/")

    @field_validator("allowed_extensions")
    @classmethod
    def _normalize_extensions(cls, value: list[str]) -> list[str]:
        normalized = []
        for ext in value:
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            if ext not in SUPPORTED_EXTENSIONS:
                raise ValueError(f"Extension non prise en charge : {ext}")
            normalized.append(ext)
        return sorted(set(normalized))

    @field_validator("allowed_import_dirs")
    @classmethod
    def _require_absolute_dirs(cls, value: list[Path]) -> list[Path]:
        for path in value:
            if not path.is_absolute():
                raise ValueError(f"Dossier d'import non absolu : {path}")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=config_file_path()),
        )

    # --- chemins dérivés -------------------------------------------------
    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "academic_writer.db"

    @property
    def effective_tessdata_dir(self) -> Path | None:
        if self.tessdata_dir is not None:
            return self.tessdata_dir
        candidate = self.data_dir / "tessdata"
        return candidate if candidate.is_dir() else None

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        for directory in (self.data_dir, self.projects_dir, self.logs_dir, self.backups_dir):
            directory.mkdir(parents=True, exist_ok=True)
