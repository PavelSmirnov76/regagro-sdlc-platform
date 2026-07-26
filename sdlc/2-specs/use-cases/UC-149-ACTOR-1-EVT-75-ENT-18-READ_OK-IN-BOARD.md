# UC-149 — Пользователь открывает список «Избранное» — экран работает, но недостижим ни с одного живого экрана

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`Routes.favouriteAds` (`/board/favourite_ads`) и связка
`FavouriteAdsPage`/`FavouriteAdsView`/`BoardCubit` полностью реализованы и,
если до них добраться, корректно показывают список объявлений, отмеченных
текущим пользователем как избранные (`GET /selected-ads`). Но, в отличие от
любого другого read-экрана `BOARD`, у этого экрана на момент написания файла
**нет ни одной живой точки входа в UI** — все три места, где переход на него
мог бы находиться, либо закомментированы, либо оставлены с пустым
обработчиком:

- (a) иконка «избранное» в шапке ленты (`board_view.dart`, `_SearchBar`) —
  весь блок `_AnimatedHeaderAction`/`InkWell(onTap: () =>
  context.pushNamed2(Routes.favouriteAds))` закомментирован;
- (b) кнопка «Избранное» в профиле (`profile_view.dart`,
  `ProfileButton(title: l10n.favorites, onTap: () {})`) — коллбэк пуст;
- (c) кнопка избранного на детальной карточке объявления
  (`board_ad_detail_view.dart`) — целиком закомментирована вместе с
  `share`-кнопкой в `actions` AppBar'а.

(c) — не сама навигация на этот экран, а единственный путь, которым можно
было бы аккуратно, без стороннего дефекта, пополнить список избранного из
карточки объявления (`AdDetailCubit.toggleAdFavourite`, отдельная
`AdDetailState`, не разделяющая `Ad.props` с лентой); он тоже мёртв. Живой
способ добавить объявление в избранное — сердечко на карточке в
`BoardPopulated` (лента/«Мои объявления»/«Избранное» — общий виджет), но там
переключение icon-state сломано независимым дефектом `Ad.props`
(`Equatable`, см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) и
[UC-142](UC-142-ACTOR-1-EVT-71-ENT-18-UPDATE_ERROR-IN-BOARD.md)) — сам
серверный вызов при этом отрабатывает, так что реальный набор «избранного» на
сервере пользователем накопить можно, просто без визуальной обратной связи.

Экран технически открывается только прямой программной навигацией в обход
штатного UI (`context.pushNamed2(Routes.favouriteAds)`/`context.go(...)` из
кода, не подключённого ни к одному видимому виджету, либо deep-link на
`/board/favourite_ads`) — это и есть главный факт этого use-case:
`RESULT = READ_OK`, потому что код, если его вызвать, отрабатывает корректно,
но реальный пользователь штатной навигацией сюда не попадает.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — как и зафиксировано в его
собственном файле («BOARD… [EVT-75] (список «Избранное»)»). На практике же
ни `FavouriteAdsView`, ни `BoardCubit`, ни `AdRepository.getFavouriteAds` не
проверяют статус авторизации (`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/favourite_ads/`, `lib/pages/board/cubit/board_cubit.dart`,
`lib/repositories/board/ad_repository.dart` не находит ни одного
совпадения) — тот же паттерн отсутствия проверки, что уже отмечен в
[UC-142](UC-142-ACTOR-1-EVT-71-ENT-18-UPDATE_ERROR-IN-BOARD.md) для
переключения избранного; актор здесь зафиксирован собственным описанием
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), а не отдельной проверкой в коде
этого пути.

## CURRENT

### Основной поток

1. Экран открывается вызовом `context.pushNamed2(Routes.favouriteAds)` (или
   эквивалентным `context.go`/deep-link на `/board/favourite_ads`,
   зарегистрированный маршрут вложен под ветку `Routes.board` в
   `lib/pages/routes.dart`) — на практике этот вызов не находится ни в одном
   живом виджете `lib/` (см. «Альтернативные потоки», главный факт).
