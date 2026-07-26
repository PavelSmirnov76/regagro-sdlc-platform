# ENT-19 — Chat

## Описание

Приватная переписка между двумя пользователями об одном объявлении.
**Online-only**, как и [ENT-18](ENT-18-AD-IN-BOARD.md) — `class Chat extends
Equatable` (`lib/models/chat/chat.dart`), нет локального Drift-хранения;
история переписки живёт только в памяти Cubit'а на время жизни экрана и
перезапрашивается заново при каждом открытии.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int? | серверный id — `null` до создания, см. «Инварианты» |
| `peerName` | String | имя собеседника, вычисляется из `ad.payload.name` |
| `peerAvatarUrl` | String? | |
| `adId` | int | ссылка на [ENT-18](ENT-18-AD-IN-BOARD.md) |
| `adTitle`/`adImageUrl`/`adPrice` | String?/String?/String? | приватные поля-fallback (`_adTitle` и т.п.), затенённые геттерами, которые предпочитают одноимённые поля вложенного `ad`, если он загружен |
| `adStatusLabel` | String? | |
| `ad` | `Ad?` | вложенный объект объявления ([ENT-18](ENT-18-AD-IN-BOARD.md)), может отсутствовать в ответе списка чатов |
| `unreadCount` | int, default 0 | счётчик непрочитанных — сброс на сервере происходит без явного клиентского запроса «прочитано» (см. «Инварианты») |
| `messages` | List\<[ChatMessage](ENT-20-CHAT-MESSAGE-IN-BOARD.md)\> | история сообщений |
| `userToId` | int | |
| `userFromId` | int | |

## Связи

- [ENT-18](ENT-18-AD-IN-BOARD.md) (Ad) — по `adId`, опционально вложен целиком
  (`ad`); чат не редактирует объявление.
- [ENT-20](ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) — один-ко-многим,
  `messages`.

## Инварианты

- **`id == null` — не ошибка, а нормальное состояние ещё не созданного чата.**
  Открытие переписки с карточки объявления конструирует `Chat(id: null, ...)`
  на клиенте локально, до какого-либо запроса к серверу; чат физически
  создаётся на сервере (`ChatsRepository.createChat`) только в момент
  отправки первого сообщения — см. [ENT-20](ENT-20-CHAT-MESSAGE-IN-BOARD.md),
  событие отправки сообщения.
- **Перед созданием чата клиент сначала проверяет, не существует ли он уже**
  (`MessagesCubit.findChat()` → `ChatsRepository.findChats(adId, userToId,
  userFromId)`) — если пара пользователь-объявление уже переписывалась
  раньше, найденный чат (с реальным `id` и историей сообщений) подставляется
  в состояние экрана вместо того, чтобы создавать дубликат при первой же
  отправке. Открытие переписки из списка чатов (`ChatsCubit`/`ChatsView`)
  этот шаг не проходит — `chat.id` в этом случае уже не `null`.
- **Нет realtime/push-канала.** Класс `BoardChatSocketService` нигде не
  определён в `lib/` — все упоминания (`injection_container.dart`, `main.dart`,
  `profile_view.dart`) полностью закомментированы: реалтайм-канал был начат и
  выключен/удалён. Обновление списка чатов и счётчика непрочитанных
  происходит только по явному `loadChats()`/pull-to-refresh — обычный REST,
  без WebSocket/polling.
- **Нет явного «прочитано».** Ни `ChatsRepository`, ни `MessagesCubit` не
  делают запроса, аналогичного «mark as read», при открытии переписки —
  снятие счётчика непрочитанных (если оно вообще происходит) полностью
  зависит от недокументированного побочного эффекта на сервере при обычном
  `GET`-запросе.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/models/chat/chat.dart` | `Chat` | CURRENT | DTO, вычисляемые геттеры `adTitle`/`adImageUrl`/`adPrice`/`lastMessage` |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.getChats`, `findChats`, `createChat` | CURRENT | список чатов, поиск существующего чата, создание нового |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.loadChats` | CURRENT | список чатов (R59) |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.findChat`, `sendMessage` | CURRENT | поиск существующего/автосоздание чата при первом сообщении |
