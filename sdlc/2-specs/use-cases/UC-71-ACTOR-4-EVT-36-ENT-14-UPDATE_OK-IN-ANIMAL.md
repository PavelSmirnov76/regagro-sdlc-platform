# UC-71 — Sync-проход успешно отправляет батч правок вакцинаций

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет одним батч-запросом
все правки уже синхронизированных вакцинаций
([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), `updatedAt != null`), и
запрос завершается успехом (сервер не возвращает непустой `errors`).
Happy-path сценарий события
[EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md)
(`vaccination.edit_push_synced`).

На сегодня строка с `updatedAt != null` никогда не появляется через живой UI
(см. «Открытые вопросы и ограничения» и
[ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) — этот use-case
технически реализован и проверен репозиторным тестом, вставляющим строку
напрямую в БД, но на практике вырожден: батч почти всегда пуст, и сама
успешность запроса не наблюдаема ни одним живым пользовательским сценарием.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком (авторизованным пользователем — шаг
гейтится `AuthRepository.isAuthorized()`) один раз (`DataUpdateStartAll`), но в
каждом отдельном сетевом вызове этого сценария человек не участвует.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка, не
   часть этого use-case).
2. При наличии сети, после загрузки справочников — если
   `_authRepository.isAuthorized()` — вызывается `DataUpdateBloc._syncAuthData`,
   которая (после мест/ферм/взвешиваний) вызывает
   `DataUpdateBloc.updateAndSyncRegagro`.
3. `updateAndSyncRegagro` решает — по количеству уже накопленных записей
   `DataUpdate`, наличию ошибок в них и флагам события — нужно ли запускать
   `DataUpdateBloc._syncAllData` в этом проходе (тот же вход, что и у
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md), не
   переизлагается здесь целиком); при недоступной сети на этом шаге эмитится
   `DataUpdateFailure` и сценарий не продолжается (другая ветка).
4. `_syncAllData` вызывает `_clearDataUpdates()`, `loadUser`,
   `syncAllUnsentAnimals()`, синхронизацию настроек,
   `_movementReportRepository.syncMovements()`,
   `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`,
   `loadAnimals()` — и последним доменным шагом этого прохода —
   `_vaccinationsRepository.syncVaccinations(true)`. Единственная точка вызова
   в кодовой базе передаёт `isFullSync: true` и никогда не передаёт
   `isDeleteErrors` — значит этот аргумент всегда остаётся дефолтным `false`
   (подтверждено `grep` по `lib/`, единственный вызов — `data_update_bloc.dart`
   строка вызова `_vaccinationsRepository.syncVaccinations(true)`).
5. `VaccinationsRepository.syncVaccinations(true)` выполняет три push-шага в
   фиксированном порядке: `_deleteVaccinationFromApi()` (delete-push,
   [EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md),
   вне рамок этого use-case), затем `_updateVaccinationFromApi()` — шаг этого
   use-case, затем `_sendVaccinationsToApi()` (create-push,
   [EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md),
   вне рамок этого use-case).
6. `_updateVaccinationFromApi` вызывает
   `VaccinationsRepository.getEditableVaccinationsWithDetails()` →
   `VaccinationsDao.getEditableVaccinationsWithDetails` — выборка строк с
   `sync == false`, `updatedAt IS NOT NULL`, `deletedAt IS NULL`,
   `createdAt IS NULL`, дополнительно отфильтрованная в коде DAO условием
   `if (animalWithDetails != null)` — строка, чей `animalId` не резолвится в
   существующую локальную запись `Animal`
   (`AnimalsDao.getAnimalWithDetailsById`), из результата молча исключается и
   в этот батч не попадёт (см. «Открытые вопросы»). Если результат пуст —
   метод возвращается сразу, ни один сетевой вызов не выполняется — это
   типичный случай сегодня (см. «Открытые вопросы»).
