# UC-129 — Пользователь открывает хаб ещё не отправленных сессий инвентаризации

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает отдельный экран-хаб («В работе» → плитка
«Инвентаризация»), показывающий все локально завершённые
(`readyToSend == true`), ещё ни разу не отправленные на сервер сессии
инвентаризации — по одной карточке на `sessionUuid`, а не по одной карточке
на строку `UnsentReportAnimals`. Экран — основа для последующей правки
конкретной сессии ([EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md),
за границами этого файла, тап по карточке).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
независимо от статуса авторизации (гость и авторизованный — одинаково):
`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` и
`lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart`
не находит ни одного совпадения — доступ и содержимое списка не зависят от
сессии пользователя.

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`) и нажимает плитку
   «Инвентаризация» (`EventTileData` с `icon: Assets.eventInventory`) —
   `onTap: () => context.pushNamed2(Routes.unsentInventories)`. В отличие от
   плиток «Вакцинация»/«Регистрация» (`count: totalVacc > 0 ? totalVacc :
   null`), здесь `count: data.inventoryCount` передаётся без условия — но
   сам `_CountBadge` внутри `EventCardWidget` всё равно рендерится только
   при `count != null && count! > 0`, так что видимый эффект тот же: при `0`
   бейджа нет, но тап работает независимо от его значения.
2. `data.inventoryCount` — отдельная подписка `InWorkBloc` на
   `_unsentReportAnimalsRepository.watchInventorySessionCount()`, **не** тот
   же код, что строит список этого экрана (см. «Бизнес-правила» —
   расхождение в обработке легаси-строк).
3. `Routes.unsentInventories` — листовой маршрут (в отличие от
   `Routes.unsentVaccination`, без вложенного дочернего маршрута правки;
   правка сессии — отдельный push поверх этого экрана, см. шаг 12).
   `builder` создаёт `const UnsentInventoriesPage()`.
4. `UnsentInventoriesPage.build` оборачивает экран в
   `BlocProvider(create: (context) => UnsentInventoriesCubit()..load())` —
   `load()` вызывается один раз при создании cubit'а; дополнительно на
   экране есть `RefreshIndicator` (см. шаг 10).
5. `UnsentInventoriesCubit` стартует в `UnsentInventoriesState.initial()`;
   `load()` сразу эмитит `UnsentInventoriesState.loading()`.
6. `load()` вызывает `_reportAnimalsRepo.getInventoryReadySessions()`
   (`UnsentReportAnimalsRepository.getInventoryReadySessions` →
   `UnsentReportAnimalsDao.getInventoryReadySessions`): `SELECT * FROM
   unsent_report_animals WHERE type = 'inventory' AND ready_to_send = true
   ORDER BY time DESC`, обёрнуто в `try/catch`.
7. Для каждой строки результата: если `row.farmId == null || row.placeId ==
   null` — `continue` (строка отбрасывается целиком, ещё до группировки).
8. Ключ группировки: `row.sessionUuid ?? 'legacy_${farmId}_${placeId}_${
   DateUtils.dateOnly(row.time).millisecondsSinceEpoch}'`. Строки с
   одинаковым ключом схлопываются в один элемент карты `sessions`: `count`
   суммируется, `time` пересчитывается как `existing.time.isAfter(row.time)
   ? existing.time : row.time` — по построению это **максимум** времени по
   группе (см. «Бизнес-правила» о том, почему это на практике не влияет на
   результат).
9. `sessions.entries` сортируются по убыванию `time`
   (`b.value.time.compareTo(a.value.time)`).
10. Второй проход по отсортированным сессиям: `sessionUuid =
    entry.key.startsWith('legacy_') ? null : entry.key`; если `null` —
    `continue`. Каждая легаси-группа, посчитанная на шаге 8, здесь
    безусловно отбрасывается — см. «Открытые вопросы».
11. `farmCache[s.farmId] ??= await _farmRepo.getById(s.farmId)`
    (`FarmRepository.getById` ищет по `Farm.remoteId`); если результат
    `null` — `continue`, вся сессия пропускается без какого-либо сообщения
    пользователю.
12. `placeCache[s.placeId] ??= await _placeRepo.getById(s.placeId)`
    (`PlaceRepository.getById` ищет по `Place.idRemote`); если результат
    `null` — тоже `continue`, тот же эффект.
