# EVT-73 — ad.detail_viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Пользователь (гость или авторизованный) открывает детальную
карточку объявления — тапом по карточке в ленте/«Моих»/«Избранном», либо из
шапки переписки (`Routes.boardAdDetail`/`Routes.messagesBoardAdDetail`,
общий экран, смонтированный в двух поддеревьях роутера) —
`AdDetailCubit(model)..viewAd()`, вызывается автоматически при создании Cubit'а,
не отдельным действием пользователя.

**Эффект.** `AdRepository.viewAd` — `POST /ads/{id}/view`, инкремент
`viewsCount` на сервере; локально `AdDetailCubit` (freezed-модель, без бага
`Ad.props`) корректно обновляет счётчик в своём state, но это не отражается
обратно в списке ленты (разные объекты).

**Исходный код.** `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` →
`BlocProvider.create`; `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` →
`AdDetailCubit.viewAd`; `lib/repositories/board/ad_repository.dart` →
`AdRepository.viewAd`.
