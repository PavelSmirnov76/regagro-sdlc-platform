# UC-184 — Push правок настроек сканера не может явно провалиться: исключение проглочено внутри репозитория, а `isNeedUpdate` не сбрасывается ни при отказе, ни при успехе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же безусловный push-шаг, что описан в
[EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) —
`DeviceSettingsRepository.updateDevicesOnSHTP()` (`PUT /devices/update`)
отправляет одним batch-запросом все строки `Devices` с `isNeedUpdate == true
&& remoteId != null`, вызывается безусловно на каждом полном sync-проходе
(`DataUpdateBloc._suncDevices()`), до pull. Здесь описан отказ самого
сетевого вызова внутри этого метода.

Структурно это тот же паттерн «проглоченного исключения», что и у парного
push-шага «создание» — [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)
(`syncDevicesOnSHTP()`): оба метода сами оборачивают сетевой вызов в
`try/catch`, сами логируют через `Talker.handle` и **сами** возвращают `bool`
— `true`/`false` — вызывающий код (`DataUpdateBloc._suncDevices()`, строка
`await _deviceSettingsRepository.updateDevicesOnSHTP();`) этот `bool` не
проверяет вообще: ни `if`, ни присваивание переменной. Ни одно исключение из
этого конкретного вызова никогда не долетает до внешнего `catch`
`on<DataUpdateStartAll>` — `UPDATE_ERROR` в смысле «пользователь увидел явный
`DataUpdateFailure` из-за этого шага» структурно недостижим, ровно как и
`CREATE_ERROR` для `EVT-90`.

Отличает этот сценарий от парного `EVT-90` более серьёзный и самостоятельный
практический эффект, специфичный именно для push «правки»: `updateDevicesOnSHTP()`
не сбрасывает `isNeedUpdate` (и не проставляет `remoteId`, хотя для этого
метода он и так уже не `null` — это предусловие выборки) **ни при отказе, ни
при успехе** — метод целиком, от начала до конца, не делает ни одной записи в
локальную таблицу `Devices`, только `dao.getAll()` на чтение. Единственный
код во всём приложении, который когда-либо сбрасывает `isNeedUpdate` для уже
существующей строки устройства, — `DeviceDtoMapper.toCompanion()`
(`packages/sheep_farm_database/lib/entities/devices/devices.dart`),
вызываемый исключительно из pull-ветки ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
и только когда `fetchDevicesFromApi()` вернул **непустой** список. Следствие:
любая строка, однажды помеченная `isNeedUpdate == true` (сохранена
пользователем через [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)),
будет заново отобрана и заново отправлена этим же push-запросом на **каждом**
последующем полном sync-проходе — независимо от того, был ли предыдущий push
технически неуспешным (сетевое исключение, этот сценарий), логически
отклонённым сервером без исключения, или на самом деле дошёл до сервера и был
там принят. Это самостоятельная находка, отдельная от того, что описано для
`EVT-90`/`syncDevicesOnSHTP()` (тот push вообще не привязан к конкретным
строкам условием `isNeedUpdate`, шлёт весь каталог целиком и только один раз
за проход, при первом пустом pull).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода. Прямого действия пользователя в момент самого отказа нет
— `_suncDevices()` вызывается из `_syncAuthData()`, которая, в свою очередь,
вызывается из `on<DataUpdateStartAll>` только если `_authRepository.isAuthorized()`
истинно на момент прохода (`if (_authRepository.isAuthorized()) await
_syncAuthData(event, emit);`) — гостевые сессии этот шаг не проходят вообще.
Проход мог быть запущен пользователем явно (кнопка обновления в
`main_page.dart`, `profile_settings_view.dart`, `in_work_page.dart`,
`data_update_page.dart`) или автоматически приложением (восстановление сессии
при холодном старте — `AuthToMain`). Строка(и) `Devices`, которые здесь не
удаётся (или удаётся, но без видимого следа) отправить, были записаны раньше
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователем,
редактирующим `ScannerSettingsPage`
([EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md),
[UC-178](UC-178-ACTOR-5-EVT-89-ENT-22-UPDATE_OK-IN-PROFILE.md) — happy path
этого сохранения). ACTOR-5 не участвует в самом sync-шаге, только в исходном
создании отправляемых данных, и не получает никакого сигнала о том, дошла ли
правка до сервера.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети (иначе —
   `DataUpdateFailure` сразу, до входа в `try`) и `loadDirectories`/`_loadBoardDirectories`,
   при `_authRepository.isAuthorized()` вызывается `await _syncAuthData(event,
   emit)` — внутри единственного внешнего `try` этого прохода.
