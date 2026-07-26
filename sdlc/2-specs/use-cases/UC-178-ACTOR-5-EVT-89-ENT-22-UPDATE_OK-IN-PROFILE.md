# UC-178 — Пользователь сохраняет настройки сканирующего устройства (одно устройство или bluetooth-группа разом)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь на `ScannerSettingsPage` меняет операции/регион/мощность/
антенны/IP-или-MAC/действия кнопок TCD/чекбокс камеры QR для одного
устройства либо разом для всей bluetooth-группы (`applyToTypes`) и
закрывает форму кнопкой «Сохранить» (`_save`) — все проверки проходят,
экран закрывается. Happy-path сценарий события
[EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)
(`device_settings.saved`).

Ключевой архитектурный факт, определяющий весь остальной документ: в
отличие от [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
(уведомления, где `save()` одним вызовом перезаписывает всю строку),
здесь почти каждое поле пишется в БД **немедленно, по месту**, в момент
взаимодействия пользователя с конкретным виджетом — не батчем при нажатии
«Сохранить». Кнопка «Сохранить» (`_save`) не пишет в БД ни одного нового
значения сама — её единственная работа: (1) прогнать валидаторы `Form`
(реально есть только у адреса) и (2) применить один явный бизнес-гейт
(«для типов с антеннами must-select-antennas»), затем закрыть экран.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость и авторизованный обрабатываются одинаково. Весь раздел `PROFILE` без
route-guard по авторизации (см. [MOD-6](../modules/MOD-6-PROFILE.md)); ни
`ScannerSettingsPage`, ни `DeviceSettingsRepository` нигде не проверяют
`AppCacheService.isAuthorized()`.

## CURRENT

### Основной поток

1. Пользователь попадает на `ScannerSettingsPage` с `Routes.scannerSettings`
   из грида `DevicesSettingsPage` (сценарий просмотра —
   [EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md), здесь не
   переспецифицируется) с аргументом `ScannerSettingsPageArguments(device,
   groupDevices?, groupTitle?)`. Единственные два места в коде, строящие
   этот аргумент — `DevicesSettingsPage._deviceModel`/`_bluetoothGroupModel`
   (`lib/pages/scanner_settings/pages/devices_settings_page.dart`).
2. `_ScannerSettingsPageState.build` оборачивает содержимое в единый `Form`
   с `_formKey` и рендерит: `_GroupOperationsContent`, если
   `groupDevices != null` (тап по плитке «Bluetooth»), иначе
   `ScannerSettingsContent(device: device)` (тап по индивидуальной плитке).
3. **Одиночное устройство.** `ScannerSettingsContent.build`
   (`lib/pages/scanner_settings/widgets/scanner_settings_views.dart`)
   свитчится по рантайм-подтипу `ScannerDevice` (получен через
   `Device.toScannerDevice()`,
   `lib/repositories/devices_settings/scanner_device.dart`) и собирает
   ровно тот набор полей, который applicable этому типу:
   - `TerminalScannerDevice` (`tcd`) → операции, регион, мощность, чекбокс
     камеры, три селектора действий кнопок TCD;
   - `BluetoothGatesScannerDevice` (`bluetooth_gates`) → операции, регион,
     мощность, антенны;
   - `RfidTcpScannerDevice`/`RfidGrpTcpScannerDevice`
     (`rfid_reader`/`rfid_reader_grp_tcp`) → операции, регион, мощность,
     IP-адрес, антенны;
   - `RfidGrpBleScannerDevice` (`rfid_reader_grp_ble`) → то же, но MAC
     вместо IP;
   - `A7ScannerDevice`/`UhfStickScannerDevice` (`A7 (bluetooth)` и 8
     `ra_*bt`/`ra_*lf`/`ra_6000uhf` типов) → только операции.
4. **Bluetooth-группа.** Плитка «Bluetooth» на гриде объединяет ровно те
   типы, для которых `DevicesSettingsPage._isBluetoothGroupDevice` истинно
   (`A7ScannerDevice || UhfStickScannerDevice`) — 9 из 14 строк каталога
   `ScannerDeviceTypes.defaults` (8 `ra_*`-типов + `a7Bluetooth`), что
   ровно совпадает с `ScannerDeviceTypes.bluetoothGroup`. Открытие этой
   плитки передаёт `groupDevices: groupDevices` (все 9), поэтому
   `_GroupOperationsContent` рендерит **только**
   `ScannerOperationsSettingsWidget(device: groupDevices.first, applyToTypes:
   groupDevices.map((d) => d.type).toList())` — ни регион, ни мощность, ни
   антенны, ни адрес, ни TCD-специфичные поля здесь не показываются вообще
   (у `A7ScannerSettings`/`UhfStickScannerSettings` нет ни одного поля,
   кроме самого факта типа).
5. Каждый полевой виджет читает своё текущее сохранённое значение в
   `initState` и пишет изменение в БД **сразу**, не дожидаясь «Сохранить»:
   - `ScannerOperationsSettingsWidget._updateOperation` — для каждого
     `type` из `applyToTypes ?? [device.type]` **последовательно** (в
     цикле `for` с `await` внутри, не `Future.wait`) вызывает
     `DeviceSettingsRepository.updateDeviceOperationUsage(deviceType:
     type, operationType, isEnabled)`. В группе один тумблер (единственная
     опция в `ScannerOperation.values` — `inventory`) одним переключением
     пишет 9 отдельных Drift-обновлений подряд.
   - `RegionSelectorWidget.onChanged` → `updateRegionInDatabase(region.index,
     type)`; если `type == ScannerDeviceTypes.bluetoothGates`, дополнительно
     `ScannerService.tryApplyGatesBleRegion(region.index)`.
   - `SelectPowerSlider.onChangeEnd` → `setPower(level)`; поскольку
     `isConnected` жёстко передан `false` из всех пяти мест вызова в
     `scanner_settings_views.dart`, всегда берётся ветка
     `updatePowerInDatabase(level, type)` (ветка
     `ScannerService.setTerminalPower` в этом сценарии недостижима); если
     `type == bluetoothGates`, дополнительно
     `ScannerService.tryApplyGatesBlePower(level)`.
   - `ScannerAddressSettingsWidget.onChanged` (только для трёх RFID-типов) →
     `updateAddressInStorage(type, value)` — вызывается на **каждое
     нажатие клавиши** (`RTextField.outline.onChanged` — прямой проброс в
     `TextFormField.onChanged`, `lib/widgets/text_field/text_field.dart`),
     не по blur/submit — промежуточное, ещё не введённое до конца значение
     адреса тоже уходит в БД.
   - `ScannerAntennasSettingsWidget._toggleAntenna` (`bluetooth_gates` и три
     RFID-типа) → `updateAntennasInStorage(type, updatedSet)`.
   - `IsUseCameraForQrCheckBoxWidget.onChanged` (только `tcd`) →
     `updateIsUseCameraForQrInDatabase(value, 'tcd')`.
   - `TcdActionSelectorsWidget._updateDeviceAction` (только `tcd`) →
     `updateDeviceButtonAction(deviceType: 'tcd', left/middle/right)`, затем
     **в том же `try`** — `ScannerService.applyTerminalButtonActions()`
     (перечитывает только что сохранённые настройки терминала и
     best-effort применяет их к физическому устройству); любое исключение
     из обоих вызовов ловится одним `catch` и лишь логируется через
     `Talker.handle`, не долетает до UI.
6. Пользователь нажимает «Сохранить» (`BlackCircleButton`,
   `AppLocalizations.save`) → `_save(context, device)`.
7. `_save`: `_formKey.currentState?.validate() ?? true` — единственный
   реальный `TextFormField`-валидатор во всём дереве —
   `field_required`-проверка внутри `ScannerAddressSettingsWidget` (только
   для трёх RFID-типов); для остальных типов (`tcd`, `bluetooth_gates`,
   вся bluetooth-группа) валидаторов в дереве нет вовсе, `validate()`
   тривиально проходит.
8. `_isAntennasRequired(device)` — `true` только для
   `BluetoothGatesScannerDevice`/`RfidTcpScannerDevice`/
   `RfidGrpTcpScannerDevice`/`RfidGrpBleScannerDevice`. Если true,
   `_save` делает **свежий** DAO-запрос `_repository.getSavedAntennas(
   device.type)` (не читает закэшированное состояние виджета
   `_antennas`); в этом сценарии множество непусто (антенна(-ы) выбраны
   на шаге 5), проверка проходит.
9. Форма валидна и антенны (если требуются) не пусты →
   `if (!context.mounted) return; context.pop();` — единственный
   наблюдаемый эффект успешного `_save`: закрытие экрана. Никакого
   success-снекбара или иного визуального подтверждения не показывается —
   все значения уже были durable-сохранены на шаге 5, до самого нажатия
   «Сохранить».
10. Вызывающая сторона (`DevicesSettingsPage._deviceModel`/
    `_bluetoothGroupModel`, `onTap`) дожидается `await
    context.pushNamed2(...)` и безусловно вызывает `_refreshDevices()` —
    перечитывает `getCurrentScannerDevices()`, чтобы перерисовать грид уже
    с обновлёнными значениями.
11. Сетевого вызова в рамках этого сценария нет. Строка(и) `Devices`,
    затронутые на шаге 5, получают `isNeedUpdate: true`/`updatedAt: now()`
    независимо от того, какой именно из семи repository-методов был
    вызван (см. «Бизнес-правила» — механизм не одинаков на уровне
    repository, но одинаков на выходе). Реальная отправка на сервер —
    отдельный, безусловный шаг следующего полного sync-прохода
    (`DataUpdateBloc._suncDevices()` → `updateDevicesOnSHTP()`, ACTOR-4,
    [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)) —
    не этот use-case.

### Альтернативные потоки

- **Антенны не выбраны у типа, для которого они обязательны —
  `REJECTED`, не этот сценарий.** Тот же `_save`, шаг 8: если
  `getSavedAntennas(device.type)` пуст, `showAppSnackBarError(context,
  context.tr('must_select_antenns'))`, `_save` возвращается без
  `context.pop()` — экран остаётся открытым. Это осознанный отказ
  бизнес-правилом (операция дошла до `_save`, была рассмотрена и
  отклонена), не техническая ошибка — отдельная классификация
  результата (`ENT-22`, `UPDATE_REJECTED`), пока не оформленная отдельным
  файлом; здесь не специфицируется дальше.
- **Форма невалидна (пустой адрес у RFID-типа) — тоже не `_save`-успех.**
  `_formKey.currentState?.validate()` возвращает `false`, `_save`
  возвращается немедленно, до проверки антенн — поле показывает
  `field_required` под собой. Тот же класс отказа, что и предыдущий пункт,
  здесь не разбирается.
- **В bluetooth-групповом потоке гейт антенн структурно недостижим.**
  `device` в `_isAntennasRequired(device)` для группового вызова — всегда
  `groupDevices.first`, то есть всегда `A7ScannerDevice` или
  `UhfStickScannerDevice`, ни один из которых не входит в список типов,
  требующих антенны. Поэтому из экрана группы `_save` **всегда** доходит
  до `context.pop()`, если только не сломан сам `Form` (валидаторов там
  нет вовсе) — REJECTED-ветка для этого экрана недостижима в принципе, не
  только маловероятна.
- **«Отмена» назад через `AppBar`/системный жест обходит бизнес-правило
  антенн целиком.** `CustomAppBar` — обычный Flutter `AppBar` без
  кастомного `leading`, поэтому автоматический back-arrow (и системный
  back-жест) присутствует всегда, вызывая `Navigator.pop` напрямую, минуя
  `_save`. Поскольку каждое поле уже пишется в БД по месту (шаг 5), выход
  этим путём не «отменяет» ничего из уже введённого — но и не требует
  выбранных антенн для типов, где `_save` бы это потребовал: пользователь
  может уйти с экрана `bluetooth_gates`/RFID-устройства с пустым
  множеством антенн, просто не нажимая «Сохранить».
- **Представитель группы маскирует расхождение состояний.**
  `ScannerOperationsSettingsWidget` в групповом потоке инициализирует
  чекбокс по `getEnabledOperationTypes(groupDevices.first.type)` — только
  по ПЕРВОМУ устройству группы. Если у остальных 8 строк это поле уже
  отличается (например, включено у части и выключено у другой), UI
  показывает состояние только первой строки; любое переключение тумблера
  применяет **это** булево значение ко всем 9 типам разом
  (`updateDeviceOperationUsage` в цикле) — расхождение, если оно было,
  стирается в пользу того, что показал/что выбрал пользователь, не
  восстанавливается.
- **`SelectPowerSlider`'s ветка «скрыт, если не подключено/не то
  железо» — мёртвый код на этом экране.** Все пять мест вызова в
  `scanner_settings_views.dart` передают `forceVisible: true`, поэтому
  условие `if (!widget.forceVisible && !k626 && !pda) return
  SizedBox.shrink();` никогда не выполняется на этом экране — слайдер
  мощности виден всегда, независимо от реального имени устройства
  (`DeviceSettingsRepository.deviceName`).
- **`A7ScannerSettingsView`/`UhfStickScannerSettingsView` внутри
  `ScannerSettingsContent` — недостижимый код на сегодняшнем entry point.**
  Единственные два места, строящие `ScannerSettingsPageArguments`
  (`devices_settings_page.dart`), либо не передают `groupDevices` для
  НЕ-bluetooth-типов (`_deviceModel`, откуда `A7`/`UhfStick`-устройства
  явно исключены циклом `if (_isBluetoothGroupDevice(device)) continue;`),
  либо передают `groupDevices` именно для `A7`/`UhfStick`-типов
  (`_bluetoothGroupModel`) — а `ScannerSettingsPage.build` при
  `groupDevices != null` всегда рендерит `_GroupOperationsContent`, никогда
  `ScannerSettingsContent`. Значит ветки `A7ScannerDevice()`/
  `UhfStickScannerDevice()` в `switch` внутри `ScannerSettingsContent.build`
  реально никогда не выполняются при текущей навигации — код существует,
  путь к нему нет.
- **Дублирование, не переиспользование, бизнес-правила «когда нужны
  антенны».** `_isAntennasRequired` (сопоставление по рантайм-подтипу
  `ScannerDevice`) и `DeviceSettingsRepository.isDeviceConfiguredForScanning`
  (сопоставление по строковому `deviceType`, [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md))
  перечисляют один и тот же набор из 4 типов двумя независимыми
  реализациями — `_save` не вызывает `isDeviceConfiguredForScanning`
  напрямую. На сегодня итог логически эквивалентен: для `bluetooth_gates`
  комбинация «Form валиден (адреса нет в дереве) + антенны непусты» и есть
  вся проверка `isDeviceConfiguredForScanning`; для трёх RFID-типов «Form
  валиден (адрес обязателен) + антенны непусты» покрывает оба условия
  `isDeviceConfiguredForScanning` (антенны И адрес). Если один из двух
  списков когда-нибудь изменится независимо от другого, они разойдутся
  молча — ни один тест такого расхождения не поймает (см. «Открытые
  вопросы»).

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность, чьё физическое хранилище меняется этим сценарием: одна строка
  `Devices` (одиночный поток) либо до 9 строк разом (`availableOperations`
  групповым циклом), с `isNeedUpdate: true`/свежим `updatedAt` на каждой
  затронутой строке.
- Ни [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md), ни
  [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (`Kind.visible`), ни
  [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) не читаются и не пишутся этим
  сценарием — три независимых настройки модуля `PROFILE`, не связанные
  общим кодом (см. [MOD-6](../modules/MOD-6-PROFILE.md)).

### Бизнес-правила

- **Персистентность — по полю, немедленно, не батчем при «Сохранить».**
  `_save` сам не пишет ни одного значения — только валидирует и закрывает
  экран. Это архитектурно отличает `EVT-89` от
  [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md)
  (уведомления, [UC-169](UC-169-ACTOR-5-EVT-85-ENT-21-UPDATE_OK-IN-PROFILE.md)),
  где всё пишется одним `clearAndInsertAll` внутри `save()`.
- **`isNeedUpdate`/`updatedAt` проставляются централизованно на уровне
  DAO, а не единообразно на уровне repository-методов.**
  `DevicesDao.updateDeviceById` (`packages/sheep_farm_database/lib/entities/devices/devices_dao.dart`)
  безусловно делает `updatedFields.copyWith(updatedAt: Value(DateTime.now()),
  isNeedUpdate: const Value(true))` **поверх любого** переданного
  `DevicesCompanion`, вызывается ли он из `updatePowerInDatabase`/
  `updateRegionInDatabase`/`updateIsUseCameraForQrInDatabase`/
  `updateDeviceButtonAction` (эти четыре сами явно включают оба поля в
  свой companion — избыточно, DAO их всё равно перезапишет тем же) или из
  `updateAntennasInStorage`/`updateAddressInStorage`/
  `updateDeviceOperationUsage` (эти три сами НЕ включают `isNeedUpdate`/
  `updatedAt` в свой companion вообще). Итог на выходе одинаков для всех
  семи методов — единая точка (`updateDeviceById`) гарантирует
  sync-пригодность независимо от того, позаботился ли об этом
  вызывающий метод.
- **Единственное исключение — `updateDeviceButtonAction` не пишет в БД
  вовсе, если ни одно из трёх значений не изменилось** (`needsUpdate`
  guard) — но это уже отсечено раньше самим виджетом
  (`TcdActionSelectorsWidget` вызывает `_updateDeviceAction` только если
  `newValue != _currentButtonAction`), так что при обычном взаимодействии
  пользователя этот guard никогда не встречает «то же самое значение».
  У остальных полей (мощность/регион) аналогичной проверки «действительно
  ли значение изменилось» нет вообще — отпускание слайдера или повторный
  выбор того же региона всё равно пишет строку и помечает
  `isNeedUpdate: true`.
- **«На лету» к реальному оборудованию применяется только часть полей** —
  регион/мощность только для `bluetooth_gates`
  (`ScannerService.tryApplyGatesBleRegion`/`tryApplyGatesBlePower`, оба —
  no-op вне Android либо без активного BLE-подключения к воротам,
  значение при этом всё равно сохраняется локально) и действия кнопок
  TCD (`ScannerService.applyTerminalButtonActions()`, безусловно после
  каждого изменения кнопки). Остальные поля (антенны, адрес, операции,
  чекбокс камеры) применяются исключительно к локальному хранилищу — не
  проецируются на физическое устройство этим сценарием.
- Групповая операция (`applyToTypes`) существует только для одного поля —
  «операции» (единственный переключатель `inventory`) — ни у одного
  другого поля параметра `applyToTypes` нет.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — основной поток (немедленное
пофайловое сохранение + гейт «Сохранить» из валидации формы и проверки
антенн) полностью реализован и достижим из UI для 5 индивидуально
показанных типов (`tcd`, `bluetooth_gates`, `rfid_reader`,
`rfid_reader_grp_tcp`, `rfid_reader_grp_ble`) и для bluetooth-группы (9
типов разом, только поле операций). Находки в «Альтернативные потоки»
(недостижимый код `A7`/`UhfStick` в одиночном потоке, дублирование правила
антенн, маскировка расхождения в группе) описывают неожиданное, но не
падающее и не блокирующее поведение существующего кода.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_ScannerSettingsPageState.build`, `._save`, `._isAntennasRequired` | CURRENT | shell экрана, кнопка «Сохранить», гейт валидации формы + антенн, `context.pop()` |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_GroupOperationsContent` | CURRENT | групповой поток — рендерит только `ScannerOperationsSettingsWidget` с `applyToTypes` |
| `lib/pages/scanner_settings/pages/devices_settings_page.dart` | `_DevicesSettingsPageState._isBluetoothGroupDevice`, `._deviceModel`, `._bluetoothGroupModel`, `._refreshDevices` | CURRENT | точка входа на экран (грид), единственные два места, строящие `ScannerSettingsPageArguments`; перечитывает грид после возврата |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `ScannerSettingsContent`, `*ScannerSettingsView` (7 классов), `ScannerAddressSettingsWidget`, `ScannerAntennasSettingsWidget` | CURRENT | сборка набора полей по рантайм-подтипу устройства; немедленная запись адреса (по клавише)/антенн |
| `lib/pages/scanner_settings/widgets/scanner_operations_settings_widget.dart` | `ScannerOperationsSettingsWidget._updateOperation` | CURRENT | немедленная запись операций, цикл по `applyToTypes` |
| `lib/pages/scanner_settings/widgets/region_selector_widget.dart` | `RegionSelectorWidget` (`onChanged`) | CURRENT | немедленная запись региона + best-effort применение к `bluetooth_gates` |
| `lib/pages/scanner_settings/widgets/select_power_slider.dart` | `SelectPowerSlider.setPower` | CURRENT | немедленная запись мощности + best-effort применение к `bluetooth_gates`; ветка «скрыт» недостижима (`forceVisible: true` из всех вызовов) |
| `lib/pages/scanner_settings/widgets/tcd_action_selectors_widget.dart` | `TcdActionSelectorsWidget._updateDeviceAction` | CURRENT | немедленная запись действий кнопок TCD + `ScannerService.applyTerminalButtonActions()` в одном `try` |
| `lib/pages/scanner_settings/widgets/is_use_camera_for_qr_check_box_widget.dart` | `IsUseCameraForQrCheckBoxWidget` (`onChanged`) | CURRENT | немедленная запись чекбокса камеры (только `tcd`) |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateDeviceOperationUsage`, `.updateAddressInStorage`, `.updateAntennasInStorage`, `.updatePowerInDatabase`, `.updateRegionInDatabase`, `.updateIsUseCameraForQrInDatabase`, `.updateDeviceButtonAction`, `.getSavedAntennas`, `.isDeviceConfiguredForScanning` | CURRENT | весь CRUD-слой этого сценария; последние три метода-«хаусхолдинга» явно дублируют то, что DAO делает безусловно |
| `lib/repositories/devices_settings/scanner_device.dart` | `ScannerDevice` (sealed), `ScannerDeviceMapper.toScannerDevice`, `ScannerOperation` | CURRENT | типизация устройства по `type`, определяет, какие поля вообще показываются |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao.updateDeviceById` | CURRENT | единая точка, безусловно принудительно проставляющая `updatedAt`/`isNeedUpdate: true` поверх любого переданного companion |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `Devices`, `ScannerDeviceTypes.defaults`/`.bluetoothGroup`, `DeviceRegion`, `TcdAction` | CURRENT | таблица, каталог типов (14 записей в `defaults` — см. «Открытые вопросы» про расхождение с [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)), 9 из них — `bluetoothGroup` |
| `lib/services/scanner_service.dart` | `ScannerService.tryApplyGatesBleRegion`, `.tryApplyGatesBlePower`, `.applyTerminalButtonActions` | CURRENT | best-effort применение к реальному оборудованию; region/power — no-op вне Android/без активного BLE-подключения |
| `lib/widgets/text_field/text_field.dart` | `RTextField.outline` (`onChanged`) | CURRENT | прямой проброс в `TextFormField.onChanged` — подтверждает «пишется на каждую клавишу» |

## Критерии приёмки

- Каждое изменение операций/региона/мощности/антенн/адреса/действий
  кнопок TCD/чекбокса камеры на `ScannerSettingsPage` приводит к вызову
  соответствующего `DeviceSettingsRepository.update*` **сразу** при
  взаимодействии с виджетом, до и независимо от нажатия «Сохранить».
- После любого такого вызова затронутая строка `Devices` имеет
  `isNeedUpdate == true` и обновлённый `updatedAt`, независимо от того,
  какой из семи `update*`-методов был вызван (гарантируется
  `DevicesDao.updateDeviceById`, не индивидуальными репозиторными
  методами).
- Для типов `bluetooth_gates`/`rfid_reader`/`rfid_reader_grp_tcp`/
  `rfid_reader_grp_ble` нажатие «Сохранить» с непустым, только что
  сохранённым множеством антенн (и — для трёх RFID-типов — непустым
  адресом, прошедшим валидатор формы) приводит ровно к одному
  `context.pop()`, без сетевого вызова и без снекбара.
- Для bluetooth-группы (`groupDevices != null`) нажатие «Сохранить»
  всегда приводит к `context.pop()` при валидной форме — проверка антенн
  структурно не применяется к этому потоку.
- Изменение переключателя операции в групповом потоке приводит к ровно
  `groupDevices.length` последовательным вызовам
  `updateDeviceOperationUsage` — по одному на каждый тип из
  `applyToTypes`.
- Возврат с экрана системным/аппбар-жестом «назад» (не через
  «Сохранить») не откатывает ни одно уже применённое по месту изменение
  — персистентность полей не привязана к самому факту нажатия
  «Сохранить».

## Связанные тесты

**TBD — теста нет.** Ни `ScannerSettingsPage`, ни его дочерние виджеты
(`ScannerOperationsSettingsWidget`, `RegionSelectorWidget`,
`SelectPowerSlider`, `ScannerAddressSettingsWidget`,
`ScannerAntennasSettingsWidget`, `TcdActionSelectorsWidget`,
`IsUseCameraForQrCheckBoxWidget`), ни `_save`/`_isAntennasRequired`, ни
сценарий `applyToTypes` для bluetooth-группы не покрыты ни одним widget-
или unit-тестом в репозитории — подтверждено чтением: `grep -rl
"ScannerSettingsPage\|DeviceSettingsRepository\|scanner_settings\|devices_settings" test/`
находит только `test/blocs/data_update_bloc_test.dart` (мокает
`DeviceSettingsRepository` как чужую зависимость для тестов sync-прохода,
не тестирует сам репозиторий) и `test/pages/scanning_bloc_test.dart`
(вызывает `updateAntennasInStorage`/`updateAddressInStorage` изнутри
`ScanningBloc` — модуль `ANIMAL`/INV, автонастройка устройства во время
сканирования, не эта страница и не событие `EVT-89`) — ни один из них не
называет `UC-178` ни в `group()`, ни в комментарии.

## Открытые вопросы и ограничения

- **Расхождение количества типов в каталоге.** Прямой подсчёт
  `ScannerDeviceTypes.defaults` (`packages/sheep_farm_database/lib/entities/devices/devices.dart`)
  даёт **14** элементов (8 `ra_*`-типов + `tcd` + `a7Bluetooth` +
  `bluetoothGates` + `rfidReader` + `rfidReaderGrpBle` +
  `rfidReaderGrpTcp`), тогда как [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)
  («Описание») утверждает «13 типов устройств». Не исправляется этим
  документом ([ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) — заморожен
  для этого прохода, редактируется только собственным модулем при
  отдельном пересмотре); зафиксировано здесь как найденное при проверке
  кода расхождение.
- **Дублирование правила «когда нужны антенны»** (`_isAntennasRequired`
  vs `DeviceSettingsRepository.isDeviceConfiguredForScanning`) сегодня
  логически эквивалентно в сочетании с валидатором адреса, но это две
  независимые реализации без общего источника истины — расхождение при
  будущем изменении одного из списков не будет поймано ни компилятором,
  ни существующими тестами (их нет, см. «Связанные тесты»).
- **Промежуточный (недопечатанный) адрес персистентно пишется в БД на
  каждую клавишу**, включая заведомо невалидные промежуточные состояния
  (например, неполный IP при вводе по цифре). Если полный sync-проход
  (`DataUpdateStartAll`) случайно совпадёт по времени с процессом ввода
  (гонка, не воспроизведённая тестом), для строки с уже выставленным
  `remoteId` в пуш «правки» (`updateDevicesOnSHTP()`,
  [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md))
  теоретически может уйти неполная строка адреса — не проверено
  эмпирически, только статическим чтением кода.
- **REJECTED-ветка (антенны не выбраны / форма невалидна) технически
  реализована, но не оформлена отдельным use-case-файлом на момент
  написания этого документа** — см. «Альтернативные потоки»; результат
  такого сценария (`ENT-22`, `UPDATE_REJECTED`) не специфицируется здесь
  дальше первого упоминания.
- Не проверено эмпирически на реальном оборудовании (BLE-ворота,
  физический TCD-терминал) — вывод о «best-effort, no-op вне
  подключения» сделан статическим чтением
  `ScannerService.tryApplyGatesBleRegion`/`tryApplyGatesBlePower`/
  `applyTerminalButtonActions`, не подтверждён интеграционным тестом с
  реальным транспортом (`MethodChannel('gates_ble/scanner')`).
