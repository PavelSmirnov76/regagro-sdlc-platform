- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)

# UC-3 — Гость успешно входит в систему по логину и паролю

## Назначение

Гость вводит непустые логин и пароль и подтверждает вход; сервер выдаёт OAuth
password grant и профиль пользователя. Клиент сохраняет главный токен и
пользователя как новую сессию — гость становится авторизованным пользователем.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — до входа. По завершении сценария тот же человек
удовлетворяет условию `AuthRepository.isAuthorized() == true` и становится
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — это переход роли одного и того же актора, не смена
устройства/аккаунта.

## CURRENT

### Основной поток

1. Гость на экране входа (`LoginView`) вводит логин и пароль; каждое изменение
   поля диспатчит `AuthEventSetLogin`/`AuthEventSetPassword` в `AuthBloc`,
   обновляя приватные `_login`/`_password`. Подтверждение входа диспатчит
   `AuthEventAuth`.
2. `AuthBloc.on<AuthEventAuth>` проверяет, что оба поля не пустые (иначе см.
   «Альтернативные потоки» — это не часть данного сценария), и вызывает
   `AuthBloc._auth`, который эмитит `AuthInProgress`, затем вызывает
   `AuthRepository.login(login: ..., password: ...)`.
3. `AuthRepository.login` проверяет `NetworkConnectivityService.hasConnection()`
   (сеть есть — иначе см. «Альтернативные потоки») и вызывает
   `_getTokenDataFromApi`: `POST {Constants.authSerivceApi}/oauth/token` с
   телом `grant_type: 'password'`, фиксированными `client_id`/`client_secret`
   приложения (`Constants.clientIdApi`/`Constants.clientSecretApi`),
   `username`/`password` из формы и `scope: '*'`.
4. Сразу после получения HTTP-ответа, ещё до разбора его в `TokenDataDTO`,
   `_getTokenDataFromApi` безусловно вызывает
   `AppCacheService.clearDirectoriesLastSyncDate()` — это происходит на любой
   попытке входа, не только на успешной (см. «Бизнес-правила»).
5. `TokenDataDTO.isSuccess` (`accessToken != null`) — сервер выдал грант.
   `login()` конвертирует его в `TokenData` через `toTokenData()`.
6. `login()` вызывает `_getUserFromApi(tokenData.bearerToken)`: `GET
   {Constants.authServiceGetUserUrl}/user` с заголовком `Authorization:
   <bearerToken>`; ответ нормализуется (`_normalizeUserPhoneFields`) и
   парсится в `UserDTO`.
7. `login()` вызывает `_saveMainAuthData(tokenData: tokenDataDto, user:
   userDTO)`: в `AUTH_BOX` пишутся главный токен (`toTokenDataHive()`) и
   пользователь (`toUserHive()`); поскольку `user != null` и
   `updateServerIntegrations` по умолчанию `true`, туда же безусловно пишется
   пустой список `serverIntegrations` и вызывается
   `AppCacheService.saveIntegrationDirection()`.
8. `login()` вызывает `_saveLogin(login)` — логин сохраняется в `LOGIN_BOX`
   (переживает будущий `logout()`).
9. `login()` вызывает `AppCacheService.setAuthorizedFlag(true)` — кэшированный
   дубликат флага авторизации выставляется в `true`.
10. `login()` вызывает `isAuthorized()` (теперь `true` — главный токен в
    `AUTH_BOX` записан) и пушит `true` в `_authStreamController` (стрим,
    слушаемый самим `AuthBloc`, реагирует только на `false`, поэтому здесь
    подписка ничего дополнительно не делает); возвращает `accessToken` —
    возвращаемое значение вызывающим кодом (`_auth`) не используется.
11. `AuthBloc._auth` читает `_authRepository.getUser()!` (только что
    сохранённого пользователя из Hive) и эмитит `AuthToMain(user)` —
    финальное состояние этого сценария.
12. (За пределами [MOD-1](../modules/MOD-1-AUTH.md), только для полноты картины.) UI-код вне AUTH
    (`MainPage`, `BlocListener<AuthBloc, AuthState>`) реагирует на `AuthToMain`
    запуском `DataUpdateStartAll` — явный sync-проход. Это принадлежит
    границе другого модуля (см. [MOD-1](../modules/MOD-1-AUTH.md), «AUTH ничего не ставит в очередь
    синхронизации»), не самому этому use-case.

### Альтернативные потоки

- **Пустой логин или пароль.** Клиентский guard бросает `'enter_login_pass'`
  до какого-либо сетевого вызова — сервер не участвует. Не часть основного
  успешного потока и не отдельный CRUD-результат этого события в смысле
  данного файла.
- **Отсутствие сети.** `NetworkConnectivityService.hasConnection() == false`
  → `login()` бросает `'Internet connection required'` до какого-либо
  сетевого вызова — ERROR-ветка, отдельный сценарий.
- **Сервер отклоняет грант (неверные логин/пароль).**
  `TokenDataDTO.isSuccess == false` → `login()` бросает
  `'invalid_login_password'`, токен и пользователь не сохраняются — это
  REJECTED-ветка той же попытки, описанная отдельно в [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md).
- **Успешный грант, но запрос профиля (`_getUserFromApi`) бросает
  исключение.** Токен уже получен, но `_saveMainAuthData` для сессии в этом
  случае не вызывается вовсе (исключение всплывает раньше); попадает в тот
  же catch-блок `on<AuthEventAuth>`, что и REJECTED/ERROR-ветки — технический
  сбой на втором шаге, отдельный сценарий, не описываемый этим файлом.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность события [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md) по определению и
  основной объект мутации: главный токен, пустой `serverIntegrations` и
  `lastLogin` записываются в `AUTH_BOX`/`LOGIN_BOX`; кэшированный флаг
  авторизации в `AppCacheService` синхронно выставляется в `true`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — профиль запрашивается заново с сервера
  (`_getUserFromApi`) и сохраняется вместе с сессией в том же боксе.

