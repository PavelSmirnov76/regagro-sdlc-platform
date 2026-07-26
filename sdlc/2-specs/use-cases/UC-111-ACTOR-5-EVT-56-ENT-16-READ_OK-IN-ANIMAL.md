# UC-111 — Пользователь открывает посуточный отчёт по выбытию для места/причины/дня

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-56](../events/EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает `DisposalReportPage` для конкретных
места/причины/минуты дня — либо тапом по элементу выбытия в посуточном
списке отчётов (`reports_day_list`), либо тапом по карточке события в хабе
«неотправленных» (`UnsentDisposalsPopulated`) — чтобы увидеть, сколько и
каких животных выбыло по этой причине, в этом месте, в это же время (с
точностью до минуты), с разбивкой по возрастной группе/виду.
`DisposalReportCubit.load` успешно завершается (нет исключения).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/disposal_report/cubit/disposal_report_cubit.dart` целиком:
`DisposalReportCubit` не импортирует и не использует `AuthRepository` ни в
одном методе, включая `load` — доступ к отчёту не зависит от статуса
авторизации.

## CURRENT

### Основной поток

1. Точка входа — один из двух независимо написанных путей, оба строят
   `DisposalReportPageArgs` и переходят на `Routes.disposalReport`:
   - **Из общего календаря отчётов**: `ReportsDayListPopulated._navigateItem`
     (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`),
     ветка `case DisposalDayItem(:final date, :final causeId, :final placeId,
     :final placeName, :final reasonName)` →
     `context.pushNamed2(Routes.disposalReport, extra:
     DisposalReportPageArgs(date: date, causeId: causeId, placeId: placeId,
     placeName: placeName, reasonName: reasonName))` — **без** `isUnsent`
     (значение по умолчанию `false`). `DisposalDayItem` строится
     `ReportsDayQuery.buildDisposalItems`
     (`lib/pages/reports_day_list/data/reports_day_query.dart`) —
     `reasonName` там всегда непустая строка (`data.disposalReasonsById[causeId]
     ?? '-'`, никогда `null` в этом пути), `placeId` — `placeId ??
     e.value.placeId`, где внешний `placeId` передан вызывающим кодом.
   - **Из хаба «неотправленных»**: `_DisposalEventCard.onTap` внутри
     `UnsentDisposalsPopulated.build`
     (`lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart`) →
     `context.pushNamed2(Routes.disposalReport, extra:
     DisposalReportPageArgs(date: event.date, causeId: event.causeId,
     placeId: event.placeId, reasonName: event.reasonName, placeName:
     event.placeName, isUnsent: true))`. Карточки хаба сгруппированы
     `UnsentDisposalsPopulated._groupByEvent` ключом
     `'${causeId}_${placeId}_${DateFormat('HHmm').format(date)}'` (минутная
     точность); `reasonName`/`placeName` здесь берутся напрямую из джойна
     (`d.reason?.name`/`d.place?.name`) и могут быть `null`, если у
     соответствующей `Disposal`-записи нет причины/места в справочнике.
2. `DisposalReportPage.build`
   (`lib/pages/disposal_report/presentation/disposal_report_page.dart`) читает
   `DisposalReportPageArgs` через
   `GoRouterState.of(context).getExtraByName<DisposalReportPageArgs>(Routes.disposalReport)`
   и создаёт `BlocProvider(create: (context) =>
   DisposalReportCubit()..load(args))` — `load` вызывается ровно один раз,
   синхронно со сборкой страницы.
3. `DisposalReportCubit.load` сразу эмитит `DisposalReportState.loading()`,
   затем входит в `try`.
4. `day = DateUtils.dateOnly(args.date)`; `timeKey =
   DateFormat('HHmm').format(args.date)` — минутная точность времени.
5. `all = await _disposalRepo.getDisposalsWithDetailsByFilters(sync:
   args.isUnsent ? false : null, causeId: args.causeId, placeId:
   args.placeId)`. В отличие от `deleteEvent`
   ([UC-103](UC-103-ACTOR-5-EVT-52-ENT-16-DELETE_OK-IN-ANIMAL.md)), `load`
   передаёт `placeId` прямо в SQL-запрос, а не фильтрует по месту в памяти.
   - Если `args.isUnsent == true` (путь из хаба) — `sync: false`: только ещё
     не отправленные записи. Проверено тестом.
   - Если `args.isUnsent == false` (путь из календаря, значение по
     умолчанию) — `sync: null`: фильтр по `sync` в `DisposalsDao`
     (`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` →
     `getAllDisposalsWithDetailsByFilters`) вообще не применяется — попадают
     и ещё не отправленные, и уже синхронизированные записи. Проверено
     отдельным тестом (`verify` с `sync: null`).
   `getAllDisposalsWithDetailsByFilters` выполняет join с `Place`/
   `DisposalReason`, затем отдельно подтягивает животных
   (`db.animalsDao.getAllAnimalsWithDetailsByFilters(ids: ...,
   isNotDeleted: null)`) — без фильтра по `deletedAt`, то есть уже
   помеченные удалёнными животные (после серверной перезагрузки) в джойн
   всё равно попадают, если физически ещё не удалены из локальной таблицы
   `Animals`.
