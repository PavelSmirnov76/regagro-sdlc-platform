- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)

# UC-4 — Гость входит с неверными учётными данными: сервер отклоняет грант (REJECTED)

## Назначение

Гость вводит непустые логин и пароль и подтверждает вход; запрос доходит до
сервера, но OAuth password grant отклоняется как неверные учётные данные.
Сессия не создаётся, гость возвращается на экран входа с сообщением об
ошибке.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — гость.

## CURRENT

### Основной поток

1. Гость вводит логин и пароль (оба непустые) на экране входа и подтверждает
   вход — `AuthBloc` получает `AuthEventAuth`.
2. `AuthBloc.on<AuthEventAuth>` проверяет, что оба поля не пустые (иначе см.
   «Альтернативные потоки»), и вызывает `AuthBloc._auth`, который эмитит
   `AuthInProgress`, затем вызывает `AuthRepository.login(login: ..., password: ...)`.
3. `AuthRepository.login` проверяет наличие сети (есть — иначе см.
   «Альтернативные потоки») и выполняет OAuth password grant, получая
   `TokenDataDTO` от сервера.
4. Сервер отвечает, но грант невалиден: `TokenDataDTO.isSuccess == false`
   (`accessToken == null`) — сервер осознанно отклонил запрос по неверным
   логину/паролю.
5. `AuthRepository.login` бросает строковое исключение
   `'invalid_login_password'`; токен и пользователь никуда не сохраняются,
   кэшированный флаг авторизации не выставляется, `_getUserFromApi` не
   вызывается.
6. Исключение всплывает из `_auth` в `catch`-блок `on<AuthEventAuth>`:
   ошибка логируется через `Talker.error`, эмитится
   `AuthMessage('invalid_login_password')`, вызывается
   `_authRepository.logout()` **без `await`** как защитная очистка сессии (в
   этом сценарии `login()` ничего не успел сохранить, так что для основного
   потока это фактически no-op), затем выполняется `await _emitInitial(emit)`,
   который эмитит `AuthInitial` с ранее введёнными `login`/`password` — гость
   остаётся на экране входа с уже заполненными полями и видит сообщение об
   ошибке.

### Альтернативные потоки

- **Пустой логин или пароль.** Клиентская проверка бросает `'enter_login_pass'`
  до какого-либо сетевого вызова — сервер не участвует. Тот же catch-блок,
  тот же паттерн состояний (`AuthMessage` → `logout()` → `AuthInitial`), но
  это не REJECTED — отдельный сценарий, не покрываемый этим use-case.
- **Отсутствие сети или другая техническая ошибка при вызове `login()`.**
  Тоже попадает в тот же catch-блок с тем же паттерном состояний, но это
  ERROR (запрос не дошёл до сервера / технический сбой), а не REJECTED —
  отдельный use-case.
- **Известный риск в отработке этого же REJECTED-сценария (не альтернативный
  успешный путь, а дефект).** `_authRepository.logout()` в catch-блоке
  вызывается без `await`. Если `logout()` сам бросает исключение
  **синхронно** (до первой внутренней точки `await`), это исключение
  прерывает выполнение catch-блока раньше `await _emitInitial(emit)`:
  `AuthMessage('invalid_login_password')` уже успевает эмититься, но
  `AuthInitial` следом не наступает — bloc зависает на `AuthMessage` вместо
  возврата к экрану входа. Воспроизведено отдельным тестом (см. «Связанные
  тесты»).

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session/TokenData) — грант не выдаётся, главный токен не
  записывается; `TokenDataDTO.isSuccess` — условие, отличающее этот сценарий
  от `_OK`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — профиль не запрашивается и не сохраняется: `login()`
  бросает раньше вызова `_getUserFromApi`.

### Бизнес-правила

- Неверные учётные данные, дошедшие до сервера и отклонённые им, —
  `REJECTED`, а не `ERROR`: сервер ответил, просто не выдал токен.
- Защитный вызов `logout()` в catch-блоке `on<AuthEventAuth>` выполняется
  безусловно при любом исключении внутри `_auth`, независимо от того, успело
  ли что-то реально сохраниться к этому моменту.
- Сообщение об ошибке — сырой строковый идентификатор исключения
  (`'invalid_login_password'`), передаваемый как есть в `AuthMessage.message`;
  перевод в пользовательский текст — на UI-уровне, вне рамок этого
  use-case.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью прослеживается в существующем коде.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuth>` | CURRENT | обрабатывает событие входа; catch-блок логирует, эмитит `AuthMessage`, вызывает `logout()` без `await`, возвращает `AuthInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._auth` | CURRENT | эмитит `AuthInProgress`, вызывает `AuthRepository.login` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthMessage` | CURRENT | состояние с сообщением об отклонённом входе |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthInitial` | CURRENT | состояние возврата на экран входа с сохранёнными логином/паролем |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.login` | CURRENT | выполняет OAuth password grant, бросает `'invalid_login_password'` при `TokenDataDTO.isSuccess == false` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | защитная очистка сессии в catch-блоке (вызывается без `await`) — источник «известного риска» |
| `packages/sheep_farm_database/lib/entities/token_data/token_data.dart` | `TokenDataDTO.isSuccess` | CURRENT | условие, различающее REJECTED и OK-ветку `login()` |

## Критерии приёмки

- При непустых логине и пароле и невалидном гранте (`TokenDataDTO.isSuccess == false`)
  `AuthBloc` эмитит последовательность `AuthInProgress` → `AuthMessage('invalid_login_password')` → `AuthInitial`.
- Главный токен и пользователь не сохраняются в `AUTH_BOX`; кэшированный флаг
  авторизации не выставляется в `true`.
- `AuthRepository.logout()` вызывается ровно один раз как часть защитной
  очистки в catch-блоке.
- Если `logout()` в catch-блоке бросает исключение синхронно, `AuthInitial`
  не наступает — bloc остаётся на `AuthMessage` (задокументированный, не
  исправляемый в рамках этого прохода риск).

## Связанные тесты

- `test/blocs/auth_bloc_test.dart`, group `'UC-3/UC-4/UC-5 — AuthEventAuth'` — конкретно кейс «логин/пароль
  заданы, login() бросает исключение -> сообщение, logout, AuthInitial».
- `test/blocs/auth_bloc_test.dart`, group
  `'UC-4/UC-5 — AuthEventAuth catch-блок с падающим logout() (известный риск)'` — доп. риск в этой же ветке:
  `logout()` бросает синхронно, `AuthInitial` не наступает.

## Открытые вопросы и ограничения

- Известный риск (не открытый вопрос, а задокументированный дефект): защитный
  `logout()` в catch-блоке `on<AuthEventAuth>` вызывается без `await` — при
  синхронном исключении внутри него bloc зависает на `AuthMessage`, не
  возвращаясь в `AuthInitial`. См. «Альтернативные потоки» и группу тестов
  `'UC-4/UC-5 — AuthEventAuth catch-блок с падающим logout() (известный риск)'`
  в `test/blocs/auth_bloc_test.dart`.
- Сообщение об ошибке — непереведённый строковый идентификатор исключения;
  локализация сообщения происходит выше по стеку (вне `AuthBloc`/`AuthRepository`),
  не проверялась в рамках этого use-case.
