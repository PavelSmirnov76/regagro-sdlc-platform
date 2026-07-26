# EVT-80 — ad_contact.called

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Два равнозначных входа: (а) иконка телефона на детальной
карточке объявления (видна при `ad.phone != null`, отключена в превью
визарда создания); (б) пункт «Позвонить» в выпадающем меню шапки переписки
(`chat.ad?.phone`).

**Эффект.** `launchUrl(Uri.parse('tel:$phone'))` — без `await`, без
`canLaunchUrl`, без обработки отказа (нет установленного диалера/эмулятор) —
fire-and-forget, ошибка проглатывается стандартным механизмом Flutter,
пользователь не получает сообщения о неудаче. Не изменяет ни одну запись
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md).

**Исходный код.** `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` →
кнопка звонка; `lib/pages/messages/presentation/messages_view.dart` →
`_MessagesHeaderMenu`, пункт «Позвонить».
