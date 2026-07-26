# EVT-78 — messages.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |

**Триггер.** Авторизованный пользователь открывает конкретную переписку — с
детальной карточки объявления (кнопка «чат», `Chat(id: null, ...)` создаётся
локально, затем `MessagesCubit.findChat()` ищет, не существует ли уже
переписка с этим автором по этому объявлению) либо тапом по элементу списка
чатов (`chat.id` уже реален, `findChat()` не выполняет поиск повторно).

**Эффект.** При `chat.id == null` — `ChatsRepository.findChats(adId, userToId,
userFromId)`, найденный чат (с историей [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md))
подставляется в состояние экрана вместо создания дубликата при первой
отправке. При уже известном `chat.id` — история сообщений берётся из
переданного `Chat.messages` (список чатов уже содержит вложенные сообщения),
без дополнительного запроса.

**Исходный код.** `lib/pages/messages/presentation/messages_view.dart`;
`lib/pages/messages/cubit/messages_cubit.dart` → `MessagesCubit.findChat`;
`lib/repositories/chats/chats_repository.dart` → `ChatsRepository.findChats`.
