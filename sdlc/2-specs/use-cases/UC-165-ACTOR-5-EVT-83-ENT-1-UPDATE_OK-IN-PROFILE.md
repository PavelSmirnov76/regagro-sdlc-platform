# UC-165 — Смена языка при сохранении профиля: вместо снекбара успеха — каскад LanguageBloc → полный ресинк без отправки локальных настроек, сброс на главный экран

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь выбирает новый язык интерфейса через `LanguagePickerField` на
экране `ProfileSettingsPage` и нажимает «Сохранить» вместе с остальными
полями формы — тот же `ProfileEditCubit.saveChanges()`, что и
[UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)/[UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md).
Здесь описывается ветка, в которой `newUserData.locale` отличается от
`currentUserData.locale`: вместо обычного успеха (снекбар «Успешно
сохранено») метод эмитит `isLanguageChanged: true` и возвращает `false` —
это запускает отдельный, не связанный с остальными полями формы каскад:
`LanguageBloc.on<LanguageEventChange>` → `LanguageService.setLocale()` →
глобальный ребилд `MaterialApp.router` и множества отдельных экранов →
`ProfileEditCubit.load()` → **полный ресинк**
(`DataUpdateBloc.add(DataUpdateStartAll(resetNavigationOnSuccess: true))`,
без `isUpdateData: true`) → сброс навигации на главный экран приложения.

Как и в [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md), один
и тот же метод обслуживает две структурно разные ветки, каждая проверена
независимо чтением кода:

- (а) **авторизованный** — `AuthRepository.updateUser(newUserData)` реально
  отправляет **весь** черновик на сервер (включая любые одновременно
  изменённые `name`/`email`/`phone`/`countryId`, не только `locale`) и
  успешно завершается **до** того, как метод проверяет расхождение локали;
- (б) **гость** — без сетевого вызова: только
  `AppCacheService.saveGuestCountryCode()` (если выбрана страна), сам факт
  смены языка не персистируется этим методом вовсе (персистирует его позже
  `LanguageService.setLocale()`, общий для обеих веток).

Результат помечен `UPDATE_OK`, потому что сама смена языка (то, ради чего
существует [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md)) в
обеих ветках доходит до конца без исключения — `LanguageService.setLocale()`
не может отказать (запись в `SharedPreferences` не проверяется на ошибку).
Ветка (а), где сопутствующие поля формы отправлены на сервер, но снекбар
успеха при этом не показывается никогда, документируется здесь же — не как
отдельный `ERROR`/`REJECTED`, поскольку операция технически не отказала ни
на одном шаге.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
независимо от статуса авторизации: `ProfileSettingsView` не имеет
route-guard'а, `LanguagePickerField` в `_ProfileSettingsRegionAndLanguage`
показывается безусловно, вне блока `if (AppCacheService.isAuthorized())`, —
и гость, и авторизованный видят и могут менять язык одинаковым кодом.

## CURRENT

### Основной поток

Основной поток — ветка (а), авторизованный пользователь, поскольку в ней
запрос реально доходит до сервера, прежде чем каскад смены языка начинается.

1. Пользователь выбирает язык в `LanguagePickerField`
   (`_ProfileSettingsRegionAndLanguage`, `profile_settings_view.dart`) —
   `onSelected` вызывает `ProfileEditCubit.selectLanguage(languageModel)`:
   `language = languageModel.code`; `newUserData = state.newUserData?.copyWith(locale: language) ?? state.currentUserData?.copyWith(locale: language)`;
   `emit(state.copyWith(newUserData: newUserData))`. `state.currentUserData`
   не меняется.
2. `state.isDataChanged` (сравнивает, среди прочего,
   `currentUserData?.locale != newUserData?.locale`) становится `true` —
   кнопка «Сохранить» видна. Пользователь может при этом же сохранении также
   поменять `name`/`email`/`phone`/страну — всё это уйдёт в одном и том же
   запросе, см. шаг 6.
3. Пользователь нажимает «Сохранить»: `onTap` вызывает
   `await context.read<ProfileEditCubit>().saveChanges()`.
4. `saveChanges()`: `emit(state.copyWith(loading: true))` — кнопка
   переходит в `isLoading: true`. `newUserData = state.newUserData` —
   непусто. `_authRepository.isAuthorized()` — истинно.
