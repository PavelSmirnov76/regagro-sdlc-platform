# EVT-28 — movement.deleted_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет ещё не отправленное перемещение с экрана хаба «неотправленных» — записи там сгруппированы в одну карточку по ключу (место отправления, место назначения, время до минуты), кнопка удаления удаляет разом всю группу; `UnsentMovementsCubit.deleteGroup`.

**Эффект.** Для каждой удаляемой записи отдельно откатывается `Animal.placeId` на `fromId`, если текущее место животного всё ещё совпадает с `placeId` записи.

**Исходный код.** `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` → `UnsentMovementsCubit.deleteGroup`; `lib/repositories/movement_report/movement_report_repository.dart` → `MovementReportRepository.delete`.
