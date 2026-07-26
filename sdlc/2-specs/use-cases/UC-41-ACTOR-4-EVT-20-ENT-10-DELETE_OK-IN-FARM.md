# UC-41 — Sync-проход успешно отправляет удаление мест на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md) |
| Сущность | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер удаление
всех локально помеченных как удалённые мест одним батч-запросом, и запрос
завершается успехом. После успеха локально физически удаляется весь исходный
набор помеченных мест целиком — включая записи, не попавшие в сам сетевой
запрос (например ещё не синхронизированные). Happy-path сценарий события
[EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md)
(`place.deletion_synced`), завершающего локальное удаление, начатое
[EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) (`place.deletion_requested`,
см. [UC-34](UC-34-ACTOR-1-EVT-17-ENT-10-DELETE_OK-IN-FARM.md)).

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
3. `_syncAuthData` вызывает `_deletePlacesFromRDS()` **первым** шагом
   авторизованной части прохода — раньше `_syncFarms()` и `_syncPlaces()`;
   порядок фиксированный, ничем не гейтится, кроме факта авторизации.
4. `_deletePlacesFromRDS` запрашивает `PlaceRepository.getAllToDelete()` — все
   локальные места, у которых `isDeleted == true` (`dao.selectCurrent()..where
   ((tbl) => tbl.isDeleted.isValue(true))`), без какой-либо фильтрации по
   `idRemote` или по ферме. Результат — список `res`.
5. Из `res` строится `remoteIds` — `res.map((e) => e.idRemote).where((id) =>
   id != null && id >= 0).cast<int>().toList()` — только записи с
   определённым неотрицательным `idRemote`.
6. Если `remoteIds` непуст — выполняется **ровно один** сетевой вызов:
   `PlaceRepository.deletePlacesOnRDS(remoteIds)` — один `DELETE
   {registrationServiceApi}/places/delete` с телом `{"ids": [...]}`,
   содержащим все `remoteIds` сразу. В отличие от ферм
   ([UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md), где запросы на
   удаление ферм как функциональности вовсе нет — см.
   [MOD-3](../modules/MOD-3-FARM.md)), и как и у создания/обновления мест
   ([UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md)) — это батч, не
   цикл отдельных запросов.
7. В этом (`DELETE_OK`) сценарии сервер отвечает `status == "1"` на весь
   батч — `deletePlacesOnRDS` возвращает `true`.
8. На `true`: `await _placeRepository.deleteAll(res)` — физически удаляет
   **весь** исходный список `res`, а не только подмножество, вошедшее в
   `remoteIds` на шаге 5. `BaseRepository.deleteAll` делегирует в
   `dao.delAll(list)` — в одной транзакции для каждого элемента `res`
   вызывается `BaseDao.del(item)` → `deleteCurrent().delete(item)`, удаление
   строки по совпадению локального PK (`id`).
9. `_syncAuthData` продолжает `_syncFarms()` и `_syncPlaces()` — вне рамок
   этого use-case.

### Альтернативные потоки

- `res` пуст (нет мест, помеченных `isDeleted: true`) → `remoteIds` пуст →
  весь `if (remoteIds.isNotEmpty)` пропускается, ни одного сетевого вызова —
  вырожденный случай «нечего синхронизировать», не этот сценарий.
- `res` непуст, но ни у одной записи нет валидного `idRemote` (`null` либо
  отрицательный) → `remoteIds` пуст → тот же пропуск целиком: ни одна запись
  из `res` физически не удаляется в этом проходе, попытка повторится на
  следующем. При инварианте, зафиксированном в «Бизнес-правила» ниже, на
  практике этот случай не должен возникать.
