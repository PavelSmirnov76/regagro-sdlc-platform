# UC-73 — Sync-проход успешно отправляет одну ещё не отправленную вакцинацию на сервер (create push)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода система ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md))
доходит до третьего push-шага вакцинации — отправки ещё не отправленных новых
записей ([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), `createdAt !=
null`, `sync == false`). В отличие от delete- и update-шагов, отправляемых
единым батчем, здесь `VaccinationsRepository._sendVaccinationsToApi` делает
цикл: один отдельный `POST .../vaccination-group-actions` на **каждую**
запись, результат независим по каждой строке. Документирует
happy-path — одна запись, запрос успешен: строка удаляется из локальной БД
(`deleteById`), т.к. теперь она есть на сервере и вернётся обратно через
последующий pull с новым локальным `id` и заполненным `shtpId`. Happy-path
события [EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md)
(`vaccination.creation_push_synced`) — событие завершает то, что локально
начал [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md)
(`vaccination.recorded`), инициированный
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md),
авторизованный пользователь — весь этот шаг гейтится `_authRepository.isAuthorized()`
в `DataUpdateBloc._syncAuthData`) один раз (`DataUpdateStartAll`), но в каждом
отдельном сетевом вызове этого сценария человек не участвует. Сама запись
вакцинации, отправляемая в этом сценарии, была создана раньше — гостем или
авторизованным пользователем одинаково ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md))
— этот факт не влияет на то, отправится ли она сейчас: единственное условие
отбора — попадание в `getNotSyncVaccinationsWithDetails()` (см. ниже).

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
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` →
   `updateAndSyncRegagro(event, emit)` (дальше в этом же методе идут
   `updateAndSyncSHTP` и синхронизация устройств — вне рамок этого use-case).
4. `updateAndSyncRegagro` решает — та же развилка, что уже документирована в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md)/[UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md) —
   по количеству уже накопленных записей `DataUpdate`, наличию ошибок в них и
   флагам события (`event.again`/`event.fullUpdate`), с повторной проверкой
   сети — нужно ли запускать `DataUpdateBloc._syncAllData` в этом проходе.
   Если сеть недоступна на этой проверке или условия не выполняются, сценарий
   до вакцинации не доходит (другая ветка).
5. `_syncAllData`: `_clearDataUpdates()` → `loadUser` →
   `_emitProgress(dataKey: DataKey.syncUnsentAnimals)` →
   `syncAllUnsentAnimals()` (sync создания животных — вне рамок этого
   use-case; к этому моменту локальный `id` любого успешно созданного нового
   животного уже заменён серверным и каскадно перенесён на связанные
   `Vaccination.animalId`, см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md))
   → `_emitProgress(dataKey: DataKey.syncSettings)` → если `event is
   DataUpdateStartAll && event.isUpdateData` — `_settingsRepository.setSettingToSHTP()`
   → безусловно `_settingsRepository.getSettingFromSHTP()` →
   `_movementReportRepository.syncMovements()` → `_disposalRepository.syncDisposals()`
   → `_syncEditedAnimals()` → `loadAnimals(event, emit)` → **`await
   _vaccinationsRepository.syncVaccinations(true)`** — с этого вызова
   начинается собственно этот сценарий. Ни до, ни после этого вызова
   `_syncAllData` не эмитит собственный `_emitProgress` именно для
   вакцинации.
6. `VaccinationsRepository.syncVaccinations(true)` (`isFullSync: true`,
   `isDeleteErrors` не передан → по умолчанию `false`): фиксированный
   порядок `_deleteVaccinationFromApi()` → `_updateVaccinationFromApi()` →
   **`_sendVaccinationsToApi()`** — наш шаг.
7. `_sendVaccinationsToApi()`:
   1. `vaccinations = await getNotSyncVaccinationsWithDetails()` →
      `VaccinationsDao.getNotSyncVaccinationsWithDetails` — `SELECT` с
      `LEFT JOIN` на `vaccines`/`units`/`injectionMethods`/`injectionPlaces`/`vaccinationTypes`,
      `WHERE sync = false AND deletedAt IS NULL AND updatedAt IS NULL`
      (без явного условия на `createdAt` — по инварианту
      [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) «ровно один из
      трёх флагов установлен одновременно» это условие эквивалентно
      `createdAt IS NOT NULL`, но реализовано через исключение двух других
      флагов, а не прямой проверкой самого `createdAt`). Каждая строка
      дополнительно читает `animalsDao.getAnimalWithDetailsById`,
      `_getDiseasesByLink` (→ `_getDiseasesByVaccinationId`, join через
      `DiseasesVaccinations`) и вычисляет `shtpId: vaccination.shtpId ?? -1`
      (колонка `shtpId` в таблице `Vaccinations` — `int?`,
      `VaccinationWithDetails.shtpId` — уже не-nullable `int`, по умолчанию
      `-1`, если в БД было `NULL`).
   2. Если список пуст — метод возвращается сразу, ни один сетевой вызов не
      выполняется (вырожденный случай, не этот сценарий).
   3. `rpcClientSHTP = getIt.get<ApiClient>(instanceName: 'farm_rpc')` →
      `CustomDioClient` (регистрация в `injection_container.dart`).
   4. `for (var vaccination in vaccinations)` — **цикл, один отдельный HTTP-вызов
      на каждую запись**, в отличие от delete/update-шагов того же
      `syncVaccinations` (батч на весь набор разом).
   5. На каждой итерации строится `ApiMessage(link:
      '${Constants.registrationServiceApi}/vaccination-group-actions',
      method: ApiMethod.post, headers: {'Accept-Language':
      LanguageService.locale}, data: {'vaccinations':
      [VaccinationApiRequest.fromVaccinationWithDetails(vaccination).toJson()]})`
      — тот же URL, что у delete (`DELETE`) и update (`PUT`) шагов, различие
      только в HTTP-методе; тело — массив из одного элемента под ключом
      `vaccinations`.
      - `VaccinationApiRequest.fromVaccinationWithDetails`: `id:
        vaccination.shtpId >= 0 ? vaccination.shtpId : null` — для
        по-настоящему новой записи `shtpId` уже `-1` (см. шаг 7.1), значит
        `id: null`, а `@JsonSerializable(includeIfNull: false)` полностью
        убирает ключ `id` из итогового JSON (сервер получает запрос без
        `id` — это и есть маркер «создать», в отличие от update-шага, где
        `id` заполнен); `animal_id: vaccination.animal.animalId` (=
        `AnimalWithDetails.animal.id`, геттер `animalId`); `dose`
        захардкожен в `1` (не берётся из `vaccination.dose`); `dose_id`/
        `measure_unit` — из `unit` (fallback `20`/`''`, если `unit == null`);
        `medicine: vaccine.name`; `vaccination_date`/`revaccination_date` —
        `DateFormat('yyyy-MM-dd HH:mm:ss')` от значения, переведённого в
        UTC; `disease_ids`/`diseases_ids` — оба ключа заполняются одним и
        тем же списком id болезней; `injection_type_id` — `injectionMethod?.id
        ?? 0`.
   6. `response = await rpcClientSHTP.call(message)` → `CustomDioClient.call`:
      добавляет заголовки `Authorization`/`Accept-Language`, выполняет
      `Dio`-запрос; нормализация формы ответа — если тело `Map`, содержащее
      ключ `data` (успешный ответ на создание обычно его содержит),
      `status` форсируется в `"1"` и тело возвращается как есть.
   7. `if (response['errors'] != null || response['status'] == 'error')` —
      в этом (`CREATE_OK`) сценарии условие ложно (нормализованное тело
      содержит `status: "1"`, ключа `errors` нет) → **иначе: `await
      deleteById(vaccination.id)`** → `VaccinationsRepository.deleteById` →
      `VaccinationsDao.deleteById` (`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`) —
      обычный Drift `DELETE FROM vaccinations WHERE id = :id`, сопоставление
      по **локальному** автоинкрементному `id` (не по `shtpId`); строка
      целиком исчезает из локальной таблицы.
   8. Цикл переходит к следующей записи (если есть) независимо — исход этой
      записи не влияет на уже обработанные до неё.
8. После завершения `for` `_sendVaccinationsToApi` возвращает управление
   нормально: внешний `try/catch` этого метода оборачивает весь цикл целиком
   и существует для перехвата исключения **вне** per-item `try` (например,
   из самого `getNotSyncVaccinationsWithDetails()`) — исключения по каждой
   отдельной сетевой попытке ловятся внутренним `try/on DioException catch`
   и наружу этого метода не выходят.
9. Управление возвращается в `syncVaccinations`: сразу следом
   `vaccinationsWithErrors = await _getNotSyncVaccinations()` →
   `VaccinationsDao.getNotSyncVaccinations` — простой `SELECT * FROM
   vaccinations WHERE sync = false`, без прочих условий. Строка, только что
   удалённая на шаге 7.7, к этому моменту физически отсутствует в таблице —
   в `vaccinationsWithErrors` она не попадает. Далее `await dao.clear()`
   (полностью очищает таблицу `vaccinations`) → `await
   _getVaccinationsFromApi()` — пагинированный `GET
   ${registrationServiceApi}/vaccinations`, каждая полученная запись
   вставляется через `insert(vaccination.toCompanion())`
   (`VaccinationDto.toCompanion`: `shtpId` = серверный `id`, `sync: true`,
   новый локальный автоинкрементный `id`) — это отдельное событие
   ([EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
   вне рамок этого use-case), но именно этим путём успешно отправленная в
   этом сценарии запись «возвращается» локально — как новая строка, а не
   как обновление удалённой. Наконец, `if (!isDeleteErrors)
   dao.insAll(vaccinationsWithErrors)` — так как `isDeleteErrors == false`
   на этом call site, `vaccinationsWithErrors` (не включающий нашу строку)
   переставляется обратно без `await` перед самим вызовом `insAll`.

### Альтернативные потоки

- `getNotSyncVaccinationsWithDetails()` пуст (нет ещё не отправленных новых
  записей) → `_sendVaccinationsToApi` возвращается сразу, ни один сетевой
  вызов не выполняется — вырожденный случай, не этот сценарий.
- Несколько записей в очереди одновременно: цикл `for` обрабатывает их
  последовательно, каждую со своим независимым `try/on DioException catch`
  — успех/отказ одной записи не влияет на обработку следующих (partial
  success на уровне пачки — предмет отдельного ERROR use-case для той же
  строки события; здесь документируется только успех для отдельно взятой
  записи).
- Строка, ранее уже получившая отказ на create-push в прошлом полном
  sync-проходе (поле `errors` заполнено текстом прошлой ошибки, `sync`
  осталось `false`): `getNotSyncVaccinationsWithDetails()` не фильтрует по
  `errors`, поэтому такая строка автоматически попадает в очередь следующего
  прохода и обрабатывается тем же кодом — если на этот раз запрос успешен,
  путь идентичен основному потоку (поле `errors` при этом не сбрасывается
  явно, т.к. строка целиком удаляется `deleteById`, а не обновляется).

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сегмент `ENT` имени файла и единственная сущность, чьё состояние
  фактически меняется этим шагом: строка целиком удаляется из локальной
  таблицы `vaccinations` при успехе.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается (не
  пишется) этим шагом: `animal_id` в теле запроса берётся из
  `VaccinationWithDetails.animal.animalId`, подтягиваемого join'ом при
  формировании выборки; сама запись `Animal` этим шагом не изменяется.
- [ENT-6](../entities/ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md) (Disease,
  HANDBOOKS) — читается через связочную таблицу `DiseasesVaccinations`
  (`VaccinationsDao._getDiseasesByLink`/`_getDiseasesByVaccinationId`) для
  заполнения `disease_ids`/`diseases_ids` тела запроса.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается для `dose_id`/`measure_unit` тела запроса (fallback
  `20`/`''`, если у записи не указан `unitId`).
- Справочники `Vaccine`, `InjectionMethod`, `InjectionPlace`,
  `VaccinationType` (VAC-локальные, без собственного `ENT` — см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) — читаются тем же
  join'ом для `medicine`/`injection_type_id`/полей запроса; ни один не
  изменяется этим шагом.

### Бизнес-правила

- Push отправляет каждое из трёх состояний `Vaccination` (delete/update/create)
  отдельным HTTP-запросом на общий эндпоинт `vaccination-group-actions`, в
  фиксированном порядке delete → update → create; delete и update — одним
  батчем на все подходящие строки разом, create — по одной записи за раз, с
  независимым результатом на каждую (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
- Успех per-item запроса определяется отсутствием ключа `errors` и
  `status != 'error'` в ответе, уже нормализованном `CustomDioClient.call`
  (форсирующим `status: "1"`, если тело содержит ключ `data`).
- Успех приводит к безусловному `deleteById` этой строки — не к простановке
  `sync = true` на месте (в отличие от delete/update-шагов, которые
  работают с уже существующими на сервере записями и обновляют/удаляют их
  локально по-другому). Запись «возвращается» локально только на
  последующем pull-шаге ([EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md)),
  как новая строка с новым локальным `id`.
- Отсутствие ключа `id` в JSON тела запроса (через `includeIfNull: false`
  при `shtpId == -1`) — единственный сигнал серверу «это создание», не
  отдельный флаг в самом запросе.
- Необработанное исключение выше per-item `try/catch` (например при самом
  чтении `getNotSyncVaccinationsWithDetails()`) пробрасывается наружу
  (`rethrow` во внешнем `catch` метода) и прерывает весь `syncVaccinations` —
  не относится к этому (`CREATE_OK`) сценарию, где предполагается, что чтение
  выборки прошло успешно.
- `dao.insAll(vaccinationsWithErrors)` в конце `syncVaccinations` вызывается
  без `await` — на этот (уже удалённый) ряд это не влияет, т.к. он не
  входит в `vaccinationsWithErrors`, но является общей особенностью
  окружающего метода.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и прослежен от `DataUpdateStartAll`
до `deleteById`. Тестового покрытия на уровне
`VaccinationsRepository._sendVaccinationsToApi` (ни успех, ни ошибка per-item
create-push) нет вовсе (см. «Связанные тесты») — это факт отсутствия теста,
а не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксированная последовательность sync-шагов для авторизованного пользователя, вызывает `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, нужно ли запускать `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_vaccinationsRepository.syncVaccinations(true)` последним шагом, после movements/disposal/edited animals/loadAnimals |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | фиксированный порядок delete → update → create, затем capture/clear/pull/reinsert |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._sendVaccinationsToApi` | CURRENT | цикл по одной записи, `POST` на каждую, per-item try/catch, `deleteById` при успехе |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getNotSyncVaccinationsWithDetails`, `deleteById`, `_getNotSyncVaccinations` | CURRENT | обёртки над DAO-методами, используемыми этим шагом |
| `lib/repositories/vaccination/vaccination_api_request.dart` | `VaccinationApiRequest.fromVaccinationWithDetails` | CURRENT | сборка тела запроса; `id: null` при `shtpId == -1` — маркер создания |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | `SELECT ... WHERE sync=false AND deletedAt IS NULL AND updatedAt IS NULL`, join на справочники, `shtpId ?? -1` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.deleteById` | CURRENT | точечный Drift `DELETE` по локальному `id` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | `SELECT * FROM vaccinations WHERE sync=false`, используется для `vaccinationsWithErrors` после push-шагов |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao._getDiseasesByLink`, `_getDiseasesByVaccinationId` | CURRENT | join через `DiseasesVaccinations` для списка болезней записи |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `VaccinationWithDetails.shtpId` | CURRENT | не-nullable `int`, дефолт `-1` при `NULL` в БД — основа маркера «создание» |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.animalId` | CURRENT | геттер `animal.id`, источник `animal_id` тела запроса |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.ins` | CURRENT | `dao.clear()`/`dao.insAll(vaccinationsWithErrors)` (без `await`)/вставка pull-строк в `syncVaccinations`/`_getVaccinationsFromApi` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальный `Dio`-запрос; нормализация формы ответа, форсирующая `status: "1"` при наличии ключа `data` |
| `lib/injection_container.dart` | регистрация `getIt` для `instanceName: 'farm_rpc'` | CURRENT | связывает `'farm_rpc'` `ApiClient` с `CustomDioClient` |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL сервиса `registration` для эндпоинта `/vaccination-group-actions` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDto.toCompanion` | CURRENT | сборка локальной строки при последующем pull (`sync: true`, новый `shtpId`) — иллюстрирует, как запись «возвращается» после этого шага |

## Критерии приёмки

- При полном sync-проходе (`syncVaccinations(true)`), для каждой строки
  `Vaccination` с `createdAt != null`/`sync == false` (без `updatedAt`/
  `deletedAt`), выполняется ровно один `POST
  {registrationServiceApi}/vaccination-group-actions` с телом
  `{"vaccinations": [<эта одна запись>]}`, JSON которой не содержит ключа
  `id`.
- Если ответ на этот запрос не содержит ключа `errors` и `status !=
  'error'` (после нормализации `CustomDioClient.call`), соответствующая
  строка удаляется из локальной таблицы `vaccinations` (`deleteById`) —
  `getNotSyncVaccinationsWithDetails()`/`getAll()` после этого шага её
  больше не возвращают.
- Обработка per-item — отказ или успех одной записи в цикле не мешает
  остальным записям очереди быть отправленными в том же вызове
  `_sendVaccinationsToApi`.
- `_sendVaccinationsToApi` не пробрасывает исключение наружу за per-item
  сетевую ошибку — только за ошибку, возникшую вне цикла (например, при
  самом чтении выборки).
- Удалённая на этом шаге строка не попадает в `vaccinationsWithErrors`
  (`_getNotSyncVaccinations()`, выполняемый сразу после push-шагов) и,
  соответственно, не переставляется обратно после `dao.clear()`.

## Связанные тесты

**TBD — теста нет.** Подтверждено чтением `test/repositories/vaccinations_repository_test.dart`
целиком и поиском (`grep -n "ApiMethod.post|_sendVaccinationsToApi|getNotSyncVaccinationsWithDetails|deleteById"`)
— ни одного совпадения внутри тела `test()`/`group()` этого файла. В файле
есть только `group('UC-72 — VaccinationsRepository.syncVaccinations(isFullSync: true) — edit push', ...)`
(PUT-шаг, `_updateVaccinationFromApi`) и `group('UC-70 — VaccinationsRepository.syncVaccinations(isFullSync: true) — delete push', ...)`
(DELETE-шаг, `_deleteVaccinationFromApi`) — оба покрывают только сценарий
«запрос падает, исключение не пробрасывается наружу», ни один не вызывает и
не мокает `ApiMethod.post`/create-шаг ни на успех, ни на ошибку. Поиск по
всему `test/` (`grep -rl "vaccination-group-actions|_sendVaccinationsToApi|syncVaccinations"`)
не даёт других файлов — `test/blocs/data_update_bloc_test.dart` мокает
`VaccinationsRepository` целиком (`MockVaccinationsRepository`), но не
содержит ни одного вызова `syncVaccinations` в теле теста. Create-push путь
(`_sendVaccinationsToApi`) на сегодня не покрыт тестами ни для `CREATE_OK`,
ни для `CREATE_ERROR`.

## Открытые вопросы и ограничения

- **`getNotSyncVaccinationsWithDetails()` выделяет «ещё не отправленные
  новые» записи не прямой проверкой `createdAt IS NOT NULL`, а исключением
  двух других флагов** (`deletedAt IS NULL AND updatedAt IS NULL` при
  `sync = false`). Корректность этого запроса целиком опирается на
  инвариант «ровно один из трёх флагов установлен одновременно»
  ([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) — если бы
  когда-нибудь появилась строка с `sync = false` и всеми тремя флагами
  `null` (например, при ручной миграции данных или баге где-то выше по
  цепочке), она попала бы в этот create-push, хотя формально не является
  «новой ещё не отправленной записью» в смысле `createdAt != null`. На
  сегодня оба известных пути, способных создать такое рассогласование
  (`markVaccinationForDeletion`, недостижимая ветка `UnsentVaccinationEditBloc._onSave`),
  сами недостижимы из UI (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) —
  риск теоретический, не наблюдаемый в текущем коде.
- **Строка, чей create-push отказал в прошлом полном sync-проходе (`errors`
  заполнено), автоматически повторно отправляется в следующем** —
  `getNotSyncVaccinationsWithDetails()` не исключает строки с непустым
  `errors`. Это ожидаемое поведение retry, но оно не проверено ни одним
  тестом (см. «Связанные тесты») и не задокументировано отдельным
  use-case на сегодня.
- **`animal_id` в теле запроса берётся из текущего значения
  `Vaccination.animalId` без проверки, что оно уже заменено серверным.**
  По порядку вызовов в `_syncAllData` (шаг 5 «Основной поток») `Vaccination`-create-push
  идёт позже `syncAllUnsentAnimals()`, так что к этому моменту животное
  этой же пачки обычно уже синхронизировано и его `id` заменён — но если
  create-push самого животного в этом же проходе отказал (другой
  use-case), запись вакцинации всё равно попадёт в этот цикл с прежним
  (возможно, локальным отрицательным) `animalId`, и что сделает сервер с
  таким значением — не проверено ни чтением серверного контракта, ни
  тестом. Зафиксировано как риск, не разобрано в рамках этого,
  предполагающего успех, документа.
- **`dao.insAll(vaccinationsWithErrors)` в конце `syncVaccinations` вызван
  без `await`.** На успешно удалённую в этом сценарии строку это не
  влияет (она не входит в `vaccinationsWithErrors`), но это общая
  особенность метода, окружающего этот шаг, стоящая отдельного
  рассмотрения при будущей правке `syncVaccinations`.
