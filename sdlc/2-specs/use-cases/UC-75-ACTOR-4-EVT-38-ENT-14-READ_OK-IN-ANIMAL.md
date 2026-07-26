# UC-75 — Sync-проход успешно перезагружает список вакцинаций с сервера

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В конце полного sync-прохода, инициированного пользователем, после трёх
push-шагов (delete → update → create) система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) безусловно запрашивает у
сервера постранично полный список вакцинаций и полностью замещает содержимое
локальной таблицы `Vaccinations` полученным ответом — без ошибки на самом
запросе (`RESULT = READ_OK`). Ещё не синхронизированные строки, существовавшие
на момент замены, снимаются перед очисткой и возвращаются в таблицу отдельным
шагом сразу после замены. Happy-path сценарий события
[EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md)
(`vaccinations.reloaded_from_server`).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком (авторизованным пользователем —
шаг гейтится `AuthRepository.isAuthorized()`) один раз (`DataUpdateStartAll`),
но в каждом отдельном сетевом вызове этого сценария человек не участвует.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. При отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка).
2. Через `_syncAuthData` → `updateAndSyncRegagro` → `_syncAllData` — тот же
   вход, что уже описан в
   [UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md) и
   [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md) (не
   переизлагается здесь целиком) — доходит до **последнего** доменного шага
   прохода: `await _vaccinationsRepository.syncVaccinations(true)`. Это
   единственная точка вызова в кодовой базе (подтверждено `grep` по
   `syncVaccinations(` в `lib/`); `isDeleteErrors` нигде не передаётся,
   значит всегда остаётся дефолтным `false`.
3. `VaccinationsRepository.syncVaccinations(isFullSync: true)`: так как
   `isFullSync == true`, сначала выполняются три push-шага в фиксированном
   порядке — `_deleteVaccinationFromApi()`
   ([EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)),
   `_updateVaccinationFromApi()`
   ([EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md)),
   `_sendVaccinationsToApi()`
   ([EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md))
   — все вне рамок этого use-case. Delete- и update-шаги перехватывают любое
   собственное исключение внутри себя (`catch` без `rethrow`) и никогда не
   прерывают остаток метода. Create-шаг (`_sendVaccinationsToApi`) перехватывает
   `DioException` на каждую отдельную запись индивидуально внутри цикла, но
   его внешний `catch` **делает `rethrow`** — то есть в этом (`READ_OK`)
   сценарии подразумевается, что ни один из трёх push-шагов не выбросил
   исключение наружу (см. «Альтернативные потоки» — редкий случай, когда это
   не так).
4. `vaccinationsWithErrors = await _getNotSyncVaccinations()` →
   `VaccinationsDao.getNotSyncVaccinations()` — `SELECT * FROM vaccinations
   WHERE sync = false`, без разбора по `createdAt`/`updatedAt`/`deletedAt`
   (снимок всех трёх состояний сразу). Снимок делается **после** трёх
   push-вызовов шага 3.
5. `await dao.clear()` → `BaseDao.clear()` = `delete(_currentTableInfo).go()`
   — безусловно удаляет **все** строки таблицы `Vaccinations`, включая
   строки, которые к этому моменту всё ещё не синхронизированы (снятые на
   шаге 4).
