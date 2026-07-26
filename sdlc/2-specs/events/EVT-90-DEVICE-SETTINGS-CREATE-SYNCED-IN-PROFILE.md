# EVT-90 — device_settings.create_synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

**Триггер.** Внутри `DataUpdateBloc._suncDevices()` — **условно**, только
если предшествующий pull ([EVT-92](EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
выполняется первым в этом же проходе) вернул пустой список — то есть
фактически только пока на сервере ещё нет ни одной записи устройств для
этого пользователя/установки: `DeviceSettingsRepository.syncDevicesOnSHTP()`.

**Эффект.** `POST /devices/store` со всеми «синкуемыми» устройствами
(`ScannerDeviceTypes.defaults`) разом, одним запросом. Метод сам
перехватывает исключение (`catch (e, stackTrace) { Talker.handle(...); return
false; }`, не пробрасывает) и возвращает `bool`, который вызывающий код **не
проверяет**. Не проставляет `remoteId`/не сбрасывает `isNeedUpdate` локально
после успеха — это происходит только следующим pull'ом
([EVT-92](EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) и
полной заменой таблицы.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc._suncDevices`; `lib/repositories/devices_settings/devices_settings_repository.dart` →
`DeviceSettingsRepository.syncDevicesOnSHTP`.
