"""Append-only session transcript, stored as JSONL."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


def new_session_id(now: datetime | None = None) -> str:
    """A sortable, unique-enough session id, e.g. ``S-20260726-101500-ab12``."""
    now = now or datetime.now(timezone.utc)
    return f"S-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


class SessionLog:
    """Reads/writes one session's ``{session_id}.jsonl`` file."""

    def __init__(self, transcript_dir: Path | str, session_id: str) -> None:
        self.dir = Path(transcript_dir)
        self.session_id = session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{session_id}.jsonl"

    def append(self, kind: str, **fields: object) -> dict:
        """Append one event; returns the written record."""
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "kind": kind,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def read(self) -> list[dict]:
        """All events for this session, in order (empty if none yet)."""
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
