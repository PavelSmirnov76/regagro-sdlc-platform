# UC-43 — Система перезагружает список мест с сервера при полном sync-проходе

## Назначение

В рамках того же явного полного sync-прохода, что и в
[UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md) (запущен пользователем
один раз, дальше идёт автоматически), система — сразу после перезагрузки
ферм — забирает с сервера актуальный список мест и приводит локальную
таблицу мест в соответствие с полученным ответом, чтобы локально были видны
места, изменённые, например, с другого устройства или другим пользователем
той же СХТП.

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
2. Внутри `_syncAuthData` порядок вызовов такой: сначала
   `_deletePlacesFromRDS()` (отправка удалений мест на сервер — предмет
   другого события), затем `_syncFarms()` (push+pull ферм — предмет
   [UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md)), и только после
   этого — `_syncPlaces()`, который выполняет push-шаги (`_storePlacesToRDS`,
   `_updatePlacesOnRDS`) и лишь затем — `_loadPlacesFromRDS`, предмет этого
   use-case.
3. `_loadPlacesFromRDS` вызывает `PlaceRepository.getAllPlacesFromRDS()`,
   которая делегирует в `FarmRepository.getAllFarmsAndPlacesFromRDS()` — тот
   же метод, что уже вызывался мгновением раньше на шаге фермы
   ([UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md)): `GET
   ${Constants.registrationServiceApi}/farms` с query-параметром
   `with_places: 1`, через `ApiClient` с `instanceName: 'farm_rpc'`. Это
   **второй, независимый** сетевой вызов на тот же endpoint в рамках одного
   sync-прохода, не переиспользование ответа, полученного при перезагрузке
   ферм (см. «Бизнес-правила»).
4. Если `response['status']` равен `"1"` или `1` — сервер вернул массив
   `data`; список мест собирается через `data.expand(...)`, читая
   вложенный `json['places']` **каждого элемента** массива ферм (или пустой
   список, если поле отсутствует), и мапит каждый через
   `PlaceExtension.fromJsonRDS` в `PlacesCompanion` (`idRemote`, `farmId`,
   `name`, `description`, `createdAt`, `updatedAt` — без `needUpdate` и
   `isDeleted`, см. «Бизнес-правила»). `getAllFarmsAndPlacesFromRDS`
   возвращает обе части (`'farms'` и `'places'`) одного и того же вызова;
   `getAllPlacesFromRDS` читает только ключ `'places'`.
5. Обратно в `_loadPlacesFromRDS`: если полученный список мест непустой —
   `_placeRepository.clear()` (удаляет вообще все строки таблицы `Places`),
   затем `_placeRepository.insertAll(res)` (батчевая вставка новых строк с
   заново присвоенными автоинкрементными локальными `id`, режим
   `insertOrReplace`).
6. Если на экране в этот момент открыт список ферм/мест —
   `FarmsAndPlacesBloc` подписан на `_placeRepository.watchAll()`
   (Drift-стрим, `_placesSubscription`), поэтому перезапись отражается в UI
   немедленно, без какого-либо дополнительного триггера.
