# UC-99 — Пользователь оформляет выбытие одного или нескольких животных — успех

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гость или
авторизованный, одинаково) проходит визард выбытия
(`AnimalDisposalBloc`/`AnimalDisposalPage`): выбирает причину выбытия и одно
или несколько животных, подтверждает — для каждого выбранного животного
создаётся отдельная запись `Disposal` (`sync: false`, локальная, без
обращения к серверу). Отдельная ветка того же визарда — причина «между
фермами (объектами) одного владельца» (`id == 4` в справочнике причин) —
добавляет два дополнительных шага (выбор целевой фермы и целевого места) и
заполняет `Disposal.toId`/`toPlaceId`; для любой другой причины эти поля
остаются `null`. Happy-path сценарий события
[EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) (`disposal.recorded`).
В отличие от [Movement](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), это
сохранение не изменяет ни одного поля самого `Animal` — ни `placeId`, ни
`deletedAt`/`disposed` (см. «Связанные сущности», «Бизнес-правила»).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения. Выбытие — local-first сценарий: `AnimalDisposalBloc` не
проверяет статус авторизации нигде в обработчиках, доступно одинаково гостю
и авторизованному пользователю; `userId` записи — id пользователя из
`AuthRepository.getUser()`, либо `-1`, если сессии нет. Сохранение не делает
ни одного сетевого вызова и не проверяет состояние сети; синхронизация —
отдельный, явный проход (см. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)).

## CURRENT

### Основной поток

1. Визард открывается одним из двух реально существующих в навигации
   входов, оба ведущих к `Routes.animalDisposal`:
   - `AnimalOperationsPage` (плитка «Выбытие» для конкретного животного,
     `lib/pages/animal_operations/animal_operations_page.dart`) →
     `AnimalDisposalPageArguments.animal(animal: animal)` — `isSingle ==
     true`;
   - `OperationsPage` (плитка «Выбытие» для места,
     `lib/pages/operations/operations_page.dart`) →
     `AnimalDisposalPageArguments.all(place: place)` — `isSingle == false`,
     `presetPlace == place`.
   Третий вариант конструктора аргументов, `AnimalDisposalPageArguments.all(farm:
   ...)` (принимающий уже загруженный `FarmWithDetails`, без обращения к
   `FarmRepository`/`PlaceRepository`/`AnimalsRepository` в `EventStart`),
   существует в коде и покрыт тестом, но ни один живой вызывающий код во всём
   `lib/` не использует эту форму — недостижим через реальную навигацию (см.
   «Открытые вопросы»).
2. `AnimalDisposalBloc` создаётся в `BlocProvider.create` вместе с
   `AnimalDisposalEventStart()`. Обработчик `on<AnimalDisposalEventStart>`:
   - резолвит `farm`: если задан `presetPlace` — через
     `FarmRepository.getById(presetPlace!.farmId)` (единственная ветка,
     реально используемая обоими живыми входами, поскольку `.animal(...)`
     тоже, отдельной веткой ниже, задаёт `presetPlace` через `fromPlace`, а
     не напрямую — фактически же для входа `.animal(...)` фермa берётся из
     `arguments.animal!.farm!`, а не из `presetPlace`, см. код: приоритет —
     `presetPlace != null` → `getById`, иначе `arguments.farm != null` →
     `arguments.farm!.farm` (недостижимая ветка), иначе
     `arguments.animal!.farm!`);
   - грузит все места фермы с животными
     (`PlaceRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)`);
   - резолвит `fromPlace`: для `.animal(...)` (isSingle) — место из уже
     загруженного списка, чей `idRemote` совпадает с
     `arguments.animal!.placeId`, либо `null`; для `.all(place:)` — место из
     того же списка, чей `idRemote` совпадает с `presetPlace!.idRemote`;
   - если `fromPlace` резолвлен — сразу грузит животных этого места
     (`AnimalsRepository.getAllAnimalsWithDetailsByFilters(placeIds:
     [fromPlace.place.idRemote!])`) в `presetAnimals`/`_data.animalsWithDetails`
     и синхронизирует `filtersData.placeIds`;
   - грузит справочник причин целиком, без фильтрации
     (`DisposalReasonsRepository.getAll()` — унаследован из
     `BaseRepository.getAll()` → `dao.getAll()`; список **не** сужается до
     `DisposalReasonHelper.availableIds`, причина `id == 4` присутствует в
     выборе наравне со всеми остальными);
   - грузит `targetFarms = (FarmRepository.getAll()).where((e) => e.remoteId
     != farm.remoteId)` — все известные локально фермы, кроме текущей, без
     какой-либо проверки «того же владельца» на уровне кода (см. «Открытые
     вопросы»);
   - для `.animal(...)` (isSingle) сразу выставляет
     `selectedAnimalIds: [arguments.animal!.animal.id]`.