2. `_syncAuthData` последовательно вызывает `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`, `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro(...)`, `updateAndSyncSHTP(...)` (в этом сценарии
   независимы от него), затем `_emitProgress(emit: emit, dataKey:
   DataKey.syncDevices)` — **без параметра `dataCategory`** (см. «Открытые
   вопросы») — и, наконец, `await _suncDevices();`.
3. `_suncDevices()`: первым шагом `await _deviceSettingsRepository.ensureDeviceInDatabase();`
   — досевает недостающие дефолтные устройства, не трогает `isNeedUpdate` уже
   существующих отредактированных строк.
4. Вторым шагом, **безусловно**: `await _deviceSettingsRepository.updateDevicesOnSHTP();`
   — вызов не обёрнут ни в `if`, ни в присваивание переменной; возвращаемое
   значение полностью отбрасывается.
5. Внутри `updateDevicesOnSHTP()`: `final localDevices = await dao.getAll();`
   — читает всю таблицу `Devices` (единственное обращение к БД во всём
   методе, на чтение); `devicesToStore = localDevices.where((e) =>
   _isSyncableDevice(e) && e.isNeedUpdate == true && e.remoteId != null)` —
   отбирает только «синкуемые» типы (`ScannerDeviceTypes.defaults`) с
   выставленным флагом правки и уже известным серверным id. В этом сценарии
   список непуст — хотя бы одна строка была недавно отредактирована через
   [EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) и уже имеет
   `remoteId` (получен более ранним успешным pull'ом).
6. `toSend` строится из `devicesToStore`, оборачивается в `{'devices':
   toSend.map((e) => e.toJson()).toList()}`, `ApiMessage(link:
   '${Constants.farmServiceApi}/devices/update', method: ApiMethod.put, data:
   body)`.
7. `try { final rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc');
   await rpcClient.call(message); return true; }` — здесь начинается отказ
   этого сценария: `rpcClient.call(message)` (`CustomDioClient.call`) бросает
   исключение — сеть недоступна, таймаут, либо любой не-2xx HTTP-ответ (Dio
   по умолчанию бросает `DioException` вне 200–299, `DioClient` не
   переопределяет `validateStatus`).
8. `catch (e, stackTrace) { getIt<Talker>().handle(e, stackTrace); return
   false; }` — исключение перехватывается **внутри самого метода**
   репозитория, логируется через `Talker` (виден в консоли/DevTools
   разработчика, не в UI пользователя) и метод завершается штатно, возвращая
   `false`. Исключение не перебрасывается (`rethrow` отсутствует) — оно не
   покидает `updateDevicesOnSHTP()`.
9. Возврат в `_suncDevices()` (шаг 4): `await
   _deviceSettingsRepository.updateDevicesOnSHTP();` — вызов просто
   завершается, возвращённое `false` никем не читается. Выполнение
   продолжается безусловно: `var remoteDevices = await
   _deviceSettingsRepository.fetchDevicesFromApi();` (pull №1), и далее по
   обычной логике `_suncDevices()` — если pull пуст, `syncDevicesOnSHTP()`
   (push «создание», [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)),
   повторный pull, если непуст — `clearAndInsertAll(remoteDevices)`,
   `ensureDeviceInDatabase()`, `ScannerService.applySavedTerminalSettings()`.
10. `_syncAuthData`/`on<DataUpdateStartAll>` не видят ничего необычного —
    если остальные независимые шаги прохода не отказали, `emit(
    DataUpdateSuccess(...))`. Пользователь видит **полностью успешное**
    завершение обновления данных, без какого-либо намёка на то, что
    конкретно правки настроек сканера не дошли до сервера.
11. **Итог, специфичный для push «правки» (в отличие от push «создание»,
    [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)):**
    строка(и), выбранные на шаге 5, остаются `isNeedUpdate == true` — ничто в
    методе `updateDevicesOnSHTP()`, ни в остальной части `_suncDevices()` для
    уже существующих строк с известным `remoteId`, их не сбрасывает. На
    **следующем** полном sync-проходе шаг 5 выполнится заново с тем же
    условием `isNeedUpdate == true && remoteId != null` — те же строки будут
    отобраны и отправлены повторно, снова без каких-либо гарантий, что этот
    повтор успешен, и снова без сброса флага при любом исходе. Единственный
    способ прервать эту цепочку — чтобы pull ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
    `fetchDevicesFromApi()`) на каком-то последующем проходе вернул непустой
    список: тогда `clearAndInsertAll(remoteDevices)` полностью заменяет
    таблицу строками, полученными через `DeviceDtoMapper.toCompanion()`, где
    `isNeedUpdate` явно проставлен `const Value(false)` — независимо от того,
    успел ли сервер реально применить ранее отправленную правку.

