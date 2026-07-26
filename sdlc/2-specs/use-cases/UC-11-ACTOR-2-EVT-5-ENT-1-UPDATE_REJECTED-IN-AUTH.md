- **derived from**: [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)

# UC-11 — Гость сбрасывает пароль по коду: сервер отклоняет неверный/истёкший код (REJECTED)

## Назначение

Гость, уже получивший код восстановления ([EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md)) и введший его вместе с
новым паролем и подтверждением, завершает сброс пароля; запрос доходит до
сервера, но тот отвечает, что код неверен или истёк. Пароль не меняется,
гость возвращается на шаг ввода кода с сообщением об ошибке.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — гость.

## CURRENT

### Основной поток

1. Гость на шаге `enterNewPassword` вводит новый пароль и подтверждение
   (email и код уже сохранены в `ForgotPasswordData` с более ранних шагов) и
   подтверждает сброс — вызывается `ForgotPasswordCubit.resetPassword()`.
2. `resetPassword()` эмитит `ForgotPasswordState.loading(state.data)`, затем
   вызывает `AuthRepository.resetPassword(email:, code:, newPassword:,
   confirmNewPassword:)` — единственный POST-запрос с этими четырьмя полями.
3. Сервер отвечает ошибкой: `DioException`, у которой
   `e.response?.data['error_type'] == "passwords.token"` — код неверен или
   истёк. Это единственный `error_type`, который `AuthRepository.resetPassword`
   явно распознаёт и превращает в типизированную ошибку.
4. `AuthRepository.resetPassword` логирует ошибку через `Talker.error` и
   бросает `ResetPasswordError(message, errorType)` — собственный класс
   `extends Error`, а не обычное исключение — с сырыми `message`/`error_type`
   из тела ответа сервера.
5. `ResetPasswordError` всплывает в `ForgotPasswordCubit.resetPassword()` и
   попадает в блок `on ResetPasswordError catch (e)`. Проверка
   `e.errorType == "passwords.token"` — истина, поэтому кубит эмитит
   `ForgotPasswordState.enterCodeStep(...)` с `data.copyWith(currentStep:
   ForgotPasswordStep.enterCode, errorMessage: e.message, isLoading: false,
   code: state.data.code, email: state.data.email)`.
6. Гость видит экран ввода кода с сохранёнными email/кодом и сообщением об
   ошибке (например «Код истёк» — конкретный текст приходит от сервера как
   есть); поля `newPassword`/`confirmNewPassword` в `ForgotPasswordData` не
   очищаются этим `copyWith` явно и сохраняют последнее введённое значение,
   но экран ввода кода их не показывает.

### Альтернативные потоки

- **`ResetPasswordError` с другим `errorType`.** Тот же `catch (e)` в кубите,
  но ветка `else`: эмитится `ForgotPasswordState.error(...)` с тем же
  `e.message` — гость не возвращается на шаг кода, а попадает на отдельный
  экран ошибки. Это гипотетическая ветка (сервер сегодня не отдаёт других
  `error_type` для этого эндпоинта, кроме `passwords.token`), не покрывается
  этим use-case.
- **Не-`DioException`/техническая ошибка вызова.** Внешний `catch (e)` в
  `resetPassword()` кубита ловит любое исключение, не являющееся
  `ResetPasswordError`, и эмитит `ForgotPasswordState.error(errorMessage:
  e.toString())` — это `ERROR` (запрос не дошёл до сервера / технический
  сбой), а не `REJECTED`, отдельный use-case.
- **Известный риск, смежный с этой же веткой кода (не альтернативный успешный
  путь, а дефект).** В `AuthRepository.resetPassword` блок `on DioException
  catch (e)` бросает `ResetPasswordError` только когда `error_type ==
  "passwords.token"`; при любом другом `error_type` (или его отсутствии)
  блок ничего не бросает — метод, объявленный как `Future<void>`, просто
  завершается штатно. Для вызывающего `ForgotPasswordCubit.resetPassword()`
  это неотличимо от настоящего успеха: эмитится `ForgotPasswordState.success`,
  хотя пароль на сервере фактически не был изменён. Этот риск уже
  задокументирован в [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md) и не специфичен для `passwords.token`-ветки,
  описываемой этим use-case, но использует тот же метод и тот же
  `try/catch`.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — попытка обновления учётных данных (пароля) отклонена
  сервером; пользователь на сервере не меняется, локально `User` в этом
  сценарии не читается и не пишется.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session) — не устанавливается: до успешного сброса пароля не
  доходит, поэтому автоматический вход ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)), который в happy-path
  следует за успешным [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), здесь не запускается; главный токен в
  `AUTH_BOX` не записывается.

