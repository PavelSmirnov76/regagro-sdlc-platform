# UC-55 — Перемещение животных отказывает технически: диалог подтверждения уже показал пользователю анимацию успеха до того, как `on<AnimalMovementEventSave>` вообще успел выполниться

## Назначение

Документирует `ERROR`-исход [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md)
(`movement.recorded`): пользователь подтверждает перемещение одного или
нескольких животных, но обработчик `AnimalMovementBloc.on<AnimalMovementEventSave>`
(`lib/pages/animal_movement/animal_movement_bloc.dart`) ловит исключение в
единственном `try/catch` — техническая ошибка (Drift/Hive-доступ), не
бизнес-отказ.

Помимо самого `try/catch`, этот сценарий фиксирует структурное свойство UI,
не зависящее от конкретной точки сбоя: диалог подтверждения
(`ConfirmSaveMovementDialog`) переключается в состояние «успех» сразу после
того, как `bloc.add(AnimalMovementEventSave())` синхронно поставил событие в
очередь — не дожидаясь, пока обработчик реально завершит (успешно или с
ошибкой) сохранение. Это верно для любой причины `ERROR`, документируемой
здесь, поэтому описывается один раз в основном потоке, а не повторяется в
каждой альтернативной ветке.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково; `on<AnimalMovementEventSave>`
не делает проверки `isAuthorized()`, `_authRepository.getUser()` используется
только для заполнения `Movement.userId` (`?? -1` при отсутствии пользователя).

## CURRENT

### Основной поток

1. Пользователь доходит до диалога `ConfirmSaveMovementDialog`
   (`lib/pages/animal_movement/animal_movement_page.dart`) одним из двух
   путей: для одиночного животного (`arguments.isSingle`) — сразу после
   выбора места назначения на шаге `AnimalMovementStep.selectMoveToPlace`;
   для группы — после выбора места назначения и последующего выбора
   животных на шаге `AnimalMovementStep.animals`, по нажатию «Далее»
   (`AnimalsStepPage.onNext`). Оба места вызова передают в диалог идентичные
   колбэки `onSave`/`onExit`.
