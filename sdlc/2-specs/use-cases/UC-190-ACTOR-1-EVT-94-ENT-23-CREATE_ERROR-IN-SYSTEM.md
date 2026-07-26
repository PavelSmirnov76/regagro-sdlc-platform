# UC-190 — Ручной запуск полного sync-прохода отказывает: пользователь остаётся на `DataUpdatePage` независимо от того, с какого из двух входов проход был запущен

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

[EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)
запускает ровно тот же обработчик — `DataUpdateBloc.on<DataUpdateStartAll>` —
что и автоматический запуск при старте приложения
([EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)).
Тот же обработчик и тот же класс отказов — сеть недоступна до входа в `try`,
либо исключение внутри `try`, перехваченное единственным внешним `catch` —
уже разобран для автоматического триггера в
[UC-188](UC-188-ACTOR-3-EVT-93-ENT-23-CREATE_ERROR-IN-SYSTEM.md); этот
документ его не переразбирает, а применяет к ручному триггеру, фокусируясь на
том, что специфично именно ему: два равнозначных, но по-разному ведущих себя
входа ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)
уже называет их «а» и «б»), различие флагов `isUpdateData`/`again` между
ними, и то, что именно видит пользователь на экране после
`DataUpdateFailure` в каждом из двух случаев.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
`DataUpdateBloc` — единственный на весь процесс инстанс, поднятый один раз в
корневом `MultiProvider` (`lib/main.dart`, `MyApp.build` →
`BlocProvider<DataUpdateBloc>(create: (context) => DataUpdateBloc())`), общий
для обоих входов и для автоматического триггера — значимо для «Открытых
вопросов» ниже (мутируемые поля-счётчики блока переживают между разными
`DataUpdateStartAll`, включая между входами).

Два входа, оба — диспатч `DataUpdateBloc.add(DataUpdateStartAll(...))`:

- **(а)** кнопка «Синхронизировать данные» на экране «В работе»
  (`lib/pages/in_work/in_work_page.dart`) — `DataUpdateStartAll(isUpdateData:
  true)` (`again`, `showDataUpdatePage` — значения по умолчанию: `false`,
  `true`). Кнопка физически находится на `InWorkPage`, которая в этот момент
  не перекрыта `DataUpdatePage` — по построению навигации это единственный
  момент, когда вход (а) вообще может быть нажат.
- **(б)** кнопка «Попробовать снова» на самом экране ошибки синка
  (`lib/pages/data_update/data_update_page.dart`, `DataUpdateInProgressWidget`,
  ветка `isError: true`) — `DataUpdateStartAll(showDataUpdatePage: false,
  again: true)` (`isUpdateData` — значение по умолчанию `false`). Кнопка
  физически находится на `DataUpdatePage`, которая в этот момент уже
  открыта — по тому же построению навигации вход (б) никогда не запускает
  проход «с нуля»: он ретраит уже показанный отказ, независимо от того, что
  привело к этому отказу — предыдущий вызов входа (а), автоматический запуск
  ([EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md))
  или более ранний вызов самого входа (б).

## CURRENT

### Основной поток

1. Пользователь нажимает один из двух входов, описанных в «Пользователь»;
   `DataUpdateBloc.on<DataUpdateStartAll>` получает событие с
   соответствующими флагами.
2. `_resetProgressCounters()` — тело метода пусто (`void
   _resetProgressCounters() {}`), ничего не сбрасывает; `_currentDataCategory`
   и `_currentDataKey` — обычные изменяемые поля того же долгоживущего
   инстанса блока, их значения от предыдущего прохода (если он был) остаются
   нетронутыми на этот момент (см. «Открытые вопросы»). Сразу эмитится
   `DataUpdateInProgress(progressPercent: 0)`.
