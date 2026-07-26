# UC-89 — Sync-проход успешно отправляет батчем ещё не отправленные взвешивания на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер одним
батч-запросом ВСЕ ещё не отправленные взвешивания
([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), `sync == false`)
— включая и по-настоящему новые записи, и локальные правки уже
синхронизированных записей (`remoteId != null`), поскольку сущность не
различает эти два случая на уровне push-протокола (см.
[ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)). Запрос завершается
успехом для всей пачки разом: `response['status'] == "1"` удаляет отправленные
строки локально без явной пометки `sync: true`. RESULT — `CREATE_OK`: эндпоинт
`/weighing-event` всегда семантически «создание» на сервере, независимо от
того, была ли строка на самом деле новой или локальной правкой ранее
отправленной записи — сама сущность и её push-протокол не различают эти два
случая, RESULT здесь описывает то, что реально происходит на проводе, не
намерение пользователя. Happy-path сценарий события
[EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)
(`animal_weighings.push_synced`) — событие завершает то, что локально начали
[EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)
(`animal_weighing.recorded`) или
[EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md)
(`animal_weighing.edited`), оба инициированные
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), авторизованный пользователь —
весь этот шаг гейтится `_authRepository.isAuthorized()` в
`DataUpdateBloc._syncAuthData`) один раз (`DataUpdateStartAll`), но в каждом
отдельном сетевом вызове этого сценария человек не участвует. Сами записи
взвешивания, отправляемые в этом сценарии, были созданы или отредактированы
раньше — гостем или авторизованным пользователем одинаково
([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)) — этот факт не влияет на то,
отправится ли запись сейчас: единственное условие отбора —
`sync == false`.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик сначала проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка, не
   часть этого use-case).
2. При наличии сети, после загрузки справочников и досок объявлений — если
   `_authRepository.isAuthorized()` — вызывается `DataUpdateBloc._syncAuthData`.
3. `_syncAuthData` выполняет фиксированную последовательность:
   `_deletePlacesFromRDS()` → `_syncFarms()` → `_syncPlaces()` →
   **`_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`** — наш шаг,
   вызывается без аргументов (единственный call site в `lib/`, подтверждено
   `grep -rn "storeAnimalWeighingsToSHTP"` — значит `animalId` всегда `null`
   в реально исполняемом коде) → `updateAndSyncRegagro(event, emit)` →
   `updateAndSyncSHTP(event, emit)` → синхронизация устройств. Уточнение
   порядка: этот push выполняется ПОСЛЕ того, как `_syncFarms()`/
   `_syncPlaces()` уже отработали внутри `_syncAuthData`, а не до них — см.
   «Открытые вопросы» ниже. Тем не менее это первый ANIMAL-доменный
   push-шаг всего прохода: он выполняется раньше `syncAllUnsentAnimals()`,
   `_movementReportRepository.syncMovements()`,
   `_disposalRepository.syncDisposals()`, `loadAnimals` (полный reload
   животных) и `_vaccinationsRepository.syncVaccinations(true)` — все они
   находятся глубже, внутри `_syncAllData`, достижимого только через
   `updateAndSyncRegagro`.
