# EVT-44 — animal_weighing.deleted_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет одно ещё не отправленное взвешивание (`sync == false`) с экрана хаба «В работе»; `AnimalWeighingsCubit.delete`.

**Эффект.** Безусловное («жёсткое») удаление строки из локальной таблицы — не пометка на удаление (у сущности вообще нет поля для этого, см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)); удаление уже синхронизированного взвешивания этим методом невозможно, отдельный immediate-путь для этого недостижим из UI. После удаления список перечитывается.

**Исходный код.** `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` → `AnimalWeighingsCubit.delete`.
