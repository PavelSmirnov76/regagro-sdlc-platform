# UC-13 — Приложение восстанавливает существующую сессию при холодном старте

## Назначение

При каждом холодном старте приложение само (без какого-либо ввода
пользователя) проверяет, есть ли уже сохранённая сессия авторизации.
Если главный токен уже сохранён с прошлого запуска — сессия читается и
используется как есть: пользователь не видит экран входа, а сразу
попадает в авторизованную часть приложения.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — само приложение, действующее автоматически до
какого-либо человеческого жеста; никакой актор-человек это действие не
инициирует.

## CURRENT

### Основной поток

1. Холодный старт процесса приложения: `MyApp.build` (`lib/main.dart`)
   создаёт `BlocProvider<AuthBloc>` с
   `AuthBloc()..add(AuthEventStart())` — событие диспатчится ровно один
   раз, при первой сборке корневого виджета, раньше любого действия
   пользователя.
2. `AuthBloc.on<AuthEventStart>` читает версию приложения
   (`PackageInfo.fromPlatform()`) и эмитит
   `AuthSplashScreen(appVersion: appVersion)`.
3. Проверяется наличие сети:
   `getIt<NetworkConnectivityService>().hasConnection()`.
4. Вызывается `AuthRepository.init(fromApi: isNetworkConnected)`:
   - если сеть есть (`fromApi == true`) — `init` вызывает
     `updateUserData()`, которая читает уже сохранённый главный токен
     (`getMainTokenData()`); токен найден (это условие данного
     сценария — сессия уже существовала до этого запуска), поэтому
     `updateUserData` запрашивает свежий профиль с сервера
     (`_getUserFromApi(tokenDataMain.bearerToken)`) и перезаписывает
     локально сохранённого `User` через `_saveMainAuthData(user:
     userDTO)` — как побочный эффект этот же вызов безусловно
     перезаписывает `serverIntegrationsKey` пустым списком и повторно
     вызывает `AppCacheService.saveIntegrationDirection()`, так как
     `updateServerIntegrations` по умолчанию `true`;
   - вне зависимости от сети `init` затем выставляет
     `AppCacheService.setAuthorizedFlag(isAuthorized())` и публикует
     `isAuthorized()` в `getAuthStream()`.
5. `AuthBloc` читает запомненный логин из `LOGIN_BOX`
   (`_authRepository.getLogin()`) и сохраняет его в собственном поле
   `_login` — используется только если пользователь позже откроет экран
   ручного входа повторно, на этот сценарий не влияет.
6. `_authRepository.isAuthorized()` (буквально `getMainTokenData() !=
   null`) возвращает `true` — главный токен уже был сохранён в
   `AUTH_BOX` до этого запуска. Это единственное условие, отличающее
   данный сценарий («сессия уже существовала») от параллельного
   («сессии не было») — сессия здесь **читается и переиспользуется**,
   не создаётся заново.
7. `AuthBloc` эмитит `AuthToMain(_authRepository.getUser()!)` —
   локально сохранённый (и, если была сеть, только что обновлённый с
   сервера) `User` читается из `AUTH_BOX` и передан ненулевым. Это
   состояние слушает `BlocListener<AuthBloc, AuthState>` в
   `MainPage.build` (`lib/pages/main/main_page.dart`), которая
   направляет в авторизованную оболочку приложения и, отдельно, как
   побочный эффект вне границ модуля `AUTH` (владеет `SYSTEM`),
   запускает `DataUpdateBloc.add(DataUpdateStartAll(...))`.
8. `AuthBloc` сразу эмитит ещё раз `const AuthSplashScreen()`.
9. Пауза `Future.delayed(const Duration(milliseconds: 500))`.
10. `AuthBloc._emitSuccess` очищает поле `_password` (не относится к
    этому сценарию — остаток от ручного входа), заново читает версию
    приложения и эмитит `AuthSuccess(appVersion: appVersion)` —
    терминальное состояние сценария.

