# EVT-55 — disposals.viewed_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Пользователь открывает хаб ещё не отправленных выбытий (обычно со сводного экрана «В работе»); `UnsentDisposalsCubit.load`. Кубит также реактивно подписан на `watchNotSyncDisposals()` — перезагружается сам при любом изменении таблицы, не только по явному действию пользователя.

**Эффект.** Загружает все записи с `sync == false`; список — основа для последующего [EVT-51](EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md).

**Исходный код.** `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` → `UnsentDisposalsCubit.load`.
