# UC-181 — Первичная отправка настроек сканера на сервер: batch-создание всех устройств одним запросом, когда сервер ещё не вернул ни одной записи

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же push-шаг, что описан в [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md) —
внутри `DataUpdateBloc._suncDevices()`, **условно**, только если предшествующий
в этом же проходе `fetchDevicesFromApi()` (pull №1,
[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
вернул пустой список — `DeviceSettingsRepository.syncDevicesOnSHTP()` шлёт
`POST /devices/store` со всеми «синкуемыми» устройствами
(`ScannerDeviceTypes.defaults` — фактически 14 типов в текущем коде, не 13,
как указано в тексте [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md);
пересчитано `python3` по литералу массива, см. «Открытые вопросы») одним
batch-запросом. Здесь описана именно успешная ветка — сетевой вызов
`rpcClient.call(message)` завершается без исключения.

Ключевая находка, проверенная отдельно чтением кода: даже в этой, успешной
ветке, локальное состояние `Devices` этим вызовом **не меняется вовсе**.
`syncDevicesOnSHTP()` не проставляет `remoteId` и не сбрасывает
`isNeedUpdate` ни одной строке — единственное, что делает вызывающий код
(`_suncDevices()`) с булевым результатом метода — отбрасывает его (`await
_deviceSettingsRepository.syncDevicesOnSHTP();`, без `if`, без переменной).
«Создание» с точки зрения локального хранилища завершается не этим
событием, а следующим сразу за ним pull'ом (pull №2, тот же
[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
— и то только если он вернёт непустой список.

Дополнительная находка: условие срабатывания («pull вернул пустой список»)
структурно неотличимо от «pull технически отказал» — `fetchDevicesFromApi()`
сам перехватывает любое исключение и тоже возвращает `[]` (см.
[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)).
Это означает, что данный «первичный push» в принципе может срабатывать не
только строго один раз в жизни аккаунта/установки, а на любом проходе, где
`GET /devices` технически не удался — см. «Альтернативные потоки» и
«Открытые вопросы».

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
push нет и не может быть — это глубоко вложенный шаг автоматического
прохода. Пользователь лишь ранее инициировал сам полный sync-проход
(`DataUpdateStartAll`), одним из нескольких способов:

- явно — кнопка обновления навбара (`main_page.dart`, читает состояние сети
  через `NetworkConnectivityService` перед диспатчем), кнопка на
  `profile_settings_view.dart` (`DataUpdateStartAll(resetNavigationOnSuccess:
  true)`), кнопка «Обновить» на экране «В работе» (`in_work_page.dart`,
  `DataUpdateStartAll(isUpdateData: true)`), кнопка повтора на
  `data_update_page.dart` (`DataUpdateStartAll(showDataUpdatePage: false,
  again: true)`);
- автоматически — `main_page.dart`'s `BlocListener<AuthBloc, AuthState>`
  диспатчит `DataUpdateStartAll` при переходе `AuthToMain` (успешный
  вход/восстановление сессии), без отдельного нажатия.

Дальше проход идёт без участия пользователя на уровне отдельного сетевого
вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).
Достижимо только для **авторизованного** пользователя — `_suncDevices()`
вызывается исключительно из `_syncAuthData()`, которая сама вызывается
только при `_authRepository.isAuthorized() == true`; для гостя этот шаг (и
весь этот use-case) недостижим ни при каких условиях.

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети (`NetworkConnectivityService.hasConnection()`, иначе
   `DataUpdateFailure` сразу, до входа сюда) и `loadDirectories`/`_loadBoardDirectories`,
   при `_authRepository.isAuthorized()` вызывается `await
   _syncAuthData(event, emit)`.
2. `_syncAuthData` последовательно вызывает (в этом сценарии все они
   завершаются независимо от него, без ошибки): `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro(event, emit)`, `updateAndSyncSHTP(event, emit)` —
   последний, среди прочего, вызывает `_emitProgress(dataKey:
   DataKey.syncReports, dataCategory: DataCategory.syncReports)`, фиксируя
   `_currentDataCategory = DataCategory.syncReports` (важно для шага 3 —
   `DataCategory` вообще не содержит значения `syncDevices`, см.
   «Открытые вопросы»). Затем: `_emitProgress(emit: emit, dataKey:
   DataKey.syncDevices)` — **без** аргумента `dataCategory` (нет такого
   значения enum'а) — и `await _suncDevices()`.
3. Внутри `_suncDevices()`, первым шагом — `await
   _deviceSettingsRepository.ensureDeviceInDatabase()`: безусловный
   идемпотентный upsert — сначала `dao.deleteDevicesByTypes(_obsoleteDeviceTypes)`
   (легаси-типы `'TCD'`/`'RFID'`/`'terminal'`/`'uhf_scanner_keyboard'`), затем
   для каждого из `defaultDevices` (14 записей в текущем коде) —
   `_ensureDefaultDevice`, гарантирующий ровно одну строку на тип. После
   этой строки таблица `Devices` **гарантированно** содержит все 14
   дефолтных типов — на свежей установке они создаются здесь же, впервые,
   с `remoteId == null`, `isNeedUpdate == false` (значение по умолчанию
   Drift-колонки).
4. `await _deviceSettingsRepository.updateDevicesOnSHTP()` —
   [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md),
   безусловный PUT-шаг, не предмет этого файла. На свежей установке
   `devicesToStore = localDevices.where((e) => _isSyncableDevice(e) &&
   e.isNeedUpdate == true && e.remoteId != null)` пуст для каждой строки
   (`remoteId` ещё `null` у всех) → `toSend.isEmpty` → метод возвращает
   `true` немедленно, ни разу не вызвав `rpcClient.call`.
5. `remoteDevices = await
   _deviceSettingsRepository.fetchDevicesFromApi()` (pull №1,
   [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) —
   `GET ${Constants.farmServiceApi}/devices`; в этом сценарии возвращает
   пустой список — **либо потому, что у сервера действительно нет ни одной
   записи устройств для этого пользователя/установки** (легитимный «первый
   раз»), **либо потому, что сам вызов бросил исключение**, перехваченное
   собственным `catch (e, stackTrace) { getIt<Talker>().handle(e,
   stackTrace); return []; }` метода — обе причины дают на этом шаге один и
   тот же наблюдаемый результат, `[]` (см. «Альтернативные потоки»).
6. `if (remoteDevices.isEmpty)` — истинно → `await
   _deviceSettingsRepository.syncDevicesOnSHTP()` —
   [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md),
   предмет этого файла.
7. Внутри `syncDevicesOnSHTP()`: `localDevices = await dao.getAll()` — вся
   физическая таблица `Devices` (гарантированно непуста прямо сейчас, шаг
   3 её только что безусловно пересеял). `devicesToStore =
   localDevices.where(_isSyncableDevice)` — `_isSyncableDevice(device) =>
   ScannerDeviceTypes.defaults.contains(device.type)`; поскольку шаг 3
   гарантирует, что в таблице нет других типов, кроме тех же 14
   дефолтных, в обычном случае `devicesToStore == localDevices` целиком —
   отфильтровывать здесь фактически нечего.
8. Каждая отобранная строка мапится в `DeviceDto`: `id: 0` (значение-заглушка
   — при создании клиент не знает и не может знать серверный id; контраст с
   `updateDevicesOnSHTP`, [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md),
   где `id: d.remoteId!` — там это реальный серверный id), `deviceCredentials`
   — текущие локальные `name`, `region`, `power`/`maxPower`/`minPower`
   (каждое через `.toString()`), `ip`, `mac`, `antennas`,
   `availableOperations`, `isUseCameraForQr`, три поля `TcdAction` кнопок;
   `type`, `createdAt`, `updatedAt: d.updatedAt ?? d.createdAt`.
9. `if (toSend.isEmpty) return true;` — в обычном случае (14 непустых строк)
   не срабатывает; см. «Альтернативные потоки» для вырожденного случая.
10. `body = {'devices': toSend.map((e) => e.toJson()).toList()}`;
    `ApiMessage(link: '${Constants.farmServiceApi}/devices/store', method:
    ApiMethod.post, data: body)`.
11. `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc'); await
    rpcClient.call(message);` — **в этом сценарии (`CREATE_OK`) вызов
    завершается без исключения**: `CustomDioClient.call` получает обычный
    HTTP-ответ, не бросает `DioException` (никакого не-2xx статуса, Dio по
    умолчанию бросил бы иначе — `DioClient` не переопределяет
    `validateStatus`), возвращает `Map` вызывающей стороне.
12. `return true;` — **внутри `try`, не проверяя содержимое ответа вообще
    ни одним условием.** Метод не читает ни `response['status']`, ни
    какой-либо другой ключ тела ответа — единственное различие, которое он
    умеет делать, это «исключение брошено» (→ `catch`, `false`) против
    «вызов завершился без исключения» (→ `true`), независимо от того, что
    именно сервер ответил содержательно.
13. `_suncDevices()` (шаг 6) получает этот `true`, но **не сохраняет его
    никуда** — `await
    _deviceSettingsRepository.syncDevicesOnSHTP();` — голый оператор,
    результат синтаксически недостижим для дальнейшего кода. Никакая
    строка `Devices` не меняется этим вызовом: ни `remoteId`, ни
    `isNeedUpdate`, ни любое другое поле — таблица физически идентична
    состоянию сразу после шага 3.
14. `remoteDevices = await
    _deviceSettingsRepository.fetchDevicesFromApi()` (pull №2, тот же
    [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
    вызывается второй раз за этот проход). Это единственный механизм,
    которым только что созданные на сервере строки вообще могут попасть в
    локальную таблицу с `remoteId`: если сервер уже обработал `POST` из
    шага 11 и `GET /devices` теперь возвращает непустой список —
    `if (remoteDevices.isNotEmpty) await
    _deviceSettingsRepository.clearAndInsertAll(remoteDevices);` —
    `BaseRepository.clearAndInsertAll` полностью заменяет таблицу `Devices`
    только что полученными строками (`remoteId` заполнен, `isNeedUpdate ==
    false` — оба задаются `DeviceDtoMapper.toCompanion()` безусловно).
15. `await _deviceSettingsRepository.ensureDeviceInDatabase();` — вызывается
    повторно, чтобы досеять любой из 14 дефолтных типов, отсутствующий в
    только что полученном серверном ответе (например, если сервер вернул
    не все типы, а только часть).
16. `await getIt<ScannerService>().applySavedTerminalSettings();` —
    применяет уже (пере)загруженные настройки терминала к реальному
    оборудованию, если оно подключено; не предмет этого файла.
17. `_syncAuthData` возвращает управление; `on<DataUpdateStartAll>` (шаг 1),
    если ни один другой независимый шаг прохода не отказал, доходит до
    `emit(DataUpdateSuccess(resetNavigationOnSuccess:
    event.resetNavigationOnSuccess))`. Пользователь видит обычное
    успешное завершение обновления данных — никакого отдельного сигнала,
    специфичного именно для push устройств (успешного или нет), нигде не
    возникает.

### Альтернативные потоки

- **Пустой batch — вырожденный, но не полностью исключённый случай.**
  `toSend.isEmpty` (шаг 9) возвращает `true` немедленно, ни разу не вызывая
  `rpcClient.call` — формально тоже `CREATE_OK` (метод завершается успешно,
  без исключения), но без единого сетевого запроса. Сразу после шага 3
  (`ensureDeviceInDatabase()`, безусловно пересеявшего все 14 типов) это
  практически недостижимо в штатной работе; теоретически возможно, если
  сама запись в БД внутри `ensureDeviceInDatabase()` тихо не сохранилась
  (например, ошибка Drift, не проверяемая никаким `try/catch` в этом
  методе — исключение в этом случае просто всплыло бы раньше, не привело
  бы к пустой таблице) или при прямом вызове `syncDevicesOnSHTP()` в обход
  `_suncDevices()` (не происходит нигде в текущем коде — единственный
  вызывающий это `DataUpdateBloc._suncDevices()`).
- **Условие срабатывания («pull вернул пустой список») неотличимо от
  «pull технически отказал».** Как отмечено в «Назначение»/шаге 5,
  `fetchDevicesFromApi()` перехватывает любое исключение и тоже
  возвращает `[]` — то есть этот «первичный push» может сработать не
  только строго один раз (пока на сервере действительно нет ни одной
  записи), но и на любом более позднем проходе, где `GET /devices`
  случайно/временно отказал технически, — по коду это неотличимо от
  «сервер ещё пуст». Поскольку сам push при этом всегда шлёт `id: 0`
  (шаг 8) для каждого из 14 устройств и не несёт никакого другого
  стабильного клиентского ключа между вызовами (кроме `type`), повторное
  срабатывание этой ветки на следующем проходе повторно отправило бы тот
  же batch ещё раз — распознаёт ли сервер это как дубликат по `type`,
  этим кодом не определяется (см. «Открытые вопросы»).
- **Ответ сервера со `status: 'error'` при HTTP 200 не отличим от успеха
  этим методом.** По той же логике `CustomDioClient.call`, что
  задокументирована для инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  б) — `Map`-ответ без ключей `data`/`animal_exits` с явным
  `response.data['status'] == 'error'` возвращается «как есть», **без
  исключения**. `syncDevicesOnSHTP()` не читает `status` вообще ни одним
  условием (шаг 12) — такой ответ приводит к тому же `return true;`, что и
  настоящий успех. Полноценная спецификация этой ветки как отдельного
  `CREATE_ERROR`/`REJECTED` — вне рамок этого файла (этот use-case
  специфицирует `CREATE_OK` по заданию текущего прохода); упомянуто здесь
  только как структурная граница того, что данный `CREATE_OK` на самом
  деле гарантирует (см. «Открытые вопросы»).
- **Сетевое исключение (`CREATE_ERROR`, отдельный, не этот сценарий) не
  прерывает проход.** Если `rpcClient.call` на шаге 11 бросает исключение —
  `catch (e, stackTrace) { getIt<Talker>().handle(e, stackTrace); return
  false; }` перехватывает его внутри самого `syncDevicesOnSHTP()`; `_suncDevices()`
  всё равно продолжает на шаг 14 как ни в чём не бывало (тот же отброшенный
  булев результат, что и в успешном случае, шаг 13) — весь проход не
  проваливается из-за этого отказа. Это принципиально другой класс
  сценария, не документируемый этим `CREATE_OK`-файлом.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность сценария. Читается (`dao.getAll()`, шаг 7) для построения тела
  запроса; **не изменяется этим вызовом ни в одном поле** — `remoteId`,
  `isNeedUpdate`, любое другое поле остаются такими же, как после шага 3, и
  до, и после успешного (или неуспешного) `syncDevicesOnSHTP()`. Физическая
  запись (`remoteId` заполняется, `isNeedUpdate` гарантированно `false`)
  происходит только на шаге 14, отдельным событием
  ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)),
  и только если оно вернуло непустой список.

### Бизнес-правила

- Один batch-запрос на все синкуемые устройства сразу — не по одному, не
  по группам; успех/отказ HTTP-вызова применяется ко всему набору из 14
  типов одновременно, партиального успеха на уровне отдельного устройства
  в этой архитектуре не существует.
- `id: 0` в каждом отправляемом `DeviceDto` — не идентификатор, а
  заглушка; клиент сознательно не пытается сопоставить исходящую запись с
  каким-либо будущим ответом сервера по этому полю.
- Условие «предшествующий pull вернул пустой список» — единственное, что
  отличает этот push от push-обновления
  ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)):
  тот же batch-эндпоинт (`/devices/store`) не вызывается вовсе, если pull
  уже вернул хотя бы одну запись — в этом случае обновление идёт только
  через `PUT /devices/update`, только по строкам с `isNeedUpdate == true`.
