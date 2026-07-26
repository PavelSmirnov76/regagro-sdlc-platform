# UC-189 — Ручной запуск полного sync-прохода двумя равнозначными путями («В работе» → «Синхронизировать данные» / экран ошибки → «Попробовать ещё») успешно завершается — но push пользовательских настроек происходит только на одном из них

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Как и зафиксировано в [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
у этого события два равнозначных, независимо диспатчащих один и тот же
`DataUpdateBloc.on<DataUpdateStartAll>` входа: (а) кнопка «Синхронизировать
данные» на экране «В работе» (`InWorkPage`/`EventTilesWidget`,
`DataUpdateStartAll(isUpdateData: true)`) и (б) кнопка на экране ошибки
синхронизации (`DataUpdatePage`, `DataUpdateStartAll(showDataUpdatePage:
false, again: true)`). Этот документ фиксирует **успешное** завершение
полного прохода, инициированного любым из этих двух входов —
`DataUpdateSuccess`, при котором [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
получает новые строки-подтверждения по обработанным категориям.

MOD-7 владеет только верхнеуровневой оркестрацией этого прохода
(`on<DataUpdateStartAll>` целиком) — отдельные push/pull-шаги для
Farm/Place, Movement/Vaccination/AnimalWeighing/Disposal/InventoryScanReport
и настроек сканера уже специфицированы в `FARM`/`ANIMAL`/`PROFILE` (см.
цитаты по ходу «Основной поток») и здесь не переспецифицируются — этот
документ описывает только то, что оркестрация делает **между** этими
уже описанными шагами, и единственную развилку, которую сама оркестрация
вносит: флаг `isUpdateData`, единственный во всей кодовой базе способ
включить `_settingsRepository.setSettingToSHTP()` — push видимости видов
животных и настроек уведомлений о вакцинации на сервер. Прочитано и
перепроверено чтением кода: несмотря на то, что EVT-94 описывает оба входа
как «равнозначные» триггеры одного и того же события, по факту они **не
эквивалентны по эффекту** — `isUpdateData` включён только в пути (а),
путь (б) явно его не передаёт (поле по умолчанию `false`), и это —
единственное различие двух входов, которое реально на что-то влияет (см.
«Открытые вопросы»).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
как и закреплено в [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md).
Оба входа этого документа доступны только из экранов, физически связанных с
уже идущим или ранее запущенным полным sync-проходом: «В работе»
(`lib/pages/in_work/in_work_page.dart`, вложен под `Routes.profile` shell
branch) и `DataUpdatePage` (`lib/pages/data_update/data_update_page.dart`,
полноэкранная страница поверх `rootNavigator`, показываемая
`main_page.dart`'s `BlocListener<DataUpdateBloc>` при любом переходе в
`DataUpdateInProgress`). Дальше, после нажатия кнопки, весь проход идёт
автоматически — без участия пользователя на уровне отдельного сетевого
вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)
(тот актор используется этим же кодом внутри `_syncAuthData`/`_syncAllData`,
но не в самом факте запуска — запуск здесь явно человеческий, ACTOR-1).

## CURRENT

### Основной поток

1. **Путь (а).** Пользователь на экране «В работе» нажимает
   `BlackCircleButton` с текстом `AppLocalizations.of(context)!.sync_data`
   (`app_ru.arb`: `"sync_data": "Синхронизировать данные"`) —
   `lib/pages/in_work/in_work_page.dart`, `EventTilesWidget.build`:
   `context.read<DataUpdateBloc>().add(const DataUpdateStartAll(isUpdateData:
   true))`. Остальные поля события — значения по умолчанию:
   `showDataUpdatePage: true`, `again: false`, `fullUpdate: false`,
   `isAfterRegistration: false`, `resetNavigationOnSuccess: false`.
2. **Путь (б), альтернативный вход в тот же обработчик.** Пользователь на
   уже открытом экране ошибки синхронизации (`DataUpdatePage`, состояние
   `DataUpdateFailure`, полученное из предыдущего неуспешного прохода — не
   часть этого документа) нажимает `BlackCircleButton.secondary` с текстом
   `AppLocalizations.of(context)!.try_again` (`app_ru.arb`: `"try_again":
   "Попробовать ещё"` — не «Повторить», как перефразирует прозу самого
   [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md);
   см. «Открытые вопросы») —
   `lib/pages/data_update/data_update_page.dart`,
   `_DataUpdateInProgressWidgetState.build`: `context.read<DataUpdateBloc>().add(
   const DataUpdateStartAll(showDataUpdatePage: false, again: true))`.
   `isUpdateData` здесь не передаётся — остаётся `false`.
3. В обоих случаях `DataUpdateBloc` — синглтон, зарегистрированный один раз
   на уровне всего приложения (`lib/main.dart`:
   `BlocProvider<DataUpdateBloc>(create: (context) => DataUpdateBloc())`,
   выше `go_router`), поэтому оба экрана управляют одним и тем же
   `on<DataUpdateStartAll>`.
4. `on<DataUpdateStartAll>` (`lib/blocs/data_update/data_update_bloc.dart`):
   сбрасывает счётчики прогресса (`_resetProgressCounters()` — пустая
   функция, см. «Открытые вопросы»), эмитит `DataUpdateInProgress(progressPercent:
   0)`, затем проверяет сеть —
   `getIt<NetworkConnectivityService>().hasConnection()`. В этом сценарии
   сеть есть (иначе — `DataUpdateFailure` немедленно, до входа в `try`, что
   не является предметом этого документа).
5. Начинается общий `try`. `directoriesSyncBaseline =
   AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
   читается **до** запуска справочников — единый снимок момента начала
   прохода, разделяемый между HANDBOOKS- и BOARD-справочниками.
6. `await loadDirectories(event, emit)` — [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md),
   уже специфицировано: синхронизирует ~18 справочников HANDBOOKS
   (включая [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md), Kind/Breed/Suit
   и т.д.), безусловно для любого актора. В этом сценарии все сетевые
   вызовы внутри успешны. Завершается `await
   _addDataUpdateSuccess(_currentDataCategory)` — из-за известного дефекта,
   уже задокументированного в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
   («категория `directories` фактически никогда не записывается»),
   `_currentDataCategory` к этому моменту равен `DataCategory.generationsTypes`,
   не `directories` — в таблицу `DataUpdates` вставляется одна строка с
   категорией `generationsTypes`. Эта строка, как показано на шаге 10,
   переживает лишь короткое время — она будет стёрта тем же самым проходом,
   ещё до его завершения (см. «Открытые вопросы» — уточнение, не
   зафиксированное в самом [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)).
7. `await _loadBoardDirectories(event, emit, updatedAtGt:
   directoriesSyncBaseline)` — [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md),
   уже специфицировано: синхронизирует 4 справочника BOARD
   ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), тоже безусловно. Не
   пишет собственной строки в `DataUpdates`.
8. `if (_authRepository.isAuthorized()) await _syncAuthData(event, emit);` —
   в этом сценарии пользователь авторизован (см. «Пользователь»), ветка
   выполняется. `_syncAuthData` — уже специфицированная для отдельных
   сущностей (см. ниже), здесь описывается только сама
   последовательность вызовов:
   - `await _deletePlacesFromRDS()`, `await _syncFarms()`, `await
     _syncPlaces()` — [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md),
     уже специфицированы (успешные варианты —
     [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md),
     [UC-27](UC-27-ACTOR-4-EVT-13-ENT-9-UPDATE_OK-IN-FARM.md),
     [UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md),
     [UC-37](UC-37-ACTOR-4-EVT-18-ENT-10-CREATE_OK-IN-FARM.md),
     [UC-39](UC-39-ACTOR-4-EVT-19-ENT-10-UPDATE_OK-IN-FARM.md),
     [UC-41](UC-41-ACTOR-4-EVT-20-ENT-10-DELETE_OK-IN-FARM.md),
     [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md)). В этом
     сценарии все успешны.
   - `await _animalWeighingsRepository.storeAnimalWeighingsToSHTP()` —
     [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), уже
     специфицировано ([UC-89](UC-89-ACTOR-4-EVT-45-ENT-15-CREATE_OK-IN-ANIMAL.md)
     успешно, [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md) —
     сам метод глотает свои ошибки и никогда не бросает исключение, так что
     этот шаг не может сорвать оставшийся проход независимо от исхода). В
     этом сценарии батч успешно принят сервером.
   - `await updateAndSyncRegagro(event, emit)` — читает текущее содержимое
     `DataUpdates` (на этот момент — одна строка `generationsTypes` с шага
     6), вычисляет `errorDataUpdates` и `dataUpdates.length <
     _totalDataUpdatesCount` (9). Как задокументировано в
     [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), это условие
     **всегда истинно** (реально в таблице никогда не набирается 9 строк) —
     ветка `event.fullUpdate`/`updateAnimals` (инкрементальная перезагрузка
     животных) структурно недостижима. И `event.again` (`false` в пути (а),
     `true` в пути (б)) здесь не имеет значения: `event.again` — лишь один
     из трёх операндов `||`, а условие истинно независимо от него из-за
     второго операнда. Проход всегда идёт по ветке `await
     _syncAllData(event, emit)`.
9. **`_syncAllData(event, emit)`** — сердце этого документа:
   - `await _clearDataUpdates()` — `_dataUpdatesRepository.clear()`
     стирает **всю** таблицу `DataUpdates`, включая единственную строку
     `generationsTypes`, вставленную на шаге 6 этим же проходом несколькими
     секундами раньше. См. «Открытые вопросы» — это уточняет
     [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) сильнее, чем
     зафиксировано в самой сущности.
   - `await loadUser(event, emit)` — `_authRepository.updateUserData()`
     успешен, затем `await _addDataUpdateSuccess(_currentDataCategory)` —
     `_currentDataCategory` только что установлен в `DataCategory.user`
     внутри `_emitProgress` этого же метода. Первая строка,
     переживающая проход: категория `user`.
   - `_emitProgress(dataKey: DataKey.syncUnsentAnimals, dataCategory:
     DataCategory.syncUnsentAnimals)` (только смена прогресс-текста, без
     записи в `DataUpdates` — категория `syncUnsentAnimals` никогда не
     подтверждается отдельной строкой, см.
     [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)), затем `await
     syncAllUnsentAnimals()` → `_syncAllLocalAnimals()` —
     [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal), синк
     каждого ещё не отправленного локального животного (`id < 0`) через
     `AnimalsRepository.syncLocalAnimal`, уже специфицировано (успешный
     вариант — [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md)).
     В этом сценарии успешно для всех локальных животных, если они есть; при
     их отсутствии цикл просто не выполняет итераций.
   - `_emitProgress(dataKey: DataKey.syncSettings)` — **без** `dataCategory`
     (прогресс-текст меняется, `_currentDataCategory` не трогается — всё ещё
     `user`).
   - **Развилка, отличающая путь (а) от пути (б):** `final isUpdateData =
     event is DataUpdateStartAll && event.isUpdateData;` — `true` для пути
     (а) (шаг 1), `false` для пути (б) (шаг 2). `if (isUpdateData) { await
     _settingsRepository.setSettingToSHTP(); }` — **только путь (а)**
     доходит до этого вызова. `setSettingToSHTP` (`lib/repositories/settings/settings_repository.dart`):
     читает локальные `ProfileSetting` (`getProfileSettings()`) и видимые
     `kindId`'ы (`_getVisibleKindIds()` →
     `_kindsRepository.getAllIdsByFilters(visible: true)`,
     [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)); если список
     видимых видов пуст — логирует через `Talker.info` и возвращается без
     сетевого вызова (не наступает в этом сценарии, где виды выбраны); иначе
     собирает `Settings(settings: SettingsMap(visibleKinds: ...,
     daysToVaccination: ..., sendVaccinationNotificationOnEmail: ...))` и
     `POST ${Constants.farmServiceApi}/user-settings/store` через
     `rpcClient.call(message)` — в этом сценарии успешно. Путь (б) этот
     блок целиком пропускает — ни один сетевой вызов на этом шаге не
     происходит.
   - `await _settingsRepository.getSettingFromSHTP()` — **выполняется в
     обоих путях**, независимо от `isUpdateData`: `GET
     ${Constants.farmServiceApi}/user-settings/get-settings`, обёрнут в
     собственный `try { ... } on DioException catch (e) { ... }` —
     применяет полученные настройки (`_setVisibleKinds`,
     `_setProfileSettingsFromApi`) поверх локальных
     [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)/`ProfileSetting`. В
     этом сценарии успешен.
   - `await _movementReportRepository.syncMovements()` —
     [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), уже
     специфицировано (успешный вариант —
     [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md)).
   - `await _disposalRepository.syncDisposals()` —
     [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), уже
     специфицировано (успешный вариант —
     [UC-105](UC-105-ACTOR-4-EVT-53-ENT-16-CREATE_OK-IN-ANIMAL.md)).
   - `await _syncEditedAnimals()` — `AnimalsRepository.getAllNeedsUpdate()` →
     `updateAnimal` на каждой правке синхронизированного животного
     ([ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), `needsUpdate ==
     true`) — уже специфицировано отдельно от этого прохода
     ([UC-52](UC-52-ACTOR-4-EVT-26-ENT-11-UPDATE_OK-IN-ANIMAL.md)).
   - `await loadAnimals(event, emit)` — очищает и полностью перезагружает
     `Animals`/идентификации/синхронизированные взвешивания с сервера
     (`syncAllAnimals()`), затем `await
     _addDataUpdateSuccess(_currentDataCategory)` —
     `_currentDataCategory` установлен в `DataCategory.animals` этим же
     методом. Вторая переживающая строка: категория `animals`.
   - `await _vaccinationsRepository.syncVaccinations(true)` —
     [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), уже
     специфицировано (успешные варианты —
     [UC-69](UC-69-ACTOR-4-EVT-35-ENT-14-DELETE_OK-IN-ANIMAL.md),
     [UC-71](UC-71-ACTOR-4-EVT-36-ENT-14-UPDATE_OK-IN-ANIMAL.md),
     [UC-73](UC-73-ACTOR-4-EVT-37-ENT-14-CREATE_OK-IN-ANIMAL.md),
     [UC-75](UC-75-ACTOR-4-EVT-38-ENT-14-READ_OK-IN-ANIMAL.md)).
   - `_syncAllData` возвращается без исключения — `updateAndSyncRegagro`,
     следовательно `_syncAuthData`, продолжают.
10. Обратно в `_syncAuthData`, после `updateAndSyncRegagro`: `await
    updateAndSyncSHTP(event, emit)` — `_emitProgress(dataKey:
    DataKey.syncReports, dataCategory: DataCategory.syncReports)`, затем
    push готовых к отправке инвентаризационных сессий
    (`_unsentReportsRepository.getAllReadyToSend()`/`.sync(...)`,
    [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), уже
    специфицировано — успешный вариант
    [UC-125](UC-125-ACTOR-4-EVT-63-ENT-17-CREATE_OK-IN-ANIMAL.md)), очистка
    локального кэша отчётов и `deleteAllReadyToSend()`, затем `await
    loadShtp(emit)` — пересобирает `_currentDataCategory` в
    `DataCategory.reports` внутри своей же `_emitProgress`, тянет отчёты с
    сервера ([UC-127](UC-127-ACTOR-4-EVT-64-ENT-17-READ_OK-IN-ANIMAL.md)) и
    вызывает `await _addDataUpdateSuccess(_currentDataCategory)` — третья и
    последняя переживающая строка: категория `reports`.
11. `_emitProgress(dataKey: DataKey.syncDevices)`, затем `await
    _suncDevices()` — [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), уже
    специфицировано в PROFILE (`ensureDeviceInDatabase`,
    `updateDevicesOnSHTP`, `fetchDevicesFromApi`,
    `syncDevicesOnSHTP`/`clearAndInsertAll`, затем
    `getIt<ScannerService>().applySavedTerminalSettings()`). Не пишет строк в
    `DataUpdates`.
12. `_syncAuthData` возвращается без исключения. `on<DataUpdateStartAll>`
    эмитит `emit(DataUpdateSuccess(resetNavigationOnSuccess:
    event.resetNavigationOnSuccess))` — `resetNavigationOnSuccess` равен
    `false` в обоих путях этого документа (ни один из двух дispatch'ей его
    не передаёт). `finally`-блок сбрасывает оба RPC-клиента
    (`ApiClient(instanceName: 'farm_rpc'/'r3_rpc').resetClient(...)`)
    независимо от исхода.
13. **Итоговое содержимое [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
    после этого прохода — ровно 3 строки: `user`, `animals`, `reports`.**
    Строка `generationsTypes` с шага 6 в финальном снимке отсутствует — она
    была стёрта на шаге 9 тем же самым проходом, который её создал. Ни
    `syncUnsentAnimals`, ни `syncDisposalListService`, ни `generations`
    никогда не фиксируются отдельными строками успеха вообще (см.
    [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) — это
    подтверждается и здесь, для этого конкретного, полностью успешного,
    авторизованного прохода.
14. **UI-эффекты успеха, одинаковые для обоих путей.** `main_page.dart`'s
    `BlocListener<DataUpdateBloc, DataUpdateState>` не реагирует на
    `DataUpdateSuccess` напрямую (только на `DataUpdateInProgress`, чтобы
    открыть страницу) — реакцию на успех несёт сам `DataUpdatePage`
    (который уже открыт к этому моменту в обоих путях — в пути (а) он был
    открыт этим же переходом в `DataUpdateInProgress` на шаге 4, в пути (б)
    он уже был открыт с прошлого неуспешного прохода): его собственный
    `BlocConsumer.listener` на `DataUpdateSuccess` — `Navigator.of(context).pop()`,
    затем безусловно `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage:
    true))` ([EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md),
    [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md); no-op вне
    prod-сборки — `if (!Constants.isProd) return;`), затем, так как
    `state.resetNavigationOnSuccess == false` в обоих путях —
    `context.go(Routes.mainNavigator)`. Пользователь в итоге оказывается на
    экране «Ферма/место» (`MainNavigatorPage`), а не остаётся на экране, с
    которого запускал синк («В работе» или экран ошибки).
15. `MainNavigatorPage`'s собственный `BlocListener<DataUpdateBloc,
    DataUpdateState>` реагирует на тот же `DataUpdateSuccess` вызовом
    `context.read<MainNavigatorCubit>().load()` — перезагружает список ферм
    (только что перезаписанный шагом 8), поэтому именно на этом экране
    видно наиболее прямое подтверждение успеха.
16. `InWorkBloc` (если экран «В работе» ещё смонтирован — актуально для
    пути (а), откуда пользователь только что ушёл шагом 14) реактивно
    отражает опустошение локальных таблиц, произошедшее этим же проходом —
    его подписки (`watchCountLocalAnimalsToCreate`, `watchCountNotSync` для
    взвешиваний/вакцинаций/выбытий, `watchNotSyncMovements`,
    `watchInventorySessionCount`) — Drift-стримы поверх тех же таблиц,
    которые шаги 8–11 только что очистили/пересинхронизировали; счётчики на
    плитках экрана «В работе» падают сами, без отдельного события.

### Альтернативные потоки

- **Путь (б) без `isUpdateData`.** Как показано на шаге 9 «Развилка», путь
  (б) выполняет весь тот же `_syncAllData`, кроме одного вызова
  (`setSettingToSHTP()`), — включая `getSettingFromSHTP()` (пассивный pull
  настроек, не push). Итоговое содержимое [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
  и вся остальная последовательность (шаги 6–13, 15, 16) идентичны пути
  (а). Единственное наблюдаемое отличие «снаружи» — на сервере не
  появляется/не обновляется запись `user-settings` за этот конкретный
  проход.
- **Неавторизованный (гостевой) вызов той же кнопки — структурно не
  исключён кодом, за рамками этого документа.** `ProfileView`
  (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`)
  показывает кнопку «В работе» без видимой проверки
  `_authRepository.isAuthorized()` в прочитанном коде — то есть гость,
  вероятно, тоже может дойти до экрана «В работе» и нажать
  «Синхронизировать данные». Если так, `_authRepository.isAuthorized()` на
  шаге 8 ложно, `_syncAuthData` не выполняется вовсе — весь этот документ
  (шаги 8–16) не наступает, доходит только до `loadDirectories`/`_loadBoardDirectories`
  (шаги 6–7), затем сразу `DataUpdateSuccess`. `isUpdateData: true` в этом
  случае не имеет вообще никакого эффекта, так как ветка, где он
  проверяется, физически не достигается. Реальная достижимость этого пути
  для гостя этим документом не проверялась глубже (не по коду UI-роутинга
  за пределами `profile_view.dart`/`routes.dart`) — [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)
  закрепляет инициатора как [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), и
  этот документ следует этому, не оспаривая.
