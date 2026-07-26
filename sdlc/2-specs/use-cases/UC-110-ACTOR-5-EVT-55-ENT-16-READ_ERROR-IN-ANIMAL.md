# UC-110 — Хаб неотправленных выбытий не грузится: `UnsentDisposalsCubit` ловит исключение репозитория, но эмитит «пусто», а не отдельную ошибку

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-55](../events/EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует технический (`READ_ERROR`) исход
[EVT-55](../events/EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md)
(`disposals.viewed_unsent`): пользователь открывает хаб ещё не отправленных
выбытий (`UnsentDisposalsPage`), но чтение из БД
(`DisposalRepository.getDisposalsWithDetailsByFilters(sync: false)`) бросает
исключение. Проверено чтением `unsent_disposals_cubit.dart` целиком:
исключение перехватывается, но кубит **не различает** «список пуст» и
«не удалось прочитать список» — оба исхода сводятся к одному и тому же
`UnsentDisposalsState.empty()`, и экран показывает то же самое сообщение
«Список пуст», что и при реально пустой таблице.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`unsent_disposals_cubit.dart` целиком: `UnsentDisposalsCubit` не объявляет и
не использует `AuthRepository` ни в одном методе, включая `load`/`_reload` —
доступ к экрану не зависит от статуса авторизации.

## CURRENT

### Основной поток

1. Пользователь попадает на `UnsentDisposalsPage` с плитки «Выбытие» экрана
   «В работе» (`onTap: () => context.pushNamed2(Routes.unsentDisposals)`,
   `lib/pages/in_work/in_work_page.dart`) — единственный найденный вход на
   этот маршрут (`grep` по `Routes.unsentDisposals` в `lib/` находит только
   регистрацию маршрута в `lib/pages/routes.dart` и эту одну точку
   навигации).
2. `UnsentDisposalsPage.build` создаёт `BlocProvider(create: (context) =>
   UnsentDisposalsCubit()..load())`. Конструктор `UnsentDisposalsCubit`
   одновременно подписывается на `_disposalRepository
   .watchNotSyncDisposals()` (стрим строк `Disposals` с `sync == false`) —
   любая эмиссия этого стрима тоже вызывает `_reload()`, независимо от того,
   был ли вызван `load()` пользователем (см. «Альтернативные потоки»).
3. `load()` синхронно эмитит `UnsentDisposalsState.loading()` (страница
   показывает `CustomLottieLoader` внутри `BottomSheetPageWrapper`), затем
   внутри собственного `try` вызывает `await _reload()`.
4. **Точка технического сбоя (этот сценарий).** Внутри `_reload()`:
   `await _disposalRepository.getDisposalsWithDetailsByFilters(sync:
   false)` бросает исключение. `DisposalRepository` не переопределяет
   `getDisposalsWithDetailsByFilters` собственной обработкой ошибок — тонкая
   обёртка делегирует прямо в `DisposalsDao
   .getAllDisposalsWithDetailsByFilters` (`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart`),
   которая сначала выполняет join-запрос (`Disposals` ⋈ `Places` ⋈
   `DisposalReasons`, фильтр `sync == false`), затем один дополнительный
   запрос `db.animalsDao.getAllAnimalsWithDetailsByFilters(ids: ...)` для
   подгрузки животных группы — исключение из любой из этих двух точек
   долетает наверх без изменений (`BaseRepository`, промежуточный базовый
   класс `DisposalRepository`, тоже не оборачивает вызов в свой
   `try/catch`).
5. **Исключение перехватывается собственным `catch` метода `_reload()`, а
   не `catch` вызывающего его `load()`.** Дословно:
   ```dart
   Future<void> _reload() async {
     if (isClosed) return;
     try {
       final disposals = await _disposalRepository
           .getDisposalsWithDetailsByFilters(sync: false);
       if (isClosed) return;
       emit(
         disposals.isEmpty
             ? const UnsentDisposalsState.empty()
             : UnsentDisposalsState.loaded(disposals: disposals),
       );
     } catch (e) {
       if (!isClosed) emit(const UnsentDisposalsState.empty());
     }
   }
   ```
   `_reload()`'s `catch` эмитит `UnsentDisposalsState.empty()` (при условии
   `!isClosed`) и **не пробрасывает** исключение дальше (нет `rethrow`) —
   `_reload()` как `Future` завершается нормально, без ошибки.
