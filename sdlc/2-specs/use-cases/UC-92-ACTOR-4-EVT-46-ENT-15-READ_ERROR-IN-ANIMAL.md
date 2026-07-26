# UC-92 — Система не может перезагрузить взвешивания (вместе с животными и идентификациями) с сервера при полном sync-проходе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь, система
достигает шага `DataUpdateBloc.loadAnimals` — единственного места в кодовой базе,
которое одновременно перезагружает три таблицы одним вызовом: `Animals`,
`AnimalIdentifications` и `AnimalWeighings` (взвешивания вложены в тот же ответ
сервера `GET .../animals`, что и сами животные). Этот файл — сценарий, в котором
этот шаг не может быть выполнен: исключение не глотается ни на одном уровне —
`loadAnimals` перехватывает его собственным `try/catch (_) { rethrow; }`, то есть
логически пробрасывает как есть, — и долетает до общего `try/catch` вокруг всего
sync-прохода в `DataUpdateBloc.on<DataUpdateStartAll>`, обрывая проход целиком.
Ошибка не специфична для взвешиваний: она в равной мере может возникнуть из-за
сбоя, относящегося к животным, к их идентификациям, либо непосредственно к
`weight_history`-блоку взвешиваний внутри ответа — исход (`READ_ERROR`, обрыв
всего прохода) один и тот же независимо от того, какая из трёх сущностей стала
непосредственной причиной.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода (`DataUpdateBloc`), без участия пользователя в момент именно этого
шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена успешно,
   `_authRepository.isAuthorized()` истинно, выполнение дошло до `_syncAuthData`
   → (после `_deletePlacesFromRDS`, `_syncFarms`, `_syncPlaces`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` — push взвешиваний,
   [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md),
   завершается независимо от исхода: единственный `catch` внутри него делает
   `getIt<Talker>().handle(e, stackTrace)` без `rethrow`) → `updateAndSyncRegagro`
   → `_syncAllData`.
2. Внутри `_syncAllData` к этому моменту уже отработали (по порядку)
   `_clearDataUpdates()`, `loadUser`, `syncAllUnsentAnimals()`,
   `_settingsRepository.getSettingFromSHTP()` (+ опционально
   `setSettingToSHTP()`), `_movementReportRepository.syncMovements()`,
   `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`. Следующий вызов
   в теле метода — `await loadAnimals(event, emit)`; после него в этом же теле
   идёт `await _vaccinationsRepository.syncVaccinations(true)` (см.
   [UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md) — сценарий, где
   уже этот следующий шаг проваливается; здесь падает более ранний шаг,
   `syncVaccinations` в этом проходе не вызывается вовсе).
3. `loadAnimals` первым делом вызывает `_emitProgress(dataKey: DataKey.animals,
   dataCategory: DataCategory.animals)` — этот шаг, в отличие от
   `syncVaccinations` в [UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md),
   эмитит собственный прогресс непосредственно перед попыткой работы, поэтому
   ключ `animals`, под которым в итоге будет показана ошибка, здесь — не
   унаследованный от более раннего шага случайный артефакт, а действительно
   верно указывает на сам упавший шаг.
4. `loadAnimals` последовательно, каждый вызов — отдельным немедленно
   зафиксированным (не входящим в общую транзакцию) действием, выполняет:
   - `await _animalsRepository.clear()` → `dao.clear()` →
     `BaseDao.clear()` = `(delete(_currentTableInfo)).go()` — **безусловно**
     удаляет вообще все строки `Animals`, включая ещё не синхронизированные
     локальные (`id < 0`);
   - `await _animalIdentificationsRepository.clear()` → тот же
     `BaseDao.clear()` — безусловно удаляет вообще все строки
     `AnimalIdentifications`;
   - `await _animalWeighingsRepository.clearSync()` → `AnimalWeighingsDao.clearSync()`
     = `(deleteCurrent()..where((tbl) => tbl.sync.isValue(true))).go()` —
     удаляет только строки `AnimalWeighings` с `sync == true` (ещё не
     отправленные, `sync == false`, — не трогает).
5. `await _animalsRepository.syncAllAnimals()` — предмет этого use-case.
   Строит постраничный опрос `GET ${Constants.registrationServiceApi}/animals`
   (`with_trashed: 1`, `with_weight: 1`, `perPage: 1000`) через
   `paginatedRequestHandler` (без собственного `try/catch`, пробрасывает
   исключение из `onRequest`/`onResponse` как есть), накапливая все страницы в
   память в `AnimalsDto` (`animals`, `identifications`, `animalWeigings`).
6. Исключение возникает в одной из точек:
   - внутри `_fetchAnimalsPage` (сетевой сбой самого вызова
     `rpcClientSHTP.call(message)`, либо ошибка внутри
     `AnimalsDto.fromJson(response['data'])`, куда обёрнут весь один HTTP-вызов
     единым `try/catch (e, stackTrace) { ...; rethrow; }`);
   - конкретно для взвешиваний — `AnimalsDto.fromJson` для каждого животного
     из `weight_history` строит `AnimalWeighingDto.fromJson(e).toAnimalWeighing(animal.id)`;
     `AnimalWeighingDto.fromJson` — сгенерированный `json_serializable`-код,
     бросающий исключение, если в конкретной записи `weight_history` любого
     животного на любой странице отсутствует/не того типа обязательное поле
     (`id`, `weight`, `weighing_date`) — попадает в тот же `try/catch`
     `_fetchAnimalsPage`, что и сетевой сбой;
   - либо (реже) внутри `db.transaction` шага 7 (батч-вставка/удаление).
7. Если пагинация целиком успешна, `syncAllAnimals` дальше вызывает
   `getAllLocalUnsynced()` (фильтр `id < 0`) и (если непусто)
   `_animalIdentificationsRepository.getAllByAnimalIds`, затем один
   `db.transaction`, который повторно `db.delete(db.animals).go()` +
   `db.delete(db.animalIdentifications).go()` (уже избыточно — обе таблицы уже
   пусты после шага 4), батчем вставляет `animals`/`identifications`/
   `animalWeigings` из ответа, и — если среди локальных id остались такие,
   которых нет в `serverIds` — восстанавливает их и их идентификации отдельным
   батчем. Любое исключение внутри тела `db.transaction` (сбой батч-вставки,
   нарушение ограничения) откатывает **весь** `db.transaction` целиком
   (стандартное поведение drift-транзакции) — в отличие от push-цикла
   `Vaccination` ([UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)),
   здесь частичная вставка части строк с потерей остатка невозможна, если сбой
   произошёл именно внутри этой транзакции.
8. `_fetchAnimalsPage` логирует через `log('Error in _fetchAnimalsPage: $e',
   stackTrace: stackTrace)` и делает `rethrow`. `syncAllAnimals` не оборачивает
   собственное тело в `try/catch` — исключение всплывает наружу без
   дополнительного логирования на этом уровне.
9. `loadAnimals` перехватывает исключение единственным `catch (_) { rethrow; }`
   (без логирования на этом уровне) — логически пробрасывает его без изменений
   дальше. Строка `await _addDataUpdateSuccess(_currentDataCategory)`, которая
   зафиксировала бы успешное завершение шага в журнале `DataUpdates`, **не
   выполняется**.
10. Исключение продолжает всплывать через `_syncAllData` → `updateAndSyncRegagro`
    → `_syncAuthData` (все — `await` без собственного `try/catch`), поэтому
    `_vaccinationsRepository.syncVaccinations(true)` (последний вызов в теле
    `_syncAllData`, идущий сразу после `loadAnimals`) и шаги `updateAndSyncSHTP`/
    `_suncDevices()`, идущие в `_syncAuthData` после `updateAndSyncRegagro`, в
    этом проходе **не вызываются вовсе** — до внешнего `try/catch` в
    `DataUpdateBloc.on<DataUpdateStartAll>` (строки его тела: `try { ... } catch
    (error, stackTrace) { ...; await _emitError(...); } finally { ... }`).
11. Внешний `catch` логирует через `getIt<Talker>().error('Возникла при
    обновлении данных $error $stackTrace')` и вызывает `_emitError`, которая
    пишет в `DataUpdates`-журнал строку с `dataCategory: _currentDataCategory`
    (`DataCategory.animals`), `errorDataKey: _currentDataKey` (`DataKey.animals`),
    `errorMessage: 'error: $error, stackTrace: $stackTrace'`, и эмитит
    `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey:
    'animals', errorMessage: ...)`.
12. `finally`-блок обработчика `on<DataUpdateStartAll>` всё равно выполняется
    (`resetClient` для обоих `ApiClient`-инстансов — `farm_rpc` и `r3_rpc`),
    независимо от исхода `try`.
13. Пользователь на экране `DataUpdatePage` видит общий экран ошибки
    синхронизации (`DataUpdateInProgressWidget(isError: true)`,
    `_Body.build`, ветка `state is DataUpdateFailure`) с текстом
    `tr('an_error_data')` + `tr('animals')` и кнопками «Попробовать снова»
    (`DataUpdateStartAll(again: true, showDataUpdatePage: false)`, что
    запускает `_syncAllData` заново **с самого начала**, а не с шага
    `loadAnimals`) и «На главную» (`go_to_home` — закрывает экран, уходит на
    `Routes.mainNavigator`, инициирует проверку обновления приложения).

### Альтернативные потоки

- **Сбой на конкретной странице пагинации после того, как несколько предыдущих
  страниц уже были успешно получены.** Поскольку `syncAllAnimals` накапливает
  все страницы в память (`AnimalsDto`, включая `animalWeigings`) и вставляет их
  в БД одним `db.transaction` только **после** полного завершения
  `paginatedRequestHandler`, ни одна строка новой пагинации (ни животные, ни
  идентификации, ни взвешивания) не попадает в БД, если сбой произошёл на
  любой из страниц — результат идентичен сбою на первой странице. Таблицы
  `Animals`/`AnimalIdentifications` при этом уже полностью пусты (шаг 4
  основного потока выполнился раньше и закоммитился независимо), а
  `AnimalWeighings` содержит только те строки, что были `sync == false` на
  момент шага 4.
- **Сбой конкретно на записи взвешивания внутри `weight_history`** (см. шаг 6
  основного потока) — сбой возникает при парсинге ответа, а не при передаче по
  сети; сервер уже успешно ответил на страницу, где-то внутри неё оказалась
  некорректная запись `weight_history` одного животного. Результат
  неотличим от сетевого сбоя той же страницы — тот же `RESULT`
  (`READ_ERROR`), не отдельный use-case.
- **Сбой внутри `db.transaction` (после успешной пагинации).** Реже сетевого
  сбоя, но структурно возможен (нарушение ограничения при батч-вставке).
  Транзакция откатывается целиком — состояние, вставленное этим шагом,
  единообразно пусто (не частично, как у Vaccination); однако предшествующий
  шаг 4 (два `clear()` + `clearSync()`) уже закоммичен вне этой транзакции и
  откатом не затрагивается — итоговое состояние таблиц то же, что и при сбое
  пагинации.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  сущность, идентифицирующая событие ([EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md)).
  Локально её таблица частично очищается на шаге 4 (`clearSync()` — только
  строки `sync == true`) и в этом сценарии **не восстанавливается**: ни новыми
  строками с сервера (пагинация/парсинг не завершились успешно), ни прежним
  содержимым (для `sync == true` строк нет механизма отката отдельно от
  `clearSync()` — они удалены безусловно и не читались заранее в память, в
  отличие от `Vaccination.vaccinationsWithErrors`). Строки с `sync == false`
  (ещё не отправленные локально) `clearSync()` не трогает и они сохраняются в
  БД в любом случае, независимо от исхода этого шага.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — таблица
  полностью очищается шагом 4 (`_animalsRepository.clear()`, безусловно, ДО
  начала попытки пуллинга), включая ещё не синхронизированные локальные
  записи (`id < 0`). При сбое пуллинга (шаги 6/7) эти строки не
  восстанавливаются: `syncAllAnimals` содержит код для восстановления
  локальных животных (`getAllLocalUnsynced()` → `localsToRestore`), но этот
  код читает состояние таблицы уже ПОСЛЕ того, как `loadAnimals` вызвал
  `_animalsRepository.clear()` — то есть `getAllLocalUnsynced()` внутри
  `syncAllAnimals`, вызванного из `loadAnimals`, всегда получает пустой
  список ещё до всякого сбоя пуллинга. Единственный другой вызывающий
  `syncAllAnimals` в кодовой базе — `updateAnimals` — сам нигде не вызывается
  ни из одного места `lib/` (мёртвый код), так что для этой сущности
  восстановление локальных животных на практике недостижимо ни в одном
  реальном пути выполнения, не только в сценарии ошибки.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — таблица полностью очищается тем же шагом 4
  (`_animalIdentificationsRepository.clear()`, безусловно) и, симметрично
  Animal, не восстанавливается при сбое пуллинга.

### Бизнес-правила

- **Один сбой сети/парсинга валит одновременно три сущности.** `loadAnimals` —
  единственный код, читающий одним HTTP-запросом (`GET .../animals`) три
  разных набора данных (`animals`, `identifications`, `animalWeigings`), и
  единственный `try/catch` в `_fetchAnimalsPage` не различает, какая часть
  ответа была причиной сбоя (сетевой уровень) или где именно в ответе
  оказалась некорректная запись (уровень парсинга) — `READ_ERROR` этого файла
  идентичен по коду вне зависимости от того, что фактически не удалось:
  сама сеть, JSON животного, JSON идентификации или JSON `weight_history`.
- **`clear()`/`clearSync()` вызываются безусловно, до попытки пуллинга, а не
  после успешного его завершения** — как и у Vaccination
  ([UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)). В отличие от
  Vaccination, здесь очистка асимметрична по трём таблицам: `Animals`/
  `AnimalIdentifications` — полное безусловное удаление; `AnimalWeighings` —
  условное по `sync`, оставляет неотправленные строки нетронутыми.
- **Восстановление вставки (шаг 7 основного потока) внутри одного
  `db.transaction` устраняет для этой тройки таблиц тот вид частичной
  порчи БД, что описан для Vaccination** ([UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md),
  «Бизнес-правила») — если исключение произойдёт именно внутри
  `db.transaction`, откат атомарен для `Animals`+`AnimalIdentifications`+
  `AnimalWeighings` одновременно. Это не устраняет потерю данных,
  зафиксированную шагом 4 (`clear()`/`clearSync()`) ДО начала транзакции —
  та фиксация уже необратима к моменту, когда транзакция могла бы откатиться.
- **Экран ошибки маркируется под ключом `animals` — здесь корректно, в отличие
  от аналогичного места у Vaccination.** `loadAnimals` эмитит собственный
  `_emitProgress(dataKey: DataKey.animals, dataCategory: DataCategory.animals)`
  непосредственно перед четырьмя действиями основного потока — поэтому, в
  отличие от [UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)
  (где ключ `animals` на экране ошибки Vaccination — унаследованный
  случайный артефакт предыдущего шага), здесь этот же ключ действительно
  соответствует упавшему шагу — он просто не различает, что конкретно из
  animals/identifications/weighings стало причиной.
- **Отказ этого шага рвёт остаток `_syncAllData` и `_syncAuthData` целиком.**
  `_vaccinationsRepository.syncVaccinations(true)` — единственный вызов после
  `loadAnimals` в теле `_syncAllData` — в этом проходе не выполняется вовсе;
  `updateAndSyncSHTP`/`_suncDevices()`, идущие в `_syncAuthData` после
  `updateAndSyncRegagro`, тоже не выполняются.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (включая путь ошибки) полностью реализован существующим
кодом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода; ловит проброшенное исключение, вызывает `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro`; при исключении из него не доходит до `updateAndSyncSHTP`/`_suncDevices` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе; при исключении из `_syncAllData` не выполняет ничего после вызова |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `loadAnimals` после `syncMovements`/`syncDisposals`/`_syncEditedAnimals`, до `syncVaccinations(true)` — при исключении из `loadAnimals` `syncVaccinations` в этом проходе не вызывается |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | ядро этого сценария: собственный `_emitProgress(dataKey: DataKey.animals, ...)`, затем `clear()`×2 + `clearSync()` + `syncAllAnimals()`; `try/catch (_) { rethrow; }` пробрасывает исключение без изменений |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет `DataUpdates`-запись об ошибке и эмитит `DataUpdateFailure`, используя `_currentDataCategory`/`_currentDataKey`, установленные `loadAnimals` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.clear` (унаследован из `BaseRepository`) | CURRENT | безусловное удаление всех строк `Animals`, включая `id < 0` |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository.clear` (унаследован из `BaseRepository`) | CURRENT | безусловное удаление всех строк `AnimalIdentifications` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.clearSync` | CURRENT | удаление только строк `AnimalWeighings` с `sync == true` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncAllAnimals` | CURRENT | ядро этого сценария: постраничный `GET`, накопление в память, `getAllLocalUnsynced()` (всегда пусто в этом вызывающем контексте), один `db.transaction` с батч-вставкой трёх таблиц + условное восстановление локальных животных |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository._fetchAnimalsPage` | CURRENT | один HTTP-вызов страницы + `AnimalsDto.fromJson`; оборачивает оба шага одним `try/catch (e, stackTrace) { log(...); rethrow; }` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllLocalUnsynced` | CURRENT | `dao.getAllLocalUnsynced()`, фильтр `id < 0` — всегда пуст на момент вызова из `syncAllAnimals`, т.к. `loadAnimals` уже вызвал `clear()` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateAnimals` (метод `DataUpdateBloc.updateAnimals`, не репозитория) | CURRENT | альтернативный вызывающий `syncAllAnimals(fromDate: ...)` — нигде не вызывается в `lib/`, мёртвый код, здесь упомянут только для полноты анализа `getAllLocalUnsynced` |
| `lib/repositories/base_repository.dart` | `BaseRepository.paginatedRequestHandler`, `BaseRepository.clear` | CURRENT | `paginatedRequestHandler` — без собственного `try/catch`, пробрасывает исключение `onRequest`/`onResponse` как есть; `clear()` = `dao.clear()` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` | CURRENT | безусловное `delete` всех строк без фильтра — используется `Animals`/`AnimalIdentifications` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.clearSync` | CURRENT | `delete` строк только с `sync == true` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllLocalUnsynced` | CURRENT | `select(animals)..where(id < 0)` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `AnimalsDto.fromJson`, `AnimalsDto._animalFromApiJson` | CURRENT | парсинг ответа сервера на животных/идентификации/`weight_history`; источник возможного исключения парсинга (не только сетевого) |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighingDto.fromJson`, `AnimalWeighingDtoExtension.toAnimalWeighing` | CURRENT | сгенерированный парсинг одной записи `weight_history` — конкретный weighing-специфичный источник исключения внутри `AnimalsDto.fromJson` |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.animals`, `DataCategory.animals`, `DataUpdates.isError` | CURRENT | ключ, под которым ошибка этого шага маркируется в журнале/на экране (см. «Бизнес-правила») |
| `lib/pages/data_update/data_update_page.dart` | `_Body.build` (ветка `DataUpdateFailure`), `DataUpdateInProgressWidget` | CURRENT | UI общего экрана ошибки синхронизации: `tr(errorTitleKey)` + `tr(errorMessageKey)`, кнопки «Попробовать снова» / «На главную» |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/animals` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и после
  завершения предшествующих шагов `_syncAllData` (`syncMovements`,
  `syncDisposals`, `_syncEditedAnimals`), `loadAnimals` безусловно очищает
  `Animals` и `AnimalIdentifications` целиком (включая ещё не
  синхронизированные локальные животные, `id < 0`) и `AnimalWeighings` —
  только строки с `sync == true` — **до** попытки запросить
  `GET .../animals`.
- Если запрос `GET .../animals` (на любой странице), либо парсинг любой части
  ответа (животное, идентификация, запись `weight_history`), либо батч-вставка
  внутри `db.transaction` бросают исключение, оно пробрасывается наружу из
  `_fetchAnimalsPage`/`syncAllAnimals`/`loadAnimals` без дополнительной
  обработки — строка `_addDataUpdateSuccess(_currentDataCategory)` не
  выполняется.
- Локальные животные (`id < 0`), их идентификации и ранее синхронизированные
  взвешивания (`sync == true`) не восстанавливаются в этом сценарии: код
  восстановления локальных животных внутри `syncAllAnimals`
  (`getAllLocalUnsynced`/`localsToRestore`) видит уже пустую таблицу
  независимо от исхода пуллинга, т.к. `loadAnimals` очистил её раньше.
- Исключение продолжает всплывать через `_syncAllData` → `updateAndSyncRegagro`
  → `_syncAuthData` — `_vaccinationsRepository.syncVaccinations(true)`
  (следующий шаг `_syncAllData` после `loadAnimals`) и `updateAndSyncSHTP`/
  `_suncDevices()` (идущие в `_syncAuthData` после `updateAndSyncRegagro`) в
  этом проходе не выполняются.
- Весь sync-проход завершается `DataUpdateFailure` (не `DataUpdateSuccess`), и
  `errorMessageKey` этого состояния равен `DataKey.animals` — на этот раз
  корректно указывающему на реально упавший шаг, а не на артефакт более
  раннего шага.
- Пользователь видит общий экран ошибки синхронизации с кнопками «Попробовать
  снова» (перезапускает `_syncAllData` полностью заново, не с шага
  `loadAnimals`) и «На главную».

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` содержит только два
теста (`'DataUpdateBloc конструируется с полным набором зависимостей из
getIt'` и `blocTest` на `DataUpdateClear`) — ни `DataUpdateStartAll`, ни
`loadAnimals`, ни `AnimalWeighingsRepository.clearSync` там не фигурируют;
`MockAnimalWeighingsRepository` зарегистрирован в `getIt` только как
DI-заглушка для конструирования `DataUpdateBloc`, без вызова его методов ни в
одном сценарии. `test/repositories/animals_repository_test.dart` покрывает
`syncAllAnimals` лишь косвенно через отдельные группы (`updateAnimalPlaceId`,
`deleteAnimalsWithDetailsByIds`, `updateAnimal`, farm/place sync) — ни одна
группа не называется по этому use-case и не вызывает `syncAllAnimals`
напрямую с моком, бросающим исключение на `ApiMethod.get`. Отдельного файла
`animal_weighings_repository_test.dart` в `test/repositories/` не существует
вовсе — `AnimalWeighingsRepository` не покрыт репозиторными тестами ни в
одном сценарии, только `AnimalWeighingsCubit`
(`test/pages/animal_weighings_cubit_test.dart`, уровень выше, не про
sync-pull).

## Открытые вопросы и ограничения

- **Потеря ещё не синхронизированных локальных животных при сбое этого шага —
  самое серьёзное расхождение с намерением кода.** `syncAllAnimals` содержит
  рабочую логику восстановления локальных (`id < 0`) животных
  (`getAllLocalUnsynced`/`localsToRestore`), но она не может сработать при
  вызове из `loadAnimals`: к моменту её выполнения таблица `Animals` уже
  безусловно пуста (`_animalsRepository.clear()` шага 4 основного потока).
  Единственный другой вызывающий `syncAllAnimals` — `DataUpdateBloc.updateAnimals`
  — сам нигде не вызывается в `lib/`, то есть эта защитная логика на практике
  не работает ни в одном реальном пути выполнения приложения, не только при
  сбое сети. Не проверялось, было ли это осознанным решением (например, если
  ожидается, что локальные животные всегда успевают синхронизироваться
  раньше, шагом `syncAllUnsentAnimals()`, до `loadAnimals`) или регрессией.
- **Пользователь не получает точного диагноза.** Экран ошибки показывает
  общий ключ `animals` — в отличие от Vaccination
  ([UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)) он здесь
  действительно относится к упавшему шагу, но всё ещё не различает, что
  именно из трёх сущностей (животные/идентификации/взвешивания) стало
  причиной, и не предупреждает пользователя, что часть локальных данных уже
  удалена (`clear()`/`clearSync()`) на момент показа этого экрана.
- **Асимметрия очистки между `Animals`/`AnimalIdentifications` (безусловная,
  полная) и `AnimalWeighings` (условная, только `sync == true`)** — не
  проверялось, является ли это осознанным решением (взвешивания считаются
  менее критичными для полной перезаписи) или просто следствием того, что
  `clearSync()` был написан отдельно от общего `BaseDao.clear()`.
- **Повторный запуск («Попробовать снова») перезапускает весь sync-проход
  заново, не только шаг `loadAnimals`** — `_syncAllData` при повторной
  попытке выполняется от `_clearDataUpdates()` и далее по всей цепочке
  (`loadUser`, `syncAllUnsentAnimals`, `syncMovements`, `syncDisposals`,
  `_syncEditedAnimals`, и только затем снова `loadAnimals`) — не проверялось
  (и не предмет этого файла — принадлежит SYSTEM, см.
  [MOD-4](../modules/MOD-4-ANIMAL.md), «Граница»), насколько это осознанное
  проектное решение против точечного retry только упавшего шага.
- **Частота реального возникновения weighing-специфичного триггера** (сбой
  парсинга одной записи `weight_history`, а не сетевой сбой) — код
  однозначно допускает такой путь (шаг 6 основного потока), но не
  проверялось, насколько часто сервер реально присылает некорректную запись
  `weight_history` в проде, отдельно от общей частоты сетевых сбоев этого
  шага.
