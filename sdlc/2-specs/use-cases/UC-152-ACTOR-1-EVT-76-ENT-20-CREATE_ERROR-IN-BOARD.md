# UC-152 — Отправка сообщения в чате отказывает: сообщение исчезает, набранный текст теряется безвозвратно

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md) |
| Сущность | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же сценарий, что описан в [EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md) —
`MessagesCubit.sendMessage()` добавляет оптимистичное сообщение (временный
отрицательный `id`, `isSending: true`) и **синхронно**, до какого-либо
сетевого вызова, очищает поле ввода. Здесь сам сетевой вызов внутри
`sendMessage()` заканчивается неуспехом — оба вызова, которые могут его
вызвать, объединены одним `try/catch` и проверены отдельно чтением кода:

- (а) `chatsRepository.createChat(...)` бросает исключение — достижимо
  только когда `state.chat.id == null` (первое сообщение переписки, чат ещё
  не создан на сервере);
- (б) `chatsRepository.sendMessage(chatId: ..., message: ...)` бросает
  исключение — достижимо и для уже существующей переписки (`chat.id` был
  задан изначально), и для только что успешно созданной в этой же попытке
  (`createChat` в шаге (а) отработал, но сам `sendMessage` — нет).

В обоих случаях наблюдаемый пользователем итог **идентичен**: оптимистичное
сообщение исчезает из списка, `isError: true` выставляется в состоянии, но
ни один виджет экрана переписки на него не подписан — видимого сообщения об
ошибке нет вообще; единственный и единственно доступный пользователю сигнал —
пропажа только что показанного сообщения. Введённый текст восстановить
невозможно — он был очищен ещё до входа в `try`.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Сам `MessagesCubit` не делает ни одной проверки авторизации (`grep -n
"isAuthorized\|AuthRepository" lib/pages/messages/cubit/messages_cubit.dart`
не находит совпадений) — но фактически до экрана переписки долетает только
уже авторизованный пользователь: `Chat`, с которым открывается
`MessagesView`, конструируется на стороне вызывающего кода с
`userFromId: AppCacheService.getUserId()!` (`_openChat` в
`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart`,
единственный вход в переписку с карточки объявления, второй вход — список
чатов, `lib/pages/chats/presentation/chats_view.dart`, куда чат уже пришёл с
сервера с ненулевым `userFromId`) — это `!`-оператор без проверки на `null`,
и `AppCacheService.getUserId()` (`lib/data/services/app_cache_service.dart`)
возвращает `null` именно тогда, когда пользователь — гость (нет закешированного
`UserHive`). Кнопка «написать» на карточке объявления при этом ничем не
скрыта для гостя (`ad.showChatButton && !ad.isMe`: `showChatButton` для
реально просматриваемого объявления захардкожен в `true`, `isMe` —
`ownerId == AppCacheService.getUserId()`, для гостя `getUserId() == null`,
значит `isMe == false` и `!isMe == true` — оба условия истинны для
незалогиненного зрителя чужого объявления, см. «Открытые вопросы») —
поэтому гость, теоретически способный дойти до этой кнопки, не долетает до
`MessagesCubit.sendMessage()` вовсе: `_openChat` падает раньше, на
конструировании `Chat`, отдельным, не относящимся к этому сценарию,
необработанным `TypeError` (null check operator used on a null value). Этот
файл документирует только уже случившийся вызов
`MessagesCubit.sendMessage()`, то есть только путь [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md).

## CURRENT

### Основной поток

1. Экран переписки открыт (`MessagesView`/`MessagesCubit(chat: chat)`) — либо
   с карточки объявления (`chat.id == null`, автосоздание чата ещё не
   произошло), либо из списка чатов (`chat.id` уже задан).
2. Пользователь набирает текст в `RTextField.outline` композера
   (`lib/pages/messages/presentation/messages_view.dart`, `_MessageComposer`)
   — каждое изменение вызывает `context.read<MessagesCubit>().changeText(text)`
   → `emit(state.copyWith(newMessageText: text))`.
