# UC-136 — Публикация объявления отказывает (сеть или отказ сервера) — форма гасит спиннер, но не сообщает пользователю о неудаче

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же визард, что описан в [EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md)
(`BoardAdCreateBloc._onCreateAd`, не-edit режим), но здесь сам вызов
`AdRepository.createAd` заканчивается исключением — по одной из двух причин,
каждая проверена отдельно чтением кода:

- (а) сетевое/техническое исключение — `rpcClient.call(message)` бросает
  (недоступность сети, таймаут, любой не-2xx HTTP-ответ);
- (б) логический отказ сервера без сетевого исключения —
  `response['status'] != "1"` (например `"0"`/`"error"`), и `AdRepository.createAd`
  сама бросает `Exception(response['message'])`.

Обе причины перехватываются **одним и тем же** `catch (e)` внутри
`AdRepository.createAd` (логирует, `rethrow`) и затем **одним и тем же**
`catch (e, st)` внутри `BoardAdCreateBloc._onCreateAd` — код нигде не
различает их. Результат для пользователя один и тот же в обоих случаях:
`_onCreateAd` логирует исключение через `Talker`, сбрасывает `onSending` в
`false` и эмитит `BoardAdCreateSuccess(_data)` — **тот же тип состояния**, что
и при обычном изменении любого поля формы, без `popRoute` и без какого-либо
флага/сообщения об ошибке. Пользователь не получает вообще никакого сигнала о
том, что публикация не удалась.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
BOARD требует реальной авторизации для мутаций (публикация — одна из них, см.
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), «гость=авторизован работает
только для чтения»); гость до этого шага визарда физически не доходит (вход в
`BoardAdCreatePage` в принципе не проверяется здесь отдельно — `BoardAdCreateBloc`
не проверяет авторизацию нигде в своих обработчиках, но сама публикация без
токена вернулась бы отказом сервера, что и покрывается веткой (б) этого же
сценария). Действие — нажатие кнопки «Опубликовать»/«Сохранить»
(`BoardAdPreviewStepPage`) на последнем шаге визарда создания объявления.

## CURRENT

### Основной поток

1. Пользователь проходит визард создания объявления (тип → количество
   животных → место/животное → описание → адрес → контакты) и доходит до шага
   `BoardAdCreateStep.preview` — `BoardAdPreviewStepPage`. Кнопка публикации
   (`context.tr('board_ad_publish')` для создания, `context.tr('save')` для
   edit-режима) привязана к `isLoading: state.data.onSending` и `onTap: () =>
   bloc.add(const BoardAdCreateEventCreateAd())`.
2. `BoardAdCreateBloc.on<BoardAdCreateEventCreateAd>` → `_onCreateAd`:
   - guard — если `_data.onSending` уже `true`, либо
     `!_data.contactsStepSuccess`, либо `!_data.addressStepSuccess`, либо
     `!_data.descriptionStepSuccess` — обработчик молча возвращается (`return`),
     без какого-либо состояния; в этом сценарии все три предпосылки
     выполнены, обработчик продолжает;
   - `adTypeId = _data.selectedAdTypeId` — если `null`, тоже молчаливый
     `return`; в этом сценарии не `null`;
   - строит `animals` (список `AdAnimalModel`) по правилам для `adTypeId ==
     1`/`5`/`6` — не влияет на исход этого сценария;
   - `_data = _data.copyWith(onSending: true); emit(BoardAdCreateSuccess(_data));` —
     кнопка публикации переходит в состояние загрузки (спиннер).
3. Внутри `try`: собирает `localFiles`/`retainedFilesPaths` (разделение по
   `_isRemoteFilePath`), `price`/`phone`/`address`/`whenWasFound` (`.trim()`).
   Поскольку `_data.isEditMode == false` (`editingAdId == null` — это
   создание, не правка), вызывается ветка `else`:
   `await _adRepository.createAd(title:, price:, description:, files:
   localFiles.map((e) => File(e)).toList(), adTypeId:, statusId: 1, phone:,
   address:, whenWasFoundText:, animals:)`.
