# UC-138 — Правка объявления отказывает технически: тот же безусловный `emit(BoardAdCreateSuccess(..., onSending:false))` без сигнала об ошибке, что и при публикации

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Автор проходит визард правки собственного объявления (тот же
`BoardAdCreateBloc`/`BoardAdCreatePage`, что и при публикации, открытый с
`BoardAdCreatePageArguments(ad: ad)` из «Моих объявлений»), подтверждает на
шаге предпросмотра — `_onCreateAd` в edit-режиме вызывает
`AdRepository.updateAd`, которая отказывает (сетевое исключение либо
логический отказ сервера). Это **тот же класс дефекта, уже задокументированный
для публикации** ([UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md)):
`_onCreateAd` — единый обработчик на оба режима (создание/правка), с одним
общим `try/catch` вокруг `await _adRepository.createAd(...)` /
`await _adRepository.updateAd(...)`; при любом исключении он безусловно
эмитит `BoardAdCreateSuccess(_data)` (тот же тип состояния, что и при успехе,
`popRoute: false`, `navigateToStepIndex: null` по умолчанию) — без единого
сигнала об ошибке где-либо в состоянии. Прочитан код обеих веток
(`isEditMode == true`/`false`) отдельно, специально для этого файла — путь
подтверждён идентичным, различие только в том, какой метод репозитория
вызывается и какие параметры ему передаются (см. «Основной поток»), поэтому
здесь не повторяется общий разбор дефекта, разобранный в
[UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md), — фиксируются
только специфичные для edit-режима детали и явное подтверждение идентичности.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
правящий собственное объявление (пункт «Редактировать» в контекстном меню
карточки на «Моих объявлениях», см. [EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md)).
Модуль `BOARD` полностью online-only ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) —
нет ни Drift-таблицы объявления, ни черновика правки: до успешного ответа
сервера отредактированные данные существуют только в памяти bloc'а
(`_data`), нигде не сохраняясь.

## CURRENT

### Основной поток

1. Пользователь открывает `BoardAdCreatePage` с
   `BoardAdCreatePageArguments(ad: ad)` → `BoardAdCreateBloc()..add(BoardAdCreateEventStart(editingAd: args?.ad))`.
   `_onStart`: `_data = BoardAdCreateData.fromAd(editingAd)` — заполняет
   `editingAdId: ad.id`, `statusId: ad.statusId`, `selectedAdTypeId:
   ad.adTypeId`, `title`/`description`/`priceDigits`/`addressLine`/
   `phoneNationalNumber`/`localPhotoPaths` (из `ad.files`, все — уже
   существующие на сервере URL) из полей объявления, затем поверх
   догружаются справочники (страны/типы объявлений/виды/фермы+места), как и
   при создании.
2. Поскольку `_data.isEditMode` (`editingAdId != null`) истинно,
   `BoardAdCreateData.currentSteps` исключает шаги `type` и `animalCount` —
   пользователь не может сменить `adTypeId` в процессе правки, он остаётся
   тем, что был задан `fromAd` на шаге 1 (см. «Открытые вопросы»
   [UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md), где
   отмечено, что `fromAd` при этом не ограничивает `adTypeId` набором
   `Constants.boardAdTypeIds`, в отличие от создания).
3. Пользователь проходит оставшиеся шаги (описание/адрес/контакты/
   предпросмотр — предзаполнены значениями из объявления, редактируемые как
   обычно) и подтверждает на шаге `preview` → диспатчится
   `BoardAdCreateEventCreateAd()` — то же событие, что и при создании, ветка
   определяется полем `_data.isEditMode`, а не отдельным событием.
