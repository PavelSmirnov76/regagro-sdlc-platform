# UC-84 — Сохранение взвешивания отказывает технически: `WeighAnimalCubit.saveWeighing` бросает исключение необработанным, диалог подтверждения зависает

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)
(`animal_weighing.recorded`): пользователь подтверждает сохранение партии
взвешиваний (одно или несколько животных подряд), а
`WeighAnimalCubit.saveWeighing` бросает исключение при попытке
сохранить строку `AnimalWeighing` — техническая ошибка (Drift/БД), не
бизнес-отказ. **В отличие от аналогичных сценариев Vaccination
([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)) и Movement
([UC-55](UC-55-ACTOR-5-EVT-27-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), здесь нет
`try/catch` вокруг цикла сохранения** — исключение пробрасывается наружу
необработанным, подтверждено существующим тестом
(`throwsA(isA<Exception>())`). Пользователь не получает никакого сообщения
об ошибке; диалог подтверждения (`ConfirmSaveWeighDialog`/
`_ConfirmSaveWeighDialogState.saveWeighing`) остаётся в состоянии ожидания —
код, который должен переключить его на экран успеха, до ошибки просто не
доходит.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart`
целиком: `WeighAnimalCubit` не объявляет и не использует `AuthRepository` ни
в одном методе, включая `saveWeighing` — запись `AnimalWeighing`
([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)) вообще не имеет
поля-автора.

## CURRENT

### Основной поток

1. Пользователь взвешивает одно или несколько животных подряд через экран
   `WeighAnimalPage`/`_WeighAnimalWeighingView`. После ввода/фиксации веса
   для очередного животного `_WeighAnimalWeighingViewState.build` предлагает
   либо перейти к следующему животному
   (`onNextAnimalTap` → `cubit.saveCurrentWeighingStayOnPage()`), либо
   завершить визит (`onFinishTap`, доступен через `showFinishButton`). Обе
   ветки при наличии незастейджённого текущего ввода (`hasPendingWeighing`)
   сперва вызывают `cubit.saveCurrentWeighingStayOnPage()` — этот метод
   обёрнут в свой собственный `try/catch` (`_emitError('Ошибка сохранения
   взвешивания')` при сбое) и **не относится к сценарию данного use-case**;
   при успехе он лишь добавляет запись в `state.data.createdAnimalWeighings`
   через `_upsertWeighing`, ничего не пишет в БД.
2. Когда пользователь готов завершить визит (`!isEditMode`, ветка `if
   (hasPendingWeighing) { ... }` в `onFinishTap` уже прошла), открывается
   `showDialog(... ConfirmSaveWeighDialog(data: cubit.state.data, onSave: ()
   async => cubit.saveWeighing(), onExit: ...))`
   (`lib/pages/weigh_animal/pages/weigh_animal_page.dart`, локальная функция
   `onFinishTap` внутри `_WeighAnimalWeighingViewState.build`).
3. Пользователь нажимает «Подтвердить» —
   `_ConfirmSaveWeighDialogState.saveWeighing()`:
   ```dart
   void saveWeighing() async {
     setState(() {
       isSaving = true;
     });
     await widget.onSave();
     setState(() {
       isSaving = false;
       isSaved = true;
     });
   }
   ```
   `isSaving` нигде не читается в `build()` (`isSaved ? _successSaveWidget(context)
   : _confirmSaveWidget(context)`, без ветвления по `isSaving`) — визуально
   в момент нажатия ничего не меняется.
4. `widget.onSave` — `() async => cubit.saveWeighing()`. Вызывается
   `WeighAnimalCubit.saveWeighing()`:
   ```dart
   Future<void> saveWeighing() async {
     for (final item in state.data.createdAnimalWeighings) {
       if (item.animalWeighing.id != -1) {
         await _animalWeighingsRepository.update(...);
       } else {
         await _animalWeighingsRepository.insert(...);
       }
     }
     _pendingParentReload = state.data.createdAnimalWeighings.isNotEmpty;
     emit(WeighAnimalState(data: state.data));
   }
   ```
   Ни в начале, ни где-либо ещё до конца цикла метод не выставляет
   `isLoading`/`error` через `emit` — в отличие от `saveCurrentWeighingStayOnPage`,
   здесь вообще нет промежуточного `emit`.
5. **Точка технического сбоя (этот сценарий).**
   `_animalWeighingsRepository.insert(...)` (для новой записи, `id == -1`)
   либо `.update(...)` (для записи с уже присвоенным `id`, например при
   правке сегодняшнего взвешивания через тот же батч) бросает исключение — в
   тесте `thenThrow(Exception('db error'))`. `saveWeighing()` **не обёрнут в
   `try/catch`** — исключение пробрасывается из метода необработанным:
   возвращаемый им `Future<void>` отклоняется этим же исключением. Ни
   `_pendingParentReload = ...`, ни финальный `emit(WeighAnimalState(data:
   state.data))` не выполняются — состояние cubit'а (`isLoading`, `error`,
   `data`) остаётся точно таким, каким было до вызова `saveWeighing()`.
6. Отклонение распространяется через `onSave: () async => cubit.saveWeighing()`
   (Dart разворачивает вложенный `Future` — исключение из
   `cubit.saveWeighing()` становится исключением, которым отклоняется
   `Future`, возвращённый самим `onSave()`), затем — в `await
   widget.onSave();` на шаге 3. Поскольку `_ConfirmSaveWeighDialogState.saveWeighing`
   объявлен как `void` (не `Future<void>`), а передан в `onTap: saveWeighing`
   (`VoidCallback`, без `await` со стороны вызывающего виджета), результат
   этого вызова никем не ожидается — необработанное исключение становится
   ошибкой в текущей Dart Zone, а не отклонённым `Future`, который кто-то мог
   бы поймать. `lib/main.dart` вызывает `runApp(const MyApp())` напрямую —
   вызов `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const
   MyApp()), (error, stack) { getIt<Talker>().handle(error, stack); });`
   закомментирован целиком. Приложение не оборачивает своё выполнение в
   `runZonedGuarded` с собственным обработчиком — это исключение не попадает
   ни в `Talker`, ни в какой-либо другой явный error-handler приложения.
7. Строки после `await widget.onSave();` на шаге 3 —
   `setState(() { isSaving = false; isSaved = true; });` — не выполняются.
   `isSaved` остаётся `false`, `build()` продолжает рендерить
   `_confirmSaveWidget` — тот же экран, что и до нажатия «Подтвердить».
   Кнопка «Подтвердить» (`onTap: saveWeighing`) по-прежнему доступна
   повторному нажатию — ничто в `build()` не блокирует её по `isSaving`.
   Пользователь не получает никакого сообщения об ошибке: ни
   `WeighAnimalCubit._emitError` (не вызывается нигде внутри `saveWeighing`),
   ни `ScaffoldMessenger`/`showAppSnackBarError` не срабатывают на этом
   пути — с точки зрения пользователя экран просто «зависает» на диалоге
   подтверждения без какой-либо обратной связи.

### Альтернативные потоки

- **Частичная запись без общей транзакции.** Цикл в `saveWeighing()`
  вызывает `insert`/`update` по одной записи `AnimalWeighing` за раз, без
  `transaction()`, охватывающей весь цикл. Если в
  `state.data.createdAnimalWeighings` несколько элементов (несколько
  животных, взвешенных подряд за визит) и исключение брошено на N-й
  итерации, записи `1..N-1` уже закоммичены в БД, `N`-я и все последующие —
  нет. Существующий тест использует ровно один элемент в батче — этот путь
  не покрыт (см. «Связанные тесты»).
- **Ретрай тем же `state.data` рискует задублировать уже вставленные
  записи.** Так как ни один `emit` в `saveWeighing()` не выполняется при
  ошибке, `state.data.createdAnimalWeighings` в cubit'е остаётся тем же
  списком, что и до неудачной попытки — включая элементы с `id == -1`,
  вставка которых уже успела закоммититься до итерации со сбоем (см. пункт
  выше). Кнопка «Подтвердить» диалога остаётся доступной (шаг 7 основного
  потока), и повторное нажатие заново вызовет `cubit.saveWeighing()` с тем
  же списком: для элементов `id == -1` это означает повторный
  `AnimalWeighingsCompanion.insert(...)` без указания `id` — Drift присвоит
  новый autoincrement `id`, создавая дублирующую строку для животного, чья
  запись уже была успешно сохранена в первой попытке. Для элементов с уже
  присвоенным `id != -1` повторный `update(...)` идемпотентен (перезаписывает
  ту же строку) и дублирования не создаёт.
- **Тот же паттерн (без `try/catch`) есть и в `saveEditedWeighing`
  (`WeighAnimalCubit`), но это отдельный, не документируемый здесь
  сценарий.** `saveEditedWeighing` используется другим диалогом
  (`ConfirmEditWeighDialog`/`_ConfirmEditWeighDialogState._save`, ветка
  `isEditMode` в `onFinishTap`) и относится к
  [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md)
  (`UPDATE`), а не к [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)
  (`CREATE`), к которому привязан этот use-case. Упоминается здесь только
  как соседняя точка того же дефекта в той же сущности — см.
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) («Ни один из
  трёх найденных «сохраняющих» методов… не обёрнут в `try/catch`»).

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  целевая сущность попытки создания/правки в рамках батча. В зависимости от
  того, на какой итерации цикла произошёл сбой, ноль, часть или (при сбое на
  самой первой итерации) ни одной строки из `createdAnimalWeighings` не
  остаётся сохранённой сверх того, что уже закоммитилось до сбоя.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только
  читается: `currentData.selectedAnimal!.animalId` (уже выбранное животное,
  из более раннего шага `selectAnimalForWeighing`/`searchByNumber`).
  `saveWeighing()` не перечитывает и не изменяет ни одного `Animal`;
  `AnimalsRepository` в этом методе не используется вовсе.
