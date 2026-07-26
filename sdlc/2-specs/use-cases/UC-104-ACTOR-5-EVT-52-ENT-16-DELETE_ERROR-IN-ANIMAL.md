# UC-104 — Удаление выбытия с экрана дневного отчёта отказывает технически: исключение перехватывается полностью пустым `catch (_) {}`, состояние кубита не меняется, экран всё равно закрывается как при успехе (ERROR)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md)
(`disposal.deleted_via_report`) так, как он реализован в
`DisposalReportCubit.deleteEvent`: попытка удалить ещё не отправленные записи
[ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) с экрана дневного отчёта о
выбытии технически отказывает — либо повторное чтение записей для удаления
(`DisposalRepository.getDisposalsWithDetailsByFilters`), либо сам вызов
удаления (`DisposalRepository.delete`) бросает исключение.

Этот дефект — точная копия того же паттерна, уже задокументированного для
MOVE-под-области в [UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)
(`MovementReportCubit.deleteEvent`, событие
[EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md)): `catch`
полностью пуст (`catch (_) {}`), без логирования, без `emit`, экран всё равно
закрывается безусловно. У соседнего события того же DISP-под-области —
[EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)
(`disposal.deleted_unsent`, `UnsentDisposalsCubit.deleteGroup`) — исключение
хотя бы логируется через `getIt<Talker>().error('deleteGroup: error: $e')`.
Здесь, в `DisposalReportCubit.deleteEvent`, нет ни `Talker`, ни `log`, ни
какого-либо иного побочного эффекта внутри `catch`-блока — символ исключения
даже не связан с именем (`catch (_)`), использовать его для логирования
синтаксически невозможно без переписывания сигнатуры catch. Метод, вызвавший
`deleteEvent`, безусловно закрывает экран сразу после `await` — независимо от
того, было ли реально что-то удалено — поэтому пользователь видит один и тот
же визуальный результат («экран закрылся») и при настоящем успехе, и при
полностью проглоченной технической ошибке; никакого способа отличить один
исход от другого нет.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково), удаляющий ещё не отправленную
запись выбытия с экрана дневного отчёта, открытого именно из хаба «В работе»
(см. «Основной поток», шаг 1 — иначе пункт меню удаления вообще не
отображается).

## CURRENT

### Основной поток

1. **Точка входа.** Пользователь открывает экран дневного отчёта о выбытии
   (`DisposalReportPage`, `lib/pages/disposal_report/presentation/disposal_report_page.dart`)
   с `args.isUnsent == true` (переход из хаба «В работе»/хаба неотправленных
   выбытий). Только в этом случае `EventReportScaffold.actions`
   (`lib/widgets/event_report/event_report_template.dart`) получает
   `MoreMenuWidget` с одним действием `l10n.delete`, `onTap: () =>
   _confirmAndDelete(context, args)` (`actions: args.isUnsent ? [...] :
   null`).
2. Пользователь нажимает это действие. `_confirmAndDelete` показывает
   `AlertDialog` (`showDialog`) с кнопками «Отмена»/«Удалить». Нажатие
   «Отмена» просто закрывает диалог (`Navigator.of(dialogContext).pop()`) —
   сценарий этого use-case не начинается.
3. Пользователь нажимает «Удалить» в диалоге. Обработчик кнопки: закрывает
   диалог (`Navigator.of(dialogContext).pop()`), затем **безусловно**
   `await context.read<DisposalReportCubit>().deleteEvent(args)`, затем — вне
   зависимости от результата этого `await` — `if (context.mounted)
   context.pop()`, закрывая сам экран отчёта.
