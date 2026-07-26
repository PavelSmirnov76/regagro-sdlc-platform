# UC-112 — Посуточный отчёт о выбытии отказывает технически: `DisposalReportCubit.load` ловит исключение и эмитит `error(e.toString())` — в отличие от `deleteEvent` того же кубита, глотающего исключение молча (READ_ERROR)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-56](../events/EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-56](../events/EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)
(`disposals.viewed_in_day_report`) так, как он реализован в
`DisposalReportCubit.load` (`lib/pages/disposal_report/cubit/disposal_report_cubit.dart`):
пользователь открывает посуточный отчёт по выбытию для места/причины/дня, но
чтение и группировка записей [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)
бросают исключение — техническая ошибка (Drift/БД или любое другое
исключение уровня данных), не бизнес-отказ: в методе нет ни одного
guard-условия, способного сознательно вернуть `REJECTED` — отчёт либо
строится по тому, что нашлось (включая пустой список), либо технически
падает. Весь код метода, от чтения до построения групп, обёрнут в один
`try`; единственный `catch (e)` безусловно эмитит
`DisposalReportState.error(e.toString())` — сырой текст исключения, без
логирования и без стек-трейса.

Это **прямая противоположность** тому, как тот же класс обрабатывает ошибку в
своём втором публичном методе. `DisposalReportCubit.deleteEvent` (описан для
`ERROR`-исхода в [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md))
оборачивает свой код в `try { ... } catch (_) {}` — полностью пустой блок,
который никогда не эмитит и не логирует. `load` и `deleteEvent` — два
метода одного и того же `DisposalReportCubit`, оба оборачивают в `try`
похожие вызовы `DisposalRepository`, и обрабатывают отказ противоположно:
`load` делает ошибку видимой пользователю (через `BlocBuilder` → `error`
ветка → текст на экране), `deleteEvent` — полностью её прячет. Тот же
контраст (обработка `load` эмитит, обработка delete-действия молчит)
повторяется и в MOVE-под-области — `MovementReportCubit.load`/`deleteEvent`
устроены идентично (см. «Альтернативные потоки» и [UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)).
У сестринских отчётных кубитов WEIGH и VAC такого delete-действия вообще нет
(см. ниже), поэтому там нет и самой возможности для такой асимметрии — их
`load` эмитит ошибку так же, как здесь ([UC-98](UC-98-ACTOR-5-EVT-49-ENT-15-READ_ERROR-IN-ANIMAL.md),
[UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md)).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково), открывающий экран
посуточного отчёта о выбытии либо из календаря событий, либо из хаба «В
работе»/неотправленных выбытий (`args.isUnsent == true`). Проверено чтением
`disposal_report_cubit.dart` целиком: ни `load`, ни остальные методы класса
не читают `AuthRepository` и не проверяют статус авторизации.

## CURRENT

### Основной поток

1. **Точка входа.** `DisposalReportPage.build`
   (`lib/pages/disposal_report/presentation/disposal_report_page.dart`)
   строит `BlocProvider(create: (context) => DisposalReportCubit()..load(args))`,
   где `args` — `DisposalReportPageArgs`, полученный из
   `GoRouterState.of(context).getExtraByName<DisposalReportPageArgs>(Routes.disposalReport)`.
   `load` запускается безусловно при создании экрана, независимо от того,
   открыт ли он из общего дневного отчёта (`isUnsent == false`) или из хаба
   неотправленных (`isUnsent == true`).
2. `DisposalReportCubit.load` немедленно эмитит
   `DisposalReportState.loading()`. `BlocBuilder` в `DisposalReportPage`
   переключает `body` в ветку `loading` (`CustomLottieLoader`), в то время
   как заголовок/дата/`actions` (`MoreMenuWidget`, если `isUnsent`) уже
   отрисованы через `EventReportScaffold`.
3. Внутри `try`: вычисляются `day = DateUtils.dateOnly(args.date)` и
   `timeKey = DateFormat('HHmm').format(args.date)`, затем `await
   _disposalRepo.getDisposalsWithDetailsByFilters(sync: args.isUnsent ? false
   : null, causeId: args.causeId, placeId: args.placeId)` — единственный
   вызов репозитория в этом методе.
