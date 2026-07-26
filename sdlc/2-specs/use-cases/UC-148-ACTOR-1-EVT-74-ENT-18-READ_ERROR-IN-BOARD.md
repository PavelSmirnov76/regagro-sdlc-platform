# UC-148 — Загрузка «Моих объявлений» отказывает: тот же общий catch, что у общей ленты, но экран падает не в «ничего не найдено», а в буквально пустую сетку без единого слова

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`MyAdsView.build` открывает список «Мои объявления» через `BoardCubit()..load(
page: 1, isMyAds: true)` — тот же `BoardCubit`, что и у общей ленты
([EVT-72](../events/EVT-72-ADS-FEED-VIEWED-IN-BOARD.md)), с тем же единственным
`try/catch` в `load()`. Здесь сам сетевой/локальный вызов заканчивается
исключением: `AdRepository.getMyAds` — не отдельная реализация со своим сетевым
вызовом, а чистая делегирующая обёртка, дословно возвращающая
`getAds(..., userId: AppCacheService.getUserId() ?? -1, ...)` без собственного
`try/catch` и без собственного лога — любое исключение ловится и
логируется («`getAds Error: $e`», не «`getMyAds Error`») внутри самого
`getAds`, затем безусловно перебрасывается (`rethrow`) через `getMyAds`
(простой `return`, без `await`/`try` вокруг него) в `BoardCubit.load`. Это тот
же самый механизм, что уже задокументирован для общей ленты в
[UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md); этот файл
фиксирует его специально для триггера `my_ads.viewed`
([EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)) и отдельно отмечает, что
здесь наблюдаемый пользователем итог **строже**, чем у общей ленты:
`MyAdsView` не использует `BoardEmpty` вовсе (в отличие от `BoardView`) — при
отказе экран рендерит `BoardPopulated` напрямую с пустым списком, то есть
буквально пустую прокручиваемую сетку без единого слова, а не хотя бы неверный,
но видимый текст «ничего не найдено».

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь, по
собственной классификации [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)
и [MOD-5](../modules/MOD-5-BOARD.md) (раздел «Состав», ACTOR-1 — «...
[EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md) (список «Мои
объявления») ... — read-экраны, специфицированы наравне с мутациями»). Код,
однако, не проверяет авторизацию ни на одном уровне этого пути: `Routes.myAds`
(`lib/pages/routes.dart`) не имеет `redirect`-гварда — единственные два
маршрута всего приложения с `isAuthorized`-редиректом — соседние
`Routes.boardAdCreate` и `Routes.chats` (`grep -n "isAuthorized"
lib/pages/routes.dart` находит ровно два совпадения, оба не здесь); ни
`BoardCubit.load`, ни `AdRepository.getMyAds`/`getAds` не проверяют статус
сессии ни в одной ветке. Оба реально существующих в навигации входа —
иконка «коллекция» в шапке `BoardView` (`lib/pages/board/presentation/widgets/board_view.dart`,
её видимость зависит только от `_isSearchFocused`, не от авторизации) и кнопка
«Мои объявления» в `ProfileView` (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`) —
доступны гостю точно так же, как и авторизованному пользователю. Для гостя
`AdRepository.getMyAds` отправляет запрос с `user_id=-1`
(`AppCacheService.getUserId() ?? -1` — `null`, если в Hive-боксе
`AuthRepository.authBoxKey` нет сохранённого `UserHive`,
`lib/data/services/app_cache_service.dart`).

## CURRENT

### Основной поток

1. Пользователь нажимает вход A (иконка «коллекция», `Assets.collection`, в
   шапке `BoardView`) либо вход B (`ProfileButton` «Мои объявления» в
   `ProfileView`) — оба ведут к `context.pushNamed2(Routes.myAds)`.
2. `MyAdsView.build` создаёт `BlocProvider(create: (_) => BoardCubit()..load(
   page: 1, isMyAds: true))`. На этот момент `state` — дефолтный `BoardState()`:
   `ads: []`, `isLoading: false`, `perPage: 20`.
3. `load(page: 1, append: false, isFavouriteAds: false, isMyAds: true)`:
   `append == false` → `emit(state.copyWith(isLoading: true))`.
4. Внутри `try`: `isFavouriteAds` — `false`, ветка пропущена; `isMyAds == true`
   → вызывается `_adRepository.getMyAds(page:, perPage: state.perPage, search:
   state.searchQuery, kindIds: state.boardFilters.kindIds, breedIds: ...,
   suitIds: ..., adTypeIds: ...)`.
5. `AdRepository.getMyAds` (`lib/repositories/board/ad_repository.dart`) —
   тело метода целиком: `return getAds(page:, perPage:, search:, userId:
   AppCacheService.getUserId() ?? -1, kindIds:, breedIds:, suitIds:,
   adTypeIds:);` — ни `try`, ни `catch`, ни собственного лога у этого метода
   нет вовсе; он просто передаёт управление и аргументы дальше в `getAds`.
6. Внутри `getAds`'s собственного `try`: `breedsRepository.getAll()`,
   `suitsRepository.getAll()`, `kindsRepository.getAll()` (локальные
   Drift-справочники), сборка `queryParameters` (теперь с `user_id`, так как
   он непустой), `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc')`,
   `response = await rpcClient.call(message)` — `GET
   ${Constants.boardServiceApi}/ads?user_id=...&...`. Исключение на любом из
   этих шагов (включая парсинг `AdResponse.fromJson`) перехватывается
   единственным `catch (e) { getIt<Talker>().error('getAds Error: $e');
   rethrow; }` метода `getAds` — лог буквально называет метод «`getAds`», не
   «`getMyAds`», поскольку `getMyAds` сам никогда не логирует и не ловит
   ничего.
7. Исключение всплывает из `getAds`, без изменений проходит через `getMyAds`
   (просто `return`-выражение, ничем не обёрнутое) прямо в `await
   _adRepository.getMyAds(...)` внутри `try` `BoardCubit.load` (шаг 4).
8. `catch (e)` в `BoardCubit.load` — тот же самый код, что уже
   задокументирован для общей ленты в
   [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md): `emit(
   state.copyWith(isLoading: false, isLoadingMore: false, isError: true,
   errorMessage: e.toString()))`. `ads` не перечислен в этом `copyWith` —
   остаётся равным тому, что было в `state.ads` до входа в `try` (на этом,
   первом вызове экрана — дефолтный `[]`).
9. `MyAdsView`'s `BlocBuilder<BoardCubit, BoardState>` перерисовывается.
   В отличие от `BoardView` (общая лента), у этого экрана нет отдельной
   ветки для пустого результата — условие ровно одно: `state.isLoading &&
   state.ads.isEmpty ? CustomLottieLoader() : BoardPopulated(ads: state.ads,
   ...)`. Поскольку `isLoading` уже `false` (шаг 8), рендерится
   `BoardPopulated(ads: const [], isLastPage: state.isLastPage,
   isLoadingMore: state.isLoadingMore, onLoadMore: ..., trailingBuilder:
   ...)`.
10. `BoardPopulated` с пустым `ads` строит `GridView.builder` с `itemCount:
    0` внутри `RefreshIndicator` — ни текста, ни иконки, ни какого-либо
    плейсхолдера (в отличие от `BoardEmpty`, который в этот файл не
    импортирован вовсе — `import` в `my_ads_view.dart` не содержит
    `board_empty.dart`). `state.isError`/`state.errorMessage` нигде в
    `my_ads_view.dart` не читаются (файл прочитан целиком — ни одного
    упоминания этих двух полей) — тот же мёртвый-для-UI паттерн, что и в
    [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md), но здесь
    итоговый визуальный результат хуже: не неверный, но хотя бы видимый
    текст «ничего не найдено», а совершенно пустая прокручиваемая область.

### Альтернативные потоки

- **Отказ происходит на этапе чтения локальных справочников
  (`breedsRepository.getAll()`/`suitsRepository.getAll()`/
  `kindsRepository.getAll()`), а не на сетевом вызове.** Перехватывается тем
  же `catch` внутри `getAds` — код не различает источник ошибки (тот же
  вывод, что и в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)
  для общей ленты).
