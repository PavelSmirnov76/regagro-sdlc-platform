# EVT-65 — animal_inventory.viewed_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает хаб «В работе» → плитка «Инвентаризация»
(счётчик `data.inventoryCount`) → `Routes.unsentInventories` →
`UnsentInventoriesCubit.load`.

**Эффект.** Загружает все `readyToSend == true` строки `UnsentReportAnimals`
типа `inventory`, группирует по `sessionUuid` в одну карточку на сессию
(место, ферма, дата+время, суммарный счётчик голов); строки без
`sessionUuid` (легаси, встречается только в тестовых фикстурах) и строки
без `farmId`/`placeId` пропускаются целиком (`continue`), как и сессии, чья
ферма не резолвится по id.

**Исходный код.** `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` →
`UnsentInventoriesCubit.load`; `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` →
`UnsentReportAnimalsRepository.getInventoryReadySessions`.
