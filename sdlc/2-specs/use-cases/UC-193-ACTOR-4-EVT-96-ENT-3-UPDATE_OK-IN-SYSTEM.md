# UC-193 — Синхронизация ~18 справочников HANDBOOKS в `loadDirectories()`: полная перезаливка при первом запуске, инкрементальный upsert при повторном

| | |
|---|---|
| Актор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Событие | [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же sync-шаг, что описан в [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) —
`DataUpdateBloc.loadDirectories()`, безусловно первый доменный шаг любого
полного sync-прохода (`on<DataUpdateStartAll>`), выполняемый и для гостя, и
для авторизованного пользователя одинаково, без проверки
`_authRepository.isAuthorized()` (в отличие от `_syncAuthData`, которая идёт
следом и гейтируется этой проверкой). Здесь описан именно успешный исход
этого шага целиком — последовательная синхронизация ~18 справочников
HANDBOOKS, с обеими её формами: первый запуск устройства/после форс-сброса
(`clearAndInsertAll` для каждого справочника) и повторный, инкрементальный
запуск (`insertAll`/upsert только по изменённым с прошлого раза строкам).
Обе формы ведут к одному и тому же результату (`UPDATE_OK`) — этот документ
описывает их как два альтернативных потока одного use-case, не как два
разных use-case, поскольку различается только объём данных и способ записи
в локальную БД, а не исход операции.

`ENT-3` (Taxonomy — `Kind`/`Breed`/`Suit`/`BreedSuit`) взят как сущность
файла, потому что это первая содержательная группа справочников в
последовательности `loadDirectories()`, которая проходит именно через явную
if/else-развилку `isIncremental` внутри самого `DataUpdateBloc` (не делегированную
в приватный метод репозитория) — реализация этой развилки идентична для ещё
девяти других справочников этого же прохода, перечисленных ниже.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система, действующая во
время sync-прохода. Прямого пользовательского действия в момент самой
синхронизации справочников нет — сам полный проход был запущен ранее одним
из:

- явно, [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — кнопка обновления в
  `lib/pages/main/main_page.dart`, `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`
  (`DataUpdateStartAll(resetNavigationOnSuccess: true)`), `lib/pages/in_work/in_work_page.dart`
  (`DataUpdateStartAll(isUpdateData: true)`) или повторная попытка на
  `lib/pages/data_update/data_update_page.dart` (`DataUpdateStartAll(showDataUpdatePage: false, again: true)`);
- автоматически, [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — `main_page.dart`'s
  `BlocListener<AuthBloc, AuthState>` диспатчит `DataUpdateStartAll` при
  переходе `AuthToMain` (успешное восстановление сессии/вход), без отдельного
  нажатия «обновить».

Дальше, внутри самого `loadDirectories()`, актор — безусловно [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md):
это единственное на сегодня документированное действие этого актора, не
привязанное к `_authRepository.isAuthorized()` — все остальные его действия,
перечисленные в `ACTOR-4` (FARM/ANIMAL/PROFILE), выполняются только внутри
`_syncAuthData`, которая идёт позже и целиком гейтируется этой проверкой.

## CURRENT

### Основной поток

1. Полный sync-проход стартует одним из путей, перечисленных в
   «Пользователь». `DataUpdateBloc.on<DataUpdateStartAll>`: после проверки
   сети (`getIt<NetworkConnectivityService>().hasConnection()` — истинно,
   иначе `DataUpdateFailure` сразу, до входа в `try`) вычисляет
   `directoriesSyncBaseline = AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
   (используется позже, шаг 15) и вызывает `await loadDirectories(event, emit)`
   внутри общего `try` — первым вызовом во всём проходе, до
   `_loadBoardDirectories` и до `_syncAuthData`.
2. Внутри `loadDirectories()` (`lib/blocs/data_update/data_update_bloc.dart`):
   `lastSyncDate = AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
   вычисляется заново (тем же вызовом, что и на шаге 1 — между ними ничего не
   пишет в `SharedPreferences`, поэтому значение совпадает); `isIncremental =
   lastSyncDate != null`. Весь метод обёрнут в собственный `try { ... } catch
   (e) { rethrow; }` — эта спека покрывает только путь без исключения.
3. **Countries** — `await _countriesRepository.syncCountries(updatedAtGt:
   lastSyncDate)`. Внутри: `getCountriesFromApi()` вызывается **без
   аргумента** (параметр `updatedAtGt` метода `syncCountries` в вызов не
   передаётся) — сервер всегда отдаёт **полный** список стран, независимо от
   `isIncremental`; `getBoardEnabledCountryIds()` — второй, независимый
   запрос (см. [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)
   для его собственного, отдельно документированного отказа); `await
   clearAndInsertAll(updatedCountries)` — **всегда** полная перезапись
   таблицы `Countries`, никогда `insertAll`, независимо от `isIncremental`
   (см. «Альтернативные потоки» — единственный справочник этого прохода,
   не следующий общему паттерну).
4. `_emitProgress(dataKey: DataKey.languages)`; `LanguageService.init()`
   переопределяет текущую локаль из уже сохранённого значения — сетевого
   вызова не делает.
5. **Kinds** — `_emitProgress(dataKey: DataKey.kinds)`; `kinds =
   await _kindsRepository.getKindsFromApi(updatedAtGt: lastSyncDate)`
   (`GET ${Constants.handbookServiceApi}/kinds`, `Accept-Language:
   LanguageService.locale`, `updated_at_gt` в query только если
   `lastSyncDate != null`). Далее развилка: `if (isIncremental) await
   _kindsRepository.insertAll(kinds); else await
   _kindsRepository.clearAndInsertAll(kinds);`.
6. Тот же паттерн (`getXFromApi(updatedAtGt: lastSyncDate)` → `if
   (isIncremental) insertAll(...) else clearAndInsertAll(...)`, реализованный
   явно внутри самого `loadDirectories`) повторяется буквально для **Breeds**
   (`_emitProgress(dataKey: DataKey.breeds)`), **Suits**
   (`_emitProgress(dataKey: DataKey.suits)`), **BreedSuits** (без отдельного
   `_emitProgress` — прогресс-текст экрана остаётся на «suits», пока идёт
   этот запрос) и **DisposalReasons** (`_emitProgress(dataKey:
   DataKey.disposalReasons)`).
7. **Проверка неотправленных вакцинаций** — `vaccination = await
   _vaccinationsRepository.getNotSyncVaccinationsWithDetails()`
   (`VaccinationsDao.getNotSyncVaccinationsWithDetails`: `sync == false`,
   `deletedAt IS NULL`, `updatedAt IS NULL`). Если список пуст: `if
   (_authRepository.isAuthorized()) await
   _vaccinesRepository.syncVaccines(updatedAtGt: lastSyncDate)` (гость
   никогда не синхронизирует `Vaccine`, независимо от того, есть ли
   неотправленные вакцинации — отдельное, самостоятельное условие, не
   упомянутое в тексте [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md));
   затем безусловно `await _unitsRepository.syncUnits(updatedAtGt:
   lastSyncDate)` (и гость, и авторизованный). Обе `syncX`-обёртки реализуют
   тот же `if (updatedAtGt != null) insertAll(...) else clearAndInsertAll(...)`
   паттерн внутри себя, не в `loadDirectories`; `VaccinesRepository.syncVaccines`
   дополнительно чистит связочную таблицу `DiseasesVaccines`
   (`_diseasesVaccinesRepository.clear()`) при `updatedAtGt == null`.
8. `_diseasesRepository.syncDiseases(updatedAtGt: lastSyncDate)` —
   выполняется всегда, независимо от шага 7 (не участвует в проверке
   неотправленных вакцинаций).
9. `_complexVaccinesRepository.syncComplexVaccines(updatedAtGt:
   lastSyncDate)`, `_injectionPlacesRepository.syncInjectionPlaces(updatedAtGt:
   lastSyncDate)`, `_injectionMethodsRepository.syncInjectionMethods(updatedAtGt:
   lastSyncDate)`, `_vaccinationTypesRepository.syncVaccinationTypes(updatedAtGt:
   lastSyncDate)` — тот же `syncX`-паттерн, каждый безусловно, без
   собственного `_emitProgress`.
10. **GenerationsTypes** — `_emitProgress(dataKey: DataKey.generationsTypes,
    dataCategory: DataCategory.generationsTypes)` — **это последнее
    присвоение `_currentDataCategory` внутри `loadDirectories()`**; поле
    остаётся равным `generationsTypes` до самого конца метода (см. шаг 14 и
    [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)). `generationsTypes
    = await _generationsTypesRepository.getTypesFromApi(updatedAtGt:
    lastSyncDate)`, затем та же явная развилка `isIncremental`.
11. Тот же явный паттерн — для **AgeGroups** (без отдельного
    `_emitProgress`), **MarkerTypes** (`_emitProgress(dataKey:
    DataKey.markerTypes)`), **MarkerPlaces** (`_emitProgress(dataKey:
    DataKey.markerPlaces)`), **KindMarkerPlaces** (без отдельного
    `_emitProgress`).
12. `_absenceReasonsRepository.syncAbsenceReasons(updatedAtGt: lastSyncDate)` —
    последний справочник последовательности, тот же `syncX`-паттерн.
13. `await AppCacheService.saveDirectoriesLastSyncDate(DateTime.now(),
    LanguageService.locale)` — записывает в `SharedPreferences` пару (дата,
    текущая локаль); именно эта пара станет `lastSyncDate` следующего
    прохода и определит, будет ли он инкрементальным.
14. `await _addDataUpdateSuccess(_currentDataCategory)` — пишет одну строку
    в `DataUpdates` с `dataCategoryId = DataCategory.generationsTypes` (не
    `.directories` — `_currentDataCategory` было переставлено на шаге 10 и
    не возвращено обратно). Уже задокументированный дефект — см.
    [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), не переисследуется
    здесь заново.
15. `loadDirectories()` возвращает управление без исключения.
    `on<DataUpdateStartAll>` продолжает: `await _loadBoardDirectories(event,
    emit, updatedAtGt: directoriesSyncBaseline)` (справочники BOARD — область
    [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md), не этого
    документа; используется значение `lastSyncDate`, вычисленное **до**
    `loadDirectories()`, то есть предыдущая, ещё не обновлённая шагом 13
    отметка), затем, если `_authRepository.isAuthorized()`, `_syncAuthData`
    (FARM/ANIMAL/PROFILE), затем `emit(DataUpdateSuccess(...))`.

### Альтернативные потоки

- **Первый запуск — `isIncremental == false`, `clearAndInsertAll` для
  каждого справочника (кроме Countries, который делает это всегда — см.
  ниже).** Наступает, когда `AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale)`
  возвращает `null`. Это происходит в одном из следующих случаев:
  - справочники этого устройства/установки приложения никогда ещё не
    синхронизировались успешно (ключ `last_directories_sync_date` в
    `SharedPreferences` отсутствует вовсе);
  - **смена языка интерфейса** — `getDirectoriesLastSyncDate` явно
    возвращает `null`, если `savedLocale != currentLocale`, даже когда сама
    дата сохранена — то есть смена локали форсирует полный реload, не
    инкрементальный, для абсолютно всех справочников разом;
  - **вход по логину/паролю** — `AuthRepository._getTokenDataFromApi`
    вызывает `AppCacheService.clearDirectoriesLastSyncDate()` **безусловно**,
    до того как вызывающий метод `login()` вообще проверяет
    `tokenDataDto.isSuccess` — то есть дата стирается, даже если сама
    попытка входа окажется неуспешной (`throw 'invalid_login_password'`
    выполнится уже после этого стирания);
  - **переход в гостевой режим** — `AuthRepository.loginWithoutAuthorization()`
    вызывает `AppCacheService.clearDirectoriesLastSyncDate()` безусловно.

  В каждом из этих случаев каждый из ~17 справочников (все, кроме Countries)
  запрашивается у сервера **без** `updated_at_gt` (полный список) и
  сохраняется через `clearAndInsertAll` → `BaseDao.clearAndInsertAll` →
  `clear()` (полное удаление всех строк текущей таблицы) + `insAll()`
  (`batch.insertAll(..., mode: InsertMode.insertOrReplace)`) внутри одной
  drift-транзакции — предыдущее содержимое таблицы никогда не остаётся
  «частично устаревшим», оно стирается целиком перед перезаписью.

- **Повторный запуск — `isIncremental == true`, инкрементальный `insertAll`
  (upsert).** Наступает, когда сохранённая дата есть и совпадает по локали с
  текущей. Каждый из ~17 справочников (кроме Countries) запрашивается с
  `updated_at_gt: lastSyncDate` — сервер возвращает только строки,
  изменившиеся с прошлого успешного прохода, — и сохраняется через
  `insertAll` → `dao.insAll` → `batch.insertAll(..., mode:
  InsertMode.insertOrReplace)` **без** предварительного `clear()`: строки с
  совпадающим `id` заменяются присланной версией, строки, отсутствующие в
  ответе (в т.ч. удалённые на сервере), никогда не трогаются этим путём —
  локальная таблица может продолжать содержать строки, которые сервер уже
  не отдаёт ни при одном инкрементальном запросе.

- **Есть неотправленные локальные вакцинации — `Vaccine`/`Unit` пропускаются
  целиком.** Если `getNotSyncVaccinationsWithDetails()` возвращает непустой
  список, ни `syncVaccines`, ни `syncUnits` не вызываются в этом проходе
  вовсе (не «пропускают часть строк» — не выполняются как метод) — весь блок
  `if (vaccination.isEmpty) { ... }` просто не входит внутрь. `Diseases` и
  остальные справочники вакцинации (`ComplexVaccines`, `InjectionPlaces`,
  `InjectionMethods`, `VaccinationTypes`) продолжают синхронизироваться как
  обычно — только `Vaccine`/`Unit` защищены этим условием (см.
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) — «чтобы не
  перетереть ссылочные записи, на которые они опираются»).

- **Countries — не следует общему паттерну isIncremental вовсе.**
  `CountriesRepository.syncCountries` не содержит условной развилки:
  `clearAndInsertAll` вызывается безусловно на каждом проходе, и
  `getCountriesFromApi()` вызывается внутри `syncCountries` без аргумента —
  параметр `updatedAtGt`, полученный самим `syncCountries`, никогда не
  доходит до сетевого запроса. Формулировка
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) («каждый
  справочник — с `updatedAtGt: lastSyncDate`») для Countries фактически не
  верна: этот конкретный справочник всегда запрашивается и перезаписывается
  полностью, независимо от `isIncremental` — см. «Открытые вопросы».

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy —
  `Kind`/`Breed`/`Suit`/`BreedSuit`) — сущность, чья таблица здесь
  синхронизируется (шаги 5–6): полная перезапись при первом запуске,
  инкрементальный upsert при повторном. Сама сущность не редактируется
  никаким другим модулем локально (см. её собственный инвариант) — это
  единственный источник её содержимого.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country) — первый
  справочник последовательности (шаг 3); единственный, не следующий паттерну
  `isIncremental` этого сценария (см. «Альтернативные потоки»); попутно
  пересчитывается `boardEnabled` — см.
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) для отказа
  именно этой части.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md)
  (DisposalReason) — тот же паттерн, шаг 6.
