# UC-62 — Система перезагружает список перемещений с сервера при полном sync-проходе

## Назначение

В рамках того же явного полного sync-прохода, что запускает
пользователь (один раз, дальше идёт автоматически) — сразу после отправки
ещё не синхронизированных перемещений на сервер — система забирает с
сервера актуальный список перемещений и приводит локальную таблицу
`Movements` в соответствие с полученным ответом, чтобы локально были видны
перемещения, созданные, например, с другого устройства или другим
пользователем той же СХТП.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода (`DataUpdateBloc`), без участия пользователя в момент именно
этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, и `_authRepository.isAuthorized()` истинно — иначе
   `_syncAuthData` не вызывается вовсе (вне границ этого файла, см.
   [MOD-4](../modules/MOD-4-ANIMAL.md), «Граница»: явный полный sync pass как
   таковой специфицируется модулем `SYSTEM`, не здесь).
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
   `syncAllUnsentAnimals()`, синхронизация настроек, и затем
   `await _movementReportRepository.syncMovements()`.
5. `syncMovements()` вызывает по очереди `sendMovementsToApi()` (push —
   батч ещё не отправленных перемещений) и, **только если push не бросил
   исключение**, `getReportsFromApiAndSave()` — предмет этого use-case (см.
   «Альтернативные потоки» — сбой push-шага).
6. `getReportsFromApiAndSave` строит `ApiMessage(link:
   '${Constants.farmServiceApi}/animal-move', method: ApiMethod.get)` и
   выполняет его через `ApiClient` (`instanceName: 'farm_rpc'`,
   `rpcClientSHTP.call(message)`) — тот же endpoint, что и push-шаг, но
   `GET` вместо `POST`.
7. Ответ читается напрямую как `(response['data'] as List)` — **без
   проверки поля `status`**, в отличие от `getAllFarmsAndPlacesFromRDS`
   (см. «Бизнес-правила»). Каждый элемент мапится через
   `MovementExtension.fromJsonRint`: `Movement.fromJson(json)` (drift-
   генерируемый парсинг по `@JsonKey`-аннотациям колонок `Movements`) с
   последующим `copyWith(remoteId: json['id'], id: null, sync: true)` —
   локальный `id` явно обнуляется, чтобы каждая строка получила новый
   автоинкрементный локальный id при вставке.
8. Если полученный список перемещений непустой — `dao.clear()` (удаляет
   вообще все строки таблицы `Movements`, без фильтра по `sync`), затем
   `dao.insAll(movements)` (батчевая вставка, режим `insertOrReplace`).
9. Если список пустой — оба вызова (`clear()`/`insAll()`) пропускаются:
   локальные данные остаются ровно такими, какими были до этого шага.
10. Весь метод обёрнут в `try/catch` без `rethrow` — любое исключение
    (сетевое, либо `TypeError` при приведении `response['data']` к `List`,
    если ключ отсутствует или сервер вернул другую форму ответа) только
    логируется через `getIt<Talker>().error(...)`, метод завершается
    нормально. Sync-проход продолжается независимо от исхода этого шага:
    `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`,
    `loadAnimals`, `_vaccinationsRepository.syncVaccinations(true)` — не
    предмет этого файла.

### Альтернативные потоки

- **Пустой ответ сервера.** `(response['data'] as List)` пуст —
  `getReportsFromApiAndSave` доходит до условия на шаге 8 и не выполняет ни
  `clear()`, ни `insAll()`. Тот же `RESULT` (`READ_OK` — вызов успешно
  завершился, просто без данных для замены), не отдельный use-case.
- **Push-шаг (`sendMovementsToApi`) бросает исключение.** Если сетевой
  вызов внутри `sendMovementsToApi` падает, либо сервер вернул
  `status != "1"`/`1` (код бросает `Exception(status['message'])`) —
  исключение логируется и **пробрасывается наружу** (`rethrow`) из
  `sendMovementsToApi`. Поскольку `syncMovements()` вызывает
  `getReportsFromApiAndSave()` следующей строкой после `await
  sendMovementsToApi()`, **эта строка не выполняется вовсе** — событие
  [EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md) в
  этом проходе не наступает. Исключение продолжает всплывать через
  `_syncAllData` → `updateAndSyncRegagro` → `_syncAuthData` до внешнего
  `try/catch` в `on<DataUpdateStartAll>`, который эмитит
  `DataUpdateFailure` и завершает **весь** sync-проход ошибкой. Не
  описывается этим файлом (другой актор-инициируемый факт — push, а не
  pull).