3. Реально проходимые шаги визарда — `AnimalDisposalData.currentSteps`:
   `selectPlace` (только если `!isSingle && presetPlace == null` — для обоих
   живых входов это условие всегда ложно, см. «Открытые вопросы») → `reason`
   (всегда) →, если выбранная причина `id == 4`, `selectTargetFarm` и
   `selectTargetPlace` → `animals` (всегда, в т.ч. для `isSingle` — этот же
   шаг несёт кнопку подтверждения выбытия).
4. Шаг «причина» (`DisposalReasonStepPage`): выбор чипа причины →
   `AnimalDisposalEventSelectReason(reason:)` — сохраняет `selectedReason` и
   безусловно сбрасывает `selectedTargetFarm`/`selectedTargetPlace`
   (`clearSelectedTargetFarm: true, clearSelectedTargetPlace: true`) и
   `targetPlaces` (`const []`), даже если причина не меняется на «между
   фермами» и обратно. Кнопка «Далее» активна только при выбранной причине,
   отдельным нажатием переключает вкладку (`toNextStep`).
5. Если выбранная причина `id == 4` («между фермами одного владельца»):
   - шаг «целевая ферма» (`SelectTargetFarmStepPage`, выпадающий список из
     `targetFarms`) → выбор →
     `AnimalDisposalEventSelectTargetFarm(farm:)` — грузит места этой фермы
     (`PlaceRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)`) в
     `targetPlaces`, сохраняет `selectedTargetFarm`, сбрасывает
     `selectedTargetPlace` (`clearSelectedTargetPlace: true`); кнопка
     «Далее» отдельным нажатием переключает вкладку;
   - шаг «целевое место» (`SelectPlaceStepPage`, тот же виджет, что и у
     шага `selectPlace`) → выбор места → `AnimalDisposalEventChangeTargetPlace(place)`
     сохраняет `selectedTargetPlace` **и** сразу переключает вкладку
     (`onSelectPlace: (place) { bloc.add(...); toNextStep(); }` — одно
     нажатие делает оба действия, без отдельной кнопки «Далее»).
6. Шаг «животные» (`AnimalsStepPage`): показывает
   `[...selectedAnimals, ...filteredAnimals]` (уже выбранные — первыми),
   множественный выбор чекбоксами/сканером номера/«выбрать всех» →
   `AnimalDisposalEventSelectAnimals(ids, isSelected)` — add/remove из `Set`
   `selectedAnimalIds`. Кнопка «Оформить выбытие» физически не отображается
   (`AnimatedSwitcher` между кнопкой и `SizedBox.shrink()`), пока
   `selectedIds` пуст — для группового входа это реальный гейт (для
   `isSingle` список уже непуст с момента `Start`). По кнопке — открывается
   `showDialog(... ConfirmSaveDisposalDialog(...))` с `animalsCount:
   selectedAnimalIds.length` и `reasonName: selectedReason?.name ?? ''`.