4. Внутри `AdRepository.createAd` (`lib/repositories/board/ad_repository.dart`):
   строит multipart-файлы (`_multipartFilesFromPaths`) для самого объявления и
   для каждого животного, читает `availableAttributes =
   await boardAttributesRepository.getAll()`, строит `AdCreateRequest.fromData(...)`,
   собирает `ApiMessage(link: '${Constants.boardServiceApi}/ads', method:
   ApiMethod.post, data: adCreateRequest.toJson(), isMultipartFormData: true)`,
   получает `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc')`, весь
   код метода — внутри одного `try`. Именно вызов `await rpcClient.call(message)` —
   точка расхождения этого сценария (обе ветки проверены отдельно чтением
   кода).
5. **Ветка (а) — сетевое/техническое исключение.**
   `CustomDioClient.call` (`lib/network/api_client/custom_dio_client.dart`)
   оборачивает `AuthInterceptor.getTokenDataByPath` и `dio.request(...)`
   собственным `try/catch`: любое исключение (сеть недоступна, таймаут, обрыв
   соединения, либо любой не-2xx HTTP-ответ — `DioClient`
   (`lib/network/dio_client.dart`) не переопределяет `validateStatus`, поэтому
   Dio по умолчанию бросает `DioException` вне 200–299) логируется через
   `getIt.get<Talker>().error('CustomDioClient: call: $e')` и безусловно
   перебрасывается (`rethrow`). Это исключение всплывает прямо в `try`
   `AdRepository.createAd` (шаг 4).
6. **Ветка (б) — логический отказ сервера без исключения.**
   `CustomDioClient.call` возвращает обычный HTTP-ответ без собственного
   исключения; для `POST /ads` типичный отказ (например «заполните все
   поля») приходит как `Map` без ключей `data`/`animal_exits` и с явным
   `response.data['status'] == 'error'` — единственная форма ответа, которую
   `CustomDioClient.call` возвращает как есть, без принудительного `status:
   "1"`. `AdRepository.createAd` получает такой `response` без исключения:
   `if (response['status'] == "1") { return; } else { throw
   Exception(response['message']); }` — ветвь `else` бросает `Exception`
   внутри того же `try` метода (шаг 4).
7. В обеих ветках исключение перехватывается **одним и тем же** `catch (e)`
   `AdRepository.createAd`: `getIt<Talker>().error('createAd Error: $e');
   rethrow;` — логирует и безусловно перебрасывает дальше, не различая ветку
   (а) от (б).
8. Исключение всплывает из `await _adRepository.createAd(...)` (шаг 3) прямо в
   `catch (e, st)` `BoardAdCreateBloc._onCreateAd`: `getIt<Talker>().handle(e,
   st); _data = _data.copyWith(onSending: false); emit(BoardAdCreateSuccess(_data));` —
   тот же тип состояния (`BoardAdCreateSuccess`), что эмитится после любого
   рядового изменения поля формы (`_onChangeTitle`, `_onAddPhoto` и т.д.) и
   после реального успеха публикации (шаг, где вместо этого эмитится
   `BoardAdCreateSuccess(_data, popRoute: true)`, недостижимый здесь). Ни
   `popRoute`, ни `navigateToStepIndex` не выставлены — оба остаются
   дефолтными (`false`/`null`).
9. `BlocConsumer.listener` в `board_ad_create_page.dart` реагирует только на
   `state.popRoute` (закрытие экрана) и `state.navigateToStepIndex`
   (переключение шага) — ни одно из условий не срабатывает, слушатель ничего
   не делает.
10. `BoardAdPreviewStepPage`'s `BlocBuilder` перерисовывается на новое
    состояние: `isLoading: state.data.onSending` — спиннер гаснет, кнопка
    снова активна, подпись не меняется. Все значения формы (`title`,
    `description`, `priceDigits`, `localPhotoPaths`, `addressLine`,
    `phoneNationalNumber`, `selectedAnimals`/`animalData` и т.д.) остаются в
    точности такими, какими были до нажатия — единственное изменившееся поле
    `_data` за весь проход — `onSending` (`false` → `true` → `false`).
11. Экран не закрывается, шаг не меняется, никакого `SnackBar`/сообщения не
    показывается (в `board_ad_create_page.dart` и
    `board_ad_preview_step_page.dart` нет ни одного вызова `SnackBar`/
    `showAppSnackBar*`). Единственный способ пользователя понять, что что-то
    пошло не так, — заметить, что после нажатия ничего не произошло (не
    закрылся визард, не появилось объявление на «Моих объявлениях»).
