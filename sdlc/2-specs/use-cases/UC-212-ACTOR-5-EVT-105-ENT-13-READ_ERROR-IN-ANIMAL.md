# UC-212 — Просмотр посуточного отчёта по перемещениям отказывает корректно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-105](../events/EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же сценарий, что [UC-211](UC-211-ACTOR-5-EVT-105-ENT-13-READ_OK-IN-ANIMAL.md),
но `_movementRepo.getMovementsWithDetailsByFilters` бросает исключение — в
отличие от соседних сценариев этого модуля ([UC-210](UC-210-ACTOR-5-EVT-104-ENT-13-READ_ERROR-IN-ANIMAL.md),
маскирующего ошибку под «пусто», и `deleteEvent` в этом же кубите, глотающего
исключение полностью пустым `catch (_) {}`), здесь ошибка обрабатывается
**корректно**.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — тот же, что в
[UC-211](UC-211-ACTOR-5-EVT-105-ENT-13-READ_OK-IN-ANIMAL.md).

## CURRENT

### Основной поток

1. `load(args)`: `emit(loading())`, затем внутри `try` —
   `_movementRepo.getMovementsWithDetailsByFilters(sync: null)` бросает
   исключение.
2. `catch (e) { emit(MovementReportState.error(e.toString())); }` —
   исключение перехвачено, эмитится специальный `error`-стейт с текстом
   исключения.
3. `MovementReportView` отображает `Center(child: Text(msg, ...))` —
   пользователь видит текст ошибки (сырой `e.toString()`, не локализованное
   сообщение).

### Альтернативные потоки

Нет — единственный путь отказа.

### Связанные сущности

Нет дополнительных.

### Бизнес-правила

- `error(message)` — отдельное, самостоятельное состояние `MovementReportState`
  (в отличие от `UnsentMovementsState`, где такого варианта нет вовсе, см.
  [UC-210](UC-210-ACTOR-5-EVT-104-ENT-13-READ_ERROR-IN-ANIMAL.md)) — сообщение
  не локализовано, сырой `e.toString()`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.load` (catch) | CURRENT | корректная обработка ошибки |
| `lib/pages/movement_report/cubit/movement_report_state.dart` | `MovementReportState.error` | CURRENT | отдельный error-вариант |

## Критерии приёмки

- Исключение из `getMovementsWithDetailsByFilters` -> `MovementReportState.error(e.toString())`.

## Связанные тесты

- `test/pages/movement_report_cubit_test.dart`, группа `'UC-212 —
  MovementReportCubit.load'` (ранее `'UC-150 — MovementReportCubit.load'` —
  число принадлежало старой, дорефакторинговой нумерации, переименована в
  рамках этого же прохода) — тест `'ошибка репозитория -> error с текстом
  исключения'`.

## Открытые вопросы и ограничения

Нет.
