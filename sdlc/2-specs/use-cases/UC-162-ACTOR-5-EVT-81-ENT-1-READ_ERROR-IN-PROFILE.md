# UC-162 — Чтение профиля в `ProfileBloc` падает: исключение никем в коде не перехватывается, в `Talker` попадает только через `Bloc.observer`, экран навсегда остаётся с пустыми именем/страной

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же внутренний механизм, что описан в
[UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md) (успешный
парный сценарий) — `ProfileBloc.on<ProfileEventStart>`
(`lib/pages/profile/profile_bloc.dart`), который строится только после
того, как `ProfileEditCubit` уже пропустил пользователя мимо гейта
«гость/авторизован» (`currentUserData != null`), резолвит `user`/
`countryName`/`appVersion` для отображения на вкладке «Профиль». Здесь
описан путь, при котором это чтение реально бросает исключение.

Это третий, отдельный класс дефекта среди уже задокументированных
`READ_ERROR`-сценариев `PROFILE`/`BOARD` — не повторяет ни один из двух
уже встречавшихся:

- в отличие от [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)
  (BOARD), где репозиторий сам глотает исключение (`catch (_) { return
  []; }`) и не роняет вызывающий код вовсе, здесь исключение **никем в
  коде приложения не перехватывается** — во всём теле
  `ProfileBloc.on<ProfileEventStart>` нет ни одного `try/catch`;
- в отличие от [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)
  (тот же модуль, `NotificationsSettingsCubit.load()`), где приложение
  само ловит исключение, логирует его через `Talker` и явно эмитит
  отдельный, отличимый вариант состояния (`failure`), здесь единственный
  перехват происходит **не в коде приложения**, а внутри самого пакета
  `bloc` (9.0.1): `Bloc.on<E>`'s внутренний `handleEvent()` оборачивает
  вызов обработчика в свой `try/catch`, вызывает
  `Bloc.observer.onError(...)` (в этом проекте — `TalkerBlocObserver`,
  зарегистрированный в `injection_container.dart`, поэтому исключение всё
  же попадает в `Talker`, но не по воле кода этого сценария) и затем
  `rethrow`. Поскольку `handleEvent()` вызывается как fire-and-forget
  (`handleEvent();`, без `await`), повторно брошенное исключение
  становится необработанной асинхронной ошибкой — в этом приложении
  `runZonedGuarded`/`runTalkerZonedGuarded` в `lib/main.dart`
  закомментированы, поэтому её не перехватывает ничто ещё раз. `emit(...)`
  (единственный, последней строкой обработчика) в этом случае не
  достигается вовсе — состояние `ProfileBloc` замирает на прежнем
  значении. Наблюдаемый пользователем итог: экран профиля рендерится
  сразу (не `LoginView` — тот гейт уже пройден раньше), но с пустыми
  именем/страной/версией приложения, без единого визуального признака
  отказа.

Внутри обработчика есть три независимых вызова, которые теоретически
могли бы бросить исключение; каждый проверен отдельно чтением кода,
похожим образом на [UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md):

- **(а) `_authRepository.getUser()`** — синхронное чтение Hive-бокса
  (`_getAuthBox() => Hive.box<dynamic>(authBoxKey)`, бросает `HiveError`,
  если бокс не открыт в памяти). Проверено отдельно: `AuthRepository.logout()`
  делает только `await box.clear()` (очищает ключи, не закрывает бокс);
  `grep -rn "\.close()" lib/` не находит ни одного вызова, закрывающего
  `AUTH_BOX` где-либо в рантайме; единственное место, где этот бокс вообще
  открывается — `AppCacheService._openBoxes` (вызывается из
  `AppCacheService.logHiveBox()` в `main()`, до `runApp()`, с
  восстановлением через `Hive.deleteBoxFromDisk` при повреждении). Тот же
  класс проверки, что уже задокументирован в
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) для другого
  бокса/сценария — здесь независимо переподтверждён для `AUTH_BOX`/`getUser()`.
  Признан структурно недостижимым на практике: к моменту, когда
  `ProfileBloc` вообще строится, тот же самый бокс уже был успешно прочитан
  секундами раньше внутри `ProfileEditCubit.load()` (обязательное условие
  для прохождения гейта, см. [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md)).
