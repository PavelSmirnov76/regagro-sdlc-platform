# EVT-54 — disposals.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Sync-проход запрашивает список выбытий за последний год (либо с явно заданной даты) с сервера — второй шаг `syncDisposals`, выполняется только если предыдущий push-шаг ([EVT-53](EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md)) не бросил исключение.

**Эффект.** Локальная таблица `Disposals` полностью очищается и перезаписывается ответом сервера, но только если ответ непустой — тот же паттерн, что у Movement ([EVT-31](EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md)), в отличие от Vaccination/AnimalWeighing (там `clear()` безусловен). `placeId`/`toPlaceId` берутся из полей ответа `from_place_id`/`to_place_id`, а не пересчитываются из текущего места животного.

**Исходный код.** `lib/repositories/disposal/disposal_repository.dart` → `DisposalRepository.getReportsFromApiAndSave`.
