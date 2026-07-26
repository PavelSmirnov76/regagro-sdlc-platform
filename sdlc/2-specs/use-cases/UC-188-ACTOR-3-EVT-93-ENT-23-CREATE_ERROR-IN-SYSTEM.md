# UC-188 — Автоматический полный sync-проход при старте отказывает на верхнем уровне: сети нет до входа в `try` (`finally` не выполняется) либо необработанное исключение внутри прохода тонет в общем `catch`, который пишет строку в DataUpdates

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же автоматический полный sync-проход, что описан в
[EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) —
`DataUpdateBloc.on<DataUpdateStartAll>`, диспатченный `MainPage`'s
`BlocListener<AuthBloc>` сразу после `AuthToMain`, для гостя и
авторизованного пользователя одинаково. Этот документ фиксирует только
самый верхний уровень обработчика — единственную точку сетевого гейта и
единственную точку перехвата исключений на весь проход — а не отдельные
sync-шаги конкретных сущностей (`_syncFarms`/`_syncPlaces`/push
взвешиваний/перемещений/вакцинаций/т.д.), которые уже вне периметра
`MOD-7` (см. границу модуля в [MOD-7](../modules/MOD-7-SYSTEM.md): «этот
модуль владеет только верхнеуровневой оркестрацией... не отдельные
`_syncFarms`/`_syncPlaces`/и т.д.») и там, где отдельно специфицированы —
уже задокументированы в `ANIMAL`/`FARM` (например
[UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md) для
перемещений, [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)
для взвешиваний).

Два независимо проверенных чтением кода под-сценария приводят к разному
наблюдаемому поведению, но оба относятся к одному и тому же результату —
проход не производит для [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
того, что должен был (чистый набор строк успеха для этого прохода), — и
оба фиксируются в одном файле, поскольку это два расходящихся пути одного
и того же верхнеуровневого обработчика, а не два разных триггера:

- **(а) сети нет уже в момент старта.** Проверка сети происходит **до**
  строки `try {` — при её провале обработчик эмитит `DataUpdateFailure` и
  делает `return` **раньше**, чем `try`/`catch`/`finally` вообще
  начинаются. Ни одна строка не пишется в `DataUpdates`, поскольку
  `_addDataUpdateError` вызывается только из `catch`, до которого в этой
  ветке выполнение никогда не доходит.
- **(б) исключение внутри `try`.** Что-то в `loadDirectories()`,
  `_loadBoardDirectories()` или `_syncAuthData()` бросает исключение,
  которое ничем не перехватывается ниже (или явно `rethrow`-ится) и
  долетает до единственного внешнего `catch (error, stackTrace)` —
  который логирует его через `Talker`, вызывает `_emitError`
  (`_addDataUpdateError` пишет строку в `DataUpdates` +
  `emit(DataUpdateFailure(...))`), и только после этого выполняется
  `finally` (сброс `ApiClient` для `farm_rpc`/`r3_rpc`).

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — не человек, само приложение,
инициирующее этот sync-проход автоматически при каждом холодном старте, до
какого-либо ввода пользователя (см. идентичность в
[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)). Человек, находящийся у
устройства в момент отказа — им может быть как гость
([ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md)), так и авторизованный
пользователь ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)), поскольку
`DataUpdateStartAll` диспатчится по `AuthToMain` одинаково для обоих, —
никак не участвует в самом отказе: он лишь видит его результат на
`DataUpdatePage`, вытолкнутой поверх экрана при первом же
`DataUpdateInProgress`. Сами шаги, выполняемые *внутри* прохода при
авторизации (`_syncAuthData`), относятся к
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — этот документ их не
специфицирует заново, только сам факт, что что-то из них может бросить
исключение, не будучи никем перехваченным ниже верхнего уровня.

## CURRENT

### Основной поток

1. Холодный старт приложения → `AuthBloc.on<AuthEventStart>` → эмит
   `AuthToMain` (см. [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) —
   этот шаг там уже специфицирован, здесь не повторяется). `MainPage`'s
   `BlocListener<AuthBloc>` (`lib/pages/main/main_page.dart`) реагирует на
   `AuthToMain` и диспатчит `context.read<DataUpdateBloc>().add(DataUpdateStartAll(again: await getIt<NetworkConnectivityService>().hasConnection(), showDataUpdatePage: true))`.
   Отдельная `BlocListener<DataUpdateBloc>` того же `MainPage` реагирует на
   **любой** `DataUpdateInProgress` вызовом `DataUpdatePage.show(context)` —
   независимо от значения `event.showDataUpdatePage` (см. «Открытые
   вопросы» — это поле нигде не читается).