4. `_onCreateAd`: те же гварды, что и в create-ветке — `if (_data.onSending
   || !_data.contactsStepSuccess || !_data.addressStepSuccess ||
   !_data.descriptionStepSuccess) return;` — ни один из них не зависит от
   `isEditMode`. `adTypeId = _data.selectedAdTypeId` (уже зафиксирован на шаге
   1, не `null`, т.к. шаг `type` недостижим в edit-режиме — см. пункт 2).
   Список `animals` собирается той же веткой `switch`-подобной логики по
   `adTypeId` (1/5/6), что и при создании — из `_data.selectedAnimals`/
   `_data.animalData`, без разницы между режимами.
5. `_data = _data.copyWith(onSending: true); emit(BoardAdCreateSuccess(_data));` —
   кнопка подтверждения дизейблится (индикация отправки на UI).
   `localFiles`/`retainedFilesPaths` разделяются по схеме URL
   (`_isRemoteFilePath`) — для нетронутых фото объявления (все изначально
   `http(s)`, из `ad.files`) все попадают в `retainedFilesPaths`; новые,
   добавленные пользователем в процессе правки, — в `localFiles`.
6. `if (_data.isEditMode) { await _adRepository.updateAd(id:
   _data.editingAdId!, title: ..., price: ..., description: ..., files:
   localFiles.map((e) => File(e)).toList(), filesPaths: retainedFilesPaths,
   adTypeId: adTypeId, statusId: _data.statusId ?? 1, phone: ..., address:
   ..., whenWasFoundText: ..., animals: animals); }` — единственная строчка,
   отличающая этот путь от create-ветки (там — `_adRepository.createAd(...)`
   без `id`/`filesPaths`, с `statusId: 1` жёстко).
7. Внутри `AdRepository.updateAd`: строится multipart-запрос
   (`AdCreateRequest.fromData(..., filesPaths: filesPaths, includeFilesPaths:
   true)`), `POST ${Constants.boardServiceApi}/ads/{id}` с добавленным
   `_method: 'PUT'` в тело (`adCreateRequest.toJson()..addAll({'_method':
   'PUT'})`). Весь метод обёрнут в один `try/catch`:
   - если `rpcClient.call(message)` бросает исключение (сеть/таймаут/не-2xx
     HTTP — тот же механизм `DioClient`/`CustomDioClient`, что разобран в
     [UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md)) — оно
     попадает в `catch (e) { getIt<Talker>().error('updateAd Error:
     $e'); rethrow; }`;
   - если ответ получен без исключения, но `response['status'] != "1"` —
     `throw Exception(response['message']);` внутри `try` — попадает в тот же
     `catch`, логируется тем же образом, тоже `rethrow`.
   Оба пути **сходятся в одном и том же исходе** — `updateAd` завершается
   пробросом `Exception` наружу в обоих случаях; в отличие от
   [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)
   (инвентаризация), здесь нет двух разных наблюдаемых пользователем
   исходов — репозиторий уже унифицировал их на своём уровне.
8. Исключение всплывает из `await _adRepository.updateAd(...)` (шаг 6) в
   `catch (e, st)` того же `try` в `_onCreateAd`, что оборачивает обе ветки:
   `getIt<Talker>().handle(e, st); _data = _data.copyWith(onSending: false);
   emit(BoardAdCreateSuccess(_data));` — **тот же тип состояния**, что и при
   успехе (`BoardAdCreateSuccess`, не отдельный `BoardAdCreateFailure` —
   последний используется только в `catch` обработчика `_onStart`, никогда в
   `_onCreateAd`), `popRoute` и `navigateToStepIndex` — оба дефолтные
   (`false`/`null`).