7. `ConfirmSaveDisposalDialog` показывает сводку и кнопку «Подтвердить» →
   `_ConfirmSaveDisposalDialogState.saveDisposal()`: `setState(isSaving:
   true)`, `await widget.onSave()`, затем (если виджет ещё смонтирован)
   `setState(isSaving: false, isSaved: true)`. Переданный колбэк — `onSave:
   () async { bloc.add(const AnimalDisposalEventSave()); }` — тело без
   `await` перед диспатчем, поэтому `await widget.onSave()` возвращается
   сразу после синхронной постановки события в очередь bloc'а, не дожидаясь
   реального завершения обработчика `AnimalDisposalEventSave` (см.
   «Открытые вопросы» — тот же паттерн, что и в аналогичном диалоге
   Movement,
   [UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md)). Диалог
   тут же переключается на состояние «успех» (заголовок
   `animals_disposed` + Lottie-анимация + кнопка «Готово»).
8. Обработчик `AnimalDisposalBloc.on<AnimalDisposalEventSave>`:
   - эмитит `AnimalDisposalSuccess(_data, isLoading: true, loadingMessage:
     'saving_data')`;
   - `animals = await _animalsRepository.getAllByFilters(ids:
     _data.selectedAnimalIds)` — дефолтный `isNotDeleted: true`
     (`AnimalsDao.getAllByFilters`: `WHERE deletedAt IS NULL`) — животные,
     удалённые между выбором на шаге «животные» и нажатием «Подтвердить»,
     автоматически исключаются;
   - `userId = _authRepository.getUser()?.id ?? -1`;
   - `isBetweenFarms = _data.isBetweenFarmsReason` (`selectedReason?.id ==
     4`);
   - для каждого животного из `animals` строит
     `Disposal(animalId: animal.id, placeId: animal.placeId ??
     _data.fromPlace?.place.idRemote, causeId: _data.selectedReason?.id,
     date: now, createdAt: now, updatedAt: now, sync: false, remoteId: null,
     guid: const Uuid().v4(), userId: userId, fromId: _data.farm?.remoteId,
     toId: isBetweenFarms ? _data.selectedTargetFarm?.remoteId : null,
     toPlaceId: isBetweenFarms ? _data.selectedTargetPlace?.place.idRemote :
     null)`;
   - вызывает `await _disposalRepository.saveDisposals(disposals)`;
   - без исключения — эмитит `AnimalDisposalSuccess(_data)` (loading
     сброшен), затем, безусловно (тот же путь исполнения, вне
     `try`/`catch`), эмитит `AnimalDisposalSuccess(_data)` ещё раз. Оба
     значения равны через `Equatable`; согласно `BlocBase.emit` (`if (state
     == _state && _emitted) return;`, пакет `bloc`) второй, идентичный
     emit — no-op, не порождает второго видимого состояния в стриме (см.
     тест `UC-152`, где на пути ошибки два разных по типу состояния между
     этими двумя emit'ами делают их оба видимыми).
9. `DisposalRepository.saveDisposals(disposals)` — единственная строка:
   `dao.insAll(disposals)`. `BaseDao.insAll` выполняет один drift `batch(...)`
   со всеми записями разом (`InsertMode.insertOrReplace`) — вставка всей
   партии одним атомарным батчем. В отличие от
   `MovementReportRepository.saveMovements`, здесь **нет** отдельного цикла,
   обновляющего что-либо в `Animal` — этим сценарием ни `placeId`, ни
   `deletedAt` животного не трогаются вовсе.
10. Пользователь нажимает «Готово» в диалоге (`isSaved == true`) → `onExit`:
    `Navigator.of(context).pop()` закрывает диалог, затем `bloc.add(const
    AnimalDisposalEventExit())` → эмитит `AnimalDisposalExit` →
    `BlocConsumer.listener` в `AnimalDisposalPage` реагирует `context.pop()`
    — закрывается вся страница визарда.

### Альтернативные потоки

- **Одиночное животное (`isSingle`, вход `AnimalOperationsPage`)**: шаг
  `selectPlace` отсутствует; `selectedAnimalIds` уже заполнен на `Start`,
  так что шаг «животные» сразу показывает кнопку подтверждения без
  дополнительного выбора. Тот же переход `CREATE_OK` — ровно одна запись
  `Disposal`.
- **Причина «между фермами одного владельца» (`id == 4`)**: два
  дополнительных шага (`selectTargetFarm`/`selectTargetPlace`); сохранённая
  запись получает непустые `toId`/`toPlaceId`.
- **Причина отличная от `id == 4`, даже если целевые ферма/место уже были
  выбраны ранее**: `AnimalDisposalEventSelectReason` безусловно сбрасывает
  `selectedTargetFarm`/`selectedTargetPlace` при любой смене причины, так
  что `toId`/`toPlaceId` сохранённой записи — `null`, независимо от того,
  что было выбрано перед этим (покрыто отдельным тестом, см. «Связанные
  тесты»).
- **Несколько выбранных животных**: по одной записи `Disposal` на каждое
  животное из `animals` (после повторной выборки из БД), вставленных одним
  batch-вызовом `dao.insAll` — не единая групповая запись.
- **У животного нет собственного `placeId`**: `Disposal.placeId` берётся из
  `_data.fromPlace?.place.idRemote` (заполняется через
  `AnimalDisposalEventChangePlace`, реально применимо для группового входа
  без `presetPlace`, недостижимого через текущую навигацию, — см. «Открытые
  вопросы»); если и `fromPlace` не задан, `placeId` сохраняется как `null`.
- **Гость / нет текущей сессии** (`_authRepository.getUser() == null`):
  `Disposal.userId` сохраняется как `-1`, поток и результат — те же.
- **`fromId`** — это `_data.farm?.remoteId`, резолвленный один раз в
  `EventStart` и далее не перечитываемый; для обоих живых входов — ферма,
  полученная через `FarmRepository.getById(presetPlace.farmId)` (вход
  `.all(place:)`) либо `arguments.animal!.farm!` (вход `.animal(...)`).

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сущность,
  совершающая переход: по одной новой строке на каждое животное из
  `animals`, все с `sync: false`, `remoteId: null`, собственным клиентским
  `guid`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только на
  чтение: повторная выборка по `selectedAnimalIds`
  (`AnimalsRepository.getAllByFilters`, дефолтный `isNotDeleted: true`) для
  чтения актуального `placeId` каждого животного. Этим сценарием **не
  пишется ни одно поле** `Animal` — ни `placeId` (в отличие от Movement), ни
  `deletedAt`/`disposed` (выбытие животного как факт на самом `Animal`
  появляется только при следующей полной перезагрузке с сервера, см.
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) и
  `.claude/rules/domain-model.md`, инвариант 6). Подтверждено интеграционным
  тестом (см. «Связанные тесты»).
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — только читается, список не фильтруется
  (`DisposalReasonsRepository.getAll()`, без сужения до
  `DisposalReasonHelper.availableIds`); причина с `causeId == 4` жёстко
  закодирована в `AnimalDisposalData.betweenFarmsReasonId` и переключает
  форму на сценарий «между фермами».
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только читается:
  текущая ферма (`fromId`) и список `targetFarms` (все фермы, кроме
  текущей, без проверки принадлежности одному владельцу); не изменяется
  этим сценарием.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — только
  читается: `fromPlace`/`selectedTargetPlace` ссылаются на места по
  `idRemote`; не изменяется этим сценарием.

