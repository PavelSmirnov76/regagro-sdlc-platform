# EVT-69 — ad.edited

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Автор открывает собственное объявление на правку (пункт
«Редактировать» в контекстном меню карточки на «Моих объявлениях» —
`BoardAdCreatePageArguments(ad: ad)`, `BoardAdCreateData.fromAd`) и проходит
тот же визард, что и при создании, подтверждает — `BoardAdCreateBloc._onCreateAd`
(edit-режим).

**Эффект.** `AdRepository.updateAd` — multipart `POST /ads/{id}` с
`_method: PUT`, различает удалённые фото по схеме URL (`http(s)` = уже на
сервере → `filesPaths`, иначе локальный файл → новый multipart). В отличие
от создания, `BoardAdCreateData.fromAd` не ограничивает `adTypeId` набором
`Constants.boardAdTypeIds` — правка объявления типа «Пропажа»/«Найдено»
(созданного не через мобильный визард) работает, хотя создать такое из
визарда нельзя.

**Исходный код.** `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` →
`BoardAdCreateBloc._onCreateAd`, `BoardAdCreateData.fromAd`; `lib/repositories/board/ad_repository.dart` →
`AdRepository.updateAd`.
