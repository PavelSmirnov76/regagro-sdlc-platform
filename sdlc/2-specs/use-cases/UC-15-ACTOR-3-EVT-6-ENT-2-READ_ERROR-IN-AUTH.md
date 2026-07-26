# UC-15 — Приложение проверяет сессию при холодном старте (техническая ошибка)

## Назначение

При каждом холодном старте приложение автоматически пытается восстановить
сессию и (если есть сеть) обновить профиль пользователя с сервера. Если на
этом шаге происходит техническая ошибка (сбой БД или сети на грани, не
осознанный отказ сервера) — приложение не должно зависнуть на сплэше:
сессия принудительно очищается, пользователю на мгновение показывается общее
сообщение об ошибке, и он оказывается на пустом экране входа.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — приложение действует автоматически, до какого-либо
ввода пользователя; человек ([ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)/[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md)) на этом шаге ничего не
инициирует, только наблюдает результат.

## CURRENT

### Основной поток

1. Приложение стартует холодным стартом. `MyApp.build` создаёт `AuthBloc` и
   сразу добавляет `AuthEventStart()` (`BlocProvider<AuthBloc>` в
   `lib/main.dart`), до любого пользовательского ввода.
2. `AuthBloc.on<AuthEventStart>` получает версию приложения через
   `PackageInfo.fromPlatform()` и эмитит `AuthSplashScreen(appVersion)`.
3. Bloc проверяет сеть (`NetworkConnectivityService.hasConnection()`) и
   вызывает `await AuthRepository.init(fromApi: isNetworkConnected)`.
4. Внутри `AuthRepository.init` — если ранее была сохранена авторизованная
   сессия (главный токен в `AUTH_BOX`) и `fromApi == true`, метод пытается
   обновить профиль пользователя с сервера (`updateUserData()` →
   `_getUserFromApi`); либо любая другая операция внутри `init` (запись
   `AppCacheService.setAuthorizedFlag`, публикация в `_authStreamController`)
   технически может бросить исключение при сбое БД/сети на грани.
5. Тело `init` целиком обёрнуто в собственный `try/catch`: при любом
   исключении внутри него метод сам (в этом порядке) — выставляет
   `AppCacheService.setAuthorizedFlag(false)`, вызывает и дожидается
   (`await`) `AuthRepository.logout()` (стирает весь `AUTH_BOX` — главный
   токен, `User`, серверные интеграции — разом, не по ключам; `LOGIN_BOX` и
   `DEVELOPER_BOX` не трогает), и пробрасывает наверх не исходное
   исключение, а голую строку `'error_loading'`.
6. Эта строка долетает до `catch (e)` в `AuthBloc.on<AuthEventStart>` как
   `e`. Строка `_login = _authRepository.getLogin()` (обычно восстанавливает
   последний сохранённый логин из `LOGIN_BOX`) стоит в коде **после** вызова
   `init()` и поэтому не выполняется — поле `_login` bloc'а остаётся с тем
   значением, что было (по умолчанию `''` на свежесозданном `AuthBloc`).
7. Bloc логирует ошибку через `Talker`
   (`getIt<Talker>().error('${'authorization_error'} $e', e)` — префикс
   `authorization_error` уходит только в лог, не показывается пользователю),
   затем эмитит `AuthMessage(e.toString())`. Для реального (не мокнутого)
   пути `e` — строка `'error_loading'`, поэтому `e.toString()` возвращает её
   же без изменений.
8. Bloc сам, ещё раз, вызывает `_authRepository.logout()` — но без `await`
   (fire-and-forget). Поскольку `init()` уже выполнил свой `await logout()`
   до пробрасывания исключения, сессия к этому моменту уже пуста
   (`isAuthorized() == false`), поэтому второй вызов идёт по короткому пути
   `logout()` (`if (!isAuthorized()) { setAuthorizedFlag(false); return; }`)
   и не трогает Hive повторно.