### Бизнес-правила

- Одна запись `Disposal` на одно животное — групповой записи на несколько
  животных одной строкой не существует.
- `toId`/`toPlaceId` заполняются исключительно при `selectedReason?.id ==
  4`; для любой другой причины — всегда `null`, даже если целевые
  ферма/место были выбраны на более раннем шаге визарда и затем причина
  сменилась (смена причины безусловно их сбрасывает).
- `placeId` сохранённой записи — это `animal.placeId` (актуальный, из
  повторной выборки на момент `Save`), а не значение, зафиксированное в
  `AnimalWithDetails` на момент входа в визард; если у животного `placeId`
  не задан — используется `_data.fromPlace?.place.idRemote`.
- `fromId` — это ферма, резолвленная один раз в `EventStart`, не
  перечитываемая заново в момент `Save`.
- `userId` — id текущего пользователя, если сессия есть, иначе `-1` —
  независимо от того, каким был вход в визард.
- Список животных, для которых реально создаются записи, повторно
  выбирается из БД с фильтром «не удалено»
  (`AnimalsRepository.getAllByFilters`, дефолтный `isNotDeleted: true`)
  непосредственно в обработчике `Save`, а не берётся из
  `_data.selectedAnimalIds` напрямую — животные, удалённые между выбором на
  шаге «животные» и нажатием «Подтвердить», в `Disposal` не попадают.
