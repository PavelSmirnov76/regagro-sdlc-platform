# UC-135 — Пользователь публикует объявление на доске — успех

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Авторизованный пользователь ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md))
проходит визард создания объявления (`BoardAdCreatePage`/`BoardAdCreateBloc`,
не-edit режим) и на последнем шаге подтверждает публикацию. Обработчик
`BoardAdCreateBloc._onCreateAd` собирает форму в параметры вызова
`AdRepository.createAd`, который отправляет один multipart `POST
{boardServiceApi}/ads` и, получив от сервера `status == "1"`, завершается без
исключения. Happy-path сценарий события
[EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md) (`ad.published`). Модуль
полностью online-only ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) — успешно
созданное объявление нигде не кэшируется локально; единственный
наблюдаемый пользователем эффект успеха — закрытие визарда и обновление
серверного списка объявлений на предыдущем экране.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Доступ к самому экрану визарда гейтится на уровне маршрута, а не внутри
`BoardAdCreateBloc`: маршрут `Routes.boardAdCreate` (`lib/pages/routes.dart`)
объявлен с `redirect: (context, state) { if
(!AppCacheService.isAuthorized()) return Routes.profile; return null; }` —
неавторизованный пользователь перенаправляется на профиль ещё до построения
`BoardAdCreatePage`, ни один обработчик визарда/репозитория не выполняет
собственную проверку авторизации. Проверка опирается на кэшированный флаг
`AppCacheService.isAuthorized()` (`lib/data/services/app_cache_service.dart`),
который `AuthRepository` синхронизирует с реальным состоянием токена при
каждом логине/логауте (`AppCacheService.setAuthorizedFlag(isAuthorized())`,
`lib/repositories/auth/auth_repository.dart`), а не напрямую
`AuthRepository.isAuthorized()` — см. «Открытые вопросы». Ни
`BoardAdCreateBloc`, ни `AdRepository.createAd` не читают текущего
пользователя вообще — авторизация запроса на сервере выполняется только
заголовком `Authorization`, который `CustomDioClient.call` подставляет из
`AuthInterceptor` независимо от этого модуля.

## CURRENT

### Основной поток

1. Пользователь открывает визард одним из двух реально существующих входов,
   оба — без аргумента `ad` (создание, не редактирование):
   - плавающая кнопка «+» на ленте объявлений (`BoardView`,
     `lib/pages/board/presentation/widgets/board_view.dart`) →
     `context.pushNamed<bool?>(Routes.boardAdCreate)`;
   - плавающая кнопка «+» на экране «Мои объявления» (`MyAdsView`,
     `lib/pages/my_ads/presentation/my_ads_view.dart`) →
     `context.pushNamed2<bool?>(Routes.boardAdCreate)`.
   Третий вызывающий код в том же файле, `MyAdsView._editAd`, передаёт
   `BoardAdCreatePageArguments(ad: ad)` — это режим редактирования
   ([EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md)), не входит в этот
   use-case (см. «Альтернативные потоки»).
2. `BoardAdCreatePage.build` читает `args = tryGetExtraByName<BoardAdCreatePageArguments?>(...)`
   (здесь всегда `null`) и создаёт `BoardAdCreateBloc()..add(BoardAdCreateEventStart(editingAd: args?.ad))` —
   `editingAd == null`, поэтому `BoardAdCreateData` остаётся в дефолтном,
   не-edit состоянии (`editingAdId == null` → `isEditMode == false`).
3. `BoardAdCreateBloc.on<BoardAdCreateEventStart>` (`_onStart`) загружает
   справочники, нужные шагам визарда: `CountriesRepository.getAll()`,
   `BoardAdTypesRepository.getAll()` (сужается до `Constants.boardAdTypeIds =
   [3, 1]` — только эти два типа реально предлагаются на шаге выбора типа,
   см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), `KindsRepository.getAllKindWithDetailsByFilters()`,
   и для каждой не удалённой локальной фермы (`FarmRepository.getAll()`, `isDeleted
   != true`) — её места вместе с животными
   (`PlaceRepository.getAllWithThisFarmIdWithAnimals(farm.remoteId!)`,
   тип `PlaceWithAnimals { place, animals: List<AnimalWithDetails> }`,
   `lib/pages/farms_and_places/farms_page_bloc.dart`). Страна по умолчанию для
   адреса/телефона — `RU`, если есть в списке, иначе первая из загруженных.
