- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md), [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)

# UC-27 — Система синхронизирует правку фермы, сервер принимает обновление

## Назначение

Во время полного sync-прохода система отправляет на сервер локальные правки
уже синхронизированных ферм, помеченные `needUpdate: true` — правки, ранее
внесённые пользователем при редактировании фермы ([EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)) — и сервер
принимает каждую без ошибки. Это завершает цикл, начатый локальным
редактированием: правка перестаёт считаться неотправленной.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система (sync-проход). Действует не по прямой команде
пользователя на этот конкретный шаг: сам полный проход запущен пользователем
один раз (`DataUpdateStartAll`), дальше `DataUpdateBloc` идёт по шагам
автоматически, без участия человека на уровне отдельного HTTP-вызова.

## CURRENT

### Основной поток

1. Полный sync-проход уже прошёл проверку сети и дошёл до
   `DataUpdateBloc._syncAuthData` → `_syncFarms()`. Внутри `_syncFarms` порядок
   фиксирован: сначала `_storeFarmsToRDS()` (новые фермы), затем
   `_updateFarmsOnRDS()` (этот сценарий), затем `_loadFarmsFromRDS()` (полная
   перезагрузка списка, [EVT-14](../events/EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md)).
2. `_updateFarmsOnRDS` вызывает `FarmRepository.getAllToUpdate()` — запрос к
   локальной таблице `Farms` с условием `needUpdate.equals(true) &
   remoteId.isNotNull()`. Пустой результат просто завершает шаг без сетевого
   вызова (лог `No farms to update`) — не сценарий этого файла.
3. Непустой список `farmsToUpdate` передаётся в
   `FarmRepository.updateFarmsOnRDS(farms)`. Метод идёт по фермам циклом,
   **по одной, не батчем**: для каждой — `PUT
   {Constants.registrationServiceApi}/farms/update` с телом
   `farm.toJsonRDS()` через `ApiClient(instanceName: 'farm_rpc')`.
4. Сервер отвечает `status == "1"` (строковое сравнение) для каждой фермы
   батча → локальная переменная `success` остаётся `true` на каждой итерации,
   цикл доходит до конца без `break`. Метод возвращает `true`.
5. `DataUpdateBloc._updateFarmsOnRDS` получает `isUpdated == true` и вызывает
   `_farmRepository.updateAll(farmsToUpdate.map((f) =>
   f.copyWith(needUpdate: false)).toList())` — **одним вызовом, для всего
   исходного батча целиком**, а не по одной ферме синхронно с её отдельным
   сетевым подтверждением. `BaseRepository.updateAll` → `BaseDao.updAll`
   оборачивает построчный `upd()` (drift `.replace()` по первичному ключу) в
   одну транзакцию.
6. Локально каждая обновлённая ферма получает `needUpdate: false` — следующий
   sync-проход больше не подберёт её в `getAllToUpdate()`, пока она не будет
   отредактирована заново.

### Альтернативные потоки

- **Пустой список к обновлению.** `getAllToUpdate()` возвращает `[]` → шаг
  завершается без сетевого вызова и без изменения локальных данных. Не
  UPDATE-сценарий (нечего обновлять), не описан этим файлом.
- **Отказ сервера или исключение на одной из ферм батча.** Первая же неудача
  (`status != "1"` либо пойманное исключение внутри
  `updateFarmsOnRDS`) ставит `success = false` и **прерывает цикл (`break`)**
  — фермы батча, идущие после неё, в этом проходе не отправляются вовсе.
  `DataUpdateBloc` получает `isUpdated == false` и не вызывает `updateAll` —
  `needUpdate` не сбрасывается ни у одной фермы батча, **включая те, что были
  успешно приняты сервером до точки останова**: партиальный успех при
  обновлении не поддерживается, в отличие от `storeFarmsOnRDS` (создание),
  где каждая ферма коммитится локально независимо. Отдельный сценарий,
  `RESULT = UPDATE_ERROR`, не описан этим файлом.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — сущность сегмента `ENT` в id: поле `needUpdate`
  переходит `true → false` для каждой фермы батча, одним транзакционным
  вызовом на весь батч, не по одной ферме синхронно с её сетевым ответом.

### Бизнес-правила

- Фермы отправляются на `/farms/update` по одной, в цикле, не единым
  батч-запросом — так же, как `storeFarmsOnRDS` для создания.
- Успех отдельного запроса определяется исключительно строковым сравнением
  `response['status'] == "1"` — тело ответа дальше не используется и не
  перезаписывает локальные поля фермы; авторитетна локальная копия, ушедшая в
  запросе. Асимметрично `FarmRepository.getAllFarmsAndPlacesFromRDS`, который
  в том же файле принимает `status` и как строку `"1"`, и как число `1`.
