- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md), [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)

# UC-26 — Sync создания фермы отказывает для одной фермы — крах обрывает персист всего пакета (незадокументированный дефект)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) |
| Сущность | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| Результат | `CREATE_ERROR` |

## Назначение

Тот же sync-шаг, что описан в [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) — `DataUpdateBloc._storeFarmsToRDS` отправляет на сервер локально созданные фермы без `remoteId`, по одной, в цикле (`FarmRepository.storeFarmsOnRDS`). Здесь хотя бы одна ферма из пакета не создаётся на сервере (сетевое исключение либо сервер отвечает без статуса успеха) — и по коду это не заканчивается изолированным пропуском одной этой фермы: следующий шаг того же метода (`PlaceRepository.updateFarmId`) падает с необработанным исключением на этой ферме, что обрывает персист **всего** пакета ферм, отправленных в этом цикле, включая те, что на сервере были созданы успешно.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во время sync-прохода. Прямого пользовательского действия в момент самого отказа нет — sync-проход к этому шагу уже был запущен ранее [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (`DataUpdateStartAll`, диспатчится, например, из `main_page.dart`, `profile_settings_view.dart`, `in_work_page.dart` или `data_update_page.dart`) — дальше проход идёт автоматически, без участия пользователя на уровне отдельного сетевого вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).

## CURRENT

### Основной поток

1. Sync-проход авторизованного пользователя (`DataUpdateBloc._syncAuthData`) доходит до `await _syncFarms()`, который сразу вызывает `DataUpdateBloc._storeFarmsToRDS`.
2. `_storeFarmsToRDS` берёт `res = await _farmRepository.getAllWithoutRemoteId()` — Drift-запрос `FarmRepository.getAllWithoutRemoteId` выбирает все локальные фермы с `remoteId < 0` (`tbl.remoteId.isSmallerThanValue(0)`), т.е. ещё ни разу не синхронизированные. Если список пуст — метод завершается сразу.
3. `remoteFarms = await _farmRepository.storeFarmsOnRDS(res)`: `FarmRepository.storeFarmsOnRDS` идёт по `res` в цикле, для каждой фермы отдельным POST-запросом (`${Constants.registrationServiceApi}/farms/store`, через `ApiClient` с `instanceName: 'farm_rpc'`).
4. Для одной конкретной фермы из пакета вызов заканчивается неудачно — либо `rpcClient.call(message)` бросает исключение (сеть/сервер), либо ответ приходит, но `response['status'] != "1"`. Оба случая внутри `storeFarmsOnRDS` обрабатываются одинаково: `log(...)` и `continue` — эта ферма не добавляется в `result`, цикл переходит к следующей ферме пакета (остальные фермы отправляются независимо от этой неудачи).
5. `storeFarmsOnRDS` возвращает `result` — только фермы, для которых POST завершился `status == "1"`; для каждой такой фермы `FarmExtension.fromJsonRDSwithLocalId` создаёт новый `Farm` с серверным `remoteId`, но с сохранённым `id: farm.id!` (тем же локальным id, что и до отправки — по нему дальше ищется соответствие).
6. `_storeFarmsToRDS` вызывает `await _placeRepository.updateFarmId(res, remoteFarms)`, передавая **весь исходный список** `res` (все фермы, что были в пакете, включая неудавшуюся) как `oldFarms`, и `remoteFarms` (только успешные) как `newFarms`.
7. `PlaceRepository.updateFarmId` идёт по `oldFarms` в цикле; для каждой фермы вычисляет `newRemoteId` через `newFarms.firstWhereOrNull((newFarm) => newFarm.id == farm.id)!.remoteId`. Для неудавшейся фермы соответствия в `newFarms` нет — `firstWhereOrNull` возвращает `null`, а `!` (null-check operator) бросает `TypeError` («Null check operator used on a null value»).
8. Это исключение не перехватывается ни в `PlaceRepository.updateFarmId`, ни в `_storeFarmsToRDS`, ни в `_syncFarms`, ни в `_syncAuthData` — единственный `try/catch` на этом пути находится в самом обработчике `DataUpdateBloc.on<DataUpdateStartAll>`, оборачивающем весь sync-проход целиком.
9. Этот внешний `catch` вызывает `DataUpdateBloc._emitError`, который пишет строку в `DataUpdates` через `_addDataUpdateError` (с тем `_currentDataCategory`/`_currentDataKey`, что были выставлены последними до этого места — не специфичными для фермы или для этого шага, т.к. ни `_syncFarms`, ни `_storeFarmsToRDS` не вызывают `_emitProgress` со своим собственным `dataKey`) и эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')` — общая, не относящаяся конкретно к ферме ошибка всего sync-прохода.
10. Поскольку исключение вылетает из `_placeRepository.updateFarmId` до того, как выполнение дошло до `await _animalsRepository.updateFarmId(res, remoteFarms)` и `await _farmRepository.updateAll(remoteFarms)` (следующие две строки `_storeFarmsToRDS`), ни одна ферма из этого пакета не получает обновлённый локальный `remoteId` в этом проходе — включая те фермы, что реально были созданы на сервере (их `Farm.remoteId` в локальной БД остаётся тем же отрицательным значением, что и до отправки).
11. На следующем полном sync-проходе `FarmRepository.getAllWithoutRemoteId()` снова вернёт весь этот пакет (`remoteId` всё ещё `< 0`) — включая фермы, уже успешно созданные на сервере в упавшем проходе, — и `storeFarmsOnRDS` отправит по ним повторный POST `/farms/store`.

