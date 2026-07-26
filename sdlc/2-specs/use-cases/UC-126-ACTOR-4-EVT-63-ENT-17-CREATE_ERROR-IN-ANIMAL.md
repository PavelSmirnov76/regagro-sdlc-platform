# UC-126 — Sync push инвентаризации отказывает: сетевое исключение сохраняет данные, логический отказ сервера удаляет их безвозвратно

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md) —
`UnsentReportAnimalsRepository.sync` отправляет одним batch-запросом все
строки `UnsentReportAnimals` с `readyToSend == true` (любого `way_type`, не
только `'inventory'` — `getAllReadyToSend()` не фильтрует по типу). Здесь сам
сетевой вызов внутри `sync()` заканчивается неуспехом одним из двух путей,
каждый проверен отдельно чтением кода и ведущий к принципиально разным
последствиям:

- (а) `rpcClient.call(message)` бросает исключение — внутри `sync()` нет
  вообще никакого `try/catch`, исключение всплывает наружу из метода,
  обрывает `DataUpdateBloc.updateAndSyncSHTP` **до** строк
  `_reportsRepository.clear()`/`_unsentReportsRepository.deleteAllReadyToSend()` —
  они просто не достигаются, локальные ready-строки остаются нетронутыми;
- (б) `rpcClient.call(message)` возвращает обычный (не бросающий исключение)
  ответ с телом `{"status": "error", ...}` (HTTP 200) — `sync()` не читает
  `response['status']` вообще ни одним условием (в отличие от взвешиваний,
  [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md), где хотя бы
  есть `if` без `else` — здесь нет даже этого), только
  `log('response: $response')` через `dart:developer` (не `Talker`, не виден
  нигде в UI, только в консоли отладки/DevTools) — метод завершается
  штатно, без исключения. `updateAndSyncSHTP` продолжает **безусловно**:
  `_reportsRepository.clear()` (весь кэш `ReportAnimals`, все типы) и
  `_unsentReportsRepository.deleteAllReadyToSend()` (все `readyToSend ==
  true` строки, все типы) выполняются, как при настоящем успехе — **данные
  сканирования теряются безвозвратно**: не остаются ни в
  `UnsentReportAnimals` (строки удалены), ни в `ReportAnimals` (кэш очищен, а
  последующий pull ничего не вернёт — сервер эти строки не принял).

