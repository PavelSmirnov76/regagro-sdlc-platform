# UC-187 — Автоматический полный sync-проход при холодном старте завершается успехом — но журнал прохода `DataUpdates` при этом либо бесконечно копится (гость), либо стирает сам себя в конце того же прохода, что его написал (авторизованный)

| | |
|---|---|
| Актор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Событие | [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же автоматический полный sync-проход, что описан в
[EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) —
запускается один раз при каждом холодном старте приложения, сразу после
проверки сессии, одинаково для гостя и авторизованного пользователя. Здесь
описан путь, где ни один шаг прохода не бросает исключение — проход доходит
до `DataUpdateSuccess`. Фокус документа — что именно в этом успешном пути
физически попадает (и не попадает) в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
(`DataUpdates`), потому что успешный проход для гостя и для авторизованного
пользователя оставляет таблицу в **принципиально разных** состояниях, хотя
триггер и весь верхнеуровневый код (`DataUpdateBloc.on<DataUpdateStartAll>`)
один и тот же:

- **у гостя** (`_authRepository.isAuthorized() == false`) — `_syncAuthData()`
  целиком пропускается, а вместе с ним и `_clearDataUpdates()` (единственное
  место в коде, которое очищает эту таблицу, см.
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)). Единственная строка
  успеха, которую пишет `loadDirectories()` (под ошибочной категорией
  `generationsTypes`, а не `directories` — сам этот факт уже задокументирован
  в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)), никогда не
  стирается — она **накапливается заново при каждом успешном проходе**, ручном
  или автоматическом, без ограничения по времени жизни установки;
