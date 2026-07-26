# UC-159 — Пользователь звонит по номеру объявления — с детальной карточки или из шапки переписки

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Два равнозначных, независимо проверенных чтением кода входа приводят к
одному и тому же действию — открыть системный диалер с номером телефона
объявления:

- **(а) иконка телефона на детальной карточке объявления**
  (`BoardAdDetailPopulated`, видна при `ad.showPhoneButton`, что означает
  `ad.phone != null && ad.phone!.isNotEmpty` — вычислено один раз в
  `BoardAdDetailModelMapper.toDetailModel()`; тап работает только при
  `contactActionsEnabled == true`, единственное место, где это не так, —
  превью визарда создания объявления, `BoardAdPreviewStepPage`);
- **(б) пункт «Позвонить» в выпадающем меню шапки переписки**
  (`_MessagesHeaderMenu` в `MessagesView`, читает `chat.ad?.phone`).

Оба сайта читают только уже загруженный на клиенте телефон объявления
([ENT-18](../entities/ENT-18-AD-IN-BOARD.md), сгенерированный сервером
generic-атрибут `attribute_id == 9`) и не изменяют ни одну его запись —
отсюда `READ_OK`, а не мутация. Оба сайта также независимо друг от друга
воспроизводят один и тот же паттерн: `launchUrl(Uri.parse('tel:$phone'))`
**без** `await`, **без** `canLaunchUrl`, **без** `try`/`catch` — не общий
хелпер, а два отдельных инлайн-вызова (подтверждено: `grep -rn "launchUrl"
lib/` не находит ни одной обёртки/сервиса для телефонных звонков во всём
`lib/`). Ни отказ диалера открыться, ни успех этого открытия никак не
наблюдаются кодом — см. «Открытые вопросы».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Ни `BoardAdDetailPopulated`,
ни `_MessagesHeaderMenu`, ни `MessagesCubit` не проверяют статус
авторизации на этом пути (`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` и
`lib/pages/messages/presentation/messages_view.dart` не находит ни одного
совпадения) — то же самое чтение, что уже доступно гостю на детальной
карточке ([EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md)).

## CURRENT

### Основной поток

**Вход А — иконка телефона на детальной карточке.**

1. Экран детальной карточки (`BoardAdDetailPage`) монтируется по одному из
   двух маршрутов, оба резолвятся в один и тот же `BoardAdDetailView(model:
   ad)`: `Routes.boardAdDetail` (тап по карточке в ленте/«Моих»/«Избранном»,
   [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md)) или
   `Routes.messagesBoardAdDetail` (тап по заголовку шапки переписки,
   `_MessagesHeaderTitle.onTap` в `messages_view.dart`) —
   `BoardAdDetailPage.build` читает `extra` по имени того маршрута, который
   реально сработал.
2. `BoardAdDetailView.build` оборачивает в `BlocProvider(create: (_) =>
   AdDetailCubit(model)..viewAd())` и рендерит `BoardAdDetailPopulated(ad:
   model)` — позиционный параметр `contactActionsEnabled` не передан,
   остаётся дефолтным `true`.
3. `_BoardAdDetailPopulatedState.build`: контейнер-кнопка звонка
   отображается только при `ad.showPhoneButton` (вычислено в
   `BoardAdDetailModelMapper.toDetailModel()` как `phone != null &&
   phone!.isNotEmpty`) — если у объявления нет телефона, иконки нет вовсе,
   этот сценарий не наступает.
4. Пользователь нажимает иконку. `onPressed: widget.contactActionsEnabled ?
   () { if (ad.phone != null) { launchUrl(Uri.parse('tel:${ad.phone!}')); }
   } : null` — при `contactActionsEnabled == true` (весь живой экран
   детальной карточки, оба маршрута шага 1) колбэк выполняется; внутренняя
   проверка `ad.phone != null` уже гарантирована шагом 3 (`showPhoneButton`
   требует ещё и непустую строку) и на практике всегда истинна здесь.
