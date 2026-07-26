# UC-145 — Пользователь открывает детальную карточку объявления (из ленты/«Моих»/«Избранного» или из шапки переписки)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Один и тот же экран (`BoardAdDetailPage`/`BoardAdDetailView`, подкреплённый
`AdDetailCubit(model)..viewAd()`) равнозначно открывается из четырёх мест,
все конструирующие один и тот же `BoardAdDetailPageArguments(ad:
ad.toDetailModel())`:

- тап по карточке в ленте (`BoardPage`), в «Моих объявлениях» (`MyAdsPage`)
  и в «Избранном» (`FavouriteAdsPage`) — все три экрана рендерят один и тот
  же переиспользуемый виджет `BoardPopulated`
  (`lib/pages/board/presentation/widgets/board_populated.dart`), чей
  `GestureDetector.onTap` — единственное место в коде, откуда стартует этот
  переход (`grep -rn "BoardAdDetailPageArguments"` находит ровно два места
  использования во всём `lib/`);
- тап по шапке переписки (`_MessagesHeaderTitle` в
  `lib/pages/messages/presentation/messages_view.dart`), доступный только
  если `chat.ad != null` (см. «Альтернативные потоки»).

Первые три ведут на маршрут `Routes.boardAdDetail` (дочерний узел
`Routes.board` внутри вкладки «Доска», без собственного
`parentNavigatorKey` — страница остаётся в навигаторе вкладки, нижний
navbar виден); четвёртый — на `Routes.messagesBoardAdDetail` (дочерний узел
`Routes.messages`, с явным `parentNavigatorKey: rootNavigatorKey` — во весь
экран, без нижнего navbar). Оба узла роутера строят один и тот же `const
BoardAdDetailPage()`. Открытие экрана автоматически, без отдельного
действия пользователя, вызывает `AdDetailCubit.viewAd()` →
`AdRepository.viewAd` (`POST /ads/{id}/view`) — инкремент `viewsCount` на
сервере.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Ни `BoardAdDetailPage`, ни
`AdDetailCubit`, ни `AdRepository.viewAd` нигде не обращаются к
`AuthRepository`/`AppCacheService.isAuthorized()`
(`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/board_ad_detail/` и по `lib/repositories/board/ad_repository.dart`
не находит ни одного совпадения). `BoardAdDetailModel.isMe` (`ownerId ==
AppCacheService.getUserId()`) — единственная связанная с личностью
пользователя проверка на этом экране, и для гостя (`getUserId()` возвращает
`null` при отсутствии сохранённого пользователя в Hive) она всегда `false`,
поскольку `ownerId` — целое число по умолчанию `0`, никогда не равное
`null`; следствия см. «Альтернативные потоки».

## CURRENT

### Основной поток

1. **Вход A — тап по карточке в ленте/«Моих»/«Избранном».**
   `BoardPopulated.build`'s `GestureDetector.onTap`:
   `context.pushNamed2(Routes.boardAdDetail, extra:
   BoardAdDetailPageArguments(ad: ad.toDetailModel()))` — `ad` берётся из
   уже загруженного в память списка объявлений (`BoardCubit`/`MyAdsCubit`/
   `FavouriteAdsCubit`, за пределами этого файла), сам этот экран не делает
   отдельного запроса за карточкой.
2. **Вход B — тап по шапке переписки.** `_MessagesHeaderTitle.build`
   (`lib/pages/messages/presentation/messages_view.dart`):
   `onTap: ad == null ? null : () => context.pushNamed2(
   Routes.messagesBoardAdDetail, extra: BoardAdDetailPageArguments(ad:
   ad.toDetailModel()))`, где `ad = chat.ad` — вложенный объект объявления
   ([ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md), поле может отсутствовать
   в ответе списка чатов).
3. `GoRouterExtension.pushNamed2` (`lib/widgets/go_router/go_router_helper.dart`)
   оборачивает переданный `extra` в `{name: extra}` перед вызовом
   `pushNamed` — то есть `extra` конечного `GoRouterState` всегда
   `Map<String, dynamic>`, ключ — имя маршрута, с которого сделан переход.
