# EVT-51 — disposal.deleted_unsent

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |

**Триггер.** Пользователь удаляет группу ещё не отправленных записей выбытия с экрана хаба «В работе»; `UnsentDisposalsCubit.deleteGroup`.

**Эффект.** Безусловное («жёсткое») удаление каждой строки группы из локальной таблицы по очереди — у Disposal нет мягкого удаления как концепции (см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)). Список реактивно перезагружается сам (подписка на `watchNotSyncDisposals`).

**Исходный код.** `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` → `UnsentDisposalsCubit.deleteGroup`.
