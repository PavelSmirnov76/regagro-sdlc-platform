# UC-57 — Удаление группы неотправленных перемещений отказывает: `UnsentMovementsCubit.deleteGroup` перехватывает исключение молча, без пользовательского сообщения об ошибке

## Назначение

Документирует ERROR-исход события [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)
(`movement.deleted_unsent`): пользователь удаляет карточку-группу ещё не
отправленных перемещений с экрана хаба «неотправленных», и вызов репозитория,
удаляющий одну из записей группы, бросает исключение. `UnsentMovementsCubit.deleteGroup`
перехватывает это исключение общим `try/catch`, логирует его через `Talker` и
завершается как обычный успех — ни пользовательского сообщения об ошибке, ни
изменения состояния кубита для этого случая не существует. Экран, вызвавший
удаление, не дожидается результата `Future`, возвращаемого `deleteGroup`,
поэтому даже если бы кубит эмитил ошибочное состояние, наблюдать его было бы
некому.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — действие доступно и гостю, и
авторизованному пользователю одинаково: хаб неотправленных перемещений не
проверяет статус авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает экран хаба неотправленных перемещений
   (`UnsentMovementsPage` →
   `lib/pages/animal_movement/presentation/unsent_movement/unsent_movements_page.dart`),
   который через `UnsentMovementsView` подписывается на `UnsentMovementsCubit`
   и в состоянии `loaded` рендерит `UnsentMovementsPopulated`
   (`lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart`).
2. `UnsentMovementsPopulated._groupByEvent` группирует
   `List<MovementWithDetails>` в карточки `_MovementEvent` по составному
   ключу `'${fromId}_${placeId}_$timeKey'` (`timeKey` — время до минуты,
   `DateFormat('HHmm')`) — одна карточка представляет несколько записей
   `Movement`, у которых совпадают место отправления, место назначения и
   минута перемещения.
3. Пользователь нажимает иконку удаления на карточке
   (`_MovementEventCard`, `IconButton(icon: Icons.delete_outline, onPressed:
   onTapDelete)`), где `onTapDelete = () => onTapDelete(event.movements)` —
   передаёт наверх весь список `MovementWithDetails` этой карточки.
4. `UnsentMovementsView`
   (`lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_view.dart`)
   подключает этот колбэк напрямую к кубиту:
   `onTapDelete: context.read<UnsentMovementsCubit>().deleteGroup` — вызов
   не оборачивается в `await`, `try/catch` или `.catchError(...)` на
   стороне виджета; `Future<void>`, возвращаемый `deleteGroup`, полностью
   игнорируется UI-слоем.
5. `UnsentMovementsCubit.deleteGroup(movements)`
   (`lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart`):
   ```dart
   Future<void> deleteGroup(List<MovementWithDetails> movements) async {
     try {
       for (final m in movements) {
         await _movementReportRepository.delete(m.movement);
       }
     } catch (e) {
       getIt<Talker>().error('deleteGroup: error: $e');
     }
   }
   ```
   один `try/catch` оборачивает **весь** цикл — не отдельную итерацию.
6. `MovementReportRepository.delete`
   (`lib/repositories/movement_report/movement_report_repository.dart`)
   переопределяет базовый метод: сначала (если `item is Movement`) вызывает
   `_rollbackAnimalPlaceFromMovement(item)`, затем `super.delete(item)` →
   `dao.del(item)` (`BaseRepository.delete` →
   `packages/sheep_farm_database/lib/entities/base_dao.dart`,
   `BaseDao.del` → `deleteCurrent().delete(item)`, обычный Drift-вызов).
7. В этом сценарии один из вызовов внутри `delete` (либо
   `_animalsRepository.getById`/`updateAnimalPlaceId` внутри отката, либо
   сам `dao.del`) бросает исключение — например ошибка Drift/SQLite или
   исключение из мока в тесте (`Exception('db error')`).
