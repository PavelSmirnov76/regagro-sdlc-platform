# UC-180 — Сохранение настройки сканирующего устройства технически отказывает: необработанное исключение проходит по-разному через каждую из семи точек записи

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же набор точек записи, что описан в [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) —
`DeviceSettingsRepository.updateAddressInStorage`/`updateAntennasInStorage`/
`updatePowerInDatabase`/`updateRegionInDatabase`/`updateIsUseCameraForQrInDatabase`/
`updateDeviceOperationUsage`/`updateDeviceButtonAction`. Здесь описан
технический отказ самой записи — исключение, брошенное `DevicesDao.findDeviceByType`
или `DevicesDao.updateDeviceById` (Drift-слой над sqlite3,
`packages/sheep_farm_database/lib/entities/devices/devices_dao.dart`), например
из-за повреждённого файла БД, переполнения диска или конфликта с параллельной
транзакцией того же `AppDatabase` — не бизнес-отказа (антенны не выбраны для
типа, которому они обязательны, — отдельный, осознанно отклоняющий сценарий,
не этот файл).

**Ни один из семи методов `DeviceSettingsRepository`, перечисленных выше, не
содержит `try`/`catch` внутри себя** — подтверждено чтением
`lib/repositories/devices_settings/devices_settings_repository.dart` целиком.
Что происходит с исключением дальше, зависит исключительно от того, какой
именно виджет вызвал метод — проверено отдельно для каждого из семи вызывающих
мест:

- **(а) шесть из семи** (`updateAddressInStorage`, `updateAntennasInStorage`,
  `updatePowerInDatabase`, `updateRegionInDatabase`,
  `updateIsUseCameraForQrInDatabase`, `updateDeviceOperationUsage`) вызываются
  из виджетов как `async`-функция, присвоенная параметру, типизированному
  синхронным колбэком (`ValueChanged<T>`/`ValueChanged<T>?` — `Switcher.onChanged`,
  `RDropDownButton.onChanged`, `RTextField.outline.onChanged`, `Slider.onChangeEnd`),
  **без единого `try`/`catch` по всей цепочке** (ни в репозитории, ни в
  виджете). Фреймворк вызывает такой колбэк синхронно и не ждёт
  возвращаемый `Future` — при броске исключения это необработанная ошибка
  `Future`, которую некому перехватить: `runApp` в `lib/main.dart` не обёрнут
  в `runZonedGuarded` (соответствующий вызов закомментирован — тот же факт,
  что уже задокументирован в
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) для другого
  сценария), поэтому ошибка уходит в обработчик корневой зоны Dart по
  умолчанию — не в `Talker`, не в `DataUpdates`, не в какой-либо снекбар/UI.
- **(б) седьмой** (`updateDeviceButtonAction`) — единственная точка, где
  вызывающий виджет (`TcdActionSelectorsWidget._updateDeviceAction`)
  оборачивает вызов в собственный `try`/`catch`, перехватывает исключение и
  логирует его через `getIt<Talker>().handle(e, st, 'Failed to update TCD
  button action')` — не перебрасывает и не показывает пользователю. Тот же
  практический итог для пользователя (тишина), но с записью в `Talker`,
  которой нет ни у одной из шести веток (а).

В обоих случаях UI не показывает пользователю расхождение между тем, что он
видит на экране, и тем, что реально записано в `Devices` — детали различаются
по виджету (оптимистичный `setState` до `await` у одних, отложенный после
`await` у других) и разобраны отдельно ниже.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость и авторизованный проходят один и тот же код, без route-guard, как и во
всём разделе PROFILE). Открывает `/profile/work_settings/devices_settings/scanner_settings`
(`ScannerSettingsPage`) для одного устройства либо через `_GroupOperationsContent`
для группы bluetooth-устройств разом ([EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md)),
меняет один параметр — адрес, антенны, мощность, регион, чекбокс камеры QR,
разрешённую операцию или действие кнопки TCD. Сам отказ — технический,
происходит внутри вызова к локальной БД, не требует какого-либо отдельного
действия пользователя сверх обычного изменения значения виджета.

## CURRENT

### Основной поток

1. Пользователь меняет значение одного из полей на `ScannerSettingsPage` —
   например перетаскивает `Slider` мощности до конца (`onChangeEnd`), выбирает
   регион в `RDropDownButton`, переключает `Switcher` антенны/операции/камеры,
   вводит адрес в `RTextField.outline`, либо выбирает действие кнопки в
   `RDropDownButton` формы TCD.
