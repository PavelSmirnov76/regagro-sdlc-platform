"""Citations and the bold-bullet metadata preamble.

Two shapes matter for the tools:

* **citations** — ``[ID](relative/path.md)`` links, the one universal
  cross-reference format across the whole tree;
* the **bold-bullet preamble** — the ``- **key**: value`` lines some artifacts
  (business tasks, tasks) carry before their first heading.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_CITATION = re.compile(r"\[([A-Z]+-\d+)\]\(([^)]+)\)")
_BULLET = re.compile(r"^- \*\*([^*]+)\*\*:\s*(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Citation:
    """A resolved-in-text citation: the id and the raw link target as written."""

    id: str
    target: str


def extract_citations(text: str) -> list[Citation]:
    """Every ``[ID](target)`` citation in ``text``, in order of appearance."""
    return [Citation(m.group(1), m.group(2)) for m in _CITATION.finditer(text)]


def citation_link(artifact_id: str, from_path: Path, to_path: Path) -> str:
    """Build ``[ID](rel)`` where ``rel`` is ``to_path`` relative to ``from_path``.

    ``from_path`` is the file that will contain the citation; the link is
    relative to its parent directory, matching how the tree cites everywhere.
    """
    rel = os.path.relpath(to_path, from_path.parent)
    return f"[{artifact_id}]({Path(rel).as_posix()})"


def parse_bullet_preamble(text: str) -> dict[str, str]:
    """The ``- **key**: value`` lines before the first ``#`` heading, as a dict."""
    head = text.split("\n#", 1)[0]
    return {m.group(1).strip(): m.group(2).strip() for m in _BULLET.finditer(head)}
