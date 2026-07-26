# UC-137 — Автор сохраняет правку собственного объявления доски

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Автор объявления открывает собственное объявление на правку с экрана «Мои
объявления» (`MyAdsView`, контекстное меню карточки → «Редактировать») и
проходит тот же визард, что и при создании (`BoardAdCreatePage` +
`BoardAdCreateBloc`), только предзаполненный данными объявления
(`BoardAdCreateData.fromAd`). Подтверждение на последнем шаге визарда
сохраняет правку — multipart `POST /ads/{id}` с `_method: PUT`
(`AdRepository.updateAd`), отличая уже загруженные на сервер фотографии
(URL `http`/`https`) от новых локальных файлов. Happy-path сценарий события
[EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md) (`ad.edited`).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Экран «Мои объявления» показывает только объявления текущего пользователя
(`BoardCubit.load(isMyAds: true)` → `AdRepository.getMyAds` → `userId:
AppCacheService.getUserId()`), поэтому редактируемое объявление всегда
принадлежит открывшему его пользователю. Сам маршрут визарда
(`Routes.boardAdCreate`, используемый и для создания, и для правки) закрыт
`redirect`-проверкой: `if (!AppCacheService.isAuthorized()) return
Routes.profile;` (`lib/pages/routes.dart`) — неавторизованный пользователь
до формы правки физически не долетает.

## CURRENT

### Основной поток

1. `MyAdsView` (`Routes.myAds`) отображает список объявлений текущего
   пользователя; каждая карточка получает `BoardAdContextMenuButton(onEdit:
   () => _editAd(context, ad), onDelete: ...)` (`board_ad_context_menu.dart`)
   — пункт меню `l10n.edit` («Редактировать»).
2. Выбор пункта меню → `MyAdsView._editAd`: `context.pushNamed2<bool?>(
   Routes.boardAdCreate, extra: BoardAdCreatePageArguments(ad: ad))` —
   передаёт уже загруженный объект `Ad` целиком, без дополнительного запроса
   к серверу.
3. `BoardAdCreatePage.build` читает аргумент (`GoRouterState.of(context)
   .tryGetExtraByName<BoardAdCreatePageArguments?>(Routes.boardAdCreate)`) и
   создаёт `BoardAdCreateBloc()..add(BoardAdCreateEventStart(editingAd:
   args?.ad))` — тот же bloc/событие `Start`, что и при создании, отличается
   только непустым `editingAd`.
4. `BoardAdCreateBloc.on<BoardAdCreateEventStart>` (`_onStart`): раз
   `event.editingAd != null`, `_data = BoardAdCreateData.fromAd(editingAd)` —
   заполняет `editingAdId: ad.id`, `statusId: ad.statusId` (сохраняется
   как есть, не хардкодится), `selectedAdTypeId: ad.adTypeId` (без
   ограничения `Constants.boardAdTypeIds`, в отличие от шага выбора типа при
   создании — см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md), «Инварианты»),
   `title`, `description`, `priceDigits: ad.price ?? ''`, `localPhotoPaths:
   ad.files` (существующие URL фотографий), `addressLine: ad.address ?? ''`,
   `phoneNationalNumber: ad.phone ?? ''`, `selectedAnimals: ad.editAnimals`
   (только если `adTypeId` — `1` или `5`, иначе `[]`), `animalData:
   editAnimals.firstOrNull ?? const AdAnimalModel()`, `isAddingNewAnimal:
   false`, `saleMode` (`multiple`, если `adTypeId == 1 && editAnimals.length
   > 1`, иначе `single`), `whenWasFound: ad.whenWasFoundText ?? ''`. Не
   заполняются: `selectedPlace` (остаётся `null`), `addressCountry`/
   `phoneCountry` (остаются `null` — см. «Открытые вопросы»).
