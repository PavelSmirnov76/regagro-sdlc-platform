# Архитектура

## Слои

```
Claude Code (агент, «мозг»)
        │  MCP (stdio)
        ▼
server.py            FastMCP: tools / resources / prompts — тонкие обёртки
        │
        ▼
service.py           SdlcService: единственное место, где происходит мутация;
        │            каждая = закон + строка аудита + запись в транскрипт
   ┌────┼───────────────┬──────────────────┐
   ▼    ▼               ▼                  ▼
 law/  audit/       transcript/       integrations/
 (закон  (SQLite     (JSONL на         (PR/APK/Telegram:
  SDLC)   леджер)     сессию)           Protocol + fake + real)
```

- **`law/`** — чистые функции над деревом `sdlc/`, без знания об MCP/БД/сети.
  Принимают явный `sdlc_root`, поэтому полностью тестируются на временном дереве.
  - `ids` — выдача/резолв id (glob-max+1, считая захороненные).
  - `frontmatter` — цитаты `[ID](path)` и bold-bullet преамбула.
  - `templates` — файловые шаблоны по типам (BT/MOD/ACTOR/ENT/EVT/UC) с точными
    обязательными секциями из соответствующих `AGENTS.md`.
  - `artifacts` — `write_new` (запрещает перезапись = freeze), `read`, `list`.
  - `prd` — единственная in-place правка: снапшот в `history/`, вставка/депрекейт `R{n}`.
  - `entomb` — перенос в `obsolete/` + заголовок when/why/superseded-by.
  - `supersede` — новый артефакт + захоронение старого.
  - `validate` — целостность: коллизии id (ошибка), висячие/стейл цитаты (на ревью).
- **`audit/`** — отдельная SQLite-БД (`changes`, `sessions`) + `sdlc-audit` CLI.
- **`transcript/`** — append-only JSONL на сессию (запрос, вопросы, вызовы, дельты).
- **`integrations/`** — `base.py` (Protocol'ы) + `fakes.py` + реальные
  `git_ops`/`apk_build`/`telegram`; `factory.build(cfg)` выбирает real/fake.
- **`service.py`** — оркестрация: `create_*`, `entomb_artifact`, `prd_*`,
  `open_pull_request`, `build_and_deliver_apk`, `validate`, `audit_history`.
- **`server.py`** — регистрация инструментов/ресурсов/промптов FastMCP.

## Поток данных при создании артефакта

1. `service.create_module(name=…, derived_from_bt="BT-4", …)`
2. `ids.allocate("MOD")` → `MOD-8`; `_cite("MOD","BT-4")` строит `[BT-4](…)`.
3. `templates.module(...)` → `(rel_path, content)`.
4. `artifacts.write_new` пишет файл (упадёт, если файл уже есть — freeze).
5. `ledger.record(action="create_module", …, new_content=content)` → строка аудита.
6. `SessionLog.append("artifact_created", …)` → строка транскрипта.
7. Если `supersede_of` задан — `entomb` старого + вторая строка аудита.

## Почему так

- **Закон отдельно от MCP.** `law/` не импортирует ни `mcp`, ни `sqlite3` — его
  можно переиспользовать и тестировать без сервера.
- **Одна точка мутации.** Всё идёт через `SdlcService`, поэтому невозможно
  изменить дерево, не оставив следа в аудите и транскрипте.
- **Фейки по умолчанию.** Разработка ядра не блокируется отсутствием ключей;
  реальные PR/APK/Telegram включаются конфигом, а не переписыванием кода.

## Точки расширения

- Новый тип артефакта: добавить в `ids.FILE_ID_TYPES`, `templates`, метод
  `create_*` в сервисе, инструмент в сервере — с тестом (red-green).
- HTTP/SSE-транспорт (для сервера) — тот же `FastMCP`, другой `mcp.run(...)`.
- Встроенный agent-loop (если понадобится) — поверх `SdlcService`, не вместо него.