9. Bloc вызывает `await _emitInitial(emit)` — заново читает версию приложения
   и эмитит терминальное состояние `AuthInitial(login: '', password: '',
   appVersion: ...)`.
10. `ProfilePage`'s `BlocListener<AuthBloc, AuthState>` реагирует на
    `AuthMessage`, показывая `SnackBar` с `l10n.tr(state.message)` — для
    ключа `error_loading` это, например, «При загрузке данных произошла
    ошибка» (см. `app_ru.arb`). Поскольку `AUTH_BOX` уже пуст,
    `ProfileEditCubit.load` (слушает `AuthRepository.getAuthBoxListenable`
    по ключу `AuthRepository.userKey`) перезагружается и, так как
    `AuthRepository.isAuthorized()` теперь `false`, показывает `LoginView`
    вместо `ProfileView` — пользователь видит пустую форму входа, а не
    бесконечный сплэш.

### Альтернативные потоки

- **Ошибка возникает без сети (`fromApi == false`).** Единственный
  оставшийся источник исключения внутри `init()` — локальная операция
  (Hive-запись флага/токена, публикация в стрим), т.к. `updateUserData()` не
  вызывается совсем. Это в точности случай «сбой БД» из условия сценария:
  результат для пользователя идентичен основному потоку (`AuthMessage` →
  `logout()` → `AuthInitial`).
- **`AuthEventStart` повторно диспатчится не на самом первом старте, а когда
  в bloc'е уже накоплены `_login`/`_password`** (например, пользователь успел
  ввести логин/пароль через `AuthEventSetLogin`/`AuthEventSetPassword`, а
  затем что-то заново вызвало `AuthEventStart`). `_emitInitial` использует
  текущие значения полей `_login`/`_password`, а не сбрасывает их — в этом
  варианте экран входа при ошибке покажет уже введённый пользователем текст,
  а не пустые поля.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность события [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md) по определению; на этом
  пути она дважды принудительно очищается (`AuthRepository.logout()` внутри
  `init()`, затем ещё раз, без `await`, внутри `AuthBloc`), а кэшированный
  флаг `AppCacheService.isAuthorized` выставляется в `false`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — если до старта была сохранена авторизованная
  сессия, `init()` пытается обновить `User` через `updateUserData()`
  (`_getUserFromApi`); при ошибке сохранённый `User` не обновляется и
  стирается вместе со всем `AUTH_BOX` при `logout()`.

### Бизнес-правила

- Любое исключение внутри `AuthRepository.init()` обрабатывается одинаково
  независимо от причины (сеть или локальное хранилище) — репозиторий не
  различает их и всегда сообщает один и тот же фиксированный ключ перевода
  `error_loading`.
- Сессия на этом пути очищается дважды: один раз (с `await`) внутри
  `AuthRepository.init()` до пробрасывания исключения, второй раз (без
  `await`, fire-and-forget) внутри `AuthBloc.on<AuthEventStart>`'s
  `catch`-блока. Второй вызов фактически безопасен (короткий путь при уже
  неавторизованной сессии), но не гарантированно завершается до эмита
  `AuthInitial`, так как не дожидается своего `Future`.
- `LOGIN_BOX` (запомненный логин) на этом пути не читается в поле `_login`
  bloc'а — `getLogin()` стоит в коде после вызова `init()` и пропускается при
  исключении, поэтому пользователь видит пустую форму входа, а не
  предзаполненный логин, даже если тот сохранён на устройстве.
