# EVT-56 — disposals.viewed_in_day_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает посуточный отчёт по выбытию для конкретных места/причины/дня (из календаря событий или из хаба неотправленных); `DisposalReportCubit.load`.

**Эффект.** Фильтрует по дню и точному времени (с точностью до минуты, не только до дня); группирует по возрастной группе/виду животного.

**Исходный код.** `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` → `DisposalReportCubit.load`.