3. Пользователь нажимает кнопку отправки (иконка `send_rounded`) —
   `onPressed: () => context.read<MessagesCubit>().sendMessage()`.
4. `sendMessage()`: `if (state.isLoading) return;` — при уже идущей отправке
   повторный тап не делает ничего. `messageText = state.newMessageText.trim();
   if (messageText.isEmpty) return;` — пустой текст не отправляется.
5. Строится `pendingMessage = ChatMessage(id:
   -DateTime.now().microsecondsSinceEpoch, text: messageText, sentAt:
   DateTime.now(), isOutgoing: true, isRead: false, isSending: true)` —
   гарантированно отрицательный временный `id`.
6. `emit(state.copyWith(isLoading: true, isError: false, newMessageText: '',
   messages: [...state.messages, pendingMessage]))` — **три вещи одним
   emit**: индикатор загрузки, сброс прошлой ошибки, **синхронная очистка
   поля ввода** (до единственной строки сетевого кода ниже) и появление
   пузыря сообщения со спиннером (`_OutgoingBubble` со `isSending: true`,
   `lib/pages/messages/presentation/messages_populated.dart`). Отдельный
   `BlocListener` в `_MessageComposerState`
   (`listenWhen: newMessageText transitions to '' AND _controller.text is
   not empty`) реагирует на этот же emit и вызывает `_controller.clear()` —
   визуально текст исчезает из текстового поля в тот же момент, что и
   появление пузыря с спиннером, до какого-либо ответа сервера.
7. `try`-блок: `var chat = state.chat;`
   - если `state.chat.id == null`: `chatId = await
     chatsRepository.createChat(adId: ..., userToId: ..., userFromId:
     ...);` — **точка (а)**; при успехе `chat = state.chat.copyWith(id:
     chatId); emit(state.copyWith(chat: chat));` — промежуточный emit,
     фиксирующий реальный серверный `id` чата в состоянии **до** попытки
     отправить само сообщение;
   - `response = await chatsRepository.sendMessage(chatId: chat.id, message:
     messageText);` — **точка (б)**, выполняется всегда, независимо от того,
     был ли чат только что создан или уже существовал.
8. При успехе (не этот сценарий): `emit(state.copyWith(isLoading: false,
   messages: state.messages.map(...).toList()))` — `pendingMessage`
   заменяется настоящим `ChatMessage` из `response` (см.
   [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md), `isSending` не
   переносится и остаётся дефолтным `false`).
9. `catch (e)`: `emit(state.copyWith(isLoading: false, isError: true,
   messages: state.messages.where((m) => m.id != pendingMessage.id)
   .toList()))` — **единый обработчик для обеих точек (а) и (б)**: код не
   различает, что именно не удалось.

### Альтернативные потоки

- **Ветка (а) — `createChat` бросает исключение.** Достижимо только при
  первом сообщении переписки. `ChatsRepository.createChat`
  (`lib/repositories/chats/chats_repository.dart`) оборачивает
  `rpcClient.call(...)` собственным `try/catch`, логирует через
  `getIt<Talker>().error('createChat Error: $e')` и безусловно
  перебрасывает (`rethrow`) — источник исключения: сеть недоступна/таймаут,
  либо любой не-2xx HTTP-ответ (`DioClient`,
  `lib/network/dio_client.dart`, не переопределяет `validateStatus` — Dio по
  умолчанию бросает `DioException` вне диапазона 200–299), либо содержимо
  успешный (HTTP 200) ответ без ожидаемой формы: `CustomDioClient.call`
  (`lib/network/api_client/custom_dio_client.dart`) форсирует `status: "1"`
  только если тело содержит ключ `data` (или `animal_exits`, нерелевантно
  здесь); если сервер вернул, например, `{"status": "error", "message":
  ...}` без `data`, `CustomDioClient.call` возвращает этот `Map` как есть,
  без исключения — тогда `response['data']` внутри `createChat` — `null`
  (ключа `data` нет), и `response['data']['chat']` — обращение `[]` к
  `null`, типизированному как `dynamic` — бросает `NoSuchMethodError`
  ("The method '[]' was called on null"), пойманный тем же `try/catch`
  `createChat` и точно так же переброшенный дальше — с точки зрения
  `MessagesCubit` неотличимо от сетевого исключения. **Итог ветки (а):**
  строка `chat = state.chat.copyWith(
  id: chatId); emit(...)` не достигается — `state.chat.id` остаётся `null`,
  как и до попытки, чат на сервере не создан ни в одном из двух случаев.
