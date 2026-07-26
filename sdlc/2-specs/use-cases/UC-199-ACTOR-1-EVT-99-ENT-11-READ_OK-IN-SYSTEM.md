# UC-199 — Пользователь открывает календарь событий фермы/места и видит месяц с индикаторами дней

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же контейнер, что описан в [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) —
`ReportsCalendarCubit.load(farm, place, month)` строит месячный вид календаря
с цветными индикаторами по дням (`CalendarReportType`: выбытие, перемещение,
инвентаризация, взвешивание, регистрация, вакцинация). Этот документ
специфицирует только успешный путь загрузки/навигации контейнера — сам
факт того, *какие* записи попадают в посуточный список конкретного дня по
каждому из шести типов, уже специфицирован в `ANIMAL` по типам (см. `MOD-7`,
«Граница»); здесь эти данные используются только как источник булевых
индикаторов «в этот день что-то было».

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
как зафиксировано в [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md).
Открывает экран с панели действий фермы (`FarmToolbarActions`,
`lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`) или
конкретного места этой фермы (`PlaceToolbarActions`,
`lib/pages/place/widgets/place_actions_widget.dart`) — оба виджета доступны из
одного и того же места навигации, кнопка «Календарь» (иконка `Assets.calendar`,
подпись `l10n.weekly_planner`). Ни в самих виджетах, ни в маршруте
`Routes.reportsCalendar`, ни в `ReportsCalendarCubit`/`ReportsCalendarView` не
найдено проверки `AppCacheService.isAuthorized()`/аналога (в отличие от двух
других мест `routes.dart`, где такой `redirect` есть) — см. «Открытые
вопросы» о вероятной доступности этого же экрана и гостю.

## CURRENT

### Основной поток

1. Пользователь на экране фермы либо места нажимает «Календарь» —
   `FarmToolbarActions.build` вызывает `context.pushNamed2(Routes.reportsCalendar,
   extra: ReportsCalendarPageArgs(farm: farm))` (без `place`); `PlaceToolbarActions.build`
   вызывает тот же переход с `ReportsCalendarPageArgs(farm: farm, place:
   placeWithAnimals)` (место всегда сопровождается фермой, хотя параметр
   `farm` у `PlaceToolbarActions` формально nullable).
2. `ReportsCalendarView.build` читает аргументы через
   `GoRouterState.of(context).getExtraByName<ReportsCalendarPageArgs>(Routes.reportsCalendar)`
   и создаёт `BlocProvider(create: (context) => ReportsCalendarCubit()..load(farm:
   args.farm, place: args.place))` — `load()` вызывается **без `await`** внутри
   каскада конструктора провайдера.
3. `ReportsCalendarCubit.load({farm, place, month})`: `displayedMonth =
   DateUtils.dateOnly(month ?? DateTime.now())` (при первом открытии `month`
   не передаётся — текущий календарный месяц); `farmId = farm?.farm.remoteId
   ?? place?.place.farmId ?? 0`; `placeId = place?.place.idRemote`;
   `scopeChanged = _rawDataFarmId != farmId || _rawDataPlaceId != placeId`.
4. Так как `_rawData == null` (первая загрузка на этом экземпляре кубита),
   эмитится `ReportsCalendarState.loading(newData)` — `ReportsCalendarView`
   рендерит `CustomLottieLoader`.