4. `storeAnimalWeighingsToSHTP({animalId: null})`:
   1. `animalWeighings = (await getAllNotSuncAnimalWeighings()).where((e) =>
      animalId == null || e.animalId == animalId)` — так как `animalId ==
      null` на единственном реальном call site, фильтр по `where` не
      сужает выборку. `getAllNotSuncAnimalWeighings()` →
      `AnimalWeighingsDao.getAllNotSuncAnimalWeighings()`: `SELECT * FROM
      animal_weighings WHERE sync = false` — без дополнительного условия на
      `remoteId`, в отличие от трёх-флагового разделения Vaccination
      ([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)) — ничто не
      отличает «никогда не отправлявшуюся» строку от «отправленной, но
      локально отредактированной».
   2. Если список пуст — метод возвращается сразу, ни один сетевой вызов не
      выполняется (вырожденный случай, не этот сценарий).
   3. `weighings` собирается циклом по каждой строке:
      `{"animal_id": e.animalId, "guid": await
      _animalsRepository.getAnimalGuidById(e.animalId),
      "measurement_unit_id": e.unitId, "weight": e.weight.toString(),
      "weighing_date": DateFormat('yyyy-MM-dd HH:mm:ss').format(e.weighingDate)}`
      — ключей `id`/`remoteId` в теле нет вовсе, ни для одной строки; именно
      это делает запрос неотличимым от «создания» даже для строк, чей
      `remoteId != null` (локальная правка уже синхронизированной записи).
      `AnimalsRepository.getAnimalGuidById` →
      `AnimalsDao.getAnimalGuidById(id)` — `getSingle()` по таблице
      `Animals`, бросает исключение, если подходящей строки нет (edge case,
      вне этого happy path — см. «Открытые вопросы»).
   4. `ApiMessage(link: '${Constants.farmServiceApi}/weighing-event',
      method: ApiMethod.post, data: {'weighings': weighings})` — один
      `POST` с телом-массивом всех неотправленных записей сразу, не цикл из
      отдельных запросов (в отличие от Vaccination create-push, см.
      [UC-73](UC-73-ACTOR-4-EVT-37-ENT-14-CREATE_OK-IN-ANIMAL.md)).
   5. `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc')` →
      `CustomDioClient.call(message)` — добавляет заголовки
      `Authorization`/`Accept-Language`, выполняет запрос через `Dio`.
      `CustomDioClient.call` нормализует форму ответа: если тело — `Map`,
      содержащий ключ `data` или `animal_exits`, `status` форсируется в
      `"1"` и тело возвращается как есть; иначе, если тело — `Map` с
      `status == 'error'`, возвращается как есть; иначе возвращается
      `{"data": response.data, "status": "1"}`.
   6. `response = await rpcClient.call(message)` — в этом (`CREATE_OK`)
      сценарии `response['status'] == "1"` (либо от самого сервера, либо
      форсировано нормализацией `CustomDioClient.call` из предыдущего
      пункта).
   7. `if (response['status'] == "1" || response['status'] == 1)`: так как
      `animalId == null` на единственном реально достижимом call site,
      выполняется ветка `else`: `await dao.clear()` →
      `BaseDao.clear()` → `(delete(_currentTableInfo)).go()` — удаляет ВСЕ
      строки таблицы `AnimalWeighings` без какого-либо `WHERE`, не только
      те, что были только что отправлены. Это стирает и строки с `sync ==
      true`, уже присутствовавшие локально с предыдущего pull'а (см.
      «Открытые вопросы»). (Ветка `if (animalId != null)` →
      `dao.deleteAllByAnimalId(animalId)` недостижима при текущем
      единственном call site — см. «Бизнес-правила».)
   8. Весь сетевой вызов и обработка ответа (шаги 4.4–4.7) обёрнуты в
      `try/catch` (`getIt<Talker>().handle(e, stackTrace)` при исключении)
      — но этот `try` НЕ покрывает построение `weighings` (шаг 4.3):
      исключение из `getAnimalGuidById`/`getSingle()` вышло бы из
      `storeAnimalWeighingsToSHTP` необработанным этим методом и всплыло бы
      выше — в `_syncAuthData`, а дальше во внешний `try/catch`
      `on<DataUpdateStartAll>` (`DataUpdateFailure`). Edge case, не этот
      успешный сценарий.
