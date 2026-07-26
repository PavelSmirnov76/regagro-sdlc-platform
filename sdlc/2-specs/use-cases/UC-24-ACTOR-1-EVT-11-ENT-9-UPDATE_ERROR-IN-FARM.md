# UC-24 — Редактирование фермы через `FarmsAndPlacesBloc` отказывает: ошибка ловится и эмитится в `FarmsPageError`, но сам код недостижим из текущего UI (ERROR)

## Назначение

Документирует ERROR-исход события [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)
(`farm.edited`) так, как он реализован в `FarmsAndPlacesBloc._onEditFarm`:
исключение из `FarmRepository.update` перехватывается, и блок эмитит
`FarmsPageError` с текстом на русском. Отдельно от самого обработчика этот
use-case фиксирует факт, обнаруженный при чтении кода: ни один экран
приложения сейчас не диспетчит `FarmsPageEventEditFarm` и не слушает
состояния `FarmsAndPlacesBloc` — реальное редактирование фермы пользователем
идёт по другому, независимому коду (`FarmCreateCubit.saveFarm`), с другой
обработкой ошибок. Сценарий, документируемый здесь, сегодня достижим только
прямым вызовом `bloc.add(FarmsPageEventEditFarm(...))` — то есть из тестов
уровня блока, не из реального пользовательского действия.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь;
имя актора наследуется от id события [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)
в имени файла (`ACTOR-1` зафиксирован там как инициатор `farm.edited`). Как
описано в «Назначении» и подробно в «Основном потоке»/«Открытых вопросах»,
в текущем коде нет UI-пути, которым этот актор мог бы фактически вызвать
именно этот обработчик — раздел документирует поведение кода при условии,
что событие всё же было бы отправлено.

## CURRENT

### Основной поток

1. `FarmsAndPlacesBloc` создаётся один раз на всё приложение в
   `MultiBlocProvider` в `lib/main.dart`:
   `BlocProvider<FarmsAndPlacesBloc>(create: (context) =>
   FarmsAndPlacesBloc(getIt.get(), getIt.get(), getIt()))` — три зависимости
   (`FarmRepository`, `PlaceRepository`, `AnimalsRepository`) берутся из
   `getIt` (сама регистрация `FarmsAndPlacesBloc` в `injection_container.dart`
   закомментирована — блок создаётся только здесь, напрямую). Блок живёт всё
   время работы приложения и доступен из любого потомка через
   `context.read<FarmsAndPlacesBloc>()`.
2. В конструкторе `FarmsAndPlacesBloc` регистрирует
   `on<FarmsPageEventEditFarm>(_onEditFarm)`.
3. Что-то вызывает `bloc.add(FarmsPageEventEditFarm(updatedFarm))` — событие
   несёт единственное поле `updatedFarm` (`Farm`).
4. `_onEditFarm` строит `newFarm = event.updatedFarm.copyWith(needUpdate:
   true)` — `needUpdate` всегда взводится в `true` безусловно, независимо от
   того, синхронизирована ли ферма (`remoteId != null`) уже с сервером или
   нет.
5. `await _farmsRepository.update(newFarm)` — `FarmRepository extends
   BaseRepository<FarmsDao, Farm, $FarmsTable>`, `update` — унаследованный
   метод `Future<bool> update(Insertable<D> item) => dao.upd(item)`
   (`lib/repositories/base_repository.dart`), который вызывает
   `BaseDao.upd(item) => updateCurrent().replace(item)`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — обычный
   Drift `replace`.
6. Вызов бросает исключение (ошибка Drift/SQLite, например нарушение
   ограничения, либо любое другое исключение, всплывающее из DAO).
7. `_onEditFarm` ловит его в `catch (e)` и эмитит
   `FarmsPageError('Ошибка редактирования фермы: ${e.toString()}')` — текст
   ошибки жёстко закодирован на русском (в коде рядом стоит комментарий `//
   todo tranlsate`), не идёт через `AppLocalizations`.
8. В отличие от успешного пути (шаг 4 в «Альтернативных потоках»), в
   `catch`-ветке нет `add(FarmsPageEventLoadFarms())` — список ферм не
   перезагружается; предыдущее состояние `FarmsPageLoadedWithAnimals` (если
   оно было) просто перекрывается новым `FarmsPageError` в потоке состояний
   блока.
9. Дальнейшего повтора/backoff нет — на этом обработка события
   заканчивается.
