# UC-156 — Поиск существующего чата при открытии переписки с карточки объявления отказывает: экран молча выглядит как пустая, ещё не начатая переписка

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-78](../events/EVT-78-MESSAGES-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же экран переписки, что и в [EVT-78](../events/EVT-78-MESSAGES-VIEWED-IN-BOARD.md):
открыт с детальной карточки объявления, чат ещё не существует на клиенте
(`Chat(id: null, ...)`), и `MessagesCubit.findChat()` асинхронно проверяет,
не переписывался ли пользователь с этим автором по этому объявлению раньше.
Здесь сам сетевой вызов внутри `findChat()` заканчивается исключением —
`try/catch` перехватывает его и переводит состояние экрана в `isError:
true`, не трогая ни `chat`, ни `messages`. Ни `MessagesView`, ни любой
дочерний виджет экрана переписки нигде не читают поле `isError` —
`grep -rn "isError" lib/pages/messages/presentation/` не находит ни одного
совпадения. Наблюдаемый пользователем результат — экран, который выглядит
неотличимо от обычной, ещё не начатой переписки (`MessagesEmpty`, «No
messages» / «Send the first message»), без единого визуального признака
того, что поиск существующего чата не удался.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Как и в [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md), ни
`MessagesCubit`, ни `ChatsRepository` не проверяют
`AuthRepository.isAuthorized()`/`AppCacheService.isAuthorized()` ни в одном
методе этого сценария — авторизация гарантируется только навигацией:
единственный путь к `Routes.messages` — через `Routes.chats`, чей маршрут
закрыт `redirect`-проверкой (`lib/pages/routes.dart`): `if
(!AppCacheService.isAuthorized()) { return Routes.profile; }`. Вход, ведущий
к этому сценарию, — карточка объявления
(`_BoardAdDetailPopulatedState._openChat`,
`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart`),
которая берёт `userFromId: AppCacheService.getUserId()!` без null-проверки,
полагаясь на тот же гейт.

## CURRENT

### Основной поток

1. Пользователь открывает переписку с детальной карточки объявления
   (достижимо только при `ad.showChatButton && !ad.isMe` — кнопка чата
   физически скрыта на собственном объявлении) — `_openChat` строит
   `Chat(id: null, peerName: ad.ownerName, adId: ad.adId, adTitle:
   ad.title, adPrice: ad.priceLabel, unreadCount: 0, messages: [],
   userToId: ad.ownerId, userFromId: AppCacheService.getUserId()!)` и
   переходит `context.go('${Routes.chats}/${Routes.messages}', extra:
   {Routes.messages: MessagesPageArgs(chat: chat)})`.
2. `MessagesPage` читает `MessagesPageArgs` из `extra` и строит
   `MessagesView(chat: args.chat)`. `MessagesView.build`
   (`lib/pages/messages/presentation/messages_view.dart`) создаёт
   `BlocProvider(create: (_) => MessagesCubit(chat: chat)..findChat())` —
   `findChat()` вызывается ровно один раз, сразу при создании кубита, без
   какого-либо действия пользователя.
3. `MessagesCubit.findChat()` (`lib/pages/messages/cubit/messages_cubit.dart`):
   `if (state.chat.id != null) return;` — на этом входе `state.chat.id ==
   null` (шаг 1), условие ложно, метод продолжается. `emit(state.copyWith(
   isLoading: true, isError: false))`.
4. Внутри `try`: `final chat = await _findExistingChat();` —
   `_findExistingChat()` вызывает `chatsRepository.findChats(adId:
   state.chat.adId, userToId: state.chat.userToId, userFromId:
   state.chat.userFromId)`.
5. `ChatsRepository.findChats` (`lib/repositories/chats/chats_repository.dart`)
   выполняет `GET ${Constants.boardServiceApi}/chats` с этими тремя
   параметрами через `rpcClient.call(message)` внутри собственного
   `try/catch`. Здесь `rpcClient.call` бросает исключение (сеть недоступна,
   таймаут, не-2xx ответ — `CustomDioClient.call` логирует и безусловно
   перебрасывает любое исключение из `dio.request`, как и в
   [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md) для
   аналогичного `farm_rpc`-клиента) — `catch (e) {
   getIt<Talker>().error('findChats Error: $e'); rethrow; }` логирует
   строку через `Talker` (видна только в консоли отладки/DevTools, не в
   UI) и перебрасывает исключение дальше.
6. Исключение всплывает из `await chatsRepository.findChats(...)` внутри
   `_findExistingChat()` (без собственного `try/catch` в этом приватном
   методе) и из `await _findExistingChat()` на шаге 4 — попадает во
   внешний `catch (e)` метода `findChat()`: `emit(state.copyWith(isLoading:
   false, isError: true));`. Поля `chat` и `messages` не переданы в этот
   `copyWith` — остаются равными тому, что было на момент входа в
   `findChat()`, то есть исходному `Chat(id: null, ...)` с пустым
   `messages: []` (шаг 1).
7. `MessagesCubit` — `Cubit`, не эмитит ничего после `catch`; метод
   `findChat()` завершается. Экран не делает никакой повторной попытки —
   `findChat()` вызывается ровно один раз за время жизни `MessagesCubit`
   (единственный вызов — шаг 2), нет ни pull-to-refresh, ни кнопки повтора
   на экране переписки.
8. `MessagesView`'s `BlocBuilder<MessagesCubit, MessagesState>` перестраивает
   `Expanded`-тело: `state.isLoading && state.messages.isEmpty ?
   CircularProgressIndicator() : state.messages.isEmpty ? MessagesEmpty() :
   MessagesPopulated(...)`. После шага 6 `isLoading == false`, `messages ==
   []` (не тронуты) — первая ветвь ложна (`isLoading` уже `false`), вторая
   истинна (`messages.isEmpty`) → рендерится `MessagesEmpty()` — тот же
   виджет, что показывается при легитимно пустой, ещё не начатой переписке.
   `state.isError` нигде не читается ни в `MessagesView`, ни в
   `MessagesEmpty`, ни в `_MessagesHeaderTitle`/`_MessagesHeaderMenu`/
   `_MessageComposer` — `grep -rn "isError"
   lib/pages/messages/presentation/` не находит ни одного совпадения.
9. Заголовок шапки (`_MessagesHeaderTitle`) и меню звонка
   (`_MessagesHeaderMenu`) строятся из `chat.peerName`/`chat.ad` как обычно
   — они не зависят от исхода `findChat()`, поскольку `chat` в этом
   сценарии остаётся исходным объектом с карточки объявления (шаг 1),
   который уже содержит `peerName`/`adTitle`/`adPrice` в виде fallback-полей
   (без вложенного `ad`, см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).

### Альтернативные потоки

- **Пользователь всё равно отправляет сообщение, несмотря на незамеченную
  ошибку.** `sendMessage()` не проверяет `state.isError` — единственный
  гейт — `if (state.isLoading) return;` (уже `false` после шага 6).
  Поскольку `state.chat.id` так и остался `null` (шаг 6 не восстанавливает
  чат), `sendMessage()` идёт по ветке (а) из
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md) — вызывает
  `createChat`, создавая **новый** чат, даже если переписка с этим автором
  по этому объявлению уже существовала на сервере: именно это должен был
  предотвратить неудавшийся `findChats` (см.
  [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md), «Перед созданием чата
  клиент сначала проверяет, не существует ли он уже»). Итог — потенциальный
  дубликат чата для одной и той же пары пользователь/объявление, без
  какого-либо сообщения пользователю о причине.
