# UC-105 — Sync-проход успешно отправляет ещё не отправленные выбытия на сервер батчами по группам

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все ещё
не отправленные выбытия ([ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md),
`sync == false`) — но не одним общим батчем на весь набор (как перемещения,
[UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)) и не по одной
записи, а группами: записи сначала группируются по составному ключу
причина/место отправления/целевое место/минута времени (`_groupForSend`), и
на каждую группу уходит отдельный `POST`-запрос. Happy-path сценарий, в
котором КАЖДЫЙ такой запрос завершается без исключения — после каждого
успешного запроса все записи соответствующей группы немедленно помечаются
`sync = true`. Событие [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md)
(`disposal.push_synced`) завершает то, что локально начал
[EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) (`disposal.recorded`),
инициированный [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md). Это второй из
пары push-шагов внутри `_syncAllData` — выполняется сразу после
`_movementReportRepository.syncMovements()` ([EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md))
и до `_syncEditedAnimals`/`loadAnimals`/`_vaccinationsRepository.syncVaccinations`.
При успехе `syncDisposals()` сразу продолжается pull-шагом
([EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md)) в
этом же вызове.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), авторизованный пользователь —
весь этот шаг гейтится `_authRepository.isAuthorized()` в
`DataUpdateBloc._syncAuthData`) один раз (`DataUpdateStartAll`), но в каждом
отдельном сетевом вызове этого сценария человек не участвует. Сами записи
выбытия, отправляемые в этом сценарии, были созданы раньше — гостем или
авторизованным пользователем одинаково ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md),
`AnimalDisposalBloc.on<AnimalDisposalEventSave>`, [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md))
— этот факт не влияет на то, отправится ли запись сейчас: единственное
условие отбора — `sync == false`.

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
4. `updateAndSyncRegagro` решает — та же развилка, что уже описана в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md)/[UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)
   (шаг 3/4): по количеству уже накопленных записей `DataUpdate`, наличию
   ошибок в них и флагам события (`event.again`/`event.fullUpdate`), с
   повторной проверкой сети — нужно ли запускать `DataUpdateBloc._syncAllData`
   в этом проходе. Если сеть недоступна на этой проверке или условия не
   выполняются, сценарий до выбытий не доходит (другая ветка).