В обоих случаях наблюдаемый пользователем итог принципиально разный: (а)
весь sync-проход явно проваливается (`DataUpdateFailure`), данные сохранены
и будут отправлены повторно; (б) проход штатно завершается
`DataUpdateSuccess`, но данные инвентаризации потеряны без какого-либо
сообщения об этом где-либо в приложении.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет — проход был запущен ранее авторизованным пользователем
(`DataUpdateStartAll`, диспатчится, например, из `main_page.dart` (кнопка
обновления навбара), `profile_settings_view.dart`, `in_work_page.dart` или
`data_update_page.dart`) — дальше проход идёт автоматически, без участия
пользователя на уровне отдельного сетевого вызова, как и описано в
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Сами строки, которые здесь не
удаётся отправить (или отправляются, но теряются), были записаны раньше и
локально [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — сессия
сканирования, завершённая через `ScanningBloc.on<ScanningEventSave>`
([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)),
пометившая строки сессии `readyToSend = true`. ACTOR-5 не участвует в самом
sync-шаге, только в исходном создании отправляемых данных.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети и загрузки
   справочников, при `_authRepository.isAuthorized()`, вызывается
   `_syncAuthData(event, emit)`.
2. `_syncAuthData` последовательно вызывает `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`, `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro(event, emit)` (в этом сценарии все они завершаются
   без ошибки, независимой от этого сценария), затем
   `await updateAndSyncSHTP(event, emit)` — **без собственного** `try/catch`
   вокруг этого вызова: весь расчёт на то, что нижестоящий код сам
   обработает свои ошибки (здесь этого не происходит, см. ниже).
3. `updateAndSyncSHTP`: `_emitProgress(dataKey: DataKey.syncReports,
   dataCategory: DataCategory.syncReports)` — фиксирует `_currentDataCategory
   = DataCategory.syncReports`, `_currentDataKey = 'syncReports'` (важно для
   шага 9); `unsentReportAnimals = await _unsentReportsRepository.getAllReadyToSend()` —
   `UnsentReportAnimalsDao.getAllByFilters(readyToSend: true)`, **без
   фильтра по типу** — в батч попадают все строки любого `way_type` с
   `readyToSend == true` разом, не только `'inventory'`. В этом сценарии
   список непуст и включает хотя бы одну строку инвентаризационной сессии,
   завершённой ранее через [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md).
4. `if (unsentReportAnimals.isNotEmpty) await _unsentReportsRepository.sync(unsentReportAnimals);` —
   вызов **не обёрнут** в `try/catch` на этом уровне тоже.
5. Внутри `UnsentReportAnimalsRepository.sync(reports)`: строится
   `allAnimals` (объединение `getAllAnimalsWithDetailsByFilters()` и
   `getAllLocalAnimalsWithDetailsByFilters()`), затем для каждой строки —
   элемент payload'а `{'transponder_id', if regagroId != null 'animal_id',
   'number', 'way_type', 'way_date', 'farm_id', 'place_id', if sessionUuid !=
   null 'uuid'}` (`animal_id` резолвится по совпадению `transponderId` с
   активной идентификацией животного, передаётся только если найден); тело —
   `{'animal_exits': [...]}`, `POST ${Constants.farmServiceApi}/exit-event`.
   **Ни одна строка этого метода не находится внутри `try` — во всём методе
   нет ни одного `try/catch`.**
6. `final rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc'); final
   response = await rpcClient.call(message);` — именно здесь начинается
   развилка этого сценария (обе ветки проверены отдельно чтением кода).

**Ветка (а) — сетевое исключение.**

7а. `CustomDioClient.call` (`lib/network/api_client/custom_dio_client.dart`)
    оборачивает `AuthInterceptor.getTokenDataByPath` и `dio.request(...)`
    собственным `try/catch`: любое исключение (сеть недоступна, таймаут,
    обрыв соединения, либо любой не-2xx HTTP-ответ — `DioClient`
    (`lib/network/dio_client.dart`) не переопределяет `validateStatus`,
    поэтому Dio по умолчанию бросает `DioException` вне 200–299) логируется
    через `getIt.get<Talker>().error('CustomDioClient: call: $e')` и
    безусловно перебрасывается (`rethrow`).
8а. Это исключение всплывает прямо из `await rpcClient.call(message)` на
    шаге 6. Поскольку `sync()` не содержит `try/catch` вообще, исключение
    покидает `sync()` необработанным.
9а. Оно же покидает `if (unsentReportAnimals.isNotEmpty) await
    _unsentReportsRepository.sync(...)` на шаге 4 — этот вызов тоже без
    собственного перехвата — и, следовательно, весь `updateAndSyncSHTP`:
    строки `await _reportsRepository.clear();` и `await
    _unsentReportsRepository.deleteAllReadyToSend();` (после `if`, вне его
    тела) **не достигаются**, `loadShtp(emit)` тоже не вызывается.
10а. Исключение всплывает из `updateAndSyncSHTP` через `_syncAuthData` (шаг 2,
    тоже без перехвата) до единственного внешнего `try/catch` —
    `on<DataUpdateStartAll>` (шаг 1): `catch (error, stackTrace) {
    getIt<Talker>().error('Возникла при обновлении данных $error
    $stackTrace'); await _emitError(emit: emit, error: error, stackTrace:
    stackTrace); }`.
11а. `_emitError` вызывает `_addDataUpdateError(dataCategory:
    _currentDataCategory, errorDataKey: _currentDataKey, errorMessage:
    'error: $error, stackTrace: $stackTrace')` — записывает строку в
    `DataUpdates` с `dataCategoryId == DataCategory.syncReports` (значение,
    зафиксированное на шаге 3, поскольку между ним и отказом ни один
    последующий `_emitProgress` не вызывался) — затем `emit(DataUpdateFailure(
    errorTitleKey: 'an_error_data', errorMessageKey: _currentDataKey,
    errorMessage: ..., isAdressesUpdate: false))`.
12а. Пользователь видит явный отказ прохода (`DataUpdateFailure`). Локально ни
    одна ready-строка `UnsentReportAnimals` не удаляется (`deleteAllReadyToSend()`
    не достигнут) — они остаются `readyToSend == true`, будут выбраны и
    отправлены заново на следующем полном sync-проходе. Кэш `ReportAnimals`
    тоже не тронут (`clear()` не достигнут) — старые данные, если были,
    остаются видны.

**Ветка (б) — логический отказ сервера без исключения.**

7б. `CustomDioClient.call` получает от `dio.request(...)` обычный HTTP
    200-ответ, тело которого — `Map<String, dynamic>` **без** ключей
    `data`/`animal_exits` и с явным `response.data['status'] == 'error'`
    (например `{"status": "error", "message": "duplicate"}`) — единственная
    ветка внутри `CustomDioClient.call`, где ответ возвращается **как есть**,
    со `status: 'error'`, без исключения (любая другая форма ответа
    принудительно получила бы `status: "1"`).
8б. `sync()` получает этот `response` из `await rpcClient.call(message)` без
    исключения. Единственное, что делается с ним дальше — `log('response:
    $response')` (`dart:developer`, виден только в консоли отладки/DevTools,
    не в `Talker`, не в UI). **Ни одного условия, читающего
    `response['status']` или `response['errors']`, в методе нет вовсе** —
    метод не имеет ни `if`, ни тем более `else`-ветки на этот счёт (строже,
    чем у взвешиваний, [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md),
    где хотя бы есть непройденный `if` без `else`). `sync()` возвращает
    управление вызывающей стороне как обычный успешно завершённый
    `Future<void>`.
