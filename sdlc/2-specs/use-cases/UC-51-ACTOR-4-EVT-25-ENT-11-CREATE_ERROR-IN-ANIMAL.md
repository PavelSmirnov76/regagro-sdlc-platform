- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md), [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)

# UC-51 — Sync создания животного отказывает технически — необработанное сетевое исключение обрывает и это животное, и весь sync-проход (per-item try/catch отсутствует, в отличие от соседнего метода того же файла)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md) — `DataUpdateBloc._syncAllLocalAnimals` отправляет на сервер локально созданных животных (`id < 0`) с заполненным `farmId`, по одному, в цикле, через `AnimalsRepository.syncLocalAnimal` → `_syncLocalAnimalFarm`. Здесь сам сетевой вызов (`POST {registrationServiceApi}/animals/storeAnimal`) заканчивается технически — сетевое исключение либо ответ сервера с не-2xx статусом, который Dio по умолчанию тоже превращает в исключение. В отличие от бизнес-отказа сервера (см. «Альтернативные потоки»), этот путь вообще не имеет ни одного `try/catch` между самим сетевым вызовом и обработчиком всего sync-прохода: исключение обрывает не только это животное, а весь `_syncAllData` целиком — тот же класс дефекта, что уже задокументирован для ферм ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) и мест ([UC-38](UC-38-ACTOR-4-EVT-18-ENT-10-CREATE_ERROR-IN-FARM.md)), но без промежуточного бага сопоставления id — здесь достаточно, что сам сетевой вызов ничем не обёрнут.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во время sync-прохода. Прямого пользовательского действия в момент самого отказа нет — sync-проход к этому шагу уже был запущен ранее [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (`DataUpdateStartAll`, диспатчится, например, из `main_page.dart`, `profile_settings_view.dart`, `in_work_page.dart` или `data_update_page.dart`) — дальше проход идёт автоматически, без участия пользователя на уровне отдельного сетевого вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Само животное, которое здесь не удаётся отправить, было заведено раньше и локально [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (`AnimalRegistrationBloc`, [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)) — ACTOR-5 не участвует в самом sync-шаге, только в исходном создании синхронизируемой записи.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход — `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети и загрузки справочников, при `_authRepository.isAuthorized()`, вызывается `_syncAuthData`.
2. `_syncAuthData` вызывает `_deletePlacesFromRDS`, `_syncFarms`, `_syncPlaces`, `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`, затем `updateAndSyncRegagro(event, emit)` — этот сценарий предполагает, что все предыдущие шаги в этом проходе не упали (иначе `updateAndSyncRegagro` вообще не достигается).
3. `updateAndSyncRegagro` (по своей внутренней логике счётчиков/повторов) вызывает `_syncAllData(event, emit)`.
4. `_syncAllData` вызывает `_clearDataUpdates()` (полностью очищает журнал `DataUpdates` в начале прохода), `loadUser`, затем `_emitProgress(dataKey: DataKey.syncUnsentAnimals, dataCategory: DataCategory.syncUnsentAnimals)` — это выставляет `_currentDataKey`/`_currentDataCategory` в `'syncUnsentAnimals'` непосредственно перед шагом, где произойдёт крах, и ничего не меняет их между этим вызовом и крахом.
5. `_syncAllData` вызывает `await syncAllUnsentAnimals()` → `_syncAllLocalAnimals()`. Метод получает `localAnimals = await _animalsRepository.getAllLocalAnimalsWithDetailsByFilters()` — без фильтров, т.е. все локальные (`id < 0`) животные со всеми деталями.
6. Цикл `for (final awd in localAnimals)`: если `awd.farmId == null` — `continue`, животное вообще не пытается синхронизироваться в этом шаге (см. [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)). Для животного с заполненным `farmId` вызывается `await _animalsRepository.syncLocalAnimal(currentAwd)` — этот вызов **не обёрнут в try/catch** внутри самого цикла `_syncAllLocalAnimals` (в отличие от структурно похожего цикла `_syncEditedAnimals` в том же файле несколькими десятками строк выше, где per-animal `await _animalsRepository.updateAnimal(animal)` обёрнут в `try { ... } catch (e) { ...; await _animalsRepository.update(animal.copyWith(errors: Value(e.toString()))); }`).
7. `syncLocalAnimal` делегирует в `_syncLocalAnimalFarm`, которая собирает payload (`birth_date`, `kind_id`, `breed_id`, `suit_id`, `place_id`, `farm_id`, `gender`, `generation`, `markers` и т.д.), строит `ApiMessage` (`POST {registrationServiceApi}/animals/storeAnimal`) и вызывает `rpcClient.call(message)` через `ApiClient` (`instanceName: 'farm_rpc'`, реализация — `CustomDioClient`).
8. Для конкретного животного этот вызов заканчивается технически: либо `dio.request(...)` бросает исключение по сетевой причине (нет соединения, таймаут, обрыв на середине прохода), либо сервер отвечает не-2xx статусом (например 422/500) — `DioClient` не переопределяет `validateStatus` (`BaseOptions` без этого поля), поэтому Dio по умолчанию считает успешными только коды 200-299 и бросает `DioException` на любом другом. `CustomDioClient.call` перехватывает это исключение только для логирования (`getIt.get<Talker>().error(...)`) и безусловно перебрасывает его дальше (`rethrow`).
9. Это исключение не перехватывается: ни в `AnimalsRepository._syncLocalAnimalFarm`/`syncLocalAnimal` (обёртки без try/catch), ни в `DataUpdateBloc._syncAllLocalAnimals` (см. шаг 6), ни в `syncAllUnsentAnimals`, ни в `_syncAllData`, ни в `updateAndSyncRegagro`, ни в `_syncAuthData` — единственный `try/catch` на этом пути находится в самом обработчике `DataUpdateBloc.on<DataUpdateStartAll>`, оборачивающем весь sync-проход целиком.
10. Этот внешний `catch (error, stackTrace)` логирует ошибку через `Talker` и вызывает `DataUpdateBloc._emitError`, который (а) пишет одну строку в `DataUpdates` через `_addDataUpdateError` с `dataCategoryId: DataCategory.syncUnsentAnimals` и `errorDataKey: 'syncUnsentAnimals'` (значения из шага 4 — специфичные для этого шага, в отличие от ферм/мест, для которых `_emitProgress` со своим `dataKey` вообще не вызывается перед этим шагом) и (б) эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'syncUnsentAnimals', errorMessage: 'error: $error, stackTrace: $stackTrace')` — общая ошибка всего sync-прохода, не привязанная к конкретному животному.
11. Поскольку исключение вылетает из середины цикла `_syncAllLocalAnimals`, все шаги `_syncAllData`, запланированные после `await syncAllUnsentAnimals();` — `_settingsRepository.getSettingFromSHTP()` (после `syncSettings`), `_movementReportRepository.syncMovements()`, `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`, `loadAnimals(event, emit)`, `_vaccinationsRepository.syncVaccinations(true)` — в этом проходе не выполняются вовсе.
12. На следующем полном sync-проходе `getAllLocalAnimalsWithDetailsByFilters()` снова вернёт то же самое животное (`id < 0`, `errors` не выставлен) вместе со всеми животными, что шли за ним в списке и не были даже попытаны — цикл начинается заново с самого начала списка.

### Альтернативные потоки

- **Животные, обработанные в этом же вызове цикла до упавшего, не откатываются.** Если в `localAnimals` несколько животных и падает не первое, а, скажем, третье по порядку — первое и второе уже успели пройти весь путь синхронно (`syncLocalAnimal` → при успехе `updateAnimalId`/`deleteAnimalsWithDetailsByIds`/`insert`/`update` — локальный id уже заменён на серверный) **до** того, как выполнение дошло до третьего и бросило исключение; этот уже состоявшийся результат не откатывается тем, что случилось позже в том же цикле. Это отличает животных от ферм/мест: там крах происходит в отдельном шаге сопоставления id **после** того, как весь пакет уже отправлен по сети, здесь же крах происходит **внутри** самого сетевого вызова для одного животного, ещё до того, как следующие животные пакета вообще были бы отправлены.
- **Другой, не-технический отказ того же самого `if` — не этот сценарий.** Если сервер отвечает HTTP-успехом (2xx), но тело ответа содержит непустой `errors` (или `status` не равен `"1"`) — `CustomDioClient.call` не бросает исключение вовсе: код клиента при наличии ключа `data` в теле принудительно выставляет `response.data['status'] = "1"`, но соседний ключ `errors` при этом остаётся как есть и попадает в `UnsentAnimalResponse.errors` без изменений. Тогда в `_syncAllLocalAnimals` условие `result.isError || !result.isSuccess` истинно, и код идёт по другой, не бросающей исключение ветке: `await _animalsRepository.update(animal.copyWith(errors: Value(result.errors == null ? result.messageJson : result.errorsJson)))`, после чего цикл переходит к следующему животному **без краха всего прохода**. Это отдельный, более узкий и более «мягкий» сценарий — запрос дошёл до сервера и был осознанно отклонён (`REJECTED` по терминологии [use-cases/AGENTS.md](AGENTS.md)), не `CREATE_ERROR` — вне рамок этого файла, упомянут здесь только потому, что это тот же самый `if`, с которым этот сценарий легко перепутать.
- **Не-2xx ответ сервера и чисто сетевой сбой в этом коде неразличимы.** Поскольку `DioClient` не задаёт свой `validateStatus`, любой не-2xx ответ (в том числе содержательный отказ валидации от сервера, например HTTP 422) тоже бросает `DioException` внутри `CustomDioClient.call` — код не различает «запрос не дошёл» и «запрос дошёл, но сервер ответил ошибкой на уровне HTTP» после того, как оба случая попали в один и тот же `catch`. Обе ветки приводят к одному и тому же необработанному крашу этого сценария — в отличие от узкой ветки выше, которая требует именно HTTP-успеха с бизнес-ошибкой в теле.
- Если `getAllLocalAnimalsWithDetailsByFilters()` возвращает пустой список, либо все локальные животные ещё без `farmId`, — цикл не доходит до `syncLocalAnimal` вовсе, сценарий не наступает.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — животное, для которого технически не удалось создание на сервере, остаётся `id < 0`, без каких-либо изменений (`errors` не выставляется — до этого поля код не доходит, см. основной поток, шаг 8-9); все животные, шедшие за ним в порядке итерации `localAnimals`, в этом проходе не пытаются синхронизироваться вовсе.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md) (AnimalIdentification) — идентификации этого животного (и всех, что шли за ним) остаются привязанными к прежнему отрицательному `animalId`, каскадная замена (`AnimalsRepository.updateAnimalId`) для них не выполняется, потому что до неё выполнение не доходит.
- `DataUpdates` (лог sync-прохода) — получает одну строку через `_addDataUpdateError`, специфичную для шага (`dataCategoryId`/`errorDataKey` = `syncUnsentAnimals`), но не для конкретного животного; сама сущность и модель append-only лога специфицируются будущим модулем SYSTEM, не в этой спеке.

### Бизнес-правила

- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED`, независимо от того, был ли конкретный технический сбой сетевым исключением или не-2xx ответом сервера (см. «Альтернативные потоки») — этот отказ никогда не доходит до пользователя как осознанно предъявленное решение по конкретному животному: он тонет в generic `DataUpdateFailure` всего sync-прохода. Та же формулировка, что и для ферм ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) и мест ([UC-38](UC-38-ACTOR-4-EVT-18-ENT-10-CREATE_ERROR-IN-FARM.md)).
- В отличие от ферм/мест, здесь нет отдельного шага сопоставления id, который бы падал уже после успешной сетевой отправки пакета — не хватает уже самого перехвата исключения вокруг сетевого вызова, а не более позднего шага. Структурно это более простой (без промежуточного бага), но по эффекту тот же класс дефекта: единственный `try/catch` на весь sync-проход, обрыв ради одного животного.
- Никакого отдельного retry/backoff-механизма для конкретно этого животного нет — «повтор на следующем проходе» не оформлен как явная бизнес-логика, это побочный эффект того, что `getAllLocalAnimalsWithDetailsByFilters()` при каждом полном проходе просто повторно выбирает все локальные животные с заполненным `farmId`, не различая «ещё не пробовали» и «уже пробовали и упали».
- Логика повторного запуска всего прохода при наличии ошибок в `DataUpdates` (`updateAndSyncRegagro`, `errorDataUpdates.isNotEmpty` → задержка 15 секунд → повторный `_syncAllData`) оценивается только на **следующем** вызове обработчика `DataUpdateBloc`, а не внутри уже упавшего прохода — этот крах не запускает немедленный повтор сам по себе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится статическим чтением кода (`_syncAllLocalAnimals` → `AnimalsRepository.syncLocalAnimal`/`_syncLocalAnimalFarm` → `CustomDioClient.call`). Возможное исправление (обернуть per-item вызов в try/catch, как уже сделано в соседнем `_syncEditedAnimals` того же файла) в рамках этого документирующего прохода не выполняется — это чисто фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllLocalAnimals` | CURRENT | цикл по локальным животным с `farmId`; вызов `syncLocalAnimal` ничем не обёрнут |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.syncAllUnsentAnimals` | CURRENT | тонкая обёртка, вызывает `_syncAllLocalAnimals` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncEditedAnimals` | CURRENT | структурно похожий соседний цикл в том же файле, который **корректно** оборачивает per-animal сетевой вызов в try/catch — контраст, показывающий, что для `_syncAllLocalAnimals` это не техническое ограничение, а пропуск |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | порядок шагов полного прохода; `syncAllUnsentAnimals()` вызывается раньше settings/movements/disposals/`_syncEditedAnimals`/`loadAnimals`/vaccinations |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе; retry-логика по `DataUpdates` оценивается только на следующем вызове |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro` после sync ферм/мест/взвешиваний |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | выставляет `_currentDataKey`/`_currentDataCategory` в `syncUnsentAnimals` непосредственно перед крахом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет строку в `DataUpdates` (`_addDataUpdateError`) и эмитит `DataUpdateFailure`, используя `_currentDataKey`/`_currentDataCategory` момента краха |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.syncUnsentAnimals`, `DataCategory.syncUnsentAnimals` | CURRENT | ключ/категория, зафиксированные в `DataUpdates`/`DataUpdateFailure` при этом крахе |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncLocalAnimal`, `._syncLocalAnimalFarm` | CURRENT | строит payload, вызывает `rpcClient.call`; без собственного try/catch |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `packages/sheep_farm_database/lib/entities/base_response/base_response.dart` | `BaseResponse.isSuccess`, `.isError` | CURRENT | поля, обслуживающие другую, не-бросающую ветку того же `if` (`REJECTED`, вне рамок этого файла) |
| `packages/sheep_farm_database/lib/entities/animal/local_animals_groups.dart` | `UnsentAnimalResponse.fromJson` | CURRENT | в этом сценарии не достигается — исключение происходит раньше, чем ответ был бы разобран |

