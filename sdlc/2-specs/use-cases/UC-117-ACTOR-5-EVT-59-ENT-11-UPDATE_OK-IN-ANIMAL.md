# UC-117 — Пользователь привязывает потомка на экране «Разведение» — успех

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь, находясь на экране «Разведение» просматриваемого животного A,
выбирает из списка кандидатов животное B (потомка) и подтверждает —
`ReproductionCubit.saveChild`. Сохранение изменяет запись **B**, не A: у B
выставляются `motherId`/`fatherId` (в зависимости от пола A), а второй
родитель B переносится из уже известного второго родителя A, если такой есть.
Happy-path сценарий события
[EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md) (`animal.child_linked`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `ReproductionCubit` не
проверяет статус авторизации ни в одном из задействованных методов
(`load`/`selectAvailableChild`/`saveChild`). Кнопка добавления потомка (FAB)
показывается только на вкладке «Потомки» (`ReproductionFilter.children`,
`_syncFab` в `lib/pages/reproduction/presentation/widgets/reproduction_view.dart`)
и только если просматриваемое животное A не выбыло
(`widget.animal.animal.deletedAt == null`) — при выбытии FAB скрывается
безусловно (`_ReproductionViewState.initState`/`_isDisposed`). Сохранение не
делает ни одного сетевого вызова; синхронизация — отдельный, явный проход
(см. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)).

## CURRENT

### Основной поток

1. Пользователь открывает `ReproductionPage` для животного A
   (`ReproductionPageArguments(animal: A)` → `ReproductionView(animal: A)`),
   которая создаёт `ReproductionCubit(A)..load()`. `load()` заполняет:
   `parents` (уже известные родители A), `children` (текущий список потомков
   A — `AnimalsRepository.getChildrenByParentId(A.animalId)`, запрос по
   `motherId == A.id OR fatherId == A.id`) и
   `addChildrenData.availableChildren` — кандидаты в потомки:
   `getAllAnimalsWithDetailsByFilters(kindIds: [A.kind.id], birthDateRange:
   DateTimeRange(start: A.birthDate, end: DateTime.now()))` — тот же вид, что
   у A, и дата рождения не раньше даты рождения A.
2. Пользователь переключается на вкладку «Потомки»
   (`ReproductionFilter.children`) — появляется плавающая кнопка добавления
   (см. «Пользователь»).
3. Тап по FAB → `_showAddChildModal` →
   `showModalBottomSheet(...ReproductionChildModalWidget(cubit:
   reproductionCubit))` — тот же экземпляр `ReproductionCubit`, переданный
   через `BlocProvider.value`.
4. В модалке — `AutoCompleteTextField<AnimalWithDetails>`, фильтрующий
   `state.addChildrenData.availableChildren` по вхождению введённого текста
   в номер идентификации кандидата **и** по `animal.animalId !=
   widget.cubit.state.animal.animalId` (кандидат не может быть самим
   животным A).
5. Пользователь выбирает кандидата B из списка →
   `onSelected` вызывает `ReproductionCubit.selectAvailableChild(B)` →
   `emit(state.copyWith(addChildrenData:
   state.addChildrenData!.copyWith(animalId: B.animal.id)))` — в состоянии
   фиксируется только `id` B, не сам объект `AnimalWithDetails`.
6. Пользователь жмёт «Сохранить» (`BlackCircleButton`, floating action
   button модалки) →
   `await context.read<ReproductionCubit>().saveChild()`; сразу после
   (`if (context.mounted)`) — `context.pop(context)` закрывает модалку
   **безусловно**, независимо от исхода `saveChild()`.
