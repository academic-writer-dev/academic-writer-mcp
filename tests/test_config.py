from pathlib import Path

import pytest
from pydantic import ValidationError

from academic_writer.core.config import CONFIG_ENV_VAR, Settings


def test_defaults_are_local_and_safe(tmp_path: Path) -> None:
    s = Settings()
    assert s.mode == "local"
    assert s.max_file_size_mb == 100
    assert ".exe" not in s.allowed_extensions
    assert s.db_path.name == "academic_writer.db"


def test_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACADEMIC_WRITER_DATA_DIR", str(tmp_path / "x"))
    monkeypatch.setenv("ACADEMIC_WRITER_MAX_FILE_SIZE_MB", "5")
    s = Settings()
    assert s.data_dir == tmp_path / "x"
    assert s.max_file_size_bytes == 5 * 1024 * 1024


def test_toml_file_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    data = tmp_path / "données"
    config.write_text(
        f"data_dir = '{data}'\nmode = 'connected'\nallowed_import_dirs = ['{tmp_path}']\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_ENV_VAR, str(config))
    monkeypatch.delenv("ACADEMIC_WRITER_DATA_DIR")  # sinon prioritaire sur le fichier (filet de conftest)
    s = Settings()
    assert s.data_dir == data
    assert s.mode == "connected"
    assert s.allowed_import_dirs == [tmp_path]


def test_env_has_priority_over_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("mode = 'connected'\n", encoding="utf-8")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(config))
    monkeypatch.setenv("ACADEMIC_WRITER_MODE", "local")
    assert Settings().mode == "local"


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_extensions=[".exe"])


def test_extensions_normalized() -> None:
    assert Settings(allowed_extensions=["PDF", ".Docx"]).allowed_extensions == [".docx", ".pdf"]


def test_relative_import_dir_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_import_dirs=[Path("relatif")])


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(mode="cloud")
