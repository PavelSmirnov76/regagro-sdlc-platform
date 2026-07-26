# UC-101 — Пользователь удаляет группу неотправленных выбытий с хаба «В работе», удаление успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует успешный (`DELETE_OK`) исход события
[EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)
(`disposal.deleted_unsent`) на экране хаба неотправленных выбытий
(`UnsentDisposalsPage`): пользователь безусловно («жёстко») удаляет из
локальной таблицы `Disposals` целую группу ещё не отправленных записей
одним нажатием — `UnsentDisposalsCubit.deleteGroup`.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `UnsentDisposalsPage`, ни
`UnsentDisposalsCubit` не проверяют статус авторизации. Единственное
предусловие для показа самого экрана — переход с плитки «Выбытие» экрана «В
работе»; единственное предусловие для показа иконки удаления конкретной
группы — на устройстве есть хотя бы одна ещё не синхронизированная
(`sync == false`) запись `Disposal`, попавшая в эту группу.

## CURRENT

### Основной поток

1. Пользователь попадает на `UnsentDisposalsPage` с плитки «Выбытие» экрана
   «В работе» (`onTap: () => context.pushNamed2(Routes.unsentDisposals)`,
   `lib/pages/in_work/in_work_page.dart`). Маршрут зарегистрирован в
   `lib/pages/routes.dart` (`Routes.unsentDisposals` → `UnsentDisposalsPage`,
   без аргументов конструктора).
2. `UnsentDisposalsPage.build` создаёт `BlocProvider(create: (context) =>
   UnsentDisposalsCubit()..load())`. Конструктор `UnsentDisposalsCubit`
   одновременно подписывается на `_disposalRepository
   .watchNotSyncDisposals()` (`DisposalRepository.watchNotSyncDisposals` →
   `DisposalsDao.watchAllNotSync`, стрим строк `Disposals` с `sync ==
   false`) — на **любую** эмиссию этого стрима кубит вызывает `_reload()`,
   независимо от содержимого эмиссии.
3. И `load()`, и `_reload()` реально показывают данные через отдельный
   запрос `_disposalRepository.getDisposalsWithDetailsByFilters(sync:
   false)` (→ `DisposalsDao.getAllDisposalsWithDetailsByFilters`) — джойн с
   местом выбытия и причиной, тот же фильтр `sync == false`. Результат
   эмитится как `UnsentDisposalsState.loaded(disposals: ...)`, либо
   `.empty()`, если список пуст; при исключении внутри `_reload()` (вызван
   из `load()`) `load()`'s внешний `catch` эмитит `.empty()` — не отдельное
   состояние ошибки.
4. `UnsentDisposalsView.build` (`state.when(loaded: ...)`) передаёт список в
   `UnsentDisposalsPopulated`. `_groupByEvent()` группирует записи по ключу
   `'${d.disposal.causeId}_${d.disposal.placeId}_$timeKey'`, где
   `timeKey = DateFormat('HHmm').format(date)`, а `date = d.disposal.date ??
   d.disposal.createdAt ?? DateTime.now()` — одна карточка
   (`_DisposalEventCard`) на группу, с количеством животных
   (`event.count`), названием причины и места из джойна.
