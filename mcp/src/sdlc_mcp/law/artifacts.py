"""Read artifacts and write **new** ones — the freeze-enforcing write primitive.

``write_new`` is the only sanctioned way to create an artifact file. It refuses
to overwrite an existing file, which is the "artifacts are frozen" law in one
place: everything that would change an artifact goes through entombment +
a new id instead (see ``entomb`` / ``supersede``), never through this function.
"""

from __future__ import annotations

from pathlib import Path

from . import ids

# Where each spec artifact type is created. BT is handled separately (its
# planning/observation split depends on the task type), so it is not here.
TYPE_DIRS: dict[str, str] = {
    "MOD": "2-specs/modules",
    "ACTOR": "2-specs/actors",
    "ENT": "2-specs/entities",
    "EVT": "2-specs/events",
    "UC": "2-specs/use-cases",
}


class FrozenViolation(Exception):
    """Raised when a write would overwrite an existing (frozen) artifact."""


def read(sdlc_root: Path, artifact_id: str) -> str:
    """Text of the artifact ``artifact_id`` (live preferred, else entombed)."""
    ref = ids.resolve(sdlc_root, artifact_id)
    if ref is None:
        raise FileNotFoundError(f"no artifact resolves to id {artifact_id}")
    return ref.path.read_text(encoding="utf-8")


def list_type(sdlc_root: Path, type_: str) -> list[ids.ArtifactRef]:
    """Every artifact of ``type_`` (delegates to :func:`ids.list_type`)."""
    return ids.list_type(sdlc_root, type_)


def write_new(sdlc_root: Path, rel_path: str, content: str) -> Path:
    """Create a new artifact file. Refuses to overwrite (freeze law)."""
    dest = sdlc_root / rel_path
    if dest.exists():
        raise FrozenViolation(
            f"artifact already exists and is frozen: {rel_path} — "
            "issue a new id and entomb the old one instead of editing"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest
