# EVT-27 — movement.recorded

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Пользователь выбирает одно или несколько животных, место отправления (если не предзадано) и место назначения в визарде перемещения, подтверждает; `AnimalMovementBloc.on<AnimalMovementEventSave>`.

**Эффект.** По одной записи `Movement` на каждое выбранное животное (список животных перед сохранением повторно выбирается из БД с фильтром «не удалено»); `Animal.placeId` каждого животного обновляется немедленно, локально.

**Исходный код.** `lib/pages/animal_movement/animal_movement_bloc.dart` → `AnimalMovementBloc.on<AnimalMovementEventSave>`; `lib/repositories/movement_report/movement_report_repository.dart` → `MovementReportRepository.saveMovements`.
