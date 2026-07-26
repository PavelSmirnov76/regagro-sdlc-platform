# UC-191 — Выход из аккаунта стирает все `@Clearable`-таблицы разом, включая сам журнал `DataUpdate` — единой Drift-транзакцией, без отдельного подтверждения и без завершающего состояния блока

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же факт, что описан в [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) —
`MainPage.on<AuthLogout>` диспатчит `DataUpdateBloc.add(DataUpdateClear())`,
единственный обработчик которого (`on<DataUpdateClear>`,
`lib/blocs/data_update/data_update_bloc.dart`) вызывает
`_appDatabase.clearUserData()` → `clearAllClearableTables()`
(`packages/sheep_farm_database/lib/database/database.dart`,
сгенерированный код — `packages/sheep_farm_database/lib/database/database.clearable.dart`).
Это единой Drift-транзакцией удаляет **все строки из 15 таблиц**, помеченных
`@Clearable()` — включая саму таблицу `DataUpdates`
([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), сущность этого UC),
которая тем самым лишается даже журнала последнего (успешного или
неуспешного) sync-прохода, не только «сбрасывается на начало прохода», как
происходит на каждом обычном полном sync (`_clearDataUpdates()`, см.
[ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), «Инварианты»).
Успешный путь этой очистки не порождает исключения нигде в двух
задействованных методах и не имеет иной ветки исхода, кроме as-is
завершения — отсюда `DELETE_OK`.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
инициировавший выход из аккаунта ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md),
`AuthBloc.on<AuthEventLogout>`, `event.clearData == true`, кнопка выхода в
профиле). Как отмечено уже в самом [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md),
тот же путь фактически проходится и после автоматической потери сессии
([EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md),
`ACTOR-3`, `event.clearData == false`) — оба варианта `AuthEventLogout`
заканчиваются одним и тем же `emit(const AuthLogout())` в `AuthBloc`, на
который подписан `MainPage`. Чтением `lib/pages/profile/bloc/auth_bloc.dart`
подтверждён и **третий** путь к тому же самому `AuthLogout`, не
упомянутый явно в тексте [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md)
(см. «Открытые вопросы»): `on<AuthEventDeleteAccount>` (запрос удаления
аккаунта, [EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md),
тоже инициируется [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)) вызывает
`_authRepository.deleteUser()`, затем `_authRepository.logout()`, затем тот
же `emit(const AuthLogout())`. Во всех трёх случаях сам актор, действующий в
момент **этого** сценария (собственно очистки БД), — не человек:
`DataUpdateBloc.on<DataUpdateClear>` выполняется без какого-либо
пользовательского участия в момент вызова, инициирован он был раньше одним
из трёх перечисленных путей.

## CURRENT

### Основной поток

1. Один из трёх путей (см. «Пользователь») доводит `AuthBloc` до
   `emit(const AuthLogout())`.
2. `MainPage`'s `BlocListener<AuthBloc, AuthState>`
   (`lib/pages/main/main_page.dart`) реагирует на `state is AuthLogout`:
   первой строкой веб-обработчика вызывает
   `context.read<DataUpdateBloc>().add(DataUpdateClear())`. `Bloc.add` —
   синхронный вызов (кладёт событие в sink и возвращает управление
   немедленно), поэтому вызывающий код не ждёт, пока обработчик события
   реально завершится (см. «Альтернативные потоки»).
3. Тем же обработчиком, сразу вслед за строкой 2, без ожидания: `shellNavigatorMessagesKey.currentState?.popUntil((route) => route.isFirst)`,
   `shellNavigatorMainNavigatorKey.currentState?.popUntil((route) => route.isFirst)`
   (оба навигационных стека — вкладок «Сообщения» и «Ферма/место»/основной —
   сбрасываются на первый маршрут), затем `context.go(Routes.profile)`
   (`/profile`) — пользователь оказывается на экране профиля/входа.
4. Параллельно с шагом 3 (порядок относительно друг друга не
   гарантирован никаким `await`) `DataUpdateBloc` обрабатывает добавленное
   на шаге 2 событие: `on<DataUpdateClear>((event, emit) async { await
   _appDatabase.clearUserData(); DefaultCacheManager().emptyCache();
   pref.setBool('have_any_language', false); })` — это **весь** обработчик,
   три строки, без `emit(...)` ни одного состояния.
