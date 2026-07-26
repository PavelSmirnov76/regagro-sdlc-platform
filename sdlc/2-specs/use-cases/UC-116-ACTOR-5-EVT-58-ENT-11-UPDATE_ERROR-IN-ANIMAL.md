# UC-116 — Привязка родителя: update бросает исключение (тихий отказ) или ранний return (isLoading застревает)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же триггер, что в успешном сценарии [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md)
(`ReproductionCubit.saveParent`) — пользователь на экране «Разведение»
подтверждает выбор матери или отца животного, — но `saveParent()` не
доходит до видимого пользователю успеха одним из двух структурно разных,
не связанных между собой путей:

- **(a)** `AnimalsRepository.update(updatedAnimal)` бросает исключение —
  `catch` перехватывает его, логирует через `Talker.error`, сбрасывает
  `isLoading` в `false`; пользователь не получает никакого сообщения об
  ошибке нигде в UI.
- **(b)** охранный ранний `return` в начале метода (`state.addPparentsData`
  равен `null`) — `isLoading`, выставленный самой первой строкой метода,
  **не сбрасывается обратно**, потому что `return` происходит до
  единственного места в успешном пути, которое ставит его в `false`, и
  до `catch`-блока (исключения не было).

Оба пути документируются одним файлом, потому что оба заканчиваются одним и
тем же исходом `UPDATE_ERROR` — сохранение записи `Animal` не происходит
(ветка (b)) или происходит частично и без подтверждения пользователю (ветка
(a), см. «Открытые вопросы» — фактически `update` в ветке (a) может успеть
записать часть побочных эффектов до того, как бросить, в зависимости от
причины исключения), — но с прямо противоположным эффектом на `isLoading`:
ветка (a) корректно возвращает `isLoading` в `false`, ветка (b) — нет.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `ReproductionCubit` не
объявляет и не использует `AuthRepository` ни в одном методе.

## CURRENT

### Основной поток

1. Пользователь на экране «Разведение» (`ReproductionView`) нажимает карточку
   «Мать» или «Отец» — `ParentsWidget.onParentTap` (`lib/pages/reproduction/
   presentation/widgets/reproduction_view.dart`) вызывает `await
   cubit.selectParentForEdit(parent)`, затем открывает
   `ReproductionParentModalWidget` через `showModalBottomSheet`.
2. В модальном окне пользователь нажимает «Сохранить»
   (`BlackCircleButton.onTap` внутри `_ReproductionParentModalWidgetState.build`)
   — вызывается `await context.read<ReproductionCubit>().saveParent()`, затем
   безусловно `context.pop(context)`, если `context.mounted` — модалка
   закрывается **независимо от исхода** `saveParent()`, в том числе если
   сработала любая из веток ниже.
3. `ReproductionCubit.saveParent` (`lib/pages/reproduction/cubit/
   reproduction_cubit.dart`) выполняется целиком внутри одного `try`:
   ```dart
   try {
     emit(state.copyWith(isLoading: true));
     final parent = state.addPparentsData;
     if (parent == null) return;
     // ... построение mother/father, updatedAnimal
     await _animalsRepository.update(updatedAnimal);
     emit(state.copyWith(isLoading: false, ...));
   } catch (e) {
     getIt<Talker>().error(e);
     emit(state.copyWith(isLoading: false));
   }
   ```
   `emit(isLoading: true)` — самая первая строка метода, до какой-либо
   проверки или репозиторного вызова.
4. **Ветка (a) — `update` бросает исключение.** Метод доходит до `await
   _animalsRepository.update(updatedAnimal)` (`state.addPparentsData` был
   не `null`, `mother`/`father` посчитаны). `AnimalsRepository.update` —
   не переопределён в `AnimalsRepository`, наследуется из
   `BaseRepository<AnimalsDao, Animal, Animals>.update` (`lib/repositories/
   base_repository.dart`), который делегирует в `dao.upd(item)` →
   `BaseDao.upd` (`packages/sheep_farm_database/lib/entities/base_dao.dart`)
   → `updateCurrent().replace(item)` — Drift-запрос, способный бросить
   исключение (например ошибку БД). Исключение перехватывается внешним
   `catch (e)`: `getIt<Talker>().error(e)` логирует его, затем
   `emit(state.copyWith(isLoading: false))` — **единственное** поле,
   которое меняется в этом emit; `parents`/`animal`/`addPparentsData`
   остаются такими, какими были **до** вызова `saveParent()` (последнее
   успешное состояние, не отражающее ни попытку, ни её провал). Ни один
   `emit` ошибки, ни `SnackBar`, ни любое другое сообщение пользователю не
   производится — `ReproductionView`/`ReproductionParentModalWidget` не
   содержат `BlocListener` и не читают `state.isLoading`/любое состояние
   ошибки в своих `build`-методах (`BlocConsumer.listenWhen` в
   `ReproductionView` реагирует только на смену `state.reproductionFilter`,
   не на `isLoading` или на исключение). Пользователь видит закрывшуюся
   модалку без какого-либо индикатора провала — как если бы сохранение
   прошло успешно.
