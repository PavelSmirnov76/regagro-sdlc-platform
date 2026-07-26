# UC-113 — Пользователь открывает вкладку «История» карточки животного

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает вкладку «История» карточки животного и видит единую
хронологическую ленту, собранную из пяти независимых источников (выбытие,
перемещение, взвешивание, вакцинация, факт регистрации) одного животного —
без фильтра лента показывает только самое свежее событие каждого типа; выбрав
фильтр по типу, пользователь видит все элементы этого типа целиком.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, разницы для этого сценария нет).

## CURRENT

### Основной поток

1. Пользователь находится на `AnimalCardPage`, в панели действий
   (`_AnimalCardToolbarActions`) нажимает кнопку «История» →
   `context.pushNamed2(Routes.animalHistory, extra:
   AnimalHistoryPageArgs(animal: animalWithDetails))`.
2. `Routes.animalHistory` вложен под `Routes.animalDetails` (который вложен
   под `Routes.animalsRegistry`) в дереве маршрутов `routes.dart`;
   `AnimalHistoryPage.build` читает аргумент через
   `GoRouterState.of(context).getExtraByName<AnimalHistoryPageArgs>` и
   создаёт `BlocProvider(create: (context) =>
   AnimalHistoryCubit()..load(args.animal.animalId))`.
3. `AnimalHistoryCubit.load(animalId)` эмитит `AnimalHistoryState.loading()`,
   затем читает животное — `_animalsRepo.getAnimalWithDetailsById(animalId)`;
   если `null` — эмитится `AnimalHistoryState.error('Animal not found')`
   (другой `RESULT`, не этот файл).
4. Из `animal.activeAnimalIdentifications` извлекается номер активного
   транспондера — первая идентификация с `markerTypeId ==
   Constants.TransponderMarkerTypeId` (значение `3`), если такая есть.
5. Пять источников читаются последовательно и независимо, каждый
   собирается в свой (максимум один) `ReportDayGroup`, пустой источник
   группы не добавляет:
   - `_buildDisposalGroups`: `_disposalRepo.getAllByAnimalId(animalId)` —
     все выбытия этого животного без фильтра по `sync`/`deletedAt`; причины
     довыгружаются одним запросом `_disposalReasonsRepo.getAllByFilters(ids:
     <уникальные causeId>)`, `reasonName` — из справочника или `'-'`, если
     `causeId == null` или причина не найдена; дата элемента — `d.date ??
     d.createdAt ?? DateTime.now()`.
   - `_buildMovementGroups`: `_movementRepo.getMovementsWithDetailsByFilters(
     animalIds: [animalId])` — вызов **не указывает** именованный параметр
     `sync`, поэтому подставляется дефолт репозитория `bool? sync = true`
     (`MovementReportRepository.getMovementsWithDetailsByFilters`), который
     репозиторий прокидывает в DAO как `sync: true`; `MovementDao` при
     непустом `sync` добавляет `query.where(mAlias.sync.equals(sync))` — т.е.
     **читаются только уже синхронизированные с сервером перемещения**, а не
     «все источники без разбора по sync-статусу» (см. «Бизнес-правила» и
     «Открытые вопросы» — это отличает Movement от остальных четырёх
     источников этого сценария). Дата элемента — `m.movement.placeDate ??
     m.movement.createdAt ?? DateTime.now()`.
   - `_buildWeighingGroups`:
     `_weighingsRepo.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(
     [animalId])` — все взвешивания животного без фильтра по `sync`; список
     пересортировывается по убыванию даты, затем среднесуточный привес
     (`avgDailyGain`) считается по разнице веса и разнице дней с
     хронологически предыдущим (более ранним) взвешиванием — `null`, если
     нет предыдущего или разница дат `<= 0` дней (тот же день).
   - `_buildVaccinationGroups`: `_vaccinationsRepo.getVaccinationsWithDetails()`
     — вызов без аргументов, `VaccinationsDao.getVaccinationsWithDetails`
     тянет **все вакцинации всех животных** (фильтр по `ids` — `Constant(true)`,
     когда `ids == null`), без фильтра по `sync`/`deletedAt`; кубит
     фильтрует результат в памяти по `v.animal.animalId == animalId`.
     `diseasesLabel` строится через
     `ReportsDayQuery.vaccinationDiseasesLabel` (имена болезней через
     запятую или `'-'`, если пусто и нет `complexVaccine`).
   - `_buildRegistrationGroups(animal.createdAt, transponder)`: не читает
     репозиторий — синхронно строит один элемент из уже загруженного
     `animal.createdAt` (если `null` — группа не добавляется) и найденного
     на шаге 4 номера транспондера.
