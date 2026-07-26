# UC-83 — Пользователь взвешивает одно или несколько животных подряд — успех

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гость или
авторизованный, одинаково) взвешивает одно животное или несколько подряд через
`WeighAnimalCubit`/`WeighAnimalPage`, вручную либо через подключённые по
Bluetooth весы, и подтверждает сохранение всей накопленной за визит партии.
Поток двухфазный: `saveCurrentWeighingStayOnPage()` стейджит по одной записи в
память (`state.data.createdAnimalWeighings`) на каждое взвешенное животное, не
трогая БД; `saveWeighing()` — единственная точка, реально пишущая партию в
БД, вызывается один раз, когда пользователь подтверждает завершение визита.
Happy-path сценарий события [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)
(`animal_weighing.recorded`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения. `WeighAnimalCubit` (`lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart`)
не импортирует и не использует `AuthRepository` нигде в файле — взвешивание,
как и перемещение/вакцинация, local-first: доступно одинаково гостю и
авторизованному пользователю, сохранение не делает ни одного сетевого вызова.
В отличие даже от `Vaccination` (у которой есть неиспользуемое поле `author`),
у `AnimalWeighing` ([ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md))
в схеме таблицы вовсе нет колонки, привязывающей запись к создавшему её
пользователю.

## CURRENT

### Основной поток

1. Экран открывается одним из трёх живых входов, ведущих к созданию новой
   записи (четвёртый вход — из хаба неотправленных взвешиваний,
   `unsent_animal_weighings_page.dart`, — передаёт `animalWeighingId` явно и
   ведёт к правке, не к этому сценарию):
   - `OperationsPage` (плитка «Взвешивание» для места) →
     `WeighAnimalPageArguments(place: place)` — `animalId` не передан, это
     единственный вход, реально дающий групповой батч «несколько животных
     подряд»;
   - `AnimalOperationsPage` (плитка «Взвешивание» для конкретного животного) →
     `WeighAnimalPageArguments(animalId: animal.animalId)`;
   - `_MainContentState._onFabPressed`, ветка `Routes.animalWeighings` (FAB на
     экране истории взвешиваний животного) →
     `WeighAnimalPageArguments(animalId: extra.animalId!, hideNextAnimalButton: true)`.
   Для обоих входов с заданным `animalId` `WeighAnimalPage.build` вычисляет
   `hideNextAnimalButton: arguments?.animalId != null || (arguments?.hideNextAnimalButton ?? false)`
   — т.е. кнопка «Следующее животное» скрыта всегда, когда животное
   предзадано, независимо от третьего параметра.
2. `WeighAnimalCubit` создаётся в `BlocProvider.create` и сразу вызывает
   `initialize(arguments?.animalId, arguments?.animalWeighingId, arguments?.place)`.
3. `WeighAnimalCubit.initialize`: грузит `unitsForWeight`
   (`UnitsRepository.getUnitsForWeight`); если `animalId` задан — грузит
   животное (`AnimalsRepository.getAnimalWithDetailsById`). Если животное
   найдено:
   - резолвит «сегодняшнее взвешивание» — либо явно по
     `animalWeighingId` (`AnimalWeighingsRepository.getAnimalWeighingById`),
     либо автоматически через `_findTodayWeighing(animal)` (последнее по
     дате взвешивание с датой, равной сегодняшней, среди
     `animal.animalWeighings` — DB-снапшот, вложенный в `AnimalWithDetails` на
     момент чтения животного, `AnimalsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`);
   - если такое взвешивание найдено — заполняет `selectedAnimalWeighingId`,
     `weight`, `isHealthy`, `selectedUnit` из него: экран **молча** переходит
     в режим правки (см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md),
     «Режим правки определяется автоматически») — это уже сценарий
     [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md), не этот
     use-case, но достижим из тех же двух входов с предзаданным `animalId`,
     если у животного уже есть взвешивание за сегодня.
   - если `animalId` не задан (групповой вход) — просто заполняет
     `units`/`place`, `selectedAnimal`/`number` — `null`.
