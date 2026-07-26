- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)

# UC-10 — Гость сбрасывает пароль по коду, сервер принимает новый пароль

## Назначение

Гость, прошедший шаги «email» ([EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md), [UC-8](UC-8-ACTOR-2-EVT-4-ENT-2-CREATE_OK-IN-AUTH.md)) и «код» мастера восстановления
пароля, вводит новый пароль и подтверждение; сервер принимает смену пароля без
ошибки. Учётная запись ([ENT-1](../entities/ENT-1-USER-IN-AUTH.md)) получает новый пароль на сервере, и это сразу
запускает автоматический вход тем же email и новым паролем ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)).

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — Гость. К этому шагу гость ещё не авторизован
(`AuthRepository.isAuthorized() == false`) и уже прошёл предыдущие шаги
мастера восстановления пароля в рамках того же `ForgotPasswordCubit`.

## CURRENT

### Основной поток

1. Гость подтверждает код на шаге `enterCodeStep`; переход на последний шаг
   выполняет `ForgotPasswordCubit.verifyCode()` — чисто локальный переход
   состояния (`ForgotPasswordState.enterNewPasswordStep`), без сетевого вызова
   и без проверки кода на этом шаге.
2. На последнем шаге гость вводит новый пароль и подтверждение —
   `ForgotPasswordCubit.setNewPassword`/`setConfirmNewPassword` сохраняют их в
   `ForgotPasswordData`.
3. Гость подтверждает шаг → `ForgotPasswordCubit.resetPassword()` эмитит
   `ForgotPasswordState.loading(state.data)`.
4. `resetPassword()` вызывает `AuthRepository.resetPassword(email: ..., code:
   ..., newPassword: ..., confirmNewPassword: ...)` — один запрос `POST
   {Constants.authSerivceApi}/reset-password` с телом `{email, token: code,
   password: newPassword, password_confirmation: confirmNewPassword}` через
   `ApiClient` (`farm_rpc`-инстанс). Тело ответа сервера не парсится и не
   используется — вызов просто дожидается завершения.
5. Вызов завершается без исключения → cubit эмитит
   `ForgotPasswordState.success(state.data)`. Поле `ForgotPasswordData.isSuccess`
   при этом НЕ выставляется в `true` этим методом — единственный признак
   успеха, на который реагирует подписчик экрана, это сам вариант состояния
   `success`, а не поле `isSuccess` (подтверждено тестом, см. «Связанные
   тесты»).
6. `ForgotPasswordView` (`BlocConsumer` listener) на `success` показывает
   `SnackBar` об успехе и сразу отправляет в `AuthBloc` событие
   `AuthEventAuthAfterRegistration(data.email, data.newPassword)` — без
   дополнительного действия гостя. Это запускает автовход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)),
   который и устанавливает авторизованную сессию ([ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)).

### Альтернативные потоки

- **Код неверен или истёк.** Сервер отвечает с `error_type ==
  "passwords.token"`; `AuthRepository.resetPassword` бросает
  `ResetPasswordError`, cubit ловит его (`on ResetPasswordError catch`) и
  возвращает гостя на шаг ввода кода (`ForgotPasswordState.enterCodeStep`) с
  сообщением об ошибке. Отдельный сценарий, `RESULT = UPDATE_REJECTED`, не
  описан этим файлом.
- **Известный дефект: любая другая ошибка сервера/сети внутри самого
  `AuthRepository.resetPassword` не отличима от успеха.** Метод ловит только
  `on DioException catch (e)`; если `error_type` в ответе — не
  `"passwords.token"` (иной код ошибки сервера, либо `e.response == null`, как
  при обрыве соединения), условие не совпадает, а `if`-ветка не содержит
  `else`/`rethrow` — исключение проглатывается, и метод завершается так, как
  будто пароль изменён. Cubit проходит тот же путь, что и в основном потоке
  (шаг 5): эмитит `success`, инициирует авто-вход с паролем, которого на
  сервере на самом деле нет. Это задокументированный дефект ложного
  `UPDATE_OK`, а не осознанная альтернативная бизнес-ветка — см. «Открытые
  вопросы и ограничения».
- **Иное исключение, долетевшее до cubit'а (не `ResetPasswordError`).** Общий
  `catch (e)` в `resetPassword()` эмитит `ForgotPasswordState.error` с текстом
  исключения. Отдельный сценарий, `RESULT = UPDATE_ERROR`, не описан этим
  файлом.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — сущность сегмента `ENT` в id: операция меняет пароль этой
  учётной записи на сервере. Локальная модель `User`/`UserDTO`
  (`packages/sheep_farm_database/lib/entities/user/user.dart`) не содержит
  поля пароля вовсе — пароль нигде не кэшируется на устройстве ни до, ни после
  вызова. Email из `ForgotPasswordData` — идентификатор учётной записи,
  соответствует `User.email` (по [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) документирован как «логин для входа/
  сброса пароля»).
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session/TokenData) — самим вызовом `resetPassword` не читается и не
  пишется: главный токен не выдаётся, новый пароль локально не сохраняется.
  Сессия появляется только на следующем шаге — автовходе ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)),
  использующем тот же email и новый пароль.