6. `await _getVaccinationsFromApi()` — ядро этого сценария:
   1. `allVaccinations = <VaccinationDto>[]`; вызывается
      `paginatedRequestHandler<List<VaccinationDto>>(perPage: 500, onRequest:
      _fetchVaccinationsPage, onResponse: ...)`.
   2. `_fetchVaccinationsPage(page, perPage)` строит `ApiMessage(link:
      '${Constants.registrationServiceApi}/vaccinations', method:
      ApiMethod.get, data: {"page": page, "per_page": perPage})` и выполняет
      его через `getIt.get<ApiClient>(instanceName: 'farm_rpc').call(message)`.
   3. Если `response['errors'] != null` — бросается `Exception(...)` (другой,
      `READ_ERROR`-сценарий, не этот файл). В этом (`READ_OK`) сценарии условие
      ложно на каждой странице.
   4. Иначе `(response['data'] as List?)?.map((e) =>
      VaccinationDto.fromJson(e)).toList() ?? []` — маппинг ответа страницы.
   5. `onResponse`: `allVaccinations.addAll(response); return
      response.isEmpty;` — цикл `paginatedRequestHandler` продолжается, пока
      очередная страница не вернёт пустой список. Важно: критерий остановки —
      именно пустота страницы, а не `response.length < perPage` — поэтому
      даже последняя фактическая страница с ровно `500` записями (или любым
      непустым количеством) не останавливает цикл сама по себе: всегда
      следует ещё один `GET`-запрос, который должен вернуть пустой массив,
      прежде чем цикл завершится.
   6. После накопления всех страниц — цикл `for (var vaccination in
      allVaccinations)`: для каждой записи **последовательно**:
      - `final id = await insert(vaccination.toCompanion())` →
        `dao.ins(..., mode: InsertMode.insertOrReplace)` в уже пустую (после
        шага 5) таблицу. `VaccinationDtoMapper.toCompanion()` не задаёт `id`
        явно (колонка — настоящий SQLite `AUTOINCREMENT`, растущий
        монотонно), поэтому каждая строка получает новый локальный `id`;
        серверный id сохраняется отдельно в `shtpId: Value(id)` (поле DTO
        `id` — не локальный id). `sync: const Value(true)` — жёстко
        захардкожено (пул с сервера всегда считается синхронизированным по
        определению, независимо от содержимого ответа). Остальные поля
        маппятся 1:1: `vaccineId` ← `medicineId`, `unitId` ← `doseId`,
        `injectionMethodId` ← `injectionTypeId`, `injectionPlaceId` ←
        `injectionPlaceId`, `notes` ← `comment`, `nextVaccinationDate` ←
        `revaccinationDate`, `series` ← `serie`, `productionDate` ←
        `manufacturedDate`, `expirationDate` ← `expirationDate`,
        `createdAt`/`updatedAt`/`deletedAt` — парсятся из ISO-строк через
        `DateTime.parse`, если не `null`. `animalId` копируется как есть, без
        проверки, резолвится ли он в существующую локальную `Animal` — в
        отличие от всех трёх push-выборок (`getEditableVaccinationsWithDetails`
        /`getDeletableVaccinationsWithDetails`/`getNotSyncVaccinationsWithDetails`),
        которые молча исключают строку, если `AnimalsDao.getAnimalWithDetailsById`
        вернул `null`. Схема `Vaccinations.animalId` объявлена с constraint'ом
        `REFERENCES animals(id) NOT NULL`, но ни в одном месте настройки
        основного соединения БД (`AppDatabase._openConnection`,
        `MigrationStrategy`) не найдено `PRAGMA foreign_keys = ON`
        (подтверждено `grep` по `packages/sheep_farm_database/lib/` — прагма
        встречается только внутри сгенерированного `Clearable`-механизма
        полной очистки БД, не в обычном пути записи) — не подтверждено,
        включено ли принудительное соблюдение внешних ключей для обычных
        `INSERT` в этом приложении.
      - `_diseasesVaccinationsRepository.saveDiseasesVaccinations(id,
        vaccination.diseasesIds.whereType<int>().toList())` — вызывается
        **без `await`**, подтверждено чтением
        `VaccinationsRepository._getVaccinationsFromApi`. `.whereType<int>()`
        отбрасывает возможные `null`-элементы серверного массива
        `diseases_ids` (поле DTO типизировано как `List<int?>`). Внутри
        `saveDiseasesVaccinations` (сама она свои два шага awaits'ит
        последовательно) — `dao.clearByVaccinationId(id)` (не находит ничего
        для только что вставленного нового `id`) и батч-вставка
        `DiseasesVaccinationsCompanion` по одному на каждый id болезни.
      - Так как вызов не awaits'ится, цикл переходит к следующей вакцинации
        (и сам метод `_getVaccinationsFromApi` может завершиться) **до** того,
        как гарантированно завершится запись связок `DiseasesVaccinations`
        для текущей вакцинации — на момент возврата из этого метода строка
        `Vaccination` гарантированно существует в БД, но соответствующие ей
        строки `DiseasesVaccinations` — нет.
   7. Тело всего метода обёрнуто в `try { ... } catch (e, st) {
      getIt<Talker>().info('getVaccinationsFromApi Error: $e st: $st');
      rethrow; }` — но этот `catch` способен перехватить только исключение,
      всплывшее синхронно в рамках этой же цепочки `await` (сбой страницы,
      сбой `insert`, синхронное исключение при самом вызове
      `saveDiseasesVaccinations`). Исключение, брошенное **внутри** не
      awaits'нутого `Future`, возвращённого `saveDiseasesVaccinations`, этим
      `catch`-блоком не перехватывается и не логируется этой строкой — оно
      становится необработанной асинхронной ошибкой отдельно от этого вызова.
      `grep -rn "runZonedGuarded"` по всему `lib/` не находит ни одного
      глобального перехватчика зон — подтверждённого перехвата такой ошибки
      где-либо ещё в кодовой базе нет.
