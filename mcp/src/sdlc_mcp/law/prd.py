"""The PRD — the pipeline's one mutable file.

Unlike every other artifact, ``PRD.md`` is edited in place. The law that keeps
that safe: before each rewrite the current version is snapshotted to
``history/PRD-{date}.md`` with a header, and requirements (``R{n}``) are never
reworded or renumbered — a dead requirement is *deprecated in place* and a new
``R{n}`` issued for what replaced it.
"""

from __future__ import annotations

import re
from pathlib import Path

PRD_REL = "0-vibes/prd/PRD.md"
HISTORY_REL = "0-vibes/prd/history"


def prd_path(sdlc_root: Path) -> Path:
    return sdlc_root / PRD_REL


def read(sdlc_root: Path) -> str:
    return prd_path(sdlc_root).read_text(encoding="utf-8")


def next_requirement_id(sdlc_root: Path) -> str:
    """``R{n}`` one past the highest ever used (deprecated ones still count)."""
    nums = [int(n) for n in re.findall(r"\bR(\d+)\b", read(sdlc_root))]
    return f"R{(max(nums) + 1) if nums else 1}"


def snapshot_and_write(
    sdlc_root: Path,
    new_text: str,
    *,
    date: str,
    why: str,
    raw: str = "нет.",
) -> tuple[Path, Path]:
    """Copy the current PRD to ``history/PRD-{date}.md`` (with header), then write.

    Returns ``(history_path, prd_path)``. ``date`` is the day the old version was
    *superseded*, per the history folder's convention.
    """
    p = prd_path(sdlc_root)
    old = p.read_text(encoding="utf-8")
    hist_dir = sdlc_root / HISTORY_REL
    hist_dir.mkdir(parents=True, exist_ok=True)
    hist = hist_dir / f"PRD-{date}.md"
    header = f"- **superseded**: {date}\n- **why**: {why}\n- **raw**: {raw}\n\n"
    hist.write_text(header + old, encoding="utf-8")
    p.write_text(new_text, encoding="utf-8")
    return hist, p


def insert_requirement(prd_text: str, rid: str, text: str) -> str:
    """Return ``prd_text`` with ``- **{rid}** — {text}`` added to Requirements."""
    line = f"- **{rid}** — {text}"
    lines = prd_text.split("\n")

    start = next(
        (i for i, ln in enumerate(lines) if re.match(r"^##\s+Requirements\b", ln, re.I)),
        None,
    )
    if start is None:  # no Requirements section: create one at the end
        return prd_text.rstrip("\n") + f"\n\n## Requirements\n\n{line}\n"

    end = next(
        (j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")),
        len(lines),
    )
    insert_at = end
    while insert_at - 1 > start and lines[insert_at - 1].strip() == "":
        insert_at -= 1  # keep the new bullet inside the section, before trailing blanks
    lines.insert(insert_at, line)
    return "\n".join(lines)


def deprecate_requirement(prd_text: str, rid: str, replaced_by: str) -> str:
    """Mark ``rid`` deprecated in place, naming the ``R{n}`` that replaced it."""
    pattern = re.compile(rf"(- \*\*{re.escape(rid)}\*\*[^\n]*)")

    def repl(m: re.Match[str]) -> str:
        s = m.group(1)
        return s if "устарело" in s else s + f" — **устарело, заменено на {replaced_by}**"

    new_text, n = pattern.subn(repl, prd_text, count=1)
    if n == 0:
        raise ValueError(f"requirement {rid} not found in PRD")
    return new_text
