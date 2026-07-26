# UC-74 — Sync-проход отправляет создание вакцинации по одной записи: конкретная запись отказана или бросает исключение

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет ещё не
отправленные новые записи вакцинации
([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), `createdAt != null`)
по одной, отдельным `POST .../vaccination-group-actions` на каждую запись —
в отличие от delete/update-шагов того же прохода
([UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md),
[UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md)), которые шлют
единый батч на весь набор сразу. Этот файл документирует `CREATE_ERROR` —
конкретная запись в этом цикле отказана (ответ содержит непустой `errors`
либо `status: 'error'`) или сам вызов бросает `DioException` — и per-item
`try/catch` внутри `VaccinationsRepository._sendVaccinationsToApi` перехватывает
это без прерывания обработки остальных записей цикла.

Отдельно этот файл фиксирует и проверяет чтением кода второй, значительно
более резкий отказ того же шага: необработанное исключение **вне**
per-item `try/catch` (при самом чтении списка к отправке, либо — что
подтверждено более конкретно ниже — при попытке собрать данные для
уже пойманного `DioException`) пробрасывается наружу через внешний
`catch`/`rethrow` метода `_sendVaccinationsToApi` и прерывает весь
`syncVaccinations`, а вместе с ним и остаток sync-прохода за пределами
вакцинаций.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком (авторизованным пользователем —
весь путь до этого шага гейтится `AuthRepository.isAuthorized()`) один раз
(`DataUpdateStartAll`), но в каждом отдельном сетевом вызове этого сценария
человек не участвует.

В отличие от [UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md) и
[UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md), состояние-кандидат
этого шага (`createdAt != null, sync == false`) достижимо через живой UI:
`VaccinationBloc` (`lib/pages/vaccination/vaccination_bloc.dart`, обработчик
сохранения) создаёт `VaccinationsCompanion.insert(..., sync: const
Value(false), createdAt: Value(DateTime.now()), updatedAt: const
Value.absent(), deletedAt: const Value.absent())` и вызывает
`VaccinationsRepository.saveVaccination` при обычном сохранении вакцинации с
экрана `VaccinationPage` — это основной, ежедневно используемый путь создания
записи вакцинации, не искусственная прямая вставка в БД.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка).
2. При наличии сети, после загрузки справочников — если
   `_authRepository.isAuthorized()` — вызывается `DataUpdateBloc._syncAuthData`,
   которая (после `_deletePlacesFromRDS`/ферм/мест/взвешиваний) вызывает
   `DataUpdateBloc.updateAndSyncRegagro`, которая решает — та же развилка, что
   уже описана в [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md)
   (шаг 3) — нужно ли запускать `DataUpdateBloc._syncAllData` в этом проходе.
   Если условия не выполняются или сеть на этом шаге недоступна, сценарий до
   вакцинаций не доходит (другая ветка).
3. `_syncAllData` выполняет `_clearDataUpdates()` → `loadUser` →
   `syncAllUnsentAnimals()` → синхронизацию настроек →
   `_movementReportRepository.syncMovements()` →
   `_disposalRepository.syncDisposals()` → `_syncEditedAnimals()` →
   `loadAnimals()` — все вне рамок этого use-case — и последним доменным
   вызовом: `await _vaccinationsRepository.syncVaccinations(true)`. Это
   единственная точка вызова в кодовой базе (подтверждено `grep -rn
   "syncVaccinations" lib/`), всегда с `isFullSync: true` и без
   `isDeleteErrors` (дефолт `false`).
4. `VaccinationsRepository.syncVaccinations(true)`: т.к. `isFullSync ==
   true`, вызывается `_deleteVaccinationFromApi()`, затем
   `_updateVaccinationFromApi()` (оба вне рамок этого use-case, независимо
   от собственного исхода — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)),
   затем **`_sendVaccinationsToApi()`** — шаг этого use-case.