5. Пользователь нажимает иконку удаления карточки (`Icons.delete_outline`,
   `IconButton.onPressed` в `_DisposalEventCard.build`) — без диалога
   подтверждения, немедленно вызывается `onTapDelete()` →
   `onTapDelete(event.disposals)` (весь список `DisposalWithDetails` этой
   группы) → `UnsentDisposalsView`'s `onTapDelete: context.read
   <UnsentDisposalsCubit>().deleteGroup`.
6. `UnsentDisposalsCubit.deleteGroup(disposals)`: единый `try`/`catch`
   вокруг `for`-цикла по списку; для каждого элемента — `await
   _disposalRepository.delete(d.disposal)`, последовательно, в порядке
   списка.
7. `DisposalRepository` не переопределяет `delete` — вызов уходит прямо в
   `BaseRepository<DisposalsDao, Disposal, $DisposalsTable>.delete(item)` →
   `dao.del(item)` → `BaseDao.del` = `deleteCurrent().delete(item)`. Так как
   `Disposals.id` объявлен `integer().nullable().autoIncrement()()`
   (первичный ключ), Drift сопоставляет строку по `id` — физическое
   удаление ровно одной строки `Disposals` на вызов, без каких-либо
   побочных эффектов на другие таблицы: в отличие от аналогичного удаления
   неотправленного перемещения (см.
   [UC-56](UC-56-ACTOR-5-EVT-28-ENT-13-DELETE_OK-IN-ANIMAL.md)),
   `DisposalRepository` не содержит отката `Animal.placeId` — только сама
   строка `Disposal`.
8. В этом (happy path) сценарии каждый вызов `repository.delete` в шаге 6
   завершается без исключения — цикл проходит по всем записям группы, все
   строки группы физически удаляются.
9. После того как все строки группы удалены, стрим `watchNotSyncDisposals()`
   (подписка из шага 2) реагирует на изменение таблицы `Disposals` и сам
   вызывает `_reload()` — `deleteGroup` не вызывает `load()`/`_reload()`
   напрямую и не эмитит состояние сам. Экран обновляется реактивно:
   удалённая группа больше не попадает в новый список (сузившийся по
   фильтру `sync == false`); если это была последняя оставшаяся группа —
   состояние переходит в `UnsentDisposalsState.empty()`.

### Альтернативные потоки

- **Исключение внутри цикла `deleteGroup`** (например `repository.delete`
  бросает на одной из записей группы) — единый `try`/`catch` кубита ловит
  его целиком, логирует через `Talker` (`getIt<Talker>().error('deleteGroup:
  error: $e')`), не пробрасывает; записи группы **до** упавшего вызова уже
  физически удалены, записи **после** него в этом проходе не обрабатываются
  вовсе — частичный, неатомарный результат по группе. Отдельный сценарий,
  `RESULT = DELETE_ERROR`, не описан этим файлом (покрыт группой `'UC-102 —
  UnsentDisposalsCubit.deleteGroup'` в тесте, см. «Связанные тесты»).
- **Ошибка внутри `_reload()`, вызванной реактивной подпиской после
  удаления** — `_reload()`'s собственный `try`/`catch` эмитит `.empty()`
  вместо падения; список на экране покажет «пусто» вместо укоротившегося
  списка, но сами строки в БД уже удалены безусловно шагом 6–8.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сущность
  сегмента `ENT` в id: каждая запись группы физически удаляется из таблицы
  `Disposals` (не мягкое удаление — у `Disposal` вообще нет концепции
  «помечено на удаление», единственный флаг состояния `sync` используется
  только для «отправлено/не отправлено»).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  только «вбок», через джойн внутри `getDisposalsWithDetailsByFilters` (для
  отображения данных животного при построении `DisposalWithDetails.animal`
  на карточке — хотя сама `UnsentDisposalsPopulated`/`_DisposalEventCard` из
  прочитанных виджетов имя животного не отображает, только причину, место,
  дату и количество), но **не изменяется** этим сценарием никак — ни
  `placeId`, ни любое другое поле `Animal` не трогается ни `deleteGroup`, ни
  `DisposalRepository.delete`.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) и [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) —
  читаются только для отображения на карточке (`reason`/`place` из джойна
  `getDisposalsWithDetailsByFilters`), не изменяются.

### Бизнес-правила

- Группировка карточек хаба — по `(causeId, placeId, HH:mm)`, не по точному
  времени (секунды/миллисекунды) и не по явному общему идентификатору
  «события выбытия» — такого поля у `Disposal` нет, ключ вычисляется на
  лету в `UnsentDisposalsPopulated._groupByEvent`.
- Удаление всей карточки — единственное удаление, доступное на этом экране;
  единичное удаление одной записи группы отсюда недостижимо (нет
  соответствующей иконки/жеста на уровне отдельной записи — карточка
  рендерит только групповую сводку).
- Тап на иконку удаления не показывает диалог подтверждения — эффект
  наступает немедленно по нажатию, без промежуточного шага (тот же паттерн,
  что у `UnsentMovementsPage`, и в отличие от `UnsentVaccinationPage`, где
  есть подтверждающий `AlertDialog`).
