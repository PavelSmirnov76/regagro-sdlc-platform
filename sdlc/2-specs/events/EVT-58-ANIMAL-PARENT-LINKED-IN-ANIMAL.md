# EVT-58 — animal.parent_linked

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

**Триггер.** На экране «Разведение» пользователь выбирает мать или отца животного — либо из списка уже зарегистрированных кандидатов (отфильтрованных по виду и правдоподобной дате рождения), либо вводом текстового номера без привязки к записи («не зарегистрировано»); подтверждает; `ReproductionCubit.saveParent`.

**Эффект.** Обновляется запись самого просматриваемого животного: `motherId`/`motherBirk` либо `fatherId`/`fatherBirk`, в зависимости от пола выбранного родителя; ранее известный второй родитель сохраняется без изменений. Для уже синхронизированного животного (`id >= 0`) взводится `needsUpdate: true` — та же деферред-sync машинерия, что у обычной правки животного ([EVT-24](EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)), отдельного push/pull-события REPRO не заводит.

**Исходный код.** `lib/pages/reproduction/cubit/reproduction_cubit.dart` → `ReproductionCubit.saveParent`.
