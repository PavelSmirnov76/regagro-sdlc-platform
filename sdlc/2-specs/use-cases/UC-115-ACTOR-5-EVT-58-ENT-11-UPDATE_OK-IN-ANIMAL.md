# UC-115 — Пользователь привязывает родителя (мать/отца) на экране «Разведение», сохранение успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь на экране «Разведение» карточки животного открывает форму
матери или отца, выбирает кандидата (из списка уже зарегистрированных
животных подходящего вида/возраста) либо вводит номер вручную без привязки к
записи, и сохраняет — `ReproductionCubit.saveParent` обновляет
`motherId`/`motherBirk` либо `fatherId`/`fatherBirk` просматриваемого
животного, ранее известный второй родитель остаётся как был, флаг
`needsUpdate` взводится по тому же признаку, что и обычная правка животного
([EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково; кнопка «Разведение» в панели
действий карточки животного (`_AnimalCardToolbarActions`) отрисовывается
безусловно — не зависит ни от знака `animal.animal.id` (локальное/
синхронизированное животное), ни от `isDisposed` (выбывшее животное). Вход в
сценарий обусловлен только тем, что просматриваемое животное вообще
существует как открытая карточка.

## CURRENT

### Основной поток

1. Пользователь на `AnimalCardPage` нажимает действие «Разведение»
   (`Assets.reproduction`) → `context.pushNamed2(Routes.reproduction, extra:
   ReproductionPageArguments(animal: animalWithDetails))`.
2. `ReproductionPage.build` читает аргумент через
   `GoRouterState.of(context).getExtraByName<ReproductionPageArguments>` и
   рендерит `ReproductionView(animal: animal)`.
3. `ReproductionView.build` создаёт `BlocProvider<ReproductionCubit>(create:
   (_) => ReproductionCubit(animal)..load())`.
4. `ReproductionCubit.load()` эмитит `isLoading: true`, затем:
   - строит `parents` через `Parents.fromInlineFields(motherId, fatherId,
     motherBirk, fatherBirk, motherName, fatherName, kindId)` из полей,
     уже лежащих на `state.animal.animal`;
   - если `motherId`/`fatherId` заданы — дополнительно перечитывает
     соответствующее животное через
     `_animalsRepository.getAnimalWithDetailsById(id)` и, если оно
     найдено, перезаписывает `motherBirk`/`motherName` (или
     `fatherBirk`/`fatherName`) актуальными значениями с той записи —
     то есть отображаемые бирка/кличка родителя берутся из **чужой**,
     свежепрочитанной записи `Animal`, а не только из инлайн-копии на
     самом просматриваемом животном;
   - грузит потомков — `_animalsRepository.getChildrenByParentId(animalId)`;
   - грузит кандидатов в родители/потомки —
     `_animalsRepository.getAllAnimalsWithDetailsByFilters(kindIds:
     [animal.kind.id], birthDateRange: DateTimeRange(start:
     DateTime(1900,1,1), end: animal.birthDate), isShowRemoteSource: null)`
     для родителей (диапазон дат — от 1900 года до дня рождения самого
     животного включительно) и симметрично `birthDateRange:
     DateTimeRange(start: animal.birthDate, end: DateTime.now())` для
     потомков. `isShowRemoteSource: null` явно отключает фильтр по
     источнику записи — в отличие от дефолта самого репозитория
     (`isShowRemoteSource = false`, только записи без `source`), сюда
     попадают кандидаты независимо от того, создана запись локально или
     подтянута с сервера;
   - эмитит `state.copyWith(parents:, children:, isLoading: false,
     addPparentsData: AddParentData(availableParents: ...),
     addChildrenData: AddChildrenData(availableChildren: ...))`.
5. `ReproductionFastFilterWidget` открывается на `ReproductionFilter.parents`
   по умолчанию; `ParentsWidget` рендерит карточки матери/отца, вычисляя
   `mother`/`father` из `state.parents?.parents?.firstWhereOrNull(gender.id ==
   Gender.femaleGenderId / maleGenderId)`.
6. Пользователь нажимает на карточку матери (или отца) →
   `onParentTap(mother ?? Parents(gender: Gender.female))` (симметрично
   `Gender.male` для отца) → `cubit.selectParentForEdit(parent)`:
   - если `parent.id != null` (родитель уже привязан) — делегирует в
     `selectAvailableParent(parent.id!)`: читает
     `_animalsRepository.getAnimalWithDetailsById(animalId)`; если найдено —
     эмитит `addPparentsData.copyWith(animalId: parent.animal.id,
     transponderId: parent.animalIdentifications.firstWhere((e) =>
     e.markerTypeId == Constants.TransponderMarkerTypeId).number, birthDate:
     parent.birthDate, gender: Gender.byId(parent.animal.gender), kindId:
     parent.animal.kindId)` — **`firstWhere` без `orElse`** (см.
     «Альтернативные потоки» — баг, ветка успеха этого шага требует, чтобы у
     найденного животного была хотя бы одна идентификация с
     `markerTypeId == Constants.TransponderMarkerTypeId`);
   - если `parent.id == null` (слот пуст) — `changeParentGender(parent.gender
     ?? Gender.female)` затем `changeParentKindId(state.animal.kind?.id ??
     0)`; оба сеттера также сбрасывают `animalId: null` в `addPparentsData`.
7. Открывается `showModalBottomSheet(... builder: (context) =>
   ReproductionParentModalWidget(cubit: cubit))`. Форма показывает
   `AutoCompleteTextField<AnimalWithDetails>` (контроллер инициализирован
   из `state.addPparentsData?.transponderId`) и `RDatePicker`
   (`disabled: state.addPparentsData?.animalId != null` — визуально
   заблокирован, если уже выбран конкретный кандидат из списка).
8. Пользователь заполняет форму одним из двух способов:
   - **выбор из списка**: подсказки строятся как
     `state.addPparentsData?.getAvailableParentsByGender(state.addPparentsData?.gender?.id
     ?? Gender.femaleGenderId)`, дополнительно отфильтрованные по вхождению
     введённого текста в номер идентификации кандидата; выбор вызывает
     `cubit.selectAvailableParent(animal.animalId)` (тот же метод, что и в
     шаге 6) и локально проставляет текст контроллера номером активного
     транспондера кандидата;
   - **ручной ввод без привязки к записи** («не зарегистрировано», R39):
     `onChanged` вызывает `cubit.changeParentTransponderId(value)`, который
     ставит `addPparentsData.copyWith(animalId: null, transponderId:
     value)` — `animalId` явно обнуляется, даже если до этого был выбран
     кандидат из списка.
   - Дату рождения можно поменять через `RDatePicker` →
     `changeParentBirthDate(date)` (эффект виден только когда поле не
     задизейблено, т.е. `animalId == null`; сам метод `changeParentBirthDate`
     такого условия не проверяет и всегда обновит `addPparentsData`, если
     будет вызван).
9. Пользователь нажимает «Сохранить» (`BlackCircleButton`, FAB) → `await
   context.read<ReproductionCubit>().saveParent()`, затем **безусловно**
   (`if (context.mounted) context.pop(context)`, независимо от того, бросил
   ли `saveParent` исключение внутри себя) — модальное окно закрывается.
10. `saveParent()`:
    - эмитит `isLoading: true`; `parent = state.addPparentsData` — не
      `null` на практике, поскольку `load()` уже успел его заполнить
      (см. «Альтернативные потоки» про теоретический ранний `return`);
    - читает `mother`/`father` из **уже загруженного** `state.parents`
      (`parents?.parents?.firstWhereOrNull(gender.id ==
      Gender.femaleGenderId / maleGenderId)`) — не перечитывает их из БД
      заново на этом шаге;
    - строит `newParent = Parents(id: parent.animalId, transponderId:
      parent.transponderId, birthDate: parent.birthDate, gender:
      parent.gender, kindId: parent.kindId)` из только что заполненного
      `addPparentsData`;
    - если `parent.gender?.id == Gender.femaleGenderId` → `mother =
      newParent`; если `== Gender.maleGenderId` → `father = newParent` —
      заменяется **только** слот, соответствующий полу выбранного
      кандидата; второй (не редактируемый в этот раз) слот остаётся тем,
      что был прочитан из `state.parents` на предыдущем шаге;
    - собирает `updatedAnimal = state.animal.animal.copyWith(motherId:
      Value(mother?.id), motherBirk: Value(mother?.transponderId),
      motherName: const Value(null), fatherId: Value(father?.id),
      fatherBirk: Value(father?.transponderId), fatherName: const
      Value(null), needsUpdate: state.animal.animal.id >= 0 ? const
      Value(true) : const Value.absent())` — `motherName`/`fatherName`
      **всегда** обнуляются в `null`, даже для слота, который в этот раз не
      менялся;
    - вызывает `await _animalsRepository.update(updatedAnimal)` —
      `AnimalsRepository` наследует `BaseRepository<AnimalsDao, Animal,
      $AnimalsTable>.update`, который делегирует в `dao.upd(item)` →
      `updateCurrent().replace(item)` (полная замена строки по `id`, без
      сетевого запроса); **возвращаемое `bool` не проверяется и не
      используется для ветвления** — в отличие от аналогичного сохранения
      в REG (`AnimalEditBloc.on<AnimalEditEventSave>`, см.
      [UC-48](UC-48-ACTOR-5-EVT-24-ENT-11-UPDATE_OK-IN-ANIMAL.md)), которое
      проверяет `ok` перед тем, как показать сообщение об успехе;
    - собирает `updatedParentsList = [if (mother != null) mother, if (father
      != null) father]`;
    - эмитит `state.copyWith(isLoading: false, animal:
      state.animal.copyWith(animal: updatedAnimal), parents:
      updatedParentsList.isEmpty ? null : Parents(parents:
      updatedParentsList), addPparentsData: AddParentData(availableParents:
      state.addPparentsData!.availableParents))` — `addPparentsData`
      возвращается к пустой форме (тот же эффект, что у
      `clearParentData()`), список кандидатов сохраняется как был.
11. После закрытия модального окна (шаг 9) срабатывает `.then((value) async
    { await cubit.clearParentData(); })` из точки открытия — повторно
    приводит `addPparentsData` к `AddParentData(availableParents: ...)`
    (эффект идемпотентен относительно уже сделанного на шаге 10).
12. `ParentsWidget` перерисовывается из обновлённого `state.parents` —
    карточка матери/отца показывает бирку и дату рождения вместо плейсхолдера
    «дата отсутствует», иконка меняется с `Assets.plus` на
    `Assets.pencilSquare`.
13. Животное с `needsUpdate == true` (если оно уже было синхронизировано)
    остаётся в локальной БД; фактическая отправка правки на сервер — тот же
    отложенный путь, что у REG
    ([EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)), не часть
    этого сценария.

### Альтернативные потоки

- **БАГ — `selectAvailableParent` без `orElse` бросает необработанный
  `StateError`, если у выбранного кандидата нет идентификации-транспондера.**
  `parent.animalIdentifications.firstWhere((e) => e.markerTypeId ==
  Constants.TransponderMarkerTypeId)` не имеет `orElse:`; если у кандидата
  нет ни одной идентификации с этим `markerTypeId` — исключение бросается
  **до** `emit()`, `addPparentsData` не меняется (выбор молча не
  применяется), а сам вызов происходит либо из `selectParentForEdit`
  (открытие формы уже привязанного родителя), либо из `onSelected`
  `AutoCompleteTextField` (выбор кандидата из подсказок) — ни один из двух
  сайтов вызова не оборачивает `await cubit.selectAvailableParent(...)` в
  `try`/`catch`, так что исключение всплывает необработанным в дереве
  виджета. Практическое следствие: кандидата без идентификации-транспондера
  нельзя привязать через выбор из списка вообще — эта ветка `EVT-58`
  недостижима успешно для таких животных; единственный обходной путь —
  ручной ввод номера (шаг 8, второй способ), который вообще не читает
  идентификации кандидата.
- **Ручной ввод номера без выбора записи («не зарегистрировано», R39).**
  `changeParentTransponderId` ставит `animalId: null` — на шаге сохранения
  `newParent.id == null`, поэтому `mother?.id`/`father?.id` (а с ними
  `motherId`/`fatherId` на `Animal`) остаются `null`, но
  `motherBirk`/`fatherBirk` заполняется введённым текстом — тот же
  `RESULT = UPDATE_OK`, просто без ссылки на существующую запись
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) для этого родителя (см.
  инвариант в [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) — схема не
  различает «не зарегистрировано» от «зарегистрировано, но пока не
  найдено»).
- **`update()` возвращает `false` либо сама сборка бросает исключение** —
  перехватывается общим `try { ... } catch (e) { getIt<Talker>().error(e);
  emit(state.copyWith(isLoading: false)); }`: пользователю не показывается
  никакое сообщение (ни снекбар, ни диалог) в обоих случаях — ни при успехе,
  ни при этой ошибке `ReproductionParentModalWidget` не слушает состояние
  кубита для сообщений (в отличие от `AnimalEditPage`/`AnimalEditMessage` в
  REG). Хуже того, кнопка «Сохранить» безусловно вызывает `context.pop`
  сразу после `await saveParent()` (шаг 9) — с точки зрения пользователя
  успех и эта ошибка **выглядят одинаково**: модальное окно просто
  закрывается. Этот путь — отдельный `RESULT = UPDATE_ERROR`, не описанный
  этим файлом.
- **`parent == null` на входе в `saveParent`.** Теоретический ранний
  `return` — `isLoading`, выставленный в начале метода, не сбрасывается
  обратно (тот же паттерн зафиксирован для `saveChild` в
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), «НАХОДКА»). На практике
  недостижимо в рамках описанной здесь навигации — `load()` всегда
  заполняет `addPparentsData` до того, как пользователь может нажать
  «Сохранить».
