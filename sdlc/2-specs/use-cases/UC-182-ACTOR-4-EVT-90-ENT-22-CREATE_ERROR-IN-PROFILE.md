# UC-182 — Первичная отправка настроек устройств на сервер отказывает: отказ перехватывается внутри репозитория и результат не проверяется вызывающим кодом

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же условный push, что описан в [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md) —
`DeviceSettingsRepository.syncDevicesOnSHTP()` отправляет одним batch-запросом
(`POST /devices/store`) все «синкуемые» устройства, но только когда
предшествующий в этом же проходе pull ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
вернул пустой список — т.е. фактически только пока на сервере ещё нет ни
одной строки устройств для этого пользователя/установки. Здесь описан путь,
которым этот push отказывает, и он **структурно недостижим как исключение**,
долетающее до вызывающего кода — тот же класс дефекта, что уже
задокументирован для проверки доступности BOARD
([UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)): метод сам
перехватывает свой отказ и возвращает значение, которое никто не читает.

Метод `syncDevicesOnSHTP()` целиком состоит из двух зон разной защищённости
(проверено чтением файла целиком): сборка батча (`dao.getAll()`,
фильтрация `_isSyncableDevice`, построение `DeviceDto`/`.toJson()`) не
защищена никаким `try/catch`; сам сетевой вызов (`rpcClient.call(message)`)
обёрнут в собственный `try { ...; return true; } catch (e, stackTrace) {
getIt<Talker>().handle(e, stackTrace); return false; }`. Оба верифицированных
пути отказа сведены в один файл, как и в аналогичных сценариях других
под-областей ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)):

- (а) — исключение внутри `rpcClient.call(message)` (сеть недоступна,
  таймаут, любой не-2xx HTTP-ответ) — перехватывается **тем же методом**,
  логируется через `Talker.handle`, метод возвращает `false`.
  `DataUpdateBloc._suncDevices()` вызывает `await
  _deviceSettingsRepository.syncDevicesOnSHTP();` **без сохранения и без
  проверки результата** — `bool` отброшен. Проход продолжается совершенно
  так же, как при настоящем успехе: следующий `fetchDevicesFromApi()`,
  `ensureDeviceInDatabase()`, `ScannerService.applySavedTerminalSettings()`,
  и в конце — `DataUpdateSuccess` для всего sync-прохода, если остальные
  независимые шаги не отказали по другой причине. Никакого сигнала об этом
  отказе не возникает нигде в приложении.
- (б) — исключение **до** входа в `try` (например, из `dao.getAll()` при
  сборке `localDevices`) — этой зоны собственный `catch` метода не касается
  вообще, исключение всплывает из `syncDevicesOnSHTP()` необработанным. Это
  единственная ветка этого сценария, которая реально доходит до внешнего
  `try/catch` (`on<DataUpdateStartAll>`) и превращается в видимый
  `DataUpdateFailure` — но даже тогда запись `DataUpdates` об отказе
  оказывается помечена чужой, устаревшей категорией (`DataCategory.reports`,
  а не чем-то относящимся к устройствам), потому что для устройств вообще не
  существует отдельного значения `DataCategory` — см. «Основной поток», шаг
  9б, и «Открытые вопросы».

Единственный наблюдаемый пользователем эффект ветки (а) — устройства так и
не появляются на сервере (`remoteId` никогда не проставляется для них), и
это станет заметно лишь косвенно, при следующем `fetchDevicesFromApi()`
(тоже перехватывающем свою собственную ошибку и возвращающем пустой список —
[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) —
неотличимо от «на сервере действительно пусто».

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет: проход был запущен ранее авторизованным пользователем —
`DataUpdateStartAll`, диспатчится, например, из `main_page.dart` (кнопка
обновления навбара), `profile_settings_view.dart`, `in_work_page.dart` или
`data_update_page.dart`, либо автоматически `main_page.dart`'s
`BlocListener<AuthBloc, AuthState>` при переходе `AuthToMain` — дальше
проход идёт без участия пользователя на уровне отдельного сетевого вызова,
как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).

