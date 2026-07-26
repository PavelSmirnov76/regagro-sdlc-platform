- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md), [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)

# UC-23 — Пользователь редактирует ферму (название/адрес), локальное сохранение успешно

## Назначение

Пользователь правит название и/или адрес уже существующей фермы и сохраняет
изменения. Локальная запись фермы ([ENT-9](../entities/ENT-9-FARM-IN-FARM.md)) обновляется без ошибки; для уже
синхронизированной фермы взводится `needUpdate: true` — сама правка на сервер
уходит не немедленно, а только на следующем sync-проходе
([EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md)).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь. Ферма и её меню действий доступны
только внутри `MainNavigator` (авторизованного шелла приложения), поэтому этот
сценарий предполагает уже выполненный вход.

## CURRENT

### Основной поток

1. Пользователь открывает меню действий фермы (`FarmMoreMenuButton` в
   `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`) и
   выбирает пункт «Редактировать» (`l10n.edit_farm`) — переход на
   `Routes.createFarm` с `FarmCreatePageArguments(farm: farm.farm)`, то есть с
   уже существующей фермой в аргументах.
2. `FarmCreatePage` создаёт `FarmCreateCubit()..loadData(farm)` —
   `FarmCreateCubit.loadData` кладёт переданную ферму в `FarmCreateState.farm`
   без похода в БД за ней повторно; `isFirstFarm` при этом всегда `false`, т.к.
   `existingFarm != null`.
3. Пользователь проходит шаги мастера (`FarmCreateStep.name` /
   `FarmCreateStep.address`; шаг видимости видов недоступен для правки, т.к.
   `isFirstFarm == false`) — правки названия/адреса накапливаются в
   `FarmCreateState.farm` через `updateFarmName`/`handlePlaceSelection`/
   `handleReverseGeocode`/`updateLatitude`/`updateLongitude`.
4. На последнем шаге (`address`, единственный доступный при правке) кнопка
   FAB вызывает `cubit.canSave()`, и если true — `FarmCreateCubit.saveFarm()`.
5. `saveFarm()` эмитит `isSubmitting: true`; поскольку `state.farm.id != null`
   (ферма уже существует локально), выполняется ветка обновления:
   `final newFarm = state.farm.copyWith(needUpdate: true);` →
   `await _farmRepository.update(newFarm)` (`FarmRepository.update`,
   унаследован из `BaseRepository<FarmsDao, Farm, $FarmsTable>` →
   `dao.upd(item)` → `updateCurrent().replace(item)` — полная замена строки по
   локальному `id`, без частичного patch по изменённым полям).
6. Вызов завершается без исключения → `saveFarm()` эмитит
   `state.copyWith(isSuccess: true)`, затем в `finally` —
   `isSubmitting: false`.
7. `FarmCreatePage`, слушая `FarmCreateCubit` (`BlocListener`,
   `listenWhen: state.isSuccess`), вызывает `_onSuccess`: `context.pop()` и
   сразу переход на `Routes.createPlace` с `PlaceCreatePageArguments(farmId:
   state.farm.remoteId!, existingPlaces: [])` — тот же переход, что и после
   создания новой фермы; `existingPlaces` жёстко задан пустым списком,
   независимо от того, что ферма уже редактируется, а не создаётся впервые —
   реальный список мест фермы этим переходом не подгружается.
8. Отдельно (вне прямой цепочки `saveFarm`) `FarmsAndPlacesBloc` подписан на
   `_farmsRepository.watchAll()`; изменение строки в таблице `Farms` триггерит
   этот стрим и заставляет блок передиспатчить `FarmsPageEventLoadFarms`,
   перечитывающий список ферм для главного экрана — обновление после правки
   долетает и туда, но не через `FarmsPageEventEditFarm`.

### Альтернативные потоки

- **Отдельный, структурно параллельный обработчик того же события существует,
  но недостижим ни из одного экрана.** `FarmsAndPlacesBloc` объявляет и
  подписывает `on<FarmsPageEventEditFarm>(_onEditFarm)`
  (`lib/pages/farms_and_places/farms_page_bloc.dart`) — именно этот метод
  назван триггером в самом [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) («`FarmsAndPlacesBloc.on<FarmsPageEventEditFarm>`»).
  `_onEditFarm` делает то же самое по сути (`event.updatedFarm.copyWith(needUpdate:
  true)` → `_farmsRepository.update(newFarm)`), но по прочтении всего `lib/`
  (`grep -rn "FarmsPageEventEditFarm" lib/`) единственные места, где
  `FarmsPageEventEditFarm` упоминается, — это его собственное объявление и
  `_onEditFarm` в `farms_page_bloc.dart`; ни один виджет его не диспатчит.
  Соседний `place_create_page.dart` диспатчит в тот же блок
  `FarmsPageEventEditPlace`/`FarmsPageEventAddPlace`/`FarmsPageEventDeletePlace`,
  но не `FarmsPageEventEditFarm`. Реальная кнопка «Редактировать» ведёт
  исключительно через `FarmCreatePage`/`FarmCreateCubit.saveFarm()` (см.
  «Основной поток»), это отдельный, не связанный с `FarmsAndPlacesBloc` код.
  Это задокументированный факт мёртвого кода, а не альтернативная бизнес-ветка
  — см. «Открытые вопросы и ограничения».
