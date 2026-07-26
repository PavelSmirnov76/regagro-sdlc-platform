"""SQLite schema and connection for the audit ledger."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_ts TEXT NOT NULL,
    human      TEXT,
    title      TEXT,
    status     TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS changes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    session_id    TEXT,
    actor_human   TEXT,
    actor_agent   TEXT,
    action        TEXT NOT NULL,
    artifact_type TEXT,
    artifact_id   TEXT,
    path          TEXT,
    summary       TEXT,
    prev_hash     TEXT,
    new_hash      TEXT,
    diff          TEXT,
    extra_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_changes_artifact ON changes(artifact_id);
CREATE INDEX IF NOT EXISTS idx_changes_session  ON changes(session_id);
CREATE INDEX IF NOT EXISTS idx_changes_ts       ON changes(ts);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (creating parent dirs + schema if needed) the audit database."""
    is_memory = str(db_path) == ":memory:"
    if not is_memory:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
