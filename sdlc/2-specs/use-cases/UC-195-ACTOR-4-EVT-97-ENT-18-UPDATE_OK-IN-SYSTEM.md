# UC-195 — Синхронизация 4 справочников доски объявлений сразу после HANDBOOKS, на общем снимке даты, без собственной записи в журнал прохода

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Успешный проход четырёх справочников BOARD (`board_ad_types`, `board_ad_statuses`,
`board_attributes`, `board_service_types`) — `DataUpdateBloc._loadBoardDirectories()`,
вызывается безусловно сразу после [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)
(`loadDirectories()`, HANDBOOKS), для гостя и авторизованного одинаково, до
проверки `_authRepository.isAuthorized()`. Эти четыре таблицы — не отдельная
сущность в дереве спек: они задокументированы как поля/справочники
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD), «используются только
этим модулем», тем же паттерном, что и справочники вакцинации внутри
[ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md). Этот сценарий — единственное место, где фиксируется факт их
периодической синхронизации, отложенный BOARD сюда, в SYSTEM (см. границу
модуля в [MOD-7](../modules/MOD-7-SYSTEM.md)).

Ключевой архитектурный факт, подтверждённый прочтением
`lib/blocs/data_update/data_update_bloc.dart`: все четыре вызова используют
**один и тот же** `updatedAtGt` — `directoriesSyncBaseline`, локальную
переменную `on<DataUpdateStartAll>`, прочитанную через
`AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)` **до**
вызова `await loadDirectories(event, emit)` (строка кода перед вызовом, не
после). Отдельного ключа/маркера «последняя синхронизация BOARD-справочников»
нигде в приложении не существует — BOARD целиком паразитирует на таймере
HANDBOOKS. Второй подтверждённый факт: `_loadBoardDirectories()` не вызывает
ни `_addDataUpdateSuccess`, ни `_addDataUpdateError` — успех этого шага нигде
не фиксируется в журнале прохода ([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)),
в отличие от `loadUser`, `loadAnimals`, `loadShtp` и самого `loadDirectories()`
(который, пусть и под ошибочной категорией `generationsTypes`, всё же пишет
свою строку).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — приложение, действующее
во время явного полного sync-прохода (`DataUpdateBloc.on<DataUpdateStartAll>`),
без участия пользователя в момент каждого отдельного сетевого вызова к
`${Constants.boardServiceApi}`. Сам проход инициирован одним из источников,
уже перечисленных для соседних шагов того же обработчика:

- вручную — кнопка/переход в `lib/pages/data_update/data_update_page.dart`,
  `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`
  (при смене языка интерфейса), `lib/pages/in_work/in_work_page.dart` (кнопка
  «Синхронизировать данные»);
- автоматически — `lib/pages/main/main_page.dart`'s
  `BlocListener<AuthBloc, AuthState>`, диспатчащий `DataUpdateStartAll` при
  переходе `AuthToMain` (успешный вход/восстановление сессии).

Независимо от источника, `main_page.dart` держит отдельный, глобальный
`BlocListener<DataUpdateBloc, DataUpdateState>`, который вызывает
`DataUpdatePage.show(context)` при **любом** `DataUpdateInProgress` —
поэтому пользователь, где бы он ни запустил проход, физически видит
полноэкранную модальную страницу прогресса (`WillPopScope` блокирует кнопку
«назад», пока состояние — `DataUpdateInProgress`) в момент, когда выполняется
и этот шаг тоже.

## CURRENT

### Основной поток

1. `on<DataUpdateStartAll>` (`lib/blocs/data_update/data_update_bloc.dart`):
   после успешной проверки сети (`NetworkConnectivityService.hasConnection()`
   — истинно, иначе `DataUpdateFailure` сразу, до входа в `try`) внутри
   общего `try` читает `final directoriesSyncBaseline =
   AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale);` —
   **до** любого вызова `loadDirectories()`.
