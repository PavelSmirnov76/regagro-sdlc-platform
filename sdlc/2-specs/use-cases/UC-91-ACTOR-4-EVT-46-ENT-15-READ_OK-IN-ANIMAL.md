# UC-91 — Система перезагружает взвешивания животных с сервера на шаге полной перезагрузки животных в sync-проходе

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

В рамках того же явного полного sync-прохода, что запускает пользователь (сам
факт запуска прохода специфицируется модулем SYSTEM, см.
[MOD-4](../modules/MOD-4-ANIMAL.md), «Граница» — не здесь) — на шаге,
который находится намного позже push'а ещё не отправленных взвешиваний
([EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)), почти
в самом конце `_syncAllData` — система полностью перезагружает локальные
таблицы животных, их идентификаций и взвешиваний из ответа сервера. Это
закрывает временное окно, в котором локальных данных о взвешиваниях меньше,
чем должно быть (открытое более ранним push-шагом, который удаляет
отправленные строки локально без немедленной замены), а заодно подтягивает
взвешивания, созданные за это время с другого устройства или другим
пользователем той же СХТП.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во
время sync-прохода (`DataUpdateBloc`), без участия пользователя в момент
именно этого шага.

## CURRENT

### Основной поток

1. Пользователь ранее запустил полный sync-проход
   (`DataUpdateBloc.on<DataUpdateStartAll>`), проверка сети уже пройдена
   успешно, и `_authRepository.isAuthorized()` истинно — внутри
   `_syncAuthData` уже отработали, по порядку: `_deletePlacesFromRDS()` →
   `_syncFarms()` → `_syncPlaces()` →
   `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`
   ([EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)) —
   push-шаг взвешиваний идёт четвёртым, уже после ферм/мест, но всё ещё
   задолго до предмета этого файла — и затем `updateAndSyncRegagro`.
2. `updateAndSyncRegagro` (при подтверждённом сетевом подключении и с учётом
   счётчика уже сохранённых `DataUpdate`-записей/флагов события) вызывает
   `_syncAllData(event, emit)`.
3. Внутри `_syncAllData`, **между** push-шагом взвешиваний и этим шагом,
   успевают отработать: `_clearDataUpdates()`, `loadUser`,
   `syncAllUnsentAnimals()` (отправка ещё не синхронизированных локальных
   животных — `id < 0` — на сервер; не каждое локальное животное обязательно
   синхронизируется здесь, см. «Бизнес-правила»), синхронизация настроек,
   `_movementReportRepository.syncMovements()`,
   `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()` — и только
   затем вызывается `await loadAnimals(event, emit)`, предмет этого файла.
   Сразу за ним, всё ещё внутри `_syncAllData`, следует
   `_vaccinationsRepository.syncVaccinations(true)`.
4. `loadAnimals` эмитит прогресс (`DataKey.animals`/`DataCategory.animals`),
   затем последовательно, тремя отдельными `await`-вызовами (не в одной
   транзакции):
   - `_animalsRepository.clear()` — `BaseRepository.clear()` →
     `AnimalsDao.clear()` (унаследовано, `AnimalsRepository` не
     переопределяет) — удаляет **все** строки таблицы `Animals`, без фильтра
     по `sync`/id.
   - `_animalIdentificationsRepository.clear()` — так же удаляет **все**
     строки `AnimalIdentifications`.
   - `_animalWeighingsRepository.clearSync()` →
     `AnimalWeighingsDao.clearSync()` — удаляет только строки `AnimalWeighings`
     с `sync == true`; строки с `sync == false` не трогает.
