# UC-185 — Sync-проход перезагружает устройства с сервера: полная замена локальной таблицы, remoteId впервые попадает в строки, isNeedUpdate сбрасывается независимо от исхода предыдущего push

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Внутри `DataUpdateBloc._suncDevices()` (`lib/blocs/data_update/data_update_bloc.dart`)
`DeviceSettingsRepository.fetchDevicesFromApi()` (`GET
${Constants.farmServiceApi}/devices`) вызывается **до двух раз** за один
полный sync-проход: первый раз сразу после
[EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)
(`updateDevicesOnSHTP()`, безусловный push правок) — его результат решает,
нужен ли
[EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)
(`syncDevicesOnSHTP()`, условный первичный push создания); второй раз сразу
после него, если он выполнялся. Этот use-case — happy-path обеих
вариаций: HTTP-вызов завершается без исключения и возвращает непустой
список устройств (на любом из двух вызовов), после чего
`clearAndInsertAll(remoteDevices)` **заменяет всю локальную таблицу
`Devices` целиком** — единственный момент во всём модуле, когда `remoteId`
реально попадает в локальные строки (см. «Инварианты» в
[ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)). Сразу вслед за заменой
`ensureDeviceInDatabase()` вызывается повторно, чтобы досеять любые
дефолтные типы каталога, отсутствующие в конкретном серверном ответе.

Помимо самого факта успешного чтения, документ фиксирует два конкретных,
подтверждённых чтением кода следствия этой замены, не очевидных из одного
только факта «pull прошёл успешно»: (1) `DeviceDtoMapper.toCompanion()`
безусловно проставляет `isNeedUpdate: const Value(false)` каждой
заменяемой строке — независимо от того, был ли предшествующий
[EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)
push этой же строки реально принят сервером (его `bool`-результат никем
не проверяется, см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)); и
(2) если серверный список непуст, но не покрывает все 13/14 типов каталога
(частичный, а не полный список), `ensureDeviceInDatabase()`, вызванный
сразу после замены, пересоздаёт недостающие типы generic-дефолтами
(`remoteId: null`, `isNeedUpdate: true`), теряя без предупреждения любые
значения, которые были настроены для этих конкретных типов до этого
прохода.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
чтения нет — проход был запущен ранее одним из известных источников
`DataUpdateStartAll`: кнопка обновления навбара (`main_page.dart`),
`profile_settings_view.dart`, `in_work_page.dart`, `data_update_page.dart`,
либо автоматически — `BlocListener<AuthBloc, AuthState>` в
`main_page.dart` при переходе `AuthToMain` (успешное восстановление
сессии/вход). Дальше проход идёт автоматически, без участия пользователя
на уровне отдельного сетевого вызова.

**Важное отличие от справочников/списка ферм: этот шаг не выполняется для
гостя.** `_suncDevices()` вызывается изнутри `_syncAuthData()`, а
`on<DataUpdateStartAll>` вызывает `_syncAuthData()` только при
`_authRepository.isAuthorized() == true`
(`lib/blocs/data_update/data_update_bloc.dart`). Если проход инициировал
гость (или пользователь стал неавторизован к моменту, когда до этой ветки
дошло выполнение), весь этот сценарий — включая
[EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)/[EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)/[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) —
не выполняется вовсе, локальная таблица `Devices` остаётся как есть.

Строки, которые эта замена может молча перезаписать/потерять (см.
«Назначение»), могли быть отредактированы ранее тем же или другим
физическим устройством через [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)
на `ScannerSettingsPage`
([UC-178](UC-178-ACTOR-5-EVT-89-ENT-22-UPDATE_OK-IN-PROFILE.md)) — ACTOR-5
не участвует в самом sync-шаге, только в исходном создании локальных
значений, которые этот шаг может как подтвердить, так и (в двух описанных
здесь под-случаях) стереть.

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети, `await loadDirectories(event, emit)` и `await
   _loadBoardDirectories(...)`, — `if (_authRepository.isAuthorized())
   await _syncAuthData(event, emit);` — в этом сценарии условие истинно.
