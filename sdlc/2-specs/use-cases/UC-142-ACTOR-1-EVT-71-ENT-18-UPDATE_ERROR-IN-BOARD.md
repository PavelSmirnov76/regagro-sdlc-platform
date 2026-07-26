# UC-142 — Переключение «избранного» на карточке объявления отказывает — необработанное исключение всплывает из Cubit

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Пользователь тапает сердечко на карточке объявления — единственный реально
подключённый путь переключения избранного, общий для трёх экранов (лента,
«Мои объявления», «Избранное»), все три построены на одном виджете
`BoardPopulated` и одном `BoardCubit` (см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md),
[EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md)). `BoardCubit.toggleAdFavourite`
вызывает `AdRepository.setAdFavourite` без собственного `try/catch`; сам вызов
из виджета (`InkWell.onTap` в `board_populated.dart`) тоже не оборачивает его
ни в `await`, ни в обработку ошибки. Если запрос к серверу отказывает (сетевое
исключение либо тело ответа с логическим отказом), исключение проходит через
`AdRepository`/`BoardCubit` необработанным и в итоге становится необработанной
асинхронной ошибкой — без какого-либо пользовательского уведомления, без
отката/изменения иконки (она и не менялась оптимистично — `emit` в этом
сценарии не достигается вовсе).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
как и зафиксировано в его собственном файле («BOARD… инициирует
[EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md) (добавление/снятие
с избранного) через `BoardCubit`»). Ни `BoardCubit`, ни `BoardPopulated`, ни
`AdRepository` не содержат ни одной проверки статуса авторизации
(`grep` по `lib/pages/board/` на `isAuthorized`/`AuthRepository` не находит
ни одного вхождения) — код технически не исключает вызов тем же путём и без
сессии, но это не исследуется глубже в рамках этого файла, так как актор
зафиксирован заданием и собственным описанием
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md).

## CURRENT

### Основной поток

1. Пользователь видит карточку объявления на одном из трёх экранов, все три
   используют один и тот же виджет `BoardPopulated` и один и тот же
   `BoardCubit`, различающийся только параметрами `load()`:
   - лента — `BoardView` (`lib/pages/board/presentation/widgets/board_view.dart`),
     `BoardCubit()..load(page: 1)`;
   - «Мои объявления» — `MyAdsView`
     (`lib/pages/my_ads/presentation/my_ads_view.dart`),
     `BoardCubit()..load(page: 1, isMyAds: true)`;
   - «Избранное» — `FavouriteAdsView`
     (`lib/pages/favourite_ads/presentation/favourite_ads_view.dart`),
     `BoardCubit()..load(page: 1, isFavouriteAds: true)`.
2. Тап по сердечку — `InkWell` внутри `BoardPopulated.build`
   (`lib/pages/board/presentation/widgets/board_populated.dart`): `onTap: () {
   context.read<BoardCubit>().toggleAdFavourite(ad.id); }` — колбэк
   синхронный (`VoidCallback`), возвращаемый `Future<void>` не сохраняется, не
   `await`-ится и не имеет `.catchError`/`try` вокруг вызова.
3. `BoardCubit.toggleAdFavourite(id)`:
   - вычисляет целевое направление переключения:
     `!state.ads.any((ad) => ad.id == id && ad.isFavourite)` — `true`, если в
     текущем списке нет объявления с этим `id` и `isFavourite == true`
     (включая случай, когда `id` вообще отсутствует в списке — тогда
     результат тоже `true`, трактуется как «добавить»);
   - `await _adRepository.setAdFavourite(id, <вычисленное значение>);` — этот
     `await` не обёрнут ни в `try`, ни в `on`, вообще нигде внутри метода.
4. `AdRepository.setAdFavourite(id, isFavourite)` — сама эта функция тоже без
   `try/catch`: `isFavourite ? await addAdToFavouritesFromApi(id) : await
   removeAdFromFavouritesFromApi(id);` — делегирует целиком одному из двух
   методов и ждёт его результат.
