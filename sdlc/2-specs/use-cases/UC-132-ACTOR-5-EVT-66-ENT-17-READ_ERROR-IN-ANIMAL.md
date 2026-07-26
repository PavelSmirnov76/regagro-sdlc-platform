# UC-132 — Итоговый отчёт по инвентаризации отказывает технически: `InventoryReportDetailsCubit.load` не перехватывает исключение вовсе, а мёртвое поле `isLoading` маскирует сбой под пустой отчёт

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)
(`animal_inventory.viewed_in_day_report`): пользователь открывает итоговый
отчёт по сессии/дню инвентаризации (с завершения сессии сканирования либо из
календаря отчётов), а `InventoryReportDetailsCubit.load`
(`lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart`) — при
исключении, брошенном в любой точке чтения/сопоставления данных — не
перехватывает его вообще. Перепроверено чтением метода и файла состояния
целиком: подтверждены два независимых дефекта, каждый сам по себе достаточный,
чтобы сделать сбой невидимым для пользователя, а вместе складывающиеся в один
наблюдаемый эффект — экран молча выглядит как «на этом месте нет животных»:

- (а) **Нет `try/catch` вовсе.** В отличие от `UnsentInventoriesCubit.load`
  (соседний read-сценарий той же под-области `INV`, тот же
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), см.
  [UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md)),
  `InventoryReportDetailsCubit.load` ни разу не оборачивает свои обращения к
  репозиториям в `try`/`catch` — ни к одному из шести (`ReportAnimalsRepository`,
  `UnsentReportAnimalsRepository`, `AnimalIdentificationsRepository`,
  `AnimalsRepository`, `FarmRepository`, `PlaceRepository`). Исключение из
  любого из них отклоняет `Future<void>`, возвращаемый `load()`, необработанным.
- (б) **`isLoading` — мёртвое поле.** `@Default(false) bool isLoading`
  (`inventory_report_details_state.dart`) не устанавливается в `true` ни в
  одной из трёх точек `emit` внутри `load()` (перепроверено `grep -rn
  "isLoading"` по всей папке `lib/pages/animals_inventory/` — единственные
  вхождения вне сгенерированного `*.freezed.dart` это объявление
  `@Default(false)` и два места чтения в `inventory_report_details_view.dart`,
  ни одного присваивания `true`). Ветка `if (state.isLoading) return
  CircularProgressIndicator()` в `_buildBody` — фактически мёртвый код: она
  никогда не выполняется ни при штатной загрузке, ни при сбое, потому что
  условие `state.isLoading` тождественно `false` на протяжении всего времени
  жизни кубита.

Порознь (а) означало бы «сбой оставляет экран в последнем показанном
состоянии» (как у `AnimalWeighingsCubit.load`,
[UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md) — вечный спиннер,
хотя бы видимый как спиннер). Здесь же (б) делает это «последнее показанное
состояние» неотличимым от пустого валидного отчёта: пользователь не видит ни
спиннера, ни ошибки — только пустые секции, как если бы на месте
содержания действительно не было ни одного животного.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Проверено чтением
`inventory_report_details_cubit.dart` и `inventory_report_details_view.dart`
целиком: ни `AuthRepository`, ни `isAuthorized` нигде не встречаются (`grep
-n "AuthRepository\|isAuthorized"` — без совпадений) — доступ к итоговому
отчёту по инвентаризации не зависит от статуса авторизации.

## CURRENT

### Основной поток