- **Гость (`AppCacheService.getUserId() == null`).** `userId` резолвится в
  `-1`, запрос уходит с `user_id=-1`; путь и итог отказа — идентичны
  авторизованному пользователю, ветвления по гостю нигде на этом пути нет.
- **Pull-to-refresh после этого отказа.** `RefreshIndicator.onRefresh →
  context.read<BoardCubit>().refresh()`. `refresh()` сперва обнуляет `ads:
  const []` (уже был `[]` на этом экране, без видимого эффекта), затем
  вызывает `load(page: 1, append: false)` — **без** `isMyAds: true`
  (известный дефект самого [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md):
  `refresh()` не форвардит текущий режим). Повторный запрос уходит через
  `getAds` (общая лента), не `getMyAds` — если он тоже бросает исключение,
  наблюдается тот же самый пустой экран этого файла; если он, наоборот,
  завершается успешно, пользователь вместо повторной «Моих объявлений»
  увидит чужие объявления общей ленты — отдельный дефект, целиком разобранный
  в [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md), не переразбирается
  здесь глубже.
- **`REJECTED`-ветки не существует** — как и у общей ленты
  ([UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)), постраничное
  чтение не имеет содержательного отказа сервера, отличного от технического
  сбоя; единственный найденный путь — `Exception`, пойманный один раз внутри
  `getAds` и один раз внутри `BoardCubit.load`.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, которую
  сценарий пытается прочитать постранично, отфильтрованно по `user_id`; при
  отказе не читается вовсе — online-only, нет локального кэша, который можно
  было бы показать вместо провалившегося запроса.