4. Пользователь последовательно проходит шаги, состав которых определяет
   `BoardAdCreateData.currentSteps`/`_stepsAfterTypeSelected()` по выбранному
   `selectedAdTypeId`/`saleMode`/`isAddingNewAnimal` — `type` → (для
   `adTypeId == 1`, продажа животного) `animalCount` → `selectPlace` → ветка
   `selectAnimal` (существующее зарегистрированное животное) **или**
   `newPetKind`/`newPetGender`/`newPetBreed`/`newPetSuit`/`newPetBirthDate`
   (животное без регистрации, вводится вручную только для этого объявления)
   **или**, при множественной продаже, `multipleSaleAnimal`/
   `multipleSaleAnimalsList` — затем, для любого типа объявления, `description`
   → `address` → `contacts` → `preview`. `TabBarView` этих шагов построен с
   `physics: const NeverScrollableScrollPhysics()` (`board_ad_create_page.dart`) —
   свайп между шагами невозможен, единственный путь вперёд — кнопка «Далее»
   (`_BoardAdCreateNextButtonFooter`), у которой `enabled: state.data.stepSuccessFor(currentStep)
   == true`; таким образом каждый пройденный шаг гарантированно валиден на
   момент перехода к следующему.
5. На шаге `preview` (`BoardAdPreviewStepPage`) кнопка
   `BlackCircleButton(title: context.tr('board_ad_publish'), isLoading:
   state.data.onSending, onTap: () => bloc.add(const
   BoardAdCreateEventCreateAd()))` — видна всегда (в отличие от шагов выше, у
   этого шага нет отдельной футер-кнопки «Далее», сам этот виджет и есть
   действие последнего шага); `BlackCircleButton.onTap` переключается на
   `() {}` пока `isLoading == true` (`lib/widgets/button/button.dart`),
   так что повторные нажатия после того, как первое достигло UI, — no-op.
6. `BoardAdCreateBloc.on<BoardAdCreateEventCreateAd>` (`_onCreateAd`):
   - защитный ранний выход: `if (_data.onSending ||
     !_data.contactsStepSuccess || !_data.addressStepSuccess ||
     !_data.descriptionStepSuccess) return;` — при нормальном прохождении
     визарда (шаг 4) все три флага уже гарантированно `true` к моменту
     показа `preview`, так что этот выход — защитный дубль, а не
     содержательная ветка (см. «Открытые вопросы»);
   - `if (adTypeId == null) return;` — недостижимо после прохождения шага
     `type`;
   - список животных объявления строится по `adTypeId` (`_data.selectedAnimals`/`_data.animalData`/`_data.isAddingNewAnimal`
     — см. «Альтернативные потоки» для точных веток по `adTypeId ∈ {1, 5,
     6}`; для любого другого `adTypeId` (на практике — только `3`,
     единственный другой реально выбираемый тип) список остаётся `[]`, ни
     одна из трёх веток `if`/`else if` не совпадает);
   - `_data = _data.copyWith(onSending: true); emit(BoardAdCreateSuccess(_data));` —
     фиксирует состояние загрузки прежде, чем что-либо асинхронное начнётся;
   - `localFiles` — те элементы `_data.localPhotoPaths`, что не являются
     `http`/`https`-путём (`_isRemoteFilePath`) — в режиме создания это
     **все** выбранные фото объявления, поскольку объявления ещё не
     существует и никакие пути не могли прийти с сервера;
     `retainedFilesPaths` — обратный фильтр, в режиме создания **всегда
     пуст** (используется только веткой `isEditMode`, см. «Альтернативные
     потоки»);
   - `price`/`phone`/`address`/`whenWasFound` — обрезаются `.trim()`;
     `phone`/`address` передаются как `null`, если после обрезки пусты;
     `whenWasFoundText` передаётся непустым только при `adTypeId == 6`
     (недостижимо из визарда создания, см. «Открытые вопросы» /
     [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) — на практике при создании
     всегда `null`;
   - вызывается `await _adRepository.createAd(title: _data.title.trim(),
     price: price, description: _data.description.trim(), files:
     localFiles.map((e) => File(e)).toList(), adTypeId: adTypeId, statusId:
     1, phone: ..., address: ..., whenWasFoundText: ..., animals: animals)` —
     `statusId` жёстко закодирован как `1` в режиме создания (в отличие от
     `updateAd`, где используется `_data.statusId ?? 1`); `serviceTypeId` не
     передаётся вовсе (остаётся `null` внутри `createAd`) — визард не даёт
     пользователю выбрать его ни на одном шаге
     ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)).
