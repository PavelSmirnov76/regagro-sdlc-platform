# UC-14 — Автоматическая выдача гостевого доступа при первом холодном старте (успех)

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md) |
| Сущность | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |

## Назначение

При самом первом холодном старте приложения — когда ещё ни разу не было ни сохранённой авторизованной сессии, ни (важно именно для этого сценария) хотя бы одного выданного ранее гостевого доступа — приложение автоматически, без единого действия пользователя и без отдельного экрана выбора «войти или продолжить как гость», создаёт неавторизованную гостевую сессию с нуля: явно фиксирует состояние «не авторизован» и обнуляет список серверных интеграций. Тот же путь срабатывает и при полном отсутствии сети на старте.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — само приложение, действующее автоматически при холодном старте, до какого-либо ввода пользователя; человек здесь не инициатор. Предусловия на момент срабатывания: `AuthRepository.isAuthorized()` уже вернул `false` на этом старте (нет сохранённого главного токена) и `AppCacheService.hasIntegrationDirection()` возвращает `false` — гостевой доступ не выдавался ни разу за всё время, не только «в эту сессию».

## CURRENT

### Основной поток

1. Приложение запускается с нуля, сохранённой сессии авторизации нет. `MyApp.build` (`lib/main.dart`) создаёт `AuthBloc` и сразу отправляет ему `AuthEventStart()`.
2. `AuthBloc.on<AuthEventStart>` эмитит `AuthSplashScreen(appVersion)`, проверяет сеть через `NetworkConnectivityService.hasConnection()` и вызывает `AuthRepository.init(fromApi: isNetworkConnected)`.
3. `AuthRepository.init`: если сеть есть, пытается обновить профиль пользователя (`updateUserData`) — но главного токена ещё нет (`getMainTokenData() == null`), поэтому `updateUserData` не делает сетевого запроса и ничего не пишет. Затем `init` выставляет кэшированный флаг `AppCacheService.setAuthorizedFlag(isAuthorized())` (в `false`) и публикует `false` в поток авторизации (`getAuthStream()`).
4. Обработчик события читает `AuthRepository.getLogin()` (пустая строка — логин ранее не запоминался) и проверяет `AuthRepository.isAuthorized()` → `false`.
5. Так как не авторизован, проверяется `AppCacheService.hasIntegrationDirection()`. В этом сценарии — `false`. Обработчик вызывает `AppCacheService.saveIntegrationDirection()` (фиксирует признак «направление уже сохранялось» — фиксированным значением, см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)), а затем `AuthRepository.loginWithoutAuthorization()`.
6. `AuthRepository.loginWithoutAuthorization()`: очищает дату последней синхронизации справочников (`AppCacheService.clearDirectoriesLastSyncDate()`), явно выставляет `AppCacheService.setAuthorizedFlag(false)` и записывает пустой список `serverIntegrations` (`<Map<String,String>>[]`) в `AUTH_BOX`. Главный токен (`mainToken`) не пишется вообще — гостевая сессия остаётся без какого-либо токена.
7. `AuthBloc` эмитит `AuthToMain(null)` — терминальное состояние успеха с `user == null`, чем оно и отличается от авторизованного захода (`AuthToMain(user)`). Приложение переходит на главный экран как гость; отдельный экран выбора «войти или продолжить как гость» не показывается.

### Альтернативные потоки

- **Нет сети на старте.** Тот же путь: `NetworkConnectivityService.hasConnection()` возвращает `false`, `AuthRepository.init(fromApi: false)` пропускает обновление профиля и использует только локальные данные; далее ветвление идентично шагам 4–7 — если `hasIntegrationDirection()` тоже `false`, гостевой доступ выдаётся так же. Обращения к сети внутри `loginWithoutAuthorization()` в принципе нет — весь метод работает только с локальным Hive/`SharedPreferences`.
- **Гостевой доступ уже выдавался раньше** (`AppCacheService.hasIntegrationDirection() == true`). Условный блок целиком пропускается, `loginWithoutAuthorization()` не вызывается повторно, сразу эмитится `AuthToMain(null)` с уже существующим (сохранённым с прошлого запуска) состоянием сессии. Это не создание с нуля — отдельный сценарий, не входит в объём этого use-case.
- **Исключение во время `init`/чтения Hive.** Перехватывается общим `catch` обработчика: `AuthMessage`, `AuthRepository.logout()`, `_emitInitial`. Отдельный сценарий (`ERROR`), не входит в объём этого use-case.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session) — главная сущность перехода: гостевая сессия создаётся здесь с нуля — обнулённые серверные интеграции и явный флаг «не авторизован» в `AUTH_BOX`/`SharedPreferences`. Главный токен не создаётся и не изменяется — сессия остаётся неавторизованной.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — не затрагивается в этом сценарии: главного токена нет, поэтому `updateUserData()` не делает запроса и не сохраняет пользователя; `AuthRepository.getUser()` в этой ветке даже не вызывается (используется только `AuthToMain(null)`).

### Бизнес-правила

