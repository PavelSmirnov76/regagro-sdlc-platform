# UC-201 — Проверка обновления приложения после sync-прохода технически завершается успешно, но не имеет ни одного видимого эффекта: единственный слушатель молчит (закомментирован), а ручной экран проверки недостижим из навигации

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) |
| Сущность | [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же реактивный шаг, что описан в [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) —
сразу после успешного завершения полного sync-прохода (`DataUpdateSuccess`,
инициированного либо автоматически [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md),
либо вручную пользователем [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md))
`data_update_page.dart` диспатчит `AppUpdateBloc.add(AppUpdateEventCheckUpdate(
showModalMessage: true))`. Здесь описан путь, в котором сама проверка версии
**технически проходит без ошибки** — прод-гейт открыт, `AppUpdateRepository.checkNewVersionRintIos`
либо не бросает исключения вовсе (внутренний `try/catch` метода — предмет
отдельного `READ_ERROR`-сценария, не этого файла), корректно обращается к
`itunes.apple.com/lookup`, сравнивает версии и (при найденной новой версии)
корректно перечитывает только что сохранённую запись из Hive-бокса —
`READ_OK` в смысле «чтение состояния ENT-24 не отказало».

Ключевая находка этого прохода: **независимо от того, какая из двух
технически успешных развилок случилась — найдена новая версия или нет —
пользователь в текущем живом коде не видит вообще никакого сигнала об
этом**, ни в момент автоматического триггера, ни при отдельно найденном в
коде ручном триггере (кнопка «На главную» на экране ошибки синка, см.
«Альтернативные потоки»). Совпадение трёх независимых фактов даёт это
молчание:

1. `main_page.dart`'s `BlocListener<AppUpdateBloc, AppUpdateState>` реагирует
   только на `state is AppUpdateNewVersion && state.showModalMessage` — то
   есть только на ветку «найдена новая версия»; на `AppUpdateMessage`
   (`'no_updates_required'`/`'internet_connection_required'`), `AppUpdateInitial`
   и `AppUpdateInProgress` этот листенер не реагирует вовсе — эти три
   состояния бесследно проходят мимо.
2. Внутри этого листенера единственная реально исполняемая ветка —
   `else` (`immediate == false`) — состоит из **одной закомментированной
   строки**: `// AppUpdatePage.showModalMessage(context, newVersion: state.newVersion);`.
   Ветка `if (state.newVersion.immediate)` структурно недостижима — единственный
   источник данных всегда конструирует `immediate: false` (см.
   [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)), — то есть
   **обе ветки этого `if/else` сегодня ничего не делают**: одна недостижима
   по данным, вторая закомментирована.
3. Единственный код, который вообще умеет реагировать на `AppUpdateMessage`/`AppUpdateInitial`/`AppUpdateInProgress`
   (`AppUpdatePage`'s собственный `BlocConsumer`), находится на странице,
   которая **сама недостижима из живой навигации приложения** — см.
   «Альтернативные потоки», подпункт про `AppUpdatePage`.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение, действующее
автоматически, без отдельного пользовательского жеста в момент самого
триггера этого события: `data_update_page.dart`'s `BlocConsumer<DataUpdateBloc,
DataUpdateState>.listener` диспатчит `AppUpdateEventCheckUpdate(showModalMessage:
true)` реактивно, как прямое следствие перехода в `DataUpdateSuccess`, а не
по отдельному нажатию. Полный sync-проход, чьё завершение запускает эту
проверку, мог быть начат ранее одним из двух акторов:

- [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — автоматически при старте
  приложения ([EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md));
- [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — вручную, кнопкой
  «Синхронизировать данные»/«Повторить» ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)).

Дальше, вплоть до самого диспатча `AppUpdateEventCheckUpdate`, никакого
дополнительного пользовательского действия не требуется — переход
осуществляет сам код `data_update_page.dart` при получении состояния
`DataUpdateSuccess`.

Отдельно, в самом коде найдены ещё два места, диспатчащие то же событие
`AppUpdateEventCheckUpdate` уже по прямому нажатию человека — кнопка «На
главную» на экране ошибки синка (`data_update_page.dart`) и кнопка
обновления/иконка refresh внутри `AppUpdatePage` — оба разобраны в
«Альтернативные потоки». В обоих случаях инициатор — человек, нажимающий
кнопку, а не приложение, реагирующее на завершение прохода без участия
пользователя; при этом [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)
как единый артефакт называет единственным инициатором [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)
и уже описывает оба класса триггера («автоматически» и «также вручную»)
внутри одного события — расхождение с общим правилом «один инициатор на
событие» (`events/AGENTS.md`) зафиксировано как факт в «Открытые вопросы»,
без правки самого замороженного [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md).

## CURRENT

### Основной поток

1. Полный sync-проход завершается `DataUpdateSuccess` (`DataUpdateBloc.on<DataUpdateStartAll>`,
   после [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)
   или [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)).
   `data_update_page.dart`'s `BlocConsumer<DataUpdateBloc, DataUpdateState>.listener`
   реагирует на `state is DataUpdateSuccess`: `Navigator.of(context).pop()`
   (закрывает саму `DataUpdatePage`, под ней остаётся `MainPage`), затем
   `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage:
   true))`.
2. `AppUpdateBloc.on<AppUpdateEventCheckUpdate>`: первой строкой —
   `if (!Constants.isProd) return;` — вне прод-сборки (обычный `flutter run`/`flutter
   test` без `--dart-define=IS_PROD=true`) обработчик завершается немедленно,
   не эмитя ни одного состояния. В прод-сборке — продолжает.
3. `emit(AppUpdateInProgress(messageKey: 'checking_for_updates'))`.
4. Если `_currentVersionNumber == 0` (всегда так при первом вызове за время
   жизни `AppUpdateBloc`, поле не персистентно) — вызывается `PackageInfo.fromPlatform()`
   и результат кладётся в `_currentVersionNumber`; это поле дальше нигде не
   читается ни в этом обработчике, ни где-либо ещё в файле — вычисление
   мёртвое (см. «Открытые вопросы»).
5. `isNetworkConnected = await NetworkConnectivityService.hasConnection()` —
   DNS-резолв `google.com` (`InternetAddress.lookup`), не связан с последующим
   сетевым вызовом к Apple.
6. `packageInfo = await PackageInfo.fromPlatform()` (второй вызов за этот же
   обработчик) → `needUpdate = await AppUpdateRepository.checkNewVersionRintIos(packageInfo.version)`:
   `GET https://itunes.apple.com/lookup?bundleId=Constants.itunesBundleId`
   (безусловно, для любой платформы — см. [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)),
   разбирает первый элемент `results`, строит `NewAppVersion(number, code,
   description, immediate: false, launchDate: null, url, localPath: '')`,
   сохраняет его в Hive (`saveNewAppVersion`), возвращает
   `_isNewerVersion(storeVersion, currentVersion)` (сравнение major.minor.patch
   по частям, отсутствующие части приравниваются к `0`). В этом сценарии
   (`READ_OK`) вызов завершается без исключения.
