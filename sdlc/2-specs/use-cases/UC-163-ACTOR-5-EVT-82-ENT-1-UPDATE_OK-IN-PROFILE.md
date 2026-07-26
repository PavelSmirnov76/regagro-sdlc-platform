# UC-163 — Сохранение профиля без смены языка: реальный PUT для авторизованного, локальный кэш страны для гостя

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь правит имя/email/телефон/страну на экране `ProfileSettingsPage`
и нажимает «Сохранить» — `ProfileEditCubit.saveChanges()` — среди изменённых
полей нет `locale`, и сетевой/локальный вызов завершается без исключения.
Тот же метод и то же событие обслуживают две структурно разные, но обе
штатно успешные ветки, каждая проверена независимо чтением кода:

- (а) **авторизованный** — реальный `PUT {authSerivceApi}/user` через
  `AuthRepository.updateUser(newUserData)`, ответ сервера перезаписывает
  Hive-снимок пользователя;
- (б) **гость** — без единого сетевого вызова: только
  `AppCacheService.saveGuestCountryCode()` (локально, `SharedPreferences`) и
  обновление `state.currentUserData` в памяти кубита.

Смена языка в рамках того же нажатия «Сохранить» — отдельный сценарий
([EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md)), не описываемый
здесь. Технический отказ сетевого вызова в ветке (а) —
[UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
независимо от статуса авторизации: экран `ProfileSettingsPage` (компонент
`ProfileSettingsView`) не имеет route-guard'а и доступен и гостю (кубит
создаётся с `loadGuestSettings: true`), и авторизованному пользователю
одинаковым кодом.

## CURRENT

### Основной поток

Основной поток — ветка (а), авторизованный пользователь, поскольку именно
она реально изменяет [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) как
серверную сущность.

1. Пользователь редактирует одно или несколько полей через `RTextField.outline`/`PhoneWidget`/`CountryDropdownField`
   в `_ProfileSettingsContactDetails`/`_ProfileSettingsRegionAndLanguage`
   (`profile_settings_view.dart`) — каждый `onChanged`/`onSelected` вызывает
   один из методов `ProfileEditCubit`: `editFirstName` (поле «Имя» —
   `l10n.first_name`, пишет в `UserModel.name`), `editEmail`, `editPhone`,
   `selectCountryCode`, `selectCountry`. Каждый метод строит новый
   `newUserData` через `state.newUserData?.copyWith(...) ?? state.currentUserData?.copyWith(...)`
   и эмитит `state.copyWith(newUserData: newUserData)` — `state.currentUserData`
   не меняется до сохранения.
2. `state.isDataChanged` (`ProfileEditStateExtension`) становится `true` —
   сравнивает `currentUserData`/`newUserData` по всем полям `UserModel`
   (включая `firstName`/`lastName`/`patronymic`/`organizationId`/`organization`/`permissions`/`roles`,
   которые этот кубит никогда не пишет и которые поэтому остаются равны).
   Кнопка «Сохранить» (`BlackCircleButton`, `Positioned` внизу экрана)
   становится видимой.
3. Пользователь нажимает «Сохранить»: `onTap` вызывает `await context.read<ProfileEditCubit>().saveChanges()`.
4. `saveChanges()`: `emit(state.copyWith(loading: true))` — кнопка переходит
   в `isLoading: true`. `newUserData = state.newUserData` — непусто.
   `_authRepository.isAuthorized()` — истинно.