- **(б) `PackageInfo.fromPlatform()`** — асинхронный вызов платформенного
  канала пакета `package_info_plus` (зафиксированная версия — `9.0.0`,
  `pubspec.lock`). Проверено отдельно чтением исходников пакета: результат
  первого успешного вызова кэшируется в статическом поле `PackageInfo._fromPlatform`
  (`lib/package_info_plus.dart`) — каждый следующий вызов внутри того же
  процесса возвращает кэш немедленно, не трогая платформенный канал вовсе.
  К моменту, когда `ProfileBloc.on<ProfileEventStart>` доходит до этой
  строки, тот же статический кэш уже гарантированно прогрет как минимум
  дважды раньше: `ProfileEditCubit.load()`'s собственным идентичным вызовом
  (обязательное условие прохождения гейта) и — ещё раньше — `AuthBloc.on<AuthEventStart>`
  (`lib/pages/profile/bloc/auth_bloc.dart`), вызываемым на сплэш-экране при
  старте приложения, до какой-либо навигации. Признан структурно
  недостижимым на практике на этом конкретном вызове.
- **(в) `_countriesRepository.getAll()`** (`CountriesRepository.getAll`,
  унаследован от `BaseRepository.getAll` → `dao.getAll()` →
  `BaseDao.getAll()` → `selectCurrent().get()`) — настоящий, некэшируемый
  Drift/sqlite3-запрос, выполняемый заново при каждом вызове, без единого
  `try/catch` на всём пути (`CountriesRepository` не переопределяет
  `getAll`; `BaseRepository`/`BaseDao` тоже не оборачивают вызов). В
  отличие от (а)/(б), эта же операция уже была один раз успешно выполнена
  секундами раньше (`ProfileEditCubit.load()`), но не кэшируется — ничто не
  мешает именно этому, второму, независимому вызову внутри `ProfileBloc`
  отказать самостоятельно (например, из-за преходящей ошибки ввода-вывода
  sqlite3, блокировки файла БД или иного drift-исключения). Это
  единственный из трёх кандидатов, признанный практически достижимым —
  именно он и описан как «Основной поток» ниже.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения.
Как и в [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md),
фактически достижим только **авторизованный** пользователь: `ProfileBloc`
строится (`profile_view.dart`) только внутри `ProfileView`, а та — только
после того, как `ProfileEditCubit` (гейт «гость/авторизован» для `/profile`)
уже эмитировал `currentUserData != null`. Собственная ветка `ProfileBloc`
«нет пользователя → `user: null`» технически существует, но, как уже
подтверждено в UC-161 фактическим единственным местом конструирования
класса в проекте, недостижима из реальной навигации — этот факт не
переопределяется здесь, только используется как предпосылка.

## CURRENT

### Основной поток

1. Авторизованный пользователь уже прошёл гейт `ProfileEditCubit.load()` —
   `PackageInfo.fromPlatform()` и `_countriesRepository.getAll()` уже были
   вызваны и успешно завершились там (иначе `ProfileView`, а значит и
   `ProfileBloc`, не были бы построены вовсе, см. «Назначение» и
   [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md)).
   `ProfileView.build` создаёт `BlocProvider(create: (context) =>
   ProfileBloc()..add(ProfileEventStart()))`.
2. `ProfileBloc.on<ProfileEventStart>` (`lib/pages/profile/profile_bloc.dart`)
   начинает выполнение: `final user = _authRepository.getUser();` —
   успешно (см. «Назначение», (а) — тот же Hive-бокс только что был
   прочитан гейтом).
