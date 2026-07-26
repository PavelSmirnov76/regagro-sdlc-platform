# UC-200 — Открытие календаря событий отказывает: `ReportsCalendarCubit.load()` без `try/catch` превращает любое исключение чтения в зависший навсегда экран загрузки

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же контейнер календаря, что описан в [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) —
`ReportsCalendarCubit.load(farm, place, month)` при первом открытии экрана
(или при смене фермы/места) грузит все сырые данные фермы разом через
`ReportsDayDataLoader.load(farmId)` — 7 репозиториев внутри одного
`Future.wait`, плюс отдельный, тоже не защищённый 8-й вызов взвешиваний.
Здесь описан единственный путь отказа этого чтения, подтверждённый
существующим тестом: `ReportsCalendarCubit.load()` не оборачивает
`await _dataLoader.load(farmId: farmId)` ни в какой `try/catch` — если
любой из этих локальных вызовов бросает исключение, оно просто
пробрасывается наружу из `load()`.

Наблюдаемый эффект принципиально отличается от уже задокументированных
сценариев `SYSTEM`/`BOARD` ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md),
[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)), где отказ
тонет **внутри** репозитория и sync-проход или реактивный пересчёт
завершаются штатно. Здесь исключение никуда не тонет содержательно — оно
пробрасывается по цепочке до самого верха, но единственная точка создания
этого кубита (`ReportsCalendarView.build`, `BlocProvider(create: (context) =>
ReportsCalendarCubit()..load(farm: args.farm, place: args.place))`) вызывает
`load()` через cascade-оператор **без `await`**: возвращаемый `Future<void>`
отбрасывается, и исключение становится необработанной ошибкой асинхронного
`Future`, а не наблюдаемым сбоем экрана. Итог для пользователя — не
сообщение об ошибке, а бесконечный спиннер загрузки: состояние кубита
застревает на `ReportsCalendarState.loading(...)` навсегда, потому что
единственный код, который довёл бы его до `loaded` (`_emitMonth`), лежит
после отказавшего `await` и никогда не выполняется. `ReportsCalendarState.error`
существует как вариант состояния и отрисовывается `ReportsCalendarView`, но
ни разу не конструируется внутри `ReportsCalendarCubit` — заготовка для
показа ошибки есть, подключения к ней нет.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
открывающий календарь событий фермы или места. Единственные два реально
найденных в `lib/` входа на этот экран — иконка «l10n.weekly_planner» на
панели действий фермы (`FarmActionsWidget`,
`lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`,
`context.pushNamed2(Routes.reportsCalendar, extra: ReportsCalendarPageArgs(farm:
farm))`) и симметричная иконка на панели действий места
(`PlaceActionsWidget`, `lib/pages/place/widgets/place_actions_widget.dart`,
`extra: ReportsCalendarPageArgs(farm: farm, place: placeWithAnimals)`). Оба
входа всегда передают непустой `extra` — сам отказ, документируемый здесь,
происходит не в момент навигации, а сразу после неё, при первой попытке
кубита загрузить данные. Прямого действия пользователя в момент самого
отказа (внутри `Future.wait`) нет — открытие экрана уже произошло, дальше
всё идёт асинхронно и без дальнейшего участия пользователя, как и в
остальных `READ`-сценариях этого типа.

## CURRENT

### Основной поток

1. Пользователь нажимает иконку календаря на панели действий фермы или
   места — `context.pushNamed2(Routes.reportsCalendar, extra:
   ReportsCalendarPageArgs(...))`.
2. `ReportsCalendarPage` (`lib/pages/reports_calendar/presentation/reports_calendar_page.dart`)
   — тонкая обёртка, сразу строит `ReportsCalendarView`.