13. `placeAnimalsCache[s.farmId] ??= await
    _placeRepo.getAllWithThisFarmIdWithAnimals(s.farmId)` — список мест
    фермы с животными, вычисляется один раз на ферму даже при нескольких
    сессиях этой фермы (кэш по `Map<int, ...>`).
14. `matchingPlace` — `firstWhere` по `p.place.idRemote == s.placeId` в
    только что полученном списке, `orElse` — синтетический
    `PlaceWithAnimals(place: place, animals: [])`.
15. Собирается синтетический `farmWithDetails = FarmWithDetails(farm: farm,
    animals: [], placesWithAnimals: placesWithAnimals, reportsCount: 0,
    vaccinationsCount: 0, animalsCount: 0)` — обёртка, нужная только чтобы
    удовлетворить сигнатуру `ScanningPageArgs.inventory(farm: ...)` на
    последующем переходе к правке (шаг 12/[EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)),
    не читается ни из какого реального агрегата фермы — все три счётчика
    жёстко `0` и на этом экране не отображаются (карточка использует только
    `farmWithDetails.farm.name`/`placeWithAnimals.place.name`).
16. В `items` добавляется `UnsentInventoryItem(farmId: s.farmId, placeId:
    s.placeId, sessionTime: s.time, animalCount: s.count, sessionUuid:
    sessionUuid, farmWithDetails: farmWithDetails, placeWithAnimals:
    matchingPlace)`.
17. После цикла — `emit(UnsentInventoriesState.loaded(items: items))`.
18. `BlocBuilder<UnsentInventoriesCubit, UnsentInventoriesState>` в
    `UnsentInventoriesPage` рендерит через `state.when(...)`:
    - `initial` → `SizedBox.shrink()`;
    - `loading` → `BottomSheetPageWrapper` с `CustomLottieLoader`;
    - `loaded` с пустым `items` → `BottomSheetPageWrapper` с
      `ProgressMessage.notFound(message: l10n.list_is_empty)`;
    - `loaded` с непустым `items` → `RefreshIndicator` (`onRefresh: () =>
      context.read<UnsentInventoriesCubit>().load()`), оборачивающий
      `ListView.separated` из `_InventorySessionCard`, по одной карточке на
      элемент `items`, в уже вычисленном порядке (шаг 9).
19. Каждая `_InventorySessionCard` показывает `item.placeName`
    (`placeWithAnimals.place.name`), `item.farmName`
    (`farmWithDetails.farm.name`), `'$dateStr  •  $timeStr'` (из
    `item.sessionTime`), `item.animalCount` и текстовую плашку «редактировать»
    (`l10n.edit`); вся карточка — `InkWell` с единым `onTap`.
20. Тап по карточке → `_openEditMode`: `context.pushNamed2(Routes.scanning,
    extra: ScanningPageArgs.inventory(farm: item.farmWithDetails,
    inventoryLabel: l10n.inventory, editPlaceId: item.placeId,
    editSessionUuid: item.sessionUuid))` — переход в правку сессии
    ([EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)),
    отдельный use-case, не предмет этого файла; переход выполняется без
    `await` и без реакции на результат навигации — по возврату этот экран
    сам себя не перезагружает (см. «Открытые вопросы»).

### Альтернативные потоки

- **Пустой список (`loaded` с `items.isEmpty`).** Не ошибка —
  `getInventoryReadySessions()` вернул `[]`, либо все строки были отброшены
  фильтрами шагов 7/10/11/12. Экран показывает `list_is_empty`. Тот же
  `RESULT` (`READ_OK`), другой визуальный итог — не отдельный use-case, см.
  шаг 18 выше.
