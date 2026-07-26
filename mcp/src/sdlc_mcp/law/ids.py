"""Allocate and resolve permanent, monotonic artifact ids.

An id like ``BT-13`` is derived purely from filenames and resolved by glob. The
next id of a type is one past the highest ever issued **counting entombed ones**
(files under an ``obsolete/`` folder), so a number is never reused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Artifact types that exist as their own files. ``R`` (PRD requirements) is not
# here: requirements live inside PRD.md as text, not as separate files.
FILE_ID_TYPES: tuple[str, ...] = ("BT", "MOD", "ACTOR", "ENT", "EVT", "UC", "FIG", "TC")

# Files that carry conventions, not artifacts — never counted or resolved as ids.
CONVENTION_FILES = {"AGENTS.md", "CLAUDE.md", "README.md"}

_FULL_ID = re.compile(r"^([A-Z]+)-(\d+)$")


@dataclass(frozen=True)
class ArtifactRef:
    """A resolved artifact: its id, file path, and whether it is entombed."""

    id: str
    path: Path
    is_obsolete: bool


def id_type(artifact_id: str) -> str:
    """``"BT-13" -> "BT"``. Raises ValueError on a malformed id."""
    m = _FULL_ID.match(artifact_id)
    if not m:
        raise ValueError(f"not a valid artifact id: {artifact_id!r}")
    return m.group(1)


def id_number(artifact_id: str) -> int:
    """``"BT-13" -> 13``. Raises ValueError on a malformed id."""
    m = _FULL_ID.match(artifact_id)
    if not m:
        raise ValueError(f"not a valid artifact id: {artifact_id!r}")
    return int(m.group(2))


def _iter_artifact_files(sdlc_root: Path):
    for p in sdlc_root.rglob("*.md"):
        if p.name in CONVENTION_FILES:
            continue
        yield p


def _match_type(name: str, type_: str) -> re.Match[str] | None:
    # A number must follow the prefix directly, so ``ENT-`` never matches
    # ``ENTRY-…`` and ``UC-1-ACTOR-…`` is only ever a ``UC`` file.
    return re.match(rf"^{re.escape(type_)}-(\d+)(?:-|\.)", name)


def existing_numbers(sdlc_root: Path, type_: str) -> list[int]:
    """Sorted unique numbers already issued for ``type_`` (incl. entombed)."""
    nums: set[int] = set()
    for p in _iter_artifact_files(sdlc_root):
        m = _match_type(p.name, type_)
        if m:
            nums.add(int(m.group(1)))
    return sorted(nums)


def allocate(sdlc_root: Path, type_: str) -> str:
    """Next free id of ``type_`` — ``max(existing) + 1``, or ``…-1`` if none."""
    if type_ not in FILE_ID_TYPES:
        raise ValueError(f"unknown file id type: {type_!r}")
    nums = existing_numbers(sdlc_root, type_)
    nxt = (nums[-1] + 1) if nums else 1
    return f"{type_}-{nxt}"


def list_type(sdlc_root: Path, type_: str) -> list[ArtifactRef]:
    """Every artifact of ``type_``, live and entombed, sorted by number."""
    refs: list[ArtifactRef] = []
    for p in _iter_artifact_files(sdlc_root):
        m = _match_type(p.name, type_)
        if m:
            refs.append(
                ArtifactRef(
                    id=f"{type_}-{m.group(1)}",
                    path=p,
                    is_obsolete="obsolete" in p.parts,
                )
            )
    return sorted(refs, key=lambda r: id_number(r.id))


def resolve(sdlc_root: Path, artifact_id: str) -> ArtifactRef | None:
    """Find the file for ``artifact_id``.

    Prefers a live file; falls back to an entombed one. Returns ``None`` if the
    id exists nowhere. Raises ValueError if the id resolves to more than one
    **live** file (a law violation — ids are unique).
    """
    type_ = id_type(artifact_id)
    num = id_number(artifact_id)
    matches: list[ArtifactRef] = []
    for p in _iter_artifact_files(sdlc_root):
        m = _match_type(p.name, type_)
        if m and int(m.group(1)) == num:
            matches.append(
                ArtifactRef(artifact_id, p, is_obsolete="obsolete" in p.parts)
            )
    if not matches:
        return None
    live = [r for r in matches if not r.is_obsolete]
    if len(live) > 1:
        paths = ", ".join(str(r.path) for r in live)
        raise ValueError(f"id {artifact_id} resolves to multiple live files: {paths}")
    return live[0] if live else matches[0]


def leading_id(filename: str) -> tuple[str, int] | None:
    """The id a filename **starts with**, e.g. ``UC-1-ACTOR-…`` -> ``("UC", 1)``."""
    m = re.match(r"^([A-Z]+)-(\d+)(?:-|\.)", filename)
    return (m.group(1), int(m.group(2))) if m else None


def artifact_files(sdlc_root: Path) -> list[Path]:
    """All artifact ``*.md`` files (convention files excluded), live + entombed."""
    return list(_iter_artifact_files(sdlc_root))
