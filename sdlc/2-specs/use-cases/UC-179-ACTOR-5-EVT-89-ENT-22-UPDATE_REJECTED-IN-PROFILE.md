# UC-179 — Закрытие формы настроек устройства с антеннами отклоняется без выбранных антенн: проверка есть только в кнопке «Сохранить», системный back её обходит

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `UPDATE_REJECTED` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же триггер, что описан в [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) —
пользователь на `ScannerSettingsPage` меняет настройки одного сканирующего
устройства и нажимает «Сохранить» (`_save`). Здесь описана ветка, где
устройство относится к одному из четырёх типов, требующих антенны
(`bluetooth_gates`, `rfid_reader`, `rfid_reader_grp_tcp`,
`rfid_reader_grp_ble`), а на момент нажатия ни одна антенна не выбрана:
`_save` осознанно отклоняет закрытие формы бизнес-правилом, показывает
снекбар `must_select_antenns` и не вызывает `context.pop()` — экран
остаётся открытым. Это `REJECTED`, а не `ERROR`: ни сеть, ни исключение
здесь не участвуют, отказ — чистое in-memory условие внутри `_save`.

Задокументированы также независимо проверенные особенности этой же ветки:
отказ блокирует только сам выход с экрана, а не запись данных — все
остальные поля (регион, мощность, операции, а для части типов ещё и
адрес) уже записаны в `Devices` до нажатия «Сохранить», отказ их не
откатывает; и что тот же метод `updateAntennasInStorage`, которым
записывается сама антенна, не выставляет `isNeedUpdate`/`updatedAt` — то
есть даже после того, как пользователь устранит причину отказа (выберет
хотя бы одну антенну) и `_save` завершится успешно, эта конкретная правка
может не попасть в следующий push-sync устройств (см. «Открытые вопросы»).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость и авторизованный проходят один и тот же код; весь модуль
[MOD-6](../modules/MOD-6-PROFILE.md), включая этот экран, открывается без
route-guard по авторизации). Точка входа: `ProfilePage` → «Настройки
работы» (`WorkSettingsPage`, `Routes.workSettings`) → «Настройки устройств»
(`DevicesSettingsPage`, `Routes.devicesSettings`) → плитка конкретного
устройства → `ScannerSettingsPage` (`Routes.scannerSettings`, итоговый путь
`/profile/work_settings/devices_settings/scanner_settings`,
`lib/pages/routes.dart`).

## CURRENT

### Основной поток

Показан на `bluetooth_gates` (плитка «SMART-GATE bluetooth») — единственный
из четырёх антенно-зависимых типов, чья форма
(`BluetoothGatesScannerSettingsView`, `lib/pages/scanner_settings/widgets/scanner_settings_views.dart`)
не содержит ни одного `TextFormField`/`validator`, поэтому здесь проверка
антенн — единственный гейт, без наложения на валидацию формы (см.
«Альтернативные потоки» для типов с адресным полем).

1. Пользователь открывает плитку «SMART-GATE bluetooth» на
   `DevicesSettingsPage` (`_deviceModel.onTap`) →
   `context.pushNamed2(Routes.scannerSettings, extra:
   ScannerSettingsPageArguments(device: device))`, `groupDevices == null` —
   одиночный, не групповой, флоу.
2. `ScannerSettingsPage.build` рендерит `ScannerSettingsContent` →
   `BluetoothGatesScannerSettingsView` внутри `Form(key: _formKey, ...)`:
   `ScannerOperationsSettingsWidget`, `RegionSelectorWidget`,
   `SelectPowerSlider`, `ScannerAntennasSettingsWidget`. У свежезаведённого
   (только что засеянного `ensureDeviceInDatabase()`) устройства этого типа
   `antennas == null` в БД — ни один из 13 `defaultDevices`
   (`DeviceSettingsRepository.defaultDevices`) не задаёт `antennas` явно,
   поэтому `getSavedAntennas('bluetooth_gates')` при первом открытии формы
   возвращает пустое множество (`device?.antennas ?? const {}`).
