# UC-139 — Автор удаляет своё объявление с экрана «Мои объявления»

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Автор объявления удаляет собственную запись с единственного экрана, где это
действие вообще доступно — «Мои объявления» (`MyAdsView`): контекстное меню
карточки → подтверждение в `_DeleteAdConfirmDialog` → `BoardCubit.deleteAd` →
`AdRepository.deleteAd` (`DELETE /ads/{id}`). Успешный путь
[EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md) (`ad.deleted`): карточка
пропадает из грид-списка сразу после ответа сервера, без локальной таблицы —
модуль `BOARD` полностью online-only ([ENT-18](../entities/ENT-18-AD-IN-BOARD.md),
«Инварианты»), поэтому «удалить» здесь означает исключительно убрать элемент
из `BoardState.ads` в памяти, ничего не остаётся ни до, ни после запроса.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Экран «Мои объявления» открывается по `Routes.myAds`, у которого (в отличие
от `Routes.boardAdCreate`) в `routes.dart` **нет** `redirect`-проверки
`AppCacheService.isAuthorized()` — маршрут технически доступен и гостю. Но
список карточек на этом экране получен через
`AdRepository.getMyAds(userId: AppCacheService.getUserId() ?? -1, ...)`
(`BoardCubit.load(isMyAds: true)`), то есть отфильтрован сервером по
`user_id` текущей сессии; создание объявления (`Routes.boardAdCreate`)
жёстко гейтится тем же `redirect` на авторизацию — гость физически не может
быть автором ни одной карточки, значит на практике экран для гостя всегда
пуст и кнопки удаления показывать нечему. Два реально существующих входа на
экран: иконка «Мои объявления» в шапке ленты
(`lib/pages/board/presentation/widgets/board_view.dart`) и пункт «Мои
объявления» в профиле
(`lib/pages/profile/presentation/widgets/profile/profile_view.dart`), оба —
`context.pushNamed2(Routes.myAds)`.

## CURRENT

### Основной поток

1. Пользователь открывает «Мои объявления» — `MyAdsPage` → `MyAdsView`,
   `BlocProvider.create: (_) => BoardCubit()..load(page: 1, isMyAds: true)`
   создаёт **отдельный экземпляр** `BoardCubit`, отдельный и от ленты, и от
   «Избранного» (у каждого экрана свой `BoardCubit`) — `BoardState.isOnlyFavouriteAds`
   в этом экземпляре всегда `false`.
2. На карточке объявления пользователь открывает контекстное меню
   (`BoardAdContextMenuButton`, передаётся в `BoardPopulated.trailingBuilder`
   — единственное реальное место в `lib/`, где этот `trailingBuilder`
   вообще задан) и выбирает пункт «Удалить» (`l10n.delete`) →
   `onDelete: () => _deleteAd(context, ad)`.
3. `MyAdsView._deleteAd` открывает `showDialog<bool>` с
   `_DeleteAdConfirmDialog` (заголовок `l10n.board_ad_delete_title`, текст
   `l10n.board_ad_delete_message`), `barrierColor:
   AppColors.black.withValues(alpha: 0.9)`. Пользователь нажимает кнопку
   «Удалить» → `onDelete: () => Navigator.of(dialogContext).pop(true)` —
   диалог закрывается немедленно, синхронно, без ожидания сетевого вызова
   (в отличие от `ConfirmSaveDisposalDialog` из `ANIMAL`, где диалог сам
   переключает внутреннее состояние на «сохранение»/«успех» — здесь диалог
   не знает о результате запроса вовсе, просто возвращает `true`).
4. `confirmed == true` и `context.mounted` — выполняется `try { await
   context.read<BoardCubit>().deleteAd(ad.id); ... }`. Это единственное
   место во всём модуле, где вызов `BoardCubit.deleteAd`/`AdRepository.deleteAd`
   обёрнут в `try/catch` (см. [EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md),
   «Исходный код»).
5. `BoardCubit.deleteAd(int id)` — **без собственного `try/catch`**: `await
   _adRepository.deleteAd(id: id);` — если это не бросает исключение,
   безусловно `emit(state.copyWith(ads: state.ads.where((ad) => ad.id !=
   id).toList()))`. Никакие другие поля состояния (`page`, `isLastPage`,
   `perPage`, `isOnlyFavouriteAds`, `errorMessage`) этим методом не
   трогаются.
