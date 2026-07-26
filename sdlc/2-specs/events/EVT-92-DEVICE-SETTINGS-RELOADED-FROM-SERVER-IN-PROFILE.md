# EVT-92 — device_settings.reloaded_from_server

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

**Триггер.** Внутри `DataUpdateBloc._suncDevices()` — вызывается **дважды**
за один проход: сразу после
[EVT-91](EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) (до
[EVT-90](EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md), решает, нужен
ли он вообще), и повторно сразу после
[EVT-90](EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md), если он
выполнялся: `DeviceSettingsRepository.fetchDevicesFromApi()`.

**Эффект.** `GET /devices`; если ответ непуст —
`clearAndInsertAll(remoteDevices)` **заменяет всю локальную таблицу
`Devices` целиком** (единственный момент, когда `remoteId` реально
попадает в локальные строки); затем `ensureDeviceInDatabase()` вызывается
повторно, чтобы досеять любые дефолтные типы, отсутствующие в серверном
ответе. Исключение перехватывается внутри самого метода (`catch (e,
stackTrace) { Talker.handle(...); return []; }`) — сетевой сбой этого шага
не проваливает sync-проход целиком, просто возвращает пустой список (как
если бы у сервера не было записей, что вручную неотличимо от «сеть упала»).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc._suncDevices`; `lib/repositories/devices_settings/devices_settings_repository.dart` →
`DeviceSettingsRepository.fetchDevicesFromApi`.
