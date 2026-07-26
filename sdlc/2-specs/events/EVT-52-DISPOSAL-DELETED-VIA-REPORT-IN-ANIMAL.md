# EVT-52 — disposal.deleted_via_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет выбытие с экрана дневного отчёта — доступно только если экран открыт из хаба неотправленных (`isUnsent: true`); `DisposalReportCubit.deleteEvent`. Тот же паттерн двух независимо написанных путей к одному эффекту, что и у Movement ([EVT-28](EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)/[EVT-29](EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md)).

**Эффект.** Повторно фильтрует все неотправленные записи по дню/точному времени (с точностью до минуты)/месту/причине и удаляет совпавшие (`DisposalRepository.delete`, тот же метод, что у [EVT-51](EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)) — отдельный, независимо написанный путь к тому же эффекту, не переиспользующий `deleteGroup`.

**Исходный код.** `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` → `DisposalReportCubit.deleteEvent`.