6. **Следствие: внешний `catch` в `load()` для этого конкретного отказа
   фактически не выполняется.** `load()` выглядит как:
   ```dart
   Future<void> load() async {
     try {
       emit(const UnsentDisposalsState.loading());
       await _reload();
     } catch (e) {
       emit(const UnsentDisposalsState.empty());
     }
   }
   ```
   Так как `await _reload()` не бросает исключение (оно уже поймано и
   поглощено на шаге 5), `load()`'s собственный `catch` в этом сценарии не
   срабатывает — итоговый эффект (`.empty()`) идентичен тому, что уже
   произвёл `_reload()` на шаге 5. Внешний `catch` в `load()` реально
   достижим только для отказов, не связанных с чтением из репозитория
   (например если бы `emit(const UnsentDisposalsState.loading())` бросил
   `StateError` из-за того, что кубит уже закрыт к этому моменту) — не
   предмет этого файла, отдельно не разбирается.
7. `UnsentDisposalsView.build` (`state.when(...)`) реагирует на `empty`
   веткой:
   ```dart
   empty: () => BottomSheetPageWrapper(
     child: Center(
       child: ProgressMessage.notFound(
         message: AppLocalizations.of(context)!.list_is_empty,
       ),
     ),
   ),
   ```
   Пользователь видит переведённое сообщение «Список пуст»
   (`AppLocalizations.list_is_empty`) — то же самое, что и при реально
   пустой (успешно прочитанной) таблице `Disposals`. Никакого признака
   технического сбоя (текста исключения, иконки ошибки, кнопки
   «Повторить») на экране нет.
8. Логирования (`Talker` или аналог) на этом пути нет: ни `catch` в
   `_reload()`, ни `catch` в `load()` не вызывают `getIt<Talker>()` —
   единственные два места этого файла, которые логируют через `Talker`
   (`deleteGroup`), для read-пути не задействованы.

### Альтернативные потоки

- **Тот же самый сбой, вызванный реактивной подпиской, а не явным
  `load()`.** `_watchSubscription` (заведена в конструкторе) вызывает
  `_reload()` напрямую на любую эмиссию `watchNotSyncDisposals()` — не
  только при первом открытии экрана. Если в момент такой реактивной
  перезагрузки (например, сразу после `deleteGroup`, см.
  [UC-101](UC-101-ACTOR-5-EVT-51-ENT-16-DELETE_OK-IN-ANIMAL.md)) тот же
  запрос бросит исключение, пользователь увидит «Список пуст» вместо
  актуального (возможно непустого) списка — тем же самым `catch`
  `_reload()`, что и в основном потоке; `load()` в этом случае вообще не
  вызывается.
- **Гонка с закрытием кубита.** И в начале `_reload()` (`if (isClosed)
  return;`), и внутри его `catch` (`if (!isClosed) emit(...)`) — двойная
  защита от `emit` после `close()`. Если кубит закрыт между стартом
  запроса к репозиторию и моментом, когда исключение долетело до `catch`,
  `emit` не вызывается вовсе — то есть при закрытии экрана в момент сбоя
  пользователь просто не увидит никакого состояния (последний показанный —
  `loading`), но это не отдельный `RESULT`, так как страница в этот момент
  уже не отображается.