- Батч отказывает (`status != "1"`) либо вызов бросает исключение (перехвачено
  внутри `deletePlacesOnRDS`, метод возвращает `false`) →
  `_placeRepository.deleteAll(res)` вовсе не вызывается — ни одна запись из
  `res` не удаляется, весь набор останется в `getAllToDelete()` на следующем
  проходе. Отдельный сценарий (`RESULT = DELETE_ERROR`), не описанный этим
  файлом.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — основная сущность
  перехода: строки, помеченные `isDeleted: true`, физически удаляются из
  локальной таблицы `Places`.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не
  изменяется этим сценарием; `_deletePlacesFromRDS` не обращается к
  `FarmRepository` вовсе.
- Animal — не затрагивается этим сценарием (в отличие от создания/обновления
  места, см. [UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md)):
  `_deletePlacesFromRDS` не выполняет ни одного запроса к
  `AnimalsRepository`. Отсутствие закреплённых животных на месте проверяется
  раньше, на этапе [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  ([ENT-10](../entities/ENT-10-PLACE-IN-FARM.md), «Инварианты»), а не повторно
  здесь.

### Бизнес-правила

- Удаление мест на сервере отправляется **одним** батч-запросом на весь
  набор `remoteIds` сразу, а не по одному в цикле — так же, как создание и
  обновление мест ([UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md)),
  но структурно иначе, чем ферм, для которых такой функциональности нет
  вовсе.
- Успех батча — all-or-nothing: единственный `status == "1"` по всему
  запросу коммитит локальное удаление разом для всего `res`; отдельного
  per-item сигнала успеха/отказа сервер для этого вызова не возвращает.
- Локальное физическое удаление после успеха покрывает **весь** список
  `res`, полученный в начале `_deletePlacesFromRDS`, а не только
  подмножество, реально вошедшее в батч-запрос (`remoteIds`). Это значит, что
  гипотетическая запись `Place` с `isDeleted: true`, но без валидного
  `idRemote`, тоже была бы удалена локально как побочный эффект успешного
  батча по другим местам — без того, чтобы сама эта запись когда-либо
  отправлялась на сервер.
- На практике, по инварианту, установленному
  `FarmsAndPlacesBloc._onDeletePlace` (см.
  [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)/
  [UC-34](UC-34-ACTOR-1-EVT-17-ENT-10-DELETE_OK-IN-FARM.md)): мягкое удаление
  (`isDeleted: true`) применяется только к местам, у которых после
  нормализации в `PlaceCreateCubit.removePlace` уже есть валидный
  неотрицательный `idRemote` — ещё не отправленное на сервер место удаляется
  физически сразу же, минуя `isDeleted: true`. Поэтому `res` на практике
  должен полностью совпадать с множеством, из которого строится `remoteIds`
  — расхождение из предыдущего пункта остаётся фактом кода, а не наблюдаемым
  в текущей цепочке модуля поведением.
- Шаги 6-8 выполняются строго раньше `_syncFarms()`/`_syncPlaces()` в том же
  проходе — порядок фиксирован в `_syncAuthData`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде. Тестового покрытия нет вовсе, ни
на уровне `data_update_bloc`, ни на уровне `PlaceRepository` (см. «Связанные
тесты») — это факт отсутствия теста, а не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети, запуск `_syncAuthData` при `isAuthorized` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | последовательность sync-шагов для авторизованного пользователя: `_deletePlacesFromRDS` вызывается первым, раньше `_syncFarms`/`_syncPlaces` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._deletePlacesFromRDS` | CURRENT | оркестрация: получить помеченные к удалению места, отобрать валидные `remoteId`, один батч-запрос удаления, `deleteAll(res)` целиком при успехе |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllToDelete` | CURRENT | выборка мест с `isDeleted == true` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.deletePlacesOnRDS` | CURRENT | один `DELETE {registrationServiceApi}/places/delete` с телом `{"ids": [...]}`; возвращает `true` только если `response['status'] == "1"` |
| `lib/repositories/base_repository.dart` | `BaseRepository.deleteAll` | CURRENT | делегирует в `dao.delAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.delAll`, `BaseDao.del` | CURRENT | построчное физическое удаление по PK в транзакции (`deleteCurrent().delete(item)`) |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель, поля `id` (локальный PK)/`idRemote`/`isDeleted` |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL, из которого строится эндпоинт удаления |
| `lib/network/api_client/api_client.dart` | `ApiClient` (`instanceName: 'farm_rpc'`) | CURRENT | RPC-клиент, которым выполняется батч-запрос удаления |
| `lib/network/api_client/api_message.dart` | `ApiMessage`, `ApiMethod.delete` | CURRENT | конверт запроса (`link`, `method`, `data`) для вызова `rpcClientSHTP.call(message)` |

## Критерии приёмки

- При запуске полного sync-прохода (`DataUpdateStartAll`) авторизованным
  пользователем, при наличии сети, если есть хотя бы одно место с
  `isDeleted == true` и валидным (неотрицательным) `idRemote`, выполняется
  ровно один `DELETE {registrationServiceApi}/places/delete` с телом
  `{"ids": [...]}`, содержащим все такие `idRemote` сразу.
- Если ответ сервера — `status == "1"`, после прохода **все** места, у
  которых было `isDeleted == true` на момент чтения (`res`, шаг 4), физически
  удалены из локальной таблицы `Places` — включая те, что не имели валидного
  `idRemote` и потому не вошли в сам запрос.
- `PlaceRepository.getAllToDelete()` после успешного прохода возвращает
  список без этих записей — они больше не существуют в таблице.
- Ни `FarmRepository`, ни `AnimalsRepository` не вызываются этим сценарием —
  сущности Farm и Animal не читаются и не изменяются.

## Связанные тесты

`TBD — теста нет`. Ни на уровне `data_update_bloc` (`test/blocs/data_update_bloc_test.dart`
мокает `PlaceRepository`, но не содержит ни одного `group()`/`test()`,
проверяющего `_deletePlacesFromRDS`), ни на уровне репозитория (файла
`test/repositories/place_repository_test.dart` не существует, `deletePlacesOnRDS`/
`getAllToDelete` не упоминаются ни в одном тестовом файле репозитория).

`test/pages/farms_and_places_bloc_test.dart`, group `'UC-11 —
FarmsAndPlacesBloc._onDeletePlace'` покрывает только локальный эффект
[EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) (мягкое/
физическое удаление в момент запроса пользователя, см.
[UC-34](UC-34-ACTOR-1-EVT-17-ENT-10-DELETE_OK-IN-FARM.md)) — не
sync-отправку удаления на сервер, инициированную
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), и потому не является тестом
этого use-case.

