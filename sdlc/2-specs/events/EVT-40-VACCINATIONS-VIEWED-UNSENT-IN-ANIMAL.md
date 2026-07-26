# EVT-40 — vaccinations.viewed_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает хаб ещё не отправленных вакцинаций (обычно со сводного экрана «В работе»); `UnsentVaccinationCubit.load`.

**Эффект.** Загружает все ещё не отправленные новые записи (`getNotSyncVaccinationsWithDetails` — по построению только `createdAt != null`, см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)); список — основа для последующего [EVT-33](EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md)/[EVT-34](EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md).

**Исходный код.** `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` → `UnsentVaccinationCubit.load`.