7. `if (!isNetworkConnected) emit(AppUpdateMessage('internet_connection_required'));`
   `else if (!needUpdate) emit(AppUpdateMessage('no_updates_required'));` —
   первое из двух независимых `if`-выражений обработчика.
8. Второе, независимое `if`-выражение: `if (needUpdate) { _newVersion = await
   AppUpdateRepository.getNewVersion(); emit(AppUpdateNewVersion(_newVersion!,
   showModalMessage: event.showModalMessage)); } else { emit(AppUpdateInitial()); }` —
   `getNewVersion()` перечитывает тот же Hive-бокс, куда шаг 6 только что
   записал значение (успешное чтение — вклад `READ_OK` в само `ENT-24`).
9. Наблюдаемый пользователем итог, для обеих технически успешных развилок
   шага 6 (`needUpdate == true` и `needUpdate == false`, при `isNetworkConnected
   == true`, наиболее частый случай на практике):
   - `needUpdate == false`: два `emit` подряд — `AppUpdateMessage('no_updates_required')`,
     затем `AppUpdateInitial()`. Ни на одно из двух состояний `main_page.dart`'s
     листенер не подписан ни строкой кода — оба проходят мимо без следа.
   - `needUpdate == true`: один `emit(AppUpdateNewVersion(newVersion, showModalMessage:
     true))`. `main_page.dart`'s `BlocListener<AppUpdateBloc, AppUpdateState>`
     реагирует (единственный код, вообще подписанный на этот тип
     состояния): `if (state.newVersion.immediate) { AppUpdatePage.show(context); }
     else { // AppUpdatePage.showModalMessage(context, newVersion: state.newVersion); }`.
     `state.newVersion.immediate` — всегда `false` (единственный источник
     конструирует его так, см. [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)) →
     всегда выполняется `else`-ветка → единственная строка внутри неё
     закомментирована → **ничего не происходит**.