- `BoardFiltersData`/справочники видов/пород/мастей (читаются той же
  `AdRepository.getAds`, до сетевого вызова) — только читаются, не
  изменяются этим сценарием; исключение при их локальной загрузке
  перехватывается тем же catch-блоком, что и сетевой отказ (см.
  «Альтернативные потоки»).

### Бизнес-правила

- Один и тот же `try/catch` в `BoardCubit.load` обслуживает все три режима
  ленты (`getAds`/`getMyAds`/`getFavouriteAds`) одинаково — нет ветвления по
  режиму и нет отдельной ветки, специфичной для «Моих объявлений».
- `AdRepository.getMyAds` не имеет собственного кода обработки ошибок — она
  целиком наследуется от `getAds`, включая текст лога («`getAds Error`», не
  «`getMyAds Error`»), поскольку `getMyAds` — чистая делегирующая обёртка.
- Catch-блок `BoardCubit.load` не перечисляет `ads` в своём `copyWith` —
  итоговое содержимое списка при отказе определяется тем, что было в
  `state.ads` до входа в `try`; на первом открытии экрана это всегда пустой
  список.
- `isError`/`errorMessage` вычисляются и сохраняются в `BoardState`, но не
  имеют ни одного потребителя в `lib/pages/my_ads/` — те же мёртвые поля, что
  и у общей ленты ([UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)),
  подтверждено чтением `my_ads_view.dart` целиком.
- В отличие от общей ленты, у этого экрана нет отдельного виджета для
  «пусто» (`BoardEmpty`) вовсе — `MyAdsView` рендерит `BoardPopulated`
  напрямую на любое не-`isLoading` состояние, будь то «у пользователя
  действительно нет объявлений», «поиск/фильтр не дал совпадений» (хотя
  элементы управления поиском/фильтрами не выведены в UI этого экрана — не
  разбирается глубже, вне рамок этого файла) или «запрос провалился» — все
  три неотличимы от пустой сетки.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий воспроизводится статическим