- **Правка ещё не отправленной фермы (`remoteId < 0`, local-new).** И
  `FarmCreateCubit.saveFarm()`, и (недостижимый) `_onEditFarm` ставят
  `needUpdate: true` одинаково, не проверяя знак `remoteId` — для
  ещё не синхронизированной фермы это семантически пустая пометка (см.
  «Бизнес-правила» и уже зафиксированную находку в `TESTING_CHECKLIST.md`).
  Отдельного `RESULT` это не меняет, `update_ok` остаётся тем же.
- **Повторное нажатие сохранить, пока первый вызов ещё выполняется.**
  `saveFarm()` имеет защиту `if (state.isSubmitting) return;` в начале метода —
  второй вызов, пока первый не завершился, — no-op.
- **Ошибка `_farmRepository.update` (исключение).** Отдельный сценарий,
  `RESULT = UPDATE_ERROR`, не описан этим файлом — `saveFarm()` не оборачивает
  вызов `update` в `try`/`catch` вокруг самого исключения (только `finally` для
  сброса `isSubmitting`), поэтому исключение улетает необработанным из
  `saveFarm()`, а не превращается в отдельное состояние ошибки экрана.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — сущность сегмента `ENT` в id: обновляемая запись, поля
  `name`/`address` (и производные адресные id/координаты) заменяются целиком,
  `needUpdate` взводится в `true`.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — не читается и не пишется самим `saveFarm()`, но следующий
  экран после успеха (`Routes.createPlace`) — это структура мест этой же
  фермы; передаётся с пустым `existingPlaces`, реальный список мест этим
  сценарием не подгружается.

### Бизнес-правила

- Обновление — синхронное с точки зрения UI (пользователь видит успех сразу
  после локального сохранения), сама отправка на сервер откладывается на
  следующий sync-проход — так же, как и для [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) (место).
- `FarmRepository.update` → `dao.upd` → `updateCurrent().replace(item)` —
  полная замена строки по локальному `id` (Drift `replace`), а не patch
  отдельных изменённых столбцов; любое поле `Farm`, не выставленное явно перед
  вызовом `saveFarm()`, сохраняется тем, что уже лежало в `FarmCreateState.farm`
  на момент вызова (значения из `loadData(existingFarm)` плюс накопленные шаги
  мастера).
- `needUpdate: true` выставляется безусловно при `farm.id != null`, без
  проверки знака `remoteId` — один и тот же флаг обслуживает и «правка
  синхронизированной фермы» (для неё флаг осмыслен — сигнал следующему
  sync-проходу), и «повторное сохранение ещё не отправленной фермы» (для неё
  флаг ничего не запускает, т.к. отправка local-new фермы на сервер идёт по
  отдельному пути — `getAllWithoutRemoteId`/create, не `getAllToUpdate`).
- Шаг видимости видов (`FarmCreateStep.kindsVisibility`) недоступен при правке
  — `_getAvailableSteps()` добавляет его только при `state.isFirstFarm`, а
  `isFirstFarm` при переданной `existingFarm` всегда `false`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован (через `FarmCreateCubit.saveFarm()`) и
покрыт тестами на успешную ветку; параллельный `FarmsAndPlacesBloc._onEditFarm`
тоже полностью реализован и покрыт тестами, но недостижим из UI (см.
«Открытые вопросы и ограничения» — не блокер этого сценария, факт о состоянии
кода).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` | CURRENT | пункт меню «Редактировать» — реальная точка входа в правку фермы, переход на `Routes.createFarm` с существующей фермой в аргументах |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage.build`, `FarmCreatePageArguments` | CURRENT | читает переданную ферму из `GoRouterState`, создаёт `FarmCreateCubit()..loadData(farm)`, слушает `isSuccess` для перехода на структуру мест |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.loadData` | CURRENT | кладёт переданную `existingFarm` в состояние, `isFirstFarm = false` |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.saveFarm` | CURRENT | ветка `state.farm.id != null` — `copyWith(needUpdate: true)` → `_farmRepository.update`; защита от повторного вызова через `isSubmitting` |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.canSave` | CURRENT | гейтит доступность кнопки сохранения на последнем шаге |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository` (наследует `BaseRepository<FarmsDao, Farm, $FarmsTable>.update`) | CURRENT | делегирует в `dao.upd` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — полная замена строки по `id` |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `Farms`, `Farm` | CURRENT | таблица/модель, поля `name`/`address`/`needUpdate` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditFarm`, `FarmsPageEventEditFarm` | CURRENT (недостижимо из UI) | структурно параллельный обработчик того же факта — реализован и оттестирован, но ни один виджет его не диспатчит |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._farmsSubscription` (`_farmsRepository.watchAll()`) | CURRENT | список ферм главного экрана обновляется реактивно на изменение таблицы `Farms`, независимо от того, каким путём строка была изменена |

