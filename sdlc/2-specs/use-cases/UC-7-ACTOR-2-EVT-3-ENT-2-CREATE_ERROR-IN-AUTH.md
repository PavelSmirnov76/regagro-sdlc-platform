- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)

# UC-7 — Автовход после регистрации/сброса пароля падает без сообщения (известный дефект)

| | |
|---|---|
| Актор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Событие | [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) |
| Сущность | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| Результат | `CREATE_ERROR` |

## Назначение

Тот же автовход, что и в успешном сценарии [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) (сразу после саморегистрации
или сброса пароля приложение само вызывает `login()` тем же email и паролем,
без повторного экрана логина) — но здесь сетевой вызов `AuthRepository.login`
падает с ошибкой. Обработчик `AuthBloc.on<AuthEventAuthAfterRegistration>` не
оборачивает вызов в try/catch вообще (в отличие от обычного входа через
`AuthEventAuth`), поэтому исключение никогда не превращается в понятное
пользователю состояние — оно просто теряется. Это задокументированный,
воспроизводимый тестом дефект, а не альтернативный, но корректно
обработанный путь.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — Гость. Он не инициирует это конкретное действие напрямую (не
нажимает «войти») — оно срабатывает автоматически сразу после того, как гость
успешно завершил саморегистрацию либо сброс пароля по коду.

## CURRENT

### Основной поток

1. Гость успешно завершает саморегистрацию (`RegistrationCubit.submit`,
   отдельный use-case на [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)) либо сброс пароля по коду
   (`ForgotPasswordCubit.resetPassword`, отдельный use-case на [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)).
2. Экран-инициатор реагирует на собственный успех: `RegistrationView` — на
   `RegistrationState.isSuccess`, `ForgotPasswordView` — на
   `ForgotPasswordState.success` — показывает свой собственный snackbar
   «successful» (относящийся только к регистрации/сбросу, не к входу) и
   диспатчит один и тот же `AuthEventAuthAfterRegistration(login, password)`
   в общий (созданный один раз в `lib/main.dart`, на всё приложение)
   `AuthBloc`.
3. `AuthBloc.on<AuthEventAuthAfterRegistration>` присваивает `_login`/`_password`
   из события и сразу вызывает общий приватный хелпер `_auth(emit)` —
   **без** окружающего `try/catch`, в отличие от обработчика `AuthEventAuth`,
   который вызывает тот же `_auth` внутри своего собственного `try/catch`.
4. `_auth` эмитит `AuthInProgress`, затем вызывает
   `AuthRepository.login(login: _login, password: _password)`.
5. `AuthRepository.login` бросает исключение — например `'Internet connection
   required'` (нет сети), `'invalid_login_password'` (сервер не принял
   логин/пароль), либо любую другую техническую ошибку внутри
   `_getTokenDataFromApi`/`_getUserFromApi` (например необработанный
   `DioException` при сбое сети/сервера в процессе запроса).
6. Поскольку у обработчика нет `try/catch`, исключение вылетает необработанным
   из обработчика события. `AuthBloc` не эмитит после `AuthInProgress`
   абсолютно ничего для этого события — ни `AuthMessage`, ни `AuthInitial`,
   ни `AuthFailure`.
7. Последнее состояние, которое видит весь остальной UI через общий
   `AuthBloc`, так и остаётся `AuthInProgress` — до тех пор, пока какое-то не
   связанное с этим событие (`AuthEventSetLogin`/`AuthEventSetPassword`, или
   новый `AuthEventStart`) случайно не перезапишет его новым состоянием.
