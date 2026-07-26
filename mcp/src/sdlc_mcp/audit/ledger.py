"""Record changes and query history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_text(text: str | None) -> str | None:
    """Short content fingerprint (first 12 hex of sha256), or ``None``."""
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def start_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    human: str | None = None,
    title: str | None = None,
    ts: str | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions(session_id, started_ts, human, title, status) "
        "VALUES(?, ?, ?, ?, 'open')",
        (session_id, ts or now_iso(), human, title),
    )
    conn.commit()


def record(
    conn: sqlite3.Connection,
    *,
    action: str,
    session_id: str | None = None,
    actor_human: str | None = None,
    actor_agent: str | None = None,
    artifact_type: str | None = None,
    artifact_id: str | None = None,
    path: str | None = None,
    summary: str | None = None,
    prev_content: str | None = None,
    new_content: str | None = None,
    diff: str | None = None,
    extra: dict | None = None,
    ts: str | None = None,
) -> int:
    """Append one change row. Returns the new row id."""
    cur = conn.execute(
        """INSERT INTO changes
             (ts, session_id, actor_human, actor_agent, action, artifact_type,
              artifact_id, path, summary, prev_hash, new_hash, diff, extra_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ts or now_iso(),
            session_id,
            actor_human,
            actor_agent,
            action,
            artifact_type,
            artifact_id,
            path,
            summary,
            hash_text(prev_content),
            hash_text(new_content),
            diff,
            json.dumps(extra, ensure_ascii=False) if extra is not None else None,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def history(
    conn: sqlite3.Connection,
    *,
    artifact_id: str | None = None,
    artifact_type: str | None = None,
    session_id: str | None = None,
    action: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    """Most-recent-first change rows matching the given filters."""
    clauses: list[str] = []
    params: list[object] = []
    for col, val in (
        ("artifact_id", artifact_id),
        ("artifact_type", artifact_type),
        ("session_id", session_id),
        ("action", action),
    ):
        if val is not None:
            clauses.append(f"{col} = ?")
            params.append(val)
    if since is not None:
        clauses.append("ts >= ?")
        params.append(since)
    if until is not None:
        clauses.append("ts <= ?")
        params.append(until)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    return list(
        conn.execute(f"SELECT * FROM changes{where} ORDER BY id DESC LIMIT ?", params)
    )
