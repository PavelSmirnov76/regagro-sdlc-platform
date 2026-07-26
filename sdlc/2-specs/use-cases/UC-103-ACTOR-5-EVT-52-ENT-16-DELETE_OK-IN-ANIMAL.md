# UC-103 — Пользователь удаляет выбытие с экрана дневного отчёта, открытого из хаба неотправленных, удаление успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Happy-path сценарий события
[EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md)
(`disposal.deleted_via_report`): пользователь удаляет ещё не отправленные
записи выбытия с экрана дневного отчёта о выбытии, открытого из хаба
«неотправленных» (`isUnsent: true`). Все ещё не отправленные записи,
подходящие под фильтр день + точное время (с точностью до минуты) + место +
причина выбытия, удаляются физически, без исключения. Тот же метод
репозитория (`DisposalRepository.delete`), что и у
[EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)
(`UnsentDisposalsCubit.deleteGroup`), но вызванный через отдельный,
независимо написанный путь (`DisposalReportCubit.deleteEvent`), не
переиспользующий `deleteGroup`. Тот же паттерн двух независимо написанных
путей к одному эффекту, что и у Movement
([EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md)/[EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md),
happy-path которого документирован в
[UC-58](UC-58-ACTOR-5-EVT-29-ENT-13-DELETE_OK-IN-ANIMAL.md)).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Проверено чтением
`lib/pages/disposal_report/cubit/disposal_report_cubit.dart` целиком:
`DisposalReportCubit` не объявляет и не использует `AuthRepository` ни в
одном методе, включая `deleteEvent`; `DisposalRepository` (репозиторий,
которым пользуется кубит) тоже не проверяет статус авторизации на этом пути.

## CURRENT

### Основной поток

1. Точка входа — тап по карточке события выбытия в хабе «неотправленных»
   (`_DisposalEventCard.onTap` внутри `UnsentDisposalsPopulated.build`,
   `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart`)
   → `context.pushNamed2(Routes.disposalReport, extra:
   DisposalReportPageArgs(date: event.date, causeId: event.causeId, placeId:
   event.placeId, reasonName: event.reasonName, placeName: event.placeName,
   isUnsent: true))`. Карточки в этом хабе сгруппированы ключом
   `'${causeId}_${placeId}_${DateFormat('HHmm').format(date)}'`
   (`UnsentDisposalsPopulated._groupByEvent`) — с точностью до минуты, тем же
   набором полей, что фильтр удаления на следующем экране (см. «Бизнес-правила»).
2. `DisposalReportPage.build`
   (`lib/pages/disposal_report/presentation/disposal_report_page.dart`)
   читает `DisposalReportPageArgs` через
   `GoRouterState.of(context).getExtraByName<DisposalReportPageArgs>(Routes.disposalReport)`,
   создаёт `BlocProvider(create: (context) => DisposalReportCubit()..load(args))`.
3. Поскольку `args.isUnsent == true`, `EventReportScaffold.actions` содержит
   `MoreMenuWidget` с единственным действием `MoreMenuAction(title:
   l10n.delete, onTap: () => _confirmAndDelete(context, args))`. Если бы
   экран был открыт из общего календаря отчётов (`isUnsent` по умолчанию
   `false`) — `actions: null`, пункт меню отсутствовал бы вовсе (см.
   «Альтернативные потоки»).
4. Пользователь открывает меню, нажимает «Удалить» → `_confirmAndDelete`
   показывает `AlertDialog` (`showDialog`) с заголовком `l10n.delete`,
   текстом `l10n.disposal`, кнопками «Отмена» (`l10n.cancel`,
   `Navigator.of(dialogContext).pop()`) и «Удалить» (текст красным).
5. Пользователь подтверждает — обработчик кнопки «Удалить»: сначала
   `Navigator.of(dialogContext).pop()` (закрывает диалог), затем `await
   context.read<DisposalReportCubit>().deleteEvent(args)`, затем, если
   `context.mounted` — `context.pop()` (закрывает сам экран отчёта,
   безусловно, независимо от того, было ли реально что удалено).
6. `DisposalReportCubit.deleteEvent(args)` — всё тело обёрнуто в
   `try {...} catch (_) {}`, без rethrow и без изменения состояния кубита ни
   при успехе, ни при ошибке (см. «Открытые вопросы»).