2. `DataUpdateBloc.on<DataUpdateStartAll>`: `_resetProgressCounters()`
   (пустой метод, `{}`) и безусловный
   `emit(DataUpdateInProgress(progressPercent: 0))` — это тот самый эмит,
   который выталкивает `DataUpdatePage` поверх текущего экрана, ещё до
   какой-либо сетевой проверки.
3. `final isNetworkConnected = await getIt<NetworkConnectivityService>().hasConnection();` —
   `NetworkConnectivityService.hasConnection` делает реальный
   `InternetAddress.lookup('google.com')`, ловит только `SocketException`
   и возвращает `false` в этом случае (любое другое исключение из lookup
   не перехвачено этим методом и всплыло бы отдельно — не покрыто этим
   документом, см. «Открытые вопросы»).
4. **Ветка (а).** Если `!isNetworkConnected`:
   `emit(DataUpdateFailure(errorTitleKey: 'internet_connection_required', errorMessageKey: 'check_connection'))`,
   затем `return;`. Эта строка `return` находится **до** ключевого слова
   `try` в исходном коде метода — значит `try`/`catch`/`finally` целиком
   пропускаются. В частности:
   - `_addDataUpdateError`/`_addDataUpdateSuccess` не вызываются ни разу —
     `DataUpdates` не получает ни одной строки об этом проходе; если в
     таблице уже были строки от предыдущего успешного/частично успешного
     прохода, они остаются как есть (не очищаются — `_clearDataUpdates()`
     находится глубоко внутри `_syncAllData`, до которого выполнение не
     доходит).
   - `getIt<Talker>()` не вызывается ни разу для этого отказа — в отличие
     от ветки (б), здесь нет вообще никакого следа в Talker-логе.
   - `finally`-блок (`await getIt<ApiClient>(instanceName: 'farm_rpc').resetClient('farm_rpc'); await getIt<ApiClient>(instanceName: 'r3_rpc').resetClient('r3_rpc');`)
     **не выполняется** — единственная асимметрия с веткой (б), где тот же
     блок выполняется всегда, независимо от исхода `try`. Прочитано также
     `CustomDioClient.resetClient`
     (`lib/network/api_client/custom_dio_client.dart`) и регистрация в
     `lib/injection_container.dart`: `DioClient` зарегистрирован как
     `registerSingleton` (один и тот же объект на всё время жизни
     процесса), `resetClient` лишь `unregister` + повторно
     `registerLazySingleton` **того же** `CustomDioClient(getIt<DioClient>())`
     — новый объект оборачивает тот же singleton `DioClient` и не хранит
     собственного мутируемого состояния. По прочитанному коду пропуск
     этого вызова в ветке (а) не имеет наблюдаемого функционального
     эффекта — сама операция статически выглядит как замена объекта на
     структурно идентичный, см. «Открытые вопросы» для оговорки.
   - `_currentDataCategory`/`_currentDataKey` (поля инстанса блока) не
     трогаются вовсе на этом проходе — остаются такими, какими были
     оставлены **предыдущим** вызовом `on<DataUpdateStartAll>` (эти два
     поля не сбрасываются между дисптачами события, `_resetProgressCounters`
     их не трогает).
   - Проход заканчивается сразу на состоянии `DataUpdateFailure`; ни
     `loadDirectories`, ни справочники BOARD, ни (при авторизации)
     `_syncAuthData` не запускаются вовсе — в этой ветке не проверяется и
     не обновляется вообще ничего.
