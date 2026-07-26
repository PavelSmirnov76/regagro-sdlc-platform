# UC-123 — Пользователь дополняет/пересматривает уже сохранённую сессию инвентаризации и завершает правку — явно кнопкой «Завершить» либо неявно уходом назад

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает уже сохранённую (`readyToSend == true`), но ещё не
отправленную на сервер сессию инвентаризации из хаба «В работе» →
`UnsentInventoriesPage`, тапает по карточке сессии →
`ScanningPageArgs.inventory(editPlaceId:, editSessionUuid:)` →
`ScanningBloc.on<ScanningStart>` переводит сессию обратно в черновик
(`markSessionAsDraftByUuid`, снимает `readyToSend`) и подгружает уже
отсканированные строки заново (`getSessionReportsByUuid`), включает
`isEditMode = true`. Пользователь может дополнить сессию новыми сканами или
просто просмотреть её без единого действия. Завершение правки — единственная
операция записи (`UPDATE`) этого файла — достижимо двумя равнозначными
путями, оба разбираются здесь одновременно, потому что оба приводят к одному
и тому же наблюдаемому эффекту на `UnsentReportAnimals` (тот же `sessionUuid`
снова становится `readyToSend == true`), но принципиально разными
механизмами:

- **Путь A — явно.** Кнопка «Завершить» на шаге сканирования →
  `ScanningEventSave` — **тот же обработчик**, что и у создания новой сессии
  ([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md), вероятный
  сосед по этому же проходу спецификации — `UC-121`/`UC-122`, на момент
  написания этого файла ещё не существующие как файлы в `use-cases/`, потому
  не цитируются markdown-ссылкой). Отличает эту сессию от создания только
  то, что `sessionUuid` уже был задан при входе (`editSessionUuid`) и не
  меняется.
- **Путь B — неявно.** Пользователь уходит с экрана «назад» (системный жест
  или дефолтная стрелка `AppBar`), не нажимая «Завершить» вовсе.
  `ScanningBloc.close()` при `_data.isEditMode && _canPersistSession`
  доперсистит сессию как `readyToSend = true` **без какого-либо
  подтверждения, снэкбара или иной обратной связи пользователю**, и без
  единого `emit` — сравнение путей A/B, включая различия в том, что именно
  каждый из них пишет в БД, см. «Основной поток».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `ScanningBloc`, ни
`UnsentReportAnimalsRepository` не проверяют статус авторизации в этом
сценарии (`grep -rn "isAuthorized\|AuthRepository" lib/pages/scanning/scanning_bloc.dart`
находит только `_authRepository.isDeveloper()`, используемый исключительно
для добавления тестового (`Test`) сканера в список типов, не для гейта
доступа). Сохранение полностью локальное — ни один из двух путей завершения
не делает сетевого вызова и не проверяет состояние сети; отправка на сервер —
отдельный, явный sync-проход (см. [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md),
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)).

## CURRENT

### Основной поток

**Вход в режим правки (общий для обоих путей завершения).**

1. Хаб «В работе» → плитка «Инвентаризация» → `Routes.unsentInventories` →
   `UnsentInventoriesCubit.load()` ([EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md),
   не этот файл) грузит все `readyToSend == true` строки `UnsentReportAnimals`
   типа `inventory`, группирует по `sessionUuid` в `UnsentInventoryItem`
   (`farmId`, `placeId`, `sessionUuid` — все три невозможны как `null` на этом
   пути: строки без `sessionUuid` явно пропускаются `continue`, см.
   [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)) вместе с
   `farmWithDetails`/`placeWithAnimals`, резолвленными через
   `FarmRepository.getById`/`PlaceRepository.getAllWithThisFarmIdWithAnimals`.
2. Тап по карточке (`_InventorySessionCard.onTap`) →
   `UnsentInventoriesPage._openEditMode`: `context.pushNamed2(Routes.scanning,
   extra: ScanningPageArgs.inventory(farm: item.farmWithDetails, inventoryLabel:
   l10n.inventory, editPlaceId: item.placeId, editSessionUuid:
   item.sessionUuid))` — вызов **не** дожидается (`await`) результата
   навигации и не подписан ни на что после возврата; единственный способ
   обновить список хаба после возврата — ручной `RefreshIndicator` (см.
   «Открытые вопросы»).