### Альтернативные потоки

- Если в пакете `res` неудачная ферма стоит **перед** успешными по порядку, в котором их вернул `getAllWithoutRemoteId` (порядок Drift-выборки, не связан с тем, какая именно ферма упадёт на сервере), — `PlaceRepository.updateFarmId` бросает исключение на первой же итерации, и ни одна ферма пакета (в том числе успешные) не получает даже частичного обновления `Places.farmId` в этом проходе.
- Если неудачная ферма стоит **после** одной или нескольких успешных, `PlaceRepository.updateFarmId` успевает выполнить `await updateAll(...)` для мест успешных ферм (их `Places.farmId` переписывается на новый серверный id фермы) до того, как дойдёт до неудачной фермы и бросит исключение — но собственная строка этой успешной фермы в `Farms` (`remoteId`) всё равно не обновляется в этом проходе, потому что до `_farmRepository.updateAll(remoteFarms)` выполнение не доходит вовсе (см. шаг 10 основного потока).
- Если в пакете ровно одна ферма и она падает — тот же краш: `newFarms` (пустой список) не содержит соответствия, `firstWhereOrNull` возвращает `null`.
- Не важно, была ли причина неудачи сетевым исключением или ответом сервера с `status != "1"` — `storeFarmsOnRDS` реагирует на них одинаково (`continue`), поэтому обе ветки приводят к одному и тому же дальнейшему краху в `updateFarmId`.
- Идентичный по структуре код есть в `AnimalsRepository.updateFarmId` (тот же паттерн `firstWhereOrNull(...)!`), но в реальном порядке вызовов `_storeFarmsToRDS` он вызывается **после** `PlaceRepository.updateFarmId` — на практике до него выполнение не доходит, потому что `PlaceRepository.updateFarmId` падает раньше.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — сущность, для которой этот use-case описывает отказ создания; после отказа её `remoteId` остаётся отрицательным независимо от того, была ли конкретная ферма реально создана на сервере в этом же проходе.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — `PlaceRepository.updateFarmId` — источник краха; для ферм, обработанных до точки краха, `Places.farmId` уже может быть переписан на новый серверный id фермы, даже когда сама эта ферма в `Farms` остаётся несинхронизированной до следующего успешного прохода.
- Animal — `AnimalsRepository.updateFarmId` (тот же паттерн бага) в этой ветке не выполняется вовсе, крах происходит раньше; полная модель `Animal` специфицируется будущим модулем ANIMAL, не в этой спеке.
- `DataUpdates` (лог sync-прохода) — получает одну строку через `_addDataUpdateError` с generic сообщением об ошибке; сама сущность и модель append-only лога специфицируются будущим модулем SYSTEM, не в этой спеке.

