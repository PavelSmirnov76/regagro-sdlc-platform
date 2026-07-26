# EVT-89 — device_settings.saved

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

**Триггер.** Пользователь меняет операции/регион/мощность/антенны/IP-или-MAC/
действия кнопок TCD/чекбокс камеры QR на `ScannerSettingsPage` (одно
устройство либо группа bluetooth-устройств разом, `applyToTypes`) и
закрывает форму (`_save`).

**Эффект.** `DeviceSettingsRepository.update*InStorage`/`updateDeviceOperationUsage`/
`updateDeviceButtonAction` — каждое изменение сразу пишется в `Devices`,
проставляя `isNeedUpdate: true`/`updatedAt: now()`. Для типов, требующих
антенны (`bluetooth_gates`, `rfid_reader`, `rfid_reader_grp_tcp`,
`rfid_reader_grp_ble`) — если антенны не выбраны, закрытие формы
осознанно отклоняется бизнес-правилом: снекбар `must_select_antenns`,
`_save` не завершается. Часть изменений дополнительно применяется «на
лету» к реальному оборудованию — регион/мощность для `bluetooth_gates`
(`ScannerService.tryApplyGatesBleRegion`/`tryApplyGatesBlePower`), действия
кнопок TCD (`ScannerService.applyTerminalButtonActions()`).

**Исходный код.** `lib/pages/scanner_settings/pages/scanner_settings_page.dart` →
`_save`, `_GroupOperationsContent`; `lib/repositories/devices_settings/devices_settings_repository.dart` →
`updateAntennasInStorage`, `updateAddressInStorage`, `updatePowerInDatabase`,
`updateRegionInDatabase`, `updateIsUseCameraForQrInDatabase`,
`updateDeviceButtonAction`, `updateDeviceOperationUsage`,
`isDeviceConfiguredForScanning`.