2. `await loadDirectories(event, emit);` выполняется целиком ([EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)):
   ~18 справочников HANDBOOKS синхронизируются, в конце метод сам вызывает
   `AppCacheService.saveDirectoriesLastSyncDate(DateTime.now(), locale)` —
   перезаписывает то самое значение, которое `directoriesSyncBaseline` уже
   прочитала на шаге 1. Поскольку `directoriesSyncBaseline` — локальная
   `final`-переменная, эта перезапись её не затрагивает: до конца
   `on<DataUpdateStartAll>` она хранит значение «последний успешный
   синк ДО этого прохода», не «сейчас».
3. `await _loadBoardDirectories(event, emit, updatedAtGt:
   directoriesSyncBaseline);` вызывается сразу после — безусловно, без
   какой-либо проверки `_authRepository.isAuthorized()` (та стоит только
   перед следующим блоком, `_syncAuthData`, строго после этого вызова).
4. Внутри `_loadBoardDirectories`: `_emitProgress(emit: emit, dataKey:
   DataKey.board)` — эмитит `DataUpdateInProgress(messageKey: 'board', ...)`.
   Вызов не передаёт `dataCategory`, поэтому `_currentDataCategory` не
   меняется и остаётся тем, что оставил последний `_emitProgress` внутри уже
   завершившегося `loadDirectories()` — `DataCategory.generationsTypes` (см.
   [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), «категория
   `directories` фактически никогда не записывается»).
5. Последовательно, одно за другим (не параллельно, каждый `await`ится до
   следующего):
   - `await _boardAdTypesRepository.syncBoardAdTypes(updatedAtGt:
     updatedAtGt);` → `getBoardAdTypesFromApi` — `GET
     ${Constants.boardServiceApi}/ad_types`, `Accept-Language:
     LanguageService.locale`, query `updated_at_gt` = ISO8601 значения, если
     `updatedAtGt != null`, иначе без этого параметра (`{}`). Парсит
     `response['data']` через `BoardAdTypeDto.fromJson(...).toRow()`.
   - `await _boardAdStatusesRepository.syncBoardAdStatuses(updatedAtGt:
     updatedAtGt);` → тот же паттерн, `GET
     ${Constants.boardServiceApi}/statuses`.
   - `await _boardAttributesRepository.syncBoardAttributes(updatedAtGt:
     updatedAtGt);` → `GET ${Constants.boardServiceApi}/attributes`.
   - `await _boardServiceTypesRepository.syncBoardServiceTypes(updatedAtGt:
     updatedAtGt);` → `GET ${Constants.boardServiceApi}/service_types`.
   Во всех четырёх репозиториях (`lib/repositories/board/board_ad_types_repository.dart`
   и три соседних файла) `sync*` — идентичный по форме метод: `if
   (updatedAtGt != null) { await insertAll(items); } else { await
   clearAndInsertAll(items); }` — `insertAll` → `BaseRepository.insertAll` →
   `BaseDao.insAll` (`batch.insertAll(..., mode: InsertMode.insertOrReplace)`,
   без удаления существующих строк); `clearAndInsertAll` →
   `BaseDao.clearAndInsertAll` (`transaction`: `clear()` затем `insAll()`,
   полная перезапись таблицы).
6. Ни один из четырёх вызовов, ни сам `_loadBoardDirectories`, не вызывает
   `_addDataUpdateSuccess`/`_addDataUpdateError`
   ([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) — метод дочитан
   целиком (`lib/blocs/data_update/data_update_bloc.dart`,
   `_loadBoardDirectories`), обращений к `_dataUpdatesRepository` в нём нет.
   Единственное наблюдаемое следствие успеха — четыре обновлённые локальные
   таблицы; факт «BOARD-справочники синхронизированы в этом проходе» нигде
   не сохраняется отдельно.
7. Управление возвращается в `on<DataUpdateStartAll>`: `if
   (_authRepository.isAuthorized()) await _syncAuthData(event, emit);`
   выполняется дальше независимо от исхода этого шага (если он не бросил
   исключение); проход в итоге эмитит `DataUpdateSuccess(...)`.

### Альтернативные потоки

- **Первый проход на устройстве (`directoriesSyncBaseline == null`).**
  `AppCacheService.getDirectoriesLastSyncDate` возвращает `null`, пока не
  сохранена ни одна успешная синхронизация HANDBOOKS для текущей локали —
  все четыре `sync*` вызываются с `updatedAtGt: null` → все идут веткой
  `clearAndInsertAll` (полная перезаливка каждой из четырёх таблиц).
- **Повторный проход.** `directoriesSyncBaseline` не `null` → все четыре
  идут веткой `insertAll` (`InsertMode.insertOrReplace`, без удаления) —
  запись BOARD-справочника, удалённая на сервере, никогда не будет удалена
  локально инкрементальным проходом; единственный способ убрать её —
  следующий `clearAndInsertAll`, то есть следующий первый-проход-заново (тот
  же структурный паттерн, что и у ~18 справочников HANDBOOKS в
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md), унаследованный
  BOARD напрямую).
