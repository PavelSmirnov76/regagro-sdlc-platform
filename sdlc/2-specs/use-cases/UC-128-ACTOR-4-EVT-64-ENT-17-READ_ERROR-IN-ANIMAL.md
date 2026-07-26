# UC-128 — Пул отчётов инвентаризации с сервера отказывает уже после того, как локальный кэш и очередь готовых к отправке сессий безусловно очищены — весь sync-проход обрывается, данные инвентаризации временно недоступны локально

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md) —
`DataUpdateBloc.updateAndSyncSHTP` → `loadShtp` →
`ReportAnimalsRepository.getReportsFromApi` — здесь именно этот сетевой
вызов (либо разбор его ответа) заканчивается неуспехом. Ключевая
особенность этого шага, отличающая его от симметричных pull-сбоев других
под-областей `ANIMAL` (см. «Бизнес-правила»): к моменту вызова
`getReportsFromApi` локальный кэш `ReportAnimals` уже **безусловно** очищен
(`_reportsRepository.clear()`) и все строки `UnsentReportAnimals` с
`readyToSend == true` уже **безусловно** удалены
(`_unsentReportsRepository.deleteAllReadyToSend()`) — обе операции выполняются
строкой раньше, независимо от того, был ли перед этим push (`getAllReadyToSend()`
вернул непустой список) и независимо от исхода этого push, если он был (см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
[EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)). Отказ
именно пула, документируемый здесь, наступает уже после этой точки
невозврата: локальные данные инвентаризации к этому моменту в любом случае
уже стёрты, и единственный шанс их восстановить в рамках этого прохода —
успешный `getReportsFromApi`.

Чтением кода подтверждены два независимо проверяемых, но одинаково
непойманных подслучая одного и того же отказа:

- **(а) техническое исключение транспорта** — `CustomDioClient.call`
  перехватывает любую сетевую/HTTP-ошибку, логирует и `rethrow`;
- **(б) ответ получен без исключения, но не в ожидаемой форме** —
  `CustomDioClient.call` возвращает управление нормально (никакого
  исключения, никакого лога), но `getReportsFromApi`'s собственное
  приведение `response['animal_exits'] as List` (либо построчный разбор
  `_fromJson` внутри `.map(...)`) бросает `TypeError` уже внутри
  `getReportsFromApi`, никем не залогированный до внешнего обработчика.

Обе ветки сходятся в одном и том же результате — `READ_ERROR`, обрыв всего
sync-прохода, `DataUpdateFailure` — отличаясь только тем, залогирован ли
отказ дважды (ветка а) или один раз (ветка б), см. «Основной поток»/«Бизнес-правила».

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самого
отказа нет — проход запущен ранее авторизованным пользователем
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), `AuthRepository.isAuthorized()`
— без этого `_syncAuthData`, а значит и `updateAndSyncSHTP`, не вызывается
вовсе) через `DataUpdateStartAll`, диспатчимый, например, из `main_page.dart`
(слушатель `AuthToMain`), `in_work_page.dart` (кнопка «Обновить данные»,
`isUpdateData: true`) или самим экраном `data_update_page.dart` (кнопка
«Попробовать снова» после предыдущего отказа) — дальше проход идёт
автоматически, без участия пользователя на уровне отдельного сетевого
вызова, как и описано в [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md).
Данные, которые этим сценарием становятся временно недоступны локально
(записанные сессии инвентаризации), были ранее созданы
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гостем или авторизованным
пользователем одинаково, через `ScanningBloc`
([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)/[EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md)) —
ACTOR-5 не участвует в самом sync-шаге.

## CURRENT

### Основной поток

1. Авторизованный пользователь ранее инициировал полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Проверка сети пройдена, при
   `_authRepository.isAuthorized()` выполнение дошло до `_syncAuthData(event, emit)`.
2. `_syncAuthData` последовательно выполняет `_deletePlacesFromRDS()`,
   `_syncFarms()`, `_syncPlaces()`, `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`,
   затем `await updateAndSyncRegagro(event, emit)` — в этом сценарии все они
   завершаются без исключения (что бы каждый из них ни сделал внутри себя).
   `updateAndSyncSHTP` вызывается следующей строкой **безусловно**, независимо
   от того, что именно решил сделать `updateAndSyncRegagro` (см. «Бизнес-правила» —
   этот шаг не разделяет условия `errorDataUpdates`/`totalDataUpdatesCount`,
   которые управляют Movement/Disposal/Vaccination/Animals). Вызов —
   `await updateAndSyncSHTP(event, emit);`, без собственного `try/catch` на
   месте вызова.
