# UC-98 — Посуточный отчёт по взвешиванию отказывает технически: `WeighingReportCubit.load` ловит исключение из чтения, эмитит `WeighingReportState.error(e.toString())`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-49](../events/EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-49](../events/EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)
(`animal_weighings.viewed_in_day_report`): пользователь открывает посуточный
отчёт по взвешиванию для места/дня, но `WeighingReportCubit.load`
(`lib/pages/weighing_report/cubit/weighing_report_cubit.dart`) ловит
исключение, брошенное при попытке прочитать животных/взвешивания или
сгруппировать их — техническая ошибка (Drift/БД или иное исключение уровня
данных), не бизнес-отказ (в сценарии нет ни одного guard-условия, способного
сознательно вернуть `REJECTED`: отчёт либо строится по тому, что нашлось,
включая пустой список животных/взвешиваний, либо технически падает).
`catch (e)` безусловно эмитит `WeighingReportState.error(e.toString())` —
сырой текст исключения, без логирования и без стек-трейса.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/weighing_report/cubit/weighing_report_cubit.dart` целиком:
`WeighingReportCubit` не объявляет и не использует `AuthRepository` ни в
одном методе, включая `load` — доступ к отчёту не зависит от статуса
авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает календарь событий, выбирает день — открывается
   `ReportsDayListPage` (`Routes.reportsDayList`), список дня строится через
   `ReportsDayListCubit`/`ReportsDayQuery.buildWeighingItems`, вызываемый из
   `ReportsDayListCubit._buildGroupsByType` и `._buildGroupsByPlace`. Тап по
   такой карточке в `ReportsDayListPopulated`
   (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`)
   на `case WeighingDayItem(:final date, :final placeId, :final placeName)`
   вызывает
   `context.pushNamed2(Routes.weighingReport, extra: WeighingReportPageArgs(date: date, placeId: placeId, placeName: placeName))`.
   В отличие от вакцинации/выбытия — `WeighingReportPageArgs`
   (`lib/pages/weighing_report/data/weighing_report_data.dart`) не содержит
   поля `farmId` вовсе, только `date`/`placeId`/`placeName`.
2. `WeighingReportView.build`
   (`lib/pages/weighing_report/presentation/widgets/weighing_report_view.dart`)
   читает `WeighingReportPageArgs` через
   `GoRouterState.of(context).getExtraByName<WeighingReportPageArgs>(Routes.weighingReport)`
   и создаёт `BlocProvider(create: (context) => WeighingReportCubit()..load(args), ...)` —
   `load` вызывается ровно один раз, синхронно со сборкой страницы;
   `WeighingReportPage` (`lib/pages/weighing_report/presentation/weighing_report_page.dart`)
   сам по себе — тонкая обёртка, целиком делегирующая рендер `WeighingReportView`.
   Повторить `load` (retry) с этого экрана нечем — ни кнопки, ни
   `RefreshIndicator` в `WeighingReportView.build` нет; в отличие от
   вакцинации/движения/выбытия, этот экран не использует общий
   `EventReportScaffold`/`EventReportBody`
   (`lib/widgets/event_report/event_report_template.dart`) — здесь напрямую
   собран `Scaffold` с `CustomAppBar` (заголовок `l10n.weighing`, подзаголовок —
   `args.date` в формате `dd.MM.yyyy HH:mm`, вычисляется в `build` независимо
   от состояния кубита) и `body: state.when(...)`.