- **Сетевое/парсинг-исключение внутри самого `getReportsFromApiAndSave`.**
  В отличие от предыдущего пункта и в отличие от аналогичного pull-шага
  ферм/мест ([UC-29](UC-29-ACTOR-4-EVT-14-ENT-9-READ_OK-IN-FARM.md),
  [UC-43](UC-43-ACTOR-4-EVT-21-ENT-10-READ_OK-IN-FARM.md)) — здесь
  исключение **не пробрасывается**: перехватывается локальным
  `try/catch`, логируется, и `syncMovements()`/`_syncAllData`/весь
  sync-проход продолжаются как ни в чём не бывало. Другой результат
  (`READ_ERROR`), не описывается этим файлом — но стоит отметить именно
  как асимметрию с push-шагом той же самой пары (см. «Бизнес-правила»,
  «Открытые вопросы»).

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) —
  единственная сущность, которую физически переписывает этот шаг; целиком,
  без построчного diff/merge — при непустом ответе локальный `id` каждого
  перемещения меняется на новый (автоинкремент), потому что это
  `delete`+`insert`, а не `update` существующих строк.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим шагом напрямую (в отличие от локального создания
  перемещения, которое немедленно обновляет `Animal.placeId` — см.
  [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), «Инварианты»); поле
  `animal_id` серверного JSON копируется в `Movement.animalId` как есть,
  без пересчёта — на сервере это всегда серверный (синхронизированный) id
  животного, так как перемещение ещё не синхронизированного локально
  животного (`id < 0`) на сервере существовать не может.

### Бизнес-правила

- Перезагрузка — безусловная замена «всё или ничего» **только когда есть
  чем заменять**: непустой ответ полностью вытесняет локальное состояние
  без сравнения по записям; пустой ответ не трогает локальное состояние
  вовсе — нет промежуточного варианта («частично обновить»).
- **Нет проверки `response['status']`** — в отличие от
  `getAllFarmsAndPlacesFromRDS` (ферма/место), этот метод читает
  `response['data']` напрямую без ветвления по статусу ответа; любая форма
  ответа без ожидаемого поля `data`-массива приводит к исключению приведения
  типа, которое обрабатывается общим `try/catch` (см. «Альтернативные
  потоки»).
- `dao.clear()` и `dao.insAll()` — два отдельных `await`-вызова, не единая
  транзакция, хотя `BaseDao.clearAndInsertAll` (оборачивающий оба шага в
  `transaction()`) для этой же цели уже существует в кодовой базе и здесь
  не используется. Если процесс будет прерван между этими двумя вызовами
  (например, крашем приложения), локальная таблица перемещений останется
  полностью пустой до следующего успешного sync-прохода.
- **`clear()` не фильтрует по `sync`** — удаляет вообще все строки таблицы,
  включая ещё не отправленные (`sync == false`), если такие почему-либо
  остались бы к этому моменту. В штатном случае к моменту вызова этого
  шага таких строк уже нет: предшествующий push-шаг (`sendMovementsToApi`)
  либо помечает все прежде неотправленные перемещения `sync=true` (при
  успехе всего батча), либо бросает исключение и предотвращает вызов этого
  шага вовсе (см. «Альтернативные потоки»). Но если между завершением push
  и стартом этого pull локально успеет появиться новая ещё не отправленная
  запись (например, гонка с созданием перемещения из UI в этом же
  приложении, в паузе между двумя `await`), `clear()` безусловно удалит и
  её — не только уже синхронизированные строки.
- **Асимметрия обработки ошибок между push и pull одной и той же пары.**
  `sendMovementsToApi` при ошибке логирует и `rethrow` — это прерывает весь
  sync-проход. `getReportsFromApiAndSave` при ошибке логирует и **не**
  прерывает ничего — сам метод, `syncMovements()`, и весь остальной
  sync-проход продолжаются так, будто перезагрузки не было. Два разных
  паттерна обработки ошибок для двух половин одного и того же
  сетевого round-trip, не унифицированы.
- Опциональный параметр `startTime` метода `getReportsFromApiAndSave`
  принимается, но нигде не используется в теле метода, и ни один вызывающий
  код (`syncMovements`) не передаёт для него значение — мёртвый параметр.