9. `BoardAdCreatePage`'s `BlocConsumer.listener`: `if (state is!
   BoardAdCreateSuccess) return; if (state.popRoute) { ...context.pop(true);
   return; } if (state.navigateToStepIndex != null) { _changeStep(...); }` —
   ни одно из условий не выполняется для состояния из шага 8 — листенер не
   делает ничего. `builder` перестраивается на том же шаге (`preview`) с
   `onSending == false` — кнопка подтверждения снова активна.
10. Пользователь не получает никакого сообщения об ошибке — ни `SnackBar`, ни
    диалога, ни надписи на экране: единственное различие с состоянием «до
    нажатия» — данные формы (введённые правки) сохранены в `_data` (не
    сброшены), можно повторно нажать подтверждение без потери набранного
    текста. Ничего не указывает, применилась ли правка на сервере частично
    (например, если `updateAd` отказал уже после того, как сервер сохранил
    часть данных) — у клиента нет способа это узнать, ответ сервера при
    отказе используется только для текста исключения, залогированного через
    `Talker`, не показанного пользователю.

### Альтернативные потоки

- **Повторная попытка после отказа.** Пользователь может снова нажать
  подтверждение на том же шаге `preview` — `_data.onSending` уже `false`
  (сброшен на шаге 8), гварда `_onCreateAd` не блокирует повтор.
  `_adRepository.updateAd` вызывается заново с теми же (или изменёнными,
  если пользователь успел их поправить) параметрами — идемпотентности на
  уровне клиента нет, `guid`/аналог не передаётся (в отличие от, например,
  `Disposal.guid` в `ANIMAL`) — повторный вызов при повторном логическом
  отказе сервера просто повторяет тот же сценарий.
- **Пользователь закрывает визард без повторной попытки** (крестик/системная
  кнопка «назад» на первом видимом шаге) — `context.pop()`, без
  диспатча какого-либо события отмены. Поскольку объявление online-only,
  никакого локального черновика правки не остаётся — недоставленные правки
  теряются полностью, объявление на сервере остаётся в состоянии, в котором
  было до попытки правки (либо, если `updateAd` успела частично применить
  изменения на сервере, но упала уже на этапе чтения ответа, — в
  неопределённом промежуточном состоянии, не наблюдаемом клиентом).
- **`adTypeId` объявления — «Пропажа»(5)/«Найдено»(6), созданного не через
  мобильный визард.** `BoardAdCreateData.fromAd` не ограничивает `adTypeId`
  набором `Constants.boardAdTypeIds` — правка такого объявления доходит до
  того же самого `_onCreateAd`/`updateAd`, отказ ведёт к тому же исходу,
  описанному выше, независимо от типа объявления.
- **Несколько животных / файлы правки.** Список `animals` и разбиение
  `localFiles`/`retainedFilesPaths` строятся так же, как и при успешном
  сценарии правки (не входит в этот файл отдельно) — их состав не влияет на
  то, как обрабатывается отказ `updateAd`: любое исключение, независимо от
  того, на каком именно этапе построения multipart-тела или сетевого вызова
  оно возникло внутри `updateAd`, ловится тем же внешним `catch` в
  `_onCreateAd`.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чья правка не
  происходит: сервер либо не получил, либо не принял изменения; локально
  объявление вообще не кешируется (online-only), поэтому этим отказом не
  повреждается никакое локальное состояние — теряются только несохранённые
  правки, введённые в текущей сессии визарда, если пользователь не повторит
  попытку.

### Бизнес-правила

- `_onCreateAd` — единый обработчик на создание и правку; единственная точка
  ветвления по режиму — `if (_data.isEditMode) { updateAd(...) } else {
  createAd(...) }`, оба вызова обёрнуты одним и тем же внешним
  `try/catch`, с одинаковым телом `catch`.
- `AdRepository.updateAd` собственным `try/catch` превращает и сетевое
  исключение, и логический отказ сервера (`response['status'] != "1"`) в
  один и тот же проброшенный `Exception` — на уровне `_onCreateAd` (и,
  соответственно, пользователя) эти два происхождения неразличимы, `REJECTED`
  как отдельный исход не существует.
- Отказ `updateAd` не эмитит `BoardAdCreateFailure` — этот тип состояния в
  коде существует и обрабатывается `BoardAdCreatePage.build` отдельным
  экраном ошибки загрузки, но используется только в `catch` `_onStart`
  (отказ при открытии/загрузке визарда), никогда в `_onCreateAd`.
- Ни один канал (state, `SnackBar`, диалог) не сообщает пользователю о
  провале правки — единственный след отказа — запись в `Talker`
  (`getIt<Talker>().handle(e, st)`), не видимая нигде в UI.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — путь воспроизводится статическим
чтением кода целиком (`BoardAdCreateBloc._onCreateAd` → `AdRepository.updateAd`
→ `CustomDioClient.call`/`DioClient`) и частично подтверждён тестом (см.
«Связанные тесты» — только сетевое исключение на уровне репозитория; ветка
логического отказа сервера для `updateAd` и весь путь на уровне bloc'а для
edit-режима тестами не покрыты, см. ниже). Исправление (например, отдельное
состояние ошибки или сообщение в `SnackBar`, аналогично общей рекомендации
для [UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md)) в рамках
этого документирующего прохода не выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `BoardAdCreatePageArguments`, точка входа «Редактировать» из «Моих объявлений» | CURRENT | открывает визард с `editingAd: args?.ad` |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventStart>` (`_onStart`), `BoardAdCreateData.fromAd` | CURRENT | заполняет `_data` из существующего `Ad`, включая `editingAdId`/`statusId`/`localPhotoPaths` (все — удалённые URL) |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateData.isEditMode`, `.currentSteps` | CURRENT | `editingAdId != null` исключает шаги `type`/`animalCount` из визарда правки |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc.on<BoardAdCreateEventCreateAd>` (`_onCreateAd`) | CURRENT | единый обработчик создания/правки; edit-ветка — `await _adRepository.updateAd(id: _data.editingAdId!, ...)`; единственный `catch` эмитит `BoardAdCreateSuccess(_data)` без сигнала об ошибке |
| `lib/pages/board_ad_create/bloc/board_ad_create_state.dart` | `BoardAdCreateSuccess`, `BoardAdCreateFailure` | CURRENT | `Failure` используется только `_onStart`; `_onCreateAd` при отказе эмитит `Success`, неотличимый от успеха по типу |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.updateAd` | CURRENT | multipart `POST /ads/{id}` c `_method: 'PUT'`; единый `try/catch` превращает сетевое исключение и `status != "1"` в один и тот же проброшенный `Exception` |
| `lib/models/board/ad_create_request.dart` | `AdCreateRequest.fromData` | CURRENT | билдер multipart-тела, включая `filesPaths`/`includeFilesPaths` для сохранённых фото при правке |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) сетевые исключения — тот же механизм, что и в create-ветке |
| `lib/pages/board_ad_create/presentation/board_ad_create_page.dart` | `BlocConsumer.listener` | CURRENT | реагирует только на `state.popRoute`/`state.navigateToStepIndex` — ни один из них не установлен при отказе `updateAd`, листенер не делает ничего |

## Критерии приёмки

- Если `AdRepository.updateAd` бросает исключение (любого происхождения —
  сетевое или `response['status'] != "1"`), `_onCreateAd`'s `catch`
  безусловно выполняет: `Talker.handle(e, st)`, `_data.onSending = false`,
  `emit(BoardAdCreateSuccess(_data))` без `popRoute` и без
  `navigateToStepIndex`.
- Состояние после отказа — того же типа `BoardAdCreateSuccess`, что и при
  успешной правке, отличимо от успеха только отсутствием `popRoute: true`.
- Данные формы (`title`, `description`, `priceDigits`, `addressLine`,
  `phoneNationalNumber`, `selectedAnimals`/`animalData` и т.д.) в `_data`
  сохранены без изменений — повторный ввод не требуется.
- Экран визарда не закрывается (в отличие от успеха, где `popRoute: true`
  вызывает `context.pop(true)`), кнопка подтверждения снова активна
  (`onSending == false`).
- Ни `SnackBar`, ни диалог, ни какой-либо другой видимый пользователю канал
  не сообщают о том, что правка не удалась.
- Объявление на сервере ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) не
  гарантированно возвращается в исходное состояние — клиент не выполняет
  никакой компенсирующей проверки/отката после отказа `updateAd`.

## Связанные тесты

- `test/repositories/ad_repository_test.dart`, group `'UC-138 — AdRepository.updateAd
  ERROR'`, test `'updateAd: сетевое исключение -> rethrow'` — подтверждает
  только сетевое исключение (`farmRpcClient.call` → `thenThrow`) →
  `expectLater(..., throwsA(isA<Exception>()))`. **Ветка логического отказа
  сервера (`response['status'] != "1"`) для `updateAd` отдельным тестом не
  покрыта** — в отличие от create-ветки, для которой есть парный тест
  `'createAd: status != "1" -> Exception с сообщением сервера, rethrow'` в
  group `'UC-136 — AdRepository.createAd ERROR'` того же файла; для
  `updateAd` такого теста нет (подтверждено чтением файла — в group
  `'UC-138'` ровно один `test(...)`).
