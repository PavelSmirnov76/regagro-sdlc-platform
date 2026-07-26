# UC-155 — Пользователь открывает переписку (из списка чатов — история уже готова, либо с карточки объявления — поиск существующего чата)

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-78](../events/EVT-78-MESSAGES-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Экран переписки (`MessagesPage`/`MessagesView`, подкреплённый
`MessagesCubit`) равнозначно открывается двумя разными путями, которые
по-разному наполняют историю сообщений ([ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md)),
показываемую на экране:

- **(а) с детальной карточки объявления** — чат ещё не существует на
  клиенте (`Chat(id: null, ..., messages: [])`), и экран, сразу после
  построения, сам инициирует сетевой поиск уже существующей переписки
  (`MessagesCubit.findChat()` → `ChatsRepository.findChats`) — успешный
  поиск подставляет найденную историю сообщений вместо пустого списка;
- **(б) из списка чатов** — `chat.id` уже реален, история сообщений уже
  пришла вложенной в ответ `GET /chats` (`ChatsCubit.loadChats()`) —
  `findChat()` не выполняет никакого сетевого запроса, экран показывает
  ровно те сообщения, что были переданы при навигации.

Этот файл специфицирует именно **чтение/отображение** истории сообщений
(`messages.viewed`) — то, что происходит сразу после открытия экрана, до
какого-либо ввода пользователя. Отправка нового сообщения (`sendMessage()`,
включая неявное автосоздание чата первым сообщением) — отдельное, уже
специфицированное событие
[UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md)
([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)); этот файл на неё не
дублируется, только фиксирует состояние экрана в момент открытия,
предшествующее любой отправке.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Ни `MessagesCubit`, ни `ChatsRepository` не проверяют
`AuthRepository.isAuthorized()`/`AppCacheService.isAuthorized()` ни в одном
методе, задействованном в этом сценарии (`findChat`, `_findExistingChat`,
`ChatsRepository.findChats`) — авторизация гарантируется только навигацией:
единственный путь к `Routes.messages` — через дочерний маршрут
`Routes.chats`, чей `redirect` (`lib/pages/routes.dart`) явно проверяет
`if (!AppCacheService.isAuthorized()) { return Routes.profile; }` —
неавторизованный пользователь до экрана переписки не долетает ни одним из
двух входов (вход (a) с карточки объявления тоже переходит через
`'${Routes.chats}/${Routes.messages}'`, то есть через тот же `redirect`).

## CURRENT

### Основной поток

1. Экран переписки открывается одним из двух реально существующих в
   навигации входов — оба строят `Chat` и передают его в `MessagesPage`
   через `MessagesPageArgs(chat: chat)`:
   - **(а) с детальной карточки объявления** —
     `_BoardAdDetailPopulatedState._openChat`
     (`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart`),
     доступна только когда кнопка чата видна вообще (`ad.showChatButton &&
     !ad.isMe` в родительском виджете) — конструирует локально `Chat(id:
     null, peerName: ad.ownerName, adId: ad.adId, adTitle: ad.title,
     adPrice: ad.priceLabel, unreadCount: 0, messages: [], userToId:
     ad.ownerId, userFromId: AppCacheService.getUserId()!)` (поле `ad:`
     конструктору не передано — остаётся `null`) и переходит
     `context.go('${Routes.chats}/${Routes.messages}', extra:
     {Routes.messages: MessagesPageArgs(chat: chat)})`;
   - **(б) из списка чатов** — `ChatsView`/`ChatsPopulated.onChatTap`
     (`lib/pages/chats/presentation/chats_view.dart`) передаёт уже
     загруженный элемент `state.chats` (из `ChatsCubit.loadChats()` →
     `ChatsRepository.getChats()`, `GET ${Constants.boardServiceApi}/chats`)
     — этот `Chat` уже имеет непустой серверный `id`, вложенную историю
     (`Chat.fromJson`'s `json['chatMessages']`) и, если сервер её вернул,
     вложенный `ad` — переход `context.pushNamed2(Routes.messages, extra:
     MessagesPageArgs(chat: chat))`.
2. `MessagesPage` (`lib/pages/messages/presentation/messages_page.dart`)
   читает `GoRouterState.of(context).getExtraByName<MessagesPageArgs>(
   Routes.messages)` и строит `MessagesView(chat: args.chat)`.
3. `MessagesView.build` создаёт `BlocProvider(create: (_) =>
   MessagesCubit(chat: chat)..findChat())`. Конструктор `MessagesCubit`
   (`super(MessagesState(chat: chat, messages: chat.messages))`)
   немедленно фиксирует начальный список сообщений ровно тем, что пришло
   вместе с `chat` — пустой для входа (а), содержимым ответа сервера для
   входа (б) — ещё до того, как `findChat()` успевает выполниться.
4. `findChat()` вызывается сразу же, асинхронно, без ожидания ввода
   пользователя:
   - **если `state.chat.id != null`** (вход (б)) — метод немедленно
     возвращается (`if (state.chat.id != null) return;`), не эмитя ни
     одного нового состояния и не делая ни одного сетевого вызова — история
     сообщений, показанная на экране, остаётся ровно той, что была
     передана на шаге 1(б), без какого-либо дополнительного запроса;
   - **если `state.chat.id == null`** (вход (а)) — эмитит `isLoading: true,
     isError: false`, затем `_findExistingChat()` вызывает
     `chatsRepository.findChats(adId: state.chat.adId, userToId:
     state.chat.userToId, userFromId: state.chat.userFromId)` (`GET
     ${Constants.boardServiceApi}/chats` с этими тремя параметрами вместо
     обычного списка). Если ответ содержит хотя бы один чат
     (`chats.firstOrNull`), метод проверяет `state.chat.id != null` ещё раз
     (защита от повторного входа, пока ждали ответ — если к этому моменту
     `id` уже стал непустым, например из-за параллельного
     `sendMessage()`/`createChat`, эмитится только `isLoading: false` без
     подмены чата) и, если условие всё ещё ложно, эмитит `chat: chat ??
     state.chat, messages: chat?.messages ?? state.messages, isLoading:
     false` — найденный чат (реальный `id` **и** его история сообщений)
     полностью заменяет исходный пустой `Chat(id: null, ...)`.
5. `MessagesView`'s `BlocBuilder<MessagesCubit, MessagesState>` перерисовывает
   тело и шапку по актуальному `state`:
   - **шапка** (`_MessagesHeaderTitle`) — `chat.peerName`/`chat.adTitle` (для
     входа (а) — из значений, зафиксированных при построении `Chat` на шаге
     1, если `findChat()` не заменил чат; `adTitle` — вычисляемый геттер
     `ad?.title ?? _adTitle ?? ''`); тап по заголовку, если `chat.ad != null`,
     ведёт на `Routes.messagesBoardAdDetail` — для входа (а) эта навигация
     недостижима до тех пор, пока `findChat()` не подставит чат с непустым
     `ad` (при исходном построении `Chat` поле `ad` не передано, остаётся
     `null`);
   - **меню звонка** (`_MessagesHeaderMenu`) — пункт «Позвонить» активен
     (`enabled: hasPhone`) только если `chat.ad?.phone` непуст после
     `.trim()` — для входа (а) телефон недоступен до тех пор, пока
     `findChat()` не подставит чат со встроенным `ad`, содержащим `phone`
     (сам исходно построенный `Chat` для входа (а) телефон не несёт вовсе);
   - **тело**: `state.isLoading && state.messages.isEmpty` →
     `CircularProgressIndicator`; иначе, если `state.messages.isEmpty` →
     `MessagesEmpty` (иллюстрация + заголовок/подзаголовок «нет сообщений»);
     иначе → `MessagesPopulated(messages: state.messages)`.
6. `MessagesPopulated` группирует сообщения по календарному дню
   (`_formatDateLabel`: «Сегодня»/«Вчера»/`dd.MM`, вставляя разделитель
   между сообщениями разных дней подряд по порядку списка, без
   собственной пересортировки — порядок берётся ровно таким, каким пришёл
   в `state.messages`) и рендерит их в `SingleChildScrollView`; после
   первого кадра (`addPostFrameCallback(_clampInitialScroll)`) позиция
   скролла подрезается в допустимый диапазон `[0, maxScrollExtent]` — при
   изменении количества сообщений (`didUpdateWidget`) выполняется
   отдельный `_scrollToBottom` с анимацией.

### Альтернативные потоки

- **`findChat()` не находит существующий чат** (`_findExistingChat()`
  возвращает `null` — ни один чат по этой тройке `adId`/`userToId`/
  `userFromId` ранее не создавался). `emit(chat: state.chat, messages:
  state.messages, isLoading: false)` — оба поля остаются равны своим же
  значениям (пустой чат/пустой список), экран показывает `MessagesEmpty`,
  неотличимо от «переписка есть, но в ней пока нет сообщений».
- **`findChat()` бросает исключение** (сетевая ошибка `findChats`) —
  `catch (e) { emit(state.copyWith(isLoading: false, isError: true)); }`.
  `state.chat`/`state.messages` не меняются (остаются исходными, пустыми),
  `isError` становится `true` — но `MessagesView.build` **не читает
  `state.isError` ни в одном месте** (проверено `grep -n "isError"
  lib/pages/messages/`: единственные упоминания вне сгенерированного
  `messages_cubit.freezed.dart` — это сам `messages_cubit.dart`, где поле
  выставляется). Наблюдаемый результат для пользователя — тот же
  `MessagesEmpty`, что и в ветке «не найдено» выше: неудачный поиск и
  подтверждённое отсутствие истории визуально неразличимы (см. «Открытые
  вопросы и ограничения»). Отдельный `UC-*-READ_ERROR`-файл для этой ветки
  в рамках этого прохода не создаётся — тот же принцип разделения
  OK/ERROR по разным use-case, что уже применён в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md) для
  ошибочной ветки `sendMessage()`.
- **Вход (б), но `chat.ad == null` в ответе списка чатов** (согласно
  [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md), вложенный `ad` «может
  отсутствовать в ответе списка чатов») — те же ограничения шапки, что и у
  входа (а) до разрешения `findChat()`: тап по заголовку не ведёт на
  карточку объявления, кнопка звонка неактивна — при этом сама история
  сообщений (предмет этого сценария) не зависит от наличия `ad` и
  отображается полностью в любом случае.
- **Гонка с `sendMessage()`**: если пользователь успевает набрать и
  отправить сообщение до того, как `findChat()` (вход (а)) завершится,
  дальнейшее поведение целиком описано в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md) («Гонка
  `findChat()`/`sendMessage()`»); этот файл её не переописывает.

