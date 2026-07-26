# UC-108 — Система не может перезагрузить список выбытий с сервера при полном sync-проходе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь —
после push-шага выбытий (`sendDisposalsToApi`, [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md))
— система пытается забрать с сервера актуальный список выбытий за последний
год и перезаписать им локальную таблицу `Disposals`. Этот файл — сценарий, в
котором именно этот запрос (`GET .../disposals`) не может быть выполнен:
`DisposalRepository.getReportsFromApiAndSave` не имеет собственного
`try/catch` вовсе (в отличие от симметричного pull-шага перемещений,
[EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md), где
исключение перехватывается, логируется и глотается), и `syncDisposals()`
тоже не оборачивает вызов этого метода в собственный `try/catch` —
исключение всплывает как есть до общего обработчика `DataUpdateBloc` и
обрывает весь sync-проход целиком.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода (`DataUpdateBloc`), без участия пользователя в момент
именно этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, `_authRepository.isAuthorized()` истинно, выполнение дошло до
   `_syncAllData` через `_syncAuthData` → `updateAndSyncRegagro` (тот же путь
   до этой точки, что и в [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md),
   «Основной поток», шаги 1–3 — здесь не повторяется; явный полный sync pass
   как таковой специфицируется модулем `SYSTEM`, см. [MOD-4](../modules/MOD-4-ANIMAL.md),
   «Граница», не этим файлом).
2. Внутри `_syncAllData` к этому моменту уже отработали (по порядку)
   `_clearDataUpdates()`, `loadUser`, `syncAllUnsentAnimals()`,
   `_settingsRepository.getSettingFromSHTP()` (+ опционально
   `setSettingToSHTP()`), и `_movementReportRepository.syncMovements()`
   завершился без исключения (оба его шага, push и pull — см.
   [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)). Следующий
   вызов в теле метода — `await _disposalRepository.syncDisposals()`.
3. `syncDisposals()` = `await sendDisposalsToApi(); await
   getReportsFromApiAndSave();` — без собственного `try/catch` вокруг обоих
   шагов. Этот сценарий начинается с того момента, когда push-шаг
   (`sendDisposalsToApi`, [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md))
   уже завершился без исключения — либо потому что `getNotSyncDisposals()`
   вернул пустой список (`notSync.isEmpty` → ранний `return`), либо потому
   что все группы неотправленных выбытий были успешно отправлены
   (`sendDisposalList`) и их строки уже помечены `sync=true`
   (`dao.updAll(...)`) отдельным, уже зафиксированным вызовом, до начала
   pull-шага. Если бы push сам бросил исключение — это другой сценарий
   ([EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md), собственный
   `try/catch` с `rethrow` внутри `sendDisposalsToApi`), и
   `getReportsFromApiAndSave()` не вызывался бы вовсе в этом проходе — не
   предмет этого файла.
4. `getReportsFromApiAndSave` (вызывается без аргумента `startTime`, поэтому
   внутри `startTime ?? yearAgo` всегда берёт `yearAgo` — «сегодня минус 365
   дней»; `end` — «завтра») строит `ApiMessage(link:
   '${Constants.disposalServiceApi}/disposals', method: ApiMethod.get, data:
   {'start_date': ..., 'end_date': ...})` и вызывает его через
   `rpcClientSHTP.call(message)` (`ApiClient`, `instanceName: 'farm_rpc'`).
5. Исключение возникает в одной из трёх точек внутри тела метода, ни одна из
   которых не обёрнута локальным `try/catch`:
   - сам сетевой вызов `rpcClientSHTP.call(message)` — единственное место,
     где происходит логирование: `CustomDioClient.call` перехватывает,
     логирует через `getIt.get<Talker>().error('CustomDioClient: call:
     $e')` и делает `rethrow`;
   - приведение типа `(response['data'] as List)` сразу после успешного
     ответа — бросает `TypeError`, если поле `data` отсутствует или имеет
     другую форму (нет проверки `response['status']`, как и у Movement);
   - внутри `.map((e) => ...)` — `DisposalExtension.fromJsonRint(e)`
     (drift-генерируемый `Disposal.fromJson`) либо последующий
     `.copyWith(placeId: Value(e['from_place_id'] as int?))` — если один
     конкретный элемент ответа имеет неожиданный тип поля.
   Ни для второй, ни для третьей точки не создаётся никакой записи в логах
   до того, как исключение достигнет внешнего обработчика (шаг 10) — в
   отличие от сетевого случая, где `CustomDioClient` уже залогировал его
   раньше.