- **НАХОДКА (обнаружено при чтении `load()` для этого файла, не
  зафиксировано ранее в [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)) —
  просматриваемое животное может попасть в список кандидатов на
  собственного родителя.** `getAllAnimalsWithDetailsByFilters` внутри
  `load()` не исключает `state.animal.animalId` ни из `availableParents`,
  ни из `availableChildren` (нет параметра `ids`/анти-фильтра по id); для
  родителей верхняя граница диапазона дат — `birthDateRange.end =
  state.animal.birthDate` включительно (`aAlias.birthDate.isSmallerOrEqualValue`
  в `AnimalsDao.getAllAnimalsWithDetailsByFilters`), а `kindIds` совпадает с
  собственным видом животного — оба условия тривиально выполняются для
  самого себя. Если пол просматриваемого животного совпадает с полом
  редактируемого слота (мужской для формы отца, женский — для формы
  матери), само животное попадёт в `getAvailableParentsByGender(...)` и
  теоретически может быть выбрано как собственный родитель через
  автокомплит. Не проверено тестом ни в одну, ни в другую сторону.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность
  сегмента `ENT` в id, задействована **двумя разными экземплярами записи**:
  1) просматриваемое животное — реально обновляемая запись
     (`motherId`/`motherBirk`/`motherName` либо
     `fatherId`/`fatherBirk`/`fatherName`, `needsUpdate`);
  2) выбранный кандидат в родители — **только читается**
     (`getAnimalWithDetailsById` в `selectAvailableParent`/`load()`), его
     собственная запись `Animal` этим сценарием не меняется — из неё берутся
     `transponderId`/`birthDate`/`gender`/`kindId` для заполнения формы.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается у кандидата в родители для поиска
  активного транспондера (`selectAvailableParent`, источник бага
  `firstWhere` без `orElse`) и у самого просматриваемого животного/списка
  кандидатов для отображения номеров в карточках и подсказках автокомплита;
  этим сценарием не создаётся, не меняется и не удаляется.

