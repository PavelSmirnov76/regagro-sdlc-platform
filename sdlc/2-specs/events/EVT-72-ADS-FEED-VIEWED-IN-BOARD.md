# EVT-72 — ads.feed_viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Пользователь (гость или авторизованный — маршрут `/board` без
route-guard) открывает вкладку «Доска», ищет по названию (debounce 450мс),
открывает диалог фильтров (вид/порода/масть/тип объявления), скроллит для
подгрузки следующей страницы, делает pull-to-refresh — `BoardCubit.load`/
`loadNextPage`/`refresh`/`applySearchText`/`applyBoardFilters`.

**Эффект.** `AdRepository.getAds` — постраничная лента (`GET /ads`).
**Известные дефекты**: множественный выбор фильтров (вид/порода/масть)
реально применяет только первое выбранное значение каждого списка, остальные
выборы визуально сохраняются, но не влияют на результат (см.
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md)); `loadNextPage`/`refresh`/
`applySearchText`/`applyBoardFilters` не форвардят текущий режим
(`isMyAds`/`isFavouriteAds`) — эти четыре метода делят один и тот же дефект
с [EVT-74](EVT-74-MY-ADS-VIEWED-IN-BOARD.md)/[EVT-75](EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md),
подробно разобрано там.

**Исходный код.** `lib/pages/board/presentation/board_view.dart` → `_SearchBar`;
`lib/pages/board/cubit/board_cubit.dart` → `BoardCubit.load`, `loadNextPage`,
`refresh`, `applySearchText`, `applyBoardFilters`; `lib/pages/board/board_filters/board_filters_bloc.dart` →
`BoardFiltersBloc`; `lib/repositories/board/ad_repository.dart` → `AdRepository.getAds`.
