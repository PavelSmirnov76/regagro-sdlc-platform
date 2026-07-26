# UC-85 — Пользователь редактирует одно взвешивание (явно из хаба неотправленных или автоматически при повторном взвешивании животного в тот же день), сохранение успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь меняет вес/единицу измерения/результат клинического осмотра уже
существующей записи `AnimalWeighing` и сохраняет правку через
`WeighAnimalCubit.saveEditedWeighing`, без исключения. `WeighAnimalPage` входит
в режим правки одного из двух способов, оба ведут к одному и тому же коду
сохранения и покрываются этим файлом одновременно:

- **явно** — пользователь открывает конкретную запись из хаба неотправленных
  взвешиваний (`UnsentAnimalWeighingsPage`), `animalWeighingId` передаётся в
  `WeighAnimalPageArguments` напрямую;
- **автоматически** — пользователь открывает экран взвешивания для животного
  (`animalId` в аргументах, `animalWeighingId` не передан), и
  `WeighAnimalCubit.initialize` сам находит у этого животного запись за
  сегодняшний день (`_findTodayWeighing`, независимо от `sync`-статуса
  найденной записи) и переводит экран в режим правки без какого-либо явного
  действия пользователя «редактировать».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `WeighAnimalCubit`, ни
`AnimalWeighingsRepository` не проверяют статус авторизации на этом пути
(`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` и
`lib/repositories/animal_weighing/animal_weighings_repository.dart` не находит
ни одного совпадения).

## CURRENT

### Основной поток

**Вход A — явно, из хаба неотправленных.**

1. `UnsentAnimalWeighingsPage` (`lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart`)
   оборачивает `AnimalWeighingsCubit()..loadNotSync()`; в состоянии
   `AnimalWeighingsLoadedNotSync` рендерит `AnimalWeighingListNotSyncWidget`.
2. Тап по строке — `onTap: (aw) async { ... }` вызывает
   `context.pushNamed2<bool?>(Routes.weighAnimal, extra:
   WeighAnimalPageArguments(animalId: aw.animalId, animalWeighingId: aw.id))` —
   оба id заданы явно, и результат навигации ожидается (`await`).

**Вход B — автоматически, при повторном открытии взвешивания для животного.**

1. Экран открывается с `animalId` в аргументах, но без `animalWeighingId` —
   например `AnimalOperationsPage` (`lib/pages/animal_operations/animal_operations_page.dart`,
   `WeighAnimalPageArguments(animalId: animal.animalId)`) или deep-link
   `Routes.animalWeighings` в `lib/pages/main/main_page.dart`
   (`WeighAnimalPageArguments(animalId: extra.animalId!, hideNextAnimalButton:
   true)`) — оба этих вызывающих места не дожидаются (`await`) результата
   навигации.
2. `WeighAnimalPage.build` создаёт `WeighAnimalCubit()..initialize(animalId,
   null, place)` — `animalWeighingId` явно `null`.

**Общее продолжение (оба входа сходятся в `WeighAnimalCubit.initialize`).**