### Связанные сущности

- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) —
  сущность, чьё отображение — предмет этого сценария: для входа (а)
  начальное значение — пустой список, заменяемый (если поиск успешен)
  историей найденного чата; для входа (б) — список, пришедший при
  навигации, не перезапрашиваемый заново этим сценарием. Ни один шаг этого
  сценария не создаёт и не изменяет ни одно сообщение.
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — для входа (а)
  именно эта сущность резолвится (или нет) шагом `findChat()`:
  `id == null` заменяется реальным серверным `id` при успешном поиске, по
  тому же паттерну, что и создание чата первым сообщением
  ([UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md)), но без
  создания нового чата — только подстановка уже существующего. Ни один шаг
  этого сценария не вызывает `ChatsRepository.createChat`. `unreadCount`
  чата не читается и не сбрасывается этим сценарием ни в каком виде — нет
  вызова, аналогичного «отметить прочитанным» (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md),
  инвариант «Нет явного „прочитано“»).
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — только читается, если
  присутствует: `chat.ad` определяет доступность тапа по заголовку на
  карточку объявления и активность кнопки звонка; для входа (а) до
  разрешения `findChat()` это поле пусто в принципе (конструктор `Chat` на
  шаге 1(а) не передаёт `ad`); не изменяется этим сценарием.

