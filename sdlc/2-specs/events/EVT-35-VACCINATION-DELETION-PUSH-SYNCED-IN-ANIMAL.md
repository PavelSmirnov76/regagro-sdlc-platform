# EVT-35 — vaccination.deletion_push_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Sync-проход доходит до первого из трёх push-шагов вакцинации — отправки записей, помеченных на удаление (`deletedAt != null`); `VaccinationsRepository.syncVaccinations` → `_deleteVaccinationFromApi`. На сегодня такие записи никогда не появляются через живой UI (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)), но шаг выполняется безусловно на каждом полном проходе и отдельно проверен репозиторным тестом, вставляющим строку напрямую в БД.

**Эффект.** Все подходящие строки отправляются одним батч-запросом (`DELETE .../vaccination-group-actions` с списком `shtpId`) разом — не по одной. Исключение или ответ с непустым `errors` перехватывается внутри метода и не пробрасывается наружу — sync pass продолжается дальше к update-шагу независимо от результата.

**Исходный код.** `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository._deleteVaccinationFromApi`.