- [ENT-7](../entities/ENT-7-GENERATION-TYPE-IN-HANDBOOKS.md)
  (GenerationType) — тот же паттерн (шаг 10); попутно — единственный
  справочник, чей `DataCategory` (`generationsTypes`) ошибочно остаётся
  записанным в журнал [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)
  как категория успеха всего шага `directories` (см. шаг 14).
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Misc
  directories — `Unit`, `KindMarkerPlaces`) — `Unit` синхронизируется на шаге
  7 (защищён проверкой неотправленных вакцинаций, но не гейтом по
  авторизации — в отличие от `Vaccine`); `KindMarkerPlaces` — на шаге 11, тем
  же явным паттерном, что и Taxonomy.
- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination, ANIMAL)
  — читается (не изменяется) через `getNotSyncVaccinationsWithDetails()` на
  шаге 7 — единственная точка, где этот сценарий заглядывает за пределы
  HANDBOOKS, чтобы решить, пропускать ли `Vaccine`/`Unit`.
- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate, SYSTEM)
  — получает единственную строку успеха этого шага (шаг 14), под неверной
  категорией — уже задокументированный дефект, цитируется, не
  переисследуется.
- Без собственной сущности в `sdlc/2-specs/entities/` на сегодня —
  синхронизируются этим же сценарием (шаги 7–9, 12), но не покрыты ни одним
  `ENT-*-IN-HANDBOOKS.md`: `Vaccine`, `Disease`, `DiseasesVaccines`
  (связочная — не путать с `DiseasesKinds`,
  [ENT-6](../entities/ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md)), `ComplexVaccine`
  и его связочная `DiseasesComplexVaccines`, `InjectionPlace`,
  `InjectionMethod`, `VaccinationType`, `AgeGroup`, `MarkerType`,
  `MarkerPlace`, `AbsenceReason` — см. «Открытые вопросы».