6. Пять списков групп конкатенируются в `_allGroups` (порядок в списке —
   выбытие, перемещение, взвешивание, вакцинация, регистрация — но это не
   финальный порядок отображения, см. шаг 7).
7. Эмитится `AnimalHistoryState.loaded(groups: _applyFilter(_allGroups,
   null), selectedFilter: null)`. `_applyFilter` с `filter == null`: для
   каждой непустой группы берётся **только первый элемент** её списка
   `items` (группы уже отсортированы по убыванию даты внутри
   `_buildXxxGroups`, поэтому «первый» — самый свежий), `count`
   принудительно выставляется в `1`; получившиеся однонаборные группы
   сортируются между собой по убыванию даты их (единственного) элемента.
8. `AnimalHistoryPage` перерисовывается через `BlocBuilder`; при `loaded`
   рендерится `_AnimalHistoryBody` — горизонтальный ряд chip-фильтров
   (`null`/взвешивание/вакцинация/выбытие/перемещение/регистрация,
   `null` подписан как «все последние») и вертикальный список
   `ReportGroupSection` (`readOnly: true`) на каждую группу; пустой список
   групп рендерит `l10n.no_data`.

### Альтернативные потоки

- **Выбор фильтра по типу.** Пользователь нажимает chip конкретного типа →
  `AnimalHistoryCubit.setFilter(type)`; работает только если текущее
  состояние уже `AnimalHistoryLoaded` (иначе no-op) — пересчитывает из уже
  загруженного `_allGroups` (без повторного похода в репозитории):
  оставляет только группы с `reportType == filter`, внутри каждой
  пересортировывает **все** элементы по убыванию даты (не переиспользует
  порядок, в котором элементы были собраны на шаге 5 — пересортировка с
  нуля через собственный компаратор `_itemDate`), `count` = длина полного
  списка элементов этого типа.
- **Возврат к `filter: null`.** Пользователь нажимает chip «все последние» →
  `setFilter(null)` — снова схлопывает каждую группу до одного (самого
  свежего) элемента, как на шаге 7 основного потока.
- **Ошибка любого из пяти источников.** Исключение в любом из
  `_buildDisposalGroups`/`_buildMovementGroups`/`_buildWeighingGroups`/
  `_buildVaccinationGroups`/`getAnimalWithDetailsById` перехватывается общим
  `try/catch` вокруг всего `load()` — эмитится `AnimalHistoryState.error`
  целиком, без частичного результата от уже успешно прочитанных источников
  (другой `RESULT`, не этот файл).
- **Пустая история по всем источникам.** Если ни один из пяти источников не
  вернул данных (в т.ч. `animal.createdAt == null`) — `loaded` эмитится с
  пустым списком групп, UI показывает `l10n.no_data`; это тот же `RESULT`
  (`READ_OK`), просто без контента.
- **Животное выбыло (`deletedAt != null`).** `AnimalHistoryPage.build`
  вычисляет `isDisposed` из `args.animal.animal.deletedAt`; если `true` —
  после первого кадра (`addPostFrameCallback`) скрывает FAB через
  `context.read<FabVisibilityCubit>().hide()`. Это не меняет состав/загрузку
  истории — тот же `load()`, тот же основной поток.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — карточка
  которого читается вначале (`getAnimalWithDetailsById`), источник
  `createdAt` для группы регистрации и `activeAnimalIdentifications` для
  номера транспондера; передаётся аргументом страницы, не перечитывается по
  ссылке остальными источниками (только их собственные `animalId`-фильтры).
- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — источник
  группы «выбытие»; вместе с ним читается справочник причин выбытия
  (`DisposalReason`, HANDBOOKS) — не отдельная перечисляемая здесь ENT-сущность
  модуля ANIMAL, но факт зависимости важен для понимания потока.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — источник
  группы «перемещение»; читаются только строки с `sync == true` (см.
  основной поток, шаг 5) — единственный из пяти источников с таким жёстким
  фильтром.
- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing)
  — источник группы «взвешивание», без фильтра по `sync`.
- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  источник группы «вакцинация»; читается запросом без фильтра по
  `animalId`/`sync` на уровне БД — вся таблица тянется и фильтруется в
  памяти кубита.

### Бизнес-правила

- **Без фильтра — по одному элементу на тип, сортировка групп по свежести.**
  `filter == null` — каждая непустая группа схлопывается до её самого
  свежего элемента (`items.first`, при условии что список уже
  отсортирован по убыванию даты каждым `_buildXxxGroups`), сами группы
  сортируются между собой по убыванию даты этого единственного элемента.
- **С фильтром — все элементы типа, пересортированные заново.** Выбор
  конкретного `CalendarReportType` показывает полный список элементов этого
  типа, отсортированный по убыванию даты **заново** в `_applyFilter`
  (`_itemDate`-компаратор), не переиспользуя порядок сборки из шага 5.
- **Каждый источник читается независимо, без единого запроса/транзакции.**
  Пять последовательных `await` к пяти разным репозиториям; ошибка
  любого — фатальна для всего экрана (см. «Альтернативные потоки»).
- **Movement — единственный источник с жёстким `sync`-фильтром по
  умолчанию.** Из-за того, что `AnimalHistoryCubit` не передаёт `sync` явно
  в `getMovementsWithDetailsByFilters`, подставляется дефолт репозитория
  (`sync: true`) — локально созданные, ещё не отправленные на сервер
  перемещения этого животного **не попадают** в ленту истории. Disposal,
  AnimalWeighing и Vaccination такого фильтра не имеют — читаются
  независимо от `sync`-статуса.
- **Vaccination — единственный источник без фильтра по `animalId` на уровне
  запроса.** `getVaccinationsWithDetails()` возвращает вакцинации всех
  животных приложения; фильтрация по нужному `animalId` — целиком в памяти
  кубита (`all.where((v) => v.animal.animalId == animalId)`).
