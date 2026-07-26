# EVT-25 — animal.creation_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки локально созданных животных (`id < 0`) с заполненным `farmId`; `DataUpdateBloc`.

**Эффект.** Животное отправляется на сервер; при успехе локальный id заменяется на серверный, каскадно обновляются связанные идентификации (и по мере специфицирования — другие под-области). Животные без `farmId` пропускаются на этом шаге, не отправляются вовсе.

**Исходный код.** `lib/repositories/animal/animals_repository.dart` → `AnimalsRepository._syncLocalAnimalFarm`, `updateAnimalId`; `lib/blocs/data_update/data_update_bloc.dart` → шаг синхронизации локальных животных.
