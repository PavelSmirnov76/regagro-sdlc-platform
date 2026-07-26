# EVT-41 — vaccinations.viewed_in_day_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает посуточный отчёт по вакцинации для конкретных фермы/места/дня (из календаря событий или из хаба неотправленных); `VaccinationReportCubit.load`.

**Эффект.** Загружает **все** вакцинации (не только неотправленные) и фильтрует в памяти по дню/ферме/месту; группирует по возрастной группе/виду животного, собирает чипы (вакцина/способ введения/доза/дата) для шапки отчёта.

**Исходный код.** `lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart` → `VaccinationReportCubit.load`.
