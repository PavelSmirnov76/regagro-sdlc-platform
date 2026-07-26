# EVT-18 — place.create_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Sync-проход доходит до отправки мест без серверного id; `DataUpdateBloc._storePlacesToRDS`.

**Эффект.** `PlaceRepository.storePlacesOnRDS` отправляет места без `idRemote`, получает серверные id; каскадно обновляются связанные животные (`AnimalsRepository.updatePlaceId`).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._storePlacesToRDS`; `lib/repositories/place_repository/place_repository.dart` → `PlaceRepository.storePlacesOnRDS`, `getAllWithoutRemoteId`.
