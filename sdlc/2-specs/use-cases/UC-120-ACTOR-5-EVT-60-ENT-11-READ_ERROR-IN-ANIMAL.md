# UC-120 — Просмотр родословной («Разведение») животного: репозиторий бросает исключение, `ReproductionCubit.load` не перехватывает его, а экран вообще не проверяет `isLoading`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же триггер, что описан у [EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md)
(`ReproductionCubit.load`) — пользователь открывает вкладку «Разведение»
карточки животного (вкладки «Родители»/«Потомство»), — но один из
репозиторных вызовов, к которым обращается `load()`
(`AnimalsRepository.getAnimalWithDetailsById`, `getChildrenByParentId`,
`getAllAnimalsWithDetailsByFilters`), бросает исключение. Проверено чтением
`lib/pages/reproduction/cubit/reproduction_cubit.dart` целиком: **у
`ReproductionCubit.load` нет вообще никакого `try/catch`** вокруг тела метода
— тот же класс дефекта, что уже задокументирован для
`AnimalWeighingsCubit.load`/`loadNotSync`
([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md),
[UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md)).

Но здесь есть нюанс, отсутствующий у WEIGH: `ReproductionState` — не
freezed-union с вариантами `loading`/`loaded` (как `AnimalWeighingsState`), а
один-единственный freezed-класс с булевым полем `isLoading`. Экран
(`_ReproductionViewState.build`, `ParentsWidget.build`, `ChildrenWidget.build`
— все три проверены чтением `lib/pages/reproduction/presentation/widgets/
reproduction_view.dart` целиком) **ни разу не читает `state.isLoading`** —
`grep -rn ".isLoading" lib/pages/reproduction/presentation/` не находит ни
одного вхождения. Поэтому при падении `load()` пользователь не видит вечный
спиннер (как в WEIGH) — он видит полностью построенный, интерактивный экран,
который выглядит как «у животного нет ни матери, ни отца, ни потомства»,
неотличимо от животного, у которого этих данных действительно нет.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `ReproductionCubit` объявляет
только одну зависимость (`_animalsRepository = getIt<AnimalsRepository>()`)
и не использует `AuthRepository` ни в одном методе, включая `load`.

## CURRENT

### Основной поток

1. Пользователь на карточке животного нажимает пункт тулбара «Разведение»
   (`_AnimalCardToolbarAction(icon: Assets.reproduction, label:
   l10n.reproduction, onTap: () => context.pushNamed2(Routes.reproduction,
   extra: ReproductionPageArguments(animal: animalWithDetails)))`,
   `lib/pages/animal_card/animal_card_page.dart`). Животное уже загружено —
   `animalWithDetails` берётся из уже открытой карточки, не запрашивается
   заново на этом шаге.
2. `ReproductionPage.build` (`lib/pages/reproduction/presentation/
   reproduction_page.dart`) достаёт `animal` из `GoRouterState.of(context)
   .getExtraByName<ReproductionPageArguments>(Routes.reproduction)` и строит
   `ReproductionView(animal: animal)`.
3. `_ReproductionViewState.build` (`lib/pages/reproduction/presentation/
   widgets/reproduction_view.dart`) строит `BlocProvider<ReproductionCubit>(
   create: (context) { final cubit = ReproductionCubit(widget.animal)..load();
   _reproductionCubit = cubit; ...; return cubit; })`. Каскад `..load()`
   возвращает сам объект кубита (не `Future`, который вернул бы вызов
   `load()`) — `create` завершается синхронно и штатно независимо от исхода
   асинхронного `load()`.
