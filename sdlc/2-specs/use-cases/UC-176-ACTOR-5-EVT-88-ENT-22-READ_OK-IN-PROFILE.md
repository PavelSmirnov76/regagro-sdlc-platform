# UC-176 — Пользователь открывает настройки сканирующих устройств: грид всех устройств и форма одного/группы устройств загружаются успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь открывает «Настройки устройств» (`/profile/work_settings/devices_settings`,
грид всех сканирующих устройств) и, из грида, конкретное устройство или
группу bluetooth-устройств (`/profile/work_settings/devices_settings/scanner_settings`,
форма). В коде это два физически независимых экрана
(`DevicesSettingsPage`/`ScannerSettingsPage`), связанных только навигацией —
как и весь модуль `PROFILE` в целом.

Ключевая находка, подтверждённая чтением всех виджетов формы: они читают
начальное значение своего поля **двумя разными, несогласованными
способами**. Пять виджетов (`RegionSelectorWidget`, `SelectPowerSlider`,
`ScannerOperationsSettingsWidget`, `ScannerAntennasSettingsWidget`,
`ScannerAddressSettingsWidget`) независимо друг от друга и от грида
запускают свой собственный асинхронный `DeviceSettingsRepository.getSavedX(device.type)`
в `initState`, полностью игнорируя `settings`, уже вычисленный для того же
`Device` один раз в гриде (`getCurrentScannerDevices()` →
`.toScannerDevice()`) и переданный сюда через `ScannerSettingsPageArguments.device`.
Два других виджета (`IsUseCameraForQrCheckBoxWidget`, `TcdActionSelectorsWidget`,
оба — только для `tcd`) читают именно этот уже загруженный `widget.device.settings.*`
синхронно, без единого дополнительного запроса к БД. Один экран открытия
формы делает пять независимых новых чтений одной и той же таблицы `Devices`
(по одной строке каждое, `findDeviceByType`) вдобавок к чтению, уже
выполненному гридом секундами раньше.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость или авторизованный, без разницы: маршрут не имеет route-guard по
авторизации, как и весь [MOD-6](../modules/MOD-6-PROFILE.md).

## CURRENT

### Основной поток