10. Итог: и в шаге 9а, и в шаге 9б — при полностью успешной, безошибочной
    технической проверке (`READ_OK`) — пользователь не получает ни
    snackbar'а, ни модального окна, ни перехода на экран обновления, ни
    какого-либо иного заметного эффекта. Разница между «обновление есть» и
    «обновления нет» с точки зрения интерфейса **отсутствует** — оба исхода
    неотличимы от «эта проверка вообще не запускалась».

### Альтернативные потоки

- **`isNetworkConnected == false` одновременно с `needUpdate == true`.**
  `hasConnection()` (DNS-резолв `google.com`) и `checkNewVersionRintIos`
  (HTTP к `itunes.apple.com`) — два независимых сетевых вызова к разным
  хостам, выполняемые последовательно, не эксклюзивно друг другу. При
  расхождении их результатов (например, `google.com` недоступен в сети
  пользователя, а `itunes.apple.com` — доступен) шаг 7 эмитит
  `AppUpdateMessage('internet_connection_required')`, а шаг 8 сразу следом —
  `AppUpdateNewVersion(..., showModalMessage: true)` — то есть код способен
  эмитить взаимно противоречащие состояния одно за другим в рамках одного
  обработчика. На сегодняшний наблюдаемый эффект это не влияет: оба всё
  равно проходят мимо `main_page.dart`'s листенера тем же путём, что в шаге
  9 — сообщение никем не читается, `AppUpdateNewVersion` попадает на
  закомментированную ветку.
- **Кнопка «На главную» на экране ошибки синка — реально существующий,
  достижимый из навигации, но не описанный в [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)
  третий триггер.** Внутри `_DataUpdateInProgressWidgetState.build`
  (`data_update_page.dart`), в ветке `DataUpdateFailure` (`widget.isError ==
  true`), кнопка `go_to_home` выполняет `Navigator.of(context).pop(); context.go(Routes.mainNavigator);
  context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage:
  true));` — то есть та же проверка запускается **после неудавшегося** sync-прохода,
  когда пользователь вручную закрывает экран ошибки, а не «сразу после
  успешного завершения», как сформулировано в [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md).
  Инициатор здесь — явное нажатие человека ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)
  по факту действия, хотя единственным зафиксированным инициатором события
  в его метаданных значится [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md)).
  Дальнейшее поведение (шаги 2–10) идентично основному потоку.
- **Ручной триггер внутри `AppUpdatePage` (кнопка «Проверить обновления»/иконка
  refresh) — структурно недостижим из живой навигации приложения.**
  Проверено: `grep -rn "AppUpdatePage" lib/` находит ссылки только в двух
  файлах — самом `app_update_page.dart` и `main_page.dart`; `lib/pages/routes.dart`
  не содержит ни одного маршрута к этой странице (`Routes` — константы
  всех маршрутов проекта, среди них нет `AppUpdatePage`); ни один экран
  профиля/настроек не строит пункт меню или кнопку, ведущую сюда (`profile_view.dart`
  показывает версию приложения только как текст, без тап-обработчика).
  Единственные два места, конструирующие `Navigator`-переход на
  `AppUpdatePage`, оба недостижимы сегодня:
  1. `main_page.dart`'s тот же листенер, ветка `if (state.newVersion.immediate)`
     → `AppUpdatePage.show(context)` — недостижима, `immediate` всегда `false`
     (см. основной поток, шаг 9б, и [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)).
  2. `AppUpdatePage.showModalMessage(...)`'s кнопка «Подробнее»
     (`AppUpdatePage.show(context)` после `Navigator.of(context).pop()`) —
     сама `showModalMessage` вызывается ровно в одном месте всего кода,
     `main_page.dart`, и эта единственная строка вызова **закомментирована**
     (та же строка, что и в основном потоке, шаг 9б).
  Следствие: `AppUpdatePage` целиком (включая кнопку «Проверить обновления»,
  refresh-иконку, экран «Новая версия», кнопку «Перейти в стор») —
  недостижимый из UI код в текущей версии приложения, несмотря на то, что
  сам класс полностью реализован и синтаксически корректен.