3. Пользователь может менять регион/мощность/операции — каждое изменение
   пишется в `Devices` немедленно, в момент взаимодействия с виджетом (не
   при нажатии «Сохранить»): `RegionSelectorWidget.onChanged` →
   `updateRegionInDatabase`, `SelectPowerSlider` → `updatePowerInDatabase`,
   `ScannerOperationsSettingsWidget` → `updateDeviceOperationUsage`. Ни один
   из этих вызовов не трогает антенны.
4. Пользователь **не** отмечает ни один чекбокс «Антенна 1»…«Антенна 4»
   (`ScannerAntennasSettingsWidget`, `CustomRadioButton` на каждый из 4)
   и нажимает `BlackCircleButton` «Сохранить» → `onTap: () => _save(context,
   device)`.
5. `_save` вызывает `_formKey.currentState?.validate() ?? true` — для этой
   формы (без единого `TextFormField`) результат всегда `true`, выполнение
   продолжается.
6. `_isAntennasRequired(device)` — `device is BluetoothGatesScannerDevice`
   → `true`. `await _repository.getSavedAntennas(device.type)` читает
   актуальное состояние `Devices.antennas` для `'bluetooth_gates'` — пусто.
   Условие `(...).isEmpty` истинно.
7. `_save` вызывает `showAppSnackBarError(context,
   context.tr('must_select_antenns'))` (красноватый фон
   `AppColors.snackbarErrorBackground`, чёрный текст — см. «Открытые
   вопросы» о расхождении с описанием error-снекбара в
   `.claude/rules/ui-architecture.md`) и **`return`** сразу после — строка
   `context.pop()` (шаг 8 счастливого пути) не выполняется.
8. `ScannerSettingsPage` остаётся открытой — регион/мощность/операции,
   изменённые на шаге 3, остаются записанными в `Devices` (отказ их не
   откатывает, откатывать нечего — это уже свершившиеся, независимые от
   `_save` записи); антенны по-прежнему пусты. Пользователь может отметить
   хотя бы одну антенну (`_toggleAntenna` → `updateAntennasInStorage`,
   немедленная запись) и повторно нажать «Сохранить» — тогда шаг 6 условие
   ложно, `_save` вызывает `context.pop()`; это отдельный, успешный
   сценарий (`UPDATE_OK`), не описываемый этим use-case.

### Альтернативные потоки

- **Типы с обязательным адресным полем (`rfid_reader`, `rfid_reader_grp_ble`)
  — форма проверяется раньше, независимым гейтом.**
  `RfidTcpScannerSettingsView`/`RfidGrpBleScannerSettingsView` дополнительно
  рендерят `ScannerAddressSettingsWidget` — `RTextField.outline` с
  `validator: (value) => value == null || value.trim().isEmpty ?
  AppLocalizations.of(context)!.field_required : null`, это настоящий
  `TextFormField` внутри того же `Form(key: _formKey)`. У обоих этих типов
  ни один `DefaultScannerDevice` не задаёт `ip`/`mac` по умолчанию
  (`ScannerDeviceLocalIds.rfidReader`/`.rfidReaderGrpBle` в
  `DeviceSettingsRepository.defaultDevices` — оба без `ip:`/`mac:`), поэтому
  у свежезаведённого устройства поле изначально пусто. Если пользователь
  его не заполнил, `_formKey.currentState?.validate()` на шаге 5
  возвращает `false` — `_save` делает `return` **до** проверки антенн
  (шаг 6 никогда не выполняется в этом случае): показывается только
  инлайн-текст `field_required` под полем (стандартное поведение
  `Form`/`TextFormField`), снекбар `must_select_antenns` не появляется
  вовсе, даже если антенны тоже не выбраны.
- **`rfid_reader_grp_tcp` (RFID-04) — адрес предзаполнен, ведёт себя как
  `bluetooth_gates`.** Единственный из четырёх антенно-зависимых типов, чей
  `DefaultScannerDevice` (`ScannerDeviceLocalIds.rfidReaderGrpTcp`) явно
  задаёт `ip: '192.168.1.201'` — значит форма (`RfidGrpTcpScannerSettingsView`)
  проходит валидацию адреса без участия пользователя, и антенный гейт
  (шаги 5-7 основного потока) — единственная реальная преграда, как и для
  `bluetooth_gates`.