7. Внутри `AdRepository.createAd`:
   - для `files` и, для каждого элемента `animals`, для его
     `localPhotoPaths` — `_multipartFilesFromPaths` строит `MultipartFile`
     только для путей, чей `File(path).exists()` возвращает `true` на
     момент вызова; несуществующий локальный файл молча выпадает из
     запроса, без ошибки/предупреждения (см. «Открытые вопросы»);
   - `availableAttributes = await boardAttributesRepository.getAll()` —
     локальный, ранее синхронизированный справочник `board_attributes`
     (Drift, `BaseRepository.getAll()`);
   - `AdCreateRequest.fromData(...)` строит список
     `List<BoardAttributeWithValue> attributes`: для каждого непустого из
     `price`/`phone`/`address`/`whenWasFoundText` вызывается `addAttr(name,
     value)`, которая ищет в `availableAttributes` запись с точным
     совпадением `a.name == name` (имена `'price'`, `'phone'`, `'address'`,
     `'when_was_found'`) — если справочник такую запись не содержит,
     соответствующий атрибут в запрос **не попадает вовсе**, без ошибки (см.
     «Открытые вопросы» — этот способ резолва по имени независим от
     захардкоженных числовых `attribute_id` (`9`/`10`/`12`/`13`), которыми
     тот же самый атрибут распознаётся при чтении объявления,
     [ENT-18](../entities/ENT-18-AD-IN-BOARD.md));
   - `adCreateRequest.toJson()` формирует тело: `title`, `description`,
     `files[]` (список `MultipartFile` фото объявления), `ad_type_id`,
     `status_id`, `attributes` (список `{attribute_id, name, type: 'string',
     entity_type, value}` — `BoardAttributeWithValue.toJson()`,
     `packages/sheep_farm_database/lib/entities/board/board_attributes.dart`),
     `animals` — список `AdAnimalModel.toJson()` (`animal_id`, `guid`,
     `kind_id`, `name`, `breed_id`, `suit_id`, `gender_id`, `birth_date`,
     `is_gender_unknown`, `price`, `filesPaths`, `files` — вложенная `Map`
     индекс→`MultipartFile` для фото конкретного животного) **если непуст**,
     либо буквально строка `''` (не пустой список, не отсутствующий ключ),
     если `animals.isEmpty`;
   - `ApiMessage(link: '${Constants.boardServiceApi}/ads', method:
     ApiMethod.post, data: adCreateRequest.toJson(), isMultipartFormData:
     true)` передаётся в `rpcClient.call` (`getIt.get<ApiClient>(instanceName:
     'farm_rpc')`);
   - `CustomDioClient.call`: `isMultipartFormData == true` →
     `FormData.fromMap(message.data)` — `dio`'s `encodeMap` рекурсивно
     разворачивает вложенные `Map`/`List` в multipart-поля с
     bracket-нотацией (`animals[0][kind_id]`, `attributes[0][value]`,
     `files[]` и т.д.), `MultipartFile`-значения становятся файловыми
     частями, остальное — текстовыми полями формы (`dio-5.9.0`,
     `lib/src/form_data.dart`, `FormData._init`/`encodeMap`);
   - ответ сервера — обычный HTTP-успех, тело которого (ожидаемо содержащее
     созданный объект под ключом `data`) заставляет
     `CustomDioClient.call` установить `response.data['status'] = "1"`
     безусловно (условие — тело содержит ключ `data` **или**
     `animal_exits`); если бы тело не содержало ни того, ни другого и не
     было явным `{'status': 'error', ...}`, ответ всё равно обёрнут в
     `{"data": response.data, "status": "1"}` — то есть любой не
     `status: 'error'` HTTP-успех для этого эндпоинта трактуется как успех.