9б. `updateAndSyncSHTP` (шаг 4) не видит ничего необычного — `await` просто
    завершается. Выполнение продолжается **безусловно**: `await
    _reportsRepository.clear();` (удаляет **все** строки таблицы
    `ReportAnimals`, `BaseDao.clear() = delete(_currentTableInfo).go()`, без
    `WHERE` — весь локальный кэш подтверждённых отчётов любого типа) и `await
    _unsentReportsRepository.deleteAllReadyToSend();`
    (`UnsentReportAnimalsDao.deleteAllReadyToSend() = delete(unsentReportAnimals)..where(readyToSend
    == true)).go()` — удаляет **все** ready-строки любого `way_type`, не
    только только что не принятые сервером).
10б. `await loadShtp(emit)` вызывается следующим: `_emitProgress(dataKey:
    DataKey.reports, dataCategory: DataCategory.reports)`, затем `reports =
    await _reportsRepository.getReportsFromApi()` — `GET
    ${Constants.farmServiceApi}/get-animal-exits` за окно «последний год —
    завтра» — сервер, ранее логически отклонивший батч, разумеется не
    возвращает эти строки как принятые; `insertAll(reports)` вставляет
    только то, что сервер реально знает (без только что потерянных строк).
11б. `_syncAuthData` (шаг 2) продолжает: `_emitProgress(dataKey:
    DataKey.syncDevices)`, `await _suncDevices()`. `on<DataUpdateStartAll>`
    (шаг 1), если остальные независимые шаги не упали, доходит до `emit(
    DataUpdateSuccess(resetNavigationOnSuccess: event.resetNavigationOnSuccess))` —
    пользователь видит **полностью успешное** завершение обновления данных.
12б. **Итог:** строки, которые были `readyToSend == true` в `UnsentReportAnimals`
    до этого прохода, удалены безвозвратно (шаг 9б) и не пересозданы никаким
    последующим шагом того же прохода (шаг 10б получает данные строго с
    сервера — а сервер их отклонил). Ни в `UnsentReportAnimals`, ни в
    `ReportAnimals` не остаётся ни одной копии. Ни `DataUpdates`, ни `Talker`,
    ни любой другой видимый пользователю канал не фиксируют этот отказ — путь
    от «пользователь завершил сессию инвентаризации» до «данные сессии
    исчезли» не оставляет ни одного наблюдаемого пользователем следа, кроме
    отсутствия сессии в местах, где она раньше была видна (хаб «В работе» —
    [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md);
    посуточный отчёт — [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)).