5. `await _authRepository.updateUser(newUserData);` — полная логика уже
   описана в [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)
   (шаг 5): `_userDataForUpdate`, `PUT {authSerivceApi}/user`,
   `response['data']`, `_normalizeUserPhoneFields`. Тело запроса — это
   **весь** `newUserData.toUserDTO().toJson()`, включая новое значение
   `locale` (поле `User.locale` маппится в `UserDTO` без переименования
   ключа — `@JsonKey` для него не объявлен) и любые другие одновременно
   отредактированные поля. Запрос завершается без исключения.
   `_saveMainAuthData(user: UserDTO.fromJson(userJson), updateServerIntegrations: false)`
   вызывается **без `await`** внутри `updateUser()` (`auth_repository.dart`,
   строка вызова `_saveMainAuthData(...)` не предварена `await`, в отличие
   от вызовов `box.put(...)` **внутри** самого `_saveMainAuthData`, которые
   awaited) — `updateUser()` возвращает управление в `saveChanges()`, не
   дожидаясь гарантированного завершения записи `box.put(userKey, ...)` в
   Hive `AUTH_BOX`. См. «Открытые вопросы» — потенциальная гонка с
   реактивной Hive-подпиской того же кубита.
6. Обратно в `saveChanges()`: `newUserData.locale != state.currentUserData?.locale` —
   истинно (сценарий этого use-case). `emit(state.copyWith(isLanguageChanged: true));`
   — в отличие от ветки (б) (шаг 4′ ниже) и от `else`-ветки без смены языка
   ([UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)), это
   `copyWith` **не** сбрасывает `loading` обратно в `false` — поле остаётся
   `true` со времени шага 4. `saveChanges()` возвращает `false`.
7. `ProfileSettingsView`'s `onTap`: `if (context.mounted && isSaved) { showAppSnackBarSuccess(...); }` —
   `isSaved == false`, снекбар успеха **не показывается**. Пользователь не
   получает вообще никакой немедленной обратной связи о том, что
   сопутствующие поля (например, новое имя) на самом деле уже были приняты
   сервером на шаге 5.
8. `BlocConsumer<ProfileEditCubit, ProfileEditState>` в `ProfileSettingsView`
   (`listenWhen: (previous, current) => !previous.isLanguageChanged && current.isLanguageChanged`)
   реагирует: `newLocale = state.newUserData?.locale ?? LanguageService.locale;`
   (равен только что выбранному языку — `newUserData` не был перезаписан
   между шагами 1 и 6); `context.read<LanguageBloc>().add(LanguageEventChange(newLocale));`
   затем `context.read<ProfileEditCubit>().consumeLanguageChangeFlag()` —
   `emit(state.copyWith(isLanguageChanged: false))`, `loading` по-прежнему
   не тронут этим вызовом и остаётся `true`.
9. `LanguageBloc.on<LanguageEventChange>`: `await LanguageService.setLocale(newLocale);`
   (`pref.setString('language', newLocale)`, `_locale = newLocale` —
   статическое поле класса, не проверяет ошибку записи) →
   `emit(LanguageStateChanged(newLocale))`.
10. `LanguageStateChanged` доходит одновременно (не в каком-то определённом
    порядке — оба подписаны на один и тот же `LanguageBloc.stream`) до:
    - `main.dart`'s корневого `BlocBuilder<LanguageBloc, LanguageStateInitial>`,
      оборачивающего `MaterialApp.router`: `lang = languageState.language == 'sp' ? 'es' : languageState.language;`
      (ветка `'sp'` мертва — `LanguageService.supportedLocales` такого кода
      не содержит) → `MaterialApp.router(locale: Locale(lang), ...)`
      пересобирается — приложение целиком переходит на новый язык при
      следующей перерисовке любого виджета, читающего `AppLocalizations.of(context)`.
    - независимых `BlocListener<LanguageBloc, LanguageStateInitial>` на
      экранах `board_page.dart`, `my_ads_page.dart`, `profile_page.dart`,
      `in_work_page.dart`, `favourite_ads_page.dart`, `main_page.dart`,
      `structure_widget.dart` — каждый на `LanguageStateChanged` вызывает
      `setState(() {})` **локально**, форсируя ребилд именно этого экрана —
      структурно избыточно по отношению к глобальному ребилду
      `MaterialApp.router`, но реализовано отдельно на каждом экране, не
      централизованно.
    - того же `BlocListener<LanguageBloc, LanguageStateInitial>`, что
      оборачивает весь `BlocProvider<ProfileEditCubit>` в
      `ProfileSettingsView` (внешний относительно `BlocConsumer` из шага 8):
      `await context.read<ProfileEditCubit>().load();` — заново запрашивает
      `PackageInfo`, `_countriesRepository.getAll()` и
      `_authRepository.getUser()!` (теперь уже отражающий подтверждённые
      сервером на шаге 5 данные, при условии, что фоновая запись Hive из
      шага 5 к этому моменту успела завершиться — см. «Открытые вопросы»),
      эмитит новый `ProfileEditState(loading: false, ...)` — **это первое
      место, где `loading` возвращается в `false`** после шага 6, то есть
      кнопка «Сохранить» показывает крутящийся индикатор весь путь от шага 4
      до этого момента. Затем, `if (context.mounted)`:
      `context.read<DataUpdateBloc>().add(const DataUpdateStartAll(resetNavigationOnSuccess: true));` —
      **без** `isUpdateData: true`.