4. `BoardAdDetailPage.build`: `GoRouterState.of(context)
   .tryGetExtraByName<BoardAdDetailPageArguments>(Routes.boardAdDetail)?.ad
   ?? GoRouterState.of(context)
   .getExtraByName<BoardAdDetailPageArguments>(Routes.messagesBoardAdDetail).ad`
   — пробует ключ входа A первым; для входа B (где ключ `boardAdDetail`
   в `extra`-карте отсутствует вовсе) `tryGetExtraByName` возвращает `null`,
   и выражение переходит ко второму, безусловному `getExtraByName` по ключу
   входа B. Строит `BoardAdDetailView(model: ad)`.
5. `BoardAdDetailView.build`: `BlocProvider(create: (_) =>
   AdDetailCubit(model)..viewAd())` — `viewAd()` вызывается синхронно сразу
   при создании Cubit'а, не отдельным действием пользователя и не по
   какому-либо условию.
6. `AdDetailCubit.viewAd()`: `await _adRepository.viewAd(state.ad.adId)`,
   без `try`/`catch` вокруг `await`; при успехе — `emit(state.copyWith(ad:
   state.ad.copyWith(viewsCount: state.ad.viewsCount + 1)))`.
7. `AdRepository.viewAd(id)`: `ApiMessage(link:
   '${Constants.boardServiceApi}/ads/$id/view', method: ApiMethod.post)` →
   `rpcClient.call(message)`; `response['status'] == '1'` → `return` (тело
   ответа больше никак не используется); иначе — `throw
   Exception(response['message'])`, `rethrow` из внешнего `catch` (после
   `getIt<Talker>().error(...)`) — попадает в `AdDetailCubit.viewAd()` без
   перехвата, см. «Альтернативные потоки».
8. Параллельно с шагом 5 (тот же `build`) строится `AppScaffold`:
   `AppBarSettings` с `title: Text('Объявление', ...)` — строка жёстко
   закодирована по-русски, не через `AppLocalizations`/`context.tr`;
   `actions` содержит два виджета кнопок избранного/шейра, оба целиком
   закомментированы в исходном коде, и один `SizedBox(width: 8)` —
   фактически видимых действий в AppBar нет. Тело —
   `BoardAdDetailPopulated(ad: model)`, где `model` — тот же аргумент,
   переданный в `BoardAdDetailView` (шаг 4), **не** `state.ad` из
   `AdDetailCubit`: во всём файле `board_ad_detail_view.dart` нет ни одного
   `BlocBuilder`/`context.watch<AdDetailCubit>()` — единственное место кода,
   которое стало бы читать `state.ad`, это те же закомментированные кнопки
   (`model.isFavourite`, `context.read<AdDetailCubit>().toggleAdFavourite`).
   Следствие — инкремент `viewsCount` на шаге 6, хотя и вычислен корректно
   (в отличие от бага `Ad.props`, `BoardAdDetailModel` — полноценный
   freezed-класс), нигде не отображается на этом самом экране (см. «Открытые
   вопросы»).
9. `BoardAdDetailPopulated.build` рендерит по данным `model` (не
   перечитывается после шага 6): фотоленту (`_BoardAdImageStrip`, если
   `animalSpecs.length <= 1`) либо сетку карточек животных
   (`_BoardAdAnimalsGrid`, если `animalSpecs.length > 1`, с возможностью
   выбрать одно животное и перейти в `_SelectedAnimalHeader` — кнопка
   возврата к сетке подписана жёстко закодированной строкой `'Все
   животные'`, не через l10n); цену (`priceLabel`, только если выбранное
   животное не задано — `selectedAnimal == null`) и счётчик просмотров
   (`hasViews = ad.viewsCount > 0`, сам счётчик нигде не выводится текстом —
   единственный связанный с ним UI-блок закомментирован, см. `if (false)
   ...` в коде); заголовок, адрес; блок контактов (аватар-инициал, имя
   владельца, кнопка звонка `if (ad.showPhoneButton)` — запускает
   `launchUrl('tel:${ad.phone}')`, кнопка чата `if (ad.showChatButton &&
   !ad.isMe)` — открывает `_openChat`); карточку характеристик животного
   (`_AnimalSpecCard`, если есть хотя бы одно из чипа/породы/даты
   рождения/масти/пола); описание; и, для объявлений о находке
   (`whenWasFoundText` непуст), блок с жёстко закодированным заголовком
   `'Когда нашлось:'`.
