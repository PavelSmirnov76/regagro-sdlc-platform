# UC-76 — Система не может перезагрузить список вакцинаций с сервера при полном sync-проходе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь —
после трёх push-шагов вакцинации (delete/update/create) — система пытается
забрать с сервера актуальный список вакцинаций и перезаписать им локальную
таблицу `Vaccinations`. Этот файл — сценарий, в котором именно этот запрос
(`GET .../vaccinations`) не может быть выполнен: исключение не логируется и
проглатывается, как в аналогичном pull-шаге перемещений, а **пробрасывается
наружу** и прерывает весь sync-проход целиком.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода (`DataUpdateBloc`), без участия пользователя в момент
именно этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`); проверка сети уже пройдена
   успешно, `_authRepository.isAuthorized()` истинно, и выполнение дошло до
   `_syncAllData` через `_syncAuthData` → `updateAndSyncRegagro` (см.
   [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md), «Основной
   поток», шаги 1–3 — тот же путь до этой точки, здесь не повторяется).
2. `_syncAllData` доходит до **последнего** вызова в своём теле —
   `await _vaccinationsRepository.syncVaccinations(true)` — уже после
   `_movementReportRepository.syncMovements()`, `_disposalRepository.syncDisposals()`,
   `_syncEditedAnimals()` и `loadAnimals(event, emit)`. Единственный вызов
   `syncVaccinations` в кодовой базе — этот, всегда с `isFullSync: true`;
   `isDeleteErrors` нигде не передаётся и остаётся `false` по умолчанию.
3. Т.к. `isFullSync == true`, `syncVaccinations` сперва выполняет по порядку
   `_deleteVaccinationFromApi()`, `_updateVaccinationFromApi()`,
   `_sendVaccinationsToApi()` — все три push-шага перехватывают исключение
   внутри себя и **не** пробрасывают его (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
   «Инварианты»); поэтому push-часть не предмет этого файла и не прерывает
   поток независимо от своего исхода.
4. `syncVaccinations` считывает **весь** текущий набор ещё не
   синхронизированных строк в память: `_getNotSyncVaccinations()` →
   `dao.getNotSyncVaccinations()` (фильтр `sync == false`, без разбора трёх
   под-состояний — новая/правка/удаление).
5. `await dao.clear()` — **безусловно** удаляет вообще все строки таблицы
   `Vaccinations` (и уже синхронизированные, и ещё не отправленные), без
   какого-либо условия на успех последующего шага. Это отличает данный
   сценарий от Movement ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)):
   там `dao.clear()` вызывается **после** успешного получения непустого
   ответа; здесь — **до** попытки его получить.
6. `await _getVaccinationsFromApi()` — предмет этого use-case. Метод строит
   постраничный опрос `ApiMessage(link:
   '${Constants.registrationServiceApi}/vaccinations', method:
   ApiMethod.get, data: {"page": page, "per_page": perPage})` через
   `paginatedRequestHandler` (постранично, `perPage: 500`, накопление всех
   страниц в память в `allVaccinations`, вставка в БД — отдельным циклом
   **после** того, как вся пагинация завершится).
7. Исключение возникает в одной из двух точек:
   - внутри `_fetchVaccinationsPage` — либо сетевой сбой самого вызова
     `rpcClientSHTP.call(message)`, либо явный `throw
     Exception(response['errors'])`, если сервер вернул непустое поле
     `errors` в ответе на любую страницу;
   - либо (значительно реже) внутри цикла вставки уже накопленных строк,
     если `insert(vaccination.toCompanion())` или
     `_diseasesVaccinationsRepository.saveDiseasesVaccinations(...)` бросят
     исключение для какой-то конкретной строки.
   `paginatedRequestHandler` (`lib/repositories/base_repository.dart`) сам не
   содержит `try/catch` — исключение из `onRequest`/`onResponse`
   пробрасывается как есть.
8. `_getVaccinationsFromApi` перехватывает исключение единственным
   `try/catch` вокруг **обоих** шагов (пагинация + вставка), логирует через
   `getIt<Talker>().info('getVaccinationsFromApi Error: $e st: $st')` и
   **`rethrow`** — в отличие от `getIt<Talker>().error(...)` без `rethrow` у
   Movement.
9. `syncVaccinations` не оборачивает `await _getVaccinationsFromApi()` в
   собственный `try/catch` — исключение продолжает всплывать наружу из
   `syncVaccinations` целиком. Строка `if (!isDeleteErrors)
   dao.insAll(vaccinationsWithErrors);`, которая вернула бы в БД набор,
   считанный на шаге 4, **никогда не выполняется** в этом сценарии.
10. Исключение продолжает всплывать через `_syncAllData` →
    `updateAndSyncRegagro` → `_syncAuthData` (обе эти функции вызывают
    следующий шаг через `await` без собственного `try/catch`, поэтому
    `updateAndSyncSHTP(event, emit)` и `_suncDevices()` — шаги, идущие после
    `updateAndSyncRegagro` внутри `_syncAuthData` — в этом проходе **не
    вызываются вовсе**) — до внешнего `try/catch` в
    `DataUpdateBloc.on<DataUpdateStartAll>` (строки 141–164).
11. Этот внешний `catch` вызывает `_emitError`, которая пишет в
    `DataUpdates`-журнал строку с `dataCategory: _currentDataCategory`,
    `errorDataKey: _currentDataKey`, `errorMessage: 'error: $error,
    stackTrace: $stackTrace'`, и эмитит `DataUpdateFailure(errorTitleKey:
    'an_error_data', errorMessageKey: _currentDataKey, errorMessage: ...)`.
    На момент падения `syncVaccinations` **`_currentDataCategory` и
    `_currentDataKey` не обновлялись явным `_emitProgress` с момента
    `loadAnimals`** (последний явный вызов —
    `_emitProgress(dataKey: DataKey.animals, dataCategory:
    DataCategory.animals)` внутри `loadAnimals`, шаг перед `syncVaccinations`
    в теле `_syncAllData`) — т.е. отказ пуллинга вакцинаций **маркируется в
    журнале и на экране ошибки под ключом `animals`**, а не под каким-либо
    ключом, относящимся к вакцинации: у пути `syncVaccinations` нет
    собственного вызова `_emitProgress` вовсе.
12. `finally`-блок обработчика `on<DataUpdateStartAll>` всё равно выполняется
    (`resetClient` для обоих `ApiClient`-инстансов), независимо от исхода
    `try`.
13. Пользователь на экране `DataUpdatePage` видит общий экран ошибки
    синхронизации (`DataUpdateInProgressWidget(isError: true)`) с текстом
    `tr('an_error_data')` + `tr('animals')` и кнопками «Попробовать снова»
    (`DataUpdateStartAll(again: true)`, что запускает `_syncAllData` заново
    **с самого начала**, а не с шага вакцинации) и «На главную».

### Альтернативные потоки

- **Сбой на конкретной странице пагинации после того, как несколько
  предыдущих страниц уже были успешно получены.** Поскольку вставка в БД
  (`for (var vaccination in allVaccinations) { await insert(...); ... }`)
  выполняется отдельным циклом **после** полного завершения
  `paginatedRequestHandler`, ни одна строка новой пагинации не попадает в БД,
  если сбой произошёл на любой из страниц, — не только на первой. Результат
  идентичен сбою на первой странице.
- **Сбой внутри цикла вставки уже накопленных строк (после успешной
  пагинации).** Реже, чем сетевой сбой, но структурно возможен: если
  `insert()`/`saveDiseasesVaccinations()` бросит исключение на какой-то
  конкретной строке уже после того, как несколько предыдущих строк того же
  вызова уже вставлены — те уже вставленные строки **остаются** в БД (цикл
  не транзакционен, `insert()` вызывается по одной строке за раз, не
  батчем), а необработанный остаток полученного списка и ранее считанный
  `vaccinationsWithErrors` — теряются. Тот же `RESULT` (`READ_ERROR`), не
  отдельный use-case; описан здесь как частный случай этого же кода.
- **Часть трёх push-шагов тоже упала (например, `_sendVaccinationsToApi`
  бросила исключение для какой-то отдельной вакцинации).** Push-шаги
  (`_deleteVaccinationFromApi`/`_updateVaccinationFromApi`) перехватывают
  исключение без `rethrow`; `_sendVaccinationsToApi` перехватывает ошибку
  **на уровне отдельной вакцинации** (`_addErrorsToVaccinations`) и
  перехватывает `rethrow` только на уровне общего внешнего `try/catch`
  метода (если бросит что-то за пределами цикла по вакцинациям, например
  `getNotSyncVaccinationsWithDetails()`). В любом случае это не предмет
  этого файла — этот use-case начинается с того момента, когда push-часть
  уже завершилась (успешно или частично неуспешно, не важно) и выполнение
  дошло до `dao.clear()` + пуллинга.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  единственная сущность, чья локальная таблица физически меняется этим
  шагом: полностью очищается (`dao.clear()`, безусловно, до попытки
  пуллинга), и в этом сценарии **не восстанавливается** — ни новыми данными
  с сервера (запрос не удался), ни прежним содержимым (строка
  `dao.insAll(vaccinationsWithErrors)` не выполняется, т.к. исключение
  пробрасывается раньше неё).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не читается и
  не изменяется этим шагом напрямую; связь только через `animalId` на
  строке `Vaccination`, который в DTO копируется как есть без пересчёта.
  Затрагивается лишь косвенно, если частичная вставка (см. «Альтернативные
  потоки») успела вставить строки, ссылающиеся на существующих локальных
  животных, до того как исключение прервало остаток цикла.
- `DiseasesVaccinations` (связочная таблица болезней вакцинации, не имеет
  собственного `ENT` — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  «Связи») — заполняется построчно внутри того же цикла, что и вставка
  `Vaccination`; при частичной вставке (см. «Альтернативные потоки»)
  окажется в согласованном состоянии только для уже вставленных строк.

### Бизнес-правила

- **Ключевое отличие от pull-а перемещений
  ([EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md),
  [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)).** Там ошибка
  пуллинга перехватывается, логируется через `Talker.error` и полностью
  проглатывается — весь остальной sync-проход (`_disposalRepository.syncDisposals()`,
  `_syncEditedAnimals()`, `loadAnimals`, и в данном случае сам
  `_vaccinationsRepository.syncVaccinations(true)`, идущий следом за
  Movement в `_syncAllData`) продолжается как ни в чём не бывало, и
  `DataUpdateSuccess` всё ещё достижим. Здесь `_getVaccinationsFromApi`
  логирует через `Talker.info` (не `.error`) и делает `rethrow` — исключение
  добирается до общего `try/catch` обработчика `DataUpdateStartAll` и
  **весь** sync-проход завершается `DataUpdateFailure`, независимо от того,
  что все предыдущие шаги (фермы/места/животные/перемещения/выбытия) уже
  успешно синхронизировались в этом же проходе.
- **`dao.clear()` вызывается безусловно, до попытки пуллинга, а не после
  успешного его завершения.** У Movement (`getReportsFromApiAndSave`)
  `clear()`/`insAll()` — условная пара, выполняемая только при непустом
  успешном ответе; у Vaccination `clear()` — первый шаг, ничем не
  обусловленный. Из-за этого сбой пуллинга здесь необратимо стирает
  локальную таблицу **целиком**, включая все ранее синхронизированные
  строки, — тогда как у Movement сбой пуллинга оставляет локальные данные
  нетронутыми.
- **Механизм «не терять неотправленные строки» ([ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  «Инварианты») работает только при успешном пуллинге.** Строки, прочитанные
  в `vaccinationsWithErrors` на шаге 4 (весь набор с `sync == false` —
  новые/в правке/в удалении, включая записи с текстом ошибки от неудачного
  push), возвращаются в БД строкой `dao.insAll(vaccinationsWithErrors)`
  **только если** `_getVaccinationsFromApi()` не бросила исключение. В этом
  сценарии — бросает, и эта строка недостижима: неотправленные записи,
  прочитанные в память, теряются вместе с уже синхронизированными.
- **Экран ошибки маркируется под ключом `animals`, не под ключом,
  относящимся к вакцинации.** У пути `_vaccinationsRepository.syncVaccinations(true)`
  внутри `_syncAllData` нет собственного вызова `_emitProgress` — последним
  перед ним отработал `loadAnimals`, установивший `_currentDataCategory =
  DataCategory.animals` и `_currentDataKey = DataKey.animals`. Пользователь
  и журнал `DataUpdates` видят отказ, подписанный как относящийся к
  животным, хотя фактическая причина — отказ шага вакцинаций.
- **Отказ пуллинга вакцинаций рвёт остаток `_syncAuthData`.** Поскольку
  `_syncAllData`/`updateAndSyncRegagro`/`_syncAuthData` вызывают друг друга
  через `await` без собственных `try/catch`, шаги `updateAndSyncSHTP(event,
  emit)` и `_suncDevices()` (синхронизация SHTP-данных и настроек
  сканирующих устройств), идущие в `_syncAuthData` **после**
  `updateAndSyncRegagro`, в этом проходе не выполняются вовсе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (включая путь ошибки) полностью реализован
существующим кодом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешняя проверка сети + `try/catch`-граница всего sync-прохода; ловит проброшенное исключение, вызывает `_emitError` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `updateAndSyncRegagro`; при исключении из него не доходит до `updateAndSyncSHTP`/`_suncDevices` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, вызывать ли `_syncAllData` в этом проходе; при исключении из `_syncAllData` не выполняет ничего после вызова |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | последний вызов в теле — `_vaccinationsRepository.syncVaccinations(true)`, после `syncMovements`/`syncDisposals`/`_syncEditedAnimals`/`loadAnimals` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | последний явный `_emitProgress(dataKey: DataKey.animals, dataCategory: DataCategory.animals)` перед вызовом `syncVaccinations` — источник ошибочной маркировки экрана ошибки |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError` | CURRENT | пишет `DataUpdates`-запись об ошибке и эмитит `DataUpdateFailure`, используя `_currentDataCategory`/`_currentDataKey`, оставшиеся от `loadAnimals` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: push (delete/update/create) → чтение неотправленных в память → `dao.clear()` безусловно → pull (`_getVaccinationsFromApi`) → условный возврат неотправленных, недостижимый при исключении |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getVaccinationsFromApi` | CURRENT | ядро этого сценария: постраничный `GET`, `Talker.info` + `rethrow` при любом исключении |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._fetchVaccinationsPage` | CURRENT | одна страница; бросает `Exception(response['errors'])`, если сервер вернул непустое поле `errors` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getNotSyncVaccinations` | CURRENT | считывает весь набор `sync == false` в память до `dao.clear()` |
| `lib/repositories/base_repository.dart` | `BaseRepository.paginatedRequestHandler` | CURRENT | без собственного `try/catch` — пробрасывает любое исключение `onRequest`/`onResponse` как есть |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll`, `BaseDao.clearAndInsertAll` | CURRENT | `clear()` — безусловное `delete` всех строк без фильтра; `clearAndInsertAll` (транзакционный) существует, но здесь не используется — `clear()` и последующая логика вызываются раздельно, не одной транзакцией |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDtoMapper.toCompanion` | CURRENT | маппинг серверного JSON в `VaccinationsCompanion` (используется только для строк, успевших дойти до вставки при частичном сбое) |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | фильтр `sync == false`, без разбора трёх под-состояний |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataKey.animals`, `DataCategory.animals`, `DataUpdates.isError` | CURRENT | ключ, под которым ошибка пуллинга вакцинаций маркируется в журнале/на экране (см. «Бизнес-правила») |
| `lib/pages/data_update/data_update_page.dart` | `_Body.build` (ветка `DataUpdateFailure`), `DataUpdateInProgressWidget` | CURRENT | UI общего экрана ошибки синхронизации: `tr(errorTitleKey)` + `tr(errorMessageKey)`, кнопки «Попробовать снова» / «На главную» |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL, к которому добавляется путь `/vaccinations` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |

## Критерии приёмки

- При авторизованном пользователе, после успешной проверки сети и после
  завершения трёх push-шагов вакцинации (`_deleteVaccinationFromApi`,
  `_updateVaccinationFromApi`, `_sendVaccinationsToApi` — независимо от их
  собственного исхода, т.к. они не пробрасывают исключения), локальная
  таблица `Vaccinations` **безусловно** полностью очищается (`dao.clear()`)
  **до** попытки запросить `GET .../vaccinations`.
- Если запрос `GET .../vaccinations` (на любой странице) либо
  постобработка полученных строк бросают исключение, оно логируется через
  `Talker.info` и **пробрасывается наружу** из `_getVaccinationsFromApi` и
  из `syncVaccinations` — в отличие от аналогичного пуллинга перемещений.
- В этом случае строка `dao.insAll(vaccinationsWithErrors)`, которая вернула
  бы в БД набор ещё не синхронизированных вакцинаций, прочитанный до
  `dao.clear()`, **не выполняется** — локальная таблица `Vaccinations`
  остаётся пустой (либо содержит только те строки нового ответа, что успели
  вставиться до сбоя, если сбой произошёл в цикле вставки, а не в
  пагинации).
- Исключение продолжает всплывать через `_syncAllData` →
  `updateAndSyncRegagro` → `_syncAuthData` — шаги `updateAndSyncSHTP` и
  `_suncDevices`, идущие в `_syncAuthData` после `updateAndSyncRegagro`, в
  этом проходе не выполняются.