12. Единственный путь вперёд для пользователя — повторно нажать кнопку
    публикации: поскольку `_data` не сброшен, повтор отправляет тот же payload
    без повторного ввода; если причина была временной (например, кратковременная
    потеря сети — ветка а), повтор может завершиться успехом
    (`popRoute: true`).

### Альтернативные потоки

- **Edit-режим (`_data.isEditMode == true`, вне рамок этого use-case).**
  Тот же обработчик `_onCreateAd` вызывает `_adRepository.updateAd(...)`
  вместо `createAd`, с идентичной формой `try/catch` (тот же `catch (e, st)`
  бloc'а, то же отсутствие сигнала об ошибке) — но это отдельное событие,
  [EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md), со своим use-case, не
  описываемое здесь подробно.
- **Guard на повторный тап во время отправки.** Пока `_data.onSending ==
  true`, повторные `BoardAdCreateEventCreateAd` из-за первой же строки
  `_onCreateAd` (`if (_data.onSending || ...) return;`) полностью
  игнорируются — быстрые повторные нажатия на кнопку не порождают
  параллельных запросов `createAd`.
- **Пустой сетевой ответ/иная форма отказа, не разбираемая отдельно.** Любое
  другое исключение на любом шаге сборки multipart-запроса внутри
  `AdRepository.createAd` (например `MultipartFile.fromFile` на
  несуществующем локальном файле) тоже перехватывается тем же `catch (e)`
  метода и рождает то же наблюдаемое поведение — сценарий не разделяет их
  отдельно, поскольку с точки зрения `BoardAdCreateBloc` любой такой случай
  неотличим от веток (а)/(б).
- **`REJECTED`-ветки не существует.** Ветка (б) — по букве описания в
  `use-cases/AGENTS.md` («операция дошла до получателя и была осознанно
  отклонена бизнес-правилом») — формально ближе к `CREATE_REJECTED`, чем к
  `CREATE_ERROR`: запрос реально доходит до сервера, и сервер осознанно
  отклоняет его (например, из-за незаполненного обязательного поля). Этот
  файл, тем не менее, фиксирует обе ветки как `CREATE_ERROR` одним файлом —
  тот же прецедент, что уже задокументирован для взвешиваний
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)) и
  инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)):
  ни `AdRepository.createAd`, ни `BoardAdCreateBloc._onCreateAd` не
  предоставляют наблюдаемого различия между «сервер отказал по содержанию» и
  «технический сбой» ни на одном уровне выше самого `CustomDioClient.call` —
  оба становятся одним и тем же `Exception`, пойманным одним и тем же `catch`.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё создание не
  состоялось: online-only, без локального хранения (см. ENT-18,
  «Инварианты» — «Онлайн-only, без сети — недоступно целиком»), поэтому при
  отказе (любая ветка) не остаётся вообще никакого следа объявления — ни на
  сервере (запрос не принят), ни локально (Drift-таблицы для `Ad` не
  существует).
- `BoardAdCreateData` (`lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart`) —
  не отдельная доменная сущность, а исключительно in-memory состояние
  визарда, живущее только на время жизни `BoardAdCreateBloc`; это единственное
  место, где введённые пользователем данные продолжают существовать после
  отказа (см. «Бизнес-правила») — до тех пор, пока пользователь не закроет
  экран, после чего они теряются безвозвратно, без какого-либо черновика.

### Бизнес-правила

- Обе причины отказа (сетевое исключение и логический отказ сервера без
  исключения) перехватываются одним и тем же `catch` дважды подряд —
  сперва в `AdRepository.createAd`, затем в `BoardAdCreateBloc._onCreateAd` —
  ни один из этих уровней не различает их и не хранит признак, какая именно
  причина произошла.
- Итоговое состояние — `BoardAdCreateSuccess(_data)` без `popRoute` и без
  `navigateToStepIndex` — тот же рантайм-тип, что при любом рядовом
  изменении поля формы; отдельного состояния-ошибки (`BoardAdCreateFailure`
  используется только для отказа самого `EventStart`, не для отказа
  публикации) для этого пути не существует.
- Данные формы не сбрасываются и не изменяются путём отказа — единственное
  затронутое поле `_data` — `onSending`, возвращаемое в `false`.
- Никакого отдельного retry/backoff-механизма нет — повтор целиком ручной,
  инициируется пользователем повторным нажатием той же кнопки с тем же,
  ничем не изменённым состоянием формы.
