# UC-25 — Sync-проход успешно отправляет новые фермы на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) |
| Сущность | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все
локально созданные фермы, у которых ещё нет серверного id, и все запросы
завершаются успехом. Локальный `remoteId` каждой фермы заменяется на
серверный, а связанные места и ещё не отправленные локальные животные,
ссылавшиеся на старый (отрицательный) id фермы, каскадно переписываются на
новый. Happy-path сценарий события
[EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) (`farm.create_synced`).

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
3. `_syncAuthData` вызывает `_deletePlacesFromRDS`, затем `_syncFarms` —
   порядок фиксированный, ничем не гейтится, кроме факта авторизации.
4. `_syncFarms` вызывает `_storeFarmsToRDS` первым шагом (до
   `_updateFarmsOnRDS` и `_loadFarmsFromRDS`).
5. `_storeFarmsToRDS` запрашивает `FarmRepository.getAllWithoutRemoteId()` —
   все локальные фермы с `remoteId < 0` (созданные локально, ещё не
   отправленные). Если список пуст — метод возвращается сразу, ничего дальше
   не выполняется (в этом проходе `EVT-12` фактически не происходит — не этот
   сценарий).
6. Для непустого списка `res` вызывается
   `FarmRepository.storeFarmsOnRDS(res)` — фермы отправляются серверу по
   одной, в цикле, каждая отдельным `POST
   {registrationServiceApi}/farms/store`. В этом (`CREATE_OK`) сценарии
   **каждый** запрос отвечает `status == "1"` — для каждой фермы
   `FarmExtension.fromJsonRDSwithLocalId` строит новый `Farm` с тем же
   локальным `id`, но с `remoteId` и адресными полями из ответа сервера;
   результат копится в возвращаемый список `remoteFarms`, длина которого в
   этом сценарии равна длине `res`.
7. `PlaceRepository.updateFarmId(res, remoteFarms)` — для каждой фермы из
   `res` находит все места (`getAllWithThisFarmId(farm.remoteId)`) — все не
   удалённые (`isDeleted != true`) места, у которых `farmId` всё ещё равен
   старому (отрицательному) `remoteId` этой фермы, независимо от того,
   синхронизировано ли само место, — и переписывает им `farmId` на новый
   серверный id той же фермы (найденной по совпадению локального `id`).
8. `AnimalsRepository.updateFarmId(res, remoteFarms)` — тот же приём, но
   только для животных: `dao.getLocalAnimalsByFarmId(farm.remoteId!)` выбирает
   исключительно **локальные** (`id < 0`), ещё не отправленные животные с
   `farmId`, равным старому `remoteId` фермы, и переписывает им `farmId` на
   новый. Вызов `updateAll(...)` внутри этого метода **не имеет `await`** —
   метод возвращается раньше, чем гарантированно завершится сама запись (см.
   «Открытые вопросы»).
9. `FarmRepository.updateAll(remoteFarms)` — `dao.updAll` в транзакции; для
   каждой фермы `BaseDao.upd` делает `updateCurrent().replace(item)` —
   построчный `UPDATE` по совпадению локального `id` (PK), заменяя `remoteId`
   и адресные поля (из шага 6) в уже существующей локальной строке. Ферма в
   базе остаётся той же строкой (тот же локальный `id`), но теперь с
   положительным `remoteId`.
10. `_syncFarms` продолжает `_updateFarmsOnRDS` и `_loadFarmsFromRDS` — вне
    рамок этого use-case (обновление уже синхронизированных ферм и полная
    перезагрузка списка ферм с сервера — другие события,
    [EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md)/[EVT-14](../events/EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md)).

### Альтернативные потоки

- `getAllWithoutRemoteId()` пуст (нет локально созданных ферм) →
  `_storeFarmsToRDS` возвращается сразу, ни один сетевой вызов не выполняется
  — вырожденный случай «нечего синхронизировать», не этот сценарий.
- Частичный отказ (одна из нескольких ферм в одном проходе отвечает ошибкой
  или падает исключением) — `storeFarmsOnRDS` делает `continue` и не включает
  эту ферму в `remoteFarms`; это отдельный сценарий (`ERROR`), не входит в
  этот `CREATE_OK` use-case, где предполагается, что **все** отправленные в
  этом проходе фермы получают успех.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — основная сущность
  перехода: `remoteId` заменяется на серверный, адресные поля перезаписываются
  данными ответа; локальный `id` и локальные флаги (`needUpdate`,
  `isDeleted`) этим шагом не меняются.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — каскадно: `farmId`
  всех не удалённых мест, ссылавшихся на старый `remoteId` фермы,
  переписывается на новый — независимо от собственного статуса синхронизации
  места.
- Animal — `farmId` локальных (`id < 0`) животных, ссылавшихся на старый
  `remoteId` фермы, тоже переписывается тем же проходом
  (`AnimalsRepository.updateFarmId`). Сущность принадлежит ещё не
  специфицированному модулю ANIMAL (см. границу
  [MOD-3](../modules/MOD-3-FARM.md), «что модуль explicitly не владеет») —
  отдельного `ENT`-id для неё в дереве спек пока нет.

### Бизнес-правила

- Фермы отправляются по одной, в цикле, не батчем; порядок — тот, в котором
  `getAllWithoutRemoteId()` их вернул (явной сортировки в коде нет).
- Каскадное обновление связанных мест и животных (шаги 7-8) выполняется
  **раньше**, чем сама ферма получает новый `remoteId` в локальной БД (шаг
  9) — по порядку строк в `_storeFarmsToRDS`.