5. Управление возвращается в `_syncAuthData`: следом выполняется
   `updateAndSyncRegagro(event, emit)` — та же развилка, что уже
   документирована в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md)/[UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md):
   по количеству уже накопленных записей `DataUpdate`, наличию ошибок в них
   и флагам события (`event.again`/`event.fullUpdate`), с повторной
   проверкой сети — решает, нужно ли запускать `_syncAllData` в этом
   проходе (вне рамок этого use-case). Если `_syncAllData` запускается, он
   доходит до `loadAnimals(event, emit)`, где
   `_animalWeighingsRepository.clearSync()` (удаляет строки `sync == true`
   — обычно уже пусто, т.к. `dao.clear()` шага 4.7 уже очистил таблицу
   целиком) вызывается непосредственно перед
   `_animalsRepository.syncAllAnimals()`, которая заново вставляет, по
   каждому животному, полный набор взвешиваний, вложенный в серверный ответ
   ([EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
   вне рамок этого use-case) — именно этим путём данные «возвращаются»
   локально после того, как этот шаг их стёр. Между успехом этого шага
   (4.7) и этим последующим `loadAnimals` — окно, в котором ЛЮБЫЕ локальные
   данные о взвешиваниях (не только по животным из отправленной пачки)
   отсутствуют в таблице `AnimalWeighings`.

### Альтернативные потоки

- `getAllNotSuncAnimalWeighings()` пуст (нет неотправленных взвешиваний) →
  `storeAnimalWeighingsToSHTP` возвращается сразу, сетевой вызов не
  выполняется — вырожденный случай, не этот сценарий.
- `response['status']` не `"1"`/`1` → ни `dao.clear()`, ни
  `dao.deleteAllByAnimalId` не вызываются вовсе — строки остаются локально
  с `sync == false`, без частичной очистки; явной ветки ошибки/`rethrow`
  нет — молчаливый no-op при отказе. Отдельный `ERROR`-сценарий для того же
  события, не входит в этот use-case.
- Исключение при самом сетевом вызове (например `DioException`) — поймано
  собственным `try/catch` этого метода, обработано через
  `getIt<Talker>().handle`, дальше не пробрасывается — sync-проход
  продолжается на `updateAndSyncRegagro`, не прерывая весь `_syncAuthData`;
  в отличие от push перемещений
  ([UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)), который
  при отказе делает `rethrow` и прерывает остаток `_syncAllData`. Разное
  поведение при отказе у двух push-шагов одного и того же прохода —
  отдельный `ERROR`-сценарий, не разбирается здесь подробно.
- Исключение при построении `weighings` (шаг 4.3, например
  `getAnimalGuidById`/`getSingle()` не находит строку `Animal`) НЕ поймано
  собственным `try` этого метода — пробрасывается наружу. Зафиксировано как
  риск, не этот успешный сценарий.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing)
  — сегмент `ENT` имени файла и сущность, чьё состояние фактически меняется
  этим шагом: при успехе вся локальная таблица целиком очищается (не только
  отправленная пачка — см. «Основной поток» и «Открытые вопросы»).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается (не
  пишется) этим шагом: `animal_id` и `guid` (через
  `AnimalsRepository.getAnimalGuidById`) берутся из уже существующих
  локальных записей `Animal`; сама запись `Animal` этим шагом не
  изменяется.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — `unitId` читается напрямую как поле строки `AnimalWeighing`
  (`measurement_unit_id` тела запроса), сам справочник `Unit` отдельно не
  подгружается join'ом (в отличие от Vaccination-варианта).

### Бизнес-правила

- Push — единый батч-запрос на все ещё не отправленные записи разом (всех
  животных сразу, т.к. `animalId` всегда `null` на единственном реальном
  call site), не цикл из отдельных запросов на каждую запись (в отличие от
  Vaccination create-push,
  [UC-73](UC-73-ACTOR-4-EVT-37-ENT-14-CREATE_OK-IN-ANIMAL.md)).
- Тело запроса не содержит `id`/`remoteId` ни для одной строки — сервер не
  может отличить создание новой записи от повторной отправки локально
  отредактированной уже синхронизированной (`remoteId != null`, `sync ==
  false`) — вероятный дубликат weighing-события на сервере в этом сценарии,
  если среди отправленных строк была правка (см.
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) «Push не
  различает создание и правку на уровне протокола»). Раздельные
  `singleSendAnimalWeighingToAPI` (`POST`, без `id`) /
  `singleEditAnimalWeighingToAPI` (`PUT .../weighing-update`, с `id`)
  реализованы в репозитории, но ни один не вызывается ни в одном call site
  в `lib/` (мёртвый код) — `storeAnimalWeighingsToSHTP` остаётся
  единственным реально используемым push-путём.