чтением кода целиком: `MyAdsView.build` → `BoardCubit.load` → `AdRepository.getMyAds`
(делегирующая обёртка) → `AdRepository.getAds` → `CustomDioClient.call`/
`DioClient`. Прямого теста именно на комбинацию `isMyAds: true` + исключение
нет (см. «Связанные тесты») — это фиксируется как честный пробел покрытия,
не блокирует документирование уже читаемого в коде поведения.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_view.dart` | иконка «коллекция» (`InkWell.onTap` → `Routes.myAds`) | CURRENT | вход A — видимость зависит только от `_isSearchFocused`, не от авторизации |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` «Мои объявления» (`onTap` → `Routes.myAds`) | CURRENT | вход B |
| `lib/pages/routes.dart` | `Routes.myAds` | CURRENT | маршрут без `redirect`-гварда — в отличие от `Routes.boardAdCreate`/`Routes.chats`, единственных двух маршрутов с `isAuthorized`-редиректом во всём приложении |
| `lib/pages/my_ads/presentation/my_ads_page.dart` | `MyAdsPage` | CURRENT | обёртка языка (`BlocListener<LanguageBloc, ...>`), оборачивает `MyAdsView` |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView.build` | CURRENT | предмет этого файла — создаёт `BoardCubit()..load(page: 1, isMyAds: true)`; единственное ветвление UI — `isLoading && ads.isEmpty` против `BoardPopulated`, без ветки для пустого/ошибочного результата; `isError`/`errorMessage` нигде не читаются |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.load` | CURRENT | общий `try/catch` для всех трёх режимов — тот же код, что и в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md) |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.refresh` | CURRENT | вызывается pull-to-refresh'ем на этом экране; не форвардит `isMyAds` (известный дефект [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)) |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.isError`, `.errorMessage` | CURRENT | поля состояния без единого читателя в `lib/pages/my_ads/` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getMyAds` | CURRENT | чистая делегирующая обёртка — `return getAds(..., userId: ...)`, без собственного `try/catch`/лога |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getAds` | CURRENT | источник исключения; собственный `try/catch`, логирует `'getAds Error: $e'` через `Talker`, `rethrow` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getUserId` | CURRENT | `null`, если в Hive нет `UserHive` — резолвится в `userId: -1` внутри `getMyAds` для гостя |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated` | CURRENT | при пустом `ads` строит `GridView.builder(itemCount: 0)` — ни текста, ни плейсхолдера |
| `lib/pages/board/presentation/widgets/board_empty.dart` | `BoardEmpty` | CURRENT (не используется этим экраном) | существует и используется `BoardView` для общей ленты — не импортирован `my_ads_view.dart` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | та же логика, что в [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md) — логирует и `rethrow` любое исключение из `dio.request`/`AuthInterceptor` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio бросает исключение на любом не-2xx ответе |

## Критерии приёмки

- Если `AdRepository.getMyAds` (то есть, фактически, делегированный
  `AdRepository.getAds` с непустым `userId`) бросает исключение при вызове из
  `BoardCubit.load(isMyAds: true)`, состояние получает `isError == true`,
  `errorMessage` содержит `e.toString()`, `isLoading`/`isLoadingMore`
  сброшены в `false`.
- Лог исключения содержит текст `'getAds Error: ...'`, а не `'getMyAds
  Error: ...'` — поскольку `getMyAds` не имеет собственного `try/catch`.
- Список `ads` в состоянии после отказа не изменяется самим catch-блоком —
  остаётся равным тому, что было в `state.ads` непосредственно перед входом в
  `try` этого вызова `load()` (на первом открытии экрана — пустой список).
- `MyAdsView` не читает ни `state.isError`, ни `state.errorMessage` — при
  `state.ads.isEmpty` после отказа рендерится `BoardPopulated` с пустым
  `GridView`, без единого текста/индикатора ошибки или «ничего не найдено».
- Отказ происходит одинаково для гостя и авторизованного пользователя —
  ни один шаг пути `Routes.myAds` → `MyAdsView` → `BoardCubit.load` →
  `AdRepository.getMyAds` не проверяет статус авторизации.

## Связанные тесты

`test/pages/board_cubit_test.dart`, group `'UC-144 — BoardCubit.load ERROR'`
(старая нумерация, будет переименована в `UC-148` отдельным контролируемым
проходом, не трогать сейчас) — 2 теста в группе, **ни один не покрывает
конкретно комбинацию `isMyAds: true` + исключение**:

- `'getAds бросает -> isError=true, errorMessage заполнен, isLoading/isLoadingMore
  сброшены'` — покрывает общую ветку (`isMyAds: false`, вызывается
  `cubit.load(page: 1)` без `isMyAds`), не режим «Мои объявления»
  напрямую — но проходит через тот же самый `catch`-блок `BoardCubit.load`,
  который обрабатывает и `isMyAds: true` (тот же код, без ветвления по
  режиму, см. «Бизнес-правила»), то есть косвенно подтверждает и этот
  сценарий на уровне механизма, не на уровне прямого вызова.
- `'getFavouriteAds бросает -> ловится тем же общим catch, что и обычная
  ветка'` — то же самое: прямое подтверждение для режима «Избранное»,
  косвенное — для «Моих объявлений», тем же рассуждением (общий catch, три
  режима, один код).