5. **Ветка (б).** Если сеть на шаге 3 доступна, выполнение входит в `try`:
   `AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)` →
   `await loadDirectories(event, emit)` → `await _loadBoardDirectories(event, emit, updatedAtGt: directoriesSyncBaseline)` →
   при `_authRepository.isAuthorized()` → `await _syncAuthData(event, emit)` →
   при отсутствии исключений — `emit(DataUpdateSuccess(...))`. Любое из
   трёх перечисленных мест может бросить исключение, которое всплывёт
   наружу без изменений, если внутри нет собственного перехвата, который
   бы его погасил:
   - `loadDirectories` оборачивает своё тело в `try { ... } catch (e) { rethrow; }` —
     чистый passthrough, ничего не меняет, эффективно эквивалентно
     отсутствию `catch` для внешнего наблюдателя.
   - `_loadBoardDirectories` вообще не имеет собственного `try/catch` —
     подтверждено чтением `_boardAdTypesRepository.syncBoardAdTypes`/
     `_boardAdStatusesRepository.syncBoardAdStatuses`/
     `_boardAttributesRepository.syncBoardAttributes`/
     `_boardServiceTypesRepository.syncBoardServiceTypes` (все четыре без
     собственного `try/catch` внутри себя тоже).
   - `_syncAuthData` также не имеет собственного `try/catch` вокруг своих
     вызовов (`_deletePlacesFromRDS`, `_syncFarms`, `_syncPlaces`,
     `storeAnimalWeighingsToSHTP`, `updateAndSyncRegagro`,
     `updateAndSyncSHTP`, `_suncDevices`) — единственные внутренние
     перехваты на этом пути точечные и не относятся к верхнему уровню
     (например, `_syncEditedAnimals` ловит и логирует ошибку на уровне
     одного животного, не перебрасывая её дальше — уже вне периметра
     этого документа).
   Конкретная иллюстрация, проверенная чтением кода: если
   `_countriesRepository.syncCountries(...)` (самый первый вызов внутри
   `loadDirectories`, до какого-либо вызова `_emitProgress`) бросает
   исключение, оно долетает до внешнего `catch` при
   `_currentDataCategory == DataCategory.directories` и `_currentDataKey == ''` —
   оба поля ещё в своих начальных значениях (`_currentDataCategory` явно
   инициализировано `DataCategory.directories` при объявлении поля,
   `_currentDataKey` — пустой строкой), поскольку до этой точки ни один
   `_emitProgress` ещё не выполнился.
6. Внешний `catch (error, stackTrace)` (единственный на весь метод):
   `getIt<Talker>().error('Возникла при обновлении данных $error $stackTrace')`,
   затем `await _emitError(emit: emit, error: error, stackTrace: stackTrace)`.
   `_emitError`: `errorMessage = 'error: $error, stackTrace: $stackTrace'`;
   `await _addDataUpdateError(dataCategory: _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: errorMessage)` —
   пишет одну новую строку в `DataUpdates` (`DataUpdatesCompanion(updatedAt: Value(DateTime.now()), dataCategoryId: Value(dataCategory), errorDataKey: Value(errorDataKey), errorMessage: Value(errorMessage))`);
   затем `emit(DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: _currentDataKey, errorMessage: errorMessage, isAdressesUpdate: isAdressUpdate))` —
   `isAdressUpdate` не передаётся вызывающим кодом ни разу во всём файле,
   всегда остаётся дефолтным `false`.
7. **Записываемые `dataCategoryId`/`errorDataKey` — не обязательно про то
   место, где реально произошло исключение.** `_currentDataCategory`/
   `_currentDataKey` — поля инстанса блока, меняемые только через
   `_emitProgress` (и то не всегда: `dataCategory` — опциональный параметр,
   `_currentDataKey` всегда перезаписывается, `_currentDataCategory` — только
   если `dataCategory != null` передан явно). Значение, которое попадёт в
   ошибочную строку, — это то, что осталось от **последнего успешно
   выполненного** до исключения вызова `_emitProgress`, не обязательно
   от места самого сбоя (тот же механизм, что уже задокументирован для
   перемещений в [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)).
   Конкретно для трёх точек, названных в этом документе:
   - исключение в `_countriesRepository.syncCountries` (самый первый вызов
     `loadDirectories`) → `dataCategoryId = DataCategory.directories`,
     `errorDataKey = ''` (см. шаг 5) — по случайности совпадает с
     реальным местом сбоя, но лишь потому, что это самый первый вызов
     всего прохода;
   - исключение где-либо в `_loadBoardDirectories` (например, в
     `_boardAdTypesRepository.syncBoardAdTypes`) →
     `dataCategoryId = DataCategory.generationsTypes` (оставшееся от
     последнего явного присвоения внутри уже завершившегося
     `loadDirectories`, см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) —
     категория `directories` фактически никогда не записывается по той же
     причине), `errorDataKey = 'board'` (`DataKey.board`, последний
     `_emitProgress` внутри самой `_loadBoardDirectories`) — то есть
     категория `generationsTypes` записывается вместе с ошибкой,
     формально не имеющей отношения к справочникам BOARD;
   - исключение в начале `_syncAuthData` (`_deletePlacesFromRDS`/
     `_syncFarms`/`_syncPlaces`, ни один из которых вызывает
     `_emitProgress`) → те же самые `dataCategoryId = DataCategory.generationsTypes`,
     `errorDataKey = 'board'`, оставшиеся от `_loadBoardDirectories`,
     завершившейся раньше;
   - исключение глубже, внутри `_syncAllData` (вызванного из
     `_syncAuthData` через `updateAndSyncRegagro`) — там снова другие
     значения, оставшиеся от последнего сработавшего внутри `_syncAllData`
     `_emitProgress` (`user`/`syncUnsentAnimals`/`syncSettings`/`syncReports`/
     `reports`/`animals` — например, ровно так, как уже задокументировано
     для перемещений в [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md)).
