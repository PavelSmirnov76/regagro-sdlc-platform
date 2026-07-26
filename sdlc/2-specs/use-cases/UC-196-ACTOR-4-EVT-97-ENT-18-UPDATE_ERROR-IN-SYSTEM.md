# UC-196 — Sync board-справочников отказывает: исключение любого из 4 репозиториев обрывает весь sync-проход, а единственная запись об этом в журнале уходит под чужой категорией `generationsTypes`, оставленной предыдущим шагом

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же шаг, что описан в [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md) —
`DataUpdateBloc._loadBoardDirectories()` синхронизирует 4 справочника BOARD
(`board_ad_types`, `board_ad_statuses`, `board_attributes`,
`board_service_types` — все четыре описаны как часть самой сущности
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md), «справочники, используемые
только этим модулем») сразу после
[EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md), безусловно, для
гостя и авторизованного одинаково. Здесь — сценарий, в котором сетевой вызов
одного из четырёх репозиториев заканчивается исключением. Метод
`_loadBoardDirectories` не имеет собственного `try/catch`, поэтому исключение
всплывает до единственного перехватчика на весь sync-проход —
`DataUpdateBloc.on<DataUpdateStartAll>` — и обрывает **весь** проход, включая
для авторизованного пользователя все последующие шаги `_syncAuthData`
(фермы/места/взвешивания/животные/вакцинации/выбытия/отчёты/устройства),
которые физически не достигаются в этом проходе вовсе, хотя формально
относятся к совершенно другому модулю (`ANIMAL`/`FARM`/`PROFILE`).

