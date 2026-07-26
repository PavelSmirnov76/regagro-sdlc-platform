# EVT-34 — vaccination.deleted_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет одну ещё не отправленную запись вакцинации (иконка удаления на карточке) либо несколько выбранных разом (иконка «удалить отмеченные» в шапке хаба неотправленных, доступна только если хаб не пуст); `UnsentVaccinationCubit.delete`/`deleteSelected`.

**Эффект.** Безусловное («жёсткое») удаление строки(строк) из локальной таблицы — не пометка на удаление, в отличие от удаления уже синхронизированной записи (недостижимо, см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)). После удаления список перечитывается заново.

**Исходный код.** `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` → `UnsentVaccinationCubit.delete`, `deleteSelected`; `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository.deleteById`.