- **TBD — теста нет** на уровне bloc'а
  (`test/pages/board_ad_create_bloc_test.dart`) конкретно для edit-режима
  `_onCreateAd`, ни для успеха, ни для ошибки: в этом файле есть group
  `'UC-135 — BoardAdCreateBloc._onCreateAd (создание)'` и group `'UC-136 —
  BoardAdCreateBloc._onCreateAd ERROR (известный дефект — без сообщения об
  ошибке)'`, но оба теста в них ведут через `BoardAdCreateEventChangeAdType`
  без `editingAd` — `_data.isEditMode` в них всегда `false`, ветка
  `updateAd` не вызывается ни в одном тесте файла. Единственный тест,
  касающийся edit-режима, — group `'BoardAdCreateEventStart'`, test
  `'editingAd задан -> данные формы предзаполнены через
  BoardAdCreateData.fromAd'` — проверяет только предзаполнение формы
  (`data.isEditMode == true`, `data.editingAdId == 42`), не сам вызов
  `updateAd` и тем более не его отказ.

## Открытые вопросы и ограничения

- **Тот же класс дефекта, что и у публикации
  ([UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md)), в
  edit-режиме того же обработчика.** `_onCreateAd` не различает создание и
  правку в обработке ошибки — единственная разница между ветками —
  `createAd`/`updateAd` и их параметры; сам `catch`, отсутствие сигнала об
  ошибке и тип эмитируемого состояния идентичны. Не переразбирается здесь
  повторно по существу — см. [UC-136](UC-136-ACTOR-1-EVT-68-ENT-18-CREATE_ERROR-IN-BOARD.md)
  для общего описания дефекта.
