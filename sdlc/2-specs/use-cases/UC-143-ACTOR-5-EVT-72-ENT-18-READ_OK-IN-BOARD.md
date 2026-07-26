# UC-143 — Пользователь открывает ленту объявлений доски (поиск, фильтры, пагинация)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-72](../events/EVT-72-ADS-FEED-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Пользователь открывает вкладку «Доска» (`BoardPage` → `BoardView`, маршрут
`Routes.board = '/board'`) и видит постраничную ленту объявлений
(`BoardCubit.load`), может искать по названию с debounce, открывать диалог
фильтров (вид/порода/масть/тип объявления), скроллить для подгрузки
следующей страницы и делать pull-to-refresh — четыре разных пользовательских
действия (`applySearchText`, `applyBoardFilters`, `loadNextPage`, `refresh`),
все в конечном счёте вызывающие один и тот же `BoardCubit.load` →
`AdRepository.getAds` (`GET /ads`). **Известный дефект**, зафиксированный уже
на уровне [ENT-18](../entities/ENT-18-AD-IN-BOARD.md): множественный выбор
значений внутри одной секции фильтра (вид/порода/масть) реально применяется
только по первому выбранному значению каждого списка —
`AdRepository.getAds` отправляет `kind_id`/`breed_id`/`suit_id` как
`kindList.firstOrNull`/`breedList.firstOrNull`/`suitList.firstOrNull`, тогда
как `ad_type_ids[]` передаётся полным массивом без этого ограничения.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Маршрут `Routes.board`
(`lib/pages/routes.dart`) зарегистрирован **без** `redirect`-guard'а — в
отличие от вложенного `create` (`Routes.boardAdCreate`, редиректит на
`Routes.profile`, если `!AppCacheService.isAuthorized()`) и от
`Routes.chats` в соседней ветке того же `StatefulShellRoute` (тот же
паттерн редиректа). Ни `BoardCubit`, ни `BoardFiltersBloc`, ни
`AdRepository.getAds` нигде не обращаются к `AuthRepository`/
`AppCacheService.isAuthorized()` (`grep -rn "isAuthorized\|AuthRepository"`
по `lib/pages/board/cubit/board_cubit.dart`,
`lib/pages/board/presentation/`, `lib/pages/board/board_filters/` и
`lib/repositories/board/ad_repository.dart` не находит ни одного
совпадения). Видимость самой вкладки «Доска» в navbar (не маршрута) гасится
отдельно, реактивно, через `BoardChatAvailabilityCubit`
([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)) — за
границами этого файла.

## CURRENT

### Основной поток

1. Пользователь открывает вкладку «Доска» — `MainPage`
   (`StatefulShellBranch` с `navigatorKey: shellNavigatorBoardKey`) строит
   `BoardPage` → `BoardView.build`: `BlocProvider(create: (_) =>
   BoardCubit()..load(page: 1))`.
2. `BoardCubit.load({page: 1, append: false, isFavouriteAds: false, isMyAds:
   false})` (дефолты обоих флагов — обычная лента, без «Мои»/«Избранное»):
   `append == false` → `emit(state.copyWith(isLoading: true))`.
3. Ни `isFavouriteAds`, ни `isMyAds` не заданы → вызывается
   `_adRepository.getAds(page: 1, perPage: state.perPage (20 по умолчанию),
   search: state.searchQuery (''), kindIds: state.boardFilters.kindIds,
   breedIds: state.boardFilters.breedIds, suitIds:
   state.boardFilters.suitIds, adTypeIds: state.boardFilters.adTypeIds)`.
4. `AdRepository.getAds`: сначала грузит **весь** локальный справочник
   `breeds`/`suits`/`kinds` (`BreedsRepository.getAll()`,
   `SuitsRepository.getAll()`, `KindsRepository.getAll()`) — нужен для
   разрешения названий породы/масти/вида у животных внутри каждого
   объявления при парсинге (`Ad.fromJson`, `specAnimals` строится по
   `breed_id`/`suit_id`/`kind_id` из ответа). Затем строит
   `queryParameters`: `page`, `per_page`; `title` — только если
   `search?.trim()` непуст; `user_id` — только если передан явно (не в этом
   потоке); `kind_id`/`breed_id`/`suit_id` — **только первый элемент**
   соответствующего списка (`kindList.firstOrNull` и т.д.), если список
   непуст; `ad_type_ids[]` — **весь** список `adTypeIds.toList()`, если
   непуст.
