# EVT-105 — movements.viewed_in_day_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает посуточный отчёт по перемещениям для
конкретных даты/мест отправления/назначения (из календаря событий или из хаба
неотправленных, с флагом `isUnsent`); `MovementReportCubit.load(args)`.

**Эффект.** Загружает **все** перемещения (`getMovementsWithDetailsByFilters(sync:
null)` — без фильтра по признаку отправки, в отличие от удаления в этом же
кубите, которое использует `sync: false`) и фильтрует в памяти по дню и паре
мест (`fromPlaceId`/`toPlaceId`); группирует по возрастной группе/виду
животного, собирает транспондерные номера для шапки отчёта.

**Исходный код.** `lib/pages/movement_report/cubit/movement_report_cubit.dart`
→ `MovementReportCubit.load`.