### Бизнес-правила

- Один и тот же метод `findChat()` обслуживает оба входа — единственное
  ветвление внутри него — проверка `state.chat.id == null` в самом начале,
  не отдельно хранимый признак «это вход с карточки объявления».
- Вход (б) никогда не порождает сетевого вызова при открытии переписки —
  вся история уже пришла вложенной в ответ `GET /chats`, отдельного
  эндпоинта «получить сообщения конкретного чата» в `ChatsRepository` нет
  (в файле только `getChats`, `findChats`, `createChat`, `sendMessage`).
- Вход (а) всегда порождает ровно один сетевой вызов `findChats` сразу при
  открытии экрана, независимо от того, наберёт ли пользователь что-либо в
  поле ввода.
- Индикатор загрузки (`CircularProgressIndicator`) показывается только
  пока `state.messages.isEmpty` — если у входа (б) уже есть история
  (`messages` непуст), состояние `isLoading` (которое для входа (б) в
  этом сценарии в принципе не выставляется) не могло бы скрыть уже
  показанные сообщения спиннером в любом случае.
- Пустой результат поиска (не найдено) и ошибка поиска (исключение)
  наблюдаемо неразличимы для пользователя — оба приводят к одному и тому
  же экрану `MessagesEmpty`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба входа (а и б) полностью реализованы и достижимы из UI; находки,