**TBD — теста нет** именно на `cubit.load(page: 1, isMyAds: true)` с
`adRepository.getMyAds(...)`, мокнутым как бросающий исключение — ни один
тест файла не воспроизводит этот конкретный вызов в связке с ошибкой; тест
`'isMyAds: true -> вызывает getMyAds с текущими параметрами вместо getAds'`
(тот же файл, группа успешного `BoardCubit.load`) подтверждает только
successful-путь этой комбинации. Покрытие на сегодня — исключительно
косвенное, через идентичность catch-блока, зафиксированную выше и
подтверждаемую чтением `board_cubit.dart`, а не отдельным запущенным тестом.

**TBD — теста нет** ни в одном файле репозиторного уровня
(`test/repositories/ad_repository_test.dart`) на `AdRepository.getAds`/
`getMyAds` вообще — ни для успеха, ни для отказа; файл покрывает только
`createAd`/`updateAd`/`viewAd`/`deleteAd`/`setAdFavourite`
(`grep -n "getAds\|getMyAds" test/repositories/ad_repository_test.dart` не
находит ни одного совпадения).

**TBD — теста нет** на виджет-уровень (`MyAdsView`/`BoardPopulated`) — ни
один существующий тест не проверяет, что при `state.isError == true` экран
рендерит пустой `GridView` без какого-либо текста; все существующие тесты
проверяют только `BoardCubit` напрямую.

## Открытые вопросы и ограничения

- **Прямого теста на `isMyAds: true` + исключение нет — покрытие целиком
  косвенное.** Вывод «тот же catch, что и у `getAds`/`getFavouriteAds`»
  сделан чтением `board_cubit.dart` (единственный `try/catch` без
  ветвления по режиму) и подкреплён тем, что оба реально протестированных
  случая (`getAds`, `getFavouriteAds`) проходят через тот же код — но ни
  один тест не мокает именно `adRepository.getMyAds(...)` как бросающий
  исключение. Риск расхождения структурно мал (код `load()` не различает
  режимы в `catch`-блоке), но эмпирически не подтверждён для этой
  конкретной комбинации.
- **Тот же класс дефекта, что и у общей ленты
  ([UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)), но здесь
  визуально хуже.** Там отказ хотя бы рендерит `BoardEmpty` с текстом
  «ничего не найдено» (пусть и неотличимым от реально пустого результата);
  здесь `MyAdsView` не использует `BoardEmpty` вовсе — при отказе
  показывается буквально пустая прокручиваемая область без единого
  визуального сигнала, что что-то пошло не так, включая тот факт, что нет
  и «ничего не найдено».
- **`getMyAds` не имеет собственного пути обработки ошибок** — весь catch/log
  унаследован от `getAds`, включая текст сообщения лога (`'getAds Error:
  $e'`), которое ничем не указывает, что причиной был именно запрос «Моих
  объявлений» — при разборе `Talker`-лога постфактум это неотличимо от
  отказа обычной ленты.
- **Отсутствие route-гварда авторизации на `Routes.myAds`.** Хотя
  [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md) и
  [MOD-5](../modules/MOD-5-BOARD.md) относят этот сценарий к
  [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (авторизованный пользователь),
  ни маршрут, ни `BoardCubit`, ни `AdRepository.getMyAds` не проверяют это
  фактически — гость реально может открыть «Мои объявления» и получить тот
  же отказ с `user_id=-1`, отправленным на сервер. Является ли это
  осознанным решением (например, ожидание, что сервер сам вернёт пустой/
  ошибочный список для несуществующего пользователя) или недосмотром — не
  зафиксировано в коде/комментариях.
- **Взаимодействие с известным дефектом `refresh()`/`loadNextPage()` не
  форвардящих `isMyAds`** ([EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md)) —
  после отказа этого сценария единственный доступный пользователю путь
  «попробовать снова» — pull-to-refresh, который сам по себе уже переключает
  запрос на `getAds` (общую ленту), а не повторяет `getMyAds`. Это отдельный,
  уже задокументированный дефект — упомянут здесь только как контекст
  «что происходит дальше», не переразбирается глубже в этом файле.
- Не проверено эмпирически против реального бэкенда — вывод сделан
  статическим чтением кода (`AdRepository.getMyAds` → `getAds` →
  `CustomDioClient.call` → `DioClient`), тем же путём, что уже
  верифицирован тестом для общей ленты и «Избранного»
  ([UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md)), но не
  отдельным тестом для этой конкретной комбинации (см. «Связанные тесты»).
