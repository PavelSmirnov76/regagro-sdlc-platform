# UC-147 — Пользователь открывает «Мои объявления» (пагинация и refresh незаметно подменяют список результатом общей ленты)

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Пользователь открывает «Мои объявления» (`MyAdsPage`/`MyAdsView`) —
собственный экран, переиспользующий тот же `BoardCubit`, что и общая лента
([UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md)): `BoardCubit()
..load(page: 1, isMyAds: true)` → `AdRepository.getMyAds` → `AdRepository.getAds(...,
userId: ...)` (`GET /ads?user_id=...`). **Известный дефект**, уже
зафиксированный на уровне [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)
и [ENT-18](../entities/ENT-18-AD-IN-BOARD.md): `isMyAds` — не поле
`BoardState`, а обычный именованный параметр `load()`, нигде не сохраняемый
между вызовами. Все три метода, которые `MyAdsView` вызывает после исходной
загрузки (`loadNextPage` — по скроллу; `refresh` — pull-to-refresh **и**
автоматически после публикации/правки объявления) диспатчат внутренний
`load()` без `isMyAds: true` — откатываются к дефолту `isMyAds: false` и тем
самым к обычной ленте (`getAds`, чужие объявления), а не к `getMyAds`. Кроме
того, у этого экрана, в отличие от общей ленты, нет отдельного «пусто»-
состояния — пустой список рендерится как пустой скролл без какого-либо
текста.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь;
именно этому актору принадлежит действие «список „Мои объявления“» согласно
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) и [MOD-5](../modules/MOD-5-BOARD.md)
(в отличие от read-сценариев общей ленты/карточки — [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md),
доступных и гостю). При этом ни маршрут `Routes.myAds`, ни `MyAdsView`, ни
`BoardCubit`, ни `AdRepository.getMyAds` фактически не проверяют
авторизацию — `grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/my_ads/`, `lib/pages/board/cubit/board_cubit.dart` и
`lib/repositories/board/ad_repository.dart` не находит ни одного совпадения;
`Routes.myAds` зарегистрирован **без** `redirect`-guard'а, в отличие от
вложенного `create` (`Routes.boardAdCreate`, редиректит на `Routes.profile`,
если `!AppCacheService.isAuthorized()`). Гость технически может дойти до
этого экрана (обе точки входа — см. «Основной поток» — тоже без проверки
авторизации), но `AdRepository.getMyAds` резолвит `userId` через
`AppCacheService.getUserId() ?? -1` — для гостя (нет сохранённого
`UserHive` в Hive-боксе) это всегда `-1`, так что запрос уходит с
`user_id=-1`, которому на сервере не может принадлежать ни одно реальное
объявление (см. «Открытые вопросы»).

## CURRENT

### Основной поток

1. Точка входа A — иконка «коллекция» (`Assets.collection`) в шапке общей
   ленты, `_SearchBarState.build` (`lib/pages/board/presentation/widgets/board_view.dart`):
   `InkWell(onTap: () => context.pushNamed2(Routes.myAds))`.
2. Точка входа B — кнопка «Мои объявления» на экране профиля
   (`ProfileButton`, `lib/pages/profile/presentation/widgets/profile/profile_view.dart`):
   `onTap: () => context.pushNamed2(Routes.myAds)`. Обе точки входа ведут к
   одному и тому же маршруту, без передачи каких-либо аргументов.
3. `Routes.myAds` (`lib/pages/routes.dart`) строит `MyAdsPage` —
   тонкая обёртка, реагирующая на смену языка (`BlocListener<LanguageBloc,
   LanguageStateInitial>` → `setState(() {})`), рендерящая `const MyAdsView()`.
4. `MyAdsView.build`: `BlocProvider(create: (_) => BoardCubit()..load(page: 1,
   isMyAds: true))` — **новый, отдельный экземпляр** `BoardCubit`, не
   переиспользующий кубит общей ленты/избранного (каждый экран, включая
   `BoardView`/`FavouriteAdsView`, создаёт собственный `BoardCubit`).
5. `BoardCubit.load(page: 1, append: false, isFavouriteAds: false, isMyAds:
   true)`: `append == false` → `emit(state.copyWith(isLoading: true))`.
