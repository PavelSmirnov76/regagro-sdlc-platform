# UC-150 — Загрузка списка «Избранное» отказывает: тот же общий catch BoardCubit.load, что и у остальных режимов ленты, но экран остаётся полностью пустым без единого сообщения

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`BoardCubit.load(page: 1, isFavouriteAds: true)` — единственная точка загрузки
списка «Избранное» (`FavouriteAdsView`), и она целиком проходит через тот же
метод и тот же единственный `try/catch`, что уже документирован для обычной
ленты в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md) — этот
файл не переизлагает общий механизм заново, а фиксирует, что происходит,
когда исключение бросает именно `AdRepository.getFavouriteAds()` (ветка
`isFavouriteAds: true`), и чем результат для пользователя отличается от
общей ленты. Отличий два: (1) сама эта ветка выходит из `try` до собственного
`emit` (`getFavouriteAds()` — первая строка тела `if (isFavouriteAds)`), то
есть `isOnlyFavouriteAds`/`page`/`isLastPage` не переопределяются вообще, и
состояние отката целиком равно тому, что было в `state` до вызова; (2)
`FavouriteAdsView` — единственный из трёх экранов, использующих
`BoardCubit`, который не рендерит `BoardEmpty` вовсе (в отличие от
`BoardView`), поэтому при отказе экран не показывает даже нейтрального текста
«ничего не найдено» — просто пустую прокручиваемую область без единого
элемента.

Как и зафиксировано в [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md),
у этого экрана на момент написания **нет ни одной живой точки входа в UI** —
переход из ленты (`board_view.dart`) и кнопка «Избранное» в профиле
(`profile_view.dart`) оба существуют в коде, но не ведут на этот маршрут (см.
«Пользователь»); маршрут `Routes.favouriteAds` при этом зарегистрирован и
полностью рабочий — сценарий (включая эту ошибочную ветку) воспроизводим
только прямой навигацией в обход штатного UI (deep-link/`context.go`).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — по метаданным события
[EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md) и по перечню
действий [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) («Избранное» — read-
экран, специфицированный наравне с мутациями). Код на этом пути, однако, не
делает ни одной проверки авторизации: `AdRepository.getFavouriteAds` не
обращается ни к `AuthRepository`, ни к `AppCacheService.isAuthorized()`, а
`Routes.favouriteAds` (`lib/pages/routes.dart`) зарегистрирован **без**
`redirect`-guard'а — так же, как `Routes.board`/`Routes.myAds`, и в отличие
от вложенного `Routes.boardAdCreate`, который явно редиректит на
`Routes.profile`, если `!AppCacheService.isAuthorized()`. С точки зрения
исполняемого кода гость и авторизованный пользователь получат идентичный
отказ на этом пути; принадлежность актору `ACTOR-1` — фиксация доменной
модели (личный список «Избранное» концептуально принадлежит авторизованному
пользователю), а не проверка, реально существующая в коде.

## CURRENT

### Основной поток

1. Прямая навигация на `Routes.favouriteAds` (единственный реально
   работающий способ на сегодня — оба потенциальных живых входа мертвы, см.
   «Назначение» и «Открытые вопросы») открывает `FavouriteAdsPage` →
   `FavouriteAdsView.build`: `BlocProvider(create: (_) => BoardCubit()..load(
   page: 1, isFavouriteAds: true))`. На этот момент `state` — дефолтный
   `BoardState()`: `ads: []`, `page: 1`, `isLastPage: false`,
   `isOnlyFavouriteAds: false`.
2. `BoardCubit.load({page: 1, append: false, isFavouriteAds: true, isMyAds:
   false})`: `append == false` → `emit(state.copyWith(isLoading: true))`.
3. Внутри `try`: `isFavouriteAds == true` → сразу вызывается
   `await _adRepository.getFavouriteAds()` — первая строка тела `if
   (isFavouriteAds) { ... }`; собственный `emit` этой ветки (`isOnlyFavouriteAds:
   true, ads:, page: 1, isLastPage: true, ...`) находится **после** этого
   вызова и в этом сценарии не достигается.
