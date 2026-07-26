# EVT-42 — animal_weighing.recorded

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь взвешивает одно животное или несколько подряд (сканирует/ищет следующее животное после каждого, экран не закрывается между ними) через `WeighAnimalCubit`, вручную либо через подключённые по Bluetooth весы, и подтверждает сохранение всей накопленной за визит партии.

**Эффект.** По одной записи `AnimalWeighing` на каждое взвешенное животное, каждая — с собственными весом/единицей/датой/отметкой здоровья; `sync=false`, `remoteId` не задан.

**Исходный код.** `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` → `WeighAnimalCubit.saveCurrentWeighingStayOnPage` (стейджинг одной записи в память), `saveWeighing` (финальная запись всей партии в БД).
