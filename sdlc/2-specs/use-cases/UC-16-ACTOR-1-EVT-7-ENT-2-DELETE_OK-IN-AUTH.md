# UC-16 — Авторизованный пользователь выходит из аккаунта (успех)

## Назначение

Авторизованный пользователь на экране настроек профиля явно нажимает «Выйти»
— локальная сессия (главный токен, `User`, серверные интеграции) стирается,
и пользователь оказывается на экране входа.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — действие доступно только когда сессия уже активна:
кнопка находится на экране, требующем авторизации (`ProfileSettingsView`,
дочерний маршрут `Routes.profile`).

## CURRENT

### Основной поток

1. Пользователь на экране «Настройки профиля» (`ProfileSettingsView`) нажимает
   кнопку «Выйти» (`l10n.logout`) — `_ProfileSettingsButtons.onTap`.
2. Обработчик `onTap` синхронно выполняет три действия подряд: переходит на
   `Routes.profile` (`context.go`), запускает (без `await`)
   `AppCacheService.clearAllCache()` и диспетчит
   `context.read<AuthBloc>().add(AuthEventLogout())` — конструктор
   `AuthEventLogout` по умолчанию задаёт `clearData: true`.
3. `AuthBloc.on<AuthEventLogout>` эмитит `AuthSplashScreen()`.
4. Так как `event.clearData == true`, обработчик дожидается
   `AuthRepository.logout()`.
5. `AuthRepository.logout()`: `isAuthorized()` истинно (главный токен ещё
   сохранён) → метод получает `AUTH_BOX` (`_getAuthBox()`) и вызывает
   `box.clear()` одним вызовом — стирает главный токен
   (`tokenMainDataKey`), `User` (`userKey`) и серверные интеграции
   (`serverIntegrationsKey`) одновременно, без разбора по ключам;
   `LOGIN_BOX`/`DEVELOPER_BOX` этим конкретным вызовом не затрагиваются.
6. `logout()` вызывает `AppCacheService.setAuthorizedFlag(false)`
   (кэшированный дубликат флага авторизации в `SharedPreferences`) и кладёт
   `false` в `_authStreamController` — тот же broadcast-стрим, который
   отдаёт `getAuthStream()`.
7. Обработчик `AuthEventLogout` эмитит `AuthLogout()`, затем вызывает
   `_emitInitial(emit)`, которая эмитит
   `AuthInitial(login: _login, password: _password, appVersion: …)`; поля
   `_login`/`_password` в самом `AuthBloc` при этом не сбрасываются — они
   переживают logout в памяти блока и будут повторно показаны на экране
   входа, даже если персистентный «запомненный логин» уже стёрт (см. шаг 2 и
   «Альтернативные потоки»).
8. `ProfilePage` держит `BlocListener<AuthBloc, AuthState>`: получив
   `AuthLogout`, он диспетчит `DataUpdateBloc.add(DataUpdateClear())` —
   сбрасывает состояние sync-пайплайна. Это эффект вне границ [MOD-1](../modules/MOD-1-AUTH.md)
   (владелец — будущий модуль SYSTEM, ещё не специфицирован отдельным
   `MOD-*`), но он реально срабатывает при каждом выходе и потому упомянут
   здесь как факт полного пользовательского сценария.
9. Поскольку `AUTH_BOX` пуст, `ProfileEditCubit.load()` (пересозданный после
   навигации на `Routes.profile`) видит `_authRepository.isAuthorized() ==
   false` и эмитит состояние с `currentUserData: null`; `ProfilePage.build`
   при `currentUserData == null` рендерит `LoginView` вместо `ProfileView` —
   пользователь визуально оказывается на экране входа.

### Альтернативные потоки