3. `ScanningPage.build` создаёт `ScanningBloc()..add(ScanningStart(farm:
   args.farm, place: args.place, scanningTypes: args.scanningTypes,
   editPlaceId: args.editPlaceId, editSessionUuid: args.editSessionUuid))`. В
   этом входе `args.place` всегда `null` (аргументы задают только
   `editPlaceId`, не сам объект `Place`) — `farm` всегда non-null
   (`item.farmWithDetails`).
4. `ScanningBloc.on<ScanningStart>`: после `ensureDeviceInDatabase`/
   `applySavedTerminalSettings` и `emit(ScanningInProgress())`:
   - `selectedScanningType` — единственный элемент `event.scanningTypes`
     (`ScanningPageArgs.inventory` всегда строит список ровно из одного
     `ScanningType(type: 'inventory')`) — всегда non-null здесь;
   - `farm = event.farm!.farm` (без обращения к `FarmRepository` — `event.farm`
     задан), `places = event.farm!.placesWithAnimals` (без обращения к
     `PlaceRepository.getAllWithThisFarmIdWithAnimals` — тот же аргумент
     `??`-приоритета, что не задействован для этого входа);
   - `presetPlace` вычисляется только из `event.place` (здесь `null`) → `null`;
     `_data` на этом шаге получает `place: null, skipPlaceStep: false` —
     значения, которые ниже перезаписываются в edit-ветке при успехе;
   - `if (selectedScanningType?.type == 'inventory' && event.editSessionUuid ==
     null)` — ложно (`editSessionUuid` задан), новый `sessionUuid` **не**
     генерируется — в отличие от [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md),
     это и делает переход `UPDATE`, а не `CREATE`: у сессии остаётся тот же
     идентификатор, с которым она была открыта;
   - `if (event.editSessionUuid != null && selectedScanningType != null)` —
     истинно: `place = _data.places.where((p) => p.place.idRemote ==
     event.editPlaceId).firstOrNull`.
     - **Если `place` найден** (обычный случай — см. «Открытые вопросы» про
       случай, когда не найден): `_data = _data.copyWith(place: place,
       scannedAnimals: [], isEditMode: true, skipPlaceStep: true, sessionUuid:
       event.editSessionUuid)`; `await
       _unsentReportsRepository.markSessionAsDraftByUuid(event.editSessionUuid!)` —
       **все** строки `UnsentReportAnimals` этого `sessionUuid` немедленно
       переводятся обратно в `readyToSend = false`, ещё до того, как
       пользователь предпримет хоть одно действие на экране правки — то есть
       первая мутация БД этого сценария происходит уже на входе, независимо от
       того, будет ли правка когда-либо завершена (см. «Открытые вопросы»);
       затем `session = await _loadSessionFromStorage()` →
       (`_isInventory && sessionUuid != null`) →
       `getSessionReportsByUuid(sessionUuid)`, мапится в `ScannedAnimal`.
       Если `session != null && session.animals.isNotEmpty`: `_data =
       _data.copyWith(scannedAnimals: session.animals)`, `emit(ScanningSuccess(
       _data, openAnimalsStep: _data.scannerType != null))`, `return` (минуя
       безусловный `emit` в конце обработчика).
5. `ScanningRegistrationData.currentSteps` для `isEditMode == true`:
   `if (scannerTypes.length != 1) steps.add(scannerType); steps.add(animals);` —
   шаг выбора места (`selectPlace`) отсутствует всегда в edit-режиме. Если
   локально настроен ровно один тип сканера (типичный случай одного
   зарегистрированного устройства), `scannerTypes.length == 1` →
   `data.scannerType` уже автоматически выставлен (`_getDefaultScannerSettings`)
   → единственный шаг — `[animals]`; `openAnimalsStep: _data.scannerType !=
   null` в этом случае логически эквивалентно тому же условию
   `scannerTypes.length == 1`, при котором шаг сканирования и так уже
   единственная вкладка (индекс `0`) — на практике этот флаг для данной ветки
   инертен (`_changeStep(0)` на уже активной вкладке `0`), в отличие от его
   использования в ветке `ScanningEventChangePlace` (другой код, не этот
   сценарий). Если типов сканера несколько (или ни одного), шаг
   `scannerType` остаётся отдельной первой вкладкой, и `openAnimalsStep`
   остаётся `false`.
