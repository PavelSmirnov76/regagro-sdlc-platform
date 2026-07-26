# UC-127 — Система перезагружает кэш отчётов о выбытии/инвентаризации с сервера сразу после push, окно «последний год — завтра»

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь (сам
факт запуска прохода специфицируется будущим модулем SYSTEM, см.
[MOD-4](../modules/MOD-4-ANIMAL.md), «Граница» — не здесь) — сразу после
push-шага ещё не отправленных сессий сканирования
([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)),
**независимо от исхода этого push на уровне содержимого ответа** — система
запрашивает у сервера список отчётов (`GET /get-animal-exits`) за окно
«последний год — завтра» и целиком заполняет заново уже опустошённый локальный
кэш `ReportAnimals` (таблица-читалка [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
используемая экранами отчёта по инвентаризации/дню и сводкой фермы). Этот шаг
выполняется на каждом полном sync-проходе безусловно, независимо от того, было
ли вообще что отправлять push-шагом.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода (`DataUpdateBloc`), без участия пользователя в момент именно этого
шага. Проход инициирован раньше [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)/пользователем
приложения (`DataUpdateStartAll`) — этот файл не про инициирование, а про сам
шаг перезагрузки.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, и `_authRepository.isAuthorized()` истинно — иначе `_syncAuthData`
   не вызывается вовсе (вне границ этого файла).
2. `_syncAuthData` выполняет по порядку: `_deletePlacesFromRDS()` →
   `_syncFarms()` → `_syncPlaces()` →
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` → `await
   updateAndSyncRegagro(event, emit)` — и только затем `await
   updateAndSyncSHTP(event, emit)`, начало сценария этого файла.
3. `updateAndSyncRegagro` заранее (внутри собственной ветки `_syncAllData`)
   уже отправляет/подтягивает животных, перемещения, вакцинации, выбытия —
   не предмет этого файла (см. [UC-91](UC-91-ACTOR-4-EVT-46-ENT-15-READ_OK-IN-ANIMAL.md),
   [UC-107](UC-107-ACTOR-4-EVT-54-ENT-16-READ_OK-IN-ANIMAL.md)). Он
   возвращается в `_syncAuthData` **без исключения** во всех наблюдаемых
   ветках, включая ветки, где он сам эмитит `DataUpdateFailure` и просто
   `return`/выходит из своего `if` (см. «Альтернативные потоки» — узкий
   race-сценарий) — `_syncAuthData` не проверяет никакой возвращаемый
   признак успеха/неуспеха и безусловно продолжает следующей строкой.
4. `updateAndSyncSHTP(event, emit)`:
   - `_emitProgress(dataKey: DataKey.syncReports, dataCategory:
     DataCategory.syncReports)`;
   - `unsentReportAnimals = await _unsentReportsRepository.getAllReadyToSend()`
     — все строки `UnsentReportAnimals` с `readyToSend == true`, без фильтра
     по `type` (не только инвентаризация — общий метод для всех значений
     `way_type`, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md));
   - если список непуст — `await _unsentReportsRepository.sync(unsentReportAnimals)`
     ([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md),
     `POST /exit-event`); `sync()` **не проверяет** `response['status']` —
     только логирует ответ (`log('response: $response')`) — поэтому
     содержательный отказ сервера (тело с `status: 'error'`) не бросает
     исключение и не отличается по дальнейшему поведению от содержательного
     успеха;
   - **безусловно**, независимо от того, был ли список пуст и каким было
     содержимое ответа push-запроса (лишь бы не было брошено исключение) —
     `await _reportsRepository.clear()`: `BaseRepository.clear()` →
     `ReportAnimalsDao.clear()` (унаследовано от `BaseDao.clear()`) —
     `(delete(_currentTableInfo)).go()` удаляет **все** строки `ReportAnimals`
     целиком, без фильтра по `type`/`sessionUuid`/чему-либо ещё;
   - затем `await _unsentReportsRepository.deleteAllReadyToSend()` — удаляет
     все строки `UnsentReportAnimals` с `readyToSend == true` (опять же без
     фильтра по `type`);
   - затем `await loadShtp(emit)` — предмет этого файла.
5. `loadShtp(emit)`:
   - `_emitProgress(dataKey: DataKey.reports, dataCategory:
     DataCategory.reports)` — переключает `_currentDataCategory` на
     `DataCategory.reports` (влияет на то, куда будет записана ошибка, если
     она случится ниже, — см. «Альтернативные потоки»);
   - `reports = await _reportsRepository.getReportsFromApi()` — без аргумента
     `startTime`;
   - `await _reportsRepository.insertAll(reports)`;
   - `await _addDataUpdateSuccess(_currentDataCategory)` — добавляет строку в
     `DataUpdates` (`dataCategoryId: DataCategory.reports`, `updatedAt:
     DateTime.now()`) безусловно, независимо от того, был ли `reports` пуст.
6. `ReportAnimalsRepository.getReportsFromApi({DateTime? startTime})`: `end` =
   завтрашняя дата (`DateTime.now().add(Duration(days: 1))`,
   `DateFormat('yyyy-MM-dd')`), `start` = `startTime ?? (DateTime.now().subtract(Duration(days:
   365)))` (та же форма). Единственный вызывающий код (`loadShtp`) никогда не
   передаёт `startTime` — окно всегда «последний год — завтра».
7. Строится `ApiMessage(link: '${Constants.farmServiceApi}/get-animal-exits',
   method: ApiMethod.get, data: {'start_date': start, 'end_date': end})`;
   `rpcClientSHTP = getIt.get<ApiClient>(instanceName: 'farm_rpc')`; `response
   = await rpcClientSHTP.call(message)`.
8. `CustomDioClient.call` (единственная реализация `ApiClient` в проде) — при
   успешном HTTP-ответе с телом-`Map`, содержащим ключ `animal_exits` (форма,
   которую и ожидает этот эндпоинт), безусловно принудительно выставляет
   `response.data['status'] = "1"` и возвращает тело как есть — **вне
   зависимости от какого-либо содержательного признака успеха в самом
   ответе**. Это не имеет значения для данного шага, поскольку
   `getReportsFromApi` вообще не читает `response['status']` ни в каком виде
   — статус ответа для этого запроса не проверяется никем.
9. `animals = (response['animal_exits'] as List).map((e) =>
   _fromJson(e)).toList()` — приведение типа без try/catch на этом уровне
   (см. «Альтернативные потоки»).
10. `_fromJson(json)` строит `ReportAnimal(id: json['id'], transponderId:
    json['transponder_id'] ?? json['number'], regagroId: json['regagro_id'],
    type: json['way_type'], time: DateTime.parse(json['way_date']), farmId:
    json['farm_id'], placeId: json['place_id'], sessionUuid: json['uuid'] as
    String?)` для каждого элемента ответа — **без фильтрации по `type`**:
    любые значения `way_type`, которые вернул сервер (не только
    `'inventory'`), попадают в результат и далее в таблицу. Примечательно:
    `ReportAnimals.id` объявлена как `integer().autoIncrement()` в схеме
    (`packages/sheep_farm_database/lib/entities/reports_animals/report_animals.dart`),
    но `_fromJson` явно выставляет `id` из серверного `json['id']` — локальный
    `id` этой строки на практике всегда равен серверному id записи, а не
    клиентскому автоинкременту.
11. `await _reportsRepository.insertAll(reports)` → `BaseRepository.insertAll`
    → `dao.insAll(reports)` → `BaseDao.insAll` — единый drift `batch(...)`:
    `batch.insertAll(_currentTableInfo, reports, mode:
    InsertMode.insertOrReplace)`. Поскольку `_reportsRepository.clear()` уже
    безусловно опустошил таблицу на шаге 4 (до вызова `loadShtp`), на
    практике эта вставка не заменяет существующие строки, а создаёт таблицу
    заново с нуля из ответа этого запроса — `insertOrReplace` здесь ничего не
    заменяет, коллизий id по построению нет.
12. Если `insertAll` не бросил исключение — `loadShtp` возвращается,
    `updateAndSyncSHTP` завершается, `_syncAuthData` продолжает:
    `_emitProgress(dataKey: DataKey.syncDevices)`, `await _suncDevices()`. При
    отсутствии независимых сбоев дальше по проходу `on<DataUpdateStartAll>`
    в итоге эмитит `DataUpdateSuccess(resetNavigationOnSuccess:
    event.resetNavigationOnSuccess)`.

### Альтернативные потоки

- **Push (шаг 4) не бросил исключение, но логически отказал (`status:
  'error'` в теле ответа `POST /exit-event`).** Поскольку `sync()` не
  проверяет `response['status']` вообще, этот случай неотличим по
  дальнейшему поведению от логического успеха push — `clear()`,
  `deleteAllReadyToSend()` и `loadShtp()` выполняются точно так же. Именно
  это имеется в виду формулировкой «независимо от исхода push на уровне
  контента ответа» в «Назначении» — данный use-case наступает в обоих
  случаях одинаково.
- **Push (шаг 4) бросил сетевое исключение.** Если `_unsentReportsRepository.sync(...)`
  бросает исключение (например, `CustomDioClient.call`
  перехватывает и безусловно перебрасывает — `rethrow` — любую сетевую
  ошибку), оно всплывает через `updateAndSyncSHTP` (нет собственного
  `try/catch` вокруг вызова `sync`) → `_syncAuthData` → до внешнего
  `try/catch` в `on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure`
  и завершает **весь** проход ошибкой. `clear()`, `deleteAllReadyToSend()` и
  `loadShtp()` в этом случае **не выполняются вовсе** — событие
  [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md)
  в этом проходе не наступает. Не этот файл.
- **Список `readyToSend` пуст.** `_unsentReportsRepository.sync(...)` не
  вызывается вовсе (гейт `if (unsentReportAnimals.isNotEmpty)`), но `clear()`,
  `deleteAllReadyToSend()` и `loadShtp()` всё равно выполняются безусловно
  следующими строками того же метода — этот шаг (и, соответственно,
  [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md))
  наступает на **каждом** полном sync-проходе, независимо от того, было ли
  вообще что отправлять.
- **Пустой ответ сервера (`animal_exits: []`).** `insertAll([])` — no-op;
  `_addDataUpdateSuccess` всё равно вызывается. В отличие от аналогичного
  pull-шага Disposal
  ([UC-107](UC-107-ACTOR-4-EVT-54-ENT-16-READ_OK-IN-ANIMAL.md), где пустой
  ответ **не трогает** предыдущее содержимое таблицы, потому что там нет
  безусловной предварительной очистки перед проверкой пустоты ответа) —
  здесь таблица `ReportAnimals` к этому моменту уже безусловно опустошена
  шагом 4 (`clear()`, до `loadShtp`), поэтому пустой ответ оставляет кэш
  реально, а не формально, пустым до следующего успешного полного прохода.
  Тот же `RESULT` (`READ_OK`), не отдельный use-case.
- **Исключение внутри `getReportsFromApi`/`_fromJson`/`insertAll`** (сетевой
  сбой самого `GET`-запроса, `TypeError` при `response['animal_exits'] as
  List`, если ключ отсутствует или имеет другую форму, ошибка
  `DateTime.parse(json['way_date'])` при некорректной дате, либо ошибка типа
  при конструировании `ReportAnimal` с `id: null`, если сервер не прислал
  `id` для элемента). Ни `getReportsFromApi`, ни `_fromJson`, ни `loadShtp`
  не оборачивают это в `try/catch` — исключение всплывает через
  `updateAndSyncSHTP` → `_syncAuthData` → до внешнего `try/catch` в
  `on<DataUpdateStartAll>`, обрывая **весь** проход `DataUpdateFailure`.
  Точно так же, как отмечено в самом
  [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  локальный кэш `ReportAnimals` к этому моменту уже пуст (очищен шагом 4) и
  остаётся пустым до следующего успешного полного прохода — экраны,
  читающие из него, в это окно показывают меньше данных, чем есть на
  сервере. `RESULT = READ_ERROR`, не этот файл (отдельный use-case на этот
  путь на момент написания не заведён).
- **Узкий race в `updateAndSyncRegagro`, предшествующем этому шагу.**
  `updateAndSyncRegagro` заново проверяет сеть
  (`NetworkConnectivityService.hasConnection()`, независимо от проверки в
  самом начале `on<DataUpdateStartAll>`) и в трёх internal-ветках
  (`errorDataUpdates.isNotEmpty && !isNetworkConnected` → `emit(DataUpdateFailure(...));
  return;`, и ещё две ветки `else { emit(DataUpdateFailure(...)); }` без
  `return`, при отсутствии сети на момент повторной проверки) эмитит
  `DataUpdateFailure`, **не бросая исключения** — метод в любом случае
  возвращается нормально. `_syncAuthData` не проверяет никакой признак
  результата этого вызова и безусловно продолжает следующей строкой —
  `await updateAndSyncSHTP(event, emit)`, то есть этот шаг (и `GET
  .../get-animal-exits`) реально выполняется **даже после того, как в этом
  же проходе уже был эмитирован `DataUpdateFailure`**. Если сеть после этого
  момента восстановилась (или флаг `hasConnection()` был неточен), проход
  может в итоге дойти до финального `emit(DataUpdateSuccess(...))`, и в
  стриме состояний бывший ранее `DataUpdateFailure` окажется перекрыт более
  поздним `DataUpdateSuccess`. Не проверялось на практике (частота
  реального попадания в это окно), не разбирается глубже здесь.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport, половина `ReportAnimals`) — сущность, совершающая
  переход этого файла: таблица `ReportAnimals` полностью заменяется
  (`clear()`, выполненный шагом раньше в `updateAndSyncSHTP`, затем
  `insertAll` внутри `loadShtp`) содержимым ответа `GET /get-animal-exits`;
  без построчного diff/merge с предыдущим содержимым. Реплицирует не только
  строки типа `'inventory'` (единственный реально достижимый тип, см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), «Инварианты»),
  но любые значения `way_type`, которые вернул сервер.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим шагом; `regagroId` каждой сохранённой строки берётся из
  серверного `json['regagro_id']` как есть, без сопоставления/валидации
  против локальной таблицы `Animals`. Сопоставление метка↔животное для
  отображения по-прежнему вычисляется отдельно, на клиенте, через
  [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md) (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), «Связи»).
- `UnsentReportAnimals` (черновая половина той же сущности [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md))
  — не читается этим шагом напрямую, но её `readyToSend == true` строки уже
  безусловно удалены предыдущим шагом того же метода
  (`deleteAllReadyToSend()`), независимо от исхода push на уровне контента.
- Нижестоящие потребители перезагруженного кэша `ReportAnimals` (не читают
  и не пишут этим шагом, но их корректность зависит от его результата):
  `MainNavigatorCubit.load` (`lib/pages/main_navigator/cubit/main_navigator_cubit.dart`,
  через `ReportAnimalsRepository.getReportsByFarmId`, сводка «за год» на
  экране фермы), `ReportsDayDataLoader.load`
  (`lib/pages/reports_day_list/data/reports_day_data_loader.dart`, посуточный
  список отчётов) и `InventoryReportDetailsCubit.load`
  (`lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart`,
  экран итогового отчёта по сессии/дню — объединяет эти строки с ещё не
  отправленными сессиями из `UnsentReportAnimals`, [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)).

### Бизнес-правила

- Этот шаг наступает на **каждом** полном sync-проходе (при
  `isAuthorized()`), безусловно и независимо от того, был ли непустым список
  `readyToSend` на предыдущем шаге и каким было содержимое ответа push-а —
  единственное, что предотвращает его целиком, это брошенное исключение на
  более раннем шаге того же прохода (см. «Альтернативные потоки»).
- Окно запроса — всегда «последний год — завтра»; параметр `startTime` у
  `getReportsFromApi` существует в сигнатуре, но единственный вызывающий код
  (`loadShtp`) никогда не передаёт для него значение — инкрементальная
  загрузка с явной даты технически поддерживается сигнатурой, но нигде не
  используется.
- Статус ответа (`response['status']`) для этого запроса **не проверяется
  вообще** — `getReportsFromApi` безусловно читает `response['animal_exits']`
  напрямую; сам `CustomDioClient` в любом случае форсирует `status: "1"` для
  тела с ключом `animal_exits`, так что даже гипотетическая проверка статуса
  здесь была бы бессмысленна для этого конкретного эндпоинта.
- Замена «всё или ничего»: перед вызовом `getReportsFromApi` таблица
  `ReportAnimals` уже безусловно опустошена (`clear()` в `updateAndSyncSHTP`,
  до `loadShtp`) — в отличие от аналогичного pull-шага Disposal
  ([UC-107](UC-107-ACTOR-4-EVT-54-ENT-16-READ_OK-IN-ANIMAL.md)), где
  `clear()`/`insAll()` оба условны на непустоте ответа и выполняются единой
  парой внутри самого pull-метода. Здесь `clear()` не зависит от содержимого
  ответа вообще — он вызывается раньше и безусловно, поэтому пустой ответ
  оставляет кэш реально пустым, а не «как было до прохода».
- Локальный `id` каждой строки `ReportAnimal` — это id, присланный сервером
  (`json['id']`), явно переданный в конструктор, несмотря на то что колонка
  схемы объявлена как `integer().autoIncrement()`.
- `insertAll`/`insAll` выполняется в режиме `InsertMode.insertOrReplace`, но
  поскольку таблица уже пуста к этому моменту, на практике происходит
  чистая вставка, а не замена существующих строк.
- Строка `DataUpdates` (`dataCategoryId: DataCategory.reports`) добавляется
  безусловно после `insertAll`, независимо от того, был ли ответ пуст.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и воспроизводится статическим
чтением кода целиком (`DataUpdateBloc.updateAndSyncSHTP` → `loadShtp` →
`ReportAnimalsRepository.getReportsFromApi`/`insertAll`). Находки, перечисленные
в «Открытые вопросы и ограничения» (в частности, узкий race в
`updateAndSyncRegagro` и отсутствие проверки статуса ответа), не блокируют
успешный основной поток, документируемый здесь.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + единственный внешний `try/catch` всего прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | задаёт порядок: фермы/места → взвешивания (push) → `updateAndSyncRegagro` → `updateAndSyncSHTP` (предмет этого файла) → синхронизация устройств; не проверяет исход `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | предшествующий шаг того же прохода; может эмитить `DataUpdateFailure` и вернуться без исключения — `_syncAuthData` всё равно продолжает дальше (см. «Альтернативные потоки») |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP` | CURRENT | ядро оркестрации: push (если непусто) → безусловный `clear()` кэша → безусловный `deleteAllReadyToSend()` → `loadShtp` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadShtp` | CURRENT | предмет use-case: `getReportsFromApi` → `insertAll` → `_addDataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress`, `_addDataUpdateSuccess` | CURRENT | эмит прогресса (переключает `_currentDataCategory`/`_currentDataKey`) и запись успеха в `DataUpdates` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsFromApi` | CURRENT | `GET .../get-animal-exits`, окно «последний год — завтра» (`startTime` не используется вызывающим кодом), без проверки `response['status']` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository._fromJson` | CURRENT | маппинг JSON → `ReportAnimal`; `id` явно берётся из серверного `json['id']`, без фильтра по `type` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsByFarmId`, `.getInventoryReports`, `.getInventoryReportsByDate`, `.getInventoryReportsByUuid`, `.getByTransponderId` | CURRENT | нижестоящие read-методы того же репозитория, читающие перезагруженный этим шагом кэш |
| `lib/repositories/base_repository.dart` | `BaseRepository.insertAll`, `.clear` | CURRENT | делегируют в `dao.insAll`/`dao.clear` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll`, `.clear` | CURRENT | `insAll` — один `batch.insertAll(..., mode: InsertMode.insertOrReplace)`; `clear` — `delete(_currentTableInfo).go()`, без фильтра |
| `packages/sheep_farm_database/lib/entities/reports_animals/report_animals.dart` | `ReportAnimals`, `ReportAnimal` | CURRENT | таблица/модель кэша; `id` — `integer().autoIncrement()`, фактически перезаписывается серверным значением при вставке через `_fromJson` |
| `packages/sheep_farm_database/lib/entities/reports_animals/report_animals_dao.dart` | `ReportAnimalsDao.getAllByFilters` | CURRENT | используется нижестоящими read-методами репозитория, не этим шагом напрямую |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.sync`, `.getAllReadyToSend`, `.deleteAllReadyToSend` | CURRENT | предшествующий push-шаг ([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)) и безусловная очистка `readyToSend`-строк перед этим шагом |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | принудительно форсирует `status: "1"` для тела с ключом `animal_exits`; логирует и `rethrow` любое сетевое исключение |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/get-animal-exits` |
| `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` | `MainNavigatorCubit.load` | CURRENT | нижестоящий потребитель перезагруженного кэша (сводка фермы «за год») |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | нижестоящий потребитель (посуточный список отчётов) |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | нижестоящий потребитель (итоговый отчёт по сессии/дню, [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)); читает не реактивно, разово при открытии экрана |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети, на каждом
  полном sync-проходе (`_syncAuthData` дошла до `updateAndSyncSHTP`) без
  брошенного ранее исключения выполняется ровно один запрос `GET
  .../get-animal-exits?start_date=...&end_date=...` с окном «последний год —
  завтра», независимо от того, был ли непустым список `readyToSend` и каким
  было содержимое ответа предшествующего push-запроса.
- К моменту этого запроса локальная таблица `ReportAnimals` уже полностью
  опустошена (`clear()`, выполненный раньше в `updateAndSyncSHTP`) — этот шаг
  не сравнивает ответ с предыдущим содержимым таблицы.
- Если ответ содержит непустой массив `animal_exits`, каждый элемент
  сохраняется в `ReportAnimals` через `insertAll`/`insAll` с локальным `id`,
  равным `json['id']` из ответа, и без фильтрации по `type`/`way_type`.
- Если массив `animal_exits` пустой, `insertAll([])` не создаёт ни одной
  строки — таблица `ReportAnimals` остаётся пустой до следующего успешного
  полного прохода.
- После `insertAll` (независимо от того, был ли ответ пуст) в `DataUpdates`
  добавляется ровно одна строка с `dataCategoryId: DataCategory.reports`.
- Любое исключение внутри `getReportsFromApi`/`_fromJson`/`insertAll` не
  перехватывается на этом уровне и прерывает весь sync-проход
  (`DataUpdateFailure`), оставляя `ReportAnimals` пустой до следующего
  успешного полного прохода — другой `RESULT` (`READ_ERROR`), не
  описываемый этим файлом.

## Связанные тесты

TBD — теста нет. Ни `ReportAnimalsRepository` (нет тестового файла вовсе — `find
test -iname "*report_animals*"` находит только
`test/repositories/unsent_report_animals_repository_test.dart`, покрывающий
`UnsentReportAnimalsRepository` — push-сторону, [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md),
не pull), ни путь `DataUpdateBloc.updateAndSyncSHTP`/`loadShtp` тестами не
покрыты.

`test/blocs/data_update_bloc_test.dart` регистрирует `MockReportAnimalsRepository`
в `getIt` (нужно для конструирования `DataUpdateBloc` в принципе), но не
стабит и не проверяет ни один его метод — единственные два теста файла
(`'DataUpdateBloc конструируется с полным набором зависимостей из getIt'` и
`blocTest` на `DataUpdateClear`) не затрагивают `on<DataUpdateStartAll>`
вообще. Это явно и честно зафиксировано комментарием в самом файле теста
(строки перед `void main()`): `DataUpdateStartAll` (~900 из 918 строк файла)
не покрыт юнит-тестом, поскольку первая же строка обработчика делает реальный
DNS-запрос (`hasNetworkConnection()`) без DI-точки для мока, а дальше идут
десятки приватных методов и реальные транзакции `AppDatabase` — осмысленный
юнит-тест такого масштаба потребовал бы рефакторинга источника под DI, что вне
рамок написания тестов без изменения кода (см. `TESTING_CHECKLIST.md`).

## Открытые вопросы и ограничения

- **Молчаливое отсутствие проверки содержательного исхода push перед pull.**
  `updateAndSyncSHTP` не различает «push прошёл успешно», «push логически
  отказал (`status: 'error'`, без исключения)» и «push вообще не вызывался,
  потому что нечего было отправлять» — во всех трёх случаях `clear()` →
  `deleteAllReadyToSend()` → `loadShtp()` выполняются одинаково. Если push
  логически отказал, локальные `readyToSend`-строки всё равно удаляются
  (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  «Push не проверяет тело ответа сервера») — данные скана теряются
  безвозвратно ещё до этого шага; сам этот шаг лишь перезагружает то, что
  реально есть на сервере, никак не компенсируя такую потерю.
- **Исключение внутри `getReportsFromApi` оставляет кэш пустым до следующего
  прохода.** Как отмечено и в самом
  [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  поскольку `clear()` выполняется раньше и безусловно (в `updateAndSyncSHTP`,
  до `loadShtp`), сбой именно pull-запроса — единственный путь, оставляющий
  `ReportAnimals` пустой на неопределённое время (до следующего успешного
  полного прохода), а не просто прерывающий обновление данных. Экраны,
  зависящие от этого кэша (`MainNavigatorCubit`, `ReportsDayDataLoader`,
  `InventoryReportDetailsCubit`), в это окно показывают меньше данных, чем
  есть на сервере, без какого-либо явного индикатора этого состояния на
  самих этих экранах.
- **Узкий race в `updateAndSyncRegagro`.** Как отмечено в «Альтернативные
  потоки», внутренняя повторная проверка сети в `updateAndSyncRegagro` может
  эмитить `DataUpdateFailure`, не прерывая исполнение — этот шаг (и весь
  остаток прохода) всё равно выполняется следующей строкой. Не проверялось,
  насколько часто в реальных условиях сеть успевает измениться между двумя
  проверками одного и того же прохода; не разбирается глубже здесь.
- **`id`, явно скопированный из серверного ответа поверх колонки
  `autoIncrement()`.** Если сервер когда-либо вернёт `animal_exits` без поля
  `id` для какого-то элемента (или с `null`), конструктор `ReportAnimal`
  получит `id: null` для не-nullable колонки — не проверялось, какая именно
  ошибка типа при этом возникает и перехватывается ли она где-либо выше по
  стеку (по чтению кода — нет, это тот же необработанный путь исключения,
  что и остальные ошибки парсинга на этом шаге).
- **Отсутствие фильтрации по `type` при пересборке кэша.** И `clear()`, и
  вставка через `_fromJson` не ограничивают себя `way_type == 'inventory'` —
  если сервер когда-либо вернёт строки с `way_type` `'output'`/`'input'`
  (легаси-типы, недостижимые из UI приложения, см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  «Инварианты»), они будут сохранены в `ReportAnimals` наравне с
  `'inventory'` и попадут в выборки `getReportsByFarmId`/`getByTransponderId`
  (не фильтрующие по `type`), хотя не попадут в `getInventoryReports*`
  (которые фильтруют). Не проверялось, возвращает ли реальный сервер такие
  строки на практике.
- **Нижестоящие потребители не реактивны.** `MainNavigatorCubit.load`,
  `ReportsDayDataLoader.load` и `InventoryReportDetailsCubit.load` читают
  `ReportAnimals` разово при открытии/явной перезагрузке экрана, не через
  `watchAll()`/реактивный поток — если такой экран уже открыт в момент этого
  sync-шага, перезагруженные данные не отразятся в нём немедленно.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим
  чтением кода (`DataUpdateBloc.updateAndSyncSHTP` → `loadShtp` →
  `ReportAnimalsRepository.getReportsFromApi` → `CustomDioClient.call`),
  включая точную форму ответа `GET /get-animal-exits`, — реальный контракт
  этого эндпоинта со стороны сервера этой спекой не верифицирован.