6. `isFavouriteAds` ложен (дефолт) → ветка `getFavouriteAds` пропускается;
   `isMyAds == true` → вызывается `_adRepository.getMyAds(page: 1, perPage:
   state.perPage (20 по умолчанию), search: state.searchQuery (''),
   kindIds: state.boardFilters.kindIds, breedIds: state.boardFilters.breedIds,
   suitIds: state.boardFilters.suitIds, adTypeIds: state.boardFilters.adTypeIds)`.
7. `AdRepository.getMyAds` — единственная строка тела:
   `return getAds(page:, perPage:, search:, userId: AppCacheService.getUserId()
   ?? -1, kindIds:, breedIds:, suitIds:, adTypeIds:)` — тот же метод, что и у
   общей ленты ([UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md)),
   с добавленным `userId`.
8. `AdRepository.getAds`: грузит **весь** локальный справочник
   `breeds`/`suits`/`kinds` (нужен для разрешения имён породы/масти/вида у
   животных внутри каждого объявления при парсинге), строит
   `queryParameters` — `page`, `per_page`, `user_id` (непуст всегда, т.к.
   `getMyAds` передаёт `?? -1`), `title` (только если `search.trim()`
   непуст — в этом потоке пуст), `kind_id`/`breed_id`/`suit_id` (только
   первый элемент соответствующего списка, если непуст), `ad_type_ids[]`
   (весь список, если непуст) → `ApiMessage(link:
   '${Constants.boardServiceApi}/ads', method: ApiMethod.get,
   queryParameters:)` → `GET /ads?user_id=...` → `AdResponse.fromJson`.
9. Без исключения — `BoardCubit.load` эмитит `state.copyWith(ads:
   response.ads (append == false, не конкатенируется), page:
   response.currentPage, isLastPage: response.isLastPage (`currentPage >=
   lastPage`), isLoading: false, isError: false, errorMessage: null)`.
10. `MyAdsView`'s `BlocBuilder<BoardCubit, BoardState>`:
    `state.isLoading && state.ads.isEmpty` → `CustomLottieLoader()`; **иначе,
    без какой-либо дополнительной проверки на пустой список**,
    `BoardPopulated(ads: state.ads, isLastPage:, isLoadingMore:, onLoadMore:
    () => context.read<BoardCubit>().loadNextPage(), trailingBuilder:
    (context, ad) => BoardAdContextMenuButton(onEdit: () => _editAd(context,
    ad), onDelete: () => _deleteAd(context, ad)))` — та же сетка 2 колонки,
    что и в общей ленте, но с `trailingBuilder`, заменяющим иконку
    «избранное» на контекстное меню «Редактировать»/«Удалить» (`onSelected`
    внутри `PopupMenuButton`).
11. Кнопка `+` (`FloatingActionButton`) открывает визард создания
    (`context.pushNamed2<bool?>(Routes.boardAdCreate)`); если визард вернул
    `true` — `await context.read<BoardCubit>().refresh()` (см.
    «Альтернативные потоки», дефект (б)).
12. Контекстное меню карточки → «Редактировать» → `_editAd`:
    `context.pushNamed2<bool?>(Routes.boardAdCreate, extra:
    BoardAdCreatePageArguments(ad: ad))`; если визард вернул `true` — тот же
    `await context.read<BoardCubit>().refresh()`.
13. Контекстное меню карточки → «Удалить» → `_deleteAd`: диалог
    подтверждения (`_DeleteAdConfirmDialog`) → при подтверждении `await
    context.read<BoardCubit>().deleteAd(ad.id)` — **не** вызывает `refresh()`
    (см. «Альтернативные потоки», контраст с шагами 11/12).

### Альтернативные потоки

- **(а) Подгрузка следующей страницы подмешивает чужие объявления.**
  Пользователь долистывает список — `BoardPopulated._onScrollNotification`
  при приближении к концу вызывает `onLoadMore()` →
  `context.read<BoardCubit>().loadNextPage()`. `BoardCubit.loadNextPage`:
  если не `isLastPage || isLoading || isLoadingMore` — `await load(page:
  state.page + 1, append: true)` — **вызов без `isMyAds`**, параметр
  откатывается к дефолту `isMyAds: false`. `load` идёт по ветке `else`
  (`isFavouriteAds` тоже `false` по дефолту) → вызывает
  `_adRepository.getAds(...)` (общая лента), не `getMyAds`. Новые `ads`
  дописываются в конец текущего списка (`[...state.ads, ...response.ads]`) —
  первая страница (реальные объявления пользователя) остаётся видна, но
  вторая и последующие страницы приходят из общей ленты доски, включая
  объявления любых других пользователей. Подтверждено тестом (см.
  «Связанные тесты»).