6. `matching = all.where((d) { ... })` — в памяти, по каждой записи `d`:
   `date = d.disposal.date ?? d.disposal.createdAt`; если `date == null` —
   запись исключается; иначе запись входит в `matching`, если одновременно
   `DateUtils.dateOnly(date).isAtSameMomentAs(day)` **и**
   `DateFormat('HHmm').format(date) == timeKey`. Место (`placeId`) и причина
   (`causeId`) уже отфильтрованы на уровне SQL-запроса шага 5 — этот фильтр
   в памяти дублирует только день+время.
7. Для каждой записи `d` из `matching`: `groupName = d.animal?.ageGroup?.name
   ?? d.animal?.kind?.name ?? '-'`; `transponder = d.animal?.firstMainNumber
   ?? '-'` (`AnimalWithDetails.firstMainNumber` — номер идентификации с
   `main == true`, иначе `animal.number`, иначе `'-'`); запись
   добавляется в `byGroup[groupName]` (обычный `Map`, `LinkedHashMap` по
   умолчанию в Dart — сохраняет порядок первого появления ключа) как
   `EventReportAnimalEntry(animalId: d.animal?.animalId, number:
   transponder)`.
8. `groups = byGroup.entries.map((e) => DisposalAnimalGroup(kindName: e.key,
   count: e.value.length, animals: e.value)).toList()` — `isExpanded` по
   умолчанию `false`; порядок групп = порядок первого появления `groupName`
   при переборе `matching`, то есть порядок, в котором `all`/`matching`
   вернул SQL-запрос (в `getAllDisposalsWithDetailsByFilters` нет `ORDER
   BY`, порядок строк не гарантирован кодом).
9. Эмитится `DisposalReportState.loaded(date: args.date, reasonName:
   args.reasonName, placeName: args.placeName, totalAnimals:
   matching.length, groups: groups)`. `reasonName`/`placeName` — ровно
   значения из `args`, без обращения к какому-либо справочнику внутри
   `load` самим — они уже разрешены вызывающим экраном (шаг 1).
10. `DisposalReportPage` рендерит `EventReportScaffold` (заголовок
    `l10n.disposal`, подзаголовок — `args.date` в формате `dd.MM.yyyy
    HH:mm`) с действиями (`MoreMenuWidget`, пункт «Удалить») только если
    `args.isUnsent == true` — см. «Альтернативные потоки». Тело —
    `state.when(... loaded: (date, reasonName, placeName, totalAnimals,
    groups) => ...)`: `chips = [если placeName != null — placeName, если
    reasonName != null — '${l10n.disposal_reason}: $reasonName']`;
    `groups` мапятся в `EventReportGroup` (тот же общий шаблон
    `lib/widgets/event_report/event_report_template.dart`, что и у
    вакцинации/движения); рендерится `EventReportBody(chips, totalAnimals,
    groups, onToggleGroup: (index) =>
    context.read<DisposalReportCubit>().toggleGroup(index))`.
11. Тап по группе вызывает `DisposalReportCubit.toggleGroup(index)` —
    переключает `isExpanded` соответствующей группы и переэмитит
    `loaded` с тем же `date`/`reasonName`/`placeName`/`totalAnimals`, только
    с изменённым списком `groups`; при `state` не `DisposalReportLoaded` —
    no-op (метод просто возвращается без `emit`). Отдельный, самостоятельный
    сценарий взаимодействия с уже загруженным отчётом, не предмет этого
    файла (тот же паттерн, что `VaccinationReportCubit.toggleGroup` в
    [UC-81](UC-81-ACTOR-5-EVT-41-ENT-14-READ_OK-IN-ANIMAL.md)).

### Альтернативные потоки

- **Ни одной записи не подошло под фильтр день+время (`matching` пуст).**
  Тот же `RESULT` (`READ_OK` — вызов успешно завершился, просто без
  данных): `loaded` эмитится с `totalAnimals: 0`, `groups: []`;
  `EventReportBody` рендерит `l10n.no_data` вместо списка групп. Не
  отдельный use-case.
