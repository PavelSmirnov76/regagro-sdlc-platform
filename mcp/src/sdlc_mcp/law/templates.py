"""File templates for each artifact type.

Each function returns ``(rel_path, content)``: the path under ``sdlc_root`` the
artifact must live at (encoding its frozen id + name) and the Markdown body with
the required section skeleton. Cross-references are passed in already rendered as
``[ID](path)`` links (built by the caller via
:func:`sdlc_mcp.law.frontmatter.citation_link`), so templates stay pure string
builders and never touch the filesystem.

The section headers here mirror each stage's ``AGENTS.md`` exactly, so an
artifact produced from a template passes the tree's own conventions.
"""

from __future__ import annotations

import re
from pathlib import Path

CRUD = ("CREATE", "READ", "UPDATE", "DELETE")
OUTCOME = ("OK", "ERROR", "REJECTED")
SEVERITY_DIR = {"ERROR": "errors", "WARNING": "warnings", "INFO": "infos"}

# Folder each artifact type is created in — also where citation links are
# computed relative to.
REL_DIRS = {
    "BT": "1-business-tasks/planning",
    "MOD": "2-specs/modules",
    "ACTOR": "2-specs/actors",
    "ENT": "2-specs/entities",
    "EVT": "2-specs/events",
    "UC": "2-specs/use-cases",
}


def slug(text: str) -> str:
    """``"QR visual tag scan" -> "QR-VISUAL-TAG-SCAN"`` — a filename-safe token."""
    return re.sub(r"[^A-Za-z0-9]+", "-", text.strip().upper()).strip("-")


def link_dir(sdlc_root: Path, type_: str) -> Path:
    """Directory citation links from a ``type_`` artifact are relative to."""
    return sdlc_root / REL_DIRS[type_]


def _checkboxes(items: list[str] | None) -> str:
    items = items or ["TBD"]
    return "\n".join(f"- [ ] {it}" for it in items)


# --------------------------------------------------------------------------- #
# 1 — business tasks
# --------------------------------------------------------------------------- #
def business_task_planning(
    *,
    bt_id: str,
    name: str,
    requirement_links: list[str],
    title: str | None = None,
    raw_note: str = "нет.",
    current_state: str = "TBD.",
    what_to_do: str = "TBD.",
    acceptance: list[str] | None = None,
    open_questions: str = "Нет.",
    surfaced_by_link: str | None = None,
) -> tuple[str, str]:
    # ``name`` is the ASCII filename token (e.g. AUTH); ``title`` is the heading.
    heading = title or name
    preamble = [f"- **raw**: {raw_note}"]
    if surfaced_by_link:
        preamble.append(f"- **surfaced by**: {surfaced_by_link}")
    reqs = ", ".join(requirement_links) if requirement_links else "нет."
    preamble.append(f"- **requirements**: {reqs}")
    rel = f"1-business-tasks/planning/{bt_id}-PLANNING-{slug(name)}.md"
    content = (
        "\n".join(preamble) + "\n\n"
        f"# {bt_id} — {heading}\n\n"
        f"## Текущее состояние\n\n{current_state}\n\n"
        f"## Что делать\n\n{what_to_do}\n\n"
        f"## Критерии приёмки\n\n{_checkboxes(acceptance)}\n\n"
        f"## Открытые вопросы\n\n{open_questions}\n"
    )
    return rel, content


def business_task_observation(
    *,
    bt_id: str,
    severity: str,
    name: str,
    requirement_links: list[str],
    title: str | None = None,
    raw_note: str = "нет.",
    description: str = "TBD.",
    acceptance: list[str] | None = None,
    open_questions: str = "Нет.",
) -> tuple[str, str]:
    severity = severity.upper()
    if severity not in SEVERITY_DIR:
        raise ValueError(f"severity must be one of {tuple(SEVERITY_DIR)}: {severity!r}")
    heading = title or name
    reqs = ", ".join(requirement_links) if requirement_links else "нет."
    rel = (
        f"1-business-tasks/observation/{SEVERITY_DIR[severity]}/"
        f"{bt_id}-{severity}-{slug(name)}.md"
    )
    content = (
        f"- **raw**: {raw_note}\n- **requirements**: {reqs}\n\n"
        f"# {bt_id} — {heading}\n\n"
        f"## Наблюдение\n\n{description}\n\n"
        f"## Критерии приёмки\n\n{_checkboxes(acceptance)}\n\n"
        f"## Открытые вопросы\n\n{open_questions}\n"
    )
    return rel, content


# --------------------------------------------------------------------------- #
# 2 — specs
# --------------------------------------------------------------------------- #
def module(
    *,
    mod_id: str,
    name: str,
    derived_from_link: str,
    purpose: str = "TBD.",
    composition: str = "TBD.",
    boundary: str = "TBD.",
) -> tuple[str, str]:
    name = name.upper()
    rel = f"2-specs/modules/{mod_id}-{name}.md"
    content = (
        f"- **derived from**: {derived_from_link}\n\n"
        f"# {mod_id} — {name}\n\n"
        f"## Назначение\n\n{purpose}\n\n"
        f"## Состав\n\n{composition}\n\n"
        f"## Граница\n\n{boundary}\n"
    )
    return rel, content