- **(б) Pull-to-refresh (ручной и автоматический после публикации/правки)
  полностью заменяет список результатом общей ленты.** И `RefreshIndicator.onRefresh`
  (`MyAdsView.build`), и автоматический вызов после успешной публикации
  (шаг 11) или правки (шаг 12) объявления вызывают один и тот же
  `context.read<BoardCubit>().refresh()`. `BoardCubit.refresh`: `emit(
  state.copyWith(ads: [], page: 1, isLastPage: false, isError: false,
  errorMessage: null, isLoadingMore: false))`, затем `await load(page: 1,
  append: false)` — **тоже без `isMyAds`/`isFavouriteAds`** — состояние
  `isOnlyFavouriteAds` из предыдущего `load` в `BoardState` формально не
  теряется (поле есть), но для `isMyAds` такого поля вообще не существует
  (см. «Бизнес-правила»), так что различить «эта сессия кубита была в
  режиме „Мои объявления“» после первого `load` вызывающему коду нечем.
  Результат: `refresh()` вызывает `getAds` (общая лента) вместо `getMyAds` —
  список «Мои объявления» **полностью** заменяется первой страницей обычной
  ленты, включая объявления любых других пользователей. Подтверждено тестом
  (см. «Связанные тесты»).
- **Удаление объявления не задевает этот дефект.** `_deleteAd` (шаг 13)
  вызывает `BoardCubit.deleteAd(id)`, который **не** вызывает `refresh()`
  или `load()` — обновляет `state.ads` локальным фильтром
  (`state.ads.where((ad) => ad.id != id)`), сохраняя результат последнего
  успешного `getMyAds`/`getAds` без нового сетевого запроса. Единственные
  два пути, реально запускающие дефект (б) с этого экрана — успешная
  публикация нового объявления и успешная правка существующего.
- **Пустой результат не показывает пользователю никакого сообщения.**
  В отличие от общей ленты (`BoardView`, `state.ads.isEmpty` → `BoardEmpty()`),
  `MyAdsView`'s `BlocBuilder` не содержит такой ветки вовсе — при
  `!state.isLoading && state.ads.isEmpty` рендерится `BoardPopulated` с
  пустым `ads`, то есть пустой `GridView` без единого слова текста. Это
  наступает и когда у пользователя действительно нет объявлений, и как
  побочный эффект дефекта (б), если обычная лента на момент подмены тоже
  оказалась пустой.
- **Поиск и фильтры этого экрана не касаются.** `MyAdsView` не строит ни
  поля поиска, ни иконки фильтров (`AppBarSettings` содержит только
  `leading`/`title`) — `BoardCubit.applySearchText`/`applyBoardFilters`
  (те же дефектные в отношении `isMyAds` методы, см.
  [UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md)) структурно
  недостижимы из этого экрана через реальную навигацию — не разбираются
  здесь глубже.
- **Ошибка сети/сервера** (`getMyAds`/`getAds` бросает исключение) —
  `catch` в `load` эмитит `isError: true`/`errorMessage`. Отдельный
  результат (`READ_ERROR`), за пределами этого файла.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё
  постраничное чтение специфицирует этот сценарий; только читается. В
  дефектных ветках (а)/(б) фактическое содержимое `ads` перестаёт быть
  подмножеством объявлений текущего пользователя — данные не повреждаются
  на сервере, искажается только то, что показывает клиент.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не читается
  через `AuthRepository`/API в этом сценарии напрямую; `AdRepository.getMyAds`
  резолвит `userId` из уже сохранённого `UserHive` (`AppCacheService.getUserId()`,
  прямое обращение к Hive-боксу в обход `AuthRepository`) — единственная
  точка, где идентичность пользователя влияет на этот сценарий; для гостя
  (нет `UserHive`) даёт `-1`.
- `Breed`/`Suit`/`Kind` (HANDBOOKS/ANIMAL, [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)) —
  читаются целиком при каждом вызове `getAds`/`getMyAds`, только для
  разрешения отображаемых названий у животных внутри объявлений; не
  изменяются этим сценарием.

### Бизнес-правила

