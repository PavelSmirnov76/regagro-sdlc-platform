- **derived from**: [BT-4](../../1-business-tasks/planning/BT-4-PLANNING-ANIMAL-REG.md)

# MOD-4 — ANIMAL

Один модуль на весь жизненный цикл животного — регистрация/редактирование (REG), перемещение (MOVE), вакцинация (VAC), взвешивание (WEIGH), выбытие (DISP), разведение/родословная (REPRO), инвентаризация (INV). Семь под-областей, специфицируемых отдельными business tasks (по одной на под-область), но один общий модуль/суффикс `-IN-ANIMAL` — так же было устроено и в прежней версии дерева.

## Назначение

Всё, что касается конкретного животного как сущности: заведение записи, идентификация, редактирование, и связанные с животным события (перемещение/вакцинация/взвешивание/выбытие/разведение/инвентаризация) — специфицируются по мере прохождения очереди модулей.

## Состав (полностью — REG + MOVE + VAC + WEIGH + DISP + REPRO + INV)

- Акторы: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (новый, «текущий пользователь ANIMAL», гость и авторизованный одинаково), [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) (переиспользован из FARM, sync-проход).
- Сущности: [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal — REG **и** REPRO, REPRO не заводит отдельную сущность), [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md) (REG), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (MOVE), [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (VAC), [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (WEIGH), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (DISP), [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) (INV).
- События: [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)…[EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md) (REG), [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)…[EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md), [EVT-104](../events/EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md), [EVT-105](../events/EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (MOVE — два последних read-события добавлены отдельным проходом, закрывая ранее отложенный пробел read-экранов, см. `SDLC-REWRITE-PLAN.md`), [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md)…[EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (VAC), [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)…[EVT-49](../events/EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (WEIGH), [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md)…[EVT-56](../events/EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (DISP), [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md) (кросс-областной, на Animal — «История животного», объединяет MOVE/VAC/WEIGH/DISP/REG в одну ленту), [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md)…[EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md) (REPRO — переиспользует push/pull REG, отдельных не заводит), [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)…[EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) (INV) (`events/EVT-*-IN-ANIMAL.md`).
- Use-cases: `use-cases/UC-*-IN-ANIMAL.md` — см. индекс [use-cases/README.md](../use-cases/README.md).

## Граница — что модуль explicitly не владеет

- Справочники, используемые только вакцинацией (`Vaccine`, `Disease`, `InjectionMethod`, `InjectionPlace`, `VaccinationType`, `ComplexVaccine`) — описаны как поля/связи внутри [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), не как отдельные сущности, т.к. ни один другой модуль их не использует.
- Ферма/место, на которые ссылается животное (`farmId`/`placeId`) — модуль [FARM](MOD-3-FARM.md), уже специфицирован; каскадная замена локального id фермы/места на серверный описывается в спеке FARM, не здесь.
- Виды/породы/масти животных — модуль [HANDBOOKS](MOD-2-HANDBOOKS.md) ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)); ANIMAL только ссылается на них по id.
- Явный полный sync pass как таковой — модуль `SYSTEM` (последний в очереди), не здесь.

Все семь под-областей специфицированы — модуль `MOD-4-ANIMAL` закрыт.
Ранее отложенный пробел read-экранов MOVE (`UnsentMovementsCubit.load`/
`MovementReportCubit.load` — часть `R26`) закрыт отдельным проходом
(`EVT-104`/`EVT-105`, `UC-209`…`UC-212`).
