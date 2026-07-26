# UC-72 — Sync правки вакцинации отказывает: PUT падает, исключение проглатывается, строка не теряется (ERROR)

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Во время явного sync-прохода система отправляет на сервер локальные правки уже
синхронизированных вакцинаций (`updatedAt != null`) вторым push-шагом
([EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md),
`VaccinationsRepository._updateVaccinationFromApi`). Когда единый батч-запрос
`PUT .../vaccination-group-actions` падает — сетевым исключением либо ответом
с непустым `errors` — код перехватывает это внутри метода и не пробрасывает
исключение наружу: sync-проход безусловно продолжается к следующему,
create-шагу того же `syncVaccinations`. В отличие от аналогичных ERROR-сценариев
у Place ([UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)) и Animal
([UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)), где
непосредственно следующий шаг того же прохода (безусловный reload) стирает
непринятую правку до конца прохода, у Vaccination строка **не теряется**: тот
же `syncVaccinations` явно считывает все ещё не синхронизированные строки в
память до `dao.clear()` и вставляет их обратно после пересборки таблицы —
строка остаётся тем же `pending_edit` (тот же `updatedAt`, `sync=false`) и
будет предложена к отправке снова на следующем полном проходе.

**Важная оговорка, проверенная по коду.** Предпосылка этого сценария —
существование в БД уже синхронизированной (`createdAt == null`) вакцинации с
`updatedAt != null` — на сегодня **не может возникнуть ни через один живой
экран приложения** (см. «Открытые вопросы»). Сценарий воспроизводится и
проверяется только репозиторным тестом, вставляющим такую строку напрямую в
БД — то же самое отмечено в самом [EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md)
и в инварианте «НАХОДКА» [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md).

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая внутри
уже запущенного полного sync-прохода (`DataUpdateBloc`), не человек и не
отдельное решение пользователя на этом шаге. Сам проход запускается человеком
до этого — `DataUpdateStartAll` диспатчится из `lib/pages/main/main_page.dart`,
`lib/pages/data_update/data_update_page.dart`,
`lib/pages/profile/presentation/profile_page.dart`,
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`,
`lib/pages/in_work/in_work_page.dart` (проверено `grep -rl
"DataUpdateStartAll(" lib/`) — сам механизм запуска прохода принадлежит модулю
`SYSTEM` (см. границу [MOD-4](../modules/MOD-4-ANIMAL.md)), здесь не
переопределяется.

## CURRENT

### Основной поток

1. **Предпосылка.** В таблице `Vaccinations` есть как минимум одна строка с
   `createdAt == null`, `updatedAt != null`, `sync == false` — «в правке»
   состояние по инварианту [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md).
   На сегодня в код это состояние может попасть только прямой вставкой в БД
   (репозиторный тест) — ни один живой путь UI его не создаёт (детали — ниже,
   «Открытые вопросы»).
2. Пользователь запускает полный sync-проход из одной из точек входа выше.
   `DataUpdateBloc.on<DataUpdateStartAll>` проверяет сеть, затем
   (авторизованный пользователь) вызывает `_syncAuthData` →
   `updateAndSyncRegagro` → `_syncAllData`.
3. `_syncAllData` выполняет фиксированную последовательность шагов без
   ветвления по результату предыдущих, заканчивающуюся `await
   _vaccinationsRepository.syncVaccinations(true)` — последним шагом всего
   прохода (`isFullSync = true`, `isDeleteErrors` не передан → дефолт
   `false`; других вызовов `syncVaccinations` в `lib/` нет — проверено
   `grep -rn "syncVaccinations(" lib/`).
4. `syncVaccinations(true)` при `isFullSync == true` выполняет три push-шага
   строго по порядку: `_deleteVaccinationFromApi()` →
   `_updateVaccinationFromApi()` (этот сценарий) → `_sendVaccinationsToApi()`.
5. `_updateVaccinationFromApi()` вызывает
   `getEditableVaccinationsWithDetails()` → `VaccinationsDao
   .getEditableVaccinationsWithDetails` (`sync.isValue(false) &
   updatedAt.isNotNull()`) — получает список, включающий строку из шага 1.
   Список непустой, поэтому метод не завершается ранним `return`.
6. Строится один `PUT ${Constants.registrationServiceApi}
   /vaccination-group-actions` с телом `{'vaccinations': [...]}`, где каждый
   элемент — `VaccinationApiRequest.fromVaccinationWithDetails(e).toJson()`
   для **всех** editable-строк разом (не по одной в цикле).
7. `rpcClientSHTP.call(message)` бросает исключение (сеть/таймаут) — этот
   сценарий, соответствует тесту `'PUT падает -> исключение не пробрасывается
   наружу (catch без rethrow)'`.