### Бизнес-правила

- Фермы отправляются на сервер по одной, в цикле, а не единым батчем — так же описано в модуле [MOD-3](../modules/MOD-3-FARM.md) и в актор-спеке [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) («частичный успех возможен и не откатывает уже отправленные записи»). Частичный успех действительно возможен на уровне HTTP-вызовов внутри `storeFarmsOnRDS` — но следующий шаг того же метода (`updateFarmId`) не рассчитан на этот частичный успех и падает, а не пропускает несовпавшую ферму.
- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED`, даже для ветки `response['status'] != "1"` (содержательный отказ сервера): этот отказ никогда не доходит до пользователя как осознанно предъявленное решение по конкретной ферме — он теряется сначала в `continue` внутри `storeFarmsOnRDS`, а затем полностью тонет в generic `DataUpdateFailure` всего sync-прохода, вызванном отдельным, не связанным с этой веткой крахом в `updateFarmId`.
- Никакого отдельного retry/backoff-механизма для конкретно этой фермы нет — «повтор на следующем проходе» не оформлен как явная бизнес-логика, это побочный эффект того, что `getAllWithoutRemoteId` при каждом полном проходе просто повторно выбирает все фермы с `remoteId < 0`, не различая «ещё не пробовали» и «уже пробовали и упали».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится статическим чтением кода (`_storeFarmsToRDS` → `storeFarmsOnRDS` → `PlaceRepository.updateFarmId`) и подтверждается существующим тестом на идентичный по структуре баг в `AnimalsRepository.updateFarmId` (см. «Связанные тесты»). Возможное исправление (не давать одной несинхронизированной ферме обрывать персист остальных, синхронизированных в этом же проходе) в рамках этого документирующего прохода не выполняется — это чисто фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._storeFarmsToRDS` | CURRENT | оркестрирует sync создания фермы: `getAllWithoutRemoteId` → `storeFarmsOnRDS` → `updateFarmId` (place, затем animals) → `updateAll` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms` | CURRENT | вызывает `_storeFarmsToRDS` первым шагом синхронизации ферм |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_syncFarms` внутри общего sync-прохода авторизованного пользователя, без собственного `try/catch` вокруг него |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет generic-строку ошибки в `DataUpdates` (`_addDataUpdateError`) и эмитит `DataUpdateFailure` |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllWithoutRemoteId` | CURRENT | выбирает фермы с `remoteId < 0`; повторно вернёт даже успешно созданные в упавшем проходе фермы на следующем проходе |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.storeFarmsOnRDS` | CURRENT | POST по одной ферме за раз; `try/catch` + `continue` на исключение, `continue` на `response['status'] != "1"` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.updateAll` | CURRENT | должен был бы персистить новый `remoteId` успешных ферм — в этой ветке не вызывается вовсе |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `FarmExtension.fromJsonRDSwithLocalId` | CURRENT | сохраняет `id: localId` в успешном `Farm` — по этому `id` `updateFarmId` ищет соответствие |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.updateFarmId` | CURRENT | падает с `TypeError` (null check operator), если для фермы из `oldFarms` нет соответствия в `newFarms` — источник краха всего пакета |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateFarmId` | CURRENT | идентичный по структуре паттерн/баг; в реальном порядке вызовов `_storeFarmsToRDS` не достигается — `PlaceRepository.updateFarmId` падает раньше |

## Критерии приёмки

- Если хотя бы одна ферма из пакета, отправленного `FarmRepository.storeFarmsOnRDS`, не получает `status == "1"` (сеть/исключение либо явный отказ сервера), следующий вызов `PlaceRepository.updateFarmId(res, remoteFarms)` бросает `TypeError` («Null check operator used on a null value») на первой такой ферме, встреченной в порядке `oldFarms`.
- Это исключение не перехватывается локально — оно долетает необработанным до внешнего `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', ...)` — общий для всего sync-прохода, не специфичный для фермы или для этого шага.
- `AnimalsRepository.updateFarmId` и `FarmRepository.updateAll(remoteFarms)` в этом проходе не выполняются вовсе — ни одна ферма пакета (включая успешно созданные на сервере) не получает обновлённый локальный `remoteId`.
- На следующем полном sync-проходе `FarmRepository.getAllWithoutRemoteId()` снова возвращает весь пакет (`remoteId` всё ещё `< 0`), включая фермы, уже успешно созданные на сервере в упавшем проходе.