### Альтернативные потоки

- **Пустой батч — сценарий не наступает, но безусловность шага 4 сохраняется.**
  Если на момент вызова `dao.getAll()` нет ни одной строки, удовлетворяющей
  `isNeedUpdate == true && remoteId != null`, `toSend.isEmpty` истинно,
  `updateDevicesOnSHTP()` возвращает `true` **до** сетевого вызова (`if
  (toSend.isEmpty) return true;`) — не этот сценарий, отказа нет, потому что
  отправлять нечего.
- **Логический отказ сервера без исключения — тот же итог, что и сетевое
  исключение, только без даже строчки в `Talker`.** `CustomDioClient.call`
  возвращает как есть (без исключения) любой `Map<String, dynamic>`-ответ,
  не содержащий `data`/`animal_exits`, но с явным `response.data['status'] ==
  'error'`. `updateDevicesOnSHTP()` не проверяет `response`/результат
  `rpcClient.call` вообще ни одним условием — единственное, что делается с
  ответом, это неявное поглощение внутри `await rpcClient.call(message);
  return true;`. Значит логический отказ сервера (батч правок отклонён
  content-уровнем, без HTTP-исключения) приводит к тому же `return true`, что
  и настоящий успех, — метод не может отличить их между собой, и в этой
  ветке даже нет `Talker.handle`, поскольку `catch` вообще не срабатывает.
  Тот же класс дефекта, что уже задокументирован для инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  «б»), но здесь без разрушительных последствий той сцены (там `deleteAllReadyToSend()`
  безвозвратно стирает данные; здесь просто ничего не сбрасывается — строка
  остаётся `isNeedUpdate == true`, как и в ветке сетевого исключения).
- **Настоящий сетевой успех — тоже не сбрасывает `isNeedUpdate`.** Даже если
  `rpcClient.call(message)` реально доходит до сервера, тот реально применяет
  правку и отвечает 2xx без `status: 'error'`, `updateDevicesOnSHTP()`
  возвращает `true`, но **не пишет в БД ничего** — ни `isNeedUpdate: false`,
  ни `updatedAt`. Строка остаётся отмеченной «нужно обновить» до следующего
  успешного pull'а с непустым ответом. Формально это не `UPDATE_ERROR`, а
  единственная «настоящая» ветка успеха этого шага — упомянута здесь потому,
  что именно она делает эффект, описанный в «Назначение», универсальным: все
  три исхода (сетевое исключение, логический отказ, настоящий успех)
  наблюдаются пользователем совершенно одинаково — строка снова уйдёт на
  следующем проходе.
- **Если исключение возникло бы вне `updateDevicesOnSHTP()`, но всё ещё внутри
  `_suncDevices()`** (например, в `ensureDeviceInDatabase()` — реальные
  Drift-операции записи, не обёрнутые в `try/catch`, — или в
  `ScannerService.applySavedTerminalSettings()`), оно всплыло бы
  необработанным до внешнего `catch` `on<DataUpdateStartAll>` и **было бы**
  видно пользователю как `DataUpdateFailure` — но это не сценарий этого
  файла: `updateDevicesOnSHTP()` (шаг push «правки», [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md))
  специально устроен так, чтобы не пропускать исключение дальше себя.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — сущность,
  чьё физическое состояние остаётся неизменным этим сценарием во всех трёх
  исходах шага 7-8 (исключение/логический отказ/настоящий успех):
  `isNeedUpdate` и `remoteId` затронутых строк не пишутся этим методом ни в
  одной ветке; единственная запись, которая когда-либо их меняет для уже
  существующей строки, происходит позже, отдельным шагом
  ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)),
  и только если он вернул непустой список.