перечисленные в «Открытые вопросы и ограничения» (неразличимость «не
найдено»/«ошибка поиска», отсутствие защиты кнопок шапки до разрешения
`findChat()`, отсутствие явного «прочитано»), не блокируют выполнение
сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState._openChat` | CURRENT | вход (а) — конструирует `Chat(id: null, ..., messages: [])`, без `ad` |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel.isMe`, `.showChatButton` | CURRENT | условие достижимости входа (а) |
| `lib/pages/chats/presentation/chats_view.dart` | `ChatsView.build` (`ChatsPopulated.onChatTap`) | CURRENT | вход (б) — уже загруженный `Chat` с реальным `id` и историей |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.loadChats` | CURRENT | источник `Chat` для входа (б) — `ChatsRepository.getChats()` |
| `lib/pages/messages/presentation/messages_page.dart` | `MessagesPage`, `MessagesPageArgs` | CURRENT | точка входа маршрута `Routes.messages`, читает `extra` по имени маршрута |
| `lib/pages/messages/presentation/messages_view.dart` | `MessagesView.build`, `_MessagesHeaderTitle`, `_MessagesHeaderMenu` | CURRENT | создаёт `MessagesCubit(chat: chat)..findChat()`; рендер шапки (переход на карточку, кнопка звонка) и тела (спиннер/пусто/список) по состоянию |
| `lib/pages/messages/presentation/messages_empty.dart` | `MessagesEmpty` | CURRENT | пустое состояние — общее для «не найдено» и «ошибка поиска» |
| `lib/pages/messages/presentation/messages_populated.dart` | `MessagesPopulated._buildItems`, `_formatDateLabel`, `_clampInitialScroll`, `_scrollToBottom` | CURRENT | группировка по дням, начальная позиция скролла |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit` (конструктор), `.findChat`, `._findExistingChat` | CURRENT | предмет этого сценария |
| `lib/pages/messages/cubit/messages_state.dart` | `MessagesState` | CURRENT | состояние экрана (`@freezed`), поле `isError` не читается ни одним UI-виджетом этого модуля |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.getChats`, `.findChats` | CURRENT | `GET /chats` без фильтра (список, вход б) и с фильтром по `adId`/`userToId`/`userFromId` (поиск существующего, вход а) |
| `lib/models/chat/chat.dart` | `Chat`, `Chat.fromJson`, `.adTitle`, `.adImageUrl`, `.adPrice`, `.lastMessage` | CURRENT | DTO, вычисляемые геттеры, зависящие от наличия вложенного `ad` |
| `lib/models/chat/chat_message.dart` | `ChatMessage.fromJson` | CURRENT | DTO сообщения истории |
| `lib/pages/routes.dart` | `redirect` маршрута `Routes.chats` | CURRENT | гейт авторизации, общий для обоих входов (вход (а) тоже проходит через `'${Routes.chats}/${Routes.messages}'`) |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized`, `.getUserId` | CURRENT | проверка в `redirect`; `userFromId` при построении `Chat` для входа (а) |

## Критерии приёмки

- При открытии экрана с `chat.id != null` (вход (б)) `ChatsRepository.findChats`
  не вызывается ни разу, а отображаемые сообщения совпадают в точности со
  списком, переданным в `MessagesPageArgs.chat.messages`.
- При открытии экрана с `chat.id == null` (вход (а)) выполняется ровно один
  вызов `ChatsRepository.findChats(adId, userToId, userFromId)` с
  параметрами исходного чата.
- Если этот вызов возвращает непустой список, отображаемые сообщения и
  `state.chat.id` заменяются на данные первого найденного чата
  (`chats.firstOrNull`); если он возвращает пустой список — оба остаются
  равны исходным значениям (пустой список, `id == null`).
- Если вызов бросает исключение — `state.isError` становится `true`, но
  `state.chat`/`state.messages` не меняются, а `MessagesView` показывает
  тот же `MessagesEmpty`, что и при пустом результате поиска.
- Индикатор загрузки виден только когда `state.isLoading == true` **и**
  `state.messages.isEmpty` одновременно.
