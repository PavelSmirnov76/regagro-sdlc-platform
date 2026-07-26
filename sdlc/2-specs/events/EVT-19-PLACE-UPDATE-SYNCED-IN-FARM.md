# EVT-19 — place.update_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Sync-проход доходит до отправки правок мест, помеченных `needUpdate: true`; `DataUpdateBloc._updatePlacesOnRDS`.

**Эффект.** `PlaceRepository.updatePlacesOnRDS` отправляет помеченные места на сервер, сбрасывает `needUpdate` при успехе.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._updatePlacesOnRDS`; `lib/repositories/place_repository/place_repository.dart` → `PlaceRepository.updatePlacesOnRDS`, `getAllToUpdate`.