2. `FavouriteAdsPage` (`lib/pages/favourite_ads/presentation/favourite_ads_page.dart`)
   — тонкая обёртка: `BlocListener<LanguageBloc, LanguageStateInitial>`
   вызывает `setState(() {})` при смене языка (`LanguageStateChanged`),
   рендерит `const FavouriteAdsView()`.
3. `FavouriteAdsView.build` (`lib/pages/favourite_ads/presentation/favourite_ads_view.dart`)
   создаёт **новый, независимый** `BoardCubit()` через `BlocProvider.create`
   и сразу диспатчит `..load(page: 1, isFavouriteAds: true)` — это не тот же
   инстанс кубита, что у общей ленты (`BoardView`) или «Моих объявлений»
   (`MyAdsView`); ни один параметр (`searchQuery`/`boardFilters`) с других
   экранов не переносится, состояние стартует с дефолтов `BoardState`.
4. `BoardCubit.load` (`lib/pages/board/cubit/board_cubit.dart`): эмитит
   `state.copyWith(isLoading: true)` (ветка `append` здесь не используется —
   `FavouriteAdsView` вызывает `load` только с `append` по умолчанию
   `false`), затем, поскольку `isFavouriteAds == true`, входит в отдельную
   ветку `if (isFavouriteAds) { ... }` **до** построения любых query-параметров
   пагинации/поиска/фильтров.
5. Эта ветка вызывает `_adRepository.getFavouriteAds()` — метод не принимает
   ни одного аргумента: ни `page`, ни `perPage`, ни `search`, ни
   `kindIds`/`breedIds`/`suitIds`/`adTypeIds` (в отличие от `getAds`/`getMyAds`,
   которые как раз читают эти поля из `BoardState`).
6. `AdRepository.getFavouriteAds` (`lib/repositories/board/ad_repository.dart`):
   резолвит справочники `breeds`/`suits`/`kinds` целиком (нужны для парсинга
   вложенных `animals` каждого объявления), делает `GET
   {boardServiceApi}/selected-ads` через `rpcClient.call` (тот же
   `ApiClient(instanceName: 'farm_rpc')`, что и остальные вызовы `AdRepository`),
   читает `response['data']` как `List<dynamic>` и парсит каждый элемент
   `Ad.fromJson(e, breeds, suits, kinds)` — возвращает голый `List<Ad>`, без
   какой-либо обёртки с метаданными пагинации (в отличие от `AdResponse`,
   которую возвращает `getAds`/`getMyAds`).
7. По успешному возврату `BoardCubit.load` эмитит `state.copyWith(
   isOnlyFavouriteAds: true, ads: ads, page: 1, isLastPage: true, isLoading:
   false, isLoadingMore: false, isError: false, errorMessage: null)` —
   `page`/`isLastPage` не читаются из ответа сервера (там их и нет), а
   зафиксированы литералами прямо в этой ветке кубита, независимо от
   фактической длины `ads`.
8. `FavouriteAdsView`'s `BlocBuilder<BoardCubit, BoardState>` перерисовывает
   тело `AppScaffold`: пока `state.isLoading && state.ads.isEmpty` —
   `CustomLottieLoader()`; иначе, безусловно (нет отдельной ветки под пустой
   список, в отличие от `BoardView`, которая переключается на `BoardEmpty()`)
   — `BoardPopulated(ads: state.ads, isLastPage: state.isLastPage,
   isLoadingMore: state.isLoadingMore, onLoadMore: () =>
   context.read<BoardCubit>().loadNextPage())`.
9. `BoardPopulated` (`lib/pages/board/presentation/widgets/board_populated.dart`)
   — тот же виджет, что и у общей ленты/«Моих объявлений»: сетка 2 колонки,
   на каждой карточке — сердечко (`ad.isFavourite ? Icons.favorite :
   Icons.favorite_border`), тап по которому вызывает
   `context.read<BoardCubit>().toggleAdFavourite(ad.id)`; тап по всей карточке
   — `context.pushNamed2(Routes.boardAdDetail, extra:
   BoardAdDetailPageArguments(ad: ad.toDetailModel()))`. `FavouriteAdsView` не
   передаёт `trailingBuilder`, так что используется этот дефолтный вид
   сердечка.
