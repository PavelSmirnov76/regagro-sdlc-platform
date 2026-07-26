# UC-198 — Одна из восьми реактивных подписок сводного экрана «В работе» бросает исключение через свой stream: `InWorkBloc` не регистрирует `onError` ни у одной из них, ошибка тонет как unhandled stream error, конкретная плитка молча застревает без счётчика

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же реактивный сводный экран, что описан в [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) —
`InWorkBloc` (`lib/pages/in_work/in_work_bloc.dart`) подписывается восемью
независимыми `StreamSubscription` на восемь `watch*`-стримов из шести разных
репозиториев, каждый из которых считает один тип ещё не отправленных на
сервер записей и обновляет одну плитку. Здесь описан единственный
структурно проверенный чтением кода путь отказа этого чтения: что
происходит, если один (любой) из этих восьми стримов эмитит **ошибку**
вместо значения.

Прочитан целиком `lib/pages/in_work/in_work_bloc.dart`: все восемь вызовов
`.listen(...)` в конструкторе `InWorkBloc` передают только позиционный
колбэк `onData` — ни один не передаёт именованный аргумент `onError`
(`grep -n "onError" lib/pages/in_work/in_work_bloc.dart` не находит ни
одного совпадения во всём файле). По контракту `dart:async`
(`dart-sdk/lib/async/stream_impl.dart`, `_nullErrorHandler`) отсутствие
`onError` у `.listen()` означает, что при ошибке стрима вызывается
`Zone.current.handleUncaughtError(error, stackTrace)` — ошибка становится
**необработанной асинхронной ошибкой стрима**, не долетающей ни до
`InWorkBloc.on<InWorkEventLoad>`, ни до какого-либо `try/catch` в этом
файле. Поскольку `runApp(const MyApp())` в `lib/main.dart` не обёрнут в
`runZonedGuarded` (соответствующий вызов `runTalkerZonedGuarded(...)`
закомментирован — тот же факт, что уже зафиксирован в
[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) для другого
сценария), эта ошибка не перехватывается никаким пользовательским кодом
приложения вообще: она не попадает ни в `Talker`-лог (в отличие от,
например, `CustomDioClient.call`, который логирует через
`getIt<Talker>().error(...)` перед `rethrow`), ни в снэкбар, ни в любую
другую видимую пользователю или разработчику форму — предел
диагностируемости здесь ниже, чем в большинстве других найденных до сих пор
в этом дереве сценариев `READ_ERROR`.

Поскольку каждая из восьми подписок — отдельный, независимый
`StreamSubscription`, отказ одной не отражается на остальных семи: экран не
падает, не показывает общей ошибки — только конкретная плитка, чей стрим
отказал, остаётся без корректного счётчика, неотличимо от «неотправленных
записей этого типа нет».

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
открывший вкладку «В работе» (`Routes.inWork`), как зафиксировано уже в
самом [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) и в
составе [MOD-7](../modules/MOD-7-SYSTEM.md) («Состав» → «Акторы»:
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) переиспользован именно для
«просмотр «В работе»/календаря»). Отказ,
описанный этим документом, никак не зависит от того, кто и когда записал
исходные данные (взвешивания/перемещения/вакцинации/выбытия/локальные
животные/сессии инвентаризации, обычно ANIMAL-актор в своих собственных
экранах) — он происходит целиком внутри реактивного чтения самого экрана
«В работе», в момент, когда `InWorkBloc` уже создан и подписан.

## CURRENT

### Основной поток

1. [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) открывает вкладку «В работе». `InWorkPage.build`
   (`lib/pages/in_work/in_work_page.dart`) оборачивает контент в
   `BlocProvider(create: (context) => InWorkBloc())` — новый экземпляр
   блока создаётся заново при каждом входе на страницу.
