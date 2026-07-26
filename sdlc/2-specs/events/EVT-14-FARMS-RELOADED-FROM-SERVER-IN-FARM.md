# EVT-14 — farms.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Sync-проход запрашивает актуальный список ферм с сервера; `DataUpdateBloc._loadFarmsFromRDS`.

**Эффект.** `FarmRepository.getAllFarmsFromRDS` — если сервер вернул непустой список, локальная таблица ферм полностью очищается и перезаписывается ответом; при пустом ответе локальные данные не трогаются.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._loadFarmsFromRDS`; `lib/repositories/farm_repository/farm_repository.dart` → `FarmRepository.getAllFarmsFromRDS`.
