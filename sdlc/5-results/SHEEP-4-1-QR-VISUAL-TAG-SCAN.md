- **task**: [`../4-tasks/SHEEP-4-1-QR-VISUAL-TAG-SCAN.md`](../4-tasks/SHEEP-4-1-QR-VISUAL-TAG-SCAN.md) (`UC-306`)

# Реализовано

- `lib/pages/weigh_animal/widgets/scanner_widget.dart` — выделена общая
  функция `resolveScannedNumber(context, scannerService)`, реализующая
  паттерн «настройка „камера как QR“ → аппаратный скан с fallback на
  камеру» — тем самым устранены три существовавших дубликата этой логики
  внутри файла (`ScannerWidget` x2, `ScannerWidgetAutoComplete` x1), не
  только добавлен новый потребитель.
- `lib/pages/animal_registration/step_pages/identifications_step_page.dart`
  — на шаге «Маркирование» рядом с полем «Визуальная бирка» добавлена
  кнопка сканирования (`Assets.scanner`, тот же нейтральный вид, что в
  `ScannerWidget`), вызывающая `resolveScannedNumber` и подставляющая
  результат в `_birkController`/`onNumberChanged` — тем же путём, что и
  ручной ввод/аппаратный сканер.
- Тестовая группа `test/pages/animal_registration_bloc_test.dart`
  переименована с `UC-52/53` на `UC-306/53`.

## Проверено

- `flutter analyze` по изменённым файлам — без замечаний.
- `flutter test test/pages/animal_registration_bloc_test.dart` — все 58
  тестов проходят (регрессия исключена).
- `dart format` применён.

## Отложено / не сделано

- Отдельный widget-тест на новую кнопку сканирования (`IdentificationsStepPage`)
  — не написан в этом проходе: в проекте нет готового мок-паттерна для
  `DeviceSettingsRepository`/`ScannerService`/`QRScanner`-навигации, с нуля
  создавать инфраструктуру теста в рамках этой узкой задачи не стал.
  Функция `resolveScannedNumber` тоже без прямого теста — её 3 предыдущих
  использования (`ScannerWidget`/`ScannerWidgetAutoComplete`) тоже не были
  покрыты тестами до этого прохода.
- Не запускалось на реальном устройстве/эмуляторе — только статическая
  проверка (`analyze`) и существующий bloc-тест.