- **Несколько строк одной `sessionUuid`.** Схлопываются в одну карточку;
  `animalCount` — сумма строк группы; `sessionTime` — максимум времени по
  группе. По инварианту [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (`ScanningBloc.on<ScanningEventSave>` нормализует **все**
  `scannedAnimals` сессии к минимальному времени скана сессии
  (`sessionStartTime = _data.scannedAnimals.map((e) => e.time).reduce((a,
  b) => a.isBefore(b) ? a : b)`) и переперсистит черновик целиком
  (`_persistDraftScanReports`) **до** вызова `markSessionReadyToSendByUuid`)
  — к моменту, когда сессия становится `readyToSend == true`, все её строки
  уже физически имеют одно и то же `time`. Максимум по группе, вычисляемый
  здесь, совпадает с этим нормализованным значением не потому, что код это
  явно проверяет, а потому что входные значения уже совпадают.
- **Легаси-строки без `sessionUuid`.** Группируются по ключу
  `legacy_${farmId}_${placeId}_${day}` на шаге 8, но безусловно
  отбрасываются на шаге 10 — тот же итоговый эффект, как если бы они вообще
  не участвовали в группировке (мёртвая работа, см. «Открытые вопросы»). По
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) такие
  строки в реальных данных не встречаются новее миграции schemaVersion 87 —
  на практике реализуемо только на очень старой, ни разу не разлогиненной
  установке (таблица `@Clearable()` — очищается лишь при логауте, не при
  миграции схемы) либо в тестовых фикстурах.
- **Строки без `farmId`/`placeId`.** Отбрасываются раньше группировки (шаг
  7) — не порождают ни полноценную, ни легаси-карточку.
- **Сессия, чья `farmId` не резолвится в локальный `Farm.remoteId`.**
  Отбрасывается на шаге 11 без какого-либо сообщения пользователю — строки
  сессии остаются в `UnsentReportAnimals` нетронутыми, просто карточка не
  появляется.
- **Сессия, чья `placeId` не резолвится в локальный `Place.idRemote`.**
  Тот же код-паттерн (шаг 12), тот же силентный эффект — но, в отличие от
  случая с фермой, **не покрыт ни одним тестом** (см. «Связанные тесты»).
- **Исключение внутри `try`-блока `load()`.** `catch (e)` → `emit(
  UnsentInventoriesState.error(e.toString()))`; страница рендерит
  `ProgressMessage.somethingWentWrong(message: msg)`. Другой `RESULT`
  (`READ_ERROR`) для того же события — за границами этого файла; тестово
  заякорено отдельной группой `'UC-130 — UnsentInventoriesCubit.load'` (см.
  «Связанные тесты»).
