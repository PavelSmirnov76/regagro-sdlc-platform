# UC-90 — Sync push взвешиваний отказывает (сетевое исключение или несостоявшийся статус ответа) — `storeAnimalWeighingsToSHTP` глотает обе ветки внутри себя, sync-проход продолжается как ни в чём не бывало

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md) —
`AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` отправляет все ещё не
отправленные взвешивания (`sync == false`) одним батч-запросом сразу. Здесь
сам сетевой вызов заканчивается неуспехом одним из двух путей: (а) `rpcClient.call`
бросает исключение, или (б) вызов возвращает обычный ответ, но
`response['status']` отличен от `"1"`/`1`, без какого-либо исключения. Оба пути
проверены отдельно чтением кода и ведут к принципиально разным (но одинаково
незаметным снаружи) последствиям:

- (а) перехватывается тем же `try/catch`, что обёртывает сетевой вызов —
  `getIt<Talker>().handle(e, stackTrace)` логирует исключение во внутренний
  Talker-лог и **не** перебрасывает его дальше;
- (б) не порождает исключения вовсе — единственный `if (response['status'] == "1" || response['status'] == 1) { ... }`
  просто не выполняется, у него **нет `else`-ветки**, метод молча
  завершается без единой строки лога.

В обоих случаях `storeAnimalWeighingsToSHTP` возвращает управление вызывающей
стороне (`DataUpdateBloc._syncAuthData`) как обычный успешный `Future<void>` —
без исключения, без сигнала об ошибке любого вида, поэтому весь sync-проход
продолжается дальше нетронутым и в итоге штатно завершается `DataUpdateSuccess`,
даже если ни одно взвешивание не было принято сервером.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во время
sync-прохода. Прямого пользовательского действия в момент самого отказа нет —
проход был запущен ранее [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)
(`DataUpdateStartAll`, диспатчится, например, из `main_page.dart` (кнопка
обновления навбара), `profile_settings_view.dart`, `in_work_page.dart` или
`data_update_page.dart`) — дальше проход идёт автоматически, без участия
пользователя на уровне отдельного сетевого вызова, как и описано в
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Сами взвешивания, которые
здесь не удаётся отправить, были записаны раньше и локально
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (`WeighAnimalCubit.saveWeighing`/
`saveEditedWeighing`, [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)/
[EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md)) — ACTOR-5 не
участвует в самом sync-шаге, только в исходном создании синхронизируемых
записей.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети и загрузки
   справочников, при `_authRepository.isAuthorized()`, вызывается
   `_syncAuthData(event, emit)`.
2. `_syncAuthData` последовательно вызывает `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()` (в этом сценарии все три завершаются без
   ошибки), затем `await _animalWeighingsRepository.storeAnimalWeighingsToSHTP()` —
   **без аргумента** `animalId` и **без собственного** `try/catch` на месте
   вызова: весь расчёт на то, что метод сам обработает свои ошибки.
3. Внутри `storeAnimalWeighingsToSHTP`: `log('storeAnimalWeighingsToSHTP: start')`,
   затем `animalWeighings = (await getAllNotSuncAnimalWeighings()).where((e) => animalId == null || e.animalId == animalId)` —
   поскольку `animalId` в этом вызове всегда `null` (единственный вызывающий
   код во всём `lib/` — шаг 2, и он никогда не передаёт `animalId`, см.
   «Открытые вопросы»), `where` не фильтрует ничего: в батч попадают все
   строки `AnimalWeighings` с `sync == false` целиком.
4. Если `animalWeighings.isEmpty` — `return` сразу же, без сетевого вызова;
   сценарий не наступает (см. «Альтернативные потоки»). В этом сценарии
   список непуст.