### Бизнес-правила

- `error_type == "passwords.token"` — единственное условие, по которому
  `AuthRepository.resetPassword` различает «код неверен/истёк» среди прочих
  возможных ошибок сервера и превращает его в типизированный
  `ResetPasswordError`.
- Дошедший до сервера и осознанно отклонённый им запрос сброса пароля —
  `REJECTED`, а не `ERROR`: сервер ответил по существу, просто не принял код.
  `ForgotPasswordCubit` использует это же условие (`e.errorType ==
  "passwords.token"`), чтобы решить, возвращать ли гостя именно на шаг ввода
  кода, а не на общий экран ошибки.
- Сообщение об ошибке — сырой текст `message` из тела ответа сервера,
  передаваемый в `errorMessage` без изменений; локализация/пользовательское
  оформление — вне рамок этого use-case.
- Возврат на шаг `enterCode` сохраняет ранее введённые `email` и `code` в
  `ForgotPasswordData` — гостю не нужно вводить их заново, только новый код.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью прослеживается в существующем коде.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.resetPassword` | CURRENT | эмитит `loading`, вызывает `AuthRepository.resetPassword`, ловит `ResetPasswordError` и по `errorType` решает между возвратом на `enterCodeStep` и `error` |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState.enterCodeStep` | CURRENT | состояние возврата на шаг ввода кода с сообщением об ошибке |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState.error` | CURRENT | состояние общей ошибки (альтернативная ветка, не этот use-case) |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordData` | CURRENT | хранит `email`/`code`/`newPassword`/`confirmNewPassword`/`currentStep`/`errorMessage` между шагами визарда |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.resetPassword` | CURRENT | выполняет запрос сброса пароля; при `error_type == "passwords.token"` бросает `ResetPasswordError`, иначе завершается без исключения (см. «известный риск») |
| `lib/repositories/auth/auth_repository.dart` | `ResetPasswordError` | CURRENT | типизированная ошибка (`extends Error`) с полями `message`/`errorType`, различающая эту REJECTED-ветку |

## Критерии приёмки

- При `error_type == "passwords.token"` в ответе сервера
  `AuthRepository.resetPassword` бросает `ResetPasswordError(message,
  "passwords.token")`.
- `ForgotPasswordCubit.resetPassword()` эмитит последовательность
  `ForgotPasswordState.loading` → `ForgotPasswordState.enterCodeStep` с
  `errorMessage`, равным `e.message`, и `currentStep ==
  ForgotPasswordStep.enterCode`.
- `email` и `code` в `ForgotPasswordData` после возврата на шаг кода равны
  значениям, которые уже были в состоянии до вызова `resetPassword()`.
- Главный токен и пользователь не записываются в `AUTH_BOX`; [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)
  (автоматический вход) не запускается.

## Связанные тесты

- `test/pages/forgot_password_cubit_test.dart`, group `'UC-10/UC-11/UC-12 — ForgotPasswordCubit.resetPassword'`, test `'UC-41: ResetPasswordError с
  errorType passwords.token -> возврат на enterCode с сообщением'`.

## Открытые вопросы и ограничения

- Известный риск (не открытый вопрос, а задокументированный дефект, уже
  описанный в [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)): в `AuthRepository.resetPassword` любой `DioException`
  с `error_type`, отличным от `"passwords.token"` (включая его отсутствие),
  проглатывается без повторного throw — метод возвращается штатно, и
  `ForgotPasswordCubit` считает сброс пароля успешным, хотя пароль на
  сервере не изменился. Использует тот же метод и тот же `try/catch`, что и
  сценарий этого use-case, но относится к другой, не покрытой веткой
  `error_type`.
- Ветка «`ResetPasswordError` с другим `errorType`» в коде присутствует
  (эмитит `ForgotPasswordState.error`), но по имеющимся данным сервер сегодня
  не возвращает для этого эндпоинта ничего, кроме `passwords.token` — тест на
  эту ветку помечен в коде как гипотетический.