5. `_sendVaccinationsToApi` целиком обёрнут одним внешним `try { ... } catch
   (e, st) { ...; rethrow; }`. Первая строка внутри — `vaccinations = await
   getNotSyncVaccinationsWithDetails()` →
   `VaccinationsDao.getNotSyncVaccinationsWithDetails` — `SELECT` с джойнами
   (`vaccine`, `unit`, `injectionMethod`, `injectionPlace`, `vaccinationType`),
   отфильтрованный по `sync == false && deletedAt IS NULL && updatedAt IS
   NULL` (без явного условия на `createdAt` — по инварианту «ровно одно из
   трёх nullable-полей установлено» из
   [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) это эквивалентно
   `createdAt != null`), сгруппированный по `id`. **В отличие от**
   `getEditableVaccinationsWithDetails`/`getDeletableVaccinationsWithDetails`,
   этот DAO-метод **не исключает** строку, чей `animalId` не резолвится в
   `AnimalsDao.getAnimalWithDetailsById` — для такой строки в результат
   подставляется заглушка `AnimalWithDetails(animal: Animal(id:
   vaccination.animalId, kindId: 0, gender: 0))`, и строка **участвует** в
   цикле ниже наравне с обычными.
6. Если `vaccinations.isEmpty` — метод возвращается немедленно, ни один
   сетевой вызов не происходит (вырожденный случай «нечего отправлять», не
   этот сценарий). Для непустого результата: `rpcClientSHTP =
   getIt.get<ApiClient>(instanceName: 'farm_rpc')`, затем цикл `for (var
   vaccination in vaccinations)`.
7. На каждой итерации строится **отдельный** запрос: `ApiMessage(link:
   '${Constants.registrationServiceApi}/vaccination-group-actions', method:
   ApiMethod.post, headers: {'Accept-Language': LanguageService.locale},
   data: {'vaccinations': [VaccinationApiRequest.fromVaccinationWithDetails(vaccination).toJson()]})`
   — тело содержит ровно одну запись, не весь список сразу.
8. Каждая итерация обёрнута собственным `try { ... } on DioException catch
   (e, st) { ...; }` — **per-item** обработка, отдельная от внешнего
   `try/catch` метода:
   ```dart
   try {
     final response = await rpcClientSHTP.call(message);
     if (response['errors'] != null || response['status'] == 'error') {
       await _addErrorsToVaccinations(vaccination.id, response);
     } else {
       await deleteById(vaccination.id);
     }
   } on DioException catch (e, st) {
     getIt<Talker>().info('sendVaccinationsToApi Error: $e st: $st');
     await _addErrorsToVaccinations(
       vaccination.id,
       e.response?.data as Map<String, dynamic>,
     );
   }
   ```
9. **Ветка A этого сценария — сервер ответил, но отклонил конкретную
   запись.** `response['errors'] != null || response['status'] == 'error'`
   истинно → вызывается `_addErrorsToVaccinations(vaccination.id,
   response)`, которая делает `dao.addErrorToVaccination(vaccinationId,
   jsonEncode(response['message']))` — пишет текст `response['message']`
   (сериализованный в JSON) в поле `Vaccination.errors` **именно этой**
   строки, по её локальному `id`. Ветка `else` (`deleteById`) не
   выполняется — запись **не удаляется** локально, остаётся в БД с
   `sync == false, createdAt != null`, но теперь ещё и с непустым `errors`.
10. **Ветка B этого сценария — сам вызов бросает `DioException` с
    HTTP-ответом от сервера.** `rpcClientSHTP.call(message)` бросает
    `DioException`, перехватывается `on DioException catch (e, st)`;
    вызывается тот же `_addErrorsToVaccinations(vaccination.id,
    e.response?.data as Map<String, dynamic>)`. Если `e.response != null` и
    `e.response!.data` фактически является `Map<String, dynamic>` (типичный
    случай — сервер ответил кодом ошибки, например 422/500, с JSON-телом),
    приведение типа проходит успешно и текст ошибки пишется в `errors` тем
    же путём, что в ветке A.