5. `launchUrl(Uri.parse('tel:${ad.phone!}'))` (`package:url_launcher/url_launcher.dart`)
   вызывается без `await` — возвращаемый `Future<bool>` отброшен, результат
   (успех/отказ) нигде не читается. Обработчика ошибок (`.catchError`,
   `try`/`catch`) вокруг вызова нет ни на этой, ни на объемлющих строках.
6. Состояние экрана (`AdDetailState`, `BoardAdDetailModel`) не меняется ни
   одним полем; ни индикатор загрузки, ни snackbar не показываются — весь
   эффект полностью вне приложения (открытие системного диалера с
   предзаполненным номером, если диалер есть).

**Вход Б — пункт «Позвонить» в шапке переписки.**

7. `MessagesView` монтирует `_MessagesHeaderMenu(chat: chat)` в `actions`
   `AppBar`'а — доступен на экране переписки, куда можно попасть либо со
   списка чатов (`ChatsPopulated.onChatTap` → `Routes.messages`, `chat.id`
   уже не `null`), либо с кнопки «чат» на детальной карточке объявления
   (`_BoardAdDetailPopulatedState._openChat`, см. шаг 10 ниже).
8. `_MessagesHeaderMenu.build`: `phone = chat.ad?.phone?.trim(); hasPhone =
   phone != null && phone.isNotEmpty`. `PopupMenuButton` всегда строит ровно
   один пункт «Позвонить» (`context.l10n.messages_call`), с `enabled:
   hasPhone` — при `!hasPhone` пункт визуально серый и недоступен для тапа
   (стандартное поведение `PopupMenuItem.enabled == false`), сам вызов
   `launchUrl` при этом недостижим.
9. При `hasPhone == true` и тапе по пункту: `onSelected: (action) { switch
   (action) { case _MessagesHeaderMenuAction.call: if (hasPhone) {
   launchUrl(Uri.parse('tel:$phone')); } } }` — тот же паттерн, что и на
   входе А: без `await`, без `canLaunchUrl`, без обработки ошибок.
