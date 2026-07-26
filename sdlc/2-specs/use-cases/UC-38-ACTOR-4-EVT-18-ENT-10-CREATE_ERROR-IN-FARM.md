- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-38 — Sync создания места отказывает — единый батч-запрос на весь пакет мест обрывается разом, крах в `updatePlaceId` обрывает персист (незадокументированный дефект)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md) |
| Сущность | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| Результат | `CREATE_ERROR` |

## Назначение

Тот же sync-шаг, что описан в [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md) — `DataUpdateBloc._storePlacesToRDS` отправляет на сервер локально созданные места без серверного `idRemote`. В отличие от ферм ([EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md), [UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)), `PlaceRepository.storePlacesOnRDS` не отправляет места по одному в цикле — весь пакет уходит **одним** HTTP-запросом, и падает/отклоняется он тоже целиком, без частичного успеха. Здесь этот единственный запрос не создаёт места на сервере (сетевое исключение либо сервер отвечает без статуса успеха) — и, как и для ферм, это не заканчивается изолированной ошибкой по конкретному месту: следующий шаг того же метода (`AnimalsRepository.updatePlaceId`) падает с необработанным исключением на первом же месте пакета, что обрывает персист **всего** пакета мест, отправленных в этом цикле.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во время sync-прохода. Прямого пользовательского действия в момент самого отказа нет — sync-проход к этому шагу уже был запущен ранее [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (`DataUpdateStartAll`) — дальше проход идёт автоматически, без участия пользователя на уровне отдельного сетевого вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).

## CURRENT

### Основной поток