- Тап по заголовку (переход на карточку объявления) и пункт «Позвонить» в
  меню шапки доступны тогда и только тогда, когда `state.chat.ad != null`
  (соответственно непуст `phone`).

## Связанные тесты

**TBD — теста нет.** `test/pages/messages_cubit_test.dart` не содержит ни
одного вызова `cubit.findChat()` — обе группы файла, `'UC-151 —
MessagesCubit.sendMessage'` и `'UC-152 — MessagesCubit.sendMessage ERROR
(известный UX-дефект — введённый текст теряется)'`, конструируют
`MessagesCubit(chat: ...)` и сразу вызывают `changeText`/`sendMessage`,
минуя `findChat()` целиком; `chatsRepository.findChats` не застаблен и не
проверяется (`verify`/`verifyNever`) ни в одном тесте этого файла. Тест
`'первое сообщение (chat.id == null) -> createChat + sendMessage...'`
использует `_chat()` с `id: null`, но это — общее начальное значение
конструктора, а не результат выполнения `findChat()`: сам метод в этом
тесте не вызывается ни разу, поэтому его нельзя честно засчитать даже как
косвенное покрытие ветки «не найдено» — тест ничего не проверяет про
`findChat()`/`_findExistingChat()` и не отличил бы эту ветку от полного
отсутствия метода в коде.

Нет теста и на уровне навигации/виджетов (`MessagesView`, оба входа,
рендер шапки/`MessagesEmpty`/`MessagesPopulated` в зависимости от
состояния) — существующие тесты работают только с `MessagesCubit`
напрямую.

## Открытые вопросы и ограничения

- **«Не найдено» и «ошибка поиска» неразличимы для пользователя.**
  `findChat()` выставляет `isError: true` при исключении, но
  `MessagesView.build` не проверяет `state.isError` ни в одном месте
  (подтверждено `grep -n "isError" lib/pages/messages/` — единственные
  непустые совпадения вне generated-файла принадлежат самому
  `messages_cubit.dart`). Пользователь, впервые открывший переписку с
  карточки объявления, видит один и тот же экран `MessagesEmpty`
  независимо от того, действительно ли переписки ещё не было, или запрос
  `findChats` не удался из-за сети — тот же класс дефекта, что уже
  зафиксирован для соседнего события [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md)
  (`ChatsView`/`isError`), но здесь обнаружен и фиксируется отдельно,
  впервые для этого экрана. Не воспроизведено тестом.
- **Кнопки шапки (переход на карточку, звонок) для входа (а) недоступны,
  пока `findChat()` не разрешится успешно.** Пользователь, открывший
  экран впервые (до того как найдена существующая переписка), не может
  ни перейти на карточку объявления, ни позвонить прямо с экрана
  переписки — обе возможности появляются только если `findChat()` находит
  чат с вложенным `ad`. Не считается ошибкой этим файлом (те же
  ограничения признаны нормальным для входа (б) при отсутствующем `ad` в
  ответе `/chats`, см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), но
  фиксируется как наблюдение по коду.
- **Нет отдельного эндпоинта «сообщения этого чата».** История для входа
  (б) — это ровно то, что вернул `GET /chats` в момент последней загрузки
  списка (`ChatsCubit.loadChats()`/`refresh()`), не перезапрашиваемое при
  открытии конкретной переписки: если собеседник отправил сообщение уже
  после того, как список чатов был загружен, но до открытия конкретной
  переписки, оно не появится, пока пользователь не вернётся в список и не
  обновит его (pull-to-refresh) — нет ни realtime-канала, ни отдельного
  запроса «обновить эту переписку» (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md),
  «Нет realtime/push-канала»). Не воспроизведено тестом.
- **Нет явного «прочитано».** Открытие переписки (оба входа) не делает ни
  одного запроса, аналогичного «отметить сообщения прочитанными» —
  снятие/несъём счётчика `unreadCount` в списке чатов после открытия
  переписки полностью зависит от недокументированного побочного эффекта
  сервера (уже зафиксировано на уровне [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md));
  этот сценарий его не проверяет и не может проверить локально, поскольку
  `unreadCount` самого открытого чата в `MessagesView` вообще не читается.
- Гонка `findChat()`/`sendMessage()` и потенциальная смена ветки сценария
  «первое/последующее сообщение» уже разобраны в
  [UC-151](UC-151-ACTOR-1-EVT-76-ENT-20-CREATE_OK-IN-BOARD.md) — не
  переописывается здесь повторно.