4. Для группового входа: пользователь ищет/сканирует животное по номеру
   (`ScannerWidget`/`AnimalNumberBannerField`) → `searchByNumber`/
   `tryGetAnimalByNumber` → `getAnimals(number)` (фильтрует по
   `place.idRemote`, если задан) → при ровно одном совпадении —
   `selectAnimalForWeighing(animal)`. Этот метод тоже вызывает
   `_findTodayWeighing(animal)` для только что выбранного животного и, если
   находит — предзаполняет `weight`/`isHealthy` из него (без установки
   `selectedAnimalWeighingId`, это поле в групповом входе никогда не
   заполняется), иначе — берёт вес из последнего BLE-показания
   (`lastScaleReading`), если не в ручном режиме и вес ещё не зафиксирован.
5. Пользователь вводит вес вручную (`updateWeight`) либо через BLE-весы
   (`initBleScale` подключается автоматически при открытии страницы;
   `readings`-стрим автообновляет `weight`, пока `!isManualMode &&
   !isWeightFixed`), выбирает единицу измерения (`updateUnit`/
   `switchUnitOnScale`), отмечает результат клинического осмотра
   (`updateIsHealthy`). Кнопка «Взвесить» (`fixWeight`) фиксирует текущий вес
   (`isWeightFixed: true`) — до этого момента `hasPendingWeighing` (UI) ложен.
6. Пользователь нажимает «Следующее животное»
   (`_WeighAnimalWeighingViewState.onNextAnimalTap`, видна только когда
   `hasSelectedAnimal && !isEditMode && (hasResultsToSave || isFixed) &&
   !hideNextAnimalButton`): если `hasPendingWeighing` (животное выбрано **и**
   вес зафиксирован) — вызывает `cubit.saveCurrentWeighingStayOnPage()`; при
   успехе — `cubit.selectNextAnimalForWeighing()` (сбрасывает
   `selectedAnimal`/`number`/`weight`/`isWeightFixed`/`isHealthy`, оставляя
   список, место и единицы).
7. `WeighAnimalCubit.saveCurrentWeighingStayOnPage()`:
   - эмитит `isLoading: true`;
   - guard-проверки по порядку: животное выбрано → иначе `'Животное не
     выбрано'`; `weight != null && weight > 0` → иначе
     `'operations__weighing_error_weight_invalid'`; единица резолвится как
     `selectedUnit ?? units.first` → иначе `'field_required'`. Любой отказ —
     `_emitError(...)`, `createdAnimalWeighings` не меняется, метод
     возвращает `false`.
   - при успехе: `todayWeighingId = _findTodayWeighing(currentData.selectedAnimal!)?.id`
     (та же DB-снапшот-проверка, что и на шаге выбора животного, повторно, на
     тот же снапшот `animal.animalWeighings`); строит
     `AnimalWeighing(id: currentData.selectedAnimalWeighingId ?? todayWeighingId ?? -1, animalId:, weight:, unitId:, weighingDate: DateTime.now(), sync: false, isHealthy:)`
     — `-1` — сентинел «ещё не вставлено» для этого визита;
   - кладёт эту запись в `createdAnimalWeighings` через `_upsertWeighing`
     (заменяет по `animalId`, если такой уже застейджен — список не может
     содержать два элемента с одним и тем же `animalId`);
   - сбрасывает форму (`weight: null, isWeightFixed: false, isHealthy: true,
     number: null`, `selectedUnit` — резолвленная единица, не сбрасывается) и
     эмитит **новый** `WeighAnimalState(data: newData)` (не `state.copyWith`)
     — тем самым неявно сбрасывает `isLoading`/`error`/`isExit`/
     `parentShouldReload` к значениям по умолчанию;
   - возвращает `true`.
8. Шаги 4–7 повторяются столько раз, сколько животных пользователь хочет
   взвесить за один визит — это и есть суть EVT-42 «одно или несколько
   животных подряд».
9. Пользователь нажимает «Завершить»
   (`onFinishTap`, видна когда `isEditMode || hasResultsToSave ||
   (!isEditMode && hasPendingWeighing)`; в этом сценарии `isEditMode` ложен).
   Если `hasPendingWeighing` — сначала вызывает
   `cubit.saveCurrentWeighingStayOnPage()` для текущего невыгруженного
   животного (последняя запись визита), затем открывает
   `ConfirmSaveWeighDialog(data: cubit.state.data, onSave: () async =>
   cubit.saveWeighing(), onExit: ...)`.
10. `ConfirmSaveWeighDialog` (`_confirmSaveWidget`) показывает сводку:
    `l10n.animals_weighed_count(createdAnimalWeighings.length)` и
    `l10n.healthy_unhealthy_count(healthyAnimalsCount, unhealthyAnimalsCount)`
    (геттеры `WeighAnimalDataExtension`, считают по
    `animalWeighing.isHealthy` внутри застейдженного списка).
