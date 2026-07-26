- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)

# UC-5 — Гость входит, но запрос технически не доходит до осмысленного ответа сервера (ERROR)

## Назначение

Гость вводит непустые логин и пароль и подтверждает вход, но попытка не
доходит до содержательного ответа сервера по технической причине — либо сеть
недоступна и запрос вообще не отправляется (преflight-проверка), либо
происходит любое другое исключение при получении токена/профиля. Сессия не
создаётся, гость возвращается на экран входа с сообщением об ошибке.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — гость.

## CURRENT

### Основной поток

1. Гость вводит логин и пароль (оба непустые) на экране входа и подтверждает
   вход — `AuthBloc` получает `AuthEventAuth`.
2. `AuthBloc.on<AuthEventAuth>` проверяет, что оба поля не пустые (иначе см.
   «Альтернативные потоки»), и вызывает `AuthBloc._auth`, который эмитит
   `AuthInProgress`, затем вызывает `AuthRepository.login(login: ..., password: ...)`.
3. `AuthRepository.login` первым делом проверяет
   `NetworkConnectivityService.hasConnection()` — **до** какого-либо сетевого
   вызова. Соединения нет — метод сразу бросает строковое исключение
   `'Internet connection required'`; ни OAuth-запрос токена
   (`_getTokenDataFromApi`), ни запрос профиля (`_getUserFromApi`) не
   выполняются вовсе.
4. Исключение всплывает из `_auth` в `catch`-блок `on<AuthEventAuth>`: ошибка
   логируется через `Talker.error`, эмитится
   `AuthMessage('Internet connection required')`, вызывается
   `_authRepository.logout()` **без `await`** как защитная очистка сессии (в
   этом сценарии `login()` ничего не успел сохранить, так что для основного
   потока это фактически no-op — токен и пользователь никогда не
   записывались), затем выполняется `await _emitInitial(emit)`, который
   эмитит `AuthInitial` с ранее введёнными `login`/`password` — гость
   остаётся на экране входа с уже заполненными полями и видит сообщение об
   ошибке.
5. UI: `ProfilePage`'s `BlocListener<AuthBloc, AuthState>` реагирует на
   `AuthMessage`, показывая `SnackBar` с `l10n.tr(state.message)`. Для этой
   ветки `state.message == 'Internet connection required'` — см. «Открытые
   вопросы и ограничения» по поводу того, как это значение проходит через
   `tr()`.

### Альтернативные потоки

- **Сеть заявлена доступной, но происходит любое другое исключение при
  получении токена/профиля.** Если преflight-проверка прошла, но
  `_getTokenDataFromApi` (OAuth-запрос, `dioClient.post`) или
  `_getUserFromApi` (запрос профиля тем же токеном, `dioClient.get`)
  бросают исключение (обрыв соединения в процессе, таймаут, неожиданный
  ответ сервера и т. п.) — это исключение ничем не отличается от
  предыдущего по обработке `try/catch` в `login()`: обеих оборачивающих
  `try/catch` в `AuthRepository.login` нет, исключение просто всплывает
  наружу тем же путём в тот же `catch`-блок `on<AuthEventAuth>`
  (`AuthMessage` → `logout()` без `await` → `AuthInitial`). Это тоже
  `ERROR` (запрос не дошёл до содержательного ответа сервера), а не
  `REJECTED` — сервер не успел осознанно отклонить попытку. Токен и
  пользователь не сохраняются: `_saveMainAuthData` достигается только после
  того, как и грант токена, и запрос профиля уже завершились успехом.
- **Пустой логин или пароль.** Клиентская проверка бросает
  `'enter_login_pass'` до какого-либо сетевого вызова — сервер не
  участвует. Тот же `catch`-блок, тот же паттерн состояний (`AuthMessage` →
  `logout()` → `AuthInitial`), но это не техническая ошибка сети/сервера —
  отдельный сценарий, не покрываемый этим use-case.
- **Сервер отвечает, но осознанно отклоняет грант** (`TokenDataDTO.isSuccess
  == false`, неверный логин/пароль) — это `REJECTED`, не `ERROR`: запрос
  дошёл, сервер содержательно ответил отказом. См. [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md).
