# EVT-88 — device_settings.viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

**Триггер.** Пользователь открывает «Настройки устройств»
(`/profile/work_settings/devices_settings`, грид) и/или конкретное
устройство (`/profile/work_settings/devices_settings/scanner_settings`,
форма) — `DevicesSettingsPage`/`ScannerSettingsPage`,
`DeviceSettingsRepository.getCurrentScannerDevices()`/`getScannerDeviceByType()`.

**Эффект.** Грид схлопывает все bluetooth-клавиатурные устройства
(`ScannerDeviceTypes.bluetoothGroup`) в одну плитку «Bluetooth»; форма
показывает параметры, специфичные для типа устройства (операции/регион/
мощность/антенны/адрес/действия кнопок TCD/чекбокс камеры QR — набор
зависит от типа, см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)), либо
групповую форму сразу для нескольких bluetooth-устройств
(`_GroupOperationsContent`).

**Исходный код.** `lib/pages/scanner_settings/pages/devices_settings_page.dart`;
`lib/pages/scanner_settings/pages/scanner_settings_page.dart`;
`lib/repositories/devices_settings/devices_settings_repository.dart` →
`DeviceSettingsRepository.getCurrentScannerDevices`, `getScannerDeviceByType`, `getDeviceByType`.
