# UC-81 — Пользователь открывает посуточный отчёт по вакцинации фермы/места/дня

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь тапает по вакцинационному пункту посуточного списка отчётов
фермы/места (`reports_day_list`) и открывает экран `VaccinationReportPage`,
чтобы увидеть, сколько и каких животных было провакцинировано в этот
конкретный день на этой ферме (и, как правило, в этом месте) — с разбивкой
по возрастной группе/виду и общей шапкой отчёта (место, вакцина(ы), способ(ы)
введения, доза, дата вакцинации).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, без разницы для этого сценария).

## CURRENT

### Основной поток

1. Пользователь находится на экране посуточного списка отчётов
   (`ReportsDayListPopulated`) и тапает по элементу вакцинации дня. Тап
   обрабатывается `ReportsDayListPopulated._navigateItem` — ветка `case
   VaccinationDayItem(:final date, :final farmId, :final placeId, :final
   placeName)` вызывает `context.pushNamed2(Routes.vaccinationReport, extra:
   VaccinationReportPageArgs(date: date, farmId: farmId, placeId: placeId,
   placeName: placeName))`. Это единственное место в коде, где строится
   `VaccinationReportPageArgs` (см. «Открытые вопросы» — почему `placeId`
   на практике всегда не `null`).
2. `VaccinationReportPage.build` читает аргументы через
   `GoRouterState.of(context).getExtraByName<VaccinationReportPageArgs>(Routes.vaccinationReport)`
   и создаёт `BlocProvider(create: (context) => VaccinationReportCubit()..load(args))`.
3. `VaccinationReportCubit.load` немедленно эмитит
   `VaccinationReportState.loading()`.
4. `day = DateUtils.dateOnly(args.date)`.
5. `all = await _vaccinationsRepo.getVaccinationsWithDetails()` —
   вызывается **без параметра `ids`**, что доходит до
   `VaccinationsDao.getVaccinationsWithDetails()` и возвращает вообще все
   строки таблицы `Vaccinations` (джойн с вакциной/юнитом/способом и местом
   введения/типом вакцинации, плюс подтягивание животного и списка болезней
   на каждую строку) — без единого фильтра по `sync`/`deletedAt`/`updatedAt`/`createdAt`,
   несмотря на doc-комментарий метода в исходнике (см. «Бизнес-правила»).
   Строка, для которой связанное животное не найдено вовсе
   (`AnimalsDao.getAnimalWithDetailsById` вернул `null`), в результат не
   попадает — но уже удалённое (`deletedAt != null`), но всё ещё существующее
   животное найдено будет (`getAnimalWithDetailsById` вызывает
   `getAllAnimalsWithDetailsByFilters` с `isNotDeleted: null`, то есть без
   фильтра по этому полю).
6. `all` фильтруется в памяти в `forDay` по трём условиям одновременно:
   `DateUtils.dateOnly(v.vaccinationDate).isAtSameMomentAs(day)`,
   `v.animal.farmId == args.farmId`, и (только если `args.placeId != null`)
   `v.animal.placeId == args.placeId`.
7. Для каждой записи `forDay`, в порядке итерации (список `all` приходит из
   DAO уже отсортированным `ORDER BY vaccinationDate DESC`, `forDay` — его
   подмножество без изменения порядка):
   - имя группы — `v.animal.ageGroup?.name ?? v.animal.kind?.name ?? '-'`;
   - номер для отображения — `v.animal.activeAnimalIdentifications
     .firstWhereOrNull((id) => id.markerTypeId ==
     Constants.TransponderMarkerTypeId)?.number ?? '-'` (`TransponderMarkerTypeId
     == 3`);
   - запись добавляется в `byGroup[groupName]` как
     `EventReportAnimalEntry(animalId: v.animal.animalId, number: transponder)`.
8. Одновременно, по тому же проходу цикла: `vaccineNames` (`Set<String>`,
   `v.vaccine.name`) и `methodNames` (`Set<String>`, `v.injectionMethod?.name
   ?? '-'`) накапливают уникальные значения по всем записям `forDay`;
   `doseStr` присваивается **только один раз, у самой первой записи цикла**
   (`doseStr ??= '${v.dose.toStringAsFixed(0)} ${v.unit?.name ?? ''}'`) — доза
   и единица измерения любых последующих записей в `forDay`, даже с другим
   значением, в шапку не попадают (см. «Бизнес-правила»).