- Список, отображаемый на экране, — реактивная проекция таблицы `Disposals`
  по фильтру `sync == false`; сам `deleteGroup` не обновляет UI-состояние
  напрямую, полагаясь целиком на подписку `watchNotSyncDisposals()` в
  конструкторе кубита.
- Удаление здесь не имеет побочного эффекта на `Animal` — в отличие от
  аналогичного сценария для Movement (см.
  [UC-56](UC-56-ACTOR-5-EVT-28-ENT-13-DELETE_OK-IN-ANIMAL.md)), потому что
  Disposal не переносит животное между местами локально (см. инвариант 6
  `.claude/rules/domain-model.md` и [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом на успешную ветку (см.
«Связанные тесты»); отсутствие диалога подтверждения и отсутствие способа
удалить одну запись группы отдельно — не блокеры, а факты текущего UI,
зафиксированные выше.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | плитка «Выбытие» (`onTap: () => context.pushNamed2(Routes.unsentDisposals)`) | CURRENT | точка входа — переход с экрана «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentDisposals` (регистрация маршрута) | CURRENT | маршрут → `UnsentDisposalsPage` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart` | `UnsentDisposalsPage.build` | CURRENT | создаёт `UnsentDisposalsCubit()..load()` |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit` (конструктор, `_watchSubscription`) | CURRENT | реактивная подписка на `watchNotSyncDisposals()`, вызывает `_reload()` на любую эмиссию |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.load`, `UnsentDisposalsCubit._reload` | CURRENT | загрузка/перезагрузка списка через `getDisposalsWithDetailsByFilters(sync: false)` |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.deleteGroup` | CURRENT | эффект [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md) — цикл `repository.delete` по каждой записи группы, единый `try`/`catch`, лог через `Talker` |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart` | `UnsentDisposalsState` (`initial`/`loading`/`loaded`/`empty`) | CURRENT | freezed-состояние кубита — нет отдельного варианта ошибки, `load()`/`_reload()` при исключении сводят к `empty()` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart` | `UnsentDisposalsView.build` | CURRENT | `BlocBuilder`, подключает `onTapDelete: context.read<UnsentDisposalsCubit>().deleteGroup` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart` | `UnsentDisposalsPopulated._groupByEvent`, `_DisposalEventCard.build` | CURRENT | группировка по `causeId`+`placeId`+`HH:mm`, иконка удаления вызывает `onTapDelete(event.disposals)` без диалога подтверждения |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.watchNotSyncDisposals`, `getDisposalsWithDetailsByFilters` | CURRENT | источник реактивного стрима (шаг 2) и данных для отображения (фильтр `sync == false`); `delete` не переопределён этим классом |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | делегирует в `dao.del(item)` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — физическое удаление строки по совпадению первичного ключа |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals.id` (`integer().nullable().autoIncrement()()`) | CURRENT | первичный ключ, по которому `delete(item)` сопоставляет строку |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.watchAllNotSync`, `getAllDisposalsWithDetailsByFilters` | CURRENT | источник реактивного стрима (шаг 2) и данных для отображения (фильтр `sync == false`) |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_with_details.dart` | `DisposalWithDetails` (`disposal`, `animal`, `place`, `reason`) | CURRENT | модель строки списка/группы — `deleteGroup` работает с `d.disposal` каждого элемента |

## Критерии приёмки

- Тап по иконке удаления карточки группы немедленно (без диалога
  подтверждения) вызывает `UnsentDisposalsCubit.deleteGroup` со всем списком
  `DisposalWithDetails` этой группы.
- `deleteGroup` вызывает `DisposalRepository.delete` ровно один раз на
  каждую запись переданного списка, последовательно, в порядке списка.
- Каждый вызов `delete` физически удаляет ровно одну строку `Disposals` (по
  первичному ключу `id`), без изменения `Animal` или любой другой таблицы.
- После успешного удаления всех записей группы кубит не эмитит состояние
  напрямую из `deleteGroup` — обновление списка приходит только через
  реактивную подписку на `watchNotSyncDisposals()`.
- Если удалённая группа была последней в списке, состояние после реактивной
  перезагрузки — `UnsentDisposalsState.empty()`.

## Связанные тесты

- `test/pages/unsent_disposals_cubit_test.dart`, group `'UC-101 —
  UnsentDisposalsCubit.deleteGroup'` (старая нумерация, переименуется
  отдельным контролируемым проходом — не трогать сейчас), test `'успех ->
  delete вызван для каждого элемента'` — покрывает основной поток на уровне
  кубита: `DisposalRepository.delete` (мокнутый) вызывается дважды для
  группы из двух записей (`_disposal(id: 1)`, `_disposal(id: 2)`), без
  исключения.
- Тот же файл, group `'UC-102 — UnsentDisposalsCubit.deleteGroup'` (тоже
  старая нумерация) — покрывает соседний `RESULT = DELETE_ERROR` (исключение
  внутри цикла, лог через `Talker`, `Future` всё равно завершается
  `completes`), не этот файл.
- Тот же файл, group `'UC-109 — UnsentDisposalsCubit.load'`, `'UC-110 —
  UnsentDisposalsCubit.load'` и `'UnsentDisposalsCubit — реактивная
  подписка'` — покрывают `load()`/`_reload()` и реактивную подписку на
  `watchNotSyncDisposals()`, которыми этот сценарий пользуется на шагах 2–3
  и 9, но не сам `deleteGroup`; в этот use-case не входят.

**TBD — теста нет** на уровне виджета/страницы (`UnsentDisposalsPage`,
`UnsentDisposalsPopulated`, `_DisposalEventCard`): весь существующий тест —
только на уровне кубита с замоканным `DisposalRepository`. Нет теста,
который рендерит `UnsentDisposalsPage` целиком, тапает иконку удаления
конкретной карточки группы и проверяет, что в `deleteGroup` передан именно
список записей этой группы (а не всего экрана), и что группировка по
`(causeId, placeId, HH:mm)` в `_groupByEvent` действительно объединяет
нужные записи в одну карточку.

**TBD — теста нет** на уровне репозитория/DAO против настоящей (in-memory)
БД: во всех существующих тестах `DisposalRepository` замокан целиком — не
проверено ни реальное поведение `BaseDao.del` против таблицы `Disposals`
(сопоставление по `id`), ни то, что удаление одной строки не задевает
`Animals`/другие таблицы при реальном SQL-запросе.

## Открытые вопросы и ограничения

- **Единичное удаление одной записи группы отсюда недостижимо.** Иконка
  удаления карточки всегда передаёт `event.disposals` — весь список записей
  группы — в `deleteGroup`; ни `UnsentDisposalsPopulated`, ни
  `_DisposalEventCard` не предоставляют способа выбрать и удалить одну
  запись группы, не удаляя всю группу целиком (тот же паттерн, что у
  `UnsentMovementsPage`, см.
  [UC-56](UC-56-ACTOR-5-EVT-28-ENT-13-DELETE_OK-IN-ANIMAL.md)).
- **Частичный неатомарный результат группового удаления при отказе одной из
  записей.** `deleteGroup` оборачивает весь `for`-цикл одним `try`/`catch`,
  не per-item и не общей Drift-транзакцией: исключение на записи N оставляет
  записи `0..N-1` уже физически удалёнными, а записи `N..конец` — вообще не
  обработанными в этом проходе. Пользователь видит только то, что карточка
  либо исчезла целиком, либо (при отказе) остаётся видимой с частью записей,
  реально уже удалённых из БД — до следующей реакции
  `watchNotSyncDisposals()`, которая перечитает укоротившийся список. Не
  разбирается глубже в рамках этого (`DELETE_OK`) файла — относится к
  соседнему `RESULT = DELETE_ERROR`.
- **`load()`/`_reload()` не различают «пусто» и «ошибка репозитория».**
  Оба исхода сводятся к одному и тому же состоянию `UnsentDisposalsState
  .empty()` — если `_reload()`, вызванная реактивной подпиской сразу после
  успешного `deleteGroup`, неожиданно бросит исключение (например временный
  сбой БД), пользователь увидит «список пуст», а не признак ошибки, даже
  если на самом деле оставшиеся записи есть, но не удалось их прочитать.
- Нет диалога подтверждения перед удалением группы — расхождение с
  аналогичным экраном для вакцинаций (`UnsentVaccinationPage`, где
  подтверждение есть), не разбирается глубже в рамках этого документирующего
  прохода.
