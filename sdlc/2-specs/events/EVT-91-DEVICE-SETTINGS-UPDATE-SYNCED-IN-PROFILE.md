# EVT-91 — device_settings.update_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

**Триггер.** Внутри `DataUpdateBloc._suncDevices()` — **безусловно**, на
каждом полном sync-проходе, до pull: `DeviceSettingsRepository.updateDevicesOnSHTP()`.

**Эффект.** `PUT /devices/update` только для строк `isNeedUpdate == true &&
remoteId != null`, одним batch-запросом. Как и
[EVT-90](EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md), метод сам
перехватывает исключение и возвращает непроверяемый `bool`, не сбрасывает
`isNeedUpdate` локально после успеха — те же строки будут отправлены
повторно на следующем проходе, пока их не перезапишет pull
([EVT-92](EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc._suncDevices`; `lib/repositories/devices_settings/devices_settings_repository.dart` →
`DeviceSettingsRepository.updateDevicesOnSHTP`.
