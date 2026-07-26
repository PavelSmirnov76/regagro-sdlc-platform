# UC-59 — Удаление перемещения с экрана дневного отчёта отказывает технически: исключение перехватывается полностью пустым `catch`, ни логирования, ни сообщения пользователю — экран всё равно закрывается как при успехе (ERROR)

## Назначение

Документирует ERROR-исход события [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md)
(`movement.deleted_via_report`) так, как он реализован в
`MovementReportCubit.deleteEvent`: попытка удалить ещё не отправленные записи
[ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) с экрана дневного отчёта о
перемещении технически отказывает — чтение записей для удаления
(`MovementReportRepository.getMovementsWithDetailsByFilters`) или сам вызов
удаления (`MovementReportRepository.delete`) бросает исключение.

Это худший по качеству обработки ошибок сценарий среди уже
специфицированных ERROR-исходов MOVE-под-области. У соседнего события
[EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)
(`movement.deleted_unsent`, `UnsentMovementsCubit.deleteGroup`, см.
[UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md)) исключение тоже
не приводит ни к какому пользовательскому сообщению, но хотя бы логируется
через `getIt<Talker>().error('deleteGroup: error: $e')`. Здесь, в
`MovementReportCubit.deleteEvent`, `catch`-блок полностью пуст (`catch (_)
{}`) — нет ни `Talker`, ни `log`, ни какого-либо иного побочного эффекта.
Хуже того: экран, вызвавший `deleteEvent`, безусловно закрывается сразу после
`await` этого метода — независимо от того, было ли реально что-то удалено —
поэтому пользователь видит тот же самый визуальный результат («экран закрылся»)
и при настоящем успехе, и при полностью проглоченной технической ошибке;
никакого способа отличить один исход от другого на экране нет.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково), удаляющий ещё не отправленное
перемещение с экрана дневного отчёта, открытого именно из хаба неотправленных
(см. «Основной поток», шаг 1 — иначе пункт меню удаления вообще не
отображается).

## CURRENT

### Основной поток

1. **Точка входа.** Пользователь открывает хаб неотправленных перемещений
   (`UnsentMovementsView` → `UnsentMovementsPopulated`,
   `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart`)
   и тапает по карточке одной группы событий (`_MovementEventCard.onTap`).
   Переход идёт как `context.pushNamed2(Routes.movementReport, extra:
   MovementReportPageArgs(..., isUnsent: true))` — именно флаг `isUnsent: true`
   в этом вызове делает возможным дальнейшее удаление (см. «Альтернативные
   потоки» — вход из общего календаря того же экрана этот флаг не выставляет).
2. `MovementReportPage` (`lib/pages/movement_report/presentation/movement_report_page.dart`)
   рендерит `MovementReportView`
   (`lib/pages/movement_report/presentation/widgets/movement_report_view.dart`),
   которая создаёт `MovementReportCubit()..load(args)` через `BlocProvider` и
   считывает `args` через `GoRouterState.of(context).getExtraByName<
   MovementReportPageArgs>(Routes.movementReport)`.
3. Поскольку `args.isUnsent == true`, `EventReportScaffold.actions`
   (`lib/widgets/event_report/event_report_template.dart`) получает
   `MoreMenuWidget` с одним действием `l10n.delete`, `onTap:
   () => _confirmAndDelete(context, args)`.
4. Пользователь нажимает это действие. `_confirmAndDelete` показывает
   `AlertDialog` (`showDialog`) с кнопками «Отмена»/«Удалить». Нажатие «Отмена»
   просто закрывает диалог — сценарий этого use-case не начинается.
5. Пользователь нажимает «Удалить» в диалоге. Обработчик кнопки: закрывает
   диалог (`Navigator.of(dialogContext).pop()`), затем **безусловно**
   `await context.read<MovementReportCubit>().deleteEvent(args)`, затем — вне
   зависимости от результата этого `await` — `if (context.mounted)
   context.pop()`, закрывая сам экран отчёта и возвращая пользователя на хаб
   неотправленных.
