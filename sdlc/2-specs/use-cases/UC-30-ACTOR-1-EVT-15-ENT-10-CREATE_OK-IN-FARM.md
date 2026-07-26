# UC-30 — Пользователь создаёт отделение фермы, локальное сохранение успешно

## Назначение

Авторизованный пользователь добавляет отделение (место содержания животных
внутри фермы) — либо принимая предложенный стандартный набор при первой
настройке структуры только что созданной фермы, либо добавляя произвольное
отделение вручную в любой момент позже. Happy-path сценарий события
[EVT-15](../events/EVT-15-PLACE-CREATED-IN-FARM.md) (`place.created`): место
сохраняется локально с отрицательным `idRemote`, без ожидания сервера и без
сетевого вызова в рамках этого сценария.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь
(`AuthRepository.isAuthorized() == true`), управляющий структурой своей
фермы.

## CURRENT

### Основной поток

1. Экран создания места (`Routes.createPlace` →
   `PlaceCreatePage`) открывается одним из двух путей:
   - **Первая настройка структуры**: сразу после успешного сохранения новой
     фермы `FarmCreatePage._onSuccess` переходит на `Routes.createPlace` с
     `PlaceCreatePageArguments(farmId: <новый farmId>, existingPlaces: [])`.
   - **Ручное добавление в любой момент**: пункт меню «Структура фермы»
     (`FarmMoreMenuButton.build`, `l10n.farm_structure`) или ссылка «указать
     площадь» на экране конкретного места (`_PlacePageBodyState.build` в
     `lib/pages/place/place_page.dart`) открывают тот же маршрут с
     `existingPlaces` = текущий список мест этой фермы.
2. `PlaceCreatePage.build` создаёт `PlaceCreateCubit` с `farmId`,
   `existingPlaces` и захардкоженным в странице списком `defaultPlaceNames` из
   пяти локализованных названий: `general_herd` («Общее стадо»),
   `adult_animals` («Взрослые особи»), `young_animals` («Молодняк»), `nursery`
   («Ясли»), `quarantine` («Карантин»).
3. Конструктор кубита вызывает `PlaceCreateCubit._initializePlaces`: если
   `existingPlaces` пуст — генерируются 5 in-memory объектов `Place`
   (`name` — очередное значение из `defaultPlaceNames`, `description: ''`,
   `needUpdate: true`, `isDeleted: false`, `farmId: state.farmId`, `id`/
   `idRemote` не заданы) и кладутся в состояние; ни один из них ещё не
   сохранён в БД. Если `existingPlaces` не пуст, дефолтные места не
   добавляются вовсе — состояние равно переданному списку как есть.
4. Пользователь взаимодействует со списком до сохранения:
   - редактирует площадь (`description`, подпись «м²»,
     `l10n.square_meters`) любого места через
     `PlaceCreateCubit.updatePlaceDescription`;
   - переименовывает **не дефолтное** место через
     `PlaceCreateCubit.updateCustomPlaceName` — для дефолтных мест
     (`cubit.isDefaultPlace(name)` возвращает `true` по точному совпадению
     строки с `defaultPlaceNames`) поле имени в UI не редактируемо, рендерится
     как статичный `Text`;
   - добавляет ещё одно произвольное место кнопкой «Добавить +»
     (`l10n.add_plus`) → `PlaceCreateCubit.addCustomPlace` — добавляет в конец
     списка ещё один in-memory `Place` с `name: ''`, `description: ''`,
     `needUpdate: true`, `isDeleted: false`.
5. Кнопка «Сохранить структуру» (`l10n.save_structure`) видна только когда в
   состоянии есть хотя бы одно место с непустым (после `trim()`) именем
   (`_PlacesList.build`).
6. По тапу на «Сохранить структуру» (`_PlacesList.build`):
   `cubit.getPlacesToSave()` (`PlaceCreateCubit.getPlacesToSave`) отфильтровывает
   места с пустым `name` из полного `state.places`. Для каждого оставшегося
   места: если `place.idRemote != null` — диспатчится
   `FarmsPageEventEditPlace(place)` (другой сценарий, не этот); иначе —
   диспатчится `FarmsPageEventAddPlace(place)` в
   `FarmsAndPlacesBloc` — это и есть создание, EVT-15. Для каждого места из
   `cubit.getPlacesToDelete()` отдельно диспатчится
   `FarmsPageEventDeletePlace` (тоже не этот сценарий). Сразу после диспатча
   всех событий вызывается `context.pop()` — переход не дожидается результата
   ни одного из асинхронных обработчиков блока.
7. `FarmsAndPlacesBloc._onAddPlace` обрабатывает `FarmsPageEventAddPlace`:
   вызывает `PlaceRepository.insertPlaceWithNegativeRemoteId(event.place)`.
8. `PlaceRepository.insertPlaceWithNegativeRemoteId`:
   `PlacesDao.insertPlaceReturning` (`into(places).insertReturning(place)`)
   вставляет строку и возвращает её с присвоенным Drift'ом автоинкрементным
   `id`; затем `PlacesDao.setPlaceNegativeRemoteId` выполняет
   `UPDATE places SET id_remote = -id WHERE id = id`, то есть проставляет
   `idRemote = -id`. Никакого сетевого вызова на этом шаге нет — место
   становится локально-несинхронизированной записью (аналог
   `Animal.id < 0` из инварианта 1 `domain-model.md`, но на поле `idRemote`,
   не на `id`).