5. Внутри `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi`
   (структурно идентичны, отличаются только методом/эндпоинтом — POST
   `${Constants.boardServiceApi}/selected-ads` с `{'ad_id': id}` против DELETE
   `${Constants.boardServiceApi}/selected-ads/$id`) — в этом сценарии
   `rpcClient.call(message)` либо бросает исключение, либо возвращает ответ,
   который метод сам интерпретирует как отказ (`response['status'] != "1"`).
   В любом из двух случаев (см. «Альтернативные потоки», ветки а/б) сработает
   `catch (e) { getIt<Talker>().error('...Error: $e'); rethrow; }` — тело
   каждого из двух методов целиком обёрнуто одним `try`.
6. Исключение, переброшенное `rethrow` на шаге 5, покидает
   `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi` необработанным,
   затем покидает `setAdFavourite` (шаг 4, тоже без `try/catch`), затем
   покидает `toggleAdFavourite` (шаг 3) — ни один `emit` внутри
   `toggleAdFavourite` не достигается: ни ветка `isOnlyFavouriteAds`
   (удаление карточки из списка «Избранное»), ни ветка обновления иконки
   (`ad.copyWith(isFavourite: !ad.isFavourite)`).
7. Поскольку вызов на шаге 2 не был `await`-нут и не имел обработчика ошибок,
   исключение, покинувшее `toggleAdFavourite`, становится необработанной
   асинхронной ошибкой Dart-рантайма (`Future`, брошенный без подписчика на
   ошибку). `lib/main.dart` не оборачивает `runApp(const MyApp())` в
   `runZonedGuarded` (единственная альтернатива закомментирована —
   `runTalkerZonedGuarded`), и нигде в `lib/` не переопределены ни
   `FlutterError.onError`, ни `PlatformDispatcher.instance.onError` (`grep`
   по всему `lib/` не находит ни одного вхождения) — значит обработка
   полностью отдана дефолтному поведению корневой Zone: ошибка не всплывает
   ни в один пользовательский UI-канал (`SnackBar`, диалог, состояние
   Cubit'а), не сообщается в `Talker` на этом уровне (только внутри
   `AdRepository`, на шаге 5, до этой точки) и не прерывает работу текущего
   экрана — построение виджета уже завершилось к моменту, когда исключение
   реально возникает (оно асинхронно, вне фазы build/layout/paint, которую
   framework перехватывает через `FlutterError.onError` для синхронных
   ошибок).
8. Наблюдаемый пользователем итог: тап по сердечку не производит видимого
   эффекта — иконка не переключается (не было оптимистичного обновления,
   `emit` не достигнут), никакого сообщения об ошибке не показывается.
   Единственный след отказа — запись в `Talker` изнутри
   `AdRepository.addAdToFavouritesFromApi`/`.removeAdFromFavouritesFromApi`
   (шаг 5) и, в зависимости от платформы/окружения, необработанное исключение
   в логе/консоли (см. «Открытые вопросы»).

### Альтернативные потоки

- **Ветка (а) — сетевое исключение.** `CustomDioClient.call`
  (`lib/network/api_client/custom_dio_client.dart`) оборачивает
  `AuthInterceptor.getTokenDataByPath`/`dio.request(...)` собственным
  `try/catch`: любое исключение (недоступность сети, таймаут, либо любой
  не-2xx HTTP-ответ — `DioClient` не переопределяет `validateStatus`, значит
  Dio по умолчанию бросает `DioException` вне 200–299) логируется через
  `getIt.get<Talker>().error('CustomDioClient: call: $e')` и
  безусловно перебрасывается (`rethrow`). Это исключение всплывает из
  `rpcClient.call(message)` на шаге 5 основного потока, идёт по тому же пути
  дальше.
- **Ветка (б) — логический отказ сервера без исключения на уровне HTTP.**
  `CustomDioClient.call` возвращает ответ **как есть**, со `status: 'error'`,
  только в одной узкой ветке: тело ответа — `Map<String, dynamic>` **без**
  ключей `data`/`animal_exits` и с явным `response.data['status'] ==
  'error'`. Любая другая форма ответа без этих ключей (например,
  `{"status": "0", ...}` — не литеральная строка `'error'`) принудительно
  получает `status: "1"` внутри `CustomDioClient.call` (см. «Открытые
  вопросы») — то есть в реальном production-стеке ветка «сервер логически
  отказал» внутри `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi`
  (`if (response['status'] == "1") return; else throw
  Exception(response['message']);`) достижима только при этом узком формате
  ответа. Тест на уровне репозитория (см. «Связанные тесты») обходит эту
  узость, подставляя ответ `{'status': '0', ...}` напрямую через мок
  `ApiClient`, минуя `CustomDioClient` целиком — так проверяется реакция
  `AdRepository`, а не факт, что сервер реально присылает именно такую форму
  ответа.