- `FarmRepository.updateAll` в этом шаге обновляет только фермы, успешно
  вернувшиеся из `storeFarmsOnRDS` (`remoteFarms`); фермы, отсутствующие в
  этом списке (отказавшие), в этом шаге никак не меняются и останутся в
  `getAllWithoutRemoteId()` на следующем проходе.
- Каскад на животных выбирает только локальные (`id < 0`), ещё не
  отправленные записи; уже синхронизированное животное со старым
  (отрицательным) `farmId` этим запросом не найдётся.
- Каскад на места, в отличие от животных, не фильтрует по собственному
  статусу синхронизации места — единственный фильтр: `farmId` равен старому
  `remoteId` фермы и `isDeleted != true`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде. Тестового покрытия на уровне
`data_update_bloc` нет (см. «Связанные тесты») — это факт отсутствия теста, а
не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети, запуск `_syncAuthData` при `isAuthorized` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | последовательность sync-шагов для авторизованного пользователя, вызывает `_syncFarms` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms` | CURRENT | вызывает `_storeFarmsToRDS` первым шагом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._storeFarmsToRDS` | CURRENT | оркестрация: получить фермы без `remoteId`, отправить, каскадно обновить Place/Animal, сохранить |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllWithoutRemoteId` | CURRENT | выборка ферм с `remoteId < 0` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.storeFarmsOnRDS` | CURRENT | `POST {registrationServiceApi}/farms/store` по одной ферме за раз |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `FarmExtension.fromJsonRDSwithLocalId` | CURRENT | строит `Farm` с прежним локальным `id` и новым `remoteId`/адресом из ответа сервера |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.updateFarmId` | CURRENT | каскадно переписывает `farmId` у мест, ссылавшихся на старый `remoteId` фермы |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmId` | CURRENT | выборка не удалённых мест по `farmId` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateFarmId` | CURRENT | каскадно переписывает `farmId` у локальных (`id < 0`) животных; вызов `updateAll` внутри не awaited |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getLocalAnimalsByFarmId` | CURRENT | выборка локальных животных по `farmId` |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | делегирует в `dao.updAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `BaseDao.upd` | CURRENT | построчный `UPDATE` по PK в транзакции (`updateCurrent().replace`) |

## Критерии приёмки

- При запуске полного sync-прохода (`DataUpdateStartAll`) авторизованным
  пользователем, при наличии сети, для каждой локальной фермы с `remoteId <
  0` выполняется отдельный `POST {registrationServiceApi}/farms/store`.
- Если ответ сервера на все такие запросы — `status == "1"`, после прохода
  каждая такая ферма в локальной БД имеет `remoteId` сервера вместо прежнего
  отрицательного значения, тот же локальный `id`, и адресные поля,
  обновлённые данными ответа.
- Все места (`Places.isDeleted != true`), у которых `farmId` равнялся старому
  (отрицательному) `remoteId` такой фермы, после прохода имеют `farmId`,
  равный новому серверному id той же фермы.
- Все локальные (`id < 0`) животные, у которых `farmId` равнялся старому
  `remoteId` такой фермы, после прохода имеют `farmId`, равный новому
  серверному id той же фермы.
- `FarmRepository.getAllWithoutRemoteId()` после успешного прохода для этих
  ферм возвращает список без них (они больше не входят в него, так как
  `remoteId` уже не отрицателен).

## Связанные тесты

`TBD — теста нет` на уровне `data_update_bloc`. Файл
`test/blocs/data_update_bloc_test.dart` существует и мокает `FarmRepository`
(`MockFarmRepository`), но не содержит ни одного `group()`/`test()`,
проверяющего `_storeFarmsToRDS`/`_syncFarms` — единственные тесты в файле
проверяют конструирование блока и `DataUpdateClear`. Тесты, покрывающие фермы,
есть только на уровне UI-cubit'ов (`test/pages/farms_and_places_bloc_test.dart`
— группы `UC-1`…`UC-12`, старая нумерация, будет переименовано, не трогать
сейчас; `test/pages/farm_create_cubit_test.dart`, group
`'FarmCreateCubit.saveFarm'`) — они проверяют локальное создание/редактирование
фермы (`FarmsAndPlacesBloc._onAddFarm`, `FarmCreateCubit.saveFarm`), не
sync-проход, инициированный [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), и
потому не являются тестами этого use-case.

## Открытые вопросы и ограничения

- Вызов `updateAll(...)` внутри `AnimalsRepository.updateFarmId` (шаг 8) не
  имеет `await` — метод-обёртка (`Future<void> updateFarmId`) возвращается
  раньше, чем гарантированно завершится сама запись в БД. В этом (`CREATE_OK`)
  сценарии это не проявляется как видимая ошибка, но означает, что порядок
  завершения каскада на животных относительно шага 9
  (`FarmRepository.updateAll(remoteFarms)`) не гарантирован кодом — факт,
  зафиксированный здесь как контекст, не разбираемый дальше в рамках этого
  файла.
- Частичный отказ внутри одной пачки (одна ферма из нескольких — отказ, а не
  все) на уровне `PlaceRepository.updateFarmId`/`AnimalsRepository.updateFarmId`
  ищет соответствующую `newFarm` через `firstWhereOrNull(...)!` — не найдя
  совпадения (ферма отсутствует в `remoteFarms`, потому что её отправка
  отказала), выражение упадёт на null-check операторе. В этом (`CREATE_OK`)
  сценарии все фермы успешны, поэтому это не проявляется — но это значит, что
  частичный успех внутри одного прохода, вероятно, не безобидный «пропускаем
  и продолжаем», как формулирует ограничение
  [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), а необработанное
  исключение; это факт для отдельного `ERROR` use-case, не для этого файла.
- Нет теста на этом уровне (см. «Связанные тесты») — весь сценарий проверен
  только чтением кода.