5. Затем `await _animalsRepository.syncAllAnimals()` (без аргумента
   `fromDate` — полная, не инкрементальная перезагрузка):
   - `paginatedRequestHandler(perPage: 1000, onRequest: _fetchAnimalsPage,
     onResponse: ...)` — цикл запросов `GET
     ${Constants.registrationServiceApi}/animals` (`instanceName:
     'farm_rpc'`, query `with_trashed: 1, with_weight: 1`), продолжается,
     пока очередная страница не вернёт пустой список `animals`; ответ каждой
     страницы парсится через `AnimalsDto.fromJson` и накапливается в
     `allAnimalsData` (`animals`, `identifications`, `animalWeigings`).
   - Для каждого животного в ответе сервера поле `weight_history` (если оно
     не `null`) построчно парсится через `AnimalWeighingDto.fromJson(e)` и
     конвертируется `.toAnimalWeighing(animal.id)` в
     `AnimalWeighingsCompanion(animalId: ..., remoteId: <серверный id из
     weight_history>, weight: ..., weighingDate: ..., unitId: ..., sync:
     Value(true))` — локальный `id` не выставляется (автоинкремент).
   - После завершения пагинации читает `getAllLocalUnsynced()` (животные с
     `id < 0`) и их идентификации — см. «Бизнес-правила»/«Открытые вопросы»:
     при вызове через `loadAnimals` этот список всегда пуст, потому что шаг 4
     уже удалил все строки `Animals` до этого момента.
   - Всё дальнейшее — в одном `db.transaction()`: `db.delete(db.animals).go()`
     и `db.delete(db.animalIdentifications).go()` (избыточны здесь — обе
     таблицы уже пусты после шага 4), затем единый `db.batch(...)`:
     `batch.insertAll(db.animals, animalData)`,
     `batch.insertAll(db.animalIdentifications, allAnimalsData.identifications)`,
     **`batch.insertAll(db.animalWeighings, allAnimalsData.animalWeigings)`**
     — это и есть батч-вставка взвешиваний, вокруг которой построен этот
     use-case; затем условная попытка восстановить `localsToRestore`
     (местные животные, отсутствующие среди `serverIds`) — на практике
     список всегда пуст в этом пути вызова (см. выше), поэтому этот блок
     кода не выполняется.
6. Обратно в `loadAnimals`: `await _addDataUpdateSuccess(_currentDataCategory)`
   (`DataCategory.animals`) — добавляет запись об успехе в журнал
   sync-прохода (`DataUpdate`, владелец — модуль SYSTEM, см.
   `.claude/rules/domain-model.md`), чем и завершается этот шаг с исходом
   `READ_OK`.

### Альтернативные потоки

- **Исключение на любом шаге `loadAnimals`** (сетевой сбой любой страницы
  пагинации, ошибка внутри транзакции и т.д.) перехватывается локальным
  `try { ... } catch (_) { rethrow; }` — перехват здесь не гасит исключение,
  а лишь пробрасывает его дальше без изменений. Оно продолжает всплывать
  через `_syncAllData` → `updateAndSyncRegagro` → `_syncAuthData` до внешнего
  `try/catch` в `on<DataUpdateStartAll>`, который вызывает `_emitError` и
  завершает **весь** sync-проход `DataUpdateFailure`. Другой `RESULT`
  (`READ_ERROR`), не описывается этим файлом — но на момент сбоя часть
  локальных данных о взвешиваниях уже могла быть удалена шагом 4
  (`clearSync()`), без гарантии, что перезагрузка успела её заменить.
- **Пустой ответ сервера на самой первой странице.** Если ферма
  действительно не имеет ни одного животного (или ответ пуст по другой
  причине), пагинация останавливается сразу же, `allAnimalsData` остаётся
  полностью пустым; транзакция всё равно выполняется — `delete` на уже
  пустых таблицах и `insertAll` на пустых списках. Тот же `RESULT`
  (`READ_OK` — шаг завершился успешно, просто без данных), не отдельный
  use-case.
