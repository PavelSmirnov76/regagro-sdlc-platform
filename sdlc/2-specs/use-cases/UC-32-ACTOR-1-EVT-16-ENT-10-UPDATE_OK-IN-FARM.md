- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-32 — Пользователь редактирует отделение (название/площадь), локальное сохранение успешно

## Назначение

Пользователь правит название и/или площадь (поле `description`) уже
существующего отделения ([ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)) на
экране структуры фермы и сохраняет изменения. Локальная запись обновляется
без ошибки; для уже синхронизированного отделения взводится `needUpdate:
true` — сама правка на сервер уходит не немедленно, а только на следующем
sync-проходе ([EVT-19](../events/EVT-19-PLACE-UPDATE-SYNCED-IN-FARM.md)).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Экран структуры фермы и его точки входа доступны только внутри
`MainNavigator` (авторизованного шелла приложения), поэтому этот сценарий
предполагает уже выполненный вход.

## CURRENT

### Основной поток

1. Пользователь открывает меню действий фермы (`FarmMoreMenuButton` в
   `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`) и
   выбирает пункт «Структура фермы» (`l10n.farm_structure`) —
   `context.pushNamed(Routes.createPlace, extra: PlaceCreatePageArguments(farmId:
   farm.farm.remoteId!, existingPlaces: farm.placesWithAnimals.map((p) =>
   p.place).toList()))`, то есть с уже существующими отделениями фермы в
   аргументах.
2. `PlaceCreatePage.build` читает аргументы, создаёт `BlocProvider` с
   `PlaceCreateCubit(farmId: ..., existingPlaces: ..., defaultPlaceNames:
   [...])`. Конструктор кубита сразу вызывает `_initializePlaces()`, но
   поскольку `existingPlaces` не пуст, ветка создания дефолтного набора мест
   не выполняется (`if (state.places.isEmpty)`).
3. `_PlacesList.build` строит по одному `_PlaceItem` на каждое место из
   `state.places`; для мест, чьё имя не входит в `defaultPlaceNames`
   (`cubit.isDefaultPlace`), название отображается как редактируемое текстовое
   поле, предзаполненное `place.name`; поле площади (`description`) —
   отдельное текстовое поле с `NumberInputFormatter`, предзаполненное
   `place.description`, редактируемо для любого места независимо от
   `isDefault`.
4. Пользователь правит поля инлайн — оба изменения копятся только в памяти
   кубита, без обращения к БД:
   - Название: `RTextFieldSimple.onChanged` → `cubit.updateCustomPlaceName(index,
     value)` → `state.places[index].copyWith(name: value)`.
   - Площадь: `RTextFieldSimple.onChanged` → `cubit.updatePlaceDescription(index,
     value)` → `state.places[index].copyWith(description: Value(value))`.
5. Пользователь нажимает «Сохранить структуру» (`l10n.save_structure`,
   `BlackCircleButton`; кнопка показана только когда `state.places.isNotEmpty
   && state.places.any((e) => e.name.trim().isNotEmpty)`). Обработчик в
   `_PlacesList.build` (`place_create_page.dart`):
   - `cubit.getPlacesToSave()` — `state.places.where((place) =>
     place.name.isNotEmpty)`.
   - Для каждого места из этого списка, у которого `place.idRemote != null`
     (запись уже существует локально в БД — независимо от знака `idRemote`,
     т.е. и для синхронизированного, и для ещё не отправленного, но уже
     вставленного места), диспатчится
     `context.read<FarmsAndPlacesBloc>().add(FarmsPageEventEditPlace(place))`
     — это ветка данного сценария. Места с `idRemote == null` (ещё ни разу не
     вставленные строки) вместо этого диспатчат `FarmsPageEventAddPlace` — не
     этот сценарий.
   - `cubit.getPlacesToDelete()` (`state.deletedPlaces`) диспатчится отдельно
     как `FarmsPageEventDeletePlace` для каждого удалённого места — не этот
     сценарий.
   - Сразу после диспатча всех событий, без ожидания их обработки,
     вызывается `context.pop()` — цикл диспатча синхронный, `await` на
     обработку событий блоком отсутствует.