- **Гонка с `AppCacheService.clearAllCache()`.** Вызов на шаге 2 не
  дожидается (`onTap` — синхронный, а `clearAllCache()` возвращает
  `Future<void>`), поэтому реально выполняется параллельно с обработкой
  `AuthEventLogout`. `clearAllCache()` без `clearIntegrationDirection: true`
  открывает и чистит **все четыре** Hive-бокса
  (`AppUpdateRepository.newAppVersionBoxKey`, `AUTH_BOX`, `LOGIN_BOX`,
  `DEVELOPER_BOX`) через `AppCacheService.clearHiveBoxes()` — то есть, в
  отличие от изолированного `AuthRepository.logout()`, полный пользовательский
  сценарий выхода из настроек профиля стирает и запомненный логин
  (`LOGIN_BOX`), и флаг режима разработчика (`DEVELOPER_BOX`), и бокс версии
  приложения — не только `AUTH_BOX`. Порядок между этой чисткой и
  собственным `box.clear()` внутри `AuthRepository.logout()` не
  гарантирован ничем в коде — эффект (полное стирание) одинаков независимо от
  порядка, но сам факт незащищённой гонки — часть текущего поведения.
- **Самозапуск повторного logout-события через `getAuthStream()`.** `false`,
  отправленный на шаге 6, доходит до подписки, оформленной в конструкторе
  `AuthBloc` (`_authRepository.getAuthStream().listen(...)`, тот же механизм,
  что использует [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md)) — она добавляет в очередь ещё один
  `AuthEventLogout(clearData: false)`, обрабатываемый той же bloc-инстанцией
  сразу вслед за первым. Эффект — повторная эмиссия
  `AuthSplashScreen()`/`AuthLogout()`/`AuthInitial()` без дополнительного
  влияния на Hive (`clearData: false` пропускает повторный `logout()`).
  Наблюдаемо только чтением исходников совместно (`auth_bloc.dart` +
  `auth_repository.dart`) — юнит-тесты `AuthBloc` мокают репозиторий, поэтому
  этот повторный проход в изоляции не проверяется.