- **Смена языка/логин по паролю/переход в гостевой режим форсируют полный
  реload и здесь.** `directoriesSyncBaseline` читается тем же
  `AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`, что и
  `lastSyncDate` внутри `loadDirectories()` — если сохранённая локаль не
  совпадает с текущей, либо `AuthRepository.clearDirectoriesLastSyncDate()`
  уже обнулила ключ (вызовы из `loginWithoutAuthorization`,
  `_getTokenDataFromApi`, см. [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)),
  `directoriesSyncBaseline` тоже окажется `null` в этом проходе — BOARD
  форсированно уходит в полную перезаливку одновременно с HANDBOOKS, хотя
  у BOARD нет отдельного условия на этот счёт — оно целиком наследуется от
  общего ключа.
- **`EVT-96` (`loadDirectories()`) бросает исключение — `EVT-97` не
  наступает вовсе.** `await loadDirectories(event, emit)` (шаг 2) и `await
  _loadBoardDirectories(...)` (шаг 3) — последовательные `await` в одном
  `try` `on<DataUpdateStartAll>`; необработанное исключение внутри
  `loadDirectories()` передаёт управление сразу во внешний `catch`, минуя
  вызов `_loadBoardDirectories` целиком. BOARD-справочники в этом случае не
  трогаются в этом проходе вообще, включая ветку `clearAndInsertAll` при
  первом проходе.
- **Любой из четырёх `sync*` бросает исключение (контраст, не этот
  сценарий).** Ни один из четырёх методов, ни `_loadBoardDirectories`, не
  оборачивают вызов в собственный `try/catch` (только внутренний
  `getBoardXxxFromApi` логирует через `getIt<Talker>().info(...)` и делает
  `rethrow`) — исключение всплывает до внешнего `catch`
  `on<DataUpdateStartAll>` → `_emitError` → `_addDataUpdateError(dataCategory:
  _currentDataCategory, errorDataKey: _currentDataKey, ...)`. Поскольку
  `_currentDataCategory` на этот момент — `DataCategory.generationsTypes`
  (шаг 4 основного потока), ошибка любого из четырёх BOARD-запросов попадёт
  в журнал под категорией `generationsTypes` с `errorDataKey: 'board'` — тот
  же класс мислейблинга, что уже задокументирован для самого
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), теперь
  подтверждённый и для этого шага. Частичное применение возможно: если,
  например, `syncBoardAdTypes` успел закоммититься, а `syncBoardAdStatuses`
  бросил исключение, первая таблица останется обновлённой, тогда как
  `attributes`/`service_types` в этом проходе не выполнятся вовсе —
  атомарности между четырьмя шагами нет. Это отдельный `RESULT` (`ERROR`),
  не специфицируемый этим файлом — приведён только как контраст.
