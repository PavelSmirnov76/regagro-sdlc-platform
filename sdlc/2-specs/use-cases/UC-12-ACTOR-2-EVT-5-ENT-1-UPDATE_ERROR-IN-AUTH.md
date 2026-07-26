# UC-12 — Сброс пароля: ошибка сервера/сети, отличная от невалидного кода, гасится репозиторием (ERROR)

## Назначение

Гость на последнем шаге мастера восстановления пароля вводит новый пароль и
подтверждение и отправляет их на сервер; сервер отвечает ошибкой, отличной от
«код недействителен/истёк» (`error_type == "passwords.token"`), либо не
отвечает вовсе (нет сети/таймаут). По смыслу это ERROR-исход события [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)
(`password_reset.completed` не наступает, пароль не меняется) — но из-за
дефекта в `AuthRepository.resetPassword` эта ошибка гасится на уровне
репозитория и наружу не пробрасывается: `ForgotPasswordCubit` не получает
исключения и эмитит `success`, как будто пароль был успешно изменён.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — гость, тот же актор, что и на остальных шагах
мастера восстановления пароля; главный токен на этот момент ещё не выдан.

## CURRENT

### Основной поток

1. Гость находится на последнем шаге мастера (`ForgotPasswordStep
   .enterNewPassword`, виджет `EnterNewPasswordStep` в
   `forgot_password_view.dart`) — предыдущие шаги (`enterEmail`, `enterCode`)
   уже пройдены. Реальной проверки кода на шаге `enterCode` не происходит:
   `ForgotPasswordCubit.verifyCode()` не делает сетевого вызова, только
   переключает `currentStep`.
2. Гость вводит новый пароль и подтверждение
   (`onNewPasswordChanged`/`onConfirmNewPasswordChanged` →
   `ForgotPasswordCubit.setNewPassword`/`setConfirmNewPassword`) и нажимает
   кнопку (`onResetPassword`) → вызывается `ForgotPasswordCubit
   .resetPassword()`.
3. `resetPassword()` эмитит `ForgotPasswordState.loading(state.data)`, затем
   вызывает `AuthRepository.resetPassword(email, code, newPassword,
   confirmNewPassword)`.
4. Репозиторий отправляет `POST {Constants.authSerivceApi}/reset-password` с
   телом `{'email': email, 'token': code, 'password': newPassword,
   'password_confirmation': confirmNewPassword}` через RPC-клиент
   (`ApiClient`, instance `farm_rpc`).
5. Вызов завершается `DioException`: сервер вернул ошибку с `error_type`,
   отличным от `"passwords.token"` (например, другое бизнес-правило
   валидации), либо `DioException` вообще не несёт `response` (таймаут/нет
   соединения) — в этом случае `e.response?.data['error_type']` равно `null`,
   что тоже не равно `"passwords.token"`.
6. `AuthRepository.resetPassword`'s `on DioException catch (e)` логирует
   ошибку (`Talker.error('AuthRepository: resetPassword: error: $e')`), затем
   проверяет `if (e.response?.data['error_type'] == "passwords.token")` —
   условие ложно, тело `if` не выполняется. **После этой проверки в
   catch-блоке больше ничего нет** — исключение не перебрасывается повторно.
7. Так как `resetPassword` — `async`-функция, чей catch-блок в этом случае
   ничего не бросает и не возвращает, она завершается нормально (`Future
   <void>` без ошибки) — вызывающий код не видит никакого исключения.
8. В `ForgotPasswordCubit.resetPassword()` `await _authRepository
   .resetPassword(...)` завершается без ошибки — выполнение продолжается на
   следующей строке того же `try`-блока: `emit(ForgotPasswordState
   .success(state.data));`. Ни `on ResetPasswordError catch (e)`, ни общий
   `catch (e)` не срабатывают — обе ветки кубита, предназначенные для
   обработки именно таких ошибок, недостижимы в этом случае, потому что
   репозиторий гасит исключение на уровень ниже.
9. `ForgotPasswordView`'s `BlocConsumer.listener` реагирует на `success` как
   на настоящий успех: показывает `SnackBar` с текстом `AppLocalizations
   .of(context)!.successful` и немедленно отправляет в `AuthBloc` событие
   `AuthEventAuthAfterRegistration(data.email, data.newPassword)` — запуская
   автовход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)) с паролем, который на сервере фактически не был
   установлен.
10. Пароль пользователя на сервере остаётся прежним; сам гость не видит
    никакого сообщения об ошибке на этом шаге — единственный след ошибки,
    отправленной сервером, это вызов `Talker.error` внутри репозитория (шаг
    6), не выводимый в UI.

### Альтернативные потоки