4. `ReproductionCubit.load()`:
   ```dart
   Future<void> load() async {
     emit(state.copyWith(isLoading: true));
     final animalData = state.animal.animal;
     ...
     if (state.animal.motherId != null) {
       final motherAnimal = await _animalsRepository.getAnimalWithDetailsById(
         state.animal.motherId!,
       );
       ...
     }
     if (state.animal.fatherId != null) {
       final fatherAnimal = await _animalsRepository.getAnimalWithDetailsById(
         state.animal.fatherId!,
       );
       ...
     }
     final parents = Parents.fromInlineFields(...);
     final children = await _animalsRepository.getChildrenByParentId(
       state.animal.animalId,
     );
     final availableParents = await _animalsRepository
         .getAllAnimalsWithDetailsByFilters(
           kindIds: [state.animal.kind!.id],
           birthDateRange: DateTimeRange(start: DateTime(1900, 1, 1), end: state.animal.birthDate!),
           isShowRemoteSource: null,
         );
     final availableChildren = await _animalsRepository
         .getAllAnimalsWithDetailsByFilters(
           kindIds: [state.animal.kind!.id],
           birthDateRange: DateTimeRange(start: state.animal.birthDate!, end: DateTime.now()),
           isShowRemoteSource: null,
         );
     emit(state.copyWith(parents: parents, children: children, isLoading: false,
       addPparentsData: AddParentData(availableParents: availableParents),
       addChildrenData: AddChildrenData(availableChildren: availableChildren)));
   }
   ```
   Первая строка (`emit(state.copyWith(isLoading: true))`) выполняется
   синхронно, до первой строки, которая может бросить исключение — состояние
   кубита переходит в `isLoading: true` гарантированно, ещё внутри
   синхронной части `create`-колбэка (см. шаг 3), до первой `await`-точки
   приостановки.
5. Метод обращается к репозиторию последовательно (`await` один за другим,
   не `Future.wait`), в этом порядке: `getAnimalWithDetailsById(motherId)`
   (условно, только если `motherId != null`), `getAnimalWithDetailsById(fatherId)`
   (условно, только если `fatherId != null`), `getChildrenByParentId(animalId)`
   (безусловно), `getAllAnimalsWithDetailsByFilters(...)` для
   `availableParents` (безусловно), `getAllAnimalsWithDetailsByFilters(...)`
   для `availableChildren` (безусловно). Один из этих вызовов бросает
   исключение. Метод целиком не обёрнут ни в один `try/catch` — исключение
   останавливает выполнение немедленно в точке броска; ни один из вызовов,
   идущих в коде после упавшего, не происходит.
6. Финальный `emit(state.copyWith(parents: ..., children: ..., isLoading:
   false, addPparentsData: ..., addChildrenData: ...))` не выполняется.
   Состояние кубита (`cubit.state`) остаётся ровно тем, что было выставлено
   на шаге 4 — `isLoading: true`, а `parents`/`children`/`addPparentsData`/
   `addChildrenData` остаются теми значениями, что были на входе в этот вызов
   `load()` (при первом, единственном вызове сразу после конструктора — это
   значения по умолчанию из `ReproductionState`: `parents: null`, `children:
   []`, `addPparentsData: null`, `addChildrenData: null` — в `load()` нет ни
   одного промежуточного `emit` между началом и не достигнутым концом).
   `isLoading` внутри кубита застревает в `true` навсегда, если ничто не
   вызовет `load()` заново.
7. `Future<void>`, возвращаемый вызовом `load()`, отклоняется этим же
   исключением. Поскольку на шаге 3 он вызван каскадом (`..load()`) и нигде
   не awaited и не имеет `.catchError`, это необработанное отклонение
   `Future` («fire-and-forget») — оно не долетает ни до `BlocProvider`, ни до
   `BlocConsumer`, ни до какого-либо явного обработчика приложения.
8. `lib/main.dart`: `main()` вызывает `runApp(const MyApp())` напрямую;
   строка `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const
   MyApp()), (error, stack) { getIt<Talker>().handle(error, stack); });`
   закомментирована целиком — приложение не оборачивает своё выполнение в
   `runZonedGuarded` с собственным обработчиком. Отклонение из шага 7 не
   попадает ни в `Talker`, ни в какой-либо иной явный error-handler
   приложения.
9. **Ключевое отличие от WEIGH.** `_ReproductionViewState.build`'s
   `BlocConsumer<ReproductionCubit, ReproductionState>` не гейтит `builder`
   по `state.isLoading` вообще — он всегда строит `Scaffold` с
   `ReproductionFastFilterWidget` и, в зависимости от
   `state.reproductionFilter` (по умолчанию `ReproductionFilter.parents`),
   либо `ParentsWidget(state: state, ...)`, либо `ChildrenWidget(state:
   state)`. Экран уже был построен на шаге 3 (виджет-дерево не зависит от
   исхода `load()`), и остаётся полностью интерактивным независимо от того,
   упал ли `load()`.
