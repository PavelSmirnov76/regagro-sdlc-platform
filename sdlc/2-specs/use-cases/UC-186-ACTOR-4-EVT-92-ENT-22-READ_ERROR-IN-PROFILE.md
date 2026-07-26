# UC-186 — Pull настроек сканера отказывает: сбой первого вызова в проходе неотличим от «сервер ещё пуст» и ошибочно запускает первичный push, сбой второго — навсегда откладывает получение `remoteId`

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) |
| Сущность | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же pull-шаг, что описан в [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) —
`DeviceSettingsRepository.fetchDevicesFromApi()`, вызываемый внутри
`DataUpdateBloc._suncDevices()` **дважды за один проход**: первый раз сразу
после [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md)
(правки), второй — сразу после [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)
(первичное создание), но только если первый вызов вернул пустой список. Тот
же паттерн, что уже задокументирован для проверки доступности BOARD
([UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)) —
`fetchDevicesFromApi()` оборачивает **весь** `GET ${Constants.farmServiceApi}/devices`
плюс весь последующий разбор ответа в один `try`, перехватывает **любое**
исключение и безусловно возвращает пустой список. В отличие от BOARD, здесь
отказ **не полностью тихий** — `catch (e, stackTrace) {
getIt<Talker>().handle(e, stackTrace); return []; }` действительно пишет в
`Talker` (просто не в `DataUpdates`, не в `SnackBar`, не в любой другой
видимый пользователю канал).