- Весь sync-проход завершается `DataUpdateFailure` (не `DataUpdateSuccess`),
  и `errorMessageKey` этого состояния равен `DataKey.animals` (последнему
  ключу, установленному `_emitProgress` перед этим шагом в `loadAnimals`),
  а не какому-либо ключу, специфичному для вакцинации.
- Пользователь видит общий экран ошибки синхронизации с кнопками
  «Попробовать снова» (перезапускает `_syncAllData` полностью заново, не с
  шага вакцинации) и «На главную».

## Связанные тесты

TBD — теста нет. `test/repositories/vaccinations_repository_test.dart`
покрывает только сбой трёх push-шагов вакцинации — группы `'UC-72 —
VaccinationsRepository.syncVaccinations(isFullSync: true) — edit push'` (PUT
падает) и `'UC-70 — VaccinationsRepository.syncVaccinations(isFullSync:
true) — delete push'` (DELETE падает); ни разу в этом файле мок
`farmRpcClient.call` не настроен бросать исключение на `ApiMethod.get` — сам
пуллинг (`_getVaccinationsFromApi`), предмет этого файла, нигде не
тестируется ни на успех, ни на ошибку. Групповые имена `UC-94`/`UC-100`,
процитированные выше, принадлежат другой, ещё не написанной паре use-case
файлов (push edit/delete), не этому файлу — они не являются ссылками на
`UC-76`. Ветка `_vaccinationsRepository.syncVaccinations(true)` в
`data_update_bloc_test.dart` также не найдена — `VaccinationsRepository`
фигурирует там (если фигурирует) только как замоканная зависимость для
конструирования `DataUpdateBloc`, без вызова `syncVaccinations` в тестовых
сценариях.

