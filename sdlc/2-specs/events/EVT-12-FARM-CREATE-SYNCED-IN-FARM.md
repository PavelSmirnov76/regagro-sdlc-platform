# EVT-12 — farm.create_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Sync-проход доходит до отправки ферм без серверного id; `DataUpdateBloc._storeFarmsToRDS`.

**Эффект.** `FarmRepository.storeFarmsOnRDS` отправляет фермы без `remoteId` по одной, в цикле. Успех по каждой — локальный `remoteId` заменяется на серверный, каскадно обновляются связанные места и животные (см. будущую спеку ANIMAL).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._storeFarmsToRDS`; `lib/repositories/farm_repository/farm_repository.dart` → `FarmRepository.storeFarmsOnRDS`, `getAllWithoutRemoteId`.