2. Виджет вызывает соответствующий метод `DeviceSettingsRepository` —
   см. таблицу в «Технические зависимости» за полным списком пар
   виджет→метод.
3. Внутри метода — общий паттерн: `final device = await dao.findDeviceByType(type);
   if (device != null) { await dao.updateDeviceById(device.id, companion); }`
   (для `updateDeviceOperationUsage` — тот же вызов `dao.findDeviceByType` через
   `getEnabledOperationTypes`; для `updateDeviceButtonAction` — структурно то
   же самое, плюс досрочный `return` с `Talker.info`, если устройство не
   найдено). **Ни один из семи методов не содержит `try`/`catch`** —
   подтверждено чтением `lib/repositories/devices_settings/devices_settings_repository.dart`
   целиком.
4. В этом сценарии `dao.findDeviceByType`/`dao.updateDeviceById`
   (`packages/sheep_farm_database/lib/entities/devices/devices_dao.dart`) бросает
   исключение — гипотетически, например `SqliteException` при повреждении
   локального файла БД/переполнении диска, либо конфликт с параллельной
   транзакцией того же `AppDatabase` (не воспроизведено против реально
   повреждённой БД — вывод сделан статическим чтением кода, метод не
   содержит собственной защиты ни от одной из этих причин). Поскольку метод
   репозитория не перехватывает исключение, оно покидает его необработанным
   и достигает вызвавшего виджета.
5. Дальнейшая судьба исключения зависит от того, какой именно из семи
   вызывающих виджетов его вызвал — каждый проверен отдельно чтением кода.

**Ветка (а) — шесть точек записи: исключение остаётся полностью
необработанным.**

6а. `_ScannerAddressSettingsWidgetState` (`scanner_settings_views.dart`):
    `onChanged: (value) => _repository.updateAddressInStorage(widget.device.type,
    value)` — присвоено `RTextField.outline.onChanged`, типизированному
    `ValueChanged<String>?` (`void Function(String)`,
    `lib/widgets/text_field/text_field.dart`). Возвращаемое значение колбэка
    (в данном случае `Future<void>`) отбрасывается — Dart допускает это
    неявно (функция, возвращающая не-`void`, совместима с местом, ожидающим
    `void`). `RTextField` вызывает этот колбэк синхронно и не ждёт его
    завершения. Поле ввода не имеет отдельного состояния «сохранено» —
    значение в `TextEditingController` остаётся тем, что ввёл пользователь,
    независимо от исхода записи в БД.
7а. `_ScannerAntennasSettingsWidgetState._toggleAntenna` (тот же файл):
    `setState(() => _antennas = updated);` вызывается **до** `await
    _repository.updateAntennasInStorage(...)` — UI уже показывает антенну
    выбранной/снятой в момент, когда запись в БД ещё не завершилась (и может
    не завершиться вовсе).
8а. `_SelectPowerSliderState.setPower` (`select_power_slider.dart`), вызывается
    из `Slider.onChangeEnd: (double value) async { ...; await setPower(...); }` —
    `onChangeEnd` типизирован `ValueChanged<double>?`, тем же образом
    отбрасывается фреймворком. `_currentValue` уже обновлён локальным
    `setState` внутри `Slider.onChanged` (вызывается на каждое промежуточное
    перетаскивание, до `onChangeEnd`) — слайдер визуально показывает целевое
    значение независимо от того, была ли персистентная запись
    (`updatePowerInDatabase`) успешной. Дополнительно: `tryApplyGatesBlePower`
    (реальное применение к железу для `bluetooth_gates`) вызывается **после**
    `updatePowerInDatabase` в том же теле `setPower` — если запись в БД
    бросает исключение, эта строка тоже не достигается.
9а. `_RegionSelectorWidgetState` (`region_selector_widget.dart`):
    `onChanged: (region) async { if (region != null) { await
    _scannerSettingsRepository.updateRegionInDatabase(...); if (...bluetoothGates)
    await tryApplyGatesBleRegion(...); } setState(() => _currentValue =
    region?.index); }` — здесь `setState` стоит **после** `await`, вне `if`.
    Если `updateRegionInDatabase` бросает исключение, ни `tryApplyGatesBleRegion`,
    ни финальный `setState` не достигаются — `_currentValue` остаётся прежним,
    дропдаун при следующей перерисовке покажет старое значение, как если бы
    пользователь не менял выбор вовсе (без какого-либо сообщения о причине).