3. `WeighingReportCubit.load` сразу эмитит `WeighingReportState.loading()`,
   затем входит в `try`:
   ```dart
   try {
     final day = DateUtils.dateOnly(args.date);
     final animals = await _animalsRepo.getAllAnimalsWithDetailsByFilters();
     final filtered = animals.where(
       (a) => args.placeId == null || a.placeId == args.placeId,
     );
     final animalIds = filtered.map((a) => a.animalId).toList();
     if (animalIds.isEmpty) {
       emit(WeighingReportState.loaded(..., totalAnimals: 0, groups: []));
       return;
     }
     final weighings = await _weighingsRepo
         .getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds);
     // фильтрация forDay по дню, группировка по kind/ageGroup, сбор groups
     emit(WeighingReportState.loaded(...));
   } catch (e) {
     emit(WeighingReportState.error(e.toString()));
   }
   ```
   `_animalsRepo.getAllAnimalsWithDetailsByFilters()` вызывается **вообще без
   параметров** — не только без `ids`, но и без `farmId` (в коде фильтрации
   по ферме для этого отчёта нет вовсе, только по месту, и то в памяти, после
   чтения); это подтягивает всех неудалённых животных всех ферм локальной БД
   (`isNotDeleted: true` — значение по умолчанию параметра DAO), а не только
   животных текущей фермы.
4. **Точка технического сбоя (этот сценарий).**
   `_animalsRepo.getAllAnimalsWithDetailsByFilters()`
   (`lib/repositories/animal/animals_repository.dart` →
   `AnimalsRepository.getAllAnimalsWithDetailsByFilters`, делегирующая
   `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` →
   `AnimalsDao.getAllAnimalsWithDetailsByFilters`) бросает исключение — в
   тесте (`test/pages/weighing_report_cubit_test.dart`) через
   `when(() => animalsRepository.getAllAnimalsWithDetailsByFilters()).thenThrow(Exception('db error'))`,
   без мока конкретной внутренней причины реального DAO-запроса.
5. `catch (e)` без стек-трейса перехватывает исключение и эмитит
   `WeighingReportState.error(e.toString())` — единственный (позиционный)
   аргумент error-варианта, `String message`
   (`lib/pages/weighing_report/cubit/weighing_report_state.dart`). Ни
   `Talker`, ни любой другой логгер здесь не вызывается — проверено чтением
   полного списка импортов `weighing_report_cubit.dart`, в нём нет импорта
   `talker_flutter`/`Talker` вовсе.
6. `WeighingReportView.build`, `state.when(...)` реагирует на ветку
   `error: (msg) => Center(child: Text(msg, style: const TextStyle(color: AppColors.white)))` —
   на экране показывается сырой, нелокализованный текст исключения (например,
   `'Exception: db error'`), без заголовка, иконки или какого-либо пояснения
   пользователю; `CustomAppBar` (заголовок + дата) продолжает отображаться
   поверх (`body` подставляется независимо от состояния).
7. Единственный способ выйти из этого состояния — уйти со страницы (кнопка
   назад в `CustomAppBar`) и заново открыть отчёт из `ReportsDayListPopulated`,
   что создаёт новый `WeighingReportCubit` и заново вызывает `load` с теми же
   `args` — нет пути «повторить» без полной пересборки страницы.

### Альтернативные потоки

- **`catch (e)` — один блок на весь `try`, покрывает несколько независимых по
  происхождению точек.** Помимо самого первого чтения
  (`_animalsRepo.getAllAnimalsWithDetailsByFilters()`, протестированная
  точка), тот же `catch` перехватил бы исключение и из второго чтения
  (`_weighingsRepo.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds)`),
  и из цикла группировки (`accumByGroup`, `animal?.ageGroup?.name ??
  animal?.kind?.name`) — отличить в UI, какая именно часть `load` отказала,
  по тексту `e.toString()` невозможно.
- **Сообщение об ошибке не локализовано.** `e.toString()` попадает на экран
  напрямую, без прогона через `AppLocalizations`/`context.tr`.
- **Данные предыдущего успешного состояния не сохраняются.**
  `WeighingReportState` — `freezed`-union
  (`initial`/`loading`/`loaded`/`error`), переход в `error` полностью
  замещает предыдущее состояние; в текущем UI повторный вызов `load` после
  уже успешной загрузки не происходит (см. основной поток, шаг 2), поэтому
  эффект не наблюдаем на практике, но структурно возможен.
