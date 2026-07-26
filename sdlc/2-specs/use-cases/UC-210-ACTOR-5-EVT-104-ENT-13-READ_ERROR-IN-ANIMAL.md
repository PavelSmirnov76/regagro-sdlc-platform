# UC-210 — Просмотр хаба неотправленных перемещений отказывает — ошибка неотличима от «пусто»

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-104](../events/EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же сценарий, что [UC-209](UC-209-ACTOR-5-EVT-104-ENT-13-READ_OK-IN-ANIMAL.md),
но репозиторный вызов бросает исключение — **подтверждённый тестом дефект**:
двойной `try/catch` (в `load()` и в `_reload()`) в итоге эмитит
`UnsentMovementsState.empty()` — то же состояние, что и при реальном
отсутствии данных, `UnsentMovementsState` не имеет `error`-варианта вовсе.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — тот же, что в
[UC-209](UC-209-ACTOR-5-EVT-104-ENT-13-READ_OK-IN-ANIMAL.md).

## CURRENT

### Основной поток

1. `load()`: `try { emit(loading()); await _reload(); } catch (e) {
   emit(UnsentMovementsState.empty()); }`.
2. `_reload()` сама уже обёрнута в свой собственный `try/catch`:
   `try { final movements = await _movementReportRepository.getMovementsWithDetailsByFilters(sync: false);
   ...; emit(...); } catch (e) { if (!isClosed) emit(UnsentMovementsState.empty()); }`
   — внешний `catch` в `load()` избыточен, так как исключение из
   репозитория уже перехвачено внутри `_reload()`.
3. Экран показывает `ProgressMessage.notFound(message: l10n.list_is_empty)` —
   визуально неотличимо от случая, когда неотправленных перемещений
   действительно нет.

### Альтернативные потоки

Нет — единственный путь отказа.

### Связанные сущности

Нет дополнительных.

### Бизнес-правила

- `UnsentMovementsState.empty()` — единственное состояние и для «данных нет»,
  и для «загрузка не удалась». Пользователь не узнает, что произошла ошибка
  БД/сети, а не реальное отсутствие неотправленных перемещений.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — дефект подтверждён существующим тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.load`, `_reload` (оба catch) | CURRENT | источник дефекта — ошибка маскируется под «пусто» |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_state.dart` | `UnsentMovementsState` | CURRENT | нет `error`-варианта вовсе |

## Критерии приёмки

- Исключение из `getMovementsWithDetailsByFilters` -> `UnsentMovementsState.empty()`
  (не отличимо от реального «пусто»).

## Связанные тесты

- `test/pages/unsent_movements_cubit_test.dart`, группа `'UC-210 —
  UnsentMovementsCubit.load'` (ранее `'UC-148 — UnsentMovementsCubit.load'` —
  число принадлежало старой, дорефакторинговой нумерации, переименована в
  рамках этого же прохода) — тест `'ошибка репозитория -> empty (не
  error)'`.

## Открытые вопросы и ограничения

Тот же класс дефекта, что и у [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
(инвентаризация) и у ряда других хабов неотправленных записей в модуле — не
исправлено ни в одном из них в рамках документирующего прохода.