2. Конструктор `InWorkBloc()` синхронно создаёт восемь независимых
   `StreamSubscription`, каждая — на свой репозиторный `watch*`-метод:
   `AnimalsRepository.watchCountLocalAnimalsToCreate()`,
   `DisposalRepository.watchCountNotSync()`,
   `AnimalWeighingsRepository.watchCountNotSync()`,
   `VaccinationsRepository.watchCountNotSync()`/`.watchCountEditableVaccinations()`/`.watchCountDeletableVaccinations()`,
   `MovementReportRepository.watchNotSyncMovements()`,
   `UnsentReportAnimalsRepository.watchInventorySessionCount()`. Ни один из
   восьми вызовов `.listen(...)` не передаёт `onError`.
3. Возьмём для конкретности плитку «Взвешивание» (взаимозаменяемо с любой
   из оставшихся семи — дефект структурно один и тот же, см.
   «Альтернативные потоки»): `_animalWeighingsSubscription =
   _animalWeighingsRepository.watchCountNotSync().listen((event) {
   add(InWorkEventLoad(animalWeighingsCount: event)); });`.
4. `AnimalWeighingsRepository.watchCountNotSync()` —
   тонкий passthrough к `AnimalWeighingsDao.watchCountNotSync()`
   (`packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart`) —
   обычный `COUNT`-запрос (`selectOnly(...).map(...).watchSingle()`),
   обёрнутый машинерией стримов drift (`QueryStream.fetchAndEmitData`,
   `drift/src/runtime/executor/stream_queries.dart`, пакет `drift-2.28.2`
   из `pub-cache`): каждый раз, когда меняется relevant-таблица, запрос
   перевыполняется; при успехе — `listener.add(data)`; если
   `_fetcher.fetchData` в этот раз бросает исключение — `catch`-блок
   вызывает `listener.controller.addError(e, s)` **вместо** `add`, не
   закрывая сам стрим.
5. Это исключение долетает до `_animalWeighingsSubscription` как ошибка
   стрима. Поскольку `.listen(onData)` на шаге 3 вызван без `onError`,
   срабатывает `dart:async`'ный `_nullErrorHandler`
   (`dart-sdk/lib/async/stream_impl.dart`): `Zone.current.handleUncaughtError(error, stackTrace)`.
6. Активная зона на этот момент — обычная корневая зона Dart: `main()`
   вызывает `runApp(const MyApp())` без обёртки `runZonedGuarded` (строка
   с `runTalkerZonedGuarded(...)` закомментирована, `lib/main.dart`). Для
   корневой зоны `handleUncaughtError` — это `_rootHandleUncaughtError` →
   `_rootHandleError` (`dart-sdk/lib/async/zone_root.dart`), которая
   планирует повторный **асинхронный** выброс того же исключения
   (`Error.throwWithStackTrace(error, stackTrace)`) — необработанная
   ошибка верхнего уровня, не проходящая ни через `FlutterError.onError`
   (этот хук вызывается только там, где сам фреймворк явно маршрутизирует
   ошибку через `FlutterError.reportError` — build/layout/paint,
   `packages/flutter/lib/src/foundation/assertions.dart`, не произвольные
   ошибки стримов), ни через `Talker`, ни через любой другой перехватчик,
   найденный в этом приложении.
7. `InWorkBloc.on<InWorkEventLoad>` для вклада именно этого стрима не
   вызывается ни разу — `_data.animalWeighingsCount` остаётся таким, каким
   был до этого момента: `null`, если ошибка произошла на самой первой
   попытке этого стрима (типичный случай — сразу после открытия экрана),
   либо последнее ранее полученное значение, если стрим до этого уже
   успевал отдать хотя бы одно число.
8. Остальные семь подписок — полностью независимые `StreamSubscription` на
   других полях `_data`; отказ этой конкретной подписки не приостанавливает,
   не отменяет и никак иначе не затрагивает их — они продолжают штатно
   получать значения и обновлять свои поля через `copyWith`.
9. `InWorkPage`'s `BlocBuilder<InWorkBloc, InWorkState>` продолжает
   рендерить `InWorkSuccess`, как только хотя бы одна из оставшихся семи
   подписок хоть раз отработала успешно (состояние необратимо переходит из
   `InWorkInitial` в `InWorkSuccess` первым же успешным
   `InWorkEventLoad` — независимо от того, какое именно поле было в нём
   заполнено). Плитка «Взвешивание» (`EventTileData` с
   `count: data.animalWeighingsCount`) рендерится `EventCardWidget`
   (`lib/widgets/event_card_widget.dart`): `if (eventTileData.count !=
   null && eventTileData.count! > 0) _CountBadge(...)` — при `null` (как и
   при `0`) красный бейдж со счётчиком просто не рисуется. Плитка выглядит
   в точности как «неотправленных взвешиваний нет» — неотличимо от
   честного нуля.