- **Регистрация — единственная «группа» без обращения к репозиторию.**
  Строится синхронно из уже загруженного `animal.createdAt` и найденного на
  шаге 4 транспондера; при `createdAt == null` группа не добавляется
  вовсе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_AnimalCardToolbarActions.build` | CURRENT | точка входа — кнопка «История» в панели действий карточки животного |
| `lib/pages/routes.dart` | `Routes.animalHistory` | CURRENT | маршрут вкладки, вложен под `Routes.animalDetails` |
| `lib/pages/animal_history/presentation/animal_history_page.dart` | `AnimalHistoryPage.build` | CURRENT | читает `AnimalHistoryPageArgs`, создаёт кубит и вызывает `load()` |
| `lib/pages/animal_history/presentation/animal_history_page.dart` | `_AnimalHistoryViewState.initState` | CURRENT | при `isDisposed == true` скрывает FAB после первого кадра |
| `lib/pages/animal_history/presentation/animal_history_page.dart` | `_AnimalHistoryBody.build` | CURRENT | ряд chip-фильтров + список `ReportGroupSection`, пустой список → `l10n.no_data` |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit.load` | CURRENT | основной метод сценария — читает животное и все пять источников, эмитит `loaded`/`error` |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit.setFilter` | CURRENT | переключение фильтра над уже загруженными данными, без повторного запроса |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._applyFilter` | CURRENT | схлопывание до 1 элемента (`filter == null`) либо полный список с пересортировкой (`filter != null`) |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._buildDisposalGroups` | CURRENT | источник группы «выбытие» + справочник причин |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._buildMovementGroups` | CURRENT | источник группы «перемещение», неявный `sync: true` |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._buildWeighingGroups` | CURRENT | источник группы «взвешивание» + расчёт `avgDailyGain` |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._buildVaccinationGroups` | CURRENT | источник группы «вакцинация», фильтр по `animalId` в памяти |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit._buildRegistrationGroups` | CURRENT | синхронная группа «регистрация» из уже загруженного `Animal.createdAt` |
| `lib/pages/animal_history/cubit/animal_history_state.dart` | `AnimalHistoryState` (`initial`/`loading`/`loaded`/`error`) | CURRENT | freezed-состояние экрана |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | читает животное, чью историю смотрит пользователь |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getAllByAnimalId` | CURRENT | тонкая обёртка над DAO, без фильтра по `sync` |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getAllByFilters` | CURRENT | справочник причин выбытия по списку `causeId` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | `bool? sync = true` по умолчанию — кубит не переопределяет |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | без фильтра по `sync` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | тонкая обёртка над DAO, без параметра `animalId` |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementDao.getAllMovementsWithDetailsByFilters` | CURRENT | `if (sync != null) query.where(mAlias.sync.equals(sync))` — источник неявного `sync == true` фильтра |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalDao.getAllByAnimalId` | CURRENT | `select(disposals)..where(animalId.equals(...))`, без фильтра `sync`/`deletedAt` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | `selectCurrent()..where(animalId.isIn(...))`, без фильтра `sync` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetails` | CURRENT | `ids == null` → `Constant(true)` — читает все вакцинации всех животных |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetailsExtension.activeAnimalIdentifications` | CURRENT | источник номера транспондера для группы регистрации |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId` | CURRENT | `markerTypeId` транспондера (`3`), используется для поиска активной идентификации |
| `lib/pages/reports_day_list/data/report_day_group.dart` | `ReportDayGroup`, `ReportDayItem` (и подклассы `MovementDayItem`/`DisposalDayItem`/`AnimalWeighingHistoryItem`/`VaccinationDayItem`/`AnimalRegistrationHistoryItem`) | CURRENT | общая модель группы/элемента, переиспользуемая из модуля отчётов-календаря |
| `lib/pages/reports_calendar/data/calendar_report_type.dart` | `CalendarReportType`, `.labelKey` | CURRENT | тип фильтра/группы, ключ локализации заголовка |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.vaccinationDiseasesLabel` | CURRENT | строка названий болезней вакцинации, переиспользуемая из модуля отчётов-календаря |
| `lib/pages/reports_day_list/presentation/widgets/report_group_section.dart` | `ReportGroupSection.build` | CURRENT | рендер одной группы списком, `readOnly: true` на этом экране |

## Критерии приёмки

- Открытие вкладки «История» вызывает `AnimalHistoryCubit.load(animalId)`
  ровно один раз, читает животное и все пять источников (выбытие,
  перемещение, взвешивание, вакцинация, регистрация) независимо друг от
  друга.
- При `filter == null` (первичная загрузка) каждая непустая группа
  показывает ровно один — самый свежий — элемент; группы отсортированы
  между собой по убыванию даты этого элемента.
- Выбор фильтра конкретного типа (`setFilter`) показывает все элементы этого
  типа, отсортированные по убыванию даты, без повторного похода в
  репозиторий.
- Возврат к `setFilter(null)` вновь схлопывает все группы до одного
  элемента каждая.
- Группа «перемещение» не включает локально созданные, ещё не
  синхронизированные перемещения этого животного (неявный `sync: true`).
- Группа «вакцинация» включает вакцинации независимо от `sync`-статуса, но
  только принадлежащие запрошенному `animalId` (фильтруется в памяти, не в
  запросе).
- Ошибка любого из пяти источников приводит к `AnimalHistoryState.error`
  целиком — частичный результат от уже успешно прочитанных источников не
  показывается.
- Пустая история по всем пяти источникам — `loaded` с пустым списком групп,
  UI показывает состояние «нет данных», не ошибку.

## Связанные тесты

`test/pages/animal_history_cubit_test.dart`:

- `group('AnimalHistoryCubit.load')` — животное не найдено → error; пустая
  история по всем источникам → `loaded` с пустым списком групп; `createdAt`
  задан → добавляется группа регистрации; вакцинация другого животного не
  попадает в группы; вакцинация этого животного → группа с 1 элементом;
  ошибка любого источника (диспоузы, вакцинации) → `error` целиком, без
  частичного результата.
- `group('AnimalHistoryCubit.load — все источники вместе')` — группы от всех
  5 источников сортируются вместе по последней дате при `filter == null`,
  каждая схлопнута до 1 элемента.
- Смежные, но отдельные test group в том же файле (без `UC-113` в
  названии — механическая привязка `grep -r "UC-113" test/` их не находит):
  `group('AnimalHistoryCubit.load — выбытия (disposal)')`,
  `group('AnimalHistoryCubit.load — перемещения (movement)')`,
  `group('AnimalHistoryCubit.load — взвешивания (weighing)')`,
  `group('AnimalHistoryCubit.load — вакцинации (доп.)')`,
  `group('AnimalHistoryCubit.load — транспондер в группе регистрации')`,
  `group('AnimalHistoryCubit.setFilter')` — покрывают детали
  «Альтернативных потоков» и «Бизнес-правил» этого файла (сортировку внутри
  группы, расчёт `avgDailyGain`, `reasonName`/`causeId` по умолчанию,
  `diseasesLabel`, поведение `setFilter` со значением/без).

Ни один из перечисленных test group не именован по конвенции `UC-{id}` —
переименование в `UC-113 — …` не входит в этот документирующий проход (см.
«Открытые вопросы»).

## Открытые вопросы и ограничения

- **Тесты не привязаны механическим анкером `UC-113`.** Все group в
  `test/pages/animal_history_cubit_test.dart` названы описательно
  (`'AnimalHistoryCubit.load'`, `'AnimalHistoryCubit.load — все источники
  вместе'` и т.д.), без `UC-{id}` в имени — `grep -r "UC-113" test/` ничего
  не находит; привязка в разделе «Связанные тесты» выше сделана по факту
  прочтения кода теста, не механически. Переименование — отдельный проход,
  не в рамках этого файла.