3. `updateAndSyncSHTP`: `_emitProgress(dataKey: DataKey.syncReports, dataCategory: DataCategory.syncReports)`;
   `unsentReportAnimals = await _unsentReportsRepository.getAllReadyToSend()` —
   выбирает все строки `UnsentReportAnimals` с `readyToSend == true`,
   независимо от `way_type` (общий метод не только для инвентаризации).
4. Если список непуст — `await _unsentReportsRepository.sync(unsentReportAnimals)`
   (POST `/exit-event`, без собственного `try/catch`, без проверки
   `response['status']`, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)/[EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)).
   В этом сценарии этот шаг (если выполнялся) завершился без исключения —
   технический сбой именно на этой строке принадлежит отдельному сценарию, не
   документируемому здесь (см. «Альтернативные потоки»).
5. **Безусловно**, независимо от того, был ли список на шаге 3 пуст и был ли
   push вообще вызван: `await _reportsRepository.clear()` →
   `BaseRepository.clear()` → `dao.clear()` → `delete(_currentTableInfo).go()` —
   удаляет **все** строки таблицы `ReportAnimals` (весь ранее закэшированный
   локально отчёт по проходам, вся глубина «последний год», не только текущая
   сессия/тип).
6. Тоже безусловно: `await _unsentReportsRepository.deleteAllReadyToSend()` —
   удаляет все строки `UnsentReportAnimals` с `readyToSend == true`,
   независимо от того, был ли push для них успешен, отказал по сети, или
   отказал по содержимому ответа сервера — все три исхода push приводят сюда
   одинаково (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).
7. `await loadShtp(emit)` — следующая строка, тоже без `try/catch` на месте
   вызова. Внутри: `_emitProgress(dataKey: DataKey.reports, dataCategory: DataCategory.reports)` —
   перезаписывает `_currentDataCategory`/`_currentDataKey`, выставленные шагом
   3, на значения, точно указывающие на «отчёты» (см. «Бизнес-правила» —
   контраст с соседними pull-сбоями).
8. `final reports = await _reportsRepository.getReportsFromApi();` —
   единственный сетевой вызов этого сценария. Внутри метода (без собственного
   `try/catch`): строится `data = {'start_date': <365 дней назад>, 'end_date': <завтра>}`;
   `final rpcClientSHTP = getIt.get<ApiClient>(instanceName: 'farm_rpc'); final response = await rpcClientSHTP.call(message);` —
   именно здесь сценарий расходится на два независимо проверенных подслучая.
9. **Ветка (а) — техническое исключение транспорта.** `CustomDioClient.call`
   перехватывает любое исключение `dio.request`/`AuthInterceptor.getTokenDataByPath`
   (сеть недоступна, таймаут, обрыв соединения, либо любой не-2xx HTTP-ответ —
   `DioClient` не переопределяет `validateStatus`, поэтому Dio по умолчанию
   бросает `DioException` вне 200–299), логирует через
   `getIt.get<Talker>().error('CustomDioClient: call: $e')` и безусловно
   `rethrow`. Исключение всплывает прямо в `getReportsFromApi`, у которого нет
   собственного `try/catch` вокруг вызова.
10. **Ветка (б) — ответ получен без исключения, но не в ожидаемой форме.**
    `CustomDioClient.call` не бросает исключение, если HTTP-ответ 2xx: если
    тело — `Map<String, dynamic>` без ключей `data`/`animal_exits` и без
    явного `response.data['status'] == 'error'` (либо тело вообще не `Map` —
    пустое, список, скаляр), `call` возвращает `{"data": response.data, "status": "1"}`
    (принудительно «успешный» статус, не связанный с реальным содержимым);
    если же явно `status: 'error'` без `data`/`animal_exits` — возвращает тело
    как есть. В обоих под-случаях результирующая карта не содержит ключа
    `animal_exits`. Назад в `getReportsFromApi`: `(response['animal_exits'] as List)` —
    обращение к отсутствующему ключу даёт `null`, `null as List` бросает
    `TypeError` **внутри** `getReportsFromApi`, уже после того, как
    `CustomDioClient.call` благополучно завершился без исключения и без единой
    записи в лог (ни `Talker`, ни что-либо ещё). Тот же итоговый эффект (тот
    же непойманный `TypeError`) наступает и если `animal_exits` присутствует,
    но хотя бы один элемент не проходит через `_fromJson` без ошибок
    (например `DateTime.parse(json['way_date'])` получает `null` или
    нераспознаваемую строку) — исключение возникает чуть позже, внутри
    `.map((e) => _fromJson(e))`, но так же без собственного перехвата.