7. Для непустого результата строится один запрос — `ApiMessage(link:
   '{registrationServiceApi}/vaccination-group-actions', method:
   ApiMethod.put, headers: {'Accept-Language': LanguageService.locale}, data:
   {'vaccinations': [...]})`, где каждая подходящая строка преобразована через
   `VaccinationApiRequest.fromVaccinationWithDetails` (поля `dose_id`/
   `measure_unit` — из `Unit`, `disease_ids`/`diseases_ids` — из списка
   `Disease` через `DiseasesVaccinations`, `injection_type_id`/
   `injection_place_id` — из `InjectionMethod`/`InjectionPlace`). Запрос
   отправляется через `getIt<ApiClient>(instanceName: 'farm_rpc').call(message)`.
8. В этом (`UPDATE_OK`) сценарии ответ сервера не содержит непустого
   `errors` — `((response['errors'] ?? {}) as Map).isNotEmpty` ложно, поэтому
   исключение не бросается и метод завершается нормально. Это единственный
   проверяемый признак успеха — ответ не разбирается построчно (в отличие от
   `_sendVaccinationsToApi`, где для каждой строки отдельно проверяются
   `errors`/`status` и вызывается либо `_addErrorsToVaccinations`, либо
   `deleteById`).
9. **Ключевой факт этого шага: `_updateVaccinationFromApi` не делает ни одной
   локальной записи в БД ни при успехе, ни при ошибке.** Ни один `dao`-вызов
   не выставляет `sync = true` и не сбрасывает `updatedAt` для отправленных
   строк — локальное состояние этих строк успешным ответом сервера никак не
   меняется на этом шаге.
10. `syncVaccinations` продолжает `_sendVaccinationsToApi()` (обрабатывает
    только строки с `createdAt != null` — не эти строки), затем читает
    `vaccinationsWithErrors = await _getNotSyncVaccinations()` →
    `VaccinationsDao.getNotSyncVaccinations()` — **безусловный** запрос
    `WHERE sync = false`, без разбора на `createdAt`/`updatedAt`/`deletedAt`.
    Так как локальный `sync` только что успешно отправленных строк всё ещё
    `false` (шаг 9), эти же строки попадают и в эту выборку.
11. `await dao.clear()` (унаследованный `BaseDao.clear()`) удаляет **все**
    строки таблицы `Vaccinations`, включая только что отправленные.
12. `await _getVaccinationsFromApi()` — полный постраничный `GET
    {registrationServiceApi}/vaccinations` с сервера; каждая строка ответа
    вставляется как **новая** локальная строка через
    `VaccinationDtoMapper.toCompanion()` (`id` не задаётся явно — колонка
    `id` объявлена `integer().autoIncrement()`, т.е. настоящий SQLite
    `AUTOINCREMENT`, монотонно растущий и не переиспользующий освобождённые
    значения; `sync: true` — задаётся явно). Среди этого пула — свежая копия
    только что обновлённой на сервере записи, с новым локальным `id` и
    `sync = true`.
13. `if (!isDeleteErrors) dao.insAll(vaccinationsWithErrors)` —
    `isDeleteErrors` на единственной точке вызова (шаг 4) всегда `false`,
    поэтому снятый до `dao.clear()` снимок (шаг 10) — включая только что
    успешно отправленную строку, всё ещё с `sync = false, updatedAt != null`
    — вставляется обратно через `BaseDao.insAll`
    (`mode: InsertMode.insertOrReplace`), сохраняя её исходный локальный `id`.
    Так как этот `id` был освобождён `dao.clear()` (шаг 11) и находится ниже
    диапазона новых `AUTOINCREMENT`-id, назначенных на шаге 12, коллизии
    первичного ключа не происходит — обе строки остаются в таблице
    одновременно (см. «Открытые вопросы»).

### Альтернативные потоки

- `getEditableVaccinationsWithDetails()` пуст (нет строк `updatedAt != null`,
  прошедших join-фильтр по `Animal`) → `_updateVaccinationFromApi`
  возвращается сразу на шаге 6, ни один сетевой вызов не происходит —
  вырожденный случай «нечего синхронизировать», не этот сценарий, но по
  фактам ниже («Открытые вопросы») это типичное состояние приложения
  сегодня, а не редкое исключение.
