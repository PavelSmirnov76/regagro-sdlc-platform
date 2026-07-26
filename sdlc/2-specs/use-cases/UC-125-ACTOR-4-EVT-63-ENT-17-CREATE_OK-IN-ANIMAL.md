# UC-125 — Sync-проход отправляет весь бэклог готовых инвентаризационных сканов одним batch-запросом — успех (ответ сервера не проверяется)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Явный, запускаемый пользователем полный sync-проход
(`DataUpdateBloc.updateAndSyncSHTP`) доходит до отправки на сервер всех
строк `UnsentReportAnimals` с `readyToSend == true` — общий метод,
покрывающий весь бэклог целиком, а не только строки, оставленные
инвентаризацией (`way_type` допускает и другие значения, см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md); на практике
единственный реально создаваемый тип — `'inventory'`). Все строки батча
отправляются одним `POST /exit-event`
(`UnsentReportAnimalsRepository.sync`). Здесь описывается путь, где сам
сетевой вызов завершается без исключения — «успех» в терминах этого файла
означает исключительно «`rpcClient.call` не бросил», а не «сервер
подтвердил приём содержательно»: тело ответа нигде не проверяется (см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), «Push не
проверяет тело ответа сервера»). Отдельно описывается точный алгоритм
резолюции `animal_id` для каждой строки payload'а — поиск по
`AnimalIdentification.markerTypeId == Constants.TransponderMarkerTypeId`
среди **всех** известных клиенту животных, синхронизированных и локальных
разом.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода; прямого пользовательского действия в момент самой
отправки нет. Проход запускается ранее
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (`DataUpdateStartAll`,
диспатчится из `main_page.dart` — кнопка обновления навбара,
`profile_settings_view.dart`, `in_work_page.dart` или `data_update_page.dart`)
— дальше проход идёт автоматически, без участия пользователя на уровне
отдельного сетевого вызова, как и описано в
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Сами строки, которые здесь
отправляются, были записаны раньше и локально тем же
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) через визард сканирования —
[EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) (завершение
новой сессии) и/или
[EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) (правка уже
сохранённой сессии) — ACTOR-5 не участвует в самом sync-шаге.

## CURRENT

### Основной поток

1. К моменту прохода в `UnsentReportAnimals` есть одна или несколько строк с
   `readyToSend == true` — результат более раннего
   [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)/
   [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md).
2. Пользователь инициирует полный sync-проход из одного из перечисленных
   выше входов → `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети
   (`NetworkConnectivityService.hasConnection()`) и загрузки справочников,
   при `_authRepository.isAuthorized()`, вызывается `_syncAuthData(event,
   emit)`.
3. `_syncAuthData` вызывает шаги последовательно: `_deletePlacesFromRDS()` →
   `_syncFarms()` → `_syncPlaces()` →
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` →
   `updateAndSyncRegagro(event, emit)` (движения/выбытия/вакцинации/животные
   — вне рамок этого файла) → `updateAndSyncSHTP(event, emit)` — шаг,
   которому посвящён этот сценарий.
4. `updateAndSyncSHTP` эмитит прогресс (`DataKey.syncReports`,
   `DataCategory.syncReports`), затем `unsentReportAnimals = await
   _unsentReportsRepository.getAllReadyToSend()` →
   `UnsentReportAnimalsDao.getAllByFilters(readyToSend: true)` — выбирает
   **весь** бэклог `readyToSend == true` целиком, без фильтра по `type`, без
   привязки к конкретной сессии/дате/ферме. В этом сценарии список непуст.
5. Поскольку список непуст, вызывается `await
   _unsentReportsRepository.sync(unsentReportAnimals)`.
6. Внутри `sync`: строится `allAnimals` — конкатенация `await
   getIt<AnimalsRepository>().getAllAnimalsWithDetailsByFilters()`
   (синхронизированные животные, дефолтные фильтры DAO: `isNotDeleted:
   true`, `isShowRemoteSource: false` → `Animal.source IS NULL`) и `await
   getIt<AnimalsRepository>().getAllLocalAnimalsWithDetailsByFilters()`
   (локальные животные, `id < 0`; внутри DAO-реализации метод передаёт
   `localOnly: true` и `requireFarmId: true` — локальное животное без
   заданного `farmId` в этот список не попадёт, см. «Открытые вопросы»).
   Первый список идёт первым в конкатенации.