4. Внутри `DisposalReportCubit.deleteEvent` (`lib/pages/disposal_report/cubit/disposal_report_cubit.dart`)
   весь код обёрнут в один `try`: вычисляются `day =
   DateUtils.dateOnly(args.date)` и `timeKey =
   DateFormat('HHmm').format(args.date)`, затем `await
   _disposalRepo.getDisposalsWithDetailsByFilters(sync: false, causeId:
   args.causeId)` — читает **все** ещё не отправленные записи выбытия по
   заданной причине (без фильтра по месту и без фильтра по дате/времени на
   уровне запроса к репозиторию — в отличие от `load()`, который передаёт
   `placeId` в тот же метод репозитория).
5. Результат фильтруется в памяти: `all.where((d) { final date =
   d.disposal.date ?? d.disposal.createdAt; ... return
   DateUtils.dateOnly(date).isAtSameMomentAs(day) &&
   DateFormat('HHmm').format(date) == timeKey && d.disposal.placeId ==
   args.placeId; })` — совпадение по дню, времени с точностью до минуты и
   месту.
6. **Технический отказ, вариант А.** `getDisposalsWithDetailsByFilters`
   сам бросает исключение (например, ошибка Drift/SQLite при чтении) —
   управление немедленно уходит в `catch (_) {}`, `toDelete` не вычисляется,
   ни один `delete` не вызывается: в БД ничего не меняется вообще.
7. Если чтение прошло успешно: для каждой записи из `toDelete` вызывается
   `await _disposalRepo.delete(d.disposal)` строго последовательно —
   `for (final d in toDelete) { await _disposalRepo.delete(d.disposal); }`, не
   `Future.wait`, не единый батч, не транзакция.
8. **Технический отказ, вариант Б.** Один из вызовов `delete(d.disposal)`
   внутри цикла бросает исключение (`DisposalRepository` не переопределяет
   `delete` — вызывается унаследованный
   `BaseRepository<DisposalsDao, Disposal, $DisposalsTable>.delete` →
   `dao.del(item)` → реальный Drift `DELETE`-запрос). Цикл прерывается на
   первом отказе: записи, обработанные до этой точки, уже физически удалены;
   оставшиеся в `toDelete` — нет.
9. **В обоих вариантах (А и Б)** брошенное исключение перехватывается
   единственным блоком `catch (_) {}`, охватывающим всё тело метода. Тело
   catch-блока полностью пусто: не вызывается ни `getIt<Talker>().error(...)`,
   ни `print`/`debugPrint`, ни любой другой side effect.
10. `deleteEvent` возвращает управление нормально (`Future<void>`,
    разрешённая успешно — `completes`) независимо от того, что произошло
    внутри (полный успех, частичное удаление до отказа на шаге 8, либо отказ
    ещё на шаге 6 до единого удаления).
11. Метод не содержит ни одного `emit(...)` ни на одном из путей — состояние
    `DisposalReportCubit` (в этот момент — `DisposalReportLoaded`, оставшееся
    с последнего `load()`) не меняется вообще. `BlocBuilder` на экране (уже
    закрываемом на шаге 3) не перерисовывается по причине этого вызова.
12. Так как `await deleteEvent(args)` в `_confirmAndDelete` не обёрнут в
    `try/catch` на стороне UI, а сам `deleteEvent` никогда не пробрасывает
    исключение наружу (перехвачено внутри), `if (context.mounted)
    context.pop()` выполняется безусловно и одинаково — что при полном успехе
    удаления, что при частичном, что при полном отказе ещё на шаге 6 (ни одна
    запись не удалена). Пользователь не получает никакого сигнала различить
    эти исходы — ни снэкбара, ни диалога, ни другого визуального поведения
    экрана.

### Альтернативные потоки

- **OK-исход того же обработчика — не входит в этот сценарий.** Если
  `getDisposalsWithDetailsByFilters` и все вызовы `delete` в цикле проходят
  без исключения, поведение UI (шаг 12) неотличимо от описанного здесь —
  экран точно так же безусловно закрывается. Это соседний, не документируемый
  здесь исход того же [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md);
  на момент написания этого файла отдельный use-case-документ для него в
  дереве `sdlc/2-specs/` не найден, поэтому не цитируется markdown-ссылкой
  (см. «Открытые вопросы»).