7. `day = DateUtils.dateOnly(args.date)`; `timeKey =
   DateFormat('HHmm').format(args.date)`.
8. `all = await _disposalRepo.getDisposalsWithDetailsByFilters(sync: false,
   causeId: args.causeId)` — заново, независимо от того, что было загружено
   на шаге `load()` (тот вызывал тот же метод с `sync: args.isUnsent ? false
   : null` **и** `placeId: args.placeId`, переданным прямо в запрос).
   `deleteEvent` передаёт в запрос только `sync`/`causeId` — фильтр по месту
   применяется позже, в памяти (шаг 9), не на уровне SQL-запроса.
   `DisposalsDao.getAllDisposalsWithDetailsByFilters`
   (`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart`)
   выполняет join на `Place`/`DisposalReason`/`Animal`.
9. Фильтр `toDelete`: для каждой записи `date = d.disposal.date ??
   d.disposal.createdAt`; если `date == null` — запись исключается; иначе
   запись входит в `toDelete`, если одновременно: `DateUtils.dateOnly(date)`
   совпадает с `day`, **и** `DateFormat('HHmm').format(date) == timeKey`
   (точность до минуты), **и** `d.disposal.placeId == args.placeId`. В
   отличие от Movement ([UC-58](UC-58-ACTOR-5-EVT-29-ENT-13-DELETE_OK-IN-ANIMAL.md)),
   здесь время суток **сравнивается** (см. «Бизнес-правила»); причина
   (`causeId`) уже отфильтрована на уровне SQL-запроса шага 8, а не в
   памяти.
10. Для каждой записи `d` из `toDelete`, последовательно, в цикле `for`:
    `await _disposalRepo.delete(d.disposal)` → `DisposalRepository` не
    переопределяет `delete` (проверено чтением `lib/repositories/disposal/disposal_repository.dart`
    целиком — метод отсутствует в файле) → используется унаследованный
    `BaseRepository.delete` (`lib/repositories/base_repository.dart`) →
    `dao.del(item)` → `BaseDao.del`
    (`packages/sheep_farm_database/lib/entities/base_dao.dart`) →
    `deleteCurrent().delete(item)` — физическое удаление строки по
    первичному ключу. Никакого отката полей `Animal` здесь не происходит
    (в отличие от Movement) — создание/удаление `Disposal` не меняет
    `Animal.placeId` ни в одну, ни в другую сторону (см. «Связанные
    сущности», инвариант 6 доменной модели).
11. Цикл проходит по всем записям `toDelete` без исключения (happy path
    этого сценария) → `deleteEvent` завершается без выброса ошибки во
    внешний `try`/`catch`.
12. Обратно на UI: `await` в шаге 5 разрешается, `context.mounted` истинно →
    `context.pop()` закрывает экран отчёта целиком. Сам `DisposalReportCubit`
    не перечитывает и не переэмитит своё состояние после удаления — экран
    закрывается сразу, не показывая обновлённый (пустой) список.
13. Экран-источник — хаб «неотправленных» (`UnsentDisposalsCubit`,
    `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart`)
    — узнаёт об удалении не через прямой вызов от `DisposalReportCubit`, а
    реактивно: конструктор `UnsentDisposalsCubit` подписан на
    `_disposalRepository.watchNotSyncDisposals()`, и физическое удаление
    строк на шаге 10 эмитит новое значение потока drift по таблице
    `Disposals`, что триггерит `_reload()` хаба независимо от того, что
    произошло на экране отчёта.

### Альтернативные потоки

- **Тот же день открыт из общего календаря отчётов**
  (`ReportsDayListPopulated._navigateItem`, кейс `DisposalDayItem`,
  `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart`)
  — `DisposalReportPageArgs` создаётся без `isUnsent` (значение по умолчанию
  `false`), поэтому на шаге 3 `actions: null` — пункт меню «Удалить» не
  показывается вовсе, весь экран read-only для этого пути. Не сценарий
  этого файла — не `EVT-52` совсем (тут `deleteEvent` не может быть вызван
  из UI).
- **У записи нет `date` и нет `createdAt`** — исключается из `toDelete`
  фильтром на шаге 9 (`if (date == null) return false`), запись не
  удаляется этим вызовом вовсе (не то же поведение, что у Movement, где
  отсутствие `animalId`/`fromId`/`placeId` не исключает запись из удаления —
  здесь отсутствие даты исключает саму возможность попасть в `toDelete`).