6. `FarmsAndPlacesBloc._onEditPlace` (подписан через
   `on<FarmsPageEventEditPlace>(_onEditPlace)`) обрабатывает каждое
   отправленное событие асинхронно, уже после того как экран закрылся:
   `final newPlace = event.updatedPlace.copyWith(needUpdate: true); await
   _placeRepository.update(newPlace);` → `PlaceRepository.update`
   (унаследован от `BaseRepository<PlacesDao, Place, $PlacesTable>.update`) →
   `dao.upd(item)` → `BaseDao.upd` → `updateCurrent().replace(item)` — полная
   замена строки по локальному `id`, а не частичный patch изменённых полей.
7. Вызов завершается без исключения → `_onEditPlace` диспатчит
   `add(FarmsPageEventLoadFarms())`, что повторно вызывает
   `FarmsAndPlacesBloc._onLoadFarms` и перезагружает список ферм/мест/животных
   для главного экрана, эмитя `FarmsPageLoadedWithAnimals`. То же самое
   перезагрузку независимо и избыточно вызывает и собственная подписка блока
   `_placesSubscription` (`_placeRepository.watchAll()`), которая срабатывает
   на любое изменение строки таблицы `Places` вне зависимости от того, каким
   путём она была изменена.

### Альтернативные потоки

- **Второй достижимый вход на тот же экран.** `place_page.dart` — когда у
  места пустое `description`, тап по ссылке «Указать площадь»
  (`l10n.place_specify_area`) тоже ведёт на `Routes.createPlace` с тем же
  `PlaceCreatePageArguments(farmId, existingPlaces: farm.placesWithAnimals...)`
  — структурно тот же экран и тот же поток сохранения, отдельного сценария не
  образует.
- **Очистка поля названия до пустой строки без нажатия удаления.**
  `getPlacesToSave()` фильтрует по `name.isNotEmpty` — такое место выпадает и
  из «to save», и (если пользователь не тапал иконку удаления) из «to
  delete» (`state.deletedPlaces` пополняется только внутри `removePlace()`).
  При сохранении для такого места не диспатчится ни `EditPlace`, ни
  `DeletePlace` — запись в БД остаётся без изменений с прежними
  именем/площадью, тихо пропущенная при этом нажатии «Сохранить». Кнопка
  сохранения при этом не скрывается, пока хотя бы одно из мест списка
  сохраняет непустое имя.
- **Ошибка `_placeRepository.update` (исключение).** `_onEditPlace` ловит
  исключение и эмитит `FarmsPageError('Ошибка редактирования места:
  ${e.toString()}')`, `RESULT = UPDATE_ERROR` — отдельный сценарий, не
  описан этим файлом. Существенно: к моменту, когда это состояние вообще
  могло бы дойти до эмита, экран `PlaceCreatePage` уже закрыт шагом 5
  (`context.pop()` вызван синхронно, без ожидания результата), и ни один
  виджет в `lib/` не подписан на `FarmsPageError` — пользователь эту ошибку
  не увидит независимо от исхода (см. «Открытые вопросы»).
- **`updatePlaceDescription`/`updateCustomPlaceName` не выставляют
  `needUpdate` сами.** Не имеет значения для итогового поведения —
  `_onEditPlace` безусловно форсирует `needUpdate: true` на сохранении,
  независимо от того, что лежало в `Place`, накопленном кубитом.
- **Правка ещё не отправленного отделения (`idRemote < 0`, local-new, но уже
  вставленного в БД).** Диспатчится тот же `FarmsPageEventEditPlace`, что и
  для синхронизированного места — код не различает знак `idRemote`, важно
  только `!= null`. Семантически для ещё не синхронизированного места
  `needUpdate: true` не запускает ничего дополнительно, т.к. отправка на
  сервер для него идёт по отдельному пути (`getAllWithoutRemoteId`/create),
  не через `getAllToUpdate` (см. «Бизнес-правила»).

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность сегмента
  `ENT` в id: обновляемая запись, поля `name`/`description` заменяются
  целиком, `needUpdate` взводится в `true`.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — только контекст: точка
  входа передаёт `farmId` = `Farm.remoteId` фермы, которой принадлежат
  редактируемые места; сама ферма этим сценарием не читается и не пишется,
  `Place.farmId` не меняется.

### Бизнес-правила

- Обновление — синхронное с точки зрения UI (пользователь видит закрытие
  экрана сразу после диспатча события, не после реального завершения
  `PlaceRepository.update`), сама отправка на сервер откладывается на
  следующий sync-проход — так же, как и для правки фермы
  ([EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)).