5. `await _dataLoader.load(farmId: farmId)` → `ReportsDayDataLoader.load`:
   `Future.wait` одновременно на 7 репозиториев — `_movementRepo.getMovementsWithDetailsByFilters(sync:
   null)`, `_disposalRepo.dao.getAll()`, `_reportAnimalsRepo.getReportsByFarmId(farmId)`,
   `_unsentReportAnimalsRepo.getInventoryReports()`, `_animalsRepo.getAllAnimalsWithDetailsByFilters(isNotDeleted:
   null, isShowRemoteSource: null)`, `_vaccinationsRepo.getVaccinationsWithDetails()`,
   `_disposalReasonsRepo.getAll()`. Из них только `getReportsByFarmId(farmId)`
   реально фильтрует по ферме на уровне DAO — оставшиеся четыре доменных
   вызова (`getMovementsWithDetailsByFilters`, `dao.getAll()` для выбытий,
   `getInventoryReports()`, `getVaccinationsWithDetails()`) не принимают
   параметр `farmId`/`animalIds`, ограничивающий выборку, и возвращают
   перемещения/выбытия/неотправленные инвентаризации/вакцинации **всего
   приложения** целиком (см. «Открытые вопросы»); `_animalsRepo...` тоже
   тянет животных всех ферм.
6. После разрешения `Future.wait`: `allAnimals` (результат `[4]`)
   фильтруется в памяти по `a.farmId == farmId` → `farmAnimals`; из них
   собираются `animalIds`. Отдельным, уже не входящим в `Future.wait`,
   последовательным вызовом: `weighings = animalIds.isEmpty ? [] : await
   _weighingsRepo.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds)` —
   единственный источник, по построению ограниченный именно животными
   запрошенной фермы.
7. Собранный `ReportsDayRawData` (поля `movements`/`disposals`/`vaccinations`/`unsentInventory`
   всё ещё содержат данные всего приложения, не только этой фермы)
   сохраняется в `_rawData`; `_rawDataFarmId`/`_rawDataPlaceId` запоминают
   пару, для которой он загружен; `_monthDaysCache.clear()`.
8. `_emitMonth(newData)`: ключ — `_monthCacheKey` = `"{year}-{month}_{farmId}_{placeId
   ?? 'all'}"`. Кэш только что очищен, поэтому строится заново:
   `ReportsDayQuery.buildCalendarDays(data: _rawData!, displayedMonth,
   placeId: newData.placeId, placeIds: newData.allPlaceIds)` — именно на этом
   шаге все ранее загруженные «по всему приложению» перемещения, выбытия,
   вакцинации и неотправленные инвентаризации впервые фильтруются под
   конкретные ферму/место: перемещения/выбытия/инвентаризация — по
   `matchesPlace`/`matchesMovementPlaces` (сравнение с `placeId`/`allPlaceIds`
   этой фермы), вакцинации — явной проверкой `v.animal.farmId !=
   data.farmId`.
9. Результат кладётся в `_monthDaysCache[cacheKey]`; сразу же
   `_preloadAdjacentMonths(newData)` тем же вызовом `buildCalendarDays`
   заранее строит и кэширует соседние (`displayedMonth ± 1`) месяцы — чтобы
   они уже были в кэше при свайпе `PageView` в любую сторону.
10. `emit(ReportsCalendarState.loaded(newData.copyWith(days: days)))`.
    `ReportsCalendarView`'s `BlocBuilder` рендерит `ReportsCalendarPopulated` →
    `_ReportsCalendarBody`.
11. `_ReportsCalendarBody.build`: `_MonthHeader` (название месяца/года,
    стрелки навигации, меню вида — `MoreMenuWidget.reportsCalendar` с двумя
    пунктами `compact`/`detailed`), `_WeekdayRow`, затем `PageView.builder`
    вокруг базовой страницы `_kBasePage = 12000` (соответствует текущему
    календарному месяцу на момент создания виджета): для активной страницы
    (`month == widget.data.displayedMonth`) берутся `widget.data.days` из
    состояния, для любой другой — `cubit.cachedDaysForMonth(month)`
    (посчитанный кэш либо пустой список, если этот месяц ещё не построен).
12. `_CalendarMonthGrid._buildWeeks` достраивает недели месяца «серыми» днями
    соседних месяцев до кратности 7 и рендерит по `viewMode`:
    `_CompactCalendarGrid` (до 6 цветных точек-индикаторов под номером дня)
    либо `_DetailedCalendarGrid` (список текстовых чипов по каждому
    присутствующему типу).