4. **Технический отказ.** Если `getDisposalsWithDetailsByFilters` бросает
   исключение (например, ошибка Drift/SQLite при чтении), управление сразу
   переходит к `catch (e)` — шаги 5–7 (фильтрация, группировка, финальный
   `emit(loaded)`) не выполняются вовсе, потому что весь этот код физически
   находится дальше в том же `try`-блоке. То же верно, если исключение
   бросает не сам вызов репозитория, а последующая in-memory фильтрация
   (`all.where(...)`, шаг 5 при успешном чтении) или построение групп (шаг
   6) — `catch` накрывает всё тело метода целиком, а не только вызов
   репозитория.
5. *(при успешном чтении, не входит в этот ERROR-сценарий)* Результат
   фильтруется по точному совпадению дня и времени с точностью до минуты
   (`DateUtils.dateOnly(date).isAtSameMomentAs(day) &&
   DateFormat('HHmm').format(date) == timeKey`), затем группируется по
   `d.animal?.ageGroup?.name ?? d.animal?.kind?.name ?? '-'` в
   `Map<String, List<EventReportAnimalEntry>>`.
6. *(при успешном чтении)* Строится список `DisposalAnimalGroup` и эмитится
   `DisposalReportState.loaded(...)`.
7. **`catch (e)`.** Единственная строка обработчика:
   `emit(DisposalReportState.error(e.toString()))`. Никакого вызова
   `getIt<Talker>().error(...)`, `print`/`debugPrint` или иного побочного
   эффекта внутри `catch` нет — сравнимо с тем, что зафиксировано для
   `deleteEvent` в [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md),
   но здесь, в отличие от `deleteEvent`, состояние всё же меняется — просто
   без логирования на этом пути.
8. `load` возвращает управление нормально (`Future<void>`, успешно
   разрешённая — исключение не пробрасывается наружу вызывающего кода).
9. `DisposalReportPage`'s `BlocBuilder` перерисовывается на этот `emit`:
   `state.when(... error: (msg) => Center(child: Text(msg, style: const
   TextStyle(color: AppColors.white))))`. Экран не закрывается, снэкбар не
   показывается — сообщение выводится напрямую как обычный `Text` в теле
   `EventReportScaffold`. Заголовок (`l10n.disposal`), дата и `actions`
   (пункт меню «Удалить», если `isUnsent`) продолжают отображаться как
   обычно — от состояния `error` зависит только содержимое `body`, `actions`
   вычисляется из `args`, не из `state`, и остаётся доступен для нажатия
   независимо от того, что отчёт не загрузился.
10. Сообщение, показанное пользователю — сырой `e.toString()` (например,
    `"Exception: db error"`), не прогнанный через `AppLocalizations` и не
    переформулированный в пользовательский текст.

### Альтернативные потоки

- **OK-исход того же метода — не входит в этот сценарий.** Если
  `getDisposalsWithDetailsByFilters` и последующая группировка проходят без
  исключения, эмитится `DisposalReportState.loaded(...)` (шаги 5–6). На
  момент написания этого файла отдельный use-case-документ для `READ_OK`
  этого же события в дереве `sdlc/2-specs/use-cases/` не найден — существует
  только тестовая группа-якорь `'UC-111 — DisposalReportCubit.load'` в
  `test/pages/disposal_report_cubit_test.dart` без соответствующего
  `.md`-файла (см. «Открытые вопросы», тот же разрыв, что
  [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md) отмечает
  для `EVT-52`/`DELETE_OK`).
- **Противоположная обработка ошибки в `deleteEvent` того же класса** —
  [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md). Тот же
  `DisposalReportCubit`, тот же паттерн `try { ... } catch (...) { ... }`
  вокруг вызовов `DisposalRepository`, но `deleteEvent`'s `catch (_) {}`
  полностью пуст: не эмитит, не логирует, а вызывающий UI
  (`_confirmAndDelete`) закрывает экран отчёта безусловно после `await`,
  независимо от исхода. `load`, документируемый здесь, — единственный из
  двух методов класса, чья ошибка вообще становится видимой пользователю.
