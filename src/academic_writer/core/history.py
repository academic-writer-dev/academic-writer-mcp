"""Historique des opérations (traçabilité).

Ne jamais y enregistrer le contenu des documents : uniquement des identifiants,
des actions et des métadonnées non sensibles.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from academic_writer.core.models import utc_now


def record_event(
    conn: sqlite3.Connection,
    *,
    project_id: str | None,
    entity_type: str,
    entity_id: str | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO history (project_id, entity_type, entity_id, action, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            project_id,
            entity_type,
            entity_id,
            action,
            json.dumps(details or {}, ensure_ascii=False),
            utc_now(),
        ),
    )
