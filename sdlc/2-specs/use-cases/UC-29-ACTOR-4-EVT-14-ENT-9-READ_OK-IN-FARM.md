# UC-29 — Система перезагружает список ферм с сервера при полном sync-проходе

## Назначение

В рамках явного полного sync-прохода (запущен пользователем один раз, дальше
идёт автоматически) система забирает с сервера актуальный список ферм и
приводит локальную таблицу ферм в соответствие с полученным ответом — так
локально видны фермы, изменённые, например, с другого устройства или другим
пользователем той же СХТП.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода (`DataUpdateBloc`), без участия пользователя в момент именно
этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, и `_authRepository.isAuthorized()` истинно — иначе `_syncAuthData`
   не вызывается вовсе (вне границ этого файла, см. [MOD-3](../modules/MOD-3-FARM.md), «Граница»).
2. `_syncAuthData` вызывает `DataUpdateBloc._syncFarms`, которая выполняет
   push-шаги (`_storeFarmsToRDS`, `_updateFarmsOnRDS`) и только затем —
   `_loadFarmsFromRDS`, предмет этого use-case.
3. `_loadFarmsFromRDS` вызывает `FarmRepository.getAllFarmsFromRDS()`, которая
   делегирует в `getAllFarmsAndPlacesFromRDS()`: `GET
   ${Constants.registrationServiceApi}/farms` с query-параметром
   `with_places: 1`, через `ApiClient` с `instanceName: 'farm_rpc'`.
4. Если `response['status']` равен `"1"` или `1` — сервер вернул массив
   `data`; каждый элемент мапится через `FarmExtension.fromJsonRDS` в
   `FarmsCompanion` (`remoteId`, `name`, `address`, `latitude`, `longitude`,
   `createdAt`, `updatedAt`, `guid` — без адресных id-полей и без
   `needUpdate`/`isDeleted`, см. «Бизнес-правила»). `getAllFarmsFromRDS`
   возвращает только ключ `'farms'` этого результата — вложенные `places`
   этого же ответа читаются отдельно, другим методом ([EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md)), не этим.
5. Обратно в `_loadFarmsFromRDS`: если полученный список ферм непустой —
   `_farmRepository.clear()` (удаляет вообще все строки таблицы `Farms`),
   затем `_farmRepository.insertAll(res)` (батчевая вставка новых строк с
   заново присвоенными автоинкрементными локальными `id`, режим
   `insertOrReplace`).
6. Если на экране в этот момент открыт список ферм —
   `FarmsAndPlacesBloc` подписан на `_farmsRepository.watchAll()`
   (Drift-стрим), поэтому перезапись отражается в UI немедленно, без
   какого-либо дополнительного триггера.
7. Sync-проход продолжается (`_syncPlaces`, `_animalWeighingsRepository...`,
   и т.д.) независимо от исхода этого шага — не предмет этого файла.

### Альтернативные потоки

- **Пустой или отклонённый сервером ответ.** Если сервер вернул пустой
  массив, либо `response['status']` не равен `"1"`/`1` — `getAllFarmsAndPlacesFromRDS`
  в обоих случаях возвращает `{'farms': [], 'places': []}` без какого-либо
  различения причины (лог `'No data or error status'` — общий на обе
  ветки). `_loadFarmsFromRDS` видит пустой список и **возвращается сразу**:
  ни `clear()`, ни `insertAll()` не вызываются, локальные данные остаются
  ровно такими, какими были до этого шага. Тот же `RESULT` (`READ_OK` — вызов
  успешно завершился, просто без данных для замены), не отдельный
  use-case.
- **Сетевое исключение во время запроса.** Если сам вызов `rpcClientSHTP.call(message)`
  бросает исключение — оно не перехватывается ни внутри
  `getAllFarmsAndPlacesFromRDS`, ни внутри `_loadFarmsFromRDS`/`_syncFarms`/
  `_syncAuthData`, и всплывает во внешний `try/catch` в
  `on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure` и завершает
  **весь** sync-проход ошибкой (не только farm-часть). Другой результат
  (`READ_ERROR`), не описывается этим файлом.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — единственная сущность, которую физически
  переписывает этот шаг; целиком, без построчного diff/merge — при
  непустом ответе локальный `id` каждой фермы меняется на новый
  (автоинкремент), потому что это `delete`+`insert`, а не `update`
  существующих строк.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — не читается и не пишется этим шагом, но
  связь `Places.farmId → Farm.remoteId` (не `Farm.id`) переживает эту
  перезапись без разрыва, так как `remoteId` в ответе сервера стабилен
  между проходами, а именно на него, а не на волатильный локальный `id`,
  ссылается `Place`.

### Бизнес-правила

- Перезагрузка — безусловная замена «всё или ничего» **только когда есть
  чем заменять**: непустой ответ полностью вытесняет локальное состояние
  без сравнения по записям; пустой/отклонённый ответ не трогает локальное
  состояние вовсе — нет промежуточного варианта («частично обновить»).
- `clear()` и `insertAll()` — два отдельных `await`-вызова, не единая
  транзакция, хотя `BaseDao.clearAndInsertAll` (оборачивающий оба шага в
  `transaction()`) для этой же цели уже существует и используется, например,
  в `AnimalWeighingsDao.clearSync`. Если процесс будет прерван между этими
  двумя вызовами (например, крашем приложения), локальная таблица ферм
  останется полностью пустой до следующего успешного sync-прохода.