5. **Ветка (b) — ранний `return`, `state.addPparentsData == null`.**
   `state.addPparentsData` равен `null` в момент вызова `saveParent()` —
   практически это означает, что `ReproductionCubit.load()` (единственный
   метод, изначально заполняющий `addPparentsData` через `emit(...,
   addPparentsData: AddParentData(availableParents: ...))`) либо вообще не
   был вызван для этого экземпляра кубита, либо ещё не успел завершить свою
   цепочку `await`-вызовов к репозиторию на момент нажатия «Сохранить».
   `if (parent == null) return;` — обычный `return`, **внутри** `try`, **до**
   любого репозиторного вызова и до финального `emit(isLoading: false, ...)`
   успешного пути; исключения не было, поэтому `catch`-блок тоже не
   выполняется. Единственный уже произведённый `emit` для этого вызова —
   `emit(state.copyWith(isLoading: true))` с первой строки метода —
   остаётся последним `emit`'ом: состояние кубита необратимо фиксируется с
   `isLoading == true` до тех пор, пока какой-то другой метод этого же
   кубита (например повторный `saveParent()`, который на этот раз пройдёт
   успешный путь, или `load()`) не вызовет `emit` заново.
6. В обеих ветках `Future`, возвращаемый `saveParent()`, успешно резолвится
   (`completes`, не `throwsA`) — вызывающий код в шаге 2
   (`await context.read<ReproductionCubit>().saveParent()`) никогда не видит
   непойманное исключение и переходит к `context.pop(context)` одинаково в
   обоих случаях, а также в успешном сценарии.

### Альтернативные потоки

- **Ветка (b) недостижима после первого успешного `load()` для того же
  экземпляра кубита.** Единственное место, устанавливающее
  `addPparentsData` в конкретное (не `null`) значение с нуля — `load()`.
  Остальные методы (`selectAvailableParent`, `changeParentTransponderId`,
  `changeParentGender`, `changeParentKindId`, `changeParentBirthDate`) в
  случае, если `state.addPparentsData` уже `null`, используют цепочку
  `state.addPparentsData?.copyWith(...)` — она возвращает `null` и просто
  переустанавливает то же `null` обратно, ничего не меняя.
  Единственные исключения — `clearParentData()` (безусловно создаёт новый
  `AddParentData(availableParents: state.addPparentsData?.availableParents
  ?? [])`, даже если было `null`) и сам `load()`. Поэтому ветка (b)
  реалистично достижима только в узком окне гонки: `ReproductionView`
  строит `BlocProvider<ReproductionCubit>(create: (context) { final cubit =
  ReproductionCubit(widget.animal)..load(); ...; return cubit; })` — вызов
  `..load()` не дожидается своего завершения перед тем, как виджет-дерево
  станет интерактивным, а сама разметка `ParentsWidget` (карточки «Мать»/
  «Отец») строится безусловно, без проверки `state.isLoading` — тап по
  карточке и последующее нажатие «Сохранить» в открывшейся модалке
  технически возможны до того, как несколько последовательных `await` внутри
  `load()` (два опциональных чтения родителей, чтение потомков, два чтения
  списков доступных животных) успеют завершиться. `clearParentData()`, если
  он успел выполниться до `saveParent()`, эту гонку закрывает (устанавливает
  `addPparentsData` не-`null` безусловно) — но по коду `ReproductionView`
  `clearParentData()` вызывается только в `.then((value) async {...})`
  после закрытия модалки, то есть **после**, а не до, попытки сохранения.
- **Сравнение с `saveChild()`.** Тот же файл содержит структурно идентичный
  парный метод `ReproductionCubit.saveChild` с тем же паттерном: `try` с
  ранним `return` при `child == null || child.animalId == null` (а также
  вторым ранним `return` при `animalChild == null` после репозиторного
  вызова), тот же `catch (e) { Talker.error(e); emit(isLoading: false); }`.
  Это отдельная сущность (изменяется чужая запись `Animal` — потомок, не
  просматриваемое животное) и отдельное событие
  ([EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md)) — не
  описывается этим файлом.