- `getAllToUpdate()` фильтрует по `needUpdate == true` и `remoteId IS NOT
  NULL` — не по `remoteId >= 0`. По инварианту [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) отрицательный
  `remoteId` тоже «не null» (ферма, ещё не отправленная на сервер). В штатном
  проходе это не создаёт проблемы, потому что `_storeFarmsToRDS` выполняется
  раньше в том же `_syncFarms` и явно обнуляет `needUpdate` для каждой
  успешно отправленной новой фермы (`FarmExtension.fromJsonRDSwithLocalId`
  жёстко ставит `needUpdate: false`) — см. «Открытые вопросы» для случая,
  когда сам `store`-шаг для записи проваливается в этом же проходе.
- Локальный сброс `needUpdate` — это «всё или ничего» для целого батча:
  либо все фермы, переданные в `updateFarmsOnRDS`, подтверждены сервером и
  разом получают `needUpdate: false`, либо ни одна не получает.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде; тестового покрытия для него нет,
см. «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms` | CURRENT | фиксирует порядок шага фермы внутри прохода: store → update → reload |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._updateFarmsOnRDS` | CURRENT | получает фермы к обновлению, отправляет их, при успехе сбрасывает `needUpdate` локально одним батчем |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllToUpdate` | CURRENT | фильтр `needUpdate == true & remoteId IS NOT NULL` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.updateFarmsOnRDS` | CURRENT | цикл `PUT {registrationServiceApi}/farms/update` по одной ферме; `break` на первой неудаче |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `FarmExtension.toJsonRDS` | CURRENT | тело `PUT`-запроса (поля `createdAt`/`updatedAt` закомментированы, не отправляются) |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `Farms.needUpdate` | CURRENT | boolean-колонка, флаг «есть неотправленная правка» |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | делегирует в `dao.updAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll` | CURRENT | транзакция: `upd(i)` (drift `.replace()` по первичному ключу) на каждый элемент батча |

## Критерии приёмки

- Хотя бы одна локальная ферма с `needUpdate == true` и не-`null` `remoteId`
  → `getAllToUpdate()` включает её в батч на отправку.
- Каждая ферма батча отправляется отдельным `PUT
  {registrationServiceApi}/farms/update` с телом `toJsonRDS()`; сервер
  отвечает `status == "1"` на каждую → `updateFarmsOnRDS` возвращает `true`.
- `true` → все фермы исходного батча получают `needUpdate: false` одним
  вызовом `updateAll` (одна транзакция, по строке на ферму).
- Тело ответа сервера не парсится и не перезаписывает локальные поля
  фермы — локальная копия остаётся авторитетной.
- Если хотя бы одна ферма батча отвечает `status != "1"` (или бросает
  исключение) — цикл прерывается (`break`), результат `false`, `needUpdate`
  не сбрасывается ни у одной фермы батча, включая уже принятые сервером до
  точки останова.

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` существует, но
покрывает только конструирование `DataUpdateBloc` и обработку
`DataUpdateClear` — сам sync-шаг фермы (`_syncFarms`/`_updateFarmsOnRDS`) не
затронут ни одним тестом.

## Открытые вопросы и ограничения

- **Партиальный успех при обновлении не поддерживается.** `break` на первой
  неудаче теряет локальный прогресс уже успешно отправленных до неё ферм —
  их `needUpdate` остаётся `true`, хотя сервер уже принял правку. До
  следующего прохода они будут отправлены повторно (для сервера идемпотентно,
  раз это `update`, а не `create`, но лишний трафик и на время
  рассинхронизированный локальный сигнал «не отправлено»).
- **Фильтр `getAllToUpdate()` по `remoteId.isNotNull()`, а не `remoteId >=
  0`.** Если для конкретной фермы `store`-шаг (`storeFarmsOnRDS`) проваливается
  в этом же проходе (внутренний `continue` на ошибке — ферма не попадает в
  `updateAll` внутри `_storeFarmsToRDS` и остаётся с отрицательным
  `remoteId`), а её `needUpdate` почему-то `true`, тот же проход подберёт её
  в `_updateFarmsOnRDS` и попытается выполнить `PUT /farms/update` с
  отрицательным `id` в теле запроса. Поведение сервера на такой запрос не
  проверялось в рамках этого use-case.
- **Асимметрия сравнения `status`.** `updateFarmsOnRDS` принимает только
  строковое `"1"`, тогда как `getAllFarmsAndPlacesFromRDS` в том же файле
  принимает и строку `"1"`, и число `1` — расхождение не задокументировано
  как осознанное решение.