- `DataUpdates` (лог sync-прохода, специфицируется будущим модулем SYSTEM) —
  **не получает ни одной строки об этом отказе** ни в одной из веток: и
  сетевое исключение, и логический отказ сервера перехватываются/поглощаются
  строго внутри `DeviceSettingsRepository`, ни разу не долетая до
  `on<DataUpdateStartAll>`'s `catch` — единственного места, которое пишет в
  `DataUpdates` через `_addDataUpdateError`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — читается
  косвенно через `_authRepository.isAuthorized()`, определяющее, дойдёт ли
  проход вообще до `_syncAuthData()`/`_suncDevices()`; не изменяется этим
  сценарием.

### Бизнес-правила

- Push «правка» ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md))
  и push «создание» ([EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md))
  — независимые методы с разным условием запуска (см.
  [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты»), но
  разделяют одну и ту же архитектурную черту: оба сами перехватывают
  исключение и возвращают непроверяемый вызывающей стороной `bool`.
- **Ни один из трёх наблюдаемых исходов шага 7-8 (сетевое исключение,
  логический отказ сервера, настоящий успех) не меняет локальное состояние
  строки.** Единственное различие между ними — попадает ли одна строка в
  `Talker` (только при исключении) — никак не влияющее на дальнейшее
  поведение `_suncDevices()` или на то, что видит пользователь.
- «Повтор на следующем проходе» — не оформленный явно retry/backoff, а
  прямое следствие того, что фильтр `isNeedUpdate == true && remoteId !=
  null` в `updateDevicesOnSHTP()` каждый раз заново отбирает одни и те же
  строки, пока их не перезапишет pull. Нет ограничения на число повторов, нет
  экспоненциальной задержки, нет пометки «эта строка уже пыталась
  отправиться N раз».
- Единственный канал, которым локальное состояние вообще может «вылечиться»,
  — успешный `fetchDevicesFromApi()` с непустым ответом
  ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)).
  Если у этого конкретного аккаунта/устройства `GET /devices` когда-либо
  систематически возвращает пустой список (сам метод тоже поглощает любое
  исключение и возвращает `[]` — тот же паттерн, что и push-методы), строки
  с `isNeedUpdate == true` будут пересылаться на **каждом** полном
  sync-проходе неограниченно долго, без какого-либо сигнала пользователю или
  разработчику (кроме единичной строки в `Talker` на те проходы, где именно
  push словил сетевое исключение).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (сетевое исключение
внутри `updateDevicesOnSHTP()`, перехваченное самим методом,
непроверяемый `bool` на вызывающей стороне, отсутствие сброса
`isNeedUpdate`/`remoteId` в любой из трёх веток) полностью воспроизводится
статическим чтением кода целиком:
`DataUpdateBloc._syncAuthData` → `._suncDevices` →
`DeviceSettingsRepository.updateDevicesOnSHTP` → `CustomDioClient.call` /
`DioClient`; отдельно подтверждено чтением всего тела
`updateDevicesOnSHTP()`, что метод не содержит ни одного вызова
`dao.update*`/`DevicesCompanion` — только `dao.getAll()` на чтение.
Исправление (например, проверка возвращённого `bool` в `_suncDevices()`,
явный сброс `isNeedUpdate`/проставление даты последней попытки после
успешного ответа сервера) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над
дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный внешний `try/catch` всего прохода — никогда не срабатывает из-за этого шага, поскольку исключение не покидает `updateDevicesOnSHTP()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_emitProgress(dataKey: DataKey.syncDevices)` (без `dataCategory`), затем `_suncDevices()`, последним шагом после `updateAndSyncSHTP` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` (результат отброшен) → `fetchDevicesFromApi()` → условно `syncDevicesOnSHTP()` → условно `clearAndInsertAll` → `ensureDeviceInDatabase()` → `ScannerService.applySavedTerminalSettings()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | параметр `dataCategory` опционален — при вызове с `dataKey: DataKey.syncDevices` не передан, `_currentDataCategory` остаётся тем, что выставил предыдущий шаг (`updateAndSyncSHTP` → `DataCategory.syncReports`) |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateDevicesOnSHTP` | CURRENT | предмет сценария — единственное обращение к БД внутри метода на чтение (`dao.getAll()`), собственный `try/catch` вокруг `rpcClient.call`, возвращает `bool`, не пишет `isNeedUpdate`/`remoteId` ни в одной ветке |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.fetchDevicesFromApi` | CURRENT | единственный код, способный сбросить `isNeedUpdate` для уже существующей строки — только если возвращает непустой список; тоже поглощает любое исключение и возвращает `[]` |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.syncDevicesOnSHTP`, `._isSyncableDevice` | CURRENT | парный push «создание» ([EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)) — тот же паттерн проглоченного исключения, другое условие запуска |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `Devices.isNeedUpdate`, `.remoteId`, `DeviceDtoMapper.toCompanion` | CURRENT | `toCompanion()` — единственное место, явно проставляющее `isNeedUpdate: const Value(false)` для строки, приходящей с сервера; вызывается только из pull-ветки |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | источник исключения (не-2xx/сеть) и источник «логического отказа без исключения» (200 OK, `Map` без `data`/`animal_exits`, явный `status: 'error'`) |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey.syncDevices` | CURRENT | `DataKey.syncDevices` существует как строковый ключ, но соответствующего значения `DataCategory.syncDevices` в перечислении нет вовсе (см. «Открытые вопросы») |
| `lib/repositories/base_repository.dart`, `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseRepository/BaseDao.clearAndInsertAll` | CURRENT | полная замена таблицы `Devices` результатом непустого pull'а — единственный путь, восстанавливающий `isNeedUpdate == false` |

