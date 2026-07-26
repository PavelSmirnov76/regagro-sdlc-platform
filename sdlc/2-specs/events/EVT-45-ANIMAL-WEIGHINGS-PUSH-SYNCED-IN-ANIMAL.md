# EVT-45 — animal_weighings.push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки взвешиваний внутри `_syncAuthData` — после синхронизации ферм и мест (`_syncFarms`/`_syncPlaces`), но раньше остальных доменных шагов (`updateAndSyncRegagro`, куда входят перемещения/выбытия/вакцинации/животные); `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`.

**Эффект.** Все строки с `sync == false` отправляются одним батч-запросом (`POST .../weighing-event`) разом — без `id`/`remoteId` в теле, поэтому сервер не может отличить создание новой записи от повторной отправки отредактированной уже существующей (см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)). Успех (`response['status'] == "1"`) удаляет отправленные строки локально (не помечает `sync: true`); данные возвращаются позже, отдельным шагом полной перезагрузки животных ([EVT-46](EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md)).

**Исходный код.** `lib/repositories/animal_weighing/animal_weighings_repository.dart` → `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`; `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc._syncAuthData`.