10. Pull-to-refresh (`RefreshIndicator.onRefresh`) вызывает
    `context.read<BoardCubit>().refresh()` — см. «Альтернативные потоки», это
    единственный реально подключённый на этом конкретном экране способ
    заново вызвать `load()` (на экране нет ни строки поиска, ни кнопки
    фильтров — `applySearchText`/`applyBoardFilters` из этого экрана
    структурно не вызываются вовсе).

### Альтернативные потоки

- **Главный факт — три мёртвые точки входа (см. «Назначение»).** (a)
  `board_view.dart`, блок `_AnimatedHeaderAction`/`InkWell(onTap: () =>
  context.pushNamed2(Routes.favouriteAds))` внутри `_SearchBarState.build` —
  закомментирован целиком, вместо него в живом дереве стоит только
  `SizedBox`-разделитель и иконка «Мои объявления» (`Routes.myAds`,
  подключена и работает). (b) `profile_view.dart`,
  `ProfileButton(type: ProfileButtonType.square, icon: Assets.award, title:
  l10n.favorites, onTap: () {})` — визуально обычная, ничем не отличимая от
  рабочих кнопок этого же ряда (`messages`→`Routes.chats`, `my_ads`→
  `Routes.myAds`, оба с реальной навигацией) плитка; сам ряд, где она стоит,
  дополнительно завёрнут в `BlocBuilder<BoardChatAvailabilityCubit, bool>` и
  рендерится только при `boardChatAvailable == true` ([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md))
  — то есть даже когда BOARD доступен по стране пользователя и кнопка видна,
  тап по ней не делает ничего и не даёт пользователю никакой обратной связи о
  том, что функциональность не подключена. (c) `board_ad_detail_view.dart`,
  `actions` AppBar'а — `IconButtonForTextField` с иконкой `Icons.favorite`/
  `Icons.favorite_border` и `onPressed: () {
  context.read<AdDetailCubit>().toggleAdFavourite(model.adId); }` —
  закомментирован вместе с `share`-кнопкой; `AdDetailCubit.toggleAdFavourite`
  и `BoardAdDetailModel.isFavourite`/`.adId` (переносится из `Ad.toDetailModel()`
  корректно, поле заполнено) в коде существуют и не тронуты — просто без
  вызывающего UI-элемента.
- **`getFavouriteAds()` бросает исключение.** Ловится тем же общим
  `try/catch`, что и обычная ветка `load()` (`isError: true, errorMessage:
  e.toString()`, `isLoading`/`isLoadingMore` сброшены) — отдельная ветка
  `RESULT = READ_ERROR` этого же события, не разбирается в этом файле (см.
  «Связанные тесты»).
- **Pull-to-refresh не форвардит режим «избранное».** `BoardCubit.refresh()`
  вызывает `load(page: 1, append: false)` **без** `isFavouriteAds: true` —
  тот же класс дефекта, что уже задокументирован для «Моих объявлений»
  ([UC-147](UC-147-ACTOR-1-EVT-74-ENT-18-READ_OK-IN-BOARD.md), [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)).
  Практически: единственное реально подключённое на этом экране действие,
  которое заново вызывает `load()` (поиска/фильтров здесь нет), подменяет
  список избранного результатом обычной публичной ленты (`getAds`, дефолтные
  параметры — без поиска/фильтров/`user_id`), при этом `state.isOnlyFavouriteAds`
  остаётся `true`, а заголовок AppBar по-прежнему «Избранное» — пользователь
  видит чужие/случайные объявления под шапкой «Избранное» без какого-либо
  индикатора смены источника данных. Если после этого тапнуть по сердечку на
  одной из подменённых карточек, `toggleAdFavourite` всё равно корректно
  определяет новое значение по `ad.isFavourite` этой же (настоящей, из общей
  ленты) карточки и, поскольку `state.isOnlyFavouriteAds == true`, убирает её
  из списка — сами данные на сервере не портятся, но с точки зрения
  пользователя это выглядит как управление избранным, а на деле это лента.