- **`state.chat.id != null` на входе — сценарий недостижим.** Если экран
  открыт из списка чатов (`ChatsView`), `chat.id` уже реален, `findChat()`
  возвращается на шаге 3 первой строкой (`if (state.chat.id != null)
  return;`) до входа в `try/catch` — исключение из `chatsRepository.findChats`
  в этом случае вообще не может произойти, потому что сам вызов не
  выполняется. `READ_ERROR` этого сценария достижим только через вход с
  карточки объявления (шаг 1).
- **Исключение внутри `_parseChats`, а не в самом сетевом вызове.**
  `ChatsRepository.findChats`'s `try` охватывает и `rpcClient.call`, и
  последующий `_parseChats(response['data'] as List)` (загружает справочники
  пород/мастей/видов через `BreedsRepository`/`SuitsRepository`/
  `KindsRepository`, затем `Chat.fromJson` на каждый элемент, либо падение
  `as List`/`as Map<String, dynamic>` при неожиданной форме ответа) — любое
  из этих исключений перехватывается тем же `catch (e) {
  getIt<Talker>().error('findChats Error: $e'); rethrow; }` и приводит к
  тому же наблюдаемому исходу (шаг 6), что и сетевое исключение; код не
  различает эти источники.
- **Гонка с `sendMessage()`, стартовавшим до отказа `findChat()`.** Если
  пользователь успевает нажать «отправить» до того, как `findChat()`
  вернёт ошибку, `sendMessage()`'s собственный гейт (`if (state.isLoading)
  return;`) не пропускает вызов, пока `isLoading == true` от `findChat()`
  (шаг 3) — тот же гейт, что описан в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md) для
  successful-веток. К моменту, когда `sendMessage()` реально выполнит
  сетевой вызов, `findChat()` уже завершился одним из исходов, включая
  этот (`isError: true`).

### Связанные сущности

- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) —
  сущность, которую должен был вернуть неудавшийся запрос (история
  сообщений найденного чата, если бы он существовал); в этом сценарии
  `state.messages` остаётся пустым списком, полученным при построении
  `Chat` на карточке объявления (шаг 1), не изменяется.
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — `state.chat`
  остаётся исходным `Chat(id: null, ...)`; поиск существующего чата,
  который должен был подставить сюда реальный `id`+историю при совпадении,
  не удаётся и не повторяется; см. «Альтернативные потоки» о риске
  дублирования чата при последующей отправке сообщения.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — только читается:
  `adId` уже зафиксирован в исходном `Chat` (карточка объявления,
  `_openChat`), передаётся в `findChats` как один из трёх параметров
  поиска; не изменяется этим сценарием.

### Бизнес-правила

- `findChat()` вызывается ровно один раз, синхронно при создании
  `MessagesCubit` — нет retry, нет pull-to-refresh, нет отдельного действия
  пользователя «повторить поиск чата» нигде на этом экране.
- `isError: true` в `MessagesState` — состояние, которое сохраняется до
  конца жизни виджета (никакой последующий код его не сбрасывает и не
  перечитывает), но структурно не имеет ни одного потребителя в
  presentation-слое `MessagesView`/`MessagesEmpty`/`MessagesPopulated` —
  поле выставляется исключительно для того, чтобы никогда не быть
  прочитанным.
- Отказ поиска существующего чата не блокирует последующую отправку
  сообщения (`sendMessage()` не проверяет `isError`), но и не защищает от
  дублирования переписки, которое сам поиск был призван предотвращать (см.
  [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий полностью воспроизводится
статическим чтением кода: `MessagesCubit.findChat` → `_findExistingChat` →
`ChatsRepository.findChats` → `CustomDioClient.call`/`DioClient`, и
независимо — `grep -rn "isError" lib/pages/messages/presentation/`,
подтверждающий отсутствие любого потребителя поля в UI. Исправление (чтение
`state.isError` в `MessagesView`, например баннер повторной попытки) в
рамках этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState._openChat` | CURRENT | единственный вход, на котором этот сценарий достижим — строит `Chat(id: null, ...)` с карточки объявления |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel.isMe`, `.showChatButton` | CURRENT | условие достижимости входа (`ad.showChatButton && !ad.isMe`) |
| `lib/pages/messages/presentation/messages_page.dart` | `MessagesPage`, `MessagesPageArgs` | CURRENT | точка входа маршрута `Routes.messages`, читает `chat` из `extra` |
| `lib/pages/messages/presentation/messages_view.dart` | `MessagesView.build` | CURRENT | создаёт `MessagesCubit(chat: chat)..findChat()`; `BlocBuilder`'s ветвление `isLoading`/`messages.isEmpty`, не читающее `isError` |
| `lib/pages/messages/presentation/messages_empty.dart` | `MessagesEmpty` | CURRENT | виджет, рендерящийся в этом сценарии — идентичен легитимно пустой переписке, не параметризован по `isError` |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.findChat`, `._findExistingChat`, `.sendMessage` | CURRENT | предмет этого сценария — `try/catch` вокруг `_findExistingChat()`, эмитящий `isError: true` без изменения `chat`/`messages` |
| `lib/pages/messages/cubit/messages_state.dart` | `MessagesState.isError` | CURRENT | поле, устанавливаемое этим сценарием и не имеющее потребителя в UI |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.findChats`, `._parseChats` | CURRENT | сетевой вызов (`GET /chats` с `ad_id`/`user_to_id`/`user_from_id`), логирует через `Talker` и перебрасывает любое исключение (сетевое или парсинга) |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/pages/routes.dart` | `redirect` маршрута `Routes.chats` | CURRENT | гейт авторизации: неавторизованный пользователь редиректится на `Routes.profile` до того, как долетит до `Routes.messages` |

