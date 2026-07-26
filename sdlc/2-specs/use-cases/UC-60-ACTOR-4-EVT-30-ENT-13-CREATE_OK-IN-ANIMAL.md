# UC-60 — Sync-проход успешно отправляет неотправленные перемещения на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все ещё
не отправленные перемещения ([ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md),
`sync == false`) одним батч-запросом сразу, и запрос завершается успехом для
всей пачки разом — каждая отправленная запись получает `sync = true`.
Happy-path сценарий события [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md)
(`movement.push_synced`) — событие завершает то, что локально начал
[EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) (`movement.recorded`),
инициированный [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md),
авторизованный пользователь — весь этот шаг гейтится `_authRepository.isAuthorized()`)
один раз (`DataUpdateStartAll`), но в каждом отдельном сетевом вызове этого
сценария человек не участвует. Перемещения, отправляемые в этом сценарии, были
записаны раньше — гостем или авторизованным пользователем одинаково
([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)) — этот факт не влияет на то,
отправится ли запись сейчас: единственное условие отбора — `sync == false`.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик сначала проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка, не
   часть этого use-case).
2. При наличии сети, после загрузки справочников и досок объявлений — если
   `_authRepository.isAuthorized()` — вызывается `DataUpdateBloc._syncAuthData`.
3. `_syncAuthData` выполняет фиксированную последовательность:
   `_deletePlacesFromRDS()` → `_syncFarms()` → `_syncPlaces()` →
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` →
   `updateAndSyncRegagro(event, emit)` (дальше в этом же методе идут
   `updateAndSyncSHTP` и синхронизация устройств — вне рамок этого use-case).
4. `updateAndSyncRegagro` решает — та же развилка, что уже описана в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md) (шаг 3): по
   количеству уже накопленных записей `DataUpdate`, наличию ошибок в них и
   флагам события (`event.again`/`event.fullUpdate`), с повторной проверкой
   сети — нужно ли запускать `DataUpdateBloc._syncAllData` в этом проходе.
   Если сеть недоступна на этой проверке или условия не выполняются, сценарий
   до перемещений не доходит (другая ветка).
5. `_syncAllData` — тот же общий префикс, что и в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md) (шаг 4):
   `_clearDataUpdates()` → `loadUser` → `syncAllUnsentAnimals()` (sync
   создания животных, [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md),
   вне рамок этого use-case) → `_emitProgress(dataKey: DataKey.syncSettings)`
   → если `event is DataUpdateStartAll && event.isUpdateData` —
   `_settingsRepository.setSettingToSHTP()` → безусловно
   `_settingsRepository.getSettingFromSHTP()` → **`await
   _movementReportRepository.syncMovements()`** — с этого вызова начинается
   собственно этот сценарий.
6. `MovementReportRepository.syncMovements()` вызывает `sendMovementsToApi()`
   первым, `getReportsFromApiAndSave()` — вторым; сам метод не оборачивает ни
   один из двух вызовов в try/catch.
7. `sendMovementsToApi()`:
   1. `movements = await getNotSyncMovements()` → `MovementsDao.getAllNotSync()`
      — `SELECT * FROM movements WHERE sync = false`.
   2. Если `movements.isEmpty` — метод возвращается сразу, ни один сетевой
      вызов не выполняется (вырожденный случай «нечего синхронизировать», не
      этот сценарий).
   3. `data = movements.map((e) => e.toJson()).toList()` — каждый `Movement`
      сериализуется drift-сгенерированным `toJson()` по `@JsonKey` из таблицы
      `Movements`: `guid`, `id` (это **локальный** autoincrement-PK этой
      таблицы, не `remoteId`), `user_id`, `animal_id`, `place_id`,
      `place_date`, `created_at`, `updated_at`, `old_place_id` (= `fromId`),
      `sync`, `remoteId`.
   4. `ApiMessage(link: '${Constants.farmServiceApi}/animal-move', method:
      ApiMethod.post, data: {'moves': data})` — один `POST` с телом-массивом
      всех неотправленных записей сразу, не цикл из отдельных запросов.
   5. `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc')` →
      `CustomDioClient.call(message)` — добавляет заголовки
      `Authorization`/`Accept-Language`, выполняет запрос через `Dio`.
      `CustomDioClient.call` нормализует форму ответа: если тело — `Map`,
      содержащий ключ `data` или `animal_exits`, `status` форсируется в `"1"`
      и тело возвращается как есть; иначе, если тело — `Map` с
      `status == 'error'`, возвращается как есть; иначе возвращается
      `{"data": response.data, "status": "1"}` (см. «Открытые вопросы» — эта
      ветка форсирует `"1"`, даже если внутри `response.data` был другой
      признак отказа).
   6. Обратно в `sendMovementsToApi`: `if (status['status'] != "1" &&
      status['status'] != 1) throw Exception(status['message']);` — в этом
      (`CREATE_OK`) сценарии условие ложно, пачка считается полностью
      успешной.
   7. `await dao.updAll(movements.map((e) => e.copyWith(sync: const
      Value(true))).toList())` — `BaseDao.updAll` выполняется в одной
      `transaction()`, вызывая `upd(item)` (→
      `updateCurrent().replace(item)`) по одному разу на каждую запись из
      списка, снятого на шаге 7.1 **до** сетевого вызова, сопоставление —
      по локальному `id` (PK). Все записи пачки получают `sync = true`
      одновременно, в одной транзакции.
