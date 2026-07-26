# UC-154 — Загрузка списка чатов отказывает: ChatsState.isError выставляется, но ChatsView.build() его нигде не читает — экран показывает обычное «нет сообщений»

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`ChatsCubit.loadChats()` — единственная точка загрузки списка чатов
(`ChatsView`/вкладка «Сообщения») — при исключении корректно выставляет
`ChatsState.isError = true` вместе с `isLoading = false`. Но
`ChatsView.build()` нигде не читает поле `isError` (подтверждено
`grep -rn "isError" lib/pages/chats/` — единственные совпадения на этот
токен во всей папке `chats/` лежат в `chats_state.dart`, `chats_cubit.dart`
и сгенерированном `chats_cubit.freezed.dart`; в `chats_view.dart` этого
токена нет вовсе): единственная развилка в `build()` — `state.isLoading`
(показать лоадер) и, если не идёт загрузка, `state.chats.isEmpty` (показать
`ChatsEmpty` или `ChatsPopulated`). При отказе `isLoading` уже `false`, а
`chats` не заполнен — экран рендерит ровно тот же `ChatsEmpty()`, что и при
реальном отсутствии переписок, без единого признака того, что запрос вообще
не выполнился.

Дефект достижим двумя разными путями, оба разобраны отдельно, поскольку
ведут к разным итоговым визуальным результатам, хоть код-путь ошибки
идентичен:

- **(а) первая загрузка** — `BlocProvider(create: (_) => ChatsCubit()
  ..loadChats())` при открытии вкладки; `chats` в этот момент ещё пуст по
  умолчанию, так что «нет сообщений» после отказа не отличимо от честного
  «переписок правда нет».
- **(б) `refresh()` (pull-to-refresh или неявный вызов из `AuthToMain`)** —
  `refresh()` **сначала** сбрасывает `chats` в `[]` (`emit(state.copyWith(
  chats: const [], isError: false))`), и только потом вызывает `loadChats()`
  заново. Если пользователь уже видел непустой список чатов и в этот момент
  тянет экран вниз (или логинится, что триггерит тот же `refresh()` через
  `BlocListener` на `AuthToMain`), а повторный запрос тоже проваливается —
  ранее видимые чаты пользователя пропадают из состояния **до** того, как
  ошибка вообще случилась, и после отказа экран показывает тот же пустой
  `ChatsEmpty()`, что и путь (а) — пользователь не может отличить «сервер
  отказал» от «переписок больше нет».

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Маршрут `Routes.chats` (`lib/pages/routes.dart`) зарегистрирован с
`redirect: (context, state) { if (!AppCacheService.isAuthorized()) return
Routes.profile; return null; }` — гость на этот экран физически не попадает,
редиректится на `/profile` раньше, чем строится `ChatsView`/`ChatsCubit`. Сам
код этого сценария (`ChatsCubit`, `ChatsRepository`) не делает ни одной
дополнительной проверки авторизации внутри себя (`grep -rn "isAuthorized|
AuthRepository" lib/pages/chats/cubit/chats_cubit.dart
lib/repositories/chats/chats_repository.dart
lib/pages/chats/presentation/chats_view.dart` не находит ни одного
совпадения) — единственный гейт целиком на уровне `go_router`. Флаг,
проверяемый гейтом (`AppCacheService.isAuthorized()`, `lib/data/services/
app_cache_service.dart` — отдельный кэшированный булев `SharedPreferences`,
не то же самое обращение, что `AuthRepository.isAuthorized()` из
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), «Идентичность»), не
верифицирован этой спекой на предмет постоянной синхронизации с главным
токеном — см. «Открытые вопросы».

## CURRENT

### Основной поток

**Вход (а) — первая загрузка вкладки.**

1. Пользователь открывает вкладку «Сообщения» (`shellNavigatorMessagesKey`,
   `Routes.chats`) — редирект-guard пропускает (авторизован), `ChatsPage`
   рендерит `const ChatsView()`.
