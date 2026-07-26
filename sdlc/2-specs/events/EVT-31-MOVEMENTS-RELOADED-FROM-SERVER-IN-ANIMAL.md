# EVT-31 — movements.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Sync-проход запрашивает актуальный список перемещений с сервера; `DataUpdateBloc`.

**Эффект.** Если сервер вернул непустой список — локальная таблица `Movements` полностью очищается и перезаписывается ответом, загруженные записи получают новый локальный id, серверный id — в `remoteId`, `sync=true` сразу. Пустой ответ не трогает локальные данные. Ошибка при получении только логируется — в отличие от push, не прерывает остальной sync-pipeline.

**Исходный код.** `lib/repositories/movement_report/movement_report_repository.dart` → `MovementReportRepository.getReportsFromApiAndSave`.