- **Обе ветки (а) и (б) сходятся к одному и тому же наблюдаемому исходу** —
  необработанное исключение из `toggleAdFavourite`, без отдельной
  `REJECTED`-ветки: код не различает «сервер осознанно отказал» и
  «технический сбой» ни на одном вышестоящем уровне (тот же паттерн, что и в
  [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md) для
  модуля `ANIMAL`) — в отличие от того сценария, здесь ни одна из веток не
  удаляет никаких локальных данных (в BOARD нет локального хранилища, см.
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md), «Инварианты»), поэтому обе
  ветки одинаково безопасны с точки зрения потери данных — разница только в
  том, что именно попало в лог `Talker`.
- **Направление «снятие с избранного» (`isFavourite: true → false`,
  `removeAdFromFavouritesFromApi`)** — структурно идентичный код (тот же
  `try/catch(e) { Talker.error; rethrow; }`, тот же безусловный `await` без
  обработки в `toggleAdFavourite`), подтверждено чтением кода; ни один из
  двух связанных тестовых файлов не проверяет отказ именно для этого
  направления — обе группы `UC-142` (см. «Связанные тесты») используют
  только направление «добавить» (`setAdFavourite(id, true)`).
- **Экран «Избранное» (`isOnlyFavouriteAds == true`)** — ветка `emit`,
  убирающая карточку из списка целиком, в этом сценарии тоже не достигается
  (исключение прерывает метод раньше) — карточка остаётся видимой в списке
  «Избранное», как будто тап не производился.
- **`AdDetailCubit.toggleAdFavourite`** (`lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart`)
  воспроизводит тот же паттерн (`await _adRepository.setAdFavourite(...)` без
  `try/catch`), но кнопка, которая могла бы его вызвать, закомментирована в
  `board_ad_detail_view.dart` (`// context.read<AdDetailCubit>().toggleAdFavourite(model.adId);`)
  — недостижимо из реального UI (см. [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md)),
  вне рамок этого use-case, не разбирается глубже.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — единственная затронутая
  сущность; в этом сценарии не изменяется вовсе (ни локально — модуль
  online-only без Drift-таблицы, ни в памяти — `emit` не достигается), в
  отличие от happy-path того же события, где `Ad.isFavourite`
  пересобирается в памяти (но и там не перерисовывается — отдельный,
  независимый дефект `Ad.props`, см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)
  и `BoardState`, не относится к этому `ERROR`-сценарию, поскольку здесь
  до пересборки `Ad` дело не доходит).

### Бизнес-правила

- Направление переключения не хранится отдельным полем — вычисляется каждый
  раз из текущего состояния списка: `!state.ads.any((ad) => ad.id == id &&
  ad.isFavourite)`; если объявление с данным `id` не найдено в `state.ads`,
  результат — `true` («добавить»).
- Нет отдельной обработки «сервер отказал» вместо «сеть недоступна» — оба
  случая проходят один и тот же `catch/rethrow` в
  `AdRepository.addAdToFavouritesFromApi`/`.removeAdFromFavouritesFromApi`, и
  затем распространяются одинаково необработанными через `setAdFavourite` и
  `toggleAdFavourite`.
- Ни `BoardCubit`, ни `AdRepository.setAdFavourite` не содержат собственного
  `try/catch` — единственный перехват во всей цепочке — внутри
  `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi`, и он существует
  только чтобы залогировать через `Talker` и тут же перебросить исключение
  дальше (`rethrow`), не для того чтобы его погасить.
- Тап по сердечку в виджете (`InkWell.onTap`) не `await`-ит и не оборачивает
  вызов `toggleAdFavourite` — единая точка дефекта, общая для всех трёх
  экранов, использующих `BoardPopulated`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий воспроизводится статическим
