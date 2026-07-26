# EVT-46 — animal_weighings.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до полной перезагрузки животных (`DataUpdateBloc.loadAnimals`) — отдельный, более поздний шаг того же прохода, чем push взвешиваний ([EVT-45](EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)).

**Эффект.** `AnimalWeighingsRepository.clearSync()` удаляет все локальные строки с `sync == true`; следом `AnimalsRepository.syncAllAnimals()` заново вставляет батчем все взвешивания, вложенные в ответ сервера по каждому животному (`sync: true`, `remoteId` — серверный id). Ошибка на этом шаге пробрасывается наружу (`rethrow`) и прерывает весь sync-проход — эффект не ограничен только взвешиваниями, тот же шаг перезагружает и самих животных, и их идентификации.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` → `DataUpdateBloc.loadAnimals`; `lib/repositories/animal_weighing/animal_weighings_repository.dart` → `AnimalWeighingsRepository.clearSync`; `lib/repositories/animal/animals_repository.dart` → `AnimalsRepository.syncAllAnimals`.
