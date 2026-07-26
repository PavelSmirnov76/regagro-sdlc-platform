# UC-140 — Удаление собственного объявления отказывает — исключение перехватывается только на уровне вызывающего виджета

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же экран и тот же вызов, что и в happy-path
[EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md) («Мои объявления» →
контекстное меню карточки → подтверждение в `_DeleteAdConfirmDialog` →
`BoardCubit.deleteAd`), но здесь `AdRepository.deleteAd` завершается
исключением. `BoardCubit.deleteAd` не имеет собственного `try/catch` —
исключение пробрасывается через него необработанным. В отличие от
большинства `ERROR`-сценариев `BOARD`, здесь это не приводит к сбою,
видимому пользователем как краш или необработанное исключение: единственный
реальный вызывающий код, `MyAdsView._deleteAd`
(`lib/pages/my_ads/presentation/my_ads_view.dart`), сам оборачивает вызов
`context.read<BoardCubit>().deleteAd(ad.id)` в `try/catch` и показывает
снэкбар об ошибке. Корректность этого сценария целиком держится на том, что
у `BoardCubit.deleteAd` сегодня ровно один вызывающий код во всём `lib/` (см.
«Технические зависимости») — если метод когда-либо будет вызван из другого
места без такой же обёртки, это станет необработанным исключением на
уровне этого нового вызывающего кода, а не сегодняшним корректным поведением.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
автор объявления, на экране «Мои объявления» (`Routes.myAds`,
`lib/pages/my_ads/presentation/my_ads_page.dart` → `MyAdsView`). На этот
экран ведут два реально существующих в навигации входа: плитка «Мои
объявления» в ленте (`lib/pages/board/presentation/widgets/board_view.dart`,
`onTap: () => context.pushNamed2(Routes.myAds)`) и пункт меню в профиле
(`lib/pages/profile/presentation/widgets/profile/profile_view.dart`).
`BoardCubit` этого экрана создаётся собственным `BlocProvider` внутри
`MyAdsView` (`BoardCubit()..load(page: 1, isMyAds: true)`), не тем же
инстансом, что у ленты «Объявления».

## CURRENT

### Основной поток

1. Пользователь на «Мои объявления» видит карточку своего объявления. Тело
   каждой карточки строит `BoardPopulated`
   (`lib/pages/board/presentation/widgets/board_populated.dart`) с
   `trailingBuilder: (context, ad) => BoardAdContextMenuButton(onEdit: ...,
   onDelete: ...)` — это единственное место во всём `lib/`, где параметр
   `trailingBuilder` реально передан (проверено `grep` по
   `trailingBuilder`/`BoardAdContextMenuButton` за пределами
   `my_ads_view.dart`); лента объявлений (`BoardPage`) и «Избранное»
   (`FavouriteAdsPage`) вызывают `BoardPopulated` без этого параметра —
   удаление недоступно ни на одном другом экране.
2. Пользователь открывает меню ⋮ (`BoardAdContextMenuButton`,
   `lib/pages/board/presentation/widgets/board_ad_context_menu.dart`) и
   выбирает пункт «Удалить» (`l10n.delete`) — `onSelected` вызывает
   `onDelete?.call()`, что в `MyAdsView` смонтировано на
   `_deleteAd(context, ad)`.
3. `_deleteAd` показывает `showDialog<bool>` с `_DeleteAdConfirmDialog`
   (заголовок `l10n.board_ad_delete_title`, текст
   `l10n.board_ad_delete_message`); кнопка «Удалить» вызывает
   `Navigator.of(dialogContext).pop(true)`.
4. Пользователь подтверждает удаление — диалог закрывается с `confirmed ==
   true`; `_deleteAd` продолжает (проверка `!context.mounted` не срабатывает
   — экран остаётся смонтирован).
5. `_deleteAd` входит в `try`: `await
   context.read<BoardCubit>().deleteAd(ad.id);`.
