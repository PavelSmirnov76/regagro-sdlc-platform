# EVT-38 — vaccinations.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Sync-проход запрашивает актуальный список вакцинаций с сервера, безусловно, независимо от исхода трёх предыдущих push-шагов ([EVT-35](EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)–[EVT-37](EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md)); `VaccinationsRepository.syncVaccinations`.

**Эффект.** Перед очисткой весь текущий набор ещё не синхронизированных строк (`sync == false`, в любом из трёх состояний) считывается в память; локальная таблица `Vaccinations` полностью очищается (`dao.clear()`) и перезаписывается постранично полученным с сервера ответом (каждая — новый локальный id, `sync=true`); затем ранее считанные неотправленные строки вставляются обратно, если только не передан `isDeleteErrors: true` (обычный пользовательский запуск синхронизации этот флаг не передаёт). Ошибка при получении пробрасывается наружу (`rethrow`) — в отличие от [EVT-31](EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md) (Movement), где ошибка pull только логируется.

**Исходный код.** `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository.syncVaccinations`, `_getVaccinationsFromApi`.