- **Ошибка на любом шаге 6–11 — не этот документ.** Любое исключение,
  всплывшее из шагов 6–11 (включая ветку `isUpdateData`, см. «Открытые
  вопросы» — `setSettingToSHTP()` не имеет собственного `try/catch`),
  перехватывается общим `catch (error, stackTrace)` `on<DataUpdateStartAll>`
  и ведёт к `DataUpdateFailure`, а не к `DataUpdateSuccess` этого
  документа — отдельный, здесь не описываемый результат
  (`CREATE_ERROR`).

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  сущность, чьи строки создаются этим сценарием: одна transient-строка
  `generationsTypes` (стирается тем же проходом), три переживающие —
  `user`, `animals`, `reports` (см. шаги 6, 9, 10, 13).
- [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion) —
  не читается/не пишется этим сценарием напрямую, но `DataUpdateSuccess`
  безусловно запускает проверку обновления приложения (шаг 14),
  специфицированную отдельно как [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md).
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)
  (Place) — синхронизируются как часть `_syncAuthData` (шаг 8); уже
  специфицированы в FARM, не переспецифицируются здесь.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — синхронизация
  локальных (`id < 0`) и отредактированных (`needsUpdate`) животных, затем
  полная перезагрузка с сервера — всё в рамках `_syncAllData` (шаг 9); уже
  специфицировано в ANIMAL.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement),
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination),
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)
  (AnimalWeighing), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)
  (Disposal), [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — все пять пушатся/подтягиваются как часть этого же
  прохода (шаги 8, 9, 10); каждая уже специфицирована отдельно в ANIMAL,
  здесь только упомянута как часть общей последовательности.
- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) —
  синхронизируется последним шагом `_syncAuthData` (шаг 11); уже
  специфицирован в PROFILE.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) — читается/пишется дважды в рамках этого прохода: как часть
  `loadDirectories()` (шаг 6, полная под-область HANDBOOKS) и как часть
  push/pull настроек (шаг 9 — `visibleKinds`, только узкая грань
  «видимость вида»); ENT-3 не редактируется этим модулем, только
  переиспользуется.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD) —
  справочники объявлений синхронизируются как часть `_loadBoardDirectories`
  (шаг 7); ENT-18 не редактируется этим модулем.

