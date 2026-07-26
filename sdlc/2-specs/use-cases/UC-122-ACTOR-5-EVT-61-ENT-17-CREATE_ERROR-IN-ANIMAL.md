# UC-122 — `ScanningEventSave` тихо не сохраняет сессию инвентаризации, если выбранное место ещё не синхронизировано (визард закрывается как при успехе); отдельная ветка — исключение при персисте

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь завершает визард инвентаризации (`ScanningPage`/`InventoryScanStepPage`,
кнопка «Завершить») — `ScanningBloc.on<ScanningEventSave>`. Весь обработчик
защищён общим приватным геттером `_canPersistSession` (`_data.farm?.remoteId
!= null && _data.place?.place.idRemote != null && _data.scanningType !=
null`), который также используется `_persistDraftScanReports`,
`_loadSessionFromStorage` и доперсистом в `close()`. Здесь разобраны два
независимо проверенных чтением кода отказа одного и того же обработчика:

- **(основной поток)** — `_canPersistSession == false` в момент `Save`
  (реально достижимо для настоящей `'inventory'`-сессии, когда выбранное
  место ещё не синхронизировано с сервером, `Place.idRemote == null`):
  `_markSessionReadyToSend()` не делает ни одной попытки записи в БД, но
  обработчик всё равно эмитит `ScanningExit` — ровно так же, как при
  успешном сохранении, без единого сообщения пользователю о том, что ничего
  не сохранено;
- **(альтернативная ветка (а))** — genuine исключение внутри `try` (например,
  ошибка Drift/DAO при `replaceDraftSessionByUuid`/`markSessionReadyToSendByUuid`):
  `catch` логирует через `Talker` и эмитит `ScanningMessage('an_error_data')`
  — видимая пользователю ошибка, но визард **не** закрывается.