5. Для каждой строки строится элемент батча: `{"animal_id": e.animalId, "guid": await _animalsRepository.getAnimalGuidById(e.animalId), "measurement_unit_id": e.unitId, "weight": e.weight.toString(), "weighing_date": DateFormat('yyyy-MM-dd HH:mm:ss').format(e.weighingDate)}`.
   Этот цикл (как и последующая сборка `ApiMessage(link: '${Constants.farmServiceApi}/weighing-event', method: ApiMethod.post, data: {'weighings': weighings})`)
   находится **вне** `try/catch` метода — `try` начинается только со строки
   получения `rpcClient` (см. «Открытые вопросы» о последствиях этого).
6. Начинается `try`: `final rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc'); final response = await rpcClient.call(message);` —
   именно здесь начинается развилка этого сценария.
7. **Ветка (а) — техническое исключение.** `CustomDioClient.call`
   (`lib/network/api_client/custom_dio_client.dart`) оборачивает
   `AuthInterceptor.getTokenDataByPath` и `dio.request(...)` собственным
   `try/catch`: любое исключение (сеть недоступна, таймаут, обрыв соединения,
   либо любой не-2xx HTTP-ответ — `DioClient` не переопределяет
   `validateStatus`, поэтому Dio по умолчанию бросает `DioException` вне
   200–299) логируется через `getIt.get<Talker>().error('CustomDioClient: call: $e')`
   и безусловно перебрасывается (`rethrow`). Это исключение всплывает прямо в
   `try` шага 6 и перехватывается собственным `catch (e, stackTrace)` метода:
   `getIt<Talker>().handle(e, stackTrace)` — логирование во внутренний
   Talker-лог (виден только через `TalkerScreen`, открываемый из
   `ProfileView` — `lib/pages/profile/presentation/widgets/profile/profile_view.dart`,
   строка `builder: (context) => TalkerScreen(talker: getIt<Talker>(), ...)`),
   **без** повторного `throw`/`rethrow`.
8. **Ветка (б) — отказ без исключения.** `CustomDioClient.call` возвращает
   обычный HTTP-ответ без собственного исключения. Его же внутренняя логика
   нормализации статуса такова, что `status` оказывается отличным от `"1"`/`1`
   только в узком случае: тело ответа — `Map<String, dynamic>` без ключей
   `data`/`animal_exits` (иначе `status` принудительно выставляется в `"1"`
   независимо от содержимого) и при этом с явным `response.data['status'] == 'error'`
   (тогда ответ возвращается как есть, со `status: 'error'`) — любая другая
   форма ответа приводит либо к принудительному `"1"`, либо к
   `{"data": response.data, "status": "1"}`. При такой узкой форме ответа
   назад в `storeAnimalWeighingsToSHTP` возвращается `response`, для которого
   `response['status'] == "1" || response['status'] == 1` — ложно. Условный
   блок (внутри которого находится единственная логика удаления —
   `dao.deleteAllByAnimalId(animalId)`/`dao.clear()`) просто пропускается.
   **`else`-ветки нет вовсе** — управление доходит до конца `try` без единого
   исключения, `catch` не выполняется, ни `Talker`, ни любой другой логгер не
   вызывается ни разу. Метод завершается молча.
9. В обоих случаях (7 и 8) `storeAnimalWeighingsToSHTP` возвращает управление
   `_syncAuthData` как обычный успешно завершённый `Future<void>` — без
   исключения. `await` на шаге 2 не видит ничего необычного, и выполнение
   безусловно продолжается: `await updateAndSyncRegagro(event, emit)`, затем
   `await updateAndSyncSHTP(event, emit)`, затем
   `_emitProgress(emit: emit, dataKey: DataKey.syncDevices)` и
   `await _suncDevices()` — весь оставшийся sync-проход выполняется в точности
   так же, как если бы push взвешиваний завершился успехом.
