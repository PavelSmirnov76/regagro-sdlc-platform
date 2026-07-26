# UC-207 — Просмотр карточки места со списком закреплённых животных и переключение между местами успешно

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-103](../events/EVT-103-PLACE-CARD-VIEWED-IN-FARM.md) |
| Сущность | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |

## Назначение

Карточка отдельного места (отделения) фермы — название, площадь/описание,
структура закреплённых животных по видам, с возможностью пролистать другие
места той же фермы свайпом. Ранее отложенный пробел (`R10` из PRD) — закрыт
этим же способом, что и остальные read-экраны модуля.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — тот же, что в
[UC-205](UC-205-ACTOR-1-EVT-102-ENT-9-READ_OK-IN-FARM.md).

## CURRENT

### Основной поток

1. Пользователь тапает по карточке места на экране
   [EVT-102](../events/EVT-102-FARM-CARD-VIEWED-IN-FARM.md) —
   `context.pushNamed2(Routes.place, extra: PlacePageArgs(placeWithAnimals: place, farm: farmWithDetails))`.
2. `PlacePage` создаёт `PlaceCubit(farmRemoteId, initialPlaceRemoteId, initialFarm, initialPlace)`
   — переданные `initialFarm`/`initialPlace` используются для мгновенного
   первого рендера до завершения `load()`.
3. `load()`: guard `if (state.isLoading) return`, затем `emit(isLoading: true)`.
   `farm = await _farmRepository.getById(farmRemoteId)`.
4. Если `farm != null`: `_farmRepository.getAnimalsForFarm(farmRemoteId)`,
   `_placeRepository.getAllWithThisFarmId(farmRemoteId)`, вручную строит
   `placesWithAnimals` (фильтрует животных по `placeId == place.idRemote}`
   для каждого места), пересчитывает `currentPlaceIndex` (стараясь сохранить
   выбранное место по `idRemote`).
5. `emit(state.copyWith(isLoading: false, data: PlaceData(farm: ..., places:
   placesWithAnimals, currentPlaceIndex: ...)))`.
6. `PlaceStructureWidget` показывает структуру по видам через
   `PlaceKindGroup.fromPlace(placeWithAnimals)`; тап по группе ведёт в список
   животных этого вида/места (`Routes.animalsRegistry`).

### Альтернативные потоки

- **Ферма не найдена.** `farm == null` — если список `places` уже пуст, `data`
  сбрасывается на `PlaceData.initial()`, иначе просто снимается `isLoading`;
  в обоих случаях ранний `return` — не считается ошибкой сама по себе, экран
  показывает пустое состояние.
- **Переключение между местами (по аналогии с R4 у ферм).** `moveToNextPlace()`/
  `moveToPreviousPlace()` — чистый `emit` нового `currentPlaceIndex` по уже
  загруженному в память списку `places`, без повторного обращения к
  репозиториям.
- **Реактивная перезагрузка.** Подписки на `_animalsRepository.watchAll()`,
  `_weighingsRepository.watchAll()`, `_placeRepository.watchAll()` — каждая
  вызывает `load()` заново; сам `load()` защищён внутренним `try/catch` (см.
  [UC-208](UC-208-ACTOR-1-EVT-103-ENT-10-READ_ERROR-IN-FARM.md)), поэтому
  необработанного исключения из этих подписок не возникает.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — место всегда
  показывается в контексте своей фермы.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) — список
  закреплённых животных читает эту сущность, не редактирует.

### Бизнес-правила

- `currentPlaceIndex` пересчитывается на каждом `load()`, стараясь сохранить
  фактически выбранное место, а не просто индекс — тот же паттерн, что у
  `currentFarmIndex` в [EVT-102](../events/EVT-102-FARM-CARD-VIEWED-IN-FARM.md).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/place/cubit/place_cubit.dart` | `PlaceCubit.load`, `moveToNextPlace`, `moveToPreviousPlace` | CURRENT | загрузка карточки места, переключение |
| `lib/pages/place/place_page.dart` | `PlacePage` | CURRENT | экран места |
| `lib/pages/place/widgets/place_structure_widget.dart` | `PlaceStructureWidget` | CURRENT | структура по видам |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById`, `getAnimalsForFarm` | CURRENT | источник данных фермы/животных |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmId` | CURRENT | источник списка мест |

## Критерии приёмки

- `PlaceCubit.load()` успешно -> `places` сгруппированы по месту,
  `currentPlaceIndex` указывает на `initialPlaceRemoteId`.
- Ферма не найдена, `places` пуст -> `data` сброшен на `PlaceData.initial()`.
- `moveToNextPlace()`/`moveToPreviousPlace()` двигают `currentPlaceIndex` в
  границах списка.

## Связанные тесты

- `test/pages/place_cubit_test.dart`, группа `'UC-207 — PlaceCubit.load
  READ_OK'` (ранее `'PlaceCubit — конструктор + load'`, переименована в
  рамках этого же прохода; содержит тесты `'успех -> places сгруппированы по
  месту, currentPlaceIndex указывает на initialPlaceRemoteId'` и `'ферма не
  найдена, places пуст -> data сброшен на initial'`), группа `'PlaceCubit —
  навигация'` (тест `'moveToNextPlace/moveToPreviousPlace двигают
  currentPlaceIndex в границах списка'`), группа `'PlaceCubit — реактивные
  подписки'` (тест `'изменение в списке животных триггерит повторный
  load()'`) — обе последние оставлены без `UC`-префикса, так как относятся к
  тому же сценарию, не отдельному use-case.

## Открытые вопросы и ограничения

Нет.
