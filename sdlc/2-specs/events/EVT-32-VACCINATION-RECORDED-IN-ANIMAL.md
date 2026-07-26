# EVT-32 — vaccination.recorded

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь проходит визард записи вакцинации (болезнь/комплексная вакцина → вакцина → дата → доза/единица → способ введения) для одного животного (карточка животного) или для нескольких выбранных животных места (батч-вакцинация из карточки места), подтверждает; `VaccinationBloc.on<VaccinationEventSave>`. Комплексная вакцина, если выбрана, перед сохранением разворачивается в конкретный список болезней.

**Эффект.** По одной записи `Vaccination` на каждое выбранное животное, каждая — с собственным набором связанных болезней в `DiseasesVaccinations`; `createdAt` выставляется, `sync=false`.

**Исходный код.** `lib/pages/vaccination/vaccination_bloc.dart` → `VaccinationBloc._onSave`; `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository.saveVaccination`.