- Успех применяется ко всей пачке одновременно, без per-item детализации —
  весь ответ либо считается успехом (`status == "1"`/`1`), либо нет.
- Успех приводит к `dao.clear()` (ветка `animalId == null`, единственная
  достижимая) — полной очистке ВСЕЙ таблицы `AnimalWeighings`, а не только
  строк отправленной пачки; данные возвращаются позже отдельным шагом
  полного animal-reload (`loadAnimals` → `syncAllAnimals`,
  [EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md)).
- Параметр `animalId` метода и ветка `dao.deleteAllByAnimalId` — недостижимый
  код при текущем единственном call site (`data_update_bloc.dart`, без
  аргументов).
- Sync-проход не эмитит отдельный progress-шаг именно для взвешиваний —
  вызов идёт между `_syncPlaces()` и `updateAndSyncRegagro()` без
  собственного `_emitProgress`, аналогично перемещениям
  ([UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде, прослежен от
`DataUpdateStartAll` до `dao.clear()`. Тестового покрытия на уровне
`AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`/`DataUpdateBloc` нет
(см. «Связанные тесты») — это факт отсутствия теста, а не незавершённость
сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксированная последовательность: `_deletePlacesFromRDS` → `_syncFarms` → `_syncPlaces` → `storeAnimalWeighingsToSHTP` → `updateAndSyncRegagro` → `updateAndSyncSHTP` → устройства |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro`, `._syncAllData`, `.loadAnimals` | CURRENT | решает, нужен ли дальнейший полный проход в этом же вызове; `loadAnimals` — точка, где взвешивания возвращаются локально позже (`clearSync` + `syncAllAnimals`) |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` | CURRENT | сам push-шаг: выборка неотправленных, сборка тела, `POST`, обработка ответа |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` | CURRENT | тонкая обёртка над DAO-методом |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` | CURRENT | `SELECT ... WHERE sync = false` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` | CURRENT | `delete(_currentTableInfo)` без `WHERE` — полная очистка таблицы при успехе |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.deleteAllByAnimalId` | CURRENT (недостижимо) | ветка для `animalId != null`, не достигается при единственном реальном call site |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalGuidById` | CURRENT | источник `guid` для каждой строки тела запроса |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalGuidById` | CURRENT | `getSingle()` по таблице `Animals` — может бросить исключение вне `try/catch` этого шага |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальный `Dio`-запрос; нормализация формы ответа, форсирующая `status: "1"` при наличии ключа `data`/`animal_exits` |
| `lib/injection_container.dart` | регистрация `getIt` для `instanceName: 'farm_rpc'` | CURRENT | связывает `'farm_rpc'` `ApiClient` с `CustomDioClient` |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый URL сервиса `farm` для эндпоинта `/weighing-event` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.singleSendAnimalWeighingToAPI`, `singleEditAnimalWeighingToAPI` | CURRENT (мёртвый код) | раздельные create/update методы с явным `id`/`remoteId`, существуют, но не вызываются нигде в `lib/` |

## Критерии приёмки

- При полном sync-проходе (`DataUpdateStartAll`), при наличии сети и
  авторизованном пользователе, для непустого набора строк `AnimalWeighing` с
  `sync == false` выполняется ровно один `POST {farmServiceApi}/weighing-event`
  с телом `{"weighings": [...]}`, содержащим все эти строки, ни у одной из
  которых нет ключа `id`/`remoteId`.
- Если ответ на этот запрос содержит `status == "1"` (строкой) или `1`, вся
  таблица `AnimalWeighings` локально становится пустой (`dao.clear()`) —
  включая строки, не входившие в отправленную пачку.
- `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings()` сразу после
  успешного прохода этого шага возвращает пустой список (таблица пуста
  целиком).
- Ни одна строка не получает `sync: true` как прямой эффект этого шага — вся
  таблица просто исчезает и возвращается позже отдельным шагом (`loadAnimals`
  → `syncAllAnimals`).

## Связанные тесты

`TBD — теста нет`. Проверено: (1) `grep -rn "storeAnimalWeighingsToSHTP|weighing-event" test/`
— совпадения ограничены регистрацией `MockAnimalWeighingsRepository` в
`getIt` в нескольких тестовых файлах (`test/blocs/data_update_bloc_test.dart`,
`test/repositories/animals_repository_test.dart`,
`test/integration/registration_to_disposal_test.dart`,
`test/pages/weigh_animal_cubit_test.dart`,
`test/pages/animal_card_bloc_test.dart`,
`test/pages/animal_history_cubit_test.dart`,
`test/pages/animal_weighings_cubit_test.dart`,
`test/pages/weighing_report_cubit_test.dart`,
`test/pages/place_cubit_test.dart`, `test/pages/in_work_bloc_test.dart`) — ни
в одном из них нет `when()`-стаба или `verify()` на
`storeAnimalWeighingsToSHTP`, и ни в одном нет тела `test()`/`group()`,
вызывающего этот метод. (2) `find test -iname "*weighing*"` не находит
отдельного `test/repositories/animal_weighings_repository_test.dart` —
репозиторного теста для `AnimalWeighingsRepository` в проекте нет вовсе.

## Открытые вопросы и ограничения

- **Push не различает create/update на уровне протокола** — вероятный
  дубликат записи на сервере, если среди отправленных строк была правка уже
  синхронизированного взвешивания (`remoteId != null`). См. подробнее
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) и
  «Бизнес-правила» выше; корректные раздельные методы существуют в
  репозитории, но не подключены ни в одном call site.
- **Порядок вызовов отличается от того, что можно предположить по
  формулировке [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)/[ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)**
  («ещё до синхронизации ферм/мест») — фактически, по чтению
  `DataUpdateBloc._syncAuthData`, `storeAnimalWeighingsToSHTP` вызывается
  ПОСЛЕ `_syncFarms()`/`_syncPlaces()`, не до них. Шаг остаётся первым
  ANIMAL-доменным push'ем всего прохода (раньше `syncAllUnsentAnimals`/
  movements/disposals/`loadAnimals`/vaccinations, которые лежат глубже,
  внутри `_syncAllData`, достижимого только через `updateAndSyncRegagro`) —
  но не первым шагом `_syncAuthData` целиком. Зафиксировано здесь как
  уточнение по факту чтения кода, не как правка уже написанных
  `EVT-45`/`ENT-15` (frozen-артефакты, вне периметра этого документа).
- **`dao.clear()` очищает всю таблицу `AnimalWeighings` целиком**, а не
  только успешно отправленную пачку — включая ранее синхронизированные
  (`sync == true`) строки, полученные предыдущим pull'ом. Между этим шагом
  и последующим `loadAnimals` (который заново вставляет полный набор
  взвешиваний по каждому животному с сервера) — окно, в котором ЛЮБЫЕ
  локальные данные о взвешиваниях (не только для животных из этой пачки)
  отсутствуют — шире, чем можно понять из формулировки
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) («взвешивания
  конкретного животного»).
- **Параметр `animalId` метода фактически мёртв** — единственный вызов в
  `lib/` (`data_update_bloc.dart`) не передаёт его, поэтому ветка
  `dao.deleteAllByAnimalId` никогда не выполняется в реальном приложении;
  весь этот use-case всегда идёт по ветке `dao.clear()`.
- **Сборка тела запроса (включая `await
  _animalsRepository.getAnimalGuidById(e.animalId)`, который может бросить
  исключение через `getSingle()`, если строка `Animal` отсутствует) не
  обёрнута в `try/catch` этого метода** — в отличие от собственно сетевого
  вызова несколькими строками ниже. Такое исключение прервало бы весь
  `storeAnimalWeighingsToSHTP` и всплыло бы выше по стеку — не проверено
  тестом, не разобрано подробно в рамках этого (успешного) сценария.
- Нет теста на уровне `storeAnimalWeighingsToSHTP`/`DataUpdateBloc` (см.
  «Связанные тесты») — весь сценарий проверен только чтением кода.
