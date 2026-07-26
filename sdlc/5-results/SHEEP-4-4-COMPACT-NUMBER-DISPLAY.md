- **task**: [`../4-tasks/SHEEP-4-4-COMPACT-NUMBER-DISPLAY.md`](../4-tasks/SHEEP-4-4-COMPACT-NUMBER-DISPLAY.md) (`UC-312`/`UC-313`)

# Реализовано

- Новый общий публичный виджет `lib/widgets/text/highlighted_number_text.dart`
  (`HighlightedNumberText`) с параметром `isShort` — заменил оба существовавших
  приватных дубликата (`_HighlightedNumber` в `event_report_template.dart`,
  `_HighlightedNumberText` в `inventory_accordion_list_widget.dart`), а не
  добавил третью копию для реестра — как и рекомендовала задача.
  - `isShort: false` (по умолчанию) — прежнее поведение не изменилось (номер
    целиком, последние 4 цифры зелёным).
  - `isShort: true` — «…» + последние 4 цифры, остальное скрыто.
  - Параметры `fontSize`/`color` сохраняют визуальные различия, которые были
    у двух исходных копий (18px без явного цвета у отчётов, дефолтный размер
    с явным чёрным у инвентаризации).
- `event_report_template.dart` — `_HighlightedNumber` теперь тонкая обёртка
  над `HighlightedNumberText` (только тап-логика из пункта 3, сама отрисовка
  делегирована).
- `inventory_accordion_list_widget.dart` — все 4 места использования
  переведены на `HighlightedNumberText`, приватный класс удалён.
- `lib/pages/animals/animals_page.dart` — `AnimalCardWidget` (общий для
  «Реестра животных» и основного списка) — номер заменён с обычного
  `Text`/`ellipsis` на `HighlightedNumberText(isShort: true)`.
- Тестовые группы переименованы: `UC-71`→`UC-312`
  (`animals_bloc_test.dart`), `UC-73`→`UC-313` (`animals_registry_cubit_test.dart`).
  ERROR-варианты (`UC-72`/`UC-74`) не переименованы — не менялись.

## Проверено

- `flutter analyze` по всем 4 изменённым `.dart`-файлам — без замечаний.
- `flutter test` по `animals_bloc_test.dart` и `animals_registry_cubit_test.dart`
  — все 40 тестов проходят.
- `flutter test test/pages/movement_report_cubit_test.dart
  test/pages/vaccination_report_cubit_test.dart
  test/pages/disposal_report_cubit_test.dart test/pages/inventory_report_details_cubit_test.dart`
  — повторно прогнаны после рефакторинга общего виджета (используются теми
  же файлами) — все проходят.
- `dart format` применён.

## Отложено / не сделано

- Отдельный widget-тест на сам `HighlightedNumberText` (граница `isShort`,
  короткие номера ≤4 символов) — не написан, в проекте нет прецедента
  чистого unit/widget-теста на подобные мелкие display-виджеты.
- Визуально на устройстве/эмуляторе не проверялось.