10. Ни `InWorkPage`, ни `EventTilesWidget` не содержат ни одного
    `BlocListener`/снэкбара/индикатора ошибки, который отреагировал бы на
    этот отказ — единственный `BlocListener` в файле подписан на
    `LanguageBloc` и не имеет отношения к этому сценарию. Кнопка
    «Синхронизировать данные» внизу экрана диспатчит отдельный,
    несвязанный `DataUpdateStartAll` в `DataUpdateBloc`
    ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)) —
    сетевую отправку уже сохранённых локальных записей, а не починку
    сломанной локальной `watch`-подписки; нажатие этой кнопки никак не
    восстанавливает пострадавшую плитку.
11. Поскольку `fetchAndEmitData` (шаг 4) не закрывает стрим при ошибке,
    следующая запись в таблицу `AnimalWeighings` (например, новое
    взвешивание, сохранённое с другого экрана) заставит drift
    перевыполнить тот же запрос; если на этот раз он успешен —
    `listener.add(data)` доходит до всё той же, всё ещё живой
    `_animalWeighingsSubscription` обычным образом, без необходимости
    закрывать и заново открывать экран «В работе» или пересоздавать блок.
    Это восстановление — побочный эффект чужой записи, а не
    спроектированный retry: оно наступает тогда и только тогда, когда
    что-то не связанное с этим экраном случайно перезаписывает нужную
    таблицу.
12. Сами данные при этом не теряются и не портятся — пользователь, который
    вместо плитки откроет отдельный хаб «Взвешивание»
    (`Routes.unsentAnimalWeighings`,
    [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md),
    см. [UC-95](UC-95-ACTOR-5-EVT-48-ENT-15-READ_OK-IN-ANIMAL.md)), попадёт
    в `AnimalWeighingsCubit.loadNotSync()`
    (`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`) —
    метод, который получает тот же набор строк совершенно другим путём:
    одноразовым `await _animalWeightingsRepository.getAllNotSuncAnimalWeighings()`
    (`Future`, не `Stream`), никак не связанным с
    `watchCountNotSync()`. Этот путь отказом плитки не затронут — хаб
    покажет корректный, непустой список, даже пока плитка над ним
    показывает «ничего нет».

### Альтернативные потоки

- **Дефект одинаков для всех восьми подписок.** `grep -n "onError"
  lib/pages/in_work/in_work_bloc.dart` не находит ни одного совпадения во
  всём файле — ни у `_unsentAnimalsToCreateCountSubscription`, ни у
  `_unsentDisposalListsCountSubscription`, ни у `_animalWeighingsSubscription`,
  ни у `_unsentVaccinationsSubscription`/`_editableVaccinationsSubscription`/`_deletableVaccinationsSubscription`,
  ни у `_unsentMovementsSubscription`, ни у `_inventoryCountSubscription`.
  Шаги 3–11 основного потока дословно применимы к любой из восьми, отличается
  только то, какое поле `InWorkData` застревает и какая плитка перестаёт
  отражать реальность.
