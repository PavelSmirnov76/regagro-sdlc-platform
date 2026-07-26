# UC-82 — Посуточный отчёт по вакцинации отказывает технически: `VaccinationReportCubit.load` ловит исключение из чтения, эмитит `VaccinationReportState.error(e.toString())`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)
(`vaccinations.viewed_in_day_report`): пользователь открывает посуточный отчёт
по вакцинации для конкретных фермы/(места)/дня, но
`VaccinationReportCubit.load` (`lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart`)
ловит исключение, брошенное при попытке прочитать/сгруппировать вакцинации —
техническая ошибка (Drift/БД или иное исключение уровня данных), не бизнес-отказ
(здесь нет ни одного guard-условия, которое могло бы вернуть `REJECTED`: отчёт
либо строится по тому, что нашлось, либо технически падает). `catch (e)`
безусловно эмитит `VaccinationReportState.error(e.toString())` — сырой текст
исключения, без логирования и без стек-трейса.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart` целиком:
`VaccinationReportCubit` не объявляет и не использует `AuthRepository` ни в
одном методе, включая `load` — доступ к отчёту не зависит от статуса
авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает календарь событий, выбирает день — открывается
   `ReportsDayListPage` (`Routes.reportsDayList`), список дня строится через
   `lib/pages/reports_day_list/data/reports_day_data_loader.dart`, который
   среди прочего вызывает `_vaccinationsRepo.getVaccinationsWithDetails()` для
   построения `VaccinationDayItem`. Тап по такой карточке в
   `ReportsDayListPopulated` (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`)
   на `case VaccinationDayItem(...)` вызывает
   `context.pushNamed2(Routes.vaccinationReport, extra: VaccinationReportPageArgs(date: date, farmId: farmId, placeId: placeId, placeName: placeName))`.
2. `VaccinationReportPage.build` (`lib/pages/vaccination_report/presentation/vaccination_report_page.dart`)
   читает `VaccinationReportPageArgs` через
   `GoRouterState.of(context).getExtraByName<VaccinationReportPageArgs>(Routes.vaccinationReport)`
   и создаёт `BlocProvider(create: (context) => VaccinationReportCubit()..load(args), ...)` —
   `load` вызывается ровно один раз, синхронно со сборкой страницы; вызвать его
   повторно (retry) из этого экрана нечем — ни кнопки, ни `RefreshIndicator`
   в `EventReportScaffold`/`EventReportBody` (`lib/widgets/event_report/event_report_template.dart`)
   нет.
3. `VaccinationReportCubit.load` (`lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart`)
   сразу эмитит `VaccinationReportState.loading()`, затем входит в `try`:
   ```dart
   try {
     final day = DateUtils.dateOnly(args.date);
     final all = await _vaccinationsRepo.getVaccinationsWithDetails();
     final forDay = all.where((v) { ... }).toList();
     // группировка по возрастной группе/виду, сбор чипов
     emit(VaccinationReportState.loaded(...));
   } catch (e) {
     emit(VaccinationReportState.error(e.toString()));
   }
   ```
4. **Точка технического сбоя (этот сценарий).** `_vaccinationsRepo.getVaccinationsWithDetails()`
   (`lib/repositories/vaccination/vaccinations_repository.dart` →
   `VaccinationsRepository.getVaccinationsWithDetails`, делегирующая
   `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` →
   `VaccinationsDao.getVaccinationsWithDetails`) бросает исключение — в тесте
   (`test/pages/vaccination_report_cubit_test.dart`) через
   `when(() => repository.getVaccinationsWithDetails()).thenThrow(Exception('db error'))`,
   без мока конкретной внутренней причины (реальный код DAO — Drift-джойн по
   нескольким таблицам плюс по одному вложенному запросу
   `db.animalsDao.getAnimalWithDetailsById`/`calculateVaccinationStatus` на
   каждую строку — любой из них теоретически может отказать так же технически).