## Открытые вопросы и ограничения

- **Локальное удаление после успеха не ограничено подмножеством, реально
  отправленным на сервер.** `deleteAll(res)` (шаг 8) стирает весь список
  `res`, полученный на шаге 4, а не только записи с валидным `idRemote`,
  вошедшие в `remoteIds`/сам батч-запрос. При инварианте, который сегодня
  поддерживает `FarmsAndPlacesBloc._onDeletePlace` (см. «Бизнес-правила»),
  это расхождение не проявляется — но код не перепроверяет это условие перед
  удалением, а полагается на инвариант, установленный другим файлом
  (`place_create_cubit.dart`).
- **Расхождение с зафиксированным ограничением
  [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)**, уже отмеченное для
  create-сценария в [UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md):
  его секция «Ограничения» утверждает «Фермы и места отправляются на сервер
  по одной, в цикле, не единым батчем». Для удаления мест это тоже не
  подтверждается кодом — `deletePlacesOnRDS` отправляет один запрос с
  массивом id сразу. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) заморожен
  (frozen) и вне периметра этой задачи — здесь его не редактирую, фиксирую
  расхождение как факт для отдельного пересмотра человеком.
- Нет теста ни на одном уровне (см. «Связанные тесты») — весь сценарий
  проверен только чтением кода.
