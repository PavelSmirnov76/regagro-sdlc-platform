# UC-109 — Пользователь открывает хаб ещё не отправленных выбытий

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-55](../events/EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает отдельный экран-хаб (`UnsentDisposalsPage`),
показывающий все локально созданные, ещё не отправленные на сервер записи
`Disposal` (`sync == false`) — по всем животным фермы сразу, сгруппированные
на UI-уровне в карточки «событий выбытия». Экран — обычно один из пунктов
сводного экрана «В работе» — основа для последующего группового удаления
карточки ([EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md), см.
[UC-101](UC-101-ACTOR-5-EVT-51-ENT-16-DELETE_OK-IN-ANIMAL.md)) либо перехода в
посуточный отчёт по этой же группе (`Routes.disposalReport` с `isUnsent:
true`) — сама навигация в отчёт вне периметра этого файла.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `UnsentDisposalsPage`, ни
`UnsentDisposalsCubit`, ни read-путь `DisposalRepository`
(`watchNotSyncDisposals`/`getDisposalsWithDetailsByFilters`) не проверяют
статус авторизации (`grep -rn "isAuthorized|AuthRepository"` по
`lib/pages/animal_disposal/presentation/unsent_disposal/`,
`lib/pages/animal_disposal/cubit/unsent_disposal/` не находит совпадений;
единственное использование `AuthRepository` в `DisposalRepository` — внутри
`sendDisposalList`, на пути отправки, не чтения). Единственное предусловие —
переход с плитки «Выбытие» экрана «В работе» (`Routes.unsentDisposals`) или
напрямую по имени этого маршрута, у которого нет собственных аргументов.

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`) и нажимает плитку
   «Выбытие» (`EventTileData` с `icon: Assets.eventDisposal`, `count:
   data.disposalListsCount`) — `onTap: () =>
   context.pushNamed2(Routes.unsentDisposals)` (`lib/pages/in_work/in_work_page.dart`).
   Плитка нажимаема независимо от значения `count` — `onTap` не гейтится
   проверкой количества; числовой бейдж на плитке (`_CountBadge`) сам по себе
   рисуется только когда `count != null && count > 0`
   (`lib/widgets/event_card_widget.dart`), но это не влияет на доступность
   перехода.
2. `Routes.unsentDisposals` — маршрут верхнего уровня, зарегистрирован в
   `lib/pages/routes.dart` (`CustomGoRoute.fade(name: Routes.unsentDisposals,
   path: Routes.unsentDisposals, builder: (context, state) =>
   const UnsentDisposalsPage())`), без собственных аргументов конструктора.
3. `UnsentDisposalsPage.build` оборачивает тело в `BlocProvider(create:
   (context) => UnsentDisposalsCubit()..load())` — `load()` вызывается один
   раз, сразу при создании кубита.
4. Конструктор `UnsentDisposalsCubit` стартует в состоянии
   `UnsentDisposalsState.initial()` и **одновременно** подписывается на
   `_disposalRepository.watchNotSyncDisposals()`
   (`DisposalRepository.watchNotSyncDisposals` → `DisposalsDao.watchAllNotSync`
   — Drift `.watch()`-стрим строк `Disposals` с `sync == false`): на любую
   эмиссию этого стрима (независимо от содержимого) кубит вызывает `_reload()`
   заново, не только по явному вызову `load()`.
5. `load()` эмитит `UnsentDisposalsState.loading()`, затем в `try`/`catch`
   вызывает `await _reload()`.
6. `_reload()`: если кубит уже закрыт (`isClosed`) — выходит без действия;
   иначе, в собственном `try`/`catch`, вызывает
   `_disposalRepository.getDisposalsWithDetailsByFilters(sync: false)`
   (→ `DisposalsDao.getAllDisposalsWithDetailsByFilters(sync: false)`).
7. DAO строит join `disposals` (алиас) с `places` (`leftOuterJoin` по
   `pAlias.idRemote == dAlias.placeId`) и `disposalReasons` (`leftOuterJoin`
   по `rAlias.id == dAlias.causeId`), с единственным явным предикатом
   `dAlias.sync.equals(false)` (параметры `animalIds`/`causeId`/`placeId`
   этого вызова не переданы — `getDisposalsWithDetailsByFilters(sync:
   false)` не задаёт их). Запрос **не содержит `orderBy`** — порядок строк
   результата не гарантирован запросом (в отличие от аналогичных read-хабов
   вакцинаций и взвешиваний, где сортировка задана явно на уровне
   DAO/join'а или самого кубита).
8. Для собранного результата DAO одним дополнительным запросом подтягивает
   животных: `db.animalsDao.getAllAnimalsWithDetailsByFilters(ids:
   result.map((e) => e.read(dAlias.animalId) ?? 0), isNotDeleted: null)` —
   один запрос на весь список (не построчно/N+1, в отличие от read-хабов
   вакцинаций и взвешиваний), `isNotDeleted: null` явно отключает фильтр по
   выбывшим — животное попадает в `DisposalWithDetails.animal` независимо от
   того, помечено ли оно уже выбывшим на сервере.
9. Каждая строка собирается в `DisposalWithDetails(disposal: ..., animal:
   animals.firstWhereOrNull((a) => a.animal.id ==
   e.read(dAlias.animalId)), place: ..., reason: ...)` — `place`/`reason`
   читаются из `readTableOrNull`, могут быть `null`, если `placeId`/`causeId`
   не резолвятся join'ом.
10. Обратно в `_reload()`: если кубит не закрыт — эмитит
    `UnsentDisposalsState.empty()`, если список пуст, иначе
    `UnsentDisposalsState.loaded(disposals: <список>)`. Дальнейшая сортировка
    списка на уровне кубита/DAO не производится.
11. `UnsentDisposalsView` (`BlocBuilder<UnsentDisposalsCubit,
    UnsentDisposalsState>`) рендерит `Scaffold` с `CustomAppBar(title:
    l10n.disposal)` и телом по `state.when(...)`:
    - `initial` → `SizedBox.shrink()`.
    - `loading` → `BottomSheetPageWrapper` с `CustomLottieLoader`.
    - `loaded(disposals)` → `UnsentDisposalsPopulated(disposals:
      disposals, onTapDelete:
      context.read<UnsentDisposalsCubit>().deleteGroup)`.
    - `empty` → `BottomSheetPageWrapper` с `ProgressMessage.notFound(message:
      l10n.list_is_empty)`.
12. `UnsentDisposalsPopulated._groupByEvent()` — **только на этом,
    UI-уровне**, не в кубите/DAO — группирует переданный список по ключу
    `'${d.disposal.causeId}_${d.disposal.placeId}_$timeKey'`, где `timeKey =
    DateFormat('HHmm').format(date)`, а `date = d.disposal.date ??
    d.disposal.createdAt ?? DateTime.now()`; итоговый список групп
    сортируется `result.sort((a, b) => b.date.compareTo(a.date))` — по
    убыванию даты события. Это единственное место во всём потоке, где
    список получает детерминированный порядок.
13. `build` рендерит `ListView.separated` из `_DisposalEventCard` — по одной
    карточке на группу, с причиной (`reason?.name`), местом (`place?.name`,
    только если не `null`), датой+временем группы и количеством животных
    (`event.count`), и иконкой удаления (`Icons.delete_outline`).

### Альтернативные потоки

- **Пустой список (`UnsentDisposalsState.empty()` из-за реально пустого
  результата запроса).** Не ошибка — `getDisposalsWithDetailsByFilters(sync:
  false)` вернул `[]` (нет ни одной ещё не отправленной записи выбытия).
  `UnsentDisposalsView` показывает `ProgressMessage.notFound(l10n.list_is_empty)`
  вместо списка карточек. Тот же `RESULT` (`READ_OK`), другой визуальный
  итог — предмет этого файла (см. «Основной поток», шаг 11).
- **Исключение внутри `getDisposalsWithDetailsByFilters()`, пойманное
  `_reload()`.** `_reload()`'s собственный `try`/`catch` перехватывает любое
  исключение и (если кубит не закрыт) эмитит **то же самое**
  `UnsentDisposalsState.empty()`, что и при реально пустом списке —
  `UnsentDisposalsState` не имеет отдельного варианта ошибки
  (`initial`/`loading`/`loaded`/`empty` — и всё, см.
  `unsent_disposals_state.dart`). На уровне UI этот случай неотличим от
  «данных действительно нет» — оба заканчиваются одним и тем же экраном
  `list_is_empty`. Внешний `try`/`catch` метода `load()` в этой ветке кода
  фактически недостижим (тело `_reload()` уже гасит любое своё исключение
  внутри себя) — сработал бы только если бы исключение возникло вне тела
  `_reload()`, например при самом вызове `emit(loading())`, что не
  наблюдалось. Отдельный `RESULT = READ_ERROR` для этого случая по коду не
  выделен — состояние экрана буквально совпадает с READ_OK-пустым вариантом;
  тестово этот путь заякорен отдельной группой `'UC-110 —
  UnsentDisposalsCubit.load'` (см. «Связанные тесты» и «Открытые вопросы»).
- **Реактивная перезагрузка независимо от явного `load()`.** Конструктор
  подписывается на `watchNotSyncDisposals()` в момент создания кубита — то
  же самое действие (`load()` через `BlocProvider(create: ...)`) запускает и
  явный вызов `load()`, и (по документированному поведению Drift-стримов
  `.watch()`, которые эмитят текущий результат сразу при подписке, а не
  только при последующих изменениях таблицы) первую эмиссию из этой
  подписки — оба пути вызывают `_reload()` независимо друг от друга
  примерно в одно и то же время при открытии экрана. Практического
  расхождения в итоговом состоянии это не даёт (оба читают одни и те же
  данные), но означает, что при обычном открытии экрана `_reload()` может
  выполниться дважды подряд. Это утверждение о самой Drift-эмиссии на
  подписку не подтверждено интеграционным тестом с реальной БД — юнит-тесты
  кубита мокают `DisposalRepository` целиком и используют обычный (не
  drift'овый) `StreamController`, который ничего не эмитит без явного
  `.add(...)` в тесте (см. «Связанные тесты»).

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — единственная
  сущность, чьё состояние отображает этот экран; читаются все строки с
  `sync == false`, без ограничения по `animalId`/`causeId`/`placeId` (эти
  параметры `getDisposalsWithDetailsByFilters` в этом вызове не переданы).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — подгружается
  одним общим запросом (`getAllAnimalsWithDetailsByFilters(ids: ..., isNotDeleted:
  null)`) для всех строк результата разом; фильтр по выбывшим явно отключён
  (`isNotDeleted: null`) — животное попадает в результат независимо от того,
  выбыло оно уже на сервере или нет. На карточках этого экрана
  (`_DisposalEventCard`) поля животного (например номер) не отображаются —
  используется только количество (`event.count`).
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — читается join'ом (`reason`), показывается на карточке как
  причина выбытия.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — читается
  join'ом (`place`, по `pAlias.idRemote == dAlias.placeId`), показывается на
  карточке, только если не `null`.

### Бизнес-правила

- **Список этого экрана глобален по всем животным фермы** — единственный
  явный предикат запроса — `sync == false`, без фильтра по `animalId`.
- **Числовой бейдж плитки «Выбытие» на «В работе» и список этого экрана
  используют один и тот же явный предикат** (`sync == false`) — в отличие от
  аналогичной пары «бейдж/список» у вакцинаций, где предикаты списка и
  count-запроса не идентичны буквально: `InWorkBloc` считает
  `disposalListsCount` через `DisposalRepository.watchCountNotSync()` →
  `DisposalsDao.watchCountNotSync()` (`WHERE sync = 0`), тот же единственный
  предикат, что и у `getAllDisposalsWithDetailsByFilters(sync: false)`.
- **Сортировка/группировка списка целиком на UI-уровне, не в
  кубите/DAO.** `UnsentDisposalsState.loaded` несёт список в порядке,
  который вернул SQL-запрос (без `orderBy`) — единственный детерминированный
  порядок появляется только внутри `UnsentDisposalsPopulated._groupByEvent`
  (группировка по `causeId`+`placeId`+`HH:mm`, сортировка групп по убыванию
  даты). Кубит/состояние не гарантируют никакого порядка сами по себе.
- Экран реактивно подписан на изменения таблицы `Disposals`
  (`watchNotSyncDisposals()`) — в отличие от аналогичных read-хабов
  вакцинаций и взвешиваний, которые загружаются один раз и не переподписаны
  на таблицу; любое изменение (`sync == false`-строк) в любом месте
  приложения перезагружает уже открытый экран без участия пользователя.
- Не существует отдельного варианта состояния для ошибки — `_reload()`
  сводит и «реально пусто», и «исключение при чтении» к одному и тому же
  `UnsentDisposalsState.empty()`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (оба варианта успеха: непустой список и пустой список)
полностью реализован и достижим из реального UI.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (плитка `EventTileData` с `icon: Assets.eventDisposal`) | CURRENT | обычная точка входа — переход по `Routes.unsentDisposals` |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (подписка `_unsentDisposalListsCountSubscription` на `DisposalRepository.watchCountNotSync`) | CURRENT | считает бейдж плитки; предикат идентичен списку этого экрана, но запрос отдельный, не используется самим хабом напрямую |
| `lib/widgets/event_card_widget.dart` | `EventTileData`, `_CountBadge` | CURRENT | бейдж плитки рисуется только при `count != null && count > 0`; не гейтит сам `onTap` |
| `lib/pages/routes.dart` | `Routes.unsentDisposals` | CURRENT | имя/путь маршрута → `UnsentDisposalsPage`, без аргументов |
| `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart` | `UnsentDisposalsPage.build` | CURRENT | создаёт кубит, вызывает `load()` один раз |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit` (конструктор, `_watchSubscription`), `UnsentDisposalsCubit.load`, `UnsentDisposalsCubit._reload` | CURRENT | предмет этого файла — подписка на `watchNotSyncDisposals()`, загрузка/перезагрузка списка |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart` | `UnsentDisposalsState` (`initial`/`loading`/`loaded`/`empty`) | CURRENT | freezed-состояние кубита — нет отдельного варианта ошибки |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_view.dart` | `UnsentDisposalsView.build` | CURRENT | `BlocBuilder`, рендерит все четыре состояния (`state.when`) |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart` | `UnsentDisposalsPopulated._groupByEvent`, `_DisposalEventCard.build` | CURRENT | единственное место, где список получает детерминированный порядок (группировка + сортировка по дате по убыванию) |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.watchNotSyncDisposals`, `getDisposalsWithDetailsByFilters` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.watchAllNotSync`, `getAllDisposalsWithDetailsByFilters` | CURRENT | Drift-стрим и join-запрос (`sync = 0`, без `orderBy`), плюс один общий запрос животных (`isNotDeleted: null`) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | один общий (не построчный) запрос животных для всего списка результата |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_with_details.dart` | `DisposalWithDetails` | CURRENT | модель строки (`disposal`, `animal`, `place`, `reason`) |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.notFound` | CURRENT | UI пустого состояния |
| `lib/widgets/loader/custom_lottie_loader.dart` | `CustomLottieLoader` | CURRENT | UI состояния загрузки |
| `lib/widgets/bottom_sheet_page_wrapper.dart` | `BottomSheetPageWrapper` | CURRENT | обёртка тела экрана для loading/loaded/empty |

## Критерии приёмки

- При открытии хаба (`Routes.unsentDisposals`) кубит вызывает `load()` один
  раз без участия пользователя, независимо от текущего значения бейджа
  плитки «Выбытие» на «В работе».
- `getDisposalsWithDetailsByFilters(sync: false)` фильтрует строки
  исключительно по `sync == false`, по всем животным и всем причинам/местам
  сразу.
- Если результат непуст — состояние `UnsentDisposalsState.loaded(disposals:
  ...)`, экран показывает карточки, сгруппированные по
  `(causeId, placeId, HH:mm)` и отсортированные по убыванию даты события;
  если результат пуст — состояние `UnsentDisposalsState.empty()`, экран
  показывает `ProgressMessage.notFound(l10n.list_is_empty)`. Оба случая —
  один и тот же `RESULT` (`READ_OK`).
- Кубит реактивно подписан на `watchNotSyncDisposals()` — любое изменение
  таблицы `Disposals` перезагружает уже открытый экран без действия
  пользователя.
- Исключение при чтении данных не даёт отдельного визуального
  состояния — экран в этом случае показывает тот же `list_is_empty`, что и
  при реально пустом списке.

## Связанные тесты

`test/pages/unsent_disposals_cubit_test.dart`, группа `'UC-109 —
UnsentDisposalsCubit.load'` (старый id — будет переименована в `UC-109`
отдельным проходом):

- test `'успех, есть данные -> loaded'` — мокнутый
  `getDisposalsWithDetailsByFilters(sync: false)` возвращает список из одной
  записи (`_disposal()`); после `load()` состояние — `loaded` (проверяется
  через хелпер `_isLoaded`). Покрывает непустой вариант основного потока.
- test `'успех, пусто -> empty'` — мокнутый
  `getDisposalsWithDetailsByFilters(sync: false)` возвращает `[]`; после
  `load()` состояние — `empty` (`_isEmpty`). Покрывает пустой вариант
  основного потока.

Тот же файл, группа `'UnsentDisposalsCubit — реактивная подписка'` (без
UC-номера) — test `'watchNotSyncDisposals эмитит -> кубит перезагружает
список сам'`: после явного `watchController.add(const [])` и
`pumpEventQueue()` состояние становится `loaded` (мок
`getDisposalsWithDetailsByFilters` в этом тесте настроен на непустой
результат) — покрывает часть основного потока этого сценария (шаг 4,
реактивная перезагрузка), но не заякорена явным `UC`-идентификатором;
тест не воспроизводит немедленную эмиссию текущего результата при первой
подписке (поведение реального Drift `.watch()`), так как использует обычный
`StreamController`, не эмитирующий ничего без явного `.add(...)` — см.
«Открытые вопросы».

Тот же файл, группа `'UC-110 — UnsentDisposalsCubit.load'`, test `'ошибка
репозитория -> empty (не error)'` — заякоривает соседнюю ветку исключения
(«Альтернативные потоки» выше): мокнутый
`getDisposalsWithDetailsByFilters(sync: false)` бросает исключение, итоговое
состояние — тот же `empty`, что и у реально пустого списка. Формально другой
код-путь, но не отдельный наблюдаемый `RESULT` — та же `UnsentDisposalsState
.empty()`, что и у READ_OK-пустого варианта этого файла; не входит в периметр
этого файла как отдельный use-case, но фиксируется здесь как открытый вопрос.

## Открытые вопросы и ограничения

- **Нет наблюдаемого `READ_ERROR`.** Исключение при чтении
  (`getDisposalsWithDetailsByFilters`) и реально пустой список сводятся к
  одному и тому же состоянию `UnsentDisposalsState.empty()` —
  `UnsentDisposalsState` не имеет варианта ошибки в принципе. Пользователь не
  может отличить «записей нет» от «не удалось прочитать записи» на этом
  экране. Тестово это заякорено отдельной группой `'UC-110 —
  UnsentDisposalsCubit.load'` в том же файле — под новой нумерацией это,
  видимо, потребует либо отдельного решения (нет отдельного `RESULT`, раз
  нет отдельного состояния), либо явной пометки, что для этого сценария
  `READ_ERROR` неприменим по факту кода.
- **Внешний `try`/`catch` метода `load()` практически недостижим** — тело
  `_reload()` уже перехватывает любое собственное исключение; внешний
  `catch` в `load()` сработает только если исключение возникнет вне вызова
  `_reload()` (не наблюдалось ни в коде, ни в тестах).
- **Возможный двойной вызов `_reload()` при открытии экрана.** Конструктор
  подписывается на `watchNotSyncDisposals()` одновременно с тем, как
  `BlocProvider` вызывает явный `load()`; если Drift-стрим `.watch()`
  эмитит текущий результат сразу при подписке (документированное поведение
  Drift, не проверенное здесь интеграционным тестом против реальной БД —
  юнит-тесты мокают репозиторий целиком через обычный `StreamController`),
  то `_reload()` может быть вызван дважды подряд при обычном открытии
  экрана. Не имеет наблюдаемого эффекта на итоговые данные (оба вызова
  читают одну и ту же таблицу), но не проверено на предмет мерцания UI
  (loading → loaded → loading → loaded) при медленном запросе.
- **Список не имеет собственного порядка на уровне кубита/DAO** —
  `getAllDisposalsWithDetailsByFilters` не задаёт `orderBy`; порядок,
  который видит пользователь, целиком определяется группировкой и
  сортировкой внутри `UnsentDisposalsPopulated._groupByEvent`, а не
  состоянием `UnsentDisposalsState.loaded`. Смена реализации виджета без
  учёта этого может незаметно изменить видимый порядок карточек.
- **Нет теста уровня виджета/страницы.** Весь существующий тест — только на
  уровне кубита с замоканным `DisposalRepository`; нет теста, который
  рендерит `UnsentDisposalsPage`/`UnsentDisposalsPopulated` целиком и
  проверяет фактическую группировку/сортировку карточек или содержимое
  `ProgressMessage.notFound` при пустом состоянии.
