# EVT-29 — movement.deleted_via_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет перемещение с экрана дневного отчёта — доступно только если экран открыт из хаба неотправленных (`isUnsent: true`); при открытии того же дня из общего календаря удаление не показывается. `MovementReportCubit.deleteEvent`.

**Эффект.** Повторно фильтрует все неотправленные записи по дню/месту отправления/месту назначения и удаляет их (`MovementReportRepository.delete`, тот же метод с откатом, что у [EVT-28](EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)) — отдельный, независимо написанный путь к тому же эффекту, не переиспользующий `deleteGroup`.

**Исходный код.** `lib/pages/movement_report/cubit/movement_report_cubit.dart` → `MovementReportCubit.deleteEvent`.