2. Пользователь нажимает «Подтвердить» — `BlackCircleButton(onTap:
   saveMovement)`. `_ConfirmSaveMovementDialogState.saveMovement()`:
   ```dart
   void saveMovement() async {
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
   `widget.onSave` в обоих местах вызова определён как `() async {
   bloc.add(AnimalMovementEventSave()); }` — тело лямбды не содержит ни
   одного `await`, поэтому `bloc.add(...)` (синхронная постановка события в
   очередь `Bloc`) — единственное, что происходит перед тем, как `Future`
   этой лямбды завершается. `await widget.onSave()` в `saveMovement()`
   резолвится сразу после этого, а не после того, как
   `on<AnimalMovementEventSave>` реально отработает.
3. `setState(() { isSaving = false; isSaved = true; })` выполняется
   практически сразу — `AnimatedSwitcher` переключает тело диалога на
   `_successSaveWidget`: заголовок `animals_moved`, Lottie-анимация успеха
   (`Assets.imSuccessAnimation`) и кнопка «Готово» (`ready`,
   `onTap: widget.onExit`). Поле `isSaving` нигде не читается в `build()` —
   индикатор загрузки внутри диалога фактически никогда не показывается,
   несмотря на то что состояние для него заведено.
4. Независимо от диалога, в `AnimalMovementBloc.on<AnimalMovementEventSave>`
   начинает выполняться реальная работа: сначала
   `emit(AnimalMovementSuccess(_data, isLoading: true, loadingMessage:
   'saving_data'))` — это меняет состояние страницы перемещения под
   диалогом, самого диалога не касается.
5. Внутри `try`: `_animalsRepository.getAllByFilters(ids:
   _data.selectedAnimalIds)` заново выбирает животных из локальной БД
   (`AnimalsDao.getAllByFilters`, дефолтный фильтр `isNotDeleted: true`);
   `_authRepository.getUser()?.id ?? -1` читает пользователя из Hive
   (`AuthRepository.getUser`). Для каждого животного собирается `Movement`
   (`animalId`, `placeId: _data.toPlace!.place.idRemote!`, `fromId:
   _data.fromPlace?.place.idRemote`, `sync: false`, `guid`, `userId`) — пока
   только в памяти, без обращения к БД. Затем вызывается
   `_movementReportRepository.saveMovements(movements)`.
6. **Точка технического сбоя (этот сценарий).** Любое исключение,
   брошенное синхронно или асинхронно кодом Drift/DAO/Hive внутри этого
   `try` — на `getAllByFilters` (именно эта точка замоделирована
   существующим тестом, см. «Связанные тесты»), на `getUser()` либо внутри
   `saveMovements(...)` — перехватывается одним и тем же блоком:
   ```dart
   } catch (e) {
     emit(AnimalMovementMessage('an_error_data'));
     getIt<Talker>().handle(e);
   }
   emit(AnimalMovementSuccess(_data));
   ```
   `catch (e)` — без `st`: стек-трейс не захватывается вовсе, в отличие,
   например, от `catch (e, st)` в `AnimalRegistrationBloc`
   ([UC-45](UC-45-ACTOR-5-EVT-22-ENT-11-CREATE_ERROR-IN-ANIMAL.md)).
   `getIt<Talker>().handle(e)` вызывается без `stackTrace`/`msg` —
   `Talker.handle(exception, [stackTrace, msg])` получает только
   исключение. Обработчик эмитит `AnimalMovementMessage('an_error_data')`,
   логирует и безусловно эмитит ещё раз `AnimalMovementSuccess(_data)` — с
   `isLoading` обратно в значении по умолчанию `false`; сам `_data` в этом
   обработчике никогда не переприсваивается, поэтому это тот же объект, что
   был до попытки сохранения.
7. На `animal_movement_page.dart` `BlocConsumer<AnimalMovementBloc,
   AnimalMovementState>` без `listenWhen` (слушатель отрабатывает на каждое
   эмитированное состояние) реагирует на `AnimalMovementMessage`:
   ```dart
   ScaffoldMessenger.of(context).showSnackBar(
     SnackBar(content: Text(AppLocalizations.of(context)!.tr(state.message))),
   );
   ```
   Это обычный `SnackBar`, не хелпер `showAppSnackBarError` из
   `lib/widgets/app_snackbar.dart`. `'an_error_data'` — реальный ключ
   `.arb` (`lib/l10n/app_ru.arb` и другие локали), `AppLocalizations.tr`
   (`lib/l10n/app_localization.dart`, `case 'an_error_data': return
   an_error_data;`) резолвит его в переведённую строку — в отличие от
   хардкод-строки в [UC-45](UC-45-ACTOR-5-EVT-22-ENT-11-CREATE_ERROR-IN-ANIMAL.md),
   здесь перевод настоящий. Снэкбар всплывает на странице перемещения, под
   уже открытым (или к этому моменту уже закрытым пользователем) диалогом
   подтверждения.
8. **Диалог подтверждения так и не узнаёт об ошибке.** Так как на шаге 2
   `await widget.onSave()` уже завершился и `isSaved` уже стал `true` ещё до
   того, как шаг 6 вообще начал выполняться, диалог остаётся на
   `_successSaveWidget` независимо от исхода реальной попытки сохранения.
   Если пользователь нажимает «Готово» (`ready`) — а UI приглашает его
   сделать именно это, так как уже сообщил об успехе — выполняется
   `widget.onExit`:
   ```dart
   onExit: () {
     Navigator.of(context).pop();
     bloc.add(AnimalMovementEventExit());
   },
   ```
   Диалог закрывается, `on<AnimalMovementEventExit>` эмитит
   `AnimalMovementExit()`, слушатель страницы вызывает `context.pop()` —
   вся страница перемещения закрывается. Пользователь покидает сценарий,
   считая перемещение успешным (в лучшем случае мельком увидев снэкбар,
   не обязательно связав его с уже закрывшимся диалогом успеха), хотя ни
   одна строка `Movement` могла не создаться и `Animal.placeId` ни одного
   животного могло не обновиться.

### Альтернативные потоки

- **Частичная запись в БД при сбое внутри самого `saveMovements`.**
  ```dart
  Future<void> saveMovements(List<Movement> movements) async {
    await dao.insAll(movements);
    for (final movement in movements) {
      final animalId = movement.animalId;
      final placeId = movement.placeId;
      if (animalId == null || placeId == null) continue;

      await _animalsRepository.updateAnimalPlaceId(animalId, placeId);
    }
  }
  ```
  `dao.insAll` (`BaseDao.insAll`) выполняет `batch((batch) =>
  batch.insertAll(...))` — единый атомарный батч: все строки `Movement`
  коммитятся разом, до начала цикла. После этого цикл по
  `_animalsRepository.updateAnimalPlaceId(animalId, placeId)`
  (`AnimalsRepository.updateAnimalPlaceId` → `AnimalsDao.getById` +
  `AnimalsDao.upd`) выполняется по одной записи, **без** общей транзакции.
  Если исключение бросается на N-м животном цикла, у животных `1..N-1`
  `placeId` уже обновлён, у N-го и всех последующих — нет, но строки
  `Movement` для них всех уже сохранены благодаря более раннему `insAll`.
  Обработчик `on<AnimalMovementEventSave>` ловит это исключение точно так
  же, как и любое другое в этом `try` — тем же `AnimalMovementMessage
  ('an_error_data')`, без какого-либо указания пользователю на то, что
  операция применилась частично.
- **`null` `animalId`/`placeId` в `Movement` не считается ошибкой.** Обе
  колонки объявлены допускающими `null` в схеме
  (`packages/sheep_farm_database/lib/entities/movement/movement.dart`:
  `IntColumn get animalId => integer().nullable()();`, аналогично
  `placeId`), хотя сами значения при формировании `Movement` в шаге 5
  основного потока всегда заполнены. Guard `if (animalId == null ||
  placeId == null) continue;` внутри `saveMovements` просто пропускает
  обновление `Animal.placeId` для такой записи без исключения — то есть
  этот сценарий (`ERROR`) им не затрагивается вовсе, только оставляет
  «немую» строку `Movement`, чей связанный `Animal.placeId` не обновился.
- **Групповой поток после сбоя.** Финальный `emit(AnimalMovementSuccess
  (_data))` после `catch` несёт тот же `_data.selectedAnimalIds`/`toPlace`,
  что и до попытки — то есть теоретически позволяет повторить попытку с тем
  же выбором, не проходя визард заново. На практике этот путь недостижим в
  текущем UI: единственный способ вызвать `AnimalMovementEventSave` —
  диалог подтверждения, а он всегда приводит к описанному выше
  «success»-экрану (шаг 8), после которого пользователь либо закрывает
  диалог кнопкой «Готово» (и тем самым выходит со всей страницы), либо
  закрывает сам `CustomDialog` (`onClose: () => isSaved ?
  widget.onExit() : Navigator.of(context).pop()`) — при `isSaved == true`
  это тоже `widget.onExit()`, то есть тот же выход со страницы. Ни один
  путь закрытия диалога после нажатия «Подтвердить» не возвращает
  пользователя к возможности повторить попытку на той же странице.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — целевая
  сущность попытки создания. В основном потоке (сбой на `getAllByFilters`
  или `getUser()`, до вызова `saveMovements`) ни одна строка `Movement` не
  создаётся вовсе. В альтернативном потоке (сбой внутри `saveMovements`,
  после `insAll`) строки `Movement` уже закоммичены атомарным батчем —
  единственное, что могло не завершиться, это последующее обновление
  `Animal.placeId`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — `placeId`
  обновляется по одному животному за раз внутри цикла `saveMovements`, вне
  всякой транзакции с `insAll` записей `Movement`; в основном потоке этого
  сценария цикл не запускается вовсе (исключение происходит раньше), в
  альтернативном — может выполниться частично.

### Бизнес-правила

- Технический сбой (исключение из Drift/DAO/Hive) классифицируется как
  `CREATE_ERROR`, а не `CREATE_REJECTED` — до бизнес-валидации (выбор
  животных/мест) дело в этом сценарии не доходит, ошибка возникает на
  уровне хранения.
- Один и тот же `catch (e)` в `on<AnimalMovementEventSave>` покрывает три
  независимых по происхождению точки сбоя (`getAllByFilters`, `getUser`,
  `saveMovements`) и реагирует на все три одинаково — `AnimalMovementMessage
  ('an_error_data')` плюс безусловный повторный `AnimalMovementSuccess
  (_data)`; отличить в UI, какая именно из трёх операций отказала, по
  тексту сообщения невозможно.
- Переключение диалога подтверждения в состояние «успех» **не зависит от
  результата** `on<AnimalMovementEventSave>` — оно управляется исключительно
  тем, что `bloc.add(...)` (постановка события в очередь) — синхронная
  операция, завершающаяся раньше, чем сам обработчик. Это верно для любого
  исхода `AnimalMovementEventSave`, не только для сбоя, но именно для
  `ERROR`-исхода это расхождение наиболее заметно: пользователь получает
  визуальное подтверждение успеха до того, как операция вообще завершилась
  (успешно или нет).
- `_movementReportRepository.saveMovements` не является одной атомарной
  операцией: вставка строк `Movement` (`dao.insAll`, единый батч) и
  обновление `Animal.placeId` для каждого животного (`updateAnimalPlaceId`,
  без общей транзакции с `insAll` и без транзакции между собой в цикле) —
  два независимых шага, поэтому технический сбой между ними оставляет
  БД в промежуточном состоянии, а обработчик bloc'а не различает это от
  сбоя, при котором вообще ничего не записалось.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных пути прослеживаются чтением
`lib/pages/animal_movement/animal_movement_bloc.dart`,
`lib/pages/animal_movement/animal_movement_page.dart`,
`lib/repositories/animal/animals_repository.dart`,
`lib/repositories/movement_report/movement_report_repository.dart`,
`packages/sheep_farm_database/lib/entities/base_dao.dart`,
`packages/sheep_farm_database/lib/entities/movement/movement.dart` и
`lib/l10n/app_localization.dart`. Отсутствие `await` внутри лямбды `onSave`
(и, как следствие, независимость перехода диалога в «успех» от реального
исхода `on<AnimalMovementEventSave>`) перепроверено чтением обоих мест
вызова `ConfirmSaveMovementDialog` в `animal_movement_page.dart`, а не
восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventSave>` | CURRENT | единственный `try/catch` на три источника исключения; эмитит `AnimalMovementMessage('an_error_data')`, логирует через `Talker.handle(e)` без стек-трейса, затем безусловно `AnimalMovementSuccess(_data)` |
| `lib/pages/animal_movement/animal_movement_event.dart` | `AnimalMovementEventSave` | CURRENT | событие, запускающее сохранение |
| `lib/pages/animal_movement/animal_movement_state.dart` | `AnimalMovementMessage`, `AnimalMovementSuccess` | CURRENT | состояния, участвующие в сценарии ошибки |
| `lib/pages/animal_movement/animal_movement_page.dart` | `ConfirmSaveMovementDialog`, `_ConfirmSaveMovementDialogState.saveMovement`, оба места вызова `showDialog(... ConfirmSaveMovementDialog(onSave: () async { bloc.add(AnimalMovementEventSave()); }, ...))` | CURRENT | диалог подтверждения переходит в `_successSaveWidget` сразу после постановки события в очередь, независимо от исхода обработчика |
| `lib/pages/animal_movement/animal_movement_page.dart` | `BlocConsumer<AnimalMovementBloc, AnimalMovementState>.listener` | CURRENT | показывает `SnackBar` (не `showAppSnackBarError`) по `AnimalMovementMessage`; вызывается на каждое состояние — `listenWhen` не задан |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllByFilters`, `AnimalsRepository.updateAnimalPlaceId` | CURRENT | `getAllByFilters` — протестированная точка сбоя (повторная выборка выбранных животных); `updateAnimalPlaceId` — источник исключения в альтернативном (частичном) потоке |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser` | CURRENT | чтение пользователя из Hive для `Movement.userId`; альтернативная (менее вероятная) точка сбоя того же `try` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.saveMovements` | CURRENT | `dao.insAll(movements)` (атомарный батч) с последующим нетранзакционным циклом `updateAnimalPlaceId` — источник частичного технического сбоя |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll` | CURRENT | `batch((batch) => batch.insertAll(...))` — атомарная вставка всех переданных `Movement` разом |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `Movements` (`animalId`, `placeId` — `IntColumn.nullable()`) | CURRENT | схема, допускающая `null` в обеих колонках — источник guard'а в `saveMovements` |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` | CURRENT | резолвит `'an_error_data'` в переведённую строку (реальный ключ `.arb`, не хардкод) |
| `lib/l10n/app_ru.arb` | `an_error_data` | CURRENT | перевод ключа для текущей локали по умолчанию |