10. `ParentsWidget.build` вычисляет `mother`/`father` из
    `state.parents?.parents?.firstWhereOrNull(...)` — при `state.parents ==
    null` (значение по умолчанию, шаг 6) оба равны `null`, и виджет рендерит
    для каждой карточки (мать/отец) `else`-ветку — плейсхолдер `Text(
    l10n.date_is_missing)` и иконку `Assets.plus` («добавить»). `ChildrenWidget.build`
    строит `ListView.separated(itemCount: state.children.length, ...)` — при
    `state.children == []` (значение по умолчанию) список пуст.
    `ReproductionFastFilterWidget(childrenCount: state.children.length, ...)`
    показывает счётчик `0`. Итог: экран выглядит и ведёт себя как у животного,
    у которого действительно нет ни матери, ни отца, ни потомства — без
    спиннера, без сообщения об ошибке, без индикации того, что данные вообще
    не были загружены.

### Альтернативные потоки

- **Сбой на разных точках вызова `load()` даёт идентичный итог, но разное
  число уже выполненных запросов.** Падение на первом же условном вызове
  (`getAnimalWithDetailsById(motherId)`, если `motherId != null`) означает,
  что ни `getChildrenByParentId`, ни оба `getAllAnimalsWithDetailsByFilters`
  не вызываются вообще; падение на последнем (`availableChildren`) означает,
  что мать/отец/потомки к этому моменту уже были успешно прочитаны локальными
  переменными — но, поскольку `emit` в `load()` вызывается только дважды (в
  начале и в самом конце), даже эти уже полученные данные никогда не попадают
  в состояние кубита и, соответственно, в UI. Итоговый наблюдаемый эффект для
  пользователя (шаг 10) одинаков независимо от того, на каком из пяти
  вызовов произошёл сбой.
- **Отдельный источник того же необработанного исключения — не сам
  репозиторий, а `!`-операторы внутри `load()`.** `kindIds: [state.animal
  .kind!.id]` и `birthDateRange: DateTimeRange(..., end: state.animal
  .birthDate!)`/`(start: state.animal.birthDate!, ...)` используют
  non-null-assertion на `AnimalWithDetails.kind` (тип `Kind?`) и
  `Animal.birthDate` (тип `DateTime?`). Если у просматриваемого животного
  `kind == null` или `birthDate == null`, `load()` бросает `TypeError` (null
  check operator used on a null value) синхронно, ещё до вызова
  `getAllAnimalsWithDetailsByFilters` — тот же класс необработанного
  исключения и тот же итоговый эффект (шаги 6–10), но источник — код самого
  кубита, а не репозиторий. Ни один существующий тест не покрывает эту
  ветку (см. «Открытые вопросы и ограничения»).
- **Экран строится нормально, не зависает и не показывает ошибку — просто
  молча лжёт данными по умолчанию.** В отличие от
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)/[UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md)
  (`AnimalWeighingsCubit` — freezed-union `initial/loading/loaded/
  loadedNotSync`, экран навсегда остаётся на `CircularProgressIndicator`/
  `CustomLottieLoader`), здесь состояние кубита (`isLoading: true`)
  технически застревает точно так же, но экран его не читает — пользователь
  не видит ни спиннера, ни ошибки, только «пустые» карточки родителей и
  пустой список потомков, неотличимые от легитимного «у этого животного
  никого не зарегистрировано».
- **Действия «добавить/изменить родителя» и «добавить потомка» деградируют
  молча.** Раз финальный `emit` не выполнился, `state.addPparentsData` и
  `state.addChildrenData` остаются `null` навсегда. Тап по карточке матери/отца
  вызывает `onParentTap(mother ?? Parents(gender: Gender.female))` →
  `selectParentForEdit` → при `parent.id == null` — `changeParentGender` +
  `changeParentKindId`, каждый из которых делает `state.copyWith
  (addPparentsData: state.addPparentsData?.copyWith(...))`; поскольку
  `state.addPparentsData` уже `null`, `null?.copyWith(...)` — no-op,
  `addPparentsData` остаётся `null`. Открывшийся `ReproductionParentModalWidget`
  (`AutoCompleteTextField.optionsBuilder: state.addPparentsData
  ?.getAvailableParentsByGender(...) ?? []`) не падает (весь доступ — через
  `?.`), но список кандидатов пуст всегда, а `onChanged: (value) => ...
  changeParentTransponderId(value)` (тоже `state.addPparentsData?.copyWith(...)`)
  так же остаётся no-op — введённый пользователем текст транспондера нигде
  не сохраняется в состоянии. Если пользователь всё равно нажмёт «Сохранить»
  (`saveParent()`), метод рано выходит по `if (parent == null) return;`
  (`parent = state.addPparentsData`) — это уже задокументированный отдельно
  дефект [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) («НАХОДКА —
  `saveParent`/`saveChild` … застревают в `isLoading: true` при раннем
  `return`»), покрытый тестовой группой `'UC-116 — ReproductionCubit
  .saveParent (ранний return, isLoading застревает)'` в
  `test/pages/reproduction_cubit_test.dart` — не переисследуется заново этим
  файлом, только упоминается как последующее звено той же цепочки отказов.
  Симметрично для потомка — `ChildrenWidget`/`_showAddChildModal` открывает
  `ReproductionChildModalWidget` с `state.addChildrenData == null`,
  `selectAvailableChild` тоже no-op (`state.addChildrenData?.copyWith(...)`),
  и `saveChild()` рано выходит по `if (child == null || child.animalId ==
  null) return;` — покрыто группой `'UC-118 — ReproductionCubit.saveChild
  (ранние return, isLoading застревает)'` того же файла.
