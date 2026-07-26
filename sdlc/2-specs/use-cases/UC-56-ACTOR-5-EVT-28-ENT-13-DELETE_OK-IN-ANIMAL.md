- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)

# UC-56 — Пользователь удаляет группу неотправленных перемещений с хаба, удаление успешно

## Назначение

Пользователь удаляет ещё не отправленное на сервер перемещение прямо с экрана
хаба неотправленных перемещений (`UnsentMovementsPage`) — записи там
сгруппированы в одну карточку по ключу (место отправления, место назначения,
время до минуты), кнопка удаления карточки удаляет разом всю группу. Happy-path
сценарий события [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)
(`movement.deleted_unsent`): каждая запись группы физически удаляется из
таблицы `Movements`, и для каждой отдельно — при выполнении условия — откатывается
`Animal.placeId` на `fromId` записи.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Доступ к хабу не требует
авторизации; единственное условие — на устройстве есть хотя бы одна ещё не
синхронизированная (`sync == false`) запись `Movement`.

## CURRENT

### Основной поток

1. Пользователь попадает на экран `UnsentMovementsPage` с экрана «В работе»
   (`EventTilesWidget`, плитка `movement` → `context.pushNamed2(Routes
   .unsentMovements)`, `lib/pages/in_work/in_work_page.dart`). Маршрут
   зарегистрирован в `lib/pages/routes.dart` (`Routes.unsentMovements` →
   `UnsentMovementsPage`).
2. `UnsentMovementsPage.build` создаёт `BlocProvider(create: (context) =>
   UnsentMovementsCubit()..load())`. Конструктор `UnsentMovementsCubit`
   одновременно подписывается на `_movementReportRepository
   .watchNotSyncMovements()` (`MovementReportRepository.watchNotSyncMovements`
   → `MovementsDao.watchAllNotSync`, стрим строк с `sync == false`) — на любую
   эмиссию этого стрима кубит вызывает `_reload()` независимо от содержимого
   эмиссии.
3. И `load()`, и `_reload()` реально показывают данные через отдельный запрос
   `_movementReportRepository.getMovementsWithDetailsByFilters(sync: false)`
   (→ `MovementsDao.getAllMovementsWithDetailsByFilters`) — джойн с местами
   отправления/назначения и данными животного, тот же фильтр `sync == false`.
   Результат эмитится как `UnsentMovementsState.loaded(movements: ...)`, либо
   `.empty()`, если список пуст.
4. `UnsentMovementsView.build` (`state.when(loaded: ...)`) передаёт список в
   `UnsentMovementsPopulated`. `_groupByEvent()` группирует записи по ключу
   `'${movement.fromId}_${movement.placeId}_${HHmm}'`, где время берётся из
   `movement.placeDate ?? movement.createdAt ?? DateTime.now()` — одна карточка
   (`_MovementEventCard`) на группу, с количеством животных (`event.count`) и
   именами мест из джойна.
