# UC-21 — Создание фермы успешно

## Назначение

Авторизованный пользователь заводит новую ферму (СХТП) через мастер создания:
имя → адрес → (только для первой фермы пользователя) видимость видов
животных. Ферма сохраняется локально с отрицательным `remoteId`, без ожидания
сети — и мастер сразу переходит к созданию первого отделения (`Place`) внутри
неё.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — экран создания фермы доступен
только авторизованному пользователю: гость, тапнувший по «Добавить первую
ферму», перенаправляется на экран профиля вместо мастера (см. «Альтернативные
потоки»).

## CURRENT

### Основной поток

1. Пользователь открывает мастер создания фермы одним из двух входов:
   FAB на главном экране навигатора, когда текущий путь — `Routes.mainNavigator`
   (`_MainPageState._onFabPressed`, `lib/pages/main/main_page.dart`), либо
   кнопкой «Добавить первую ферму»/«первое животное» на пустом экране без ферм
   (`AddFirstFarmWidget.build`, `lib/pages/main_navigator/presentation/widgets/add_first_farm_widget.dart`
   — доступна только когда `AppCacheService.isAuthorized()` истинно). Оба входа
   вызывают `context.pushNamed2(Routes.createFarm)` без `FarmCreatePageArguments`
   (`farm == null`).
2. `FarmCreatePage.build` читает аргументы (`farm = null`), создаёт
   `BlocProvider<FarmCreateCubit>` и вызывает `FarmCreateCubit()..loadData(farm)`.
3. `FarmCreateCubit.loadData(null)`: эмитит `isLoading: true`; вызывает
   `_farmRepository.getAll()` (наследуется от `BaseRepository.getAll` →
   `dao.getAll()`); вычисляет
   `isFirstFarm = existingFarm == null && allFarms.where((f) => !f.isDeleted).isEmpty`;
   так как `isFirstFarm` истинно, дополнительно загружает
   `_kindsRepository.getAll()` и сортирует по `name`; эмитит состояние с
   пустой заготовкой `farm` (дефолт `FarmCreateState`:
   `Farm(needUpdate: true, isDeleted: false, name: '', address: '')`),
   `isFirstFarm`, `kinds`, `isLoading: false`.
4. `_FarmCreateViewState.build` строит `TabController` по
   `cubit.getAvailableSteps()` — `[FarmCreateStep.name, FarmCreateStep.address]`,
   плюс `FarmCreateStep.kindsVisibility` в конце, когда `state.isFirstFarm`
   (`FarmCreateCubit._getAvailableSteps`). Пользователь проходит шаги:
   - **Имя** (`FarmNameStepPage`) — ввод названия, `cubit.updateFarmName`.
   - **Адрес** (`FarmAddressStepPage`) — геопоиск или метка на карте;
     `cubit.handlePlaceSelection`/`cubit.handleReverseGeocode` резолвят детали
     через `NominatimService`, заполняя `address`, `latitude`/`longitude`,
     `countryId` (по `country_code` через `CountriesRepository.getByCountryCode`),
     `regionId`/`districtId`/`localityId`/`streetId`/`house`/`building`/`apartment`.
   - **Видимость видов** (`FarmKindsStepPage`, только для первой фермы) —
     `cubit.toggleKindVisibility`/`toggleAllKindsVisibility` правят
     `Kind.visible` в памяти состояния кубита, ещё не сохранено в БД.
5. На последнем доступном шаге пользователь нажимает круглую кнопку
   (`_CircularProgressButton`, активна когда `cubit.canSave()` возвращает
   `true` — заполнены `name`, `address`, `regionId`). Обработчик `onTap`
   в `_FarmCreateViewState._Body`-дереве (`farm_create_page.dart`): если
   `state.isFirstFarm`, сначала `await cubit.saveKinds()`, затем
   `await cubit.saveFarm()`.