2. `ChatsView.build()`: `AppScaffold(... child: BlocProvider(create: (_) =>
   ChatsCubit()..loadChats(), child: BlocListener<AuthBloc, AuthState>(...
   child: BlocBuilder<ChatsCubit, ChatsState>(...))))`. `loadChats()`
   вызывается сразу внутри `create`, синхронно до первого `await` —
   `emit(state.copyWith(isLoading: true, isError: false))` (первая строка
   тела метода) успевает произойти до того, как `BlocBuilder` получит
   управление на построение первого кадра.
3. Внутри `try`: `final chats = await _repository.getChats();` —
   `ChatsRepository.getChats()` (`lib/repositories/chats/chats_repository.dart`)
   сам обёрнут в собственный `try/catch`: сначала грузит справочники
   (`BreedsRepository.getAll()`, `SuitsRepository.getAll()`,
   `KindsRepository.getAll()` — нужны только для `Chat.fromJson`), затем
   `rpcClient.call(ApiMessage(link: '${Constants.boardServiceApi}/chats',
   method: ApiMethod.get))`. В этом сценарии где-то на этом пути (сетевой
   отказ, не-2xx ответ, либо исключение при разборе JSON внутри
   `_parseChats`/`Chat.fromJson`) бросается исключение — логируется через
   `getIt<Talker>().error('getChats Error: $e')` (видно только в
   `Talker`-логе/DevTools, не в UI) и безусловно перебрасывается (`rethrow`).
4. Исключение всплывает из `await _repository.getChats()` без изменений,
   перехватывается `catch (e) { emit(state.copyWith(isLoading: false,
   isError: true)); }` — `copyWith` не упоминает `chats`, поле остаётся
   равным значению до вызова (для этого входа — дефолт `[]`, заданный
   конструктором `ChatsState()`).
5. `ChatsView`'s `BlocBuilder<ChatsCubit, ChatsState>` перестраивается:
   `if (state.isLoading) return CustomLottieLoader();` — ложно (`isLoading`
   только что стал `false` на шаге 4); единственная оставшаяся ветка —
   `RefreshIndicator(... child: state.chats.isEmpty ? const ChatsEmpty() :
   ChatsPopulated(...))`. `state.isError` не упоминается в этом методе
   вообще ни разу — при `chats.isEmpty == true` (шаг 4) выбирается
   `ChatsEmpty()` безусловно, независимо от того, `isError` истинен или
   ложен.
6. Пользователь видит `ChatsEmpty()` — иконка, `context.l10n.chats_empty_title`,
   `context.l10n.chats_empty_subtitle`, кнопка `context.l10n.chats_empty_button`
   (`context.go(Routes.board)`) — тот же экран, что и при честном отсутствии
   переписок. Никакого текста об ошибке, никакого `SnackBar`
   (`showAppSnackBarError` и подобные хелперы из `lib/widgets/app_snackbar.dart`
   этим сценарием не задействованы вовсе), никакого визуально отличимого
   признака отказа запроса.

**Вход (б) — `refresh()` после того, как список уже был непустым.**

7. Пользователь тянет список вниз (`RefreshIndicator.onRefresh: () =>
   context.read<ChatsCubit>().refresh()`), либо `BlocListener` реагирует на
   `AuthToMain` (успешный логин/восстановление сессии) вызовом того же
   `chatsCubit.refresh()` — оба пути ведут в один и тот же метод.
8. `ChatsCubit.refresh()`: `emit(state.copyWith(chats: const [], isError:
   false));` — список, который мог быть непустым секунду назад, уже стёрт
   из состояния **до** повторного запроса; затем `await loadChats();`
   выполняет тот же путь, что и шаги 2–4 выше.
9. Если этот повторный вызов `_repository.getChats()` тоже бросает —
   `catch` шага 4 срабатывает так же: `isError: true`, `isLoading: false`,
   `chats` остаётся тем, чем было **на момент входа в `try` этого конкретного
   вызова** — то есть уже `[]`, установленным шагом 8, а не тем непустым
   списком, что пользователь видел до жеста обновления.
