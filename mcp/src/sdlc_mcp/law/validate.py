"""Tree integrity — the one automated check a pass runs before proposing a delta.

Only **id collisions** (two live files sharing one id) are hard errors, because
they break glob resolution. Everything else is advisory, per the law "a live
artifact citing an entombed id is flagged for review, not automatically
entombed":

* **unresolved** — a citation to an id that exists nowhere;
* **stale** — a citation to an id that now lives in ``obsolete/``;
* **broken_links** — a citation whose written path no longer points at a file.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter, ids


@dataclass
class ValidationReport:
    collisions: list[str] = field(default_factory=list)
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    stale: list[tuple[str, str]] = field(default_factory=list)
    broken_links: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing structural is broken (collisions are the only gate)."""
        return not self.collisions

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "collisions": self.collisions,
            "unresolved": [{"file": f, "id": i} for f, i in self.unresolved],
            "stale": [{"file": f, "id": i} for f, i in self.stale],
            "broken_links": [{"file": f, "target": t} for f, t in self.broken_links],
        }


def validate_tree(sdlc_root: Path) -> ValidationReport:
    rep = ValidationReport()
    files = ids.artifact_files(sdlc_root)

    # id collisions: >1 live file for the same (type, number). Only managed
    # types count — tracker-named tasks (SHEEP-4-1, mirrored task↔result) share
    # a leading "SHEEP-4" by design and are not monotonic artifact ids.
    live_by_id: dict[str, list[Path]] = defaultdict(list)
    for p in files:
        lid = ids.leading_id(p.name)
        if lid and lid[0] in ids.FILE_ID_TYPES and "obsolete" not in p.parts:
            live_by_id[f"{lid[0]}-{lid[1]}"].append(p)
    rep.collisions = sorted(aid for aid, ps in live_by_id.items() if len(ps) > 1)

    # citation integrity
    for p in files:
        rel_name = str(p.relative_to(sdlc_root))
        text = p.read_text(encoding="utf-8")
        for cit in frontmatter.extract_citations(text):
            try:
                ref = ids.resolve(sdlc_root, cit.id)
            except ValueError:
                continue  # ambiguous id — already reported as a collision above
            if ref is None:
                rep.unresolved.append((rel_name, cit.id))
            elif ref.is_obsolete:
                rep.stale.append((rel_name, cit.id))
            target = (p.parent / cit.target).resolve()
            if not target.exists():
                rep.broken_links.append((rel_name, cit.target))

    return rep
