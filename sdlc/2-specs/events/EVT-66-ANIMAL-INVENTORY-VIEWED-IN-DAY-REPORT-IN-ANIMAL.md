# EVT-66 — animal_inventory.viewed_in_day_report

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Два равнозначных входа на один и тот же экран
(`InventoryReportDetailsPage`/`InventoryReportDetailsCubit.load`): (а)
пользователь только что завершил сессию сканирования (`ScanningExit`,
`type.type == 'inventory'`) — экран открывается автоматически сразу после
[EVT-61](EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)/[EVT-62](EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md);
(б) пользователь открывает посуточный отчёт по инвентаризации места из
календаря отчётов (`reports_day_list` → `InventoryDayItem`).

**Эффект.** Загружает отчёты по дате (`getInventoryReportsByDate`) либо по
`sessionUuid` (`getInventoryReportsByUuid`, объединяя ещё не отправленные и
уже подтверждённые сервером строки), сопоставляет с
`AnimalIdentification`/`AnimalWithDetails` **без ограничения по ферме** (в
отличие от живого сканирования, см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)) и строит 4
секции: учтено (по возрастной группе/виду), отсутствует, чужие метки
(известное животное с другого места/фермы), неизвестные номера.

**Исходный код.** `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` →
`InventoryReportDetailsCubit.load`; `lib/pages/animals_inventory/presentation/inventory_report_details_view.dart` →
`_computeSections`; `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` →
`getInventoryReportsByDate`, `getInventoryReportsByUuid`; `lib/pages/report/report_animals_repository.dart` →
`getInventoryReportsByDate`, `getInventoryReportsByUuid`.
