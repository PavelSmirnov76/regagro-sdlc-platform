- **task**: [`../4-tasks/SHEEP-4-8-FARM-NAME-VALIDATION-KEYBOARD.md`](../4-tasks/SHEEP-4-8-FARM-NAME-VALIDATION-KEYBOARD.md) (`UC-315`)

# Реализовано

1. **Валидация названия** — `RTextFieldSimple` получил параметр `validator`
   (проброс в уже поддерживающий его `RTextField.outline`). Новый
   trim-aware метод `Validator.isNotBlank({value, message})` (строка из
   пробелов = не заполнено, в отличие от `isNotEmpty`). Новый
   локализованный ключ `farm_name_required` = «Укажите название фермы» во
   всех 9 `.arb`. `FarmNameStepPage` обёрнут в `Form`+`GlobalKey<FormState>`,
   поле использует новый валидатор.
2. **Кнопка на шаге названия** — больше не скрывается при невозможности
   продолжить (`_CircularProgressButton.canProceed` для шага `.name` теперь
   всегда `true`); по тапу — `_nameFormKey.currentState?.validate()`,
   переход только при успехе. Остальные шаги (`address`/`kindsVisibility`) —
   поведение не тронуто.
3. **Клавиатура** — `FarmNameStepPage` обёрнут в `SingleChildScrollView`
   (`keyboardDismissBehavior: onDrag`), кнопка на шаге названия получает
   компенсирующий `Padding` на `MediaQuery.viewInsets.bottom` (только для
   этого шага — `Scaffold.resizeToAvoidBottomInset: false` не тронут, чтобы
   не сломать шаг адреса). Закрытие клавиатуры по тапу вне поля уже было
   реализовано в базовом `RTextField` (`onTapOutside`) — не потребовалось
   отдельно.
4. **Двойной тап** — `FarmCreateState.isSubmitting` (freezed, codegen
   прогнан), `FarmCreateCubit.saveFarm()` — guard в начале + `try/finally`,
   сбрасывающий флаг независимо от результата. FAB игнорирует тап во время
   сабмита.
5. Заодно исправлена устаревшая ссылка в `UC-1`→`UC-315` на мёртвый
   `FarmsAndPlacesBloc._onAddFarm` — код не менялся (ссылка была только в
   спеке), но подтверждено построчно, что `FarmCreateCubit.saveFarm()` —
   единственный живой путь.

Название при возврате на предыдущий шаг сохраняется — не менялось, уже
работало корректно.

## Проверено

- `dart run build_runner build --workspace --delete-conflicting-outputs` —
  успешно (для `FarmCreateState.isSubmitting`).
- `flutter analyze` по всем 6 изменённым `.dart`-файлам — без замечаний.
- `flutter test test/pages/farm_create_cubit_test.dart
  test/utilts/validator_test.dart test/pages/farms_and_places_bloc_test.dart`
  — все тесты (91 в сумме по первым двум файлам) проходят.
- Добавлены новые тесты: `UC-315 — Validator.isNotBlank` (4 кейса, включая
  строку из пробелов) в `validator_test.dart`; `UC-315: повторный вызов
  saveFarm...` (двойной тап через `Completer`, проверка что репозиторий
  вызван ровно 1 раз) в `farm_create_cubit_test.dart`.
- `dart format` применён.

## Отложено / не сделано

- Widget-тест на сам `FarmNameStepPage`/`_CircularProgressButton` (что поле
  реально подсвечивается, кнопка реально не перекрыта клавиатурой) — не
  написан, только логика на уровне кубита/валидатора покрыта юнит-тестами;
  визуальная часть (реальное позиционирование над клавиатурой на разных
  размерах экрана) не проверялась на устройстве/эмуляторе.