11. `DataUpdateBloc.on<DataUpdateStartAll>` немедленно
    `emit(DataUpdateInProgress(progressPercent: 0))`. `MainPage`'s
    глобальный `BlocListener<DataUpdateBloc, DataUpdateState>`
    (`main_page.dart`, `if (state is DataUpdateInProgress) DataUpdatePage.show(context);`)
    открывает `DataUpdatePage` поверх экрана настроек профиля, на котором
    пользователь только что нажал «Сохранить».
12. Проверка сети (`NetworkConnectivityService.hasConnection()`); в этом
    сценарии сеть есть. Полный проход выполняется: `loadDirectories`,
    `_loadBoardDirectories`, затем, поскольку `_authRepository.isAuthorized()`
    истинно, `_syncAuthData` — весь конвейер (`_deletePlacesFromRDS`,
    `_syncFarms`, `_syncPlaces`, взвешивания, `updateAndSyncRegagro`,
    `updateAndSyncSHTP`, устройства) специфицируется по частям другими
    use-case (`ANIMAL`/будущий `SYSTEM`), не здесь. Единственный шаг,
    релевантный этому use-case, — `SettingsRepository.getSettingFromSHTP()`
    (pull, вызывается **безусловно** на каждый проход) перезаписывает
    единственную строку `ProfileSettings` ([ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md))
    и `Kind.visible` содержимым с сервера; `SettingsRepository.setSettingToSHTP()`
    (push) **не вызывается** — `data_update_event.dart`'s комментарий на
    `DataUpdateStartAll.isUpdateData` прямо это документирует: «Явный флаг:
    синк запущен со страницы "В работе" через кнопку "Обновить данные". По
    умолчанию false, чтобы не отправлять настройки на сервер в других
    сценариях» — событие из шага 10 использует значение по умолчанию
    (`isUpdateData: false`).
13. `on<DataUpdateStartAll>` доходит до
    `emit(DataUpdateSuccess(resetNavigationOnSuccess: event.resetNavigationOnSuccess))`
    (`resetNavigationOnSuccess == true`, унаследовано из шага 10).
14. `DataUpdatePage`'s `BlocConsumer<DataUpdateBloc, DataUpdateState>`
    `listener`, ветка `if (state is DataUpdateSuccess)`: проверка
    `have_any_language` (см. «Открытые вопросы» — отдельный, не связанный по
    сути с этим сценарием механизм); `Navigator.of(context).pop();`
    (закрывает `DataUpdatePage`); `context.read<AppUpdateBloc>().add(AppUpdateEventCheckUpdate(showModalMessage: true));`;
    затем, поскольку `state.resetNavigationOnSuccess == true`:
    `WidgetsBinding.instance.addPostFrameCallback((_) => resetMainShellNavigation());` —
    **не** `context.go(Routes.mainNavigator)`, как было бы при `false`.
15. `resetMainShellNavigation()` (`lib/pages/routes.dart`):
    `rootNavigatorKey.currentState?.popUntil((route) => route.isFirst);`,
    затем для каждой ветки shell'а `StatefulNavigationShell`:
    `shell.goBranch(i, initialLocation: true)`, затем
    `rootNavigatorKey.currentContext?.go(Routes.mainNavigator)`. Итог:
    пользователь, только что открывший экран настроек профиля и нажавший
    «Сохранить», оказывается на главной вкладке приложения — экран
    `ProfileSettingsPage`, с которого всё началось, закрыт вместе со всем
    стеком навигации.
16. Наблюдаемый пользователем итог всего сценария: интерфейс отображается на
    новом языке; ни один снекбар успеха/ошибки самого сохранения профиля не
    показан (шаг 7); вместо этого пользователь на короткое время видит
    полноэкранный `DataUpdatePage`, затем оказывается на главном экране —
    полностью вне контекста, в котором он совершил действие.

### Альтернативные потоки