5. `_onStart` продолжает как и при создании: грузит `countries`,
   `boardAdTypesRepository.getAll()` (фильтруется до `Constants
   .boardAdTypeIds`, но этот список используется только шагом выбора типа,
   который в edit-режиме не показывается — см. шаг 7), выставляет
   `addressCountry`/`phoneCountry` в `_data.addressCountry ?? ru`/
   `_data.phoneCountry ?? ru` (оба были `null` после `fromAd`, так что оба
   безусловно получают RU/первую страну списка — см. «Открытые вопросы»),
   грузит `kinds`, активные фермы и их места с животными
   (`placesWithAnimals`), эмитит финальный `BoardAdCreateSuccess(_data)`.
6. `BoardAdCreatePage` строит `TabBarView` по `state.data.currentSteps`.
   `BoardAdCreateData.currentSteps`: при `isEditMode == true` (`editingAdId
   != null`) шаги `type` и `animalCount` безусловно исключаются из списка,
   рассчитанного `_stepsAfterTypeSelected()`, — какой бы ни была
   `selectedAdTypeId`.
7. Состав видимых шагов зависит от `adTypeId`/`saleMode` (все — уже
   предзаполненные значениями из шага 4):
   - `adTypeId == 1`, `saleMode == single` (одно животное на продажу, самый
     частый случай) → `[selectPlace, selectAnimal, description, address,
     contacts, preview]`;
   - `adTypeId == 1`, `saleMode == multiple` → `[selectPlace, selectAnimal,
     multipleSaleAnimalsList, multipleSaleAnimal, description, address,
     contacts, preview]`;
   - любой другой `adTypeId` (`3`/`5`/`6`) → `[description, address,
     contacts, preview]` — визард открывается сразу на шаге описания, минуя
     выбор места/животного целиком.
8. Пользователь правит нужные поля на шагах `description`/`address`/
   `contacts` (заголовок, описание, цена/«когда нашлось», фотографии через
   `BoardAdCreateEventAddPhoto`/`RemovePhoto` — они добавляются/удаляются в
   том же смешанном списке `localPhotoPaths`, где уже лежат URL исходных
   фотографий объявления) и доходит до шага `preview`.
9. `BoardAdPreviewStepPage`: кнопка подтверждения показывает `context.tr(
   'save')` вместо `context.tr('board_ad_publish')`, поскольку
   `state.data.isEditMode == true`; по нажатию — `bloc.add(const
   BoardAdCreateEventCreateAd())` (то же событие, что и при создании).
10. `BoardAdCreateBloc._onCreateAd`: те же гейты, что и при создании
    (`onSending`/`contactsStepSuccess`/`addressStepSuccess`/
    `descriptionStepSuccess` — return, если что-то не пройдено); строит
    `animals` по тем же правилам, что и при создании (по `adTypeId`);
    разбирает `_data.localPhotoPaths` на `localFiles` (пути, не начинающиеся
    с `http`/`https`) и `retainedFilesPaths` (URL, уже начинающиеся с
    `http`/`https`) через модульную функцию `_isRemoteFilePath`. Поскольку
    `_data.isEditMode == true`, вызывается:
    ```
    await _adRepository.updateAd(
      id: _data.editingAdId!,
      title: ..., price: ..., description: ...,
      files: localFiles.map((e) => File(e)).toList(),
      filesPaths: retainedFilesPaths,
      adTypeId: adTypeId,
      statusId: _data.statusId ?? 1,
      phone: ..., address: ..., whenWasFoundText: ...,
      animals: animals,
    );
    ```
    (при создании вместо этого безусловно вызывается `createAd` с
    `statusId: 1` литералом).