10. `ChatsView` перестраивается тем же кодом шага 5 — `state.chats.isEmpty ==
    true` (список стёрт на шаге 8) → `ChatsEmpty()`. Пользователь, только что
    видевший свои переписки, теперь видит «нет сообщений» без какого-либо
    объяснения — данные на сервере при этом никуда не делись, пропало только
    их локальное отображение.

### Альтернативные потоки

- **`AuthLogout` во время отображения ошибки.** `BlocListener`'s ветка `if
  (state is AuthLogout) { chatsCubit.clear(); }` эмитит `const ChatsState()`
  целиком — сбрасывает и `isError`, и `chats`, и `isLoading` к дефолтам,
  независимо от того, в каком состоянии был экран. Не то же самое, что этот
  дефект (полный сброс, а не маскировка), упомянуто только для полноты
  картины по `BlocListener`.
- **Источник исключения не различается.** Ни `ChatsRepository.getChats()`,
  ни `ChatsCubit.loadChats()` не отличают сетевой отказ (таймаут,
  недоступность сервера, не-2xx ответ) от исключения при разборе ответа
  (`_parseChats`/`Chat.fromJson`, например при неожиданной форме `json['id']`
  или `json['chatMessages']`) — оба варианта проходят один и тот же
  `try/catch` в `ChatsRepository.getChats()`, затем один и тот же `catch` в
  `loadChats()`, с одинаковым итогом.
- **Гость не может воспроизвести этот путь напрямую.** Редирект-guard
  `Routes.chats` отправляет неавторизованного пользователя на `/profile`
  раньше, чем `ChatsCubit`/`ChatsView` вообще строятся — сценарий
  воспроизводим только для авторизованного пользователя, чей `AppCacheService.
  isAuthorized()` возвращает `true`.
- **Пустой ответ сервера — не этот сценарий.** Если `_repository.getChats()`
  успешно возвращает пустой список (`[]`), это обычный, корректно
  специфицированный путь `READ_OK` с реально пустым списком чатов — не
  предмет этого файла; отличить его от описанного здесь `READ_ERROR`
  невозможно на уровне `ChatsView`, только на уровне `ChatsCubit.state`,
  который UI не читает.

### Связанные сущности

- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — сущность, чьё чтение
  проваливается; модуль полностью online-only (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md),
  «Описание» — нет локального Drift-хранения чатов), поэтому при отказе нет
  вообще никакого локального кэша, который можно было бы показать вместо
  результата неудавшегося запроса — состояние экрана целиком равно тому, что
  было в памяти `ChatsCubit` до этого вызова.
- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) —
  вложен в каждый `Chat` через поле `messages` (`json['chatMessages']`),
  используется вычисляемым `Chat.lastMessage`/`Chat.lastMessageAt` для
  превью последнего сообщения в списке; не запрашивается отдельно этим
  сценарием и не участвует в самом отказе.
- `Breed`/`Suit`/`Kind` (HANDBOOKS) — читаются целиком внутри
  `ChatsRepository.getChats()` до сетевого вызова, только для разрешения
  названий внутри вложенного `Ad` (см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md));
  исключение при их чтении обрабатывается тем же catch-блоком, что и
  сетевой отказ, без различения источника.

### Бизнес-правила

- `ChatsState.isError` — поле, которое `ChatsCubit` корректно выставляет и
  сбрасывает (`loadChats`/`refresh`), но которое ни один виджет в дереве
  `ChatsView` не читает — то же наблюдение уже зафиксировано в
  [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md), «Эффект».
- `ChatsView` различает всего два состояния UI — «идёт загрузка»
  (`CustomLottieLoader`) и «список пуст или непуст» (`ChatsEmpty`/
  `ChatsPopulated`) — в отличие от трёхчастного разделения `BoardView` на
  общей ленте (`Loader`/`BoardEmpty`/`BoardPopulated`, где хотя бы есть
  осмысленный текст в пустом состоянии), здесь третьего, «ошибочного»
  представления не существует вовсе ни для одного из двух входов.
- `refresh()` активно ухудшает наблюдаемый результат по сравнению с простым
  первым `loadChats()`: он не просто не показывает ошибку, а **стирает уже
  показанные пользователю данные** ещё до попытки их перезагрузить — при
  отказе повторного запроса пользователь теряет из вида ранее видимый
  список чатов, хотя ни один чат на сервере не удалялся.
- Нет отдельной ветки `REJECTED` — код не способен отличить содержательный
  отказ сервера от технического сбоя ни на одном уровне (`ChatsRepository`,
  `ChatsCubit`), поэтому оба класса отказа документируются здесь одним
  `READ_ERROR`, как и в аналогичных сценариях `BOARD`
  ([UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md),
  [UC-150](UC-150-ACTOR-1-EVT-75-ENT-18-READ_ERROR-IN-BOARD.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий (отказ `ChatsRepository.getChats()` внутри
`ChatsCubit.loadChats()`, для обоих входов — первой загрузки и `refresh()`)
статически прослеживается в коде целиком и подтверждён проходящим тестом на
уровне кубита (см. «Связанные тесты»); отсутствие какого-либо теста на
уровне виджета (`ChatsView`) не блокирует существование самого дефекта —
факт, что `isError` нигде не читается в `build()`, подтверждён прямым чтением
файла и `grep`, а не только тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/chats/presentation/chats_view.dart` | `ChatsView.build` | CURRENT | предмет дефекта — читает только `state.isLoading`/`state.chats.isEmpty`, ни разу не упоминает `state.isError` |
| `lib/pages/chats/presentation/chats_empty.dart` | `ChatsEmpty` | CURRENT | рендерится при `chats.isEmpty`, независимо от `isError` — идентичный вид для «правда пусто» и «отказ запроса» |
| `lib/pages/chats/presentation/chats_populated.dart` | `ChatsPopulated` | CURRENT | не участвует в этом сценарии напрямую (список пуст в обоих входах на момент отказа), упомянут для полноты ветвления |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.loadChats` | CURRENT | корректно выставляет `isError: true, isLoading: false` при исключении; не трогает `chats` в `catch`-ветке |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.refresh` | CURRENT | сбрасывает `chats` в `[]` **до** повторного `loadChats()` — источник входа (б) |
| `lib/pages/chats/cubit/chats_cubit.dart` | `ChatsCubit.clear` | CURRENT | вызывается из `BlocListener` на `AuthLogout`; полный сброс состояния, включая `isError` |
| `lib/pages/chats/cubit/chats_state.dart` | `ChatsState.isError` | CURRENT | поле существует, корректно управляется кубитом, не читается ни одним виджетом `chats/` |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.getChats` | CURRENT | источник исключения; собственный `try/catch`, логирует через `Talker`, `rethrow`; не различает сетевой отказ и ошибку разбора ответа |
| `lib/pages/chats/presentation/chats_page.dart` | `ChatsPage` | CURRENT | тонкая обёртка, напрямую рендерит `ChatsView()` |
| `lib/pages/routes.dart` | `Routes.chats` (`redirect` на `!AppCacheService.isAuthorized()`) | CURRENT | единственный auth-гейт на этом пути; сам `ChatsCubit`/`ChatsRepository` авторизацию не проверяют |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized` | CURRENT | кэшированный булев флаг, использованный гейтом маршрута — отдельный от `AuthRepository.isAuthorized()` источник истины |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthLogout`, `AuthToMain` | CURRENT | состояния, на которые реагирует `BlocListener` в `ChatsView` — `clear()`/`refresh()` соответственно |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT (не используется этим сценарием) | существующий проектный канал сообщения об ошибке, не задействованный здесь |

## Критерии приёмки

- Если `ChatsRepository.getChats()` бросает исключение внутри
  `ChatsCubit.loadChats()` (вызванного либо напрямую при первом построении
  экрана, либо через `refresh()`), состояние получает `isError == true`,
  `isLoading == false`; `chats` остаётся равным значению, которое было в
  состоянии непосредственно перед этим вызовом `loadChats()`.
- Для входа (а) (первая загрузка) это значение — `[]` по умолчанию; для
  входа (б) (`refresh()`) это тоже `[]`, поскольку `refresh()` сбрасывает
  `chats` в `[]` раньше, чем повторно вызывает `loadChats()` — независимо от
  того, был ли список непустым непосредственно перед жестом обновления.
- `ChatsView.build()` не читает `state.isError` ни в одном условии — при
  `isLoading == false` и `chats.isEmpty == true` он рендерит `ChatsEmpty()`
  вне зависимости от значения `isError`, делая отказ запроса визуально
  неотличимым от реального отсутствия переписок.
- `RefreshIndicator` и жест pull-to-refresh остаются доступны на экране
  `ChatsEmpty()` после отказа — повторный вызов `refresh()` доступен
  пользователю, хоть и без какой-либо подсказки, что предыдущая попытка
  провалилась.

## Связанные тесты

`test/pages/chats_cubit_test.dart`, group `'UC-154 — ChatsCubit.loadChats
ERROR'` (старая нумерация, будет переименована в `UC-154` отдельным
контролируемым проходом, не трогать сейчас):

