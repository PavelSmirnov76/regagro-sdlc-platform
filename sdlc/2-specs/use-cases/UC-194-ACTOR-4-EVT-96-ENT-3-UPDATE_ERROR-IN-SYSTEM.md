# UC-194 — Сбой в середине `loadDirectories` пишется в журнал под категорией, оставшейся от предыдущего прохода, а уже применённые справочники остаются частично обновлёнными

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

`DataUpdateBloc.loadDirectories` (см. [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md))
синхронизирует ~18-19 справочников HANDBOOKS одним последовательным `await`-цепочкой
внутри одного метода: `countries → kinds → breeds → suits → breedSuits →
disposalReasons → [vaccines+units, условно] → diseases → complexVaccines →
injectionPlaces → injectionMethods → vaccinationTypes → generationsTypes →
ageGroups → markerTypes → markerPlaces → kindMarkerPlaces → absenceReasons`.
Этот документ фиксирует, что происходит, когда один из справочников
где-то в середине этой цепочки (не первый и не последний) бросает исключение —
что уже подтверждено чтением кода технической задачей на этот проход, и что
отдельно проверено здесь: (а) есть ли у `loadDirectories` собственный
`try/catch`, отдельный от общего `catch` `on<DataUpdateStartAll>`; (б) в каком
состоянии остаются уже обработанные справочники; (в) под какой именно
категорией строка об ошибке фактически попадает в
[ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (`DataUpdates`).

Ответ по каждому пункту, подтверждённый чтением
`lib/blocs/data_update/data_update_bloc.dart`:

- **(а) — да, у `loadDirectories` есть собственный `try/catch`**, но он ничего
  не делает: `catch (e) { rethrow; }` — просто перебрасывает исключение выше,
  не логируя, не записывая ничего под конкретной категорией/ключом справочника,
  не отличаясь по эффекту от отсутствия try/catch вовсе. Единственное место,
  которое реально пишет строку в `DataUpdates` при ошибке — общий
  `catch (error, stackTrace)` блока `on<DataUpdateStartAll>`, вызывающий
  `_emitError` → `_addDataUpdateError`.
- **(б) — да, уже обработанные справочники остаются частично обновлёнными.**
  Каждый справочник синхронизируется своим отдельным `clearAndInsertAll`/`insAll`
  вызовом (`BaseDao.clearAndInsertAll`, `BaseDao.insAll` —
  `packages/sheep_farm_database/lib/entities/base_dao.dart`), и **каждый из них
  обёрнут в свою собственную независимую Drift-транзакцию** — нет ни одной
  транзакции, охватывающей весь `loadDirectories` целиком. Значит, если
  справочник №6 (из ~18-19) бросает исключение, справочники №1-5 уже
  зафиксированы в БД — их транзакции успешно завершились раньше и не
  откатываются отказом шестого.
- **(в) — записанная категория ошибки почти никогда не `directories` и почти
  никогда не соответствует справочнику, который реально отказал.** Категория
  берётся из `_currentDataCategory` — общего изменяемого поля инстанса
  `DataUpdateBloc` (`DataCategory _currentDataCategory = DataCategory.directories;`),
  а не из локальной переменной метода. Внутри `loadDirectories` эта категория
  переустанавливается ровно один раз — на `DataCategory.generationsTypes`, на
  шаге `generationsTypes` (14-м из ~18-19) — и до этого шага остаётся тем,
  чем была **до входа в `loadDirectories`**. Поскольку `loadDirectories` —
  самый первый доменный шаг `on<DataUpdateStartAll>`, «до входа» означает: то,
  чем `_currentDataCategory` осталось **в конце предыдущего полного прохода**
  этого же (долгоживущего, см. «Технические зависимости») инстанса блока. См.
  «Основной поток» — конкретный прогон с указанием, какая именно категория
  фактически попадёт в строку.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Сам проход запущен раньше человеком, но без участия
человека на уровне отдельного сетевого вызова к конкретному справочнику
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), «Идентичность»). Инициатором
самого прохода мог быть как [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)
(ручной запуск — кнопка обновления в `main_page.dart`,
`profile_settings_view.dart`, `in_work_page.dart`, `data_update_page.dart`),
так и [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) (автозапуск при холодном
старте) — `loadDirectories` вызывается безусловно в обоих случаях, для гостя и
авторизованного пользователя одинаково (см. [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)).
Сам отказ этого сценария наступает без какого-либо действия человека в этот
момент.