### Бизнес-правила

- `loadDirectories()` выполняется безусловно на каждом полном проходе, для
  гостя и авторизованного одинаково — единственная синхронизация ACTOR-4,
  не гейтированная `isAuthorized()`.
- `isIncremental` — одно булево значение, вычисленное один раз в начале
  метода из пары (сохранённая дата, сохранённая локаль), и разделяемое почти
  всеми справочниками прохода — не пересчитывается отдельно для каждого
  (Countries — единственное исключение, игнорирующее его вовсе).
- «Последняя успешная синхронизация справочников» хранится в
  `SharedPreferences` (`AppCacheService`), не в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md):
  эти два источника независимы — `SharedPreferences` реально управляет
  инкрементальностью следующего прохода, `DataUpdates` в это же время
  получает строку под неверной категорией и не может служить надёжным
  подтверждением, что шаг `directories` вообще случился.
- Метка сохраняется (`saveDirectoriesLastSyncDate`, шаг 13) только в самом
  конце метода, после того как все ~18 справочников синхронизированы
  успешно — если процесс прервётся раньше (например, исключение на любом
  промежуточном шаге), метка не будет обновлена и следующий проход снова
  окажется полным (`isIncremental == false`), а не «доездом» с середины
  списка — ни один частично пройденный список справочников не сохраняется.
