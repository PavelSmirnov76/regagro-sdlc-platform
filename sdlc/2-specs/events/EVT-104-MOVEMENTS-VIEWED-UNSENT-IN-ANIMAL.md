# EVT-104 — movements.viewed_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает хаб ещё не отправленных перемещений
(обычно со сводного экрана «В работе»); `UnsentMovementsCubit.load`.

**Эффект.** Загружает все ещё не отправленные перемещения
(`getMovementsWithDetailsByFilters(sync: false)`); список — основа для
последующего [EVT-28](EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md). Реактивно
перезагружается через подписку на `watchNotSyncMovements()`.

**Исходный код.** `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart`
→ `UnsentMovementsCubit.load`, `_reload`.