- **Вход из общего дневного отчёта (не из хаба неотправленных).** Если
  `DisposalReportPage` открыт с `args.isUnsent == false` (по умолчанию), то
  `EventReportScaffold.actions == null` — пункт меню «Удалить» не отображается
  вовсе, и весь сценарий этого use-case недостижим с этого пути входа.
- **Тот же локальный эффект удаления через другой код —
  `UnsentDisposalsCubit.deleteGroup`.** Хаб «В работе» также позволяет удалить
  ту же группу выбытий прямо со своего экрана, минуя
  `DisposalReportCubit.deleteEvent` — отдельный, независимо написанный путь к
  тому же эффекту (`lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart`,
  событие [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)).
  Там `catch (e)` хотя бы логирует через `Talker`
  (`getIt<Talker>().error('deleteGroup: error: $e')`), и список хаба
  реактивно перечитывается из БД через `watchNotSyncDisposals()` — если
  удаление реально не прошло, запись просто останется видна в списке. Экран
  отчёта, описываемый здесь, такой реактивной проверки не имеет: он не
  перечитывает состояние после удаления, а закрывается сразу.
- **Точная параллель в MOVE-под-области — `MovementReportCubit.deleteEvent`**
  ([UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)). Тот же
  `try { ... } catch (_) {}` вокруг чтения + последовательного цикла
  `delete`, тот же безусловный `context.pop()` в вызывающем виджете. Отличие
  по сущностям: `MovementReportRepository.delete` перед удалением строки
  откатывает `Animal.placeId` (`_rollbackAnimalPlaceFromMovement`) — здесь,
  для Disposal, такого отката нет вовсе: `DisposalRepository.delete` не
  переопределён и не трогает `Animal` ни в каком виде (см. «Связанные
  сущности»).

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сущность,
  которую сценарий пытается удалить; это же `ENT`-сегмент имени файла. При
  отказе варианта А ни одна запись не удаляется; при отказе варианта Б
  удаляется неопределённое префиксное подмножество отобранных записей
  (порядок определяется порядком элементов `toDelete`, то есть порядком,
  возвращённым `getDisposalsWithDetailsByFilters`).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — **не
  затрагивается этим сценарием вообще**, ни при успехе, ни при отказе.
  `DisposalWithDetails.animal` используется в `load()` для группировки по
  виду/статусу, но `deleteEvent` не читает и не изменяет поля `Animal` —
  в отличие от Movement (см. «Альтернативные потоки»), удаление Disposal не
  откатывает никакое поле животного, что согласуется с инвариантом
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md): создание/удаление
  Disposal не помечает и не размечает `Animal` локально.

### Бизнес-правила

- `catch (_) {}` — синтаксически перехватывает и молча отбрасывает любое
  исключение любого типа на любом из двух вызовов внутри `try`; код не
  различает причину отказа и не может её различить постфактум — исключение
  нигде не сохраняется, даже во временную переменную.