- `isMyAds` — обычный именованный параметр `BoardCubit.load()`, не поле
  `BoardState`. В отличие от `isFavouriteAds`, для которого состояние хранит
  зеркальное поле `isOnlyFavouriteAds` (используемое, например,
  `toggleAdFavourite` для решения, удалять ли объявление из списка при
  снятии с избранного), у режима «Мои объявления» такого зеркального поля
  нет вовсе — после первого `load(isMyAds: true)` ни в `BoardState`, ни в
  `BoardCubit` не остаётся ни одного бита информации о том, что текущий
  список — «мои объявления», а не общая лента.
- Как следствие, все четыре метода `BoardCubit`, повторно вызывающие
  внутренний `load()` (`loadNextPage`, `refresh`, `applySearchText`,
  `applyBoardFilters`), делают это с дефолтами обоих флагов
  (`isFavouriteAds: false, isMyAds: false`) — не с параметрами, с которыми
  был выполнен исходный `load()` этого же экземпляра кубита. Для общей
  ленты ([UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md)) это не
  создаёт наблюдаемой проблемы (дефолты и так совпадают с исходным режимом);
  для «Мои объявления» — создаёт, потому что исходный режим (`isMyAds:
  true`) отличается от дефолта.
- Публикация и правка объявления (оба открываются из этого экрана) —
  единственные два действия, вызывающие `refresh()` с этого экрана;
  удаление — не вызывает.