6. Внутри `MovementReportCubit.deleteEvent` (`lib/pages/movement_report/cubit/movement_report_cubit.dart`)
   весь код обёрнут в один `try`: вычисляется `day =
   DateUtils.dateOnly(args.date)`, затем `await
   _movementRepo.getMovementsWithDetailsByFilters(sync: false)` — читает **все**
   ещё не отправленные перемещения (не отфильтрованные по месту/дате на уровне
   DAO), затем фильтрует их в памяти по `DateUtils.dateOnly(date)
   .isAtSameMomentAs(day) && fromId == args.fromPlaceId && placeId ==
   args.toPlaceId` (без сравнения времени с точностью до минуты — отдельная,
   уже описанная в тестах особенность фильтрации, не специфичная для
   ERROR-ветки).
7. **Технический отказ, вариант А.** `getMovementsWithDetailsByFilters` сам
   бросает исключение (например, ошибка Drift/SQLite при чтении) — управление
   немедленно уходит в `catch (_) {}`, `toDelete` не вычисляется, ни один
   `delete` не вызывается: в БД ничего не меняется вообще.
8. **Технический отказ, вариант Б.** Чтение проходит успешно, но один из
   вызовов `await _movementRepo.delete(m.movement)` внутри `for (final m in
   toDelete)` бросает исключение — цикл не обёрнут ни в транзакцию, ни в
   `Future.wait`, вызовы идут строго последовательно; если бросает,
   например, третья из пяти отобранных записей, записи 1 и 2 к этому моменту
   уже физически удалены (и `Animal.placeId` для них уже откачен на `fromId`,
   см. «Связанные сущности»), а записи 3–5 остаются как есть — частичный,
   рассогласованный результат, не отличимый снаружи от «ничего не удалилось»
   и от «удалилось всё».
9. В обоих вариантах (А и Б) `catch (_) {}` перехватывает исключение и не
   делает ровным счётом ничего: не логирует (ни `Talker`, ни `log`, ни
   `print`), не эмитит никакого состояния `MovementReportCubit` (сам метод
   `deleteEvent` вообще не вызывает `emit` ни на одном пути — ни в `try`, ни в
   `catch`), не пробрасывает исключение наружу. `deleteEvent` возвращает
   нормально завершённый `Future<void>`.
10. Управление возвращается в `_confirmAndDelete` (шаг 5): `await` на
    `deleteEvent` завершается без исключения независимо от того, что
    произошло внутри (варианты А/Б или настоящий успех) — и `context.pop()`
    исполняется безусловно. Пользователь видит ровно одну и ту же картину во
    всех трёх случаях: диалог закрылся, затем сам экран отчёта закрылся,
    никакого сообщения об ошибке нигде не появляется.

### Альтернативные потоки

- **OK-исход того же обработчика — не входит в этот сценарий.** Если
  `getMovementsWithDetailsByFilters` и все вызовы `delete` в цикле проходят
  без исключения, поведение UI (шаг 10) неотличимо от описанного здесь —
  экран точно так же безусловно закрывается. Это соседний, не документируемый
  здесь исход того же [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md).
- **Вход из общего календаря (не из хаба неотправленных).** Тот же экран
  (`Routes.movementReport`) открывается и из `ReportsDayListPopulated`
  (`lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`,
  `_navigateItem` → `MovementReportPageArgs(...)` без `isUnsent`, то есть с
  значением по умолчанию `false`). В этом случае `EventReportScaffold.actions`
  равен `null` — пункт меню «Удалить» не отображается вовсе, и весь сценарий
  этого use-case недостижим с этого пути входа.