## Связанные тесты

TBD — теста на уровне `DataUpdateBloc`/`FarmRepository`/`PlaceRepository` для этого сценария (полный sync-проход, [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md)) нет.

Смежное покрытие того же по структуре бага (несовпадение `oldFarms`/`newFarms` по `id`), но на уровне `AnimalsRepository` в изоляции, не через реальный `DataUpdateBloc`-пайплайн: `test/repositories/animals_repository_test.dart`, group `'UC-RA-LS-73 — updateFarmId / updatePlaceId'`, test `'БАГ-ловушка (намеренная, не найдено соответствие new*.id): firstWhereOrNull(...)! падает с null check error, если для старой фермы/места нет соответствия в newFarms/newPlaces'` (будет переименовано, не трогать сейчас). Этот тест воспроизводит крах именно на `AnimalsRepository.updateFarmId`, а не на `PlaceRepository.updateFarmId`, который в реальном порядке вызовов `_storeFarmsToRDS` падает первым — теста на `PlaceRepository.updateFarmId` для этого случая нет вовсе, ни под каким именем.

## Открытые вопросы и ограничения

- Порядок обработки в `oldFarms`/`res` определяется порядком, который вернул `FarmRepository.getAllWithoutRemoteId` (Drift `selectCurrent()..where(remoteId < 0)`), и никак не связан с тем, какая именно ферма упадёт на сервере, — поэтому наблюдаемые побочные эффекты (успели ли места каких-то ферм получить новый `farmId` до краха) не детерминированы с точки зрения бизнес-логики, только с точки зрения порядка выборки из БД. Не проверено эмпирически на реальном запуске — вывод сделан чтением кода.
- Возможное рассогласование `Places.farmId` (уже переписан на новый серверный id, если эта ферма шла в списке раньше упавшей) и `Farms.remoteId` (всё ещё старое отрицательное значение, потому что `_farmRepository.updateAll` в этом проходе не вызывается) для ферм, обработанных до точки краха, — не проверено эмпирически, только по чтению кода.
- Повторная отправка на сервер уже успешно созданных в упавшем проходе ферм на следующем sync-проходе может приводить к дублированию фермы на сервере — зависит от того, дедуплицирует ли сервер запрос `/farms/store` (например по `guid`), что вне зоны видимости этого клиентского кода и этой спеки.
- Является ли этот краш «известным дефектом» с точки зрения продукта или намеренно оставленным поведением (падать громко, чтобы разработчик заметил проблему в логах) — нигде в коде/комментариях этого не зафиксировано. Тест `test/repositories/animals_repository_test.dart` называет идентичный по структуре случай «БАГ-ловушка (намеренная)», что похоже скорее на осознанную фиксацию уже существующего поведения тестом, чем на продуктовое решение о желаемом поведении.
- `DataUpdateBloc` не переопределяет `Bloc.onError` для отдельного шага синхронизации ферм — единственный способ увидеть исходное исключение (а не только generic `DataUpdateFailure`) — это `errorMessage` внутри самого состояния (собирается в `_emitError` из `error`/`stackTrace`) либо строка в `DataUpdates`, а не что-то персонально видимое пользователю про конкретную ферму.