- **Известный риск в отработке того же catch-блока (общий для всех веток
  этого события, не специфичный для ERROR).** `_authRepository.logout()`
  вызывается без `await`. Если `logout()` сам бросает исключение
  **синхронно** (до первой внутренней точки `await`), это исключение
  прерывает выполнение catch-блока раньше `await _emitInitial(emit)`:
  `AuthMessage(...)` уже успевает эмититься, но `AuthInitial` следом не
  наступает — bloc зависает вместо возврата к экрану входа. Тот же дефект
  для этого же catch-блока, воспроизведённый на другом триггере (отклонённый
  грант), задокументирован в [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md) и покрыт там отдельным тестом; для
  триггера «нет сети» отдельного теста этого риска нет.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session/TokenData) — главный токен так и не выдаётся и не
  записывается; преflight-проверка сети либо любое другое техническое
  исключение обрывают попытку до того, как `_saveMainAuthData` вообще может
  быть вызван.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — профиль не запрашивается (преflight-ветка) либо запрос
  профиля сам оказывается источником исключения (альтернативная ветка);
  сохранение пользователя не происходит ни в одном случае.

### Бизнес-правила

- Преflight-проверка сети (`NetworkConnectivityService.hasConnection()`)
  гейтит весь `login()` целиком: без соединения ни OAuth-запрос, ни запрос
  профиля не выполняются — исключение бросается раньше первого сетевого
  вызова.
- Любое исключение, не являющееся осознанным серверным отказом
  (`TokenDataDTO.isSuccess == false` → `'invalid_login_password'`), считается
  технической ошибкой (`ERROR`) — граница между `ERROR` и `REJECTED`
  проведена исключительно внутри `AuthRepository.login`, а не в `AuthBloc`:
  bloc обрабатывает оба случая одним и тем же catch-блоком, не различая их.
- Защитный вызов `logout()` в catch-блоке `on<AuthEventAuth>` выполняется
  безусловно при любом исключении внутри `_auth`, независимо от того, что
  именно его вызвало и успело ли что-то реально сохраниться к этому моменту.
- Сообщение об ошибке — сырой строковый идентификатор исключения
  (`'Internet connection required'` для преflight-ветки, текст исключения
  `dio`/иного технического сбоя для альтернативной ветки), передаваемый как
  есть в `AuthMessage.message`; перевод в пользовательский текст — на
  UI-уровне, вне рамок этого use-case.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — основная ветка (преflight-проверка сети) полностью