Важное отличие этого сценария от остальных `ACTOR-4`-сценариев `MOD-6`: весь
шаг устройств (`_suncDevices()`) выполняется **только для авторизованного
пользователя** — `on<DataUpdateStartAll>` вызывает `_syncAuthData(event,
emit)` (внутри которого лежит `_suncDevices()`) строго под условием
`if (_authRepository.isAuthorized()) await _syncAuthData(event, emit);`. Для
гостя `_suncDevices()` не вызывается вообще ни разу за весь sync-проход —
локальные настройки устройств гостя, в отличие от их создания/редактирования
([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), гость=авторизован
одинаково), никогда не покидают устройство.

Строки, которые здесь не удаётся отправить, были заведены не пользователем
напрямую, а идемпотентным сидированием каталога
(`DeviceSettingsRepository.ensureDeviceInDatabase()`, см.
[ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), «Инварианты») — сам
`ensureDeviceInDatabase()` тоже вызывается безусловно первым шагом
`_suncDevices()`, до push.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. После проверки сети
   (`NetworkConnectivityService.hasConnection()` — истинно, иначе
   `DataUpdateFailure` сразу, до входа сюда), `loadDirectories()` и
   `_loadBoardDirectories()`, при `_authRepository.isAuthorized()` вызывается
   `await _syncAuthData(event, emit)` — **без собственного** `try/catch`
   вокруг этого вызова: единственный внешний перехват — на уровне
   `on<DataUpdateStartAll>`.
2. `_syncAuthData` последовательно вызывает `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro(event, emit)`, `updateAndSyncSHTP(event, emit)` — в
   этом сценарии все они завершаются без ошибки, независимой от этого
   сценария. `updateAndSyncSHTP` заканчивается `loadShtp(emit)`, который
   вызывает `_emitProgress(dataKey: DataKey.reports, dataCategory:
   DataCategory.reports)` — это последний вызов `_emitProgress` с явно
   переданным `dataCategory` перед шагом 3, важно для шага 9б.
3. `_emitProgress(emit: emit, dataKey: DataKey.syncDevices)` — вызван **без
   аргумента `dataCategory`**: `_emitProgress` (`lib/blocs/data_update/data_update_bloc.dart`)
   обновляет `_currentDataCategory` только `if (dataCategory != null)` —
   здесь он `null`, поэтому `_currentDataCategory` остаётся тем, что было
   установлено на шаге 2 (`DataCategory.reports`), не меняясь на что-либо
   относящееся к устройствам. `_currentDataKey` при этом становится
   `DataKey.syncDevices` безусловно (эта часть присваивается независимо от
   `dataCategory`).