- **Групповой (bluetooth) флоу — эта ветка структурно недостижима.**
  `_bluetoothGroupModel.onTap` открывает `ScannerSettingsPage` с
  `groupDevices` = только `A7ScannerDevice`/`UhfStickScannerDevice`
  (`DevicesSettingsPage._isBluetoothGroupDevice`); `_save` вызывается с тем
  же `device` — `groupDevices.first` (`ScannerSettingsPageArguments.device`,
  выставленный в `_bluetoothGroupModel`). `_isAntennasRequired` для обоих
  этих типов — всегда `false` (проверяет только
  `BluetoothGatesScannerDevice`/`RfidTcpScannerDevice`/
  `RfidGrpTcpScannerDevice`/`RfidGrpBleScannerDevice`, ни один из которых не
  входит в группу). Групповая форма (`_GroupOperationsContent`, только
  `ScannerOperationsSettingsWidget`) не показывает поле антенн вовсе — этот
  `UPDATE_REJECTED` невозможен ни для одной групповой плитки.
- **Системный/AppBar back обходит проверку целиком, для любого типа.**
  `CustomAppBar` (`lib/widgets/app_bar/custom_app_bar.dart`) строится как
  обычный `AppBar` без `leading`/`automaticallyImplyLeading: false` — при
  наличии предыдущего маршрута Flutter сам добавляет кнопку «назад»,
  вызывающую `Navigator.maybePop()`; ни `PopScope`, ни `WillPopScope` в
  `ScannerSettingsPage`/`ScannerSettingsContent` не объявлены. Значит,
  нажатие этой автоматической кнопки (или системный жест/кнопка back на
  Android) закрывает форму безусловно, минуя `_save`,
  `_isAntennasRequired` и любую другую проверку — антенны могут остаться
  пустыми, и это никак не помешает выйти с экрана этим путём. Единственный
  путь, где `must_select_antenns`-отказ вообще срабатывает, — явное
  нажатие кнопки «Сохранить».

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность сценария. `antennas` — поле, из-за пустоты которого отказ
  наступает; не изменяется самим отказом (`_save` не пишет ничего на этой
  ветке). Поля `region`/`power`/`availableOperations`/`ip`/`mac`,
  изменённые до нажатия «Сохранить» через отдельные виджеты формы, уже
  записаны в ту же строку `Devices` независимо от исхода `_save` — отказ
  их не касается.

### Бизнес-правила

- **Для типов `bluetooth_gates`, `rfid_reader`, `rfid_reader_grp_tcp`,
  `rfid_reader_grp_ble` — непустой набор антенн обязателен для закрытия
  формы через «Сохранить».** Условие — `_isAntennasRequired(device) &&
  (await _repository.getSavedAntennas(device.type)).isEmpty`
  (`ScannerSettingsPage._save`); для всех остальных типов (`tcd`,
  `a7Bluetooth`, восемь `*bt`/`*lf`/`*uhf`-типов из `UhfStickScannerDevice`)
  условие всегда ложно — антенны у них не проверяются и не показываются в
  форме вовсе.
- **Отказ — осознанное решение кода `_save` по чистому in-memory условию,
  не техническая ошибка.** Ни сеть, ни исключение здесь не участвуют —
  `REJECTED`, не `ERROR`.
- **Отказ блокирует только `context.pop()`, не запись данных.** Все поля,
  кроме самих антенн, уже персистентны в `Devices` к моменту вызова `_save`
  (виджеты формы пишут в БД по одному, в момент взаимодействия — см.
  [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)) —
  «Сохранить» здесь не собирает и не фиксирует изменения формы разом, а
  лишь решает, разрешить ли пользователю покинуть уже применённое
  состояние через этот конкретный путь.
- **Проверка выполняется ровно один раз, только внутри `_save`, не при
  открытии/в процессе редактирования формы.** Отмечено уже в
  [UC-176](UC-176-ACTOR-5-EVT-88-ENT-22-READ_OK-IN-PROFILE.md) для чтения:
  сам просмотр/переключение антенн ничем не блокируется; кнопка
  «Сохранить» не дизейблится заранее при пустых антеннах.