- **Два разных «этажа» риска у семи подписок vs у двух.** Шесть
  подписок — чистые `COUNT`-запросы прямого прохождения (`AnimalsRepository`,
  `DisposalRepository`, `AnimalWeighingsRepository`, три метода
  `VaccinationsRepository`) — единственный источник исключения там —
  собственно выполнение drift-запроса. Две подписки устроены сложнее:
  - `_unsentMovementsSubscription`: `MovementReportRepository.watchNotSyncMovements()`
    → `MovementsDao.watchAllNotSync()` (строки, не счётчик) — дедупликация
    по ключу `${m.fromId}_${m.placeId}_${DateFormat('HHmm').format(date)}`
    выполняется **внутри колбэка `.listen()` самого блока**, тоже без
    `onError`; исключение может прийти либо из самого drift-запроса, либо
    из этой сборки ключа (`date = m.placeDate ?? m.createdAt ??
    DateTime.now()` — защищено от `null`, но не от иных сбоев форматирования).
  - `_inventoryCountSubscription`: `UnsentReportAnimalsRepository.watchInventorySessionCount()`
    оборачивает `UnsentReportAnimalsDao.watchInventoryReadyList()`
    (строки) собственным `.map((records) { ...
    DateUtils.dateOnly(r.time) ... })` **внутри репозитория**, ещё до
    того, как результат вообще доходит до `.listen()` блока — на один слой
    раньше, чем у семи остальных, но итоговый эффект (ошибка без `onError`
    где бы то ни было по пути) идентичен.
- **Ошибка на самой первой попытке против ошибки после уже показанных
  значений.** Если сбой происходит на первой попытке стрима (типично —
  сразу после открытия экрана) — поле остаётся `null` с самого начала,
  неотличимо от честного «нет неотправленных записей» (шаг 9). Если сбой
  происходит **после** того, как стрим уже успевал отдать хотя бы одно
  значение, поле замораживается на последнем известном числе — плитка
  показывает правдоподобный, но устаревший счётчик; с точки зрения
  пользователя это можно назвать даже более вводящим в заблуждение
  случаем, чем отсутствие бейджа вовсе.
- **Повторное открытие экрана даёт каждой подписке новый шанс, но не
  гарантию.** `BlocProvider` уничтожает предыдущий `InWorkBloc` при уходе
  со страницы (`InWorkBloc.close()` отменяет все восемь подписок) и создаёт
  новый при следующем входе — если причина сбоя была временной (гонка,
  разовая блокировка БД), новая попытка может пройти успешно; если причина
  постоянная (например, сама операция чтения систематически падает на
  конкретном состоянии таблицы), та же самая плитка будет молча
  отказывать заново при каждом новом открытии экрана, без накопления
  какого-либо диагностического следа между попытками.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность,
  названная в id этого UC: `AnimalsRepository.watchCountLocalAnimalsToCreate()`
  считает строки `Animals` с `id < 0` и `farmId IS NOT NULL` (см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), инвариант «`id < 0` —
  единственный признак «ещё не синхронизировано»») для плитки
  «Регистрация» — один из восьми равноправно затрагиваемых этим сценарием
  случаев.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement),
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination, три
  из восьми подписок), [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)
  (AnimalWeighing, основной пример «Основного потока»),
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal),
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport/`UnsentReportAnimal`) — каждая сущность отдаёт свой
  счётчик через собственный репозиторный стрим; все восемь стримов
  структурно идентичны по отношению к этому дефекту (подтверждено
  чтением всего `lib/pages/in_work/in_work_bloc.dart`).
- `DataUpdate` ([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) —
  не затрагивается этим сценарием: кнопка «Синхронизировать данные» на
  этом же экране ведёт в отдельный, несвязанный `DataUpdateBloc`
  ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)),
  никак не влияющий на восемь локальных `watch`-подписок «В работе» и не
  чинящий их при отказе.

### Бизнес-правила

- Экран «В работе» — чисто read-проекция поверх уже специфицированных
  ANIMAL-хабов неотправленных записей, не отдельный источник истины (см.
  [MOD-7](../modules/MOD-7-SYSTEM.md), «Граница — что модуль explicitly не
  владеет»): в текущем коде отказ этой проекции никак не защищён отдельным
  fallback- или retry-механизмом, специфичным для одной плитки.
- `READ_REJECTED` для этого сценария структурно недостижим — здесь нет
  сервера, нет содержательного отказа, который бизнес-правило могло бы
  осознанно отклонить: это чисто локальное чтение, и единственная
  наблюдаемая развилка — «значение показано» / «значение не показано (или
  устарело) из-за необработанного исключения».
- Ни на уровне `InWorkBloc`, ни на уровне `InWorkPage` нет никакого
  индикатора «эта плитка не смогла обновиться» — визуально отказавшая
  плитка неотличима от плитки с честным нулём непереданных записей ни в
  какой из веток кода, прочитанных для этого документа.