6. `AdRepository.deleteAd({required int id})`: строит `ApiMessage(link:
   '${Constants.boardServiceApi}/ads/$id', method: ApiMethod.delete)`, без
   `data`; `rpcClient = getIt.get<ApiClient>(instanceName: 'farm_rpc')` —
   в production-конфигурации DI (`injection_container.dart`) это всегда
   `CustomDioClient`; `response = await rpcClient.call(message);`.
7. `CustomDioClient.call`: если `dio.request(...)` не бросает исключение
   (HTTP-ответ 2xx — `DioClient` не переопределяет `validateStatus`, любой
   не-2xx уже стал бы `DioException` до этой строки), тело нормализуется:
   если `response.data` — `Map` и содержит ключ `data` или `animal_exits` —
   `response.data['status']` принудительно выставляется в `"1"`; иначе, если
   `response.data` — `Map` с явным `response.data['status'] == 'error'` —
   ответ возвращается как есть (без принудительного статуса); во всех
   остальных случаях (включая тело, не являющееся `Map`, например пустое
   тело DELETE-ответа) — возвращается `{'data': response.data, 'status':
   '1'}`. Итог: для DELETE-эндпоинта, у которого тело ответа обычно не
   содержит `data`/`animal_exits`, любой не-`error`-ответ 2xx получает
   `status: "1"` независимо от исходного содержимого тела.
8. `AdRepository.deleteAd` проверяет **только** `if (response['status'] ==
   "0") { throw Exception(response['message']); }` — единственный
   `if`/`else`-подобный блок метода; в этом основном сценарии условие ложно
   (см. шаг 7 — `CustomDioClient` никогда не возвращает буквально `"0"`, см.
   «Открытые вопросы»), метод завершается без исключения и без
   `return`-значения (`Future<void>`).
9. Управление возвращается в `BoardCubit.deleteAd` (шаг 5) — `emit`
   выполняется, `ads` без удалённого `id`.
10. `await context.read<BoardCubit>().deleteAd(ad.id)` в `_deleteAd` (шаг 4)
    завершается без исключения → `if (context.mounted) {
    showAppSnackBarSuccess(context, l10n.deleted_successful); }` — снэкбар
    «Данные удалены успешно» (`deleted_successful` — общий ключ, не
    board-специфичный текст).
11. `BlocBuilder<BoardCubit, BoardState>` в `MyAdsView` реагирует на новое
    состояние — `GridView` в `BoardPopulated` перерисовывается без карточки
    удалённого объявления; `page`/`isLastPage` не пересчитываются и не
    рефетчатся — список просто короче на одну позицию до следующего
    `refresh()`/`loadNextPage()`.

### Альтернативные потоки

- **Отмена подтверждения.** Пользователь нажимает «Отмена» либо крестик
  (`onCancel`/`onClose`, оба — `Navigator.of(dialogContext).pop(false)`) —
  `confirmed != true`, `_deleteAd` возвращается сразу после `if (confirmed
  != true || !context.mounted) return;`: ни `BoardCubit.deleteAd`, ни
  `AdRepository.deleteAd` не вызываются, `BoardState.ads` не меняется. Тот
  же результат, если экран размонтирован к моменту закрытия диалога
  (`!context.mounted`).
- **Id, уже отсутствующий в текущем `state.ads`.** `state.ads.where((ad) =>
  ad.id != id)` не проверяет, был ли `id` вообще в списке — если между
  открытием контекстного меню и завершением сетевого вызова список уже был
  перезагружен (`refresh()`) без этого объявления, `emit` всё равно
  выполняется (сетевой DELETE-запрос уходит и обрабатывается тем же
  образом), но видимого изменения списка нет — `ads` до и после фильтрации
  совпадают по содержимому.
- **Единственный экземпляр `BoardCubit` этого экрана** — `isOnlyFavouriteAds`
  здесь всегда `false`, поэтому ветка `BoardCubit.toggleAdFavourite`
  «убрать карточку из списка целиком при `isOnlyFavouriteAds == true`» (см.
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) к сценарию удаления
  отношения не имеет — `deleteAd` не проверяет этот флаг вовсе, ветвления
  тут нет физически.

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, совершающая
  переход: конкретный элемент `BoardState.ads` (in-memory список данного
  экземпляра `BoardCubit`) исчезает из списка; на сервере запись объявления
  удаляется тем же вызовом `DELETE /ads/{id}` — ни одна другая локальная
  копия (нет ни Drift-таблицы, ни unsent-паттерна, см. «Инварианты»
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)) этим сценарием не
  затрагивается.
