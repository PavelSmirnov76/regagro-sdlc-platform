# UC-151 — Пользователь отправляет сообщение в переписке (первое — с автосозданием чата, либо последующее)

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md) |
| Сущность | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Один и тот же метод, `MessagesCubit.sendMessage()`, обслуживает два разных
по наблюдаемому эффекту, но структурно единых сценария:

- **первое сообщение переписки** — экран открыт с `Chat(id: null, ...)`
  (карточка объявления, чат ещё не существует ни на клиенте, ни, возможно,
  на сервере) — перед отправкой самого сообщения `sendMessage()` вызывает
  `ChatsRepository.createChat`, получает реальный `id` чата и только затем
  отправляет сообщение;
- **последующее сообщение** — `state.chat.id` уже задан (открыто из списка
  чатов, либо чат уже был создан более ранним вызовом `sendMessage()` в этой
  же сессии экрана) — `createChat` не вызывается вовсе, сразу
  `ChatsRepository.sendMessage`.

В обеих ветках сообщение сначала добавляется в список оптимистично —
временный отрицательный `id`, `isSending: true`, поле ввода очищается
синхронно, до какого-либо сетевого вызова — и по успешному ответу сервера
заменяется настоящим (см. [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md),
«Инварианты»).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Ни `MessagesCubit`, ни `ChatsRepository` сами не проверяют
`AuthRepository.isAuthorized()`/`AppCacheService.isAuthorized()` ни в одном
методе, задействованном в этом сценарии — авторизация гарантируется только
навигацией: единственный путь к `Routes.messages` — через `Routes.chats`,
маршрут которого закрыт `redirect`-проверкой (`lib/pages/routes.dart`):
`if (!AppCacheService.isAuthorized()) { return Routes.profile; }` —
неавторизованный пользователь до экрана переписки физически не долетает.
Вход с карточки объявления (`_openChat`) дополнительно берёт
`userFromId: AppCacheService.getUserId()!` без null-проверки — полагается на
тот же гейт навигации.

## CURRENT

### Основной поток