5. `await _authRepository.updateUser(newUserData);`:
   - `_userDataForUpdate(user)` — `formattedPhone = formatPhoneNumber(user.phone ?? '', user.phoneNumberCode ?? '')`;
     `data = user.copyWith(phone: formattedPhone).toUserDTO().toJson()`; если
     `formattedPhone` пуст — `data['phone']`/`data['phone_number_code']`/`data['phone_country_iso_code']`
     обнуляются явно. `User.toUserDTO()` маппит `lastName` в `UserDTO.secondName`
     (JSON-ключ `second_name`) — это поле в данном сценарии никогда не
     редактируется (`editFirstName` пишет только в `name`), поэтому в запросе
     передаётся то значение `lastName`, что уже было у пользователя, без
     изменений.
   - `rpcClientSHTP = getIt.get<ApiClient>(instanceName: 'farm_rpc')`;
     `message = ApiMessage(link: '${Constants.authSerivceApi}/user', method: ApiMethod.put, data: userData)`;
     `response = await rpcClientSHTP.call(message)` завершается без
     исключения (в отличие от [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md)).
   - `userJson = response['data'] as Map<String, dynamic>` — успешно
     приводится (ключ `data` присутствует).
   - `_normalizeUserPhoneFields(userJson)` — пересобирает `phone`/`phone_number_code`/`phone_country_iso_code`
     из «сырых» цифр ответа сервера (см. [ENT-1](../entities/ENT-1-USER-IN-AUTH.md),
     логика описана также в [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md)'s
     техническая таблица).
   - `_saveMainAuthData(user: UserDTO.fromJson(userJson), updateServerIntegrations: false)` —
     `box.put(userKey, user.toUserHive())` в Hive `AUTH_BOX`; поскольку
     `updateServerIntegrations: false`, ключ `serverIntegrationsKey` и
     `AppCacheService.saveIntegrationDirection()` этим вызовом **не
     трогаются** (в отличие от `login()`, где они переписываются) — правка
     профиля затрагивает исключительно Hive-снимок самого `User`.
6. Обратно в `saveChanges()`: `newUserData.locale != state.currentUserData?.locale` —
   ложно (сценарий этого use-case — без смены языка).
7. `else`-ветка: `await load();` — перезапрашивает `PackageInfo`, `_countriesRepository.getAll()`
   и `_authRepository.getUser()!` (уже перезаписанный на шаге 5), заново
   строит `currentUserData`/`newUserData` из этого канонического
   серверного снимка (а не из локально-оптимистичного `newUserData` до
   сохранения) и эмитит `ProfileEditState(currentUserData: ..., newUserData: ..., loading: false, countries: ..., appVersion: ...)`.
8. `saveChanges()` возвращает `true`.
9. `onTap` в `ProfileSettingsView`: `if (context.mounted && isSaved) { showAppSnackBarSuccess(context, l10n.profile_settings__successfully_saved); }` —
   пользователь видит snackbar успеха; кнопка «Сохранить» скрывается, если
   `state.isDataChanged` стало `false` (обычно так и есть, поскольку `load()`
   заново уравнял `currentUserData`/`newUserData`).

### Альтернативные потоки

- **(б) Гость — без сетевого вызова, только локальный кэш страны.**
  `_authRepository.isAuthorized()` — ложно; ветка требует
  `loadGuestSettings: true` (иначе `load()` вообще не строит
  `currentUserData` и экран уходит в `LoginView`, `profile_page.dart`) —
  `ProfileSettingsView` всегда создаёт кубит именно так
  (`ProfileEditCubit(loadGuestSettings: true)`).
  1. `countryCode = newUserData.selectedCountry?.code`; если не `null` и не
     пусто — `await AppCacheService.saveGuestCountryCode(countryCode)`
     (`pref.setString('_guestCountryCodeKey', countryCode)` +
     `guestCountryCodeNotifier.value = countryCode`) — единственная строка,
     реально персистируемая где-либо для гостя. Выполняется практически
     всегда (`_getSavedOrSystemCountry` почти никогда не возвращает `null`),
     независимо от того, менял ли пользователь именно страну.
  2. `newUserData.locale == state.currentUserData?.locale` (без смены языка) →
     `emit(state.copyWith(loading: false, currentUserData: newUserData, newUserData: newUserData)); return true;`
  3. `onTap` показывает тот же snackbar успеха — с точки зрения
     пользователя гостевой и авторизованный успех неотличимы.
  4. **Находка (не тестируется, подтверждена чтением `load()`):** правки
     `name`/`email`/`phone` для гостя сохраняются **только в памяти
     текущего экземпляра кубита** (`state.currentUserData`) — ни в Hive, ни
     в `SharedPreferences` для этих трёх полей ничего не пишется. Метод
     `load()` для гостя (`!_authRepository.isAuthorized()` и
     `_loadGuestSettings == true`) **безусловно** пересобирает
     `currentUserData` заново с `name: ''`, `email: ''` (и без `phone` —
     остаётся `null`), беря из персистентного состояния только страну
     (`_getSavedOrSystemCountry`, читает `AppCacheService.getGuestCountryCode()`
     либо системную локаль). Поэтому при любом повторном вызове `load()` —
     минимум при пересоздании `ProfileEditCubit(loadGuestSettings: true)`,
     что происходит каждый раз, когда `ProfileSettingsView`'s
     `BlocProvider.create` строится заново (например, уход с экрана
     настроек профиля и возврат на него) — только что сохранённые гостем
     имя/email/телефон бесследно исчезают, снова становясь пустыми, при
     этом сама операция `saveChanges()` перед этим вернула `true` и
     показала пользователю snackbar успеха. Единственное поле, которое
     реально переживает пересоздание кубита — страна (через
     `AppCacheService.saveGuestCountryCode`/`getGuestCountryCode`).