8. `AdRepository.createAd` видит `response['status'] == "1"` → `return;` —
   без исключения, без какого-либо возвращаемого значения (созданный на
   сервере id объявления нигде не читается и не сохраняется).
9. Обратно в `_onCreateAd`: без исключения — `_data =
   _data.copyWith(onSending: false); emit(BoardAdCreateSuccess(_data,
   popRoute: true));`.
10. `BoardAdCreatePage`'s `BlocConsumer.listener`: `state.popRoute == true` →
    `context.pop(true)` — закрывает весь визард, возвращая `true` вызвавшему
    `context.pushNamed`/`pushNamed2`. `BoardView`/`MyAdsView` (шаг 1) видят
    `published == true`/`updated == true` → `await
    context.read<BoardCubit>().refresh()` — перезапрашивают ленту у сервера;
    само созданное объявление нигде локально не собирается и не
    подставляется напрямую — оно появится в списке только через этот
    повторный `getAds`/`getMyAds`.

### Альтернативные потоки

- **`adTypeId == 1` (продажа животного/животных), выбрано уже
  зарегистрированное животное** (`_data.selectedAnimals` непуст,
  `selectAnimal`/`multipleSaleAnimal`-шаги): `animals =
  _data.selectedAnimals` — снимок (`AdAnimalModel`, поля `animal_id`/`guid`
  скопированы из `AnimalWithDetails` на момент выбора), само животное
  ([ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)) не читается повторно и
  не изменяется этим сценарием.
- **`adTypeId == 1`, `isAddingNewAnimal == true` (одиночная продажа, животное
  без регистрации)**: `_data.selectedAnimals` пуст → `animals =
  [_data.animalData]` — введённые вручную на шагах `newPetKind`…
  `newPetBirthDate` вид/порода/масть/пол/дата рождения, без связи с каким-либо
  `Animal` в БД.
- **`adTypeId == 1`, множественная продажа**: `animals =
  _data.selectedAnimals` — список, накопленный шагами
  `multipleSaleAnimal`/`multipleSaleAnimalsList` (каждый элемент — своя цена
  и свои фото).
- **`adTypeId == 5`** («пропажа» — недостижим из визарда создания,
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)): та же ветка, что и `adTypeId
  == 1`, но при пустом `_data.selectedAnimals` подставляется
  `[_data.animalData]` безусловно, независимо от `isAddingNewAnimal`.
- **`adTypeId == 6`** («найдено» — тоже недостижим из визарда создания):
  `animals = [_data.animalData]` безусловно.
- **`adTypeId == 3` (услуга) — единственный другой реально выбираемый на
  шаге `type` тип** (`Constants.boardAdTypeIds = [3, 1]`): не совпадает ни с
  одним условием построения `animals`, список остаётся `[]`; шаги
  `animalCount`/`selectPlace`/`selectAnimal`/`newPet*`/`multipleSaleAnimal*`
  отсутствуют в `currentSteps` для этой ветки — визард идёт `type` →
  `description` → `address` → `contacts` → `preview` напрямую.
- **Ни одной фотографии объявления не выбрано**: `localPhotoPaths` пуст →
  `files: []` → пустой `files[]` в теле запроса — не блокирует публикацию,
  ни один шаг визарда не требует хотя бы одного фото объявления как условия
  `descriptionStepSuccess`/`addressStepSuccess`/`contactsStepSuccess`.
- **Режим редактирования (`_data.isEditMode == true`, `editingAd != null`)** —
  другая ветка того же обработчика `_onCreateAd` (`if (_data.isEditMode) {
  await _adRepository.updateAd(...) } else { ... }`), вызывает `updateAd`, не
  `createAd`; отдельное событие
  ([EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md)), не входит в этот
  use-case.
