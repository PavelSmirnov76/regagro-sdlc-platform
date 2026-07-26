# EVT-23 — animal.local_edited

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Пользователь редактирует ещё не синхронизированное животное (`id < 0`) — карточка животного ведёт на отдельный экран для этого случая, не на `AnimalEditPage`.

**Эффект.** Правка сохраняется прямо в локальную запись — животное всё ещё целиком уйдёт на сервер при первой синхронизации, отдельного флага отложенной отправки не требуется (в отличие от [EVT-24](EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)).

**Исходный код.** `lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart` → `UnsentAnimalEditBloc` (экран `Routes.unsentAnimalEdit`, отдельный от `AnimalEditBloc`).