Практическое следствие — этот технический сбой не проваливает sync-проход
целиком (в отличие от [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
ветка (б), где похожий по духу сбой соседнего метода **проваливает** проход),
но неотличим от легитимного «у сервера действительно нет записей устройств
для этого пользователя/установки» — `clearAndInsertAll` не вызывается
(список пуст в обоих случаях), локальные данные остаются как есть (не
теряются), но и не обновляются. Ниже проверены отдельно, чтением кода, два
структурно разных исхода одного и того же отказа метода — какой из двух
вызовов этого события за проход отказал:

- **(а) отказывает первый вызов** — пустой результат из-за сбоя сети/разбора
  ответа неотличим от «сервер ещё не видел устройств этого
  пользователя/установки», что ошибочно запускает попытку
  [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)
  (первичный batch-push) там, где сервер на самом деле мог быть просто
  временно недоступен, а не пуст.
- **(б) отказывает второй вызов** (достижим только если первый вызов уже был
  пуст, легитимно или из-за (а)) — `clearAndInsertAll` не вызывается вовсе
  за весь проход, и это единственный механизм, которым `remoteId` в принципе
  попадает в локальные строки ([ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md),
  «Инварианты») — эффект переживает этот один проход: локальные правки
  устройства без `remoteId` не смогут быть отправлены и на следующем
  проходе тоже (`updateDevicesOnSHTP()` фильтрует по `remoteId != null`).

Дополнительно проверена и задокументирована отдельным под-пунктом третья,
структурно возможная, но на сегодня практически недостижимая ветка —
исключение при резолве `ApiClient` **до** входа в `try` этого конкретного
метода (в отличие от `syncDevicesOnSHTP()`, где тот же резолв защищён своим
`try`).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет — проход был запущен ранее авторизованным пользователем одним из
нескольких способов (как и в [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)):

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
вызова. Достижимо только для **авторизованного** пользователя —
`_suncDevices()` вызывается исключительно из `_syncAuthData()`, вызываемой
только при `_authRepository.isAuthorized() == true`; для гостя этот шаг (и
весь этот use-case) недостижим ни при каких условиях — тот же факт, что уже
установлен в [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md).

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети (`NetworkConnectivityService.hasConnection()`, иначе
   `DataUpdateFailure` сразу, до входа сюда), `loadDirectories()` и
   остальных независимых шагов, при `_authRepository.isAuthorized()`
   вызывается `await _syncAuthData(event, emit)` — без собственного
   `try/catch` вокруг этого вызова.
2. `_syncAuthData` доходит до `updateAndSyncSHTP(event, emit)`, затем
   `_emitProgress(emit: emit, dataKey: DataKey.syncDevices)` (без
   `dataCategory` — `_currentDataCategory` остаётся тем, что установил
   предыдущий шаг, не относящимся к устройствам; см.
   [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md) за
   разбором этого факта — здесь он не имеет значения, поскольку в этом
   сценарии исключение никогда не покидает `_suncDevices()`, см. ниже), и
   `await _suncDevices()`.
3. Внутри `_suncDevices()`: `await
   _deviceSettingsRepository.ensureDeviceInDatabase()` (безусловный
   идемпотентный upsert 14 дефолтных типов — количество пересчитано
   независимо по литералу `ScannerDeviceTypes.defaults`, расхождение с
   текстом [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) уже отмечено в
   [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)), затем
   `await _deviceSettingsRepository.updateDevicesOnSHTP()` ([EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md),
   не в границах этого файла), затем `var remoteDevices = await
   _deviceSettingsRepository.fetchDevicesFromApi();` — **первый** вызов
   этого события за проход, предмет ветки (а).
4. Внутри `fetchDevicesFromApi()`
   (`lib/repositories/devices_settings/devices_settings_repository.dart`):
   `const link = '${Constants.farmServiceApi}/devices'; const message =
   ApiMessage(link: link, method: ApiMethod.get); final rpcClient =
   getIt.get<ApiClient>(instanceName: 'farm_rpc');` — **эти три строки лежат
   вне какого-либо `try/catch` этого метода** (контраст с
   `syncDevicesOnSHTP()`, где резолв того же `ApiClient` находится внутри
   собственного `try` — см. «Альтернативные потоки» для отдельно проверенной
   ветки на этот счёт). Только отсюда начинается защищённая зона:
   ```dart
   try {
     final response = await rpcClient.call(message);
     final data = response['data']['devices'] as List;
     return data
         .map((json) => DeviceDto.fromJson(json))
         .where((device) => ScannerDeviceTypes.defaults.contains(device.type))
         .map((device) => device.toCompanion())
         .toList();
   } catch (e, stackTrace) {
     getIt<Talker>().handle(e, stackTrace);
     return [];
   }
   ```
   Этот `try` шире, чем у `syncDevicesOnSHTP()`/`updateDevicesOnSHTP()` —
   защищает не только сам сетевой вызов, но и весь разбор ответа (`as List`,
   `DeviceDto.fromJson`, фильтрацию, `.toCompanion()`, финальный `.toList()`
   — форсирующий немедленное вычисление всей цепочки `Iterable` целиком).
5. В этом сценарии одна из операций внутри `try` бросает исключение —
   проверены отдельно три независимых источника, любой из них ведёт к
   одному и тому же исходу шага 6:
   - `rpcClient.call(message)` (`CustomDioClient.call`,
     `lib/network/api_client/custom_dio_client.dart`) бросает
     `DioException` — сеть недоступна, таймаут, обрыв соединения, либо
     любой не-2xx HTTP-ответ (`DioClient`,
     `lib/network/dio_client.dart`, не переопределяет `validateStatus` —
     Dio по умолчанию бросает исключение вне 200–299). `CustomDioClient.call`
     сам логирует (`getIt.get<Talker>().error('CustomDioClient: call:
     $e')`) и безусловно перебрасывает (`rethrow`) — эта конкретная
     причина отказа оказывается залогирована в `Talker` **дважды**: один
     раз изнутри клиента, второй раз — перехватом `fetchDevicesFromApi()`
     самим (шаг 6);
   - вызов завершается без исключения, но `response['data']` не содержит
     ключа `devices` (или сам `response['data']` — не `Map`) — `as List`
     бросает `TypeError`, минуя `CustomDioClient` полностью (та часть уже
     отработала успешно);
   - `DeviceDto.fromJson(json)` бросает для **любого одного** элемента
     массива (`DateTime.parse(json['created_at'])`/`json['updated_at']` на
     некорректной строке, либо отсутствующий обязательный ключ) — поскольку
     `.toList()` форсирует всю цепочку `.map/.where/.map` целиком, один
     некорректный элемент где угодно в ответе обрывает разбор **всего**
     списка — теряются и все остальные, корректные строки того же ответа,
     не только сбойная.
6. `catch (e, stackTrace) { getIt<Talker>().handle(e, stackTrace); return
   []; }` — перехватывает любую из трёх причин единообразно, логирует через
   `Talker.handle` (видно только в собственном лог-вьюере `Talker`
   приложения/консоли отладки, не в `DataUpdates`, не в `SnackBar`, не в
   каком-либо ином видимом пользователю канале) и возвращает пустой список —
   **то же самое значение, которое метод вернул бы, если бы сервер
   содержательно ответил «у этого пользователя/установки нет ни одной
   записи устройств»**.

**Ветка (а) — отказывает первый вызов (шаг 3).**

7а. `remoteDevices` (шаг 3) равен `[]` — по любой из трёх причин шага 5, либо
    по легитимной причине («сервер действительно пуст», не входит в этот
    файл). `_suncDevices()` не может и не пытается их различить.
8а. `if (remoteDevices.isEmpty)` — истинно → `await
    _deviceSettingsRepository.syncDevicesOnSHTP();` —
    [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md)/[UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md) —
    вызывается **независимо от того, была ли причина пустоты технической
    (этот сценарий) или содержательной**. Если сервер на самом деле уже
    хранит записи устройств для этого пользователя/установки (а pull
    просто не смог их прочитать), этот шаг всё равно шлёт `POST
    /devices/store` со всеми 14 «синкуемыми» устройствами, каждое с `id: 0`
    (см. [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md),
    шаг 8) — попытка «первичного создания» там, где содержательно нужно
    было бы просто повторить чтение. Возможное следствие — повторно
    отправленный batch на сервер, уже имеющий эти записи; распознаёт ли
    сервер это как дубликат по `type`, клиентским кодом не определяется
    (тот же открытый вопрос, что и в
    [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)).
9а. `remoteDevices = await
    _deviceSettingsRepository.fetchDevicesFromApi();` — **второй** вызов
    этого же события за проход (тот же метод, предмет ветки (б)),
    вызывается безусловно сразу после `syncDevicesOnSHTP()`, независимо от
    того, что тот вернул.
10а. Если этот второй вызов технически успешен и сервер теперь
    содержательно возвращает непустой список (независимо от того, был ли
    он получен из-за только что отправленного push'а или уже существовал
    до него) — `if (remoteDevices.isNotEmpty) { await
    _deviceSettingsRepository.clearAndInsertAll(remoteDevices); }`
    выполняется, `remoteId` проставляется корректно; **вся ветка (а) в этом
    случае визуально «самозалечивается»** — пользователь и разработчик не
    видят никакого следа того, что первый pull технически отказал, кроме
    одной строки в `Talker`-логе и, возможно, лишнего batch-`POST`,
    отправленного зря.
11а. Если же второй вызов тоже отказывает — это уже ветка (б), см. ниже.

**Ветка (б) — отказывает второй вызов (шаг 9а; достижим только если первый
вызов уже был пуст — легитимно или из-за ветки (а)).**

7б. `remoteDevices = await _deviceSettingsRepository.fetchDevicesFromApi();`
    (шаг 9а) сам проходит шаги 4-6 второй раз за тот же проход и по любой из
    тех же трёх причин возвращает `[]`, логируя через `Talker.handle`
    отдельной строкой (неотличимой в самом логе от строки, которая была бы
    записана при отказе первого вызова, — сообщение `Talker.handle`
    одинаково для обоих call site'ов, никакой пометки «это первый pull» /
    «это второй pull» код не добавляет).
8б. `if (remoteDevices.isNotEmpty)` — ложно → `clearAndInsertAll` **не
    вызывается вовсе за весь этот проход**. Это единственный механизм, тем
    ли иным способом описанный в [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)
    («Инварианты»), которым `remoteId` в принципе попадает в локальные
    строки `Devices` — ни `updateDevicesOnSHTP()`, ни `syncDevicesOnSHTP()`
    не делают этого сами (см.
    [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)).
9б. `await _deviceSettingsRepository.ensureDeviceInDatabase();`
    (повторный вызов — досеивает недостающие дефолты; ничего не меняет
    здесь, т.к. ничего не удалялось) и `await
    getIt<ScannerService>().applySavedTerminalSettings();` выполняются
    безусловно, применяя к оборудованию (если оно подключено) те же
    локальные настройки, что были в таблице до всего этого прохода —
    ничего свежего с сервера так и не пришло.
10б. `_suncDevices()` возвращает управление без исключения; `_syncAuthData`,
    `on<DataUpdateStartAll>` (шаг 1) доходят до `emit(DataUpdateSuccess(...))`,
    если остальные независимые шаги прохода не отказали по другой причине.
    Пользователь видит **полностью успешное** завершение обновления
    данных — то же самое, что и при настоящем успехе.
11б. **Итог, переживающий этот один проход:** ни одна строка `Devices`
    не получает `remoteId` на этом проходе — даже если один из push'ов
    (текущий или более ранний) реально дошёл до сервера. Любая строка,
    у которой `remoteId` уже был `null` до этого прохода, останется такой
    же и после него. Практическое следствие для [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md):
    `updateDevicesOnSHTP()` отбирает только строки с `isNeedUpdate == true
    && remoteId != null` — то есть любая локальная правка настройки
    устройства (один из семи методов записи, [UC-180](UC-180-ACTOR-5-EVT-89-ENT-22-UPDATE_ERROR-IN-PROFILE.md)),
    сделанная пользователем для устройства без `remoteId`, останется
    непередаваемой через PUT-путь **до тех пор, пока pull не завершится
    успешно на каком-то из будущих проходов** — не только этот один раз.
    На следующем полном проходе первый вызов `fetchDevicesFromApi()` будет
    предпринят заново с нуля; если он снова окажется пуст (легитимно или
    технически), весь цикл ветки (а) повторится, включая ещё одну попытку
    `syncDevicesOnSHTP()`.

**Ветка (в) — исключение до входа в `try` самого `fetchDevicesFromApi()`
(проверена отдельно, структурно возможна, практически недостижима).**

12в. `getIt.get<ApiClient>(instanceName: 'farm_rpc')` (шаг 4, три строки
    вне `try`) теоретически может бросить, если экземпляр с этим именем не
    зарегистрирован в `getIt` в момент вызова — `get_it` бросает
    `StateError`/`ArgumentError` в этом случае, и это исключение не будет
    перехвачено ни здесь, ни выше по `_suncDevices()`/`_syncAuthData` (у них
    тоже нет собственного `try/catch` вокруг этого вызова), всплывёт до
    единственного внешнего `catch` `on<DataUpdateStartAll>` (шаг 1) — то же
    поведение, что уже задокументировано как ветка (б) в
    [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md) для
    соседнего метода: пользователь **увидел** бы явный
    `DataUpdateFailure`, а не тихий провал этого сценария. На практике
    недостижимо на сегодня — сильнее, чем аргумент про порядок операций в
    `main()` из [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md):
    тот же `instanceName: 'farm_rpc'` уже гарантированно резолвится и
    используется раньше в этой же цепочке вызовов — `_syncAuthData`
    вызывает `_syncFarms()` (несколько строк выше `_suncDevices()`), который
    безусловно доходит до `_loadFarmsFromRDS()` →
    `FarmRepository.getAllFarmsFromRDS()` → `getAllFarmsAndPlacesFromRDS()`
    (`lib/repositories/farm_repository/farm_repository.dart`) — та резолвит
    `getIt.get<ApiClient>(instanceName: 'farm_rpc')` одной из первых строк
    своего тела, без всякого условия. То есть к моменту, когда выполнение
    доходит до шага 4, эта же регистрация в `getIt` уже была успешно
    использована как минимум один раз секундами ранее в рамках того же
    прохода — раньше и надёжнее, чем условный резолв внутри самих
    `updateDevicesOnSHTP()`/`syncDevicesOnSHTP()` (те резолвят тот же
    `ApiClient` только при непустом `toSend`, не гарантированно на каждом
    проходе).

### Альтернативные потоки

- **Первый вызов легитимно пуст (не ошибка), второй — технически отказал.**
  Это тоже ветка (б) — код не различает «первый вызов был пуст легитимно» от
  «первый вызов был пуст из-за ветки (а)»; единственное условие входа в
  ветку (б) — `remoteDevices.isEmpty` после первого вызова, по любой
  причине, и отказ второго вызова. И «настоящий первый раз в жизни
  аккаунта» (после успешного `syncDevicesOnSHTP()` в тот же проход), и
  «повторный отказ pull'а после ошибочно запущенного в ветке (а) push'а»
  приводят к одному и тому же итогу шага 11б.
- **Резолв `getIt` для второго вызова (шаг 9а) так же вне `try`, что и для
  первого** — ветка (в) равно применима к обоим вызовам этого события за
  проход, не только к первому; не расписана здесь отдельно для второго
  вызова, чтобы не дублировать одну и ту же структуру.
- **Асимметрия защиты внутри одного метода, в противоположную сторону
  относительно `syncDevicesOnSHTP()`.** [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)
  документирует, что в `syncDevicesOnSHTP()` сборка батча (до `try`)
  беззащитна, а сетевой вызов (внутри `try`) — защищён. Здесь же резолв
  `ApiClient` (структурно аналог «подготовки к вызову») вынесен **перед**
  `try`, тогда как в `syncDevicesOnSHTP()` тот же самый резолв находится
  **внутри** `try` — то же самое действие (`getIt.get<ApiClient>(instanceName:
  'farm_rpc')`) защищено в одном методе этого же файла и не защищено в
  другом, без какого-либо задокументированного объяснения этой
  непоследовательности.
- **`REJECTED`-ветки не существует.** Как и в
  [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
  метод не проверяет содержимое ответа сервера на предмет осознанного
  бизнес-отказа — единственное различие, которое умеет делать
  `fetchDevicesFromApi()`, это «исключение где-то внутри `try`» против
  «успешный разбор», независимо от того, что именно сервер содержательно
  ответил.

### Связанные сущности

- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device) — единственная
  сущность, которую этот сценарий пытается прочитать и не может: ни в
  ветке (а), ни в ветке (б) `remoteId`/`isNeedInsert`-семантика
  (`clearAndInsertAll`) не применяется к таблице `Devices` за счёт именно
  отказавшего вызова; в ветке (а), если *второй* вызов того же прохода
  всё же успешен, таблица обновляется этим вторым вызовом, а не тем,
  который отказал.
- `DataUpdates` (лог sync-прохода, специфицируется будущим модулем `SYSTEM`) —
  **не получает ни одной строки ни в одной из веток (а)/(б)** — в отличие
  от [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)
  (ветка б, где исключение до защищённой зоны *соседнего* метода реально
  всплывает и записывается, пусть и под чужой категорией), здесь
  исключение никогда не покидает `fetchDevicesFromApi()` (кроме
  структурно возможной, но практически недостижимой ветки (в)) — этот
  сценарий строже «тих», чем любой другой уже задокументированный отказ
  этого модуля, кроме зеркального [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
  ветка (а).

### Бизнес-правила

- Одно и то же событие ([EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md))
  вызывается дважды за проход, тем же кодом, без какой-либо метки,
  различающей «это первый вызов» от «это второй» ни в самом методе, ни в
  записи `Talker`, ни где-либо ещё — единственный способ различить их
  постфактум — порядковое положение строки в логе относительно
  предшествующего вызова `syncDevicesOnSHTP()`.
- Отказ этого шага (в любой из первых двух веток) не проваливает
  sync-проход целиком — контраст с [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
  ветка (б), где похожий по духу «отказ до защищённой зоны» соседнего
  метода **проваливает** проход. Асимметрия объясняется исключительно тем,
  что здесь у `fetchDevicesFromApi()` вся содержательная логика лежит
  внутри `try`, а у `syncDevicesOnSHTP()` — частично снаружи.
- Отказ первого вызова структурно неотличим от легитимного «у сервера нет
  записей» и **ошибочно запускает** попытку первичного push'а
  ([UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md)) —
  тот же самый открытый вопрос, что уже отмечен в обоих этих файлах с их
  стороны, здесь зафиксирован окончательно со стороны самого pull'а.
- Отказ второго вызова — единственный путь, которым локальные правки уже
  существующего устройства (при `remoteId == null`) остаются
  непередаваемыми на сервер **более одного прохода подряд**, не только на
  этом одном — вплоть до первого будущего прохода, где `fetchDevicesFromApi()`
  технически отработает успешно.
- Нет ретрая внутри одного прохода сверх двух предусмотренных архитектурой
  вызовов; нет backoff между ними — второй вызов происходит немедленно
  вслед за первым (и после `syncDevicesOnSHTP()`), без какой-либо паузы.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной механизм (широкий `try` внутри
`fetchDevicesFromApi()`, перехватывающий сетевые и парсинг-исключения
одинаково, безусловный возврат `[]`, неотличимость от легитимно пустого
ответа сервера, двукратный вызов за проход с независимыми последствиями
для веток (а)/(б)) полностью воспроизводится статическим чтением кода:
`DataUpdateBloc._suncDevices` → `DeviceSettingsRepository.fetchDevicesFromApi`
→ `CustomDioClient.call`/`DioClient`/`DeviceDto.fromJson`. Ветка (в)
(резолв `ApiClient` вне `try`) прослежена так же — статическим чтением — и
признана структурно возможной, но практически недостижимой при текущем
порядке вызовов внутри `_suncDevices()` (тот же `instanceName` уже
резолвился раньше в этой же цепочке). Ни одна из трёх веток не
подтверждена запущенным тестом (см. «Связанные тесты» — TBD). Исправление
(например, различение причины пустого ответа, отдельная проверка перед
запуском `syncDevicesOnSHTP()`, сохранение «последнего известного
хорошего» списка при отказе pull'а) в рамках этого документирующего
прохода не выполняется — это фиксация уже существующего кода, а не работа
над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.fetchDevicesFromApi` | CURRENT | предмет сценария — резолв `ApiClient` вне `try` (ветка в); широкий `try/catch`, покрывающий сетевой вызов и весь разбор ответа (ветки а/б) |
| `lib/repositories/devices_settings/devices_settings_repository.dart` | `DeviceSettingsRepository.syncDevicesOnSHTP`, `.updateDevicesOnSHTP`, `.clearAndInsertAll` (через `BaseRepository`) | CURRENT | соседние шаги того же прохода — `syncDevicesOnSHTP` запускается условно из-за пустого результата этого события (ветка а); `clearAndInsertAll` — единственный писатель `remoteId`, не достигается ни в одной из веток (а)/(б) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._suncDevices` | CURRENT | оркестрация: `ensureDeviceInDatabase()` → `updateDevicesOnSHTP()` → `fetchDevicesFromApi()` (вызов №1, предмет сценария) → если пуст: `syncDevicesOnSHTP()` → `fetchDevicesFromApi()` (вызов №2, предмет сценария) → если непуст: `clearAndInsertAll()` → `ensureDeviceInDatabase()` → `ScannerService.applySavedTerminalSettings()` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData`, `.on<DataUpdateStartAll>` | CURRENT | вызывает `_suncDevices()` без собственного `try/catch`; единственный внешний перехват всего прохода — не достигается ни в одной из веток (а)/(б), теоретически достижим в ветке (в) |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsFromRDS`, `.getAllFarmsAndPlacesFromRDS` | CURRENT | вызывается безусловно раньше `_suncDevices()` внутри той же `_syncAuthData`; резолвит тот же `getIt.get<ApiClient>(instanceName: 'farm_rpc')` — довод против практической достижимости ветки (в) |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует (`Talker.error`) и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` — источник одной из трёх причин исключения (двойное логирование в `Talker` для этой причины) |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/network/api_client/api_client.dart` | `ApiClient` (интерфейс), `getIt.get<ApiClient>(instanceName: 'farm_rpc')` | CURRENT | резолв, вынесенный вне `try` этого метода (ветка в) |
| `packages/sheep_farm_database/lib/entities/devices/devices.dart` | `DeviceDto.fromJson`, `DeviceDtoMapper.toCompanion`, `ScannerDeviceTypes.defaults` | CURRENT | разбор ответа внутри `try`; `DateTime.parse` внутри `fromJson` — источник второй из трёх причин исключения; один некорректный элемент списка обрывает разбор всего ответа (`.toList()` форсирует всю цепочку) |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый путь `GET ${Constants.farmServiceApi}/devices` |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey.syncDevices` | CURRENT | не участвуют в этом сценарии — ни одна из веток (а)/(б) не доходит до `_addDataUpdateError`; упомянуто только для контраста с [UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md) |
| `lib/services/scanner_service.dart` | `ScannerService.applySavedTerminalSettings` | CURRENT | вызывается безусловно в конце `_suncDevices()`, применяя те же (не обновившиеся) локальные настройки, если обе ветки (а)/(б) отказали |

## Критерии приёмки

- Если `rpcClient.call`, разбор JSON (`response['data']['devices'] as
  List`) или `DeviceDto.fromJson` любого элемента ответа бросает исключение
  внутри `fetchDevicesFromApi()`, метод логирует его через `Talker.handle`
  и возвращает `<DevicesCompanion>[]`, независимо от того, сколько
  элементов ответа было корректными.
- Если это первый вызов события за проход и результат пуст (по любой
  причине), `_suncDevices()` безусловно вызывает `syncDevicesOnSHTP()` —
  код не различает «сервер пуст» от «pull технически отказал».
- Если второй вызов события за тот же проход тоже возвращает пустой список
  (по любой причине), `clearAndInsertAll` не вызывается вовсе за весь этот
  проход — ни одна строка `Devices` не получает `remoteId`/`isNeedUpdate ==
  false` этим проходом, независимо от исхода предшествующего
  `syncDevicesOnSHTP()`.
- Ни в одной из этих двух веток исключение не покидает `_suncDevices()` —
  `on<DataUpdateStartAll>` доходит до `DataUpdateSuccess`, если остальные
  независимые шаги прохода не отказали по другой причине; `DataUpdates` не
  получает ни одной новой строки об этом отказе.
- Резолв `getIt.get<ApiClient>(instanceName: 'farm_rpc')` внутри
  `fetchDevicesFromApi()` физически расположен вне `try` этого метода — при
  текущем порядке вызовов внутри `_suncDevices()` (та же регистрация уже
  использована раньше в этой же цепочке) это структурно не проявляется на
  практике ни в одном известном пути выполнения.
- Локальная правка устройства с `remoteId == null`, сделанная пользователем
  между двумя проходами, оба из которых заканчиваются веткой (б), не будет
  отправлена через `updateDevicesOnSHTP()` ни на одном из этих проходов —
  только на первом будущем проходе, где `fetchDevicesFromApi()` технически
  отработает успешно.

## Связанные тесты

`grep -rn "fetchDevicesFromApi" test/` — пусто. `grep -rl
"DeviceSettingsRepository" test/` находит два файла —
`test/blocs/data_update_bloc_test.dart` и `test/pages/scanning_bloc_test.dart` —
в обоих `DeviceSettingsRepository` присутствует исключительно как
`MockDeviceSettingsRepository`, зарегистрированная в `getIt` как
зависимость конструктора соответствующего блока/кубита
(`DataUpdateBloc`/`ScanningBloc`), ни разу не относящаяся к `_suncDevices()`
или `fetchDevicesFromApi` конкретно:

- `test/blocs/data_update_bloc_test.dart` не стабит на этом моке ни один
  метод вообще (регистрация — `getIt.registerLazySingleton<DeviceSettingsRepository>(()
  => MockDeviceSettingsRepository())`, без единого `when(...)`); единственные
  два теста файла — `'DataUpdateBloc конструируется с полным набором
  зависимостей из getIt'` и `'DataUpdateClear очищает пользовательские
  данные БД'` — ни один не диспатчит `DataUpdateStartAll` и не вызывает
  `_suncDevices()`.
- `test/pages/scanning_bloc_test.dart` стабит на этом же моке только
  `ensureDeviceInDatabase`, `getDefaultDevices`, `getSavedAntennas`,
  `getSavedAddress`, `updateAntennasInStorage`, `updateAddressInStorage` —
  никогда `fetchDevicesFromApi` — и относится к отдельной фиче (`INV`,
  сканирование при инвентаризации), не к sync-проходу устройств.

Отдельного файла `test/repositories/devices_settings_repository_test.dart`
не существует (`find test -iname "*devices_settings*"` — пусто).

**TBD — теста нет.** Ни на ветку (а) (первый вызов отказывает, ошибочно
запускается `syncDevicesOnSHTP()`), ни на ветку (б) (второй вызов
отказывает, `clearAndInsertAll` не достигается весь проход, `remoteId`
остаётся непроставленным более одного прохода), ни на ветку (в) (резолв
`ApiClient` вне `try`), ни на неразличимость двух вызовов одного события в
логе `Talker` — не существует ни одного unit- или интеграционного теста.

## Открытые вопросы и ограничения

- **То же самое основание, что уже открыто в
  [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
  зафиксировано здесь с противоположной, «читающей» стороны:** является ли
  неразличимость «сервер пуст» / «pull технически отказал» осознанным
  допущением (например, ожидание, что `GET /devices` почти никогда не
  отказывает на практике) или недосмотром — ничем в коде/комментариях не
  зафиксировано.
- **Один некорректный элемент ответа губит весь список.** Поскольку
  `.map/.where/.map(...).toList()` вычисляется целиком, единственная
  сломанная запись где угодно в ответе `GET /devices` (например, сервер
  вернул `created_at` в нестандартном формате для одного устройства)
  отбрасывает **все** остальные, корректные записи того же ответа — не
  проверено против реального формата ответа бэкенда, вывод сделан
  статическим чтением `DeviceDto.fromJson`.
- **Асимметрия расположения `try` относительно резолва `ApiClient` между
  `fetchDevicesFromApi()` и `syncDevicesOnSHTP()`** (см. «Альтернативные
  потоки») ничем не объяснена — не зафиксировано, было ли осознанным
  решением защитить резолв в одном методе и не защищать в другом.
- **Отсутствие маркера, различающего первый и второй вызов одного события
  за проход, в самом логе `Talker`.** Постфактум, по логам пользователя,
  невозможно достоверно определить, какая из двух веток (а)/(б) произошла
  — только по относительному порядку строк, если рядом видна (или не
  видна) соответствующая строка `syncDevicesOnSHTP()`.
- **Дедупликация на сервере при повторном push'е, ошибочно запущенном
  веткой (а), не верифицируема из этого кода** — тот же открытый вопрос,
  что и в [UC-181](UC-181-ACTOR-4-EVT-90-ENT-22-CREATE_OK-IN-PROFILE.md)/[UC-182](UC-182-ACTOR-4-EVT-90-ENT-22-CREATE_ERROR-IN-PROFILE.md),
  подтвердить или опровергнуть можно только против реального бэкенда.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`DeviceSettingsRepository.fetchDevicesFromApi` → `CustomDioClient.call` →
  `DioClient`/`DeviceDto.fromJson`), без запущенного теста, подтверждающего
  любую из трёх веток (см. «Связанные тесты» — TBD).
