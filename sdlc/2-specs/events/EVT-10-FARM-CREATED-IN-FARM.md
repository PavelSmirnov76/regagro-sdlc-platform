# EVT-10 — farm.created

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Пользователь заполняет название и адрес (геопоиск либо метка на карте) в мастере создания фермы и подтверждает; `FarmCreateCubit.saveFarm`.

**Эффект.** `FarmRepository.insertFarmWithNegativeRemoteId` — ферма сохраняется локально с отрицательным `remoteId`, без ожидания сервера. На этом же шаге (для первой фермы пользователя) можно настроить видимость видов животных — отдельная сущность ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)), не часть этой сущности.

**Исходный код.** `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` → `FarmCreateCubit.saveFarm`; `lib/repositories/farm_repository/farm_repository.dart` → `FarmRepository.insertFarmWithNegativeRemoteId`.
