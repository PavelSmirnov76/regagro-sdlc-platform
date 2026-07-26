# EVT-37 — vaccination.creation_push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до третьего push-шага вакцинации — отправки ещё не отправленных новых записей (`createdAt != null`); `VaccinationsRepository.syncVaccinations` → `_sendVaccinationsToApi`.

**Эффект.** В отличие от [EVT-35](EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-36](EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md), записи отправляются по одной, отдельным `POST .../vaccination-group-actions` на каждую — результат независим по каждой записи: успех удаляет строку локально (`deleteById`), отказ конкретной записи (ответ с `errors`/`status: error`, либо `DioException`) записывает текст ошибки в поле `errors` этой же строки, не прерывая отправку остальных. Необработанное исключение выше per-item try/catch (например при самом чтении списка к отправке) пробрасывается наружу и прерывает весь `syncVaccinations`.

**Исходный код.** `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository._sendVaccinationsToApi`, `_addErrorsToVaccinations`.