7. Управление возвращается в `syncVaccinations`: `if (!isDeleteErrors)
   dao.insAll(vaccinationsWithErrors);` — `isDeleteErrors` на единственной
   точке вызова (шаг 2) всегда `false`, поэтому ветка выполняется. **Этот
   вызов тоже не awaits'ится** (подтверждено чтением исходного текста
   `syncVaccinations` — `dao.insAll(vaccinationsWithErrors);` без `await`
   перед ним, при том, что сам метод `async`). Следствие: тело
   `syncVaccinations` завершается (его собственный `Future` резолвится) не
   дожидаясь гарантированного завершения этой батч-вставки — снимок
   `vaccinationsWithErrors` (по факту вставки — `insertOrReplace`, с теми же
   исходными `id`, полями и `sync == false`, что и до `dao.clear()` на шаге 5)
   лишь **запущен**, а не подтверждённо завершён, к моменту, когда
   `await _vaccinationsRepository.syncVaccinations(true)` на шаге 2
   возвращает управление в `_syncAllData`, а дальше — в `DataUpdateSuccess`.

Итоговый наблюдаемый эффект в локальной БД к концу этого (`READ_OK`) шага:
таблица `Vaccinations` содержит полный набор строк с сервера (новые
локальные `id`, `sync == true`), и, при отсутствии ошибок на предыдущих
шагах, следом — прежние ещё не синхронизированные строки в исходном виде.
Оба финальных состояния (пул и реинсерт) достигаются каждое своим
не-awaits'нутым вызовом, без единой транзакции и без гарантии порядка
завершения относительно возврата из `syncVaccinations`.

### Альтернативные потоки

- **Один из трёх предшествующих push-шагов пробрасывает исключение наружу.**
  Delete- и update-шаги перехватывают собственные исключения без `rethrow` и
  никогда этого не делают. Create-шаг (`_sendVaccinationsToApi`) перехватывает
  только `DioException` на уровне отдельной записи внутри цикла; любое иное
  исключение вне этого внутреннего `catch` (например, сбой самого
  `getNotSyncVaccinationsWithDetails()`, или non-`DioException` ошибка в
  `_addErrorsToVaccinations`/`deleteById`) долетает до внешнего `catch`
  `_sendVaccinationsToApi`, который делает `rethrow`. В этом (редком) случае
  `syncVaccinations` сама выбрасывает исключение сразу после шага 3, **до**
  шага 4 (снимок) — весь остаток этого use-case (снимок/`clear`/pull/реинсерт)
  не выполняется вовсе в этом проходе, [EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md)
  не наступает. Исключение всплывает до внешнего `try/catch` в
  `on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure` и завершает
  **весь** sync-проход ошибкой — не описывается этим файлом.