6. Пользователь на шаге «Животные» (`InventoryScanStepPage`) видит уже
   восстановленные из БД `scannedAnimals` (список сессии, как он был на
   момент последнего сохранения) наравне со списком животных места
   (`placeWithAnimals: data.place!`). Может отсканировать дополнительные
   метки либо не делать ничего.
7. Каждый новый скан → `ScanningEventAddAnimal`: дедуплицирует по
   `transponderId` (обновляет `time` существующей строки вместо дублирования
   записи в состоянии) либо добавляет новую запись первой; затем
   `_persistDraftScanReports()` → (`_isInventory && sessionUuid != null`) →
   `replaceDraftSessionByUuid(sessionUuid:, farmId:, placeId:, type:
   'inventory', animals: _data.scannedAnimals)` → `dao.deleteDraftBySessionUuid(sessionUuid)`
   (удаляет строки этого `sessionUuid`, где `readyToSend == false` —
   безопасно, поскольку шаг 4 уже перевёл все строки сессии в `false`) +
   полная повторная вставка текущего в-памяти списка, каждая новая строка —
   снова с `readyToSend: false` явно. `emit(ScanningSuccess(_data))`.

**Путь A — явное завершение.**

8. Пользователь нажимает «Завершить» (`l10n.finish`) на шаге «Животные» —
   единственная кнопка, без диалога подтверждения (в отличие от визардов
   Movement/Disposal) — `_InventoryScanStepPageState._finishScan()`:
   останавливает подписки сканера (`_stopScanOnExit`), затем
   `widget.onCompleteScan()` → `bloc.add(const ScanningEventSave())`.
9. `ScanningBloc.on<ScanningEventSave>` (тот же обработчик, что у
   [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md), без
   отдельной ветки на `isEditMode`):
   - `sessionStartTime` — минимальное `time` среди **текущего** (уже
     дополненного) `_data.scannedAnimals` (или `DateTime.now()`, если список
     пуст); `normalizedAnimals` — тот же список, но у **каждой** записи
     (включая ранее сохранённые, не только новые сканы) `time` принудительно
     перезаписывается этим единым `sessionStartTime`;
   - `_data = _data.copyWith(scannedAnimals: normalizedAnimals)`;
   - `await _markSessionReadyToSend()`: (`_canPersistSession` здесь всегда
     `true` — `farm`/`place`/`scanningType` были провалидированы уже на входе
     в edit-режим и ничто в этом bloc'е не сбрасывает `place` при
     `isEditMode == true`, см. `ScanningEventChangePlace`, ветка требует
     `!isEditMode` — «тихий no-op» из [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)
     здесь недостижим) → `await _persistDraftScanReports()` (снова
     `replaceDraftSessionByUuid` с уже нормализованными временами, тот же
     delete+insert, `readyToSend: false`), затем `await
     _unsentReportsRepository.markSessionReadyToSendByUuid(sessionUuid)` —
     **все** строки этого `sessionUuid` становятся `readyToSend = true`;
   - `emit(ScanningExit(time: sessionStartTime, type: _data.scanningType!,
     placeId: _data.place?.place.idRemote, placeName: _data.place?.place.name,
     sessionUuid: _data.sessionUuid))` — `sessionUuid` совпадает с тем, с
     которым сессия была открыта;
   - безусловно, сразу после (вне зависимости от успеха/исключения — только
     успешная ветка релевантна этому файлу) — `emit(ScanningSuccess(_data))`.
     Поскольку `ScanningExit` уже вызвал `context.pop(...)` в слушателе
     страницы к моменту, когда этот второй `emit` доходит до подписчиков,
     наблюдаемого эффекта у него, как правило, уже нет — тот же паттерн
     «лишний emit после выхода», что отмечен в
     [UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md), но здесь это
     не дедупликация `Equatable`-состояний, а просто то, что виджет,
     слушающий стрим, уже начал уходить со страницы.