5. `_appDatabase.clearUserData()` (`packages/sheep_farm_database/lib/database/database.dart`)
   — тонкий алиас: `Future<void> clearUserData() =>
   clearAllClearableTables();`.
6. `clearAllClearableTables()` — сгенерированный код
   (`packages/sheep_farm_database/lib/database/database.clearable.dart`,
   `packages/sheep_farm_database/lib/clearable/clearable_builder.dart`)
   открывает Drift-`transaction()`, внутри которого сначала выполняет
   `customStatement('PRAGMA foreign_keys = OFF')`, затем внутри `try`
   последовательно удаляет **все строки** (`delete(table).go()`, без
   `WHERE`) из 15 таблиц, помеченных `@Clearable()` (подтверждено отдельным
   `grep -rl "@Clearable()"` по `packages/sheep_farm_database/lib/entities/`):
   `animalIdentifications`, `animalWeighings`, `animals`, `dataUpdates`,
   `disposals`, `enterpriseAddresses`, `farms`, `localGpsTrackers`,
   `movements`, `places`, `profileSettings`, `reportAnimals`,
   `selectionHistories`, `unsentReportAnimals`, `vaccinations` — порядок
   в списке ровно такой, каким он записан в сгенерированном методе (по
   алфавиту таблиц, не по порядку FK-зависимостей). В `finally` того же
   блока `PRAGMA foreign_keys = ON` включается обратно, независимо от
   исхода `try`. Вся последовательность удалений — одна Drift-транзакция:
   исключение на любом отдельном `delete(...).go()` откатывает все уже
   выполненные внутри неё удаления целиком, ничего не остаётся частично
   удалённым.