1. Экран переписки открывается одним из двух реально существующих в
   навигации входов, оба в итоге строят один `Chat` и передают его в
   `MessagesPage` через `MessagesPageArgs(chat: chat)`:
   - **(a) с детальной карточки объявления** —
     `_BoardAdDetailPopulatedState._openChat`
     (`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart`),
     достижим только когда `ad.showChatButton && !ad.isMe` (кнопка физически
     скрыта на собственном объявлении пользователя) — конструирует
     `Chat(id: null, peerName: ad.ownerName, adId: ad.adId, adTitle:
     ad.title, adPrice: ad.priceLabel, unreadCount: 0, messages: [],
     userToId: ad.ownerId, userFromId: AppCacheService.getUserId()!)` и
     переходит `context.go('${Routes.chats}/${Routes.messages}', extra:
     {Routes.messages: MessagesPageArgs(chat: chat)})`;
   - **(б) из списка чатов** — `ChatsView`/`ChatsPopulated.onChatTap`
     (`lib/pages/chats/presentation/chats_view.dart`) берёт уже загруженный
     `Chat` из `ChatsCubit.loadChats()` (`ChatsRepository.getChats()`, `GET
     ${Constants.boardServiceApi}/chats`) — этот объект уже имеет непустой
     серверный `id` и, как правило, историю `messages`
     (`Chat.fromJson`'s `json['chatMessages']`) — переходит
     `context.pushNamed2(Routes.messages, extra: MessagesPageArgs(chat:
     chat))`.
2. `MessagesPage` (`lib/pages/messages/presentation/messages_page.dart`)
   читает `GoRouterState.of(context).getExtraByName<MessagesPageArgs>(
   Routes.messages)` и строит `MessagesView(chat: args.chat)`.
   `MessagesView.build` создаёт `BlocProvider(create: (_) =>
   MessagesCubit(chat: chat)..findChat())` — конструктор `MessagesCubit`
   (`super(MessagesState(chat: chat, messages: chat.messages))`) фиксирует
   начальный список сообщений сразу из переданного `chat` (пустой для входа
   (a), из ответа сервера для входа (б)).
3. `findChat()` выполняется асинхронно сразу при создании кубита, до
   какого-либо ввода пользователя: если `state.chat.id != null` (вход (б))
   — метод немедленно возвращается, ничего не меняя. Если `state.chat.id ==
   null` (вход (a)) — эмитит `isLoading: true, isError: false`, вызывает
   `ChatsRepository.findChats(adId: state.chat.adId, userToId:
   state.chat.userToId, userFromId: state.chat.userFromId)` (`GET
   ${Constants.boardServiceApi}/chats` с этими тремя параметрами) через
   приватный `_findExistingChat()`, и, если находит существующий чат этой
   же пары пользователь/объявление (`chats.firstOrNull`), подставляет его
   (реальный `id` + история `messages`) в состояние вместо исходного
   `Chat(id: null, ...)` — см. «Альтернативные потоки» о взаимодействии
   этого шага с последующим `sendMessage()`.
4. Пользователь печатает текст в поле композера (`RTextField.outline`
   внутри `_MessageComposer`,
   `lib/pages/messages/presentation/messages_view.dart`); каждое изменение
   — `onChanged: (text) => context.read<MessagesCubit>().changeText(text)`
   → `emit(state.copyWith(newMessageText: text))`.
5. Пользователь нажимает кнопку отправки (`send_rounded`) →
   `context.read<MessagesCubit>().sendMessage()`. `sendMessage()`:
   - если `state.isLoading` — метод немедленно возвращается без какого-либо
     эффекта (гейт от параллельного вызова, в т.ч. пока ещё не завершился
     `findChat()` из шага 3 — см. «Открытые вопросы»);
   - если `state.newMessageText.trim()` пуст — метод немедленно
     возвращается (пустое/whitespace-only сообщение не отправляется,
     кнопка отправки при этом ничем визуально не блокируется — см.
     «Открытые вопросы»);
   - иначе строит `pendingMessage = ChatMessage(id:
     -DateTime.now().microsecondsSinceEpoch, text: messageText, sentAt:
     DateTime.now(), isOutgoing: true, isRead: false, isSending: true)` —
     временный отрицательный `id`;
   - **синхронно**, одним `emit`, до какого-либо сетевого вызова:
     `isLoading: true, isError: false, newMessageText: ''` (поле ввода
     сброшено немедленно), `messages: [...state.messages, pendingMessage]`
     (оптимистичное сообщение уже видно в переписке).
6. Ветвление — единственное, что различает «первое» и «последующее»
   сообщение (обе ветки проверены отдельно чтением кода и отдельным тестом,
   см. «Связанные тесты»):
   - **(а) `state.chat.id == null`** (чат к этому моменту так и не был
     найден/создан — см. шаг 3 и «Альтернативные потоки»): вызывается
     `await chatsRepository.createChat(adId: state.chat.adId, userToId:
     state.chat.userToId, userFromId: state.chat.userFromId)` — `POST
     ${Constants.boardServiceApi}/chats` с телом `{'ad_id': adId,
     'user_ids': [userToId, userFromId]}`; ответ разбирается как
     `response['data']['chat']['id']` (приводится к `int`, если пришла
     строка). Локальная переменная `chat = state.chat.copyWith(id:
     chatId)`; **промежуточный** `emit(state.copyWith(chat: chat))` делает
     новый `id` видимым в состоянии ещё до отправки самого сообщения;
   - **(б) `state.chat.id != null`**: шаг создания чата целиком
     пропускается, `chat` остаётся равным `state.chat` без изменений.
7. В обеих ветках — `final response = await
   chatsRepository.sendMessage(chatId: chat.id, message: messageText)` —
   `POST ${Constants.boardServiceApi}/chat-messages` с телом `{'message':
   ..., 'chat_id': chatId, 'type': 'direct'}`; ответ разбирается
   `ChatMessage.fromJson(response['data'])` (реальный серверный `id`,
   `isOutgoing` вычислен по `user_id == AppCacheService.getUserId()`,
   `isRead` из `is_read`, по умолчанию `true`, если поле отсутствует;
   `isSending` не передаётся конструктору — остаётся `false` по умолчанию).
8. Финальный `emit`: `isLoading: false`, `messages:
   state.messages.map(...)` — сообщение с `id == pendingMessage.id`
   заменяется вручную собранным `ChatMessage` (без `isSending`, без
   `copyWith` от `pendingMessage`) с реальными полями ответа; остальные
   сообщения списка не тронуты. Композер (`_MessageComposer`'s
   `BlocListener`, `listenWhen` на переход `newMessageText` в пустую
   строку) реагирует на очистку поля (уже случившуюся на шаге 5) и
   очищает свой `TextEditingController`, если тот ещё не пуст.

### Альтернативные потоки

- **`findChat()` успевает найти существующий чат раньше, чем пользователь
  отправит сообщение.** Вход (a) с карточки объявления не гарантирует, что
  реально произойдёт ветка (а) шага 6: если пара пользователь/объявление
  уже переписывалась раньше, `findChat()` (шаг 3) успевает подставить
  найденный чат с реальным `id` в состояние раньше нажатия «отправить» —
  тогда `sendMessage()` пойдёт по ветке (б), `createChat` не будет вызван
  вовсе, несмотря на то что экран был открыт с `Chat(id: null, ...)`.
  Явного `await` между построением UI и первым возможным нажатием
  отправки нет, но собственный гейт `sendMessage()`
  (`if (state.isLoading) return;`, шаг 5) не даёт пользователю реально
  отправить сообщение, пока `findChat()` (тоже выставляющий `isLoading:
  true` на время своего запроса) не завершится — так что к моменту, когда
  `sendMessage()` реально выполняет сетевой вызов, `findChat()` уже
  разрешился одним из двух исходов.
- **`findChat()` не находит существующий чат** (`_findExistingChat()`
  возвращает `null`, либо бросает исключение) — `state.chat` остаётся
  равным исходному `Chat(id: null, ...)` (при исключении —
  `catch (e) { emit(state.copyWith(isLoading: false, isError: true)); }`,
  `isError: true` виден в состоянии, но не блокирует последующий
  `sendMessage()`, у которого свой независимый `try/catch`) — дальнейший
  `sendMessage()` идёт по ветке (а) шага 6, как и описано в основном
  потоке.
- **CREATE_ERROR (`createChat`/`sendMessage` бросает исключение в самом
  `sendMessage()`)** — не входит в этот use-case: отдельный сценарий того
  же события, для которого в том же тестовом файле уже существует
  независимая группа тестов (`group('UC-152 — MessagesCubit.sendMessage
  ERROR (известный UX-дефект — введённый текст теряется)')`) — удаление
  `pendingMessage` из списка и безвозвратная потеря введённого текста уже
  задокументированы как инвариант в
  [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md). Отдельный
  `UC-*-CREATE_ERROR`-файл для неё в рамках этого прохода не создаётся.

### Связанные сущности

- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) —
  сущность, совершающая переход: оптимистичная строка (шаг 5) заменяется
  подтверждённой сервером (шаг 8); не хранится нигде, кроме
  `MessagesState.messages` в памяти экрана — модуль полностью online-only,
  нет Drift-таблицы ни для чатов, ни для сообщений; при повторном открытии
  переписки история перечитывается заново с сервера.
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — при `chat.id ==
  null` физически создаётся на этом же пути (шаг 6, ветка а) —
  `id == null` до этого момента не ошибка, а нормальное состояние ещё не
  созданного чата, как уже задокументировано в «Инварианты» ENT-19; после
  успеха `state.chat.id` становится реальным серверным id, видимым и в
  промежуточном, и в финальном `emit`.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — только читается:
  `adId` передаётся в `createChat`/`findChats`, не изменяется этим
  сценарием; поле `ad.showChatButton && !ad.isMe` определяет саму
  достижимость входа (a).