7. Для каждой строки `e` батча резолвится `regagroId`: `allAnimals.where((e2)
   => e2.activeAnimalIdentifications.where((e2) => e2.markerTypeId ==
   Constants.TransponderMarkerTypeId).firstOrNull?.number ==
   e.transponderId.toString()).firstOrNull?.animalId`. То есть для каждого
   животного берётся **первая** (по порядку списка
   `AnimalWithDetails.animalIdentifications`, не гарантированно
   детерминированному) идентификация с `markerTypeId == 3`
   (`Constants.TransponderMarkerTypeId`), и только её `number` сравнивается с
   номером метки строкой; из всех животных, у которых это совпало, берётся
   первое по порядку `allAnimals` (синхронизированные — раньше локальных,
   см. шаг 6). `activeAnimalIdentifications`
   (`packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart`)
   — геттер, чьё имя предполагает фильтрацию по активности, но реализован
   как `animalIdentifications.where((e) => true)` — не фильтрует вообще
   ничего (см. «Открытые вопросы»).
8. Для каждой строки строится элемент payload'а: `transponder_id` и `number`
   (оба — `e.transponderId.toString()`, для `TextColumn` не меняет значение),
   `animal_id` — **только если** `regagroId != null` (иначе ключ полностью
   отсутствует в map, разрешение остаётся на сервере), `way_type` =
   `e.type`, `way_date` = `DateFormat('yyyy-MM-dd HH:mm:ss').format(e.time)`,
   `farm_id`/`place_id` — значения, уже сохранённые на самой строке (не
   перечитываются из `FarmRepository`/`PlaceRepository`), `uuid` — только
   если `e.sessionUuid != null`.
9. Собирается `{'animal_exits': [...]}`, единый `ApiMessage(link:
   '${Constants.farmServiceApi}/exit-event', method: ApiMethod.post, data:
   data)`, вызывается `getIt.get<ApiClient>(instanceName:
   'farm_rpc').call(message)`.
10. `CustomDioClient.call` выполняет HTTP-запрос; на этом сценарии он
    завершается без исключения (сеть доступна, ответ — 2xx). Нормализация
    ответа (принудительный `status: "1"` при наличии ключа `data` в теле,
    либо возврат как есть при явном `status: 'error'`, либо `{"data":
    response.data, "status": "1"}` в остальных случаях) не влияет на этот
    сценарий — `sync()` только логирует результат (`log('response:
    $response')`), не читает `response['status']` вообще.
11. `sync()` возвращает управление `updateAndSyncSHTP` без исключения.
    Немедленно и безусловно (вне какого-либо `try/catch`): `await
    _reportsRepository.clear()` — полная очистка таблицы `ReportAnimals`
    (все `way_type`, не только эта партия), затем `await
    _unsentReportsRepository.deleteAllReadyToSend()` —
    `UnsentReportAnimalsDao.deleteAllByFilters`-эквивалент, реализованный как
    `DELETE ... WHERE readyToSend = true` — новый запрос к БД в момент этого
    вызова, а не удаление по тому же списку id, что был получен на шаге 4
    (см. «Открытые вопросы»).
12. `await loadShtp(emit)` выполняется следом — `GET /get-animal-exits`
    (окно «последний год — завтра»), результат вставляется в уже пустую
    `ReportAnimals` ([EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md),
    отдельное событие/сценарий, здесь не детализируется дальше).
13. Если остальные шаги прохода не упали независимо, проход продолжается
    (`_suncDevices`) и в итоге эмитит `DataUpdateSuccess` — тот же сигнал
    пользователю, что и при полном успехе, независимо от того, что реально
    содержалось в ответе сервера на шаге 10.

### Альтернативные потоки

- **Пустой батч.** Если `getAllReadyToSend()` возвращает `[]`, `sync()` не
  вызывается вовсе (сетевого запроса нет), но `_reportsRepository.clear()` и
  `_unsentReportsRepository.deleteAllReadyToSend()` всё равно выполняются
  безусловно (шаги 4 и 11 кода не различают «батч был пуст» и «батч был
  успешно отправлен»).
- **Несколько сессий/дней/ферм в одном батче.** Один и тот же вызов `sync`
  покрывает вообще весь бэклог `readyToSend == true` разом — не по одной
  сессии инвентаризации и не по одному дню; строки из разных
  ферм/мест/сессий уходят в одном `POST`.