9. После завершения вызова репозитория (успешно или с проглоченным
   исключением — см. «Открытые вопросы») `_onAddPlace` безусловно диспатчит
   `FarmsPageEventLoadFarms()`, которая перезагружает список ферм/мест/животных
   (`FarmsAndPlacesBloc._onLoadFarms`). Независимо от этого, подписка
   `_placesSubscription` на `PlaceRepository.watchAll()`, установленная в
   конструкторе блока, тоже реагирует на изменение таблицы `Places` и сама
   диспатчит ещё один `FarmsPageEventLoadFarms()` — после создания одного
   места список перезагружается минимум дважды.

### Альтернативные потоки

- Несколько новых мест сохраняются за один тап «Сохранить структуру» (весь
  дефолтный набор при первой настройке, либо дефолтные + добавленные вручную)
  → на каждое место отдельно диспатчится свой `FarmsPageEventAddPlace`,
  никакой батч-вставки нет; частичный сбой одного вызова не откатывает уже
  вставленные места (сейчас неактуально практически, см. находку про
  проглоченное исключение ниже).
- `existingPlaces` не пуст на момент открытия экрана (ручной вход) →
  дефолтный набор не предлагается вовсе, доступно только ручное добавление
  через `addCustomPlace`.
- Место с пустым (после `trim()`) именем никогда не попадает в
  `getPlacesToSave()` — не диспатчит `FarmsPageEventAddPlace`, не создаётся в
  БД.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — создаваемая сущность
  этого сценария.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — родитель по `farmId`
  (значение — `Farm.remoteId` фермы, передаваемое в
  `PlaceCreatePageArguments.farmId`); этим сценарием не изменяется, только
  читается/передаётся дальше.

### Бизнес-правила

- Стандартный набор из пяти названий мест предлагается **только** когда
  `existingPlaces` пуст в момент создания `PlaceCreateCubit` (первая настройка
  структуры) — при уже существующих местах на ферме автопредложение не
  срабатывает повторно.
- Принадлежность имени к дефолтному набору определяется точным строковым
  совпадением с элементом `defaultPlaceNames`
  (`PlaceCreateCubit.isDefaultPlace`), а не отдельным флагом/типом на
  `Place` — переименование дефолтного места в UI недоступно вовсе (не просто
  «не рекомендуется»).
- Новое место всегда вставляется уже с `needUpdate: true`, выставленным на
  уровне кубита при создании in-memory объекта, а не проставляется отдельно
  после вставки в БД.
- `description` (площадь) — единственное поле дефолтного места, доступное для
  редактирования в этом сценарии; свободный ввод, ограничен только
  `NumberInputFormatter` и `maxLength: 5` в UI.
- Место с пустым именем отфильтровывается на уровне
  `PlaceCreateCubit.getPlacesToSave` — фильтрация происходит в кубите, до
  диспатча событий в `FarmsAndPlacesBloc`, а не внутри самого блока или
  репозитория.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и работает как описано в CURRENT;
находки, перечисленные в «Открытые вопросы и ограничения», не блокируют его
выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/routes.dart` | `Routes.createPlace` | CURRENT | маршрут экрана создания/редактирования структуры мест |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage._onSuccess` | CURRENT | переход к созданию мест сразу после успешного сохранения новой фермы, `existingPlaces: []` |
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton.build` | CURRENT | ручной вход «Структура фермы» в любой момент, `existingPlaces` = текущие места фермы |
| `lib/pages/place/place_page.dart` | `_PlacePageBodyState.build` | CURRENT | альтернативный ручной вход — ссылка «указать площадь» на экране конкретного места |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePage.build` | CURRENT | создаёт `PlaceCreateCubit` с жёстко заданным `defaultPlaceNames` (5 локализованных названий) |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `_PlacesList.build` | CURRENT | кнопка «Сохранить структуру»: диспатчит `FarmsPageEventAddPlace`/`EditPlace`/`DeletePlace` по каждому месту, затем `context.pop()` без ожидания результата |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit._initializePlaces` | CURRENT | автосоздание дефолтных мест в памяти, только если `existingPlaces` пуст |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.addCustomPlace` | CURRENT | ручное добавление пустого места в конец списка |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.getPlacesToSave` | CURRENT | фильтрует места с пустым именем перед сохранением |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventAddPlace` | CURRENT | событие блока, несущее создаваемый `Place` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onAddPlace` | CURRENT | вызывает `PlaceRepository.insertPlaceWithNegativeRemoteId`, безусловно перезагружает список |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.insertPlaceWithNegativeRemoteId` | CURRENT | эффект EVT-15 — локальная вставка + простановка отрицательного `idRemote`; собственный try/catch проглатывает исключения |
| `packages/sheep_farm_database/lib/entities/place/places_dao.dart` | `PlacesDao.insertPlaceReturning`, `PlacesDao.setPlaceNegativeRemoteId` | CURRENT | insert + `UPDATE ... SET id_remote = -id` на уровне Drift DAO |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель, `id` — autoincrement, `idRemote` — nullable |
| `lib/l10n/app_ru.arb` | `general_herd`, `adult_animals`, `young_animals`, `nursery`, `quarantine`, `farm_departments`, `add_plus`, `save_structure`, `square_meters` | CURRENT | локализованные строки экрана и дефолтного набора названий |

