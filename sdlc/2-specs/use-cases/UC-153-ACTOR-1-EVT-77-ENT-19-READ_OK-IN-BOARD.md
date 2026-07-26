# UC-153 — Пользователь открывает список чатов (вкладка «Сообщения»)

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Авторизованный пользователь открывает вкладку «Сообщения»
(`Routes.chats = '/chats'`) и видит список своих переписок
(`ChatsCubit.loadChats` → `ChatsRepository.getChats`, `GET /chats`) — каждая
строка показывает собеседника/объявление, превью последнего сообщения
(`Chat.lastMessage`), время последнего сообщения и счётчик непрочитанных
(`Chat.unreadCount`). Вход на этот экран закрыт двумя независимыми гейтами
(route-редирект по авторизации плюс отдельный, уже специфицированный гейт
доступности раздела по стране), а не одной проверкой. Как и весь модуль
[MOD-5](../modules/MOD-5-BOARD.md), сценарий полностью online-only: нет
локального хранения списка чатов, обновление — только по явному
`loadChats()`/pull-to-refresh, без realtime (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
В отличие от большинства read-сценариев [MOD-5](../modules/MOD-5-BOARD.md)
(лента/карточка объявления — [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md),
доступны и гостю), этот экран требует реальной авторизации: маршрут
`Routes.chats` зарегистрирован с `redirect: (context, state) { if
(!AppCacheService.isAuthorized()) return Routes.profile; return null; }`
(`lib/pages/routes.dart`) — гость никогда не видит `ChatsPage`. Ни
`ChatsCubit`, ни `ChatsRepository.getChats` сами не делают повторной проверки
авторизации (`grep -n "isAuthorized\|AuthRepository"` по
`lib/pages/chats/cubit/chats_cubit.dart` и
`lib/repositories/chats/chats_repository.dart` не находит совпадений) — вся
проверка целиком вынесена в route guard, тот же паттерн, что и у
`Routes.boardAdCreate` внутри соседней ветки `Routes.board`.

## CURRENT

### Основной поток

1. Пользователь переходит на вкладку «Сообщения» (или маршрут `/chats`
   резолвится по любой другой причине — deep link, редирект). `go_router`
   вычисляет `redirect` маршрута `Routes.chats`: если
   `!AppCacheService.isAuthorized()` (`getMainTokenData() == null`) —
   возвращает `Routes.profile`, и `ChatsPage` не строится вовсе.
2. Независимо от этого route-редиректа, вкладка «Сообщения» гейтится ещё и
   доступностью раздела BOARD по стране пользователя — уже
   специфицированное [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
   (`BoardChatAvailabilityCubit`, инициатор [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)):
   `MainPage`'s `BlocListener<BoardChatAvailabilityCubit, bool>` при
   `boardChatAvailable == false` и текущей вкладке с индексом `0`
   (Доска), `1` (Поиск животного) или `3` (Сообщения) немедленно
   переключает на индекс `2` (Главная, `_safeFallbackIndex`) через
   `_onItemTapped` → `navigationShell.goBranch(...)` (`lib/pages/main/main_page.dart`).
   Этот гейт — не route-guard (см. [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md),
   «не является route-guard'ом»), а реактивное переключение вкладки поверх
   уже построенного дерева.
3. `CustomGoRoute.fade` для `Routes.chats` строит `const ChatsPage()` →
   `ChatsView` (`lib/pages/chats/presentation/chats_page.dart`,
   `chats_view.dart`).
4. `ChatsView.build` создаёт `BlocProvider(create: (_) => ChatsCubit()..loadChats())`
   — вызов `loadChats()` планируется синхронно в той же строке, что и
   создание кубита.
5. `ChatsCubit.loadChats()`: `emit(state.copyWith(isLoading: true, isError: false))`,
   затем `await _repository.getChats()`.
6. `ChatsRepository.getChats()`: RPC-вызов `GET {Constants.boardServiceApi}/chats`
   через `getIt<ApiClient>(instanceName: 'farm_rpc')`; ответ передаётся в
   `_parseChats(response['data'] as List)`.
7. `_parseChats` перед разбором самих чатов читает три HANDBOOKS-справочника
   целиком — `BreedsRepository.getAll()`, `SuitsRepository.getAll()`,
   `KindsRepository.getAll()` (все три — `BaseRepository`, локальное
   Drift-чтение уже засинхронизированных данных, без отдельного сетевого
   вызова на каждый список чатов) — они нужны только для того, чтобы
   разобрать вложенный `ad` (если он есть в ответе) через `Ad.fromJson(adJson,
   breeds, suits, kinds)`.
8. Для каждого элемента списка строится `Chat.fromJson(e, breeds:, suits:,
   kinds:)`: если `json['ad']` — непустая карта, вложенный `Ad` разбирается
   целиком и подставляется в `Chat.ad`; иначе `ad == null`, а
   `adTitle`/`adImageUrl`/`adPrice` заполняются из плоских
   `ad_title`/`ad_image_url`/`ad_price` (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)
   про геттеры-фолбэки). `messages` — из `json['chatMessages']` (пустой
   список, если поле отсутствует).
9. Успешный результат: `emit(state.copyWith(chats: chats, isLoading: false))`
   — `isError` не трогается на этом пути (остаётся тем, что было выставлено
   в `false` на шаге 5).
10. `ChatsView`'s `BlocBuilder<ChatsCubit, ChatsState>`: пока `state.isLoading`
    — рендерит `CustomLottieLoader()`; после — `RefreshIndicator` с телом
    `state.chats.isEmpty ? ChatsEmpty() : ChatsPopulated(chats: state.chats, onChatTap: ...)`.
11. `ChatsPopulated` рендерит `ListView.separated` из `_ChatListTile` на
    каждый `Chat`: превью-коллаж объявления (`BoardAdPreviewCollage.fromAd`),
    `chat.peerName`, время последнего сообщения
    (`DateTimeFormat.dateTimeFormatWithoutSeconds(context, chat.lastMessageAt!)`,
    пусто, если `null`), `chat.adTitle`/`chat.adPrice`/`chat.adStatusLabel`
    (последние два — только если не `null`), текст последнего сообщения
    (`chat.lastMessage?.text ?? ''`, максимум 2 строки с обрезкой), и, только
    при `chat.unreadCount > 0`, круглый бейдж `_UnreadBadge(count:
    chat.unreadCount)` (`lib/pages/chats/presentation/chats_populated.dart`).
12. Тап по строке: `onChatTap(chat)` → `context.pushNamed2(Routes.messages,
    extra: MessagesPageArgs(chat: chat))` — переход к переписке, отдельное
    событие [EVT-78](../events/EVT-78-MESSAGES-VIEWED-IN-BOARD.md), вне
    рамок этого файла; состояние `ChatsCubit` при этом не меняется.

### Альтернативные потоки

- **Pull-to-refresh.** `RefreshIndicator.onRefresh` вызывает
  `context.read<ChatsCubit>().refresh()`: `emit(state.copyWith(chats: const
  [], isError: false))` (список сразу очищается, ещё до сетевого ответа),
  затем `await loadChats()` — то есть на один pull-to-refresh приходится
  минимум два видимых состояния (пустой список → результат), не одно.
- **Список пуст (`state.chats.isEmpty`, включая случай, когда сервер
  ответил пустым массивом).** Рендерится `ChatsEmpty` — заголовок/подзаголовок
  (`l10n.chats_empty_title`/`chats_empty_subtitle`) и кнопка `l10n.chats_empty_button`,
  ведущая на `Routes.board` (`context.go(Routes.board)`), а не на создание
  объявления.
- **`AuthToMain` (успешный логин или запуск приложения с уже
  сохранённой сессией) при смонтированном `ChatsView`.** `ChatsView`
  держит собственный `BlocListener<AuthBloc, AuthState>` (внутри того же
  `build`, независимо от `MainPage`): при `state is AuthToMain` вызывает
  `context.read<ChatsCubit>().refresh()`. Параллельно и независимо
  `MainPage`'s отдельный `BlocListener` того же `AuthBloc` реагирует на
  `AuthToMain` собственным побочным эффектом — запускает полный
  синхронизационный проход (`DataUpdateBloc.add(DataUpdateStartAll(...))`,
  модуль SYSTEM) — оба обработчика подписаны на один и тот же поток
  `AuthBloc` и срабатывают независимо друг от друга, без какой-либо
  координации порядка между собой.
- **`AuthLogout` при смонтированном `ChatsView`.** Локальный `BlocListener`
  вызывает `context.read<ChatsCubit>().clear()` → `emit(const ChatsState())`
  (список/флаги сбрасываются к дефолту, без обращения к репозиторию).
  Параллельно `MainPage`'s собственный `BlocListener` на тот же `AuthLogout`
  дополнительно откатывает навигацию (`shellNavigatorMessagesKey.currentState
  ?.popUntil((route) => route.isFirst)`) и принудительно переключает на
  `Routes.profile` (`context.go(Routes.profile)`) — то есть после логаута
  пользователь физически покидает эту вкладку, а не просто видит пустой
  список поверх неё.
- **Ошибка при `getChats()`** (сеть/сервер) — `ChatsCubit.loadChats()`
  ловит исключение, `emit(state.copyWith(isLoading: false, isError: true))`,
  `chats` не трогается. Это ветвление приводит к результату `READ_ERROR`
  — за рамками этого файла (`RESULT = READ_OK`); упомянуто здесь только
  потому что делит один и тот же обработчик `loadChats()` с основным
  потоком. На момент написания этого файла отдельный use-case для
  `READ_ERROR` этого события ещё не существует.

### Связанные сущности

- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — сущность, чьё
  чтение отображает этот экран; читается целиком (`GET /chats`, без
  пагинации на клиенте), не изменяется этим сценарием.
- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) —
  вложена в каждый `Chat.messages`; используется только через
  `messages.lastOrNull` (`Chat.lastMessage`/`lastMessageAt`) для превью
  строки списка, полная переписка на этом экране не рендерится.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — опционально вложен в
  `Chat.ad`; когда присутствует, вытесняет плоские фолбэк-поля
  `adTitle`/`adImageUrl`/`adPrice` через геттеры (см.
  [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)); не изменяется этим
  сценарием.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy —
  Kind/Breed/Suit, HANDBOOKS) — читается целиком (`getAll()` каждого из
  трёх справочников) при каждом вызове `_parseChats`, только для того,
  чтобы разобрать вложенный `Ad`; локальное Drift-чтение уже
  засинхронизированных данных, не отдельный сетевой запрос; не изменяется
  этим сценарием.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  не читается напрямую этим сценарием, но обуславливает, дойдёт ли
  пользователь до этого экрана вообще, через уже специфицированный
  [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
  (`Country.boardEnabled`).

### Бизнес-правила

- Доступ к экрану гейтится двумя независимыми механизмами: route-редирект
  по `AppCacheService.isAuthorized()` (жёсткий guard, срабатывает при
  резолве маршрута) и реактивный гейт [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
  по доступности BOARD для страны пользователя (переключает вкладку уже
  после того, как она построена, не блокирует сам маршрут).
  `ChatsCubit`/`ChatsRepository` не дублируют ни одну из этих проверок сами.
- Список — полная замена при каждой загрузке (`copyWith(chats: chats)`),
  без слияния с предыдущим состоянием и без клиентской пагинации.
- Нет realtime/push и нет клиентского опроса (`BoardChatSocketService`
  нигде не определён в `lib/` — все три упоминания в
  `injection_container.dart`, `main.dart`, `profile_view.dart` полностью
  закомментированы, см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md));
  свежесть списка и счётчика непрочитанных зависит исключительно от того,
  когда в очередной раз был вызван `loadChats()`/`refresh()`.
- Нет явного «прочитано»: открытие списка/переписки не делает отдельного
  запроса «mark as read» — снятие `unreadCount` (если оно вообще
  происходит) полностью зависит от недокументированного побочного эффекта
  сервера на обычный `GET` (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).
- Бейдж непрочитанных отображается только при `unreadCount > 0` — при `0`
  элемент бейджа не рендерится вовсе (не «0», а отсутствие виджета).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (загрузка списка при открытии вкладки), pull-to-refresh
и реакция на смену авторизации полностью реализованы и достижимы через
навигацию; находки, перечисленные в «Открытые вопросы и ограничения», не
блокируют выполнение сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/routes.dart` | маршрут `Routes.chats` (`redirect`) | CURRENT | route-guard — редирект на `Routes.profile`, если `!AppCacheService.isAuthorized()` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized` | CURRENT | `getMainTokenData() != null` — источник признака авторизации для гейта выше |
| `lib/pages/main/main_page.dart` | `_MainPageState.build` (`BlocListener<BoardChatAvailabilityCubit, bool>`, `_onItemTapped`, `_safeFallbackIndex`) | CURRENT | второй гейт — уводит с вкладки «Сообщения» на «Главная», когда BOARD недоступен по стране |
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit` | CURRENT | предмет уже специфицированного [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md), источник флага гейта выше |
| `lib/pages/chats/presentation/chats_page.dart` | `ChatsPage` | CURRENT | тонкая обёртка маршрута над `ChatsView` |
| `lib/pages/chats/presentation/chats_view.dart` | `ChatsView.build` | CURRENT | создаёт `ChatsCubit`, собственный `BlocListener<AuthBloc, AuthState>` (`refresh`/`clear`), переключает loader/empty/populated |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.loadChats`, `.refresh`, `.clear` | CURRENT | предмет этого файла |
| `lib/pages/chats/cubit/chats_state.dart` | `ChatsState` (`chats`, `isLoading`, `isError`) | CURRENT | freezed-состояние экрана |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.getChats`, `._parseChats` | CURRENT | `GET {boardServiceApi}/chats`; сборка справочников для вложенного `Ad` |
| `lib/repositories/breed/breeds_repository.dart` | `BreedsRepository.getAll` | CURRENT | HANDBOOKS-справочник, читается на каждый вызов `_parseChats` |
| `lib/repositories/suit/suits_repository.dart` | `SuitsRepository.getAll` | CURRENT | то же, для мастей |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository.getAll` | CURRENT | то же, для видов |
| `lib/models/chat/chat.dart` | `Chat.fromJson`, `.lastMessage`, `.lastMessageAt`, `.adTitle`/`.adImageUrl`/`.adPrice` | CURRENT | DTO и вычисляемые геттеры превью строки списка |
| `lib/models/chat/chat_message.dart` | `ChatMessage` | CURRENT | элемент `Chat.messages`, источник `lastMessage` |
| `lib/models/board/ad.dart` | `Ad.fromJson` | CURRENT | опциональный вложенный объект объявления внутри чата |
| `lib/pages/chats/presentation/chats_populated.dart` | `ChatsPopulated`, `_ChatListTile`, `_UnreadBadge` | CURRENT | рендер строки списка — превью, время, бейдж непрочитанных |
| `lib/pages/chats/presentation/chats_empty.dart` | `ChatsEmpty` | CURRENT | пустое состояние, CTA на `Routes.board` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthToMain`, `AuthLogout` | CURRENT | состояния, на которые реагирует собственный `BlocListener` внутри `ChatsView` |
| `lib/network/api_client/api_client.dart` | `ApiClient` (`instanceName: 'farm_rpc'`) | CURRENT | RPC-транспорт вызова `GET /chats` |
| `lib/constants.dart` | `Constants.boardServiceApi` | CURRENT | базовый путь `/chats` |

## Критерии приёмки

- При переходе на `Routes.chats` авторизованным пользователем (route-редирект
  не сработал) и при `BoardChatAvailabilityCubit.state == true` ровно один
  раз вызывается `ChatsRepository.getChats()` в момент создания
  `ChatsCubit` (`create: (_) => ChatsCubit()..loadChats()`).
- Успешный ответ переводит состояние в `chats: <результат>`, `isLoading:
  false`, `isError: false`; предыдущее содержимое `chats` полностью
  замещается, не дополняется.
- Пока `isLoading == true`, `ChatsView` рендерит `CustomLottieLoader()`
  вместо списка/пустого состояния.
- При `state.chats.isEmpty` рендерится `ChatsEmpty` (с CTA на
  `Routes.board`), иначе — `ChatsPopulated` со списком строк.
- Каждая строка списка показывает `peerName`, `adTitle`/`adPrice`/
  `adStatusLabel` (только заданные), время и текст последнего сообщения
  (`lastMessageAt`/`lastMessage?.text`, пусто при отсутствии), и бейдж
  непрочитанных — тогда и только тогда, когда `unreadCount > 0`.
- Pull-to-refresh (`RefreshIndicator.onRefresh`) сначала очищает
  `chats`/`isError` (`refresh()`), затем повторно вызывает `getChats()` —
  минимум два наблюдаемых состояния на одно действие пользователя.
- Тап по строке вызывает переход на `Routes.messages` с
  `MessagesPageArgs(chat: chat)` и не изменяет состояние `ChatsCubit`.
- `AuthToMain`, полученный, пока `ChatsView` смонтирован, вызывает
  `ChatsCubit.refresh()`; `AuthLogout` — `ChatsCubit.clear()` (сброс к
  `const ChatsState()`, без сетевого вызова).
- Ни `ChatsCubit`, ни `ChatsRepository.getChats` не выполняют собственной
  проверки авторизации.

## Связанные тесты

`test/pages/chats_cubit_test.dart`:

- group `'UC-153 — ChatsCubit.loadChats'` (старая нумерация, будет
  переименована в `UC-153` отдельным контролируемым проходом, не трогать
  сейчас) — 1 тест: `'успех -> chats заполнен, isLoading:false'` — прямое
  покрытие основного потока: `getChats()` мокается на успешный ответ,
  проверяются `cubit.state.chats`, `.isLoading == false`, `.isError ==
  false`.
- group `'ChatsCubit.refresh'` (без номера, вспомогательная, не отдельный
  use-case) — тест `'очищает chats и isError, затем перезагружает'` —
  покрывает альтернативный поток pull-to-refresh: `refresh()` вызывает
  `getChats()` ровно один раз (`verify(...).called(1)`), итоговый `chats`
  равен результату повторного вызова.
- group `'ChatsCubit.clear'` (без номера, вспомогательная) — тест
  `'сбрасывает состояние к дефолтному'` — после успешной загрузки `clear()`
  возвращает состояние к `const ChatsState()`.
- Соседняя group `'UC-154 — ChatsCubit.loadChats ERROR'` в этом же файле
  покрывает ветку `isError: true` — это результат `READ_ERROR` того же
  события, вне рамок этого файла (`RESULT = READ_OK`), упомянут здесь
  только для полноты картины по файлу теста.

**TBD — теста нет** на сам route-guard (`Routes.chats`'s `redirect`,
`AppCacheService.isAuthorized()`) — ни один тест не проверяет резолв
маршрута для неавторизованного пользователя, только прямое создание
`ChatsCubit()` в обход навигации.

**TBD — теста нет** на гейт [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
в связке именно с вкладкой «Сообщения» (`_onItemTapped(_safeFallbackIndex)`
при `_currentIndex == 3`) — нет теста, воспроизводящего `MainPage` с
`boardChatAvailable == false` и активной вкладкой «Сообщения».

**TBD — теста нет** на собственный `BlocListener<AuthBloc, AuthState>`
внутри `ChatsView` (реакция `refresh()`/`clear()` на `AuthToMain`/
`AuthLogout` через реальный виджет) — существующие тесты вызывают
`cubit.refresh()`/`cubit.clear()` напрямую, не через `AuthBloc`-событие и
не через смонтированный `ChatsView`.

**TBD — теста нет** на рендер `ChatsPopulated`/`ChatsEmpty`/`_UnreadBadge`
(виджет-уровень) — все существующие тесты проверяют только состояние
`ChatsCubit`, не построение самого списка/бейджа.

## Открытые вопросы и ограничения

- **Два независимых, некоординированных гейта входа.** Route-редирект
  (`Routes.chats`) и реактивный гейт [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
  решают разные вопросы (авторизация vs доступность по стране) разными
  механизмами (жёсткий guard vs реактивное переключение вкладки уже поверх
  построенного дерева) — нет единой точки, отвечающей за «может ли этот
  пользователь сейчас увидеть список чатов»; поведение при их
  одновременном срабатывании (например, логаут при одновременной смене
  страны) не воспроизведено и не покрыто тестом.
- **`PageViewBranchContainer` строит все вкладки нижней навигации сразу**
  (`lib/widgets/go_router/page_view_branch_container.dart`:
  `List.generate(widget.children.length, ...)`, неактивные обёрнуты в
  `Offstage(offstage: true, ...)`, но не исключены из дерева, плюс
  `AutomaticKeepAliveClientMixin` держит их состояние живым) — то есть
  ветка «Сообщения» (и, значит, `ChatsCubit()..loadChats()`) потенциально
  строится уже при первом построении `MainPage` в сессии, а не строго в
  момент тапа пользователя по вкладке. Достоверно ли это в связке с тем,
  как `go_router` резолвит `redirect` конкретно для ещё не посещённой
  ветки `StatefulShellBranch`, и совпадает ли фактический момент первого
  вызова `loadChats()` с этим предположением — не проверено ни рантайм-
  тестом, ни явным логом в этом файле; существующие тесты кубита создают
  `ChatsCubit()` напрямую, минуя `MainPage`/навигацию целиком.
- **Ошибка загрузки неотличима от «нет чатов» пользователю** (`isError`
  выставляется, но `ChatsView.build` проверяет только `isLoading`/пустой
  список — уже зафиксированный дефект на уровне
  [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md)). Формально это
  ветвление другого результата (`READ_ERROR`), но оно делит один и тот же
  экран и один и тот же `BlocBuilder`, что и этот `READ_OK`-сценарий.
- **Нет явного «прочитано».** Ни этот экран, ни экран переписки не делают
  отдельного запроса на сброс `unreadCount` — совпадает ли фактическое
  поведение сервера (обнуляет ли он счётчик по самому факту `GET /chats`
  или `GET` переписки, или не обнуляет вовсе) не задокументировано и не
  проверяется клиентским кодом (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).
- **Конкурентная реакция на `AuthToMain` без координации.** Собственный
  `BlocListener` `ChatsView` (`refresh()`) и отдельный `BlocListener`
  `MainPage` (полный `DataUpdateStartAll`) реагируют на одно и то же
  состояние `AuthBloc` независимо; порядок их выполнения относительно друг
  друга не гарантирован ни кодом, ни тестом.
- **Пустая история сообщений элемента списка неотличима от «сообщений
  правда нет».** Если ответ `/chats` для конкретного чата не содержит
  `chatMessages` (или содержит пустой список), `Chat.fromJson` использует
  `[]` по умолчанию — `lastMessage`/`lastMessageAt` становятся `null`,
  превью строки — пустая строка, без явного отличия от чата, где
  сообщений действительно ещё не было.
