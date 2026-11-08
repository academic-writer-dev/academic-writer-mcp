"""Accès à la base SQLite locale.

- Une connexion courte par opération : sûr même si les outils MCP s'exécutent
  dans des threads différents, et si plusieurs clients (Claude Desktop, Claude Code)
  lancent chacun leur processus serveur sur la même base.
- Mode WAL + délai d'attente : lectures concurrentes, écritures sérialisées.
- Sauvegarde automatique avant toute migration d'une base existante.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from academic_writer.core.errors import StorageError
from academic_writer.storage.migrations import LATEST_VERSION, MIGRATIONS

logger = logging.getLogger("academic_writer.storage")

_BUSY_TIMEOUT_MS = 10_000


class Database:
    def __init__(self, path: Path, backups_dir: Path) -> None:
        self.path = path
        self.backups_dir = backups_dir

    # --- connexions ------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=_BUSY_TIMEOUT_MS / 1000, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Transaction en écriture : validée si le bloc réussit, annulée sinon."""
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()

    # --- schéma ----------------------------------------------------------
    def schema_version(self) -> int:
        with self.read() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    def initialize(self) -> list[int]:
        """Crée la base si besoin, active WAL et applique les migrations en attente."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        with self.read() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
        current = self.schema_version()
        if current > LATEST_VERSION:
            raise StorageError(
                f"La base (schéma v{current}) a été créée par une version plus récente "
                f"d'Academic Writer (schéma maximal connu : v{LATEST_VERSION}). Mettez le logiciel à jour."
            )
        pending = [m for m in MIGRATIONS if m.version > current]
        if not pending:
            return []
        if existed and current > 0:
            self.backup(label=f"avant-migration-v{pending[0].version}")
        applied: list[int] = []
        for migration in pending:
            script = f"BEGIN IMMEDIATE;\n{migration.sql}\nPRAGMA user_version = {migration.version};\nCOMMIT;"
            conn = self.connect()
            try:
                conn.executescript(script)
            except sqlite3.Error as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise StorageError(f"Échec de la migration v{migration.version} : {exc}") from exc
            finally:
                conn.close()
            logger.info("Migration appliquée : v%d (%s)", migration.version, migration.description)
            applied.append(migration.version)
        return applied

    # --- sauvegarde ------------------------------------------------------
    def backup(self, label: str = "manuelle") -> Path:
        """Copie cohérente de la base (API de sauvegarde SQLite, sûre même en cours d'utilisation)."""
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        destination = self.backups_dir / f"academic_writer-{stamp}-{safe_label}.db"
        source = self.connect()
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        logger.info("Sauvegarde de la base créée : %s", destination.name)
        return destination
