# UC-37 — Sync-проход успешно отправляет новые места на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md) |
| Сущность | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все
локально созданные места, у которых ещё нет серверного id, одним батч-запросом,
и запрос завершается успехом. Локальный `idRemote` каждого места заменяется на
серверный, а ещё не отправленные локальные животные, ссылавшиеся на старый
(отрицательный) `idRemote` места, каскадно переписываются на новый. Happy-path
сценарий события [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md)
(`place.create_synced`).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)) один раз (`DataUpdateStartAll`),
но в каждом отдельном сетевом вызове этого сценария человек не участвует.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик сначала проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (это другая ветка, не
   часть этого use-case).
2. При наличии сети и после загрузки справочников — если
   `_authRepository.isAuthorized()` — вызывается
   `DataUpdateBloc._syncAuthData`.
3. `_syncAuthData` вызывает шаги в фиксированном порядке:
   `_deletePlacesFromRDS()`, затем `_syncFarms()`, затем `_syncPlaces()` —
   отправка новых мест идёт последней из этой тройки, после синхронизации
   ферм.
4. `_syncPlaces` вызывает `_storePlacesToRDS()` первым шагом (до
   `_updatePlacesOnRDS()` и `_loadPlacesFromRDS()`).
5. `_storePlacesToRDS` запрашивает `PlaceRepository.getAllWithoutRemoteId()` —
   все локальные места с `idRemote < 0` (созданные локально, ещё не
   отправленные). Если список пуст — метод возвращается сразу, ничего дальше
   не выполняется (в этом проходе [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md)
   фактически не происходит — не этот сценарий).
6. Для непустого списка `res` вызывается
   `PlaceRepository.storePlacesOnRDS(res)`. В отличие от ферм
   ([UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md)) это **один**
   `POST {registrationServiceApi}/places/store` с телом, содержащим массив
   всех мест сразу (`{"places": [...]}`), а не цикл из отдельных запросов на
   каждое место. В этом (`CREATE_OK`) сценарии ответ — `status == "1"`, а
   `response['data']` — список той же длины, что и `res`, в том же порядке;
   для каждого элемента `PlaceExtension.fromJsonRDSwithLocalId(data[index],
   places[index].id!)` строит новый `Place` с тем же локальным `id` (взятым
   позиционно из `res`, не из ответа сервера), но с `idRemote` и прочими
   полями из ответа. Результат копится в `remotePlaces`, длина которого в
   этом сценарии равна длине `res`.
7. `AnimalsRepository.updatePlaceId(res, remotePlaces)` — для каждого места
   из `res` находит локальных (`id < 0`), ещё не отправленных животных
   (`dao.getLocalAnimalsByPlaceId(place.idRemote!)`) с `placeId`, равным
   старому `idRemote` этого места, ищет соответствующее новое место в
   `remotePlaces` по совпадению локального `id`, и переписывает `placeId`
   этих животных на новый серверный `idRemote`. Вызов `updateAll(...)` внутри
   цикла этого метода **не имеет `await`** (см. «Открытые вопросы» — та же
   особенность, что и в `AnimalsRepository.updateFarmId`, см.
   [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md)).
8. `PlaceRepository.updateAll(remotePlaces)` — `dao.updAll` в транзакции; для
   каждого места `BaseDao.upd` делает `updateCurrent().replace(item)` —
   построчный `UPDATE` по совпадению локального `id` (PK), заменяя `idRemote`
   и прочие поля (из шага 6) в уже существующей локальной строке. Место в
   базе остаётся той же строкой (тот же локальный `id`), но теперь с
   положительным `idRemote`.
9. `_syncPlaces` продолжает `_updatePlacesOnRDS()` и `_loadPlacesFromRDS()` —
   вне рамок этого use-case (обновление уже синхронизированных мест и полная
   перезагрузка списка мест с сервера — другие события,
   [EVT-19](../events/EVT-19-PLACE-UPDATE-SYNCED-IN-FARM.md)/[EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md)).

В отличие от Farm (`FarmRepository.updateFarmId` каскадно переписывает и
`Place.farmId` — [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md)), у
`updatePlaceId` нет каскада на другие сущности модуля FARM — Place ни на что
внутри этого модуля дальше не ссылается, каскад идёт только на Animal.

### Альтернативные потоки

- `getAllWithoutRemoteId()` пуст (нет локально созданных мест) →
  `_storePlacesToRDS` возвращается сразу, сетевой вызов не выполняется —
  вырожденный случай «нечего синхронизировать», не этот сценарий.