2. `_syncAuthData()` (`lib/blocs/data_update/data_update_bloc.dart`)
   выполняет несколько независимых от этого сценария шагов
   (`_deletePlacesFromRDS`, `_syncFarms`, `_syncPlaces`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP`,
   `updateAndSyncRegagro`, `updateAndSyncSHTP`), затем
   `_emitProgress(dataKey: DataKey.syncDevices)` и, последним шагом,
   `await _suncDevices()`.
3. `_suncDevices()`: `await
   _deviceSettingsRepository.ensureDeviceInDatabase()` — идемпотентный
   реseed каталога (удаляет строки устаревших легаси-типов
   `_obsoleteDeviceTypes`, гарантирует ровно одну строку на каждый из 13/14
   `defaultDevices` с фиксированным `id` из `ScannerDeviceLocalIds`) — до
   какого-либо сетевого вызова этого шага.
4. `await _deviceSettingsRepository.updateDevicesOnSHTP()` —
   [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md),
   `PUT ${Constants.farmServiceApi}/devices/update` для строк
   `isNeedUpdate == true && remoteId != null`, безусловно. Метод
   перехватывает своё собственное исключение и возвращает непроверяемый
   `bool` — не предмет этого сценария, но его (не проверяемый) исход
   определяет, что именно вернёт сервер на следующем шаге.
5. `var remoteDevices = await
   _deviceSettingsRepository.fetchDevicesFromApi();` — первый в этом
   проходе вызов [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md).
   Внутри: `ApiMessage(link: '${Constants.farmServiceApi}/devices', method:
   ApiMethod.get)`, `rpcClient.call(message)` через `ApiClient` с
   `instanceName: 'farm_rpc'`. В этом сценарии вызов завершается без
   исключения.
6. `final data = response['data']['devices'] as List;` — непустой список.
   Каждый элемент: `DeviceDto.fromJson(json)` (парсит `id`, `type`,
   `created_at`/`updated_at` как `DateTime.parse(...)`, и
   `device_credentials` — **JSON-строку**, требующую отдельного
   `DeviceCredentialsDto.fromString` → `jsonDecode` внутри самого
   `DeviceCredentialsDto.fromJson`, а не вложенный объект напрямую).
7. `.where((device) => ScannerDeviceTypes.defaults.contains(device.type))`
   — молча отбрасывает из ответа сервера любую строку, чей `type` не
   входит в текущие 13/14 значений каталога (легаси-типы вроде
   `'TCD'`/`'RFID'`/`'terminal'`/`'uhf_scanner_keyboard'`, либо любой ещё
   не известный клиенту тип) — такие строки не попадают в
   `remoteDevices` и, следовательно, никогда не появятся в локальной
   таблице через этот путь.
8. `.map((device) => device.toCompanion())` —
   `DeviceDtoMapper.toCompanion()`
   (`packages/sheep_farm_database/lib/entities/devices/devices.dart`):
   `id: Value(ScannerDeviceLocalIds.byType(type))` — не `null` и не
   `Value.absent()` ни для одного элемента, прошедшего фильтр шага 7 (обе
   таблицы — `ScannerDeviceTypes.defaults` и `ScannerDeviceLocalIds.byType`
   switch — перечисляют один и тот же набор типов), т.е. каждая строка
   получает фиксированный, детерминированный локальный `id`, никогда не
   новый автоинкрементный; `remoteId: Value(id)` — серверное числовое
   `id` из ответа, здесь физически попадает в локальную строку впервые;
   `isNeedUpdate: const Value(false)` — жёстко, не производное ни от чего
   в ответе сервера и не от предыдущего локального значения строки.
9. **Развилка, зависящая от результата шага 5 — обе ветки заканчиваются
   этим же use-case, вариант (б) через один дополнительный цикл
   push/pull.**
   - **Вариант (а) — сервер уже имел записи устройств для этого
     пользователя/установки.** `remoteDevices` (с шага 5) уже непуст —
     `if (remoteDevices.isEmpty)` (условие для
     [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md))
     ложно, второй вызов `fetchDevicesFromApi()` в этом проходе не
     происходит вовсе.
   - **Вариант (б) — первый вызов пуст (типично: у сервера ещё нет ни
     одной записи устройств для этого пользователя/установки).**
     `await _deviceSettingsRepository.syncDevicesOnSHTP()` —
     [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md),
     `POST .../devices/store` со всеми синкуемыми устройствами разом;
     результат (`bool`) не проверяется. Затем `remoteDevices = await
     _deviceSettingsRepository.fetchDevicesFromApi();` — **второй** вызов
     [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)
     в этом же проходе. В этом сценарии он тоже возвращает непустой
     список (например, только что созданные сервером строки — но код
     этого не проверяет и не требует: непустой ответ на этом шаге
     достаточен для продолжения независимо от его происхождения).
10. `if (remoteDevices.isNotEmpty) await
    _deviceSettingsRepository.clearAndInsertAll(remoteDevices);` — в этом
    сценарии условие истинно (из варианта (а) или (б)).
    `BaseRepository.clearAndInsertAll` → `DevicesDao.clearAndInsertAll`
    (`packages/sheep_farm_database/lib/entities/base_dao.dart`):
    внутри одной транзакции — `clear()` (`delete(Devices).go()`, без
    `WHERE`, вся таблица целиком) затем `insAll(remoteDevices)`
    (`batch.insertAll(..., mode: InsertMode.insertOrReplace)`). Итог:
    таблица `Devices` теперь содержит ровно те строки, что вернул сервер
    (после фильтра шага 7) — с их `remoteId`, актуальными значениями
    полей и `isNeedUpdate == false` — и **не** содержит ни одной строки,
    которая была в локальной таблице до этого шага, но отсутствует в
    ответе сервера.
11. `await _deviceSettingsRepository.ensureDeviceInDatabase();` —
    повторный вызов сразу после замены. Для каждого из 13/14
    `defaultDevices`: если тип уже присутствует среди только что
    вставленных строк (обычный случай при полном ответе сервера) —
    `_ensureDefaultSettings` только дозаполняет **null**-поля
    (`ip`/`mac`/`antennas`/`availableOperations`), не трогая `remoteId`
    или уже заполненные значения; если тип **отсутствует** среди строк с
    шага 10 (сервер вернул неполный список — не покрывающий все 13/14
    типов) — `_ensureDefaultDevice` не находит существующей строки этого
    типа и вставляет generic-дефолт (`DefaultScannerDevice.toCompanion`):
    фиксированный `id`, `remoteId: const Value(null)`, `isNeedUpdate:
    const Value(true)`, значения по умолчанию (`power: 33, maxPower: 33,
    minPower: 1, region: 4`, без антенн/адреса) — независимо от того,
    какие значения были у строки этого типа до шага 10.
12. `await getIt<ScannerService>().applySavedTerminalSettings();` —
    перечитывает строку `tcd` (уже после шагов 10-11) через
    `getScannerDeviceByType(ScannerDeviceTypes.tcd)` и, только на Android
    (`Platform.isAndroid`), best-effort применяет мощность/регион/действия
    кнопок к реальному терминалу — не меняет БД, побочный эффект на
    оборудование.
13. `_suncDevices()` завершается без исключения; `_syncAuthData()`,
    `on<DataUpdateStartAll>` продолжают — при отсутствии независимых
    отказов на других шагах весь проход завершается
    `DataUpdateSuccess`. Ни один UI-элемент этого прохода не показывает
    что-либо специфичное для факта «таблица устройств была заменена» —
    единственный наблюдаемый пользователем эффект (если он вообще
    заметен) — измененные значения на `DevicesSettingsPage`/
    `ScannerSettingsPage` при следующем их открытии.

### Альтернативные потоки

- **Оба вызова `fetchDevicesFromApi()` в проходе возвращают пусто —
  `READ_OK` не наступает.** Если и первый, и второй (после
  [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md))
  вызов возвращают `[]`, `if (remoteDevices.isNotEmpty)` (шаг 10) ложно —
  `clearAndInsertAll` не вызывается вовсе, локальная таблица `Devices`
  остаётся полностью нетронутой этим проходом (только реseed каталога на
  шагах 3 и 11, оба — no-op над уже полной таблицей). Это не отдельный
  `RESULT` (список пуст — не исключение, метод не завершается ошибкой),
  но наблюдаемо иначе, чем этот сценарий: ни один `remoteId` не
  обновляется, ни один `isNeedUpdate` не сбрасывается.
- **Исключение внутри `fetchDevicesFromApi()` (сеть недоступна, не-2xx
  ответ, либо `response['data']['devices']` бросает из-за неожиданной
  формы ответа) — тоже не этот сценарий.** Метод перехватывает **любое**
  исключение (`catch (e, stackTrace) { getIt<Talker>().handle(e,
  stackTrace); return []; }`) и возвращает пустой список — неотличимо на
  уровне вызывающего кода (`_suncDevices()`) от «сервер действительно не
  вернул ни одной записи» (предыдущий пункт). И логический (пустой
  ответ), и технический (исключение) случай наблюдаются вызывающим кодом
  одинаково — как `READ_ERROR`/пустой список, не разбирается дальше в
  этом файле (`READ_OK`).
- **Частичный (не полный) непустой ответ сервера — тот же `READ_OK`
  структурно, но с потерей данных для отсутствующих типов.** Описано как
  шаг 11 основного потока — здесь отмечено отдельно, потому что это
  единственная найденная в этом сценарии ветка, где формально успешное
  чтение (`READ_OK`, непустой список, `clearAndInsertAll` выполнен без
  ошибки) приводит к молчаливой потере ранее настроенных локальных
  значений для типов, которых не было в конкретном ответе — без разницы
  в наблюдаемом коде между «сервер никогда не создавал этот тип» и
  «сервер имел эти данные, но не вернул их в этом конкретном ответе».
- **Дублирующиеся `type` в ответе сервера — не воспроизведено, но
  структурно возможно.** `insAll` внутри `clearAndInsertAll` вставляет
  батчем с `InsertMode.insertOrReplace`; поскольку `id` каждой строки
  выводится детерминированно из `type` (шаг 8), две строки ответа с
  одинаковым `type` получили бы один и тот же `id` — при таком (не
  наблюдавшемся в этом чтении кода как реально присылаемое сервером)
  ответе вторая молча заменила бы первую в батче, без ошибки.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) —
  единственная сущность, чьё физическое хранилище меняется этим
  сценарием: `clearAndInsertAll` заменяет таблицу `Devices` целиком
  (шаг 10), `ensureDeviceInDatabase()` затем реseed'ит недостающие
  дефолты (шаг 11). Единственный сценарий во всём модуле `PROFILE`, где
  `remoteId` физически присваивается локальным строкам.
- Ни [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (уведомления), ни [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)
  (`Kind.visible`), ни [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User)
  не читаются и не пишутся этим сценарием — устройства синхронизируются
  независимым, не связанным с ними кодом (см.
  [MOD-6](../modules/MOD-6-PROFILE.md), «Граница»).
- Реальное физическое устройство (терминал TCD) — не сущность БД, но
  затрагивается сценарием косвенно на шаге 12
  (`ScannerService.applySavedTerminalSettings()`), только на Android,
  best-effort, без изменения БД.

### Бизнес-правила

- **`remoteId` попадает в локальные строки только через этот сценарий.**
  Ни [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md),
  ни [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)
  не проставляют `remoteId` и не сбрасывают `isNeedUpdate` сами — это
  происходит исключительно как побочный эффект `clearAndInsertAll` на
  шаге 10 этого сценария.
- **`isNeedUpdate` сбрасывается в `false` безусловно, не как подтверждение
  конкретного push.** `DeviceDtoMapper.toCompanion()` жёстко ставит
  `isNeedUpdate: const Value(false)` для каждой заменяемой строки —
  независимо от того, был ли предшествующий
  [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)
  для этой же строки реально принят сервером (его `bool`-результат
  отброшен вызывающим кодом, см.
  [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)). Если push молча
  отказал (сетевая ошибка внутри `updateDevicesOnSHTP`, перехваченная
  собственным `try/catch`), а сервер по-прежнему отдаёт старые
  (домодификационные) значения — этот пул перезапишет локальную строку
  этими старыми значениями и одновременно погасит `isNeedUpdate`,
  заставив систему считать локальное изменение синхронизированным, хотя
  оно фактически не дошло до сервера и теперь потеряно локально.
- **Порядок шагов внутри `_suncDevices()` фиксирован и не настраивается:**
  реseed → безусловный push правок → pull №1 → (если пуст) push создания
  → pull №2 → (если непуст любой из двух pull) замена таблицы → реseed →
  применение к оборудованию. Ни один из шагов не откатывает предыдущий
  при отказе последующего.
- **Фильтр по `ScannerDeviceTypes.defaults` — единственная защита от
  «мусорных» типов в ответе сервера**, применяется только на этапе
  `fetchDevicesFromApi()` (шаг 7); ничего не защищает от дублирующегося
  `type` внутри уже отфильтрованного списка (см. «Альтернативные
  потоки»).
- **Неполный ответ сервера не отличим в коде от «этого типа никогда не
  существовало на сервере».** `ensureDeviceInDatabase()` реагирует на оба
  случая одинаково — вставляет generic-дефолт с `remoteId: null`,
  `isNeedUpdate: true` — независимо от того, что причина отсутствия могла
  быть временной (сервер вернул неполный набор именно в этом ответе, а
  не вообще никогда не создавал тип).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — основной поток (обе вариации вызова
[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)
в рамках одного прохода, `clearAndInsertAll`, повторный
`ensureDeviceInDatabase()`) полностью прослеживается статическим чтением
`DataUpdateBloc._suncDevices()` →
`DeviceSettingsRepository.fetchDevicesFromApi`/`clearAndInsertAll`/
`ensureDeviceInDatabase` → `DeviceDtoMapper.toCompanion`. Найденные
следствия (безусловный сброс `isNeedUpdate`, потеря настроек типов,
отсутствующих в частичном ответе) также прослежены статически, но не
подтверждены ни одним тестом (см. «Связанные тесты») и не проверены
эмпирически против реального бэкенда — не выполняется исправление в
рамках этого документирующего прохода.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | вызывает `_syncAuthData()` только при `_authRepository.isAuthorized()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_suncDevices()` последним шагом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: reseed → push правок → pull №1 → (если пуст) push создания → pull №2 → (если непуст) замена таблицы → reseed → применение к оборудованию |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.fetchDevicesFromApi` | CURRENT | `GET .../devices`, фильтр по `ScannerDeviceTypes.defaults`, перехватывает любое исключение и возвращает `[]` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateDevicesOnSHTP`, `.syncDevicesOnSHTP` | CURRENT | предшествующие push-шаги этого же прохода — их непроверяемый исход определяет, что вернёт следующий pull |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `._ensureDefaultDevice`, `._ensureDefaultSettings` | CURRENT | реseed каталога до и после замены; вставляет generic-дефолт (`remoteId: null`, `isNeedUpdate: true`) для типов, отсутствующих в ответе сервера |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `DeviceDto.fromJson`, `DeviceDtoMapper.toCompanion`, `DeviceCredentialsDto.fromString`/`.fromJson` | CURRENT | парсинг ответа сервера; `toCompanion()` — источник `remoteId`, детерминированного `id` через `ScannerDeviceLocalIds.byType`, и жёсткого `isNeedUpdate: false` |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.defaults`, `ScannerDeviceLocalIds.byType` | CURRENT | фильтр допустимых типов и детерминированное сопоставление типа с фиксированным локальным `id` |
| `lib/repositories/devices_settings/scanner_device.dart` | `DefaultScannerDevice.toCompanion` | CURRENT | generic-дефолты, вставляемые при реseed'е отсутствующего в ответе сервера типа |
| `lib/repositories/base_repository.dart` | `BaseRepository.clearAndInsertAll` | CURRENT | делегирует в DAO |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `.insAll`, `.clearAndInsertAll` | CURRENT | транзакция: `delete(table).go()` без `WHERE`, затем `batch.insertAll(..., mode: InsertMode.insertOrReplace)` |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao.updateDeviceById` | CURRENT | не вызывается этим сценарием напрямую, но определяет, почему `isNeedUpdate` вообще было `true` до этого прохода (см. [UC-178](UC-178-ACTOR-5-EVT-89-ENT-22-UPDATE_OK-IN-PROFILE.md)) |
| `lib/services/scanner_service.dart` | `ScannerService.applySavedTerminalSettings`, `.applySettings` | CURRENT | best-effort применение к реальному TCD-терминалу после замены таблицы, только Android |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` (`instanceName: 'farm_rpc'`) | CURRENT | транспорт запроса `GET .../devices` |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый путь эндпоинта устройств |

## Критерии приёмки

- Если `fetchDevicesFromApi()` (первый или, при пустом первом ответе,
  второй вызов в рамках одного прохода `_suncDevices()`) завершается без
  исключения и возвращает непустой список, `clearAndInsertAll` заменяет
  таблицу `Devices` целиком: каждая оставшаяся строка имеет `remoteId`,
  равный серверному `id`, и `isNeedUpdate == false`, независимо от
  значения `isNeedUpdate` этой строки до замены.
- Ни одна строка ответа сервера с `type`, не входящим в
  `ScannerDeviceTypes.defaults`, не попадает в локальную таблицу через
  этот пул.
- После замены `ensureDeviceInDatabase()` гарантирует, что все 13/14 типов
  каталога присутствуют в таблице: типы из ответа сервера сохраняют
  полученные значения (кроме `null`-полей, дозаполняемых дефолтом), типы,
  отсутствовавшие в ответе, получают строку с `remoteId == null`,
  `isNeedUpdate == true` и generic-значениями `DefaultScannerDevice`.
- Весь sync-проход (`on<DataUpdateStartAll>`), в рамках которого
  произошёл этот сценарий, не переходит в `DataUpdateFailure` из-за него
  — при отсутствии независимых отказов на других шагах проход завершается
  `DataUpdateSuccess`.
- `_suncDevices()` не выполняется вовсе (ни один из шагов 3-13), если на
  момент `_syncAuthData()` `_authRepository.isAuthorized()` ложно.

## Связанные тесты

**TBD — теста нет.** `test/blocs/data_update_bloc_test.dart` регистрирует
`MockDeviceSettingsRepository` только как обязательную DI-зависимость,
необходимую для конструирования `DataUpdateBloc()` (см. явный комментарий
в файле: «`DataUpdateStartAll` (~900 из 1013 строк файла — основной sync
pipeline) НЕ покрыт юнит-тестом»); ни один `when(...)`-стаб не задан ни
для одного метода `DeviceSettingsRepository`, и единственные два реальных
теста файла (`'DataUpdateBloc конструируется с полным набором
зависимостей из getIt'` и блок-тест `DataUpdateClear`) не диспатчат
`DataUpdateStartAll` вообще — `_suncDevices()`/`fetchDevicesFromApi()`
не вызываются ни в одном прогоне. `grep -rn
"fetchDevicesFromApi\|_suncDevices\|clearAndInsertAll" test/` находит
только сам мок-класс в `data_update_bloc_test.dart`/`scanning_bloc_test.dart`
(интерфейсная реализация, не тест поведения) и не связанный с этим
сценарием тест `BaseRepository.clearAndInsertAll` в
`test/repositories/base_repository_test.dart` (проверяет общий механизм
`clearAndInsertAll` на абстрактном тестовом репозитории, не на
`DeviceSettingsRepository`/таблице `Devices`). Отдельного файла
`test/repositories/devices_settings_repository_test.dart` не существует.

## Открытые вопросы и ограничения

- **Безусловный сброс `isNeedUpdate` в `false` этим пулом — единственный
  способ, которым локальное «нужно отправить» вообще когда-либо
  гасится**, поскольку ни `updateDevicesOnSHTP()`, ни `syncDevicesOnSHTP()`
  не делают этого сами (см.
  [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)). Это значит, что при
  силентном отказе push (сетевая ошибка, перехваченная и проглоченная
  внутри `updateDevicesOnSHTP`) последующий успешный pull того же прохода
  и есть момент, когда локальное изменение теряется и одновременно
  перестаёт считаться «ожидающим отправки» — то же по сути семейство
  риска, что уже задокументировано для
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) («Локальные
  правки могут быть молча перезаписаны сервером»), но здесь дополнительно
  гасится и сам флаг «нужно синхронизировать», а не только значение поля.
