# UC-160 — Пользователь звонит по номеру объявления с карточки или из шапки переписки — отказ запуска звонка нигде не долетает до пользователя

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

[EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) (`ad_contact.called`)
достижимо из двух равнозначных, независимо проверенных чтением кода мест —
(а) иконка телефона на детальной карточке объявления
(`board_ad_detail_populated.dart`) и (б) пункт «Позвонить» в выпадающем меню
шапки переписки (`messages_view.dart`) — и в обоих `launchUrl(Uri.parse(
'tel:$phone'))` вызывается без `await`, без предварительного `canLaunchUrl`
и без `try`/`catch` вокруг вызова. Сам звонок не изменяет ни одну запись
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md) — это `READ`-по-CRUD-классификации
действие (использование уже прочитанных контактных данных), а не мутация.
Этот файл фиксирует единственный содержательный сценарий этого события —
отказ запуска звонка, в любой из двух его реально возможных форм, остаётся
полностью невидимым для пользователя, независимо от того, с какой из двух
точек входа он начат.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Ни
`BoardAdDetailPopulated`, ни `_MessagesHeaderMenu`, ни `launchUrl` не
проверяют статус авторизации — звонок по номеру объявления/собеседника не
требует входа в аккаунт (`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` и
`lib/pages/messages/presentation/messages_view.dart` не находит ни одного
совпадения).

## CURRENT

### Основной поток

**Общий эффект, одинаковый для обеих точек входа.**

1. Оба места вызывают ровно одну и ту же функцию пакета `url_launcher` —
   `launchUrl(Uri)` (`package:url_launcher/src/url_launcher_uri.dart`) — и в
   обоих местах возвращаемое значение полностью отбрасывается: нет `await`,
   нет `.then`/`unawaited()`, нет `try`/`catch` ни в одном из двух виджетов.
2. Собственная документация функции в исходнике пакета фиксирует два разных
   исхода неудачи: «Returns true if the URL was launched successfully,
   otherwise either returns false or throws a `PlatformException` depending
   on the failure» (`url_launcher-6.3.2/lib/src/url_launcher_uri.dart`,
   doc-comment `launchUrl`). Поскольку ни один из двух вызывающих сайтов не
   читает `Future<bool>`, оба исхода неразличимы для пользователя:
   - **исключение** (`PlatformException`, типичный случай для эмулятора/
     симулятора без установленного диалера, либо устройства без телефонного
     приложения вовсе) — поскольку вызов не дожидается результата,
     исключение всплывает как необработанная ошибка `Future` асинхронно,
     вне стека вызова нажатия; попадает (если попадает вообще) только в
     стандартный обработчик необработанных ошибок Flutter/зоны, не в
     `Talker`, не в `AppSnackBar`, не в какой-либо виджет этого дерева;
   - **обычный (не бросающий) `false`** — штатный, документированный сигнал
     «не удалось запустить» — тоже никогда не читается ни одним из двух
     вызывающих сайтов, то есть с точки зрения кода неотличим от успеха.
3. В обоих случаях нет ни `SnackBar` (`showAppSnackBarError`/
   `showAppSnackBarInfo`), ни диалога, ни индикатора загрузки — нажатая
   иконка/пункт меню просто возвращаются в состояние покоя, как будто
   ничего не произошло.
4. Ни одно из двух мест не вызывает `canLaunchUrl` до попытки запуска —
   решение показать/включить кнопку целиком основано на наличии непустого
   номера телефона в данных, а не на том, способно ли устройство реально
   обработать `tel:`-схему.

**Точка входа (а) — иконка телефона на детальной карточке объявления.**

5. `BoardAdDetailPopulated.build`: иконка телефона рендерится только при
   `ad.showPhoneButton` — поле, вычисленное один раз в
   `BoardAdDetailModelMapper.toDetailModel()` как `phone != null &&
   phone!.isNotEmpty` (`board_ad_detail_model.dart`), то есть отсутствие
   номера у объявления убирает саму иконку, а не только обработчик.
6. `onPressed: widget.contactActionsEnabled ? () { if (ad.phone != null) {
   launchUrl(Uri.parse('tel:${ad.phone!}')); } } : null` —
   `contactActionsEnabled` (конструктор `BoardAdDetailPopulated`, по
   умолчанию `true`) выключается только в одном месте во всём `lib/` —
   превью шага визарда создания объявления
   (`board_ad_preview_step_page.dart`, `contactActionsEnabled: false`); во
   всех остальных живых входах (`board_ad_detail_view.dart` строит
   `BoardAdDetailPopulated(ad: model)` без переопределения аргумента)
   значение — дефолтный `true`, то есть кнопка активна.
7. При нажатии (и `contactActionsEnabled == true`, и `ad.phone != null`) —
   `launchUrl(Uri.parse('tel:${ad.phone!}'))`, эффект и отказ — см. пункты
   1–4 выше.

**Точка входа (б) — пункт «Позвонить» в шапке переписки.**