8. Исключение всплывает из `_movementReportRepository.delete(m.movement)`
   внутри цикла `for` в `deleteGroup` и прерывает цикл — все элементы
   `movements`, идущие в списке **после** упавшего, не проходят через
   `delete` вовсе, даже попытки не предпринимается.
9. `catch (e)` в `deleteGroup` перехватывает исключение и вызывает
   `getIt<Talker>().error('deleteGroup: error: $e')` — только сообщение
   исключения, без стектрейса. Исключение не перевыбрасывается
   (`rethrow` отсутствует) — `deleteGroup` возвращает нормально
   завершившийся `Future<void>`.
10. `UnsentMovementsState` (`part` файл
    `unsent_movements_state.dart`) — закрытый freezed-union из четырёх
    вариантов: `initial`, `loading`, `loaded(movements)`, `empty`. Варианта
    для ошибки не существует вовсе — `deleteGroup` в принципе не может
    эмитить состояние-ошибку, даже если бы захотел.
11. Поскольку шаг 4 не дожидается `Future` от `deleteGroup`, а
    `UnsentMovementsCubit` не эмитит после `deleteGroup` вообще ничего
    напрямую — единственный способ, которым экран узнаёт об изменении
    списка, это реактивная подписка в конструкторе кубита:
    `_movementReportRepository.watchNotSyncMovements().listen((_) =>
    _reload())`, где `watchNotSyncMovements` → `dao.watchAllNotSync()`
    (`packages/sheep_farm_database/lib/entities/movement/movement_dao.dart`)
    — реактивный Drift-запрос `(select(movements)..where((t) =>
    t.sync.equals(false))).watch()`.
12. Итог: пользователь нажимает иконку удаления и не получает никакого
    сигнала о произошедшем сбое — ни снэкбара, ни индикации загрузки, ни
    изменения состояния экрана специально под ошибку. Единственное
    наблюдаемое пользователем следствие — карточка на экране может
    визуально измениться (см. «Альтернативные потоки», партиальное
    удаление) или остаться как есть, в зависимости от того, на каком
    элементе цикла произошёл сбой.

### Альтернативные потоки

- **Партиальное удаление группы.** Если исключение бросается не на первом
  элементе `movements`, то предыдущие элементы группы к этому моменту уже
  успешно удалены отдельными `await`-вызовами (`delete` не обёрнут в общую
  Drift-транзакцию на уровне `deleteGroup`) — эти удаления не откатываются
  при последующем исключении. Реактивный `watchAllNotSync()` (шаг 11
  основного потока) увидит изменившийся набор строк и вызовет `_reload()`,
  так что карточка на экране перерисуется с уменьшенным числом животных
  (`event.count`) или исчезнет вовсе, если удалились все её записи, кроме
  одной, на которой всё остановилось. Пользователь не может отличить этот
  случай от «удаление одной записи из группы было каким-то намеренным
  частичным действием» — сообщения об ошибке по-прежнему нет.
- **Исключение внутри отката `Animal.placeId`, а не при самом удалении
  строки.** `MovementReportRepository.delete` вызывает
  `_rollbackAnimalPlaceFromMovement(item)` **до** `super.delete(item)`. Если
  исключение бросается уже после того, как `_animalsRepository.updateAnimalPlaceId(animalId,
  fromId)` внутри отката успешно выполнилась, но до/во время `dao.del(item)`
  — животное к этому моменту уже откатилось на `fromId`, а сама запись
  `Movement` при этом **не удалена** и остаётся в хабе неотправленных как
  ни в чём не бывало. Это рассинхронизация между [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)
  (Animal.placeId уже откачен) и [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)
  (запись перемещения формально ещё существует и не отправлена) — см.
  «Открытые вопросы».
