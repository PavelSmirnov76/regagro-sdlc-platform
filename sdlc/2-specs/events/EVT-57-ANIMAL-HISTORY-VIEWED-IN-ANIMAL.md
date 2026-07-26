# EVT-57 — animal.history_viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает вкладку «История» карточки животного; `AnimalHistoryCubit.load`.

**Эффект.** Кросс-областной read-экран — собирает в единую хронологическую ленту события пяти разных источников одного животного: выбытие ([ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)), перемещение ([ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)), взвешивание ([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)), вакцинация ([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) и сам факт регистрации животного. Без фильтра каждая группа схлопывается до одного (самого свежего) элемента; с выбранным фильтром — показывает все элементы этого типа, отсортированные по дате по убыванию.

**Исходный код.** `lib/pages/animal_history/cubit/animal_history_cubit.dart` → `AnimalHistoryCubit.load`, `setFilter`.