10. Кнопка чата (`showChatButton && !ad.isMe` — поскольку
    `showChatButton` в `toDetailModel()` всегда `true`, условие фактически
    сводится к `!ad.isMe`) вызывает `_openChat(context)`:
    строит `Chat(id: null, peerName: ad.ownerName, adId: ad.adId, adTitle:
    ad.title, adPrice: ad.priceLabel, unreadCount: 0, messages: [],
    userToId: ad.ownerId, userFromId: AppCacheService.getUserId()!)` —
    **безусловный** `!` на потенциально `null`-значении, и лишь затем
    `context.go('${Routes.chats}/${Routes.messages}', extra: {
    Routes.messages: MessagesPageArgs(chat: chat) })`. Само создание/отправка
    сообщения — отдельное событие
    ([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)), за пределами
    этого файла; см. «Альтернативные потоки» о том, кто реально может
    нажать эту кнопку.

### Альтернативные потоки

- **Вход B недоступен, если `chat.ad == null`.** Список чатов
  ([ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)) может не содержать
  вложенный объект объявления — в этом случае `onTap` шапки переписки
  буквально `null`, тап по области визуально ничего не делает; этот путь
  открытия для конкретной переписки недостижим, пока `Chat.ad` не окажется
  заполнен (например, после того как этот же чат был открыт хотя бы раз с
  карточки объявления, где `ad` передаётся явно).