3. `final packageInfo = await PackageInfo.fromPlatform();` — успешно,
   разрешается мгновенно из статического кэша пакета, прогретого как
   минимум гейтом, а на практике ещё раньше — сплэш-экраном (см.
   «Назначение», (б)).
4. `user != null` — истинно (гейт уже гарантировал это). `final countries
   = await _countriesRepository.getAll();` — вызывается независимо,
   отдельным Drift-запросом к таблице `Countries`, без какого-либо
   переиспользования результата, полученного гейтом секундами раньше. В
   этом сценарии вызов бросает исключение (см. «Назначение», (в)) — ни
   `CountriesRepository.getAll`, ни `BaseRepository`, ни `BaseDao.getAll`
   не оборачивают его в `try/catch`.
5. Исключение всплывает из тела обработчика `on<ProfileEventStart>` —
   единственный `emit(ProfileInitial(user: user, appVersion: appVersion,
   countryName: countryName))`, стоящий последней строкой метода, не
   достигается.
6. Внутри `bloc` (9.0.1): `Bloc.on<E>`'s внутренняя функция
   `handleEvent()` вызывает обработчик в собственном `try { await
   handler(event, emitter); } catch (error, stackTrace) { onError(error,
   stackTrace); rethrow; }`. `onError` (определён в `BlocBase`) вызывает
   `_blocObserver.onError(this, error, stackTrace)`.
7. `Bloc.observer` в этом приложении — `TalkerBlocObserver`
   (`lib/injection_container.dart`, `Bloc.observer = TalkerBlocObserver(talker:
   loger, ...)`). Его `onError` **безусловен** (в отличие от `onEvent`/
   `onChange`/`onCreate`/`onClose` того же класса, которые проверяют
   `settings.enabled`/конкретный флаг): `_talker.error('${bloc.runtimeType}',
   error, stackTrace)` — строка `'ProfileBloc'` вместе с исключением и
   стектрейсом попадает в `Talker`, видимый только через встроенный
   лог-экран (`TalkerScreen`, открывается скрытой кнопкой «Logger» при
   включённом `DeveloperModeBloc` — физически на этом же экране профиля,
   см. [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md)), не в
   UI самого сценария и не пользователю каким-либо иным способом.
8. `handleEvent()`'s `catch`-блок делает `rethrow`. Поскольку сам вызов
   `handleEvent();` — fire-and-forget (без `await`, без `.catchError()` со
   стороны внутренней инфраструктуры пакета `bloc`, подписывающей на него
   `controller.stream`), повторно брошенное исключение становится
   необработанной асинхронной ошибкой. `lib/main.dart`: `runApp(const
   MyApp());` не обёрнут в `runZonedGuarded`
   (закомментированный `runTalkerZonedGuarded(getIt<Talker>(), () =>
   runApp(const MyApp()), ...)` — рядом, но не активен) — ничто в
   приложении не перехватывает эту ошибку повторно; Dart печатает
   «Unhandled exception» и стектрейс в консоль по умолчанию, приложение не
   падает (это не часть синхронного построения дерева виджетов/обработки
   жеста), пользователь не видит ничего.
9. Поскольку исключение произошло до единственного `emit(...)`, состояние
   `ProfileBloc` не меняется для этого вызова. Для самого первого
   `ProfileEventStart()` (диспатчится немедленно при построении
   `ProfileView`, шаг 1) состояние остаётся ровно конструкторным дефолтом:
   `const ProfileInitial()` → `user: null`, `appVersion: ''`, `countryName:
   ''`.
10. `ProfileView`'s внутренний `BlocBuilder<ProfileBloc, ProfileState>` —
    как уже задокументировано в [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md),
    `ProfileState` имеет единственный подкласс (`ProfileInitial`), поэтому
    `if (state is! ProfileInitial) { return CustomLottieLoader(); }`
    никогда не истинно — рендерится полный каркас профиля немедленно, со
    значениями по умолчанию: `state.user?.name` → `''`, `state.countryName`
    → `''`, `state.appVersion` → `''` (текст `l10n.app_version: `).
    Остальные элементы экрана (кнопка-шестерёнка → `Routes.profileSettings`,
    блоки «Избранное»/«Сообщения»/«Мои объявления», видимые по
    `BoardChatAvailabilityCubit` независимо от этого сценария, «В работе»,
    «Настройки работы», контакты поддержки) отображаются и работают как
    обычно — этот отказ обнуляет только три текстовых поля, источник
    которых — `ProfileState`.