3. `initialize(animalId, animalWeighingId, place)`: грузит `unitsForWeight` и
   `animal = await _animalsRepository.getAnimalWithDetailsById(animalId)`.
   Далее:
   - если `animalWeighingId != null` (вход A) — запись грузится напрямую:
     `todayWeighing = await
     _animalWeighingsRepository.getAnimalWeighingById(animalWeighingId)`;
   - если `animalWeighingId == null` (вход B) — `todayWeighing =
     _findTodayWeighing(animal)`: фильтрует `animal.animalWeighings`
     (заполняется join'ом в `AnimalsDao.getAllAnimalsWithDetailsByFilters` через
     `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
     отсортировано по `weighingDate` по возрастанию) по совпадению
     года/месяца/дня с `DateTime.now()`, берёт последнее совпадение
     (`lastWhereOrNull`) — **без проверки `sync`**, т.е. запись, уже
     синхронизированная ранее сегодня, тоже считается «сегодняшним
     взвешиванием» и открывает режим правки.
4. `_initialAnimalWeighing = todayWeighing` (кэш «как было до правки»); эмитится
   `WeighAnimalState(data: ...copyWith(selectedAnimal: animal, presetAnimalId:
   animal.animalId, selectedAnimalWeighingId: todayWeighing?.id, weight:
   todayWeighing?.weight, isHealthy: todayWeighing?.isHealthy ?? true, units:
   unitsForWeight, selectedUnit: todayWeighing?.unitId != null ? await
   _unitsRepository.getById(todayWeighing!.unitId!) : null, place: place))`.
   Если запись найдена (оба входа при успехе) — `selectedAnimalWeighingId`
   ненулевой, и экран уже в режиме правки к моменту первой отрисовки.
5. `_WeighAnimalWeighingView.build` вычисляет `isEditMode =
   data.selectedAnimalWeighingId != null` — `true`. Это скрывает кнопку «Ещё
   животное» (`showNextAnimalButton` требует `!isEditMode`) и переключает
   поведение кнопки `l10n.finish_label` («Готово») на ветку правки в
   `onFinishTap`.
6. Пользователь меняет вес (ручной ввод/BLE-весы, `updateWeight`), единицу
   измерения (`updateUnit`/`switchUnitOnScale`) и/или отметку здоровья
   (`updateIsHealthy`) — теми же виджетами, что и при создании нового
   взвешивания; ничто в UI явно не подписывает пользователю «вы сейчас
   редактируете уже существующую запись», кроме отсутствия кнопки «Ещё
   животное».
7. Тап «Готово» → `onFinishTap`: поскольку `isEditMode == true`, вызывается
   `cubit.hasEditChanges()`. Если `true` — открывается диалог
   `ConfirmEditWeighDialog` (`showDialog`, `barrierColor:
   Colors.black.withValues(alpha: 0.9)`) с `onSave: cubit.saveEditedWeighing`.
8. `hasEditChanges()`: `initial = _initialAnimalWeighing` (ненулевой на этом
   пути); сравнивает `state.data.isHealthy` с `initial.isHealthy`,
   `state.data.weight ?? initial.weight` с `initial.weight` (допуск `0.000001`
   на double), `state.data.selectedUnit?.id ?? initial.unitId` с
   `initial.unitId` — `true`, если хоть одно из трёх разошлось.
9. Пользователь жмёт «Сохранить» в диалоге →
   `_ConfirmEditWeighDialogState._save()`: `setState(isSaving = true)`, `final
   ok = await widget.onSave()` (т.е. `cubit.saveEditedWeighing()`).
10. `saveEditedWeighing()`: `id = selectedAnimalWeighingId`, `animal =
    selectedAnimal` — оба ненулевые на этом пути (guard пропущен, см.
    «Альтернативные потоки» про недостижимую ветку `return false`). `initial =
    _initialAnimalWeighing`; `weight = state.data.weight ?? initial?.weight`;
    `unitId = state.data.selectedUnit?.id ?? initial?.unitId`; `weighingDate =
    initial?.weighingDate ?? DateTime.now()` — **пользователь не может изменить
    дату/время взвешивания через этот кубит вообще**, значение всегда берётся
    из исходной записи; `remoteId = initial?.remoteId`.
11. Собирается `AnimalWeighingsCompanion(id: Value(id), remoteId: remoteId ==
    null ? const Value.absent() : Value(remoteId), animalId:
    Value(animal.animalId), weight: Value(weight), weighingDate:
    Value(weighingDate), unitId: Value(unitId), sync: const Value(false),
    isHealthy: Value(state.data.isHealthy))`.
12. `await _animalWeighingsRepository.update(updated)` →
    `BaseRepository.update` (`lib/repositories/base_repository.dart`) →
    `dao.upd(item)` → `BaseDao.upd` = `updateCurrent().replace(item)`
    (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — обновляет
    строку `AnimalWeighings` по первичному ключу `id`; не бросает исключение на
    этом пути.
13. При `ok == true`: кубит пересобирает `_initialAnimalWeighing` из уже
    сохранённых значений (`weight`, `unitId`, `isHealthy` — новые; `id`,
    `remoteId`, `animalId`, `weighingDate` — из старого `base`), так что
    следующий вызов `hasEditChanges()` на этом же кубите вернёт `false`.
    `saveEditedWeighing()` возвращает `true`.
14. `_save()`: `isSaving = false, isSaved = true` — `ConfirmEditWeighDialog`
    переключается на успешный вид (текст «Данные сохранены», Lottie-анимация,
    кнопка «Готово»).
15. Тап «Готово» (или закрытие диалога, `onClose` при `isSaved == true`) →
    `widget.onComplete(reloadParent: true)` → в `weigh_animal_page.dart`:
    `Navigator.of(dialogContext).pop()`, затем `await
    cubit.exit(parentShouldReload: true)`.
16. `exit({parentShouldReload: true})`: `reload = parentShouldReload ||
    _pendingParentReload` = `true`; эмитится `state.copyWith(isExit: true,
    parentShouldReload: true)`.
17. `_WeighAnimalView`'s `BlocListener` (`listenWhen: curr.isExit &&
    !prev.isExit`) вызывает `context.pop<bool>(state.parentShouldReload)` —
    страница закрывается, возвращая `true` вызывающему коду.
18. Дальнейшая реакция зависит от входа: только вход A (`UnsentAnimalWeighingsPage`)
    реально ждёт (`await`) результат и при `result == true` вызывает
    `context.read<AnimalWeighingsCubit>().loadNotSync()`, обновляя список —
    отредактированная строка остаётся в хабе неотправленных, потому что
    `sync` после правки снова `false` (см. шаг 11). Вход B
    (`AnimalOperationsPage`, `main_page.dart`) не ожидает результат
    навигации вовсе — правка сохраняется в БД корректно, но ни один экран,
    инициировавший вход B, не реагирует на завершение правки каким-либо
    образом.

### Альтернативные потоки

- **Изменений не было (`hasEditChanges() == false`) на шаге 7.** `onFinishTap`
  сразу вызывает `await cubit.exit()` (без аргументов →
  `parentShouldReload = false`, т.к. `_pendingParentReload` тоже `false` на
  этом пути) — диалог подтверждения не открывается,
  `_animalWeighingsRepository.update` не вызывается вовсе. Формально это ещё
  «успешное» закрытие режима правки, но не `UPDATE_OK` для сущности — БД не
  меняется. Не покрывается этим файлом.
- **`id == null || animal == null` в `saveEditedWeighing`.** Формальный guard
  (`if (id == null || animal == null) return false;`) в практически
  достижимых потоках A/B не срабатывает: `selectedAnimalWeighingId` и
  `_initialAnimalWeighing` выставляются в `initialize` одновременно (оба —
  из одного и того же `todayWeighing`), и никакой другой метод кубита не
  меняет `selectedAnimalWeighingId` без параллельного обновления
  `_initialAnimalWeighing` (`grep -rn "selectedAnimalWeighingId"
  lib/pages/weigh_animal/` — единственное место присвоения, `initialize`,
  строка `selectedAnimalWeighingId: todayWeighing?.id`, ровно там же, где
  выставляется `_initialAnimalWeighing`). Ветка технически реализована и
  покрыта тестом (см. «Связанные тесты»), но не достигается ни из одного
  живого UI-потока.
- **Пользователь выбирает животное через поиск по номеру
  (`searchByNumber`/`tryGetAnimalByNumber` → `selectAnimalForWeighing`), а не
  через `initialize` с готовым `animalId`.** `selectAnimalForWeighing` тоже
  вызывает `_findTodayWeighing(animal)` и предзаполняет `weight`/`isHealthy`
  найденной сегодняшней записью, **но не трогает `selectedAnimalWeighingId`**
  — режим правки автоматически НЕ включается на этом пути, даже если у
  найденного животного уже есть взвешивание за сегодня. Проверено тестом
  `'selectAnimalForWeighing использует вес существующего сегодняшнего
  взвешивания, если оно есть'` (`test/pages/weigh_animal_cubit_test.dart`),
  который проверяет только `weight`/`isHealthy`, не
  `selectedAnimalWeighingId`. Т.е. автоматический вход B (этот файл) доступен
  только когда `animalId` приходит в `WeighAnimalPageArguments` заранее
  (карточка животного, deep-link) — не когда животное находится поиском
  внутри уже открытого экрана взвешивания без предустановленного `animalId`.
- **У животного несколько записей за сегодня** (например уже
  синхронизированная + новая локальная, обе с датой сегодня). `_findTodayWeighing`
  берёт последнюю по `weighingDate` (список отсортирован по возрастанию,
  `lastWhereOrNull`) — более раннее сегодняшнее взвешивание становится
  недоступным для правки этим путём.
- **Отказ от сохранения в диалоге без явного действия** (`onClose` при
  `isSaved == false` → `Navigator.of(context).pop()`) — диалог просто
  закрывается, `saveEditedWeighing` не вызывается, состояние кубита и режим
  правки не меняются, пользователь остаётся на `WeighAnimalPage`. Не этот
  файл.
- **`_save()` при `ok == false`** (`_animalWeighingsRepository.update`
  вернул `false`) — `Navigator.of(context).pop()` закрывает диалог без
  перехода в успешный вид; `RESULT` для этой ветки — не `UPDATE_OK` (нет
  отдельного специфицированного файла на момент написания).
- **`saveEditedWeighing`/`update` бросает исключение** — метод не обёрнут в
  `try/catch` ни в кубите, ни в `_ConfirmEditWeighDialogState._save()`;
  исключение пробрасывается наружу необработанным. `RESULT = UPDATE_ERROR`,
  не этот файл (отдельный use-case на этот путь на момент написания не
  заведён).

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  сущность сегмента `ENT` в id: единственная строка обновляется на месте через
  частичный `AnimalWeighingsCompanion` + `replace()`; `sync` принудительно
  становится `false` независимо от исходного значения, `remoteId` сохраняется
  как был.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается только:
  `animalId` в компаньоне берётся из уже загруженного `selectedAnimal.animalId`
  (тот же животное, экран не даёт переназначить взвешивание на другое
  животное); `animal.animalWeighings` (живой join) используется как источник
  для `_findTodayWeighing`.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — `selectedUnit` подставляется из уже загруженной записи, если
  пользователь не сменил единицу измерения явно.

### Бизнес-правила

- **Дата/время взвешивания не редактируются в этом кубите вообще.**
  `weighingDate` в сохраняемом компаньоне всегда берётся из
  `_initialAnimalWeighing.weighingDate` — даже во входе B (пользователь
  физически взвешивает животное второй раз в тот же день) новое измерение
  просто перезаписывает вес/единицу/здоровье поверх записи с исходным
  временем создания; момент повторного взвешивания нигде не фиксируется.
- **`sync` всегда становится `false` при правке, независимо от исходного
  значения** — включая случай, когда `_initialAnimalWeighing.sync == true`
  (запись уже была отправлена на сервер, найдена входом B). Локально нет
  отдельного признака «это правка уже отправленной записи» (см. ENT-15,
  «Одно логическое состояние на два семантически разных случая»); отличить
  этот случай от «никогда не отправлялась» можно только по `remoteId !=
  null`.
- **`remoteId` явно сохраняется** (`Value(remoteId)` либо `Value.absent()`,
  никогда `Value(null)`) — по факту не имеет значения для семантики
  `replace()` (колонка без `.withDefault(...)`, отсутствие в компаньоне и так
  не сбрасывает значение — см. `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart`,
  только `sync`/`isHealthy` имеют `.withDefault(...)`), но фиксирует намерение
  кода не терять `remoteId` при правке.
- **Следствие для последующей синхронизации (другой актор/событие, не этот
  файл).** Единственный реально вызываемый push-путь
  (`AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`, из
  `DataUpdateBloc`) отправляет батчем все строки с `sync == false` на
  `POST .../weighing-event` (создание), не различая `remoteId == null`/`!=
  null`. Правка уже синхронизированного взвешивания (вход B, запись с
  `remoteId != null`), сохранённая этим сценарием, с высокой вероятностью
  создаст на сервере дубликат при следующем полном sync-проходе, а не
  обновит существующую запись — задокументировано подробнее в
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md).
- Ни `saveEditedWeighing`, ни вызывающий его `_save()` не оборачивают вызов в
  `try/catch` — согласуется с остальными «сохраняющими» путями `AnimalWeighing`
  (см. ENT-15).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — успешная ветка (оба входа A и B) полностью реализована в коде.