- Полная перезаливка (`clearAndInsertAll`) и инкрементальный upsert
  (`insertAll`) для одного и того же справочника используют один и тот же
  `BaseDao`/транзакционный механизм — различается только то, вызывается ли
  предварительный `clear()`, и какой `updated_at_gt` уходит на сервер.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — весь описанный сценарий (порядок ~18
справочников, развилка `isIncremental`, условный пропуск `Vaccine`/`Unit`,
отклонение `Countries` от общего паттерна, форс полного реload по смене
локали/логину/гостевому входу, финальная запись в `DataUpdates` под неверной
категорией) воспроизводится статическим чтением: `DataUpdateBloc.loadDirectories`
→ `AppCacheService` → `AuthRepository` → отдельные репозитории справочников.
Исправление любого из отмеченных отклонений (Countries, гость без
`Vaccine`, категория журнала) в рамках этого документирующего прохода не
выполняется — это фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | сетевой чек, вычисление `directoriesSyncBaseline`, вызывает `loadDirectories` первым доменным шагом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories` | CURRENT | предмет UC — последовательность ~18 справочников, явная развилка `isIncremental` для Kinds/Breeds/Suits/BreedSuits/DisposalReasons/GenerationsTypes/AgeGroups/MarkerTypes/MarkerPlaces/KindMarkerPlaces, условный пропуск Vaccine/Unit, финальная запись в журнал |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._emitProgress`, `._currentDataCategory`, `._addDataUpdateSuccess` | CURRENT | прогресс UI и запись в журнал; `_currentDataCategory` необратимо переставляется на `generationsTypes` на шаге 10 |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate`, `.saveDirectoriesLastSyncDate`, `.clearDirectoriesLastSyncDate` | CURRENT | источник `isIncremental`; ключ несёт и дату, и локаль — рассинхрон локали форсирует полный реload |
| `lib/l10n/language_service.dart` | `LanguageService.locale`, `.init` | CURRENT | локаль — участвует и в ключе `SharedPreferences`, и в заголовке `Accept-Language` каждого запроса справочника |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized`, `.login`, `._getTokenDataFromApi`, `.loginWithoutAuthorization` | CURRENT | форс полного реload по логину/паролю (безусловно, до проверки успеха попытки) и гостевому входу |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.syncCountries`, `.getCountriesFromApi`, `.getBoardEnabledCountryIds` | CURRENT | единственное отклонение от `isIncremental`-паттерна прохода — см. «Альтернативные потоки»/«Открытые вопросы» |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository.getKindsFromApi` | CURRENT | Taxonomy — первый справочник с явной `isIncremental`-развилкой в самом блоке |
| `lib/repositories/breed/breeds_repository.dart` | `BreedsRepository.getBreedsFromApi` | CURRENT | тот же паттерн |
| `lib/repositories/suit/suits_repository.dart` | `SuitsRepository.getSuitsFromApi` | CURRENT | тот же паттерн |
| `lib/repositories/breed_suit/breed_suits_repository.dart` | `BreedSuitsRepository.getBreedSuitsFromApi` | CURRENT | тот же паттерн, без собственного `_emitProgress` |
| `lib/repositories/disposal_reason/disposal_reasons_repository.dart` | `DisposalReasonsRepository.getDisposalReasonsFromApi` | CURRENT | тот же паттерн |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getNotSyncVaccinationsWithDetails` | CURRENT | условие, решающее пропуск `Vaccine`/`Unit` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | точный фильтр — `sync=false`, `deletedAt IS NULL`, `updatedAt IS NULL` |
| `lib/repositories/vaccination/vaccines_repository.dart` | `VaccinesRepository.syncVaccines` | CURRENT | дополнительно гейтирован `isAuthorized()` — гость никогда не получает `Vaccine`; чистит `DiseasesVaccines` при полном запуске |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository.syncUnits` | CURRENT | не гейтирован авторизацией — только проверкой неотправленных вакцинаций |
| `lib/repositories/vaccination/diseases_repository.dart` | `DiseasesRepository.syncDiseases` | CURRENT | безусловен, вне проверки шага 7 |
| `lib/repositories/vaccination/complex_vaccines_repository.dart` | `ComplexVaccinesRepository.syncComplexVaccines` | CURRENT | тот же делегированный `syncX`-паттерн |
| `lib/repositories/vaccination/injection_places_repository.dart` | `InjectionPlacesRepository.syncInjectionPlaces` | CURRENT | тот же паттерн |
| `lib/repositories/vaccination/injection_methods_repository.dart` | `InjectionMethodsRepository.syncInjectionMethods` | CURRENT | тот же паттерн |
| `lib/repositories/vaccination/vaccination_types_repository.dart` | `VaccinationTypesRepository.syncVaccinationTypes` | CURRENT | тот же паттерн |
| `lib/repositories/generations_types_repository/generations_types_repository.dart` | `GenerationsTypesRepository.getTypesFromApi` | CURRENT | GenerationType — точка, где `_currentDataCategory` необратимо переставляется |
| `lib/repositories/age_group/age_groups_repository.dart` | `AgeGroupsRepository.getAgeGroupsFromApi` | CURRENT | явная `isIncremental`-развилка в блоке, без `_emitProgress` |
| `lib/repositories/marker_type/marker_types_repository.dart` | `MarkerTypesRepository.getMarkerTypesFromApi` | CURRENT | тот же паттерн |
| `lib/repositories/marker_places/marker_places_repository.dart` | `MarkerPlacesRepository.getMarkerPlacesFromApi` | CURRENT | тот же паттерн |
| `lib/repositories/kind_marker_places/kind_marker_places_repository.dart` | `KindMarkerPlacesRepository.getKindMarkerPlacesFromApi` | CURRENT | тот же паттерн, без `_emitProgress` |
| `lib/repositories/absence_reason/absence_reasons_repository.dart` | `AbsenceReasonsRepository.syncAbsenceReasons` | CURRENT | последний справочник последовательности |
| `lib/repositories/base_repository.dart` | `BaseRepository.insertAll`, `.clearAndInsertAll` | CURRENT | тонкие обёртки над `dao.insAll`/`dao.clearAndInsertAll`, общие для всех перечисленных репозиториев |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll`, `.clearAndInsertAll`, `.clear` | CURRENT | `insAll` — `batch.insertAll(..., mode: InsertMode.insertOrReplace)` (upsert); `clearAndInsertAll` — `clear()` + `insAll()` в одной транзакции |
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataCategory`, `DataKey` | CURRENT | категория (`generationsTypes`), под которой ошибочно фиксируется итоговый успех этого шага — см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |

## Критерии приёмки

- При `AppCacheService.getDirectoriesLastSyncDate(LanguageService.locale) ==
  null` (первый запуск, смена локали, либо форс-сброс по логину/паролю или
  гостевому входу) каждый из ~17 справочников (кроме Countries) получает от
  сервера полный список (без `updated_at_gt`) и сохраняется через
  `clearAndInsertAll` — предыдущее содержимое таблицы полностью стирается
  перед вставкой.
- При непустой сохранённой дате, совпадающей по локали, каждый из тех же
  ~17 справочников получает от сервера только строки, изменившиеся с
  `lastSyncDate` (`updated_at_gt`), и сохраняется через `insertAll`
  (upsert) — без предварительного `clear()`.
- `Countries` всегда сохраняется через `clearAndInsertAll`, и его запрос к
  серверу (`getCountriesFromApi()`) всегда выполняется без фильтра по дате —
  независимо от значения `isIncremental` для остальных справочников этого же
  прохода.
- Если `VaccinationsDao.getNotSyncVaccinationsWithDetails()` возвращает
  непустой список, ни `VaccinesRepository.syncVaccines`, ни
  `UnitsRepository.syncUnits` не вызываются в этом проходе.
- Если список пуст, `UnitsRepository.syncUnits` вызывается независимо от
  авторизации; `VaccinesRepository.syncVaccines` вызывается только если
  `_authRepository.isAuthorized()` — гость никогда не получает `Vaccine` в
  этом сценарии.