11. Итог, видимый пользователем: экран, неотличимый от настоящего
    авторизованного профиля по структуре (не `LoginView`), но с пустым
    именем, пустой строкой страны и пустой версией приложения — без
    какого-либо сообщения об ошибке, кнопки повтора или индикатора,
    сохраняющийся до тех пор, пока что-то не запустит `ProfileEventStart`
    заново (см. «Альтернативные потоки») и эта повторная попытка не
    окажется успешной.

### Альтернативные потоки

- **Отказ на реактивном перезапуске после уже успешного первого чтения —
  «протухшие», а не пустые данные.** И `ProfileEditCubit`, и `ProfileBloc`
  независимо подписаны на один и тот же `ValueListenable<Box>`
  (`AuthRepository.getAuthBoxListenable(keys: [AuthRepository.userKey])`,
  см. [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md)).
  `ProfileBloc._listener` вызывает `add(ProfileEventStart())` при каждом
  изменении ключа `userKey`. Если первый вызов `on<ProfileEventStart>`
  прошёл успешно (реальные `name`/`countryName`/`appVersion` уже
  отображены), а **следующий**, вызванный этим реактивным триггером,
  отказывает тем же путём (в) — состояние `ProfileBloc` остаётся равным
  предыдущему, уже отображённому значению: пользователь видит не пустой, а
  просто не обновившийся экран (например, после правки имени на
  `/profile_settings`, вызвавшей запись в тот же Hive-ключ, старое имя
  продолжает отображаться на `/profile`), без какого-либо признака, что
  обновление не удалось.