- **Публикация отказывает** (`createAd` бросает исключение — сетевая ошибка
  либо `response['status'] != "1"`, то есть явный `Exception(response['message'])`
  из `AdRepository.createAd`): другая ветка того же `_onCreateAd`
  (`catch (e, st) { ...; emit(BoardAdCreateSuccess(_data.copyWith(onSending:
  false))); }`) — тот же тип состояния `BoardAdCreateSuccess`, `popRoute`
  остаётся `false` по умолчанию, форма не сбрасывается и не показывает
  никакого явного сообщения об ошибке внутри состояния. Не входит в этот
  use-case (`CREATE_ERROR`, отдельный файл).

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, совершающая
  переход: создаётся на сервере этим сценарием; клиент никогда не читает и
  не хранит результат (ни присвоенный id, ни сам объект) — единственный
  канал, которым созданное объявление становится видимым, — последующий
  `BoardCubit.refresh()` → обычный `GET /ads`.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  только читается: список стран для выбора страны адреса/телефона
  (`_data.addressCountry`/`phoneCountry`), с дефолтом `RU`.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (вид/порода/масть,
  HANDBOOKS) — только читается: заполняет шаги `newPetKind`/`newPetBreed`/`newPetSuit`
  и фильтрует список животных на шаге выбора существующего животного; ничем
  из этого сценарий не изменяет.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только читается:
  `FarmRepository.getAll()` в `_onStart`, источник ферм для загрузки их мест.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — только
  читается: `PlaceRepository.getAllWithThisFarmIdWithAnimals` — места с их
  животными, источник для шага `selectPlace`/`selectAnimal`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) — только
  читается (через `PlaceWithAnimals.animals: List<AnimalWithDetails>`): даёт
  пользователю выбрать уже зарегистрированное животное для продажи; выбор
  превращается в одноразовый снимок `AdAnimalModel`, само `Animal` не
  изменяется и повторно не читается при публикации.

### Бизнес-правила

- `statusId` нового объявления всегда `1` — жёстко закодировано в
  не-edit ветке `_onCreateAd`, не зависит от каких-либо данных формы.
- `serviceTypeId` никогда не передаётся из визарда создания — ни один шаг не
  даёт его выбрать (см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)).
- `retainedFilesPaths` (уже загруженные на сервер фото) в режиме создания
  всегда пуст — это поле осмысленно только для `updateAd`.
- Генерик-атрибуты (`price`/`phone`/`address`/`when_was_found`) резолвятся
  во время создания запроса по точному совпадению строкового `name` в
  локальном справочнике `board_attributes`, а не по захардкоженному
  числовому `attribute_id`, которым тот же атрибут распознаётся при чтении
  объявления ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) — если справочник
  ещё не синхронизирован или не содержит нужного имени, соответствующее
  значение молча не попадает в запрос, без ошибки.
- `AdCreateRequest.toJson()` кодирует полностью пустой список животных как
  строку `''`, а не как пустой список/отсутствующий ключ — единственная
  такая асимметрия среди полей запроса.
- Ни один локальный файл фотографии, отсутствующий на диске на момент
  публикации, не приводит к ошибке — `_multipartFilesFromPaths` молча
  пропускает такие пути (`if (await file.exists())`).
- `createAd` не возвращает и не сохраняет id, присвоенный сервером новому
  объявлению — единственный способ увидеть созданное объявление клиенту:
  последующий `refresh()` списка через обычный `GET /ads`.