8. `_MessagesHeaderMenu.build` (`messages_view.dart`): `phone =
   chat.ad?.phone?.trim(); hasPhone = phone != null && phone.isNotEmpty` —
   номер берётся из вложенного объявления самого чата
   ([ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md), `Chat.ad`), не из
   какого-либо отдельного запроса.
9. Пункт меню `PopupMenuItem<_MessagesHeaderMenuAction>(value: .call,
   enabled: hasPhone, ...)` — при `chat.ad == null` или пустом/`null`
   номере пункт отображается неактивным (серый текст/иконка через
   тернарник в `Text`/`Icon`, `enabled: false` у самого
   `PopupMenuItem` — Flutter не вызывает `onSelected` для отключённого
   пункта), то есть попытки запуска в этом случае вообще не происходит —
   это отдельная, не входящая в этот сценарий ветка (см. «Альтернативные
   потоки»).
10. При `hasPhone == true` и выборе пункта — `onSelected: (action) {
    switch (action) { case _MessagesHeaderMenuAction.call: if (hasPhone) {
    launchUrl(Uri.parse('tel:$phone')); } } }` — тот же вызов, без `await`,
    без `try`/`catch`, эффект и отказ — те же пункты 1–4.

### Альтернативные потоки

- **Иконка телефона скрыта целиком** (а): `ad.showPhoneButton == false`
  (`Ad.phone` пуст/`null`) — иконки нет в дереве вовсе, попытки запуска не
  существует; не этот сценарий.
- **Пункт «Позвонить» неактивен** (б): `chat.ad == null` либо
  `chat.ad!.phone` пуст/`null`/состоит из пробелов — пункт меню отрисован,
  но `enabled: false`, выбор недоступен пользователю; попытки запуска не
  происходит; не этот сценарий.
- **Превью визарда создания** (а, `contactActionsEnabled == false`):
  иконка телефона отображается, но `onPressed: null` — нажатие не вызывает
  вообще никакого кода, в отличие от сценария этого файла, где
  `launchUrl` вызывается, но результат теряется.
- **Успешный запуск диалера** — `launchUrl` возвращает `true`, диалер
  открывается с уже набранным номером; это `READ_OK` того же события, не
  входит в этот файл (значение результата всё равно нигде не читается ни
  на этом, ни на другом пути — код одинаков для обеих точек входа).
- **Обе точки входа читают разный источник номера, но идентичный код
  запуска.** (а) читает `ad.phone` (аргумент `BoardAdDetailModel`,
  переданный при открытии карточки); (б) читает `chat.ad?.phone` (номер из
  объявления, вложенного в открытый чат) — расхождение источника не влияет
  на этот сценарий: оба в итоге строят один и тот же `Uri.parse('tel:...')`
  и передают его в один и тот же необрабатываемый `launchUrl`.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — `phone` читается
  только: и в (а) через `BoardAdDetailModel.phone`/`.showPhoneButton`, и в
  (б) через вложенный `Chat.ad?.phone`. Ни одна запись `Ad` не изменяется
  этим сценарием.
- [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat) — точка входа (б)
  зависит от того, заполнено ли `Chat.ad` (может отсутствовать в ответе
  списка чатов, см. [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md),
  «Поля») — не изменяется этим сценарием.

### Бизнес-правила

- Для отказа звонка (в любой из двух документированных пакетом форм —
  брошенное исключение или возвращённый `false`) во всём модуле не
  существует ни одного канала обратной связи пользователю — ни
  `SnackBar`, ни `Talker`, ни какого-либо другого видимого механизма.
- Ни одна из двух точек входа не предваряет попытку запуска проверкой
  `canLaunchUrl` — видимость/активность кнопки полностью определяется
  наличием непустого номера в данных, не возможностью устройства
  реально обработать `tel:`-схему.
- Обе точки входа технически независимы (разные виджеты, разные условия
  видимости/активности, разные источники номера), но используют
  побайтово идентичный паттерн вызова `launchUrl` — фиксация отказа как
  общего сценария события, а не как двух разных use-case, оправдана тем,
  что наблюдаемое пользователем поведение отказа тождественно в обеих
  точках.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе точки входа и общий для них