### Бизнес-правила

- `isUpdateData` — единственный флаг во всей кодовой базе, включающий push
  пользовательских настроек (`SettingsRepository.setSettingToSHTP`) на
  сервер; он привязан намеренно к ручному запуску из «В работе» (путь (а))
  и намеренно **не** передаётся ни автоматическим запуском при старте
  ([EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)),
  ни ретраем на экране ошибки (путь (б) этого документа), ни любым из
  оставшихся мест диспатча `DataUpdateStartAll`
  (`profile_settings_view.dart`).
- Развилка «докат прерванного прохода vs полный `_syncAllData`»
  (`updateAndSyncRegagro`) структурно сломана и всегда выбирает полный
  проход — задокументировано в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md);
  следствие для этого документа — `event.again` (единственное поле,
  формально различающее путь (а) от пути (б) помимо `isUpdateData`) не
  оказывает никакого наблюдаемого эффекта ни на один из двух путей.
- Полностью успешный авторизованный проход всегда стирает собственную же
  «справочную» строку `DataUpdates` (категория `generationsTypes`,
  ошибочно замещающая `directories`), потому что `_clearDataUpdates()`
  находится **внутри** `_syncAllData`, вызываемого позже той же строки —
  финальное содержимое таблицы после успешного авторизованного прохода
  всегда ровно `{user, animals, reports}`, никогда 4 категории.
