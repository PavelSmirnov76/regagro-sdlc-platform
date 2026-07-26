# EVT-64 — animal_inventory.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Тот же sync-проход, сразу после
[EVT-63](EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md) (push, вне
зависимости от его исхода на уровне контента ответа) —
`DataUpdateBloc.updateAndSyncSHTP` → `loadShtp` →
`ReportAnimalsRepository.getReportsFromApi`.

**Эффект.** `GET /get-animal-exits` за окно «последний год — завтра»,
результат вставляется в `ReportAnimals` (`insertAll`). Локальный кэш к этому
моменту уже безусловно очищен предыдущим шагом
([EVT-63](EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md):
`_reportsRepository.clear()` вызывается **до** `loadShtp`, не после) — если
именно этот сетевой вызов (`getReportsFromApi`) бросит исключение, локальный
кэш `ReportAnimals` остаётся пустым (уже очищен, но не переpopulate) до
следующего успешного полного прохода; исключение всплывает до внешнего
`try/catch` `on<DataUpdateStartAll>` и валит весь sync-проход
(`DataUpdateFailure`).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc.loadShtp`; `lib/pages/report/report_animals_repository.dart` →
`ReportAnimalsRepository.getReportsFromApi`, `_fromJson`.
