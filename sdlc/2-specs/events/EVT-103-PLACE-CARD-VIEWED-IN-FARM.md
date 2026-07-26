# EVT-103 — place_card.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-3](../modules/MOD-3-FARM.md) |
| Сущность(и) | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

**Триггер.** Пользователь открывает карточку отдельного места — обычно тапом
по месту с экрана [EVT-102](EVT-102-FARM-CARD-VIEWED-IN-FARM.md); `PlaceCubit.load()`
(конструктор кубита получает `farmRemoteId`/`initialPlaceRemoteId`, опционально
уже готовые `initialFarm`/`initialPlace` для мгновенного первого рендера до
завершения `load()`).

**Эффект.** Загружает ферму и все её места вместе с закреплёнными животными,
строит список `PlaceWithAnimals`, пересчитывает текущий индекс места (стараясь
сохранить выбранное по `idRemote`). Включает также переключение между местами
той же фермы (`moveToNextPlace`/`moveToPreviousPlace`) — чисто in-memory сдвиг
`currentPlaceIndex` по уже загруженному списку, аналогично переключению ферм в
[EVT-102](EVT-102-FARM-CARD-VIEWED-IN-FARM.md).

**Исходный код.** `lib/pages/place/cubit/place_cubit.dart` → `PlaceCubit.load`,
`moveToNextPlace`, `moveToPreviousPlace`; `lib/pages/place/place_page.dart` →
`PlacePage`; `lib/pages/place/widgets/place_structure_widget.dart` →
`PlaceStructureWidget`.