- **Строки с `type` отличным от `'inventory'`** (`'output'`/`'input'`) —
  участвовали бы в том же запросе тем же кодом (нет фильтра по `type` ни в
  `getAllReadyToSend`, ни в `sync`), но реально такие строки нигде в `lib/`
  не создаются, только в тестовых фикстурах (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).
- **Метка не находит совпадения ни у одного животного** (ни синхронизированного,
  ни локального — например метка ещё не привязана ни к одному известному
  клиенту животному, либо единственное совпадающее животное имеет
  `Animal.source != null`, либо это локальное животное без `farmId`): ключ
  `animal_id` в этом элементе payload'а просто отсутствует, без какой-либо
  локальной ошибки/предупреждения — резолюция окончательно остаётся на
  сервере.
- **Логический отказ сервера (`HTTP 200` с `status: 'error'` в теле) или
  сетевое исключение** — другой `RESULT` (`CREATE_ERROR`), не этот файл. Оба
  пути покрыты тестами в том же файле (группы `'UC-126 —
  UnsentReportAnimalsRepository.sync (приоритет №1 дефект — потеря
  данных)'` и `'UC-126 — UnsentReportAnimalsRepository.sync (сетевое
  исключение — данные сохранены)'`, старая нумерация — см. «Связанные
  тесты»), но собственного use-case файла на момент написания не имеют.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals`) — сущность, совершающая
  переход: весь `readyToSend == true` бэклог покидает эту таблицу
  безвозвратно сразу после (попытки) отправки, независимо от содержимого
  ответа сервера.
- `ReportAnimals` (та же сущность [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  вторая из двух таблиц) — полностью очищается (`clear()`) этим же шагом,
  до последующего `loadShtp`/pull.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только
  читается, дважды: как источник резолюции `animal_id` (и синхронизированные,
  и локальные животные одним плоским списком) и как источник `farmId`
  (шаг 6, `requireFarmId: true` для локальных) — этим сценарием ни одно поле
  `Animal` не меняется.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — только читается, через геттер
  `activeAnimalIdentifications`, который не фильтрует по `isActive`
  (см. «Открытые вопросы»); сопоставление — по `markerTypeId ==
  Constants.TransponderMarkerTypeId` и точному совпадению `number` с
  `transponderId`.

### Бизнес-правила

- Push — единый batch-запрос на весь `readyToSend == true` бэклог сразу, не
  по сессиям и не по одной записи (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).
- `animal_id` в payload — best-effort клиентская резолюция: если ни одно
  известное клиенту животное (синхронизированное или локальное) не имеет
  транспондерной идентификации с точно совпадающим номером, поле просто
  отсутствует — это не ошибка сценария, разрешение остаётся на сервере.
- Резолюция ищет среди объединения двух независимых источников —
  синхронизированных (`isNotDeleted: true`, `Animal.source IS NULL`) и
  локальных (`id < 0`, обязательно с заданным `farmId`) животных; при
  совпадении номера у животных из обоих множеств приоритет — у
  синхронизированного (оно идёт первым в конкатенации, шаг 6).
- `farm_id`/`place_id` элемента payload'а — это значения, уже сохранённые на
  самой строке `UnsentReportAnimals` (заполненные раньше, во время
  сканирования), не значения, заново прочитанные из `FarmRepository`/
  `PlaceRepository` в момент push'а.
- Успех этого шага в терминах `CREATE_OK` — чисто технический: единственное
  условие — что вызов `rpcClient.call` не бросил исключение; содержимое
  тела ответа не проверяется и не влияет на результат (см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), «Push не
  проверяет тело ответа сервера»).
- Немедленно после (успешной по этому определению) отправки — независимо от
  того, что было в ответе сервера, — весь локальный кэш `ReportAnimals` и
  весь `readyToSend == true` бэклог `UnsentReportAnimals` стираются
  безусловно; `resolved animal_id`, даже если он был вычислен для payload'а,
  нигде не сохраняется обратно в `UnsentReportAnimals` — строка всё равно
  целиком удаляется следующим шагом, вычисление одноразовое.
- Единственный источник восстановления состояния после push'а — последующий
  pull ([EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md)),
  который выполняется тем же проходом сразу следом, независимо от исхода
  push'а на уровне контента.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров нет — успешный (в определении «без исключения») путь push'а
полностью реализован и покрыт тестом (см. «Связанные тесты»); содержательный
отказ сервера и сетевое исключение — другой `RESULT`, не этот файл, и не
блокируют выполнение сценария, описанного здесь.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP` | CURRENT | ядро сценария — `getAllReadyToSend` → (если непусто) `sync` → безусловно `clear`/`deleteAllReadyToSend` → `loadShtp`, без собственного `try/catch` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncSHTP` после `storeAnimalWeighingsToSHTP`/`updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка входа полного sync-прохода; проверка сети и `isAuthorized()` до вызова `_syncAuthData` |
| `lib/pages/main/main_page.dart` | диспатч `DataUpdateStartAll` (кнопка обновления навбара) | CURRENT | один из живых входов прохода |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | диспатч `DataUpdateStartAll` | CURRENT | вход |
| `lib/pages/in_work/in_work_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | вход |
| `lib/pages/data_update/data_update_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | вход |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getAllReadyToSend` | CURRENT | выбор всего бэклога `readyToSend == true`, без фильтра по `type` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.sync` | CURRENT | построение `allAnimals`, резолюция `animal_id`, сборка payload'а, единственный `POST` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.deleteAllReadyToSend` | CURRENT | безусловное удаление; новый запрос по `readyToSend == true`, не по списку, полученному `getAllReadyToSend` |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.getAllByFilters`, `deleteAllReadyToSend` | CURRENT | реализация выборки/удаления на уровне Drift |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals.dart` | `UnsentReportAnimals` | CURRENT | схема — `transponderId` как `TextColumn`, без нормализации |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters`, `getAllLocalAnimalsWithDetailsByFilters` | CURRENT | два источника резолюции `animal_id` — синхронизированные и локальные животные |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | реализация фильтров (`isNotDeleted`, `isShowRemoteSource`, `localOnly`, `requireFarmId`) |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.activeAnimalIdentifications` | CURRENT | `animalIdentifications.where((e) => true)` — не фильтрует ничего, несмотря на имя |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId`, `Constants.farmServiceApi` | CURRENT | id типа маркера-транспондера (`3`) и базовый путь API |
| `lib/network/api_client/api_client.dart`, `lib/network/api_client/api_message.dart` | `ApiClient.call`, `ApiMessage` | CURRENT | RPC-обёртка, инстанс `'farm_rpc'` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | выполняет HTTP-запрос, нормализует ответ; сама по себе не бросает исключение на 200 с `status: 'error'` в теле |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.clear`, `getReportsFromApi` | CURRENT | безусловная очистка всего кэша `ReportAnimals` сразу после `sync()`; затем источник данных для последующего `loadShtp` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>` | CURRENT | предшествующий шаг ([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)/[EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)) — выставляет `readyToSend = true`, вне рамок этого файла |

