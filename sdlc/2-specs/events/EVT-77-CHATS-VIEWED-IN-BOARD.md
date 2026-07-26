# EVT-77 — chats.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) |

**Триггер.** Авторизованный пользователь открывает вкладку «Сообщения»
(`/chats`, редирект на `/profile`, если не авторизован) — `ChatsCubit.loadChats`.

**Эффект.** `ChatsRepository.getChats` — `GET /chats`, список с превью
последнего сообщения (`Chat.lastMessage`) и счётчиком непрочитанных
(`unreadCount`). Обновляется только по явному `loadChats()`/pull-to-refresh —
нет realtime/push (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)).
**Известный дефект**: `ChatsState.isError` выставляется при исключении, но
`ChatsView.build()` проверяет только `isLoading`/пустой список — при ошибке
экран показывает обычное «нет чатов», неотличимое от реального отсутствия
переписок.

**Исходный код.** `lib/pages/chats/presentation/chats_view.dart`;
`lib/pages/chats/cubit/chats_cubit.dart` → `ChatsCubit.loadChats`, `refresh`,
`clear`; `lib/repositories/chats/chats_repository.dart` → `ChatsRepository.getChats`.