- **Ранний `return` при `animalIds.isEmpty` не затрагивает этот сценарий
  напрямую**, но делит `try` на две подобласти: если `getAllAnimalsWithDetailsByFilters()`
  успешно вернула пустой/полностью отфильтрованный по месту список, второе
  чтение (`_weighingsRepo...`) вообще не вызывается — точка сбоя этого
  сценария (шаг 4) обязана произойти строго до этого `return`, либо после
  него (во втором чтении/группировке), симметрично альтернативному потоку
  выше.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  целевая сущность чтения; при сбое ни одна запись не попадает в UI, даже
  если она физически существует в БД.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается первым
  шагом через `_animalsRepo.getAllAnimalsWithDetailsByFilters()`
  (`AnimalWithDetails`); используется для фильтрации по `placeId` и для
  группировки по `ageGroup?.name ?? kind?.name`; в этом сценарии это
  протестированная точка сбоя; не изменяется.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — поле `unitId` у `AnimalWeighing` не читается этим методом
  вовсе (в отличие от истории взвешиваний конкретного животного,
  `AnimalWeighingsCubit.load`) — группировка строится только по весу/имени
  группы, без единицы измерения; упомянуто здесь только потому, что связь
  формально существует у сущности ([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)),
  не потому, что участвует в этом сценарии.

### Бизнес-правила

- Технический сбой (исключение из чтения животных/взвешиваний или из
  группировки) классифицируется как `READ_ERROR`, а не `READ_REJECTED` —
  сценарий не содержит ни одного бизнес-guard'а, способного сознательно
  отклонить запрос: единственная фильтрация (место/день) — это `where` по
  уже прочитанным данным, пустой результат которой ведёт к `loaded` с
  `totalAnimals: 0`, а не к ошибке.
- Один и тот же `catch (e)` в `load` покрывает сбой обоих чтений
  (`getAllAnimalsWithDetailsByFilters`, затем
  `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`) и последующей
  группировки — реагирует на все три одинаково, без логирования и без
  ветвления по источнику.
- Ошибка не логируется никаким централизованным механизмом (`Talker` или
  иным) — единственный след сбоя — то, что попадает в
  `WeighingReportState.error` и рендерится пользователю.
- Переход в состояние ошибки необратим средствами самого экрана — нет ни
  кнопки повтора, ни автоматического ретрая; единственный способ повторить
  попытку — закрыть и заново открыть отчёт целиком.
- **Отчёт не фильтрует животных по ферме вовсе** —
  `_animalsRepo.getAllAnimalsWithDetailsByFilters()` вызывается без
  `farmId`, а `WeighingReportPageArgs` не имеет такого поля; единственный
  фильтр после чтения — по `placeId` (в памяти). Это отличается от
  вакцинационного отчёта того же модуля ([UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md)),
  который явно фильтрует по `v.animal.farmId == args.farmId`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных потока (общий `catch` на три
источника; отсутствие локализации сообщения) прослеживаются чтением
`lib/pages/weighing_report/cubit/weighing_report_cubit.dart`,
`lib/pages/weighing_report/cubit/weighing_report_state.dart`,
`lib/pages/weighing_report/presentation/widgets/weighing_report_view.dart`,
`lib/repositories/animal/animals_repository.dart`,
`lib/repositories/animal_weighing/animal_weighings_repository.dart` и
`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart`. Отсутствие
вызова логгера в `catch` перепроверено чтением полного списка импортов файла
кубита напрямую, а не восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/weighing_report/cubit/weighing_report_cubit.dart` | `WeighingReportCubit.load` | CURRENT | единственный `try/catch` сценария; `catch (e)` без стек-трейса и без логирования, эмитит `WeighingReportState.error(e.toString())` |
| `lib/pages/weighing_report/cubit/weighing_report_state.dart` | `WeighingReportState.error` | CURRENT | freezed-вариант состояния, несущий сырой текст исключения (`String message`, позиционный аргумент) |
| `lib/pages/weighing_report/data/weighing_report_data.dart` | `WeighingReportPageArgs` | CURRENT | аргументы (`date`/`placeId`/`placeName` — без `farmId`), передаваемые в `load` |
| `lib/pages/weighing_report/presentation/weighing_report_page.dart` | `WeighingReportPage.build` | CURRENT | тонкая обёртка, целиком делегирует рендер `WeighingReportView` |
| `lib/pages/weighing_report/presentation/widgets/weighing_report_view.dart` | `WeighingReportView.build` | CURRENT | вызывает `load` один раз в `create:`; `state.when(... error: ...)` рендерит `Center(child: Text(msg, ...))` без локализации и без действия «повторить»; заголовок/подзаголовок собраны напрямую в `Scaffold`+`CustomAppBar`, без `EventReportScaffold` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | источник исключения, протестированная (мокнутая) точка сбоя |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | реальная (немокнутая) реализация первого чтения |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | второе чтение внутри того же `try`; не протестированная напрямую как источник исключения в этом файле, но покрыта тем же `catch` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | реальная (немокнутая) реализация второго чтения |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` | CURRENT | точка входа — на `case WeighingDayItem(...)` вызывает `pushNamed2(Routes.weighingReport, extra: WeighingReportPageArgs(...))` |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildWeighingItems` | CURRENT | строит `WeighingDayItem`, источник `date`/`placeId`/`placeName` для аргументов экрана |
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit._buildGroupsByType`, `ReportsDayListCubit._buildGroupsByPlace` | CURRENT | оба места вызова `buildWeighingItems` — оба передают конкретный (не `null`) `placeId` |
| `lib/pages/routes.dart` | `Routes.weighingReport` | CURRENT | константа имени/пути маршрута |

