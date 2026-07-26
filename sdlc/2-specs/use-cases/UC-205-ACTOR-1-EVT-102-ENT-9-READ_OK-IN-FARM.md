# UC-205 — Просмотр карточки фермы со сводной статистикой и переключение между фермами успешно

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-102](../events/EVT-102-FARM-CARD-VIEWED-IN-FARM.md) |
| Сущность | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Стартовый экран приложения — карточка текущей фермы пользователя со сводной
статистикой (список отделений и количество животных на каждом), с
возможностью пролистать другие фермы того же пользователя свайпом. Ранее
отложенный пробел (`R3`/`R4` из PRD) — закрыт этим же способом, что и
остальные read-экраны модуля.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — переиспользован из AUTH, как и
для остальных use-case FARM.

## CURRENT

### Основной поток

1. `MainNavigatorPage` создаёт `MainNavigatorCubit`, который в конце своего
   конструктора вызывает `load()` (без ожидания).
2. `load()`: `farms = await _farmsRepository.getAll()`, фильтрует
   `isDeleted != true`. Для каждой фермы — `_farmsRepository.getAnimalsForFarm(farm.remoteId)`,
   счётчики за год (вакцинации/отчёты/животные), `_placeRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)`.
3. Собирает список `FarmWithDetails` (ферма, животные, места с животными,
   счётчики), сохраняет текущий индекс фермы, если он ещё валиден, иначе
   сбрасывает на 0.
4. `emit(MainNavigatorState.loaded(MainNavigatorData(farms: ..., currentFarmIndex: ...)))`.
5. `FarmStatisticsWidget` показывает `farmWithDetails.animals.length` как
   общее число животных и список карточек мест (`_buildPlaceCard`) по
   `farmWithDetails.placesWithAnimals`. Тап по карточке места — переход в
   [EVT-103](../events/EVT-103-PLACE-CARD-VIEWED-IN-FARM.md).

### Альтернативные потоки

- **Переключение между фермами (R4).** Горизонтальный свайп внутри того же
  `MainNavigatorPopulated` (`onHorizontalDragUpdate`/`onHorizontalDragEnd`,
  порог `_triggerProgress = 0.58` от `_maxDragExtent = 56`px, либо по скорости
  жеста `_velocityThreshold = 900`) вызывает `cubit.moveToNextFarm()` /
  `cubit.moveToPreviousFarm()`. Оба метода — чистый `emit` нового
  `currentFarmIndex` (с проверкой границ `canMoveToNextFarm`/
  `canMoveToPreviousFarm`) по уже загруженному в память списку `farms` — без
  повторного обращения к репозиториям и без персистентности (см.
  [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)). Визуальные "ручки"-стрелки
  `FarmNavigationHandle` показываются слева/справа только если есть куда
  листать.
- **Реактивная перезагрузка.** Подписки на `_farmsRepository.watchAll()`,
  `_placeRepository.watchAll()`, `_animalsRepository.watchAll()`,
  `_weighingsRepository.watchAll()` — каждая при эмите вызывает `load()`
  заново (без `onError`, см. [UC-206](UC-206-ACTOR-1-EVT-102-ENT-9-READ_ERROR-IN-FARM.md)).

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — через
  `placesWithAnimals`, каждая ферма показывает свои места.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) — счётчик
  общего числа животных и счётчики за год читают эту сущность, не редактируют.

### Бизнес-правила

- `currentFarmIndex` сохраняется между вызовами `load()`, если он ещё валиден
  для нового списка ферм (не сбрасывается на 0 просто потому, что где-то в БД
  что-то изменилось) — но это не персистентность: новый инстанс
  `MainNavigatorCubit` (hot-restart, повторный заход на экран) всегда стартует
  с `currentFarmIndex: 0`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` | `MainNavigatorCubit.load`, `moveToNextFarm`, `moveToPreviousFarm` | CURRENT | загрузка списка ферм со статистикой, переключение |
| `lib/pages/main_navigator/presentation/widgets/farm_statistics_widget.dart` | `FarmStatisticsWidget` | CURRENT | рендер карточки фермы и списка мест |
| `lib/pages/main_navigator/presentation/widgets/main_navigator_populated.dart` | `MainNavigatorPopulated` | CURRENT | свайп-жест переключения ферм |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAll`, `getAnimalsForFarm` | CURRENT | источник данных фермы/животных |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmIdWithAnimals` | CURRENT | источник мест с животными |

## Критерии приёмки

- `MainNavigatorCubit.load()` успешно -> `MainNavigatorState.loaded` со
  списком `FarmWithDetails`, каждая со своими `placesWithAnimals`.
- `moveToNextFarm()`/`moveToPreviousFarm()` двигают `currentFarmIndex` в
  границах списка, без обращения к репозиториям.

## Связанные тесты

TBD — теста нет. Тестового файла для `MainNavigatorCubit` не существует
(проверено — ни один файл в `test/` не упоминает этот класс).

## Открытые вопросы и ограничения

Полный пробел в тестовом покрытии — не только для этого сценария, но и для
[UC-206](UC-206-ACTOR-1-EVT-102-ENT-9-READ_ERROR-IN-FARM.md) (тот же кубит).
