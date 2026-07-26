# EVT-47 — animal_weighings.viewed_for_animal

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает вкладку взвешиваний карточки животного; `AnimalWeighingsCubit.load`.

**Эффект.** Загружает все взвешивания животного (независимо от `sync`-статуса, в отличие от Vaccination), сортирует по дате по возрастанию, подтягивает место животного для заголовка; экран поверх этого вычисляет среднесуточный привес/увес между последовательными записями (`buildGainData`). Альтернативный, не читающий из БД путь инициализации (`initWithoutLoad`) существует в коде, но нигде не вызывается — см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md).

**Исходный код.** `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` → `AnimalWeighingsCubit.load`; `lib/pages/animal_weighings/utils/animal_weighing_gain_utils.dart` → `buildGainData`.