8. Управление возвращается в `syncMovements`, который продолжает
   `getReportsFromApiAndSave()` ([EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
   — вне рамок этого use-case.
9. `_syncAllData` продолжает после возврата из `syncMovements()`:
   `_disposalRepository.syncDisposals()` → `_syncEditedAnimals()` →
   `loadAnimals(event, emit)` → `_vaccinationsRepository.syncVaccinations(true)`
   — все вне рамок этого use-case.

### Альтернативные потоки

- `getNotSyncMovements()` пуст (нет неотправленных перемещений) →
  `sendMovementsToApi` возвращается сразу, сетевой вызов не выполняется —
  вырожденный случай, не этот сценарий.
- Отказ пачки целиком (`status['status']` не `"1"`/`1`) или исключение при
  самом вызове → собственный `catch` внутри `sendMovementsToApi` логирует
  через `Talker` и **пробрасывает исключение дальше** (`rethrow`) — ни одна
  запись пачки не получает `sync = true`. Так как ни `syncMovements`, ни
  вызывающий его код в `_syncAllData` не оборачивают этот вызов в свой
  try/catch, исключение всплывает до внешнего `try/catch` в
  `on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure` через
  `_emitError` — и прерывает весь остаток `_syncAllData` (шаг 8 —
  `getReportsFromApiAndSave` — и шаг 9 в этом проходе не выполняются вовсе).
  Отдельный `ERROR`-сценарий, не входит в этот use-case.
- Из предыдущего пункта следует: отказ push в этом же проходе означает, что
  pull (`getReportsFromApiAndSave`, [EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
  тоже не выполнится — `syncMovements` не оборачивает эти два вызова
  раздельно. Зафиксировано здесь как факт об очерёдности, не отдельный
  сценарий.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — основная
  сущность перехода: `sync` меняется с `false` на `true` для каждой записи
  пачки; локальный `id` и прочие поля строки этим шагом не переписываются —
  `remoteId` для перемещений, отправленных этим (push) путём, так и остаётся
  незаполненным (заполняется только для записей, загруженных с сервера
  через [EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  см. [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не
  затрагивается этим шагом напрямую; `Animal.placeId` уже был обновлён
  локально раньше, в момент записи перемещения
  ([EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)) — этот сценарий
  не читает и не пишет поля животного.

### Бизнес-правила

- Push — один батч-запрос на все ещё не отправленные записи разом, не цикл
  из отдельных запросов на каждую запись.
- Успех применяется ко всей пачке одновременно — партиального успеха на
  уровне отдельной строки нет: либо все записи, снятые в начале метода,
  получают `sync = true`, либо (при отказе) ни одна.
- Обновляются на `sync = true` именно те строки, что были прочитаны в самом
  начале метода, до сетевого вызова, сопоставление — по локальному `id`
  (PK); ответ сервера для этого эндпоинта не разбирается на отдельные поля
  и не переносится обратно в локальные строки — используется только для
  решения успех/отказ.
- Sync-проход не эмитит отдельный progress-шаг именно для перемещений — вызов
  идёт между settings и выбытием без собственного `_emitProgress`, в отличие
  от ферм/мест/справочников выше по цепочке этого же прохода.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде. Тестового покрытия на уровне
`MovementReportRepository.sendMovementsToApi`/`DataUpdateBloc` нет (см.
«Связанные тесты») — это факт отсутствия теста, а не незавершённость
сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксированная последовательность sync-шагов для авторизованного пользователя, вызывает `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, нужно ли запускать `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_movementReportRepository.syncMovements()` после `syncAllUnsentAnimals`/settings, до disposal/editedAnimals/loadAnimals/vaccinations |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.syncMovements` | CURRENT | вызывает `sendMovementsToApi()` перед `getReportsFromApiAndSave()`, без собственного try/catch |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.sendMovementsToApi` | CURRENT | выборка неотправленных, батч `POST`, проверка статуса, пометка пачки `sync = true`, `rethrow` при отказе |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getNotSyncMovements` | CURRENT | обёртка над `MovementsDao.getAllNotSync` |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.getAllNotSync` | CURRENT | `SELECT ... WHERE sync = false` |
| `packages/sheep_farm_database/lib/database/database.g.dart` | `Movement.toJson`, `Movement.fromJson` | CURRENT | drift-сгенерированная (де)сериализация по `@JsonKey`-маппингу таблицы `Movements` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | абстрактный контракт сетевого вызова, используемый `sendMovementsToApi` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальный `Dio`-запрос; нормализация формы ответа, определяющая итоговое `status['status']` |
| `lib/injection_container.dart` | регистрация `getIt` для `instanceName: 'farm_rpc'` | CURRENT | связывает `'farm_rpc'` `ApiClient` с `CustomDioClient` |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый URL сервиса `farm` (`{protocol}{host}/api/services/farm`) для эндпоинта `/animal-move` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `BaseDao.upd` | CURRENT | построчный `UPDATE` по PK в одной транзакции (`updateCurrent().replace`) |

## Критерии приёмки

- При полном sync-проходе (`DataUpdateStartAll`), при наличии сети и
  авторизованном пользователе, для непустого набора записей `Movement` с
  `sync == false` выполняется ровно один `POST {farmServiceApi}/animal-move`
  с телом `{"moves": [...]}`, содержащим все эти записи.
- Если ответ на этот запрос считается успешным (`status['status'] == "1"`
  или `1`), после прохода каждая из этих записей в локальной БД имеет
  `sync == true`, при неизменных прочих полях (локальный `id`, `remoteId` и
  т.д.).
- `MovementReportRepository.getNotSyncMovements()` после успешного прохода
  для этих записей больше не возвращает их.
- `MovementReportRepository.getReportsFromApiAndSave()` (pull-часть
  `syncMovements`) выполняется в этом же проходе следом за успешным push, а
  не пропускается.

## Связанные тесты

`TBD — теста нет` на уровне `MovementReportRepository.sendMovementsToApi`/
`DataUpdateBloc` — подтверждено поиском по `test/` (`sendMovementsToApi`,
`syncMovements`, `animal-move`, `UC-60`): совпадений внутри тела какого-либо
`test()`/`group()` нет. `test/blocs/data_update_bloc_test.dart` мокает
`MovementReportRepository` (`MockMovementReportRepository`), но не содержит
ни одного теста, вызывающего `syncMovements`/`sendMovementsToApi`.

Три других MOVE-теста, упомянутые в задании, относятся к другим событиям и
другому актору, не подменяют покрытие этого сценария:
`test/pages/animal_movement_bloc_test.dart`, group `'UC-54 — AnimalMovementEventSave'`/`'UC-138 — ...'` — покрывают
[EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) (запись
перемещения [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), не sync-push);
`test/pages/unsent_movements_cubit_test.dart`, group `'UC-56 — UnsentMovementsCubit.deleteGroup'`/`'UC-140 — ...'` — покрывают
[EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md);
`test/pages/movement_report_cubit_test.dart`, group `'UC-58 — MovementReportCubit.deleteEvent'`/`'UC-142 — ...'` — покрывают
[EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md). Ни один
из них не вызывает `sendMovementsToApi` и не проверяет путь sync-актора,
документируемый этим use-case.

## Открытые вопросы и ограничения

- **Нормализация формы ответа в `CustomDioClient.call` может форсировать
  `status['status']` в `"1"`** для любого ответа, который одновременно не
  содержит ключ `data`/`animal_exits` и не является буквально
  `{'status': 'error', ...}` — такой ответ оборачивается в `{"data":
  response.data, "status": "1"}`. Если реальный ответ сервера на `/animal-
  move` для отклонённой пачки выглядит, например, как `{"status": "0",
  "message": "..."}` (без ключа `data`, `status` — не строка `'error'`), эта
  нормализация форсирует успех на внешнем уровне независимо от фактического
  вердикта сервера по пачке, и проверка `sendMovementsToApi`
  (`status['status'] != "1" && status['status'] != 1`) никогда его не
  увидит. Не подтверждено по реальному ответу сервера этого эндпоинта —
  зафиксировано как риск для того, что именно считается «настоящим» успехом;
  дальше в рамках этого (`CREATE_OK`, где успех предполагается) документа не
  разбирается.
- `dao.updAll` строится на списке `movements`, снятом до сетевого запроса
  (шаг 7.1), сопоставление — по локальному PK; запись, добавленная локально
  между этим чтением и обновлением (в архитектуре этого приложения
  практически невозможно в рамках одного `await`-последовательного вызова
  на одном изоляте), не попала бы в пометку `sync = true` этой пачки, даже
  если бы теоретически была отправлена тем же запросом. Не найдено как
  реальный гоночный сценарий в коде — зафиксировано только для полноты.
- Нет теста на уровне `sendMovementsToApi`/`syncMovements`/`_syncAllData`
  (см. «Связанные тесты») — весь сценарий проверен только чтением кода.
