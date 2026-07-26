# EVT-21 — places.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Sync-проход запрашивает актуальный список мест с сервера; `DataUpdateBloc._loadPlacesFromRDS`.

**Эффект.** `PlaceRepository.getAllPlacesFromRDS` — если сервер вернул непустой список, локальная таблица мест полностью очищается и перезаписывается ответом; при пустом ответе локальные данные не трогаются.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._loadPlacesFromRDS`; `lib/repositories/place_repository/place_repository.dart` → `PlaceRepository.getAllPlacesFromRDS`.