8. Исключение перехватывается общим `catch (e, st)` метода:
   `getIt<Talker>().info('updateVaccinationFromApi Error: $e st: $st')` —
   только запись в лог. **Ни `errors`, ни `sync`, ни `updatedAt` строки не
   меняются этим catch-блоком** — в отличие от аналогичного ERROR-сценария
   Animal ([UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)),
   где отказ хотя бы временно записывается в `Animal.errors`; здесь нет вообще
   никакой записи в БД на этом шаге.
9. `_updateVaccinationFromApi()` завершается нормально (без исключения).
   `syncVaccinations` безусловно продолжает следующим шагом —
   `_sendVaccinationsToApi()` (create-шаг). Строка из шага 1 не попадает в его
   выборку (`getNotSyncVaccinationsWithDetails` фильтрует `updatedAt.isNull()`)
   — create-шаг эту строку не трогает и не видит.
10. `syncVaccinations` продолжает: `final vaccinationsWithErrors = await
    _getNotSyncVaccinations();` — `VaccinationsDao.getNotSyncVaccinations`
    фильтрует **только** по `sync.isValue(false)`, без разбора
    unsent-new/pending-edit/pending-delete — строка из шага 1 попадает в этот
    список как есть, с тем же `updatedAt`, `sync=false`.
11. `await dao.clear();` — `BaseDao.clear` = безусловный `DELETE` по всей
    таблице `Vaccinations`, без `WHERE`. Строка из шага 1 физически удаляется
    из таблицы на этом шаге (таблица `DiseasesVaccinations` не затрагивается).
12. `await _getVaccinationsFromApi();` — постраничный `GET
    .../vaccinations`, каждый элемент вставляется через
    `insert(vaccination.toCompanion())`. `VaccinationDtoMapper.toCompanion()`
    не указывает `id` (только `shtpId`) — локальный `id` назначается СУБД
    заново. `Vaccinations.id` объявлен как `integer().autoIncrement()`
    (истинный SQLite `AUTOINCREMENT`) — счётчик не переиспользует уже
    выданные значения после `clear()`, поэтому коллизии `id` с готовящейся к
    восстановлению строкой из шага 1 не происходит.
13. `if (!isDeleteErrors) dao.insAll(vaccinationsWithErrors);` —
    `isDeleteErrors` здесь `false` (шаг 3), поэтому эта ветка выполняется:
    `insAll` = батч `insertOrReplace` — так как объект `Vaccination`,
    считанный на шаге 10, несёт свой оригинальный `id`, строка вставляется
    обратно **с тем же `id`, тем же `updatedAt`, тем же `sync=false`** — как
    будто `clear()`/reload её не касались. Вызов **не awaited** (последняя
    строка асинхронного метода без `await`) — собственный `Future` метода
    `syncVaccinations` может резолвиться раньше, чем фактически завершится
    эта вставка (см. «Открытые вопросы»).
14. Весь проход эмитит `DataUpdateSuccess` — `syncVaccinations(true)`
    последний шаг `_syncAllData`, ни один catch внутри него не пробросил
    исключение наружу к `on<DataUpdateStartAll>`. Отказ PUT нигде не виден
    пользователю: ни в UI, ни в состоянии animal-фильтров, нигде.
15. На следующем полном sync-проходе строка (не изменившаяся: тот же
    `updatedAt`, `sync=false`) снова будет выбрана
    `getEditableVaccinationsWithDetails()` — PUT будет предпринят повторно,
    без ограничения числа попыток и без экспоненциального backoff.

### Альтернативные потоки

