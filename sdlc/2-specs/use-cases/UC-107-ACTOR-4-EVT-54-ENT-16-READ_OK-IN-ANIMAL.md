# UC-107 — Система перезагружает список выбытий с сервера при полном sync-проходе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь
(один раз, дальше идёт автоматически) — сразу после отправки ещё не
синхронизированных выбытий на сервер — система забирает с сервера список
выбытий за последний год (либо с явно заданной даты) и приводит локальную
таблицу `Disposals` в соответствие с полученным ответом, чтобы локально были
видны выбытия, созданные, например, с другого устройства или другим
пользователем той же СХТП.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода (`DataUpdateBloc`), без участия пользователя в момент
именно этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, и `_authRepository.isAuthorized()` истинно — иначе
   `_syncAuthData` не вызывается вовсе (вне границ этого файла).
2. `_syncAuthData` выполняет по порядку `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`,
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`, и затем
   `updateAndSyncRegagro(event, emit)`.
3. `updateAndSyncRegagro` — в зависимости от количества уже сохранённых
   `DataUpdate`-записей, наличия записей с ошибкой и флагов события
   (`event.again`/`event.fullUpdate`) — при подтверждённом сетевом
   подключении вызывает `_syncAllData(event, emit)`; при отсутствии сети на
   этом повторном шаге эмитит `DataUpdateFailure` (вне границ этого файла).
4. Внутри `_syncAllData`: `_clearDataUpdates()`, `loadUser`,
   `syncAllUnsentAnimals()`, синхронизация настроек, затем
   `await _movementReportRepository.syncMovements()` (Movement — не
   предмет этого файла), и сразу за ней `await
   _disposalRepository.syncDisposals()` — начало сценария этого файла.
5. `syncDisposals()` вызывает по очереди `await sendDisposalsToApi()`
   (push — батч ещё не отправленных выбытий, [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md))
   и, **только если предыдущая строка не бросила исключение**, `await
   getReportsFromApiAndSave()` — предмет этого use-case. Между двумя
   вызовами нет собственного `try/catch`: это последовательные `await` в
   теле одного метода.
6. `getReportsFromApiAndSave({DateTime? startTime})` строит окно дат: `end`
   = завтрашняя дата (`DateTime.now().add(Duration(days: 1))`), `start` =
   `startTime ?? (DateTime.now().subtract(Duration(days: 365)))` — оба
   форматируются как `'yyyy-MM-dd'` (`DateFormat('yyyy-MM-dd')`, без
   времени, в отличие от push-запроса `sendDisposalList`, который шлёт
   `'yyyy-MM-dd hh:mm:ss'`). `syncDisposals()` вызывает метод без
   аргументов — `startTime` фактически всегда `null` в этом проходе, окно
   всегда «последний год».
7. Метод строит `ApiMessage(link: '${Constants.disposalServiceApi}/disposals',
   method: ApiMethod.get, data: {'start_date': start, 'end_date': end})` и
   выполняет его через `ApiClient` (`getIt.get<ApiClient>(instanceName:
   'farm_rpc')`, `rpcClientSHTP.call(message)`) — тот же endpoint, что и
   push-шаг (`sendDisposalList`), но `GET` вместо `POST`.
8. Ответ читается напрямую как `(response['data'] as List)` — **без
   проверки поля `status`**. Каждый элемент `e` мапится в два шага:
   - `DisposalExtension.fromJsonRint(e)` → `Disposal.fromJson(e)`
     (drift-генерируемый парсинг по `@JsonKey`-аннотациям колонок
     `Disposals`: `place_id`→`placeId`, `cause_id`→`causeId`,
     `to_place_id`→`toPlaceId`, `from_id`→`fromId`, `to_id`→`toId`,
     `animal_id`→`animalId`, `date`, `deleted_at`, `created_at`,
     `updated_at`, `guid`, `user_id`, `sync`, `remoteId`), затем
     `.copyWith(remoteId: Value(e['id']), id: const Value(null), sync:
     const Value(true), causeId: Value(e['disposal_reason_id']))` —
     локальный `id` явно обнуляется (новый автоинкрементный id при
     вставке), и **`causeId` немедленно переопределяется** значением ключа
     `disposal_reason_id`, а не `cause_id`, которым это же поле только что
     было распаршено базовым `fromJson` (тот же ключ, что использует
     push-запрос `sendDisposalList` — `'disposal_reason_id': causeId`).
     Если ответ этого GET-эндпоинта в принципе не содержит `cause_id`,
     первичный парсинг даёт `causeId == null`, и правильное значение
     появляется только благодаря этому явному `copyWith`.
   - В репозитории результат ещё раз оборачивается:
     `disposal.copyWith(placeId: Value(e['from_place_id'] as int?))` —
     `placeId` **перезаписывается** значением ключа `from_place_id`,
     полностью замещая то, что базовый `fromJson` уже распарсил из ключа
     `place_id` (который этот конкретный GET-ответ, судя по имени
     используемого ключа, не содержит). `toPlaceId`, в отличие от
     `placeId`, не переопределяется репозиторием отдельно — он приходит
     из базового `fromJson` напрямую по ключу `to_place_id`, который
     совпадает с `@JsonKey`-аннотацией колонки, поэтому дополнительный
     `copyWith` для него не нужен технически, хотя по факту оба поля
     («место отправления» и «целевое место») в равной мере читаются из
     полей ответа `from_place_id`/`to_place_id`, а не пересчитываются из
     текущего `Animal.placeId` — ни то, ни другое поле код вообще не
     читает на этом шаге.
9. Если полученный список выбытий непустой — `await dao.clear()` (удаляет
   вообще все строки таблицы `Disposals`, без фильтра по `sync`), затем
   `await dao.insAll(disposals)` (батчевая вставка, режим `insertOrReplace`,
   `BaseDao.insAll`). Оба вызова — отдельные `await`, не единая транзакция
   (`BaseDao.clearAndInsertAll` для этой же цели существует в кодовой базе,
   но здесь не используется).
10. Если список пустой — оба вызова (`clear()`/`insAll()`) пропускаются:
    локальные данные остаются ровно такими, какими были до этого шага.
    Метод в любом случае возвращает построенный список `disposals`
    (используется в тестах; вызывающий код `syncDisposals()` возвращаемое
    значение игнорирует).
11. **У метода нет собственного `try/catch`** — ни вокруг сетевого вызова,
    ни вокруг разбора ответа, ни вокруг `clear()`/`insAll()`. Любое
    исключение (сетевая ошибка внутри `rpcClientSHTP.call`, `TypeError` при
    `response['data'] as List` или при `e['from_place_id'] as int?`, ошибка
    БД внутри `dao.clear()`/`dao.insAll()`) продолжает всплывать наружу без
    какой-либо обработки на этом уровне — из `getReportsFromApiAndSave`,
    через `syncDisposals()` (тоже без `try/catch`), через `_syncAllData`,
    `updateAndSyncRegagro`, `_syncAuthData`, до внешнего `try/catch` в
    `on<DataUpdateStartAll>` (см. «Альтернативные потоки»).
12. Если весь метод завершился без исключения — sync-проход продолжается:
    `_syncEditedAnimals()`, `loadAnimals`,
    `_vaccinationsRepository.syncVaccinations(true)` — не предмет этого
    файла.

### Альтернативные потоки

- **Пустой ответ сервера.** `(response['data'] as List)` пуст —
  `getReportsFromApiAndSave` доходит до условия на шаге 9 и не выполняет ни
  `clear()`, ни `insAll()`. Тот же `RESULT` (`READ_OK` — вызов успешно
  завершился, просто без данных для замены), не отдельный use-case; ровно
  так документирует третий тест группы (см. «Связанные тесты»).
- **Ответ без `from_place_id`/`to_place_id`.** Устаревший формат ответа
  сервера (без этих двух полей) не приводит к исключению — `e['x'] as
  int?` на отсутствующем ключе даёт `null`, а не бросает. Сохранённая
  запись получает `placeId == null` и `toPlaceId == null`; текущее
  `Animal.placeId` животного при этом **не подставляется** ни в каком
  виде — второй тест группы проверяет это явно, включая заранее вставленное
  в БД животное с `placeId: 999`, которое никак не влияет на результат.
- **Push-шаг (`sendDisposalsToApi`) бросает исключение.** Если сетевой
  вызов внутри `sendDisposalsToApi`/`sendDisposalList` падает — исключение
  логируется (`getIt<Talker>().error(...)`) и **пробрасывается наружу**
  (`rethrow`) из `sendDisposalsToApi`. Поскольку `syncDisposals()` вызывает
  `getReportsFromApiAndSave()` следующей строкой после `await
  sendDisposalsToApi()` без собственного `try/catch`, **эта строка не
  выполняется вовсе** — событие
  [EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md) в
  этом проходе не наступает. Исключение продолжает всплывать через
  `_syncAllData` → `updateAndSyncRegagro` → `_syncAuthData` до внешнего
  `try/catch` в `on<DataUpdateStartAll>`, который эмитит
  `DataUpdateFailure` и завершает **весь** sync-проход ошибкой (в том числе
  прерывая `_syncEditedAnimals`, `loadAnimals`,
  `_vaccinationsRepository.syncVaccinations`). Другой актор-инициируемый
  факт (push, а не pull) — не описывается этим файлом.
- **Сетевое/парсинг/БД-исключение внутри самого `getReportsFromApiAndSave`.**
  В отличие от аналогичного pull-шага Movement
  ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md),
  `MovementReportRepository.getReportsFromApiAndSave`, где такое
  исключение перехватывается локальным `try/catch`, логируется и
  проглатывается — sync-проход продолжается как ни в чём не бывало) —
  здесь **нет никакой локальной обработки вообще**: исключение
  распространяется точно так же, как и исключение push-шага (см. пункт
  выше), до внешнего `try/catch` в `on<DataUpdateStartAll>`, и точно так же
  завершает **весь** sync-проход ошибкой (`DataUpdateFailure`). Другой
  результат (`READ_ERROR`), не описывается этим файлом — но стоит отметить
  как отличие от асимметрии Movement (см. «Бизнес-правила», «Открытые
  вопросы»).

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) —
  единственная сущность, которую физически переписывает этот шаг; целиком,
  без построчного diff/merge — при непустом ответе локальный `id` каждого
  выбытия меняется на новый (автоинкремент), потому что это
  `delete`+`insert`, а не `update` существующих строк.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим шагом напрямую; поле `animal_id` серверного JSON
  копируется в `Disposal.animalId` как есть, без пересчёта. Инвариант
  «создание Disposal не помечает животное выбывшим локально» (см.
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), «Связи») этим шагом
  не затрагивается — он про создание, а не про перезагрузку.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md)
  (DisposalReason, HANDBOOKS) — не читается и не пишется; `causeId`
  каждой сохранённой записи ссылается на неё по значению, взятому из
  ответа (`disposal_reason_id`), без валидации существования справочной
  записи с таким id на этом шаге.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — не читается и
  не пишется; `fromId`/`toId` каждой сохранённой записи копируются из
  ответа (`from_id`/`to_id`) как есть.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — не
  читается и не пишется; `placeId`/`toPlaceId` каждой сохранённой записи
  копируются из ответа (`from_place_id`/`to_place_id`) как есть, включая
  случай, когда сервер их не прислал (оба остаются `null`, см.
  «Альтернативные потоки»).

### Бизнес-правила

- Перезагрузка — безусловная замена «всё или ничего» **только когда есть
  чем заменять**: непустой ответ полностью вытесняет локальное состояние
  без сравнения по записям; пустой ответ не трогает локальное состояние
  вовсе — нет промежуточного варианта («частично обновить»). Тот же
  паттерн, что у Movement
  ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)); отличается
  от Vaccination/AnimalWeighing, где `clear()` безусловен (см.
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)).
- **Нет проверки `response['status']`** — метод читает `response['data']`
  напрямую без ветвления по статусу ответа; любая форма ответа без
  ожидаемого поля `data`-массива приводит к исключению приведения типа,
  которое здесь **ничем не перехватывается** (см. следующий пункт).
- **Симметрично с push-шагом, в отличие от Movement.** У Movement push
  (`rethrow`, прерывает весь проход) и pull (локальный `try/catch`,
  проглатывает исключение, проход продолжается) обрабатывают ошибку
  по-разному — задокументированная асимметрия
  ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)). У
  Disposal такой асимметрии нет: ни push (`sendDisposalsToApi`, явный
  `rethrow`), ни pull (`getReportsFromApiAndSave`, вообще без `try/catch`)
  не глотают исключение — оба одинаково прерывают весь sync-проход.
- `dao.clear()` и `dao.insAll()` — два отдельных `await`-вызова, не единая
  транзакция, хотя `BaseDao.clearAndInsertAll` (оборачивающий оба шага в
  `transaction()`) для этой же цели уже существует в кодовой базе и здесь
  не используется.
- **`clear()` не фильтрует по `sync`** — удаляет вообще все строки
  таблицы, включая ещё не отправленные (`sync == false`), если такие
  почему-либо остались бы к этому моменту. В штатном случае к моменту
  вызова этого шага таких строк уже нет: предшествующий push-шаг либо
  помечает все прежде неотправленные выбытия `sync=true` (при успехе всего
  батча), либо бросает исключение и предотвращает вызов этого шага вовсе.
- Опциональный параметр `startTime` метода `getReportsFromApiAndSave`
  принимается, но единственный вызывающий код (`syncDisposals`) не
  передаёт для него значение — окно запроса всегда «последний год»,
  инкрементальная загрузка с явной даты сигнатурой поддерживается, но
  ничем в проде не используется.
- **Нет реактивного подписчика на полную таблицу `Disposals`**
  (`watchAll()`) ни в одном bloc/cubit `lib/pages/` — `DisposalRepository`
  экспонирует только `watchCountNotSync()`/`watchNotSyncDisposals()`,
  оба фильтрованные по `sync == false`. Экраны, показывающие выбытия
  (`DisposalReportCubit.load`, `AnimalHistoryCubit`), запрашивают данные
  разово через `getDisposalsWithDetailsByFilters`/аналоги при
  открытии/явной перезагрузке экрана, а не реактивно по записи в БД —
  если такой экран уже открыт в момент этого шага, перезапись не
  отразится в нём немедленно.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | гейтит вызов за `isAuthorized()`, задаёт порядок относительно ферм/мест/взвешиваний, ведёт к `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе (по счётчику `DataUpdate`, ошибкам, флагам события), повторно гейтит проверкой сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | задаёт порядок: `...` → `_movementReportRepository.syncMovements()` → `_disposalRepository.syncDisposals()` → `...` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.syncDisposals` | CURRENT | последовательность push (`sendDisposalsToApi`) → pull (`getReportsFromApiAndSave`), без `try/catch` между шагами |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.sendDisposalsToApi` | CURRENT | предшествующий push-шаг; при ошибке `rethrow` — тогда pull, предмет этого файла, не вызывается вовсе |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getReportsFromApiAndSave` | CURRENT | ядро сценария: `GET`-запрос без проверки `status` + условные `dao.clear()`/`dao.insAll()`, без `try/catch` вообще |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `DisposalExtension.fromJsonRint` | CURRENT | маппинг серверного JSON в `Disposal` (`remoteId = json['id']`, `id = null`, `sync = true`, `causeId` переопределён из `disposal_reason_id`) |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals`, `Disposal.fromJson` (генерируемый) | CURRENT | таблица и базовый парсинг по `@JsonKey`-аннотациям колонок (`place_id`, `to_place_id`, `from_id`, `to_id`, `cause_id`, ...) |
