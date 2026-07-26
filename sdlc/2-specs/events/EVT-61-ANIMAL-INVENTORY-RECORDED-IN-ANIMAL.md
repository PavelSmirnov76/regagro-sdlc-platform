# EVT-61 — animal_inventory.recorded

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Пользователь проходит визард инвентаризации (место → тип
сканера → сканирование, шаги места/типа пропускаются, если они уже заданы
или единственны), сканирует метки на месте содержания, подтверждает —
`ScanningPage`/`InventoryScanStepPage` → `ScanningBloc.on<ScanningEventSave>`.
Каждый скан по ходу уже персистится черновиком отдельно (см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md), не отдельное
событие) — это событие про **завершение** сессии, не про отдельный скан.

**Эффект.** Строки `UnsentReportAnimals` текущей сессии (`sessionUuid`)
нормализуются по времени (все — к минимальному времени сессии) и
помечаются `readyToSend = true` (`markSessionReadyToSendByUuid`). Смена
места посреди ещё не завершённой сессии обнуляет накопленные сканы и заводит
новый `sessionUuid` — см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

**Исходный код.** `lib/pages/scanning/scanning_bloc.dart` →
`ScanningBloc.on<ScanningEventSave>`, `_markSessionReadyToSend`; `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` →
`UnsentReportAnimalsRepository.markSessionReadyToSendByUuid`.