- Восстановление конкретной плитки зависит исключительно от того, произойдёт
  ли в будущем несвязанная запись в соответствующую таблицу (шаг 11) —
  никакого выделенного планового retry именно этого стрима в коде нет.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий воспроизводится
полностью статическим чтением кода целиком по цепочке: `InWorkBloc`
constructor → любой из восьми `.listen(...)` без `onError`
(`lib/pages/in_work/in_work_bloc.dart`, подтверждено `grep`) →
соответствующий `watch*`-метод репозитория/DAO → `QueryStream.fetchAndEmitData`
пакета `drift` (`drift-2.28.2`, `lib/src/runtime/executor/stream_queries.dart`),
которая при ошибке запроса вызывает `listener.controller.addError` без
закрытия стрима → `_nullErrorHandler` (`dart-sdk/lib/async/stream_impl.dart`)
→ `Zone.current.handleUncaughtError` → корневая зона по умолчанию
(`_rootHandleUncaughtError`/`_rootHandleError`, `dart-sdk/lib/async/zone_root.dart`),
поскольку `runApp` в `lib/main.dart` не обёрнут в `runZonedGuarded`. Реальный
запуск против намеренно отказывающего Drift-соединения (например,
принудительно закрытая в рантайме БД или ошибка диска) этим проходом не
воспроизведён эмпирически — см. «Открытые вопросы». Исправление (например,
добавление `onError` к каждой из восьми подписок, отдельный визуальный
индикатор отказа плитки, запись в `Talker`) в рамках этого документирующего
прохода не выполняется — это фиксация уже существующего кода, а не работа
над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc()` (конструктор, все восемь вызовов `.listen(...)`) | CURRENT | ни один из восьми не передаёт `onError` — подтверждено `grep -n "onError"` по всему файлу (0 совпадений) |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc.on<InWorkEventLoad>` | CURRENT | единственный путь обновления `_data`/эмиссии `InWorkSuccess` — никогда не вызывается для той части события, чей стрим отказал |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc.close` | CURRENT | отменяет все восемь подписок при уничтожении блока (уход со страницы) — новый вход создаёт новый блок и новые подписки с чистого листа |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.watchCountNotSync` | CURRENT | passthrough к DAO, основной пример «Основного потока» |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.watchCountNotSync` | CURRENT | `COUNT`-запрос через `selectOnly(...).watchSingle()` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.watchCountNotSync` | CURRENT | passthrough к DAO, структурно идентичен |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.watchCountNotSync` | CURRENT | `COUNT`-запрос |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.watchCountNotSync`, `.watchCountEditableVaccinations`, `.watchCountDeletableVaccinations` | CURRENT | три passthrough-метода, три из восьми подписок |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.watchCountNotSync`, `.watchCountEditableVaccinations`, `.watchCountDeletableVaccinations` | CURRENT | три `COUNT`-запроса |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.watchNotSyncMovements` | CURRENT | возвращает строки (не счётчик); дедупликация выполняется в самом блоке |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.watchAllNotSync` | CURRENT | строковый `watch()`-запрос |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.watchCountLocalAnimalsToCreate` | CURRENT | passthrough к DAO, сущность из id этого UC |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.watchCountLocalAnimalsToCreate` | CURRENT | `COUNT`-запрос по `id < 0 AND farmId IS NOT NULL` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.watchInventorySessionCount` | CURRENT | собственный `.map()`-трансформ поверх стрима строк DAO — дополнительный слой риска на один уровень раньше блока |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.watchInventoryReadyList` | CURRENT | строковый `watch()`-запрос |
| `drift-2.28.2` (pub-cache, зависимость `packages/sheep_farm_database`) `lib/src/runtime/executor/stream_queries.dart` | `QueryStream.fetchAndEmitData` | CURRENT | сторонний пакет — при ошибке запроса вызывает `listener.controller.addError(e, s)`, не закрывая стрим — следующая релевантная запись в таблицу может успешно перевыполнить запрос без пересоздания подписки |
| Dart SDK 3.41.0 (bin/cache/dart-sdk) `lib/async/stream_impl.dart` | `_nullErrorHandler` | CURRENT | часть Dart SDK, не кода проекта — поведение по умолчанию для `.listen()` без `onError`: форвардит ошибку в `Zone.current.handleUncaughtError` |
| Dart SDK 3.41.0 `lib/async/zone_root.dart` | `_rootHandleUncaughtError`, `_rootHandleError` | CURRENT | часть Dart SDK — обработчик корневой зоны по умолчанию, планирует асинхронный повторный выброс той же ошибки, без перехвата |
| `lib/main.dart` | `main()` — `runApp(const MyApp())`, закомментированный `runTalkerZonedGuarded(...)` | CURRENT | никакая пользовательская зона/лог не активны — тот же факт, что уже установлен в [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) |
| Flutter SDK 3.41.0 `packages/flutter/lib/src/foundation/assertions.dart` | `FlutterError.onError` | CURRENT | часть Flutter SDK — вызывается только там, где сам фреймворк явно маршрутизирует ошибку через `FlutterError.reportError` — не для произвольных ошибок стримов вне build/layout/paint |
| `lib/pages/in_work/in_work_page.dart` | `InWorkPage.build`, `EventTilesWidget` | CURRENT | рендерит то, что сейчас лежит в `InWorkSuccess.data`; нет ни одного индикатора отказа отдельной плитки |
| `lib/widgets/event_card_widget.dart` | `EventCardWidget`, `_CountBadge` | CURRENT | `count == null` и `count == 0` рендерятся одинаково — без бейджа |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | независимый одноразовый `Future`-путь к тем же данным (`getAllNotSuncAnimalWeighings`) — не использует `watchCountNotSync()`, этим сценарием не затронут; используется здесь как перекрёстная проверка (см. шаг 12) |

## Критерии приёмки

- Если любой из восьми стримов, на которые подписан `InWorkBloc`
  (`AnimalsRepository.watchCountLocalAnimalsToCreate`,
  `DisposalRepository.watchCountNotSync`,
  `AnimalWeighingsRepository.watchCountNotSync`,
  `VaccinationsRepository.watchCountNotSync`/`.watchCountEditableVaccinations`/`.watchCountDeletableVaccinations`,
  `MovementReportRepository.watchNotSyncMovements`,
  `UnsentReportAnimalsRepository.watchInventorySessionCount`), эмитит
  ошибку вместо значения, `InWorkBloc` её не перехватывает — ни один из
  восьми вызовов `.listen(...)` в конструкторе не передаёт `onError`.
- Ошибка становится необработанной асинхронной ошибкой стрима, форвардится
  Dart'ом по умолчанию в `Zone.current.handleUncaughtError`; поскольку
  `runApp` в `main()` не обёрнут в `runZonedGuarded`, ни один пользовательский
  обработчик (`Talker`, снэкбар, диалог) её не получает.
- `InWorkBloc.on<InWorkEventLoad>` не вызывается для вклада отказавшего
  стрима — соответствующее поле `InWorkData` сохраняет предыдущее значение
  (`null`, если ошибка произошла до первой успешной эмиссии этого стрима).
- Остальные семь подписок продолжают штатно работать независимо от отказа
  одной — `InWorkSuccess` эмитится и рендерится, как только любая из них
  хоть раз отработала успешно.
- На отказавшей плитке `EventCardWidget` не рисует красный счётчик-бейдж
  ни при `count == null`, ни при `count == 0` — отказавшая плитка визуально
  неотличима от плитки с честным нулём.
- Стрим drift, чья текущая попытка выполнения отказала
  (`QueryStream.fetchAndEmitData`), не закрывается — последующая
  релевантная запись в ту же таблицу может успешно перевыполнить запрос и
  доставить значение той же самой, уже существующей подписке без
  необходимости покидать и заново открывать экран «В работе».
- Повторное открытие экрана «В работе» (пересоздание `InWorkBloc` через
  `BlocProvider`) даёт каждой из восьми подписок новую попытку с нуля;
  ничего в коде не гарантирует, что причина отказа не повторится.
- Открытие отдельного хаба неотправленных записей соответствующего типа
  (например `Routes.unsentAnimalWeighings` →
  `AnimalWeighingsCubit.loadNotSync`) не зависит от отказавшего стрима «В
  работе» и может показать корректные, непустые данные независимо от
  состояния соответствующей плитки.

## Связанные тесты

`test/pages/in_work_bloc_test.dart` существует и покрывает только
успешные комбинации через фейковые `StreamController<int>`/`StreamController<List<Movement>>`
(по одному на каждый из восьми стримов, все — `.broadcast()`). Дословные
названия существующих групп:

- `group('UC-197 — InWorkBloc реактивные подписки', ...)` — тесты
  `'конструктор подписывается на все 8 потоков без падений, начальное
  состояние InWorkInitial'`, `'каждый поток независимо обновляет свой
  счётчик в InWorkSuccess.data'`, `'обновление одного потока не сбрасывает
  уже накопленные значения других (copyWith merge)'`.
