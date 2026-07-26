# UC-6 — Автовход после регистрации или сброса пароля (успех)

| | |
|---|---|
| Актор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Событие | [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) |
| Сущность | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |

## Назначение

Сразу после того как гость успешно завершил саморегистрацию либо успешно сбросил пароль по коду, приложение само выполняет вход тем же email и (актуальным на этот момент) паролем — без повторного экрана логина и без ручного действия пользователя. Успешный результат — новая авторизованная сессия ([ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)) записана, пользователь оказывается на главном экране так же, как после обычного ручного входа.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — гость. В момент срабатывания сценария главный токен ещё не выдан: пользователь только что отправил форму регистрации либо форму сброса пароля, `AuthRepository.isAuthorized()` до этого момента возвращает `false`.

## CURRENT

### Основной поток

1. Гость успешно завершает саморегистрацию ([EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md), [UC-1](UC-1-ACTOR-2-EVT-1-ENT-1-CREATE_OK-IN-AUTH.md)) через `RegistrationCubit.submit` либо успешно завершает сброс пароля по коду ([EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), [UC-10](UC-10-ACTOR-2-EVT-5-ENT-1-UPDATE_OK-IN-AUTH.md)) через `ForgotPasswordCubit` — в обоих случаях итоговое состояние кубита несёт email и (новый) пароль, введённые/подтверждённые пользователем.
2. `BlocConsumer`-слушатель экрана видит успех: `RegistrationView` проверяет `state.isSuccess`, `ForgotPasswordView` — ветку `success` через `state.whenOrNull`. В обоих случаях слушатель показывает `SnackBar` об успехе и сразу же, без участия пользователя, отправляет в общий `AuthBloc` событие `AuthEventAuthAfterRegistration(email, password)`.
3. `AuthBloc.on<AuthEventAuthAfterRegistration>` — отдельный обработчик, не переиспользующий `on<AuthEventAuth>` напрямую. Он записывает переданные login/password в приватные поля блока (`_login`/`_password`) и вызывает общий приватный хелпер `AuthBloc._auth`, тот же самый, что использует ручной вход.
4. `AuthBloc._auth` эмитит `AuthInProgress()` и вызывает `AuthRepository.login(login: _login, password: _password)`.
5. `AuthRepository.login` проверяет соединение, запрашивает токен у API, при успехе получает профиль пользователя, сохраняет токен и пользователя в зашифрованный Hive-бокс сессии (`AuthRepository._saveMainAuthData`), запоминает логин (`AuthRepository._saveLogin`), выставляет кэшированный флаг авторизации (`AppCacheService.setAuthorizedFlag(true)`) и публикует `true` в поток авторизации.
6. `AuthBloc._auth` читает сохранённого пользователя через `AuthRepository.getUser()` и эмитит `AuthToMain(user)` — тот же терминальный успех, что и у обычного ручного входа ([UC-3](UC-3-ACTOR-2-EVT-2-ENT-2-CREATE_OK-IN-AUTH.md)).
7. Приложение переходит с экрана регистрации/сброса пароля на главный экран — так же, как после обычного входа.

### Альтернативные потоки

- **Сервер отклоняет логин/пароль или сеть обрывается во время вызова.** `AuthRepository.login` выбрасывает исключение (`invalid_login_password` либо `Internet connection required`, если соединения нет ещё до сетевого вызова). В отличие от `on<AuthEventAuth>`, обработчик `on<AuthEventAuthAfterRegistration>` не оборачивает `_auth` в try/catch — исключение вылетает необработанным из обработчика блока, стрим блока застревает на `AuthInProgress()`, экран показывает бесконечный лоадер без сообщения об ошибке и без возврата к рабочему состоянию. Это отдельный сценарий (`ERROR`), не входит в объём этого use-case.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session) — главная сущность перехода: главный токен и вычисляемый флаг `isAuthorized()` появляются именно здесь.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — профиль пользователя запрашивается и сохраняется в той же операции, вместе с токеном, в том же Hive-боксе.

### Бизнес-правила