5. `ApiMessage(link: '${Constants.boardServiceApi}/ads', method:
   ApiMethod.get, queryParameters: ...)` → `rpcClient.call(message)` (GET
   `/ads`) → `AdResponse.fromJson(response, breeds, suits, kinds)`:
   `currentPage`/`lastPage`/`total` из ответа, `ads` — список
   [ENT-18](../entities/ENT-18-AD-IN-BOARD.md), `isLastPage` вычисляется как
   `currentPage >= lastPage`.
6. Без исключения — `BoardCubit.load` эмитит `state.copyWith(ads:
   response.ads (append == false, поэтому не конкатенируется с прежними),
   page: response.currentPage, isLastPage: response.isLastPage, isLoading:
   false, isError: false, errorMessage: null)`.
7. `BoardView`'s `BlocBuilder<BoardCubit, BoardState>`: `state.isLoading &&
   state.ads.isEmpty` → `CustomLottieLoader()`; иначе `state.ads.isEmpty` →
   `BoardEmpty()`; иначе `BoardPopulated` — сетка 2 колонки, карточка на
   объявление (обложка, цена/`animal.suitValue`-чипы, заголовок, адрес,
   кнопка «избранное»).
8. **Поиск.** `_SearchBar.onChanged`: сбрасывает предыдущий `Timer`, ставит
   новый на 450мс; по истечении, если виджет ещё смонтирован —
   `context.read<BoardCubit>().applySearchText(value)`.
   `BoardCubit.applySearchText`: `trimmed = text.trim()`; если `trimmed ==
   state.searchQuery` — `return` (no-op, повторный запрос не идёт); иначе
   `emit(state.copyWith(searchQuery: trimmed, ads: [], page: 1, isLastPage:
   false, isError: false, errorMessage: null, isLoadingMore: false))`, затем
   `await load(page: 1, append: false)` (без флагов `isFavouriteAds`/
   `isMyAds` — см. «Открытые вопросы»).
9. **Фильтры.** Иконка фильтра (`_SearchBar`) →
   `showModalBottomSheet<BoardFiltersData?>(isScrollControlled: true,
   builder: (_) => BoardFiltersDialog(arguments: BoardFiltersPageArguments(
   selectedData: cubit.state.boardFilters)))` — тот же bottom-sheet паттерн,
   что и у остальных фильтров сущностей (`.claude/rules/ui-architecture.md`).
   Диалог открывает свой собственный `BoardFiltersBloc`
   (`BoardFiltersEventStart`), пользователь выбирает значения (add/remove в
   `Set` через `isSelected` + список id — `BoardFiltersEventSelectKinds`
   и т.п., каждое значение реально добавляется в `selectedData.kindIds` без
   ограничения на количество), нажимает «Применить» →
   `BoardFiltersEventApply` → `emit(BoardFiltersExit(_data.selectedData))` →
   `BlocListener` в диалоге реагирует `Navigator.pop(context, filters)`.
   Если результат `showModalBottomSheet` непуст —
   `cubit.applyBoardFilters(data)`: `emit(state.copyWith(boardFilters: data,
   ads: [], page: 1, isLastPage: false, isError: false, errorMessage: null,
   isLoadingMore: false))`, затем `await load(page: 1, append: false)` —
   **без сравнения с предыдущими фильтрами** (повторная подача тех же
   значений всё равно вызывает `getAds` заново, покрыто тестом). Закрытие
   диалога без «Применить» (`Navigator.pop` без результата, крестик/свайп)
   не меняет `state.boardFilters` вовсе.
10. **Подгрузка при скролле.** `BoardPopulated`'s
    `NotificationListener<ScrollNotification>`: при
    `ScrollUpdateNotification`/`ScrollEndNotification` по вертикальной оси,
    если `metrics.pixels >= metrics.maxScrollExtent -
    _loadMoreScrollThreshold (280)` (или контент короче экрана,
    `maxScrollExtent <= 0`) и список не пуст — `onLoadMore()` →
    `context.read<BoardCubit>().loadNextPage()`.
    `BoardCubit.loadNextPage`: если `isLastPage || isLoading ||
    isLoadingMore` — `return` (no-op); иначе `await load(page: state.page +
    1, append: true)`.
11. `load(append: true)`: `emit(state.copyWith(isLoadingMore: true))`
    (вместо `isLoading`); после ответа —
    `ads: [...state.ads, ...response.ads]` (конкатенация в конец, не
    замена), `page`/`isLastPage` из ответа, `isLoadingMore: false`.
    `BoardPopulated` дополнительно показывает `CircularProgressIndicator`
    под сеткой, пока `isLoadingMore == true`.
12. **Pull-to-refresh.** `RefreshIndicator.onRefresh: () =>
    context.read<BoardCubit>().refresh()`. `BoardCubit.refresh`:
    `emit(state.copyWith(ads: [], page: 1, isLastPage: false, isError:
    false, errorMessage: null, isLoadingMore: false))`, затем `await
    load(page: 1, append: false)` (снова без флагов — см. «Открытые
    вопросы»).

### Альтернативные потоки

- **Множественный выбор фильтров одной секции реально не работает** (см.
  «Назначение»). Пользователь может отметить несколько видов/пород/мастей в
  `BoardFiltersDialog` — `BoardFiltersBloc` честно накапливает все выбранные
  id в `selectedData.kindIds`/`breedIds`/`suitIds` (подтверждено тестом,
  см. «Связанные тесты»), диалог визуально показывает все выбранные чипы.
  Но когда `BoardCubit.applyBoardFilters` передаёт эти списки в
  `AdRepository.getAds`, на сервер уходит только первый элемент каждого
  списка (`kindList.firstOrNull` и т.д.) — реальный результат ленты
  фильтруется только по одному виду/породе/масти, даже если пользователь
  выбрал несколько. Тип объявления (`adTypeIds`) — единственный фильтр этой
  формы, где множественный выбор реально доходит до сервера
  (`ad_type_ids[]`, полный массив). Не воспроизведено тестом на уровне
  `AdRepository`/`BoardCubit` (см. «Открытые вопросы»).
- **Поиск: текст не изменился после `trim()`.** `applySearchText` — no-op,
  `getAds` повторно не вызывается (покрыто тестом).
- **Пустой результат** (`state.ads.isEmpty && !state.isLoading`) — `BoardEmpty`
  без различия между «действительно нет объявлений» и «применённые фильтры
  ничего не нашли»: оба случая рендерят один и тот же виджет.
- **Ошибка сети/сервера** (`getAds` бросает исключение) — `catch` в `load`
  эмитит `isError: true`/`errorMessage`; `isLoading`/`isLoadingMore`
  сбрасываются. Это отдельный результат (`READ_ERROR`), за пределами этого
  файла.
- **`loadNextPage`/`refresh`/`applySearchText`/`applyBoardFilters` не
  форвардят `isMyAds`/`isFavouriteAds`.** Все четыре метода вызывают `load`
  без этих двух именованных аргументов, то есть всегда без флагов. Для
  **этой** сцены (обычная лента, `isMyAds`/`isFavouriteAds` уже `false` с
  момента первого `load`) это не меняет наблюдаемого поведения — совпадает
  с дефолтом. Тот же факт становится реальным дефектом только на экранах
  «Мои объявления»/«Избранное», которые переиспользуют этот же `BoardCubit`
  (см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md); тест
  `'BoardCubit.refresh (НАХОДКА: не форвардит isMyAds/isFavouriteAds при
  повторном load())'` в `test/pages/board_cubit_test.dart`) — не
  разбирается глубже в рамках этого файла, поскольку не относится к общей
  ленте.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё
  постраничное чтение специфицирует этот сценарий; только читается, ничего
  не меняет.