4. `AdRepository.getFavouriteAds()` (`lib/repositories/board/ad_repository.dart`)
   сам обёрнут в собственный `try/catch`: сначала грузит **весь** локальный
   справочник `breeds`/`suits`/`kinds` (`BreedsRepository.getAll()`,
   `SuitsRepository.getAll()`, `KindsRepository.getAll()` — нужны только для
   разрешения названий внутри `Ad.fromJson`, не для параметров запроса — сам
   эндпоинт `GET ${Constants.boardServiceApi}/selected-ads` не принимает ни
   `page`/`per_page`, ни `search`/`kind_id`/`breed_id`/`suit_id`/`ad_type_ids[]`
   в отличие от `getAds`), затем `rpcClient.call(message)`. Любое исключение
   на любом из этих шагов логируется через `getIt<Talker>().error('getFavouriteAds
   Error: $e')` (видно только в `Talker`-логе/DevTools, не в UI) и безусловно
   перебрасывается (`rethrow`).
5. Исключение всплывает из `await _adRepository.getFavouriteAds()` (шаг 3) в
   `BoardCubit.load` без изменений — перехватывается **тем же самым**
   `catch (e)`, что и ветка `getAds`/`getMyAds` (см.
   [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md), где этот
   единственный catch-блок документирован подробно; здесь он применяется к
   ветке `isFavouriteAds: true` — прямое подтверждение теста, см. «Связанные
   тесты»): `emit(state.copyWith(isLoading: false, isLoadingMore: false,
   isError: true, errorMessage: e.toString()))`.
6. Этот `copyWith` не перечисляет `ads`, `page`, `isLastPage`,
   `isOnlyFavouriteAds` — все четыре остаются равными тому, что было в
   `state` непосредственно перед входом в `try` этого вызова. Для этого
   сценария (первый и единственный `load()` свежесозданного `BoardCubit`) это
   дефолты шага 1: `ads: []`, `page: 1`, `isLastPage: false`,
   `isOnlyFavouriteAds: false` — то есть после отказа состояние не несёт
   вообще никакого следа того, что запрашивался именно режим «Избранное»
   (контраст с успешным путём, который явно проставляет
   `isOnlyFavouriteAds: true`).
7. `FavouriteAdsView`'s `BlocBuilder<BoardCubit, BoardState>` перерисовывается:
   `state.isLoading && state.ads.isEmpty` — ложно (`isLoading` уже `false`
   после шага 5) → единственная альтернатива в этом виджете, без
   промежуточной проверки `isError`/`ads.isEmpty` отдельно (в отличие от
   `BoardView`, который хотя бы различает `BoardEmpty` и `BoardPopulated`) —
   `BoardPopulated(ads: state.ads /* [] */, isLastPage: state.isLastPage
   /* false */, isLoadingMore: state.isLoadingMore /* false */, onLoadMore:
   () => context.read<BoardCubit>().loadNextPage())`.
8. `BoardPopulated.build` с `ads: []`: `GridView.builder(itemCount: 0, ...)` —
   рендерит пустую прокручиваемую область без единого элемента и без единой
   строки текста. `RefreshIndicator`, оборачивающий это дерево в
   `FavouriteAdsView`, остаётся активным независимо от того, пуст список или
   нет.
9. Пользователь видит белый/пустой экран «Избранное» без какого-либо признака
   того, что запрос вообще не выполнился — не отличимо ни от «в избранном
   реально ничего нет», ни от любого другого состояния, поскольку экран не
   рисует вообще никакого текста ни в одном из этих случаев.

### Альтернативные потоки