## Критерии приёмки

- При исключении из `_animalsRepository.getAllByFilters(...)` внутри
  `on<AnimalMovementEventSave>` bloc эмитит `AnimalMovementMessage
  ('an_error_data')`, затем `AnimalMovementSuccess` — без промежуточных
  состояний между ними, кроме уже эмитированного в начале обработчика
  `AnimalMovementSuccess(_data, isLoading: true, loadingMessage:
  'saving_data')`.
- То же самое эмитируется при исключении из `_authRepository.getUser()`
  или из `_movementReportRepository.saveMovements(...)` — один и тот же
  `catch` без ветвления по источнику.
- `getIt<Talker>().handle(e)` вызывается ровно один раз на пойманное
  исключение, без стек-трейса (`catch (e)`, не `catch (e, st)`).
- Диалог подтверждения (`ConfirmSaveMovementDialog`) переходит в
  `_successSaveWidget` сразу после `bloc.add(AnimalMovementEventSave())`,
  независимо от того, каким состоянием впоследствии завершится
  `on<AnimalMovementEventSave>` — успехом или `AnimalMovementMessage
  ('an_error_data')`.
- Если сбой происходит после того, как `dao.insAll(movements)` внутри
  `saveMovements` уже выполнился, строки `Movement` остаются
  закоммиченными в БД, даже если последующий цикл обновления
  `Animal.placeId` завершился с исключением на одном из животных.