- **Точная параллель в MOVE-под-области.** `MovementReportCubit.load`
  (`lib/pages/movement_report/cubit/movement_report_cubit.dart`) устроен
  идентично: тот же `try { ... } catch (e) { emit(MovementReportState.error(e.toString())); }`
  вокруг чтения/группировки, и та же противоположность своему
  `deleteEvent`'s `catch (_) {}` ([UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)).
  Асимметрия «load эмитит / delete-действие молчит» — не случайность одного
  файла, а повторяющийся паттерн копипаста между отчётными cubit'ами модуля
  ANIMAL, воспроизведённый как минимум дважды (DISP, MOVE).
- **У WEIGH и VAC такой асимметрии в принципе нет.**
  `WeighingReportCubit` (`lib/pages/weighing_report/cubit/weighing_report_cubit.dart`,
  [UC-98](UC-98-ACTOR-5-EVT-49-ENT-15-READ_ERROR-IN-ANIMAL.md)) и
  `VaccinationReportCubit` (`lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart`,
  [UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md)) реализуют
  ровно тот же паттерн `load` (`catch (e)` → `emit(...State.error(e.toString()))`),
  но ни один из этих двух классов не объявляет метода-аналога
  `deleteEvent` вообще — проверено чтением обоих файлов целиком. Контраст
  «видимая ошибка чтения vs молчаливая ошибка удаления» существует только
  там, где у отчётного кубита есть собственное delete-действие
  (`disposal.deleted_via_report` / `movement.deleted_via_report`), то есть
  только в DISP и MOVE.
- **Вход из общего дневного отчёта vs из хаба неотправленных.** Единственная
  разница между `args.isUnsent == true` и `== false` внутри `load` —
  параметр `sync` вызова репозитория (`false` вместо `null`); обработка
  ошибки одинакова в обоих случаях.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сущность,
  которую сценарий пытается прочитать; это же `ENT`-сегмент имени файла. При
  отказе ни одна запись не попадает в состояние `loaded` — предыдущий
  `loading()` заменяется на `error(...)`, список групп/животных не строится.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  косвенно через `DisposalWithDetails.animal` (`ageGroup`/`kind`/
  `firstMainNumber`) для построения групп при успехе; при отказе (этот
  сценарий) не читается вовсе, потому что исключение прерывает поток до
  того, как эти поля используются, либо само чтение/использование этих
  полей — и есть источник исключения (шаг 4). Ни в одном случае `Animal` не
  изменяется.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — `args.reasonName`/`args.causeId` приходят готовыми аргументами
  экрана (см. `DisposalReportPageArgs`), `load` не выполняет собственный
  lookup причины по справочнику — при отказе это не имеет значения, так как
  `reasonName` в состояние `error` вообще не попадает.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) /
  [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) —
  аналогично: `args.placeName`/`args.placeId` — готовые аргументы экрана, не
  результат lookup внутри `load`.

### Бизнес-правила

- `try` в `load` оборачивает весь код метода — вызов репозитория,
  in-memory фильтрацию и построение групп — единым блоком; `catch (e)`
  реагирует одинаково независимо от того, на каком из этих шагов возникло
  исключение.
- `catch (e)` безусловно перезаписывает предыдущее состояние
  (`DisposalReportState.loading()`, эмитированное на шаге 2) состоянием
  `error(e.toString())` — без проверки типа исключения, без ветвления.
- Внутри `catch` нет ни одного вызова логирования (`Talker`/`log`/
  `print`/`debugPrint`) — идентично `deleteEvent` в этом отношении (см.
  [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md)), хотя в
  отличие от `deleteEvent` состояние здесь всё же меняется и достигает UI.
- Текст ошибки, показанный пользователю, — сырой `e.toString()`, не
  локализованный через `AppLocalizations` и не сформулированный как
  пользовательское сообщение.
- Правило проекта показывать ошибки через `lib/widgets/app_snackbar.dart`
  (`showAppSnackBarError` и т.д., `.claude/rules/ui-architecture.md`) в этом
  обработчике не применяется — ошибка рендерится как обычный `Text` внутри
  `body` слота `EventReportScaffold`, а не как снэкбар/диалог.
