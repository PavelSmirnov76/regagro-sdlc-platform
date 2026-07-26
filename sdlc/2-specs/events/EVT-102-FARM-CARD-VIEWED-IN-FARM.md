# EVT-102 — farm_card.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |

**Триггер.** Стартовый экран приложения (`MainNavigatorPage`) открывается или
перезагружается реактивно (изменение в фермах/местах/животных/взвешиваниях);
`MainNavigatorCubit.load()`.

**Эффект.** Загружает все не удалённые фермы пользователя, для каждой — её
животных, счётчики за год (вакцинации/отчёты/животные) и список её мест с
привязанными животными (`FarmWithDetails`/`PlaceWithAnimals`), сохраняя (по
возможности) индекс текущей выбранной фермы. Включает также переключение
между уже загруженными фермами (`moveToNextFarm`/`moveToPreviousFarm`) — тот
же кубит и тот же экран, чисто in-memory сдвиг `currentFarmIndex` по уже
загруженному списку, без повторного обращения к репозиториям и без
персистентности выбора (см. [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)).
Тап по карточке места ведёт в [EVT-103](EVT-103-PLACE-CARD-VIEWED-IN-FARM.md).

**Исходный код.** `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` →
`MainNavigatorCubit.load`, `moveToNextFarm`, `moveToPreviousFarm`;
`lib/pages/main_navigator/presentation/widgets/farm_statistics_widget.dart` →
`FarmStatisticsWidget`; `lib/pages/main_navigator/presentation/widgets/main_navigator_populated.dart`
→ `MainNavigatorPopulated` (свайп-жест переключения ферм).