## Критерии приёмки

- При исключении из `_animalsRepo.getAllAnimalsWithDetailsByFilters()`
  внутри `WeighingReportCubit.load` кубит эмитит ровно два состояния подряд:
  `WeighingReportState.loading()`, затем
  `WeighingReportState.error(e.toString())` — без промежуточного `loaded`.
- То же самое эмитируется при исключении из
  `_weighingsRepo.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` или из
  цикла группировки — один и тот же `catch` без ветвления по источнику.
- Сообщение состояния `error` — точный результат `e.toString()` брошенного
  исключения, без оборачивания/локализации/добавления контекста.
- Ни один логгер (`Talker` или иной) не вызывается при обработке исключения.
- `WeighingReportView` рендерит текст сообщения через
  `Center(child: Text(msg, ...))` под тем же `CustomAppBar` (заголовок/дата
  остаются видны).
- Повторный вызов `load` с теми же аргументами возможен только через полное
  пересоздание `WeighingReportCubit`/страницы (уход и повторный вход из
  `ReportsDayListPopulated`) — в самом экране нет элемента, инициирующего
  повтор.

## Связанные тесты

- `test/pages/weighing_report_cubit_test.dart`, group
  `'UC-98 — WeighingReportCubit.load'`, test
  `'ошибка репозитория -> error с текстом исключения'` — прямое покрытие:
  `animalsRepository.getAllAnimalsWithDetailsByFilters()` замокан на
  `thenThrow(Exception('db error'))`, после
  `cubit.load(WeighingReportPageArgs(date: DateTime(2026, 7, 16)))`
  проверяется через `cubit.state.when(...)`, что ветка `error` сработала и
  `message` содержит подстроку `'db error'` (остальные ветки `when`
  вызывают `fail(...)`, если бы сработали).
- Соседняя group `'UC-97 — WeighingReportCubit.load'` в том же файле
  покрывает `READ_OK`-исход того же метода (нет животных вообще; успешная
  группировка по kind; фильтрация по `placeId`), не документируемый здесь.
- **TBD — теста нет** на сбой, возникающий именно во втором чтении
  (`getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`) или внутри цикла
  группировки (а не в первом чтении животных) — существующий тест мокает
  исключение только на уровне `getAllAnimalsWithDetailsByFilters()`.
