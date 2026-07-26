# UC-50 — Sync создания животного успешен

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все
локально созданные животные ([ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md),
`id < 0`), у которых уже заполнен `farmId`, и все запросы завершаются успехом.
Для каждого такого животного локальный (отрицательный) `id` заменяется на
серверный: исходная строка удаляется, новая создаётся под серверным id, а все
связанные локальные записи (идентификации, ещё не отправленные взвешивания,
вакцинации, перемещения, невыгруженное выбытие), ссылавшиеся на старый id,
каскадно переписываются на новый — до удаления исходной строки. Happy-path
сценарий события [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)
(`animal.creation_synced`) — событие завершает то, что локально начал
[EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)
(`animal.registered_locally`), инициированный
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), авторизованный пользователь —
весь этот шаг гейтится `AuthRepository.isAuthorized()`) один раз
(`DataUpdateStartAll`), но в каждом отдельном сетевом вызове этого сценария
человек не участвует. Животное, отправляемое в этом сценарии, было
зарегистрировано ранее и локально — гостем или авторизованным пользователем
одинаково ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)) — этот факт не
влияет на то, отправится ли оно сейчас: единственные условия отбора здесь —
`id < 0` и заполненный `farmId`.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. Обработчик сначала проверяет сеть
   (`NetworkConnectivityService.hasConnection()`); при отсутствии сети сразу
   эмитится `DataUpdateFailure`, дальше сценарий не идёт (другая ветка, не
   часть этого use-case).
2. При наличии сети, после загрузки справочников и досок объявлений — если
   `_authRepository.isAuthorized()` — вызывается `DataUpdateBloc._syncAuthData`,
   которая (после ферм/мест/взвешиваний) вызывает
   `DataUpdateBloc.updateAndSyncRegagro`.
3. `updateAndSyncRegagro` решает — по количеству уже накопленных записей
   `DataUpdate`, наличию ошибок в них и флагам события — нужно ли запускать
   `DataUpdateBloc._syncAllData` в этом проходе; при недоступной сети на этом
   шаге эмитится `DataUpdateFailure` и сценарий не продолжается (другая ветка).
4. `_syncAllData` вызывает `_clearDataUpdates()`, затем `loadUser`, затем —
   после `_emitProgress(dataKey: DataKey.syncUnsentAnimals, dataCategory:
   DataCategory.syncUnsentAnimals)` — `DataUpdateBloc.syncAllUnsentAnimals()`,
   которая делегирует в `DataUpdateBloc._syncAllLocalAnimals()`. Это первый
   доменный (не directory/user) шаг синхронизации в проходе — раньше движений,
   выбытий, правок уже синхронизированных животных (`_syncEditedAnimals`) и
   полной перезагрузки списка животных с сервера (`loadAnimals`), которые идут
   следом в этом же `_syncAllData` и не входят в этот use-case.
5. `_syncAllLocalAnimals` запрашивает
   `AnimalsRepository.getAllLocalAnimalsWithDetailsByFilters()` без аргументов
   фильтра — внутри метод вызывает
   `AnimalsDao.getAllAnimalsWithDetailsByFilters` с `localOnly: true` и
   `requireFarmId: true`, то есть сам DB-запрос уже ограничен строками с
   `id < 0` **и** `farmId IS NOT NULL`. Для каждого элемента списка код всё
   ещё содержит охранное условие `if (awd.farmId == null) continue;` — оно не
   может сработать на результатах именно этого запроса (см. «Открытые
   вопросы»).
6. Для непустого списка каждое `AnimalWithDetails` (`awd`) отправляется по
   одному, в цикле, вызовом `AnimalsRepository.syncLocalAnimal(awd)` →
   `AnimalsRepository._syncLocalAnimalFarm` — `POST
   {registrationServiceApi}/animals/storeAnimal`. В теле запроса `number` и
   `marker_date` верхнего уровня берутся только из элемента
   `animalIdentifications`, у которого `markerTypeId ==
   Constants.TransponderMarkerTypeId` (найден через `firstWhereOrNull`, может
   быть `null`, если у животного нет идентификации-транспондера) — никогда из
   `Animal.number` и никогда из идентификации другого типа. Для каждого
   элемента вложенного списка `markers` поля `is_main` и `main`
   пересчитываются заново как `markerTypeId == Constants.TransponderMarkerTypeId`
   — локально сохранённое значение `AnimalIdentification.main` в этом запросе
   нигде не читается.