Оба случая дают `RESULT = CREATE_ERROR` для [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
(сессия не становится `readyToSend`), но наблюдаемое пользователем поведение
принципиально разное — от полностью незаметного отказа до явного, но не
закрывающего экран сообщения.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `ScanningBloc` нигде не
проверяет статус авторизации. Сохранение полностью локальное — сетевых
вызовов в этом обработчике нет.

## CURRENT

### Основной поток

1. Пользователь настраивает структуру фермы локально (`FarmsAndPlacesBloc`/
   `PlaceCreateCubit.addCustomPlace`) и создаёт новое место — оно сохраняется
   с `idRemote == null` (столбец `IntColumn get idRemote =>
   integer().nullable()()`, без `.withDefault`, `packages/sheep_farm_database/lib/entities/place/places.dart`) —
   сервер ещё не присвоил месту id, полный sync-проход ещё не запускался.
   Сама ферма при этом уже имеет non-null (но отрицательный) `remoteId` —
   см. [ENT-9](../entities/ENT-9-FARM-IN-FARM.md), «Новая ферма получает
   отрицательный локальный `remoteId`» — поэтому дальше по тексту гейт
   `_canPersistSession` реально спотыкается только о место, не о ферму.
2. Пользователь открывает это место (`PlaceToolbarActions`,
   `lib/pages/place/widgets/place_actions_widget.dart`) → плитка «События» →
   `Routes.operations` (`OperationsPageArgs(place: placeWithAnimals.place)`)
   — без какой-либо проверки/фильтра по `idRemote`.
3. На `OperationsPage` — плитка «Инвентаризация» →
   `context.pushNamed2(Routes.scanning, extra: ScanningPageArgs.inventory(place:
   place, inventoryLabel: l10n.inventory))`. `ScanningPageArgs.inventory` —
   единственный конструктор аргументов этой страницы; `scanningTypes` у него
   всегда ровно один элемент, `ScanningType(id: 3, type: 'inventory')` — тип
   сканирования никогда не остаётся неопределённым на этом входе.
4. `ScanningPage.build` создаёт `ScanningBloc()..add(ScanningStart(farm: null,
   place: place, scanningTypes: [...инвентаризация...]))`.
5. `ScanningBloc.on<ScanningStart>`: `selectedScanningType` резолвится сразу
   (единственный элемент, `event.scanningTypes.length == 1`) — `_data.scanningType`
   не бывает `null` на этом входе. `farm = await
   _farmRepository.getById(event.place!.farmId)` — резолвит ту же (возможно
   ещё не синхронизированную) ферму; её `remoteId` отрицательный, но не
   `null` — проверку `farm?.remoteId != null` это проходит. `places = await
   _placeRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)` →
   `PlaceRepository.getAllWithThisFarmId` фильтрует только по `farmId`/`isDeleted`,
   без всякого условия на `idRemote` — несинхронизированное место попадает в
   список наравне с остальными. `presetPlace = places.where((p) =>
   p.place.idRemote == event.place!.idRemote).firstOrNull` — оба `idRemote`
   равны `null`, сравнение `null == null` истинно — `presetPlace` резолвится
   в то же (несинхронизированное) место.
6. `_data = _data.copyWith(..., place: presetPlace, skipPlaceStep: presetPlace
   != null)` — поскольку `presetPlace != null`, `skipPlaceStep = true`, и шаг
   «место» (`ScanningStep.place`) целиком пропускается
   (`ScanningRegistrationData.singleSteps`) — визард сразу открывается на
   шаге сканирования (или выбора сканера, если типов больше одного). Ничто в
   UI не сигнализирует пользователю, что выбранное место не синхронизировано
   — имя места отображается нормально (`data.place?.place.name`).
7. Пользователь сканирует метки — каждая порождает `ScanningEventAddAnimal`.
   Обработчик обновляет `_data.scannedAnimals` (сразу видно в UI —
   `ScanningProgressBar`), затем вызывает `await _persistDraftScanReports()`.
   Внутри: `if (!_canPersistSession) return;` — `_canPersistSession` ложен
   (второе условие, `_data.place?.place.idRemote != null`, не выполняется) —
   метод возвращается немедленно, ни разу не вызывая
   `replaceDraftSessionByUuid`. **За всю сессию сканирования не создаётся ни
   одной строки `UnsentReportAnimals`**, сколько бы меток ни было
   отсканировано.
8. Пользователь нажимает «Завершить» (`l10n.finish`,
   `InventoryScanStepPage._finishScan` → `widget.onCompleteScan()` →
   `bloc.add(const ScanningEventSave())`).
9. `ScanningBloc.on<ScanningEventSave>`: вычисляет `sessionStartTime`
   (минимальное время среди отсканированных меток, либо `DateTime.now()`,
   если список пуст), нормализует `_data.scannedAnimals` к этому времени
   (чисто в памяти — `_data = _data.copyWith(scannedAnimals:
   normalizedAnimals)`), затем `await _markSessionReadyToSend()`.
10. `_markSessionReadyToSend()`: `if (!_canPersistSession) return now;` — та
    же самая проверка, тот же результат — метод возвращается немедленно, **не
    вызывая** ни `_persistDraftScanReports()`, ни
    `markSessionReadyToSendByUuid`/`markSessionReadyToSend`.
11. Управление возвращается в обработчик без исключения — выполнение
    безусловно продолжается к `emit(ScanningExit(time: sessionStartTime, type:
    _data.scanningType!, placeId: _data.place?.place.idRemote /* null */,
    placeName: _data.place?.place.name /* настоящее имя места */, sessionUuid:
    _isInventory ? _data.sessionUuid : null /* сгенерирован ещё в
    ScanningStart, не null */))`. Код этой ветки **нигде не проверяет
    `_canPersistSession`** — эмит `ScanningExit` не отличает удавшуюся и
    неудавшуюся попытку персиста вообще.
12. `catch`-блок не срабатывает (исключения не было); сразу после (уже вне
    `try`/`catch`, безусловно) выполняется `emit(ScanningSuccess(_data));` —
    второй emit подряд в этом же обработчике.
13. `ScanningPage`'s `BlocConsumer.listener` реагирует на оба состояния по
    очереди. На `ScanningExit`: `context.pop(state.time)` закрывает визард, и,
    поскольку `state.type.type == 'inventory' && state.time != null` (условие
    всегда истинно — `time` никогда не `null`), сразу
    `context.pushNamed2(Routes.inventoryReport, extra:
    InventoryReportPageArgs(date: state.time!, sessionUuid: state.sessionUuid,
    farmId: args!.farm?.farm.remoteId ?? args.place?.farmId, placeId:
    state.placeId /* null */))` — переход на экран итогового отчёта той же
    сессии. Второй emit (`ScanningSuccess`) на уже закрытом/размонтированном
    визарде эффекта не имеет.
14. `InventoryReportDetailsCubit.load()`: поскольку `_sessionUuid != null`,
    запрашивает `getInventoryReportsByUuid(sessionUuid)` и у
    `_unsentReportsRepository`, и у `_inventoryReportRepository` — оба
    возвращают пустой список (ни одна строка `UnsentReportAnimals` не была
    создана за всю сессию, шаг 7; `ReportAnimals`, серверный кэш, тем более
    ничего не знает об этой сессии). Пользователь видит полностью пустой
    итоговый отчёт («учтено» — 0, «отсутствует» — не сравнивается ни с чем
    осмысленным) — единственный хоть сколько-нибудь заметный побочный эффект
    отказа, но без какого-либо явного сообщения об ошибке где-либо в этом
    потоке.

### Альтернативные потоки

- **(а) Технический сбой — исключение внутри `try` обработчика
  `ScanningEventSave`.** Тот же обработчик, что и в основном потоке, но на
  этот раз `_canPersistSession == true` (место синхронизировано), и один из
  awaited вызовов внутри `_markSessionReadyToSend()` →
  `_persistDraftScanReports()` (`UnsentReportAnimalsRepository.replaceDraftSessionByUuid`/`replaceDraftSession`)
  либо `markSessionReadyToSendByUuid`/`markSessionReadyToSend` — обычные
  Drift/DAO-вызовы (`packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart`,
  `UnsentReportAnimalsDao`, без собственного `try/catch`) — бросает
  исключение (например, БД закрыта/повреждена). Исключение всплывает до
  `catch (e, st)` обработчика `ScanningEventSave`:
  `getIt<Talker>().error('при сохранении данных $e, st: $st')` логирует его
  во внутренний Talker-лог, затем `emit(ScanningMessage('an_error_data'))`.
  **`ScanningExit` в этой ветке не эмитится вовсе** — `ScanningPage`'s
  listener показывает `SnackBar` (`ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
  Text(AppLocalizations.of(context)!.tr(state.message))))`) и не закрывает
  экран — пользователь остаётся в визарде и может повторно нажать
  «Завершить». Сразу после `catch` (та же безусловная строка, что и в
  основном потоке) выполняется `emit(ScanningSuccess(_data));` — `_data.scannedAnimals`
  к этому моменту уже нормализован по времени (присвоение происходит до
  `await _markSessionReadyToSend()`), независимо от того, успел ли персист
  реально что-то записать до падения.
- **(б) `_data.place` отсутствует целиком (`null`), а не просто не
  синхронизирован — путь, воспроизведённый тестом `UC-122`.** Тест строит
  сессию через `ScanningStart(farm: ..., scanningTypes: [ScanningType(type:
  'output')])` **без** `place:` вовсе — `presetPlace` в `ScanningStart` в
  этом случае не резолвится (`event.place != null` ложно), `_data.place`
  остаётся `null` (не просто с `idRemote == null`, а полностью
  неопределённым объектом). Это тот же самый гейт `_canPersistSession` и то
  же самое поведение (`ScanningEventSave` → `ScanningExit` без персиста), что
  и в основном потоке, но тип сканирования здесь — легаси `'output'`, а не
  `'inventory'`: по [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  типы `'output'`/`'input'` нигде в `lib/` не создаются вне тестов —
  `ScanningPageArgs.inventory` (единственный реальный конструктор аргументов)
  всегда передаёт `'inventory'`. Тест — корректный и достаточный
  Bloc-уровневый якорь для самого гейта/дефекта, но не воспроизводит именно
  «несинхронизированное место» как причину для настоящей `'inventory'`-сессии
  (см. «Открытые вопросы»).
- **(в) Правка уже сохранённой сессии, когда `editPlaceId` не находит
  совпадения (`UnsentInventoriesPage._openEditMode`).** Этот вход передаёт
  `ScanningPageArgs.inventory(farm: item.farmWithDetails, editPlaceId:
  item.placeId, editSessionUuid: item.sessionUuid)` — без `place:`. В
  `ScanningStart`: `if (event.editSessionUuid != null && selectedScanningType
  != null) { final place = _data.places.where((p) => p.place.idRemote ==
  event.editPlaceId).firstOrNull; if (place != null) { ...isEditMode: true,
  skipPlaceStep: true, sessionUuid: event.editSessionUuid... } }` — если
  `item.farmWithDetails.placesWithAnimals` не содержит место с этим
  `idRemote` (устаревший/несовпадающий кэш фермы), весь блок `if (place !=
  null)` пропускается целиком: `_data.place`, `_data.isEditMode`,
  `_data.sessionUuid` остаются на значениях по умолчанию (`null`/`false`/`null`)
  — визард продолжается как **новая** (не edit) сессия, показывая шаг
  «место», вместо восстановления той, которую пользователь пришёл
  редактировать. Если пользователь на этом шаге выбирает то же (или любое
  другое) несинхронизированное место — применяется тот же основной поток
  этого файла. Реальная достижимость этого расхождения кэша фермы отдельно
  не проверялась (см. «Открытые вопросы»).

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — сущность сегмента `ENT`: ни в основном потоке, ни в
  ветке (а) не появляется ни одной строки `UnsentReportAnimals` с
  `readyToSend = true` для этой попытки; в основном потоке — вообще ни одной
  строки для всей сессии (ни черновика, ни готовой к отправке).
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — только
  читается; именно его поле `idRemote` (`int?`, `null` до первой
  синхронизации места) — точная причина, по которой `_canPersistSession`
  ложен в основном потоке, при полностью нормальном, видимом пользователю
  выборе места.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только читается;
  `remoteId` несинхронизированной фермы — отрицательное, но не `null`
  значение, поэтому в реально достижимом сценарии эта часть гейта
  `_canPersistSession` не является практической причиной отказа.

### Бизнес-правила

- **Один и тот же приватный гейт `_canPersistSession` разделяют четыре разных
  места кода**: `_persistDraftScanReports` (каждый скан),
  `_markSessionReadyToSend` (завершение), `_loadSessionFromStorage`
  (восстановление черновика при смене места/входе в правку) и доперсист в
  `close()` (уход назад в режиме правки) — все молча ничего не делают, если
  гейт ложен, ни один не логирует и не сигнализирует об этом наружу.
- **Гейт проверяет не «место выбрано», а «у выбранного места есть серверный
  id».** Место, полностью корректно выбранное и отображаемое в UI (имя
  видно, шаг «место» может быть даже пропущен через `presetPlace`), всё равно
  проваливает `_canPersistSession`, если оно ещё не прошло синхронизацию с
  сервером — состояние, штатно достижимое в этом offline-first приложении
  (создать структуру фермы локально и сразу начать инвентаризацию, не
  дожидаясь sync-прохода).
- **Ни один скан за такую сессию не персистится**, не только финальное
  сохранение — `ScanningEventAddAnimal` использует тот же гейт, поэтому вся
  сессия существует исключительно в оперативной памяти блока (`_data.scannedAnimals`)
  до самого закрытия визарда.
- `emit(ScanningExit(...))` в обработчике `ScanningEventSave` не имеет
  условия на `_canPersistSession` вовсе — код одинаково закрывает визард и
  после реального сохранения, и после того, как персист был полностью
  пропущен.
- Второй `emit(ScanningSuccess(_data))` в конце обработчика выполняется
  безусловно в обеих ветках (основной поток и ветка (а)) — после `ScanningExit`
  он не имеет видимого эффекта (визард уже закрыт), после `ScanningMessage`
  в ветке (а) он оставляет визард в обычном рабочем состоянии.
- В основном потоке `ScanningExit.time` никогда не `null` (по умолчанию —
  `DateTime.now()`), поэтому переход на экран итогового отчёта
  (`Routes.inventoryReport`) в `ScanningPage`'s listener срабатывает
  безусловно для любой `'inventory'`-сессии, включая эту неудавшуюся —
  единственный хоть как-то заметный пользователю след отказа, но без единого
  явного сообщения об ошибке.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба сценария (основной поток и ветка
(а)) воспроизводятся статическим чтением кода:
`ScanningBloc.on<ScanningEventSave>` → `_markSessionReadyToSend` →
`_canPersistSession`/`_persistDraftScanReports`/`UnsentReportAnimalsRepository`.
Возможное исправление (например, показ `ScanningMessage`, когда персист был
пропущен из-за `_canPersistSession == false`, либо блокировка кнопки
«Завершить» для несинхронизированного места) в рамках этого документирующего
прохода не выполняется — это фиксация уже существующего кода, а не работа
над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/place/widgets/place_actions_widget.dart` | `PlaceToolbarActions` (плитка «События») | CURRENT | вход к `OperationsPage` для любого места, без фильтра по `idRemote` |
| `lib/pages/operations/operations_page.dart` | плитка «Инвентаризация» (`onTap` → `Routes.scanning`) | CURRENT | реальный вход №1 — новая сессия, `ScanningPageArgs.inventory(place: place, ...)` |
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `_openEditMode` | CURRENT | реальный вход №2 — правка сессии, `ScanningPageArgs.inventory(farm:, editPlaceId:, editSessionUuid:)`; ветка (в) |
| `lib/pages/scanning/scanning_page.dart` | `ScanningPageArgs.inventory`, `_ScanningPageState.build` (`BlocConsumer.listener` — `ScanningExit`/`ScanningMessage`) | CURRENT | единственный реальный конструктор аргументов (всегда `type: 'inventory'`); закрытие визарда и переход на `Routes.inventoryReport` по `ScanningExit`, `SnackBar` по `ScanningMessage` |
| `lib/pages/scanning/steps/inventory_scan_step_page.dart` | `InventoryScanStepPage._finishScan`, `onCompleteScan` | CURRENT | кнопка «Завершить», диспатчит `ScanningEventSave` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningStart>` | CURRENT | резолвит `farm`/`presetPlace`/`skipPlaceStep`, включая случай несинхронизированного места (`idRemote == null == null`) |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventAddAnimal>`, `_persistDraftScanReports` | CURRENT | каждый скан обновляет `_data` в памяти и пытается персистить черновик — молча пропускается тем же гейтом |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>`, `_markSessionReadyToSend`, `_canPersistSession` | CURRENT | ядро сценария — общий гейт, безусловный `emit(ScanningExit(...))`, `try/catch` вокруг персиста, безусловный второй `emit(ScanningSuccess(_data))` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.replaceDraftSession`, `replaceDraftSessionByUuid`, `markSessionReadyToSend`, `markSessionReadyToSendByUuid` | CURRENT | вызываются только при `_canPersistSession == true`; потенциальный источник исключения для ветки (а) |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao` | CURRENT | Drift/DAO-слой под репозиторием — без собственного `try/catch` |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places.idRemote` | CURRENT | `int?`, без `.withDefault` — `null` у не синхронизированного места, точная причина отказа гейта |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmId`, `getAllWithThisFarmIdWithAnimals` | CURRENT | не фильтрует места по `idRemote` — несинхронизированное место возвращается наравне с остальными |
| `lib/pages/animals_inventory/presentation/inventory_report__details_page.dart` | `InventoryReportPageArgs` | CURRENT | аргументы экрана, на который безусловно переходит `ScanningExit` для `'inventory'`-сессий |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | при непустом `sessionUuid` запрашивает отчёты только по нему — для этого сценария оба источника возвращают пустой список |

## Критерии приёмки

- Если в момент обработки `ScanningEventSave` `_data.place?.place.idRemote ==
  null` (несинхронизированное место), при этом `_data.farm?.remoteId != null`
  и `_data.scanningType != null` (как всегда для реально достижимого
  `'inventory'`-входа) — `_markSessionReadyToSend()` возвращается, ни разу не
  вызвав `_persistDraftScanReports()`, `markSessionReadyToSendByUuid` или
  `markSessionReadyToSend`.
- В этом случае обработчик тем не менее эмитит `ScanningExit` с той же
  формой, что и после настоящего успеха (кроме `placeId`, который равен
  `null`), затем безусловно — `ScanningSuccess(_data)`; `ScanningMessage` не
  эмитится ни разу.
- За всю сессию (от первого скана до «Завершить») в `UnsentReportAnimals` не
  появляется ни одной строки.
- `ScanningPage` закрывает визард и переходит на `Routes.inventoryReport`;
  `InventoryReportDetailsCubit.load()` для того же `sessionUuid` не находит
  ни одной строки ни в `UnsentReportAnimals`, ни в `ReportAnimals`.
- Если тот же обработчик, при `_canPersistSession == true`, ловит исключение
  из `_markSessionReadyToSend()` — `getIt<Talker>().error(...)` вызывается
  ровно один раз, эмитится `ScanningMessage('an_error_data')`, `ScanningExit`
  не эмитится вовсе, затем безусловно эмитится `ScanningSuccess(_data)`;
  визард остаётся открытым.

## Связанные тесты

- `test/pages/scanning_bloc_test.dart`, group `'UC-122 — ScanningBloc.ScanningEventSave
  (известный дефект — тихий no-op)'`, test `'место не выбрано
  (_canPersistSession=false) -> markSessionReadyToSend НЕ вызван, но
  ScanningExit эмитится как при успехе'` — подтверждает сам гейт
  `_canPersistSession` и безусловный `ScanningExit` на уровне Bloc'а через
  `verifyNever` на `markSessionReadyToSend`/`replaceDraftSession`. Тест
  строит прецедент через `buildStartedBlocWithoutPlace()` — сессию **без
  какого-либо** `place` (не просто с несинхронизированным `idRemote`) и с
  легаси типом `'output'`, а не `'inventory'` — то есть механически
  подтверждает ветку (б) этого файла, а не «несинхронизированное место»,
  прослеженную как основной поток (см. «Открытые вопросы»).
- **TBD — теста нет** на основной поток именно с `type: 'inventory'` и
  `place.idRemote == null` (несинхронизированное, но выбранное место) —
  ни один существующий тест `scanning_bloc_test.dart` не строит
  `PlaceWithAnimals`/`Place` с `idRemote: null` для инвентаризационного типа.
- **TBD — теста нет** на ветку (а) (исключение внутри `try` обработчика
  `ScanningEventSave` — например, мок `UnsentReportAnimalsRepository`,
  бросающий `Exception` из `replaceDraftSessionByUuid`/`markSessionReadyToSendByUuid`) —
  ни `'an_error_data'`, ни `ScanningMessage`, ни `throw`/`Exception` не
  встречаются в `scanning_bloc_test.dart`.
- **TBD — теста нет** на ветку (в) (`editPlaceId` без совпадения в
  `_data.places` при входе через `editSessionUuid`) — существующий тест
  группы `'UC-123 — ScanningStart (editSessionUuid)'` в этом же файле
  проверяет только случай, когда место **находится**.

## Открытые вопросы и ограничения

- **Тест демонстрирует гейт `_canPersistSession`, но не его практически
  достижимый для `'inventory'`-сессий механизм.** Тест `UC-122` доводит
  `_data.place` до `null` целиком, используя легаси тип `'output'`, который,
  по [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), нигде
  не создаётся вне тестов. Основной поток этого файла прослеживает другой,
  реально достижимый через `ScanningPageArgs.inventory` (единственный
  реальный конструктор, всегда `'inventory'`) механизм — не отсутствующее, а
  ещё не синхронизированное место (`idRemote == null`). Оба механизма бьют в
  один и тот же булев гейт и дают одно и то же наблюдаемое поведение, но ни
  один тест не воспроизводит именно второй, реально достижимый вариант.
- **Достижимость `_data.place == null` (а не просто несинхронизированного
  места) через настоящую навигацию не подтверждена.** Оба обнаруженных в
  `ScanningStart` `.firstOrNull`-поиска (по `event.place!.idRemote` для новой
  сессии; по `event.editPlaceId` для правки, ветка (в)) в принципе могут не
  найти совпадения и оставить `_data.place` полностью `null`, но в обоих
  случаях `skipPlaceStep` остаётся `false`, и шаг «место»
  (`SelectPlaceStepPage.onSelectPlace`) — единственный путь к шагу
  «сканирование» — сам устанавливает `_data.place` перед переходом дальше.
  Единственный теоретически оставшийся путь — гонка между синхронным
  `toNextStep()` этого коллбэка и асинхронным эмитом обновлённого состояния
  `ScanningEventChangePlace` — не воспроизведена и не проверялась
  widget-тестом.
- **Уточнение к тексту [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).**
  Инвариант «Черновик персистится на каждый скан, не только при завершении»
  там сформулирован безусловно; этот файл фиксирует, что на практике он сам
  обусловлен `_canPersistSession` — пока выбранное место не синхронизировано,
  ни один скан не персистится вообще, даже черновиком. `ENT-17` — заморожен,
  это уточнение не редактирует его, а дополняет здесь.
- **Ветка (в) (расхождение кэша фермы при `editPlaceId`) не проверялась на
  практическую вероятность** — насколько часто `item.farmWithDetails.placesWithAnimals`,
  переданный из `UnsentInventoriesCubit.load()`, может не содержать место,
  на которое ссылается `item.placeId`, отдельно не исследовалось.
- Не проверено эмпирически на реальном запуске (только статическое чтение
  кода) — в частности, поведение `PlaceRepository.getAllWithThisFarmIdWithAnimals`
  и сопоставление `null == null` для `idRemote` в `ScanningStart` не
  прогонялось через реальную Drift-БД с фикстурой несинхронизированного
  места, только прослежено построчно.