11. В обеих ветках (9) и (10) исключение всплывает из `getReportsFromApi`
    дальше — из `loadShtp` (без `try/catch`), дальше — из `updateAndSyncSHTP`
    (без `try/catch` на месте вызова `loadShtp`), дальше — из `_syncAuthData`
    (вызывает `updateAndSyncSHTP` без `try/catch`) — и достигает единственного
    внешнего `try/catch` всего прохода, `on<DataUpdateStartAll>`.
12. `catch (error, stackTrace)`: `getIt<Talker>().error('Возникла при
    обновлении данных $error $stackTrace')` — для ветки (б) это единственная
    запись в лог вообще; для ветки (а) — уже вторая (первая была внутри
    `CustomDioClient.call`). Затем `await _emitError(emit: emit, error: error, stackTrace: stackTrace)`.
13. `_emitError` → `_addDataUpdateError(dataCategory: _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')` —
    пишет строку в `DataUpdates`. Поскольку последним вызовом `_emitProgress`
    с ненулевым `dataCategory` перед сбоем был именно шаг 7 (`loadShtp`,
    `DataCategory.reports`/`DataKey.reports`), эта запись **точно** указывает
    на «отчёты» — в отличие от pull-сбоев Movement/Disposal/Vaccination (см.
    «Бизнес-правила»). Затем эмитится `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'reports', errorMessage: ...)`.
14. `finally` в `on<DataUpdateStartAll>` выполняется независимо от исхода:
    `resetClient('farm_rpc')`, `resetClient('r3_rpc')`.
15. Пользователь видит экран `DataUpdatePage` (открыт автоматически по
    `DataUpdateInProgress` через `BlocListener<DataUpdateBloc, DataUpdateState>`
    в `main_page.dart`) в состоянии ошибки: `_Body.build`, ветка
    `state is DataUpdateFailure` → `tr('an_error_data')` + `tr('reports')` =
    «Произошла ошибка при обработке данных\nОтчеты» — оба ключа реально
    переведены (см. «Бизнес-правила» — контраст с `syncSettings` у Disposal).
    Две кнопки: «Попробовать снова» (`DataUpdateStartAll(again: true, showDataUpdatePage: false)`)
    и «На главную» (`Navigator.pop` + `context.go(Routes.mainNavigator)`, без
    повторной попытки).
16. К этому моменту, независимо от того, какая ветка сработала и что было в
    `unsentReportAnimals` на шаге 3: таблица `ReportAnimals` пуста (шаг 5 уже
    выполнился), ни одной строки `UnsentReportAnimals` с `readyToSend == true`
    не осталось (шаг 6 уже выполнился) — если до сбоя пользователь не начал
    новую сессию сканирования, **ни в одной из двух таблиц ENT-17 не осталось
    ни одной строки**. Экраны, читающие их напрямую
    (`UnsentInventoriesCubit.load`, `InventoryReportDetailsCubit.load`,
    `OperationsCubit`, `MainNavigatorCubit`, `ReportsDayDataLoader`) не
    проверяют «был ли последний sync успешен» и покажут пустой
    список/нулевые счётчики без какого-либо индикатора, что данные не
    отсутствуют, а временно недоступны из-за отказа этого шага.