6. `BoardCubit.deleteAd(id)` — весь метод состоит из двух строк, без
   собственного `try/catch`: `await _adRepository.deleteAd(id: id);` затем
   `emit(state.copyWith(ads: state.ads.where((ad) => ad.id != id).toList()))`
   — `state.ads` **не изменяется оптимистично до ответа сервера**, изменение
   стоит строго после `await`, так что откатывать в случае ошибки нечего.
7. `AdRepository.deleteAd({required int id})`
   (`lib/repositories/board/ad_repository.dart`) строит `ApiMessage(link:
   '${Constants.boardServiceApi}/ads/$id', method: ApiMethod.delete)` и
   вызывает `rpcClient.call(message)` (`getIt.get<ApiClient>(instanceName:
   'farm_rpc')`) внутри собственного `try/catch` метода. Здесь сценарий
   расходится на два независимо проверенных источника исключения,
   **сходящихся к одному и тому же `catch`**:
   - **сетевой/HTTP-сбой** — `CustomDioClient.call`
     (`lib/network/api_client/custom_dio_client.dart`) оборачивает
     `dio.request(...)` собственным `try/catch`: `DioClient`
     (`lib/network/dio_client.dart`) не переопределяет `validateStatus`,
     поэтому Dio по умолчанию бросает `DioException` на любом не-2xx
     ответе, как и на обрыве соединения/таймауте; `CustomDioClient.call`
     логирует (`getIt.get<Talker>().error('CustomDioClient: call: $e')`) и
     безусловно перебрасывает (`rethrow`) — исключение всплывает прямо из
     `await rpcClient.call(message)` внутри `AdRepository.deleteAd`;
   - **логический отказ, воспроизводимый в тестах прямым моком
     `ApiClient`** — `rpcClient.call` возвращает `Map` без исключения, и
     `if (response['status'] == "0") { throw Exception(response['message']);
     }` бросает исключение внутри того же `try`-блока `deleteAd`.

   Обе ветки перехватываются одним и тем же `catch (e) {
   getIt<Talker>().error('deleteAd Error: $e'); rethrow; }` — в отличие от
   `UnsentReportAnimalsRepository.sync`
   ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md)), где
   похожие два источника расходились к принципиально разным исходам, здесь
   они с самого начала унифицированы одним и тем же перехватом внутри
   `AdRepository`, и наружу выходит один и тот же вид исключения независимо
   от источника.
8. Исключение покидает `AdRepository.deleteAd`, затем
   `await _adRepository.deleteAd(id: id)` внутри `BoardCubit.deleteAd` —
   поскольку у `BoardCubit.deleteAd` нет собственного `try/catch`, строка
   `emit(state.copyWith(ads: ...))` **не достигается**: `state.ads` остаётся
   прежним, удалённая карточка не пропадает из локального состояния.
9. Исключение продолжает всплывать из `context.read<BoardCubit>().deleteAd(ad.id)`
   внутри `_deleteAd` — здесь оно наконец перехватывается: `catch (_) { if
   (context.mounted) { showAppSnackBarError(context, l10n.deleted_with_errors);
   } }` (`lib/widgets/app_snackbar.dart` → `showAppSnackBarError`, фон
   `AppColors.snackbarErrorBackground`).
10. Пользователь видит снэкбар с текстом `l10n.deleted_with_errors` («Error
    deleting data» в `app_en.arb`). Диалог подтверждения уже закрыт (шаг 4);
    повторного открытия не происходит. Карточка объявления остаётся видимой
    в списке «Мои объявления» — ни локально, ни на сервере ничего не
    удалено.

### Альтернативные потоки

- **Отмена в диалоге подтверждения — не этот сценарий.** Если пользователь
  нажимает «Отмена» или крестик (`onCancel`/`onClose`, оба вызывают
  `Navigator.of(dialogContext).pop(false)`), либо закрывает диалог иначе,
  `confirmed != true`, и `_deleteAd` возвращается до вызова
  `context.read<BoardCubit>().deleteAd(...)` — `AdRepository.deleteAd`
  вообще не вызывается, никакого исключения не возникает.