- `deleteEvent` не эмитит ни одного состояния `DisposalReportCubit` — ни в
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
- Фильтрация внутри `deleteEvent` частично дублирует, но не полностью
  повторяет фильтрацию внутри `load()`: `causeId` применяется на уровне
  запроса к репозиторию в обоих методах, а `placeId` — только в `load()`
  (передан аргументом в `getDisposalsWithDetailsByFilters`); в `deleteEvent`
  `placeId` проверяется только в фильтре `where` в памяти, после того как
  чтение уже прошло без него.
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
существующем коде. Единственный практический разрыв — тест на вариант Б
(частичный отказ середины цикла `delete`), которого нет; см. «Связанные
тесты» и «Открытые вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage.build` (`actions: args.isUnsent ? [MoreMenuWidget(...)] : null`) | CURRENT | показывает пункт меню «Удалить» только при `args.isUnsent` |
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage._confirmAndDelete` | CURRENT | `AlertDialog` подтверждения; после `await deleteEvent(args)` безусловно вызывает `context.pop()` без проверки результата |
| `lib/pages/disposal_report/data/disposal_report_data.dart` | `DisposalReportPageArgs` | CURRENT | `date`/`causeId`/`placeId`/`isUnsent`, используемые для повторной фильтрации внутри `deleteEvent` |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.deleteEvent` | CURRENT | `try { ... } catch (_) {}` — полностью пустой обработчик ошибки, без `emit`, без логирования |
| `lib/pages/disposal_report/cubit/disposal_report_state.dart` | `DisposalReportState` (вариант `error`) | CURRENT | вариант `error` существует в freezed-union, но `deleteEvent` никогда его не эмитит |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getDisposalsWithDetailsByFilters` | CURRENT | источник отказа варианта А — повторное чтение неотправленных записей по причине выбытия |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository` (`delete` не переопределён) | CURRENT | `delete` — унаследованная реализация `BaseRepository`, источник отказа варианта Б |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | `dao.del(item)`, вызывается для каждой записи `toDelete` последовательно |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — реальный Drift `DELETE`-запрос, источник отказа |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllDisposalsWithDetailsByFilters` | CURRENT | реальный Drift-запрос, лежащий в основе шага чтения |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.deleteGroup` | CURRENT | соседний путь к тому же эффекту ([EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)) — для сравнения: хотя бы логирует через `Talker`, здесь такого логирования нет |
| `lib/widgets/more_menu/more_menu_widget.dart` | `MoreMenuWidget`, `MoreMenuAction` | CURRENT | UI-компонент пункта меню «Удалить», видимого только при `args.isUnsent` |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportScaffold.actions` | CURRENT | место, где `MoreMenuWidget` подключается к `AppBar` экрана отчёта |

## Критерии приёмки

- Если `DisposalRepository.getDisposalsWithDetailsByFilters` бросает
  исключение внутри `DisposalReportCubit.deleteEvent`, вызов `deleteEvent(args)`
  завершается нормально (`completes`, а не `throwsA(...)`), состояние
  `DisposalReportCubit` (`cubit.state`) после вызова идентично состоянию до
  вызова — ни `emit`, ни изменение видимого состояния не происходит.
- Ни один вызов `Talker`/`log`/иного логирования не происходит внутри
  `catch`-блока `deleteEvent` — блок пуст (`catch (_) {}`).
- В вызывающем UI-коде (`_confirmAndDelete`) `context.pop()` выполняется после
  `await deleteEvent(args)` независимо от того, было ли реально удалено
  что-либо — экран отчёта закрывается и при полном отказе (вариант А), и при
  частичном (вариант Б), и при полном успехе, без какого-либо различающего
  признака, видимого пользователю.
- Если `getDisposalsWithDetailsByFilters` завершается успешно, но
  `DisposalRepository.delete` бросает исключение на одной из записей цикла,
  все записи, обработанные до точки отказа, уже физически удалены, а
  необработанные — нет; `deleteEvent` всё равно завершается нормально.
- `Animal` не читается и не изменяется этим методом ни на одном из путей —
  ни при успехе, ни при любом из двух вариантов отказа.

## Связанные тесты

`test/pages/disposal_report_cubit_test.dart`, group `'UC-104 —
DisposalReportCubit.deleteEvent'` (переименуется отдельным контролируемым
проходом позже, не трогать сейчас):