- После успешного завершения всех шагов метода `AppCacheService.saveDirectoriesLastSyncDate(DateTime.now(),
  LanguageService.locale)` записывается ровно один раз, в самом конце —
  делая следующий проход инкрементальным (при неизменной локали и
  отсутствии форс-сброса).
- `DataUpdates` получает ровно одну строку успеха этого шага, с
  `dataCategoryId == DataCategory.generationsTypes` (не `.directories`).

## Связанные тесты

TBD — теста нет. `grep -rln "loadDirectories\|syncCountries\|getKindsFromApi\|DataCategory.directories" test/` не находит ни одного файла — ни сам `DataUpdateBloc.loadDirectories`, ни развилка `isIncremental`, ни отклонение `Countries`, ни условие пропуска `Vaccine`/`Unit` не покрыты никаким тестом. Отдельных репозиторных тестов ни для одного из ~18 справочников этого прохода не существует (`find test -iname "*kind*repo*" -o -iname "*countries_repo*" -o -iname "*directories*"` — пусто).

Единственный существующий тестовый файл, трогающий `DataUpdateBloc` вообще —
`test/blocs/data_update_bloc_test.dart` — содержит:

- `test('DataUpdateBloc конструируется с полным набором зависимостей из
  getIt', ...)` — проверяет только успешное конструирование блока (все
  зависимости зарегистрированы в тестовом `getIt`), не поведение;