- **Кнопка чата видна и гостю.** `!ad.isMe` истинно для любого
  `ownerId`, не совпадающего с текущим `AppCacheService.getUserId()`, а для
  гостя `getUserId()` — всегда `null` (см. «Пользователь»), так что кнопка
  чата отображается наравне с авторизованным пользователем — сам этот экран
  не делает различия между [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (к
  которому принадлежит и гость) и [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)
  (строго авторизованный, единственный актор чата/мутаций объявления по
  [MOD-5](../modules/MOD-5-BOARD.md)). Нажатие гостем приводит к немедленному
  падению на `AppCacheService.getUserId()!` внутри `_openChat` — до
  какой-либо навигации и до срабатывания `redirect`-guard'а `Routes.chats`
  (`!AppCacheService.isAuthorized() -> Routes.profile`), поскольку
  форс-анврап выполняется раньше `context.go(...)`. Это дефект действия
  «открыть чат» ([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)-ветка
  инициации, не самого просмотра карточки), но кнопка, ведущая к нему,
  видна именно на этом экране — фиксируется здесь как код-ридинг находка, не
  разбирается глубже (см. «Открытые вопросы»).
- **`viewAd()` бросает исключение** (сеть/сервер) — не перехватывается ни в
  `AdDetailCubit`, ни выше по стеку вызова (`BlocProvider.create` не
  оборачивает `..viewAd()` в обработку ошибок); отдельный результат
  (`READ_ERROR`), за пределами этого файла.
- **Владелец открывает собственное объявление** (`ad.isMe == true`) —
  кнопка чата не рендерится вовсе (`!ad.isMe` ложно); кнопка звонка
  продолжает отображаться независимо от `isMe` (условие только
  `showPhoneButton`).
- **Несколько животных в объявлении** (`animalSpecs.length > 1`) — вместо
  фотоленты показывается сетка карточек (`_BoardAdAnimalsGrid`); тап по
  карточке переключает на `_SelectedAnimalHeader` для одного животного,
  сбрасывающийся обратно на сетку по кнопке `'Все животные'`; цена самого
  объявления (`hasPrice`) скрывается, пока выбрано конкретное животное
  (`selectedAnimal == null` — часть условия `hasPrice`).
- **Повторное открытие той же карточки** (например, `context.pop()` назад
  в ленту и повторный тап) — `context.pushNamed2` создаёт новый экземпляр
  маршрута/страницы, новый `AdDetailCubit`, и `viewAd()` вызывается заново —
  сервер получает ещё один инкремент `viewsCount` за то же объявление в той
  же пользовательской сессии; никакой дедупликации «уже просмотрено в этом
  сеансе» на клиенте нет.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чей просмотр
  специфицирует этот сценарий: сам объект приходит на экран уже загруженным
  (лентой/«Моими»/«Избранным»/списком чатов), этот сценарий не делает
  повторного `GET`-запроса за карточкой; единственный сетевой вызов —
  `POST /ads/{id}/view`, инкрементирующий `viewsCount` на сервере.
  Локальный `AdDetailState.ad.viewsCount` тоже инкрементируется корректно
  (freezed, без бага `Ad.props`), но, в отличие от утверждения в
  [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md) (которое отмечает
  только то, что инкремент не попадает обратно в ленту), на **этом самом
  экране** это тоже не имеет видимого эффекта — тело строится из аргумента
  `model`, а не из состояния Cubit'а (шаг 8 выше).
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — не читается и не
  изменяется этим сценарием напрямую; кнопка чата на этом экране лишь
  конструирует новый локальный `Chat(id: null, ...)` и передаёт его дальше
  по навигации — фактическое создание чата происходит только при первой
  отправке сообщения ([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)),
  за пределами этого файла. Для входа B этот же экран, наоборот, получает
  `ad` уже вложенным в `Chat.ad`, если он был загружен ранее.
- [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage) — не
  затрагивается этим сценарием ни на одном шаге.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  не читается этим сценарием: `Country.boardEnabled` гейтит только
  видимость вкладки «Доска» в navbar
  ([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md),
  `BoardChatAvailabilityCubit`), не сам маршрут `Routes.boardAdDetail`/
  `Routes.messagesBoardAdDetail` — если экран уже открыт (например, по
  прямой навигации через шапку переписки, вход B, доступный из отдельной
  вкладки «Сообщения»), доступность страны повторно не проверяется.

### Бизнес-правила

- `viewAd()` вызывается ровно один раз на каждое монтирование этого экрана,
  безусловно, независимо от статуса авторизации и от того, каким из двух
  входов (A/B) пользователь сюда попал.
- Инкремент `viewsCount` на сервере не зависит от того, что при этом
  происходит на клиенте — `AdRepository.viewAd` не возвращает и не
  использует обновлённое значение счётчика, полагается только на
  `status == '1'`.
- Локальный инкремент `state.ad.viewsCount` в `AdDetailCubit` вычислен
  корректно (не страдает багом `Ad.props`, поскольку `BoardAdDetailModel` —
  независимый freezed-DTO этого экрана, не сам `Ad`), но не имеет видимого
  эффекта нигде на этом экране — тело экрана не подписано на состояние
  Cubit'а.
- Кнопка чата скрыта тогда и только тогда, когда `ad.isMe == true`
  (`ownerId == AppCacheService.getUserId()`); для гостя это условие всегда
  ложно, то есть кнопка чата видна гостю наравне с авторизованным
  пользователем.
- Кнопка звонка видна тогда и только тогда, когда `ad.phone` непуст —
  независимо от `isMe`/статуса авторизации.
- Заголовок AppBar (`'Объявление'`), подпись кнопки возврата к сетке
  животных (`'Все животные'`) и заголовок блока находки (`'Когда нашлось:'`)
  — жёстко закодированные русские строки, не проходящие через
  `AppLocalizations`/`context.tr`.
- Кнопки избранного и «поделиться» в AppBar этого экрана полностью
  закомментированы в исходном коде — `AdDetailCubit.toggleAdFavourite`
  существует в том же классе, что и `viewAd`, но ни один виджет этого
  экрана его не вызывает (переключение избранного для объявления в
  списках делается другим методом, `BoardCubit.toggleAdFavourite`, с
  карточки в ленте/«Моих»/«Избранном» — отдельный сценарий,
  [UC-141](UC-141-ACTOR-1-EVT-71-ENT-18-UPDATE_OK-IN-BOARD.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба входа (A и B) полностью реализованы и достижимы из UI; находки,
перечисленные в «Открытые вопросы и ограничения» (инертный локальный
инкремент счётчика, кнопка чата, доступная гостю и падающая при нажатии,
хардкод русских строк, отсутствие повторной проверки доступности по
стране), не блокируют выполнение основного сценария просмотра карточки.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated.build` (`GestureDetector.onTap`) | CURRENT | вход A — общий для ленты, «Моих» и «Избранного» виджет |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView.build` (`BoardPopulated`) | CURRENT | второе место переиспользования входа A |
| `lib/pages/favourite_ads/presentation/favourite_ads_view.dart` | `FavouriteAdsView.build` (`BoardPopulated`) | CURRENT | третье место переиспользования входа A |
| `lib/pages/messages/presentation/messages_view.dart` | `_MessagesHeaderTitle.build` (`onTap`) | CURRENT | вход B — тап по шапке переписки, только при `chat.ad != null` |
| `lib/pages/routes.dart` | `Routes.boardAdDetail`, `Routes.messagesBoardAdDetail` | CURRENT | два независимых узла роутера с общим `builder`; только второй задаёт `parentNavigatorKey: rootNavigatorKey` |
| `lib/widgets/go_router/go_router_helper.dart` | `GoRouterExtension.pushNamed2` | CURRENT | оборачивает `extra` в `{name: extra}` при переходе |
| `lib/widgets/go_router/go_router_state.dart` | `GoRouterStateExtension.tryGetExtraByName`, `.getExtraByName` | CURRENT | чтение `extra` по имени маршрута, откуда пришёл переход |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_page.dart` | `BoardAdDetailPage.build`, `BoardAdDetailPageArguments` | CURRENT | резолв аргумента для обоих входов в общий `model` |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | `BoardAdDetailView.build` (`BlocProvider.create`) | CURRENT | создаёт `AdDetailCubit(model)..viewAd()` автоматически; тело строится из `model`, не из `BlocBuilder` |
| `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` | `AdDetailCubit.viewAd`, `.toggleAdFavourite` | CURRENT | предмет этого файла — `viewAd`; `toggleAdFavourite` — мёртвый код на этом экране |
| `lib/pages/board_ad_detail/cubit/ad_detail_state.dart` | `AdDetailState` | CURRENT | freezed-состояние; обновляется корректно, но не читается ни одним виджетом этого экрана |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.viewAd` | CURRENT | `POST /ads/{id}/view`, без перехвата исключения внутри `AdDetailCubit` |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel`, `BoardAdDetailModelMapper.toDetailModel`, `.isMe` | CURRENT | DTO экрана; `isMe = ownerId == AppCacheService.getUserId()` |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `BoardAdDetailPopulated.build`, `_openChat` | CURRENT | рендер фотоленты/сетки животных, цены, адреса, кнопок звонка/чата; хардкод русских строк |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getUserId` | CURRENT | `null` для гостя — используется и в `isMe`, и (без проверки на `null`) в `_openChat` |
| `lib/models/chat/chat.dart` | `Chat` | CURRENT | конструируется локально в `_openChat`, `id: null` до создания на сервере |
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit.load` | CURRENT | гейтит только видимость вкладки «Доска» в navbar, не сам маршрут этого экрана |

## Критерии приёмки

- Открытие экрана через любой из четырёх путей (лента, «Мои», «Избранное»,
  шапка переписки при непустом `chat.ad`) приводит ровно к одному вызову
  `AdRepository.viewAd(ad.id)`, выполненному автоматически при создании
  `AdDetailCubit`, без отдельного действия пользователя.
- `viewAd()` отправляет `POST` на `${Constants.boardServiceApi}/ads/{id}/view`
  и при `status == '1'` не бросает исключение.
- При успехе `AdDetailState.ad.viewsCount` в самом Cubit'е увеличивается
  ровно на 1 относительно значения, с которым Cubit был создан.
- Тело экрана (`BoardAdDetailPopulated`) строится из аргумента,
  переданного при создании `BoardAdDetailView`, и не перестраивается по
  изменению состояния `AdDetailCubit` — обновлённый `viewsCount` из
  предыдущего пункта не отображается нигде на этом экране.
- Кнопка чата видна тогда и только тогда, когда `ad.isMe == false` —
  включая случай гостя, для которого `isMe` всегда `false`.
- Кнопка звонка видна тогда и только тогда, когда `ad.phone` непусто.
- Вход B (`_MessagesHeaderTitle`) не выполняет переход и не создаёт
  `AdDetailCubit`, если `chat.ad == null`.

## Связанные тесты

`test/pages/ad_detail_cubit_test.dart`:

- group `'UC-145 — AdDetailCubit.viewAd'` (старая нумерация, будет
  переименована в `UC-145` отдельным контролируемым проходом, не трогать
  сейчас) — 1 тест: `'успех -> viewsCount локально увеличивается
  корректно'` — создаёт `AdDetailCubit(BoardAdDetailModel(adId: 9,
  viewsCount: 3))`, мокает `adRepository.viewAd(9)` успехом, после
  `cubit.viewAd()` проверяет `cubit.state.ad.viewsCount == 4`.

`test/repositories/ad_repository_test.dart`:

- group `'UC-145 — AdRepository.viewAd'` (та же старая нумерация) — 1
  тест: `'успех -> POST /ads/{id}/view'` — мокает `farmRpcClient.call`
  ответом `{'status': '1'}`, вызывает `repository.viewAd(7)`, проверяет
  захваченное сообщение: `message.method == ApiMethod.post`,
  `message.link` содержит `/ads/7/view`.

Группы `'UC-146 — AdDetailCubit.viewAd ERROR (известный дефект — без
try/catch)'` (тот же файл, `ad_detail_cubit_test.dart`) и `'UC-146 —
AdRepository.viewAd ERROR'` (тот же файл, `ad_repository_test.dart`)
покрывают ветку исключения — отдельный результат (`READ_ERROR`), не входят
в этот use-case.