- Возвращаемое `syncDevicesOnSHTP()` булево значение не используется нигде
  выше по стеку вызовов — с точки зрения бизнес-логики прохода push
  всегда «прозрачен»: он не может ни провалить проход, ни явно
  подтвердить пользователю, что настройки действительно долетели до
  сервера. Единственное наблюдаемое пользователем последствие успешного
  push — это то, что случится (или нет) на следующем pull того же
  прохода (шаг 14) или одного из последующих.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий полностью воспроизводится
статическим чтением кода: `DataUpdateBloc._suncDevices` →
`DeviceSettingsRepository.syncDevicesOnSHTP` → `CustomDioClient.call`.
Действительно ли сервер дедуплицирует повторные batch'и по типу устройства
(актуально для случая повторного срабатывания из-за отказавшего pull, см.
«Альтернативные потоки»/«Открытые вопросы») — этим кодом не определяется и
не может быть проверено чтением одного клиентского репозитория; это
ограничение видимости, а не блокер написания этого файла. Исправление
(например, проверка ответа сервера перед `return true`, либо сохранение
`remoteId` сразу по ответу `POST`, без ожидания следующего pull) в рамках
этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_suncDevices()` последним шагом, после `updateAndSyncSHTP`; фиксирует `_currentDataKey = DataKey.syncDevices` без сопутствующей `DataCategory` (такого значения enum не существует) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` → `fetchDevicesFromApi()` (pull №1) → если пуст: `syncDevicesOnSHTP()` (этот файл) → `fetchDevicesFromApi()` (pull №2) → если непуст: `clearAndInsertAll()` → `ensureDeviceInDatabase()` (повторно) → `ScannerService.applySavedTerminalSettings()`; булев результат `syncDevicesOnSHTP()` нигде не читается |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.syncDevicesOnSHTP` | CURRENT | предмет сценария — сборка batch'а из всех `_isSyncableDevice`-строк с `id: 0`, `POST /devices/store`, `try/catch` без чтения тела ответа |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `._ensureDefaultDevice`, `.defaultDevices`, `._obsoleteDeviceTypes` | CURRENT | безусловное пересеивание 14 дефолтных типов непосредственно перед push'ем — гарантирует непустой `localDevices` на шаге 7 |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.updateDevicesOnSHTP` | CURRENT | предшествующий безусловный PUT-шаг ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)) — на свежей установке no-op (`remoteId` ещё `null` у всех строк) |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.fetchDevicesFromApi`, `.clearAndInsertAll` | CURRENT | pull №1/№2 ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) — единственный способ, которым `remoteId` фактически попадает в локальные строки после этого push'а |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository._isSyncableDevice` | CURRENT | фильтр `ScannerDeviceTypes.defaults.contains(type)` — в обычном случае пропускает все строки без исключения |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.defaults`, `DeviceDto`, `DeviceCredentialsDto` | CURRENT | 14 синкуемых типов (не 13, см. «Открытые вопросы»); DTO, отправляемый в теле `POST` |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый путь `/devices/store` |
| `lib/network/api_client/api_client.dart`, `lib/network/api_client/api_message.dart` | `ApiClient`, `ApiMessage`, `ApiMethod.post` | CURRENT | обёртка сетевого вызова; `instanceName: 'farm_rpc'` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | в этом (`CREATE_OK`) сценарии не бросает исключение и не возвращает `status: 'error'`; при `status: 'error'` вернул бы ответ как есть, не проверяемый вызывающим методом (см. «Альтернативные потоки») |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/services/scanner_service.dart` | `ScannerService.applySavedTerminalSettings` | CURRENT | вызывается последним шагом `_suncDevices()`, после (пере)загрузки локальных настроек pull'ом; не предмет этого файла |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.syncDevices`, `DataCategory` (enum без значения `syncDevices`) | CURRENT | ключ прогресса для этого шага; отсутствие соответствующей категории — почему `_emitProgress` на шаге 2 вызывается без `dataCategory` |