- `blocTest('DataUpdateClear очищает пользовательские данные БД', ...)` —
  прямой `blocTest` верхнего уровня, без `group()`, покрывает только
  `DataUpdateClear`, не `DataUpdateStartAll`/`loadDirectories`.

Файл содержит собственный дисклеймер, объясняющий это отсутствие покрытия:

> DataUpdateBloc инжектирует >25 репозиториев через поля-геттеры getIt<X>()
> (не через конструктор) — конструктору бЛока нужны ВСЕ они
> зарегистрированы, даже для теста одного простого события.
> DataUpdateStartAll (~900 из 1013 строк файла — основной sync pipeline) НЕ
> покрыт юнит-тестом: первая же строка обработчика — `await
> hasNetworkConnection()` (реальный DNS-запрос без DI-точки), дальше десятки
> приватных методов и реальные транзакции AppDatabase. Осмысленный
> юнит-тест такого масштаба потребовал бы рефакторинга источника под DI —
> вне рамок написания тестов без изменения кода. См. TESTING_CHECKLIST.md.

`loadDirectories()` — часть того же необёрнутого DI `DataUpdateStartAll`,
поэтому тот же дисклеймер прямо применим и к сценарию этого документа.

## Открытые вопросы и ограничения

- **Countries — не следует общему паттерну, вопреки формулировке
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md).** Текст
  события утверждает, что каждый справочник синхронизируется «с
  `updatedAtGt: lastSyncDate`» — для Countries это не так:
  `syncCountries` получает параметр, но не передаёт его ни в
  `getCountriesFromApi()`, ни в собственную развилку (развилки для
  Countries нет вовсе, всегда `clearAndInsertAll`). Является ли это
  осознанным решением (например, потому что таблица стран мала и полная
  перезагрузка дешева) или недосмотром при копировании паттерна из
  остальных справочников — ничем в коде/комментариях не зафиксировано.
