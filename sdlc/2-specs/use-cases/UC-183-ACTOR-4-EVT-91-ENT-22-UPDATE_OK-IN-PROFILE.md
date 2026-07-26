# UC-183 — Push правок настроек устройства уходит на сервер безусловно на каждом sync-проходе, но локально ничего не подтверждает

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же шаг, что описан в [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) —
внутри `DataUpdateBloc._suncDevices()`, **безусловно**, на каждом полном
sync-проходе, до pull: `DeviceSettingsRepository.updateDevicesOnSHTP()` шлёт
`PUT /devices/update` одним batch-запросом для строк `Devices`, у которых
одновременно `isNeedUpdate == true` и `remoteId != null`. Здесь описан путь,
где этот сетевой вызов завершается без исключения — `UPDATE_OK` в терминах
этого корпуса, — и прослежено до конца, что именно это «ОК» означает на
практике: метод даже не читает тело ответа сервера, возвращает `true`,
вызывающий код (`_suncDevices()`) этот `bool` полностью игнорирует, а сама
строка `Devices` не получает никакого локального подтверждения (`isNeedUpdate`
не сбрасывается, `remoteId` не трогается) — единственный способ, которым
локальное состояние когда-либо становится «чистым», это последующий,
самостоятельный [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)
(`fetchDevicesFromApi()` + `clearAndInsertAll`), не сам этот push.

Сравнение с соседним push этой же сущности —
[EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)
(`syncDevicesOnSHTP()`) — та же структура метода (собственный `try/catch`,
возвращаемый, но не проверяемый `bool`, никакого сброса `isNeedUpdate`
после успеха), но принципиально другое условие запуска: `syncDevicesOnSHTP()`
выполняется **условно**, только если предшествующий pull в этом же проходе
вернул пустой список, и шлёт **все** «синкуемые» устройства разом с `id: 0`;
`updateDevicesOnSHTP()` (этот файл) выполняется **безусловно**, на каждом
проходе, и шлёт только отфильтрованное подмножество с `id: d.remoteId!`.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
push нет. Проход запускается одним из известных источников
`DataUpdateStartAll` (кнопка обновления `main_page.dart`/`profile_settings_view.dart`/`in_work_page.dart`/`data_update_page.dart`,
либо автоматически после восстановления сессии), но `_suncDevices()`
достигается только если `_authRepository.isAuthorized()` истинно на момент
`on<DataUpdateStartAll>` (`if (_authRepository.isAuthorized()) await
_syncAuthData(event, emit);`) — гость, инициировавший тот же
`DataUpdateStartAll`, до `_syncAuthData`, а значит и до `_suncDevices()`, не
доходит вовсе; этот сценарий возможен только для авторизованного
пользователя.

Строки, которые здесь пытаются отправить, были отредактированы раньше и
локально [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) на экране
`ScannerSettingsPage` ([EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)) —
но не любое редактирование этого экрана обязательно устанавливает
`isNeedUpdate: true` (см. «Открытые вопросы»). ACTOR-5 не участвует в самом
sync-шаге, только в исходном создании отправляемых данных.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети,
   `loadDirectories`/`_loadBoardDirectories` (независимо от этого сценария),
   `_authRepository.isAuthorized()` истинно → `await _syncAuthData(event,
   emit)`.
2. `_syncAuthData` последовательно вызывает `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro(event, emit)` (внутри которого условно, в
   зависимости от `event.isUpdateData`/наличия предыдущих ошибок/`event.again`/`event.fullUpdate`,
   может выполниться и push настроек уведомлений — [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md),
   отдельный, более узко гейтированный путь, не влияющий на этот сценарий),
   `updateAndSyncSHTP(event, emit)` — всё это независимо от этого сценария —
   затем, **безусловно**, без какой-либо проверки `event.isUpdateData`/`event.again`/`event.fullUpdate`:
   `_emitProgress(emit: emit, dataKey: DataKey.syncDevices)` (без `dataCategory`
   — `_currentDataCategory` остаётся тем, что было выставлено предыдущим
   шагом) и `await _suncDevices()`.
