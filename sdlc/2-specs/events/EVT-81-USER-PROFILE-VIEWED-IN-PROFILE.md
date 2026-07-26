# EVT-81 — user.profile_viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) |

**Триггер.** Пользователь (гость или авторизованный) открывает вкладку
«Профиль» (`/profile`, без route-guard) — legacy `ProfileBloc.on<ProfileEventStart>`
(`lib/pages/profile/profile_bloc.dart`).

**Эффект.** Гость видит `LoginView` вместо данных профиля; авторизованный —
имя/страну (резолвится по `countryId`, либо по совпадению `phoneCountryIsoCode`,
если `countryId` не совпал ни с одной страной)/кнопки перехода в настройки,
BOARD (избранное/сообщения/мои объявления, видны только при
`BoardChatAvailabilityCubit == true`), «В работе», «Настройки работы».
Реактивно перезагружается при изменении пользователя в Hive-боксе.

**Исходный код.** `lib/pages/profile/presentation/profile_page.dart`,
`lib/pages/profile/presentation/widgets/profile/profile_view.dart`;
`lib/pages/profile/profile_bloc.dart` → `ProfileBloc.on<ProfileEventStart>`.
