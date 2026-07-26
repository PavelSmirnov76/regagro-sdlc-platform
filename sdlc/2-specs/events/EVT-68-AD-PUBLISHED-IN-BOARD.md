# EVT-68 — ad.published

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

**Триггер.** Авторизованный пользователь проходит визард создания объявления
(тип → количество животных → место/животное или новое животное → описание →
адрес → контакты → предпросмотр), подтверждает публикацию —
`BoardAdCreateBloc._onCreateAd` (не-edit режим).

**Эффект.** `AdRepository.createAd` — multipart `POST /ads` с генерик-атрибутами
(телефон/адрес/цена/«когда нашлось»), сервер создаёт объявление и присваивает
id; локально ничего не кэшируется (см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) —
online-only). Типы объявлений «Пропажа»(5)/«Найдено»(6) недостижимы на этом
шаге (только 1/3) — см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md).

**Исходный код.** `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` →
`BoardAdCreateBloc._onCreateAd`; `lib/repositories/board/ad_repository.dart` →
`AdRepository.createAd`.