- **Pull-to-refresh (`RefreshIndicator.onRefresh`).** Повторно вызывает
  `load()` с нуля — тот же код-путь, что и первичная загрузка, без
  инкрементального сравнения с текущим списком.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals`) — сущность, чьё состояние
  отображает этот экран; читается только подмножество `type = 'inventory'
  ∧ readyToSend = true` («готово к отправке», см. шаг 6).
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — читается
  построчно на сессию (с кэшем по id), по `remoteId`; не резолвленная ферма
  молча исключает сессию из списка; не изменяется этим сценарием.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается
  построчно на сессию (с кэшем по id), по `idRemote`, плюс
  `getAllWithThisFarmIdWithAnimals` построчно на ферму (тоже с кэшем) для
  построения синтетического `placeWithAnimals`/`farmWithDetails`; не
  изменяется этим сценарием.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — фактически не
  используется этим экраном по существу: `placesWithAnimals` содержит
  списки животных по месту, но карточка показывает только имя
  места/фермы/дату/счётчик голов, не сопоставляет отдельные метки с
  животными (в отличие от [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md),
  экрана итогового отчёта, который делает такое сопоставление).

### Бизнес-правила

- **Бейдж плитки и список экрана — два независимых алгоритма группировки
  над одним и тем же базовым предикатом.**
  `InWorkBloc.data.inventoryCount` = `UnsentReportAnimalsRepository.watchInventorySessionCount()`,
  которая тоже фильтрует `type = 'inventory' ∧ readyToSend = true`
  (`UnsentReportAnimalsDao.watchInventoryReadyList`, тот же предикат, что и
  `getInventoryReadySessions`), но группирует легаси-строки **как
  полноценные сессии** — каждый уникальный ключ `legacy_${farmId}_${placeId}_${day}`
  добавляется в `Set<String> keys` наравне с `sessionUuid`. Этот же экран
  (шаг 10) такие группы безусловно отбрасывает. Значит, при наличии
  легаси-строк (см. «Альтернативные потоки», условия появления) бейдж «В
  работе» может показывать число сессий больше, чем количество карточек,
  реально отображаемых этим экраном для тех же данных — та же форма
  находки, что и «бейдж/список» у вакцинации
  ([UC-79](UC-79-ACTOR-5-EVT-40-ENT-14-READ_OK-IN-ANIMAL.md), «Бизнес-правила»),
  но здесь расхождение — не в предикате запроса, а в правилах группировки
  одного и того же набора строк.
- Ключ легаси-группы включает календарный день (`DateUtils.dateOnly`), не
  точное время — две легаси-строки одной фермы/места в один день, но с
  разным временем, схлопываются в одну легаси-группу (не имеет значения для
  итогового списка, поскольку такие группы всё равно отбрасываются).
- Обогащение сессий (резолв фермы/места/животных) идёт последовательно,
  `await` внутри `for`-цикла, не `Future.wait` — но `farmCache`,
  `placeCache`, `placeAnimalsCache` мемоизируют результат по id, так что
  повторное появление той же фермы/места среди нескольких сессий не
  порождает повторных запросов к БД.
- Синтетические `FarmWithDetails`/`PlaceWithAnimals`, собираемые в шагах
  14–15, — «одноразовые» view-model'и с жёстко занулёнными счётчиками, не
  вычисляемые из какого-либо реального агрегата фермы; существуют
  исключительно ради сигнатуры аргумента при переходе к правке.
- Экран не подписан на изменения `UnsentReportAnimals` реактивно (`watch`);
  `load()` — разовый запрос на момент создания cubit'а, либо по явному
  pull-to-refresh.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (оба варианта успеха: непустой и пустой список)
полностью реализован и достижим из UI.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (плитка `EventTileData` с `icon: Assets.eventInventory`) | CURRENT | обычная точка входа — переход по `Routes.unsentInventories` |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (подписка на `watchInventorySessionCount`) | CURRENT | считает бейдж плитки — независимый от этого экрана алгоритм группировки, см. «Бизнес-правила» |
| `lib/pages/routes.dart` | `Routes.unsentInventories` | CURRENT | листовой маршрут, без вложенного дочернего маршрута правки |
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `UnsentInventoriesPage.build`, `_openEditMode`, `_InventorySessionCard` | CURRENT | создаёт cubit, рендерит все состояния, переход к правке |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | предмет этого файла — загрузка и группировка списка |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_state.dart` | `UnsentInventoriesState`, `UnsentInventoryItem` | CURRENT | freezed-состояния экрана + view-model карточки |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReadySessions`, `watchInventorySessionCount` | CURRENT | тонкая делегация в DAO / отдельный алгоритм для бейджа |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.getInventoryReadySessions`, `watchInventoryReadyList` | CURRENT | явный предикат `type = 'inventory' ∧ readyToSend = true`, общий для обоих алгоритмов |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>` (нормализация времени сессии) | CURRENT | почему все строки одной `readyToSend`-сессии на практике имеют одинаковое `time` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | резолв фермы по `remoteId`; `null` → сессия пропускается |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById`, `getAllWithThisFarmIdWithAnimals` | CURRENT | резолв места по `idRemote`; список мест фермы с животными |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmWithDetails`, `PlaceWithAnimals` | CURRENT | синтетические view-model'и, используемые только для передачи в `ScanningPageArgs.inventory` |
| `lib/pages/scanning/scanning_page.dart` | `ScanningPageArgs.inventory` | CURRENT | аргументы целевого экрана правки ([EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)), не предмет этого файла |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.notFound`, `ProgressMessage.somethingWentWrong` | CURRENT | UI пустого состояния / состояния ошибки |

## Критерии приёмки

- При открытии `Routes.unsentInventories` cubit вызывает `load()` ровно один
  раз без участия пользователя.
- Если `getInventoryReadySessions()` вернул несколько строк с одинаковой
  `sessionUuid`, они схлопываются ровно в один `UnsentInventoryItem` с
  `animalCount`, равным числу строк группы, и тем же `sessionUuid`.
- Строки без `sessionUuid` не порождают ни один элемент списка, независимо
  от наличия `farmId`/`placeId`.
- Строки, у которых `farmId == null` либо `placeId == null`, не порождают ни
  один элемент списка.
- Сессия, чья `farmId` не резолвится через `FarmRepository.getById`,
  пропускается без перевода состояния в `error`.
- Элементы `items` отсортированы по убыванию времени группы.
- Пустой итоговый список — состояние `loaded` с `items.isEmpty`, экран
  показывает `list_is_empty`; тот же `RESULT` (`READ_OK`), что и непустой
  вариант.
