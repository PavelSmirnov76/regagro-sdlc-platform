# EVT-26 — animal.edit_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки животных, помеченных `needsUpdate: true` (см. [EVT-24](EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)); `DataUpdateBloc`.

**Эффект.** Правка отправляется на сервер (`updateAnimal`); при успехе `needsUpdate` и `errors` сбрасываются локально; при отказе или исключении текст ошибки записывается в поле `errors` животного вместо повторной отправки в этом же проходе.

**Исходный код.** `lib/repositories/animal/animals_repository.dart` → `AnimalsRepository.updateAnimal`; `lib/blocs/data_update/data_update_bloc.dart` → шаг синхронизации отложенных правок.
