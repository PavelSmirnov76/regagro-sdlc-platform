- **business task**: `BT-23` ([`../1-business-tasks/planning/BT-23-PLANNING-FARM-NAME-VALIDATION-KEYBOARD.md`](../1-business-tasks/planning/BT-23-PLANNING-FARM-NAME-VALIDATION-KEYBOARD.md))
- **spec**: `UC-315` ([`../2-specs/use-cases/UC-315-ACTOR-1-EVT-1-ENT-1-CREATE_OK-IN-FARM.md`](../2-specs/use-cases/UC-315-ACTOR-1-EVT-1-ENT-1-CREATE_OK-IN-FARM.md), supersedes `UC-1`), `ENT-1`
- **design**: нет `FIG-{n}` и не будет — по этому тикету дизайн-стадия не запускается (см. raw `SHEEP-4-clarifications.md`, «Общее»); визуальный вид ошибки поля — стандартный механизм `Form`/`TextFormField`, уже используемый в проекте
- **tracker**: нет подключённого трекера (Yandex Tracker MCP недоступен в этой сессии) — по `RUNBOOK.md` шаг 6, этот файл является записью учёта. Внешний тикет-источник — `SHEEP-4`, пункт чек-листа 8

# Регистрация фермы: обязательность названия, клавиатура, защита от двойного тапа

## Объём

Три независимые правки на визарде регистрации фермы
(`lib/pages/farms_and_places/sub_pages/farms_create/`):

1. **Валидация названия** (шаг «Название», `FarmNameStepPage`):
   - Добавить `validator` в `RTextFieldSimple` (`lib/widgets/text_field/text_field.dart:436-486`) — проброс в уже поддерживающий его `RTextField.outline`.
   - Обернуть `FarmNameStepPage` в `Form`+`GlobalKey<FormState>`.
   - Добавить в `Validator` (`lib/utilts/validator.dart`) trim-aware проверку (строка из пробелов = не заполнено), локализованное сообщение «Укажите название фермы» (новый ключ, через `/add-translation`).
   - Кнопка перехода на шаге названия — не скрывать при `canProceed == false`, как сейчас (`_CircularProgressButton`, `farm_create_page.dart:295-310`); вместо этого — всегда тапабельна, по тапу `formKey.currentState!.validate()`, при неудаче — стандартная подсветка поля + сообщение, без перехода. **Остальные шаги (адрес, виды) не трогать** — их текущий паттерн «скрывать кнопку» вне объёма этой задачи.

2. **Клавиатура** (тот же шаг): обеспечить видимость поля и кнопки при открытой клавиатуре — прокрутка и/или поправка позиции `floatingActionButton` на `MediaQuery.of(context).viewInsets.bottom` (сейчас `resizeToAvoidBottomInset: false` без компенсации для FAB, `farm_create_page.dart:141-204`). Ориентир — уже работающий паттерн в `registration_view.dart` (дефолтный `resizeToAvoidBottomInset` + `SingleChildScrollView`).

3. **Двойной тап** (последний шаг, сохранение): добавить `isSubmitting`-подобный флаг в `FarmCreateState`/`FarmCreateCubit`, защитить `saveFarm()` (`farm_create_cubit.dart:294-304`) от повторного вызова — по образцу `RegistrationCubit`/`RegistrationState` (`isSubmitting`, кнопка игнорирует тап во время сабмита).

Названия при возврате на предыдущий шаг уже сохраняются корректно — не трогать, регрессия исключена по построению (`FarmCreateState.farm` — общее состояние на весь визард).

Полное обоснование и CURRENT/TARGET — `UC-315`.

## Критерии приёмки (definition of done)

- [ ] Без заполнения (или только с пробелами) названия перейти дальше со шага названия нельзя.
- [ ] При попытке продолжить без названия — поле подсвечивается, показывается «Укажите название фермы».
- [ ] После ввода корректного названия переход становится доступен.
- [ ] Клавиатура не перекрывает поле и кнопку перехода на шаге названия, на разных размерах экрана.
- [ ] При возврате на предыдущий шаг название сохраняется.
- [ ] Двойное нажатие на кнопку сохранения не создаёт две фермы.
- [ ] Шаги «Адрес» и «Виды» — без изменений в поведении.

## Реализационные заметки

- Не переписывать `_CircularProgressButton` целиком — точечно изменить canProceed/onTap только для ветки шага названия в месте его использования (`farm_create_page.dart:171-187`), сохранив текущее поведение для других шагов.
- Переиспользовать `Validator`/`Form`-паттерн, уже применённый в самом `farm_create_page.dart` (`GlobalKey<FormState>`+`validator`+`isSubmitting`) — не изобретать новый.
- Тест `test/pages/farms_and_places_bloc_test.dart` (группа `UC-1`) тестирует мёртвый обработчик (`FarmsAndPlacesBloc._onAddFarm`) — не переименовывать на `UC-315`, он не отражает реальный путь; завести новый тест на `FarmCreateCubit`/`FarmNameStepPage` с якорем `UC-315`.

## Зависимости

Нет блокирующих зависимостей — весь нужный паттерн (`Form`+`validator`+`isSubmitting`) уже есть в проекте в другом флоу, переиспользуется, не создаётся с нуля.