чтением кода целиком: `InkWell.onTap` (`board_populated.dart`) →
`BoardCubit.toggleAdFavourite` → `AdRepository.setAdFavourite` →
`addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi` →
`CustomDioClient.call`/`DioClient` — и подтверждён запущенными тестами на
уровне cubit'а и репозитория (см. «Связанные тесты», направление «добавить»
зелёное на момент написания); направление «снять» и реальный
Zone-наблюдаемый эффект необработанного исключения тестами не покрыты (см.
«Открытые вопросы»). Исправление (обернуть вызов в `try/catch` в
`BoardCubit.toggleAdFavourite` и/или в `onTap` виджета) в рамках этого
документирующего прохода не выполняется — это фиксация уже существующего
кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated.build` (`InkWell.onTap` сердечка) | CURRENT | вызывает `toggleAdFavourite` без `await`/обработки ошибки — общая точка входа для всех трёх экранов |
| `lib/pages/board/presentation/widgets/board_view.dart` | `BoardView.build` | CURRENT | вход №1 — общая лента (`BoardCubit()..load(page: 1)`) |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView.build` | CURRENT | вход №2 — «Мои объявления» (`isMyAds: true`) |
| `lib/pages/favourite_ads/presentation/favourite_ads_view.dart` | `FavouriteAdsView.build` | CURRENT | вход №3 — «Избранное» (`isFavouriteAds: true`) |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.toggleAdFavourite` | CURRENT | вычисляет направление, вызывает `setAdFavourite` без `try/catch`; оба `emit` (обновление иконки / удаление из списка «Избранное») в этом сценарии недостижимы |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.isOnlyFavouriteAds` | CURRENT | флаг, определяющий, какая из веток `emit` была бы выбрана при успехе — в ERROR-сценарии не имеет значения |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.setAdFavourite` | CURRENT | делегирует в `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi` по направлению; без собственного `try/catch` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.addAdToFavouritesFromApi` | CURRENT | POST `/selected-ads`; `try/catch` логирует через `Talker` (`'sendIsFavouriteToApi Error: $e'`) и `rethrow` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.removeAdFromFavouritesFromApi` | CURRENT | DELETE `/selected-ads/{id}`; `try/catch` логирует через `Talker` (`'removeAdFromFavouritesFromApi Error: $e'`) и `rethrow`; структурно идентичен `addAdToFavouritesFromApi` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | источник ветки (а) — логирует и `rethrow` любое исключение `dio.request`; источник ветки (б) — единственная узкая форма ответа, проходящая как `status: 'error'` без исключения |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio бросает исключение на любом не-2xx ответе |
| `lib/models/board/ad.dart` | `Ad.props` (Equatable) | CURRENT | не включает `isFavourite` — независимый дефект happy-path, не проявляется в этом ERROR-сценарии (см. «Связанные сущности») |
| `lib/main.dart` | `main()`, `MyApp.build` | CURRENT | `runApp(const MyApp())` без `runZonedGuarded`; ни `FlutterError.onError`, ни `PlatformDispatcher.instance.onError` нигде в `lib/` не переопределены — подтверждает отсутствие app-level перехвата необработанной асинхронной ошибки |
| `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` | `AdDetailCubit.toggleAdFavourite` | CURRENT | тот же паттерн без `try/catch`, но недостижим — кнопка закомментирована в `board_ad_detail_view.dart` (вне рамок этого use-case) |

## Критерии приёмки

- Если `AdRepository.setAdFavourite` (через `addAdToFavouritesFromApi` либо
  `removeAdFromFavouritesFromApi`, независимо от направления переключения)
  завершается исключением, оно всплывает необработанным из
  `BoardCubit.toggleAdFavourite` — ни одна из веток `emit` внутри метода не
  выполняется.
- `BoardState.ads` после отказа равен состоянию до тапа — иконка сердечка
  визуально не меняется ни на одном из трёх экранов (лента/«Мои
  объявления»/«Избранное»).
- Отказ логируется через `Talker` внутри
  `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi` до `rethrow` —
  это единственный видимый (не в UI, только в логе приложения) след отказа.
- Поскольку `InkWell.onTap` в `BoardPopulated` не `await`-ит и не
  перехватывает возвращаемый `Future`, ни `SnackBar`, ни любое другое
  пользовательское уведомление об ошибке не показывается ни на одном из трёх
  экранов.

## Связанные тесты

- `test/pages/board_cubit_test.dart`, group `'UC-142 — BoardCubit.toggleAdFavourite
  ERROR (известный дефект — без try/catch)'` — тест `'setAdFavourite бросает
  -> исключение пробрасывается, иконка не меняется, emit не достигается'`:
  мокает `adRepository.setAdFavourite(9, true)` через
  `thenThrow(Exception('network error'))`, проверяет `cubit.toggleAdFavourite(9)`
  через `expectLater(..., throwsA(isA<Exception>()))`, затем — что
  `cubit.state.ads.single.isFavourite` осталось `false`. Покрывает только
  направление «добавить» (`isFavourite: false → true`).