- **Ветка (б), первое сообщение (`createChat` уже успешно отработал в этой
  же попытке).** `chatsRepository.sendMessage` (тот же файл) бросает по
  тому же спектру причин — сетевое исключение либо (аналогично, но другой
  формы) исключение внутри `ChatMessage.fromJson(response['data'])`
  (`lib/models/chat/chat_message.dart`): если `response` не содержит `data`,
  `response['data']` — `dynamic null`, передаваемый в параметр, статически
  типизированный как ненулевой `Map<String, dynamic> json`, — на границе
  вызова это бросает `TypeError` ("type 'Null' is not a subtype of type
  'Map<String, dynamic>'"), не доходя даже до строки `json['id']`.
  **Важное отличие от ветки (а):**
  промежуточный `emit(state.copyWith(chat: chat))` шага 7 уже выполнился —
  чат реально существует на сервере и `state.chat.id` уже ненулевой на
  момент входа в `catch`. Сам `catch`-блок переписывает только `isLoading`/
  `isError`/`messages` — `chat` в `copyWith` не указан, значит остаётся
  прежним значением состояния (с уже присвоенным `id`). Внешне это выглядит
  как та же самая ошибка отправки, что и в остальных ветках — никакой
  индикации того, что чат de facto уже создан, не показывается.
- **Ветка (б), последующее сообщение (`chat.id` был задан ещё до вызова
  `sendMessage()`).** `createChat` вообще не вызывается (`if (state.chat.id
  == null)` ложно) — единственная сетевая операция попытки — сам
  `sendMessage` репозитория, и именно эта комбинация покрыта существующим
  тестом (см. «Связанные тесты»).
- **Отсутствие ветки `REJECTED`.** Ни `ChatsRepository`, ни
  `CustomDioClient`, ни `MessagesCubit` не отличают содержательный отказ
  сервера (например, «нельзя писать самому себе», «переписка заблокирована»)
  от технического сбоя — любой такой отказ, если он вообще возвращается
  сервером не как исключение, а как логическое тело ответа без ожидаемых
  ключей, всё равно превращается в runtime-исключение при разборе
  (`NoSuchMethodError`/`TypeError`, в зависимости от того, какой именно
  вызов первым натыкается на отсутствующий ключ — см. выше) и попадает в тот
  же единственный `catch`, что и сетевые сбои. Отдельного `REJECTED`-пути в
  коде не существует.
- **Повторная попытка после ошибки.** `isLoading` сброшен в `false` в
  `catch`-блоке, поэтому пользователь может немедленно набрать текст заново
  и повторно нажать отправку в пределах того же открытого экрана — для
  ветки (б) `state.chat.id` уже задан (в том числе после сценария «первое
  сообщение», см. выше), поэтому повторная попытка не создаёт чат дважды;
  для ветки (а) `state.chat.id` остаётся `null`, и `createChat` будет
  вызван заново.

### Связанные сущности

- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — не транзиционирует
  этим сценарием единообразно: в ветке (а) чат не создаётся вовсе
  (`id` остаётся `null`); в ветке (б) при первом сообщении чат к моменту
  отказа уже **успешно создан и закреплён** в состоянии (`chat.id` реальный,
  серверный), несмотря на то что само сообщение не отправлено; в ветке (б)
  при последующем сообщении чат не создаётся и не изменяется этим вызовом
  вовсе (уже существовал).
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — только читается: `adId`/
  `userToId`/`userFromId`, передаваемые в `createChat`/`sendMessage`,
  происходят из `state.chat`, которая, в свою очередь, была сконструирована
  из объявления при открытии переписки (`_openChat`,
  `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart`)
  либо получена уже готовой из списка чатов; объявление не изменяется этим
  сценарием.

### Бизнес-правила

- Оптимистичная отправка и синхронная очистка поля ввода происходят
  **безусловно**, до входа в `try` — то есть до того, как стало известно,
  удастся ли отправка. Это не зависит от того, какая из точек (а)/(б)
  впоследствии откажет — потеря текста гарантирована при любом исходе
  ошибки, а не только при каком-то одном из них.
- Единый `catch` на обе сетевые точки (а)/(б) — сознательного различения
  «не удалось создать чат» и «чат создан, но сообщение не отправлено» в
  коде нет; оба показываются пользователю абсолютно одинаково.
- `isError: true` в `MessagesState` не имеет ни одного подписчика в
  презентационном слое — `grep -rn "isError" lib/pages/messages/presentation/`
  не находит ни одного совпадения ни в `messages_view.dart`, ни в
  `messages_populated.dart`, ни в `messages_empty.dart`, ни в
  `messages_page.dart`. Поле существует в состоянии, но не отображается
  никаким виджетом — ни снэкбаром, ни баннером, ни иконкой ошибки на самом
  сообщении. Единственный наблюдаемый пользователем эффект отказа —
  исчезновение пузыря сообщения, до этого момента показывавшего спиннер
  `isSending`.

## TARGET

TARGET не отличается от CURRENT — этот проход фиксирует уже существующее
поведение (известный UX-дефект), не выполняет исправление.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий воспроизводится статическим
чтением кода (`MessagesCubit.sendMessage` → `ChatsRepository.createChat`/
`.sendMessage` → `CustomDioClient.call`) и подтверждён запущенным тестом
для одной из веток (см. «Связанные тесты»); исправление (например,
восстановление `newMessageText` при отказе, различение веток (а)/(б),
видимый снэкбар при `isError`) в рамках этого документирующего прохода не
выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.sendMessage` | CURRENT | оптимистичная отправка; синхронная очистка `newMessageText` до `try`; единый `catch` на точки (а)/(б); удаляет `pendingMessage` из `messages` при отказе |
| `lib/pages/messages/cubit/messages_state.dart` | `MessagesState.isError`, `.newMessageText`, `.isLoading` | CURRENT | `isError`/`isLoading` сбрасываются в `catch`; `newMessageText` не восстанавливается (не переопределяется в `catch`-`copyWith`) |
| `lib/pages/messages/presentation/messages_view.dart` | `_MessageComposerState` (`BlocListener`, `listenWhen` на `newMessageText`) | CURRENT | синхронизирует `TextEditingController` с уже очищенным `newMessageText`; не подписан на `isError` |
| `lib/pages/messages/presentation/messages_populated.dart` | `_OutgoingBubble` (`isSending`) | CURRENT | рендер спиннера у ещё не подтверждённого сообщения; при отказе сообщение целиком удаляется из списка, отдельного «не отправлено»-состояния бабла нет |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.createChat`, `.sendMessage` | CURRENT | каждый метод — свой `try/catch`, логирует через `Talker` и безусловно `rethrow`; не проверяет `response['status']` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | форсирует `status: "1"` только при наличии ключа `data`/`animal_exits` в ответе; логический ответ без этих ключей возвращается как есть, без исключения — приводит к `NoSuchMethodError`/`TypeError` при разборе выше по стеку (см. «Альтернативные потоки») |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/models/chat/chat_message.dart` | `ChatMessage.fromJson` | CURRENT | параметр `json` типизирован ненулевым `Map<String, dynamic>` — источник `TypeError` ("type 'Null' is not a subtype...") при логическом отказе сервера без ключа `data` в ответе `sendMessage` |
| `lib/models/chat/chat.dart` | `Chat.copyWith` | CURRENT | используется на шаге 7 для фиксации реального `id` чата в состоянии сразу после успешного `createChat`, до попытки отправки сообщения |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState._openChat` | CURRENT | конструирует исходный `Chat` с `userFromId: AppCacheService.getUserId()!` — единственная (неявная) причина, по которой этот сценарий фактически ограничен авторизованным пользователем |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getUserId` | CURRENT | возвращает `null` для гостя — источник несвязанного с этим сценарием, но упомянутого в «Пользователь» падения `_openChat` |

## Критерии приёмки

- Если `state.chat.id == null` и `chatsRepository.createChat(...)` бросает
  любое исключение, `sendMessage()` не вызывает
  `chatsRepository.sendMessage`; `catch`-блок выставляет `isLoading: false`,
  `isError: true`, удаляет `pendingMessage` из `messages`; `state.chat.id`
  остаётся `null`.
- Если `chatsRepository.sendMessage(...)` бросает любое исключение —
  независимо от того, был ли непосредственно перед этим успешно вызван
  `createChat` в этой же попытке, — `catch`-блок выставляет те же
  `isLoading: false`, `isError: true`, удаляет `pendingMessage` из
  `messages`; если `createChat` перед этим успел отработать успешно,
  `state.chat.id` остаётся установленным в реальный серверный id (не
  откатывается).
- `state.newMessageText` после отказа любой из двух точек остаётся пустой
  строкой (была очищена до входа в `try`, `catch`-блок её не переопределяет)
  — исходно набранный текст нигде в состоянии не сохраняется.
- Ни один виджет `lib/pages/messages/presentation/` не читает
  `MessagesState.isError` — визуально отказ не отличается от «сообщение
  тихо не появилось», кроме факта исчезновения ранее показанного пузыря со
  спиннером.
- После отказа `sendMessage()` может быть вызван повторно (не блокируется
  `if (state.isLoading) return`, так как `isLoading` уже сброшен в `catch`).

## Связанные тесты

`test/pages/messages_cubit_test.dart`, group `'UC-152 — MessagesCubit.sendMessage
ERROR (известный UX-дефект — введённый текст теряется)'` (старая нумерация,
будет переименована в `UC-152` отдельным контролируемым проходом, не
трогать сейчас), тест `'sendMessage бросает -> временное сообщение убрано,
isError:true, текст НЕ восстановлен'` — мокает
`chatsRepository.sendMessage(chatId: 100, message: 'Привет')` через
`thenThrow(Exception('network error'))` для чата с уже заданным `id: 100`
(то есть покрывает только ветку «(б), последующее сообщение» из
«Альтернативные потоки» этого файла); проверяет `cubit.state.messages` —
`isEmpty` (временное сообщение удалено из списка целиком), `cubit.state.isError`
— `true`, `cubit.state.isLoading` — `false`, `cubit.state.newMessageText` —
`isEmpty` с явным `reason: 'НАХОДКА подтверждена: поле было очищено ДО
сетевого вызова и не восстанавливается после ошибки — текст потерян
безвозвратно'`.

