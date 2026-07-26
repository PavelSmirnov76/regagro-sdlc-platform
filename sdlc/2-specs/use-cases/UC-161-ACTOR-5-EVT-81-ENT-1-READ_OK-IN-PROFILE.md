# UC-161 — Пользователь открывает вкладку «Профиль» и видит текущие данные аккаунта (или экран входа, если это гость)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь (гость или авторизованный — маршрут `/profile` без
route-guard) открывает вкладку «Профиль» нижней навигации. В коде это на
самом деле **два независимых, последовательно вложенных механизма**, не
один:

1. `ProfilePage` создаёт `ProfileEditCubit()..load()` (обычным конструктором,
   `loadGuestSettings: false` по умолчанию) — он решает, показывать ли
   `LoginView` (гость) или содержимое профиля (авторизованный), и это
   единственное место, где решение «гость/авторизован» реально
   принимается для этого экрана.
2. Только если гейт пройден (`currentUserData != null`, т.е. пользователь
   авторизован), рендерится `ProfileView`, которая создаёт **свой,
   отдельный** `ProfileBloc()..add(ProfileEventStart())` — именно он
   резолвит имя/страну для отображения на экране.

Из этого следует нетривиальный факт, подтверждённый чтением кода и
единственным местом конструирования каждого класса в проекте
(`grep -rn "ProfileView(\|ProfileBloc(" lib/`): `ProfileBloc` **никогда не
создаётся для гостя** в реальной навигации — гость гарантированно
перехватывается гейтом `ProfileEditCubit` на шаг раньше. Собственная ветка
`ProfileBloc` «нет пользователя → `user: null`» (которую покрывает группа
тестов `'ProfileBloc.Start — гость'`) технически существует и корректно
работает в изоляции, но **структурно недостижима** из живой навигации
`/profile` — см. «Альтернативные потоки» и по духу параллель с
[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) (там —
недостижимый технический путь ошибки; здесь — недостижимая ветка внутри
`READ_OK`, тот же приём верификации: подтверждено фактическим единственным
местом вызова конструктора, а не предположением).

Событие [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) описывает
эффект («гость видит `LoginView`, авторизованный — данные») как единый
факт под общей причиной `ProfileBloc.on<ProfileEventStart>` — это описание
верно для наблюдаемого результата, но неточно как причинно-следственная
цепочка: причина показа `LoginView` — `ProfileEditCubit`, не `ProfileBloc`.
Не редактируется (частота фиксации — заморожен), фиксируется здесь как
факт для CURRENT.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость или авторизованный, один и тот же код на входе
(`ProfileEditCubit.load()` ветвится по `_authRepository.isAuthorized()`
внутри себя, не через route-guard).

## CURRENT

### Основной поток

1. Пользователь нажимает вкладку «Профиль» нижней навигации
   (`NavBar._NavBarButton` с `label: l10n.profile`, `iconAsset:
   Assets.personFill`, `lib/widgets/bottom_app_bar/nav_bar.dart`) →
   переход на индекс 4, маршрут `Routes.profile` (`'/profile'`), строится
   `ProfilePage` (`lib/pages/profile/presentation/profile_page.dart`).
2. `_ProfilePageState.build` оборачивает страницу в `MultiBlocListener`
   (реагирует на `LanguageBloc`/`AuthBloc`, не влияет на чтение данных
   профиля) и создаёт `BlocProvider(create: (context) =>
   ProfileEditCubit()..load())` — конструктор без аргументов,
   `loadGuestSettings` остаётся `false` по умолчанию.
3. `ProfileEditCubit.load()` (`lib/pages/profile/cubit/profile_edit_cubit.dart`):
   `emit(state.copyWith(loading: true))`; `await
   PackageInfo.fromPlatform()`; `await _countriesRepository.getAll()`
   (`CountriesRepository.getAll` — `BaseRepository.getAll` → `dao.getAll()`,
   вся локальная таблица `Countries`, без фильтра).