11. `AdRepository.updateAd`: конвертирует `files` (новые локальные пути) в
    `MultipartFile` через `_multipartFilesFromPaths` (пропускает путь, если
    файл к моменту вызова не существует на диске — тот же паттерн, что и у
    `createAd`); применяет тот же remote/local разбор ещё раз, уже на уровне
    каждого животного (`animal.localPhotoPaths` → `files`/`filesPaths`,
    `includeFilesPaths: true`); собирает `AdCreateRequest.fromData(...,
    filesPaths: filesPaths, includeFilesPaths: true, ...)` и вызывает
    `rpcClient.call(ApiMessage(link: '${Constants.boardServiceApi}/ads/$id',
    method: ApiMethod.post, data: adCreateRequest.toJson()..addAll({'_method':
    'PUT'}), isMultipartFormData: true))`.
12. При `response['status'] == "1"` метод возвращается без исключения;
    `_onCreateAd` выставляет `onSending: false` и эмитит
    `BoardAdCreateSuccess(_data, popRoute: true)`.
13. `BoardAdCreatePage`'s `BlocConsumer.listener`: `state.popRoute == true` →
    `context.pop(true)` — визард закрывается, возвращая `true` вызывающему
    экрану.
14. `MyAdsView._editAd`: `updated == true` → `await context.read<BoardCubit>
    ().refresh()` — список «Мои объявления» перезапрашивается у сервера
    целиком (`isMyAds: true`); правка становится видна пользователю только
    после этого перезапроса — сам объект `Ad`, переданный в визард
    (`args.ad`), нигде не патчится на месте (см. «Связанные сущности»).

### Альтернативные потоки

- **Правка объявления с одним животным на продажу (`adTypeId == 1`,
  `saleMode == single`) — выбор места сбрасывает уже предзаполненное
  животное.** Первый видимый шаг для этой ветки — `selectPlace`
  (`BoardAdSelectPlaceStepPage`), при этом `selectedPlace` после `fromAd`
  остаётся `null` (шаг 4) и ничем не подсвечен в списке мест
  (`selectedPlace: data.selectedPlace` передаётся в `SelectPlaceStepPage`
  как есть); шаг входит в `_autoAdvanceSteps`, так что нижняя кнопка «Далее»
  для него вообще не отображается — единственный способ продвинуться дальше
  — тапнуть по одному из мест списка, что сразу диспатчит
  `BoardAdCreateEventSelectPlace(place)` и переключает вкладку. Обработчик
  `_onSelectPlace`:
  ```
  final keepSelectedAnimals = _data.selectedAdTypeId == 1 &&
      _data.saleMode == BoardAdSaleMode.multiple;
  _data = _data.copyWith(
    selectedPlace: event.place,
    selectedAnimals: keepSelectedAnimals ? _data.selectedAnimals : const [],
    ...
  );
  ```
  Поскольку `saleMode == single` (не `multiple`), `keepSelectedAnimals ==
  false` — `selectedAnimals` безусловно сбрасывается в `[]`, стирая
  животное, пришедшее из `ad.editAnimals` на шаге 4. Следующий шаг
  (`selectAnimal`) требует `selectAnimalStepSuccess ==
  selectedAnimals.isNotEmpty` — пользователь обязан заново выбрать животное
  (из тех, что есть на только что выбранном месте), причём ничто в UI не
  подсказывает, что нужно выбрать именно то же самое животное, которое уже
  было на объявлении. Если пользователь выберет другое животное (или другое
  место, где исходного животного нет вовсе), сохранённое обновление
  привяжет объявление к другому животному — без какого-либо
  предупреждения. Механизм сброса подтверждён тестом на уровне обработчика
  (см. «Связанные тесты»), но не воспроизведён именно в связке с
  предзаполнением через `fromAd` — не наступает как сквозной интеграционный
  тест, только прослежено чтением кода.
- **Правка объявления с несколькими животными на продажу (`adTypeId == 1`,
  `saleMode == multiple`)** — тот же шаг `selectPlace`, но
  `keepSelectedAnimals == true`, так что выбор места **не** сбрасывает уже
  предзаполненный список животных.
