# UC-131 — Пользователь открывает итоговый отчёт инвентаризации (после сканирования или из посуточного календаря)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Один и тот же экран (`InventoryReportDetailsPage`/`InventoryReportDetailsView`,
подкреплённый `InventoryReportDetailsCubit.load()`) равнозначно открывается
двумя разными путями:

- **(а) сразу после завершения сессии сканирования** — `ScanningPage`
  реагирует на `ScanningExit` с `type.type == 'inventory'`
  (`lib/pages/scanning/scanning_page.dart`), автоматический переход, без
  отдельного действия пользователя «открыть отчёт»;
- **(б) из посуточного отчёта календаря** —
  `ReportsDayListPopulated._navigateItem` реагирует на тап по
  `InventoryDayItem`
  (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`).

Оба пути строят один и тот же `InventoryReportPageArgs` (`date`,
`sessionUuid?`, `farmId?`, `placeId?`) и передают его в один и тот же
`InventoryReportDetailsCubit`, который принимает **либо** `sessionUuid`
(режим «по сессии»), **либо**, при его отсутствии, `date`+`placeId` (режим
«по дате») — два разных, не пересекающихся кода загрузки внутри одного
`load()`. Экран строит 4 секции (учтено/отсутствует/чужие метки/неизвестные
номера) **без ограничения по ферме** при сопоставлении метки с животным — в
отличие от живого сканирования, инвариант уже зафиксирован в
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни
`InventoryReportDetailsCubit`, ни `UnsentReportAnimalsRepository`, ни
`ReportAnimalsRepository` не проверяют статус авторизации нигде на этом
пути (`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart`,
`lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart`
и `lib/pages/report/report_animals_repository.dart` не находит ни одного
совпадения).

## CURRENT

### Основной поток

**Вход A — сразу после завершения сканирования.**

1. `ScanningBloc.on<ScanningEventSave>` эмитит `ScanningExit(time:
   sessionStartTime, type: _data.scanningType!, placeId:
   _data.place?.place.idRemote, placeName: ..., sessionUuid: _isInventory ?
   _data.sessionUuid : null)`. Для инвентаризации `_data.sessionUuid`
   заполняется безусловно уже в `on<ScanningStart>` — либо новым `Uuid().v4()`
   (новая сессия), либо `event.editSessionUuid` (правка) — то есть на этом
   пути `sessionUuid` в `ScanningExit` практически всегда непуст (см.
   «Открытые вопросы» о единственном отличающемся случае).
2. `ScanningPage`'s `BlocConsumer.listener` на `ScanningExit`: `context.pop(
   state.time)` закрывает визард сканирования, затем, при `state.type.type ==
   'inventory' && state.time != null` (оба условия истинны на этом пути),
   `context.pushNamed2(Routes.inventoryReport, extra:
   InventoryReportPageArgs(date: state.time!, sessionUuid: state.sessionUuid,
   farmId: args!.farm?.farm.remoteId ?? args.place?.farmId, placeId:
   state.placeId))` — `farmId` берётся не из `ScanningExit` (там его нет), а
   из исходных аргументов входа в визард сканирования.

**Вход B — из посуточного отчёта календаря.**

3. `reports_day_query.dart` строит `InventoryDayItem` построчно из
   `ReportAnimal`/`UnsentReportAnimal` за конкретное место и день, группируя
   строки по `sessionUuid` (`byUuid`) — каждая группа с непустым `sessionUuid`
   даёт один `InventoryDayItem(sessionUuid: entry.key, farmId: data.farmId,
   placeId: placeId, ...)`; строки без `sessionUuid` (легаси) собираются в
   отдельную ветку и дают `InventoryDayItem` **без** `sessionUuid`, но с теми
   же непустыми `farmId`/`placeId` (см. «Открытые вопросы» о том, что эта
   легаси-ветка — единственный реально достижимый способ получить
   `sessionUuid == null` при переходе на этот экран).
4. `ReportsDayListPopulated._navigateItem`, ветка `case InventoryDayItem(:date,
   :sessionUuid, :farmId, :placeId)`: `context.pushNamed2(Routes.inventoryReport,
   extra: InventoryReportPageArgs(date: date, sessionUuid: sessionUuid,
   farmId: farmId, placeId: placeId))` — прямая передача полей элемента без
   дополнительной обработки.

**Общее продолжение (оба входа сходятся в `InventoryReportDetailsCubit.load`).**

5. `InventoryReportDetailsView.build` читает
   `GoRouterState.of(context).getExtraByName<InventoryReportPageArgs>(
   Routes.inventoryReport)` и создаёт `BlocProvider(create: (context) =>
   InventoryReportDetailsCubit(date: args.date, sessionUuid: args.sessionUuid,
   farmId: args.farmId, placeId: args.placeId)..load())`.
6. `load()` сразу эмитит сброшенное состояние `InventoryReportDetailsState(
   date: state.date)` (все остальные поля — дефолты, включая `isLoading:
   false` — см. «Открытые вопросы», этот сброс не включает признак загрузки).
7. Ветвление по `_sessionUuid`:
   - **режим «по сессии»** (`_sessionUuid != null`, единственный реально
     достижимый режим для входа A и для входа B с непустым `sessionUuid`):
     `reports` собирается из двух источников без какого-либо фильтра по
     `placeId`/`farmId` — `_unsentReportsRepository.getInventoryReportsByUuid(
     sessionUuid)` (`UnsentReportAnimalsDao.getBySessionUuid`, ещё не
     отправленные строки той же сессии, замапленные `_fromUnsent` в
     `ReportAnimal`) **плюс**
     `_inventoryReportRepository.getInventoryReportsByUuid(sessionUuid)`
     (`ReportAnimalsDao.getAllByFilters(types: ['inventory'],
     sessionUuid: sessionUuid)`, уже подтверждённые сервером строки той же
     сессии) — оба набора объединяются без дедупликации;
   - **режим «по дате»** (`_sessionUuid == null`, единственный реально
     достижимый способ — легаси-ветка входа B, см. «Открытые вопросы»):
     `sentByDate = _inventoryReportRepository.getInventoryReportsByDate(
     state.date)` и `unsentByDate = _unsentReportsRepository.
     getInventoryReportsByDate(state.date)` — **оба** метода
     (`ReportAnimalsRepository.getInventoryReportsByDate`,
     `UnsentReportAnimalsRepository.getInventoryReportsByDate`) фильтруют
     строки не только по календарному дню (`DateUtils.dateOnly(r.time)
     .isAtSameMomentAs(dateOnly)`), но и явным условием `r.sessionUuid ==
     null` — то есть в этом режиме принципиально не могут попасть строки
     современной (post-миграция v87/88) сессии, только легаси-строки без
     `sessionUuid`; оба результата затем дополнительно фильтруются по
     `_placeId` (`.where((r) => _placeId == null || r.placeId == _placeId)`).
8. `getIt.get<Talker>().info(...)` логирует `date`/`sessionUuid`/количество
   найденных строк.
9. Если `reports.isEmpty` — `emit(InventoryReportDetailsState(date:
   state.date))` (те же дефолты, что и на шаге 6) и `return` — справочники
   животных/идентификаций, ферма и место не запрашиваются вовсе (см.
   «Альтернативные потоки»).
10. `identificationFromReports = reports.map((e) => e.transponderId).toSet()`;
    `identifications = await _identificationsRepository.getAll()` (весь
    справочник `AnimalIdentification`, без фильтра); `otherAnimals =
    identificationFromReports.where((e) => !identifications.any((i) =>
    i.number == e)).toList()` — номера меток, которых нет **ни у одного**
    животного ни на одном месте/ферме (кандидаты в секцию «неизвестные
    номера»).
11. `animals = await _animalsRepository.getAllAnimalsWithDetailsByFilters()`
    — **без единого аргумента фильтра**: `isNotDeleted` (единственный
    небулевый дефолт метода) равен `true` по умолчанию, поэтому запрос
    реально читает **все** живые (не удалённые) животные во всей локальной
    базе, независимо от фермы/места.
12. `farm = await _farmsRepository.getById(_farmId ?? reports.first.farmId)`;
    `place = await _placesRepository.getById(_placeId ?? reports.first.placeId)`
    — по `Farm.remoteId`/`Place.idRemote`; для обоих реально достижимых
    входов (A и B) `_farmId`/`_placeId` в конструкторе кубита уже заданы
    непустыми (аргументы `InventoryReportPageArgs` заполнены на шагах 2/4), so
    `reports.first.farmId`/`.placeId` как fallback на практике не
    используется этими двумя входами.
13. Если `farm != null`: `animals.removeWhere((e) => (e.farmId !=
    farm.remoteId || (place != null && e.placeId != place.idRemote)) &&
    e.animalIdentificationNumbers.intersection(identificationFromReports)
    .isEmpty)` — животное **остаётся** в пуле, если оно (а) с этой фермы и
    (если резолвлено) с этого места, **или** (б) хотя бы одна из его меток
    встречается среди отсканированных в этой сессии, даже если животное
    физически с другого места/фермы — это и есть механизм, наполняющий
    секцию «чужие метки» (см. шаг 15 ниже и «Открытые вопросы» — что
    происходит, если `farm == null`).
14. `myAnimalsByKind = animals.fold<Map<Kind, List<AnimalWithDetails>>>({},
    (acc, e) => acc..putIfAbsent(e.kind!, () => []).add(e))` — группировка
    по виду животного (`Kind` как ключ карты; `e.kind!` — некритично
    неявное допущение, что у каждого прошедшего фильтр животного вид уже
    зарезолвлен join'ом).
15. `emit(InventoryReportDetailsState(date: state.date, allAnimals: reports,
    otherAnimals: otherAnimals, myAnimalsByKind: myAnimalsByKind, farm: farm,
    place: place))` — `isLoading` не переопределяется явно нигде в `load()`
    и остаётся дефолтным `false` на всём протяжении метода, включая период
    ожидания `await` (см. «Открытые вопросы»).
16. `InventoryReportDetailsView.build`'s `BlocBuilder` перерисовывает
    `Scaffold`: `AppBar` с заголовком `l10n.inventory` и подзаголовком —
    датой из `args.date` (не из `state.date`, те же значения на практике,
    т.к. кубит их не расходит); кнопка `share` в `actions` видна только при
    `!state.isLoading && state.myAnimalsByKind.isNotEmpty` — поскольку
    `isLoading` всегда `false` (шаг 15), это условие фактически сводится к
    «есть хотя бы одно животное в пуле».
17. `_buildBody`: `if (state.isLoading) return
    CircularProgressIndicator()` — условие никогда не истинно (см. шаг 15),
    ветка мертва на практике; тело сразу переходит к
    `_computeSections(context, state)`.
18. `_computeSections` вычисляет `scannedIds =
    state.allAnimalIdentificationNumbers` (множество `transponderId` из
    `allAnimals`) и для каждого животного из `state.myAnimalsByKind.values`:
    `isOurPlace = state.farm?.remoteId == animal.farmId &&
    state.place?.idRemote == animal.placeId`; `isScanned =
    animal.animalIdentificationNumbers.intersection(scannedIds).isNotEmpty`;
    `groupName = animal.ageGroup?.name ?? animal.kind?.name ?? '-'`;
    `displayNumber = animal.firstMainNumber`. Ветвление:
    - `isOurPlace && isScanned` → секция «учтено», сгруппированная по
      `groupName` (`scannedByAgeGroup`);
    - `isOurPlace && !isScanned` → секция «отсутствует»
      (`InventoryAbsentEntry`, порядковый `index`);
    - `!isOurPlace && isScanned` → секция «чужие метки»
      (`InventoryForeignKnownEntry`, с именем места
      `animal.place?.name ?? departmentNotSpecified`);
    - `!isOurPlace && !isScanned` — ни одна ветка не подходит, животное
      молча выпадает из всех секций (структурно недостижимо после
      фильтра шага 13, кроме случая `farm == null`, см. «Открытые
      вопросы»).
19. `unknownNumbers: state.otherAnimals` — секция «неизвестные номера»
    берётся напрямую из состояния (шаг 10), не пересчитывается в `_computeSections`.
20. `InventoryAccordionListWidget` рендерит все 4 секции: «учтено» —
    отдельный аккордеон на каждую возрастную группу; «отсутствует» — всегда
    отображается (даже с `count == 0`); «чужие метки» — единый аккордеон
    `known foreign + unknown numbers`, отображается **только** при
    `totalForeignCount > 0` (`knownForeignAnimals.length +
    unknownNumbers.length`); `ScanningProgressBar` в шапке показывает
    `_countScanned(state)`/`_countTotal(state)` — оба пересчитаны заново по
    тому же критерию `isOurPlace` (не переиспользуют секции из шага 18
    напрямую, но по тому же предикату).

### Альтернативные потоки

- **`reports.isEmpty` (шаг 9).** Ни `AnimalIdentification`, ни `Animal`, ни
  `Farm`/`Place` не запрашиваются вовсе; `state.farm`/`state.place` остаются
  `null`. `_buildBody` всё равно строит `_computeSections` (все 4 списка
  пусты) — экран показывает шапку `0/0` и раздел «Отсутствует (0)», без
  секции «чужие метки» (`totalForeignCount == 0`) и без какого-либо
  сообщения пользователю о том, что данных нет (в отличие от
  [UC-129](UC-129-ACTOR-5-EVT-65-ENT-17-READ_OK-IN-ANIMAL.md), где пустой
  список явно рендерит `ProgressMessage.notFound`). Кнопка `share` в AppBar
  скрыта (`myAnimalsByKind.isEmpty`).
- **Режим «по дате» с непустым `_placeId`, но без строк-легаси на эту дату
  и место.** `sentByDate`/`unsentByDate` после фильтра `r.sessionUuid ==
  null` пусты → тот же путь, что и «reports.isEmpty» выше. Единственный
  реально достижимый через навигацию способ получить непустой результат в
  этом режиме — легаси-строки без `sessionUuid` (см. «Открытые вопросы»).
- **`farm == null`** (`_farmsRepository.getById` не резолвит переданный
  `farmId`/`reports.first.farmId`). Шаг 13 (`if (farm != null)`) целиком
  пропускается — `animals` остаётся **нефильтрованным списком всех живых
  животных во всей локальной базе** (шаг 11), не только этой фермы. В
  `_computeSections` (шаг 18) `isOurPlace` сравнивает `null ==
  animal.farmId` — истинно только для животных без `farmId` вовсе,
  практически никогда; следствие — секция «отсутствует» на практике
  становится пустой для любых данных (ни одно животное не признаётся «нашим
  местом»), а любое отсканированное известное животное, независимо от
  фактического места, показывается в секции «чужие метки». Не покрыто
  тестом (см. «Связанные тесты»).
- **`farm != null`, но `place == null`** (место не резолвится). Условие
  `place != null && e.placeId != place.idRemote` в шаге 13 всегда ложно —
  фильтр ослабляется до «животное с этой фермы (независимо от места) либо
  отсканировано» — секция «отсутствует»/«учтено» на этом пути фактически
  агрегирует все места фермы разом, не только место сессии.
- **Экспорт в Excel/PDF** (кнопка `share`, видимая при непустом
  `myAnimalsByKind`) — отдельное событие
  [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md),
  не изменяет ни одну запись `InventoryScanReport`; за границами этого
  файла.
- **Правка сессии** (`ScanningStart` с `editSessionUuid`/`editPlaceId`,
  [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)) и
  повторное завершение снова приводят на этот же экран через тот же вход A
  — не отдельный use-case, тот же код-путь этого файла целиком.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals` + `ReportAnimals`) — сущность,
  чьё состояние отображает этот экран; читается целиком по `sessionUuid` (оба
  источника, без дедупликации) либо по `date`+`sessionUuid == null`+`placeId`
  (легаси-режим); не изменяется этим сценарием.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается целиком, без фильтра
  (`_identificationsRepository.getAll()`), используется дважды: для
  вычисления «неизвестных номеров» (шаг 10) и, через
  `animal.animalIdentificationNumbers` на каждом `AnimalWithDetails`, для
  сопоставления метка↔животное во всех 4 секциях; не изменяется.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается без
  фильтра (`getAllAnimalsWithDetailsByFilters()`, `isNotDeleted: true`
  дефолт), затем сужается в памяти по ферме/месту (шаг 13); не изменяется
  этим сценарием.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — читается один
  раз по `remoteId` (`_farmId` из аргументов либо fallback на первую
  строку отчёта); не резолвленная ферма меняет поведение фильтрации, см.
  «Альтернативные потоки»; не изменяется.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается
  один раз по `idRemote` тем же паттерном, что и ферма; не изменяется.