- **`loadNextPage()` после загрузки избранного — структурно недостижимый
  повторный запрос.** `AdRepository.getFavouriteAds()` не поддерживает
  пагинацию вовсе, но `BoardCubit.load` в ветке `isFavouriteAds` безусловно
  фиксирует `isLastPage: true` — из-за guard'а в начале `loadNextPage()`
  (`if (state.isLastPage || ...) return;`) любой скролл до конца списка на
  этом экране не порождает второго вызова `getFavouriteAds`/`getAds`; кнопка
  «загрузить ещё» в `BoardPopulated` эффективно никогда не активируется на
  этом экране (код-путь не воспроизведён отдельным тестом именно для ветки
  избранного — см. «Связанные тесты»).
- **Пустой результат.** `getFavouriteAds()` возвращает пустой список — рендер
  не отличается от общего случая пустого `ads` на этом экране: нет отдельного
  «пусто»-сообщения (в отличие от `BoardView`, которая на пустом `ads`
  показывает `BoardEmpty()`) — `BoardPopulated` со всеми счётчиками равными
  нулю просто рисует пустую прокручиваемую сетку под шапкой «Избранное».

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — единственная читаемая
  этим сценарием сущность: `AdRepository.getFavouriteAds` парсит полный,
  несегментированный список объявлений, отмеченных избранными текущим
  пользователем на сервере (`isFavourite` этих объявлений в ответе — всегда
  `true` по построению эндпоинта); не изменяется этим read-сценарием.
  Неполный `Equatable.props` у `Ad` (не включает `isFavourite`) — фон для
  дефекта переключения на карточке (см. [UC-142](UC-142-ACTOR-1-EVT-71-ENT-18-UPDATE_ERROR-IN-BOARD.md)),
  но сам список этого экрана строится заново с сервера при каждом `load` и
  этим дефектом не затронут.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  не читается напрямую этим use-case, но косвенно определяет, видна ли
  вообще кнопка-точка-входа (b) в профиле: весь ряд с ней завёрнут в
  `BlocBuilder<BoardChatAvailabilityCubit, bool>`
  ([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)), который
  вычисляется по `Country.boardEnabled`; при `boardEnabled == false` для
  страны пользователя кнопка не рендерится вовсе, но даже при `true` её
  `onTap` пуст — доступность по стране не влияет на итоговый вывод «точка
  входа мертва в обоих случаях».

### Бизнес-правила

- `AdRepository.getFavouriteAds()` не принимает и не поддерживает ни один из
  параметров пагинации/поиска/фильтрации, которые есть у `getAds`/`getMyAds`
  — сервер отдаёт весь список избранного одним запросом.
- `BoardCubit.load(isFavouriteAds: true)` безусловно фиксирует `page: 1,
  isLastPage: true` в состоянии — это литералы самого кубита, не значения,
  вычисленные из ответа сервера.
- `state.isOnlyFavouriteAds` выставляется в `true` только веткой
  `isFavouriteAds` внутри `load()`; ни один другой метод `BoardCubit`
  (`refresh`, `loadNextPage`, `applySearchText`, `applyBoardFilters`) не
  устанавливает и не форвардит этот флаг при повторном обращении к `load()`.
- `FavouriteAdsView` не встраивает ни поле поиска, ни кнопку фильтров — на
  этом конкретном экране `applySearchText`/`applyBoardFilters` структурно не
  могут быть вызваны пользователем; единственный реально подключённый способ
  инициировать повторный `load()` — pull-to-refresh.