3. `ReportsCalendarView.build` (`lib/pages/reports_calendar/presentation/widgets/reports_calendar_view.dart`)
   читает аргументы через `GoRouterState.of(context).getExtraByName<ReportsCalendarPageArgs>(Routes.reportsCalendar)`
   и строит `BlocProvider(create: (context) => ReportsCalendarCubit()..load(farm:
   args.farm, place: args.place), child: BlocBuilder<ReportsCalendarCubit,
   ReportsCalendarState>(...))`.
4. Cascade-оператор `..load(...)` вызывает `ReportsCalendarCubit.load()`
   синхронно вплоть до первого `await` (async-функции в Dart выполняются
   синхронно до первой точки ожидания) — к моменту, когда `create`
   возвращает управление `BlocProvider`, `load()` уже успел вычислить
   `displayedMonth`, `farmId` (`farm?.farm.remoteId ?? place?.place.farmId ?? 0`),
   определить `scopeChanged` (истинно при первом открытии — `_rawDataFarmId`/
   `_rawDataPlaceId` изначально `null`) и, так как `_rawData == null` тоже
   истинно, выполнить `emit(ReportsCalendarState.loading(newData))`. Экран
   сразу показывает `CustomLottieLoader` (ветка `loading` в
   `state.when(...)` `ReportsCalendarView`).
5. Тем же вызовом `load()` продолжается: `_rawData = await
   _dataLoader.load(farmId: farmId);` — именно эта строка отдаёт управление
   без ожидания снаружи: вызвавший код (шаг 3) отбросил `Future<void>` от
   `load()` через cascade, поэтому `load()` с этого момента выполняется как
   ничем не отслеживаемая «оторванная» асинхронная задача.
6. Внутри `ReportsDayDataLoader.load(farmId)`
   (`lib/pages/reports_day_list/data/reports_day_data_loader.dart`):
   `await Future.wait([_movementRepo.getMovementsWithDetailsByFilters(sync:
   null), _disposalRepo.dao.getAll(), _reportAnimalsRepo.getReportsByFarmId(farmId),
   _unsentReportAnimalsRepo.getInventoryReports(),
   _animalsRepo.getAllAnimalsWithDetailsByFilters(isNotDeleted: null,
   isShowRemoteSource: null), _vaccinationsRepo.getVaccinationsWithDetails(),
   _disposalReasonsRepo.getAll()])` — семь параллельных вызовов, все —
   локальные чтения Drift/DAO, ни один не обращается к сети (в отличие от
   [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)/[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md),
   где отказ приходит из сети). В этом сценарии один из семи бросает
   исключение (конкретная причина — повреждение локальных данных,
   несовместимая миграция схемы, сбой запроса DAO/join и т.п. — не
   воспроизведена эмпирически, см. «Открытые вопросы»).
7. Ни `ReportsDayDataLoader.load`, ни вызывающий его `ReportsCalendarCubit.load`
   не оборачивают этот вызов в `try/catch`. `Future.wait` (аргумент
   `eagerError` не передан, по умолчанию `false`) дожидается завершения
   (успехом или ошибкой) всех семи futures, но, поскольку хотя бы одна из
   них завершилась ошибкой, сам `Future.wait` в итоге тоже завершается
   ошибкой — она всплывает из `ReportsDayDataLoader.load` прямо на `await`
   шага 5, ничем не перехваченная.
8. Так как этот `await` внутри `load()` не обёрнут в `try/catch`, а сам
   `load()` не awaited вызывающей стороной (шаг 3), исключение становится
   необработанной асинхронной ошибкой `Future`, а не наблюдаемым состоянием
   кубита. Она **не** проходит через `Cubit.onError`/`Bloc.observer.onError`
   (`TalkerBlocObserver`, зарегистрированный глобально в
   `lib/injection_container.dart` как `Bloc.observer = TalkerBlocObserver(...)`):
   в `package:bloc` (`bloc-9.0.1`, `lib/src/bloc_base.dart`) собственный
   `try/catch`→`onError` есть только вокруг самого вызова `emit()` — здесь
   исключение брошено раньше и без единого `emit` на своём пути, поэтому
   `onError` не вызывается ни разу и запись об этом отказе не попадает даже
   в лог `Talker`/`TalkerScreen`.