8. `finally`: `await getIt<ApiClient>(instanceName: 'farm_rpc').resetClient('farm_rpc'); await getIt<ApiClient>(instanceName: 'r3_rpc').resetClient('r3_rpc');` —
   выполняется всегда в ветке (б), независимо от того, был исход `try`
   успехом или обработанным здесь исключением (не выполняется только в
   ветке (а), см. шаг 4).
9. Пользователь видит `DataUpdatePage` в состоянии `DataUpdateFailure`:
   `messageKey = '${AppLocalizations.of(context)!.tr(state.errorTitleKey)}\n${AppLocalizations.of(context)!.tr(state.errorMessageKey)}'`.
   В ветке (а) оба ключа (`internet_connection_required`/`check_connection`)
   явно замаплены в `lib/l10n/app_localization.dart` (`AppLocalizationsExtension.tr`)
   и показываются переведённой строкой на текущем языке. В ветке (б)
   `errorTitleKey = 'an_error_data'` тоже замаплен, но `errorMessageKey`
   (одно из `_currentDataKey` — сырые внутренние ключи вроде `'board'`,
   `'syncSettings'`, `''`) в подавляющем большинстве случаев **не** имеет
   своего `case` в этом же `switch` — `default: return key;` возвращает
   сырой непереведённый ключ как есть (см. «Открытые вопросы»).
   `WillPopScope.onWillPop` возвращает `state is! DataUpdateInProgress` —
   для `DataUpdateFailure` это `true`, то есть системная кнопка "назад"
   позволяет закрыть страницу вручную; автоматического перехода дальше не
   происходит ни в одной из веток.

### Альтернативные потоки

- **`updateAndSyncRegagro` может эмитить `DataUpdateFailure` в обход
  этого механизма целиком — отдельный, здесь не покрываемый путь.**
  Внутри `_syncAuthData` → `updateAndSyncRegagro` есть собственная
  повторная проверка сети (`getIt<NetworkConnectivityService>().hasConnection()`);
  если к этому моменту сеть пропала и при этом `errorDataUpdates.isNotEmpty`
  (или на ветке `event.fullUpdate`), метод сам делает
  `emit(DataUpdateFailure(errorTitleKey: 'internet_connection_required', errorMessageKey: 'check_connection'))`
  и `return` — но это `return` только из `updateAndSyncRegagro`, не
  исключение. Управление возвращается в `_syncAuthData`, которая
  **продолжает** со следующей строки (`await updateAndSyncSHTP(event, emit)`,
  затем `_suncDevices()`) как ни в чём не бывало, и весь `on<DataUpdateStartAll>`
  в итоге всё равно доходит до `emit(DataUpdateSuccess(...))`, если
  дальше ничего не бросит исключение — то есть пользователь может увидеть
  `DataUpdateFailure`, за которым почти сразу последует `DataUpdateSuccess`
  того же прохода. Этот путь не пишет строку в `DataUpdates`
  (`_addDataUpdateError` не вызывается — это не `catch`), и `finally`
  внешнего `try` тоже не имеет к нему отношения (он всё ещё внутри
  внешнего `try`). Это независимый от двух документируемых здесь
  сценариев дефект — упоминается как найденный при чтении кода
  `on<DataUpdateStartAll>`/`updateAndSyncRegagro`, но не специфицируется
  отдельным сценарием этого документа (не входит в заданный периметр «нет
  сети до `try`» / «исключение внутри `try`»); см. «Открытые вопросы».