## Критерии приёмки

- На каждом полном sync-проходе для авторизованного пользователя
  `_suncDevices()` выполняет `ensureDeviceInDatabase()` →
  `updateDevicesOnSHTP()` → `fetchDevicesFromApi()` строго в этом порядке;
  `syncDevicesOnSHTP()` вызывается тогда и только тогда, когда этот
  `fetchDevicesFromApi()` вернул пустой список.
- `syncDevicesOnSHTP()` включает в тело `POST /devices/store` все строки
  локальной таблицы `Devices`, чей `type` присутствует в
  `ScannerDeviceTypes.defaults`, независимо от значений `isNeedUpdate`/`remoteId` —
  в отличие от `updateDevicesOnSHTP()`, здесь нет фильтра по этим полям.
- Если сетевой вызов внутри `syncDevicesOnSHTP()` завершается без
  исключения (успех, предмет этого файла, либо содержательный отказ
  сервера, неотличимый от успеха этим кодом), метод возвращает `true`;
  если вызов бросает исключение — `false`. Оба случая приводят к
  идентичному дальнейшему поведению `_suncDevices()` — возвращаемое
  значение нигде не влияет на дальнейшее выполнение.
- Ни в успешном, ни в неуспешном случае `syncDevicesOnSHTP()` не изменяет
  ни одной строки локальной таблицы `Devices` напрямую (ни `remoteId`, ни
  `isNeedUpdate`) — единственный способ, которым локальное хранилище
  получает `remoteId`/`isNeedUpdate == false`, это последующий непустой
  `fetchDevicesFromApi()` в том же проходе.