- `Breed`/`Suit`/`Kind` (HANDBOOKS/ANIMAL, [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)) —
  читаются целиком (`getAll()`, без фильтра по видимости или ферме) при
  каждом вызове `getAds`, только для разрешения отображаемых названий у
  животных внутри объявлений; не изменяются этим сценарием.
- `board_ad_types` (справочник, поле/связь [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) —
  читается отдельно `BoardFiltersBloc` при открытии диалога фильтров
  (`BoardAdTypesRepository.getAll()`), сужается до
  `Constants.boardAdTypeIdsForFilter = [1, 5, 3, 6]` — шире, чем
  `Constants.boardAdTypeIds = [3, 1]`, доступные при создании объявления
  (визард создания не даёт выбрать «Пропажа»(5)/«Найдено»(6), фильтр ленты —
  даёт искать по ним).
- `Country.boardEnabled` ([ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md),
  HANDBOOKS) — не читается этим сценарием напрямую; определяет только
  видимость самой вкладки в navbar ([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)),
  не поведение `BoardCubit`/`AdRepository` после того, как экран уже открыт.

### Бизнес-правила

- `BoardCubit.load` без `isFavouriteAds`/`isMyAds` — единственный путь,
  реализующий обычную ленту; `isFavouriteAds: true` уходит в отдельную ветку
  (`getFavouriteAds`, `page` всегда `1`, `isLastPage` всегда `true`) и
  `isMyAds: true` — в `getMyAds` (тот же `getAds` с добавленным `userId`) —
  оба вне границ этого файла (отдельные события/UC).
- `perPage` — фиксированный дефолт состояния (`20`), не настраивается
  пользователем нигде в этом потоке.
- `AdRepository.getAds` не проверяет и не требует авторизации — ни явной
  проверки токена, ни `user_id` в параметрах запроса при обычной ленте.
- Множественный выбор фильтра одной секции (вид/порода/масть) визуально
  сохраняется в `selectedData`, но применяется к результату только по
  первому выбранному значению каждой секции — единственная секция без этого
  ограничения — тип объявления.
- `isLastPage` ленты вычисляется сервером (`currentPage >= lastPage` в
  `AdResponse`), не клиентским подсчётом длины страницы.
- Подгрузка следующей страницы (`loadNextPage`) физически заблокирована,
  пока предыдущий `load`/`loadNextPage` не завершился (`isLoading ||
  isLoadingMore`) или пока `isLastPage == true` — конкатенация ответа в
  `ads` не может задвоиться повторным одновременным вызовом.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (открытие ленты, поиск, фильтры, пагинация,
pull-to-refresh) полностью реализован и достижим из UI; находки,
перечисленные в «Открытые вопросы и ограничения» (многозначный фильтр,
отсутствие различия между «пусто» и «фильтры ничего не нашли»,
нефорвардинг `isMyAds`/`isFavouriteAds` в сестринских сценариях), не
блокируют выполнение этого сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/routes.dart` | `Routes.board`, `GoRoute` без `redirect` | CURRENT | точка входа маршрута, без auth-guard'а — в отличие от `Routes.boardAdCreate`/`Routes.chats` |
| `lib/pages/board/presentation/board_page.dart` | `BoardPage` | CURRENT | обёртка экрана, реагирует на смену языка |
| `lib/pages/board/presentation/widgets/board_view.dart` | `BoardView.build`, `_SearchBar` | CURRENT | создаёт `BoardCubit`, поиск (debounce 450мс), открытие диалога фильтров |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load`, `.loadNextPage`, `.refresh`, `.applySearchText`, `.applyBoardFilters` | CURRENT | предмет этого файла — все пять методов сходятся в `getAds` для обычной ленты |
| `lib/pages/board/cubit/board_state.dart` | `BoardState` | CURRENT | `ads`/`page`/`perPage`/`isLoading`/`isLoadingMore`/`isLastPage`/`isError`/`searchQuery`/`boardFilters` |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated._onScrollNotification` | CURRENT | триггер подгрузки следующей страницы по скроллу (порог 280px) |
| `lib/pages/board/presentation/widgets/board_empty.dart` | `BoardEmpty` | CURRENT | состояние «пусто» (без различия причины) |
| `lib/pages/board/board_filters/board_filters_bloc.dart` | `BoardFiltersBloc.on<BoardFiltersEventStart/SelectKinds/SelectBreeds/SelectSuits/SelectAdTypes/Apply>` | CURRENT | диалог фильтров — накопление выбранных id, справочники |
| `lib/pages/board/board_filters/board_filters_models.dart` | `BoardFiltersData`, `BoardFiltersPageData`, `BoardFilter` | CURRENT | модель выбранных фильтров/справочников диалога |
| `lib/pages/board/board_filters/board_filters_dialog.dart` | `BoardFiltersDialog` | CURRENT | bottom-sheet UI, `Navigator.pop(context, filters)` по «Применить» |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getAds` | CURRENT | ядро сценария — построение `queryParameters`, `GET /ads`, известный дефект `firstOrNull` |
| `lib/models/board/ad.dart` | `AdResponse.fromJson`, `Ad.fromJson`, `AdResponse.isLastPage` | CURRENT | парсинг страницы ответа, разрешение названий вида/породы/масти животных внутри объявления |
| `lib/repositories/breed/breeds_repository.dart`, `lib/repositories/suit/suits_repository.dart`, `lib/repositories/kind/kinds_repository.dart` | `.getAll()` | CURRENT | полные справочники, читаемые при каждом вызове `getAds` для разрешения названий |
| `lib/repositories/board/board_ad_types_repository.dart` | `BoardAdTypesRepository.getAll()` | CURRENT | справочник типов объявления для диалога фильтров, сужается до `Constants.boardAdTypeIdsForFilter` |
| `lib/constants.dart` | `Constants.boardAdTypeIdsForFilter`, `Constants.boardAdTypeIds` | CURRENT | доступные типы объявления в фильтре (`[1,5,3,6]`) шире, чем в визарде создания (`[3,1]`) |
| `lib/network/api_client/api_client.dart`, `lib/network/api_client/api_message.dart` | `ApiClient.call`, `ApiMessage` | CURRENT | транспорт `GET /ads` |

## Критерии приёмки

- Открытие вкладки «Доска» без какой-либо предварительной проверки
  авторизации вызывает ровно один `AdRepository.getAds(page: 1, perPage: 20,
  search: '', kindIds: [], breedIds: [], suitIds: [], adTypeIds: [])` и
  заполняет `state.ads`/`state.page`/`state.isLastPage` из ответа.
- Пока запрос выполняется, `state.isLoading == true` (обычная загрузка) либо
  `state.isLoadingMore == true` (подгрузка следующей страницы,
  `append: true`) — никогда оба сразу.
- Повторный поиск с тем же текстом (после `trim()`) не вызывает повторный
  `getAds`; поиск с новым текстом сбрасывает `page`/`ads`/`isLastPage` и
  вызывает `getAds` с новым `search`.
- Применение фильтров всегда вызывает `getAds` заново (даже с теми же
  значениями), передавая новые `kindIds`/`breedIds`/`suitIds`/`adTypeIds` в
  `state.boardFilters`.
- `loadNextPage` не выполняет новый запрос, пока `isLastPage ||
  isLoading || isLoadingMore`; при успешном вызове новые `ads` дописываются
  в конец текущего списка, не заменяют его.
- `refresh` полностью сбрасывает `ads`/`page`/`isLastPage`/`isError` перед
  повторной загрузкой первой страницы.
- Если пользователь выбрал несколько значений в одной секции фильтра
  (вид/порода/масть), в запрос `GET /ads` уходит `kind_id`/`breed_id`/
  `suit_id`, равный только первому выбранному id этой секции; `ad_type_ids[]`
  в запросе, напротив, содержит все выбранные id типа объявления.

## Связанные тесты

`test/pages/board_cubit_test.dart`:

- group `'UC-143 — BoardCubit.load (общая лента, без флагов)'` (старая
  нумерация, будет переименована в `UC-143` отдельным контролируемым
  проходом, не трогать сейчас) — из шести тестов группы этому сценарию
  (обычная лента, без `isMyAds`/`isFavouriteAds`) релевантны три:
  - `'успех -> getAds вызывается с параметрами из state, ads/page/isLastPage
    заполняются'`;
  - `'isLoading выставляется в true синхронно на время запроса и
    сбрасывается по завершении'`;
  - `'append: true -> isLoadingMore вместо isLoading, новые ads добавляются
    в конец'`.
  Оставшиеся три теста этой же группы (`isFavouriteAds: true`, `isMyAds:
  true`) проверяют сестринские ветки того же метода и будут процитированы в
  других UC — не дублируются здесь.
- group `'BoardCubit.loadNextPage'` (без номера UC — механика пагинации
  общая для всех режимов ленты, не привязана к одному сценарию отдельным
  комментарием в файле):
  - `'обычная страница -> грузит page+1 и добавляет ads в конец списка'`;
  - `'isLastPage=true -> no-op, повторный getAds не вызывается'`;
  - `'isLoading=true (первый load ещё не завершился) -> no-op'`;
  - `'isLoadingMore=true (предыдущий loadNextPage ещё не завершился) ->
    no-op, данные не задваиваются'`.
  Тест `'НАХОДКА: после load(isMyAds: true), loadNextPage подмешивает
  страницу из общей ленты (getAds), а не getMyAds...'` (та же группа) не
  относится к этому сценарию — покрывает сестринский дефект `isMyAds`, не
  обычную ленту.
- group `'BoardCubit.applySearchText'` (без номера UC):
  - `'текст совпадает с уже применённым (после trim) -> no-op, повторный
    getAds не вызывается'`;
  - `'текст отличается -> обновляет searchQuery (с trim), сбрасывает
    пагинацию, грузит заново'`.
- group `'BoardCubit.applyBoardFilters'` (без номера UC):
  - `'применяет фильтры и перезагружает список с новыми
    kindIds/breedIds/suitIds/adTypeIds'`;
  - `'не сравнивает с текущими фильтрами -> load вызывается даже при
    повторной подаче тех же значений'`.

`test/pages/board_filters_bloc_test.dart` (без номера UC — внутренняя
механика диалога фильтров, не самостоятельный use-case, приводится как
вспомогательное доказательство для альтернативного потока про
множественный выбор):

- group `'BoardFiltersBloc — выбор фильтров'`, test `'SelectKinds
  isSelected:true добавляет id, isSelected:false убирает'` — подтверждает,
  что `selectedData.kindIds` реально накапливает несколько id на уровне
  диалога/bloc'а (расхождение с сервером — только внутри
  `AdRepository.getAds`, не здесь).