7. `ReproductionCubit.saveChild()`:
   - `emit(state.copyWith(isLoading: true))`.
   - `child = state.addChildrenData`; guard `if (child == null ||
     child.animalId == null) return;` — не срабатывает на этом пути
     (кандидат уже выбран на шаге 5).
   - Собирает известных родителей A из уже загруженных в состояние полей
     `state.animal.animal` (`animalData`), **без** обращения к репозиторию:
     `mother = Parents(id: state.animal.motherId, transponderId:
     animalData.motherBirk, gender: Gender.female, kindId:
     animalData.kindId)`, если `state.animal.motherId != null ||
     animalData.motherBirk != null`, иначе `null`; `father` — симметрично,
     по `fatherId`/`fatherBirk`.
   - Строит `newParent` — представление самого A как родителя:
     `Parents(id: state.animal.animalId, transponderId:
     state.animal.activeAnimalIdentifications.firstOrNull?.number,
     birthDate: state.animal.birthDate, gender:
     Gender.byId(state.animal.animal.gender), kindId:
     state.animal.animal.kindId)`.
   - Пол A решает, куда попадает `newParent`: `state.animal.animal.gender ==
     Gender.femaleGenderId` → `mother = newParent` (перезаписывает то, что
     было собрано выше); `== Gender.maleGenderId` → `father = newParent`.
   - `animalChild = await _animalsRepository.getAnimalWithDetailsById(
     child.animalId!)` — **повторная выборка** полной, актуальной на момент
     сохранения записи потомка B из БД (через
     `AnimalsDao.getAnimalWithDetailsById` →
     `getAllAnimalsWithDetailsByFilters(ids: [id], isNotDeleted: null)` —
     включая мягко удалённых животных), а не переиспользование объекта,
     переданного в `selectAvailableChild` на шаге 5.
   - Guard `if (animalChild == null) return;` — не срабатывает на этом пути
     (B резолвится по `id`).
   - `updatedChildAnimal = animalChild.animal.copyWith(motherId:
     Value(mother?.id), motherBirk: Value(mother?.transponderId),
     motherName: const Value(null), fatherId: Value(father?.id), fatherBirk:
     Value(father?.transponderId), fatherName: const Value(null),
     needsUpdate: animalChild.animal.id >= 0 ? const Value(true) : const
     Value.absent())` — изменяется запись **B** (потомка), не A;
     `needsUpdate` зависит от `animalChild.animal.id` (id самого B), не от
     `state.animal.animal.id` (id A).
   - `await _animalsRepository.update(updatedChildAnimal)` →
     `BaseRepository.update` → `dao.upd(item)` → `BaseDao.upd` =
     `updateCurrent().replace(item)` — не бросает исключение на этом пути.
   - `updatedChild = animalChild.copyWith(animal: updatedChildAnimal)`;
     `updatedChildren = [...state.children.where((e) => e.animalId !=
     updatedChild.animalId), updatedChild]` — локальный список потомков A в
     состоянии обновляется **в памяти** (без повторного запроса
     `getChildrenByParentId`), заменяя запись B, если она уже была в списке,
     либо добавляя новую.
   - `emit(state.copyWith(isLoading: false, children: updatedChildren,
     addChildrenData: AddChildrenData(availableChildren:
     state.addChildrenData!.availableChildren)))` — выбор (`animalId`) в
     `addChildrenData` сбрасывается, список кандидатов сохраняется как был.
8. `.then((_) => cubit.clearChildData())` (продолжение шага 3, после
   закрытия модалки) — ещё раз сбрасывает `addChildrenData.animalId`
   (к этому моменту уже `null` после шага 7) — идемпотентно.
9. Вкладка «Потомки» перерисовывается по новому `state.children` — B
   появляется в списке (или занимает место своей прежней версии).

### Альтернативные потоки

- **A — самец.** `newParent` перезаписывает `father` вместо `mother`;
  уже известный второй родитель A (мать, если есть) переносится в
  `motherId`/`motherBirk` потомка без изменений.
- **У A уже есть известный второй родитель** (например A — самка с уже
  известным `fatherId`/`fatherBirk` — «дед» B) — этот родитель переносится в
  `fatherId`/`fatherBirk` потомка B без изменений и без дополнительного
  обращения к репозиторию за этой записью (используется напрямую значение,
  уже присутствующее на A).