- **`response['errors'] != null` на какой-либо странице, либо сетевой сбой
  внутри `_fetchVaccinationsPage`/`paginatedRequestHandler`.** Исключение
  логируется через `Talker.info` и пробрасывается (`rethrow`) из
  `_getVaccinationsFromApi` — в отличие от аналогичного pull-шага Movement
  ([EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)), где такое же по
  роли исключение только логируется и проглатывается. Здесь оно прерывает
  `syncVaccinations` и весь sync-проход целиком. `READ_ERROR`-сценарий, не
  этот файл.
- **Пустой ответ с первой же страницы.** `response.isEmpty` истинно сразу —
  `allVaccinations` остаётся пустым списком, цикл вставки (шаг 6.6) не
  выполняется ни разу. Таблица `Vaccinations`, уже очищенная шагом 5,
  остаётся пустой (до реинсерта снимка шагом 7) — тот же `RESULT` (`READ_OK`
  — запрос успешно завершился, просто без серверных данных), не отдельный
  use-case.
- **Ошибка внутри не awaits'нутого `saveDiseasesVaccinations` или
  не awaits'нутого финального `dao.insAll(vaccinationsWithErrors)`.** Ни
  одна из них не перехватывается локальным `try/catch` соответствующего
  метода (см. «Основной поток», шаг 6.7) и не влияет на то, произойдёт ли
  `rethrow`/`DataUpdateFailure` — с точки зрения `on<DataUpdateStartAll>` весь
  проход по-прежнему может завершиться `DataUpdateSuccess`, даже если одна из
  этих фоновых записей фактически провалилась. Не отдельный `RESULT`, потому
  что она никак не проявляется ни в одном из закрытых значений `RESULT`
  данного дерева — просто тихий побочный эффект без наблюдаемого исхода на
  уровне use-case.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность сегмента `ENT`: таблица физически переписывается целиком
  (`delete`+`insert`, не `update` существующих строк) — при непустом ответе
  каждая пришедшая с сервера запись получает новый локальный `id`; ещё не
  синхронизированные строки, существовавшие до `clear()`, восстанавливаются
  отдельным (не awaits'нутым) шагом сразу после пула.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим шагом; поле `animal_id` серверного JSON копируется в
  `Vaccination.animalId` без резолва/проверки существования (в отличие от
  всех трёх push-выборок того же репозитория, см. «Основной поток», шаг
  6.6).
- `Disease` (через связочную таблицу `DiseasesVaccinations`) — для каждой
  пришедшей вакцинации перезаписывается заново (`clearByVaccinationId` +
  батч-вставка) на основе `diseases_ids` ответа; не имеет собственного
  `ENT`-id в этом дереве (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  «Связи»).
- `Vaccine`, `Unit`, `InjectionMethod`, `InjectionPlace`, `VaccinationType` —
  VAC-локальные справочники ([ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md)
  (Unit, HANDBOOKS) — кросс-модульный, остальные без собственного `ENT`-id) —
  этим шагом не читаются и не пишутся; только их id копируются как
  foreign-key поля пришедшей строки, без валидации, что такая справочная
  запись существует локально.

### Бизнес-правила

- Пул — безусловная замена «всё или ничего» на уровне самой таблицы
  `Vaccinations` (`clear()` без фильтра по `sync`, затем полная перезапись
  постранично полученным ответом), но с отдельным механизмом сохранения
  «хвоста» ещё не синхронизированных строк вокруг этой замены (снимок до
  `clear()`, реинсерт после пула) — тот же принцип «ни одна неотправленная
  строка не теряется при полном sync-проходе», что зафиксирован в
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), применяется здесь как
  для строк, которые пришли с сервера, так и для строк, которые остались
  локальными.
- Критерий остановки пагинации — пустота очередной страницы
  (`response.isEmpty`), не `response.length < perPage`: всегда минимум один
  дополнительный `GET`-запрос после последней фактически непустой страницы.
