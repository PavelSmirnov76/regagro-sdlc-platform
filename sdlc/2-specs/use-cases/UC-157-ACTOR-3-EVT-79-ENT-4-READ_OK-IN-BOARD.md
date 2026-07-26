# UC-157 — Реактивный пересчёт доступности раздела BOARD по стране (гость/авторизованный, три независимых триггера)

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md) |
| Сущность | [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

`BoardChatAvailabilityCubit` — единственный экземпляр на всё приложение,
предоставленный `MultiProvider` в корне виджетного дерева
(`MyApp.build`, `lib/main.dart`, выше `go_router`, выше любой авторизационной
развилки), пересчитывает `bool` — «доступен ли раздел BOARD (доска
объявлений + чат) текущему пользователю по стране» — автоматически, без
единого действия пользователя в момент самого пересчёта, по трём независимым
триггерам:

1. смена пользователя в Hive auth-боксе (ключ `USER`) — login/logout;
2. смена сохранённого гостевого кода страны;
3. завершение синхронизации справочника стран (`CountriesRepository.syncCountries`).

Результат — чистый UI-гейт: количество вкладок нижней навигации (5 против 2)
и видимость трёх независимых блоков на экране профиля. Он **не** route-guard:
`lib/pages/routes.dart` не содержит ни одной проверки этого флага ни для
одного маршрута BOARD (подтверждено чтением файла — единственные проверки
там — `AppCacheService.isAuthorized()` для `/board/create` и `/chats`, к
доступности по стране отношения не имеющие) — см. «Открытые вопросы».

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение, действующее
автоматически. Сам пересчёт не инициируется явным жестом пользователя ни в
одном из трёх триггеров: даже когда первопричина — человеческое действие
(вход/выход из аккаунта, выбор гостевой страны), эти действия принадлежат
другим, уже специфицированным событиям других акторов (AUTH); ACTOR-3 здесь
отвечает только за факт «кубит отреагировал и пересчитал», не за исходный
человеческий жест. Пересчёт по завершении `syncCountries()` (триггер 3) и
подавно не связан ни с каким пользовательским действием напрямую — это
побочный эффект синхронизации справочников (HANDBOOKS).

## CURRENT

### Основной поток

1. При старте приложения `MyApp.build` (`lib/main.dart`) оборачивает всё
   дерево в `MultiProvider`, один из провайдеров — `BlocProvider<BoardChatAvailabilityCubit>(
   create: (context) => BoardChatAvailabilityCubit())`. Кубит создаётся один
   раз и живёт всё время жизни приложения, выше `go_router` и выше любой
   развилки авторизации.
2. Конструктор `BoardChatAvailabilityCubit()` (`super(false)` — начальное
   состояние всегда `false`, до первого завершения `load()`) подписывается на
   три независимых источника:
   - `_authBoxListenable = _authRepository.getAuthBoxListenable(keys:
     [AuthRepository.userKey])` → `AuthRepository._getAuthBox().listenable(
     keys: [...])` (`hive_ce_flutter`, `BoxX.listenable`) — `ValueListenable`,
     уведомляющий слушателей только когда меняется запись именно с ключом
     `USER` в auth-боксе;
   - `AppCacheService.guestCountryCodeNotifier` (`ValueNotifier<String?>`,
     обновляется `AppCacheService.saveGuestCountryCode`);
   - `AppCacheService.boardEnabledSyncNotifier` (`ValueNotifier<DateTime?>`,
     выставляется в `DateTime.now()` последней строкой
     `CountriesRepository.syncCountries()`).
   Затем конструктор безусловно вызывает `load()` один раз — этот самый
   первый пересчёт происходит не по одному из трёх триггеров, а сразу при
   создании кубита (холодный старт приложения).
3. `load()`: `final country = await _getCurrentCountry(); if (!isClosed)
   emit(country?.boardEnabled == true)`.
4. `_getCurrentCountry()` ветвится по `_authRepository.isAuthorized()`
   (`getMainTokenData() != null`):
   - **авторизован** — `user = _authRepository.getUser()`; если `user ==
     null` (защитный случай — теоретически не должен наступать, поскольку
     `AuthRepository._saveMainAuthData` при входе сохраняет `tokenMainDataKey`
     и `userKey` из одного и того же вызова, но структурно ничем не
     гарантировано) — `return null` немедленно, без единого обращения к
     `CountriesRepository`. Иначе: `countries = await
     _countriesRepository.getAll()` — **весь** локальный справочник стран
     разом, без фильтра (`BaseRepository.getAll` → `dao.getAll()`);
     `countryId = int.tryParse(user.countryId ?? '')` — если не `null`,
     линейный перебор `countries` в поисках `c.id == countryId`, возврат
     первого совпадения; если совпадения нет **или** `countryId` не
     распарсился — fallback: `isoCode = user.phoneCountryIsoCode`, если не
     `null`/не пусто, линейный перебор в поисках `c.code.toUpperCase() ==
     isoCode.toUpperCase()` (регистронезависимое сравнение с обеих сторон),
     возврат первого совпадения; если и это не найдено — `return null`.
   - **гость** — `guestCode = AppCacheService.getGuestCountryCode()`
     (синхронное чтение `SharedPreferences`, ключ `guest_country_code`,
     тот же факт, что задокументирован полем `guestCountryCode` на
     [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)); если не `null`/не пусто —
     `return await _countriesRepository.getByCountryCode(
     guestCode.toUpperCase())` — точечный DAO-запрос по коду
     (`CountriesDao.getByCountryCode`), без перебора справочника целиком;
     если гостевой код не сохранён — `return null` немедленно, ни одного
     обращения к `CountriesRepository`.
5. Итоговый `bool` — `country?.boardEnabled == true`: `country == null`,
   `country.boardEnabled == null` и `country.boardEnabled == false`
   неразличимы в состоянии кубита — все три схлопываются в один и тот же
   `false`, без какого-либо различающего признака где-либо в состоянии или UI.
6. `lib/pages/main/main_page.dart`'s `_MainContent.build`:
   `boardChatAvailable = context.watch<BoardChatAvailabilityCubit>().state`
   передаётся в `NavBar(..., boardChatAvailable: boardChatAvailable)`.
   `NavBar.build` (`lib/widgets/bottom_app_bar/nav_bar.dart`) строит **5**
   кнопок при `true` (индексы 0 «Доска», 1 «Поиск», 2 «Ферма»/скрыт под FAB,
   3 «Сообщения», 4 «Профиль») либо **2** кнопки при `false` (только индекс
   2 «Ферма» и индекс 4 «Профиль» — индексы 0/1/3 физически отсутствуют в
   ряду кнопок, не просто задизейблены).
7. Тот же `_MainContent.build` также содержит
   `BlocListener<BoardChatAvailabilityCubit, bool>`: `if (!boardChatAvailable
   && (_currentIndex == 0 || _currentIndex == 1 || _currentIndex == 3))
   _onItemTapped(_safeFallbackIndex)` (`_safeFallbackIndex = 2`, «Ферма») —
   срабатывает только на переход в `false`, только если пользователь в этот
   момент находится на одной из трёх «бордовых» вкладок; переход в `true`
   ничего не переключает автоматически.
8. `lib/pages/profile/presentation/widgets/profile/profile_view.dart`
   содержит три независимых `BlocBuilder<BoardChatAvailabilityCubit, bool>`
   (каждый подписывается на кубит отдельно, не через один общий `watch`):
   один рендерит блок кнопок «Избранное»/т.п. только при `true`
   (`SizedBox.shrink()` иначе); второй — рендерит альтернативный
   информационный блок (высота `204`, окаймлённый `Container`) только при
   `false`; третий — рендерит нижний позиционированный информационный блок
   (высота `100`) только при `true`.

### Три независимых триггера (после первичной загрузки на шаге 2)

- **Триггер 1 — смена пользователя.** `_onAuthChanged` вызывает `load()`
  при любом изменении записи с ключом `USER` в auth-боксе — сохранение при
  логине (`_saveMainAuthData`, `if (user != null) await box.put(userKey,
  ...)`) и полная очистка бокса при логауте (`AuthRepository.logout()` →
  `box.clear()`) оба видимы этому листенеру: `hive_ce`'s
  `Keystore.clear()` эмитит `_notifier.notify(Frame.deleted(frame.key))`
  для **каждого** ключа, существовавшего в боксе на момент очистки, включая
  `USER` — `_BoxListenable` (`hive_ce_flutter/src/box_extensions.dart`)
  фильтрует по `keys!.contains(event.key)`, так что и логин (`put`), и
  логаут (`clear`, при условии что `USER` был установлен ранее) реально
  доходят до `_onAuthChanged`, а не только точечный `put` по тому же ключу.
- **Триггер 2 — смена гостевого кода страны.**
  `AppCacheService.saveGuestCountryCode(countryCode)` пишет в
  `SharedPreferences` и синхронно обновляет
  `guestCountryCodeNotifier.value = countryCode` → `_onGuestCountryChanged`
  → `load()`.
- **Триггер 3 — синхронизация справочника стран.**
  `CountriesRepository.syncCountries()` (HANDBOOKS, вне этого модуля)
  последней строкой выставляет `AppCacheService.boardEnabledSyncNotifier.value
  = DateTime.now()` → `_onBoardEnabledSynced` → `load()`. Внутри
  `syncCountries()`: `boardEnabledIds = await getBoardEnabledCountryIds()`
  (`GET ${Constants.boardServiceApi}/countries`), затем `country.copyWith(
  boardEnabled: Value(boardEnabledIds.contains(c.id)))` для **каждой**
  страны справочника, `clearAndInsertAll(updatedCountries)` — весь локальный
  справочник стран перезаписывается разом при каждом проходе.

Ни один из трёх обработчиков (`_onAuthChanged`/`_onGuestCountryChanged`/
`_onBoardEnabledSynced`) не различает, какой именно триггер сработал — все
три вызывают один и тот же `load()`, с одним и тем же `_getCurrentCountry()`
внутри.

### Альтернативные потоки

- **Гость без сохранённого кода страны** (свежая установка до выбора
  страны) — `_getCurrentCountry()` возвращает `null` немедленно, без единого
  обращения к `CountriesRepository`; состояние — `false`.
- **Авторизован, но `getUser() == null`** — защитный случай, структурно не
  гарантированный: `return null` без единого обращения к
  `CountriesRepository`; не покрыт ни одним тестом файла.
- **Авторизован, `countryId` не совпал ни с одной страной, и
  `phoneCountryIsoCode` тоже не совпал (или пуст/`null`)** — оба пути
  резолва исчерпаны, `_getCurrentCountry()` возвращает `null`; состояние —
  `false`.
- **Авторизован, `countryId` не задан, но `phoneCountryIsoCode` совпадает по
  коду** — fallback единственный сработавший путь; состояние зависит только
  от `boardEnabled` найденной страны.
- **Сбой сети внутри `getBoardEnabledCountryIds()` во время триггера 3.**
  Метод перехватывает **любое** исключение и молча возвращает `[]`
  (`catch (_) { return []; }`) — после этого `syncCountries()` продолжает
  как обычно: **все** страны справочника получают `boardEnabled: false`
  через `copyWith`, `clearAndInsertAll` перезаписывает весь справочник, и
  `boardEnabledSyncNotifier` всё равно выставляется — кубит пересчитывается
  и, если до этого прохода страна пользователя была `boardEnabled: true`,
  раздел BOARD молча выключается для этой страны (и фактически для всех
  стран разом), без лога, без ретрая, без какого-либо отличия от
  легитимного «эта страна действительно не входит в BOARD».
- **Раздел BOARD физически недостижим только для трёх вкладок нижней
  навигации, но не для маршрутов.** `routes.dart` не содержит ни одной
  проверки этого флага ни для одного маршрута BOARD — прямой
  `context.pushNamed2`/`context.go('/board/...')`/`'/chats'` (кроме двух
  уже существующих `isAuthorized`-проверок на `/board/create` и `/chats`,
  не связанных со страной) остаётся доступен независимо от состояния этого
  кубита.

### Связанные сущности

- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  сущность, чьё поле `boardEnabled` целиком определяет исход этого сценария;
  читается двумя разными путями (`getAll()` + перебор в памяти для
  авторизованного, точечный `getByCountryCode()` для гостя), не изменяется
  этим модулем.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — читается только
  для авторизованной ветки: поля `countryId` и `phoneCountryIsoCode`
  используются как два независимых, последовательно проверяемых ключа
  резолва страны; не изменяется этим сценарием.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session, AUTH) — поле
  `guestCountryCode` читается для гостевой ветки через
  `AppCacheService.getGuestCountryCode()`; не изменяется этим сценарием.