- **Неуспешная попытка входа по паролю всё равно форсирует полный реload
  справочников.** `AuthRepository._getTokenDataFromApi` вызывает
  `AppCacheService.clearDirectoriesLastSyncDate()` безусловно, до проверки
  `tokenDataDto.isSuccess` в вызывающем `login()` — то есть неверный
  логин/пароль (`throw 'invalid_login_password'`) уже успел стереть
  сохранённую дату к моменту, когда пользователь увидит ошибку входа.
  Следующий успешный проход (даже без последующего логина — например, для
  гостя) окажется полным, а не инкрементальным, из-за одной неудачной
  попытки чужого входа. Не зафиксировано, является ли это намеренным.
- **Гость никогда не синхронизирует `Vaccine`, независимо от неотправленных
  вакцинаций.** Условие `_authRepository.isAuthorized()` внутри блока
  `if (vaccination.isEmpty)` — самостоятельный, отдельный от проверки
  неотправленных вакцинаций гейт, не упомянутый текстом
  [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) (который
  говорит только про пропуск «если есть неотправленные локальные
  вакцинации»). Продуктовое обоснование (гостю не нужен справочник вакцин,
  потому что вакцинация — авторизованный сценарий?) нигде явно не
  зафиксировано в коде/комментариях.
- **~10 таблиц, синхронизируемых этим сценарием, не имеют собственной
  сущности в `sdlc/2-specs/entities/`.** `Vaccine`, `Disease`,
  `DiseasesVaccines`, `ComplexVaccine`, `DiseasesComplexVaccines`,
  `InjectionPlace`, `InjectionMethod`, `VaccinationType`, `AgeGroup`,
  `MarkerType`, `MarkerPlace`, `AbsenceReason` синхронизируются в тех же
  шагах `loadDirectories()`, что и Taxonomy/Country/DisposalReason/GenerationType/Misc
  directories, но ни один `ENT-3`…`ENT-8` их не покрывает буквально (только
  их связочная родственница `DiseasesKinds` — через
  [ENT-6](../entities/ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md), которая
  описывает другую таблицу, не `DiseasesVaccines`/`DiseasesComplexVaccines`).
  Это раздел HANDBOOKS, уже помеченный как специфицированный целиком в
  [MOD-2](../modules/MOD-2-HANDBOOKS.md) — данный документ фиксирует пробел,
  не устраняет его: не в компетенции этого use-case дополнять чужой,
  замороженный модуль.
- **`DiseasesVaccinesRepository.insertDiseasesVaccinesByVaccineAndDiseases`
  вызывается без `await` внутри синхронного маппера
  `VaccinesRepository._toVaccineWithDiseases`.** Замечено по ходу чтения
  `syncVaccines`, не исследовано глубже — потенциальный источник гонки
  между записью вакцин и записью их связей с болезнями, либо тихой потери
  ошибки записи связи; относится к сущности, не имеющей собственной спеки
  (см. пункт выше), поэтому не разбирается здесь подробно.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод сделан статическим чтением кода (`DataUpdateBloc.loadDirectories` →
  каждый из перечисленных репозиториев → `BaseRepository`/`BaseDao`), без
  запущенного теста, подтверждающего любую из описанных ветвей (см.
  «Связанные тесты» — TBD).
