- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-33 — Пользователь редактирует отделение (место), локальное сохранение отказывает

## Назначение

Пользователь правит название и/или площадь (`description`) уже существующего
отделения на экране структуры фермы и сохраняет изменения. Локальное
обновление записи места ([ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)) завершается исключением;
`FarmsAndPlacesBloc._onEditPlace` перехватывает его и эмитит состояние ошибки,
но экран к этому моменту уже закрыт — пользователь не получает никакой
обратной связи о том, что правка не сохранилась.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь. Экран структуры мест фермы доступен
только внутри `MainNavigator` (авторизованного шелла приложения) через меню
действий фермы, поэтому сценарий предполагает уже выполненный вход.

## CURRENT

### Основной поток

1. Пользователь открывает меню действий фермы (`FarmMoreMenuButton` в
   `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`) и
   выбирает пункт «Структура фермы» (`l10n.farm_structure`) — переход на
   `Routes.createPlace` с `PlaceCreatePageArguments(farmId: farm.farm.remoteId!,
   existingPlaces: farm.placesWithAnimals.map((p) => p.place).toList())`, то
   есть с уже существующими местами фермы в аргументах. Тот же экран достижим
   и из `PlacePage` (`_PlacePageBodyState.build`, ссылка «Указать площадь»,
   `l10n.place_specify_area`) — только когда у места ещё пусто поле
   `description`.
2. `PlaceCreatePage` создаёт `PlaceCreateCubit(farmId: ..., existingPlaces:
   ..., defaultPlaceNames: ...)` — `PlaceCreateState.initial` кладёт
   переданные места в `state.places` без похода в БД повторно; т.к.
   `existingPlaces` не пуст, `_initializePlaces()` не подставляет
   стандартный набор мест.
3. Пользователь правит поля существующего места (`_PlaceItem` в
   `place_create_page.dart`) — название через `RTextFieldSimple.onChanged` →
   `PlaceCreateCubit.updateCustomPlaceName(index, value)`, площадь через
   второе `RTextFieldSimple.onChanged` → `PlaceCreateCubit
   .updatePlaceDescription(index, description)`. Оба метода делают
   `state.places[index].copyWith(...)` и `emit` нового списка — идёт только
   в памяти кубита, без записи в БД.
4. Пользователь нажимает «Сохранить структуру» (`BlackCircleButton`,
   `l10n.save_structure`, видима только когда `state.places.isNotEmpty` и
   хотя бы одно место с непустым именем). Обработчик `onTap` в
   `_PlacesList.build` (`place_create_page.dart`):
   - берёт `cubit.getPlacesToSave()` — все места с непустым `name`;
   - для каждого места с `idRemote != null` (в том числе только что
     отредактированное) диспатчит `context.read<FarmsAndPlacesBloc>()
     .add(FarmsPageEventEditPlace(place))`;
   - для мест с `idRemote == null` диспатчит `FarmsPageEventAddPlace`
     (не этот сценарий);
   - для `cubit.getPlacesToDelete()` диспатчит `FarmsPageEventDeletePlace`
     (не этот сценарий);
   - сразу же, без ожидания результата ни одного из добавленных событий,
     безусловно вызывает `context.pop()`.
5. `FarmsAndPlacesBloc._onEditPlace` (`lib/pages/farms_and_places
   /farms_page_bloc.dart`) обрабатывает `FarmsPageEventEditPlace`: строит
   `newPlace = event.updatedPlace.copyWith(needUpdate: true)` и вызывает
   `await _placeRepository.update(newPlace)` — `PlaceRepository.update`
   унаследован из `BaseRepository<PlacesDao, Place, $PlacesTable>` (метод не
   переопределён), делегирует в `dao.upd(item)` →
   `BaseDao.upd` → `updateCurrent().replace(item)` (Drift, полная замена
   строки по локальному `id`).
6. Вызов `_placeRepository.update` выбрасывает исключение (например ошибка
   БД/констрейнта) — `_onEditPlace` перехватывает его в `catch (e)` и
   эмитит `FarmsPageError('Ошибка редактирования места: ${e.toString()}')`;
   `add(FarmsPageEventLoadFarms())` (вызывался бы в случае успеха) не
   выполняется — список ферм/мест не перезагружается по этой ветке.
7. Ни один виджет в приложении не подписан на состояния
   `FarmsAndPlacesBloc` (`BlocBuilder`/`BlocListener`/`BlocConsumer`) —
   единственное место, где на этот блок вообще есть ссылка кроме его
   собственного файла, это `place_create_page.dart`, и там он используется
   только через `context.read<FarmsAndPlacesBloc>().add(...)`, без
   прослушивания `stream`/состояния. Эмитированный `FarmsPageError` уходит
   в стрим блока, но экран к этому моменту уже закрыт шагом 4 (`context
   .pop()` выполнен синхронно, не дожидаясь исхода асинхронного
   `_onEditPlace`) — пользователь не видит ни снекбара, ни какого-либо
   другого индикатора ошибки.