- **У конкретного животного `weight_history` отсутствует (`null`) в ответе
  сервера.** Такое животное не добавляет ни одной строки в `animalWeigings`
  (условие `if (animalWeighingsData != null)`); на остальные животные того же
  ответа это не влияет.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  основная сущность этого шага: полностью зависимая от сервера часть таблицы
  (`sync == true`) удаляется и заново вставляется батчем; строки `sync ==
  false` (ещё не отправленные) этим шагом не читаются и не удаляются
  напрямую — но могут осиротеть, если их родительское животное было удалено
  и не восстановлено (см. ниже, ENT-11).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — тот же шаг
  дважды (сначала `_animalsRepository.clear()` в `loadAnimals`, затем
  собственный `db.delete(db.animals)` внутри `syncAllAnimals()`) удаляет
  **все** строки таблицы `Animals` без фильтра по `id`/синхронизации, и затем
  заново вставляет их из ответа сервера. **Находка:** локальное
  (`id < 0`, ещё не отправленное) животное, которое к моменту этого шага не
  было синхронизировано более ранним `syncAllUnsentAnimals()` (например, у
  него не заполнен `farmId`, либо предыдущая попытка синхронизации
  завершилась ошибкой — animal остаётся с `errors`, но всё ещё `id < 0`),
  удаляется этим шагом безвозвратно: заложенная в `syncAllAnimals()` логика
  восстановления `localsToRestore` читает `getAllLocalUnsynced()` уже
  **после** того, как вызывающий код (`loadAnimals`) полностью очистил
  таблицу `Animals` — поэтому список всегда пуст в этом пути вызова, и
  восстановление никогда не срабатывает на практике (см. «Бизнес-правила»).
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — та же участь, что и у Animal: полностью
  перезаписывается этим шагом (дважды удаляется, один раз вставляется), и
  восстановление локальных-только идентификаций так же неработоспособно на
  практике по той же причине.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — только читается по ссылке (`unitId` в присланных
  `weight_history`), этим шагом не создаётся и не изменяется.

### Бизнес-правила

- **Перезагрузка «всё или ничего» без сравнения по записям** — как для
  животных/идентификаций (полная замена), так и для взвешиваний (замена
  только той части, что уже была `sync == true`); нет промежуточного
  варианта «обновить только изменившееся».
- **Три независимых `await`-вызова в `loadAnimals` (`clear()` / `clear()` /
  `clearSync()`) выполняются не в одной транзакции** — если процесс
  прервётся между ними и стартом `syncAllAnimals()` (например, крашем
  приложения или обрывом сети до первого запроса страницы), локальные
  таблицы `Animals`/`AnimalIdentifications` останутся полностью пустыми, а
  `AnimalWeighings` — без единой ранее синхронизированной строки, до
  следующего успешного полного sync-прохода.
- **Двойное удаление Animals/AnimalIdentifications.** `loadAnimals` вызывает
  `_animalsRepository.clear()`/`_animalIdentificationsRepository.clear()`
  явно, а `syncAllAnimals()` внутри своей же транзакции повторно выполняет
  `db.delete(db.animals).go()`/`db.delete(db.animalIdentifications).go()` —
  избыточно (обе таблицы уже пусты), но именно из-за этого порядка
  восстановление local-only животных внутри `syncAllAnimals()` становится
  недостижимым при вызове из `loadAnimals` (см. «Связанные сущности»,
  находка про ENT-11).
- **Единственный вызывающий код, где логика восстановления local-only
  животных внутри `syncAllAnimals()` могла бы реально сработать —
  `DataUpdateBloc.updateAnimals(fromDate: ...)`** — не вызывает предварительный
  `clear()`/`clearSync()` перед `syncAllAnimals(fromDate: ...)`. Но
  `updateAnimals` не вызывается нигде в кодовой базе (ни из `_syncAllData`,
  ни из какого-либо другого места `lib/` или `test/` — проверено по всему
  дереву репозитория) — это полностью мёртвый метод. Итог: логика
  восстановления local-only животных внутри `syncAllAnimals()` мертва в
  обоих смыслах — либо вызывающий код (`updateAnimals`), который сделал бы её
  осмысленной, никогда не вызывается, либо вызывающий код, который
  реально вызывается (`loadAnimals`), лишает её смысла предварительной
  полной очисткой.
- **Ни один из трёх `clear`/`clearSync`-вызовов явно не переключает `PRAGMA
  foreign_keys`.** В кодовой базе единственное место, которое это делает —
  сгенерированный `ClearableExtension.clearAllClearableTables` (вызывается
  при логауте через `_appDatabase.clearUserData()`, не этим шагом): временно
  выключает `foreign_keys` на время своей очистки и явно включает обратно в
  `finally`. Ни соединение с БД при
  открытии (`database.dart`, `_openConnection`), ни этот шаг `loadAnimals`
  не задают PRAGMA явно — фактическое состояние enforcement на момент этого
  шага зависит от того, происходил ли логаут раньше в рамках того же
  запущенного процесса приложения; не проверялось эмпирически на реальном
  устройстве/сборке.