- `PlaceRepository.update` → `dao.upd` → `updateCurrent().replace(item)` —
  полная замена строки по локальному `id` (Drift `replace`), а не patch
  отдельных изменённых столбцов; любое поле `Place`, не выставленное явно
  перед диспатчем события, сохраняется тем, что уже лежало в объекте `Place`,
  пришедшем в `PlaceCreateCubit` через `existingPlaces` плюс накопленные
  инлайн-правки.
- `needUpdate: true` выставляется безусловно при диспатче
  `FarmsPageEventEditPlace`, без проверки знака `idRemote` — один и тот же
  флаг обслуживает и «правка синхронизированного места» (для него флаг
  осмыслен — сигнал следующему sync-проходу, `PlaceRepository.getAllToUpdate`
  фильтрует по `needUpdate.equals(true) & idRemote.isNotNull()`), и «повторное
  сохранение ещё не отправленного места» (для него флаг ничего не запускает,
  т.к. отправка местного-нового места на сервер идёт по отдельному запросу —
  `getAllWithoutRemoteId`, не `getAllToUpdate`).
- Различение «редактирование» / «создание» на экране структуры фермы
  делается исключительно по `place.idRemote != null` в момент нажатия
  «Сохранить» (`place_create_page.dart`), а не по какому-либо явному флагу
  «это редактирование» — один и тот же экран/кубит обслуживает и создание
  первой структуры фермы, и последующую правку.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестами на успешную ветку (как
для достижимого UI-пути через `place_create_page.dart`, так и напрямую для
`FarmsAndPlacesBloc._onEditPlace`).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` | CURRENT | пункт меню «Структура фермы» — основная точка входа, передаёт `farmId` и текущий список мест фермы |
| `lib/pages/place/place_page.dart` | `PlacePage.build` (ссылка «Указать площадь») | CURRENT | второй достижимый вход на тот же экран, доступен когда у места пустое `description` |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePage.build`, `_PlacesList.build`, `PlaceCreatePageArguments` | CURRENT | читает переданные места, рендерит инлайн-поля правки, на «Сохранить» диспатчит `FarmsPageEventEditPlace`/`AddPlace`/`DeletePlace` и сразу закрывает экран без ожидания результата |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.updateCustomPlaceName`, `updatePlaceDescription`, `getPlacesToSave`, `getPlacesToDelete` | CURRENT | накопление инлайн-правок в памяти, фильтрация мест к сохранению/удалению |
| `lib/pages/farms_and_places/sub_pages/places/place_create_state.dart` | `PlaceCreateState` | CURRENT | freezed-состояние экрана структуры фермы |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditPlace`, `FarmsPageEventEditPlace` | CURRENT | реальный обработчик правки — `copyWith(needUpdate: true)` → `_placeRepository.update`; на успех передиспатчит `FarmsPageEventLoadFarms` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._farmsSubscription`/`_placesSubscription` (`watchAll()`) | CURRENT | список ферм/мест главного экрана обновляется реактивно на изменение таблицы `Places`, независимо от того, каким путём строка была изменена |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventEditPlace` | CURRENT | событие, несущее уже изменённый в памяти `Place` |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageError` | CURRENT (не имеет подписчиков в UI) | эмитится при исключении в `_onEditPlace`, но не слушается ни одним виджетом |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository` (наследует `BaseRepository<PlacesDao, Place, $PlacesTable>.update`), `getAllToUpdate` | CURRENT | делегирует в `dao.upd`; `getAllToUpdate` — выборка для sync-прохода по `needUpdate == true && idRemote != null` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — полная замена строки по `id` |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель, поля `name`/`description`/`idRemote`/`needUpdate` |
| `lib/pages/routes.dart` | `Routes.createPlace` | CURRENT | маршрут экрана структуры фермы, вложен под `Routes.mainNavigator` |

## Критерии приёмки

- Открытие экрана структуры фермы через пункт меню «Структура фермы» (или
  через ссылку «Указать площадь» на экране места) передаёт в
  `PlaceCreateCubit` уже существующие места фермы; дефолтный набор мест не
  создаётся, т.к. `existingPlaces` не пуст.
- Инлайн-правка названия и/или площади в списке отделений обновляет только
  состояние `PlaceCreateCubit` в памяти, без обращения к `PlaceRepository`.