- Ни один из трёх потенциальных путей в UI к этому экрану не подключён:
  переход из ленты и кнопка на детальной карточке закомментированы в коде,
  кнопка в профиле подключена визуально, но с пустым обработчиком.
- Маршрут `/board/favourite_ads` не защищён каким-либо гейтом в
  `lib/pages/routes.dart` (в отличие от `Routes.boardAdCreate`, у которого
  есть `redirect` на неавторизованность) — достижим программной навигацией
  вне зависимости от статуса авторизации.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сам сценарий (маршрут, экран, кубит, репозиторий) полностью
реализован и корректно работает при прямом вызове; ничего не заблокировано
на уровне кода. Единственное препятствие — отсутствие живой точки входа в
штатной навигации (см. «Основной поток», «Альтернативные потоки», «Открытые
вопросы и ограничения») — это факт навигации/UI-подключения, а не
недоделанная реализация самого read-пути.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/routes.dart` | регистрация `Routes.favouriteAds` (вложена под ветку `Routes.board`) | CURRENT | маршрут существует и разрешается, без auth-гейта |
| `lib/pages/favourite_ads/presentation/favourite_ads_page.dart` | `FavouriteAdsPage`, `_FavouriteAdsPageState.build` | CURRENT | тонкая обёртка, ререндер по смене языка |
| `lib/pages/favourite_ads/presentation/favourite_ads_view.dart` | `FavouriteAdsView.build` | CURRENT | создаёт независимый `BoardCubit`, диспатчит `load(isFavouriteAds: true)`, единственная кнопка повторного `load()` на этом экране — pull-to-refresh |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load` (ветка `isFavouriteAds`) | CURRENT | вызывает `getFavouriteAds()`, фиксирует `page`/`isLastPage` литералами |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.refresh`, `.loadNextPage`, `.applySearchText`, `.applyBoardFilters` | CURRENT | ни один не форвардит `isFavouriteAds`/`isOnlyFavouriteAds` при повторном `load()` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.toggleAdFavourite` | CURRENT | при `state.isOnlyFavouriteAds == true` снятие с избранного убирает карточку из списка целиком |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.isOnlyFavouriteAds`, `.page`, `.isLastPage` | CURRENT | поля состояния, читаемые этим сценарием |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getFavouriteAds` | CURRENT | `GET {boardServiceApi}/selected-ads`, без параметров, без пагинации |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated` (сетка, сердечко, переход на `Routes.boardAdDetail`) | CURRENT | общий виджет карточек, переиспользован без изменений |
| `lib/pages/board/presentation/widgets/board_view.dart` | `_SearchBarState.build`, закомментированный `_AnimatedHeaderAction`/`InkWell(onTap: () => context.pushNamed2(Routes.favouriteAds))` | CURRENT (мёртвый код) | точка входа (a), не подключена |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build`, `ProfileButton(title: l10n.favorites, onTap: () {})` | CURRENT | точка входа (b), пустой коллбэк |
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit` | CURRENT | гейтит видимость всего ряда кнопок, включающего точку входа (b) |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | закомментированный `IconButtonForTextField` в `actions`, `AdDetailCubit.toggleAdFavourite(model.adId)` | CURRENT (мёртвый код) | точка входа (c) — не навигация, а единственный бездефектный способ пополнить избранное с карточки |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel.isFavourite`, `.adId`, `Ad.toDetailModel()` | CURRENT | поля, которые использовал бы обработчик (c), корректно заполнены и сегодня, несмотря на мёртвый UI |
| `lib/models/board/ad.dart` | `Ad`, `Ad.props` (Equatable, без `isFavourite`) | CURRENT | фон дефекта переключения на карточке ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md), [UC-142](UC-142-ACTOR-1-EVT-71-ENT-18-UPDATE_ERROR-IN-BOARD.md)), не влияет на сам read этого сценария |

## Критерии приёмки