- Отказ батча целиком (ответ `status != "1"` либо исключение при вызове) →
  `storePlacesOnRDS` возвращает `[]` для **всего** списка сразу — это не
  частичный отказ, как у ферм (там `continue` пропускает одну ферму, не
  трогая остальные, см. [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md)),
  а all-or-nothing по всей пачке мест этого прохода; отдельный `ERROR`
  сценарий, не входит в этот `CREATE_OK` use-case, где предполагается, что
  **вся** отправленная в этом проходе пачка мест получает успех.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — основная сущность
  перехода: `idRemote` заменяется на серверный, прочие поля перезаписываются
  данными ответа; локальный `id` и локальные флаги (`needUpdate`,
  `isDeleted`) этим шагом не меняются.
- Animal — `placeId` локальных (`id < 0`) животных, ссылавшихся на старый
  `idRemote` места, переписывается тем же проходом
  (`AnimalsRepository.updatePlaceId`). Сущность принадлежит ещё не
  специфицированному модулю ANIMAL (см. границу
  [MOD-3](../modules/MOD-3-FARM.md), «что модуль explicitly не владеет») —
  отдельного `ENT`-id для неё в дереве спек пока нет.

### Бизнес-правила

- Места одного прохода отправляются **одним** батч-запросом, не по одному в
  цикле (в отличие от ферм) — см. расхождение с формулировкой ограничения
  [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) в «Открытые вопросы».
- Сопоставление ответа сервера с отправленными местами — позиционное, по
  индексу массива (`data[index]` ↔ `places[index]`), не по id из ответа;
  предполагает, что сервер возвращает элементы в том же порядке и той же
  длине, что и запрос.
- Каскад на животных выбирает только локальные (`id < 0`), ещё не
  отправленные записи; уже синхронизированное животное со старым
  (отрицательным) `placeId` этим запросом не найдётся — то же ограничение,
  что и у ферм.
- `PlaceRepository.updateAll` в этом шаге обновляет только места, успешно
  вернувшиеся из `storePlacesOnRDS` (`remotePlaces`); при полном успехе это
  все места из `res`. Место, отсутствующее в этом списке (весь батч
  отказал), в этом шаге никак не меняется и останется в
  `getAllWithoutRemoteId()` на следующем проходе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде. Тестового покрытия на уровне
`data_update_bloc`/`PlaceRepository.storePlacesOnRDS` нет (см. «Связанные
тесты») — это факт отсутствия теста, а не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети, запуск `_syncAuthData` при `isAuthorized` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | последовательность sync-шагов для авторизованного пользователя: `_deletePlacesFromRDS` → `_syncFarms` → `_syncPlaces` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncPlaces` | CURRENT | вызывает `_storePlacesToRDS` первым шагом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._storePlacesToRDS` | CURRENT | оркестрация: получить места без `idRemote`, отправить батчем, каскадно обновить Animal, сохранить |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithoutRemoteId` | CURRENT | выборка мест с `idRemote < 0` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.storePlacesOnRDS` | CURRENT | один `POST {registrationServiceApi}/places/store` с телом-массивом всех мест; сопоставление ответа с запросом по индексу |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `PlaceExtension.fromJsonRDSwithLocalId` | CURRENT | строит `Place` с прежним локальным `id` и новым `idRemote`/полями из ответа сервера |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updatePlaceId` | CURRENT | каскадно переписывает `placeId` у локальных (`id < 0`) животных; вызов `updateAll` внутри не awaited |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getLocalAnimalsByPlaceId` | CURRENT | выборка локальных животных по `placeId` |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | делегирует в `dao.updAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `BaseDao.upd` | CURRENT | построчный `UPDATE` по PK в транзакции (`updateCurrent().replace`) |

## Критерии приёмки

- При запуске полного sync-прохода (`DataUpdateStartAll`) авторизованным
  пользователем, при наличии сети, для всех локальных мест с `idRemote < 0`
  выполняется один `POST {registrationServiceApi}/places/store` с телом,
  содержащим все эти места.
- Если ответ сервера — `status == "1"` и `data` той же длины и в том же
  порядке, что и запрос, после прохода каждое такое место в локальной БД
  имеет `idRemote` сервера вместо прежнего отрицательного значения, тот же
  локальный `id`, и прочие поля, обновлённые данными ответа.
- Все локальные (`id < 0`) животные, у которых `placeId` равнялся старому
  `idRemote` такого места, после прохода имеют `placeId`, равный новому
  серверному `idRemote` того же места.
- `PlaceRepository.getAllWithoutRemoteId()` после успешного прохода для этих
  мест возвращает список без них (они больше не входят в него, так как
  `idRemote` уже не отрицателен).

## Связанные тесты

`TBD — теста нет` на уровне `data_update_bloc`/`PlaceRepository.storePlacesOnRDS`.
Файл `test/blocs/data_update_bloc_test.dart` существует и мокает
`PlaceRepository` (`MockPlaceRepository`), но не содержит ни одного
`group()`/`test()`, проверяющего `_storePlacesToRDS`/`_syncPlaces` —
единственные тесты в файле проверяют конструирование блока и
`DataUpdateClear`.

Каскадный шаг (шаг 7, `AnimalsRepository.updatePlaceId`) отдельно покрыт
репозиторным юнит-тестом — `test/repositories/animals_repository_test.dart`,
group `'UC-RA-LS-73 — updateFarmId / updatePlaceId'`, test `'updatePlaceId переносит
локальных животных со старого idRemote места на новый'`. Этот тест проверяет
именно `AnimalsRepository.updatePlaceId` в изоляции, не
`PlaceRepository.storePlacesOnRDS` и не оркестрацию `_storePlacesToRDS`
целиком — частичное, не полное покрытие этого use-case.