3. Внутри `_suncDevices()`: первым действием — `await
   _deviceSettingsRepository.ensureDeviceInDatabase()` — идемпотентный upsert
   каталога (удаляет устаревшие типы, досеивает недостающие из 13 дефолтных —
   см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты»).
   К моменту следующего шага каждая строка таблицы `Devices` гарантированно
   имеет `type`, входящий в `ScannerDeviceTypes.defaults`.
4. Вторым действием, **до** какого-либо pull в этом же проходе: `await
   _deviceSettingsRepository.updateDevicesOnSHTP();` — вызов, которому
   посвящён этот файл. Возвращаемое значение не присваивается ни одной
   переменной — результат отбрасывается синтаксически, не только логически.
5. Внутри `updateDevicesOnSHTP()`: `final localDevices = await dao.getAll();` —
   `BaseDao.getAll()` (`selectCurrent().get()`), вся таблица `Devices` без
   фильтра.
6. `final devicesToStore = localDevices.where((e) => _isSyncableDevice(e) &&
   e.isNeedUpdate == true && e.remoteId != null);` — три условия одновременно:
   тип входит в `ScannerDeviceTypes.defaults` (после шага 3 верно для каждой
   строки таблицы, фильтр фактически не отсеивает ничего дополнительно);
   `isNeedUpdate == true` — строка несёт локальную правку, ещё не
   подтверждённую сервером; `remoteId != null` — строка уже когда-то была
   получена от сервера предыдущим успешным pull'ом
   ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)).
   В этом сценарии есть хотя бы одна строка, удовлетворяющая всем трём.
7. Для каждой такой строки строится `DeviceDto(deviceCredentials:
   DeviceCredentialsDto(name:, region:, power:, maxPower:, minPower:, ip:,
   mac:, antennas:, availableOperations:, isUseCameraForQr:,
   leftButtonAction:, middleButtonAction:, rightButtonAction:), type: d.type,
   id: d.remoteId!, createdAt: d.createdAt, updatedAt: d.updatedAt ??
   d.createdAt)` — весь текущий набор колонок строки, не только то поле,
   правка которого выставила `isNeedUpdate`; `id` — уже известный серверный
   id (в отличие от `syncDevicesOnSHTP()`, где для этого же поля жёстко
   передаётся `0`).
8. `toSend` в этом сценарии непуст: `final body = {'devices':
   toSend.map((e) => e.toJson()).toList()};` — `DeviceDto.toJson()` кладёт в
   тело только `{'id', 'device_credentials', 'type'}` (не `createdAt`/`updatedAt`,
   несмотря на то что оба поля были явно переданы конструктору); `message =
   ApiMessage(link: '${Constants.farmServiceApi}/devices/update', method:
   ApiMethod.put, data: body)`.
9. `try { final rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc');
   await rpcClient.call(message); return true; }` — `rpcClient` здесь всегда
   `CustomDioClient` (`lib/network/api_client/custom_dio_client.dart`).
   `dio.request(...)` завершается 2xx-ответом; `CustomDioClient.call`
   возвращает его — либо с принудительным `status: "1"` (тело содержит
   `data`/`animal_exits`), либо, для любой другой формы тела, не помеченной
   явным `status: 'error'`, оборачивает в `{"data": response.data, "status":
   "1"}` — в любом случае без исключения. Именно это и есть `UPDATE_OK`,
   которому посвящён этот файл.
10. **Ключевой факт этого шага: `await rpcClient.call(message)` не
    присваивается ни одной переменной внутри `updateDevicesOnSHTP()` — метод
    физически не может прочитать содержимое ответа, даже если бы захотел.**
    `return true;` следует сразу за вызовом безусловно, независимо от того,
    что именно вернул сервер внутри тела 2xx-ответа (см. «Открытые
    вопросы» — тот же класс дефекта, что и в
    [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)/[UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md),
    только здесь этот пробел ещё глубже — там ответ хотя бы попадал в
    переменную и просто не проверялся, здесь его негде проверить в принципе).
11. `updateDevicesOnSHTP()` возвращает `true` вызывающей стороне —
    `_suncDevices()` (шаг 4). Значение отброшено (шаг 4), выполнение
    `_suncDevices()` продолжается без какой-либо реакции на исход этого шага.