**TBD — теста нет** на сам факт четырёх равнозначных входов на уровне
навигации (`BoardPopulated.onTap` из трёх разных экранов,
`_MessagesHeaderTitle.onTap`) — существующие тесты вызывают
`AdDetailCubit.viewAd()`/`AdRepository.viewAd()` напрямую, не через переход
по маршруту.

**TBD — теста нет** на то, что `BoardAdDetailPopulated`/`BoardAdDetailView`
не перечитывают `AdDetailState` после `viewAd()` — ни один тест не
проверяет виджет-уровень этого экрана.

**TBD — теста нет** на условие видимости кнопки чата (`showChatButton &&
!ad.isMe`), на кнопку звонка (`showPhoneButton`) и на падение
`AppCacheService.getUserId()!` в `_openChat` для гостя.

**TBD — теста нет** на `_MessagesHeaderTitle.onTap == null` при `chat.ad ==
null`.

## Открытые вопросы и ограничения

- **Инкремент `viewsCount` не имеет видимого эффекта на этом самом
  экране.** `BoardAdDetailPopulated` строится из `model` — аргумента,
  захваченного до создания `AdDetailCubit`, а не из `state.ad` через
  `BlocBuilder`/`context.watch`. Даже без бага `Ad.props`
  ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), который объясняет, почему
  инкремент не долетает до ленты, обновлённое значение счётчика не
  отображается вообще нигде — единственная причина, по которой это
  незаметно, в том, что счётчик просмотров и сам по себе нигде текстом не
  выводится на этом экране (`hasViews` вычисляется, но связанный блок
  закомментирован). Не воспроизведено тестом, не разбирается глубже.
