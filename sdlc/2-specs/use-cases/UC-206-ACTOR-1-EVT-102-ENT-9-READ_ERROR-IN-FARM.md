# UC-206 — Просмотр карточки фермы отказывает — нет обработки ошибок вообще, экран навсегда остаётся в загрузке

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-102](../events/EVT-102-FARM-CARD-VIEWED-IN-FARM.md) |
| Сущность | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Тот же сценарий, что [UC-205](UC-205-ACTOR-1-EVT-102-ENT-9-READ_OK-IN-FARM.md),
но любой из репозиторных вызовов внутри `MainNavigatorCubit.load()` бросает
исключение — **подтверждённый чтением кода дефект**: `load()` не имеет ни
одного `try/catch`, а `MainNavigatorState` не имеет `error`-варианта вообще.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — тот же, что в
[UC-205](UC-205-ACTOR-1-EVT-102-ENT-9-READ_OK-IN-FARM.md).

## CURRENT

### Основной поток

1. `MainNavigatorCubit.load()` вызывает `_farmsRepository.getAll()`,
   `_farmsRepository.getAnimalsForFarm(...)`, `_placeRepository.getAllWithThisFarmIdWithAnimals(...)`
   без единого `try/catch` вокруг них.
2. Если любой из этих вызовов бросает исключение — оно не перехватывается
   методом `load()`.

### Альтернативные потоки

- **Первый вызов из конструктора.** `MainNavigatorCubit()` вызывает `load()`
  без `await` и без обработки — необработанное исключение уходит в
  error-зону Dart/Flutter (конкретное поведение зависит от того, как Zone
  перехватит unhandled Future error), `MainNavigatorState` остаётся
  `initial` — экран показывает бесконечный `CircularProgressIndicator`,
  подтверждённого пути показать пользователю ошибку нет.
- **Повторный вызов из реактивных подписок.** Подписки на
  `_farmsRepository.watchAll()`/`_placeRepository.watchAll()`/
  `_animalsRepository.watchAll()`/`_weighingsRepository.watchAll()` вызывают
  `load()` без `onError` — тот же класс отказа, каждый раз, когда стрим
  эмитит во время сбоя источника данных.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — `getAllWithThisFarmIdWithAnimals`
  тоже может бросить исключение, тот же необработанный путь.

### Бизнес-правила

- Нет разделения ошибок по типу — потому что нет обработки ошибок вовсе.
  Единственное наблюдаемое пользователем поведение — экран остаётся в
  состоянии загрузки бессрочно.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — дефект воспроизводится статическим
чтением кода (`MainNavigatorState` — только `initial`/`loaded`, `load()` —
без `try/catch`).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` | `MainNavigatorCubit.load` | CURRENT | источник дефекта — без `try/catch` |
| `lib/pages/main_navigator/cubit/main_navigator_state.dart` | `MainNavigatorState` | CURRENT | только `initial`/`loaded`, нет `error` |

## Критерии приёмки

- Исключение из любого репозиторного вызова внутри `load()` -> необработанное
  исключение, `MainNavigatorState` не меняется (остаётся `initial`, если это
  первый вызов).

## Связанные тесты

TBD — теста нет (см. [UC-205](UC-205-ACTOR-1-EVT-102-ENT-9-READ_OK-IN-FARM.md)
— тестового файла для `MainNavigatorCubit` не существует вовсе).

## Открытые вопросы и ограничения

Не проверено экспериментально (только статическим чтением кода), как именно
Flutter/Dart-зона обрабатывает необработанное исключение из `Future`,
запущенного без `await` в конструкторе `Cubit` — крашит ли это приложение,
или тихо теряется в `Zone.current.handleUncaughtError`. В любом случае
пользователь не получает структурированного сообщения об ошибке.