`test/pages/farms_and_places_bloc_test.dart` (группы `UC-1`…`UC-12`, старая
нумерация, будет переименовано, не трогать сейчас), `test/pages/farm_create_cubit_test.dart`,
`test/pages/place_create_cubit_test.dart` (group `'PlaceCreateCubit.removePlace'`
и др.) — тесты локального CRUD/UI-cubit (`PlaceCreateCubit`), не
sync-прохода, инициированного [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md),
и потому не являются тестами этого use-case.

## Открытые вопросы и ограничения

- **Расхождение с зафиксированным ограничением [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md):**
  его секция «Ограничения» утверждает «Фермы и места отправляются на сервер
  по одной, в цикле, не единым батчем — частичный успех возможен и не
  откатывает уже отправленные записи». Для мест это не подтверждается кодом:
  `PlaceRepository.storePlacesOnRDS` отправляет один `POST .../places/store`
  с массивом всех мест сразу (в отличие от `FarmRepository.storeFarmsOnRDS`,
  которая действительно шлёт фермы по одной в цикле — см.
  [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md) и
  `sdlc/2-specs/modules/MOD-3-FARM.md`). `ACTOR-4` — заморожен (frozen) и вне
  периметра этой задачи, здесь его не редактирую; фиксирую расхождение как
  факт, требующий отдельного пересмотра `ACTOR-4` человеком.
- Сопоставление ответа с запросом — по индексу массива, не по id из ответа.
  Если сервер вернёт `data` короче, чем `places` (при этом `status == "1"`),
  `List.generate(data.length, ...)` молча обработает только первые
  `data.length` элементов; оставшиеся места так и останутся с отрицательным
  `idRemote` без явной ошибки. Не проявляется в этом (успешном, полная длина
  ответа) сценарии — дальше в рамках этого файла не разбирается.
- Вызов `updateAll(...)` внутри `AnimalsRepository.updatePlaceId` (шаг 7) не
  имеет `await` — метод-обёртка (`Future<void> updatePlaceId`) возвращается
  раньше, чем гарантированно завершится сама запись в БД; то же самое, что и
  у `updateFarmId` (см. [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md)),
  подтверждено комментарием в тесте (`test/repositories/animals_repository_test.dart`,
  `pumpEventQueue()` как диагностический костыль теста).
- Полный отказ батча (шаг 6) оставляет `remotePlaces = []`; на шаге 7
  `updatePlaceId` для каждого места из `res` ищет совпадение в `remotePlaces`
  через `firstWhereOrNull(...)!` — не найдя его, выражение упадёт на
  null-check операторе. Для аналогичного метода `updateFarmId` это
  подтверждено существующим тестом-ловушкой (`test/repositories/animals_repository_test.dart`,
  `'БАГ-ловушка (намеренная, не найдено соответствие new*.id): ...'`); для
  `updatePlaceId` отдельного теста-ловушки нет — только тест happy-path. В
  этом (`CREATE_OK`) сценарии батч полностью успешен, поэтому не
  проявляется — это факт для отдельного `ERROR` use-case, не для этого
  файла.
- Нет теста на уровне `PlaceRepository.storePlacesOnRDS`/`_storePlacesToRDS`/
  `data_update_bloc` (см. «Связанные тесты») — этот уровень проверен только
  чтением кода; каскадный шаг (шаг 7) отдельно проверен репозиторным тестом.