- **Ошибка из `db.animalsDao.getAllAnimalsWithDetailsByFilters`, а не из
  самого join-запроса `Disposals`.** `DisposalsDao
  .getAllDisposalsWithDetailsByFilters` выполняет два независимых по
  происхождению Drift-вызова подряд (сам join, затем отдельный запрос
  животных по `ids` из результата join) — исключение из второго вызова
  неотличимо для `_reload()`'s `catch` от исключения из первого; оба
  сводятся к одному и тому же `.empty()`.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — целевая
  сущность чтения; при сбое ни одна строка (даже если join успел вернуть
  часть результата до отказа второго запроса) не попадает в состояние
  экрана — `UnsentDisposalsState.empty()` не несёт частичного результата,
  так как `disposals` вообще не присваивается локальной переменной до
  `emit`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  «вбок» через `db.animalsDao.getAllAnimalsWithDetailsByFilters` внутри
  того же DAO-метода (для заполнения `DisposalWithDetails.animal`) — один
  из двух источников исключения в этом сценарии; сама сущность `Animal`
  этим сценарием не изменяется никак.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) и [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) —
  участвуют в том же join-запросе (левые джойны по `causeId`/`placeId`),
  читаются, но не изменяются; их отсутствие/несовпадение не является
  причиной исключения (`leftOuterJoin` не бросает при отсутствии
  совпадения — соответствующее поле результата просто `null`).

### Бизнес-правила

- Технический сбой чтения (исключение внутри
  `getDisposalsWithDetailsByFilters`, на любом из двух вложенных
  Drift-запросов) классифицируется как `READ_ERROR`, но **код этого не
  отражает** — нет отдельного варианта `UnsentDisposalsState`, который
  различал бы «пусто» от «ошибка»: freezed-состояние объявляет только
  `initial`/`loading`/`loaded`/`empty` (`unsent_disposals_state.dart`), без
  варианта `error`.
- Единственная реально исполняемая перехватывающая точка для этого отказа —
  `catch` внутри `_reload()`, не `catch` в `load()` — несмотря на то, что
  оба формально существуют в файле и оба на вид эмитят одно и то же
  (`.empty()`); внешний `catch` в `load()` не пробрасывается до
  исключения-источника, так как `_reload()` сама поглощает исключение
  без `rethrow`.
- Ошибка нигде не логируется (`Talker` не вызывается ни в `load()`, ни в
  `_reload()`) — в отличие от `deleteGroup` этого же кубита, где `catch`
  вызывает `getIt<Talker>().error('deleteGroup: error: $e')`. Единственный
  read-путь этого файла оставляет разработчика вообще без следа отказа.