### Бизнес-правила

- Итоговое состояние — чистая функция от `Country.boardEnabled` найденной
  страны (или его отсутствия) в момент вызова `load()`; кубит не хранит
  предыдущее состояние как часть логики резолва (`emit` не сравнивается с
  предыдущим значением вручную — сравнение `state == _state`, пропускающее
  повторный `emit` при идентичном bool, целиком принадлежит `flutter_bloc`,
  не этому коду).
- Для авторизованного пользователя — `countryId` (точное совпадение по
  `id`) имеет приоритет над `phoneCountryIsoCode` (совпадение по `code`);
  второй проверяется только если первый не задан или не дал совпадения.
- Для гостя — единственный путь резолва: точное совпадение (после
  `.toUpperCase()` с обеих сторон, поскольку `getByCountryCode` не
  документирует регистронезависимость сам) сохранённого кода с `Country.code`.
- Гейт — чисто презентационный: скрывает/показывает вкладки нижней
  навигации и три блока экрана профиля; ни на один маршрут (включая
  создание объявления и чаты, у которых есть отдельная `isAuthorized`-
  проверка) состояние этого кубита не влияет.
- **Скрытие вкладки «Поиск животного» (индекс 1) — непреднамеренный побочный
  эффект, а не бизнес-правило про сам поиск животных.** Вкладка с индексом
  1 в 5-кнопочной раскладке `NavBar` (иконка `searchHeartFill`, `l10n.search`)
  ведёт на `Routes.animalSearch` (`AnimalGlobalOnlineSearchPage`) —
  самостоятельный `StatefulShellBranch`, зарегистрированный в `routes.dart`
  безусловно, без единой связи с BOARD в своём собственном определении.
  Единственная причина её исчезновения при `boardChatAvailable == false` —
  то, что 2-кнопочная раскладка `NavBar` (`else`-ветка) жёстко содержит
  только «Ферма» (индекс 2) и «Профиль» (индекс 4), без слота для поиска
  животного вовсе. Тот же самый `BlocListener` в `main_page.dart` (шаг 7)
  автоматически уводит пользователя со страницы поиска животного (индекс 1
  входит в условие `_currentIndex == 0 || _currentIndex == 1 || _currentIndex
  == 3`) при выключении BOARD по стране, хотя поиск животного — фича модуля
  ANIMAL, не BOARD. Маршрут `Routes.animalSearch` остаётся достижим
  программной навигацией независимо от этого флага — теряется только
  вкладка навбара.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров нет — сценарий полностью реализован, все три триггера достижимы и