## Связанные тесты

- `test/pages/animal_movement_bloc_test.dart`, group `'UC-55 — AnimalMovementEventSave'`, test `'ошибка сохранения ->
  AnimalMovementMessage("an_error_data"), корректная обработка'` — прямое
  покрытие точки сбоя `getAllByFilters`: `animalsRepository.getAllByFilters
  (ids: any(named: 'ids'))` замокан на `thenThrow(Exception('db error'))`,
  ожидается, что поток состояний бло­ка содержит
  `AnimalMovementMessage` со значением `'an_error_data'`.
- Соседняя group `'UC-54 — AnimalMovementEventSave'` в том же файле
  покрывает `CREATE_OK`-исход того же обработчика (успешное сохранение),
  не документируемый здесь.
- **TBD — теста нет** на сбой в `_authRepository.getUser()` — тот же
  `catch`, но отдельно не проверен.
- **TBD — теста нет** на сбой внутри самого `saveMovements` (после
  `dao.insAll`, но до/во время цикла `updateAnimalPlaceId`) — альтернативный
  поток с частичной записью в БД никаким тестом не покрыт.
- **TBD — теста нет** на поведение самого диалога
  `ConfirmSaveMovementDialog`/`_ConfirmSaveMovementDialogState.saveMovement`
  — ни успешный, ни ошибочный переход в `_successSaveWidget` не проверяется
  ни одним widget-тестом; вывод об «оптимистичном» UI сделан по чтению
  кода, не по прогону теста.