Прочтением кода подтверждено: запись в журнал sync-прохода
([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) при этом отказе
**делается** — через общий `_emitError`/`_addDataUpdateError`, как и для
любого другого исключения, долетевшего до внешнего `catch`, — но под
категорией `DataCategory.generationsTypes`, оставшейся от **предыдущего**,
не относящегося к BOARD шага (`loadDirectories()`), а не под какой-либо
board-специфичной категорией: `DataCategory` (9 значений, см.
[ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) не содержит значения
`board` вовсе. Единственный сохранившийся board-специфичный след —
`errorDataKey = 'board'` (`DataKey.board`, простая текстовая константа, не
завязанная на `enum`).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет — проход уже был запущен ранее одним из способов:

- явно [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — кнопка обновления в
  `lib/pages/data_update/data_update_page.dart`,
  `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`
  или `lib/pages/in_work/in_work_page.dart`;
- автоматически [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) —
  `lib/pages/main/main_page.dart`'s `BlocListener<AuthBloc, AuthState>`
  диспатчит `DataUpdateStartAll` при переходе `AuthToMain` (успешное
  восстановление сессии/вход), без отдельного нажатия «обновить».

`loadDirectories()` и следующий за ним `_loadBoardDirectories()` выполняются
безусловно для **любого** актора — и гостя, и авторизованного;
`_authRepository.isAuthorized()` проверяется только для последующего шага
`_syncAuthData`, до которого в этом сценарии выполнение не доходит вовсе (см.
«Основной поток», шаг 11). Дальше проход идёт полностью автоматически, без
участия пользователя на уровне отдельного сетевого вызова, как и описано в
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети (`NetworkConnectivityService.hasConnection()` — истинно, иначе
   `DataUpdateFailure` сразу, до входа в общий `try`) выставляется
   `directoriesSyncBaseline = AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
   — значение, сохранённое **предыдущим** успешным проходом (или `null` при
   первом запуске).
2. `await loadDirectories(event, emit)` выполняется полностью успешно (все
   ~18 HANDBOOKS-справочников, включая `Kind`/`Breed`/`Suit`/`BreedSuit` —
   [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) — синхронизируются без
   ошибки; отказ на этом более раннем шаге — другой, здесь не покрываемый
   сценарий). В конце `loadDirectories()`: (а) **безусловно**
   `AppCacheService.saveDirectoriesLastSyncDate(DateTime.now(), LanguageService.locale)`
   перезаписывает персистентный `last_directories_sync_date` — независимо от
   исхода следующего шага, который на этот момент ещё даже не начался; (б)
   `_addDataUpdateSuccess(_currentDataCategory)` пишет в
   [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) строку успеха под
   категорией `DataCategory.generationsTypes` — последним явным присвоением
   `_currentDataCategory` внутри `loadDirectories()` (см.
   [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), «Категория
   `directories` фактически никогда не записывается»). Именно это
   присвоение — источник категории, под которой чуть позже запишется и
   ошибка этого сценария.
3. `await _loadBoardDirectories(event, emit, updatedAtGt: directoriesSyncBaseline)`
   начинается. Первая строка — `_emitProgress(emit: emit, dataKey: DataKey.board)`
   — **без аргумента `dataCategory`**. Внутри `_emitProgress` параметр
   `dataCategory` опционален: если не передан, `_currentDataCategory` не
   переписывается и остаётся тем же, что было выставлено на шаге 2
   (`DataCategory.generationsTypes`) — меняется только `_currentDataKey`, на
   `'board'`.
4. `_loadBoardDirectories` **не имеет собственного `try/catch`** — весь метод
   последовательно, без промежуточной обработки ошибок, вызывает:
   `_boardAdTypesRepository.syncBoardAdTypes(updatedAtGt: ...)` →
   `_boardAdStatusesRepository.syncBoardAdStatuses(updatedAtGt: ...)` →
   `_boardAttributesRepository.syncBoardAttributes(updatedAtGt: ...)` →
   `_boardServiceTypesRepository.syncBoardServiceTypes(updatedAtGt: ...)`.
   Каждый из четырёх — `getBoardXFromApi()` (GET-запрос через
   `rpcClient.call(message)`, `instanceName: 'farm_rpc'`) плюс
   `insertAll`/`clearAndInsertAll` в зависимости от того, передан ли
   `updatedAtGt`.
5. В этом сценарии один из четырёх вызовов (любой — наблюдаемый эффект
   одинаков для всех четырёх, см. «Альтернативные потоки») заканчивается
   исключением: внутри `getBoardXFromApi()` собственный `catch (e, st) { getIt<Talker>().info('...Error: $e st: $st'); rethrow; }`
   логирует его во внутренний `Talker`-лог и безусловно перебрасывает
   (`rethrow`) — источник исключения либо `CustomDioClient.call` (сеть,
   таймаут, любой не-2xx статус — `DioClient` не переопределяет
   `validateStatus`), либо приведение `response['data'] as List<dynamic>` при
   ответе без ожидаемого ключа `data`.
6. Исключение всплывает из `syncBoardX...()`, из `_loadBoardDirectories`
   (шаг 4, без собственного `catch`), напрямую в `catch (error, stackTrace)`
   обработчика `on<DataUpdateStartAll>` — единственную точку перехвата на
   весь sync-проход.
7. Внешний `catch`: `getIt<Talker>().error('Возникла при обновлении данных $error $stackTrace')`,
   затем `await _emitError(emit: emit, error: error, stackTrace: stackTrace)`
   (`isAdressUpdate` не передан, остаётся `false` по умолчанию).
8. `_emitError` вызывает `_addDataUpdateError(dataCategory: _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')`.
   На этот момент `_currentDataCategory == DataCategory.generationsTypes`
   (оставшееся от шага 2, HANDBOOKS-шага, не относящегося к BOARD) и
   `_currentDataKey == 'board'` (выставленное на шаге 3). Строка
   вставляется в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
   (`DataUpdatesRepository.insert` → `BaseDao.ins` →
   `InsertMode.insertOrReplace`; поскольку `id` — autoincrement и в
   `DataUpdatesCompanion` не задаётся, конфликтов нет — вставляется **новая**
   строка, ничего не заменяется).
9. `_emitError` также эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'board', errorMessage: 'error: $error, stackTrace: $stackTrace', isAdressesUpdate: false)`.
   Весь sync-проход на этом заканчивается для данного вызова
   `on<DataUpdateStartAll>`; `finally` всё равно выполняется —
   `ApiClient(instanceName: 'farm_rpc')`/`ApiClient(instanceName: 'r3_rpc')`
   сбрасываются.
10. `lib/pages/main/main_page.dart`'s `BlocListener<DataUpdateBloc, DataUpdateState>`
    открыл `DataUpdatePage` ещё в момент самого первого
    `emit(DataUpdateInProgress(...))`, до входа в `try` (шаг 1 общей
    последовательности). `DataUpdatePage`'s собственный `_Body.build`
    реагирует на `DataUpdateFailure`, отображая
    `'${AppLocalizations.of(context)!.tr('an_error_data')}\n${AppLocalizations.of(context)!.tr('board')}'`.
    `'an_error_data'` разрешается в реальный локализованный текст
    (`app_en.arb`/`app_ru.arb`: «An error occurred while processing
    data»/«Произошла ошибка при обработке данных»). Для `'board'` в
    `AppLocalizationsExtension.tr` (`lib/l10n/app_localization.dart`) нет
    отдельного `case` — управление попадает в `default: return key;` —
    пользователь видит вторую строку буквально как нелокализованное
    английское слово `board`.
11. Поскольку исключение произошло **до** проверки
    `_authRepository.isAuthorized()`, шаг `_syncAuthData` (фермы, места,
    взвешивания, `updateAndSyncRegagro`/`_syncAllData` целиком — животные,
    перемещения, вакцинации, выбытия, `syncEditedAnimals`,
    `updateAndSyncSHTP`/отчёты, `_suncDevices`) в этом проходе **не
    выполняется вовсе**, даже для авторизованного пользователя — блок с
    полностью не связанной с BOARD доменной логикой ANIMAL/FARM/PROFILE
    целиком приносится в жертву отказу одного из четырёх
    справочников BOARD.
12. Поскольку `_syncAuthData` (а значит и вложенный в него, через
    `updateAndSyncRegagro`, вызов `_syncAllData`) не выполняется,
    `_clearDataUpdates()` (`_dataUpdatesRepository.clear()`) — единственное
    место, которое очищает журнал [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
    в начале прохода — **тоже не выполняется в этом проходе**. Обе строки,
    записанные в этом же проходе (успех `generationsTypes` на шаге 2, ошибка
    `generationsTypes`/`'board'` на шаге 8), добавляются **поверх** того, что
    уже лежало в таблице от предыдущего прохода, который дошёл до
    `_syncAllData`, а не в свежеочищенную таблицу — вопреки общему описанию
    [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) «полностью
    очищается в начале каждого полного прохода» (это верно только для
    проходов, которые доходят до `_syncAllData`; см. «Открытые вопросы»).
13. Следующий полный sync-проход читает `directoriesSyncBaseline` заново —
    это уже **новое** значение, сохранённое на шаге 2 **этого** (упавшего)
    прохода, а не старое значение, с которым сам шаг 4 (board) в этом
    проходе фактически работал и не смог завершить. Поскольку у BOARD нет
    собственного персистентного «последнего успешного» момента (см.
    [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md),
    «отдельного ключа для BOARD нет»), следующая попытка синхронизации
    четырёх board-справочников запросит с сервера изменения
    `updated_at_gt: <новое значение>` — окно между старым `directoriesSyncBaseline`
    (тем, что реально нужно было board на этом проходе) и новым (уже
    сохранённым HANDBOOKS-шагом до отказа BOARD) оказывается пропущено
    **навсегда**, ни один следующий проход его больше не запросит (см.
    «Открытые вопросы» — расширенный разбор).

### Альтернативные потоки

- **Любой из четырёх репозиториев даёт один и тот же наблюдаемый эффект.**
  `_emitProgress(dataKey: DataKey.board)` вызывается **один раз**, до всех
  четырёх `syncBoardX...()`; между ними нет ни одного дополнительного
  вызова `_emitProgress`. Поэтому `errorDataKey` в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) — всегда `'board'`,
  независимо от того, какой именно из четырёх справочников отказал: в
  отличие от `loadDirectories()` (который вызывает `_emitProgress` с
  собственным `DataKey` перед каждым HANDBOOKS-справочником —
  `DataKey.kinds`, `DataKey.breeds`, `DataKey.suits` и т.д. — и потому при
  отказе одного из них сохраняет хотя бы этот более точный ключ),
  `_loadBoardDirectories` теряет эту гранулярность: по журналу невозможно
  определить, какой конкретно из четырёх board-справочников не
  синхронизировался.
- **Частичный, не атомарный эффект на четырёх локальных таблицах.**
  Вызовы `syncBoardAdTypes` → `syncBoardAdStatuses` → `syncBoardAttributes` →
  `syncBoardServiceTypes` идут последовательно, каждый `await`-ится
  отдельно. Если, например, третий (`syncBoardAttributes`) бросает
  исключение, первые два (`board_ad_types`, `board_ad_statuses`) уже успели
  выполнить свой `insertAll`/`clearAndInsertAll` и физически обновлены в
  локальной БД, а `board_attributes` и `board_service_types` — нет; отката
  первых двух не происходит.
- **`REJECTED` структурно недостижим.** Ни один из четырёх
  `getBoardXFromApi()` не проверяет содержательный `status` ответа
  (в отличие, например, от `sendMovementsToApi`,
  [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) — код
  просто приводит `response['data'] as List<dynamic>` и полагается на то,
  что `CustomDioClient.call` уже бросит исключение на любом не-2xx ответе;
  единственная не-успешная ветка — техническое исключение (сетевое или
  ошибка приведения типа), одинаково обрабатываемое во всех четырёх
  репозиториях одним и тем же `catch (e, st) { ...; rethrow; }`.
- **Гость и авторизованный страдают от самого отказа `_loadBoardDirectories`
  одинаково** — оба доходят до этого шага безусловно и одинаково видят
  `DataUpdateFailure`; различие только в том, что у авторизованного этим же
  отказом дополнительно блокируется весь последующий `_syncAuthData` (шаг
  11), тогда как у гостя после `_loadBoardDirectories` в любом случае больше
  ничего не выполняется (`_syncAuthData` для гостя не вызывается вовсе, даже
  при полном успехе).
- **Отказ более раннего шага (`loadDirectories()`, до board) — другой,
  здесь не покрываемый сценарий.** Если исключение происходит внутри самого
  `loadDirectories()` (например, при синхронизации `Kind`/`Country`),
  `_currentDataCategory`/`_currentDataKey` на момент `_emitError` будут
  соответствовать тому HANDBOOKS-шагу, а не `generationsTypes`/`'board'`, и
  `_loadBoardDirectories` не будет вызван вовсе в этом проходе — тот же
  общий механизм (единственный внешний `catch`), но другая пара
  категория/ключ в журнале.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD) — сущность,
  указанная в id этого use-case: её собственные справочные таблицы
  (`board_ad_types`, `board_ad_statuses`, `board_attributes`,
  `board_service_types`, описанные внутри самой
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) как «справочники, используемые
  только этим модулем») — это именно то, что не смогло полностью
  синхронизироваться в этом сценарии (частично, для тех репозиториев,
  которые успели отработать до отказа — см. «Альтернативные потоки»); сами
  объявления (`Ad`) этим шагом не читаются и не изменяются.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  получает две новые строки за этот проход (успех `generationsTypes` от
  предшествующего `loadDirectories()`, ошибка `generationsTypes`/`'board'`
  от этого отказа), причём **не в свежеочищенную таблицу** — см. «Основной
  поток», шаг 12, и «Открытые вопросы».
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy — Kind/
  Breed/Suit/BreedSuit, HANDBOOKS) — упоминается только для контекста:
  синхронизируется успешно чуть раньше в этом же проходе, внутри
  `loadDirectories()` (шаг 2); сама эта сущность не портится и не связана с
  BOARD — приведена здесь, чтобы показать, что «чужая» категория
  `generationsTypes`, под которой записывается ошибка BOARD, тоже
  принадлежит не ENT-3, а отдельному справочнику `GenerationsType`
  (`lib/repositories/generations_types_repository/generations_types_repository.dart`),
  синхронизируемому тем же `loadDirectories()` позже, чем ENT-3, и раньше,
  чем возвращается управление в `on<DataUpdateStartAll>`.
- `Animal`, `Movement`, `Vaccination`, `AnimalWeighing`, `Disposal`, `Farm`,
  `Place`, `Device` (ANIMAL/FARM/PROFILE, все уже специфицированы своими
  модулями) — ни один из этих объектов не читается и не изменяется этим
  сценарием: весь `_syncAuthData`, отвечающий за их sync-шаги, не
  достигается вовсе (см. «Основной поток», шаг 11).

### Бизнес-правила

- Результат сценария — `UPDATE_ERROR`: локальные таблицы четырёх
  board-справочников не просто читаются, а перезаписываются
  (`clearAndInsertAll`/`insertAll`) содержимым, полученным с сервера; отказ
  этого одностороннего pull-обновления тонет в generic
  `DataUpdateFailure` всего sync-прохода, не доходя до пользователя как
  осознанно предъявленное решение по конкретному справочнику —
  `UPDATE_REJECTED` для этого шага структурно недостижим (см.
  «Альтернативные потоки»).
- **`_loadBoardDirectories` — единственный шаг всего sync-прохода,
  вызываемый безусловно (для гостя и авторизованного одинаково) и при этом
  способный обрушить весь оставшийся проход, включая полностью посторонний
  для BOARD `_syncAuthData`.** BOARD в остальном коде описан как «online-only,
  без sync-шага» для собственных объявлений
  ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) — тем не менее сам факт
  синхронизации его четырёх справочников оказывается на критическом пути
  общего sync-прохода наравне с HANDBOOKS.
- Ни один из четырёх `DataCategory` (`directories`, `animals`, `user`,
  `reports`, `syncReports`, `syncUnsentAnimals`,
  `syncDisposalListService`, `generations`, `generationsTypes` — все 9
  значений) не выделен для BOARD — единственный сохранившийся
  board-специфичный след ошибки — строковый `errorDataKey = 'board'`,
  не завязанный на `enum` и потому не участвующий ни в каком типизированном
  сравнении категорий (например в `updateAndSyncRegagro`).
- Очистка журнала [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) в
  начале «каждого полного прохода» на практике условна: она происходит
  только если проход доходит до `_syncAllData` — то есть только для
  авторизованного пользователя и только если ни один из предшествующих
  шагов (включая сам `_loadBoardDirectories`) не оборвал проход раньше. Этот
  сценарий — пример прохода, который до неё не доходит.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий полностью воспроизводится
статическим чтением кода: `DataUpdateBloc.on<DataUpdateStartAll>` →
`loadDirectories` → `_loadBoardDirectories` → любой из
`BoardAdTypesRepository.syncBoardAdTypes`/`BoardAdStatusesRepository.syncBoardAdStatuses`/
`BoardAttributesRepository.syncBoardAttributes`/`BoardServiceTypesRepository.syncBoardServiceTypes`
→ `CustomDioClient.call`. Возможное исправление (собственный `try/catch`
вокруг `_loadBoardDirectories`, отдельная категория `DataCategory.board`,
раздельные `_emitProgress`-ключи на каждый из четырёх справочников,
отдельный персистентный «последний синк» для BOARD) в рамках этого
документирующего прохода не выполняется — это фиксация уже существующего
кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError`; `finally` сбрасывает оба `ApiClient` независимо от исхода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories` | CURRENT | предшествующий шаг; безусловно сохраняет `AppCacheService.saveDirectoriesLastSyncDate(DateTime.now(), ...)` и пишет успех `_addDataUpdateSuccess(DataCategory.generationsTypes)` независимо от исхода следующего, ещё не начавшегося шага `_loadBoardDirectories` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadBoardDirectories` | CURRENT | предмет сценария — без собственного `try/catch`; единственный вызов `_emitProgress(dataKey: DataKey.board)` не передаёт `dataCategory`, оставляя `_currentDataCategory` тем, что было выставлено `loadDirectories` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | опциональный `dataCategory`: не передан для board — `_currentDataCategory` не переписывается |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `_addDataUpdateError` | CURRENT | пишут строку в `DataUpdates`, используя `_currentDataCategory`/`_currentDataKey` момента краха (`generationsTypes`/`'board'`); эмитят `DataUpdateFailure` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData`, `.updateAndSyncRegagro`, `._syncAllData`, `._clearDataUpdates` | CURRENT | не достигаются в этом сценарии вовсе — журнал `DataUpdates` не очищается в этом проходе |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе; `isAdressesUpdate` остаётся `false` (не передан в `_emitError`) |
| `lib/repositories/board/board_ad_types_repository.dart` | `BoardAdTypesRepository.getBoardAdTypesFromApi`, `.syncBoardAdTypes` | CURRENT | `catch (e, st) { Talker.info(...); rethrow; }` — не различает сетевой сбой и приведение типа |
| `lib/repositories/board/board_ad_statuses_repository.dart` | `BoardAdStatusesRepository.getBoardAdStatusesFromApi`, `.syncBoardAdStatuses` | CURRENT | тот же паттерн |
| `lib/repositories/board/board_attributes_repository.dart` | `BoardAttributesRepository.getBoardAttributesFromApi`, `.syncBoardAttributes` | CURRENT | тот же паттерн |
| `lib/repositories/board/board_service_types_repository.dart` | `BoardServiceTypesRepository.getBoardServiceTypesFromApi`, `.syncBoardServiceTypes` | CURRENT | тот же паттерн |
| `lib/repositories/generations_types_repository/generations_types_repository.dart` | `GenerationsTypesRepository` | CURRENT | справочник, чья категория (`DataCategory.generationsTypes`) ошибочно фиксируется в журнале вместо BOARD (контекст, не предмет отказа) |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey.board` | CURRENT | 9 значений `DataCategory`, ни одно не для BOARD; `DataKey.board = 'board'` — единственный сохранившийся текстовый след |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository.insert` | CURRENT | тонкая обёртка над `BaseRepository`/`BaseDao.ins` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins` | CURRENT | `InsertMode.insertOrReplace`; поскольку `id` не задаётся в `DataUpdatesCompanion`, каждый вызов создаёт новую строку — накопление, не замена |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate`, `.saveDirectoriesLastSyncDate` | CURRENT | единый персистентный «снимок», общий для HANDBOOKS и BOARD; обновляется `loadDirectories` независимо от исхода `_loadBoardDirectories` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`; источник технического отказа во всех четырёх board-репозиториях |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio бросает исключение на любом не-2xx ответе |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | проверяется только после этого шага — определяет, будет ли (в отсутствие отказа) выполнен `_syncAuthData` |
| `lib/pages/data_update/data_update_page.dart` | `_Body.build` | CURRENT | рендерит `errorTitleKey`/`errorMessageKey` через `context.tr(...)` при `DataUpdateFailure` |
| `lib/l10n/app_localization.dart` | `AppLocalizationsExtension.tr` | CURRENT | `switch` без `case 'board'` — попадает в `default: return key;`, показывая нелокализованное слово `board` |
| `lib/pages/main/main_page.dart` | `BlocListener<AuthBloc, AuthState>`, `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | автотриггер (`AuthToMain` → `DataUpdateStartAll`) и открытие `DataUpdatePage` по `DataUpdateInProgress` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`, `lib/pages/in_work/in_work_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | остальные ручные точки запуска прохода |

## Критерии приёмки

- Если внутри `_loadBoardDirectories` любой из четырёх вызовов
  (`syncBoardAdTypes`/`syncBoardAdStatuses`/`syncBoardAttributes`/`syncBoardServiceTypes`)
  бросает исключение, оно не перехватывается ни в `_loadBoardDirectories`,
  ни где-либо между ним и `on<DataUpdateStartAll>` — единственная точка
  перехвата находится там же, где перехватываются все остальные технические
  отказы полного прохода.
- В [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) добавляется ровно
  одна новая строка ошибки с `dataCategoryId = DataCategory.generationsTypes`
  (не `directories`, не любое board-специфичное значение — такого не
  существует) и `errorDataKey = 'board'`.
- `DataUpdateFailure` эмитится с `errorMessageKey = 'board'`; на экране
  `DataUpdatePage` вторая строка сообщения об ошибке отображается как
  нелокализованное слово `board` (нет `case 'board'` в
  `AppLocalizationsExtension.tr`).
- Ни один шаг `_syncAuthData` (фермы/места/взвешивания/`updateAndSyncRegagro`/
  вакцинации/выбытия/отчёты/устройства) не выполняется в этом проходе — ни
  для гостя (это ожидаемо и без отказа), ни для авторизованного пользователя
  (это специфично для этого сценария).
- `_clearDataUpdates()` не вызывается в этом проходе — предыдущее содержимое
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (если было) не
  стирается; обе строки этого прохода (успех `generationsTypes` от
  `loadDirectories`, ошибка `generationsTypes`/`'board'` от этого отказа)
  добавляются поверх него.
- `AppCacheService`'s персистентный `last_directories_sync_date` уже
  перезаписан на «сейчас» к моменту отказа BOARD (см. «Основной поток», шаг
  2) — независимо от исхода `_loadBoardDirectories`; следующий проход
  использует это новое значение как `updatedAtGt` для BOARD, минуя окно,
  которое реально требовалось этому (упавшему) проходу.
- Локальные таблицы тех board-справочников, чей `syncBoardX...()` успел
  выполниться до отказавшего, физически обновлены (`insertAll`/
  `clearAndInsertAll`); справочники после отказавшего — нет; отката первых
  не происходит.

## Связанные тесты

TBD — теста нет. Ни `DataUpdateBloc._loadBoardDirectories`, ни прогон этого
конкретного сценария (исключение одного из четырёх board-репозиториев,
перехват внешним `catch`, запись в `DataUpdates` под категорией
`generationsTypes`) не покрыты тестами — в репозитории нет тестовых файлов
для `BoardAdTypesRepository`/`BoardAdStatusesRepository`/
`BoardAttributesRepository`/`BoardServiceTypesRepository` вовсе
(`find test -iname "*board_ad_types*"` и аналогичные — пусто).

Единственный тест, затрагивающий `DataUpdateBloc`, — `test/blocs/data_update_bloc_test.dart`
— содержит ровно один `blocTest` верхнего уровня (не внутри `group()`),
`blocTest('DataUpdateClear очищает пользовательские данные БД', ...)`,
проверяющий совершенно другое событие (`DataUpdateClear`, очистку
пользовательских данных при логауте), не `DataUpdateStartAll` и никак не
относящийся к board-справочникам. Файл содержит развёрнутый
комментарий-дисклеймер прямо над `void main()`, объясняющий, почему
`DataUpdateStartAll` не покрыт тестом, и он прямо относится к этому
сценарию:

> `DataUpdateBloc` инжектирует >25 репозиториев через поля-геттеры
> `getIt<X>()` (не через конструктор) — конструктору блока нужны ВСЕ они
> зарегистрированы, даже для теста одного простого события.
> `DataUpdateStartAll` (~900 из 1013 строк файла — основной sync pipeline)
> НЕ покрыт юнит-тестом: первая же строка обработчика —
> `await hasNetworkConnection()` (реальный DNS-запрос без DI-точки), дальше
> десятки приватных методов и реальные транзакции `AppDatabase`.
> Осмысленный юнит-тест такого масштаба потребовал бы рефакторинга
> источника под DI — вне рамок написания тестов без изменения кода. См.
> `TESTING_CHECKLIST.md`.

Единственный существующий тест регистрирует моки для всех четырёх
board-репозиториев (`MockBoardAdTypesRepository` и т.д.) в своём `setUp`,
но ни один тест этого файла не настраивает их поведение (успех/исключение)
и не проверяет `_loadBoardDirectories` — регистрация есть только потому, что
без неё не сконструировался бы сам `DataUpdateBloc`.

## Открытые вопросы и ограничения

- **Потенциальная безвозвратная потеря окна синхронизации BOARD.** Поскольку
  персистентный `last_directories_sync_date` — общий для HANDBOOKS и BOARD
  снимок, и он безусловно продвигается вперёд `loadDirectories()` независимо
  от исхода последующего `_loadBoardDirectories`, отказ именно этого шага (в
  отличие от, например, push перемещений/взвешиваний, где несинхронизированные
  строки помечены `sync == false` и переотправляются на следующем проходе
  целиком, [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md),
  [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)) не имеет
  механизма повтора именно пропущенного окна: следующий проход спросит
  сервер про board-справочники начиная с **нового**, уже продвинутого
  момента, а не с того, который в этом проходе реально не удалось
  обработать. Если сервер за это окно успел изменить/добавить строки
  какого-либо из четырёх board-справочников, эти изменения не будут получены
  клиентом никогда, ни на одном будущем проходе, если только сервер не
  обслуживает `updated_at_gt` неточно (не проверено — вне зоны видимости
  клиентского кода). Является ли это осознанным компромиссом (переиспользовать
  один и тот же временной снимок ради простоты) или недосмотром при
  добавлении BOARD к уже существующему HANDBOOKS-шагу — ничем в коде/
  комментариях не зафиксировано.
- **Отсутствие отдельной `DataCategory` для BOARD — по всей видимости,
  такое же упущение, как и известная путаница `directories`/`generationsTypes`,
  описанная в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).** Doc-
  комментарий `enum DataCategory` явно запрещает вставлять новые значения не
  в конец (`ДОБАВЛЯТЬ ПЕРЕЧИСЛЕНИЯ МОЖНО ТОЛЬКО С КОНЦА»), но нового значения
  для BOARD, добавленного вместе с `board_ad_types`/`board_ad_statuses`/
  `board_attributes`/`board_service_types` (миграция `from < 79`, см.
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), в итоге так и не появилось —
  сам факт синхронизации BOARD-справочников оказался «бездомным» с точки
  зрения типизированной категории, хотя `DataKey.board` (текстовая константа)
  для него всё же был заведён.
- **По журналу невозможно определить, какой конкретно из четырёх
  board-справочников не синхронизировался** — единственный `_emitProgress(dataKey: DataKey.board)`
  вызывается один раз перед всеми четырьмя, в отличие от каждого
  HANDBOOKS-справочника внутри `loadDirectories()`, у которого свой
  собственный `DataKey`. Осознанное упрощение или недосмотр — не
  зафиксировано.
- **Очистка [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) в начале
  «каждого полного прохода» на практике условна**, а не безусловна, как
  можно прочитать в общем описании сущности: она достижима только если
  проход доходит до `_syncAllData`. Гостевые проходы никогда её не достигают
  (`_syncAuthData` для гостя не вызывается вовсе), и любой авторизованный
  проход, упавший раньше `_syncAuthData` (как этот сценарий), тоже. Отсюда —
  потенциальное неограниченное накопление строк в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) при повторяющихся
  гостевых или рано обрывающихся авторизованных проходах, не зафиксированное
  в самой сущности как отдельный инвариант.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DataUpdateBloc.on<DataUpdateStartAll>` →
  `loadDirectories` → `_loadBoardDirectories` → `BoardAdTypesRepository.syncBoardAdTypes`
  (и три аналогичных) → `CustomDioClient.call` → `DioClient`), включая
  предположение о том, что `${Constants.boardServiceApi}/...` может отказать
  независимо от соседних HANDBOOKS-эндпоинтов того же прохода — тот же класс
  предположения, что уже сделан и помечен неподтверждённым в
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) для
  `${Constants.boardServiceApi}/countries`.