- **Путь из общего календаря (`args.isUnsent == false`).** `sync`
  передаётся как `null` в запрос (шаг 5) — попадают и ещё не отправленные,
  и синхронизированные записи; экран не показывает пункт меню «Удалить»
  (`EventReportScaffold.actions == null`), то есть с этого пути отчёт
  полностью read-only.
- **Путь из хаба «неотправленных» (`args.isUnsent == true`).** `sync`
  передаётся как `false` — только ещё не отправленные записи; экран
  показывает пункт меню «Удалить», ведущий к отдельному сценарию
  (`deleteEvent`, [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md),
  документирован в [UC-103](UC-103-ACTOR-5-EVT-52-ENT-16-DELETE_OK-IN-ANIMAL.md)/[UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md)),
  не предмет этого файла.
- **Исключение внутри `try`** (например сбой доступа к локальной БД в
  `getDisposalsWithDetailsByFilters` или при построении групп) —
  перехватывается, эмитится `DisposalReportState.error(e.toString())`.
  Другой `RESULT` (`READ_ERROR`), не предмет этого файла — покрыт соседней
  тестовой группой `'UC-112 — DisposalReportCubit.load'` (старая
  нумерация, см. «Связанные тесты»); отдельный use-case-файл для этого
  исхода на момент написания этого файла ещё не заведён.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) —
  единственная сущность, чьё состояние (в смысле сегмента `ENT` в имени
  этого use-case) здесь читается; сама запись не изменяется. Читается либо
  только ещё не отправленные (`sync: false`, путь из хаба), либо вообще без
  фильтра по `sync` (путь из календаря).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  через `d.animal` (`AnimalWithDetails`) на каждой строке `DisposalWithDetails`;
  `ageGroup`/`kind` — для имени группы, `animalId`/`firstMainNumber` — для
  отображаемой записи животного; подтягивается с `isNotDeleted: null`
  (без исключения уже отмеченных удалёнными животных, если строка ещё
  физически существует локально); не изменяется.
- `DisposalReason` (модуль HANDBOOKS,
  [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md)) — `causeId`
  уже отфильтрован на уровне SQL-запроса (шаг 5); в самом `load`
  используется только для join (поле `reason` результата не читается этим
  методом вовсе — заголовок отчёта берёт `reasonName` напрямую из `args`,
  не из этого join); не изменяется.
- `Place` (модуль FARM, [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)) —
  `placeId` уже отфильтрован на уровне SQL-запроса (шаг 5); аналогично
  `DisposalReason` — join присутствует в `DisposalWithDetails`, но поле
  `place` не читается `load` (заголовок берёт `placeName` из `args`); не
  изменяется.

### Бизнес-правила

- **Фильтр `sync` зависит только от `args.isUnsent`, не от репозиторного
  запроса по умолчанию.** `sync: args.isUnsent ? false : null` — единственное
  место в `load`, где различаются два входных пути; всё остальное
  (day+time+place+cause фильтрация) одинаково для обоих.
- **Место и причина фильтруются на уровне SQL-запроса, день и точное время
  (минута) — только в памяти, после чтения.** Это единственная фильтрация в
  памяти в `load` (в отличие от `deleteEvent`, где в памяти фильтруются ещё
  и место, и день/время — см. [UC-103](UC-103-ACTOR-5-EVT-52-ENT-16-DELETE_OK-IN-ANIMAL.md)).
- **`reasonName`/`placeName` в `loaded`-состоянии — пас-тру строки из
  аргументов навигации, не результат собственного обращения `load` к
  справочникам.** Оба вызывающих экрана (календарь, хаб) уже разрешили эти
  имена по-своему (см. основной поток, шаг 1) до создания `DisposalReportCubit`.
- **`totalAnimals` считает записи выбытия, совпавшие по дню/времени, не
  уникальных животных** — то же допущение, что и у вакцинации/взвешивания
  того же модуля; если бы одно и то же животное выбыло дважды с одинаковыми
  день+минута (на практике маловероятно для реального `Disposal`, так как
  выбытие одного и того же животного второй раз не имеет смысла в домене,
  но код это не проверяет), обе записи вошли бы в счётчик отдельно.