13. Ячейка дня кликабельна только при `cell.isCurrentMonth &&
    cell.reportTypes.isNotEmpty` — дни без событий и дни соседних месяцев
    (`GestureDetector.onTap: null`) не реагируют на тап.
14. Тап по кликабельному дню → `_onDayTap(date)`: при `widget.data.isFarmLevel`
    (место не выбрано, `place == null && farm != null`) —
    `context.pushNamed2(Routes.farmDayList, extra: FarmDayListPageArgs(date:
    date, farm: farm))`; иначе — `context.pushNamed2(Routes.reportsDayList,
    extra: ReportsDayListPageArgs(date: date, farm: farm, place: place))`. Оба
    перехода ведут на уже специфицированные read-сценарии `ANIMAL`
    (посуточное содержимое дня по 6 типам) — вне границ этого модуля (см.
    `MOD-7`, «Граница»).
15. Если в аргументах задано `place` (уровень места) — под сеткой месяца
    показывается кнопка «+ {l10n.reports_calendar_new_event}», ведущая на
    `Routes.operations` с `OperationsPageArgs(place: place.place)` — создание
    нового события, отдельная фича, вне этого сценария.

### Альтернативные потоки

- **Кэш при тех же `farmId`/`placeId`.** Повторный `load()` (например, при
  возврате на уже созданный экземпляр кубита с тем же экраном) не проходит
  условие `scopeChanged || _rawData == null` — `_dataLoader.load` не
  вызывается повторно, сразу выполняется `_emitMonth(newData)` на уже
  загруженных `_rawData`, независимо от того, изменился ли переданный
  `month`.
- **Смена месяца свайпом.** `PageView.onPageChanged` → `_onPageChanged`
  вычисляет месяц по номеру страницы; если он отличается от текущего
  `displayedMonth`, вызывается `cubit.changeMonth(month)` — эмитит новое
  `loaded`-состояние с обновлённым `displayedMonth`, переиспользуя (либо
  достраивая на лету, если ещё не в кэше) `_monthDaysCache`; `_dataLoader`
  не вызывается вовсе.
- **Переключение вида (`compact`/`detailed`).** `setViewMode` работает в
  любом текущем варианте состояния — `state.when` переэмичивает **тот же**
  вариант freezed-объекта (`initial`/`loading`/`loaded`/`error`) с новым
  `viewMode`; не делает ничего, если запрошенное значение уже установлено
  (`if (_data.viewMode == viewMode) return;` — состояние не переэмичивается,
  `identical` сохраняется).
- **Легенда типов событий.** Кнопка `info_outline` в `CustomAppBar` открывает
  статичный `Dialog` со списком всех 6 `CalendarReportType` и их цветов —
  не связана с кубитом/состоянием, чисто статический UI.
- **Отказ `_dataLoader.load()` — другая, здесь не элаборируемая ветка.**
  `load()` не оборачивает вызов `_dataLoader.load(farmId: farmId)` в
  `try/catch` — исключение всплывает необработанным из `load()` (см.
  `test/pages/reports_calendar_cubit_test.dart`, тест `'ошибка dataLoader ->
  исключение пробрасывается (нет try/catch в load())'` той же группы). Так
  как `load()` вызван без `await` внутри каскада `BlocProvider.create`, это
  становится необработанной ошибкой `Future`, не перехватываемой самим
  виджетом. Полное описание этой ветки — предмет отдельного документа
  (`READ_ERROR` того же события [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)),
  здесь не дублируется.