## Критерии приёмки

- Если для локального животного (`id < 0`, `farmId != null`) вызов `POST {registrationServiceApi}/animals/storeAnimal` заканчивается сетевым исключением либо не-2xx HTTP-ответом, `CustomDioClient.call` логирует и перебрасывает исключение дальше без изменений.
- Это исключение не перехватывается ни в `AnimalsRepository`, ни в `DataUpdateBloc._syncAllLocalAnimals`/`syncAllUnsentAnimals`/`_syncAllData`/`updateAndSyncRegagro`/`_syncAuthData` — единственная точка перехвата — внешний `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>`.
- `DataUpdates` получает ровно одну новую строку: `dataCategoryId = DataCategory.syncUnsentAnimals`, `errorDataKey = 'syncUnsentAnimals'`, `errorMessage`, содержащий текст исключения и stack trace.
- Эмитится `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'syncUnsentAnimals', errorMessage: ...)`; весь sync-проход на этом заканчивается.
- Животные, чья синхронизация в этом же вызове цикла уже успешно завершилась до краха, сохраняют уже применённую замену локального id на серверный. Животное, чей вызов упал, и все животные, шедшие за ним в порядке `localAnimals`, остаются `id < 0`, без изменения `errors`, и повторно выбираются с самого начала списка на следующем полном sync-проходе.
- Ни один из шагов `_syncAllData`, запланированных после `syncAllUnsentAnimals()` в этом же проходе (settings/movements/disposals/`_syncEditedAnimals`/`loadAnimals`/vaccinations), не выполняется.

