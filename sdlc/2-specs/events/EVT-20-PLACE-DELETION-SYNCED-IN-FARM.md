# EVT-20 — place.deletion_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Sync-проход доходит до отправки удалённых мест; `DataUpdateBloc._deletePlacesFromRDS`.

**Эффект.** `PlaceRepository.getAllToDelete()` берёт все локально помеченные `isDeleted: true` места (`res`); из них только с валидным неотрицательным `idRemote` идут одним батч-запросом (`ids: [...]`) в `deletePlacesOnRDS`. Если сервер вернул общий успех по батчу — локально удаляется весь исходный набор `res` целиком, включая записи, которые не попали в сам сетевой вызов (например ещё не синхронизированные). Если сервер вернул отказ по батчу — локально не удаляется ничего из `res`, попытка повторится на следующем sync-проходе.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._deletePlacesFromRDS`; `lib/repositories/place_repository/place_repository.dart` → `PlaceRepository.getAllToDelete`, `deletePlacesOnRDS`.