- Успешная публикация не создаёт и не изменяет ни одной строки в локальной
  БД — весь модуль online-only ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (не-edit ветка `_onCreateAd` → `AdRepository.createAd` →
успешный multipart `POST /ads`) полностью реализован и подтверждён и
bloc-уровневым, и repository-уровневым тестом (см. «Связанные тесты»);
находки, перечисленные в «Открытые вопросы и ограничения», не блокируют его
выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_view.dart` | кнопка «+» (`onTap` → `Routes.boardAdCreate`) | CURRENT | вход №1 — создание, без `BoardAdCreatePageArguments` |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | кнопка «+» (`onTap` → `Routes.boardAdCreate`) | CURRENT | вход №2 — создание; `_editAd` в том же файле — режим редактирования, вне этого use-case |
| `lib/pages/routes.dart` | маршрут `Routes.boardAdCreate`, `redirect` | CURRENT | гейт доступа — неавторизованный пользователь перенаправляется на `Routes.profile` через `AppCacheService.isAuthorized()` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized`, `.setAuthorizedFlag` | CURRENT | кэшированный флаг авторизации, читаемый гейтом маршрута |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | источник истины для флага (синхронизируется при логине/логауте, не читается этим модулем напрямую) |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `BoardAdCreatePageArguments`, `_BoardAdCreatePageState.build` | CURRENT | создаёт `BoardAdCreateBloc`, диспатчит `BoardAdCreateEventStart(editingAd: args?.ad)`; `BlocConsumer.listener` реагирует на `popRoute` (`context.pop(true)`) |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `TabBarView` (`physics: NeverScrollableScrollPhysics`), `_BoardAdCreateNextButtonFooter` | CURRENT | шаги визарда проходятся только вперёд, кнопка «Далее» гейтится `BoardAdCreateData.stepSuccessFor` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventStart>` (`_onStart`) | CURRENT | грузит страны/типы объявлений/фермы+места+животных/таксономию |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateData.currentSteps`, `._stepsAfterTypeSelected` | CURRENT | состав шагов визарда по `selectedAdTypeId`/`saleMode`/`isAddingNewAnimal` |
| `lib/pages/board_ad_create/presentation/steps/board_ad_preview_step_page.dart` | `BoardAdPreviewStepPage` | CURRENT | финальный шаг — кнопка публикации, диспатчит `BoardAdCreateEventCreateAd` |
| `lib/widgets/button/button.dart` | `BlackCircleButton.onTap` (`!isLoading ? onTap : () {}`) | CURRENT | повторные нажатия после того, как `onSending:true` достиг UI, — no-op |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventCreateAd>` (`_onCreateAd`), не-edit ветка | CURRENT | ядро сценария — построение `animals`, обрезка полей, вызов `AdRepository.createAd`, `emit(..., popRoute: true)` |
| `lib/models/board/ad_animal_model.dart` | `AdAnimalModel.toJson`, `.copyWith` | CURRENT | шейп payload'а животного объявления, вложенные `files` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.createAd` | CURRENT | сборка `MultipartFile`, резолв атрибутов по имени, multipart `POST /ads`, проверка `response['status'] == "1"` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository._multipartFilesFromPaths` | CURRENT | конвертация путей в `MultipartFile`, молча пропускает несуществующие файлы |
| `lib/models/board/ad_create_request.dart` | `AdCreateRequest.fromData`, `.toJson` | CURRENT | резолв генерик-атрибутов по имени, сериализация тела (в т.ч. `animals: ''` при пустом списке) |
| `packages/sheep_farm_database/lib/entities/board/board_attributes.dart` | `BoardAttributeWithValue.toJson` | CURRENT | wire-формат одного генерик-атрибута |
| `lib/repositories/board/board_attributes_repository.dart` | `BoardAttributesRepository.getAll` (наследован от `BaseRepository`) | CURRENT | источник локального справочника атрибутов, используемого для резолва по имени |
| `lib/network/api_client/api_message.dart` | `ApiMessage.isMultipartFormData` | CURRENT | флаг, включающий `FormData.fromMap` в `CustomDioClient.call` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | оборачивает данные в `FormData.fromMap`, нормализует `response['status']` на `"1"` для любого не-`error` HTTP-успеха |
| `/Users/pavelsmirnov/.pub-cache/hosted/pub.dev/dio-5.9.0/lib/src/form_data.dart` | `FormData._init`/`encodeMap` | CURRENT (внешний пакет `dio`) | рекурсивно разворачивает вложенные `Map`/`List` в multipart-поля с bracket-нотацией |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `PlaceWithAnimals` | CURRENT | связка `Place` + его `List<AnimalWithDetails>`, источник шага выбора животного |
| `lib/pages/board/presentation/widgets/board_view.dart`, `lib/pages/my_ads/presentation/my_ads_view.dart` | обработчик результата `pushNamed`/`pushNamed2` (`published == true` → `BoardCubit.refresh()`) | CURRENT | единственный способ увидеть созданное объявление — повторный `GET /ads` |

## Критерии приёмки

- По нажатию кнопки публикации на шаге `preview` (не-edit режим), при
  `_data.contactsStepSuccess && _data.addressStepSuccess &&
  _data.descriptionStepSuccess && !_data.onSending && _data.selectedAdTypeId
  != null`, выполняется ровно один вызов `AdRepository.createAd` с
  `title`/`description`, обрезанными пробелами, `statusId == 1`,
  `phone`/`address`, равными `null` при пустой строке после обрезки, и
  `animals`, построенным по ветке `adTypeId` (см. «Альтернативные потоки»).
- `AdRepository.createAd` выполняет ровно один multipart-вызов методом
  `POST` на адрес, содержащий `/ads`; если ответ сервера — `Map` с
  `status == "1"` (гарантированно при наличии ключа `data`/`animal_exits`,
  либо по умолчанию для любого HTTP-успеха без явного
  `status: 'error'`), `createAd` возвращает управление без исключения.
- После успешного `createAd` бы emit'ится ровно один
  `BoardAdCreateSuccess(_data, popRoute: true)` с `onSending == false`, без
  какого-либо состояния ошибки.
- `BoardAdCreatePage` закрывает визард (`context.pop(true)`) исключительно в
  ответ на `popRoute == true`; вызвавший экран (`BoardView`/`MyAdsView`)
  реагирует на `true` вызовом `BoardCubit.refresh()`.
- Ни `BoardAdCreateBloc`, ни `AdRepository.createAd` не производят ни одной
  записи в локальную БД в рамках этого сценария.

## Связанные тесты

- `test/pages/board_ad_create_bloc_test.dart`, group `'UC-135 —
  BoardAdCreateBloc._onCreateAd (создание)'` — тест `'успех -> createAd
  вызван, popRoute:true'`: собирает `BoardAdCreateBloc` через `buildFilledBloc()`
  (заполняет форму до валидного состояния с `adTypeId: 2` — тестовое
  значение вне `Constants.boardAdTypeIds`, упражняющее ту же «базовую» ветку
  построения `animals`/шагов, что и реально выбираемый на практике `adTypeId
  == 3`), мокает `adRepository.createAd(...)` успехом, дожидается состояния
  `BoardAdCreateSuccess` с `popRoute == true` и проверяет `verify(...)
  .called(1)` с `title: 'Заголовок'`, `description: 'Описание'`, `adTypeId:
  2`, `statusId: 1` (остальные именованные параметры — `any(named: ...)`, не
  проверяются поэлементно).
