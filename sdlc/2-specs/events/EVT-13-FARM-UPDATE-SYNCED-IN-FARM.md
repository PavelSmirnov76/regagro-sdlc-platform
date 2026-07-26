# EVT-13 — farm.update_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Sync-проход доходит до отправки правок ферм, помеченных `needUpdate: true`; `DataUpdateBloc._updateFarmsOnRDS`.

**Эффект.** `FarmRepository.updateFarmsOnRDS` отправляет каждую помеченную ферму отдельным запросом. Успех сбрасывает `needUpdate`; отказ на любой ферме останавливает весь цикл (`break`, не `continue`) — частичный успех при обновлении не поддерживается, в отличие от создания.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._updateFarmsOnRDS`; `lib/repositories/farm_repository/farm_repository.dart` → `FarmRepository.updateFarmsOnRDS`, `getAllToUpdate`.