- Исключение внутри `getInventoryReadySessions()`/последующей обработки
  переводит состояние в `error(e.toString())` — другой `RESULT`
  (`READ_ERROR`), только фиксируется здесь как граница этого файла.

## Связанные тесты

`test/pages/unsent_inventories_cubit_test.dart`, группа `group('UC-129 —
UnsentInventoriesCubit.load', ...)` (старая нумерация — будет переименована
в `UC-129` отдельным контролируемым проходом, не трогать сейчас) — 6 тестов,
покрывающих основной поток и большинство альтернативных потоков этого файла:

- `'без готовых сессий -> loaded с пустым items'` — пустой список (шаг 18,
  пустой вариант).
- `'несколько строк одной sessionUuid -> схлопываются в один item с
  суммарным count'` — группировка по `sessionUuid` (шаг 8), `animalCount ==
  3`, `sessionUuid` сохранён.
- `'legacy-сессии без sessionUuid пропускаются (continue)'` — ветка
  «Легаси-строки без `sessionUuid`».
- `'строки без farmId/placeId пропускаются'` — ветка «Строки без
  `farmId`/`placeId`».
- `'farm не найден по id -> сессия пропускается'` — ветка «Сессия, чья
  `farmId` не резолвится».
- `'две разные sessionUuid -> два item, отсортированы по времени убывания'`
  — сортировка (шаг 9): `items.first.sessionUuid == 'uuid-late'`,
  `items.last.sessionUuid == 'uuid-early'`.

Отдельная группа `group('UC-130 — UnsentInventoriesCubit.load', ...)` (тот
же файл, тест `'исключение из репозитория -> error state'`) — ветка
`READ_ERROR`, в этот use-case не входит.

**TBD — теста нет** на ветку «сессия, чья `placeId` не резолвится через
`PlaceRepository.getById`» — по коду симметрична уже покрытой ветке с
фермой (шаг 12 против шага 11), но отдельного теста, мокающего
`placeRepository.getById(...)` как возвращающий `null` при уже успешном
резолве фермы, в файле нет.

## Открытые вопросы и ограничения

- **Мёртвая работа при группировке легаси-строк.** Шаг 8 честно строит
  агрегированную запись (`count`, максимум `time`) для легаси-ключа, но шаг
  10 безусловно её выбрасывает — тот же результат получился бы, отбрасывая
  такие строки сразу на шаге 7 вместе со строками без `farmId`/`placeId`.
  Не меняет наблюдаемое поведение, только читаемость кода.
- **Расхождение бейджа и списка на легаси-строках.** См. «Бизнес-правила» —
  `data.inventoryCount` (плитка «В работе») учитывает легаси-группы как
  сессии, сам экран — нет. Различие проявляется только при наличии
  легаси-строк, которые по [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  не должны появляться в данных новее миграции schemaVersion 87, но таблица
  чистится только логаутом, а не миграцией — теоретически достижимо на
  очень старой, ни разу не разлогиненной установке.
- **Силентный дроп сессии при нерезолвленной ферме/месте.** Пользователь,
  успешно завершивший сессию сканирования (readyToSend = true), может
  обнаружить, что она просто не отображается в этом хабе, без какого-либо
  объяснения — строки при этом никуда не исчезают из `UnsentReportAnimals`,
  просто не находят пары в `Farm`/`Place`. Не воспроизведено как баг-репорт,
  фиксируется здесь как наблюдение по коду.
- **Ветка «место не резолвится» не покрыта тестом** — см. «Связанные
  тесты».
- **Экран не обновляется реактивно.** `load()` — разовый вызов при создании
  cubit'а либо по явному pull-to-refresh; если после открытия экрана
  где-то ещё завершится или отредактируется сессия инвентаризации, уже
  открытый экран этого не увидит без ручного refresh или пересоздания.
- **Возврат с экрана правки не перезагружает список.** Переход на
  `Routes.scanning` (шаг 20) не дожидается результата навигации — по
  возврату из правки карточка на этом экране может остаться со старыми
  значениями до следующего `load()`. Сама логика правки — предмет
  [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md), здесь
  фиксируется только то, что READ_OK-сценарий этого файла не перезапускается
  автоматически.