- **Техническая ошибка сетевого вызова (ветка а).** Исключение из
  `rpcClientSHTP.call` (сеть недоступна, не-2xx, `TypeError` при отсутствии
  ключа `data` в ответе) — отдельный use-case,
  [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md).
- **Смена языка (обе ветки).** Если `newUserData.locale != state.currentUserData?.locale`,
  метод не завершает обычным успехом ни для (а), ни для (б) — эмитит
  `isLanguageChanged: true` и возвращает `false` — [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md),
  не этот use-case.
- **`newUserData == null`.** Если `state.newUserData` пуст (`saveChanges()`
  вызван до единственного `load()`), метод возвращает `false` сразу же
  (`if (newUserData == null) return false;`), не доходя ни до одной из двух
  описанных здесь веток.
- **Значимые для сравнения поля `UserModel`, которые этот экран никогда не
  пишет.** `firstName`/`lastName`/`patronymic`/`organizationId`/`organization`/`permissions`/`roles`
  участвуют в `isDataChanged`, но ни один метод `ProfileEditCubit` их не
  меняет — `editFirstName`/`editName` пишут исключительно в `name`,
  оставляя отдельное поле `firstName` (существующее в
  [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)) нетронутым в этом сценарии.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — в ветке (а)
  реально обновляется и на сервере (`PUT .../user`), и локально
  (Hive `AUTH_BOX`, ключ `userKey`, через `_saveMainAuthData`); в ветке (б)
  не читается и не пишется вовсе — гостевой `currentUserData` (`id: 0`) не
  соответствует ни одной персистентной записи `User`, это чисто
  клиентский конструктор для UI.
- `Country` ([ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md), HANDBOOKS) —
  читается (`_countriesRepository.getAll()`, вызывается внутри `load()`,
  не внутри `saveChanges()` напрямую) для отображения и валидации выбора
  страны; не изменяется этим сценарием ни в одной ветке. Гостевой код страны
  (`selectedCountry.code`) — единственное поле, которое ветка (б) реально
  персистирует, через отдельный ключ `SharedPreferences`
  (`AppCacheService.saveGuestCountryCode`), не через саму таблицу `Country`.

### Бизнес-правила

- `editName` и `editFirstName` пишут в одно и то же поле `UserModel.name` —
  в UI используется только `editFirstName` (`_ProfileSettingsContactDetails`),
  `editName` не вызывается ни из одного экрана.
- Для авторизованного `updateUser()` вызывается с `updateServerIntegrations: false` —
  этим сценарием не переписывается `serverIntegrationsKey`/интеграционное
  направление, только сам `User`.
- Клиентская валидация полей формы (обязательность, формат email/телефона)
  отсутствует полностью: `ProfilePage`/`_ProfilePageState` объявляет
  `final GlobalKey<FormState> _formKey = GlobalKey<FormState>();` и передаёт
  его в `ProfileView(formKey: _formKey, state: state)`, но
  `ProfileView.build` не оборачивает ничего в `Form(key: formKey, ...)` и
  нигде не вызывает `formKey.currentState?.validate()` — поле объявлено и
  передано, но не используется вовсе. При этом сама реальная форма
  редактирования — `_ProfileSettingsContactDetails` в
  `profile_settings_view.dart` (три `RTextField.outline` для имени, телефона,
  email) — это **другое** дерево виджетов, вообще не связанное с этим
  `formKey`: там нет ни `Form`, ни единого `validator:`, переданного в
  `RTextField.outline` (хотя виджет поддерживает `validator` как параметр).
  Итог — сохранение полностью полагается на ответ сервера; единственная
  клиентская проверка перед показом кнопки «Сохранить» — `state.isDataChanged`
  (хоть что-то изменилось), не формат/обязательность конкретных полей.
- Успех для гостя (ветка б) и успех для авторизованного (ветка а) неотличимы
  для пользователя (один и тот же snackbar), хотя по факту различаются
  принципиально: для авторизованного меняется реальная серверная сущность
  [ENT-1](../entities/ENT-1-USER-IN-AUTH.md), для гостя — временное
  in-memory состояние плюс один персистентный ключ (код страны).