11. Пользователь нажимает «Подтвердить» →
    `_ConfirmSaveWeighDialogState.saveWeighing()`:
    ```dart
    void saveWeighing() async {
      setState(() { isSaving = true; });
      await widget.onSave();
      setState(() { isSaving = false; isSaved = true; });
    }
    ```
    `widget.onSave` — `() async => cubit.saveWeighing()`: тело — выражение,
    само являющееся `Future<void>` от вызова `cubit.saveWeighing()`; для
    `async`-функции с телом-выражением это означает, что внешний `Future`
    резолвится только после реального завершения `cubit.saveWeighing()`
    (сплющивание вложенного `Future`, а не постановка в очередь без
    ожидания). **В отличие от аналогичных диалогов Vaccination/Movement**
    ([UC-63](UC-63-ACTOR-5-EVT-32-ENT-14-CREATE_OK-IN-ANIMAL.md),
    [UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md), где лямбда —
    блок с `bloc.add(...)` без `await`/без возврата `Future`), здесь
    `await widget.onSave()` реально дожидается, пока цикл сохранения внутри
    `saveWeighing()` (шаг 12) отработает — переход в `isSaved: true`
    корректно отражает, что запись в БД уже завершена.
12. `WeighAnimalCubit.saveWeighing()`:
    ```dart
    Future<void> saveWeighing() async {
      for (final item in state.data.createdAnimalWeighings) {
        if (item.animalWeighing.id != -1) {
          await _animalWeighingsRepository.update(
            AnimalWeighingsCompanion(
              id: Value(item.animalWeighing.id),
              animalId: Value(item.animalWeighing.animalId),
              weight: Value(item.animalWeighing.weight),
              weighingDate: Value(item.animalWeighing.weighingDate),
              unitId: Value(item.animalWeighing.unitId),
              sync: const Value(false),
              isHealthy: Value(item.animalWeighing.isHealthy),
            ),
          );
        } else {
          await _animalWeighingsRepository.insert(
            AnimalWeighingsCompanion.insert(
              animalId: item.animalWeighing.animalId,
              weight: item.animalWeighing.weight,
              weighingDate: item.animalWeighing.weighingDate,
              unitId: Value(item.animalWeighing.unitId),
              sync: const Value(false),
              isHealthy: Value(item.animalWeighing.isHealthy),
            ),
          );
        }
      }
      _pendingParentReload = state.data.createdAnimalWeighings.isNotEmpty;
      emit(WeighAnimalState(data: state.data));
    }
    ```
    Для каждого застейдженного элемента, последовательно, `await`-ится ровно
    один вызов репозитория: `id != -1` → `update` (`BaseRepository.update` →
    `dao.upd` → `updateCurrent().replace(item)`, PK-based replace — колонки,
    отсутствующие в `Companion` (здесь — `remoteId`, без значения по
    умолчанию), в SQL `UPDATE` не участвуют и остаются в БД без изменений);
    `id == -1` → `insert` (`BaseRepository.insert` → `dao.ins` →
    `insertOrReplace`, обычная вставка с автоинкрементом при отсутствующем
    `id`, `remoteId` остаётся `NULL`). Оба варианта явно передают
    `sync: Value(false)`. Ни один сетевой вызов не выполняется. Исключения
    из этого цикла не перехватываются (см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)
    — не относится к этому, успешному, use-case).
13. После цикла: `_pendingParentReload = state.data.createdAnimalWeighings.isNotEmpty`
    (список к этому моменту не изменялся с начала цикла — фактически
    оценивается на том же наборе, что был обработан) — в этом сценарии
    всегда `true`, поскольку диалог открывается только когда партия непуста.
    Эмитится **новый** `WeighAnimalState(data: state.data)` — тот же `data`,
    но, как и в шаге 7, все прочие поля состояния (`isLoading`, `error`,
    `isExit`, `parentShouldReload`) сбрасываются к значениям по умолчанию.
    `createdAnimalWeighings` **не очищается**.
14. Диалог переключается на `_successSaveWidget` (Lottie-анимация, кнопка
    «Готово»). Пользователь нажимает «Готово» → `onExit` (передан из
    `_WeighAnimalWeighingViewState.onFinishTap`):
    `Navigator.of(dialogContext).pop()` (закрывает диалог), затем
    `await cubit.exit()`.