9. `lib/main.dart`'s `runApp(const MyApp())` не обёрнут ни в какую
   зону-обработчик: `runTalkerZonedGuarded(getIt<Talker>(), () =>
   runApp(const MyApp()), (error, stack) { getIt<Talker>().handle(error,
   stack); });`, который перенаправлял бы такую ошибку в собственный
   `Talker`-лог приложения, закомментирован — тот же факт, что уже
   задокументирован для другого сценария в
   [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md). `grep -rn
   "FlutterError.onError\|PlatformDispatcher.instance.onError\|runZonedGuarded"
   lib/` не находит ни одного места, где такая зона была бы настроена. Без
   собственной зоны исключение доходит до зоны Dart по умолчанию, которая
   печатает его в консоль/stderr и не завершает работающий изолят —
   единственный след этого отказа виден только тому, кто смотрит в
   debug-консоль запущенного процесса; ни пользователь, ни какой-либо экран
   приложения этого не видят.
10. Так как код после отказавшего `await` (`_rawDataFarmId = farmId;
    _rawDataPlaceId = placeId; _monthDaysCache.clear(); _emitMonth(newData);`)
    ни разу не выполняется, состояние кубита остаётся ровно тем, что было
    эмитировано на шаге 4 — `ReportsCalendarState.loading(newData)` — на
    неограниченный срок. `ReportsCalendarView`'s `state.when(... loading: (_)
    => const Center(child: CustomLottieLoader(size:
    CustomLottieLoaderSize.small)) ...)` продолжает показывать спиннер без
    какого-либо таймаута.
11. `ReportsCalendarState.error` (`lib/pages/reports_calendar/cubit/reports_calendar_state.dart`)
    отрисовывается `ReportsCalendarView` (`error: (data) => Center(child:
    Text(data.errorMessage ?? ''...))`), но во всём файле
    `reports_calendar_cubit.dart` единственная ссылка на этот вариант —
    внутри `setViewMode`'s `state.when(..., error: (_) =>
    emit(ReportsCalendarState.error(newData)), ...)`, которая лишь
    переэмитит **уже существующее** `error`-состояние с новыми данными; она
    не может перевести кубит в `error` из какого-либо другого состояния.
    Никакой `emit`, конструирующий `ReportsCalendarState.error(...)` «с
    нуля», в кубите не найден — ветка отображения ошибки в
    `ReportsCalendarView` для этого (и вообще любого) сценария сегодня
    структурно недостижима.
12. Единственный выход для пользователя — уйти с экрана вручную (назад по
    навигации); ни кнопки повтора, ни какого-либо текста, объясняющего
    зависание, на `ReportsCalendarView` нет.

### Альтернативные потоки

- **Успешный путь — контраст, не этот сценарий.** Если ни один из семи
  вызовов `Future.wait` (и, если он достигается, восьмой условный вызов
  взвешиваний — см. ниже) не бросает исключения, `_dataLoader.load`
  разрешается нормально, `_emitMonth(newData)` выполняется, состояние
  переходит в `loaded`. Этот путь — `READ_OK`, документирован отдельным
  use-case, использующим ту же тестовую группу (см. «Связанные тесты»), не
  входит в этот документ.
- **Смена фермы/места после уже успешной загрузки — тот же класс отказа при
  повторном вызове.** Если предыдущий `load()` завершился успехом (`_rawData
  != null`), а затем `farmId`/`placeId` изменились (`scopeChanged == true`),
  `load()` снова входит в ветку `if (scopeChanged || _rawData == null)` и
  вызывает `_dataLoader.load` заново. Если этот повторный вызов бросает
  исключение — эффект тот же: состояние застревает на только что
  эмитированном `loading(newData)`, при этом ранее показанный `loaded`
  экран (с реальными днями месяца) исчезает без возможности вернуться к
  нему иначе, чем полным выходом и повторным входом на экран (что создаёт
  новый экземпляр кубита и без того теряет весь предыдущий кэш
  `_monthDaysCache`).
- **`changeMonth`/`setViewMode`, вызванные, пока кубит уже завис на
  `loading`.** `changeMonth` вызывает `_emitMonth(newData)`, а
  `_emitMonth` содержит собственную защиту `if (_rawData == null) return;` —
  поскольку `_rawData` действительно остаётся `null` (шаг 6 отказал раньше,
  чем успел его присвоить), вызов молча ничего не делает, крэша нет, но и
  восстановления тоже нет. `setViewMode`, в отличие от `_emitMonth`, не
  проверяет `_rawData` вовсе — она напрямую переэмитит **тот же** вариант
  состояния (`state.when(loading: (_) => emit(ReportsCalendarState.loading(newData)),
  ...)`) с обновлённым `viewMode`; косметически безобидно, к восстановлению
  экрана не приводит. `cachedDaysForMonth` для любого месяца просто
  возвращает `[]` (кэш не был заполнен ни разу) — тоже безобидно.
- **Восьмой, условный вызов взвешиваний — отдельный, не покрытый общим
  `Future.wait` источник того же по характеру отказа.** После разрешения
  семи параллельных вызовов `ReportsDayDataLoader.load` вычисляет
  `farmAnimals`/`animalIds` из результата `_animalsRepo...` и, только если
  `animalIds` непуст, отдельно (уже не внутри `Future.wait`, последовательным
  `await`) вызывает `_weighingsRepo.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds)`.
  Этот вызов тоже не обёрнут в `try/catch` — исключение отсюда проходит
  ровно тот же путь (шаги 7–12 выше), просто наступает на шаг позже, уже
  после того как семь параллельных чтений успешно завершились.
- **Тангенциальная находка иной природы — не этот сценарий.**
  `GoRouterStateExtension.getExtraByName` (`lib/widgets/go_router/go_router_state.dart`)
  делает непроверенный `(extra as Map<String, dynamic>)[name] as T` — бросил
  бы исключение, если бы `extra` был `null` или неверной формы. Оба реально
  найденных источника навигации на этот экран (`FarmActionsWidget`,
  `PlaceActionsWidget`) всегда передают корректный `extra`, поэтому этот
  путь не наступает на практике. Даже если бы наступил — это исключение
  бросается синхронно внутри `StatelessWidget.build`, которое фреймворк
  Flutter перехватывает и отрисовывает собственным экраном ошибки
  (`FlutterError.reportError`/дефолтный error widget) — принципиально иной,
  куда более заметный отказ, не покрываемый этим документом.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `_animalsRepo.getAllAnimalsWithDetailsByFilters(isNotDeleted: null,
  isShowRemoteSource: null)`, один из семи параллельных вызовов, чей отказ
  документирует этот сценарий; результат также используется для отбора
  `animalIds`, передаваемых восьмому (условному) вызову взвешиваний. Ничем
  не изменяется этим сценарием — чистое чтение.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — читается
  через `MovementReportRepository.getMovementsWithDetailsByFilters(sync:
  null)`.
- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  читается через `VaccinationsRepository.getVaccinationsWithDetails()`.
- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  читается условным восьмым вызовом,
  `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`
  — отдельный, не защищённый общим `Future.wait` источник того же по
  характеру отказа (см. «Альтернативные потоки»).
- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — читается
  через прямой доступ к DAO, `_disposalRepo.dao.getAll()` (вся таблица, без
  фильтра по ферме на этом этапе — фильтрация происходит позже, в
  `ReportsDayQuery.buildCalendarDays`, в этом сценарии не достигаемой).
- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — читается дважды, отдельными вызовами:
  `_reportAnimalsRepo.getReportsByFarmId(farmId)` (таблица `ReportAnimals`) и
  `_unsentReportAnimalsRepo.getInventoryReports()` (таблица
  `UnsentReportAnimals`).
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — читается через `_disposalReasonsRepo.getAll()`, используется
  только для построения карты отображаемых названий причин выбытия
  (`disposalReasonsById`) — в этом сценарии до использования результата дело
  не доходит.

### Бизнес-правила

- Первая загрузка экрана (и любая последующая смена фермы/места) неявно
  требует, чтобы **все** как минимум семь (до восьми, считая условный вызов
  взвешиваний) независимых локальных чтений завершились успехом — правило
  «всё или ничего» реализовано самим использованием `Future.wait` без
  индивидуальной обработки ошибок каждого источника, а не как осознанное
  продуктовое решение «не показывать частично загруженный календарь».
- Ни один из этих семи-восьми вызовов не обращается к сети — это
  единственный из просмотренных на сегодня `READ_ERROR`-сценариев `SYSTEM`,
  где источник отказа — локальная СУБД (Drift/`sqlite3`), а не бэкенд;
  такой отказ структурно маловероятнее сетевого, но ничем не защищён, если
  всё же происходит.
- У экрана нет собственной политики повтора/таймаута для этого чтения:
  единственный способ восстановления — выйти и снова открыть экран, что
  создаёт новый экземпляр `ReportsCalendarCubit` и запускает `load()` с
  нуля (без гарантии, что причина исходного отказа к этому моменту
  исчезла).
- Экран календаря — read-only отображение уже существующих фактов ANIMAL
  (движение/вакцинация/выбытие/взвешивание/инвентаризация/регистрация,
  см. границу модуля в [MOD-7](../modules/MOD-7-SYSTEM.md)) — сам этот
  сценарий не пишет и не портит ни одну из связанных сущностей, весь эффект
  ограничен состоянием UI одного экрана.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Сценарий (отсутствие `try/catch` вокруг
`await _dataLoader.load(farmId: farmId)` внутри `ReportsCalendarCubit.load()`,
проброс исключения из невожидаемого cascade-вызова в `BlocProvider.create`,
отсутствие обработки на уровне `Cubit.onError`/`Bloc.observer` и отсутствие
зонного перехвата в `main.dart`) полностью воспроизводится статическим
чтением кода и подтверждается существующим unit-тестом на уровне самого
кубита (см. «Связанные тесты»). Исправление (например, обёртка `try/catch`
с эмиссией `ReportsCalendarState.error`, либо `await` вместо cascade в месте
создания кубита) в рамках этого документирующего прохода не выполняется —
это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_calendar/cubit/reports_calendar_cubit.dart` | `ReportsCalendarCubit.load` | CURRENT | не оборачивает `await _dataLoader.load(farmId: farmId)` в `try/catch`; при исключении не эмитит `ReportsCalendarState.error`, метод просто прерывается |
| `lib/pages/reports_calendar/cubit/reports_calendar_cubit.dart` | `ReportsCalendarCubit._emitMonth` | CURRENT | единственный код, который довёл бы состояние до `loaded`; в этом сценарии никогда не достигается |
| `lib/pages/reports_calendar/cubit/reports_calendar_state.dart` | `ReportsCalendarState.error` | CURRENT | вариант состояния существует и отрисовывается `ReportsCalendarView`, но нигде в `ReportsCalendarCubit` не конструируется «с нуля» — только переэмитится, если уже был `error`, внутри `setViewMode` |
| `lib/pages/reports_calendar/presentation/widgets/reports_calendar_view.dart` | `ReportsCalendarView.build` | CURRENT | создаёt кубит через `BlocProvider(create: (context) => ReportsCalendarCubit()..load(...))` — cascade без `await`; исключение из `load()` становится необработанной ошибкой `Future` |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | `Future.wait` без `try/catch` поверх семи репозиториев; отдельный, тоже не защищённый условный восьмой вызов взвешиваний |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | один из семи параллельных вызовов — локальный Drift-запрос |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.dao.getAll` | CURRENT | один из семи — прямой доступ к DAO, минуя обёртку репозитория |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsByFarmId` | CURRENT | один из семи |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReports` | CURRENT | один из семи |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | один из семи; результат также определяет `animalIds` для восьмого вызова |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | один из семи |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getAll` | CURRENT | один из семи (наследуется от `BaseRepository.getAll`) |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | восьмой, условный вызов — выполняется вне `Future.wait`, последовательно, тоже без `try/catch` |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | наблюдатель зарегистрирован глобально, но не получает эту ошибку — она не проходит через `emit` |
| `lib/main.dart` | `main()`, закомментированный `runTalkerZonedGuarded` | CURRENT | нет зоны-обёртки вокруг `runApp` — тот же факт, что уже задокументирован в [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) |
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmActionsWidget` — иконка «l10n.weekly_planner» | CURRENT | единственная точка входа с уровня фермы, всегда передаёт `extra` |
| `lib/pages/place/widgets/place_actions_widget.dart` | `PlaceActionsWidget` — иконка «l10n.weekly_planner» | CURRENT | единственная точка входа с уровня места, всегда передаёт `extra` |
| `lib/widgets/go_router/go_router_state.dart` | `GoRouterStateExtension.getExtraByName` | CURRENT | непроверенный каст `extra`; тангенциальная, отдельная от этого сценария находка (см. «Альтернативные потоки») |
| внешний пакет `bloc` (`bloc-9.0.1`), `lib/src/bloc_base.dart` | `BlocBase.emit`, `Cubit.onError` | внешняя зависимость | `emit()` оборачивает только сам себя в `try/catch` → `onError`; исключение, брошенное до/без вызова `emit`, никогда не проходит через `onError` |

## Критерии приёмки

- Если любой из семи параллельных вызовов внутри `ReportsDayDataLoader.load`
  (через `Future.wait`), либо отдельный условный восьмой вызов взвешиваний,
  бросает исключение — `ReportsCalendarCubit.load()` не перехватывает его:
  `await _dataLoader.load(farmId: farmId)` пробрасывает исключение дальше,
  не эмитя `ReportsCalendarState.error`.
- Поскольку `load()` вызывается в `BlocProvider.create` через cascade без
  `await`, это исключение становится необработанной ошибкой асинхронного
  `Future`, не перехватываемой ни `TalkerBlocObserver` (не проходит через
  `emit`), ни каким-либо зонным обработчиком (`runZonedGuarded` не
  используется — закомментирован в `lib/main.dart`).
- Состояние кубита остаётся `ReportsCalendarState.loading(...)` — последним
  состоянием, эмитированным до отказавшего `await`, — на неопределённый
  срок; `ReportsCalendarView` продолжает показывать `CustomLottieLoader`,
  без сообщения об ошибке и без кнопки повтора.
- `ReportsCalendarState.error` не конструируется «с нуля» ни в одном из
  просмотренных путей `ReportsCalendarCubit` — вариант состояния структурно
  недостижим из любого другого состояния (единственная ссылка на него в
  кубите — переэмиссия уже существующего `error`-состояния в
  `setViewMode`).
- Тест `test/pages/reports_calendar_cubit_test.dart`, группа `'UC-199 —
  ReportsCalendarCubit.load'`, под-тест `'ошибка dataLoader -> исключение
  пробрасывается (нет try/catch в load())'`, подтверждает проброс
  исключения через `expectLater(cubit.load(farm: _farm()), throwsA(isA<Exception>()))`.