9. `groups` строится из `byGroup.entries.map(...)` в
   `EventReportGroup(kindName, count: animals.length, animals)` —
   `isExpanded` по умолчанию `false`; порядок групп = порядок первого
   появления имени группы при переборе `forDay`.
10. `chips` собираются в фиксированном порядке: `args.placeName` (если не
    `null`) → все `vaccineNames` → все `methodNames` → `doseStr` (если
    установлен) → строка `'дата вакцинации: '` + `DateFormat('dd.MM.yyyy').format(args.date)`.
11. Эмитится `VaccinationReportState.loaded(date: args.date, chips,
    totalAnimals: forDay.length, groups)`.
12. `VaccinationReportPage` рендерит `EventReportScaffold` (заголовок
    `l10n.vaccination`, подзаголовок — `args.date` в формате `dd.MM.yyyy
    HH:mm`) с телом `EventReportBody`: шапка `ReportInfoHeader(chips,
    totalAnimals)`, затем список `_KindAccordion` — по одному на группу,
    заголовок группы + счётчик животных; тап по строке разворачивает список
    номеров животных этой группы через `onToggleGroup` →
    `VaccinationReportCubit.toggleGroup` (отдельный сценарий, не предмет
    этого файла).

### Альтернативные потоки

- **Ни одной вакцинации за день/ферму/место не найдено.** `forDay` пуст —
  цикл группировки не выполняется, `groups == []`, `totalAnimals == 0`;
  `chips` всё равно строятся (`placeName` + пустая дата вакцинации без вакцин/
  способов/дозы). `EventReportBody` рендерит `l10n.no_data` вместо списка
  групп. Тот же `RESULT` (`READ_OK` — вызов успешно завершился, просто без
  данных), не отдельный use-case.
- **Исключение внутри `try`** (например сбой доступа к локальной БД в
  `getVaccinationsWithDetails` или при подтягивании животного/болезней внутри
  DAO) — перехватывается, эмитится `VaccinationReportState.error(e.toString())`.
  Другой `RESULT` (`READ_ERROR`), не предмет этого файла (см. «Связанные
  тесты» — покрыт отдельной группой в том же тестовом файле).
- **`args.placeId == null`.** Код это явно поддерживает (фильтр по месту
  просто пропускается, отчёт агрегирует по всей ферме) — но по факту
  недостижимо через единственный существующий путь навигации на этот экран
  (см. «Открытые вопросы»).

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  единственная сущность, чьё состояние (в файловом смысле сегмента `ENT` в
  имени этого use-case) здесь читается; сама запись не изменяется. Читается
  **без исключения** ещё не отправленных, редактируемых и помеченных на
  удаление строк (см. «Бизнес-правила»), в отличие от истории вакцинаций
  животного, которая по умолчанию показывает только синхронизированные
  записи.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `v.animal` (`AnimalWithDetails`) на каждой строке; `farmId`/`placeId`
  используются для фильтрации, `ageGroup`/`kind` — для имени группы,
  `animalId` — для перехода на карточку животного из развёрнутого списка.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается через
  `v.animal.activeAnimalIdentifications` для поиска номера транспондера,
  отображаемого в развёрнутой группе.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (HANDBOOKS,
  Unit) — `v.unit?.name` используется при построении строки дозы в шапке
  отчёта.
- VAC-локальные справочники без собственного `ENT` (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Связи»): `Vaccine`
  (`v.vaccine.name` — название вакцины в чипах), `InjectionMethod`
  (`v.injectionMethod?.name` — способ введения в чипах).

### Бизнес-правила

- **Doc-комментарий `VaccinationsDao.getVaccinationsWithDetails` не
  соответствует коду.** Комментарий гласит «Получить вакцинации с деталями
  (isSync=true && deletedAt==null && updatedAt==null && createdAt!=null)», но
  реальный `where(...)` метода — только `ids == null ? Constant(true) :
  vaccinationAlias.id.isIn(ids)`; фильтра по `sync`/`deletedAt`/`updatedAt`/
  `createdAt` в запросе нет вовсе. Практическое следствие для этого экрана:
  посуточный отчёт по вакцинации показывает **вообще все** вакцинации дня —
  включая ещё не отправленные (`sync == false`), находящиеся в правке
  (`updatedAt != null`) или помеченные на удаление (`deletedAt != null`) и
  записи с сохранённым текстом ошибки push (`errors != null`) — в отличие от
  истории вакцинаций конкретного животного, которая по умолчанию
  (`sync: true`) показывает только синхронизированные записи (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Инварианты»).
