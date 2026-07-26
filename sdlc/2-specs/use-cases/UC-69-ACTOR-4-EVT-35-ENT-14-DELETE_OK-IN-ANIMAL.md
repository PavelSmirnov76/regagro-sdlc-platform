# UC-69 — Sync-проход успешно отправляет батч удаления вакцинаций на сервер

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного полного sync-прохода, инициированного пользователем, система
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) отправляет на сервер все
записи [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), помеченные на
«мягкое» удаление уже синхронизированной вакцинации (`deletedAt != null`),
одним батч-запросом `DELETE .../vaccination-group-actions` сразу, и запрос
завершается успехом для всей пачки разом. Happy-path сценарий события
[EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)
(`vaccination.deletion_push_synced`).

Важная оговорка, разбираемая ниже (см. «Открытые вопросы и ограничения»): на
сегодня строка в состоянии, которое отбирает этот шаг, никогда не появляется
через живой UI — `markVaccinationForDeletion` (единственный способ выставить
`deletedAt`) вызывается только из `VaccinationCardPage`, чей маршрут нигде не
открывается (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)). Этот
файл описывает шаг так, как он реально выполнился бы, если бы такая строка
существовала — производный сценарий, воспроизводимый сегодня только прямой
вставкой строки в БД (как это делает существующий репозиторный тест).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая во время
sync-прохода. Проход инициирован человеком
([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), авторизованный пользователь —
весь путь до этого шага гейтится `_authRepository.isAuthorized()`) один раз
(`DataUpdateStartAll`), но в каждом отдельном сетевом вызове этого сценария
человек не участвует. Кто именно когда-то поставил вакцинацию на удаление, для
этого шага не имеет значения — единственное условие отбора строки, описанное
ниже, не различает авторов.

## CURRENT

### Основной поток

1. Авторизованный пользователь инициирует полный sync-проход —
   `DataUpdateBloc.on<DataUpdateStartAll>`. При отсутствии сети сразу эмитится
   `DataUpdateFailure`, дальше сценарий не идёт (другая ветка).
2. При наличии сети и `_authRepository.isAuthorized()` вызывается
   `DataUpdateBloc._syncAuthData`, которая выполняет фиксированную
   последовательность `_deletePlacesFromRDS()` → `_syncFarms()` →
   `_syncPlaces()` → `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()`
   → `updateAndSyncRegagro(event, emit)` (дальше в том же методе идут
   `updateAndSyncSHTP` и синхронизация устройств — вне рамок этого use-case).
3. `updateAndSyncRegagro` решает — та же развилка, что уже описана в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md) (шаг 3) и
   [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md) (шаг 4) — по
   количеству уже накопленных записей `DataUpdate`, наличию ошибок в них и
   флагам события, с повторной проверкой сети — нужно ли запускать
   `DataUpdateBloc._syncAllData` в этом проходе. Если условия не выполняются,
   сценарий до вакцинаций не доходит (другая ветка).
4. `_syncAllData` — тот же общий префикс, что и в
   [UC-50](UC-50-ACTOR-4-EVT-25-ENT-11-CREATE_OK-IN-ANIMAL.md) (шаг 4) и
   [UC-60](UC-60-ACTOR-4-EVT-30-ENT-13-CREATE_OK-IN-ANIMAL.md) (шаг 5):
   `_clearDataUpdates()` → `loadUser` → `syncAllUnsentAnimals()` →
   `_emitProgress(dataKey: DataKey.syncSettings)` → опционально
   `_settingsRepository.setSettingToSHTP()` → безусловно
   `_settingsRepository.getSettingFromSHTP()` → `_movementReportRepository
   .syncMovements()` → `_disposalRepository.syncDisposals()` →
   `_syncEditedAnimals()` → `loadAnimals(event, emit)` — все вне рамок этого
   use-case — и, наконец, **`await _vaccinationsRepository
   .syncVaccinations(true)`** — последний вызов в `_syncAllData`, с этого
   начинается собственно этот сценарий.
