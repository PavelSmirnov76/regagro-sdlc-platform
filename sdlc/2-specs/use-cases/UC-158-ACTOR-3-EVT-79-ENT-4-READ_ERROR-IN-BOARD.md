# UC-158 — Проверка доступности BOARD по стране отказывает: сбой одного шага справочника стран тихо отключает раздел для всех стран разом

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md) |
| Сущность | [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Тот же реактивный пересчёт, что описан в [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md) —
`BoardChatAvailabilityCubit` перечитывает `country?.boardEnabled == true` при
любом из трёх триггеров (смена авторизованного пользователя, смена гостевой
страны, завершение `CountriesRepository.syncCountries()`). Здесь описан
единственный реально наблюдаемый в коде путь отказа этого чтения — и он
**не** проявляется как исключение, долетающее до `BoardChatAvailabilityCubit`.
`CountriesRepository.getBoardEnabledCountryIds()` (`lib/repositories/country/countries_repository.dart`)
оборачивает сетевой вызов к `${Constants.boardServiceApi}/countries` в
собственный `try/catch`, который перехватывает **любое** исключение и
безусловно возвращает пустой список — без единой строки лога (ни `Talker`,
ни `dart:developer`, ничего). `syncCountries()` вызывает этот метод **вторым**
шагом, уже после того как первый шаг — `getCountriesFromApi()`, отдельный
запрос к другому пути того же API-хоста, `${Constants.handbookServiceApi}/overpass/countries`
— успешно завершился и вернул полный список стран. То есть этот сценарий
наступает именно тогда, когда общий обмен со справочным сервисом жив, а
конкретно board-специфичный эндпоинт того же хоста — недоступен, отвечает
ошибкой или таймаутит: частичный, а не полный сетевой отказ.

Наблюдаемый пользователем итог — не ошибка, а **тихое исчезновение всего
раздела BOARD** (вкладки «Доска»/«Сообщения» в навбаре, блоки в профиле) для
**вообще всех стран одновременно**, как только текущий пользователь окажется
на устройстве, где этот отказ уже произошёл при последней синхронизации
справочников — неотличимо от легитимного «в этой стране BOARD отключён
бизнес-правилом». Дополнительно проверена и задокументирована отдельным
под-пунктом единственная найденная в самом `BoardChatAvailabilityCubit`
(не через `CountriesRepository`) точка, где исключение теоретически могло бы
возникнуть — синхронное чтение Hive-бокса авторизации; см. «Альтернативные
потоки».

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение, действующее
автоматически. Прямого пользовательского действия в момент самого отказа
нет: сбой происходит внутри `CountriesRepository.syncCountries()`, вызванного
первым шагом `DataUpdateBloc.loadDirectories()` — частью полного sync-прохода
(`on<DataUpdateStartAll>`), который мог быть запущен одним из нескольких
источников:

- явно пользователем — кнопка обновления в `main_page.dart`, `profile_settings_view.dart`,
  `in_work_page.dart` или `data_update_page.dart`;
- автоматически приложением — `main_page.dart`'s `BlocListener<AuthBloc,
  AuthState>` диспатчит `DataUpdateStartAll` при переходе `AuthToMain` (успешное
  восстановление сессии/вход), без отдельного нажатия «обновить».

`loadDirectories()` (и, следовательно, `syncCountries()`) выполняется
безусловно для **любого** актора — и гостя, и авторизованного пользователя,
`_authRepository.isAuthorized()` проверяется только для шага `_syncAuthData`,
идущего строго после. Реактивный пересчёт самого `BoardChatAvailabilityCubit`
после этого отказа тоже не зависит от актора, инициировавшего исходный
sync-проход — он подписан на `AppCacheService.boardEnabledSyncNotifier`
глобально, для любого текущего пользователя приложения (гостя или
авторизованного), находящегося на экране в момент срабатывания.

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети (`NetworkConnectivityService.hasConnection()` — истинно, иначе
   `DataUpdateFailure` сразу, до входа сюда) вызывает `await
   loadDirectories(event, emit)` внутри общего `try`.
2. `loadDirectories()` (`lib/blocs/data_update/data_update_bloc.dart`) первым
   действием вызывает `await _countriesRepository.syncCountries(updatedAtGt:
   lastSyncDate)` — **без своего `try/catch`** вокруг этого конкретного
   вызова (внешний `try` — на уровне `on<DataUpdateStartAll>`, шаг 1).
3. Внутри `CountriesRepository.syncCountries()`: `final countries = await
   getCountriesFromApi();` — `GET ${Constants.handbookServiceApi}/overpass/countries`,
   без собственного `try/catch` в этом методе. В этом сценарии вызов
   успешен и возвращает полный (или инкрементальный, при непустом
   `updatedAtGt`) список `Country`.
4. `final boardEnabledIds = await getBoardEnabledCountryIds();` — второй,
   независимый запрос, `GET ${Constants.boardServiceApi}/countries` (другой
   путь того же API-хоста, отдельный сервисный сегмент). Внутри — `try {
   ...; return (response['data'] as List).map((e) => e['country_id'] as
   int).toList(); } catch (_) { return []; }`. В этом сценарии
   `client.call(message)` (тот же `CustomDioClient.call`, что и во всех
   остальных RPC-вызовах приложения) бросает исключение — сеть недоступна,
   таймаут, либо любой не-2xx HTTP-ответ именно на этом пути (Dio по
   умолчанию бросает исключение вне 200–299, `DioClient` не переопределяет
   `validateStatus`). **`catch (_)` перехватывает исключение любого типа, не
   читает и не логирует его** (никакого `Talker`, никакого
   `dart:developer.log`, в отличие от большинства других сетевых вызовов
   приложения) и возвращает `<int>[]`.
5. `syncCountries()` продолжает как ни в чём не бывало: `final
   updatedCountries = countries.map((c) => c.copyWith(boardEnabled:
   Value(boardEnabledIds.contains(c.id)))).toList();` — поскольку
   `boardEnabledIds` пуст, `.contains(c.id)` ложно для **абсолютно каждой**
   строки, независимо от того, каким было её реальное состояние на сервере
   или в локальной таблице до этого прохода.
6. `await clearAndInsertAll(updatedCountries);` — `BaseRepository.clearAndInsertAll`
   → `dao.clearAndInsertAll(list)`: полностью очищает локальную таблицу
   `Countries` и вставляет её заново — **все** ранее сохранённые значения
   `boardEnabled` (включая корректные `true` от предыдущих успешных
   синхронизаций) безвозвратно заменяются на `false`, без какого-либо
   частичного/merge-обновления и без сохранения «последнего известного
   хорошего» состояния где-либо ещё.
7. `AppCacheService.boardEnabledSyncNotifier.value = DateTime.now();` —
   выставляется **безусловно**, в конце метода, независимо от того, был ли
   шаг 4 успешным или отказал. `syncCountries()` возвращает управление без
   исключения — `loadDirectories()`, `on<DataUpdateStartAll>` (шаг 1)
   продолжают как при полностью штатном исходе; весь sync-проход в итоге
   завершается `DataUpdateSuccess` (если остальные независимые шаги не
   упали по другой причине) — **никакого наблюдаемого пользователем
   сигнала об этом отказе не возникает нигде в приложении**.
8. Присвоение `boardEnabledSyncNotifier.value` синхронно уведомляет всех
   слушателей `ValueNotifier` — в частности, глобально предоставленный
   `BoardChatAvailabilityCubit._onBoardEnabledSynced`, который вызывает
   `load()` немедленно, для текущего пользователя приложения (гостя или
   авторизованного), независимо от того, кто/что инициировало исходный
   sync-проход на шаге 1.
9. `BoardChatAvailabilityCubit.load()` → `_getCurrentCountry()`: для
   авторизованного — ищет страну по `user.countryId`/`user.phoneCountryIsoCode`
   среди `_countriesRepository.getAll()` (та же, только что перезаписанная
   локальная таблица); для гостя — `_countriesRepository.getByCountryCode(guestCode)`.
   В обоих случаях резолвится (если резолвится вообще) строка `Country`, чьё
   поле `boardEnabled` теперь равно `false` — независимо от того, каким
   оно было секунду назад и каким остаётся на самом сервере для стран, чей
   реальный список board-enabled id не менялся вовсе.
10. `emit(country?.boardEnabled == true)` → `false`. `main_page.dart`'s
    `BlocListener<BoardChatAvailabilityCubit, bool>` реагирует: если
    `_currentIndex` пользователя в этот момент — 0 («Доска»), 1 («Поиск»)
    или 3 («Сообщения»), выполняется принудительный переход на
    `_safeFallbackIndex` (индекс 2, «Ферма/место»), без какого-либо
    сообщения о причине. `NavBar.build` перестраивает нижнюю навигацию по
    ветке `else` (без вкладок «Доска»/«Поиск»/«Сообщения»). Три
    `BlocBuilder<BoardChatAvailabilityCubit, bool>` в `profile_view.dart`
    скрывают/меняют соответствующие блоки профиля тем же флагом.

### Альтернативные потоки

- **Гость и авторизованный пользователь страдают одинаково.** Ни
  `syncCountries()`, ни срабатывание `boardEnabledSyncNotifier`, ни
  `BoardChatAvailabilityCubit._onBoardEnabledSynced` не различают, кто
  сейчас использует приложение — эффект глобален для локальной базы,
  затрагивает любого пользователя этого устройства, оказавшегося в
  приложении после отказавшей синхронизации, независимо от того, кто её
  запустил.
- **Отказ первого шага (`getCountriesFromApi()`), в отличие от второго, не
  тихий.** Если сетевой вызов внутри `getCountriesFromApi()` (не
  `getBoardEnabledCountryIds()`) бросает исключение — у этого метода нет
  собственного `try/catch` — оно всплывает необработанным из
  `syncCountries()`, из `loadDirectories()`, до внешнего `catch` в
  `on<DataUpdateStartAll>` (шаг 1): пользователь видит явный `DataUpdateFailure`,
  локальная таблица `Countries` вообще не трогается (`clearAndInsertAll` не
  достигается), `boardEnabledSyncNotifier` не выставляется. Это **не** тот
  же класс отказа, что описан в основном потоке — приведён здесь только как
  контраст: только отказ именно `getBoardEnabledCountryIds()` (шаг 4)
  проходит незамеченным, отказ соседнего шага (шаг 3) — нет.
- **Проверенная отдельно под-ветка: исключение внутри самого
  `BoardChatAvailabilityCubit`, не через `CountriesRepository`.** Три места
  в цепочке этого кубита читают Hive-бокс авторизации напрямую, синхронным
  вызовом `Hive.box<dynamic>(AuthRepository.authBoxKey)`
  (`AuthRepository._getAuthBox()`), который бросает `HiveError`, если этот
  бокс не открыт в памяти на момент вызова: (1) конструктор
  `BoardChatAvailabilityCubit()` — `_authRepository.getAuthBoxListenable(keys:
  [AuthRepository.userKey])`, вызывается синхронно, не внутри `try/catch`;
  (2) `_getCurrentCountry()` → `_authRepository.isAuthorized()` →
  `getMainTokenData()`; (3) та же функция → `_authRepository.getUser()` —
  обе тоже не обёрнуты ни в какой `try/catch` ни в `_getCurrentCountry()`,
  ни в `load()`. Если бы любое из этих трёх мест бросило исключение, оно
  не было бы поймано нигде в этой цепочке: (1) — синхронное исключение
  из конструктора всплыло бы прямо из `BlocProvider.create` в `main.dart`,
  до появления самого `BoardChatAvailabilityCubit` в дереве провайдеров —
  принципиально другой отказ, не эмиссия `bool`; (2)/(3) — произошли бы
  внутри `async load()`, вызываемого в конструкторе и во всех трёх
  `_onXChanged`-колбэках **без `await` и без `.catchError`** — исключение
  стало бы необработанной ошибкой `Future`, видимой (если вообще) только
  зоне Dart по умолчанию (`runApp` в `main.dart` не обёрнут в
  `runZonedGuarded` — соответствующий вызов закомментирован), `emit()` на
  этом пути так и не был бы достигнут, и `state` кубита просто застыл бы на
  предыдущем значении без каких-либо дальнейших признаков проблемы. Прочтением
  `lib/main.dart` подтверждено: `AppCacheService.logHiveBox()` (которая
  открывает `AUTH_BOX` через `Hive.openBox` внутри `_openBoxes`) вызывается
  до `runApp()`, а `BoardChatAvailabilityCubit()` конструируется только
  один раз, внутри `MyApp.build`, то есть уже после `runApp()` — при
  текущем порядке операций в `main()` бокс гарантированно уже открыт к
  этому моменту, и ни один из трёх пунктов не наступает на практике. Эта
  гарантия обеспечена только порядком строк в `main()`, не какой-либо
  проверкой/контрактом в самом коде `BoardChatAvailabilityCubit`/`AuthRepository`
  (`grep -rn "\.close()" lib/` не находит ни одного места, закрывающего этот
  бокс в рантайме — открывается один раз при старте и не закрывается до
  конца жизни процесса).

### Связанные сущности

- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  сущность, чьё физическое состояние портится этим сценарием:
  `clearAndInsertAll` перезаписывает **всю** локальную таблицу, выставляя
  `boardEnabled = false` каждой строке, независимо от предыдущего значения;
  читается заново сразу после этого же кубитом через `getAll()`/`getByCountryCode()`.
- `User` ([ENT-1](../entities/ENT-1-USER-IN-AUTH.md), AUTH) — читается (не
  изменяется) в `_getCurrentCountry()` для авторизованной ветки:
  `user.countryId`/`user.phoneCountryIsoCode` определяют, какая строка
  `Country` резолвится и, следовательно, какое (уже испорченное)
  `boardEnabled` будет использовано.
- Session/токен ([ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), AUTH,
  Hive `AUTH_BOX`) — читается через `AuthRepository.isAuthorized()`/`.getUser()`/`.getAuthBoxListenable()`;
  единственное место в этой цепочке, где в принципе возможно исключение, не
  проходящее через `CountriesRepository` (см. «Альтернативные потоки»); не
  изменяется этим сценарием.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad), [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md)
  (Chat) — не читаются и не изменяются этим сценарием напрямую, но их
  экраны (лента, «Мои объявления», список чатов) становятся физически
  недостижимы из навигации, пока флаг остаётся `false` — единственная
  причина, по которой этот сценарий вообще имеет пользовательские
  последствия за пределами самой таблицы `Country`.

### Бизнес-правила

- Доступность BOARD пересчитывается реактивно из уже сохранённого локально
  `Country.boardEnabled`, не прямым запросом к серверу в момент проверки —
  корректность флага полностью зависит от того, насколько недавняя
  синхронизация справочника стран была успешной именно на шаге
  `getBoardEnabledCountryIds()`.
- Отказ этого конкретного шага в текущем коде **неотличим** от легитимного
  «сервер явно вернул пустой список board-enabled стран» — оба случая
  приводят к тому же `boardEnabledIds == []` и тому же результату
  `boardEnabled: false` для всех строк.
- `clearAndInsertAll` не делает частичного обновления — отказ одного
  сетевого запроса стирает результаты **всех** предыдущих успешных
  синхронизаций этого поля одновременно, не только тех стран, которые
  реально стали недоступны сейчас.
- Нет ретрая, нет backoff, нет отдельного индикатора отказа — единственный
  способ восстановить корректные значения `boardEnabled` — следующий
  успешный (в части `getBoardEnabledCountryIds()`) полный sync-проход,
  запущенный любым из перечисленных в «Пользователь» способов.
- Гость и авторизованный пользователь используют один и тот же локальный
  кэш `Countries` — исправление или порча этого поля одним действием
  (синхронизацией) видна сразу обоим классам актора на этом устройстве.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (тихий проглот
исключения в `CountriesRepository.getBoardEnabledCountryIds()`, безусловная
перезапись `Countries.boardEnabled` в `false` для всех строк,
`DataUpdateSuccess` без какого-либо видимого сигнала) полностью
воспроизводится статическим чтением кода: `DataUpdateBloc.loadDirectories`
→ `CountriesRepository.syncCountries` → `.getBoardEnabledCountryIds` →
`CustomDioClient.call`. Проверенная отдельно под-ветка (исключение в самом
`BoardChatAvailabilityCubit` через чтение Hive-бокса авторизации) также
прослежена статически и признана структурно возможной, но на сегодня
недостижимой при текущем порядке инициализации `main()` — см.
«Альтернативные потоки». Исправление (например, проверка/лог результата
`getBoardEnabledCountryIds()`, сохранение предыдущего значения при отказе
вместо безусловного `false`, обёртка `load()`/конструктора кубита в
`try/catch`) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getBoardEnabledCountryIds` | CURRENT | предмет основного потока — `catch (_) { return []; }`, любое исключение поглощается без лога |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getCountriesFromApi`, `.syncCountries` | CURRENT | `getCountriesFromApi` — без `try/catch`, контрастная (не тихая) ветка отказа; `syncCountries` — оркестрация: оба сетевых шага, `clearAndInsertAll`, безусловный notifier |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>`, `.loadDirectories` | CURRENT | запускает `syncCountries()` первым шагом полного sync-прохода; сам проход не видит отказ шага 4 и завершается `DataUpdateSuccess` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.boardEnabledSyncNotifier`, `.guestCountryCodeNotifier`, `.getGuestCountryCode` | CURRENT | реактивные источники; первый выставляется безусловно в конце `syncCountries()` |
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit` (конструктор, `load`, `_getCurrentCountry`, `_onAuthChanged`/`_onGuestCountryChanged`/`_onBoardEnabledSynced`) | CURRENT | получатель испорченных данных; ни один из трёх реактивных путей и ни сам `load()` не обёрнуты в `try/catch` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized`, `.getUser`, `.getAuthBoxListenable`, `._getAuthBox` | CURRENT | делегируют в синхронный `Hive.box<dynamic>(authBoxKey)` — единственный найденный источник исключения не через `CountriesRepository` (см. «Альтернативные потоки») |
| `lib/main.dart` | `main()` (порядок: `Hive.initFlutter` → … → `AppCacheService.logHiveBox()` → … → `runApp`) | CURRENT | единственная причина, по которой найденная Hive-под-ветка сегодня не наступает — `AUTH_BOX` открывается раньше, чем конструируется кубит; не закреплено никаким контрактом в самом коде кубита |
| `lib/pages/main/main_page.dart` | `BlocListener<BoardChatAvailabilityCubit, bool>` | CURRENT | единственный потребитель, реагирующий принудительной навигацией на `false`, независимо от причины |
| `lib/widgets/bottom_app_bar/nav_bar.dart` | `NavBar.build` | CURRENT | скрывает/показывает вкладки «Доска»/«Поиск»/«Сообщения» по тому же флагу |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | три `BlocBuilder<BoardChatAvailabilityCubit, bool>` | CURRENT | скрывают/показывают блоки профиля по тому же флагу |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | источник исключения, которое перехватывает `catch (_)` внутри `getBoardEnabledCountryIds` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе |
| `lib/constants.dart` | `Constants.handbookServiceApi`, `.boardServiceApi` | CURRENT | разные сегменты одного API-хоста — объясняют, почему шаг 3 может быть успешным, а шаг 4 (другой сегмент) — нет |
| `packages/sheep_farm_database/lib/entities/country/countries.dart` | `Countries.boardEnabled` | CURRENT | nullable `bool`-колонка без дефолта — и `null`, и `false` дают один и тот же наблюдаемый эффект в `country?.boardEnabled == true` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clearAndInsertAll` | CURRENT | полная перезапись таблицы `Countries`, без частичного/merge-обновления |

## Критерии приёмки

- Если `client.call(message)` внутри `CountriesRepository.getBoardEnabledCountryIds()`
  бросает исключение любого типа, метод возвращает `<int>[]` без исключения
  и без единой записи в лог (`Talker`/`dart:developer`).
- `syncCountries()` в этом случае продолжает без ошибки: каждая строка
  `Country` из `updatedCountries` получает `boardEnabled == false`,
  `clearAndInsertAll` полностью заменяет локальную таблицу этим набором,
  `AppCacheService.boardEnabledSyncNotifier.value` обновляется безусловно.
- Полный sync-проход (`on<DataUpdateStartAll>`), внутри которого произошёл
  этот отказ, не переходит в `DataUpdateFailure` из-за него — при отсутствии
  других независимых причин отказа проход завершается `DataUpdateSuccess`.
- Сразу после обновления `boardEnabledSyncNotifier`, `BoardChatAvailabilityCubit.load()`
  эмитит `false` для **любой** страны, независимо от актора (гость/авторизованный)
  и от того, было ли реальное серверное значение `boardEnabled` для этой
  страны `true` до этого прохода.
- Пользователь, находящийся в момент этой эмиссии на индексе навигации
  0/1/3, принудительно переводится на индекс 2 (`main_page.dart`); нижняя
  навигация (`NavBar`) и три блока `profile_view.dart` скрывают
  BOARD-элементы — без какого-либо текста/иконки/снэкбара, объясняющего
  причину.
- Конструктор `BoardChatAvailabilityCubit()` и все вызовы `load()`
  (прямой в конструкторе и три реактивных из `_onAuthChanged`/
  `_onGuestCountryChanged`/`_onBoardEnabledSynced`) не содержат `try/catch` —
  любое исключение из чтения Hive-бокса авторизации (`AuthRepository.getAuthBoxListenable`/`.isAuthorized`/`.getUser`)
  либо всплывает синхронно из конструктора (если это происходит в момент
  создания кубита), либо становится необработанной ошибкой `Future` (если
  это происходит внутри `load()`), не изменяя видимое состояние `bool`.

## Связанные тесты

`test/blocs/board_chat_availability_cubit_test.dart` существует и покрывает
только успешные комбинации:

- group `'BoardChatAvailabilityCubit — гость'`: `'нет сохранённого guest-кода
  страны -> false'`, `'guest-код страны с boardEnabled:true -> true'`,
  `'guest-код страны с boardEnabled:false -> false'`.
- group `'BoardChatAvailabilityCubit — авторизован'`: `'countryId
  пользователя совпадает с id страны с boardEnabled:true -> true'`,
  `'countryId не совпадает ни с одной страной, phoneCountryIsoCode тоже не
  совпадает -> false'`, `'countryId не задан, но phoneCountryIsoCode
  совпадает по коду страны -> true'`.
- group `'BoardChatAvailabilityCubit — реактивные подписки'`: `'изменение
  пользователя в Hive-боксе напрямую триггерит перезагрузку (без ручного
  вызова load())'`, `'boardEnabledSyncNotifier срабатывает -> перезагрузка'`.

Ни один из семи тестов не мокает `countriesRepository.getAll()`/`.getByCountryCode()`
как бросающий исключение, и ни один не проверяет реальный
`CountriesRepository.getBoardEnabledCountryIds`/`.syncCountries` (мокается
только интерфейс `CountriesRepository` целиком — `getBoardEnabledCountryIds`
в тестовом дублере не участвует вовсе). Отдельного файла
`test/repositories/countries_repository_test.dart` не существует
(`find test -iname "*countries_repository*"` — пусто).

**TBD — теста нет** на сценарий, описанный этим файлом: ни на молчаливый
проглот исключения в `getBoardEnabledCountryIds()` и последующую
безусловную перезапись `boardEnabled: false` для всех стран внутри
`syncCountries()`, ни на найденную под-ветку исключения из Hive-бокса
авторизации внутри самого `BoardChatAvailabilityCubit` (ни конструктор, ни
`load()`, ни один из трёх `_onXChanged`-колбэков не вызываются в тестах в
condition, где `AuthRepository`/`Hive.box` бросали бы исключение).

## Открытые вопросы и ограничения

- **Безусловное «отказ = отключено для всех» — намеренное решение (fail-closed
  для платного/гейтируемого раздела) или недосмотр — ничем в коде/комментариях
  не зафиксировано.** Ничто не отличает содержательный ответ сервера «в этой
  стране BOARD выключен» от «мы не смогли спросить сервер вовсе» — оба дают
  один и тот же локально сохранённый `false`.
- **Отсутствие лога делает этот отказ невидимым даже для разработчика.**
  В отличие от подавляющего большинства сетевых вызовов приложения
  (`rethrow` после `getIt<Talker>().error(...)`, см., например,
  [UC-156](UC-156-ACTOR-1-EVT-78-ENT-20-READ_ERROR-IN-BOARD.md) для похожего
  по механике, но залогированного отказа), здесь `catch (_)` не читает и не
  печатает исключение никуда — ни в `Talker`, ни в `dart:developer.log`.
  Диагностировать этот сценарий постфактум (например, по логам пользователя)
  невозможно в принципе.
- **`clearAndInsertAll` стирает «последнее известное хорошее» состояние
  безвозвратно.** Нет отдельного шага, который сохранял бы предыдущее
  значение `boardEnabled` при отказе именно этого запроса и восстанавливал
  бы его вместо `false` — единственный способ вернуться к корректным
  значениям — дождаться следующего полностью успешного прохода
  синхронизации справочников.
- **Найденная Hive-под-ветка (см. «Альтернативные потоки») зависит только от
  порядка операций в `main()`, не от явного контракта.** Сегодня
  `AppCacheService.logHiveBox()` гарантированно открывает `AUTH_BOX` раньше,
  чем строится единственный экземпляр `BoardChatAvailabilityCubit` — но эта
  гарантия нигде не закреплена (ни ассертом, ни тестом, ни комментарием
  рядом с конструктором кубита); переупорядочивание вызовов в `main()` в
  будущем могло бы молча вернуть этот путь к жизни. Не воспроизведено тестом
  и не проверено эмпирически (перевод бокса в закрытое состояние в
  момент конструирования кубита не смоделирован).
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода
  (`CountriesRepository.getBoardEnabledCountryIds` → `CustomDioClient.call` →
  `DioClient`), без запущенного теста, подтверждающего именно эту ветку (см.
  «Связанные тесты» — TBD). В частности, не подтверждено, действительно ли
  `${Constants.boardServiceApi}/countries` и `${Constants.handbookServiceApi}/overpass/countries`
  на практике когда-либо отказывают независимо друг от друга (оба —
  разные пути одного и того же хоста `Constants.hostApiRint`, не
  обязательно разные физические сервисы за ним).
