# UC-130 — Хаб неотправленных сессий инвентаризации отказывает технически: `UnsentInventoriesCubit.load` ловит исключение и показывает пользователю читаемое сообщение об ошибке

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md)
(`animal_inventory.viewed_unsent`): пользователь открывает хаб ещё не
отправленных (`readyToSend == true`) сессий инвентаризации со сводного экрана
«В работе», а `UnsentInventoriesCubit.load`
(`lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart`) — при
исключении, брошенном в любой точке чтения/сопоставления данных — переходит в
явное состояние `UnsentInventoriesState.error(e.toString())`, и
`UnsentInventoriesPage` рендерит это сообщение пользователю через
`ProgressMessage.somethingWentWrong(message: msg)`. Перепроверено чтением
метода целиком: **весь метод, кроме самого первого `emit(loading())`, обёрнут
в один `try/catch`** — это охватывает не только начальный вызов
`_reportAnimalsRepo.getInventoryReadySessions()`, но и последующую
группировку/дедупликацию строк по `sessionUuid`, и все per-сессионные
обращения к `FarmRepository`/`PlaceRepository` внутри цикла построения
`UnsentInventoryItem`.

Это **положительный контраст**, а не находка о дефекте: в отличие от
большинства других read-сценариев этой же под-области `INV`,
`UnsentInventoriesCubit.load` — реализация с явной обработкой ошибки от
начала до конца. В частности, соседний кубит той же под-области,
обслуживающий другой read-экран того же события `INV` — `InventoryReportDetailsCubit.load`
(`lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart`,
итоговый отчёт по сессии/дню, [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)) —
не содержит вообще ни одного `try`/`catch`, а его состояние
(`InventoryReportDetailsState`, `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart`)
даже не является freezed-union и физически не имеет варианта `error` — при
исключении там неминуемо возникло бы необработанное отклонение `Future`, как
это уже задокументировано для других кубитов этой под-области
([UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md),
[UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)). Здесь же
пользователь гарантированно увидит экран с сообщением, а не бесконечный
спиннер.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Проверено чтением
`lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` целиком:
`UnsentInventoriesCubit` объявляет только три зависимости
(`_reportAnimalsRepo`, `_farmRepo`, `_placeRepo`) и нигде не использует
`AuthRepository`/проверку `isAuthorized` — доступ к хабу неотправленных
сессий инвентаризации не зависит от статуса авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`,
   `lib/pages/in_work/in_work_page.dart`) и тапает по плитке «Инвентаризация»
   (`EventTileData(... value: l10n.inventory, count: data.inventoryCount,
   onTap: () => context.pushNamed2(Routes.unsentInventories))`); счётчик
   плитки — отдельный поток из `InWorkBloc._inventoryCountSubscription`
   (`_unsentReportAnimalsRepository.watchInventorySessionCount()`), не тот
   метод, что вызывает этот сценарий (см. «Открытые вопросы»).
2. Открывается `UnsentInventoriesPage`
   (`lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart`,
   маршрут `Routes.unsentInventories`, зарегистрирован в `lib/pages/routes.dart`).
   `build` создаёт `BlocProvider(create: (context) =>
   UnsentInventoriesCubit()..load(), ...)` — вызов `load()` через каскадный
   оператор (`..`) синхронно со сборкой страницы; сам `create` не сохраняет и
   не awaits `Future<void>`, который вернул бы `load()` (тот же паттерн, что
   и в соседних хабах, например
   [UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md)) — но здесь
   это не приводит к необработанному отклонению `Future`, потому что сам
   `load()` не отклоняется ни при каком внутреннем исключении (см. шаг 5).
3. `UnsentInventoriesCubit.load()` сразу эмитит
   `const UnsentInventoriesState.loading()` (единственная строка вне
   `try`), затем входит в `try`:
   - `rows = await _reportAnimalsRepo.getInventoryReadySessions()`;
   - группирует `rows` в `Map<String, ({farmId, placeId, time, count})>` по
     ключу `row.sessionUuid ?? 'legacy_${row.farmId}_${row.placeId}_${...}'`,
     суммируя `count` и беря более позднее `time` при совпадении ключа;
   - сортирует по `time` по убыванию;
   - для каждой сессии, чей ключ не начинается с `'legacy_'` (легаси-строки
     без `sessionUuid` пропускаются целиком, `continue`, — то же правило,
     что уже задокументировано в [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)),
     резолвит `farm = farmCache[s.farmId] ??= await _farmRepo.getById(s.farmId)`
     (кэш по `farmId`, пропуская сессию целиком, если `farm == null`), затем
     аналогично `place = placeCache[s.placeId] ??= await _placeRepo.getById(s.placeId)`,
     затем `placeAnimalsCache[s.farmId] ??= await _placeRepo.getAllWithThisFarmIdWithAnimals(s.farmId)` —
     каждый вызов кэшируется по `farmId`/`placeId`, так что при нескольких
     сессиях одной фермы/места повторного сетевого/БД-обращения не будет, но
     и повторной попытки при сбое первого вызова тоже не будет (см.
     «Альтернативные потоки»);
   - собирает `UnsentInventoryItem` (место/ферма/дата+время/суммарный
     `animalCount`/`sessionUuid`) и в конце эмитит
     `UnsentInventoriesState.loaded(items: items)`.
4. **Точка технического сбоя (этот сценарий).** Любой из перечисленных выше
   `await`-вызовов внутри `try` бросает исключение — в тесте
   (`test/pages/unsent_inventories_cubit_test.dart`) это воспроизводится на
   уровне первого чтения:
   `when(() => reportAnimalsRepository.getInventoryReadySessions()).thenThrow(Exception('db error'))`.
5. `catch (e)` перехватывает исключение **без логирования** (ни `Talker`, ни
   любой другой механизм здесь не вызывается — перепроверено чтением полного
   списка импортов файла кубита: `Talker`/логгер не импортирован вовсе) и
   безусловно эмитит `UnsentInventoriesState.error(e.toString())` — сырой
   текст исключения, единственный аргумент `error`-варианта
   (`lib/pages/unsent_inventories/cubit/unsent_inventories_state.dart`).
   `load()` возвращает управление нормально (`Future<void>` не отклоняется) —
   именно это отличает данный сценарий от `create:`-каскадов, где
   необработанное исключение внутри `load`/`loadNotSync` рождает
   необработанное отклонение `Future` в текущей Dart Zone.
6. `UnsentInventoriesPage`'s `BlocBuilder` реагирует на ветку `error` через
   `state.when(...)`: `error: (msg) => BottomSheetPageWrapper(child: Center(child:
   ProgressMessage.somethingWentWrong(message: msg)))`. `ProgressMessage.somethingWentWrong`
   (`lib/widgets/progress_bar/progress_message.dart`) собирает виджет из
   иконки `Assets.imSomethingWentWrong` (SVG, статичная для любого текста) и
   строки текста; поскольку `message` (= `e.toString()`, например `'Exception:
   db error'`) непустой, конструктор **не подставляет** свой дефолт `'Что-то
   пошло не так'` (`message.isNotEmpty ? message : 'Что-то пошло не так'`) —
   пользователь видит иконку «что-то пошло не так», но текстом под ней
   служит сырая, нелокализованная строка исключения, не дружелюбное
   сообщение.