12. **Ни `isNeedUpdate`, ни `remoteId` только что отправленных строк не
    меняются локально этим шагом.** В отправленном `DeviceDto` не было ни
    одной инструкции записи в локальную БД — `updateDevicesOnSHTP()` целиком
    состоит из чтения (`dao.getAll()`) и сетевого вызова, ни одного
    `dao.update*`/`dao.insert*`. Строки остаются `isNeedUpdate == true` в
    локальной таблице сразу после того, как сервер их только что принял.
13. `_suncDevices()` продолжает: `var remoteDevices = await
    _deviceSettingsRepository.fetchDevicesFromApi();` (pull №1,
    [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)).
    Если он возвращает непустой список (обычный случай, раз сервер уже что-то
    знает об этом пользователе/установке) — `if (remoteDevices.isNotEmpty)
    await _deviceSettingsRepository.clearAndInsertAll(remoteDevices);`
    заменяет **всю** таблицу `Devices` целиком строками, построенными
    `DeviceDto.toCompanion()` из ответа `GET /devices` — только на этом шаге
    только что отправленные строки реально получают `isNeedUpdate: const
    Value(false)` (жёстко зашито в `toCompanion()`, не зависит от того, что
    именно сервер сохранил) и `remoteId: Value(id)` (то же значение, что уже
    было). Если pull №1 пуст — выполняется условный `syncDevicesOnSHTP()`
    ([EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md))
    и повторный pull; тот же механизм замены таблицы применяется только если
    он в итоге вернул непустой список.
14. `await _deviceSettingsRepository.ensureDeviceInDatabase();` (повторно,
    досеять недостающие дефолтные типы после возможной замены таблицы), затем
    `await getIt<ScannerService>().applySavedTerminalSettings();` — применяет
    сохранённые настройки терминала (`tcd`) к реальному оборудованию, если
    таковое подключено; не влияет на `isNeedUpdate`/`remoteId`.
15. `_syncAuthData`, `on<DataUpdateStartAll>` продолжают без ошибки (при
    отсутствии независимых отказов на других шагах прохода) —
    `emit(DataUpdateSuccess(...))`. Ни один из шагов 4–12 не порождает ни
    единого видимого пользователю признака того, что именно произошло с
    push'ем: ни успех, ни (гипотетический) отказ этого конкретного шага не
    отражаются нигде в UI отдельно от общего результата всего прохода.

### Альтернативные потоки

- **Пустой batch — push вообще не выполняет сетевого вызова.** Если ни одна
  строка `Devices` не удовлетворяет всем трём условиям шага 6 одновременно
  (нет локальных правок, либо все правки уже относятся к строкам без
  `remoteId`), `toSend` пуст → `if (toSend.isEmpty) return true;` —
  `updateDevicesOnSHTP()` возвращает `true` немедленно, без единого сетевого
  запроса. Формально тот же `UPDATE_OK`, что и основной поток, но по
  фактическому отсутствию работы, а не по успеху реального запроса.
- **Строка с `isNeedUpdate == true`, но `remoteId == null`, исключена из
  этого push безусловно и бессрочно.** Если устройство отредактировано
  раньше, чем сервер когда-либо подтвердил для него `remoteId` (например,
  сразу после первой установки приложения, до первого успешного pull/create-цикла),
  условие `e.remoteId != null` на шаге 6 ложно — строка не попадает в
  `devicesToStore` ни на этом, ни на любом последующем проходе, пока
  `remoteId` не будет проставлен отдельно, через
  [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)
  (полная замена таблицы данными с сервера). До этого момента правка
  пользователя остаётся видна только локально и никогда не будет отправлена
  этим методом.
- **Если ни один pull в проходе не вернул непустой список (шаг 13),
  `isNeedUpdate` не сбрасывается вовсе за весь проход.** Строки, только что
  успешно принятые сервером на шаге 9, остаются `isNeedUpdate == true`
  локально до следующего полного sync-прохода — на котором
  `updateDevicesOnSHTP()` соберёт и отправит те же самые строки повторно,
  без какого-либо признака того, что они уже были приняты раньше.
- **Тот же класс метода, другое условие запуска.**
  `syncDevicesOnSHTP()` ([EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md))
  запускается только если предшествующий pull этого же прохода вернул пустой
  список — практически только «первичный» push для установки, у которой на
  сервере ещё вообще нет ни одной записи устройств. `updateDevicesOnSHTP()`
  (этот файл) не имеет такого гейта — выполняется на каждом проходе,
  независимо от того, что вернул или вернёт pull в этом же проходе.
