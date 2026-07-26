# UC-118 — Привязка потомка отказывает: `ReproductionCubit.saveChild` — тихий отказ `update` и два ранних `return` с зависанием `isLoading`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md)
(`animal.child_linked`) в трёх разных, но кодово соседних точках одного и
того же метода `ReproductionCubit.saveChild`:

- **(а) технический сбой** — `_animalsRepository.update(...)` бросает
  исключение при попытке сохранить обновлённую запись выбранного потомка;
  перехватывается общим `catch` метода — тот же паттерн тихого отказа, что
  и у `ReproductionCubit.saveParent` (сценарий для родителя).
- **(б) ранний `return`** — `state.addChildrenData` равен `null`, либо
  `addChildrenData.animalId` не выбран пользователем.
- **(в) ранний `return`** — потомок с выбранным `animalId` не находится в
  репозитории (`_animalsRepository.getAnimalWithDetailsById(...)` возвращает
  `null`).

Во всех трёх случаях `AnimalsRepository.update` для потомка либо не
вызывается вовсе (б, в), либо вызывается и падает (а) — ни в одном из них
пользователь не получает сообщения об ошибке. В (б) и (в), в отличие от
(а), `emit(state.copyWith(isLoading: true))`, выполненный в самом начале
`try`-блока, не сбрасывается никаким последующим `emit` — `isLoading`
остаётся `true` в состоянии кубита до следующего успешного вызова
`saveChild()`/`saveParent()`/`load()`.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/reproduction/cubit/reproduction_cubit.dart` целиком:
`ReproductionCubit` не объявляет и не использует `AuthRepository` ни в
одном методе, включая `saveChild` — запись `Animal`
([ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)) сама по себе не имеет
поля-автора привязки родословной.

## CURRENT

### Основной поток

1. Пользователь открывает экран «Разведение» (`ReproductionPage` →
   `ReproductionView`). При первом `build` создаётся
   `ReproductionCubit(widget.animal)..load()`
   (`_ReproductionViewState.build`); переключает вкладку на «Дети»
   (`ReproductionFilter.children` через
   `ReproductionFastFilterWidget.onReproductionFilterChanged` →
   `cubit.setReproductionFilter`). Смена `reproductionFilter` — единственное
   условие, при котором `BlocConsumer.listenWhen` вызывает `_syncFab`,
   которая показывает FAB (`fab.setAction(_showAddChildModal)`), только
   если `!_isDisposed && state.reproductionFilter == children`.
2. Нажатие FAB открывает `showModalBottomSheet(... builder: (_) =>
   ReproductionChildModalWidget(cubit: cubit))`
   (`_showAddChildModal`). Модалка показывает
   `AutoCompleteTextField<AnimalWithDetails>` по
   `state.addChildrenData?.availableChildren` — список, заполняемый только
   внутри `ReproductionCubit.load()` через
   `_animalsRepository.getAllAnimalsWithDetailsByFilters(kindIds: [текущий
   вид], birthDateRange: [birthDate текущего животного .. DateTime.now()])`
   — то есть кандидаты того же вида и «моложе» просматриваемого животного.
3. Пользователь выбирает кандидата — `onSelected` вызывает
   `cubit.selectAvailableChild(animal)`, который **только** записывает
   `addChildrenData.animalId = animal.animal.id` из уже переданного в UI
   объекта; в репозиторий за подтверждением существования записи `selectAvailableChild`
   не обращается.
4. Пользователь нажимает «Сохранить» (`BlackCircleButton` внутри FAB
   модалки): `onTap: () async { await
   context.read<ReproductionCubit>().saveChild(); if (context.mounted) {
   context.pop(context); } }`
   (`reproduction_view.dart`, `_ReproductionChildModalWidgetState.build`).
   **`context.pop(context)` вызывается безусловно после `await saveChild()`**
   — `saveChild()` никогда не перебрасывает исключение наружу (см. ниже),
   так что модалка закрывается одинаково и при успехе, и при любом из трёх
   отказов этого сценария.
5. `ReproductionCubit.saveChild()`:
   ```dart
   Future<void> saveChild() async {
     try {
       emit(state.copyWith(isLoading: true));
       final child = state.addChildrenData;
       if (child == null || child.animalId == null) return;
       ...
       final animalChild = await _animalsRepository.getAnimalWithDetailsById(
         child.animalId!,
       );
       if (animalChild == null) return;
       ...
       await _animalsRepository.update(updatedChildAnimal);
       ...
       emit(state.copyWith(isLoading: false, children: updatedChildren, ...));
     } catch (e) {
       getIt<Talker>().error(e);
       emit(state.copyWith(isLoading: false));
     }
   }
   ```
   `emit(state.copyWith(isLoading: true))` — первая строка внутри `try`.
6. **(б) Ранний `return` — потомок не выбран.** Если `state.addChildrenData`
   равен `null` (возможно только пока `load()` ещё не завершился: начальное
   `ReproductionState` не задаёт `addChildrenData` по умолчанию — поле
   `null`, пока `load()` не выполнит финальный `emit`; FAB технически
   доступен сразу после переключения фильтра на «Дети», независимо от того,
   успел ли `load()` отработать) **или** `addChildrenData.animalId == null`
   (пользователь открыл модалку и нажал «Сохранить», ничего не выбрав в
   `AutoCompleteTextField`) — метод возвращается на строке `if (child ==
   null || child.animalId == null) return;`, до какого-либо обращения к
   `_animalsRepository`. `_animalsRepository.update` и
   `.getAnimalWithDetailsById` не вызываются. **`isLoading`, выставленный на
   предыдущем шаге в `true`, не сбрасывается — состояние кубита остаётся
   `isLoading: true`.**
7. **(в) Ранний `return` — выбранный потомок не найден.** Если
   `child.animalId` задан, но
   `_animalsRepository.getAnimalWithDetailsById(child.animalId!)`
   возвращает `null` — метод возвращается на строке `if (animalChild ==
   null) return;`, до вызова `_animalsRepository.update`. Как и в (б),
   **`isLoading` остаётся `true`.**
8. **(а) Технический сбой при сохранении.** Если оба ранних `return` не
   сработали (потомок выбран и найден), кубит строит `updatedChildAnimal =
   animalChild.animal.copyWith(motherId: ..., motherBirk: ..., motherName:
   const Value(null), fatherId: ..., fatherBirk: ..., fatherName: const
   Value(null), needsUpdate: animalChild.animal.id >= 0 ? const
   Value(true) : const Value.absent())` и вызывает `await
   _animalsRepository.update(updatedChildAnimal)`. Если этот вызов бросает
   исключение (например, ошибка Drift/БД) — оно ловится общим `catch (e)`
   метода: `getIt<Talker>().error(e)` вызывается один раз, затем
   `emit(state.copyWith(isLoading: false))`. **`isLoading` здесь корректно
   сбрасывается**, в отличие от (б)/(в) — но `state.children` остаётся
   ровно тем списком, что был до вызова `saveChild()` (обновление потомка
   не попадает ни в state, ни, разумеется, в БД дальше точки сбоя), и
   `ReproductionState` не содержит ни поля ошибки, ни какого-либо другого
   сигнала для UI — сообщение об ошибке пользователю не показывается никаким
   `SnackBar`/`ScaffoldMessenger`.

### Альтернативные потоки

- **Модалка закрывается одинаково при успехе и при любом из трёх отказов.**
  Так как `saveChild()` перехватывает исключение сама и никогда не
  перебрасывает его наружу, а оба ранних `return` завершаются нормально —
  `await context.read<ReproductionCubit>().saveChild();` в
  `reproduction_view.dart` всегда резолвится без ошибки, и следующая строка
  `context.pop(context)` выполняется без исключений. С точки зрения
  пользователя нажатие «Сохранить» выглядит одинаково успешным во всех
  четырёх случаях (три отказа + реальный успех).
- **Случай (б) достижим двумя разными путями с одинаковым кодовым исходом.**
  Либо `addChildrenData` целиком `null` (узкое окно гонки — FAB
  открывается сразу по смене фильтра, вне зависимости от того, успел ли
  асинхронный `load()` дойти до финального `emit`), либо
  `addChildrenData.animalId == null` уже после `load()`, когда пользователь
  просто не выбрал кандидата перед нажатием «Сохранить». Существующий тест
  (см. «Связанные тесты») покрывает только второй вариант, через
  `buildLoadedCubit` (т.е. `load()` гарантированно завершён).
- **`selectAvailableChild` не проверяет, что выбранный кандидат всё ещё
  существует в репозитории** — она лишь копирует `animal.animal.id` из уже
  переданного в UI объекта `AnimalWithDetails` (взятого из
  `state.addChildrenData.availableChildren`, вычисленного один раз в
  `load()`). Случай (в) возникает при повторном обращении к
  `_animalsRepository.getAnimalWithDetailsById` уже внутри `saveChild()` —
  если к этому моменту запись более недоступна (например, тестовый мок
  возвращает `null`, или в реальном приложении — потомок был удалён/успел
  замениться синком между выбором в модалке и нажатием «Сохранить»).
- **Тот же паттерн тихого отказа (а) есть и в `ReproductionCubit.saveParent`** —
  тот же общий `try { emit(isLoading:true); ...; await
  _animalsRepository.update(...); ...; } catch (e) { getIt<Talker>().error(e);
  emit(isLoading:false); }`, применённый к обновлению просматриваемого
  животного вместо потомка. Не документируется здесь — это отдельный
  сценарий для родителя, привязанный к
  [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md), а не к
  [EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md). Упоминается
  только как соседняя точка того же дефекта в том же кубите.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — **одна и та же
  сущность в двух ролях, две разные записи**: просматриваемое животное
  (`state.animal`, роль будущего родителя — только читается: его
  `motherId`/`motherBirk`/`fatherId`/`fatherBirk`, `birthDate`, `gender`,
  `kindId` и транспондер используются, чтобы построить, чем должен стать
  родитель потомка; сама запись просматриваемого животного методом
  `saveChild` не изменяется и не перечитывается) и выбранный потомок
  (`animalChild`, полученный через `getAnimalWithDetailsById` — **именно
  эта запись** является целью `_animalsRepository.update` и, соответственно,
  единственной записью `Animal`, которую может задеть отказ данного
  use-case).
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — только читается:
  `state.animal.activeAnimalIdentifications.firstOrNull?.number` (транспондер
  просматриваемого животного, для поля `transponderId` строящегося
  `newParent`/`Parents`). `AnimalIdentification` не создаётся, не
  обновляется и не удаляется методом `saveChild`. Note: геттер
  `activeAnimalIdentifications` (`animals_with_details.dart`) реализован как
  `animalIdentifications.where((e) => true).toList()` — фактически
  возвращает весь список идентификаций без какой-либо фильтрации, несмотря
  на название.

### Бизнес-правила

- Классифицируется как `UPDATE_ERROR`, а не `UPDATE_REJECTED` в любой из
  трёх ветвей: (а) — исключение уровня хранения (Drift/БД), не
  бизнес-валидация; (б)/(в) — данные, необходимые для операции, не
  сформированы к моменту вызова (нет выбранного/найденного потомка), а не
  осознанно отклонены бизнес-правилом.
- `needsUpdate` выставляется в `true` для потомка только если
  `animalChild.animal.id >= 0` (потомок уже синхронизирован); для ещё не
  отправленного локального потомка (`id < 0`) поле не трогается
  (`Value.absent()`) — не относится к отказному сценарию напрямую, но
  определяет, какая запись реально требует повторной отправки после (в
  случае успеха, не рассматриваемого здесь) события.
- `motherName`/`fatherName` потомка всегда принудительно обнуляются
  (`const Value(null)`) при любом успешном прохождении до `update` —
  относится к обеим сторонам одинаково, независимо от того, менялась ли
  фактически мать или отец; в отказных ветках (б)/(в) до этого кода
  выполнение не доходит вовсе, в (а) это уже произошло до сбоя `update`, но
  сама операция отклонена репозиторием целиком (изменение не
  сохраняется).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — все три ветки прослеживаются чтением
`lib/pages/reproduction/cubit/reproduction_cubit.dart` (`saveChild`,
`selectAvailableChild`, `load`), `lib/pages/reproduction/cubit/reproduction_state.dart`,
`lib/pages/reproduction/data/add_parent_data.dart` (`AddChildrenData`),
`lib/pages/reproduction/presentation/widgets/reproduction_view.dart`
(`_showAddChildModal`, `_syncFab`, `_ReproductionChildModalWidgetState.build`),
`lib/repositories/animal/animals_repository.dart`,
`lib/repositories/base_repository.dart`,
`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` и
`packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart`.
То, что `isLoading` нигде в `lib/pages/reproduction/` не читается за
пределами самого `ReproductionState`/`ReproductionCubit` (ни один
`BlocBuilder`/`BlocConsumer` в `reproduction_view.dart` не обращается к
`state.isLoading`), перепроверено отдельным `grep` по всей папке
`lib/pages/reproduction/`, а не восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.saveChild` | CURRENT | единственный метод сценария; `try/catch` перехватывает (а), ранние `return` — источники (б) и (в); `isLoading` выставляется в `true` первой строкой `try` и сбрасывается только по успешному пути или в `catch` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.selectAvailableChild` | CURRENT | предшествующий шаг — пишет только `addChildrenData.animalId` из уже переданного объекта, не обращается к репозиторию за подтверждением существования |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | единственное место, где `addChildrenData` впервые становится не `null` (до этого — `null` по умолчанию), и откуда берётся `availableChildren` |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState` | CURRENT | `isLoading` без `@Default` не объявлен — фактически `false` по умолчанию через freezed-конструктор; `addChildrenData` — `AddChildrenData?`, `null` до первого `load()` |
| `lib/pages/reproduction/data/add_parent_data.dart` | `AddChildrenData` | CURRENT | `animalId` — `int?`, `null` по умолчанию — источник условия раннего `return` (б) |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionChildModalWidgetState.build` (FAB `onTap`) | CURRENT | безусловно вызывает `context.pop(context)` сразу после `await saveChild()`, независимо от исхода |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionViewState._syncFab` | CURRENT | показывает FAB, открывающий модалку добавления ребёнка, по смене `reproductionFilter` — независимо от того, завершился ли асинхронный `load()` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | источник (в) — возвращает `Future<AnimalWithDetails?>`, `null` при отсутствии записи |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (наследует `BaseRepository.update`, своего переопределения нет) | CURRENT | источник (а) — исключение из `update` не перехватывается на уровне репозитория |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | тонкая обёртка `dao.upd(item)`, без своего `try/catch` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | непосредственный Drift-запрос, возвращающий `null`, если запись не найдена |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetails.animalId`, `.motherId`, `.fatherId`, `.birthDate`, `.activeAnimalIdentifications` | CURRENT | геттеры, используемые для построения `Parents`-объектов внутри `saveChild` |

## Критерии приёмки

- Если `state.addChildrenData == null` либо
  `state.addChildrenData!.animalId == null` в момент вызова `saveChild()`,
  метод возвращается до любого обращения к `_animalsRepository`;
  `animalsRepository.getAnimalWithDetailsById` и `.update` не вызываются
  вовсе; `cubit.state.isLoading == true` после вызова (застревает).
- Если `_animalsRepository.getAnimalWithDetailsById(child.animalId!)`
  возвращает `null`, метод возвращается до вызова
  `_animalsRepository.update`; `.update` не вызывается;
  `cubit.state.isLoading == true` после вызова (тот же паттерн застревания,
  что и в предыдущем пункте).
- Если `_animalsRepository.update(updatedChildAnimal)` бросает исключение,
  оно перехватывается внутри `saveChild()`: `getIt<Talker>().error(e)`
  вызывается ровно один раз, `cubit.state.isLoading == false` после вызова,
  `cubit.state.children` не меняется относительно состояния до вызова.
- Во всех трёх случаях `ReproductionState` не содержит ни одного поля,
  сигнализирующего пользователю об ошибке, и вызывающий код
  (`reproduction_view.dart`) закрывает модалку добавления ребёнка так же,
  как при успехе.

## Связанные тесты

- `test/pages/reproduction_cubit_test.dart`, group `'UC-118 —
  ReproductionCubit.saveChild ERROR (известный дефект — тихий отказ)'`, test
  `'saveChild: update бросает -> Talker.error вызван, isLoading:false, дети
  не обновлены'` — покрывает (а): `animalsRepository.update(any())`
  замокан на `thenThrow(Exception('db error'))`,
  `getAnimalWithDetailsById(20)` возвращает валидного потомка (ранние
  `return` не срабатывают), после `cubit.selectAvailableChild(childAnimal)`
  и `await cubit.saveChild()` проверяется
  `verify(() => getIt<Talker>().error(any())).called(1)`,
  `expect(cubit.state.isLoading, false)`,
  `expect(cubit.state.children, isEmpty)`.