- `EventReportScaffold.actions` вычисляется из `args.isUnsent`, а не из
  `state` кубита — пункт меню «Удалить» остаётся видимым и активным даже
  когда `body` показывает ошибку чтения; нажатие на него запускает
  `deleteEvent` независимо от того, что `load` только что технически отказал
  (см. «Альтернативные потоки»).
- Асимметрия обработки ошибок внутри одного и того же `DisposalReportCubit`:
  `load`'s `catch (e)` эмитит и, тем самым, делает отказ видимым
  пользователю; `deleteEvent`'s `catch (_) {}` (см.
  [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md)) не
  эмитит ничего и полностью скрывает отказ. Это не два разных класса с
  разными конвенциями — это один класс, применяющий обе конвенции к двум
  соседним своим методам.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — путь технического отказа `load` (единый `try`, единственный
`catch (e)`, безусловный `emit(error(...))`) полностью прослеживается в
существующем коде и покрыт тестом. Единственные практические разрывы —
отсутствие отдельного `.md`-документа на `READ_OK`-исход того же метода и
отсутствие теста, различающего источник исключения (репозиторий vs
in-memory группировка) — см. «Открытые вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage.build` (`BlocProvider(create: (context) => DisposalReportCubit()..load(args))`) | CURRENT | точка входа, безусловно запускает `load` при создании экрана |
| `lib/pages/disposal_report/presentation/disposal_report_page.dart` | `DisposalReportPage.build` (`state.when(... error: (msg) => Center(child: Text(msg, ...)))`) | CURRENT | рендерит текст ошибки в `body`, не меняя заголовок/дату/`actions` |
| `lib/pages/disposal_report/data/disposal_report_data.dart` | `DisposalReportPageArgs` | CURRENT | `date`/`causeId`/`placeId`/`isUnsent`/`reasonName`/`placeName`, передаваемые в `load` |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.load` | CURRENT | `try { ... } catch (e) { emit(DisposalReportState.error(e.toString())); }` |
| `lib/pages/disposal_report/cubit/disposal_report_cubit.dart` | `DisposalReportCubit.deleteEvent` | CURRENT | контраст — `catch (_) {}` того же класса никогда не эмитит (см. [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md)) |
| `lib/pages/disposal_report/cubit/disposal_report_state.dart` | `DisposalReportState` (вариант `error`) | CURRENT | freezed union-вариант, реально достигаемый этим путём (в отличие от `deleteEvent`) |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getDisposalsWithDetailsByFilters` | CURRENT | источник исключения в основном документируемом варианте отказа |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllDisposalsWithDetailsByFilters` | CURRENT | реальный Drift-запрос, лежащий в основе чтения |
| `lib/widgets/event_report/event_report_template.dart` | `EventReportScaffold` | CURRENT | оболочка экрана — `title`/`date`/`actions` не зависят от `state`, только `body` |
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.load` | CURRENT | идентичный паттерн в сестринской MOVE-под-области (для сравнения) |
| `lib/pages/weighing_report/cubit/weighing_report_cubit.dart` | `WeighingReportCubit.load` | CURRENT | идентичный паттерн в WEIGH, без соответствующего delete-метода (см. [UC-98](UC-98-ACTOR-5-EVT-49-ENT-15-READ_ERROR-IN-ANIMAL.md)) |
| `lib/pages/vaccination_report/cubit/vaccination_report_cubit.dart` | `VaccinationReportCubit.load` | CURRENT | идентичный паттерн в VAC, без соответствующего delete-метода (см. [UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md)) |

## Критерии приёмки

- Если `DisposalRepository.getDisposalsWithDetailsByFilters` бросает
  исключение внутри `DisposalReportCubit.load`, вызов `load(args)`
  завершается нормально (`completes`, исключение не пробрасывается наружу),
  а `cubit.state` становится `DisposalReportState.error(message)`, где
  `message` содержит текст исключения (`e.toString()`).
- Ни один вызов логирования (`Talker`/`log`/иное) не происходит внутри
  `catch`-блока `load`.
- `DisposalReportPage` при получении состояния `error` отображает `msg` как
  текст в теле экрана; заголовок, дата и (при `isUnsent == true`) пункт меню
  «Удалить» продолжают отображаться без изменений.
- В отличие от `deleteEvent` того же кубита (см.
  [UC-104](UC-104-ACTOR-5-EVT-52-ENT-16-DELETE_ERROR-IN-ANIMAL.md)), эта
  ошибка действительно меняет наблюдаемое состояние кубита — асимметрия
  между двумя методами одного класса должна оставаться проверяемой отдельно
  для каждого из них.

## Связанные тесты

`test/pages/disposal_report_cubit_test.dart`, group `'UC-112 —
DisposalReportCubit.load'` (переименуется отдельным контролируемым проходом
позже, не трогать сейчас):