- **Частичный ответ сервера неотличим от «тип никогда не создавался».**
  Ничего в `ensureDeviceInDatabase()`/`_ensureDefaultDevice` не различает
  «сервер прислал неполный список в этом конкретном ответе» и «сервер
  никогда не имел записи этого типа» — оба приводят к одинаковому
  generic-реseed'у с `remoteId: null`. Не проверено, действительно ли
  сервер `${Constants.farmServiceApi}/devices` когда-либо возвращает
  частичный (не пустой, но не полный) список на практике — вывод сделан
  статическим чтением кода, не эмпирическим наблюдением реального ответа
  бэкенда.
- **`DeviceCredentialsDto.fromString` предполагает, что `device_credentials`
  в ответе сервера — JSON-**строка**, а не вложенный JSON-объект** —
  если контракт сервера когда-либо изменится на вложенный объект без
  двойного кодирования, `jsonDecode` внутри `fromString` бросит
  исключение, которое перехватывается тем же `catch` в
  `fetchDevicesFromApi()` — неотличимо от сетевого сбоя (см.
  «Альтернативные потоки»), не проверено против реального контракта
  сервера этим документом.
- Дублирующийся `type` в ответе сервера (см. «Альтернативные потоки») —
  структурно возможное, но не воспроизведённое ни тестом, ни
  наблюдавшимся реальным ответом сервера, следствие детерминированного
  сопоставления `type → id` в сочетании с `InsertMode.insertOrReplace`.
- Не проверено эмпирически на реальном запуске против настоящего
  бэкенда — вывод сделан статическим чтением кода
  (`DeviceSettingsRepository.fetchDevicesFromApi` →
  `DeviceDtoMapper.toCompanion` → `BaseDao.clearAndInsertAll` →
  `DeviceSettingsRepository.ensureDeviceInDatabase`), без единого
  запущенного теста, подтверждающего любую из двух вариаций (а)/(б)
  основного потока или любое из описанных в «Открытые вопросы»
  следствий.