- **Вариант состояния `error` структурно недостижим независимо от исхода
  `load()`.** Полный поиск (`grep -rn "ReportsCalendarState.error" lib/
  test/`) находит ровно одно место конструирования этого варианта —
  `setViewMode`'s `error: (_) => emit(ReportsCalendarState.error(newData))` —
  которое лишь **сохраняет** уже существующий вариант `error`, если кубит
  уже был в нём; ничто в `load()`/`changeMonth()`/где-либо ещё не переводит
  кубит в `error` **из** `initial`/`loading`/`loaded`. Единственный найденный
  в коде отказ (см. пункт выше) не оборачивается в `catch`, поэтому не
  превращается в `.error()` — ветка `error: (data) =>
  Text(data.errorMessage ?? '')` в `reports_calendar_view.dart` в сегодняшнем
  коде недостижима ни при каком известном пути выполнения.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — первичная
  сущность по id этого сценария: `Animal.createdAt` каждого животного фермы
  — источник типа-индикатора `registration`; тот же массив
  (`getAllAnimalsWithDetailsByFilters`) — база для отбора взвешиваний фермы
  на шаге 6. Читается **целиком, по всем фермам приложения**, фильтруется по
  `farmId` уже в памяти кубита/лоадера — этим сценарием не изменяется.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)
  (Place), `FARM` — `farm.farm.remoteId`, `farm.placesWithAnimals` (→
  `allPlaceIds`), `place.place.farmId`/`place.place.idRemote` определяют
  `farmId`/`placeId`, ключ кэша и то, какой из двух посуточных экранов
  (`farmDayList`/`reportsDayList`) открывается по тапу; читаются, не
  изменяются.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement),
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal),
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination),
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing),
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — все пять читаются как источники индикаторов дней
  месяца; не изменяются. Собственное посуточное представление каждого типа
  (детали конкретного дня) уже специфицировано в `ANIMAL` (см. `MOD-7`,
  «Граница») — этот сценарий владеет только агрегированным
  индикатором/точкой на уровне месяца, не содержимым дня.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason),
  `HANDBOOKS` — читается целиком (`getAll()`) в состав `ReportsDayRawData`
  (`disposalReasonsById`), но реально используется только посуточным
  экраном, не самим месячным контейнером — загружается заодно, в рамках
  того же `Future.wait`.

### Бизнес-правила

- Кэш сырых данных (`_rawData`) ключуется по паре `(farmId, placeId)`, не
  только по `farmId` — переключение с «вся ферма» на конкретное место (или
  наоборот) в пределах той же фермы тоже считается `scopeChanged` и требует
  повторной загрузки `ReportsDayDataLoader.load`, даже если нужные фермы
  данные уже были загружены секунду назад для другого `placeId`.
- Кэш построенных дней месяца (`_monthDaysCache`) — отдельный от кэша сырых
  данных, ключуется строкой `"{year}-{month}_{farmId}_{placeId ?? 'all'}"`;
  полностью очищается при каждой повторной загрузке сырых данных, но не при
  простой смене месяца/вида отображения.
- Соседние месяцы (±1 от отображаемого) достраиваются заранее при каждой
  успешной загрузке/смене месяца — до 3 вызовов `ReportsDayQuery.buildCalendarDays`
  за одно пользовательское действие (текущий месяц + 2 соседних), не
  отражённых отдельным индикатором загрузки.
- День кликабелен исключительно по наличию хотя бы одного типа события и
  принадлежности отображаемому месяцу — сама точка/чип не несёт отдельного
  действия, тап всегда ведёт на весь день целиком, не на конкретный тип
  события.
- Переход по тапу — единственное место, где контейнер расходится по двум
  разным маршрутам в зависимости от уровня (ферма целиком vs конкретное
  место); оба потребляют один и тот же `CalendarDayEntry`/`reportTypes`,
  разница только в наборе аргументов страницы (`FarmDayListPageArgs` vs
  `ReportsDayListPageArgs`).
- Режим отображения (`compact`/`detailed`) — единственная часть состояния,
  которая осознанно переживает переход в любой другой вариант freezed-состояния
  (через `state.when` внутри `setViewMode`) — выбор пользователя не
  сбрасывается промежуточными техническими состояниями.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — весь описанный поток (шаги 1–15)