прослеживается в существующем коде и покрыта тестом. Альтернативная ветка
(исключение при запросе токена/профиля, отличное от преflight-проверки)
прослеживается в коде так же однозначно, но не имеет отдельного теста — см.
«Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/login/login_view.dart` | `LoginView` | CURRENT | экран входа — источник `AuthEventSetLogin`/`AuthEventSetPassword`/`AuthEventAuth` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuth>` | CURRENT | обрабатывает событие входа; catch-блок логирует, эмитит `AuthMessage`, вызывает `logout()` без `await`, возвращает `AuthInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._auth` | CURRENT | эмитит `AuthInProgress`, вызывает `AuthRepository.login` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthMessage` | CURRENT | состояние с сообщением о технической ошибке входа |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthInitial` | CURRENT | состояние возврата на экран входа с сохранёнными логином/паролем |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.login` | CURRENT | преflight-проверка сети, бросает `'Internet connection required'` при её отсутствии; без try/catch вокруг сетевых вызовов |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getTokenDataFromApi` | CURRENT | OAuth-запрос токена — источник исключения в альтернативной ветке |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getUserFromApi` | CURRENT | запрос профиля тем же токеном — источник исключения в альтернативной ветке |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | защитная очистка сессии в catch-блоке (вызывается без `await`) |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | преflight-проверка соединения перед `login()` |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | показывает `SnackBar` с `l10n.tr(state.message)` при `AuthMessage` |
| `lib/l10n/app_localization.dart` | `AppLocalization.tr` | CURRENT | резолвит ключ перевода; для нераспознанного ключа возвращает сам ключ (`default: return key;`) |

## Критерии приёмки

- При непустых логине и пароле и недоступной сети `AuthBloc` эмитит
  последовательность `AuthInProgress` → `AuthMessage('Internet connection
  required')` → `AuthInitial`, не выполняя ни одного сетевого вызова
  (`dioClient.post`/`dioClient.get` не вызываются).
- Главный токен и пользователь не сохраняются в `AUTH_BOX`; кэшированный флаг
  авторизации не выставляется в `true`.
- Любое другое исключение при получении токена/профиля (сеть заявлена
  доступной) приводит к тому же паттерну состояний, что и отсутствие сети —
  `AuthInProgress` → `AuthMessage(<сообщение исключения>)` → `AuthInitial`.
- `AuthRepository.logout()` вызывается ровно один раз как часть защитной
  очистки в catch-блоке.

## Связанные тесты

- `test/repositories/auth_repository_test.dart`, group `'UC-5 — login без сети'` — тест `'login:
  нет сети -> throws до сетевого вызова'`: проверяет ровно преflight-ветку
  этого use-case (`NetworkConnectivityService.hasConnection() == false` →
  `throws 'Internet connection required'`, `dioClient.post` ни разу не
  вызывается).
- `test/blocs/auth_bloc_test.dart`, group `'UC-3/UC-4/UC-5 — AuthEventAuth'`
  (общая группа с [UC-3](UC-3-ACTOR-2-EVT-2-ENT-2-CREATE_OK-IN-AUTH.md)/[UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md) — один и тот же тест-кейс покрывает несколько
  UC) — конкретно кейс
  «логин/пароль заданы, login() бросает исключение -> сообщение, logout,
  AuthInitial»: на уровне bloc'а `AuthRepository` замокан целиком, поэтому
  тест использует строку `'invalid_login_password'` как payload исключения
  (сам по себе это триггер `REJECTED`, см. [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md)) — но проверяемый механизм
  (`AuthInProgress` → `AuthMessage(<то, что бросил login()>)` → `AuthInitial`,
  безусловный вызов `logout()`) идентичен для любого исключения, включая
  `'Internet connection required'`: `AuthBloc` не различает `ERROR` и
  `REJECTED` в собственном catch-блоке. Это и есть общий тест, привязка к
  которому объясняется в `AGENTS.md` («несколько новых UC мапятся в одну
  тестовую группу»).
- Альтернативная ветка (исключение при `_getTokenDataFromApi`/
  `_getUserFromApi` уже после успешной преflight-проверки) — TBD, теста нет
  ни на уровне репозитория, ни на уровне bloc'а.

## Открытые вопросы и ограничения

- **Найденный дефект (не открытый вопрос): сообщение `'Internet connection
  required'` никогда не переводится на нерусские/неанглийские локали.**
  `AuthMessage.message` для этой ветки — буквальная строка `'Internet
  connection required'` (с заглавной буквы и пробелами), а ключ перевода в
  `.arb`-файлах — `internet_connection_required` (нижний регистр,
  подчёркивания). `AppLocalization.tr` ищет точное совпадение по `switch` и
  не находит его для этой строки, поэтому попадает в `default: return key;`
  — гость на любой локали видит нередактированный английский текст `Internet
  connection required` в `SnackBar`, а не переведённое сообщение (для
  `'invalid_login_password'` в соседнем `REJECTED`-сценарии такого
  расхождения нет — там ключ совпадает буквально). Не исправлялось в рамках
  этого прохода документирования.
- Известный риск, общий с [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md): защитный `logout()` в catch-блоке
  `on<AuthEventAuth>` вызывается без `await` — при синхронном исключении
  внутри него bloc зависает на `AuthMessage`, не возвращаясь в
  `AuthInitial`. Воспроизведён и покрыт тестом только на триггере
  «отклонённый грант» ([UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md)); на триггере «нет сети» отдельного теста нет,
  но по коду риск идентичен — `logout()` вызывается одинаково независимо от
  того, что было брошено в `_auth`.
- Различие `ERROR`/`REJECTED` проведено по конкретным строковым литералам,
  которые решает бросить `AuthRepository.login` — не по типу исключения. Если
  в будущем сетевой слой (`dio`) начнёт бросать типизированные исключения
  вместо просто пропускания их наружу, эта граница не изменится сама по
  себе, пока `login()` не станет их явно перехватывать/различать.