- `group('UC-197 — InWorkBloc дедупликация перемещений', ...)` — тесты
  `'несколько записей с одинаковым from/to/HHmm -> считаются одним
  событием'`, `'записи с разным from/to/HHmm -> считаются раздельно'`.

Обе группы процитированы дословно как они названы в файле сегодня —
включая расхождение номера (`UC-197`, не `UC-198`, id этого документа) с
именем текущего UC; переименование тестов, если оно требуется, — задача
отдельного прохода оператора, не этого документа.

Ни один из пяти тестов ни разу не вызывает `.addError(...)` ни на одном из
восьми фейковых `StreamController` — всюду используется только `.add(...)`
(успешные данные). Сценарий «стрим эмитит ошибку вместо/между значениями»,
описанный этим документом, этим файлом не покрыт.

**TBD — теста нет** на сценарий, документируемый здесь: ни на отсутствие
`onError` у любой из восьми подписок, ни на то, что ошибка одной из них не
трогает остальные семь, ни на застревание поля `InWorkData` на `null`/на
устаревшем значении.

## Открытые вопросы и ограничения

- **Осознанное ли это решение («экран одноразовый/косметический, точная
  цифра не критична, реальные данные всегда доступны через свои хабы») или
  недосмотр — ничем в коде/комментариях `in_work_bloc.dart` не
  зафиксировано.** Ни один из восьми `.listen()` не содержит комментария,
  объясняющего отсутствие `onError`.