- **Асимметрия тестового покрытия репозитория.** Для `createAd` есть
  отдельный тест на логический отказ сервера (`status != "1"`), для
  `updateAd` — только на сетевое исключение; поведение кода для обеих веток
  `updateAd` идентично (подтверждено чтением — единый `try/catch`), но
  логическая ветка `updateAd` не имеет собственного регрессионного теста.
- **Нет идемпотентности повторной отправки правки.** В отличие от некоторых
  сущностей `ANIMAL` (например `Disposal.guid`), запрос `updateAd` не несёт
  клиентского идентификатора попытки — повторная отправка после отказа
  неотличима на сервере от новой правки; не разбирается глубже в рамках
  этого файла.
- **Частичное применение правки на сервере не проверяется.** Если сервер
  успел изменить часть данных объявления до того, как `updateAd` получила
  ошибку (например, на этапе чтения/парсинга ответа уже после фактического
  сохранения), клиент не выполняет никакой сверки — у `_data` в bloc'е нет
  способа узнать, что реально сохранилось на сервере. Не воспроизведено
  эмпирически, не разбирается глубже.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`BoardAdCreateBloc._onCreateAd` → `AdRepository.updateAd` →
  `CustomDioClient.call`/`DioClient`) и частично подтверждён тестом с
  замоканным `ApiClient` (сетевое исключение, см. «Связанные тесты»).