- **Повторная попытка требует полного пересоздания экрана.**
  `_ReproductionViewState` не переопределяет `activate()` (в отличие от
  `_AnimalWeighingsBodyState` из [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md))
  — единственный способ вызвать `load()` заново — покинуть вкладку
  «Разведение» (`AppBar`-кнопка «назад» через `CustomAppBar`) и открыть её
  заново с карточки животного, что пересоздаст `BlocProvider`/
  `ReproductionCubit` и вызовет `load()` с нуля; при устойчивой (не
  преходящей) причине сбоя результат идентичен.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность из
  сегмента id; в этом сценарии читается до пяти раз за один вызов `load()`:
  мать (условно, `getAnimalWithDetailsById(motherId)`), отец (условно,
  `getAnimalWithDetailsById(fatherId)`), потомки
  (`getChildrenByParentId(animalId)`), и дважды через
  `getAllAnimalsWithDetailsByFilters` (кандидаты в родители/потомки). Мать,
  отец и каждый потомок — тот же самый `ENT-11`, что и просматриваемое
  животное (два и более экземпляра одной сущности в одном сценарии: текущее
  животное, его родители и его потомки — все они строки одной и той же
  Drift-таблицы `Animals`). Сбой чтения любого из них одинаково обрывает весь
  метод и оставляет `parents`/`children`/`addPparentsData`/`addChildrenData`
  в состоянии по умолчанию.

### Бизнес-правила

- **НАХОДКА — полное отсутствие обработки исключений в `load()`.**
  `ReproductionState` — не union с вариантом «ошибка», а обычный
  freezed-класс с `isLoading: bool`; при сбое код не доходит ни до какого
  `emit` после начального `isLoading: true` — кубит физически не может
  показать «пусто по факту» (`parents: null`, `children: []`) отдельно от
  «пусто из-за сбоя», потому что оба случая — буквально одно и то же
  значение состояния.
- **НАХОДКА — экран не проверяет `isLoading` вообще.** Даже если бы `load()`
  завершался успешно чуть позже, `_ReproductionViewState`/`ParentsWidget`/
  `ChildrenWidget` всё равно рендерили бы контент по `state.parents`/
  `state.children` немедленно — поле `isLoading` кубита не используется ни в
  одном виджете модуля REPRO (`grep` по `lib/pages/reproduction/presentation/`
  не находит ни одного обращения к нему). Это отличает сценарий от WEIGH:
  там `isLoading`-эквивалент (`AnimalWeighingsLoading`) хотя бы гейтит
  экран на спиннер; здесь у поля `isLoading` вообще нет наблюдаемого эффекта
  на UI — оно существует только внутри `ReproductionState`, доступное лишь
  тестам, читающим `cubit.state.isLoading` напрямую.
- **Экран строится нормально и не падает.** `BlocProvider.create` —
  синхронный колбэк; каскад `..load()` возвращает объект кубита, а не
  `Future` вызова `load()`, поэтому построение виджет-дерева не зависит от
  исхода асинхронного `load()`.
