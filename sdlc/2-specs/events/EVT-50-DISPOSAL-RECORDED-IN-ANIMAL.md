# EVT-50 — disposal.recorded

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Пользователь проходит визард выбытия (место → причина → [если причина «между фермами одного владельца», id `4`] целевая ферма → целевое место → животные), подтверждает; `AnimalDisposalBloc.on<AnimalDisposalEventSave>`.

**Эффект.** По одной записи `Disposal` на каждое выбранное животное, `sync=false`; для сценария «между фермами» дополнительно заполняются `toId`/`toPlaceId`. Животное НЕ помечается выбывшим локально — это отдельный, более поздний факт (см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)).

**Исходный код.** `lib/pages/animal_disposal/animal_disposal_bloc.dart` → `AnimalDisposalBloc.on<AnimalDisposalEventSave>`; `lib/repositories/disposal/disposal_repository.dart` → `DisposalRepository.saveDisposals`.