## TARGET

TARGET не отличается от CURRENT. Отсутствие клиентской валидации формы и
потерю несохранённых гостевых полей при пересоздании кубита этот
документирующий проход фиксирует как факт существующего кода, не устраняет.

## TBD / BLOCKED

Блокеров для документирования нет — обе ветки (авторизованная с реальным
`PUT`, гостевая с локальным кэшем страны) полностью прослеживаются
статическим чтением `ProfileEditCubit.saveChanges` →
`AuthRepository.updateUser`/`AppCacheService.saveGuestCountryCode`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.saveChanges` | CURRENT | развилка авторизован/гость, вызывает `updateUser` либо `saveGuestCountryCode`, решает про `isLanguageChanged` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.editName`, `.editFirstName`, `.editEmail`, `.editPhone`, `.selectCountryCode`, `.selectCountry` | CURRENT | пишут черновик `state.newUserData`; `editName`/`editFirstName` пишут одно и то же поле `name` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | для авторизованного — строит `currentUserData` из `_authRepository.getUser()`; для гостя — безусловно пересобирает `name: ''`, `email: ''`, сохраняя только страну |
| `lib/pages/profile/cubit/profile_edit_state.dart` | `ProfileEditStateExtension.isDataChanged` | CURRENT | управляет видимостью кнопки «Сохранить» |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUser`, `._userDataForUpdate`, `._normalizeUserPhoneFields`, `._saveMainAuthData` | CURRENT | реальный `PUT {authSerivceApi}/user`, разбор ответа, запись в Hive с `updateServerIntegrations: false` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.saveGuestCountryCode`, `.getGuestCountryCode` | CURRENT | единственная персистируемая часть гостевого сохранения — код страны в `SharedPreferences` |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `User.toUserDTO`, `UserDTO.toJson`, `UserDTO.fromJson` | CURRENT | доменная модель/DTO, `lastName` → `secondName`/`second_name` |
| `lib/pages/profile/data/user_model.dart` | `UserModel`, `UserModel.copyWith` | CURRENT | форма `User` с добавленным `selectedCountry`, используемая кубитом как черновик и как текущее значение |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build`, `_ProfileSettingsContactDetails` | CURRENT | единственный вызывающий код кнопки «Сохранить»; поля формы без `Form`/`validator` |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState._formKey` | CURRENT | объявлен и передан в `ProfileView`, нигде не используется |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build` | CURRENT | принимает `formKey`, не оборачивает содержимое в `Form`, не содержит полей редактирования вовсе (редактирование физически на другом экране) |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getAll` | CURRENT | источник списка стран, используемый обеими ветками |

## Критерии приёмки

- Авторизованный пользователь: после `saveChanges()` без смены `locale` —
  `AuthRepository.updateUser` вызван ровно один раз с данными
  `state.newUserData`; Hive `AUTH_BOX`/`userKey` содержит ответ сервера
  (не локально-оптимистичные данные); `saveChanges()` возвращает `true`;
  `state.currentUserData` после последующего `load()` равен пересобранному
  из свежего `_authRepository.getUser()`.
- Гость: после `saveChanges()` без смены `locale` — `AuthRepository.updateUser`
  не вызывается ни разу; если `newUserData.selectedCountry?.code` не пусто —
  `AppCacheService.saveGuestCountryCode` вызван с этим кодом; `saveChanges()`
  возвращает `true`; `state.currentUserData` немедленно (без отдельного
  `load()`) становится равен `newUserData`.
- Гость: если после успешного `saveChanges()` вызывается `load()` заново
  (в частности — через пересоздание `ProfileEditCubit(loadGuestSettings: true)`),
  `state.currentUserData?.name` и `state.currentUserData?.email` возвращаются
  к пустой строке независимо от того, что было сохранено предыдущим вызовом
  `saveChanges()`; `state.currentUserData?.selectedCountry`/`countryId`
  восстанавливается из `AppCacheService.getGuestCountryCode()`.
- В обеих ветках `state.isLanguageChanged` остаётся `false` (сценарий этого
  use-case не включает смену `locale`).
- `ProfileView.build` не строит ни одного `Form`-виджета с `key: formKey` — 
  `_ProfilePageState._formKey` не участвует ни в одной валидации.

## Связанные тесты

