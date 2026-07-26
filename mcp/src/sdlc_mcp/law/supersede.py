"""Supersession — the pipeline's only forward link.

"Updating" a frozen artifact is: write a **new** artifact (carrying a
``supersedes: {old_id}`` note) and **entomb** the old one, pointing its
``superseded by`` header at the new id. The new content is written first, so a
name collision aborts before anything is entombed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import artifacts
from . import entomb as _entomb


@dataclass(frozen=True)
class SupersedeResult:
    new_id: str
    new_path: Path
    obsolete_path: Path


def supersede(
    sdlc_root: Path,
    *,
    old_id: str,
    new_id: str,
    new_rel_path: str,
    new_content: str,
    when: str,
    why: str,
) -> SupersedeResult:
    """Write the new artifact, then entomb the old one under it."""
    new_path = artifacts.write_new(sdlc_root, new_rel_path, new_content)
    obsolete_path = _entomb.entomb(
        sdlc_root, old_id, when=when, why=why, superseded_by=new_id
    )
    return SupersedeResult(new_id=new_id, new_path=new_path, obsolete_path=obsolete_path)
