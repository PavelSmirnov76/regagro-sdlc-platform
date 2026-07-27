# Установка и настройка

Всё, что требует твоего участия, собрано здесь. Разделы 1–3 нужны, чтобы
пользоваться ядром локально (управление PRD/спеками/задачами + аудит). Раздел 4 —
чтобы включить реальные внешние действия (PR / APK / Telegram). Раздел 5 — новый
GitHub-репозиторий платформы. Раздел 6 — развёртывание на сервере как **общего
коннектора для claude.ai** (участники работают прямо с сайта).

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

> Это **локальный** режим (stdio) для разработчика. Общий доступ, когда
> участники работают прямо из **claude.ai** (кастомный коннектор по HTTPS с
> токеном), — в разделе 6.

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

## 6. Развёртывание на сервере (общий коннектор для claude.ai)

Цель: MCP крутится на сервере под `systemd`, наружу отдаётся через `nginx` по
HTTPS с проверкой токена, и участник добавляет его в **claude.ai → Settings →
Connectors** как кастомный коннектор по URL `https://<домен>/sse?token=<токен>` —
и работает с процессом прямо из чата. Мозг — его же Claude на claude.ai; сервер
только предоставляет инструменты.

Ниже — по факту развёрнутого стенда (`ra-mcp-4.skobeltsyn.com`, Ubuntu 22.04).
Нужны: домен, чей A-запись указывает на сервер, и открытые наружу порты 80/443.

### 6.1 Код и окружение на сервере

```bash
# репозиторий платформы (через GitHub, deploy key — приложение остаётся своим репо)
git clone git@github.com:<owner>/regagro-sdlc-platform.git /root/sdlc-platform
cd /root/sdlc-platform/mcp
uv sync                          # Python 3.11; ~/.local не root-owned -> uv.toml не нужен
uv run pytest                    # зелёные
```

### 6.2 `mcp/.env` — сетевой транспорт + токен

`.env` в `.gitignore`, живёт только на сервере (`chmod 600`). Токен — длинный
случайный (`openssl rand -hex 32`):

```bash
cat > /root/sdlc-platform/mcp/.env <<EOF
MCP_TRANSPORT=sse
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_TOKEN=$(openssl rand -hex 32)
SDLC_ROOT=/root/sdlc-platform/sdlc
EOF
chmod 600 /root/sdlc-platform/mcp/.env
```

`MCP_HOST=127.0.0.1` — процесс слушает только локально, наружу его выставляет
nginx. Без `MCP_AUTH_TOKEN` транспорт поднимется **без гейта** — на публичном
сервере токен обязателен. По умолчанию DNS-rebinding защита отключена (граница —
токен + TLS); чтобы пинить хосты, задай `MCP_ALLOWED_HOSTS=<домен>`.

### 6.3 systemd-сервис

```ini
# /etc/systemd/system/sdlc-mcp.service
[Unit]
Description=SDLC MCP server (SSE transport, token-gated)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/sdlc-platform/mcp
ExecStart=/root/.local/bin/uv run sdlc-mcp
Restart=on-failure
RestartSec=2
User=root

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable --now sdlc-mcp
# проверка на самом сервере: без токена 401, с токеном открывается SSE-поток
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/sse                     # 401
curl -sN --max-time 2 "http://127.0.0.1:8000/sse?token=<ТОКЕН>" | head -2              # event: endpoint
```

Сервер грузит `.env` сам (python-dotenv) — путь абсолютный, от cwd не зависит.

### 6.4 nginx (reverse proxy, SSE-настройки)

```bash
apt-get update && apt-get install -y nginx
```

```nginx
# /etc/nginx/sites-available/sdlc-mcp
server {
    listen 80;
    listen [::]:80;
    server_name <домен>;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # SSE: стримить сразу, держать соединение открытым
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        chunked_transfer_encoding off;
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/sdlc-mcp /etc/nginx/sites-enabled/sdlc-mcp
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 6.5 TLS (Let's Encrypt) — claude.ai требует HTTPS

```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d <домен> --non-interactive --agree-tos \
        --register-unsafely-without-email --redirect
```

certbot добавит 443-блок с сертификатом и редирект 80→443, поднимет таймер
автопродления. Проверка снаружи:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<домен>/sse                # 401
curl -sN --max-time 3 "https://<домен>/sse?token=<ТОКЕН>" | head -2          # event: endpoint
```

### 6.6 Подключение в claude.ai

Отдай участнику URL `https://<домен>/sse?token=<ТОКЕН>` (SSE). В claude.ai →
**Settings → Connectors → Add custom connector** → вставить URL → Add. В чате
появятся инструменты `sdlc-platform` и промпты `run_pass`/`new_feature`/`tdd_task`.

> `/messages/` (куда клиент шлёт сообщения после `/sse`) намеренно открыт без
> токена — он защищён неугадываемым `session_id`, выдаваемым только после
> аутентифицированного `/sse` (см. `mcp/src/sdlc_mcp/transport.py`).

### 6.7 Эксплуатация

- **Обновить код:** `cd /root/sdlc-platform && git pull && systemctl restart sdlc-mcp`.
- **Сменить/отозвать токен:** перегенерируй `MCP_AUTH_TOKEN` в `.env` →
  `systemctl restart sdlc-mcp`. Старый URL сразу перестаёт работать; раздай новый.
- **Логи:** `journalctl -u sdlc-mcp -f`. Токен виден в access-логах (он в URL) —
  для секрета настрой маскирование query-string или переходи на Bearer-заголовок.
- **PR/APK/Telegram с сервера** требуют на нём `APP_REPO_PATH` (клон приложения),
  `gh`/ключей и Flutter (раздел 4); без них эти действия остаются фейками.

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
- **claude.ai не подключает коннектор / всё время 401** — URL должен быть
  `https://<домен>/sse?token=<ТОКЕН>`; проверь `systemctl status sdlc-mcp` и
  `curl -sN "https://<домен>/sse?token=<ТОКЕН>"` (должен пойти `event: endpoint`).
  Токен в `.env` и в URL обязаны совпадать (после смены — `systemctl restart`).
- **Коннектор подключился, но инструменты «висят»** — nginx буферизует SSE:
  убедись, что в конфиге есть `proxy_buffering off` и длинные `proxy_read_timeout`
  (§6.4). Если в логах отлуп по `Host` — задай `MCP_ALLOWED_HOSTS=<домен>` или
  оставь пустым (DNS-rebinding защита выключается).