4. `await _suncDevices()` — тоже без собственного `try/catch`. Внутри:
   `await _deviceSettingsRepository.ensureDeviceInDatabase()` (безусловный
   идемпотентный upsert каталога из 13 типов — гарантирует, что к этому
   моменту в таблице `Devices` есть ровно по одной строке на каждый тип
   `ScannerDeviceTypes.defaults`), затем `await
   _deviceSettingsRepository.updateDevicesOnSHTP()` (правки,
   [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md), не
   в границах этого файла), затем `var remoteDevices = await
   _deviceSettingsRepository.fetchDevicesFromApi();` (первый pull,
   [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) —
   в этом сценарии возвращает пустой список (сервер ещё не знает ни одной
   записи устройств для этого пользователя/установки).
5. `if (remoteDevices.isEmpty) { await
   _deviceSettingsRepository.syncDevicesOnSHTP(); ... }` — условие истинно,
   push вызывается. Внутри `syncDevicesOnSHTP()`
   (`lib/repositories/devices_settings/devices_settings_repository.dart`):
   `final localDevices = await dao.getAll();` — читает **всю** таблицу
   `Devices` (не только «синкуемые» типы); `final devicesToStore =
   localDevices.where(_isSyncableDevice);` — `_isSyncableDevice(device) =>
   ScannerDeviceTypes.defaults.contains(device.type)`, в норме проходят все
   13 строк, только что гарантированных шагом 4; `final toSend =
   devicesToStore.map((d) => DeviceDto(deviceCredentials:
   DeviceCredentialsDto(...), type: d.type, id: 0, createdAt: d.createdAt,
   updatedAt: d.updatedAt ?? d.createdAt)).toList();` — **эти четыре строки
   выполняются вне какого-либо `try/catch` этого метода**; `if
   (toSend.isEmpty) return true;` (вырожденный случай, см. «Альтернативные
   потоки»); `final body = {'devices': toSend.map((e) =>
   e.toJson()).toList()};` — тоже вне `try`; `final message = ApiMessage(link:
   '${Constants.farmServiceApi}/devices/store', method: ApiMethod.post, data:
   body);` — тоже вне `try`.
6. Только отсюда начинается защищённая зона:
   ```dart
   try {
     final rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc');
     await rpcClient.call(message);
     return true;
   } catch (e, stackTrace) {
     getIt<Talker>().handle(e, stackTrace);
     return false;
   }
   ```
   В этом сценарии `rpcClient.call(message)` (`CustomDioClient.call`,
   `lib/network/api_client/custom_dio_client.dart`) бросает исключение —
   сеть недоступна, таймаут, обрыв соединения, либо любой не-2xx
   HTTP-ответ (`DioClient`, `lib/network/dio_client.dart`, не
   переопределяет `validateStatus` — Dio по умолчанию бросает `DioException`
   вне 200–299). `CustomDioClient.call` сам логирует
   (`getIt.get<Talker>().error('CustomDioClient: call: $e')`) и безусловно
   перебрасывает (`rethrow`) — это исключение и есть то, что ловит `catch`
   строкой ниже.
7. `catch (e, stackTrace) { getIt<Talker>().handle(e, stackTrace); return
   false; }` — исключение перехвачено **здесь же, внутри
   `syncDevicesOnSHTP()`**, залогировано через `Talker.handle` (видно только
   в консоли/лог-файле `Talker`, не в UI, не в `DataUpdates`), метод
   возвращает `false` вместо того, чтобы позволить исключению всплыть
   дальше.
8. `_suncDevices()` (шаг 5, `_deviceSettingsRepository.syncDevicesOnSHTP();`) —
   вызов **не сохраняет и не проверяет** возвращённый `bool`: `await
   _deviceSettingsRepository.syncDevicesOnSHTP();` — выражение целиком, без
   `final result =`, без `if`. Выполнение продолжается совершенно так же,
   как если бы метод вернул `true`.
9. `remoteDevices = await _deviceSettingsRepository.fetchDevicesFromApi();` —
   второй pull, вызывается безусловно сразу после push, независимо от того,
   что тот вернул. В этом сценарии сервер по-прежнему не получил ни одной
   записи (push реально не дошёл), поэтому этот вызов тоже возвращает пустой
   список. `if (remoteDevices.isNotEmpty) { await
   _deviceSettingsRepository.clearAndInsertAll(remoteDevices); }` — условие
   ложно, `clearAndInsertAll` не выполняется: `remoteId` ни одной строки не
   проставляется.
10. `await _deviceSettingsRepository.ensureDeviceInDatabase();` (повторный
    вызов, досеивает недостающие дефолты — здесь ничего не меняет, т.к.
    ничего не удалялось) и `await
    getIt<ScannerService>().applySavedTerminalSettings();` выполняются
    безусловно, независимо от исхода push/pull.
11. `_suncDevices()` возвращает управление `_syncAuthData` без исключения;
    `on<DataUpdateStartAll>` (шаг 1) доходит до `emit(DataUpdateSuccess(
    resetNavigationOnSuccess: event.resetNavigationOnSuccess))`, если
    остальные независимые шаги прохода не отказали по другой причине.
    Пользователь видит **полностью успешное** завершение обновления данных.
12. **Итог ветки (а):** ни одна строка `Devices` не получает `remoteId`;
    `isNeedUpdate` не сбрасывается (в push и не участвовало — это поле
    касается только `updateDevicesOnSHTP()`); ни `DataUpdates`, ни `Talker`
    (кроме внутренней записи `Talker.handle`, не связанной с UI/логом
    sync-прохода), ни любой другой видимый пользователю канал не фиксируют
    этот отказ как отказ именно устройств. Условие следующего push
    (`remoteDevices.isEmpty` после первого pull) снова окажется истинным на
    следующем полном sync-проходе — push будет предпринят заново,
    неограниченное число раз, пока однажды не пройдёт успешно (или пока
    первопричина остаётся, то же самое повторится бесконечно, без единого
    сообщения пользователю).

**Ветка (б) — исключение до входа в защищённую зону (проверена отдельно).**

9б. Если исключение возникает не на шаге 6 (`rpcClient.call`), а раньше —
    например, `dao.getAll()` (шаг 5) бросает ошибку Drift (недоступна БД,
    диск, что угодно, срывающее чтение таблицы `Devices`) — собственный
    `catch` метода (шаг 7) этот код вообще не покрывает: он оборачивает
    только `try { final rpcClient = ...; await rpcClient.call(message); return
    true; }`, не строки сборки батча. Исключение покидает
    `syncDevicesOnSHTP()` необработанным.
10б. Оно же покидает `_suncDevices()` (шаг 5, без собственного `try/catch`) и
    `_syncAuthData` (шаг 2, тоже без перехвата), достигая единственного
    внешнего `try/catch` — `on<DataUpdateStartAll>` (шаг 1): `catch (error,
    stackTrace) { getIt<Talker>().error('Возникла при обновлении данных
    $error $stackTrace'); await _emitError(emit: emit, error: error,
    stackTrace: stackTrace); }`.
11б. `_emitError` вызывает `_addDataUpdateError(dataCategory:
    _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: ...)`.
    `_currentDataCategory` на этот момент равен `DataCategory.reports`
    (установлено на шаге 2 внутри `loadShtp()`, шаг 3 его не поменял —
    см. «Назначение»/шаг 3): `DataCategory` (`packages/sheep_farm_database/lib/entities/data_update/data_updates.dart`)
    вообще не содержит значения для устройств (`directories, animals, user,
    reports, syncReports, syncUnsentAnimals, syncDisposalListService,
    generations, generationsTypes` — полный список, ни одного элемента про
    `devices`). Строка `DataUpdates`, которую увидит пользователь/разработчик
    в истории обновлений, окажется помечена категорией `reports`
    (относящейся к соседнему, уже успешно завершившемуся шагу), при этом
    `errorDataKey == DataKey.syncDevices` — корректный ключ, установленный
    безусловно на шаге 3 независимо от `dataCategory`. Результат:
    полу-верный диагностический след — по ключу можно понять, что упал
    именно шаг устройств, но категория указывает на другой раздел.
12б. `emit(DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey:
    _currentDataKey, errorMessage: ..., isAdressesUpdate: false))`.
    Пользователь в этой ветке **видит** явный отказ прохода — в отличие от
    ветки (а), это единственный путь этого сценария, дающий понять, что
    что-то не удалось (хоть и без прямого указания, что именно устройства, и
    с неверно помеченной категорией в `DataUpdates`).

### Альтернативные потоки

- **Пустой батч — сценарий (а)/(б) не наступает, метод завершается успехом
  без единого сетевого вызова.** Если после `ensureDeviceInDatabase()`
  (шаг 4) таблица `Devices` не содержит ни одной строки с типом из
  `ScannerDeviceTypes.defaults` (структурно маловероятно — `ensureDeviceInDatabase()`
  как раз только что гарантировал 13 строк, — но не исключено, если само
  сидирование частично отказало без исключения), `toSend.isEmpty` истинно,
  `syncDevicesOnSHTP()` возвращает `true` немедленно, `rpcClient` не
  создаётся, никакого сетевого вызова не происходит вовсе. Не является
  ошибкой ни в каком смысле — упомянуто только как третий, отличный от (а) и
  (б) путь через тот же метод.
- **Условие срабатывания push — «только если сервер ещё пуст», не «есть
  несинхронизированные локальные изменения».** В отличие от
  `updateDevicesOnSHTP()` ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md),
  фильтрует по `isNeedUpdate == true && remoteId != null` и вызывается
  безусловно каждый проход), `syncDevicesOnSHTP()` вообще не смотрит на
  `isNeedUpdate` — единственное условие вызова этого метода снаружи
  (`_suncDevices()`, шаг 5) — пустой результат **первого** pull. Если у
  сервера уже есть хотя бы одна строка устройств для этого
  пользователя/установки (независимо от того, все ли 13 типов туда попали),
  этот push вообще не вызывается ни на одном последующем проходе — типы,
  отсутствующие на сервере по любой причине (в том числе из-за этого самого
  сценария на более раннем проходе, если тогда сервер всё же принял часть
  батча частично — сам эндпоинт не документирован этим use-case на предмет
  частичного успеха), никогда не будут отправлены повторно этим механизмом.
