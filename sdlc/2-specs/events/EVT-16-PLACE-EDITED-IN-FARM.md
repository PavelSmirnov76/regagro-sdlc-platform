# EVT-16 — place.edited

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Пользователь меняет название или площадь (поле `description`) существующего отделения; `FarmsAndPlacesBloc.on<FarmsPageEventEditPlace>`/`PlaceCreateCubit.updatePlaceDescription`.

**Эффект.** Локальная запись обновляется; для уже синхронизированного места взводится `needUpdate: true`.

**Исходный код.** `lib/pages/farms_and_places/farms_page_bloc.dart` → `FarmsAndPlacesBloc._onEditPlace`; `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart` → `PlaceCreateCubit.updatePlaceDescription`, `updateCustomPlaceName`.
