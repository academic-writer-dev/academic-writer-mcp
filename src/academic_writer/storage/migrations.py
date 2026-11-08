"""Migrations du schéma SQLite.

Chaque migration est appliquée une seule fois, dans une transaction, et la version
courante est stockée dans ``PRAGMA user_version``. Ne jamais modifier une migration
déjà publiée : en ajouter une nouvelle.

Les tables des phases suivantes (sections, sources, citations, claims, evidence,
audits, findings, suggestions, domain_profiles, templates) seront ajoutées par de
nouvelles migrations au moment où leur code sera développé.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Projets, documents, révisions, historique, réglages",
        sql="""
CREATE TABLE projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description   TEXT NOT NULL DEFAULT '',
    document_type TEXT NOT NULL,
    language      TEXT NOT NULL,
    discipline    TEXT,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX idx_projects_status ON projects(status);

CREATE TABLE documents (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    role              TEXT NOT NULL,
    title             TEXT,
    original_filename TEXT NOT NULL,
    source_path       TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    extension         TEXT NOT NULL,
    mime_type         TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL CHECK (size_bytes >= 0),
    sha256            TEXT NOT NULL,
    security_notes    TEXT NOT NULL DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'imported',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (project_id, sha256)
);
CREATE INDEX idx_documents_project ON documents(project_id);

CREATE TABLE revisions (
    id                 TEXT PRIMARY KEY,
    document_id        TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    parent_revision_id TEXT REFERENCES revisions(id) ON DELETE RESTRICT,
    kind               TEXT NOT NULL,
    stored_path        TEXT,
    sha256             TEXT,
    note               TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'proposed'
                       CHECK (status IN ('proposed', 'accepted', 'rejected', 'superseded')),
    created_at         TEXT NOT NULL,
    decided_at         TEXT
);
CREATE INDEX idx_revisions_document ON revisions(document_id);

CREATE TABLE history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT REFERENCES projects(id) ON DELETE RESTRICT,
    entity_type TEXT NOT NULL,
    entity_id   TEXT,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_history_project ON history(project_id, created_at);

CREATE TABLE settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
""",
    ),
    Migration(
        version=2,
        description="Extractions et recherche plein texte (FTS5)",
        sql="""
CREATE TABLE extractions (
    document_id   TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE RESTRICT,
    extractor     TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    page_count    INTEGER,
    char_count    INTEGER NOT NULL,
    block_count   INTEGER NOT NULL,
    table_count   INTEGER NOT NULL,
    image_count   INTEGER NOT NULL,
    ocr_pages     INTEGER NOT NULL DEFAULT 0,
    warnings      TEXT NOT NULL DEFAULT '[]',
    result_path   TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    seq         INTEGER NOT NULL,
    page        INTEGER,
    heading     TEXT,
    text        TEXT NOT NULL,
    UNIQUE (document_id, seq)
);
CREATE INDEX idx_chunks_project ON chunks(project_id);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, heading,
    content='chunks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, heading) VALUES (new.id, new.text, coalesce(new.heading, ''));
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, heading) VALUES ('delete', old.id, old.text, coalesce(old.heading, ''));
END;
CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, heading) VALUES ('delete', old.id, old.text, coalesce(old.heading, ''));
    INSERT INTO chunks_fts(rowid, text, heading) VALUES (new.id, new.text, coalesce(new.heading, ''));
END;
""",
    ),
    Migration(
        version=3,
        description="Domaine disciplinaire et convention de présentation des projets",
        sql="""
ALTER TABLE projects ADD COLUMN domain_id TEXT;
ALTER TABLE projects ADD COLUMN domain_confirmed_at TEXT;
ALTER TABLE projects ADD COLUMN convention TEXT CHECK (convention IN ('ru', 'fr', 'intl'));
""",
    ),
    Migration(
        version=4,
        description="Consentements au traitement externe et suivi de l'usage des fournisseurs IA",
        sql="""
CREATE TABLE ai_consents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    scope       TEXT NOT NULL CHECK (scope IN ('all', 'anthropic', 'openai')),
    granted_at  TEXT NOT NULL,
    revoked_at  TEXT,
    note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_ai_consents_project ON ai_consents(project_id);