- **`UnsentMovementsCubit.delete` (единичное удаление, не групповое) —
  симметричный, но отдельный метод.** Тот же паттерн
  try/catch-с-логированием-без-rethrow существует и для одиночного удаления
  одной записи (`delete(MovementWithDetails movement)`), но, в отличие от
  `deleteGroup`, этот метод нигде не вызывается из `lib/` (проверено
  поиском по дереву — единственный подключённый в UI колбэк, `onTapDelete`
  в `unsent_movements_view.dart`, ведёт на `deleteGroup`, не на `delete`).
  Не входит в этот сценарий — отдельная, не документируемая здесь находка.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — сегмент
  `ENT` имени файла; сущность, чьё удаление отказывает. При отказе строка
  (или её часть, для остальных элементов группы) остаётся в БД
  неудалённой.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — `placeId`
  которого пытается откатить `_rollbackAnimalPlaceFromMovement` до
  фактического удаления строки `Movement`; при отказе на позднем шаге
  отката (см. «Альтернативные потоки») откат может состояться, даже когда
  сама запись `Movement` не удаляется.

### Бизнес-правила

- Один `try/catch` в `deleteGroup` оборачивает весь цикл, не итерацию —
  первое же исключение останавливает обработку всех оставшихся элементов
  группы без индивидуального отчёта по каждому.
- Перехваченное исключение только логируется (`Talker.error`,
  без стектрейса) и не пробрасывается — вызывающая сторона (`UnsentMovementsView`)
  не может отличить успешное завершение группы от отказавшего технически,
  потому что оба случая возвращают один и тот же нормально завершившийся
  `Future<void>`.
- `UnsentMovementsState` не содержит варианта для ошибки — архитектурно
  `deleteGroup` не имеет способа сообщить об отказе через состояние
  кубита, даже если бы вызывающий код дожидался результата.
- Порядок операций внутри `MovementReportRepository.delete` (сначала откат
  `Animal.placeId`, затем удаление строки `Movement`) означает, что откат
  может «пережить» отказавшее удаление самой строки — эти две операции не
  атомарны относительно друг друга.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик полностью прослеживается чтением кода, включая
факт, что вызывающий UI не дожидается результата и не может среагировать на
ошибку в принципе. Единственный незакрытый разрыв — отсутствие теста на
партиальное удаление группы (когда исключение бросается не на первом
элементе) — зафиксирован в «Открытые вопросы и ограничения» и в «Связанные
тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/presentation/unsent_movement/unsent_movements_page.dart` | `UnsentMovementsPage` | CURRENT | точка входа экрана хаба неотправленных перемещений |
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_view.dart` | `UnsentMovementsView` (`onTapDelete: context.read<UnsentMovementsCubit>().deleteGroup`) | CURRENT | подключает удаление карточки к кубиту без `await`/обработки результата |
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart` | `UnsentMovementsPopulated._groupByEvent`, `_MovementEventCard` (`IconButton(onPressed: onTapDelete)`) | CURRENT | группировка записей в карточку и кнопка удаления всей группы |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.deleteGroup` | CURRENT | цикл по группе, один `try/catch`, лог через `Talker`, без rethrow |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_state.dart` | `UnsentMovementsState` (`initial`/`loading`/`loaded`/`empty`) | CURRENT | freezed-union без варианта ошибки |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.delete`, `_rollbackAnimalPlaceFromMovement` | CURRENT | откат `Animal.placeId` перед удалением строки; источник исключения, перехватываемого в `deleteGroup` |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | `dao.del(item)` — базовая реализация, которую переопределяет `MovementReportRepository.delete` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — реальный Drift-вызов, способный бросить исключение |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.watchAllNotSync`, `MovementsDao.getAllNotSync` | CURRENT | реактивный запрос, лежащий в основе `watchNotSyncMovements`/`_reload` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getById`, `AnimalsRepository.updateAnimalPlaceId` | CURRENT | читает/обновляет `Animal.placeId` внутри отката, вызываемого до удаления строки `Movement` |

## Критерии приёмки

- При вызове `deleteGroup(movements)`, если `MovementReportRepository.delete`
  бросает исключение на любом элементе `movements`, `deleteGroup` завершает
  свой `Future<void>` без исключения (`completes`, а не `throwsA(...)`).