## Критерии приёмки

- Если `getAllReadyToSend()` возвращает непустой список, происходит ровно
  один вызов `ApiClient(instanceName: 'farm_rpc').call(...)` с `method ==
  ApiMethod.post` и `link`, оканчивающимся на `/exit-event`, с телом
  `{'animal_exits': [...]}`, где длина списка равна длине входного списка
  строк.
- Каждый элемент `animal_exits` содержит `transponder_id`/`number`, равные
  исходному `transponderId`; `way_type`, равный исходному `type`;
  `way_date`, отформатированный `yyyy-MM-dd HH:mm:ss` по исходному `time`;
  `farm_id`/`place_id`, равные исходным полям строки без изменений; `uuid`
  присутствует тогда и только тогда, когда исходный `sessionUuid` не `null`.
- `animal_id` присутствует в элементе тогда и только тогда, когда среди
  объединения (сначала синхронизированные с `isNotDeleted: true` и
  `Animal.source IS NULL`, затем локальные с `id < 0` и заданным `farmId`)
  есть животное, чья первая (в порядке списка идентификаций) идентификация
  с `markerTypeId == Constants.TransponderMarkerTypeId` имеет `number`,
  равный `transponderId`; в этом случае значение — `animalId` этого
  животного, приведённый к строке.
