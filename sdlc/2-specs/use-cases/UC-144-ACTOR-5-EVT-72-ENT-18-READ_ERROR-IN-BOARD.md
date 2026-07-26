# UC-144 — Загрузка ленты объявлений отказывает: ошибка перехватывается общим catch, но ни один виджет её не показывает

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-72](../events/EVT-72-ADS-FEED-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`BoardCubit.load()` — единственная точка загрузки ленты объявлений
(`lib/pages/board/cubit/board_cubit.dart`), общая для всех пяти реально
существующих триггеров события
[EVT-72](../events/EVT-72-ADS-FEED-VIEWED-IN-BOARD.md) (открытие вкладки,
поиск, фильтры, пагинация, pull-to-refresh) и одновременно для двух других
режимов той же ленты (`isMyAds`/`isFavouriteAds` —
[EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)/[EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md),
здесь упоминаются только как подтверждение общности catch-блока, не как
предмет этого файла). Метод целиком обёрнут в `try/catch`: при исключении из
`AdRepository.getAds`/`getFavouriteAds` эмитится `state.copyWith(isLoading:
false, isLoadingMore: false, isError: true, errorMessage: e.toString())`.

Ключевая находка — `isError`/`errorMessage` вычисляются и сохраняются в
`BoardState`, но **ни один виджет модуля BOARD их не читает**
(`grep -rn "isError\|errorMessage" lib/pages/board/` находит эти два поля
только в `board_cubit.dart`, `board_state.dart` и сгенерированном
`board_cubit.freezed.dart` — ни разу в `board_view.dart`, `board_empty.dart`,
`board_populated.dart` или `board_page.dart`). `BoardView` решает, что
рисовать, только по `state.isLoading`/`state.ads.isEmpty` — отказ сети
становится видимым пользователю исключительно через то, что происходит с
`ads`, а что именно происходит с `ads`, зависит от того, какой из пяти
триггеров вызвал `load()` (см. «Основной поток»/«Альтернативные потоки»).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково: маршрут `Routes.board`
(`lib/pages/routes.dart`) не имеет `redirect`-гварда авторизации — в отличие
от вложенного маршрута `create` (создание объявления), который явно
редиректит на `Routes.profile`, если `!AppCacheService.isAuthorized()`. Ни
`BoardCubit`, ни `AdRepository.getAds`/`getFavouriteAds` не проверяют статус
авторизации ни в одной ветке.

## CURRENT

### Основной поток

1. Пользователь открывает вкладку «Доска» (`Routes.board`) —
   `BoardView.build` создаёт `BlocProvider(create: (_) => BoardCubit()..load(page:
   1))`. На этот момент `state.ads` равно дефолтному `const []`
   (`BoardState()` из `board_state.dart`).
2. `load(page: 1, append: false, isFavouriteAds: false, isMyAds: false)`:
   `append == false` → `emit(state.copyWith(isLoading: true))`.
3. Внутри `try`: `isMyAds`/`isFavouriteAds` оба `false` → вызывается
   `_adRepository.getAds(page:, perPage:, search: state.searchQuery, kindIds:
   state.boardFilters.kindIds, breedIds: ..., suitIds: ..., adTypeIds: ...)`.
4. `AdRepository.getAds` (`lib/repositories/board/ad_repository.dart`) сам
   обёрнут в `try/catch`: любое исключение (из `breedsRepository.getAll()`,
   `suitsRepository.getAll()`, `kindsRepository.getAll()` — локальные
   справочники Drift, либо из `rpcClient.call(message)` — сетевой вызов `GET
   ${Constants.boardServiceApi}/ads`, либо из `AdResponse.fromJson` при
   неожиданной форме ответа) логируется через `getIt<Talker>().error('getAds
   Error: $e')` (видно только в `Talker`-логе/DevTools, не в UI приложения —
   в `lib/` не найдено ни одного экрана, встраивающего `TalkerScreen`/лог
   `Talker` в пользовательский интерфейс) и безусловно перебрасывается
   (`rethrow`).
5. Исключение всплывает из `await _adRepository.getAds(...)` (шаг 3) в
   `BoardCubit.load` без изменений — `catch (e)` перехватывает его: `emit(
   state.copyWith(isLoading: false, isLoadingMore: false, isError: true,
   errorMessage: e.toString()))`. Поле `ads` в этом `copyWith` не
   перечисляется — остаётся равным тому, что было в `state` **до** входа в
   `try` (на этом входе — дефолтный `[]`, шаг 1).
6. `BlocBuilder<BoardCubit, BoardState>` в `BoardView.build` перерисовывается:
   `state.isLoading && state.ads.isEmpty` — ложно (`isLoading` уже `false`);
   `state.ads.isEmpty` — истинно → рендерится `const BoardEmpty()`.
7. `BoardEmpty` (`lib/pages/board/presentation/widgets/board_empty.dart`)
   показывает статичный текст `l10n.board_empty_results` («ничего не
   найдено» по смыслу ключа) — тот же самый текст, что и при реально пустом
   результате поиска/фильтра. Ни `state.isError`, ни `state.errorMessage`
   этим виджетом не читаются и нигде на этом экране не отображаются: с точки
   зрения пользователя технический сетевой отказ и «по этому запросу
   действительно ничего нет» неотличимы.

### Альтернативные потоки

- **Отказ внутри `loadNextPage()` (пагинация, `append: true`).** `load(page:
  state.page + 1, append: true)` на шаге "append == true" эмитит только
  `isLoadingMore: true`, **не сбрасывая** `ads`. При том же отказе (шаги 3–5
  выше) `ads` остаётся равным списку, накопленному до этой страницы —
  `BoardPopulated` продолжает показывать уже загруженные карточки без
  изменений, спиннер подгрузки (`if (isLoadingMore) ...
  CircularProgressIndicator`, `board_populated.dart`) просто исчезает.
  Критично: этот путь **не меняет `isLastPage`** (оно не перечислено в
  `copyWith` catch-блока) — если до отказа было `false`, оно остаётся
  `false`. `_onScrollNotification` в `BoardPopulated` разрешает повторный
  `onLoadMore()` при любом приближении к концу списка, пока `!isLastPage &&
  !isLoadingMore && ads.isNotEmpty`; `loadNextPage()` со своей стороны
  блокирует повтор только при `isLastPage || isLoading || isLoadingMore` —
  ни одно из условий не остаётся истинным после отказа. Следствие: очередной
  скролл к концу списка снова вызывает тот же самый вечно проваливающийся
  запрос — молчаливый бесконечный retry без единого сообщения пользователю,
  ограниченный только тем, что пользователь физически продолжает
  докручивать список.
- **Отказ внутри `refresh()`/`applySearchText()`/`applyBoardFilters()`.** Все
  три метода эмитят `state.copyWith(ads: const [], page: 1, isLastPage:
  false, isError: false, errorMessage: null, isLoadingMore: false)`
  **до** вызова `load(page: 1, append: false)` — то есть уже показанный
  пользователю список стирается заранее, независимо от исхода самого
  `load()`. Если после этого `load()` проваливается (шаги 3–5), `ads`
  остаётся пустым (перезаписанным заранее), и экран откатывается к
  `BoardEmpty` — пользователь, до этого видевший заполненную ленту, после
  неудачного pull-to-refresh/поиска/применения фильтра видит "ничего не
  найдено" вместо прежнего списка, без какого-либо объяснения, что запрос
  на самом деле не выполнился.
- **`isFavouriteAds: true` (режим «Избранное»,
  [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md), отдельный от
  этого файла сценарий) отказывает так же.** `_adRepository.getFavouriteAds()`
  бросает — перехватывается **тем же самым** `catch` блоком `load()` (тест
  `'getFavouriteAds бросает -> ловится тем же общим catch, что и обычная
  ветка'`, см. «Связанные тесты») — тот же результат: `isError: true`,
  `errorMessage` заполнен, ни один виджет этого не показывает. Подтверждает,
  что обработка ошибок в `BoardCubit.load` не различает три источника данных
  (лента/мои/избранное) — один код пути на все три.
- **Гость (нет активной сессии).** Ни один шаг основного потока не проверяет
  авторизацию — поведение при отказе идентично для гостя и авторизованного
  пользователя.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, которую
  сценарий пытается прочитать постранично; при отказе не читается вовсе (ни
  одна `Ad` не парсится из ответа, если исключение брошено до/во время
  `rpcClient.call`/`AdResponse.fromJson`), полностью online-only — нет
  локального кэша, который можно было бы показать вместо провалившегося
  запроса.
- `BoardFiltersData`/`board_filters` (справочники видов/пород/мастей,
  читаются той же `AdRepository.getAds` до сетевого вызова) — только читаются,
  не изменяются этим сценарием; исключение при их локальной загрузке
  (`breedsRepository.getAll()` и т.п.) обрабатывается тем же catch-блоком,
  что и сетевой отказ — код не различает источник ошибки.

### Бизнес-правила

- Один `try/catch` в `BoardCubit.load` обслуживает все три режима ленты
  (`getAds`/`getMyAds`→`getAds`/`getFavouriteAds`) одинаково — нет ветвления
  по типу отказа (сеть/локальная БД/парсинг ответа) и нет отдельной ветки
  `REJECTED` (сервер не может «отказать по существу» постраничному чтению).
- Catch-блок не перечисляет `ads` в своём `copyWith` — итоговое содержимое
  списка при отказе целиком определяется тем, что было в `state.ads` на
  момент входа в `try`, то есть вызывающим контекстом (первый вызов —
  пусто; `loadNextPage` — прежняя страница сохраняется; `refresh`/
  `applySearchText`/`applyBoardFilters` — уже обнулено ими самими до вызова
  `load`).
- `isError`/`errorMessage` в `BoardState` — состояние, вычисляемое и
  хранимое, но не имеющее ни одного потребителя в дереве виджетов модуля —
  де-факто мёртвые для пользователя поля.
- `isLastPage` не переопределяется catch-блоком — отказ внутри
  `loadNextPage()` не переводит пагинацию в терминальное состояние,
  оставляя возможность повторной попытки при следующем скролле.
- Ошибка логируется только через `Talker` (`getIt<Talker>().error(...)`
  внутри `AdRepository`) — не через `showAppSnackBarError`/другой
  пользовательский канал, определённый в `.claude/rules/ui-architecture.md`
  для именно такого случая (сообщение об ошибке).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (провал `getAds` при открытии ленты) и все
перечисленные альтернативные потоки (пагинация, refresh/поиск/фильтры,
режим «Избранное», гость) статически прослеживаются в коде и подтверждены
тестом (см. «Связанные тесты»); находки, перечисленные в «Открытые вопросы и
ограничения» (мёртвые `isError`/`errorMessage`, потеря уже показанного
списка после неудачного refresh/поиска/фильтра, молчаливый бесконечный
retry пагинации), не блокируют выполнение сценария — лента после отказа
просто показывает пустой экран, приложение не падает.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_view.dart` | `BoardView.build` (`BlocProvider.create`, `BlocBuilder`) | CURRENT | точка входа A — первый вызов `load(page: 1)`; решает `Loader`/`BoardEmpty`/`BoardPopulated` только по `isLoading`/`ads.isEmpty`, не читая `isError` |
| `lib/pages/board/presentation/widgets/board_view.dart` | `_SearchBarState._openFilters`, `RTextField.onChanged` (debounce 450мс) | CURRENT | точки входа — фильтры (`applyBoardFilters`) и поиск (`applySearchText`) |
| `lib/pages/board/presentation/board_page.dart` | `BoardPage.build` | CURRENT | оболочка вкладки, оборачивает `BoardView` |
| `lib/pages/board/presentation/widgets/board_empty.dart` | `BoardEmpty` | CURRENT | рендерится и при пустом результате, и при отказе с пустым `ads` — текст не различает эти два случая |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated._onScrollNotification`, `onLoadMore` | CURRENT | триггер точки входа — пагинация; не проверяет `isError`, продолжает разрешать `onLoadMore()` после провалившейся страницы, пока `isLastPage == false` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load` | CURRENT | предмет этого файла — общий `try/catch`, эмит `isError`/`errorMessage`, не трогает `ads` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.loadNextPage`, `.refresh`, `.applySearchText`, `.applyBoardFilters` | CURRENT | остальные 4 триггера `load()`; `refresh`/`applySearchText`/`applyBoardFilters` сбрасывают `ads` **до** вызова `load`, `loadNextPage` — нет |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.isError`, `.errorMessage` | CURRENT | поля состояния без единого читателя в виджетах модуля |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getAds`, `.getFavouriteAds`, `.getMyAds` | CURRENT | источник исключения; собственный `try/catch` логирует через `Talker` и `rethrow`; `getMyAds` делегирует в `getAds` |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT (не используется этим сценарием) | существующий проектный канал сообщения об ошибке, не задействованный в `BoardView`/`BoardEmpty`/`BoardPopulated` |
| `lib/pages/routes.dart` | `Routes.board` (без `redirect`), `Routes.boardAdCreate` (`redirect` на `isAuthorized`) | CURRENT | подтверждает доступность ленты и гостю — контраст с соседним маршрутом того же модуля |

## Критерии приёмки

- Если `AdRepository.getAds` (либо, в режиме «Избранное», `getFavouriteAds`)
  бросает исключение при вызове из `BoardCubit.load`, состояние получает
  `isError == true`, `errorMessage` содержит `e.toString()`, `isLoading` и
  `isLoadingMore` сброшены в `false`.
- Список `ads` в состоянии после отказа не изменяется самим catch-блоком —
  он остаётся равным тому, что было в `state.ads` непосредственно перед
  входом в `try` этого конкретного вызова `load()`.
- Ни `BoardView`, ни `BoardEmpty`, ни `BoardPopulated` не читают
  `state.isError`/`state.errorMessage` — при `state.ads.isEmpty` после
  отказа пользователь видит тот же экран, что и при действительно пустом
  результате, без индикации технической ошибки.
- Отказ внутри `loadNextPage()` (`append: true`) не переводит `isLastPage` в
  `true` — состояние пагинации после ошибки допускает повторный вызов
  `loadNextPage()` при следующем приближении к концу списка.
- Отказ внутри `refresh()`/`applySearchText()`/`applyBoardFilters()`
  оставляет `ads` пустым, даже если непосредственно перед вызовом список уже
  был заполнен — эти три метода стирают его заранее, независимо от исхода
  `load()`.
- Ветка `isFavouriteAds: true` обрабатывается тем же catch-блоком
  `BoardCubit.load`, с тем же итоговым состоянием `isError`/`errorMessage`.

## Связанные тесты

`test/pages/board_cubit_test.dart`, group `'UC-144 — BoardCubit.load ERROR'`
(старая нумерация, будет переименована в `UC-144` отдельным контролируемым
проходом, не трогать сейчас) — 2 теста:

- `'getAds бросает -> isError=true, errorMessage заполнен, isLoading/isLoadingMore
  сброшены'` — прямое покрытие основного потока: мокает
  `adRepository.getAds(...)` через `thenThrow(Exception('network down'))`,
  проверяет `cubit.state.isError == true`,
  `cubit.state.errorMessage` содержит `'network down'`,
  `cubit.state.isLoading == false`, `cubit.state.isLoadingMore == false`,
  `cubit.state.ads` пуст.
- `'getFavouriteAds бросает -> ловится тем же общим catch, что и обычная
  ветка'` — прямое подтверждение того, что режим «Избранное» использует тот
  же catch-блок: мокает `adRepository.getFavouriteAds()` через
  `thenThrow(Exception('boom'))`, вызывает `cubit.load(page: 1,
  isFavouriteAds: true)`, проверяет `cubit.state.isError == true` и
  `cubit.state.errorMessage` содержит `'boom'`.

**TBD — теста нет** на виджет-уровень (`BoardView`/`BoardEmpty`/
`BoardPopulated`) — ни один существующий тест не проверяет, что происходит
на экране при `state.isError == true` (в частности, что `BoardEmpty`
рендерится с тем же текстом, что и при реально пустом результате); все
существующие тесты проверяют только `BoardCubit` напрямую, не дерево
виджетов.

**TBD — теста нет** на сценарий «отказ внутри `loadNextPage()` сохраняет
предыдущую страницу и не меняет `isLastPage`» — существующие тесты
`loadNextPage` (группа `'BoardCubit.loadNextPage'`, тот же файл) покрывают
только успешные и no-op (`isLastPage`/`isLoading`/`isLoadingMore` уже
`true`) случаи, ни один не мокает `getAds` как бросающий исключение именно
при `append: true`.

**TBD — теста нет** на сценарий «`refresh()`/`applySearchText()`/
`applyBoardFilters()` стирают уже показанный список, а затем `load()`
проваливается» — существующие тесты этих трёх методов (группы
`'BoardCubit.refresh (...)'`, `'BoardCubit.applySearchText'`,
`'BoardCubit.applyBoardFilters'`, тот же файл) проверяют только успешные
исходы.

## Открытые вопросы и ограничения

- **`isError`/`errorMessage` — состояние без единого потребителя.** Оба поля
  вычисляются и сохраняются в `BoardState`, но ни `BoardView`, ни
  `BoardEmpty`, ни `BoardPopulated`, ни `BoardPage` их не читают (проверено
  `grep -rn "isError\|errorMessage" lib/pages/board/` — совпадения только в
  `board_cubit.dart`/`board_state.dart`/сгенерированном
  `board_cubit.freezed.dart`). Технический отказ сети/локальной БД
  становится для пользователя неотличим от «по этому запросу ничего не
  найдено». Проект уже располагает готовым каналом именно для этого случая —
  `showAppSnackBarError` (`lib/widgets/app_snackbar.dart`,
  `.claude/rules/ui-architecture.md`) — не задействованным нигде в модуле
  BOARD. Является ли отсутствие индикации осознанным решением или
  недосмотром — ничем в коде/комментариях не зафиксировано.
- **Потеря уже показанного списка после неудачного refresh/поиска/фильтра.**
  `refresh()`/`applySearchText()`/`applyBoardFilters()` обнуляют `ads` **до**
  вызова `load()` — если сам `load()` после этого проваливается, ранее
  показанные объявления пропадают без возврата и без сообщения, что запрос
  не выполнился; единственный способ снова их увидеть — успешный повторный
  вызов одного из этих методов. Поскольку [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)
  полностью online-only (нет локального кэша), восстановить список без
  повторного успешного запроса к серверу невозможно в принципе.
- **Молчаливый бесконечный retry пагинации.** Отказ внутри `loadNextPage()`
  не меняет `isLastPage` — если оно было `false` до отказа, остаётся
  `false`, и `BoardPopulated._onScrollNotification` продолжает разрешать
  `onLoadMore()` при каждом приближении к концу списка. Технически это не
  бесконечный автоматический цикл (каждый повтор требует нового скролла
  пользователя), но каждый такой скролл будет заново проваливаться тем же
  образом, без единого признака того, что дальнейших страниц на самом деле
  может и не быть проблемой сети, а не концом списка. Не воспроизведено
  тестом (см. «Связанные тесты»).
- **Ошибка логируется только в `Talker`, не в UI.** `AdRepository.getAds`/
  `getFavouriteAds` логируют через `getIt<Talker>().error(...)` перед
  `rethrow` — видно только в `Talker`-логе/DevTools; в `lib/` не найдено ни
  одного экрана, встраивающего `TalkerScreen`/аналогичный лог-вьюер, через
  который обычный пользователь мог бы увидеть эту запись.
- **Не проверено эмпирически против реального бэкенда.** Вывод сделан
  статическим чтением кода (`BoardCubit.load` → `AdRepository.getAds`/
  `getFavouriteAds`) и подтверждён модульным тестом с замоканным
  `AdRepository` (см. «Связанные тесты») — форма реальных сетевых сбоев
  (таймаут, DNS, не-2xx ответ) этой спекой не воспроизведена, только
  универсальное `Exception`.