7. Единственный способ выйти из этого состояния — уйти со страницы
   (стандартная кнопка «назад» `CustomAppBar`) и заново открыть хаб из
   `InWorkPage`, что создаёт новый `UnsentInventoriesCubit` и заново вызывает
   `load()`; ветка `error` в отличие от ветки `loaded` не обёрнута в
   `RefreshIndicator` — потянуть вниз для повтора на самом экране ошибки
   нельзя.

### Альтернативные потоки

- **Исключение из `_farmRepo.getById`/`_placeRepo.getById`/`_placeRepo.getAllWithThisFarmIdWithAnimals`
  внутри цикла по сессиям, а не из первого чтения.** Тот же `try/catch`
  покрывает и эти вызовы — исключение из любого из них приводит к
  идентичному переходу в `error(e.toString())`, независимо от того, сколько
  сессий уже успело быть обработано до этой точки (частичный результат не
  сохраняется — `items` собирается локально внутри `try` и никогда не
  эмитится частично). Не покрыто отдельным тестом (см. «Связанные тесты»);
  существующий тест мокает сбой только на уровне
  `getInventoryReadySessions()`.
- **Кэши (`farmCache`/`placeCache`/`placeAnimalsCache`) не пере-пытываются
  после сбоя.** Поскольку `farmCache[s.farmId] ??= await _farmRepo.getById(s.farmId)`
  присваивает кэш только при успешном завершении `await` (при исключении
  запись в `Map` не появляется), повторный `load()` после ошибки выполнит
  все репозиторные вызовы заново «с нуля» — не проблема сама по себе (кубит
  создаётся заново при повторном открытии страницы), но означает, что внутри
  одного и того же вызова `load()` частично успешный кэш не переживает
  исключение (сам `load()` в этом случае уже целиком завершается веткой
  `catch`).