### Бизнес-правила

- **`needsUpdate: true` выставляется только для уже синхронизированного
  животного (`state.animal.animal.id >= 0`)** — `Value.absent()` для
  локального (`id < 0`), та же схема, что у `AnimalEditBloc` (REG, см.
  [UC-48](UC-48-ACTOR-5-EVT-24-ENT-11-UPDATE_OK-IN-ANIMAL.md)); REPRO не
  заводит собственной sync-машинерии, переиспользует ровно эту.
- **Заменяется только слот, соответствующий полу выбранного кандидата**;
  второй слот берётся из уже загруженного `state.parents`, не
  перечитывается из БД в момент сохранения — если реальная запись второго
  родителя изменилась в БД с момента последнего `load()` этого экрана
  (например, отредактирована с другого устройства и синхронизирована), эта
  устаревшая копия всё равно будет записана обратно в `updatedAnimal`.
- **`motherName`/`fatherName` всегда обнуляются в `null` этим сценарием**,
  независимо от того, какой слот менялся — REPRO не пишет отображаемое имя
  родителя ни при каком раскладе (см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)).
- **`AnimalsRepository.update` → `dao.upd`** — полная замена строки Drift по
  `id`, не частичный patch: любое поле `Animal`, не выставленное явно в
  `copyWith` внутри `saveParent`, сохраняется тем, что уже лежало в
  `state.animal.animal` на момент вызова.