- **Сервер отвечает, но с непустым `errors`** (без брошенного исключения на
  уровне транспорта): `if (((response['errors'] ?? {}) as Map).isNotEmpty)
  throw Exception(response['errors']);` — код сам конструирует исключение и
  бросает его внутри того же `try`, поэтому оно ловится тем же `catch (e,
  st)`, что и сетевой сбой шага 7. Формально это ближе к бизнес-отказу
  (сервер ответил и отклонил), а не к «не долетело» — но код не различает эти
  два технически разных случая никак, оба ведут к одному и тому же
  логированию и продолжению прохода. Как и в аналогичном сценарии Place
  ([UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)), оба
  технических подтипа фиксируются здесь как один и тот же `UPDATE_ERROR`,
  не разбиваются на отдельные use-case.
- **`getEditableVaccinationsWithDetails()` возвращает пустой список.**
  `if (vaccinations.isEmpty) return;` — метод завершается раньше формирования
  PUT-запроса; сценарий вообще не наступает (нет ни одной строки в правке).
- **В батче несколько editable-строк, отказывает не «своя», а общий запрос.**
  Поскольку весь батч уходит одним PUT (как у Place, не как у Animal, где
  цикл с отдельным вызовом на каждое животное —
  [UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)), отказ
  одного вызова затрагивает **все** editable-строки батча одинаково — партиал
  успеха на этом шаге не бывает: либо все они остаются `pending_edit`, либо
  (при успехе) ни одна.
- **`isDeleteErrors: true`.** Единственный продакшн-вызов
  (`DataUpdateBloc._syncAllData`) никогда не передаёт этот флаг — он всегда
  `false`. Если бы вызывающий код когда-либо передал `true`, шаг 13 не
  выполнился бы вовсе, и та же самая PUT-неудача обернулась бы
  безвозвратной потерей строки в том же проходе — противоположный исход
  тому, что документирован здесь как основной поток. Путь мёртв в
  сегодняшнем коде, но существует как параметр метода.
- **`dao.insAll(vaccinationsWithErrors)` не дожидается своего завершения**
  (шаг 13). Так как `syncVaccinations(true)` — последний шаг `_syncAllData`,
  ничто внутри самого этого прохода не читает таблицу `Vaccinations` после
  этой точки, поэтому гонка не проявляется в рамках одного прохода. Она
  теоретически возможна только для стороннего конкурентного чтения (открытый
  в этот момент экран вакцинаций) — не проверялась экспериментально.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  единственная сущность, чьё состояние меняется на всех этапах сценария: от
  неудачной попытки push (шаг 8, где ничего не меняется) до последующего
  `clear()`/reload/reinsert (шаги 11–13), сохраняющего исходное
  `pending_edit`-состояние строки без изменений.

### Бизнес-правила