- **TBD — теста нет** на поведение `WeighingReportView` в состоянии `error`
  (рендер `Center(child: Text(...))`, отсутствие локализации, отсутствие
  действия «повторить») — ни одним widget-тестом (в `test/` нет файла для
  `weighing_report_view.dart`/`weighing_report_page.dart`); вывод сделан по
  чтению кода.

## Открытые вопросы и ограничения

- **В этом сценарии try/catch ЕСТЬ — в отличие от EVT-47/EVT-48 того же
  модуля, где его нет вовсе.** `WeighingReportCubit.load` явно ловит
  исключение и превращает его в наблюдаемое пользователем состояние
  `error`. Соседние read-сценарии взвешивания в том же модуле —
  `AnimalWeighingsCubit.load`
  ([EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md),
  `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`)
  и `AnimalWeighingsCubit.loadNotSync`
  ([EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md),
  тот же файл) — не содержат `try/catch` вообще (проверено чтением обоих
  методов целиком): любое исключение из их репозиторных вызовов
  (`getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
  `getAllNotSuncAnimalWeighings`, либо из вложенных вызовов
  `getAnimalWithDetailsById`/`getById` внутри цикла) распространяется дальше
  необработанным. Оба метода вызываются через каскад в `create:`
  (`AnimalWeighingsCubit()..load(animalId)` /
  `AnimalWeighingsCubit()..loadNotSync()`,
  `lib/pages/animal_weighings/pages/animal_weighings_page.dart`,
  `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart`) —
  без `await`, поэтому исключение там не пробрасывается синхронно в вызывающий
  код и не всплывает как `error`-состояние: экран просто остаётся в
  `AnimalWeighingsState.loading()` бесконечно (спиннер), а само исключение
  становится необработанным отклонением `Future`. Не исследовано в рамках
  этого файла, куда именно такое необработанное исключение попадает на
  практике (Zone/`FlutterError.onError` или полная тишина) — это относится к
  сценариям EVT-47/EVT-48, не к предмету этого файла.
- **Отсутствие логирования — осознанный выбор или недосмотр?**
  `WeighingReportCubit.load` ловит `catch (e)` без стек-трейса и не логирует
  его вовсе — при технической ошибке никакого следа сбоя, кроме того, что
  видит пользователь на экране, не остаётся нигде. Тот же паттерн
  повторяется и в соседних отчётах модуля (`VaccinationReportCubit`, см.
  [UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md);
  `MovementReportCubit`) — то есть это сквозной паттерн семейства
  day-report кубитов, не изолированная особенность одного файла; ничего в
  коде/комментариях не фиксирует, было ли это решение осознанным.
- **Отчёт не фильтрует по ферме.** `WeighingReportPageArgs` не несёт `farmId`,
  а `_animalsRepo.getAllAnimalsWithDetailsByFilters()` вызывается без него —
  не проверялось, является ли это осознанным продуктовым решением (в
  однофермерном контексте приложения `placeId` мог считаться достаточным
  идентификатором) или расхождением с намерением, задокументированным для
  вакцинационного отчёта того же модуля.
- **Ветка `args.placeId == null` в `WeighingReportCubit.load` недостижима
  из текущего UI**, по той же схеме, что и у вакцинационного отчёта
  ([UC-81](UC-81-ACTOR-5-EVT-41-ENT-14-READ_OK-IN-ANIMAL.md), «Открытые
  вопросы») — оба места построения `WeighingDayItem`
  (`ReportsDayListCubit._buildGroupsByType`/`._buildGroupsByPlace`) всегда
  передают конкретный `placeId`; фильтр `args.placeId == null || ...`
  формально существует в коде, но реального пути открыть этот отчёт без
  указания места сегодня нет.
- **Реальный (немокнутый) источник исключения в проде не отделён от
  тестового.** Тест использует произвольное `Exception('db error')` на
  уровне репозитория животных; какая конкретно операция внутри
  `AnimalsDao.getAllAnimalsWithDetailsByFilters` (или второго чтения —
  `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`)
  реалистичнее всего бросает исключение на практике — не исследовано в
  рамках этого сценария.