### Альтернативные потоки

- **Пустой батч — сценарий не наступает.** Если на момент вызова
  `getAllReadyToSend()` нет ни одной строки с `readyToSend == true` (любого
  типа), `sync()` вообще не вызывается (`if (unsentReportAnimals.isNotEmpty)`),
  но `_reportsRepository.clear()` и `_unsentReportsRepository.deleteAllReadyToSend()`
  всё равно выполняются безусловно — на пустом наборе это no-op без
  видимого эффекта, кроме сброса кэша `ReportAnimals` перед следующим pull'ом
  (шаг 10б выполняется в любом случае, независимо от исхода `sync()`).
- **Батч смешивает `'inventory'` с другими `way_type`.** `getAllReadyToSend()`
  не фильтрует по типу — если в один batch-запрос попадают одновременно
  строки инвентаризации и легаси-типов `'output'`/`'input'` (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), эти типы
  недостижимы из реального UI, но теоретически возможны как тестовые
  фикстуры/легаси-данные), логический отказ сервера в ветке (б) удаляет их
  все разом — потеря не ограничивается только инвентаризацией.
- **Исключение до строки `try` в `updateAndSyncSHTP` — вырожденный случай,
  здесь не наступающий.** В отличие от взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md), где сборка
  батча вне `try` — отдельный источник сбоя), здесь весь метод `sync()`
  целиком лишён `try/catch`, так что разделения на «до входа в try» и «внутри
  try» не существует вообще — любое исключение на любой стадии `sync()`
  (включая `getAllAnimalsWithDetailsByFilters()`/`getAllLocalAnimalsWithDetailsByFilters()`
  при сборке `allAnimals`) ведёт к тому же исходу, что и ветка (а):
  необработанное исключение, всплывающее до внешнего `catch`
  `on<DataUpdateStartAll>`.