- `'ошибка -> isError:true, isLoading:false, chats не тронут'` — прямое
  подтверждение кода кубита из этого сценария: мокает
  `chatsRepository.getChats()` через `thenThrow(Exception('network
  error'))`, вызывает `cubit.loadChats()`, проверяет `cubit.state.isError ==
  true`, `cubit.state.isLoading == false`, `cubit.state.chats` пуст.

**TBD — теста нет** на уровне виджета `ChatsView`: ни один тест не строит
`ChatsView`/`BlocBuilder` с `ChatsState(isError: true)` и не проверяет, что
рендерится именно `ChatsEmpty()` без какого-либо текста об ошибке —
подтверждено только чтением `chats_view.dart` и `grep -rn "isError"
lib/pages/chats/`, не тестом.

**TBD — теста нет** на связку «`refresh()` после того, как `chats` уже был
непустым, и повторный `loadChats()` внутри него тоже проваливается» —
существующая group `'ChatsCubit.refresh'` в том же файле покрывает только
успешный повторный запрос (`getChats()` отвечает списком), не случай, когда
и исходный список был непустым, и повторный запрос тоже бросает исключение.

## Открытые вопросы и ограничения

- **`isError` — корректно управляемое, но полностью мёртвое для UI поле.**
  Ни `loadChats()`, ни `refresh()`, ни `clear()` не допускают ошибки в
  собственной логике управления флагом — единственный пробел строго на
  стороне `ChatsView.build()`, который его не читает. Является ли это
  осознанным упрощением (например, ожидание, что список чатов почти никогда
  не проваливается на практике) или недосмотром — ничем в коде/комментариях
  не зафиксировано.