11. И в ветке A, и в ветке B (когда каст в шаге 10 не бросает) исключение из
    текущей итерации **не прерывает** `for`-цикл — обработка переходит к
    следующей записи `vaccinations` независимо от исхода текущей. Это
    буквальный per-item `try/catch`, о котором сказано в задаче: одна
    отказанная/бросившая запись не мешает остальным записям того же
    прохода быть отправленными.
12. После завершения цикла (все записи обработаны, ни одна не вызвала
    исключение вне per-item `try/catch`) `_sendVaccinationsToApi` завершается
    штатно. `syncVaccinations` продолжает безусловно: `vaccinationsWithErrors
    = await _getNotSyncVaccinations()` → `VaccinationsDao.getNotSyncVaccinations()`
    — безусловный `WHERE sync = false`, без разбора по
    `createdAt`/`updatedAt`/`deletedAt` — включает и записи, которым только
    что был проставлен `errors` (шаги 9-10), т.к. их `sync` этим шагом не
    менялся. Затем `await dao.clear()` удаляет **всю** таблицу
    `Vaccinations`, `await _getVaccinationsFromApi()` тянет полный `pull` с
    сервера (отказанная запись не могла попасть на сервер — в этом ответе её
    не будет), и `if (!isDeleteErrors) dao.insAll(vaccinationsWithErrors)`
    (условие всегда истинно на единственном реальном вызывающем сайте)
    вставляет снятый на предыдущем шаге снимок обратно — включая отказанную
    запись, тем же локальным `id`, с тем же `createdAt != null, sync ==
    false`, и теперь с непустым `errors`. Запись переживает проход и снова
    попадёт в `getNotSyncVaccinationsWithDetails()` (и, значит, будет
    отправлена повторно) на следующем полном sync-проходе — тот же общий
    механизм «ни одна неотправленная строка не теряется», что и у
    delete/update-шагов ([UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md),
    [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md)).

### Альтернативные потоки

- **Успех конкретной записи (не этот сценарий).** `response['errors'] ==
  null && response['status'] != 'error'` → `deleteById(vaccination.id)` —
  запись удаляется из локальной БД целиком (`RESULT = CREATE_OK`, отдельный
  файл, не описанный здесь).
- **`getNotSyncVaccinationsWithDetails()` пуст.** `_sendVaccinationsToApi`
  возвращается на шаге 6, ни один сетевой вызов не происходит — вырожденный
  случай «нечего отправлять».
- **НАХОДКА — ветка B (`DioException` без ответа сервера) фактически
  бросает НОВОЕ, необработанное исключение вместо того, чтобы записать
  ошибку.** `e.response?.data as Map<String, dynamic>` — если `e.response ==
  null` (типичный случай `DioException` без ответа сервера: таймаут
  соединения, обрыв сети, недоступный хост — `DioExceptionType.connectionTimeout`/
  `connectionError`/`sendTimeout`/`receiveTimeout` не заполняют `response`),
  то `e.response?.data` вычисляется в `null`, и `null as Map<String,
  dynamic>` (не-nullable целевой тип) бросает `TypeError` («type 'Null' is
  not a subtype of type 'Map<String, dynamic>'») **до** вызова
  `_addErrorsToVaccinations` — аргумент вычисляется раньше самого вызова,
  поэтому `_addErrorsToVaccinations` в этом случае вообще не выполняется,
  поле `errors` этой записи не пишется. Это исключение брошено **внутри**
  тела `on DioException catch` — ничто на этом же уровне его не перехватывает
  (перехват исключений, брошенных внутри собственного `catch`-блока, требует
  отдельного окружающего `try`, которого здесь нет) — оно немедленно
  всплывает к внешнему `try { ... } catch (e, st) { ...; rethrow; }`,
  оборачивающему весь метод `_sendVaccinationsToApi` (шаг 5), которое его
  логирует и **пробрасывает дальше** (`rethrow`). Именно это — самый
  конкретно воспроизводимый путь к «необработанному исключению вне
  per-item try/catch», о котором говорится в задаче: он не требует сбоя
  самого чтения `getNotSyncVaccinationsWithDetails()` — обычный сетевой
  таймаут посреди цикла его вызывает.