17. Если пользователь жмёт «Попробовать снова» (шаг 15) — новый проход
    `DataUpdateStartAll(again: true)`. На этом новом проходе
    `updateAndSyncRegagro` читает `dataUpdates = await _dataUpdatesRepository.getAll()`,
    включающий строку, добавленную шагом 13 (`dataCategoryId: reports`,
    `isError == true`). Поскольку `event.again == true`, условие
    `(event.again || dataUpdates.length < _totalDataUpdatesCount || errorDataUpdates.isNotEmpty)`
    истинно уже по одному этому флагу; а поскольку `errorDataUpdates.isNotEmpty`
    тоже истинно — выполняется дополнительная ветка: `_emitProgress(dataKey: 'reloading_data_update')`,
    повторная проверка сети, `await Future.delayed(const Duration(seconds: 15))`,
    и только затем `await _syncAllData(event, emit)` — **полный** пересинк
    (`_clearDataUpdates()` → `loadUser` → `syncAllUnsentAnimals` → settings →
    movements → disposals → `_syncEditedAnimals` → `loadAnimals` →
    vaccinations), ни один шаг которого структурно не связан с
    инвентаризацией, и который сам стирает **всю** таблицу `DataUpdates`
    (`_clearDataUpdates()` в самом начале), включая строку об этом самом
    отказе. Только после того, как `_syncAllData`/`updateAndSyncRegagro`
    вернутся без исключения, `_syncAuthData` того же нового прохода снова
    доходит до `updateAndSyncSHTP` — повторная попытка именно пул-шага
    инвентаризации гарантированно откладывается минимум на 15 секунд и на
    полный пересинк всех остальных сущностей `ANIMAL`, не связанных с этим
    отказом.
18. Если на повторной попытке `getReportsFromApi` завершается успешно —
    `ReportAnimals` заново заполняется (`insertAll`) окном «последний год —
    завтра», `_addDataUpdateSuccess(DataCategory.reports)` пишет строку
    успеха, `DataUpdateSuccess` эмитится (если остальные независимые шаги
    прохода тоже не отказали) — локальный разрыв закрывается. Если отказывает
    снова — цикл шагов 8–17 повторяется целиком.

### Альтернативные потоки

- **Push-шаг (`_unsentReportsRepository.sync`, шаг 4) сам бросает техническое
  исключение.** У `sync()` тоже нет собственного `try/catch`
  (`lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart`) —
  исключение возникает **до** шагов 5/6 (`clear()`/`deleteAllReadyToSend()`
  ещё не выполнены), поэтому в этой альтернативе локальные данные ENT-17 не
  теряются вовсе: подтверждено тестом `'сетевое исключение -> единственный
  безопасный путь: deleteAllReadyToSend() не достигается, данные сохранены'`
  (`test/repositories/unsent_report_animals_repository_test.dart`, группа
  `'UC-126 — ...'`, старая нумерация). Отдельный, не документируемый этим
  файлом сценарий (собственный `CREATE_ERROR` для
  [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)).
- **Push-шаг завершается «логическим» отказом сервера без исключения**
  (`response['status'] == 'error'`, HTTP 200) — `sync()` этого не замечает
  (не проверяет тело ответа), выполнение доходит до шагов 5/6 так же, как при
  реальном успехе push (подтверждено тестом `'логический отказ сервера (200
  OK, тело с ошибкой) -> sync() его не замечает -> deleteAllReadyToSend()
  всё равно выполняется...'`, группа `'UC-126 — ...'`, тот же файл, старая
  нумерация) — этот сценарий (READ_ERROR пула) наступает после этого
  одинаково, независимо от того, принял ли сервер push по содержанию.
- **`unsentReportAnimals` пуст на шаге 3** (пользователь не завершал новых
  сессий с прошлого прохода) — `sync()` не вызывается вовсе (`if (unsentReportAnimals.isNotEmpty)`),
  но шаги 5/6 (`clear()`/`deleteAllReadyToSend()`) всё равно выполняются
  безусловно — этот сценарий (отказ пула) достижим и на проходе, где
  пользователь не отправлял ничего нового.
- **Источник исключения внутри ветки (б) — приведение верхнего уровня против
  разбора одного элемента.** Оба источника (`(response['animal_exits'] as List)`
  и построчный `_fromJson`) неотличимы друг от друга на уровне кода (одна и
  та же непойманная область без ветвления) и приводят к одинаковому исходу;
  не разнесены на отдельные use-case, как и в аналогичном месте у Disposal
  ([UC-108](UC-108-ACTOR-4-EVT-54-ENT-16-READ_ERROR-IN-ANIMAL.md)).