- Гостевой доступ автоматически выдаётся ровно один раз «за всё время» — до первого случая, когда `AppCacheService.hasIntegrationDirection()` станет `true`; последующие холодные старты без сессии больше не проходят через `loginWithoutAuthorization()`.
- Гостевой доступ не пишет ни одного токена (см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), «Инварианты») — только пустые серверные интеграции и явный флаг «не авторизован»; этим он и отличается от последующего реального входа.
- Отдельного UI-экрана «выбор входа/гостя» на этом первом старте не показывается — решение принимается приложением автоматически, до какого-либо ввода пользователя.
- Поведение идентично при наличии и при отсутствии сети на старте — разница только в том, пытается ли `init` обновить профиль пользователя (для гостя это не имеет эффекта, так как профиля ещё нет).
- Как и все сценарии [MOD-1](../modules/MOD-1-AUTH.md), `loginWithoutAuthorization()` — целиком локальная операция без сетевого вызова.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью реализован, TARGET не добавляет нового объёма работы.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/main.dart` | `MyApp.build` | CURRENT | создаёт `AuthBloc` и сразу отправляет `AuthEventStart()` при старте приложения |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | CURRENT | проверка сессии при старте; при отсутствии авторизации и признака «уже был гостем» — автовыдача гостевого доступа |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthToMain` | CURRENT | терминальное состояние успеха; `user == null` = гостевой заход |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSplashScreen` | CURRENT | промежуточное состояние на время проверки сессии |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.init` | CURRENT | обновление профиля при наличии сети (в этой ветке — без эффекта, токена нет), выставление кэшированного флага авторизации |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | проверка главного токена — `false` в этом сценарии |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.loginWithoutAuthorization` | CURRENT | создание с нуля неавторизованной гостевой сессии: очистка даты синка справочников, флаг «не авторизован», пустой список серверных интеграций |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.hasIntegrationDirection` | CURRENT | проверка «гостевой доступ уже выдавался хотя бы раз» |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.saveIntegrationDirection` | CURRENT | фиксирует, что признак выдан (пишет одно и то же значение — см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)) |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.setAuthorizedFlag` | CURRENT | явно выставляет кэшированный флаг «не авторизован» |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearDirectoriesLastSyncDate` | CURRENT | сбрасывает дату последней синхронизации справочников как часть выдачи гостевого доступа |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | проверка сети перед `AuthRepository.init` |

## Критерии приёмки

- При холодном старте без сохранённой сессии и без ранее выданного гостевого доступа (`hasIntegrationDirection() == false`) `AuthBloc` вызывает `AuthRepository.loginWithoutAuthorization()` ровно один раз и эмитит `AuthToMain(null)`.
- После этого `AuthRepository.isAuthorized()` остаётся `false` — главный токен не появляется.
- После этого `AUTH_BOX.serverIntegrations` — пустой список, `AppCacheService.isAuthorized()` — `false`, `AppCacheService.hasIntegrationDirection()` — `true`.
- Сценарий проходит одинаково независимо от наличия сети на старте (различается только вызов `updateUserData` внутри `init`, который в этой ветке не имеет эффекта).
- Пользователю не показывается отдельный экран выбора «войти/продолжить как гость» — переход на главный экран происходит напрямую из `AuthToMain(null)`.

## Связанные тесты

- `test/blocs/auth_bloc_test.dart`, group `'UC-13/UC-14/UC-15 — AuthEventStart'`, тест `'не авторизован -> сохраняет integration direction, логинится без авторизации, AuthToMain(null)'`.
- `test/blocs/auth_bloc_test.dart`, group `'UC-13/UC-14/UC-15 — AuthEventStart'`, тест `'нет соединения -> init(fromApi:false), логинится без авторизации, AuthToMain(null)'` — покрывает альтернативный поток «нет сети на старте».
- `test/repositories/auth_repository_test.dart`, group `'UC-14 — loginWithoutAuthorization'`, тест `'пустой список интеграций'` — проверяет только запись `AUTH_BOX.serverIntegrations`, не проверяет побочные эффекты `AppCacheService`.

## Открытые вопросы и ограничения

- `AppCacheService.saveIntegrationDirection()`/`hasIntegrationDirection()` — судя по [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) («Инварианты»), похожи на неиспользуемый остаток более ранней архитектуры: сохраняемое значение фиксировано и нигде за пределами этой же проверки не влияет на другое ветвление кода. Сама проверка «выдавался ли гостевой доступ хотя бы раз» при этом реальна и управляет тем, вызывается ли `loginWithoutAuthorization()`, — вопрос только к содержимому сохраняемого значения, не к самому факту ветвления.
- Тест `'пустой список интеграций'` в `auth_repository_test.dart` не проверяет побочные эффекты `clearDirectoriesLastSyncDate()`/`setAuthorizedFlag(false)`, а тесты в `auth_bloc_test.dart` не проверяют итоговое состояние `AUTH_BOX`/`SharedPreferences` напрямую (только `verify` вызовов моков) — сквозного теста, проверяющего все три эффекта `loginWithoutAuthorization()` за один прогон, нет.