- **НАХОДКА — необработанное исключение вне per-item `try/catch`
  прерывает весь `syncVaccinations` и заметную часть остального
  sync-прохода.** И «ветка B без ответа» (выше), и гипотетический сбой
  самого `getNotSyncVaccinationsWithDetails()` (например, ошибка
  Drift/SQLite при чтении) дают один и тот же исход: исключение
  пробрасывается (`rethrow`) из `_sendVaccinationsToApi()`. В `syncVaccinations`
  вызов `await _sendVaccinationsToApi();` ничем не обёрнут (в отличие от
  `_updateVaccinationFromApi`/`_deleteVaccinationFromApi`, у которых
  собственный `catch` без `rethrow` — см.
  [UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md),
  [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md)) — значит
  исключение выходит из `syncVaccinations()` целиком, и **все** последующие
  безусловные шаги того же вызова (`_getNotSyncVaccinations()` снимок,
  `dao.clear()`, `_getVaccinationsFromApi()` pull, `insAll`) **не
  выполняются вовсе** — не только для create-шага, но и итоговый
  снимок/clear/pull/реинсерт-цикл, общий для всех трёх push-шагов
  прохода, целиком пропускается. Далее исключение выходит из
  `DataUpdateBloc._syncAllData` (последняя строка метода), затем из
  `updateAndSyncRegagro` (оба места вызова `_syncAllData` там ничем не
  обёрнуты), затем прерывает `_syncAuthData` на строке `await
  updateAndSyncRegagro(event, emit);` — следующие строки того же метода,
  `await updateAndSyncSHTP(event, emit);` и `await _suncDevices();`
  (синхронизация SHTP-данных и настроек устройств сканирования), **не
  выполняются в этом проходе**. В конце концов исключение перехватывается
  внешним `try { ... } catch (error, stackTrace) { ...; await
  _emitError(...); }` внутри `on<DataUpdateStartAll>`
  (`lib/blocs/data_update/data_update_bloc.dart`) — `_emitError` вызывает
  `_addDataUpdateError` (пишет запись об ошибке в таблицу `DataUpdates`,
  вне рамок [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) и эмитит
  `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey:
  _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')`
  — пользователь видит проваленный sync целиком, не только по вакцинациям.
  Локальная таблица `Vaccinations` при этом остаётся полностью нетронутой
  (ни одна строка не потеряна — снимок/`clear()`/pull для неё просто не
  успел начаться), но и никакого обновления с сервера в этом проходе она не
  получает.
- **НАХОДКА — `_addErrorsToVaccinations` не дожидается собственной записи в
  БД.** Тело метода — `dao.addErrorToVaccination(vaccinationId,
  jsonEncode(response['message'])).toString();` — вызывает `.toString()`
  на возвращённом `Future<void>`, не `await`. Сам `_addErrorsToVaccinations`
  объявлен `async`, но без единого `await` внутри — вызывающий код (`await
  _addErrorsToVaccinations(...)` в шагах 9/10) дожидается лишь синхронного
  завершения тела этого метода, не завершения самой записи `errors` в БД.
  На практике drift выполняет запросы к одному и тому же соединению по
  очереди в порядке вызова, поэтому видимого расхождения в тестах пока не
  зафиксировано — но гарантии, что `errors` уже записан к моменту
  следующей итерации цикла или снимка `_getNotSyncVaccinations()` после
  цикла, в самом коде нет.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  основная сущность: строки-кандидаты отбираются по `sync == false,
  deletedAt IS NULL, updatedAt IS NULL` (эквивалент `createdAt != null` по
  инварианту), включая строки с нерезолвящимся `animalId` (см. шаг 5); в
  этом (`CREATE_ERROR`) сценарии строка **не удаляется** и не меняет
  `sync`/`createdAt` — единственное поле, которое может быть изменено,
  это `errors` (и то не гарантированно к моменту следующего шага, см.
  «Альтернативные потоки»).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  (с возможным fallback на заглушку, см. шаг 5) для построения `animal_id`/
  `guid` тела запроса; не изменяется этим сценарием ни при успехе, ни при
  ошибке.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается для `dose_id`/`measure_unit` тела запроса
  (с fallback `?? 20`/`?? ''`, если `unit == null`); не изменяется.
- `Disease`/`DiseasesVaccinations` — читаются для `disease_ids`/
  `diseases_ids` тела запроса; без собственного `ENT`-id (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «используются
  исключительно внутри VAC»); не изменяются.
- `InjectionMethod`/`InjectionPlace` (VAC-локальные справочники) — читаются
  для `injection_type_id`/`injection_place_id` тела запроса; не изменяются.
- `Vaccine`, `VaccinationType` — читаются при построении
  `VaccinationWithDetails` (джойн в `getNotSyncVaccinationsWithDetails`),
  но `VaccinationType` фактически **не попадает** в тело запроса — см.
  «Открытые вопросы».
- `DataUpdate` (SYSTEM) — получает новую запись об ошибке через
  `DataUpdateBloc._addDataUpdateError` только в резкой альтернативной ветке
  (необработанное исключение вне per-item `try/catch`), не в обычной
  per-item ветке A/B этого сценария.

### Бизнес-правила

- Create-шаг отправляет каждую подходящую запись **отдельным** `POST`-запросом
  с результатом, независимым по каждой записи — в отличие от delete/update-шагов
  того же прохода, отправляющих единый батч на весь набор сразу.
- Отказ конкретной записи (непустой `errors`/`status: 'error'` в ответе, либо
  `DioException` с телом ответа, приводимым к `Map<String, dynamic>`)
  перехватывается per-item `try/catch` и пишется в поле `errors` **этой**
  строки через `_addErrorsToVaccinations` — не прерывает обработку остальных
  записей цикла.
- Отказанная запись **не удаляется** локально (в отличие от успешной, которая
  удаляется через `deleteById`) — она остаётся в состоянии `sync == false,
  createdAt != null`, теперь с непустым `errors`, и участвует в следующем
  полном sync-проходе снова.
- `DioException` без HTTP-ответа сервера (`e.response == null`) — типичный
  случай сетевого сбоя посреди цикла — не обрабатывается корректно per-item
  `try/catch`: приведение `null as Map<String, dynamic>` бросает новое
  исключение, которое не перехватывается на этом уровне и эскалируется до
  внешнего `catch`/`rethrow` метода — то есть именно тот класс отказов
  (обрыв сети), для которого per-item устойчивость нужнее всего, на практике
  ведёт себя как самый резкий, а не самый мягкий исход.
- Необработанное исключение вне per-item `try/catch` прерывает весь
  `syncVaccinations` (снимок/`clear`/pull/реинсерт для всех трёх состояний
  вакцинации не выполняется в этом проходе вовсе) и весь остаток
  `_syncAuthData` того же прохода (SHTP-синхронизация, синхронизация
  устройств) — заканчивается общим `DataUpdateFailure`, видимым
  пользователю, не специфичным для вакцинаций сообщением.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — обе ветки (per-item отказ и эскалирующее исключение вне per-item
`try/catch`) полностью реализованы и прослеживаются чтением кода, включая
конкретный, воспроизводимый триггер второй ветки (`DioException` без
`response`). Недостающее покрытие тестами зафиксировано в «Связанные тесты»,
не является незавершённостью кода.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода; внешний `try/catch`, в который эскалирует резкая альтернативная ветка |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData`, `updateAndSyncRegagro` | CURRENT | последовательность sync-шагов; резкая ветка прерывает `updateAndSyncSHTP`/`_suncDevices`, идущие после `updateAndSyncRegagro` в `_syncAuthData` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_vaccinationsRepository.syncVaccinations(true)` последним доменным шагом, единственная точка вызова |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `_addDataUpdateError` | CURRENT | обработка исключения, эскалировавшего до внешнего `catch` — запись `DataUpdate` с ошибкой, эмит `DataUpdateFailure` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: delete → update → create (этот use-case) → снимок `sync=false` → `clear()` → pull → реинсерт; ничем не оборачивает вызов `_sendVaccinationsToApi()` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._sendVaccinationsToApi` | CURRENT | шаг этого use-case: цикл по одной записи, внешний `try/catch` с `rethrow`, внутренний per-item `try/on DioException catch` без `rethrow` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._addErrorsToVaccinations` | CURRENT | запись текста ошибки в поле `errors` конкретной строки; вызов `dao.addErrorToVaccination(...).toString()` без `await` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getNotSyncVaccinationsWithDetails`, `deleteById`, `_getNotSyncVaccinations` | CURRENT | выборка кандидатов на create-push, удаление успешной записи, безусловный снимок перед `clear()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | SQL-фильтр `sync=false, deletedAt IS NULL, updatedAt IS NULL`; в отличие от `getEditableVaccinationsWithDetails`/`getDeletableVaccinationsWithDetails` не исключает строку с нерезолвящимся `animalId` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.addErrorToVaccination`, `deleteById`, `getNotSyncVaccinations` | CURRENT | точечный `UPDATE errors`, точечный `DELETE`, безусловный `WHERE sync = false` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll` | CURRENT | `clear()` — `DELETE` всей таблицы; `insAll()` — `insertOrReplace` батчем, сохраняет переданный `id` (в т.ч. отказанной записи) |
| `lib/repositories/vaccination/vaccination_api_request.dart` | `VaccinationApiRequest.fromVaccinationWithDetails` | CURRENT | построение тела `POST`-запроса; `dose`, `vaccinationTypeId`, `manufacturedDate`, `expirationDate` захардкожены (`1`/`null`/`null`/`null`) независимо от реальных полей записи, см. «Открытые вопросы» |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | абстрактный контракт сетевого вызова |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальная реализация; `catch (e) { ...; rethrow; }` не различает `DioException`/иные исключения при пробросе |
| `lib/pages/vaccination/vaccination_bloc.dart` | обработчик сохранения, создающий `VaccinationsCompanion.insert(..., createdAt: Value(DateTime.now()))` | CURRENT | живой источник строки-кандидата этого сценария |
| `lib/pages/vaccination/vaccination_page.dart` | `saveVaccination` | CURRENT | UI-точка входа, с которой пользователь создаёт запись, впоследствии попадающую в этот push-шаг |

## Критерии приёмки

- При полном sync-проходе, если среди строк `Vaccination` с `sync == false,
  createdAt != null` есть хотя бы одна, для каждой такой строки выполняется
  отдельный `POST {registrationServiceApi}/vaccination-group-actions` с
  телом, содержащим ровно одну запись.
- Если ответ на конкретный `POST` содержит непустой `errors` или `status:
  'error'`, либо вызов бросает `DioException` с `response.data`, приводимым
  к `Map<String, dynamic>` — поле `errors` именно этой строки получает
  текст `response['message']`/`e.response!.data['message']`, строка
  остаётся в БД (не удаляется), и обработка переходит к следующей записи
  того же цикла без прерывания.
- Если `DioException` брошен без `response` (`e.response == null`) — каст
  `null as Map<String, dynamic>` бросает `TypeError`, поле `errors` этой
  строки **не** записывается, и исключение эскалирует до внешнего
  `catch`/`rethrow` метода `_sendVaccinationsToApi`.
- Любое исключение, эскалировавшее до внешнего `catch`/`rethrow`
  `_sendVaccinationsToApi` (включая случай выше), прерывает
  `syncVaccinations` целиком — снимок/`clear()`/pull/реинсерт для всех трёх
  push-состояний вакцинации в этом проходе не выполняются — и прерывает
  остаток `_syncAuthData` (`updateAndSyncSHTP`, `_suncDevices` не
  вызываются), заканчиваясь `DataUpdateFailure` через
  `DataUpdateBloc._emitError`.
- После прохода, завершившегося per-item отказом без эскалации, строка с
  проставленным `errors` по-прежнему присутствует в
  `getNotSyncVaccinationsWithDetails()` и будет отправлена повторно на
  следующем полном sync-проходе.

## Связанные тесты

`TBD — теста нет`. В `test/repositories/vaccinations_repository_test.dart`
есть группы `'UC-72 — VaccinationsRepository.syncVaccinations(isFullSync:
true) — edit push'` (число `94` — старая нумерация, покрывает
`_updateVaccinationFromApi`, [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md))
и `'UC-70 — VaccinationsRepository.syncVaccinations(isFullSync: true) —
delete push'` (покрывает `_deleteVaccinationFromApi`,
[UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md)) — ни одна из
них не касается create-шага. Подтверждено `grep -rn "ApiMethod.post\|
_sendVaccinationsToApi\|vaccination-group-actions" test/` — три случайных
совпадения по `ApiMethod.post` находятся в `test/repositories/ad_repository_test.dart`,
`test/repositories/auth_repository_test.dart`,
`test/repositories/unsent_report_animals_repository_test.dart` и относятся к
доскам объявлений/авторизации/отчётам, не к вакцинациям. Ни один тест в
репозитории не вставляет строку `Vaccination` с `createdAt != null` и не
мокает `ApiMethod.post` на `.../vaccination-group-actions` — ни happy-path
(`CREATE_OK`), ни этот (`CREATE_ERROR`) сценарий не покрыты ни на каком
уровне (`VaccinationsRepository`, `DataUpdateBloc`).

## Открытые вопросы и ограничения

- **Самый резкий отказ этого шага (эскалация исключения) имеет конкретный,
  вероятный триггер — сетевой таймаут/обрыв связи посреди цикла, а не
  экзотический сбой чтения БД.** `e.response?.data as Map<String, dynamic>`
  внутри уже сработавшего `on DioException catch` бросает `TypeError`,
  когда сервер не успел ответить (`response == null`) — ровно тот класс
  ошибок, ради устойчивости к которому per-item `try/catch` и существует.
  Не подтверждено интеграционным тестом с реальным `Dio`-таймаутом (только
  чтением кода `_sendVaccinationsToApi` и сигнатуры `DioException.response`
  как `Response<dynamic>?`), но опирается на задокументированное поведение
  пакета `dio`, не на предположение.
- **`_addErrorsToVaccinations` не дожидается собственной записи в БД**
  (`dao.addErrorToVaccination(...).toString()` без `await`) — расхождение по
  времени между «строка обработана в цикле» и «`errors` реально записан в
  таблицу» теоретически возможно; не воспроизведено тестом (тестов на этот
  шаг нет вообще, см. «Связанные тесты»).
- **`VaccinationApiRequest.fromVaccinationWithDetails` хардкодит `dose: 1`,
  `vaccinationTypeId: null`, `manufacturedDate: null`, `expirationDate:
  null`** независимо от фактических `vaccination.dose`,
  `vaccination.vaccinationType`, `vaccination.productionDate`,
  `vaccination.expirationDate` — эти поля читаются в
  `VaccinationWithDetails` (джойн в `getNotSyncVaccinationsWithDetails`), но
  не попадают в тело `POST`-запроса этого шага. Тот же хардкод действует и
  в батч-`PUT` update-шага ([UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md)),
  т.к. используется та же фабрика — находка этого файла, не описанная там.
  Не решается в рамках документирующей задачи — предмет будущего
  TARGET-прохода.
- **Строка с нерезолвящимся `animalId` всё же уходит на сервер с
  заглушкой-животным** (`kindId: 0, gender: 0`, без `guid`) — в отличие от
  update/delete-шагов, где такая строка тихо исключается из батча. Не
  проверено, как сервер реагирует на `animal_id` без валидного `guid` —
  внешний актор, вне рамок клиентского кода.
- Нет теста на любую ветку этого файла (per-item отказ по `errors`/`status`,
  per-item `DioException` с валидным `response`, эскалация из-за
  `DioException` без `response`, эскалация из-за сбоя самого
  `getNotSyncVaccinationsWithDetails()`) — весь `CREATE_ERROR`-путь этого
  use-case, включая находку про каст `null as Map<String, dynamic>`,
  проверен только чтением кода, не тестом.