7. Sync-проход продолжается (`_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   `updateAndSyncRegagro`, `updateAndSyncSHTP`, `_suncDevices`) независимо от
   исхода этого шага — не предмет этого файла.

### Альтернативные потоки

- **Пустой или отклонённый сервером ответ.** Если сервер вернул пустой
  массив, либо `response['status']` не равен `"1"`/`1` —
  `getAllFarmsAndPlacesFromRDS` в обоих случаях возвращает `{'farms': [],
  'places': []}` без какого-либо различения причины (лог `'No data or error
  status'` — общий на обе ветки). `_loadPlacesFromRDS` видит пустой список
  и **возвращается сразу**: ни `clear()`, ни `insertAll()` не вызываются,
  локальные данные остаются ровно такими, какими были до этого шага. Тот же
  `RESULT` (`READ_OK` — вызов успешно завершился, просто без данных для
  замены), не отдельный use-case.
- **Сетевое исключение во время запроса.** Если сам вызов
  `rpcClientSHTP.call(message)` бросает исключение — оно не перехватывается
  ни внутри `getAllFarmsAndPlacesFromRDS`, ни внутри
  `_loadPlacesFromRDS`/`_syncPlaces`/`_syncAuthData`, и всплывает во внешний
  `try/catch` в `on<DataUpdateStartAll>`, который эмитит `DataUpdateFailure`
  и завершает **весь** sync-проход ошибкой (не только places-часть). Другой
  результат (`READ_ERROR`), не описывается этим файлом.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — единственная
  сущность, которую физически переписывает этот шаг; целиком, без
  построчного diff/merge — при непустом ответе локальный `id` каждого места
  меняется на новый (автоинкремент), потому что это `delete`+`insert`, а не
  `update` существующих строк.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не
  пишется этим шагом напрямую, но данные этого шага физически приходят как
  вложенное поле `places` того же серверного JSON-элемента фермы; и связь
  `Places.farmId → Farm.remoteId` (не `Farm.id`) переживает перезапись обеих
  таблиц без разрыва, так как `remoteId` в ответе сервера стабилен между
  проходами.

### Бизнес-правила

- Перезагрузка — безусловная замена «всё или ничего» **только когда есть
  чем заменять**: непустой ответ полностью вытесняет локальное состояние
  без сравнения по записям; пустой/отклонённый ответ не трогает локальное
  состояние вовсе — нет промежуточного варианта («частично обновить»).
- `clear()` и `insertAll()` — два отдельных `await`-вызова, не единая
  транзакция, хотя `BaseDao.clearAndInsertAll` (оборачивающий оба шага в
  `transaction()`) для этой же цели уже существует и используется, например,
  в `AnimalWeighingsDao.clearSync`. Если процесс будет прерван между этими
  двумя вызовами (например, крашем приложения), локальная таблица мест
  останется полностью пустой до следующего успешного sync-прохода.
- **Повторный сетевой вызов того же endpoint.** `_syncFarms` (шаг фермы) и
  `_syncPlaces` (этот шаг) вызывают `getAllFarmsAndPlacesFromRDS()`
  независимо друг от друга — каждый делает свой `GET .../farms?with_places=1`
  и получает свой полный JSON-ответ с обеими вложенными частями (`farms` +
  `places`), при этом каждый вызывающий читает только свою половину
  (`'farms'` либо `'places'`) и отбрасывает другую. Один и тот же ответ
  сервера фактически запрашивается дважды за один sync-проход.
- `PlaceExtension.fromJsonRDS` не заполняет `needUpdate` и `isDeleted` — в
  `PlacesCompanion` эти значения остаются `Value.absent()`, и поскольку
  `_loadPlacesFromRDS` вставляет строки заново (не обновляет существующие),
  а обе эти колонки в `Places` — `withDefault(const Constant(false))`, при
  вставке они безусловно получают `false`. Как следствие:
  - если предыдущий push-шаг `_updatePlacesOnRDS` не подтверждён сервером
    (`isUpdated == false`, локальный `needUpdate` остаётся `true`) —
    следующий же шаг, этот, молча перезаписывает то же место серверной
    версией с `needUpdate == false`, теряя признак неотправленной правки
    без какой-либо ошибки пользователю (тот же паттерн, что для фермы в
    [UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md), «Бизнес-правила»).
  - если удаление места на сервере не подтверждено (`_deletePlacesFromRDS`:
    `deletePlacesOnRDS` вернул `false` — по неуспешному статусу или по
    перехваченному исключению — и локальная строка с `isDeleted == true`
    поэтому не была удалена через `deleteAll(res)`), а место при этом
    по-прежнему существует на сервере — этот шаг вставляет его заново с
    `isDeleted == false`, то есть **локально «отменяет» ранее запрошенное
    пользователем удаление места**, не сообщая об этом.
- Порядок внутри `_syncAuthData` — сначала `_deletePlacesFromRDS()`, затем
  `_syncFarms()` (push+pull ферм), и только затем `_syncPlaces()` (push+pull
  мест, этот файл — последний pull-шаг всей последовательности).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | гейтит вызов за `isAuthorized()`, задаёт порядок `_deletePlacesFromRDS` → `_syncFarms` → `_syncPlaces` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncPlaces` | CURRENT | последовательность push (`_storePlacesToRDS`, `_updatePlacesOnRDS`) → pull (`_loadPlacesFromRDS`) для мест |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadPlacesFromRDS` | CURRENT | ядро этого сценария: запрос + условные `clear()`/`insertAll()` |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllPlacesFromRDS` | CURRENT | тонкая обёртка, читающая ключ `'places'` общего ответа |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsAndPlacesFromRDS` | CURRENT | сам HTTP GET `.../farms?with_places=1`, проверка `status`, маппинг вложенных `places` из JSON |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `PlaceExtension.fromJsonRDS` | CURRENT | маппинг серверного JSON в `PlacesCompanion` (только подмножество полей, без `needUpdate`/`isDeleted`) |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear`, `BaseRepository.insertAll` | CURRENT | обобщённые DAO-операции, которыми пользуется `_loadPlacesFromRDS` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.clearAndInsertAll` | CURRENT | нижележащие примитивы удаления всех строк / батч-вставки (`insertOrReplace`); `clearAndInsertAll` существует, но в этом сценарии не используется |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc` (`_placesSubscription`, подписка на `watchAll()` в конструкторе) | CURRENT | реактивный потребитель — немедленно отражает перезапись, если экран ферм/мест открыт |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети, полный
  sync-проход запрашивает `GET .../farms?with_places=1` для этого шага ровно
  один раз за проход, после `_deletePlacesFromRDS`, после `_syncFarms` и
  после push-шагов `_syncPlaces` (`_storePlacesToRDS`, `_updatePlacesOnRDS`).
- Если ответ сервера имеет `status == "1"`/`1` и непустой список
  вложенных мест хотя бы у одной фермы, локальная таблица `Places`
  полностью заменяется (`clear()` затем `insertAll()`) содержимым ответа;
  любое локальное место, отсутствующее в ответе сервера, после этого шага в
  локальной БД отсутствует.
- Если ответ пустой либо `status` не равен `"1"`/`1`, локальная таблица
  `Places` остаётся полностью без изменений — ни одного вызова `clear()`
  или `insertAll()` не происходит.
- Локальная правка места (`needUpdate == true`), не подтверждённая сервером
  на предыдущем push-шаге того же прохода, всё равно перезаписывается этим
  шагом при непустом ответе — наблюдаемое поведение, а не то, к чему стоит
  стремиться (см. «Бизнес-правила»).
- Локальное удаление места (`isDeleted == true`), не подтверждённое
  сервером на предыдущем шаге `_deletePlacesFromRDS`, при непустом ответе
  всё равно «отменяется» этим шагом — место возвращается с `isDeleted ==
  false` (см. «Бизнес-правила»).

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` существует, но
единственные тесты в нём — конструирование `DataUpdateBloc` и обработка
`DataUpdateClear`; ни `_loadPlacesFromRDS`, ни
`FarmRepository.getAllFarmsAndPlacesFromRDS`, ни ветка sync-прохода для мест
тестами не покрыты.

## Открытые вопросы и ограничения

- **Молчаливая потеря неподтверждённой локальной правки.** Если push этого
  же места в этом же проходе не удался (см. «Бизнес-правила»), эта
  перезагрузка стирает локальную правку и сбрасывает `needUpdate` в
  `false`, не сообщая об этом ни пользователю, ни через отдельный
  per-record статус ошибки — сама sync-фаза при этом всё равно может
  завершиться `DataUpdateSuccess`, если сеть в остальном отработала.
  Поведение существующего кода, не предмет исправления в этом
  документирующем проходе.
- **Молчаливая отмена неподтверждённого удаления места.** Если удаление
  места на сервере не подтверждено (см. «Бизнес-правила»), эта перезагрузка
  возвращает место локально с `isDeleted == false`, то есть пользователь,
  запросивший удаление, увидит место снова после следующего же
  sync-прохода — без объяснения причины. Тот же класс проблемы, что и
  потеря `needUpdate`, но для другого поля и другого предшествующего шага.
- **Не различить «у фермы нет мест» и «сервер отклонил запрос».** Пустой
  массив и `status != "1"` возвращают одинаковый результат (`{'farms': [],
  'places': []}`) — вызывающий код не может отличить легитимный пустой
  ответ от серверной ошибки/отказа, и в обоих случаях просто оставляет
  локальные данные как есть.
- **`clear()`+`insertAll()` не атомарны**, хотя транзакционный
  `clearAndInsertAll` для этой же цели уже есть в кодовой базе и не
  используется здесь — окно между двумя вызовами теоретически может
  оставить локальную таблицу мест пустой при аварийном прерывании процесса.
- **Дублирующий сетевой вызов.** Один и тот же endpoint
  (`GET .../farms?with_places=1`) запрашивается дважды за один sync-проход
  — один раз ради `farms` (шаг фермы), один раз ради `places` (этот шаг) —
  не проверено, есть ли у этого заметная стоимость (задержка, нагрузка на
  сервер) вне границ этого документирующего прохода.
