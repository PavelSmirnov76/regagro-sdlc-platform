# UC-197 — Пользователь открывает сводный экран «В работе»: 8 реактивных Drift-подписок сворачиваются в 6 плиток-счётчиков ANIMAL-очереди

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Пользователь открывает `InWorkPage` (`Routes.inWork`) — единственный экран
приложения, агрегирующий в одном месте счётчики ещё не отправленных на
сервер записей сразу по шести категориям ANIMAL-домена (взвешивание,
перемещение, вакцинация, выбытие, регистрация животных, инвентаризация).
Экран ничего не загружает по явной команде (нет `load()`/pull-to-refresh) —
`InWorkBloc` целиком реактивен: его конструктор сразу подписывается на 8
Drift-стримов поверх шести разных репозиториев, и каждое их изменение
самостоятельно обновляет один счётчик в объединённом состоянии. Экран —
чистая точка навигации: каждая из шести плиток ведёт на свой отдельный
хаб-экран уже неотправленных записей этой категории; сам `InWorkPage`
записи не показывает и не редактирует. Внизу — кнопка «Синхронизировать
данные», инициирующая ручной полный sync-проход
([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
не предмет этого файла).

**BOARD (избранное/сообщения/мои объявления) в этом экране не участвует
вообще** — подтверждено чтением `in_work_bloc.dart`: импортируются и
инжектируются ровно шесть репозиториев (`AnimalsRepository`,
`DisposalRepository`, `AnimalWeighingsRepository`, `VaccinationsRepository`,
`MovementReportRepository`, `UnsentReportAnimalsRepository`) — ни одного
BOARD-репозитория (`AdsRepository`/`ChatsRepository`/`MessagesRepository` и
т.п.) в списке нет. Весь экран посвящён исключительно ANIMAL-домену, как и
зафиксировано в самом [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — так называет инициатора сам
[EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) (frozen), и с
этим id пишется этот файл. Но прямое чтение кода даёт более широкую
картину, зафиксированную здесь как факт, а не как решение поменять id: точка
входа — `ProfileButton` (`type: ProfileButtonType.square`, `title:
l10n.in_work__title`) в `lib/pages/profile/presentation/widgets/profile/profile_view.dart`,
`onTap: () => context.pushNamed2(Routes.inWork)` — не обёрнута ни в какое
условие по авторизации (в отличие, например, от `_DeleteAccountButton` в
`profile_settings_view.dart`, честно проверенного через
`AppCacheService.isAuthorized()`). `ProfileBloc.on<ProfileEventStart>`
(`lib/pages/profile/profile_bloc.dart`) явно поддерживает `user == null`
(гость) без падения и без редиректа — `_authRepository.getUser()` может
вернуть `null`, и `ProfileView.build` тем не менее рендерит весь экран,
включая эту плитку. Сам `InWorkBloc` и все шесть его репозиториев — чистые
локальные Drift-запросы (`watchCountNotSync`/`watchCountLocalAnimalsToCreate`/
`watchNotSyncMovements`/`watchInventorySessionCount`), ни один не проверяет
`AuthRepository.isAuthorized()`. Подробнее о том, что это значит для
корректности id актора в имени файла — см. «Открытые вопросы и
ограничения» (вынесено туда, не потеряно).

## CURRENT

### Основной поток

1. Пользователь на вкладке «Профиль» нажимает квадратную плитку «В работе»
   (`l10n.in_work__title`) — единственная найденная точка входа на этот
   экран во всём `lib/` (`grep -rn "Routes.inWork\b" lib` вне `routes.dart`
   даёт ровно одно совпадение, `profile_view.dart`).
2. `Routes.inWork` — маршрут верхнего уровня внутри той же навигационной
   ветки, что и остальные экраны профиля (`routes.dart`); `builder` создаёт
   `const InWorkPage()`.
3. `InWorkPage.build` оборачивает контент в `BlocListener<LanguageBloc,
   LanguageStateInitial>` (стандартный для экранов приложения
   перерендер-по-смене-языка боилерплейт, не специфичен для этого
   сценария) и в `BlocProvider(create: (context) => InWorkBloc())` — без
   вызова какого-либо `load()`: весь первичный сбор данных выполняется
   подписками, инициированными прямо в конструкторе `InWorkBloc`.
4. Конструктор `InWorkBloc()` синхронно подписывается на 8 потоков,
   каждый — на своей паре репозиторий/DAO:
   - `_animalsRepository.watchCountLocalAnimalsToCreate()` →
     `AnimalsDao.watchCountLocalAnimalsToCreate` — `COUNT(id)` по
     `Animals` с `id < 0 AND farmId IS NOT NULL` → `InWorkEventLoad(animalsToCreateCount: …)`.
   - `_disposalRepository.watchCountNotSync()` →
     `DisposalDao.watchCountNotSync` — `COUNT(id)` по `Disposals` с
     `sync = false` (без группировки) → `InWorkEventLoad(disposalListsCount: …)`.
   - `_animalWeighingsRepository.watchCountNotSync()` →
     `AnimalWeighingsDao.watchCountNotSync` — `COUNT(id)` по
     `AnimalWeighings` с `sync = false` → `InWorkEventLoad(animalWeighingsCount: …)`.
   - `_unsentVaccinationsRepository.watchCountNotSync()` →
     `VaccinationsDao.watchCountNotSync` — `sync=false ∧ deletedAt IS NULL ∧
     updatedAt IS NULL ∧ createdAt IS NOT NULL` → `InWorkEventLoad(vaccinationsCount: …)`.
   - `_unsentVaccinationsRepository.watchCountEditableVaccinations()` →
     `VaccinationsDao.watchCountEditableVaccinations` — `sync=false ∧
     updatedAt IS NOT NULL ∧ deletedAt IS NULL ∧ createdAt IS NULL` →
     `InWorkEventLoad(editableVaccinationsCount: …)`.
   - `_unsentVaccinationsRepository.watchCountDeletableVaccinations()` →
     `VaccinationsDao.watchCountDeletableVaccinations` — `sync=false ∧
     deletedAt IS NOT NULL ∧ updatedAt IS NULL ∧ createdAt IS NULL` →
     `InWorkEventLoad(deletableVaccinationsCount: …)`.
   - `_movementReportRepository.watchNotSyncMovements()` →
     `MovementDao.watchAllNotSync` — весь `List<Movement>` с `sync = false`
     (без агрегации в БД); дедупликация выполняется в самом callback'е
     подписки (см. шаг 5) → `InWorkEventLoad(movementsCount: …)`.
   - `_unsentReportAnimalsRepository.watchInventorySessionCount()` →
     `UnsentReportAnimalsDao.watchInventoryReadyList` — строки
     `UnsentReportAnimals` с `type = 'inventory' AND readyToSend = true`;
     репозиторий сам сворачивает список строк в число уникальных сессий
     (см. шаг 6) → `InWorkEventLoad(inventoryCount: …)`.
5. Дедупликация перемещений (внутри `.listen` перемещенческого потока, не в
   БД-запросе): для каждой строки `Movement` вычисляется `date = m.placeDate
   ?? m.createdAt ?? DateTime.now()`, затем ключ `'${m.fromId}_${m.placeId}_${DateFormat('HHmm').format(date)}'`
   добавляется в `Set<String>`; `movementsCount` — размер этого множества,
   не число строк. Несколько строк `Movement` с одинаковыми
   origin/destination и совпадающим временем с точностью до минуты
   (`fromId` — место отправления, `placeId` — место назначения, оба —
   `idRemote`, см. [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md))
   схлопываются в одно «событие» — так групповое перемещение нескольких
   животных одним действием (по одной строке `Movement` на каждое животное)
   считается одной единицей на бейдже.
6. Дедупликация инвентаризации (внутри самого репозитория, не в
   `InWorkBloc`): `watchInventorySessionCount` мапит список строк в
   `Set<String>` ключей — `r.sessionUuid`, если он есть, иначе
   `'legacy_${r.farmId}_${r.placeId}_${DateUtils.dateOnly(r.time).millisecondsSinceEpoch}'`
   для легаси-строк без `sessionUuid` (см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md),
   поле `sessionUuid` появилось поздно в истории миграций) — размер этого
   множества и есть `inventoryCount`.
7. Каждое из 8 полей `InWorkEventLoad` заполняется независимо — конструктор
   `InWorkEventLoad({this.animalsToCreateCount, …})` принимает все поля как
   опциональные, и каждый из 8 `.listen`-колбэков вызывает `add(...)` только
   с одним заполненным полем, остальные семь остаются `null` по умолчанию
   этого конкретного вызова.
8. `on<InWorkEventLoad>` — единственный обработчик события: `_data =
   _data.copyWith(animalsToCreateCount: event.animalsToCreateCount, …)`
   (все 8 полей передаются в `copyWith`), затем `emit(InWorkSuccess(_data))`.
   `InWorkData.copyWith` для каждого поля — `newValue ?? this.oldValue`:
   поскольку у события заполнено ровно одно поле, а остальные семь —
   `null`, оператор `??` откатывается на уже накопленное значение из `_data`
   для всех остальных семи полей. Эффект: обновление одного потока **не
   сбрасывает** уже накопленные значения других — состояние монотонно
   накапливается по мере того, как приходят первые эмиссии всех 8 потоков
   (Drift `.watch()` эмитит текущий результат сразу при подписке, затем на
   каждое изменение таблицы).
9. `InWorkPage`'s `BlocBuilder<InWorkBloc, InWorkState>` рендерит
   `EventTilesWidget` только когда состояние — `InWorkSuccess`; для
   начального `InWorkInitial` (до первой эмиссии хотя бы одного из 8
   потоков) возвращается `const SizedBox.shrink()` — пустой экран без
   лоадера.
10. При рендере `EventTilesWidget` вычисляются два производных значения:
    `totalVacc = (vaccinationsCount ?? 0) + (editableVaccinationsCount ?? 0)
    + (deletableVaccinationsCount ?? 0)` и `totalReg = animalsToCreateCount
    ?? 0`. Строятся ровно 6 `EventTileData` (у каждой `title: ''` —
    поле есть в модели, но остаётся пустой строкой на каждой из шести
    плиток, нигде не используется этим экраном):
    1. «Взвешивание» (`Assets.eventWeighing`) — `count:
       animalWeighingsCount` (передан как есть, без ternary) → `onTap:
       context.pushNamed2(Routes.unsentAnimalWeighings)`.
    2. «Перемещение» (`Assets.eventMovement`) — `count: movementsCount` →
       `onTap: context.pushNamed2(Routes.unsentMovements)`.
    3. «Вакцинация» (`Assets.eventVaccination`) — `count: totalVacc > 0 ?
       totalVacc : null` (явный ternary, единственная плитка, где ноль
       обнуляется до `null` в коде страницы, а не в виджете) → `onTap:
       context.pushNamed2(Routes.unsentVaccination)`.
    4. «Выбытие» (`Assets.eventDisposal`) — `count: disposalListsCount` →
       `onTap: context.pushNamed2(Routes.unsentDisposals)`.
    5. «Регистрация животных» (`Assets.eventRegistration`) — `count: totalReg
       > 0 ? totalReg : null` (тот же explicit-ternary паттерн, что у
       вакцинации) → `onTap: context.pushNamed2(Routes.unsentAnimalGroups,
       extra: AnimalsToCreateUpdateFilter.all)`.
    6. «Инвентаризация» (`Assets.eventInventory`) — `count: inventoryCount`
       → `onTap: context.pushNamed2(Routes.unsentInventories)`.
11. `EventCardWidget` для любой плитки показывает числовой бейдж
    (`_CountBadge`) только если `eventTileData.count != null &&
    eventTileData.count! > 0` — для плиток 1/2/4/6 эта проверка выполняется
    внутри самого виджета (значение передано как есть, включая возможный
    `0`); для плиток 3/5 ноль уже заранее заменён на `null` в коде страницы
    — два разных места одного и того же эффекта «бейдж не показывается при
    нуле».
12. Кнопка «Синхронизировать данные» внизу (`BlackCircleButton`,
    `l10n.sync_data`) диспатчит `context.read<DataUpdateBloc>().add(const
    DataUpdateStartAll(isUpdateData: true))` —
    [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
    путь (а). `DataUpdateBloc` читается из провайдера, поднятого один раз в
    корне (`lib/main.dart`, `BlocProvider<DataUpdateBloc>`), не создаётся
    самим `InWorkPage`. Сам `InWorkPage` не подписан ни на какое состояние
    `DataUpdateBloc` — реакция на прогресс/ошибку/успех прохода (открытие
    `DataUpdatePage` при `DataUpdateInProgress`) происходит на уровень выше,
    в `MultiBlocListener` из `lib/pages/main/main_page.dart` (`BlocListener<DataUpdateBloc,
    DataUpdateState>`), общем для всей навигационной оболочки — эта часть
    не специфична для `InWorkPage` и не предмет этого файла.

### Альтернативные потоки

- **Пустой экран до первой эмиссии.** Между созданием `InWorkBloc` и первым
  `add(InWorkEventLoad)` состояние — `InWorkInitial`, `InWorkPage` рендерит
  `SizedBox.shrink()` — не лоадер, буквально ничего. На практике Drift
  `.watch()`-потоки эмитят текущий результат запроса почти сразу после
  подписки (асинхронно, но без сетевого ожидания), поэтому окно пустого
  экрана обычно очень короткое, но структурно не гарантировано нулевым —
  8 подписок стартуют синхронно в конструкторе, но их первые эмиссии
  приходят по мере разрешения 8 независимых асинхронных Drift-запросов, не
  одновременно.
- **Ни одна не отправленная запись ни по одной категории (все значения —
  `0`).** Ни одна из шести плиток не показывает бейдж (`count == null` или
  `count! <= 0` для всех шести) — плитки остаются нажимаемыми, каждая ведёт
  на свой (в этом случае пустой) хаб — тот же `RESULT` (`READ_OK`), просто
  без визуальных бейджей; отдельного «пустого состояния» на уровне самого
  `InWorkPage` нет (в отличие, например, от [UC-79](UC-79-ACTOR-5-EVT-40-ENT-14-READ_OK-IN-ANIMAL.md),
  где хаб-экран одной категории явно показывает `list_is_empty`) — здесь
  «пусто» просто выглядит как отсутствие шести бейджей на тех же шести
  плитках.
- **Гость проходит тот же путь.** Как зафиксировано в «Пользователь», ни
  точка входа (`ProfileView`), ни сам `InWorkBloc`/его 6 репозиториев не
  проверяют авторизацию — гость, локально создавший записи (регистрация,
  взвешивание, вакцинация, перемещение, выбытие, инвентаризация доступны
  ему точно так же, см. [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)),
  увидит на этом экране те же самые ненулевые бейджи, что и авторизованный
  пользователь на том же устройстве — см. «Открытые вопросы».
- **Возврат с любого из шести хабов не создаёт отдельного пути.** Переходы
  на все шесть маршрутов выполняются обычным `context.pushNamed2` без
  `await`/обработки результата; `InWorkBloc` живёт на месте (не
  пересоздаётся при переходах вглубь того же поддерева навигации) и
  продолжает получать события от всех 8 подписок независимо от того, какой
  хаб сейчас открыт поверх него — если что-то было отправлено/удалено на
  дочернем хабе, соответствующая Drift-таблица меняется, поток эмитит
  новое значение, и бейдж на `InWorkPage` (если пользователь вернётся назад)
  обновится сам, без какого-либо явного события возврата.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность
  `ENT`-сегмента этого use-case (по id [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md)).
  На этом экране непосредственно читается только узкая часть таблицы —
  `id < 0 AND farmId IS NOT NULL` (плитка «Регистрация животных») — само
  состояние `Animal` этим сценарием не меняется, только считывается счётчик.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement, ANIMAL) —
  читается целиком (`sync = false`), дедуплицируется на клиенте по ключу
  `fromId_placeId_HHmm` для плитки «Перемещение».
- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination,
  ANIMAL) — три независимых счётчика (`sync=false` с разными комбинациями
  `createdAt`/`updatedAt`/`deletedAt`), суммируются в один бейдж
  «Вакцинация».
- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing,
  ANIMAL) — один счётчик (`sync = false`) для плитки «Взвешивание».
- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal, ANIMAL) —
  один счётчик (`sync = false`, без группировки) для плитки «Выбытие» — см.
  «Бизнес-правила» о несоответствии имени поля (`disposalListsCount`) и
  фактического предиката (считает строки, не списки/группы).
- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport, ANIMAL) — `UnsentReportAnimals` с `type='inventory'
  AND readyToSend=true`, дедуплицируется по `sessionUuid`/легаси-ключу для
  плитки «Инвентаризация».
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate,
  SYSTEM) — не читается и не изменяется самим просмотром экрана; кнопка
  «Синхронизировать данные» на этом же экране инициирует полный sync-проход,
  который эту сущность пишет — за пределами данного `READ_OK`-сценария (см.
  [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)).
- `Ad`/`Chat`/`ChatMessage` ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md) и
  далее, BOARD) — **явно не читаются и не показываются**: подтверждённое
  задачей отсутствие BOARD в этом сценарии (см. «Назначение»).

### Бизнес-правила

- **8 потоков → 6 плиток**, не 1:1 — вакцинация одна плитка объединяет 3
  счётчика (новые + редактируемые + помеченные на удаление), остальные пять
  плиток — по одному потоку каждая.