- Сохранение полностью локальное: `on<AnimalDisposalEventSave>` не делает ни
  одного сетевого вызова и не проверяет состояние сети.
- `sync: false` устанавливается явно на каждой записи.
- `DisposalRepository.saveDisposals` не производит никаких побочных
  обновлений `Animal` — в отличие от `MovementReportRepository.saveMovements`,
  который после вставки `Movement` отдельным циклом обновляет
  `Animal.placeId`.
- Кнопка перехода к диалогу подтверждения на шаге «животные» физически не
  отображается, пока `selectedAnimalIds` пуст — путь к `Save` с нулём
  выбранных животных недостижим этой кнопкой.
- Визард закрывается только по явному `AnimalDisposalEventExit` (нажатие
  «Готово» после успеха), не автоматически сразу по завершении
  `AnimalDisposalEventSave`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток, включая ветку «между фермами одного владельца» и
групповое выбытие нескольких животных, полностью реализован и покрыт
тестами (см. «Связанные тесты»); находки, перечисленные в «Открытые вопросы
и ограничения», не блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_operations/animal_operations_page.dart` | плитка «Выбытие» (`onTap` → `Routes.animalDisposal`) | CURRENT | вход №1 — одно предзаданное животное (`AnimalDisposalPageArguments.animal`) |
| `lib/pages/operations/operations_page.dart` | плитка «Выбытие» (`onTap` → `Routes.animalDisposal`) | CURRENT | вход №2 — групповой, предзаданное место (`AnimalDisposalPageArguments.all(place:)`) |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `AnimalDisposalPageArguments` (`.animal`/`.all`, `isSingle`) | CURRENT | аргументы точки входа визарда, включая недостижимую через навигацию форму `.all(farm:)` |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `_AnimalDisposalPageState.build` (`BlocProvider`/`BlocConsumer.listener`) | CURRENT | создаёт `AnimalDisposalBloc`, реагирует на `AnimalDisposalExit` (`context.pop`) и `AnimalDisposalMessage` (`SnackBar`) |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventStart>` | CURRENT | резолвит `farm`/`fromPlace`, грузит места+животных, причины (без фильтра), `targetFarms` |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalData.currentSteps`, `.isBetweenFarmsReason`, `.betweenFarmsReasonId` | CURRENT | состав шагов визарда, ветка «между фермами» (`id == 4`) |
| `lib/pages/animal_disposal/steps/disposal_reason_step_page.dart` | `DisposalReasonStepPage` | CURRENT | шаг выбора причины |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventSelectReason>` | CURRENT | сохраняет причину, безусловно сбрасывает целевую ферму/место |
| `lib/pages/animal_disposal/steps/select_target_farm_step_page.dart` | `SelectTargetFarmStepPage` | CURRENT | шаг выбора целевой фермы (только ветка «между фермами») |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventSelectTargetFarm>` | CURRENT | грузит места целевой фермы, сбрасывает целевое место |
| `lib/pages/umiversal_step_page/select_place_step_page.dart` | `SelectPlaceStepPage` | CURRENT | шаг выбора места — переиспользуется и для `selectPlace`, и для `selectTargetPlace` |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventChangeTargetPlace>`, `.on<AnimalDisposalEventChangePlace>` | CURRENT | сохраняют выбранное целевое место / место отправления |
| `lib/pages/umiversal_step_page/animals_step_page.dart` | `AnimalsStepPage` | CURRENT | множественный выбор животных, кнопка подтверждения скрыта при пустом `selectedIds` |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventSelectAnimals>` | CURRENT | add/remove id в `Set` `selectedAnimalIds` |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `ConfirmSaveDisposalDialog`, `_ConfirmSaveDisposalDialogState.saveDisposal` | CURRENT | диалог подтверждения, диспатч `Save`, переключение на состояние «успех»; `onSave` не дожидается реального завершения обработчика |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventSave>` | CURRENT | ядро сценария — построение `Disposal` на каждое повторно выбранное животное, вызов `saveDisposals` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllByFilters` | CURRENT | делегирует в DAO, дефолтный `isNotDeleted: true` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllByFilters` | CURRENT | `WHERE deletedAt IS NULL` при `isNotDeleted: true` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.saveDisposals` | CURRENT | единственная точка записи — `dao.insAll`, без побочных обновлений `Animal` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll` | CURRENT | batch-вставка (`InsertMode.insertOrReplace`) в одном drift `batch` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals` | CURRENT | схема таблицы `Disposal` |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository` (наследует `BaseRepository.getAll`) | CURRENT | список причин — без сужения до `DisposalReasonHelper.availableIds` |
| `lib/utilts/disposal_reason_helper.dart` | `DisposalReasonHelper.movementBetweenObjectsOwnerId` | CURRENT | значение `4`, совпадающее с `AnimalDisposalData.betweenFarmsReasonId`, но не используемое `AnimalDisposalBloc` напрямую (литерал продублирован) |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById`, `.getAll` | CURRENT | резолв текущей фермы (`Start`) и списка целевых ферм (ветка «между фермами») |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getAllWithThisFarmIdWithAnimals` | CURRENT | места текущей фермы (`Start`) и целевой фермы (`SelectTargetFarm`) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser` | CURRENT | `userId` записи, `-1` для гостя |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventExit>` | CURRENT | эмитит `AnimalDisposalExit`, закрывающий визард |
| `/Users/pavelsmirnov/.pub-cache/hosted/pub.dev/bloc-9.2.0/lib/src/bloc_base.dart` | `BlocBase.emit` | CURRENT (внешний пакет `bloc`) | `if (state == _state && _emitted) return;` — второй, идентичный `emit(AnimalDisposalSuccess(_data))` в конце обработчика `Save` — no-op |