- **Потомок B ещё не синхронизирован** (`animalChild.animal.id < 0`) —
  `needsUpdate` устанавливается как `Value.absent()`, т.е. поле не
  затрагивается вовсе (остаётся как было, обычно `null`) — локальное
  животное и так целиком уйдёт на сервер при первой синхронизации.
- **Кандидат не выбран** (`child == null` или `child.animalId == null`) —
  ранний `return`; `isLoading`, выставленный в начале метода, не
  сбрасывается обратно (тот же известный дефект, что у `saveParent`, см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), «Открытые вопросы»).
  Модалка при этом всё равно закрывается — `context.pop(context)` на шаге 6
  выполняется безусловно сразу после `await`. Не `UPDATE_OK`, не входит в
  этот файл.
- **`getAnimalWithDetailsById(child.animalId!)` возвращает `null`** (запись
  B не резолвится к моменту сохранения) — ранний `return`, тот же эффект
  (`isLoading` не сбрасывается). Не входит в этот файл.
- **`update` бросает исключение** — `RESULT = UPDATE_ERROR`, не этот файл;
  покрыто отдельным тестом («известный дефект — тихий отказ»): `Talker.error`
  вызывается, `isLoading: false`, никакого сообщения пользователю не
  показывается.
- **Гипотетически: `state.animal.animal.gender` — не `maleGenderId` и не
  `femaleGenderId`.** Ни одна из двух веток не срабатывает, `newParent` (сам
  A) не попадает ни в `mother`, ни в `father` потомка B — привязка A к B не
  происходит вовсе, сохраняется только тот второй родитель, что уже был
  известен у A (если есть). На практике не воспроизводится через реальный
  UI (см. «Открытые вопросы»).

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — фигурирует
  **дважды, как два разных экземпляра одной и той же сущности**: просматриваемое
  животное A (только чтение — источник `motherId`/`motherBirk`/
  `fatherId`/`fatherBirk`/`kindId`/`gender`/`birthDate`/
  `activeAnimalIdentifications`; этим сценарием в A не пишется ни одно поле)
  и потомок B (единственная запись, которая реально изменяется — переход
  состояния, отражённый в сегменте `ENT`/`UPDATE_OK` имени файла).
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — только чтение:
  `state.animal.activeAnimalIdentifications.firstOrNull?.number` (номер A,
  используемый как `transponderId` в `newParent`) и номера идентификации
  кандидатов в автокомплите модалки (фильтрация/отображение); ни одна
  идентификация не создаётся и не меняется этим сценарием.

### Бизнес-правила

- Изменяется запись выбранного потомка B, полученная **заново** через
  `getAnimalWithDetailsById(child.animalId)`, а не переданный в
  `selectAvailableChild` объект `AnimalWithDetails` (потенциально
  устаревший к моменту сохранения).
- Пол просматриваемого животного A определяет, в `motherId` или `fatherId`
  потомка попадает id A: `female` → `motherId`, `male` → `fatherId`.
- Второй родитель потомка переносится из уже известного второго родителя A
  (`motherId`/`motherBirk` или `fatherId`/`fatherBirk` A, как есть, без
  похода в репозиторий за этой записью) — если такого второго родителя у A
  нет, соответствующее поле потомка сохраняется как `Value(null)`.
- `motherName`/`fatherName` потомка всегда перезаписываются в `null` этим
  сценарием (та же оговорка, что и в `saveParent`, зафиксированная в
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)).
- `needsUpdate` потомка взводится по признаку id **потомка** (`>= 0`), не id
  просматриваемого животного — то же деферред-sync правило, что у обычной
  правки животного (см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), «Инварианты»).
- Список `children` (потомки A) в состоянии обновляется оптимистично в
  памяти кубита — без повторного запроса `getChildrenByParentId` к БД.
- Персист — единственный вызов `AnimalsRepository.update(updatedChildAnimal)`,
  делегирующий в `dao.upd` → `BaseDao.upd` → `updateCurrent().replace(item)`
  — полная замена строки `Animal` потомка по первичному ключу `id`.
