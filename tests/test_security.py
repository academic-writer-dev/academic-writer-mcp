"""Tests de sécurité : chemins et inspection des fichiers."""

import zipfile
from pathlib import Path

import pytest

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError, SecurityViolation, ValidationFailed
from academic_writer.security.files import inspect_file
from academic_writer.security.paths import ensure_within, resolve_user_file, safe_child
from tests.conftest import make_docx, make_ooxml, make_pdf

# --- chemins -------------------------------------------------------------


def test_relative_path_rejected() -> None:
    with pytest.raises(ValidationFailed):
        resolve_user_file("documents\\rapport.docx")


def test_empty_and_nul_paths_rejected(inbox: Path) -> None:
    with pytest.raises(ValidationFailed):
        resolve_user_file("   ")
    with pytest.raises(SecurityViolation):
        resolve_user_file(str(inbox / "a\x00.txt"))


def test_device_path_rejected() -> None:
    with pytest.raises(SecurityViolation):
        resolve_user_file("\\\\.\\PhysicalDrive0")


def test_missing_file(inbox: Path) -> None:
    with pytest.raises(NotFoundError):
        resolve_user_file(str(inbox / "absent.txt"))


def test_directory_rejected(inbox: Path) -> None:
    with pytest.raises(ValidationFailed):
        resolve_user_file(str(inbox))


def test_quotes_are_stripped(inbox: Path) -> None:
    f = inbox / "a.txt"
    f.write_text("x", encoding="utf-8")
    assert resolve_user_file(f'"{f}"') == f.resolve()


def test_outside_allowed_dirs_rejected(tmp_path: Path, inbox: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("confidentiel", encoding="utf-8")
    with pytest.raises(SecurityViolation):
        ensure_within(resolve_user_file(str(outside)), [inbox])


def test_traversal_is_resolved_then_rejected(tmp_path: Path, inbox: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("confidentiel", encoding="utf-8")
    sneaky = f"{inbox}\\..\\secret.txt"
    with pytest.raises(SecurityViolation):
        ensure_within(resolve_user_file(sneaky), [inbox])


def test_safe_child_blocks_escape(tmp_path: Path) -> None:
    with pytest.raises(SecurityViolation):
        safe_child(tmp_path / "base", "..", "evil.txt")


# --- fichiers ------------------------------------------------------------


def test_valid_text_markdown_docx_pdf(settings: Settings, inbox: Path) -> None:
    (inbox / "a.txt").write_text("Texte en français — Русский текст", encoding="utf-8")
    (inbox / "b.md").write_text("# Titre\n", encoding="utf-8")
    for name in ("a.txt", "b.md"):
        assert inspect_file(inbox / name, settings).warnings == []
    docx = inspect_file(make_docx(inbox / "c.docx"), settings)
    assert docx.mime_type.endswith("wordprocessingml.document")
    pdf = inspect_file(make_pdf(inbox / "d.pdf"), settings)
    assert pdf.mime_type == "application/pdf" and len(pdf.sha256) == 64


def test_disallowed_extension(settings: Settings, inbox: Path) -> None:
    f = inbox / "virus.exe"
    f.write_bytes(b"MZ")
    with pytest.raises(ValidationFailed):
        inspect_file(f, settings)


def test_empty_file_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "vide.txt"
    f.write_bytes(b"")
    with pytest.raises(ValidationFailed):
        inspect_file(f, settings)


def test_too_large_file_rejected(tmp_path: Path, inbox: Path) -> None:
    small = Settings(data_dir=tmp_path / "d", allowed_import_dirs=[inbox], max_file_size_mb=1)
    f = inbox / "gros.txt"
    f.write_bytes(b"a" * (2 * 1024 * 1024))
    with pytest.raises(ValidationFailed):
        inspect_file(f, small)


def test_fake_pdf_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "faux.pdf"
    f.write_text("je ne suis pas un pdf", encoding="utf-8")
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_executable_renamed_docx_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "piege.docx"
    f.write_bytes(b"MZ\x90\x00" + b"\x00" * 100)
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_xlsx_renamed_as_docx_rejected(settings: Settings, inbox: Path) -> None:
    f = make_ooxml(inbox / "classeur.docx", "xl/")
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_docx_with_macros_rejected(settings: Settings, inbox: Path) -> None:
    f = make_docx(inbox / "macro.docx", {"word/vbaProject.bin": b"\x00\x01"})
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_zip_bomb_rejected(settings: Settings, inbox: Path) -> None:
    f = make_docx(inbox / "bombe.docx", {"word/media/zeros.bin": b"\x00" * (20 * 1024 * 1024)})
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_corrupted_zip_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "casse.docx"
    f.write_bytes(b"PK\x03\x04" + b"\xff" * 200)
    with pytest.raises(ValidationFailed):
        inspect_file(f, settings)


def test_dangerous_internal_path_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "slip.docx"
    with zipfile.ZipFile(f, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<d/>")
        archive.writestr("../../evil.txt", "x")
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_binary_text_rejected(settings: Settings, inbox: Path) -> None:
    f = inbox / "binaire.txt"
    f.write_bytes(b"abc\x00\x01\x02")
    with pytest.raises(SecurityViolation):
        inspect_file(f, settings)


def test_pdf_javascript_warning(settings: Settings, inbox: Path) -> None:
    f = make_pdf(inbox / "js.pdf", b"<< /S /JavaScript /JS (app.alert(1)) >>")
    result = inspect_file(f, settings)
    assert any("JavaScript" in w for w in result.warnings)


def test_cp1251_text_accepted_with_warning(settings: Settings, inbox: Path) -> None:
    f = inbox / "russe.txt"
    f.write_bytes("Пример текста".encode("cp1251"))
    result = inspect_file(f, settings)
    assert any("UTF-8" in w for w in result.warnings)
