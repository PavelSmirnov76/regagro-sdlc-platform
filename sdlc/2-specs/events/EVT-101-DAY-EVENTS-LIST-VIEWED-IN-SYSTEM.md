# EVT-101 — day_events_list.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) |

**Триггер.** Пользователь тапает по дню с событиями в календаре
([EVT-99](EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)) — промежуточный
экран-контейнер между месячным календарём и уже специфицированными
посуточными отчётами по каждому типу в `ANIMAL`. Два варианта: место
задано — `Routes.reportsDayList`, `ReportsDayListCubit.load(date, farm,
place)`; ферма целиком — `Routes.farmDayList`, `FarmDayListCubit.load(date,
farm)`. Ранее не специфицировался ни в одном модуле — обнаружен при
специфицировании контейнера календаря, не совпадает ни с одним из уже
описанных per-type Cubit'ов посуточных отчётов (`WeighingReportCubit` и
т.д.).

**Эффект.** `ReportsDayListCubit` (уровень места): группирует события дня
по **типу** (`movement/disposal/inventory/weighing/vaccination/registration`,
через `ReportsDayQuery.build*Items`), либо, если место не задано,
`_buildGroupsByPlace` — группирует по **месту** внутри фермы, все типы
одного места в одном плоском списке. `FarmDayListCubit` (уровень фермы,
всегда с заданной фермой) — группирует только по **месту**
(`FarmDayPlaceGroup`), без деления по типу внутри места. Тап по элементу
списка переводит на уже специфицированный посуточный отчёт своего типа
(`Routes.movementReport`/`weighingReport`/`disposalReport`/`vaccinationReport`/
`inventoryReport` — все пять читают из `_navigateItem` и передают уже
загруженные здесь `date`/`placeId`/и т.д. дальше). Тап по элементу типа
«регистрация» (`RegistrationDayItem`) — исключение: `Routes.registrationDayReport`
ведёт на `RegistrationDayReportPage`, чистый `StatelessWidget` без
собственного Cubit/загрузки — просто отображает уже загруженный здесь
список `animals`, переданный через `RegistrationDayReportPageArgs`; в
отличие от остальных пяти типов, у регистрации нет собственного
специфицированного (или вообще существующего) Cubit с состоянием
успех/ошибка — вся ответственность за загрузку и обработку ошибок для
этого типа лежит целиком на этом событии, не на отдельном экране.

**Исходный код.** `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` →
`ReportsDayListCubit.load`, `_buildGroupsByType`, `_buildGroupsByPlace`;
`lib/pages/reports_day_list/cubit/farm_day_list_cubit.dart` →
`FarmDayListCubit.load`; `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` →
`_navigateItem`; `lib/pages/registration_day_report/presentation/registration_day_report_page.dart` →
`RegistrationDayReportPage` (чистый passthrough).