- **`REJECTED`-ветки не существует.** Осознанный отказ сервера (явный
  `status: 'error'` в ответе на `GET .../get-animal-exits`) и «мусорный»
  2xx-ответ без ожидаемых ключей проходят через одну и ту же точку отказа —
  отсутствие ключа `animal_exits` в обоих случаях → один и тот же `TypeError`
  на приведении к `List`. Нет кода, который различал бы «сервер осознанно
  отказал» и «ответ просто не в ожидаемой форме» — оба видны пользователю как
  один и тот же `READ_ERROR`.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — сущность сегмента `ENT` в id: обе физические
  таблицы уже опустошены (шаги 5/6) к моменту отказа пула; `ReportAnimals`
  не получает ни одной новой строки (`insertAll` не достигается),
  `UnsentReportAnimals.readyToSend` не восстанавливается никак — единственный
  путь наполнить их заново — успешный пул на будущем проходе (шаг 18) или
  запись новой сессии сканирования пользователем.
- `DataUpdates` (журнал sync-прохода, специфицируется будущим модулем
  `SYSTEM`) — получает ровно одну новую строку об этом отказе
  (`dataCategoryId: DataCategory.reports`, `errorDataKey: 'reports'`), которая
  на следующем полном проходе прочитывается `updateAndSyncRegagro` как часть
  `errorDataUpdates` и форсирует полный `_syncAllData()` с 15-секундной
  задержкой прежде, чем этот же пул-шаг будет предпринят повторно (шаг 17).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не пишется этим конкретным шагом вовсе (в отличие от предшествующего
  push-шага, `sync()`, который читает `AnimalsRepository.getAllAnimalsWithDetailsByFilters`/`getAllLocalAnimalsWithDetailsByFilters`
  для резолва `animal_id` payload'а) — сопоставление метка↔животное для уже
  полученных (в прошлом, до этого отказа) строк `ReportAnimals` целиком
  вычисляется на клиенте позже, при отображении, не на этом шаге.

### Бизнес-правила

- **Разрушительная подготовка безусловна и не зависит от исхода пула.**
  `clear()`/`deleteAllReadyToSend()` выполняются строго **до** сетевого
  вызова, которым можно было бы восстановить кэш, и независимо от того, было
  ли что отправлять — отказ этого шага достижим на **любом** авторизованном
  проходе, не только на том, где пользователь недавно завершил инвентаризацию.
- **Пул-шаг инвентаризации не разделяет «умный» гейт остальных сущностей
  ANIMAL.** `updateAndSyncSHTP` вызывается из `_syncAuthData` безусловно,
  сразу после `updateAndSyncRegagro`, независимо от того, что решил сделать
  `updateAndSyncRegagro` (тот, в свою очередь, запускает `_syncAllData` —
  Movement/Disposal/Vaccination/Animals — только при `event.again ||
  dataUpdates.length < _totalDataUpdatesCount || errorDataUpdates.isNotEmpty`
  либо `event.fullUpdate`). Реальный полный пропуск синхронизации остальных
  сущностей возможен (когда ни одно из этих условий не истинно); пул отчётов
  инвентаризации всё равно выполняется на каждом таком проходе.
- **Обе технически различные ветки отказа (а/б) сходятся в одном и том же
  наблюдаемом результате.** `READ_ERROR`, тот же `DataUpdateFailure`, та же
  запись в `DataUpdates` — разница только в том, залогирован ли отказ дважды
  (ветка а — `CustomDioClient.call` + внешний `catch`) или один раз (ветка б —
  только внешний `catch`); никакого пользовательского или бизнес-различия
  между ними нет.
- **Атрибуция ошибки здесь точна — контраст с соседними pull-сбоями той же
  под-области ANIMAL.** В отличие от Disposal ([UC-108](UC-108-ACTOR-4-EVT-54-ENT-16-READ_ERROR-IN-ANIMAL.md))
  и Vaccination ([UC-76](UC-76-ACTOR-4-EVT-38-ENT-14-READ_ERROR-IN-ANIMAL.md)),
  чьи собственные pull-методы не вызывают `_emitProgress` перед своим сетевым
  вызовом (и потому наследуют устаревший, не относящийся к делу ключ на
  момент отказа — у Disposal это буквально нетранслированная строка
  `syncSettings`), `loadShtp` вызывает собственный
  `_emitProgress(dataKey: DataKey.reports, dataCategory: DataCategory.reports)`
  непосредственно перед сетевым вызовом — ошибка атрибутируется точно, и оба
  ключа (`an_error_data`, `reports`) резолвятся в реальный переведённый текст
  и в `app_ru.arb`/`app_en.arb`, и в `AppLocalizations.tr` — пользователь
  реально читает связный (пусть и общий) текст ошибки, а не служебный ключ.
- **`REJECTED` структурно недостижим** — см. «Альтернативные потоки».
- **Стоимость повторной попытки шире, чем сам отказ.** Кнопка «Попробовать
  снова» перезапускает не точечно этот шаг, а форсирует (через оставленную
  строку `DataUpdates` и/или флаг `again: true`) 15-секундную задержку и
  полный `_syncAllData()` (Movement/Disposal/Vaccination/Animals/настройки) —
  прежде чем пул отчётов инвентаризации будет предпринят повторно в том же
  проходе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе ветки отказа (техническое исключение
транспорта и исключение разбора ответа без предшествующего исключения)
воспроизводятся статическим чтением кода целиком: `DataUpdateBloc.updateAndSyncSHTP`
→ `loadShtp` → `ReportAnimalsRepository.getReportsFromApi` →
`CustomDioClient.call`/`DioClient`. Возможное исправление (например,
собственный `try/catch` вокруг пула, отдельный от push, либо перенос
`clear()`/`deleteAllReadyToSend()` после успешного пула вместо до) в рамках
этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственная внешняя `try/catch`/`finally`-граница всего прохода; ловит исключение отовсюду ниже, вызывает `_emitError`, `finally` сбрасывает оба `ApiClient` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncSHTP` без собственного `try/catch`, безусловно, сразу после `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP` | CURRENT | push (если непусто) → безусловные `clear()`/`deleteAllReadyToSend()` → `loadShtp` — предмет этого сценария |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadShtp` | CURRENT | вызывает `getReportsFromApi` без `try/catch`; собственный `_emitProgress(DataKey.reports/DataCategory.reports)` непосредственно перед сбоем |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | на следующем полном проходе видит оставленную этим сценарием строку `DataUpdates` (`dataCategoryId: reports`) как `errorDataUpdates`, форсирует ветку с 15-секундной задержкой и `_syncAllData` ещё до повторной попытки этого шага |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | `await _clearDataUpdates()` в начале стирает всю таблицу `DataUpdates`, включая строку об этом отказе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `_addDataUpdateError`, `_emitProgress` | CURRENT | пишут строку в `DataUpdates` и формируют `DataUpdateFailure.errorMessageKey` из `_currentDataKey` |
| `lib/pages/report/report_animals_repository.dart` | `ReportAnimalsRepository.getReportsFromApi`, `._fromJson` | CURRENT | ядро сценария — сетевой вызов без `try/catch`, приведение `response['animal_exits'] as List`, поэлементный разбор |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear`, `.insertAll` | CURRENT | `dao.clear()`/`dao.insAll()`, используемые `ReportAnimalsRepository` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` | CURRENT | `delete(_currentTableInfo).go()` — безусловное удаление всех строк таблицы |
| `packages/sheep_farm_database/lib/entities/reports_animals/report_animals.dart` | `ReportAnimals`, `ReportAnimal` | CURRENT | таблица/модель, полностью очищаемая шагом 5 и не заполняемая при сбое пула |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getAllReadyToSend`, `.sync`, `.deleteAllReadyToSend` | CURRENT | предшествующий push-шаг ([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)); `deleteAllReadyToSend` выполняется безусловно до вызова `loadShtp` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | транспорт; ветка (а) — логирует через `Talker.error` и `rethrow`; ветка (б) — не бросает исключение, нормализует статус, но не гарантирует наличие ожидаемых ключей ответа |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — любой не-2xx ответ уже становится исключением Dio до входа в `CustomDioClient.call` |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory.reports`, `DataKey.reports`, `DataUpdates`, `DataUpdateExtension.isError` | CURRENT | категория/ключ, под которым фиксируется именно этот отказ |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` (ветка `case 'reports'`) | CURRENT | переводит `errorMessageKey` в «Отчеты» — контраст с [UC-108](UC-108-ACTOR-4-EVT-54-ENT-16-READ_ERROR-IN-ANIMAL.md) (ключ `syncSettings` без своего `case`) |
| `lib/l10n/app_ru.arb` | ключи `reports`, `an_error_data` | CURRENT | реальные переводы, использованные экраном ошибки |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdatePage`, `_Body.build` (ветка `DataUpdateFailure`), `DataUpdateInProgressWidget` | CURRENT | экран ошибки; кнопки «Попробовать снова» (`DataUpdateStartAll(again: true)`) / «На главную» |
| `lib/pages/main/main_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` (ветка `DataUpdateInProgress` → `DataUpdatePage.show`) | CURRENT | точка входа показа экрана обновления/ошибки |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | читает `UnsentReportAnimalsRepository` напрямую — покажет пустой хаб после этого отказа |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | читает обе таблицы ENT-17 напрямую — покажет пустой отчёт после этого отказа |
| `lib/pages/animal_operations/cubit/operations/operations_cubit.dart` | `OperationsCubit` (`_readingsRepository`) | CURRENT | читает `ReportAnimalsRepository` напрямую |
| `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` | `MainNavigatorCubit` (`_reportsRepository.getReportsByFarmId`) | CURRENT | читает `ReportAnimalsRepository` напрямую — влияет на счётчики навигации |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader` | CURRENT | читает обе таблицы ENT-17 напрямую для посуточных отчётов |
| `test/repositories/unsent_report_animals_repository_test.dart` | группы `'UC-125 — ...'`/`'UC-126 — ...'`/`'UC-126 — ...'` (старая нумерация) | CURRENT | покрывают push-шаг ([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)), не пул — см. «Связанные тесты» |
| `test/blocs/data_update_bloc_test.dart` | (весь файл, комментарий над `void main()`) | CURRENT | документирует, что `DataUpdateStartAll` не покрыт юнит-тестом вовсе |

## Критерии приёмки

- При авторизованном пользователе, после того как push-шаг
  `unsentReportAnimals` (если был) завершился без исключения, и после того
  как `_reportsRepository.clear()`/`_unsentReportsRepository.deleteAllReadyToSend()`
  уже выполнились, если `ReportAnimalsRepository.getReportsFromApi()` — сам
  сетевой вызов либо последующий разбор ответа — бросает исключение любого
  рода, оно не перехватывается ни в `getReportsFromApi`, ни в `loadShtp`, ни в
  `updateAndSyncSHTP`, ни в `_syncAuthData`.
- Исключение достигает `catch` в `on<DataUpdateStartAll>`, который пишет
  строку в `DataUpdates` с `dataCategoryId == DataCategory.reports`,
  `errorDataKey == 'reports'`, и эмитит `DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'reports')`.
- К моменту показа этой ошибки таблица `ReportAnimals` пуста (очищена шагом
  5, не восстановлена), и ни одной строки `UnsentReportAnimals` с
  `readyToSend == true` не осталось — независимо от того, что содержал батч
  на входе в `updateAndSyncSHTP`.
- Оба ключа локализации (`an_error_data`, `reports`) резолвятся в реальный
  переведённый текст и в `.arb`-файлах, и в `AppLocalizations.tr`, а не в
  нетранслированную строку по умолчанию.
- Весь sync-проход завершается `DataUpdateFailure`, не `DataUpdateSuccess`;
  шаг `_emitProgress(dataKey: DataKey.syncDevices)`/`_suncDevices()`,
  следующий за `updateAndSyncSHTP` в `_syncAuthData`, в этом проходе не
  выполняется.
- На следующем полном проходе (в т.ч. по кнопке «Попробовать снова»,
  `DataUpdateStartAll(again: true)`) строка `DataUpdates`, оставленная этим
  сценарием, заставляет `updateAndSyncRegagro` выполнить ветку с
  `Future.delayed(const Duration(seconds: 15))` и полным `_syncAllData()`
  (который сам стирает всю таблицу `DataUpdates`, включая эту строку) прежде,
  чем `_syncAuthData` того же прохода снова дойдёт до повторной попытки
  `updateAndSyncSHTP`.

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` прямым текстом
документирует (комментарий над `void main()`), что `DataUpdateStartAll` (по
собственной оценке файла — «~900 из 1013 строк файла… основной sync
pipeline») не покрыт юнит-тестом: первая же строка обработчика — реальный
DNS-запрос без DI-точки, дальше десятки приватных методов и реальные
транзакции `AppDatabase`; сам файл содержит только два теста — конструктор
`DataUpdateBloc` и обработчик `DataUpdateClear`, ни один не доходит до
`_syncAuthData`/`updateAndSyncSHTP`.

