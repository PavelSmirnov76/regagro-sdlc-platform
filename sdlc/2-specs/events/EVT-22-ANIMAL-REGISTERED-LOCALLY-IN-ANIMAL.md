# EVT-22 — animal.registered_locally

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** Пользователь (гость или авторизованный) проходит визард регистрации (вид → порода → масть → пол → дата рождения → маркировка → чекаут; шаг выбора места — только если место не передано аргументом) и подтверждает на чекауте; `AnimalRegistrationBloc`.

**Эффект.** Животное сохраняется локально с отрицательным id, без ожидания сервера; заполненные идентификационные записи ([ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)) сохраняются вместе с ним в той же операции.

**Исходный код.** `lib/pages/animal_registration/animal_registration_bloc.dart` → `AnimalRegistrationBloc.saveAnimal`.