- **`NetworkConnectivityService.hasConnection` может сама бросить
  исключение, отличное от `SocketException`.** Метод ловит только
  `on SocketException catch (_) {}`; любое другое исключение из
  `InternetAddress.lookup` (например `TimeoutException`, если бы вызов
  был обёрнут таймаутом — в текущем коде не обёрнут) всплыло бы из
  `hasConnection()` необработанным. На шаге 3 (до `try`) это означало бы
  крах `on<DataUpdateStartAll>` **до** входа даже в `try`/`catch` этого
  метода — то есть необработанное исключение bloc-обработчика, не
  покрываемое ни веткой (а), ни веткой (б) этого документа (см.
  «Открытые вопросы»).
- **Гость проходит по тому же верхнему уровню, что и авторизованный
  пользователь.** Обе ветки (а) и (б) идентичны для гостя и
  авторизованного — единственная развилка по авторизации находится
  глубже, на входе в `_syncAuthData` (`if (_authRepository.isAuthorized())`),
  то есть гость никогда не доходит до места, где может сработать
  исключение из `_syncAuthData`, но веткам (а) и исключению из
  `loadDirectories`/`_loadBoardDirectories` это не мешает — они одинаково
  достижимы для гостя.

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  основная сущность сценария. В ветке (а) не получает ни одной строки
  (существующие строки от предыдущего прохода не трогаются и не
  очищаются). В ветке (б) получает ровно одну новую строку через
  `_addDataUpdateError`, с `dataCategoryId`/`errorDataKey`, зависящими от
  того, где именно случилось исключение (см. шаг 7) — не обязательно
  отражающими реальное место сбоя.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) и остальные справочники, читаемые/записываемые внутри
  `loadDirectories` (`Breeds`, `Suits`, `BreedSuits`, `DisposalReasons`,
  `GenerationsTypes`, `AgeGroups`, `MarkerTypes`, `MarkerPlaces`,
  `KindMarkerPlaces`, `AbsenceReasons`, `Countries`, `Vaccines`, `Units`,
  `Diseases`, `ComplexVaccines`, `InjectionPlaces`, `InjectionMethods`,
  `VaccinationTypes`) — при исключении на любом шаге `loadDirectories`
  после какого-либо `clearAndInsertAll`/`insertAll`, но до следующего,
  соответствующая таблица остаётся частично обновлённой (часть
  справочников из списка уже перезаписана новыми данными, часть — нет);
  сама последовательность и списки полей этих таблиц не
  переспецифицируются здесь — уже покрыты `HANDBOOKS`.
  `AppCacheService.saveDirectoriesLastSyncDate` вызывается только в самом
  конце `try`-блока `loadDirectories`, **после** всех перечисленных
  синков — при исключении на любом более раннем шаге `lastSyncDate` не
  обновляется вовсе, и следующий проход снова будет неинкрементальным
  (`isIncremental = lastSyncDate != null` для старого/отсутствующего
  значения), то есть повторно перезагрузит справочники полностью
  (`clearAndInsertAll`), а не по `updatedAtGt`.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD) — справочники
  BOARD (`BoardAdTypes`, `BoardAdStatuses`, `BoardAttributes`,
  `BoardServiceTypes`), синхронизируемые в `_loadBoardDirectories`; при
  исключении на любом из четырёх вызовов оставшиеся не выполняются в этом
  проходе, частично обновлённое состояние остаётся до следующего прохода.
- `Farm`/`Place`/`Animal`/`Movement`/`Vaccination`/`AnimalWeighing`/
  `Disposal`/`Device` (`FARM`/`ANIMAL`/`PROFILE`, уже специфицированы
  отдельно) — при исключении внутри `_syncAuthData` их частичное
  синхронизированное/несинхронизированное состояние на момент сбоя не
  откатывается и не помечается этим сценарием — сам факт возможного
  исключения на этих шагах относится к периметру этого документа только
  как «что-то из перечисленных вызовов бросило», не как отдельная
  спецификация их собственных отказов (уже сделана в `UC-26`/`UC-51`/
  `UC-61`/`UC-90` и аналогичных).

### Бизнес-правила