- **Нет реактивного подписчика на полную таблицу `Movements`**
  (`watchAll()`) ни в одном bloc/cubit `lib/pages/` — в отличие от
  `FarmsAndPlacesBloc.watchAll()` для ферм/мест. Экраны, показывающие
  перемещения (`MovementReportCubit.load`, `AnimalHistoryCubit`), запрашивают
  данные разово через `getMovementsWithDetailsByFilters` при открытии/явной
  перезагрузке экрана, а не реактивно по записи в БД — если такой экран
  уже открыт в момент этого шага, перезапись не отразится в нём
  немедленно.

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
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.syncMovements` | CURRENT | последовательность push (`sendMovementsToApi`) → pull (`getReportsFromApiAndSave`); pull вызывается только если push не бросил исключение |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.sendMovementsToApi` | CURRENT | предшествующий push-шаг; при ошибке `rethrow` — тогда pull, предмет этого файла, не вызывается вовсе |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getReportsFromApiAndSave` | CURRENT | ядро этого сценария: `GET`-запрос без проверки `status` + условные `dao.clear()`/`dao.insAll()`, `try/catch` без `rethrow` |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `MovementExtension.fromJsonRint` | CURRENT | маппинг серверного JSON в `Movement` (`remoteId = json['id']`, `id = null`, `sync = true`) |
| `lib/constants.dart` | `Constants.farmServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/animal-move` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.clearAndInsertAll` | CURRENT | нижележащие примитивы — удаление всех строк без фильтра по `sync` / батч-вставка `insertOrReplace`; `clearAndInsertAll` существует в кодовой базе, но здесь не используется |
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.load` | CURRENT | пример разового (не реактивного) чтения перезагруженных данных при открытии экрана отчёта |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и **после**
  успешного (без исключения) завершения push-шага
  (`sendMovementsToApi`), полный sync-проход запрашивает `GET
  .../animal-move` для этого шага ровно один раз за проход.
- Если push-шаг бросает исключение, этот `GET`-запрос не выполняется
  вовсе, и весь sync-проход завершается ошибкой (`DataUpdateFailure`).
- Если ответ на `GET .../animal-move` содержит непустой массив `data`,
  локальная таблица `Movements` полностью заменяется (`dao.clear()` затем
  `dao.insAll()`) содержимым ответа; любое локальное перемещение,
  отсутствующее в ответе сервера, после этого шага в локальной БД
  отсутствует — независимо от того, было ли оно ранее синхронизировано.
- Если массив `data` пустой, локальная таблица `Movements` остаётся
  полностью без изменений — ни `dao.clear()`, ни `dao.insAll()` не
  вызываются.
- Любое исключение внутри самого `getReportsFromApiAndSave` (сеть,
  приведение типа при отсутствии/неверной форме `data`) перехватывается,
  логируется и **не прерывает** ни `syncMovements()`, ни остальной
  sync-проход — в отличие от исключения на предшествующем push-шаге.

## Связанные тесты

TBD — теста нет. Ни push- (`sendMovementsToApi`), ни pull-часть
(`getReportsFromApiAndSave`) `MovementReportRepository`, ни ветка
`_syncAllData`/`syncMovements()` в `DataUpdateBloc` не покрыты тестами на
уровне репозитория или `data_update_bloc_test.dart` (там
`MovementReportRepository` присутствует только как замоканная зависимость
для конструирования `DataUpdateBloc`, без вызова `syncMovements` в тестовых
сценариях). Тесты, перечисленные для соседних use-case'ов перемещения
(`UC-137`/`UC-138` в `test/pages/animal_movement_bloc_test.dart`,
`UC-139`/`UC-140` в `test/pages/unsent_movements_cubit_test.dart`,
`UC-141`/`UC-142` в `test/pages/movement_report_cubit_test.dart`) покрывают
другие события (`AnimalMovementEventSave`, `UnsentMovementsCubit.deleteGroup`,
`MovementReportCubit.deleteEvent`), не pull-перезагрузку с сервера —
предмет этого файла.

## Открытые вопросы и ограничения

- **Асимметричная обработка ошибок push/pull.** Сбой push-шага
  (`sendMovementsToApi`) прерывает весь sync-проход; сбой pull-шага, этот
  файл, только логируется и полностью проглатывается — сама sync-фаза
  может завершиться `DataUpdateSuccess`, даже если перезагрузка списка
  перемещений с сервера фактически не удалась в этом проходе. Пользователь
  не получает никакого сигнала о том, что локальный список перемещений мог
  устареть. Поведение существующего кода, не предмет исправления в этом
  документирующем проходе.
- **Отсутствие проверки `status` в ответе.** В отличие от ферм/мест, этот
  вызов не различает «сервер вернул пустой список» и «сервер вернул
  ошибку/неожиданную форму ответа» — оба случая либо дают пустой массив
  (не трогает локальные данные), либо бросают исключение при приведении
  типа (перехватывается и проглатывается, см. выше).
- **`clear()` не фильтрует по `sync`.** Теоретическое окно гонки: новое
  локально созданное (ещё не отправленное) перемещение, появившееся между
  завершением push-шага и стартом этого pull-шага в рамках одного и того
  же sync-прохода, было бы удалено безусловным `clear()` наравне с уже
  синхронизированными строками — не проверялось, насколько это окно
  реалистично достижимо на практике (однопоточная модель Dart сужает его
  до границ между `await`).
- **`clear()`+`insAll()` не атомарны**, хотя транзакционный
  `clearAndInsertAll` для этой же цели уже есть в кодовой базе и не
  используется здесь — окно между двумя вызовами теоретически может
  оставить локальную таблицу перемещений полностью пустой при аварийном
  прерывании процесса.
- **Мёртвый параметр `startTime`** у `getReportsFromApiAndSave` — принят в
  сигнатуре, не используется в теле, не передаётся ни одним вызывающим
  кодом; не проверялось, задумывался ли он для инкрементальной
  загрузки (аналогично одноимённому параметру
  `DisposalRepository.getReportsFromApiAndSave`) и был ли забыт при
  реализации, либо это осознанно не завершённая часть контракта.
- **Нет реактивного отражения в уже открытом экране.** Экраны отчётов по
  перемещениям читают данные разово при открытии/явном действии
  пользователя, не через `watchAll()` — если экран с перемещениями уже
  открыт в момент этого sync-шага, пользователь не увидит перезагруженные
  данные без повторного захода на экран.