- `test/pages/reproduction_cubit_test.dart`, group `'UC-118 —
  ReproductionCubit.saveChild (ранние return, isLoading застревает)'` (2
  теста внутри):
  - `'addChildrenData.animalId не выбран -> ранний return, update не
    вызывается'` — покрывает (б), только вариант «после `load()`, кандидат
    не выбран» (`buildLoadedCubit` гарантирует, что `load()` завершён,
    `selectAvailableChild` не вызывается вовсе): проверяет
    `verifyNever(() => animalsRepository.update(any()))` и
    `expect(cubit.state.isLoading, isTrue, reason: 'тот же паттерн
    застревания isLoading, что и в saveParent при раннем return')`.
  - `'выбранный ребёнок не найден в репозитории -> ранний return'` —
    покрывает (в): `getAnimalWithDetailsById(30)` замокан на
    `thenAnswer((_) async => null)`, после `selectAvailableChild(_animal(30))`
    и `await cubit.saveChild()` проверяется
    `verifyNever(() => animalsRepository.update(any()))`.
  (Групповые имена используют старую нумерацию `UC-199` — идентификатор
  будет переименован отдельным проходом; сами тесты уже покрывают ровно эти
  сценарии.)
- **TBD — теста нет** на вариант (б) «`addChildrenData` целиком `null`»
  (гонка: `saveChild()` вызван до того, как асинхронный `load()` успел
  дойти до финального `emit`) — существующий тест использует
  `buildLoadedCubit`, то есть `load()` гарантированно завершён к моменту
  вызова.