- `User` ([ENT-1](../entities/ENT-1-USER-IN-AUTH.md), AUTH) — только
  читается косвенно: список экрана уже отфильтрован сервером по
  `user_id == AppCacheService.getUserId()` на этапе `getMyAds`
  (`BoardCubit.load`, не в этом сценарии); сам `deleteAd` не проверяет
  авторство карточки повторно на клиенте — полагается на то, что сервер уже
  отдал только карточки текущего пользователя и что сервер сам отклонит
  DELETE чужой записи (что клиентом никак не проверяется и не отражается
  отдельной веткой — см. «Открытые вопросы»).

### Бизнес-правила

- Удаление всегда одиночное — по одному `id` за вызов; массового удаления
  нескольких объявлений разом в UI не существует.
- Подтверждение обязательно: прямого пути от контекстного меню к сетевому
  DELETE-запросу, минуя `_DeleteAdConfirmDialog`, нет.
- `BoardCubit.deleteAd` не содержит `try/catch` — единственная защита от
  необработанного исключения находится в вызывающем виджете
  (`MyAdsView._deleteAd`), не в самом cubit'е.
- Успех определяется исключительно отсутствием исключения из
  `AdRepository.deleteAd` — метод не возвращает и не публикует никакого
  дополнительного признака успеха (`Future<void>`), `BoardCubit.deleteAd`
  не читает тело ответа сервера напрямую, полностью полагаясь на то, что
  репозиторий либо вернул управление, либо бросил.
- Локальное изменение (`emit` с отфильтрованным списком) происходит
  **после** подтверждённого сетевого ответа, не оптимистично до него — в
  отличие, например, от `Movement`, где `Animal.placeId` меняется локально
  ещё до подтверждения сервера (см. `.claude/rules/domain-model.md`,
  инвариант 5); здесь никакого локального шага «до» сети не существует
  вовсе, потому что нет локальной копии, которую можно было бы менять
  заранее.
- Снэкбар успеха/ошибки — общие ключи `deleted_successful`/
  `deleted_with_errors`, не специфичные для объявлений доски (тот же
  паттерн, что и в других местах приложения, использующих эти ключи).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и покрыт тестом на обоих
уровнях (cubit и repository, см. «Связанные тесты»); находки, перечисленные
в «Открытые вопросы и ограничения», не блокируют его выполнение.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView._deleteAd` | CURRENT | единственное место, оборачивающее вызов в `try/catch`; показывает confirm-диалог, затем снэкбар успеха/ошибки |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `_DeleteAdConfirmDialog` | CURRENT | модальное подтверждение; `onDelete`/`onCancel`/`onClose` — синхронный `Navigator.pop`, без ожидания сети |
| `lib/pages/my_ads/presentation/my_ads_page.dart` | `MyAdsPage` | CURRENT | обёртка страницы (реагирует на смену языка), рендерит `MyAdsView` |
| `lib/pages/board/presentation/widgets/board_ad_context_menu.dart` | `BoardAdContextMenuButton` | CURRENT | пункт меню «Удалить», вызывает переданный `onDelete` |
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated.trailingBuilder` | CURRENT | слот грид-карточки; заполняется контекстным меню только вызывающей стороной `MyAdsView` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.deleteAd` | CURRENT | вызывает `AdRepository.deleteAd`, без `try/catch`; при успехе `emit` с отфильтрованным `ads` |
| `lib/pages/board/cubit/board_state.dart` | `BoardState.ads` | CURRENT | in-memory список, единственное поле, меняемое этим сценарием |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.deleteAd` | CURRENT | `DELETE /ads/{id}`; собственный `try/catch` с `Talker`-логом и `rethrow`; успех определяется как `response['status'] != "0"` |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | нормализует любой не-error 2xx ответ к `status: "1"`; никогда не возвращает буквально `"0"` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — любой не-2xx ответ становится исключением ещё до нормализации в `CustomDioClient` |
| `lib/injection_container.dart` | регистрация `ApiClient` с `instanceName: 'farm_rpc'` | CURRENT | в production связывает `farm_rpc` именно с `CustomDioClient` |
| `lib/pages/routes.dart` | маршрут `Routes.myAds` | CURRENT | вход на экран; без `redirect`-проверки авторизации (в отличие от `Routes.boardAdCreate`) |
| `lib/pages/board/presentation/widgets/board_view.dart` | иконка «Мои объявления» (`onTap` → `Routes.myAds`) | CURRENT | вход №1 в экран |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` «Мои объявления» (`onTap` → `Routes.myAds`) | CURRENT | вход №2 в экран |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarSuccess`, `showAppSnackBarError` | CURRENT | снэкбары успеха/ошибки, вызываемые из `_deleteAd` |
| `lib/l10n/app_ru.arb`, `lib/l10n/app_en.arb` | `board_ad_delete_title`, `board_ad_delete_message`, `deleted_successful`, `deleted_with_errors`, `cancel`, `delete` | CURRENT | тексты диалога подтверждения и снэкбара |