10. **`hasPhone` зависит от того, как был открыт этот экран переписки** —
    проверено отдельно чтением обоих путей:
    - открытие со списка чатов (`ChatsCubit.loadChats()` →
      `ChatsRepository.getChats()` → `GET {boardServiceApi}/chats`,
      `Chat.fromJson` парсит опциональное поле `ad` из ответа) — `chat.ad`
      уже заполнен на момент монтирования `MessagesView`
      (`MessagesCubit.findChat()` возвращается немедленно, так как
      `state.chat.id != null`); `hasPhone` равен тому, есть ли у объявления
      телефон, как и ожидается;
    - открытие с кнопки «чат» на детальной карточке
      (`_BoardAdDetailPopulatedState._openChat`): локально конструируется
      `Chat(id: null, peerName: ad.ownerName, adId: ad.adId, adTitle:
      ad.title, adPrice: ad.priceLabel, unreadCount: 0, messages: [],
      userToId: ad.ownerId, userFromId: AppCacheService.getUserId()!)` —
      **аргумент `ad:` не передан вовсе**, поле остаётся `null`.
      `MessagesCubit.findChat()` (вызывается автоматически при создании
      Cubit'а, `state.chat.id == null`) ищет уже существующую переписку
      (`ChatsRepository.findChats(adId, userToId, userFromId)`, тот же
      эндпоинт `/chats` с фильтром) — если пара пользователь-объявление уже
      переписывалась раньше, найденный чат (с реальным `ad`, если сервер
      его вернул) подставляется целиком; если это первая переписка с этим
      продавцом по этому объявлению, `_findExistingChat()` возвращает `null`
      и `state.chat` остаётся локально сконструированным объектом с `ad ==
      null` — `hasPhone` равен `false`, пункт «Позвонить» неактивен **на
      всём протяжении этой первой переписки**, даже если у объявления есть
      телефон, и восстанавливается только при повторном открытии той же
      переписки со списка чатов позже.

### Альтернативные потоки

- **`ad.phone` пуст/отсутствует.** Вход А: иконка не рендерится вовсе (шаг
  3). Вход Б: пункт меню виден, но недоступен для тапа (шаг 8). В обоих
  случаях `launchUrl` не вызывается — это не ветка `ERROR`/`REJECTED`
  события, а условие, при котором событие вообще не инициируется.
- **Нет установленного диалера / эмулятор без телефонии** (упомянуто в
  [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md)) — поскольку
  `Future<bool>`, возвращённый `launchUrl`, нигде не дожидается и не
  читается, ни успех, ни отказ не производят никакого наблюдаемого эффекта
  в приложении: пользователь не получает ни snackbar, ни какого-либо иного
  сигнала. Не воспроизведено тестом (см. «Связанные тесты»).
- **Вход Б для только что созданной переписки** (шаг 10, вторая ветка) —
  пункт «Позвонить» структурно недоступен независимо от наличия телефона у
  объявления, пока пользователь не выйдет и не откроет ту же переписку
  заново со списка чатов. Не является веткой одного и того же UC-159 в
  смысле «событие произошло иначе» — это предпосылка, при которой вход Б не
  наступает вовсе на этой конкретной сессии экрана.
- **Превью визарда создания объявления** (`BoardAdPreviewStepPage`) —
  единственное место, где `contactActionsEnabled: false`: иконка звонка
  видна (если `ad.showPhoneButton`), но `onPressed: null` — тап не
  производит никакого эффекта, `launchUrl` не вызывается. За пределы этого
  файла не выходит (превью — не публикация), упомянуто только как
  единственное исключение из шага 4.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — единственная сущность,
  чьё поле читается этим сценарием (`phone`, извлечённый на сервере из
  generic-атрибута `attribute_id == 9`); не изменяется ни одной веткой
  сценария, ни на одном из двух входов.
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — вход Б целиком
  зависит от того, заполнено ли вложенное поле `Chat.ad`: см. шаг 10 —
  именно опциональность `ad` (уже задокументированная в ENT-19 как «может
  отсутствовать в ответе списка чатов», здесь же дополнительно проверено,
  что при только что созданном локальном `Chat` оно отсутствует
  структурно, не только опционально по ответу сервера) определяет, доступен
  ли пункт «Позвонить» вообще. `Chat` не изменяется этим сценарием.

### Бизнес-правила

- Оба входа читают один и тот же исходный факт (`Ad.phone`) двумя разными
  путями в памяти (`BoardAdDetailModel.phone` для входа А,
  `Chat.ad?.phone` для входа Б) — не через общий сервис/утилиту; правки
  одного сайта не гарантированно затрагивают другой.
- Видимость/доступность действия вычисляется независимо на каждом сайте:
  вход А — `ad.phone != null && ad.phone!.isNotEmpty` (`showPhoneButton`);
  вход Б — `chat.ad?.phone?.trim()` non-null non-empty (`hasPhone`) — два
  разных, не переиспользующих друг друга условия над формально одним и тем
  же значением.
- Ни один из двух вызовов `launchUrl` не оборачивается в `await`, не
  предваряется `canLaunchUrl`, не оборачивается в `try`/`catch` — оба
  сайта fire-and-forget, независимо друг от друга (два места в коде, один и
  тот же паттерн).
- Событие не изменяет ни `Ad`, ни `Chat` — `READ_OK` в буквальном смысле:
  единственный эффект — попытка передать управление системному диалеру за
  пределами наблюдаемости приложения.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — оба входа (А и Б) полностью реализованы и достижимы из UI; находка о
структурной недоступности входа Б для только что созданной переписки (шаг
10) не блокирует сам сценарий (телефон объявления по-прежнему доступен
через вход А на той же карточке), фиксируется в «Открытые вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState.build` (иконка звонка, `IconButtonForTextField.onPressed`) | CURRENT | вход А — тап по иконке телефона на детальной карточке |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModelMapper.toDetailModel` (`showPhoneButton`) | CURRENT | вычисляет видимость кнопки звонка из `Ad.phone` (non-null, non-empty) |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_page.dart` | `BoardAdDetailPage.build` | CURRENT | общая точка входа детальной карточки для обоих маршрутов (`Routes.boardAdDetail`/`Routes.messagesBoardAdDetail`) |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | `BoardAdDetailView.build` | CURRENT | монтирует `BoardAdDetailPopulated(ad: model)` с `contactActionsEnabled` по умолчанию `true` |
| `lib/pages/board_ad_create/presentation/steps/board_ad_preview_step_page.dart` | `BoardAdPreviewStepPage.build` | CURRENT | единственное место с `contactActionsEnabled: false` — превью визарда создания |
| `lib/pages/messages/presentation/messages_view.dart` | `_MessagesHeaderMenu.build` | CURRENT | вход Б — пункт «Позвонить» в выпадающем меню шапки переписки |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState._openChat` | CURRENT | конструирует локальный `Chat(...)` без аргумента `ad:` при переходе в новый чат с карточки объявления — источник находки шага 10 |
| `lib/pages/messages/cubit/messages_cubit.dart` | `MessagesCubit.findChat`, `._findExistingChat` | CURRENT | резолвит уже существующую переписку (с `ad`, если сервер его вернул) либо оставляет локально сконструированный чат с `ad == null` |
| `lib/repositories/chats/chats_repository.dart` | `ChatsRepository.getChats`, `.findChats` | CURRENT | оба используют один и тот же эндпоинт `GET {boardServiceApi}/chats`; `Chat.fromJson` парсит опциональное поле `ad` из ответа |
| `lib/models/chat/chat.dart` | `Chat.ad`, `Chat.fromJson` | CURRENT | опциональное вложенное поле, из которого фактически читается `phone` для входа Б |
| `lib/models/board/ad.dart` | `Ad.phone` | CURRENT | источник значения (generic-атрибут `attribute_id == 9`), общий для обоих входов |
| `lib/widgets/button/icon_button.dart` | `IconButtonForTextField` | CURRENT | обычный `IconButton`; `onPressed: null` делает кнопку видимой, но неактивной (превью визарда) |
| `android/app/src/main/AndroidManifest.xml` | `<queries>` (`android.intent.action.VIEW`, `data android:scheme="tel"`) | CURRENT | package-visibility декларация для Android 11+, не заменяет отсутствующий `canLaunchUrl`-чек в коде |

## Критерии приёмки

- Вход А: иконка звонка отображается на детальной карточке тогда и только
  тогда, когда `ad.showPhoneButton == true` (`ad.phone` не `null` и не
  пусто); тап по ней при `contactActionsEnabled == true` вызывает ровно
  один раз `launchUrl(Uri.parse('tel:${ad.phone}'))`, без `await`.
- Вход А, превью визарда создания (`contactActionsEnabled == false`): тап по
  видимой иконке не вызывает `launchUrl` ни разу.
- Вход Б: пункт «Позвонить» в меню шапки переписки всегда присутствует;
  доступен для тапа (`enabled: true`) тогда и только тогда, когда
  `chat.ad?.phone?.trim()` не `null` и не пусто; тап вызывает ровно один раз
  `launchUrl(Uri.parse('tel:$phone'))`, без `await`.
- Переписка, открытая впервые с карточки объявления через кнопку «чат»
  (`_openChat`) и не найденная как уже существующая (`findChats` вернул
  пустой список), даёт `chat.ad == null` и, следовательно, `hasPhone ==
  false` для пункта «Позвонить» на всём протяжении этой сессии экрана —
  независимо от того, есть ли у объявления телефон.
- Ни один из двух входов не изменяет ни одно поле `Ad`/`Chat` и не эмитит
  новое состояние экрана в результате самого нажатия (за исключением
  побочного `viewAd()`, принадлежащего отдельному
  [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md), не этому
  сценарию).

## Связанные тесты

**TBD — теста нет.** Ни на один из двух входов не найдено ни widget-, ни
unit-теста:

- `grep -rln "BoardAdDetailPopulated\|showPhoneButton\|contactActionsEnabled\|MessagesHeaderMenu\|messages_call" test/` —
  ноль совпадений.
- `grep -rn "launchUrl\|tel:" test/` — ноль совпадений во всём каталоге
  тестов.
- Существующие `test/pages/ad_detail_cubit_test.dart` (группы `UC-145`/
  `UC-146`, старая нумерация — про `AdDetailCubit.viewAd`, отдельный
  сценарий [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md)) и
  `test/pages/messages_cubit_test.dart` (группы `UC-151`/`UC-152`, старая
  нумерация — про `MessagesCubit.sendMessage`) существуют, но проверяют
  другие сценарии того же модуля, не касаются ни кнопки/иконки звонка, ни
  пункта меню «Позвонить».
- Находка шага 10 (`chat.ad == null` для только что созданной переписки)
  тоже не покрыта тестом — `test/pages/messages_cubit_test.dart` не мокает
  `ChatsRepository.findChats` как возвращающий пустой список специально для
  проверки состояния `chat.ad` после этого.

## Открытые вопросы и ограничения

- **Оба входа — независимо повторённый fire-and-forget-паттерн.** Ни один
  вызов `launchUrl` (ни на детальной карточке, ни в меню переписки) не
  оборачивается в `await`, `canLaunchUrl` или обработку ошибок — полностью
  соответствует описанию в
  [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md), проверено
  здесь отдельно на обоих сайтах чтением кода. Отсутствие общей
  утилиты/сервиса для звонка означает, что будущее исправление (например,
  добавление `canLaunchUrl` + сообщение об ошибке) нужно будет внести в
  обоих местах по отдельности, если не будет выделен общий хелпер.
- **Вход Б структурно недоступен для только что созданной переписки**
  (шаг 10). Это не тот же класс дефекта, что fire-and-forget — это
  отдельная, более узкая находка: `chat.ad` заполняется только через
  `MessagesCubit.findChat()`, который перезаписывает состояние лишь если
  находит уже существующую переписку тем же адресатом/объявлением;
  локально сконструированный (только что открытый) чат никогда не несёт
  `ad` сам по себе. Пользователь, впервые пишущий продавцу, не может
  позвонить через меню переписки в течение этой же сессии экрана — только
  через вход А на той же самой карточке объявления (которая всё ещё
  доступна: заголовок шапки переписки — это ссылка обратно на
  `BoardAdDetailPage`, `Routes.messagesBoardAdDetail`).
- **Реальное поведение при открытии `tel:`-ссылки не подтверждено на
  устройстве.** Android-манифест (`android/app/src/main/AndroidManifest.xml`)
  декларирует `<queries>` для `scheme="tel"` — package-visibility на
  Android 11+ не блокирует резолв диалера сама по себе; но `canLaunchUrl` в
  коде всё равно не вызывается ни разу, так что при отсутствии диалера
  (эмулятор без телефонии) поведение `launchUrl` (тихий `false`/брошенное
  исключение, проглоченное отсутствием `try`/`catch`) не воспроизведено
  тестом ни для одного из двух входов — фиксируется только как утверждение
  из [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md), не
  перепроверено эмпирически здесь.
- **`ios/Runner/Info.plist` не декларирует `LSApplicationQueriesSchemes`**
  для `tel` (в отличие от `AndroidManifest.xml`) — не проверено, требуется
  ли это на практике для `url_launcher`/`tel:` на iOS (обычно системные
  схемы вроде `tel:` не требуют явной декларации в отличие от кастомных URL
  схем сторонних приложений); упоминается как наблюдение по коду, не как
  подтверждённый дефект, не разбирается глубже в рамках этого файла.
- **`RESULT = READ_OK` не имеет наблюдаемой пары `ERROR`/`REJECTED` в
  этом коде.** Ни один из двух сайтов не читает результат `launchUrl` —
  сценарий, в котором диалер не открылся, структурно неотличим от
  сценария, в котором он открылся: код не порождает ветку, которую можно
  было бы задокументировать отдельным use-case с другим `RESULT`. Это
  согласуется с законом «RESULT — закрытый словарь»
  (`../use-cases/AGENTS.md`), но стоит зафиксировать явно: если фактическое
  поведение диалера когда-либо станет наблюдаемым (например, добавят
  `canLaunchUrl`), это будет новое событие/новый use-case, а не изменение
  этого файла.