- `test/repositories/ad_repository_test.dart`, group `'UC-135 —
  AdRepository.createAd'` — тест `'успех -> POST /ads со статусом "1" не
  бросает исключение'`: мокает `farmRpcClient.call(any())` ответом
  `{'status': '1'}`, вызывает `repository.createAd(title: 'Продам овцу',
  description: 'Описание', files: const [], adTypeId: 1, statusId: 1)`,
  проверяет `completes`, затем через `captureAny()` проверяет, что
  отправленный `ApiMessage.method == ApiMethod.post` и `ApiMessage.link`
  содержит `/ads` — не проверяет содержимое `message.data`
  (атрибуты/животные/файлы), см. «TBD» ниже.
- Обе группы всё ещё называются по старой схеме нумерации (`UC-135`) на
  момент написания этой спеки — переименование под `UC-135` выполняется
  отдельным контролируемым проходом, не этой задачей; якорь `grep -r
  "UC-135" test/` заработает только после него.
- Соседняя группа `'UC-136 — BoardAdCreateBloc._onCreateAd ERROR (известный
  дефект — без сообщения об ошибке)'` (тот же bloc-тест-файл) и группа
  `'UC-136 — AdRepository.createAd ERROR'` (тот же repository-тест-файл) в
  этот use-case не входят — покрывают ветку `CREATE_ERROR` (сетевое
  исключение / `response['status'] != "1"`), отдельный файл.
- **TBD — теста нет** на реальное построение `animals` для `adTypeId == 1`
  (ни с выбранным существующим животным, ни с `isAddingNewAnimal`, ни при
  множественной продаже) внутри `_onCreateAd` — единственный дошедший до
  `CreateAd` bloc-тест использует `adTypeId: 2` с пустым списком животных.
