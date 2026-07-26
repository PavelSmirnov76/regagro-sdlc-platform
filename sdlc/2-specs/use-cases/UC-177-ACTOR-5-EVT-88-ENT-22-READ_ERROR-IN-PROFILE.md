# UC-177 — Чтение настроек устройств сканирования падает: непойманное исключение Drift воспроизводится независимо в гриде и в четырёх виджетах формы — везде как бесконечный спиннер, без единой строки лога

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же экран, что описан в [EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md) —
`DevicesSettingsPage` (грид устройств) и `ScannerSettingsPage` (форма одного
устройства/группы) читают локальные настройки сканирующих устройств через
`DeviceSettingsRepository`. Здесь описан путь, когда это чтение реально
бросает исключение — в отличие от [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)
(BOARD), где технический `READ_ERROR` структурно недостижим, потому что
репозиторий сам глотает исключение, здесь **ни один слой между физическим
Drift-запросом и виджетом не содержит ни одного `try/catch`** —
`DeviceSettingsRepository`, `DevicesDao`, `BaseDao`, `BaseRepository` — все
пропускают исключение насквозь, необработанным. Это полноценный, реально
наблюдаемый в коде `READ_ERROR`.

Наблюдаемый пользователем итог даже тише, чем в
[UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md) (соседний
`READ_ERROR` этого же модуля, для уведомлений о вакцинации) — там ошибка хотя
бы долетает до `catch` кубита и пишется в `Talker`, просто UI её не
показывает. Здесь исключение долетает до `FutureBuilder`/голого
`initState()`-вызова, ничем не перехваченное по пути, и **не логируется
вообще нигде** — ни в `Talker`, ни в `dart:developer`, ни даже в виде
стандартной консольной записи об необработанной асинхронной ошибке
(`main.dart`'s `runZonedGuarded`/`runTalkerZonedGuarded` закомментирован, а
`FutureBuilder` сам «поглощает» ошибку через `.then(..., onError: ...)`,
из-за чего до зоны по умолчанию она вообще не долетает). Проверено и
задокументировано отдельными под-пунктами: (а) тот же класс дефекта
воспроизводится независимо ещё в четырёх виджетах внутри формы одного
устройства, не только в гриде; (б) один из этих виджетов (адрес) деградирует
иначе — молча, без спиннера; (в) кнопка «Сохранить» становится немым no-op,
если тот же непойманный сбой происходит в момент повторной проверки антенн
перед сохранением.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость или авторизованный — здесь это **действительно** так, без оговорок в
духе [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md) (там
кнопка входа на экран уведомлений видна только авторизованному). Прочитаны
обе точки входа в цепочке:

- `ProfileView.build` (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`)
  — кнопка `ProfileButton` с `l10n.profile_settings__work_settings` →
  `context.pushNamed2(Routes.workSettings)` — рендерится безусловно, без
  какой-либо проверки `AppCacheService.isAuthorized()` вокруг неё (в отличие
  от `_ProfileSettingsButtons`, обёрнутого в такую проверку и обсуждённого в
  [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)).
- `WorkSettingsPage.build` (`lib/pages/profile_settings/presentation/work_settings_page.dart`)
  — `WorkSettingsItem` «Настройки устройств» → `context.pushNamed2(Routes.devicesSettings)`
  — также без условия по авторизации.

То есть для этой конкретной пары экранов формулировка «весь раздел без
route-guard по авторизации», уже зафиксированная в
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) и [MOD-6](../modules/MOD-6-PROFILE.md),
подтверждается буквально и на уровне видимости кнопки-входа, не только на
уровне отсутствия `redirect` в `go_router` — расхождение,
задокументированное для соседнего экрана в
[UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md), здесь не
повторяется.

Полный путь: `ProfilePage` → `/profile/work_settings` (`WorkSettingsPage`) →
`/profile/work_settings/devices_settings` (`DevicesSettingsPage`) →
опционально `/profile/work_settings/devices_settings/scanner_settings`
(`ScannerSettingsPage`, `lib/pages/routes.dart`).

## CURRENT

### Основной поток

1. Пользователь (гость или авторизованный, см. «Пользователь») на
   `ProfilePage` нажимает «Настройки работы» → `WorkSettingsPage` → «Настройки
   устройств» → `context.pushNamed2(Routes.devicesSettings)`.
2. `DevicesSettingsPage` (`lib/pages/scanner_settings/pages/devices_settings_page.dart`)
   создаётся; `_repository = getIt<DeviceSettingsRepository>()` — резолвит уже
   существующий lazy singleton (`lib/injection_container.dart`:
   `getIt.registerLazySingleton<DeviceSettingsRepository>(() => DeviceSettingsRepository())`),
   чей `dao = getIt<AppDatabase>().getDaoByType<DevicesDao>()`
   (`lib/repositories/base_repository.dart`) резолвится синхронно при первом
   обращении к репозиторию — если бы сама `AppDatabase` была недоступна,
   отказ произошёл бы раньше и по-другому, вне рамок этого сценария (см.
   «Технические зависимости»). `initState()`:
   `_devicesFuture = _repository.getCurrentScannerDevices();`.
3. `getCurrentScannerDevices()` → `getCurrentDevices()`
   (`lib/repositories/devices_settings/devices_settings_repository.dart`):
   сначала `await ensureDeviceInDatabase()` — идемпотентный ресид каталога
   (`loadCurrentHardwareName()` через платформенный канал
   `DeviceInfoPlugin`; `dao.deleteDevicesByTypes(_obsoleteDeviceTypes)`; цикл
   `_ensureDefaultDevice` по всем 13 `defaultDevices`, каждый — несколько
   вызовов `dao.findDevicesByType`/`getDeviceById`/`deleteDeviceById`/`insertDevice`/`updateDeviceById`),
   затем `final devices = await dao.getAllDevices();` (`select(devices).get()`
   — реальный Drift-запрос к физической sqlite3-БД,
   `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart`).
   **Ни один из этих вызовов, ни сам `DeviceSettingsRepository`, ни
   `DevicesDao`, ни `BaseDao`, ни `BaseRepository` не оборачивают ничего в
   `try/catch`.** В этом сценарии один из вызовов внутри `ensureDeviceInDatabase()`
   либо сам `dao.getAllDevices()` бросает исключение (I/O-ошибка,
   блокировка файла БД, повреждение данных) — из-за отсутствия
   какого-либо перехвата по всему этому пути невозможно даже определить
   постфактум, на каком именно из полутора десятков вложенных вызовов
   произошёл отказ.
4. Исключение всплывает необработанным из `getCurrentDevices()`, из
   `getCurrentScannerDevices()`, становится ошибкой завершения `Future`,
   присвоенного `_devicesFuture` на шаге 2.
5. `FutureBuilder<List<ScannerDevice>>` (`DevicesSettingsPage.build`)
   подписан на этот `Future` через `.then<void>(onValue, onError: (error,
   stackTrace) { setState(() { _snapshot = AsyncSnapshot.withError(ConnectionState.done,
   error, stackTrace); }); })` — стандартный механизм самого виджета Flutter.
   Присоединение `onError`-обработчика означает, что ошибка `Future`
   считается обработанной на уровне Dart — она не долетает ни до какого
   `Zone`-перехватчика по умолчанию. Дополнительно подтверждено чтением
   `lib/main.dart`: вызов `runZonedGuarded`/`runTalkerZonedGuarded` там
   буквально закомментирован (`// runTalkerZonedGuarded(getIt<Talker>(), ()
   => runApp(const MyApp()));`), так что даже если бы ошибка не была
   поймана `FutureBuilder`, глобального перехватчика всё равно нет. Итог:
   **эта ошибка не логируется вообще нигде** — ни в `Talker`, ни в
   `dart:developer`, ни стандартной консольной записью об необработанной
   асинхронной ошибке.
6. `snapshot` теперь: `connectionState == ConnectionState.done`, `hasError ==
   true`, `data == null`. `AsyncSnapshot.hasData` определён как `data !=
   null`, независимо от `connectionState`/`hasError`.
7. `DevicesSettingsPage.build`'s `FutureBuilder.builder`:
   ```dart
   if (!snapshot.hasData) {
     return const Center(child: CircularProgressIndicator());
   }
   return SafeArea(child: DevicesGrid(devices: _buildGridModels(context, snapshot.data!)));
   ```
   — **ни одна ветка этого `builder` не читает `snapshot.hasError`/`snapshot.error`
   вообще**. Поскольку `data` остаётся `null` навсегда, условие `!snapshot.hasData`
   истинно бессрочно.
8. Итог, видимый пользователем: экран «Настройки устройств» показывает
   бесконечно крутящийся `CircularProgressIndicator` по центру пустого
   `Scaffold` — ни текста ошибки, ни кнопки «повторить», ни `SnackBar`, ни
   какого-либо иного признака отказа. Грид (`DevicesGrid`) и весь его
   контент (13 плиток устройств, включая схлопнутую плитку «Bluetooth») ни
   разу не строятся.

### Альтернативные потоки

- **(а) «Обновление» после возврата с экрана устройства повторяет тот же
  отказ, без встроенного retry.** `_deviceModel`/`_bluetoothGroupModel`'s
  `onTap`: `await context.pushNamed2(Routes.scannerSettings, extra: ...);
  _refreshDevices();` — `_refreshDevices()` пересоздаёт тот же
  `_devicesFuture = _repository.getCurrentScannerDevices();`. Если условие,
  вызвавшее исключение (например, персистентная ошибка I/O диска), не
  исчезло, тот же путь (шаги 3-8) повторяется идентично — никакого
  backoff/отличающегося поведения при повторной попытке не предусмотрено.
  Единственный способ вообще «перезапустить» чтение — полностью покинуть
  `DevicesSettingsPage` (`Navigator.pop`) и открыть её заново, что
  пересоздаёт `_DevicesSettingsPageState` с нуля — сама страница не
  содержит ни кнопки «повторить», ни pull-to-refresh.

- **(б) Тот же класс дефекта, проверенный отдельно, воспроизводится
  независимо ещё в четырёх виджетах внутри `ScannerSettingsPage`'s дерева —
  не только в гриде.** Каждый из этих виджетов — независимый
  `StatefulWidget`, вызывающий свой собственный метод
  `DeviceSettingsRepository` в `initState()`, без единого `try/catch`, по
  идентичному паттерну `if (value == null) return const
  Center(child: CircularProgressIndicator());` в `build()`:

  - `ScannerOperationsSettingsWidget._loadSettings()`
    (`lib/pages/scanner_settings/widgets/scanner_operations_settings_widget.dart`)
    → `getEnabledOperationTypes(type)` → `dao.findDeviceByType(type)` —
    рендерится **для всех шести** видов форм устройства (единственный
    виджет, общий для всех типов, включая `A7ScannerSettingsView`/`UhfStickScannerSettingsView`).
  - `RegionSelectorWidget.initSettings()`
    (`lib/pages/scanner_settings/widgets/region_selector_widget.dart`) →
    `getSavedRegion(type)` → `dao.findDeviceByType(type)` — для пяти из
    шести видов (TCD/BluetoothGates/RfidTcp/RfidGrpTcp/RfidGrpBle).
  - `SelectPowerSlider.initSettings()`
    (`lib/pages/scanner_settings/widgets/select_power_slider.dart`) →
    `getSavedPower(type)` → `dao.findDeviceByType(type)` — те же пять видов.
  - `ScannerAntennasSettingsWidget._loadAntennas()`
    (`lib/pages/scanner_settings/widgets/scanner_settings_views.dart`) →
    `getSavedAntennas(type)` → `dao.findDeviceByType(type)` — только для
    типов, требующих антенны (BluetoothGates/RfidTcp/RfidGrpTcp/RfidGrpBle,
    четыре из шести видов).

  Для типа устройства, требующего антенны (например, `bluetooth_gates`),
  если каждый из этих четырёх независимых `await`-вызовов (не единый
  batch-запрос, а четыре отдельных обращения к той же таблице `Devices`) по
  отдельности отказывает, форма показывает **до четырёх одновременно
  бесконечно крутящихся `CircularProgressIndicator`** внутри одной
  `Column`, при этом остальная разметка (заголовки секций, отступы)
  отображается нормально вокруг них — страница не падает и не показывает
  ни строки объяснения.

  Контрастно устроены два соседних виджета того же дерева:

  - `ScannerAddressSettingsWidget._loadAddress()`
    (`lib/pages/scanner_settings/widgets/scanner_settings_views.dart`) →
    `getSavedAddress(type)` — **не содержит проверки `null` в `build()`
    вовсе**: при отказе `_controller.text` просто никогда не
    присваивается, остаётся пустой строкой (дефолт `TextEditingController()`)
    — поле ввода IP/MAC молча выглядит как легитимное «адрес ещё не
    задан», без какого-либо спиннера или иного признака отказа.
  - `IsUseCameraForQrCheckBoxWidget`
    (`lib/pages/scanner_settings/widgets/is_use_camera_for_qr_check_box_widget.dart`)
    и `TcdActionSelectorsWidget`
    (`lib/pages/scanner_settings/widgets/tcd_action_selectors_widget.dart`)
    этим отказом **не затронуты вовсе** — оба читают начальное значение
    прямо из `widget.device.settings` (объект `ScannerDevice`, уже
    полностью собранный и переданный через `ScannerSettingsPageArguments`
    из уже успешно завершившегося на предыдущем экране
    `getCurrentScannerDevices()`), не делая ни одного отдельного
    обращения к БД в своём `initState()`.

- **(в) Кнопка «Сохранить» становится немым no-op, если тот же непойманный
  сбой происходит в момент проверки бизнес-правила об антеннах.**
  `ScannerSettingsPage._save()` (обработчик, стоящий за
  [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md); упомянут
  здесь только как контрастный побочный эффект того же дефекта, не как
  предмет этого файла) для типов, требующих антенны, повторно вызывает
  `await _repository.getSavedAntennas(device.type)` — **пятая** независимая
  точка вызова того же непойманного чтения, на этот раз внутри
  `Future<void>`-обработчика, подключённого к обычному `VoidCallback
  onTap: () => _save(context, device)` на `BlackCircleButton`
  (`lib/widgets/button/button.dart`, `final VoidCallback onTap;`) — то
  есть без ожидания результата вызывающей стороной (`onTap` не
  `async`, возвращённый `_save`'s `Future` никем не подхватывается). Если
  этот вызов бросает исключение, оно становится необработанной
  асинхронной ошибкой, которую (как и в основном потоке, шаг 5) некому
  перехватить — `runZonedGuarded`/`runTalkerZonedGuarded` в `main.dart`
  закомментирован. Наблюдаемый эффект: нажатие «Сохранить» визуально не
  делает ничего — ни `SnackBar` `must_select_antenns` (см.
  [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)), ни
  `context.pop()` не достигаются, никакого лога нигде не появляется. Уже
  задокументированное бизнес-правило `REJECTED` (пустые антенны →
  снекбар) в этом состоянии структурно недостижимо — оно может
  сработать только если предшествующий ему повторный `getSavedAntennas`
  сам завершится успешно.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность, которую этот сценарий пытается прочитать (таблица `Devices`,
  все пять описанных точек входа читают её же, разными методами и
  фильтрами) и не может; ничего не записывается ни в одной из веток этого
  сценария — все пять затронутых чтений (`getCurrentDevices`/`getAllDevices`,
  `getEnabledOperationTypes`, `getSavedRegion`, `getSavedPower`,
  `getSavedAntennas`) — чистые `SELECT`, без побочных эффектов на данные.
- `User` ([ENT-1](../entities/ENT-1-USER-IN-AUTH.md), AUTH) и `Kind`
  ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md), HANDBOOKS) — **не
  читаются и не изменяются** этим сценарием ни в одной из веток: в отличие
  от [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md)/[EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md)
  этого же модуля, весь путь `DeviceSettingsRepository` для локального
  чтения (в отличие от сетевого push/pull, см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md))
  не обращается ни к одной другой таблице.

### Бизнес-правила

- Каталог из 13 устройств пересевается идемпотентно на **каждый** вызов
  `getCurrentDevices()` (`ensureDeviceInDatabase()` перед чтением, не
  отдельным шагом при первом запуске) — то есть отказ мог произойти как во
  время этого пересева (несколько write-вызовов подряд), так и во время
  финального `dao.getAllDevices()`; из-за отсутствия логирования на каждом
  шаге вызывающий код не может отличить одно от другого.
- Ни на одном из пяти независимых call site'ов (грид,
  `ScannerOperationsSettingsWidget`, `RegionSelectorWidget`,
  `SelectPowerSlider`, `ScannerAntennasSettingsWidget`) не смоделировано
  отдельного «состояния ошибки» — единственное состояние, которое умеет
  различать `build()` каждого из этих виджетов, это «значение ещё `null`»
  (интерпретируется как «загрузка идёт») против «значение получено» —
  тождество «ещё грузится» и «никогда не загрузится» не различается нигде
  в этой части кода.
- Данные устройства не привязаны к аккаунту (не `@Clearable`, см.
  [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)) — этот отказ не
  зависит от авторизации: гость и авторизованный пользователь видят
  идентичное поведение на одном и том же физическом устройстве приложения.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (непойманное
исключение в `DeviceSettingsRepository.getCurrentDevices()`/`getAllDevices()`
→ `FutureBuilder` без ветки `hasError` → бесконечный
`CircularProgressIndicator`, без единой строки лога) полностью
воспроизводится статическим чтением кода:
`DevicesSettingsPage.initState` → `DeviceSettingsRepository.getCurrentScannerDevices`
→ `.getCurrentDevices` → `DevicesDao.getAllDevices`/`ensureDeviceInDatabase`.
Независимо проверенная под-ветка (тот же дефект в четырёх виджетах формы
устройства) прослежена так же — статическим чтением каждого из
`ScannerOperationsSettingsWidget`/`RegionSelectorWidget`/`SelectPowerSlider`/`ScannerAntennasSettingsWidget`.
Ни один из пяти путей не подтверждён запущенным тестом (см. «Связанные
тесты» — тестов на этот модуль нет вовсе). Исправление (например,
`try/catch` в `DeviceSettingsRepository`, отдельная ветка `hasError` в
каждом `FutureBuilder`/ручном чтении `initState()`, единый паттерн
loading/error/data вместо голого `if (value == null)`) в рамках этого
документирующего прохода не выполняется — это фиксация уже существующего
кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.getCurrentDevices`, `.getCurrentScannerDevices`, `.ensureDeviceInDatabase`, `.getEnabledOperationTypes`, `.getSavedRegion`, `.getSavedPower`, `.getSavedAntennas`, `.getSavedAddress`, `.getScannerDeviceByType`, `.getDeviceByType` | CURRENT | весь read-путь этого сценария — ни один метод не содержит `try/catch` |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao.getAllDevices`, `.findDeviceByType`, `.findDevicesByType`, `.getDeviceById`, `.deleteDeviceById`, `.insertDevice`, `.updateDeviceById`, `.deleteDevicesByTypes` | CURRENT | сырые Drift-запросы, источник технического исключения |
| `lib/repositories/base_repository.dart` | `BaseRepository.dao` | CURRENT | `getIt<AppDatabase>().getDaoByType<BD>()` — синхронный резолв при конструировании репозитория, без своего `try/catch`; предполагается уже успешным к моменту этого сценария |
| `lib/injection_container.dart` | `getIt.registerLazySingleton<DeviceSettingsRepository>` | CURRENT | единственный экземпляр репозитория на весь процесс |
| `lib/pages/scanner_settings/pages/devices_settings_page.dart` | `_DevicesSettingsPageState.initState`, `._refreshDevices`, `.build` (`FutureBuilder`) | CURRENT | предмет основного потока — `builder` не читает `snapshot.hasError`/`.error` ни разу |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_ScannerSettingsPageState._save` | CURRENT | пятая точка вызова того же непойманного чтения (`getSavedAntennas`), внутри fire-and-forget `onTap` |
| `lib/widgets/button/button.dart` | `BlackCircleButton.onTap` (`VoidCallback`) | CURRENT | `_save`'s `Future` не ожидается вызывающей стороной — источник «немого» отказа кнопки в альтернативном потоке (в) |
| `lib/pages/scanner_settings/widgets/scanner_operations_settings_widget.dart` | `_ScannerOperationsSettingsWidgetState._loadSettings`, `.build` | CURRENT | тот же паттерн `if (value == null) CircularProgressIndicator()`, рендерится для всех шести видов форм устройства |
| `lib/pages/scanner_settings/widgets/region_selector_widget.dart` | `_RegionSelectorWidgetState.initSettings`, `.build` | CURRENT | тот же паттерн, пять из шести видов |
| `lib/pages/scanner_settings/widgets/select_power_slider.dart` | `_SelectPowerSliderState.initSettings`, `.build` | CURRENT | тот же паттерн, те же пять видов |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `_ScannerAntennasSettingsWidgetState._loadAntennas`, `.build`; `_ScannerAddressSettingsWidgetState._loadAddress` | CURRENT | антенны — тот же паттерн (четыре вида); адрес — иная, молчаливая деградация без спиннера |
| `lib/pages/scanner_settings/widgets/is_use_camera_for_qr_check_box_widget.dart` | `_IsUseCameraForQrCheckBoxWidgetState.initState` | CURRENT | контрастный случай — не читает БД повторно, не затронут этим сценарием |
| `lib/pages/scanner_settings/widgets/tcd_action_selectors_widget.dart` | `_TcdActionSelectorsWidgetState.initState` | CURRENT | тот же контраст — не затронут |
| `lib/pages/profile_settings/presentation/work_settings_page.dart` | `WorkSettingsPage.build`, `WorkSettingsItem` («Настройки устройств») | CURRENT | точка входа — рендерится безусловно, без проверки авторизации |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` («Настройки работы») | CURRENT | предшествующая точка входа — тоже без проверки авторизации, в отличие от `_ProfileSettingsButtons` (см. [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)) |
| `lib/main.dart` | `main()` (`runZonedGuarded`/`runTalkerZonedGuarded` закомментирован) | CURRENT | причина, по которой это исключение не логируется вообще нигде, даже для разработчика |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `Devices` (таблица) | CURRENT | физическое хранилище, чтение которого отказывает в этом сценарии |

## Критерии приёмки

- Если любой Drift-вызов внутри `ensureDeviceInDatabase()`/`dao.getAllDevices()`
  бросает исключение, `DeviceSettingsRepository.getCurrentDevices()`/`getCurrentScannerDevices()`
  пробрасывают его необработанным — ни в репозитории, ни в `DevicesDao`, ни в
  `BaseDao`/`BaseRepository` нет ни одного `try/catch` на этом пути.
- `DevicesSettingsPage`'s `FutureBuilder` не содержит ветки, читающей
  `snapshot.hasError`/`snapshot.error` — при отказе `snapshot.hasData`
  остаётся `false` бессрочно, и экран показывает `CircularProgressIndicator`
  вместо грида без ограничения по времени.
- Это исключение не появляется ни в `Talker`, ни в `dart:developer`, ни
  консольной записью об необработанной асинхронной ошибке — потому что
  `FutureBuilder` присоединяет `onError`-обработчик (что «поглощает» ошибку
  на уровне `Future`), а `runZonedGuarded`/`runTalkerZonedGuarded` в
  `main()` закомментирован.
- Тот же класс дефекта (непойманное чтение → `if (value == null)
  CircularProgressIndicator()` бессрочно) независимо воспроизводится в
  `ScannerOperationsSettingsWidget` (все шесть видов форм устройства), в
  `RegionSelectorWidget`/`SelectPowerSlider` (пять из шести видов) и в
  `ScannerAntennasSettingsWidget` (четыре вида, требующих антенны) — для
  типа устройства, требующего антенны, при независимом отказе всех
  соответствующих чтений форма показывает до четырёх одновременных
  бессрочных спиннеров.
- `ScannerAddressSettingsWidget` при том же отказе деградирует иначе — без
  проверки `null` в `build()`, оставляя текстовое поле пустым, неотличимо
  от легитимного «адрес ещё не задан».
- `IsUseCameraForQrCheckBoxWidget` и `TcdActionSelectorsWidget` не читают
  БД повторно в своём `initState()` (используют уже переданный
  `widget.device.settings`) и этим отказом не затрагиваются.
- Если тот же непойманный вызов (`getSavedAntennas`) отказывает внутри
  `ScannerSettingsPage._save()` для типа устройства, требующего антенны,
  нажатие кнопки «Сохранить» не производит никакого видимого эффекта: ни
  снекбара `must_select_antenns`, ни `context.pop()`, ни лога где-либо.
- Единственный способ повторить попытку чтения — полностью покинуть
  `DevicesSettingsPage`/`ScannerSettingsPage` (пересоздание `State`) и
  открыть экран заново; ни на одном из пяти затронутых виджетов нет
  встроенной кнопки «повторить».

## Связанные тесты

`grep -rln "getCurrentScannerDevices\|getEnabledOperationTypes\|getSavedAntennas\|getSavedRegion\|getSavedPower\|getSavedAddress\|DevicesSettingsPage\|ScannerSettingsPage\|ScannerAntennasSettingsWidget\|ScannerOperationsSettingsWidget\|RegionSelectorWidget\|SelectPowerSlider\|ScannerAddressSettingsWidget" test/`
находит единственный файл — `test/pages/scanning_bloc_test.dart`. Он мокает
`DeviceSettingsRepository` (`MockDeviceSettingsRepository`) как зависимость
`ScanningBloc` (модуль `INV`, не `PROFILE`) и стабит на нём только
`ensureDeviceInDatabase`, `getDefaultDevices`, `getSavedAntennas`,
`getSavedAddress`, `updateAntennasInStorage`, `updateAddressInStorage` — во
всех случаях как штатно успешные вызовы (`thenAnswer`/`thenReturn`), ни
разу не как бросающие исключение. Он не тестирует ни `DevicesSettingsPage`,
ни `ScannerSettingsPage`, ни `getCurrentDevices`/`getCurrentScannerDevices`/`getScannerDeviceByType`/`getEnabledOperationTypes`/`getSavedRegion`/`getSavedPower`,
ни любой из виджетов формы (`ScannerOperationsSettingsWidget`/`RegionSelectorWidget`/`SelectPowerSlider`/`ScannerAntennasSettingsWidget`/`ScannerAddressSettingsWidget`) —
это тест другой фичи (сканирование при инвентаризации), несвязанной с
экраном настроек устройств.

Отдельного файла на `DeviceSettingsRepository`/`DevicesSettingsPage`/`ScannerSettingsPage`
в репозитории нет (`find test -iname "*device*"`, `find test -iname
"*scanner_setting*"` — оба пустые).

**TBD — теста нет** на сценарий, описанный этим файлом: ни на основной
поток (непойманное исключение в `getCurrentDevices()`/`getAllDevices()` →
бессрочный спиннер в `DevicesSettingsPage` без единого лога), ни на
альтернативный поток (а) (повтор того же отказа при `_refreshDevices()`),
ни на (б) (независимое воспроизведение того же дефекта в
`ScannerOperationsSettingsWidget`/`RegionSelectorWidget`/`SelectPowerSlider`/`ScannerAntennasSettingsWidget`,
и контрастную деградацию `ScannerAddressSettingsWidget`), ни на (в) (немой
no-op кнопки «Сохранить» при отказе повторной проверки антенн).

## Открытые вопросы и ограничения

- **Полное отсутствие обработки ошибок на всём пути (`DeviceSettingsRepository`
  → `DevicesDao` → `BaseDao`/`BaseRepository`) — недосмотр или осознанное
  решение «на этом экране сбой Drift невозможен»?** Ничем в коде/комментариях
  не зафиксировано. Контраст с соседним `READ_ERROR` этого же модуля
  ([UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)), где хотя
  бы кубит перехватывает и логирует ошибку (просто UI её не показывает) —
  здесь перехвата нет вообще ни на одном уровне.
- **`runZonedGuarded`/`runTalkerZonedGuarded` закомментирован в `main.dart`
  — тот же факт, что уже отмечен в [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)
  для отдельного, не связанного с этим подсистемного пути (BOARD/Hive).**
  Подтверждено здесь для совершенно другой подсистемы (PROFILE/Drift) —
  указывает на то, что это ограничение сквозное для всего приложения, а не
  специфичное для одного модуля.
- **Пять независимых точек одного и того же класса дефекта в одном
  небольшом разделе UI** (`DevicesSettingsPage` + четыре виджета формы) —
  не сведены к общему компоненту/паттерну загрузки; правка в одном месте
  (например, добавление `try/catch` в `DeviceSettingsRepository`) не
  устранит остальные четыре, пока каждый виджет продолжает интерпретировать
  `null` как «загрузка», а не «загрузка или отказ».
- **Невозможно отличить постфактум, какой именно из вложенных вызовов
  внутри `ensureDeviceInDatabase()`/`getAllDevices()` бросил исключение** —
  ни один промежуточный шаг не логируется отдельно.
- Не проверено эмпирически на реальном отказавшем sqlite3/drift-соединении —
  вывод сделан статическим чтением кода; единственный существующий тест,
  трогающий `DeviceSettingsRepository`
  (`test/pages/scanning_bloc_test.dart`), мокает все его методы как
  всегда успешные и относится к отдельной фиче (`INV`), не к этому модулю.
- Не проверено эмпирически, приводит ли реальный отказ Drift-соединения к
  одновременному отказу всех четырёх независимых чтений в форме одного
  устройства (правдоподобно, так как это один и тот же `NativeDatabase`) —
  или возможен частичный отказ, когда часть из четырёх запросов проходит
  успешно, а часть — нет; альтернативный поток (б) прослеживает оба случая
  как структурно возможные, не разделяя их по вероятности.