4. Пользователь авторизован (`_authRepository.isAuthorized()` →
   `getMainTokenData() != null` — истинно): `user =
   _authRepository.getUser()!`; `selectedCountry =
   _getSelectedCountry(countries, user)` — сначала ищет страну по
   `int.tryParse(user.countryId ?? '')` среди `countries`, при неудаче — по
   совпадению `country.code.toUpperCase() ==
   user.phoneCountryIsoCode?.toUpperCase()`; `selectedLanguage =
   LanguageService.locale`; `currentUserData =
   UserModel.fromUser(user, selectedCountry, selectedLanguage)`; `emit(
   ProfileEditState(currentUserData: currentUserData, newUserData:
   currentUserData, loading: false, countries: countries, appVersion:
   appVersion))`.
5. `ProfilePage`'s `BlocBuilder<ProfileEditCubit, ProfileEditState>`:
   `state.loading` — `false`, `state.currentUserData` — не `null` → рендер
   `ProfileView(formKey: _formKey, state: state)`
   (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`).
6. `ProfileView.build` **не использует** ни `formKey`, ни свой аргумент
   `state` (типа `ProfileEditState`, тот самый, только что построенный
   шагом 4) нигде в теле метода — оба объявлены как обязательные поля
   конструктора, но не читаются далее (см. «Открытые вопросы»). Вместо
   этого `build` создаёт независимый `BlocProvider(create: (context) =>
   ProfileBloc()..add(ProfileEventStart()))`.
7. `ProfileBloc.on<ProfileEventStart>` (`lib/pages/profile/profile_bloc.dart`):
   `user = _authRepository.getUser()` (второй, независимый вызов того же
   метода, что и шаг 4); `packageInfo = await
   PackageInfo.fromPlatform()` (второй независимый вызов); `countries =
   await _countriesRepository.getAll()` (второй независимый вызов той же
   таблицы). Резолв `countryName`: сначала по `int.tryParse(user.countryId
   ?? '')` среди `countries` (совпадение по `c.id`), при неудаче — по
   `c.code.toUpperCase() == user.phoneCountryIsoCode?.toUpperCase()` —
   логика поиска буквально повторяет `ProfileEditCubit._getSelectedCountry`
   (шаг 4), реализована второй раз независимо, с другим типом результата
   (`String countryName`, а не `Country? selectedCountry`).
8. `emit(ProfileInitial(user: user, appVersion: appVersion, countryName:
   countryName))`.
9. `ProfileView`'s внутренний `BlocBuilder<ProfileBloc, ProfileState>`:
   `state.user?.name`, `state.countryName`, `state.appVersion`
   отображаются в `ProfilePageWrapper` (заголовок, кнопка-шестерёнка →
   `Routes.profileSettings`) — блок с именем/страной, кнопки «Избранное»/
   «Сообщения»/«Мои объявления» (видны только при
   `BoardChatAvailabilityCubit == true`, см.
   [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md)-связанный
   [UC-157](UC-157-ACTOR-3-EVT-79-ENT-4-READ_OK-IN-BOARD.md)/[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)),
   «В работе» (`Routes.inWork`), «Настройки работы»
   (`Routes.workSettings`), контакты поддержки (email/Telegram) и
   `l10n.app_version: ${state.appVersion}`, кликабельный при включённом
   `DeveloperModeBloc` для открытия `TalkerScreen`.

### Альтернативные потоки

- **Гость.** `_authRepository.isAuthorized()` — ложно на шаге 4; так как
  `ProfileEditCubit` сконструирован без `loadGuestSettings: true` (шаг 2),
  ветка `if (!_loadGuestSettings)` истинна: `emit(ProfileEditState(loading:
  false, countries: countries, currentUserData: null, newUserData: null,
  appVersion: appVersion))`. `ProfilePage`'s `BlocBuilder`:
  `state.currentUserData == null` → `return const LoginView();`
  (`lib/pages/profile/presentation/widgets/login/login_view.dart`, форма
  email/пароль + переход на регистрацию) — `ProfileView`, а значит и
  `ProfileBloc`, **не строится вовсе**. Собственная «гостевая» ветка
  `ProfileBloc.on<ProfileEventStart>` (`user == null` → `countryName`
  остаётся `''`, без единого вызова `_countriesRepository.getAll()` —
  `verifyNever` в тесте) реализована и корректна как изолированный
  юнит, но не достижима ни с одной точки навигации: подтверждено чтением —
  `ProfileView` конструируется ровно один раз в проекте
  (`profile_page.dart:68`), только внутри ветки `currentUserData != null`;
  `ProfileBloc` конструируется ровно один раз в проекте
  (`profile_view.dart:35`), только внутри `ProfileView.build`. Нет
  никакого другого маршрута/виджета, инстанцирующего `ProfileBloc`
  напрямую.
- **Реактивная перезагрузка при изменении пользователя в Hive —
  дублируется в обоих механизмах одновременно.** И `ProfileEditCubit`, и
  `ProfileBloc` независимо подписываются на **один и тот же**
  `ValueListenable<Box>` — `_authRepository.getAuthBoxListenable(keys:
  [AuthRepository.userKey])` — каждый в своём конструкторе, и каждый
  реагирует по-своему: `ProfileEditCubit._listener` вызывает `load()`
  повторно (пересобирает весь `ProfileEditState`, в т.ч. заново решает
  гейт гость/авторизован); `ProfileBloc._listener` вызывает `add(
  ProfileEventStart())` повторно (пересобирает `countryName`/`user`
  независимо). Если оба виджета одновременно смонтированы (т.е.
  пользователь уже авторизован и стоит на `/profile`, а `userKey`
  меняется — например, логин/логаут в другой вкладке того же процесса) —
  срабатывают оба слушателя, `countriesRepository.getAll()` и
  `authRepository.getUser()` каждый вызываются по два раза подряд
  (по одному на механизм), без какой-либо координации между ними.
- **Мгновенное первое построение `ProfileBloc` до завершения его
  `on<ProfileEventStart>`.** `ProfileState` объявляет единственный
  подкласс — `ProfileInitial` (`part 'profile_state.dart'`); и
  конструктор (`super(const ProfileInitial())`, поля по умолчанию
  `user: null, appVersion: '', countryName: ''`), и состояние после
  обработки события (шаг 8) — оба одного типа. Проверка `if (state is!
  ProfileInitial) { return CustomLottieLoader(); }`
  (`profile_view.dart`) поэтому **никогда не истинна** — реального
  индикатора загрузки для этой внутренней подписки нет: на кадре(-ах)
  между построением `ProfileBloc` и завершением его `await
  PackageInfo.fromPlatform()`/`await
  _countriesRepository.getAll()` пользователь видит пустое имя, пустую
  страну и пустую версию приложения (дефолтные значения конструктора),
  которые сменяются реальными данными без какого-либо визуального
  перехода/лоадера.
- **Экран `/profile_settings` (`ProfileSettingsPage` →
  `ProfileSettingsView`) — второй, отдельный «просмотр текущих данных
  профиля»**, доступный по кнопке-шестерёнке из `ProfilePageWrapper`.
  Строит `ProfileEditCubit(loadGuestSettings: true)..load()` — **другой
  экземпляр кубита, с другим значением флага конструктора**, чем на
  `/profile`. Для гостя здесь `_loadGuestSettings == true`, поэтому шаг 3
  идёт по другой ветке: строится синтетический `currentUserData =
  UserModel(id: 0, name: '', email: '', countryId:
  selectedCountry?.id.toString(), locale: LanguageService.locale, …)` —
  гость получает предзаполненную форму редактирования (страна — по
  сохранённому `AppCacheService.getGuestCountryCode()` или системной
  локали), а не `LoginView`. Это тот же класс/метод
  (`ProfileEditCubit.load`), что и в основном потоке, но принципиально
  другой наблюдаемый факт для гостя — см. «Открытые вопросы»: не
  описывается этим use-case как единый сценарий с `/profile`, только
  фиксируется как связанная, но отдельная поверхность одного и того же
  события. `if (AppCacheService.isAuthorized())` дополнительно скрывает
  блок с именем на этом экране для гостя вовсе, независимо от того, что
  `currentUserData` для гостя здесь не `null`.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — читается (не
  изменяется) дважды за один проход экрана: `AuthRepository.getUser()`
  внутри `ProfileEditCubit.load()` (шаг 4) и второй раз внутри
  `ProfileBloc.on<ProfileEventStart>` (шаг 7); оба обращения читают одну
  и ту же строку `UserHive` из Hive-бокса `AuthRepository.authBoxKey`, по
  ключу `AuthRepository.userKey`.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS)
  — читается дважды тем же образом (`CountriesRepository.getAll()`, вся
  локальная таблица без фильтра, в обоих механизмах), используется для
  резолва имени/объекта страны пользователя по `countryId`/
  `phoneCountryIsoCode`.
- Session/токен ([ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), AUTH,
  Hive `AUTH_BOX`) — `_authRepository.isAuthorized()` (→
  `getMainTokenData() != null`) определяет ветвление гость/авторизован в
  `ProfileEditCubit.load()` (единственное место, где это ветвление
  реально принимает решение для этого экрана); `ProfileBloc` не
  проверяет авторизацию отдельно — просто получает уже гарантированно не
  `null` результат `getUser()`, потому что он строится только после того,
  как гейт уже пропустил авторизованного пользователя.

### Бизнес-правила

- **Гейт «гость/авторизован» для вкладки «Профиль» принадлежит
  `ProfileEditCubit`, не `ProfileBloc`.** Единственное решающее условие —
  `_authRepository.isAuthorized()` внутри `ProfileEditCubit.load()`,
  вызванного с `loadGuestSettings: false` (дефолт конструктора,
  используемый именно `ProfilePage`). `ProfileBloc` строится только
  после того, как это решение уже принято в пользу «авторизован» — его
  собственная логика ветвления по `user == null` формально существует, но
  не участвует в реальном UI-потоке `/profile`.
- **Резолв страны реализован дважды, независимо, с разным типом
  результата.** Оба места (`ProfileEditCubit._getSelectedCountry` →
  `Country?`, `ProfileBloc.on<ProfileEventStart>` инлайн → `String
  countryName`) реализуют одно и то же правило («сначала по `countryId`,
  при неудаче — по `phoneCountryIsoCode`, регистронезависимо»), без
  переиспользования общего кода между ними.
- **Итоговые отображаемые `name`/`countryName`/`appVersion` на экране
  «Профиль» приходят из `ProfileBloc`, не из `ProfileEditCubit`** — хотя
  оба кубита/блока вычисляют по сути одни и те же данные из тех же
  источников (`AuthRepository.getUser()`, `CountriesRepository.getAll()`,
  `PackageInfo.fromPlatform()`), и `ProfileEditState`, содержащий уже
  готовый `currentUserData`/`appVersion`, физически передаётся в
  `ProfileView` как аргумент `state`, но нигде не читается.
- Оба механизма реагируют на один и тот же реактивный источник (Hive-бокс
  авторизации, ключ `userKey`) независимо друг от друга — нет общего
  единственного места пересчёта «профиль обновился».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной поток (гейт `ProfileEditCubit`
→ рендер `ProfileView`/`ProfileBloc` для авторизованного, `LoginView` для
гостя) полностью реализован и достижим с единственной точки входа —
вкладка «Профиль» нижней навигации. Найденные структурные особенности
(дублирующийся резолв страны, неиспользуемые `formKey`/`state` в
`ProfileView`, структурно недостижимая гостевая ветка `ProfileBloc`,
дублирующаяся реактивная подписка, отсутствующий реальный лоадер для
внутреннего `ProfileBloc`) зафиксированы как факт CURRENT, не как
блокеры — это документирующий проход, не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/widgets/bottom_app_bar/nav_bar.dart` | `NavBar` (`_NavBarButton` с `label: l10n.profile`) | CURRENT | точка входа — переход на вкладку «Профиль» |
| `lib/pages/routes.dart` | `Routes.profile`, `Routes.profileSettings`, `Routes.inWork`, `Routes.workSettings`, `Routes.chats`, `Routes.myAds` | CURRENT | маршруты, используемые этим экраном и его переходами |
| `lib/pages/profile/presentation/profile_page.dart` | `ProfilePage`, `_ProfilePageState.build` | CURRENT | строит `ProfileEditCubit()..load()` (гейт), рендерит `LoginView`/`ProfileView` по `currentUserData` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load`, `._getSelectedCountry` | CURRENT | реальный гейт «гость/авторизован» для `/profile`; независимый резолв страны, возвращает `Country?` |
| `lib/pages/profile/cubit/profile_edit_state.dart` | `ProfileEditState` | CURRENT | состояние гейта; передаётся в `ProfileView` как `state`, но не читается там |
| `lib/pages/profile/presentation/widgets/login/login_view.dart` | `LoginView` | CURRENT | экран, показываемый гостю вместо данных профиля |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build` | CURRENT | конструирует независимый `ProfileBloc`; параметры `formKey`/`state` объявлены, но не используются в теле `build` |
| `lib/pages/profile/profile_bloc.dart` | `ProfileBloc.on<ProfileEventStart>` | CURRENT | второй, независимый резолв `user`/`countryName`/`appVersion`, фактически рендерящийся на экране |
| `lib/pages/profile/profile_event.dart` | `ProfileEventStart` | CURRENT | единственное событие блока |
| `lib/pages/profile/profile_state.dart` | `ProfileState`, `ProfileInitial` | CURRENT | единственный подкласс состояния — причина, по которой `if (state is! ProfileInitial)` в `profile_view.dart` никогда не истинно |
| `lib/pages/profile/presentation/widgets/profile_page_wrapper.dart` | `ProfilePageWrapper` | CURRENT | общий каркас (шапка, кнопка перехода в `Routes.profileSettings`) для `ProfileView` и `LoginView` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build` | CURRENT | второй потребитель `ProfileEditCubit`, с `loadGuestSettings: true` — связанная, но отдельная поверхность просмотра текущих данных |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser`, `.isAuthorized`, `.getAuthBoxListenable`, `.userKey` | CURRENT | источник `User`; читается независимо обоими механизмами; ключ реактивной подписки, общий для обоих |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getAll` (унаследован от `BaseRepository.getAll`) | CURRENT | источник справочника стран; читается независимо обоими механизмами |
| `lib/pages/profile/data/user_model.dart` | `UserModel`, `UserModel.fromUser` | CURRENT | модель, которую строит `ProfileEditCubit.load()` (не используется в рендере имени/страны, т.к. `state` не читается в `ProfileView`) |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized`, `.getGuestCountryCode` | CURRENT | используется только в связанном `ProfileSettingsView`, не на `/profile` |
| `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` | `BoardChatAvailabilityCubit` | CURRENT | внешний флаг, скрывающий/показывающий блоки BOARD внутри `ProfileView` — не читается/не изменяется этим сценарием, только потребляется |
| `lib/blocs/developer_mode/developer_mode_bloc.dart` | `DeveloperModeBloc`, `DeveloperModeEnabled` | CURRENT | показывает доп. кнопку «Logger» на экране профиля, побочный к основному сценарию |

## Критерии приёмки

- Открытие `/profile` строит `ProfileEditCubit()..load()` с
  `loadGuestSettings: false`; если `_authRepository.isAuthorized()` ложно —
  эмитится `ProfileEditState(currentUserData: null, …)` и пользователь
  видит `LoginView`, без построения `ProfileView`/`ProfileBloc`.
- Если `_authRepository.isAuthorized()` истинно — `ProfileEditCubit.load()`
  резолвит `currentUserData` из `AuthRepository.getUser()!` и
  `_getSelectedCountry`, эмитит `loading: false`; строится `ProfileView`,
  которая немедленно создаёт `ProfileBloc()..add(ProfileEventStart())`.
- `ProfileBloc.on<ProfileEventStart>` эмитит `ProfileInitial` с `user`,
  равным результату независимого `AuthRepository.getUser()`, и
  `countryName`, резолвленным по `countryId` (приоритет) либо
  `phoneCountryIsoCode` (fallback, регистронезависимое сравнение) среди
  независимого `CountriesRepository.getAll()`; отображаются
  `state.user?.name`, `state.countryName`, `state.appVersion`.
- Изменение записи пользователя в Hive-боксе (`AuthRepository.userKey`)
  при смонтированном экране триггерит переисполнение обоих механизмов
  независимо: `ProfileEditCubit.load()` (через `ProfileEditCubit`'s
  слушатель) и `ProfileBloc.add(ProfileEventStart())` (через свой
  отдельный слушатель на тот же ключ).
- `formKey` и `state`, переданные в конструктор `ProfileView`, не влияют
  на то, что физически отображается в `build()` — итоговые
  `name`/`countryName`/`appVersion` всегда приходят из внутреннего
  `ProfileBloc`, независимо от содержимого `state`.

## Связанные тесты

`test/pages/profile_bloc_test.dart` (группы пока без номера, будут
переименованы под `UC-161` отдельным проходом):

- group `'ProfileBloc.Start — гость'`, test `'нет пользователя ->
  user:null, countryName пуст'` — проверяет саму ветку `ProfileBloc` при
  отсутствии пользователя (`state.user`, `state.countryName == ''`,
  `verifyNever(() => countriesRepository.getAll())`); эта ветка, как
  показано в «Альтернативные потоки», не достижима из реальной навигации
  `/profile` — тест верен как юнит-тест изолированного `ProfileBloc`, не
  как воспроизведение наблюдаемого пользователем сценария этого экрана.
- group `'ProfileBloc.Start — авторизован'`: test `'countryId совпадает ->
  countryName заполнено по id'`, test `'countryId не совпадает, но
  phoneCountryIsoCode совпадает по коду -> countryName по коду'` —
  покрывают основной и первый альтернативный путь резолва страны внутри
  `ProfileBloc` (шаг 7 основного потока).
- group `'ProfileBloc — реактивная подписка'`, test `'изменение
  пользователя в Hive-боксе триггерит ProfileEventStart сам'` — покрывает
  реактивную подписку `ProfileBloc` на `AuthRepository.userKey`.

`test/pages/profile_edit_cubit_test.dart` — тесты гейта, который в
реальности определяет, достигает ли пользователь `ProfileView`/`ProfileBloc`
вообще; релевантны этому UC как доказательство факта «профиль
просмотрен» на уровне гейта, отдельно от рендера (не путать с будущим
use-case на `saveChanges`/`editXxx` — сохранение/правка, другое событие):

- group `'UC-161 — ProfileEditCubit.load (гость)'` (номер старый, будет
  переприсвоен отдельным проходом): test `'loadGuestSettings:false ->
  currentUserData/newUserData:null'` — прямое доказательство ветки
  «гость видит `LoginView`» этого UC (`ProfilePage` использует именно
  `loadGuestSettings: false`); test `'loadGuestSettings:true ->
  currentUserData сформирован из guest-контекста'` — релевантно не
  `/profile`, а связанному, но отдельному экрану `/profile_settings` (см.
  «Альтернативные потоки»).
- group `'UC-161 — ProfileEditCubit.load (авторизован)'` (номер старый):
  test `'пользователь из Hive-бокса -> currentUserData заполнен из
  User'` — доказывает резолв `currentUserData`/`selectedCountry` на
  стороне гейта (шаг 4 основного потока), предшествующий (но, как
  показано в «Бизнес-правила», физически не используемый при рендере)
  шагу 7.
- group `'ProfileEditCubit — реактивная подписка'`, test `'изменение
  пользователя в Hive-боксе триггерит повторный load()'` — покрывает
  реактивную подписку гейта, независимую от подписки `ProfileBloc`.

**TBD — теста нет** на: (а) факт, что `ProfileView` физически не читает
свои аргументы `formKey`/`state`; (б) факт, что `ProfileEditCubit.load()`
и `ProfileBloc.on<ProfileEventStart>` оба вызываются (дважды каждый метод
источника данных) при одном открытии `/profile` авторизованным
пользователем — нет теста, монтирующего `ProfilePage`/`ProfileView`
целиком (оба существующих файла тестируют `ProfileBloc` и
`ProfileEditCubit` по отдельности, через `bloc_test`/прямой вызов, не
через `testWidgets`); (в) отсутствие видимого лоадера для внутренней
подписки `ProfileBloc` (единственный подкласс `ProfileState`) — нет
виджет-теста, проверяющего содержимое кадра до завершения
`on<ProfileEventStart>`.

## Открытые вопросы и ограничения

- **[EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) называет
  единственным механизмом `ProfileBloc.on<ProfileEventStart>` — по факту
  гейт «гость/авторизован» реализован в `ProfileEditCubit`, отдельном
  классе, который строится на уровень выше `ProfileView`.** `EVT-81`
  заморожен, не редактируется этим use-case — расхождение зафиксировано
  здесь как факт CURRENT, обнаруженный при более глубоком прочтении, чем
  было доступно на момент написания `EVT-81`.
- **`formKey`/`state` — неиспользуемые аргументы конструктора
  `ProfileView`.** Не найдено объяснения в коде/комментариях, планировался
  ли когда-либо рендер формы редактирования прямо на `/profile`
  (`formKey` предполагает форму) — на сегодня оба параметра мертвы,
  подтверждено `grep`-ом по телу `profile_view.dart`.
- **Двойное независимое чтение `AuthRepository.getUser()` и
  `CountriesRepository.getAll()` за один проход экрана** — не найдено
  переиспользования результата между `ProfileEditCubit` и `ProfileBloc`;
  неясно, намеренная ли это избыточность (разделение ответственности:
  гейт против рендера) или недосмотр, оставшийся с момента, когда один из
  двух механизмов ещё не существовал.
- **`ProfileEditCubit(loadGuestSettings: true)` на `/profile_settings` —
  третий флаг поведения того же класса, не описанный этим use-case
  полностью.** Гостю показывается синтетический (не персистентный,
  `id: 0`) `currentUserData` на этом отдельном экране; насколько эта
  ветка относится к [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md)
  (просмотр) против [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md)
  (правка, чтение как первый шаг формы редактирования) — не решено этим
  файлом однозначно, зафиксировано как открытый вопрос на будущий проход
  по `EVT-82`.
- **Нет ни одного `testWidgets`, монтирующего `ProfilePage`/`ProfileView`
  целиком** — оба существующих теста (`profile_bloc_test.dart`,
  `profile_edit_cubit_test.dart`) проверяют `ProfileBloc`/`ProfileEditCubit`
  изолированно, через прямое конструирование и `bloc.stream`/`cubit.state`,
  не через дерево виджетов — структурная недостижимость гостевой ветки
  `ProfileBloc` (см. «Альтернативные потоки») подтверждена статическим
  чтением (`grep` по местам конструирования), не воспроизведена
  end-to-end тестом.