### Альтернативные потоки

- **Сессия уже существовала, но сети при старте нет.** `fromApi ==
  false` → `AuthRepository.init` не вызывает `updateUserData()` вовсе —
  шаг 4 просто выставляет флаг и стрим по уже известному
  `isAuthorized()`, профиль с сервера не запрашивается, используется
  исключительно локально сохранённый `User`. Дальше (шаги 5–10) —
  идентично основному потоку. Это отдельная ветвь того же [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md), не
  отдельный use-case (тот же `RESULT`), но в текущем тестовом наборе
  явно не покрыта для авторизованной ветки — единственный
  «нет соединения»-тест сценария (`test/blocs/auth_bloc_test.dart`)
  проверяет ветку `isAuthorized() == false`, не эту.
- **Обновление профиля с сервера падает исключением.** Если
  `updateUserData()` бросает (например `_getUserFromApi` — сетевая
  ошибка/ошибка сервера), исключение перехватывается собственным
  `try/catch` внутри `AuthRepository.init`, которое **выставляет флаг
  авторизации в `false`, вызывает `logout()` (полностью очищает
  `AUTH_BOX`, включая только что перезаписанный токен) и перебрасывает
  `'error_loading'`** — это уничтожает уже существовавшую валидную
  сессию, а не просто пропускает обновление профиля (см. «Бизнес-правила»).
  Исключение дальше ловится внешним `try/catch` в
  `AuthBloc.on<AuthEventStart>`: логируется через `Talker`, эмитится
  `AuthMessage(e.toString())`, повторно вызывается
  `_authRepository.logout()`, эмитится `AuthInitial` — другой результат
  того же события (`_ERROR`), не описывается этим файлом.
- **Токена не было вовсе (`isAuthorized() == false`) на этом же
  событии** — гостевой холодный старт (первый запуск с автовыдачей
  гостевого доступа либо повторный гостевой запуск) — другой актор-ответ
  на тот же [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md), отдельный сценарий, не описывается этим файлом.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md) по определению и главный
  предмет чтения: главный токен (`AUTH_BOX`/`tokenMainDataKey`) — это
  то, что и проверяется, и переиспользуется; запомненный логин
  (`LOGIN_BOX`) читается попутно; дублирующий кэшированный флаг
  авторизации (`AppCacheService`) синхронизируется вручную на каждом
  шаге.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — читается из `AUTH_BOX` (`getUser()`) и, при
  наличии сети, перезаписывается свежей копией с сервера ещё до того,
  как `AuthBloc` её прочитает.

### Бизнес-правила

- Единственный критерий «сессия уже существовала» —
  `AuthRepository.isAuthorized()`, то есть наличие сохранённого
  главного токена; никакая дополнительная проверка (срок действия
  токена, состояние пользователя на сервере и т.п.) на этом шаге не
  выполняется.
- Обновление профиля с сервера при старте — попытка «лучших усилий», но
  не мягкая: она делается только при наличии сети, однако если сеть
  есть и запрос всё же завершается ошибкой, это не деградирует до
  «остались при локальных данных» — весь `init()` считается провалом,
  локальная сессия удаляется (`logout()`) и пользователь получает
  `AuthMessage` вместо восстановленной сессии. Отсутствие сети в момент
  проверки (`hasConnection() == false`) и наличие сети с последующей
  ошибкой запроса — два разных исхода одного и того же события с
  диаметрально противоположным результатом для одной и той же валидной
  сессии.
- Восстановление сессии — это чтение и переиспользование уже
  сохранённых данных: ни новый токен, ни новая запись `User` на этом
  шаге не создаются (создание — предмет других use-case'ов, например
  входа по логину/паролю).
