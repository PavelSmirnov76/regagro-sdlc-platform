# EVT-71 — ad.favourite_toggled

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Пользователь тапает сердечко на карточке объявления (единственный
реально подключённый путь — в общей ленте/«Моих объявлениях»/«Избранном»;
кнопка на самой детальной карточке и переход на экран «Избранное» из ленты/
профиля закомментированы в UI, см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) —
`BoardCubit.toggleAdFavourite`/`AdDetailCubit.toggleAdFavourite`.

**Эффект.** `AdRepository.setAdFavourite` — `POST /selected-ads` (добавить)
либо `DELETE /selected-ads/{id}` (убрать). На экране «Избранное» переключение
дополнительно убирает карточку из списка целиком. **Известный дефект**:
`Ad.props` (Equatable) не включает `isFavourite` — после успешного запроса
`BoardCubit` не перерисовывает иконку (см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md));
`AdDetailCubit` использует отдельную freezed-модель без этого дефекта, но не
подключён к живой кнопке.

**Исходный код.** `lib/pages/board/cubit/board_cubit.dart` →
`BoardCubit.toggleAdFavourite`; `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` →
`AdDetailCubit.toggleAdFavourite`; `lib/repositories/board/ad_repository.dart` →
`AdRepository.setAdFavourite`.