10. `BlocConsumer.listener` в `ScanningPage`, ветка `state is ScanningExit`:
    `context.pop(state.time)` (результат навигации не используется
    вызывающим кодом — хаб не ждал `await`, см. шаг 2), затем, поскольку
    `state.type.type == 'inventory' && state.time != null` — оба истинны —
    `context.pushNamed2(Routes.inventoryReport, extra:
    InventoryReportPageArgs(date: state.time!, sessionUuid: state.sessionUuid,
    farmId: ..., placeId: state.placeId))` — тот же автоматический переход на
    итоговый отчёт ([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)),
    что и после создания новой сессии.

**Путь B — неявное завершение (уход назад).**

11. Вместо «Завершить» пользователь инициирует системный back-жест либо
    нажимает дефолтную стрелку `AppBar` (`CustomAppBar` не задаёт `leading`/
    `automaticallyImplyLeading` — Flutter добавляет стандартную стрелку,
    вызывающую `Navigator.maybePop`). Единственный явный `Navigator.pop`/
    `context.pop` во всей папке `lib/pages/scanning/` — тот, что в шаге 10
    (путь A); никакая другая кнопка визарда не завершает страницу напрямую.
    `_ScanningPageState`'s `WillPopScope.onWillPop`: `if (_currentIndex > 0) {
    _toPrevStep(); return false; }`, иначе `return true;`.
    - Если `scannerTypes.length == 1` (шаг 5) — единственная вкладка
      `[animals]`, индекс всегда `0` — первое же нажатие «назад»
      действительно закрывает страницу.
    - Если типов сканера несколько — вкладки `[scannerType, animals]`;
      находясь на «Животные» (индекс `1`), первое нажатие только
      переключает на вкладку `scannerType` (`_toPrevStep()`, `return false`);
      закрывает страницу только второе нажатие (индекс `0`).
12. Как только `Navigator` реально снимает `ScanningPage` с дерева,
    `BlocProvider`, обёртывающий `ScanningBloc`, вызывает `dispose: (_, bloc)
    => bloc.close()` (`package:flutter_bloc`, `bloc_provider.dart`) — сигнатура
    `dispose` в используемом `provider`/`flutter_bloc` синхронна (`void
    Function(...)`), поэтому `Future`, возвращаемый `close()`, **не
    ожидается** этим местом вызова — запись в БД происходит в фоне, уже после
    того, как с точки зрения пользователя страница исчезла.
13. `ScanningBloc.close()`: отменяет все подписки сканера,
    `_commonChannel.invokeMethod('clear')`, затем — `if (_data.isEditMode &&
    _canPersistSession)` (оба истинны в этом сценарии) → `if (_isInventory &&
    _data.sessionUuid != null)` (истинно) → `await
    _unsentReportsRepository.markSessionReadyToSendByUuid(_data.sessionUuid!)`.
    В отличие от пути A:
    - **не** вызывается `_persistDraftScanReports()`/`replaceDraftSessionByUuid`
      перед пометкой готовности — просто «запечатывает» уже персистентные
      строки (каждый скан из шага 7 уже был сохранён немедленно своим
      собственным вызовом);
    - **не** нормализует `time` ни одной строки к общему `sessionStartTime` —
      шаг 9 (нормализация) целиком принадлежит `ScanningEventSave`, который
      здесь не вызывается вовсе; строки сохраняют то `time`, что у них было на
      момент последнего `_persistDraftScanReports()` (исходное время сессии
      для нетронутых строк, `DateTime.now()` на момент скана для новых);
    - **не эмитится ни одно состояние** — ни `ScanningExit`, ни
      `ScanningSuccess` — пользователь не получает вообще никакого сигнала
      (ни снэкбара, ни навигации), что сессия была повторно помечена
      `readyToSend = true`;
    - **не происходит** автоматический переход на
      `InventoryReportDetailsPage` — этот переход управляется исключительно
      слушателем состояния `ScanningExit` (шаг 10), которое на этом пути
      никогда не возникает.
    - `return super.close();`.

### Альтернативные потоки

- **Совсем без новых сканов, чистый просмотр.** Пользователь ничего не
  сканирует после входа в edit-режим и сразу завершает (любым из путей) —
  единственный наблюдаемый эффект на БД — двойной переворот флага
  `readyToSend` (`false` на входе, снова `true` на выходе); содержимое сессии
  не меняется. Формально всё ещё `UPDATE_OK` по определению этого файла (само
  событие [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)
  явно допускает «дополнительные сканы либо простой просмотр»).
- **Несколько типов сканера настроено одновременно** — путь B требует двух
  последовательных нажатий «назад» вместо одного (см. шаг 11), итоговая
  запись в БД идентична.
- **Целевое место не резолвится в `_data.places` по `editPlaceId`.** Если
  `place = _data.places.where(...).firstOrNull` на шаге 4 возвращает `null`
  (см. «Открытые вопросы» — конкретный воспроизводимый по коду механизм, не
  гипотетический), весь блок `if (place != null) { ... }` пропускается
  целиком: `markSessionAsDraftByUuid` **не вызывается вовсе** (сессия
  остаётся как была, `readyToSend == true`, нетронутой), `isEditMode`
  остаётся `false`, `sessionUuid` в `_data` остаётся `null` (несмотря на то,
  что `event.editSessionUuid` был непустым). Управление доходит до
  безусловного `emit(ScanningSuccess(_data))` в конце обработчика — с
  `place: null, skipPlaceStep: false` (значения из самого начала обработчика,
  шаг 4) — то есть пользователь вместо экрана правки конкретной сессии молча
  попадает в **обычный (не-edit) визард** с шагом выбора места первым, без
  единого восстановленного скана и без индикации, что что-то пошло не так.
  Эта ветка не покрывается этим use-case (это не `UPDATE`, а фактически
  прерванный вход) — задокументирована в «Открытые вопросы».
- **Исключение внутри `ScanningEventSave`** (например, репозиторий бросает) —
  перехватывается тем же `try/catch`, что и у
  [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md):
  `getIt<Talker>().error(...)`, `emit(ScanningMessage('an_error_data'))`, затем
  всё равно безусловный `emit(ScanningSuccess(_data))`. `RESULT` для этой
  ветки — не `UPDATE_OK`; отдельный use-case на эту ветку в этот файл не
  входит.
- **Приложение/процесс убито (или иным образом уничтожено) между шагом 4
  (`markSessionAsDraftByUuid`, уже отработавшим) и любым из путей завершения
  правки** — `dispose`/`close()` гарантированно вызывается только штатным
  жизненным циклом Flutter-виджета; принудительное завершение процесса ОС не
  гарантирует его вызов. Сессия остаётся `readyToSend = false` на
  неопределённый срок — не воспроизведено тестом, разобрано в «Открытые
  вопросы».

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (`UnsentReportAnimals`, `InventoryScanReport`) — сущность сегмента `ENT` в
  id: все строки одного и того же `sessionUuid` переворачивают
  `readyToSend` дважды (`true → false` на входе в правку, `false → true` на
  завершении любым путём); ни `sessionUuid`, ни `id` строк не меняются —
  это то, что делает переход `UPDATE`, а не создание новой сессии
  ([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)).
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — только
  читается: `editPlaceId` резолвится в объект `Place` по совпадению
  `idRemote` внутри уже загруженного `event.farm.placesWithAnimals`; см.
  «Открытые вопросы» про случай, когда это совпадение не находится.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только читается:
  `item.farmWithDetails.farm`, передаётся визарду напрямую, без обращения к
  `FarmRepository` в этом входе.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только
  читается, косвенно: `placeWithAnimals.animals` (уже загруженный список
  животных места) используется `InventoryScanStepPage` для прогресс-бара
  «учтено»/секций сопоставления — сам этот сценарий не создаёт и не меняет
  ни одну строку `Animal` (сопоставление метка↔животное на этом экране
  вычисляется на клиенте без FK, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).

### Бизнес-правила

- **Вход в режим правки уже мутирует БД, независимо от исхода.**
  `markSessionAsDraftByUuid` вызывается сразу в `ScanningStart`, до какого-либо
  действия пользователя — открытие карточки «на посмотреть» и последующий
  выход БЕЗ штатного завершения (см. «Открытые вопросы» про убитый процесс)
  оставляет сессию в `readyToSend = false`, невидимой в хабе «В работе»
  (который показывает только `readyToSend == true`), до следующего успешного
  прохождения любого из двух путей завершения.
- **`sessionUuid` не меняется ни одним из двух путей** — это единственный
  структурный признак, отличающий `UPDATE_OK` этого файла от `CREATE_OK`
  [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md); оба пути
  используют один и тот же `UnsentReportAnimalsDao.markSessionReadyToSendByUuid`.
- **Путь A нормализует `time` всех строк сессии к единому `sessionStartTime`;
  путь B не трогает `time` вовсе.** Расхождение затрагивает только точное
  значение `time` каждой строки — группировка по `sessionUuid` (хаб, отчёт)
  не зависит от точности этого поля, но факт расхождения — реальный, не
  гипотетический (см. шаги 9 vs 13).
- **Путь B не даёт пользователю никакой обратной связи.** Ни снэкбара, ни
  автоматического перехода на `InventoryReportDetailsPage` — контраст с
  путём A, у которого оба этих эффекта есть.
- **`_canPersistSession` не может стать `false` в edit-режиме** внутри этого
  bloc'а — единственный код, сбрасывающий `place`
  (`ScanningEventChangePlace`, ветка `_isInventory && !_data.isEditMode`),
  требует `isEditMode == false`; для этого сценария (`isEditMode == true` с
  момента `ScanningStart`) «тихий no-op» из
  [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) (место не
  выбрано → `ScanningExit` без сохранения) структурно недостижим.
- Ни один из двух путей завершения не делает сетевого вызова и не проверяет
  состояние сети — сохранение полностью локальное.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба пути завершения правки (A и B) полностью реализованы в коде и
исполняются при обычной навигации. Находки, перечисленные в «Открытые
вопросы и ограничения» (в первую очередь — несовпадение фильтров
`PlaceRepository.getAllWithThisFarmId`/`getById` и риск «зависшей» сессии при
аварийном завершении процесса), не блокируют исполнение штатного сценария —
они сужают его надёжность в конкретных граничных случаях.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `UnsentInventoriesPage._openEditMode`, `_InventorySessionCard.onTap` | CURRENT | вход — тап по карточке уже сохранённой сессии; навигация без ожидания (`await`) результата |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | источник `item.farmWithDetails`/`item.placeId`/`item.sessionUuid`, передаваемых в аргументы визарда |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmId` (фильтрует `isDeleted`), `.getById` (не фильтрует) | CURRENT | расхождение фильтров — источник находки про несопоставимое место, см. «Открытые вопросы» |
| `lib/pages/scanning/scanning_page.dart` | `ScanningPageArgs.inventory`, `_ScanningPageState.build` (`WillPopScope.onWillPop`), `BlocConsumer.listener` (ветка `ScanningExit`) | CURRENT | точка входа визарда, гейт «уход назад», навигация к отчёту после пути A |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningStart>` (ветка `editSessionUuid`), `on<ScanningEventAddAnimal>`, `on<ScanningEventSave>`, `close()`, `_canPersistSession`, `_isInventory`, `_markSessionReadyToSend`, `_persistDraftScanReports`, `_loadSessionFromStorage` | CURRENT | ядро сценария — оба пути завершения правки |
| `lib/pages/scanning/scanning_event.dart` | `ScanningStart` (`editPlaceId`, `editSessionUuid`), `ScanningEventSave` | CURRENT | входные параметры edit-режима |
| `lib/pages/scanning/scanning_state.dart` | `ScanningExit`, `ScanningSuccess` | CURRENT | `ScanningExit` — путь A; путь B не эмитит ни одно из этих состояний |
| `lib/pages/scanning/steps/inventory_scan_step_page.dart` | `_InventoryScanStepPageState._finishScan` | CURRENT | кнопка «Завершить» — путь A, без диалога подтверждения |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `markSessionAsDraftByUuid`, `getSessionReportsByUuid`, `replaceDraftSessionByUuid`, `markSessionReadyToSendByUuid` | CURRENT | персист-примитивы, общие для обоих путей |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `markSessionAsDraftByUuid`, `getBySessionUuid`, `deleteDraftBySessionUuid`, `markSessionReadyToSendByUuid` | CURRENT | SQL-уровень; `deleteDraftBySessionUuid` фильтрует `readyToSend == false` |
| `/Users/pavelsmirnov/.pub-cache/hosted/pub.dev/flutter_bloc-9.1.1/lib/src/bloc_provider.dart` | `BlocProvider` (`dispose: (_, bloc) => bloc.close()`) | CURRENT (внешний пакет `flutter_bloc`) | синхронная сигнатура `dispose` — `Future`, возвращаемый `close()`, не ожидается; ключевой механизм пути B |

## Критерии приёмки

- Открытие сессии через `editSessionUuid`/`editPlaceId` (при успешном
  резолве места) немедленно, до какого-либо действия пользователя, переводит
  все строки `UnsentReportAnimals` этого `sessionUuid` в `readyToSend ==
  false` (`markSessionAsDraftByUuid`) и восстанавливает `scannedAnimals` в
  состоянии из уже сохранённых строк (`getSessionReportsByUuid`), с
  `isEditMode == true`.
- Завершение путём A (`ScanningEventSave` при `sessionUuid != null`) вызывает
  `markSessionReadyToSendByUuid(sessionUuid)` ровно один раз, с тем же
  `sessionUuid`, с которым сессия была открыта (новый `sessionUuid` не
  создаётся), и эмитит `ScanningExit` с тем же `sessionUuid`.
- Завершение путём B (`ScanningBloc.close()` при `isEditMode == true` и
  `_canPersistSession == true`) вызывает `markSessionReadyToSendByUuid(sessionUuid)`
  ровно один раз, с тем же `sessionUuid`, **без** вызова
  `replaceDraftSessionByUuid` и **без** эмита какого-либо состояния.
- Оба пути в итоге оставляют один и тот же набор строк (тот же `sessionUuid`)
  с `readyToSend == true` — без новых или задублированных строк.
- Только путь A запускает автоматический переход на
  `InventoryReportDetailsPage`; путь B не переходит никуда, не показывает
  снэкбар и не эмитит `ScanningExit`.

## Связанные тесты

- `test/pages/scanning_bloc_test.dart`, group `'UC-123 — ScanningStart
  (editSessionUuid)'` (старая нумерация — переименуется отдельным
  контролируемым проходом, не трогать сейчас), test `'editSessionUuid задан,
  сессия найдена с животными -> восстанавливает scannedAnimals и
  openAnimalsStep'` — покрывает только вход в режим правки (`ScanningStart`):
  проверяет `state.data.isEditMode == true` и
  `state.data.scannedAnimals.single.transponderId == '333'`. Не покрывает ни
  один из двух путей завершения правки. Собственный комментарий теста
  честно фиксирует это: `// close() персистит сессию заново, т.к.
  isEditMode:true после этого теста.` — `markSessionReadyToSendByUuid`
  застаблен исключительно для того, чтобы `addTearDown(bloc.close)` не упал
  на немокнутом вызове мока; ни один `verify(...)` не проверяет ни сам факт
  вызова, ни переданный ему `sessionUuid`.