6. `FarmCreateCubit.saveKinds()`: если `isFirstFarm && kinds.isNotEmpty`,
   вызывает `_kindsRepository.updateAll(state.kinds)` — персистит изменённую
   видимость видов ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md), модуль
   HANDBOOKS) до того, как ферма вообще создана.
7. `FarmCreateCubit.saveFarm()`: защита от повторного сабмита
   (`if (state.isSubmitting) return`); эмитит `isSubmitting: true`; так как
   `state.farm.id == null` (новая ферма), вызывает
   `_farmRepository.insertFarmWithNegativeRemoteId(state.farm)`.
8. `FarmRepository.insertFarmWithNegativeRemoteId`: `dao.insertFarmReturning(farm)`
   — `INSERT` в `Farms`, возвращает вставленную строку с локальным
   автоинкрементным `id` и `remoteId == null` (поле не было выставлено во
   входном `Farm`); затем вызывает `dao.setFarmNegativeRemoteId(newFarm)` —
   `UPDATE Farms SET remote_id = -id WHERE id = newFarm.id`; метод возвращает
   `newFarm.id!`.
9. `FarmCreateCubit.saveFarm()` эмитит
   `farm: state.farm.copyWith(remoteId: Value(-newFarmId))`, затем
   `isSuccess: true`, и в `finally` — `isSubmitting: false`.
10. `FarmCreatePage`'s `BlocListener<FarmCreateCubit, FarmCreateState>`
    (`listenWhen: state.isSuccess`) вызывает `_onSuccess`: `context.pop()`
    (закрывает мастер создания фермы) и сразу
    `context.pushNamed(Routes.createPlace, extra: PlaceCreatePageArguments(farmId: state.farm.remoteId!, existingPlaces: []))`
    — пользователь без промежуточного экрана попадает в мастер создания
    первого отделения новой фермы.

### Альтернативные потоки

- **Гость на пустом экране ферм.** `AddFirstFarmWidget.build` при
  `AppCacheService.isAuthorized() == false` не открывает мастер — тап уводит
  на `context.go(Routes.profile)`. Экран создания фермы недостижим для гостя
  этим входом; FAB-вход (`main_page.dart`) в принципе доступен только когда
  видна главная навигация, что для гостя ведёт по отдельному потоку профиля,
  не описанному здесь.
- **Не первая ферма.** Если у пользователя уже есть хотя бы одна ферма с
  `isDeleted != true`, `isFirstFarm` ложно, шаг видимости видов не
  показывается, `saveKinds()` не вызывается (условие `isFirstFarm &&
  kinds.isNotEmpty` в `saveKinds` и сам факт, что UI вызывает его только при
  `state.isFirstFarm`, — двойная защита одного и того же условия).
- **`setFarmNegativeRemoteId` не дожидается (`await`) внутри репозитория.**
  `FarmRepository.insertFarmWithNegativeRemoteId` присваивает результат
  `dao.setFarmNegativeRemoteId(newFarm)` в `result`, не ставя `await` перед
  вызовом — `log('...: Finish: $result')` логирует представление
  `Future<int>`, а не итоговое число обновлённых строк, и сам метод
  возвращает `newFarm.id!` кубиту, не дожидаясь, пока `UPDATE remote_id`
  реально завершится. Наблюдаемый эффект для этого сценария (успех)
  отсутствует — drift выполняет запросы на одном соединении
  последовательно, поэтому `UPDATE` фактически завершается раньше, чем
  следующий запрос к той же БД; ничто в коде это не гарантирует явно (см.
  «Открытые вопросы»).
