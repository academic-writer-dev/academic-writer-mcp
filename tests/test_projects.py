import json

import pytest

from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.models import DocumentType, Language, ProjectStatus
from academic_writer.server.services import Services


def _create(services: Services, name: str = "Mémoire Master"):
    return services.projects.create(name, DocumentType.MEMOIRE_MASTER, Language.FR,
                                    description="Maintenance prédictive", discipline="Génie mécanique")


def test_create_and_get(services: Services) -> None:
    project = _create(services)
    assert len(project.id) == 32
    assert project.status is ProjectStatus.ACTIVE
    assert services.projects.get(project.id) == project
    assert (services.settings.projects_dir / project.id / "originals").is_dir()


def test_name_is_required_and_trimmed(services: Services) -> None:
    with pytest.raises(ValidationFailed):
        _create(services, "   ")
    assert _create(services, "  Rapport  ").name == "Rapport"


def test_invalid_enum_rejected(services: Services) -> None:
    with pytest.raises(ValueError):
        services.projects.create("X", "roman", Language.FR)


def test_get_unknown(services: Services) -> None:
    with pytest.raises(NotFoundError):
        services.projects.get("0" * 32)


def test_list_orders_and_filters(services: Services) -> None:
    first = _create(services, "Premier")
    second = _create(services, "Second")
    assert [p.id for p in services.projects.list()] == [second.id, first.id]
    services.projects.archive(first.id)
    assert [p.id for p in services.projects.list()] == [second.id]
    assert len(services.projects.list(include_archived=True)) == 2


def test_update(services: Services) -> None:
    project = _create(services)
    updated = services.projects.update(project.id, language=Language.RU, name="Магистерская диссертация")
    assert updated.language is Language.RU
    assert updated.name == "Магистерская диссертация"
    assert updated.updated_at > project.updated_at
    assert updated.discipline == project.discipline


def test_update_without_changes_rejected(services: Services) -> None:
    project = _create(services)
    with pytest.raises(ValidationFailed):
        services.projects.update(project.id)


def test_archive_is_idempotent_and_blocks_updates(services: Services) -> None:
    project = _create(services)
    archived = services.projects.archive(project.id)
    assert archived.status is ProjectStatus.ARCHIVED
    assert services.projects.archive(project.id).status is ProjectStatus.ARCHIVED
    with pytest.raises(ValidationFailed):
        services.projects.update(project.id, name="Nouveau")


def test_history_recorded_without_content(services: Services) -> None:
    project = _create(services)
    services.projects.update(project.id, description="Texte confidentiel")
    with services.db.read() as conn:
        rows = conn.execute("SELECT action, details FROM history WHERE project_id = ? ORDER BY id",
                            (project.id,)).fetchall()
    assert [r["action"] for r in rows] == ["created", "updated"]
    assert "confidentiel" not in rows[1]["details"]
    assert json.loads(rows[1]["details"]) == {"fields": ["description"]}
