# EVT-74 — my_ads.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Пользователь открывает «Мои объявления» — иконка «коллекция» в
шапке ленты либо кнопка в профиле — `BoardCubit()..load(page: 1, isMyAds: true)`.

**Эффект.** `AdRepository.getMyAds` — `GET /ads?user_id=...`. **Известный
дефект**: `BoardCubit` не хранит `isMyAds` как персистентный режим состояния —
`loadNextPage`/`refresh`/`applySearchText`/`applyBoardFilters` вызывают
внутренний `load()` без передачи текущего режима, откатываясь к дефолтному
`isMyAds: false`. Практически: подгрузка следующей страницы подмешивает чужие
объявления из общей ленты; pull-to-refresh (в т.ч. автоматический после
создания/редактирования объявления, `context.read<BoardCubit>().refresh()`)
полностью заменяет список результатом обычной публичной ленты. Отсутствует
отдельное «пусто»-состояние (в отличие от общей ленты) — пустой список
рендерится как пустой скролл без текста.

**Исходный код.** `lib/pages/my_ads/presentation/my_ads_view.dart`;
`lib/pages/board/cubit/board_cubit.dart` → `BoardCubit.load`, `loadNextPage`,
`refresh`; `lib/repositories/board/ad_repository.dart` → `AdRepository.getMyAds`.
