# EVT-49 — animal_weighings.viewed_in_day_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает посуточный отчёт по взвешиванию для места/дня (из календаря событий); `WeighingReportCubit.load`.

**Эффект.** Загружает животных места (или всех, если место не задано), затем их взвешивания, фильтрует в памяти по дню; группирует по виду животного, суммируя вес и количество на группу.

**Исходный код.** `lib/pages/weighing_report/cubit/weighing_report_cubit.dart` → `WeighingReportCubit.load`.