7. Ответ парсится `UnsentAnimalResponse.fromJson`; `BaseResponse.isSuccess` —
   `status == 1`, `BaseResponse.isError` — `errors != null`. В этом
   (`CREATE_OK`) сценарии `isSuccess == true` и `isError == false` для
   **каждого** отправленного в этом проходе животного.
8. При успехе `result.animal` (собран внутри `UnsentAnimalResponse.fromJson`
   как `Animal.fromJson(data)` с доп. полями родословной/диапазона дат
   рождения из вложенных объектов ответа) содержит новую строку животного с
   присвоенным сервером положительным `id` — сохраняется в `serverAnimal`;
   `localId` — это исходный (отрицательный) `animal.id` до отправки.
9. `DisposalRepository.changeIdUnsentAnimalFromUnsentDisposalList(oldId:
   localId, newId: serverAnimal.id)`, вызов обёрнут в try/catch (исключение
   гасится, логируется только при `kDebugMode`) — переписывает `animalId` у
   ещё не отправленных (`Disposal.sync == false`) записей выбытия, ссылавшихся
   на `localId`.
10. `AnimalsRepository.updateAnimalId(localId, serverAnimal.id)`, тоже
    обёрнут в try/catch с тем же гашением ошибки — каскадно переписывает
    `animalId` на `serverAnimal.id` у: ещё не отправленных взвешиваний
    (`AnimalWeighingsRepository.getAllNotSuncAnimalWeighings()`, дополнительно
    отфильтрованных на совпадение `animalId == localId` уже в коде репозитория
    животных), вакцинаций
    (`VaccinationsRepository.getVaccinationsByAnimalId(localId)`), перемещений
    (`MovementReportRepository.getAllByAnimalId(localId)`) и всех
    идентификаций
    (`AnimalIdentificationsRepository.updateAnimalIdForAllIdentifications(localId,
    serverAnimal.id)`). Оба каскадных вызова (шаги 9-10) выполняются и
    завершаются **до** удаления исходной строки животного на шаге 11.
11. Так как `localId != serverAnimal.id` практически всегда (отрицательный id
    против положительного серверного), вызывается
    `AnimalsRepository.deleteAnimalsWithDetailsByIds([localId])` — репозиторий
    сначала вызывает `_deleteRelatedOperationsByAnimalId(localId)` (удаление
    любых оставшихся под `localId` перемещений/взвешиваний/вакцинаций — в этом
    (`CREATE_OK`) сценарии таких уже нет, так как шаг 10 их переписал раньше),
    затем `AnimalsDao.deleteAnimalsWithDetailsByIds([localId])` — построчное
    `DELETE` строки `Animals` с этим `id` и всех `AnimalIdentifications` с
    этим `animalId` в одной транзакции.
12. `existing = await AnimalsRepository.getById(serverAnimal.id)` — на первом
    успешном создании такой строки под этим id ещё нет, поэтому
    `existing == null` → `AnimalsRepository.insert(serverAnimal)`. Если строка
    с этим серверным id уже существует (иначе), вместо этого выполняется
    `AnimalsRepository.update(serverAnimal)`.
13. Цикл переходит к следующему `AnimalWithDetails` в списке из шага 5, если
    он есть; после цикла `_syncAllData` продолжает `_settingsRepository`,
    `_movementReportRepository.syncMovements()`,
    `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()`,
    `loadAnimals()`, `_vaccinationsRepository.syncVaccinations(true)` — все
    вне рамок этого use-case.

### Альтернативные потоки

- `getAllLocalAnimalsWithDetailsByFilters()` пуст (нет локальных животных с
  заполненным `farmId`) — цикл в `_syncAllLocalAnimals` не выполняет ни одной
  итерации, ни один сетевой вызов не происходит; вырожденный случай «нечего
  синхронизировать», не этот сценарий.