| `lib/constants.dart` | `Constants.disposalServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/disposals` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.clearAndInsertAll` | CURRENT | нижележащие примитивы — удаление всех строк без фильтра по `sync` / батч-вставка `insertOrReplace`; `clearAndInsertAll` существует в кодовой базе, но здесь не используется |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.load` | CURRENT | пример разового (не реактивного) чтения перезагруженных данных при открытии экрана отчёта |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и
  **после** успешного (без исключения) завершения push-шага
  (`sendDisposalsToApi`), полный sync-проход запрашивает `GET
  .../disposals?start_date=...&end_date=...` для этого шага ровно один
  раз за проход, с окном «последний год — завтра».
- Если push-шаг бросает исключение, этот `GET`-запрос не выполняется
  вовсе, и весь sync-проход завершается ошибкой (`DataUpdateFailure`).
- Если ответ на `GET .../disposals` содержит непустой массив `data`,
  локальная таблица `Disposals` полностью заменяется (`dao.clear()` затем
  `dao.insAll()`) содержимым ответа; любое локальное выбытие,
  отсутствующее в ответе сервера, после этого шага в локальной БД
  отсутствует — независимо от того, было ли оно ранее синхронизировано.
- Если массив `data` пустой, локальная таблица `Disposals` остаётся
  полностью без изменений — ни `dao.clear()`, ни `dao.insAll()` не
  вызываются.