- **`updateDevicesOnSHTP()` имеет идентичную структуру и тот же
  игнорируемый `bool`**, но это отдельное событие
  ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)),
  вне границ этого файла — упомянуто здесь только для полноты картины
  `_suncDevices()`.
- **Даже при настоящем сетевом успехе push'а, `remoteId` проставляется не
  этим методом, а только следующим pull'ом** (шаг 9,
  [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md)) —
  если этот второй pull сам отказывает (перехватывает свою ошибку и
  возвращает пустой список, тот же механизм, что описан для первого pull),
  `remoteId` не будет проставлен даже после технически успешного push'а —
  это отдельный, самостоятельный сценарий `READ_ERROR` для
  [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
  не специфицируемый этим файлом.
- **`REJECTED`-ветки не существует**, как и в аналогичных сценариях `ANIMAL`
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)) — код не
  проверяет `response`/`response['status']` вообще ни одним условием внутри
  `syncDevicesOnSHTP()`, поэтому у него нет и не может быть пути, различающего
  «сервер осознанно отклонил батч» от «сеть недоступна»: любой ответ, дошедший
  до `return true;` без исключения, трактуется как безусловный успех,
  независимо от содержимого тела ответа.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — сущность,
  которую этот сценарий не изменяет физически ни в одной из веток: ветка (а)
  не пишет и не читает ничего в таблице `Devices` после начального
  `dao.getAll()` (шаг 5); ветка (б) не доходит даже до этого чтения (либо
  само это чтение и есть источник исключения). В обеих ветках ни `remoteId`,
  ни `isNeedUpdate` ни одной строки не меняются этим use-case — единственный
  способ, которым `remoteId` в принципе мог бы измениться, лежит в
  [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md),
  не в этом событии.
