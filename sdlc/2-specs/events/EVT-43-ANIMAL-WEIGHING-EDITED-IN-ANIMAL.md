# EVT-43 — animal_weighing.edited

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь редактирует одно взвешивание — либо явно, открыв его из хаба неотправленных, либо неявно: `WeighAnimalPage` открылась в режиме правки, потому что у животного уже нашлось взвешивание за сегодняшний день (`WeighAnimalCubit._findTodayWeighing`, независимо от `sync`-статуса найденной записи); подтверждает через диалог `ConfirmEditWeighDialog` → `WeighAnimalCubit.saveEditedWeighing`.

**Эффект.** Единственная запись `AnimalWeighing` обновляется на месте (вес/единица/отметка здоровья); `sync` выставляется в `false`, `remoteId` (если был) сохраняется как есть — в отличие от Vaccination/Movement, локально нет отдельного признака «это правка уже отправленной записи», а не новая.

**Исходный код.** `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` → `WeighAnimalCubit.saveEditedWeighing`, `hasEditChanges`.