- **`!context.mounted` после диалога** — тот же ранний `return`, что и выше;
  на практике почти недостижим в рамках одного синхронного `showDialog`, но
  формально предусмотрен кодом.
- **Единственный вызывающий код сегодня.** `grep -rn "\.deleteAd("` по
  `lib/` находит ровно два места: `BoardCubit.deleteAd` (сама реализация) и
  `MyAdsView._deleteAd` (единственный вызов извне). Если в будущем
  `BoardCubit.deleteAd` будет вызван из другого экрана/виджета без
  собственного `try/catch` вокруг вызова, исключение станет необработанным
  на уровне того нового вызывающего кода — сегодняшняя корректность этого
  `ERROR`-сценария не встроена в сам `BoardCubit`, а является свойством
  единственного существующего вызывающего кода.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё удаление
  не происходит: ни в памяти (`BoardState.ads` не изменяется, поскольку
  `emit` в `BoardCubit.deleteAd` не достигается), ни на сервере. Модуль
  полностью online-only ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md),
  «Описание») — локальной таблицы/черновика удаления не существует, поэтому
  «откатывать» после ошибки нечего: до успешного ответа сервера ничего не
  менялось.
- `BoardState` (`lib/pages/board/cubit/board_state.dart`) — `@freezed`,
  поле `ads` читается и (в успешном случае) переписывается
  `BoardCubit.deleteAd`; в этом сценарии остаётся равным предыдущему
  значению, так как строка `emit` не достигается.

### Бизнес-правила

- `BoardCubit.deleteAd` — единственный метод `BoardCubit` без собственного
  `try/catch`: `load`, `applySearchText`, `applyBoardFilters` перехватывают
  ошибки сами (`catch (e) { emit(state.copyWith(isError: true, ...)); }`);
  `deleteAd`, `toggleAdFavourite`, `viewAd` — нет, но только у `deleteAd`
  единственный вызывающий код сам оборачивает вызов в `try/catch` —
  `toggleAdFavourite`/`viewAd` вызываются из мест, не проверенных в рамках
  этого файла.
- `AdRepository.deleteAd` — единственный метод `AdRepository`, чья проверка
  неуспеха написана как `if (response['status'] == "0") throw ...`
  (позитивная проверка кода отказа). Все остальные методы того же файла
  (`createAd`, `updateAd`, `viewAd`, `addAdToFavouritesFromApi`,
  `removeAdFromFavouritesFromApi`) написаны в обратную сторону — `if
  (response['status'] == "1") return; else throw ...` (позитивная проверка
  кода успеха, отказ — любое другое значение). См. «Открытые вопросы» —
  эта асимметрия существенна с учётом того, как `CustomDioClient.call`
  нормализует ответ.
- Оптимистичного удаления карточки из UI до подтверждения сервера не
  существует — `state.ads` меняется только строкой, следующей за `await
  _adRepository.deleteAd(...)`, и не достигается при исключении.
- Удаление — одна DELETE-операция на одно объявление; группового/batch-
  удаления в этом сценарии нет.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий воспроизводится статическим