- Сообщение пользователю — фиксированный i18n-ключ `error_loading`,
  одинаковый с любым другим местом приложения, использующим этот же ключ;
  пользователь не может по одному только тексту отличить «сессия/БД не
  восстановилась при старте» от любой другой генерической ошибки загрузки.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/main.dart` | `MyApp.build` | CURRENT | создаёт `AuthBloc` и сразу добавляет `AuthEventStart()` при холодном старте |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | CURRENT | catch-блок: логирование, `AuthMessage`, повторный (не await'нутый) `logout()`, переход к `AuthInitial` через `_emitInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._emitInitial` | CURRENT | эмитит терминальное состояние `AuthInitial(login: _login, password: _password, appVersion)` — `_login`/`_password` не были обновлены из репозитория на этом пути |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.init` | CURRENT | оборачивает `fromApi`-обновление профиля; при любом исключении сам сбрасывает кэш-флаг, вызывает (`await`) `logout()` и пробрасывает строку `'error_loading'` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | стирает весь `AUTH_BOX` разом; короткий путь при уже неавторизованной сессии — только повторная установка кэш-флага |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getLogin` | CURRENT | на этом пути не вызывается (исключение из `init()` происходит раньше этой строки в bloc'е) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUserData` | CURRENT | источник возможной сетевой ошибки внутри `init()`, если ранее была сохранена авторизованная сессия |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthMessage` / `AuthInitial` | CURRENT | терминальные состояния этой ветки |
| `lib/l10n/app_localization.dart` | `AppLocalization.tr` (case `'error_loading'`) | CURRENT | резолвит ключ `error_loading` в локализованный текст, показанный пользователю |
| `lib/pages/profile/presentation/profile_page.dart` | `ProfilePage` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | показывает `SnackBar` с `l10n.tr(state.message)` при `AuthMessage` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | реактивно перезагружается по Hive-listener'у на `AuthRepository.userKey`; после очистки `AUTH_BOX` показывает `LoginView` вместо `ProfileView` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.setAuthorizedFlag` | CURRENT | кэшированный флаг авторизации, выставляется в `false` дважды на этом пути (внутри `init()` и внутри `logout()`) |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | определяет `fromApi` при вызове `init()`, проверяется до исключения |

## Критерии приёмки

- Если `AuthRepository.init(fromApi: ...)` бросает исключение при
  `AuthEventStart`, `AuthBloc` эмитит ровно последовательность:
  `AuthSplashScreen(appVersion)` → `AuthMessage(...)` → `AuthInitial(...)`.
- `AuthRepository.logout()` вызывается (хотя бы один раз) в рамках обработки
  этой ошибки — сессия не остаётся частично авторизованной.
- Итоговое состояние — `AuthInitial`, не `AuthFailure`/не зависание на
  `AuthSplashScreen`/`AuthInProgress` — пользователь получает управляемый,
  видимый экран входа, а не тупик.
- Сообщение, попавшее в `AuthMessage.message`, — это `e.toString()` от
  пойманного исключения без дополнительной обработки/маскировки в bloc'е.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-13/UC-14/UC-15 — AuthEventStart'`, test
`'исключение -> AuthMessage, logout, AuthInitial'`.

## Открытые вопросы и ограничения

- Второй вызов `_authRepository.logout()` внутри `AuthBloc`'s `catch`-блока
  не имеет `await` — это fire-and-forget вызов, чей `Future` не
  гарантированно завершается до эмита `AuthInitial`. На практике не влияет
  на наблюдаемое поведение, потому что `AuthRepository.init()` уже выполнил
  свой собственный (awaited) `logout()` до пробрасывания исключения, и
  сессия к этому моменту уже пуста — но это осознанно не проверенное кодом
  допущение, а не гарантия порядка выполнения.
- Тест мокает `AuthRepository.init` напрямую через `mocktail`, бросая
  `Exception('db error')`, — это проверяет обработку исключения в
  `AuthBloc`, но не проверяет реальную внутреннюю логику `init()` (что она
  сама уже вызывает `logout()` и переводит любое исключение в фиксированную
  строку `'error_loading'`); эта часть верифицирована только чтением кода
  `AuthRepository.init`, отдельного теста на неё нет.
- Сообщение `error_loading` — общий ключ, используемый и в других частях
  приложения; из самого текста пользователь не может понять, что именно
  сессия не восстановилась при старте, а не любая другая ошибка загрузки
  данных.
