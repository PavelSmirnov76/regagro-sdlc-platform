# UC-106 — Sync push выбытий отказывает технически на одной из групп: исключение пробрасывается наружу, обрывает и pull этого же прохода, и весь sync-проход — но группы, отправленные до отказавшей, уже необратимо помечены `sync=true`

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md) —
`DisposalRepository.sendDisposalsToApi` группирует все ещё не отправленные
выбытия (`sync == false`) по составному ключу
`causeId_placeId_toPlaceId_timeKey` (`_groupForSend`) и отправляет их **не
одним общим батчем на всё**, а последовательным циклом `for (final group in
groups)` — один POST-запрос (`sendDisposalList`) на группу, с `await
dao.updAll(...)`, помечающим строки этой группы `sync = true`, сразу после
успеха каждого отдельного запроса. Здесь одна из групп (не обязательно
первая) технически отказывает: либо `rpcClient.call` внутри `sendDisposalList`
бросает исключение (сеть/таймаут/не-2xx ответ — `DioClient` не переопределяет
`validateStatus`, поэтому Dio по умолчанию бросает `DioException` вне
200–299), либо (что здесь не наступает — см. «Открытые вопросы»)
осмысленный отказ сервера в теле 2xx-ответа, который `sendDisposalList` **не
проверяет вовсе** (в отличие от Movement/`sendMovementsToApi`, где `status`
явно сверяется с `"1"`/`1`). Исключение из `sendDisposalList` всплывает в
`for`-цикл `sendDisposalsToApi`, перехватывается единственным `catch (e,
stackTrace)`, оборачивающим весь метод: `getIt<Talker>().error(...)` логирует,
затем безусловный `rethrow`. Поскольку `sendDisposalsToApi` вызывается из
`syncDisposals()` без собственного `try/catch` (`await
sendDisposalsToApi(); await getReportsFromApiAndSave();`), исключение
обрывает `syncDisposals` целиком — pull-шаг ([EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
в этом проходе не выполняется. Дальше исключение поднимается тем же путём,
что и у Movement ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) —
до единственного внешнего `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>` —
но, в отличие от Movement (единый батч без цикла, где партиальный успех
структурно невозможен), здесь любые группы, чей `sendDisposalList` +
`dao.updAll` успели полностью отработать **до** отказавшей группы, уже
необратимо закоммичены как `sync = true` (`updAll` выполняет каждое
обновление внутри собственной drift `transaction()`, дожидаясь её завершения
перед переходом к следующей группе цикла) — частичный успех на уровне групп
реально существует и не откатывается при последующем `rethrow`.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет — sync-проход к этому шагу уже был запущен ранее авторизованным
пользователем (`DataUpdateStartAll`, диспатчится, например, из
`main_page.dart`, `profile_settings_view.dart`, `in_work_page.dart` или
`data_update_page.dart`) — дальше проход идёт автоматически, без участия
пользователя на уровне отдельного сетевого вызова, как и описано в
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md). Сами выбытия, которые здесь
не удаётся отправить (полностью или частично), были записаны раньше и
локально [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)
(`AnimalDisposalBloc.on<AnimalDisposalEventSave>`,
[EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md)) — ACTOR-5 не
участвует в самом sync-шаге, только в исходном создании синхронизируемых
записей.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети и загрузки
   справочников, при `_authRepository.isAuthorized()`, вызывается
   `_syncAuthData(event, emit)`, которая (после ферм/мест/взвешиваний)
   вызывает `updateAndSyncRegagro(event, emit)` → `_syncAllData(event,
   emit)` (в этом сценарии предполагается, что предыдущие шаги не упали —
   иначе до `_syncAllData` выполнение не доходит вовсе).
2. `_syncAllData` вызывает `_clearDataUpdates()`, `loadUser(event, emit)`,
   `_emitProgress(dataKey: DataKey.syncUnsentAnimals, dataCategory:
   DataCategory.syncUnsentAnimals)` (выставляет `_currentDataKey =
   'syncUnsentAnimals'`, `_currentDataCategory =
   DataCategory.syncUnsentAnimals`), `await syncAllUnsentAnimals()` (в этом
   сценарии завершается без ошибки).