- Вызов `rpcClient.call`, завершившийся без исключения (независимо от
  `status` в теле ответа), приводит к тому, что до возврата из
  `updateAndSyncSHTP` гарантированно выполняются оба: `await
  _reportsRepository.clear()` и `await
  _unsentReportsRepository.deleteAllReadyToSend()`, в этом порядке.
- Если `getAllReadyToSend()` возвращает пустой список — `sync()` не
  вызывается вовсе (ноль сетевых вызовов), но `clear()`/`deleteAllReadyToSend()`
  всё равно выполняются.
- Независимо от исхода этого шага на уровне контента ответа,
  `updateAndSyncSHTP` продолжает выполнение `loadShtp(emit)` следующим
  шагом.

## Связанные тесты

- `test/repositories/unsent_report_animals_repository_test.dart`, group
  `'UC-125 — UnsentReportAnimalsRepository.sync (успех)'` (старая
  нумерация, будет переименована отдельным контролируемым проходом — не
  трогать сейчас):
  - test `'успешный push -> POST /exit-event, затем все ready-строки
    удалены локально'` — вставляет две строки `UnsentReportAnimal`
    (`readyToSend: true` по умолчанию фабрики `_report`), мокает `farmRpcClient.call(any())`
    ответом `{'status': 'ok'}`, мокает `AnimalsRepository.getAllAnimalsWithDetailsByFilters()`/
    `getAllLocalAnimalsWithDetailsByFilters()` пустыми списками (резолюция
    `animal_id` в этом тесте не проверяется отдельно — оба источника
    пусты, элементы payload'а без `animal_id`), прогоняет ровно ту же
    последовательность вызовов, что и `DataUpdateBloc.updateAndSyncSHTP`
    (`_runSyncPipeline`: `getAllReadyToSend` → `sync` → `deleteAllReadyToSend`,
    без `_reportsRepository.clear()` — не относящаяся к этому репозиторию
    таблица не мокается в этом файле), затем проверяет, что
    `farmRpcClient.call` был вызван ровно один раз с `ApiMessage` (`method
    == ApiMethod.post`, `link` содержит `/exit-event`), и что после этого
    `db.unsentReportAnimalsDao.getAllByFilters(readyToSend: true)`
    возвращает пустой список — обе введённые строки удалены.
- Соседние группы того же файла — `'UC-126 —
  UnsentReportAnimalsRepository.sync (приоритет №1 дефект — потеря
  данных)'` (логический отказ сервера, `status: 'error'` в 200-теле, при
  этом `deleteAllReadyToSend()` всё равно выполняется — данные теряются
  безвозвратно) и `'UC-126 — UnsentReportAnimalsRepository.sync (сетевое
  исключение — данные сохранены)'` (исключение до `deleteAllReadyToSend()`
  — строка сохраняется) — не входят в этот use-case (другой `RESULT`,
  `CREATE_ERROR`), собственного use-case файла на момент написания не
  имеют.
- **TBD — теста нет** на резолюцию `animal_id` как таковую: тест группы
  `UC-125` явно мокает оба источника (`getAllAnimalsWithDetailsByFilters`/
  `getAllLocalAnimalsWithDetailsByFilters`) пустыми списками — ни один
  тест репозитория не проверяет, что при непустом списке животных
  `animal_id` реально резолвится (или не резолвится) по правилам,
  описанным в «Основной поток», шаг 7 (включая приоритет
  синхронизированных животных над локальными при совпадении, и то, что
  сравнивается только первая транспондерная идентификация животного).
- **TBD — теста нет** на `DataUpdateBloc.updateAndSyncSHTP` напрямую —
  `test/blocs/data_update_bloc_test.dart` покрывает только конструирование
  `DataUpdateBloc` и обработку `DataUpdateClear`; ни `on<DataUpdateStartAll>`,
  ни `updateAndSyncSHTP` этим файлом не вызываются вовсе (`grep -n
  "getAllReadyToSend\|deleteAllReadyToSend\|reportAnimalsRepository\|unsentReportAnimalsRepository"
  test/blocs/data_update_bloc_test.dart` не находит совпадений) — то, что
  `_reportsRepository.clear()` действительно вызывается именно в этом
  месте оркестрации (а не только смоделировано вручную в
  `_runSyncPipeline` теста репозитория, который эту таблицу не трогает
  вовсе), реальным прогоном `DataUpdateBloc` не подтверждено.

## Открытые вопросы и ограничения

- **`deleteAllReadyToSend()` не ограничен тем же списком id, что был
  получен `getAllReadyToSend()` на шаге 4.** Это отдельный DB-запрос,
  заново выбирающий (для удаления) все строки с `readyToSend == true` **на
  момент своего вызова** — если между шагом 4 (выборка) и шагом 11
  (удаление) какая-то другая сессия сканирования успеет завершиться
  (`ScanningBloc.on<ScanningEventSave>`/`close()`, тот же процесс,
  тот же event loop, вполне может выполниться, пока ожидается `await
  rpcClient.call(...)` на сетевом вызове) и выставить `readyToSend = true`
  на новых строках, эти новые строки **никогда не попадали в отправленный
  payload**, но всё равно будут удалены следующим `deleteAllReadyToSend()`
  — потеря данных, отличная от уже задокументированного в
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  content-уровневого отказа сервера. Гонка не воспроизведена
  эмпирически/тестом, оценка вероятности на практике не проводилась — не
  разбирается глубже в рамках этого файла.
- **`activeAnimalIdentifications` — геттер, чьё имя обещает фильтрацию,
  которой нет.** `AnimalIdentification.isActive` существует как колонка
  (см. [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)), но
  `activeAnimalIdentifications` реализован как `animalIdentifications.where((e)
  => true)` — тождественная функция, не проверяющая `isActive` ни разу.
  Резолюция `animal_id` в этом сценарии (как и другие потребители того же
  геттера в `lib/`) видит абсолютно все идентификации животного, включая
  потенциально неактивные. Осознанное решение или недосмотр в имени/теле
  геттера — не зафиксировано в коде.
- **Первый реальный потребитель `Animal.source`/`isShowRemoteSource`
  внутри ANIMAL.** [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) явно
  оставляет поле `source` неописанным «до тех пор, пока не появится
  под-область, которая его реально читает». `AnimalsRepository.getAllAnimalsWithDetailsByFilters()`,
  вызванный здесь без аргументов, использует дефолт `isShowRemoteSource:
  false` → `Animal.source IS NULL` — то есть эта резолюция молча исключает
  из поиска любое синхронизированное животное с непустым `source`. Что
  именно помечает животное как «удалённый источник» и почему оно должно
  быть исключено из сопоставления транспондера — не задокументировано ни
  здесь, ни в [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md); не
  разбирается глубже в рамках этого файла.
- **Сравнивается только первая транспондерная идентификация животного,
  порядок списка не гарантирован явной сортировкой на этом пути.** Если у
  животного более одной идентификации с `markerTypeId ==
  Constants.TransponderMarkerTypeId` (само по себе нетипичный случай —
  `IdentificationsStepPage` предполагает один транспондер на животное, но
  явного ограничения на уровне БД/резолюции нет), совпадение проверяется
  только у `.firstOrNull` из них; более поздняя в списке идентификация,
  даже если её `number` реально совпал бы с меткой, никогда не будет
  проверена.
- **Локальные животные без `farmId` молча исключены из резолюции.**
  `AnimalsRepository.getAllLocalAnimalsWithDetailsByFilters()` внутри DAO
  передаёт `requireFarmId: true` независимо от вызывающего кода — достижимо
  ли на практике локальное (ещё не отправленное) животное без заданного
  `farmId` через визард регистрации, этой спекой не проверено; не
  разбирается глубже.
- **`resolved animal_id` вычисляется, но нигде не сохраняется.** Даже когда
  резолюция на шаге 7 успешна, значение используется только для payload'а
  разового `POST`; строка `UnsentReportAnimals`, для которой оно было
  вычислено, целиком удаляется следующим шагом (`deleteAllReadyToSend`), а
  `ReportAnimals.regagroId` заполняется отдельно и независимо, только из
  ответа последующего pull'а
  ([EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md)) —
  два вычисления одного и того же факта, клиентское и серверное, никак не
  сверяются друг с другом.
- Не проверено эмпирически на реальном запуске против настоящего сервера —
  вывод сделан статическим чтением кода
  (`DataUpdateBloc.updateAndSyncSHTP` → `UnsentReportAnimalsRepository.sync`
  → `CustomDioClient.call`), включая точную форму нормализации ответа;
  реальный контракт `POST .../exit-event` со стороны сервера этой спекой не
  верифицирован.
