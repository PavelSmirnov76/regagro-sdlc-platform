# UC-146 — Автоматический запрос просмотра карточки объявления отказывает без обработки, но саму карточку это не блокирует

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же экран, что описан в [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md) —
детальная карточка объявления — при монтировании автоматически вызывает
`AdDetailCubit(model)..viewAd()` (`lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart`),
без ожидания результата и без обработки ошибки: возвращаемый `viewAd()`
`Future<void>` не awaited в `create:` и не имеет ни одного attached
`catchError`. Здесь `AdRepository.viewAd` (в отличие от `AdDetailCubit.viewAd`)
завершается неуспехом — либо сетевым исключением, либо логическим отказом
сервера (`response['status'] != "1"`), оба случая репозиторий сам ловит
собственным `try/catch` и безусловно перебрасывает (`rethrow`) после
логирования в `Talker`. `AdDetailCubit.viewAd` этот `rethrow` не перехватывает
вообще — исключение покидает `viewAd()` необработанным, `emit`, увеличивающий
`viewsCount`, не достигается.

Ключевая находка, проверенная отдельно чтением всего экрана: дело не только в
том, что карточка была загружена раньше, чем случился этот отказ — она
**структурно не зависит** от состояния `AdDetailCubit` вовсе, в успехе или в
отказе одинаково. `BoardAdDetailView.build` передаёт в
`BoardAdDetailPopulated` именно `model` — аргумент конструктора `BoardAdDetailView`,
не `context.watch<AdDetailCubit>().state.ad`. Ни в `board_ad_detail_view.dart`,
ни в `board_ad_detail_populated.dart`, ни в `board_ad_detail_page.dart` нет ни
одного `BlocBuilder`/`BlocConsumer`, читающего `AdDetailState`
(`grep -rn "AdDetailCubit" lib/` находит только точку создания `create: (_) =>
AdDetailCubit(model)..viewAd()` и один закомментированный
`context.read<AdDetailCubit>().toggleAdFavourite(...)` в `actions` AppBar'а).
Cubit существует исключительно ради побочного эффекта сетевого вызова —
его состояние, посчитанное или нет, никем не читается.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково: ни `AdDetailCubit.viewAd`, ни
`AdRepository.viewAd` не проверяют статус авторизации ни в одной ветке
(`grep -n "isAuthorized\|AuthRepository" lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart
lib/repositories/board/ad_repository.dart` не находит совпадений). Отказ
наступает без какого-либо отдельного действия пользователя — `viewAd()`
запускается автоматически при монтировании экрана, тем же образом, что и в
успешном сценарии [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md).

## CURRENT

### Основной поток

1. Пользователь (гость или авторизованный) открывает детальную карточку
   объявления — тапом по карточке в ленте (`BoardPage`/`board_populated.dart`),
   «Моих объявлениях» или «Избранном» (`Routes.boardAdDetail`), либо из шапки
   переписки (`Routes.messagesBoardAdDetail`) — оба маршрута монтируют один и
   тот же `BoardAdDetailPage` (`lib/pages/routes.dart`). `BoardAdDetailPage.build`
   резолвит `BoardAdDetailPageArguments`/`MessagesPageArgs` по имени активного
   маршрута и строит `BoardAdDetailView(model: ad)` — `model` уже содержит
   `viewsCount` со значения, посчитанного сервером **до** этого открытия (для
   входа из ленты — через `Ad.toDetailModel()` на объекте, полученном ранее
   `BoardCubit.load()`).
2. `BoardAdDetailView.build`: `BlocProvider(create: (_) =>
   AdDetailCubit(model)..viewAd(), child: AppScaffold(..., child:
   BoardAdDetailPopulated(ad: model)))` — `viewAd()` вызывается сразу при
   создании кубита, каскадом (`..`), без `await` и без какого-либо обработчика
   ошибки на этом уровне; возвращаемое значение каскада — сам `AdDetailCubit`,
   не `Future`, поэтому вызывающий код структурно не может ни дождаться, ни
   перехватить результат `viewAd()`, даже если бы захотел.
3. `AdDetailCubit.viewAd()` (`lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart`):
   `await _adRepository.viewAd(state.ad.adId);` — вызов **не обёрнут** в
   `try/catch` во всём методе; следующая строка — `emit(state.copyWith(ad:
   state.ad.copyWith(viewsCount: state.ad.viewsCount + 1)))`.
4. `AdRepository.viewAd(id)` (`lib/repositories/board/ad_repository.dart`)
   строит `ApiMessage(link: '${Constants.boardServiceApi}/ads/$id/view',
   method: ApiMethod.post)` и вызывает `rpcClient.call(message)` **внутри
   собственного** `try/catch`. В этом сценарии вызов заканчивается неуспехом
   одним из двух путей, оба сходятся в одном и том же `catch`:
   - сетевое исключение — `CustomDioClient.call`
     (`lib/network/api_client/custom_dio_client.dart`) оборачивает
     `AuthInterceptor.getTokenDataByPath`/`dio.request(...)` своим `try/catch`:
     любая ошибка (сеть недоступна, таймаут, либо не-2xx ответ — `DioClient`,
     `lib/network/dio_client.dart`, не переопределяет `validateStatus`, поэтому
     Dio по умолчанию бросает `DioException` вне 200–299) логируется через
     `getIt.get<Talker>().error('CustomDioClient: call: $e')` и безусловно
     перебрасывается (`rethrow`);
   - логический отказ без исключения — `CustomDioClient.call` получает
     обычный HTTP 200-ответ с телом, не содержащим `data`/`animal_exits`, но с
     `status: 'error'` — возвращает его как есть, без исключения;
     `AdRepository.viewAd` получает этот `response` без ошибки, но `if
     (response['status'] == "1") return; else throw
     Exception(response['message']);` бросает `Exception` сам.
   В обоих случаях `AdRepository.viewAd`'s собственный `catch (e) {
   getIt<Talker>().error('viewAd Error: $e'); rethrow; }` логирует ошибку и
   безусловно перебрасывает её дальше — с точки зрения вызывающего кода оба
   происхождения неотличимы, наружу выходит один и тот же тип исключения.
5. Исключение всплывает из `await _adRepository.viewAd(...)` (шаг 3) прямо из
   `AdDetailCubit.viewAd()` — метод не содержит `try/catch`, поэтому
   возвращаемый `Future<void>` завершается с ошибкой; строка `emit(...)`,
   увеличивающая `viewsCount`, не выполняется.
6. Поскольку вызов на шаге 2 — необслуженный (`unawaited`) каскад внутри
   `BlocProvider.create`, эта ошибка становится unhandled/unobserved rejection
   встроенного в Dart `Future` — она не прерывает построение виджета, не
   всплывает в `build()`, не показывает `SnackBar`/диалог. `main()`
   (`lib/main.dart`) вызывает `runApp(const MyApp())` напрямую — строка
   `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const MyApp()), ...)`
   присутствует в файле, но закомментирована — то есть даже дополнительного
   зонового перехвата этой ошибки за пределами уже сработавшего
   `Talker.error` внутри `AdRepository.viewAd` (шаг 4) в приложении не
   настроено.
7. `BoardAdDetailPopulated` (переданная в `BoardAdDetailView.build` как
   `BoardAdDetailPopulated(ad: model)`) рендерится с тем же `model`, что был
   передан в конструктор `BoardAdDetailView` на шаге 1 — фотографии, цена,
   заголовок, адрес, контакты продавца, кнопки звонка/чата, блок животного
   строятся исключительно из этого объекта. Экран не содержит ни одного
   `BlocBuilder<AdDetailCubit, AdDetailState>`/`context.watch<AdDetailCubit>()` —
   отказ `viewAd()` на шаге 5 не имеет наблюдаемого эффекта на эту отрисовку:
   она была бы идентичной и при успехе, и при отказе, и при ещё не
   завершившемся вызове.
8. `viewsCount` (виден пользователю только когда `hasViews = ad.viewsCount >
   0`, в `BoardAdDetailPopulated.build`) читается из того же `widget.ad`
   (снова — конструкторный `model`, не `state.ad` кубита), поэтому даже без
   отказа увеличенное значение из `AdDetailState` не попало бы в этот текст —
   но в этом сценарии оно и не вычислено вовсе (шаг 5).

### Альтернативные потоки

- **Вход из шапки переписки (`Routes.messagesBoardAdDetail`).** Тот же
  `BoardAdDetailPage`, тот же код-путь целиком — `BoardAdDetailPage.build`
  резолвит `BoardAdDetailPageArguments` через `MessagesPageArgs.ad`, дальше
  шаги 2–8 идентичны.
- **Гость (нет активной сессии).** Ни один шаг не проверяет авторизацию —
  поведение при отказе идентично для гостя и авторизованного пользователя.
- **`toggleAdFavourite` — не задействован в этом сценарии.** Единственный
  вызов `context.read<AdDetailCubit>().toggleAdFavourite(model.adId)`
  закомментирован в `board_ad_detail_view.dart` (действие «избранное» из
  AppBar'а карточки недостижимо из UI — отдельная находка, зафиксированная в
  `test/pages/ad_detail_cubit_test.dart` как «мёртвый код»); этот отказ
  `viewAd()` не связан с ней и не влияет на неё.
- **Сообщение об ошибке нигде не появляется ни разу за весь путь.** В отличие
  от [UC-144](UC-144-ACTOR-5-EVT-72-ENT-18-READ_ERROR-IN-BOARD.md) (лента), где
  хотя бы `BoardState.isError`/`errorMessage` вычисляются (просто не читаются
  виджетами), здесь `AdDetailState` не имеет подобных полей вовсе — состояние
  кубита при отказе `viewAd()` попросту не меняется ни в одном поле.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad / `BoardAdDetailModel`) —
  единственная сущность, которую сценарий пытается изменить (`viewsCount` на
  сервере через `POST /ads/{id}/view`) и единственная, что отображается
  экраном; при этом отказе `viewsCount` не меняется ни на сервере, ни локально
  ни в одном представлении (`Ad` в ленте, `BoardAdDetailModel` в `model`,
  `AdDetailState.ad` в кубите) — все три остаются равны значению,
  вычисленному до открытия карточки.

### Бизнес-правила

- `AdRepository.viewAd` — единственная точка в этом сценарии, где вообще есть
  обработка ошибки (`try/catch` + `Talker.error` + `rethrow`); `AdDetailCubit.viewAd`
  и место его вызова (`BlocProvider.create`) обе оставляют исключение
  полностью необработанным дальше по цепочке.
- Отказ этого сетевого вызова никогда не влияет на то, показывается ли сама
  карточка объявления — она построена из аргумента конструктора экрана
  (`model`), полученного до `viewAd()` и не связанного с состоянием
  `AdDetailCubit` ни в одном виджете дерева.
- Инкремент `viewsCount` в этом сценарии — фактически fire-and-forget
  телеметрия без единого потребителя в UI: даже при успехе увеличенное
  значение осело бы только в `AdDetailState.ad.viewsCount`, которое ни один
  виджет не читает (см. «Назначение»); при отказе оно не вычисляется вовсе, и
  разница между двумя исходами для пользователя неразличима.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий прослеживается статическим
чтением кода целиком (`BoardAdDetailView.build` → `AdDetailCubit.viewAd` →
`AdRepository.viewAd` → `CustomDioClient.call`/`DioClient`) и подтверждён
двумя запущенными тестами на двух уровнях (кубит и репозиторий, см.
«Связанные тесты»). Находки, перечисленные в «Открытые вопросы и
ограничения» (отсутствие глобального перехвата unhandled-ошибки, отсутствие
раздельного теста для сетевой ветки отказа репозитория, отсутствие
виджет-уровневого теста) не блокируют выполнение сценария — экран не падает
и продолжает отображаться.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | `BoardAdDetailView.build` (`BlocProvider.create: (_) => AdDetailCubit(model)..viewAd()`) | CURRENT | точка запуска сценария — вызов `viewAd()` без `await` и без обработчика ошибки; строит `BoardAdDetailPopulated(ad: model)` из конструкторного аргумента, не из состояния кубита |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_page.dart` | `BoardAdDetailPage.build` | CURRENT | резолвит `model` из `BoardAdDetailPageArguments`/`MessagesPageArgs` в зависимости от маршрута (`Routes.boardAdDetail`/`Routes.messagesBoardAdDetail`) |
| `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` | `AdDetailCubit.viewAd` | CURRENT | предмет этого файла — вызывает `_adRepository.viewAd(...)` без `try/catch`; исключение покидает метод необработанным, `emit` не достигается |
| `lib/pages/board_ad_detail/cubit/ad_detail_state.dart` | `AdDetailState` | CURRENT | freezed-состояние, единственное поле `ad`; не имеет `isError`/`errorMessage`-подобных полей |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel`, `BoardAdDetailModelMapper.toDetailModel` | CURRENT | DTO экрана (freezed, полный `props`, без бага `Ad.props` из [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)); `viewsCount` копируется из `Ad` один раз при построении `model`, не обновляется этим сценарием |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_populated.dart` | `BoardAdDetailPopulated.build` | CURRENT | рендерит экран из `widget.ad` (конструкторный параметр); не содержит `BlocBuilder`/`context.watch`, читающего `AdDetailState` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.viewAd` | CURRENT | `POST /ads/{id}/view`; собственный `try/catch` — логирует через `Talker` и безусловно перебрасывает (`rethrow`) как сетевые исключения, так и логический `response['status'] != "1"` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует и безусловно перебрасывает (`rethrow`) любое исключение из `dio.request`/`AuthInterceptor`; при HTTP-успехе с `Map` без `data`/`animal_exits` и явным `status: 'error'` возвращает ответ как есть, без исключения |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/main.dart` | `main()` | CURRENT | `runApp(const MyApp())` без `runZonedGuarded`; вызов `runTalkerZonedGuarded(...)` присутствует в файле, но закомментирован — unhandled-ошибка из шага 6 не получает дополнительного перехвата на этом уровне |
| `lib/pages/board/presentation/widgets/board_populated.dart` | обработчик `onTap` карточки | CURRENT | вход A — строит `BoardAdDetailPageArguments(ad: ad.toDetailModel())` и переходит на `Routes.boardAdDetail` |
| `lib/pages/messages/presentation/messages_view.dart` | `_MessagesHeaderTitle.build` (`onTap`) | CURRENT | вход B — переход на `Routes.messagesBoardAdDetail` из шапки переписки |