- `Unit` ([ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md),
  HANDBOOKS) — только читается, как `unitId` уже выбранной на этапе
  стейджинга единицы измерения; `UnitsRepository` в `saveWeighing()` не
  используется.

### Бизнес-правила

- Технический сбой (исключение из `insert`/`update` на уровне Drift/DAO)
  классифицируется как `CREATE_ERROR`, а не `CREATE_REJECTED` — до этой
  точки все guard-условия (животное выбрано, вес > 0, единица выбрана) уже
  прошли на этапе `saveCurrentWeighingStayOnPage`; отказ происходит на
  уровне хранения, не бизнес-валидации.
- **`WeighAnimalCubit.saveWeighing` — единственный из трёх «финальных»
  методов сохранения этого cubit'а (наравне с
  `saveCurrentWeighingStayOnPage`, у которого есть свой `try/catch`, и
  `saveEditedWeighing`, у которого `try/catch` нет вовсе), где исключение из
  цикла сохранения не перехватывается вообще.** Это прямо противоположно
  паттерну `VaccinationBloc.on<VaccinationEventSave>`
  ([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)) и
  `AnimalMovementBloc.on<AnimalMovementEventSave>`
  ([UC-55](UC-55-ACTOR-5-EVT-27-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), которые
  оба ловят исключение и эмитят сообщение пользователю.
- Цикл в `saveWeighing()` не обёрнут в общую транзакцию — сбой в середине
  оставляет БД в промежуточном состоянии (часть записей сохранена, часть —
  нет), а вызывающий код (диалог, а затем и сам пользователь) никак не
  различает этот случай от случая, при котором вообще ничего не
  записалось.
- `WeighAnimalCubit` не читает и не использует авторизацию/пользователя ни в
  одном методе — у `AnimalWeighing` вообще нет поля-автора
  ([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба ключевых альтернативных потока (частичная запись
без транзакции; риск дублирования при ретрае того же `state.data`)
прослеживаются чтением
`lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart`,
`lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_state.dart`,
`lib/pages/weigh_animal/pages/weigh_animal_page.dart`,
`lib/repositories/animal_weighing/animal_weighings_repository.dart`,
`lib/repositories/base_repository.dart`,
`packages/sheep_farm_database/lib/entities/base_dao.dart`,
`packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart`
и `lib/main.dart`. Отсутствие `try/catch` вокруг цикла в `saveWeighing`,
отсутствие `await` со стороны `onTap: saveWeighing` и то, что
`runTalkerZonedGuarded` в `lib/main.dart` закомментирован, перепроверены
чтением исходников напрямую, а не восстановлены по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveWeighing` | CURRENT | цикл сохранения по одной записи за раз, без `try/catch` — единственная точка сбоя данного сценария; при исключении не выполняет ни `_pendingParentReload`, ни финальный `emit` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveCurrentWeighingStayOnPage` | CURRENT | предшествующий шаг стейджинга — обёрнут в собственный `try/catch` (`_emitError('Ошибка сохранения взвешивания')`), не относится к сценарию ошибки данного use-case |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_state.dart` | `WeighAnimalState`, `WeighAnimalData` | CURRENT | `isLoading`/`error` по умолчанию `false`/`null`; ни один из них не выставляется `saveWeighing()` при ошибке |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `_WeighAnimalWeighingViewState.build` (локальная функция `onFinishTap`) | CURRENT | единственный живой путь к открытию `ConfirmSaveWeighDialog` вне режима правки; передаёт `onSave: () async => cubit.saveWeighing()` |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `ConfirmSaveWeighDialog`, `_ConfirmSaveWeighDialogState.saveWeighing` | CURRENT | `void async`-метод без `try/catch`, вызывается как `VoidCallback` (`onTap: saveWeighing`), никем не awaited; необработанное исключение обрывает выполнение до `setState(() { isSaved = true; })` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository` (наследует `BaseRepository.insert`/`update`, своих переопределений нет) | CURRENT | нет собственного `try/catch` вокруг `insert`/`update` |
| `lib/repositories/base_repository.dart` | `BaseRepository.insert`, `BaseRepository.update` | CURRENT | тонкие обёртки — `dao.ins(item)` / `dao.upd(item)`, без `try/catch` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins`, `BaseDao.upd` | CURRENT | непосредственная Drift-вставка/обновление одной строки — точка сбоя, воспроизведённая тестом через мок |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao` | CURRENT | не переопределяет `ins`/`upd` из `BaseDao` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings`, `AnimalWeighingsCompanion` | CURRENT | схема таблицы; строка может остаться несохранённой при сбое или задублированной при ретрае (см. «Альтернативные потоки») |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` вызывается напрямую; вызов `runTalkerZonedGuarded(...)` с обработчиком `getIt<Talker>().handle(error, stack)` закомментирован целиком — необработанные асинхронные исключения не попадают ни в один явный error-handler приложения |

## Критерии приёмки

- При исключении из `_animalWeighingsRepository.insert(...)` или `.update(...)`
  внутри цикла `WeighAnimalCubit.saveWeighing()` метод не перехватывает его —
  возвращаемый `Future<void>` отклоняется тем же исключением
  (`throwsA(isA<Exception>())`).
- Ни `_pendingParentReload`, ни финальный `emit(WeighAnimalState(data:
  state.data))` не выполняются для итерации, на которой брошено исключение,
  и для всех последующих — состояние cubit'а (`isLoading`, `error`, `data`)
  после неудачного вызова идентично состоянию до него.
- Строки `AnimalWeighing`, для которых `insert`/`update` успели выполниться
  до итерации со сбоем, остаются закоммиченными в БД — цикл не обёрнут в
  общую транзакцию.
- В `_ConfirmSaveWeighDialogState.saveWeighing()` код после `await
  widget.onSave()` (`setState(() { isSaving = false; isSaved = true; })`) не
  выполняется — `isSaved` остаётся `false`, диалог продолжает рендерить
  `_confirmSaveWidget`, кнопка «Подтвердить» остаётся доступной повторному
  нажатию.
- Пользователь не получает никакого сообщения об ошибке на этом пути — ни
  `WeighAnimalCubit._emitError`, ни `ScaffoldMessenger`/
  `showAppSnackBarError` не вызываются ни из `saveWeighing()`, ни из
  `_ConfirmSaveWeighDialogState.saveWeighing()`.

## Связанные тесты

- `test/pages/weigh_animal_cubit_test.dart`, group
  `'UC-84 — WeighAnimalCubit.saveWeighing ERROR (известный дефект — без try/catch)'`,
  test `'insert бросает -> исключение пробрасывается наружу необработанным
  (нет try/catch вокруг финального шага)'` — прямое покрытие:
  `animalWeighingsRepository.insert(any())` замокан на
  `thenThrow(Exception('db error'))`, после успешного
  `cubit.saveCurrentWeighingStayOnPage()` (шаг стейджинга, отдельно
  проверяется, что он прошёл) проверяется, что
  `await expectLater(cubit.saveWeighing(), throwsA(isA<Exception>()));` —
  вызов `saveWeighing()` действительно отклоняет `Future` тем же
  исключением. (Групповое имя со старым номером `UC-114` — идентификатор
  будет переименован отдельным проходом; сам тест уже покрывает ровно этот
  сценарий.)
- Соседняя group `'UC-83 — WeighAnimalCubit.saveWeighing (офлайн)'` в том же
  файле покрывает `CREATE_OK`-исход того же метода, не документируемый
  здесь.
- **TBD — теста нет** на частичную запись при нескольких элементах
  `createdAnimalWeighings` (сбой на N-й итерации цикла, `1..N-1` уже
  закоммичены) — существующий тест использует ровно один элемент в батче
  (`buildInitializedCubit` + один `saveCurrentWeighingStayOnPage()`).
- **TBD — теста нет** на сценарий ретрая после ошибки (повторный вызов
  `cubit.saveWeighing()` с тем же `state.data.createdAnimalWeighings` и
  риском дублирования вставленных записей).
- **TBD — теста нет** на сбой в ветке `update(...)` (элемент с `id != -1`)
  внутри того же цикла — существующий тест воспроизводит только ветку
  `insert(...)`.
- **TBD — теста нет** на поведение самого диалога `ConfirmSaveWeighDialog`/
  `_ConfirmSaveWeighDialogState.saveWeighing` — ни успешный, ни ошибочный
  переход в `_successSaveWidget` не проверяется ни одним widget-тестом (в
  `test/` нет файла для `weigh_animal_page.dart`); вывод о зависании диалога
  и об отсутствии обратной связи пользователю сделан по чтению кода, а не по
  запуску реального приложения.

## Открытые вопросы и ограничения

- **Реальное поведение необработанного исключения из `void async`
  `VoidCallback` в запущенном приложении не проверено ни одним
  widget/integration-тестом.** Из чтения `lib/main.dart` (`runApp` без
  `runZonedGuarded`/`runTalkerZonedGuarded`) следует, что оно не попадает ни
  в `Talker`, ни в явный обработчик приложения — но точный наблюдаемый
  эффект (тихо теряется в консоли, показывает framework-овый красный экран
  в debug-сборке, или что-то иное, специфичное для конкретной версии
  Flutter/Dart) не подтверждён запуском самого приложения, только чтением
  кода и семантики Dart Zones. Сформулировано в задаче как «диалог
  зависнет/упадёт» — оба формулировки совместимы с тем, что установлено
  чтением кода (шаг 7 основного потока: код успеха не выполняется).
- **Почему WEIGH, в отличие от VAC/MOVE, не получил `try/catch` вокруг
  финального сохранения?** Ничего в коде/комментариях не объясняет,
  является ли отсутствие `try/catch` в `saveWeighing`/`saveEditedWeighing`
  преднамеренным решением или недосмотром — при том, что третий метод той
  же группы, `saveCurrentWeighingStayOnPage`, `try/catch` имеет.
  Дублирует находку, уже зафиксированную в
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md).
- **Риск дублирования записей при ретрае** (см. «Альтернативные потоки») —
  не подтверждён тестом; вывод сделан по чтению кода `saveWeighing` и
  `_upsertWeighing`/`state.data.createdAnimalWeighings`, где ничего не
  очищается и не помечается как частично сохранённое после неудачной
  попытки.
- **`isSaving` в `_ConfirmSaveWeighDialogState` — мёртвое поле**, не
  читается в `build()`, тот же паттерн, что уже отмечен в
  [UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md) для
  аналогичного диалога вакцинации.
- **Единственный выход из зависшего диалога — закрытие без сохранения.**
  Поскольку `isSaved` остаётся `false`, `CustomDialog.onClose` (крестик)
  вызывает `Navigator.of(context).pop()` без сохранения (ветка `isSaved ?
  widget.onExit() : Navigator.of(context).pop()`), а не `widget.onExit()` —
  пользователь может закрыть диалог, но экран взвешивания не покидается
  (`onExit`/`cubit.exit()` не вызываются), и результат нажатия «Подтвердить»
  так и остаётся неизвестным пользователю без повторной попытки.