- **`updatedAnimal` в ветке (a) уже полностью построен в памяти до вызова
  `update`.** Исключение в `update` не откатывает и не трогает
  `state.animal` — объект, который получила бы `emit` при успехе, просто
  никогда не подставляется в состояние; локальная переменная
  `updatedAnimal` выходит из области видимости вместе с прерванным вызовом.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность из
  сегмента id; ОДНА И ТА ЖЕ сущность в этом сценарии в двух ролях:
  просматриваемое животное (`state.animal.animal`, которое пытаются
  обновить полями `motherId`/`motherBirk`/`fatherId`/`fatherBirk`) и
  родитель-кандидат (`state.addPparentsData`, `state.parents` — читаются,
  но не изменяются этим методом). Обе роли — экземпляры одной и той же
  Drift-таблицы `Animals`, не отдельные сущности.

### Бизнес-правила

- **Ветка (a) — тихий отказ.** Исключение из `update` логируется через
  `Talker.error`, но не долетает до пользователя ни в каком виде — ни
  `SnackBar`, ни поле ошибки в состоянии, ни повторная попытка. Это то же
  самое ограничение, что зафиксировано для `saveChild` в паре
  `EVT-59`/`ENT-11`: обе привязки (родителя и потомка) сообщают об ошибке
  исключительно в лог, никогда в UI.
- **Ветка (b) — `isLoading` необратимо застревает в `true` для данного
  экземпляра кубита**, пока не произойдёт следующий успешный `emit` (любой
  другой метод кубита, включая повторный вызов `saveParent()`, который на
  этот раз дойдёт до конца). Сегодня это не создаёт видимого зависшего
  индикатора загрузки — ни `ReproductionView`, ни
  `ReproductionParentModalWidget` не читают `state.isLoading` ни в одном
  `build`-методе (см. «Открытые вопросы» — поле нигде не отрисовывается),
  так что немедленный практический эффект для текущего пользователя — нулевой;
  тем не менее состояние кубита реально некорректно и обнаруживается тестом,
  напрямую проверяющим `cubit.state.isLoading`.
- **`needsUpdate` в ветке (a) НЕ взводится** — исключение происходит либо
  внутри самого `dao.upd` (запись в БД не применилась, либо применилась
  частично — зависит от причины исключения и не проверяется этим сценарием
  отдельно), в любом случае состояние кубита `state.animal` не обновляется
  этим вызовом, поэтому `needsUpdate: true`, вычисленный для
  `updatedAnimal`, не отражается нигде, что мог бы прочитать
  дальнейший sync pipeline из этого же прогона приложения (кубит держит
  устаревший `state.animal`, пока экран не перезагрузят).
- **Обе ветки заканчиваются одинаково с точки зрения вызывающего кода** —
  `Future` от `saveParent()` резолвится успешно, `context.pop(context)`
  выполняется безусловно. Экран «Разведение», к которому пользователь
  возвращается, ничем не отличается от исхода настоящего успеха, кроме
  того, что запись `Animal` в ветке (a) не была обновлена вовсе, а в ветке
  (b) даже не была предпринята попытка.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обе ветки (исключение в `update` и ранний `return` при
отсутствующем `addPparentsData`) прослеживаются по существующему коду
`ReproductionCubit.saveParent` полностью, без пробелов, требующих уточнения
у пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `ParentsWidget.onParentTap` (внутри `ReproductionView.build`) | CURRENT | точка входа — открывает `ReproductionParentModalWidget` после `cubit.selectParentForEdit(parent)` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionParentModalWidgetState.build` (`BlackCircleButton.onTap`) | CURRENT | вызывает `await context.read<ReproductionCubit>().saveParent()`, затем безусловный `context.pop(context)` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.saveParent` | CURRENT | ядро сценария — `try/catch`, ранний `return` при `state.addPparentsData == null`, вызов `_animalsRepository.update` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | единственный метод, изначально заполняющий `addPparentsData` не-`null` значением — определяет окно гонки для ветки (b) |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState.isLoading`, `ReproductionState.addPparentsData` | CURRENT | поля, застревающие/не читаемые в ветке (b) |
| `lib/pages/reproduction/data/add_parent_data.dart` | `AddParentData` | CURRENT | тип `state.addPparentsData`; `null` в момент вызова — условие ветки (b) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (не переопределяет `update`) | CURRENT | `update` наследуется из `BaseRepository` без изменений |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | делегирует в `dao.upd(item)`; исключение отсюда — причина ветки (a) в тесте (мок бросает прямо на этом вызове) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — реальный Drift-вызов, оборачиваемый `BaseRepository.update` |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` (импорт `package:talker_flutter/talker_flutter.dart`) | `Talker.error` (через `getIt<Talker>()`) | CURRENT | единственный эффект ветки (a), видимый где-либо — запись в лог, не в UI |

## Критерии приёмки

- Если `_animalsRepository.update(updatedAnimal)` бросает исключение,
  `ReproductionCubit.saveParent()` перехватывает его, ровно один раз
  вызывает `getIt<Talker>().error(e)`, эмитит `state.copyWith(isLoading:
  false)` как последнее изменение состояния, и `Future`, возвращаемый
  `saveParent()`, успешно резолвится (`completes`, не `throwsA`).
