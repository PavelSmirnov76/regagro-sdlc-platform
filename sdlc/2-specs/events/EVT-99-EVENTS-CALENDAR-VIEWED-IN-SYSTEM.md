# EVT-99 — events_calendar.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) |

**Триггер.** Пользователь открывает календарь событий фермы/места
(`Routes.reportsCalendar`) — `ReportsCalendarCubit.load(farm, place, month)`.
Только сам контейнер (месячный вид) — посуточное содержимое конкретного дня
уже специфицировано по 6 типам в `ANIMAL` (`CalendarReportType`: disposal,
movement, inventory, weighing, registration, vaccination).

**Эффект.** Первая загрузка (или смена фермы/места) грузит все сырые данные
фермы разом (`ReportsDayDataLoader.load(farmId)` — 7 репозиториев) и строит
дни месяца; смена месяца/режима отображения (`compact`/`detailed`) переиспользует
кэш без повторной загрузки. Дни без событий не кликабельны; тап по дню с
событиями открывает посуточный список (`Routes.farmDayList`/`Routes.reportsDayList`,
в зависимости от того, открыт ли календарь всей фермы или конкретного
места) — уже специфицированные read-события ANIMAL.

**Исходный код.** `lib/pages/reports_calendar/cubit/reports_calendar_cubit.dart` →
`ReportsCalendarCubit.load`, `changeMonth`, `setViewMode`;
`lib/pages/reports_day_list/data/reports_day_data_loader.dart` →
`ReportsDayDataLoader.load`; `lib/pages/reports_calendar/presentation/widgets/reports_calendar_populated.dart` →
`_onDayTap`.