полностью реализован и достижим. Структурно недостижим только вариант
состояния `error` (см. «Альтернативные потоки»/«Открытые вопросы») — это не
блокирует документирование самого `READ_OK`-потока, так как он его не
затрагивает.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmToolbarActions.build` | CURRENT | точка входа на уровне фермы — `ReportsCalendarPageArgs(farm: farm)` |
| `lib/pages/place/widgets/place_actions_widget.dart` | `PlaceToolbarActions.build` | CURRENT | точка входа на уровне места — `ReportsCalendarPageArgs(farm: farm, place: placeWithAnimals)` |
| `lib/pages/routes.dart` | `Routes.reportsCalendar`, `Routes.farmDayList`, `Routes.reportsDayList` | CURRENT | маршрут контейнера и двух вариантов посуточного экрана; ни один redirect-guard (`AppCacheService.isAuthorized()`) не обёрнут вокруг этого поддерева |
| `lib/pages/reports_calendar/data/reports_calendar_page_args.dart` | `ReportsCalendarPageArgs`, `CalendarDayEntry` | CURRENT | аргументы страницы (`isFarmLevel`); модель дня календаря |
| `lib/pages/reports_calendar/presentation/reports_calendar_page.dart` | `ReportsCalendarPage` | CURRENT | тонкая обёртка над `ReportsCalendarView` |
| `lib/pages/reports_calendar/presentation/widgets/reports_calendar_view.dart` | `ReportsCalendarView.build` | CURRENT | читает аргументы, создаёт `BlocProvider` + `load()` без `await`, рендерит по 4 вариантам `state.when` |
| `lib/pages/reports_calendar/cubit/reports_calendar_cubit.dart` | `ReportsCalendarCubit.load`, `.changeMonth`, `.setViewMode`, `.cachedDaysForMonth`, `._emitMonth`, `._preloadAdjacentMonths`, `._monthCacheKey` | CURRENT | вся логика контейнера: загрузка сырых данных, кэш сырых данных и дней месяца |
| `lib/pages/reports_calendar/cubit/reports_calendar_state.dart` | `ReportsCalendarStateData`, `ReportsCalendarState` | CURRENT | freezed-состояние (4 варианта: `initial`/`loading`/`loaded`/`error`), геттеры `farmId`/`placeId`/`allPlaceIds`/`isFarmLevel` |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | `Future.wait` на 7 репозиториев + отдельный последовательный `await` взвешиваний по уже отфильтрованным `animalId` фермы |
| `lib/pages/reports_day_list/data/reports_day_raw_data.dart` | `ReportsDayRawData`, `.animalsAtPlace`, `.animalIdsAtPlace` | CURRENT | контейнер сырых данных, часть полей которого (`movements`/`disposals`/`vaccinations`/`unsentInventory`) не ограничена запрошенной фермой на уровне запроса |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildCalendarDays` | CURRENT | строит дни месяца с набором типов событий; единственное место, где четыре «неограниченных» источника фактически фильтруются по `placeId`/`placeIds`/`farmId` |
| `lib/pages/reports_calendar/data/calendar_report_type.dart` | `CalendarReportType`, `.dotColor`, `.labelKey`, `.labelBackgroundColor`, `.labelTextColor` | CURRENT | 6 типов индикаторов дня и их визуальное представление |
| `lib/pages/reports_calendar/data/calendar_view_mode.dart` | `CalendarViewMode` | CURRENT | `compact`/`detailed` |
| `lib/pages/reports_calendar/presentation/widgets/reports_calendar_populated.dart` | `ReportsCalendarPopulated`, `_ReportsCalendarBodyState._onDayTap`, `._onPageChanged`, `_CalendarMonthGrid._buildWeeks`, `_CompactCalendarGrid`, `_DetailedCalendarGrid` | CURRENT | UI: `PageView` по месяцам вокруг `_kBasePage`, меню вида в шапке, тап по дню → навигация фермы/места |
| `lib/pages/reports_day_list/data/report_day_group.dart` | `FarmDayListPageArgs`, `ReportsDayListPageArgs` | CURRENT | аргументы двух посуточных страниц назначения — вне этого модуля |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | без параметра `farmId` — при `sync: null` и пустом `animalIds` возвращает перемещения всего приложения |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.dao` (→ `BaseDao.getAll`) | CURRENT | без параметра `farmId` — возвращает все выбытия приложения |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | без параметра `farmId`/`animalId` — возвращает все вакцинации приложения |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReports` | CURRENT | без параметра `farmId` — возвращает все неотправленные инвентаризации приложения |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsByFarmId` | CURRENT | единственный из семи параллельных вызовов, реально фильтрующий по `farmId` на уровне DAO (`dao.getAllByFilters(farmId: farmId)`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | грузит животных всех ферм, фильтрация по `farmId` — в памяти лоадера |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | вызывается отдельно, после `Future.wait`, только по `animalId` животных уже отфильтрованной фермы |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getAll` | CURRENT | справочник причин выбытия, `HANDBOOKS` |
| `lib/widgets/more_menu/more_menu_widget.dart` | `MoreMenuWidget.reportsCalendar` | CURRENT | меню переключения `compact`/`detailed` в шапке |