- Ответ сервера для конкретного животного — ошибка (`isError == true` или
  `!isSuccess`) — ветка `if (result.isError || !result.isSuccess)` пишет
  `animal.errors` и переходит к следующему животному, не удаляя и не заменяя
  локальную строку; отдельный `ERROR`-сценарий, не входит в этот use-case, где
  предполагается, что **все** отправленные в этом проходе животные получают
  успех.
- Животное без идентификации-транспондера (`identification == null` на шаге
  6) — `number` и `marker_date` верхнего уровня уходят как `null`; это всё
  ещё `CREATE_OK`, если сервер отвечает успехом, просто с более скудным телом
  запроса — не отдельный сценарий.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — основная
  сущность перехода: исходная (отрицательная id) строка удаляется целиком
  (не обновляется на месте — в отличие от Farm в
  [UC-25](UC-25-ACTOR-4-EVT-12-ENT-9-CREATE_OK-IN-FARM.md), где `remoteId`
  переписывается в той же строке), новая строка создаётся под серверным id из
  данных ответа.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — каскадно: `animalId` всех идентификаций, ссылавшихся
  на старый (отрицательный) id животного, переписывается на новый серверный —
  сами строки идентификаций не удаляются и не пересоздаются из ответа сервера
  (см. «Открытые вопросы» про неиспользуемое
  `UnsentAnimalResponse.animalIdentifications`).
- AnimalWeighing, Vaccination, Movement, Disposal — каскадно переписывается
  `animalId` только у ещё не отправленных строк (`sync == false` /
  «not sync»), ссылавшихся на старый id животного. Эти сущности принадлежат
  ещё не специфицированным под-областям [MOD-4](../modules/MOD-4-ANIMAL.md)
  (WEIGH/VAC/MOVE/DISP соответственно) — отдельных `ENT`-id для них в дереве
  спек пока нет.

### Бизнес-правила

- Кандидаты на отправку — только локальные (`id < 0`) животные с заполненным
  `farmId`; фильтрация происходит на уровне самого DB-запроса
  (`localOnly`/`requireFarmId` в `AnimalsDao.getAllAnimalsWithDetailsByFilters`),
  а не только по коду вызывающего цикла.
- `number`/`marker_date` верхнего уровня запроса и `is_main`/`main` каждого
  элемента `markers` всегда вычисляются из/по признаку
  `markerTypeId == Constants.TransponderMarkerTypeId` — независимо от того,
  что локально хранится в `Animal.number` или `AnimalIdentification.main`.
- Животные отправляются по одной, в цикле, не батчем; порядок — тот, в
  котором `getAllLocalAnimalsWithDetailsByFilters()` их вернул (явной
  сортировки в вызывающем коде нет).
- Каскадное обновление связанных записей (шаги 9-10) выполняется **раньше**,
  чем удаляется исходная строка животного (шаг 11) — по порядку строк в
  `_syncAllLocalAnimals`.
- И `changeIdUnsentAnimalFromUnsentDisposalList`, и `updateAnimalId`
  вызываются каждый в своём try/catch, гасящем любое исключение (лог — только
  при `kDebugMode`); ошибка внутри каскада не отражается в `animal.errors` и
  не останавливает цикл — животное в этом случае всё равно считается успешно
  синхронизированным.
- `existing == null` → `insert`, иначе `update` (шаг 12) — единственная
  развилка между вставкой новой строки и обновлением уже существующей под тем
  же серверным id; для первого создания конкретного животного это всегда
  `insert`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде. Тестового покрытия на уровне