- **Группы не сортируются явно** — порядок = порядок первого появления
  имени группы при переборе `matching`, который наследует порядок,
  возвращённый SQL-запросом без `ORDER BY`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и покрытая тестами альтернативная ветка (`sync: null`
вместо `sync: false`) полностью реализованы и достижимы из UI с обоих
входных путей (календарь и хаб неотправленных).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` (кейс `DisposalDayItem`) | CURRENT | точка входа из общего календаря — строит `DisposalReportPageArgs` без `isUnsent` (по умолчанию `false`) |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildDisposalItems` | CURRENT | строит `DisposalDayItem` (источник `date`/`causeId`/`placeId`/`placeName`/`reasonName` для аргументов экрана из календаря); `reasonName` всегда `data.disposalReasonsById[causeId] ?? '-'` |
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit._buildGroupsByType`, `ReportsDayListCubit._buildGroupsByPlace` | CURRENT | оба вызывающих места `buildDisposalItems` передают конкретный (не `null`) `placeId` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart` | `UnsentDisposalsPopulated._groupByEvent`, `_DisposalEventCard.onTap` | CURRENT | альтернативная точка входа из хаба неотправленных — строит `DisposalReportPageArgs` с `isUnsent: true`; ключ группировки карточки — `causeId_placeId_HHmm` |
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage.build` | CURRENT | точка входа маршрута `Routes.disposalReport`; читает `DisposalReportPageArgs` через `getExtraByName`, создаёт `BlocProvider(..load(args))`, рендерит `state.when` |
| `lib/widgets/go_router/go_router_state.dart` | `GoRouterState.getExtraByName` | CURRENT | извлекает `DisposalReportPageArgs` из `extra` навигации |
| `lib/pages/disposal_report/data/disposal_report_data.dart` | `DisposalReportPageArgs`, `DisposalAnimalGroup` | CURRENT | аргументы экрана (`date`, `causeId`, `placeId`, `reasonName`, `placeName`, `isUnsent`) и модель группы отчёта |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.load`, `DisposalReportCubit.toggleGroup` | CURRENT | ядро сценария — pull с фильтром по `sync`/`causeId`/`placeId` на уровне запроса, фильтрация по дню+минуте и группировка в памяти; `toggleGroup` — раскрытие/сворачивание группы после `loaded` |
| `lib/pages/disposal_report/cubit/disposal_report_state.dart` | `DisposalReportState.initial`, `DisposalReportState.loading`, `DisposalReportState.loaded`, `DisposalReportState.error` | CURRENT | freezed-состояния экрана |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getDisposalsWithDetailsByFilters` | CURRENT | тонкая обёртка над DAO; передаёт `sync`/`causeId`/`placeId` без изменений |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllDisposalsWithDetailsByFilters` | CURRENT | реальный источник данных — join с `Place`/`DisposalReason`, отдельное подтягивание животных (`isNotDeleted: null`), без `ORDER BY` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_with_details.dart` | `DisposalWithDetails` | CURRENT | модель строки, читаемая кубитом (`disposal`, `animal`) |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.firstMainNumber`, `AnimalWithDetails.ageGroup`, `AnimalWithDetails.kind` | CURRENT | источники имени группы (`ageGroup?.name ?? kind?.name ?? '-'`) и отображаемого номера животного |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportAnimalEntry`, `EventReportGroup`, `EventReportScaffold`, `EventReportBody` | CURRENT | общий UI-шаблон посуточных отчётов, переиспользуемый другими `EVT` (движение/вакцинация/взвешивание/выбытие) |
| `lib/pages/routes.dart` | `Routes.disposalReport` | CURRENT | константа имени/пути маршрута |

## Критерии приёмки

- Тап по элементу выбытия посуточного списка (`DisposalDayItem`) или по
  карточке хаба неотправленных открывает `DisposalReportPage` и запускает
  `DisposalReportCubit.load` ровно один раз, синхронно эмитируя `loading`,
  затем (при отсутствии исключений) `loaded`.
- `getDisposalsWithDetailsByFilters` вызывается с `causeId: args.causeId`,
  `placeId: args.placeId` и `sync: false`, если `args.isUnsent == true`, либо
  `sync: null`, если `args.isUnsent == false` (значение по умолчанию).
- `loaded`-состояние включает только те записи из результата запроса, у
  которых `DateUtils.dateOnly(date) == day` и
  `DateFormat('HHmm').format(date) == DateFormat('HHmm').format(args.date)`,
  где `date = disposal.date ?? disposal.createdAt`; запись без обеих дат
  исключается.
- `totalAnimals` равен числу записей, прошедших фильтр дня+времени
  (`matching.length`), не числу уникальных животных.
- Животные группируются по `ageGroup?.name ?? kind?.name ?? '-'`; каждая
  группа хранит `count` и список пар (`animalId`, номер — `firstMainNumber`
  либо `'-'`).
- `reasonName`/`placeName` в `loaded`-состоянии — ровно значения
  `args.reasonName`/`args.placeName`, без дополнительного обращения к
  справочникам внутри `load`.
- Любое исключение при загрузке/группировке данных приводит к
  `error`-состоянию с текстом исключения, не к `loaded`.
- Пункт меню «Удалить» показывается только при `args.isUnsent == true`; при
  `false` (путь из общего календаря) отчёт полностью read-only.

## Связанные тесты

`test/pages/disposal_report_cubit_test.dart`, группа `group('UC-111 —
DisposalReportCubit.load', () { ... })` (старая нумерация, см. правило
именования выше) — две проверки внутри:

- `test('успех (args.isUnsent:true -> sync:false) -> группирует по kind,
  учитывает только совпадающие по дате+времени+месту', () async { ... })` —
  `args.isUnsent: true`; `getDisposalsWithDetailsByFilters` замокан на
  `sync: false, causeId: 2, placeId: 5` и возвращает две записи (одну с
  совпадающим временем, одну на час позже того же дня/места); после
  `cubit.load(args)` проверяется `state.totalAnimals == 1` и
  `state.placeName == args.placeName`.
- `test('isUnsent:false -> sync передаётся как null вместо false', () async
  { ... })` — отдельные `localArgs` с `isUnsent: false`; репозиторий
  замокан на возврат `[]` строго с параметрами `sync: null, causeId: 2,
  placeId: 5`; после `cubit.load(localArgs)` проверяется через
  `verify(...).called(1)`, что вызов действительно произошёл именно с
  `sync: null` (не `sync: false`) — прямое покрытие ветки `args.isUnsent ?
  false : null` для случая `isUnsent == false`.

Соседняя группа `group('UC-112 — DisposalReportCubit.load', () { ... })`
в том же файле покрывает ветку `error` (другой `RESULT` — `READ_ERROR`, не
предмет этого файла): репозиторий замокан на `thenThrow`, проверяется
`cubit.state.when(... error: (message) => expect(message,
contains('db error')))`.

Отдельная группа `group('DisposalReportCubit.toggleGroup', () { ... })` в
том же файле покрывает переключение `isExpanded` (успешный кейс после
`loaded` и no-op до `loaded`) — самостоятельное взаимодействие с уже
загруженным отчётом, не предмет этого файла (см. основной поток, шаг 11).

## Открытые вопросы и ограничения

- **Нет отдельного use-case-файла для `READ_ERROR`-исхода этого же метода**
  (покрыт тестовой группой `'UC-112 — DisposalReportCubit.load'`) — при его
  заведении сослаться отсюда обратно нельзя (traceability только вверх), но
  из него можно процитировать этот файл как предшествующий `READ_OK`-путь.
- **`placeId`/`causeId` в аргументах навигации теоретически могут быть
  `null` с одного из двух входных путей, но не с другого.** Со стороны
  календаря (`ReportsDayListCubit._buildGroupsByType`/`._buildGroupsByPlace`)
  `placeId` гарантированно не `null` (оба вызывающих места передают
  конкретный `pid`, полученный из `PlaceWithAnimals.place.idRemote` —
  `null`-значения пропускаются раньше, до вызова `buildDisposalItems`). Со
  стороны хаба неотправленных `args.placeId`/`args.causeId` — прямое
  значение `Disposal.placeId`/`causeId` через джойн
  (`UnsentDisposalsPopulated._groupByEvent`), без гарантии не-`null`: сама
  запись `Disposal` создаётся с `placeId: animal.placeId ??
  _data.fromPlace?.place.idRemote`
  (`lib/pages/animal_disposal/animal_disposal_bloc.dart`) — теоретически
  `null`, если на момент выбытия у животного не было `placeId` и форма не
  выбирала ферму отправления. Не воспроизведено тестовыми данными в рамках
  этого файла — открытый вопрос, насколько реалистичен такой `Disposal` на
  практике.
- **Порядок групп в отчёте не гарантирован явной сортировкой** — зависит от
  порядка строк, вернувшихся из `DisposalsDao.getAllDisposalsWithDetailsByFilters`
  (запрос без `ORDER BY`). Не проверялось, является ли фактический порядок
  (обычно rowid/insertion order в SQLite) достаточно стабильным для
  пользователя на практике или это скрытый источник визуальной
  нестабильности между повторными открытиями одного и того же отчёта.
- **`DisposalReason`/`Place`, подтянутые join'ом `getAllDisposalsWithDetailsByFilters`,
  фактически не читаются `load`** (заголовок использует `args.reasonName`/
  `args.placeName` напрямую) — join выполняется, но его результат по этим
  двум полям отбрасывается; не исследовано, является ли это намеренной
  экономией (заголовок уже знает нужные имена от вызывающего экрана) или
  случайным избыточным запросом.