## Критерии приёмки

- По нажатию «Подтвердить» в `ConfirmSaveDisposalDialog` (после того как
  `_data.selectedReason != null` и `_data.selectedAnimalIds` не пуст)
  выполняется ровно один вызов `DisposalRepository.saveDisposals`, со
  списком, длина которого равна количеству записей, вернувшихся из
  `AnimalsRepository.getAllByFilters(ids: selectedAnimalIds)` — то есть уже
  без животных, удалённых между выбором в UI и нажатием кнопки.
- Каждый элемент этого списка — новая `Disposal` с `sync: false`,
  `remoteId: null`, непустым клиентским `guid`, `causeId ==
  _data.selectedReason?.id`, `userId`, равным id текущего пользователя либо
  `-1`, `fromId == _data.farm?.remoteId`.
- `placeId` каждого элемента равен `animal.placeId`, если оно задано, иначе
  `_data.fromPlace?.place.idRemote`.
- `toId`/`toPlaceId` каждого элемента непусты тогда и только тогда, когда
  `_data.selectedReason?.id == 4`; в этом случае они равны
  `_data.selectedTargetFarm?.remoteId`/`_data.selectedTargetPlace?.place.idRemote`.
  Для любой другой причины — `null`, даже если целевая ферма/место были
  выбраны на более раннем шаге того же прохождения визарда.
- Обработчик `AnimalDisposalEventSave` не выполняет ни одного сетевого
  вызова и не изменяет ни одно поле `Animal`.
- `AnimalsStepPage` не показывает кнопку подтверждения, пока
  `selectedAnimalIds` пуст — путь к `Save` с нулём выбранных животных
  недостижим через эту кнопку.
- Обработчик `AnimalDisposalEventSave` не эмитит `AnimalDisposalExit`
  напрямую — визард закрывается только по отдельному
  `AnimalDisposalEventExit`.

## Связанные тесты