- **Состояние монотонно накапливается, не перезаписывается целиком.**
  `InWorkEventLoad`/`InWorkData.copyWith` устроены так, что любое из 8
  событий обновляет ровно одно поле, остальные семь сохраняют предыдущее
  значение через `newValue ?? oldValue` — при этом любое реальное
  (не-null) значение потока, включая `0`, корректно перекрывает предыдущее
  (`??` реагирует только на `null`, не на `0`/falsy).
- **Бейдж скрывается на `null`ИЛИ на `0`, но двумя разными механизмами.**
  Для плиток 1/2/4/6 условие `count! > 0` — внутри `EventCardWidget`
  (общий на все плитки виджет); для плиток 3/5 (вакцинация, регистрация) то
  же самое условие явно продублировано в коде страницы (`totalX > 0 ?
  totalX : null`) до передачи в `EventTileData` — тот же наблюдаемый
  результат достигается двумя разными по коду путями, специфично именно
  этим двум плиткам, у которых `count` — производная сумма, а не поле
  `InWorkData` напрямую.
- **Дедупликация — на трёх разных уровнях архитектуры для трёх разных
  плиток.** Перемещение — дедуплицируется в `.listen`-колбэке самого
  `InWorkBloc` (не в БД, не в репозитории). Инвентаризация —
  дедуплицируется внутри репозитория (`UnsentReportAnimalsRepository.watchInventorySessionCount`),
  `InWorkBloc` только ретранслирует уже посчитанное число. Выбытие и
  вакцинация — **не дедуплицируются нигде** (голый `COUNT(id)` по
  строкам), несмотря на то что групповое выбытие/вакцинация нескольких
  животных одним действием тоже создаёт по одной строке на животное (тот
  же структурный паттерн, что у перемещения, по [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)/[ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)/[ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md))
    — три сущности с одинаковой «одна строка на одно животное» моделью
  получают на этом экране три разных подхода к счётчику: дедуп по времени
  (Movement), сумма трёх статусов без дедупа (Vaccination), голый счёт
  строк без дедупа (Disposal).