- Сохранение полностью локальное — ни один сетевой вызов не выполняется
  этим сценарием; последующая отправка `needsUpdate: true` — предмет
  отдельного sync-прохода (SYSTEM), не этого файла.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и покрыт тестами (см. «Связанные
тесты»); находки («зависший» `isLoading` при раннем `return`, теоретически
недостижимая ветка «пол A — ни male, ни female») не блокируют его
выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reproduction/presentation/reproduction_page.dart` | `ReproductionPageArguments`, `ReproductionPage.build` | CURRENT | вход на экран «Разведение» просматриваемого животного A |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionViewState._showAddChildModal`, `._syncFab` | CURRENT | FAB добавления потомка — виден только на вкладке «Потомки» и только если A не выбыло |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ReproductionChildModalWidget` (`AutoCompleteTextField.onSelected`, кнопка «Сохранить») | CURRENT | UI-модалка выбора потомка; закрывается безусловно после `await saveChild()` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | загружает `children` (текущие потомки A) и `addChildrenData.availableChildren` (кандидаты, тот же вид + дата рождения не раньше A) |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.selectAvailableChild` | CURRENT | фиксирует id выбранного кандидата в `addChildrenData` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.saveChild` | CURRENT | ядро сценария — предмет этого use-case |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState.animal`, `.children`, `.addChildrenData` | CURRENT | состояние экрана |
| `lib/pages/reproduction/data/add_parent_data.dart` | `AddChildrenData` | CURRENT | payload выбранного потомка + список кандидатов |
| `lib/models/parents.dart` | `Parents` | CURRENT | промежуточная модель родителя (mother/father/newParent), только поля `id`/`transponderId` реально персистятся |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById`, `.update`, `.getChildrenByParentId` | CURRENT | повторная выборка потомка перед сохранением; персист; загрузка списка потомков A в `load()` |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | делегирует `dao.upd` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById`, `.getChildrenByParentId` | CURRENT | повторная выборка потомка по id (включая мягко удалённых, `isNotDeleted: null`); запрос потомков по `motherId`/`fatherId` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals`, `Animal` (`motherId`/`motherBirk`/`motherName`/`fatherId`/`fatherBirk`/`fatherName`/`needsUpdate`) | CURRENT | поля, изменяемые этим сценарием — на записи потомка |
| `packages/sheep_farm_database/lib/entities/gender/gender.dart` | `Gender.maleGenderId`, `.femaleGenderId`, `.byId` | CURRENT | определяет, в `motherId` или `fatherId` потомка попадает id просматриваемого животного |

## Критерии приёмки

- По выбору кандидата B в модалке «Добавить потомка» и нажатию «Сохранить»
  выполняется ровно один вызов
  `AnimalsRepository.getAnimalWithDetailsById(B.animalId)` и ровно один
  вызов `AnimalsRepository.update`, с `Animal`, чей `id` равен `B.animalId`.
- `captured.motherId == A.animalId`, если `A.gender == Gender.femaleGenderId`;
  `captured.fatherId == A.animalId`, если `A.gender == Gender.maleGenderId`.
- Если у A уже был известен второй родитель (`motherId`/`motherBirk` или
  `fatherId`/`fatherBirk`), это же значение (`id` и/или `birk`) присутствует
  у потомка после сохранения на том поле, которое пол A не перезаписывает.
- `captured.needsUpdate == true` тогда и только тогда, когда id потомка B
  (не A) `>= 0`; при `B.id < 0` — `needsUpdate` не выставлен (`isNull`).
- `captured.motherName == null` и `captured.fatherName == null` после
  сохранения, независимо от того, что было записано раньше.
- `state.children` после `saveChild()` содержит ровно одну запись с
  `animalId == B.animalId` (обновлённую версию), без дублей.
- `state.isLoading == false` после успешного сохранения.

## Связанные тесты

- `test/pages/reproduction_cubit_test.dart`, group `'UC-117 —
  ReproductionCubit.saveChild'` (старая нумерация, переименуется отдельным
  контролируемым проходом — не трогать сейчас) — 1 тест: `'выбранный
  ребёнок синхронизирован (id>=0) -> его Animal.motherId/fatherId
  обновлены, needsUpdate:true'` — просматриваемое животное female (`id=5`),
  потомок male (`id=20`) → `captured.motherId == 5`, `captured.needsUpdate
  == true`. Прямое покрытие основного потока этого файла.