Достижимость входа B ограничена конкретными вызывающими экранами
(`AnimalOperationsPage`, deep-link `Routes.animalWeighings` в `main_page.dart`)
— она НЕ включается, если животное для взвешивания находится поиском внутри
уже открытого экрана (см. «Альтернативные потоки»); это не блокирует код, но
сужает практическую достижимость автоматического режима правки.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart` | `UnsentAnimalWeighingsPage.build` (`onTap`) | CURRENT | вход A — явный переход из хаба неотправленных, единственный вызывающий код, ожидающий (`await`) результат навигации |
| `lib/pages/animal_operations/animal_operations_page.dart` | `AnimalOperationsPage.build` (плитка «Взвешивание») | CURRENT | вход B — передаёт только `animalId`, не ждёт результата навигации |
| `lib/pages/main/main_page.dart` | обработчик `Routes.animalWeighings` | CURRENT | вход B (deep-link) — передаёт только `animalId` и `hideNextAnimalButton: true`, не ждёт результата навигации |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `WeighAnimalPageArguments`, `WeighAnimalPage.build`, `_WeighAnimalWeighingView.build` (`isEditMode`, `onFinishTap`), `ConfirmEditWeighDialog`/`_ConfirmEditWeighDialogState._save` | CURRENT | оболочка страницы, вычисление режима правки, UI-триггер сохранения |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.initialize`, `_findTodayWeighing`, `hasEditChanges`, `saveEditedWeighing` | CURRENT | предмет сценария — оба входа сходятся здесь |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_state.dart` | `WeighAnimalData.selectedAnimalWeighingId` | CURRENT | поле-флаг режима правки |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.update`, `getAnimalWeighingById` | CURRENT | персист правки; загрузка записи по id для входа A |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | делегирует в `dao.upd` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings` | CURRENT | схема — только `sync`/`isHealthy` имеют `.withDefault(...)` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` (заполнение `animalWeighings`) | CURRENT | источник `animal.animalWeighings`, используемый `_findTodayWeighing`, отсортирован по `weighingDate` по возрастанию |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | сортировка, от которой зависит выбор `lastWhereOrNull` при нескольких записях за один день |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` | CURRENT | последующий push-путь — не различает создание/правку, риск дубликата для входа B (см. «Бизнес-правила») |

## Критерии приёмки

- Открытие через явный `animalWeighingId` (вход A) и через `animalId` без
  `animalWeighingId`, когда у животного уже есть запись за сегодня (вход B),
  оба приводят к ненулевому `selectedAnimalWeighingId` и заполненному
  `_initialAnimalWeighing` ещё до какого-либо действия пользователя.
- `hasEditChanges()` возвращает `false` сразу после загрузки (ничего не
  расходится с `_initialAnimalWeighing`) и `true`, как только вес (с допуском
  `0.000001`), единица измерения или отметка здоровья отличаются от исходных
  значений.
- Успешное сохранение вызывает `AnimalWeighingsRepository.update` ровно один
  раз с `AnimalWeighingsCompanion`, чей `id` равен исходному
  `selectedAnimalWeighingId`, `sync.value == false`, и `remoteId` —
  `Value.absent()`, если исходный `remoteId` был `null`, иначе `Value(remoteId)`
  с тем же значением.
- После успешного сохранения `saveEditedWeighing()` возвращает `true`, а
  следующий вызов `hasEditChanges()` на том же кубите возвращает `false`.
- UI: успешный вид `ConfirmEditWeighDialog` по тапу «Готово» вызывает
  `cubit.exit(parentShouldReload: true)`; страница закрывается, возвращая
  `true`; хаб неотправленных (единственный ожидающий результат вызывающий код)
  перезагружает список по этому `true`.

## Связанные тесты

- `test/pages/weigh_animal_cubit_test.dart`, group `'UC-85 — WeighAnimalCubit.hasEditChanges/saveEditedWeighing'`
  (старая нумерация, переименуется отдельным контролируемым проходом — не
  трогать сейчас):
  - test `'hasEditChanges — без выбранного взвешивания -> false; изменение
    веса/юнита/здоровья -> true'` — покрывает вход A (`initialize(1, 77,
    null)` с замоканным `getAnimalWeighingById(77)`) и переход
    `hasEditChanges()` из `false` в `true` после `updateWeight`.
  - test `'saveEditedWeighing — id/animal не заданы -> false, репозиторий не
    вызывается'` — покрывает guard-ветку, недостижимую из живого UI (см.
    «Альтернативные потоки»); `verifyNever(() =>
    animalWeighingsRepository.update(any()))`.
  - test `'saveEditedWeighing — успех -> update() вызван с новыми
    значениями, internal-состояние синхронизировано'` — прямое покрытие этого
    файла: захватывает `AnimalWeighingsCompanion` (`captured.id.value == 77`,
    `captured.weight.value == 55`), проверяет `result == true` и
    `cubit.hasEditChanges() == false` после сохранения.