8. Локальная строка места не изменяется (исключение прервало
   `updateCurrent().replace`) — введённая пользователем правка названия/
   площади теряется без следа для пользователя: на экране, к которому он
   вернулся, будет показано прежнее (неотредактированное) состояние места,
   как только источник данных этого экрана (`MainNavigatorCubit`/
   `PlaceCubit`, через собственные независимые подписки на
   `_placeRepository.watchAll()`) в следующий раз перечитает список — а
   поскольку строка не менялась, `watchAll()` в этой ветке вообще не
   сработает.

### Альтернативные потоки

- **Несколько мест сохраняются в одном действии «Сохранить структуру».**
  Цикл `for (final place in placesToSave)` диспатчит по одному
  `FarmsPageEventEditPlace`/`FarmsPageEventAddPlace` на каждое место;
  `on<FarmsPageEventEditPlace>(_onEditPlace)` зарегистрирован без явного
  `transformer` (bloc по умолчанию обрабатывает события конкурентно) — сбой
  `update` для одного места не блокирует и не откатывает обработку событий
  по остальным местам того же сохранения.
- **Нет защиты от повторного нажатия «Сохранить структуру».** В отличие от
  `FarmCreateCubit.saveFarm()` (см. [UC-23](UC-23-ACTOR-1-EVT-11-ENT-9-UPDATE_OK-IN-FARM.md)), `onTap` в `place_create_page
  .dart` не проверяет никакой флаг вроде `isSubmitting` — повторное быстрое
  нажатие до завершения предыдущего вызова просто диспатчит те же события
  ещё раз.
- **Место ещё не синхронизировано (`idRemote == null`).** Такое место не
  попадает в этот сценарий — цикл сохранения направляет его в
  `FarmsPageEventAddPlace`/`_onAddPlace`, а не в `FarmsPageEventEditPlace`/
  `_onEditPlace`.
- **`removePlace()` c ошибкой «есть животные».** Отдельный, не связанный с
  этим сценарием путь ошибки — `PlaceCreateCubit.removePlace` сам
  устанавливает `state.errorMessage = 'move_all_animals_to_delete'`,
  который **действительно** показывается через `showAppSnackBarError` в
  `_PlacesList`'s `BlocConsumer` (`listener`); этот механизм существует
  в том же файле, но не используется для ошибки `_onEditPlace` — он
  слушает `PlaceCreateCubit`, а `_onEditPlace` работает внутри отдельного
  `FarmsAndPlacesBloc`, который в этом виджете не прослушивается.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность сегмента `ENT` в id: обновление её локальной
  записи (`name`/`description`/`needUpdate`) не завершается — исключение
  прерывает запись, старые значения строки в БД остаются как есть.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не пишется этим сценарием напрямую, но экран
  структуры мест открывается в контексте конкретной фермы (`farmId`),
  переданной из `FarmMoreMenuButton`/`PlacePage`.

### Бизнес-правила

- Как и для фермы ([EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)/[UC-23](UC-23-ACTOR-1-EVT-11-ENT-9-UPDATE_OK-IN-FARM.md)), правка места локально-синхронная с
  точки зрения кода: `needUpdate: true` взводится безусловно при вызове
  `_onEditPlace`, без проверки, действительно ли место уже
  синхронизировано (`idRemote != null` уже гарантирован тем, что именно
  такие места попадают в `FarmsPageEventEditPlace`, а не `AddPlace`).
- `PlaceRepository.update` → `dao.upd` → `updateCurrent().replace(item)` —
  полная замена строки по локальному `id` (Drift `replace`), а не patch
  отдельных изменённых столбцов.