- **Попытка восстановления через pull-to-refresh.** `RefreshIndicator.onRefresh:
  () => context.read<BoardCubit>().refresh()` остаётся доступен даже на
  пустом экране (жест не зависит от наличия элементов в
  `GridView.builder`/`BoardPopulated`). `BoardCubit.refresh()` эмитит сброс
  (`ads: [], page: 1, isLastPage: false, isError: false, errorMessage: null,
  isLoadingMore: false`), затем вызывает `load(page: 1, append: false)` —
  **без** `isFavouriteAds: true` (тот же уже задокументированный дефект
  нефорвардинга режима, см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) и
  тест `'BoardCubit.refresh (НАХОДКА: не форвардит isMyAds/isFavouriteAds при
  повторном load())'`, `test/pages/board_cubit_test.dart`) — реально
  вызывается `_adRepository.getAds(...)` (обычная публичная лента), а не
  повторный `getFavouriteAds()`. Если этот вызов успешен, пользователь,
  потянувший экран «Избранное» вниз после молчаливого отказа, неожиданно
  видит публичную ленту объявлений вместо повторной попытки загрузить
  избранное — и ничто в состоянии (`isOnlyFavouriteAds` остаётся `false` всё
  это время) не сигнализирует о подмене источника данных. Не разбирается
  глубже в этом файле — источник дефекта уже зафиксирован для соседнего
  сценария.
- **Исключение из локальных справочников, а не из сети.** `breedsRepository.getAll()`/
  `suitsRepository.getAll()`/`kindsRepository.getAll()` внутри
  `AdRepository.getFavouriteAds()` выполняются раньше `rpcClient.call` и
  теоретически тоже могут бросить (повреждённая локальная БД и т.п.) — тот же
  `try/catch` этого метода и тот же catch `BoardCubit.load` обрабатывают этот
  случай идентично сетевому отказу, без различения источника.
- **Гость / нет текущей сессии.** Ни один шаг этого пути не проверяет
  авторизацию — поведение при отказе идентично для гостя и авторизованного
  пользователя (см. «Пользователь»).
- **Оба потенциальных живых входа в этот экран мертвы.** Переход из ленты
  (`board_view.dart`, `context.pushNamed2(Routes.favouriteAds)`) закомментирован;
  кнопка «Избранное» в профиле (`profile_view.dart`, `title: l10n.favorites`)
  имеет пустой `onTap: () {}`. Единственный способ реально дойти до этого
  экрана и, следовательно, до этой ошибочной ветки — прямая навигация в обход
  штатного UI.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё чтение
  проваливается; при исключении ни одна `Ad` не парсится, список остаётся
  таким, каким был до вызова (в этом сценарии — пустым по умолчанию); модуль
  полностью online-only, локального кэша, который можно было бы показать
  вместо провалившегося запроса, не существует.
- `Breed`/`Suit`/`Kind` (HANDBOOKS/ANIMAL) — читаются целиком внутри
  `AdRepository.getFavouriteAds()` до сетевого вызова, только для разрешения
  названий внутри объявлений; не изменяются этим сценарием; исключение при их
  чтении обрабатывается тем же catch-блоком, что и сетевой отказ.

### Бизнес-правила

- Один и тот же `try/catch` в `BoardCubit.load` обслуживает все три режима
  ленты (`getAds`/`getMyAds`/`getFavouriteAds`) одинаково — этот сценарий не
  вводит отдельной ветки обработки ошибок для «Избранного», а лишь
  подтверждает, что общий механизм (см.
  [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)) реально
  срабатывает и для этой ветки.
- Ветка `isFavouriteAds: true` в catch-блоке отличается от остальных двух тем,
  что при успехе она устанавливает `isOnlyFavouriteAds`/`page`/`isLastPage`
  собственным, отдельным `emit`, находящимся **внутри** `try`, но **после**
  вызова, который может бросить исключение — при отказе ни одно из этих трёх
  полей не переопределяется вовсе, они остаются равными состоянию,
  предшествовавшему вызову.
- `FavouriteAdsView` не различает «идёт загрузка» / «пусто» / «ошибка» тремя
  разными представлениями, как `BoardView` (`Loader`/`BoardEmpty`/
  `BoardPopulated`) — только `Loader`/`BoardPopulated`, и `BoardPopulated` с
  пустым списком не показывает вообще никакого текста.
