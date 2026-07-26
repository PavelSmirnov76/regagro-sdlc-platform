# UC-208 — Просмотр карточки места отказывает — исключение проглочено, старые данные показаны молча

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-103](../events/EVT-103-PLACE-CARD-VIEWED-IN-FARM.md) |
| Сущность | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Тот же сценарий, что [UC-207](UC-207-ACTOR-1-EVT-103-ENT-10-READ_OK-IN-FARM.md),
но `load()` бросает исключение — **подтверждённый тестом дефект**: `catch (_)
{ emit(state.copyWith(isLoading: false)); }` полностью проглатывает
исключение без логирования, `data` остаётся без изменений (старые/пустые
данные), `PlaceState`/`PlaceData` не имеют отдельного `error`-поля вовсе.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — тот же, что в
[UC-207](UC-207-ACTOR-1-EVT-103-ENT-10-READ_OK-IN-FARM.md).

## CURRENT

### Основной поток

1. `PlaceCubit.load()`: `emit(isLoading: true)`, затем внутри `try` —
   `_farmRepository.getById`/`getAnimalsForFarm`, `_placeRepository.getAllWithThisFarmId`.
2. Любое из этих обращений бросает исключение (например, БД-ошибка) ->
   `catch (_) { emit(state.copyWith(isLoading: false)); }`.
3. `isLoading` сбрасывается в `false`, но `data` (`farm`/`places`/
   `currentPlaceIndex`) остаётся тем же, что было до вызова — либо старыми
   данными (если это повторный `load()`), либо начальными/переданными через
   `initialFarm`/`initialPlace` (если это первый вызов).

### Альтернативные потоки

Нет — единственный путь отказа, тот же для первого и для повторных вызовов
`load()` (включая вызовы из реактивных подписок).

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — `FarmRepository.getById`/
  `getAnimalsForFarm` тоже могут бросить исключение, тот же проглоченный путь.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL).

### Бизнес-правила

- `catch (_) {}` — полностью пустой, без логирования (в отличие, например, от
  `UnsentMovementsCubit.deleteGroup`, где хотя бы есть `Talker`). Пользователь
  не может отличить «данные не изменились, потому что ничего не изменилось» от
  «данные не изменились, потому что произошла ошибка загрузки».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — дефект подтверждён существующим тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/place/cubit/place_cubit.dart` | `PlaceCubit.load` (catch) | CURRENT | источник дефекта — пустой `catch (_)` |
| `lib/pages/place/cubit/place_state.dart` | `PlaceState`, `PlaceData` | CURRENT | нет `error`-варианта вовсе |

## Критерии приёмки

- Исключение внутри `load()` -> `isLoading` сброшен на `false`, `data` не
  изменён (ни `farm`, ни `places`, ни `currentPlaceIndex`).

## Связанные тесты

- `test/pages/place_cubit_test.dart`, группа `'UC-208 — PlaceCubit.load
  READ_ERROR'` (ранее часть `'PlaceCubit — конструктор + load'`, вынесена в
  отдельную группу и переименована в рамках этого же прохода) — тест
  `'исключение при загрузке -> isLoading сброшен, данные не тронуты'`.

## Открытые вопросы и ограничения

Нет.
