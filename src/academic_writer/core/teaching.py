"""Profils d'enseignants et politique de sources (modèles et règles, sans dépendance vers les services).

Politique de sources d'un projet :
- ``course_only`` : uniquement les documents fournis par l'enseignant (rôles instructions, course, rubric,
  template, example, data) ; aucune source bibliographique ni recherche en ligne ; une question que le
  cours ne traite pas est signalée, jamais complétée par des connaissances externes ;
- ``project_sources`` (défaut) : documents et sources enregistrées du projet ;
- ``external_allowed`` : connaissances et sources externes permises, toujours signalées comme externes et
  jamais attribuées à l'enseignant.
"""

from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, Field

from academic_writer.core.models import SOURCE_POLICY_LABELS, TEACHER_ROLES, SourcePolicy


class Notation(BaseModel):
    symbol: str = Field(max_length=40)
    meaning: str = Field(max_length=300)
    unit: str | None = Field(default=None, max_length=40)


class TeacherProfile(BaseModel):
    id: str
    name: str
    subject: str | None = None
    course: str | None = None
    institution: str | None = None
    source_policy: SourcePolicy = "course_only"
    source_policy_label: str = ""
    notations: list[Notation] = Field(default_factory=list)
    methods: str = Field(default="", description="Méthodes et démarches imposées par l'enseignant.")
    expectations: str = Field(default="", description="Attentes : présentation, niveau de détail, barème…")
    created_at: str
    updated_at: str


class TeacherProfileList(BaseModel):
    count: int
    profiles: list[TeacherProfile]


def profile_from_row(row: sqlite3.Row) -> TeacherProfile:
    return TeacherProfile(
        id=row["id"], name=row["name"], subject=row["subject"], course=row["course"], institution=row["institution"],
        source_policy=row["source_policy"], source_policy_label=SOURCE_POLICY_LABELS[row["source_policy"]],
        notations=[Notation.model_validate(n) for n in json.loads(row["notations"] or "[]")],
        methods=row["methods"] or "", expectations=row["expectations"] or "",
        created_at=row["created_at"], updated_at=row["updated_at"])


def load_profile(conn: sqlite3.Connection, profile_id: str | None) -> TeacherProfile | None:
    if not profile_id:
        return None
    row = conn.execute("SELECT * FROM teacher_profiles WHERE id = ?", (profile_id,)).fetchone()
    return profile_from_row(row) if row else None


_GAP = {"fr": "[NON TRAITÉ DANS LE COURS : …]", "ru": "[В МАТЕРИАЛАХ КУРСА НЕТ: …]", "en": "[NOT COVERED IN THE COURSE: …]"}


def gap_marker(language: str) -> str:
    return _GAP.get(language, _GAP["fr"])


def policy_rules(policy: str, language: str) -> list[str]:
    """Règles ajoutées aux consignes du rédacteur selon la politique de sources du projet."""
    if policy == "course_only":
        return [
            "CONSIGNE DE L'ENSEIGNANT : réponds UNIQUEMENT à partir des documents de l'enseignant fournis dans le "
            "dossier (consignes, cours, barème, modèles, exemples, données). N'utilise AUCUNE connaissance "
            "extérieure, même si tu la crois exacte, et ne cite aucune source bibliographique.",
            f"Si le cours ne permet pas de répondre à une question, écris exactement {gap_marker(language)} en "
            "précisant la question : ne comble jamais le manque.",
            "Respecte les notations, les symboles, les unités et la démarche du cours ; si deux documents du cours se "
            "contredisent, signale la contradiction au lieu de choisir.",
        ]
    if policy == "external_allowed":
        return [
            "Les connaissances et sources externes sont permises, mais tout élément qui ne vient pas des documents "
            "de l'enseignant doit être signalé comme externe (« (source externe) » ou citation [@clé]) et ne doit "
            "jamais être présenté comme venant du cours ou de l'enseignant.",
        ]
    return []


def allowed_roles(policy: str) -> tuple[str, ...] | None:
    """Rôles des documents utilisables pour la rédaction ; None = tous."""
    return TEACHER_ROLES if policy == "course_only" else None