- Успешное завершение прохода не оставляет пользователя на экране, с
  которого он его запустил — оба пути этого документа безусловно
  перенаправляют на `Routes.mainNavigator` (экран «Ферма/место»), потому что
  ни один из них не передаёт `resetNavigationOnSuccess: true`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Оба пути (кнопка «В работе» и кнопка
экрана ошибки), вся последовательность `on<DataUpdateStartAll>` для
авторизованного пользователя и итоговое содержимое `DataUpdates`
прослежены статическим чтением кода целиком: `in_work_page.dart`/
`data_update_page.dart` → `DataUpdateBloc.on<DataUpdateStartAll>` →
`_syncAuthData` → `updateAndSyncRegagro` → `_syncAllData` →
`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`. Не проверено
эмпирически на реальном запуске против настоящего бэкенда.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `EventTilesWidget.build` (`BlackCircleButton`, `l10n.sync_data`) | CURRENT | путь (а) — диспатчит `DataUpdateStartAll(isUpdateData: true)` |
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdateInProgressWidgetState.build` (`BlackCircleButton.secondary`, `l10n.try_again`) | CURRENT | путь (б) — диспатчит `DataUpdateStartAll(showDataUpdatePage: false, again: true)` |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdatePage.show`, `_isPageOpen` | CURRENT | реальный (единственный действующий) guard от повторного открытия страницы; независим от `event.showDataUpdatePage` |
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdatePageState.build` (`BlocConsumer<DataUpdateBloc, DataUpdateState>.listener`) | CURRENT | реакция на `DataUpdateSuccess`: `Navigator.pop`, `AppUpdateEventCheckUpdate`, условная навигация на `Routes.mainNavigator` |
| `lib/pages/main/main_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | открывает `DataUpdatePage` при `DataUpdateInProgress`, не читая `event.showDataUpdatePage` |
| `lib/main.dart` | `BlocProvider<DataUpdateBloc>` | CURRENT | единственный экземпляр `DataUpdateBloc` на всё приложение, выше `go_router` |
| `lib/blocs/data_update/data_update_event.dart` | `DataUpdateEvent`, `DataUpdateStartAll` (`isUpdateData`, `again`, `showDataUpdatePage`, `resetNavigationOnSuccess`) | CURRENT | поля события; `showDataUpdatePage` и `isAfterRegistration` нигде не читаются, `again` читается один раз внутри всегда-истинного условия |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | верхнеуровневая оркестрация: сеть → `loadDirectories` → `_loadBoardDirectories` → (если авторизован) `_syncAuthData` → `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData`, `.updateAndSyncRegagro`, `._syncAllData`, `.updateAndSyncSHTP`, `._suncDevices` | CURRENT | полная авторизованная часть прохода; `updateAndSyncRegagro` всегда выбирает `_syncAllData` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._clearDataUpdates`, `._addDataUpdateSuccess`, `.loadUser`, `.loadAnimals`, `.loadShtp`, `.loadDirectories` | CURRENT | единственные писатели/читатели `DataUpdates` за этот проход |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.setSettingToSHTP`, `.getSettingFromSHTP` | CURRENT | push (только путь (а), без собственного `try/catch`) / pull (оба пути, ловит `DioException`) настроек |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates`, `DataCategory`, `DataKey` | CURRENT | таблица журнала, категории, ключи прогресса |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository.clear`, `.insert`, `.getAll` | CURRENT | тонкая обёртка, используемая шагами 6, 9, 10, 13 |
| `lib/pages/main_navigator/main_navigator_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` → `MainNavigatorCubit.load` | CURRENT | видимый эффект успеха на экране «Ферма/место» |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (реактивные `Stream`-подписки) | CURRENT | счётчики «В работе» реактивно отражают опустошение локальных таблиц этим же проходом |
| `lib/blocs/app_update/app_update_bloc.dart` | `AppUpdateBloc.on<AppUpdateEventCheckUpdate>` | CURRENT | безусловно запускается листенером `DataUpdatePage` после успеха; `if (!Constants.isProd) return;` |