## Критерии приёмки

- Открытие календаря с панели действий фермы или места вызывает
  `ReportsCalendarCubit.load` ровно один раз с фермой/местом из аргументов
  страницы; отсутствие/наличие `place` в аргументах однозначно определяет
  `isFarmLevel`.
- Если пара `(farmId, placeId)` ещё не загружалась (или изменилась
  относительно предыдущей) — эмитится `loading`, затем
  `ReportsDayDataLoader.load(farmId)` выполняет `Future.wait` на 7
  репозиториев плюс отдельный последующий запрос взвешиваний по `animalId`
  именно этой фермы.
- После загрузки строятся дни месяца через `ReportsDayQuery.buildCalendarDays`,
  результат кладётся в кэш по ключу `"{year}-{month}_{farmId}_{placeId ??
  'all'}"`; соседние (±1) месяцы достраиваются заранее и тоже кэшируются.
- Повторный `load()` с той же парой `(farmId, placeId)` переиспользует уже
  загруженные сырые данные без повторного обращения к `ReportsDayDataLoader`
  — независимо от того, изменился ли переданный месяц.
- Смена `farmId` или `placeId` инициирует повторную загрузку сырых данных и
  полную очистку кэша дней месяца.
- Смена месяца (`changeMonth`, включая свайп `PageView`) и переключение вида
  (`setViewMode`) не вызывают повторного обращения к `ReportsDayDataLoader`.
- Ячейка дня кликабельна только при наличии хотя бы одного типа события и
  принадлежности отображаемому месяцу; тап ведёт на `Routes.farmDayList`
  (при отсутствии `place`) либо `Routes.reportsDayList` (при заданном
  `place`), с соответствующими аргументами (`date`, `farm`[, `place`]).

## Связанные тесты

`test/pages/reports_calendar_cubit_test.dart`, группа `'UC-199 —
ReportsCalendarCubit.load'` (имя группы приведено дословно — несовпадение с
id этого документа, `UC-199`, зафиксировано ниже в «Открытые вопросы», не
исправляется в этом проходе):

- `'первая загрузка -> loaded с текущей фермой'` — прямое доказательство
  основного потока (шаги 3–10): единственный вызов `dataLoader.load(farmId:
  1)`, итоговое состояние `loaded`.
- `'повторный load() с той же фермой -> dataLoader не вызывается снова
  (кэш)'` — доказательство первого пункта «Альтернативных потоков»: второй
  `load()` вызван с другим `month`, `dataLoader.load` всё равно вызван ровно
  1 раз.