- **Тот же локальный эффект удаления через другой код — `UnsentMovementsCubit.deleteGroup`.**
  Хаб неотправленных также позволяет удалить ту же группу перемещений прямо со
  своего экрана, минуя `MovementReportCubit.deleteEvent` — отдельный, независимо
  написанный путь к тому же эффекту (см. [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md),
  ERROR-исход — [UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md)).
  Там `catch (e)` хотя бы логирует через `Talker`, и список хаба реактивно
  перечитывается из БД через `watchNotSyncMovements()` — если удаление реально
  не прошло, запись просто останется видна в списке. Экран отчёта, описываемый
  здесь, такой реактивной проверки не имеет: он не перечитывает состояние после
  удаления, а закрывается сразу.

### Связанные сущности

- [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) — сущность,
  которую сценарий пытается удалить; это же `ENT`-сегмент имени файла. При
  отказе варианта А ни одна запись не удаляется; при отказе варианта Б
  удаляется неопределённое префиксное подмножество отобранных записей.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — каждый успешный
  вызов `MovementReportRepository.delete` внутри цикла (шаг 8) перед
  удалением строки перемещения откатывает `Animal.placeId` на `fromId` этой
  записи, но только если текущее место животного всё ещё равно `placeId`
  записи (`_rollbackAnimalPlaceFromMovement`,
  `lib/repositories/movement_report/movement_report_repository.dart`). При
  частичном отказе (вариант Б) это означает, что часть животных из группы уже
  получила откат места, а часть — нет, при том что с точки зрения
  пользователя (шаг 10) вся группа выглядит одинаково удалённой.

### Бизнес-правила

- `catch (_) {}` — синтаксически перехватывает и молча отбрасывает любое
  исключение любого типа на любом из двух вызовов внутри `try`; код не
  различает причину отказа и не может её различить постфактум — исключение
  нигде не сохраняется, даже во временную переменную.
- `deleteEvent` не эмитит ни одного состояния `MovementReportCubit` — ни в
  успешном пути, ни в `catch`; вызывающий код (`_confirmAndDelete`) не читает
  `cubit.state` после `await`, поэтому даже если бы состояние менялось, это
  никак не отражалось бы на решении вызвать `context.pop()`.
- `context.pop()` в `_confirmAndDelete` вызывается **безусловно** после
  `await deleteEvent(args)`, без проверки исключения (никакого `try/catch`
  вокруг самого `await` в UI-коде нет) и без проверки, действительно ли
  что-то было удалено — единственное условие перед `pop()` —
  `context.mounted`, не имеющее отношения к результату удаления.
- Удаление записей внутри `deleteEvent` — последовательный `for`-цикл с
  отдельным `await` на каждую запись, не единый батч-вызов и не транзакция;
  частичный успех цикла (часть записей удалена, часть — нет) технически
  возможен и ничем не сигнализируется.
- Правило проекта показывать пользователю ошибки через
  `lib/widgets/app_snackbar.dart` (`showAppSnackBarError` и т.д.,
  `.claude/rules/ui-architecture.md`) в этом обработчике не применяется вовсе
  — ни при технической ошибке (нет вызова `emit`/снэкбара в принципе), ни при
  успехе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обе технические ветки отказа (чтение и удаление) и
