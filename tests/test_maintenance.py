"""Tests de la maintenance (phase 10) : diagnostic, sauvegarde / restauration, configuration des clients."""

import json
import zipfile
from pathlib import Path

import pytest
from mcp import Client

from academic_writer.cli import main as cli_main
from academic_writer.core import maintenance
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.server.app import mcp
from academic_writer.server.services import Services


@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("Sauvegarde", DocumentType.TP, Language.FR)
    path = inbox / "consignes.txt"
    path.write_text("Calculer la vitesse.", encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    return project


def test_backup_and_restore_roundtrip(services: Services, project) -> None:
    info = maintenance.create_backup(services.settings, services.db, complete=True)
    assert info.kind == "complete" and Path(info.path).exists()
    with zipfile.ZipFile(info.path) as zf:
        names = zf.namelist()
    assert "manifest.json" in names and "academic_writer.db" in names
    assert any(n.startswith(f"projects/{project.id}/originals/") for n in names)
    # modification après la sauvegarde, puis restauration
    services.projects.create("Projet postérieur", DocumentType.TP, Language.FR)
    assert len(services.projects.list()) == 2
    result = maintenance.restore_backup(services.settings, services.db, Path(info.path))
    assert [p.name for p in services.projects.list()] == ["Sauvegarde"]
    assert Path(result.safety_backup).exists() and result.projects_restored == 1
    document = services.documents.list(project.id)[0]
    assert services.documents.stored_file(document).read_text(encoding="utf-8") == "Calculer la vitesse."
    backups = maintenance.list_backups(services.settings).backups
    assert [b.kind for b in backups] == ["complete", "complete"]  # la sauvegarde + celle de sécurité


def test_restore_rejects_bad_archives(services: Services, tmp_path: Path) -> None:
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"app": "academic-writer"}))
        zf.writestr("academic_writer.db", b"")
        zf.writestr("../../hors.txt", "x")
    with pytest.raises(ValidationFailed, match="interdit"):
        maintenance.restore_backup(services.settings, services.db, evil)
    other = tmp_path / "other.zip"
    with zipfile.ZipFile(other, "w") as zf:
        zf.writestr("readme.txt", "x")
    with pytest.raises(ValidationFailed, match="incomplète"):
        maintenance.restore_backup(services.settings, services.db, other)


def test_setup_desktop_preserves_other_servers(tmp_path: Path) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(json.dumps({"mcpServers": {"solidworks": {"command": "x"}}, "preferences": {"a": 1}}),
                      encoding="utf-8")
    check = maintenance.setup_desktop(apply=False, config_path=config)
    assert check.status == "a_configurer" and "academic-writer" not in config.read_text(encoding="utf-8")
    done = maintenance.setup_desktop(apply=True, config_path=config)
    data = json.loads(config.read_text(encoding="utf-8"))
    assert done.status == "configure" and Path(done.backup_path).exists()
    assert data["mcpServers"]["solidworks"] == {"command": "x"} and data["preferences"] == {"a": 1}
    assert data["mcpServers"]["academic-writer"]["args"][-2:] == ["-m", "academic_writer"]
    assert maintenance.setup_desktop(apply=False, config_path=config).status == "deja_configure"


def test_diagnose_structure(services: Services) -> None:
    diagnosis = maintenance.diagnose(services)
    components = {c.component: c for c in diagnosis.checks}
    assert components["Base de données"].status == "ok" and diagnosis.ready
    assert components["Mode réseau"].detail.startswith("local")
    assert components["Sauvegardes"].status == "attention"  # aucune sauvegarde dans l'environnement de test


def test_cli_restore_requires_confirmation(capsys) -> None:
    assert cli_main(["restore", "inexistant.zip"]) == 2
    assert "--yes" in capsys.readouterr().out


@pytest.mark.anyio
async def test_maintenance_tools_and_prompts() -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"system_check", "create_backup", "list_backups"} <= names
        prompts = {p.name for p in (await client.list_prompts()).prompts}
        assert {"rediger_rapport", "verifier_avant_remise", "trouver_sources", "academic_analysis"} <= prompts
        result = await client.call_tool("create_backup", {"complete": False})
        assert result.structured_content["kind"] == "base"
        prompt = await client.get_prompt("rediger_rapport", {"fichier_consignes": "ЛР4.pdf"})
        assert "n'invente aucune valeur" in prompt.messages[0].content.text


def test_cli_output_survives_legacy_console_encoding(monkeypatch) -> None:
    import io
    import sys

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1251")
    monkeypatch.setattr(sys, "stdout", stream)
    cli_main(["restore", "inexistant.zip"])
    stream.write("— → é\n")  # ne doit pas lever UnicodeEncodeError après la reconfiguration
    stream.flush()
