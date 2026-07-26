# Установка и настройка

Всё, что требует твоего участия, собрано здесь. Разделы 1–3 нужны, чтобы
пользоваться ядром (управление PRD/спеками/задачами + аудит). Раздел 4 — чтобы
включить реальные внешние действия (PR / APK / Telegram). Раздел 5 — новый
GitHub-репозиторий платформы. Раздел 6 — перенос на сервер.

---

## 1. Что нужно на машине

| Инструмент | Зачем | Проверка |
|---|---|---|
| **Python 3.11** | рантайм MCP (FastMCP требует ≥3.10) | `python3.11 --version` |
| **uv** | окружение и зависимости | `uv --version` |
| git | версионирование | `git --version` |
| gh *(для PR)* | создание pull request | `gh --version` |
| fvm/flutter *(для APK)* | сборка приложения | `fvm flutter --version` |

На этой машине Python 3.11 и uv уже стоят через Homebrew (`brew install
python@3.11 uv`).

> **Особенность этой машины:** каталог `~/.local` принадлежит `root`, поэтому uv
> не может использовать дефолтные пути. Рядом лежит `mcp/uv.toml` (в `.gitignore`),
> который направляет uv на writable-кэш (`~/Library/Caches/uv`) и системный
> Python 3.11 (`python-preference = "only-system"`, `python-downloads = "never"`).
> На нормальной машине этот файл не нужен — удали его там, и uv возьмёт дефолты.

---

## 2. Установка и проверка

```bash
cd /Users/pavelsmirnov/projects/regagro/sdlc-platform/mcp
uv sync                          # поставить всё по uv.lock
uv run pytest                    # все тесты зелёные
uv run python scripts/smoke.py   # поднять сервер по stdio и вызвать инструменты
uv run sdlc-audit history        # история изменений (пусто в начале)
```

---

## 3. Регистрация MCP-сервера в Claude Code

Claude Code запускает сервер как подпроцесс по stdio. Два способа.

### Способ А — файл `.mcp.json` (в корне рабочей области)

Скопируй `.mcp.json.example` в `.mcp.json` рабочей области, где запускаешь Claude
Code (можно и в самом `agro_system`, чтобы вести код приложения и процесс из
одного места):

```json
{
  "mcpServers": {
    "sdlc-platform": {
      "command": "uv",
      "args": ["--directory",
               "/Users/pavelsmirnov/projects/regagro/sdlc-platform/mcp",
               "run", "sdlc-mcp"],
      "env": {
        "SDLC_ROOT": "/Users/pavelsmirnov/projects/regagro/sdlc-platform/sdlc",
        "APP_REPO_PATH": "/Users/pavelsmirnov/projects/regagro/agro_system"
      }
    }
  }
}
```

`--directory` важен: uv должен стартовать в `mcp/`, чтобы подхватить `uv.toml`.
Если `uv` не на PATH у Claude Code — укажи абсолютный путь `/opt/homebrew/bin/uv`.

### Способ Б — команда

```bash
claude mcp add sdlc-platform \
  -e SDLC_ROOT=/Users/pavelsmirnov/projects/regagro/sdlc-platform/sdlc \
  -e APP_REPO_PATH=/Users/pavelsmirnov/projects/regagro/agro_system \
  -- uv --directory /Users/pavelsmirnov/projects/regagro/sdlc-platform/mcp run sdlc-mcp
```

Проверка: в сессии Claude Code выполни `/mcp` — сервер `sdlc-platform` должен
появиться с инструментами (`business_task_create`, `validate_tree`, …) и
промптами (`run_pass`, `new_feature`, `tdd_task`).

Секреты (Telegram/GitHub-токен) в `.mcp.json` **не клади** — они идут через
`mcp/.env` (раздел 4), который сервер грузит сам и который в `.gitignore`.

---

## 4. Включение реальных внешних действий

Без ключей `open_pull_request` и `build_and_deliver_apk` работают на **фейках**
(записывают вызов, возвращают `used_fake: true`) — безопасно для разработки.
Ниже — как включить настоящие.

Скопируй шаблон и заполняй по мере готовности:

```bash
cp mcp/.env.example mcp/.env
```

### 4.1 GitHub — создание PR

1. Установи и авторизуй gh (один раз):
   ```bash
   brew install gh        # если ещё нет
   gh auth login          # выбери GitHub.com → SSH → браузер
   gh auth status         # должно показать залогиненного пользователя
   ```