## Критерии приёмки

- По нажатию «Удалить» в контекстном меню карточки на экране «Мои
  объявления», затем «Удалить» в `_DeleteAdConfirmDialog`, выполняется ровно
  один вызов `AdRepository.deleteAd(id: ad.id)` — `DELETE
  ${Constants.boardServiceApi}/ads/{id}`.
- Если этот вызов завершается без исключения (нормальный 2xx-ответ,
  `response['status'] != "0"`), `BoardCubit.deleteAd` выполняет ровно один
  `emit` с `ads`, из которого удалённый `id` отсутствует; все остальные поля
  `BoardState` не меняются этим вызовом.
- После этого `_deleteAd` показывает `showAppSnackBarSuccess(context,
  l10n.deleted_successful)`; UI-грид `MyAdsView` не отображает больше
  карточку удалённого объявления.
- Отмена или закрытие `_DeleteAdConfirmDialog` (кнопка «Отмена» либо
  крестик) не приводит ни к одному вызову `AdRepository.deleteAd`, ни к
  изменению `BoardState.ads`.
- Сценарий не делает и не требует ни одной операции с локальной БД — ни
  Drift-таблицы для `Ad`, ни какого-либо «неотправленного» состояния не
  существует ни до, ни после вызова.

## Связанные тесты

- `test/pages/board_cubit_test.dart`, group `'UC-139 — BoardCubit.deleteAd'`
  — тест `'успех -> deleteAd вызван, объявление пропадает из списка'`:
  мокает `adRepository.deleteAd(id: 9)` успехом, строит `BoardCubit` с двумя
  объявлениями (`_ad(id: 9)`, `_ad(id: 10)`), вызывает `cubit.deleteAd(9)`,
  проверяет `verify(() => adRepository.deleteAd(id: 9)).called(1)` и
  `cubit.state.ads.map((a) => a.id) == [10]`.
- `test/repositories/ad_repository_test.dart`, group `'UC-139 —
  AdRepository.deleteAd'` — тест `'успех -> DELETE /ads/{id}'`: мокает
  `farmRpcClient.call(any())` ответом `{'status': '1'}`, вызывает
  `repository.deleteAd(id: 9)`, проверяет `method == ApiMethod.delete` и
  `link` содержит `/ads/9`.
- Старая нумерация групп (`UC-139` в обоих файлах) относится к прежней схеме
  id и не переименована на момент написания этой спеки — переименование под
  `UC-139` выполняется отдельным контролируемым проходом, не этой задачей;
  якорь `grep -r "UC-139" test/` заработает только после него.
- `test/repositories/ad_repository_test.dart`, group `'UC-140 —
  AdRepository.deleteAd ERROR'`, и `test/pages/board_cubit_test.dart`, group
  `'UC-140 — BoardCubit.deleteAd ERROR (эталон — обработка на уровне
  вызывающего виджета)'` в этот use-case **не входят** — это ветка `ERROR`
  того же события (сетевое исключение/`response['status'] == "0"`),
  специфицируемая отдельным use-case, не этим файлом.