- **у авторизованного** — `_syncAuthData()` в этом же самом проходе доходит до
  `updateAndSyncRegagro` → `_syncAllData`, первая строка которого —
  `await _clearDataUpdates()` — стирает **всю** таблицу целиком, включая
  строку, которую `loadDirectories()` только что написал несколькими шагами
  раньше **в этом же самом проходе**. Итог: для авторизованного пользователя
  таблица `DataUpdates` не просто «никогда не видит корректной категории
  `directories`» (это уже знает [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) —
  она вообще никогда не видит **никакой** строки о справочниках после
  завершения полного прохода, даже мислейбл `generationsTypes`: строка
  создаётся и в тот же проход уничтожается, до того как пользователь успевает
  увидеть `DataUpdateSuccess`.

Обе половины проверены отдельно прямым чтением `DataUpdateBloc` — точный
порядок вызовов см. «CURRENT» ниже.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение, действующее
автоматически при холодном старте, без явного жеста человека в момент самого
триггера. Какой класс актора (гость — [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) —
или авторизованный пользователь — [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md))
уже сидит на устройстве, определяется раньше и вне этого сценария —
`AuthBloc.on<AuthEventStart>` (специфицировано `ACTOR-3`/[EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md));
это событие лишь читает результат того решения через
`_authRepository.isAuthorized()`, не участвует в его принятии. Ни
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), ни
[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) не нажимают ничего, чтобы этот
проход начался — это отличает `EVT-93` от ручного запуска того же прохода
([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
инициатор — [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)).

## CURRENT

### Основной поток

1. `AuthBloc.on<AuthEventStart>` (`lib/pages/profile/bloc/auth_bloc.dart`)
   определяет сессию и эмитит `AuthToMain(user)` для авторизованного
   (`_authRepository.isAuthorized() == true`) или `AuthToMain(null)` для
   гостя — в обоих случаях без дальнейшего участия человека.
2. `MainPage`'s `BlocListener<AuthBloc, AuthState>`
   (`lib/pages/main/main_page.dart`) реагирует на `AuthToMain` любым
   содержимым одинаково: `context.read<DataUpdateBloc>().add(DataUpdateStartAll(
   again: await getIt<NetworkConnectivityService>().hasConnection(),
   showDataUpdatePage: true))`. Ни `resetNavigationOnSuccess`, ни
   `isUpdateData`, ни `fullUpdate` не передаются — остаются на дефолтных
   `false` (`lib/blocs/data_update/data_update_event.dart`,
   `DataUpdateStartAll`/`DataUpdateEvent`).
3. `DataUpdateBloc.on<DataUpdateStartAll>` (`lib/blocs/data_update/data_update_bloc.dart`):
   `_resetProgressCounters()` — пустая заглушка (`void _resetProgressCounters() {}`,
   ничего не делает), затем `emit(DataUpdateInProgress(progressPercent: 0))` —
   безусловно, до какой-либо проверки сети.
4. `MainPage`'s второй, соседний `BlocListener<DataUpdateBloc, DataUpdateState>`
   реагирует на этот `DataUpdateInProgress`, вызывая `DataUpdatePage.show(context)`
   (`lib/pages/data_update/data_update_page.dart`) — полноэкранный
   `Navigator.push` с root-навигатором, охраняемый статическим флагом
   `_isPageOpen`, чтобы не открыть страницу дважды. Именно это, а не значение
   `event.showDataUpdatePage` (см. «Открытые вопросы»), решает, откроется ли
   страница прогресса.
5. `final isNetworkConnected = await getIt<NetworkConnectivityService>().hasConnection();` —
   второй, независимый от шага 2, реальный DNS-запрос
   (`InternetAddress.lookup('google.com')`, `lib/services/network_connectivity_service.dart`).
   В этом сценарии — `true` (иначе — `DataUpdateFailure` сразу, до входа в
   `try`, сценарий не наступает).
6. `final directoriesSyncBaseline = AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale);` —
   читается **до** запуска `loadDirectories()`; тот же снимок передаётся на шаг
   8 (см. [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md)).
7. `await loadDirectories(event, emit)` —
   [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md), полностью
   специфицировано там. В конце метода — единственная запись успеха в
   `DataUpdates` в этом методе: `await _addDataUpdateSuccess(_currentDataCategory)`,
   где `_currentDataCategory` к этому моменту равно `DataCategory.generationsTypes`
   (последнее явное присвоение внутри метода — см.
   [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)), не
   `DataCategory.directories`. Это единственная строка, добавленная в таблицу
   с начала прохода.
8. `await _loadBoardDirectories(event, emit, updatedAtGt: directoriesSyncBaseline)` —
   [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md); не пишет
   ни одной строки в `DataUpdates`.
9. `if (_authRepository.isAuthorized()) await _syncAuthData(event, emit);` —
   единственное ветвление по классу актора во всём успешном потоке. Для гостя
   (`isAuthorized() == false`) весь метод целиком пропускается — обработчик
   пропускает шаги 10–14 (все они помечены «только авторизованный») и сразу
   переходит к шагу 15, а таблица `DataUpdates` в этот момент содержит ровно
   одну строку — ту, что была написана на шаге 7.
10. **(только авторизованный)** `_syncAuthData`: `_deletePlacesFromRDS()`,
    `_syncFarms()`, `_syncPlaces()`,
    `_animalWeighingsRepository.storeAnimalWeighingsToSHTP()` — уже
    специфицировано в `FARM`/`ANIMAL` (`ACTOR-4`), ни одна из этих операций не
    пишет в `DataUpdates`.
11. **(только авторизованный)** `await updateAndSyncRegagro(event, emit)`:
    `final dataUpdates = await _dataUpdatesRepository.getAll();` — таблица на
    этот момент содержит как минимум одну строку — ту, что добавлена шагом 7
    (`generationsTypes`), — плюс любые строки, пережившие с предыдущего
    прохода (для авторизованного пользователя это, как правило, `user` /
    `animals` / `reports` с прошлого раза — см. пункт 13 ниже). `errorDataUpdates`
    пусто (сценарий без ошибок). `dataUpdates.length < _totalDataUpdatesCount`
    (9) истинно всегда (см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) →
    условие первой ветки истинно **безусловно**, независимо от значения
    `event.again`, вычисленного на шаге 2, — `await _syncAllData(event, emit)`
    вызывается всегда.
12. **(только авторизованный)** `_syncAllData` — **первая строка метода**:
    `await _clearDataUpdates()` → `DataUpdatesRepository.clear()` →
    `BaseDao.clear()` → `delete(_currentTableInfo).go()`
    (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — полностью
    удаляет **все** строки таблицы `DataUpdates`, включая строку, написанную
    шагом 7 **в этом же самом проходе**, за несколько шагов до этого момента.
    С этой строки и до конца прохода в таблице нет ни одной записи о
    справочниках — ни под верной категорией, ни под ошибочной.
13. **(только авторизованный)** далее внутри `_syncAllData`, по порядку:
    `loadUser(event, emit)` пишет строку `DataCategory.user`
    (`_authRepository.updateUserData()` — [ENT-1](../entities/ENT-1-USER-IN-AUTH.md));
    `_emitProgress(dataCategory: DataCategory.syncUnsentAnimals)` +
    `syncAllUnsentAnimals()` — категория выставляется, но `_addDataUpdateSuccess`
    под ней не вызывается ни разу — строка не пишется; `_emitProgress(dataKey:
    DataKey.syncSettings)` (без `dataCategory`); если `event.isUpdateData`
    (здесь всегда `false` для этого автозапуска, см.
    [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)) —
    `_settingsRepository.setSettingToSHTP()` пропускается;
    `_settingsRepository.getSettingFromSHTP()`,
    `_movementReportRepository.syncMovements()`,
    `_disposalRepository.syncDisposals()`, `_syncEditedAnimals()` — уже
    специфицировано в `ANIMAL`, не пишут в `DataUpdates`; `loadAnimals(event,
    emit)` пишет строку `DataCategory.animals`
    (`_animalsRepository.syncAllAnimals()` — [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md));
    `_vaccinationsRepository.syncVaccinations(true)` — не пишет.
14. **(только авторизованный)** возврат в `_syncAuthData`: `await
    updateAndSyncSHTP(event, emit)` → `_emitProgress(dataCategory:
    DataCategory.syncReports)` (категория выставляется, строка не пишется) →
    отправка/очистка неотправленных отчётов
    (`_unsentReportsRepository`/`_reportsRepository`) → `loadShtp(emit)`
    пишет строку `DataCategory.reports`
    (`_reportsRepository.getReportsFromApi()`/`insertAll`). Затем
    `_emitProgress(dataKey: DataKey.syncDevices)` (без категории) и
    `_suncDevices()` — настройки сканера/устройства
    ([ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md), `PROFILE`) — не пишут
    в `DataUpdates`.

    **Итог для авторизованного пользователя:** к концу прохода таблица
    `DataUpdates` содержит ровно три новые строки — `user`, `animals`,
    `reports` — в указанном порядке добавления. Строка о справочниках,
    написанная шагом 7 этого же прохода, в таблице отсутствует — она была
    удалена шагом 12 раньше, чем проход завершился.

    **Итог для гостя:** к концу прохода (шаг 9 пропускает всё
    авторизованное ветвление целиком) таблица `DataUpdates` содержит ровно
    одну строку сверх того, что было до этого прохода, — ту, что написал шаг
    7 (`generationsTypes`, не `directories`). Поскольку `_clearDataUpdates()`
    не вызывается никогда, если пользователь ни разу не входил в аккаунт на
    этом устройстве, каждый следующий успешный проход (автоматический —
    `EVT-93`, или ручной — [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md))
    добавляет **ещё одну** такую строку — `_dataUpdatesRepository.insert`
    (`BaseRepository.insert` → `BaseDao.ins` →
    `intoCurrent().insert(item, mode: InsertMode.insertOrReplace)`) без
    указания `id` (автоинкрементный столбец, не задан в
    `DataUpdatesCompanion`), поэтому `insertOrReplace` никогда не находит
    конфликт по первичному ключу и ведёт себя как обычный `insert` — новая
    строка при каждом вызове, не upsert по категории. Строки для чисто
    гостевой установки накапливаются без ограничения по времени жизни
    приложения (см. «Открытые вопросы»).
15. `emit(DataUpdateSuccess(resetNavigationOnSuccess: event.resetNavigationOnSuccess))` —
    `resetNavigationOnSuccess` здесь всегда `false` (шаг 2), для обеих ветвей
    актора.
16. `finally`: `await getIt<ApiClient>(instanceName: 'farm_rpc').resetClient('farm_rpc');
    await getIt<ApiClient>(instanceName: 'r3_rpc').resetClient('r3_rpc');` —
    выполняется безусловно, успех или ошибка. Каждый `resetClient`
    (`lib/network/api_client/custom_dio_client.dart`) —
    `getIt.unregister<ApiClient>(instanceName: ...)` +
    `registerLazySingleton(() => CustomDioClient(getIt<DioClient>()), instanceName: ...)` —
    свежая обёртка вокруг того же самого singleton `DioClient`; собственного
    изменяемого состояния (помимо ссылки на `dio`) у `CustomDioClient` нет —
    наблюдаемого эффекта на этот сценарий это не имеет.
17. `DataUpdatePage`'s `BlocConsumer<DataUpdateBloc, DataUpdateState>.listener`
    (`lib/pages/data_update/data_update_page.dart`) реагирует на
    `DataUpdateSuccess`: если `!(pref.getBool('have_any_language') ?? false)` —
    ставит `true` и диспатчит `context.read<LanguageBloc>().add(LanguageEventChange(
    LanguageService.locale))` — происходит только один раз за установку (или
    до следующего `DataUpdateClear`, который сбрасывает флаг обратно в
    `false` — сам сброс не входит в этот сценарий). Затем
    `Navigator.of(context).pop()` закрывает страницу прогресса;
    `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage:
    true))` — это и есть фактический триггер
    [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md), а не сама
    `DataUpdateSuccess` из `DataUpdateBloc`: если бы `DataUpdatePage` почему-то
    не была открыта или не смонтирована в момент эмиссии, этот диспатч не
    произошёл бы вовсе — специфицируется отдельным use-case
    ([EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)), здесь
    зафиксирован только сам факт того, откуда он берётся. Наконец, так как
    `state.resetNavigationOnSuccess == false` (шаг 15) — `context.go(Routes.mainNavigator)`.

### Альтернативные потоки

- **Триггер шага 2 разряжает: `event.again`, вычисленный `MainPage`, не влияет
  ни на что в этом сценарии.** Единственное место, где `event.again`
  читается — условие `updateAndSyncRegagro` на шаге 11, — но это условие
  истинно всегда независимо от `event.again` (см.
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)). Значение,
  вычисленное `await getIt<NetworkConnectivityService>().hasConnection()`
  специально для этого события на шаге 2, структурно не может повлиять на
  дальнейшее поведение этого же прохода.
- **Три отдельных, независимых сетевых DNS-запроса за один проход.**
  `NetworkConnectivityService.hasConnection()` вызывается трижды в рамках
  одного успешного прохода: шаг 2 (`MainPage`, до диспатча), шаг 5
  (`on<DataUpdateStartAll>`, верхнеуровневый гейт), и ещё раз внутри
  `updateAndSyncRegagro` (шаг 11, тот же метод `hasConnection()`, локальная
  переменная с тем же именем) — ни один результат не переиспользуется между
  вызовами.
- **`_syncAllData` вызывает `loadAnimals` (полная перезагрузка), никогда —
  `updateAnimals` (инкрементальная).** `DataUpdateBloc.updateAnimals`
  (использующий `_lastUpdateDate`, вычисленный из категории `animals` в
  `updateAndSyncRegagro`) существует в коде, но не вызывается нигде в
  `lib/` — `grep -rn "\.updateAnimals(" lib/` не находит вызывающего кода
  вовсе, только определение метода. Это независимое подтверждение того же
  структурного дефекта, что уже задокументирован в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md): развилка
  «докат/полный проход» никогда не выбирает докат.