- `DataUpdates` (лог sync-прохода, специфицируется будущим модулем `SYSTEM`) —
  не получает ни одной строки в ветке (а); получает одну строку в ветке (б),
  но с `dataCategoryId == DataCategory.reports` — категорией соседнего,
  уже успешно завершившегося шага, не какой-либо категорией устройств
  (`DataCategory` не содержит такого значения вовсе).

### Бизнес-правила

- Push — единый batch-запрос на все «синкуемые» устройства сразу, не по
  одной записи и не по типу — отказ (в любой из двух веток) относится ко
  всему батчу одновременно, партиального успеха на уровне отдельного
  устройства в этой архитектуре запроса не описано.
- **Ветка (а) — единственный найденный в `MOD-6` путь, где технический сбой
  сети полностью проглатывается на уровне репозитория, а не только на
  уровне вызывающего кода.** В отличие от [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)
  (`ANIMAL`, где исключение не перехватывается вообще нигде до внешнего
  `catch`), здесь метод сам ловит исключение и возвращает `false` —
  дополнительный, специфичный для этого метода уровень проглатывания поверх
  того, что вызывающий код (`_suncDevices()`) всё равно не читает
  результат — двойная защита от видимости отказа, а не одна.
- **Ветка (б) — единственный путь, дающий пользователю понять, что
  что-то отказало**, но диагностический след внутри `DataUpdates` для неё
  структурно неверен: категория (`reports`) не совпадает с реальным
  источником отказа (устройства), потому что `DataCategory` не предусматривает
  отдельного значения для этого шага прохода.