- В ветке (a) `state.parents`, `state.animal` после вызова остаются такими
  же, какими были до вызова `saveParent()` — не отражают ни попытку
  сохранения, ни выбранного нового родителя.
- Если `state.addPparentsData == null` в момент вызова `saveParent()`,
  метод не вызывает `_animalsRepository.update` ни разу, и последнее
  состояние кубита после вызова — `isLoading == true` (то самое значение,
  выставленное первой строкой метода, никогда не сброшенное обратно).
- Ни в одной из двух веток `ReproductionView`/`ReproductionParentModalWidget`
  не показывают пользователю никакого сообщения об ошибке — не через
  `SnackBar`, не через видимый текст на экране.

## Связанные тесты

`test/pages/reproduction_cubit_test.dart`:

- Группа `'UC-116 — ReproductionCubit.saveParent ERROR (известный дефект — тихий отказ)'`
  (текущее имя всё ещё содержит устаревший номер `UC-116` — не
  переименовывать здесь, переименование отдельным проходом), тест
  `'saveParent: update бросает -> Talker.error вызван, isLoading:false, никакого сообщения пользователю'`
  — мокает `animalsRepository.update(any())` на `thenThrow(Exception('db
  error'))`, вызывает `saveParent()` после `load()`, проверяет
  `verify(() => getIt<Talker>().error(any())).called(1)`,
  `cubit.state.isLoading == false`, и `cubit.state.parents == null` (ветка
  (a) этого файла).
- Группа `'UC-116 — ReproductionCubit.saveParent (ранний return, isLoading застревает)'`
  (тот же старый номер в имени, то же замечание про переименование
  отдельным проходом), тест
  `'addPparentsData отсутствует (load() не вызывался) -> ранний return, isLoading остаётся true'`
  — создаёт `ReproductionCubit(_animal(5))` **без** вызова `load()`, вызывает
  `saveParent()` напрямую, проверяет `cubit.state.isLoading == true` и
  `verifyNever(() => animalsRepository.update(any()))` (ветка (b) этого
  файла).

Ни один из двух тестов не проверяет отсутствие видимого пользователю
сообщения об ошибке на уровне виджета (`ReproductionView`/
`ReproductionParentModalWidget`) — оба теста работают напрямую с кубитом,
без `pumpWidget`; вывод о «тихом отказе» в UI сделан этим документом по
чтению `reproduction_view.dart` (нет `BlocListener`, нет чтения
`state.isLoading` в `build`), не закреплён отдельным widget-тестом.

## Открытые вопросы и ограничения

- **Ветка (b) сегодня не создаёт видимого зависшего индикатора загрузки.**
  `state.isLoading` не читается ни в одном `build`-методе
  `ReproductionView`/`ReproductionParentModalWidget` — «экран остаётся в
  состоянии загрузки бессрочно» верно на уровне состояния кубита (важно для
  будущих виджетов, которые могли бы начать читать это поле, и для тестов),
  но не соответствует сегодня никакому наблюдаемому пользователем спиннеру
  или блокировке интерфейса. Не решено этим документирующим файлом, значит
  ли это, что баг менее приоритетен, чем формулировка ENT-11 предполагает —
  вопрос пользователю, если поведение должно измениться в `TARGET`.
- **Реалистичность ветки (b) в продакшене — узкое окно гонки, не
  гарантированный путь.** Единственный правдоподобный сценарий — открыть
  модалку «Сохранить» и нажать «Сохранить» до того, как несколько
  последовательных `await` внутри `ReproductionCubit.load()` (кикнутого не
  дожидаясь в `BlocProvider.create`) успеют завершиться на реальном
  устройстве. Существующий тест воспроизводит ветку (b) искусственно —
  вызывает `saveParent()` вообще без предшествующего `load()`, что
  доказывает существование бага в коде, но не измеряет и не подтверждает
  частоту его реального срабатывания на устройстве пользователя.
- **Ни одна ветка не логирует и не показывает пользователю ЧТО именно
  сломалось.** В ветке (a) `Talker.error(e)` пишет исключение целиком в
  лог, но не различает, например, ошибку constraint БД от любой другой
  причины — сценарий не проверяет, какие конкретно исключения от
  `dao.upd`/Drift реалистичны в проде.
- **Нет теста на уровне виджета**, подтверждающего, что закрытие модалки
  (`context.pop(context)`) в `_ReproductionParentModalWidgetState.build`
  происходит одинаково что при успехе, что при любой из двух ошибочных
  веток — вывод сделан по чтению кода (`context.pop` не обусловлен
  результатом `await saveParent()`), не закреплён `pumpWidget`-тестом,
  который бы фактически кликнул «Сохранить» и проверил закрытие листа.