- **Пользователь уже не авторизован в момент вызова `logout()`.**
  `AuthRepository.logout()` начинается с проверки `isAuthorized()`; если она
  ложна, метод только вызывает `AppCacheService.setAuthorizedFlag(false)` и
  возвращает управление — `box.clear()` не вызывается, `AUTH_BOX` не
  трогается. Идемпотентная защитная ветка внутри самого метода `logout()`,
  не отдельный путь UI-кнопки (кнопка «Выйти» показывается только когда
  сессия уже активна).

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — основная сущность сценария: главный токен,
  `User` и серверные интеграции внутри `AUTH_BOX` удаляются одним вызовом
  `box.clear()`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — хранится тем же ключом того же `AUTH_BOX`
  (`userKey`) и стирается вместе с токеном на шаге 5, хотя [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — не
  единственная затронутая сущность, `User` тоже перестаёт существовать
  локально в этот момент.

### Бизнес-правила

- Единственное условие входа в «настоящий» путь очистки — `event.clearData
  == true`, что соответствует значению по умолчанию конструктора
  `AuthEventLogout()`, используемого явной кнопкой «Выйти»; путь с `false`
  зарезервирован за автоматическим/повторным вызовом (см. [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) и
  «Альтернативные потоки»).
- `logout()` стирает `AUTH_BOX` целиком одним вызовом, не по отдельным
  ключам — нет варианта частичного выхода (например, сохранить `User`, но
  сбросить токен).
- Обработчик `AuthEventLogout` не оборачивает `_authRepository.logout()` в
  `try/catch` — успешный путь (этот сценарий) всегда доходит до `AuthLogout`
  → `AuthInitial`; сбой самого вызова `logout()` — другой сценарий
  (`DELETE_ERROR`, вне рамок этого файла).
- Кнопка «Выйти», инициирующая сценарий, находится в `ProfileSettingsView`
  и до диспетча события параллельно (без `await`) запускает
  `AppCacheService.clearAllCache()` — фактически более широкую очистку, чем
  документирует изолированный `AuthRepository.logout()` (см. «Альтернативные
  потоки»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестами на уровне
`AuthBloc`/`AuthRepository`; сквозной UI-путь (гонка с `clearAllCache()`,
самозапуск повторного события, переключение `ProfilePage` на `LoginView`)
верифицирован только чтением исходного кода, не отдельным тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_ProfileSettingsButtons` | CURRENT | кнопка «Выйти»: навигация, `clearAllCache()` (без `await`), диспетч `AuthEventLogout()` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventLogout>` | CURRENT | оркестрирует выход: `AuthSplashScreen` → (если `clearData`) `logout()` → `AuthLogout` → `_emitInitial` |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventLogout` | CURRENT | событие с полем `clearData`, default `true` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSplashScreen`, `AuthLogout`, `AuthInitial` | CURRENT | эмитируемые состояния основного потока |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | `isAuthorized()`-проверка, `box.clear()` над `AUTH_BOX`, сброс кэш-флага, публикация `false` в `getAuthStream()` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getAuthBox`, `authBoxKey`, `loginBoxKey`, `developerBoxKey` | CURRENT | ключи трёх Hive-боксов сессии |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getAuthStream` | CURRENT | broadcast-стрим, повторно подписанный конструктором `AuthBloc` (источник самозапуска, см. «Альтернативные потоки») |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearAllCache`, `clearHiveBoxes`, `setAuthorizedFlag` | CURRENT | параллельная (гонка) очистка всех четырёх Hive-боксов, вызванная UI-кнопкой до диспетча события |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | на `AuthLogout` диспетчит `DataUpdateClear()`; рендерит `LoginView`, когда `ProfileEditCubit.currentUserData == null` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | `_authRepository.isAuthorized() == false` → `currentUserData: null`, что переключает `ProfilePage` на экран входа |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `User`, `UserHive` | CURRENT | сущность, хранящаяся тем же ключом `AUTH_BOX`, стираемая вместе с токеном |

## Критерии приёмки

- Нажатие «Выйти» на экране настроек профиля при активной сессии приводит к
  вызову `AuthRepository.logout()` ровно один раз с `clearData: true`.
- После завершения обработчика `AUTH_BOX` не содержит ни главного токена, ни
  `User`, ни серверных интеграций — `AuthRepository.isAuthorized()`
  возвращает `false`.
- `AuthBloc` эмитит последовательность `AuthSplashScreen()` → `AuthLogout()`
  → `AuthInitial` (порядок и состав именно такой, без промежуточных
  ошибочных состояний).
- Пользователь визуально оказывается на экране входа (`LoginView`), а не на
  `ProfileView`.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-16/UC-18 — AuthEventLogout'`, test
`'clearData: true -> вызывает logout() у репозитория'`.

`test/repositories/auth_repository_test.dart`, group `'UC-16 — logout'`,
test `'авторизован -> очищает authBox и эмитит false в стрим'`.

## Открытые вопросы и ограничения

- **Гонка между `AppCacheService.clearAllCache()` и `AuthEventLogout`.**
  Кнопка вызывает `clearAllCache()` без `await` перед диспетчем события —
  ничто в коде не гарантирует порядок между этой чисткой (всех четырёх
  Hive-боксов) и внутренним `box.clear()` `AuthRepository.logout()`. Итоговый
  результат идентичен независимо от порядка, но незащищённая гонка сама по
  себе — наблюдаемый факт текущей реализации, не документированный ни в
  [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), ни в [EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md) (обе описывают только изолированный
  `AuthRepository.logout()`, для которого `LOGIN_BOX`/`DEVELOPER_BOX`
  переживают выход — это верно только для самого `logout()`, но не для
  полного пути кнопки «Выйти»).
- **Самозапуск второго `AuthEventLogout(clearData: false)`.** Реальный
  (не замоканный) `AuthRepository.logout()` публикует `false` в тот же
  стрим, на который подписан конструктор `AuthBloc` — это добавляет в
  очередь ещё один проход обработчика сразу после первого. Эффект
  безобиден (повторная идентичная последовательность состояний), но
  отдельным тестом с реальным (не замоканным) репозиторием не покрыт —
  видно только при совместном чтении `auth_bloc.dart` и
  `auth_repository.dart`.
- **`_login`/`_password` в `AuthBloc` переживают logout в памяти.** Поля
  очищаются только явными событиями `AuthEventSetLogin`/`AuthEventSetPassword`,
  не самим `AuthEventLogout` — экран входа может показать ранее введённый
  логин, даже когда персистентное хранилище (`LOGIN_BOX`) уже стёрто гонкой
  из предыдущего пункта.
- **`DataUpdateClear()` на `AuthLogout`** — сброс sync-состояния при выходе
  принадлежит будущему модулю SYSTEM (ещё не специфицирован отдельным
  `MOD-*`); здесь зафиксирован только как наблюдаемый факт полного
  пользовательского сценария, без отдельного `ENT`/`EVT` id для него.