10. Ни в одной из двух веток не вызывается `DataUpdateBloc._emitError`/
    `_addDataUpdateError` — эта машинерия существует только внутри внешнего
    `catch (error, stackTrace)` обработчика `on<DataUpdateStartAll>`, а этот
    внешний `catch` для данного отказа никогда не срабатывает (исключение,
    если оно и было, погашено на шаге 7, до него не долетев). Следствие: в
    таблицу `DataUpdates` не добавляется ни одной строки об этом отказе, и
    `updateAndSyncRegagro`, которая на следующем вызове читает
    `errorDataUpdates = dataUpdates.where((du) => du.isError)`, чтобы решить,
    запускать ли автоматический повтор всего прохода, никогда не видит этот
    конкретный отказ — он не может инициировать повторную попытку.
11. Если остальные шаги прохода не упали независимо, `on<DataUpdateStartAll>`
    доходит до `emit(DataUpdateSuccess(resetNavigationOnSuccess: event.resetNavigationOnSuccess))` —
    пользователь видит полностью успешное завершение обновления данных, хотя
    батч взвешиваний сервером принят не был.
12. Локально ни одна строка `AnimalWeighings` с `sync == false` не удаляется —
    удаление (`dao.deleteAllByAnimalId`/`dao.clear()`) находится строго внутри
    пропущенного/недостигнутого условного блока. Строки остаются в таблице в
    точности такими же, какими были до попытки отправки (`sync == false`,
    `remoteId` не меняется) — `AnimalWeighingsCubit`/экран истории
    взвешиваний, если открыт, продолжает показывать их как неотправленные.
13. Дальше в этом же проходе `DataUpdateBloc.loadAnimals` вызывает
    `_animalWeighingsRepository.clearSync()` (удаляет только строки
    `sync == true` — этого сценария не касается) и затем
    `_animalsRepository.syncAllAnimals()`, которая через
    `batch.insertAll(db.animalWeighings, allAnimalsData.animalWeigings)`
    вставляет взвешивания, пришедшие с сервера по каждому животному, —
    **рядом** с уже лежащими там неотправленными строками, не заменяя и не
    сверяясь с ними: неудавшийся батч никак не примиряется с этой перезагрузкой.
14. На следующем полном sync-проходе `getAllNotSuncAnimalWeighings()` снова
    выберет тот же самый набор строк (плюс всё, что было записано между
    проходами), и весь батч будет отправлен заново целиком — тот же итоговый
    эффект «повтор на следующем проходе», что и у перемещений
    ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), но
    достигнутый принципиально другим механизмом: там повтор — следствие того,
    что исключение обрывает **весь** проход; здесь — следствие того, что
    строки просто никогда не помечаются отправленными, при том что сам проход
    как раз успешно завершается.

### Альтернативные потоки

- **Пустой батч — сценарий не наступает.** Если на момент вызова
  `getAllNotSuncAnimalWeighings()` нет ни одной строки с `sync == false`
  (после фильтра по `animalId`, который на практике всегда пуст, см. ниже),
  `storeAnimalWeighingsToSHTP` возвращается сразу после первой проверки
  (`if (animalWeighings.isEmpty) return;`), не делая сетевого вызова вовсе.
- **Параметр `animalId` мёртв на практике.** `storeAnimalWeighingsToSHTP({int? animalId})`
  принимает опциональный `animalId` для точечной отправки взвешиваний одного
  животного (`if (animalId != null) await dao.deleteAllByAnimalId(animalId) else await dao.clear()`),
  но единственный вызов метода во всём `lib/` —
  `DataUpdateBloc._syncAuthData` — всегда вызывает его без аргументов;
  ветка `animalId != null` (включая соответствующее условие в `where`)
  недостижима в реально работающем коде.
