# UC-54 — Перемещение животных между местами завершается успехом

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гость или
авторизованный, одинаково) проходит визард перемещения (`AnimalMovementBloc` /
`AnimalMovementPage`), выбирает место назначения (и, если применимо, место
отправления и список животных) и подтверждает — для каждого выбранного
животного создаётся отдельная запись `Movement` (`sync: false`, локальная, без
обращения к серверу), `Animal.placeId` каждого из них обновляется немедленно,
локально. Happy-path сценарий события
[EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) (`movement.recorded`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения. Перемещение — local-first сценарий: доступно одинаково гостю и
авторизованному пользователю, сохранение не делает ни одного сетевого вызова и
не проверяет состояние сети перед записью; sync — отдельный, явный проход (см.
[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)).

## CURRENT

### Основной поток

1. Визард открывается одним из двух способов входа:
   `AnimalMovementPageArguments.animal(animal:)` — одиночное животное
   (`isSingle == true`), либо `AnimalMovementPageArguments.all(farm:, place:)`
   — групповой вход по ферме, опционально с предустановленным местом
   отправления (`presetFromPlace`). `AnimalMovementBloc` создаётся с этими
   аргументами и сразу получает `AnimalMovementEventStart()`.
2. Обработчик `AnimalMovementEventStart`:
   - резолвит `farm`: из `presetFromPlace` (через
     `FarmRepository.getById(presetFromPlace.farmId)`), иначе из
     `arguments.farm`, иначе из `arguments.animal!.farm!` (одиночный вход);
   - грузит все места фермы с животными
     (`PlaceRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)`);
   - ветка `isSingle`: `selectedAnimalIds = [arguments.animal!.animal.id]`,
     `fromPlace` — место из уже загруженного списка, чей `idRemote` совпадает с
     `arguments.animal!.placeId` (или `null`, если животное «без места»);
   - ветка группы: грузит `getAnimalsWithoutPlaceByFarmId(farm.remoteId!)`;
     если передан `presetFromPlace` — резолвит `fromPlace` из уже загруженного
     списка мест по `idRemote` и сразу подгружает животных этого места
     (`getAllAnimalsWithDetailsByFilters(placeIds: [fromPlace.place.idRemote!])`
     — дефолтный `isNotDeleted: true`) в `_data.animals`, иначе `_data.animals`
     остаётся пустым до явного выбора места отправления.
3. Реально проходимые шаги визарда — `AnimalMovementData.currentSteps`:
   **место отправления** (`AnimalMovementStep.selectMoveFromPlace`, только
   если `!isSingle && presetFromPlace == null`) → **место назначения**
   (`AnimalMovementStep.selectMoveToPlace`, всегда) → **животные**
   (`AnimalMovementStep.animals`, только если `!isSingle`).
4. Шаг «место отправления» (если проходится, `SelectPlaceStepPage`):
   выбор места → `AnimalMovementEventChangeMoveFromPlace(place)` — подгружает
   животных этого места
   (`getAllAnimalsWithDetailsByFilters(placeIds: [place.idRemote], isNotDeleted: null)`
   — здесь фильтр удалённых **не** применяется, в отличие от предзагрузки
   `presetFromPlace` на шаге 2, см. «Открытые вопросы»), обновляет
   `filtersData.placeIds`; карточка «без места» на этом же шаге →
   `AnimalMovementEventChangeMoveFromPlace(place: null)` — переключает список
   животных на `animalsWithoutPlace`.
5. Шаг «место назначения» (`SelectPlaceStepPage`, тот же виджет): список
   доступных мест на уровне виджета исключает текущее `fromPlace`
   (`_Body._createStepWidgetByStep`, case `selectMoveToPlace`:
   `data.places.where((e) => e.place.idRemote != data.fromPlace?.place.idRemote)`).
   Выбор места → `AnimalMovementEventChangeMoveToPlace(place)` — записывает
   `_data.toPlace`. Если `isSingle` — сразу показывается
   `ConfirmSaveMovementDialog` (шаг «животные» не существует для этого входа);
   иначе — переход к следующему шагу.
6. Шаг «животные» (только групповой вход, `AnimalsStepPage`): множественный
   выбор чекбоксами/сканером/«выбрать всех» →
   `AnimalMovementEventSelectAnimals(ids, isSelected)` — add/remove id из
   `Set` `selectedAnimalIds`. Кнопка перехода к подтверждению
   (`buttonTitle`/`onNext`) **не отображается вовсе**, пока `selectedIds`
   пуст (`AnimalsStepPage.build`, `AnimatedSwitcher` между кнопкой и
   `SizedBox.shrink()`) — этот шаг физически не может быть завершён с пустым
   выбором. По кнопке → тот же `ConfirmSaveMovementDialog`.
7. `ConfirmSaveMovementDialog` показывает сводку (количество животных,
   карточки from/to) и кнопку «Подтвердить» →
   `_ConfirmSaveMovementDialogState.saveMovement()`: `setState(isSaving:
   true)`, `await widget.onSave()`, `setState(isSaving: false, isSaved:
   true)`. Оба вызывающих сайта передают
   `onSave: () async { bloc.add(AnimalMovementEventSave()); }` — колбэк не
   содержит `await` перед диспатчем, поэтому `await widget.onSave()`
   возвращается сразу после синхронной постановки события в очередь bloc'а, не
   дожидаясь реального завершения обработчика `AnimalMovementEventSave»
   (см. «Открытые вопросы»); диалог тут же переключается на состояние
   «успех» (Lottie-анимация + кнопка «Готово»).
8. Обработчик `AnimalMovementEventSave`:
   - эмитит `AnimalMovementSuccess(_data, isLoading: true, loadingMessage:
     'saving_data')`;
   - `syncedAnimals = await _animalsRepository.getAllByFilters(ids:
     _data.selectedAnimalIds)` — дефолтный `isNotDeleted: true`
     (`AnimalsDao.getAllByFilters`: `WHERE deletedAt IS NULL`) — животные,
     помеченные удалёнными между выбором на шаге 6 и нажатием «Подтвердить»,
     автоматически исключаются из `syncedAnimals`;
   - `userId = _authRepository.getUser()?.id ?? -1`;
   - для каждого животного из `syncedAnimals` строит
     `Movement(animalId: animal.id, placeId: _data.toPlace!.place.idRemote!,
     placeDate: DateTime.now(), createdAt: DateTime.now(), updatedAt:
     DateTime.now(), sync: false, remoteId: null, guid: const Uuid().v4(),
     userId: userId, fromId: _data.fromPlace?.place.idRemote)`;
   - вызывает `_movementReportRepository.saveMovements(movements)`;
   - без исключения — эмитит `AnimalMovementSuccess(_data)` (loading
     сброшен); визард **не** закрывается автоматически здесь — закрытие
     происходит отдельным, явным событием `AnimalMovementEventExit`.
9. `MovementReportRepository.saveMovements`:
   - `dao.insAll(movements)` — одна batch-вставка всех записей разом
     (`BaseDao.insAll`, `InsertMode.insertOrReplace`);
   - затем **отдельным циклом** (не в одной транзакции с вставкой) для
     каждой записи с непустыми `animalId`/`placeId` вызывает
     `_animalsRepository.updateAnimalPlaceId(animalId, placeId)`.
   - `AnimalsRepository.updateAnimalPlaceId`: читает животное по id
     (`dao.getById`), обновляет `placeId` (`dao.upd`, с
     `updatedAt: const Value.absent()` — само поле `updatedAt` животного этой
     операцией не трогается) — локально, немедленно, без ожидания сети.
10. Пользователь нажимает «Готово» в диалоге (состояние `isSaved == true`) →
    `onExit`: `Navigator.of(context).pop()` закрывает диалог, затем
    `bloc.add(AnimalMovementEventExit())` → эмитит `AnimalMovementExit` →
    `BlocConsumer.listener` в `AnimalMovementPage` реагирует вызовом
    `context.pop()` — закрывается вся страница визарда.

### Альтернативные потоки

- **Одиночное животное (`isSingle`)**: шаги «место отправления» и «животные»
  отсутствуют в `currentSteps` — `selectedAnimalIds` и `fromPlace` уже
  заполнены на шаге `Start`; единственный проходимый шаг — выбор места
  назначения, сразу за которым — диалог подтверждения. Тот же переход
  `CREATE_OK` — ровно одна запись `Movement`.
- **`presetFromPlace` передан, но `isSingle == false`** (групповой вход с
  предустановленным местом отправления): пропускается только шаг «место
  отправления» — `fromPlace` уже определён на `Start` из `presetFromPlace`;
  шаг «животные» по-прежнему проходится, как в обычном групповом потоке.
- **Несколько выбранных животных**: `saveAnimal`-эквивалент здесь —
  `AnimalMovementEventSave` строит по одной записи `Movement` на каждый id из
  `selectedAnimalIds`, вставленные одним batch-вызовом `dao.insAll`, но с
  отдельным вызовом `updateAnimalPlaceId` на каждое животное.
- **Место отправления не выбрано вовсе** (например прямой вход без
  `presetFromPlace` и без прохождения шага «место отправления» — недостижимо
  для группового входа по `currentSteps`, но достижимо для одиночного входа,
  если `arguments.animal!.placeId` не совпал ни с одним известным местом
  фермы): `_data.fromPlace == null`, `Movement.fromId` сохраняется как `null`.
- **Гость / нет текущей сессии** (`_authRepository.getUser() == null`):
  `Movement.userId` сохраняется как `-1`, поток и результат — те же.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — сущность,
  совершающая переход: по одной новой строке на каждое животное из
  `syncedAnimals`, все с `sync: false`, `remoteId: null`, собственным
  клиентским `guid`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — `placeId`
  каждого перемещённого животного обновляется локально в том же вызове
  `saveMovements`, немедленно, без ожидания серверного подтверждения
  (`updatedAt` при этом не меняется).
- Farm/Place — справочник модуля [FARM](../modules/MOD-3-FARM.md)
  ([ENT-9](../entities/ENT-9-FARM-IN-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md));
  `fromPlace`/`toPlace` ссылаются на них по `idRemote`, сам справочник не
  меняется этим сценарием.

### Бизнес-правила

- Одна запись `Movement` на одно животное — группового перемещения одной
  строкой на несколько животных не существует.
- Список животных, для которых реально создаются записи, повторно выбирается
  из БД с фильтром «не удалено» (`AnimalsRepository.getAllByFilters`,
  дефолтный `isNotDeleted: true`) непосредственно в обработчике `Save` — не
  из `_data.selectedAnimalIds` напрямую, поэтому животные, удалённые между
  выбором на шаге «животные» и нажатием «Подтвердить», в `Movement` не
  попадают.
- `Animal.placeId` обновляется локально в момент сохранения, а не после
  синхронизации, и не зависит от `_data.isNetworkConnected` — сохранение не
  проверяет состояние сети вообще.
- `Movement.fromId` — это `_data.fromPlace?.place.idRemote` на момент
  нажатия «Подтвердить»; `null`, если место отправления не выбрано.
- `Movement.userId` — id текущего пользователя, если сессия есть, иначе `-1`
  (гость или разлогиненное состояние) — независимо от того, каким был вход в
  визард.
- Список мест на шаге выбора места назначения исключает текущее `fromPlace`
  на уровне виджета страницы, не на уровне данных bloc'а.
- Для одиночного животного (`isSingle`) шаги выбора места отправления и
  списка животных не существуют в `currentSteps`; для группового входа с
  `presetFromPlace` не существует только шаг выбора места отправления.
- Кнопка перехода к диалогу подтверждения на шаге «животные» физически не
  отображается, пока `selectedAnimalIds` пуст — 0 выбранных животных не может
  дойти до `AnimalMovementEventSave` этим путём.
- Визард закрывается только по явному `AnimalMovementEventExit` (нажатие
  «Готово» после успеха) — не автоматически сразу по завершении
  `AnimalMovementEventSave`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и покрыт тестом (см. «Связанные
тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/animal_movement_page.dart` | `AnimalMovementPageArguments` (`.all`/`.animal`, `isSingle`) | CURRENT | аргументы точки входа визарда |
| `lib/pages/animal_movement/animal_movement_page.dart` | `_AnimalMovementPageState.build` (`BlocProvider`/`BlocConsumer.listener`) | CURRENT | создаёт `AnimalMovementBloc`, реагирует на `AnimalMovementExit` вызовом `context.pop` |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventStart>` | CURRENT | резолвит `farm`/`fromPlace`, грузит места+животных, ветки `isSingle`/группа |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementData.currentSteps` | CURRENT | реально проходимые шаги визарда, условные `selectMoveFromPlace`/`animals` |
| `lib/pages/umiversal_step_page/select_place_step_page.dart` | `SelectPlaceStepPage` | CURRENT | шаг выбора места (отправления/назначения), карточка «без места» |
| `lib/pages/animal_movement/animal_movement_page.dart` | `_Body._createStepWidgetByStep` (case `selectMoveToPlace`) | CURRENT | список мест назначения исключает текущее `fromPlace` на уровне виджета |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventChangeMoveFromPlace>` | CURRENT | обновление `fromPlace`, подгрузка животных места без фильтра удалённых |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventChangeMoveToPlace>` | CURRENT | запись выбранного места назначения |
| `lib/pages/umiversal_step_page/animals_step_page.dart` | `AnimalsStepPage` | CURRENT | множественный выбор животных, кнопка перехода скрыта при пустом `selectedIds` |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventSelectAnimals>` | CURRENT | add/remove id в `Set` `selectedAnimalIds` |
| `lib/pages/animal_movement/animal_movement_page.dart` | `ConfirmSaveMovementDialog`, `_ConfirmSaveMovementDialogState.saveMovement` | CURRENT | диалог подтверждения, диспатч `Save`, переключение на состояние «успех» |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventSave>` | CURRENT | построение `Movement` на каждое животное из повторно выбранного списка, вызов `saveMovements` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllByFilters` | CURRENT | делегирует в DAO, дефолтный `isNotDeleted: true` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllByFilters` | CURRENT | `WHERE deletedAt IS NULL` при `isNotDeleted: true` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.saveMovements` | CURRENT | batch-вставка `Movement` + отдельный цикл `updateAnimalPlaceId` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll` | CURRENT | batch insert (`InsertMode.insertOrReplace`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateAnimalPlaceId` | CURRENT | читает животное, обновляет `placeId` (`updatedAt` не меняется) |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `Movements`, `Movement` | CURRENT | таблица/модель `Movement` |
| `lib/pages/animal_movement/animal_movement_bloc.dart` | `AnimalMovementBloc.on<AnimalMovementEventExit>` | CURRENT | эмитит `AnimalMovementExit`, закрывающий визард |

## Критерии приёмки

- По нажатию «Подтвердить» в `ConfirmSaveMovementDialog` (после того как
  `_data.toPlace != null` и `_data.selectedAnimalIds` не пуст) выполняется
  ровно один вызов `MovementReportRepository.saveMovements`, со списком,
  длина которого равна количеству записей, вернувшихся из
  `AnimalsRepository.getAllByFilters(ids: selectedAnimalIds)` — то есть уже
  без животных, удалённых между выбором в UI и нажатием кнопки.
- Каждый элемент этого списка — новая `Movement` с `sync: false`,
  `remoteId: null`, непустым клиентским `guid`, `placeId`, равным
  `_data.toPlace!.place.idRemote`, `fromId`, равным
  `_data.fromPlace?.place.idRemote`, и `userId`, равным id текущего
  пользователя либо `-1`.
- После `saveMovements` для каждого элемента с непустыми `animalId` и
  `placeId` выполняется ровно один вызов
  `AnimalsRepository.updateAnimalPlaceId(animalId, placeId)`.
- Обработчик `AnimalMovementEventSave` не эмитит `AnimalMovementExit`
  напрямую — визард закрывается только по отдельному
  `AnimalMovementEventExit`.
- `AnimalsStepPage` не показывает кнопку перехода к подтверждению, пока
  `selectedIds` пуст — путь к `Save` с нулём выбранных животных недостижим
  через эту кнопку.

## Связанные тесты

- `test/pages/animal_movement_bloc_test.dart`, group `'UC-54 — AnimalMovementEventSave'`, тест `'успех -> сохраняет Movement для каждого
  выбранного животного'` — основной поток этого use-case: выбор места
  назначения и одного животного, `AnimalMovementEventSave`, проверка, что
  `saveMovements` вызван с одной `Movement` с ожидаемыми `animalId`/`placeId`/
  `userId`/`sync: false`.
- `test/pages/animal_movement_bloc_test.dart`, group `'AnimalMovementEventSave
  — дополнительные ветки'` — покрывает альтернативные потоки этого же
  сценария: несколько выбранных животных (`Movement` создаётся для каждого),
  отсутствие текущего пользователя (`userId == -1`), выбранное место
  отправления (`fromId` берётся из `fromPlace.place.idRemote`). Имя группы не
  содержит собственной ссылки на `UC-54` (старая нумерация, переименование —
  отдельный контролируемый проход, не в рамках этого файла).
- Группа `'UC-55 — AnimalMovementEventSave'` в этом же файле в это use-case
  не входит — покрывает ветку `ERROR` (исключение при
  `getAllByFilters`/`saveMovements` → `AnimalMovementMessage('an_error_data')`).

## Открытые вопросы и ограничения

- `AnimalMovementData.copyWith` использует `field ?? this.field` для
  нулабельных полей `fromPlace`/`toPlace` — явно переданный `null` неотличим
  от «не передано» и откатывается на прежнее значение. Подтверждено двумя
  тестами, явно помеченными `БАГ` в group `'AnimalMovementEventChangeMoveFromPlace'`
  (`test/pages/animal_movement_bloc_test.dart`): (1) выбор карточки «без
  места» после того как `fromPlace` уже был выбран, корректно переключает
  список животных на `animalsWithoutPlace`, но не очищает `_data.fromPlace` —
  устаревшее значение остаётся и может попасть в `Movement.fromId`, если
  пользователь продолжит без явной смены места; (2) выбор `toPlace`, затем
  смена `fromPlace` на то же место — код пытается сбросить `toPlace`
  (`copyWith(toPlace: null)` в обработчике `ChangeMoveFromPlace`), но из-за
  того же бага `toPlace` не очищается, и в результате может быть сохранён
  `Movement` с `toPlace == fromPlace` (перемещение животного в то же место, в
  котором оно уже находится) — притом что список мест на шаге «место
  назначения» *исключает* текущее `fromPlace` только на уровне виджета, что
  этот конкретный порядок действий (сначала `toPlace`, потом совпавший
  `fromPlace`) обходит. Не исправлено, не разбирается глубже в рамках этого
  файла.
- `ConfirmSaveMovementDialog.saveMovement()` делает `await widget.onSave()`, но
  переданный колбэк (`() async { bloc.add(AnimalMovementEventSave()); }`) не
  содержит `await` перед диспатчем события — диалог переключается в
  состояние «успех» сразу после синхронной постановки события в очередь
  bloc'а, не дожидаясь, пока обработчик `AnimalMovementEventSave` реально
  завершит `getAllByFilters`/`saveMovements`. Пользователь может нажать
  «Готово» (закрывающее весь визард) раньше, чем сохранение в БД
  гарантированно завершилось. Гонка не воспроизведена, не разбирается
  глубже в рамках этого файла.
- `MovementReportRepository.saveMovements` не оборачивает `dao.insAll` и
  последующий цикл `updateAnimalPlaceId` в единую транзакцию — если
  обновление места одного из животных упадёт с исключением, уже вставленные
  записи `Movement` и уже обновлённые `Animal.placeId` предыдущих животных в
  этом же вызове останутся как есть, частичный эффект не откатывается. Не
  воспроизведено, не разбирается глубже.
- Предзагрузка животных места отправления при входе с `presetFromPlace`
  (`AnimalMovementBloc.on<AnimalMovementEventStart>`) использует дефолтный
  `isNotDeleted: true`, а ручной выбор места отправления через
  `AnimalMovementEventChangeMoveFromPlace` — тот же метод репозитория, но с
  `isNotDeleted: null` (фильтр отключён). Это означает, что список животных,
  показанный на шаге «животные», может включать уже удалённых животных, если
  место отправления было выбрано вручную, а не предзадано — они всё равно
  будут молча отброшены на шаге `Save` (см. «Бизнес-правила»), но пользователь
  может увидеть и попытаться выбрать животное, которое не попадёт в
  результат. Не разбирается глубже в рамках этого файла.
- `AnimalsRepository.updateAnimalPlaceId` явно передаёт
  `updatedAt: const Value.absent()` — смена места животного не отражается в
  `Animal.updatedAt`. Неясно, осознанное ли это решение, или недосмотр; не
  разбирается глубже в рамках этого файла.