- Сетевой гейт **один на весь проход** и находится строго до `try` —
  единственный способ добраться до `loadDirectories`/`_syncAuthData`
  вообще — пройти эту проверку; после неё сеть повторно не
  перепроверяется на верхнем уровне (перепроверяется только внутри
  `updateAndSyncRegagro`, см. «Альтернативные потоки»).
  `errorTitleKey`/`errorMessageKey` для отсутствия сети
  (`internet_connection_required`/`check_connection`) — одна и та же
  пара констант, что и во всех прочих местах `DataUpdateBloc`, где
  проверяется сеть.
  `finally` (сброс `ApiClient` `farm_rpc`/`r3_rpc`) выполняется **только**
  если выполнение хотя бы вошло в `try` — ветка (а) эту гарантию
  нарушает, поскольку `return` находится раньше `try`, а не внутри него.
- Оба под-сценария дают один и тот же результат для пользователя —
  переход в `DataUpdateFailure` без какого-либо автоматического повтора
  в рамках этого же вызова обработчика; следующая попытка требует нового
  дисптача `DataUpdateStartAll` (следующий холодный старт — снова
  [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md),
  либо ручной — `EVT-94`, вне периметра этого документа).
- Только ветка (б) оставляет какой-либо след в `DataUpdates` — ветка (а)
  полностью «немая»: ни `Talker`, ни `DataUpdates`, единственное
  наблюдаемое свидетельство — сам факт того, что пользователь видел
  экран ошибки в момент отказа (который исчезает, стоит покинуть
  `DataUpdatePage`).
- `_addDataUpdateError` пишет `dataCategoryId`/`errorDataKey`, отражающие
  состояние счётчика прогресса **на момент исключения**, а не место, где
  оно произошло — тот же принцип, что уже задокументирован в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) и
  [UC-61](UC-61-ACTOR-4-EVT-30-ENT-13-CREATE_ERROR-IN-ANIMAL.md), здесь
  дополнительно подтверждён для трёх мест, специфичных для верхнего
  уровня (`loadDirectories`/`_loadBoardDirectories`/начало `_syncAuthData`).
- Записанная строка `DataUpdates` от ветки (б), если она попала в таблицу
  до следующего прохода (таблица не очищается между проходами, кроме как
  в начале `_syncAllData` того же или следующего прохода), делает
  `errorDataUpdates.isNotEmpty` истинным на следующем вызове
  `updateAndSyncRegagro` — что по [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
  и так уже всегда приводит к полному `_syncAllData()` (сама развилка
  «докат vs полный проход» сломана независимо от этого), но
  дополнительно добавляет фиксированную 15-секундную задержку перед
  повтором.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба под-сценария (отсутствие сети до
`try` и необработанное исключение внутри `try`) воспроизводятся
статическим чтением `DataUpdateBloc.on<DataUpdateStartAll>` целиком, без
необходимости запускать приложение. Возможное исправление (например,
перенос сетевой проверки внутрь `try`, чтобы `finally` выполнялся
единообразно; либо запись в `DataUpdates` реального места сбоя вместо
последнего `_emitProgress`; либо обработка немой ветки (а) в Talker) в
рамках этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | сетевой гейт до `try` (ветка а, `return` до `try`/`finally`); единственный внешний `try/catch/finally` всего прохода (ветка б) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | собирает `errorMessage`, вызывает `_addDataUpdateError`, эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', ...)` — только для ветки (б) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._addDataUpdateError`, `._addDataUpdateSuccess` | CURRENT | единственные точки записи в `DataUpdates`; ни одна не вызывается в ветке (а) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | устанавливает `_currentDataKey` всегда, `_currentDataCategory` только если передан `dataCategory` — значения, которые попадут в ошибочную строку (б), если исключение произойдёт позже |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories`, `._loadBoardDirectories`, `._syncAuthData` | CURRENT | три места, где может возникнуть необработанное исключение сценария (б); ни одно не имеет собственного перехвата на верхнем уровне (`loadDirectories`'s `catch` — чистый `rethrow`) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | собственная повторная проверка сети внутри `_syncAuthData`; при отказе эмитит `DataUpdateFailure` через `return`, не через исключение — не обрывает `_syncAuthData` (см. «Альтернативные потоки») |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.syncCountries` | CURRENT | самый первый вызов внутри `loadDirectories`, конкретная иллюстрация ветки (б) с нетронутыми `_currentDataCategory`/`_currentDataKey` |
| `lib/repositories/board/board_ad_types_repository.dart` | `BoardAdTypesRepository.syncBoardAdTypes` | CURRENT | без собственного `try/catch`; иллюстрация возможного исключения внутри `_loadBoardDirectories` |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | единственный сетевой гейт перед `try`; ловит только `SocketException`, любое другое исключение из `InternetAddress.lookup` не перехвачено этим методом |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.resetClient` | CURRENT | вызывается в `finally` только в ветке (б); `unregister` + повторная регистрация того же `CustomDioClient`, обёртывающего тот же singleton `DioClient` |
| `lib/injection_container.dart` | регистрация `DioClient` (`registerSingleton`) и `ApiClient` `farm_rpc`/`r3_rpc` (`registerLazySingleton`) | CURRENT | `DioClient` — один и тот же объект на весь процесс; `resetClient` не создаёт наблюдаемого функционального отличия по прочитанному коду |
| `lib/pages/main/main_page.dart` | `BlocListener<AuthBloc>` (ветка `AuthToMain`), `BlocListener<DataUpdateBloc>` (ветка `DataUpdateInProgress`) | CURRENT | диспатчит `DataUpdateStartAll(again: hasConnection(), showDataUpdatePage: true)`; показывает `DataUpdatePage` при любом `DataUpdateInProgress`, не читая `event.showDataUpdatePage` |
| `lib/blocs/data_update/data_update_event.dart` | `DataUpdateEvent.showDataUpdatePage` | CURRENT | поле объявлено и передаётся, но не читается нигде ни в `DataUpdateBloc`, ни в `main_page.dart` — мёртвое для этого триггера |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdatePage`, `_DataUpdatePageState.build`, `_Body.build` | CURRENT | рендерит `errorTitleKey`/`errorMessageKey` через `.tr()`; `WillPopScope.onWillPop` разрешает закрытие вручную для любого состояния, кроме `DataUpdateInProgress` |
| `lib/l10n/app_localization.dart` | `AppLocalizationsExtension.tr` | CURRENT | `default: return key;` — необработанные ключи (`'board'`, `'syncSettings'`, `''` и т.д.) отображаются как сырая непереведённая строка |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates`, `DataCategory`, `DataKey` | CURRENT | таблица/enum/константы, записываемые `_addDataUpdateError`; `DataKey.board = 'board'`, прочие ключи — см. класс целиком |