## Критерии приёмки

- Если на момент вызова `findChat()` `state.chat.id == null` и
  `chatsRepository.findChats(...)` (вызванный через `_findExistingChat()`)
  бросает исключение, `MessagesCubit` эмитит ровно одно финальное
  состояние с `isLoading: false, isError: true`, оставляя `chat` и
  `messages` равными их значению на входе в `findChat()`.
- После этого отказа `state.messages.isEmpty == true` приводит к рендеру
  `MessagesEmpty()` в `MessagesView`, тому же виджету, что и при легитимно
  пустой, ещё не начатой переписке — не должно быть визуального отличия
  без явного чтения `state.isError` (текущий код его не читает нигде в
  presentation-слое).
- `findChat()` не вызывается повторно после отказа в рамках жизни одного
  `MessagesCubit` — нет кода, реагирующего на `isError: true` попыткой
  повтора.
- Последующий вызов `sendMessage()` после этого отказа не блокируется
  `isError` и идёт по ветке «первое сообщение» (`state.chat.id == null` →
  `createChat`), как описано в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md).

## Связанные тесты

**TBD — теста нет.** `test/pages/messages_cubit_test.dart` содержит группы
`'UC-151 — MessagesCubit.sendMessage'` и `'UC-152 — MessagesCubit.sendMessage
ERROR (известный UX-дефект — введённый текст теряется)'` — обе покрывают
только `sendMessage()`. Ни один тест файла не мокает `chatsRepository.findChats`
и не вызывает `MessagesCubit.findChat()` — сценарий этого файла (исключение
внутри `findChat()`, `isError: true` без изменения `chat`/`messages`, и то,
что `isError` не имеет потребителя в UI) не проверен ни одним существующим
тестом.