- **(б) Гость.** Шаги 4–7 отличаются: `_authRepository.isAuthorized()` —
  ложно. `countryCode = newUserData.selectedCountry?.code`; если не `null` и
  не пусто — `await AppCacheService.saveGuestCountryCode(countryCode)`
  (выполняется независимо от того, менялась ли страна в этом сохранении —
  см. [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)). Далее
  `newUserData.locale != state.currentUserData?.locale` — истинно:
  `emit(state.copyWith(loading: false, isLanguageChanged: true));` — в
  отличие от ветки (а), `loading` явно сброшен в `false` здесь же, кнопка
  «Сохранить» не остаётся в состоянии загрузки. `saveChanges()` возвращает
  `false`, без единого сетевого вызова. Шаги 8–16 (весь каскад
  `LanguageBloc` → ребилды → повторный `load()` → полный ресинк → сброс
  навигации) выполняются **идентично**, включая диспатч
  `DataUpdateStartAll(resetNavigationOnSuccess: true)` — этот диспатч в
  `ProfileSettingsView`'s внешнем `BlocListener<LanguageBloc>` не проверяет
  `isAuthorized()` вовсе. Отличие по существу — шаг 12: поскольку
  `_authRepository.isAuthorized()` в момент выполнения `on<DataUpdateStartAll>`
  тоже ложно, весь `_syncAuthData` (включая `getSettingFromSHTP()`/`_suncDevices()`)
  **пропускается целиком** (`if (_authRepository.isAuthorized()) await _syncAuthData(...)`) —
  для гостя этот сценарий не читает и не пишет
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)/`Kind.visible`
  вовсе, только справочники (`loadDirectories`/`_loadBoardDirectories`).
  Гость тоже оказывается на главном экране (шаги 13–15 не зависят от
  авторизации), несмотря на то, что для него ресинк функционально ничего не
  синхронизировал, кроме публичных справочников.
- **Сеть недоступна в момент шага 10.** `on<DataUpdateStartAll>` проверяет
  `NetworkConnectivityService.hasConnection()` первым делом; если сети нет —
  `emit(DataUpdateFailure(errorTitleKey: 'internet_connection_required', errorMessageKey: 'check_connection'))`
  немедленно, без единого шага загрузки справочников или `_syncAuthData`.
  Смена самого языка (шаги 1–9) уже полностью состоялась и не откатывается —
  `LanguageService.setLocale()` уже персистировал новый язык в
  `SharedPreferences` до диспатча `DataUpdateStartAll`, интерфейс уже
  переключился. Разница с основным потоком — только в шагах 13–15: вместо
  `DataUpdateSuccess`/сброса навигации пользователь видит экран
  `DataUpdatePage` с сообщением об отсутствии сети и остаётся на нём (не
  автоматически возвращается на экран профиля) — `_isPageOpen`
  (`DataUpdatePage`) статичен, повторный вызов `.show()` из другого места до
  закрытия текущего экземпляра не откроет второй.
- **`newUserData == null`.** Если `saveChanges()` вызван до единственного
  `load()` (`state.newUserData` пуст), метод возвращает `false` сразу же,
  не доходя до проверки локали — этот сценарий вообще не наступает
  (`selectLanguage` тоже требует уже загруженного `state.newUserData`/`currentUserData`
  для построения черновика).
- **Одновременная смена языка и других полей формы (обе ветки).** Как
  отмечено на шаге 2/5 — `newUserData`, отправленный в `updateUser()` (ветка
  а) или примененный локально (ветка б, только страна), содержит **все**
  черновые изменения разом, не только `locale`. Для авторизованного это
  означает, что реальное сохранение имени/email/телефона/страны **прошло
  успешно на сервере** (шаг 5), но пользователь не получает об этом никакого
  подтверждения — ни снекбара успеха (`isSaved == false`), ни немедленного
  обновления `state.currentUserData` (обновится только на шаге 10, после
  всего каскада `LanguageBloc`).

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — поле `locale`;
  в ветке (а) реально обновляется и на сервере, и в Hive `AUTH_BOX`
  (`_saveMainAuthData`, без гарантии завершения к моменту, когда
  `saveChanges()` продолжает выполнение — см. «Открытые вопросы»); в ветке
  (б) не персистируется этим методом вовсе (сам факт смены языка
  персистирует общий для обеих веток `LanguageService.setLocale()`, в
  `SharedPreferences`, не в `User`).
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — не изменяется и не читается напрямую этим сценарием,
  но **косвенно подвергается риску** в ветке (а): полный ресинк, запущенный
  на шаге 10 этим же сценарием, безусловно выполняет
  `SettingsRepository.getSettingFromSHTP()` (pull), который перетирает
  единственную строку таблицы содержимым с сервера, тогда как push
  (`setSettingToSHTP()`) в этом сценарии не выполняется (`isUpdateData` не
  передан) — см. инвариант ENT-21 «Локальные правки могут быть молча
  перезаписаны сервером». Если пользователь ранее менял настройки
  уведомлений о вакцинации локально и ещё не синхронизировал их отдельным
  проходом с `isUpdateData: true` (кнопка «Обновить данные» на экране «В
  работе»), смена языка этим сценарием их бесследно перетрёт.
