# EVT-48 — animal_weighings.viewed_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает хаб ещё не отправленных взвешиваний (обычно со сводного экрана «В работе»); `AnimalWeighingsCubit.loadNotSync`.

**Эффект.** Загружает все строки с `sync == false` по всем животным сразу (глобальный список, не по одному животному), сортирует по дате; список — основа для последующего [EVT-43](EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md) (тап по записи открывает правку)/[EVT-44](EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md).

**Исходный код.** `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` → `AnimalWeighingsCubit.loadNotSync`.