## Связанные тесты

`test/pages/reports_calendar_cubit_test.dart`, группа `'UC-199 —
ReportsCalendarCubit.load'`, под-тест `'ошибка dataLoader -> исключение
пробрасывается (нет try/catch в load())'`:

```dart
when(() => dataLoader.load(farmId: 1)).thenThrow(Exception('db error'));
final cubit = ReportsCalendarCubit(dataLoader: dataLoader);
addTearDown(cubit.close);

await expectLater(cubit.load(farm: _farm()), throwsA(isA<Exception>()));
```

Это единственный тест, покрывающий именно этот путь отказа. Он проверяет
проброс исключения из `load()` напрямую — в тесте `cubit.load(...)`
целенаправленно awaited (`expectLater(cubit.load(...), throwsA(...))`), в
отличие от продакшен-кода, где тот же вызов не awaited (cascade в
`BlocProvider.create`, см. основной поток). Тест доказывает факт «`load()`
пробрасывает исключение, не перехватывая его», но не воспроизводит и не
может воспроизвести (это уже не то, что можно продемонстрировать голым
unit-тестом кубита без построения виджет-дерева) специфичный для CURRENT
сценарий «необработанная ошибка `Future` из-за отсутствия `await` в месте
создания кубита» — тот факт установлен отдельно, чтением
`reports_calendar_view.dart` и пакета `bloc`, не тестом.