- **Важное уточнение к премise задачи.** Точно такой же по форме код
  (freezed-состояние без варианта `error`, `catch` внутри `_reload()`,
  сведение к `.empty()`, отсутствие логирования) обнаружен и в
  `UnsentMovementsCubit` (MOVE, [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md),
  `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart`)
  — это два независимых, но буквально идентичных по коду места. Проверено
  чтением `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart`
  целиком: `UnsentVaccinationCubit.load` (VAC,
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) **не** повторяет
  этот паттерн — там `catch` эмитит отдельный, различимый
  `UnsentVaccinationError(message: e.toString(), ...)` (см.
  [UC-80](UC-80-ACTOR-5-EVT-40-ENT-14-READ_ERROR-IN-ANIMAL.md)), а не
  `.empty()`. Формулировка задачи, поставившей этот файл («та же находка,
  что у VAC»), в этой части не подтвердилась при независимой проверке кода —
  точный аналог найден у MOVE (`UnsentMovementsCubit`), не у VAC.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба перехватывающих `catch`-блока (`load()`,
`_reload()`) прослежены чтением
`lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart`,
`lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart`,
`lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart`,
`lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_view.dart`,
`lib/repositories/disposal/disposal_repository.dart`,
`lib/repositories/base_repository.dart` и
`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart`
целиком — не восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | плитка «Выбытие» (`onTap: () => context.pushNamed2(Routes.unsentDisposals)`) | CURRENT | единственный найденный вход на `Routes.unsentDisposals` |
| `lib/pages/routes.dart` | `Routes.unsentDisposals` | CURRENT | маршрут → `UnsentDisposalsPage` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart` | `UnsentDisposalsPage.build` | CURRENT | создаёт `UnsentDisposalsCubit()..load()` |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.load` | CURRENT | внешний `try`/`catch`, эмитит `loading()`; собственный `catch` фактически не срабатывает при отказе чтения из репозитория (см. основной поток, шаг 6) |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit._reload` | CURRENT | реальная перехватывающая точка этого сценария — `catch` без `rethrow`, эмитит `.empty()`, без логирования |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit` (конструктор, `_watchSubscription`) | CURRENT | реактивная подписка на `watchNotSyncDisposals()`, вызывает `_reload()` независимо от `load()` (см. «Альтернативные потоки») |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart` | `UnsentDisposalsState` (`initial`/`loading`/`loaded`/`empty`) | CURRENT | freezed-состояние — нет варианта `error`, любой отказ чтения неотличим от «список пуст» |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_view.dart` | `UnsentDisposalsView.build` (`state.when`, ветка `empty`) | CURRENT | рендерит `ProgressMessage.notFound(message: list_is_empty)` — одинаково для реально пустого списка и для технического сбоя |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.notFound` | CURRENT | статический (не связанный с текстом исключения) UI для ветки `empty` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.getDisposalsWithDetailsByFilters` | CURRENT | тонкая обёртка (`=> dao.getAllDisposalsWithDetailsByFilters(...)`) — не перехватывает исключение |
| `lib/repositories/base_repository.dart` | `BaseRepository` (базовый класс `DisposalRepository`) | CURRENT | не добавляет собственную обработку ошибок вокруг `dao`-вызовов |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.getAllDisposalsWithDetailsByFilters` | CURRENT | join-запрос (`Disposals` ⋈ `Places` ⋈ `DisposalReasons`, фильтр `sync == false`) плюс отдельный вложенный вызов `db.animalsDao.getAllAnimalsWithDetailsByFilters` — обе точки могут быть источником исключения в этом сценарии |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | альтернативный источник исключения, вызывается внутри `getAllDisposalsWithDetailsByFilters` для подгрузки животных группы |
| `lib/pages/animal_movement/cubit/unsent_movement/unsent_movements_cubit.dart` | `UnsentMovementsCubit.load`, `UnsentMovementsCubit._reload` | CURRENT | буквально идентичный по коду аналог этого сценария в MOVE — не предмет этого файла, приведён для сверки премисы |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | контрастный пример — тот же формально сбой (исключение чтения) даёт **отличимый** результат (`UnsentVaccinationError`), не `.empty()`; не предмет этого файла |

## Критерии приёмки

- При исключении из `_disposalRepository
  .getDisposalsWithDetailsByFilters(sync: false)` внутри `_reload()` (вызван
  либо из `load()`, либо реактивной подпиской на `watchNotSyncDisposals()`)
  кубит эмитит `UnsentDisposalsState.empty()` — без падения приложения и без
  необработанного исключения на уровне `Cubit`.
- Эмитированное состояние в этом случае неотличимо от состояния, которое
  эмитируется при успешном чтении пустого списка — `UnsentDisposalsState`
  не несёт информации о том, что конкретно произошло: «данных нет» или
  «не удалось прочитать данные».
- `UnsentDisposalsView` при `UnsentDisposalsState.empty()` рендерит
  `ProgressMessage.notFound(message: AppLocalizations.of(context)!
  .list_is_empty)` — статический текст «Список пуст», без текста
  исключения и без кнопки «Повторить».
- Исключение не логируется через `Talker` ни в `load()`, ни в `_reload()`.
- `load()`'s собственный внешний `catch` не участвует в обработке этого
  конкретного отказа — исключение из `_disposalRepository
  .getDisposalsWithDetailsByFilters` перехватывается и поглощается внутри
  `_reload()`, до того как оно могло бы всплыть в `load()`.

## Связанные тесты

`test/pages/unsent_disposals_cubit_test.dart`, group `'UC-110 —
UnsentDisposalsCubit.load'` (старая нумерация, переименуется отдельным
контролируемым проходом — не трогать сейчас), test `'ошибка репозитория ->
empty (не error)'` — мокает
`disposalRepository.getDisposalsWithDetailsByFilters(sync: false)` на
`thenThrow(Exception('db error'))`, вызывает `cubit.load()` и проверяет
`_isEmpty(cubit.state)` через локальный хелпер `_isEmpty` (`state.when(...,
empty: () => true, ...)`) — покрывает наблюдаемый исход основного потока
(шаги 3–6), но не проверяет напрямую, что срабатывает именно `catch`
`_reload()`, а не `catch` `load()` (оба неотличимы по итоговому состоянию,
см. «Открытые вопросы»).