- **Правка объявления типа «Пропажа»/«Найдено» (`adTypeId == 5`/`6`)** —
  визард открывается сразу на шаге `description`, минуя `selectPlace`/
  `selectAnimal` целиком (см. шаг 7); возможность вообще открыть такую
  правку — уже задокументированный в [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)
  инвариант («Пропажа»/«Найдено» недостижимы из создания, но доступны через
  правку существующего объявления такого типа).
- **Ни одна фотография не менялась** — `localFiles` пуст,
  `retainedFilesPaths` совпадает с исходным `ad.files`; тело запроса всё
  равно содержит `filesPaths[]` с теми же URL (см. «Бизнес-правила»).
- **Все фотографии объявления удалены на экране правки** —
  `retainedFilesPaths` пуст и новых фото не добавлено; `filesPaths[]`
  отправляется как явный пустой массив (не отсутствует), что отличает
  «фотографий не осталось» от «поле не передавалось» на стороне сервера.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё серверное
  состояние меняется этим сценарием (`AdRepository.updateAd`, весь
  редактируемый набор полей разом, без diff по отдельным полям). Локально
  объявление online-only (нет Drift-таблицы) — ни объект `Ad`, переданный в
  визард как аргумент, ни какой-либо локальный кэш не патчатся на месте;
  вызывающий экран должен сам перезапросить список (`BoardCubit.refresh()`,
  шаг 14), чтобы увидеть правку.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  только читается: `CountriesRepository.getAll()` — источник списка для
  селекторов страны адреса/телефона; поскольку `fromAd` не восстанавливает
  исходную страну объявления, оба селектора в edit-режиме безусловно
  показывают RU (или первую страну списка), независимо от реальной страны
  объявления (см. «Открытые вопросы»). Сущность `Country` этим сценарием не
  изменяется.
- Справочники `board_ad_types`/`board_attributes` (описаны как поля/связи
  внутри [ENT-18](../entities/ENT-18-AD-IN-BOARD.md), не отдельными
  сущностями) — только читаются: `BoardAdTypesRepository.getAll()`
  (фактически не используется для решения об `adTypeId` в edit-режиме, шаг
  выбора типа скрыт) и `BoardAttributesRepository.getAll()` (маппинг
  цена/телефон/адрес/«когда нашлось» в generic-атрибуты тела запроса).
- Farm/Place (модуль FARM, уже специфицирован) — только читаются:
  `FarmRepository.getAll()` + `PlaceRepository
  .getAllWithThisFarmIdWithAnimals` наполняют `placesWithAnimals` для шагов
  `selectPlace`/`selectAnimal` (актуально для `adTypeId == 1`).
- `AnimalIdentification`/`Kind`/`Breed`/`Suit` (модуль ANIMAL/HANDBOOKS) —
  только читаются: резолвят названия породы/масти/вида для превью и для
  списка животных пользователя на шаге `selectAnimal`; сами животные этим
  сценарием не изменяются.

### Бизнес-правила

- Один и тот же bloc/визард обслуживает и создание, и правку; единственный
  дискриминатор — `BoardAdCreateData.isEditMode` (`editingAdId != null`),
  определяемый один раз при обработке `BoardAdCreateEventStart` по
  наличию/отсутствию `editingAd`.
- Edit-режим всегда исключает шаги `type`/`animalCount` — тип объявления
  через этот визард сменить нельзя; `adTypeId` — то, что уже было на
  объявлении, без ограничения `Constants.boardAdTypeIds` (в отличие от шага
  выбора типа при создании).
- `statusId`, отправляемый при обновлении, — исходный `ad.statusId` (или
  `1`, только если он был `null`) — в отличие от создания, где всегда
  безусловно отправляется литерал `1`.
- Различение «уже на сервере» / «новый локальный файл» в обоих списках
  фотографий (объявления и каждого животного) выполняется исключительно по
  схеме URL (`http`/`https`) строки пути — независимо (и идентично) в
  `BoardAdCreateBloc._onCreateAd` и внутри `AdRepository.updateAd`
  (собственная копия той же проверки).