- `'load() со сменой фермы -> dataLoader вызывается заново'` —
  доказательство инвалидации кэша по смене `farmId` (по одному вызову
  `dataLoader.load` на каждую из двух ферм).
- `'ошибка dataLoader -> исключение пробрасывается (нет try/catch в
  load())'` — четвёртый под-тест той же группы; относится к ветке
  `READ_ERROR` того же события ([EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)),
  не к этому документу — упомянут здесь только для полноты состава группы,
  не как доказательство `OK`-потока.

Вспомогательные, безномерные группы того же файла — покрывают механику
контейнера (кэш дней, переключение вида), не сам сценарий открытия:

- `group('ReportsCalendarCubit.changeMonth')` — 2 теста: смена месяца без
  повторного вызова `dataLoader`; `changeMonth` до первого `load()` —
  `_emitMonth` ничего не делает (`_rawData == null`), состояние остаётся
  `initial`.
- `group('ReportsCalendarCubit.setViewMode')` — 3 теста: смена вида в
  `loaded`; то же значение вида — no-op (`identical` состояние не
  переэмичено); смена вида до `load()` — работает уже в `initial`
  (доказательство того, что `setViewMode` не зависит от текущего варианта
  состояния).
- `group('ReportsCalendarCubit.cachedDaysForMonth')` — 2 теста: месяц вне
  кэша → пустой список; после `load()` текущий месяц закэширован (проверяет
  только сам факт наличия списка, не его содержимое — см. «Открытые
  вопросы»).

Ни `ReportsDayDataLoader.load`, ни `ReportsDayQuery.buildCalendarDays`
отдельными тестовыми файлами не покрыты (`find test -iname
"*reports_day_query*"`/`*reports_day_data_loader*"` — пусто); единственная
точка, где эти два символа задействованы тестами — косвенно, через
`MockReportsDayDataLoader` (сам лоадер целиком подменяется дублёром) в этом
же файле и в `test/pages/reports_day_list_cubit_test.dart`/`test/pages/farm_day_list_cubit_test.dart`
— тесты кубитов посуточного экрана, уже вне границ этого модуля (см.
`MOD-7`, «Граница»).

## Открытые вопросы и ограничения

- **Историческая нумерация группы теста.** Группа `'UC-199 —
  ReportsCalendarCubit.load'` носила старый id `UC-300` до переименования в
  рамках этого же прохода — правило «tests link back by self-naming»
  (`../use-cases/AGENTS.md`) теперь механически выполняется
  (`grep -r "UC-199" test/` находит эту группу). Соседний файл
  `test/pages/reports_day_list_cubit_test.dart` (и
  `test/pages/farm_day_list_cubit_test.dart`) называли свои группы по
  номерам `UC-301`…`UC-304` до аналогичного переименования на `UC-203`/
  `UC-204` в рамках специфицирования [EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md) —
  см. [UC-203](UC-203-ACTOR-1-EVT-101-ENT-11-READ_OK-IN-SYSTEM.md)/[UC-204](UC-204-ACTOR-1-EVT-101-ENT-11-READ_ERROR-IN-SYSTEM.md).
  Оба флоу «календарь/день» использовали общую практику проставления
  номеров тестовых групп заранее, до фактического прохода спецификации, с
  расчётом на будущие id, которые в итоге получились другими.
- **Индикаторы дней не проверены ни одним тестом с непустыми данными.**
  Все 4 теста группы `'UC-199 — ReportsCalendarCubit.load'` и оба теста
  `'ReportsCalendarCubit.cachedDaysForMonth'` используют `_rawData()` со
  всеми пустыми списками (`movements`/`disposals`/`vaccinations`/`weighings`/…
  — везде `const []`). `ReportsDayQuery.buildCalendarDays` вызывается в
  каждом из них, но никогда не с данными, способными породить непустой
  `reportTypes` хотя бы на одном дне — содержательное ядро этого
  `READ_OK`-сценария (какие именно точки/чипы появляются на календаре)
  задокументировано здесь статическим чтением кода, но не подтверждено
  тестом с реальными данными ни на уровне `ReportsCalendarCubit`, ни
  отдельным тестовым файлом `ReportsDayQuery`.
