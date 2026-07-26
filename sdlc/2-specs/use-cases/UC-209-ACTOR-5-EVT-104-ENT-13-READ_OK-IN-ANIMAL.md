# UC-209 — Просмотр хаба ещё не отправленных перемещений успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-104](../events/EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Хаб ещё не отправленных перемещений — список для последующей отмены
([EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)). Ранее
отложенный пробел (часть `R26` из PRD, наравне с уже специфицированным
удалением) — закрыт этим же способом, что и аналогичные read-экраны
VAC/WEIGH/DISP/INV.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — тот же, что для остальных
сценариев MOVE.

## CURRENT

### Основной поток

1. `UnsentMovementsPage` создаёт `UnsentMovementsCubit()..load()`, обычно
   открывается со сводного экрана «В работе».
2. `load()`: `emit(UnsentMovementsState.loading())`, затем `await _reload()`.
3. `_reload()`: `movements = await _movementReportRepository.getMovementsWithDetailsByFilters(sync: false)`.
4. `emit(movements.isEmpty ? UnsentMovementsState.empty() :
   UnsentMovementsState.loaded(movements: movements))`.
5. `UnsentMovementsPopulated` рендерит список; тап по перемещению открывает
   дневной отчёт с `isUnsent: true` ([EVT-105](../events/EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)).

### Альтернативные потоки

- **Список пуст.** Нет ни одного ещё не отправленного перемещения ->
  `UnsentMovementsState.empty()` — то же состояние, что и при ошибке загрузки
  (см. [UC-210](UC-210-ACTOR-5-EVT-104-ENT-13-READ_ERROR-IN-ANIMAL.md)).
- **Реактивная перезагрузка.** Подписка на
  `_movementReportRepository.watchNotSyncMovements()` вызывает `_reload()`
  заново при любом изменении набора неотправленных перемещений.

### Связанные сущности

Нет дополнительных — сценарий целиком в рамках [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md).

### Бизнес-правила

- `getMovementsWithDetailsByFilters(sync: false)` — тот же репозиторный метод,
  что использует и удаление ([EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)),
  фильтр `sync: false` идентичен.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.load`, `_reload` | CURRENT | загрузка хаба неотправленных |
| `lib/pages/animal_movement/presentation/unsent_movement/unsent_movements_page.dart` | `UnsentMovementsPage` | CURRENT | экран |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | источник данных |

## Критерии приёмки

- Успех, есть данные -> `UnsentMovementsState.loaded(movements: ...)`.
- Успех, пусто -> `UnsentMovementsState.empty()`.

## Связанные тесты

- `test/pages/unsent_movements_cubit_test.dart`, группа `'UC-209 —
  UnsentMovementsCubit.load'` (ранее `'UC-147 — UnsentMovementsCubit.load'` —
  число принадлежало старой, дорефакторинговой нумерации, переименована в
  рамках этого же прохода) — тесты `'успех, есть данные -> loaded'` и
  `'успех, пусто -> empty'`.

## Открытые вопросы и ограничения

Нет.