6. Поскольку присваивание `final disposals = (response['data'] as
   List).map(...).toList()` не завершается ни в одном из трёх случаев,
   условный блок `if (disposals.isNotEmpty) { await dao.clear(); await
   dao.insAll(disposals); }` не выполняется вовсе — ни разу, независимо от
   того, какая из трёх точек стала причиной. Локальная таблица `Disposals`
   остаётся ровно в том состоянии, в котором её оставил push-шаг 3 этого
   прохода (отправленные строки уже помечены `sync=true`) — этим пул-сбой
   отличается от Vaccination (см. «Бизнес-правила»).
7. `syncDisposals()` не оборачивает `await getReportsFromApiAndSave()`
   собственным `try/catch` — исключение продолжает всплывать из
   `syncDisposals()` без изменений.
8. `_syncAllData` тоже не оборачивает `await
   _disposalRepository.syncDisposals()` — исключение всплывает дальше;
   следующие вызовы в теле этого же метода — `_syncEditedAnimals()`,
   `loadAnimals(event, emit)`, `_vaccinationsRepository.syncVaccinations(true)`
   — в этом проходе **не выполняются вовсе**.
9. Исключение продолжает всплывать через `updateAndSyncRegagro` →
   `_syncAuthData` (оба вызывают следующий шаг через `await` без
   собственного `try/catch`) — поэтому `updateAndSyncSHTP(event, emit)` и
   `_suncDevices()`, идущие в `_syncAuthData` после `updateAndSyncRegagro`,
   тоже не выполняются в этом проходе.
10. Достигает внешнего `try/catch` в `DataUpdateBloc.on<DataUpdateStartAll>`.
    Этот `catch` логирует через `getIt<Talker>().error('Возникла при
    обновлении данных $error $stackTrace')` и вызывает `_emitError`.
11. `_emitError` пишет в `DataUpdates`-журнал строку с `dataCategory:
    _currentDataCategory`, `errorDataKey: _currentDataKey`, `errorMessage:
    'error: $error, stackTrace: $stackTrace'`, и эмитит
    `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey:
    _currentDataKey, errorMessage: ...)`. На момент этого сбоя ни
    `syncMovements()`, ни `syncDisposals()` не вызывали `_emitProgress`
    самостоятельно — последний явный вызов внутри `_syncAllData` до этой
    точки: `_emitProgress(dataKey: DataKey.syncUnsentAnimals, dataCategory:
    DataCategory.syncUnsentAnimals)`, затем `_emitProgress(dataKey:
    DataKey.syncSettings)` (без `dataCategory`, поэтому `_currentDataCategory`
    не меняется). Итог: `_currentDataCategory ==
    DataCategory.syncUnsentAnimals`, `_currentDataKey == 'syncSettings'` —
    оба значения не имеют отношения ни к Movement, ни к Disposal.
12. `finally`-блок обработчика `on<DataUpdateStartAll>` всё равно выполняется
    (`resetClient` для `farm_rpc` и `r3_rpc`), независимо от исхода `try`.
13. Пользователь на экране `DataUpdatePage` видит общий экран ошибки
    синхронизации (`DataUpdateInProgressWidget(isError: true)`, `_Body.build`,
    ветка `state is DataUpdateFailure`) с текстом `tr('an_error_data')` +
    `tr('syncSettings')`. Строки `'syncSettings'` нет ни в одном `.arb`-файле
    (`app_en.arb`/`app_ru.arb`) и нет отдельного `case` для неё в
    `AppLocalizations.tr` — попадает в `default: return key;`, то есть
    пользователь буквально видит нетранслированный внутренний ключ
    `syncSettings` вторым абзацем текста ошибки. Кнопки — «Попробовать снова»
    (`DataUpdateStartAll(again: true, showDataUpdatePage: false)`, что
    перезапускает `_syncAllData` заново **с самого начала**, не с шага
    Disposal) и «На главную» (`go_to_home`).