- `Kind` ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md),
  HANDBOOKS — узкая грань `visible`) — тот же риск, тем же запросом
  (`getSettingFromSHTP`/`setSettingToSHTP` — единый эндпоинт на оба факта,
  см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
- `Country` ([ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md),
  HANDBOOKS) — читается (`_countriesRepository.getAll()` внутри
  повторного `load()` на шаге 10), не изменяется этим сценарием.

### Бизнес-правила

- Смена языка — единственное условие в `saveChanges()`, которое превращает
  штатное сохранение в отдельный, не CRUD-успешный с точки зрения
  пользователя путь: `isLanguageChanged: true` вместо снекбара успеха,
  независимо от того, изменялись ли одновременно другие поля.
- Полный ресинк после смены языка (`DataUpdateStartAll(resetNavigationOnSuccess: true)`,
  без `isUpdateData`) — не часть бизнес-логики самого профиля, а побочный
  эффект, зашитый в презентационный слой (`ProfileSettingsView`'s
  `BlocListener<LanguageBloc>`), не в `ProfileEditCubit`/`LanguageBloc`
  напрямую — эти двое ничего не знают о `DataUpdateBloc`.
- `resetNavigationOnSuccess: true` — осознанный выбор именно в этом месте
  вызова (единственное место в кодовой базе, использующее `true`, по
  аналогии с тем, как `isUpdateData: true` уникален для экрана «В работе», —
  не проверено этим проходом исчерпывающе, но не найдено других вызовов
  `DataUpdateStartAll` с этим параметром при чтении `data_update_event.dart`/`main_page.dart`/`profile_settings_view.dart`/`in_work_page.dart`).
  Эффект — пользователь безусловно покидает экран настроек профиля при
  успешном ресинке, даже если он не запрашивал переход куда-либо ещё.
- Гость и авторизованный проходят один и тот же каскад `LanguageBloc` →
  ресинк → сброс навигации, хотя для гостя ресинк не выполняет ни одного
  шага, специфичного для этого модуля ([ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)/`Kind.visible`/`Device`) —
  код не различает акторов на этом уровне вовсе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе ветки (авторизованная с реальным
`PUT`, гостевая без сетевого вызова) и весь последующий каскад
(`LanguageBloc` → ребилды → повторный `load()` → `DataUpdateStartAll` →
сброс навигации) полностью прослеживаются статическим чтением
`ProfileEditCubit.saveChanges` → `ProfileSettingsView`'s двух
`BlocListener` → `LanguageBloc.on<LanguageEventChange>` →
`DataUpdateBloc.on<DataUpdateStartAll>` → `DataUpdatePage`/`routes.dart`.
Гонка вокруг неawait'ленного `_saveMainAuthData(...)` (см. «Открытые
вопросы») подтверждена чтением кода, но не воспроизведена запущенным
тестом с таймингом — это не блокер для документирования CURRENT-поведения,
поскольку сама структура кода (вызов без `await`) наблюдаема однозначно.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.selectLanguage` | CURRENT | пишет `newUserData.locale` в черновик, не трогая `currentUserData` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.saveChanges` | CURRENT | развилка (а)/(б); при расхождении `locale` эмитит `isLanguageChanged: true` вместо обычного успеха; в ветке (а) не сбрасывает `loading` этим `copyWith` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.consumeLanguageChangeFlag` | CURRENT | сбрасывает `isLanguageChanged` обратно в `false`, не трогая `loading` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | вызывается дважды в разных местах каскада (реактивная Hive-подписка кубита и явный вызов из `BlocListener<LanguageBloc>`); первое место, где `loading` возвращается в `false` после шага 6 основного потока |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit._valueListenable`/`_listener` (конструктор) | CURRENT | подписка на `getAuthBoxListenable(keys: [AuthRepository.userKey])`, вызывает `load()` при любом изменении `userKey` в Hive — независимый от каскада источник повторного `load()` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUser` | CURRENT | `PUT {authSerivceApi}/user` с полным `newUserData` (включая новый `locale`); вызывает `_saveMainAuthData(...)` **без `await`** |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._saveMainAuthData`, `.getAuthBoxListenable` | CURRENT | `box.put(userKey, ...)` (awaited внутри метода, но сам метод не awaited вызывающим `updateUser`); источник события для `_valueListenable` |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `User.toUserDTO`, `UserDTO.toJson` | CURRENT | `locale` маппится без переименования JSON-ключа |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build` — оба `BlocListener` (`ProfileEditCubit`/`LanguageBloc`) | CURRENT | внутренний — диспатчит `LanguageEventChange`; внешний — вызывает `ProfileEditCubit.load()` и диспатчит `DataUpdateStartAll(resetNavigationOnSuccess: true)` без проверки `isAuthorized()` |
| `lib/pages/language/language_bloc.dart` | `LanguageBloc.on<LanguageEventChange>` | CURRENT | `LanguageService.setLocale` → `emit(LanguageStateChanged)` |
| `lib/l10n/language_service.dart` | `LanguageService.setLocale`, `.init`, `.supportedLocales` | CURRENT | персист в `SharedPreferences` (ключ `'language'`), не проверяет ошибку записи |
| `lib/main.dart` | `MyApp.build` — `BlocBuilder<LanguageBloc, LanguageStateInitial>` | CURRENT | пересобирает `MaterialApp.router(locale: ...)` на `LanguageStateChanged`; мёртвая ветка `'sp' -> 'es'` |
| `lib/pages/board/presentation/board_page.dart`, `lib/pages/my_ads/presentation/my_ads_page.dart`, `lib/pages/profile/presentation/profile_page.dart`, `lib/pages/in_work/in_work_page.dart`, `lib/pages/favourite_ads/presentation/favourite_ads_page.dart`, `lib/pages/main/main_page.dart`, `lib/widgets/home/structure_widget.dart` | собственный `BlocListener<LanguageBloc, LanguageStateInitial>` на каждом экране | CURRENT | форсирует `setState(() {})` на `LanguageStateChanged` — избыточно по отношению к глобальному ребилду `MaterialApp.router`, реализовано отдельно на каждом экране |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | проверка сети первой; при наличии сети — `loadDirectories`/`_loadBoardDirectories`, затем, если `isAuthorized()`, `_syncAuthData` |
| `lib/blocs/data_update/data_update_event.dart` | `DataUpdateStartAll.isUpdateData` | CURRENT | дефолт `false`; комментарий в коде явно связывает `true` только с экраном «В работе» |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.getSettingFromSHTP`, `.setSettingToSHTP` | CURRENT | pull безусловный (перетирает [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)/`Kind.visible`), push — только при `isUpdateData: true`, здесь не выполняется |
| `lib/pages/main/main_page.dart` | `MainPage.build` — `BlocListener<DataUpdateBloc, DataUpdateState>` | CURRENT | `if (state is DataUpdateInProgress) DataUpdatePage.show(context)` — единственная точка навигации на `DataUpdatePage` при этом диспатче |
| `lib/pages/data_update/data_update_page.dart` | `_DataUpdatePageState.build` — `BlocConsumer` `listener` | CURRENT | на `DataUpdateSuccess` — `have_any_language`-проверка, `Navigator.pop`, ветвление `resetNavigationOnSuccess` между `resetMainShellNavigation()` и `context.go(Routes.mainNavigator)` |
| `lib/pages/routes.dart` | `resetMainShellNavigation` | CURRENT | сбрасывает весь `StatefulNavigationShell` на начальные локации всех веток и переходит на `Routes.mainNavigator` |