- `placeId`/`toPlaceId` каждой сохранённой записи равны значениям полей
  ответа `from_place_id`/`to_place_id` соответственно, независимо от
  текущего `Animal.placeId` того же животного; если сервер не прислал эти
  поля, оба остаются `null`.
- Любое исключение внутри самого `getReportsFromApiAndSave` (сеть,
  приведение типа при отсутствии/неверной форме `data` или
  `from_place_id`, ошибка БД) не перехватывается на этом уровне и
  прерывает весь sync-проход ошибкой (`DataUpdateFailure`) — так же, как
  и исключение предшествующего push-шага, без асимметрии, задокументированной
  для Movement.

## Связанные тесты

`test/repositories/disposal_repository_test.dart` →
`group('UC-107 — getReportsFromApiAndSave', ...)` (имя группы со старым
номером — переименование будет сделано отдельным проходом, ссылка
работоспособна уже сейчас через `grep -r "UC-320" test/`), 3 теста:

- `'from_place_id/to_place_id ответа -> placeId/toPlaceId сохранённой
  записи (без обогащения через Animal.placeId)'` — заранее вставляет
  `Animal(id: 224, placeId: 999)`, мокает ответ с `from_place_id: 55`,
  `to_place_id: 66`, проверяет, что и возвращённый результат, и
  сохранённая в БД запись получили `placeId: 55`/`toPlaceId: 66`, а не
  `999` от животного.