- **Взвешивания от сервера всегда получают новый локальный `id`** (не
  переиспользуют старый) — `AnimalWeighingDtoExtension.toAnimalWeighing` не
  выставляет `id`, только `remoteId`; дубликатов по `remoteId` в рамках
  одного успешного шага не возникает, поскольку предшествующий `clearSync()`
  безусловно удаляет все прежние `sync == true` строки перед вставкой.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и достижим на практике (весь
`_syncAllData` последовательно доходит до `loadAnimals` при штатном полном
sync-проходе). Раздел «Открытые вопросы» ниже фиксирует найденный дефект
восстановления local-only животных — он не блокирует сам факт успешной
перезагрузки взвешиваний, но искажает связанный факт про Animal/
AnimalIdentification в рамках того же шага.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | более ранний шаг того же прохода — push взвешиваний ([EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)) через `storeAnimalWeighingsToSHTP`, задолго до этого шага |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | задаёт порядок: `...` → `_syncEditedAnimals()` → `loadAnimals` → `_vaccinationsRepository.syncVaccinations(true)` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | ядро сценария: `clear()`+`clear()`+`clearSync()` → `syncAllAnimals()` → `_addDataUpdateSuccess`; `try/catch` без обработки, только `rethrow` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAnimals` | CURRENT | альтернативный (инкрементальный, `fromDate`) вызывающий код `syncAllAnimals` — не вызывается нигде в кодовой базе (мёртвый код, см. «Бизнес-правила») |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.clearSync` | CURRENT | делегирует в `dao.clearSync()` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.clearSync` | CURRENT | `delete` строк `AnimalWeighings` где `sync == true` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.clear` (унаследован из `BaseRepository`) | CURRENT | `delete` всех строк `Animals`, без фильтра |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear`, `BaseRepository.paginatedRequestHandler` | CURRENT | нижележащие примитивы: полная очистка таблицы; цикл постраничного опроса сервера до пустой страницы |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncAllAnimals` | CURRENT | пагинация + одна транзакция: `delete`+`batch.insertAll` для animals/identifications/weighings, попытка восстановления local-only животных |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository._fetchAnimalsPage` | CURRENT | одна страница `GET .../animals` с `with_weight: 1` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `AnimalsDto.fromJson`, `AnimalsDto.empty` | CURRENT | парсинг ответа сервера в `animals`/`identifications`/`animalWeigings` (поле `weight_history` на каждом животном) |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighingDto.fromJson`, `AnimalWeighingDtoExtension.toAnimalWeighing` | CURRENT | маппинг одного элемента `weight_history` в `AnimalWeighingsCompanion` (`sync: true`, `remoteId` = серверный id) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllLocalUnsynced` | CURRENT | источник «local-only» списка внутри `syncAllAnimals` — при вызове через `loadAnimals` всегда пуст (см. «Бизнес-правила») |
| `packages/sheep_farm_database/lib/database/database.clearable.dart` | `ClearableExtension.clearAllClearableTables` | CURRENT | единственное место в кодовой базе, явно переключающее `PRAGMA foreign_keys`; этим шагом не вызывается |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL для `.../animals` |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | транспорт запроса (`instanceName: 'farm_rpc'`) |

## Критерии приёмки

- На каждом полном sync-проходе шаг `loadAnimals` удаляет локальные строки
  `AnimalWeighings` с `sync == true` (`clearSync()`) **до** первого сетевого
  запроса `syncAllAnimals()` — не после и не одновременно.
- После успешного завершения пагинации (`GET .../animals`, до первой пустой
  страницы) и коммита единой транзакции, локальная таблица `AnimalWeighings`
  содержит ровно объединение всех элементов `weight_history` по всем
  страницам ответа, каждый — с `sync: true`, `remoteId`, равным серверному
  id взвешивания, и новым локальным `id`.
- Строки `AnimalWeighings` с `sync == false` не удаляются шагом `clearSync()`
  и не участвуют в батч-вставке из ответа сервера.
- Любое исключение между стартом `loadAnimals` и коммитом финальной
  транзакции пробрасывается без изменений (`rethrow`) и проваливает весь
  sync-проход (`DataUpdateFailure`) — не даёт частично применённого
  состояния как «успех».
- Локальное (`id < 0`) животное, оставшееся несинхронизированным к моменту
  старта `loadAnimals`, удаляется этим шагом и не восстанавливается —
  собственная логика восстановления `syncAllAnimals()` не может его найти,
  потому что вызывающий код уже очистил таблицу `Animals` перед вызовом.

## Связанные тесты

TBD — теста нет. В `test/blocs/data_update_bloc_test.dart` есть только два
теста (конструирование `DataUpdateBloc` из зависимостей `getIt` и
`DataUpdateClear` очищает пользовательские данные) — ни `loadAnimals`, ни
ветка `_syncAllData`, доходящая до него, не вызываются ни в одном тестовом
сценарии. В `test/repositories/animals_repository_test.dart` `syncAllAnimals`
не упоминается вовсе (`grep` по файлу подтверждает единственное вхождение —
в самом `lib/repositories/animal/animals_repository.dart`); единственный
тест, где фигурирует `weighingsRepository`, — группа
`'updateAnimalId — обновление ссылок при замене local id на серверный'`,
которая проверяет отдельный сценарий (перенос `animalId` в связанных
записях при замене id), не эту перезагрузку с сервера.

## Открытые вопросы и ограничения

- **Находка — восстановление local-only животных внутри `syncAllAnimals()`
  недостижимо на практике.** Единственный реально вызываемый путь
  (`loadAnimals`) вызывает `_animalsRepository.clear()` **до**
  `syncAllAnimals()`, которая сама читает `getAllLocalUnsynced()` для
  вычисления `localsToRestore` — список всегда пуст к этому моменту.
  Единственный путь, где эта логика была бы осмысленной
  (`DataUpdateBloc.updateAnimals`, инкрементальный, без предварительного
  `clear()`), нигде не вызывается — мёртвый метод (проверено `grep` по всему
  `lib/`/`test/`). Итоговый эффект: локальное животное, не
  синхронизированное более ранним `syncAllUnsentAnimals()` (например, из-за
  отсутствующего `farmId` или ошибки прошлой попытки синхронизации),
  безвозвратно удаляется каждым полным sync-проходом, вместе со своими
  идентификациями; его ещё не отправленные взвешивания (`sync == false`,
  переживают `clearSync()`) остаются в таблице `AnimalWeighings`, ссылаясь
  на уже несуществующий `animalId` — не проверялось, приводит ли это к
  видимым ошибкам в UI (списки взвешиваний по несуществующему животному)
  или проходит незамеченным.
- **Неясен фактический статус `PRAGMA foreign_keys` в момент этого шага.**
  Ни открытие соединения, ни этот шаг явно не задают его; единственное
  место в кодовой базе, которое им управляет
  (`ClearableExtension.clearAllClearableTables`, логаут), временно выключает
  и затем включает его обратно — если логаут происходил раньше в рамках
  того же запущенного процесса приложения, `foreign_keys` мог остаться
  включённым для всех последующих операций, включая описанные здесь
  безусловные `delete`; не проверялось эмпирически, приводит ли это к
  исключению при удалении животного с ещё существующими дочерними строками,
  либо ограничение в этой сборке попросту не активно.
- **Три отдельных `await`-вызова в `loadAnimals` не образуют одну
  транзакцию** с последующей сетевой синхронизацией — крах/обрыв процесса
  между ними и стартом `syncAllAnimals()` оставляет `Animals`/
  `AnimalIdentifications` пустыми, а `AnimalWeighings` без единой ранее
  синхронизированной строки, до следующего успешного полного прохода; не
  проверялось, насколько часто это окно реалистично достижимо на практике
  (зависит от длительности пагинации по `.../animals`, которая может занять
  несколько сетевых round-trip'ов на крупных фермах).
- **Асимметрия обработки ошибок в рамках одного и того же прохода.** Сбой на
  этом шаге (`loadAnimals`) — как и сбой push-шага взвешиваний
  ([EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)) —
  прерывает **весь** sync-проход (`rethrow` до внешнего `try/catch`); это
  отличается от, например, перезагрузки перемещений
  ([UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)), где сбой
  pull-шага только логируется и не прерывает ничего. Не проверялось, является
  ли это осознанным решением (весь блок «животные» считается критичным для
  продолжения прохода) или случайной несогласованностью между похожими
  pull-шагами разных сущностей.