- group `'BoardFiltersBloc.Start'`, test `'успех -> adTypes отфильтрован по
  Constants.boardAdTypeIdsForFilter, kinds/breeds/suits загружены'` —
  подтверждает состав справочников диалога.

**TBD — теста нет** на сам известный дефект `AdRepository.getAds`
(`kindList.firstOrNull`/`breedList.firstOrNull`/`suitList.firstOrNull`
против полного `ad_type_ids[]`) — `test/repositories/ad_repository_test.dart`
не содержит ни одной группы для `getAds` вообще (только `createAd`/
`updateAd`/`viewAd`/`deleteAd`/`setAdFavourite`); ни один тест во всём
дереве `test/` не вызывает реальный (не замоканный) `AdRepository.getAds` с
несколькими `kindIds`/`breedIds`/`suitIds`, чтобы зафиксировать фактически
отправленные query-параметры.

**TBD — теста нет** на `cubit.refresh()` без флагов (обычная лента) —
единственные два теста, вызывающие `BoardCubit.refresh()` в файле, покрывают
сестринский дефект `isFavouriteAds`/`isMyAds` (группа `'BoardCubit.refresh
(НАХОДКА: не форвардит isMyAds/isFavouriteAds при повторном load())'`), не
базовый случай.

**TBD — теста нет** на `BoardEmpty`/различие «нет объявлений вообще» vs
«фильтры/поиск ничего не нашли» — ни один тест не проверяет виджет-уровень
`BoardView`/`BoardEmpty`, только состояние `BoardCubit`.