- **Пуловая вставка (`insert`) и вставка связей болезней
  (`saveDiseasesVaccinations`) для одной и той же строки выполняются не в
  одной транзакции, и вторая явно не awaits'ится** — на любой момент времени
  между этими двумя шагами может существовать `Vaccination` без единой
  связанной `DiseasesVaccinations`-строки, даже при полностью успешном сетевом
  ответе.
- **Финальный реинсерт снятого до `clear()` снимка (`dao.insAll(vaccinationsWithErrors)`)
  тоже явно не awaits'ится** — успешное завершение `syncVaccinations` (и,
  соответственно, всего sync-прохода с `DataUpdateSuccess`) не гарантирует,
  что эта батч-вставка уже завершилась к этому моменту.
- Ошибка на самом сетевом получении списка (`_fetchVaccinationsPage`/
  `response['errors']`) пробрасывается наружу и прерывает весь sync-проход —
  асимметрично по отношению к аналогичному pull-шагу Movement, где такая же
  по роли ошибка только логируется (см. «Альтернативные потоки»,
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)).
- `animalId` пришедшей строки не валидируется против локальной таблицы
  `Animal` этим шагом (в отличие от всех трёх push-выборок того же
  репозитория) — раз строка существует на сервере, она вставляется локально
  независимо от того, есть ли локально резолвящееся животное.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и выполняется безусловно на каждом
