# UC-40 — Sync правки места отказывает: единый батч-запрос отказывает целиком (ERROR)

## Назначение

Во время явного sync-прохода система отправляет на сервер локальные правки
уже синхронизированных мест (`needUpdate: true`), скопившиеся с момента
последнего успешного прохода. В отличие от аналогичного сценария для фермы
([UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)), места этого
пакета отправляются не по одному в цикле, а единым PUT-запросом со всеми
местами сразу в теле — поэтому здесь нет цикла с `break`/`continue`: если
сервер отвечает отказом или сам запрос падает исключением, отказывает **весь**
пакет разом, потому что попытка была ровно одна. Как и у фермы, следующий шаг
того же прохода — безусловная полная перезагрузка мест с сервера — стирает
признак «требует отправки» у всех мест разом независимо от исхода отправки;
эффект тот же — не отложенная отправка, а тихая потеря правки.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая внутри
уже запущенного полного sync-прохода (`DataUpdateBloc`); не человек и не
отдельное решение пользователя на этом шаге. Сам проход перед этим запускается
человеком (`DataUpdateStartAll` диспатчится из `lib/pages/main/main_page.dart`,
`lib/pages/profile/presentation/profile_page.dart`,
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`,
`lib/pages/in_work/in_work_page.dart`, `lib/pages/data_update/data_update_page.dart`)
— сам механизм запуска прохода принадлежит модулю `SYSTEM` (см. границу
[MOD-3](../modules/MOD-3-FARM.md)), здесь не переопределяется.

## CURRENT

### Основной поток

1. **Предпосылка.** Как минимум одно уже синхронизированное место (`idRemote`
   не `null`) было локально отредактировано ранее —
   [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md),
   `FarmsAndPlacesBloc._onEditPlace` — правка выставила `needUpdate: true` на
   копии места (`event.updatedPlace.copyWith(needUpdate: true)`) и сохранила
   её локально через `_placeRepository.update(newPlace)`; на сервер ничего ещё
   не отправлялось.
2. Запускается полный sync-проход: `DataUpdateBloc.on<DataUpdateStartAll>`
   проверяет сеть, затем (пользователь авторизован) вызывает
   `DataUpdateBloc._syncAuthData`, которая безусловно, без `try/catch` вокруг
   каждого шага, выполняет `_deletePlacesFromRDS()` → `_syncFarms()` →
   `_syncPlaces()`.
3. `_syncPlaces()` выполняет три шага строго по порядку, каждый со своим
   `await`, без ветвления по результату предыдущего:
   `_storePlacesToRDS()` → `_updatePlacesOnRDS()` (этот сценарий) →
   `_loadPlacesFromRDS()`.
4. `_updatePlacesOnRDS()` запрашивает `PlaceRepository.getAllToUpdate()` —
   `needUpdate.equals(true) & idRemote.isNotNull()` — получает список мест
   `placesToUpdate` (одно или несколько).
5. `PlaceRepository.updatePlacesOnRDS(placesToUpdate)` **не идёт по списку в
   цикле**: весь список сериализуется одним телом запроса — `{"places":
   places.map((e) => e.toJsonRDS()).toList()}` — и отправляется **одним** `PUT
   ${Constants.registrationServiceApi}/places/update` через
   `getIt.get<ApiClient>(instanceName: 'farm_rpc')`. Здесь нет переменной
   `success`, инкрементально меняющейся по ходу цикла, как у фермы, — есть
   ровно один `if/else` по результату ровно одного вызова.
6. Сервер отвечает статусом, отличным от `"1"`, **либо** сам вызов
   (`rpcClient.call(message)`) бросает исключение (например `DioException`,
   таймаут/нет сети) — оба случая обрабатываются одинаково (общий
   `try/catch`): метод возвращает `false`. Никакое отдельное место пакета не
   получает собственного, независимого исхода — потому что для них не было
   собственного отдельного сетевого вызова.
7. `updatePlacesOnRDS` возвращает `false`. Обратно в
   `DataUpdateBloc._updatePlacesOnRDS`: `isUpdated == false` → выполняется
   только `log('_updatePlacesOnRDS: Failed to update places on RDS')` в
   `else`-ветке. **Ветка `if (isUpdated)`, вызывающая
   `_placeRepository.updateAll(placesToUpdate.map((place) =>
   place.copyWith(needUpdate: false))...)`, не выполняется вовсе** — это
   касается каждого места пакета, включая (при батче из нескольких мест) те,
   что содержательно не изменились относительно уже принятой сервером версии,
   если такие оказались бы в одном пакете с реально правленным местом.
8. Никакое исключение наружу не пробрасывается — `_updatePlacesOnRDS()`
   (метод бло́ка) завершается нормально, `_syncPlaces()` продолжает со
   следующим шагом безусловно.
9. `_loadPlacesFromRDS()` вызывает `PlaceRepository.getAllPlacesFromRDS()`,
   который делегирует в `FarmRepository.getAllFarmsAndPlacesFromRDS()` — тот
   же самый сетевой вызов (`GET ${Constants.registrationServiceApi}/farms` с
   `queryParameters: {'with_places': 1}`), который несколькими шагами раньше
   (внутри уже завершившегося `_syncFarms()`) выполнил и
   `_loadFarmsFromRDS()` — оба reload'а внутри одного прохода делают свой
   отдельный HTTP GET на один и тот же эндпоинт, без общего кеша между ними.
   В типичном случае (сервер отвечает `status == "1"` или `1` и в системе
   вообще есть места) ответ непустой; `getAllPlacesFromRDS` возвращает
   `res['places']`.
10. `if (res.isEmpty) return;` — условие ложно (ответ непустой), поэтому
    выполняется `await _placeRepository.clear()` (полностью удаляет все
    строки таблицы `Places`), затем `await _placeRepository.insertAll(res)`.
    Каждый элемент `res` — `PlacesCompanion`, построенный
    `PlaceExtension.fromJsonRDS`, который **не указывает `needUpdate` вовсе**
    — при вставке (`InsertMode.insertOrReplace`) используется дефолт колонки,
    `Constant(false)` (`Places.needUpdate`,
    `boolean().withDefault(const Constant(false))`).
11. Итоговое локальное состояние места, чья правка не дошла до сервера, после
    этого одного прохода: локальная строка заменена **старой, досерверной**
    версией с сервера; правка полностью потеряна, `needUpdate` оказывается
    `false` — не потому, что шаг 7 его сбросил (он этого не сделал), а потому,
    что шаг 10 перезаписал всю строку заново дефолтом колонки. Следующий
    проход уже не найдёт это место через `getAllToUpdate()` и не повторит
    попытку — правка стёрта безвозвратно.
12. Весь `DataUpdateStartAll` при этом всё равно завершается
    `DataUpdateSuccess` (см. `on<DataUpdateStartAll>`) — ни одно исключение не
    долетело до внешнего `try/catch`, поэтому пользователь не видит никакого
    сообщения об ошибке. `Places.needUpdate` нигде не читается ни одним
    виджетом (проверено по всему `lib/`) — в интерфейсе также нет никакого
    индикатора «правка не отправлена» ни до, ни после этого прохода.

### Альтернативные потоки

- **В пакете несколько мест, отказ вызван состоянием сервера, не конкретным
  местом.** Поскольку весь пакет уходит одним запросом, невозможна ситуация
  «часть мест пакета отправилась успешно, часть — нет» на этом шаге, в отличие
  от фермы, где `break` посреди цикла может оставить и успешные, и
  неотправленные элементы в одном и том же неопределившемся состоянии. У места
  сама архитектура запроса делает исход пакета атомарным: либо весь пакет
  принят (`status == "1"`), либо весь пакет не подтверждён.
- **Два разных технических подтипа отказа объединены в один и тот же
  результат.** Не-`"1"` статус ответа сервера и брошенное исключение
  (сеть/таймаут) обрабатываются кодом абсолютно одинаково — оба ведут к
  `return false;` внутри одного и того же `catch`/`else`, без какого-либо
  различения причины дальше по потоку. Поэтому оба технических подтипа — часть
  этого же `UPDATE_ERROR`-сценария, не два разных use-case.
- **Перезагрузка списка (шаг 9) сама падает исключением** (например сеть
  пропала между PUT-вызовом и последующим GET). `FarmRepository
  .getAllFarmsAndPlacesFromRDS` не оборачивает сам вызов
  `rpcClientSHTP.call(message)` в `try/catch` — исключение здесь
  пробрасывается наружу через `_loadPlacesFromRDS` → `_syncPlaces` →
  `_syncAuthData` → внешний `try/catch` в `on<DataUpdateStartAll>` →
  `DataUpdateFailure`. В этом случае reload (шаг 10) не происходит вовсе,
  поэтому `needUpdate: true` у всех мест пакета **сохраняется** локально — их
  правки при этом не теряются и будут повторно предложены к отправке на
  следующем полном проходе. Это не основной, а более редкий побочный случай —
  обратный по исходу основному потоку при внешне похожей причине («не
  долетело до сервера»).
- **Перезагрузка (шаг 9) возвращает пустой список** (`response['status'] !=
  "1"` именно на этом GET-запросе). Тогда `if (res.isEmpty) return;`
  срабатывает раньше `clear()`/`insertAll()` — локальные места не трогаются
  вовсе, `needUpdate: true` сохраняется, они будут повторно предложены на
  следующем проходе. Как и предыдущий пункт — расходится с основным потоком
  только потому, что reload в этот раз не долетел до фактической перезаписи
  локальной таблицы.
- **`_storePlacesToRDS()` (шаг, предшествующий этому сценарию внутри
  `_syncPlaces`) сам не отправил на сервер часть новых мест в этом же
  проходе.** `PlaceRepository.storePlacesOnRDS` возвращает `[]` при отказе
  всего своего пакета (та же архитектура одного батч-запроса, что и у
  `updatePlacesOnRDS`); тогда `_placeRepository.updateAll(remotePlaces)` с
  пустым списком ничего не делает, и такие места остаются с отрицательным
  `idRemote`. Если у такого места `needUpdate` окажется `true`, фильтр
  `getAllToUpdate()` (`idRemote.isNotNull()`, а не `idRemote >= 0`) всё равно
  включит его в пакет этого сценария — поведение сервера на `PUT
  .../places/update` с отрицательным `id` в теле не проверялось в рамках
  этого use-case.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — единственная
  сущность, чьё состояние (данные полей и флаг `needUpdate`) меняется на всех
  этапах этого сценария: и на этапе неудачной отправки правки, и на этапе
  последующей безусловной перезаписи через reload.

### Бизнес-правила

- Места, требующие обновления на сервере, отправляются **одним** HTTP
  PUT-запросом на весь пакет — так же, как создание
  ([EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md),
  `PlaceRepository.storePlacesOnRDS`), но иначе, чем у фермы: и создание
  ([EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md)), и обновление
  ([EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md)) фермы идут по
  одной ферме за раз, в цикле. У места нет цикла вовсе на этом шаге — значит,
  нет и выбора между стратегией `break` и `continue`: батч атомарен по
  построению запроса, а не по логике обработки ответа.
- Успех/неудача пакета обновления фиксируется одним общим `bool` на весь вызов
  `updatePlacesOnRDS` — ровно как у фермы, но здесь это единственно возможный
  исход в принципе (один вызов — один ответ), а не следствие того, что цикл
  прервался после первых успешных итераций.
- Последующая полная перезагрузка списка мест с сервера
  ([EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md))
  выполняется в рамках того же прохода безусловно, сразу после попытки
  обновления, без какой-либо связи с её результатом — именно она, а не сама
  неудавшаяся отправка, окончательно определяет судьбу локальной правки:
  непереданные изменения замещаются серверной (для них — устаревшей) версией,
  а признак «требует отправки» сбрасывается в дефолтное значение колонки
  вместе с остальными полями строки.
- Ни неудача самой отправки, ни последующая потеря правки при reload не
  порождают ни исключения, долетающего до `DataUpdateStartAll`, ни
  какого-либо состояния ошибки, ни записи, видимой пользователю где-либо в
  UI — единственный след — текстовые сообщения в лог (`log(...)`), не
  выводимые никуда за пределы логов приложения.
- `getAllToUpdate()` фильтрует по `needUpdate == true` и `idRemote IS NOT
  NULL` — не по `idRemote >= 0`. По инварианту [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)
  отрицательный `idRemote` тоже «не null» (место, ещё не отправленное на
  сервер) — та же асимметрия фильтра, что и у фермы (см. «Открытые вопросы»
  [UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — весь сценарий, включая переход к следующему шагу
(`_loadPlacesFromRDS`) и его взаимодействие с уже неудавшимся обновлением,
прослеживается по существующему коду без пробелов, требующих уточнения у
пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешний `try/catch` прохода; ошибки, проглоченные внутри репозитория, до него не долетают — проход завершается `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксированная последовательность `_deletePlacesFromRDS` → `_syncFarms` → `_syncPlaces`, все шаги безусловны, без собственного `try/catch` вокруг каждого |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncPlaces` | CURRENT | фиксированная последовательность `_storePlacesToRDS` → `_updatePlacesOnRDS` → `_loadPlacesFromRDS`, все шаги безусловны |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._updatePlacesOnRDS` | CURRENT | получает места с `needUpdate:true`, вызывает `PlaceRepository.updatePlacesOnRDS` с пакетом целиком; сбрасывает `needUpdate` только при `isUpdated == true` для всего пакета |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadPlacesFromRDS` | CURRENT | безусловно следует за `_updatePlacesOnRDS`; при непустом ответе сервера полностью очищает и перезаписывает локальную таблицу `Places` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.updatePlacesOnRDS` | CURRENT | **один** `PUT .../places/update` с телом `{"places": [...]}` на весь пакет разом; нет цикла, нет `break`/`continue` — один `try/catch`, один `bool` на весь вызов |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllToUpdate` | CURRENT | запрос мест: `needUpdate.equals(true) & idRemote.isNotNull()` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllPlacesFromRDS` | CURRENT | делегирует в `FarmRepository.getAllFarmsAndPlacesFromRDS`, возвращает ключ `'places'` ответа |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.storePlacesOnRDS` | CURRENT | тот же паттерн одного батч-запроса, что и `updatePlacesOnRDS`, но для создания — упомянут в альтернативном потоке про рассинхронизацию фильтра `getAllToUpdate` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsAndPlacesFromRDS` | CURRENT | `GET .../farms?with_places=1` — общий сетевой вызов, используемый и `_loadFarmsFromRDS`, и `_loadPlacesFromRDS` (два отдельных HTTP-вызова на один и тот же эндпоинт за один проход); сам вызов не обёрнут в `try/catch` — исключение здесь пробрасывается наружу |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places.needUpdate` | CURRENT | `BoolColumn`, `withDefault(const Constant(false))` |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `PlaceExtension.fromJsonRDS` | CURRENT | конвертация серверного JSON в `PlacesCompanion`; поле `needUpdate` не указывается — берётся дефолт колонки |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear` / `insertAll` / `updateAll` | CURRENT | обёртки над `BaseDao`, используемые reload'ом (`clear`+`insertAll`) и несостоявшимся сбросом флага (`updateAll`) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` / `insAll` / `updAll` | CURRENT | drift-примитивы: `clear` удаляет все строки, `insAll` — `insertOrReplace` батчем, `updAll` — `upd` по одной записи в транзакции |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditPlace` | CURRENT | путь, которым локальная правка (предпосылка сценария) выставляет `needUpdate: true` — см. [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API ферм/мест, используемый в PUT/GET-запросах |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент, через который идут все PUT/GET-вызовы этого сценария |

## Критерии приёмки

- Если в пакете из N ≥ 1 мест с `needUpdate: true` единственный `PUT
  .../places/update` отвечает статусом, отличным от `"1"`, либо завершается
  исключением — `PlaceRepository.updatePlacesOnRDS` возвращает `false` для
  всего пакета целиком (проверяемо одним вызовом мока, без подсчёта повторных
  вызовов — их и не может быть больше одного).
- `DataUpdateBloc._updatePlacesOnRDS` при `isUpdated == false` не вызывает
  `PlaceRepository.updateAll` вовсе — ни для одного места пакета.
- `_updatePlacesOnRDS()`/`_syncPlaces()` завершаются без исключения
  (`completes`, а не `throwsA(...)`) — сбой не всплывает выше по цепочке
  вызовов.
- Если следующий за этим `_loadPlacesFromRDS()` получает непустой ответ от
  `GET .../farms?with_places=1`, локальная таблица `Places` полностью
  перезаписывается, и `needUpdate` каждой перезаписанной строки становится
  `false` — в том числе для места, чья правка не дошла до сервера в этом же
  проходе.
- Полный проход `DataUpdateStartAll` в этом сценарии завершается
  `DataUpdateSuccess`, не `DataUpdateFailure`, несмотря на то что как минимум
  одно место не было обновлено на сервере.

## Связанные тесты

TBD — теста нет. На уровне `data_update_bloc.dart` для sync-сценариев мест
(в т.ч. этого) тестов не существует: `test/blocs/data_update_bloc_test.dart`
содержит только тест конструирования блока и тест `DataUpdateClear`, ни
`_syncPlaces`, ни `_updatePlacesOnRDS`, ни `PlaceRepository.updatePlacesOnRDS`
там не упоминаются. Отдельного `test/repositories/place_repository_test.dart`
в репозитории не существует вовсе — `grep -rl "updatePlacesOnRDS" test/` не
находит ни одного файла. `test/pages/farms_and_places_bloc_test.dart` (группа
`'UC-9 — FarmsAndPlacesBloc._onEditPlace'`, старая нумерация, будет
переименовано, не трогать сейчас) покрывает только предпосылку этого сценария
(взведение `needUpdate: true` при локальном редактировании места), не сам
sync-шаг.

## Открытые вопросы и ограничения

- **Задокументированный, не устраняемый в этом проходе (TARGET == CURRENT)
  риск тихой потери данных.** Комбинация «весь пакет обновления не имеет
  собственного, независимого от соседей, подтверждения» + «безусловный reload
  сразу следующим шагом, стирающий `needUpdate` через дефолт колонки
  независимо от того, дошла ли правка до сервера» означает, что для любого
  места, чья правка не была принята сервером в конкретном проходе, эффект — не
  «попробуем на следующем проходе», а безвозвратная потеря правки уже в этом
  же проходе — при обычном, непустом ответе GET-эндпоинта. По форме риск
  идентичен ферме ([UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)), но у места он проявляется даже без `break`
  — потому что цикла с промежуточными успехами здесь никогда и не было.
- **Отсутствие любого пользовательского сигнала.** `Places.needUpdate` не
  читается ни одним виджетом в `lib/` — ни до, ни после такого прохода
  пользователь не видит признака «правка не отправлена» или «правка была
  отменена»; весь проход репортится как `DataUpdateSuccess`.
- **Несоответствие описанию в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).**
  Раздел «Ограничения» этого актора утверждает: «Фермы и места отправляются на
  сервер по одной, в цикле, не единым батчем — частичный успех возможен и не
  откатывает уже отправленные записи». Для ферм это подтверждается кодом; для
  мест — нет: и `PlaceRepository.storePlacesOnRDS` (создание), и
  `PlaceRepository.updatePlacesOnRDS` (этот сценарий) сериализуют весь пакет
  в тело одного запроса и отправляют его одним вызовом, без цикла по одному
  месту за раз. Частичный успех для места на этом шаге в принципе невозможен —
  ровно обратное тому, что написано в актор-спеке. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — уже
  зафиксированный (frozen) артефакт; это расхождение здесь только
  зафиксировано, не исправлено — исправление самого [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) вне периметра
  этой чисто документирующей задачи.
- **Асимметрия фильтра `getAllToUpdate()`.** Как и у фермы
  ([UC-27](UC-27-ACTOR-4-EVT-13-ENT-9-UPDATE_OK-IN-FARM.md),
  [UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)), фильтр
  проверяет `idRemote IS NOT NULL`, а не `idRemote >= 0` — если `store`-шаг
  (`_storePlacesToRDS`, тот же проход) для места того же пакета проваливается
  раньше по коду, а его `needUpdate` почему-то `true`, этот же проход подберёт
  его в `_updatePlacesOnRDS` и попытается выполнить `PUT /places/update` с
  отрицательным `id` в теле — поведение сервера на такой запрос не
  проверялось.
- **Дублирующий сетевой вызов reload'а.** `_loadFarmsFromRDS` и
  `_loadPlacesFromRDS` в рамках одного и того же прохода независимо вызывают
  `FarmRepository.getAllFarmsAndPlacesFromRDS()` — два отдельных HTTP GET на
  идентичный `${Constants.registrationServiceApi}/farms?with_places=1` за один
  проход, без общего кеша между вызовами. Не специфично для сценария ошибки
  этого файла, но напрямую участвует в шаге 9/10 основного потока.