**TBD — теста нет** на реактивный путь: ни один существующий тест этого
файла не проверяет, что исключение внутри `_reload()`, вызванной эмиссией
`watchNotSyncDisposals()` (а не прямым вызовом `load()`), тоже приводит к
`.empty()` — существующий тест реактивной подписки (group
`'UnsentDisposalsCubit — реактивная подписка'`) проверяет только успешный
путь (`getDisposalsWithDetailsByFilters` замокан на успешный ответ), не
исключение на этом пути.

**TBD — теста нет** на содержимое сообщения пользователю
(`ProgressMessage.notFound` / `list_is_empty`) на уровне виджета — весь
существующий тест только на уровне кубита с замоканным
`DisposalRepository`, без рендера `UnsentDisposalsView`.

## Открытые вопросы и ограничения

- **Нет способа отличить «пусто» от «ошибка» ни в коде, ни на экране.**
  `UnsentDisposalsState` не предоставляет варианта `error`; пользователь,
  столкнувшийся с реальным сбоем БД (например повреждённый файл БД,
  диск переполнен), увидит то же «Список пуст», что и при отсутствии
  неотправленных выбытий — нет побуждения повторить попытку или обратиться
  в поддержку, потому что ничто на экране не сигнализирует о сбое.
- **Двойной, но фактически единственный работающий `catch`.** Код выглядит
  так, будто в `load()` есть защита на случай отказа `_reload()`, но
  поскольку `_reload()` сама перехватывает и не пробрасывает исключение,
  этот внешний `catch` в `load()` мёртв для данного класса отказов — не
  проверялось, было ли это осознанным решением (defensive redundancy) или
  результатом того, что `_reload()` изначально не имела своего `catch` и он
  был добавлен позже без удаления внешнего.
- **Нет логирования на всём read-пути.** Ни `load()`, ни `_reload()` не
  вызывают `Talker` при перехваченном исключении — в отличие от
  `deleteGroup` этого же файла. Разработчик не получит никакого следа
  технического сбоя чтения списка, кроме того, что успеет заметить/сообщить
  пользователь, увидевший необъяснимо пустой список.
- **Нет кнопки «Повторить».** `UnsentDisposalsView`'s ветка `empty` не
  предлагает retry — единственный способ заново вызвать `load()` — закрыть
  экран и открыть его заново с «В работе», что пересоздаёт
  `UnsentDisposalsCubit` целиком (тот же вывод, что и для `deleteGroup`,
  см. [UC-101](UC-101-ACTOR-5-EVT-51-ENT-16-DELETE_OK-IN-ANIMAL.md)).
- **Премиса задачи про параллель с VAC уточнена, не подтверждена буквально**
  (см. «Бизнес-правила»): точный аналог по коду — `UnsentMovementsCubit`
  (MOVE), не `UnsentVaccinationCubit.load` (VAC), у которого есть отдельное,
  различимое состояние ошибки. Не разбирается глубже в рамках этого файла,
  который специфицирует именно Disposal/ENT-16 — параллель с MOVE указана
  как факт для будущей сверки при специфицировании соответствующего
  сценария MOVE (`EVT` для «movements viewed unsent», на момент написания
  этого файла отдельным use-case ещё не оформлен).