- **`toDelete` — пустой список** (ни одна ещё не отправленная запись не
  подошла под фильтр день+время+место) — цикл на шаге 10 не выполняется ни
  разу, `deleteEvent` завершается без единого вызова `delete`; тот же
  успешный (без исключения) выход, что и happy path, просто без побочного
  эффекта.
- **Исключение при чтении (`getDisposalsWithDetailsByFilters`) или при
  каком-то из вызовов `delete` в середине цикла** — ловится внешним
  `catch (_) {}`, ошибка нигде не логируется и не отражается в состоянии
  кубита; если исключение произошло не на первой итерации, записи,
  удалённые до него, остаются удалёнными (частичный эффект без отката уже
  случившихся удалений) — отдельный сценарий (`RESULT = DELETE_ERROR`), не
  описанный этим файлом, покрытый тестом `'UC-104 — DisposalReportCubit.deleteEvent'`
  (старая нумерация, см. «Связанные тесты»).

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сущность
  сегмента `ENT` в id: удаляемые записи, переход «существует (ещё не
  отправлено, `sync == false`)» → физически удалена (нет промежуточного
  мягкого состояния — `deletedAt` заполняется только сервером и этой
  под-областью не используется, см. `ENT-16`).
- `Animal` (модуль ANIMAL, [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md))
  — только косвенно, через join в `DisposalWithDetails` (для группировки по
  `ageGroup`/`kind`/`firstMainNumber` в `load()`, не в `deleteEvent`);
  `deleteEvent` не читает и не изменяет ни одно поле `Animal` — в отличие от
  Movement, здесь нет отката `placeId` или иного поля, потому что создание
  `Disposal` само по себе не меняет `Animal` локально.
- `DisposalReason` (модуль HANDBOOKS, [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md))
  — `causeId` уже отфильтрован на уровне SQL-запроса (шаг 8); сущность
  только на чтение через join, этим сценарием не изменяется.
- `Place` (модуль FARM, [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)) —
  только на чтение, через join (`place` в `DisposalWithDetails`) для
  отображения названия места в карточке хаба и в отчёте; этим сценарием не
  изменяется.

### Бизнес-правила

- Кнопка удаления гейтится исключительно флагом `args.isUnsent`, переданным
  вызывающим экраном, а не каким-либо запросом к репозиторию — один и тот
  же виджет `DisposalReportPage` обслуживает и read-only путь из общего
  календаря, и путь с удалением из хаба неотправленных.
- Фильтр удаления — день + точное время (с точностью до минуты) + место +
  причина выбытия (причина — на уровне SQL-запроса, остальное — в памяти).
  Это **точнее**, чем у Movement
  ([UC-58](UC-58-ACTOR-5-EVT-29-ENT-13-DELETE_OK-IN-ANIMAL.md)), где время
  суток не сравнивается вовсе, и совпадает с ключом группировки карточек
  самого хаба (`causeId_placeId_HHmm`) — следствие: удаление, вызванное с
  одной конкретной карточки хаба, задевает только записи этой же карточки,
  без риска захватить записи, отображавшиеся в хабе отдельной карточкой
  того же дня/места/причины, но в другое время (в отличие от Movement, где
  такой риск есть).
- Удаление — всегда физическое (`deleteCurrent().delete`), не мягкое;
  `DisposalRepository` не переопределяет `delete` — используется
  унаследованный `BaseRepository.delete` без какой-либо сопутствующей
  логики отката (в отличие от `MovementReportRepository.delete`, которая
  переопределяет `delete` ради отката `Animal.placeId`).