- `test/pages/profile_edit_cubit_test.dart`, group `'UC-163 — ProfileEditCubit.saveChanges (гость, без смены языка)'`,
  test `'locale не менялся -> сохраняет как currentUserData, возвращает true'` —
  покрывает ровно ветку (б) основного потока этого use-case: гость,
  `editName` меняет `name`, `saveChanges()` возвращает `true`,
  `currentUserData?.name` обновлён.
- `test/pages/profile_edit_cubit_test.dart`, group `'ProfileEditCubit — редактирование'`,
  test `'editName/editEmail/editPhone обновляют newUserData поверх currentUserData'` —
  покрывает шаг 1 основного потока (черновик редактирования) для гостевого
  контекста; авторизованный вызов тех же методов отдельно не тестируется, но
  логика методов не зависит от `isAuthorized()`.
- `test/pages/profile_edit_cubit_test.dart`, group `'ProfileEditCubit — остальные редакторы полей'`,
  test `'editFirstName/selectCountryCode/selectCountry/selectLanguage'` —
  единственный тест, явно проверяющий и комментирующий, что `editFirstName`
  пишет в то же поле `name`, что и `editName` (`reason: 'editFirstName пишет
  в то же поле name, что и editName'`).
- **Ни один тест не покрывает авторизованную ветку `saveChanges()` (вызов
  `AuthRepository.updateUser`).** Подтверждено чтением всего файла
  `test/pages/profile_edit_cubit_test.dart`: `setUp` регистрирует в `getIt`
  реальный `AuthRepository()` (не мок) поверх Hive-тестового бокса и
  `MockCountriesRepository`; ни один `test()` во всём файле не кладёт
  `TokenDataHive`/`UserHive` в бокс **и одновременно** не вызывает
  `saveChanges()` — группа `'UC-161 — ProfileEditCubit.load (авторизован)'`
  проверяет только `load()`, группы `'UC-163'`/`'UC-165'` вызывают
  `saveChanges()` только для гостя (`loadGuestSettings: true`, без токена в
  боксе). `Talker` также не зарегистрирован в `getIt` ни в одном `setUp` —
  реальный вызов `AuthRepository.updateUser()` в тестовом окружении обратился
  бы к сети без мока и, скорее всего, упал бы до `getIt<Talker>().handle(e)`
  (тоже незарегистрированного), что дополнительно подтверждает: авторизованная
  ветка `saveChanges()` (ни успешная, ни отказная) сегодня физически не может
  быть покрыта этим тестовым файлом без добавления мока `AuthRepository`.

**TBD — теста нет** на авторизованную ветку основного потока (ветка а
целиком: `AuthRepository.updateUser` возвращает успех, Hive перезаписывается,
`load()` вызывается повторно) и на находку про потерю гостевых
`name`/`email`/`phone` при пересоздании кубита (ветка б, шаг 4 «Альтернативных
потоков») — оба утверждения подтверждены только статическим чтением кода.

## Открытые вопросы и ограничения

- **Находка (не дефект в терминах ошибки, а архитектурное несоответствие
  ожиданиям пользователя).** Успешное сохранение имени/email/телефона гостем
  показывает тот же snackbar успеха, что и у авторизованного, но фактически
  персистирует только код страны. Является ли это осознанным продуктовым
  решением («гость и так временный, хранить его имя незачем») или
  недосмотром (ожидалось, что `UserModel` гостя тоже переживёт пересоздание
  экрана, например через `SharedPreferences`/Hive без токена) — ничем в
  коде/комментариях не зафиксировано.
- **`formKey`/`GlobalKey<FormState>` в `ProfilePage`/`ProfileView` — мёртвый
  код, structurally отделённый от реального экрана редактирования.**
  `ProfileView` (куда он передаётся) вообще не содержит текстовых полей —
  редактирование происходит в `ProfileSettingsView`/`ProfileSettingsPage`,
  отдельном дереве виджетов без единого `Form`. Неясно, был ли `formKey`
  когда-то частью экрана редактирования и остался после переноса полей на
  `ProfileSettingsPage`, либо это черновик, оставленный для будущей
  валидации, так и не подключённый.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод по ветке (а) сделан статическим чтением
  `ProfileEditCubit.saveChanges` → `AuthRepository.updateUser` →
  `CustomDioClient.call`, без запущенного теста, подтверждающего именно
  успешный ответ сервера с ключом `data` (см. «Связанные тесты» — TBD).
