# ENT-22 — Device

## Описание

Настройки одного подключаемого сканирующего устройства (терминал,
Bluetooth- или UHF/RFID-сканер) — R66. Drift-таблица `Devices`
(`packages/sheep_farm_database/lib/entities/devices/devices.dart`).
Каталог из 13 типов устройств (`ScannerDeviceTypes.defaults`) **сеется
локально автоматически** (`DeviceSettingsRepository.ensureDeviceInDatabase`,
идемпотентный upsert по типу) — пользователь не создаёт записи сам, только
редактирует параметры уже существующих.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id — для «bluetooth-клавиатурных» типов и терминала жёстко фиксирован через `ScannerDeviceLocalIds` (101-108, 1-4, 6-7), не автоинкрементный по факту использования |
| `remoteId` | int? | серверный id — заполняется только после успешного `fetchDevicesFromApi` (pull), не после push (см. «Инварианты») |
| `name` | text | |
| `type` | text | один из `ScannerDeviceTypes` (`ra_100bt`…`ra_6000uhf`, `tcd`, `bluetooth_gates`, `rfid_reader`, `rfid_reader_grp_tcp`, `rfid_reader_grp_ble`, `A7 (bluetooth)`) |
| `power` | real | 1-33 в БД, в UI маппится в 4-100% с шагом 3 |
| `maxPower`/`minPower` | real, default 0 | |
| `region` | int, default 0 | индекс `DeviceRegion` (10 значений — `cn920_925`…`fullBand`) |
| `ip` | text? | адрес для TCP-типов |
| `mac` | text? | адрес для `rfidReaderGrpBle` — единственный MAC-тип, определяется через `_isMacDevice` |
| `antennas` | Set\<int\>? | через `IntSetConverter` (CSV-строка в БД) |
| `availableOperations` | Set\<String\>? | через `StringSetConverter`; `input`/`output` нормализуются в `passage` (`ScannerOperation.normalizeType`) |
| `leftButtonAction`/`middleButtonAction`/`rightButtonAction` | `TcdAction` (`uhfScanner`/`qrScanner`/`uhfPlusQrScanner`/`none`), через `TcdActionConverter` | только для `tcd`; дефолты по устройству `RA-9000UHF`: left=qrScanner, middle=uhfScanner, right=uhfPlusQrScanner |
| `isUseCameraForQr` | bool, default false | только для `tcd` |
| `createdAt` | DateTime, default now | |
| `updatedAt` | DateTime? | проставляется вручную при каждой правке |
| `isNeedUpdate` | bool, default false | флаг «есть локальные изменения, не отправленные на сервер» |

## Связи

- Не связана ни с одной другой сущностью этого модуля напрямую — настройки
  устройства читаются во время выполнения `ScannerService`, используемым
  другими модулями (WEIGH/REG/INV сканирование), но это применение
  настроек, не владение сущностью.

## Инварианты

- **Каталог устройств сеется идемпотентно, не создаётся пользователем.**
  `ensureDeviceInDatabase()` удаляет устаревшие типы (`_obsoleteDeviceTypes`
  — легаси-названия `'TCD'`/`'RFID'`/`'terminal'`/`'uhf_scanner_keyboard'` из
  прошлой схемы), затем для каждого из 13 `defaultDevices` гарантирует
  ровно одну запись, разрешая конфликты id/дублей построчно
  (`_ensureDefaultDevice`).
- **Push «создание» и push «правка» — два разных метода с разным условием
  запуска, не единый механизм.** `syncDevicesOnSHTP()` (`POST /devices/store`)
  шлёт **все** «синкуемые» устройства и вызывается из
  `DataUpdateBloc._suncDevices()` **только если** первый в этом же проходе
  `fetchDevicesFromApi()` (pull) вернул пустой список (т.е. фактически
  только пока на сервере вообще нет ни одной записи для этого юзера/девайса —
  условный, «первичный» push, не выполняется на каждом проходе).
  `updateDevicesOnSHTP()` (`PUT /devices/update`) шлёт только строки с
  `isNeedUpdate == true && remoteId != null` и вызывается **безусловно** на
  каждом проходе, до pull.
- **Ни `syncDevicesOnSHTP()`, ни `updateDevicesOnSHTP()` не сбрасывают
  `isNeedUpdate` и не проставляют `remoteId` локально после успеха.** Оба
  метода лишь возвращают `bool` (true/false), полученный из того, бросил ли
  сетевой вызов исключение (оба сами перехватывают исключение —
  `catch (e, stackTrace) { getIt<Talker>().handle(e, stackTrace); return false; }`,
  не пробрасывают наружу) — вызывающий код (`_suncDevices()`) этот `bool`
  **не проверяет вообще** (`await`, результат отброшен). Единственный
  способ, которым `remoteId`/актуальное состояние попадает в локальную
  таблицу — последующий `fetchDevicesFromApi()` + `clearAndInsertAll(remoteDevices)`
  (полная замена таблицы), и то только если ответ pull непуст.
- **Полная последовательность одного sync-прохода** (`DataUpdateBloc._suncDevices()`):
  `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` (правки, безусловно) →
  `fetchDevicesFromApi()` (pull №1) → если пуст: `syncDevicesOnSHTP()`
  (создание) → `fetchDevicesFromApi()` (pull №2) → если непуст:
  `clearAndInsertAll(remoteDevices)` (таблица заменяется целиком) →
  `ensureDeviceInDatabase()` (повторно, досеять недостающие дефолты после
  замены) → `ScannerService.applySavedTerminalSettings()`.
- **Не `@Clearable()`** — переживает логаут/`clearUserData()`, в отличие от
  [ENT-21](ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) (уведомления,
  `@Clearable`) — настройки устройств привязаны к физическому устройству
  приложения, не к аккаунту.
- **Часть изменений применяется «на лету» к реальному сканеру, не только в
  БД** — регион/мощность для `bluetooth_gates` (`ScannerService.tryApplyGatesBleRegion`/`tryApplyGatesBlePower`),
  действия кнопок TCD (`ScannerService.applyTerminalButtonActions()`).
- **`isDeviceConfiguredForScanning(type)`** — доменное правило готовности:
  для `bluetoothGates` нужны непустые антенны; для `rfidReader`/
  `rfidReaderGrpTcp`/`rfidReaderGrpBle` — антенны **и** непустой адрес
  (ip/mac); для остальных типов — всегда `true`.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `Devices`, `ScannerDeviceTypes`, `ScannerDeviceLocalIds`, `DeviceRegion`, `TcdAction`, `DeviceDto`, `DeviceCredentialsDto` | CURRENT | таблица, каталог типов/id, сетевые DTO |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `syncDevicesOnSHTP`, `updateDevicesOnSHTP`, `fetchDevicesFromApi`, `getSaved*`/`update*InStorage`, `isDeviceConfiguredForScanning` | CURRENT | весь CRUD + push/pull |
| `lib/repositories/devices_settings/scanner_device.dart` | `ScannerDevice` (sealed), `Device.toScannerDevice` | CURRENT | типизированная обёртка по типу устройства для UI |
| `lib/pages/scanner_settings/pages/devices_settings_page.dart` | `DevicesSettingsPage` | CURRENT | грид устройств |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `ScannerSettingsPage` | CURRENT | форма настроек одного/группы устройств |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация полного sync-прохода устройств |