## Критерии приёмки

- Если `AdRepository.viewAd` бросает исключение (по любой из двух причин —
  сетевой сбой, пойманный и переброшенный `CustomDioClient.call`, либо
  логический `response['status'] != "1"`, пойманный и переброшенный самим
  `AdRepository.viewAd`), `Future`, возвращаемый `AdDetailCubit.viewAd()`,
  завершается с тем же исключением — `expectLater(cubit.viewAd(),
  throwsA(isA<Exception>()))`.
- После такого отказа `cubit.state.ad.viewsCount` остаётся равным значению до
  вызова — `emit`, увеличивающий счётчик, не достигается.
- Экран (`BoardAdDetailPopulated`, смонтированный через
  `BoardAdDetailView`/`BoardAdDetailPage`) продолжает отображаться с теми же
  данными независимо от исхода `viewAd()` — ни фотографии, ни цена, ни
  контакты, ни кнопки звонка/чата не зависят от состояния `AdDetailCubit`.
- Отказ `viewAd()` не производит ни одного видимого пользователю сообщения
  (`SnackBar`, диалог, индикатор) — единственный след отказа во всём
  приложении — запись `Talker.error('viewAd Error: $e')` внутри
  `AdRepository.viewAd`.

## Связанные тесты

- `test/pages/ad_detail_cubit_test.dart`, group `'UC-146 — AdDetailCubit.viewAd
  ERROR (известный дефект — без try/catch)'`, test `'viewAd бросает ->
  исключение пробрасывается, счётчик не меняется, но карточку это не
  блокирует'` — мокает `adRepository.viewAd(9)` через
  `thenThrow(Exception('network error'))`, проверяет
  `expectLater(cubit.viewAd(), throwsA(isA<Exception>()))` и
  `cubit.state.ad.viewsCount == 3` (неизменно), с явным `reason: 'emit после
  awaited-исключения не достигается'`.
