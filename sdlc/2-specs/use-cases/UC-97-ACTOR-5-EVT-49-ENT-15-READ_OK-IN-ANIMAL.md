# UC-97 — Пользователь открывает посуточный отчёт по взвешиванию для места/дня

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-49](../events/EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь тапает по элементу взвешивания в посуточном списке отчётов
(`reports_day_list`) и открывает экран `WeighingReportPage`, чтобы увидеть,
сколько животных и с каким суммарным весом было взвешено в этот конкретный
день на месте (или, если место не задано, вообще во всей локальной базе),
с разбивкой по возрастной группе/виду.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/weighing_report/cubit/weighing_report_cubit.dart` целиком:
`WeighingReportCubit` не объявляет и не использует ничего, завязанного на
статус авторизации — доступ к отчёту от него не зависит.

## CURRENT

### Основной поток

1. Пользователь находится на экране посуточного списка отчётов
   (`ReportsDayListPopulated`) и тапает по элементу взвешивания дня. Тап
   обрабатывается `ReportsDayListPopulated._navigateItem` — ветка `case
   WeighingDayItem(:final date, :final placeId, :final placeName)` вызывает
   `context.pushNamed2(Routes.weighingReport, extra: WeighingReportPageArgs(date:
   date, placeId: placeId, placeName: placeName))`. Это единственное место в
   коде, где строится `WeighingReportPageArgs`.
2. `WeighingReportView.build` читает аргументы через
   `GoRouterState.of(context).getExtraByName<WeighingReportPageArgs>(Routes.weighingReport)`
   и создаёт `BlocProvider(create: (context) => WeighingReportCubit()..load(args))` —
   `load` вызывается ровно один раз, синхронно со сборкой страницы.
3. `WeighingReportCubit.load` сразу эмитит `WeighingReportState.loading()`,
   затем входит в `try`.
4. `day = DateUtils.dateOnly(args.date)`.
5. `animals = await _animalsRepo.getAllAnimalsWithDetailsByFilters()` —
   вызывается **без единого именованного параметра**, то есть со всеми
   значениями по умолчанию репозиторного метода: `isNotDeleted: true`
   (исключает животных с `deletedAt != null`), `isShowRemoteSource: false`
   (исключает животных с непустым `source`), без `farmId` вовсе. Реальный
   SQL-запрос (`AnimalsDao.getAllAnimalsWithDetailsByFilters`) не содержит
   `ORDER BY` — порядок строк в `animals` не гарантирован кодом.
6. `filtered = animals.where((a) => args.placeId == null || a.placeId ==
   args.placeId)` — единственный фильтр по месту, применяемый в памяти;
   фермы (`farmId`) в фильтрации не участвуют вовсе (см. «Бизнес-правила»).
7. `animalIds = filtered.map((a) => a.animalId).toList()`.
8. **Ранний выход при пустом `animalIds`.** Если после фильтрации по месту
   не осталось ни одного животного, кубит немедленно эмитит
   `WeighingReportState.loaded(date: args.date, placeName: args.placeName,
   kindName: null, totalAnimals: 0, groups: [])` и возвращается —
   `AnimalWeighingsRepository` в этом случае вообще не вызывается.
9. Иначе — `weighings = await _weighingsRepo
   .getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds)`, что
   доходит до `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`:
   `SELECT ... WHERE animalId IN (:animalIds) ORDER BY weighingDate ASC` —
   **без единого фильтра по `sync`** (в отличие от
   `getSyncAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`, соседнего метода
   того же DAO, который явно фильтрует `sync == true`) — попадают и ещё не
   отправленные, и уже синхронизированные записи.
10. `forDay = weighings.where((w) =>
    DateUtils.dateOnly(w.weighingDate).isAtSameMomentAs(day))` — фильтр по дню
    в памяти.
11. `animalById = {for (final a in filtered) a.animalId: a}` — карта для
    последующего джойна; поскольку `weighings` уже отфильтрованы DAO строго по
    `animalIds` из `filtered`, `animalById[w.animalId]` не может оказаться
    `null` для строки из `forDay`.
12. Цикл по `forDay`, в порядке возрастания `weighingDate`: для каждой записи
    `groupName = animal?.ageGroup?.name ?? animal?.kind?.name ?? '-'`;
    аккумулятор группы (`_WeighingGroupAccum`, `count`/`totalWeight`) создаётся
    при первом появлении имени группы (`accumByGroup.putIfAbsent`) и
    увеличивается на каждую запись (`count++`, `totalWeight += w.weight`) — без
    дедупликации по `animalId` (см. «Бизнес-правила»).
13. `groups = accumByGroup.entries.map((e) => WeighingAnimalGroup(groupName:
    e.key, totalWeightKg: e.value.totalWeight, count: e.value.count)).toList()`
    — порядок групп = порядок первого появления `groupName` при переборе
    `forDay` (т.е. по возрастанию даты взвешивания записи, первой давшей эту
    группу); внутри группы нет ни списка животных, ни их номеров — только
    агрегаты.
14. `firstAnimal = filtered.firstOrNull` (первый элемент **всего** `filtered` —
    списка животных места/фермы после фильтра по `placeId`, **до** фильтрации
    по дню, в порядке, в котором их вернула БД, т.е. без гарантированного
    порядка); `kindName = firstAnimal?.kind?.name`.
15. `totalAnimals = groups.fold(0, (sum, g) => sum + g.count)` — сумма
    аккумулированных `count` по всем группам, то есть равна числу строк
    `forDay` (записей взвешивания за день), не числу уникальных животных.
16. Эмитится `WeighingReportState.loaded(date: args.date, placeName:
    args.placeName, kindName: kindName, totalAnimals: totalAnimals, groups:
    groups)`.
17. `WeighingReportView` рендерит `Scaffold` с `CustomAppBar` (заголовок
    `l10n.weighing`, подзаголовок — `args.date` в формате `dd.MM.yyyy HH:mm` —
    **не** `state.date`, хотя оба значения совпадают, так как оба берутся из
    того же `args`), телом `_WeighingReportBody`: шапка `ReportInfoHeader` с
    чипами `[placeName, kindName]` (оба — только если не `null`) и
    `totalAnimals`, затем плоский `ListView.builder` из `_WeighingGroupRow` —
    по одной строке на группу (имя группы, суммарный вес в `l10n.kg`, число
    записей) — без аккордеона и без раскрытия списка животных группы, в
    отличие от посуточного отчёта по вакцинации (`EventReportScaffold`/
    `_KindAccordion`, [UC-81](UC-81-ACTOR-5-EVT-41-ENT-14-READ_OK-IN-ANIMAL.md)).

### Альтернативные потоки

- **Ни одного животного после фильтра по месту (или взвешиваний за день не
  найдено).** Покрыто шагом 8 основного потока или пустым `forDay` на шаге
  10 — в обоих случаях `loaded` с `totalAnimals: 0`, `groups: []`; во втором
  случае, в отличие от первого, `AnimalWeighingsRepository` всё же был вызван.
  Тот же `RESULT` (`READ_OK` — вызов успешно завершился, просто без данных),
  не отдельный use-case.
- **`args.placeId == null`.** Код это явно поддерживает (фильтр по месту на
  шаге 6 просто пропускается, запрос животных выполняется вообще без
  ограничения по ферме/месту) — но по факту недостижимо через единственный
  существующий путь навигации на этот экран (см. «Открытые вопросы»).
- **Исключение внутри `try`** (например сбой доступа к локальной БД в
  `getAllAnimalsWithDetailsByFilters`/`getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`
  или при построении групп) — перехватывается, эмитится
  `WeighingReportState.error(e.toString())`. Другой `RESULT` (`READ_ERROR`),
  не предмет этого файла (покрыт соседней группой `'UC-98 —
  WeighingReportCubit.load'` в том же тестовом файле; отдельный use-case для
  этого исхода на момент написания этого файла ещё не заведён).

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  единственная сущность, чьё состояние (в смысле сегмента `ENT` в имени этого
  use-case) здесь читается; сама запись не изменяется. Читается **без
  исключения** ещё не отправленных записей (`sync == false`), наравне с
  синхронизированными.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `AnimalWithDetails` на каждой строке `filtered`; `placeId` используется для
  фильтрации, `animalId` — как ключ джойна с взвешиваниями,
  `ageGroup`/`kind` — для имени группы и для `kindName` шапки; не изменяется.
  Запрос неявно исключает животных с `deletedAt != null` и с непустым
  `source` (значения по умолчанию `isNotDeleted`/`isShowRemoteSource` — см.
  «Бизнес-правила»).

