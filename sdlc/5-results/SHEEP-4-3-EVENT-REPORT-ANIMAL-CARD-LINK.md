- **task**: [`../4-tasks/SHEEP-4-3-EVENT-REPORT-ANIMAL-CARD-LINK.md`](../4-tasks/SHEEP-4-3-EVENT-REPORT-ANIMAL-CARD-LINK.md) (`UC-309`/`UC-310`/`UC-311`)

# Реализовано

- `lib/widgets/event_report/event_report_template.dart` — новый класс
  `EventReportAnimalEntry {animalId, number}`, `EventReportGroup.transponderNumbers`
  заменён на `animals: List<EventReportAnimalEntry>`. `_HighlightedNumber`
  теперь принимает `animalId` и оборачивается в `InkWell` с переходом
  `context.pushNamed2(Routes.animalDetailsFromSearch, extra:
  AnimalCardExtra(animalId: ...))` — тем же вызовом, что в
  `registration_day_report_view.dart`. Если `animalId == null` (животное не
  сопоставлено ни с одной идентификацией в этой записи), строка остаётся
  нетапабельной — это встречается редко (только если `activeAnimalIdentifications`
  не содержит транспондера), не является полноценной регрессией.
- `MovementAnimalGroup` (`movement_report_data.dart`) и `DisposalAnimalGroup`
  (`disposal_report_data.dart`) — аналогично переведены на
  `animals: List<EventReportAnimalEntry>`.
- Все три кубита (`movement_report_cubit.dart`, `disposal_report_cubit.dart`,
  `vaccination_report_cubit.dart`) — при построении групп теперь прокидывают
  `animal?.animalId` вместе с номером, а не только номер.
- `movement_report_view.dart`/`disposal_report_page.dart` — обновлена
  промежуточная маппинг-функция (локальный `*AnimalGroup` →
  `EventReportGroup`) на новое поле `animals`.
- Тестовые группы переименованы: `UC-149`→`UC-309`
  (`movement_report_cubit_test.dart`), `UC-109`→`UC-310`
  (`vaccination_report_cubit_test.dart`), `UC-163`→`UC-311`
  (`disposal_report_cubit_test.dart`). ERROR-варианты (`UC-150`/`UC-110`/`UC-164`)
  не переименованы — соответствующие UC не менялись.

## Проверено

- `flutter analyze` по всем 8 изменённым файлам — без замечаний.
- `flutter test` по трём файлам кубитов (`movement_report_cubit_test.dart`,
  `vaccination_report_cubit_test.dart`, `disposal_report_cubit_test.dart`) —
  все 18 тестов проходят, регрессия исключена.
- `dart format` применён.

## Отложено / не сделано

- Отдельный widget/интеграционный тест на сам тап-переход (открытие
  `AnimalCardPage` из конкретной строки отчёта, сохранение позиции
  прокрутки после возврата) — не написан: требует поднятия `GoRouter` в
  тестовом окружении, в проекте нет готового паттерна для такого теста ни
  для одного из трёх экранов-отчётов.
- Сохранение позиции прокрутки/состояния при возврате не проверялось вручную
  на устройстве/эмуляторе — обеспечивается архитектурно (`push`, не `go`),
  но не подтверждено визуально в этом проходе.