- **То же доменное правило готовности к сканированию проверяется отдельно,
  в другом контексте.** `DeviceSettingsRepository.isDeviceConfiguredForScanning`
  (см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты»)
  использует условие «антенны непусты» (плюс для трёх RFID-типов ещё и
  непустой адрес) как признак «устройство готово к сканированию» — вызывается
  из `ScanningBloc`/`WEIGH`/`REG`/`INV`, не из `ScannerSettingsPage._save`;
  два независимых места кода проверяют структурно то же самое условие по
  антеннам, не переиспользуя друг друга напрямую (`_isAntennasRequired` в
  `ScannerSettingsPage` — свой собственный `switch`/`is`-список типов,
  отдельный от `switch` внутри `isDeviceConfiguredForScanning`).

## TARGET

TARGET не отличается от CURRENT — бизнес-правило «антенны обязательны для
этих четырёх типов» уже реализовано так, как описано в CURRENT, и не
меняется этим документирующим проходом. Обнаруженные тут же особенности
(обход проверки через back, не-персистентность `isNeedUpdate` при самой
записи антенн) — не исправляются в рамках этой спеки, см. «Открытые
вопросы».

## TBD / BLOCKED

Блокеров для документирования нет — весь сценарий, включая независимо
проверенные альтернативные ветки (адресный гейт, групповой флоу, обход
через back), прослеживается статическим чтением кода:
`scanner_settings_page.dart` → `scanner_device.dart` →
`devices_settings_repository.dart` → `scanner_settings_views.dart` →
`custom_app_bar.dart`. Не подтверждено ни одним тестом — см. «Связанные
тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_ScannerSettingsPageState._save` | CURRENT | `_formKey.currentState?.validate()`, затем `_isAntennasRequired(device) && (await getSavedAntennas(device.type)).isEmpty` → `showAppSnackBarError('must_select_antenns')` + `return`, без `context.pop()` |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_ScannerSettingsPageState._isAntennasRequired` | CURRENT | `device is BluetoothGatesScannerDevice \|\| device is RfidTcpScannerDevice \|\| device is RfidGrpTcpScannerDevice \|\| device is RfidGrpBleScannerDevice` — закрытый список из 4 типов |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_GroupOperationsContent` | CURRENT | групповой (bluetooth) флоу — `device` всегда `groupDevices.first`, всегда `A7ScannerDevice`/`UhfStickScannerDevice`, `_isAntennasRequired` для него всегда `false` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.getSavedAntennas` | CURRENT | читает `Devices.antennas` заново на момент вызова `_save`, не кэш формы |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateAntennasInStorage` | CURRENT | пишет `antennas` немедленно при переключении чекбокса; **не** выставляет `isNeedUpdate`/`updatedAt` (расхождение с описанием в [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md), см. «Открытые вопросы») |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateAddressInStorage`, `.updateDeviceOperationUsage` | CURRENT | тот же паттерн — пишут `ip`/`mac`/`availableOperations` немедленно, тоже не выставляют `isNeedUpdate`/`updatedAt` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updatePowerInDatabase`, `.updateRegionInDatabase`, `.updateIsUseCameraForQrInDatabase`, `.updateDeviceButtonAction` | CURRENT | контраст — эти четыре метода выставляют `isNeedUpdate: true`/`updatedAt: now()` при записи |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.defaultDevices` | CURRENT | ни один из 13 элементов не задаёт `antennas`; только `rfidReaderGrpTcp` задаёт `ip` по умолчанию — источник различия между альтернативными ветками |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.isDeviceConfiguredForScanning` | CURRENT | то же условие «антенны непусты» в другом контексте (готовность к сканированию для WEIGH/REG/INV), не вызывается из `_save` |
| `lib/repositories/devices_settings/scanner_device.dart` | `BluetoothGatesScannerDevice`, `RfidTcpScannerDevice`, `RfidGrpTcpScannerDevice`, `RfidGrpBleScannerDevice`, `ScannerDeviceMapper.toScannerDevice` | CURRENT | типы, которые `_isAntennasRequired` распознаёт по `is`-проверке; сопоставление `type` → подкласс |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `ScannerAntennasSettingsWidget._toggleAntenna` | CURRENT | немедленная запись выбора антенны, читаемая `_save` на шаге 6 |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `ScannerAddressSettingsWidget` (`RTextField.outline`, `validator`) | CURRENT | независимый, более ранний гейт формы для `rfid_reader`/`rfid_reader_grp_ble` — блокирует `_save` до проверки антенн |
| `lib/pages/scanner_settings/pages/devices_settings_page.dart` | `_deviceModel`, `_bluetoothGroupModel` | CURRENT | точки навигации — одиночный флоу (антенны достижимы) против группового (недостижимы) |
| `lib/widgets/app_bar/custom_app_bar.dart` | `CustomAppBar` | CURRENT | обычный `AppBar` без переопределения `leading`/`PopScope` — автоматическая кнопка «назад» обходит `_save` |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT | рендерит снекбар отказа; фон `AppColors.snackbarErrorBackground`, текст `AppColors.black` — см. «Открытые вопросы» о расхождении с правилом проекта |
| `lib/theme/app_colors.dart` | `AppColors.snackbarErrorBackground`, `.red20`, `.red100` | CURRENT | `snackbarErrorBackground == red20` (`0xFFFFE0E5`) по значению, не `red100` |
| `lib/l10n/app_ru.arb`, `lib/l10n/app_en.arb` | `must_select_antenns`, `field_required` | CURRENT | переведённые тексты обоих независимых гейтов на всех языках приложения |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.bluetoothGates`, `.rfidReader`, `.rfidReaderGrpTcp`, `.rfidReaderGrpBle` | CURRENT | строковые константы четырёх антенно-зависимых типов |
| `lib/pages/routes.dart` | `Routes.profile`, `.workSettings`, `.devicesSettings`, `.scannerSettings` | CURRENT | вложенность маршрута до точки входа сценария |