- **Повторный `saveFarm()` до завершения первого** — покрыто отдельным
  тестом (`UC-315` в старой нумерации, см. «Связанные тесты»): второй вызов,
  пока `isSubmitting == true`, синхронно возвращается без повторного
  обращения к репозиторию.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) — основная сущность сценария:
  новая строка `Farm`, вставленная с `remoteId`, выставленным отрицательным
  сразу после вставки (id < 0 по конвенции локально-созданной, ещё не
  синхронизированной записи).
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) — не создаётся этим
  сценарием, но `_onSuccess` немедленно переводит пользователя в мастер
  создания первого `Place` для только что созданной фермы — сквозной
  UI-переход, часть наблюдаемого поведения кнопки создания фермы.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Kind, модуль
  HANDBOOKS) — побочно затрагивается только когда `isFirstFarm`: видимость
  видов сохраняется через `KindsRepository.updateAll` до вставки самой
  фермы, отдельным шагом (`saveKinds()`), не частью транзакции создания
  фермы.

### Бизнес-правила

- Единственные обязательные для сохранения поля — `name`, `address`,
  `regionId` (`FarmCreateCubit.canSave`); шаг адреса дополнительно требует
  `countryId` для перехода на следующий шаг (`canProceedToNextStep`), но не
  для самого сохранения.
- Шаг видимости видов показывается и обязателен к прохождению
  (`canProceedToNextStep` для `kindsVisibility` требует `kinds.any((k) =>
  k.visible)`) только для первой фермы пользователя — определяется один раз
  при `loadData`, не пересчитывается по ходу заполнения формы.
- Создание всегда local-first: `insertFarmWithNegativeRemoteId` не делает
  сетевых вызовов и не ждёт подтверждения сервера — синхронизация
  (замена отрицательного `remoteId` на серверный) происходит отдельным
  шагом, вне этого сценария (см. [MOD-3](../modules/MOD-3-FARM.md)).
- `saveFarm()` защищён от повторного параллельного вызова флагом
  `isSubmitting`, но не оборачивает `_farmRepository.insertFarmWithNegativeRemoteId`
  в `try/catch` — обработка сбоя самого вызова (репозиторий гасит исключение
  внутри себя и возвращает `0`, см. «Открытые вопросы») сценарием `CREATE_OK`
  не покрывается.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован; сквозной UI-путь (два входа в мастер,
переход в создание `Place` после успеха) верифицирован только чтением
исходного кода, отдельным widget-тестом не покрыт.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main/main_page.dart` | `_MainPageState._onFabPressed` | CURRENT | FAB на главном экране навигатора открывает `Routes.createFarm` без аргументов |
| `lib/pages/main_navigator/presentation/widgets/add_first_farm_widget.dart` | `AddFirstFarmWidget.build` | CURRENT | вход для пользователя без ферм; для гостя ведёт на профиль вместо мастера |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage.build`, `_FarmCreateViewState`, `_onSuccess` | CURRENT | шелл мастера: создаёт кубит, слушает `isSuccess`, после успеха переходит в `Routes.createPlace` |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.loadData`, `_getAvailableSteps`, `canSave`, `saveKinds`, `saveFarm` | CURRENT | загрузка `isFirstFarm`/справочника видов, состав шагов, валидация, сохранение видимости видов и самой фермы |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_state.dart` | `FarmCreateState`, `FarmCreateStep` | CURRENT | freezed-состояние мастера, дефолтная заготовка `Farm` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAll`, `insertFarmWithNegativeRemoteId` | CURRENT | источник списка ферм для `isFirstFarm`; локальная вставка с последующим выставлением отрицательного `remoteId` |
| `packages/sheep_farm_database/lib/entities/farm/farms_dao.dart` | `FarmsDao.insertFarmReturning`, `setFarmNegativeRemoteId` | CURRENT | `INSERT ... RETURNING`; отдельный неawait-нутый `UPDATE remote_id = -id` |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `Farms`, `Farm` | CURRENT | таблица/модель, `remoteId` — nullable, без дефолтного значения |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository.getAll`, `updateAll` | CURRENT | загрузка и сохранение видимости видов на шаге `kindsVisibility` |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePageArguments` | CURRENT | принимает `farmId` только что созданной фермы для следующего шага мастера |
| `lib/pages/routes.dart` | `Routes.createFarm`, `Routes.createPlace` | CURRENT | маршруты мастера создания фермы и отделения |

## Критерии приёмки

- После заполнения имени, адреса (и, для первой фермы, видимости хотя бы
  одного вида) и нажатия финальной кнопки создаётся ровно одна новая строка
  `Farm` с заданными пользователем полями.
- Сразу после вставки `Farm.remoteId` отрицателен и по модулю равен
  локальному `id` строки (`remoteId == -id`).
- Сохранение не делает и не ждёт сетевых вызовов — `isSuccess: true`
  достигается без обращения к API.
- Для первой фермы пользователя изменённая видимость видов
  ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)) сохраняется до
  вставки фермы, и её сохранение не создаёт вторую ферму и не блокирует
  успех при пустом `kinds`.
- После успеха пользователь автоматически оказывается в мастере создания
  отделения (`Routes.createPlace`) с `farmId`, равным `remoteId` только что
  созданной фермы.
- Повторный тап по финальной кнопке до завершения первого вызова не создаёт
  вторую ферму (`insertFarmWithNegativeRemoteId` вызывается не более одного
  раза за клик-серию).

## Связанные тесты

`test/pages/farm_create_cubit_test.dart`, group `'FarmCreateCubit.saveFarm'`,
test `'farm.id == null -> insertFarmWithNegativeRemoteId, remoteId выставлен
отрицательным'`.