- Никакого отдельного retry/backoff-механизма нет; «повтор на следующем
  проходе» для ветки (а) — не оформленная явно бизнес-логика, а побочный
  эффект того, что условие срабатывания push'а (`remoteDevices.isEmpty`
  после первого pull) снова окажется истинным, если сервер так и не получил
  ни одной записи. Для ветки (б) повтор произойдёт тоже, т.к. push всё равно
  не состоялся — но пользователь хотя бы увидит `DataUpdateFailure`, пусть и
  с неверно помеченной категорией.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе ветки (сетевое исключение,
перехватываемое внутри `syncDevicesOnSHTP()` и не проверяемое вызывающим
кодом; исключение до входа в защищённую зону метода, всплывающее до внешнего
`catch` с последующей неверной категоризацией в `DataUpdates`)
воспроизводятся статическим чтением кода целиком: `DataUpdateBloc._suncDevices`
→ `DeviceSettingsRepository.syncDevicesOnSHTP` → `CustomDioClient.call`/`DioClient`
(ветка а); `DeviceSettingsRepository.syncDevicesOnSHTP` (сборка батча, до
`try`) → `DataUpdateBloc.on<DataUpdateStartAll>` (ветка б). Исправление
(например, проверка/логирование результата `syncDevicesOnSHTP()` в
`_suncDevices()`, добавление отдельного значения `DataCategory` для
устройств) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный внешний `try/catch` всего прохода; гейтует весь шаг устройств условием `_authRepository.isAuthorized()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncSHTP()`, затем `_suncDevices()`, оба без собственного `try/catch` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP`, `.loadShtp` | CURRENT | предыдущий шаг прохода; `loadShtp` — последнее место, где `_currentDataCategory` явно устанавливается (`DataCategory.reports`) перед шагом устройств |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` → pull №1 → (если пуст) `syncDevicesOnSHTP()` → pull №2 → (если непуст) `clearAndInsertAll` → `ensureDeviceInDatabase()` → `applySavedTerminalSettings()`; вызов `syncDevicesOnSHTP()` не сохраняет и не проверяет возвращаемый `bool` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | вызов для `DataKey.syncDevices` не передаёт `dataCategory` — `_currentDataCategory` остаётся тем, что было установлено предыдущим шагом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `._addDataUpdateError` | CURRENT | пишут строку в `DataUpdates` (`dataCategoryId == _currentDataCategory`) и эмитят `DataUpdateFailure` — достигаются только в ветке (б) |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.syncDevicesOnSHTP` | CURRENT | предмет основного потока — сборка батча вне `try` (ветка б), сетевой вызов и его перехват внутри `try/catch` (ветка а), `bool`-результат в обоих случаях |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.ensureDeviceInDatabase`, `._isSyncableDevice`, `.fetchDevicesFromApi` | CURRENT | сидирование каталога перед push (шаг 4); фильтр батча; последующий pull, определяющий, проставится ли `remoteId` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` — источник исключения ветки (а) |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` (интерфейс) | CURRENT | абстракция, за которой скрывается `CustomDioClient` |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый путь `POST ${Constants.farmServiceApi}/devices/store` |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `ScannerDeviceTypes.defaults`, `DeviceDto`, `DeviceCredentialsDto` | CURRENT | каталог «синкуемых» типов; DTO батча — конструирование и `.toJson()` не защищены `try/catch` метода |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll` | CURRENT | `dao.getAll()` (шаг 5) — единственный явно вероятный, хоть и структурно маловероятный, источник исключения ветки (б) |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey.syncDevices` | CURRENT | `DataCategory` не содержит значения для устройств вовсе — ветка (б) неизбежно помечает строку `DataUpdates` чужой категорией |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository` (через `BaseRepository.insert`) | CURRENT | физическая запись строки `DataUpdates` в ветке (б) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | гейт, без которого `_suncDevices()` не вызывается вовсе (гость) |
| `lib/services/scanner_service.dart` | `ScannerService.applySavedTerminalSettings` | CURRENT | вызывается безусловно в конце `_suncDevices()`, независимо от исхода push/pull |

## Критерии приёмки

- Если предшествующий pull ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
  вернул пустой список и внутри `syncDevicesOnSHTP()` вызов `rpcClient.call`
  бросает исключение любого типа, оно перехватывается **тем же методом**,
  логируется через `Talker.handle`, метод возвращает `false`.
- `DataUpdateBloc._suncDevices()` не проверяет и не сохраняет этот `bool` —
  выполнение продолжается идентично успешному исходу: второй pull
  вызывается безусловно, `ensureDeviceInDatabase()` и
  `ScannerService.applySavedTerminalSettings()` выполняются, `_syncAuthData`
  и весь `on<DataUpdateStartAll>` завершаются без исключения. Ни одна строка
  `Devices` не получает `remoteId`; `DataUpdates` не получает ни одной новой
  строки, относящейся к этому отказу; sync-проход завершается
  `DataUpdateSuccess`, если остальные независимые шаги не отказали по другой
  причине.
- Если вместо этого исключение возникает до входа в защищённую `try`-зону
  `syncDevicesOnSHTP()` (например, при `dao.getAll()`), оно всплывает
  необработанным через `_suncDevices()`/`_syncAuthData()` до единственного
  внешнего `catch` (`on<DataUpdateStartAll>`), который пишет строку в
  `DataUpdates` с `dataCategoryId == DataCategory.reports` (не какой-либо
  категорией устройств — таковой не существует) и `errorDataKey ==
  DataKey.syncDevices`, и эмитит `DataUpdateFailure`.
- Условие срабатывания push'а (`remoteDevices.isEmpty` после первого pull в
  рамках `_suncDevices()`) при следующем полном sync-проходе снова окажется
  истинным, если сервер так и не получил ни одной записи устройств —
  попытка push'а повторяется на каждом последующем проходе без ограничения
  числа попыток и без какого-либо предупреждения пользователю.

## Связанные тесты

`find test -iname "*device*" -o -iname "*scanner*"` не находит ни одного
файла. `grep -rn "syncDevicesOnSHTP\|updateDevicesOnSHTP\|fetchDevicesFromApi"
test/` — пусто. `DeviceSettingsRepository` упоминается только в
`test/blocs/data_update_bloc_test.dart` (как `MockDeviceSettingsRepository`,
зарегистрированный в `getIt` без единого заданного поведения ни на один из
его методов) и в `test/pages/scanning_bloc_test.dart` (тоже только как
мок-зависимость, не связанная с этим сценарием). Оба существующих теста
`test/blocs/data_update_bloc_test.dart` (`'DataUpdateBloc конструируется с
полным набором зависимостей из getIt'` и `'DataUpdateClear очищает
пользовательские данные БД'`) не диспатчат `DataUpdateStartAll` и не
вызывают `_suncDevices()`/`syncDevicesOnSHTP()` ни разу.

