"""Scaffold the numbered SDLC pipeline into a target repo.

A Python port of ``Skills-main/skills/sdlc-scaffold/scripts/scaffold.sh``:
copy the bundled stage templates (0-vibes … 9-observation, each with
README/AGENTS/CLAUDE + the root RUNBOOK) into ``<target>/<container>/``,
substituting ``{{PROJECT_NAME}}``. Structure and conventions only — no domain
content. Idempotent (existing files are skipped unless ``force``); ``force``
backs the container up first; a marked, idempotent pointer is added to the host
``CLAUDE.md`` so an agent at the repo root discovers the pipeline.

Pure filesystem logic — no MCP, db, or network. The service layer adds the
audit/transcript records.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

POINTER_MARK = "sdlc-scaffold:pipeline"


@dataclass
class ScaffoldReport:
    dest_root: str
    container: str
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    backup: str | None = None
    host_pointer: str | None = None  # CLAUDE.md path updated, else None
    dry_run: bool = False


def bundled_templates() -> Path:
    """The stage templates shipped with the engine."""
    return Path(__file__).resolve().parent.parent / "scaffold_templates"


def _next_backup(dest_root: Path) -> Path:
    n = 1
    while (dest_root.parent / f"{dest_root.name}.bak-{n}").exists():
        n += 1
    return dest_root.parent / f"{dest_root.name}.bak-{n}"


def _pointer_block(container: str, *, lead_newline: bool) -> str:
    lead = "\n" if lead_newline else ""
    return (
        f"{lead}<!-- {POINTER_MARK} -->\n"
        "## SDLC pipeline\n\n"
        f"This project runs the numbered SDLC pipeline in `{container}/`. To run a pass —\n"
        "absorb new data, update the PRD, and fan the change through specs, design,\n"
        f"and tasks — follow `{container}/RUNBOOK.md`. The rules are in `{container}/AGENTS.md`.\n"
        f"<!-- /{POINTER_MARK} -->\n"
    )


def _add_host_pointer(target: Path, container: str, dry_run: bool) -> str | None:
    """Point the host CLAUDE.md at the pipeline (marked, idempotent)."""
    cm = target / "CLAUDE.md"
    if (target / ".claude" / "CLAUDE.md").is_file():
        cm = target / ".claude" / "CLAUDE.md"

    existed = cm.is_file()
    if existed and POINTER_MARK in cm.read_text(encoding="utf-8"):
        return None  # already pointed
    if dry_run:
        return str(cm)

    cm.parent.mkdir(parents=True, exist_ok=True)
    with cm.open("a", encoding="utf-8") as f:
        f.write(_pointer_block(container, lead_newline=existed))
    return str(cm)


def scaffold_tree(
    target: Path,
    *,
    templates_dir: Path | None = None,
    container: str = "sdlc",
    project_name: str = "Project",
    force: bool = False,
    dry_run: bool = False,
    host_pointer: bool = True,
) -> ScaffoldReport:
    """Scaffold the pipeline into ``target``; see the module docstring."""
    templates = (templates_dir or bundled_templates()).resolve()
    if not templates.is_dir():
        raise FileNotFoundError(f"templates not found at {templates}")

    target = target.expanduser()
    flat = container in ("", ".")
    dest_root = target if flat else target / container
    report = ScaffoldReport(
        dest_root=str(dest_root),
        container="." if flat else container,
        dry_run=dry_run,
    )

    srcs = sorted(
        p for p in templates.rglob("*") if p.is_file() and p.name != ".DS_Store"
    )

    backed_up = False
    for src in srcs:
        rel = src.relative_to(templates)
        dest = dest_root / rel

        if dest.exists() and not force:
            report.skipped.append(str(rel))
            continue

        # Only an existing file is at risk; back the container up once, lazily.
        if dest.exists() and not backed_up:
            if dry_run:
                report.backup = str(_next_backup(dest_root))
            else:
                bak = _next_backup(dest_root)
                shutil.copytree(dest_root, bak)
                report.backup = str(bak)
            backed_up = True

        report.created.append(str(rel))
        if dry_run:
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8").replace(
            "{{PROJECT_NAME}}", project_name
        )
        dest.write_text(text, encoding="utf-8")

    if not flat and host_pointer:
        report.host_pointer = _add_host_pointer(target, container, dry_run)

    return report