- **Доза/единица измерения в шапке — только у первой по порядку записи
  дня**, не агрегированная сводка. Если в один день/на ферме/в месте
  зафиксированы вакцинации с разными дозами, в чипах отчёта будет показана
  доза только той записи, что оказалась первой в `forDay` (по убыванию
  `vaccinationDate` от DAO, при равных датах — по порядку строк в БД) — не
  максимум/сумма/список.
- `vaccineNames`/`methodNames` — множества (`Set<String>`, фактически
  `LinkedHashSet`), поэтому порядок чипов детерминирован (порядок первого
  появления значения при переборе `forDay`), но сами значения не привязаны к
  конкретной группе животных — одна общая шапка на весь отчёт, а не на
  группу.
- **`activeAnimalIdentifications` — геттер, чьё имя не отражает поведение.**
  `AnimalWithDetails.activeAnimalIdentifications` определён как
  `animalIdentifications.where((e) => true).toList()` — фильтр-заглушка,
  фактически возвращающая все идентификации животного без разбора,
  независимо от поля `isActive` записи ([ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)).
  Первый найденный маркер с `markerTypeId == 3` показывается как «номер»
  вне зависимости от того, активен ли он на самом деле.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и достижим из UI (за вычетом
ветки `args.placeId == null`, см. «Открытые вопросы»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` | CURRENT | единственная точка построения `VaccinationReportPageArgs` и перехода на `Routes.vaccinationReport` |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildVaccinationItems` | CURRENT | строит `VaccinationDayItem` (источник `date`/`farmId`/`placeId`/`placeName` для аргументов экрана) |
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit._buildGroupsByType`, `ReportsDayListCubit._buildGroupsByPlace` | CURRENT | оба места вызова `buildVaccinationItems` — оба передают конкретный (не `null`) `placeId` |
| `lib/pages/routes.dart` | `Routes.vaccinationReport` | CURRENT | константа имени/пути маршрута |
| `lib/pages/vaccination_report/data/vaccination_report_data.dart` | `VaccinationReportPageArgs` | CURRENT | аргументы экрана (`date`, `farmId`, `placeId`, `placeName`) |
| `lib/pages/vaccination_report/presentation/vaccination_report_page.dart` | `VaccinationReportPage.build` | CURRENT | чтение args, создание `BlocProvider(..load(args))`, рендер по `state.when` |
| `lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart` | `VaccinationReportCubit.load` | CURRENT | ядро сценария — pull + фильтрация/группировка/сборка чипов в памяти |
| `lib/pages/vaccination_report/cubit/vaccination_report_state.dart` | `VaccinationReportState.loading`, `VaccinationReportState.loaded`, `VaccinationReportState.error` | CURRENT | freezed-состояния экрана |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | тонкая обёртка над DAO |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetails` | CURRENT | реальный источник данных; без фильтра по `ids`/`sync`, несмотря на doc-комментарий (см. «Бизнес-правила») |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `VaccinationWithDetails` | CURRENT | модель строки, читаемая cubit'ом (`animal`, `vaccine`, `dose`, `unit`, `injectionMethod`, `vaccinationDate`) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | подтягивание животного на каждую строку вакцинации; `isNotDeleted: null` — удалённое животное не отфильтровывается, только полностью отсутствующее |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.activeAnimalIdentifications` | CURRENT | источник номера транспондера в шапке группы; фактически не фильтрует (`where((e) => true)`), несмотря на имя геттера |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId` | CURRENT | id типа маркера (`3`), по которому выбирается номер для отображения |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportAnimalEntry`, `EventReportGroup`, `EventReportScaffold`, `EventReportBody` | CURRENT | общий UI-шаблон посуточных отчётов, переиспользуемый другими `EVT` (movement/weighing/disposal/registration) |

## Критерии приёмки

- Тап по вакцинационному элементу посуточного списка отчётов
  (`VaccinationDayItem`) открывает `VaccinationReportPage` и запускает
  `VaccinationReportCubit.load` ровно один раз, синхронно эмитируя
  `loading`, затем (при отсутствии исключений) `loaded`.
- `loaded`-состояние включает только те вакцинации, у которых
  `DateUtils.dateOnly(vaccinationDate)` совпадает с днём из аргументов,
  `animal.farmId` совпадает с `args.farmId`, и (если `args.placeId != null`)
  `animal.placeId` совпадает с `args.placeId` — независимо от `sync`,
  `deletedAt`, `updatedAt`, `errors` записи.
- `totalAnimals` в `loaded`-состоянии равен числу отфильтрованных
  вакцинаций (`forDay.length`), не числу уникальных животных — одно и то же
  животное, вакцинированное дважды в один день, за один визит в этот день,
  учитывается дважды.
- Животные группируются по `ageGroup?.name ?? kind?.name ?? '-'`; каждая
  группа содержит количество и список пар (`animalId`, номер транспондера
  либо `'-'`).
- Чипы шапки содержат (в этом порядке, когда применимо): название места,
  затем уникальные названия вакцин, затем уникальные способы введения,
  затем строку дозы первой по порядку записи, затем дату вакцинации в
  формате `дата вакцинации: dd.MM.yyyy`.
- Пустой `forDay` даёт `loaded`-состояние с `groups == []` и
  `totalAnimals == 0`, экран показывает `l10n.no_data` вместо списка групп.
- Любое исключение при загрузке данных приводит к `error`-состоянию с
  текстом исключения, не к `loaded`.

## Связанные тесты

`test/pages/vaccination_report_cubit_test.dart`, группа `group('UC-81 —
VaccinationReportCubit.load', () { ... })` — две проверки внутри:

- `test('успех -> группирует по kind, считает totalAnimals только для
  этого дня/фермы', () async { ... })` — три вакцинации с разными датой/
  фермой, проверяет, что после `load` в состоянии `VaccinationReportLoaded`
  `totalAnimals == 1` и единственная группа имеет `kindName == 'Овца'`.
- `test('placeId задан -> фильтрует ещё и по месту', () async { ... })` —
  две вакцинации на одной ферме/дне с разными `placeId`, проверяет, что при
  заданном `args.placeId` в состоянии остаётся только одна (`totalAnimals ==
  1`).

Соседняя группа `group('UC-82 — VaccinationReportCubit.load', () { ... })`
в том же файле покрывает ветку `error` (другой `RESULT`, не предмет этого
файла).

## Открытые вопросы и ограничения

- **Ветка `args.placeId == null` в `VaccinationReportCubit.load`
  недостижима из текущего UI.** Единственное место, строящее
  `VaccinationReportPageArgs` — `ReportsDayListPopulated._navigateItem`, и
  единственный источник `VaccinationDayItem` —
  `ReportsDayQuery.buildVaccinationItems`, вызываемый из двух мест
  (`ReportsDayListCubit._buildGroupsByType` и `._buildGroupsByPlace`) — в
  обоих вызывающий код передаёт конкретный (не `null`) `placeId` (`pid`,
  всегда пришедший из `PlaceWithAnimals.place.idRemote` внутри цикла по
  конкретным местам). Фильтр `if (args.placeId != null) ...` в коде
  `VaccinationReportCubit.load` формально существует и покрыт тестом
  (`placeId задан`), но реального пути открыть этот отчёт без указания
  места на сегодня нет — не проверялось, задумывался ли когда-то
  фермо-уровневый (без места) вход на этот экран, который впоследствии не
  был реализован либо был убран.
- **Doc-комментарий DAO расходится с кодом** (см. «Бизнес-правила») — отчёт
  показывает вакцинации, ещё не отправленные на сервер, в правке или
  ожидающие удаления, а также записи с сохранённой ошибкой push, наравне с
  полностью синхронизированными. Не проверялось, является ли это
  осознанным продуктовым решением («показывать в дневном отчёте вообще всё,
  что физически есть локально») или расхождением с намерением,
  задокументированным в устаревшем комментарии.
- **Доза/единица в шапке — не агрегат.** При неоднородных дозах в пределах
  одного дня/фермы/места пользователь увидит дозу только первой по порядку
  записи, без индикации, что это не единственное значение — риск неверно
  прочитать шапку как «общую дозу для всех» животных отчёта.
- **`activeAnimalIdentifications` не фильтрует по `isActive`.** Имя геттера
  предполагает фильтрацию активных идентификаций, но реализация
  (`where((e) => true)`) возвращает все записи без разбора — если у
  животного есть более одной идентификации с `markerTypeId == 3`
  (транспондер), в отчёте показывается первая найденная, независимо от
  `isActive`.