10. **Ни один виджет в `lib/` не подписан на состояния `FarmsAndPlacesBloc`.**
    Проверено чтением: во всём `lib/` нет ни одного `BlocBuilder<
    FarmsAndPlacesBloc, ...>`, `BlocConsumer<FarmsAndPlacesBloc, ...>` или
    `BlocListener<FarmsAndPlacesBloc, ...>` — единственное место, где на блок
    вообще ссылаются за пределами его собственных файлов,
    `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`, и
    там он используется только как приёмник команд (`context.read<
    FarmsAndPlacesBloc>().add(...)` для событий по местам — `FarmsPageEventAddPlace`/
    `FarmsPageEventEditPlace`/`FarmsPageEventDeletePlace`), без чтения
    состояния. Из этого следует: `FarmsPageError`, эмитированный на шаге 7,
    сегодня не показывается ни одному реальному пользователю ни при каких
    обстоятельствах — эмиссия существует только на уровне потока состояний
    блока.

### Альтернативные потоки

- **OK-исход того же обработчика — не входит в этот сценарий.** Если
  `_farmsRepository.update(newFarm)` завершается успешно, `_onEditFarm`
  вызывает `add(FarmsPageEventLoadFarms())`, что асинхронно запускает
  `_onLoadFarms` и в итоге эмитит `FarmsPageLoadedWithAnimals` — это
  соседний, не документируемый здесь исход того же [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md).
- **Реальный, UI-достижимый путь редактирования фермы — это другой код, не
  описываемый этим use-case.** Пункт меню «Редактировать ферму»
  (`l10n.edit_farm` в `FarmMoreMenuButton`,
  `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`)
  переходит на `Routes.createFarm` с `FarmCreatePageArguments(farm:
  farm.farm)`, открывая `FarmCreatePage`, которая создаёт `FarmCreateCubit()
  ..loadData(farm)`. Сохранение идёт через `FarmCreateCubit.saveFarm()`
  (`lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart`):
  при `state.farm.id != null` (правка существующей фермы) метод тоже строит
  `newFarm = state.farm.copyWith(needUpdate: true)` и тоже вызывает
  `await _farmRepository.update(newFarm)` — тот же репозиторий и тот же
  вызов DAO, что и в «Основном потоке», — но делает это внутри голого `try {
  ... } finally { emit(state.copyWith(isSubmitting: false)); }`, **без
  единого `catch`**. Если `update` здесь бросает исключение, оно не
  перехватывается нигде в `FarmCreateCubit` — это необработанная ошибка
  `Future`, а не `FarmsPageError`. `FarmsAndPlacesBloc._onEditFarm` в этом
  реальном пути вообще не участвует.
- Поиск по всему `lib/` за пределами `farms_page_bloc.dart`/
  `farms_page_event.dart` не находит ни одного `.add(FarmsPageEventEditFarm(
  ...))` — единственные три вхождения идентификатора `FarmsPageEventEditFarm`
  во всём `lib/` — это определение класса события, его регистрация
  (`on<FarmsPageEventEditFarm>(_onEditFarm)`) и сам обработчик.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — сущность, чьё состояние
  пытается поменять сценарий (`needUpdate`); это же ENT-сегмент имени файла.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — не читается и не
  пишется в этом сценарии; упомянута лишь потому, что `FarmsAndPlacesBloc`
  хранит `PlaceRepository` как общую зависимость (используется другими
  обработчиками того же блока, не `_onEditFarm`).

### Бизнес-правила

- `needUpdate` взводится в `true` безусловно при попытке правки, независимо
  от исхода `update` и от того, была ли ферма уже синхронизирована.
- Текст ошибки не локализован — жёстко закодированная русская строка
  `'Ошибка редактирования фермы: ${e.toString()}'`, включающая сырой
  `e.toString()` без какой-либо фильтрации.
- Обработчик не делает retry и не откатывает `needUpdate`/локальное
  состояние — при ошибке `update` просто не происходит, ферма остаётся в
  том виде, в каком была до попытки правки.
- Как зафиксировано в «Основном потоке» (шаг 10), выход `FarmsPageError` из
  этого обработчика ни на что не влияет за пределами потока состояний
  блока — ни снэкбар, ни иной UI-эффект в текущем коде не завязаны на это
  состояние.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик, включая факт его недостижимости из текущего UI,