10а. `_IsUseCameraForQrCheckBoxWidgetState` (`is_use_camera_for_qr_check_box_widget.dart`):
    `onChanged: (bool? value) async { await
    getIt<DeviceSettingsRepository>().updateIsUseCameraForQrInDatabase(...);
    setState(() { _isUseCameraForQr = value; }); }` — тот же порядок, что и у
    региона: `setState` после `await`. При исключении переключатель не
    получает новое состояние в `State`, следующая перерисовка покажет
    прежнее значение.
11а. `_ScannerOperationsSettingsWidgetState._updateOperation`
    (`scanner_operations_settings_widget.dart`): `setState(() =>
    _enabledOperationTypes = updated);` — **до** цикла `for (final type in
    types) { await _repository.updateDeviceOperationUsage(...); }`, где
    `types = widget.applyToTypes ?? [widget.device.type]`. UI уже показывает
    операцию включённой/выключенной для всего представления виджета
    независимо от исхода цикла (см. также «Альтернативные потоки» —
    групповое применение обрывается посередине).
12а. Во всех шести случаях исключение, брошенное внутри `async`-функции,
    присвоенной синхронно типизированному колбэку, становится необработанной
    ошибкой `Future` — фреймворк-виджет (`Switch`/`Slider`/`DropdownButton`/
    `TextField`) вызывает колбэк и не ждёт его результат. Поскольку `runApp`
    в `lib/main.dart` не обёрнут в `runZonedGuarded` (вызов закомментирован),
    эта ошибка обрабатывается зоной Dart по умолчанию — не проходит ни через
    `Talker`, ни через `FlutterError.onError`/`PlatformDispatcher.instance.onError`
    (эти хуки покрывают ошибки в build/layout/paint/gesture, не произвольный
    необработанный `Future` из прикладного кода), ни через любой видимый
    пользователю канал. Наблюдаемый пользователем итог — изменение поля либо
    выглядит применённым (антенны, операции, мощность — за счёт
    оптимистичного/промежуточного `setState`), либо тихо не происходит без
    объяснения (адрес, регион, камера QR — без видимой ошибки, просто
    следующая перерисовка показывает старое значение или, для адреса, само
    поле не имеет визуального признака «не сохранено» вовсе).

**Ветка (б) — седьмая точка записи (`updateDeviceButtonAction`): исключение
перехвачено, но проглочено.**

6б. `_TcdActionSelectorsWidgetState._updateDeviceAction` (`tcd_action_selectors_widget.dart`)
    — единственный из семи вызывающих мест, где вызов обёрнут:
    `try { await _deviceSettingsRepository.updateDeviceButtonAction(...); await
    getIt<ScannerService>().applyTerminalButtonActions(); } catch (e, st) {
    getIt<Talker>().handle(e, st, 'Failed to update TCD button action'); }`.
7б. Если `updateDeviceButtonAction` бросает исключение — на этом же общем
    основании (шаг 4) — оно перехватывается этим `catch`, логируется через
    `Talker.handle`, не перебрасывается дальше и не показывается
    пользователю никаким снекбаром/диалогом. `setState`, обновляющий
    `_leftButtonAction`/`_middleButtonAction`/`_rightButtonAction`, в этом
    виджете вызывается **до** вызова `_updateDeviceAction` (в обработчике
    `onChanged` дропдауна, `if (newValue != null && newValue !=
    _leftButtonAction) { setState(() => _leftButtonAction = newValue); ...
    }`) — то есть UI уже показывает выбранное действие кнопки независимо от
    исхода записи, как и в ветке (а).
8б. Практический итог для пользователя — та же тишина, что и в ветке (а);
    единственная разница — эта ветка оставляет след в `Talker`-логе
    (доступном через встроенный просмотрщик логов, если пользователь туда
    зайдёт), тогда как ни одна из шести веток (а) не оставляет никакого
    следа нигде.

### Альтернативные потоки