- `test/repositories/ad_repository_test.dart`, group `'UC-146 —
  AdRepository.viewAd ERROR'`, test `'status != "1" -> Exception, rethrow'` —
  мокает `farmRpcClient.call(any())` ответом `{'status': '0', 'message':
  'err'}`, проверяет `expectLater(repository.viewAd(7),
  throwsA(isA<Exception>()))`. Покрывает только логическую ветку отказа
  (см. «Открытые вопросы» — сетевая ветка, где исключение бросает сам
  `rpcClient.call`, отдельно на уровне репозитория не воспроизведена).
- Старая нумерация групп (`UC-146` в обоих файлах, для разных слоёв — кубит и
  репозиторий) относится к прежней схеме id и не переименована на момент
  написания этой спеки — переименование под новый id (`UC-146` для обоих)
  выполняется отдельным контролируемым проходом, не этой задачей; якорь
  `grep -r "UC-146" test/` заработает только после него.

**TBD — теста нет** на виджет-уровень (`BoardAdDetailView`/
`BoardAdDetailPopulated`) — ни один существующий тест не монтирует сам
экран и не проверяет, что он продолжает рендериться после того, как
`viewAd()` бросает; оба существующих теста работают только с
`AdDetailCubit`/`AdRepository` напрямую, не с деревом виджетов.