## Связанные тесты

TBD — теста нет. Тестов на уровне `data_update_bloc.dart` для sync-сценариев животного ([EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)/[EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)) нет вообще.

Смежное покрытие — только happy-path и только на уровне репозитория, в изоляции от `DataUpdateBloc`: `test/repositories/animals_repository_test.dart`, group `'syncLocalAnimal — идёт напрямую в Farm (R3/RegAgro-бэкенд удалён)'`, test `'вызывает Farm sync, r3_rpc не используется вовсе'` — проверяет только успешный ответ (`status: 1`) через мок `farmRpcClient.call`, не проверяет ни исключение из этого вызова, ни поведение `_syncAllLocalAnimals`/`DataUpdateBloc` при отказе.

## Открытые вопросы и ограничения

- Является ли отсутствие per-item `try/catch` в `_syncAllLocalAnimals` осознанным решением или упущением — сравнение с соседним `_syncEditedAnimals` того же файла (см. «Технические зависимости»), который per-item try/catch **имеет**, говорит скорее в пользу упущения, но нигде в коде/комментариях это не зафиксировано явно.
- Не различаются в коде «запрос не дошёл до сервера» и «сервер ответил не-2xx статусом» — оба варианта дают один и тот же необработанный крах; является ли это осознанным упрощением или потерей полезной информации (например, для различения технической ошибки и содержательного отказа со стороны сервера) — не зафиксировано.
- В отличие от `Place` (см. «Открытые вопросы» в [UC-38](UC-38-ACTOR-4-EVT-18-ENT-10-CREATE_ERROR-IN-FARM.md)), у `Animal` есть поле `guid` (см. [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)) — может ли оно использоваться сервером для дедупликации повторно отправляемого на следующем проходе животного (после сетевого сбоя, когда неизвестно, успел ли предыдущий запрос реально дойти и обработаться до обрыва соединения) — вне зоны видимости этого клиентского кода и этой спеки, не проверено.
- `DataUpdateBloc` не переопределяет `Bloc.onError` для этого шага — единственный способ увидеть исходное исключение (а не только generic `DataUpdateFailure`) — это `errorMessage` внутри самого состояния (собирается в `_emitError` из `error`/`stackTrace`) либо строка в `DataUpdates`, а не что-то персонально видимое пользователю про конкретное животное.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим чтением кода (`_syncAllLocalAnimals` → `AnimalsRepository.syncLocalAnimal`/`_syncLocalAnimalFarm` → `CustomDioClient.call` → `DioClient`).