- Онлайн-only природа [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) означает,
  что неудачная публикация не оставляет вообще никакого локального следа —
  в отличие от большинства сущностей `ANIMAL`, здесь нет unsent-очереди/
  черновика, куда можно было бы вернуться после отказа: единственное
  сохранение — в оперативной памяти `_data`, теряемое при закрытии экрана.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе причины отказа (сетевое исключение и
логический отказ сервера без исключения) воспроизводятся статическим чтением
кода целиком: `BoardAdCreateBloc._onCreateAd` → `AdRepository.createAd` →
`CustomDioClient.call`/`DioClient`. Ветка (б) подтверждена запущенным тестом
на уровне репозитория (см. «Связанные тесты»); отсутствие сигнала об ошибке в
целом (независимо от причины) подтверждено запущенным тестом на уровне
bloc'а. Исправление (например, отдельное состояние `BoardAdCreateError`/
`SnackBar` при отказе) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_create/presentation/steps/board_ad_preview_step_page.dart` | `BoardAdPreviewStepPage` | CURRENT | кнопка публикации/сохранения, `isLoading: state.data.onSending`, диспатчит `BoardAdCreateEventCreateAd` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc._onCreateAd` | CURRENT | guard на повторный тап/незаполненные шаги; собирает payload; ветвится `isEditMode` (`updateAd`/`createAd`); единственный `catch (e, st)` для обеих причин отказа — логирует через `Talker.handle`, сбрасывает `onSending`, эмитит `BoardAdCreateSuccess(_data)` без `popRoute`/`navigateToStepIndex` |
| `lib/pages/board_ad_create/bloc/board_ad_create_state.dart` | `BoardAdCreateSuccess`, `BoardAdCreateFailure` | CURRENT | `BoardAdCreateSuccess` — единственный тип состояния, переиспользуемый и для рядовых изменений формы, и для этого отказа; `BoardAdCreateFailure` существует, но используется только отказом `EventStart`, не этим сценарием |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `_BoardAdCreatePageState.build` (`BlocConsumer.listener`) | CURRENT | реагирует только на `popRoute`/`navigateToStepIndex` — ни один не выставлен этим сценарием, слушатель не реагирует никак |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.createAd` | CURRENT | строит multipart-запрос, вызывает `rpcClient.call`; собственный `catch (e) { Talker.error('createAd Error: $e'); rethrow; }` — единый для обеих причин отказа; при `response['status'] != "1"` сама бросает `Exception(response['message'])` внутри своего же `try` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor` (ветка а); при HTTP-успехе без ключей `data`/`animal_exits` и с явным `status: 'error'` возвращает ответ как есть без исключения (несущая форма ветки б) |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/models/board/ad_create_request.dart` | `AdCreateRequest.fromData` | CURRENT | строит тело multipart-запроса из `_data` — то же тело будет собрано заново при ручном повторе, поскольку `_data` не тронут отказом |
| `lib/repositories/board/board_attributes_repository.dart` | `BoardAttributesRepository.getAll` | CURRENT | читается перед сборкой запроса (генерик-атрибуты цена/адрес/телефон); не связано с отказом напрямую |

## Критерии приёмки

- Если `rpcClient.call` внутри `AdRepository.createAd` бросает исключение
  ЛИБО возвращает ответ с `response['status'] != "1"`, `AdRepository.createAd`
  в обоих случаях безусловно перебрасывает `Exception` (никогда не глотает
  его молча).
- `BoardAdCreateBloc._onCreateAd`, поймав это исключение (любой из двух
  причин): выставляет `onSending: false`; эмитит `BoardAdCreateSuccess(_data)`
  с `popRoute: false` и `navigateToStepIndex: null`; не изменяет ни одно
  пользовательское поле `_data` (`title`/`description`/`priceDigits`/
  `localPhotoPaths`/`addressLine`/`phoneNationalNumber`/`selectedAnimals`/
  `animalData` остаются такими же, какими были до нажатия кнопки публикации).
- Ни в `_data`, ни в каком-либо ином видимом пользователю канале (нет
  `SnackBar`, нет отдельного состояния-ошибки) не появляется сообщение об
  этом отказе — по рантайм-типу состояние неотличимо от состояния,
  порождённого рядовым безобидным изменением поля формы.
- Визард не закрывается и не переключает шаг; пользователь остаётся на шаге
  предпросмотра с активной (не в состоянии загрузки) кнопкой публикации,
  готовой к повторному нажатию с теми же данными.
- Ни один локальный след неудачной попытки публикации не создаётся —
  Drift-таблицы для `Ad` не существует (см. ENT-18, online-only).

## Связанные тесты

- `test/pages/board_ad_create_bloc_test.dart`, group `'UC-136 —
  BoardAdCreateBloc._onCreateAd ERROR (известный дефект — без сообщения об
  ошибке)'`, test `'createAd бросает -> BoardAdCreateSuccess без popRoute,
  данные формы сохранены, БЕЗ сигнала об ошибке'` — мокает `adRepository.createAd`
  через `thenThrow(Exception('server error'))` (родовое исключение — стоит за
  обе причины отказа сразу, неразличимые на этом уровне); подтверждает, что
  итоговое состояние — `BoardAdCreateSuccess` (не `BoardAdCreateFailure`),
  `popRoute == false`, `title`/`description` сохранены, `onSending == false`.