## CURRENT

### Основной поток

Иллюстративный прогон: это **не первый** полный проход `DataUpdateBloc` с
момента запуска процесса приложения (инстанс блока создаётся один раз, в
`MyApp.build` — `BlocProvider<DataUpdateBloc>(create: (context) => DataUpdateBloc())`,
`lib/main.dart` — и живёт всё время работы приложения), т.е. до этого прогона
уже был как минимум один успешный полный проход.

1. Успешно завершившийся предыдущий проход дошёл (через
   `_syncAuthData → updateAndSyncSHTP → loadShtp`) до последней в
   хронологии вызова строки, реально переустанавливающей
   `_currentDataCategory` за весь проход — `_emitProgress(..., dataCategory: DataCategory.reports)`
   внутри `loadShtp` (`DataKey.reports`/`DataCategory.reports`) — и сразу же
   записал `_addDataUpdateSuccess(_currentDataCategory)` под этой категорией.
   Проход завершился `DataUpdateSuccess`. `_resetProgressCounters()` (вызывается
   в начале каждого `on<DataUpdateStartAll>`) — **пустое тело**
   (`void _resetProgressCounters() {}`), не сбрасывает `_currentDataCategory`
   ни между шагами одного прохода, ни между проходами. К концу предыдущего
   прохода `_currentDataCategory == DataCategory.reports` — и остаётся таким,
   пока что-то явно его не переустановит.
2. Пользователь ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) или автозапуск
   [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)) инициирует новый
   `DataUpdateStartAll`. Проверка сети проходит. `_currentDataCategory`
   по-прежнему равно `DataCategory.reports` — значение шага 1, ничем не
   тронутое между проходами.