## Критерии приёмки

- Авторизованный пользователь меняет `locale` (с изменением или без
  изменения других полей формы) и сохраняет: `AuthRepository.updateUser`
  вызывается ровно один раз с полным `newUserData`; `saveChanges()`
  возвращает `false`; `state.isLanguageChanged` становится `true`;
  `ProfileSettingsView` не показывает снекбар успеха для этого вызова
  `saveChanges()`.
- Гость меняет `locale`: `AuthRepository.updateUser` не вызывается ни разу;
  если выбрана страна — `AppCacheService.saveGuestCountryCode` вызван;
  `saveChanges()` возвращает `false`, `state.isLanguageChanged` — `true`,
  `state.loading` — `false` сразу после этого `emit` (в отличие от
  авторизованной ветки).
- В обеих ветках — после `isLanguageChanged: true`: `LanguageBloc` получает
  `LanguageEventChange` с новым локалем; `LanguageService.locale` и
  `pref.getString('language')` равны новому значению; `LanguageBloc`
  эмитит `LanguageStateChanged` с тем же значением.
- После `LanguageStateChanged`: `ProfileEditCubit.load()` вызван (минимум
  один раз, из `BlocListener<LanguageBloc>` в `ProfileSettingsView`);
  `DataUpdateBloc` получает `DataUpdateStartAll` с
  `resetNavigationOnSuccess: true` и `isUpdateData: false` (дефолт).