- test `'ошибка репозитория -> error с текстом исключения'` — мок
  `disposalRepository.getDisposalsWithDetailsByFilters(sync: false, causeId:
  2, placeId: 5)` настроен `thenThrow(Exception('db error'))`; тест создаёт
  `DisposalReportCubit()`, вызывает `await cubit.load(args)` (без обёртки в
  `expectLater`/`throwsA`, то есть неявно подтверждает, что исключение не
  пробрасывается наружу), затем через `cubit.state.when(...)` проверяет, что
  достигнута именно ветка `error`, и `expect(message, contains('db error'))`.
- Смежная, но не относящаяся к этому ERROR-документу group `'UC-111 —
  DisposalReportCubit.load'` (строки выше в том же файле) покрывает
  успешный путь фильтрации по дню/времени/`isUnsent` — соответствует
  `READ_OK`-исходу того же события, отдельный `.md`-документ на который пока
  не существует (см. «Открытые вопросы»).
- **TBD — теста нет**, различающего источник исключения: ни один
  существующий тест не настраивает мок так, чтобы `getDisposalsWithDetailsByFilters`
  прошёл успешно, а исключение возникло позже — в in-memory фильтрации/
  группировке (шаги 5–6 «Основного потока»). Существующий тест покрывает
  только отказ самого вызова репозитория.
- **TBD — теста нет** на реальный UI-эффект (`DisposalReportPage` рендерит
  `Text(msg, ...)` в `body`, `actions` остаётся видимым при `isUnsent`) —
  покрытие есть только на уровне кубита, не на уровне виджета/страницы.

## Открытые вопросы и ограничения

- **`READ_OK`-исход того же метода (`disposals.viewed_in_day_report` /
  `READ_OK`) на момент написания этого файла ещё не задокументирован
  отдельным use-case** (`UC-*-ACTOR-5-EVT-56-ENT-16-READ_OK-IN-ANIMAL.md` в
  дереве `sdlc/2-specs/use-cases/` не найден) — существует только тестовая
  группа-якорь `'UC-111 — DisposalReportCubit.load'`. Как только
  соответствующий файл появится, стоит добавить на него ссылку из
  «Назначения» и из «Альтернативных потоков» этого документа отдельной,
  контролируемой правкой.
- **Асимметрия «`load` эмитит / `deleteEvent` молчит» — не общая для всего
  модуля ANIMAL, а специфична для под-областей, у которых вообще есть
  delete-via-report действие (DISP, MOVE).** WEIGH и VAC демонстрируют
  тот же паттерн `load`, но не имеют аналогичного `deleteEvent`, так что
  сравнивать там нечего — это ограничивает область применимости вывода
  «один и тот же класс обрабатывает ошибку по-разному», сделанного в
  «Назначении», именно двумя под-областями, а не всеми четырьмя.
- **Правило проекта об использовании `app_snackbar.dart` для отображения
  ошибок не применяется в этом обработчике** — ошибка рендерится напрямую
  как `Text` внутри тела экрана, минуя стандартный хелпер. Зафиксировано как
  факт CURRENT, не исправляется в рамках этого документирующего прохода
  (TARGET == CURRENT).
- Нужно ли вообще что-то менять здесь (логирование, локализация текста
  ошибки, единообразие с `deleteEvent`, скрытие «Удалить» при ошибке
  чтения) — вопрос будущего TARGET-прохода, не разрешается этим документом:
  он фиксирует только то, что есть в коде сегодня.