воспроизводятся статическим чтением кода, оба ветвления (`гость`/
`авторизован`) полностью покрыты тестами (см. «Связанные тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit` (конструктор, `load`, `_getCurrentCountry`, `_onAuthChanged`, `_onGuestCountryChanged`, `_onBoardEnabledSynced`, `close`) | CURRENT | предмет этого файла целиком — подписки на три источника, единая логика резолва страны |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getAuthBoxListenable`, `.isAuthorized`, `.getUser`, `.logout`, `._saveMainAuthData` | CURRENT | источник триггера 1 (Hive-листенер по ключу `USER`); ветвление гость/авторизован; `logout()`'s `box.clear()` — источник события логаута |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getAll`, `.getByCountryCode`, `.syncCountries`, `.getBoardEnabledCountryIds` | CURRENT | источник данных `Country` для обеих веток резолва; `syncCountries` — источник триггера 3; `getBoardEnabledCountryIds` молча глотает любое сетевое исключение (`catch (_) => []`) |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.guestCountryCodeNotifier`, `.boardEnabledSyncNotifier`, `.getGuestCountryCode`, `.saveGuestCountryCode` | CURRENT | источники триггера 2 и триггера 3; хранилище гостевого кода страны (`SharedPreferences`, не Hive) |
| `lib/main.dart` | `MyApp.build` (`BlocProvider<BoardChatAvailabilityCubit>`) | CURRENT | единственная точка создания кубита — глобально, в корне дерева, выше `go_router` |
| `lib/pages/main/main_page.dart` | `_MainContent.build` (`BlocListener<BoardChatAvailabilityCubit, bool>`, `context.watch<BoardChatAvailabilityCubit>()`, `_onItemTapped`, `_safeFallbackIndex`) | CURRENT | автопереключение на вкладку «Ферма» при переходе в `false`, если пользователь на одной из вкладок 0/1/3; передача состояния в `NavBar` |
| `lib/widgets/bottom_app_bar/nav_bar.dart` | `NavBar.build` | CURRENT | 5-кнопочная раскладка при `true`, 2-кнопочная (без слота поиска животного) при `false` |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | три независимых `BlocBuilder<BoardChatAvailabilityCubit, bool>` | CURRENT | видимость блока «Избранное»/т.п. (только `true`), альтернативного информационного блока (только `false`), нижнего информационного блока (только `true`) |
| `lib/pages/routes.dart` | весь файл (маршруты `Routes.board`, `Routes.boardAdCreate`, `Routes.chats`, `Routes.messages`, `Routes.animalSearch` и их поддерево) | CURRENT | **не содержит ни одной проверки `boardEnabled`/этого кубита** ни для одного маршрута — только `AppCacheService.isAuthorized()` для `/board/create` и `/chats`; `Routes.animalSearch` зарегистрирован безусловно, независимо от BOARD |
| `packages/sheep_farm_database/lib/entities/country/countries.dart` | `Country.boardEnabled` (`BoolColumn`, `nullable()`) | CURRENT | поле, определяющее исход сценария |
| `packages/sheep_farm_database/lib/entities/country/countries_dao.dart` | `CountriesDao.getByCountryCode` | CURRENT | точечный запрос для гостевой ветки |
| `packages/hive_ce_flutter` (внешний пакет) | `BoxX.listenable`, `_BoxListenable.addListener` | CURRENT | фильтрация Hive-событий по `keys.contains(event.key)` — основа триггера 1 |
| `packages/hive_ce` (внешний пакет) | `Keystore.clear` | CURRENT | эмитит `Frame.deleted(key)` для каждого ключа бокса при полной очистке — подтверждает, что логаут (`box.clear()`), не только точечный `put`, тоже долетает до триггера 1 |

## Критерии приёмки

- При изменении записи с ключом `USER` в auth-боксе (логин или логаут)
  кубит пересчитывает состояние без явного вызова `load()` снаружи.
- При сохранении гостевого кода страны (`AppCacheService.saveGuestCountryCode`)
  кубит пересчитывает состояние.
- При завершении `CountriesRepository.syncCountries()` (срабатывание
  `boardEnabledSyncNotifier`) кубит пересчитывает состояние.
- Для авторизованного пользователя: сперва точное совпадение `countryId` с
  `Country.id`; при отсутствии совпадения (включая нечисловой/незаданный
  `countryId`) — регистронезависимый fallback на совпадение
  `phoneCountryIsoCode` с `Country.code`.
- Для гостя: единственный путь — точное (после приведения к верхнему
  регистру) совпадение сохранённого гостевого кода с `Country.code` через
  прямой запрос `getByCountryCode`, без перебора всего справочника.
- Итоговое состояние — `country?.boardEnabled == true`; отсутствие страны,
  `boardEnabled == null` и `boardEnabled == false` дают один и тот же
  результат `false`, неразличимый снаружи кубита.
- Ни один маршрут в `lib/pages/routes.dart` не проверяет состояние этого
  кубита — гейт действует исключительно на уровне видимости вкладок
  `NavBar` и трёх блоков `profile_view.dart`.

## Связанные тесты

`test/blocs/board_chat_availability_cubit_test.dart` — три группы, на
момент написания этой спеки **без номера** (не переименование — первое
присвоение `UC-157`, выполняется отдельным контролируемым проходом):

- group `'BoardChatAvailabilityCubit — гость'`:
  - `'нет сохранённого guest-кода страны -> false'` — конструктор без
    сохранённого кода; `expect(cubit.state, false)` +
    `verifyNever(() => countriesRepository.getByCountryCode(any()))` —
    прямое подтверждение ветки «гость без кода» из «Альтернативные потоки».
  - `'guest-код страны с boardEnabled:true -> true'` — кубит создаётся
    **до** `AppCacheService.saveGuestCountryCode('ru')` — тест тем самым
    одновременно проверяет и резолв гостя, и реактивность триггера 2 (код
    сохраняется уже после создания кубита).
  - `'guest-код страны с boardEnabled:false -> false'` — тот же порядок,
    страна найдена, но `boardEnabled: false`.
- group `'BoardChatAvailabilityCubit — авторизован'`:
  - `'countryId пользователя совпадает с id страны с boardEnabled:true -> true'` —
    прямое подтверждение основного пути резолва по `id`.
  - `'countryId не совпадает ни с одной страной, phoneCountryIsoCode тоже не
    совпадает -> false'` — оба пути резолва исчерпаны.
  - `'countryId не задан, но phoneCountryIsoCode совпадает по коду страны ->
    true'` — прямое подтверждение fallback-пути.
- group `'BoardChatAvailabilityCubit — реактивные подписки'`:
  - `'изменение пользователя в Hive-боксе напрямую триггерит перезагрузку
    (без ручного вызова load())'` — прямое подтверждение триггера 1: кубит
    создаётся при пустом auth-боксе (`state == false`), затем прямой `box.put`
    токена и пользователя без какого-либо обращения к самому кубиту — после
    `pumpEventQueue()` состояние становится `true`.
  - `'boardEnabledSyncNotifier срабатывает -> перезагрузка'` — прямое
    подтверждение триггера 3: гостевой код сохранён и разрешается в `true`,
    мок `getByCountryCode` переключается на `boardEnabled: false`, затем
    `AppCacheService.boardEnabledSyncNotifier.value = DateTime(2026)`
    выставляется напрямую (без вызова `syncCountries()`) — состояние
    становится `false` после `pumpEventQueue()`.

**TBD — теста нет** на ветку «авторизован, но `getUser() == null`»
(защитный случай — ни один тест файла не воспроизводит `isAuthorized() ==
true` при отсутствующей записи `userKey`).

**TBD — теста нет** на сбой сети внутри `getBoardEnabledCountryIds()` во
время `syncCountries()` и последующее массовое обнуление `boardEnabled` —
существующие тесты мокают `CountriesRepository` целиком (`getAll`/
`getByCountryCode`), не воспроизводя внутреннюю логику `syncCountries()`.

**TBD — теста нет** на `NavBar`/`main_page.dart`/`profile_view.dart` —
все существующие тесты проверяют только `BoardChatAvailabilityCubit`
изолированно (bool-состояние), не виджет-уровень (5 vs 2 кнопки,
автопереключение вкладки, три блока профиля, побочное скрытие вкладки
«Поиск животного»).

## Открытые вопросы и ограничения

- **Гейт — чисто UI-уровневый, не route-guard.** `lib/pages/routes.dart`
  не содержит ни одной проверки `boardEnabled`/этого кубита ни для одного
  маршрута BOARD (подтверждено `grep -n "boardEnabled" lib/pages/routes.dart`
  — ноль совпадений; единственные проверки в файле — две проверки
  `AppCacheService.isAuthorized()`, для `/board/create` и `/chats`, не
  связанные со страной). Прямой переход по имени маршрута
  (`context.pushNamed2`/`context.go`) в `/board`, `/board/board_ad_detail`,
  `/chats/messages` и т.п. не блокируется независимо от состояния этого
  кубита — единственное, что реально пропадает при `false`, это точки входа
  в UI (вкладки навбара, кнопки профиля).
- **Сетевой сбой в `getBoardEnabledCountryIds()` тихо выключает BOARD для
  всех стран разом.** Любое исключение перехватывается и превращается в
  пустой список без лога и без ретрая; последующий `syncCountries()` пишет
  `boardEnabled: false` в **каждую** строку справочника, и следующий
  реактивный пересчёт (триггер 3 всё равно срабатывает, независимо от
  исхода) может молча выключить ранее доступный BOARD для страны
  пользователя — неотличимо от легитимного «эта страна не входит в BOARD».
- **Скрытие вкладки «Поиск животного» — не задокументированное нигде явно
  побочное сцепление модулей.** Вкладка индекса 1 в `NavBar` ведёт на
  `Routes.animalSearch` (модуль ANIMAL, `AnimalGlobalOnlineSearchPage`),
  зарегистрированный в `routes.dart` безусловно и не имеющий никакого
  собственного отношения к доступности BOARD по стране. Она пропадает из
  навигации и триггерит автопереключение на «Ферма»
  (`main_page.dart`'s `BlocListener`, условие включает индекс 1) при
  `boardChatAvailable == false` только потому, что 2-кнопочная раскладка
  `NavBar` жёстко ограничена «Фермой» и «Профилем», без слота для поиска.
  Является ли это осознанным продуктовым решением («в странах без BOARD
  поиск животного тоже не нужен») или непреднамеренным следствием того, что
  обе фичи делят один и тот же переключатель раскладки навбара — ничем в
  коде/комментариях не зафиксировано.
- **`country == null`, `boardEnabled == null` и `boardEnabled == false` не
  различимы ни в состоянии кубита, ни в UI.** Пользователь, чья страна не
  резолвилась вовсе (например рассинхронизированный локальный кэш `Country`),
  и пользователь страны, явно не входящей в BOARD, видят один и тот же
  результат — `false`, без какого-либо сообщения, объясняющего разницу.
- **Логаут через `box.clear()` подтверждён как надёжный источник триггера 1
  только чтением исходников внешнего пакета** (`hive_ce`'s
  `Keystore.clear()` эмитит `Frame.deleted(key)` на каждый существовавший
  ключ, `hive_ce_flutter`'s `_BoxListenable` фильтрует по `event.key`) — ни
  один тест файла не воспроизводит именно логаут (`AuthRepository.logout()`
  → `box.clear()`) как источник реактивного пересчёта; единственный
  реактивный тест auth-триггера воспроизводит прямой `box.put` (эквивалент
  логина), не `clear()` (эквивалент логаута).
- Три независимых `BlocBuilder<BoardChatAvailabilityCubit, bool>` в
  `profile_view.dart` (вместо одного общего `watch`) — не проверено, дают
  ли они наблюдаемо иное поведение перерисовки по сравнению с одной общей
  подпиской; на функциональный исход сценария (итоговое bool-состояние) это
  не влияет.