3. `_syncAllData` вызывает `_emitProgress(emit: emit, dataKey:
   DataKey.syncSettings)` — **без** аргумента `dataCategory`. Так как
   `dataCategory` в `_emitProgress` опционален и не переписывает
   `_currentDataCategory`, когда не передан, `_currentDataCategory` остаётся
   `DataCategory.syncUnsentAnimals` (от шага 2), только `_currentDataKey`
   меняется на `'syncSettings'`. Между этим вызовом и крахом ниже никакой
   другой `_emitProgress`, специфичный для выбытий, не вызывается вовсе.
4. `_syncAllData` вызывает (при `event.isUpdateData`)
   `_settingsRepository.setSettingToSHTP()`, затем безусловно
   `_settingsRepository.getSettingFromSHTP()` — оба завершаются без ошибки в
   этом сценарии.
5. `_syncAllData` вызывает `await _movementReportRepository.syncMovements()` —
   в этом сценарии успешно (push и pull перемещений отрабатывают без
   исключения).
6. `_syncAllData` вызывает `await _disposalRepository.syncDisposals()` —
   этот вызов **не обёрнут** в собственный `try/catch` внутри `_syncAllData`.
   `DisposalRepository.syncDisposals` — это `await sendDisposalsToApi();
   await getReportsFromApiAndSave();`.
7. Внутри `sendDisposalsToApi`: `notSync = await getNotSyncDisposals()`
   (`DisposalsDao.getAllNotSync()` — все строки `Disposals` с `sync ==
   false`). Если список пуст — метод возвращается сразу (`if
   (notSync.isEmpty) return;`), сценарий не наступает (см. «Альтернативные
   потоки»). Иначе `groups = _groupForSend(notSync)` разбивает записи на
   группы по ключу `causeId_placeId_toPlaceId_timeKey` (минутная точность
   даты); в этом сценарии список групп содержит две и более группы.
8. Начинается `for (final group in groups)`: для каждой группы по очереди —
   `await sendDisposalList(causeId: ..., date: ..., animalIds: ...,
   fromId: ..., toId: ..., toPlaceId: ...)`, затем при успехе `await
   dao.updAll(group.disposals.map((e) => e.copyWith(sync: const
   Value(true))).toList())`. Для первых `k` групп (`k ≥ 0`) оба вызова
   успевают полностью отработать — их строки `Disposal` уже закоммичены как
   `sync = true` (`updAll` оборачивает обновления `transaction()`,
   дожидаясь коммита перед возвратом).
9. На группе `k+1` `sendDisposalList` вызывает `rpcClient.call(message)`
   (`ApiClient` с `instanceName: 'farm_rpc'`, реализация —
   `CustomDioClient`), и этот вызов заканчивается технически: `dio.request`
   бросает исключение (сеть недоступна, таймаут, обрыв соединения, либо
   любой не-2xx HTTP-ответ, поскольку `DioClient` не переопределяет
   `validateStatus`), `CustomDioClient.call` логирует его через
   `getIt.get<Talker>().error('CustomDioClient: call: $e')` и безусловно
   перебрасывает (`rethrow`). В отличие от `MovementReportRepository.sendMovementsToApi`,
   `sendDisposalList` **не проверяет** поле `status` возвращённого ответа
   вообще — весь возвращённый `response` отбрасывается (`await
   rpcClient.call(message); return true;`), поэтому единственный путь
   отказа этого метода — исключение из самого `rpcClient.call`, не
   содержательный отказ сервера в теле успешного ответа (см. «Альтернативные
   потоки»).
10. Исключение из `sendDisposalList` всплывает в теле `for`-цикла
    `sendDisposalsToApi`, прерывая цикл немедленно — `dao.updAll` для группы
    `k+1` не вызывается, и группы после неё (`k+2`, …) вообще не
    обрабатываются в этом проходе. Исключение перехватывается единственным
    `catch (e, stackTrace)`, оборачивающим весь метод целиком:
    `getIt<Talker>().error('sendDisposalsToApi Error: $e', stackTrace)`,
    затем безусловный `rethrow`.
11. Поскольку исключение вылетает из `sendDisposalsToApi`, вторая строка
    `syncDisposals` (`await getReportsFromApiAndSave()`, pull-шаг,
    [EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md))
    в этом проходе не выполняется вовсе.
