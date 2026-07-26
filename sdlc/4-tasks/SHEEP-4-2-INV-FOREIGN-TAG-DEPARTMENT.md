- **business task**: `BT-19` ([`../1-business-tasks/planning/BT-19-PLANNING-ANIMAL-INV-FOREIGN-TAG-DEPARTMENT.md`](../1-business-tasks/planning/BT-19-PLANNING-ANIMAL-INV-FOREIGN-TAG-DEPARTMENT.md)), `BT-25` ([`../1-business-tasks/planning/BT-25-PLANNING-ANIMAL-INV-REPORT-ANIMAL-CARD-LINK.md`](../1-business-tasks/planning/BT-25-PLANNING-ANIMAL-INV-REPORT-ANIMAL-CARD-LINK.md), дополнение — тап-переход в карточку животного)
- **spec**: `UC-317` ([`../2-specs/use-cases/UC-317-ACTOR-5-EVT-85-ENT-11-READ_OK-IN-ANIMAL.md`](../2-specs/use-cases/UC-317-ACTOR-5-EVT-85-ENT-11-READ_OK-IN-ANIMAL.md), supersedes `UC-307` supersedes `UC-176`), `UC-318` (supersedes `UC-308` supersedes `UC-178`), `ENT-11`, `ENT-2`, `ENT-5`
- **design**: нет `FIG-{n}` и не будет — по этому тикету дизайн-стадия не запускается ни по одному пункту (см. raw `SHEEP-4-clarifications.md`, «Общее»); экран уже существует, меняется только текст fallback'а
- **tracker**: нет подключённого трекера (Yandex Tracker MCP недоступен в этой сессии) — по `RUNBOOK.md` шаг 6, этот файл является записью учёта. Внешний тикет-источник — `SHEEP-4`, пункт чек-листа 2

# Показывать «Отделение не указано» вместо `-`/пустоты для чужих и неизвестных меток инвентаризации

## Объём

Экран деталей сессии инвентаризации
(`lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart`,
`lib/pages/scanning/widgets/inventory_accordion_list_widget.dart`) уже
показывает секцию «Чужие метки» с отделением/видом/номером — почти без
доработок. Нужно только:

1. `InventoryForeignKnownEntry.placeName` (`_computeSections`, :149) — заменить
   fallback `'-'` на новый локализованный текст **«Отделение не указано»**,
   когда `animal.place == null`.
2. `_UnknownNumbersWrap`/`state.otherAnimals` (номера, не найденные ни в одной
   `AnimalIdentification` в системе, :67,:166 в кубите, рендер
   `inventory_accordion_list_widget.dart:272-295`) — сейчас показывается
   только голый номер; добавить рядом с каждым таким номером тот же текст
   «Отделение не указано» (вид/возрастную группу для этих строк показать
   нельзя — животное не идентифицировано вообще).

Приоритет «возрастная группа важнее вида» — **не трогать**, подтверждено
постановщиком как корректное поведение.

Полное обоснование и CURRENT/TARGET-поведение — `UC-317` (текущий живой
преемник `UC-307`).

## Критерии приёмки (definition of done)

- [ ] Для «чужой» метки без резолвящегося места вместо `-` показывается «Отделение не указано».
- [ ] Для номера, не найденного ни в одной идентификации в системе, рядом с номером тоже показывается «Отделение не указано».
- [ ] Термин «отделение» используется единообразно (не «место содержания»).
- [ ] Приоритет вид/возрастная группа не меняется.
- [ ] Наименование отделения по-прежнему не обрезается (нет `overflow`/`maxLines`).
- [ ] Регрессия исключена: остальная логика `_computeSections`/группировки не меняется.

## Реализационные заметки

- Завести новый ключ локализации через `/add-translation` (напр.
  `inventory_department_not_specified` = «Отделение не указано», по образцу
  существующего `enterprise_location_not_specified`) — не хардкодить строку
  инлайн.
- Для `_UnknownNumbersWrap` — конкретный layout (переиспользовать разметку
  `_KnownForeignRow` без вида/возрастной группы, либо дополнить текущий
  `Wrap` подписью под/рядом с номером) не задан ни тикетом, ни макетом —
  решает исполнитель, ориентируясь на существующий визуальный стиль экрана
  (см. `UC-317`, `TBD/BLOCKED`). При сомнении — согласовать словами с
  постановщиком до реализации, не выдумывать новый дизайн-паттерн.
- Тестовая группа `test/pages/inventory_report_details_cubit_test.dart`
  сейчас именуется по `UC-176` — при реализации переименовать/дополнить
  ссылку на `UC-317` (правило самопривязки теста к спеке).

## Зависимости

Нет блокирующих зависимостей. Единственная новая работа за пределами самого
экрана — локализационный ключ (`/add-translation`, все языки приложения).

## Дополнение — тап-переход в карточку животного (`BT-25`, `UC-317`/`UC-318`)

Запрошено постановщиком после реализации всех задач тикета: тот же
тап-переход в `AnimalCardPage`, что уже сделан для отчётов
перемещения/вакцинации/выбытия (`SHEEP-4-3`), нужен и здесь.

### Объём дополнения

1. `InventoryAgeGroupSection`, `InventoryAbsentEntry`,
   `InventoryForeignKnownEntry` (`inventory_report_details_view.dart`,
   `inventory_accordion_list_widget.dart`) — получили `animalId`.
2. `_TagNumberRow`, `_AbsentAnimalRow`, `_KnownForeignRow`
   (`inventory_accordion_list_widget.dart`) — обёрнуты новым
   хелпером `_tappableRow(context, animalId, child)`
   (`InkWell` → `context.pushNamed2(Routes.animalDetailsFromSearch, extra:
   AnimalCardExtra(animalId: ...))` при `animalId != null`).
3. `_UnknownNumbersWrap` — без изменений, не тапабелен (нет `animalId`).
4. `inventory_scan_step_page.dart` (живое сканирование сессии, второй
   потребитель того же `InventoryAccordionListWidget`) — получил тот же
   тап-переход как побочный эффект правки общего виджета; сам не покрыт ни
   одним `UC`.

### Критерии приёмки дополнения

- [x] Строки «учтено»/«отсутствует»/«чужая метка» тапабельны, открывают карточку именно этого животного.
- [x] `unknownNumbers` — по-прежнему не тапабельны.
- [x] Живой экран сканирования — то же поведение (общий виджет).
- [x] Fallback «Отделение не указано» и остальная логика `_computeSections` не регрессируют.

Результат — `../5-results/SHEEP-4-2-INV-FOREIGN-TAG-DEPARTMENT.md`.