- `filesPaths[]`/`animals[].filesPaths` в теле запроса на обновление
  присутствуют всегда (`includeFilesPaths: true`), даже пустым массивом —
  в отличие от `createAd`, который этот ключ никогда не отправляет
  (`includeFilesPaths: false` по умолчанию, ключ включается только если
  список не пуст).
- Успешное сохранение выглядит идентично успешному созданию
  (`BoardAdCreateSuccess(_data, popRoute: true)`), включая то же отсутствие
  какого-либо явного сообщения об ошибке на неуспешном пути — это уже
  задокументированное поведение `_onCreateAd`, не специфичное для правки, и
  не раскрывается здесь повторно.
- Сохранение не патчит локально ни один объект `Ad` — экран, открывший
  правку, обязан сам инициировать перезапрос списка, чтобы увидеть новое
  состояние (см. «Связанные сущности»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (multipart `POST /ads/{id}` с `_method: PUT`, разбор
фотографий на уже-загруженные и новые) полностью реализован и покрыт хотя бы
репозиторным тестом (см. «Связанные тесты»); находки, перечисленные в
«Открытые вопросы и ограничения» (в первую очередь — сброс предзаполненного
животного при повторном выборе места на правке одиночной продажи), не
блокируют его выполнение — они описывают неожиданное, но не падающее с
ошибкой поведение существующего кода.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView._editAd` | CURRENT | точка входа — открывает визард с `BoardAdCreatePageArguments(ad: ad)`, обновляет `BoardCubit` после успешного возврата |
| `lib/pages/board/presentation/widgets/board_ad_context_menu.dart` | `BoardAdContextMenuButton` | CURRENT | пункт контекстного меню «Редактировать» карточки в «Моих объявлениях» |
| `lib/pages/routes.dart` | маршрут `Routes.boardAdCreate` (`redirect`) | CURRENT | гейт авторизации перед открытием визарда (общий для создания и правки) |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `BoardAdCreatePageArguments`, `_BoardAdCreatePageState.build`, `BlocConsumer.listener` (`popRoute`) | CURRENT | чтение аргумента, диспатч `Start`, закрытие визарда по `popRoute` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventStart>` | CURRENT | предзаполнение формы через `fromAd`, дефолт стран, загрузка справочников/мест |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateData.fromAd` | CURRENT | маппинг полей `Ad` в форму визарда; не восстанавливает `selectedPlace`/`addressCountry`/`phoneCountry` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateData.isEditMode`, `.currentSteps`, `._stepsAfterTypeSelected` | CURRENT | исключение шагов `type`/`animalCount`, состав шагов по `adTypeId`/`saleMode` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventSelectPlace>` (`_onSelectPlace`) | CURRENT | условие `keepSelectedAnimals` — источник альтернативного потока со сбросом животного |
| `lib/pages/board_ad_create/presentation/steps/board_ad_select_department_step_page.dart` | `BoardAdSelectPlaceStepPage` | CURRENT | шаг выбора места; передаёт `selectedPlace` как есть, без принудительного предвыбора |
| `lib/pages/board_ad_create/presentation/steps/board_ad_preview_step_page.dart` | `BoardAdPreviewStepPage` | CURRENT | текст кнопки `save`/`board_ad_publish` в зависимости от `isEditMode`, диспатч `CreateAd` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc._onCreateAd` | CURRENT | развилка `updateAd`/`createAd` по `isEditMode`, разбор `localPhotoPaths` на `localFiles`/`retainedFilesPaths` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.updateAd` | CURRENT | multipart `POST /ads/{id}` с `_method: PUT`; повторный remote/local разбор фото, в т.ч. по каждому животному |
| `lib/models/board/ad_create_request.dart` | `AdCreateRequest.fromData`, `.toJson` | CURRENT | сборка тела запроса; безусловный ключ `filesPaths[]` при `includeFilesPaths: true` |
| `lib/models/board/ad_animal_model.dart` | `AdAnimalModel.toJson`, `.fromJson` | CURRENT | тот же remote/local разбор фотографий на уровне отдельного животного |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getAll` | CURRENT | источник дефолтной страны адреса/телефона, не восстанавливаемой из `Ad` |
| `lib/constants.dart` | `Constants.boardAdTypeIds` | CURRENT | ограничение шага выбора типа при создании; неприменимо на правке, т.к. шаг скрыт |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.refresh` | CURRENT | перезапрос списка «Мои объявления» после успешного возврата из визарда |

## Критерии приёмки

- Выбор «Редактировать» на карточке в «Моих объявлениях» открывает
  `Routes.boardAdCreate` с `BoardAdCreatePageArguments(ad: ad)`;
  `BoardAdCreateEventStart(editingAd: ad)` переводит bloc в состояние с
  `data.isEditMode == true` и `data.editingAdId == ad.id`.
- Визард в edit-режиме не показывает шаги `type`/`animalCount`, независимо
  от `adTypeId` объявления.
- Подтверждение на шаге `preview` (при `!onSending &&
  contactsStepSuccess && addressStepSuccess && descriptionStepSuccess`)
  вызывает ровно один `AdRepository.updateAd(id: ad.id, ...)` — не
  `createAd`.
- `AdRepository.updateAd` выполняет ровно один вызов `rpcClient.call`, чей
  `link` содержит `/ads/{id}`, а `data['_method'] == 'PUT'`.
- Каждый элемент `_data.localPhotoPaths`, начинающийся с `http`/`https`,
  попадает в `filesPaths` без повторной загрузки как файл; каждый
  оставшийся (локальный) путь конвертируется в `MultipartFile` и попадает в
  `files` — то же правило действует и для `animal.localPhotoPaths` каждого
  выбранного животного.
- `statusId`, переданный в `updateAd`, равен `ad.statusId` (либо `1`, если
  он был `null`) — не хардкодится в `1` безусловно.
- При `response['status'] == "1"` bloc эмитит `BoardAdCreateSuccess(_data,
  popRoute: true)`; `BoardAdCreatePage` реагирует `context.pop(true)`.
- После возврата с `true` вызывающий экран («Мои объявления») выполняет
  `BoardCubit.refresh()`.

## Связанные тесты

- `test/repositories/ad_repository_test.dart`, group `'UC-137 —
  AdRepository.updateAd'`, test `'успех -> POST /ads/{id} с _method:PUT, не
  бросает исключение'` — репозиторный уровень: подтверждает эффект шага 11
  основного потока (`link` содержит `/ads/5`, `data['_method'] == 'PUT'`),
  вызывая `updateAd` напрямую с готовыми параметрами, не через bloc/визард
  целиком.
- `test/pages/board_ad_create_bloc_test.dart`, group `'BoardAdCreateEventStart'`
  (без номера UC), blocTest `'editingAd задан -> данные формы предзаполнены
  через BoardAdCreateData.fromAd'` — подтверждает шаг 4 (`isEditMode`,
  `editingAdId`, предзаполнение `title`/`statusId`), не покрывает сохранение.
- `test/pages/board_ad_create_bloc_test.dart`, group `'BoardAdCreateData —
  вычисляемые геттеры степ-успеха'` (без номера UC), test `'fromAd
  определяет режим множественной продажи по adTypeId:1 и >1 editAnimals'` —
  подтверждает вычисление `saleMode` из шага 4.
- `test/pages/board_ad_create_bloc_test.dart`, group `'BoardAdCreateData
  .currentSteps — ветки по типу объявления/режиму'` (без номера UC), test
  `'isEditMode:true -> из currentSteps исключены type и animalCount'` —
  подтверждает шаг 6 основного потока.
- `test/pages/board_ad_create_bloc_test.dart`, group `'место / животное'`
  (без номера UC), blocTest `'SelectPlace сбрасывает selectedAnimals, кроме
  adType:1+multiple'` — подтверждает сам механизм альтернативного потока
  (условие `keepSelectedAnimals`), но собирает bloc заново
  (`BoardAdCreateBloc()`), без предшествующего `EventStart(editingAd:
  ...)` — то есть не воспроизводит именно комбинацию «правка → предзаполненное
  животное → сброс на шаге `selectPlace`» сквозным прогоном.
- **TBD — теста нет** на полный edit-путь через bloc целиком: ни один тест
  не диспатчит `BoardAdCreateEventCreateAd` после `BoardAdCreateEventStart
  (editingAd: ...)`, то есть ни один тест не проверяет, что edit-режим
  реально вызывает `AdRepository.updateAd` (а не `createAd`) через
  `_onCreateAd` — группа `'UC-135 — BoardAdCreateBloc._onCreateAd
  (создание)'` покрывает только create-режим.
- **TBD — теста нет** на сквозной сценарий «правка объявления с одним
  животным на продажу → выбор места на шаге `selectPlace` → предзаполненное
  животное теряется» — механизм сброса (см. выше) и предзаполнение через
  `fromAd` (см. выше) проверены каждый по отдельности, но не в связке друг с
  другом.

## Открытые вопросы и ограничения

- **Правка одиночной продажи теряет предзаполненное животное при
  обязательном повторном выборе места.** Для `adTypeId == 1` с одним
  животным (`saleMode == single`, самый частый случай продажи) первый
  видимый шаг визарда на правке — `selectPlace`, кнопки «Далее» на нём нет
  (шаг входит в `_autoAdvanceSteps`), а `selectedPlace` после
  `fromAd`/`_onStart` остаётся `null` и ничем не подсвечен в списке — так
  что пользователь обязан заново тапнуть по какому-то месту, прежде чем
  сможет продвинуться дальше. Это действие безусловно очищает
  `selectedAnimals` (см. «Альтернативные потоки»), стирая животное, уже
  привязанное к объявлению, и вынуждая выбрать животное заново на следующем
  шаге — без какой-либо подсказки, что нужно выбрать именно исходное. Если
  пользователь (что вполне вероятно, особенно если хотел поправить только
  текст/цену/фото, а не животное) выберет другое место или другое животное,
  сохранённая правка молча привяжет объявление к другому животному. Не
  воспроизведено сквозным тестом (см. «Связанные тесты»), не разбирается
  глубже в рамках этого файла.
- **Страна адреса/телефона на правке всегда сбрасывается на RU (или первую
  в списке), а не восстанавливается из объявления.** `BoardAdCreateData
  .fromAd` не заполняет `addressCountry`/`phoneCountry` (в `Ad` вообще нет
  поля страны — см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)), поэтому
  `_onStart` безусловно применяет тот же дефолт, что и при создании с нуля
  (`_data.addressCountry ?? ru`). Наблюдаемого следствия на сохранение это
  не имеет (в запрос уходят только `addressLine`/`phoneNationalNumber` —
  строки, не код страны, и оба геттера `addressStepSuccess`/
  `contactsStepSuccess` от этого дефолта, наоборот, становятся легче
  выполнимыми), но селекторы страны в UI на шагах `address`/`contacts`
  показывают не тот флаг/код, что был исходно, если объявление создавалось
  не из RU. Не разбирается глубже.
- **Оба слоя (bloc и repository) независимо реализуют одинаковую проверку
  URL-схемы** (`_isRemoteFilePath` в `board_ad_create_bloc.dart` и локальная
  функция `isRemoteFilePath` внутри `AdRepository.updateAd`) — на сегодня
  они идентичны и решения совпадают, но это дублирование логики, а не
  переиспользование одной функции; расхождение в будущем (например, если
  один из них научится распознавать ещё одну схему путей) тихо разошлось бы
  по двум местам одновременно. Не разбирается глубже.