- `'ответ без from_place_id/to_place_id (устаревший запрос) -> placeId/
  toPlaceId остаются null, не подставляется текущее место животного'` —
  тот же заранее вставленный `Animal(placeId: 999)`, мокает ответ без
  `from_place_id`/`to_place_id` (оба `null`), проверяет `placeId`/
  `toPlaceId` результата равны `null`.
- `'пустой ответ сервера -> локальные данные не трогаются'` — заранее
  вставляет существующую запись `Disposal(guid: 'existing')`, мокает
  ответ `{'data': []}`, проверяет, что после вызова в БД по-прежнему ровно
  одна запись с тем же `guid`.

## Открытые вопросы и ограничения

- **Нет обработки ошибок вообще внутри `getReportsFromApiAndSave`.**
  В отличие от Movement (`MovementReportRepository.getReportsFromApiAndSave`,
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)), где сбой
  этого шага логируется и проглатывается, у Disposal сбой этого шага
  прерывает **весь** sync-проход так же, как и сбой push-шага — не
  проверялось, осознанное ли это решение (например, «Disposal критичнее
  Movement для целостности данных») или просто отсутствие try/catch,
  скопированного по аналогии с другими сущностями, было забыто именно
  здесь.
- **Хрупкая связь между `@JsonKey('cause_id')` и ручным
  `causeId: Value(json['disposal_reason_id'])`.** Аннотация колонки
  говорит «это поле приходит по ключу `cause_id`», но для этого конкретного
  GET-ответа фактическое значение подставляется отдельной строкой кода,
  читающей другой ключ (`disposal_reason_id`, тот же, что использует
  push-запрос). Если кто-то в будущем уберёт этот `copyWith`, ожидая, что
  `Disposal.fromJson` уже сам корректно распарсил `causeId` по аннотации,
  значение молча станет `null` для ответов без ключа `cause_id` — не
  проверялось, содержит ли реальный ответ сервера оба ключа одновременно.