## Открытые вопросы и ограничения

- **Потеря локальных данных при сбое пуллинга — самое серьёзное расхождение
  с Movement.** У Movement сбой пуллинга не трогает локальные данные вовсе;
  здесь `dao.clear()` уже выполнен безусловно до попытки пуллинга, и при её
  неудаче ни новые данные с сервера, ни прежнее содержимое (включая
  прочитанные в память ещё не синхронизированные записи с текстом ошибки
  push) не возвращаются в таблицу — `dao.insAll(vaccinationsWithErrors)`
  недостижим. Не проверялось на реальном проде, насколько часто эта ветка
  реализуется (частота сетевых сбоев именно на этом шаге), но код
  однозначно допускает полную потерю локальной истории вакцинаций одного
  неудачного sync-прохода.
- **Пользователь не получает точного диагноза.** Экран ошибки показывает
  общий ключ `animals`, унаследованный от `loadAnimals` — ничто в UI не
  указывает, что именно шаг вакцинации оказался причиной сбоя, и тем более
  ничто не предупреждает, что локальный список вакцинаций уже опустошён на
  момент показа этого экрана.
- **`clear()` не атомарен с последующим пуллингом+вставкой.** Транзакционный
  `BaseDao.clearAndInsertAll` существует в кодовой базе и не используется
  здесь; даже без сетевого сбоя аварийное завершение процесса между
  `dao.clear()` и последующей вставкой оставило бы таблицу `Vaccinations`
  пустой — не проверялось, насколько это окно реалистично достижимо на
  практике отдельно от сценария этого файла.
- **Частичная вставка при сбое в середине цикла (см. «Альтернативные
  потоки»)** — код допускает состояние, где часть новых серверных строк уже
  вставлена, а `vaccinationsWithErrors` и остаток пагинации потеряны; не
  проверялось, насколько часто исключение реалистично возникает именно на
  этом шаге (`insert`/`saveDiseasesVaccinations`) в проде, а не на сетевом
  вызове.
- **Повторный запуск («Попробовать снова») перезапускает весь sync-проход
  заново, не только шаг вакцинации** — `_syncAllData` при повторной попытке
  выполняется от `_clearDataUpdates()` и далее по всей цепочке
  (`loadUser`, `syncAllUnsentAnimals`, `syncMovements`, `syncDisposals`,
  `loadAnimals`, и только затем снова `syncVaccinations`) — не
  проверялось (и не предмет этого файла — принадлежит `SYSTEM`, см.
  [MOD-4](../modules/MOD-4-ANIMAL.md), «Граница»), насколько это
  осознанное проектное решение против точечного retry только упавшего
  шага.