- `FarmExtension.fromJsonRDS` не заполняет адресные id-поля
  (`countryId`/`regionId`/`districtId`/`localityId`/`streetId`/`house`/
  `building`/`apartment`) — в `FarmsCompanion` эти значения остаются
  `Value.absent()`. Поскольку `_loadFarmsFromRDS` вставляет строки заново
  (не обновляет существующие), а эти колонки в `Farms` — nullable без
  `withDefault`, при вставке они получают `null`. Любые значения, ранее
  сохранённые локально по этим полям (например, через
  `FarmExtension.fromJsonRDSwithLocalId`, используемый в другом
  сценарии, или введённые при локальном создании фермы), безусловно
  стираются в `null` при каждой успешной непустой перезагрузке.
- Порядок внутри `_syncFarms` — сначала push (`_storeFarmsToRDS`,
  `_updateFarmsOnRDS`), затем этот pull-шаг. Если `_updateFarmsOnRDS`
  получает `isUpdated == false` от `FarmRepository.updateFarmsOnRDS` (весь
  батч не отправился), локальный `needUpdate` для этих ферм остаётся
  `true` — но следующий же шаг, этот, безусловно перезаписывает те же
  фермы серверной (неотредактированной) версией, и поскольку
  `fromJsonRDS` не переносит `needUpdate` в `FarmsCompanion`, вставка
  использует дефолт колонки (`false`). Результат — локальная правка,
  которая не была подтверждена сервером, молча теряется и помечается как
  «синхронизировано», без всплывающей ошибки пользователю.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | гейтит вызов за `isAuthorized()`, задаёт порядок относительно синхронизации остальных сущностей |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms` | CURRENT | последовательность push (`_storeFarmsToRDS`, `_updateFarmsOnRDS`) → pull (`_loadFarmsFromRDS`) для ферм |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadFarmsFromRDS` | CURRENT | ядро этого сценария: запрос + условные `clear()`/`insertAll()` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsFromRDS` | CURRENT | тонкая обёртка, читающая ключ `'farms'` общего ответа |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsAndPlacesFromRDS` | CURRENT | сам HTTP GET `.../farms?with_places=1`, проверка `status`, маппинг JSON |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `FarmExtension.fromJsonRDS` | CURRENT | маппинг серверного JSON в `FarmsCompanion` (только подмножество полей) |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear`, `BaseRepository.insertAll` | CURRENT | обобщённые DAO-операции, которыми пользуется `_loadFarmsFromRDS` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.clearAndInsertAll` | CURRENT | нижележащие примитивы удаления всех строк / батч-вставки (`insertOrReplace`); `clearAndInsertAll` существует, но в этом сценарии не используется |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc` (подписка на `watchAll()` в конструкторе) | CURRENT | реактивный потребитель — немедленно отражает перезапись, если экран ферм открыт |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети, полный
  sync-проход запрашивает `GET .../farms?with_places=1` ровно один раз за
  проход, после push-шагов и до `_syncPlaces`.
- Если ответ сервера имеет `status == "1"`/`1` и непустой список ферм,
  локальная таблица `Farms` полностью заменяется (`clear()` затем
  `insertAll()`) содержимым ответа; любая локальная ферма, отсутствующая в
  ответе сервера, после этого шага в локальной БД отсутствует.
- Если ответ пустой либо `status` не равен `"1"`/`1`, локальная таблица
  `Farms` остаётся полностью без изменений — ни одного вызова `clear()`
  или `insertAll()` не происходит.
- Локальная правка фермы (`needUpdate == true`), не подтверждённая
  сервером на предыдущем push-шаге того же прохода, всё равно
  перезаписывается этим шагом при непустом ответе — наблюдаемое
  поведение, а не то, к чему стоит стремиться (см. «Бизнес-правила»).

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` существует, но
единственные тесты в нём — конструирование `DataUpdateBloc` и обработка
`DataUpdateClear`; ни `_loadFarmsFromRDS`, ни `FarmRepository.getAllFarmsFromRDS`,
ни ветка sync-прохода для ферм тестами не покрыты.

## Открытые вопросы и ограничения

- **Молчаливая потеря неподтверждённой локальной правки.** Если push этой
  же фермы в этом же проходе не удался (см. «Бизнес-правила»), эта
  перезагрузка стирает локальную правку и сбрасывает `needUpdate` в
  `false`, не сообщая об этом ни пользователю, ни через отдельный
  per-record статус ошибки — сама sync-фаза при этом всё равно может
  завершиться `DataUpdateSuccess`, если сеть в остальном отработала.
  Поведение существующего кода, не предмет исправления в этом
  документирующем проходе.
- **Не различить «аккаунт без ферм» и «сервер отклонил запрос».**
  Пустой массив и `status != "1"` возвращают одинаковый результат
  (`{'farms': [], 'places': []}`) — вызывающий код не может отличить
  легитимный пустой ответ от серверной ошибки/отказа, и в обоих случаях
  просто оставляет локальные данные как есть.
- **`clear()`+`insertAll()` не атомарны**, хотя транзакционный
  `clearAndInsertAll` для этой же цели уже есть в кодовой базе и не
  используется здесь — окно между двумя вызовами теоретически может
  оставить локальную таблицу ферм пустой при аварийном прерывании
  процесса.
- Адресные id-поля фермы (`countryId` и соседние) стираются в `null` при
  каждой непустой перезагрузке, так как `FarmExtension.fromJsonRDS` их не
  переносит — не проверено, требуются ли эти поля где-либо ниже по потоку
  после первой синхронизации фермы (вне границ этого файла).