15. `WeighAnimalCubit.exit({bool parentShouldReload = false})`:
    `reload = parentShouldReload || _pendingParentReload` → `true`
    (параметр не передан явно из этого колбэка, но `_pendingParentReload`
    уже `true` после шага 13); эмитит `state.copyWith(isExit: true,
    parentShouldReload: true)`.
16. `_WeighAnimalView`'s `BlocListener` (`listenWhen: curr.isExit &&
    !prev.isExit`) → `context.pop<bool>(state.parentShouldReload)` —
    закрывает `WeighAnimalPage`, возвращая вызывающему экрану `true`
    (сигнал «нужно перезагрузить данные»).

### Альтернативные потоки

- **Одно предзаданное животное (`animalId` задан, `hideNextAnimalButton`
  всегда `true`)**: кнопка «Следующее животное» никогда не показывается —
  батч этого визита физически ограничен одной записью. Остальной поток
  (стейджинг → диалог подтверждения → `saveWeighing`) идентичен.
- **У одного из выбранных животных уже есть взвешивание за сегодня в БД** (из
  более раннего, отдельного визита/сохранения того же дня, не из текущей
  in-memory партии): `_findTodayWeighing` при выборе/стейджинге этого
  животного находит существующую строку, `todayWeighingId` — не `null` →
  застейдженная запись получает `id != -1` → в шаге 12 для этого животного
  выполняется `update`, а не `insert`. Один вызов `saveWeighing()` может дать
  **смешанную** партию (часть — новые вставки, часть — обновления уже
  существующих сегодняшних строк), без какого-либо UI-индикатора, какие
  именно животные попали в какую ветку. `sync` в обоих случаях всё равно
  переустанавливается в `false` — обновлённая ранее синхронизированная
  строка снова помечается «требует отправки» (см.
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), тот же
  инвариант).
- **Повторный стейджинг того же животного до финального сохранения**: если
  пользователь снова находит/выбирает уже застейдженное в этой партии
  животное (по номеру) и жмёт «Следующее животное»/«Завершить» ещё раз,
  `_upsertWeighing` заменяет прежний элемент списка новым (по `animalId`) —
  в партию попадает только последняя версия записи для этого животного, а
  не обе. Позиция элемента в списке при этом смещается в конец (порядок
  `createdAnimalWeighings` — не строго порядок первого взвешивания, если
  животное перевзвешивалось повторно в рамках визита).
- **Текущее (ещё не зафиксированное) животное молча выпадает из партии.**
  И `onNextAnimalTap`, и `onFinishTap` вызывают
  `cubit.saveCurrentWeighingStayOnPage()` только если `hasPendingWeighing`
  (`hasSelectedAnimal && isFixed`) истинно. Если пользователь выбрал
  животное, ввёл вес, но не нажал «Взвесить» (`isWeightFixed` остаётся
  `false`) и сразу нажимает «Следующее животное» (кнопка уже видна, если в
  партии уже есть другие записи — `hasResultsToSave`) или «Завершить», это
  животное **не стейджится и без предупреждения теряется** — форма просто
  сбрасывается (`selectNextAnimalForWeighing`) или сразу открывается диалог
  подтверждения без него. `saveCurrentWeighingStayOnPage()` сама по себе не
  проверяет `isWeightFixed` (только `weight != null && weight > 0`), но оба
  живых вызывающих места вызывают её лишь при уже истинном `isFixed`, так
  что этот собственный гейт метода сегодня недостижим отдельно от гейта на
  уровне UI.
- **Гость / нет текущей сессии**: поведение и результат идентичны —
  `WeighAnimalCubit` не читает `AuthRepository` вовсе; у `AnimalWeighing`
  нет поля, которое отличало бы гостя от авторизованного пользователя.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)
  (AnimalWeighing) — сущность, совершающая переход: по одной новой либо
  обновлённой строке на каждый уникальный `animalId`, застейдженный к
  моменту `saveWeighing()`, все — с `sync: false`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только на
  чтение: резолв конкретного животного (`getAnimalWithDetailsById`) и поиск
  кандидатов для группового входа
  (`searchAllAnimalsWithDetailsByNumbersAndName`); встроенный снапшот
  `animal.animalWeighings` используется для детекта «взвешивания за
  сегодня». Этим сценарием ни одно поле `Animal` не пишется.
- `Unit` ([ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md),
  HANDBOOKS) — единица измерения веса, только читается
  (`UnitsRepository.getUnitsForWeight`/`getById`).
- `Place`/`Farm` (модуль FARM, [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)/
  [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)) — только на чтение, для
  фильтрации доступных животных группового входа по `place.idRemote`; этим
  сценарием не изменяются.

### Бизнес-правила

- Одна запись `AnimalWeighing` на одно уникальное `animalId` за визит —
  `_upsertWeighing` не даёт партии содержать две записи для одного и того же
  животного одновременно.
- Сохранение полностью локальное: ни `saveCurrentWeighingStayOnPage`, ни
  `saveWeighing` не делают ни одного сетевого вызова и не проверяют
  состояние сети.
- `sync: false` устанавливается явно в обеих ветках (`insert`/`update`) — та
  же семантика, что и у прочих локальных мутаций взвешивания (см.
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)).
- Выбор `insert` против `update` для конкретного животного определяется не
  UI-намерением пользователя («создаю новую запись»), а тем, нашёл ли
  `_findTodayWeighing` для этого животного уже существующую сегодняшнюю
  строку в БД на момент выбора/стейджинга — то же автоматическое,
  необъявленное пользователю переключение режима, что описано у
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) для одиночного
  предзаданного входа, только здесь оно происходит по каждому животному
  батча независимо, через локальную переменную `todayWeighingId` внутри
  `saveCurrentWeighingStayOnPage`, а не через `selectedAnimalWeighingId`
  (это поле в групповом входе не заполняется вовсе).
- Валидность веса (`> 0`) и резолв единицы измерения (`selectedUnit ??
  units.first`, иначе отказ) проверяются один раз на каждое животное — в
  момент стейджинга (`saveCurrentWeighingStayOnPage`), не повторно в момент
  финального `saveWeighing()`.
- Число животных в одном визите ничем не ограничено на уровне кода —
  зависит только от того, сколько раз пользователь пройдёт цикл
  поиск/выбор → ввод веса → «Взвесить» → «Следующее животное», пока не
  нажмёт «Завершить».
- `createdAnimalWeighings` не очищается после успешного `saveWeighing()` —
  на практике не имеет значения, поскольку следом сразу вызывается `exit()`,
  закрывающий страницу (и вместе с ней — `WeighAnimalCubit`), но при
  гипотетическом повторном вызове `saveWeighing()` на том же экземпляре
  cubit'а все уже сохранённые записи были бы обработаны (вставлены/
  обновлены) повторно.
- Цикл `for` внутри `saveWeighing()` await-ит каждый вызов репозитория
  последовательно, без общей транзакции на весь батч — технический сбой
  посередине оставил бы часть партии сохранённой, часть — нет (см. сценарий
  `CREATE_ERROR`, не описываемый здесь).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (включая по-настоящему групповой батч из нескольких
разных животных, единственный реально дающий его вход — `OperationsPage` с
`place`) полностью реализован и работает как описано в CURRENT; находки,
перечисленные в «Открытые вопросы и ограничения», не блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/operations/operations_page.dart` | `OperationsPage` | CURRENT | вход №1 — единственный, дающий реально групповой батч (`animalId` не передан) |
| `lib/pages/animal_operations/animal_operations_page.dart` | `AnimalOperationsPage` | CURRENT | вход №2 — одно предзаданное животное |
| `lib/pages/main/main_page.dart` | `_MainContentState._onFabPressed` (ветка `Routes.animalWeighings`) | CURRENT | вход №3 — FAB на экране истории взвешиваний животного, `hideNextAnimalButton: true` явно |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `WeighAnimalPageArguments`, `WeighAnimalPage.build` | CURRENT | сборка аргументов, `hideNextAnimalButton` вычисляется из `animalId`, немедленный вызов `initialize` в `BlocProvider.create` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.initialize` | CURRENT | резолв животного, детект сегодняшнего взвешивания, молчаливое переключение в режим правки |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit._findTodayWeighing` | CURRENT | поиск взвешивания за сегодня среди DB-снапшота `animal.animalWeighings` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.getAnimals`, `.searchByNumber`, `.tryGetAnimalByNumber`, `.selectAnimalForWeighing`, `.selectNextAnimalForWeighing` | CURRENT | поиск/выбор животного для батча (групповой вход) |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.updateWeight`, `.updateUnit`, `.updateIsHealthy`, `.initBleScale`, `.fixWeight`, `.resetWeight`, `.switchUnitOnScale`, `.switchToManualInput` | CURRENT | заполнение формы (ручной ввод/BLE-весы) |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveCurrentWeighingStayOnPage` | CURRENT | guard-проверки, построение `AnimalWeighing`, стейджинг через `_upsertWeighing` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit._upsertWeighing` | CURRENT | dedupe застейдженной партии по `animalId` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveWeighing` | CURRENT | ядро сценария — цикл `insert`/`update` по всей застейдженной партии |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.exit` | CURRENT | эмит `isExit`/`parentShouldReload`, учитывает `_pendingParentReload` |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_state.dart` | `WeighAnimalData`, `WeighAnimalDataExtension.healthyAnimalsCount`/`unhealthyAnimalsCount` | CURRENT | форма/состояние; сводка для диалога подтверждения |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_with_details.dart` | `AnimalWeighingsWithDetails` | CURRENT | форма застейдженного в памяти элемента (`animalWeighing` + `unit`) |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `ConfirmSaveWeighDialog`, `_ConfirmSaveWeighDialogState.saveWeighing` | CURRENT | диалог подтверждения; `await widget.onSave()` реально дожидается `cubit.saveWeighing()` (в отличие от аналогичных диалогов VAC/MOVE) |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `_WeighAnimalWeighingViewState.build` (`onNextAnimalTap`, `onFinishTap`) | CURRENT | связка UI-кнопок с методами cubit'а, гейт по `hasPendingWeighing` |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `_WeighAnimalView.build` (`BlocListener` по `isExit`) | CURRENT | закрытие страницы, `context.pop<bool>(state.parentShouldReload)` |
| `lib/repositories/base_repository.dart` | `BaseRepository.insert`, `BaseRepository.update` | CURRENT | делегируют в `dao.ins`/`dao.upd`; `AnimalWeighingsRepository` не переопределяет ни один из них |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins`, `BaseDao.upd` | CURRENT | `insertOrReplace` (новая строка при отсутствующем `id`); `updateCurrent().replace(item)` (PK-based replace, отсутствующие в `Companion` колонки без default не входят в SQL `UPDATE`) |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings`, `AnimalWeighingsCompanion` | CURRENT | схема таблицы: `id` autoincrement, `remoteId` nullable без default, `sync`/`isHealthy` со значениями по умолчанию |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao` (метод, строящий `AnimalWithDetails.animalWeighings` через `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`) | CURRENT | источник DB-снапшота «сегодняшних» взвешиваний животного для `_findTodayWeighing` |

## Критерии приёмки

- По каждому уникальному `animalId`, застейдженному в
  `createdAnimalWeighings` к моменту вызова `saveWeighing()`, выполняется
  ровно один вызов репозитория — `insert`, если `id == -1`, либо `update`,
  если `id != -1`, — с `sync.value == false`.
- Суммарное число вызовов `insert` + `update` за один `saveWeighing()` равно
  `createdAnimalWeighings.length` на момент вызова.
- `saveCurrentWeighingStayOnPage()` не изменяет `createdAnimalWeighings`, пока
  не выбрано животное, вес не положителен или единица измерения не
  резолвится — в каждом из этих трёх случаев возвращает `false` и не
  вызывает ни один репозиторий.
- Повторный стейджинг уже застейдженного в этой партии `animalId` заменяет
  прежнюю запись, а не добавляет вторую — итоговый список не может содержать
  дубликат по `animalId`.
- Ни `saveCurrentWeighingStayOnPage`, ни `saveWeighing` не выполняют ни
  одного сетевого вызова.
- После успешного `saveWeighing()` и последующего `exit()` (нажатие «Готово»
  в диалоге подтверждения) `parentShouldReload == true`, если партия была
  непустой на момент вызова `saveWeighing()`.

## Связанные тесты

- `test/pages/weigh_animal_cubit_test.dart`, group
  `'UC-83 — WeighAnimalCubit.saveWeighing (офлайн)'`, test `'успех ->
  AnimalWeighing(sync:false) вставлена, сетевой вызов не происходит'` —
  покрывает основной поток этого use-case для партии из одного животного:
  стейджинг + `saveWeighing()`, проверка, что `insert` вызван ровно один раз
  с ожидаемыми `animalId`/`weight`/`sync:false`, а `update` не вызывается ни
  разу. Имя группы использует старую нумерацию (`UC-113`) — не
  переименовывается в рамках этого файла.