- **`REJECTED`-ветки не существует**, как и у взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)) — код не
  умеет отличить содержательный отказ сервера (ветка б) от технического сбоя
  (ветка а) на каком-либо вышестоящем уровне; здесь ветка (б) при этом ещё и
  активно удаляет данные, а не просто «ничего не делает» — см. «Открытые
  вопросы».

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals`+`ReportAnimals`) — сущность,
  чьё физическое хранилище меняется этим сценарием: ветка (а) не меняет
  ничего; ветка (б) удаляет все `readyToSend == true` строки
  `UnsentReportAnimals` (шаг 9б) и полностью очищает `ReportAnimals` (шаг
  9б), затем заполняет `ReportAnimals` заново только тем, что вернул сервер
  (шаг 10б) — исключая только что отклонённые строки.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  только: `allAnimals` (объединение `getAllAnimalsWithDetailsByFilters()` и
  `getAllLocalAnimalsWithDetailsByFilters()`) используется для резолва
  `animal_id` каждого элемента payload'а по совпадению `transponderId`;
  `Animal` не изменяется этим сценарием ни в одной из веток.
- `DataUpdates` (лог sync-прохода, специфицируется будущим модулем SYSTEM) —
  получает одну строку об отказе только в ветке (а) (`dataCategoryId ==
  DataCategory.syncReports`); в ветке (б) — **не получает ни одной строки**,
  несмотря на фактическую потерю данных.

### Бизнес-правила

- Push — единый batch-запрос на все `readyToSend == true` строки сразу, всех
  `way_type` одновременно, не по сессиям и не по одной записи (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)) — отказ (в
  любой из двух веток) применяется ко всему батчу одновременно, партиального
  успеха на уровне отдельной сессии/строки в этой архитектуре запроса не
  существует.
- **Ветка (а) — единственный найденный в этом сценарии путь, где данные не
  теряются.** Сетевое исключение прерывает выполнение раньше, чем
  выполняются деструктивные шаги (`clear()`/`deleteAllReadyToSend()`), и
  явно проваливает весь sync-проход, давая пользователю понять, что что-то
  не удалось (хоть и без указания, что именно).
- **Ветка (б) — единственный найденный во всём модуле ANIMAL путь
  безвозвратной потери пользовательских данных при логическом (не
  техническом) отказе сервера.** Тот же класс дефекта, что уже
  задокументирован для взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)), но здесь
  строго хуже: там push просто не отмечает записи отправленными (`sync`
  остаётся `false`, данные остаются локально, просто дублируются при
  следующей попытке) — здесь же строки уже отправленного (с точки зрения
  клиента) батча **активно удаляются** (`deleteAllReadyToSend()`) несмотря
  на то, что сервер их не принял. Ни одна другая под-область `ANIMAL`,
  просмотренная на сегодня, не воспроизводит именно эту комбинацию
  («логический отказ без исключения» + «безусловное удаление локальной
  копии сразу после push»).
- Никакого отдельного retry/backoff-механизма для батча инвентаризации нет;
  для ветки (а) «повтор на следующем проходе» — не оформленная явно
  бизнес-логика, а побочный эффект того, что `getAllReadyToSend()` при
  каждом полном проходе просто повторно выбирает все ещё не удалённые
  ready-строки. Для ветки (б) повтора не будет никогда — строк для повтора
  уже не существует.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба под-сценария (сетевое исключение и
логический отказ сервера без исключения) воспроизводятся статическим
чтением кода целиком: `DataUpdateBloc.updateAndSyncSHTP` →
`UnsentReportAnimalsRepository.sync` → `CustomDioClient.call`/`DioClient`
(ветка а — подтверждена интеграционно-подобным тестом, см. «Связанные
тесты», через мок `ApiClient`, бросающий исключение) — и подтверждены
запущенными тестами (см. «Связанные тесты», обе ветки зелёные на момент
написания). Исправление (например, проверка `response['status']` перед
`deleteAllReadyToSend()`/`clear()`, аналогично тому, что уже частично
существует у взвешиваний) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncSHTP()` без собственного `try/catch`; порядок — после `updateAndSyncRegagro`, до `_suncDevices` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP` | CURRENT | оркестрация: `getAllReadyToSend()` → (если непусто) `sync()` → безусловно `_reportsRepository.clear()` + `deleteAllReadyToSend()` → `loadShtp()`; ни один из трёх вызовов не обёрнут в `try/catch` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadShtp` | CURRENT | пуллит `GET .../get-animal-exits` и вставляет результат в `ReportAnimals`, вызывается сразу после безусловной очистки |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный внешний `try/catch` всего прохода — срабатывает только для ветки (а); для ветки (б) не срабатывает вовсе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `._addDataUpdateError` | CURRENT | пишут строку в `DataUpdates` (`dataCategoryId == DataCategory.syncReports`) и эмитят `DataUpdateFailure` — вызываются только в ветке (а) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | фиксирует `_currentDataCategory`/`_currentDataKey`, используемые `_addDataUpdateError` при отказе |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.sync` | CURRENT | строит payload (резолв `animal_id` по `transponderId`), вызывает `rpcClient.call` — **без единого `try/catch` во всём методе**; не читает `response['status']`/`response['errors']` ни одним условием |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getAllReadyToSend`, `.deleteAllReadyToSend` | CURRENT | выбор батча (все `way_type` разом) / безусловное удаление всех `readyToSend == true` строк |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters`, `.getAllLocalAnimalsWithDetailsByFilters` | CURRENT | источник `allAnimals` для резолва `animal_id` внутри `sync()` — потенциальный источник исключения вне какого-либо `try` (см. «Альтернативные потоки») |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` (ветка а); при HTTP-успехе с `Map` без `data`/`animal_exits` и явным `status: 'error'` возвращает ответ как есть без исключения (ветка б) |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsFromApi` | CURRENT | вызывается `loadShtp` сразу после безусловной очистки — пуллит только то, что сервер реально подтверждает |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear` | CURRENT | делегирует в `dao.clear()`, вызывается безусловно из `updateAndSyncSHTP` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` | CURRENT | `delete(_currentTableInfo).go()` — без `WHERE`, вся таблица целиком |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.getAllByFilters`, `.deleteAllReadyToSend` | CURRENT | выбор по `readyToSend == true` без фильтра по типу; удаление по тому же условию, без фильтра по типу |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>` | CURRENT | источник строк, которые становятся предметом этого сценария — помечает сессию `readyToSend = true` ([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)) |

## Критерии приёмки

- Если для непустого батча (`getAllReadyToSend()` вернул хотя бы одну
  строку) вызов `rpcClient.call` внутри `UnsentReportAnimalsRepository.sync`
  бросает исключение, оно всплывает необработанным из `sync()`, из
  `updateAndSyncSHTP`, из `_syncAuthData` — до единственного внешнего
  `catch` `on<DataUpdateStartAll>`, который пишет строку в `DataUpdates` и
  эмитит `DataUpdateFailure`. Строки `UnsentReportAnimals` с `readyToSend ==
  true` остаются нетронутыми; кэш `ReportAnimals` тоже не изменяется.
- Если тот же вызов возвращает ответ с `response['status'] == 'error'` (без
  исключения), `sync()` завершается без ошибки; `updateAndSyncSHTP`
  безусловно вызывает `_reportsRepository.clear()` и
  `_unsentReportsRepository.deleteAllReadyToSend()`, затем `loadShtp()`; ни
  одна из ранее существовавших ready-строк не восстанавливается ни в
  `UnsentReportAnimals`, ни в `ReportAnimals`; `DataUpdates` не получает ни
  одной строки об этом отказе; sync-проход завершается
  `DataUpdateSuccess`, если остальные шаги не упали независимо.

## Связанные тесты

- `test/repositories/unsent_report_animals_repository_test.dart`, group
  `'UC-125 — UnsentReportAnimalsRepository.sync (успех)'` — контрольный
  baseline (не этот файл): подтверждает, что при обычном успешном ответе
  ready-строки удаляются, как и ожидается в норме.
- `test/repositories/unsent_report_animals_repository_test.dart`, group
  `'UC-126 — UnsentReportAnimalsRepository.sync (приоритет №1 дефект —
  потеря данных)'` — прямое подтверждение **ветки (б)**: тест
  `'НАХОДКА подтверждена: логический отказ сервера (200 OK, тело с
  ошибкой) -> sync() его не замечает -> deleteAllReadyToSend() всё равно
  выполняется -> данные сканирования потеряны безвозвратно'` мокает
  `farmRpcClient.call(any())` ответом `{'status': 'error', 'message':
  'duplicate'}`, прогоняет `_runSyncPipeline` (локальный хелпер файла,
  дословно воспроизводящий три строки оркестрации
  `updateAndSyncSHTP`: `getAllReadyToSend()` → `sync()` →
  `deleteAllReadyToSend()` — без вызова `_reportsRepository.clear()`,
  который в этом репозиторном тесте не воспроизводится отдельно, т.к. он
  принадлежит другому репозиторию) и проверяет, что
  `db.unsentReportAnimalsDao.getAllByFilters(readyToSend: true)` возвращает
  пустой список — с явным `reason: 'ДЕФЕКТ: строка удалена локально, хотя
  сервер её не принял — безвозвратная потеря данных пользователя'`.