5. Пользователь нажимает иконку удаления карточки (`Icons.delete_outline`,
   `IconButton.onPressed` в `_MovementEventCard.build`) — без диалога
   подтверждения, немедленно вызывается `onTapDelete()` →
   `onTapDelete(event.movements)` (весь список `MovementWithDetails` этой
   группы) → `UnsentMovementsView`'s `onTapDelete: context.read
   <UnsentMovementsCubit>().deleteGroup`.
6. `UnsentMovementsCubit.deleteGroup(movements)`: единый `try`/`catch` вокруг
   `for`-цикла по списку; для каждого элемента —
   `await _movementReportRepository.delete(m.movement)`, последовательно, в
   порядке списка.
7. `MovementReportRepository.delete` (переопределение
   `BaseRepository<MovementsDao, Movement, $MovementsTable>.delete`): если
   аргумент — `Movement` (а не произвольный `Insertable`), сначала вызывает
   `_rollbackAnimalPlaceFromMovement(item)`, затем безусловно `super.delete
   (item)` → `dao.del(item)` → `BaseDao.del` = `deleteCurrent().delete(item)` —
   физическое удаление строки `Movements` (по совпадению с `item`, в т.ч. по
   `id`).
8. `_rollbackAnimalPlaceFromMovement(movement)`: читает `animalId`/`fromId`/
   `placeId` с записи; если хоть одно из них `null` — выходит без отката (но
   строка всё равно будет физически удалена шагом 7). Иначе —
   `animal = await _animalsRepository.getById(animalId)`
   (`AnimalsRepository.getById` → `dao.getById`); если `animal == null` или
   `animal.placeId != placeId` — тоже выходит без отката (место животного с
   тех пор изменилось чем-то другим). Иначе —
   `await _animalsRepository.updateAnimalPlaceId(animalId, fromId)`, которая
   заново читает животное по `id` и выполняет `dao.upd(animal.copyWith
   (placeId: Value(fromId), updatedAt: const Value.absent()))` — полная
   замена строки `Animal` с новым `placeId`.
9. В этом (happy path) сценарии каждый вызов `repository.delete` в шаге 6
   завершается без исключения — цикл проходит по всем записям группы, откат
   `Animal.placeId` (шаг 8) применяется отдельно к каждой записи по своему
   условию.
10. После того как все строки группы физически удалены, стрим
    `watchNotSyncMovements()` (подписка из шага 2) реагирует на изменение
    таблицы `Movements` и сам вызывает `_reload()` — `deleteGroup` не вызывает
    `load()`/`_reload()` напрямую. Экран обновляется реактивно: удалённая
    группа больше не попадает в новый список (сузившийся по фильтру `sync ==
    false`); если это была последняя оставшаяся группа — состояние переходит
    в `UnsentMovementsState.empty()`.

### Альтернативные потоки

- **У записи отсутствует `animalId`, `fromId` или `placeId`.** Строка
  `Movement` всё равно физически удаляется (шаг 7), но
  `_rollbackAnimalPlaceFromMovement` не трогает `Animal` вовсе — тот же
  переход `DELETE_OK`, но без побочного эффекта на животное.
- **Текущее место животного уже не совпадает с `placeId` записи** (животное с
  момента создания перемещения было перемещено чем-то другим, например
  другой ещё не отправленной записью либо уже синхронизированным
  перемещением). Строка `Movement` всё равно удаляется, откат не выполняется
  — тот же `DELETE_OK`, тот же побочный эффект «без отката».
- **Исключение внутри цикла `deleteGroup`** (например `repository.delete`
  бросает на одной из записей группы) — единый `try`/`catch` кубита ловит его
  целиком, логирует через `Talker` (`getIt<Talker>().error(...)`), не
  пробрасывает; записи группы **до** упавшего вызова уже физически удалены (с
  применённым или пропущенным откатом каждая по своему условию), записи
  **после** него в этом проходе не обрабатываются вовсе — частичный,
  неатомарный результат по группе. Отдельный сценарий, `RESULT =
  DELETE_ERROR`, не описан этим файлом.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — сущность
  сегмента `ENT` в id: каждая запись группы физически удаляется из таблицы
  `Movements` (не мягкое удаление — у `Movement` вообще нет поля вроде
  `isDeleted`).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не сущность
  сегмента `ENT`, но реально изменяется этим сценарием: `placeId` условно
  откатывается на `fromId` удаляемой записи, отдельно для каждого животного
  группы, по независимому условию (шаг 8).

### Бизнес-правила

- Группировка карточек хаба — по `(fromId, placeId, HH:mm)`, не по точному
  времени (секунды/миллисекунды) и не по явному общему идентификатору
  «события перемещения» — такого поля у `Movement` нет, ключ вычисляется на
  лету в `UnsentMovementsPopulated._groupByEvent`.
- Удаление всей карточки — единственное удаление, доступное на этом экране;
  единичное удаление одной записи группы отсюда недостижимо (см. «Открытые
  вопросы»).
- Тап на иконку удаления не показывает диалог подтверждения — эффект
  наступает немедленно по нажатию, без промежуточного шага.
- Откат `Animal.placeId` — per-record, не per-group: у каждой записи группы
  свои `animalId`/`fromId`/`placeId`, поэтому решение «откатывать или нет»
  принимается отдельно для каждого животного группы, а не одним общим
  условием на всю карточку.
- Список, отображаемый на экране, — реактивная проекция таблицы `Movements`
  по фильтру `sync == false`; сам `deleteGroup` не обновляет UI-состояние
  напрямую, полагаясь целиком на подписку `watchNotSyncMovements()` в
  конструкторе кубита.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом на успешную ветку (см.
«Связанные тесты»); находки, перечисленные в «Открытые вопросы и
ограничения», не блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | плитка `movement` (`EventTileData.onTap` → `context.pushNamed2(Routes.unsentMovements)`) | CURRENT | точка входа — переход с экрана «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentMovements` (регистрация маршрута) | CURRENT | маршрут → `UnsentMovementsPage` |
| `lib/pages/animal_movement/presentation/unsent_movement/unsent_movements_page.dart` | `UnsentMovementsPage.build` | CURRENT | создаёт `UnsentMovementsCubit()..load()` |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit` (конструктор, `_watchSubscription`) | CURRENT | реактивная подписка на `watchNotSyncMovements()`, вызывает `_reload()` на любую эмиссию |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.load`, `UnsentMovementsCubit._reload` | CURRENT | загрузка/перезагрузка списка через `getMovementsWithDetailsByFilters(sync: false)` |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.deleteGroup` | CURRENT | эффект [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md) — цикл `repository.delete` по каждой записи группы, единый `try`/`catch` |
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart` | `UnsentMovementsPopulated._groupByEvent`, `_MovementEventCard.build` | CURRENT | группировка по `fromId`+`placeId`+`HH:mm`, иконка удаления вызывает `onTapDelete(event.movements)` без диалога подтверждения |
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_view.dart` | `UnsentMovementsView.build` | CURRENT | подключение `onTapDelete: context.read<UnsentMovementsCubit>().deleteGroup` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.delete` | CURRENT | переопределение `BaseRepository.delete` — сначала откат, затем физическое удаление |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository._rollbackAnimalPlaceFromMovement` | CURRENT | условие отката: `animalId`/`fromId`/`placeId` не `null` и текущий `Animal.placeId == placeId` записи |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | делегирует в `dao.del(item)` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — физическое удаление строки по совпадению с `item` |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.watchAllNotSync`, `MovementsDao.getAllMovementsWithDetailsByFilters` | CURRENT | источник реактивного стрима (шаг 2) и данных для отображения (фильтр `sync == false`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getById`, `AnimalsRepository.updateAnimalPlaceId` | CURRENT | чтение текущего `Animal.placeId` для проверки условия отката и его обновление на `fromId` |

## Критерии приёмки

- Тап по иконке удаления карточки группы немедленно (без диалога
  подтверждения) вызывает `UnsentMovementsCubit.deleteGroup` со всем списком
  `MovementWithDetails` этой группы.
- `deleteGroup` вызывает `MovementReportRepository.delete` ровно один раз на
  каждую запись переданного списка, последовательно, в порядке списка.
- Для записи, у которой заполнены `animalId`, `fromId` и `placeId` и текущий
  `Animal.placeId` всё ещё равен `placeId` записи, `Animal.placeId`
  обновляется на `fromId` этой записи до того, как сама строка `Movement`
  физически удаляется.
- Для записи без `animalId`/`fromId`/`placeId`, либо если текущий
  `Animal.placeId` уже отличается от `placeId` записи, строка `Movement` всё
  равно физически удаляется, а `Animal` не изменяется.
- После успешного удаления всех записей группы кубит не эмитит состояние
  напрямую из `deleteGroup` — обновление списка приходит только через
  реактивную подписку на `watchNotSyncMovements()`.

## Связанные тесты

- `test/pages/unsent_movements_cubit_test.dart`, group `'UC-56 — UnsentMovementsCubit.deleteGroup'` (старая нумерация, переименуется
  отдельным контролируемым проходом — не трогать сейчас), test `'успех ->
  delete вызван для каждого элемента'` — покрывает основной поток на уровне
  кубита: `MovementReportRepository.delete` (мокнутый) вызывается дважды для
  группы из двух записей, без исключения.
- Тот же файл, group `'UC-57 — UnsentMovementsCubit.deleteGroup'` (тоже
  старая нумерация) — покрывает соседний `RESULT = DELETE_ERROR`
  (исключение внутри цикла, лог через `Talker`), не этот файл.
- Тот же файл, group `'НАХОДКА — UnsentMovementsCubit.delete (мёртвый код, не
  вызывается нигде в lib/, см. ENT-9)'` — покрывает единичный метод
  `UnsentMovementsCubit.delete` (не `deleteGroup`); в этот use-case не входит
  — у него нет вызывающего сайта в `lib/` вообще (подтверждено `grep -rn` по
  `lib/` на паттерны вызова этого метода), реальный экран использует только
  `deleteGroup` (см. «Открытые вопросы»). Пометка `ENT-9` в названии группы —
  ссылка на устаревшую (docs-only) нумерацию сущностей, не на текущий
  [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) этого дерева спек.
- TBD — теста нет на уровне репозитория (реальная/in-memory БД, не мок):
  во всех существующих тестах (`unsent_movements_cubit_test.dart`,
  `test/pages/movement_report_cubit_test.dart`) `MovementReportRepository`
  замокан целиком — сама реализация `_rollbackAnimalPlaceFromMovement`
  (чтение `Animal` по `animalId`, сравнение `placeId`, условный `upd`) не
  проверена ни одним тестом, работающим против настоящей таблицы `Animals`.

## Открытые вопросы и ограничения

- **`UnsentMovementsCubit.delete` (единичное удаление одной записи, не
  группы) реализован, обработан тем же паттерном (`try`/`catch` + лог через
  `Talker`) и покрыт тестом, но не имеет ни одного вызывающего сайта в
  `lib/`.** Единственная кнопка удаления на экране (`_MovementEventCard`)
  всегда передаёт `event.movements` — весь список записей группы — в
  `deleteGroup`; удалить одну запись группы, не удаляя всю группу целиком,
  через реальный UI сегодня невозможно.
- **Частичный неатомарный результат группового удаления при отказе одной из
  записей.** `deleteGroup` оборачивает весь `for`-цикл одним `try`/`catch`,
  не per-item: исключение на записи N оставляет записи `0..N-1` уже
  физически удалёнными (с уже применённым или пропущенным откатом каждая),
  а записи `N..конец` — вообще не обработанными в этом проходе. Пользователь
  видит только то, что карточка либо исчезла целиком, либо (при отказе)
  остаётся видимой с частью записей, реально уже удалённых из БД — до
  следующей реакции `watchNotSyncMovements()`, которая перечитает
  укоротившийся список. Не разбирается глубже в рамках этого (`DELETE_OK`)
  файла — относится к соседнему `RESULT = DELETE_ERROR`.
- **Условие отката читает `Animal.placeId` заново отдельным запросом на
  каждую запись группы**, без общей транзакции на уровне `deleteGroup`/
  `MovementReportRepository.delete` — при параллельном изменении того же
  животного чем-то ещё в процессе выполнения цикла (маловероятно в
  однопоточном Flutter-приложении, но не исключено по конструкции кода)
  возможна гонка между чтением условия (шаг 8) и последующим `dao.upd`. Не
  воспроизведено и не разбирается глубже в рамках этого файла.