**TBD — теста нет** на ветку (а) (`createChat` бросает исключение при
`chat.id == null`) — ни один тест файла не мокает `chatsRepository.createChat`
как бросающий исключение.

**TBD — теста нет** на подветку «(б), первое сообщение» (`createChat`
успешно отрабатывает, а последующий `sendMessage` бросает исключение в той
же попытке) — не проверено, что `state.chat.id` при этом остаётся
установленным в реальный серверный id после отказа.

**TBD — теста нет** на отсутствие подписки UI на `isError` (это утверждение
об отсутствии эффекта, подтверждено только чтением кода/`grep`, не
виджет-тестом).

**TBD — теста нет** на подветку логического отказа сервера без ключа
`data` (ни `NoSuchMethodError` для `createChat`, ни `TypeError` для
`sendMessage`/`ChatMessage.fromJson`) — существующий тест воспроизводит
только явное сетевое исключение через `thenThrow`.

## Открытые вопросы и ограничения

- **Единственный сигнал об ошибке — молчаливое исчезновение сообщения,
  причём даже этот сигнал не подкреплён явным UI-элементом.** `isError`
  выставляется в состоянии, но ни `MessagesView`, ни любой из вложенных
  виджетов на него не подписаны — нет ни `SnackBar`, ни инлайн-иконки
  «не отправлено» на самом сообщении (в отличие от, например, стандартного
  паттерна мессенджеров с красным восклицательным знаком/кнопкой повтора).
  Пользователь может интерпретировать пропажу сообщения как что угодно —
  включая ложное впечатление, что оно вовсе не было напечатано.