- `test/pages/weigh_animal_cubit_test.dart`, group `'WeighAnimalCubit.exit'`,
  test `'parentShouldReload не передан, но saveWeighing ранее сохранил хотя
  бы одно взвешивание -> parentShouldReload:true'` — покрывает последний
  критерий приёмки (шаги 13–15 основного потока), тоже только для партии из
  одного животного.
- **TBD — теста нет** на партию из **нескольких разных** животных за один
  `saveWeighing()` (собственно «несколько животных подряд» из названия
  события) — ни один существующий тест не стейджит больше одного `animalId`
  перед вызовом `saveWeighing()`.
- **TBD — теста нет** на ветку `update` внутри `saveWeighing()` (случай, когда
  `_findTodayWeighing` находит уже существующую сегодняшнюю строку и
  `saveCurrentWeighingStayOnPage` присваивает `id != -1`) — покрыт только
  инсерт-путь.
- **TBD — теста нет** на dedupe-поведение `_upsertWeighing` (повторный
  стейджинг того же `animalId` до финального сохранения).
- **TBD — теста нет** на связку `ConfirmSaveWeighDialog`/
  `_WeighAnimalWeighingViewState` (widget-уровень) — в частности, на факт,
  что `await widget.onSave()` реально дожидается завершения
  `cubit.saveWeighing()` (отмечено как код-ридинг наблюдение, не
  воспроизведено тестом).