Та же группа теста цитируется для happy-path сценариев (`READ_OK`) в другом
use-case этой же пары событие/сущность — не входит в этот документ.

Единственный тестовый файл `DataUpdateBloc` (`test/blocs/data_update_bloc_test.dart`)
к этому сценарию не относится — календарь не участвует в sync-проходе,
только читает уже локально накопленные данные.

## Открытые вопросы и ограничения

- **Реальный источник исключения не установлен эмпирически.** Какой именно
  из семи-восьми локальных вызовов и при каком состоянии локальной БД
  реально бросает исключение на практике (повреждённые данные, рассинхрон
  миграции схемы, конкретный сбойный `join` в одном из DAO) — не
  воспроизведено; вывод сделан статическим чтением кода и подтверждён
  тестом только на уровне мока всего `ReportsDayDataLoader.load` целиком, не
  отдельного репозитория внутри него. TBD.
- **Механизм «необработанная ошибка `Future` не имеет видимого следствия»
  не проверен эмпирически на реальном запуске.** Вывод построен из чтения
  `lib/main.dart` (`runZonedGuarded`, закомментирован),
  `bloc-9.0.1`'s `BlocBase.emit`/`onError` (внешний пакет, не код проекта) и
  отсутствия `FlutterError.onError`/`PlatformDispatcher.instance.onError`
  где-либо в `lib/` (проверено `grep -rn` по всему каталогу) — не запущено
  реальное приложение/интеграционный тест, подтверждающий, что консоль —
  единственный след этого отказа.
- **Осознанное решение или недосмотр — не зафиксировано.** Отсутствие
  `try/catch` в `ReportsCalendarCubit.load()` при том, что вариант
  `ReportsCalendarState.error` присутствует в модели состояния и уже
  отрисовывается `ReportsCalendarView`, — сильный сигнал в пользу
  недосмотра (заготовка для показа ошибки существует, но не подключена к
  этому пути), но ничем в коде/комментариях прямо не подтверждено.
- **Тангенциальная находка иной природы, здесь не описываемая.**
  `GoRouterStateExtension.getExtraByName` делает непроверенный `as`-каст
  `extra`; оба реальных источника навигации на этот экран всегда передают
  `extra`, поэтому это не тот же класс отказа и не покрывается этим
  документом — упомянуто, чтобы не потерялось при дальнейшей работе с этим
  экраном (см. «Альтернативные потоки»).
- **Нет способа для пользователя отличить «ещё грузится» от «зависло
  навсегда».** Экран не показывает индикатор долгой загрузки, таймаут или
  подсказку — единственный сигнал проблемы, доступный пользователю,
  субъективен («загрузка слишком долго не заканчивается»).
