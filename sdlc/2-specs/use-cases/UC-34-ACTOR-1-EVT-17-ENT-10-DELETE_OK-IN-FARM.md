- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-34 — Пользователь удаляет отделение фермы, удаление успешно

## Назначение

Авторизованный пользователь удаляет отделение (место содержания животных
внутри фермы) из мастера структуры фермы. Happy-path сценарий события
[EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
(`place.deletion_requested`): на месте не остаётся закреплённых (не выбывших)
животных, поэтому удаление проходит без отказа. Реальный эффект в БД зависит
от того, было ли место уже когда-либо синхронизировано с сервером: для
уже синхронизированного — мягкое `isDeleted: true`, для ещё не отправленного —
прямое физическое удаление строки. Отправка мягкого удаления на сервер —
отдельный шаг более позднего sync-прохода
([EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md)), не описанный
этим файлом.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь
(`AuthRepository.isAuthorized() == true`), управляющий структурой своей фермы.

## CURRENT

### Основной поток

1. Точка входа — пункт меню фермы «Структура фермы» (`l10n.farm_structure`,
   `FarmMoreMenuButton.build` в
   `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`) →
   переход на `Routes.createPlace` с `PlaceCreatePageArguments(farmId:
   farm.farm.remoteId!, existingPlaces: <текущие места фермы>)`. Тот же экран
   также открывается по ссылке «указать площадь» на экране конкретного места
   (`_PlacePageBodyState.build` в `lib/pages/place/place_page.dart`) — в обоих
   случаях `existingPlaces` — реальный, непустой список уже существующих мест
   фермы (не сценарий первой настройки с пустым списком из
   [UC-30](UC-30-ACTOR-1-EVT-15-ENT-10-CREATE_OK-IN-FARM.md)).
2. `PlaceCreatePage.build` создаёт `PlaceCreateCubit(farmId, existingPlaces,
   defaultPlaceNames)`. Поскольку `existingPlaces` не пуст,
   `PlaceCreateCubit._initializePlaces` не добавляет дефолтный набор —
   состояние `PlaceCreateState.places` равно переданному списку как есть.
3. Пользователь нажимает иконку удаления (`Icons.delete_forever`,
   `GestureDetector.onTap` в `_PlaceItemState.build`,
   `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`) у
   конкретного места в списке → `cubit.removePlace(index)`.
4. `PlaceCreateCubit.removePlace`: сбрасывает `errorMessage` в `null`; берёт
   `placeToRemove = state.places[index]`.
5. Если `placeToRemove.idRemote != null` — запрашивает
   `_animalsRepository.getAllAnimalsWithDetailsByFilters(placeIds:
   [placeToRemove.idRemote ?? placeToRemove.id!])`
   (`AnimalsRepository.getAllAnimalsWithDetailsByFilters`,
   `lib/repositories/animal/animals_repository.dart`; параметр по умолчанию
   `isNotDeleted: true` — учитываются только текущие, не выбывшие животные).
   Если `placeToRemove.idRemote == null` — запроса нет вовсе, шаг 6
   пропускается: такое место ещё ни разу не было записано в БД (ни
   `PlacesDao.insertPlaceReturning`, ни серверный ответ его не создали), а
   значит на него физически не может ссылаться ни одно животное.
6. Список животных на месте пуст (happy path этого сценария) —
   `animalsForPlace.isEmpty`, проверка проходит, `errorMessage` остаётся
   `null`.
7. Место убирается из `state.places` (`updatedPlaces.removeAt(index)`) —
   только в памяти кубита; на экране место сразу пропадает из списка, но ни
   физическое, ни мягкое удаление в БД ещё не произошло.
8. Место добавляется в `state.deletedPlaces`:
   - если `placeToRemove.idRemote != null && placeToRemove.idRemote! >= 0`
     (место реально существует на сервере) — добавляется как есть, с
     сохранённым `idRemote`;
   - иначе (`idRemote == null`, либо отрицательный — то есть ещё не
     отправленное на сервер) — добавляется с `idRemote`, принудительно
     выставленным в `null` (`copyWith(idRemote: const Value(null))`),
     независимо от того, какое значение там было раньше.
9. `emit(state.copyWith(places: updatedPlaces, deletedPlaces:
   updatedDeletedPlaces))`. `errorMessage` остался `null`, поэтому слушатель
   `_PlacesList.build` (`listenWhen: previous.errorMessage !=
   current.errorMessage`) не показывает `SnackBar`.
10. Пользователь нажимает «Сохранить структуру» (`l10n.save_structure`;
    кнопка видна, только если в `state.places` осталось хотя бы одно место с
    непустым именем после `trim()`). По тапу (`_PlacesList.build`): сначала
    цикл по `cubit.getPlacesToSave()` (диспатчит `FarmsPageEventEditPlace`/
    `FarmsPageEventAddPlace` — не этот сценарий), затем цикл по
    `cubit.getPlacesToDelete()` (= `state.deletedPlaces`) — на каждое место
    диспатчится `FarmsPageEventDeletePlace(place)` в `FarmsAndPlacesBloc`.
    Сразу после обоих циклов — `context.pop()`, без ожидания завершения
    асинхронных обработчиков блока.
11. `FarmsAndPlacesBloc.on<FarmsPageEventDeletePlace>(_onDeletePlace)`: если
    `event.place.idRemote != null` (после нормализации в кубите на шаге 8 это
    верно ровно для мест, действительно уже синхронизированных с сервером) —
    мягкое удаление: `_placeRepository.update(event.place.copyWith(isDeleted:
    true))`; иначе — физическое: `_placeRepository.delete(event.place)`
    (`PlaceRepository` наследует
    `BaseRepository<PlacesDao, Place, $PlacesTable>.update`/`.delete` →
    `BaseDao.upd`/`BaseDao.del` → `updateCurrent().replace(item)` /
    `deleteCurrent().delete(item)`, удаление строки по совпадению с `item`, в
    т.ч. по `id`).
12. Вызов завершается без исключения → `_onDeletePlace` безусловно диспатчит
    `FarmsPageEventLoadFarms()`; независимо от этого, подписка
    `_placesSubscription` на `_placeRepository.watchAll()` (установлена в
    конструкторе блока) тоже реагирует на изменение таблицы `Places` и сама
    диспатчит ещё один `FarmsPageEventLoadFarms()` — после удаления одного
    места список перезагружается минимум дважды (тот же паттерн, что и у
    создания места в
    [UC-30](UC-30-ACTOR-1-EVT-15-ENT-10-CREATE_OK-IN-FARM.md)).
13. `FarmsAndPlacesBloc._onLoadFarms` перечитывает фермы и для каждой —
    `PlaceRepository.getAllWithThisFarmId(farm.remoteId)`, которая фильтрует
    `tbl.isDeleted.isNotValue(true)` — мягко удалённое место (шаг 11) больше
    не попадает в список; физически удалённая строка просто отсутствует в
    таблице `Places`. Экран фермы обновляется — удалённое место больше не
    отображается ни в одном из путей.

### Альтернативные потоки

- **Несколько мест удаляются за один тап «Сохранить структуру»** — каждое
  отдельным `FarmsPageEventDeletePlace`, без общей транзакции; частичный сбой
  середины цикла не откатывает уже удалённые места (тот же паттерн
  нетранзакционного пакетного сохранения, что и у создания в
  [UC-30](UC-30-ACTOR-1-EVT-15-ENT-10-CREATE_OK-IN-FARM.md)).
- **`idRemote == null` в момент `removePlace`** — проверка животных вообще не
  выполняется (см. шаг 5); место убирается из списка сразу, без обращения к
  `AnimalsRepository`.
- **Пользователь закрывает экран до нажатия «Сохранить структуру»**
  (`IconButton` в `AppBar.leading`, `context.pop()`) — весь накопленный
  `state.deletedPlaces` теряется вместе с кубитом; ни одно удаление не
  доходит ни до мягкой, ни до физической записи в БД.
- **На месте есть закреплённые (не выбывшие) животные**
  (`animalsForPlace.isNotEmpty`) — `errorMessage:
  'move_all_animals_to_delete'`, метод завершается `return` до какого-либо
  изменения `places`/`deletedPlaces`; место остаётся в списке. Отдельный
  сценарий (`RESULT = DELETE_REJECTED`), не описанный этим файлом.
- **Исключение в `_placeRepository.update`/`.delete`** —
  `FarmsAndPlacesBloc._onDeletePlace` оборачивает вызов в `try`/`catch`,
  эмитит `FarmsPageError('Ошибка удаления места: ...')`. Отдельный сценарий
  (`RESULT = DELETE_ERROR`), не описанный этим файлом.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность сегмента
  `ENT` в id: удаляемая запись, транзишн «существует» → мягко (`isDeleted:
  true`) либо физически удалена.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не изменяется этим
  сценарием, только читается/передаётся как `farmId` (`Farm.remoteId`) в
  `PlaceCreatePageArguments`.
- `Animal` — сущность модуля ANIMAL (пока не специфицирован отдельно, см.
  границу [MOD-3](../modules/MOD-3-FARM.md)): используется только на чтение,
  как условие блокировки удаления (проверяется, но в этом, успешном,
  сценарии список пуст).

### Бизнес-правила

- Удаление отделения — единственная реально работающая операция удаления в
  этом модуле (у фермы такой функциональности нет вовсе, см.
  [MOD-3](../modules/MOD-3-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)).
- Проверка «нет закреплённых животных» гейтится через `idRemote != null`, а
  не напрямую через факт «место уже сохранено в БД» — на практике это
  эквивалентно, потому что любое место, хоть раз записанное в БД (через
  `insertPlaceWithNegativeRemoteId` либо через серверный ответ), уже имеет
  непустой `idRemote` (положительный или `-id`); пустой `idRemote` бывает
  только у in-memory места текущей сессии мастера, ещё ни разу не
  сохранённого.
- Разделение «мягкое/физическое» удаление выполняется дважды по одному и тому
  же признаку разными компонентами: `PlaceCreateCubit.removePlace` решает,
  какое значение `idRemote` положить в `deletedPlaces` (сохранить или
  принудительно обнулить), а `FarmsAndPlacesBloc._onDeletePlace` решает,
  какую операцию вызвать, по более простому условию `idRemote != null`.
  Корректность второго условия зависит от нормализации, сделанной первым —
  единственная точка диспатча `FarmsPageEventDeletePlace` в коде
  (`_PlacesList.build`) всегда берёт места из `cubit.getPlacesToDelete()`,
  поэтому на практике рассинхронизации нет, но два условия физически лежат в
  разных файлах и не связаны общим кодом.
- Персистентность удаления откладывается до явного нажатия «Сохранить
  структуру» — сам тап на иконку удаления меняет только in-memory состояние
  кубита, ничего не пишет в БД.
- Переход `context.pop()` после диспатча событий удаления не дожидается
  результата ни одного асинхронного обработчика блока — тот же паттерн, что и
  у создания места в
  [UC-30](UC-30-ACTOR-1-EVT-15-ENT-10-CREATE_OK-IN-FARM.md).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и работает как описано в CURRENT;
находки, перечисленные в «Открытые вопросы и ограничения», не блокируют его
выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton.build` | CURRENT | пункт меню «Структура фермы» — точка входа с реальным списком мест фермы в `existingPlaces` |
| `lib/pages/place/place_page.dart` | `_PlacePageBodyState.build` | CURRENT | альтернативная точка входа — ссылка «указать площадь» на экране конкретного места |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePage.build` | CURRENT | создаёт `PlaceCreateCubit` с переданными `farmId`/`existingPlaces` |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `_PlaceItemState.build` | CURRENT | иконка `Icons.delete_forever` — вызывает `cubit.removePlace(index)` |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `_PlacesList.build` | CURRENT | кнопка «Сохранить структуру» — диспатчит `FarmsPageEventDeletePlace` по каждому месту из `getPlacesToDelete()`, затем `context.pop()` без ожидания |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.removePlace` | CURRENT | эффект [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) в памяти кубита — проверка животных (условно), перенос места в `deletedPlaces` с нормализацией `idRemote` |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.getPlacesToDelete` | CURRENT | возвращает `state.deletedPlaces` для диспатча в блок |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | проверка «нет закреплённых животных» (`isNotDeleted: true` по умолчанию), вызывается только когда `idRemote != null` |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventDeletePlace` | CURRENT | событие блока, несущее удаляемый `Place` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onDeletePlace` | CURRENT | эффект [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) в БД — мягкое (`update` с `isDeleted: true`) либо физическое (`delete`) удаление в зависимости от `idRemote` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onLoadFarms`, `_placesSubscription` | CURRENT | безусловная и реактивная (через `watchAll()`) перезагрузка списка мест после удаления |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository` (наследует `BaseRepository<PlacesDao, Place, $PlacesTable>.update`/`.delete`), `PlaceRepository.getAllWithThisFarmId` | CURRENT | делегирует в `dao.upd`/`dao.del`; фильтрует `isDeleted.isNotValue(true)` при перечитывании списка |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd`, `BaseDao.del` | CURRENT | `updateCurrent().replace(item)` / `deleteCurrent().delete(item)` |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель, поля `idRemote`/`isDeleted` |
| `lib/l10n/app_ru.arb` | `farm_structure`, `save_structure`, `move_all_animals_to_delete` | CURRENT | локализованные строки точки входа, кнопки сохранения и сообщения об отказе (последнее — для смежного `DELETE_REJECTED`) |

## Критерии приёмки

- Удаление места без закреплённых (не выбывших) животных по тапу на иконку
  удаления и последующему «Сохранить структуру» завершается без ошибки.
- Для места, у которого `idRemote != null && idRemote! >= 0` (уже
  синхронизировано с сервером), реальный эффект в БД — `update` с
  `isDeleted: true`; строка физически остаётся в таблице `Places`.
- Для места без `idRemote` либо с отрицательным `idRemote` (ещё не отправлено
  на сервер) — реальный эффект в БД — физическое удаление строки
  (`PlaceRepository.delete`).
- После успешного удаления место больше не появляется в списке мест фермы при
  следующей перезагрузке (`FarmsAndPlacesBloc._onLoadFarms`).
- Тап на иконку удаления сам по себе не пишет ничего в БД — эффект наступает
  только после явного «Сохранить структуру».
- Проверка «на месте нет животных» выполняется до изменения
  `places`/`deletedPlaces`, кроме случая места без `idRemote` (ещё не
  персистированного), для которого проверка не выполняется вовсе.

## Связанные тесты

- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit.removePlace'`, test `'idRemote:null (ещё не отправлено на сервер) -> удаляется без проверки животных'` — шаг 5 (место без `idRemote`) (будет переименовано, не трогать сейчас).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit.removePlace'`, test `'idRemote задан, животных нет -> удаляется, попадает в deletedPlaces'` — основной happy path этого сценария на уровне кубита (будет переименовано, не трогать сейчас).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit.removePlace'`, test `'idRemote отрицательный (локальное, не отправленное) -> deletedPlaces получает idRemote:null'` — нормализация `idRemote` на шаге 8 (будет переименовано, не трогать сейчас).
- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-11 — FarmsAndPlacesBloc._onDeletePlace'` (старая нумерация), test `'idRemote != null -> update(isDeleted:true), физически не удаляется'` — мягкое удаление на шаге 11 (будет переименовано, не трогать сейчас).
- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-11 — FarmsAndPlacesBloc._onDeletePlace'` (старая нумерация), test `'idRemote == null -> прямое delete()'` — физическое удаление на шаге 11 (будет переименовано, не трогать сейчас).
- TBD — теста нет на уровне, связывающем оба слоя за один сценарий (тап
  «Сохранить структуру» → диспатч `FarmsPageEventDeletePlace` из реального
  `cubit.getPlacesToDelete()` в реальный `FarmsAndPlacesBloc`): оба слоя
  (`PlaceCreateCubit.removePlace` и `FarmsAndPlacesBloc._onDeletePlace`)
  протестированы независимо, но не как один e2e/widget-поток.
- TBD — теста нет на уровне `data_update_bloc.dart` для последующей отправки
  мягкого удаления на сервер ([EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md)) — вне периметра этого файла.

## Открытые вопросы и ограничения

- **Условие мягкого/физического удаления продублировано в двух файлах разной
  формой одного и того же факта.** `PlaceCreateCubit.removePlace` проверяет
  `idRemote != null && idRemote! >= 0`, чтобы решить, сохранять ли `idRemote`
  при переносе в `deletedPlaces`; `FarmsAndPlacesBloc._onDeletePlace`
  проверяет более простое `idRemote != null`, чтобы решить, вызывать ли
  `update` или `delete`. Второе условие корректно только благодаря
  нормализации, сделанной первым (отрицательный `idRemote` принудительно
  обнуляется перед переносом) — единственная точка диспатча
  `FarmsPageEventDeletePlace` в коде идёт именно через
  `cubit.getPlacesToDelete()`, поэтому расхождения на практике не возникает,
  но это неявная, не закреплённая общим кодом зависимость между двумя
  файлами.
- **`placeToRemove.idRemote ?? placeToRemove.id!` в `removePlace` —
  недостижимая ветвь `??`.** Вызов `_animalsRepository
  .getAllAnimalsWithDetailsByFilters(placeIds: [placeToRemove.idRemote ??
  placeToRemove.id!])` находится внутри `if (placeToRemove.idRemote !=
  null)`, поэтому `placeToRemove.idRemote` в этой точке уже гарантированно
  не `null` — правая часть `??` (`placeToRemove.id!`) никогда не
  выполняется.
- **Двойная перезагрузка списка** после удаления — тот же паттерн, что и у
  создания места ([UC-30](UC-30-ACTOR-1-EVT-15-ENT-10-CREATE_OK-IN-FARM.md)):
  `_onDeletePlace` явно диспатчит `FarmsPageEventLoadFarms()`, и одновременно
  подписка на `PlaceRepository.watchAll()` в конструкторе блока делает то же
  самое при изменении таблицы `Places`.
- **Пакетное удаление не атомарно** — при удалении нескольких мест за один
  тап «Сохранить структуру» каждое из них удаляется отдельным вызовом
  `FarmsPageEventDeletePlace`/`update`/`delete`, без общей транзакции;
  частичный сбой середины цикла не откатывает уже удалённые места.
- Дальнейшая отправка мягкого удаления на сервер и его подтверждение — это
  отдельное событие ([EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md),
  `place.deletion_synced`) и отдельный use-case, не описанный здесь; на
  уровне `data_update_bloc.dart` (`_deletePlacesFromRDS`) тестов для этого
  пути пока нет (см. «Связанные тесты»).