## Открытые вопросы и ограничения

- **Автоматическое, необъявленное переключение insert/update по каждому
  животному батча.** Если у выбранного животного уже есть строка
  `AnimalWeighing` за сегодня (из более раннего отдельного визита), партия
  этого визита обновит её вместо того, чтобы создать новую, без какого-либо
  сигнала об этом в UI — пользователь не может отличить по интерфейсу,
  какие животные в его партии реально создали новую запись, а какие
  перезаписали существующую сегодняшнюю. См. тот же инвариант в
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) для одиночного
  предзаданного входа — здесь он повторяется независимо на уровне каждого
  элемента группового батча.
- **Молчаливая потеря текущего, не зафиксированного взвешивания.** Если
  пользователь ввёл вес для выбранного животного, но не нажал «Взвесить»
  (`isWeightFixed` остаётся `false`), а затем нажимает «Следующее животное»
  или «Завершить» (обе кнопки могут быть уже видны из-за ранее
  застейдженных животных), это животное не попадает в партию без какого-либо
  предупреждения — см. «Альтернативные потоки». Не воспроизведено отдельным
  тестом.
- **`createdAnimalWeighings` не сбрасывается после успешного
  `saveWeighing()`.** Практически не имеет значения, поскольку `exit()`
  сразу закрывает страницу и cubit вместе с ней, но при гипотетическом
  повторном вызове `saveWeighing()` на том же экземпляре все уже сохранённые
  записи были бы обработаны повторно (для строк с уже присвоенным `id` —
  повторный, идемпотентный `update`; но `id`, полученный от `insert` в
  первом проходе, в `createdAnimalWeighings` никогда не записывается назад —
  так что при таком гипотетическом повторе элементы, вставленные как новые в
  первом проходе, во втором проходе снова пошли бы по ветке `insert` с
  `id == -1`, создав дубликаты). Не воспроизведено тестом, не разбирается
  глубже — путь недостижим из текущего UI (кнопка диалога — одноразовая).
- **`isSaving` в `_ConfirmSaveWeighDialogState` — мёртвое состояние**,
  выставляется, но не читается в `build()` — тот же паттерн, что и в
  аналогичных диалогах Vaccination/Movement
  ([UC-63](UC-63-ACTOR-5-EVT-32-ENT-14-CREATE_OK-IN-ANIMAL.md),
  [UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md)).
- **Отсутствие транзакции на весь батч.** Цикл `for` в `saveWeighing()`
  await-ит каждый `insert`/`update` по отдельности, без общей транзакции —
  технический сбой в середине партии (не описываемый в этом, успешном,
  use-case) оставил бы часть застейдженных записей сохранёнными, часть —
  нет.
