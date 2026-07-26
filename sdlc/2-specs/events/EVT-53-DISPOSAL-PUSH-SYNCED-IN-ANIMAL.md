# EVT-53 — disposal.push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до отправки ещё не отправленных выбытий; `DisposalRepository.sendDisposalsToApi`, вызывается из `syncDisposals`.

**Эффект.** Неотправленные записи группируются по причине/месту отправления/целевому месту/минуте времени (`_groupForSend`) и отправляются по одному батч-запросу на группу; успех каждой группы помечает её строки `sync=true`. Исключение логируется и **пробрасывается наружу** (`rethrow`) — в отличие от VAC/WEIGH (где push-исключение глотается), здесь отказ прерывает `syncDisposals` целиком, и следующий шаг ([EVT-54](EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md)) в этом проходе не выполняется.

**Исходный код.** `lib/repositories/disposal/disposal_repository.dart` → `DisposalRepository.sendDisposalsToApi`, `_groupForSend`, `sendDisposalList`.