- **Необработанное исключение теряется полностью молча** — `lib/main.dart`
  не оборачивает `runApp` в `runZonedGuarded`/`runTalkerZonedGuarded` (вызов
  закомментирован целиком), тот же инфраструктурный факт, что и в
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)/[UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий (отсутствие `try/catch`, отклонение `Future`,
отсутствие логирования, отсутствие гейтинга UI по `isLoading`, молчаливый
рендеринг значений по умолчанию как «пусто по факту») прослеживается по
существующему коду `ReproductionCubit.load`,
`ReproductionState`, `_ReproductionViewState`, `ParentsWidget`, `ChildrenWidget`
полностью, без пробелов, требующих уточнения у пользователя. Единственная
содержательная неопределённость (реальное наблюдаемое поведение
необработанного отклонения `Future` в запущенном приложении) зафиксирована
в «Открытые вопросы и ограничения», не как пробел документации.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_AnimalCardToolbarAction` (пункт «Разведение», `onTap`) | CURRENT | точка входа — `context.pushNamed2(Routes.reproduction, extra: ReproductionPageArguments(animal: animalWithDetails))` |
| `lib/pages/reproduction/presentation/reproduction_page.dart` | `ReproductionPage.build` | CURRENT | достаёт `animal` из `extra`, строит `ReproductionView(animal: animal)` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionViewState.build` (`BlocProvider.create`) | CURRENT | `ReproductionCubit(widget.animal)..load()` — каскад не awaited |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionViewState.build` (`BlocConsumer.builder`) | CURRENT | строит `Scaffold`/`ParentsWidget`/`ChildrenWidget` безусловно — `state.isLoading` нигде не читается |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ParentsWidget.build` | CURRENT | рендерит из `state.parents?.parents` null-safely — `null` даёт плейсхолдер «добавить», неотличимый от «данных действительно нет» |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ChildrenWidget.build` | CURRENT | `ListView.separated(itemCount: state.children.length, ...)` — при `children: []` список пуст |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ReproductionParentModalWidget`, `ReproductionChildModalWidget` | CURRENT | оба читают `addPparentsData`/`addChildrenData` только через `?.` — не падают, но кандидаты пусты и правки застревают no-op, если `load()` не дошёл до финального `emit` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | ядро сценария — без `try/catch` вокруг пяти обращений к репозиторию и двух `!`-non-null-assertion на `kind`/`birthDate` |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState` | CURRENT | обычный freezed-класс (не union) с полем `isLoading: bool`; варианта «ошибка» нет, поле нигде не читается presentation-слоем |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | вызывается дважды за один `load()`, условно (мать/отец); тонкий passthrough в DAO, без `try/catch` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getChildrenByParentId` | CURRENT | вызывается безусловно; тонкий passthrough в DAO |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | вызывается дважды безусловно (`availableParents`/`availableChildren`); тонкий passthrough в DAO |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | делегирует в `getAllAnimalsWithDetailsByFilters(ids: [id])`, без `try/catch` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getChildrenByParentId` | CURRENT | Drift-select по `motherId`/`fatherId`, затем делегирует в `getAllAnimalsWithDetailsByFilters`, без `try/catch` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | реальная (немокнутая) реализация — Drift-запрос, без `try/catch`; общая точка, в которую сходятся все три метода репозитория выше |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.kind`, `AnimalWithDetails.animalId`, `AnimalWithDetails.motherId`/`fatherId` | CURRENT | `kind` — `Kind?`, разыменовывается через `!` в `load()`; `animalId`/`motherId`/`fatherId` — тонкие геттеры над `animal.*` |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `AnimalWeighingsPage.build` (контрастный сосед) | CURRENT | ([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)) — тот же дефект отсутствия `try/catch`, но экран там гейтит UI по состоянию-union и остаётся на спиннере, а не рендерит «пусто» |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` вызывается напрямую; `runTalkerZonedGuarded(...)` закомментирован целиком — необработанные асинхронные исключения не попадают ни в один явный error-handler приложения |

## Критерии приёмки

- Если любой из репозиторных вызовов `load()`
  (`AnimalsRepository.getAnimalWithDetailsById` — для матери и/или отца,
  `getChildrenByParentId`, `getAllAnimalsWithDetailsByFilters` — для
  `availableParents` и/или `availableChildren`) бросает исключение, `load()`
  не перехватывает его — возвращаемый `Future<void>` отклоняется тем же
  исключением (`throwsA(...)`, а не `completes`).
- После сбоя `cubit.state.isLoading` остаётся `true` — финальный `emit` не
  выполняется; `cubit.state.parents`/`children`/`addPparentsData`/
  `addChildrenData` остаются теми значениями, что были на момент начала
  этого вызова `load()` (по умолчанию: `null`/`[]`/`null`/`null`).
- Вызовы, идущие в коде после упавшего, не происходят вовсе (не «происходят,
  но результат отбрасывается») — частичного результата не существует.
- Ни один вызов `getIt<Talker>()` (или любого другого логгера) не происходит
  на этом пути.
- UI (`_ReproductionViewState`, `ParentsWidget`, `ChildrenWidget`) не
  показывает ни спиннера, ни сообщения об ошибке — экран рендерится так же,
  как для животного без зарегистрированных родителей/потомков, потому что
  presentation-слой нигде не читает `state.isLoading`.
- Действия «добавить/изменить родителя» и «добавить потомка», предпринятые
  после такого сбоя, не приводят к обновлению состояния (`addPparentsData`/
  `addChildrenData` остаются `null`, кандидаты в модалках всегда пустой
  список) — до тех пор, пока пользователь не покинет вкладку и не откроет её
  заново (пересоздание `ReproductionCubit`).

## Связанные тесты

`test/pages/reproduction_cubit_test.dart`, group `'UC-119 — ReproductionCubit
.load'` — в текущем виде группа содержит ровно шесть тестов: `'нет данных о
родителях -> parents=null, справочники всё равно заполняются'`, `'motherId
задан, мать найдена в репозитории -> motherBirk берётся из найденного
животного'`, `'motherId задан, мать НЕ найдена в репозитории -> используются
исходные motherBirk животного'`, `'fatherId задан, отец найден в репозитории
-> fatherBirk берётся из найденного животного'`, `'children заполняется
результатом getChildrenByParentId'`, `'availableParents фильтруются датой
рождения ДО текущего животного, availableChildren — ПОСЛЕ'` — все шесть
покрывают только успешный путь `load()`. Ни один мок
(`animalsRepository.getAnimalWithDetailsById`/`getChildrenByParentId`/
`getAllAnimalsWithDetailsByFilters`) не настроен на `thenThrow` ни в этой
группе, ни где-либо ещё в файле (проверено чтением файла целиком).

**TBD — теста нет** на `READ_ERROR`-исход `ReproductionCubit.load()` — ни для
сбоя на `getAnimalWithDetailsById` (мать/отец), ни для `getChildrenByParentId`,
ни для `getAllAnimalsWithDetailsByFilters` (кандидаты в родители/потомки), ни
для альтернативного источника того же класса сбоя — `!`-non-null-assertion
на `kind`/`birthDate`.

## Открытые вопросы и ограничения

- **Реальное поведение необработанного отклонения `Future` в запущенном
  приложении не проверено ни одним widget/integration-тестом.** Вывод о том,
  что экран не падает и не показывает индикацию сбоя, сделан по чтению кода
  (`BlocProvider.create` — синхронный колбэк; presentation-слой не читает
  `state.isLoading`; `lib/main.dart` не использует `runZonedGuarded`), а не по
  факту запуска реального приложения — тот же класс ограничения, что уже
  зафиксирован в
  [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)/[UC-96](UC-96-ACTOR-5-EVT-48-ENT-15-READ_ERROR-IN-ANIMAL.md).
- **`!`-non-null-assertion на `kind`/`birthDate` как отдельный источник того
  же необработанного исключения не покрыт ни одним тестом.** Если у
  просматриваемого животного `kind == null` или `birthDate == null`, `load()`
  бросает `TypeError` синхронно внутри собственного тела, ещё до обращения к
  репозиторию — по внешнему эффекту неотличимо от репозиторного сбоя
  (`Future` отклоняется, `isLoading` застревает в `true`), но причина — код
  кубита, а не зависимость. Насколько часто `kind`/`birthDate` реально
  бывают `null` для животного, уже дошедшего до экрана «Разведение», этим
  документом не оценивалось.
- **Стоит ли добавлять обработку ошибок в `load()` и/или гейтинг UI по
  `isLoading`?** Не решено этим документирующим файлом — распространяется
  на всю тройку симптомов (отсутствие `try/catch`, отсутствие варианта
  «ошибка» в `ReproductionState`, отсутствие проверки `isLoading` в
  presentation-слое) одинаково; вопрос пользователю, если поведение должно
  измениться в `TARGET`.
- **Отсутствует тест, параметризованный по тому, какой из пяти вызовов (или
  какая из двух non-null-assertion) становится причиной сбоя.** Существующие
  шесть тестов группы `'UC-119 — ReproductionCubit.load'` покрывают только
  штатный путь.
- Сценарий отражает поведение исключительно `ReproductionCubit.load` (вкладка
  «Разведение» одного животного, [EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md));
  на момент написания этого файла в дереве спек нет отдельного `READ_OK`
  use-case для того же события — успешный путь `load()` покрыт только тестами
  (см. выше), но не отдельным документирующим файлом.
