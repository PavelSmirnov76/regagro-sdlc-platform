# UC-121 — Пользователь успешно проводит новую сессию инвентаризации (сканирует метки, завершает — сессия помечается readyToSend)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь проходит визард инвентаризации (`ScanningBloc`/`ScanningPage`) с
нуля — не правку уже сохранённой сессии (та — [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md),
отдельный use-case): место содержания и (если он не единственный) тип
физического сканера уже выбраны или подставлены автоматически, пользователь
сканирует RFID/UHF-метки животных на этом месте и жмёт «Завершить». Каждый
скан по ходу уже персистится отдельным черновиком
([ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), инвариант
«Черновик персистится на каждый скан») — предметом этого файла является
именно завершение: время всех сканов сессии нормализуется к минимальному, и
строки `UnsentReportAnimals` этой сессии (`sessionUuid`) помечаются
`readyToSend = true` — переход `draft → ready_to_send` из state machine
`InventoryScanReport` (`.claude/rules/domain-model.md`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни в `ScanningBloc`, ни в
`UnsentReportAnimalsRepository` нет ни одной проверки статуса авторизации
(`grep -n "isAuthorized\|getUser("` по обоим файлам не находит совпадений) —
в отличие, например, от `Disposal` ([ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)),
строка `UnsentReportAnimals` вообще не хранит `userId`. Сохранение полностью
локальное, без единого сетевого вызова; отправка на сервер — отдельный,
явный sync-шаг [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) не описывается
этим файлом.

## CURRENT

### Основной поток

1. Единственный реально существующий в навигации вход для НОВОЙ (не-edit)
   сессии — плитка «Инвентаризация» на экране событий места
   (`OperationsPage`, `lib/pages/operations/operations_page.dart`):
   `context.pushNamed2(Routes.scanning, extra: ScanningPageArgs.inventory(place:
   place, inventoryLabel: l10n.inventory))` — `farm` не передан, `editPlaceId`/
   `editSessionUuid` тоже не переданы (`grep -rn "ScanningPageArgs.inventory\|Routes.scanning"
   lib/` вне `scanning_page.dart` находит только этот вызов и второй, из
   `UnsentInventoriesPage` — тот второй уже задаёт `editSessionUuid`, т.е. это
   вход правки, [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md),
   не этот файл).
2. `ScanningPage.build` читает аргументы и создаёт `ScanningBloc()..add(ScanningStart(
   farm: null, place: args.place, scanningTypes: [ScanningType(id: 3, name:
   inventoryLabel, type: 'inventory')], editPlaceId: null, editSessionUuid: null))` —
   `ScanningPageArgs.inventory(...)` всегда конструирует ровно один элемент
   `scanningTypes` с `type: 'inventory'`, других типов операции сканирования
   этот конструктор не порождает никогда.
3. `ScanningBloc.on<ScanningStart>`: `await _deviceSettingsRepository.ensureDeviceInDatabase()`,
   `await _scannerService.applySavedTerminalSettings()`; `emit(ScanningInProgress())`;
   `selectedScanningType = event.scanningTypes.first` (список длины 1, всегда
   `'inventory'` для этого входа); `scannerTypes = _buildScannerTypes(operationType:
   'inventory')` — перебирает `_deviceSettingsRepository.getDefaultDevices()`,
   оставляет только устройства, включённые для операции `'inventory'`
   (`isDeviceEnabledForOperation`) и уже сконфигурированные
   (`isDeviceConfiguredForScanning`), схлопывает группу Bluetooth-устройств в
   одну карточку (`_collapseBluetoothGroup`), и добавляет мок-сканер `'Test'`
   (`id: 10`, всегда `isActive: true`), если `_authRepository.isDeveloper()`.
4. `farm = event.farm?.farm ?? (await _farmRepository.getById(event.place!.farmId))!` —
   поскольку `event.farm == null` на этом входе, ферма резолвится по
   `place.farmId` через `FarmRepository.getById` (поиск по `remoteId`, не по
   локальному `id`); `places = event.farm?.placesWithAnimals ?? await
   _placeRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)` —
   аналогично, грузится заново, т.к. `event.farm` пуст.
5. `presetPlace = places.where((p) => p.place.idRemote == event.place!.idRemote).firstOrNull` —
   ищет только что переданное место среди загруженного списка мест этой же
   фермы. Поскольку это то же самое место, с экрана которого была открыта
   плитка «Инвентаризация» (значит, оно уже принадлежит ферме и присутствует в
   `getAllWithThisFarmIdWithAnimals`), в типичном случае резолвится успешно —
   `skipPlaceStep: true` (см. «Открытые вопросы» про случай, когда это не так).
6. Т.к. `selectedScanningType.type == 'inventory'` и `event.editSessionUuid ==
   null` — `_data = _data.copyWith(sessionUuid: const Uuid().v4())`: для
   новой сессии инвентаризации `sessionUuid` минтится безусловно на этом шаге,
   один раз. Ветка `if (event.editSessionUuid != null && ...)` (восстановление
   уже сохранённой сессии правки) пропускается целиком — `editSessionUuid ==
   null`.
7. `emit(ScanningSuccess(_data))` — `_data.isEditMode == false`,
   `skipPlaceStep == true`, `sessionUuid` задан, `scannedAnimals` пуст.
   `ScanningRegistrationData.currentSteps` (= `singleSteps`, не-edit ветка):
   шаг `place` исключён (`skipPlaceStep`); шаг `scannerType` включается, только
   если `scannerTypes.length != 1`; шаг `animals` присутствует всегда. Если
   ровно одно устройство прошло фильтр шага 3 (типичный случай одного
   сконфигурированного сканера, без включённого dev-режима) — единственный
   шаг визарда сразу же `ScanningStep.animals`.
8. **Если `scannerTypes.length != 1`** (несколько сконфигурированных
   устройств, либо dev-режим добавил мок-сканер сверх одного реального) —
   пользователь видит шаг `ScannerTypeStepPage`, выбирает карточку → `bloc.add(
   ScanningEventChangeScannerType(type))`: подгружает сохранённые `ip`/антенны
   для этого типа устройства, `emit(ScanningSuccess(...))`; UI-колбэк
   `onSelected` сразу же вызывает `toNextStep()`, переключая вкладку на
   `animals`.
9. Вкладка `animals` рендерит `InventoryScanStepPage(scannedAnimals: [],
   placeWithAnimals: data.place!, allPlaces: data.places, selectedScannerTypeId:
   data.scannerType!.id, onCompleteScan: () => bloc.add(const ScanningEventSave()),
   ...)` — оба `!` предполагают, что `place`/`scannerType` уже разрешены
   предыдущими шагами.
10. Пользователь запускает скан (`_startContinuousScan`) — по
    `selectedScannerTypeId` вызывается соответствующий метод
    `ScannerService` (`startContinuousUhfScan`/`startContinuousBluetoothScan`/
    `startContinuousTcpScan`/`startContinuousBlueScan`/`startContinuousGrpScan`/
    `startContinuousGrpBleScan`); для Bluetooth-клавиатурного сканера
    (`ScannerDeviceLocalIds.bluetoothKeyboard`) и для тестового сканера
    (`id == 10`) отдельного «запуска» не требуется — статус сразу `connected`.
11. Каждый физический скан приходит через один из потоков
    `ScannerService.continuousUhfScans`/`tcpScans`/`grpScans`/`grpBleScans`/
    `bluetoothScans`/`blueScans` (либо `MockScanner.animalsStream` для
    тестового сканера, либо прямой ввод текста для Bluetooth-клавиатуры/
    dev-поля) — обработчик `animalsListen`, подписанный в конструкторе
    `ScanningBloc`, нормализует id до последних 15 символов и добавляет
    `ScanningEventAddAnimal(ScannedAnimal(transponderId: ..., time:
    DateTime.now()))`.
12. `on<ScanningEventAddAnimal>`: если `transponderId` уже есть в
    `scannedAnimals` — существующая запись обновляется на месте (новое
    `time`, тот же `transponderId`), список не растёт; иначе — новая запись
    добавляется в начало списка (`[event.animal, ...scannedAnimals]`). В обеих
    ветках сразу вызывается `_persistDraftScanReports()`, затем
    `emit(ScanningSuccess(_data))`.
13. `_persistDraftScanReports()`: `_canPersistSession` (ферма/место/тип
    сканирования резолвлены) — `true`; т.к. `_isInventory && sessionUuid !=
    null` → `UnsentReportAnimalsRepository.replaceDraftSessionByUuid(sessionUuid:,
    farmId: farm.remoteId!, placeId: place.place.idRemote!, type: 'inventory',
    animals: scannedAnimals)` — DAO удаляет все ещё черновые
    (`readyToSend == false`) строки этого `sessionUuid`
    (`deleteDraftBySessionUuid`) и вставляет заново весь текущий список одним
    `batch` (`insAll`) — полная замена, не точечный upsert (см.
    [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).
14. Шаги 11–13 повторяются на каждую новую/повторную метку. Одновременно UI
    (`InventoryScanStepPage._computeSections`, живой пересчёт при каждой
    перестройке) переносит отсканированные номера из «не найдено» в секции по
    возрастной группе места, ищет «чужие известные» метки среди мест **той же
    фермы** (см. ограничение видимости — [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
    инвариант «Дублирование логики сопоставления...»), а счётчик в
    `ScanningProgressBar` растёт до `data.place!.animals.length`.
15. Пользователь жмёт «Завершить» (кнопка видна безусловно при
    `_connectionStatus == connected`, не гейтится непустым списком сканов —
    см. «Альтернативные потоки») → `InventoryScanStepPage._finishScan()`:
    останавливает поток скана (`_stopScanOnExit`), затем `widget.onCompleteScan()`
    → `bloc.add(const ScanningEventSave())`.
16. `on<ScanningEventSave>`: `sessionStartTime` = минимальное `time` среди
    `_data.scannedAnimals` (список непуст в этом сценарии); `normalizedAnimals`
    = та же метка/тот же `transponderId`, но у **каждого** элемента `time`
    заменяется на этот единственный `sessionStartTime` — вся сессия схлопывается
    к одному моменту времени; `_data = _data.copyWith(scannedAnimals:
    normalizedAnimals)`.
17. `await _markSessionReadyToSend()`: `_canPersistSession == true` →
    `_persistDraftScanReports()` вызывается повторно — теперь уже с
    нормализованным списком (тот же `replaceDraftSessionByUuid`: удаляет и
    заново вставляет черновые строки этого `sessionUuid`, все с одинаковым
    `time`); затем, т.к. `_isInventory && sessionUuid != null` →
    `UnsentReportAnimalsRepository.markSessionReadyToSendByUuid(sessionUuid)` →
    DAO `UPDATE unsentReportAnimals SET readyToSend = true WHERE sessionUuid =
    :uuid` (безусловно по всем строкам этого uuid, без фильтра по текущему
    `readyToSend`) — это и есть переход, названный в
    [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md).
18. `emit(ScanningExit(time: sessionStartTime, type: _data.scanningType!
    (`'inventory'`), placeId: _data.place?.place.idRemote, placeName:
    _data.place?.place.name, sessionUuid: _data.sessionUuid))` — `sessionUuid`
    заполнен, т.к. `_isInventory == true`.
19. `ScanningPage`'s `BlocConsumer.listener`: `state is ScanningExit` →
    `context.pop(state.time)` (закрывает страницу визарда, возвращая `time`
    вызывающему коду — `OperationsPage`'s `onTap` этот результат не
    ожидает и не использует); затем, т.к. `state.type.type == 'inventory' &&
    state.time != null` → `context.pushNamed2(Routes.inventoryReport, extra:
    InventoryReportPageArgs(date: state.time!, sessionUuid: state.sessionUuid,
    farmId: args.farm?.farm.remoteId ?? args.place?.farmId, placeId:
    state.placeId))` — сразу открывается итоговый отчёт по этой сессии
    ([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md),
    не специфицируется этим файлом).
20. После `emit(ScanningExit(...))` обработчик, вне зависимости от исхода
    `try`, безусловно эмитит ещё раз `emit(ScanningSuccess(_data))` — к этому
    моменту слушатель уже среагировал на `ScanningExit` и страница уже
    закрывается (шаг 19), поэтому этот второй emit не имеет видимого эффекта —
    тот же безобидный, но избыточный паттерн двойного `emit`, что и в
    [UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md) («Открытые
    вопросы», «Двойной `emit`»).

### Альтернативные потоки

- **Смена места посреди ещё не завершённой (не-edit) сессии.** Если
  пользователь на шаге `animals` (или, теоретически, на шаге `place`, если он
  всё же показан — см. «Открытые вопросы») меняет место —
  `ScanningEventChangePlace`: ветка `_isInventory && !_data.isEditMode`
  безусловно выполняет `_data = _data.copyWith(place: event.place,
  scannedAnimals: [], sessionUuid: const Uuid().v4())` — накопленные сканы
  сбрасываются в памяти, заводится **новый** `sessionUuid`. Строки уже
  персистнутого черновика прежнего (брошенного) `sessionUuid`, записанные
  предыдущими вызовами `ScanningEventAddAnimal`/шагом 13, при этом **не
  удаляются** ни в этой ветке, ни где-либо ещё в коде — они остаются в
  `UnsentReportAnimals` с `readyToSend == false`, недостижимые из UI этой же
  сессии (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  инвариант «Смена места посреди новой сессии...»). Дальше визард продолжается
  с новым `sessionUuid`, и итоговый успешный `Save` (шаги 15–20) относится уже
  только к нему.
- **Уход со страницы кнопкой «назад» до нажатия «Завершить» (не-edit сессия).**
  `_ScanningPageState`'s `WillPopScope` на первой вкладке пропускает `pop`,
  закрывая всю страницу и уничтожая `ScanningBloc` (`close()`). Т.к.
  `_data.isEditMode == false`, условие `if (_data.isEditMode &&
  _canPersistSession)` в `close()` ложно целиком — ни
  `markSessionReadyToSendByUuid`, ни какая-либо иная персистенция не
  вызываются. Уже отсканированные и черновиком персистнутые метки (шаг 13)
  остаются в БД с `readyToSend == false` под тем же `sessionUuid` бессрочно —
  тот же итоговый эффект «осиротевших черновых строк», что и в сценарии смены
  места, но вызванный другим триггером (в отличие от [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md),
  где то же самое действие в **edit**-режиме, наоборот, доперсистит сессию как
  `readyToSend`, см. `ScanningBloc.close()`, ветка `isEditMode == true`). Не
  этот файл — RESULT здесь не `CREATE_OK` (ничего не завершено), отдельный
  use-case на эту ветку на момент написания не заведён.
- **«Завершить» нажато при `scannedAnimals.isEmpty`.** Кнопка «Завершить» в
  `InventoryScanStepPage._buildControls` видна безусловно при
  `_connectionStatus == connected`, независимо от числа сканов — в отличие,
  например, от кнопки подтверждения `AnimalsStepPage` в выбытии
  ([UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md)), скрытой при
  пустом выборе. В этом случае `sessionStartTime = DateTime.now()` (запасная
  ветка тернарника на шаге 16), `normalizedAnimals` — пустой список,
  `_persistDraftScanReports()` при пустом `animals` в
  `replaceDraftSessionByUuid` только удаляет прежние черновые строки этого
  `sessionUuid` (`deleteDraftBySessionUuid`) и сразу возвращается
  (`if (animals.isEmpty) return;`, репозиторий), не вставляя ничего —
  под этим `sessionUuid` не остаётся ни одной строки вообще. Последующий
  `markSessionReadyToSendByUuid(sessionUuid)` выполняет `UPDATE ... WHERE
  sessionUuid = :uuid` над нулём строк — не ошибка, но и не эффект. Экран всё
  равно эмитит `ScanningExit(sessionUuid: <тот же uuid>, ...)` и переходит на
  итоговый отчёт — по полностью пустой сессии, неотличимо от «успеха» на
  уровне UI (см. «Открытые вопросы»).
- **Несколько сконфигурированных сканеров либо dev-режим.** Если
  `scannerTypes.length != 1` (второй реальный сканер, либо один реальный плюс
  добавленный `_authRepository.isDeveloper()` мок `'Test'`) — перед шагом
  `animals` добавляется шаг `ScannerTypeStepPage` (см. основной поток, шаг 8);
  в противном случае (ровно один сконфигурированный сканер, без dev-режима)
  этот шаг исключён и `scannerType` подставляется автоматически
  (`_getDefaultScannerSettings`).
- **Повторный скан уже известной метки.** Покрыт основным потоком (шаг 12) —
  дедуп по `transponderId`, время обновляется на месте, список не растёт.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — сущность, совершающая переход: строки
  `UnsentReportAnimals` этого `sessionUuid` — от `readyToSend == false`
  (создаются по одной на каждый уникальный скан через `replaceDraftSessionByUuid`)
  к `readyToSend == true` (после `markSessionReadyToSendByUuid`), со всеми
  `time`, нормализованными к минимальному моменту сессии.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только читается,
  и не через `sessionUuid`/БД-связь (её нет, см. ENT-17), а исключительно на
  клиенте, в момент отрисовки: `InventoryScanStepPage._computeSections`
  сопоставляет отсканированные `transponderId` с
  `animal.activeAnimalIdentifications` места (и, для «чужих», — других мест
  той же фермы) через [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md).
  Ни одно поле `Animal` этим сценарием не пишется.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается:
  место сессии (`farmId`/`placeId`, сохраняемые в каждой строке
  `UnsentReportAnimals`); не изменяется этим сценарием.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — читается:
  резолвится один раз в `ScanningStart` через `FarmRepository.getById`, не
  перечитывается заново при `Save`; не изменяется этим сценарием.

### Бизнес-правила

- Для новой (не-edit) сессии инвентаризации `sessionUuid` минтится один раз в
  `ScanningStart` и остаётся тем же до `Save`, если только пользователь не
  сменит место (тогда — новый `sessionUuid`, см. «Альтернативные потоки»).
- Каждый уникальный скан персистится немедленно, отдельным вызовом
  `replaceDraftSessionByUuid`, а не только в момент завершения — черновик
  всегда синхронизирован с тем, что видно на экране.
- `Save` нормализует время **всех** сканов сессии к единому минимальному
  моменту — исходное время каждого отдельного скана после завершения сессии
  не восстановимо ни в `UnsentReportAnimals`, ни где-либо ещё.
- `readyToSend` выставляется `UPDATE ... WHERE sessionUuid = :uuid` —
  безусловно по всем строкам этого `sessionUuid`, без проверки, что каждая из
  них действительно ещё черновая.
- Сохранение полностью локальное — ни `on<ScanningStart>`, ни
  `on<ScanningEventSave>` не выполняют ни одного сетевого вызова; push всех
  `readyToSend == true` строк — отдельный будущий sync-шаг, не в рамках этого
  файла.
- Кнопка «Завершить» не гейтится непустым списком сканов — визард можно
  успешно завершить, не отсканировав ни одной метки (см. «Альтернативные
  потоки»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — основной поток (шаги 1–20) полностью
реализован и достижим через единственный живой вход (`OperationsPage`, плитка
«Инвентаризация»); находки, перечисленные в «Альтернативные потоки» и
«Открытые вопросы», не блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/operations/operations_page.dart` | `OperationsPage.build` (плитка «Инвентаризация») | CURRENT | единственный живой вход для новой (не-edit) сессии — `ScanningPageArgs.inventory(place:)`, без `farm`/`editSessionUuid` |
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `UnsentInventoriesPage._openEditMode` | CURRENT | второй живой вход в `Routes.scanning` — но всегда с `editSessionUuid`, т.е. правка ([EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)), не этот файл |
| `lib/pages/scanning/scanning_page.dart` | `ScanningPageArgs.inventory`, `ScanningPage.build`, `BlocConsumer.listener` (`ScanningExit`) | CURRENT | конструирует аргументы (всегда один `ScanningType` с `type: 'inventory'`), запускает `ScanningStart`, по `ScanningExit` закрывает страницу и открывает `Routes.inventoryReport` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningStart>` | CURRENT | резолвит farm/place, минтит `sessionUuid` для новой inventory-сессии, строит `scannerTypes` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc._buildScannerTypes`, `_collapseBluetoothGroup`, `_getDefaultScannerSettings` | CURRENT | фильтр включённых/сконфигурированных устройств, схлопывание Bluetooth-группы, авто-выбор при единственном устройстве |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventChangeScannerType>` | CURRENT | шаг выбора типа сканера, если их больше одного |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventAddAnimal>`, `_persistDraftScanReports` | CURRENT | дедуп по `transponderId`, персист черновика на каждый скан через `replaceDraftSessionByUuid` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>`, `_markSessionReadyToSend` | CURRENT | ядро сценария — нормализация времени, повторный персист, `markSessionReadyToSendByUuid`, `emit(ScanningExit)` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventChangePlace>` | CURRENT | ветка `_isInventory && !isEditMode` — сброс сканов и новый `sessionUuid` при смене места посреди сессии |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.close()` | CURRENT | для не-edit сессии не персистит ничего при закрытии страницы кнопкой «назад» — условие `isEditMode && _canPersistSession` ложно |
| `lib/pages/scanning/steps/scanner_type_step_page.dart` | `ScannerTypeStepPage` | CURRENT | шаг выбора типа сканера — рендерится только при `scannerTypes.length != 1` |
| `lib/pages/scanning/steps/inventory_scan_step_page.dart` | `InventoryScanStepPage._startContinuousScan`, `_finishScan`, `_computeSections`, `_buildControls` | CURRENT | сам экран сканирования — запуск/остановка потока, кнопка «Завершить» (не гейтится непустым списком), живой пересчёт секций |
| `lib/pages/scanning/widgets/inventory_accordion_list_widget.dart` | `InventoryAccordionListWidget` | CURRENT | отображение живых секций «найдено»/«не найдено»/«чужое известное»/«неизвестное» |
| `lib/services/scanner_service.dart` | `ScannerService.continuousUhfScans`/`tcpScans`/`grpScans`/`grpBleScans`/`bluetoothScans`/`blueScans`, `startContinuousXxxScan` | CURRENT | потоки сырых сканов по типам физических сканеров |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.replaceDraftSessionByUuid`, `markSessionReadyToSendByUuid` | CURRENT | персист черновика (полная замена по `sessionUuid`) и финальная пометка готовности |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.deleteDraftBySessionUuid`, `markSessionReadyToSendByUuid` | CURRENT | безусловный `UPDATE ... WHERE sessionUuid = :uuid`, без проверки исходного `readyToSend` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll` | CURRENT | batch-вставка нормализованных строк черновика |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | резолв фермы по `remoteId` из `place.farmId`, один раз в `ScanningStart` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmIdWithAnimals` | CURRENT | список мест фермы для резолва `presetPlace` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `applySavedTerminalSettings`, `getDefaultDevices`, `isDeviceEnabledForOperation`, `isDeviceConfiguredForScanning` | CURRENT | подготовка устройства и фильтр доступных сканеров для операции `'inventory'` |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.bluetoothGroup`, `ScannerDeviceLocalIds.bluetoothKeyboard` | CURRENT | группировка Bluetooth-устройств, распознавание клавиатурного сканера |
| `lib/pages/animals_inventory/presentation/inventory_report__details_page.dart` | `InventoryReportPageArgs` | CURRENT | аргументы следующего экрана ([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)), на который безусловно переходит успешный `Save` |

## Критерии приёмки

- `ScanningStart` со `scanningTypes` длины 1 и типом `'inventory'`, без
  `editSessionUuid`, всегда порождает новый `sessionUuid` (`const Uuid().v4()`)
  до первого `emit(ScanningSuccess)`.
- Каждый `ScanningEventAddAnimal` с новым `transponderId` увеличивает
  `scannedAnimals` на один элемент (в начало списка) и вызывает ровно один
  `replaceDraftSessionByUuid` с текущим `sessionUuid` и полным списком; тот же
  `transponderId` повторно — не увеличивает длину списка, обновляет `time`.
- `ScanningEventSave` при непустом `scannedAnimals`: все элементы после
  нормализации имеют одинаковый `time`, равный минимальному исходному;
  вызывается ровно один дополнительный `replaceDraftSessionByUuid` (с
  нормализованными данными) и ровно один `markSessionReadyToSendByUuid(sessionUuid)`;
  эмитится `ScanningExit` с тем же `sessionUuid`, `type.type == 'inventory'` и
  `time`, равным нормализованному моменту.
- После `ScanningExit` строка (или строки) `UnsentReportAnimals` этого
  `sessionUuid` имеют `readyToSend == true`.
- Сценарий не выполняет ни одного сетевого вызова.
- Страница визарда закрывается (`context.pop`), и приложение переходит на
  `Routes.inventoryReport` с `sessionUuid`/`date`/`placeId` из `ScanningExit`.

## Связанные тесты

- `test/pages/scanning_bloc_test.dart`, group `'UC-121 — ScanningEventChangePlace
  (inventory: новая сессия)'` (историческая нумерация — до пересборки
  `sdlc/2-specs/`, будет переименована отдельным контролируемым проходом, не
  трогать сейчас) — тест `'inventory-режим (не edit) -> новая сессия
  (sessionUuid меняется), scannedAnimals сброшены'` косвенно подтверждает
  часть основного потока (шаг 6 — `ScanningStart` минтит `sessionUuid` для
  новой inventory-сессии: тест читает `firstSessionUuid` сразу после `Start` и
  сравнивает с тем, что осталось после `ScanningEventChangePlace`) и целиком
  покрывает альтернативный поток «смена места посреди сессии» (сброс
  `scannedAnimals`, новый `sessionUuid`) — но не сам финальный `Save`.
- `test/pages/scanning_bloc_test.dart`, group `'НАХОДКА — ScanningEventSave,
  легаси не-uuid путь (type="output" — структурно недостижим через реальную
  навигацию, см. ENT-11)'` (историческая нумерация, не трогать) — тест
  `'валидная сессия (ферма+место+тип выбраны) -> markSessionReadyToSend вызван,
  ScanningExit'` подтверждает механизм «нормализация → пометка готовности →
  `ScanningExit`» на уровне `ScanningEventSave`, но идёт через легаси
  не-`sessionUuid` путь (`type: 'output'`, `markSessionReadyToSend`, не
  `markSessionReadyToSendByUuid`) — этот путь недостижим через реальную
  навигацию (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  инвариант «Разделяемые таблицы с недостижимым легаси-типом»). Название
  группы в тестовом файле ссылается на «см. ENT-11» — по факту описываемый
  механизм принадлежит [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  не `ENT-11` (Animal); это цитируется здесь дословно как есть, без правки
  чужого текста (см. «Открытые вопросы»).
- **TBD — теста нет** на прямой сценарий этого файла: ни один тест не проводит
  НОВУЮ (не-edit, с реальным `sessionUuid`, `type == 'inventory'`) сессию через
  `ScanningEventAddAnimal` → `ScanningEventSave` с проверкой (`verify`) вызова
  `markSessionReadyToSendByUuid`/`replaceDraftSessionByUuid` — оба метода
  только застаблены (`stubPersistCalls()`) во всём файле, ни разу не
  верифицированы. Две группы выше покрывают части механизма по отдельности
  (минтинг `sessionUuid` и сброс сессии при смене места — первая; нормализация
  + пометка готовности + `ScanningExit` — вторая, но через мёртвый
  не-`sessionUuid` путь), но ни одна не доводит именно живой uuid-путь до
  `Save` целиком.
- **TBD — теста нет** на сценарий «Завершить» при `scannedAnimals.isEmpty»
  (нулевая сессия, помечаемая `readyToSend` без единой строки в БД).
- **TBD — теста нет** на уход со страницы кнопкой «назад» до «Завершить» в
  не-edit сессии (`ScanningBloc.close()` ничего не персистит).

## Открытые вопросы и ограничения

- **Шаг «место» для новой сессии де-факто недостижим через единственный живой
  вход.** `OperationsPage` всегда передаёт уже загруженное место той же
  фермы, поэтому `presetPlace` в `ScanningStart` в типичном случае резолвится
  успешно и `skipPlaceStep == true`. Код, отображающий шаг `SelectPlaceStepPage`
  для не-edit сессии, существует и технически реализован (сработает, если
  `presetPlace` не резолвится — например, рассинхронизация `idRemote`), но
  отдельно не воспроизведён и не покрыт тестом с реальным несовпадением. Тот
  же паттерн честности, что уже применялся к недостижимым шагам в
  [UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md) («Шаг
  `selectPlace` де-факто недостижим»).
- **«Нулевая» успешная сессия.** Кнопка «Завершить» не проверяет, что хотя бы
  одна метка была отсканирована — визард можно успешно завершить (со
  `ScanningExit` и переходом на отчёт) без единой строки `UnsentReportAnimals`
  под этим `sessionUuid` вообще (см. «Альтернативные потоки»). Является ли это
  осознанным решением (пустой отчёт как валидный факт «на месте никого не
  нашли») или недосмотром — ничем в коде не зафиксировано.
- **Асимметрия `close()` между edit- и не-edit сессией.** Уход кнопкой «назад»
  до «Завершить» в edit-режиме доперсиживает сессию как `readyToSend`
  ([EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)); в
  не-edit режиме (этот файл) — не делает ничего, оставляя уже
  персистнутые сканы черновиком навсегда под брошенным `sessionUuid`. Не
  разбирается глубже здесь.
- **Комментарий в тестовом файле цитирует не тот `ENT`.** Группа `'НАХОДКА —
  ScanningEventSave, легаси не-uuid путь (type="output"...)'` в своём
  собственном названии ссылается на «см. ENT-11» (Animal), тогда как
  описываемый ей механизм (легаси `way_type`, недостижимый через реальную
  навигацию) документирован в [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport), не в `ENT-11`. Тест — уже существующий, не
  переписывается этим проходом; расхождение зафиксировано здесь как
  наблюдение, аналогично тому, как [UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md)
  фиксирует нерезолвящуюся ссылку `ENT-27`/`UC-319` в комментарии исходного
  кода, не исправляя его.
- **Исключение в `on<ScanningStart>` до первого `emit` гасится тихо.**
  `ensureDeviceInDatabase()`/`applySavedTerminalSettings()` выполняются внутри
  `try`, чей `catch (e, st)` только логирует через `if (kDebugMode) log(...)` —
  в release-сборке (`kDebugMode == false`) сбой на этом шаге не оставляет
  вообще никакого следа, и бloc так и остаётся в `ScanningInitial()` — экран
  показывает бесконечный `CircularProgressIndicator` (`_BodyBuilder`, ветка
  `else`). Не воспроизведено тестом, вероятность на практике не оценивалась —
  не разбирается глубже в рамках этого файла.
- **Двойной `emit` в конце `ScanningEventSave`** — не имеет видимого эффекта
  (страница уже закрыта слушателем к моменту второго `emit`), тот же паттерн,
  что и в [UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md); не
  разбирается глубже.
- Не проверено эмпирически на реальном устройстве со сканером — вывод сделан
  статическим чтением кода (`ScanningBloc` → `ScannerService` →
  `UnsentReportAnimalsRepository`/DAO); поведение конкретных физических
  сканеров (UHF/Bluetooth/TCP/GRP) при реальном обрыве соединения посреди
  сессии этой спекой не покрывается.