- **TBD — теста нет** на поведение самой модалки
  (`_ReproductionChildModalWidgetState`/`_showAddChildModal`) — ни то, что
  `context.pop(context)` вызывается безусловно после `await saveChild()`,
  ни визуальное отсутствие индикатора ошибки не проверяются ни одним
  widget-тестом (в `test/` нет файла для `reproduction_view.dart` /
  `reproduction_page.dart`); вывод сделан по чтению кода, а не по запуску
  реального приложения.

## Открытые вопросы и ограничения

- **`isLoading` нигде не читается в `lib/pages/reproduction/`** — ни один
  `BlocBuilder`/`BlocConsumer` в `reproduction_view.dart` не обращается к
  `state.isLoading` (перепроверено `grep` по всей папке). Из этого следует,
  что зависание `isLoading` в `true` при (б)/(в) на сегодняшний день —
  **скрытый дефект без наблюдаемого симптома**: он проявится только если в
  будущем какой-то виджет экрана «Разведение» начнёт биндиться к
  `state.isLoading` (например, спиннер на кнопке «Сохранить»), и тогда этот
  виджет застрянет в состоянии загрузки до следующего успешного вызова
  `saveChild`/`saveParent`/`load`.
- **Случай (а) — тот же самый «тихий отказ», что и в `saveParent`** —
  документирование этого паттерна как дефекта или как принятого поведения
  не входит в рамки данного use-case; здесь зафиксирован только сам факт
  CURRENT-поведения.
- **Реальная достижимость варианта (б) «`addChildrenData` целиком `null`»
  не подтверждена ни тестом, ни запуском приложения** — вывод о том, что
  окно гонки существует (FAB становится доступен сразу по смене фильтра,
  независимо от завершения `load()`), сделан по чтению
  `_syncFab`/`BlocConsumer.listenWhen` и `ReproductionCubit.load`, а не по
  наблюдению за реальным поведением UI.