- `MyAdsView` не содержит собственной ветки «пусто» — единственное условное
  ветвление тела — `isLoading && ads.isEmpty` (индикатор загрузки), любое
  другое состояние, включая полностью пустой список после завершения
  загрузки, рендерится тем же `BoardPopulated`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (открытие экрана с любой из двух точек входа,
постраничная загрузка через `getMyAds`) полностью реализован и достижим из
UI; находки, перечисленные в «Открытые вопросы и ограничения» (нефорвардинг
`isMyAds` в `loadNextPage`/`refresh`, отсутствие «пусто»-состояния,
недостижимость поиска/фильтров с этого экрана), не блокируют выполнение
сценария — они искажают его результат, а не препятствуют выполнению.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_view.dart` | `_SearchBarState.build` (иконка `Assets.collection`) | CURRENT | точка входа A — из шапки общей ленты |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` («Мои объявления») | CURRENT | точка входа B — из экрана профиля |
| `lib/pages/routes.dart` | `Routes.myAds`, `GoRoute` без `redirect` | CURRENT | маршрут, без auth-guard'а — в отличие от `Routes.boardAdCreate` |
| `lib/pages/my_ads/presentation/my_ads_page.dart` | `MyAdsPage` | CURRENT | тонкая обёртка, реагирует на смену языка |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView.build`, `_editAd`, `_deleteAd` | CURRENT | предмет сценария — создаёт `BoardCubit()..load(isMyAds: true)`; вызывает `refresh()` после создания/правки; `deleteAd()` без `refresh()` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load`, `.loadNextPage`, `.refresh`, `.deleteAd` | CURRENT | `load` — единственное место, знающее про `isMyAds`; `loadNextPage`/`refresh` его не форвардят |
| `lib/pages/board/cubit/board_state.dart` | `BoardState` | CURRENT | нет поля `isMyAds` (асимметрично `isOnlyFavouriteAds`) |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getMyAds`, `.getAds` | CURRENT | `getMyAds` — тонкая обёртка над `getAds` с `userId` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getUserId` | CURRENT | резолв `userId` из Hive-бокса напрямую, в обход `AuthRepository`; `null` для гостя |
| `lib/models/board/ad.dart` | `AdResponse.fromJson`, `.isLastPage` | CURRENT | парсинг страницы ответа, общий с `getAds` |
| `lib/repositories/breed/breeds_repository.dart`, `lib/repositories/suit/suits_repository.dart`, `lib/repositories/kind/kinds_repository.dart` | `.getAll()` | CURRENT | полные справочники, читаемые при каждом вызове `getAds`/`getMyAds` для разрешения имён |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated`, `._onScrollNotification` | CURRENT | общий с лентой виджет сетки; триггер `loadNextPage` по скроллу; нет собственной ветки «пусто» |
| `lib/pages/board/presentation/widgets/board_ad_context_menu.dart` | `BoardAdContextMenuButton` | CURRENT | `trailingBuilder` этого экрана — «Редактировать»/«Удалить» вместо иконки «избранное» |
| `lib/pages/board/presentation/widgets/board_empty.dart` | `BoardEmpty` | CURRENT | НЕ используется `MyAdsView` — контраст с `BoardView` |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `BoardAdCreatePageArguments` | CURRENT | аргумент правки, передаваемый из `_editAd` |
| `lib/network/api_client/api_client.dart`, `lib/network/api_client/api_message.dart` | `ApiClient.call`, `ApiMessage` | CURRENT | транспорт `GET /ads?user_id=...` |

## Критерии приёмки

- Открытие «Мои объявления» с любой из двух точек входа создаёт ровно один
  новый `BoardCubit` и вызывает `load(page: 1, isMyAds: true)` ровно один
  раз, что приводит к ровно одному вызову `AdRepository.getMyAds(page: 1,
  perPage: 20, search: '', kindIds: [], breedIds: [], suitIds: [],
  adTypeIds: [])` и ни одному вызову `AdRepository.getAds` напрямую.
- `state.ads`/`state.page`/`state.isLastPage` после исходной загрузки
  соответствуют объявлениям, вернувшимся из `getMyAds` (то есть объявлениям
  текущего пользователя), не общей ленты.
- **БАГ, зафиксированный этим сценарием**: `loadNextPage()`, вызванный после
  `load(page: 1, isMyAds: true)` на том же экземпляре `BoardCubit`,
  фактически вызывает `AdRepository.getAds` (без `userId`), а не
  `AdRepository.getMyAds` — начиная со второй страницы, `state.ads`
  перестаёт быть подмножеством объявлений текущего пользователя.
- **БАГ, зафиксированный этим сценарием**: `refresh()`, вызванный после
  `load(page: 1, isMyAds: true)` на том же экземпляре `BoardCubit` (вручную
  pull-to-refresh либо автоматически после успешной публикации/правки
  объявления), тоже вызывает `AdRepository.getAds`, полностью заменяя
  `state.ads` первой страницей общей ленты.
- `deleteAd(id)`, вызванный с этого экрана, не выполняет ни `refresh()`, ни
  повторный `load()` — не запускает описанный выше баг.
- При `!state.isLoading && state.ads.isEmpty` `MyAdsView` не показывает
  пользователю никакого текстового сообщения — рендерится пустой
  `BoardPopulated`.

## Связанные тесты

`test/pages/board_cubit_test.dart` (нумерация групп — старая, будет
переименована отдельным контролируемым проходом, не трогать сейчас; ни одна
из перечисленных ниже групп не переименовывается в `UC-147` — отдельной
выделенной группы под этот use-case в файле нет):

- group `'UC-143 — BoardCubit.load (общая лента, без флагов)'` (будет
  переименована в `UC-143`) — единственный релевантный этому файлу под-тест,
  цитируется как **частичное доказательство** основного потока (сам вызов
  `load(isMyAds: true)` → `getMyAds`, без пагинации/refresh):
  `'isMyAds: true -> вызывает getMyAds с текущими параметрами вместо
  getAds'` — мокает `adRepository.getMyAds(page: 1, perPage: 20, search:
  '', kindIds: const [], breedIds: const [], suitIds: const [], adTypeIds:
  const [])`, вызывает `cubit.load(page: 1, isMyAds: true)`, проверяет
  `cubit.state.ads.map((a) => a.id) == [7]` и `verifyNever` на
  `adRepository.getAds(...)` с любыми аргументами.
- group `'BoardCubit.loadNextPage'` (без номера UC) — test `'НАХОДКА: после
  load(isMyAds: true), loadNextPage подмешивает страницу из общей ленты
  (getAds), а не getMyAds (board_cubit.dart:83-86)'` — прямое подтверждение
  **альтернативного потока (а)**: мокает `getMyAds(page: 1, ...)` (страница
  1, `lastPage: 2`) и отдельно `getAds(page: 2, ...)` (страница 2), вызывает
  `cubit.load(page: 1, isMyAds: true)` (`isLastPage == false`), затем
  `cubit.loadNextPage()`; `verifyNever` на `getMyAds(page: 2, ...)`;
  `cubit.state.ads.map((a) => a.id) == [1, 99]`, с явным `reason: 'страница
  2 подтянута из getAds (общая лента), а не getMyAds — на реальном экране
  "Мои объявления" это происходит при обычной пагинации листания списка'`.
