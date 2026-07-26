# EVT-84 — vaccination_notification_settings.viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |

**Триггер.** Пользователь открывает «Настройки уведомлений»
(`/profile/profile_settings/notifications_settings`) —
`NotificationsSettingsCubit.load()`.

**Эффект.** Читает `SettingsRepository.getProfileSettings()` (локально,
Drift). Дефолты при отсутствии сохранённых значений — `daysToVaccination: 7`,
`sendVaccinationNotificationOnEmail: true` (в коде cubit'а); UI-слайдер,
однако, использует собственный фолбэк `5` (см.
[ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)) — расхождение,
видимое только в узком окне до завершения `load()`.

**Исходный код.** `lib/pages/profile_settings/presentation/notifications_settings_page.dart`;
`lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` →
`NotificationsSettingsCubit.load`; `lib/repositories/settings/settings_repository.dart` →
`SettingsRepository.getProfileSettings`.