## Критерии приёмки

- Если для непустого `toSend` (хотя бы одна строка `isNeedUpdate == true &&
  remoteId != null`) вызов `rpcClient.call` внутри `updateDevicesOnSHTP()`
  бросает исключение, оно перехватывается собственным `catch` метода,
  логируется через `Talker.handle` и не перебрасывается — метод возвращает
  `false`, не изменяя ни одной строки `Devices`.
- `_suncDevices()` не читает и не проверяет этот `bool` — выполнение
  безусловно продолжается к `fetchDevicesFromApi()`, независимо от исхода
  предыдущего шага.
- Полный sync-проход не переходит в `DataUpdateFailure` из-за этого отказа —
  при отсутствии других независимых причин проход завершается
  `DataUpdateSuccess`.
- `DataUpdates` не получает ни одной строки об этом отказе.
- Строка(и), выбранные фильтром `isNeedUpdate == true && remoteId != null`,
  остаются с этими же значениями (`isNeedUpdate == true`, `remoteId`
  неизменен) после завершения `updateDevicesOnSHTP()` — независимо от того,
  бросил ли `rpcClient.call` исключение, вернул ли логический отказ без
  исключения, или реально успешно завершился.
- На следующем полном sync-проходе тот же фильтр повторно отбирает эти же
  строки для отправки, если только не произошёл промежуточный `fetchDevicesFromApi()`
  с непустым ответом и последующий `clearAndInsertAll`, который проставляет
  `isNeedUpdate: false` через `DeviceDtoMapper.toCompanion()`.

## Связанные тесты

**TBD — теста нет.** `test/blocs/data_update_bloc_test.dart` регистрирует
`DeviceSettingsRepository` как `MockDeviceSettingsRepository()` через `getIt`
(`class MockDeviceSettingsRepository extends Mock implements
DeviceSettingsRepository {}`), но ни разу не стабит ни один из его методов
(`when(() => ...)` для `updateDevicesOnSHTP`/`ensureDeviceInDatabase`/
`fetchDevicesFromApi`/`syncDevicesOnSHTP` в файле не встречается вообще), а
единственные два теста этого файла — `'DataUpdateBloc конструируется с
полным набором зависимостей из getIt'` (смоук-тест конструктора, не
диспатчит никакое событие) и `'DataUpdateClear очищает пользовательские
данные БД'` (тестирует `DataUpdateClear`, не `DataUpdateStartAll`) — ни один
из них не доходит до `_syncAuthData()`/`_suncDevices()`. Отдельного файла
`test/repositories/devices_settings_repository_test.dart` не существует
(`find test -iname "*device*"` — пусто). `grep -r "UC-184" test/` не находит
ничего.