- group `'BoardCubit.refresh (НАХОДКА: не форвардит isMyAds/isFavouriteAds
  при повторном load())'` (без номера UC) — test `'после load(isMyAds:
  true), refresh() дёргает getAds вместо getMyAds'` — прямое подтверждение
  **альтернативного потока (б)**: мокает `getMyAds(...)` (возвращает
  объявление `id: 1`) и `getAds` (через `stubGetAdsAny`, возвращает
  объявление `id: 2`), вызывает `cubit.load(page: 1, isMyAds: true)`
  (`state.ads == [1]`), затем `cubit.refresh()`; проверяет, что `getMyAds`
  всё ещё был вызван (`called(1)`) и `getAds` вызван ровно один раз
  (`verifyGetAdsAnyCalled(1)`), но итоговый `cubit.state.ads.map((a) =>
  a.id) == [2]`, с явным `reason: 'BUG: pull-to-refresh на экране "Мои
  объявления" (my_ads_view.dart) и авто-refresh после создания/правки
  объявления подменяют список результатом общей ленты вместо getMyAds'`.

**TBD — теста нет** на сам факт двух точек входа (`_SearchBarState` /
`ProfileButton`) на уровне навигации — существующие тесты проверяют только
`BoardCubit`/`AdRepository` напрямую, не переход `context.pushNamed2(Routes.myAds)`
из какого-либо из двух вызывающих виджетов.

**TBD — теста нет** на отсутствие «пусто»-состояния (`MyAdsView` рендерит
пустой `BoardPopulated` без сообщения) — ни один тест файла не проверяет
виджет-уровень `MyAdsView`/`BoardPopulated`, только состояние `BoardCubit`.

**TBD — теста нет** на `deleteAd()` как единственное действие этого экрана,
не запускающее дефект (б), — существующий тест `'успех -> deleteAd вызван,
объявление пропадает из списка'` (group `'UC-139 — BoardCubit.deleteAd'`)
подтверждает только сам факт локального удаления из списка, не то, что
`deleteAd` не вызывает `refresh()`/`load()` (отсутствие вызова прямо не
проверяется `verifyNever` в этом тесте).

**TBD — теста нет** на `applySearchText`/`applyBoardFilters` в сочетании с
предшествующим `isMyAds: true` — оба метода структурно недостижимы из
`MyAdsView` (нет UI поиска/фильтров на этом экране), поэтому пробел
теоретический, не наблюдаемый через реальную навигацию.

## Открытые вопросы и ограничения

- **`isMyAds` — единственный из двух флагов режима, не имеющий зеркального
  поля в `BoardState`.** `isFavouriteAds` хотя бы частично переживает
  `load()` через `state.isOnlyFavouriteAds` (используется `toggleAdFavourite`
  для решения, убирать ли объявление из списка при снятии с избранного, —
  см. [UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md) и тест
  `'после load(isFavouriteAds: true), refresh() дёргает getAds вместо
  getFavouriteAds — isOnlyFavouriteAds остаётся true при чужом списке'` в
  том же файле) — то есть тот же класс дефекта существует и у «Избранного»
  (`isOnlyFavouriteAds` остаётся `true`, но данные всё равно подменяются на
  общую ленту). `isMyAds` не оставляет в состоянии вообще ничего — после
  бага список выглядит как обычная лента, и ни одно поле `BoardState` не
  фиксирует, что режим экрана был другим. Не разбирается глубже в рамках
  этого файла — задокументировано как наблюдение по коду.
- **Гость технически достижим до этого экрана без содержательного
  результата.** Ни одна из двух точек входа, ни сам маршрут, ни `BoardCubit`,
  ни `AdRepository.getMyAds` не проверяют авторизацию — `userId` резолвится
  как `AppCacheService.getUserId() ?? -1`. Не проверено интеграционно (запрос
  идёт к реальному API), поведение сервера на `user_id=-1` этой спекой не
  верифицировано — фиксируется только как факт клиентского кода.
- **Автообновление после создания/правки — единственный путь, где дефект
  (б) виден пользователю почти сразу после успешного действия.** Пользователь
  публикует или правит объявление, ожидая увидеть обновлённый список «Мои
  объявления», и вместо этого получает первую страницу общей ленты — без
  какого-либо сообщения об ошибке (запрос `getAds` завершается успешно,
  просто не тот запрос). Не воспроизведено на уровне виджета/интеграционно,
  только на уровне `BoardCubit` (см. «Связанные тесты»).
- **Исправление в рамках этого документирующего прохода не выполняется** —
  как и для аналогичного дефекта общей ленты
  ([UC-143](UC-143-ACTOR-5-EVT-72-ENT-18-READ_OK-IN-BOARD.md)), это фиксация
  уже существующего кода, а не работа над дефектом.