3. `loadDirectories(event, emit)` вызывается — первый доменный шаг нового
   прохода. `lastSyncDate = AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
   — не `null` (сохранён по итогу предыдущего успешного прохода, см. шаг 9),
   `isIncremental == true`.
4. `_countriesRepository.syncCountries(updatedAtGt: lastSyncDate)` —
   успешно.
5. `kinds`, `breeds`, `suits` — каждый: `_emitProgress(dataKey: ...)`
   **без** `dataCategory` (ни один из этих трёх вызовов не передаёт
   именованный параметр `dataCategory`), затем `getXFromApi` + `insertAll`
   (инкрементальный upsert, т.к. `isIncremental == true`) — все три успешны,
   каждый в своей отдельной транзакции (`BaseDao.insAll` → `batch(...)`).
   `_currentDataCategory` по-прежнему `DataCategory.reports` — ни один из этих
   шагов его не меняет.
6. `breedSuits` — для этого справочника `loadDirectories` вовсе не вызывает
   `_emitProgress` (ни `dataKey`, ни `dataCategory`) — успешный
   `getBreedSuitsFromApi` + `insertAll`, целиком без прогресс-события.
   Пять справочников (`countries`, `kinds`, `breeds`, `suits`, `breedSuits`)
   к этому моменту уже зафиксированы в БД своими отдельными транзакциями.
7. `_emitProgress(emit: emit, dataKey: DataKey.disposalReasons)` — **это
   единственная точка**, где `_currentDataKey` становится `'disposalReasons'`;
   `dataCategory` этим вызовом по-прежнему не передаётся.
   `_disposalReasonsRepository.getDisposalReasonsFromApi(updatedAtGt: lastSyncDate)`
   (`lib/repositories/disposal_reason/disposal_reasons_repository.dart`)
   бросает исключение (сетевой сбой/таймаут/`DioException` — конкретная
   причина для этого сценария не важна, важно только то, что исключение
   долетает до вызывающего кода).
8. Исключение всплывает через `loadDirectories`'s собственный `try` — его
   `catch (e) { rethrow; }` не делает ничего, кроме повторного `throw`, — и
   продолжает всплытие до единственного реального обработчика, `catch (error, stackTrace)`
   блока `on<DataUpdateStartAll>`. `_loadBoardDirectories` и `_syncAuthData`
   **не вызываются вовсе** — исключение оборвало проход раньше, чем до них
   дошла очередь.
9. `_emitError(emit: emit, error: error, stackTrace: stackTrace)` вызывает
   `_addDataUpdateError(dataCategory: _currentDataCategory, errorDataKey: _currentDataKey, errorMessage: 'error: $error, stackTrace: $stackTrace')`.
   В таблицу `DataUpdates` пишется строка:
   `dataCategoryId = DataCategory.reports` (залежавшееся значение шага 1 —
   **не** `DataCategory.directories`, и вообще не относится к справочникам),
   `errorDataKey = 'disposalReasons'` (это, наоборот, верно — установлено
   шагом 7 непосредственно перед отказом). Одновременно `emit(DataUpdateFailure(errorTitleKey: 'an_error_data', errorMessageKey: 'disposalReasons', ...))`.
10. `DataUpdatePage._Body.build` (`lib/pages/data_update/data_update_page.dart`)
    показывает пользователю
    `'${AppLocalizations.of(context)!.tr('an_error_data')}\n${AppLocalizations.of(context)!.tr('disposalReasons')}'`.
    `tr('an_error_data')` резолвится в реальный переведённый текст
    (`"An error occurred while processing data"` и т.д. — `lib/l10n/app_en.arb`
    и другие `.arb`). `tr('disposalReasons')` — нет: `AppLocalizations.tr`
    (`lib/l10n/app_localization.dart`) не содержит `case 'disposalReasons':` —
    ни для одного из `DataKey`-констант, использованных в `loadDirectories`,
    кроме `'reports'`, нет своего `case`, у switch есть только
    `default: return key;` — так что пользователь видит буквально нетранслированную
    строку `disposalReasons` рядом с общим заголовком ошибки.
11. `AppCacheService.saveDirectoriesLastSyncDate(...)` (вызывается только в
    конце `loadDirectories`, **после** всех ~18-19 справочников) в этом
    прогоне не достигается вовсе — `lastSyncDate` для этой локали остаётся
    равным значению **до** этого прогона (тем же, что был на шаге 3).
12. Локальное состояние справочников после этого прогона: `countries`,
    `kinds`, `breeds`, `suits`, `breedSuits` — свежие (upsert применён);
    `disposalReasons` и всё, что шло бы после него в цепочке (`vaccines`/`units`
    при отсутствии несинхронизированных вакцинаций, `diseases`,
    `complexVaccines`, `injectionPlaces`, `injectionMethods`,
    `vaccinationTypes`, `generationsTypes`, `ageGroups`, `markerTypes`,
    `markerPlaces`, `kindMarkerPlaces`, `absenceReasons`) — не тронуты этим
    прогоном вовсе, остаются в состоянии **до** него. Ни одна строка
    `DataUpdates`/иной таблицы не помечает эту смесь как частично
    обновлённую — единственный след отказа — одна строка ошибки под
    неверной категорией (шаг 9).
13. Следующий `DataUpdateStartAll` (ручной повтор [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)
    или автозапуск [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)) снова начинает
    `loadDirectories` с `countries` — прогресса, «докатывающего» именно с
    `disposalReasons`, не существует: цепочка всегда идёт с начала. `lastSyncDate`
    по-прежнему равен значению до отказавшего прогона (шаг 11), поэтому
    `countries`/`kinds`/`breeds`/`suits`/`breedSuits` отправляются на upsert
    заново с тем же `updatedAtGt` — избыточно, но не разрушительно
    (`insertAll`/upsert идемпотентен). Если на этот раз сеть/сервер
    восстановились, вся цепочка проходит целиком, `saveDirectoriesLastSyncDate`
    наконец выполняется, `_addDataUpdateSuccess(_currentDataCategory)`
    пишет успешную строку под `DataCategory.generationsTypes` (уже описанный в
    [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) отдельный дефект) — частично
    устаревшие справочники «самоисцеляются» к консистентному состоянию.
    Если же конкретно `disposalReasons`-эндпоинт систематически отказывает
    (не разовый сетевой сбой, а стабильная ошибка), каждый последующий проход
    повторяет ровно тот же паттерн: справочники №1-5 бесполезно, но безвредно
    переприменяются заново, справочники №6-19 остаются недостижимы бесконечно
    — `lastSyncDate` не продвигается никогда, инкрементальный режим для
    справочников не наступает никогда, пока этот конкретный отказ не
    исчезнет.

### Альтернативные потоки

- **Отказ на самом первом прогоне процесса приложения (единственный случай,
  когда категория `directories` реально попадает в `DataUpdates` — как
  ошибка, не как успех).** Если это первый вызов `loadDirectories` с момента
  создания инстанса `DataUpdateBloc` (т.е. ни один `_emitProgress(dataCategory: ...)`
  ещё ни разу не выполнялся за всё время процесса), `_currentDataCategory`
  всё ещё равно значению по умолчанию поля класса —
  `DataCategory.directories`. Если отказ наступает **до** шага
  `generationsTypes` (например, тот же `disposalReasons`), строка ошибки в
  `DataUpdates` действительно получит `dataCategoryId = DataCategory.directories`.
  Это единственный путь, которым эта категория вообще может появиться в
  таблице — и то только как строка **ошибки**, никогда как строка успеха
  (см. «Открытые вопросы» — нюанс к формулировке
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)).
- **Отказ на шаге, для которого `_emitProgress(dataKey: ...)` не вызывается
  вовсе** (`breedSuits`, `vaccines`/`units`, `diseases`, `complexVaccines`,
  `injectionPlaces`, `injectionMethods`, `vaccinationTypes`, `ageGroups`,
  `kindMarkerPlaces`, `absenceReasons`) — `errorDataKey`/`errorMessageKey`,
  записанные `_emitError`, в этом случае — не пустая строка, а `_currentDataKey`
  от **предыдущего** шага, вызвавшего `_emitProgress` (например, если
  `breedSuits` отказывает — ключ ошибки останется `'suits'`, установленный
  шагом раньше). Ближе к истине, чем `dataCategoryId` (см. основной поток),
  но всё равно не указывает точно на отказавший справочник.
- **Отказ на шаге после `generationsTypes`** (`ageGroups`, `markerTypes`,
  `markerPlaces`, `kindMarkerPlaces`, `absenceReasons`) — здесь
  `_currentDataCategory` уже успел переустановиться на
  `DataCategory.generationsTypes` (шаг 468-472 внутри метода), так что
  ошибка попадёт под эту категорию — не под категорию отказавшего справочника,
  но хотя бы под категорию, реально относящуюся к справочникам, в отличие от
  основного потока этого документа.
- **Первый прогон для локали (`lastSyncDate == null`, `isIncremental == false`)**
  вместо шага 5/6 из «Основного потока» использует `clearAndInsertAll`
  (полная перезаливка) для каждого справочника до отказавшего включительно —
  та же логика частичного применения, только вместо частичного upsert
  получается частичная **полная замена**: справочники до отказавшего разом
  очищены и переналиты свежими данными, справочники после него — в исходном
  (для истинно первого прогона — пустом) состоянии. Отличие от инкрементального
  случая — только в размере эффекта на уже обработанные справочники, не в
  механизме отказа.

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy —
  `Kind`/`Breed`/`Suit`/`BreedSuit`) — четыре из ~18-19 справочников цепочки;
  в иллюстративном сценарии выше все четыре уже успешно обновлены к моменту
  отказа на `disposalReasons` — сама сущность `ENT-3` этим конкретным отказом
  не оставлена в противоречивом состоянии (она вся целиком успела примениться
  раньше отказавшего шага), но именно этот факт («некоторые справочники
  из общей цепочки уже применены, другие нет, и ничего в БД не различает
  два этих состояния для конкретного справочника, кроме одной строки-ошибки
  под чужой категорией») — предмет этого документа.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  получает единственную строку об отказе, `dataCategoryId` которой в
  большинстве реальных прогонов (все, кроме самого первого в жизни процесса)
  не имеет отношения ни к `directories`, ни к отказавшему справочнику —
  залежавшееся значение конца предыдущего прохода.
- Справочники BOARD ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md), через
  `_loadBoardDirectories`) — в этом сценарии не затрагиваются вовсе:
  `_loadBoardDirectories` вызывается в `on<DataUpdateStartAll>` **после**
  `loadDirectories`, и раз исключение оборвало проход внутри `loadDirectories`,
  до `_loadBoardDirectories` выполнение не доходит — граница из
  [MOD-7](../modules/MOD-7-SYSTEM.md) («справочники BOARD» специфицируются как
  отдельный факт синка) здесь просто не активируется.

### Бизнес-правила

- Результат — `UPDATE_ERROR`: отказ реально доходит до пользователя (в виде
  полноэкранного `DataUpdateFailure` на `DataUpdatePage`) и до журнала
  `DataUpdates` — в отличие от эталонного сценария взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)), где ошибка
  тонет внутри репозитория и не поднимается выше метода вовсе. Здесь
  проблема не в «проглатывании» отказа, а в том, что записанное о нём
  свидетельство (категория) в подавляющем большинстве случаев неверно.
- Нет ни одного транзакционного/checkpoint-механизма, объединяющего все
  ~18-19 справочников `loadDirectories` в одну атомарную единицу — каждый
  справочник коммитится независимо, партиальное применение архитектурно
  ожидаемо при любом сбое в середине цепочки, не только в иллюстративном
  сценарии этого документа.
- Прогресс синхронизации справочников не персистентен на уровне «с какого
  именно справочника продолжить» — только `lastSyncDate` (общий для всей
  цепочки, продвигается единственный раз, в самом конце) отличает
  «инкрементальный» режим от «полного». Отказ до конца цепочки означает: при
  следующей попытке `isIncremental` вычисляется от того же старого
  `lastSyncDate`, и вся цепочка проходится заново с `countries` — нет
  «докатки» именно с точки отказа.
- Категория ошибки (`DataCategory`) в `DataUpdates` — общий изменяемый
  инстанс-филд блока, не аргумент/локальная переменная конкретного вызова;
  корректность записанной категории зависит от того, что происходило в
  **предыдущем** проходе этого же долгоживущего инстанса блока, а не только
  от текущего — нарушение локальности эффекта, которое не видно при чтении
  одного `loadDirectories` метода изолированно.

## TARGET

TARGET не отличается от CURRENT — это документирующий проход, фиксирующий
уже существующее поведение, а не проектирование исправления.

## TBD / BLOCKED

Блокеров для документирования нет — оба факта (собственный, но
неинформативный `try/catch` внутри `loadDirectories`; частичное применение
справочников до отказавшего) воспроизводятся статическим чтением кода
целиком: `DataUpdateBloc.on<DataUpdateStartAll>` →
`DataUpdateBloc.loadDirectories` → `BaseDao.clearAndInsertAll`/`insAll`
(`packages/sheep_farm_database/lib/entities/base_dao.dart`). Возможное
исправление (например: своя обработка ошибки на уровне каждого справочника с
записью точной категории/ключа; оборачивание всей цепочки в одну транзакцию
или явный чек-поинт прогресса; продвижение `lastSyncDate` по мере, а не по
завершении всей цепочки) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный реальный обработчик ошибки всего прохода (`catch (error, stackTrace)` → `_emitError`); `loadDirectories` — первый вызов внутри его `try` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories` | CURRENT | последовательная цепочка ~18-19 справочников; собственный `try/catch (e) { rethrow; }` — не добавляет никакой обработки, только перебрасывает исключение выше; единственная переустановка `_currentDataCategory` (на `DataCategory.generationsTypes`) и единственный вызов `AppCacheService.saveDirectoriesLastSyncDate` — оба в самом конце метода, не достигаются при отказе раньше них |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress` | CURRENT | мутирует общие инстанс-филды `_currentDataCategory`/`_currentDataKey`; параметр `dataCategory` опционален — большинство вызовов внутри `loadDirectories` его не передают |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._resetProgressCounters` | CURRENT | пустое тело — не сбрасывает `_currentDataCategory`/`_currentDataKey` ни между шагами, ни между полными проходами |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `_addDataUpdateError` | CURRENT | пишут строку в `DataUpdates`, используя `_currentDataCategory`/`_currentDataKey` как есть на момент вызова — без верификации их актуальности относительно места фактического отказа |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadShtp` | CURRENT | последний по хронологии вызов, реально переустанавливающий `_currentDataCategory` (на `DataCategory.reports`) в обычном успешном авторизованном проходе — оставляет это значение для следующего прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._currentDataCategory`, `_currentDataKey` (поля класса) | CURRENT | `DataCategory _currentDataCategory = DataCategory.directories;` (значение по умолчанию — единственная ситуация, где `directories` реально попадёт в таблицу, см. «Альтернативные потоки»); `String _currentDataKey = '';` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clearAndInsertAll`, `BaseDao.insAll` | CURRENT | каждый справочник — своя независимая Drift-транзакция; нет общей транзакции на всю цепочку `loadDirectories` |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey` | CURRENT | 9 значений `DataCategory` — гораздо грубее ~18-19 `DataKey`-констант конкретных справочников; у `DataKey` нет константы для `breedSuits` вовсе |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate`, `saveDirectoriesLastSyncDate` | CURRENT | `lastSyncDate` продвигается только по завершении **всей** цепочки `loadDirectories` без отказа — партиальный прогресс не персистится |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getDisposalReasonsFromApi` | CURRENT | иллюстративная точка отказа основного потока этого документа (6-й из ~18-19 шагов цепочки) |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr`, `BuildContextL10nExtension.tr` | CURRENT | `default: return key;` — большинство `DataKey`-констант, используемых как `errorMessageKey`, не имеют перевода и показываются пользователю как есть |
| `lib/pages/data_update/data_update_page.dart` | `_Body.build` | CURRENT | рендерит `errorTitleKey`+`errorMessageKey` через `context.tr(...)` на полноэкранном `DataUpdateFailure` |
| `lib/main.dart` | `MyApp.build` → `BlocProvider<DataUpdateBloc>` | CURRENT | инстанс `DataUpdateBloc` создаётся один раз на весь процесс приложения — обосновывает «залежавшуюся» категорию между проходами |

## Критерии приёмки

- При исключении внутри `loadDirectories` до шага `generationsTypes`
  (например, при отказе `disposalReasons`) `DataUpdates` получает ровно одну
  строку ошибки, `dataCategoryId` которой равен значению `_currentDataCategory`
  на конец **предыдущего** полного прохода этого же процесса (в обычном
  авторизованном сценарии — `DataCategory.reports`), а не `DataCategory.directories`
  и не категории, относящейся к отказавшему справочнику.
- Справочники, обработанные до отказавшего шага цепочки (в основном потоке —
  `countries`, `kinds`, `breeds`, `suits`, `breedSuits`), остаются
  зафиксированными в локальной БД своими независимыми транзакциями и не
  откатываются отказом более позднего шага той же цепочки.
- Справочники от отказавшего шага и далее (`disposalReasons` и всё, что шло
  бы за ним) остаются нетронутыми этим прогоном — в том состоянии, в котором
  были до его начала.
- `AppCacheService.saveDirectoriesLastSyncDate` не вызывается, если отказ
  наступает раньше конца `loadDirectories` — `lastSyncDate` для этой локали
  не продвигается, и следующий прогон `loadDirectories` начинается заново с
  `countries`, без докатки именно с точки отказа.
- Если отказавший шаг систематически (не разово) не может завершиться
  успехом, каждый последующий полный проход повторяет один и тот же паттерн:
  справочники до него — избыточно переприменяются заново; справочники после
  него — остаются недостижимы; инкрементальный режим для справочников не
  наступает никогда, пока конкретный отказ не будет устранён.
- Пользователь видит на `DataUpdatePage` общий заголовок ошибки
  (`an_error_data`) и буквальную, нетранслированную строку `errorMessageKey`
  (например, `disposalReasons`) для любого `DataKey`, у которого нет
  собственного `case` в `AppLocalizations.tr` — что верно для подавляющего
  большинства ключей, используемых внутри `loadDirectories`.

## Связанные тесты

TBD — теста нет. Единственный тест `data_update_bloc_test.dart`,
покрывающий `DataUpdateBloc`, — `blocTest('DataUpdateClear очищает
пользовательские данные БД', ...)` (без номера use-case в названии — событие
`DataUpdateClear`, не `DataUpdateStartAll`, к этому сценарию не относится) и
`test('DataUpdateBloc конструируется с полным набором зависимостей из getIt', ...)`.
Файл содержит явный дисклеймер, объясняющий отсутствие покрытия
`DataUpdateStartAll` (а значит и `loadDirectories`) тестами:

> DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры getIt<X>()
> (не через конструктор) — конструктору бЛока нужны ВСЕ они зарегистрированы,
> даже для теста одного простого события. DataUpdateStartAll (~900 из 1013
> строк файла — основной sync pipeline) НЕ покрыт юнит-тестом: первая же
> строка обработчика — `await hasNetworkConnection()` (реальный DNS-запрос
> без DI-точки), дальше десятки приватных методов и реальные транзакции
> AppDatabase. Осмысленный юнит-тест такого масштаба потребовал бы
> рефакторинга источника под DI — вне рамок написания тестов без изменения
> кода. См. TESTING_CHECKLIST.md.

(`test/blocs/data_update_bloc_test.dart`; цитата приведена как есть — включая
опечатку «бЛока» и строку файла «1013», расходящуюся с текущими 918 строками
`data_update_bloc.dart` на момент написания этого документа, вероятно
устаревшую с момента написания комментария). Ни `loadDirectories`, ни
частичное применение справочников, ни корректность `dataCategoryId`
записанной ошибки этим или каким-либо иным найденным тестом не покрываются.

## Открытые вопросы и ограничения

- **Уточнение к [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).**
  Формулировка ENT-23 — «Категория `directories` из 9 значений enum'а нигде
  фактически не встречается в самой таблице» — верна для строк **успеха**
  (подтверждено и этим документом), но при прямом чтении кода нашёлся один
  узкий путь, которым `DataCategory.directories` всё же может попасть в
  `DataUpdates` — как строка **ошибки**, и только на самом первом вызове
  `loadDirectories` за время жизни процесса приложения (до того, как
  какой-либо `_emitProgress(dataCategory: ...)` успел выполниться хотя бы раз),
  при отказе раньше шага `generationsTypes` (см. «Альтернативные потоки»).
  `ENT-23` — заморожен, эта спека его не правит, только фиксирует найденный
  нюанс.