2. Убедись, что `APP_REPO_PATH` в `mcp/.env` указывает на `agro_system`.
3. Как это работает: `open_pull_request` в каталоге приложения делает
   `git push -u origin <текущая ветка>` и `gh pr create --base develop --head
   <ветка> --title … --body …`, возвращает URL PR. Ветку с изменениями готовит
   Claude Code до вызова (правки кода → коммит на feature-ветке).

> Пока `gh` не авторизован или `APP_REPO_PATH` пуст — PR остаётся фейковым.

### 4.2 Telegram — доставка APK

1. Создай бота: напиши **@BotFather** в Telegram → `/newbot` → имя и username →
   получишь **токен** вида `123456:ABC-DEF...`.
2. Узнай **chat_id**, куда слать сборки:
   - напиши своему боту любое сообщение (или добавь его в нужную группу и
     напиши там);
   - открой `https://api.telegram.org/bot<ТОКЕН>/getUpdates` в браузере;
   - в ответе возьми `result[].message.chat.id` (для группы — отрицательное
     число). Альтернатива: спросить `@userinfobot` свой id.
3. Впиши в `mcp/.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=123456789
   ```
4. Проверка вручную (не обязательно):
   ```bash
   curl -F chat_id=<CHAT_ID> -F document=@/путь/к/файлу.txt \
     "https://api.telegram.org/bot<ТОКЕН>/sendDocument"
   ```

### 4.3 APK — сборка

- `build_and_deliver_apk(flavor="prod")` запускает в `agro_system`
  `fvm flutter build apk --flavor prod --dart-define=IS_PROD=true` (или `flutter`,
  если fvm недоступен), затем шлёт `build/app/outputs/flutter-apk/app-prod-release.apk`
  в Telegram.
- Для релизной сборки в приложении должна быть настроена **подпись** (release
  keystore в `android/`). Если подпись не настроена — используй `flavor="dev"`
  для отладочной сборки.
- Требуется `APP_REPO_PATH` и рабочий `fvm/flutter`.

---

## 5. Новый GitHub-репозиторий платформы

Локальный git уже инициализирован (ветка `main`). Чтобы поднять удалённый:

```bash
cd /Users/pavelsmirnov/projects/regagro/sdlc-platform
git add -A
git commit -m "SDLC-платформа: MCP-сервер + дерево sdlc + аудит"

# приватный репозиторий и push одной командой (нужен gh auth):
gh repo create regagro-sdlc-platform --private --source=. --remote=origin --push
```

Без gh — создай пустой репозиторий на github.com и:

```bash
git remote add origin git@github.com:<owner>/regagro-sdlc-platform.git
git push -u origin main
```

Что коммитится: `sdlc/`, `mcp/` (код + `uv.lock` + тесты), `docs/`. Что нет
(в `.gitignore`): `mcp/.venv/`, `mcp/var/` (аудит-БД и транскрипты), `mcp/.env`,
`mcp/uv.toml`.

---

## 6. Перенос на сервер (позже)

1. Склонируй репозиторий платформы на сервер.
2. Поставь Python 3.11 + uv штатно. Если `~/.local` не принадлежит root — файл
   `mcp/uv.toml` не нужен вовсе.
3. `cd mcp && uv sync`.
4. `mcp/.env` — секреты сервера (Telegram/gh). `SDLC_ROOT` по умолчанию —
   `../sdlc` рядом с `mcp/`.
5. Запуск: для Claude Code по-прежнему stdio. Для постоянного сервиса/HTTP —
   добавить HTTP/SSE-транспорт (тот же `FastMCP`, другой `mcp.run(...)`) и завести
   под systemd/pm2. Это отдельный шаг v2.

---

## 7. Траблшутинг

- **`failed to create directory ~/.local/share/uv`** — тот самый root-owned
  `~/.local`. Проверь, что рядом есть `mcp/uv.toml` с `cache-dir`,
  `python-preference = "only-system"`, `python-downloads = "never"`.
- **`/mcp` не видит сервер** — проверь путь в `--directory` и что `uv` на PATH у
  Claude Code (или пропиши `/opt/homebrew/bin/uv`). Запусти вручную
  `uv --directory .../mcp run sdlc-mcp` — сервер должен ждать stdio без ошибок.
- **PR/APK/Telegram отвечают `used_fake: true`** — ключи ещё не заданы (раздел 4)
  или `gh` не авторизован / нет `APP_REPO_PATH`.
- **Тест на Python < 3.11** — активируй правильный интерпретатор: `uv` берёт 3.11
  автоматически по `.python-version`.