- **Четыре из семи параллельных запросов `ReportsDayDataLoader.load` не
  фильтруют по `farmId` на уровне БД/API.** `getMovementsWithDetailsByFilters(sync:
  null)`, `dao.getAll()` (выбытия), `getInventoryReports()`,
  `getVaccinationsWithDetails()` не принимают ограничивающий параметр
  `farmId`/`animalIds` — при каждом открытии календаря любой фермы в
  память загружаются перемещения/выбытия/неотправленные
  инвентаризации/вакцинации **всего приложения** целиком; корректность
  итогового результата обеспечена только тем, что `ReportsDayQuery`
  полностью пере-фильтровывает каждый источник по `placeId`/`placeIds`
  (или явно `farmId` — вакцинации) на этапе построения дней. Для аккаунта
  с несколькими фермами стоимость открытия календаря одной фермы растёт с
  общим числом ферм/животных/событий на устройстве, а не с размером именно
  открытой фермы. Не зафиксировано, является ли это осознанным компромиссом
  ради простоты одного `Future.wait` или недосмотром.
- **Вариант состояния `ReportsCalendarState.error` структурно недостижим в
  текущем коде** (см. «Альтернативные потоки») — единственный найденный
  отказ (исключение `_dataLoader.load()`) не превращается в этот вариант, а
  всплывает необработанным; ветка `error` в `reports_calendar_view.dart`
  не достигается ни при каком известном сегодня пути выполнения. Не
  проверено, существовало ли когда-либо в истории кода место, реально
  переводившее кубит в `error` (например, до перехода на текущий
  `ReportsDayDataLoader`/мок-дублёр в тестах) — вне рамок этого
  документирующего прохода.
- **Кэш сырых данных не инвалидируется реактивно, пока сам экран календаря
  открыт.** `_rawData` загружается один раз на пару `(farmId, placeId)` и не
  обновляется при изменении данных на другом экране — если пользователь, не
  покидая экран календаря (например, через вложенный посуточный экран и
  возврат назад), создаст/изменит запись, влияющую на индикаторы месяца,
  снимок в `_rawData`/`_monthDaysCache` этого не увидит вплоть до
  повторного `load()` с изменившейся парой `(farmId, placeId)` — простое
  возвращение на тот же экран календаря с той же фермой/местом снова
  использует ветку кэша. Не проверено эмпирически (нет теста,
  воссоздающего сценарий «вернулись после создания события в тот же день»).
- **Отсутствие auth-guard на маршруте не подтверждено сквозным тестом.**
  Наблюдение в «Пользователь»/«Технические зависимости» (нет
  `AppCacheService.isAuthorized()` вокруг поддерева `Routes.reportsCalendar`
  в `routes.dart`, в отличие от двух других мест того же файла) сделано
  статическим чтением кода, не подтверждено виджет-тестом с гостевой
  сессией; сама вероятность гостевого доступа согласуется с доменной
  моделью (фермы/места — local-first, доступны и гостю), но факт того, что
  [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) (заморожен)
  называет единственным инициатором [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md),
  а не также [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), этим документом
  не пересматривается.
- Не проверено эмпирически на реальном запуске приложения — весь вывод
  сделан статическим чтением кода (`ReportsCalendarCubit`,
  `ReportsDayDataLoader`, `ReportsDayQuery.buildCalendarDays`,
  `ReportsCalendarPopulated`) и разбором существующих тестов; поведение
  реальных Drift-запросов на большом объёме данных (стоимость `Future.wait`
  на семи репозиториях, растущих со всем приложением, см. выше) этим
  проходом не измерено.