## Критерии приёмки

- Для устройства типа `bluetooth_gates`/`rfid_reader`/`rfid_reader_grp_tcp`/
  `rfid_reader_grp_ble`, если на момент нажатия «Сохранить»
  `_formKey.currentState?.validate()` истинно, а `getSavedAntennas(type)`
  пусто — `_save` вызывает `showAppSnackBarError` с текстом
  `must_select_antenns`, не вызывает `context.pop()`, `ScannerSettingsPage`
  остаётся открытой.
- Ни одно поле, ранее записанное через виджеты формы (регион, мощность,
  операции, адрес), не откатывается и не изменяется этим отказом — `_save`
  на этой ветке не выполняет ни одной записи в `Devices`.
- Для `rfid_reader`/`rfid_reader_grp_ble` с пустым адресным полем отказ
  формы (`field_required`) наступает раньше проверки антенн — снекбар
  `must_select_antenns` в этом случае не показывается, даже если антенны
  тоже не выбраны.
- Для групповой (bluetooth) плитки `_isAntennasRequired` всегда возвращает
  `false` — этот `UPDATE_REJECTED` структурно недостижим через групповой
  флоу.
- Нажатие автоматической кнопки «назад» `CustomAppBar` (или системного
  back-жеста) закрывает `ScannerSettingsPage` без вызова `_save`, для
  любого типа устройства и при любом состоянии антенн.
- Выбор хотя бы одной антенны и повторное нажатие «Сохранить» проходит
  проверку и вызывает `context.pop()` — отдельный, не описываемый здесь
  `UPDATE_OK`.

## Связанные тесты

`grep -rli "antenn\|scanner_settings" test/` находит только
`test/pages/scanning_bloc_test.dart`, где `DeviceSettingsRepository.getSavedAntennas`
фигурирует исключительно как мок-зависимость сценария готовности к
сканированию (`isDeviceConfiguredForScanning`, вызывается из
`ScanningBloc`) — не имеет отношения к `ScannerSettingsPage._save` или к
этому use-case. Ни `_save`, ни `_isAntennasRequired`, ни
`ScannerSettingsPage` целиком не упоминаются ни в одном файле `test/`.

**TBD — теста нет.** Нет ни одного unit- или widget-теста на
`ScannerSettingsPage._save`, на бизнес-правило «антенны обязательны для
четырёх типов», на порядок гейтов (адрес раньше антенн), на
недостижимость этой ветки через групповой флоу, ни на обход проверки через
кнопку «назад» — ни один из этих фактов не проверен запущенным тестом,
только статическим чтением кода, выполненным при написании этой спеки.