## Открытые вопросы и ограничения

- **Судьба unhandled-ошибки после шага 6 не подтверждена эмпирически.**
  Отсутствие `runZonedGuarded`/активного `runTalkerZonedGuarded` в `main.dart`
  установлено чтением кода (закомментированная строка), но то, как именно
  Flutter-рантайм в реальном запуске обрабатывает необслуженный `Future`,
  возникший из каскадного вызова внутри `BlocProvider.create` (печать в
  консоль отладки через встроенный обработчик `PlatformDispatcher`, полное
  игнорирование, либо что-то ещё) — этой спекой не воспроизведено на живом
  запуске приложения, только статическим чтением.
- **Сетевая ветка отказа `AdRepository.viewAd` не покрыта отдельным
  репозиторным тестом.** Единственный существующий тест
  (`test/repositories/ad_repository_test.dart`) мокает только логический
  `response['status'] != "1"`; ветка, где сам `rpcClient.call` бросает
  исключение (например `DioException` от таймаута/недоступной сети), на
  уровне `AdRepository` отдельно не воспроизведена — предполагается
  идентичной по итоговому поведению (`rethrow` после `Talker.error`), но не
  подтверждена тестом именно в этой конфигурации.
- **`AdDetailCubit` — состояние без единого потребителя, в любом исходе.**
  Не только при отказе (предмет этого файла), но и при успехе `viewAd()`
  прирост `viewsCount` в `AdDetailState` не читается ни одним виджетом экрана
  — `BoardAdDetailPopulated` строится из конструкторного `model`, не из
  состояния кубита. Является ли отсутствие `BlocBuilder` на этом экране
  осознанным решением (счётчик просмотров — чистая телеметрия без
  необходимости в UI-фидбэке) или недосмотром — ничем в коде/комментариях не
  зафиксировано; в любом случае этот отказ не создаёт дополнительного,
  отличного от «успеха» пользовательского эффекта.
- Не проверено эмпирически против реального бэкенда — вывод сделан
  статическим чтением кода (`AdDetailCubit.viewAd` → `AdRepository.viewAd` →
  `CustomDioClient.call` → `DioClient`) и подтверждён модульными тестами с
  замоканными `AdRepository`/`ApiClient` (см. «Связанные тесты»); точная
  форма реального сетевого сбоя (таймаут, DNS, не-2xx ответ) и точная форма
  реального логического отказа сервера этой спекой не верифицированы.