- После успешного завершения `deleteEvent` сам экран отчёта не перечитывает
  своё состояние — он безусловно закрывается (`context.pop()`).
  Актуальность списка на предыдущем экране обеспечивается его собственной
  реактивной подпиской на `watchNotSyncDisposals()` (хаб неотправленных), а
  не явным вызовом от `DisposalReportCubit`.
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
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart` | `UnsentDisposalsPopulated.build`, `UnsentDisposalsPopulated._groupByEvent`, `_DisposalEventCard.onTap` | CURRENT | точка входа — тап по карточке события в хабе неотправленных, переход на `Routes.disposalReport` с `isUnsent: true`; ключ группировки карточки — `causeId_placeId_HHmm` |
| `lib/pages/reports_day_list/presentation/widgets/reports_day_list_populated.dart` | `ReportsDayListPopulated._navigateItem` (кейс `DisposalDayItem`) | CURRENT | альтернативная точка входа из общего календаря — тот же экран, но без `isUnsent` (по умолчанию `false`); пункт меню удаления не показывается |
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage.build` | CURRENT | точка входа маршрута `Routes.disposalReport`; читает `DisposalReportPageArgs` через `getExtraByName`, создаёт `DisposalReportCubit`, показывает пункт меню «Удалить» только при `args.isUnsent` |
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage._confirmAndDelete` | CURRENT | `AlertDialog` подтверждения; по «Удалить» — `await cubit.deleteEvent(args)`, затем `context.pop()` при `context.mounted` |
| `lib/widgets/go_router/go_router_state.dart` | `GoRouterState.getExtraByName` | CURRENT | извлекает `DisposalReportPageArgs` из `extra` навигации |
| `lib/widgets/more_menu/more_menu_widget.dart` | `MoreMenuWidget`, `MoreMenuAction` | CURRENT | UI-меню с единственным пунктом «Удалить» |
| `lib/pages/disposal_report/data/disposal_report_data.dart` | `DisposalReportPageArgs` | CURRENT | `date`, `causeId`, `placeId`, `reasonName`, `placeName`, `isUnsent` — параметры фильтра и гейт видимости кнопки удаления |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.deleteEvent` | CURRENT | эффект [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md) — повторная выборка `sync: false, causeId`, фильтр по дню/времени/месту в памяти, цикл удаления; `try`/`catch (_) {}` без изменения состояния |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getDisposalsWithDetailsByFilters` | CURRENT | `sync: false, causeId` — только ещё не отправленные записи данной причины, с join на `Place`/`DisposalReason`/`Animal` |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | `DisposalRepository` не переопределяет `delete` — используется этот унаследованный метод, делегирующий в `dao.del` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — физическое удаление строки по первичному ключу |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals` | CURRENT | таблица; колонка `deletedAt` существует, но не используется этим (или каким-либо локальным) путём удаления |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllDisposalsWithDetailsByFilters` | CURRENT | join с `Place`/`DisposalReason`/`Animal`, фильтр `sync`/`causeId`/`placeId` (последний не используется вызовом из `deleteEvent`) |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit` (подписка на `watchNotSyncDisposals`, `_reload`), `UnsentDisposalsCubit.deleteGroup` | CURRENT | экран-источник этого сценария — реактивно узнаёт об удалении через drift-поток, не через прямой вызов от `DisposalReportCubit`; `deleteGroup` — соседний путь ([EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)) к тому же `DisposalRepository.delete`, но с логированием ошибки через `Talker`, в отличие от `deleteEvent` |
| `lib/l10n/app_ru.arb` | `delete`, `disposal`, `cancel` | CURRENT | локализованные строки диалога подтверждения |

## Критерии приёмки

- Пункт меню «Удалить» показывается только когда `DisposalReportPageArgs.isUnsent
  == true` (путь из хаба неотправленных); при открытии того же дня из
  общего календаря (`isUnsent == false`) пункт меню отсутствует.
- Подтверждение диалога вызывает `deleteEvent(args)`, которое заново
  выбирает все `sync: false` записи выбытия данной причины
  (`causeId: args.causeId`) и включает в удаление те, для которых
  `DateUtils.dateOnly(date) == day && DateFormat('HHmm').format(date) ==
  DateFormat('HHmm').format(args.date) && placeId == args.placeId`.
- Каждая подходящая запись удаляется физически (`delete` →
  `BaseRepository.delete` → `dao.del`); `Disposal` не имеет отдельного
  признака мягкого удаления, используемого этим путём.
- Удаление записи `Disposal` не изменяет ни одно поле `Animal` — в отличие
  от Movement, здесь нет отката `placeId` или другого поля.
- Если ни одна запись не подошла под фильтр — `deleteEvent` завершается без
  единого вызова `delete` и без исключения (тот же успешный исход).
- По завершении без исключения экран отчёта закрывается (`context.pop()`)
  безусловно, не перечитывая собственное состояние.
- Хаб неотправленных отражает удаление реактивно, через подписку на
  `watchNotSyncDisposals()`, не через явный вызов от `DisposalReportCubit`.