## Критерии приёмки

- Оба входа — `DataUpdateStartAll(isUpdateData: true)` (путь а) и
  `DataUpdateStartAll(showDataUpdatePage: false, again: true)` (путь б) —
  проходят через один и тот же `on<DataUpdateStartAll>` и при успешной сети
  на всех сетевых шагах завершаются `emit(DataUpdateSuccess(resetNavigationOnSuccess:
  false))`.
- Только путь (а) вызывает `SettingsRepository.setSettingToSHTP()` внутри
  `_syncAllData`; путь (б) этот вызов пропускает целиком, при этом
  выполняя `getSettingFromSHTP()` в обоих случаях.
- После полностью успешного авторизованного прохода таблица `DataUpdates`
  содержит ровно три строки без ошибки — категории `user`, `animals`,
  `reports`; строка `generationsTypes`, вставленная в начале того же
  прохода `loadDirectories()`, в финальном снимке отсутствует (стёрта
  `_clearDataUpdates()` внутри `_syncAllData` того же прохода).
- `event.again` (`false` в пути а, `true` в пути б) не меняет, какая ветка
  `updateAndSyncRegagro` выполняется — обе всегда доходят до
  `_syncAllData`.
- После `DataUpdateSuccess` пользователь в обоих путях оказывается на
  `Routes.mainNavigator`, а не на экране, откуда был инициирован синк;
  `MainNavigatorCubit.load()` и реактивные подписки `InWorkBloc`
  синхронно отражают результат прохода без отдельного явного обновления.
