- **task**: [`../4-tasks/SHEEP-4-2-INV-FOREIGN-TAG-DEPARTMENT.md`](../4-tasks/SHEEP-4-2-INV-FOREIGN-TAG-DEPARTMENT.md) (`UC-307`/`UC-308`, дополнение — `UC-317`/`UC-318`)

# Реализовано

- Новый локализационный ключ `inventory_department_not_specified` = «Отделение
  не указано» добавлен во все 9 `.arb`-файлов (в русской локали — реальный
  перевод; в остальных 7 нешаблонных локалях, где вся секция `inventory_*`
  уже была на английском без перевода — оставлен английский текст «Department
  not specified», по образцу уже принятого в этой секции состояния, не в
  разнобой). `flutter gen-l10n` прогнан.
- `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`
  — `_computeSections` теперь принимает `BuildContext`, fallback
  `InventoryForeignKnownEntry.placeName` заменён с `'-'` на локализованный
  текст.
- `lib/pages/scanning/widgets/inventory_accordion_list_widget.dart` —
  `_UnknownNumbersWrap` переведён с компактного `Wrap` (голый номер) на
  полноширинные строки в стиле уже существующих `_AbsentAnimalRow`/
  `_KnownForeignRow` (лейбл слева, номер справа) — показывает «Отделение не
  указано» рядом с каждым номером, не найденным ни в одной идентификации.
  Новый обязательный параметр `departmentNotSpecifiedLabel` на
  `InventoryAccordionListWidget`.
- **Найден и обновлён второй потребитель**, не упомянутый в исходной
  спеке (`UC-307`/`UC-308` цитировали только `inventory_report_details_view.dart`):
  `lib/pages/scanning/steps/inventory_scan_step_page.dart` — экран **живого**
  сканирования инвентаризации использует тот же
  `InventoryAccordionListWidget` со своей собственной `_computeSections()` и
  тоже собирает `unknownNumbers` — прокинут тот же локализованный лейбл.
  Плейсхолдер `placeName` там не нужен (`place.place.name` берётся из
  заведомо не-null объекта, не из nullable join, как в отчёте) — тронут
  только `unknownNumbers`.

## Отклонение от спеки (замечено по ходу реализации)

`UC-307`/`UC-308`/`BT-19` цитировали `_computeSections` как метод
`InventoryReportDetailsCubit` (`inventory_report_details_cubit.dart:113-168`)
— на самом деле это приватный метод `InventoryReportDetailsView`
(`inventory_report_details_view.dart`), сам кубит (109 строк) этой логики не
содержит. Фактическое поведение и критерии приёмки спеки не пострадали
(строка кода правильно найдена и исправлена), только путь в «Технические
зависимости» был неточным — не стал заводить новый UC ради опечатки в пути
файла, оставляю эту заметку как исправление на будущее.

## Проверено

- `flutter analyze` по всем 3 изменённым `.dart`-файлам — 0 ошибок (5
  pre-existing `info`-замечаний в `inventory_scan_step_page.dart`, не в
  затронутых мной строках).
- `flutter test test/pages/inventory_report_details_cubit_test.dart` — все 5
  тестов проходят.
- `dart format` применён.

## Отложено / не сделано

- Отдельный widget-тест на новый fallback/на новую раскладку
  `_UnknownNumbersWrap` — не написан (оба экрана требуют полноценного
  `pumpLocalizedContext` + мокнутых репозиториев/кубитов, в проекте нет
  готового такого теста ни для одного из двух экранов, для точечной задачи
  не стал заводить инфраструктуру с нуля).

## Дополнение — тап-переход в карточку животного (`UC-317`/`UC-318`, `BT-25`)

Запрошено постановщиком после реализации всех задач тикета — тот же
тап-переход, что в `SHEEP-4-3` (отчёты перемещения/вакцинации/выбытия), нужен
и в отчёте инвентаризации.

### Реализовано

- `lib/pages/scanning/widgets/inventory_accordion_list_widget.dart` —
  `InventoryAgeGroupSection.numbers: List<String>` →
  `animals: List<EventReportAnimalEntry>`; `InventoryAbsentEntry` и
  `InventoryForeignKnownEntry` получили `required final int? animalId`; новый
  хелпер `_tappableRow(BuildContext, int? animalId, Widget child)` — `InkWell`
  с переходом на `Routes.animalDetailsFromSearch` (`AnimalCardExtra`), когда
  `animalId != null`; `_TagNumberRow`, `_AbsentAnimalRow`, `_KnownForeignRow`
  переведены на него. `_UnknownNumbersWrap` не тронут (нет `animalId`).
- `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`
  — `_computeSections` прокидывает `animal.animalId` во все три модели строк.
- `lib/pages/scanning/steps/inventory_scan_step_page.dart` — тот же
  `animalId`-threading в собственной `_computeSections`, экран живого
  сканирования получил тап-переход как побочный эффект правки общего
  виджета; по-прежнему не покрыт отдельным `UC` (см. «Открытые вопросы» в
  `UC-317`).

### Проверено

- `flutter analyze` по всем трём файлам — чисто (только pre-existing
  info-замечания в `inventory_scan_step_page.dart` на несвязанных строках).
- `flutter test test/pages/inventory_report_details_cubit_test.dart` — проходит.
- `dart format` применён.
- Полный `flutter test` — 1249/1249 проходят.

### Отложено / не сделано

- Widget-тест на сам тап (открытие карточки по нажатию) — не написан, по той
  же причине, что и в исходном проходе (нет готовой инфраструктуры
  `pumpLocalizedContext` + мокнутых кубитов для этих двух экранов).
- `inventory_scan_step_page.dart` остаётся без собственного `UC` в спеке —
  предсуществующий пробел, не закрыт в рамках этого узкого дополнения.
