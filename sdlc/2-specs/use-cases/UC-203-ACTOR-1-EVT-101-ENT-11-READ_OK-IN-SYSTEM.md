# UC-203 — Пользователь открывает посуточный список событий (промежуточный экран между календарём и отчётом по типу)

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Пользователь тапает по дню с событиями в календаре
([EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)) и попадает
на промежуточный экран-контейнер, группирующий все события этого дня, до
того как выбрать конкретный тип/место и провалиться в уже
специфицированный посуточный отчёт этого типа (`ANIMAL`). Два варианта в
зависимости от уровня, на котором был открыт календарь:

- **Уровень места** (`Routes.reportsDayList`, `ReportsDayListCubit.load(date,
  farm, place)`) — если `place` задан, группирует по **типу** события
  (движение/выбытие/инвентаризация/взвешивание/вакцинация/регистрация);
  если `place` не задан (открыт с уровня фермы, но без конкретного места) —
  группирует по **месту**, все типы одного места одним плоским списком.
- **Уровень фермы** (`Routes.farmDayList`, `FarmDayListCubit.load(date,
  farm)`) — всегда группирует по **месту** внутри фермы, без деления по
  типу.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
уже открывший календарь ([EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md))
для конкретной фермы (и, опционально, места).

## CURRENT

### Основной поток

1. `ReportsCalendarPopulated._onDayTap` (уже специфицирован в
   [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)) переводит
   на `Routes.reportsDayList` (уровень места) либо `Routes.farmDayList`
   (уровень фермы), передавая `date`/`farm`/(опционально)`place`.
2. **Ветка «место задано»** — `ReportsDayListCubit.load(date:, farm:,
   place:)`: `emit(loading)` → `farmId = farm?.farm.remoteId ?? place?.place.farmId
   ?? 0` → `rawData = await _dataLoader.load(farmId: farmId)`
   (`ReportsDayDataLoader` — те же 7 репозиториев, что уже используются
   календарём, `Future.wait`) → `_buildGroupsByType`: для каждого из 6 типов
   вызывает `ReportsDayQuery.build*Items(rawData, day, placeId, ...)`,
   добавляет группу (`ReportDayGroup`, с `accentColor`/`count`/`reportType`),
   только если список непуст → `emit(loaded(date, groups, farm, place))`.
3. **Ветка «место не задано»** (`ReportsDayListCubit`, `_buildGroupsByPlace`) —
   для каждого места фермы строит один плоский список
   (`flatItems`, все 6 типов вперемешку), группа — одна на место
   (`title: placeName`), если список непуст.
4. **`FarmDayListCubit.load(date:, farm:)`** (уровень фермы) — тот же
   `_dataLoader.load(farmId:)`, но группирует иначе:
   `ReportsDayQuery.entriesForPlace(rawData, day, pid)` для каждого места
   фермы — `FarmDayPlaceGroup(place:, entries:)`, тоже только если непусто.
5. `ReportsDayListPopulated`/аналог для фермы — рендерит список групп,
   `ListView.separated`; тап по элементу (`_navigateItem`, `switch` по
   типу `ReportDayItem`) переводит на уже специфицированный посуточный
   отчёт своего типа: `Routes.movementReport`/`weighingReport`/
   `disposalReport`/`vaccinationReport`/`inventoryReport` — каждый получает
   уже вычисленные здесь `date`/`placeId`/`farmId`/и т.д.
6. **Исключение — тип «регистрация».** `RegistrationDayItem` →
   `Routes.registrationDayReport` → `RegistrationDayReportPage` — чистый
   `StatelessWidget`, без собственного Cubit, без своей загрузки/состояния
   ошибки: просто рендерит `animals`, уже вычисленный здесь
   (`ReportsDayQuery.buildRegistrationItem`) и переданный через
   `RegistrationDayReportPageArgs`. В отличие от остальных пяти типов,
   у регистрации нет отдельного специфицированного Cubit с состояниями
   успех/ошибка — вся ответственность за загрузку/агрегацию для этого типа
   лежит на этом же `load()`.

### Альтернативные потоки

- Пустой день (все 6 запросов вернули пусто для всех мест/типов) —
  `loaded` с пустым списком групп; UI показывает `AppLocalizations.of(context)!.no_data`.
- Ферма без мест (`farm.placesWithAnimals` пуст) — оба cubit'а
  соответственно возвращают пустой список групп, тот же `no_data`.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сегмент `ENT`
  этого use-case; сами данные приходят из `ReportsDayDataLoader`, который
  читает Animal/Movement/Disposal/AnimalWeighing/Vaccination/InventoryScanReport —
  уже специфицированные сущности `ANIMAL`, здесь только агрегируются для
  отображения, не изменяются.

### Бизнес-правила

- Группа/элемент добавляется в список, только если для него нашлась хотя
  бы одна запись за этот день — пустые типы/места не показываются вовсе (не
  как "0 записей", а как отсутствующая строка).
- `ReportsDayListCubit` и `FarmDayListCubit` — два независимых класса с
  дублирующей структурой (`load`, `try/catch`, `_dataLoader.load(farmId:)`),
  различающихся только логикой группировки — не общий базовый класс.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit.load`, `_buildGroupsByType`, `_buildGroupsByPlace` | CURRENT | загрузка/группировка, уровень места |
| `lib/pages/reports_day_list/cubit/farm_day_list_cubit.dart` | `FarmDayListCubit.load` | CURRENT | загрузка/группировка, уровень фермы |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | общий загрузчик сырых данных (используется и календарём) |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.build*Items`, `entriesForPlace` | CURRENT | построение элементов по типу/месту |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` | CURRENT | переход на посуточный отчёт по типу |
| `lib/pages/registration_day_report/presentation/registration_day_report_page.dart` | `RegistrationDayReportPage` | CURRENT | чистый passthrough для типа «регистрация» |

## Критерии приёмки

- `ReportsDayListCubit.load`/`FarmDayListCubit.load` эмитят `loading`, затем
  `loaded` с группами, построенными из `ReportsDayDataLoader.load(farmId:)`.
- Группа/элемент отсутствует в списке, если для него нет записей за день.
- Тап по элементу любого из пяти типов, кроме регистрации, переводит на уже
  специфицированный посуточный отчёт этого типа с корректными параметрами.
- Тап по элементу «регистрация» переводит на чистый passthrough-экран без
  собственной загрузки.

## Связанные тесты

- `test/pages/reports_day_list_cubit_test.dart`, группы `'UC-203 — ReportsDayListCubit.load,
  уровень места (place задан)'`, `'UC-203 — ReportsDayListCubit.load,
  уровень фермы (place не задан)'`, `'UC-203 — ReportsDayListCubit.load,
  разрешение farmId/placeId и нормализация даты'` (три группы, ранее носившие
  общий старый id `UC-303`, переименованы в рамках этого же прохода).
- `test/pages/farm_day_list_cubit_test.dart`, группа `'UC-203 —
  FarmDayListCubit.load'` (ранее `UC-301`, переименована в рамках этого же
  прохода).

## Открытые вопросы и ограничения

- `RegistrationDayReportPage` — единственный из шести типов без
  собственного специфицированного Cubit; его отсутствие ошибки
  задокументировано как структурная особенность в
  [EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md), не
  разбирается отдельным use-case, т.к. у экрана нет собственной логики,
  которая могла бы отказать.