- `test/pages/animal_disposal_bloc_test.dart`, group `'UC-99 —
  AnimalDisposalEventSave'` (5 тестов) — основной поток и большая часть
  альтернативных потоков этого use-case: `'успех -> сохраняет Disposal для
  каждого выбранного животного'`; `'нет авторизованного пользователя, но
  сохранение успешно -> userId = -1'`; `'у животного нет своего placeId ->
  берётся место из _data.fromPlace (заполненного через ChangePlace)'`;
  `'fromId сохранённого Disposal берётся из фермы, загруженной в EventStart
  (.all(farm:))'` (несмотря на название, тест использует `.all(farm:)` как
  способ явно задать ферму в тестовом `build`, а не как утверждение о живом
  входе — сама эта форма аргументов недостижима через реальную навигацию,
  см. «Открытые вопросы»); `'несколько выбранных животных -> по одному
  Disposal на каждое'`.
- `test/pages/animal_disposal_bloc_test.dart`, group `'UC-99 —
  AnimalDisposalEventSave (причина «между фермами владельца»)'` (2 теста) —
  ветка «между фермами»: `'причина id == 4 c выбранными целевой
  фермой/местом -> toId/toPlaceId заполнены'`; `'причина отличная от id ==
  4, даже если целевые ферма/место выбраны ранее -> toId/toPlaceId не
  заполняются'`.
- `test/integration/registration_to_disposal_test.dart`, bare `test(...)` с
  описанием, начинающимся `'UC-99 — животное, зарегистрированное
  AnimalRegistrationBloc, находится и выбывает через AnimalDisposalBloc;
  после выбытия остаётся не помеченным disposed локально (ENT-16/ENT-11,
  domain-model.md — disposed выставляется только сервером)'` — сквозной
  интеграционный тест с реальными `AnimalsRepository`/`DisposalRepository`
  поверх общей in-memory БД (без моков): регистрирует животное через
  `AnimalRegistrationBloc`, затем выбывает его через тот же
  `AnimalDisposalBloc`, проверяет реально вставленную строку `Disposal`
  (`animalId`/`causeId`/`userId`/`sync`) через `DisposalRepository.getAll()`
  и подтверждает, что `Animal.deletedAt` после этого остаётся `null` —
  единственный тест, реально проходящий через `dao.insAll`, а не через
  мокнутый `DisposalRepository`. (Комментарий в описании теста ссылается на
  `ENT-10`, но по содержанию описывает инвариант `Disposal`/`Animal`,
  зафиксированный здесь как [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md).)
- Группа `'AnimalDisposalEventSelectReason / SelectAnimals / ChangeFilters /
  ChangePlace'` и группа `'AnimalDisposalEventSelectTargetFarm /
  ChangeTargetPlace'` (тот же файл) не входят в этот use-case напрямую (они
  проверяют отдельные обработчики шагов, не `Save`), но покрывают
  предпосылки для альтернативных потоков, описанных выше — в частности,
  тест `'SelectReason сбрасывает ранее выбранные целевую ферму/место'`
  напрямую подтверждает правило, зафиксированное в «Бизнес-правила».
- Группа `'UC-100 — AnimalDisposalEventSave'` (тот же файл) в этот use-case
  не входит — покрывает ветку `ERROR` (исключение при
  `getAllByFilters`/`saveDisposals` → `AnimalDisposalMessage('an_error_data')`).
- **TBD — теста нет** на реальный вызов `dao.insAll` при **нескольких**
  животных или на партию, где один и тот же `guid` мог бы случайно
  дублироваться — интеграционный тест выше проверяет только одно животное.
- **TBD — теста нет** на связку `ConfirmSaveDisposalDialog`/
  `_Body._createStepWidget` (widget-уровень) — в частности, на факт, что
  `await widget.onSave()` не дожидается реального завершения
  `AnimalDisposalEventSave` (отмечено как код-ридинг наблюдение, не
  воспроизведено тестом).

## Открытые вопросы и ограничения

