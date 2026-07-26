# EVT-76 — message.sent

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |

**Триггер.** Авторизованный пользователь набирает текст в поле переписки и
отправляет — `MessagesCubit.sendMessage`. Экран переписки открывается либо с
детальной карточки объявления (`Chat(id: null, ...)`, автора нельзя написать
самому себе — кнопка скрыта при `ad.isMe`), либо из списка чатов (`chat.id`
уже задан).

**Эффект.** Сообщение добавляется оптимистично (временный отрицательный id,
`isSending: true`), поле ввода очищается сразу. Если `state.chat.id == null` —
сначала `ChatsRepository.createChat` (создаёт [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md),
получает реальный id), затем `ChatsRepository.sendMessage`; если чат уже
существует — сразу `sendMessage`. По ответу сервера оптимистичное сообщение
заменяется настоящим. См. [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md)
— при отказе введённый текст не восстанавливается.

**Исходный код.** `lib/pages/messages/cubit/messages_cubit.dart` →
`MessagesCubit.sendMessage`, `findChat`; `lib/repositories/chats/chats_repository.dart` →
`ChatsRepository.createChat`, `sendMessage`, `findChats`.