- Push трёх состояний вакцинации идёт в фиксированном порядке delete → update
  → create в рамках одного `syncVaccinations`; update и delete отправляются
  батчем на весь подходящий набор строк разом, create — по одной записи за
  раз (инвариант [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
- `_updateVaccinationFromApi()` не пишет `errors` ни в каком случае отказа —
  единственный след отказа за пределами этого шага — то, что строка
  сохраняет свои nullable-флаги `pending_edit`-состояния неизменными; в этом
  смысле сценарий даже менее заметен, чем аналогичный у Animal
  ([UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)), где хотя
  бы временно записывается текст ошибки.
- Никакое исключение из `_updateVaccinationFromApi()` не покидает метод —
  `syncVaccinations` безусловно продолжает к create-шагу независимо от
  исхода update-шага.
- `_getNotSyncVaccinations()` (фильтр только по `sync=false`, без разбора
  трёх состояний) + `dao.clear()` + `dao.insAll(...)` — единственный механизм
  всего сценария, который явно защищает ещё не синхронизированные строки
  (в любом из трёх состояний, включая `pending_edit` этого сценария) от
  безусловного reload'а следующим шагом того же прохода. Это архитектурно
  отличается от Place ([UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md))
  и Animal ([UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)),
  где эквивалентный reload ничего не сохраняет заранее и стирает
  непринятую правку безвозвратно в том же проходе.
- Строка, чей PUT не прошёл, будет автоматически предложена к отправке
  повторно на каждом следующем полном sync-проходе — без ограничения числа
  попыток, без backoff, без какого-либо признака «эта строка часто
  отказывает», видимого пользователю или коду.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — весь сценарий, включая взаимодействие update-шага с
последующим create-шагом и с механизмом
capture-clear-pull-reinsert, прослеживается по существующему коду без
пробелов, требующих уточнения у пользователя. Единственная содержательная
оговорка — недостижимость предпосылки сценария из живого UI — зафиксирована
не как пробел, а как факт CURRENT-поведения в «Открытые вопросы и
ограничения».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешний `try/catch` всего прохода; отказ, проглоченный внутри `syncVaccinations`, до него не долетает — проход завершается `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` / `updateAndSyncRegagro` | CURRENT | цепочка вызовов к `_syncAllData`, только для авторизованного пользователя |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | фиксированная последовательность шагов, заканчивающаяся `await _vaccinationsRepository.syncVaccinations(true)` — последний шаг всего прохода, без собственного try/catch вокруг него |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations` | CURRENT | оркестрация: delete→update→create push, затем `_getNotSyncVaccinations()` → `dao.clear()` → `_getVaccinationsFromApi()` → условный `dao.insAll(...)` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._updateVaccinationFromApi` | CURRENT | ядро сценария: один batch `PUT .../vaccination-group-actions`, `catch (e, st)` без `rethrow`, только `Talker.info(...)`, никаких изменений в БД |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._sendVaccinationsToApi` | CURRENT | следующий (create) шаг, выполняется безусловно после update-шага; строку этого сценария не видит (фильтр `updatedAt IS NULL`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getNotSyncVaccinations` | CURRENT | захват всех `sync=false` строк (любое из трёх состояний) непосредственно перед `dao.clear()` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository._getVaccinationsFromApi` | CURRENT | постраничный pull с сервера; вставка через `toCompanion()` без `id` — назначается СУБД заново |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getEditableVaccinationsWithDetails` | CURRENT | источник PUT-батча: делегирует в DAO-фильтр `sync=false & updatedAt IS NOT NULL` |
| `lib/repositories/vaccination/vaccination_api_request.dart` | `VaccinationApiRequest.fromVaccinationWithDetails` | CURRENT | сборка одного элемента тела PUT-запроса из `VaccinationWithDetails` |
| `lib/repositories/base_repository.dart` | `BaseRepository.paginatedRequestHandler` | CURRENT | постраничный обход GET-эндпоинта, используемый `_getVaccinationsFromApi` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getEditableVaccinationsWithDetails` | CURRENT | DAO-запрос: `sync.isValue(false) & updatedAt.isNotNull()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | DAO-запрос create-шага: `sync.isValue(false) & updatedAt.isNull()` — исключает строку этого сценария |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinations` | CURRENT | DAO-запрос захвата перед `clear()`: только `sync.isValue(false)`, без разбора состояний |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` / `BaseDao.insAll` | CURRENT | drift-примитивы: `clear` — безусловный `DELETE` по всей таблице, `insAll` — батч `insertOrReplace`, сохраняющий переданный `id` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations.id` | CURRENT | `integer().autoIncrement()` — истинный SQLite `AUTOINCREMENT`, не переиспользует id после `clear()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDtoMapper.toCompanion` | CURRENT | конвертация серверного DTO в `VaccinationsCompanion`; `id` не указывается, только `shtpId` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditBloc._onSave` | CURRENT | единственная ветка кода, теоретически способная выставить `updatedAt` на уже синхронизированной строке; недостижима на практике (см. ниже) |
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | (список на основе `getNotSyncVaccinationsWithDetails()`) | CURRENT | вход `Routes.unsentVaccinationEdit` ведёт только к строкам `createdAt != null` — их `_onSave` не устанавливает `updatedAt` |
| `lib/pages/vaccination_card/vaccination_card_page.dart` | `VaccinationCardPage` | CURRENT | единственный экран, ведущий к `Routes.unsentVaccinationEditFromEditable` (ветке, устанавливающей `updatedAt`); сам недостижим — `Routes.vaccinationCard` нигде не пушится (проверено `grep -rln "Routes.vaccinationCard" lib/`) |
| `lib/pages/routes.dart` | `Routes.vaccinationCard` / `Routes.unsentVaccinationEdit` / `Routes.unsentVaccinationEditFromEditable` | CURRENT | константы маршрутов, подтверждающие тупиковую навигационную цепочку |
| `lib/pages/main/main_page.dart`, `lib/pages/data_update/data_update_page.dart`, `lib/pages/profile/presentation/profile_page.dart`, `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`, `lib/pages/in_work/in_work_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | точки входа полного sync-прохода, внутри которого наступает этот сценарий |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API, используемый PUT-запросом этого сценария |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент PUT-вызова и последующего pull-запроса |

## Критерии приёмки

- Если `getEditableVaccinationsWithDetails()` возвращает ≥1 строку и вызов
  `rpcClientSHTP.call(message)` внутри `_updateVaccinationFromApi()` бросает
  исключение (или ответ содержит непустой `errors`) — метод завершается без
  исключения (`completes`, а не `throwsA(...)`).
- Строка, участвовавшая в неудавшемся PUT, не получает изменений `errors`/
  `sync`/`updatedAt` от самого `_updateVaccinationFromApi()` — проверяемо
  чтением строки сразу после вызова, до следующих шагов `syncVaccinations`.
- `syncVaccinations(true)` при отказе update-шага всё равно выполняет
  безусловный `GET`-запрос дальше по цепочке (`_getVaccinationsFromApi`) —
  проверяемо тем, что среди перехваченных вызовов мока есть как минимум один
  `ApiMethod.get`.
- После полного вызова `syncVaccinations(true)`, где PUT отказал, строка
  присутствует в БД ровно один раз, с тем же `updatedAt` и `sync == false`,
  что были у неё до вызова — не потеряна и не задублирована.
- Полный `DataUpdateStartAll`, содержащий этот сценарий, завершается
  `DataUpdateSuccess`, не `DataUpdateFailure`.
- На следующем вызове `syncVaccinations(true)` та же строка снова
  присутствует среди результата `getEditableVaccinationsWithDetails()` —
  повторная попытка PUT предпринимается автоматически, без ограничения
  числа попыток.

## Связанные тесты

`test/repositories/vaccinations_repository_test.dart`, группа `'UC-72 —
VaccinationsRepository.syncVaccinations(isFullSync: true) — edit push'`
(старая нумерация в названии группы, будет переименовано отдельным проходом,
не трогать сейчас) — содержит ровно два `test()`, оба процитированы точно как
они называются в файле сейчас:

- `'PUT падает -> исключение не пробрасывается наружу (catch без rethrow)'` —
  вставляет строку `id: 3, shtpId: 300, createdAt: null, updatedAt:
  DateTime(2026, 7, 10)`, мокает `farmRpcClient.call` так, чтобы бросать
  исключение для `ApiMethod.put` и отвечать `{'data': []}` для остальных
  методов, затем `await expectLater(repository.syncVaccinations(true),
  completes);` и проверяет, что среди перехваченных вызовов есть и `put`, и
  `get`.
- `'НАХОДКА: строка НЕ теряется при сбое PUT — getNotSyncVaccinations()/
  insAll() возвращают её ровно в том же pending_edit виде (тот же updatedAt,
  sync=false), т.к. getNotSyncVaccinations() фильтрует только по sync=false,
  без разбора unsent-new/pending_edit/pending_delete'` — та же настройка
  мока, но после `await repository.syncVaccinations(true);` проверяет, что
  `db.vaccinationsDao.getAll()` возвращает ровно одну строку
  (`hasLength(1)`), с тем же `updatedAt` (`editedAt`) и `sync == false`.

## Открытые вопросы и ограничения

- **Предпосылка сценария недостижима из живого UI.** `UnsentVaccinationEditBloc
  ._onSave` устанавливает `updatedAt` только в ветке `_data.vaccination
  ?.createdAt == null` (то есть когда редактируется уже синхронизированная
  запись) — но единственный вход в этот блок с уже синхронизированной
  записью, `Routes.unsentVaccinationEditFromEditable`, пушится только из
  `VaccinationCardPage` (`lib/pages/vaccination_card/vaccination_card_page.dart`,
  строка навигации на `Routes.unsentVaccinationEditFromEditable`). Сам
  `VaccinationCardPage` недостижим: `grep -rln "Routes.vaccinationCard" lib/`
  находит только `routes.dart` (объявление маршрута) и сам
  `vaccination_card_page.dart` (где `Routes.vaccinationCard` используется
  лишь для чтения собственных `extra`-аргументов через `getExtraByName`, не
  для навигации) — ни один другой файл `lib/` не вызывает
  `context.pushNamed2(Routes.vaccinationCard, ...)` или аналог. Второй вход,
  `Routes.unsentVaccinationEdit` (из `unsent_vaccination_page.dart`, список —
  `getNotSyncVaccinationsWithDetails()`), по определению этой выборки
  содержит только строки `createdAt != null` — для них `_onSave` пишет
  `Value.absent()` вместо `updatedAt`, эта ветка тоже не может создать
  предпосылку сценария. Совпадает с тем, что уже зафиксировано в
  [EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md) и
  инварианте «НАХОДКА» [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md).
  На практике этот сценарий воспроизводим только тестом, вставляющим строку
  напрямую в БД (см. «Связанные тесты») — вопрос пользователю: считать ли
  сам путь `updatedAt`-правки вакцинации мёртвым кодом, требующим удаления
  или починки навигации, вне периметра этой документирующей задачи.
- **RESULT-неоднозначность внутри одного и того же catch.** «Сервер ответил
  непустым `errors`» (по строгому словарю `RESULT` —
  [use-cases/AGENTS.md](AGENTS.md), «REJECTED» — операция дошла до сервера и
  сознательно отклонена) и «вызов упал исключением» (по тому же словарю —
  «ERROR», операция не дошла) обрабатываются кодом `_updateVaccinationFromApi`
  совершенно одинаково: оба заканчиваются в одном `catch (e, st)` без
  различения причины. Зафиксировано здесь как факт, не устраняется —
  использован прецедент [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md),
  где аналогичное объединение двух технических подтипов уже задокументировано
  тем же образом.
- **Полная невидимость отказа.** В отличие от Animal
  ([UC-53](UC-53-ACTOR-4-EVT-26-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)), где отказ
  хотя бы на мгновение записывается в `Animal.errors` (потенциально видимое
  пользователю поле, пусть и стираемое следующим шагом), у Vaccination
  `_updateVaccinationFromApi` не пишет вообще ничего в БД при отказе —
  единственный след — `Talker.info(...)` в логах приложения, недоступных
  обычному пользователю.
- **Гонка от неawait-нутого `dao.insAll(...)`.** Шаг 13 основного потока не
  дожидается завершения вставки — теоретически конкурентное чтение таблицы
  `Vaccinations` в этом узком окне (например, открытый в этот момент экран
  вакцинаций) может увидеть таблицу без этой строки. Не проявляется в
  рамках самого sync-прохода (это последний шаг `_syncAllData`), не
  проверялось экспериментально для конкурентного UI-чтения.
- **Бесконечный автоматический повтор без сигнала пользователю.** Ничто не
  ограничивает число повторных попыток PUT для одной и той же строки и не
  помечает её как «часто отказывающую» — при системной проблеме на сервере
  (например, вечно некорректных данных строки) она будет предприниматься на
  каждом полном проходе неопределённо долго, без backoff и без какого-либо
  UI-индикатора.
- **`isDeleteErrors: true` как незащищённый мёртвый параметр.** Сегодня
  единственный вызывающий код (`DataUpdateBloc._syncAllData`) всегда
  передаёт `false`, поэтому строка защищена. Если этот параметр когда-либо
  будет передан как `true` из нового вызывающего кода, ровно тот же самый
  отказ PUT приведёт к обратному исходу — безвозвратной потере строки в том
  же проходе, без какого-либо предупреждения в самом методе
  `syncVaccinations` о том, что это меняет гарантию сохранности
  неотправленных строк. Вне периметра этой документирующей задачи.