1. Sync-проход авторизованного пользователя (`DataUpdateBloc._syncAuthData`) вызывает `await _deletePlacesFromRDS()`, затем `await _syncFarms()`, затем `await _syncPlaces()`. Этот сценарий предполагает, что шаг `_syncFarms()` в этом проходе не упал (иначе `_syncPlaces()` вообще не достигается — см. [UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md) для краха на шаге ферм).
2. `_syncPlaces` вызывает `await _storePlacesToRDS()` первым шагом.
3. `_storePlacesToRDS` берёт `res = await _placeRepository.getAllWithoutRemoteId()` — Drift-запрос `PlaceRepository.getAllWithoutRemoteId` выбирает все локальные места с `idRemote < 0` (`tbl.idRemote.isSmallerThanValue(0)`), т.е. ещё ни разу не синхронизированные. Если список пуст — метод завершается сразу.
4. `remotePlaces = await _placeRepository.storePlacesOnRDS(res)`: `PlaceRepository.storePlacesOnRDS` формирует **один** POST-запрос (`${Constants.registrationServiceApi}/places/store`, через `ApiClient` с `instanceName: 'farm_rpc'`) с телом `{"places": res.map((e) => e.toJsonRDS()).toList()}` — весь пакет мест сериализуется в один список внутри одного запроса, в отличие от `FarmRepository.storeFarmsOnRDS`, который отправляет фермы по одной, отдельным запросом на каждую.
5. Этот единственный вызов заканчивается неудачно — либо `rpcClient.call(message)` бросает исключение (сеть/сервер), либо ответ приходит, но `response['status'] != "1"`. Оба случая внутри `storePlacesOnRDS` обрабатываются одинаково: `log(...)` и `return []` — метод возвращает пустой список. Поскольку весь пакет отправляется одним запросом, частичный успех здесь невозможен в принципе (в отличие от ферм, где per-item цикл допускает, что часть ферм в пакете реально создалась, а часть — нет): либо `response['status'] == "1"` и весь пакет получает соответствующие серверные записи через `PlaceExtension.fromJsonRDSwithLocalId` (позиционное сопоставление `data[index]` ↔ `res[index].id`), либо запрос не удался целиком и `remotePlaces` пуст для всего пакета.
6. `_storePlacesToRDS` вызывает `await _animalsRepository.updatePlaceId(res, remotePlaces)`, передавая **весь исходный список** `res` (все места, что были в пакете) как `oldPlaces`, и `remotePlaces` (пустой в этой ветке) как `newPlaces`.
7. `AnimalsRepository.updatePlaceId` идёт по `oldPlaces` в цикле; для первого же места вызывает `animalsList = await dao.getLocalAnimalsByPlaceId(place.idRemote!)` (только чтение — список локальных животных на этом месте, `id < 0`), затем вычисляет `newRemoteId` через `newPlaces.firstWhereOrNull((newPlace) => newPlace.id == place.id)!.idRemote`. Поскольку `newPlaces` пуст, `firstWhereOrNull` возвращает `null` для **любого** места пакета, а `!` (null-check operator) бросает `TypeError` («Null check operator used on a null value») уже на первой итерации — до того, как `updateAll(...)` для этого места вообще вызывается (запись животных на этом пути не происходит, только чтение).
8. Это исключение не перехватывается ни в `AnimalsRepository.updatePlaceId`, ни в `_storePlacesToRDS`, ни в `_syncPlaces`, ни в `_syncAuthData` — единственный `try/catch` на этом пути находится в самом обработчике `DataUpdateBloc.on<DataUpdateStartAll>`, оборачивающем весь sync-проход целиком.
9. Этот внешний `catch` вызывает `DataUpdateBloc._emitError`, который пишет строку в `DataUpdates` через `_addDataUpdateError` (с тем `_currentDataCategory`/`_currentDataKey`, что были выставлены последними до этого места — не специфичными для места или для этого шага, т.к. ни `_syncFarms`, ни `_syncPlaces`, ни `_storePlacesToRDS` не вызывают `_emitProgress` со своим собственным `dataKey`) и эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')` — общая, не относящаяся конкретно к месту ошибка всего sync-прохода.
10. Поскольку исключение вылетает из `_animalsRepository.updatePlaceId` до того, как выполнение дошло до `await _placeRepository.updateAll(remotePlaces)` (следующая строка `_storePlacesToRDS`), ни одно место из пакета не получает обновлённый локальный `idRemote` в этом проходе — что в данном сценарии не теряет никакого реально состоявшегося успеха, так как весь пакет и так провалился на сервере целиком.
11. Дальнейшие шаги `_syncPlaces` (`_updatePlacesOnRDS`, `_loadPlacesFromRDS`) в этом проходе не выполняются — исключение обрывает выполнение раньше.
12. На следующем полном sync-проходе `PlaceRepository.getAllWithoutRemoteId()` снова вернёт весь этот пакет (`idRemote` всё ещё `< 0`), и `storePlacesOnRDS` отправит по нему повторный POST `/places/store`.

### Альтернативные потоки

- В отличие от ферм ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)), здесь **не важен порядок**, в котором `getAllWithoutRemoteId` вернул места пакета: поскольку `storePlacesOnRDS` либо возвращает данные для всех мест пакета, либо пуст для всех сразу, крах в `updatePlaceId` при неудаче гарантированно происходит на первом же месте пакета в порядке, который вернул Drift-запрос — не бывает так, что часть мест пакета успела получить `idRemote`, а часть нет.
- Не важно, была ли причина неудачи сетевым исключением или ответом сервера с `status != "1"` — `storePlacesOnRDS` реагирует на них одинаково (`log` + `return []`), поэтому обе ветки приводят к одному и тому же дальнейшему краху в `updatePlaceId`.
- Если в пакете `res` пусто (нет локальных мест без серверного id) — `_storePlacesToRDS` возвращается до вызова `storePlacesOnRDS`, сценарий не наступает.
- `AnimalsRepository.updatePlaceId` вызывает `updateAll(...)` без `await` внутри цикла (тот же паттерн, что и в `updateFarmId`) — в этой ветке это не проявляется, так как исключение бросается до строки с `updateAll` уже на первой итерации.
- Идентичный по структуре код есть в `AnimalsRepository.updateFarmId` (тот же паттерн `firstWhereOrNull(...)!`), задействованный шагом раньше в `_syncFarms()` — если бы упал он, `_syncPlaces()` в этом же проходе не был бы достигнут вовсе (см. [UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)).

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность, для которой этот use-case описывает отказ создания; после отказа `idRemote` всего пакета остаётся отрицательным, так как сервер не создал ни одной записи этого пакета.
- Animal — `AnimalsRepository.updatePlaceId` — источник краха; для первого места пакета выполняется только чтение (`dao.getLocalAnimalsByPlaceId`), запись (`updateAll`) на этом пути не происходит вовсе, крах случается раньше; полная модель `Animal` специфицируется будущим модулем ANIMAL, не в этой спеке.
- `DataUpdates` (лог sync-прохода) — получает одну строку через `_addDataUpdateError` с generic сообщением об ошибке; сама сущность и модель append-only лога специфицируются будущим модулем SYSTEM, не в этой спеке.