`DataUpdateBloc`/`_syncAllLocalAnimals` нет (см. «Связанные тесты») — это факт
отсутствия теста, а не незавершённость сценария.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | точка входа полного sync-прохода, проверка сети |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | последовательность sync-шагов для авторизованного пользователя, вызывает `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | решает, нужно ли запускать `_syncAllData` в этом проходе |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `syncAllUnsentAnimals` первым доменным шагом после `loadUser` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.syncAllUnsentAnimals` | CURRENT | делегирует в `_syncAllLocalAnimals` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllLocalAnimals` | CURRENT | оркестрация: выборка локальных животных, отправка по одному, каскад id, delete+insert/update |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncLocalAnimal`, `AnimalsRepository._syncLocalAnimalFarm` | CURRENT | `POST {registrationServiceApi}/animals/storeAnimal`; построение `number`/`marker_date`/`markers` из идентификации-транспондера |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllLocalAnimalsWithDetailsByFilters` | CURRENT | обёртка над `AnimalsDao.getAllLocalAnimalsWithDetailsByFilters` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateAnimalId` | CURRENT | каскад `animalId` в weighings/vaccinations/movements/identifications |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.deleteAnimalsWithDetailsByIds`, `AnimalsRepository._deleteRelatedOperationsByAnimalId` | CURRENT | удаление исходной строки Animal+AnimalIdentifications; safety-net удаление movements/weighings/vaccinations под старым id |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getById`, `AnimalsRepository.insert`, `AnimalsRepository.update` | CURRENT | insert-or-update новой строки под серверным id |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.changeIdUnsentAnimalFromUnsentDisposalList` | CURRENT | переписывает `animalId` у ещё не отправленных (`sync == false`) записей выбытия |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository.updateAnimalIdForAllIdentifications` | CURRENT | каскад `animalId` для идентификаций |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllLocalAnimalsWithDetailsByFilters`, `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | DB-уровневый фильтр `localOnly`/`requireFarmId` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.deleteAnimalsWithDetailsByIds` | CURRENT | построчный `DELETE` `Animals`+`AnimalIdentifications` в транзакции |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllLocalUnsynced` | CURRENT | выборка `id < 0`, используется отдельно `loadAnimals`/`syncAllAnimals` (см. «Открытые вопросы») |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.farmId` | CURRENT | геттер `animal.farmId ?? joinedFarmId`, используется охранным условием шага 5 |
| `packages/sheep_farm_database/lib/entities/animal/local_animals_groups.dart` | `UnsentAnimalResponse.fromJson`, `BaseResponse.isSuccess`, `BaseResponse.isError` | CURRENT | парсинг ответа сервера, признаки успеха/ошибки |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId`, `Constants.registrationServiceApi` | CURRENT | id типа маркера «транспондер» (`3`), базовый URL сервиса регистрации |

## Критерии приёмки

- При полном sync-проходе (`DataUpdateStartAll`), при наличии сети и
  авторизованном пользователе, для каждого локального (`id < 0`) животного с
  заполненным `farmId` выполняется отдельный `POST
  {registrationServiceApi}/animals/storeAnimal`.
- В теле каждого такого запроса `number`/`marker_date` верхнего уровня взяты
  из идентификации с `markerTypeId == Constants.TransponderMarkerTypeId` (или
  `null`, если такой нет); каждый элемент `markers` несёт `is_main`/`main`,
  равные `markerTypeId == Constants.TransponderMarkerTypeId`.
- Если ответ на такой запрос — `status == 1` без `errors`, после прохода в
  локальной БД больше нет строки `Animals` со старым (отрицательным) `id`
  этого животного, но есть строка с серверным id из ответа.
- Все идентификации, ещё не отправленные взвешивания/вакцинации/перемещения и
  ещё не отправленные (`sync == false`) записи выбытия, ссылавшиеся на старый
  id животного, после прохода ссылаются на новый серверный id.
- `AnimalsRepository.getAllLocalUnsynced()` после успешного прохода для этого
  животного больше не возвращает его (оно больше не `id < 0`).

## Связанные тесты

`TBD — теста нет` на уровне `DataUpdateBloc`/`_syncAllLocalAnimals`. Файл
`test/blocs/data_update_bloc_test.dart` существует, но содержит только два
теста — конструирование блока и `DataUpdateClear` — ни один `group()`/`test()`
не касается `syncAllUnsentAnimals`/`_syncAllLocalAnimals`; поиск
`syncAllUnsentAnimals`/`_syncAllLocalAnimals`/`syncLocalAnimal`/`UC-50` по
`test/` подтверждает отсутствие такого теста на этом уровне.