- Исключение логируется ровно один раз через `getIt<Talker>().error(...)`.
- Ни один элемент `movements`, идущий в списке после упавшего, не проходит
  через `MovementReportRepository.delete` в рамках того же вызова
  `deleteGroup`.
- Ни в одном состоянии `UnsentMovementsState`, ни в UI не появляется
  сообщение об ошибке — с точки зрения интерфейса результат неотличим от
  `DELETE_OK`, если ни одна запись не была успешно удалена, и от частичного
  `DELETE_OK`, если часть записей группы успела удалиться до сбоя.

## Связанные тесты

`test/pages/unsent_movements_cubit_test.dart`, group `'UC-57 — UnsentMovementsCubit.deleteGroup'`, test `'отказ -> залогировано через
Talker, исключение не пробрасывается'`: мок
`movementReportRepository.delete(any())` бросает `Exception('db error')`,
`await expectLater(cubit.deleteGroup([_movement()]), completes)` проверяет
отсутствие проброса, `verify(() => getIt<Talker>().error(any())).called(1)`
проверяет факт логирования. Соседний OK-тест того же файла, group `'UC-56 — UnsentMovementsCubit.deleteGroup'`, покрывает успешный путь (`delete`
вызывается для каждого элемента группы).

**TBD — теста нет** на партиальное удаление группы (список из нескольких
элементов, где исключение бросается не на первом) — существующий ERROR-тест
проверяет только группу из одного элемента, поэтому не демонстрирует, что
предыдущие успешно удалённые элементы группы остаются удалёнными, а
последующие — нет.

**TBD — теста нет** на уровне виджета/страницы (`UnsentMovementsView`,
`UnsentMovementsPopulated`) — весь существующий тест только на уровне
кубита; факт, что UI не дожидается `Future` от `deleteGroup` и поэтому не
может показать ошибку, выведен чтением кода `unsent_movements_view.dart`, а
не отдельным виджет-тестом.

## Открытые вопросы и ограничения

- **Откат `Animal.placeId` не атомарен с удалением строки `Movement`.**
  `MovementReportRepository.delete` вызывает
  `_rollbackAnimalPlaceFromMovement(item)` до `super.delete(item)` — если
  исключение бросается между успешным откатом и успешным удалением строки
  (или во время самого `dao.del`), `Animal.placeId` уже откачен на
  `fromId`, но запись `Movement` остаётся в БД и продолжает отображаться в
  хабе неотправленных как «ещё не удалённая». Специального теста на этот
  подслучай нет — выведено чтением кода.
- **Нет способа отличить полный успех, частичный успех и полный отказ
  `deleteGroup` ни в одном состоянии кубита, ни в UI.** Все три исхода
  возвращают один и тот же нормально завершившийся `Future<void>`, и
  единственная видимая пользователю обратная связь — косвенная, через
  реактивный пересчёт списка (`watchNotSyncMovements`), а не через
  осознанный сигнал об ошибке.
- **Вызывающий UI не дожидается результата `deleteGroup` в принципе**
  (`onTapDelete: context.read<UnsentMovementsCubit>().deleteGroup` без
  `await`) — даже если бы `UnsentMovementsState` завтра получил вариант
  ошибки, текущий `_MovementEventCard`/`UnsentMovementsPopulated` не
  подписан на него никаким `BlocListener`/`BlocConsumer` в этом дереве
  виджетов, и потребовал бы отдельного изменения, не входящего в рамки
  этого документирующего прохода (TARGET == CURRENT).
- Нужно ли когда-либо сделать удаление группы атомарным (единая
  транзакция на всю группу с полным откатом при частичном отказе), и
  нужно ли добавлять вариант ошибки в `UnsentMovementsState` с
  пользовательским сообщением — вопросы будущего TARGET-прохода, не
  разрешаются в рамках этой чисто документирующей задачи.