чтением кода и подтверждён запущенными тестами на двух уровнях
(`AdRepository.deleteAd`, `BoardCubit.deleteAd`), оба зелёные на момент
написания. Прямого теста на реальный сетевой/HTTP-сбой именно для
`deleteAd` (в отличие от `updateAd`, см. «Открытые вопросы») и
widget-теста на `MyAdsView._deleteAd`/`_DeleteAdConfirmDialog` нет — это
пробел покрытия, а не блокер документирования: поведение уже наблюдаемо
статическим чтением кода `AdRepository.deleteAd` → `CustomDioClient.call` →
`DioClient`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_ad_context_menu.dart` | `BoardAdContextMenuButton` | CURRENT | пункт меню «Удалить» → `onDelete` |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated.trailingBuilder` | CURRENT | параметр, реально переданный только из `MyAdsView` — удаление недоступно ни на ленте, ни в «Избранном» |
| `lib/pages/my_ads/presentation/my_ads_page.dart` | `MyAdsPage` | CURRENT | точка маршрута `Routes.myAds`, оборачивает `MyAdsView` |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView._deleteAd`, `_DeleteAdConfirmDialog` | CURRENT | единственный вызывающий код `BoardCubit.deleteAd` во всём `lib/`; единственное место с `try/catch` вокруг этого вызова |
| `lib/pages/board/presentation/widgets/board_view.dart` | плитка «Мои объявления» (`onTap` → `Routes.myAds`) | CURRENT | вход №1 в навигации на этот экран |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | пункт «Мои объявления» | CURRENT | вход №2 в навигации на этот экран |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.deleteAd` | CURRENT | без `try/catch`; `emit` после `await` не достигается при исключении |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.ads` | CURRENT | поле, не изменяемое в этом сценарии |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.deleteAd` | CURRENT | `try/catch` метода, `Talker.error` + `rethrow`; проверка `response['status'] == "0"` (в отличие от остальных методов файла) |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | реальный источник сетевого/HTTP-исключения; нормализует успешный ответ к `status: "1"`, кроме случая, когда исходное тело уже содержит `status: 'error'` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio бросает на любом не-2xx ответе |
| `lib/network/api_client/api_client.dart` | `ApiClient` | CURRENT | интерфейс, мокается тестами напрямую (в обход `CustomDioClient`) |
| `lib/network/api_client/api_message.dart` | `ApiMessage`, `ApiMethod.delete` | CURRENT | тело запроса `DELETE /ads/{id}` |
| `lib/constants.dart` | `Constants.boardServiceApi` | CURRENT | базовый путь эндпоинта объявлений |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT | снэкбар, показываемый по `catch` в `MyAdsView._deleteAd` |

## Критерии приёмки

- Если `AdRepository.deleteAd` бросает исключение по любой из двух причин
  (сетевой/HTTP-сбой внутри `CustomDioClient.call`, либо ответ с
  `response['status'] == "0"`), `BoardCubit.deleteAd` пробрасывает это же
  исключение необработанным — `state.ads` не меняется (сравнить с
  состоянием до вызова).
- Единственный существующий вызывающий код, `MyAdsView._deleteAd`,
  перехватывает это исключение собственным `try/catch` и вызывает
  `showAppSnackBarError(context, l10n.deleted_with_errors)`; исключение
  дальше не пробрасывается, приложение не падает.
- После отказа карточка удаляемого объявления остаётся в списке «Мои
  объявления» (ни локальное состояние, ни сервер не изменились).
- Ни один другой экран `BOARD` (лента, «Избранное») не предоставляет
  пользователю действие удаления — `trailingBuilder` передан только в
  `MyAdsView`.

## Связанные тесты

- `test/pages/board_cubit_test.dart`, group `'UC-140 — BoardCubit.deleteAd
  ERROR (эталон — обработка на уровне вызывающего виджета)'`, test
  `'deleteAd бросает -> исключение пробрасывается через cubit
  необработанным, список не меняется'` — мокает
  `adRepository.deleteAd(id: 9)` через `.thenThrow(Exception('network
  error'))`, подтверждает `expectLater(cubit.deleteAd(9),
  throwsA(isA<Exception>()))` и что `cubit.state.ads` после этого всё ещё
  содержит id `9` (список не изменился).
- `test/repositories/ad_repository_test.dart`, group `'UC-140 —
  AdRepository.deleteAd ERROR'`, test `'status == "0" -> Exception,
  rethrow'` — мокает `farmRpcClient.call(any())` ответом `{'status': '0',
  'message': 'err'}` напрямую через `MockApiClient` (в обход
  `CustomDioClient`), подтверждает `expectLater(repository.deleteAd(id: 9),
  throwsA(isA<Exception>()))`.