- `AdRepository.getFavouriteAds` не принимает и не может передать ни
  пагинацию, ни поиск, ни фильтры — единственный параметризуемый источник
  отказа для этой ветки — сам факт вызова `GET /selected-ads` (и
  предшествующее чтение локальных справочников), не комбинация
  входных параметров, как у `getAds`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий (провал `getFavouriteAds()` при загрузке экрана «Избранное»)
статически прослеживается в коде целиком и подтверждён проходящим тестом
(см. «Связанные тесты»); находка о полном отсутствии живой точки входа в этот
экран (см. «Назначение»/«Открытые вопросы») не блокирует существование или
корректность самой ошибочной ветки — маршрут и код полностью рабочие, просто
недостижимы штатной навигацией.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/favourite_ads/presentation/favourite_ads_page.dart` | `FavouriteAdsPage` | CURRENT | обёртка экрана, реагирует на смену языка |
| `lib/pages/favourite_ads/presentation/favourite_ads_view.dart` | `FavouriteAdsView.build` | CURRENT | создаёт `BoardCubit()..load(page: 1, isFavouriteAds: true)`; `BlocBuilder` не различает `isError`/пустой список — только `Loader`/`BoardPopulated` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load` (ветка `isFavouriteAds`, общий `catch`) | CURRENT | предмет этого файла — та же ветка `try`, что документирована в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md); `getFavouriteAds()` вызывается до собственного `emit` ветки |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.isOnlyFavouriteAds`, `.page`, `.isLastPage`, `.isError`, `.errorMessage` | CURRENT | поля, не перечисленные в `copyWith` catch-блока — остаются равными состоянию до вызова |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getFavouriteAds` | CURRENT | источник исключения; собственный `try/catch`, логирует через `Talker`, `rethrow`; не принимает параметров пагинации/фильтров |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getAds` | CURRENT | вызывается вместо `getFavouriteAds` внутри `refresh()` (см. «Альтернативные потоки») из-за нефорвардинга `isFavouriteAds` |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated.build`, `._onScrollNotification` | CURRENT | рендерится безусловно (нет ветки `BoardEmpty` в этом экране); с `ads: []` — пустой `GridView.builder(itemCount: 0)` без текста |
| `lib/pages/routes.dart` | `Routes.favouriteAds` (без `redirect`) | CURRENT | маршрут зарегистрирован и рабочий, без auth-guard'а — как `Routes.board`/`Routes.myAds`, в отличие от `Routes.boardAdCreate` |
| `lib/pages/board/presentation/widgets/board_view.dart` | закомментированный `context.pushNamed2(Routes.favouriteAds)` | CURRENT | мёртвая точка входа №1 |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | пункт `title: l10n.favorites, onTap: () {}` | CURRENT | мёртвая точка входа №2 — пустой коллбэк |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT (не используется этим сценарием) | существующий проектный канал сообщения об ошибке, не задействованный здесь — тот же пробел, что в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md) |

## Критерии приёмки

- Если `AdRepository.getFavouriteAds()` бросает исключение при вызове из
  `BoardCubit.load(isFavouriteAds: true)`, состояние получает `isError ==
  true`, `errorMessage` содержит `e.toString()`, `isLoading` и
  `isLoadingMore` сброшены в `false` — тем же кодом, что и для
  `getAds`/`getMyAds`.
- `ads`, `page`, `isLastPage`, `isOnlyFavouriteAds` после отказа равны
  значениям, которые были в состоянии непосредственно перед вызовом (для
  свежесозданного `BoardCubit` экрана «Избранное» — `[]`, `1`, `false`,
  `false`).
- `FavouriteAdsView` не читает `isError`/`errorMessage` — после отказа она
  рендерит `BoardPopulated` с (неизменным, пустым) списком: пустую сетку без
  единого элемента и без единого сообщения, неотличимую от «в избранном
  ничего нет».