- **Ни одна из четырёх синхронизаций не проверяет `Country.boardEnabled`.**
  В отличие от видимости самого раздела BOARD в UI (управляется
  `BoardChatAvailabilityCubit`/`country?.boardEnabled`, см. [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)),
  `_loadBoardDirectories()` не читает ни `Country`, ни
  `_authRepository.isAuthorized()`, ни какой-либо флаг доступности — все
  четыре запроса выполняются на любом устройстве в любой стране, включая те,
  где раздел BOARD скрыт из навигации целиком.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD) — сегмент id этого
  use-case; сами объявления (`Ad`) не читаются и не изменяются этим сценарием,
  но четыре справочника-предмет этого сценария (`board_ad_types`,
  `board_ad_statuses`, `board_attributes`, `board_service_types`)
  задокументированы как часть именно этой сущности («Связи»/«Исходный код»
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) — отдельных `ENT-*` для них
  не заведено.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy, HANDBOOKS)
  — не читается и не изменяется этим сценарием напрямую, но
  `directoriesSyncBaseline`, используемый всеми четырьмя BOARD-запросами —
  это ровно то же значение `AppCacheService.getDirectoriesLastSyncDate`,
  которое [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)
  использует для синхронизации HANDBOOKS; BOARD и HANDBOOKS делят один
  таймер, а не имеют независимые.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  не читается этим сценарием (см. «Альтернативные потоки»): поле
  `boardEnabled` управляет только видимостью UI раздела BOARD, а не тем,
  синхронизируются ли его справочники на устройство.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate,
  SYSTEM) — журнал прохода, который этот сценарий **не пишет** ни при
  успехе (нет отдельной записи под каким-либо `DataCategory`), ни
  специфично при ошибке (ошибка любого из четырёх шагов записалась бы под
  чужой, уже занятой категорией `generationsTypes` — см. «Альтернативные
  потоки»).

### Бизнес-правила

- BOARD-справочники синхронизируются безусловно, в рамках любого полного
  sync-прохода, независимо от актора (гость/авторизованный) — так же, как
  и HANDBOOKS, и до какой-либо проверки авторизации.
- Инкрементальность/полная перезаливка определяется исключительно
  нулевостью общего `directoriesSyncBaseline`, того же самого значения, что
  определяет инкрементальность HANDBOOKS в этом же проходе — оба семейства
  справочников синхронизируются в одном и том же режиме (оба полные, либо
  оба инкрементальные) в любой конкретный проход, никогда порознь.
- Чтение `directoriesSyncBaseline` **до** запуска `loadDirectories()`, а не
  после — не случайность, а единственный способ, которым инкрементальное
  окно BOARD могло бы совпасть с окном HANDBOOKS: если бы это значение
  читалось после `loadDirectories()` (то есть после того, как та уже
  перезаписала сохранённую дату на «сейчас»), `updatedAtGt` для BOARD стал
  бы текущим моментом времени, а не датой последнего реального успешного
  синка — тогда любые серверные изменения BOARD-справочников, случившиеся
  между последним синком и текущим моментом, были бы молча пропущены на
  каждом проходе.
- Успех этого шага не оставляет никакого отдельного следа, кроме
  содержимого самих четырёх таблиц — ни в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md),
  ни в `SharedPreferences` (в отличие от HANDBOOKS, у которого есть
  `last_directories_sync_date`/`last_directories_sync_locale`). Диагностика
  «когда в последний раз реально синхронизировались BOARD-справочники»
  возможна только косвенно — через `updatedAt` полей самих строк, если
  сервер их присылает, либо вовсе невозможна.

## TARGET

TARGET не отличается от CURRENT. Отсутствие записи в
[ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) и безусловная
синхронизация независимо от `Country.boardEnabled` зафиксированы как факт
существующего кода в «Открытые вопросы и ограничения» — исправление в
рамках этого документирующего прохода не выполняется.

## TBD / BLOCKED