- **`DataUpdates` не очищается перед `loadDirectories` для гостя.**
  `_clearDataUpdates()` вызывается только внутри `_syncAllData`, которая
  вызывается только при `_authRepository.isAuthorized()` — то есть для
  гостевого прохода (который, по [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md),
  тоже безусловно выполняет `loadDirectories`) таблица `DataUpdates` не
  очищается вовсе на этом проходе; строки от предыдущих гостевых проходов
  могут накапливаться, пока не сработает `@Clearable()` при логауте. Не
  проверено, как именно это взаимодействует с `updateAndSyncRegagro`'овским
  условием (оно, впрочем, само по себе не выполняется для гостя, т.к.
  `_syncAuthData` не вызывается) — вне рамок этого документа, зафиксировано
  как смежное наблюдение.
- **Не проверено эмпирически на реальном запуске.** Вывод сделан статическим
  чтением кода (`on<DataUpdateStartAll>` → `loadDirectories` →
  `BaseDao.clearAndInsertAll`/`insAll`, `_emitProgress`, `_emitError`) —
  реальный прогон с намеренно вызванным сетевым сбоем на конкретном шаге
  (например, через мок/прокси) этой спекой не производился.
- **Значимость для продукта не оценивалась.** Насколько часто в реальной
  эксплуатации отдельный справочник систематически (а не разово) отказывает
  посреди цепочки — не оценивалось; вероятная частота разового сетевого сбоя
  (после которого следующий проход обычно проходит целиком и «самоисцеляет»
  частичное состояние) против системного отказа конкретного эндпоинта (после
  которого прогресс блокируется бессрочно) не разграничена эмпирически.
