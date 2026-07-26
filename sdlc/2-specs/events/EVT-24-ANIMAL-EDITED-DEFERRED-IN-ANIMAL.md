# EVT-24 — animal.edited_deferred

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Пользователь редактирует уже синхронизированное животное (`id >= 0`) — порода/масть/дата рождения/пол; `AnimalEditBloc`.

**Эффект.** Правка сохраняется только локально, с флагом `needsUpdate: true` — отправка на сервер отложена до следующего sync-прохода ([EVT-26](EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)), не выполняется немедленно.

**Исходный код.** `lib/pages/animal_edit/animal_edit_bloc.dart` → `AnimalEditBloc` (обработчик сохранения).
