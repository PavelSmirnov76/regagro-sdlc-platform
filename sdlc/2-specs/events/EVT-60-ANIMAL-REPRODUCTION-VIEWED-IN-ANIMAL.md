# EVT-60 — animal.reproduction_viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает экран «Разведение» карточки животного (вкладки «Родители»/«Потомство»); `ReproductionCubit.load`.

**Эффект.** Резолвит текущих мать/отца (по `motherId`/`fatherId`, при их отсутствии — из текстовых `motherBirk`/`fatherBirk`), вычисляет список потомков (все животные, чей `motherId`/`fatherId` указывает на текущее), и отдельно строит два списка кандидатов — доступных родителей (тот же вид, дата рождения раньше просматриваемого животного) и доступных потомков (тот же вид, дата рождения позже).

**Исходный код.** `lib/pages/reproduction/cubit/reproduction_cubit.dart` → `ReproductionCubit.load`.