def actor(
    *,
    actor_id: str,
    name: str,
    module: str,
    title: str,
    identity: str = "TBD.",
    goals: str = "TBD.",
    permissions: str = "TBD.",
    interacts_links: list[str] | None = None,
) -> tuple[str, str]:
    name, module = name.upper(), module.upper()
    rel = f"2-specs/actors/{actor_id}-{name}-IN-{module}.md"
    interacts = (
        "\n\n## Взаимодействует с\n\n" + ", ".join(interacts_links)
        if interacts_links
        else ""
    )
    content = (
        f"# {actor_id} — {title}\n\n"
        f"## Идентичность\n\n{identity}\n\n"
        f"## Цели\n\n{goals}\n\n"
        f"## Права\n\n{permissions}{interacts}\n"
    )
    return rel, content


def entity(
    *,
    ent_id: str,
    name: str,
    module: str,
    title: str,
    owning_module_link: str,
    description: str = "TBD.",
    fields: list[tuple[str, str, str]] | None = None,
    source_rows: list[tuple[str, str, str, str]] | None = None,
) -> tuple[str, str]:
    name, module = name.upper(), module.upper()
    rel = f"2-specs/entities/{ent_id}-{name}-IN-{module}.md"
    fields = fields or [("id", "int", "идентификатор")]
    ftable = "| Поле | Тип | Описание |\n|---|---|---|\n" + "\n".join(
        f"| {a} | {b} | {c} |" for a, b, c in fields
    )
    source_rows = source_rows or [("lib/…", "Symbol", "CURRENT", "роль")]
    stable = "| File | Symbol | Status | Role |\n|---|---|---|---|\n" + "\n".join(
        f"| {a} | {b} | {c} | {d} |" for a, b, c, d in source_rows
    )
    content = (
        f"# {ent_id} — {title}\n\n"
        f"## Описание\n\nВладеющий модуль: {owning_module_link}. {description}\n\n"
        f"## Поля\n\n{ftable}\n\n"
        f"## Исходный код\n\n{stable}\n"
    )
    return rel, content


def event(
    *,
    evt_id: str,
    name: str,
    module: str,
    title: str,
    initiator_link: str,
    entity_links: list[str],
    trigger: str = "TBD.",
    effect: str = "TBD.",
    source: str = "TBD.",
) -> tuple[str, str]:
    name, module = name.upper(), module.upper()
    rel = f"2-specs/events/{evt_id}-{name}-IN-{module}.md"
    ents = ", ".join(entity_links) if entity_links else "—"
    content = (
        f"# {evt_id} — {title}\n\n"
        f"| Инициатор | {initiator_link} |\n|---|---|\n"
        f"| Модуль | {module} |\n"
        f"| Сущность(и) | {ents} |\n\n"
        f"**Триггер.** {trigger}\n\n"
        f"**Эффект.** {effect}\n\n"
        f"**Исходный код.** {source}\n"
    )
    return rel, content


def use_case(
    *,
    uc_id: str,
    actor_id: str,
    evt_id: str,
    ent_id: str,
    crud: str,
    outcome: str,
    module: str,
    title: str,
    actor_link: str,
    event_link: str,
    entity_links: list[str],
    purpose: str = "TBD.",
    current_main: str = "TBD.",
    current_alt: str = "Нет.",
    related_entity_links: list[str] | None = None,
    business_rules: str = "Нет.",
    target: str = "Не отличается от CURRENT.",
    tbd: str = "Нет.",
    tech_deps: str = "TBD.",
    acceptance: list[str] | None = None,
    tests: str = "TBD — теста нет.",
    open_questions: str = "Нет.",
) -> tuple[str, str]:
    crud, outcome, module = crud.upper(), outcome.upper(), module.upper()
    if crud not in CRUD:
        raise ValueError(f"crud must be one of {CRUD}: {crud!r}")
    if outcome not in OUTCOME:
        raise ValueError(f"outcome must be one of {OUTCOME}: {outcome!r}")
    result = f"{crud}_{outcome}"
    rel = (
        f"2-specs/use-cases/"
        f"{uc_id}-{actor_id}-{evt_id}-{ent_id}-{result}-IN-{module}.md"
    )
    related = ", ".join(related_entity_links or entity_links)
    content = (
        f"# {uc_id} — {title}\n\n"
        f"## Назначение\n\nПокрывает {event_link}. {purpose}\n\n"
        f"## Пользователь\n\n{actor_link}\n\n"
        f"## CURRENT\n\n"
        f"### Основной поток\n\n{current_main}\n\n"
        f"### Альтернативные потоки\n\n{current_alt}\n\n"
        f"### Связанные сущности\n\n{related}\n\n"
        f"### Бизнес-правила\n\n{business_rules}\n\n"
        f"## TARGET\n\n{target}\n\n"
        f"## TBD / BLOCKED\n\n{tbd}\n\n"
        f"## Технические зависимости\n\n{tech_deps}\n\n"
        f"## Критерии приёмки\n\n{_checkboxes(acceptance)}\n\n"
        f"## Связанные тесты\n\n{tests}\n\n"
        f"## Открытые вопросы и ограничения\n\n{open_questions}\n"
    )
    return rel, content