CREATE TABLE ai_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    TEXT REFERENCES projects(id) ON DELETE RESTRICT,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    task          TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_estimate REAL,
    status        TEXT NOT NULL CHECK (status IN ('ok', 'refused', 'error')),
    error_kind    TEXT,
    request_id    TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX idx_ai_usage_created ON ai_usage(created_at);
""",
    ),
    Migration(
        version=5,
        description="Rédaction encadrée : exigences, plans, sections, révisions de sections",
        sql="""
CREATE TABLE requirements (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    source_document_id TEXT REFERENCES documents(id) ON DELETE RESTRICT,
    page               INTEGER,
    kind               TEXT NOT NULL CHECK (kind IN ('task', 'length', 'structure', 'format', 'norm',
                                                     'deadline', 'variant', 'data', 'other')),
    text               TEXT NOT NULL,
    value              TEXT,
    status             TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'confirmed', 'rejected')),
    origin             TEXT NOT NULL CHECK (origin IN ('extracted', 'user')),
    position           INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX idx_requirements_project ON requirements(project_id, kind);

CREATE TABLE outlines (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    version      INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'superseded')),
    language     TEXT NOT NULL,
    convention   TEXT NOT NULL,
    domain_id    TEXT NOT NULL,
    target_words INTEGER,
    global_requirement_ids TEXT NOT NULL DEFAULT '[]',
    note         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    approved_at  TEXT,
    UNIQUE (project_id, version)
);

CREATE TABLE outline_sections (
    id              TEXT PRIMARY KEY,
    outline_id      TEXT NOT NULL REFERENCES outlines(id) ON DELETE RESTRICT,
    position        INTEGER NOT NULL,
    section_key     TEXT,
    title           TEXT NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 4),
    required        INTEGER NOT NULL DEFAULT 1,
    guidance        TEXT,
    target_words    INTEGER,
    requirement_ids TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'drafted', 'validated')),
    origin          TEXT NOT NULL DEFAULT 'template'
);
CREATE INDEX idx_outline_sections ON outline_sections(outline_id, position);

CREATE TABLE section_revisions (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    section_id         TEXT NOT NULL REFERENCES outline_sections(id) ON DELETE RESTRICT,
    version            INTEGER NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('draft', 'rewrite', 'translation', 'correction')),
    engine             TEXT NOT NULL,
    model              TEXT,
    language           TEXT NOT NULL,
    text               TEXT NOT NULL,
    word_count         INTEGER NOT NULL,
    checks             TEXT NOT NULL DEFAULT '[]',
    status             TEXT NOT NULL DEFAULT 'proposed'
                       CHECK (status IN ('proposed', 'accepted', 'rejected', 'superseded')),
    parent_revision_id TEXT REFERENCES section_revisions(id) ON DELETE RESTRICT,
    note               TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    decided_at         TEXT,
    UNIQUE (section_id, version)
);
CREATE INDEX idx_section_revisions ON section_revisions(section_id, status);
""",
    ),
    Migration(
        version=6,
        description="Exigences : types objectif / étape / question, numéro d'origine et intertitre",
        sql="""
CREATE TABLE requirements_v6 (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    source_document_id TEXT REFERENCES documents(id) ON DELETE RESTRICT,
    page               INTEGER,
    kind               TEXT NOT NULL CHECK (kind IN ('task', 'step', 'question', 'objective', 'length', 'structure',
                                                     'format', 'norm', 'deadline', 'variant', 'data', 'other')),
    text               TEXT NOT NULL,
    value              TEXT,
    status             TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'confirmed', 'rejected')),
    origin             TEXT NOT NULL CHECK (origin IN ('extracted', 'user')),
    position           INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    number             TEXT,
    group_label        TEXT
);
INSERT INTO requirements_v6 (id, project_id, source_document_id, page, kind, text, value, status, origin, position,
                             created_at, updated_at)
    SELECT id, project_id, source_document_id, page, kind, text, value, status, origin, position, created_at, updated_at
    FROM requirements;
DROP TABLE requirements;
ALTER TABLE requirements_v6 RENAME TO requirements;
CREATE INDEX idx_requirements_project ON requirements(project_id, kind);
""",
    ),
)

LATEST_VERSION: int = MIGRATIONS[-1].version