- **Групповое применение обрывается посередине.** Когда `ScannerOperationsSettingsWidget`
  открыт для группы bluetooth-устройств (`_GroupOperationsContent`,
  `applyToTypes` содержит несколько типов), `_updateOperation` вызывает
  `updateDeviceOperationUsage` **последовательно в цикле**, без
  `try`/`catch` вокруг тела цикла. Если запись для одного из типов бросает
  исключение, цикл прерывается на этой итерации — оставшиеся типы группы
  вообще не пытаются записаться, без какого-либо сигнала, какие именно
  устройства группы реально применили изменение, а какие нет; единственное
  состояние `_enabledOperationTypes` виджета уже было обновлено
  оптимистично для всех типов разом до начала цикла (шаг 11а), так что UI не
  может показать это расхождение по отдельным устройствам группы даже в
  принципе.
- **`updateDeviceButtonAction` не находит устройство.** Отдельно от
  технического отказа записи — если `dao.findDeviceByType(deviceType)`
  возвращает `null` (устройство ещё не засеяно `ensureDeviceInDatabase()`),
  метод логирует `Talker.info(...)` и делает `return` **до** какой-либо
  попытки записи — не исключение, а штатная ранняя остановка; не
  относится к этому сценарию (нет брошенного исключения), упомянуто здесь
  только чтобы отличить от ветки (б).
- **`REJECTED`-ветка существует отдельно и не описывается здесь.**
  `ScannerSettingsPage._save` содержит осознанный бизнес-отказ — если для
  типа, которому обязательны антенны (`_isAntennasRequired`), их набор пуст,
  форма не закрывается и показывается `showAppSnackBarError(context,
  context.tr('must_select_antenns'))` — операция дошла до кода и была
  сознательно отклонена бизнес-правилом, а не провалилась технически.
  Ни одна из семи точек записи полей, разобранных в этом файле, не участвует
  в этой проверке — она происходит независимо, при закрытии формы, не при
  изменении отдельного поля.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность, чьё физическое состояние (таблица `Devices`) должно было
  измениться этим сценарием, но не меняется: при отказе `dao.updateDeviceById`
  вся строка (включая `isNeedUpdate`/`updatedAt`, которые проставляются той
  же самой `write`-операцией) остаётся такой, какой была до попытки —
  каждый вызов атомарен на уровне одного Drift `update...write()`, частичной
  записи одного поля без остальных не бывает.

### Бизнес-правила

- Ни один из семи путей записи не имеет состояния «сохранение…»/«не
  сохранено» на уровне UI — сохранение полностью fire-and-forget по
  архитектуре виджетов (шесть путей) либо перехвачено только для внутреннего
  лога, не для пользователя (седьмой путь, TCD).
- Нет ретрая — отказавшая попытка не повторяется автоматически; следующая
  попытка произойдёт только если пользователь снова изменит то же поле.
- Единственная асимметрия во всём наборе из семи методов — `updateDeviceButtonAction`
  вызывается из места с `try`/`catch` (ветка б), тогда как остальные шесть —
  нет; ничем в коде/комментариях эта асимметрия не объяснена и не выглядит
  намеренным архитектурным решением.

## TARGET

TARGET не отличается от CURRENT — это документирующий проход по уже
существующему дефекту, не работа над исправлением.

## TBD / BLOCKED