- Ответ содержит непустой `errors`, либо вызов `rpcClientSHTP.call` бросает
  исключение (сеть, парсинг) → перехватывается внутри `catch` без `rethrow`
  — отдельный `ERROR`-сценарий, не входит в этот `UPDATE_OK` use-case.
- Строка, чей `animalId` не резолвится в существующую локальную `Animal` —
  молча исключается из батча ещё на шаге 6 (условие `if (animalWithDetails
  != null)` в `VaccinationsDao.getEditableVaccinationsWithDetails`); такая
  строка не участвует ни в этом, ни в `ERROR`-сценарии этого шага — она
  просто никогда не попадает в тело запроса, оставаясь в «pending edit»
  локально бессрочно тем же путём, что описан в «Открытые вопросы» ниже для
  успешно отправленных строк.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  основная сущность: строки-кандидаты отбираются по `sync == false,
  updatedAt != null, deletedAt == null, createdAt == null`; после успешного
  батч-PUT сам этот шаг не меняет ни одно из этих полей — итоговое состояние
  строки определяется последующим циклом «снимок → `clear()` → пул с сервера
  → реинсерт снимка» (шаги 10-13), а не самим `_updateVaccinationFromApi`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается дважды:
  как условие включения строки в батч
  (`AnimalsDao.getAnimalWithDetailsById(vaccination.animalId) != null`) и как
  источник `animal_id`/`guid` тела запроса
  (`VaccinationApiRequest.fromVaccinationWithDetails`). Не изменяется этим
  сценарием.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается только для полей `dose_id`/`measure_unit` тела
  запроса, не изменяется.
- `Disease`/`DiseasesVaccinations` — читаются для полей `disease_ids`/
  `diseases_ids` тела запроса (список болезней, покрываемых этой записью
  вакцинации); не имеют собственного `ENT`-id (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «используются
  исключительно внутри VAC»), не изменяются этим сценарием.
- `InjectionMethod`/`InjectionPlace` (VAC-локальные справочники, без
  собственного `ENT`-id) — читаются для `injection_type_id`/
  `injection_place_id` тела запроса, не изменяются.

### Бизнес-правила

- Три push-шага (delete → update → create) выполняются в этом фиксированном
  порядке при каждом полном sync-проходе, независимо друг от друга по
  результату — успех/ошибка одного шага не влияет на то, выполнятся ли
  остальные.
- Правки уже синхронизированных строк отправляются **одним** батч-запросом
  на весь подходящий набор сразу — не по одной в цикле, в отличие от
  create-шага (`_sendVaccinationsToApi`, который шлёт по одной записи с
  независимым результатом на каждую).
- Единственный проверяемый признак успеха батча — отсутствие непустого
  `errors` в теле ответа целиком; ответ не содержит и не разбирается
  построчно — нет способа отличить «сервер принял часть строк батча» от
  «принял все» на основе этого кода.