### Бизнес-правила

- **Фильтрация только по месту, никогда по ферме.** В отличие от посуточного
  отчёта по вакцинации ([UC-81](UC-81-ACTOR-5-EVT-41-ENT-14-READ_OK-IN-ANIMAL.md),
  `VaccinationReportPageArgs.farmId` — обязательный фильтр), у
  `WeighingReportPageArgs` вообще нет поля `farmId`, и
  `WeighingReportCubit.load` не передаёт `farmId` в
  `getAllAnimalsWithDetailsByFilters` ни при каком `args.placeId`. Пока
  `placeId` задан (единственный достижимый на практике случай — см. «Открытые
  вопросы»), это не создаёт видимой утечки между фермами, так как место
  однозначно принадлежит одной ферме; при гипотетическом `placeId == null`
  отчёт агрегировал бы животных **всей локальной базы**, а не одной фермы.
- **`totalAnimals` считает записи взвешивания за день, не уникальных
  животных.** Если одно и то же животное взвешено дважды в один день (в
  таблице оказались две строки `AnimalWeighing` с одинаковым `animalId` и
  датой в пределах одного дня), обе учитываются отдельно и в `count` своей
  группы, и в итоговом `totalAnimals`.
- **`kindName` шапки — вид первого животного всего отфильтрованного по месту
  списка, не обязательно связан с показанными группами дня.** `firstAnimal`
  берётся из `filtered` (все животные места/фермы, до фильтра по дню) в
  порядке, в котором их вернула БД (без `ORDER BY` в запросе) — животное может
  не иметь ни одной записи взвешивания за этот день вовсе, при этом его
  `kind.name` всё равно попадёт в чип шапки, потенциально не совпадая ни с
  одной из фактически отображённых групп.