- `AppUpdateEventCheckUpdate(showModalMessage: true)` диспатчится
  безусловно после любого `DataUpdateSuccess` из `DataUpdatePage`,
  независимо от того, каким из двух путей проход был запущен.

## Связанные тесты

TBD — теста нет ни на один из двух путей и ни на `isUpdateData`-развилку.

`test/blocs/data_update_bloc_test.dart` — единственный тестовый файл для
`DataUpdateBloc` — содержит развёрнутый комментарий-дисклеймер, который
прямо объясняет, почему: «DataUpdateBloc инжектирует >25 репозиториев через
поля-геттеры getIt<X>() (не через конструктор) — конструктору бЛока нужны
ВСЕ они зарегистрированы, даже для теста одного простого события.
DataUpdateStartAll (~900 из 1013 строк файла — основной sync pipeline) НЕ
покрыт юнит-тестом: первая же строка обработчика — `await
hasNetworkConnection()` (реальный DNS-запрос без DI-точки), дальше десятки
приватных методов и реальные транзакции AppDatabase. Осмысленный юнит-тест
такого масштаба потребовал бы рефакторинга источника под DI — вне рамок
написания тестов без изменения кода.» Единственный реальный тест в этом
файле — `blocTest('DataUpdateClear очищает пользовательские данные БД', ...)`
(прямой `blocTest` верхнего уровня, не внутри `group()`) — покрывает
`DataUpdateClear`, отдельное от `DataUpdateStartAll` событие, не относящееся
к этому сценарию.