### Альтернативные потоки

- **Пустой ответ сервера.** `(response['data'] as List)` пуст — метод
  доходит до условия на шаге 6 и не выполняет ни `clear()`, ни `insAll()`.
  Другой `RESULT` (`READ_OK`, вызов завершился успешно, просто без данных
  для замены), не этот сценарий.
- **Push-шаг (`sendDisposalsToApi`) сам бросает исключение.** Логируется
  через `getIt<Talker>().error('sendDisposalsToApi Error: $e', stackTrace)`
  и пробрасывается (`rethrow`) — `getReportsFromApiAndSave()`, предмет этого
  файла, не вызывается вовсе в этом проходе. Отдельное событие
  ([EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md)), не
  описывается этим файлом.
- **Три конкретные точки исключения шага 5 (сеть / приведение типа `data` /
  парсинг одного элемента ответа)** — неотличимы друг от друга на уровне
  кода (одна и та же непойманная область без ветвления) и приводят к
  одинаковому исходу (`READ_ERROR`, весь проход обрывается); не разнесены на
  отдельные use-case.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) —
  номинальный субъект сценария, но **фактически не мутируется этим шагом**:
  исключение (в любой из трёх точек шага 5) возникает строго до того, как
  выполняется `dao.clear()`/`dao.insAll()` — таблица остаётся в том виде, в
  каком её оставил предшествующий push-шаг того же прохода (уже отправленные
  строки помечены `sync=true`, остальные не тронуты).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим шагом напрямую (поле `animalId` на `Disposal` лишь
  ссылается на него, как задокументировано в
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), «Связи»). Косвенно
  задет тем, что этот сбой обрывает проход до `loadAnimals` — сам `Animal` в
  этом проходе не перезагружается вовсе (см. «Бизнес-правила»), но это
  следствие обрыва прохода, а не действие данного шага над сущностью.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — не
  затрагивается этим шагом; упоминается только как непосредственно
  предшествующий, уже успешно завершившийся шаг того же прохода (см.
  «Основной поток», шаг 2).

### Бизнес-правила

- **Ключевое отличие от pull-а перемещений
  ([EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)).** Там ошибка
  пуллинга перехватывается собственным `try/catch`, логируется через
  `Talker.error` и полностью проглатывается — `syncMovements()`, весь
  остальной sync-проход (`_disposalRepository.syncDisposals()` — этот
  сценарий начался бы штатно — `_syncEditedAnimals()`, `loadAnimals`,
  `syncVaccinations`) продолжается как ни в чём не бывало, `DataUpdateSuccess`
  всё ещё достижим. Здесь у `getReportsFromApiAndSave` нет вовсе никакого
  `try/catch` на уровне метода, и `syncDisposals()` его тоже не добавляет —
  исключение добирается до общего обработчика `DataUpdateStartAll`, и весь
  проход завершается `DataUpdateFailure`, независимо от того, что фермы,
  места, животные (неотправленные) и перемещения уже успешно
  синхронизировались в этом же проходе.