## Критерии приёмки

- Пользователь может создать отделение фермы двумя путями: (а) приняв
  предложенный набор из пяти дефолтных названий при первой настройке
  структуры только что созданной фермы (`existingPlaces` пуст на момент
  открытия), (б) добавив произвольное место вручную в любой момент через
  «Структура фермы» или экран конкретного места.
- Каждое место с непустым (после `trim()`) именем и без `idRemote` при
  нажатии «Сохранить структуру» порождает ровно одно событие
  `FarmsPageEventAddPlace`.
- На каждое такое событие `FarmsAndPlacesBloc._onAddPlace` ровно один раз
  вызывает `PlaceRepository.insertPlaceWithNegativeRemoteId`, без сетевого
  запроса.
- После вставки запись в таблице `Places` имеет `idRemote == -id` (значение,
  обратное собственному локальному `id`) — место считается
  несинхронизированным.
- Место с пустым именем не порождает `FarmsPageEventAddPlace` и не создаёт
  запись в `Places`.
- Дефолтный набор названий предлагается только когда `existingPlaces` пуст в
  момент создания `PlaceCreateCubit`; при непустом списке автопредложение не
  происходит, а имена уже существующих дефолтных мест остаются
  нередактируемыми в UI.

## Связанные тесты

- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit — инициализация'`, test `'existingPlaces пуст -> автосоздание дефолтных мест из defaultPlaceNames'` — дефолтный набор при первой настройке (будет переименовано, не трогать сейчас).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit — редактирование'`, test `'addCustomPlace добавляет новое пустое место в конец списка'` — ручное добавление (будет переименовано, не трогать сейчас).
- `test/pages/place_create_cubit_test.dart`, group `'PlaceCreateCubit — getPlacesToSave/getPlacesToDelete'`, test `'getPlacesToSave отфильтровывает места с пустым именем'` — фильтрация перед сохранением (будет переименовано, не трогать сейчас).
- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-7 — FarmsAndPlacesBloc._onAddPlace'`, test `'успех -> insertPlaceWithNegativeRemoteId вызван, список перезагружен'` — сам эффект EVT-15 на уровне блока, через мок репозитория (будет переименовано, не трогать сейчас).
- TBD — теста нет на уровне `PlaceRepository`/`PlacesDao` против реальной (in-memory) БД: ни один существующий тест не проверяет конкретное значение `idRemote == -id` после вставки — только вызов мока `insertPlaceWithNegativeRemoteId` через `verify(...).called(1)`.

## Открытые вопросы и ограничения

- **Собственный try/catch в `FarmsAndPlacesBloc._onAddPlace` — недостижимая
  ветвь для этого вызова.** `PlaceRepository.insertPlaceWithNegativeRemoteId`
  сама оборачивает оба вызова DAO в `try/catch` и только логирует исключение
  (`log('insertPlaceWithNegativeRemoteId: Exception $e')`), никогда не
  перебрасывая его дальше и не возвращая признак неудачи (`Future<void>`).
  Внешний `catch` в `_onAddPlace`, эмитящий `FarmsPageError('Ошибка создания
  места: ...')`, из-за этого не может сработать на ошибке именно этого
  вызова — сценарий CREATE_ERROR для этого пути в реальности недостижим,
  несмотря на то что для него уже написан тест
  (`test/pages/farms_and_places_bloc_test.dart`, group `'UC-8 — …ERROR'`),
  который проверяет только явно замоканный `thenThrow` на уровне мока
  репозитория, а не реальное поведение `PlaceRepository`.
- **Двойная перезагрузка списка.** `_onAddPlace` явно диспатчит
  `FarmsPageEventLoadFarms()` после вставки, и одновременно подписка на
  `PlaceRepository.watchAll()` в конструкторе блока делает то же самое при
  изменении таблицы `Places` — после создания одного места
  `FarmsAndPlacesBloc._onLoadFarms` выполняется минимум дважды подряд.
  Функционально безвредно, но лишняя работа.
- **Пакетное сохранение не атомарно.** Если пользователь сохраняет несколько
  новых мест за один тап (дефолтный набор из первой настройки, либо
  дефолты + добавленные вручную), каждое из них — отдельный вызов
  `insertPlaceWithNegativeRemoteId`, без общей транзакции; частичный сбой
  середины цикла не откатывает уже вставленные места (на практике не
  проявляется — см. первую находку про проглоченное исключение).
- Дальнейшая отправка этого места на сервер — отдельное событие
  ([EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md),
  `place.create_synced`) и отдельный use-case, не описанный здесь; тестов на
  уровне `data_update_bloc.dart` для этого пути пока нет (TBD — теста нет).