- **Возврат `update()` не проверяется** — успешный `emit` происходит
  безусловно, пока не было выброшено исключение; это отличает REPRO от
  аналогичного сохранения REG (`AnimalEditBloc`), которое ветвится по
  булеву результату записи.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Основной поток (выбор кандидата с транспондер-идентификацией или ручной ввод
номера, сохранение) полностью реализован и достижим. Единственная
заблокированная на практике ветка — выбор кандидата **без**
идентификации-транспондера (см. «Альтернативные потоки», `StateError` без
`orElse`) — это баг, а не отсутствующая функциональность, отдельного TBD не
заводит.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_AnimalCardToolbarActions.build` | CURRENT | точка входа — кнопка «Разведение» в панели действий карточки животного, отрисовывается безусловно |
| `lib/pages/routes.dart` | `Routes.reproduction` | CURRENT | маршрут экрана «Разведение» |
| `lib/pages/reproduction/presentation/reproduction_page.dart` | `ReproductionPage.build`, `ReproductionPageArguments` | CURRENT | читает аргумент из `GoRouterState`, рендерит `ReproductionView` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ReproductionView.build` | CURRENT | создаёт `ReproductionCubit`, вызывает `load()` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ParentsWidget.build` | CURRENT | карточки матери/отца, `onParentTap` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ReproductionParentModalWidget` (`_ReproductionParentModalWidgetState.build`) | CURRENT | bottom sheet формы родителя: автокомплит номера, `RDatePicker`, кнопка «Сохранить» |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | загрузка `parents`/`children`/списков кандидатов, `isShowRemoteSource: null` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.selectParentForEdit` | CURRENT | делегирование в `selectAvailableParent` либо предзаполнение `gender`/`kindId` для пустого слота |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.selectAvailableParent` | CURRENT (баг) | `firstWhere` без `orElse` по `Constants.TransponderMarkerTypeId` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.changeParentGender`, `changeParentKindId`, `changeParentTransponderId`, `changeParentBirthDate` | CURRENT | сеттеры формы кандидата |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.saveParent` | CURRENT | основной метод сценария |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.clearParentData` | CURRENT | сброс формы после закрытия sheet |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState` | CURRENT | freezed-состояние экрана |
| `lib/pages/reproduction/data/add_parent_data.dart` | `AddParentData`, `AddParentDataX.getAvailableParentsByGender` | CURRENT | форма выбора родителя + фильтр кандидатов по полу |
| `lib/models/parents.dart` | `Parents`, `Parents.fromInlineFields` | CURRENT | модель родителя (`GenealogyAnimal`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById`, `getAllAnimalsWithDetailsByFilters`, `getChildrenByParentId` | CURRENT | чтение животного/кандидатов/потомков |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (наследует `BaseRepository<AnimalsDao, Animal, $AnimalsTable>.update`) | CURRENT | делегирует в `dao.upd`, без сетевого вызова |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` — возвращаемый `bool` не проверяется вызывающим кодом `saveParent` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | источник списка кандидатов, без исключения `id` просматриваемого животного |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animal` (`motherId`/`motherBirk`/`motherName`/`fatherId`/`fatherBirk`/`fatherName`/`needsUpdate`) | CURRENT | поля таблицы, изменяемые этим сценарием |
| `lib/constants.dart` | `Constants.TransponderMarkerTypeId` | CURRENT | значение `3`, используется в `firstWhere` без `orElse` (баг) |
| `packages/sheep_farm_database/lib/entities/gender/gender.dart` | `Gender`, `Gender.femaleGenderId`/`maleGenderId`, `Gender.byId` | CURRENT | определение пола слота/кандидата |

## Критерии приёмки

- Открытие карточки матери/отца через `ParentsWidget.onParentTap` вызывает
  `selectParentForEdit`, который либо подтягивает данные уже привязанного
  родителя (`selectAvailableParent`), либо предзаполняет `gender`/`kindId`
  для пустого слота.
- Выбор кандидата с идентификацией-транспондером из автокомплита заполняет
  `addPparentsData` (`animalId`/`transponderId`/`birthDate`/`gender`/`kindId`)
  без исключения.
- Ручной ввод номера без выбора кандидата оставляет `animalId == null` и
  заполняет только `transponderId`.
- `saveParent` вызывает `AnimalsRepository.update` ровно один раз с копией
  `Animal`, где изменён только слот, соответствующий полу выбранного
  кандидата (`motherId`/`motherBirk` либо `fatherId`/`fatherBirk`), второй
  слот сохранён из ранее загруженных `state.parents`, `motherName`/
  `fatherName` — всегда `null`, `needsUpdate == true` тогда и только тогда,
  когда исходный `id >= 0`.
- После успешного сохранения `state.parents` содержит обновлённый список
  (мать/отец), `ParentsWidget` показывает бирку и дату рождения вместо
  плейсхолдера.
- Кандидат без идентификации-транспондера не может быть выбран через список
  (бросает `StateError`, `addPparentsData` не меняется) — задокументированное
  ограничение, не критерий провала конкретно этого успешного сценария.

## Связанные тесты

`test/pages/reproduction_cubit_test.dart`:

- `group('UC-115 — ReproductionCubit.saveParent')` (якорь под старым
  номером — переименование в `UC-115` отдельным проходом, не входит в этот
  документирующий файл):
  - `'синхронизированное животное (id>=0) -> update с needsUpdate:true,
    motherBirk из выбранного родителя'` — основной поток этого файла:
    `id >= 0` → `update()` вызван с `motherBirk == 'T-1'` и `needsUpdate ==
    true`.
  - `'локальное животное (id<0) -> needsUpdate не трогается (Value.absent ->
    остаётся как было, null)'` — та же ветка для `id < 0`: `needsUpdate ==
    null` (не тронут).
- `group('UC-115 — ReproductionCubit.saveParent — дополнительные ветки')`:
  - `'обновление только матери сохраняет ранее известного отца'` — покрывает
    правило «второй слот берётся из `state.parents`, не перечитывается из
    БД»: `captured.fatherBirk == 'F-OLD'` при редактировании только матери.
- Смежные, но не анкорованные под `UC-115` (описательные названия,
  `grep -r "UC-115" test/` их не находит):
  - `group('ReproductionCubit.selectParentForEdit')` — покрывает оба ветвления
    шага 6 основного потока (делегирование в `selectAvailableParent` для
    уже привязанного родителя; предзаполнение `gender`/`kindId` для пустого
    слота, включая дефолт `Gender.female`, если пол не передан).
  - `group('ReproductionCubit.selectAvailableParent')`, тест `'животное
    найдено, есть транспондер -> addPparentsData заполняется из него'` —
    покрывает успешную ветку выбора кандидата (шаг 8, первый способ).
  - `group('ReproductionCubit.selectAvailableParent')`, тест `'БАГ
    (reproduction_cubit.dart:122-126): животное найдено, но без
    транспондер-идентификации -> firstWhere без orElse бросает
    необработанный StateError'` — покрывает найденный баг из «Альтернативные
    потоки» (уже задокументирован тестом на момент написания этого файла).

## Открытые вопросы и ограничения

- **Тесты не анкорованы под `UC-115`.** Существующие группы называются
  `'UC-115 — ReproductionCubit.saveParent'` и `'UC-115 — ReproductionCubit.saveParent
  — дополнительные ветки'` (старый номер) плюс несколько описательных групп
  без какого-либо `UC-{id}` (`selectParentForEdit`,
  `selectAvailableParent`) — `grep -r "UC-115" test/` сейчас ничего не
  находит. Переименование анкоров — отдельный проход, не в рамках этого
  файла.
- **Успех и локальная/сетевая ошибка сохранения неразличимы для
  пользователя.** Ни один путь (`saveParent` успешно завершился /
  `update()` вернул `false` / поймано исключение) не показывает снекбар или
  иное сообщение — `ReproductionParentModalWidget` не слушает состояние
  кубита для отображения ошибок, а кнопка «Сохранить» безусловно закрывает
  модальное окно сразу после `await saveParent()`, независимо от исхода.
- **Второй (не редактируемый в этот раз) родитель пишется из потенциально
  устаревшего `state.parents`, не перечитывается из БД в момент
  сохранения.** Если сама запись второго родителя была изменена в БД между
  `load()` этого экрана и нажатием «Сохранить» (правка с другого экрана,
  синхронизация с сервера), эта устаревшая копия попадёт в
  `updatedAnimal.motherBirk`/`fatherBirk`.
- **Кандидат-«самому себе».** `load()` не исключает id просматриваемого
  животного из списков кандидатов ни в родители, ни в потомки — граница
  диапазона дат для родителей (`birthDateRange.end == animal.birthDate`,
  включительно) и совпадающий `kindId` тривиально выполняются для самого
  себя; при совпадении пола животное теоретически может появиться в
  собственном автокомплите как кандидат в родители. Обнаружено при чтении
  кода для этого файла, не покрыто ни одним существующим тестом — ни как
  подтверждённый баг, ни как проверенное ограничение.
- **`selectAvailableParent`/`selectParentForEdit` без `try`/`catch` на
  сайтах вызова.** И `onParentTap` (`reproduction_view.dart`), и
  `onSelected` автокомплита вызывают `await
  cubit.selectAvailableParent(...)` без оборачивания — `StateError`,
  описанный выше, всплывает необработанным в дереве виджета, а не
  превращается в контролируемое состояние ошибки экрана.