- **Push настроек устройств не гейтирован так, как push настроек уведомлений
  той же группы экранов.** `SettingsRepository.setSettingToSHTP()`
  ([ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)) выполняется
  только внутри `_syncAllData`, которая сама достижима из
  `updateAndSyncRegagro` лишь при выполнении отдельных условий (`event.again`,
  число уже накопленных `DataUpdates`, наличие ошибок, либо
  `event.fullUpdate`), и даже тогда — только если `event.isUpdateData ==
  true`. `_suncDevices()` не имеет ни одного из этих условий — вызывается
  безусловно каждый раз, когда `_syncAuthData` вообще достигнута
  (т.е. пользователь авторизован).

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность, читаемая и потенциально изменяемая этим сценарием: читается
  целиком (`dao.getAll()`, шаг 5) для построения batch'а; сама
  `updateDevicesOnSHTP()` не пишет в неё ничего — `isNeedUpdate`/`remoteId`
  меняются только последующим, самостоятельным шагом того же
  `_suncDevices()` ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
  шаг 13), и только если этот шаг реально вернул непустой список.
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) (ProfileSettings) —
  не читается и не изменяется этим сценарием; упомянута только как контраст
  гейтирования (см. «Альтернативные потоки») — соседняя настройка того же
  модуля, синхронизируемая принципиально иначе гейтированным вызовом внутри
  того же полного прохода.

### Бизнес-правила

- Порядок операций внутри `_suncDevices()` фиксирован: `ensureDeviceInDatabase()`
  → `updateDevicesOnSHTP()` (этот файл, безусловно, до pull) → `fetchDevicesFromApi()`
  (pull №1) → условно `syncDevicesOnSHTP()` + pull №2 → условно
  `clearAndInsertAll` → `ensureDeviceInDatabase()` (повторно) →
  `ScannerService.applySavedTerminalSettings()`.
- Отбор строк для этого push — исключительно пара локальных флагов
  (`isNeedUpdate`, `remoteId`), без каких-либо временных меток/версий и без
  учёта того, было ли что-то отправлено на предыдущем проходе — единственный
  критерий «эта строка ещё не подтверждена» это `isNeedUpdate == true`, а
  единственный критерий «эту строку вообще можно адресовать по id» —
  `remoteId != null`.
- Успех или неуспех сетевого вызова этого шага не оказывает никакого
  влияния на дальнейшее выполнение `_suncDevices()` — следующие шаги (pull,
  условный create, повторная досевка каталога, применение настроек к
  терминалу) выполняются одинаково в обоих случаях.
- Единственный механизм, которым локальное состояние `Devices` когда-либо
  становится согласованным с сервером после push'а — не сам push, а
  последующий pull того же прохода, и то лишь при условии, что он вернул
  непустой список.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий полностью прослеживается