8. С точки зрения пользователя: он остаётся на том же экране регистрации/
   сброса пароля, на котором уже увидел свой собственный «successful»
   snackbar; никакого сообщения об ошибке входа нигде не появляется —
   в частности, `BlocListener<AuthBloc, AuthState>` в `ProfilePage`,
   который **показывает** `SnackBar` именно для `AuthMessage`, здесь не
   срабатывает, потому что `AuthMessage` на этом пути никогда не эмитится;
   перехода в основной раздел приложения тоже не происходит (`login()` падает
   до ветки, которая вызывает `AppCacheService.setAuthorizedFlag(true)`, так
   что приложение и не должно считать пользователя вошедшим — но по факту это
   просто тихо повисает, а не явно сообщается).

### Альтернативные потоки

- Если после этого пользователь попадает на `LoginView` (например, через
  `ProfilePage`, когда `ProfileEditCubit.currentUserData == null`, или вручную
  вернувшись назад), кнопка входа рендерится как `isLoading: true` /
  `enabled: false` — она выглядит зависшей в состоянии загрузки, потому что
  `LoginView`'s `BlocBuilder<AuthBloc, AuthState>` читает то же самое
  зависшее состояние `AuthInProgress` общего блока. Это самовосстанавливается,
  как только пользователь начинает печатать в поле email или пароля —
  `AuthEventSetLogin`/`AuthEventSetPassword` безусловно вызывают
  `_emitInitial`, перезаписывая зависшее состояние на `AuthInitial`.
- Независимо от конкретной причины, по которой `AuthRepository.login` бросил
  исключение (нет сети, отклонённые сервером логин/пароль, либо неожиданная
  техническая ошибка внутри сетевых вызовов), отсутствие `try/catch` в
  обработчике сводит все эти случаи к одному и тому же наблюдаемому исходу —
  в коде нет ветки, которая обрабатывала бы их по-разному.
- Два разных экрана-инициатора приводят к одному и тому же обработчику: сразу
  после саморегистрации (`RegistrationView`) и сразу после сброса пароля
  (`ForgotPasswordView`) — оба диспатчат идентичный по форме
  `AuthEventAuthAfterRegistration(login, password)` и попадают в один и тот же
  необёрнутый код.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session / главный токен) — сущность, чьё создание должно было бы
  завершиться этим вызовом, но не завершается: пока `login()` не дошёл до
  `_saveMainAuthData`, ни один ключ сессии в `AUTH_BOX` не записывается —
  главный токен не появляется.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — тот же неудавшийся вызов должен был бы получить и
  сохранить пользователя (`_getUserFromApi` + `_saveMainAuthData(user: ...)`)
  вместе с токеном за один проход; при ошибке до этой точки `User` тоже не
  сохраняется.

### Бизнес-правила

- `AuthEventAuthAfterRegistration` — единственный обработчик из всей группы
  событий `AuthBloc`, вызывающий сетевой `AuthRepository.login` без
  окружающего `try/catch`; оба других обработчика, идущих через сеть
  (`AuthEventAuth`, `AuthEventStart`), ловят исключение и как минимум
  возвращают состояние `AuthInitial` через `_emitInitial`.
- Это не отдельное бизнес-правило «автовход должен молча падать» — это
  немаркированный, воспроизводимый тестом дефект.
- Результат сценария — `CREATE_ERROR`, а не `CREATE_REJECTED`: даже в той
  ветке, где сервер содержательно отклоняет логин/пароль
  (`'invalid_login_password'`), этот отказ никогда не доходит до пользователя
  как осознанно предъявленное решение — он теряется в необработанном
  исключении, поэтому с точки зрения продукта это неразрешённая техническая
  ошибка, а не предъявленный и понятый пользователем отказ.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — CURRENT воспроизводится существующим
