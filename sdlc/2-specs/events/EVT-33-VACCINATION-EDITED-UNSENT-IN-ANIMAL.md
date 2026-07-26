# EVT-33 — vaccination.edited_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает ещё не отправленную (новую, `createdAt != null`) запись вакцинации из хаба неотправленных и сохраняет правку; `UnsentVaccinationEditBloc.on<UnsentVaccinationEditEventSave>`. Единственный живой вход в этот блок — список хаба (`getNotSyncVaccinationsWithDetails`), который по построению возвращает только такие, ещё ни разу не отправленные, записи.

**Эффект.** Поля записи обновляются на месте; запись остаётся в том же состоянии «новая, не отправленная» (`updatedAt` не выставляется — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), недостижимая ветка правки уже синхронизированной записи).

**Исходный код.** `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` → `UnsentVaccinationEditBloc._onSave`; `lib/repositories/vaccination/vaccinations_repository.dart` → `VaccinationsRepository.updateVaccination`.
