# EVT-11 — farm.edited

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Пользователь открывает уже существующую ферму на редактирование (название/адрес) и сохраняет; `FarmsAndPlacesBloc.on<FarmsPageEventEditFarm>`.

**Эффект.** Локальная запись обновляется, для уже синхронизированной фермы (`remoteId != null`) взводится `needUpdate: true` — правка попадёт на сервер только на следующем sync-проходе, не немедленно.

**Исходный код.** `lib/pages/farms_and_places/farms_page_bloc.dart` → `FarmsAndPlacesBloc._onEditFarm`.
