# EVT-30 — movement.push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки ещё не отправленных перемещений; `DataUpdateBloc`.

**Эффект.** Все неотправленные записи отправляются одним батч-запросом сразу (не по одной). Успех — `sync=true` для всего батча разом. Отказ или исключение пробрасывается наружу и прерывает весь sync-проход — ни одна запись батча не помечается синхронизированной, попытка повторится на следующем полном проходе целиком.

**Исходный код.** `lib/repositories/movement_report/movement_report_repository.dart` → `MovementReportRepository.sendMovementsToApi`.