- Старая нумерация (`UC-140`) в обоих файлах относится к прежней схеме id и
  не переименована на момент написания этой спеки — переименование под
  `UC-140` выполняется отдельным контролируемым проходом; якорь `grep -r
  "UC-140" test/` заработает только после него.
- **TBD — теста нет** на реальный сетевой/HTTP-сбой именно для
  `AdRepository.deleteAd` (в отличие от `updateAd`, где такой тест есть —
  `test/repositories/ad_repository_test.dart`, group `'UC-138 —
  AdRepository.updateAd ERROR'`, `farmRpcClient.call(any()).thenThrow(...)`)
  — сегодняшний `'UC-140 — AdRepository.deleteAd ERROR'` покрывает только
  ветку `response['status'] == "0"`, смоделированную прямым возвратом из
  мока, а не исключением из `rpcClient.call`.
- **TBD — теста нет** на `MyAdsView._deleteAd`/`_DeleteAdConfirmDialog` на
  уровне виджета — весь путь «диалог подтверждён → catch → снэкбар»
  подтверждён здесь только чтением кода, не тестом.

## Открытые вопросы и ограничения

- **Проверка `response['status'] == "0"` в `AdRepository.deleteAd`, скорее
  всего, недостижима через реальный `CustomDioClient` в проде.**
  `CustomDioClient.call` (`lib/network/api_client/custom_dio_client.dart`)
  нормализует любой успешный HTTP-ответ одним из трёх путей: (1) тело —
  `Map`, содержащий ключ `data` или `animal_exits` → `status` принудительно
  переписывается на `"1"`; (2) тело — `Map`, и `response.data['status'] ==
  'error'` (буквально строка `'error'`, не `"0"`) → возвращается как есть;
  (3) любой другой случай → `{"data": response.data, "status": "1"}` —
  исходное поле `status`, каким бы оно ни было (включая `"0"`), **теряется
  и принудительно заменяется на `"1"`**. Из этого следует, что буквальное
  значение `status: "0"`, которое проверяет `deleteAd`, не может пережить
  прохождение через `CustomDioClient` ни при каком реальном ответе сервера —
  единственный способ его получить, показанный в этом файле, — прямой мок
  `ApiClient` в тесте, в обход `CustomDioClient` целиком. Если реальный
  бэкенд действительно сигнализирует логический отказ строкой `status:
  'error'` (та же форма, что уже задокументирована для другого эндпоинта в
  [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  б), то `deleteAd`, проверяющий именно `== "0"`, а не `!= "1"` (как это
  сделано во всех остальных методах того же файла — см. «Бизнес-правила»),
  **не заметит такой отказ вовсе** — `if` не сработает, метод завершится
  без исключения, `BoardCubit.deleteAd` дойдёт до `emit` и уберёт карточку
  из UI, как будто удаление прошло успешно, хотя сервер его отклонил. Не
  проверено эмпирически против реального бэкенда — вывод сделан статическим
  чтением `CustomDioClient.call` и `AdRepository.deleteAd`; точная форма
  логического отказа, которую в реальности отдаёт эндпоинт `DELETE
  /ads/{id}`, этой спекой не верифицирована.
- **Корректность этого сценария — свойство единственного вызывающего кода,
  не самого `BoardCubit`.** `BoardCubit.deleteAd` не имеет собственной
  защиты; если появится второй вызывающий код без своего `try/catch`,
  исключение станет необработанным именно там. Не разбирается глубже в
  рамках этого файла — только зафиксировано как ограничение архитектуры.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`MyAdsView._deleteAd` → `BoardCubit.deleteAd` → `AdRepository.deleteAd` →
  `CustomDioClient.call`/`DioClient`) и подтверждён модульными тестами с
  замоканными `AdRepository`/`ApiClient` (см. «Связанные тесты»).