- **TBD — теста нет** на вход B (`WeighAnimalCubit.initialize(animalId, null,
  place)`, когда мокнутый `getAnimalWithDetailsById` возвращает
  `AnimalWithDetails` с непустым `animalWeighings`, содержащим запись за
  сегодня) — существующий тест группы `'WeighAnimalCubit.initialize'`
  (`'животное без взвешивания сегодня -> ...'`) использует фабрику `_animal(id)`
  без `animalWeighings` вовсе, т.е. проверяет только пустую ветку
  `_findTodayWeighing`. Единственный тест, где `animalWeighings` непустой и
  содержит сегодняшнюю запись (`'selectAnimalForWeighing использует вес
  существующего сегодняшнего взвешивания, если оно есть'`), идёт через
  `selectAnimalForWeighing`, не через `initialize`, и не проверяет
  `selectedAnimalWeighingId` — сам факт входа B (автоматический переход в
  режим правки именно через `initialize`) в тестах не зафиксирован.
- **TBD — теста нет** на сценарий «несколько записей за сегодня» —
  `_findTodayWeighing` берёт последнюю по `weighingDate`, но ни один тест не
  строит фикстуру с двумя сегодняшними записями для одного животного.

## Открытые вопросы и ограничения

- **Асимметрия между `initialize` и `selectAnimalForWeighing`.** Только вход
  через `WeighAnimalCubit.initialize` с готовым `animalId` (вход B) включает
  автоматический режим правки; поиск животного внутри уже открытого экрана
  (`selectAnimalForWeighing`) предзаполняет вес/здоровье из сегодняшней записи,
  но не режим правки. Осознанное разделение (взвешивание нескольких животных
  подряд через поиск не должно молча становиться правкой) или недосмотр — не
  зафиксировано в коде явно, только выводится из наблюдаемого поведения.
- **Молчаливая перезапись даты/времени взвешивания.** Вход B по определению
  означает, что пользователь физически взвешивает животное второй раз в
  тот же день — но фактическое время этого повторного измерения нигде не
  сохраняется, `weighingDate` остаётся от первой записи. Не отражено ни в UI
  (нет предупреждения «вы редактируете более раннюю запись»), ни в модели.
- **Риск серверного дубликата для входа B.** Правка уже синхронизированного
  взвешивания (найденного входом B по `_findTodayWeighing` без проверки
  `sync`) сбрасывает `sync` в `false`; единственный реальный push-путь не
  различает создание/правку по протоколу — см. «Бизнес-правила» и
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md). Этот файл
  фиксирует только локальный `UPDATE_OK`; последствия на сервере — предмет
  отдельного (ещё не заведённого) use-case на стороне SYSTEM/sync-прохода.
- **Два вызывающих экрана входа B не реагируют на результат навигации
  вовсе** (`AnimalOperationsPage`, `main_page.dart`) — в отличие от входа A,
  где хаб неотправленных явно перезагружает список. Не баг сам по себе (эти
  экраны не хранят список, требующий обновления), но асимметрия стоит иметь
  в виду при дальнейшей работе с этими вызывающими местами.