тестом. Возможное исправление (обернуть `_auth` в обработчике
`AuthEventAuthAfterRegistration` в `try/catch`, по аналогии с
`AuthEventAuth`) в рамках этого прохода не выполняется — это чисто
документирующий проход по уже существующему коду, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuthAfterRegistration>` | CURRENT | обработчик автовхода без `try/catch` — источник дефекта |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._auth` | CURRENT | общий приватный метод входа, эмитит `AuthInProgress` и вызывает `AuthRepository.login` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventAuth>` | CURRENT | обработчик обычного входа — тот же `_auth`, но обёрнутый в `try/catch`, контраст с дефектом |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventAuthAfterRegistration` | CURRENT | событие-триггер с `login`/`password`, переданными из формы регистрации/сброса пароля |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthInProgress` | CURRENT | состояние, в котором зависает блок |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthMessage` | CURRENT | состояние, которое эмитилось бы при перехваченной ошибке — здесь никогда не эмитится |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.login` | CURRENT | сетевой вызов, источник исключения (нет сети / неверные логин-пароль / иная техническая ошибка) |
| `lib/pages/registration/presentation/widgets/registration_view.dart` | `RegistrationView` | CURRENT | диспатчит `AuthEventAuthAfterRegistration` по `RegistrationState.isSuccess` |
| `lib/pages/registration/cubit/registration_cubit.dart` | `RegistrationCubit.submit` | CURRENT | источник `login`/`password` для этого сценария (саморегистрация) |
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `ForgotPasswordView` | CURRENT | диспатчит `AuthEventAuthAfterRegistration` по `ForgotPasswordState.success` |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.resetPassword` | CURRENT | источник `login`/`password` для этого сценария (сброс пароля) |
| `lib/pages/profile/presentation/widgets/login/login_view.dart` | `LoginView` | CURRENT | побочный эффект: кнопка входа читает то же зависшее `AuthInProgress`, если пользователь позже открывает этот экран |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | показывает `SnackBar` для `AuthMessage` — здесь не срабатывает, т.к. `AuthMessage` не эмитится |
| `lib/main.dart` | `MyApp.build` (`BlocProvider<AuthBloc>`) | CURRENT | `AuthBloc` создаётся один раз на всё приложение — зависшее состояние видно из любого места, где есть `BlocBuilder`/`BlocListener` на этот блок |

## Критерии приёмки

- При падении `AuthRepository.login` внутри обработки
  `AuthEventAuthAfterRegistration` единственное эмитированное состояние —
  `AuthInProgress`; `AuthMessage`, `AuthInitial` и `AuthFailure` не эмитятся.
- Исключение всплывает необработанным на уровне обработчика события
  (наблюдаемо в тесте через параметр `errors`).
- Ни один экран приложения не показывает пользователю сообщение об ошибке в
  результате этого падения (`ProfilePage`'s `BlocListener` на `AuthMessage`
  не срабатывает, т.к. это состояние не эмитируется).
- `AuthBloc` не переходит ни в `AuthInitial`, ни в `AuthFailure` сам по себе —
  выход из зависшего состояния возможен только следующим не связанным
  событием (`AuthEventSetLogin`/`AuthEventSetPassword`/`AuthEventStart`),
  которое безусловно эмитит новое состояние независимо от предыдущего.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-6/UC-7 — AuthEventAuthAfterRegistration'`.

## Открытые вопросы и ограничения

- Стоит ли в будущем привести этот обработчик к тому же паттерну, что и
  `AuthEventAuth` (обернуть `_auth` в `try/catch`, эмитить `AuthMessage` +
  `AuthInitial`) — вопрос продуктового/технического решения, вне рамок этого
  документирующего прохода.
- Реальна ли на практике ветка `'invalid_login_password'` именно в этом
  сценарии (логин/пароль здесь берутся напрямую из только что успешной
  саморегистрации/сброса, а не введены заново пользователем) — код не
  исключает её (например из-за рассинхронизации между сервисом регистрации и
  сервисом входа), но она не подтверждена наблюдением на реальных данных.
- `AuthBloc` не переопределяет `Bloc.onError` — необработанное исключение уходит
  в стандартный `onError` `flutter_bloc`/`Zone`, что означает: единственный
  способ увидеть его в проде — это логи/краш-репортинг уровня фреймворка, а не
  что-то видимое конечному пользователю.