- **Не прод-сборка (`Constants.isProd == false`).** Шаг 2 основного потока
  прерывает обработчик без единого `emit` — состояние `AppUpdateBloc`
  остаётся `AppUpdateInitial()` (начальное значение конструктора), сеть не
  опрашивается вовсе, `checkNewVersionRintIos`/Hive не трогаются. Это ветвление
  относится к самому обработчику, а не к успешности/неуспешности проверки —
  проверка в этом случае не выполняется вовсе, а не завершается с ошибкой.
- **«Обязательное» обновление (`immediate == true`, блокирующий `WillPopScope`
  на `AppUpdatePage`) — структурно недостижимо: единственный источник данных
  всегда передаёт `immediate: false`.** Уже задокументировано в
  [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md), не разбирается
  здесь заново.

### Связанные сущности

- [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion) —
  сущность, чьё состояние здесь и читается, и пишется: `checkNewVersionRintIos`
  (шаг 6) сохраняет свежую запись в Hive-бокс `NEW_APP_VERSION_BOX_KEY`,
  `getNewVersion()` (шаг 8) читает её же обратно для передачи в
  `AppUpdateNewVersion`. Оба обращения в этом сценарии успешны — предмет
  `READ_OK`.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) — не
  читается и не изменяется этим сценарием напрямую, но именно переход
  `DataUpdateBloc` в состояние `DataUpdateSuccess` (описанное этой сущностью
  и оркестровкой [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)/[EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md))
  — единственное условие, реактивно запускающее шаг 1 основного потока;
  без него `AppUpdateEventCheckUpdate` в этом (не ручном) пути не был бы
  диспатчен вовсе.

### Бизнес-правила

- Проверка обновления в проде выполняется безусловно для **любой**
  платформы через iTunes Lookup API — на Android версия сборки сравнивается
  с версией из iOS App Store, что лишено смысла (см. [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)).
  Вне прод-сборки обработчик не делает ничего.
- Сравнение версий — по числовым частям `major.minor.patch`, отсутствующие
  части (`storeVersion`/`currentVersion` разной длины) приравниваются к
  `0`; при равенстве всех трёх частей `_isNewerVersion` возвращает `false`
  (обновление не считается нужным).
- Нет ретрая и нет backoff — проверка выполняется ровно один раз на каждый
  диспатч `AppUpdateEventCheckUpdate`, следующая попытка — только при
  следующем таком диспатче (новый успешный/проваленный sync-проход или,
  структурно недостижимо сегодня, повторное открытие `AppUpdatePage`).
