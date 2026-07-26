# EVT-75 — favourite_ads.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** `Routes.favouriteAds` — маршрут и экран полностью реализованы
(`FavouriteAdsPage`/`BoardCubit()..load(page: 1, isFavouriteAds: true)`), но
**не имеет ни одной живой точки входа в UI**: переход из ленты закомментирован,
кнопка «Избранное» в профиле видима, но её `onTap` — пустой коллбэк, а кнопка
избранного на детальной карточке (единственный путь добавить объявление в
избранное без бага, см. [EVT-71](EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md))
тоже закомментирована. R55 (просмотр избранного) практически недостижим из
живого UI на момент этой спецификации — открыть экран можно только прямой
навигацией в обход штатного UI (deep-link/`context.go`).

**Эффект.** `AdRepository.getFavouriteAds` — `GET /selected-ads`, всегда
`page = 1, isLastPage = true` (сервер не поддерживает пагинацию для этого
списка). Тот же дефект нефорвардинга режима, что у
[EVT-74](EVT-74-MY-ADS-VIEWED-IN-BOARD.md) — `refresh()`/поиск/фильтры
откатываются к обычной ленте.

**Исходный код.** `lib/pages/favourite_ads/presentation/favourite_ads_view.dart`;
`lib/pages/board/cubit/board_cubit.dart` → `BoardCubit.load`; `lib/repositories/board/ad_repository.dart` →
`AdRepository.getFavouriteAds`; `lib/pages/routes.dart` → регистрация `Routes.favouriteAds`.