- **TBD — теста нет** на путь A (явный `ScanningEventSave` при уже открытой
  edit-сессии). Единственное место, где `markSessionReadyToSendByUuid`
  застаблен именно для сценариев с диспатчем `ScanningEventSave`, —
  `stubPersistCalls()`/`buildStartedBlocWithPlace()` — но обе фикстуры всегда
  строят **свежую** (не-edit) сессию; ни один тест не комбинирует
  `editSessionUuid` (edit-режим) с последующим `ScanningEventSave` и не
  проверяет через `verify`, что `markSessionReadyToSendByUuid` вызван с тем
  же `sessionUuid`. Тот же обработчик используется и для
  [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) — пробел
  общий для обоих сценариев, не специфичен для правки.
- **TBD — теста нет** на путь B (`ScanningBloc.close()` при `isEditMode ==
  true`) вовсе — ни вызов `markSessionReadyToSendByUuid` не проверяется через
  `verify`, ни отсутствие эмита состояния не проверяется явно каким-либо
  тестом.
- **TBD — теста нет** на альтернативную ветку «место не резолвится в
  `_data.places` по `editPlaceId`» (см. «Открытые вопросы») — ни в
  `scanning_bloc_test.dart`, ни в `unsent_inventories_cubit_test.dart` нет
  фикстуры, где `PlaceRepository.getAllWithThisFarmIdWithAnimals` не содержит
  место, которое при этом успешно резолвится `PlaceRepository.getById`.