безусловный `context.pop()` в вызывающем UI-коде полностью прослеживаются в
существующем коде. Тест, впрямую подтверждающий отказ, покрывает только
ветку А (`getMovementsWithDetailsByFilters` бросает) — ветка Б (частичный
отказ середины цикла `delete`) существующим тестом не покрыта, см.
«Связанные тесты» и «Открытые вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_movement/presentation/unsent_movement/widgets/unsent_movements_populated.dart` | `_MovementEventCard.onTap` | CURRENT | реальная точка входа: `context.pushNamed2(Routes.movementReport, extra: MovementReportPageArgs(..., isUnsent: true))` |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `_navigateItem` (case `MovementDayItem`) | CURRENT | альтернативная точка входа на тот же экран, но без `isUnsent` (по умолчанию `false`) — делает удаление недостижимым с этого пути |
| `lib/pages/routes.dart` | `Routes.movementReport` | CURRENT | константа маршрута, регистрация `MovementReportPage` в `go_router` |
| `lib/pages/movement_report/presentation/movement_report_page.dart` | `MovementReportPage` | CURRENT | точка входа экрана, рендерит `MovementReportView` |
| `lib/pages/movement_report/presentation/widgets/movement_report_view.dart` | `MovementReportView.build`, `_confirmAndDelete` | CURRENT | показывает пункт меню «Удалить» только при `args.isUnsent`; после `await deleteEvent(args)` безусловно вызывает `context.pop()` без проверки результата |
| `lib/pages/movement_report/data/movement_report_data.dart` | `MovementReportPageArgs.isUnsent` | CURRENT | флаг, включающий/выключающий видимость действия удаления |
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.deleteEvent` | CURRENT | `try { ... } catch (_) {}` — полностью пустой обработчик ошибки, без `emit`, без логирования |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | источник отказа варианта А — чтение всех неотправленных записей перед фильтрацией в памяти |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.delete`, `_rollbackAnimalPlaceFromMovement` | CURRENT | источник отказа варианта Б; каждый вызов внутри цикла — отдельная точка отказа, откат `Animal.placeId` выполняется до удаления строки |
| `packages/sheep_farm_database/lib/entities/movement/movement_dao.dart` | `MovementsDao.getAllMovementsWithDetailsByFilters` | CURRENT | реальный Drift-запрос, лежащий в основе шага 6 |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getById`, `AnimalsRepository.updateAnimalPlaceId` | CURRENT | зависимости отката `Animal.placeId`, используемые `_rollbackAnimalPlaceFromMovement` |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.deleteGroup` | CURRENT | соседний путь к тому же эффекту (см. [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)) — для сравнения: логирует через `Talker`, здесь такого логирования нет |
| `lib/widgets/more_menu/more_menu_widget.dart` | `MoreMenuWidget`, `MoreMenuAction` | CURRENT | UI-компонент пункта меню «Удалить», видимого только при `args.isUnsent` |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportScaffold.actions` | CURRENT | место, где `MoreMenuWidget` подключается к `AppBar` экрана отчёта |

## Критерии приёмки

- Если `MovementReportRepository.getMovementsWithDetailsByFilters` бросает
  исключение внутри `MovementReportCubit.deleteEvent`, вызов `deleteEvent(args)`
  завершается нормально (`completes`, а не `throwsA(...)`), состояние
  `MovementReportCubit` (`cubit.state`) после вызова идентично состоянию до
  вызова — ни `emit`, ни изменение видимого состояния не происходит.
- Ни один вызов `Talker`/`log`/иного логирования не происходит внутри
  `catch`-блока `deleteEvent` — блок пуст (`catch (_) {}`).
- В вызывающем UI-коде (`_confirmAndDelete`) `context.pop()` выполняется после
  `await deleteEvent(args)` независимо от того, было ли реально удалено что-либо
  — экран отчёта закрывается и при полном отказе (вариант А), и при частичном
  (вариант Б), и при полном успехе, без какого-либо различающего признака,
  видимого пользователю.
- Если `getMovementsWithDetailsByFilters` завершается успешно, но
  `MovementReportRepository.delete` бросает исключение на одной из записей
  цикла, все записи, обработанные до точки отказа, уже физически удалены (с
  применённым откатом `Animal.placeId`, где применимо), а необработанные —
  нет; `deleteEvent` всё равно завершается нормально.

## Связанные тесты

`test/pages/movement_report_cubit_test.dart`, group `'UC-59 — MovementReportCubit.deleteEvent'` (переименуется отдельным контролируемым
проходом позже, не трогать сейчас):

- test `'БАГ: catch (_) {} — исключение при чтении/удалении молча
  проглатывается, состояние кубита не меняется (тот же паттерн, что
  DisposalReportCubit.deleteEvent, UC-RA-LS-118)'` — прямое покрытие варианта
  А («Основной поток», шаг 7): мок
  `movementReportRepository.getMovementsWithDetailsByFilters(sync: false)`
  настроен `thenThrow(Exception('db error'))`; тест проверяет `await
  expectLater(cubit.deleteEvent(args), completes)` и `expect(cubit.state,
  stateBefore)` — что состояние кубита не изменилось.