- **`farm == null`/`place == null` (сессия не найдена в справочнике) — не
  этот файл.** Это не исключение: строка молча пропускается (`continue`) и
  ведёт к `loaded` с более коротким (или пустым) списком, а не к `error` —
  задокументировано отдельным `READ_OK`-тестом (`'farm не найден по id ->
  сессия пропускается'`, см. «Связанные тесты», не входит в этот сценарий).
- **Легаси-строки без `sessionUuid` — не этот файл.** Пропускаются тем же
  `continue` (см. `ENT-17`), не порождают исключения; ведут к `loaded`, а не
  к `error`.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals`) — целевая сущность чтения:
  при сбое ни одна `readyToSend`-сессия не попадает в UI, независимо от
  того, сколько их было в БД — весь результат отбрасывается одним `catch`,
  без сохранения частично прочитанного.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — читается через
  `FarmRepository.getById(s.farmId)` на каждую уникальную ферму среди
  найденных сессий (результат кэшируется в `farmCache`); не изменяется этим
  сценарием; сам может быть источником исключения (см. «Альтернативные
  потоки»).
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается
  через `PlaceRepository.getById(s.placeId)` и
  `PlaceRepository.getAllWithThisFarmIdWithAnimals(s.farmId)` (кэшируются в
  `placeCache`/`placeAnimalsCache`); не изменяется этим сценарием; тоже
  потенциальный источник исключения.

### Бизнес-правила

- Технический сбой (исключение из чтения `UnsentReportAnimals` или из
  последующего резолва фермы/места) классифицируется как `READ_ERROR`, а не
  `READ_REJECTED` — единственная «отклоняющая» логика метода (легаси-строки,
  строки без `farmId`/`placeId`, ферма/место не резолвится) реализована
  через тихий `continue`, ведущий к `loaded` (пустому или укороченному
  списку), а не к `error`; `error` наступает исключительно от непойманного
  технического исключения.
- Один и тот же `try/catch` покрывает и сам вызов
  `getInventoryReadySessions()`, и группировку/дедупликацию по `sessionUuid`,
  и все per-сессионные обращения к `FarmRepository`/`PlaceRepository` —
  `catch` не различает источник, любое из них ведёт к одинаковому
  `error(e.toString())`.
- Ошибка не логируется ни в `Talker`, ни куда-либо ещё — единственный след
  сбоя, который видит кто-либо, это сообщение на экране пользователя;
  тот же паттерн «catch без логирования», что и в
  [UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md).
- Сообщение состояния `error` не локализовано — `e.toString()` передаётся в
  `ProgressMessage.somethingWentWrong(message: ...)` напрямую, минуя
  `AppLocalizations`/`context.tr`; поскольку `message` непустой, дружелюбный
  дефолт этого виджета (`'Что-то пошло не так'`) не используется вовсе —
  пользователь видит именно техническую строку исключения.
- В отличие от `InventoryReportDetailsCubit.load` (тот же `INV`, другой
  read-экран — [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)),
  здесь состояние физически способно нести ошибку (`UnsentInventoriesState` —
  freezed-union из `initial`/`loading`/`loaded`/`error`) и метод её реально
  перехватывает — это качественное отличие в надёжности между двумя
  read-сценариями одной и той же под-области, не количественное (не «то же
  самое, но чуть лучше»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (исключение на первом чтении,
`getInventoryReadySessions()`) полностью реализован и покрыт тестом.
Альтернативная точка сбоя (исключение из `FarmRepository`/`PlaceRepository`
внутри цикла по сессиям, уже после успешного первого чтения) технически
покрыта тем же `try/catch`, но не воспроизведена отдельным тестом — см.
«Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (плитка «Инвентаризация») | CURRENT | точка входа — `onTap: () => context.pushNamed2(Routes.unsentInventories)` |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc._inventoryCountSubscription` (`watchInventorySessionCount`) | CURRENT | источник счётчика плитки — другой метод репозитория, чем у самого сценария (см. «Открытые вопросы») |
| `lib/pages/routes.dart` | `Routes.unsentInventories` | CURRENT | константа имени/пути маршрута |
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `UnsentInventoriesPage.build` | CURRENT | `create: (context) => UnsentInventoriesCubit()..load()`; ветка `error` рендерит `ProgressMessage.somethingWentWrong(message: msg)` внутри `BottomSheetPageWrapper`, без `RefreshIndicator` |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | предмет сценария — весь метод, кроме первого `emit(loading())`, обёрнут в один `try/catch` |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_state.dart` | `UnsentInventoriesState.error` | CURRENT | freezed-вариант, несущий `e.toString()` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.getInventoryReadySessions` | CURRENT | тонкая обёртка `dao.getInventoryReadySessions()`, без собственного `try/catch` — протестированная (мокнутая) точка сбоя |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.getInventoryReadySessions` | CURRENT | реальная (немокнутая) реализация — прямой Drift-select по `type == 'inventory' && readyToSend == true` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | вызывается на каждую уникальную `farmId` найденных сессий, кэшируется в `farmCache`; альтернативная (непротестированная) точка сбоя |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById`, `.getAllWithThisFarmIdWithAnimals` | CURRENT | то же для `placeId`/фермы (`placeCache`/`placeAnimalsCache`); альтернативные (непротестированные) точки сбоя |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.somethingWentWrong` | CURRENT | рендер сообщения об ошибке — SVG-иконка + сырой (нелокализованный) текст; собственный дружелюбный дефолт не используется, если `message` непустой |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | контрастный сосед той же под-области (`INV`, [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)) — не содержит `try/catch` вовсе |
| `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart` | `InventoryReportDetailsState` | CURRENT | обычный (не union) freezed-класс — физически не имеет варианта `error` |

## Критерии приёмки

- При исключении из `_reportAnimalsRepo.getInventoryReadySessions()` внутри
  `UnsentInventoriesCubit.load()` кубит эмитит ровно два состояния подряд:
  `UnsentInventoriesState.loading()`, затем
  `UnsentInventoriesState.error(e.toString())` — без промежуточного `loaded`.
- То же самое верно при исключении из `_farmRepo.getById`,
  `_placeRepo.getById` или `_placeRepo.getAllWithThisFarmIdWithAnimals`
  внутри цикла построения `UnsentInventoryItem` — один и тот же
  необёрнутый по источнику `catch`.
- Сообщение состояния `error` — точный результат `e.toString()` брошенного
  исключения, без изменений, без локализации, без логирования в `Talker`
  или любой другой механизм.
- `load()` не бросает исключение наружу и не отклоняет свой `Future<void>` ни
  при каком исключении внутри `try` — вызывающий код (`create:`-каскад
  `UnsentInventoriesPage`) не должен обрабатывать отклонение `Future`.
- `UnsentInventoriesPage` рендерит ветку `error` через
  `Center(child: ProgressMessage.somethingWentWrong(message: msg))` внутри
  `BottomSheetPageWrapper` — пользователь видит иконку «что-то пошло не так»
  и текст `msg` под ней, а не бесконечный спиннер.
- Ветка `error` не обёрнута в `RefreshIndicator` — единственный способ
  повторить попытку — уйти со страницы и открыть хаб заново (новый
  `UnsentInventoriesCubit`, новый вызов `load()`).

## Связанные тесты

- `test/pages/unsent_inventories_cubit_test.dart`, group `'UC-130 —
  UnsentInventoriesCubit.load'` (старая нумерация, переименуется отдельным
  контролируемым проходом — не трогать сейчас), test `'исключение из
  репозитория -> error state'` — прямое покрытие: `reportAnimalsRepository.getInventoryReadySessions()`
  замокан на `thenThrow(Exception('db error'))`; после `cubit.load()`
  проверяется через `cubit.state.when(...)`, что сработала именно ветка
  `error` и `message` содержит подстроку `'db error'` (остальные ветки
  `when` вызывают `fail('expected error')`, если бы сработали).