7. `clearAllClearableTables()` (и, соответственно, `clearUserData()`)
   возвращает управление без исключения — это и есть `DELETE_OK`: 15 таблиц
   оказываются пустыми одной атомарной операцией, включая
   [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (`dataUpdates`) —
   журнал последнего sync-прохода исчезает без следа, не просто
   «обнуляется на начало следующего прохода», как это происходит внутри
   `_syncAllData()`/`_clearDataUpdates()` при обычном полном sync-проходе.
8. `await` на шаге 4 (внутри `on<DataUpdateClear>`) продолжает: вызывается
   `DefaultCacheManager().emptyCache()` — **без `await`**, метод
   возвращает `Future<void>`, которое обработчик не ждёт. Затем
   `pref.setBool('have_any_language', false)` — тоже **без `await`**
   (`pref` — модуль-уровня `late final SharedPreferences`,
   `lib/main.dart`). Обработчик `on<DataUpdateClear>` завершается сразу
   после этой строки, не дожидаясь исхода ни одного из двух
   fire-and-forget вызовов — оба они предмет отдельного, не этого,
   документа (см. ниже).
9. Ни на одном из шагов 4–8 обработчик не вызывает `emit(...)` — состояние
   `DataUpdateBloc` не меняется этим событием вовсе (объект
   `DataUpdateClearSuccess`, существующий в `data_update_state.dart`, ни
   разу не конструируется во всём `lib/` — см. «Открытые вопросы»). Ни один
   `BlocListener<DataUpdateBloc, DataUpdateState>` (единственный —
   в `main_page.dart`, реагирующий только на `DataUpdateInProgress`) не
   получает сигнала об этом событии в принципе.

### Альтернативные потоки

- **Гонка между очисткой БД и уходом с экрана.** Поскольку `bloc.add()` на
  шаге 2 не дожидается завершения обработчика, а сброс двух навигационных
  стеков и `context.go(Routes.profile)` на шаге 3 выполняются сразу вслед за
  ним синхронно, экран профиля/входа отображается независимо от того,
  успела ли трёхшаговая Drift-транзакция шага 6 уже физически завершиться.
  На практике это не создаёт видимого пользователю расхождения данных (сама
  навигация уже увела пользователя с экранов, читавших очищаемые таблицы),
  но означает, что «уход на профиль» и «локальные данные действительно
  стёрты» — два независимых, не синхронизированных momента.
- **Третий путь к тому же `DataUpdateClear`, не описанный явно в тексте
  [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md).** Как показано
  в «Пользователь», `AuthBloc.on<AuthEventDeleteAccount>`
  ([EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md))
  тоже эмитит `AuthLogout` тем же путём, что и обычный выход/автоматическая
  потеря сессии — очистка БД по этому сценарию происходит и после успешного
  (с точки зрения `AuthBloc` — см. [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md),
  «Ограничения», про непроверенный ответ сервера в `deleteUser`) запроса на
  удаление аккаунта, не только после обычного логаута.
- **Два fire-and-forget вызова внутри того же обработчика — не предмет
  этого документа.** `DefaultCacheManager().emptyCache()` и
  `pref.setBool('have_any_language', false)` вызываются без `await` внутри
  `on<DataUpdateClear>` — сам обработчик и вызвавший его код (шаг 3)
  завершаются раньше, чем эти две операции реально произойдут. Ни одна из
  них не может отказать наблюдаемо для этого сценария (`DELETE_OK` этого
  UC — про очистку БД, шаги 5–7), но именно эта незавершённость —
  потенциальный источник отдельного, ERROR-сценария (гонка при уборке
  `tempDir` в тесте, см. «Связанные тесты», — прямое проявление того же
  факта в тестовом окружении). Аналогичной находке об `on<AuthEventDeleteAccount>`
  без ловли ошибок посвящено «Ограничения» в
  [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md); подробная спецификация
  этого конкретного ERROR-пути — задача отдельного документа (`UC-192`),
  здесь только фиксируется как контекст.
- **Отказ самой Drift-транзакции — путь, не наступающий на практике и не
  покрытый тестом.** Если бы `delete(...).go()` любой из 15 таблиц бросил
  исключение (например, при повреждении локального файла БД), `transaction()`
  откатила бы все уже сделанные внутри неё удаления, а исключение всплыло
  бы из `clearUserData()` наружу необработанным — `on<DataUpdateClear>` не
  оборачивает вызов в `try/catch`, поэтому исключение стало бы
  необработанной ошибкой обработчика события (тот же механизм, которым
  `Bloc.close()` дожидается будущего обработчика через `emitter.future`, но
  ошибка не гасится нигде выше). Этот путь не найден воспроизводимым при
  обычной работе приложения и не тестируется (см. «Связанные тесты»).

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  сущность, чья таблица (`DataUpdates`) физически опустошается этим
  сценарием целиком, а не только «обнуляется на начало следующего прохода»
  — единственный путь в кодовой базе, стирающий журнал прохода без того,
  чтобы тут же начать новый полный `_syncAllData()`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal),
  [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)
  (Movement), [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)
  (Vaccination), [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)
  (AnimalWeighing), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)
  (Disposal), [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport — таблицы `UnsentReportAnimals` и `ReportAnimals`
  обе `@Clearable`) — все семь также физически очищаются той же
  транзакцией шага 6, независимо от их собственного sync-статуса
  (`sync`/`needsUpdate`/`errors`): и уже синхронизированные, и ещё не
  отправленные строки стираются одинаково, без разбора.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm),
  [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — тоже
  `@Clearable`, очищаются той же транзакцией.
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — тоже `@Clearable`; сам файл этой сущности уже заранее
  фиксирует этот факт и явно называет `DataUpdateClear`/`clearUserData()`
  по имени, отмечая асимметрию с [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)
  (Device, настройки сканера — не `@Clearable`, переживает логаут на том же
  устройстве).
- Три дополнительные `@Clearable`-таблицы без собственного `ENT`-id на
  сегодня: `SelectionHistories` (история автокомплита при регистрации
  животного, живой код — `lib/repositories/selection_history/selection_history_repository.dart`)
  очищается вместе со всеми остальными; `EnterpriseAddresses` и
  `LocalGpsTrackers` — таблицы, для которых `grep -rn` по всему `lib/` не
  находит ни одного обращения (`EnterpriseAddress\b`, `LocalGpsTracker`) —
  структурно мёртвые остатки удалённых легаси-модулей, физически всё ещё
  очищаемые этим сценарием наравне с живыми таблицами, хотя реально в них
  ничего не пишется.
- `HANDBOOKS`/`BOARD`-справочники ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)
  и другие; [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) и т.д.) и
  [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — явно
  **не** затрагиваются этим сценарием (не `@Clearable`) — механизм, которым
  справочники и настройки сканера остаются доступными офлайн после смены
  аккаунта на одном устройстве.

### Бизнес-правила

- Очистка — «всё или ничего» на уровне 15 `@Clearable`-таблиц: нет
  выборочной очистки по пользователю/аккаунту, нет частичного отката —
  единая Drift-транзакция.
- Набор очищаемых таблиц определяется исключительно наличием аннотации
  `@Clearable()` на объявлении Drift-таблицы и сгенерированным кодом
  (`clearable_builder.dart` перечисляет их в
  `database.clearable.dart`) — не отдельным ручным списком в
  `DataUpdateBloc`/`AppDatabase`, который нужно было бы поддерживать
  вручную.
- Очистка не зависит от того, каким из трёх путей (обычный логаут,
  автоматическая потеря сессии, удаление аккаунта) был инициирован
  `AuthLogout` — во всех трёх случаях выполняется один и тот же
  `DataUpdateClear`.
- Результат этого сценария не сигнализируется пользователю никаким
  отдельным UI-состоянием (нет прогресса, нет подтверждения) — единственный
  видимый пользователю эффект самого выхода — переход на экран профиля
  (шаг 3), который происходит независимо от этого сценария и не ждёт его
  завершения.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной поток (три строки
`on<DataUpdateClear>`, `clearUserData()` → `clearAllClearableTables()`,
список из 15 `@Clearable`-таблиц, включая саму `DataUpdates`) полностью
воспроизводится статическим чтением кода и подтверждён прогоном
существующего теста (см. «Связанные тесты»). Возможные уточнения
(например, явная эмиссия `DataUpdateClearSuccess`, ожидание завершения
очистки перед навигацией на шаге 3, `await` для двух fire-and-forget
вызовов) в рамках этого документирующего прохода не выполняются — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main/main_page.dart` | `BlocListener<AuthBloc, AuthState>` внутри `MainPage.build` | CURRENT | реагирует на `state is AuthLogout`: диспатчит `DataUpdateClear()`, сбрасывает `shellNavigatorMessagesKey`/`shellNavigatorMainNavigatorKey`, вызывает `context.go(Routes.profile)` — без ожидания завершения `DataUpdateClear` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventLogout>`, `on<AuthEventDeleteAccount>` | CURRENT | оба обработчика эмитят `AuthLogout`; первый — по явному логауту или по авто-инвалидации (`event.clearData`), второй — после запроса удаления аккаунта (третий, не упомянутый в тексте EVT-95 путь к тому же `DataUpdateClear`) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateClear>` | CURRENT | весь обработчик сценария — три вызова, без `emit(...)`, без `try/catch` |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateClearSuccess` | CURRENT | объявлен, но не конструируется нигде в `lib/` — мёртвый класс состояния (см. «Открытые вопросы») |
| `lib/main.dart` | `late final SharedPreferences pref` | CURRENT | глобальный объект, на котором вызывается `setBool('have_any_language', false)` без `await` внутри обработчика |
| `packages/sheep_farm_database/lib/database/database.dart` | `AppDatabase.clearUserData` | CURRENT | тонкий алиас на `clearAllClearableTables()` |
| `packages/sheep_farm_database/lib/database/database.clearable.dart` | `ClearableExtension.clearAllClearableTables` | CURRENT | сгенерированный код: одна Drift-`transaction()`, `PRAGMA foreign_keys = OFF/ON`, 15 `delete(table).go()` без `WHERE` |
| `packages/sheep_farm_database/lib/clearable/clearable_builder.dart` | построитель `database.clearable.dart` | CURRENT | источник списка таблиц — собирается по аннотации `@Clearable()`, не поддерживается вручную |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates` (`@Clearable()`) | CURRENT | таблица-предмет этого UC — очищается целиком, включая уже записанные строки текущего/предыдущего прохода |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart`, `animal_identification/animal_identifications.dart`, `animal_weighing/animal_weighings.dart`, `disposal/disposal.dart`, `enterprise_address/enterprise_addresses.dart`, `farm/farms.dart`, `gps_tracker/local_gps_trackers.dart`, `movement/movement.dart`, `place/places.dart`, `profile_settings/profile_settings.dart`, `reports_animals/report_animals.dart`, `selection_history/selection_histories.dart`, `unsent_report_animal/unsent_report_animals.dart`, `vaccination/vaccinations/vaccinations.dart` | соответствующие `@Clearable()` Drift-таблицы | CURRENT | остальные 14 таблиц, очищаемые той же транзакцией |

## Критерии приёмки

- `MainPage`'s `BlocListener<AuthBloc, AuthState>` при `state is AuthLogout`
  диспатчит ровно один `DataUpdateBloc.add(DataUpdateClear())`, независимо
  от того, каким из трёх путей (`EVT-7`, `EVT-8`, `EVT-9`) был достигнут
  `AuthLogout`.
- `on<DataUpdateClear>` вызывает `_appDatabase.clearUserData()` и дожидается
  его (`await`) — метод возвращается без исключения при штатной работе БД.
- `clearAllClearableTables()` выполняет удаление всех строк из всех 15
  таблиц, помеченных `@Clearable()` (список зафиксирован в «Технические
  зависимости»), одной атомарной Drift-транзакцией с временно отключёнными
  проверками внешних ключей.
- Таблица `DataUpdates` ([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md))
  оказывается пустой после этого сценария, независимо от того, сколько
  строк успело накопиться в текущем/предыдущем sync-проходе.
- Ни одна не-`@Clearable` таблица (справочники HANDBOOKS/BOARD, `Devices`,
  `Kind.visible`) не затрагивается.
- Обработчик `on<DataUpdateClear>` не эмитит ни одного состояния
  `DataUpdateBloc` — ни `DataUpdateInProgress`, ни `DataUpdateClearSuccess`,
  ни какого-либо другого.

## Связанные тесты

`test/blocs/data_update_bloc_test.dart` — единственный существующий тест
блока, `blocTest('DataUpdateClear очищает пользовательские данные БД', ...)`,
вызванный напрямую на верхнем уровне `main()` (без `group(...)`, без номера
use-case в названии — это первое присвоение номера этому тесту, не
переименование). Файл открывается развёрнутым комментарием-дисклеймером,
объясняющим, почему `DataUpdateStartAll` (~900 из 1013 строк файла —
основной sync pipeline) не покрыт юнит-тестом:

> `// DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры getIt<X>()`
> `// (не через конструктор) — конструктору бЛока нужны ВСЕ они зарегистрированы,`
> `// даже для теста одного простого события. DataUpdateStartAll (~900 из 1013`
> `// строк файла — основной sync pipeline) НЕ покрыт юнит-тестом: первая же`
> `// строка обработчика — await hasNetworkConnection() (реальный DNS-запрос`
> `// без DI-точки), дальше десятки приватных методов и реальные транзакции`
> `// AppDatabase. Осмысленный юнит-тест такого масштаба потребовал бы`
> `// рефакторинга источника под DI — вне рамок написания тестов без изменения`
> `// кода. См. TESTING_CHECKLIST.md.`

Именно поэтому в `setUp` регистрируются моки для всех >25 репозиториев
конструктора `DataUpdateBloc`, а `AppDatabase` — не мок: `registerTestGetIt()`
регистрирует **настоящий** in-memory `AppDatabase` (`createTestDatabase()`),
через который и проходит реальная транзакция `clearAllClearableTables()` в
этом тесте. Отдельно замокан платформенный канал `path_provider`
(на настоящую временную папку) — сам `DataUpdateClear` конструирует
`DefaultCacheManager()`, который дёргает `path_provider` за временной
директорией; `tearDown` содержит собственный комментарий, объясняющий, что
удаление этой временной папки может гоняться с фоновым (не дождавшимся,
см. «Альтернативные потоки») `DefaultCacheManager().emptyCache()`, и поэтому
оборачивает удаление в `try/catch (_) {}`.

Сам тест: `act: (bloc) => bloc.add(DataUpdateClear())`, `verify: (_) {
expect(pref.getBool('have_any_language'), isFalse); }`. Проверяется **только**
факт сброса `have_any_language` в `SharedPreferences` — ни одна таблица БД не
засеивается данными перед актом и не проверяется на пустоту после: тест не
содержит ни одной проверки, что `Animals`/`Farms`/`DataUpdates`/любая другая
из 15 `@Clearable`-таблиц действительно была очищена, несмотря на название
теста («…очищает пользовательские данные БД»). Реальный вызов
`clearAllClearableTables()` в тесте происходит (тест бы упал, если бы этот
вызов бросил исключение — `bloc.close()`, вызываемый `blocTest` перед
`verify`, дожидается завершения `on<DataUpdateClear>` через
`Future.wait(_emitters.map((e) => e.future))` пакета `bloc`), но сам факт
очистки БД проверяется этим тестом лишь косвенно (отсутствием падения), не
прямой проверкой состояния таблиц.

## Открытые вопросы и ограничения

- **Третий триггер (`EVT-9`, удаление аккаунта) не упомянут в тексте
  [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md).** Событие
  заморожено и не правится этим документом, но статическое чтение
  `AuthBloc.on<AuthEventDeleteAccount>` подтверждает, что оно эмитит тот же
  `AuthLogout`, которого достаточно для `MainPage` — то есть очистка БД по
  этому сценарию наступает и после удаления аккаунта, не только после
  логаута/авто-инвалидации. Не зафиксировано нигде явно, было ли это
  учтено при написании EVT-95, или обнаружено только сейчас.
- **`DataUpdateClearSuccess` — мёртвый класс состояния.** Объявлен в
  `data_update_state.dart` с полем `closePage`, но `grep -rn
  "DataUpdateClearSuccess" lib/ test/` не находит ни одного места, где он
  бы конструировался или на него бы кто-то реагировал. Является ли это
  недописанной фичей (например, экран, который должен был закрыться по
  этому состоянию) или полностью устаревшим остатком — ничем в
  коде/комментариях не зафиксировано.
- **Гонка между навигацией и очисткой БД (шаги 2–3 vs 4–7) не имеет
  наблюдаемых последствий в проверенном коде, но и не гарантирована никаким
  контрактом.** `bloc.add()` не дожидается обработчика; если бы в будущем
  экран профиля (`Routes.profile`) стал читать любую из 15 `@Clearable`-таблиц
  сразу при построении, он мог бы увидеть данные, ещё не успевшие
  физически удалиться. На сегодня, судя по прочитанному коду
  `profile_view.dart`/навигации, такого чтения нет — риск теоретический, не
  подтверждённый эмпирически.
- **Два fire-and-forget вызова (`DefaultCacheManager().emptyCache()`,
  `pref.setBool('have_any_language', false)`) — их собственный ERROR-путь
  не специфицирован этим документом.** Оставлены как контекст по прямому
  указанию в постановке задачи; отдельная спецификация — предмет `UC-192`.
- **`SelectionHistories`/`EnterpriseAddresses`/`LocalGpsTrackers` не имеют
  собственного `ENT`-id.** `SelectionHistories` — живая таблица (история
  автокомплита REG), `EnterpriseAddresses`/`LocalGpsTrackers` — таблицы без
  единого обращения в `lib/` (подтверждено `grep -rn`), по всей видимости
  остатки удалённых легаси GPS/ENTRY-REQUIREMENTS-модулей; ни одна из трёх
  не заведена как отдельная сущность ни в одном специфицированном модуле —
  вне рамок этого документа решать, нужен ли им отдельный `ENT`-id.
- Не проверено эмпирически на реальном устройстве/сборке — вывод сделан
  статическим чтением кода и прогоном `test/blocs/data_update_bloc_test.dart`
  в тестовом окружении (in-memory Drift, замоканный `path_provider`), не
  реальным логаутом в работающем приложении.
