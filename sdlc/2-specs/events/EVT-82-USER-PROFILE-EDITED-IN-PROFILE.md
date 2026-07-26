# EVT-82 — user.profile_edited

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) |

**Триггер.** Пользователь редактирует имя/email/телефон/страну на экране
`ProfileSettingsPage` и нажимает «Сохранить» — `ProfileEditCubit.saveChanges()`.

**Эффект.** Для авторизованного — `AuthRepository.updateUser(newUserData)`
(`PUT {authSerivceApi}/user`, нормализация телефона, запись в Hive). Для
гостя — **без сетевого вызова**: только `AppCacheService.saveGuestCountryCode`
(локально) и обновление in-memory `currentUserData`. Если среди изменённых
полей — `locale`, метод не завершает обычным успехом, а эмитит
`isLanguageChanged: true` и возвращает `false` — см.
[EVT-83](EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md).

**Исходный код.** `lib/pages/profile/cubit/profile_edit_cubit.dart` →
`ProfileEditCubit.saveChanges`, `editName`/`editFirstName`/`editEmail`/
`editPhone`/`selectCountryCode`/`selectCountry`; `lib/repositories/auth/auth_repository.dart` →
`AuthRepository.updateUser`.