- Отказ (в т.ч. брошенное исключение) внутри `syncDevicesOnSHTP()` сам по
  себе не приводит к `DataUpdateFailure` всего прохода — исключение
  перехвачено внутри самого метода и никогда не всплывает выше.

## Связанные тесты

`test/blocs/data_update_bloc_test.dart` и `test/pages/scanning_bloc_test.dart` —
единственные два файла, где `DeviceSettingsRepository` вообще фигурирует
(`grep -rln "DeviceSettingsRepository" test/`), и в обоих — только как
мок-зависимость конструктора соответствующего blok'а/cubit'а
(`MockDeviceSettingsRepository`, регистрируется в `getIt`, метод
`ensureDeviceInDatabase`/`getDefaultDevices` стаббится для не относящихся
к этому сценарию тестов sync-прохода/сканирования). Ни один тест не
вызывает и не проверяет `syncDevicesOnSHTP` — `grep -rn "syncDevicesOnSHTP"
test/` пуст. `test/blocs/data_update_bloc_test.dart` содержит единственный
тест, не относящийся к `_suncDevices()`:
`'DataUpdateBloc конструируется с полным набором зависимостей из getIt'`, и
единственный `blocTest`, тоже не относящийся к этому сценарию:
`'DataUpdateClear очищает пользовательские данные БД'`. Отдельного файла
`test/repositories/devices_settings_repository_test.dart` не существует
(`find test -iname "*devices_settings*"` — пусто).