- `test/repositories/ad_repository_test.dart`, group `'UC-142 —
  AdRepository.addAdToFavouritesFromApi/removeAdFromFavouritesFromApi
  ERROR'` — тест `'status == "0" -> Exception, rethrow'`: мокает
  `farmRpcClient.call(any())` ответом `{'status': '0', 'message': 'err'}`,
  проверяет `repository.setAdFavourite(3, true)` через `expectLater(...,
  throwsA(isA<Exception>()))`. Несмотря на название группы, упоминающее оба
  метода, реально протестирован только `addAdToFavouritesFromApi`
  (направление `true`) — `removeAdFromFavouritesFromApi` этой группой не
  вызывается ни разу.
- **TBD — теста нет** на направление «снять с избранного»
  (`removeAdFromFavouritesFromApi` бросает исключение) ни на уровне
  `BoardCubit`, ни на уровне `AdRepository` — код структурно идентичен
  протестированному направлению (см. «Альтернативные потоки»), но отдельно
  не проверен.
- **TBD — теста нет** на реальный сетевой путь через `CustomDioClient.call`
  (ветки а/б, см. «Альтернативные потоки») — оба существующих теста мокают
  `ApiClient`/`AdRepository` напрямую, минуя `CustomDioClient` целиком.
- **TBD — теста нет** на виджет-уровне (`BoardPopulated`, тап по сердечку) —
  ни один widget-тест не воспроизводит собственно необработанную асинхронную
  ошибку, возникающую из-за отсутствия `await`/`catchError` в `onTap`; оба
  существующих теста проверяют только `Cubit`/`Repository` напрямую.

## Открытые вопросы и ограничения

- **Реальный наблюдаемый эффект необработанной асинхронной ошибки не
  верифицирован эмпирически.** Вывод о том, что ошибка не показывается
  пользователю и не прерывает работу экрана, сделан статическим чтением кода
  (`main.dart` не оборачивает `runApp` в `runZonedGuarded`; ни
  `FlutterError.onError`, ни `PlatformDispatcher.instance.onError` нигде не
  переопределены) — точное поведение на конкретной платформе/сборке (debug
  vs release, наличие внешнего crash-reporting, который в этом коде
  полностью закомментирован — `firebase_core`/`firebase_messaging`) этим
  файлом не проверялось.
- **`CustomDioClient.call` пропускает `status: 'error'` без исключения
  только в узкой форме ответа** (`Map` без ключей `data`/`animal_exits`, с
  буквальным `status == 'error'`) — любая другая форма нестатусного отказа
  (например, `{"status": "0", ...}`, как в тесте репозитория) принудительно
  получает `status: "1"` внутри `CustomDioClient.call` и не привела бы к
  `else throw Exception(...)` внутри `addAdToFavouritesFromApi`/
  `removeAdFromFavouritesFromApi` в реальном production-стеке — тест
  репозитория обходит эту узость, мокая `ApiClient` напрямую. Реальная форма
  ответа `/selected-ads`/`/selected-ads/{id}` при отказе сервера этим файлом
  не проверена против настоящего бэкенда.
- **Направление «снять с избранного» не проверено отдельно ни одним тестом**
  (см. «Связанные тесты») — структурная идентичность коду направления
  «добавить» установлена чтением, не тестом.
- **Код не проверяет авторизацию перед вызовом.** Ни `BoardCubit`, ни
  `BoardPopulated`, ни `AdRepository` не содержат проверки
  `AuthRepository.isAuthorized()` — гостевой доступ к этому же пути
  технически не исключён кодом; не разбирается глубже, поскольку актор
  зафиксирован заданием и собственным описанием
  [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md).
- **`AdDetailCubit.toggleAdFavourite` воспроизводит тот же паттерн,** но
  недостижим из живого UI (кнопка закомментирована в
  `board_ad_detail_view.dart`) — упомянут только для полноты, не входит в
  этот use-case (см. [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md)).