- **Не проверено эмпирически против реально отказывающего Drift-соединения**
  (например, принудительно закрытая в рантайме `AppDatabase`, ошибка
  диска, конкурентная миграция схемы) — вывод сделан статическим чтением
  `InWorkBloc`, восьми репозиторных/DAO-методов, собственной машинерии
  стримов `drift` (`stream_queries.dart`) и поведения Dart SDK по
  умолчанию (`stream_impl.dart`, `zone_root.dart`). Конкретная причина,
  по которой один из этих запросов реально бросил бы исключение в
  продакшене, этим проходом не воспроизведена и не идентифицирована — этот
  документ фиксирует механизм отсутствия обработки, а не конкретный
  триггер.
- **Не проверено, действительно ли `PlatformDispatcher.instance.onError`
  (крючок движка Flutter, вызываемый для необработанных ошибок изолята) в
  принципе получил бы эту ошибку в текущей конфигурации приложения** — это
  вопрос поведения самого Flutter/Dart-рантайма, не кода приложения;
  сколько-нибудь надёжного стороннего перехватчика (crash-reporting SDK и
  т.п.), подключённого к этому крючку, в прочитанном коде не найдено —
  единственный подготовленный в коде механизм (`runTalkerZonedGuarded`) на
  сегодня закомментирован.
- Не установлено, насколько вероятно на практике, чтобы конкретно эти
  восемь `COUNT`/`SELECT`-запросов (простые, без внешних зависимостей,
  выполняемые над локальной SQLite-базой) вообще бросали исключение в
  реальной эксплуатации — оценка такой вероятности вне рамок задачи,
  поставленной для этого документа.