- **Потерянный текст не восстанавливается никаким способом.** Поле очищено
  синхронно на шаге 6, до входа в `try` — ни один путь `catch` не имеет
  доступа к исходному `messageText` для возврата его в
  `state.newMessageText`, хотя локальная переменная `messageText` технически
  ещё жива в скоупе `catch` (просто не используется). Это простое
  исправление не выполняется в рамках документирующего прохода (см. `TARGET`).
- **Ветки (а) и (б) при первом сообщении переписки оставляют состояние сущности
  [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) в разных, неразличимых для
  пользователя состояниях** — в одном случае чат не создан вовсе, в другом
  уже создан на сервере, но первое сообщение потеряно. Требует ли это
  различие какого-либо особого UX (например, «чат создан, попробуйте
  отправить снова» вместо общего «ошибка отправки») — не зафиксировано ни
  в коде, ни в продуктовых требованиях.
- **`_openChat` (`board_ad_detail_populated.dart`) полагается на
  `AppCacheService.getUserId()!` без проверки на `null`**, при том что
  кнопка «написать» на карточке объявления не скрыта явно для гостя
  (`Ad.toDetailModel()`, `lib/pages/board_ad_detail/data/board_ad_detail_model.dart`,
  — единственный маппер, используемый для реального просмотра
  опубликованного объявления, — хардкодит `showChatButton: true`
  безусловно, независимо от `allowMessages`, которое владелец объявления
  мог выбрать при создании: поле `_data.allowMessages` читается только
  превью-маппером внутри мастера создания объявления
  (`board_ad_create_bloc.dart`), не влияет на то, что видит реальный
  зритель чужого опубликованного объявления; `!ad.isMe` истинно для гостя,
  так как `isMe = (ownerId == AppCacheService.getUserId())`, а
  `getUserId()` для гостя — `null`, что не совпадает ни с одним реальным
  `ownerId`). Формально это отдельный, более ранний по времени сбой
  (`TypeError` до создания `MessagesView`), не относящийся к
  `MessagesCubit.sendMessage()` и не входящий в объём этого файла — но он
  прямо объясняет, почему актором этого сценария де-факто может быть только
  [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), а не гостевой
  [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), несмотря на то что сама
  карточка объявления читается обоими одинаково. Не проверено эмпирически
  (нет теста, запускающего `_openChat` от имени гостя).
- **Не проверено эмпирически на реальном бэкенде.** Форма логического
  отказа без ключа `data` (`{"status": "error", ...}`), приводящая к
  `NoSuchMethodError` внутри `createChat` и к `TypeError` внутри
  `ChatMessage.fromJson`, выведена статическим
  чтением `CustomDioClient.call` по аналогии с уже задокументированным для
  модуля ANIMAL поведением (см.
  [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)), не
  подтверждена реальным ответом `POST .../chats` или `POST
  .../chat-messages`.