## Связанные тесты

- `test/pages/disposal_report_cubit_test.dart`, group `'UC-103 —
  DisposalReportCubit.deleteEvent'` (старая нумерация), test `'удаляет
  только записи, совпадающие по дате+времени (с точностью до минуты) и
  месту'` — основной happy path этого сценария: три записи с одинаковым
  `causeId`, из которых одна совпадает по дате+времени+месту (`matching`),
  одна отличается местом (`wrongPlace`), одна отличается временем
  (`wrongTime`, тот же день, час позже); `getDisposalsWithDetailsByFilters`
  замокан на возврат всех трёх с параметрами `sync: false, causeId: 2` (без
  `placeId` — подтверждает, что вызов из `deleteEvent` не передаёт `placeId`
  в запрос); после `cubit.deleteEvent(args)` проверяется `verify(() =>
  disposalRepository.delete(matching.disposal)).called(1)` и `verifyNever`
  для `wrongPlace`/`wrongTime`. В этом тесте `DisposalRepository.delete`
  замокан целиком (`thenAnswer((_) async => 1)`), поэтому реальный путь
  `BaseRepository.delete` → `dao.del` → `deleteCurrent().delete` этим тестом
  не проверяется — только факт вызова `repository.delete(...)` с ожидаемой
  записью.
- Соседняя group `'UC-104 — DisposalReportCubit.deleteEvent'` в том же файле
  покрывает `DELETE_ERROR`-исход того же метода (исключение при чтении,
  `catch (_) {}` глотает его, состояние кубита не меняется) — не
  документируемый этим файлом.
- TBD — теста нет на уровне репозитория/DAO для
  `DisposalsDao.getAllDisposalsWithDetailsByFilters`/`BaseDao.del`,
  вызванных именно через этот путь, не замоканных ради проверки реального
  физического удаления строки — существующий тест мокает
  `DisposalRepository` целиком.
- TBD — теста нет на уровне, связывающем UI-диалог подтверждения
  (`DisposalReportPage._confirmAndDelete`) с реальным
  `DisposalReportCubit.deleteEvent` в одном widget/e2e-потоке — существующий
  тест проверяет только сам кубит напрямую, без прохождения через
  `AlertDialog`/`MoreMenuWidget`.
- TBD — теста нет, подтверждающего реактивное обновление
  `UnsentDisposalsCubit` через `watchNotSyncDisposals()` именно как следствие
  удаления, выполненного из `DisposalReportCubit.deleteEvent` (а не из
  `UnsentDisposalsCubit.deleteGroup`) — оба пути ведут к одному и тому же
  `DisposalRepository.delete`, но связка «удаление в отчёте → реактивное
  обновление хаба» не покрыта отдельным тестом.

## Открытые вопросы и ограничения

- **Молчаливое глотание всех исключений (`try`/`catch (_) {}`).** Ни
  успешный, ни ошибочный исход не меняют состояние `DisposalReportCubit` —
  пользователь не получает обратной связи об ошибке ни на уровне кубита, ни
  через какой-либо лог (`Talker` здесь не используется, в отличие от
  `UnsentDisposalsCubit.deleteGroup`, которая логирует ошибку через
  `getIt<Talker>().error`). UI закрывает экран (`context.pop()`)
  независимо от того, было ли реально что-то удалено или метод упал с
  исключением на первой же строке.
- **Частичный эффект при исключении в середине цикла.** Если
  `_disposalRepo.delete` бросает исключение не на первой итерации, записи,
  удалённые до этого момента, остаются удалёнными — отката уже
  выполненных удалений нет; внешний `try`/`catch (_) {}` останавливает
  только продолжение цикла, не откатывает уже случившееся. Не покрыто
  отдельным тестом (частично смежно с `RESULT = DELETE_ERROR`, не
  описанным этим файлом).
- **Нет прямого теста реального (немокнутого) физического удаления строки
  и join-запроса `getAllDisposalsWithDetailsByFilters`** через этот
  конкретный путь — единственный существующий тест мокает
  `DisposalRepository` целиком.
- Дальнейшая судьба уже физически удалённых записей в последующем
  sync-проходе (они просто отсутствуют — синхронизировать нечего) не
  описана отдельным событием/сценарием — вне периметра этого файла.