- **Тот же класс уязвимости — на уровне самого гейта,
  `ProfileEditCubit.load()`.** Метод целиком лишён `try/catch` (проверено
  чтением всего тела `load()`). Он вызывается не через `Bloc.on<E>`, а
  как обычный `Future`-метод, вызванный fire-and-forget (`ProfileEditCubit()..load()`,
  `profile_page.dart`) — поэтому исключение отсюда **не проходит даже
  через `Bloc.observer`**: `BlocBase.onError`/`addError` вызываются только
  явным кодом самого класса (например, внутри `emit()`, если тот бросает
  по другой причине) или инфраструктурой `Bloc.on<E>` — обычный метод
  кубита, вызванный напрямую, ни то ни другое не запускает. Если тот же
  практически достижимый источник (в) — `_countriesRepository.getAll()` —
  откажет здесь (эта же строка выполняется в `load()` раньше, чем в
  `ProfileBloc`, и с тем же отсутствием кэширования), `emit(ProfileEditState(...))`
  ни в одной из веток метода не достигается: `state.loading` остаётся
  равным `true` (выставлено первой строкой `load()`, `emit(state.copyWith(loading:
  true))`) навсегда. `ProfilePage`'s `BlocBuilder<ProfileEditCubit,
  ProfileEditState>`: `if (state.loading ?? true) { return
  CustomLottieLoader(); }` — истинно бесконечно; `ProfileView`, а
  следовательно и `ProfileBloc`, **не строятся вовсе** — событие
  [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) в этом
  случае не происходит совсем, экран навсегда виснет на индикаторе
  загрузки, без единой строки лога где бы то ни было. Это более тяжёлый и
  более тихий вариант того же корневого дефекта (полное отсутствие
  `try/catch` вокруг одного и того же некэшируемого чтения), но
  затрагивает другой класс/метод и другое поведение UI — не описывается
  этим файлом как основной сценарий (тот привязан к `ProfileBloc`/EVT-81
  по заданию id этого use-case), только фиксируется как обнаруженная при
  проверке смежная находка, требующая отдельного прохода.
- **(а)/(б) — проверены и признаны структурно недостижимыми именно на этих
  вызовах** (Hive-бокс уже гарантированно открыт; `PackageInfo` уже
  гарантированно закэширован) — подробности в «Назначение». Отмечено
  здесь отдельно, поскольку задание этого прохода явно требовало проверить
  оба источника, а не только практически достижимый (в).

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — сущность
  сегмента `ENT` этого use-case: `_authRepository.getUser()` (шаг 2)
  завершается успешно и сам по себе не является источником отказа в этом
  сценарии, но именно `state.user` — то поле `ProfileState`, которое
  должно было обновиться финальным `emit(...)` и вместо этого замирает на
  `null` (первое открытие) либо на предыдущем значении (реактивный
  перезапуск, см. «Альтернативные потоки») — читается, не изменяется.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS)
  — сущность, чьё чтение (`_countriesRepository.getAll()`, шаг 4) реально
  бросает исключение в практически достижимой ветке (в); читается, не
  изменяется.
- Session/токен ([ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), AUTH,
  Hive `AUTH_BOX`) — не читается напрямую этим обработчиком (`ProfileBloc`
  не вызывает `isAuthorized()`), но её более раннее успешное чтение
  гейтом — предпосылка, по которой ветка (а) признана недостижимой; не
  изменяется этим сценарием.

### Бизнес-правила

- В `ProfileState` нет и не может быть отдельного, отличимого от успеха
  варианта отказа — в отличие от `NotificationsSettingsState`
  ([UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)), где
  такой вариант (`failure`) явно объявлен как freezed-юнион, здесь
  единственный подкласс `ProfileState` — `ProfileInitial`, и обработчик
  не эмитит вообще ничего при отказе — архитектурно негде было бы
  показать отличимое состояние ошибки, даже если бы код этого хотел.
- Логирование в `Talker` в этом сценарии происходит не по воле кода
  сценария, а как побочный эффект глобальной инфраструктуры
  (`Bloc.observer`) — единственный из трёх встречавшихся в модулях
  `PROFILE`/`BOARD` `READ_ERROR`-сценариев, где лог появляется
  «бесплатно», не будучи запрошен явным `try/catch` в самом коде фичи.
- Нет ни ретрая, ни кнопки «повторить» — единственный способ вызвать
  `on<ProfileEventStart>` заново — либо реактивный триггер по
  `AuthRepository.userKey` (не гарантированный: может не сработать,
  если пользователь не меняет ничего в своих данных), либо полный выход
  и повторный вход на вкладку «Профиль» (пересоздаёт `ProfileBloc`).
- Отказ этого сценария никак не связан с sync-проходом
  (`DataUpdateBloc`/`DataUpdateStartAll`) — это чисто локальное чтение,
  не затрагивающее `DataUpdates`, сетевые вызовы или какой-либо признак,
  видимый на экране «В работе».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (необработанное
исключение из `_countriesRepository.getAll()` внутри
`ProfileBloc.on<ProfileEventStart>` → перехват и `rethrow` служебным
`handleEvent()` пакета `bloc` → логирование в `Talker` через
`Bloc.observer` без участия кода сценария → необработанная асинхронная
ошибка → `emit(...)` не достигается → `ProfileState` замирает) полностью
прослеживается статическим чтением кода: `ProfileBloc.on<ProfileEventStart>`
→ `CountriesRepository.getAll` → `BaseRepository.getAll` → `BaseDao.getAll`
→ `selectCurrent().get()`, плюс независимое чтение исходников пакетов
`bloc` (9.0.1) и `talker_bloc_logger` (5.0.1). Два других кандидата
источника исключения ((а) Hive-бокс, (б) `PackageInfo.fromPlatform()`)
проверены отдельно и признаны структурно недостижимыми именно на этих
вызовах — не подтверждённых экспериментально, но обоснованных чтением
кода/пакетов (см. «Назначение»). Смежная находка (идентичная уязвимость
внутри `ProfileEditCubit.load()`, блокирующая сам гейт) зафиксирована как
относящаяся к другому классу/событию, не переспецифицируется здесь как
основной сценарий. Исправление (например, `try/catch` вокруг
`_countriesRepository.getAll()` с отдельным вариантом состояния, обёртка
`runApp()` в `runZonedGuarded`, кэширование результата между
`ProfileEditCubit`/`ProfileBloc`) в рамках этого документирующего прохода
не выполняется — это фиксация уже существующего кода, а не работа над
дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/profile_bloc.dart` | `ProfileBloc.on<ProfileEventStart>` | CURRENT | предмет основного потока — ни одного `try/catch` во всём теле обработчика; единственный `emit(...)` — последняя строка |
| `lib/pages/profile/profile_state.dart` | `ProfileState`, `ProfileInitial` | CURRENT | единственный подкласс состояния — архитектурно негде выразить отличимый вариант отказа |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build`, внутренний `BlocProvider`/`BlocBuilder<ProfileBloc, ProfileState>` | CURRENT | конструирует `ProfileBloc` уже после гейта; рендерит `state.user?.name`/`.countryName`/`.appVersion` без разбора по варианту состояния |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | тот же класс уязвимости на уровне гейта — без собственного `try/catch`; см. «Альтернативные потоки» |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build`, `state.loading ?? true` | CURRENT | если гейт падает раньше, чем этот сценарий вообще становится достижим — экран навсегда остаётся на `CustomLottieLoader()` |
| `lib/repositories/country/countries_repository.dart` | `CountriesRepository.getAll` (унаследован от `BaseRepository.getAll`) | CURRENT | практически достижимый источник исключения — реальный, некэшируемый Drift-запрос, вызывается независимо и гейтом, и `ProfileBloc` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll` | CURRENT | `selectCurrent().get()` — без `try/catch`, конечная реализация вызова |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser`, `._getAuthBox`, `.logout` | CURRENT | `getUser()` — синхронное чтение Hive-бокса; `logout()` делает только `box.clear()`, не `.close()` — почему ветка (а) структурно недостижима |
| `lib/data/services/app_cache_service.dart` | `AppCacheService._openBoxes`, `.logHiveBox` | CURRENT | доказывает, что `AUTH_BOX` открывается один раз при старте (`main()`, до `runApp()`), с восстановлением там же при повреждении — не закрывается позже в рантайме |
| `lib/main.dart` | `main()` (`runApp`, закомментированный `runTalkerZonedGuarded`) | CURRENT | `runZonedGuarded` неактивен — необработанная асинхронная ошибка из `handleEvent()` не перехватывается повторно нигде |
| `package_info_plus` (внешний, 9.0.0) | `PackageInfo.fromPlatform`, статическое поле `_fromPlatform` | CURRENT | кэширует результат первого успешного вызова — почему ветка (б) структурно недостижима именно на этом, повторном, вызове |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | CURRENT | вызывает тот же `PackageInfo.fromPlatform()` ещё на сплэш-экране, до всякой навигации — подтверждает, что кэш прогрет задолго до `/profile` |
| `bloc` (внешний, 9.0.1) | `Bloc.on<E>` → внутренний `handleEvent()` | CURRENT | оборачивает вызов обработчика в `try/catch`, вызывает `onError`, затем `rethrow`; сам вызов `handleEvent()` — fire-and-forget, поэтому `rethrow` становится необработанной асинхронной ошибкой |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | единственный обработчик `onError` для всех `Bloc`/`Cubit` в приложении |
| `talker_bloc_logger` (внешний, 5.0.1) | `TalkerBlocObserver.onError` | CURRENT | безусловно (без проверки `settings.enabled`, в отличие от `onEvent`/`onChange`/`onCreate`/`onClose` того же класса) логирует `bloc.runtimeType` + ошибку + стектрейс в `Talker` |
| `lib/blocs/developer_mode/developer_mode_bloc.dart` | `DeveloperModeBloc` | CURRENT | единственный способ увидеть этот лог из UI — скрытая кнопка «Logger» на этом же экране профиля (см. [UC-161](UC-161-ACTOR-5-EVT-81-ENT-1-READ_OK-IN-PROFILE.md)) |