паттерн необрабатываемого `launchUrl` воспроизводятся статическим чтением
кода целиком (`board_ad_detail_populated.dart`, `messages_view.dart`,
исходник пакета `url_launcher` — doc-comment `launchUrl`, подтверждающий
оба документированных пакетом исхода неудачи). Исправление (например,
проверка возвращённого `bool`, `canLaunchUrl` до попытки, `SnackBar` при
неудаче) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `_BoardAdDetailPopulatedState.build` (иконка телефона, `onPressed`) | CURRENT | точка входа (а) — вызывает `launchUrl` без `await`/`canLaunchUrl`/`try`-`catch`, только если `ad.phone != null` и `contactActionsEnabled` |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModelMapper.toDetailModel` (`showPhoneButton`) | CURRENT | вычисляет видимость иконки телефона (а) один раз при построении модели карточки |
| `lib/pages/board_ad_create/presentation/steps/board_ad_preview_step_page.dart` | `contactActionsEnabled: false` | CURRENT | единственное место, где точка входа (а) выключается целиком (превью визарда), см. «Альтернативные потоки» |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | `BoardAdDetailView.build` | CURRENT | все живые (не превью) открытия карточки — `contactActionsEnabled` дефолтный `true` |
| `lib/pages/messages/presentation/messages_view.dart` | `_MessagesHeaderMenu.build`, `onSelected` (`_MessagesHeaderMenuAction.call`) | CURRENT | точка входа (б) — тот же вызов `launchUrl` без обработки, только при `hasPhone` |
| `lib/models/chat/chat.dart` | `Chat.ad` | CURRENT | источник номера для точки входа (б) — может быть `null` |
| `url_launcher-6.3.2/lib/src/url_launcher_uri.dart` | `launchUrl` | CURRENT (внешний пакет `url_launcher`) | doc-comment фиксирует оба возможных исхода неудачи — `false` без исключения либо `PlatformException` |

## Критерии приёмки

- Нажатие иконки телефона на карточке объявления (при `ad.showPhoneButton
  && contactActionsEnabled && ad.phone != null`) вызывает ровно один раз
  `launchUrl(Uri.parse('tel:${ad.phone}'))`, без предшествующего
  `canLaunchUrl` и без обёртки `try`/`catch`.
- Выбор пункта «Позвонить» в меню шапки переписки (при `hasPhone == true`)
  вызывает ровно один раз `launchUrl(Uri.parse('tel:$phone'))`, тем же
  образом — без проверки и без обработки.
- В обеих точках входа возвращаемое значение `launchUrl` (`Future<bool>`)
  нигде не читается — ни через `await`, ни через `.then`, ни через
  `unawaited()` с последующей проверкой.
- Если платформа не может обработать `tel:`-схему (нет диалера) —
  независимо от того, приводит ли это к `false` или к брошенному
  `PlatformException` — ни один виджет этого дерева не показывает
  пользователю никакого сообщения об этом.
- Пункт «Позвонить» в шапке переписки недоступен для выбора (`enabled:
  false`), если `chat.ad == null` или номер пуст — попытка запуска в этом
  случае не происходит вовсе.

## Связанные тесты

TBD — теста нет. `grep -rln "board_ad_detail_populated\|BoardAdDetailPopulated\|messages_view\|MessagesView\|launchUrl\|tel:" test/` не находит ни одного тестового файла, ссылающегося ни на один из виджетов, ни на сам вызов `launchUrl`/`tel:`-схему — сценарий этого файла не покрыт ни одним существующим тестом ни на уровне виджета, ни на уровне интеграции.

## Открытые вопросы и ограничения

- **Тот же необрабатываемый паттерн `launchUrl` используется и за пределами
  `BOARD`.** `grep -rn "launchUrl(" lib/` находит идентичный по форме
  вызов (без `await`/`canLaunchUrl`/`try`-`catch`) также в
  `lib/pages/registration/presentation/widgets/registration_view.dart`,
  `lib/pages/app_update/app_update_page.dart`,
  `lib/pages/profile/presentation/widgets/login/login_view.dart` и
  `lib/pages/profile/presentation/widgets/profile/profile_view.dart` — этот
  файл фиксирует находку только для двух мест
  [EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) (`ad_contact
  .called`), не разбирает остальные вхождения за пределами `MOD-5`.
- **Смежная, но структурно другая находка на той же карточке объявления —
  не про звонок.** `BoardAdDetailPopulated._openChat` (кнопка чата,
  `ad.showChatButton && !ad.isMe`) использует `AppCacheService
  .getUserId()!` — безусловный force-unwrap на потенциально `null`
  значении для гостя, что делает саму кнопку чата видимой гостю и приводит
  к падению `Null check operator used on a null value` при нажатии. Это
  дефект действия «открыть чат»
  ([EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md)-инициации), не
  звонка — уже подробно задокументирован как основной анализ в
  [UC-145](UC-145-ACTOR-5-EVT-73-ENT-18-READ_OK-IN-BOARD.md) («Открытые
  вопросы», «Кнопка чата видна гостю и падает при нажатии»); упоминается
  здесь только как соседняя находка на том же экране, не разбирается
  повторно, чтобы не подменять собой основной результат этого файла
  (звонок, `READ_ERROR`).
- **Не проверено эмпирически на реальном устройстве без диалера** — вывод
  сделан статическим чтением кода обоих вызывающих сайтов и
  doc-comment'а самой функции `launchUrl` в исходнике пакета
  `url_launcher-6.3.2`; какой именно из двух документированных исходов
  (тихий `false` или брошенное исключение) в реальности возвращает каждая
  платформа (Android/iOS/эмулятор/симулятор) для отсутствующего
  телефонного обработчика — этой спекой не верифицировано, оба
  рассмотрены как равно возможные и равно невидимые пользователю.