`test/pages/data_update_page_test.dart` покрывает только
`DataUpdatePage.show()` защиту от повторного открытия
(`group('DataUpdatePage.show() — защита от повторного открытия')`) через
`MockDataUpdateBloc` — не диспатч конкретных `DataUpdateStartAll`-вариантов
и не нажатие кнопки «Попробовать ещё».

`test/pages/in_work_bloc_test.dart` покрывает реактивные подписки и
дедупликацию перемещений `InWorkBloc`
(`group('UC-197 — InWorkBloc реактивные подписки')`,
`group('UC-197 — InWorkBloc дедупликация перемещений')`) — не сам
`InWorkPage`-виджет и не нажатие кнопки «Синхронизировать данные».

## Открытые вопросы и ограничения

- **`showDataUpdatePage` — мёртвое поле.** Объявлено на `DataUpdateEvent`,
  передаётся явно (`false`) только в пути (б), но нигде в коде не
  читается — ни в `DataUpdateBloc`, ни в `main_page.dart`'s
  `BlocListener<DataUpdateBloc>` (который открывает страницу по самому
  факту состояния `DataUpdateInProgress`, независимо от того, каким
  событием оно было вызвано). Единственный механизм, реально
  предотвращающий повторное открытие страницы при путях (б) — статический
  `DataUpdatePage._isPageOpen`, целиком независимый от этого поля события.
  Является ли `showDataUpdatePage: false` в пути (б) намеренной, но
  фактически недействующей документацией намерения, или переживший
  рефакторинг остаток — ничем в коде не зафиксировано.