## Критерии приёмки

- `ProfileBloc.on<ProfileEventStart>` не содержит ни одного `try/catch`;
  единственный `emit(...)` — последняя строка обработчика.
- Если `_countriesRepository.getAll()` (единственный практически
  достижимый источник — см. CURRENT) бросает исключение, `emit(...)` не
  достигается; исключение перехватывается только служебным `handleEvent()`
  пакета `bloc`, который вызывает `Bloc.observer.onError` (в этом
  приложении — `TalkerBlocObserver`, безусловное логирование
  `'ProfileBloc'` + ошибка + стектрейс в `Talker`) и затем `rethrow`.
- Так как `handleEvent()` вызывается без `await`, повторно брошенное
  исключение становится необработанной асинхронной ошибкой — не
  перехватывается нигде ещё (`runZonedGuarded` в `main.dart`
  закомментирован), не показывается пользователю ни `SnackBar`, ни любым
  иным способом, не приводит к падению приложения.
- `_authRepository.getUser()` и `PackageInfo.fromPlatform()` в этом
  сценарии не являются источником отказа: к моменту вызова `AUTH_BOX` уже
  гарантированно открыт (не закрывается нигде в рантайме), а
  `PackageInfo._fromPlatform` уже гарантированно прогрет как минимум
  гейтом `ProfileEditCubit.load()`.