3. `lib/pages/main/main_page.dart`'s `BlocListener<DataUpdateBloc,
   DataUpdateState>` реагирует на `DataUpdateInProgress`, вызывая
   `DataUpdatePage.show(context)`. Внутри — статический guard `_isPageOpen`:
   - **вход (а):** `_isPageOpen == false` (иначе кнопка была бы физически
     недостижима, см. «Пользователь») → флаг ставится в `true`,
     `Navigator.of(context, rootNavigator: true).push(MaterialPageRoute(...))`
     реально пушит `DataUpdatePage` поверх `InWorkPage`;
   - **вход (б):** `_isPageOpen == true` (страница уже открыта — с неё и
     была нажата кнопка) → `show()` возвращается немедленно, никакого нового
     push; тот же самый, уже смонтированный виджет `DataUpdatePage`
     продолжает жить, его собственный `BlocConsumer<DataUpdateBloc,
     DataUpdateState>` перестраивает `_Body` по новым состояниям того же
     блока.
4. `await getIt<NetworkConnectivityService>().hasConnection()` — единственный
   сетевой гейт до входа в `try`, идентичен для обоих входов и для
   автоматического триггера.
   - **Ветка А — сети нет.** `emit(DataUpdateFailure(errorTitleKey:
     'internet_connection_required', errorMessageKey: 'check_connection'))`,
     немедленный `return` — до `try`, значит `_addDataUpdateError`/
     `_emitError` не вызываются вовсе: **в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
     не добавляется ни одной строки** для этой под-ветки, несмотря на то что
     `RESULT` этого документа — `CREATE_ERROR` (см. «Бизнес-правила»).
   - **Ветка Б — сеть есть, исключение внутри `try`.** Проход идёт как в
     основном потоке [UC-188](UC-188-ACTOR-3-EVT-93-ENT-23-CREATE_ERROR-IN-SYSTEM.md)
     (`loadDirectories` → `_loadBoardDirectories` → при авторизации
     `_syncAuthData`, который для входа (а) при `isUpdateData: true`
     дополнительно вызывает `_settingsRepository.setSettingToSHTP()`, см.
     ниже) до момента, когда какой-то шаг бросает исключение. Оно
     перехватывается единственным внешним `catch (error, stackTrace)`:
     `getIt<Talker>().error(...)`, затем `_emitError(emit: emit, error: error,
     stackTrace: stackTrace)` → `_addDataUpdateError(dataCategory:
     _currentDataCategory, errorDataKey: _currentDataKey, errorMessage:
     'error: $error, stackTrace: $stackTrace')` — **это единственное место,
     где для этого сценария реально создаётся строка [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)** —
     и `emit(DataUpdateFailure(errorTitleKey: 'an_error_data',
     errorMessageKey: _currentDataKey, errorMessage: ..., isAdressesUpdate:
     false))` (`isAdressUpdate` у `_emitError` не передан ни разу во всём
     `lib/` — параметр всегда `false`, `DataUpdateFailure.isAdressesUpdate`
     этой же веткой и не читается в UI, см. «Открытые вопросы»).
   - `finally` выполняется в обоих случаях (кроме ветки А, у которой
     `return` — внутри `try/catch/finally` целиком, `finally` тоже
     срабатывает): `resetClient('farm_rpc')`, `resetClient('r3_rpc')`.
5. `DataUpdatePage`'s `BlocConsumer` перестраивает `_Body` по
   `DataUpdateFailure`: `DataUpdateInProgressWidget(messageKey:
   '${l10n.tr(state.errorTitleKey)}\n${l10n.tr(state.errorMessageKey)}',
   isError: true)` — переведённые заголовок и сообщение, вместо
   Lottie-анимации — два `BlackCircleButton` рядом: «Попробовать снова»
   (`l10n.try_again`) и «На главный экран» (`l10n.go_to_home`). Это
   единственный экран, который видит пользователь после отказа в обоих
   входах — вход (а) не возвращает на «В работе»: та же самая
   `DataUpdatePage`, пуш которой этот вход только что вызвал, теперь
   показывает ошибку прямо поверх неё; вход (б) просто оставляет
   пользователя там же, где он уже был.
6. `WillPopScope.onWillPop` = `state is! DataUpdateInProgress` — для
   `DataUpdateFailure` это `true`: системный жест «назад»/свайп закрывает
   `DataUpdatePage` без единого предупреждения и без явного действия
   пользователя — блок при этом не получает никакого события, последнее
   состояние (`DataUpdateFailure`) остаётся его текущим `state` и просто
   перестаёт кем-либо наблюдаться, пока не придёт следующий
   `DataUpdateStartAll`.
7. Если пользователь вместо этого нажимает явную кнопку:
   - **«Попробовать снова»** — это и есть вход (б): диспатчит
     `DataUpdateStartAll(showDataUpdatePage: false, again: true)`, весь
     поток повторяется с шага 1, `_isPageOpen` уже `true` → без нового push,
     та же страница анимированно (`AnimatedSwitcher`, 250 мс) переходит
     из отображения ошибки обратно в `DataUpdateInProgressWidget` (без
     `isError`), затем — в `DataUpdateSuccess`/новый `DataUpdateFailure`.
   - **«На главный экран»** — `Navigator.of(context).pop()` (закрывает
     `DataUpdatePage`, `_isPageOpen` сбрасывается в `false` по завершении
     `await` в `show()`), `context.go(Routes.mainNavigator)`, и **безусловно**
     `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(
     showModalMessage: true))` — проверка обновления приложения запускается
     независимо от того, что sync только что провалился; последнее
     состояние `DataUpdateBloc` (`DataUpdateFailure`) явно нигде не
     сбрасывается этой кнопкой.

### Альтернативные потоки

- **`isUpdateData` — единственное реальное отличие входа (а) от входа
  (б) в самой логике прохода.** Только при `isUpdateData: true` (то есть
  только через вход (а), и то только если проход доходит до этого шага без
  более раннего отказа) `_syncAllData` вызывает
  `_settingsRepository.setSettingToSHTP()`. Этот метод **не имеет
  собственного `try/catch`** — любое исключение (сетевое или нет) всплывает
  напрямую в общий `catch` шага 4 (ветка Б). Вход (б) никогда не
  устанавливает `isUpdateData: true`, поэтому ретрай уже показанного отказа
  никогда не повторяет попытку отправки настроек, даже если самый первый
  отказ (который сейчас ретраится) произошёл именно на этом шаге при входе
  (а). Соседний вызов той же строкой ниже, `getSettingFromSHTP()`,
  выполняется при обоих входах одинаково, но сам ловит `on DioException` и
  тихо подставляет настройки по умолчанию — не все исключения (например,
  ошибка `Settings.fromJson` на неожиданном ответе) относятся к
  `DioException`, такие всё ещё дошли бы до общего `catch`.
- **`again` не влияет на исход на практике.** `event.again` читается только
  внутри `updateAndSyncRegagro`, уже после того, как сеть проверена повторно
  и мы миновали ветку А; по документированной в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) находке
  (`dataUpdates.length < DataCategory.values.length` истинно почти всегда)
  ветка «полный `_syncAllData()`» выбирается независимо от `again` в обоих
  входах — различие флага между входами (а: `false` по умолчанию, б:
  `true`) не меняет наблюдаемое поведение.
- **`showDataUpdatePage` — мёртвое поле события в обоих входах.** Оно нигде
  не читается ни в `DataUpdateBloc`, ни в `MainPage`'s `BlocListener`
  (`if (state is DataUpdateInProgress) DataUpdatePage.show(context)` не
  смотрит на событие вовсе) — то, что вход (б) не порождает второй push,
  обеспечивает исключительно статический `_isPageOpen` на самой
  `DataUpdatePage`, а не значение `showDataUpdatePage: false`, которое вход
  (б) передаёт.
- **Успешный ретрай — вне рамок этого документа.** Если после входа (б)
  проход в итоге доходит до `DataUpdateSuccess`, `DataUpdatePage`'s listener
  сам делает `Navigator.of(context).pop()` и переходы, описанные для
  успешного прохода — сюда не относится, `RESULT` этого документа —
  `CREATE_ERROR`.

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  сущность из id этого документа; реально получает новую строку **только**
  в ветке Б (исключение внутри `try`), не в ветке А (сеть недоступна) — см.
  шаг 4.
- `Settings`/`ProfileSetting` (PROFILE, не редактируется этим модулем) —
  читается/пишется через `SettingsRepository.setSettingToSHTP`/
  `.getSettingFromSHTP`, доступный только со входа (а) при `isUpdateData:
  true`; сам отказ этого шага (если он происходит) — один из возможных
  источников ветки Б, специфичный именно входу (а).
- [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion) —
  не читается самим отказом sync-прохода, но кнопка «На главный экран»
  безусловно инициирует `AppUpdateEventCheckUpdate` сразу после отказа —
  проверка обновления не зависит от исхода только что провалившегося
  прохода.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) —
  косвенно: если ветка Б наступает на шаге `loadAnimals` (уже после
  `_clearDataUpdates()`/`loadUser`/etc. внутри `_syncAllData`), локальная
  таблица `Animals` в этот момент уже могла быть очищена
  (`_animalsRepository.clear()` вызывается в начале `loadAnimals`, до
  `syncAllAnimals()`) — этот документ не разбирает эту развилку заново
  (она — часть общей механики, разобранной [UC-188](UC-188-ACTOR-3-EVT-93-ENT-23-CREATE_ERROR-IN-SYSTEM.md)),
  но она в равной мере применима к обоим ручным входам, так как исполняется
  тем же кодом `_syncAllData`.

### Бизнес-правила

- `RESULT = CREATE_ERROR` покрывает обе под-ветки (А и Б), но фактическая
  запись в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) создаётся
  только в ветке Б — в ветке А `CREATE` в буквальном смысле не происходит,
  пользователь тем не менее получает тот же класс экрана-отказа
  (`DataUpdateFailure`) на `DataUpdatePage`.
- Оба ручных входа сходятся в одном и том же экране ошибки — нет отдельного
  визуального различия между «отказал проход, запущенный явной кнопкой
  синхронизации» и «отказал повторный ретрай»; единственное, что отличает
  их для пользователя, — путь, которым он туда попал (push поверх «В
  работе» для входа (а); никакого перехода для входа (б)).
- `isUpdateData: true` (и, значит, попытка `setSettingToSHTP()`) —
  единственная во всей кодовой базе привязка отправки настроек пользователя
  к явному ручному запуску, а не к автоматическому ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)),
  и одновременно единственная к **конкретно входу (а)** — вход (б)
  (ретрай) эту попытку не повторяет, даже ретраируя тот же самый исходный
  отказ.
- Ни один из двух входов не ограничивает число ретраев и не показывает
  пользователю признак «уже пытались N раз» — единственная встроенная
  задержка (`Future.delayed(seconds: 15)` внутри `updateAndSyncRegagro`,
  см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) наступает
  только если предыдущий проход успел записать в `DataUpdates` ошибочную
  строку (то есть только после ветки Б, не после ветки А) и только если
  текущая попытка проходит сетевой гейт шага 4.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба входа и обе ветки отказа (сеть
недоступна до `try`; исключение внутри `try`) полностью воспроизводятся
статическим чтением `lib/blocs/data_update/data_update_bloc.dart`,
`lib/pages/in_work/in_work_page.dart`, `lib/pages/data_update/data_update_page.dart`,
`lib/pages/main/main_page.dart`, `lib/main.dart` и
`lib/repositories/settings/settings_repository.dart`. Возможное исправление
(например, сброс `_currentDataCategory`/`_currentDataKey` в начале каждого
прохода, реальное чтение `showDataUpdatePage`, запись строки в `DataUpdates`
и для ветки А) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | единственный обработчик обоих ручных входов; сетевой гейт до `try` (ветка А); единственный внешний `catch` (ветка Б) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitError`, `._addDataUpdateError` | CURRENT | создают строку [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) и эмитят `DataUpdateFailure` — только для ветки Б |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | читает `event.again`; выбор ветки на практике не зависит от него (см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | `isUpdateData`-ветка вызывает `_settingsRepository.setSettingToSHTP()` — доступно только со входа (а) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._resetProgressCounters` | CURRENT | тело пусто — `_currentDataCategory`/`_currentDataKey` не сбрасываются между проходами |
| `lib/blocs/data_update/data_update_event.dart` | `DataUpdateStartAll` (`isUpdateData`, `again`, `showDataUpdatePage`) | CURRENT | флаги, которыми отличаются оба входа; `showDataUpdatePage` нигде не читается |
| `lib/blocs/data_update/data_update_state.dart` | `DataUpdateInProgress`, `DataUpdateFailure` | CURRENT | состояния, наблюдаемые пользователем в обоих входах |
| `lib/pages/in_work/in_work_page.dart` | кнопка «Синхронизировать данные» | CURRENT | вход (а) [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md) — `DataUpdateStartAll(isUpdateData: true)` |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdatePage.show`, `._isPageOpen`, `_Body`, `DataUpdateInProgressWidget` | CURRENT | вход (б) (кнопки «Попробовать снова»/«На главный экран»); отображение `DataUpdateFailure`; статический guard, реально предотвращающий повторный push |
| `lib/pages/main/main_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | пушит `DataUpdatePage` только при `DataUpdateInProgress`, не читая `showDataUpdatePage` |
| `lib/main.dart` | `MyApp.build` → `BlocProvider<DataUpdateBloc>` | CURRENT | один инстанс блока на весь сеанс приложения — источник «залипания» полей-счётчиков между проходами и входами |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.setSettingToSHTP`, `.getSettingFromSHTP` | CURRENT | первая без собственного `try/catch` (доступна только входу (а)); вторая ловит только `DioException` |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | сетевой гейт, вызывается дважды: до `try` и внутри `updateAndSyncRegagro` |
| `lib/blocs/app_update/app_update_event.dart` | `AppUpdateEventCheckUpdate` | CURRENT | диспатчится кнопкой «На главный экран» безусловно, независимо от исхода синка |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates`, `DataCategory`, `DataKey` | CURRENT | таблица/категории/ключи [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |

## Критерии приёмки

- Вход (а) («Синхронизировать данные» на «В работе») диспатчит
  `DataUpdateStartAll(isUpdateData: true)`, реально пушит новый экземпляр
  `DataUpdatePage` (`_isPageOpen` было `false`).
- Вход (б) («Попробовать снова» на самой `DataUpdatePage`) диспатчит
  `DataUpdateStartAll(showDataUpdatePage: false, again: true)`, не пушит
  новый экземпляр страницы (`_isPageOpen` уже `true`) — тот же виджет
  анимированно переключает содержимое.
- Если `NetworkConnectivityService.hasConnection()` в начале
  `on<DataUpdateStartAll>` возвращает `false`, для обоих входов немедленно
  эмитится `DataUpdateFailure(errorTitleKey: 'internet_connection_required',
  errorMessageKey: 'check_connection')` без единой новой строки в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).
- Если сеть есть, но какой-либо шаг внутри `try` бросает исключение, для
  обоих входов создаётся строка [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
  (`_addDataUpdateError`) и эмитится `DataUpdateFailure(errorTitleKey:
  'an_error_data', errorMessageKey: _currentDataKey, errorMessage: ...)`.
- `_settingsRepository.setSettingToSHTP()` вызывается (и может стать
  источником исключения ветки Б) только когда `isUpdateData == true` — то
  есть только на входе (а), никогда на входе (б), даже если ретраится отказ,
  изначально пришедший со входа (а).
- После `DataUpdateFailure` в обоих входах `DataUpdatePage` показывает
  переведённые `errorTitleKey`/`errorMessageKey` и две кнопки — «Попробовать
  снова» (диспатчит вход (б)) и «На главный экран» (`Navigator.pop`,
  `context.go(Routes.mainNavigator)`, безусловный
  `AppUpdateEventCheckUpdate(showModalMessage: true)`); системный жест
  «назад» дополнительно закрывает страницу без диалога подтверждения
  (`WillPopScope.onWillPop` истинен для `DataUpdateFailure`).

## Связанные тесты

TBD — теста нет. Единственный существующий тест файла —
`blocTest('DataUpdateClear очищает пользовательские данные БД', ...)`
(верхнеуровневый `blocTest`, не внутри `group()`) — покрывает только событие
`DataUpdateClear`, не `DataUpdateStartAll` ни в каком виде. Файл
`test/blocs/data_update_bloc_test.dart` содержит развёрнутый
комментарий-дисклеймер прямо перед `main()`, объясняющий, почему
`DataUpdateStartAll` не покрыт тестом вовсе:

> DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры getIt<X>()
> (не через конструктор) — конструктору бЛока нужны ВСЕ они зарегистрированы,
> даже для теста одного простого события. DataUpdateStartAll (~900 из 1013
> строк файла — основной sync pipeline) НЕ покрыт юнит-тестом: первая же
> строка обработчика — `await hasNetworkConnection()` (реальный DNS-запрос
> без DI-точки), дальше десятки приватных методов и реальные транзакции
> AppDatabase. Осмысленный юнит-тест такого масштаба потребовал бы
> рефакторинга источника под DI — вне рамок написания тестов без изменения
> кода. См. TESTING_CHECKLIST.md.

Ни один из двух конкретных входов этого документа (кнопка на `InWorkPage`,
кнопка на `DataUpdatePage`) и ни одна из двух веток отказа (сеть недоступна,
исключение внутри `try`) тестами не проверяются — ни на уровне
`DataUpdateBloc`, ни на уровне виджетов `InWorkPage`/`DataUpdatePage`
(`grep -rn "InWorkPage\|DataUpdatePage" test/` не находит тестового файла ни
для одного из двух виджетов).

## Открытые вопросы и ограничения

- **`_currentDataCategory`/`_currentDataKey` не сбрасываются между
  проходами.** `_resetProgressCounters()` — пустое тело, а сами поля живут
  на единственном, разделяемом на весь сеанс приложения инстансе
  `DataUpdateBloc` (`lib/main.dart`). Если исключение ветки Б происходит на
  самом раннем шаге нового прохода — до первого `_emitProgress` внутри
  `loadDirectories` (первая строка которого — `_countriesRepository.syncCountries(...)`,
  вызываемая до какого-либо `_emitProgress` в этом методе) — записанная в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) строка получит
  `dataCategoryId`/`errorDataKey`, оставшиеся от **предыдущего** прохода
  (или от значений по умолчанию `DataCategory.directories`/`''`, если это
  вообще первый прогон), а не описывающие реально упавший шаг. Наиболее
  вероятный практический случай, когда это проявляется, — именно ретрай
  входом (б) сразу после отказа входом (а) (или наоборот) в рамках одной
  сессии — не проверено эмпирически.
- **`getSettingFromSHTP()` ловит только `DioException`**, не любое
  исключение — `_setVisibleKinds`/`_setProfileSettingsFromApi`/`Settings.fromJson`
  на неожиданном ответе теоретически способны бросить исключение, не
  являющееся `DioException`, которое тогда дошло бы до общего `catch` шага
  4 (ветка Б) при обоих входах — не проверено, какая форма ответа сервера
  могла бы это вызвать на практике.
- **`showDataUpdatePage` — мёртвое поле события**, не читаемое нигде в
  `DataUpdateBloc`/`MainPage`; фактический guard от повторного push —
  исключительно статический `_isPageOpen` на `DataUpdatePage`. Было ли поле
  задумано как этот самый guard и осталось невостребованным, или это
  vestige другого, уже удалённого механизма — ничем в коде/комментариях не
  зафиксировано.
- **`DataUpdateFailure.isAdressesUpdate` — тоже мёртвое поле в этом
  сценарии**: единственный вызов `_emitError` не передаёт `isAdressUpdate:
  true` ни разу во всём `lib/`, а `_Body`'s ветка `DataUpdateFailure` это
  поле и не читает — нет наблюдаемого эффекта для пользователя ни при
  каком значении.
- **Сообщения `DataUpdateInProgress` не переводятся**, в отличие от
  `DataUpdateFailure`: `_Body` передаёt `state.messageKey` в
  `DataUpdateInProgressWidget` как есть (например литеральную строку
  `'reloading_data_update'` из `updateAndSyncRegagro`, либо
  `DataKey.syncSettings` → `'syncSettings'`), без вызова `l10n.tr()`, тогда
  как для `DataUpdateFailure` тот же `_Body` явно переводит оба ключа. Это
  видно пользователю в обоих ручных входах во время короткого окна
  «прогресс» перед новым успехом/отказом — тангенциально теме этого
  документа (`CREATE_ERROR`), но часть буквально наблюдаемого экрана между
  нажатием ретрая и следующим состоянием.
- Не проверено эмпирически на реальном устройстве/эмуляторе — весь вывод
  сделан статическим чтением перечисленных в «Технические зависимости»
  файлов.