`test/repositories/unsent_report_animals_repository_test.dart` воспроизводит
(через собственный вспомогательный `_runSyncPipeline`, чей комментарий прямо
ссылается на `lib/blocs/data_update/data_update_bloc.dart:245-263`) ровно ту
оркестрацию, что `updateAndSyncSHTP` делает вокруг push-репозитория —
`getAllReadyToSend()` → `sync()` → `deleteAllReadyToSend()` — тремя тестами:

- группа `'UC-125 — UnsentReportAnimalsRepository.sync (успех)'` —
  успешный push;
- группа `'UC-126 — UnsentReportAnimalsRepository.sync (приоритет №1 дефект —
  потеря данных)'` — логический отказ сервера (200 OK, тело с ошибкой), не
  замечаемый `sync()`;
- группа `'UC-126 — UnsentReportAnimalsRepository.sync (сетевое исключение —
  данные сохранены)'` — техническое исключение push, данные не теряются.

Все три теста (старая нумерация, не переименовывается этим проходом)
покрывают push-шаг ([EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)),
не пул — ни один из них не вызывает `_reportsRepository.clear()`,
`loadShtp()` или `getReportsFromApi()`; сценарий этого файла (`READ_ERROR`
пула, [EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md))
не покрыт вовсе. Отдельного тестового файла для `ReportAnimalsRepository` в
репозитории нет.