- Состояние `ProfileBloc` остаётся равным значению до отказавшего вызова:
  при самом первом открытии экрана — конструкторному дефолту
  `ProfileInitial(user: null, appVersion: '', countryName: '')`; при
  отказе на более позднем реактивном перезапуске (после уже успешного
  первого чтения) — предыдущему, ранее корректно вычисленному значению.
- `ProfileView` рендерит полный экран профиля (не `LoginView`) с пустыми
  (или «протухшими») `name`/`countryName`/`appVersion`, при полностью
  рабочих остальных элементах экрана — без сообщения об ошибке, кнопки
  повтора или индикатора где бы то ни было.
- Идентичный по механике отказ внутри `ProfileEditCubit.load()` (тот же
  некэшируемый `_countriesRepository.getAll()`, тоже без `try/catch`)
  оставляет `state.loading == true` навсегда — `ProfilePage` показывает
  `CustomLottieLoader()` бесконечно, `ProfileView`/`ProfileBloc` не
  строятся вовсе, и это происходит вообще без единой строки лога (Cubit'ный
  метод, вызванный напрямую, не проходит через `Bloc.observer`).

## Связанные тесты

`test/pages/profile_bloc_test.dart` — все три существующие группы
покрывают только успешные пути:

- group `'ProfileBloc.Start — гость'`, test `'нет пользователя ->
  user:null, countryName пуст'`;
- group `'ProfileBloc.Start — авторизован'`, test `'countryId совпадает ->
  countryName заполнено по id'`, test `'countryId не совпадает, но
  phoneCountryIsoCode совпадает по коду -> countryName по коду'`;
- group `'ProfileBloc — реактивная подписка'`, test `'изменение
  пользователя в Hive-боксе триггерит ProfileEventStart сам'`.

Ни один тест не мокает `countriesRepository.getAll()` как бросающий
исключение (единственный мок в файле — `MockCountriesRepository`,
стабленный только успешными ответами или не стабленный вовсе, когда
`verifyNever` подтверждает, что вызова не было); `AuthRepository` в этом
файле — реальный класс поверх `hive_test_helper`, а не мок, поэтому путь
(а) в принципе не воспроизводится этим набором тестов тем же механизмом;
`PackageInfo.fromPlatform()` замокан один раз статически в `setUpAll` через
`PackageInfo.setMockInitialValues(...)` и никогда не бросает.