- `test/repositories/unsent_report_animals_repository_test.dart`, group
  `'UC-126 — UnsentReportAnimalsRepository.sync (сетевое исключение —
  данные сохранены)'` — прямое подтверждение **ветки (а)**: тест
  `'сетевое исключение -> единственный безопасный путь:
  deleteAllReadyToSend() не достигается, данные сохранены'` мокает
  `farmRpcClient.call(any())` через `thenThrow(Exception('network error'))`,
  проверяет, что `_runSyncPipeline` действительно пробрасывает исключение
  (`throwsA(isA<Exception>())`) и что после этого
  `db.unsentReportAnimalsDao.getAllByFilters(readyToSend: true)` всё ещё
  содержит одну строку (`hasLength(1)`).
- Старая нумерация групп (`UC-125`/`UC-126`/`UC-126`) в этом тестовом файле
  относится к прежней схеме id и не переименована на момент написания этой
  спеки — переименование под новые id (`UC-126` для веток а/б) выполняется
  отдельным контролируемым проходом, не этой задачей; якорь `grep -r
  "UC-126" test/` заработает только после него.

## Открытые вопросы и ограничения

- **Это тот же класс дефекта, что и у взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)), но здесь
  хуже.** У взвешиваний push просто не отмечает строки отправленными
  (`sync` остаётся `false`) — данные остаются локально в неизменном виде,
  просто дублируются при следующей попытке отправки. Здесь, в ветке (б),
  строки уже **активно удаляются** (`deleteAllReadyToSend()`) несмотря на
  логический (не технический) отказ сервера — это единственный найденный на
  сегодня во всём модуле `ANIMAL` путь безвозвратной потери пользовательских
  данных при content-уровневом (не сетевом) отказе сервера.