- **Группы не хранят список животных.** `WeighingAnimalGroup` — только
  `groupName`/`totalWeightKg`/`count`; в отличие от вакцинации/движения,
  экран не даёт раскрыть группу до списка конкретных животных/номеров
  транспондеров.
- **Неявные фильтры по умолчанию репозиторного метода.** Вызов
  `getAllAnimalsWithDetailsByFilters()` без параметров означает
  `isNotDeleted: true` (исключает `deletedAt != null`) и
  `isShowRemoteSource: false` (исключает `source != null`) — тот же метод,
  вызываемый на уровне построения самого посуточного списка
  (`ReportsDayDataLoader.load` → `_animalsRepo.getAllAnimalsWithDetailsByFilters(isNotDeleted:
  null, isShowRemoteSource: null)`), **без** этих ограничений. Открытие
  отчёта по конкретному дню повторно читает животных с более строгим
  фильтром, чем тот, что использовался при построении самого превью-элемента
  в списке дня — теоретическая возможность расхождения счётчиков между
  превью и детальным отчётом для животных с `deletedAt != null` или
  непустым `source` (см. «Открытые вопросы»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и обе покрытые тестами альтернативные ветки (пустой
список животных; пустой `forDay`) полностью реализованы и достижимы из UI, за
вычетом ветки `args.placeId == null` (см. «Открытые вопросы»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` | CURRENT | единственная точка построения `WeighingReportPageArgs` и перехода на `Routes.weighingReport` |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildWeighingItems` | CURRENT | строит `WeighingDayItem` (источник `date`/`placeId`/`placeName` для аргументов экрана); оба вызывающих места (`_buildGroupsByType`, `_buildGroupsByPlace`) передают только не-`null` `placeId` |
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit._buildGroupsByType`, `ReportsDayListCubit._buildGroupsByPlace` | CURRENT | оба места вызова `buildWeighingItems` — оба гарантируют не-`null` `placeId` (`required int placeId` / `if (pid == null) continue;`) |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | тот же репозиторный метод (`_animalsRepo.getAllAnimalsWithDetailsByFilters`) читается ещё раз при построении самого дневного списка, с другими значениями `isNotDeleted`/`isShowRemoteSource` |
| `lib/pages/routes.dart` | `Routes.weighingReport` | CURRENT | константа имени/пути маршрута |
| `lib/pages/weighing_report/data/weighing_report_data.dart` | `WeighingReportPageArgs`, `WeighingAnimalGroup` | CURRENT | аргументы экрана (`date`, `placeId`, `placeName` — без `farmId`) и модель группы отчёта |
| `lib/pages/weighing_report/presentation/widgets/weighing_report_view.dart` | `WeighingReportView.build`, `_WeighingReportBody`, `_WeighingGroupRow` | CURRENT | чтение args, создание `BlocProvider(..load(args))`, рендер по `state.when` — плоский список групп без раскрытия по животным |
| `lib/pages/weighing_report/presentation/weighing_report_page.dart` | `WeighingReportPage` | CURRENT | тонкая обёртка над `WeighingReportView` |
| `lib/pages/weighing_report/cubit/weighing_report_cubit.dart` | `WeighingReportCubit.load` | CURRENT | ядро сценария — pull + фильтрация/группировка в памяти |
| `lib/pages/weighing_report/cubit/weighing_report_state.dart` | `WeighingReportState.initial`, `WeighingReportState.loading`, `WeighingReportState.loaded`, `WeighingReportState.error` | CURRENT | freezed-состояния экрана |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | тонкая обёртка над DAO; вызывается кубитом без параметров (все значения по умолчанию) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | реальный источник данных; без `ORDER BY`, с фильтрами `deletedAt.isNull()`/`source.isNull()` по умолчанию (`isNotDeleted`/`isShowRemoteSource`) |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | тонкая обёртка над DAO |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | реальный источник данных — `WHERE animalId IN (...) ORDER BY weighingDate ASC`, без фильтра по `sync` (в отличие от соседнего `getSyncAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`) |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.kind`, `AnimalWithDetails.ageGroup` | CURRENT | источники имени группы (`ageGroup?.name ?? kind?.name ?? '-'`) и `kindName` шапки |
| `lib/widgets/event_report/report_info_header.dart` | `ReportInfoHeader` | CURRENT | общий виджет шапки отчёта (чипы + `totalAnimals`), переиспользуемый другими посуточными отчётами |

## Критерии приёмки

- Тап по элементу взвешивания посуточного списка (`WeighingDayItem`)
  открывает `WeighingReportPage` и запускает `WeighingReportCubit.load` ровно
  один раз, синхронно эмитируя `loading`, затем (при отсутствии исключений)
  `loaded`.
- Если после фильтрации по `args.placeId` (когда задан) не осталось ни
  одного животного — `loaded` эмитится немедленно с `totalAnimals: 0`,
  `groups: []`, `kindName: null`, и `AnimalWeighingsRepository` не
  вызывается вовсе.
- Иначе — `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`
  вызывается ровно с теми `animalId`, что остались после фильтра по месту, и
  результат фильтруется по `DateUtils.dateOnly(weighingDate) ==
  DateUtils.dateOnly(args.date)` — независимо от `sync`/`remoteId` записи.
- `totalAnimals` в `loaded`-состоянии равен числу отфильтрованных по дню
  записей взвешивания (`forDay.length`), не числу уникальных животных — одно
  и то же животное, взвешенное дважды в этот день, учитывается дважды.
- Животные группируются по `ageGroup?.name ?? kind?.name ?? '-'`; каждая
  группа хранит только `count` и суммарный `totalWeightKg` — без списка
  конкретных животных.
- `kindName` в `loaded`-состоянии — `kind?.name` первого животного из
  `filtered` (весь список после фильтра по месту, до фильтра по дню, без
  гарантированного порядка) — не обязательно связан ни с одной из
  фактически показанных групп.
- `placeName` в `loaded`-состоянии — ровно значение `args.placeName`, без
  обращения к справочнику мест.
- Любое исключение при загрузке/группировке данных приводит к
  `error`-состоянию с текстом исключения, не к `loaded`.

## Связанные тесты

`test/pages/weighing_report_cubit_test.dart`, группа `group('UC-97 —
WeighingReportCubit.load', () { ... })` — три проверки внутри (имя группы и
номер в идентификаторе теста — старые, будут переименованы отдельным
проходом):

- `test('нет животных вообще -> loaded с totalAnimals:0, weighings не
  запрашиваются', () async { ... })` — `getAllAnimalsWithDetailsByFilters`
  возвращает `[]`; после `load` состояние `WeighingReportLoaded` имеет
  `totalAnimals == 0`, и `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`
  не вызывается вовсе (`verifyNever`).
- `test('успех -> группирует по kind, считает totalAnimals только для
  этого дня', () async { ... })` — одно животное с двумя записями
  взвешивания на разные даты; после `load` `totalAnimals == 1`, единственная
  группа имеет `groupName == 'Овца'` и `totalWeightKg == 20` (вес записи
  именно за запрошенный день, не сумма обеих записей).
- `test('placeId задан -> фильтрует животных по месту до запроса
  взвешиваний', () async { ... })` — два животных с разными `placeId`;
  проверяется, что `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`
  вызывается ровно с `[1]` (id животного на запрошенном месте), не с обоими
  id.

Соседняя группа `group('UC-98 — WeighingReportCubit.load', () { ... })` в
том же файле покрывает ветку `error` (другой `RESULT`, не предмет этого
файла).

## Открытые вопросы и ограничения

- **Ветка `args.placeId == null` в `WeighingReportCubit.load`
  недостижима из текущего UI.** Единственное место, строящее
  `WeighingReportPageArgs` — `ReportsDayListPopulated._navigateItem`, и
  единственный источник `WeighingDayItem` — `ReportsDayQuery.buildWeighingItems`,
  вызываемый из двух мест (`ReportsDayListCubit._buildGroupsByType` и
  `._buildGroupsByPlace`) — в обоих вызывающий код гарантирует не-`null`
  `placeId` (`required int placeId` в первом случае; `if (pid == null)
  continue;` во втором). Если бы этот путь когда-либо стал достижим, отчёт
  агрегировал бы животных **всей локальной базы**, а не одной фермы — у
  `WeighingReportCubit` в отличие от вакцинации/движения нет собственного
  понятия `farmId` вовсе, только `placeId`.
- **Расхождение фильтров животных между превью в списке дня и самим
  отчётом.** `ReportsDayDataLoader.load` (строит превью-элемент
  `WeighingDayItem` в самом списке дня) читает животных с `isNotDeleted:
  null, isShowRemoteSource: null` (без этих ограничений), а
  `WeighingReportCubit.load` (открытие детального отчёта по тому же дню)
  читает их же с умолчаниями метода — `isNotDeleted: true, isShowRemoteSource:
  false`. Не проверялось на практике (нет теста и не найдено готовых
  тестовых животных с `deletedAt != null`/непустым `source` в базе), но
  теоретически два экрана могут показать разные числа для одного и того же
  дня/места, если такие животные есть.
- **`kindName` шапки может не соответствовать показанным группам.** Берётся
  из первого животного всего отфильтрованного по месту списка (до фильтра по
  дню, без гарантированного порядка запроса), а не из группы с максимальным
  количеством/весом или иной агрегированной логики — риск показать в чипе
  вид, которого нет ни в одной из отображённых групп дня.
- **`totalAnimals` — счётчик записей взвешивания, а не уникальных
  животных** — то же допущение, что и в посуточном отчёте по вакцинации
  ([UC-81](UC-81-ACTOR-5-EVT-41-ENT-14-READ_OK-IN-ANIMAL.md)); не
  проверялось, является ли это осознанным продуктовым решением или
  расхождением с ожиданием пользователя («сколько животных взвесили»).
- **Отсутствие детализации по животным внутри группы** (в отличие от
  вакцинации/движения) — не зафиксировано нигде в коде/комментариях, было ли
  это осознанным упрощением экрана взвешивания или просто ещё не
  реализованной частью функциональности.
- **Отдельный use-case для `READ_ERROR`-исхода этого же метода
  (`WeighingReportCubit.load`, соседняя тестовая группа `'UC-136'`) на момент
  написания этого файла ещё не заведён** — при заведении его нужно будет
  явно сослаться отсюда обратно нельзя (traceability только вверх), но из
  него — процитировать этот файл как предшествующий `READ_OK`-путь.