- **Исключение до входа в `try` — другой, не покрываемый этим сценарием
  случай.** Если `getAllNotSuncAnimalWeighings()` (DAO/Drift-запрos) или
  `_animalsRepository.getAnimalGuidById(e.animalId)` (вызывается на каждой
  строке батча при его сборке) бросит исключение, оно возникает **до**
  строки `try {` и не перехватывается собственным `catch`
  `storeAnimalWeighingsToSHTP` вовсе — такое исключение всплывёт наружу из
  метода, оборвёт `_syncAuthData` и, за неимением промежуточных
  перехватчиков, дойдёт до единственного внешнего `try/catch` в
  `on<DataUpdateStartAll>` — по итоговому наблюдаемому поведению это ближе к
  сценарию перемещений ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md):
  весь проход обрывается, `DataUpdateFailure`), а не к этому UC. Задача этого
  документа — именно отказ **внутри** `try` метода (шаги 7–8 выше), где
  ошибка гасится локально; этот альтернативный, более ранний путь сбоя здесь
  не покрывается и не тестируется (см. «Открытые вопросы»).
- **`REJECTED`-ветки не существует.** В отличие от синхронизации животного
  ([UC-51](UC-51-ACTOR-4-EVT-25-ENT-11-CREATE_ERROR-IN-ANIMAL.md)), где для
  осознанного отказа сервера есть отдельная не бросающая исключение ветка,
  здесь и технический сбой (ветка а), и содержательный отказ сервера
  (ветка б, `status: 'error'`) не различаются по итоговому эффекту вообще —
  оба просто ничего не меняют локально и не поднимаются выше метода; ветка
  (б) при этом даже не логируется, в отличие от (а).

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  все строки батча, отправка которого отказала (по любой из двух причин),
  остаются `sync == false` без изменений; тот же набор (плюс новые,
  записанные между проходами) будет повторно отправлен целиком на следующем
  полном sync-проходе.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `_animalsRepository.getAnimalGuidById(e.animalId)` при сборке каждого
  элемента батча (см. «Альтернативные потоки» — потенциальный источник
  исключения вне `try`); сама сущность `Animal` этим сценарием не изменяется.
  Позже, в этом же проходе, `AnimalsRepository.syncAllAnimals()` перезаписывает
  список взвешиваний каждого животного данными с сервера, не трогая
  оставшиеся неотправленные строки (шаг 13).
- `DataUpdates` (лог sync-прохода, специфицируется будущим модулем SYSTEM) —
  **не получает** ни одной строки об этом отказе (в отличие от аналогичного
  сценария перемещений, [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) —
  ключевое отличие этого сценария.

### Бизнес-правила

- Результат сценария — `CREATE_ERROR` для обеих под-веток (техническое
  исключение и несостоявшийся статус ответа без исключения) — ни одна из них
  не доходит до пользователя как осознанно предъявленное решение по
  конкретному взвешиванию или батчу: обе тонут внутри одного метода, не
  всплывая даже до уровня всего sync-прохода. `CREATE_REJECTED` для push
  взвешиваний структурно недостижим в текущем коде — нет пути, которым
  содержательный отказ сервера был бы отличим от технического сбоя на любом
  вышестоящем уровне.
- Push — единый батч на все ещё не отправленные записи разом, не по одной
  (см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), инвариант
  «Push не различает создание и правку»); отказ применяется ко всему батчу
  одновременно, партиального успеха на уровне отдельной записи в этой
  архитектуре запроса не существует.
- В отличие от аналогичного сценария перемещений
  ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), отказ push
  взвешиваний **не обрывает** sync-проход и **не помечается** как ошибка
  прохода — весь остальной проход выполняется до конца и штатно завершается
  успехом. Единственный наблюдаемый пользователем эффект — то, что
  взвешивания, отправленные до сбоя, продолжают числиться неотправленными на
  экране их истории; никакого сообщения об ошибке, связанного именно с этим
  шагом, нигде не показывается.
