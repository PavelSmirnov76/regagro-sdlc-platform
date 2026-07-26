# EVT-39 — vaccinations.viewed_for_animal

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает вкладку вакцинаций карточки животного; `AnimalVaccinationsCubit.load` (подписан на `watchCountAllVaccinations()` — перезагружается сам при любом изменении в таблице `Vaccinations`, не только по явному действию пользователя).

**Эффект.** Загружает только уже синхронизированные записи (`sync: true`) животного, вычисляет статус каждой, применяет быстрый фильтр/фильтры экрана, отдельно выделяет «будущие» (ещё не наступившие `nextVaccinationDate`). Отдельный экран группировки по болезням (`VaccinationsByDiseasesCubit`) существует в коде, но нигде не открывается — недостижим из UI.

**Исходный код.** `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` → `AnimalVaccinationsCubit.load`.