- **Если это не первый успешный проход авторизованного пользователя на этом
  устройстве**, к моменту шага 11 таблица `DataUpdates` уже содержит строки
  `user`/`animals`/`reports`, оставшиеся от предыдущего прохода (шаг 12
  предыдущего прохода их не тронул — они были написаны **после** этого шага в
  прошлый раз). `dataUpdates.length` на шаге 11 в этом случае — 4 (1 новая
  `generationsTypes` + 3 старых), но итог тот же: условие всё равно истинно,
  `_clearDataUpdates()` стирает все 4 разом.
- **Переход гостя в авторизованный режим (логин) не стирает уже накопленные
  гостевые строки сам по себе** — стирание происходит только при следующем
  успешном авторизованном проходе (шаг 12), не в момент самого входа.
  Логаут (`DataUpdateClear`, `@Clearable()` на таблице) стирает всё
  безусловно — это отдельный, не покрываемый этим документом сценарий.

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) — предмет
  этого документа; итоговое состояние таблицы после успешного прохода прямо
  противоположно для гостя (строка копится) и для авторизованного (строка
  того же прохода стирается тем же проходом).
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind, breeds,
  suits и т.д., `HANDBOOKS`) — читается/перезаписывается шагом 7
  (`loadDirectories`, специфицировано [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md));
  не редактируется этим модулем напрямую.
- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, справочники `BOARD`) —
  синхронизируется шагом 8 (специфицировано
  [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md)).
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm),
  [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — синхронизируются
  шагом 10, только для авторизованного (специфицировано `FARM`/`ACTOR-4`).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal),
  [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement),
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination),
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing),
  [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) —
  синхронизируются внутри шагов 10/13, только для авторизованного
  (специфицировано `ANIMAL`/`ACTOR-4`); `Animal` также единственная категория
  (`DataCategory.animals`), помимо `user`/`reports`, реально фиксируемая в
  `DataUpdates` этим проходом (шаг 13).
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — обновляется шагом 13
  (`loadUser` → `_authRepository.updateUserData()`), только для
  авторизованного; единственная другая категория, реально фиксируемая в
  `DataUpdates` (`DataCategory.user`).
- [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device, `PROFILE`) —
  синхронизируется шагом 14 (`_suncDevices`), только для авторизованного; не
  пишет в `DataUpdates`.
- [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion) —
  читается сразу после этого сценария, шагом 17
  (`AppUpdateEventCheckUpdate`, [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)),
  не изменяется самим этим сценарием.

### Бизнес-правила

- Успешный полный sync-проход не гарантирует, что в
  [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) появится запись обо
  всех девяти категориях `DataCategory` — реально фиксируются максимум три
  (`user`, `animals`, `reports`) для авторизованного и максимум одна
  (мислейбл `generationsTypes` вместо `directories`) для гостя; остальные
  шесть категорий (`directories` в чистом виде, `syncReports`,
  `syncUnsentAnimals`, `syncDisposalListService`, `generations`,
  и для авторизованного — сама `generationsTypes`) никогда не фиксируются как
  успешные строки ни при каком исходе прохода.