- **`clear()` не фильтрует по `sync`.** Теоретическое окно гонки: новое
  локально созданное (ещё не отправленное) выбытие, появившееся между
  завершением push-шага и стартом этого pull-шага в рамках одного и того
  же sync-прохода, было бы удалено безусловным `clear()` наравне с уже
  синхронизированными строками — не проверялось, насколько это окно
  реалистично достижимо на практике (однопоточная модель Dart сужает его
  до границ между `await`).
- **`clear()`+`insAll()` не атомарны**, хотя транзакционный
  `clearAndInsertAll` для этой же цели уже есть в кодовой базе и не
  используется здесь — окно между двумя вызовами теоретически может
  оставить локальную таблицу выбытий полностью пустой при аварийном
  прерывании процесса.
- **Мёртвый параметр `startTime`** у `getReportsFromApiAndSave` — принят в
  сигнатуре, не используется телом метода иначе как через `??`-fallback,
  но единственный вызывающий код (`syncDisposals`) никогда не передаёт для
  него значение; та же ситуация задокументирована для одноимённого
  параметра `MovementReportRepository.getReportsFromApiAndSave`
  ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)) — не
  проверялось, задумывался ли он для инкрементальной загрузки и был ли
  забыт при реализации, либо это осознанно не завершённая часть
  контракта в обеих сущностях одновременно.
- **Нет реактивного отражения в уже открытом экране.** Экраны отчётов по
  выбытиям читают данные разово при открытии/явном действии пользователя,
  не через `watchAll()` — если экран с выбытиями уже открыт в момент
  этого sync-шага, пользователь не увидит перезагруженные данные без
  повторного захода на экран.