**TBD — теста нет.** Ни на успешную ветку `syncDevicesOnSHTP()` (этот
файл), ни на её отказ, ни на условие срабатывания («pull вернул пустой
список»), ни на то, что булев результат отбрасывается вызывающим кодом —
не существует ни одного unit-теста ни для
`DeviceSettingsRepository.syncDevicesOnSHTP`, ни для
`DataUpdateBloc._suncDevices` целиком (сам `DataUpdateStartAll` не
покрыт юнит-тестами вообще — см. комментарий в начале
`test/blocs/data_update_bloc_test.dart` про `>25` зависимостей и реальный
DNS-запрос первой строкой обработчика).

## Открытые вопросы и ограничения

- **Условие «pull вернул пустой список» не отличает «сервер действительно
  пуст» от «GET /devices технически отказал».** Оба случая дают
  одинаковый `[]` на шаге 5, оба одинаково запускают этот push. Является
  ли фактическое возможное повторное срабатывание «первичного» push'а на
  произвольном более позднем проходе (не только один раз в жизни
  аккаунта/установки) осознанным допущением или недосмотром — ничем в
  коде/комментариях не зафиксировано.
- **Дедупликация на сервере не верифицируема из этого кода.** Поскольку
  каждый push отправляет `id: 0` для каждого устройства и не несёт другого
  стабильного клиентского ключа между вызовами (кроме `type`), повторное
  срабатывание push'а из-за периодически отказывающего pull'а могло бы в
  принципе создавать дублирующиеся записи на сервере — подтвердить или
  опровергнуть это можно только против реального бэкенда, не чтением
  клиентского репозитория.