- Нажатие «Сохранить структуру» вызывает `PlaceRepository.update` ровно один
  раз на каждое отредактированное место с `idRemote != null` (через
  `FarmsAndPlacesBloc._onEditPlace`), с копией места, где `needUpdate ==
  true`, и не вызывает `insertPlaceWithNegativeRemoteId` для этих мест.
- Вызов завершается без исключения → триггерится `FarmsPageEventLoadFarms`,
  список ферм/мест главного экрана перезагружается.
- Место с очищенным до пустой строки названием не порождает ни `EditPlace`,
  ни `DeletePlace` при нажатии «Сохранить» (см. «Альтернативные потоки»).

## Связанные тесты

- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-9 —
  FarmsAndPlacesBloc._onEditPlace'` (будет переименовано, не трогать
  сейчас), test `'успех -> update вызван с needUpdate:true'` — покрывает
  реальный обработчик `_onEditPlace`, используемый достижимым UI-путём этого
  сценария.
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit —
  редактирование'`, test `'updatePlaceDescription обновляет описание по
  индексу'` — покрывает инлайн-правку площади в памяти кубита (шаг 4
  основного потока).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit —
  редактирование'`, test `'updateCustomPlaceName переименовывает место по
  индексу'` — покрывает инлайн-правку названия в памяти кубита (шаг 4
  основного потока).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit —
  getPlacesToSave/getPlacesToDelete'`, test `'getPlacesToSave отфильтровывает
  места с пустым именем'` — покрывает фильтрацию, определяющую состав мест,
  для которых вообще диспатчится `EditPlace`/`AddPlace` на шаге 5.
- TBD — теста нет: сквозной UI-путь `place_create_page.dart` (реальный выбор
  `EditPlace` вместо `AddPlace` по `idRemote != null` и синхронный
  `context.pop()` без ожидания результата) не покрыт отдельным widget-тестом;
  проверен только чтением исходного кода.

## Открытые вопросы и ограничения

- **`FarmsPageError` не имеет подписчиков в UI.** Прочтение всего `lib/`
  (`grep -rn "FarmsPageError" lib/`) не находит ни одного `BlocListener`/
  `BlocConsumer<FarmsAndPlacesBloc>`, реагирующего на это состояние — оно
  эмитится, но нигде не отображается пользователю. Для сценария этого файла
  (успех) это не наблюдаемо, но означает, что параллельный сценарий
  `UPDATE_ERROR` для этого же события структурно не имеет пути показать
  ошибку пользователю; дополнительно усугубляется тем, что
  `place_create_page.dart` закрывает экран синхронно, до того как
  `_onEditPlace` вообще успевает завершиться.
- **Место с очищенным названием без явного удаления тихо пропускается при
  сохранении.** `getPlacesToSave()` отфильтровывает пустые имена, но
  `getPlacesToDelete()` пополняется только через `removePlace()` — сочетание
  двух независимых фильтров оставляет промежуточное состояние (имя очищено,
  удаление не запрошено), в котором нажатие «Сохранить» не делает с этой
  записью ничего, оставляя её в БД без изменений. Не проверено, ожидает ли
  пользователь при этом, что запись будет удалена.
- **Расхождение путей в уже существующих [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md).**
  Оба файла ссылаются на `place_create_cubit.dart` по пути
  `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart`;
  фактическое расположение — `lib/pages/farms_and_places/sub_pages/places/
  place_create_cubit.dart` (`find lib/pages/farms_and_places -iname
  "*place_create*"` подтверждает единственную копию файла, только в
  `sub_pages/places/`). [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)
  заморожены и не редактируются этим проходом — путь в «Технические
  зависимости» этого файла указан по факту чтения кода; расхождение
  фиксируется здесь как наблюдение для следующей ревизии графа спек, не как
  исправление задним числом.
- Знак `idRemote` не проверяется при диспатче `FarmsPageEventEditPlace` — для
  ещё не отправленного места (`idRemote < 0`) `needUpdate: true` ничего не
  запускает немедленно, т.к. отправка нового места на сервер идёт по другому
  запросу (`getAllWithoutRemoteId`). Не самостоятельный дефект пользовательского
  сценария (итоговое поведение корректно), но тот же паттерн путаницы двух
  жизненных циклов в одном флаге, что уже отмечен для фермы в
  [UC-23](UC-23-ACTOR-1-EVT-11-ENT-9-UPDATE_OK-IN-FARM.md).