## Критерии приёмки

- Открытие фермы на редактирование через пункт меню «Редактировать»
  передаёт существующую ферму в `FarmCreateCubit` — шаг видимости видов
  недоступен (`isFirstFarm == false`).
- Сохранение на последнем доступном шаге при `state.farm.id != null` вызывает
  `FarmRepository.update` ровно один раз с копией фермы, где `needUpdate ==
  true`, и не вызывает `insertFarmWithNegativeRemoteId`.
- Вызов завершается без исключения → `FarmCreateState.isSuccess == true`,
  `isSubmitting` возвращается в `false`; экран переходит на структуру мест той
  же фермы (`Routes.createPlace`, `farmId: state.farm.remoteId!`).
- Повторное нажатие «Сохранить» до завершения первого вызова не порождает
  второй вызов `update` (`isSubmitting`-защита).

## Связанные тесты

- `test/pages/farm_create_cubit_test.dart`, group `'FarmCreateCubit.saveFarm'`,
  test `'farm.id != null -> update с needUpdate:true, remoteId не трогается'`
  — покрывает реальный, достижимый из UI путь этого сценария.
- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-3 —
  FarmsAndPlacesBloc._onEditFarm'` (будет переименовано, не трогать сейчас),
  test `'успех -> update вызван с needUpdate:true'` — покрывает структурно
  параллельный, но недостижимый из UI обработчик `_onEditFarm` (см. «Основной
  поток»/«Альтернативные потоки»).

## Открытые вопросы и ограничения

- **`FarmsAndPlacesBloc._onEditFarm`/`FarmsPageEventEditFarm` — мёртвый код с
  точки зрения UI, хотя [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) называет именно его триггером.** Прочтение
  всего `lib/` (`grep -rn "FarmsPageEventEditFarm" lib/`) не находит ни одного
  `.add(FarmsPageEventEditFarm(...))` — единственная реальная кнопка правки
  фермы (`l10n.edit_farm` в `FarmMoreMenuButton`) идёт через отдельный
  `FarmCreateCubit.saveFarm()`, не через `FarmsAndPlacesBloc`. Оба пути
  реализуют одну и ту же бизнес-операцию (`needUpdate: true` +
  `FarmRepository.update`) независимо друг от друга и оба полностью
  оттестированы, но только один из них когда-либо вызывается пользователем.
  Это не решение, требующее переопределения [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) в рамках этого прохода
  (события заморожены) — фиксируется здесь как факт, требующий внимания при
  следующей ревизии графа спек.
- `needUpdate: true` выставляется без проверки знака `remoteId` в обоих путях
  — для ещё не отправленной фермы (`remoteId < 0`) флаг ничего не запускает,
  т.к. отправка на сервер идёт по другому запросу (`getAllWithoutRemoteId`).
  Не самостоятельный дефект пользовательского сценария (итоговое поведение
  корректно), но признак путаницы двух разных жизненных циклов в одном флаге
  — уже зафиксировано в `TESTING_CHECKLIST.md`.
- `saveFarm()` не оборачивает вызов `_farmRepository.update` в `try`/`catch` —
  любое исключение (например ошибка БД) улетает необработанным из метода;
  `isSubmitting` всё равно сбрасывается через `finally`, но `isSuccess`
  никогда не выставляется в `true`, и отдельного состояния ошибки для этой
  ветки в `FarmCreateState` нет. `RESULT = UPDATE_ERROR` для этого пути не
  описан ни этим, ни каким-либо другим use-case файлом на момент написания.
- Переход на `Routes.createPlace` после успешной правки всегда передаёт
  `existingPlaces: []`, даже если у фермы уже есть места — экран структуры мест
  сам их не подгружает из этого перехода; не проверено в рамках этого файла,
  восполняет ли `PlaceCreateCubit` этот список самостоятельно при старте (вне
  периметра — это уже часть [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)/use-case создания места, не правки фермы).