- `test/pages/reproduction_cubit_test.dart`, group `'UC-117 —
  ReproductionCubit.saveChild — дополнительные ветки'` — 2 теста:
  - `'текущее животное — самец -> ребёнку проставляется fatherId текущего
    животного'` — просматриваемое животное male (`id=5`) →
    `captured.fatherId == 5`. Покрывает бизнес-правило «пол A определяет
    motherId/fatherId».
  - `'переносит уже известного отца текущего (материнского) животного в
    fatherId ребёнка'` — A female (`id=5`, `fatherId=99`,
    `fatherBirk='GRANDPA'`) → `captured.motherId == 5` (сам A),
    `captured.fatherId == 99` (перенесённый «дед»). Покрывает бизнес-правило
    «перенос второго известного родителя».
- Группа `'UC-118 — ReproductionCubit.saveChild ERROR (известный дефект —
  тихий отказ)'` (тот же файл) в этот use-case **не входит** — покрывает
  ветку исключения при `update` (`RESULT = UPDATE_ERROR`, тихий отказ,
  `isLoading: false`).
- **TBD — теста нет** на ветку раннего `return` при `animalChild == null`
  (`getAnimalWithDetailsById(child.animalId)` возвращает `null`) — ни один
  существующий тест не мокает этот случай отдельно.
- **TBD — теста нет** на гипотетическую ветку «пол A — не male и не
  female» (см. «Открытые вопросы») — `Gender` на практике допускает только
  два значения, ветка не воспроизведена.

## Открытые вопросы и ограничения

- **`isLoading` остаётся `true` навсегда при раннем `return`** (ни выбранный
  потомок не задан, ни `animalChild` не резолвится) — тот же известный
  дефект, что и в `saveParent` (см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), «НАХОДКА»); UI не
  показывает пользователю никакой обратной связи об ошибке. Модалка при
  этом всё равно закрывается безусловно (`context.pop(context)` сразу после
  `await saveChild()`), поэтому пользователь физически не видит «зависшую»
  загрузку — но состояние `ReproductionCubit` остаётся `isLoading: true` до
  следующего `emit` (например следующего `load()`).
- **Гипотетическая ветка «пол просматриваемого животного — не male и не
  female»** технически возможна на уровне типов (`Animal.gender` —
  произвольный `int` в БД), но не воспроизводима через реальный UI
  (`Gender.valuesForAnimal` ограничивает выбор при регистрации/редактировании
  двумя значениями); в этой ветке `newParent` теряется — привязка A к
  потомку не происходит, сохраняется только уже известный второй родитель A
  (если есть). Не разбирается глубже.
- **Список `availableChildren` (кандидаты в потомки) грузится один раз** при
  открытии экрана (`ReproductionCubit.load`) и не обновляется, пока экран
  открыт — если новый подходящий кандидат регистрируется параллельно
  (другим устройством/сессией), он не появится в автокомплите без
  повторного захода на экран. Не разбирается глубже — это про доступность
  кандидата, а не про сам сценарий сохранения.
- **Второй родитель, «унаследованный» от A, копируется по значению**
  (`id`/`birk`) в момент сохранения — если впоследствии запись этого
  родителя изменится, потомок B не получит обновление автоматически (нет
  связи с каскадом, кроме буквального совпадения значений на момент
  записи). Тот же паттерн, что и у `saveParent`
  ([EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md)).