5. `_syncAllData` — тот же общий префикс, что и в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md)/[UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md):
   `_clearDataUpdates()` → `loadUser` → `syncAllUnsentAnimals()` → settings
   (`setSettingToSHTP`/`getSettingFromSHTP`) → `await
   _movementReportRepository.syncMovements()` ([EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
   вне рамок этого use-case) → **`await _disposalRepository.syncDisposals()`**
   — с этого вызова начинается собственно этот сценарий. `_syncAllData` не
   оборачивает этот вызов в собственный `try/catch`.
6. `DisposalRepository.syncDisposals()`: `await sendDisposalsToApi(); await
   getReportsFromApiAndSave();` — сам метод тоже не оборачивает ни один из
   двух вызовов в try/catch.
7. `sendDisposalsToApi()`:
   1. `notSync = await getNotSyncDisposals()` → `DisposalsDao.getAllNotSync()`
      — `SELECT * FROM disposals WHERE sync = false`.
   2. Если `notSync.isEmpty` — метод возвращается сразу, ни один сетевой
      вызов не выполняется (вырожденный случай «нечего синхронизировать»,
      не этот сценарий).
   3. `groups = _groupForSend(notSync)` строит `List<_DisposalSendGroup>`:
      для каждой записи `d` вычисляется `timeKey =
      DateFormat('yyyyMMddHHmm').format(d.date ?? d.createdAt ??
      DateTime.now())` (минутная точность) и составной ключ `'${d.causeId}_
      ${d.placeId}_${d.toPlaceId}_$timeKey'`; записи с одинаковым ключом
      объединяются в одну `_DisposalSendGroup`. `causeId`/`date`/`fromId`/
      `toId`/`toPlaceId` группы берутся из **первой** встреченной в этом
      ключе записи (`existing.causeId` и т.д. на ветке merge, не
      пересчитываются из последующих записей того же ключа); `animalIds`
      группы — конкатенация `d.animalId` всех записей ключа, **только если
      `d.animalId != null`**; `disposals` группы — все записи ключа
      безусловно, включая те, чей `animalId` был `null` и потому не попал в
      `animalIds` (см. «Открытые вопросы»).
   4. Цикл `for (final group in groups)`: на каждую группу — **отдельный**
      `await sendDisposalList(...)`, затем **отдельный** `await
      dao.updAll(group.disposals.map((e) => e.copyWith(sync: const
      Value(true))).toList())` — обновление применяется сразу после
      успешного запроса этой группы, до перехода к следующей группе (не
      накапливается для одного финального `updAll` в конце).
   5. `sendDisposalList({causeId, date, animalIds, fromId, toId, toPlaceId})`:
      `userId = getIt<AuthRepository>().getUser()?.id ?? -1`; тело —
      `{'disposal_reason_id': causeId, 'disposal_at':
      DateFormat('yyyy-MM-dd hh:mm:ss').format(date.toUtc()), 'animals':
      animalIds, 'from_id': fromId, 'user_id': userId, 'to_id': toId,
      'to_place_id': toPlaceId}`; `ApiMessage(link:
      '${Constants.disposalServiceApi}/disposals', method: ApiMethod.post,
      data: data)`; `rpcClient = getIt.get<ApiClient>(instanceName:
      'farm_rpc')` → `CustomDioClient.call(message)`. Метод **не читает
      возвращённый `Map` вовсе** — `await rpcClient.call(message); return
      true;` — успех этого шага определяется исключительно тем, что вызов
      не бросил исключение, а не содержимым тела ответа (см. «Открытые
      вопросы» и сравнение с [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md),
      где `status` явно проверяется). Возвращаемое `bool` тоже нигде не
      читается вызывающим кодом (`sendDisposalsToApi` не сохраняет
      результат `await sendDisposalList(...)`).
   6. В этом (`CREATE_OK`) сценарии каждый вызов `sendDisposalList` для
      каждой группы завершается без исключения — после каждого из них
      `dao.updAll` (`BaseDao.updAll` → `transaction()`, построчный
      `upd(item)` → `updateCurrent().replace(item)` по локальному `id`)
      помечает все записи этой конкретной группы `sync = true`.
   7. После того как цикл по всем группам завершился без единого
      исключения, `sendDisposalsToApi` возвращается нормально (без
      `rethrow`).
8. Управление возвращается в `syncDisposals`, который продолжает
   `getReportsFromApiAndSave()` ([EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
   — вне рамок этого use-case, но выполняется именно потому, что push не
   бросил исключение.
9. `_syncAllData` продолжает после возврата из `syncDisposals()`:
   `_syncEditedAnimals()` → `loadAnimals(event, emit)` →
   `_vaccinationsRepository.syncVaccinations(true)` — все вне рамок этого
   use-case.

### Альтернативные потоки

- `getNotSyncDisposals()` пуст (нет неотправленных выбытий) →
  `sendDisposalsToApi` возвращается сразу, ни один сетевой вызов не
  выполняется — вырожденный случай, не этот сценарий.
- Один из вызовов `sendDisposalList` внутри цикла бросает исключение (сеть,
  таймаут, не-2xx статус по умолчанию для Dio — `DioClient` не
  переопределяет `validateStatus`) → исключение всплывает из
  `sendDisposalList`, цикл `for` прерывается, **группы, обработанные до
  этой строго раньше в порядке итерации, уже получили `sync = true`**
  (частичный успех на уровне групп — их `dao.updAll` уже закоммичен),
  оставшиеся группы (включая ту, что упала) остаются `sync == false`.
  Собственный `catch (e, stackTrace)` метода `sendDisposalsToApi` логирует
  через `Talker` (`'sendDisposalsToApi Error: $e'`) и безусловно
  перебрасывает (`rethrow`). Отдельный `ERROR`-сценарий, не входит в этот
  use-case.
- Из предыдущего пункта следует: отказ хотя бы одной группы в этом же
  проходе означает, что `getReportsFromApiAndSave` ([EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
  тоже не выполнится в этом проходе (`syncDisposals` не оборачивает два
  вызова раздельно), и все шаги `_syncAllData` после `syncDisposals()`
  (`_syncEditedAnimals`/`loadAnimals`/vaccinations) не выполнятся —
  зафиксировано здесь как факт об очерёдности, не отдельный сценарий.
- Ответ сервера на конкретный `POST /disposals` содержит бизнес-отказ
  (например `{'status': 'error', 'message': ...}`, что `CustomDioClient.call`
  возвращает как обычный `Map` без исключения) — `sendDisposalList` этот
  случай не отличает от успеха, так как вообще не читает тело ответа;
  запрос считается успешным, группа получает `sync = true`. Структурно это
  тот же (`CREATE_OK`) путь, а не отдельный `REJECTED`-сценарий — см.
  «Открытые вопросы».

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — основная
  сущность перехода: `sync` меняется с `false` на `true` для каждой записи
  успешно отправленной группы, сразу после запроса этой группы; локальный
  `id` и прочие поля строки этим шагом не переписываются — `remoteId` для
  выбытий, отправленных этим (push) путём, так и остаётся незаполненным
  (заполняется только для записей, загруженных с сервера через
  [EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md)).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не
  затрагивается этим шагом напрямую; животное НЕ помечается выбывшим
  локально этим (и вообще никаким локальным) шагом — `disposed`/`deletedAt`
  заполняются только при последующей полной перезагрузке животных с
  сервера (см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), инвариант
  «Нет мягкого удаления», и `.claude/rules/domain-model.md`, инвариант 6).
  `animalId` каждой строки читается (для сборки `animalIds` тела запроса),
  не пишется.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — `causeId` читается как есть и передаётся в теле запроса
  (`disposal_reason_id`), справочник отдельно не подгружается.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — `fromId`/`toId`
  (ссылки на фермы по `remoteId`) читаются как есть, не изменяются этим
  шагом.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) —
  `placeId`/`toPlaceId` читаются как есть (участвуют и в ключе группировки,
  и в теле запроса), не изменяются этим шагом.

### Бизнес-правила

- Push группируется по составному ключу причина/место отправления/целевое
  место/минута времени (`_groupForSend`), не единым батчем на весь набор
  (как перемещения, [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md))
  и не по одной записи — один `POST {disposalServiceApi}/disposals` на
  каждую группу.
- Успех/отказ применяется на уровне ГРУППЫ, не на уровне всего набора и не
  на уровне отдельной записи: `dao.updAll` для группы выполняется сразу
  после успешного запроса этой группы, до перехода к следующей — частичный
  успех между группами одного и того же прохода возможен и не откатывается
  (см. «Альтернативные потоки»).
- `fromId`/`toId` группы не входят в ключ группировки и берутся только из
  первой встреченной в этом ключе записи — если бы в один и тот же ключ
  (`causeId`/`placeId`/`toPlaceId`/минута) попали записи с разными `fromId`
  или `toId`, тело запроса унесло бы значение только первой из них, а
  различие остальных было бы отброшено молча (см. «Открытые вопросы»).
- Запись с `animalId == null` включается в `group.disposals` (и получает
  `sync = true` при успехе группы), но не включается в `animalIds` тела
  запроса — количество отправленных на сервер id животных может быть
  меньше количества помеченных синхронизированными строк.
- `sendDisposalList` не проверяет тело ответа сервера вовсе — успех
  определяется исключительно отсутствием исключения при `rpcClient.call`,
  в отличие от `MovementReportRepository.sendMovementsToApi`, которая явно
  проверяет `status` и сама бросает `Exception` при отказе (см. [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)).
- Sync-проход не эмитит отдельный progress-шаг именно для выбытий — вызов
  идёт между перемещениями и `_syncEditedAnimals` без собственного
  `_emitProgress`, как и у перемещений ([UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде, прослежен от
`DataUpdateStartAll` до `dao.updAll` каждой группы. Тестового покрытия на
уровне `DisposalRepository.sendDisposalsToApi`/`_groupForSend`/
`sendDisposalList`/`DataUpdateBloc` нет (см. «Связанные тесты») — это факт
отсутствия теста, а не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | фиксированная последовательность sync-шагов для авторизованного пользователя, вызывает `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, нужно ли запускать `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_disposalRepository.syncDisposals()` сразу после `_movementReportRepository.syncMovements()`, до `_syncEditedAnimals`/`loadAnimals`/`syncVaccinations` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.syncDisposals` | CURRENT | `await sendDisposalsToApi(); await getReportsFromApiAndSave();`, без собственного try/catch |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalsToApi` | CURRENT | выборка неотправленных, группировка, цикл по группам (`sendDisposalList` → `dao.updAll(sync: true)` сразу после каждой), логирование и `rethrow` при исключении |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository._groupForSend` | CURRENT | группировка по составному ключу `causeId_placeId_toPlaceId_timeKey` (минутная точность); `causeId`/`date`/`fromId`/`toId`/`toPlaceId` группы берутся из первой встреченной записи |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalList` | CURRENT | строит тело запроса, выполняет `POST`; не читает тело ответа — успех = отсутствие исключения; возвращаемый `bool` не используется вызывающим кодом |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getNotSyncDisposals` | CURRENT | тонкая обёртка над `DisposalsDao.getAllNotSync` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllNotSync` | CURRENT | `SELECT ... WHERE sync = false` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals`, `Disposal` | CURRENT | таблица/модель; поля `causeId`/`placeId`/`toId`/`toPlaceId`/`fromId`/`animalId`/`date`/`sync`, участвующие в этом сценарии |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser` | CURRENT | источник `user_id` тела запроса, `-1` при отсутствии |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | абстрактный контракт сетевого вызова, используемый `sendDisposalList` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальный `Dio`-запрос; нормализует форму ответа, но результат этой нормализации `sendDisposalList` не читает вовсе |
| `lib/injection_container.dart` | регистрация `getIt` для `instanceName: 'farm_rpc'` | CURRENT | связывает `'farm_rpc'` `ApiClient` с `CustomDioClient` |
| `lib/constants.dart` | `Constants.disposalServiceApi` | CURRENT | базовый URL сервиса `disposal` для эндпоинта `/disposals` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `BaseDao.upd` | CURRENT | построчный `UPDATE` по PK в одной транзакции, выполняется отдельно на каждую группу |

## Критерии приёмки

- При полном sync-проходе (`DataUpdateStartAll`), при наличии сети и
  авторизованном пользователе, для непустого набора записей `Disposal` с
  `sync == false` выполняется по одному `POST {disposalServiceApi}/disposals`
  на каждую группу, построенную `_groupForSend` (ключ
  причина/место/целевое место/минута времени), а не один общий запрос на
  весь набор и не по одному запросу на запись.
- Если ни один из этих запросов не бросает исключение, после прохода каждая
  запись, входившая в `group.disposals` любой из этих групп, имеет
  `sync == true` в локальной БД — независимо от того, была ли она включена
  в `animalIds` тела запроса своей группы.
- `DisposalRepository.getNotSyncDisposals()` после полностью успешного
  прохода этого шага не возвращает больше ни одну из отправленных записей.
- `DisposalRepository.getReportsFromApiAndSave()` (pull-часть
  `syncDisposals`) выполняется в этом же проходе следом за успешным push, а
  не пропускается.
- Содержимое тела ответа сервера на `POST /disposals` не влияет на
  результат этого шага — `sendDisposalList` не читает `status`/тело ответа;
  результат определяется исключительно тем, бросил ли вызов исключение.

## Связанные тесты

`TBD — теста нет`. Проверено: `test/repositories/disposal_repository_test.dart`
содержит только `group('UC-107 — getReportsFromApiAndSave', ...)` (три
теста на pull-часть, не на push) — прочитан целиком, ни `sendDisposalsToApi`,
ни `_groupForSend`, ни `sendDisposalList`, ни `syncDisposals` там не
упоминаются и не вызываются. `grep -rn
"sendDisposalsToApi|syncDisposals|_groupForSend|sendDisposalList|UC-105"
test/` по всему каталогу тестов совпадений не даёт. `test/blocs/data_update_bloc_test.dart`
регистрирует `MockDisposalRepository` в `getIt`, но не содержит ни одного
теста, вызывающего `syncDisposals`/`sendDisposalsToApi`.
`test/integration/registration_to_disposal_test.dart` использует настоящий
(не мокнутый) `DisposalRepository`, но проверяет только локальное сохранение
через `AnimalDisposalBloc` (`savedDisposals.single.sync, isFalse` —
[EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md)), не вызывает
`syncDisposals`/`sendDisposalsToApi`. Остальные call site'ы
`MockDisposalRepository` (`test/pages/animal_history_cubit_test.dart`,
`test/pages/animal_disposal_bloc_test.dart`,
`test/pages/disposal_report_cubit_test.dart`,
`test/pages/unsent_disposals_cubit_test.dart`,
`test/pages/in_work_bloc_test.dart`) относятся к другим событиям/экранам
(история животного, визард выбытия, дневной отчёт, «неотправленные», «в
работе»), не к этому sync-сценарию.

## Открытые вопросы и ограничения

- **`sendDisposalList` не читает тело ответа сервера вовсе** — успех
  определяется исключительно отсутствием исключения при `rpcClient.call`.
  Бизнес-отказ, пришедший как обычный HTTP-ответ (например `{'status':
  'error', 'message': ...}`, который `CustomDioClient.call` возвращает как
  есть, без исключения), здесь молча трактуется как успех: группа получает
  `sync = true`, хотя сервер мог фактически отклонить её. В отличие от
  перемещений ([UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)),
  где `status` явно проверяется и вызывает `throw Exception`, для выбытий
  `REJECTED` структурно недостижим не потому, что сервер никогда не
  отказывает, а потому, что код никогда не смотрит на признак отказа в теле
  ответа.
- **Частичный успех между группами одного прохода возможен и не
  откатывается.** Цикл `for` в `sendDisposalsToApi` шлёт запрос и делает
  `dao.updAll` группа за группой; если N-я по счёту группа бросает
  исключение, группы, обработанные раньше неё в этом же вызове, уже
  закоммичены (`sync = true`) — это не единая транзакция «весь набор
  разом», как в перемещениях. Не подтверждено эмпирически, только чтением
  кода.
- **`fromId`/`toId` группы не входят в ключ группировки** (`causeId_placeId_
  toPlaceId_timeKey`) и берутся только из первой встреченной в этом ключе
  записи — при гипотетическом совпадении причины/места/целевого
  места/минуты, но с разными `fromId` или `toId`, тело запроса унесло бы
  значение только первой записи, различие остальных было бы отброшено
  молча. Не подтверждено как воспроизводимый в реальных данных случай
  (`placeId` в этом приложении обычно однозначно связан с одной фермой) —
  зафиксировано как структурный риск, не разобранный подробнее в рамках
  этого (успешного) сценария.
- **Запись с `animalId == null` помечается `sync = true` вместе со своей
  группой, даже не будучи представленной в `animalIds` тела запроса** —
  число id животных, реально ушедших на сервер, может быть меньше числа
  строк, помеченных синхронизированными.
- **`DateFormat('yyyy-MM-dd hh:mm:ss')` использует `hh` (12-часовой формат
  без AM/PM-маркера)** для поля `disposal_at` — для записей с временем
  после полудня строка не содержит признака половины суток; как это поле
  разбирает сервер и есть ли там компенсация — вне зоны видимости этого
  клиентского кода, не проверено.
- **`date` группы, если ни `d.date`, ни `d.createdAt` не заданы, берётся как
  `DateTime.now()` в момент выполнения `_groupForSend`, отдельно для каждой
  такой записи** (до объединения в группы) — сгруппируются только записи,
  которым достался один и тот же округлённый до минуты момент вызова;
  граничный случай, не проверенный на практике.
- Нет теста на уровне `sendDisposalsToApi`/`_groupForSend`/
  `sendDisposalList`/`syncDisposals`/`DataUpdateBloc` (см. «Связанные
  тесты») — весь сценарий проверен только чтением кода.