статическим чтением кода: `DataUpdateBloc._syncAuthData` →
`DataUpdateBloc._suncDevices` → `DeviceSettingsRepository.updateDevicesOnSHTP`
→ `CustomDioClient.call`. Исправление (например, чтение и проверка ответа
сервера перед `return true`, либо явный сброс `isNeedUpdate`/установка
`remoteId` сразу после подтверждённого успеха, не дожидаясь следующего
pull'а) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | вызывает `_syncAuthData` только если `_authRepository.isAuthorized()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_suncDevices()` безусловно, последним шагом, без проверки `event.isUpdateData`/`.again`/`.fullUpdate` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` (безусловно, до pull) → `fetchDevicesFromApi()` → условно `syncDevicesOnSHTP()` + pull → условно `clearAndInsertAll` → `ensureDeviceInDatabase()` → `ScannerService.applySavedTerminalSettings()`; возвращаемый `bool` `updateDevicesOnSHTP()` нигде не проверяется |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | вызывается с `dataKey: DataKey.syncDevices`, без `dataCategory` — `_currentDataCategory` наследуется от предыдущего шага прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro`, `._syncAllData` | CURRENT | контекст контраста — гейтирование push настроек уведомлений ([ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)), принципиально более узкое, чем у этого шага |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateDevicesOnSHTP` | CURRENT | предмет этого сценария: фильтр `_isSyncableDevice && isNeedUpdate == true && remoteId != null`, `PUT /devices/update`, `try/catch` возвращает непроверяемый `bool`; ответ сервера не читается ни в одной ветке |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `.fetchDevicesFromApi`, `.syncDevicesOnSHTP`, `._isSyncableDevice` | CURRENT | соседние шаги того же `_suncDevices()`; `fetchDevicesFromApi` — единственный путь, реально сбрасывающий `isNeedUpdate`/выставляющий `remoteId` |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.setSettingToSHTP` | CURRENT | контраст — соседний push той же группы экранов, гейтированный `event.isUpdateData == true` внутри более узко достижимой `_syncAllData` |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `Devices.isNeedUpdate`, `.remoteId`, `ScannerDeviceTypes.defaults`, `DeviceDto`, `DeviceCredentialsDto`, `DeviceDto.toJson`, `DeviceDtoMapper.toCompanion` | CURRENT | поля-предикаты отбора; `toJson()` не включает `createdAt`/`updatedAt` в тело; `toCompanion()` — единственное место, жёстко проставляющее `isNeedUpdate: false` при последующем pull |
| `packages/sheep_farm_database/lib/entities/devices/devices_dao.dart` | `DevicesDao` (наследует `BaseDao.getAll`) | CURRENT | физический источник `localDevices` — вся таблица, без фильтра на уровне SQL |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll`, `.clearAndInsertAll` | CURRENT | `getAll()` — используется этим шагом; `clearAndInsertAll` — используется соседним pull'ом (не этим шагом) |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | 2xx-ответ без `status: 'error'` возвращается без исключения — источник `UPDATE_OK`, документированного здесь |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — любой не-2xx дал бы исключение (не этот сценарий) |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый URL `PUT .../devices/update` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updatePowerInDatabase`, `.updateRegionInDatabase`, `.updateIsUseCameraForQrInDatabase`, `.updateDeviceButtonAction` | CURRENT | единственные четыре метода, реально выставляющие `isNeedUpdate: true` — источник строк, которые вообще способны попасть в этот push (см. «Открытые вопросы») |
| `lib/services/scanner_service.dart` | `ScannerService.applySavedTerminalSettings` | CURRENT | последний шаг `_suncDevices()`, не влияет на `isNeedUpdate`/`remoteId` |

## Критерии приёмки

- Если хотя бы одна строка `Devices` удовлетворяет `_isSyncableDevice(e) &&
  e.isNeedUpdate == true && e.remoteId != null`, `updateDevicesOnSHTP()`
  строит `PUT ${Constants.farmServiceApi}/devices/update` с телом
  `{'devices': [...]}`, где каждый элемент несёт `id`, равный текущему
  `remoteId` строки, и полный набор её текущих полей внутри
  `device_credentials`.
- Если `rpcClient.call(message)` завершается без исключения, метод
  возвращает `true`, не читая и не проверяя содержимое ответа ни в одной
  ветке.
- Вызывающий код (`DataUpdateBloc._suncDevices()`) не проверяет и не
  использует возвращённое значение никаким образом — исход этого шага не
  влияет на выполнение последующих шагов того же прохода.
- Ни `isNeedUpdate`, ни `remoteId` строк, участвовавших в этом push'е, не
  меняются самим `updateDevicesOnSHTP()` — единственный способ, которым они
  меняются в рамках того же прохода, это последующий `fetchDevicesFromApi()`
  с непустым ответом и `clearAndInsertAll`.
- Если ни одна строка не удовлетворяет фильтру, `updateDevicesOnSHTP()`
  возвращает `true` без единого сетевого вызова.

## Связанные тесты

`grep -rn "DeviceSettingsRepository\|devices_settings" test/` находит только
`test/blocs/data_update_bloc_test.dart` и `test/pages/scanning_bloc_test.dart` —
в обоих `DeviceSettingsRepository` зарегистрирован в `getIt` исключительно
как мок-зависимость, нужная для конструирования `DataUpdateBloc`/`ScanningBloc`
целиком (DI), без единого `when(...)`/`verify(...)` на `updateDevicesOnSHTP`,
`syncDevicesOnSHTP`, `fetchDevicesFromApi`, `ensureDeviceInDatabase` или
`_suncDevices`. Единственные два теста `data_update_bloc_test.dart` —
`'DataUpdateBloc конструируется с полным набором зависимостей из getIt'`
(конструктор) и `'DataUpdateClear очищает пользовательские данные БД'`
(`DataUpdateClear`, другое событие) — ни один не диспатчит
`DataUpdateStartAll` и, следовательно, не достигает `_suncDevices()` вовсе.
Отдельного файла `test/repositories/devices_settings_repository_test.dart`
не существует.

**TBD — теста нет.**

## Открытые вопросы и ограничения

- **Метод физически не может отличить `UPDATE_OK` от логического отказа
  сервера внутри 2xx-ответа — `await rpcClient.call(message)` не
  присваивается переменной вообще.** Строже, чем в
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) (где ответ
  хотя бы попадает в переменную и просто не проверяется условием) — здесь
  нет и самой переменной, которую можно было бы проверить. Является ли это
  осознанным решением (ожидание, что `PUT /devices/update` никогда не
  возвращает `status: 'error'` в 2xx-теле) или недосмотром — ничем в
  коде/комментариях не зафиксировано.
