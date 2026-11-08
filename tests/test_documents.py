import stat
from pathlib import Path

import pytest

from academic_writer.core.errors import SecurityViolation, ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.security.files import sha256_file
from academic_writer.server.services import Services
from tests.conftest import make_docx, make_pdf


@pytest.fixture
def project(services: Services):
    return services.projects.create("TP3", DocumentType.TP, Language.FR)


def test_import_keeps_original_and_protects_copy(services: Services, project, inbox: Path) -> None:
    source = make_docx(inbox / "Consignes TP3.docx")
    before = sha256_file(source)
    result = services.documents.import_document(project.id, str(source), DocumentRole.INSTRUCTIONS, "Consignes")

    assert not result.duplicate
    doc = result.document
    assert doc.role is DocumentRole.INSTRUCTIONS
    assert doc.original_filename == "Consignes TP3.docx"
    assert doc.sha256 == before
    # L'original de l'utilisateur est intact et toujours présent.
    assert source.exists() and sha256_file(source) == before
    # La copie est stockée dans le projet, identique et en lecture seule.
    stored = services.documents.stored_file(doc)
    assert stored.parent == services.settings.projects_dir / project.id / "originals"
    assert sha256_file(stored) == before
    assert not stored.stat().st_mode & stat.S_IWRITE
    assert not list(stored.parent.glob("*.part"))


def test_duplicate_not_copied_twice(services: Services, project, inbox: Path) -> None:
    source = make_pdf(inbox / "article.pdf")
    first = services.documents.import_document(project.id, str(source))
    copy = inbox / "article (copie).pdf"
    copy.write_bytes(source.read_bytes())
    second = services.documents.import_document(project.id, str(copy))
    assert second.duplicate and second.document.id == first.document.id
    assert len(services.documents.list(project.id)) == 1


def test_list_filter_by_role(services: Services, project, inbox: Path) -> None:
    (inbox / "a.txt").write_text("consignes", encoding="utf-8")
    (inbox / "b.md").write_text("# brouillon", encoding="utf-8")
    services.documents.import_document(project.id, str(inbox / "a.txt"), DocumentRole.INSTRUCTIONS)
    services.documents.import_document(project.id, str(inbox / "b.md"), DocumentRole.DRAFT)
    assert len(services.documents.list(project.id)) == 2
    drafts = services.documents.list(project.id, DocumentRole.DRAFT)
    assert [d.extension for d in drafts] == [".md"]


def test_outside_allowed_dir_rejected(services: Services, project, tmp_path: Path) -> None:
    outside = tmp_path / "ailleurs.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(SecurityViolation):
        services.documents.import_document(project.id, str(outside))


def test_import_from_data_dir_rejected(services: Services, project, inbox: Path) -> None:
    services.settings.allowed_import_dirs.append(services.settings.data_dir)
    inside = services.settings.data_dir / "x.txt"
    inside.write_text("x", encoding="utf-8")
    with pytest.raises(SecurityViolation):
        services.documents.import_document(project.id, str(inside))


def test_archived_project_rejects_import(services: Services, project, inbox: Path) -> None:
    (inbox / "a.txt").write_text("x", encoding="utf-8")
    services.projects.archive(project.id)
    with pytest.raises(ValidationFailed):
        services.documents.import_document(project.id, str(inbox / "a.txt"))


def test_suspicious_file_leaves_no_trace(services: Services, project, inbox: Path) -> None:
    bad = make_docx(inbox / "macro.docx", {"word/vbaProject.bin": b"\x00"})
    with pytest.raises(SecurityViolation):
        services.documents.import_document(project.id, str(bad))
    assert services.documents.list(project.id) == []
    assert not any((services.settings.projects_dir / project.id / "originals").iterdir())


def test_metadata_detects_tampering(services: Services, project, inbox: Path) -> None:
    (inbox / "a.txt").write_text("original", encoding="utf-8")
    doc = services.documents.import_document(project.id, str(inbox / "a.txt")).document
    meta = services.documents.metadata(doc.id)
    assert meta.integrity_ok and meta.original_protected

    stored = services.documents.stored_file(doc)
    stored.chmod(stat.S_IREAD | stat.S_IWRITE)
    stored.write_text("modifié", encoding="utf-8")
    meta = services.documents.metadata(doc.id)
    assert not meta.integrity_ok and not meta.original_protected


def test_security_warnings_stored(services: Services, project, inbox: Path) -> None:
    pdf = make_pdf(inbox / "js.pdf", b"/JavaScript")
    result = services.documents.import_document(project.id, str(pdf))
    assert result.document.security_notes
    assert "Avertissements" in result.message