- Соседняя group `'UC-129 — UnsentInventoriesCubit.load'` (тот же файл, 6
  тестов) покрывает `READ_OK`-исход того же метода — пустой список; несколько
  строк одной `sessionUuid` схлопываются в один `item` с суммарным `count`;
  легаси-сессии без `sessionUuid` пропускаются; строки без `farmId`/`placeId`
  пропускаются; ферма не найдена по id → сессия пропускается; несколько
  разных `sessionUuid` → сортировка по времени по убыванию — не
  документируется здесь, это отдельный сценарий (`READ_OK`).
- **TBD — теста нет** на исключение, брошенное на шаге `_farmRepo.getById`/
  `_placeRepo.getById`/`_placeRepo.getAllWithThisFarmIdWithAnimals` внутри
  цикла по сессиям, уже после успешного `getInventoryReadySessions()` —
  существующий тест мокает сбой только на уровне первого чтения.
- **TBD — теста нет** на widget-уровне (`UnsentInventoriesPage` в состоянии
  `error`) — в `test/` нет widget-теста для этого файла; вывод о рендере
  `ProgressMessage.somethingWentWrong` и об отсутствии `RefreshIndicator` в
  ветке `error` сделан по чтению кода, не по запуску виджета.

## Открытые вопросы и ограничения