- **Кнопка чата видна гостю и падает при нажатии.** `!ad.isMe` — гость
  никогда не «владелец» объявления (`getUserId() == null`, `ownerId` — не
  `null`), поэтому видит кнопку чата наравне с авторизованным
  пользователем. Нажатие вызывает `_openChat`, где `AppCacheService
  .getUserId()!` разыменовывается безусловно и раньше любой навигации/
  `redirect`-guard'а `Routes.chats` — для гостя это `Null check operator
  used on a null value`. Дефект относится к действию «открыть чат»
  ([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)-инициации), но
  кнопка, ведущая к нему, — часть рендера именно этого экрана. Не
  воспроизведено тестом, не разбирается глубже в рамках этого файла.
- **Три жёстко закодированных русских строки.** Заголовок AppBar
  (`'Объявление'`, `board_ad_detail_view.dart`), подпись кнопки возврата к
  сетке животных (`'Все животные'`) и заголовок блока «когда нашлось»
  (`'Когда нашлось:'`, оба — `board_ad_detail_populated.dart`) не проходят
  через `AppLocalizations`/`context.tr` — единственный текст экрана,
  видимый пользователю без учёта выбранного языка приложения.
- **Нет повторной проверки доступности раздела по стране.** `Country
  .boardEnabled` ([ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md))
  гейтит только видимость вкладки «Доска» в navbar
  ([EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)), не
  сам маршрут этого экрана — вход B (шапка переписки) достижим из отдельной
  вкладки «Сообщения» независимо от текущего состояния
  `BoardChatAvailabilityCubit`. Не воспроизведено как конкретный кейс, не
  разбирается глубже.
- **Повторное открытие одной и той же карточки увеличивает `viewsCount`
  без ограничений.** Нет ни клиентской дедупликации «уже просмотрено в этом
  сеансе», ни какого-либо троттлинга — каждое монтирование этого экрана для
  того же объявления (в том числе повторное, после `context.pop()` назад и
  нового тапа) отправляет ещё один `POST /ads/{id}/view`. Не
  разбирается глубже.
