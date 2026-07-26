- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md)

# UC-58 — Пользователь удаляет перемещение с экрана дневного отчёта, удаление успешно

## Назначение

Пользователь удаляет ещё не отправленные перемещения с экрана дневного отчёта
о перемещении, открытого из хаба «неотправленных» (`isUnsent: true`).
Happy-path сценарий события
[EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md)
(`movement.deleted_via_report`): все ещё не отправленные записи, подходящие
под фильтр день + место отправления + место назначения, удаляются физически,
без исключения, с попыткой отката `Animal.placeId` по каждой записи
индивидуально. Тот же метод репозитория с откатом, что и у
[EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md), но вызванный
через отдельный, независимо написанный путь (`MovementReportCubit.deleteEvent`,
а не `UnsentMovementsCubit.deleteGroup`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `MovementReportCubit`, ни
`MovementReportRepository` не проверяют `AuthRepository.isAuthorized()` на
этом пути.

## CURRENT

### Основной поток

1. Точка входа — тап по карточке группы перемещений в хабе «неотправленных»
   (`_MovementEventCard.onTap` внутри
   `UnsentMovementsPopulated.build`,
   `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart`)
   → `context.pushNamed2(Routes.movementReport, extra:
   MovementReportPageArgs(date: event.date, fromPlaceId: event.fromId,
   toPlaceId: event.toId, fromPlaceName: ..., toPlaceName: ..., isUnsent:
   true))`. Карточки в этом хабе сгруппированы более узко, чем фильтр
   удаления на следующем экране — ключ группировки здесь
   `'${fromId}_${placeId}_${DateFormat('HHmm').format(date)}'`, то есть с
   точностью до минуты (см. «Бизнес-правила»).
2. `MovementReportPage` (`lib/pages/movement_report/presentation/movement_report_page.dart`)
   рендерит `MovementReportView`.
3. `MovementReportView.build`
   (`lib/pages/movement_report/presentation/widgets/movement_report_view.dart`)
   читает `MovementReportPageArgs` через
   `GoRouterState.of(context).getExtraByName<MovementReportPageArgs>(Routes.movementReport)`,
   создаёт `BlocProvider(create: (context) => MovementReportCubit()..load(args))`.
4. Поскольку `args.isUnsent == true`, `EventReportScaffold.actions` содержит
   `MoreMenuWidget` с единственным действием `MoreMenuAction(title:
   l10n.delete, onTap: () => _confirmAndDelete(context, args))`. Если бы
   экран был открыт из общего календаря (без `isUnsent`, по умолчанию
   `false`) — `actions: null`, пункт меню отсутствовал бы вовсе (см.
   «Альтернативные потоки»).
5. Пользователь открывает меню, нажимает «Удалить» → `_confirmAndDelete`
   показывает `AlertDialog` (`showDialog`) с заголовком `l10n.delete`,
   текстом `l10n.movement`, кнопками «Отмена» (`l10n.cancel`,
   `Navigator.of(dialogContext).pop()`) и «Удалить» (текст красным).
6. Пользователь подтверждает — обработчик кнопки «Удалить»: сначала
   `Navigator.of(dialogContext).pop()` (закрывает диалог), затем `await
   context.read<MovementReportCubit>().deleteEvent(args)`, затем, если
   `context.mounted` — `context.pop()` (закрывает сам экран отчёта,
   безусловно, независимо от того, было ли реально что удалено).
7. `MovementReportCubit.deleteEvent(args)` — всё тело обёрнуто в
   `try {...} catch (_) {}`, без rethrow и без изменения состояния кубита ни
   при успехе, ни при ошибке (см. «Открытые вопросы»).
8. `day = DateUtils.dateOnly(args.date)`.
9. `all = await _movementRepo.getMovementsWithDetailsByFilters(sync: false)`
   — заново, независимо от того, что было загружено на шаге `load()` (тот
   вызывал тот же метод с `sync: null`), выбирает из БД все ещё не
   отправленные (`sync: false`) перемещения с join на `Place`/`Animal`
   (`MovementsDao.getAllMovementsWithDetailsByFilters`).
10. Фильтр `toDelete`: для каждой записи `date = m.movement.placeDate ??
    m.movement.createdAt`; если `date == null` — запись исключается; иначе
    запись входит в `toDelete`, если `DateUtils.dateOnly(date)` совпадает с
    `day` **и** `m.movement.fromId == args.fromPlaceId` **и**
    `m.movement.placeId == args.toPlaceId`. Время суток (`HH:mm`) не
    сравнивается вовсе — только календарный день (см. «Бизнес-правила»).
11. Для каждой записи `m` из `toDelete`, последовательно, в цикле `for`:
    `await _movementRepo.delete(m.movement)` →
    `MovementReportRepository.delete` (override):
    - `_rollbackAnimalPlaceFromMovement(item)`: если `animalId`, `fromId`
      или `placeId` записи — `null`, откат не выполняется, метод завершается
      без изменений. Иначе — `animal = await
      _animalsRepository.getById(animalId)`; если `animal == null` или
      `animal.placeId != placeId` (животное с тех пор уже перемещено
      куда-то ещё) — откат не выполняется. Иначе —
      `_animalsRepository.updateAnimalPlaceId(animalId, fromId)`, что читает
      животное по id и делает `dao.upd(animal.copyWith(placeId:
      Value(fromId), updatedAt: Value.absent()))`.
    - `super.delete(item)` → `BaseRepository.delete` → `dao.del(item)` →
      drift `deleteCurrent().delete(item)` — физическое удаление строки по
      первичному ключу (`Movements` не имеет колонки мягкого удаления вовсе —
      `id`/`remoteId`/`guid`/`userId`/`animalId`/`placeId`/`placeDate`/
      `createdAt`/`updatedAt`/`fromId`/`sync` — полный список колонок,
      `isDeleted` среди них нет).
12. Цикл проходит по всем записям `toDelete` без исключения (happy path
    этого сценария) → `deleteEvent` завершается без выброса ошибки во
    внешний `try`/`catch`.
13. Обратно на UI: `await` в шаге 6 разрешается, `context.mounted` истинно →
    `context.pop()` закрывает экран отчёта целиком. Сам `MovementReportCubit`
    не перечитывает и не переэмитит своё состояние после удаления — экран
    закрывается сразу, не показывая обновлённый (пустой) список.
14. Экран-источник — хаб «неотправленных» (`UnsentMovementsCubit`) — узнаёт
    об удалении не через прямой вызов от `MovementReportCubit`, а
    реактивно: конструктор `UnsentMovementsCubit` подписан на
    `_movementReportRepository.watchNotSyncMovements()`
    (`lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart`),
    и физическое удаление строк на шаге 11 эмитит новое значение потока drift
    по таблице `Movements`, что триггерит `_reload()` хаба независимо от
    того, что произошло на экране отчёта.

### Альтернативные потоки

- **Тот же день открыт из общего календаря отчётов**
  (`ReportsDayListPopulated._navigateItem`, кейс `MovementDayItem`,
  `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`)
  — `MovementReportPageArgs` создаётся без `isUnsent` (значение по умолчанию
  `false`), поэтому на шаге 4 `actions: null` — пункт меню «Удалить» не
  показывается вовсе, весь экран read-only для этого пути. Не сценарий
  этого файла — не `EVT-29` совсем (тут `deleteEvent` не может быть вызван
  из UI).
- **В подходящих под фильтр день+места перемещениях несколько разных
  времён** (например два перемещения в один день между теми же местами, но
  в разное время) — оба удаляются в одном вызове `deleteEvent`, потому что
  фильтр на шаге 10 не сравнивает `HH:mm`. Это шире, чем сама карточка,
  которую пользователь тапнул на шаге 1 (там ключ группировки включает
  `HHmm`) — то есть удаление через отчёт может затронуть перемещения,
  которые на экране хаба визуально относились к другой карточке того же дня
  и тех же мест. Зафиксировано в тесте как явная находка (см. «Связанные
  тесты»).
- **У записи нет `animalId`, `fromId` или `placeId`** —
  `_rollbackAnimalPlaceFromMovement` возвращается без отката, но сама
  запись всё равно физически удаляется шагом `super.delete(item)`
  следующей строкой того же вызова `delete`.
- **`animal.placeId` уже не равен `placeId` этой записи** (животное с тех
  пор переместили ещё раз чем-то другим) — откат не выполняется по той же
  причине, что и в [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md);
  запись всё равно удаляется физически.
- **`toDelete` — пустой список** (ни одна ещё не отправленная запись не
  подошла под фильтр) — цикл на шаге 11 не выполняется ни разу,
  `deleteEvent` завершается без единого вызова `delete`; тот же успешный
  (без исключения) выход, что и happy path, просто без побочного эффекта.
- **Исключение при чтении (`getMovementsWithDetailsByFilters`) или при
  каком-то из вызовов `delete` в середине цикла** — ловится внешним
  `catch (_) {}`, ошибка нигде не логируется и не отражается в состоянии
  кубита; если исключение произошло не на первой итерации, записи,
  удалённые до него, остаются удалёнными (частичный эффект без отката уже
  случившихся удалений) — отдельный сценарий (`RESULT = DELETE_ERROR`), не
  описанный этим файлом.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — сущность
  сегмента `ENT` в id: удаляемые записи, переход «существует» → физически
  удалена (без промежуточного мягкого состояния — у таблицы нет колонки
  `isDeleted`).
- `Animal` (модуль ANIMAL, [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md))
  — `placeId` условно откатывается на `fromId` удаляемой записи, по каждой
  записи независимо.
- `Place` (модуль FARM) — только на чтение, через join
  (`fromPlace`/`toPlace` в `MovementWithDetails`) для отображения названий
  мест в отчёте и в карточке хаба; этим сценарием не изменяется.

### Бизнес-правила

- Кнопка удаления гейтится исключительно флагом `args.isUnsent`,
  переданным вызывающим экраном, а не каким-либо запросом к репозиторию —
  один и тот же виджет `MovementReportView` обслуживает и read-only путь из
  общего календаря, и путь с удалением из хаба неотправленных.
- Фильтр удаления — день + место отправления + место назначения, без учёта
  времени суток — грубее, чем ключ группировки карточек в самом хабе
  (`fromId_placeId_HHmm`), и грубее, чем аналогичный сценарий
  `DisposalReportCubit.deleteEvent` (тот дополнительно сверяет `HH:mm`).
  Следствие: удаление, вызванное с одной конкретной карточки хаба, может
  затронуть и записи, отображавшиеся в хабе отдельной карточкой того же дня
  между теми же местами, но в другое время.
- Удаление — всегда физическое (`deleteCurrent().delete`), не мягкое:
  `Movements` не имеет колонки, аналогичной `Place.isDeleted`.
- Откат `Animal.placeId` — по каждой удаляемой записи независимо, с двумя
  проверками (все три поля записи не `null`; текущее место животного всё
  ещё равно `placeId` записи) — тот же механизм, что и у
  [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md), но
  вызванный отдельно написанным кодом (`MovementReportCubit.deleteEvent`
  вместо `UnsentMovementsCubit.deleteGroup`), не общей функцией.
- После успешного завершения `deleteEvent` сам экран отчёта не перечитывает
  своё состояние — он безусловно закрывается (`context.pop()`).
  Актуальность списка на предыдущем экране обеспечивается его собственной
  реактивной подпиской на `watchNotSyncMovements()` (хаб неотправленных), а
  не явным вызовом от `MovementReportCubit`.
- `deleteEvent` не делает различий между «ничего не найдено для удаления» и
  «что-то удалено» — оба случая завершаются одинаково успешно (без
  исключения), UI не показывает разного результата ни в том, ни в другом
  случае.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и работает как описано в
CURRENT; находки, перечисленные в «Открытые вопросы и ограничения», не
блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart` | `UnsentMovementsPopulated.build`, `_MovementEventCard.onTap` | CURRENT | точка входа — тап по карточке группы в хабе неотправленных, переход на `Routes.movementReport` с `isUnsent: true`; ключ группировки карточки — `fromId_placeId_HHmm` |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` (кейс `MovementDayItem`) | CURRENT | альтернативная точка входа из общего календаря — тот же экран, но без `isUnsent` (по умолчанию `false`); пункт меню удаления не показывается |
| `lib/pages/movement_report/presentation/movement_report_page.dart` | `MovementReportPage` | CURRENT | точка входа маршрута `Routes.movementReport` |
| `lib/pages/movement_report/presentation/widgets/movement_report_view.dart` | `MovementReportView.build` | CURRENT | читает `MovementReportPageArgs` через `getExtraByName`, создаёт `MovementReportCubit`, показывает пункт меню «Удалить» только при `args.isUnsent` |
| `lib/pages/movement_report/presentation/widgets/movement_report_view.dart` | `MovementReportView._confirmAndDelete` | CURRENT | `AlertDialog` подтверждения; по «Удалить» — `await cubit.deleteEvent(args)`, затем `context.pop()` при `context.mounted` |
| `lib/widgets/go_router/go_router_state.dart` | `GoRouterState.getExtraByName` | CURRENT | извлекает `MovementReportPageArgs` из `extra` навигации |
| `lib/widgets/more_menu/more_menu_widget.dart` | `MoreMenuWidget`, `MoreMenuAction` | CURRENT | UI-меню с единственным пунктом «Удалить» |
| `lib/pages/movement_report/data/movement_report_data.dart` | `MovementReportPageArgs` | CURRENT | `date`, `fromPlaceId`, `toPlaceId`, `isUnsent` — параметры фильтра и гейт видимости кнопки удаления |
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.deleteEvent` | CURRENT | эффект [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md) — повторная выборка `sync: false`, фильтр по дню/местам без учёта времени, цикл удаления; `try`/`catch (_) {}` без изменения состояния |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | `sync: false` — только ещё не отправленные записи, с join на `Place`/`Animal` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.delete` | CURRENT | override — сначала `_rollbackAnimalPlaceFromMovement`, затем `super.delete` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository._rollbackAnimalPlaceFromMovement` | CURRENT | условный откат `Animal.placeId` на `fromId` записи |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getById`, `AnimalsRepository.updateAnimalPlaceId` | CURRENT | чтение текущего животного и запись отката `placeId` |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | делегирует в `dao.del` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — физическое удаление строки по первичному ключу |
| `packages/sheep_farm_database/lib/entities/movement/movement.dart` | `Movements` | CURRENT | таблица без колонки мягкого удаления |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.getAllMovementsWithDetailsByFilters`, `MovementsDao.watchAllNotSync` | CURRENT | join с `Place` (`fromId`/`placeId`) и `Animal`, фильтр `sync`; поток, на который реактивно подписан хаб неотправленных |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit` (подписка на `watchNotSyncMovements`, `_reload`) | CURRENT | экран-источник этого сценария — реактивно узнаёт об удалении через drift-поток, не через прямой вызов от `MovementReportCubit` |
| `lib/l10n/app_ru.arb` | `delete`, `movement`, `cancel` | CURRENT | локализованные строки диалога подтверждения |

## Критерии приёмки

- Пункт меню «Удалить» показывается только когда `MovementReportPageArgs.isUnsent
  == true` (путь из хаба неотправленных); при открытии того же дня из
  общего календаря (`isUnsent == false`) пункт меню отсутствует.
- Подтверждение диалога вызывает `deleteEvent(args)`, которое заново
  выбирает все `sync: false` перемещения и включает в удаление те, для
  которых `DateUtils.dateOnly(date) == day && fromId == args.fromPlaceId &&
  placeId == args.toPlaceId`, без сравнения времени суток.
- Каждая подходящая запись удаляется физически (`delete`); таблица
  `Movements` не имеет колонки мягкого удаления.
- Для каждой удаляемой записи: если `animalId`, `fromId` и `placeId` не
  `null`, и текущий `Animal.placeId` всё ещё равен `placeId` записи —
  `Animal.placeId` откатывается на `fromId`; в противном случае (любое из
  полей `null`, либо место животного уже не совпадает) откат не
  выполняется, но запись всё равно удаляется.
- Если ни одна запись не подошла под фильтр — `deleteEvent` завершается без
  единого вызова `delete` и без исключения (тот же успешный исход).
- По завершении без исключения экран отчёта закрывается (`context.pop()`)
  безусловно, не перечитывая собственное состояние.
- Хаб неотправленных отражает удаление реактивно, через подписку на
  `watchNotSyncMovements()`, не через явный вызов от `MovementReportCubit`.

## Связанные тесты

- `test/pages/movement_report_cubit_test.dart`, group `'UC-58 — MovementReportCubit.deleteEvent'` (старая нумерация), test `'НАХОДКА:
  удаляет по дате+fromId+placeId БЕЗ проверки точного времени — ...'` —
  основной happy path этого сценария: подтверждает, что записи одного дня
  между теми же местами удаляются вместе независимо от времени (шаг 10), а
  записи с другим местом назначения или другим днём — нет
  (`verifyNever`). В этом тесте `MovementReportRepository.delete`
  замокан целиком (`thenAnswer((_) async => 1)`), поэтому сам откат
  `Animal.placeId` внутри `_rollbackAnimalPlaceFromMovement` этим тестом не
  проверяется — только факт вызова `repository.delete(...)` с ожидаемыми
  записями.
- TBD — теста нет на уровне репозитория для
  `MovementReportRepository._rollbackAnimalPlaceFromMovement`,
  вызванного именно через этот путь (`MovementReportCubit.deleteEvent` →
  `MovementReportRepository.delete`): ни один найденный тестовый файл не
  использует `MovementReportRepository` не замоканной ради проверки
  реального отката `Animal.placeId` для этого сценария. `grep -rn
  "_rollbackAnimalPlaceFromMovement" test/` не находит ни одного файла.
- TBD — теста нет на уровне, связывающем UI-диалог подтверждения
  (`MovementReportView._confirmAndDelete`) с реальным
  `MovementReportCubit.deleteEvent` в одном widget/e2e-потоке — существующий
  тест проверяет только сам кубит напрямую, без прохождения через
  `AlertDialog`/`MoreMenuWidget`.
- Для push/pull sync-сценариев тестов на уровне репозитория/`data_update_bloc.dart`
  нет вообще — не применимо к этому сценарию напрямую (удаление локальное,
  без последующей отправки удалённых записей на сервер), но упоминается по
  общему правилу отсутствия такого покрытия в модуле MOVE.

## Открытые вопросы и ограничения

- **Молчаливое глотание всех исключений (`try`/`catch (_) {}`).** Ни
  успешный, ни ошибочный исход не меняют состояние `MovementReportCubit` —
  пользователь не получает обратной связи об ошибке ни на уровне кубита, ни
  через какой-либо лог (`Talker` здесь не используется, в отличие от
  `UnsentMovementsCubit.deleteGroup`, которая логирует ошибку через
  `getIt<Talker>().error`). UI закрывает экран (`context.pop()`)
  независимо от того, было ли реально что-то удалено или метод упал с
  исключением на первой же строке.
- **Фильтр без учёта времени суток — единственная разница по сравнению с
  ключом группировки карточек хаба.** Карточка в хабе группирует записи по
  `fromId_placeId_HHmm` (с точностью до минуты), а `deleteEvent` при
  открытии из этой карточки удаляет по дню целиком — то есть может задеть
  записи, которые визуально относились к другой карточке того же дня между
  теми же местами. Явно зафиксировано как находка в комментарии
  теста-эталона.
- **Частичный эффект при исключении в середине цикла.** Если
  `_movementRepo.delete` бросает исключение не на первой итерации, записи,
  удалённые до этого момента, остаются удалёнными — отката уже
  выполненных удалений нет; внешний `try`/`catch (_) {}` останавливает
  только продолжение цикла, не откатывает уже случившееся. Не покрыто
  отдельным тестом (частично смежно с `RESULT = DELETE_ERROR`, не описанным
  этим файлом).
- **Нет прямого теста отката `Animal.placeId` для этого конкретного пути.**
  Единственный существующий тест (`UC-141`) мокает
  `MovementReportRepository.delete` целиком, поэтому логика
  `_rollbackAnimalPlaceFromMovement` (общая с
  [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)) в
  контексте вызова именно из `MovementReportCubit.deleteEvent` не
  верифицирована ни одним найденным тестом.
- Дальнейшая судьба уже физически удалённых записей в последующем sync-проходе
  (они просто отсутствуют — синхронизировать нечего) не описана отдельным
  событием/сценарием — вне периметра этого файла.