- test `'БАГ: catch (_) {} — исключение при чтении/удалении молча
  проглатывается, состояние кубита не меняется (deleteEvent нигде не
  emit-ит, ни на успехе, ни на ошибке — идентичный вызывающий код закрывает
  экран как при успехе в обоих случаях)'` — прямое покрытие варианта А
  («Основной поток», шаг 6): мок
  `disposalRepository.getDisposalsWithDetailsByFilters(sync: false, causeId:
  2)` настроен `thenThrow(Exception('db error'))`; тест проверяет `await
  expectLater(cubit.deleteEvent(args), completes)` и `expect(cubit.state,
  stateBefore)` — что состояние кубита не изменилось.
- Смежный, успешный тест в том же файле — group `'UC-103 —
  DisposalReportCubit.deleteEvent'` — покрывает основной путь фильтрации
  (день + время с точностью до минуты + место), не входит в этот
  ERROR-документ.
- **TBD — теста нет** на вариант Б («Основной поток», шаг 8): ни один
  существующий тест не настраивает `disposalRepository.delete(any())` на
  `thenThrow(...)` при успешном `getDisposalsWithDetailsByFilters` —
  частичный отказ середины цикла удаления не воспроизведён.
- **TBD — теста нет** на реальный UI-эффект (`_confirmAndDelete` в
  `disposal_report_page.dart`, безусловный `context.pop()` после `await
  deleteEvent`) — покрытие есть только на уровне кубита, не на уровне
  виджета/страницы.

## Открытые вопросы и ограничения

- **Худший обработчик ошибок среди специфицированных ERROR-исходов DISP.** В
  отличие от `UnsentDisposalsCubit.deleteGroup`
  (`getIt<Talker>().error('deleteGroup: error: $e')` хотя бы вызывается) —
  здесь нет ни логирования, ни пользовательского сообщения, ни отличимого
  состояния кубита. Диагностировать реальный сбой в проде по этому пути
  невозможно вообще — ни по логам, ни по поведению приложения. Зафиксировано
  как факт CURRENT, не исправляется в рамках этого документирующего прохода
  (TARGET == CURRENT).
- **Безусловный `context.pop()` маскирует отказ как успех.** Поскольку
  `_confirmAndDelete` закрывает экран после `await deleteEvent(args)`
  независимо от исхода, а сам `deleteEvent` никогда не пробрасывает
  исключение наружу, у пользователя нет никакого способа узнать, что
  удаление не произошло (вариант А) или произошло только частично (вариант
  Б) — с точки зрения UI все три исхода (полный успех, полный отказ,
  частичный отказ) визуально идентичны.
- **Частичный отказ цикла удаления (вариант Б) не покрыт тестом и не
  сигнализируется нигде.** Записи `toDelete` удаляются последовательно, без
  транзакции и без сбора результатов по каждому вызову — если один из
  вызовов `delete` посередине списка бросает исключение, уже обработанный
  префикс списка остаётся удалённым, а остаток — нет; итоговое состояние
  группы выбытий оказывается рассогласованным, и ни код, ни пользователь об
  этом не узнают.
- **Тот же дефект воспроизведён и в MOVE-под-области** —
  [UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)
  (`MovementReportCubit.deleteEvent`) — это не единичная опечатка в одном
  обработчике, а повторяющийся паттерн копипаста между отчётными cubit'ами
  разных под-областей модуля ANIMAL.
- **OK-исход того же метода (`disposal.deleted_via_report` / `DELETE_OK`) на
  момент написания этого файла ещё не задокументирован отдельным use-case**
  (`UC-*-ACTOR-5-EVT-52-ENT-16-DELETE_OK-IN-ANIMAL.md` в дереве
  `sdlc/2-specs/use-cases/` не найден). Как только этот файл появится, стоит
  добавить на него ссылку из «Назначения» и из «Альтернативных потоков» этого
  документа отдельной, контролируемой правкой.
- Нужно ли вообще чинить это (`await`/явный `try-catch` с логированием и
  пользовательским сообщением об ошибке, различающееся поведение
  `context.pop()`) — вопрос будущего TARGET-прохода, не разрешается здесь:
  этот документ фиксирует только то, что есть в коде сегодня.