Блокеров для документирования нет. Основной поток (общий `updatedAtGt`,
последовательные `insertAll`/`clearAndInsertAll`, отсутствие записи в
[ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) полностью
воспроизводится статическим чтением кода: `DataUpdateBloc.on<DataUpdateStartAll>`
→ `.loadDirectories` → `._loadBoardDirectories` → четыре
`BoardXxxRepository.syncBoardXxx`. Не проверено эмпирически на реальном
запуске против настоящего бэкенда `${Constants.boardServiceApi}`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>`, `._loadBoardDirectories`, `.loadDirectories` | CURRENT | оркестрация: чтение общего `directoriesSyncBaseline` до `loadDirectories()`, безусловный вызов `_loadBoardDirectories` сразу после, отсутствие обращений к `_dataUpdatesRepository` внутри `_loadBoardDirectories` |
| `lib/repositories/board/board_ad_types_repository.dart` | `BoardAdTypesRepository.getBoardAdTypesFromApi`, `.syncBoardAdTypes` | CURRENT | `GET ${Constants.boardServiceApi}/ad_types`, incremental/full по `updatedAtGt != null` |
| `lib/repositories/board/board_ad_statuses_repository.dart` | `BoardAdStatusesRepository.getBoardAdStatusesFromApi`, `.syncBoardAdStatuses` | CURRENT | `GET ${Constants.boardServiceApi}/statuses`, тот же паттерн |
| `lib/repositories/board/board_attributes_repository.dart` | `BoardAttributesRepository.getBoardAttributesFromApi`, `.syncBoardAttributes` | CURRENT | `GET ${Constants.boardServiceApi}/attributes`, тот же паттерн |
| `lib/repositories/board/board_service_types_repository.dart` | `BoardServiceTypesRepository.getBoardServiceTypesFromApi`, `.syncBoardServiceTypes` | CURRENT | `GET ${Constants.boardServiceApi}/service_types`, тот же паттерн |
| `lib/repositories/base_repository.dart` | `BaseRepository.insertAll`, `.clearAndInsertAll` | CURRENT | тонкая обёртка, делегирует в DAO |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll`, `.clearAndInsertAll` | CURRENT | `insAll` — `insertOrReplace` без удаления; `clearAndInsertAll` — `clear()` + `insAll()` в одной транзакции |
| `packages/sheep_farm_database/lib/entities/board/board_ad_types.dart`, `board_ad_statuses.dart`, `board_attributes.dart`, `board_service_types.dart` | `BoardAdTypes`, `BoardAdStatuses`, `BoardAttributes`, `BoardServiceTypes` | CURRENT | Drift-таблицы, предмет синхронизации этого сценария |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate`, `.saveDirectoriesLastSyncDate` | CURRENT | единственный источник `directoriesSyncBaseline`; ключ и значение общие с HANDBOOKS, отдельного ключа для BOARD нет |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey.board` | CURRENT | `DataKey.board = 'board'` используется как `messageKey` прогресса; ни один `DataCategory` не соответствует именно этому шагу |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository` | CURRENT | не вызывается из `_loadBoardDirectories` вовсе — отсутствие вызова и есть находка этого сценария |
| `lib/pages/main/main_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` → `DataUpdatePage.show` | CURRENT | глобально показывает модальную страницу прогресса при любом `DataUpdateInProgress`, включая этот шаг, независимо от источника запуска прохода |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdateInProgressWidget`, `_Body.build` | CURRENT | отображает `state.messageKey` (`'board'`) как обычный `Text`, без прогона через `AppLocalizations.tr` |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` | CURRENT | `switch` не содержит кейса `'board'` — сработал бы `default: return key`, если бы этот текст где-то прогонялся через `tr()` (не прогоняется, см. выше) |
| `lib/constants.dart` | `Constants.boardServiceApi` | CURRENT | общий API-хост-сегмент для всех четырёх запросов этого сценария |

## Критерии приёмки

- `_loadBoardDirectories` вызывается ровно один раз за проход, сразу после
  успешного завершения `loadDirectories()`, безусловно для гостя и
  авторизованного, до проверки `_authRepository.isAuthorized()`.
- Все четыре вызова (`syncBoardAdTypes`, `syncBoardAdStatuses`,
  `syncBoardAttributes`, `syncBoardServiceTypes`) получают один и тот же
  `updatedAtGt`, равный `directoriesSyncBaseline` — значению, прочитанному
  **до** запуска `loadDirectories()`, не значению, сохранённому в конце его
  выполнения.
- При `updatedAtGt == null` (первый проход/форсированный полный реload) —
  каждая из четырёх таблиц проходит `clearAndInsertAll` (полная перезапись).
  При `updatedAtGt != null` — каждая проходит `insertAll` (`insertOrReplace`,
  без удаления существующих строк).
- Ни при успешном, ни при неуспешном завершении любого из четырёх запросов
  `_loadBoardDirectories` не вызывает `_addDataUpdateSuccess` напрямую —
  успех этого шага не создаёт отдельной строки в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) ни под одной из 9
  категорий `DataCategory`.
- Полный sync-проход продолжается (`_syncAuthData`, если авторизован; в
  конце — `DataUpdateSuccess`) независимо от того, что успех именно этого
  шага нигде не зафиксирован отдельно.
- Во время выполнения этого шага пользователь, у которого на экране
  смонтирован `main_page.dart` (то есть всегда, пока приложение открыто),
  видит `DataUpdatePage` с текстом `messageKey == 'board'`, показанным без
  локализации.

## Связанные тесты

`test/blocs/data_update_bloc_test.dart` регистрирует моки для всех четырёх
board-репозиториев (`MockBoardAdTypesRepository`,
`MockBoardAdStatusesRepository`, `MockBoardAttributesRepository`,
`MockBoardServiceTypesRepository`) в общем `setUp`, но ни один тест файла не
диспатчит `DataUpdateStartAll` и не проверяет `_loadBoardDirectories` —
единственный содержательный тест файла:

```dart
blocTest<DataUpdateBloc, DataUpdateState>(
  'DataUpdateClear очищает пользовательские данные БД',
  ...
);
```

(прямой `blocTest` верхнего уровня, не внутри `group()`, без номера — это
тест на `DataUpdateClear`, не на сценарий этого файла). Файл же содержит
явный дисклеймер, объясняющий, почему это так:

> DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры getIt<X>()
> (не через конструктор) — конструктору бЛока нужны ВСЕ они зарегистрированы,
> даже для теста одного простого события. DataUpdateStartAll (~900 из 1013
> строк файла — основной sync pipeline) НЕ покрыт юнит-тестом: первая же
> строка обработчика — `await hasNetworkConnection()` (реальный DNS-запрос
> без DI-точки), дальше десятки приватных методов и реальные транзакции
> AppDatabase. Осмысленный юнит-тест такого масштаба потребовал бы
> рефакторинга источника под DI — вне рамок написания тестов без изменения
> кода. См. TESTING_CHECKLIST.md.

`grep -rn "loadBoardDirectories\|_loadBoardDirectories" test/` не находит
ничего, кроме импортов моков в этом же файле.

**TBD — теста нет** на сценарий этого файла (ни на общий `updatedAtGt`
между четырьмя запросами, ни на incremental/full ветвление, ни на
отсутствие записи в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)).

## Открытые вопросы и ограничения

- **Успех шага нигде не фиксируется.** В отличие от `loadUser`, `loadAnimals`,
  `loadShtp` и самого `loadDirectories()` (пусть и под неверной категорией),
  `_loadBoardDirectories()` — единственный крупный шаг полного sync-прохода,
  вообще не пишущий в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).
  Не зафиксировано, было ли это осознанным решением (справочники BOARD
  сочли не заслуживающими отдельного трекинга) или недосмотром при
  добавлении этого шага в pipeline.
- **Безусловная синхронизация независимо от доступности BOARD в стране
  пользователя.** `Country.boardEnabled` управляет только видимостью
  экранов ([UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)), не
  тем, скачиваются ли справочники — устройства в странах с отключённым
  BOARD всё равно получают и хранят локально все четыре таблицы, которые
  никогда не будут показаны в UI этого устройства.
- **Общий с HANDBOOKS таймер — не выбор, а отсутствие альтернативы.**
  BOARD не может синхронизироваться чаще или реже HANDBOOKS, и не может
  быть форсирован к полному реload независимо от него — оба семейства
  всегда находятся в одной фазе (оба incremental либо оба full) в любой
  конкретный проход.
- **Мислейблинг ошибки при отказе этого шага** (см. «Альтернативные
  потоки») — не специфицируется этим файлом (это `RESULT=ERROR`, другой
  use-case), но обязан быть при нём учтён: ошибка любого из четырёх
  BOARD-запросов попала бы в журнал под чужой категорией
  `generationsTypes`, унаследовав тот же класс дефекта, что уже
  задокументирован для [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)
  в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).
- Не проверено эмпирически на реальном запуске против настоящего
  бэкенда — вывод сделан статическим чтением кода, без запущенного теста,
  подтверждающего именно эту цепочку (см. «Связанные тесты» — TBD).