12. Исключение не перехватывается ни в `DisposalRepository.syncDisposals`,
    ни в `DataUpdateBloc._syncAllData`, ни в `updateAndSyncRegagro`, ни в
    `_syncAuthData` — единственный `try/catch` на этом пути находится в
    самом обработчике `DataUpdateBloc.on<DataUpdateStartAll>`, оборачивающем
    весь sync-проход целиком.
13. Этот внешний `catch (error, stackTrace)` логирует ошибку через `Talker`
    и вызывает `DataUpdateBloc._emitError`, который (а) пишет одну строку в
    `DataUpdates` через `_addDataUpdateError(dataCategory: _currentDataCategory,
    errorDataKey: _currentDataKey, errorMessage: ...)`, используя значения,
    выставленные на шаге 3: `dataCategoryId = DataCategory.syncUnsentAnimals`
    (оставшееся от совсем другого, более раннего шага, а не от выбытий) и
    `errorDataKey = 'syncSettings'` (тоже не про выбытия — просто последний
    вызванный перед крахом `_emitProgress`), и (б) эмитит
    `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey:
    'syncSettings', errorMessage: 'error: $error, stackTrace: $stackTrace')` —
    общая ошибка всего sync-прохода, не привязанная ни к выбытиям, ни к
    конкретной группе/записи.
14. Поскольку исключение вылетает из середины `_syncAllData`, все шаги,
    запланированные после `_disposalRepository.syncDisposals()` —
    `_syncEditedAnimals()`, `loadAnimals(event, emit)`,
    `_vaccinationsRepository.syncVaccinations(true)` — в этом проходе не
    выполняются вовсе.
15. Итоговое состояние таблицы `Disposals` неоднородно внутри одного и того
    же отказавшего прохода: строки первых `k` (успевших) групп уже
    `sync = true` и на следующем проходе повторно отправлены не будут; строки
    отказавшей группы `k+1` и всех последующих (`k+2`, …) остаются
    `sync = false` — на следующем полном sync-проходе `getNotSyncDisposals()`
    вернёт именно этот оставшийся набор (вместе с любыми выбытиями,
    записанными между проходами), и он будет перегруппирован и отправлен
    заново (возможно, уже в других группах, если состав/минутный ключ
    изменился из-за новых записей).

### Альтернативные потоки

- **Пустой батч — сценарий не наступает.** Если на момент вызова
  `getNotSyncDisposals()` нет ни одной записи с `sync == false`,
  `sendDisposalsToApi` возвращается сразу после первой строки (`if
  (notSync.isEmpty) return;`), не делая сетевого вызова вовсе.
- **Единственная группа в батче — сценарий вырождается в поведение,
  идентичное Movement по наблюдаемому эффекту (хотя механизм иной).** Если
  `_groupForSend` возвращает ровно одну группу, отказ этой группы означает,
  что `k = 0` — ни одна группа не успела закоммититься раньше, и по
  наблюдаемому результату (ни одна запись не помечена `sync = true`) это
  неотличимо от полного отказа единого батча Movement
  ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) — разница
  раскрывается только при двух и более группах в одном проходе.
- **Технически возможная, но здесь не наступающая ветка: содержательный
  отказ сервера в теле успешного ответа.** `sendDisposalList` не читает
  `status` (или любое другое поле) возвращённого `rpcClient.call(message)` —
  метод безусловно `return true;` сразу после `await rpcClient.call(...)`,
  независимо от содержимого ответа. Следствие: даже явный бизнес-отказ
  сервера в 2xx-ответе (например тело со `status: 'error'`, как у Movement)
  **не приводит к исключению** в этом коде вообще — `sendDisposalList`
  вернёт `true`, `dao.updAll` для этой группы выполнится, и группа будет
  ошибочно помечена как успешно отправленная. `CREATE_REJECTED` для push
  выбытий структурно недостижим не потому, что отказ сервера тонет в общем
  `catch` (как у Movement), а потому, что код в принципе не проверяет
  содержимое ответа — эта ветка **не покрывается настоящим сценарием**,
  зафиксирована здесь как отдельное наблюдение (см. «Открытые вопросы»).
- **Частичный успех по группам реален и не откатывается.** В отличие от
  Movement (единый батч без цикла — либо все, либо ни одна запись), здесь
  `for`-цикл с `await` на каждой итерации означает, что группы,
  обработанные до отказавшей, уже необратимо закоммичены как
  `sync = true` — `rethrow` из `sendDisposalsToApi` не откатывает уже
  выполненные `dao.updAll` (нет общей транзакции вокруг всего цикла, только
  вокруг каждого отдельного `updAll`).
