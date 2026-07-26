# UC-202 — Автопроверка обновления после синка: нет сети или сбой iTunes-запроса эмитят сообщение, которое не долетает ни до одного экрана

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) |
| Сущность | [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Два формально разных технических отказа одного и того же чтения —
(а) на устройстве нет сети в момент проверки и (б) `checkNewVersionRintIos`
падает при обращении к `itunes.apple.com/lookup` или при разборе ответа —
в текущем коде **неотличимы друг от друга и оба структурно невидимы
пользователю**. `AppUpdateRepository.checkNewVersionRintIos`
(`lib/repositories/app_update/app_update_repository.dart`) оборачивает весь
сетевой вызов и разбор ответа в собственный `try/catch`, который перехватывает
любое исключение, логирует его через `Talker` и возвращает `false` — метод
физически не может бросить исключение наружу, поэтому в `AppUpdateBloc`
(`lib/blocs/app_update/app_update_bloc.dart`) нет и не может быть
try/catch-ветки для случая (б): для блока это уже не исключение, а обычное
`needUpdate == false`. Случай (а) — независимая проверка
`NetworkConnectivityService.hasConnection()` (DNS-запрос к `google.com`,
`lib/services/network_connectivity_service.dart`) — даёт свою собственную
ветку сообщения, но **не отменяет** реальный HTTP-запрос к iTunes: тот всё
равно выполняется безусловно, даже когда устройство уже точно офлайн.

Дополнительно проверено и задокументировано отдельным фактом: единственный
экран, где сообщение об этих отказах вообще показалось бы (`AppUpdatePage`,
через `BlocConsumer`'ный `SnackBar`), в текущей сборке **недостижим ни из
какой живой навигации** — см. «Основной поток», шаг 9.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение, действующее
автоматически. Прямого пользовательского жеста в момент самого отказа нет:
проверка запускается диспатчем `AppUpdateEventCheckUpdate(showModalMessage:
true)` из `lib/pages/data_update/data_update_page.dart`, у которого два живых
источника:

- автоматически, сразу после `DataUpdateSuccess` — `BlocListener<DataUpdateBloc,
  DataUpdateState>` в `DataUpdatePage` диспатчит проверку сразу после
  завершения полного sync-прохода ([EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)/[EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)),
  независимо от того, кто запустил сам sync-проход (ACTOR-3 автоматически при
  старте либо [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) вручную);
- человеческим жестом, но тем же кодовым путём — кнопка «На главную»
  (`go_to_home`) на экране `DataUpdateFailure` внутри той же
  `DataUpdatePage.dart` тоже диспатчит `AppUpdateEventCheckUpdate(showModalMessage:
  true)`. Это фактически более реалистичный триггер именно для случая (а):
  пользователь оказывается на этой кнопке чаще всего именно потому, что
  предыдущий sync-проход уже отказал из-за отсутствия сети
  (`DataUpdateBloc.on<DataUpdateStartAll>` проверяет сеть первым шагом — см.
  `.claude/rules/domain-model.md`), и в момент нажатия «На главную» сеть, как
  правило, всё ещё отсутствует.

Также существует полностью ручной путь — иконка refresh в `AppBar`
`AppUpdatePage` и кнопка «Проверить обновления» на экране `AppUpdateInitial`
(обе — `AppUpdateEventCheckUpdate()` с `showModalMessage: false` по
умолчанию), но он требует, чтобы `AppUpdatePage` уже была открыта — что в
текущей сборке не происходит ни из какого живого экрана (см. шаг 9).

## CURRENT

### Основной поток

1. `DataUpdateSuccess` (или нажатие «На главную» на `DataUpdateFailure`) →
   `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage:
   true))` (`data_update_page.dart`).
2. `AppUpdateBloc.on<AppUpdateEventCheckUpdate>`: `if (!Constants.isProd)
   return;` — вне прод-сборки (в т.ч. любой обычный `flutter test`) обработчик
   завершается, не эмитив ни одного состояния. Весь дальнейший поток этого
   сценария существует только в прод-сборке.
3. `emit(AppUpdateInProgress(messageKey: 'checking_for_updates'))`.
4. `_currentVersionNumber` вычисляется через `PackageInfo.fromPlatform()`,
   только если он ещё `0` — вычисленное значение нигде далее в классе не
   читается (мёртвое присваивание, не влияет ни на одну ветку этого
   сценария).
5. `isNetworkConnected = await getIt<NetworkConnectivityService>().hasConnection()`
   — DNS-запрос к `google.com`, полностью независимая от iTunes проверка.
6. **Безусловно**, независимо от результата шага 5, вызывается
   `needUpdate = await _appUpdateRepository.checkNewVersionRintIos(packageInfo.version)`
   — реальный `dio.get('https://itunes.apple.com/lookup', ...)`. Внутри
   `checkNewVersionRintIos` весь запрос и разбор ответа обёрнуты в
   `try { ... } catch (e) { getIt<Talker>().error('Ошибка проверки версии
   через iTunes: $e'); return false; }` — это касается и случая (а) (нет
   сети → `dio.get` бросает исключение, поймано здесь же) и случая (б)
   (сеть есть, но `itunes.apple.com` недоступен/таймаутит/отвечает
   не-2xx/присылает JSON без ожидаемых полей `results`/`version` — все эти
   пути тоже кидают исключение при разборе и тоже ловятся тем же `catch`).
   Метод физически не может вернуть управление иначе, чем через `bool` —
   **исключение никогда не долетает до `AppUpdateBloc`**, поэтому в самом
   блоке try/catch вокруг вызова репозитория нет и не нужен.
7. `if (!isNetworkConnected) { emit(AppUpdateMessage('internet_connection_required')); }
   else if (!needUpdate) { emit(AppUpdateMessage('no_updates_required')); }`
   — `if`/`else if`, эмитится ровно одно из двух сообщений (в обоих
   изучаемых здесь случаях `needUpdate` уже `false`, так как шаг 6 не мог
   вернуть иначе при отказе).
8. Отдельным, не `else`-связанным условием сразу следом: `if (needUpdate) {
   ...эмит AppUpdateNewVersion... } else { emit(AppUpdateInitial()); }`. Так
   как `needUpdate == false` в обоих случаях (а) и (б), это **второе emit**
   срабатывает немедленно вслед за сообщением из шага 7 — на один
   диспатч `AppUpdateEventCheckUpdate` в обоих отказных случаях уходит
   последовательность `AppUpdateInProgress` → `AppUpdateMessage(...)` →
   `AppUpdateInitial()`, три состояния подряд.
9. **Ни одно из двух emit'ов шагов 7–8 не наблюдаемо нигде в реально
   работающем приложении.** Единственные подписчики на `AppUpdateBloc` в
   проекте:
   - `lib/pages/main/main_page.dart`, `BlocListener<AppUpdateBloc,
     AppUpdateState>` — реагирует только на `state is AppUpdateNewVersion &&
     state.showModalMessage`, полностью игнорируя `AppUpdateMessage` и
     `AppUpdateInitial`. Даже внутри этой ветки: `if (state.newVersion.immediate)
     { AppUpdatePage.show(context); } else { /* AppUpdatePage.showModalMessage(...)
     закомментирован */ }` — а `immediate` структурно всегда `false` (см.
     [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)), значит даже
     ветка «новая версия найдена» сегодня ничего не показывает.
   - `lib/pages/app_update/app_update_page.dart`, собственный
     `BlocConsumer` — вот он действительно показывает `SnackBar` для
     `AppUpdateMessage`. Но сама `AppUpdatePage` **нигде не зарегистрирована
     в `routes.dart`** (`grep -n "appUpdate" lib/pages/routes.dart` — пусто)
     и запускается только через `AppUpdatePage.show(context)`, единственные
     два места вызова которого — упомянутая выше ветка `main_page.dart`
     (гейт `immediate == true`, структурно недостижим) и кнопка «Подробнее»
     внутри `AppUpdatePage.showModalMessage(...)` — а сам
     `showModalMessage(...)` нигде не вызывается вживую (единственная
     ссылка на него в кодовой базе — закомментированная строка в
     `main_page.dart`). Итог: `AppUpdatePage` целиком недостижима из живой
     навигации в текущей сборке (`grep -rn "AppUpdatePage(" lib/` и
     `grep -rn "AppUpdatePage.show" lib/` подтверждают ровно эти четыре
     места, ни одно из них не живое для конечного пользователя).
   - Итог: сообщения `internet_connection_required` (случай а) и
     `no_updates_required` (случай б, при том что реальная причина —
     необработанный технический отказ, а не «вы уже на последней версии»)
     эмитятся в `AppUpdateBloc`, но не производят вообще никакого
     наблюдаемого эффекта — ни `SnackBar`, ни навигации, ни любого другого
     сигнала — нигде в приложении.

### Альтернативные потоки

- **Случай (б) в чистом виде** (сеть в целом есть — `isNetworkConnected ==
  true`, но именно `itunes.apple.com/lookup` недоступен/таймаутит/отвечает
  некорректным JSON) отличается от случая (а) только тем, какое из двух
  сообщений эмитится на шаге 7 (`no_updates_required` вместо
  `internet_connection_required`) — обе ветки одинаково проходят через
  `catch` внутри `checkNewVersionRintIos` и одинаково невидимы (шаг 9).
  Отличить «реально нет обновлений» от «не удалось проверить» невозможно ни
  по состоянию блока, ни тем более пользователем — обе ветки дают
  идентичный `AppUpdateMessage('no_updates_required')`.
- **Третий, не запрошенный явно, но соседний путь возврата `false` без
  исключения**: если HTTP-запрос успешен (2xx), но `results` пуст/`null`
  либо `appInfo.version` пуст — `checkNewVersionRintIos` возвращает `false`
  через `return` внутри `try`, не доходя до `catch` вообще (никакого лога
  `Talker` в этом случае). Технически не исключение, но по наблюдаемому
  пользователем эффекту неотличимо от случаев (а)/(б) — тот же
  `AppUpdateMessage('no_updates_required')`, та же невидимость (шаг 9).
- **Полностью ручной вход** — иконка refresh на `AppBar` `AppUpdatePage`
  или кнопка «Проверить обновления» на состоянии `AppUpdateInitial`
  (`AppUpdateEventCheckUpdate()`, `showModalMessage: false` по умолчанию) —
  единственный путь, где `SnackBar` для `AppUpdateMessage` реально показался
  бы (`AppUpdatePage`'s собственный `BlocConsumer`), но требует, чтобы
  `AppUpdatePage` уже была открыта — что, как показано в шаге 9, недостижимо
  ни из какой живой навигации в текущей сборке.
- **Не-прод сборка** (`flutter build ... --flavor dev` без
  `--dart-define=IS_PROD=true`, и любой обычный `flutter test`) —
  `on<AppUpdateEventCheckUpdate>` завершается на первой строке, не эмитив ни
  одного состояния; весь этот use-case структурно не существует вне прод.

### Связанные сущности

- [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion)
  — сущность, чьё чтение отказывает этим сценарием. `saveNewAppVersion`
  (запись в Hive-бокс `NEW_APP_VERSION_BOX_KEY`) достигается только на
  **успешном** пути `checkNewVersionRintIos` (после удачного парсинга,
  перед `return _isNewerVersion(...)`) — ни случай (а), ни случай (б), ни
  соседний путь с пустым `results` до записи не доходят: ранее
  сохранённая (или отсутствующая) версия в Hive-боксе остаётся как есть,
  ни обновляется, ни очищается. Известный отдельно задокументированный
  риск ENT-24 — `saveNewAppVersion` падает с `HiveError` при непустом
  `launchDate` — этим сценарием не задействуется: `checkNewVersionRintIos`
  всегда конструирует `NewAppVersion(..., null, ...)` для `launchDate`,
  независимо от исхода запроса.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) — не
  читается и не изменяется этим сценарием; это сущность предшествующего
  полного sync-прохода (`DataUpdateSuccess`/`DataUpdateFailure`), чьё
  завершение — единственный автоматический (либо человеческий, через
  «На главную») триггер `AppUpdateEventCheckUpdate(showModalMessage: true)`,
  описанный в «Пользователь».

### Бизнес-правила

- Проверка обновления выполняется только в прод-сборке (`Constants.isProd`);
  вне неё — полный no-op без единого emit.
- Единственный источник истины — синхронный сетевой запрос к
  `itunes.apple.com/lookup` в момент проверки; предварительная проверка
  связности (`NetworkConnectivityService.hasConnection()`) не предотвращает
  этот запрос — он выполняется безусловно, даже когда устройство уже точно
  офлайн.
- Любой технический отказ чтения — будь то отсутствие сети, недоступность
  конкретно `itunes.apple.com`, таймаут или некорректный ответ — сегодня
  структурно неотличим от штатного «обновлений нет» и, независимо от этого,
  не производит никакого наблюдаемого пользователем эффекта нигде в
  приложении.
- Ветка «обязательное обновление» (`immediate == true`), единственная,
  которая заставила бы `main_page.dart` открыть `AppUpdatePage`
  автоматически, структурно недостижима (см.
  [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)) — то есть даже
  штатный положительный исход («найдена новая версия») сегодня не
  показывается автоматически ни в каком виде.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Оба заявленных сценария (а — нет сети в
момент проверки, б — исключение внутри `checkNewVersionRintIos`) полностью
воспроизводятся статическим чтением кода: `AppUpdateBloc.on<AppUpdateEventCheckUpdate>`
→ `NetworkConnectivityService.hasConnection()` / `AppUpdateRepository.checkNewVersionRintIos`
→ `try/catch`, возвращающий `false` без исключения наружу. Недостижимость
`AppUpdatePage` из живой навигации также прослежена статически
(`grep -rn "AppUpdatePage(" lib/`, `grep -rn "AppUpdatePage.show" lib/`,
`grep -n "appUpdate" lib/pages/routes.dart`) и признана полной — не найдено
ни одного живого пути показа. Ни одно из этих наблюдений не воспроизведено
динамически (нет запущенного теста, эмулирующего реальный сбой сети или
реальный ответ iTunes) — см. «Связанные тесты». Исправление (например,
пропуск сетевого вызова при `!isNetworkConnected`, различение технического
отказа и «обновлений нет», подключение `AppUpdatePage`/`SnackBar` к живой
навигации) в рамках этого документирующего прохода не выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/app_update/app_update_bloc.dart` | `AppUpdateBloc.on<AppUpdateEventCheckUpdate>` | CURRENT | оркестрация — ранний выход вне прод, безусловный вызов репозитория независимо от связности, двойной emit (`AppUpdateMessage` + `AppUpdateInitial`) при `needUpdate == false` |
| `lib/blocs/app_update/app_update_state.dart` | `AppUpdateInitial`, `AppUpdateInProgress`, `AppUpdateNewVersion`, `AppUpdateMessage` | CURRENT | состояния; `AppUpdateMessage` — предмет основного потока |
| `lib/blocs/app_update/app_update_event.dart` | `AppUpdateEventCheckUpdate` | CURRENT | единственное живое событие, `showModalMessage` определяет намерение показать модалку (не гарантирует показ) |
| `lib/repositories/app_update/app_update_repository.dart` | `AppUpdateRepository.checkNewVersionRintIos` | CURRENT | предмет случая (б) — `try/catch` вокруг всего сетевого вызова и разбора ответа, логирует через `Talker`, возвращает `false`, никогда не бросает |
| `lib/repositories/app_update/app_update_repository.dart` | `AppUpdateRepository.saveNewAppVersion`, `.getNewVersion` | CURRENT | не достигаются ни на одной из веток этого сценария |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | предмет случая (а) — независимый DNS-запрос к `google.com`, не связан с реальной доступностью `itunes.apple.com` |
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdatePageState.build` (`BlocListener<DataUpdateBloc>`), кнопка «На главную» в `DataUpdateInProgressWidget` | CURRENT | два живых места диспатча `AppUpdateEventCheckUpdate(showModalMessage: true)` |
| `lib/pages/main/main_page.dart` | `BlocListener<AppUpdateBloc, AppUpdateState>` | CURRENT | единственный слушатель блока вне `AppUpdatePage`; реагирует только на `AppUpdateNewVersion && showModalMessage && immediate` (недостижимо); ветка `else` — закомментированный вызов |
| `lib/pages/app_update/app_update_page.dart` | `AppUpdatePage`, `AppUpdatePage.show`, `AppUpdatePage.showModalMessage`, `_AppUpdatePageState.build` (`BlocConsumer`) | CURRENT (недостижим из живой навигации) | единственное место, где `AppUpdateMessage` реально рендерился бы в `SnackBar` — недостижимо: нет маршрута в `routes.dart`, оба вызова `.show()` гейтированы недостижимой `immediate == true`, `.showModalMessage()` нигде не вызывается вживую |
| `lib/pages/routes.dart` | (отсутствие записи для `AppUpdatePage`) | CURRENT | подтверждает отсутствие go_router-маршрута к экрану |
| `packages/sheep_farm_database/lib/entities/new_app_version/new_app_version.dart` | `NewAppVersion`, `NewAppVersionHive` | CURRENT | сущность [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md); `immediate`/`launchDate` не задействуются этим сценарием |
| `lib/constants.dart` | `Constants.isProd`, `Constants.itunesBundleId` | CURRENT | гейт прод-сборки; bundle id для запроса к iTunes |

## Критерии приёмки

- В прод-сборке, при `NetworkConnectivityService.hasConnection() == false` в
  момент диспатча `AppUpdateEventCheckUpdate`, `AppUpdateBloc` тем не менее
  выполняет реальный HTTP-запрос к `itunes.apple.com/lookup` через
  `checkNewVersionRintIos`, и только после его завершения эмитит
  `AppUpdateMessage('internet_connection_required')`, затем немедленно —
  `AppUpdateInitial()`.
- Если `checkNewVersionRintIos` бросает исключение любого происхождения
  (сетевая ошибка, таймаут, не-2xx ответ, ошибка разбора JSON) — исключение
  перехватывается внутри самого метода, логируется через
  `getIt<Talker>().error(...)`, метод возвращает `false` без исключения
  наружу; `AppUpdateBloc` не содержит и не может содержать try/catch вокруг
  этого вызова, так как исключение туда никогда не долетает.
- При `needUpdate == false` (обе ветки — сеть отсутствует, либо
  `checkNewVersionRintIos` вернул `false` по любой причине) `AppUpdateBloc`
  эмитит ровно два состояния подряд на один `AppUpdateEventCheckUpdate`:
  `AppUpdateMessage(...)`, затем `AppUpdateInitial()`.
- Ни `AppUpdateMessage`, ни `AppUpdateInitial` не обрабатываются
  `BlocListener<AppUpdateBloc, AppUpdateState>` в `main_page.dart` — этот
  слушатель фильтрует строго по `AppUpdateNewVersion && showModalMessage`.
- `AppUpdatePage` (единственный виджет, чей `BlocConsumer` показывает
  `SnackBar` для `AppUpdateMessage`) не зарегистрирована ни в одном
  `GoRoute` в `lib/pages/routes.dart`, и оба существующих вызова
  `AppUpdatePage.show(...)` в кодовой базе гейтированы условием
  `newVersion.immediate == true`, которое, по независимо задокументированному
  факту [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md), никогда
  не выполняется единственным живым источником данных.
- Ни на одной из веток этого сценария (а, б, соседняя ветка с пустым
  `results`) не вызывается `AppUpdateRepository.saveNewAppVersion` — ранее
  сохранённое (или отсутствующее) значение в Hive-боксе
  `NEW_APP_VERSION_BOX_KEY` остаётся неизменным.

## Связанные тесты

`test/blocs/app_update_bloc_test.dart` существует и содержит ровно один
тест (`grep -c "blocTest" test/blocs/app_update_bloc_test.dart` → `1`; сам
файл — 42 строки):

```
blocTest<AppUpdateBloc, AppUpdateState>(
  'CheckUpdate в не-prod сборке завершается сразу, без единого emit '
  '(Constants.isProd == false для обычного `flutter test`)',
  ...
);
```

Он покрывает только шаг 2 «Основного потока» (ранний выход вне прод) — не
относится к сценариям (а)/(б) этого use-case. Файл предваряется
дисклеймером:

> `AppUpdateBloc опирается на: Constants.isProd (compile-time константа,
> false для обычного `flutter test` без --dart-define=IS_PROD=true),
> hasNetworkConnection() (реальный DNS-запрос), package_info_plus/
> path_provider/open_file/android_intent_plus (реальные platform channels).
> Юнит-тестом реалистично покрывается только то, что не упирается в эти
> зависимости — раннее завершение при !Constants.isProd. Остальное см.
> TESTING_CHECKLIST.md.`

Этот дисклеймер сам частично устарел: `path_provider`/`open_file`/`android_intent_plus`
не импортируются текущим `app_update_bloc.dart` (эти зависимости относились
к уже удалённому Android-пути скачивания/установки `.apk`, см.
[ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)), а свободная
функция `hasNetworkConnection()` заменена на инжектируемый
`NetworkConnectivityService.hasConnection()` — но итоговый вывод дисклеймера
(реалистично тестируем только путь `!Constants.isProd`) остаётся верным и
сегодня, поскольку `checkNewVersionRintIos` — обычный метод без DI-обёртки
над `Dio()`. Отдельно: `TESTING_CHECKLIST.md` (строка про
`blocs/app_update/app_update_bloc.dart`) указывает «2 теста» для этого
файла — на сегодня в файле фактически один `blocTest`, расхождение не
устраняется этим документирующим проходом.

`test/repositories/app_update_repository_test.dart`, группа «БАГ: сохранение
версии с непустым launchDate — реальная конфигурация Hive» — фиксирует
латентный дефект `saveNewAppVersion` (падение с `HiveError` при непустом
`launchDate`), упомянутый в «Связанные сущности». Это доказательство
существования дефекта в `AppUpdateRepository`, но **не** воспроизводит
сценарий этого use-case: тест напрямую вызывает `saveNewAppVersion` с
искусственно непустым `launchDate`, тогда как реальный путь
`checkNewVersionRintIos` (единственный, что задействован в (а)/(б)) всегда
передаёт `launchDate: null` и до `saveNewAppVersion` в обеих отказных ветках
не доходит вовсе (см. «Критерии приёмки»).

**TBD — теста нет** ни на случай (а) (`hasConnection() == false`,
безусловный вызов `checkNewVersionRintIos`, двойной emit), ни на случай (б)
(исключение внутри `checkNewVersionRintIos`, поглощаемое внутренним
`try/catch`), ни на недостижимость `AppUpdatePage`/`SnackBar` из живой
навигации.

## Открытые вопросы и ограничения

- **Полная невидимость результата проверки — намеренное решение (пауза
  фичи после `f971f006`, до восстановления показа) или недосмотр —
  ничем в коде/комментариях не зафиксировано.** Закомментированный вызов
  `AppUpdatePage.showModalMessage(...)` в `main_page.dart` — единственный
  след того, что показ когда-то был активен; ни issue, ни TODO рядом нет.
- **Двойной emit (`AppUpdateMessage` сразу за которым `AppUpdateInitial`)
  ничем не объяснён** — структура `if (!isNetworkConnected) {...} else if
  (!needUpdate) {...}` затем отдельный `if (needUpdate) {...} else {...}`
  выглядит как след рефакторинга (например, удаления промежуточной ветки),
  не как осознанный дизайн двух последовательных состояний на одно событие.
- **Безусловный сетевой запрос к iTunes даже при уже известном отсутствии
  сети** — `isNetworkConnected` вычисляется, но не используется как ранний
  выход перед вызовом `checkNewVersionRintIos`; при отсутствии сети реальный
  `dio.get(...)` (у `Dio()` без явного `connectTimeout`) всё равно
  выполняется и должен исчерпать таймаут/бросить исключение внутри
  репозитория, прежде чем шаг 7 вообще получит управление — фактическая
  задержка не измерена в рамках этого документирующего прохода.
- Не проверено эмпирически на реальном устройстве против настоящего
  `itunes.apple.com` — вывод сделан статическим чтением кода
  (`AppUpdateBloc.on<AppUpdateEventCheckUpdate>` →
  `NetworkConnectivityService.hasConnection` /
  `AppUpdateRepository.checkNewVersionRintIos`), без запущенного теста,
  воспроизводящего именно сетевой сбой или сбой iTunes (см. «Связанные
  тесты» — TBD).
- `_currentVersionNumber` вычисляется в обработчике (`PackageInfo.fromPlatform()`),
  но нигде в классе `AppUpdateBloc` не читается — не влияет ни на одну ветку
  этого сценария, но остаётся неиспользуемым состоянием поля.
