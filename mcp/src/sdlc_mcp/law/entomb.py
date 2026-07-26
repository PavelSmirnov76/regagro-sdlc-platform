"""Entombment — the only way to retire an artifact.

A retired artifact is never deleted or corrected: it moves to an ``obsolete/``
folder beside its live siblings, gains a header stating **when**, **why**, and
**superseded by** which id, and its original content below is left untouched.
``obsolete/`` *is* the staleness marker — nothing else records it.
"""

from __future__ import annotations

from pathlib import Path

from . import ids


class EntombError(Exception):
    """Raised when an id cannot be entombed (unknown, or already entombed)."""


def entomb(
    sdlc_root: Path,
    artifact_id: str,
    *,
    when: str,
    why: str,
    superseded_by: str | None = None,
) -> Path:
    """Move ``artifact_id`` to ``obsolete/`` with a header. Returns the new path."""
    ref = ids.resolve(sdlc_root, artifact_id)
    if ref is None:
        raise EntombError(f"cannot entomb unknown id {artifact_id}")
    if ref.is_obsolete:
        raise EntombError(f"{artifact_id} is already entombed")

    src = ref.path
    obsolete_dir = src.parent / "obsolete"
    obsolete_dir.mkdir(parents=True, exist_ok=True)
    dest = obsolete_dir / src.name
    if dest.exists():
        raise EntombError(f"an entombed file already exists at {dest}")

    header = (
        "<!-- ENTOMBED -->\n"
        f"> **Entombed:** {when}\n"
        f"> **Why:** {why}\n"
        f"> **Superseded by:** {superseded_by or 'none'}\n\n"
    )
    dest.write_text(header + src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return dest
