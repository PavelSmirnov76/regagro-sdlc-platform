# UC-114 — История животного: животное не найдено или один из пяти источников бросает исключение

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же триггер, что в успешном сценарии [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md)
(`AnimalHistoryCubit.load`) — пользователь открывает вкладку «История» карточки
животного, — но `load()` завершается ошибкой одним из двух не связанных между
собой путей:

- **(a)** `AnimalsRepository.getAnimalWithDetailsById(animalId)` возвращает
  `null` — животное с этим id не найдено;
- **(b)** один из пяти источников ленты (выбытие/перемещение/взвешивание/
  вакцинация; регистрация — синхронная и сама по себе не бросает) бросает
  исключение.

В обоих случаях кубит эмитит один и тот же вариант `AnimalHistoryState.error(...)`,
и в обоих случаях лента не строится вообще — если хотя бы один из четырёх
асинхронных источников падает, остальные, идущие в коде после него, **вообще
не вызываются** в этом проходе `load()`: вызовы последовательные (`await` один
за другим), а не `Future.wait`, поэтому частичного результата (например «три
источника успели, четвёртый упал — показать эти три») не существует.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `AnimalHistoryCubit` не
объявляет и не использует `AuthRepository` ни в одном методе.

## CURRENT

### Основной поток

1. Пользователь на карточке животного нажимает пункт тулбара «История»
   (`l10n.animal_history_title`) — `context.pushNamed2(Routes.animalHistory,
   extra: AnimalHistoryPageArgs(animal: animalWithDetails))`
   (`lib/pages/animal_card/animal_card_page.dart`). На этот момент животное
   уже существует и загружено — `animalWithDetails` берётся из уже открытой
   карточки, а не запрашивается заново.
2. `AnimalHistoryPage.build` (`lib/pages/animal_history/presentation/
   animal_history_page.dart`) строит `BlocProvider(create: (context) =>
   AnimalHistoryCubit()..load(args.animal.animalId))`. Каскад `..load(...)`
   возвращает сам объект кубита — построение виджет-дерева не зависит от
   исхода `load()`.
3. `AnimalHistoryCubit.load(animalId)` (`lib/pages/animal_history/cubit/
   animal_history_cubit.dart`) синхронно эмитит `AnimalHistoryState.loading()`,
   затем весь остальной код метода обёрнут в один `try/catch`:
   ```dart
   try {
     final animal = await _animalsRepo.getAnimalWithDetailsById(animalId);
     if (animal == null) {
       emit(const AnimalHistoryState.error('Animal not found'));
       return;
     }
     // ... вычисление transponder, затем последовательно:
     groups.addAll(await _buildDisposalGroups(animalId));
     groups.addAll(await _buildMovementGroups(animalId));
     groups.addAll(await _buildWeighingGroups(animalId));
     groups.addAll(await _buildVaccinationGroups(animalId));
     groups.addAll(_buildRegistrationGroups(animal.createdAt, transponder));
     _allGroups = groups;
     emit(AnimalHistoryState.loaded(...));
   } catch (e) {
     emit(AnimalHistoryState.error(e.toString()));
   }
   ```
4. **Ветка (a) — животное не найдено.** `getAnimalWithDetailsById` возвращает
   `null`. Это **не исключение** — явная проверка `if (animal == null)` внутри
   `try`, с `emit` фиксированного, захардкоженного английского текста
   `'Animal not found'` (не через `AppLocalizations`, не через `context.tr`) и
   немедленным `return`. Ни один из пяти источников (выбытие, перемещение,
   взвешивание, вакцинация, регистрация) не вызывается вообще — `return`
   происходит до первой строки, которая их читает. `catch`-блок в этой ветке
   не участвует: путь выхода — обычный `return`, не проброс исключения.