- Если сеть доступна и полный ресинк завершается `DataUpdateSuccess`:
  происходит вызов `resetMainShellNavigation()`, а не
  `context.go(Routes.mainNavigator)`.
- Для авторизованного полный ресинк вызывает
  `SettingsRepository.getSettingFromSHTP()` и не вызывает
  `SettingsRepository.setSettingToSHTP()`; для гостя ни один из двух методов
  не вызывается (`_syncAuthData` пропущен целиком).

## Связанные тесты

- `test/pages/profile_edit_cubit_test.dart`, group
  `'UC-165 — ProfileEditCubit.saveChanges (гость, смена языка)'`, test
  `'locale изменился -> isLanguageChanged:true, возвращает false,
  currentUserData не тронут'` — покрывает ровно ветку (б) основного потока
  `saveChanges()` (шаги 4′–7 «Альтернативных потоков» этого use-case):
  проверяет `result == false`, `state.isLanguageChanged == true` и что
  `currentUserData` не меняется этим вызовом. Не проверяет `state.loading`
  явно и не идёт дальше самого `saveChanges()` — каскад `LanguageBloc` →
  ресинк → сброс навигации этим тестом не затрагивается (тестируется только
  `ProfileEditCubit`, без `LanguageBloc`/`DataUpdateBloc` в контексте).
- `test/pages/language_bloc_test.dart`, group
  `'UC-165 — LanguageBloc.LanguageEventChange (общий код, оба
  актора)'`, test `'LanguageEventChange -> сохраняет в pref, эмитит Changed
  с новым языком'` — покрывает шаг 9 основного потока (общий для обеих
  веток): `LanguageEventChange('fr')` → `pref` содержит
  `'fr'`, эмитится `LanguageStateChanged` с `'fr'`. Не специфичен именно для
  UC-165 (группа явно комбинирует его с другим use-case, вызывающим тот же
  код) и не проверяет ничего из последующего каскада (ребилды/ресинк/сброс
  навигации).
- `test/pages/language_bloc_test.dart`, group `'LanguageBloc.LanguageEventLoad'`
  (без номера) — не тест сценария этого use-case напрямую, но
  вспомогательное доказательство механизма `LanguageService.init()`
  (откат на `'en'` при неподдерживаемом языке, чтение платформенной локали
  при пустом `pref`), на который опирается `LanguageBloc`'s конструктор.
- `test/pages/profile_edit_cubit_test.dart`, group `'ProfileEditCubit —
  реактивная подписка'`, test `'изменение пользователя в Hive-боксе
  триггерит повторный load()'` — не тест этого use-case, но подтверждает
  сам факт существования механизма из шага 5/10 основного потока
  (`_valueListenable`/`_listener`, вызывающие `load()` при любой записи в
  `userKey`), с которым может гоняться неawait'ленный `_saveMainAuthData(...)`
  внутри `AuthRepository.updateUser`.

**TBD — теста нет** на авторизованную ветку (а) целиком: ни один тест не
кладёт `TokenDataHive`/`UserHive` в Hive-бокс **и одновременно** не вызывает
`saveChanges()` со сменой `locale` — `test/pages/profile_edit_cubit_test.dart`'s
`setUp` регистрирует реальный (не мокнутый) `AuthRepository`, реальный
сетевой `PUT` в тестовом окружении не воспроизводим без мока `ApiClient`
(см. ту же оговорку в «Связанные тесты» [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)).
**TBD — теста нет** также на: `state.loading`, остающийся `true` в ветке (а)
между шагами 6 и 10; на диспатч `DataUpdateStartAll(resetNavigationOnSuccess: true)`
из `ProfileSettingsView`'s внешнего `BlocListener<LanguageBloc>`; на
последующий вызов `resetMainShellNavigation()`; на пропуск
`_syncAuthData` для гостя в рамках именно этого каскада; на гонку между
неawait'ленным `_saveMainAuthData` и повторным `load()`. Все эти
утверждения подтверждены только статическим чтением кода в рамках этой
спеки.

## Открытые вопросы и ограничения