## Открытые вопросы и ограничения

- **Отсутствие сброса `isNeedUpdate`/`remoteId` — осознанное решение
  («сервер сам разберётся с дублями по вторичному ключу», «следующий pull
  всё равно перезапишет») или недосмотр — ничем в коде/комментариях не
  зафиксировано.** В отличие от подавляющего большинства других
  sync-сущностей приложения (например, `Movement`/`Vaccination`/`AnimalWeighing`,
  где push, как правило, явно выставляет `sync: true` при успехе), здесь
  локальное состояние вообще не завязано на исход push — единственная
  завязка идёт через параллельный, независимый pull.
- **Тройное неразличение исходов (сетевое исключение / логический отказ
  сервера без исключения / настоящий успех) — тот же класс проблемы, что уже
  задокументирован для инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  «б»), но здесь без разрушительных последствий: там неразличение приводит к
  безвозвратному удалению данных; здесь — к их избыточной, но не разрушающей
  их же самих, повторной отправке.** Является ли `updateDevicesOnSHTP()`
  вообще предназначенным отличать успех от отказа — неясно: даже при
  настоящем сетевом успехе метод не пишет ничего в локальную БД, то есть
  «правильное» поведение (сброс `isNeedUpdate` при успехе) для этого метода
  сегодня не реализовано вовсе, а не просто «сломано в error-ветке».
- **Побочная находка: значения `DataCategory` не включают `syncDevices`,
  хотя строковый `DataKey.syncDevices` существует.** `_emitProgress(emit:
  emit, dataKey: DataKey.syncDevices)` (вызывается непосредственно перед
  `_suncDevices()`) не передаёт `dataCategory` — параметр опционален, и при
  `null` `_currentDataCategory` не меняется, оставаясь равным значению,
  выставленному предыдущим шагом (`updateAndSyncSHTP` → `DataCategory.syncReports`).
  Практического следствия для сценария этого файла нет (сам
  `updateDevicesOnSHTP()` никогда не пропускает исключение наружу), но если
  бы будущий рефакторинг добавил необработанный throw где-то внутри
  `_suncDevices()` вне `updateDevicesOnSHTP()`/`syncDevicesOnSHTP()`/
  `fetchDevicesFromApi()` (все три сегодня сами поглощают исключения) —
  например, в `ensureDeviceInDatabase()` (реальные Drift-операции записи, без
  `try/catch`) или в `ScannerService.applySavedTerminalSettings()` — итоговая
  строка `DataUpdates` записала бы это как отказ категории `syncReports`, не
  какой-либо категории, относящейся к устройствам, потому что такой
  категории не существует в перечислении вовсе.
- **Не пересекается с [UC-180](UC-180-ACTOR-5-EVT-89-ENT-22-UPDATE_ERROR-IN-PROFILE.md).**
  Тот файл — технический отказ DAO-записи при локальном сохранении настройки
  пользователем ([EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md),
  ACTOR-5); этот — отказ сетевого push-шага sync-прохода (`EVT-91`, ACTOR-4).
  Оба классифицированы `UPDATE_ERROR` для одной и той же сущности
  ([ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)), но описывают
  непересекающиеся точки отказа одного жизненного цикла записи.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DeviceSettingsRepository.updateDevicesOnSHTP`
  → `CustomDioClient.call` → `DioClient`), без запущенного теста,
  подтверждающего именно эту ветку (см. «Связанные тесты» — TBD). В
  частности, не подтверждено эмпирически, как часто на практике
  `fetchDevicesFromApi()` (`GET /devices`) реально возвращает непустой список
  для только что отправленных правок — от этого напрямую зависит, сколько
  полных sync-проходов подряд одна и та же строка будет отправляться
  повторно в реальных условиях.