- Прямой вызов `context.pushNamed2(Routes.favouriteAds)` (или переход по
  `/board/favourite_ads`) строит `FavouriteAdsPage`/`FavouriteAdsView`,
  которые создают новый `BoardCubit` и вызывают `load(page: 1,
  isFavouriteAds: true)`.
- `load(isFavouriteAds: true)` вызывает ровно `AdRepository.getFavouriteAds()`
  (без аргументов) и ни разу не вызывает `getAds`/`getMyAds`.
- По успеху `state.ads` равен списку, распарсенному из `response['data']`,
  `state.isOnlyFavouriteAds == true`, `state.page == 1`,
  `state.isLastPage == true` — независимо от длины полученного списка.
- Ни один живой (не закомментированный, не с пустым обработчиком) виджет во
  всём `lib/` не выполняет переход на `Routes.favouriteAds` и не вызывает
  `AdDetailCubit.toggleAdFavourite`/эквивалент из детальной карточки —
  единственный живой способ добавить объявление в избранное во всём модуле —
  сердечко на карточке в `BoardPopulated` (лента/«Мои объявления»/«Избранное»).
- `context.read<BoardCubit>().refresh()` на этом экране вызывает
  `load(page: 1, append: false)` без `isFavouriteAds: true` — после
  pull-to-refresh фактический источник данных сменяется на `getAds` (общая
  лента), при этом `state.isOnlyFavouriteAds` продолжает быть `true`.

## Связанные тесты

- `test/pages/board_cubit_test.dart`, группа `'UC-143 — BoardCubit.load
  (общая лента, без флагов)'` (текущее имя группы — старая нумерация;
  согласно заданию будет переименована в `UC-143`, отдельным контролируемым
  проходом, не трогать сейчас), тест `'isFavouriteAds: true -> вызывает
  getFavouriteAds (не getAds/getMyAds), page=1, isLastPage=true всегда'` —
  прямое покрытие основного потока: стаб `getFavouriteAds()` возвращает
  `[_ad(id: 5, isFavourite: true)]`, `cubit.load(page: 3, isFavouriteAds:
  true)` даёт `state.ads.map((a) => a.id) == [5]`,
  `state.isOnlyFavouriteAds == true`, `state.page == 1`,
  `state.isLastPage == true`, и `verifyNever` на `getAds` с любыми
  аргументами.
- `test/pages/board_cubit_test.dart`, группа `'BoardCubit.refresh (НАХОДКА:
  не форвардит isMyAds/isFavouriteAds при повторном load())'`, тест `'после
  load(isFavouriteAds: true), refresh() дёргает getAds вместо
  getFavouriteAds — isOnlyFavouriteAds остаётся true при чужом списке'` —
  прямое покрытие дефекта из «Альтернативные потоки»: после
  `load(isFavouriteAds: true)` (`state.ads == [1]`) и `refresh()`,
  `getFavouriteAds` вызван ровно 1 раз (не второй), `getAds` вызван (через
  `verifyGetAdsAnyCalled(1)`), `state.isOnlyFavouriteAds` остаётся `true`,
  `state.ads.map((a) => a.id) == [2]` (объявление из общей ленты, не из
  избранного).
- `test/pages/board_cubit_test.dart`, группа `'UC-144 — BoardCubit.load
  ERROR'`, тест `'getFavouriteAds бросает -> ловится тем же общим catch, что
  и обычная ветка'` — в этот use-case не входит (покрывает `READ_ERROR`,
  отдельный, ещё не написанный use-case для этого же события).
- Группа `'UC-141 — BoardCubit.toggleAdFavourite'`, тест `'на экране
  "Избранное" (isOnlyFavouriteAds) -> toggle убирает карточку из списка
  целиком'` — не входит в этот use-case напрямую (это `EVT-71`, отдельная
  мутация), но покрывает предпосылку одного из «Бизнес-правил» этого файла
  (поведение `toggleAdFavourite` при `isOnlyFavouriteAds == true`).