`test/pages/profile_edit_cubit_test.dart` — аналогично, все существующие
группы (`'UC-161 — ProfileEditCubit.load (гость)'`, `'UC-161 —
ProfileEditCubit.load (авторизован)'`, `'ProfileEditCubit — реактивная
подписка'` и остальные) стабят `countriesRepository.getAll()` только
успешным ответом (`thenAnswer((_) async => [...])`), ни разу — исключением.

**TBD — теста нет** ни на один из под-потоков этого сценария: ни на факт,
что исключение из `_countriesRepository.getAll()` внутри
`ProfileBloc.on<ProfileEventStart>` не перехватывается кодом приложения и
утекает через `Bloc.observer`/`TalkerBlocObserver` в необработанную
асинхронную ошибку, ни на итоговое замирание `ProfileInitial(user: null,
...)`/предыдущего значения, ни на «протухшие данные» при отказе
реактивного перезапуска, ни на параллельный, более тяжёлый сценарий внутри
`ProfileEditCubit.load()` (бесконечный `CustomLottieLoader()`, вовсе без
лога).

## Открытые вопросы и ограничения

- **Три разных техники обработки одного и того же класса продуктовой
  проблемы («локальное чтение отказывает») в пределах одной пары модулей
  `PROFILE`/`BOARD`.** [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) —
  репозиторий сам глотает исключение молча, без лога; [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md) —
  приложение явно ловит, логирует и эмитит отдельное состояние (которое UI,
  впрочем, тоже игнорирует); этот файл — исключение не ловится нигде в
  коде приложения вовсе, лог появляется только как побочный эффект
  глобальной инфраструктуры `Bloc.observer`. Ничем в коде/комментариях не
  зафиксировано, было ли это осознанным разнообразием или тремя
  независимыми недосмотрами в разное время.
- **Архитектурная граница `ProfileState` (единственный подкласс) не
  оставляет места для отличимого состояния ошибки**, даже если бы кто-то
  захотел его добавить обычным `emit` — потребовало бы сначала расширить
  саму иерархию состояния (сегодня — простой `Equatable`-класс, не
  freezed-юнион, в отличие от `NotificationsSettingsState`).
- **Смежная находка, не специфицированная этим файлом как основной
  сценарий:** идентичная уязвимость внутри `ProfileEditCubit.load()`
  (тот же некэшируемый `_countriesRepository.getAll()`, тоже без
  `try/catch`) блокирует сам гейт «гость/авторизован» для `/profile` —
  экран навсегда виснет на `CustomLottieLoader()`, `ProfileBloc` не
  строится вовсе, событие [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md)
  не происходит совсем, и в отличие от сценария этого файла — совсем без
  лога (обычный метод кубита, вызванный напрямую, не приводит к вызову
  `Bloc.observer.onError`). Заслуживает отдельного use-case в будущем
  проходе — не переспецифицируется здесь, поскольку id этого файла
  однозначно привязан к `ProfileBloc`/EVT-81, не к `ProfileEditCubit`.
- **Практическая достижимость ветки (в) не подтверждена эмпирически** —
  вывод сделан чтением кода (`CountriesRepository.getAll` не кэширует
  результат, в отличие от `PackageInfo.fromPlatform()`) и не воспроизведён
  ни одним тестом, ни реальным запуском против настоящей sqlite3-БД в
  состоянии сбоя.
- Не проверено, действительно ли на реальных устройствах между двумя
  вызовами `_countriesRepository.getAll()` (гейт и `ProfileBloc`),
  разделёнными считанными миллисекундами в рамках одного и того же кадра
  построения виджетов, в принципе может успеть произойти независимый сбой
  именно второго вызова — предположение основано на отсутствии
  кэширования в коде, не на наблюдаемой частоте таких отказов.