## Открытые вопросы и ограничения

- **`isError` — поле без единого потребителя в presentation-слое.**
  `MessagesState.isError` выставляется в `true` этим сценарием, но ни
  `MessagesView`, ни `MessagesEmpty`, ни `MessagesPopulated`, ни
  `_MessageComposer` его не читают (`grep -rn "isError"
  lib/pages/messages/presentation/` — ноль совпадений). Пользователь,
  чей поиск существующего чата отказал по сети, видит экран, полностью
  неотличимый от легитимно пустой, ещё не начатой переписки — нет ни
  снэкбара, ни баннера, ни иконки ошибки, ни кнопки «повторить». Является
  ли отсутствие обработки `isError` в UI осознанным решением (например,
  ожидание, что `sendMessage()` всё равно исправит ситуацию, создав новый
  чат) или недосмотром — ничем в коде/комментариях не зафиксировано.
- **Риск дублирования чата после этого отказа.** Поскольку `findChat()` —
  единственный механизм, предотвращающий повторное создание чата для уже
  переписывавшейся пары (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)),
  а его отказ оставляет `state.chat.id == null` без восстановления,
  последующая отправка сообщения (`sendMessage()`) создаёт новый чат через
  `createChat`, даже если такая переписка уже существовала на сервере. Не
  проверено тестом — эффект выведен чтением кода `sendMessage()`'s ветки
  (а), уже задокументированной в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md).
- **Нет retry ни в каком виде.** `findChat()` вызывается один раз при
  создании `MessagesCubit`; единственный способ повторить попытку —
  закрыть экран переписки и открыть его заново с той же карточки
  объявления (пересоздаёт `MessagesCubit`, вызывает `findChat()` заново) —
  ничем в UI пользователю не подсказано, что это нужно сделать.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`MessagesCubit.findChat` → `ChatsRepository.findChats` →
  `CustomDioClient.call` → `DioClient`), без запущенного теста,
  подтверждающего именно эту ветку (см. «Связанные тесты» — TBD).
