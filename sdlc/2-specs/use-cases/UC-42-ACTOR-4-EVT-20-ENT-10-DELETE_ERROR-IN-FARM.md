# UC-42 — Sync удаления места отказывает: единый батч-запрос отказывает целиком (ERROR)

## Назначение

Во время явного sync-прохода система отправляет на сервер удаление локально
помеченных к удалению мест — единым батч-запросом со всеми `idRemote` сразу,
как и в happy-path сиблинге того же события,
[UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md). Здесь сервер
отвечает отказом на весь батч, либо сам вызов падает исключением — оба случая
обрабатываются кодом одинаково. Локально не удаляется ни одна запись из
исходного набора помеченных к удалению мест — включая те, что даже не попали
в сам сетевой вызов из-за отсутствующего/отрицательного `idRemote`. Не
описанная в [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md) ветка
того же [EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md)
(`place.deletion_synced`), завершающего локальное удаление, начатое
[EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
(`place.deletion_requested`, см.
[UC-34](UC-34-ACTOR-1-EVT-17-ENT-10-DELETE_OK-IN-FARM.md)).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая внутри
уже запущенного полного sync-прохода (`DataUpdateBloc`); не человек и не
отдельное решение пользователя на этом шаге. Сам проход перед этим запускается
человеком (`DataUpdateStartAll` диспатчится из `lib/pages/main/main_page.dart`,
`lib/pages/profile/presentation/profile_page.dart`,
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`,
`lib/pages/in_work/in_work_page.dart`,
`lib/pages/data_update/data_update_page.dart`) — сам механизм запуска прохода
принадлежит модулю `SYSTEM` (см. границу [MOD-3](../modules/MOD-3-FARM.md)),
здесь не переопределяется.

## CURRENT

### Основной поток

1. **Предпосылка.** Как минимум одно уже синхронизированное место (`idRemote`
   не `null` и неотрицательный) было ранее помечено к удалению —
   [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md),
   `FarmsAndPlacesBloc._onDeletePlace` — `event.place.copyWith(isDeleted:
   true)`, сохранённое локально через `_placeRepository.update(deletedPlace)`;
   на сервер удаление ещё не отправлялось.
2. Запускается полный sync-проход: `DataUpdateBloc.on<DataUpdateStartAll>`
   проверяет сеть, затем (пользователь авторизован) вызывает
   `DataUpdateBloc._syncAuthData`, которая **первым** шагом авторизованной
   части прохода — раньше `_syncFarms()` и `_syncPlaces()` — вызывает
   `_deletePlacesFromRDS()`.
3. `_deletePlacesFromRDS()` запрашивает `PlaceRepository.getAllToDelete()` —
   `dao.selectCurrent()..where((tbl) => tbl.isDeleted.isValue(true))`, без
   фильтрации по `idRemote` или по ферме — результат `res`.
4. Из `res` строится `remoteIds` — `res.map((e) => e.idRemote).where((id) =>
   id != null && id >= 0).cast<int>().toList()` — только записи с валидным
   неотрицательным `idRemote`. В этом сценарии `remoteIds` непуст (иначе сеть
   вообще не вызывается — см. «Альтернативные потоки»).
5. `if (remoteIds.isNotEmpty)` — выполняется **ровно один** сетевой вызов:
   `PlaceRepository.deletePlacesOnRDS(remoteIds)` — один `DELETE
   ${Constants.registrationServiceApi}/places/delete` с телом `{"ids":
   [...]}`, содержащим все `remoteIds` сразу, через
   `getIt.get<ApiClient>(instanceName: 'farm_rpc')`.
6. Сервер отвечает статусом, отличным от `"1"` (`log('deletePlacesOnRDS:
   Error, status: $response')`), **либо** сам вызов (`rpcClientSHTP
   .call(message)`) бросает исключение — оба случая перехвачены общим
   `try/catch` внутри `deletePlacesOnRDS` и приводят к одному и тому же
   результату: метод возвращает `false`.
7. Обратно в `_deletePlacesFromRDS`: `isDeletedOnRDS == false` →
   `if (isDeletedOnRDS) { await _placeRepository.deleteAll(res); }` не
   выполняется вовсе. В отличие от `_updatePlacesOnRDS`/`_updateFarmsOnRDS`,
   здесь **нет `else`-ветки и нет отдельного `log(...)`** на уровне
   `_deletePlacesFromRDS` для случая отказа — единственный след неудачи
   остаётся внутри самого `PlaceRepository.deletePlacesOnRDS` (`log(...)`).
8. Ни одна запись из `res` не удаляется локально — это касается и записей,
   вошедших в `remoteIds` (реально отправленных в отказавшем батче), и
   записей, которые в него не вошли вовсе (шаг 4): решение «удалять или нет»
   принимается одним общим `bool` на весь `res`, а не по каждой записи
   отдельно.
9. Никакое исключение наружу не пробрасывается — `_deletePlacesFromRDS()`
   завершается нормально, `_syncAuthData` продолжает безусловно: `_syncFarms()`
   (не читает и не пишет `Places`), затем `_syncPlaces()` —
   `_storePlacesToRDS()` → `_updatePlacesOnRDS()` → `_loadPlacesFromRDS()`.
10. Переживёт ли оставшийся `isDeleted: true` этот проход до следующего (то
    есть будет ли попытка удаления реально повторена на следующем полном
    sync-проходе), или же будет молча отменена ещё в рамках **этого же**
    прохода — решает не этот шаг, а последний шаг `_syncPlaces()`,
    `_loadPlacesFromRDS()` (независимый `GET .../farms?with_places=1`,
    предмет [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md)). Там же
    (см. «Бизнес-правила»/«Открытые вопросы» [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md))
    задокументировано: при обычном непустом ответе reload'а — а место, чьё
    удаление здесь не подтверждено, по определению всё ещё существует на
    сервере и потому попадёт в этот ответ — место вставляется заново с
    `isDeleted == false`, то есть намерение пользователя удалить его
    отменяется молча, а не просто откладывается.
11. Весь `DataUpdateStartAll` при этом (если ни один из последующих шагов
    прохода не бросит исключение) всё равно завершается `DataUpdateSuccess` —
    ни отказ удаления, ни его возможная последующая молчаливая отмена
    reload'ом (п. 10) не долетают до внешнего `try/catch` и не порождают
    никакого состояния ошибки. `Places.isDeleted` не читается ни одним
    виджетом в `lib/` — пользователь не видит никакого индикатора «удаление
    не подтверждено» ни во время, ни после такого прохода.

### Альтернативные потоки

- **Два разных технических подтипа отказа объединены в один и тот же
  результат.** Не-`"1"` статус ответа сервера и брошенное исключение
  (сеть/таймаут) обрабатываются кодом абсолютно одинаково — оба ведут к
  `return false;` внутри одного и того же `catch`/`else` в
  `deletePlacesOnRDS`, без какого-либо различения причины дальше по потоку.
  Тот же паттерн объединения, что и у обновления фермы/места
  ([UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md),
  [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)) — оба
  подтипа часть этого же `DELETE_ERROR`-сценария, не два разных use-case.
- **`res` непуст, но `remoteIds` пуст** (ни у одной записи из `res` нет
  валидного неотрицательного `idRemote`) — `if (remoteIds.isNotEmpty)`
  пропускается целиком: сетевой вызов не выполняется вовсе,
  `deletePlacesOnRDS` не вызывается, а значит и вопрос «отказал батч или
  нет» не возникает — не этот сценарий (граничный случай уже отмечен как
  альтернативный поток в
  [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md)). По инварианту,
  поддерживаемому `FarmsAndPlacesBloc._onDeletePlace`
  ([EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)), на
  практике этот случай не должен возникать — мягкое удаление ставится только
  местам с уже валидным `idRemote`.
- **`res` пуст** (нет мест с `isDeleted == true` вовсе) — тот же пропуск,
  вырожденный случай «нечего синхронизировать», не этот сценарий.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — единственная
  сущность, которую затрагивает этот сценарий: локальные строки с `isDeleted
  == true` остаются в таблице `Places` неизменными после этого шага (в
  отличие от happy-path
  [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md), где они
  физически удаляются).
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не
  изменяется этим шагом; `_deletePlacesFromRDS` не обращается к
  `FarmRepository` вовсе (как и в happy-path, см.
  [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md), «Связанные
  сущности»).

### Бизнес-правила

- Удаление мест на сервере отправляется **одним** батч-запросом на весь
  набор `remoteIds` сразу, а не по одному в цикле — как и у happy-path
  ([UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md)) и у
  создания/обновления мест
  ([UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md),
  [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)). Отказ
  батча — тоже all-or-nothing: единственный не-`"1"` статус (или
  исключение) по всему запросу отменяет локальное удаление разом для всего
  `res`, без per-item сигнала.
- Отказ батча оставляет нетронутым **весь** список `res`, а не только
  подмножество, реально вошедшее в `remoteIds` — симметрично тому, как
  успех батча удаляет весь `res` целиком, включая записи, не попавшие в
  сетевой вызов (см. [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md),
  «Бизнес-правила»). Ни один из двух исходов не рассматривает запись `res`
  независимо от соседей по батчу.
- В отличие от `_updatePlacesOnRDS`/`_updateFarmsOnRDS`, `_deletePlacesFromRDS`
  не логирует явно ветку отказа на своём уровне — единственный след остаётся
  внутри `PlaceRepository.deletePlacesOnRDS` самого.
- Судьбу оставшегося `isDeleted: true` — будет ли попытка удаления повторена
  на следующем полном проходе, или молча отменена ещё в рамках этого же
  прохода — определяет не этот шаг, а последующий безусловный reload
  (`_loadPlacesFromRDS`, [EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md),
  задокументировано в [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md)) —
  этот шаг сам по себе не гарантирует и не исключает повтор.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью реализован в коде, включая переход к
последующим шагам того же прохода; отсутствие пользовательского сигнала об
отказе и зависимость итоговой судьбы удаления от отдельного, независимого шага
reload'а — задокументированные факты текущего поведения, а не незавершённая
реализация (см. «Открытые вопросы и ограничения»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешний `try/catch` прохода; отказ, перехваченный внутри репозитория, до него не долетает — проход завершается `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_deletePlacesFromRDS()` первым шагом, раньше `_syncFarms()`/`_syncPlaces()`; все шаги безусловны |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._deletePlacesFromRDS` | CURRENT | получает `res` через `getAllToDelete`, строит `remoteIds`, вызывает `deletePlacesOnRDS`; `deleteAll(res)` вызывается только при `isDeletedOnRDS == true` — нет `else`-ветки/лога при `false` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms`, `_syncPlaces`, `_loadPlacesFromRDS` | CURRENT | выполняются безусловно вслед за отказавшим удалением; `_loadPlacesFromRDS` — последний шаг `_syncPlaces()`, предмет [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md), фактически определяет судьбу оставшегося `isDeleted: true` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllToDelete` | CURRENT | выборка мест с `isDeleted == true` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.deletePlacesOnRDS` | CURRENT | один `DELETE {registrationServiceApi}/places/delete` с телом `{"ids": [...]}`; не-`"1"` статус и брошенное исключение оба обрабатываются одним `try/catch` и возвращают `false` |
| `lib/repositories/base_repository.dart` | `BaseRepository.deleteAll` | CURRENT | в этом сценарии не вызывается вовсе (гейт `isDeletedOnRDS == true` не пройден) |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onDeletePlace` | CURRENT | путь, которым устанавливается предпосылка сценария ([EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)) — `isDeleted: true` для уже синхронизированного места |
| `lib/pages/main/main_page.dart`, `lib/pages/profile/presentation/profile_page.dart`, `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`, `lib/pages/in_work/in_work_page.dart`, `lib/pages/data_update/data_update_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | точки входа, инициирующие полный sync-проход, частью которого является этот сценарий |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL, из которого строится эндпоинт удаления мест |
| `lib/network/api_client/api_client.dart` | `ApiClient` (`instanceName: 'farm_rpc'`) | CURRENT | RPC-клиент, которым выполняется батч-запрос удаления |
| `lib/network/api_client/api_message.dart` | `ApiMessage`, `ApiMethod.delete` | CURRENT | конверт запроса (`link`, `method`, `data`) для вызова `rpcClientSHTP.call(message)` |

## Критерии приёмки

- Если единственный `DELETE {registrationServiceApi}/places/delete` (с телом
  `{"ids": [...]}` для всего батча из `remoteIds`) отвечает статусом, отличным
  от `"1"`, либо завершается исключением —
  `PlaceRepository.deletePlacesOnRDS` возвращает `false` (проверяемо одним
  вызовом мока, без повторов внутри самого вызова).
- `DataUpdateBloc._deletePlacesFromRDS` при `isDeletedOnRDS == false` не
  вызывает `PlaceRepository.deleteAll` вовсе — ни для одной записи `res`, в
  том числе для записей, не попавших в `remoteIds`.
- `_deletePlacesFromRDS()`/`_syncAuthData()` завершаются без исключения
  (`completes`, а не `throwsA(...)`) — отказ не всплывает выше по цепочке
  вызовов.
- `PlaceRepository.getAllToDelete()`, вызванный сразу после этого шага (до
  последующего reload'а), возвращает тот же набор записей, что и до попытки
  удаления — ни одна не исчезла.
- Полный проход `DataUpdateStartAll` в этом сценарии завершается
  `DataUpdateSuccess`, не `DataUpdateFailure`, несмотря на то что удаление
  места не было подтверждено сервером.

## Связанные тесты

`TBD — теста нет`. Ни на уровне `data_update_bloc`
(`test/blocs/data_update_bloc_test.dart` мокает `PlaceRepository`
(`MockPlaceRepository`), но не содержит ни одного `group()`/`test()`,
проверяющего `_deletePlacesFromRDS`), ни на уровне репозитория (файла
`test/repositories/place_repository_test.dart` не существует,
`grep -rl "deletePlacesOnRDS" test/` не находит ни одного файла).

`test/pages/farms_and_places_bloc_test.dart`, group `'UC-12 —
FarmsAndPlacesBloc._onDeletePlace ERROR'` покрывает только локальный отказ
[EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) (исключение из
`_placeRepository.update`/`delete` в момент запроса пользователя) — не
sync-отправку удаления на сервер, инициированную
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), и потому не является тестом
этого use-case.

## Открытые вопросы и ограничения

- **«Повтор на следующем проходе» не гарантирован — решает отдельный,
  независимый шаг того же прохода.** Сам `_deletePlacesFromRDS` оставляет
  `isDeleted: true` нетронутым при отказе батча, что можно прочитать как
  «попытка будет повторена на следующем sync-проходе». Но непосредственно
  вслед за ним, в рамках **этого же** прохода, `_loadPlacesFromRDS`
  безусловно перезагружает и полностью перезаписывает таблицу `Places` с
  сервера — а место, чьё удаление не подтверждено, по построению сценария
  всё ещё существует на сервере и попадёт в этот ответ. Как именно это
  сказывается на `isDeleted` (типично — сбрасывается в `false`, то есть
  удаление отменяется молча, а не откладывается) — уже полностью
  задокументировано отдельным use-case,
  [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md) («Бизнес-правила»,
  «Открытые вопросы»); здесь не переисследуется повторно, только фиксируется
  как прямое продолжение этого сценария.
- **Отсутствие любого пользовательского сигнала.** `Places.isDeleted` не
  читается ни одним виджетом в `lib/` — пользователь, запросивший удаление
  места, не получает никакого сообщения ни о том, что удаление не дошло до
  сервера, ни (в типичном случае, см. пункт выше) о том, что оно было молча
  отменено при следующем reload'е того же прохода; весь проход репортится
  как `DataUpdateSuccess`.
- **Расхождение с зафиксированным ограничением
  [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)**, уже отмеченное для
  happy-path того же события в
  [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md): секция
  «Ограничения» актора утверждает «Фермы и места отправляются на сервер по
  одной, в цикле, не единым батчем» — для удаления мест (как и для
  создания/обновления) это не подтверждается кодом, запрос — один батч на
  весь список. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) заморожен и вне
  периметра этой задачи — не переисправляется здесь повторно, только
  подтверждается тот же, уже зафиксированный факт.
- Нет теста ни на одном уровне (см. «Связанные тесты») — весь сценарий,
  включая его зависимость от последующего `_loadPlacesFromRDS`, проверен
  только чтением кода.