## Критерии приёмки

- Если сеть недоступна (`NetworkConnectivityService.hasConnection()`
  возвращает `false`) в момент старта `on<DataUpdateStartAll>`, метод
  эмитит `DataUpdateFailure(errorTitleKey: 'internet_connection_required', errorMessageKey: 'check_connection')`
  и возвращается **до** входа в `try` — ни `_addDataUpdateError`, ни
  `_addDataUpdateSuccess`, ни `Talker`, ни `finally` (сброс `ApiClient`
  `farm_rpc`/`r3_rpc`) не выполняются.
- Если сеть доступна и исключение возникает где-либо в `loadDirectories`,
  `_loadBoardDirectories` или `_syncAuthData` без собственного перехвата
  ниже (либо перехват — чистый `rethrow`), оно долетает до единственного
  внешнего `catch (error, stackTrace)` метода `on<DataUpdateStartAll>`.
- В этом случае `getIt<Talker>().error(...)` логирует ошибку, затем
  `_emitError` пишет ровно одну новую строку в `DataUpdates`
  (`dataCategoryId`/`errorDataKey`, равные текущим `_currentDataCategory`/
  `_currentDataKey` инстанса блока на момент исключения — не обязательно
  относящимся к месту сбоя) и эмитит
  `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')`.
- В этом случае `finally` (сброс `ApiClient` для `farm_rpc` и `r3_rpc`)
  выполняется всегда, независимо от исхода `try`.
- Ни в одной из двух веток не выполняется автоматический повтор в рамках
  того же вызова обработчика — оба заканчиваются на `DataUpdateFailure`,
  следующая попытка требует нового дисптача `DataUpdateStartAll`.

## Связанные тесты

TBD — теста нет. Единственный существующий тест файла
`test/blocs/data_update_bloc_test.dart` — `blocTest('DataUpdateClear очищает пользовательские данные БД', ...)`
(прямой `blocTest` верхнего уровня, без `group()`, без номера use-case) —
покрывает событие `DataUpdateClear`, не `DataUpdateStartAll`, и не
относится к этому сценарию.