1. Пользователь на `ProfilePage` нажимает `ProfileButton` с текстом
   `l10n.profile_settings__work_settings`
   (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`) →
   `context.pushNamed2(Routes.workSettings)` → `WorkSettingsPage`
   (`lib/pages/profile_settings/presentation/work_settings_page.dart`).
2. На `WorkSettingsPage` нажимает `WorkSettingsItem` с текстом
   `l10n.devices_settings` → `context.pushNamed2(Routes.devicesSettings)`.
   `Routes.devicesSettings` вложен под `Routes.workSettings` (сам — под
   `Routes.profile`) в `routes.dart` — итоговый путь
   `/profile/work_settings/devices_settings`.
3. `_DevicesSettingsPageState.initState`
   (`lib/pages/scanner_settings/pages/devices_settings_page.dart`):
   `_devicesFuture = _repository.getCurrentScannerDevices()`.
4. `DeviceSettingsRepository.getCurrentScannerDevices()` →
   `getCurrentDevices()`: сначала **безусловно** `await ensureDeviceInDatabase()`
   (идемпотентный upsert каталога из 13 типов — см.
   [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты»), затем
   `dao.getAllDevices()` (вся таблица `Devices`), затем для **каждого** из 13
   `defaultDevices` — в их фиксированном порядке объявления в
   `DeviceSettingsRepository.defaultDevices`, не в порядке хранения в БД —
   ищет первую строку с совпадающим `type` (`firstOrNull`), `whereType<Device>()`
   отбрасывает `null` (не находится ни разу при исправной БД, т.к.
   `ensureDeviceInDatabase()` только что это гарантировал). Возвращает
   `List<Device>` длиной ≤13, строго в порядке `defaultDevices`.
5. `getCurrentScannerDevices()` мапит каждый `Device` через
   `ScannerDeviceMapper.toScannerDevice()` (`lib/repositories/devices_settings/scanner_device.dart`)
   в типизированный `sealed ScannerDevice` — конкретный подкласс
   (`UhfStickScannerDevice`/`TerminalScannerDevice`/`RfidTcpScannerDevice`/
   `BluetoothGatesScannerDevice`/`RfidGrpTcpScannerDevice`/`RfidGrpBleScannerDevice`/
   `A7ScannerDevice`) выбирается по `type` через `switch`, неся уже
   загруженный `settings`-объект со всеми полями, специфичными для этого
   типа.
6. `FutureBuilder<List<ScannerDevice>>` пересобирается:
   `snapshot.hasData` истинно → `_buildGridModels(context, snapshot.data!)`
   вызывает `_isBluetoothGroupDevice` (`device is A7ScannerDevice || device is
   UhfStickScannerDevice`) для каждого устройства: все совпавшие собираются
   отдельно (`groupDevices`), остальные получают собственную плитку
   (`title: device.name`, `image: Assets.getDeviceAvatarByName(device.name)`).
   Если среди устройств встречается `TerminalScannerDevice` и `groupDevices`
   непуст — общая плитка «Bluetooth» (`l10n.bluetooth_devices`, картинка
   `RA-9500UHF`) вставляется сразу после плитки терминала; иначе, если
   `groupDevices` непуст, — вставляется первой (`insert(0, …)`).
7. `DevicesGrid` (`lib/pages/scanner_settings/widgets/devices_grid.dart`)
   рендерит `GridView.builder` в 2 колонки, по `DeviceItem` на плитку.
8. Пользователь нажимает плитку конкретного устройства → `context.pushNamed2(
   Routes.scannerSettings, extra: ScannerSettingsPageArguments(device:
   device))`; нажимает плитку «Bluetooth» → `ScannerSettingsPageArguments(
   device: groupDevices.first, groupDevices: groupDevices, groupTitle:
   l10n.bluetooth_devices)`. `Routes.scannerSettings` вложен под
   `Routes.devicesSettings` — итоговый путь
   `/profile/work_settings/devices_settings/scanner_settings`.
9. `_ScannerSettingsPageState.build`
   (`lib/pages/scanner_settings/pages/scanner_settings_page.dart`) читает
   аргументы через `GoRouterState.of(context).tryGetExtraByName`. Заголовок —
   `arguments.groupTitle`, если задан, иначе
   `_nameLocalization(context, device.name)` (спецкейсы: `'tcd'` →
   `l10n.terminal`, `'Стационарный считыватель'` → `l10n.stationary_reader`,
   иначе — сырое `name` без перевода).
10. Если открыта группа (`groupDevices != null`) — рендерится
    `_GroupOperationsContent`: единственное содержимое —
    `ScannerOperationsSettingsWidget(device: device, applyToTypes:
    groupDevices.map((d) => d.type).toList())`, где `device` — это
    `groupDevices.first` (шаг 8), а не какой-то отдельный «групповой»
    объект. Иначе — рендерится `ScannerSettingsContent`
    (`lib/pages/scanner_settings/widgets/scanner_settings_views.dart`):
    `switch (device)` по конкретному подтипу `ScannerDevice` выбирает набор
    полей (`TcdScannerSettingsView`/`BluetoothGatesScannerSettingsView`/
    `RfidTcpScannerSettingsView`/`RfidGrpTcpScannerSettingsView`/
    `RfidGrpBleScannerSettingsView`/`A7ScannerSettingsView`/
    `UhfStickScannerSettingsView`, набор полей на каждый тип — см.
    [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Поля»).
11. Каждый виджет внутри выбранного набора полей загружает своё начальное
    значение независимо, одним из двух способов:
    - **Асинхронный, игнорирующий уже переданный `settings`** —
      `ScannerOperationsSettingsWidget._loadSettings` →
      `getEnabledOperationTypes(device.type)`; `RegionSelectorWidget.initSettings`
      → `getSavedRegion(device.type)`; `SelectPowerSlider.initSettings` →
      `getSavedPower(device.type)`; `ScannerAntennasSettingsWidget._loadAntennas`
      → `getSavedAntennas(device.type)`; `ScannerAddressSettingsWidget._loadAddress`
      → `getSavedAddress(device.type)`. Каждый — отдельный `findDeviceByType`
      (по `type`, не по `id`) внутри `DeviceSettingsRepository`, отдельная
      строка `Devices`, полностью независимо от того, что тот же `Device`
      уже был прочитан на шаге 4 и превращён в `settings` на шаге 5.
    - **Синхронный, из уже переданного `settings`** —
      `IsUseCameraForQrCheckBoxWidget.initState` читает
      `widget.device.settings.isUseCameraForQr` напрямую;
      `TcdActionSelectorsWidget.initState` читает
      `widget.device.settings.leftButtonAction`/`.middleButtonAction`/`.rightButtonAction`
      напрямую. Ни один запрос к `DeviceSettingsRepository` для этих двух
      полей не выполняется при открытии формы.
12. Пользователь возвращается назад (кнопка «Сохранить» либо системный
    back) — `DevicesSettingsPage._deviceModel`/`_bluetoothGroupModel`'s
    `onTap` содержит `await context.pushNamed2(...); _refreshDevices();`:
    после закрытия формы грид **безусловно** перезапускает шаг 3
    (`_repository.getCurrentScannerDevices()` заново, включая повторный
    `ensureDeviceInDatabase()`), независимо от того, было ли что-то реально
    изменено на форме.

### Альтернативные потоки

- **Группировка bluetooth-устройств продублирована как отдельная, менее
  строгая проверка типа, а не переиспользует существующий справочник
  типов.** `ScannerDeviceTypes.bluetoothGroup`
  (`packages/sheep_farm_database/lib/entities/devices/devices.dart`) — уже
  существующий список из тех же 9 строковых типов (8 UHF-стик + `a7Bluetooth`),
  реально используемый в другом месте приложения
  (`lib/pages/scanning/scanning_bloc.dart`). `DevicesSettingsPage._isBluetoothGroupDevice`
  не читает этот список вовсе — переопределяет то же самое множество через
  `device is A7ScannerDevice || device is UhfStickScannerDevice`
  (структурное сравнение по typed-подклассу, вычисленному
  `ScannerDeviceMapper.toScannerDevice()` на основе того же поля `type`).
  Оба определения сегодня описывают одно и то же множество, но независимо,
  без единого источника истины — расхождение возможно при добавлении новых
  типов в будущем (обновили один список — забыли другой).
- **Порядок плиток в гриде — фиксированный порядок объявления
  `defaultDevices`, не порядок хранения в БД.** `getCurrentDevices()` строит
  результат, перебирая `defaultDevices` (константный список, `RA-100BT` →
  … → `RFID-04`) и подставляя найденную строку — физический порядок строк
  внутри таблицы `Devices` (`dao.getAllDevices()`) не влияет на порядок
  плиток.
- **Групповая форма отражает сохранённые операции только первого устройства
  группы, не сводный/единый статус по всей группе.** `groupDevices.first`
  (шаг 8) — единственный источник начального значения `ScannerOperationsSettingsWidget`
  внутри `_GroupOperationsContent`, хотя переключение операции применяется
  сразу ко всем типам группы (`applyToTypes`). Если у отдельных устройств
  группы ранее были сохранены разные наборы включённых операций — форма
  покажет только состояние первого, не предупреждая о расхождении.
- **Ни грид, ни ни один из пяти «асинхронных» виджетов формы не проверяют
  ошибку явно, и ведут себя по-разному при отказе.** `FutureBuilder` в
  `DevicesSettingsPage.build` проверяет только `!snapshot.hasData` — если
  `_repository.getCurrentScannerDevices()` (а значит и вложенный
  `ensureDeviceInDatabase()`/любой Drift-вызов внутри него) бросает
  исключение, `snapshot.hasData` остаётся `false` даже после того, как
  `Future` завершился с ошибкой (`connectionState == done`), и экран
  показывает `CircularProgressIndicator()` бессрочно, без какого-либо
  текста ошибки. На форме та же немая деградация неоднородна по виджетам:
  `SelectPowerSlider`, `ScannerAntennasSettingsWidget`,
  `ScannerOperationsSettingsWidget` каждый содержит явную проверку
  `if (_currentValue/_antennas/_enabledOperationTypes == null) return
  const Center(child: CircularProgressIndicator());` — те же бессрочные
  спиннеры при отказе своего собственного независимого запроса;
  `RegionSelectorWidget` вместо этого молча деградирует к первому значению
  `DeviceRegion.cn920_925` (`_getDeviceRegion` трактует `null` как «вне
  диапазона»); `ScannerAddressSettingsWidget` молча оставляет поле пустым
  (`_controller.text` никогда не устанавливается, если `_loadAddress()`
  бросает исключение до `setState`). Ни один из этих путей не является
  `READ_ERROR`, специфицированным этим файлом — он документирует только
  `READ_OK`; см. «Открытые вопросы».

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность этого сценария: читается многократно (один раз гридом на
  устройство, затем ещё до пяти раз формой на каждое открытое устройство),
  не изменяется — весь сценарий этого файла ограничен просмотром.

### Бизнес-правила

- Каталог из 13 устройств не создаётся пользователем — «Настройки
  устройств» всегда показывают ровно те типы, что описаны
  `DeviceSettingsRepository.defaultDevices`/`ScannerDeviceTypes.defaults`
  (см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты»),
  никогда меньше и никогда больше — пользователь не может ни добавить, ни
  удалить плитку.
- Набор полей, показываемых формой, определяется исключительно типом
  устройства (какой `switch`-кейс `ScannerSettingsContent`/`toScannerDevice()`
  сработал), не каким-либо явным флагом конфигурации.
- Кнопка «Сохранить» физически присутствует на этом экране
  (`ScannerSettingsPage._save`), но запись изменений — отдельное событие
  ([EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)), вне
  границ этого use-case; сам просмотр формы не блокируется отсутствием
  выбранных антенн — валидация (`_isAntennasRequired` + проверка
  непустых антенн) выполняется только внутри `_save`, не при открытии
  экрана, т.е. открыть и просто посмотреть форму устройства без единой
  выбранной антенны — полностью нормальное, ничем не блокируемое
  состояние `READ_OK`.
- Экран не выполняет ни push, ни pull к серверу — весь просмотр строго
  локальный (Drift); синхронизация настроек устройств —
  [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)/[EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)/[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
  выполняется только как часть отдельного sync-прохода
  ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)), не при открытии этих
  экранов.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной поток (грид → форма
одного/группы устройств) полностью реализован и достижим с единственной
точки входа (`ProfilePage` → «Настройки работы» → «Настройки устройств»).
Найденные структурные особенности (дублирующаяся логика группировки,
несогласованный способ загрузки полей формы — часть синхронно из уже
переданного объекта, часть асинхронно повторным запросом к БД,
неоднородная немая деградация при отказе) зафиксированы как факт CURRENT,
не как блокеры — это документирующий проход, не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` (`l10n.profile_settings__work_settings`) | CURRENT | точка входа — переход на `Routes.workSettings` |
| `lib/pages/profile_settings/presentation/work_settings_page.dart` | `WorkSettingsPage`, `WorkSettingsItem` | CURRENT | второй шаг маршрута — переход на `Routes.devicesSettings` |
| `lib/pages/routes.dart` | `Routes.profile`, `.workSettings`, `.devicesSettings`, `.scannerSettings` | CURRENT | вложенность маршрута — итоговые пути `/profile/work_settings/devices_settings` и `.../scanner_settings` |
| `lib/pages/scanner_settings/pages/devices_settings_page.dart` | `DevicesSettingsPage`, `_isBluetoothGroupDevice`, `_buildGridModels`, `_deviceModel`, `_bluetoothGroupModel`, `_refreshDevices` | CURRENT | грид; коллапс bluetooth-типов в одну плитку; безусловный рефреш после возврата с формы |
| `lib/pages/scanner_settings/data/devices_grid_model.dart` | `DevicesGridModel` | CURRENT | модель плитки грида |
| `lib/pages/scanner_settings/widgets/devices_grid.dart` | `DevicesGrid`, `DeviceItem` | CURRENT | 2-колоночный `GridView.builder` |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `ScannerSettingsPage`, `ScannerSettingsPageArguments`, `_nameLocalization`, `_GroupOperationsContent`, `_isAntennasRequired`, `_save` | CURRENT | форма одного/группы устройств; заголовок; `_save`/`_isAntennasRequired` — вне границ этого файла ([EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)) |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `ScannerSettingsContent`, `TcdScannerSettingsView`, `BluetoothGatesScannerSettingsView`, `RfidTcpScannerSettingsView`, `RfidGrpTcpScannerSettingsView`, `RfidGrpBleScannerSettingsView`, `A7ScannerSettingsView`, `UhfStickScannerSettingsView`, `ScannerAddressSettingsWidget`, `ScannerAntennasSettingsWidget` | CURRENT | набор полей по типу устройства; `ScannerAddressSettingsWidget`/`ScannerAntennasSettingsWidget` — независимая асинхронная загрузка своего поля |
| `lib/pages/scanner_settings/widgets/region_selector_widget.dart` | `RegionSelectorWidget.initSettings` | CURRENT | независимая асинхронная загрузка `getSavedRegion`; молча деградирует к `DeviceRegion.cn920_925` при `null`/отказе |
| `lib/pages/scanner_settings/widgets/select_power_slider.dart` | `SelectPowerSlider.initSettings` | CURRENT | независимая асинхронная загрузка `getSavedPower`; бессрочный спиннер при отказе (`_currentValue == null`) |
| `lib/pages/scanner_settings/widgets/scanner_operations_settings_widget.dart` | `ScannerOperationsSettingsWidget._loadSettings` | CURRENT | независимая асинхронная загрузка `getEnabledOperationTypes`; используется и одиночной, и групповой формой; бессрочный спиннер при отказе |
| `lib/pages/scanner_settings/widgets/is_use_camera_for_qr_check_box_widget.dart` | `IsUseCameraForQrCheckBoxWidget.initState` | CURRENT | читает `widget.device.settings.isUseCameraForQr` синхронно, без запроса к репозиторию |
| `lib/pages/scanner_settings/widgets/tcd_action_selectors_widget.dart` | `TcdActionSelectorsWidget.initState` | CURRENT | читает `widget.device.settings.leftButtonAction`/`.middleButtonAction`/`.rightButtonAction` синхронно, без запроса к репозиторию |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.getCurrentScannerDevices`, `.getCurrentDevices`, `.ensureDeviceInDatabase`, `.defaultDevices`, `.getEnabledOperationTypes`, `.getSavedRegion`, `.getSavedPower`, `.getSavedAntennas`, `.getSavedAddress` | CURRENT | весь набор чтений этого сценария — грид (один проход) и форма (до пяти независимых по-полевых запросов) |
| `lib/repositories/devices_settings/scanner_device.dart` | `ScannerDevice` (sealed), `ScannerDeviceMapper.toScannerDevice`, `TerminalScannerSettings`, `RfidTcpScannerSettings`, `BluetoothGatesScannerSettings`, `RfidGrpTcpScannerSettings`, `RfidGrpBleScannerSettings`, `A7ScannerSettings`, `UhfStickScannerSettings` | CURRENT | типизированная обёртка; носитель `settings`, который пять виджетов формы игнорируют, а два — используют |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.bluetoothGroup`, `.defaults` | CURRENT | существующий справочник группировки/каталога, не переиспользованный `_isBluetoothGroupDevice` |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao.getAllDevices`, `.findDeviceByType` | CURRENT | физические запросы к таблице `Devices` — один раз (грид) и по одному на поле (форма) |
| `lib/constants.dart` | `Assets.getDeviceAvatarByName` | CURRENT | резолв картинки плитки по имени устройства |
| `lib/l10n/app_localizations.dart` (сгенерированный из `app_en.arb`) | `devices_settings`, `bluetooth_devices`, `terminal`, `stationary_reader` | CURRENT | тексты заголовков грида/формы |

## Критерии приёмки

- Открытие `/profile/work_settings/devices_settings` вызывает
  `DeviceSettingsRepository.getCurrentScannerDevices()` ровно один раз при
  первом построении страницы (`initState`); грид показывает ровно одну
  плитку на каждый несгруппированный тип и ровно одну общую плитку
  «Bluetooth» на все устройства, для которых `_isBluetoothGroupDevice`
  истинно (если таких хотя бы одно).
- Открытие конкретной плитки передаёт в `ScannerSettingsPage` уже
  загруженный `ScannerDevice` (без повторного запроса на уровне самой
  страницы) и рендерит набор полей, соответствующий подтипу `ScannerDevice`
  этого устройства (см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)).
- Каждый из пяти полей — операции, регион, мощность, антенны, адрес —
  инициализируется собственным независимым асинхронным запросом
  `DeviceSettingsRepository.getSavedX(device.type)`, а не значением уже
  переданного `device.settings`; поля «использовать камеру для QR» и три
  действия кнопок TCD инициализируются, наоборот, синхронно из
  `device.settings`, без запроса к репозиторию.
- Открытие групповой плитки «Bluetooth» рендерит только
  `ScannerOperationsSettingsWidget` (без региона/мощности/адреса/антенн),
  с начальным состоянием, загруженным для `groupDevices.first.type`, и
  `applyToTypes`, равным типам всех устройств группы.
- Возврат с формы (любым способом) безусловно вызывает
  `_refreshDevices()` на гриде, независимо от того, было ли реально
  сохранено какое-либо изменение.
- Ни открытие грида, ни открытие формы не выполняют ни одного сетевого
  вызова — оба экрана читают исключительно локальную таблицу `Devices`.

## Связанные тесты

`find test -iname "*device*" -o -iname "*scanner*"` (после исключения
`test/blocs/data_update_bloc_test.dart` и `test/pages/scanning_bloc_test.dart`,
где `DeviceSettingsRepository` фигурирует только как мок-зависимость
других сценариев — sync устройств и сканирование, не открытие этого
экрана) не находит ни одного файла, посвящённого
`DevicesSettingsPage`/`ScannerSettingsPage`/чтениям
`DeviceSettingsRepository.getCurrentScannerDevices`/`getCurrentDevices`/`getSavedRegion`/`getSavedPower`/`getSavedAntennas`/`getSavedAddress`/`getEnabledOperationTypes`
в контексте этого экрана. Ни `getCurrentScannerDevices`, ни
`getScannerDeviceByType`, ни любой из виджетов
`lib/pages/scanner_settings/` не упоминаются ни в одном файле `test/`.

**TBD — теста нет.** Ни на сам грид, ни на коллапс bluetooth-устройств в
одну плитку, ни на выбор набора полей формы по типу устройства, ни на
найденную несогласованность способов загрузки (синхронно из `settings`
против пяти независимых асинхронных запросов), ни на безусловный
`_refreshDevices()` после возврата, ни на отсутствие проверки
`snapshot.hasError` в `DevicesSettingsPage` — не существует ни одного
unit- или widget-теста (`test/` не содержит файла ни для
`devices_settings_page`, ни для `scanner_settings_page`, ни отдельного
`devices_settings_repository_test.dart`).

## Открытые вопросы и ограничения

- **Пять полей формы читаются заново из БД, хотя те же значения уже были
  загружены гридом секундами раньше и переданы в аргументах навигации —
  намеренная защита от рассинхронизации (settings могли устареть, пока
  пользователь листал грид) или недосмотр (два разных разработчика писали
  разные виджеты независимо)?** Ничем в коде/комментариях не
  зафиксировано. Два других поля (камера для QR, действия кнопок TCD)
  решают тот же вопрос ровно противоположным способом в том же файле того
  же экрана.
- **Дублирующееся определение множества bluetooth-типов
  (`ScannerDeviceTypes.bluetoothGroup` против
  `_isBluetoothGroupDevice`).** Оба описывают сегодня одно и то же
  множество (9 типов), но независимо — нет теста или assert'а,
  гарантирующего, что они не разойдутся при добавлении нового типа
  устройства в будущем.
- **`FutureBuilder` в `DevicesSettingsPage` не проверяет `snapshot.hasError`
  — структурно возможный `READ_ERROR` для этого же события, не
  специфицированный этим файлом.** Если `getCurrentScannerDevices()`
  (а значит, и вложенный `ensureDeviceInDatabase()`) бросит исключение,
  пользователь увидит бессрочный `CircularProgressIndicator()` без
  единого признака ошибки — не подтверждено ни одним тестом, выведено
  статическим чтением `builder` внутри `FutureBuilder`.
- **Три разных, ничем не согласованных исхода отказа пяти «асинхронных»
  виджетов формы на одном экране** (бессрочный спиннер у
  `SelectPowerSlider`/`ScannerAntennasSettingsWidget`/`ScannerOperationsSettingsWidget`;
  молчаливая деградация к дефолтному региону у `RegionSelectorWidget`;
  молчаливое пустое поле у `ScannerAddressSettingsWidget`) — не решено
  этим файлом, было ли это осознанным выбором каждого автора виджета по
  отдельности.
- **Групповая форма показывает состояние операций только первого
  устройства группы**, не сводное/предупреждающее о возможном расхождении
  между устройствами внутри `groupDevices` — не зафиксировано нигде как
  сознательное упрощение.
- Не проверено эмпирически на реальном устройстве (в частности —
  фактическая относительная скорость пяти параллельных запросов
  `findDeviceByType` формы против одного отрисованного кадра, и поведение
  при реально медленной локальной БД) — вывод сделан статическим чтением
  кода, без запущенного widget-теста, монтирующего
  `DevicesSettingsPage`/`ScannerSettingsPage` целиком.