- Pull-to-refresh остаётся доступен на этом пустом экране и вызывает
  `cubit.refresh()`, который — из-за отдельно задокументированного дефекта —
  обращается к `getAds()` (публичная лента), а не повторяет
  `getFavouriteAds()`.

## Связанные тесты

`test/pages/board_cubit_test.dart`, group `'UC-144 — BoardCubit.load ERROR'`
(старая нумерация, будет переименована в `UC-144` отдельным контролируемым
проходом, не трогать сейчас — общая для обоих сценариев `getAds`/
`getFavouriteAds` группа):

- `'getFavouriteAds бросает -> ловится тем же общим catch, что и обычная
  ветка'` — прямое доказательство именно этого сценария: мокает
  `adRepository.getFavouriteAds()` через `thenThrow(Exception('boom'))`,
  вызывает `cubit.load(page: 1, isFavouriteAds: true)`, проверяет
  `cubit.state.isError == true` и `cubit.state.errorMessage, contains('boom')`.

**TBD — теста нет** на виджет-уровень `FavouriteAdsView`/`BoardPopulated`
после отказа — ни один тест не проверяет, что при `state.isError == true` и
`state.ads.isEmpty` этот конкретный экран рендерит пустую сетку без единого
текстового сообщения (в отличие от `BoardEmpty` на общей ленте); все
существующие тесты проверяют только `BoardCubit` напрямую.

**TBD — теста нет** на связку «первый `load(isFavouriteAds: true)` провалился,
затем пользователь делает `refresh()`» — существующий тест группы
`'BoardCubit.refresh (НАХОДКА: не форвардит isMyAds/isFavouriteAds при
повторном load())'` покрывает только случай, когда первый `load(isFavouriteAds:
true)` был **успешен**, а не когда он сам провалился.

**TBD — теста нет** на сам факт, что оба потенциальных входа в этот экран
(`board_view.dart`'s закомментированный `pushNamed2`, `profile_view.dart`'s
пустой `onTap`) недостижимы — зафиксировано только чтением кода (`grep`)
здесь и в [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md), не
тестом.

## Открытые вопросы и ограничения

- **Сценарий практически недостижим из живого UI**, как и его успешный
  вариант ([EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md)) — оба
  реальных входа (переход из ленты, кнопка в профиле) существуют в коде, но
  не работают. Эта спека фиксирует поведение кода, реально исполняемого при
  прямой навигации на `Routes.favouriteAds`, а не то, с чем обычный
  пользователь сталкивается сегодня через штатную навигацию.
- **Самый молчаливый из трёх однотипных сценариев отказа `BoardCubit.load`.**
  Общая лента (`BoardView`, [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md))
  хотя бы показывает `BoardEmpty` с текстом «ничего не найдено» (пусть и не
  различая ошибку от реальной пустоты); `FavouriteAdsView` не показывает даже
  этого — экран остаётся буквально пустым, без единого элемента интерфейса,
  сигнализирующего о состоянии загрузки данных.
- **Восстановление через pull-to-refresh незаметно подменяет источник
  данных.** Поскольку `refresh()` не форвардит `isFavouriteAds`, первая же
  попытка пользователя вручную обновить пустой экран «Избранное» переключает
  его на публичную ленту объявлений — без какого-либо сообщения о том, что
  режим изменился; `isOnlyFavouriteAds` в состоянии остаётся `false` на
  всём протяжении, поэтому ни одно поле состояния не позволяет UI-коду
  впоследствии обнаружить эту подмену. Не разбирается глубже здесь — источник
  дефекта уже описан для соседних сценариев ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)).
- **Не проверено эмпирически против реального бэкенда.** Вывод сделан
  статическим чтением кода (`BoardCubit.load` → `AdRepository.getFavouriteAds`)
  и подтверждён модульным тестом с замоканным `AdRepository` — форма реальных
  сетевых сбоев (таймаут, DNS, не-2xx ответ) этой спекой не воспроизведена,
  только универсальное `Exception`.