- **TBD — теста нет** на сам `MyAdsView._deleteAd`/`_DeleteAdConfirmDialog`
  на уровне виджета — ни на подтверждение/отмену диалога, ни на то, что
  `showAppSnackBarSuccess` реально показывается после успеха; существующие
  тесты покрывают только уровни `BoardCubit` и `AdRepository` по отдельности.

## Открытые вопросы и ограничения

- **`AdRepository.deleteAd` проверяет ответ иначе, чем все остальные методы
  того же класса, и эта проверка похожа на недостижимую в production.**
  `createAd`/`updateAd`/`viewAd`/`addAdToFavouritesFromApi`/
  `removeAdFromFavouritesFromApi` считают успехом строго `response['status']
  == "1"` (иначе бросают исключение); `deleteAd` — единственный метод,
  инвертирующий условие: успех — это «не `"0"`». По коду
  `CustomDioClient.call` (в production `ApiClient` с `instanceName:
  'farm_rpc'` всегда `CustomDioClient` — см. `injection_container.dart`)
  любой ответ без исключения либо принудительно получает `status: "1"`,
  либо (единственное исключение — `Map`-тело с явным `status == 'error'` и
  без ключей `data`/`animal_exits`) передаётся как есть **с тем значением,
  которое буквально прислал сервер** — то есть, по всей видимости,
  `'error'`, а не `"0"`. Найденного во всём просмотренном коде пути, при
  котором `response['status']` стало бы буквально строкой `"0"`, нет — тест
  `'status == "0" -> Exception, rethrow'` (`UC-140`) проверяет это условие
  через мок `ApiClient`, подставляющий `"0"` напрямую, минуя нормализацию
  `CustomDioClient`, то есть подтверждает только код самого `deleteAd`, не
  то, что этот код когда-либо реально достижим через боевой `farm_rpc`.
  Практическое следствие: если сервер логически отклонит удаление (вернёт,
  например, `{'status': 'error', 'message': '...'}` без `data`), `deleteAd`
  **не бросит исключение** — `'error' != "0"` — и `BoardCubit.deleteAd`
  уберёт карточку из списка так, как будто удаление прошло успешно, хотя
  сервер его не подтвердил. Не воспроизведено интеграционно (нет реального
  ответа сервера), сформулировано статическим чтением `AdRepository.deleteAd`
  → `CustomDioClient.call` → `injection_container.dart`; не разбирается
  глубже в рамках этого документирующего прохода (фиксация CURRENT, не
  исправление).
- **Авторство карточки не проверяется клиентом при удалении.** `deleteAd`
  отправляет только `id`, не `userId` и не сверяет `ad.userId` с текущим
  пользователем — единственная защита от удаления чужого объявления это то,
  что список «Мои объявления» уже отфильтрован сервером по `user_id`
  (`getMyAds`) и, предположительно, сервер сам отклонит DELETE чужой записи.
  Это предположение о серверном поведении не верифицировано в этом
  документирующем проходе (модуль полностью online-only, серверный код вне
  границ репозитория).
- **`page`/`isLastPage` не пересчитываются после локального удаления.**
  Успешное удаление уменьшает `ads` на один элемент, но не запрашивает
  повторно текущую страницу и не корректирует `isLastPage` — если это было
  последнее объявление последней подгруженной страницы, счётчики пагинации
  временно перестают точно отражать содержимое списка до следующего
  `refresh()`/`loadNextPage()`. Не воспроизведено тестом, не разбирается
  глубже.
- **Гонка «cubit закрыт до завершения запроса» не проверена.** `await
  context.read<BoardCubit>().deleteAd(ad.id)` держит ссылку на `BoardCubit`,
  захваченную до `await`; если экран будет закрыт (и `BlocProvider` вызовет
  `cubit.close()`) в промежутке между уходом сетевого запроса и `emit`
  внутри `deleteAd`, это тот же класс гонки, что уже отмечен для
  `ConfirmSaveDisposalDialog` в `ANIMAL`
  ([UC-99](UC-99-ACTOR-5-EVT-50-ENT-16-CREATE_OK-IN-ANIMAL.md), «Открытые
  вопросы»), только без диалога, синхронно переключающегося на «успех» до
  завершения запроса — здесь `_DeleteAdConfirmDialog` закрывается ещё раньше
  сетевого вызова. Не воспроизведено, не разбирается глубже.