- Смежный, успешный тест в том же файле — group `'UC-58 — MovementReportCubit.deleteEvent'` — покрывает основной путь фильтрации
  (дата+`fromId`+`placeId` без сравнения времени), не входит в этот
  ERROR-документ.
- **TBD — теста нет** на вариант Б («Основной поток», шаг 8): ни один
  существующий тест не настраивает `movementReportRepository.delete(any())`
  на `thenThrow(...)` при успешном
  `getMovementsWithDetailsByFilters` — частичный отказ середины цикла удаления
  не воспроизведён.
- **TBD — теста нет** на реальный UI-эффект (`_confirmAndDelete` в
  `movement_report_view.dart`, безусловный `context.pop()` после `await
  deleteEvent`) — покрытие есть только на уровне кубита, не на уровне
  виджета/страницы.
- Соседний код с тем же дефектом (`catch (_) {}` без логирования) существует и
  в модуле DISP — `DisposalReportCubit.deleteEvent`
  (`lib/pages/disposal_report/cubit/disposal_report_cubit.dart`), на что прямо
  указывает текст самого теста (`UC-RA-LS-118` — идентификатор старой
  конвенции нумерации, не входит в текущую схему `sdlc/2-specs/`, приведён
  здесь как факт, не как ссылка на живой артефакт этого дерева).

## Открытые вопросы и ограничения

- **Худший обработчик ошибок среди специфицированных ERROR-исходов MOVE.**
  В отличие от [UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md)
  (`Talker.error` хотя бы вызывается) и от ERROR-исходов REG-под-области
  ([UC-47](UC-47-ACTOR-5-EVT-23-ENT-11-UPDATE_ERROR-IN-ANIMAL.md),
  [UC-49](UC-49-ACTOR-5-EVT-24-ENT-11-UPDATE_ERROR-IN-ANIMAL.md) — там хотя бы
  показывается снэкбар с `'an_error_data'`), здесь нет ни логирования, ни
  пользовательского сообщения, ни отличимого состояния кубита. Диагностировать
  реальный сбой в проде по этому пути невозможно вообще — ни по логам, ни по
  поведению приложения.
  Зафиксировано как факт CURRENT, не исправляется в рамках этого
  документирующего прохода (TARGET == CURRENT).
- **Безусловный `context.pop()` маскирует отказ как успех.** Поскольку
  `_confirmAndDelete` закрывает экран после `await deleteEvent(args)`
  независимо от исхода, а сам `deleteEvent` никогда не пробрасывает исключение
  наружу, у пользователя нет никакого способа узнать, что удаление не
  произошло (вариант А) или произошло только частично (вариант Б) — с точки
  зрения UI все три исхода (полный успех, полный отказ, частичный отказ)
  визуально идентичны.
- **Частичный отказ цикла удаления (вариант Б) не покрыт тестом и не
  сигнализируется нигде.** Записи `toDelete` удаляются последовательно, без
  транзакции и без сбора результатов по каждому вызову — если один из вызовов
  `delete` посередине списка бросает исключение, уже обработанный префикс
  списка (включая связанный откат `Animal.placeId`) остаётся применённым, а
  остаток — нет; итоговое состояние группы перемещений оказывается
  рассогласованным, и ни код, ни пользователь об этом не узнают.
- **Тот же дефект (`catch (_) {}` без логирования) воспроизведён и в модуле
  DISP** (`DisposalReportCubit.deleteEvent`) — это не единичная опечатка в
  одном обработчике, а повторяющийся паттерн копипаста между отчётными
  cubit'ами разных под-областей; вне области действия этого документа
  (ANIMAL/MOVE), приведено здесь только как контекст находки.