5. `catch (e)` без стек-трейса перехватывает исключение и эмитит
   `VaccinationReportState.error(e.toString())` — единственный аргумент
   error-варианта, `String message`
   (`lib/pages/vaccination_report/cubit/vaccination_report_state.dart`).
   Ни `Talker`, ни любой другой логгер здесь не вызывается — в отличие от,
   например, `VaccinationBloc._onSave` (`catch (e, st) { getIt<Talker>().handle(e, st); ... }`,
   см. [UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)),
   исключение здесь не логируется вовсе.
6. `VaccinationReportPage.build`, `state.when(...)` реагирует на ветку
   `error: (msg) => Center(child: Text(msg, style: const TextStyle(color: AppColors.white)))`
   (`lib/pages/vaccination_report/presentation/vaccination_report_page.dart`) —
   на экране показывается сырой, нелокализованный текст исключения
   (`e.toString()`, например `'Exception: db error'`), без заголовка, иконки
   или какого-либо пояснения пользователю; шапка `EventReportScaffold`
   (заголовок + дата) продолжает отображаться поверх (`body` подставляется
   независимо от состояния).
7. Единственный способ выйти из этого состояния — уйти со страницы (кнопка
   назад в `CustomAppBar` внутри `EventReportScaffold`) и заново открыть отчёт
   из `ReportsDayListPopulated`, что создаёт новый `VaccinationReportCubit` и
   заново вызывает `load` с теми же `args` — нет пути «повторить» без полной
   пересборки страницы.

### Альтернативные потоки

- **`catch (e)` — один блок на весь `try`, покрывает несколько независимых по
  происхождению точек.** Помимо самого чтения
  (`_vaccinationsRepo.getVaccinationsWithDetails()`, протестированная точка),
  тот же `catch` перехватил бы исключение и из цикла группировки (`byGroup`/
  `vaccineNames`/`methodNames`/`doseStr` — например, если `v.vaccine`,
  `v.animal.kind` или подобное поле неожиданно оказалось в состоянии,
  не предусмотренном текущими данными) — отличить в UI, какая именно часть
  `load` отказала, по тексту `e.toString()` невозможно.
- **Сообщение об ошибке не локализовано.** В отличие от, например,
  `VaccinationMessage('an_error_data')` в `VaccinationBloc`
  ([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)), которое
  резолвится через `AppLocalizations.tr` в переведённую строку, здесь на
  экран напрямую попадает `e.toString()` — техническая строка (например,
  `'Exception: db error'`), без прогона через `l10n`.
- **`totalAnimals`/`chips`/`groups` из предыдущего успешного состояния не
  сохраняются.** `VaccinationReportState` — `freezed`-union
  (`initial`/`loading`/`loaded`/`error`), переход в `error` полностью
  замещает предыдущее состояние — если бы `load` вызывался повторно после
  уже успешной загрузки (в текущем UI не происходит, см. шаг 2), пользователь
  потерял бы уже показанные данные, а не увидел бы их вместе с сообщением об
  ошибке.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  целевая сущность чтения; при сбое ни одна запись не попадает в UI (даже
  если часть строк была бы успешно прочитана до места сбоя внутри цикла
  DAO — `catch` в кубите не различает частичный и нулевой результат, весь
  список просто отбрасывается).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `VaccinationWithDetails.animal` (джойн внутри DAO), используется для
  фильтрации по `farmId`/`placeId` и для группировки по
  `ageGroup?.name ?? kind?.name`; не изменяется.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается через
  `v.animal.activeAnimalIdentifications.firstWhereOrNull(...)` для отображения
  номера транспондера (`Constants.TransponderMarkerTypeId`, `lib/constants.dart`)
  в каждой карточке животного группы; не изменяется.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit, HANDBOOKS) —
  читается через `v.unit?.name` при построении строки дозы (`doseStr`); не
  изменяется.
- `Vaccine`, `InjectionMethod` (VAC-локальные справочники, без собственного
  `ENT` — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) —
  читаются через `v.vaccine.name`/`v.injectionMethod?.name` для сбора чипов
  шапки отчёта; не изменяются.

### Бизнес-правила