- **`event.again` читается ровно один раз** — внутри условия
  `updateAndSyncRegagro`, которое, как задокументировано в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), истинно всегда
  независимо от этого флага. Формально путь (б) передаёт `again: true`,
  путь (а) — implicit `false`; на наблюдаемое поведение это не влияет.
- **`isAfterRegistration`** объявлено на `DataUpdateStartAll`, включено в
  `Equatable.props`, но не читается ни в одном методе `DataUpdateBloc`
  (`grep -rn "isAfterRegistration" lib/` находит только объявление и
  использование в `props`) — ни один из живых мест диспатча (включая оба
  пути этого документа) его не передаёт. Не относится напрямую к
  сценарию этого документа, но обнаружено при полной проверке всех полей
  события.
- **`setSettingToSHTP()` не имеет собственного `try/catch`, и вызывающий
  код (`_syncAllData`) тоже не оборачивает этот конкретный вызов** — в
  отличие от соседнего `getSettingFromSHTP()` (тот же файл), который явно
  ловит `DioException`. Поскольку эта ветка достижима только в пути (а)
  (`isUpdateData: true`), сетевой сбой именно на этом шаге — единственный
  во всём документе способ, которым **успешно начавшийся** путь (а)
  (сеть была доступна на шаге 4) мог бы всё же сорваться и прервать
  оставшуюся часть прохода (`getSettingFromSHTP`, движения/выбытия,
  правки животных, `loadAnimals`, вакцинации, `updateAndSyncSHTP`,
  `_suncDevices`) целиком — необработанное исключение всплыло бы до
  внешнего `catch` `on<DataUpdateStartAll>`, дав `DataUpdateFailure`
  вместо `DataUpdateSuccess`. Сам этот отказ (`CREATE_ERROR`) — не предмет
  этого документа (он про успешный путь), но заслуживает отдельного
  прохода документирования; путь (б), не имеющий этой ветки вовсе, этому
  конкретному риску не подвержен.
- **Прогресс-текст во время `DataUpdateInProgress` — не переведённая
  пользователю строка.** `DataUpdateInProgressWidget.build`
  (`data_update_page.dart`) рендерит `widget.messageKey` (== `_currentDataKey`,
  сырое значение `DataKey.*`, например `'kinds'`, `'breeds'`,
  `'syncSettings'`, `'animals'`) напрямую через `Text(widget.messageKey,
  ...)`, **без** `AppLocalizations.of(context)!.tr(...)` — в отличие от
  ветки `DataUpdateFailure` того же файла, которая явно транслирует оба
  ключа (`tr(state.errorTitleKey)`/`tr(state.errorMessageKey)`).
  Пользователь в течение всего прохода (оба пути этого документа) в
  прямом смысле видит на экране английские camelCase-идентификаторы, а не
  человекочитаемый текст статуса.
- **`DataUpdateInProgress.progressPercent` всегда `0`.**
  `DataUpdateBloc._getProgressPercent()` — жёстко `=> 0;`,
  `_resetProgressCounters()` — пустое тело; поле не используется ни для
  какой логики и не отображается нигде в `DataUpdateInProgressWidget`
  (нет ни числового процента, ни прогресс-бара) — полностью
  вестигиальный механизм для этого (и любого другого) прохода.
- **Гостевая достижимость кнопки «В работе» → «Синхронизировать данные»
  не проверена до конца.** См. «Альтернативные потоки» — `profile_view.dart`
  не показывает явной проверки `isAuthorized()` вокруг кнопки «В работе» в
  прочитанном коде. Если гость всё же может дойти до этой кнопки, флаг
  `isUpdateData: true` не имеет никакого эффекта (ветка `_syncAuthData` не
  достигается вовсе) — но эта ветка UI-роутинга (гейтится ли навигация
  выше по дереву, например на уровне вкладок) этим документом не
  прослежена до конца.
- **Расхождение между прозой [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)
  и реальным текстом кнопки.** Замороженный текст события называет кнопку
  экрана ошибки «Повторить»; реальный ключ локализации, использованный в
  коде (`app_ru.arb`, `try_again`), — «Попробовать ещё». Эта спека не
  правит замороженный [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
  только фиксирует расхождение, чтобы оно не потерялось.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`in_work_page.dart`/`data_update_page.dart` → `DataUpdateBloc.on<DataUpdateStartAll>` →
  `_syncAuthData` → `_syncAllData` → `SettingsRepository`), включая точный
  порядок вызовов `_clearDataUpdates()`/`_addDataUpdateSuccess`, определяющий
  итоговое содержимое `DataUpdates` (шаг 13).
