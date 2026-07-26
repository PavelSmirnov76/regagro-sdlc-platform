- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-19](../events/EVT-19-PLACE-UPDATE-SYNCED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-39 — Система синхронизирует правку отделения, сервер принимает обновление

## Назначение

Во время полного sync-прохода система одним запросом отправляет на сервер
локальные правки уже синхронизированных отделений
([ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)), помеченные `needUpdate:
true` — правки, ранее внесённые пользователем при редактировании структуры
фермы ([EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md)) — и сервер
принимает весь пакет без ошибки. Это завершает цикл, начатый локальным
редактированием: правка перестаёт считаться неотправленной.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система (sync-проход).
Действует не по прямой команде пользователя на этот конкретный шаг: сам
полный проход запущен пользователем один раз (`DataUpdateStartAll`), дальше
`DataUpdateBloc` идёт по шагам автоматически, без участия человека на уровне
отдельного HTTP-вызова.

## CURRENT

### Основной поток

1. Полный sync-проход уже прошёл проверку сети и дошёл до
   `DataUpdateBloc._syncAuthData`, которая вызывает `_deletePlacesFromRDS()`,
   затем `_syncFarms()`, затем `_syncPlaces()` — фиксированный порядок,
   безусловный. Внутри `_syncPlaces` порядок тоже фиксирован:
   `_storePlacesToRDS()` (новые места, [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md))
   → `_updatePlacesOnRDS()` (этот сценарий) → `_loadPlacesFromRDS()` (полная
   перезагрузка списка, [EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md)).
   Предпосылка основного потока — предыдущий шаг (`_storePlacesToRDS`)
   завершился без исключения (типично — либо нет мест без `idRemote`, либо
   их отправка прошла успешно); см. «Альтернативные потоки» для случая,
   когда это не так.
2. `_updatePlacesOnRDS` вызывает `PlaceRepository.getAllToUpdate()` — запрос
   к локальной таблице `Places` с условием `needUpdate.equals(true) &
   idRemote.isNotNull()`. Пустой результат просто завершает шаг без
   сетевого вызова (лог `No places to update`) — не сценарий этого файла.
3. Непустой список `placesToUpdate` передаётся в
   `PlaceRepository.updatePlacesOnRDS(places)`. В отличие от фермы
   ([UC-27](UC-27-ACTOR-4-EVT-13-ENT-9-UPDATE_OK-IN-FARM.md), которая
   отправляет по одной ферме циклом), места **не** отправляются по одному:
   весь список сериализуется одним телом `{"places":
   places.map((e) => e.toJsonRDS()).toList()}` и уходит **единственным**
   `PUT {Constants.registrationServiceApi}/places/update` через
   `ApiClient(instanceName: 'farm_rpc')`.
4. `PlaceExtension.toJsonRDS()` на каждое место в списке формирует
   `{id: idRemote, farm_id: farmId, name: name, description: ...}` — с
   особым правилом для `description`: если оно `null` или пустая строка, в
   теле уходит строка `'0'`, а не `null`/`''`.
5. Сервер отвечает `status == "1"` (строковое сравнение, единственный
   ответ на весь пакет сразу, не по одному месту) → `updatePlacesOnRDS`
   логирует `Success` и возвращает `true`.
6. `DataUpdateBloc._updatePlacesOnRDS` получает `isUpdated == true` и
   вызывает `_placeRepository.updateAll(placesToUpdate.map((place) =>
   place.copyWith(needUpdate: false)).toList())` — одним вызовом, для всего
   исходного списка целиком. `BaseRepository.updateAll` → `BaseDao.updAll`
   оборачивает построчный `upd()` (drift `.replace()` по локальному
   первичному ключу `id`) в одну транзакцию.
7. Локально каждое обновлённое место получает `needUpdate: false` —
   следующий sync-проход больше не подберёт его в `getAllToUpdate()`, пока
   оно не будет отредактировано заново. Тело ответа сервера дальше не
   парсится и не перезаписывает локальные поля места — авторитетна
   локальная копия, ушедшая в запросе.
8. Шаг 3 модуля `_loadPlacesFromRDS()` ([EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md))
   выполняется сразу следующим, безусловно — вне зависимости от результата
   этого шага; в сценарии этого файла (успех) его эффект не расходится с
   уже установленным состоянием (`needUpdate: false` уже сброшен).

### Альтернативные потоки

- **Пустой список к обновлению.** `getAllToUpdate()` возвращает `[]` → шаг
  завершается без сетевого вызова и без изменения локальных данных. Не
  UPDATE-сценарий (нечего обновлять), не описан этим файлом.
- **Отказ сервера или исключение на единственном запросе.** `status !=
  "1"` либо пойманное исключение внутри `updatePlacesOnRDS` возвращают
  `false` для **всего** списка разом — здесь нет цикла и нет частичного
  успеха на уровне отдельных мест (в отличие от фермы, где `break`
  прерывает цикл после уже принятых сервером записей: тут принять
  «частично» физически невозможно, так как запрос один). `needUpdate` не
  сбрасывается ни у одного места из списка. Отдельный сценарий, `RESULT =
  UPDATE_ERROR`, не описан этим файлом.
- **Предыдущий шаг (`_storePlacesToRDS`) бросает исключение раньше, чем
  этот шаг вообще начинается.** Если в системе есть места без `idRemote`
  (`getAllWithoutRemoteId()` непусто) и `PlaceRepository.storePlacesOnRDS`
  возвращает `[]` (сетевая ошибка или `status != "1"`),
  `AnimalsRepository.updatePlaceId(res, [])` бросает `Null check operator
  used on a null value` на первой же итерации (`firstWhereOrNull(...)!`
  возвращает `null` для пустого `remotePlaces`) — исключение
  пробрасывается наружу через `_storePlacesToRDS` → `_syncPlaces`, и
  `_updatePlacesOnRDS` (этот сценарий) в этом проходе **не выполняется
  вовсе**. Это предпосылочный сбой соседнего шага
  ([EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md)), не
  описывается подробнее здесь — см. «Открытые вопросы».

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность
  сегмента `ENT` в id: поле `needUpdate` переходит `true → false` для
  каждого места списка, одним транзакционным вызовом на весь список
  целиком, не по одному месту синхронно с его сетевым ответом (которого у
  отдельного места и нет — ответ один на весь пакет).
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — только контекст:
  `Place.farmId` в этом сценарии не меняется; синхронизация ферм
  (`_syncFarms`) выполняется раньше в том же `_syncAuthData`, но независимо
  от этого шага.

### Бизнес-правила

- Места, требующие обновления на сервере, отправляются **единым batch-
  запросом** `PUT /places/update` с телом-массивом — не по одному месту в
  цикле, как фермы. Это расходится с обобщающей формулировкой в
  [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) («Фермы и места
  отправляются на сервер по одной, в цикле, не единым батчем») — по факту
  чтения `PlaceRepository.updatePlacesOnRDS`/`storePlacesOnRDS` эта
  характеристика верна только для ферм; см. «Открытые вопросы».
- Успех/неудача определяется исключительно строковым сравнением
  `response['status'] == "1"` для всего пакета сразу — тело ответа дальше
  не используется и не перезаписывает локальные поля мест; авторитетна
  локальная копия, ушедшая в запросе.
- `getAllToUpdate()` фильтрует по `needUpdate == true` и `idRemote IS NOT
  NULL` — не по `idRemote >= 0`. По инварианту
  [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) отрицательный `idRemote`
  тоже «не null» (место, ещё не отправленное на сервер).
- Локальный сброс `needUpdate` — это «всё или ничего» для целого списка:
  либо все места, переданные в `updatePlacesOnRDS`, подтверждены
  единственным сетевым ответом и разом получают `needUpdate: false`, либо
  ни одно не получает — здесь это буквальное следствие того, что запрос
  физически один, а не результат явной стратегии «остановиться на первой
  неудаче», как у фермы.
- `PlaceExtension.toJsonRDS()` подставляет строку `'0'` вместо `null`/``''``
  для поля `description`, когда оно не задано или пусто — специфика
  сериализации Place, не имеющая аналога в `FarmExtension.toJsonRDS()`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде; тестового покрытия для него
нет, см. «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксирует порядок прохода: удаление мест → sync ферм → sync мест |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncPlaces` | CURRENT | фиксирует порядок шага мест: store → update → reload |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._updatePlacesOnRDS` | CURRENT | получает места к обновлению, отправляет их, при успехе сбрасывает `needUpdate` локально одним батчем |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllToUpdate` | CURRENT | фильтр `needUpdate == true & idRemote IS NOT NULL` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.updatePlacesOnRDS` | CURRENT | единственный `PUT {registrationServiceApi}/places/update` с телом-массивом на весь список сразу (не цикл) |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `PlaceExtension.toJsonRDS` | CURRENT | тело запроса на место; `description` подставляется как `'0'`, если `null`/пусто |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places.needUpdate` | CURRENT | boolean-колонка, флаг «есть неотправленная правка», дефолт `false` |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | делегирует в `dao.updAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll` | CURRENT | транзакция: `upd(i)` (drift `.replace()` по первичному ключу) на каждый элемент списка |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.storePlacesOnRDS` | CURRENT | соседний шаг того же `_syncPlaces`, выполняется непосредственно перед этим сценарием; при неудаче возвращает `[]` для всего списка сразу |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updatePlaceId` | CURRENT | вызывается внутри `_storePlacesToRDS`; `firstWhereOrNull(...)!` бросает исключение, если `storePlacesOnRDS` вернул `[]`, а список мест без `idRemote` был непуст — это не даёт этому сценарию выполниться в том же проходе |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditPlace` | CURRENT | путь, которым локальная правка (предпосылка сценария) выставляет `needUpdate: true` — см. [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API мест, используемый в PUT-запросе |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент, через который идёт запрос этого сценария |

## Критерии приёмки

- Хотя бы одно локальное место с `needUpdate == true` и не-`null`
  `idRemote` → `getAllToUpdate()` включает его в список на отправку.
- Список мест отправляется единственным `PUT
  {registrationServiceApi}/places/update` с телом-массивом
  `{"places": [...]}`; сервер отвечает `status == "1"` на весь пакет →
  `updatePlacesOnRDS` возвращает `true`.
- `true` → все места исходного списка получают `needUpdate: false` одним
  вызовом `updateAll` (одна транзакция, по строке на место).
- Тело ответа сервера не парсится и не перезаписывает локальные поля
  места — локальная копия остаётся авторитетной.
- Если единственный запрос отвечает `status != "1"` (или бросает
  исключение) — результат `false`, `needUpdate` не сбрасывается ни у
  одного места списка.

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` существует, но
покрывает только конструирование `DataUpdateBloc` и обработку
`DataUpdateClear` — сам sync-шаг мест (`_syncPlaces`/`_updatePlacesOnRDS`)
не затронут ни одним тестом; `grep -rl "updatePlacesOnRDS" test/` не
находит ни одного файла.

## Открытые вопросы и ограничения

- **Обобщение в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) не
  подтверждается кодом для мест.** Актёрская спека утверждает «Фермы и
  места отправляются на сервер по одной, в цикле, не единым батчем» — по
  факту чтения `PlaceRepository.updatePlacesOnRDS` и
  `PlaceRepository.storePlacesOnRDS` места отправляются **единым
  batch-запросом**, без цикла; поштучно, в цикле, отправляются только
  фермы (`FarmRepository.storeFarmsOnRDS`/`updateFarmsOnRDS`). Заморожено
  и не редактируется этим проходом — фиксируется здесь как наблюдение для
  следующей ревизии графа спек, как и аналогичное наблюдение в
  [UC-32](UC-32-ACTOR-1-EVT-16-ENT-10-UPDATE_OK-IN-FARM.md) про путь
  `place_create_cubit.dart`.
- **«Всё или ничего» на весь список, а не на первую неудачу.** В отличие от
  фермы ([UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)), где
  `break` теряет прогресс уже принятых сервером записей после первой
  отказавшей, для мест такого прогресса в принципе не существует — запрос
  один, поэтому либо весь список подтверждён, либо ни одна запись. Не
  однозначно лучше или хуже: не бывает частичного успеха, но и не бывает
  ситуации, где часть списка успела дойти до сервера, а другая часть — нет.
- **Взаимодействие с соседним шагом создания.** Если
  `_storePlacesToRDS` (шаг непосредственно перед этим) падает исключением
  из-за `AnimalsRepository.updatePlaceId`'s `firstWhereOrNull(...)!` на
  пустом `remotePlaces`, этот сценарий не выполняется вовсе в том же
  проходе, а исключение всплывает до внешнего `try/catch` в
  `on<DataUpdateStartAll>`, завершая проход `DataUpdateFailure`. Сам этот
  сбой — предмет отдельного use-case для
  [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md)
  (`RESULT = CREATE_ERROR`), не раскрывается здесь подробнее; упомянут
  только как предпосылочное ограничение достижимости сценария этого файла.
- **Претензия [UC-32](UC-32-ACTOR-1-EVT-16-ENT-10-UPDATE_OK-IN-FARM.md) о
  безопасности повторной правки ещё не отправленного места требует
  уточнения.** [UC-32](UC-32-ACTOR-1-EVT-16-ENT-10-UPDATE_OK-IN-FARM.md)
  утверждает, что `needUpdate: true` на месте с `idRemote < 0` «ничего не
  запускает немедленно», так как отправка идёт по отдельному пути
  (`getAllWithoutRemoteId`, не `getAllToUpdate`). Это верно только пока
  `_storePlacesToRDS` успевает обработать такое место раньше
  `_updatePlacesOnRDS` в том же проходе. Если batch-запрос
  `storePlacesOnRDS` для этого места падает (см. пункт выше) настолько
  тихо, что исключение не бросается (гипотетически, если `updatePlaceId`
  будет исправлен отдельно), место осталось бы с отрицательным `idRemote`
  и `needUpdate: true`, а `getAllToUpdate()` (`idRemote IS NOT NULL`, без
  проверки знака) подобрал бы его и попытался бы выполнить `PUT
  /places/update` с отрицательным `id` в теле запроса. Поведение сервера
  на такой запрос не проверялось в рамках этого use-case.