### Бизнес-правила

- Два равнозначных, независимых входа (A — сразу после сканирования, B — из
  посуточного календаря) ведут к одному и тому же коду загрузки — вычислено
  идентично, независимо от того, какой из них привёл пользователя на экран.
- Режим «по сессии» (`sessionUuid`) — единственный реально достижимый режим
  для современных (post-миграция v87/88) данных; режим «по дате» структурно
  существует и покрыт тестом, но на живой навигации наполняется только
  легаси-строками без `sessionUuid`, потому что `getInventoryReportsByDate`
  в обоих репозиториях (`ReportAnimalsRepository`,
  `UnsentReportAnimalsRepository`) сама явно требует `r.sessionUuid == null`.
- Сопоставление метка↔животное на этом экране не ограничено фермой сессии
  так же строго, как во время живого сканирования — животное, отсканированное
  в этой сессии, но принадлежащее другой ферме/месту, остаётся в пуле и
  показывается как «известное животное с другого объекта», а не отбрасывается
  (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
  инвариант «Дублирование логики сопоставления метка↔животное»).
- `isLoading` в `InventoryReportDetailsState` — поле, которое `load()`
  никогда не выставляет в `true` ни на одном шаге; соответствующая ветка UI
  (`CircularProgressIndicator`, скрытие кнопки `share`) написана, но
  структурно недостижима при нормальном выполнении.