- **Имя поля `disposalListsCount` не соответствует тому, что оно на самом
  деле считает.** Название предполагает подсчёт списков/групп выбытия (в
  `DisposalRepository` есть отдельная группирующая логика при отправке —
  `_groupForSend`, и хаб-экран оперирует понятием «группа»,
  `UnsentDisposalsCubit.deleteGroup(List<DisposalWithDetails>)`), но
  `DisposalDao.watchCountNotSync` — простой `COUNT(id) WHERE sync=false`,
  без `groupBy` какого-либо вида. Батч-выбытие нескольких животных одним
  действием даёт на этой плитке число строк (по одной на животное), не
  число батчей — в отличие от плитки «Перемещение», которая для аналогичной
  структуры данных (одна строка на животное) явно схлопывает батч в «одно
  событие».
- **Счётчик плитки «Регистрация животных» и счётчик, который использует сам
  хаб этой плитки, — разные DAO-запросы с разным предикатом.**
  `InWorkBloc` использует `AnimalsDao.watchCountLocalAnimalsToCreate`
  (`id < 0 AND farmId IS NOT NULL`); `UnsentAnimalGroupsPage`/`UnsentAnimalsBloc`
  (первый экран, открывающийся по этой плитке) используют
  `AnimalsDao.watchLocalAnimalsCount` (`id < 0`, без условия по `farmId`) —
  тот же класс расхождения, что уже задокументирован для вакцинации в
  [UC-79](UC-79-ACTOR-5-EVT-40-ENT-14-READ_OK-IN-ANIMAL.md) («Бизнес-правила»):
  оба запроса совпадают, пока не существует локальной записи `Animal` с
  `id < 0 AND farmId IS NULL` — реальная достижимость такой записи в шаге
  регистрации (`farmPlace`) на глубину REG-визарда в рамках этого файла не
  перепроверялась (см. «Открытые вопросы»).