- **Шаг `selectPlace` де-факто недостижим.** Оба реально существующих в
  навигации входа (`AnimalOperationsPage` → `.animal(...)`, `OperationsPage`
  → `.all(place:)`) всегда приводят к условию `isSingle || presetPlace !=
  null`, при котором `AnimalDisposalData.currentSteps` пропускает шаг
  `selectPlace`. Он существует в коде, отрисовывается
  `SelectPlaceStepPage`-виджетом и покрыт логикой bloc'а
  (`AnimalDisposalEventChangePlace`), но требует вызова
  `AnimalDisposalPageArguments.all()` без `place` и без `farm` — такого
  вызова не найдено ни в одном месте `lib/`. Не разбирается глубже в рамках
  этого файла.
- **`AnimalDisposalPageArguments.all(farm:)` недостижим через реальную
  навигацию.** Форма аргументов, целиком минующая
  `FarmRepository`/`PlaceRepository`/`AnimalsRepository` в `EventStart` и
  беручая ферму/места сразу из переданного `FarmWithDetails`, существует в
  коде и покрыта тестом (`'.all(farm:) — берёт ферму и места напрямую из
  аргумента...'`), но ни один живой вызывающий код не конструирует
  `AnimalDisposalPageArguments` таким образом — только тесты. Не
  разбирается глубже в рамках этого файла.
- **`ConfirmSaveDisposalDialog.saveDisposal()` не дожидается реального
  завершения сохранения.** `await widget.onSave()` дожидается только
  синхронной постановки `AnimalDisposalEventSave` в очередь bloc'а
  (переданный колбэк не содержит `await` перед `bloc.add(...)`), а не
  завершения самого обработчика (`getAllByFilters`/`saveDisposals`). Диалог
  переключается в состояние «успех» и позволяет закрыть визард раньше, чем
  запись в БД гарантированно завершена — тот же паттерн, что и в аналогичном
  диалоге Movement
  ([UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md)). Гонка не
  воспроизведена, не разбирается глубже.
- **`targetFarms` не проверяет принадлежность одному владельцу.** Список
  целевых ферм для сценария «между фермами одного владельца» — это все
  локально известные фермы, кроме текущей (`FarmRepository.getAll()`, минус
  `farm`), без какой-либо проверки, что они действительно принадлежат
  «одному владельцу» — сама эта гарантия, если она вообще существует,
  обеспечивается только тем, что приложение ведёт единственный профиль
  фермера (см. «Single profile», `sdlc/2-specs/AGENTS.md`), а не явной
  проверкой в этом коде. Не разбирается глубже.
- **Справочник причин не фильтруется до `DisposalReasonHelper.availableIds`.**
  `EventStart` вызывает `DisposalReasonsRepository.getAll()` напрямую
  (унаследованный `BaseRepository.getAll()` → `dao.getAll()`), а не
  `getAllAvailable()` (который сузил бы список до
  `DisposalReasonHelper.availableIds`) — весь локально синхронизированный
  справочник причин становится выбираемым в UI, включая причину `id == 4`.
  Комментарий в исходном коде bloc'а (`AnimalDisposalData.betweenFarmsReasonId`)
  ссылается на спек-идентификаторы `ENT-27`/`UC-319` как источник этого
  наблюдения («снятое исключение `.where((e) => e.id != 4)`»); `ENT-27` не
  резолвится ни к одному живому артефакту в `sdlc/2-specs/` на момент
  написания этого файла (вероятно, остаток нумерации до полной пересборки
  дерева спек) — не цитируется здесь как ссылка на артефакт, только
  дословно как текст комментария в источнике. Не разбирается глубже.
- **Двойной `emit(AnimalDisposalSuccess(_data))` в конце успешного пути.**
  Не имеет видимого эффекта благодаря дедупликации одинаковых
  последовательных состояний в `BlocBase.emit` (пакет `bloc`), но остаётся
  избыточным чтением кода — при любом будущем изменении, из-за которого
  второй `_data` перестанет быть равным первому (например, добавление поля,
  меняющегося между двумя emit'ами), туда незаметно вернётся второе видимое
  состояние. Не воспроизведено тестом, не разбирается глубже.