- Порядок вызовов внутри одного и того же прохода (`loadDirectories()` пишет
  строку → далее по цепочке `_clearDataUpdates()` стирает всю таблицу) не
  документирован нигде как продуктовое намерение — это следствие того, что
  очистка живёт внутри `_syncAllData`, а не в начале `on<DataUpdateStartAll>`
  целиком, притом что `loadDirectories()`/`_loadBoardDirectories()` всегда
  выполняются раньше проверки авторизации.
- Гостевой и авторизованный режимы делят одну и ту же локальную таблицу
  `DataUpdates` на одном устройстве (как и `Countries`, см.
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)) — но здесь,
  в отличие от `Countries`, характер порчи разный по направлению: гость
  копит мусорные строки, авторизованный периодически стирает их дочиста.
- `DataUpdatePage` — а не сам `DataUpdateBloc` — единственное место,
  инициирующее проверку обновления приложения
  ([EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)) после
  успешного прохода; это архитектурно означает, что проверка обновления
  зависит от UI-слоя, а не от бизнес-состояния `DataUpdateBloc` напрямую.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Обе половины (накопление строк у гостя,
самостирание строки у авторизованного) полностью воспроизводятся статическим
чтением кода: `DataUpdateBloc.on<DataUpdateStartAll>` →
`loadDirectories`/`_addDataUpdateSuccess` → `_syncAuthData` →
`updateAndSyncRegagro` → `_syncAllData` → `_clearDataUpdates`/`loadUser`/
`loadAnimals` → `updateAndSyncSHTP` → `loadShtp`. Исправление (например,
перенос `_clearDataUpdates()` в начало `on<DataUpdateStartAll>` целиком, или
использование `insertOrUpdate` по категории вместо накопительного `insert`)
в рамках этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main/main_page.dart` | `BlocListener<AuthBloc, AuthState>` | CURRENT | диспатчит `DataUpdateStartAll` на `AuthToMain`, для гостя и авторизованного одинаково |
| `lib/pages/main/main_page.dart` | `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | вызывает `DataUpdatePage.show(context)` на `DataUpdateInProgress`, независимо от `event.showDataUpdatePage` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | CURRENT | определяет актора (гость/авторизованный), эмитит `AuthToMain` в обоих случаях |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | верхнеуровневая оркестрация; сетевой гейт; `try/finally` с `resetClient` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories` | CURRENT | пишет единственную строку успеха под фактической категорией `generationsTypes` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadBoardDirectories` | CURRENT | не пишет в `DataUpdates` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | ветвление `if (_authRepository.isAuthorized())`; вызывается только для авторизованного |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | условие «докат/полный проход», всегда истинно в первой ветке (см. `ENT-23`) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | первая строка — `_clearDataUpdates()`, стирает строку `loadDirectories` того же прохода |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadUser`, `.loadAnimals`, `.loadShtp` | CURRENT | единственные три вызова, реально фиксирующие успех в `DataUpdates` этого прохода (`user`/`animals`/`reports`) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAnimals` | CURRENT, мёртв | не вызывается нигде в `lib/` — независимое подтверждение недостижимости инкрементальной ветки |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._addDataUpdateSuccess`, `._clearDataUpdates` | CURRENT | точка записи (`insert`, не upsert) и точка полной очистки таблицы |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository` | CURRENT | тонкая обёртка `getAll`/`insert`/`clear` над `BaseRepository` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins`, `.clear` | CURRENT | `ins` — `insertOrReplace` без указания `id` → всегда новая строка, не upsert по категории; `clear` — `delete(...).go()`, полная очистка таблицы |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates`, `DataCategory` | CURRENT | таблица, автоинкрементный `id`, 9 категорий |
| `lib/pages/data_update/data_update_page.dart` | `DataUpdatePage`, `_DataUpdatePageState.build` (`BlocConsumer.listener`) | CURRENT | фактическая точка триггера `AppUpdateEventCheckUpdate`; сброс языка один раз через `pref.getBool('have_any_language')`; навигация на `Routes.mainNavigator` |
| `lib/blocs/app_update/app_update_bloc.dart` | `AppUpdateBloc.on<AppUpdateEventCheckUpdate>` | CURRENT | получатель диспатча из `DataUpdatePage`; специфицируется отдельным use-case ([EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md)) |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | вызывается трижды независимо в рамках одного прохода |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.resetClient` | CURRENT | пересоздаёт `ApiClient`-обёртку в `getIt` для `farm_rpc`/`r3_rpc`, безусловно, в `finally` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized`, `.updateUserData` | CURRENT | единственное ветвление актора; обновление `User` внутри `loadUser` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate` | CURRENT | снимок, читаемый до `loadDirectories`, используемый также в `_loadBoardDirectories` |

## Критерии приёмки

- Полный автоматический sync-проход (`DataUpdateStartAll` из `MainPage`'s
  `BlocListener<AuthBloc>`), в котором ни один сетевой вызов не отказывает,
  завершается `emit(DataUpdateSuccess(resetNavigationOnSuccess: false))` для
  гостя и для авторизованного пользователя одинаково.
- Для **авторизованного** пользователя после завершения прохода таблица
  `DataUpdates` содержит ровно три новые строки без ошибки —
  `DataCategory.user`, `DataCategory.animals`, `DataCategory.reports` — и
  **не содержит** строки со значением, добавленным `loadDirectories()` этого
  же прохода (она удалена `_clearDataUpdates()` внутри `_syncAllData`,
  вызванного позже в том же проходе).
- Для **гостя** после завершения прохода таблица `DataUpdates` содержит на
  одну строку больше, чем до прохода — с `dataCategoryId ==
  DataCategory.generationsTypes` (не `DataCategory.directories`) и `errorDataKey ==
  null`/`errorMessage == null`; при повторных успешных проходах на том же
  устройстве без входа в аккаунт число таких строк растёт без ограничения
  (`_clearDataUpdates()` не достигается ни разу).
- `DataUpdateBloc._resetProgressCounters()`/`._getProgressPercent()` не
  влияют на успешность прохода — оба фактически no-op (`{}`/`=> 0`).
- `getIt<ApiClient>(instanceName: 'farm_rpc')` и
  `getIt<ApiClient>(instanceName: 'r3_rpc')` после завершения прохода — новые
  экземпляры `CustomDioClient`, зарегистрированные `resetClient` в `finally`,
  вне зависимости от исхода прохода.
- `AppUpdateEventCheckUpdate(showModalMessage: true)` диспатчится ровно один
  раз на успешный проход — из `DataUpdatePage`'s `BlocConsumer.listener` на
  `DataUpdateSuccess`, не из самого `DataUpdateBloc`.
- `pref.getBool('have_any_language')` переключается в `true` и
  `LanguageEventChange(LanguageService.locale)` диспатчится не более одного
  раза за успешный проход, и вовсе не диспатчится, если флаг уже был `true`
  с прошлого успешного прохода.

## Связанные тесты

TBD — теста нет на этот сценарий целиком (ни на успешный проход, ни на
разное итоговое состояние `DataUpdates` для гостя/авторизованного).

Единственный тест в `test/blocs/data_update_bloc_test.dart` —
`blocTest('DataUpdateClear очищает пользовательские данные БД', ...)` — не
`group()`, прямой `blocTest` верхнего уровня, без номера use-case — покрывает
`DataUpdateClear`, не `DataUpdateStartAll`. Единственный другой тест того же
файла — `test('DataUpdateBloc конструируется с полным набором зависимостей
из getIt', ...)`, проверяет только успешность конструктора.

Файл содержит развёрнутый комментарий-дисклеймер прямо перед `void main()`,
объясняющий, почему `DataUpdateStartAll` не покрыт тестом:

> `DataUpdateBloc` инжектирует >25 репозиториев через поля-геттеры `getIt<X>()`
> (не через конструктор) — конструктору блока нужны ВСЕ они зарегистрированы,
> даже для теста одного простого события. `DataUpdateStartAll` (~900 из 1013
> строк файла — основной sync pipeline) НЕ покрыт юнит-тестом: первая же
> строка обработчика — `await hasNetworkConnection()` (реальный DNS-запрос
> без DI-точки), дальше десятки приватных методов и реальные транзакции
> `AppDatabase`. Осмысленный юнит-тест такого масштаба потребовал бы
> рефакторинга источника под DI — вне рамок написания тестов без изменения
> кода. См. `TESTING_CHECKLIST.md`.

Этот дисклеймер прямо объясняет, почему сценарий, специфицированный этим
документом (полный успешный проход и его эффект на `DataUpdates`), тоже не
покрыт: он целиком лежит внутри того же непокрытого `on<DataUpdateStartAll>`.

## Открытые вопросы и ограничения

- **`showDataUpdatePage` — мёртвое поле события.** `DataUpdateEvent.showDataUpdatePage`
  устанавливается в нескольких местах (`MainPage` передаёт `true`,
  `DataUpdateInProgressWidget`'s кнопка «Повторить» передаёт `false`), но
  нигде не читается — ни в `DataUpdateBloc`, ни в `MainPage`'s
  `BlocListener<DataUpdateBloc>` (тот безусловно вызывает `DataUpdatePage.show`
  на любой `DataUpdateInProgress`, независимо от значения этого поля).
  `grep -rn "\.showDataUpdatePage" lib/` не находит ни одного места чтения,
  кроме определения и присвоений. Является ли это недоделанной фичей
  (условный показ страницы) или намеренно оставленным для будущего —
  ничем в коде не зафиксировано.
- **Неограниченный рост `DataUpdates` для устройства, где ни разу не
  выполнялся вход в аккаунт.** Поскольку `_clearDataUpdates()` достижим
  только через ветку `isAuthorized() == true`, установка, которую всегда
  используют как гостя, добавляет одну новую строку `generationsTypes` в
  `DataUpdates` при каждом успешном автоматическом (при каждом холодном
  старте) или ручном ([EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md))
  проходе, без верхней границы. Практический масштаб (сотни/тысячи строк за
  типичный срок жизни установки) не измерялся эмпирически — вывод сделан
  чтением кода `_addDataUpdateSuccess`/`BaseDao.ins`, не нагрузочным тестом
  или профилированием реальной БД.
- **Совпадение по времени двух независимых архитектурных решений превращает
  «мислейбл» в «полное исчезновение».** [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
  уже фиксирует, что категория `directories` пишется под именем
  `generationsTypes`; этот документ добавляет к этому, что для
  авторизованного пользователя даже эта неверно подписанная строка не
  переживает тот же самый проход, потому что `_clearDataUpdates()` в
  `_syncAllData` ничего не знает о том, что `loadDirectories()` уже
  отработал раньше в этом же вызове `on<DataUpdateStartAll>`. Сделано ли это
  намеренно (например, в предположении, что очистка происходит только «в
  начале прохода», без учёта фактического порядка вызовов) — не
  зафиксировано ни в коде, ни в комментариях.
- **Три отдельных вызова `hasConnection()` в рамках одного прохода** (шаги 2,
  5 и внутри `updateAndSyncRegagro`) не обёрнуты в общий кэш/пропуск —
  избыточность отмечена как факт, не оценивалась с точки зрения
  практического влияния на время старта приложения.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DataUpdateBloc.on<DataUpdateStartAll>`
  целиком, включая все переходы по `DataCategory`) и подтверждён точечным
  `grep` на отсутствие вызывающего кода для `updateAnimals`. Не воспроизведено
  тестом (см. «Связанные тесты» — TBD) и не проверено на реальном устройстве
  с накопленной историей множества гостевых проходов.