- **TBD — теста нет** на точную форму `message.data`, отправляемую
  `AdRepository.createAd` — состав `attributes` (резолв по имени),
  сериализацию `animals` как `''` при пустом списке, вложенные `files` по
  индексу для фото животного; repository-тест проверяет только
  `method`/`link` захваченного `ApiMessage`.
- **TBD — теста нет** на пропуск несуществующего локального файла фото в
  `_multipartFilesFromPaths` (`if (await file.exists())`).

## Открытые вопросы и ограничения

- **Гейт маршрута читает кэшированный флаг, а не живой токен.** `redirect`
  маршрута `Routes.boardAdCreate` проверяет `AppCacheService.isAuthorized()` —
  булев флаг в `SharedPreferences`, который `AuthRepository` обязан
  синхронизировать при каждом изменении авторизации
  (`setAuthorizedFlag(isAuthorized())`), но который сам визард/репозиторий
  объявлений не перепроверяет. Если эта синхронизация где-либо пропущена
  (не проверено в рамках этого файла), кэшированное значение может разойтись
  с реальным наличием токена; сам факт создания объявления при этом
  по-прежнему зависит только от заголовка `Authorization`, добавляемого
  `AuthInterceptor` независимо от этой проверки. Не разбирается глубже.
- **Резолв генерик-атрибутов по имени (запись) и по числовому id (чтение) —
  два независимых пути к одному и тому же факту.** `AdCreateRequest.fromData`
  ищет атрибут в локальном справочнике по строковому `name`
  (`'price'`/`'phone'`/`'address'`/`'when_was_found'`), тогда как парсинг уже
  существующего объявления ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md))
  распознаёt тот же атрибут по захардкоженному `attribute_id`
  (`9`/`10`/`12`/`13`). Согласованность между этими двумя путями ничем в
  коде не гарантирована — она держится только на том, что сервер
  сопоставляет одни и те же id этим же именам. Не воспроизведено как
  дефект, не разбирается глубже.
- **`animals: ''` вместо пустого списка/отсутствующего ключа.** Единственное
  поле `AdCreateRequest.toJson()`, кодируемое как строка-заглушка при пустом
  состоянии, а не обычным пустым списком — вероятно, осознанный выбор под
  конкретный формат парсинга на бэкенде (multipart не может передать
  буквально пустой JSON-массив как отдельное поле без дополнительных
  условностей), но само это допущение о серверном парсинге этой спекой не
  проверено. Не разбирается глубже.
- **Тройной guard (`onSending`/`contactsStepSuccess`/`addressStepSuccess`/`descriptionStepSuccess`)
  в начале `_onCreateAd` — защитный дубль, не содержательная ветка.** При
  нормальном прохождении визарда (шаг `TabBarView` без свайпа, кнопка
  «Далее» гейтится `stepSuccessFor`) три проверяемых флага уже гарантированно
  `true` к моменту показа `preview` — единственный путь, которым guard мог
  бы сработать содержательно, не найден в рамках чтения этого файла. Не
  разбирается глубже.
- **Возможная гонка двойного нажатия кнопки публикации.** `Bloc.on<E>()` по
  умолчанию использует `flatMap`-транспорт (`bloc-9.2.0`,
  `lib/src/bloc.dart`, `Bloc.transformer`/`_FlatMapStreamTransformer`) —
  события одного типа обрабатываются не строго последовательно, а как
  слитые потоки, без ожидания завершения предыдущего обработчика. Guard
  `_data.onSending` читает поле экземпляра `_data`, устанавливаемое в `true`
  только внутри самого обработчика; UI (`BlackCircleButton.onTap`)
  блокирует повторное нажатие только после того, как `onSending: true`
  дошло до перестроенного виджета — между двумя нажатиями до этого момента
  теоретически возможен повторный вход в `_onCreateAd` и, как следствие,
  дублирующий `POST /ads`. Не воспроизведено тестом (единственный
  `CreateAd`-тест диспатчит событие один раз), не разбирается глубже.