полностью прослеживается в существующем коде и покрыт тестом на уровне
блока.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/main.dart` | `MultiBlocProvider` → `BlocProvider<FarmsAndPlacesBloc>` | CURRENT | создаёт единственный экземпляр блока на всё приложение из трёх репозиториев `getIt` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditFarm` | CURRENT | ловит исключение `_farmsRepository.update`, эмитит `FarmsPageError`, без reload списка |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventEditFarm` | CURRENT | событие, несущее `updatedFarm`; нигде в `lib/` не диспетчится за пределами своего файла определения/регистрации |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageError` | CURRENT | состояние-ошибка (`message`); ни один виджет в `lib/` на него не подписан |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageLoadedWithAnimals` | CURRENT | состояние, которое эта ошибка перекрывает в потоке (соседний OK-путь) |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository` (`extends BaseRepository<FarmsDao, Farm, $FarmsTable>`) | CURRENT | предоставляет `update`, используемый и этим обработчиком, и `FarmCreateCubit.saveFarm` |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` — точка, откуда всплывает перехватываемое исключение |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — реальный Drift-вызов, способный бросить исключение |
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` (действие `l10n.edit_farm`) | CURRENT | фактическая точка входа «Редактировать ферму» в UI — не диспетчит `FarmsPageEventEditFarm` |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage` | CURRENT | экран, реально используемый для правки фермы (получает существующий `Farm` через `FarmCreatePageArguments`) |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.saveFarm` | CURRENT | реальный код, исполняемый при правке фермы пользователем; голый `try/finally` без `catch` — иная обработка ошибок, чем в этом use-case |

## Критерии приёмки

- При отправке `FarmsPageEventEditFarm(updatedFarm)` в `FarmsAndPlacesBloc`,
  если `FarmRepository.update` (через `BaseDao.upd`) бросает исключение,
  блок эмитит ровно одно состояние `FarmsPageError`, чьё `message` равно
  `'Ошибка редактирования фермы: ' + e.toString()`; сам вызов `add(...)` не
  приводит к необработанному исключению снаружи блока (`completes`, а не
  `throwsA(...)`).
- В этой ветке `FarmsPageEventLoadFarms` не добавляется — в отличие от
  успешного пути, список ферм/животных не перезагружается после ошибки
  правки.
- `event.updatedFarm.copyWith(needUpdate: true)` — именно этот объект
  передаётся в `update`, даже если сам вызов затем падает.
- Факт, что сегодня ни один экран не диспетчит `FarmsPageEventEditFarm` и ни
  один виджет не читает состояния `FarmsAndPlacesBloc` — часть текущего,
  подтверждённого чтением кода поведения; это не критерий для исправления в
  рамках этого документирующего прохода (TARGET == CURRENT).

## Связанные тесты

- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-4 —
  FarmsAndPlacesBloc._onEditFarm ERROR'` (будет переименовано, не трогать
  сейчас), test `'update бросает -> FarmsPageError("Ошибка редактирования
  фермы: ...")'` — прямое покрытие «Основного потока»: мок
  `farmRepository.update` бросает `Exception('db error')`, блок собирается
  через `buildLoadedBloc()` (уже в состоянии `FarmsPageLoadedWithAnimals`),
  затем добавляется `FarmsPageEventEditFarm`, и тест ждёт `FarmsPageError` с
  сообщением, содержащим `'Ошибка редактирования фермы'`.
- **TBD — теста нет** на реальный UI-путь («Альтернативные потоки»,
  `FarmCreateCubit.saveFarm` при `update`, бросающем исключение для
  `farm.id != null`). `test/pages/farm_create_cubit_test.dart`, group
  `'FarmCreateCubit.saveFarm'`, содержит только успешные и
  isSubmitting-сценарии — ветки с исключением из `farmRepository.update` там
  нет.

## Открытые вопросы и ограничения

- **Зафиксированное расхождение с описанием триггера в [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)
  — не исправляется в рамках этого прохода.** Файл события описывает триггер
  как «пользователь открывает уже существующую ферму на редактирование
  (название/адрес) и сохраняет; `FarmsAndPlacesBloc.on<FarmsPageEventEditFarm>`»
  — однако при чтении кода реальная UI-точка входа «Редактировать ферму»
  (`FarmMoreMenuButton` → `FarmCreatePage` → `FarmCreateCubit.saveFarm`)
  идёт другим путём и не использует `FarmsAndPlacesBloc` вовсе (см.
  «Альтернативные потоки»). [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) — уже существующий, замороженный
  артефакт; это расхождение фиксируется здесь, а не правится в нём.
- **Компаундный риск ниже по потоку в реальном пути.** Поскольку реальный
  код правки фермы (`FarmCreateCubit.saveFarm`) не перехватывает исключение
  из `update` вовсе, ошибка там становится необработанным `Future`-исключением,
  а не контролируемым состоянием ошибки — иная и потенциально более грубая
  деградация UX, чем `FarmsPageError` этого use-case, но за пределами кода,
  который здесь документируется.
- Нужно ли когда-либо реально подключать `FarmsPageEventEditFarm`/
  `_onEditFarm` к UI, оставлять его как unused/легаси-код, либо удалить —
  вопрос будущего TARGET-прохода, не разрешается в рамках этой чисто
  документирующей задачи.