- **Pull этого же прохода не выполняется.** Поскольку `syncDisposals`
  вызывает `sendDisposalsToApi()` и `getReportsFromApiAndSave()`
  последовательно, а не независимо, отказ push обрывает и pull
  ([EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md)) в
  этом же проходе — даже если бы сама загрузка списка с сервера была
  доступна и работоспособна, до неё выполнение не доходит.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — записи
  групп, успевших отправиться до отказавшей, необратимо помечены `sync =
  true`; записи отказавшей группы и всех последующих остаются `sync =
  false` и будут перегруппированы и повторно отправлены на следующем
  полном sync-проходе.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — этот сценарий
  не помечает животных выбывшими локально (это отдельный, более поздний
  факт — см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) и
  `.claude/rules/domain-model.md`, инвариант 6) и не трогает `placeId`;
  единственная связь — `animalId` внутри уже созданных строк `Disposal`.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) —
  предшествующий шаг того же `_syncAllData` (`_movementReportRepository.syncMovements()`,
  строка перед `_disposalRepository.syncDisposals()`); в этом сценарии
  предполагается успешным, иначе исключение произошло бы раньше и до
  выбытий выполнение вовсе не дошло бы (см. [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)).
- `DataUpdates` (лог sync-прохода) — получает одну строку через
  `_addDataUpdateError`, с `dataCategoryId`/`errorDataKey`, оставшимися от
  предыдущих, не связанных с выбытиями шагов (`DataCategory.syncUnsentAnimals` /
  `'syncSettings'`), а не что-то специфичное для этого шага или для
  конкретной отказавшей группы; сама сущность и модель append-only лога
  специфицируются будущим модулем SYSTEM, не в этой спеке.

### Бизнес-правила

- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED` — этот отказ
  никогда не доходит до пользователя как осознанно предъявленное решение по
  конкретной группе выбытий: он тонет в generic `DataUpdateFailure` всего
  sync-прохода. Та же формулировка результата, что у Movement
  ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) и Farm
  ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)) — но
  причина недостижимости `REJECTED` здесь иная: `sendDisposalList` вообще не
  считывает `status` ответа (см. «Альтернативные потоки»), тогда как у
  Movement содержательный отказ сервера хотя бы обнаруживается (просто
  обрабатывается тем же `throw`, что и техническая ошибка).
- Push — цикл по группам (не единый батч на всё, как у Movement, и не цикл
  по одной записи, как у Farm/Animal) — группировка по
  `causeId_placeId_toPlaceId_timeKey` (см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md),
  инвариант «Push отправляет батчами»); отказ одной группы прерывает
  оставшиеся группы этого прохода, но не откатывает уже успевшие — частичный
  успех на уровне групп реален, в отличие и от Movement (партиальный успех
  невозможен в принципе — один запрос на всё), и от Farm/Animal (там цикл по
  одной записи, но частичный успех обрабатывается отдельным багом в
  последующей логике, не структурным различием самого запроса).
- Никакого отдельного retry/backoff-механизма для конкретно отказавшей
  группы нет — «повтор на следующем проходе» не оформлена как явная бизнес-
  логика, это побочный эффект того, что `getNotSyncDisposals()` при каждом
  полном проходе просто повторно выбирает все записи с `sync == false`, не
  различая «ещё не пробовали» и «уже пробовали и упали»; притом группировка
  на следующем проходе может получиться иной, если между проходами появились
  новые неотправленные выбытия с тем же ключом.
- Логика повторного запуска всего прохода при наличии ошибок в
  `DataUpdates` (`updateAndSyncRegagro`, `errorDataUpdates.isNotEmpty` →
  задержка 15 секунд → повторный `_syncAllData`) оценивается только на
  **следующем** вызове обработчика `DataUpdateBloc`, а не внутри уже
  упавшего прохода — этот крах не запускает немедленный повтор сам по себе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится статическим
чтением кода (`DataUpdateBloc._syncAllData` →
`DisposalRepository.syncDisposals`/`sendDisposalsToApi`/`sendDisposalList` →
`CustomDioClient.call`/`DioClient`). Возможное исправление (например,
завернуть каждую группу в собственный try/catch, чтобы отказ одной группы не
прерывал остальные, или добавить проверку `status` ответа в
`sendDisposalList`, как у Movement) в рамках этого документирующего прохода
не выполняется — это чисто фиксация уже существующего кода, а не работа над
дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_disposalRepository.syncDisposals()` без собственного `try/catch`, сразу после `_movementReportRepository.syncMovements()`; последующие шаги (edited animals/load animals/vaccinations) не выполняются при исключении |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro` после sync ферм/мест/взвешиваний |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная точка перехвата исключения на этом пути — внешний `try/catch`, вызывающий `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | вызов перед крахом (`dataKey: DataKey.syncSettings`, без `dataCategory`) не меняет `_currentDataCategory` — остаётся `DataCategory.syncUnsentAnimals` от предыдущего, не связанного с выбытиями шага |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет строку в `DataUpdates` (`_addDataUpdateError`) и эмитит `DataUpdateFailure`, используя `_currentDataKey`/`_currentDataCategory` момента краха |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateFailure` | CURRENT | состояние, в которое попадает весь sync-проход при этом крахе |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.syncSettings`, `DataCategory.syncUnsentAnimals` | CURRENT | конкретные (не относящиеся к выбытиям) ключ/категория, зафиксированные в `DataUpdates`/`DataUpdateFailure` при этом крахе |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.syncDisposals` | CURRENT | `await sendDisposalsToApi(); await getReportsFromApiAndSave();` — вторая строка не выполняется при исключении из первой |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalsToApi` | CURRENT | группирует (`_groupForSend`) и отправляет `for`-циклом по группам; `dao.updAll` после каждой успешной группы делает частичный успех необратимым; ловит исключение только для логирования (`Talker.error`) и безусловно перебрасывает (`rethrow`) |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository._groupForSend` | CURRENT | строит группы по ключу `causeId_placeId_toPlaceId_timeKey`; порядок обработки — порядок вставки в `Map`, то есть порядок, в котором `notSync` содержал первую запись каждой группы |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalList` | CURRENT | POST на группу; не проверяет `status` возвращённого ответа вовсе — единственный путь отказа метода — исключение из `rpcClient.call` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getNotSyncDisposals` | CURRENT | выбирает оставшиеся `sync == false` записи, которые будут перегруппированы и повторно отправлены на следующем проходе |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllNotSync`, `updAll` (наследуется от `BaseDao`) | CURRENT | выбор оставшихся неотправленных строк; `updAll` оборачивает обновления каждой группы собственной drift `transaction()`, коммитя её до перехода `for`-цикла к следующей группе |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll` | CURRENT | `transaction(() async { for (final i in list) await upd(i); })` — коммит per-вызов, без общей транзакции вокруг всего `for`-цикла `sendDisposalsToApi` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals`, `Disposal` | CURRENT | таблица/модель; `sync` остаётся `false` только для отказавшей и последующих (не обработанных) групп при этом крахе |

## Критерии приёмки

- Если для непустого набора `getNotSyncDisposals()` вызов `rpcClient.call`
  внутри `sendDisposalList` для одной из групп (в порядке обработки `for`-
  цикла) бросает исключение, `sendDisposalsToApi` логирует ошибку через
  `Talker` и безусловно перебрасывает исключение дальше.
- Группы, чей `sendDisposalList` + `dao.updAll` полностью отработали **до**
  отказавшей группы (в порядке итерации `for`-цикла), получают `sync = true`
  и не откатываются при последующем `rethrow`.
- Отказавшая группа и все группы после неё в этом же `for`-цикле остаются
  `sync == false`, а `dao.updAll` для них не вызывается вовсе.
- Это исключение не перехватывается ни в `DisposalRepository.syncDisposals`,
  ни в `DataUpdateBloc._syncAllData`/`updateAndSyncRegagro`/`_syncAuthData` —
  единственная точка перехвата — внешний `try/catch` в
  `DataUpdateBloc.on<DataUpdateStartAll>`.
- `getReportsFromApiAndSave()` (pull того же вызова `syncDisposals`) и все
  шаги `_syncAllData`, запланированные после `syncDisposals()`
  (`_syncEditedAnimals`/`loadAnimals`/vaccinations), в этом проходе не
  выполняются.