## Открытые вопросы и ограничения

- **Четыре структурно однотипных pull-шага (Movement/Vaccination/Disposal/
  инвентаризация) реализуют четыре разных сочетания «глотать ли исключение» ×
  «чистить ли локальные данные заранее» × «эмитить ли собственный,
  относящийся к делу progress-ключ перед сбоем».** Movement глотает
  исключение и не трогает локальные данные; Vaccination пробрасывает
  исключение и безусловно стирает локальные данные до попытки пула;
  Disposal пробрасывает исключение, но не стирает данные заранее;
  инвентаризация (этот файл) пробрасывает исключение, безусловно стирает
  локальные данные **обеих** своих таблиц заранее (шире, чем Vaccination —
  там стирается одна таблица), но единственная из четырёх — сама эмитит
  точный progress-ключ перед своим сетевым вызовом. Не проверялось, является
  ли именно это сочетание для инвентаризации осознанным решением или
  случайным следствием того, что `loadShtp` изначально нуждался в
  собственном `_emitProgress` для отображения прогресса (а не для точной
  атрибуции ошибки) и точность атрибуции — побочный, не целенаправленный
  эффект.
- **Стоимость повторной попытки не ограничена самим отказавшим шагом.**
  Оставленная этим сценарием строка `DataUpdates` (и/или флаг `again: true`)
  форсирует на следующем проходе полный `_syncAllData()`
  (Movement/Disposal/Vaccination/Animals/настройки) с 15-секундной задержкой,
  прежде чем инвентаризация будет предпринята повторно — не проверялось,
  является ли этот более широкий радиус повтора осознанным общим
  проектным решением ретрая всего прохода (`SYSTEM`, вне рамок этого файла,
  см. [MOD-4](../modules/MOD-4-ANIMAL.md), «Граница») или непреднамеренным
  побочным эффектом того, что `errorDataUpdates` не различает, к какой
  именно сущности относится оставленная ошибка.
- **Полная локальная потеря данных инвентаризации не ограничена по времени.**
  Пока проход, доходящий до успешного `getReportsFromApi`, не выполнится
  (пользователь может закрыть `DataUpdatePage` кнопкой «На главную» и не
  повторять попытку сколь угодно долго), ни одна из читающих обе таблицы
  ENT-17 страниц не покажет пользователю никакого предупреждения о том, что
  видимая пустота — следствие отказа синхронизации, а не факт отсутствия
  данных.
- Не проверено эмпирически на реальном запуске — вывод сделан статическим
  чтением кода (`updateAndSyncSHTP` → `loadShtp` →
  `ReportAnimalsRepository.getReportsFromApi` → `CustomDioClient.call` →
  `DioClient`), включая точную форму ответа, необходимую для ветки (б)
  (`Map` без `data`/`animal_exits`, либо не-`Map` тело) — реальный контракт
  `GET .../get-animal-exits` со стороны сервера этой спекой не верифицирован.