### Бизнес-правила

- `_syncAuthData` вызывает синхронизацию мест безусловно, следом за фермами, на каждом полном sync-проходе для авторизованного пользователя — ничем не гейтится (см. [MOD-3](../modules/MOD-3-FARM.md)).
- В отличие от ферм, места отправляются на сервер **единым батчем**, а не по одной в цикле — частичный успех на уровне HTTP-вызова здесь невозможен в принципе: либо весь пакет получает серверные id, либо ни одно место пакета их не получает. Следующий шаг того же метода (`updatePlaceId`) не рассчитан даже на этот бинарный исход отказа и падает вместо того, чтобы просто оставить пакет несинхронизированным.
- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED`, даже для ветки `response['status'] != "1"` (содержательный отказ сервера): этот отказ никогда не доходит до пользователя как осознанно предъявленное решение — он теряется сначала в `return []` внутри `storePlacesOnRDS`, а затем полностью тонет в generic `DataUpdateFailure` всего sync-прохода, вызванном отдельным, не связанным с этой веткой крахом в `updatePlaceId`.
- Никакого отдельного retry/backoff-механизма для этого пакета нет — «повтор на следующем проходе» не оформлен как явная бизнес-логика, это побочный эффект того, что `getAllWithoutRemoteId` при каждом полном проходе просто повторно выбирает все места с `idRemote < 0`, не различая «ещё не пробовали» и «уже пробовали и упали».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится статическим чтением кода (`_storePlacesToRDS` → `storePlacesOnRDS` → `AnimalsRepository.updatePlaceId`). Возможное исправление (не давать провалу batch-запроса приводить к необработанному краху, вместо этого оставлять пакет несинхронизированным) в рамках этого документирующего прохода не выполняется — это чисто фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._storePlacesToRDS` | CURRENT | оркестрирует sync создания места: `getAllWithoutRemoteId` → `storePlacesOnRDS` → `updatePlaceId` → `updateAll` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncPlaces` | CURRENT | вызывает `_storePlacesToRDS` первым шагом синхронизации мест, затем `_updatePlacesOnRDS`, `_loadPlacesFromRDS` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_syncFarms`, затем `_syncPlaces` внутри общего sync-прохода авторизованного пользователя, без собственного `try/catch` вокруг них |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет generic-строку ошибки в `DataUpdates` (`_addDataUpdateError`) и эмитит `DataUpdateFailure` |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithoutRemoteId` | CURRENT | выбирает места с `idRemote < 0`; повторно вернёт весь пакет на следующем проходе |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.storePlacesOnRDS` | CURRENT | один POST на весь пакет; `try/catch` вокруг всего вызова и ветка `status != "1"` одинаково возвращают `[]` для всего пакета — частичного успеха не бывает |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.updateAll` | CURRENT | должен был бы персистить новый `idRemote` пакета — в этой ветке не вызывается вовсе |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `PlaceExtension.fromJsonRDSwithLocalId` | CURRENT | сохраняет `id: localId` в успешном `Place` — по этому `id` `updatePlaceId` ищет соответствие |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updatePlaceId` | CURRENT | падает с `TypeError` (null check operator) на первом же месте `oldPlaces`, если для него нет соответствия в `newPlaces` — источник краха всего пакета |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getLocalAnimalsByPlaceId` | CURRENT | read-запрос, выполняется до строки краха; запись животных на этом пути не происходит |

## Критерии приёмки

- Если единственный batch-запрос `PlaceRepository.storePlacesOnRDS` для пакета, отправленного `_storePlacesToRDS`, не получает `status == "1"` (сеть/исключение либо явный отказ сервера), метод возвращает `[]` для **всего** пакета — частичного результата не бывает.
- Следующий вызов `AnimalsRepository.updatePlaceId(res, [])` бросает `TypeError` («Null check operator used on a null value») на первом же месте, встреченном в порядке `oldPlaces` (`res`).
- Это исключение не перехватывается локально — оно долетает необработанным до внешнего `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', ...)` — общий для всего sync-прохода, не специфичный для места или для этого шага.
- `PlaceRepository.updateAll(remotePlaces)` в этом проходе не выполняется вовсе — ни одно место пакета не получает обновлённый локальный `idRemote`.
- На следующем полном sync-проходе `PlaceRepository.getAllWithoutRemoteId()` снова возвращает весь пакет (`idRemote` всё ещё `< 0`).

