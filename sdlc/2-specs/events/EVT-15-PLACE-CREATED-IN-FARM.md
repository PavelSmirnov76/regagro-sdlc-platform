# EVT-15 — place.created

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Пользователь добавляет отделение (при первой настройке структуры фермы — из предложенного стандартного набора, либо вручную в любой момент); `PlaceCreateCubit.addCustomPlace`/`FarmsAndPlacesBloc.on<FarmsPageEventAddPlace>`.

**Эффект.** `PlaceRepository.insertPlaceWithNegativeRemoteId` — место сохраняется локально с отрицательным `idRemote`, без ожидания сервера.

**Исходный код.** `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart` → `PlaceCreateCubit.addCustomPlace`, `_initializePlaces`; `lib/pages/farms_and_places/farms_page_bloc.dart` → `FarmsAndPlacesBloc._onAddPlace`; `lib/repositories/place_repository/place_repository.dart` → `PlaceRepository.insertPlaceWithNegativeRemoteId`.
