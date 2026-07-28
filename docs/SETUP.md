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
        "SDLC_ROOT": "/Users/pavelsmirnov/projects/regagro/agro_system/sdlc",
        "APP_REPO_PATH": "/Users/pavelsmirnov/projects/regagro/agro_system"
      }
    }
  }
}
```

`--directory` важен: uv должен стартовать в `mcp/`, чтобы подхватить `uv.toml`.
Если `uv` не на PATH у Claude Code — укажи абсолютный путь `/opt/homebrew/bin/uv`.
`SDLC_ROOT`/`APP_REPO_PATH` указывают на **целевой проект** (его дерево `sdlc/` и
корень репозитория) — движок своего дерева не носит. Для быстрой проверки без
проекта можно не задавать `SDLC_ROOT`: возьмётся `examples/mini-sdlc`.

### Способ Б — команда

```bash
claude mcp add sdlc-platform \
  -e SDLC_ROOT=/Users/pavelsmirnov/projects/regagro/agro_system/sdlc \
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

`open_pull_request` в каталоге приложения делает `git push -u origin <ветка>` и
`gh pr create --base <APP_BASE_BRANCH> --head <ветка> …`, возвращает URL PR. Ветку
с изменениями готовит Claude (правки кода → коммит на feature-ветке) до вызова.
`RealGitOps` включается, когда задан `APP_REPO_PATH` **и** на PATH есть `gh`.

**Push** идёт по ключу репозитория. На сервере — per-repo deploy key (см. §6):
`origin` = прямой `git@github.com:<owner>/<repo>.git`, `core.sshCommand` указывает
на ключ. **Создание PR** (`gh`) — по токену.

1. Поставь `gh` (сервер Ubuntu — официальный apt-репозиторий cli.github.com;
   локально — `brew install gh`).
2. Дай `gh` токен. Проще всего — **fine-grained PAT**, ограниченный целевым репо
   (Repository access → Only select repositories → `<repo>`; Permissions →
   **Contents: RW**, **Pull requests: RW**), и положить его в `mcp/.env`:
   ```
   GH_TOKEN=github_pat_…
   ```
   `gh` подхватывает `GH_TOKEN` из окружения процесса MCP сам — `gh auth login`
   не нужен. На **записываемом** сервере пиши токен, не светя значение в терминале:
   ```bash
   printf '%s\n' 'github_pat_…' | ssh root@server \
     'read -r T; sed -i "/^GH_TOKEN=/d" mcp/.env; \
      printf "GH_TOKEN=%s\n" "$T" >> mcp/.env; systemctl restart sdlc-mcp'
   ```
   Токен держи одноразовым/коротким и отзови, когда доступ больше не нужен.
3. Задай **`APP_BASE_BRANCH`** в `.env` = ветка-база проекта (иначе PR метит в
   `develop`). Для `lifestocks` это `develop_shz_rewirte`.

> Без `gh` или `APP_REPO_PATH` PR остаётся фейком; без валидного `GH_TOKEN`
> `git push` пройдёт (deploy key), а `gh pr create` вернёт ошибку аутентификации.

### 4.2 Доставка APK — GitHub Release

`build_and_deliver_apk` собирает APK и заливает его как **asset в GitHub Release**
на репозитории приложения, возвращая ссылку. Почему релиз, а не Telegram:
сервер→GitHub работает там, где другие каналы не проходят (напр. `api.telegram.org`
недоступен из РФ), и у asset нет практического лимита размера (у Telegram-бота —
50 МБ, а debug-APK легко 250+ МБ).

- Реальную загрузку включает тот же `gh` + `GH_TOKEN` (§4.1) при заданном
  `APP_REPO_PATH`; без них — фейк (`used_fake: true`).
- Тег по умолчанию — `apk-<flavor>-<mode>-<short-sha>`; повтор на том же коммите
  перезаписывает asset (`gh release upload --clobber`).
- Тулчейн сборки на сервере (Flutter+Android SDK+JDK) — раздел 8.

### 4.3 APK — сборка (flavor / mode)

- `build_and_deliver_apk(flavor="dev", mode="debug")` запускает в репозитории
  приложения `flutter build apk --debug --flavor dev --dart-define=IS_PROD=false`
  (через `fvm`, если проект пинит версию в `.fvmrc`), артефакт —
  `build/app/outputs/flutter-apk/app-dev-debug.apk`.
