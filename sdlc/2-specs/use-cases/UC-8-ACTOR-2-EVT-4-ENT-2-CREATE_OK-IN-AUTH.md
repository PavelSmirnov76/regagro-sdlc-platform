# UC-8 — Гость запрашивает код восстановления пароля (успех)

## Назначение

Гость, забывший пароль, вводит email на первом шаге мастера восстановления
пароля и получает от сервера подтверждение запроса кода без ошибки — мастер
переходит к шагу ввода кода.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — действие доступно только до входа в систему, не
требует главного токена.

## CURRENT

### Основной поток

1. Гость на экране мастера восстановления пароля (`EnterEmailStep` в
   `forgot_password_view.dart`) вводит email; каждое изменение поля вызывает
   `ForgotPasswordCubit.setEmail`, обновляя `email` в `ForgotPasswordData`
   внутри состояния `ForgotPasswordState.enterEmailStep`.
2. Гость нажимает кнопку отправки кода (`onSendCode`) → вызывается
   `ForgotPasswordCubit.sendCode()`.
3. `sendCode` эмитит `ForgotPasswordState.loading(state.data)`.
4. `sendCode` вызывает `AuthRepository.sendCodeToEmail(email: state.data.email)`,
   который отправляет `POST {Constants.authSerivceApi}/forgot-password` с телом
   `{'email': email}` через RPC-клиент (`ApiClient`, instance name
   `farm_rpc`).
5. Вызов завершается без исключения — `sendCodeToEmail` не читает и не
   разбирает тело ответа сервера, просто дожидается вызова
   (`await rpcClientSHTP.call(message)`); успех на клиенте означает
   исключительно «HTTP-вызов не выбросил исключение», а не «сервер
   подтвердил существование email или реальную отправку кода».
6. Cubit эмитит `ForgotPasswordState.enterCodeStep`, где
   `ForgotPasswordData.currentStep` становится `ForgotPasswordStep.enterCode`
   — мастер переходит на следующий шаг (ввод кода).
7. Сам код, отправленный на email, на этом шаге клиентом никак не
   валидируется — переход на следующий шаг ничего не проверяет онлайн;
   реальная проверка кода происходит только при попытке сброса пароля.

### Альтернативные потоки

- **Сетевая/серверная ошибка при отправке.** Если `sendCodeToEmail` бросает
  `DioException`, cubit ловит её (`on DioException catch (e)`), эмитит
  `ForgotPasswordState.enterEmailStep` с `errorMessage` из
  `e.response?.data['message']`, и `currentStep` остаётся `enterEmail` —
  мастер не продвигается. Это иной результат того же события (сетевая
  ошибка недостижения получателя, а не сознательный отказ) — отдельный
  сценарий, не описываемый этим файлом.
- **Гость возвращается на первый шаг и повторяет запрос.**
  `ForgotPasswordCubit.prevStep()` с шага `enterCode` очищает `code` и
  `errorMessage` и возвращает на `enterEmail`; повторный вызов `sendCode()`
  проходит тот же основной поток заново, без ограничения по количеству
  попыток на клиенте.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность события [EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md) по определению; на деле
  этот шаг не читает и не пишет ни одного поля сессии в `AUTH_BOX`/`LOGIN_BOX`
  — это чистый сетевой побочный эффект без локальной мутации, начало более
  широкого процесса восстановления доступа к сессии, не запись в Hive.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — введённый email соответствует полю `User.email`
  (согласно [ENT-1](../entities/ENT-1-USER-IN-AUTH.md), это поле явно документировано как «логин для входа/сброса
  пароля»), однако в этом шаге клиент не загружает и не создаёт объект `User`
  — email передаётся серверу голой строкой, вне контекста конкретной локально
  известной учётной записи.

### Бизнес-правила

- Единственный критерий успеха на клиенте — отсутствие исключения при
  HTTP-вызове; тело ответа сервера не парсится и не проверяется ни на каком
  условии.
- Переход на шаг ввода кода происходит безусловно при отсутствии сетевой
  ошибки — клиент не может отличить «код реально отправлен на существующий
  email» от «сервер просто ответил 200».
- Действие требует сети — как и все действия гостя в [MOD-1](../modules/MOD-1-AUTH.md), у
  `sendCodeToEmail` нет локального черновика/очереди на случай отсутствия
  соединения.
- Проверка правильности самого кода восстановления отложена на следующий шаг
  мастера ([EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)) и в этом сценарии не происходит.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `EnterEmailStep` | CURRENT | UI первого шага: поле email + кнопка, вызывающая `sendCode()` |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.setEmail` | CURRENT | сохраняет введённый email в `ForgotPasswordData` до отправки |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.sendCode` | CURRENT | оркестрирует шаг: loading → вызов репозитория → переход на `enterCode` или откат на `enterEmail` с ошибкой |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState` | CURRENT | freezed sealed-состояние cubit'а (`enterEmailStep`/`enterCodeStep`/`loading`/…) |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordData` | CURRENT | данные мастера: `email`, `code`, `currentStep` и т.д. |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordStep` | CURRENT | enum шагов мастера (`enterEmail`/`enterCode`/`enterNewPassword`) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.sendCodeToEmail` | CURRENT | `POST {Constants.authSerivceApi}/forgot-password` без разбора тела ответа |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый URL auth-сервиса, используемый в пути запроса |

## Критерии приёмки

- Ввод email на шаге `enterEmail` и вызов `sendCode()` при успешном
  (не бросающем исключение) `AuthRepository.sendCodeToEmail` переводит
  состояние cubit'а в `ForgotPasswordState.enterCodeStep` с
  `currentStep == ForgotPasswordStep.enterCode`.
- Перед сетевым вызовом cubit кратковременно эмитит
  `ForgotPasswordState.loading`.
- `email`, введённый на первом шаге, сохраняется в `ForgotPasswordData` и
  передаётся в `sendCodeToEmail` без изменений.
- Тело ответа сервера не влияет на переход — успех определяется исключительно
  отсутствием исключения.

## Связанные тесты

`test/pages/forgot_password_cubit_test.dart`, group `'UC-8/UC-9 — ForgotPasswordCubit.sendCode'`, test `'UC-37: успех -> currentStep:enterCode'`.

## Открытые вопросы и ограничения

- Клиент не может отличить «сервер реально отправил код на существующий email»
  от «сервер ответил 200 без реальной отправки» — тело ответа не проверяется
  нигде в `sendCodeToEmail`. Поведение сервера в этом случае — вне границ
  клиентского кода и этого сценария.
- Нет ограничения по числу повторных запросов кода с клиента — гость может
  вызывать `sendCode()` сколько угодно раз подряд, возвращаясь на первый шаг
  через `prevStep()`.