- **Историческая, не авторитетная параллель.** Аналогичный по существу
  дефект (тогда — под старой нумерацией, `EVT-83`/`ENT-11` в
  `sdlc-deprecated/`, до полной пересборки дерева спек) уже был
  задокументирован в `sdlc-deprecated/2-specs/use-cases/UC-172-ACTOR-2-EVT-83-ENT-11-CREATE_REJECTED-IN-ANIMAL.md`
  как «самый серьёзный подтверждённый дефект этого корпуса», со ссылкой на
  ещё более раннее упоминание в constraints `sdlc/0-vibes/prd/PRD.md`. Тот
  документ классифицировал сценарий как `CREATE_REJECTED` (операция дошла до
  сервера и была осознанно отклонена); эта спека, следуя заданию текущего
  прохода, фиксирует его как `CREATE_ERROR` — обе ветки (а) и (б) сведены в
  один файл, как и для взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)), поскольку
  код не предоставляет наблюдаемого различия между «сервер отказал» и
  «технический сбой» ни на одном вышестоящем уровне — с точки зрения
  вызывающего кода и пользователя это неотличимые исходы. Упоминается здесь
  только как исторический контекст, не как авторитетная ссылка на живой
  артефакт (`sdlc-deprecated/` не используется как источник для нового
  дерева).
- **`sync()` не проверяет ответ сервера вообще ни одним условием** — строже,
  чем у взвешиваний (`storeAnimalWeighingsToSHTP`), где хотя бы есть
  недостигаемый `if (response['status'] == "1" || response['status'] == 1)`
  без `else`. Здесь нет и такого условия — единственное действие с ответом
  сервера — `log('response: $response')` через `dart:developer`, не
  связанный ни с `Talker`, ни с `DataUpdates`, ни с каким-либо UI. Является
  ли отсутствие проверки осознанным решением (например, ожидание, что этот
  эндпоинт никогда не возвращает `status: 'error'` в 2xx-ответе) или
  недосмотром — ничем в коде/комментариях не зафиксировано.
- **Потенциальная потеря затрагивает не только инвентаризацию.**
  `getAllReadyToSend()`/`deleteAllReadyToSend()` работают по всем `way_type`
  разом, не фильтруя `'inventory'` — если легаси-типы `'output'`/`'input'`
  когда-либо станут достижимы из UI (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  «Инварианты» — на сегодня недостижимы), тот же логический отказ потеряет и
  их одновременно.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`UnsentReportAnimalsRepository.sync` → `CustomDioClient.call` →
  `DioClient`) и подтверждён модульными тестами с замоканным `ApiClient`
  (см. «Связанные тесты»); точная форма ответа, необходимая для ветки (б)
  (`Map` без `data`/`animal_exits`, с `status: 'error'`), реально
  наблюдаемая от `POST .../exit-event` со стороны сервера, этой спекой не
  верифицирована.