## Открытые вопросы и ограничения

- **Проверка антенн обходится системной/AppBar кнопкой «назад».** Единственный
  путь, где `must_select_antenns`-отказ вообще применяется, — явное
  нажатие «Сохранить»; `CustomAppBar` не переопределяет автоматическую
  кнопку возврата, `ScannerSettingsPage` не оборачивает форму в
  `PopScope`/`WillPopScope`. Следствие: пользователь может настроить
  устройство наполовину (например, задать регион/мощность, но не выбрать
  антенны) и выйти с экрана кнопкой «назад» вместо «Сохранить» — бизнес-правило
  «антенны обязательны» в этом случае не применяется вовсе, хотя цель
  правила (не оставить нерабочую конфигурацию) явно подразумевает
  обратное. Не подтверждено, было ли это осознанным решением (кнопка
  «назад» — просто способ отменить/выйти без проверки) или недосмотром.
- **`updateAntennasInStorage`/`updateAddressInStorage`/`updateDeviceOperationUsage`
  не выставляют `isNeedUpdate`/`updatedAt` — расхождение с описанием
  эффекта в [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)
  («каждое изменение сразу пишется в `Devices`, проставляя `isNeedUpdate:
  true`/`updatedAt: now()`»), которое буквально верно только для
  `updatePowerInDatabase`/`updateRegionInDatabase`/`updateIsUseCameraForQrInDatabase`/
  `updateDeviceButtonAction`.** Практическое следствие для этого сценария:
  пользователь устраняет причину отказа (выбирает антенну,
  `updateAntennasInStorage`), `_save` успешно завершается — но если ни
  одно из четырёх «настоящих» полей на этой же строке `Devices` не менялось
  в эту же сессию редактирования, `isNeedUpdate` у строки может остаться
  `false`. Следующий sync-проход (`DataUpdateBloc._suncDevices` →
  `updateDevicesOnSHTP()`) фильтрует именно по `isNeedUpdate == true &&
  remoteId != null` — такая строка не попадёт в push, и выбранные антенны
  останутся только локальными, никогда не будут отправлены на сервер, без
  какого-либо видимого пользователю признака этого. Не проверено на
  реальном sync-проходе (вывод — статическим чтением
  `devices_settings_repository.dart` + `data_update_bloc.dart`), но методы
  читаются однозначно.
- **Фактический снекбар отказа не совпадает по цвету/тексту с описанием
  error-варианта в `.claude/rules/ui-architecture.md`** (там — фон
  `AppColors.red100`, текст `AppColors.white`; в коде `showAppSnackBarError`
  — фон `AppColors.snackbarErrorBackground` (`0xFFFFE0E5`, по значению
  совпадает с `AppColors.red20`, светло-розовый), текст всегда
  `AppColors.black`, одинаково для всех трёх вариантов
  info/success/error). Тангенциально для этого use-case (сам факт отказа
  не зависит от оформления), но напрямую влияет на то, что реально видит
  пользователь при `must_select_antenns`.
- **Нет UI-индикации до нажатия «Сохранить»** (например, дизейбл кнопки,
  пока не выбрана хотя бы одна антенна для этих четырёх типов) —
  пользователь узнаёт об отказе только постфактум, из снекбара; тот же
  паттерн отсутствия предупреждающего UI уже отмечен для похожего
  бизнес-правила в [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md)
  (видимость видов).
- Не проверено, различаются ли фактически `ScannerDeviceTypes.bluetoothGates`/
  `.rfidReader`/`.rfidReaderGrpTcp`/`.rfidReaderGrpBle` (список,
  зашитый в `_isAntennasRequired` через `is`-проверку типов) и полный
  список типов, для которых в принципе имеет смысл требовать антенну —
  оба источника (`_isAntennasRequired` и
  `isDeviceConfiguredForScanning`) сегодня совпадают по составу, но
  независимо друг от друга, без общего справочника/константы,
  аналогично уже отмеченному в [UC-176](UC-176-ACTOR-5-EVT-88-ENT-22-READ_OK-IN-PROFILE.md)
  расхождению `ScannerDeviceTypes.bluetoothGroup` vs
  `_isBluetoothGroupDevice`.
