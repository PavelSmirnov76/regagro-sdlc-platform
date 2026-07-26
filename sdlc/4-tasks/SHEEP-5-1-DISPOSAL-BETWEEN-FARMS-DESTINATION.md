- **business task**: `BT-26` ([`../1-business-tasks/planning/BT-26-PLANNING-ANIMAL-DISP-BETWEEN-FARMS-DESTINATION.md`](../1-business-tasks/planning/BT-26-PLANNING-ANIMAL-DISP-BETWEEN-FARMS-DESTINATION.md))
- **spec**: `UC-319` ([`../2-specs/use-cases/UC-319-ACTOR-5-EVT-73-ENT-27-CREATE_OK-IN-ANIMAL.md`](../2-specs/use-cases/UC-319-ACTOR-5-EVT-73-ENT-27-CREATE_OK-IN-ANIMAL.md), supersedes `UC-151`), `ENT-27` (supersedes `ENT-10`)
- **design**: не требуется — переиспользуются существующие компоненты (`RDropDownButton`, `SelectPlaceStepPage`), новых экранов/визуальных компонентов нет
- **tracker**: нет подключённого трекера в этой сессии — по `RUNBOOK.md` шаг 6, этот файл является записью учёта

# Включить причину выбытия «между фермами владельца», добавить шаги выбора целевой фермы/места

## Объём

1. **DB-миграция** (`packages/sheep_farm_database`): новая колонка
   `Disposals.toPlaceId` (`to_place_id`), `schemaVersion` +1, блок
   `onUpgrade` под новый номер.
2. **`AnimalDisposalBloc`** (`animal_disposal_bloc.dart`):
   - убрать `.where((e) => e.id != 4)` при загрузке причин в
     `on<AnimalDisposalEventStart>`;
   - новые события `AnimalDisposalEventSelectTargetFarm`/
     `AnimalDisposalEventChangeTargetPlace`;
   - новые поля `AnimalDisposalData`: `targetFarms` (все фермы владельца, кроме
     фермы-источника), `selectedTargetFarm`, `targetPlaces`,
     `selectedTargetPlace`;
   - `currentSteps` — вставить `selectTargetFarm`/`selectTargetPlace` между
     `reason` и `animals`, только когда `selectedReason?.id == 4`;
   - `on<AnimalDisposalEventSave>` — при `selectedReason?.id == 4` заполнять
     `toId`/`toPlaceId` из `selectedTargetFarm`/`selectedTargetPlace`.
3. **`animal_disposal_page.dart`**/`animal_disposal_state.dart`: новые значения
   `AnimalDisposalStep.selectTargetFarm`/`.selectTargetPlace`, виджеты шагов
   (`RDropDownButton` для фермы, переиспользованный `SelectPlaceStepPage` для
   места), заголовки в `_TabBar._getTitles`.
4. **`disposal_repository.dart`**: `sendDisposalList` — новый параметр/поле
   запроса `to_place_id`; `_groupForSend`/`_DisposalSendGroup` — ключ группы и
   передаваемые данные учитывают `toPlaceId`.

Полное обоснование — `UC-319`, `ENT-27`.

## Критерии приёмки (definition of done)

- [ ] Причина с `id == 4` доступна для выбора.
- [ ] При её выборе визард показывает шаг выбора целевой фермы (выпадающий
      список, без фермы-источника) и шаг выбора целевого места (стандартный
      компонент), между шагом причины и шагом выбора животных.
- [ ] Для остальных причин — поведение визарда не меняется.
- [ ] Сохранённая запись несёт `toId`/`toPlaceId` выбранных фермы/места (только
      для причины `id == 4`).
- [ ] Исходящий запрос создания выбытия несёт `to_place_id` = `toPlaceId` группы
      (только для группы с этой причиной); `from_id`/`to_id` — `remoteId` ферм.
- [ ] `flutter test` — зелёный, включая новый(-ые) тест(-ы) на
      `AnimalDisposalEventSave` для причины `id == 4`.

## Реализационные заметки

- Список ферм для дропдауна — `FarmRepository.getAll()` (все локально известные
  фермы владельца), без сетевого запроса.
- Места целевой фермы — тем же методом, что уже используется для места-источника
  (`PlaceRepository.getAllWithThisFarmIdWithAnimals`), для консистентности
  отображения (счётчики животных).
- Не трогать `DisposalReasonHelper` — подтверждено мёртвым кодом (`ENT-27`),
  вне объёма этой задачи.

## Зависимости

`SHEEP-5-2` (тот же модуль `Disposal`, независимая правка pull-пути) — можно
реализовывать в любом порядке, оба меняют одну и ту же таблицу/сущность, но не
пересекающиеся участки кода.