- **REJECTED-исход того же события — не входит в этот сценарий.** Если
  `error_type == "passwords.token"` (конкретный код недействителен/истёк),
  репозиторий бросает `ResetPasswordError`, и `ForgotPasswordCubit` явно ловит
  её (`on ResetPasswordError catch (e) { if (e.errorType == "passwords.token")
  ... }`), возвращая гостя на шаг ввода кода с сообщением об ошибке. Сервер в
  этом случае осознанно отклонил конкретный код — это отдельный use-case, не
  описываемый здесь.
- **Ветки кубита для «прочих» ошибок существуют в коде, но недостижимы при
  текущей реализации репозитория — покрыты только изолированными/гипотетическими
  тестами.** Два теста на уровне `ForgotPasswordCubit`
  (`test/pages/forgot_password_cubit_test.dart`) мокают сам метод
  `AuthRepository.resetPassword`, минуя его реальную реализацию, и тем самым
  проверяют ветки кубита в отрыве от реального дефекта репозитория:
  - `'UC-42: generic исключение -> error с текстом исключения'` — мок бросает
    обычный `Exception('network error')` напрямую; кубит ловит его в общем
    `catch (e)` и эмитит `ForgotPasswordState.error` с `errorMessage:
    e.toString()`. В реальном коде репозитория этот путь достижим только если
    что-то бросит НЕ `DioException` (например, сбой резолвинга зависимости
    через `getIt`), а не в результате обычного сетевого/серверного отказа
    сброса пароля — такие отказы всегда приходят как `DioException` и
    перехватываются (и гасятся) репозиторием раньше, чем дойдут до этого
    `catch`.
  - `'UC-41 (альт. поток, гипотетический): ResetPasswordError с другим
    errorType -> error state'` — мок бросает `ResetPasswordError('...',
    'some_other_error')` напрямую, проверяя `else`-ветку `on
    ResetPasswordError catch (e)` в кубите. В реальном коде репозитория
    `ResetPasswordError` конструируется **только** внутри `if
    (e.response?.data['error_type'] == "passwords.token")` — веток,
    создающих его с другим `errorType`, в коде нет вовсе. Поэтому этот
    `else` в кубите — мёртвый код при нынешней реализации репозитория; тест
    сам называет себя «гипотетическим» по этой причине.

  Оба теста корректно документируют, как повёл бы себя кубит, если бы он
  вообще получил такую ошибку — но по факту (см. «Основной поток», шаги 6–8)
  репозиторий не пропускает наверх ни одну из этих форм ошибки для сценария
  сброса пароля: реальный дефект — на уровень ниже этих двух кубит-веток,
  внутри самого `AuthRepository.resetPassword`.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — сценарий пытается обновить учётные данные
  пользователя (пароль привязан к `User.email` как логину, согласно [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)),
  но сам пароль не входит ни в одно документированное поле
  `User`/`UserHive`/`UserDTO` — это чисто серверный атрибут аутентификации,
  вне локальной модели `User`. Локально объект `User` в этом сценарии не
  читается и не пишется.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — на самом шаге сброса пароля сессия/токен не
  создаются и не читаются; однако из-за дефекта (см. «Основной поток», шаг 9)
  ложный `success` запускает автовход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)), который уже
  работает с [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — побочный эффект, не являющийся целью данного сценария.

### Бизнес-правила

- Единственный признанный репозиторием «настоящий» отказ сброса пароля —
  `DioException` с `response.data['error_type'] == "passwords.token"`; любой
  другой `error_type`, отсутствие `response` вовсе (нет сети/таймаут) или
  отсутствие самого поля обрабатываются одинаково — молча, без проброса
  исключения дальше.
- Ошибка при этом не теряется полностью: она логируется через `Talker.error`
  внутри `AuthRepository.resetPassword` до проверки `error_type` — то есть
  видна в логах, даже когда невидима для UI и состояния кубита.
- Как и все действия гостя в [MOD-1](../modules/MOD-1-AUTH.md), вызов online-only — локального
  черновика/повторной отправки при сбое нет; при этом дефекте гость не
  получает даже стандартного «попробуйте снова» — мастер просто завершается
  показом успеха.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий, включая сам дефект, полностью прослеживается в
существующем коде и покрыт тестами на уровне репозитория.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `EnterNewPasswordStep` | CURRENT | UI последнего шага: поля нового пароля/подтверждения + кнопка, вызывающая `resetPassword()` |
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `ForgotPasswordView.build` (`BlocConsumer` listener) | CURRENT | реагирует на `success`/`error`; на `success` показывает snackbar и отправляет `AuthEventAuthAfterRegistration` в `AuthBloc` |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.resetPassword` | CURRENT | оркестрирует шаг: loading → вызов репозитория → `on ResetPasswordError`/generic `catch`/безусловный `success` при отсутствии исключения |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.verifyCode` | CURRENT | предыдущий шаг мастера — не делает сетевой проверки кода |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState` | CURRENT | freezed sealed-состояние кубита (`success`/`error`/`enterCodeStep`/…) |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordData` | CURRENT | данные мастера: `newPassword`, `confirmNewPassword`, `errorMessage` и т.д. |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.resetPassword` | CURRENT (дефект) | `POST {authSerivceApi}/reset-password`; `on DioException` перебрасывает `ResetPasswordError` только при `error_type == "passwords.token"`, иначе гасит исключение без проброса |
| `lib/repositories/auth/auth_repository.dart` | `ResetPasswordError` | CURRENT | класс ошибки, конструируется репозиторием только для `error_type == "passwords.token"` |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый URL auth-сервиса, используемый в пути запроса |

## Критерии приёмки

- При `DioException` от `POST {authSerivceApi}/reset-password` с
  `error_type`, отличным от `"passwords.token"` (в т.ч. когда `response`
  отсутствует вовсе — таймаут/нет сети), `AuthRepository.resetPassword`
  завершается без исключения (`completes`, а не `throwsA(...)`).
- В этом случае `ForgotPasswordCubit.resetPassword()` не переходит ни в `on
  ResetPasswordError catch`, ни в общий `catch (e)` — эмитится
  `ForgotPasswordState.success(state.data)`, тот же результат, что и при
  настоящем успехе ([UC-10](UC-10-ACTOR-2-EVT-5-ENT-1-UPDATE_OK-IN-AUTH.md)-эквивалент).
- `ForgotPasswordView` реагирует на это состояние как на настоящий успех:
  показывает snackbar с `AppLocalizations.of(context)!.successful` и
  отправляет `AuthEventAuthAfterRegistration(email, newPassword)` в
  `AuthBloc`, хотя пароль на сервере не был изменён.
- Ошибка при этом логируется через `Talker.error` внутри `AuthRepository
  .resetPassword` — видна в логах приложения, но не отражается ни в
  `ForgotPasswordData.errorMessage`, ни в каком-либо состоянии UI.
- `ForgotPasswordData.errorMessage` после такого вызова остаётся таким, каким
  было до вызова (как правило `null`) — новое сообщение об ошибке не
  устанавливается.

## Связанные тесты

- `test/repositories/auth_repository_test.dart`, group `'UC-8/UC-9 (sendCodeToEmail) / UC-10/UC-11/UC-12 (resetPassword) / UC-19/UC-20 (deleteUser)'`,
  test `'UC-42 БАГ: resetPassword — ошибка сервера, отличная от
  passwords.token, молча проглатывается (метод завершается без исключения,
  пароль по факту не изменён)'` и test `'UC-42 БАГ: resetPassword — полное
  отсутствие сети (response: null) тоже молча проглатывается'` — прямое покрытие дефекта на
  уровне репозитория, оба варианта из «Основного потока» (другой
  `error_type` и полное отсутствие `response`).
- `test/pages/forgot_password_cubit_test.dart`, group `'UC-10/UC-11/UC-12 — ForgotPasswordCubit.resetPassword'`, test `'UC-42: generic исключение ->
  error с текстом исключения'` и test `'UC-41 (альт. поток, гипотетический):
  ResetPasswordError с другим errorType -> error state'` — покрывают ветки кубита, которые обработали бы такую
  ошибку, ЕСЛИ БЫ она дошла до кубита; на практике (см. «Альтернативные
  потоки») репозиторий гасит её раньше, чем эти ветки могли бы сработать для
  этого сценария — оба теста мокают `AuthRepository.resetPassword` напрямую,
  в обход его реальной (проглатывающей) реализации.

## Открытые вопросы и ограничения

- **Задокументированный дефект, не исправляемый в рамках этого прохода
  (TARGET == CURRENT).** `AuthRepository.resetPassword` не пробрасывает
  исключение ни для какой ошибки сервера/сети, кроме `error_type ==
  "passwords.token"` — любой другой отказ сервера воспринимается вызывающим
  кодом как успех.
- **Компаундный UX-риск ниже по потоку.** Ложный `success` запускает автовход
  ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)) с паролем, который не был реально сохранён на сервере —
  этот автовход, скорее всего, будет отклонён сервером как неверные учётные
  данные (аналог [UC-4](UC-4-ACTOR-2-EVT-2-ENT-2-CREATE_REJECTED-IN-AUTH.md), но для другого события/актора-триггера), и это
  отклонение никак не связано в UI с первоначальным сбоем сброса пароля:
  пользователь увидит «successful», затем — отдельную, необъяснённую ошибку
  входа.
- Какое поведение должно быть вместо текущего (пробрасывать исключение
  всегда, показывать конкретное сообщение сервера и т.д.) — вопрос будущего
  TARGET-прохода, не разрешается в рамках этой чисто документирующей задачи.