- **Movement — единственный источник с неявным `sync: true`, не
  задокументированный на уровне вызова.** `AnimalHistoryCubit._buildMovementGroups`
  не указывает `sync` явно; поведение («только синхронизированные
  перемещения») целиком зависит от значения по умолчанию в сигнатуре
  `MovementReportRepository.getMovementsWithDetailsByFilters` — при её
  изменении лента истории молча поменяет состав данных без единой строчки
  кода в самом кубите. Не поднятый в коде и, вероятно, не осознанный
  разработчиком нюанс: локально созданное (ещё не отправленное)
  перемещение животного не появится в его собственной вкладке «История»,
  хотя появится в других экранах, читающих Movement без `sync`-фильтра.
- **Vaccination читается без ограничения по животному на уровне БД.**
  `getVaccinationsWithDetails()` тянет и строит `VaccinationWithDetails`
  (включая повторный `getAnimalWithDetailsById` и запрос болезней на
  каждую строку) для **всех** вакцинаций всех животных приложения, только
  чтобы затем отфильтровать один `animalId` в памяти — дороже, чем
  `getVaccinationsWithDetailsByAnimalId`, которым пользуется соседний
  сценарий вкладки вакцинаций ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)
  + [EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md)),
  и без фильтра `sync` — включает вакцинации, ещё не подтверждённые
  сервером, в отличие от вкладки вакцинаций той же карточки животного,
  где `sync: true` — жёсткий фильтр. Расхождение в поведении между двумя
  экранами одной карточки не описано пользователю нигде в UI.
- **Внутригрупповая сортировка перед схлопыванием предполагает уже
  отсортированный список.** `_applyFilter` при `filter == null` берёт
  `items.first` без собственной пересортировки — корректность зависит от
  того, что каждый `_buildXxxGroups` уже отсортировал свой список по
  убыванию даты перед возвратом; сам `_applyFilter` это не перепроверяет.