- `DataUpdates` получает ровно одну новую строку: `dataCategoryId =
  DataCategory.syncUnsentAnimals`, `errorDataKey = 'syncSettings'`
  (оставшиеся от более раннего, не связанного с выбытиями шага),
  `errorMessage`, содержащий текст исключения и stack trace.
- Эмитится `DataUpdateFailure(errorTitleKey: 'an_error_data',
  errorMessageKey: 'syncSettings', errorMessage: ...)`; весь sync-проход на
  этом заканчивается.
- На следующем полном sync-проходе `getNotSyncDisposals()` вернёт только
  оставшиеся `sync == false` записи (отказавшей и последующих групп, плюс
  любые новые) — не весь исходный набор, если хотя бы одна группа успела
  отправиться раньше отказавшей.

## Связанные тесты

TBD — теста нет. Ни `DisposalRepository.sendDisposalsToApi`/`syncDisposals`,
ни прогон этого сценария через `DataUpdateBloc` тестами не покрыты.

Единственный тестовый файл по репозиторию —
`test/repositories/disposal_repository_test.dart` — покрывает только
`group('UC-107 — getReportsFromApiAndSave', ...)` (три теста про
pull-обогащение `placeId`/`toPlaceId` и поведение при пустом ответе сервера,
[EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md)); ни
один из них не мокает и не проверяет `sendDisposalsToApi`/`sendDisposalList`/
`syncDisposals`/`DataUpdateBloc`. Смежные тесты по выбытиям
(`test/pages/animal_disposal_bloc_test.dart`, `test/pages/unsent_disposals_cubit_test.dart`,
`test/pages/disposal_report_cubit_test.dart`) касаются других событий модуля
(создание/удаление выбытия), не push-синхронизации, и к этому сценарию не
относятся.

## Открытые вопросы и ограничения

- Является ли отсутствие отдельного `try/catch` вокруг каждой группы внутри
  `sendDisposalsToApi` (позволяющего продолжить оставшиеся группы после
  отказа одной) осознанным решением или упущением — нигде в коде/
  комментариях это не зафиксировано, как и для аналогичных мест у Movement
  ([UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)) и Farm
  ([UC-26](UC-26-ACTOR-4-EVT-12-ENT-9-CREATE_ERROR-IN-FARM.md)).
- `sendDisposalList` не проверяет `status` возвращённого ответа вовсе — даже
  явный бизнес-отказ сервера в теле 2xx-ответа приведёт к тому, что группа
  будет ошибочно помечена `sync = true`, хотя сервер её не принял (см.
  «Альтернативные потоки»). Это не тот же дефект, что у Movement (там отказ
  сервера обнаруживается, но обрабатывается тем же путём, что техническая
  ошибка) — здесь отказ сервера в теле ответа не обнаруживается вовсе.
  Является ли отсутствие такой проверки осознанным упрощением или потерей
  функциональности — не зафиксировано.
- Порядок групп внутри `for`-цикла (а значит, какие именно записи окажутся
  «успевшими», а какие — «оставшимися» при отказе) определяется порядком
  вставки в `Map` внутри `_groupForSend`, то есть порядком, в котором
  `getNotSyncDisposals()` вернул исходный список — сам этот порядок (сортировка
  DAO-запроса) этой спекой не верифицирован.
- Повторная отправка на следующем проходе оставшихся групп (включая
  записи, для которых сервер, возможно, уже частично что-то создал до
  обрыва соединения на середине запроса) может приводить к дублированию на
  сервере — зависит от того, дедуплицирует ли сервер повторный запрос
  `POST .../disposals` (например по `guid` каждой записи), что вне зоны
  видимости этого клиентского кода и этой спеки.
- `DataUpdateBloc` не переопределяет `Bloc.onError` для этого шага —
  единственный способ увидеть исходное исключение (а не только generic
  `DataUpdateFailure`) — это `errorMessage` внутри самого состояния
  (собирается в `_emitError` из `error`/`stackTrace`) либо строка в
  `DataUpdates`, а не что-то персонально видимое пользователю про
  конкретную отказавшую группу выбытий.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим
  чтением кода (`_syncAllData` → `DisposalRepository.syncDisposals`/
  `sendDisposalsToApi`/`sendDisposalList` → `CustomDioClient.call` →
  `DioClient`), включая частичный успех по группам и отсутствие проверки
  `status` в `sendDisposalList`.