- Экспорт (`share`) не входит в бизнес-правила этого события — отдельное,
  явно специфицированное [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба входа (A и B) и оба режима загрузки (`sessionUuid`/`date`)
полностью реализованы и достижимы из UI; находки, перечисленные в «Открытые
вопросы и ограничения» (мёртвая ветка `isLoading`, практическая
недостижимость непустого режима «по дате», ослабление фильтра при
нерезолвленной ферме/месте), не блокируют выполнение сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/scanning/scanning_page.dart` | `_ScanningPageState.build` (`BlocConsumer.listener`, ветка `ScanningExit`) | CURRENT | вход A — автоматический переход сразу после завершения сессии сканирования |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>`, `on<ScanningStart>` | CURRENT | эмитит `ScanningExit` с `sessionUuid`; заполняет `_data.sessionUuid` на старте для любой инвентаризации |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | построение `InventoryDayItem` (группировка `byUuid`/легаси-ветка) | CURRENT | источник данных входа B — группирует строки по `sessionUuid`, легаси-строки дают `InventoryDayItem` без `sessionUuid` |
| `lib/pages/reports_day_list/data/report_day_group.dart` | `InventoryDayItem` | CURRENT | модель элемента дневного списка — `farmId`/`placeId` обязательны, `sessionUuid` опционален |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` (ветка `InventoryDayItem`) | CURRENT | вход B — тап по карточке в посуточном календаре |
| `lib/pages/animals_inventory/presentation/inventory_report__details_page.dart` | `InventoryReportPageArgs`, `InventoryReportDetailsPage` | CURRENT | аргументы точки входа экрана, общие для входов A и B |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView.build`, `_buildBody`, `_computeSections`, `_countScanned`, `_countTotal` | CURRENT | оболочка экрана; вычисление 4 секций и шапки прогресса |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | предмет этого файла — оба режима загрузки сходятся здесь |
| `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart` | `InventoryReportDetailsState`, `.allAnimalIdentificationNumbers` | CURRENT | состояние экрана; `isLoading` — недостижимая в `load()` ветка |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReportsByUuid`, `.getInventoryReportsByDate` | CURRENT | источник ещё не отправленных строк для обоих режимов; `getInventoryReportsByDate` явно требует `sessionUuid == null` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getInventoryReportsByUuid`, `.getInventoryReportsByDate` | CURRENT | источник уже подтверждённых сервером строк для обоих режимов, тот же фильтр `sessionUuid == null` в режиме «по дате» |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository.getAll` | CURRENT | весь справочник меток, без фильтра — источник «неизвестных номеров» |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | вызывается без аргументов — `isNotDeleted: true` дефолт, читает всех живых животных базы |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | резолв фермы по `remoteId`; `null` ослабляет фильтр шага 13 целиком |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById` | CURRENT | резолв места по `idRemote`; `null` ослабляет условие по месту |
| `lib/pages/scanning/widgets/inventory_accordion_list_widget.dart` | `InventoryAccordionListWidget`, `ScanningProgressBar` | CURRENT | рендер 4 секций и шапки прогресса; переиспользуется со сценарием живого сканирования |

## Критерии приёмки

- Открытие через вход A (`ScanningExit` после `ScanningEventSave` для
  инвентаризации) и через вход B (тап по `InventoryDayItem` в посуточном
  календаре) оба приводят к одному и тому же `InventoryReportDetailsCubit`
  и одному и тому же наблюдаемому состоянию для одинаковых входных данных.
- Если `_sessionUuid` задан, `load()` объединяет строки
  `UnsentReportAnimalsRepository.getInventoryReportsByUuid` и
  `ReportAnimalsRepository.getInventoryReportsByUuid` для этого
  `sessionUuid`, не вызывая ни один из методов `getInventoryReportsByDate`.
- Если `_sessionUuid` не задан, `load()` вызывает оба
  `getInventoryReportsByDate` (передавая `state.date`) и дополнительно
  фильтрует результат по `_placeId`, если он задан.
- Если объединённый список строк пуст, `identificationsRepository.getAll()`
  не вызывается, а состояние возвращается к дефолтным значениям
  (`myAnimalsByKind` пуст, `farm`/`place` — `null`).
- Если ферма резолвлена (`farm != null`), в итоговый пул `myAnimalsByKind`
  попадают только животные этой фермы/места, плюс любое животное с меткой,
  совпадающей с одной из отсканированных в сессии, независимо от его
  фактического места/фермы.
- Секция «неизвестные номера» состоит ровно из тех `transponderId`
  объединённого списка строк, для которых не нашлось ни одной
  `AnimalIdentification` с таким же `number`.
- Кнопка экспорта (`share`) в AppBar видна тогда и только тогда, когда
  `myAnimalsByKind` непуст.

## Связанные тесты

`test/pages/inventory_report_details_cubit_test.dart`:

- group `'UC-131 — InventoryReportDetailsCubit.load (по дате)'` (старая
  нумерация, будет переименована в `UC-131` отдельным контролируемым
  проходом, не трогать сейчас) — 4 теста, покрывающие режим «по дате»
  (мокая репозитории напрямую, без учёта фильтра `sessionUuid == null`
  внутри самих реальных репозиториев — см. «Открытые вопросы»):
  - `'reports пуст -> allAnimals пуст, справочники не запрашиваются'` —
    ветка «Альтернативные потоки», `reports.isEmpty`;
    `verifyNever(() => identificationsRepository.getAll())`.
  - `'reports найдены -> myAnimalsByKind сгруппирован, otherAnimals для
    непривязанных чипов'` — основной поток режима «по дате»: 2 строки
    отчёта (`T1`, `T2`), одна идентификация (`T1`), одно животное;
    `otherAnimals == ['T2']`, `myAnimalsByKind.values.single` длиной 1,
    `farm?.remoteId == 10`, `place?.idRemote == 20`.
  - `'placeId фильтр применяется к отчётам за дату'` — два отчёта с разным
    `placeId` (`20`/`30`), кубит создан с `placeId: 20`; `allAnimals`
    отфильтрован до одной строки (шаг «оба результата затем дополнительно
    фильтруются по `_placeId`»).
  - `'farm != null -> животные другой фермы без совпадения по чипу
    исключаются'` — два животных (`farmId: 10`/`farmId: 999`), ферма
    резолвится в `10`; итоговый пул содержит только животное с `farmId ==
    10` (прямое покрытие шага 13, ветвь без совпадения по метке).
- group `'UC-131 — InventoryReportDetailsCubit.load (по sessionUuid)'` (та
  же старая нумерация) — 1 тест:
  - `'sessionUuid задан -> объединяет unsent + sent отчёты,
    getInventoryReportsByDate не вызывается'` — прямое покрытие режима «по
    сессии»: одна ещё не отправленная строка (`U1`) и одна уже
    подтверждённая сервером строка (`T2`), обе с `sessionUuid: 'uuid-1'`;
    `allAnimals` длиной 2; `verifyNever` на оба метода
    `getInventoryReportsByDate` (и `sent`, и `unsent`).

**TBD — теста нет** на ветку «`farm == null`» (шаг 13 целиком пропущен,
пул животных остаётся нефильтрованным по ферме) — ни один тест файла не
мокает `farmRepository.getById` как возвращающий `null` при непустом,
резолвящемся `placeRepository.getById`.

**TBD — теста нет** на сам факт двух равнозначных входов A/B на уровне
навигации (`ScanningPage`'s `BlocConsumer.listener` / `ReportsDayListPopulated
._navigateItem`) — существующие тесты проверяют только
`InventoryReportDetailsCubit.load()` напрямую, с уже готовыми конструктор-
аргументами, не сам переход `ScanningExit`/тап по `InventoryDayItem`.

**TBD — теста нет** на секцию «чужие метки» (`InventoryForeignKnownEntry`) и
на сам `_computeSections`/`InventoryReportDetailsView` — все существующие
тесты проверяют только `InventoryReportDetailsCubit.load()` (состояние), не
виджет-уровень построения 4 секций.

## Открытые вопросы и ограничения

- **Режим «по дате» на практике наполняется только легаси-данными.**
  `getInventoryReportsByDate` в обоих репозиториях (`ReportAnimalsRepository`,
  `UnsentReportAnimalsRepository`) явно фильтрует `r.sessionUuid == null` —
  единственный реально достижимый через навигацию способ попасть в этот
  режим — легаси-ветка `reports_day_query.dart` (строки без `sessionUuid`),
  которая по [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  не должна появляться в данных новее миграции schemaVersion 87/88. На
  практике это означает, что при открытии современной (post-миграция)
  сессии всегда используется режим «по сессии», а режим «по дате» — код,
  написанный для случая, который в реальных данных почти никогда не
  наступает. Существующие тесты этого расхождения не видят, поскольку
  мокают репозитории напрямую и не воспроизводят их внутренний фильтр.
- **`isLoading` — поле, которое `load()` никогда не выставляет в `true`.**
  Ни начальный сброс состояния (шаг 6), ни промежуточные шаги не эмитят
  `InventoryReportDetailsState(..., isLoading: true)` — соответствующие
  ветки UI (`CircularProgressIndicator` в `_buildBody`, скрытие кнопки
  `share`) написаны, но структурно недостижимы: между шагом 6 (эмит с
  `isLoading: false` по умолчанию) и финальным эмитом на шаге 15/9 экран
  либо ещё не перерисован (тот же кадр), либо уже показывает
  предварительно построенные (пустые) секции — заметно только как «пустой
  экран без индикатора» на медленном устройстве/большой базе животных, не
  как явный баг. Является ли это осознанным решением (загрузка
  предполагается достаточно быстрой, индикатор не нужен) или недосмотром —
  не зафиксировано в коде.
- **`farm == null` ослабляет фильтр животных до полного отсутствия
  ограничения по ферме/месту.** Если `FarmRepository.getById` не резолвит
  `farmId` (пришедший из аргументов входа A/B либо, теоретически, из
  `reports.first.farmId`), шаг 13 целиком пропускается — пул `animals`
  остаётся равным **всем** живым животным локальной базы (шаг 11), и в
  `_computeSections` секция «отсутствует» становится фактически пустой для
  любых данных (см. «Альтернативные потоки»). Не воспроизведено тестом,
  вероятность на практике (устаревший локальный кэш `Farm`) не оценивалась.
- **Полная выгрузка `getAllAnimalsWithDetailsByFilters()` без единого
  фильтра.** Экран для показа одной сессии одного места читает **весь**
  справочник живых животных фермера (без `placeIds`/`farmId`/`kindIds`) и
  фильтрует в памяти — заметный, не переиспользующий индексацию БД паттерн,
  общий для этого экрана; последствия для производительности на больших
  базах животных не измерялись.
- **Расхождение с бейджем посуточного календаря (не проверено этим
  файлом).** `reports_day_query.dart` вычисляет `scanned`/`total`/`extra`
  для самого элемента `InventoryDayItem` собственным, независимым
  алгоритмом (`countScannedHere`/`countExtra`, фильтр только по `placeId`,
  без сопоставления через `Farm`/`Place`-резолв), отличным от того, что
  `InventoryReportDetailsCubit`/`_computeSections` пересчитывают при
  открытии этого экрана (шаги 13/18 выше, с резолвом фермы/места и
  ослаблением фильтра при `farm == null`/`place == null`). Оба алгоритма
  читают одни и те же исходные строки, но разными путями — на практике
  цифры на плитке календаря и на итоговом экране этого use-case не
  гарантированно совпадают. Не воспроизведено как конкретный кейс, не
  покрыто тестом ни с одной из сторон, фиксируется здесь как наблюдение по
  коду.
- **Пустой результат не показывает пользователю никакого сообщения.** В
  отличие от [UC-129](UC-129-ACTOR-5-EVT-65-ENT-17-READ_OK-IN-ANIMAL.md)
  (хаб неотправленных, явный `ProgressMessage.notFound`), этот экран при
  `reports.isEmpty` молча показывает шапку `0/0` и пустую секцию
  «Отсутствует (0)» — пользователь не может отличить «в этой сессии
  действительно ничего не отсканировано» от «данные не нашлись по
  какой-то технической причине» (например, `farmId`/`placeId`, не
  резолвящиеся в `Farm`/`Place`, либо совпавший с легаси-веткой режим «по
  дате», см. выше).
