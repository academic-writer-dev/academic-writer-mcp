import sqlite3

import pytest

from academic_writer.core.config import Settings
from academic_writer.core.errors import StorageError
from academic_writer.storage.db import Database
from academic_writer.storage.migrations import LATEST_VERSION, MIGRATIONS

EXPECTED_TABLES = {"projects", "documents", "revisions", "history", "settings", "extractions", "chunks", "chunks_fts"}


def _db(settings: Settings) -> Database:
    return Database(settings.data_dir / "test.db", settings.backups_dir)


def test_initialize_creates_schema(settings: Settings) -> None:
    db = _db(settings)
    assert db.initialize() == [m.version for m in MIGRATIONS]
    assert db.schema_version() == LATEST_VERSION
    with db.read() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert EXPECTED_TABLES <= tables
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_initialize_is_idempotent(settings: Settings) -> None:
    db = _db(settings)
    db.initialize()
    assert db.initialize() == []


def test_foreign_keys_enforced(settings: Settings) -> None:
    db = _db(settings)
    db.initialize()
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO documents (id, project_id, role, original_filename, source_path, stored_path, "
                "extension, mime_type, size_bytes, sha256, created_at, updated_at) "
                "VALUES ('d', 'inexistant', 'source', 'a.txt', 'x', 'y', '.txt', 'text/plain', 1, 'h', 't', 't')"
            )


def test_transaction_rolls_back_on_error(settings: Settings) -> None:
    db = _db(settings)
    db.initialize()
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('k', 'v', 't')")
            raise RuntimeError("échec simulé")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0


def test_backup_creates_consistent_copy(settings: Settings) -> None:
    db = _db(settings)
    db.initialize()
    with db.transaction() as conn:
        conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('k', 'v', 't')")
    backup = db.backup("test")
    assert backup.exists() and backup.parent == settings.backups_dir
    copy = sqlite3.connect(backup)
    try:
        assert copy.execute("SELECT value FROM settings WHERE key='k'").fetchone()[0] == "v"
    finally:
        copy.close()


def test_newer_schema_is_refused(settings: Settings) -> None:
    db = _db(settings)
    db.initialize()
    with db.read() as conn:
        conn.execute(f"PRAGMA user_version = {LATEST_VERSION + 1}")
    with pytest.raises(StorageError):
        db.initialize()