Отдельные строительные блоки этого сценария покрыты юнит-тестами
репозитория, но не самим сценарием и не привязаны к этому id (`group()` не
именован `UC-50`): `test/repositories/animals_repository_test.dart` —
`group('updateAnimalId — обновление ссылок при замене local id на
серверный', ...)` проверяет каскад `animalId` в
weighings/vaccinations/movements/identifications в изоляции (шаг 10 этого
use-case), `group('syncLocalAnimal — идёт напрямую в Farm (R3/RegAgro-бэкенд
удалён)', ...)` проверяет только сам факт вызова `farm_rpc` и разбор успешного
ответа (шаги 6-7), не строит и не проверяет тело запроса
(`number`/`marker_date`/`is_main`/`main`, шаг 6), и `group('deleteAnimalsWithDetailsByIds', ...)`
проверяет удаление строки в изоляции (шаг 11). Ни один из этих тестов не
покрывает оркестрацию `_syncAllLocalAnimals` целиком: охранное условие шага 5,
try/catch-гашение шагов 9-10, ветвление insert-или-update шага 12 — не
проверены нигде.

## Открытые вопросы и ограничения

- Охранное условие `if (awd.farmId == null) continue;` в
  `_syncAllLocalAnimals` (шаг 5) — мёртвый код на результатах именно этого
  запроса: `AnimalsRepository.getAllLocalAnimalsWithDetailsByFilters()`
  вызывает `AnimalsDao.getAllAnimalsWithDetailsByFilters` с
  `requireFarmId: true`, который уже добавляет `WHERE farmId IS NOT NULL` на
  уровне SQL, а `AnimalWithDetails.farmId` — это `animal.farmId ??
  joinedFarmId`, то есть не может быть `null`, если `animal.farmId` не может
  быть `null`. Условие, возможно, было актуально до появления
  `requireFarmId` или защищает от гипотетического будущего вызова этого же
  метода с другими аргументами — факт зафиксирован здесь, дальше не
  разбирается.
- И `DisposalRepository.changeIdUnsentAnimalFromUnsentDisposalList`, и
  `AnimalsRepository.updateAnimalId` (шаги 9-10) вызываются в try/catch,
  который гасит исключение полностью и логирует его только при
  `kDebugMode`. Если один из этих вызовов упадёт частично (например,
  обновил взвешивания, но упал на вакцинациях) — часть связанных записей
  останется ссылаться на старый (уже удалённый на шаге 11) `localId`,
  животное при этом не помечается `errors` и по внешним признакам считается
  успешно синхронизированным. Это не проявляется в `CREATE_OK`-сценарии, где
  предполагается, что каскад проходит целиком, но означает, что частичный
  отказ каскада — тихая потеря связи, не отдельный `ERROR` use-case с
  собственным наблюдаемым результатом.
- `UnsentAnimalResponse.animalIdentifications` — распарсен из
  `data.animal_identifications` ответа сервера в
  `UnsentAnimalResponse.fromJson`, но нигде не читается в
  `_syncAllLocalAnimals`: локальные идентификации после этого сценария — это
  те же ранее существовавшие строки, у которых шаг 10 переписал `animalId`,
  а не то, что вернул сервер в этом поле. Не выяснено, для чего тогда это
  поле разбирается (используется ли оно где-то ещё в кодовой базе) — вне
  рамок этого файла.
- `_syncAllLocalAnimals` (этот use-case) выполняется в `_syncAllData` раньше,
  чем `loadAnimals()` в том же проходе. `loadAnimals()` вызывает
  `AnimalsRepository.syncAllAnimals()`, которая внутри одной транзакции
  удаляет **все** строки `Animals`, затем вставляет заново данные из полного
  серверного fetch плюс `localsToRestore` — животные из
  `AnimalsRepository.getAllLocalUnsynced()` (`id < 0`), которых нет среди
  id, вернувшихся с сервера. Животное, только что созданное этим use-case,
  уже имеет положительный (не «unsynced») id, поэтому не попадёт в
  `localsToRestore`; если оно по любой причине ещё не отражено в ответе того
  же полного fetch (например, из-за задержки согласованности на бэкенде), оно
  не попадёт и в `animalData` — итог: строка молча исчезнет из локальной БД
  до конца этого же прохода. Не проверено эмпирически (требует сетевого
  таймлайна бэкенда, не только чтения кода) — зафиксировано здесь как риск,
  не разбирается дальше в рамках этого `CREATE_OK` use-case.
- Нет теста на уровне `DataUpdateBloc`/`_syncAllLocalAnimals` (см. «Связанные
  тесты») — весь сценарий проверен только чтением кода.
