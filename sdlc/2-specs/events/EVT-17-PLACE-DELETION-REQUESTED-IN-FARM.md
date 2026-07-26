# EVT-17 — place.deletion_requested

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Пользователь удаляет отделение — из мастера настройки структуры (`PlaceCreateCubit.removePlace`) либо с экрана фермы; `FarmsAndPlacesBloc.on<FarmsPageEventDeletePlace>`.

**Эффект.** Перед удалением проверяется, что на месте не осталось закреплённых животных — если есть, удаление отклоняется с сообщением на клиенте, до какого-либо изменения данных. Если животных нет: для уже синхронизированного места (`idRemote != null`) — мягкое `isDeleted: true`; для ещё не синхронизированного — прямое физическое удаление локальной строки.

**Исходный код.** `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart` → `PlaceCreateCubit.removePlace`; `lib/pages/farms_and_places/farms_page_bloc.dart` → `FarmsAndPlacesBloc._onDeletePlace`.