`test/pages/farm_create_cubit_test.dart`, group `'FarmCreateCubit.saveFarm'`,
test `'UC-315: повторный вызов saveFarm до завершения первого -> второй вызов
no-op (isSubmitting-защита)'` (будет переименовано, не трогать сейчас).

TBD — сквозной сценарий с реальным `FarmsDao`/`KindsRepository` (не
замоканными) и с UI-переходом в `Routes.createPlace` после успеха теста не
имеет.

## Открытые вопросы и ограничения

- **`setFarmNegativeRemoteId` вызывается без `await` внутри
  `insertFarmWithNegativeRemoteId`.** `final result =
  dao.setFarmNegativeRemoteId(newFarm);` присваивает `Future<int>`, не
  дожидаясь его — метод возвращает `newFarm.id!` кубиту, пока `UPDATE
  remote_id = -id` формально ещё не гарантированно завершён. В однопоточном
  доступе к одному drift-соединению запросы фактически выполняются по
  очереди, поэтому наблюдаемого сбоя в этом сценарии нет, но само отсутствие
  `await` — не документированная защита, а совпадение порядка выполнения;
  ничто в коде не мешает будущему рефактору (например, переносу вставки и
  апдейта на разные соединения/изоляты) обнажить гонку, при которой строка
  ненадолго — или не только ненадолго — остаётся с `remoteId == null` вместо
  отрицательного.
- **Молчаливое поглощение ошибки в `insertFarmWithNegativeRemoteId`.**
  `catch (e, stackTrace)` логирует исключение и возвращает `0`, не
  перебрасывая его дальше. `FarmCreateCubit.saveFarm()` не различает этот
  случай от успеха: `-newFarmId` становится `-0` (`0`), состояние всё равно
  получает `isSuccess: true`, а `_onSuccess` затем читает
  `state.farm.remoteId!` как ненулевой валидный id отделения. Этот сценарий
  документирует только успешный путь (`CREATE_OK`); сам факт, что ошибка
  вставки в коде выглядит неотличимой от успеха, не имеет отдельного
  `CREATE_ERROR`-сценария в этом проходе — заслуживает отдельного
  use-case при специфицировании ошибочных путей FARM.
- **Гонка `AddFirstFarmWidget` vs `_onFabPressed`** не пересекаются в одном
  клике, но оба ведут в один и тот же `FarmCreateCubit` — не отдельный
  открытый вопрос, просто два независимых входа с идентичным поведением
  дальше по потоку.