- **Побочный, структурно не связанный механизм с тем же
  `LanguageEventChange`: `have_any_language`.** `DataUpdateBloc.on<DataUpdateClear>`
  (вызывается при логауте) сбрасывает `pref.setBool('have_any_language', false)`.
  `DataUpdatePage`'s `listener` на **любой** `DataUpdateSuccess` (включая тот,
  что порождён этим самым use-case на шаге 13) проверяет:
  `if (!(pref.getBool('have_any_language') ?? false)) { pref.setBool('have_any_language', true); context.read<LanguageBloc>().add(LanguageEventChange(LanguageService.locale)); }` —
  если это первый успешный полный ресинк с момента последнего логаута
  (флаг ещё не выставлен), диспатчится **ещё один** `LanguageEventChange`,
  на этот раз с уже текущим (только что изменённым в этом же сценарии, шаг
  9) `LanguageService.locale` — то есть без фактической смены языка,
  исключительно чтобы повторно форсировать `emit(LanguageStateChanged)` и
  тем самым триггернуть `setState()` на экранах из шага 10, которые могли
  не пересобраться сами. Комментарий в коде — `/// Чтобы обновились экраны`.
  Практическое пересечение с этим use-case: если пользователь меняет язык
  при первом с момента логина полном ресинке (`have_any_language` ещё
  `false`), сценарий этого UC сам порождает второй, избыточный проход через
  `LanguageBloc.on<LanguageEventChange>` (шаг 9 повторяется с тем же
  значением) — безвредно с точки зрения данных, но ещё раз демонстрирует,
  что `LanguageEventChange` используется в кодовой базе как общий
  «форсировать ребилд подписанных экранов» примитив, а не только как
  «пользователь реально сменил язык».
- **Гонка вокруг неawait'ленного `_saveMainAuthData(...)` внутри
  `AuthRepository.updateUser` (найдено при чтении кода для этой спеки, не
  упомянуто явно в [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)).**
  `updateUser()` вызывает `_saveMainAuthData(...)` без `await`, поэтому
  `saveChanges()` продолжает выполнение (проверка `newUserData.locale !=
  state.currentUserData?.locale` на шаге 6) не дожидаясь гарантированного
  завершения `box.put(userKey, ...)`. Одновременно `ProfileEditCubit`'s
  собственная `_valueListenable`-подписка на тот же ключ вызовет `load()`
  автоматически, как только (и если) эта фоновая запись реально
  завершится — в момент времени, не синхронизированный с явным вызовом
  `load()` на шаге 10 (который выполняется намного позже, после полного
  прохода `LanguageBloc`/`SharedPreferences`). Оба вызова `load()` в итоге
  делают одно и то же (пересобирают `ProfileEditState` из канонического
  состояния), так что практический эффект гонки, по всей видимости,
  ограничивается лишним пересозданием состояния кубита, а не потерей
  данных — но это не проверено ни статическим анализом иного рода, ни
  тестом с реальным таймингом Hive; является ли отсутствие `await` здесь
  осознанным решением (fire-and-forget персиста, чтобы не блокировать UI) —
  ничем в коде/комментариях не зафиксировано.
- **Отсутствие обратной связи пользователю о судьбе сопутствующих полей
  формы.** Как отмечено в «Альтернативных потоках», если пользователь в
  ветке (а) одновременно с языком поменял, например, имя — оно реально
  сохраняется на сервере (шаг 5), но пользователь не видит об этом ни
  снекбара, ни какого-либо другого немедленного сигнала; экран, который
  показал бы обновлённое имя (после `load()` на шаге 10), к этому моменту
  уже заменён на `DataUpdatePage`, а затем на главный экран (шаг 15) —
  пользователь физически не возвращается на экран профиля, чтобы это
  увидеть, если только не откроет его заново.
- **`state.loading`, зависший в `true` в ветке (а).** Между шагами 6 и 10
  кнопка «Сохранить» показывает `isLoading: true`, хотя сам `saveChanges()`
  уже вернул управление вызывающему коду — визуально это неотличимо от
  «сохранение всё ещё идёт», хотя по факту идёт совсем другой,
  внешний по отношению к `ProfileEditCubit` процесс (каскад `LanguageBloc`).
  К моменту, когда пользователь мог бы это заметить, экран уже, как
  правило, покрыт `DataUpdatePage` (шаг 11) — не проверено, насколько это
  реально заметно пользователю на практике, только то, что код это
  допускает.
- **Сброс навигации на главный экран — не запрошенное пользователем
  поведение.** Пользователь нажал «Сохранить» на экране настроек профиля;
  итогом (в happy path, при наличии сети) является перемещение на главную
  вкладку приложения, а не возврат на тот же экран профиля с уже
  переведённым интерфейсом. Является ли это осознанным продуктовым
  решением (чтобы гарантированно показать пользователю уже
  ресинхронизированные данные с чистого «домашнего» состояния) или
  побочным эффектом того, что `resetNavigationOnSuccess: true` было
  скопировано из другого сценария использования `DataUpdateStartAll`, —
  ничем в коде/комментариях не зафиксировано.