- Технический сбой (исключение из чтения/группировки) классифицируется как
  `READ_ERROR`, а не `READ_REJECTED` — сценарий не содержит ни одного
  бизнес-guard'а, способного сознательно отклонить запрос: единственная
  фильтрация (день/ферма/место) — это `where` по уже прочитанным данным,
  пустой результат которой ведёт к `loaded` с `totalAnimals: 0`, а не к
  ошибке.
- Один и тот же `catch (e)` в `load` покрывает и сбой самого чтения
  (`getVaccinationsWithDetails`), и любой сбой в последующей группировке —
  реагирует на оба одинаково, без логирования и без ветвления по источнику.
- Ошибка не логируется никаким централизованным механизмом (`Talker` или
  иным) — единственный след сбоя — то, что попадает в `VaccinationReportState.error`
  и рендерится пользователю.
- Переход в состояние ошибки необратим средствами самого экрана — нет ни
  кнопки повтора, ни автоматического ретрая; единственный способ повторить
  попытку — закрыть и заново открыть отчёт целиком.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных потока (общий `catch` на несколько
источников; отсутствие локализации сообщения) прослеживаются чтением
`lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart`,
`lib/pages/vaccination_report/cubit/vaccination_report_state.dart`,
`lib/pages/vaccination_report/presentation/vaccination_report_page.dart`,
`lib/widgets/event_report/event_report_template.dart`,
`lib/repositories/vaccination/vaccinations_repository.dart` и
`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`.
Отсутствие вызова логгера в `catch` перепроверено чтением полного списка
импортов файла кубита напрямую, а не восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart` | `VaccinationReportCubit.load` | CURRENT | единственный `try/catch` сценария; `catch (e)` без стек-трейса и без логирования, эмитит `VaccinationReportState.error(e.toString())` |
| `lib/pages/vaccination_report/cubit/vaccination_report_state.dart` | `VaccinationReportState.error` | CURRENT | freezed-вариант состояния, несущий сырой текст исключения |
| `lib/pages/vaccination_report/data/vaccination_report_data.dart` | `VaccinationReportPageArgs` | CURRENT | аргументы (`date`/`farmId`/`placeId`/`placeName`), передаваемые в `load` |
| `lib/pages/vaccination_report/presentation/vaccination_report_page.dart` | `VaccinationReportPage.build` | CURRENT | вызывает `load` один раз в `create:`; `state.when(... error: ...)` рендерит `Center(child: Text(msg, ...))` без локализации и без действия «повторить» |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportScaffold` | CURRENT | общий каркас (заголовок/дата/`CustomAppBar`), под которым рендерится ветка ошибки; без `RefreshIndicator` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | источник исключения, протестированная (мокнутая) точка сбоя |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetails` | CURRENT | реальная (немокнутая) реализация чтения — джойны + по-строчные вложенные вызовы (`getAnimalWithDetailsById`, `calculateVaccinationStatus`), любой из которых теоретически может бросить исключение того же вида |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` | CURRENT | точка входа — на `case VaccinationDayItem(...)` вызывает `pushNamed2(Routes.vaccinationReport, extra: VaccinationReportPageArgs(...))` |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | тот же репозиторный метод (`_vaccinationsRepo.getVaccinationsWithDetails()`) читается ещё раз при построении самого дневного списка, до открытия отчёта |
| `lib/pages/routes.dart` | `Routes.vaccinationReport` | CURRENT | константа имени/пути маршрута |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId` | CURRENT | используется при построении номера транспондера внутри цикла группировки (альтернативный источник исключения) |

## Критерии приёмки

- При исключении из `_vaccinationsRepo.getVaccinationsWithDetails()` внутри
  `VaccinationReportCubit.load` кубит эмитит ровно два состояния подряд:
  `VaccinationReportState.loading()`, затем `VaccinationReportState.error(e.toString())` —
  без промежуточного `loaded`.
- То же самое эмитируется при исключении из любой другой части того же
  `try`-блока (группировка/сбор чипов) — один и тот же `catch` без
  ветвления по источнику.
- Сообщение состояния `error` — точный результат `e.toString()` брошенного
  исключения, без оборачивания/локализации/добавления контекста.
- Ни один логгер (`Talker` или иной) не вызывается при обработке исключения.
- `VaccinationReportPage` рендерит текст сообщения через `Center(child: Text(msg, ...))`
  под тем же `EventReportScaffold` (заголовок/дата остаются видны).
- Повторный вызов `load` с теми же аргументами возможен только через полное
  пересоздание `VaccinationReportCubit`/страницы (уход и повторный вход из
  `ReportsDayListPopulated`) — в самом экране нет элемента, инициирующего
  повтор.

## Связанные тесты

- `test/pages/vaccination_report_cubit_test.dart`, group
  `'UC-82 — VaccinationReportCubit.load'`, test
  `'ошибка репозитория -> error с текстом исключения'` — прямое покрытие:
  `repository.getVaccinationsWithDetails()` замокан на
  `thenThrow(Exception('db error'))`, после `cubit.load(VaccinationReportPageArgs(date: DateTime(2026, 7, 16), farmId: 1))`
  проверяется через `cubit.state.when(...)`, что ветка `error` сработала и
  `message` содержит подстроку `'db error'` (остальные ветки `when` вызывают
  `fail(...)`, если бы сработали).
- Соседняя group `'UC-81 — VaccinationReportCubit.load'` в том же файле
  покрывает `READ_OK`-исход того же метода (группировка по `kind`,
  фильтрация по дню/ферме/месту), не документируемый здесь.
- **TBD — теста нет** на сбой, возникающий именно внутри цикла
  группировки/сбора чипов (а не в самом вызове репозитория) — существующий
  тест мокает исключение только на уровне `getVaccinationsWithDetails()`.
- **TBD — теста нет** на поведение `VaccinationReportPage`/
  `EventReportScaffold` в состоянии `error` (рендер `Center(child: Text(...))`,
  отсутствие локализации, отсутствие действия «повторить») — ни одним
  widget-тестом (в `test/` нет файла для `vaccination_report_page.dart`);
  вывод сделан по чтению кода.

## Открытые вопросы и ограничения

- **Отсутствие логирования — осознанный выбор или недосмотр?** В отличие от
  `VaccinationBloc._onSave` ([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)),
  которое логирует исключение через `Talker.handle(e, st)` со стек-трейсом,
  `VaccinationReportCubit.load` ловит `catch (e)` без стек-трейса и не
  логирует его вовсе — при технической ошибке никакого следа сбоя, кроме
  того, что видит пользователь на экране, не остаётся нигде (ни в `Talker`,
  ни где-либо ещё). Тот же паттерн («catch без логирования») повторяется и в
  соседних отчётах (`WeighingReportCubit`, `MovementReportCubit` — проверено
  чтением `lib/pages/weighing_report/cubit/weighing_report_cubit.dart` и
  `lib/pages/movement_report/cubit/movement_report_cubit.dart`), то есть это
  не изолированная особенность одного файла, а сквозной паттерн семейства
  day-report кубитов; ничего в коде/комментариях не фиксирует, было ли это
  решение осознанным.
- **Нелокализованный текст ошибки — осознанное решение или недосмотр?**
  `e.toString()` попадает на экран напрямую, без прогона через
  `AppLocalizations`/`context.tr` — при смене локали приложения текст
  технической ошибки (например, `'Exception: db error'`) всё равно останется
  на исходном (обычно английском/техническом) языке.
- **Нет действия «повторить» на самом экране ошибки.** Пользователю доступен
  единственный выход — уйти со страницы и заново открыть отчёт из списка дня;
  является ли отсутствие retry-кнопки намеренным упрощением UI для этого
  редкого технического случая или недосмотром — не зафиксировано нигде в
  коде/комментариях.
- **Реальный (немокнутый) источник исключения в проде не отделён от
  тестового.** Тест использует произвольное `Exception('db error')` на
  уровне репозитория; какая конкретно операция внутри
  `VaccinationsDao.getVaccinationsWithDetails` (Drift-джойн, вложенный
  `getAnimalWithDetailsById`, `calculateVaccinationStatus`) реалистичнее
  всего бросает исключение на практике — не исследовано в рамках этого
  сценария.