- Результат проверки (найдена версия или нет) не влияет на UI сегодня ни в
  каком случае — единственная точка, где различие между исходами могло бы
  стать видимым (`main_page.dart`'s листенер), сама не реализована для
  недостижимой ветки и закомментирована для реально исполняемой.
- `NewAppVersion`, записанная в Hive этим сценарием, переживает процесс —
  следующий вызов `getNewVersion()` (например, если бы `AppUpdatePage`
  когда-нибудь стал достижим) прочитал бы именно её, пока не случится
  следующий успешный `checkNewVersionRintIos` или явный `clear()`
  (последний нигде не вызывается в живом коде, кроме тестов).

## TARGET

TARGET не отличается от CURRENT. Задача этого прохода — зафиксировать
текущее поведение статическим чтением кода, не проектировать исправление
найденного молчания (восстановление закомментированного вызова, починка
достижимости `AppUpdatePage`, разделение [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)
на события с явно разными инициаторами и т.д. в рамках этого документирующего
прохода не проектируются).

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (технически успешная
проверка версии через `AppUpdateRepository.checkNewVersionRintIos`, обе
развилки — «найдена новая версия» и «обновлений не требуется» — и оба
независимых `if`-выражения обработчика) полностью прослежен статическим
чтением `AppUpdateBloc.on<AppUpdateEventCheckUpdate>`. Недостижимость
`AppUpdatePage` из живой навигации подтверждена по всем найденным точкам
входа (`grep -rn "AppUpdatePage" lib/`, отсутствие маршрута в `lib/pages/routes.dart`).
Не проверено эмпирически на реальном запуске против настоящего
`itunes.apple.com` (вывод сделан статическим чтением кода и существующих
тестов, см. «Связанные тесты» — сам сетевой прод-путь тестом не покрыт).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdatePageState.build` (`BlocConsumer<DataUpdateBloc, DataUpdateState>.listener`) | CURRENT | диспатчит `AppUpdateEventCheckUpdate(showModalMessage: true)` реактивно на `DataUpdateSuccess` — основной триггер этого UC |
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdateInProgressWidgetState.build` (кнопка `go_to_home` в ветке `DataUpdateFailure`) | CURRENT | второй, реально достижимый диспатч того же события после неудавшегося (не успешного) sync-прохода — см. «Альтернативные потоки» |
| `lib/blocs/app_update/app_update_bloc.dart` | `AppUpdateBloc.on<AppUpdateEventCheckUpdate>` | CURRENT | вся оркестрация: прод-гейт, `NetworkConnectivityService.hasConnection`, вызов репозитория, оба независимых `if`-выражения, оба `emit` |
| `lib/blocs/app_update/app_update_event.dart` | `AppUpdateEventCheckUpdate` | CURRENT | событие бlока, поле `showModalMessage` |
| `lib/blocs/app_update/app_update_state.dart` | `AppUpdateInitial`, `AppUpdateInProgress`, `AppUpdateMessage`, `AppUpdateNewVersion` | CURRENT | все четыре состояния; `AppUpdateInitial`/`AppUpdateInProgress`/`AppUpdateMessage` не имеют ни одного достижимого слушателя вне `AppUpdatePage` |
| `lib/repositories/app_update/app_update_repository.dart` | `AppUpdateRepository.checkNewVersionRintIos`, `.saveNewAppVersion`, `.getNewVersion`, `._versionStringToInt`, `._isNewerVersion` | CURRENT | сетевой вызов к iTunes, сохранение/чтение Hive, сравнение версий |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | независимый от iTunes-вызова DNS-резолв `google.com` |
| `lib/pages/main/main_page.dart` | `MainPage.build` (`BlocListener<AppUpdateBloc, AppUpdateState>`) | CURRENT | единственный код, вообще подписанный на `AppUpdateNewVersion`; закомментированная строка внутри `else`-ветки — предмет центральной находки этого UC |
| `lib/pages/app_update/app_update_page.dart` | `AppUpdatePage`, `AppUpdatePage.show`, `AppUpdatePage.showModalMessage`, `_AppUpdatePageState` | CURRENT, недостижим из навигации | единственный код, реагирующий на `AppUpdateMessage`/`AppUpdateInitial`/`AppUpdateInProgress` — сам недостижим |
| `lib/pages/routes.dart` | `Routes` | CURRENT | не содержит маршрута к `AppUpdatePage` — подтверждает недостижимость |
| `lib/main.dart` | `MyApp.build` (`BlocProvider<AppUpdateBloc>`) | CURRENT | `AppUpdateBloc` — синглтон на всё приложение, создаётся один раз выше `go_router` |
| `lib/constants.dart` | `Constants.isProd`, `.itunesBundleId`, `.appStoreUrl`, `.playMarketAppUrl` | CURRENT | прод-гейт и параметры сетевого вызова/ссылок на сторы |
| `packages/sheep_farm_database/lib/entities/new_app_version/new_app_version.dart` | `NewAppVersion`, `NewAppVersionHive` | CURRENT | сущность [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md), читаемая/пишемая шагами 6 и 8 |
| `lib/data/services/app_cache_service.dart` | `AppCacheService._openBoxes` (открытие `NEW_APP_VERSION_BOX_KEY`) | CURRENT | гарантирует, что Hive-бокс уже открыт к моменту вызова `saveNewAppVersion`/`getNewVersion` |

## Критерии приёмки

- При `Constants.isProd == true`, сразу после `DataUpdateSuccess`,
  `AppUpdateBloc` получает `AppUpdateEventCheckUpdate(showModalMessage: true)`
  и эмитит `AppUpdateInProgress`, затем (без исключения из
  `checkNewVersionRintIos`) — либо `AppUpdateMessage('no_updates_required')` +
  `AppUpdateInitial()` (если найденная версия не новее текущей), либо
  `AppUpdateNewVersion(newVersion, showModalMessage: true)` (если новее);
  при недоступности `hasConnection()` дополнительно эмитится
  `AppUpdateMessage('internet_connection_required')` перед этим же вторым
  `emit`.
- Оба обращения к Hive-хранилищу [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)
  (`saveNewAppVersion` внутри `checkNewVersionRintIos`, `getNewVersion` при
  `needUpdate == true`) завершаются без исключения в этом сценарии.
- `main_page.dart`'s `BlocListener<AppUpdateBloc, AppUpdateState>` — реагирует
  только на `AppUpdateNewVersion && showModalMessage == true`; при
  `state.newVersion.immediate == false` (всегда так) единственная
  предусмотренная реакция (`AppUpdatePage.showModalMessage`) не выполняется,
  так как соответствующая строка кода закомментирована — итог: ни модального
  окна, ни перехода, ни любого иного эффекта.
- Состояния `AppUpdateMessage`, `AppUpdateInitial`, `AppUpdateInProgress` не
  имеют в живом дереве виджетов ни одного слушателя — единственный код,
  реагирующий на них (`AppUpdatePage`'s `BlocConsumer`), не монтируется
  никогда, так как ни один путь навигации к `AppUpdatePage` не достижим
  (оба существующих вызова `AppUpdatePage.show`/`showModalMessage`
  структурно недостижимы или закомментированы, `lib/pages/routes.dart` не
  содержит маршрута к этой странице).
- Второй, реально достижимый диспатч `AppUpdateEventCheckUpdate(showModalMessage:
  true)` — кнопка «На главную» на экране `DataUpdateFailure` — приводит к
  тому же набору состояний и тому же отсутствию видимого эффекта, несмотря
  на то, что предшествующий sync-проход в этом случае завершился неудачей,
  а не `DataUpdateSuccess`.
- Вне прод-сборки (`Constants.isProd == false`) обработчик `AppUpdateEventCheckUpdate`
  не эмитит ни одного состояния — `AppUpdateBloc` остаётся в исходном
  `AppUpdateInitial()`.

## Связанные тесты

`test/blocs/app_update_bloc_test.dart` — единственный тест, без `group()`:

```
blocTest<AppUpdateBloc, AppUpdateState>(
  'CheckUpdate в не-prod сборке завершается сразу, без единого emit '
  '(Constants.isProd == false для обычного `flutter test`)',
  ...
)
```

Файл открывается дисклеймером-комментарием: «`AppUpdateBloc` опирается на:
`Constants.isProd` (compile-time константа, `false` для обычного `flutter
test` без `--dart-define=IS_PROD=true`), `hasNetworkConnection()` (реальный
DNS-запрос), `package_info_plus`/`path_provider`/`open_file`/`android_intent_plus`
(реальные platform channels). Юнит-тестом реалистично покрывается только
то, что не упирается в эти зависимости — раннее завершение при
`!Constants.isProd`. Остальное см. `TESTING_CHECKLIST.md`.» — то есть этот
единственный тест проверяет **гейт «вне прода — не эмитить»**
(«Альтернативные потоки», последний пункт), а не основной поток этого
use-case (реальный вызов `checkNewVersionRintIos`, оба независимых
`if`-выражения, обе развилки `needUpdate`) — **TBD — теста нет** на сам
прод-путь `READ_OK`.

`test/repositories/app_update_repository_test.dart`, группа `'getNewVersion /
saveNewAppVersion / clear'` — три теста (`'пустой бокс -> getNewVersion
возвращает null'`, `'saveNewAppVersion сохраняет, getNewVersion читает
обратно'`, `'clear очищает бокс'`) косвенно подтверждают, что локальное
Hive-хранение [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)
(шаги 6 и 8 основного потока — запись и обратное чтение) работает корректно
при уже открытом боксе; ни один из них не вызывает сам
`checkNewVersionRintIos` (сетевой iTunes-вызов не мокается и не
проверяется в этом файле вовсе — `grep -n "checkNewVersionRintIos"
test/repositories/app_update_repository_test.dart` не находит совпадений).
Тот же файл содержит группу `'БАГ: сохранение версии с непустым launchDate'`
(`HiveError`-баг) — не относится к `READ_OK`, `launchDate` в этом сценарии
всегда `null` (см. [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)).

Ни `main_page.dart`'s листенер, ни диспатч из `data_update_page.dart`, ни
недостижимость `AppUpdatePage` не покрыты ни одним тестом:
`test/pages/main_page_test.dart` открывается комментарием «`MainPage`/`_MainContent`
сами по себе не тестируются виджет-тестом: требуют реального
`StatefulNavigationShell` (go_router), минимум 6 одновременных Bloc/Cubit
через `BlocProvider`/`context.watch` (`FabVisibilityCubit`, `AuthBloc`,
`AppUpdateBloc`, `DataUpdateBloc`, `UserPermissionsBloc`, `LanguageBloc`,
`BoardChatAvailabilityCubit`) и `AppCacheService` (Hive). Единственная в
файле чистая, независимая от виджет-дерева логика — геометрия кастомного
расположения FAB, она и протестирована ниже.» — то есть весь листенер,
центральный для находки этого UC, не тестируется в принципе этим файлом.
`test/pages/data_update_page_test.dart` покрывает только `group('DataUpdatePage.show()
— защита от повторного открытия', ...)`; состояние `DataUpdateSuccess`
(и, следовательно, диспатч `AppUpdateEventCheckUpdate`) в этом файле нигде
не эмитится — **TBD — теста нет** на весь путь «`DataUpdateSuccess` →
диспатч → молчание `main_page.dart`».

## Открытые вопросы и ограничения

- **Закомментированная строка `AppUpdatePage.showModalMessage(context, newVersion:
  state.newVersion)` в `main_page.dart` — намеренное временное отключение
  фичи или забытая правка?** Комментарий рядом с самим `BlocProvider<AppUpdateBloc>`
  в `main.dart` («Обновление приложения / Первый запуск с показом модального
  окна») описывает именно то поведение, которое сейчас закомментировано —
  ничто в коде/истории коммитов, доступной этому проходу, не объясняет,
  почему строка отключена именно так, а не удалена вместе с остальным
  функционалом (см. коммит `f971f006`, уже зафиксированный в [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)
  как убравший другие мёртвые пути обновления).
- **`AppUpdatePage` целиком — недостижимый, но полностью реализованный
  код.** Не решено (и не в периметре этого документирующего прохода),
  является ли это кандидатом на удаление (по аналогии с уже вычищенными
  Android/Regagro-путями, см. [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md))
  или на восстановление точки входа (раскомментирование строки в
  `main_page.dart` плюс, отдельно, добавление явного пункта в
  `routes.dart`/профиль для ручной проверки).
- **[EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) как единый
  артефакт объединяет автоматический (`ACTOR-3`, сразу после
  `DataUpdateSuccess`) и как минимум два человеческих триггера (кнопка «На
  главную» на экране ошибки синка, кнопка/иконка внутри `AppUpdatePage`) под
  одним инициатором.** Формально расходится с «Exactly one initiator per
  event» (`../events/AGENTS.md`) — зафиксировано здесь как наблюдение,
  правка самого замороженного [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)
  вне периметра этого файла.
- **`_currentVersionNumber` (поле `AppUpdateBloc`) вычисляется, но нигде не
  читается** — второй избыточный вызов `PackageInfo.fromPlatform()` за один
  и тот же обработчик, не влияющий на итоговое сравнение версий
  (`_isNewerVersion` использует `packageInfo.version`, не это поле). Не
  влияет на наблюдаемое поведение, отмечено как найденная мёртвая
  вычислительная ветка.
- Не проверено эмпирически на реальном запуске против настоящего
  `itunes.apple.com/lookup` — вывод о технической успешности проверки
  (`READ_OK`) сделан статическим чтением `AppUpdateRepository.checkNewVersionRintIos`
  и подтверждающих его репозиторных тестов на локальное Hive-хранение (см.
  «Связанные тесты»), не запущенным сквозным тестом, воспроизводящим сам
  сетевой вызов и последующую (отсутствующую) реакцию `main_page.dart`.