Блокеров для документирования нет. Все семь путей (шесть необработанных,
один перехваченный-но-проглоченный) воспроизводятся статическим чтением кода
целиком: `DeviceSettingsRepository.update*`/`updateDeviceButtonAction`/
`updateDeviceOperationUsage` → `DevicesDao.findDeviceByType`/`updateDeviceById` →
семь вызывающих виджетов в `lib/pages/scanner_settings/widgets/`. Ни один
путь не проверен эмпирически против реально повреждённой локальной БД —
причина исключения (`SqliteException`/конфликт транзакции/переполнение
диска) гипотетическая, сама возможность исключения из Drift-слоя и
отсутствие перехвата в прикладном коде — факт, подтверждённый чтением.
Исправление (например, единообразная обёртка всех семи вызовов в
`try`/`catch` с видимым снекбаром отказа, откат оптимистичного `setState`
при ошибке) в рамках этого документирующего прохода не выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `updateAddressInStorage`, `updateAntennasInStorage`, `updatePowerInDatabase`, `updateRegionInDatabase`, `updateIsUseCameraForQrInDatabase`, `updateDeviceOperationUsage`, `updateDeviceButtonAction` | CURRENT | все семь методов записи одного параметра устройства — ни один не содержит `try`/`catch` |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao.findDeviceByType`, `.updateDeviceById` | CURRENT | Drift-вызовы, из которых предположительно исходит исключение этого сценария; без собственной защиты от ошибок sqlite3 |
| `lib/pages/scanner_settings/widgets/scanner_settings_views.dart` | `_ScannerAddressSettingsWidgetState` (`onChanged`), `_ScannerAntennasSettingsWidgetState._toggleAntenna` | CURRENT | ветка (а) — адрес (fire-and-forget без своего состояния), антенны (оптимистичный `setState` до `await`) |
| `lib/pages/scanner_settings/widgets/select_power_slider.dart` | `_SelectPowerSliderState.setPower`, `Slider.onChangeEnd` | CURRENT | ветка (а) — `_currentValue` уже обновлён промежуточным `onChanged` до вызова `setPower`; `tryApplyGatesBlePower` не достигается при отказе |
| `lib/pages/scanner_settings/widgets/region_selector_widget.dart` | `_RegionSelectorWidgetState` (`RDropDownButton.onChanged`) | CURRENT | ветка (а) — `setState` идёт после `await`, при отказе не достигается, дропдаун остаётся на прежнем значении |
| `lib/pages/scanner_settings/widgets/is_use_camera_for_qr_check_box_widget.dart` | `_IsUseCameraForQrCheckBoxWidgetState` (`Switcher.onChanged`) | CURRENT | ветка (а) — `setState` после `await`, тот же эффект, что у региона |
| `lib/pages/scanner_settings/widgets/scanner_operations_settings_widget.dart` | `_ScannerOperationsSettingsWidgetState._updateOperation` | CURRENT | ветка (а) — оптимистичный `setState` до цикла по `applyToTypes`; цикл обрывается на первом отказавшем типе без `try`/`catch` |
| `lib/pages/scanner_settings/widgets/tcd_action_selectors_widget.dart` | `_TcdActionSelectorsWidgetState._updateDeviceAction` | CURRENT | ветка (б) — единственная точка с `try`/`catch`, логирует через `Talker.handle`, не перебрасывает, не показывает пользователю |
| `lib/widgets/radio/switcher.dart` | `Switcher.onChanged` (`ValueChanged<bool>`) | CURRENT | синхронно типизированный колбэк — вызывается без ожидания возвращаемого `Future` |
| `lib/widgets/drop_down_button/drop_down_button.dart` | `RDropDownButton.onChanged` (`ValueChanged<T?>?`) | CURRENT | тот же паттерн для дропдаунов (регион, действия кнопок TCD) |
| `lib/widgets/text_field/text_field.dart` | `RTextField.onChanged` (`ValueChanged<String>?`) | CURRENT | тот же паттерн для поля адреса |
| `lib/main.dart` | `main()` (`runApp` без `runZonedGuarded`, строка закомментирована) | CURRENT | причина, по которой необработанная ошибка `Future` из любой ветки (а) не попадает ни в один видимый канал — тот же факт, что уже задокументирован в [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) |
| `lib/services/scanner_service.dart` | `ScannerService.applyTerminalButtonActions`, `.tryApplyGatesBlePower`, `.tryApplyGatesBleRegion` | CURRENT | применение «на лету» к реальному оборудованию — во всех трёх случаях вызывается после (возможно отказавшей) записи в БД, в одном и том же теле функции, без отдельной защиты от отказа предыдущего шага |
| `lib/pages/scanner_settings/pages/scanner_settings_page.dart` | `_ScannerSettingsPageState._save`, `._isAntennasRequired` | CURRENT | место осознанного бизнес-отказа (`must_select_antenns`) — контраст, не часть этого сценария, см. «Альтернативные потоки» |

## Критерии приёмки

- Если `dao.findDeviceByType`/`dao.updateDeviceById` бросает исключение
  внутри одного из шести методов ветки (а) (`updateAddressInStorage`,
  `updateAntennasInStorage`, `updatePowerInDatabase`, `updateRegionInDatabase`,
  `updateIsUseCameraForQrInDatabase`, `updateDeviceOperationUsage`),
  исключение остаётся необработанным на всех уровнях (репозиторий → виджет →
  фреймворк-колбэк) — ни `Talker`, ни снекбар, ни `DataUpdates`, ни любой
  другой канал не фиксируют отказ; изменённое поле не сохраняется в
  `Devices`.
- Если то же исключение бросает `updateDeviceButtonAction`, оно
  перехватывается `try`/`catch` внутри `TcdActionSelectorsWidget._updateDeviceAction`
  и логируется через `Talker.handle`, но не перебрасывается и не
  показывается пользователю — та же практическая невидимость для
  пользователя, что и в ветке (а), с единственной разницей — записью в
  Talker-логе.
- В обеих ветках изменённое поле визуально может выглядеть применённым
  (антенны, операции, мощность, действия кнопок TCD — за счёт
  `setState`, вызванного до или независимо от `await`) либо остаться
  незаметно на прежнем значении при следующей перерисовке (адрес, регион,
  чекбокс камеры QR — `setState` идёт после `await`, которое не
  завершается) — ни один из семи путей не показывает пользователю
  расхождение между UI и фактическим состоянием `Devices`.
- Для группового применения (`applyToTypes` с несколькими типами устройств)
  — если запись для одного из типов внутри цикла `_updateOperation` бросает
  исключение, обработка последующих типов этого же цикла прерывается;
  оставшиеся устройства группы не получают изменение, без какого-либо
  сигнала, какие именно типы применились, а какие нет.

## Связанные тесты

**TBD — теста нет.** `find test -iname "*device*"` и `find test -iname
"*scanner*"` не находят ни одного файла. `grep -rl
"DeviceSettingsRepository|ScannerSettings|scanner_settings" test/` находит
только `test/blocs/data_update_bloc_test.dart` и `test/pages/scanning_bloc_test.dart` —
в обоих `DeviceSettingsRepository` присутствует исключительно как
замоканная зависимость несвязанного блока (`DataUpdateBloc`, `ScanningBloc`),
ни один тест не вызывает и не проверяет ни один из семи методов записи
самого репозитория, ни один из семи виджетов `lib/pages/scanner_settings/widgets/`.
Отдельного файла `test/repositories/devices_settings_repository_test.dart`
не существует.

## Открытые вопросы и ограничения

- **Историческая, не авторитетная параллель.** Тот же по существу дефект
  (под старой нумерацией id, до полной пересборки дерева спек) уже был
  кратко задокументирован в
  `sdlc-deprecated/2-specs/use-cases/UC-282-ACTOR-1-EVT-135-ENT-17-UPDATE_ERROR-IN-PROFILE.md`
  одной строкой: «ни один из семи `update*`-методов... не обёрнут в
  try/catch... ни один из виджетов-настроек тоже не ловит его». Тот документ
  не различал семь точек записи между собой и не заметил единственное
  исключение — `updateDeviceButtonAction`/`TcdActionSelectorsWidget`,
  которое на самом деле перехватывается (ветка б, разобрана отдельно в этом
  файле). Упоминается здесь только как исторический контекст, не как
  авторитетная ссылка на живой артефакт (`sdlc-deprecated/` не используется
  как источник для нового дерева).
- **Асимметрия между веткой (а) и веткой (б) ничем не объяснена.** Не
  зафиксировано ни в коде, ни в комментариях, было ли решение обернуть
  именно `updateDeviceButtonAction` (и только его) в `try`/`catch`
  осознанным (например, из-за соседнего вызова `applyTerminalButtonActions()`,
  который реально может бросать при недоступном оборудовании) или
  случайным следствием того, что этот виджет писался/правился отдельно от
  остальных шести.
- **Не проверено эмпирически.** Вывод сделан статическим чтением кода
  (`DeviceSettingsRepository.update*` → `DevicesDao.findDeviceByType`/
  `.updateDeviceById`) — ни один тест и ни один ручной прогон не
  воспроизводит реальное исключение Drift/sqlite3 на этом пути (см.
  «Связанные тесты» — TBD). Точная причина, по которой `dao.updateDeviceById`
  реально может бросить исключение на устройстве пользователя (повреждение
  файла БД, переполнение диска, конфликт транзакций), этой спекой не
  подтверждена, только структурно допущена.
- Зависит от того же факта об отсутствии `runZonedGuarded` в `main.dart`,
  что и [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) — если
  этот вызов когда-либо будет раскомментирован, поведение всех шести веток
  (а) изменится одновременно (ошибки начнут перехватываться на уровне
  зоны), без единого изменения в файлах `lib/pages/scanner_settings/`.