- **`mode`**: `debug` подписывается авто-debug-ключом → **не нужен release
  keystore** (годится для шаринга). `release` требует настроенной подписи
  (`android/key.properties` + keystore), иначе Gradle падает на
  `SigningConfig "release" is missing … storeFile`.
- **`flavor`**: `dev`/`prod` (см. `productFlavors` в `android/app/build.gradle`).
- Требуется `APP_REPO_PATH` и рабочий `flutter`/`fvm`.

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

Два клона: **движок** (эта платформа) и **целевой проект** (его код + дерево
`sdlc/`). Оба — через GitHub (deploy key). Для лабы разумно клонировать **форк**
проекта, чтобы MCP не пушил в боевой репозиторий.

```bash
# движок
git clone git@github.com:<owner>/regagro-sdlc-platform.git /root/sdlc-platform
cd /root/sdlc-platform/mcp
uv sync                          # Python 3.11; ~/.local не root-owned -> uv.toml не нужен
uv run pytest                    # зелёные

# целевой проект (форк для лабы; deploy key с записью нужен для PR — раздел 4.1)
git clone git@github.com:<you>/agro_system.git /root/agro_system
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
# Движок наводится на ДЕРЕВО ПРОЕКТА (не платформы) — единый источник правды.
SDLC_ROOT=/root/agro_system/sdlc
APP_REPO_PATH=/root/agro_system
EOF
chmod 600 /root/sdlc-platform/mcp/.env
```

`MCP_HOST=127.0.0.1` — процесс слушает только локально, наружу его выставляет
nginx. Без `MCP_AUTH_TOKEN` транспорт поднимется **без гейта** — на публичном
сервере токен обязателен. По умолчанию DNS-rebinding защита отключена (граница —
токен + TLS); чтобы пинить хосты, задай `MCP_ALLOWED_HOSTS=<домен>`.
`SDLC_ROOT`/`APP_REPO_PATH` указывают на клон проекта — там и код, и `sdlc/`.

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

---

## 8. Тулчейн сборки APK на сервере (Flutter + Android)

Нужен только для реальной сборки (`build_and_deliver_apk`). По факту стенда
(Ubuntu 22.04, ~4 ГБ RAM). Проект пинит версию Flutter в `.fvmrc` → ставим через
`fvm`; для `flutter build apk` нужны JDK, Android SDK (platform/build-tools/NDK по
версиям из `android/app/build.gradle`).

```bash
# JDK + утилиты
apt-get install -y openjdk-17-jdk unzip xz-utils git curl

# fvm + пиновая версия Flutter (в каталоге проекта)
curl -fsSL https://fvm.app/install.sh | bash
ln -sf ~/fvm/bin/fvm /usr/local/bin/fvm        # чтобы сервис видел fvm на PATH
cd /root/<project> && fvm install              # ставит версию из .fvmrc

# Android SDK
export ANDROID_SDK_ROOT=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
curl -fsSL -o /tmp/ct.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q /tmp/ct.zip -d "$ANDROID_SDK_ROOT/cmdline-tools"
mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
SDK="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
yes | "$SDK" --sdk_root="$ANDROID_SDK_ROOT" --licenses
# версии — из android/app/build.gradle (compileSdk / buildToolsVersion / ndkVersion)
"$SDK" --sdk_root="$ANDROID_SDK_ROOT" "platform-tools" "platforms;android-36" \
       "build-tools;35.0.0" "ndk;27.0.12077973"

# связать Flutter с SDK/JDK + принять android-лицензии (в каталоге проекта)
cd /root/<project>
fvm flutter config --android-sdk "$ANDROID_SDK_ROOT" --jdk-dir "$JAVA_HOME"
yes | fvm flutter doctor --android-licenses
```

- **Память.** На ~4 ГБ Gradle легко ловит OOM — добавь swap и ограничь heap
  (не трогая репозиторий, в `~/.gradle/gradle.properties`):
  ```bash
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  printf 'org.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=512m\norg.gradle.daemon=false\n' \
    > /root/.gradle/gradle.properties
  ```
- **Codegen.** Если проект на freezed/drift/json и генерёжка **не** в репо —
  сначала `fvm dart run build_runner build --delete-conflicting-outputs`.
- **debug vs release.** `mode="debug"` не требует keystore (см. §4.3). Пустые
  каталоги ассетов (`assets/.../`) git не хранит — при предупреждении «unable to
  find directory entry» создай их (`mkdir -p`), это не фатально.
- **Telegram из РФ.** `api.telegram.org` с РФ-сервера недоступен, поэтому доставка
  APK — через GitHub Release (§4.2), не Telegram.
