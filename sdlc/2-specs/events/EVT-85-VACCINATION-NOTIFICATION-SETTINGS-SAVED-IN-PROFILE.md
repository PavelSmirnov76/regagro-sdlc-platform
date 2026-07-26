# EVT-85 — vaccination_notification_settings.saved

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |

**Триггер.** Пользователь меняет дни-до-вакцинации (слайдер `HorizontalPicker`,
1-30) и/или переключатель email-уведомления, нажимает сохранить —
`NotificationsSettingsCubit.save()`. Два дополнительных переключателя на
этом же экране (`_notifyOnNewMessages`, `_systemNotifications`) — чисто
декоративные, хранятся только в локальном `State` виджета, не читаются и не
сохраняются этим методом (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).

**Эффект.** `SettingsRepository.saveProfileSettings` →
`dao.clearAndInsertAll([...])` — локальная таблица `ProfileSettings`
полностью перезаписывается одной строкой. Отправка на сервер этим методом
**не выполняется** — push происходит отдельно, при следующем sync-проходе с
`isUpdateData: true` (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).

**Исходный код.** `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` →
`NotificationsSettingsCubit.save`, `changeDaysToVaccination`,
`changeSendVaccinationNotificationOnEmail`; `lib/repositories/settings/settings_repository.dart` →
`SettingsRepository.saveProfileSettings`.
