# EVT-70 — ad.deleted

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Автор удаляет собственное объявление с экрана «Мои объявления»
(единственный экран с этим действием — контекстное меню карточки →
подтверждение в `_DeleteAdConfirmDialog`) — `BoardCubit.deleteAd`.

**Эффект.** `AdRepository.deleteAd` — `DELETE /ads/{id}`; при успехе
объявление убирается из локального списка `BoardState.ads` в памяти
(никакой локальной таблицы нет, удалять больше нечего).

**Исходный код.** `lib/pages/my_ads/presentation/my_ads_view.dart` →
`_deleteAd` (единственное место, где вызов обёрнут в try/catch со снэкбаром);
`lib/pages/board/cubit/board_cubit.dart` → `BoardCubit.deleteAd`;
`lib/repositories/board/ad_repository.dart` → `AdRepository.deleteAd`.