- **`refresh()` активно теряет уже отображённые данные при повторном
  отказе.** Комбинация «сбросить список перед повторным запросом» +
  «не показывать ошибку» — то же по существу наблюдение, что уже
  зафиксировано для похожих сценариев `BOARD`
  ([UC-150](UC-150-ACTOR-1-EVT-75-ENT-18-READ_ERROR-IN-BOARD.md), где
  `refresh()` вдобавок ещё и подменяет источник данных) — здесь `refresh()`
  как минимум не подменяет источник (тот же `getChats()` вызывается
  повторно), но эффект для пользователя аналогичен: видимые данные исчезают
  без объяснения.
- **`AppCacheService.isAuthorized()` как источник guard'а маршрута** —
  отдельный кэшированный флаг от `AuthRepository.isAuthorized()`
  ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), «Идентичность»); эта спека
  не проверяла эмпирически, гарантированно ли эти два флага всегда
  синхронизированы (например, сразу после логаута или удаления аккаунта) —
  за пределами этого файла, поскольку не влияет на сам дефект `isError`.
- **Не проверено эмпирически против реального бэкенда.** Вывод сделан
  статическим чтением кода (`ChatsCubit.loadChats`/`refresh` →
  `ChatsRepository.getChats` → `ChatsView.build`) и подтверждён проходящим
  модульным тестом на уровне кубита с замоканным `ChatsRepository` — точная
  форма реальных сетевых сбоев (таймаут, DNS, не-2xx ответ, неожиданная
  форма JSON) этой спекой не воспроизведена, только универсальное
  `Exception`.