### Бизнес-правила

- Один и тот же метод `MessagesCubit.sendMessage()` обслуживает оба
  сценария (первое/последующее сообщение) — единственное разветвление
  внутри метода — проверка `state.chat.id == null` непосредственно перед
  отправкой, а не отдельно хранимый признак «это первое сообщение».
- Оптимистичное сообщение и очистка поля ввода происходят синхронно, одним
  `emit`, до какого-либо сетевого вызова — независимо от того, какая ветка
  (а/б) сработает дальше.
- `createChat` вызывается не более одного раза за один вызов
  `sendMessage()` и только тогда, когда на момент вызова `state.chat.id`
  всё ещё `null` — что не гарантированно совпадает с «это первое
  сообщение, отправленное с карточки объявления» (см. «Альтернативные
  потоки»).
- Реальный `id` сообщения, полученный от сервера, заменяет временный
  отрицательный `id` по совпадению `message.id == pendingMessage.id` —
  сравнение по значению временного id, не по позиции в списке.
- `isSending` заменённого сообщения не переносится через `copyWith` — новый
  `ChatMessage` строится вручную без этого поля, что по умолчанию даёт
  `false` (корректный итоговый результат, но не через `copyWith`, как уже
  отмечено в [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров нет — обе ветки (первое сообщение с автосозданием чата, последующее
сообщение без повторного создания) полностью реализованы и покрыты тестами
(см. «Связанные тесты»); находки, перечисленные в «Открытые вопросы и
ограничения» (гонка `findChat()`/`sendMessage()`, отсутствие видимой
блокировки кнопки отправки во время `isLoading`, молчаливый no-op на
пустом сообщении), не блокируют выполнение сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState._openChat` | CURRENT | вход (a) — конструирует `Chat(id: null, ...)` с карточки объявления, достижим только при `ad.showChatButton && !ad.isMe` |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel.isMe`, `.showChatButton` | CURRENT | условие достижимости входа (a) |
| `lib/pages/chats/presentation/chats_view.dart` | `ChatsView.build` (`ChatsPopulated.onChatTap`) | CURRENT | вход (б) — уже загруженный `Chat` с реальным `id` из списка чатов |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.loadChats` | CURRENT | источник `Chat` для входа (б) — `ChatsRepository.getChats()` |
| `lib/pages/messages/presentation/messages_page.dart` | `MessagesPage`, `MessagesPageArgs` | CURRENT | точка входа маршрута `Routes.messages`, читает `extra` по имени маршрута |
| `lib/pages/messages/presentation/messages_view.dart` | `MessagesView.build`, `_MessageComposerState` | CURRENT | создаёт `MessagesCubit(chat: chat)..findChat()`, поле ввода, кнопка отправки |
| `lib/pages/routes.dart` | `StatefulShellBranch` («Сообщения»), `redirect` маршрута `Routes.chats` | CURRENT | гейт авторизации: неавторизованный пользователь редиректится на `Routes.profile`, `Routes.messages` — вложенный потомок |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.findChat`, `._findExistingChat`, `.sendMessage`, `.changeText` | CURRENT | предмет этого сценария — обе ветки сходятся в `sendMessage()` |
| `lib/pages/messages/cubit/messages_state.dart` | `MessagesState` | CURRENT | состояние экрана (`@freezed`) |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.createChat`, `.sendMessage`, `.findChats` | CURRENT | сетевые вызовы: `POST /chats`, `POST /chat-messages`, `GET /chats` (поиск существующего) |
| `lib/models/chat/chat.dart` | `Chat`, `Chat.copyWith` | CURRENT | DTO, `id: null` до создания |
| `lib/models/chat/chat_message.dart` | `ChatMessage`, `ChatMessage.fromJson` | CURRENT | DTO сообщения, `isOutgoing` вычисляется по `user_id == AppCacheService.getUserId()` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getUserId`, `.isAuthorized` | CURRENT | `userFromId` входа (a); гейт навигации `Routes.chats` |

## Критерии приёмки

- При `state.chat.id == null` на момент вызова `sendMessage()` выполняется
  ровно один вызов `ChatsRepository.createChat` (с `adId`/`userToId`/
  `userFromId` текущего чата), и только после его успешного завершения —
  `ChatsRepository.sendMessage` с полученным `chatId`.
- При `state.chat.id != null` на момент вызова `sendMessage()`
  `ChatsRepository.createChat` не вызывается вовсе — сразу
  `ChatsRepository.sendMessage` с уже имеющимся `chatId`.
- В обеих ветках оптимистичное сообщение (отрицательный `id`,
  `isSending: true`) добавляется в `state.messages`, а `newMessageText`
  очищается синхронно, до завершения любого из сетевых вызовов.
- По успешному ответу `sendMessage` (в обеих ветках) оптимистичное
  сообщение заменяется в списке новым `ChatMessage` с `id` из ответа
  сервера — длина списка сообщений не меняется, остальные сообщения не
  затронуты.
- `state.isLoading` возвращается в `false` после завершения обеих веток.

## Связанные тесты

- `test/pages/messages_cubit_test.dart`, group `'UC-151 —
  MessagesCubit.sendMessage'`:
  - `'первое сообщение (chat.id == null) -> createChat + sendMessage,
    временное сообщение заменено серверным'` — мокает `createChat`
    (возвращает `100`) и `sendMessage(chatId: 100, message: 'Привет')`,
    конструирует кубит с `_chat()` (`id: null`); проверяет
    `verify(createChat(adId: 1, userToId: 2, userFromId: 3)).called(1)`,
    `cubit.state.chat.id == 100`, единственное сообщение в списке с `id ==
    500` (реплейс временного отрицательного id), `isLoading == false`.
  - `'последующее сообщение (chat.id уже есть) -> createChat НЕ
    вызывается повторно'` — конструирует кубит с `_chat(id: 100)`, мокает
    только `sendMessage(chatId: 100, message: 'Ещё')`; проверяет
    `verifyNever(() => chatsRepository.createChat(adId: any(named:
    'adId'), userToId: any(named: 'userToId'), userFromId: any(named:
    'userFromId')))` и итоговое единственное сообщение с `id == 501`.
- `test/pages/messages_cubit_test.dart`, group `'UC-152 —
  MessagesCubit.sendMessage ERROR (известный UX-дефект — введённый текст
  теряется)'` — не входит в этот use-case (ветка `CREATE_ERROR` того же
  события `message.sent`, уже задокументированная как инвариант в
  [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md)); отдельный
  `UC`-файл для неё в рамках этого прохода не создаётся.
- Старая нумерация группы (`UC-151`) в этом тестовом файле относится к
  прежней схеме id и не переименована на момент написания этой спеки —
  переименование под `UC-151` выполняется отдельным контролируемым
  проходом, не этой задачей; якорь `grep -r "UC-151" test/` заработает
  только после него.
- **TBD — теста нет** на гонку «`findChat()` находит существующий чат до
  нажатия отправки» (см. «Альтернативные потоки») — оба существующих теста
  конструируют кубит напрямую с уже финальным `chat.id` (либо `null`, либо
  заданным), не вызывая `findChat()` перед `sendMessage()`.
- **TBD — теста нет** на поведение composer-виджета (`_MessageComposer`'s
  `BlocListener`, реальная кнопка отправки, видимую (не)блокировку во
  время `isLoading`) — оба существующих теста проверяют только
  `MessagesCubit` напрямую, без построения виджетов.

## Открытые вопросы и ограничения

- **Кнопка отправки ничем не блокируется во время `isLoading`.**
  `_MessageComposerState`'s `onPressed: () =>
  context.read<MessagesCubit>().sendMessage()` не проверяет
  `state.isLoading` — визуально кнопка выглядит одинаково активной, пока
  `findChat()`/предыдущий `sendMessage()` ещё выполняется; собственный
  гейт `sendMessage()` (`if (state.isLoading) return;`) делает повторное/
  параллельное нажатие no-op без какой-либо обратной связи пользователю
  (ни ошибки, ни визуального отклика). Не воспроизведено тестом, не
  разбирается глубже в рамках этого файла.
- **`findChat()` может незаметно сменить ветку сценария.** Вход (a) с
  карточки объявления не гарантирует, что реально произойдёт `createChat`
  — если `findChat()` успевает найти существующий чат первым (шаг 3),
  пользователь фактически проходит по ветке «последующее сообщение», хотя
  открывал экран так, как будто это первое. Отличить, какая ветка
  сработала, пользователю негде — обе визуально неотличимы. Не
  воспроизведено тестом.
- **Пустая/whitespace-only отправка отклоняется молча.**
  `sendMessage()`'s `if (messageText.isEmpty) return;` (после `.trim()`)
  не даёт пользователю никакой обратной связи — кнопка отправки просто
  ничего не делает. Не зафиксировано тестом, не разбирается глубже.
- Ошибочная ветка (`createChat`/`sendMessage` бросает исключение)
  документирована отдельно как инвариант
  [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) и покрыта тестом
  (group `UC-152`, см. «Связанные тесты»), но не как отдельный
  `UC-*-CREATE_ERROR`-файл в рамках этого прохода спецификации.