1. Два равнозначных входа на этот экран (см.
   [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)):
   - **(а)** пользователь только что завершил сессию сканирования —
     `ScanningBloc` эмитит `ScanningExit`, `_ScanningPageState`'s
     `BlocConsumer.listener` (`lib/pages/scanning/scanning_page.dart`) при
     `state.type.type == 'inventory' && state.time != null` вызывает
     `context.pushNamed2(Routes.inventoryReport, extra:
     InventoryReportPageArgs(date: state.time!, sessionUuid:
     state.sessionUuid, farmId: args!.farm?.farm.remoteId ??
     args.place?.farmId, placeId: state.placeId))`;
   - **(б)** пользователь открывает посуточный отчёт из календаря —
     `ReportsDayListPopulated._navigateItem`
     (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`),
     ветка `case InventoryDayItem(...)`, тот же `context.pushNamed2(
     Routes.inventoryReport, extra: InventoryReportPageArgs(date:, sessionUuid:,
     farmId:, placeId:))`.
2. `InventoryReportDetailsView.build`
   (`lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`)
   читает аргументы (`GoRouterState.of(context).getExtraByName<
   InventoryReportPageArgs>(Routes.inventoryReport)`) и создаёт
   `BlocProvider(create: (context) => InventoryReportDetailsCubit(date:
   args.date, sessionUuid: args.sessionUuid, farmId: args.farmId, placeId:
   args.placeId)..load(), ...)` — вызов `load()` через каскадный оператор
   (`..`), синхронно с созданием кубита. Каскад возвращает сам объект
   `InventoryReportDetailsCubit`, а не `Future<void>`, который вернул бы
   вызов `load()` — `create` не сохраняет и не `await`'ит этот `Future`
   (тот же паттерн «fire-and-forget», что и в
   [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)).
3. Конструктор кубита вызывает `super(InventoryReportDetailsState(date:
   date))` — уже на этом шаге, до первой строки `load()`, состояние имеет
   `isLoading: false` (значение по умолчанию) и пустые
   `myAnimalsByKind`/`otherAnimals`/`allAnimals`, `farm`/`place == null`.
4. `load()` начинается строкой `emit(InventoryReportDetailsState(date:
   state.date))` — повторно тот же «пустой» снимок состояния, без установки
   `isLoading: true`. Это единственная строка метода, которая гарантированно
   выполняется до первого потенциально бросающего исключение `await`.
5. Далее — в зависимости от того, передан ли `_sessionUuid` (не `null` для
   входа (а) и для большинства заходов (б), т.к. `InventoryDayItem` тоже
   несёт `sessionUuid`; путь без него — легаси-случай):
   - с `_sessionUuid`: `await _unsentReportsRepository.getInventoryReportsByUuid(_sessionUuid)`,
     затем `await _inventoryReportRepository.getInventoryReportsByUuid(_sessionUuid)`;
   - без него: `await _inventoryReportRepository.getInventoryReportsByDate(state.date)`,
     затем `await _unsentReportsRepository.getInventoryReportsByDate(state.date)`.
   Ни один из этих четырёх вызовов не обёрнут ни в какой `try`/`catch` — ни
   локально в методе, ни внутри самих репозиториев (`ReportAnimalsRepository`/
   `UnsentReportAnimalsRepository` — тонкие делегации в DAO без собственной
   обработки ошибок).
6. **Точка технического сбоя (этот сценарий).** Любой из четырёх вызовов шага
   5 бросает исключение (например, ошибка Drift-запроса на уровне DAO).
   Исключение не перехватывается ничем внутри `load()` — выполнение метода
   останавливается немедленно, а `Future<void>`, возвращаемый вызовом
   `load()`, отклоняется этим же исключением.
7. Поскольку `load()` вызван каскадом на шаге 2 (без `await`, без
   `.catchError`), это — необработанное отклонение `Future`
   («fire-and-forget»): оно не долетает ни до `BlocProvider`, ни до
   `BlocBuilder`, ни до какого-либо явного обработчика приложения.
   `lib/main.dart`: `runApp(const MyApp())` вызывается напрямую; строка
   `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const MyApp()),
   (error, stack) { getIt<Talker>().handle(error, stack); });` закомментирована
   целиком (проверено чтением файла) — исключение не попадает ни в `Talker`,
   ни в какой-либо иной явный error-handler приложения. Единственный вызов
   `Talker` внутри самого `load()` — `getIt.get<Talker>().info('[InventoryReportDetailsCubit]
   date=..., sessionUuid=..., found ${reports.length} reports')` — это
   информационная строка на успешном пути **после** шага 5, она не пишется
   вообще, если исключение произошло на самом шаге 5, и в любом случае не
   является логированием ошибки.
8. Состояние кубита остаётся ровно тем, что было эмитировано на шаге 4 —
   `InventoryReportDetailsState(date: date)` с пустыми
   `myAnimalsByKind`/`otherAnimals`/`allAnimals`, `farm`/`place == null`,
   `isLoading: false`. Дальнейших `emit` в этом вызове `load()` не происходит.
9. `InventoryReportDetailsView`'s `BlocBuilder` рендерит это состояние через
   `_buildBody`: `if (state.isLoading)` — `false`, ветка спиннера
   (`CircularProgressIndicator`) не выполняется (см. дефект (б) выше);
   выполняется `_computeSections(context, state)` над пустым
   `state.myAnimalsByKind` — возвращает четыре пустых списка (`scanned`,
   `absent`, `knownForeign`, `unknownNumbers: state.otherAnimals` тоже
   пустой) — и `InventoryAccordionListWidget` рендерится с нулевым
   содержимым во всех секциях. Кнопка экспорта в `AppBar.actions`
   (`!state.isLoading && state.myAnimalsByKind.isNotEmpty`) тоже не
   показывается — оба операнда условия ложны/пусты, тот же результат, что и
   для честного пустого отчёта.
10. Пользователь видит полностью отрисованный экран отчёта с нулевыми
    секциями — ни спиннера, ни сообщения об ошибке, ни какого-либо признака
    того, что загрузка вообще не завершилась штатно. Единственный способ
    покинуть это состояние — стандартная кнопка «назад» `CustomAppBar`; на
    самом экране нет ни кнопки повтора, ни `RefreshIndicator` (тело —
    обычный `SingleChildScrollView`, не обёрнутый в `RefreshIndicator`).
    Повторное открытие экрана (снова со сканирования или снова из календаря)
    создаёт новый `InventoryReportDetailsCubit` и заново вызывает `load()`;
    если причина сбоя не была разовой (например, повреждённые данные
    конкретной сессии), повтор откажет тем же образом.

### Альтернативные потоки

- **Исключение позже в методе, уже после успешного шага 5 (`reports`
  непустой).** Если `reports.isEmpty` после шага 5 — метод сразу же
  `emit(InventoryReportDetailsState(date: state.date))` и `return` (см. ниже,
  отдельный, не-ошибочный путь). Если же `reports` непуст, метод продолжает:
  `await _identificationsRepository.getAll()`, затем `await
  _animalsRepository.getAllAnimalsWithDetailsByFilters()`, затем `await
  _farmsRepository.getById(_farmId ?? reports.first.farmId)`, затем `await
  _placesRepository.getById(_placeId ?? reports.first.placeId)` — любой из
  этих четырёх тоже не обёрнут ни в какой `try`/`catch` и приводит к
  идентичному итоговому эффекту (шаги 6–10 основного потока): состояние
  замирает на той же «пустой» форме, эмитированной шагом 4, потому что
  между шагом 4 и финальным `emit` (в самом конце метода) кубит не делает ни
  одного промежуточного `emit`.
- **Внутренний null-check, а не вызов репозитория, как источник исключения.**
  `final myAnimalsByKind = animals.fold<Map<Kind, List<AnimalWithDetails>>>(
  {}, (acc, e) => acc..putIfAbsent(e.kind!, () => []).add(e));` — `Kind?
  kind` на `AnimalWithDetails` (`packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart`)
  допускает `null`; если хотя бы одно животное, вернувшееся из
  `getAllAnimalsWithDetailsByFilters()`, имеет `kind == null`, оператор `!`
  бросает `Null check operator used on a null value` — восьмая по счёту (и
  единственная не-репозиторная) незащищённая точка отказа того же метода, с
  тем же итоговым эффектом.
- **`reports.isEmpty` после успешного шага 5 — не этот сценарий.** Это
  легитимный, не ошибочный короткий путь: `if (reports.isEmpty) {
  emit(InventoryReportDetailsState(date: state.date)); return; }` — то же
  самое «пустое» состояние, что и при сбое (шаг 8), эмитируется намеренно,
  без исключения. Использованная здесь форма состояния физически
  неотличима от состояния, замёрзшего из-за необработанного исключения (см.
  дефект (б)) — это ключевая причина, по которой сбой (документируемый
  здесь) и честный «на месте нет животных» визуально сливаются в одно и то
  же. Отдельный `READ_OK`-сценарий для этого случая на сегодня не написан
  (нет use-case файла для `EVT-66`/`READ_OK`), поэтому не цитируется здесь по
  id — фиксируется только сам факт визуальной идентичности.
- **Сравнение с `AnimalWeighingsCubit.load`
  ([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)).** Там при
  аналогичном отсутствии `try/catch` первая строка метода —
  `emit(const AnimalWeighingsState.loading())`, отдельный вариант
  freezed-union, который UI гарантированно отображает как спиннер; сбой
  замораживает состояние на этом явном «loading»-варианте — пользователь
  видит вечный спиннер, качественно отличимый (хоть и без сообщения об
  ошибке) от «здесь пусто». Здесь же состояние не различает
  loading/loaded/error как варианты union — это один и тот же класс,
  `isLoading` внутри него никогда не становится `true` — и сбой замораживает
  состояние на форме, тождественной пустому успеху, а не на спиннере.
  Качественно иной (и менее заметный) режим отказа, не просто «то же самое,
  но чуть хуже».
- **Сравнение с `UnsentInventoriesCubit.load`
  ([UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md), сосед той
  же под-области `INV`, тот же [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).**
  Там метод целиком (кроме первого `emit(loading())`) обёрнут в один
  `try/catch`, состояние — freezed-union с явным вариантом `error(String
  message)`, и пользователь гарантированно видит `ProgressMessage.somethingWentWrong`.
  Здесь — ни того, ни другого: качественное, а не количественное отличие в
  надёжности между двумя read-экранами одной и той же под-области, тот же
  вывод, который уже сделан в противоположную сторону в
  [UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md).

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals` + `ReportAnimals`) — целевая
  сущность чтения: при сбое ни одна строка (черновая или уже подтверждённая
  сервером) не попадает в UI, независимо от того, сколько их реально есть в
  БД по этой сессии/дате.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `AnimalsRepository.getAllAnimalsWithDetailsByFilters()` (без фильтров —
  все животные) и сопоставляется с найденными отчётами по
  `animalIdentificationNumbers`; не изменяется этим сценарием; сам может
  быть источником исключения (см. «Альтернативные потоки»), включая
  внутренний null-check `e.kind!`.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается целиком через
  `AnimalIdentificationsRepository.getAll()` (унаследован от
  `BaseRepository<Dao, D, T>.getAll`), используется, чтобы отличить
  известные номера (`otherAnimals` — метки без совпадающей идентификации);
  не изменяется этим сценарием; тоже потенциальный источник исключения.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — читается через
  `FarmRepository.getById(_farmId ?? reports.first.farmId)`; используется,
  чтобы отфильтровать животных чужой фермы и подписать заголовок отчёта; не
  изменяется этим сценарием.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается
  через `PlaceRepository.getById(_placeId ?? reports.first.placeId)`,
  аналогично; не изменяется этим сценарием.

### Бизнес-правила

- Технический сбой (исключение из любого из шести чтений либо из внутреннего
  `e.kind!`) классифицируется как `READ_ERROR`, а не `READ_REJECTED` — в
  методе нет ни одной сознательно отклоняющей ветки бизнес-логики (в отличие,
  например, от `readyToSend`-условий в `ScanningBloc`, см.
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)); единственный
  путь к нештатному исходу — непойманное техническое исключение, та же
  классификация, что уже принята для соседнего сценария той же под-области
  ([UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md)).
- **НАХОДКА — полное отсутствие обработки исключений.** Ни один из шести
  вызовов репозиториев (плюс внутренний null-check) не защищён `try/catch`;
  метод рассчитан целиком на «happy path». Ни разу не логируется через
  `Talker` или любой другой механизм — единственный вызов `Talker` в методе
  информационный и относится к успешному пути.
- **НАХОДКА — `isLoading` не используется по назначению.** Поле объявлено,
  читается в двух местах UI (`_buildBody`, кнопка экспорта), но ни разу не
  устанавливается в `true` ни в одном из трёх `emit` метода — ветка спиннера
  `_buildBody` физически недостижима при работе через этот кубит. Из-за
  этого пользователь не видит индикации загрузки вообще ни в штатном, ни в
  отказном сценарии — оба выглядят как мгновенно (или после произвольной
  задержки) отрисованный отчёт.
- **Комбинация (а)+(б) — сбой неотличим от честного пустого отчёта.**
  Поскольку замороженное при сбое состояние (шаг 8) и намеренно эмитируемое
  состояние `reports.isEmpty` (см. «Альтернативные потоки») — буквально одна
  и та же форма (`InventoryReportDetailsState(date: state.date)`, все поля по
  умолчанию), UI не может — и не пытается — различить «здесь действительно
  нет животных» от «загрузка не завершилась». Это отличает данный сценарий
  от [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md) (там хотя
  бы виден вечный спиннер, качественно отличимый от «загружено, пусто»).
- Нет никакого retry-механизма на самом экране (ни `RefreshIndicator`, ни
  кнопки повтора) — единственный способ повторить попытку — уйти со страницы
  и открыть отчёт заново (новый `InventoryReportDetailsCubit`, новый вызов
  `load()`), причём пользователь не получает никакого сигнала, что стоило бы
  это сделать.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба дефекта (отсутствие `try/catch` и мёртвое поле `isLoading`)
прослеживаются по существующему коду полностью, статическим чтением
`InventoryReportDetailsCubit.load`, `InventoryReportDetailsState` и
`InventoryReportDetailsView._buildBody`, без пробелов, требующих уточнения у
пользователя. Единственная содержательная неопределённость (реальное
наблюдаемое поведение необработанного отклонения `Future` в запущенном
приложении, а не только по семантике Dart Zones) зафиксирована в «Открытые
вопросы и ограничения», не как пробел документации — тот же класс
ограничения, что уже отмечен в [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/scanning/scanning_page.dart` | `_ScanningPageState.build` (`BlocConsumer.listener`, ветка `ScanningExit`) | CURRENT | точка входа (а) — переход на `Routes.inventoryReport` сразу после завершения сессии сканирования |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `_navigateItem` (ветка `InventoryDayItem`) | CURRENT | точка входа (б) — переход на `Routes.inventoryReport` из календаря отчётов |
| `lib/pages/routes.dart` | `Routes.inventoryReport` | CURRENT | константа имени/пути маршрута |
| `lib/pages/animals_inventory/presentation/inventory_report__details_page.dart` | `InventoryReportDetailsPage.build`, `InventoryReportPageArgs` | CURRENT | тонкая обёртка-страница + модель аргументов |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView.build` | CURRENT | `create: (context) => InventoryReportDetailsCubit(...)..load()`, каскад без `await`/`.catchError` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView._buildBody` | CURRENT | `if (state.isLoading) return CircularProgressIndicator()` — недостижимая ветка (дефект (б)) |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView._computeSections` | CURRENT | строит 4 секции из `state`; над пустым состоянием (сбой либо честный пустой отчёт) возвращает 4 пустых списка |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | предмет сценария — ни одного `try`/`catch` вокруг шести обращений к репозиториям |
| `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart` | `InventoryReportDetailsState` | CURRENT | обычный (не freezed-union) класс; `isLoading` — `@Default(false)`, нигде не устанавливается в `true`; физически не имеет варианта `error` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getInventoryReportsByDate`, `.getInventoryReportsByUuid` | CURRENT | чтение кэша подтверждённых сервером отчётов, без собственного `try/catch` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReportsByDate`, `.getInventoryReportsByUuid` | CURRENT | чтение черновика/готовой к отправке сессии, без собственного `try/catch` |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository.getAll` (унаследован от `BaseRepository.getAll`) | CURRENT | резолвит известные номера меток |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | читает все животные для группировки по виду/месту |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | резолвит ферму отчёта |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById` | CURRENT | резолвит место отчёта |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.kind` (`Kind?`) | CURRENT | допускающее `null` поле; `e.kind!` в `load()` — восьмая, не-репозиторная незащищённая точка отказа |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` вызывается напрямую; `runTalkerZonedGuarded(...)` закомментирован целиком — необработанное отклонение `Future` не попадает ни в один явный error-handler приложения |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | контрастный сосед той же под-области (`INV`, [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md), [UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md)) — единый `try/catch` + явный вариант `error` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.load` | CURRENT | контрастный сосед другой под-области ([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)) — тоже без `try/catch`, но первая строка эмитит явный `loading()`, поэтому сбой хотя бы виден как вечный спиннер |

## Критерии приёмки

- Если любой из шести вызовов (`ReportAnimalsRepository.getInventoryReportsByDate`/`.getInventoryReportsByUuid`,
  `UnsentReportAnimalsRepository.getInventoryReportsByDate`/`.getInventoryReportsByUuid`,
  `AnimalIdentificationsRepository.getAll`,
  `AnimalsRepository.getAllAnimalsWithDetailsByFilters`,
  `FarmRepository.getById`, `PlaceRepository.getById`), либо внутренний
  `e.kind!`, бросает исключение внутри `InventoryReportDetailsCubit.load()`,
  метод не перехватывает его — возвращаемый `Future<void>` отклоняется тем же
  исключением (`throwsA(...)`, а не `completes`).
- Ни один вызов `getIt<Talker>()` (или любого другого логгера) с сообщением
  об ошибке не происходит на этом пути — единственный вызов `Talker` в
  методе относится к успешному пути и не достигается при сбое на шаге 5.
- Ни при каком исключении внутри `load()` поле `isLoading` итогового
  состояния кубита не равно `true` — оно тождественно `false` на всём
  протяжении жизни кубита, что подтверждается отсутствием единого
  присваивания `isLoading: true` во всём файле `inventory_report_details_cubit.dart`.
- После сбоя `cubit.state` идентично по форме (`myAnimalsByKind`/`otherAnimals`/`allAnimals`
  пусты, `farm`/`place == null`, `isLoading == false`) состоянию, эмитируемому
  намеренно для честного пустого отчёта (`reports.isEmpty`) — визуально
  неразличимы.
- `InventoryReportDetailsView` при таком сбое не показывает ни
  `CircularProgressIndicator`, ни какого-либо сообщения об ошибке — тело
  рендерится через `_computeSections` с четырьмя пустыми секциями, кнопка
  экспорта в `AppBar` не отображается.
- На экране нет `RefreshIndicator` и нет кнопки повтора — единственный способ
  повторить попытку — покинуть экран (кнопка «назад») и открыть отчёт заново.

## Связанные тесты

`test/pages/inventory_report_details_cubit_test.dart` содержит две группы —
`group('UC-131 — InventoryReportDetailsCubit.load (по дате)', ...)` (4 теста)
и `group('UC-131 — InventoryReportDetailsCubit.load (по sessionUuid)', ...)`
(1 тест) (старая нумерация, переименуется отдельным контролируемым проходом —
не трогать сейчас). Все пять тестов настраивают моки только через
`thenAnswer` (успешные ответы) и проверяют исключительно `READ_OK`-исходы
(пустой список; группировка по виду/`otherAnimals`; фильтр `placeId`;
исключение животных чужой фермы; объединение unsent+sent по `sessionUuid`) —
**ни один тест файла не настраивает `thenThrow` ни для одного из шести
моков** (`reportAnimalsRepository`, `unsentReportAnimalsRepository`,
`animalsRepository`, `identificationsRepository`, `farmRepository`,
`placeRepository`), и ни один не проверяет `isLoading`.

**TBD — теста нет** на исключение, брошенное любым из шести репозиториев
внутри `InventoryReportDetailsCubit.load()` — этот сценарий (`READ_ERROR`) не
покрыт ни одним существующим тестом.

**TBD — теста нет** на то, что `isLoading` никогда не становится `true` —
вывод сделан статическим чтением кода (отсутствие присваивания), не
подтверждён явной проверкой в тесте.

**TBD — теста нет** на widget-уровне (`InventoryReportDetailsView`/`InventoryReportDetailsPage`)
— в `test/` нет ни одного widget-теста для этой страницы; вывод о рендере
пустых секций без спиннера и без сообщения об ошибке сделан по чтению кода,
не по запуску виджета.

## Открытые вопросы и ограничения

- **Реальное поведение необработанного отклонения `Future` в запущенном
  приложении не проверено ни одним widget/integration-тестом.** Вывод о том,
  что экран не падает, а молча дорисовывается пустым, сделан по чтению кода
  (`BlocProvider.create` — синхронный колбэк, каскад возвращает кубит, а не
  `Future`; `lib/main.dart` не использует `runZonedGuarded`) и по семантике
  Dart Zones для fire-and-forget `Future`, а не по факту запуска реального
  приложения — тот же класс ограничения, что уже зафиксирован в
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md).
- **Почему `InventoryReportDetailsCubit.load` (INV, этот файл) не получил ни
  `try/catch`, ни варианта ошибки состояния, а его непосредственный сосед
  той же под-области — `UnsentInventoriesCubit.load` ([EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md),
  [UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md)) — получил
  оба?** Тот же открытый вопрос, что уже поднят в
  [UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md) с обратной
  стороны; ничего в коде/комментариях не объясняет асимметрию как осознанное
  решение (например, «хаб важнее итогового отчёта») в противовес случайному
  результату независимой разработки двух похожих экранов.
- **Стоит ли добавлять `InventoryReportDetailsState` вариант ошибки/явный
  loading-флаг и оборачивать `load()` в `try/catch`, по аналогии с
  `UnsentInventoriesState`/`UnsentInventoriesCubit`?** Не решено этим
  документирующим файлом — вопрос продукту/разработке, если поведение должно
  измениться.
- **Стоит ли визуально различать «на месте действительно нет животных» и
  «загрузка отчёта не завершилась»?** Сейчас это один и тот же экран без
  какого-либо признака различия — нерешённый продуктовый вопрос, не
  зафиксированный нигде в коде/комментариях.
- **Нет автоматического повтора при пересоздании виджета.** В отличие от
  `AnimalWeighingsCubit`/`_AnimalWeighingsBodyState.activate()` (см.
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)),
  `InventoryReportDetailsView` — простой `StatelessWidget` с одним
  `BlocProvider.create`; никакого хука жизненного цикла, который повторно
  вызвал бы `load()` без полного пересоздания страницы, здесь нет.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим
  чтением кода (`InventoryReportDetailsView.build` →
  `InventoryReportDetailsCubit.load` → шесть репозиториев); реальная частота
  и причины сбоя каждого конкретного репозитория этой спекой не
  верифицированы.