Файл содержит развёрнутый комментарий-дисклеймер прямо перед `void main()`,
объясняющий, почему `DataUpdateStartAll` не покрыт тестом, дословно:
«DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры
getIt<X>() (не через конструктор) — конструктору бЛока нужны ВСЕ они
зарегистрированы, даже для теста одного простого события.
DataUpdateStartAll (~900 из 1013 строк файла — основной sync pipeline) НЕ
покрыт юнит-тестом: первая же строка обработчика — `await hasNetworkConnection()`
(реальный DNS-запрос без DI-точки), дальше десятки приватных методов и
реальные транзакции AppDatabase. Осмысленный юнит-тест такого масштаба
потребовал бы рефакторинга источника под DI — вне рамок написания тестов
без изменения кода. См. TESTING_CHECKLIST.md.» — этот дисклеймер прямо
применим и к обеим веткам этого документа (а тем более к ветке (б),
требующей мокать конкретное исключение из одного из трёх названных
методов). Заметно также, что дисклеймер называет размер файла «1013
строк» — на момент этого прохода файл фактически насчитывает 918 строк
(комментарий не пересматривался после более поздних правок файла; сам
факт непокрытости `DataUpdateStartAll` от этого не меняется).

## Открытые вопросы и ограничения

- **`updateAndSyncRegagro` может эмитить `DataUpdateFailure`, за которым
  почти сразу последует `DataUpdateSuccess` того же прохода** (см.
  «Альтернативные потоки») — это не покрывается ни одной из двух веток
  этого документа (не исключение, не сетевой гейт верхнего уровня), но
  найдено при чтении того же кода и напрямую касается качества сигнала
  `DataUpdateFailure` для пользователя. Заслуживает отдельного
  документирования (собственного use-case), не выполненного здесь, чтобы
  не выходить за периметр, заданный для этого прохода.
- **`event.showDataUpdatePage` — мёртвое поле для обоих триггеров.**
  Ни `DataUpdateBloc`, ни `main_page.dart` его не читают —
  `DataUpdatePage.show` вызывается для любого `DataUpdateInProgress`
  безусловно. Является ли это осознанным упрощением (поле, оставленное
  «на будущее») или забытым остатком более ранней версии кода — нигде в
  комментариях не зафиксировано.
- **`errorMessageKey`, показанный пользователю в ветке (б), в
  большинстве случаев — непереведённый сырой ключ.** `AppLocalizationsExtension.tr`
  не содержит `case` для большинства значений `DataKey`
  (`'board'`, `'syncSettings'`, `'syncDevices'`, `''` и т.д.) — `default: return key;`
  показывает пользователю дословно английский идентификатор ключа вместо
  какого-либо перевода. Аналогичная проблема уже зафиксирована для
  другого экрана в
  [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md)
  («снэкбар показывает "key" вместо перевода») — здесь тот же класс
  дефекта, другой экран.
- **`NetworkConnectivityService.hasConnection` не перехватывает ничего,
  кроме `SocketException`.** Возможное иное исключение из
  `InternetAddress.lookup` привело бы к необработанному краху
  `on<DataUpdateStartAll>` ещё до входа в `try`/`catch` этого метода —
  такой путь прочитанным кодом не закрыт ни одной веткой этого документа
  и не воспроизведён эмпирически (оценка вероятности такого исключения
  на практике вне рамок этой спеки).
- **Пропуск `finally` в ветке (а) — по прочитанному коду не имеет
  наблюдаемого эффекта, но не проверено эмпирически.** `resetClient`
  переоборачивает один и тот же singleton `DioClient` в структурно
  идентичный новый `CustomDioClient`; является ли сам факт замены объекта
  (а не только его состояния) значимым где-либо ещё в приложении
  (например, если что-то удерживает старую ссылку на `ApiClient` дольше
  одного прохода) — статическим чтением этих двух файлов не выяснено до
  конца.
- Не проверено эмпирически на реальном запуске (обрыв сети посреди
  холодного старта, реальное исключение внутри `loadDirectories`/
  `_loadBoardDirectories`/`_syncAuthData`) — оба сценария выведены
  статическим чтением `DataUpdateBloc.on<DataUpdateStartAll>` целиком, а
  также вложенных вызовов, перечисленных в «Технические зависимости».
