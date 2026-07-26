- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)

# UC-61 — Sync push перемещений отказывает технически — исключение пробрасывается наружу и обрывает весь sync-проход, ни одна запись батча не помечается синхронизированной

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md) — `MovementReportRepository.sendMovementsToApi` отправляет все ещё не отправленные перемещения (`sync == false`) одним батч-запросом сразу, не по одной. Здесь сам сетевой вызов заканчивается технически — либо `rpcClient.call` бросает исключение (сеть/таймаут/не-2xx статус по умолчанию для Dio), либо ответ приходит нормально, но тело содержит статус, отличный от `"1"`/`1` (в том числе явный бизнес-отказ сервера, например `status: 'error'`), и код сам бросает `Exception` в ответ на это. Оба случая обрабатываются в `sendMovementsToApi` одинаково: `catch` логирует через `Talker` и безусловно перебрасывает (`rethrow`) — метод не различает «не дошло» и «дошло, но отклонено», и ни разу не пытается сохранить частичный успех. Ни один вызывающий уровень (`syncMovements`, `_syncAllData`, `updateAndSyncRegagro`, `_syncAuthData`) не оборачивает этот вызов собственным `try/catch` — исключение долетает до единственного перехватчика на весь sync-проход, обрывая его целиком.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во время sync-прохода. Прямого пользовательского действия в момент самого отказа нет — sync-проход к этому шагу уже был запущен ранее [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (`DataUpdateStartAll`, диспатчится, например, из `main_page.dart`, `profile_settings_view.dart`, `in_work_page.dart` или `data_update_page.dart`) — дальше проход идёт автоматически, без участия пользователя на уровне отдельного сетевого вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Сами перемещения, которые здесь не удаётся отправить, были записаны раньше и локально [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (`AnimalMovementBloc.on<AnimalMovementEventSave>`, [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)) — ACTOR-5 не участвует в самом sync-шаге, только в исходном создании синхронизируемых записей.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход — `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети и загрузки справочников, при `_authRepository.isAuthorized()`, вызывается `_syncAuthData`.
2. `_syncAuthData` вызывает `_deletePlacesFromRDS`, `_syncFarms`, `_syncPlaces`, `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`, затем `updateAndSyncRegagro(event, emit)` — этот сценарий предполагает, что все предыдущие шаги в этом проходе не упали (иначе `updateAndSyncRegagro` вообще не достигается).
3. `updateAndSyncRegagro` (по своей внутренней логике счётчиков/повторов) вызывает `_syncAllData(event, emit)`.
4. `_syncAllData` последовательно вызывает `_clearDataUpdates()`, `loadUser(event, emit)` (внутри — `_emitProgress(dataKey: DataKey.user, dataCategory: DataCategory.user)`), затем `_emitProgress(emit: emit, dataKey: DataKey.syncUnsentAnimals, dataCategory: DataCategory.syncUnsentAnimals)` — это выставляет `_currentDataKey = 'syncUnsentAnimals'` и `_currentDataCategory = DataCategory.syncUnsentAnimals`. Далее `await syncAllUnsentAnimals()` (в этом сценарии завершается без ошибки).
5. `_syncAllData` вызывает `_emitProgress(emit: emit, dataKey: DataKey.syncSettings)` — **без** аргумента `dataCategory`. Внутри `_emitProgress` параметр `dataCategory` опционален: если он не передан, `_currentDataCategory` не переписывается и остаётся тем же, что был выставлен на предыдущем шаге (`DataCategory.syncUnsentAnimals`, из шага 4) — только `_currentDataKey` меняется на `'syncSettings'`. Между этим вызовом и крахом ниже никакой другой `_emitProgress`, специфичный для перемещений, не вызывается вовсе.
6. `_syncAllData` вызывает (при `event.isUpdateData`) `_settingsRepository.setSettingToSHTP()`, затем безусловно `_settingsRepository.getSettingFromSHTP()` — в этом сценарии оба завершаются без ошибки.
7. `_syncAllData` вызывает `await _movementReportRepository.syncMovements()` — этот вызов **не обёрнут** в собственный `try/catch` внутри `_syncAllData`. `MovementReportRepository.syncMovements` — это `await sendMovementsToApi(); await getReportsFromApiAndSave();`.
8. `sendMovementsToApi`: `movements = await getNotSyncMovements()` (`MovementsDao.getAllNotSync()` — все строки `Movements` с `sync == false`). Если список пуст — метод возвращается сразу, сценарий не наступает (см. «Альтернативные потоки»). Иначе строится `data = movements.map((e) => e.toJson()).toList()` и `ApiMessage(link: '${Constants.farmServiceApi}/animal-move', method: ApiMethod.post, data: {'moves': data})`, вызывается `await rpcClient.call(message)` через `ApiClient` с `instanceName: 'farm_rpc'` (реализация — `CustomDioClient`, обёртка над `DioClient`).
9. Этот вызов заканчивается технически одним из двух путей:
   - `CustomDioClient.call` перехватывает исключение из `dio.request(...)` (сеть недоступна, таймаут, обрыв соединения, либо любой не-2xx HTTP-ответ — `DioClient` не переопределяет `validateStatus`, поэтому Dio по умолчанию бросает `DioException` на любом статусе вне 200-299), логирует его через `Talker` и безусловно перебрасывает (`rethrow`) — это исключение всплывает прямо в `sendMovementsToApi`.
   - Либо `CustomDioClient.call` возвращает обычный ответ без собственного исключения (например HTTP 2xx с телом `{'status': 'error', ...}` — код клиента в этом случае явно возвращает `response.data` как есть, не подставляя `status: "1"`), и уже в самом `sendMovementsToApi` условие `status['status'] != "1" && status['status'] != 1` истинно — метод сам бросает `Exception(status['message'])`.
10. Оба пути заканчиваются в одном и том же `catch (e, stackTrace)` внутри `sendMovementsToApi`: `getIt<Talker>().error('sendMovementsToApi Error: $e', stackTrace)`, затем безусловный `rethrow` — код не различает «запрос не дошёл» и «дошёл, но был отклонён», см. «Альтернативные потоки».
11. Поскольку исключение вылетает из `sendMovementsToApi`, вторая строка `syncMovements` (`await getReportsFromApiAndSave()`, pull-шаг, [EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md)) в этом проходе не выполняется вовсе.
12. Исключение не перехватывается ни в `MovementReportRepository.syncMovements`, ни в `DataUpdateBloc._syncAllData`, ни в `updateAndSyncRegagro`, ни в `_syncAuthData` — единственный `try/catch` на этом пути находится в самом обработчике `DataUpdateBloc.on<DataUpdateStartAll>`, оборачивающем весь sync-проход целиком.
13. Этот внешний `catch (error, stackTrace)` логирует ошибку через `Talker` и вызывает `DataUpdateBloc._emitError`, который (а) пишет одну строку в `DataUpdates` через `_addDataUpdateError(dataCategory: _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: ...)` — используя значения, выставленные на шаге 5: `dataCategoryId = DataCategory.syncUnsentAnimals` (оставшееся от совсем другого, более раннего шага, а не от перемещений) и `errorDataKey = 'syncSettings'` (тоже не про перемещения — просто последний вызванный перед крахом `_emitProgress`), и (б) эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'syncSettings', errorMessage: 'error: $error, stackTrace: $stackTrace')` — общая ошибка всего sync-прохода, не привязанная ни к перемещениям, ни к конкретной записи.
14. Поскольку исключение вылетает из середины `_syncAllData`, все шаги, запланированные после `_movementReportRepository.syncMovements()` — `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`, `loadAnimals(event, emit)`, `_vaccinationsRepository.syncVaccinations(true)` — в этом проходе не выполняются вовсе.
15. Ни одна запись `Movement` из батча не помечается `sync = true` — `dao.updAll(...)` в `sendMovementsToApi` находится после проверки статуса и до него в этом сценарии не доходит. На следующем полном sync-проходе `getNotSyncMovements()` снова вернёт тот же самый набор записей (`sync` всё ещё `false`), вместе с любыми перемещениями, записанными между проходами — и весь набор будет отправлен заново, целиком.

### Альтернативные потоки

- **Пустой батч — сценарий не наступает.** Если на момент вызова `getNotSyncMovements()` нет ни одной записи с `sync == false`, `sendMovementsToApi` возвращается сразу после первой строки (`if (movements.isEmpty) return;`), не делая сетевого вызова вовсе.
- **Технический отказ и осознанный отказ сервера неразличимы в этом коде.** В отличие от синхронизации животного ([UC-51](UC-51-ACTOR-4-EVT-25-ENT-11-CREATE_ERROR-IN-ANIMAL.md)), где для содержательного отказа сервера (`result.isError`) есть отдельная, не бросающая исключение ветка (`_animalsRepository.update(animal.copyWith(errors: ...))`), у перемещений такой более мягкой ветки нет вовсе: `sendMovementsToApi` реагирует на любой `status`, отличный от `"1"`/`1` (включая явный бизнес-отказ вроде `status: 'error'`), тем же самым `throw Exception(...)`, что и на настоящее сетевое исключение — оба варианта проходят через один и тот же `catch`/`rethrow` и одинаково обрывают весь sync-проход. Поэтому результат этого сценария всегда `CREATE_ERROR`, `CREATE_REJECTED` для push перемещений структурно недостижим в текущем коде.
- **Не одна запись, а весь батч.** В отличие от ферм (циклический POST по одной, [UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) и от животных (цикл `syncLocalAnimal` по одному, [UC-51](UC-51-ACTOR-4-EVT-25-ENT-11-CREATE_ERROR-IN-ANIMAL.md)), здесь нет цикла и нет частично успевших записей — весь набор неотправленных перемещений уходит одним HTTP-запросом, поэтому при отказе либо успевают все, либо ни одна: частичного успеха на уровне отдельной записи батча в принципе не существует, а не просто не обрабатывается.
- **Pull этого же прохода не выполняется.** Поскольку `syncMovements` вызывает `sendMovementsToApi()` и `getReportsFromApiAndSave()` последовательно, а не независимо, отказ push обрывает и pull ([EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md)) в этом же проходе — даже если бы сама загрузка списка с сервера была доступна и работоспособна, до неё выполнение не доходит.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — все записи батча, отправка которого технически отказала, остаются `sync == false` без изменений; тот же набор (плюс новые, записанные между проходами) будет повторно отправлен целиком на следующем полном sync-проходе.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — `Animal.placeId` уже был обновлён локально в момент записи перемещения ([EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)), до какой-либо попытки синхронизации; этот сценарий его не трогает и не откатывает — отказ push никак не связан с локальным состоянием `placeId` (см. также `domain-model.md`, инвариант 5: «Movement меняет `Animal.placeId` локально до подтверждения сервера; при отказе синка автоматического rollback нет»).
- `DataUpdates` (лог sync-прохода) — получает одну строку через `_addDataUpdateError`, с `dataCategoryId`/`errorDataKey`, оставшимися от предыдущих, не связанных с перемещениями шагов (`DataCategory.syncUnsentAnimals` / `'syncSettings'`), а не что-то специфичное для этого шага; сама сущность и модель append-only лога специфицируются будущим модулем SYSTEM, не в этой спеке.

### Бизнес-правила

- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED`, независимо от того, был ли конкретный технический сбой сетевым исключением или ответом сервера со статусом, отличным от `"1"`/`1` (см. «Альтернативные потоки») — этот отказ никогда не доходит до пользователя как осознанно предъявленное решение по конкретному перемещению: он тонет в generic `DataUpdateFailure` всего sync-прохода. Та же формулировка, что и для ферм ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) и животных ([UC-51](UC-51-ACTOR-4-EVT-25-ENT-11-CREATE_ERROR-IN-ANIMAL.md)).
- Push — единый батч на все ещё не отправленные записи разом, не по одной (см. [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), инвариант «Push»); успех или отказ применяется ко всему батчу одновременно — партиального успеха на уровне отдельной записи нет и не может быть в этой архитектуре запроса, в отличие от ферм/животных, где частичный успех технически возможен (там баг в другом — в последующей обработке частичного успеха).
- Никакого отдельного retry/backoff-механизма для конкретно этого батча нет — «повтор на следующем проходе» не оформлена как явная бизнес-логика, это побочный эффект того, что `getNotSyncMovements()` при каждом полном проходе просто повторно выбирает все записи с `sync == false`, не различая «ещё не пробовали» и «уже пробовали и упали».
- Логика повторного запуска всего прохода при наличии ошибок в `DataUpdates` (`updateAndSyncRegagro`, `errorDataUpdates.isNotEmpty` → задержка 15 секунд → повторный `_syncAllData`) оценивается только на **следующем** вызове обработчика `DataUpdateBloc`, а не внутри уже упавшего прохода — этот крах не запускает немедленный повтор сам по себе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится статическим чтением кода (`DataUpdateBloc._syncAllData` → `MovementReportRepository.syncMovements`/`sendMovementsToApi` → `CustomDioClient.call`/`DioClient`). Возможное исправление (например, отделить push-шаг перемещений от остального `_syncAllData` собственным `try/catch`, аналогично тому, что уже сделано для `_syncEditedAnimals` в соседнем сценарии животных) в рамках этого документирующего прохода не выполняется — это чисто фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_movementReportRepository.syncMovements()` без собственного `try/catch`; последующие шаги (disposals/edited animals/load animals/vaccinations) не выполняются при исключении |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro` после sync ферм/мест/взвешиваний |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | вызов перед крахом (`dataKey: DataKey.syncSettings`, без `dataCategory`) не меняет `_currentDataCategory` — остаётся `DataCategory.syncUnsentAnimals` от предыдущего, не связанного с перемещениями шага |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет строку в `DataUpdates` (`_addDataUpdateError`) и эмитит `DataUpdateFailure`, используя `_currentDataKey`/`_currentDataCategory` момента краха |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.syncSettings`, `DataCategory.syncUnsentAnimals` | CURRENT | конкретные (не относящиеся к перемещениям) ключ/категория, зафиксированные в `DataUpdates`/`DataUpdateFailure` при этом крахе |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.syncMovements` | CURRENT | `await sendMovementsToApi(); await getReportsFromApiAndSave();` — вторая строка не выполняется при исключении из первой |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.sendMovementsToApi` | CURRENT | строит батч-payload, вызывает `rpcClient.call`; бросает `Exception` при `status` вне `"1"`/`1`; логирует и безусловно перебрасывает (`rethrow`) любое исключение; `dao.updAll(sync: true)` достигается только при успехе |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getNotSyncMovements` | CURRENT | выбирает батч, который будет повторно отправлен целиком на следующем проходе |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`; при HTTP-успехе с `status: 'error'` в теле возвращает ответ как есть, не бросая исключение сама — это исключение бросает уже `sendMovementsToApi` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.getAllNotSync` | CURRENT | выбирает все строки `Movements` с `sync == false`; тот же набор выбирается заново на следующем проходе |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `Movements`, `Movement` | CURRENT | таблица/модель; `sync` остаётся `false` для всего батча при этом крахе |

## Критерии приёмки

- Если для непустого батча `getNotSyncMovements()` вызов `rpcClient.call` внутри `sendMovementsToApi` либо бросает исключение, либо возвращает ответ со `status`, отличным от `"1"`/`1`, `sendMovementsToApi` логирует ошибку через `Talker` и безусловно перебрасывает исключение дальше — независимо от того, была ли причина сетевой или содержательным отказом сервера.
- Это исключение не перехватывается ни в `MovementReportRepository.syncMovements`, ни в `DataUpdateBloc._syncAllData`/`updateAndSyncRegagro`/`_syncAuthData` — единственная точка перехвата — внешний `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>`.
- `getReportsFromApiAndSave()` (pull того же вызова `syncMovements`) и все шаги `_syncAllData`, запланированные после `syncMovements()` (disposals/`_syncEditedAnimals`/`loadAnimals`/vaccinations), в этом проходе не выполняются.
- `DataUpdates` получает ровно одну новую строку: `dataCategoryId = DataCategory.syncUnsentAnimals`, `errorDataKey = 'syncSettings'` (оставшиеся от более раннего, не связанного с перемещениями шага), `errorMessage`, содержащий текст исключения и stack trace.
- Эмитится `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'syncSettings', errorMessage: ...)`; весь sync-проход на этом заканчивается.
- Ни одна запись `Movement` из батча не получает `sync = true`; на следующем полном sync-проходе `getNotSyncMovements()` вернёт тот же набор (плюс любые новые записи), и попытка отправки повторится целиком.
- `Animal.placeId` для животных, чьи перемещения входили в неудавшийся батч, остаётся таким, каким он был выставлен локально при записи перемещения ([EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)) — этот сценарий его не меняет и не откатывает.

## Связанные тесты

TBD — теста нет. Ни `MovementReportRepository.sendMovementsToApi`/`syncMovements`, ни прогон этого сценария через `DataUpdateBloc` тестами не покрыты.

Смежные тесты по перемещениям касаются других событий модуля, не push-синхронизации, и к этому сценарию не относятся: `test/pages/animal_movement_bloc_test.dart` (group `'UC-54 — AnimalMovementEventSave'` — успешная локальная запись перемещения, [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md); group `'UC-55 — AnimalMovementEventSave'` — ошибка локального сохранения), `test/pages/unsent_movements_cubit_test.dart` (group `'UC-56 — UnsentMovementsCubit.deleteGroup'` — успешное удаление группы неотправленных, [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md); group `'UC-57 — UnsentMovementsCubit.deleteGroup'` — ошибка удаления), `test/pages/movement_report_cubit_test.dart` (group `'UC-58 — MovementReportCubit.deleteEvent'` — успешное удаление с экрана дневного отчёта, [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md); group `'UC-59 — MovementReportCubit.deleteEvent'` — ошибка, молча проглатываемая `catch (_) {}`). Ни один из них не мокает и не проверяет `sendMovementsToApi`/`syncMovements`/`DataUpdateBloc`.

## Открытые вопросы и ограничения

- Является ли отсутствие отдельного `try/catch` вокруг `_movementReportRepository.syncMovements()` в `_syncAllData` осознанным решением или упущением — нигде в коде/комментариях это не зафиксировано явно, как и для аналогичных мест в фермах ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) и животных ([UC-51](UC-51-ACTOR-4-EVT-25-ENT-11-CREATE_ERROR-IN-ANIMAL.md)).
- Не различаются в коде «запрос не дошёл до сервера» и «сервер ответил статусом, отличным от `"1"`/`1`» (в том числе явный бизнес-отказ) — оба варианта дают один и тот же необработанный крах; является ли отсутствие отдельной `REJECTED`-ветки для перемещений осознанным упрощением (в отличие от животных, где такая ветка есть) или потерей полезной информации — не зафиксировано.
- `DataUpdateBloc` не переопределяет `Bloc.onError` для этого шага — единственный способ увидеть исходное исключение (а не только generic `DataUpdateFailure`) — это `errorMessage` внутри самого состояния (собирается в `_emitError` из `error`/`stackTrace`) либо строка в `DataUpdates`, а не что-то персонально видимое пользователю про конкретное перемещение или батч.
- Повторная отправка на следующем проходе всего батча (включая записи, для которых сервер, возможно, уже частично что-то создал до обрыва соединения на середине запроса) может приводить к дублированию на сервере — зависит от того, дедуплицирует ли сервер повторный запрос `/animal-move` (например по `guid` каждой записи), что вне зоны видимости этого клиентского кода и этой спеки.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим чтением кода (`_syncAllData` → `MovementReportRepository.syncMovements`/`sendMovementsToApi` → `CustomDioClient.call` → `DioClient`).