## Открытые вопросы и ограничения

- **Множественный выбор фильтров одной секции не доходит до сервера.**
  Зафиксировано уже в [ENT-18](../entities/ENT-18-AD-IN-BOARD.md):
  `AdRepository.getAds` использует `firstOrNull` для `kind_id`/`breed_id`/
  `suit_id`, отбрасывая все выбранные значения, кроме первого. UI и
  `BoardFiltersBloc` не сигнализируют пользователю об этом ограничении
  никак — чипы всех выбранных значений остаются видимыми и «активными»
  после применения, хотя реально повлияло только одно. Не воспроизведено
  тестом на уровне `AdRepository`/`BoardCubit` (см. «Связанные тесты»); не
  разбирается глубже в рамках этого файла.
- **`loadNextPage`/`refresh`/`applySearchText`/`applyBoardFilters` не
  форвардят `isMyAds`/`isFavouriteAds`.** Для этого сценария (обычная
  лента) это не создаёт наблюдаемой проблемы, поскольку оба флага и так
  `false` с первого `load`. Тот же факт — реальный, задокументированный
  тестами дефект для сестринских сценариев «Мои объявления»/«Избранное»
  (не специфицированных этим файлом): pull-to-refresh, повторный поиск,
  применение фильтров и подгрузка страницы на тех экранах незаметно
  подменяют список результатом обычной ленты. Не разбирается глубже здесь.
- **`BoardEmpty` не различает причину пустого результата.** Экран показывает
  одинаковый пустой стейт и когда объявлений вообще ещё нет, и когда
  применённые поиск/фильтры не нашли ни одного совпадения — пользователь не
  может отличить «доска пуста» от «сбросьте фильтры». Не воспроизведено
  тестом, не разбирается глубже.
- **Полная выгрузка `breeds`/`suits`/`kinds` на каждый вызов `getAds`.**
  Ради разрешения названий у животных внутри объявлений каждый вызов ленты
  (первая страница, подгрузка, поиск, фильтры, refresh) заново читает три
  полных локальных справочника без какого-либо кеширования между вызовами
  внутри `AdRepository` — не измерялось, стоит ли это отдельного внимания
  на больших справочниках; не разбирается глубже в рамках этого файла.