## Открытые вопросы и ограничения

- **Программно воспроизводимый сбой входа в правку через несовпадение
  фильтров `PlaceRepository`.** `getAllWithThisFarmId` (использован внутри
  `getAllWithThisFarmIdWithAnimals`, источник `event.farm.placesWithAnimals`
  для `ScanningBloc`) фильтрует `farmId.isValue(farmId) &
  isDeleted.isNotValue(true)` — исключает мягко удалённые места и места,
  чей `farmId` не совпадает с ожидаемым. `getById` (использован в
  `UnsentInventoriesCubit.load` при построении карточки хаба) фильтрует
  только по `idRemote`, **без** проверки `isDeleted`. Если место, на которое
  ссылается ещё не отправленная сессия, стало мягко удалено (или сменило
  `farmId`) уже после создания сессии, но карточка сессии всё ещё строится
  успешно (`getById` его находит) — при открытии на правку `_data.places`
  (построенный через `getAllWithThisFarmIdWithAnimals`) этого места не
  содержит, `place = _data.places.where(...).firstOrNull` возвращает `null`,
  и пользователь вместо экрана правки конкретной сессии молча попадает в
  обычный (не-edit) визард выбора места — без единой строки лога, снэкбара
  или иной индикации (см. «Альтернативные потоки»). Не воспроизведено тестом
  (см. «Связанные тесты»), не разбирается глубже в рамках этого файла.