- Автовход всегда переиспользует те же самые email и пароль, которые пользователь только что использовал для регистрации/сброса — отдельного запроса учётных данных нет.
- Использует тот же сетевой путь входа (`AuthRepository.login`), что и обычный ручной вход ([EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md)) — специального «постregistration»-эндпоинта нет.
- Как и все сценарии [MOD-1](../modules/MOD-1-AUTH.md), вызов полностью online-only: нет локального черновика, нет отложенной синхронизации — сценарий ждёт прямого ответа сервера.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью реализован, TARGET не добавляет нового объёма работы.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuthAfterRegistration>` | CURRENT | обработчик события: сохраняет login/password, вызывает общий `_auth` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._auth` | CURRENT | эмитит `AuthInProgress`, вызывает `AuthRepository.login`, эмитит `AuthToMain` |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventAuthAfterRegistration` | CURRENT | событие, несущее login+password из формы регистрации/сброса |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthToMain` | CURRENT | терминальное состояние успеха, общее с ручным входом |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.login` | CURRENT | сетевой вызов входа, сохранение токена+пользователя, выставление флага авторизации |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._saveMainAuthData` | CURRENT | запись токена и пользователя в `AUTH_BOX` |
| `lib/pages/registration/presentation/widgets/registration_view.dart` | `RegistrationView.build` (`BlocConsumer` listener) | CURRENT | по успеху `RegistrationCubit` отправляет `AuthEventAuthAfterRegistration` |
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `ForgotPasswordView.build` (`BlocConsumer` listener) | CURRENT | по успеху `ForgotPasswordCubit` отправляет `AuthEventAuthAfterRegistration` |

## Критерии приёмки

- После успешной саморегистрации ([EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)) `AuthBloc` без дополнительного действия пользователя получает `AuthEventAuthAfterRegistration` с тем же email и паролем, которые были отправлены на регистрацию.
- После успешного сброса пароля ([EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)) `AuthBloc` без дополнительного действия пользователя получает `AuthEventAuthAfterRegistration` с тем же email и новым паролем.
- При успешном ответе сервера на `AuthRepository.login` блок проходит через `AuthInProgress()` и завершается `AuthToMain(user)`.
- После `AuthToMain(user)` `AuthRepository.isAuthorized()` возвращает `true`, а `AuthRepository.getUser()` возвращает того же пользователя, что получен от API.
- Приложение переходит на главный экран, как и после обычного ручного входа ([UC-3](UC-3-ACTOR-2-EVT-2-ENT-2-CREATE_OK-IN-AUTH.md)).

## Связанные тесты

`TBD — теста нет` для успешной ветки. В `test/blocs/auth_bloc_test.dart` группа `'UC-6/UC-7 — AuthEventAuthAfterRegistration'` существует, но покрывает только ошибочную ветку того же события (необработанное исключение `login()`, зависание на `AuthInProgress()`) — это тест другого сценария (`ERROR`, [UC-7](UC-7-ACTOR-2-EVT-3-ENT-2-CREATE_ERROR-IN-AUTH.md)), не данного (`CREATE_OK`). Отдельного успешного теста на `AuthEventAuthAfterRegistration` в файле нет (успешный сценарий покрыт только для обычного `AuthEventAuth` в группе `'UC-3/UC-4/UC-5 — AuthEventAuth'`, который вызывает тот же `AuthRepository.login`/`_auth`, но не тот же обработчик события).

## Открытые вопросы и ограничения

- Успешная ветка `AuthEventAuthAfterRegistration` не имеет собственного теста — сегодня она проверяется только транзитивно, через тест на `AuthEventAuth` (тот же `_auth`-хелпер), но не через сам обработчик `on<AuthEventAuthAfterRegistration>`.
- Отсутствие try/catch в этом обработчике (см. «Альтернативные потоки») — известный дефект, задокументированный отдельно в [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) и покрываемый отдельным use-case на `ERROR`; здесь упомянут только как контекст, почему успешный путь и обработка ошибок не симметричны с [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md).