## Связанные тесты

TBD — теста на уровне `DataUpdateBloc`/`PlaceRepository` для этого сценария (полный sync-проход, [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md)) нет.

Смежное покрытие того же по структуре кода (`firstWhereOrNull(...)!` в `updatePlaceId`), но только успешного пути, не краха: `test/repositories/animals_repository_test.dart`, group `'UC-RA-LS-73 — updateFarmId / updatePlaceId'`, test `'updatePlaceId переносит локальных животных со старого idRemote места на новый'` (будет переименовано, не трогать сейчас). В отличие от `updateFarmId`, для которого в этом же group есть отдельный тест-ловушка на именно этот краш (`'БАГ-ловушка (намеренная, не найдено соответствие new*.id): ...'`), для `updatePlaceId` аналогичного теста на `TypeError` нет вовсе — ни на уровне `AnimalsRepository` в изоляции, ни тем более на уровне `PlaceRepository`/`DataUpdateBloc`.

## Открытые вопросы и ограничения

- Является ли решение отправлять места единым батчем (в отличие от ферм — по одной в цикле) осознанным архитектурным выбором или случайным расхождением между `FarmRepository.storeFarmsOnRDS` и `PlaceRepository.storePlacesOnRDS` — нигде в коде/комментариях не зафиксировано.
- Повторная отправка на сервер уже отправленного (но не подтверждённого локально) пакета мест на следующем sync-проходе может приводить к дублированию записей на сервере — зависит от того, дедуплицирует ли сервер запрос `/places/store`; у `Place` нет поля вроде `guid`, по которому такая дедупликация могла бы опираться на стороне клиента, а есть ли она на сервере — вне зоны видимости этого клиентского кода и этой спеки.
- Является ли этот краш «известным дефектом» с точки зрения продукта или намеренно оставленным поведением (падать громко, чтобы разработчик заметил проблему в логах) — нигде в коде/комментариях этого не зафиксировано.
- `DataUpdateBloc` не переопределяет `Bloc.onError` для отдельного шага синхронизации мест — единственный способ увидеть исходное исключение (а не только generic `DataUpdateFailure`) — это `errorMessage` внутри самого состояния (собирается в `_emitError` из `error`/`stackTrace`) либо строка в `DataUpdates`, а не что-то персонально видимое пользователю про конкретное место.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим чтением кода (`_storePlacesToRDS` → `storePlacesOnRDS` → `AnimalsRepository.updatePlaceId`).