- **Счётчик плитки «В работе» и сам сценарий читают через разные методы
  репозитория, с разной трактовкой легаси-строк.** `InWorkBloc` считает
  количество сессий через `watchInventorySessionCount()`
  (`UnsentReportAnimalsRepository`), который включает легаси-строки без
  `sessionUuid` в счёт (синтетический ключ `'legacy_farmId_placeId_day'`);
  `UnsentInventoriesCubit.load()` же (этот сценарий и его `READ_OK`-сосед)
  безусловно пропускает такие строки (`continue`) при построении списка.
  Теоретически это может привести к положительному счётчику на плитке при
  пустом (`loaded([])`) хабе после открытия — но это расхождение проявляется
  в ветке `READ_OK`/пустого списка, не в `READ_ERROR`, задокументированном
  здесь; уже отмечено на уровне сущности в
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md). Не
  разбирается глубже в рамках этого файла.
- **Почему `InventoryReportDetailsCubit.load` (тот же `INV`, соседний
  read-экран) не получил ни `try/catch`, ни варианта `error`, а
  `UnsentInventoriesCubit.load` — получил?** Ничего в коде/комментариях не
  объясняет эту асимметрию внутри одной и той же под-области — как
  осознанное решение (хаб «В работе» важнее для надёжности, чем итоговый
  отчёт) или как случайный результат независимой разработки двух похожих
  экранов, не зафиксировано нигде.
- **Отсутствие логирования и локализации — тот же паттерн, что и в других
  «read»-кубитах этой под-области.** См.
  [UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md) — не
  изолированная особенность этого файла, а сквозной паттерн семейства
  «catch без логирования» среди read-сценариев `ANIMAL`.
- **Нет действия «повторить» на самом экране ошибки.** Пользователю доступен
  только уход со страницы и повторное открытие хаба целиком; является ли
  отсутствие retry-кнопки/`RefreshIndicator` в ветке `error` осознанным
  упрощением UI для редкого технического случая или недосмотром — не
  зафиксировано нигде в коде/комментариях.