- **BOARD не участвует ни в одном из 8 потоков** — подтверждено списком
  инжектируемых репозиториев `InWorkBloc` (см. «Назначение»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров нет — основной поток (реактивное построение всех шести плиток,
дедупликация перемещений/инвентаризации, кнопка ручного sync-прохода)
полностью реализован и достижим из UI одним нажатием с экрана профиля.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build` (квадратная `ProfileButton`, `l10n.in_work__title`) | CURRENT | единственная точка входа во всём `lib/`, без проверки авторизации |
| `lib/pages/profile/profile_bloc.dart` | `ProfileBloc.on<ProfileEventStart>` | CURRENT | явно поддерживает `user == null` (гость) без редиректа — предок точки входа |
| `lib/pages/routes.dart` | `Routes.inWork`, `Routes.unsentAnimalWeighings`, `Routes.unsentMovements`, `Routes.unsentVaccination`, `Routes.unsentDisposals`, `Routes.unsentAnimalGroups`, `Routes.unsentInventories` | CURRENT | маршрут экрана и маршруты всех шести хабов, на которые ведут плитки |
| `lib/pages/in_work/in_work_page.dart` | `InWorkPage.build`, `EventTilesWidget.build`, `_MainContentState`-независимый `BlocProvider<InWorkBloc>` | CURRENT | создание bloc'а без `load()`, вычисление `totalVacc`/`totalReg`, layout шести плиток, кнопка sync |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (конструктор — 8 подписок), `on<InWorkEventLoad>` | CURRENT | предмет этого файла — вся реактивная сборка состояния |
| `lib/pages/in_work/in_work_event.dart` | `InWorkEventLoad` | CURRENT | 8 опциональных полей, ровно одно заполнено на вызов |
| `lib/pages/in_work/in_work_state.dart` | `InWorkInitial`, `InWorkSuccess` | CURRENT | состояния экрана (`Equatable`, не `freezed`) |
| `lib/widgets/event_card_widget.dart` | `EventTileData`, `EventCardWidget.build`, `_CountBadge` | CURRENT | рендер одной плитки; условие показа бейджа (`count != null && count! > 0`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.watchCountLocalAnimalsToCreate`, `.watchLocalAnimalsCount` | CURRENT | первый — источник бейджа этого экрана; второй — источник счётчика хаба той же плитки, другой предикат |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.watchCountLocalAnimalsToCreate`, `.watchLocalAnimalsCount` | CURRENT | `id<0 ∧ farmId IS NOT NULL` против `id<0` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.watchCountNotSync` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalDao.watchCountNotSync` | CURRENT | `COUNT(id) WHERE sync=false`, без `groupBy` — см. «Бизнес-правила» |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.watchCountNotSync` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.watchCountNotSync` | CURRENT | `COUNT(id) WHERE sync=false` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.watchCountNotSync`, `.watchCountEditableVaccinations`, `.watchCountDeletableVaccinations` | CURRENT | три тонкие делегации в DAO |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.watchCountNotSync`, `.watchCountEditableVaccinations`, `.watchCountDeletableVaccinations` | CURRENT | три разных предиката по `sync`/`createdAt`/`updatedAt`/`deletedAt` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.watchNotSyncMovements` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementDao.watchAllNotSync` | CURRENT | `sync=false`, без агрегации — дедуп выполняется в `InWorkBloc` |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `Movements` (в т.ч. `createdAt`/`updatedAt`, не описанные в [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)) | CURRENT | `createdAt` — второй по приоритету источник даты в ключе дедупликации |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.watchInventorySessionCount` | CURRENT | сворачивает список строк в число уникальных сессий (`sessionUuid`/легаси-ключ) |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.watchInventoryReadyList` | CURRENT | `type='inventory' ∧ readyToSend=true` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc`, `DataUpdateStartAll` | CURRENT | получатель диспатча кнопки «Синхронизировать данные»; сам проход — [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md), не предмет этого файла |
| `lib/main.dart` | `BlocProvider<DataUpdateBloc>` | CURRENT | единственный на процесс инстанс, поднят в корне, не создаётся `InWorkPage` |
| `lib/pages/main/main_page.dart` | `MultiBlocListener` → `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | реагирует на прогресс/ошибку прохода уровнем выше `InWorkPage`, показом `DataUpdatePage`; сам `InWorkPage` этого состояния не читает |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.deleteGroup` | CURRENT | косвенное подтверждение, что хаб-экран этой плитки сам оперирует понятием «группа», в отличие от голого счётчика на «В работе» |

## Критерии приёмки

- При открытии `InWorkPage` не выполняется ни одного явного «загрузочного»
  вызова — все 6 плиток заполняются исключительно за счёт 8 Drift-подписок,
  инициированных в конструкторе `InWorkBloc`.
- Пока не пришла ни одна из 8 первых эмиссий, экран пуст (`SizedBox.shrink()`),
  без индикатора загрузки.
- Изменение любой из шести отслеживаемых таблиц (`Animals`, `Disposals`,
  `AnimalWeighings`, `Vaccinations`, `Movements`, `UnsentReportAnimals`) —
  в т.ч. вызванное действием на дочернем хаб-экране этой же плитки —
  автоматически обновляет соответствующий бейдж на `InWorkPage`, без
  повторного открытия экрана и без отдельного события «возврата».
- Для перемещений: N строк `Movement` с одинаковыми `fromId`/`placeId` и
  временем, совпадающим с точностью до минуты, отображаются как один
  бейдж-инкремент, а не N.
- Для инвентаризации: строки одной сессии (общий `sessionUuid`, или общий
  `farmId`/`placeId`/календарный день для легаси-строк без `sessionUuid`)
  отображаются как один бейдж-инкремент.
- Для вакцинации: бейдж — сумма трёх независимых счётчиков (новые +
  редактируемые + помеченные на удаление).
- Для выбытия: бейдж — число строк `Disposals` с `sync=false`, **без**
  группировки по батчу/списку выбытия, несмотря на название поля
  `disposalListsCount`.
- Бейдж любой из шести плиток не отображается, если итоговое значение —
  `null` или `0` (для всех шести плиток — тем или иным из двух эквивалентных
  по эффекту путей, см. «Бизнес-правила»).
- Нажатие кнопки «Синхронизировать данные» диспатчит `DataUpdateStartAll(isUpdateData:
  true)` в общий, поднятый в корне `DataUpdateBloc` — сам `InWorkPage` не
  показывает никакой немедленной обратной связи по этому нажатию (реакция —
  на уровень выше, в `MainPage`).
- Ни один из шести источников данных этого экрана не читает и не пишет
  ничего из BOARD.

## Связанные тесты

`test/pages/in_work_bloc_test.dart`:

- Группа `'UC-197 — InWorkBloc реактивные подписки'` (дословно, см.
  «Открытые вопросы» — расхождение номера с этим файлом):
  - `'конструктор подписывается на все 8 потоков без падений, начальное
    состояние InWorkInitial'` — создаёт `InWorkBloc`, проверяет
    `bloc.state is InWorkInitial` без единой эмиссии в контроллеры.
  - `'каждый поток независимо обновляет свой счётчик в InWorkSuccess.data'`
    — последовательно (с `pumpEventQueue()` между каждым) шлёт значения во
    все 7 int-контроллеров (`animalsToCreateController`, `disposalController`,
    `weighingsController`, `vaccinationsController`,
    `editableVaccinationsController`, `deletableVaccinationsController`,
    `inventoryController`) и проверяет, что каждое поле `InWorkData` приняло
    ровно посланное значение (движения в этом тесте не участвуют).
  - `'обновление одного потока не сбрасывает уже накопленные значения
    других (copyWith merge)'` — шлёт `animalsToCreateController.add(3)`,
    затем `disposalController.add(2)`, проверяет, что оба значения (3 и 2)
    сохранились одновременно — прямая проверка `copyWith`-merge-семантики,
    описанной в шаге 8 «Основного потока».
- Группа `'UC-197 — InWorkBloc дедупликация перемещений'` (тот же
  расхождение номера):
  - `'несколько записей с одинаковым from/to/HHmm -> считаются одним
    событием'` — два `Movement` с `fromId: 1, placeId: 2`, `placeDate`,
    отличающимся на 30 секунд (`time` и `time.add(Duration(seconds: 30))`),
    ожидает `movementsCount == 1`.
  - `'записи с разным from/to/HHmm -> считаются раздельно'` — два `Movement`
    с разными `placeId` (2 и 3), тем же временем, ожидает `movementsCount ==
    2`.

Оба сценария из задачи покрыты тестами по существу. **Не покрыты тестами**:
дедупликация инвентаризации (`watchInventorySessionCount`,
`sessionUuid`/легаси-ключ) — ни в `in_work_bloc_test.dart`, ни где-либо ещё
(`grep -rn "watchInventorySessionCount" test/` не находит тестового файла на
сам репозиторий); суммирование трёх счётчиков вакцинации в `totalVacc` и
условная замена `0` на `null` (эта логика — в `in_work_page.dart`, не в
`in_work_bloc.dart`, а виджет-тестов на `InWorkPage` в репозитории нет
вовсе — `find test -iname "*in_work*"` находит только
`in_work_bloc_test.dart`); показ/скрытие бейджа в `EventCardWidget` при
`count == 0`.

**TBD — теста нет** на: рендер `InWorkPage`/`EventTilesWidget` целиком
(маппинг 6 плиток на маршруты, видимость бейджей), и на
`UnsentReportAnimalsRepository.watchInventorySessionCount` отдельно от
`InWorkBloc`.

## Открытые вопросы и ограничения

- **Расхождение номера теста с этим use-case.** Обе группы теста в
  `test/pages/in_work_bloc_test.dart` названы `'UC-197 — …'`, не `'UC-197 —
  …'` — `grep -r "UC-197" test/` не находит ничего, хотя по содержанию
  (все 8 подписок, дедупликация перемещений) это ровно сценарий,
  описываемый этим файлом. Согласно инструкции, тест не переименовывается
  в рамках этого прохода — переименование в `UC-197` (или подтверждение,
  что `297` был правильным номером, а частью пересборки является этот
  файл) остаётся оператору отдельным шагом.
- **Кто на самом деле может инициировать [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) — открытый
  вопрос к самому событию, не решаемый этим файлом.** Frozen-текст
  [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) и
  [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) называют инициатором
  строго авторизованного пользователя. Прямым чтением кода («Пользователь»
  выше) подтверждено: единственная точка входа (`ProfileView`) не проверяет
  `isAuthorized()`, `ProfileBloc` явно поддерживает `user == null`, а все 6
  репозиториев `InWorkBloc` — чистые локальные Drift-запросы без проверки
  авторизации. В модуле `ANIMAL` уже существует отдельный,
  специально описанный для симметричной ситуации актор —
  [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) («текущий пользователь
  приложения, независимо от статуса авторизации» — именно он инициирует
  создание всех записей, чьи счётчики показывает этот экран: REG/MOVE/VAC/WEIGH/DISP/INV).
  Гость, реально накопивший локальные записи по любой из шести категорий
  (что ему доступно наравне с авторизованным пользователем, по
  [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)), увидит на этом экране
  те же самые ненулевые бейджи — этот файл фиксирует данный факт как
  проверенный чтением кода, не как предложение переименовать актора в
  frozen [EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md)
  или сам этот use-case — по правилам пайплайна замена id — решение
  оператора, не этого документирующего прохода.
- **Два из шести хабов, на которые ведут плитки, не имеют собственного
  «*-VIEWED-UNSENT-IN-ANIMAL»-события в дереве специк**, в отличие от
  остальных четырёх. Проверено перечислением `sdlc/2-specs/events/*VIEWED*`:
  существуют [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md)
  (вакцинация), [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md)
  (взвешивание), [EVT-55](../events/EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md)
  (выбытие), [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md)
  (инвентаризация) — но ни одного `MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL`, ни
  `ANIMAL-REGISTRATIONS-VIEWED-UNSENT-IN-ANIMAL` (или аналога) для
  `Routes.unsentMovements`/`Routes.unsentAnimalGroups`. Единственное
  READ-событие, где сегодня фигурирует `Movement` — [EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md)
  (system-side pull при sync-проходе, не пользовательский просмотр хаба,
  см. [UC-62](UC-62-ACTOR-4-EVT-31-ENT-13-READ_OK-IN-ANIMAL.md)) — принципиально
  другой сценарий. Из-за этого пробела «Основной поток» этого файла (шаг
  10, плитки 2 и 5) не цитирует несуществующие события markdown-ссылкой —
  только называет целевые маршруты. Восполнение пробела (выпуск новых
  `EVT`/`UC` для этих двух хабов) — вне рамок этого документирующего
  прохода по MOD-7.
- **`ENT-13` (Movement) не документирует поля `createdAt`/`updatedAt`**,
  хотя `createdAt` — второй по приоритету источник даты в самом ключе
  дедупликации, разбираемом этим файлом (`m.placeDate ?? m.createdAt ??
  DateTime.now()`). Проверено чтением `Movements`-таблицы напрямую
  (`packages/sheep_farm_database/lib/entities/movement/movement.dart`) —
  оба поля существуют в схеме, оба `nullable`. Так как [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)
  заморожен, этот файл не правит его таблицу полей, только фиксирует
  пробел.
- **Предикат `disposalListsCount` (голый `COUNT` строк) против
  предполагаемого именем поля смысла («списки»/группы) — не переисследован
  здесь на предмет продуктовой намеренности.** Возможно, поле изначально
  задумывалось как счётчик групп и было упрощено до счётчика строк
  осознанно (например, потому что группировка выбытия сложнее группировки
  перемещений по времени) — код/комментарии рядом с
  `DisposalDao.watchCountNotSync` этого не проясняют.
- **Расхождение предикатов `watchCountLocalAnimalsToCreate` (эта плитка,
  `farmId IS NOT NULL`) и `watchLocalAnimalsCount` (хаб той же плитки, без
  условия по `farmId`) не переисследовано на предмет реальной
  достижимости** — то есть может ли вообще существовать персистентная
  локальная запись `Animal` с `id<0 ∧ farmId IS NULL` при текущем визарде
  регистрации (`AnimalRegistrationBloc`, шаг `farmPlace` из `singleSteps`).
  Тот же класс расхождения уже зафиксирован для вакцинации в
  [UC-79](UC-79-ACTOR-5-EVT-40-ENT-14-READ_OK-IN-ANIMAL.md), где он также
  остался неразрешённым «зависит от инварианта, не проверяется в момент
  чтения».
- **Виджет-теста на `InWorkPage`/`EventTilesWidget` нет вовсе** — ни на
  маппинг плитка→маршрут, ни на условие видимости бейджа при `count == 0`,
  ни на явные `ternary`-преобразования `totalVacc`/`totalReg` в коде самой
  страницы (в отличие от логики `InWorkBloc`, которая тестами покрыта).