## Открытые вопросы и ограничения

- **Оптимистичный переход диалога в «успех» — намеренное решение или
  недосмотр?** Ничего в коде/комментариях не фиксирует, был ли выбор
  `Future<void> Function() onSave` без ожидания реального результата
  бло­ка осознанным (например: «локальное сохранение достаточно быстрое,
  реальная обратная связь важна только для последующей синхронизации») или
  случайным следствием того, что `onSave` вызывает `bloc.add(...)`, а не
  дожидается соответствующего состояния из `bloc.stream`.
- **`isSaving` в `_ConfirmSaveMovementDialogState` — мёртвое состояние.**
  Поле выставляется в `true`/`false`, но нигде не читается в `build()` —
  индикатор загрузки внутри диалога не рендерится никогда. Неясно, это
  задел на будущий UI, который не успели подключить, или забытый остаток
  более раннего варианта экрана.
- **Частичный технический сбой в `saveMovements` (строки `Movement`
  сохранены, `Animal.placeId` обновлён не для всех) не имеет ни
  автоматического покрытия, ни механизма сверки/отката.** Не
  зафиксировано, считается ли это приемлемым редким крайним случаем или
  нерассмотренным пробелом.
- **Расхождение с описанием полей в [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md).**
  Там `animalId`/`placeId` описаны как `int` (не nullable), но фактическая
  Drift-колонка (`packages/sheep_farm_database/lib/entities/movement/movement.dart`)
  объявлена `.nullable()`, и код `saveMovements` явно проверяет их на
  `null`. Для этого сценария (`ERROR`) это не меняет вывод — оба поля
  всегда заполнены на шаге 5 основного потока, — но сама возможность
  `null`-значений в схеме нигде не объяснена и не используется намеренно
  где-либо ещё в прочитанном коде.