5. `VaccinationsRepository.syncVaccinations(isFullSync: true)`: т.к.
   `isFullSync == true`, первым вызывается `_deleteVaccinationFromApi()` —
   до `_updateVaccinationFromApi()` и `_sendVaccinationsToApi()` (фиксированный
   порядок delete → update → create, см.
   [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
6. `_deleteVaccinationFromApi()`:
   1. `vaccinations = await getDeletableVaccinationsWithDetails()` →
      `VaccinationsDao.getDeletableVaccinationsWithDetails` — `SELECT` с
      джойнами (`vaccine`, `unit`, `injectionMethod`, `injectionPlace`,
      `vaccinationType`), отфильтрованный по `sync == false && deletedAt !=
      null && updatedAt == null && createdAt == null`, сгруппированный по
      `id`. Для каждой строки, прошедшей фильтр, дополнительно вызывается
      `db.animalsDao.getAnimalWithDetailsById(vaccination.animalId)` и
      `_getDiseasesByLink(vaccination.id)`; строка попадает в итоговый список
      `VaccinationWithDetails`, **только если** `animalWithDetails != null` —
      иначе тихо пропускается (см. «Альтернативные потоки»).
   2. В этом (`DELETE_OK`) сценарии список непустой — в противном случае метод
      вернулся бы немедленно, не выполнив ни одного сетевого вызова
      (вырожденный случай, практически всегда истинный сегодня, см. «Открытые
      вопросы»).
   3. `rpcClientSHTP = getIt.get<ApiClient>(instanceName: 'farm_rpc')`;
      формируется `ApiMessage(link: '${Constants.registrationServiceApi}
      /vaccination-group-actions', method: ApiMethod.delete, headers:
      {"Accept-Language": LanguageService.locale}, data: {'ids': vaccinations
      .map((e) => e.shtpId).toList()})` — **один** батч-запрос со списком
      `shtpId` всех отобранных строк сразу, не цикл из отдельных запросов на
      каждую.
   4. `response = await rpcClientSHTP.call(message)`.
   5. `if (((response['errors'] ?? {}) as Map).isNotEmpty) throw
      Exception(...)` — в этом (`DELETE_OK`) сценарии условие ложно (`errors`
      пуст или отсутствует), исключение не бросается.
   6. Метод завершается штатно (`return` из конца `try`) — **никакой локальной
      мутации БД внутри `_deleteVaccinationFromApi` не происходит вообще**, ни
      при успехе, ни при отказе: не вызывается ни `deleteById`, ни
      `dao.upd*`, флаг `sync`/поле `deletedAt` отобранных строк не меняются
      этим методом ни в каком случае.
7. Управление возвращается в `syncVaccinations`, который продолжает
   безусловно (независимо от исхода шага 6) — `_updateVaccinationFromApi()`
   затем `_sendVaccinationsToApi()` ([EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md),
   [EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md) —
   вне рамок этого use-case).
8. `vaccinationsWithErrors = await _getNotSyncVaccinations()` →
   `VaccinationsDao.getNotSyncVaccinations` — `SELECT * FROM vaccinations
   WHERE sync = false`, без фильтра по `deletedAt`/`updatedAt`/`createdAt`.
   Снимок делается **после** трёх push-вызовов, но **до** следующего шага —
   и всё ещё включает строку(и), только что успешно удалённую(ые) на сервере
   шагом 6, потому что ничто в `_deleteVaccinationFromApi` не поменяло их
   `sync`/`deletedAt`.
9. `await dao.clear()` → `BaseDao.clear` = `delete(_currentTableInfo).go()` —
   безусловно удаляет **все** строки локальной таблицы `Vaccinations`, не
   только синхронизированные/удаляемые.
10. `await _getVaccinationsFromApi()` — постраничный `GET
    .../vaccinations`, вставка каждой полученной строки в (теперь пустую)
    таблицу. Так как в этом сценарии удаление на сервере реально произошло,
    удалённая вакцинация отсутствует в этом ответе и не попадает в таблицу
    отсюда.
11. `if (!isDeleteErrors) dao.insAll(vaccinationsWithErrors)` —
    `isDeleteErrors` по умолчанию `false`, и единственный реальный вызывающий
    (`DataUpdateBloc._syncAllData`, шаг 4 выше: `syncVaccinations(true)`, без
    именованного аргумента) никогда не передаёт `true` — эта ветка **всегда**
    выполняется в поставляемом приложении. `BaseDao.insAll` = `batch
    .insertAll(_currentTableInfo, list, mode: InsertMode.insertOrReplace)` —
    вставляет обратно ровно те же объекты `Vaccination`, что были сняты на
    шаге 8, с теми же `id`, `deletedAt`, `sync == false`, `updatedAt == null`,
    `createdAt == null` — включая строку, только что успешно удалённую на
    сервере.

Итоговый наблюдаемый эффект в локальной БД к концу этого (`DELETE_OK`) прохода:
строка `Vaccination`, для которой сервер подтвердил удаление, **возвращается
в локальную таблицу в точности в том же виде**, в каком была до начала
прохода — `deletedAt` всё ещё установлен, `sync` всё ещё `false`. На следующем
полном sync-проходе она снова пройдёт фильтр
`getDeletableVaccinationsWithDetails()` и будет отправлена в `DELETE`-батче
повторно, для того же `shtpId`.

### Альтернативные потоки

- **`getDeletableVaccinationsWithDetails()` пуст** — `_deleteVaccinationFromApi`
  возвращается немедленно, ни один сетевой вызов не выполняется. Это
  вырожденный случай, но на сегодня — практически всегда истинный (см.
  «Открытые вопросы»), не этот сценарий.
- **`animalId` строки не резолвится** (`getAnimalWithDetailsById` вернул
  `null`) — строка тихо исключается из результата
  `getDeletableVaccinationsWithDetails()`, даже если `sync`/`deletedAt`/
  `updatedAt`/`createdAt` полностью подходят под фильтр. Она не попадёт ни в
  один `DELETE`-батч, пока это условие не изменится — никакой ошибки или
  диагностики нигде не появляется.
- **Ответ содержит непустой `errors`, либо сам вызов бросает исключение** —
  перехватывается внутри `_deleteVaccinationFromApi` (`catch` без `rethrow`),
  логируется через `Talker`, sync pass продолжается к update/create-шагам как
  ни в чём не бывало. Отдельный сценарий, `RESULT = DELETE_ERROR`, не описан
  этим файлом (соответствующий тест уже существует, см. «Связанные тесты»).
- **Несколько удаляемых строк одновременно** — все их `shtpId` уходят в одном
  и том же батч-запросе, не по одному запросу на строку (тот же паттерн, что
  зафиксирован в [EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)).

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность сегмента `ENT`: её `deletedAt`/`sync`/`updatedAt`/`createdAt`
  читаются для отбора и (net) не меняются необратимо этим сценарием — строка
  переживает удачный серверный `DELETE` без потери локального состояния (см.
  «Основной поток», шаги 8–11).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  (`getAnimalWithDetailsById`) при сборке `VaccinationWithDetails`; наличие
  резолвящегося животного — обязательное условие включения строки в батч
  (см. «Альтернативные потоки»); поля самого `Animal` этим сценарием не
  изменяются.
- `Disease` (через связочную таблицу `DiseasesVaccinations`, `_getDiseasesByLink`) —
  читается при сборке `VaccinationWithDetails`, но не входит в тело
  `DELETE`-запроса (там уходит только список `shtpId`) и не изменяется; не
  имеет собственного `ENT` в этом дереве спек (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Связи»).
- `Vaccine`, `Unit`, `InjectionMethod`, `InjectionPlace`, `VaccinationType` —
  VAC-локальные справочники, join'ятся в `getDeletableVaccinationsWithDetails`
  для сборки `VaccinationWithDetails`, но не влияют на исход и не входят в
  `DELETE`-payload; тоже без собственного `ENT` (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Связи»).

### Бизнес-правила

- Push отправляется одним батч-запросом на все подходящие строки сразу, не
  циклом отдельных запросов на каждую.
- Условие отбора строки в батч — комбинация ровно четырёх полей:
  `sync == false`, `deletedAt != null`, `updatedAt == null`, `createdAt ==
  null`, плюс отдельное (silent) требование резолвящегося `animalId`.
- Ошибка на этом шаге (исключение или непустой `errors`) перехватывается
  внутри `_deleteVaccinationFromApi` и не прерывает остаток
  `syncVaccinations` — update/create-шаги того же прохода выполняются
  независимо от исхода удаления.
- **«Ни одна неотправленная строка не теряется при полном sync-проходе»
  (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) применяется
  одинаково ко всем трём состояниям (новая/правка/удаление) и не различает
  «сервер подтвердил удаление» от «сервер отклонил/не увидел запрос»** —
  снимок `_getNotSyncVaccinations()` и последующий `insAll` не проверяют,
  был ли конкретно этот `deletedAt`-ряд успешно обработан шагом 6. Именно
  поэтому успешный серверный `DELETE` не приводит к необратимому исчезновению
  строки локально в этом же проходе.
- `_deleteVaccinationFromApi` не пишет и не читает признак «эта строка уже
  была отправлена на удаление в прошлом проходе» — при повторном проходе то
  же условие снова истинно, и батч формируется заново с тем же составом.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сам шаг полностью реализован и выполняется безусловно на каждом полном
sync-проходе, никаких недостающих веток кода. Единственное, чего нет, —
достижимого через живой UI пути наполнить `getDeletableVaccinationsWithDetails()`
непустым списком (см. «Открытые вопросы и ограничения») — это делает сценарий
практически ненаблюдаемым в текущей версии приложения, а не незавершённым в
коде.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>`, `_syncAuthData`, `updateAndSyncRegagro` | CURRENT | общий префикс полного sync-прохода до вакцинаций (проверка сети/авторизации, гейтинг повтора) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | вызывает `_vaccinationsRepository.syncVaccinations(true)` последним шагом, после movements/disposals/animals |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: delete → update → create → снимок `sync=false` → `dao.clear()` → pull → условный `insAll` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._deleteVaccinationFromApi` | CURRENT | сборка и отправка батч-`DELETE`, перехват ошибок без `rethrow`, без локальной мутации в любом исходе |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getDeletableVaccinationsWithDetails` | CURRENT | обёртка над `dao.getDeletableVaccinationsWithDetails` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getNotSyncVaccinations` | CURRENT | снимок всех `sync == false` строк до `dao.clear()` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getVaccinationsFromApi` | CURRENT | постраничный pull после `dao.clear()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getDeletableVaccinationsWithDetails` | CURRENT | отбор по `sync==false && deletedAt!=null && updatedAt==null && createdAt==null`, join'ы, фильтр по резолвящемуся `animalId` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | `SELECT * FROM vaccinations WHERE sync = false`, без разбора состояний |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.markVaccinationForDeletion` | CURRENT | единственный способ выставить `deletedAt` — недостижим из живого UI (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear`, `BaseDao.insAll` | CURRENT | безусловное удаление всех строк таблицы; батч-вставка `insertOrReplace` тем же набором объектов |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | резолв животного строки — жёсткий фильтр включения в батч |
| `lib/network/api_client/api_client.dart` | `ApiClient.call` | CURRENT | абстрактный контракт сетевого вызова |
| `lib/injection_container.dart` | регистрация `getIt` для `instanceName: 'farm_rpc'` | CURRENT | связывает `'farm_rpc'` `ApiClient` с реальной реализацией |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый URL для эндпоинта `/vaccination-group-actions` |
| `lib/pages/vaccination_card/vaccination_card_page.dart` | `VaccinationCardPage` | CURRENT | единственный (недостижимый) вызывающий сайт `markVaccinationForDeletion` |

## Критерии приёмки

- Если на момент выполнения `_deleteVaccinationFromApi` в БД есть хотя бы одна
  строка `Vaccination` с `sync == false && deletedAt != null && updatedAt ==
  null && createdAt == null` и резолвящимся `animalId`, выполняется ровно один
  `DELETE {registrationServiceApi}/vaccination-group-actions` с телом `{'ids':
  [...]}`, содержащим `shtpId` всех таких строк разом.
- Если ответ на этот запрос не содержит непустого `errors`, метод завершается
  без исключения и без какой-либо прямой мутации таблицы `Vaccinations`.
- Независимо от предыдущего пункта, к концу того же вызова
  `syncVaccinations` строка, которая была отобрана в батч, снова присутствует
  в локальной таблице с теми же `id`/`deletedAt`/`sync == false`/`updatedAt
  == null`/`createdAt == null`, что и до начала прохода — если только
  `syncVaccinations` не был вызван с `isDeleteErrors: true` (на реальном
  вызывающем сайте не встречается).
- Пул-шаг (`_getVaccinationsFromApi`) не возвращает удалённую на сервере
  вакцинацию в GET-ответе; её повторное появление в локальной таблице
  объясняется исключительно шагом снимок-`clear`-`insAll`, не пул-запросом.

## Связанные тесты

`TBD — теста нет` на успешный (без ошибки) `DELETE`-push: в
`test/repositories/vaccinations_repository_test.dart` есть group `'UC-70 —
VaccinationsRepository.syncVaccinations(isFullSync: true) — delete push'`
(старая нумерация, переименуется отдельным контролируемым проходом — не
трогать сейчас), но оба её теста (`'DELETE падает -> исключение не
пробрасывается наружу (catch без rethrow)'` и `'НАХОДКА: строка тоже НЕ
теряется при сбое DELETE ...'`) настраивают мок `farm_rpc` так, что именно
`DELETE`-вызов бросает исключение — это покрывает соседний `RESULT =
DELETE_ERROR`, не этот (`DELETE_OK`) файл. Ни один существующий тест не
проверяет ветку, где `DELETE`-вызов успешен (мок возвращает ответ без
`errors`), и что именно происходит со строкой дальше по цепочке
снимок/`clear`/pull/`insAll`.

Смежные (не покрывающие этот файл) группы того же файла:
`'НАХОДКА — VaccinationsRepository.markVaccinationForDeletion — код рабочий,
но вызывается только из карточки вакцинации (vaccination_card), которая
недостижима из UI, см. ENT-7-VACCINATION-IN-ANIMAL'` — покрывает только
постановку `deletedAt` (предусловие этого сценария, не сам push); ссылка на
`ENT-7` в названии группы — устаревшая (docs-only) нумерация сущностей из
прежнего дерева спек, не текущий [ENT-7](../entities/ENT-7-GENERATION-TYPE-IN-HANDBOOKS.md)
(`GenerationType`, HANDBOOKS) этого дерева — тот `ENT-7` к вакцинации
отношения не имеет.

## Открытые вопросы и ограничения

- **Сценарий практически недостижим на реальных данных.**
  `VaccinationsRepository.markVaccinationForDeletion` — единственный способ
  выставить `deletedAt` — вызывается только из
  `lib/pages/vaccination_card/vaccination_card_page.dart`, чей маршрут
  (`Routes.vaccinationCard`) зарегистрирован в `lib/pages/routes.dart`, но
  нигде в `lib/` не открывается (`context.pushNamed2`/`context.go` на этот
  маршрут не встречаются — подтверждено `grep -rn` по `Routes.vaccinationCard`
  в `lib/`, единственное вхождение вне `routes.dart` — чтение `extra`-аргумента
  внутри самой `VaccinationCardPage`). Поэтому на практике
  `getDeletableVaccinationsWithDetails()` всегда пуст, и ранний `return` в
  `_deleteVaccinationFromApi` срабатывает почти на каждом реальном
  sync-проходе — батч-запрос, описанный этим файлом, в поставляемом
  приложении, по всей видимости, никогда не отправлялся. Единственный способ
  сегодня воспроизвести этот сценарий — вставить строку в БД напрямую (как
  делает `test/repositories/vaccinations_repository_test.dart`) либо
  дождаться изменения, которое сделает `VaccinationCardPage` достижимой.
- **Даже при достижимости успешный серверный `DELETE` не удаляет строку
  локально в том же проходе.** `_getNotSyncVaccinations()`/`insAll()` не
  различают «этот `deletedAt`-ряд только что был успешно отправлен» от
  «ещё не отправлен» — строка возвращается в таблицу в неизменном виде
  (см. «Основной поток», шаги 8–11) и будет отправлена повторно на следующем
  полном sync-проходе, для того же `shtpId`. Ведёт ли себя сервер идемпотентно
  на повторный `DELETE` уже удалённого `shtpId` — неизвестно из клиентского
  кода (внешний актор, вне рамок этого файла).
- **Silent-исключение по нерезолвящемуся `animalId`.** Если строка проходит
  фильтр по `sync`/`deletedAt`/`updatedAt`/`createdAt`, но её `animalId` не
  резолвится в `AnimalsDao.getAnimalWithDetailsById`, она никогда не попадёт
  ни в один `DELETE`-батч этим кодом — ни ошибки, ни лога, ни иного признака
  где-либо не появляется. Не воспроизведено как реальный сценарий на практике
  (сама достижимость исходного состояния уже маловероятна, см. первый пункт),
  зафиксировано только для полноты.
- Нет теста, покрывающего именно успешную ветку `_deleteVaccinationFromApi`
  (см. «Связанные тесты») — весь основной поток этого файла проверен только
  чтением кода, не исполнением.