- **Отличие от Vaccination
  ([EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  [UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)) — тот же
  исход прохода, разная судьба локальных данных.** Оба пути пробрасывают
  исключение и валят весь проход, но у Vaccination `dao.clear()` вызывается
  безусловно, **до** попытки пуллинга — сбой там необратимо стирает
  локальную таблицу вакцинаций целиком. У Disposal `dao.clear()`/`insAll()` —
  условная пара **после** успешного построения списка из ответа (тот же
  паттерн, что у Movement) — сбой здесь оставляет локальную таблицу
  `Disposals` нетронутой. Три структурно однотипных pull-шага (Movement /
  Vaccination / Disposal) реализуют три разных сочетания «глотать ли
  исключение» × «чистить ли таблицу заранее», не унифицированы ни по одной
  из двух осей.
- **Отказ этого шага рвёт больше последующих шагов `_syncAllData`, чем отказ
  Vaccination.** Disposal-пуллинг стоит в теле `_syncAllData` раньше
  Vaccination — сразу после Movement, до `_syncEditedAnimals()`,
  `loadAnimals(event, emit)` и `_vaccinationsRepository.syncVaccinations(true)`.
  Его отказ означает, что ни один из этих трёх шагов не выполняется в этом
  проходе вовсе — включая полную перезагрузку `Animals`/
  `AnimalIdentifications`/`AnimalWeighings` ([UC-92](UC-92-ACTOR-4-EVT-46-ENT-15-READ_ERROR-IN-ANIMAL.md)
  описывает симметричный сбой уже внутри `loadAnimals`, здесь до него дело
  не доходит вовсе) и локальную отправку отредактированных животных
  (`_syncEditedAnimals`). У Vaccination (последний вызов в теле
  `_syncAllData`) её собственный отказ не обрывает ничего внутри
  `_syncAllData` — только шаги `updateAndSyncSHTP`/`_suncDevices` уровнем
  выше, в `_syncAuthData`.
- **Отсутствие собственного логирования непосредственно в
  `getReportsFromApiAndSave`.** В отличие от push-шага той же пары
  (`sendDisposalsToApi`, логирует `'sendDisposalsToApi Error: $e'` перед
  `rethrow`) и в отличие от Vaccination (`Talker.info('getVaccinationsFromApi
  Error: $e st: $st')` перед `rethrow`), здесь для двух из трёх источников
  исключения (приведение типа `data`, парсинг элемента ответа) нет вовсе
  никакой записи в логах до того, как исключение долетит до общего
  обработчика `DataUpdateStartAll` — единственная точка внутри этого метода,
  где что-либо логируется, — сетевой уровень `CustomDioClient.call`.
- **Экран ошибки маркируется под ключом `syncSettings`, полностью не
  относящимся ни к Movement, ни к Disposal.** Ни `syncMovements()`, ни
  `syncDisposals()` не вызывают собственный `_emitProgress` — последний явный
  вызов до этой точки в `_syncAllData` установил `_currentDataCategory =
  DataCategory.syncUnsentAnimals` и `_currentDataKey = 'syncSettings'` (шаг
  синхронизации настроек, отработавший раньше). У этой строки нет случая в
  `AppLocalizations.tr` (`default: return key`) — пользователь видит
  буквально нетранслированную строку `syncSettings`, не текст об ошибке
  выбытий и не текст об ошибке настроек.
- **`startTime` — используемый, но никогда не передаваемый параметр.** В
  отличие от одноимённого мёртвого параметра у Movement
  (`MovementReportRepository.getReportsFromApiAndSave`, полностью
  игнорируется в теле), здесь `startTime` реально используется
  (`start_date` запроса), но единственный вызывающий код
  (`syncDisposals()`) не передаёт для него значение — на практике всегда
  запрашивается диапазон «последние 365 дней». Это не влияет на то,
  происходит ли сбой этого сценария (сбой воспроизводится независимо от
  диапазона дат), упомянуто только как контекст самого запроса.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (включая путь ошибки) полностью реализован
существующим кодом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода; ловит проброшенное исключение, вызывает `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro`; при исключении из него не доходит до `updateAndSyncSHTP`/`_suncDevices` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе; при исключении из `_syncAllData` не выполняет ничего после вызова |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | порядок: `...` → `_movementReportRepository.syncMovements()` → `_disposalRepository.syncDisposals()` → `_syncEditedAnimals()` → `loadAnimals` → `syncVaccinations(true)`; исключение из `syncDisposals()` пропускает три последних шага в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress`, `_emitError` | CURRENT | `_emitProgress` устанавливает `_currentDataCategory`/`_currentDataKey`, последний раз перед этим шагом — со значениями `syncUnsentAnimals`/`syncSettings`; `_emitError` использует их при записи ошибки и в `DataUpdateFailure.errorMessageKey` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.syncDisposals` | CURRENT | оркестрация: `await sendDisposalsToApi(); await getReportsFromApiAndSave();` — без собственного `try/catch` вокруг обоих шагов |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalsToApi` | CURRENT | предшествующий push-шаг ([EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md)); при исключении логирует и `rethrow` — тогда pull, предмет этого файла, не вызывается вовсе |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getReportsFromApiAndSave` | CURRENT | ядро этого сценария: `GET`-запрос без проверки `status`, без собственного `try/catch`; `dao.clear()`/`dao.insAll()` — условная пара, недостижимая при исключении |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals`, `DisposalExtension.fromJsonRint` | CURRENT | таблица (все поля nullable) и drift-генерируемая конвертация ответа сервера — источник возможного `TypeError` при неожиданной форме элемента |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll` | CURRENT | нижележащие примитивы, недостижимые в этом сценарии |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | транспорт запроса; единственная точка логирования (`Talker.error`) для сетевого источника исключения, перед `rethrow` |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` (ветка `default: return key;`) | CURRENT | у ключа `syncSettings` нет отдельного `case` — пользователю показывается нетранслированный внутренний ключ |
| `lib/l10n/app_en.arb`, `lib/l10n/app_ru.arb` | (ключ `syncSettings` отсутствует) | CURRENT | подтверждает отсутствие перевода для ключа, под которым маркируется эта ошибка |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.syncSettings`, `DataKey.syncUnsentAnimals`, `DataCategory.syncUnsentAnimals`, `DataUpdates.isError` | CURRENT | значения, унаследованные из более раннего шага, под которыми фактически маркируется эта ошибка |
| `lib/pages/data_update/data_update_page.dart` | `_Body.build` (ветка `DataUpdateFailure`), `DataUpdateInProgressWidget` | CURRENT | UI общего экрана ошибки синхронизации: `tr(errorTitleKey)` + `tr(errorMessageKey)`, кнопки «Попробовать снова» / «На главную» |
| `lib/constants.dart` | `Constants.disposalServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/disposals` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | абстрактный транспортный интерфейс (`instanceName: 'farm_rpc'`) |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и после
  завершения без исключения push-шага выбытий (`sendDisposalsToApi`),
  `syncDisposals()` вызывает `getReportsFromApiAndSave()`, которая
  запрашивает `GET .../disposals`.
- Если этот запрос, либо приведение типа `response['data'] as List`, либо
  парсинг любого элемента ответа бросают исключение, оно пробрасывается
  наружу из `getReportsFromApiAndSave`/`syncDisposals` без дополнительной
  обработки — блок `dao.clear()`/`dao.insAll()` не выполняется, локальная
  таблица `Disposals` остаётся в том состоянии, в котором её оставил
  предшествующий push-шаг этого же прохода.
- Исключение продолжает всплывать через `_syncAllData` →
  `updateAndSyncRegagro` → `_syncAuthData` — `_syncEditedAnimals()`,
  `loadAnimals(event, emit)`, `_vaccinationsRepository.syncVaccinations(true)`
  (следующие шаги `_syncAllData`) и `updateAndSyncSHTP`/`_suncDevices()`
  (идущие в `_syncAuthData` после `updateAndSyncRegagro`) в этом проходе не
  выполняются.
- Весь sync-проход завершается `DataUpdateFailure` (не `DataUpdateSuccess`),
  и `errorMessageKey` этого состояния равен значению `_currentDataKey`,
  унаследованному от более раннего шага (`'syncSettings'`), а не какому-либо
  ключу, специфичному для Disposal.
- Пользователь видит общий экран ошибки синхронизации, второй строкой текста
  которого — нетранслированный ключ `syncSettings` (нет соответствующей
  записи ни в `.arb`-файлах, ни в `AppLocalizations.tr`), с кнопками
  «Попробовать снова» (перезапускает `_syncAllData` полностью заново, не с
  шага Disposal) и «На главную».

## Связанные тесты

TBD — теста нет. `test/repositories/disposal_repository_test.dart` содержит
группу `group('UC-107 — getReportsFromApiAndSave', ...)`, но все три её теста
покрывают только успешные ответы сервера (непустой список с
`from_place_id`/`to_place_id`, непустой список без них, пустой список) — ни
один тест не настраивает `farmRpcClient.call` на исключение при
`ApiMethod.get`, то есть сценарий этого файла (`READ_ERROR`) не покрыт вовсе.
`test/blocs/data_update_bloc_test.dart` содержит только два теста
(`'DataUpdateBloc конструируется с полным набором зависимостей из getIt'` и
`blocTest` на `DataUpdateClear`) — `DisposalRepository` фигурирует там только
как замоканная зависимость (`MockDisposalRepository`) для конструирования
`DataUpdateBloc`, без вызова `syncDisposals()` ни в одном тестовом сценарии;
ветка `_syncAllData`/`_disposalRepository.syncDisposals()` не тестируется ни
на успех, ни на ошибку.

## Открытые вопросы и ограничения

- **Три структурно однотипных pull-шага (Movement/Vaccination/Disposal) без
  единой стратегии обработки ошибок.** Movement глотает исключение и не
  трогает локальные данные при сбое; Vaccination пробрасывает исключение и
  безусловно стирает локальные данные ДО попытки пуллинга; Disposal (этот
  файл) пробрасывает исключение, как Vaccination, но не стирает локальные
  данные, как Movement. Не проверялось, является ли именно это сочетание для
  Disposal осознанным проектным решением или случайным следствием того, что
  три метода были написаны независимо друг от друга.
- **Пользователь не получает точного диагноза и видит нетранслированный
  внутренний ключ.** Экран ошибки показывает ключ `syncSettings` —
  унаследованный артефакт шага, отработавшего двумя вызовами раньше, для
  которого к тому же нет записи ни в одном `.arb`-файле: вместо
  человекочитаемого текста (об ошибке выбытий, синхронизации или хоть о чём-то
  осмысленном) пользователь видит буквально строку `syncSettings`.
- **Более широкий радиус обрыва, чем у Vaccination.** Поскольку Disposal
  стоит в очереди `_syncAllData` раньше, отказ этого шага останавливает
  также `_syncEditedAnimals()` (отправку локально отредактированных
  животных) и `loadAnimals` (полную перезагрузку `Animals`/
  `AnimalIdentifications`/`AnimalWeighings`) в этом же проходе — не
  проверялось, насколько это осознанно, учитывая что у самого `loadAnimals`
  есть собственный, отдельно специфицированный сценарий отказа
  ([UC-92](UC-92-ACTOR-4-EVT-46-ENT-15-READ_ERROR-IN-ANIMAL.md)), до которого
  в этом сценарии дело просто не доходит.
- **Отсутствие логирования для двух из трёх источников исключения.**
  Сетевой сбой логируется на уровне `CustomDioClient.call` до всплытия;
  сбой приведения типа `data` или сбой парсинга конкретного элемента ответа
  — нет, единственная запись об этих двух случаях появляется уже на уровне
  общего обработчика `DataUpdateStartAll`, без указания, что именно (форма
  ответа целиком или один конкретный элемент) стало причиной.
- **Повторный запуск («Попробовать снова») перезапускает весь sync-проход
  заново, не только шаг Disposal** — `_syncAllData` при повторной попытке
  выполняется от `_clearDataUpdates()` и далее по всей цепочке (`loadUser`,
  `syncAllUnsentAnimals`, `syncMovements`, и только затем снова
  `syncDisposals`) — не проверялось (и не предмет этого файла — принадлежит
  `SYSTEM`, см. [MOD-4](../modules/MOD-4-ANIMAL.md), «Граница»), насколько
  это осознанное проектное решение против точечного retry только упавшего
  шага.
- **Отсутствие теста на этот сценарий** делает регрессию (например, если бы
  кто-то по аналогии с Movement добавил сюда глотающий `try/catch`, изменив
  наблюдаемое поведение всего прохода с `DataUpdateFailure` на
  `DataUpdateSuccess`) необнаружимой автоматически — см. «Связанные тесты».