**TBD — теста нет.** Ни на ветку (а) (сетевое исключение, перехватываемое
внутри `syncDevicesOnSHTP()`, отброшенный `bool` в `_suncDevices()`), ни на
ветку (б) (исключение до входа в `try`, неверная категория в `DataUpdates`),
ни на условие срабатывания push'а (`remoteDevices.isEmpty` после первого
pull), ни на гейт по авторизации — не существует ни одного unit- или
интеграционного теста.

## Открытые вопросы и ограничения

- **Двойное проглатывание отказа — на уровне метода репозитория и на уровне
  вызывающего кода — осознанное решение или недосмотр?** Ничем в
  коде/комментариях не зафиксировано. В отличие от большинства других
  push-сценариев `ANIMAL` (где непроверка ответа — единственный уровень
  проблемы), здесь `syncDevicesOnSHTP()` дополнительно перехватывает
  исключение сама, так что даже если бы `_suncDevices()` начала проверять
  `bool`, единственное, что она могла бы обнаружить — уже постфактум
  залогированный (через `Talker`, не через `DataUpdates`) факт отказа, без
  доступа к самому исключению/стектрейсу на этом уровне.
- **Асимметрия защиты внутри одного метода: сборка батча не защищена,
  сетевой вызов — защищён.** Не зафиксировано, было ли решение обернуть
  `try/catch` именно вокруг сетевого вызова (а не вокруг всего метода)
  осознанным (например, ожидание, что `dao.getAll()` не может отказать на
  практике) или просто следствием того, что `try` был добавлён позже, вокруг
  уже написанного кода.
- **`DataCategory` не имеет значения для устройств** — единственная ветка
  этого сценария, дающая пользователю видимый сигнал об отказе (ветка б),
  всё равно записывает его под чужой, случайно оставшейся от предыдущего
  шага категорией (`reports`). Не зафиксировано, планировалось ли когда-либо
  добавить отдельное значение категории для `MOD-6`/устройств.
- **Условие «push только пока сервер пуст» не различает «сервер никогда не
  получал батч» от «сервер получил, но принял не всё» частично.** Если
  единственный существующий push-эндпоинт (`POST /devices/store`) когда-либо
  возвращает частичный успех (принял часть из 13 устройств, отклонил
  остальные) без исключения, `syncDevicesOnSHTP()` всё равно вернёт `true`
  (никакого условия на этот счёт в коде нет), а следующий pull, если он
  вернёт непустой список (хотя бы с частью устройств), навсегда закроет
  условие повторного push'а для оставшихся — этот аспект не проверен ни
  одним тестом и не задокументирован со стороны реального ответа сервера.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DeviceSettingsRepository.syncDevicesOnSHTP`
  → `CustomDioClient.call` → `DioClient`; `BaseDao.getAll` как источник
  ветки б) без запущенного теста, подтверждающего любую из двух веток (см.
  «Связанные тесты» — TBD).