- **Успешный push не подтверждается локально ничем, кроме последующего
  успешного pull'а того же прохода.** Если этот же проход завершает
  `_suncDevices()` без хотя бы одного непустого `fetchDevicesFromApi()`
  (основной поток предполагает, что pull №1 вернул непустой список — но
  структурно возможен и обратный случай, если сервер между push'ем и pull'ом
  того же прохода ещё не успел отдать только что принятые данные, либо если
  оба pull'а этого прохода независимо отказали и вернули пустой список,
  проглотив исключение — см. [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)),
  `isNeedUpdate` этих строк остаётся `true` бессрочно, и они будут
  переотправлены на следующем проходе — без какого-либо признака (ни для
  пользователя, ни для разработчика через `Talker`/`DataUpdates`) того, что
  это повторная, а не первая попытка.
- **Не каждая правка формы `ScannerSettingsPage` вообще способна попасть в
  этот push.** Прочтением `DeviceSettingsRepository` подтверждено: только
  `updatePowerInDatabase`, `updateRegionInDatabase`,
  `updateIsUseCameraForQrInDatabase` и `updateDeviceButtonAction`
  устанавливают `isNeedUpdate: true`. `updateAntennasInStorage`,
  `updateAddressInStorage` и `updateDeviceOperationUsage` (используются
  `ScannerAntennasSettingsWidget`/`ScannerAddressSettingsWidget`/`ScannerOperationsSettingsWidget`
  — три из пяти виджетов формы, см.
  [UC-176](UC-176-ACTOR-5-EVT-88-ENT-22-READ_OK-IN-PROFILE.md)) пишут
  изменённое поле в `Devices`, **не** трогая `isNeedUpdate` вовсе. Итог:
  правка одних только антенн, адреса или включённых операций — без
  сопутствующей правки мощности/региона/камеры/кнопок TCD той же строки —
  никогда не выставит `isNeedUpdate: true`, а значит никогда не будет
  подобрана `updateDevicesOnSHTP()` на шаге 6 этого сценария и никогда не
  будет отправлена на сервер этим методом — при этом `DeviceCredentialsDto`,
  которое отправилось бы для этой строки при срабатывании push'а по другой
  причине, всё равно несло бы это изменённое значение поля (весь набор
  колонок сериализуется разом, шаг 7), маскируя факт, что само по себе оно
  push не вызывает. Не зафиксировано нигде в коде/комментариях, было ли это
  осознанным решением (эти поля синхронизируются как побочный эффект чужой
  правки) или недосмотром при добавлении `isNeedUpdate` к части методов, но
  не ко всем.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DeviceSettingsRepository.updateDevicesOnSHTP`
  → `CustomDioClient.call` → `DioClient`), без единого запущенного теста,
  подтверждающего эту ветку (см. «Связанные тесты» — TBD). В частности, не
  подтверждено, действительно ли `PUT ${Constants.farmServiceApi}/devices/update`
  на практике когда-либо отвечает телом без `data`/`animal_exits` и с явным
  `status: 'error'` в 2xx — форма, которая в этом методе прошла бы совершенно
  незамеченной.