- **Отсутствие обратной связи пользователю на пути B.** В отличие от пути A,
  уход «назад» не показывает ни снэкбар, ни автоматический переход к отчёту —
  пользователь физически не может отличить (без реального обращения к хабу
  и его ручному обновлению) «сессия сохранена» от «сессия осталась в
  черновике». Асимметрия — осознанная или недосмотр — не зафиксирована в
  коде явно, только выводится из наблюдаемого поведения.
- **Риск «зависшей» сессии при аварийном завершении процесса.**
  `markSessionAsDraftByUuid` (шаг 4) выполняется синхронно с открытием
  экрана правки; единственная операция, возвращающая сессию в
  `readyToSend = true`, находится либо в `ScanningEventSave`, либо в
  `ScanningBloc.close()`, оба из которых требуют штатного жизненного цикла
  Flutter-виджета (`dispose`). Если процесс уничтожается между этими двумя
  моментами (не гарантированно перехватываемое событие для Dart-кода —
  например принудительное закрытие задачи ОС), сессия остаётся
  `readyToSend = false` на неопределённый срок — невидимой в хабе «В работе»
  (который показывает только `readyToSend == true`) до следующего успешного
  повторного прохождения через тот же `sessionUuid`. Похожий класс
  осиротевших черновых строк уже задокументирован в
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) для другого
  триггера (смена места посреди новой сессии) — здесь тот же итоговый риск,
  другой триггер. Не воспроизведено тестом, не разбирается глубже.
- **Расхождение нормализации `time` между путями A и B.** Путь A
  перезаписывает `time` всех строк сессии единым `sessionStartTime`; путь B
  не трогает `time` вообще (см. «Бизнес-правила»). Ни один известный экран
  чтения (хаб, итоговый отчёт) не демонстрирует зависимости от точности этого
  поля на уровне пройденных секций, но расхождение — реальный, не
  гипотетический факт кода, не разбирается глубже.
- **Хаб «В работе» не обновляется автоматически после правки.**
  `UnsentInventoriesPage._openEditMode` не дожидается (`await`) результата
  навигации и не переподписывается ни на что после возврата — единственный
  способ увидеть актуальный список после любого из путей завершения правки —
  ручной `RefreshIndicator` либо полное пересоздание страницы (повторный
  вход в хаб). Не разбирается глубже в рамках этого файла.
