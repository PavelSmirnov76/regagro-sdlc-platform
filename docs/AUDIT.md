# Аудит и транскрипт

Два независимых журнала на каждое действие.

## Аудит-БД (`mcp/var/audit.db`, SQLite)

Что менялось в дереве. Отдельная БД, `.gitignore`-нута (это runtime-данные, не
исходники). Таблицы:

- **`changes`** — по строке на мутацию: `ts`, `session_id`, `actor_human`,
  `actor_agent`, `action`, `artifact_type`, `artifact_id`, `path`, `summary`,
  `prev_hash`, `new_hash`, `diff`, `extra_json`.
- **`sessions`** — `session_id`, `started_ts`, `human`, `title`, `status`.

Содержимое не хранится целиком — только короткие sha256-отпечатки (`prev_hash`,
`new_hash`), чтобы БД не пухла; полные версии артефактов и так лежат в git и в
`history/` (для PRD).

### Команда истории

```bash
uv run sdlc-audit history                       # всё, свежее сверху
uv run sdlc-audit history --artifact BT-14      # по артефакту
uv run sdlc-audit history --type MOD            # по типу
uv run sdlc-audit history --action entomb       # по действию
uv run sdlc-audit history --session S-2026...   # по сессии
uv run sdlc-audit history --since 2026-07-01 --limit 20
```

Пример вывода:

```
[   1] 2026-07-26T16:25:33+00:00  create_business_task BT-14   pavel   новая бизнес-задача QR
[   3] 2026-07-26T16:25:33+00:00  entomb               MOD-3   pavel   superseded by MOD-8
```

Через MCP то же самое — инструмент `audit_history`.

## Транскрипт сессии (`mcp/var/transcripts/{session_id}.jsonl`)

Как шла сессия: запрос человека, вопросы/ответы, вызовы инструментов,
предложенные и утверждённые дельты, результаты. Append-only JSONL, по файлу на
сессию. Читается инструментом `transcript_read` или прямо из файла.

`session_id` (например `S-20260726-162533-ab12`) пишется в каждую строку
`changes`, поэтому аудит и транскрипт связаны: по строке аудита находишь сессию,
по сессии — весь контекст, в котором изменение было сделано.

## Что считается «изменением»

Любой вызов сервиса, меняющий дерево: `create_*`, `entomb_artifact`,
`prd_add_requirement` / `prd_deprecate_requirement` / `prd_propose_edit`,
`open_pull_request`, `build_and_deliver_apk`, а также `session_note`. Чистые
чтения (`read_*`, `list_*`, `allocate_id`, `validate_tree`) не пишут в аудит.

## Граница гарантии

Аудит покрывает изменения, сделанные **через инструменты MCP**. Прямое ручное
редактирование файлов `sdlc/` в обход сервера аудит не увидит — поэтому
санкционированный путь правок это инструменты, а `validate_tree` ловит
структурные нарушения постфактум. Жёсткое ограничение (например git-hook,
отклоняющий неаудированные изменения) — кандидат в следующую версию.
