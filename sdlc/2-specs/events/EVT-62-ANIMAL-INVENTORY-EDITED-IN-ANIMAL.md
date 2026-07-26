# EVT-62 — animal_inventory.edited

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает уже сохранённую (`readyToSend = true`),
но ещё не отправленную сессию инвентаризации из хаба «В работе» →
`UnsentInventoriesPage`, тап по карточке → `ScanningPageArgs.inventory(editPlaceId:, editSessionUuid:)` →
`ScanningBloc.on<ScanningStart>` (`markSessionAsDraftByUuid` снимает
`readyToSend`, подгружает уже отсканированные строки заново,
`isEditMode = true`). Правка (дополнительные сканы либо простой просмотр)
завершается одним из двух путей: явно — кнопкой «Завершить»
(`ScanningEventSave`, тот же обработчик, что у [EVT-61](EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)),
либо неявно — уходом с экрана назад (`ScanningBloc.close()`, доперсистит
сессию как ready-to-send, если `isEditMode && _canPersistSession`, без
дополнительного подтверждения).

**Эффект.** Строки `UnsentReportAnimals` того же `sessionUuid` снова
помечаются `readyToSend = true`; в отличие от [EVT-61](EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md),
`sessionUuid` не меняется — это правка существующей сессии, а не создание
новой.

**Исходный код.** `lib/pages/scanning/scanning_bloc.dart` →
`ScanningBloc.on<ScanningStart>` (ветка `editSessionUuid`),
`ScanningBloc.close()`, `on<ScanningEventSave>`; `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` →
`UnsentReportAnimalsRepository.markSessionAsDraftByUuid`, `getSessionReportsByUuid`, `markSessionReadyToSendByUuid`.
