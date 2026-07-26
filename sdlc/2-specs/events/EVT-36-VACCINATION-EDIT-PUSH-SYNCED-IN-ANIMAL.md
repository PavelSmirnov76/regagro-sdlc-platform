# EVT-36 — vaccination.edit_push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до второго push-шага вакцинации — отправки записей, помеченных `updatedAt != null` (правка уже синхронизированной записи); `VaccinationsRepository.syncVaccinations` → `_updateVaccinationFromApi`. На сегодня такие записи никогда не появляются через живой UI (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)), но шаг выполняется безусловно на каждом полном проходе и отдельно проверен репозиторным тестом, вставляющим строку напрямую в БД.

**Эффект.** Все подходящие строки отправляются одним батч-запросом (`PUT .../vaccination-group-actions`) разом. Исключение или ответ с непустым `errors` перехватывается внутри метода и не пробрасывается наружу — записи остаются в том же «в правке» состоянии до следующей попытки, sync pass продолжается дальше к create-шагу.

**Исходный код.** `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository._updateVaccinationFromApi`.