- Переход в `AuthSuccess` происходит безусловно спустя фиксированную
  паузу в 500 мс после `AuthToMain` — не по какому-либо событию или
  подтверждению, чисто по таймеру.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и покрыт тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/main.dart` | `MyApp.build` | CURRENT | создаёт `AuthBloc` и диспатчит `AuthEventStart()` один раз при холодном старте |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | CURRENT | оркестрирует сценарий: splash → проверка сети → `init` → ветвление по `isAuthorized()` → `AuthToMain` → пауза → `AuthSuccess` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._emitSuccess` | CURRENT | завершающий переход: очищает `_password`, эмитит `AuthSuccess` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthToMain` | CURRENT | состояние с восстановленным `User?` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSplashScreen` | CURRENT | промежуточное/начальное состояние |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSuccess` | CURRENT | терминальное состояние сценария |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.init` | CURRENT | условное обновление профиля с сервера + синхронизация флага авторизации/стрима |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUserData` | CURRENT | запрос свежего профиля с сервера при наличии главного токена, вызывается изнутри `init` только если есть сеть |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | `getMainTokenData() != null` — критерий «сессия уже существовала» |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getMainTokenData` | CURRENT | чтение главного токена из `AUTH_BOX` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser` | CURRENT | чтение сохранённого `User` из `AUTH_BOX` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getLogin` | CURRENT | чтение запомненного логина из `LOGIN_BOX` |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | проверка сети, определяющая `fromApi` |
| `lib/pages/main/main_page.dart` | `MainPage.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | потребляет `AuthToMain` для маршрутизации в авторизованную оболочку; попутно инициирует кросс-модульный (`SYSTEM`) sync-проход — вне границ этого файла |

## Критерии приёмки

- При холодном старте, если `AuthRepository.isAuthorized()` уже
  `true` до вызова `AuthEventStart`, `AuthBloc` эмитит строго
  последовательность: `AuthSplashScreen(appVersion)` →
  `AuthToMain(user)` с ненулевым `user` → `AuthSplashScreen()` →
  (после паузы ~500 мс) `AuthSuccess(appVersion)`.
- Экран входа/регистрации пользователю не показывается — сессия
  используется как есть, без повторной аутентификации.
- При наличии сети (`isNetworkConnected == true`) `AuthRepository.init`
  вызывается с `fromApi: true`, что запускает обновление профиля с
  сервера; при отсутствии сети — с `fromApi: false`, без сетевого
  запроса, только на локальных данных.
- `user` в `AuthToMain` — результат `AuthRepository.getUser()`,
  считанный после `init()` (то есть уже с учётом возможного
  серверного обновления).

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-13/UC-14/UC-15 — AuthEventStart'`,
test `'авторизован -> AuthToMain(user), затем SplashScreen, затем
(после задержки) AuthSuccess'`.

## Открытые вопросы и ограничения

- Ветка «сессия уже существовала, но сети при старте нет»
  (`fromApi: false` при `isAuthorized() == true`) не имеет отдельного
  проходящего теста в текущем наборе — существующий «нет
  соединения»-тест того же `group` проверяет только неавторизованную
  ветку. Поведение для авторизованной ветки без сети верифицировано
  чтением кода (`AuthRepository.init`, `updateUserData`), не тестом.
- Ошибка при попытке обновить профиль с сервера (сеть была, запрос
  упал) полностью уничтожает уже существовавшую валидную локальную
  сессию (`logout()` внутри `init`'s catch) вместо того, чтобы
  деградировать до уже сохранённых локальных данных — то же самое, что
  происходит при полном отсутствии сети, но с противоположным для
  пользователя исходом (сессия сохранена vs сессия уничтожена) при
  внешне похожей причине («не удалось получить свежие данные»). Это
  поведение существующего кода, не предмет исправления в этом проходе
  документации.
- Побочный запуск кросс-модульного sync-прохода
  (`DataUpdateBloc.add(DataUpdateStartAll(...))`) из `MainPage` при
  получении `AuthToMain` — факт, зафиксированный при чтении кода, но
  принадлежит границе модуля `SYSTEM` (см. [MOD-1](../modules/MOD-1-AUTH.md), «Граница»), не
  описывается здесь подробнее.