5. **Ветка (b) — исключение в одном из источников.** Животное найдено; метод
   доходит до последовательности `groups.addAll(await _buildXxxGroups(...))`.
   Один из четырёх асинхронных вызовов бросает исключение:
   `_buildDisposalGroups` → `DisposalRepository.getAllByAnimalId` (и, только
   если список выбытий непуст, следом `DisposalReasonsRepository.
   getAllByFilters`), `_buildMovementGroups` →
   `MovementReportRepository.getMovementsWithDetailsByFilters`,
   `_buildWeighingGroups` →
   `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
   `_buildVaccinationGroups` → `VaccinationsRepository.getVaccinationsWithDetails`.
   Исключение всплывает до внешнего `try`, `catch (e)` перехватывает его и
   эмитит `AnimalHistoryState.error(e.toString())` — сырой текст исключения
   Dart (например `'Exception: db error'`), без логирования (ни один вызов
   `Talker` или другого логгера в этом `catch` не происходит).
6. Порядок вызовов в коде фиксирован: disposal → movement → weighing →
   vaccination → registration. Исключение в источнике, стоящем раньше по
   этому порядку, гарантированно предотвращает вызов всех последующих в этом
   же проходе `load()` — они физически не выполняются, а не «выполняются, но
   их результат отбрасывается».
7. Локальная переменная `groups`, в которую уже могли попасть группы от
   источников, отработавших **до** упавшего (например disposal и movement
   успели, weighing упал), нигде не сохраняется и не эмитится — она просто
   выходит из области видимости вместе с прерванным вызовом `load()`. Поле
   `_allGroups` (которое читает `setFilter`) не обновляется — остаётся тем,
   что было установлено предыдущим успешным `load()`, если он был, либо
   пустым списком по умолчанию.
8. `AnimalHistoryPage`/`_AnimalHistoryView.build` (`BlocBuilder`) реагирует на
   `AnimalHistoryState.error(msg)` веткой `error: (msg) => Center(child:
   ProgressMessage.somethingWentWrong(message: msg))` — сообщение `msg`
   (либо `'Animal not found'`, либо `e.toString()`) выводится пользователю
   как есть, тоже без прогона через `AppLocalizations`/`context.tr`. Виджет
   `ProgressMessage` — картинка + `Text(message)`, без кнопки повтора.

### Альтернативные потоки

- **Регистрация (`_buildRegistrationGroups`) сама по себе никогда не бросает.**
  Это синхронная функция над уже полученными данными (`animal.createdAt` и
  `transponder`, вычисленные сразу после успешного чтения животного) — у неё
  нет собственного репозиторного вызова. Тем не менее при исключении в любом
  из четырёх предыдущих источников она тоже не выполняется — единственная
  причина в порядке кода (шаг 5 списка выше), не в том, что сама регистрация
  чем-то рискует.
- **`_buildDisposalGroups` — два репозиторных вызова, оба могут стать
  причиной той же ошибки.** `DisposalRepository.getAllByAnimalId` вызывается
  всегда; `DisposalReasonsRepository.getAllByFilters` — только если список
  выбытий непуст. Исключение в любом из двух даёт идентичный внешний эффект
  (переход в `catch`, `error(e.toString())`) — сценарий не различает, какая
  именно из двух зависимостей внутри одного логического источника упала.
- **Ошибка на разных из четырёх источников даёт идентичный результат**, но
  разное число уже вызванных перед этим репозиториев: упавший `disposal`
  (первый по порядку) означает, что movement/weighing/vaccination вообще не
  вызывались; упавшая `vaccination` (четвёртая по порядку) означает, что
  disposal/movement/weighing к этому моменту уже успешно отработали и вернули
  свои группы — но даже в этом случае финальный результат для пользователя
  одинаков: `AnimalHistoryState.error(...)`, без единой видимой группы.
- **Сравнение с `AnimalWeighingsCubit.load`
  ([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)).** Там метод
  вообще не обёрнут в `try/catch` — исключение отклоняет `Future`
  необработанным, а состояние кубита зависает на `loading` навсегда, без
  видимого сообщения. Здесь, наоборот, `try/catch` есть и гарантированно
  приводит к видимому `AnimalHistoryState.error(...)` — `Future`, возвращаемый
  `load()`, всегда успешно резолвится (`completes`), независимо от исхода.
- **Повторная попытка не предусмотрена экраном.** `ProgressMessage.
  somethingWentWrong` не содержит кнопки повтора; единственный способ
  повторить `load()` — покинуть вкладку «История» и открыть её заново с
  карточки животного, что пересоздаст `BlocProvider`/`AnimalHistoryCubit` и
  вызовет `load(animalId)` заново с нуля.
- **`setFilter` после ошибки — no-op.** Если состояние кубита `AnimalHistoryError`
  (не `AnimalHistoryLoaded`), `setFilter` ничего не делает — проверка `if
  (current is AnimalHistoryLoaded)` не проходит, `emit` не вызывается; UI
  фильтров на экране ошибки и не отображается (см. `_AnimalHistoryView.build`
  — ветка `error` не строит `_AnimalHistoryBody` с фильтрами).

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность из
  сегмента id; читается первой (`getAnimalWithDetailsById`), её отсутствие —
  ветка (a).
- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — первый по
  порядку из четырёх асинхронных источников ленты; исключение здесь
  блокирует все три последующих.
- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — второй по
  порядку источник.
- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  третий по порядку источник.
- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  четвёртый, последний асинхронный источник; `VaccinationsRepository.
  getVaccinationsWithDetails()` читает вакцинации **всех** животных фермы и
  фильтрует по `animalId` уже в памяти кубита — падение здесь одинаково
  обрывает всю ленту для одного животного, даже если причина сбоя никак не
  связана с этим конкретным животным.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — не читается отдельным репозиторным вызовом в этом
  сценарии: транспондер берётся из `animal.activeAnimalIdentifications`,
  уже присутствующих в объекте, полученном на шаге 1 `getAnimalWithDetailsById`
  — падение здесь невозможно отдельно от падения самого чтения животного.

### Бизнес-правила

- **Нет частичного успеха.** Если хотя бы один из четырёх асинхронных
  источников падает, из пяти возможных групп ленты не показывается ни одна —
  включая те, что успели отработать до сбоя, и регистрацию, которая вообще не
  зависит от упавшего источника.
- **Два структурно разных пути к одному и тому же результату.** «Животное не
  найдено» — это ветка нормального выполнения (`if`/`return`), не исключение;
  «исключение в источнике» — это ветка `catch`. Оба заканчиваются одним и тем
  же вариантом `AnimalHistoryState.error(String message)`, различающимся
  только текстом `message`.
- **Текст ошибки для пользователя не унифицирован и не локализован.** Ветка
  (a) — захардкоженная английская строка `'Animal not found'`; ветка (b) —
  сырой `e.toString()` (текст конкретного класса исключения Dart, например
  `Exception: db error`). Ни один из двух вариантов не проходит через
  `AppLocalizations`/`context.tr`, оба показываются пользователю дословно.
- **Ошибка не логируется.** В отличие от некоторых других read-сценариев
  модуля (например `AnimalVaccinationsCubit.load`, см.
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)), здесь `catch`
  не вызывает `Talker` или любой другой логгер — исключение целиком
  превращается в текст на экране и нигде больше не фиксируется.
- **`load()` гарантированно завершается без проброса исключения наружу.**
  И ветка (a), и ветка (b) заканчиваются `emit`, а не `throw`/необработанным
  отклонением `Future` — вызывающий код (`BlocProvider.create`) никогда не
  видит непойманное исключение из этого метода.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — оба пути к `READ_ERROR` (явная проверка на `null` и `try/catch`
вокруг последовательности из четырёх источников) прослеживаются по
существующему коду `AnimalHistoryCubit.load` полностью, без пробелов,
требующих уточнения у пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_AnimalCardToolbarAction` (пункт «История», `onTap`) | CURRENT | точка входа — `context.pushNamed2(Routes.animalHistory, extra: AnimalHistoryPageArgs(animal: animalWithDetails))` |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryPageArgs` | CURRENT | аргументы страницы — уже загруженное `AnimalWithDetails` с карточки |
| `lib/pages/animal_history/presentation/animal_history_page.dart` | `AnimalHistoryPage.build` | CURRENT | `BlocProvider(create: (context) => AnimalHistoryCubit()..load(args.animal.animalId))` |
| `lib/pages/animal_history/presentation/animal_history_page.dart` | `_AnimalHistoryViewState.build` (`BlocBuilder`, ветка `error`) | CURRENT | рендерит `ProgressMessage.somethingWentWrong(message: msg)` для `AnimalHistoryState.error`; ветка фильтров/списка не строится |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.somethingWentWrong` | CURRENT | картинка + `Text(message)`, без кнопки повтора |
| `lib/pages/animal_history/cubit/animal_history_cubit.dart` | `AnimalHistoryCubit.load` | CURRENT | ядро сценария — проверка `animal == null` (ветка a) и единственный `try/catch` вокруг всех пяти источников (ветка b) |
| `lib/pages/animal_history/cubit/animal_history_state.dart` | `AnimalHistoryState.error` | CURRENT | freezed-вариант, используемый обеими ветками (a) и (b) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | первый вызов `load()`; `null` → ветка (a) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | возвращает `null`, если по `ids: [id]` ничего не найдено |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getAllByAnimalId` | CURRENT | первый по порядку асинхронный источник ленты (`_buildDisposalGroups`) |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalDao.getAllByAnimalId` | CURRENT | Drift-запрос, к которому приводит исключение из мока в тесте |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getAllByFilters` | CURRENT | второй вызов внутри `_buildDisposalGroups`, только если список выбытий непуст |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | второй по порядку асинхронный источник (`_buildMovementGroups`) |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.getAllMovementsWithDetailsByFilters` | CURRENT | Drift-запрос за перемещениями |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | третий по порядку асинхронный источник (`_buildWeighingGroups`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetails` | CURRENT | четвёртый, последний асинхронный источник (`_buildVaccinationGroups`); читает вакцинации всех животных, фильтрует по `animalId` в памяти |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetails` | CURRENT | Drift-запрос, к которому приводит исключение из мока в тесте «ошибка в источнике вакцинаций» |

## Критерии приёмки

- Если `AnimalsRepository.getAnimalWithDetailsById(animalId)` возвращает
  `null`, `AnimalHistoryCubit.load(animalId)` эмитит ровно одно новое
  состояние после `loading()` — `AnimalHistoryState.error('Animal not found')`
  — и не вызывает ни один из пяти источников (disposal/movement/weighing/
  vaccination/registration).
- Если любой из четырёх асинхронных источников (`DisposalRepository.
  getAllByAnimalId`/`DisposalReasonsRepository.getAllByFilters`,
  `MovementReportRepository.getMovementsWithDetailsByFilters`,
  `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
  `VaccinationsRepository.getVaccinationsWithDetails`) бросает исключение,
  `load(animalId)` эмитит `AnimalHistoryState.error(e.toString())`, и
  `Future`, возвращаемый `load()`, успешно резолвится (`completes`, а не
  `throwsA`).
- Источники, идущие по порядку кода **после** упавшего, не вызываются в этом
  проходе `load()` — не только их результат отсутствует в финальном
  состоянии, а сам вызов не происходит.
- Состояние кубита после любой из двух веток — `AnimalHistoryError`, никогда
  `AnimalHistoryLoaded` с пустым или частичным списком групп.
- `_allGroups` не обновляется этим неудачным проходом `load()` — `setFilter`,
  вызванный после ошибки, остаётся no-op (текущее состояние — не
  `AnimalHistoryLoaded`).
- Ни один вызов `Talker` (или другого логгера) не происходит в `catch`-блоке
  ветки (b).

## Связанные тесты

`test/pages/animal_history_cubit_test.dart`, `group('AnimalHistoryCubit.load')`
(описательное имя группы, без номера `UC-` — не переименовывать):

- `test('животное не найдено -> error', ...)` — мокает
  `getAnimalWithDetailsById(1)` на `null`, ожидает `error('Animal not found')`.
- `test('ошибка одного из источников -> error целиком (нет частичного результата)', ...)`
  — мокает `disposalRepository.getAllByAnimalId(any())` на
  `thenThrow(Exception('db error'))` (первый по порядку источник), ожидает
  `error`, содержащий `'db error'`.
- `test('ошибка в источнике вакцинаций -> тоже error целиком', ...)` — мокает
  `vaccinationsRepository.getVaccinationsWithDetails()` на
  `thenThrow(Exception('vacc error'))` (четвёртый, последний асинхронный
  источник — disposal/movement/weighing к этому моменту в тесте уже отвечают
  пустыми списками по умолчанию из `setUp`), ожидает `error`, содержащий
  `'vacc error'`.

Ни один из трёх тестов не проверяет явно (`verifyNever`), что источники,
идущие в коде после упавшего, действительно не были вызваны — вывод об этом
сделан по чтению `load()` (последовательные `await`, не `Future.wait`), а не
по assert'у в тесте. Отдельного теста на исключение именно в
`MovementReportRepository`/`AnimalWeighingsRepository`, а также на исключение
в `DisposalReasonsRepository.getAllByFilters` (второй вызов внутри
`_buildDisposalGroups`, а не первый) — нет.

## Открытые вопросы и ограничения

- **Нет теста, проверяющего невызов последующих источников явно.** Три
  существующих теста подтверждают только итоговое состояние (`error`,
  текст сообщения), не то, что `movementReportRepository`/
  `weighingsRepository`/`vaccinationsRepository` (для теста с падением на
  disposal) или `disposalRepository` (для теста с падением на vaccination,
  где он, по коду, обязан быть вызван и успешно отработать) реально были
  вызваны нужное число раз — заявление «остальные не вызываются вовсе»
  проверено этим документом по чтению кода `load()`, но не закреплено
  `verify`/`verifyNever` в тесте.
- **Ошибка не локализована и не унифицирована по тексту.** `'Animal not
  found'` — захардкоженная английская строка; `e.toString()` — сырой текст
  Dart-исключения. Оба показываются пользователю дословно через
  `ProgressMessage.somethingWentWrong`, без прогона через `AppLocalizations`.
  Не решено этим документирующим файлом, стоит ли это менять — вопрос
  пользователю, если поведение должно измениться в `TARGET`.
- **Ошибка ветки (b) нигде не логируется** (нет вызова `Talker` в `catch`) —
  в проде такой сбой виден только самому пользователю на экране, у команды
  нет диагностического следа без дополнительных средств (например
  централизованного мониторинга исключений, если он есть на другом уровне
  приложения — не проверено в рамках этого use-case).
- **Нет кнопки повтора на экране ошибки.** Единственный способ повторить
  `load()` — выйти со вкладки «История» и открыть её заново; сам факт того,
  удаётся ли повтор при действительно временном сбое (например кратковременная
  блокировка БД), не проверен ни одним тестом.
- Сценарий отражает исключительно `AnimalHistoryCubit.load` (кросс-областная
  лента «История» карточки животного, [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md));
  успешный путь того же метода — отдельный use-case (`READ_OK`, не этот
  файл).