- Локальные флаги строки (`sync`, `updatedAt`) не пишутся этим шагом ни при
  успехе, ни при ошибке — единственный канал, которым локальное состояние
  вообще может измениться после push, это последующий безусловный цикл
  «снимок несинхронизированных строк → `clear()` всей таблицы → полный
  `pull` с сервера → реинсерт снимка», общий для всех трёх push-шагов
  `syncVaccinations` (см. шаги 10-13 и «Открытые вопросы»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде, включая happy-path. Недостижимость
через живой UI (см. «Открытые вопросы и ограничения») — факт о продукте
сегодня (единственный способ создать строку-кандидат недостижим из живых
экранов), а не незавершённость реализации самого push-шага.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData`, `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | последовательность sync-шагов для авторизованного пользователя, решение о запуске `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_vaccinationsRepository.syncVaccinations(true)` последним доменным шагом прохода, единственная точка вызова, `isDeleteErrors` не передаётся (дефолт `false`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: delete-push → update-push (этот use-case) → create-push → снимок несинхронизированных строк → `clear()` → pull → реинсерт снимка |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._updateVaccinationFromApi` | CURRENT | шаг этого use-case: `PUT .../vaccination-group-actions` одним батчем, `catch` без `rethrow`, никакой локальной записи при успехе |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getEditableVaccinationsWithDetails`, `VaccinationsRepository._getNotSyncVaccinations` | CURRENT | выборка кандидатов на push (условная, по трём nullable-флагам) и безусловная выборка `sync == false` для снимка перед `clear()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getEditableVaccinationsWithDetails` | CURRENT | SQL-фильтр `sync=false, updatedAt IS NOT NULL, deletedAt IS NULL, createdAt IS NULL` + join-условие `animalWithDetails != null` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | безусловный `WHERE sync = false`, без разбора по `createdAt`/`updatedAt`/`deletedAt` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll` | CURRENT | `clear()` — `DELETE` всей таблицы; `insAll()` — `insertOrReplace` батчем, сохраняет переданный `id` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations.id` | CURRENT | `integer().autoIncrement()` — настоящий SQLite `AUTOINCREMENT`, id не переиспользуются после `clear()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDtoMapper.toCompanion` | CURRENT | маппинг ответа `GET .../vaccinations` в `VaccinationsCompanion`; `id` не задаётся явно (новый `AUTOINCREMENT`-id при вставке), `sync: true` — явно |
| `lib/repositories/vaccination/vaccination_api_request.dart` | `VaccinationApiRequest.fromVaccinationWithDetails` | CURRENT | построение тела PUT-запроса из `VaccinationWithDetails` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | выполнение сетевого запроса (`farm_rpc`-инстанс) |

## Критерии приёмки

- При полном sync-проходе (`DataUpdateStartAll`), при наличии сети и
  авторизованном пользователе, если существует хотя бы одна строка
  `Vaccination` с `sync == false, updatedAt != null, deletedAt == null,
  createdAt == null`, чей `animalId` резолвится в существующую локальную
  `Animal`, — выполняется ровно один `PUT
  {registrationServiceApi}/vaccination-group-actions` с телом `{'vaccinations':
  [...]}`, содержащим все такие строки.
- Если ответ на этот запрос не содержит непустого `errors`, исключение не
  пробрасывается, и sync pass продолжается до конца (create-push, затем
  снимок/clear/pull/реинсерт, затем следующие шаги `_syncAllData`).
- После такого прохода строка, участвовавшая в успешном батче, **остаётся** в
  локальной БД с теми же `sync == false, updatedAt != null` (тем же локальным
  `id`), рядом с отдельной новой строкой (другой локальный `id`, `sync ==
  true`), пришедшей тем же проходом из полного `pull` и отражающей
  применённую на сервере правку.
- `VaccinationsRepository.getEditableVaccinationsWithDetails()` /
  `watchCountEditableVaccinations()` после такого «успешного» прохода
  по-прежнему возвращает/учитывает эту строку — то есть тот же батч будет
  отправлен на сервер повторно на следующем sync-проходе, несмотря на то что
  предыдущая попытка уже завершилась успехом.

## Связанные тесты

`TBD — теста нет.` В `test/repositories/vaccinations_repository_test.dart`
есть группа `'UC-72 — VaccinationsRepository.syncVaccinations(isFullSync:
true) — edit push'` (число `94` в имени — старая нумерация, группа будет
переименована отдельным проходом, не трогается здесь), но оба входящих в неё
теста мокают `farmRpcClient.call` так, что вызов с `method == ApiMethod.put`
**бросает исключение** — то есть проверяют `ERROR`-ветку того же шага
(`_updateVaccinationFromApi`'s `catch` без `rethrow`), не `UPDATE_OK`.
Ни один тест в файле не мокает `PUT` успешным ответом (`{'errors': null}`/
`{'errors': {}}`) для строки с `updatedAt != null` — сценарий этого файла
(успешный ответ сервера на батч правок) не покрыт ни одним тестом на любом
уровне (`VaccinationsRepository`, `DataUpdateBloc`) — подтверждено `grep` по
`syncVaccinations`/`_updateVaccinationFromApi`/`getEditableVaccinationsWithDetails`
по `test/`, единственное совпадение — этот же файл и эта же группа.

## Открытые вопросы и ограничения

- **Сценарий недостижим через живой UI.** Строка-кандидат для этого шага
  (`updatedAt != null, createdAt == null`) может появиться только через
  `VaccinationsRepository.updateVaccination`/DAO-уровневую правку уже
  синхронизированной записи, но, как зафиксировано в
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), единственный живой
  вход в `UnsentVaccinationEditBloc` (`UnsentVaccinationPage`, список из
  `getNotSyncVaccinationsWithDetails`) по построению этой выборки всегда даёт
  строки с `createdAt != null` — ветка `_onSave`, ставящая `updatedAt` для
  уже синхронизированной записи, недостижима с любого известного экрана.
  Следствие: `getEditableVaccinationsWithDetails()` возвращает пустой список
  практически всегда, `_updateVaccinationFromApi` в реальной эксплуатации
  почти всегда завершается на шаге раннего `return` (см. «Альтернативные
  потоки»), ни разу не доходя до сетевого вызова — а значит, и сам
  `UPDATE_OK`-ответ сервера, предмет этого файла, на сегодня не наблюдается
  ни в одном живом сценарии приложения. Единственный способ воспроизвести
  этот use-case — вставить строку с `updatedAt != null` напрямую в БД, как
  делает репозиторный тест.
- **Успешный push не помечает строку синхронизированной — вместо этого
  создаёт дубликат и запускает бесконечную повторную отправку.** Это
  находка этого файла, не зафиксированная в
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (там тот же снимок/
  clear/pull/реинсерт-цикл описан как гарантия «ни одна неотправленная
  строка не теряется», без учёта, что на **успехе** это же поведение создаёт
  побочный эффект). Механизм (шаги 9-13 выше, подтверждён чтением
  `_updateVaccinationFromApi`, `syncVaccinations`, `VaccinationsDao.clear`/
  `insAll`, схемы `Vaccinations.id` и `VaccinationDtoMapper.toCompanion`):
  `_updateVaccinationFromApi` не пишет `sync`/`updatedAt` даже при успехе →
  строка снова попадает в безусловный `_getNotSyncVaccinations()` снимок →
  `dao.clear()` удаляет всю таблицу → полный `pull` создаёт для той же
  вакцинации свежую строку с новым `AUTOINCREMENT`-id и `sync = true` →
  снимок реинсертится тем же (старым, освобождённым) `id`, снова с `sync =
  false, updatedAt != null`. Итог — после «успешного» прохода в таблице две
  строки одной и той же серверной вакцинации: одна помечена
  синхронизированной, вторая — по-прежнему «в правке» и будет отправлена
  повторно на следующем проходе, и на всех последующих, без ограничения
  числа попыток, даже если сервер каждый раз отвечает успехом. Не
  подтверждено интеграционным тестом с реальным SQLite (только чтением кода
  и объявления схемы `integer().autoIncrement()` — истинный SQLite
  `AUTOINCREMENT`, гарантирующий отсутствие переиспользования id после
  `DELETE`), но опирается на задокументированное поведение drift/SQLite, не
  на предположение.
- Строка, чей `animalId` не резолвится в локальную `Animal`
  (`getAnimalWithDetailsById == null`), молча исключается из
  `getEditableVaccinationsWithDetails()` — не попадает ни в `UPDATE_OK`, ни в
  `ERROR` сценарий этого шага, и тем же циклом снимок/clear/pull/реинсерт
  сохраняется в вечном «pending edit» состоянии — тот же класс проблемы, что
  и выше, но без единого сетевого вызова.
- Ответ разбирается только на уровне «есть ли непустой `errors` во всём
  теле» — партиальный отказ (сервер принял часть строк батча, отклонил
  другую) в этом коде неотличим от полного успеха или полного отказа; нет
  наблюдаемого способа узнать, какая именно строка батча была отклонена.
- Нет теста, мокающего успешный ответ `PUT
  {registrationServiceApi}/vaccination-group-actions` для строки с
  `updatedAt != null` (см. «Связанные тесты») — весь `UPDATE_OK`-путь этого
  use-case, включая находку про дубликат строки выше, проверен только
  чтением кода, не тестом.