полном sync-проходе (после трёх push-шагов), при условии что ни один из них не
пробросил исключение наружу (см. «Альтернативные потоки»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>`, `_syncAuthData`, `updateAndSyncRegagro` | CURRENT | общий префикс полного sync-прохода до вакцинаций (проверка сети/авторизации, гейтинг повтора) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_vaccinationsRepository.syncVaccinations(true)` последним доменным шагом прохода, единственная точка вызова, `isDeleteErrors` не передаётся (дефолт `false`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: delete → update → create push → снимок несинхронизированных строк → `dao.clear()` → `_getVaccinationsFromApi` (этот use-case) → не-awaits'нутый реинсерт снимка |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getVaccinationsFromApi` | CURRENT | ядро этого use-case: постраничный `GET`, вставка каждой строки через `insert`, не-awaits'нутый вызов сохранения связей болезней, `try/catch` с `rethrow` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._fetchVaccinationsPage` | CURRENT | построение и выполнение одного постраничного `GET`-запроса, проверка `response['errors']` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getNotSyncVaccinations` | CURRENT | снимок всех `sync == false` строк до `dao.clear()` |
| `lib/repositories/base_repository.dart` | `BaseRepository.paginatedRequestHandler`, `BaseRepository.insert`, `BaseRepository.insertAll` | CURRENT | общий постраничный цикл (критерий остановки — пустая страница); обёртки над `dao.ins`/`dao.insAll` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | безусловный `SELECT ... WHERE sync = false`, без разбора по состояниям |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.ins`, `BaseDao.insAll` | CURRENT | `clear()` — `DELETE` всей таблицы без фильтра; `ins()`/`insAll()` — `insertOrReplace`, `id` не переиспользуется благодаря `AUTOINCREMENT` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations.id`, `Vaccinations.animalId` | CURRENT | `id` — `integer().autoIncrement()` (настоящий SQLite `AUTOINCREMENT`); `animalId` — `REFERENCES animals(id) NOT NULL`, соблюдение не подтверждено (см. «Основной поток», шаг 6.6) |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDto`, `VaccinationDto.fromJson`, `VaccinationDtoMapper.toCompanion` | CURRENT | парсинг серверного JSON, маппинг в `VaccinationsCompanion` (`sync: Value(true)` жёстко, `id` не задаётся) |
| `lib/repositories/vaccination/diseases_vaccinations_repository.dart` | `DiseasesVaccinationsRepository.saveDiseasesVaccinations` | CURRENT | вызывается без `await` из `_getVaccinationsFromApi`; сама последовательно awaits'ит `clearByVaccinationId` + батч-вставку |
| `packages/sheep_farm_database/lib/entities/vaccination/diseases/diseases_vaccinations_dao.dart` | `DiseasesVaccinationsDao.clearByVaccinationId` | CURRENT | удаление прежних связей болезней перед перезаписью (для нового `id` — не находит ничего) |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL для эндпоинта `/vaccinations` |
| `packages/sheep_farm_database/lib/database/database.dart` | `AppDatabase._openConnection`, `AppDatabase.migration` | CURRENT | подтверждает отсутствие `PRAGMA foreign_keys = ON` на основном соединении |
| `packages/sheep_farm_database/lib/database/database.clearable.dart` | `PRAGMA foreign_keys = OFF`/`ON` | CURRENT | единственное место в пакете, где эта прагма вообще упоминается — другой, не относящийся к этому шагу путь полной очистки БД |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и после того,
  как ни один из трёх предшествующих push-шагов (`_deleteVaccinationFromApi`,
  `_updateVaccinationFromApi`, `_sendVaccinationsToApi`) не пробросил
  исключение наружу, полный sync-проход запрашивает `GET
  {registrationServiceApi}/vaccinations` постранично (`per_page=500`), пока
  очередная страница не вернёт пустой массив `data`.
- Если ни на одной странице `response['errors']` не непусто, накопленный
  список вставляется в локальную таблицу `Vaccinations` (уже полностью
  очищенную безусловным `dao.clear()`) — по одной строке за раз, каждая с
  новым локальным `id`, `sync == true`, и `shtpId`, равным серверному `id`.
- Для каждой вставленной строки инициируется (без ожидания завершения)
  перезапись связей `DiseasesVaccinations` по списку ненулевых
  `diseases_ids` ответа.
- Если на момент снимка (`_getNotSyncVaccinations`, до `dao.clear()`)
  существовали ещё не синхронизированные строки — они снова присутствуют в
  локальной таблице после этого шага (запущенный, но явно не awaits'нутый
  `dao.insAll(...)`), если только `syncVaccinations` не был вызван с
  `isDeleteErrors: true` (на реальном вызывающем сайте не встречается).
- Если любая страница возвращает непустой `response['errors']`, либо сам
  сетевой вызов бросает исключение, `_getVaccinationsFromApi` логирует
  ошибку и пробрасывает исключение наружу — весь sync-проход завершается
  `DataUpdateFailure` (другой, `READ_ERROR`-сценарий).

## Связанные тесты

`TBD — теста нет.` В `test/repositories/vaccinations_repository_test.dart`
единственные группы, где `syncVaccinations(true)` реально вызывается —
`'UC-72 — VaccinationsRepository.syncVaccinations(isFullSync: true) — edit
push'` и `'UC-70 — VaccinationsRepository.syncVaccinations(isFullSync: true)
— delete push'` (числа `94`/`100` — старая нумерация, группы будут
переименованы отдельным контролируемым проходом, не трогаются здесь). Во
всех четырёх тестах этих групп мок `farmRpcClient.call` для `method ==
ApiMethod.get` (т.е. для эндпоинта `/vaccinations`, предмета этого файла)
настроен так, что **всегда возвращает `{'data': <dynamic>[]}`** — пустой
успешный ответ. Это технически проходит через ветку `READ_OK`, но с пустым
`allVaccinations` (см. «Альтернативные потоки» — вырожденный случай), и ни
один из этих тестов не проверяет ни сам факт вставки пришедших с сервера
записей, ни присвоение нового `id`/`sync == true`, ни вызов
`saveDiseasesVaccinations`, ни реинсерт снятого снимка. Подтверждено `grep`
по `test/` — `VaccinationDto`/`getVaccinationsFromApi` встречаются только в
`lib/`, ни в одном тестовом файле нет конструирования непустого ответа
`/vaccinations`. Отдельно подтверждено, что в
`test/blocs/data_update_bloc_test.dart`,
`test/repositories/animals_repository_test.dart` и
`test/integration/registration_to_disposal_test.dart`
`VaccinationsRepository` присутствует только как полностью замоканная
зависимость (`MockVaccinationsRepository`) — ни `syncVaccinations`, ни
`_getVaccinationsFromApi` там не вызываются вовсе.

## Открытые вопросы и ограничения

- **Реинсерт снимка не awaits'ится вызывающим кодом.** `syncVaccinations`
  вызывает `dao.insAll(vaccinationsWithErrors)` без `await` внутри `async`
  метода — сам `syncVaccinations` (и, соответственно, весь sync-проход,
  вплоть до `DataUpdateSuccess`) может завершиться раньше, чем эта
  батч-вставка гарантированно закончится. Верифицировано чтением исходного
  текста `VaccinationsRepository.syncVaccinations`; не проверялось
  интеграционным тестом с реальным SQLite, чем именно это может проявиться
  на практике (гонка с последующим экраном, читающим таблицу сразу после
  «успешного» прохода, либо просто фактическое завершение записи раньше, чем
  Dart успевает продолжить выполнение — однопоточная модель событийного цикла
  сужает окно, но не устраняет его логически).
- **Сохранение связей болезней тоже не awaits'ится.** Внутри цикла
  `_getVaccinationsFromApi` вызов `saveDiseasesVaccinations` не дожидается
  завершения перед переходом к следующей вакцинации и перед возвратом из
  метода — на момент, когда `_getVaccinationsFromApi` считается успешно
  завершённым, для только что пришедших строк `Vaccination` таблица
  `DiseasesVaccinations` может быть ещё не заполнена. Любая ошибка внутри
  этого не-awaits'нутого вызова становится необработанной асинхронной
  ошибкой: не перехватывается локальным `try/catch` метода, не логируется
  этой строкой лога, и не найдено ни одного `runZonedGuarded` в `lib/`,
  который мог бы перехватить её на более высоком уровне — подтверждено
  `grep`, но не проверялось, ловит ли её (и как реагирует на это) сам Flutter
  framework/Dart VM по умолчанию в релизной сборке.
- **Отсутствие `PRAGMA foreign_keys = ON` на основном соединении.**
  `Vaccinations.animalId` объявлен как `REFERENCES animals(id) NOT NULL`, но
  этот шаг вставляет строку с `animalId` из серверного ответа без резолва в
  локальную `Animal` — если constraint не соблюдается движком (что
  правдоподобно при отсутствии `PRAGMA foreign_keys = ON`, подтверждённом
  `grep`-ом по `packages/sheep_farm_database/lib/`), вставка успешно
  проходит независимо от того, существует ли такое животное локально; если
  же где-то (например, платформенный дефолт `sqlite3`/пакета `drift`) эта
  прагма всё же включена не в исходном коде этого репозитория, поведение
  могло бы быть другим — не проверялось эмпирически (интеграционным тестом с
  реальным SQLite-файлом).
- **Критерий остановки пагинации требует лишнего запроса.**
  `paginatedRequestHandler` останавливается по пустоте страницы, а не по
  `length < perPage` — при, например, ровно `500` вакцинациях на сервере
  потребуется два `GET`-запроса вместо одного (второй вернёт пустой массив).
  Не влияет на корректность результата, но не проверялось, насколько это
  значимо с точки зрения затрат на большом количестве данных — вне рамок
  этого документирующего прохода.
- **Асимметрия обработки ошибок между этим шагом и аналогичным pull'ом
  Movement.** Ошибка `_getVaccinationsFromApi` прерывает весь sync-проход
  (`rethrow`); аналогичная по роли ошибка `MovementReportRepository
  .getReportsFromApiAndSave` (см.
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)) только
  логируется и не прерывает ничего. Два разных паттерна обработки ошибок для
  двух структурно похожих pull-шагов одного и того же sync-прохода, не
  унифицированы — поведение существующего кода, не предмет исправления в
  этом документирующем проходе.
- Нет теста, покрывающего непустой успешный ответ `/vaccinations` (см.
  «Связанные тесты») — весь `READ_OK`-путь этого use-case, включая обе
  находки про не-awaits'нутые вызовы выше, проверен только чтением кода, не
  исполнением.