- Никакого отдельного retry/backoff-механизма для конкретно этого батча нет —
  «повтор на следующем проходе» не оформлен как явная бизнес-логика, это
  побочный эффект того, что `getAllNotSuncAnimalWeighings()` при каждом
  полном проходе просто повторно выбирает все строки с `sync == false`, не
  различая «ещё не пробовали» и «уже пробовали и не получилось».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба под-сценария (техническое исключение
и несостоявшийся статус ответа без исключения) воспроизводятся статическим
чтением кода целиком: `DataUpdateBloc._syncAuthData` →
`AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` →
`CustomDioClient.call`/`DioClient`. Возможное исправление (например,
логирование ветки (б), либо запись отказа в `DataUpdates`, либо перенос
сборки батча внутрь `try`) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `storeAnimalWeighingsToSHTP()` без собственного `try/catch`; безусловно продолжает следующими шагами независимо от исхода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный внешний `try/catch` всего прохода; для этого сценария никогда не срабатывает, т.к. исключение гасится раньше |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `_addDataUpdateError` | CURRENT | пишут строку в `DataUpdates`/эмитят `DataUpdateFailure` — не вызываются для этого сценария ни разу |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | читает `errorDataUpdates` из `DataUpdates`, чтобы решить о повторе всего прохода — не видит этот отказ |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | позже в этом же проходе вызывает `_animalWeighingsRepository.clearSync()` (не затрагивает `sync == false` строки) и `_animalsRepository.syncAllAnimals()` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` | CURRENT | строит батч-payload (вне `try`), вызывает `rpcClient.call` (внутри `try`); `catch` логирует через `Talker.handle` без `rethrow`; при `status` вне `"1"`/`1` без исключения — `if` без `else`, метод молча завершается; удаление строк достигается только при явном успехе |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` | CURRENT | выбирает батч, который будет повторно отправлен целиком на следующем проходе |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalGuidById` | CURRENT | вызывается на каждой строке батча вне `try` метода — потенциальный источник исключения, не покрываемого этим сценарием (см. «Альтернативные потоки») |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncAllAnimals` | CURRENT | `batch.insertAll(db.animalWeighings, allAnimalsData.animalWeigings)` — вставляет серверные взвешивания рядом с оставшимися неотправленными, не сверяясь с ними |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor`; при HTTP-успехе нормализует `status` в `"1"`, кроме узкого случая `Map` без `data`/`animal_exits` и с явным `status: 'error'` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings`, `deleteAllByAnimalId`, `clearSync` | CURRENT | выбор батча по `sync == false`; удаление, достигаемое только при успехе; `clearSync` удаляет лишь `sync == true` строки |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings`, `AnimalWeighing` | CURRENT | таблица/модель; `sync` остаётся `false` для всего батча при этом отказе |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `TalkerScreen` | CURRENT | единственное место в приложении, где виден лог `Talker` — включая запись, оставленную веткой (а) этого сценария |

## Критерии приёмки

- Если для непустого батча (`getAllNotSuncAnimalWeighings()` вернул хотя бы
  одну строку) вызов `rpcClient.call` внутри `storeAnimalWeighingsToSHTP`
  бросает исключение, метод логирует его через `getIt<Talker>().handle(e, stackTrace)`
  и возвращается без исключения — вызывающий код (`_syncAuthData`) не видит
  никакого сбоя.
- Если тот же вызов возвращает ответ с `response['status']`, отличным от
  `"1"`/`1`, но без исключения, метод не удаляет ни одной строки, ничего не
  логирует и возвращается так же тихо, как при полном успехе.
- Ни в одном из двух случаев не вызывается `DataUpdateBloc._emitError`/
  `_addDataUpdateError` — в `DataUpdates` не добавляется ни одной строки об
  этом отказе.
- Sync-проход продолжается следующими шагами (`updateAndSyncRegagro`,
  `updateAndSyncSHTP`, `_suncDevices`) и при отсутствии независимых сбоев
  завершается `DataUpdateSuccess`.
- Ни одна строка `AnimalWeighings` из батча не получает удаление (`sync`
  остаётся `false`); на следующем полном sync-проходе
  `getAllNotSuncAnimalWeighings()` вернёт тот же набор (плюс любые новые
  строки), и попытка отправки повторится целиком.

## Связанные тесты

TBD — теста нет. Ни `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`, ни
прогон этого сценария через `DataUpdateBloc` тестами не покрыты — в
репозитории нет тестового файла для `AnimalWeighingsRepository` вовсе.

Единственный смежный тестовый файл по взвешиваниям —
`test/pages/animal_weighings_cubit_test.dart` — покрывает
`AnimalWeighingsCubit` (`delete`, `load`, `setDateFilter`, `clearSelection`,
`selectAnimalWeighing` и т.д., группы вида `'UC-87 — AnimalWeighingsCubit.delete (неотправленное)'`,
`'UC-93 — AnimalWeighingsCubit.load (история конкретного животного)'`), не
push-синхронизацию — ни один тест этого файла не мокает и не проверяет
`storeAnimalWeighingsToSHTP`/`rpcClient`/`DataUpdateBloc`.

## Открытые вопросы и ограничения

- **Расхождение с описанием в [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md).**
  Текст события утверждает, что push взвешиваний — «самый первый доменный шаг
  `_syncAuthData`, ещё до синхронизации ферм/мест». При прямом чтении
  текущего кода `_syncAuthData` (`lib/blocs/data_update/data_update_bloc.dart`)
  порядок вызовов иной: `_deletePlacesFromRDS()` → `_syncFarms()` →
  `_syncPlaces()` → и только затем `storeAnimalWeighingsToSHTP()` — то есть
  взвешивания отправляются **после**, а не до синхронизации ферм/мест. Эта
  спека сама это не правит (EVT-45 — заморожен), но фиксирует наблюдаемое
  расхождение, чтобы оно не потерялось.
- **Ветка (б) — единственная во всём просмотренном коде AnimalWeighing,
  которая не логируется вообще ничем.** В отличие от ветки (а) (Talker) и в
  отличие от аналогичного места у перемещений
  ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md), где
  несостоявшийся статус сам явно бросает `Exception` и попадает под общий
  `catch`/`rethrow`), здесь несостоявшийся статус ответа не оставляет вообще
  никакого следа — ни в `Talker`, ни в `DataUpdates`, ни где-либо ещё. Является
  ли это осознанным решением (например, ожидание, что сервер этот эндпоинт
  никогда не возвращает `status`, отличный от `"1"`, в 2xx-ответе) или
  недосмотром — ничем в коде/комментариях не зафиксировано.
- **Молчаливый успех всего прохода при фактическом отказе push.** Поскольку
  ни одна из двух веток не поднимает исключение, а вся отчётность об ошибках
  прохода (`DataUpdates`, `DataUpdateFailure`) привязана только к внешнему
  `catch` `on<DataUpdateStartAll>`, пользователь получает `DataUpdateSuccess`
  для прохода, в котором взвешивания на сервер фактически не попали —
  единственный способ это заметить — открыть экран истории взвешиваний и
  увидеть, что записи всё ещё числятся неотправленными, либо открыть
  `TalkerScreen` из профиля и найти там запись ветки (а) (для ветки (б) —
  вообще никак). Является ли такая полная развязка «успеха прохода» и
  «успеха push взвешиваний» осознанным продуктовым решением — не
  зафиксировано.
- **Сборка батча (включая `getAnimalGuidById` на каждой строке) вне `try`
  метода — отдельный, здесь не покрытый путь сбоя.** Как отмечено в
  «Альтернативные потоки», исключение на этом более раннем шаге ведёт к
  совершенно другому наблюдаемому поведению (обрыв всего прохода, как у
  перемещений), а не к тихому проглатыванию, документируемому здесь. Оценка
  вероятности такого сбоя на практике (например, гонка между удалением
  животного и попыткой отправить его ещё не удалённое взвешивание) не
  проводилась — она вне рамок задачи, поставленной для этого документа.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим
  чтением кода (`_syncAuthData` → `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` →
  `CustomDioClient.call` → `DioClient`), включая точную форму ответа,
  необходимую для ветки (б) (`Map` без `data`/`animal_exits`, с
  `status: 'error'`) — реальный контракт `POST .../weighing-event` со стороны
  сервера этой спекой не верифицирован.
