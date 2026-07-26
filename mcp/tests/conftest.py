"""Shared fixtures: a throwaway, law-valid ``sdlc/`` tree and a temp audit DB."""

from __future__ import annotations

from pathlib import Path

import pytest

MINI_PRD = """# PRD — mini

| | |
|---|---|
| Источник | fixture |

## Purpose & scope

A tiny PRD for tests.

## Goals and non-goals

- Goal: exercise the law.

## Requirements

- **R12** — Guest can self-register.
- **R13** — User can log in with login/password.
- **R14** — User can reset the password.

## Success metrics

- Tests pass.
"""

MINI_BT1 = """- **raw**: нет — часть первого прохода.
- **requirements**: [R12](../../0-vibes/prd/PRD.md), [R13](../../0-vibes/prd/PRD.md).

# BT-1 — Специфицировать модуль AUTH

## Текущее состояние

Модуль авторизации в проде.

## Что делать

Написать глоссарий и use-case спеки.

## Критерии приёмки

- [ ] MOD-1 написан.

## Открытые вопросы

Нет.
"""

MINI_UC1 = """# UC-1 — Гость саморегистрируется

## Назначение

Покрывает [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md).

## CURRENT

### Основной поток

Работает.

### Альтернативные потоки

Нет.

### Связанные сущности

[ENT-1](../entities/ENT-1-USER-IN-AUTH.md).

### Бизнес-правила

Нет.

## TARGET

Не отличается от CURRENT.

## TBD / BLOCKED

Нет.

## Технические зависимости

Нет.

## Критерии приёмки

- [ ] Регистрация проходит.

## Связанные тесты

TBD — теста нет.

## Открытые вопросы и ограничения

Нет.
"""


def _w(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mini_sdlc(tmp_path: Path) -> Path:
    """A minimal but law-valid ``sdlc/`` tree rooted at ``tmp_path/sdlc``."""
    root = tmp_path / "sdlc"

    _w(root, "0-vibes/prd/PRD.md", MINI_PRD)
    (root / "0-vibes/prd/history").mkdir(parents=True, exist_ok=True)
    _w(root, "0-vibes/raw/2026-07-01/note.md", "raw data\n")

    # Convention files that id scans must ignore.
    _w(root, "1-business-tasks/planning/AGENTS.md", "rules\n")
    _w(root, "1-business-tasks/planning/README.md", "| BT | ... |\n")
    _w(root, "1-business-tasks/planning/BT-1-PLANNING-AUTH.md", MINI_BT1)

    _w(
        root,
        "2-specs/modules/MOD-1-AUTH.md",
        "- **derived from**: [BT-1](../../1-business-tasks/planning/BT-1-PLANNING-AUTH.md)\n\n"
        "# MOD-1 — AUTH\n\n## Назначение\n\nАвторизация.\n\n## Состав\n\nACTOR-1, ENT-1, EVT-1.\n\n## Граница\n\nНе владеет фермами.\n",
    )
    _w(root, "2-specs/actors/ACTOR-1-USER-IN-AUTH.md", "# ACTOR-1 — User\n\n## Идентичность\n\nisAuthorized().\n\n## Цели\n\nВойти.\n\n## Права\n\nВсё.\n")
    _w(root, "2-specs/entities/ENT-1-USER-IN-AUTH.md", "# ENT-1 — User\n\n## Описание\n\nВладеющий модуль: [MOD-1](../modules/MOD-1-AUTH.md).\n\n## Поля\n\n| Поле | Тип |\n|---|---|\n| id | int |\n")
    _w(root, "2-specs/events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md", "# EVT-1 — user.self_registered\n\n| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |\n|---|---|\n| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |\n\n**Триггер.** Форма.\n\n**Эффект.** Создан User.\n")
    _w(root, "2-specs/use-cases/UC-1-ACTOR-1-EVT-1-ENT-1-CREATE_OK-IN-AUTH.md", MINI_UC1)

    # An entombed module proves allocation counts obsolete ids.
    _w(root, "2-specs/modules/obsolete/MOD-2-OLDAUTH.md", "> **Entombed**\n\n# MOD-2 — OLDAUTH\n")

    return root


@pytest.fixture
def service(mini_sdlc: Path, tmp_path: Path):
    """An :class:`SdlcService` wired to the mini tree + a temp db/transcript."""
    from sdlc_mcp.config import Config
    from sdlc_mcp.service import SdlcService

    cfg = Config(
        sdlc_root=mini_sdlc,
        audit_db=tmp_path / "audit.db",
        transcript_dir=tmp_path / "transcripts",
        actor_human="pavel",
        actor_agent="test",
        app_repo=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        gh_token=None,
    )
    return SdlcService(cfg)