- **TBD — теста нет** ни на один из трёх фактов из «Основной поток»/
  «Альтернативные потоки», проверяемых на уровне виджетов/навигации: что
  `board_view.dart`/`profile_view.dart`/`board_ad_detail_view.dart` не
  содержат живого перехода на `Routes.favouriteAds` (или, для (c), живого
  вызова `toggleAdFavourite` с детальной карточки) — все существующие тесты
  проверяют только `BoardCubit`/`AdRepository` напрямую, ни один не строит
  `BoardView`/`ProfileView`/`BoardAdDetailView` через `pumpWidget` и не
  проверяет отсутствие обработчика.
- **TBD — теста нет** на `FavouriteAdsPage`/`FavouriteAdsView` как виджет
  (рендер `CustomLottieLoader`/`BoardPopulated`, поведение `RefreshIndicator`,
  реакция на `LanguageStateChanged`) — покрытие есть только на уровне
  `BoardCubit`.
- **TBD — теста нет** на `loadNextPage()` именно после
  `load(isFavouriteAds: true)` (структурная недостижимость повторного
  запроса из-за `isLastPage: true`) — существующий тест `'isLastPage=true ->
  no-op, повторный getAds не вызывается'` (группа `'BoardCubit.loadNextPage'`)
  проверяет то же самое поведение guard'а, но через обычный `getAds`, не
  через ветку избранного.

## Открытые вопросы и ограничения

- **Практическая недостижимость экрана — не техническая, а навигационная.**
  Все компоненты, необходимые для этого сценария (маршрут, экран, кубит,
  репозиторий), реализованы и покрыты тестами на уровне `BoardCubit`; чинить
  нужно не код чтения списка, а ровно три точки подключения UI, перечисленные
  в «Основной поток»/«Альтернативные потоки». Не оценивалось, было ли это
  осознанным решением (фича временно скрыта) или недосмотром при рефакторинге
  `_SearchBar`/`ProfileView`/`BoardAdDetailView` — не зафиксировано в коде.
- **Единственный живой способ пополнить избранное (сердечко в
  `BoardPopulated`) — сломан по рендеру, но не по данным.** Тап по сердечку
  на карточке в общей ленте/«Моих объявлениях» реально отправляет запрос на
  сервер (`AdRepository.setAdFavourite`), но локальная иконка не
  перерисовывается из-за неполного `Ad.props` (см.
  [UC-142](UC-142-ACTOR-1-EVT-71-ENT-18-UPDATE_ERROR-IN-BOARD.md)) — то есть
  пользователь технически может накопить непустой список избранного на
  сервере, не видя тому подтверждения в UI, и этот список корректно
  отобразился бы на экране «Избранное», если бы до него можно было
  добраться. Не проверено сквозным (integration) тестом «сердечко → сервер →
  открыть избранное», описанное только по коду.
- **Дефект нефорвардинга режима в `refresh()` — общий для всех трёх режимов
  `BoardCubit.load`.** Тот же код-путь и та же находка, что и у
  [UC-147](UC-147-ACTOR-1-EVT-74-ENT-18-READ_OK-IN-BOARD.md) («Мои
  объявления»): `refresh()`, `loadNextPage()`, `applySearchText()`,
  `applyBoardFilters()` берут только `page`/аргументы, но не
  `isFavouriteAds`/`isMyAds` — на экране «Избранное» из всех четырёх реально
  подключён только `refresh()` (нет ни поля поиска, ни кнопки фильтров), так
  что практическое проявление дефекта здесь у́же, чем на «Моих объявлениях»,
  но по сути тот же баг в общем для трёх экранов `BoardCubit.load`.
- **Гейт видимости кнопки в профиле (`BoardChatAvailabilityCubit`,
  [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)) не
  связан с причиной, по которой она не работает.** Даже для стран, где
  `Country.boardEnabled == true` и кнопка «Избранное» в профиле видна,
  `onTap` всё равно пуст — доступность BOARD по стране и подключённость
  этой конкретной кнопки — два независимых факта, оба должны быть
  зафиксированы отдельно, не как один и тот же гейт.