- **Возвращаемое `bool` метода `syncDevicesOnSHTP()` — мёртвая
  API-поверхность.** Единственный вызывающий код (`_suncDevices()`)
  отбрасывает его безусловно; является ли это заделом под будущего
  вызывающего (который однажды начнёт проверять результат), либо
  наследием прошлого рефакторинга — не задокументировано.
- **Расхождение с текстом [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md):**
  тот файл описывает каталог как «13 типов устройств»; независимый
  пересчёт литерала `ScannerDeviceTypes.defaults` (и параллельного списка
  `DeviceSettingsRepository.defaultDevices`) для этого use-case даёт 14
  элементов. Отмечено здесь только как наблюдение при повторной проверке
  фактов чтением кода — `ENT-22` заморожен и не редактируется этим файлом.
- **Отсутствие `DataCategory.syncDevices`** означает, что любая ошибка,
  случившаяся внутри `_suncDevices()` (например, в
  `ensureDeviceInDatabase()` или `ScannerService.applySavedTerminalSettings()`,
  а не в самом `syncDevicesOnSHTP()`, который никогда не пробрасывает
  исключение наружу) была бы залогирована в `DataUpdates` под категорией,
  оставшейся от предыдущего шага прохода (`DataCategory.syncReports`, см.
  «Основной поток», шаг 2) — не какой-либо специфичной для устройств
  категорией. Не относится напрямую к `CREATE_OK`-сценарию этого файла, но
  объясняет, почему для этого шага в принципе не может существовать
  собственной строки `DataUpdates` при отказе.
- Не проверено эмпирически на реальном запуске против настоящего
  бэкенда — вывод сделан статическим чтением кода
  (`DeviceSettingsRepository.syncDevicesOnSHTP` → `CustomDioClient.call` →
  `DioClient`), без запущенного теста, подтверждающего именно эту ветку
  (см. «Связанные тесты» — TBD).
