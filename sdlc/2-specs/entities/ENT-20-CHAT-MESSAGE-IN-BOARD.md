# ENT-20 — ChatMessage

## Описание

Одно текстовое сообщение внутри [ENT-19](ENT-19-CHAT-IN-BOARD.md) (Chat).
Online-only, как и остальные сущности этого модуля — `class ChatMessage
extends Equatable` (`lib/models/chat/chat_message.dart`), без локального
хранения.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int | серверный id; на клиенте, до подтверждения сервером, временно — **отрицательный** `-DateTime.now().microsecondsSinceEpoch` (оптимистичное сообщение, см. «Инварианты») |
| `text` | String | |
| `sentAt` | DateTime | из `created_at`, `DateTime.tryParse(...) ?? DateTime.now()` — при неразборчивой/отсутствующей дате в ответе тихо подставляется текущее время |
| `isOutgoing` | bool | вычисляется на клиенте: `json['user_id'] == AppCacheService.getUserId()` — принадлежность сообщения текущему пользователю не приходит явным флагом с сервера |
| `isRead` | bool | из `is_read`, по умолчанию `true`, если поле отсутствует в ответе |
| `isSending` | bool, default false | признак «ещё не подтверждено сервером» — используется только для только что созданного оптимистичного сообщения, не сохраняется/не приходит с сервера |

## Связи

- [ENT-19](ENT-19-CHAT-IN-BOARD.md) (Chat) — многие-к-одному, `chatId` передаётся
  отдельным параметром при отправке (не хранится как поле самой модели
  сообщения).

## Инварианты

- **Оптимистичная отправка с временным отрицательным id.** `MessagesCubit.sendMessage()`
  сразу добавляет `pendingMessage` (`isSending: true`, `id` отрицательный,
  `isOutgoing: true` без ожидания сервера) в список и **синхронно** очищает
  поле ввода (`newMessageText: ''`) — до сетевого вызова. После успешного
  ответа сервера это же сообщение по `id` (сравнение с `pendingMessage.id`)
  заменяется настоящим (`ChatMessage.fromJson`, реальный `id`/`isRead`), но
  **`isSending` при этом не переносится** — новый экземпляр строится вручную
  без `isSending`, что по умолчанию `false` — итоговое поведение верное
  (спиннер у отправленного сообщения гаснет), но не через `copyWith`.
- **Потеря введённого текста при отказе отправки.** Если `createChat`/
  `sendMessage` бросает исключение — оптимистичное сообщение убирается из
  списка (`state.messages.where(id != pendingMessage.id)`), но `newMessageText`
  **не восстанавливается** (уже был очищен синхронно в начале метода) —
  пользователю нужно вспоминать и печатать текст заново; единственный сигнал
  об этом — `isError: true` в состоянии экрана.
- **Первое сообщение в переписке неявно создаёт [ENT-19](ENT-19-CHAT-IN-BOARD.md).**
  Если `state.chat.id == null` на момент `sendMessage()`, перед самой
  отправкой выполняется `ChatsRepository.createChat`, и только затем —
  `sendMessage(chatId: ..., message: ...)`. Оба вызова — часть одного
  доменного факта «пользователь отправил сообщение», не два отдельных
  пользовательских действия.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/models/chat/chat_message.dart` | `ChatMessage` | CURRENT | DTO, `isOutgoing` вычисляется на клиенте |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.sendMessage` | CURRENT | оптимистичная отправка, неявное создание чата первым сообщением, потеря текста при отказе |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.sendMessage` | CURRENT | `POST /chat-messages` |