- `test/repositories/ad_repository_test.dart`, group `'UC-136 —
  AdRepository.createAd ERROR'`, test `'createAd: status != "1" -> Exception с
  сообщением сервера, rethrow'` — мокает `farmRpcClient.call` ответом без
  исключения `{'status': '0', 'message': 'Заполните все поля'}`; подтверждает,
  что `repository.createAd(...)` бросает `Exception` — это отдельное,
  независимое подтверждение именно ветки (б), на уровне репозитория, не
  bloc'а.
- Старая нумерация групп (`UC-136`) в обоих файлах относится к прежней схеме
  id и не переименована на момент написания этой спеки — переименование под
  этот id (`UC-136`) выполняется отдельным контролируемым проходом, не этой
  задачей; якорь `grep -r "UC-136" test/` заработает только после него.
- **TBD — теста нет** на ветку (а) специально для `AdRepository.createAd` —
  т.е. на `farmRpcClient.call`/`rpcClient.call`, бросающий исключение
  непосредственно внутри `createAd` (а не через родовой мок на уровне
  `adRepository` целиком, как в тесте bloc'а выше). Ближайшее реально
  существующее покрытие той же формы кода — `test/repositories/ad_repository_test.dart`,
  group `'UC-138 — AdRepository.updateAd ERROR'`, test `'updateAd: сетевое
  исключение -> rethrow'` — тот же `try/catch/rethrow`, но для
  `updateAd`, не `createAd`.

## Открытые вопросы и ограничения

- **Тот же класс дефекта, что и у sync-push'ей ANIMAL
  ([UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md),
  [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)), но здесь
  это переднеплановое, инициированное пользователем действие, не фоновый
  sync-проход.** Пользователь явно нажимает кнопку и активно ждёт результата —
  молчаливый отказ здесь заметнее и практически неизбежно вызовет повторное
  нажатие «в никуда», а не будет обнаружен спустя время на экране истории.
- Было ли задумано какое-то другое поведение (`SnackBar`, отдельное состояние
  ошибки) и просто не подключено, либо решение «дать пользователю самому
  заметить и повторить» осознанное — ничем в коде/комментариях не
  зафиксировано.
- Классификация обеих причин одним `CREATE_ERROR`-файлом (не разделение ветки
  (б) на `CREATE_REJECTED`) сделана по прецеденту
  [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md)/[UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md) —
  см. «Альтернативные потоки»; при этом строго по букве `use-cases/AGENTS.md`
  ветка (б) (осознанный отказ сервера, дошедший до получателя) ближе к
  `REJECTED`, чем к `ERROR` — открытый вопрос к самой применимости этого
  прецедента, не решаемый в рамках этого документирующего прохода.
- Покрытие теста для ветки (а) специально для `createAd` (не `updateAd`) —
  TBD (см. «Связанные тесты»); вывод для ветки (а) в этом файле опирается на
  идентичность формы `try/catch/rethrow` в `AdRepository.createAd`/`updateAd`,
  подтверждённую чтением кода, и на тест ветки (а) для `updateAd` (`UC-138`),
  не на прямой тест для `createAd`.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`AdRepository.createAd` →
  `CustomDioClient.call` → `DioClient`) и подтверждён двумя независимыми
  тестами (см. «Связанные тесты»); точная форма ответа `POST /ads` при
  логическом отказе (`status`, отличный от `"1"`, конкретные значения
  `message`) реальным сервером этой спекой не верифицирована.