- В отличие от аналогичного пути правки фермы (`FarmCreateCubit.saveFarm()`,
  где исключение из `_farmRepository.update` вообще не перехватывается и
  улетает необработанным — см. «Открытые вопросы и ограничения» в [UC-23](UC-23-ACTOR-1-EVT-11-ENT-9-UPDATE_OK-IN-FARM.md)),
  для места исключение **перехвачено** (`try`/`catch` в `_onEditPlace`) и
  превращено в типизированное состояние `FarmsPageError`. Но итог для
  пользователя тот же — никакой видимой обратной связи, потому что состояние
  некому слушать (см. «Основной поток», шаг 7).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован (перехват исключения в `_onEditPlace`
работает и покрыт тестом на уровне блока); отсутствие пользовательской
обратной связи об ошибке — задокументированный факт текущего поведения, а не
незавершённая реализация (см. «Открытые вопросы и ограничения»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` | CURRENT | пункт меню «Структура фермы» — точка входа на экран структуры мест уже существующей фермы, передаёт `existingPlaces` |
| `lib/pages/place/place_page.dart` | `_PlacePageBodyState.build` | CURRENT | альтернативная точка входа («Указать площадь») на тот же экран, только когда `description` пусто |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePage`, `_PlacesList.build` | CURRENT | инициализация `PlaceCreateCubit` из переданных мест; кнопка «Сохранить структуру» — диспатчит `FarmsPageEventEditPlace` для правленых мест и безусловно вызывает `context.pop()` сразу после диспатча |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.updateCustomPlaceName`, `updatePlaceDescription`, `getPlacesToSave` | CURRENT | накопление правок в памяти кубита, отбор мест с непустым именем к сохранению |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditPlace`, `FarmsPageEventEditPlace` | CURRENT | перехватывает исключение `_placeRepository.update`, эмитит `FarmsPageError`; не диспатчит `FarmsPageEventLoadFarms` в этой ветке |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageError` | CURRENT | состояние ошибки — не прослушивается ни одним виджетом приложения |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository` (наследует `BaseRepository<PlacesDao, Place, $PlacesTable>.update`) | CURRENT | делегирует в `dao.upd`, не переопределяет `update` |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — полная замена строки по `id`, источник исключения при сбое |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель, поля `name`/`description`/`needUpdate`/`idRemote` |
| `lib/main.dart` | `BlocProvider<FarmsAndPlacesBloc>` | CURRENT | единственная регистрация блока в дереве виджетов; ни один потомок не оборачивает его в `BlocBuilder`/`BlocListener`/`BlocConsumer` |

## Критерии приёмки

- Открытие экрана структуры мест через пункт меню «Структура фермы»
  передаёт в `PlaceCreateCubit` уже существующие места фермы, включая
  синхронизированные (`idRemote != null`).
- Правка названия/площади существующего места и нажатие «Сохранить
  структуру» диспатчит ровно один `FarmsPageEventEditPlace` на это место с
  `needUpdate` уже выставленным на стороне обработчика.
- Если `PlaceRepository.update` выбрасывает исключение,
  `FarmsAndPlacesBloc._onEditPlace` перехватывает его и эмитит
  `FarmsPageError`, содержащий подстроку `'Ошибка редактирования места'`;
  исключение не всплывает наружу из обработчика; `FarmsPageEventLoadFarms`
  в этой ветке не диспатчится.
- Экран `PlaceCreatePage` закрывается сразу после диспатча событий
  сохранения независимо от исхода `_onEditPlace` — ни `BlocListener`, ни
  снекбар, ни иной UI-индикатор ошибки для этой ветки не появляются.
- Локальная строка места в БД не изменяется, если `update` выбросил
  исключение раньше завершения записи.

## Связанные тесты

- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-10 —
  FarmsAndPlacesBloc._onEditPlace ERROR'` (будет переименовано, не трогать
  сейчас), test `'update бросает -> FarmsPageError("Ошибка редактирования
  места: ...")'` — покрывает перехват исключения и эмит `FarmsPageError`
  на уровне блока.
- Отдельного теста на то, что `PlaceCreatePage` закрывается независимо от
  исхода и что ошибка нигде не отображается пользователю (UI-уровень, не
  уровень блока), нет — TBD, теста нет.

## Открытые вопросы и ограничения

- **`FarmsPageError`, эмитированный `_onEditPlace`, никем не прослушивается.**
  Прочтение всего `lib/` (`grep -rln "BlocBuilder<FarmsAndPlacesBloc\|
  BlocListener<FarmsAndPlacesBloc\|BlocConsumer<FarmsAndPlacesBloc" lib/`) не
  находит ни одного вхождения — `FarmsAndPlacesBloc` регистрируется в
  `lib/main.dart` и используется только через `context.read<...>().add(...)`
  в `place_create_page.dart`, без прослушивания состояния. В отличие от
  соседнего фермерского пути ([UC-23](UC-23-ACTOR-1-EVT-11-ENT-9-UPDATE_OK-IN-FARM.md)), где исключение из
  `_farmRepository.update` вообще не перехватывается, здесь исключение
  перехвачено и оформлено как типизированное состояние — но результат для
  пользователя идентичен: никакой видимой обратной связи об ошибке.
- **`context.pop()` в `_PlacesList.build` вызывается синхронно, не дожидаясь
  ни одного из диспатченных событий.** Экран закрывается независимо от
  того, успеет ли `_onEditPlace` завершиться успехом, ошибкой, или вообще
  выполниться до навигации — тайминг между `pop()` и асинхронным
  обработчиком блока не гарантирован ни в какую сторону.
- **Пре-существующая неточность пути в исходных данных [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) этого
  сценария.** [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) (заморожен, не редактируется этим проходом) цитирует
  `PlaceCreateCubit.updatePlaceDescription`/`updateCustomPlaceName` по пути
  `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit
  .dart` — фактически на момент написания этого файла класс находится по
  пути `lib/pages/farms_and_places/sub_pages/places/place_create_cubit
  .dart` (тот же класс, файл перемещён). Технические зависимости этого
  use-case выше указывают проверенный актуальный путь; расхождение в
  [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) зафиксировано здесь как факт для следующей ревизии графа спек,
  не исправляется в рамках этого прохода (события заморожены).
- Нет защиты от повторного нажатия «Сохранить структуру» (в отличие от
  `FarmCreateCubit.saveFarm()` с флагом `isSubmitting`) — не проверялось,
  требует ли это отдельного сценария гонки при параллельных вызовах
  `_onEditPlace` для одного и того же места.