### Бизнес-правила

- Сеть проверяется до любого сетевого вызова — `login()` не пытается
  выполнить OAuth-запрос без подтверждённого соединения.
- OAuth password grant использует фиксированные учётные данные приложения
  (`Constants.clientIdApi`/`Constants.clientSecretApi`) и `scope: '*'` —
  значения не вводятся пользователем и не зависят от фермы/организации.
- Успех определяется двумя последовательными сетевыми вызовами: получить
  токен И получить профиль — сохранённая сессия всегда несёт свежий `User`
  с сервера, а не только токен.
- `AppCacheService.clearDirectoriesLastSyncDate()` вызывается безусловно
  сразу после ответа на `oauth/token`, ещё до проверки `isSuccess` — это
  происходит одинаково и на этом OK-сценарии, и на REJECTED-сценарии
  ([UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md)): любая попытка входа форсирует пересинхронизацию справочников, не
  только успешная.
- `serverIntegrations` при сохранении пользователя безусловно перезаписывается
  пустым списком — ничто в клиентском коде не заполняет его реальными
  данными (см. инвариант [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)).
- Два независимых признака «авторизован» — живой (`isAuthorized()` по
  `AUTH_BOX`) и кэшированный (`AppCacheService`) — на этом успешном пути
  выставляются в `true` синхронно друг с другом, но ничто в коде не
  гарантирует, что они не разойдутся позже (документированный инвариант
  [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), не предмет исправления в этом use-case).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью прослеживается в существующем коде и
покрыт тестом (см. «Связанные тесты»), хоть и только на уровне bloc'а (см.
«Открытые вопросы и ограничения»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/login/login_view.dart` | `LoginView` | CURRENT | экран входа: поля логина/пароля диспатчат `AuthEventSetLogin`/`AuthEventSetPassword`, кнопка подтверждения — `AuthEventAuth` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuth>` | CURRENT | обработчик события входа, guard на пустые поля, вызывает `_auth` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._auth` | CURRENT | эмитит `AuthInProgress`, вызывает `AuthRepository.login`, читает `getUser()`, эмитит `AuthToMain` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthToMain` | CURRENT | финальное состояние успешного входа, несёт `User` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.login` | CURRENT | оркестрирует: проверка сети, OAuth grant, запрос профиля, сохранение сессии, кэшированный флаг |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getTokenDataFromApi` | CURRENT | `POST {authSerivceApi}/oauth/token` password grant; безусловный `clearDirectoriesLastSyncDate()` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getUserFromApi` | CURRENT | `GET {authServiceGetUserUrl}/user` с `Authorization: <bearerToken>`, нормализация телефона, парсинг `UserDTO` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._saveMainAuthData` | CURRENT | пишет токен/пользователя/пустой `serverIntegrations` в `AUTH_BOX` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._saveLogin` | CURRENT | сохраняет логин в `LOGIN_BOX` |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | проверка сети перед любым сетевым вызовом `login()` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.setAuthorizedFlag` | CURRENT | кэшированный дубликат флага авторизации, выставляется в `true` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearDirectoriesLastSyncDate` | CURRENT | безусловный сброс даты последней синхронизации справочников сразу после ответа `oauth/token` |
| `packages/sheep_farm_database/lib/entities/token_data/token_data.dart` | `TokenDataDTO.isSuccess` / `TokenDataDTO.toTokenData` | CURRENT | условие успешного гранта и конвертация DTO → доменная модель |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `UserDTO.toUserHive` | CURRENT | конвертация полученного профиля в Hive-форму перед сохранением |
| `lib/constants.dart` | `Constants.clientIdApi`, `Constants.clientSecretApi` | CURRENT | фиксированные `client_id`/`client_secret` приложения, встроенные в тело password grant |

## Критерии приёмки

- При непустых логине/пароле, наличии сети и успешном гранте (`TokenDataDTO.isSuccess
  == true`) `AuthBloc` эмитит последовательность `AuthInProgress` →
  `AuthToMain(user)`.
- После завершения `AuthRepository.isAuthorized() == true`: `AUTH_BOX`
  содержит главный токен (`TokenDataHive`) и пользователя (`UserHive`).
- `LOGIN_BOX` содержит логин, использованный при входе.
- Кэшированный флаг `AppCacheService` выставлен в `true`.
- `AuthRepository.getAuthStream()` эмитит `true`.
- `AuthToMain.user` соответствует пользователю, полученному через
  `_getUserFromApi` (после нормализации телефона), а не устаревшим/пустым
  данным.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-3/UC-4/UC-5 — AuthEventAuth'`, test
`'логин/пароль заданы, login() успешен -> AuthInProgress, затем AuthToMain'`.

## Открытые вопросы и ограничения

- Успешный сценарий покрыт только на уровне `AuthBloc`, с `AuthRepository`
  полностью замоканным (`mocktail`) — сама сетевая часть `login()`
  (`_getTokenDataFromApi`/`_getUserFromApi`: форма тела password grant,
  нормализация телефона, реальный round-trip `TokenDataDTO`/`UserDTO`) не
  имеет отдельного репозиторного теста на успешный случай; на уровне
  репозитория тестами покрыта только ERROR-ветка отсутствия сети (`UC-5 — login без сети`, `test/repositories/auth_repository_test.dart`).
- `clearDirectoriesLastSyncDate()` срабатывает раньше, чем клиент вообще
  узнаёт, был ли грант успешным — не проверялось, является ли это осознанным
  решением или побочным эффектом порядка вызовов внутри
  `_getTokenDataFromApi`.