### Бизнес-правила

- Один прямой сетевой `POST`-вызов, без локального черновика или очереди — как
  и все действия [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) в [MOD-1](../modules/MOD-1-AUTH.md), сценарий ждёт прямого ответа сервера.
- Нет клиентской проверки совпадения `newPassword`/`confirmNewPassword` внутри
  `resetPassword()` — предполагается, что это уже сделала форма ввода нового
  пароля (её код вне периметра этого use-case).
- Успех на клиенте определяется исключительно отсутствием исключения,
  долетевшего до cubit'а — тело ответа сервера не проверяется ни на каком
  условии, аналогично `sendCodeToEmail` ([EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md)/[UC-8](UC-8-ACTOR-2-EVT-4-ENT-2-CREATE_OK-IN-AUTH.md)).
- Единственная ветка ошибки, которую `AuthRepository.resetPassword` явно
  различает, — неверный/истёкший код (`error_type == "passwords.token"`),
  оборачиваемый в `ResetPasswordError`; любая другая `DioException` внутри
  этого метода перехватывается и не пробрасывается дальше.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом на успешную ветку.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.resetPassword` | CURRENT | оркестрирует шаг: loading → вызов репозитория → `success` либо откат/ошибка |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.verifyCode` | CURRENT | локальный переход на последний шаг мастера перед вводом нового пароля |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState` | CURRENT | freezed sealed-состояние cubit'а, вариант `success` — единственный сигнал успеха для подписчика |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordData` | CURRENT | данные мастера (`email`, `code`, `newPassword`, `confirmNewPassword`); поле `isSuccess` этим методом не используется |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.resetPassword` | CURRENT | `POST {authSerivceApi}/reset-password`; пробрасывает `ResetPasswordError` только для `error_type == "passwords.token"`, любую другую `DioException` проглатывает |
| `lib/repositories/auth/auth_repository.dart` | `ResetPasswordError` | CURRENT | типизированная ошибка неверного/истёкшего кода |
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `ForgotPasswordView.build` (`BlocConsumer` listener) | CURRENT | на `success` показывает `SnackBar`, отправляет `AuthEventAuthAfterRegistration` в `AuthBloc` |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый URL auth-сервиса, используемый в пути `/reset-password` |

## Критерии приёмки

- Валидный код, новый пароль и совпадающее подтверждение при ответе сервера
  без ошибки → `POST {Constants.authSerivceApi}/reset-password` завершается
  без исключения, cubit эмитит `ForgotPasswordState.success(data)`.
- В состоянии `success` `ForgotPasswordData.isSuccess == false` — сигналом
  успеха для подписчика служит сам вариант состояния `success`, не это поле.
- Успех без дополнительного действия гостя немедленно отправляет
  `AuthEventAuthAfterRegistration(email, newPassword)` в `AuthBloc`, запуская
  автовход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md), [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)) тем же email и новым паролем.
- Тело ответа сервера на `resetPassword` не парсится и не используется —
  успех определяется исключительно отсутствием исключения, долетевшего до
  cubit'а.

## Связанные тесты

`test/pages/forgot_password_cubit_test.dart`, group `'UC-10/UC-11/UC-12 — ForgotPasswordCubit.resetPassword'`, test `'UC-40: успех -> success'`.

## Открытые вопросы и ограничения

- Известный дефект (не открытый вопрос): `AuthRepository.resetPassword`
  перехватывает только `DioException` и пробрасывает `ResetPasswordError`
  лишь для `error_type == "passwords.token"` — любая другая серверная/сетевая
  ошибка (включая обрыв соединения, когда `e.response == null`) молча
  проглатывается, и cubit получает такой же `success`, как при реальной смене
  пароля (см. «Альтернативные потоки»). Последующий авто-вход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md),
  [UC-6](UC-6-ACTOR-2-EVT-3-ENT-2-CREATE_OK-IN-AUTH.md)) в этом случае неизбежно падает на неверном пароле, а его обработчик
  не оборачивает вызов в try/catch — экран зависает в состоянии загрузки, не
  сообщая гостю, что пароль на самом деле не изменён.
- Нет клиентской проверки совпадения `newPassword`/`confirmNewPassword`
  внутри `resetPassword()` — ожидается, что это делает форма ввода нового
  пароля, чей код не входит в проверенный периметр этого сценария.
- Тест на успешную ветку (`'UC-40: успех -> success'`, имя теста в коде пока не переименовано) не проверяет содержимое отправленного тела
  запроса — все четыре именованных параметра замаскированы
  `any(named: ...)`-матчерами; соответствие полей запроса телу `POST`
  (`email`/`token`/`password`/`password_confirmation`) подтверждено чтением
  кода `AuthRepository.resetPassword`, а не тестом.
