# EVT-63 — animal_inventory.push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки готовых к отправке сессий
инвентаризации; `DataUpdateBloc.updateAndSyncSHTP` → все строки с
`readyToSend == true` (`getAllReadyToSend`, не только инвентаризация —
общий метод для всех `way_type`) одним batch-запросом →
`UnsentReportAnimalsRepository.sync`.

**Эффект.** `POST /exit-event` с телом, где `animal_id` резолвится на
клиенте по совпадению `transponderId` с активной идентификацией животного
(если найдена). **Ответ сервера не проверяется** (`sync()` только логирует
его) — сразу после вызова, независимо от содержимого ответа,
`updateAndSyncSHTP` безусловно чистит локальный кэш `ReportAnimals`
(`_reportsRepository.clear()`) и удаляет все `readyToSend == true` строки
(`deleteAllReadyToSend()`). Сетевое исключение (не логический отказ) —
единственный путь, прерывающий это раньше, см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc.updateAndSyncSHTP`; `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` →
`UnsentReportAnimalsRepository.sync`, `getAllReadyToSend`, `deleteAllReadyToSend`.
