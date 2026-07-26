# UC-9 — Гость запрашивает код восстановления пароля (ошибка)

## Назначение

Гость, забывший пароль, вводит email на первом шаге мастера восстановления
пароля, но попытка запроса кода не завершается успехом — сервер отвечает
ошибкой (например «Email не найден») либо запрос технически не доходит.
Мастер не продвигается: гость остаётся на шаге ввода email с сообщением об
ошибке и может повторить попытку.

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
   `{'email': email}` через RPC-клиент (`ApiClient`, instance name `farm_rpc`,
   реализация `CustomDioClient`).
5. Вызов завершается ошибкой: `CustomDioClient.call` логирует исключение через
   `Talker` и пробрасывает его дальше (`rethrow`) без изменений — сервер
   ответил не-2xx статусом с телом вида `{'message': 'Email не найден'}` (или
   иной технической ошибкой на уровне Dio), и `dio.request` бросает
   `DioException`. `AuthRepository.sendCodeToEmail` не оборачивает вызов в
   try/catch — исключение доходит до cubit'а без изменений.
6. `ForgotPasswordCubit.sendCode()` ловит его веткой `on DioException catch
   (e)` и эмитит `ForgotPasswordState.enterEmailStep` с тем же `email` и
   `errorMessage: e.response?.data['message']` — `currentStep` остаётся
   `ForgotPasswordStep.enterEmail`, мастер не продвигается.
7. `ForgotPasswordView` перерисовывает `EnterEmailStep`; `hasErrorMessage`
   становится `true`, и текст ошибки показывается как обычный красный текст
   под полем email — **сырой текст из тела ответа сервера, без прогона через
   `AppLocalizations.tr()`**. Это отличается от обработки терминального
   состояния `ForgotPasswordState.error` в том же виджете (`BlocConsumer`
   `listener`), которое, наоборот, прогоняется через `.tr()`.
8. Гость может отредактировать email (`setEmail`) и повторно нажать
   «Отправить код» — `errorMessage` явно не сбрасывается в `setEmail`,
   поэтому старый текст ошибки остаётся видимым до следующего ответа
   `sendCode()` (успешного или нет).

### Альтернативные потоки

- **Успешный повтор после ошибки не сбрасывает старое сообщение.** Если
  повторный `sendCode()` завершается успехом, cubit эмитит
  `ForgotPasswordState.enterCodeStep(state.data.copyWith(currentStep:
  ForgotPasswordStep.enterCode))` — `copyWith` меняет только `currentStep`,
  `errorMessage` из предыдущей неудачной попытки остаётся в
  `ForgotPasswordData` без изменений. `EnterCodeStep` тоже безусловно рендерит
  `errorMessage` (`if (errorMessage != null) ...`), поэтому устаревшее
  сообщение об ошибке продолжает отображаться уже на шаге ввода кода.
- **Чистая сетевая ошибка без ответа сервера** (`e.response == null`, обрыв
  соединения/таймаут на уровне Dio). `e.response?.data['message']` в этом
  случае короткозамыкается целиком (не только на `.data`) — `errorMessage`
  становится `null`; `hasErrorMessage` не показывает ничего, гость просто
  видит, что вернулся на тот же шаг без всякого сообщения об ошибке.
- **Не-`DioException` исключение внутри `sendCode()`.** Метод содержит
  единственную ветку `on DioException catch` — любое другое исключение
  всплывает необработанным из метода cubit'а, минуя оба состояния
  (`enterEmailStep` с ошибкой и терминальное `error`).
- **Тело ответа не `Map`** (например HTML-страница шлюза/прокси при 502/503).
  `e.response?.data['message']` в этом случае бросил бы исключение
  индексирования уже внутри самого `catch`-блока — не покрыто тестом,
  поведение не проверено рантаймом.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность события [EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md) по определению; фактически
  в этой ветке (как и в успешной) ни один Hive-бокс не читается и не
  пишется — ошибка не затрагивает главный токен/`lastLogin`, гость остаётся
  гостем.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — введённый email соответствует полю `User.email` по
  смыслу, но локальный/серверный объект `User` здесь не читается и не
  создаётся — email передаётся серверу голой строкой, вне контекста
  конкретной локально известной учётной записи.

### Бизнес-правила

- Код от техники ошибки не различает: любая ошибка HTTP-вызова (осмысленный
  отказ сервера вроде «Email не найден», таймаут, ошибка сервера без
  осмысленного тела) обрабатывается одной и той же веткой `on DioException
  catch` — отдельного `_REJECTED`-статуса для случая «email не найден» в этой
  ветке восстановления пароля нет (в отличие, например, от сброса пароля по
  коду, [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), где отдельно разбирается `ResetPasswordError.errorType ==
  "passwords.token"`).
- `errorMessage` — сырой текст из тела ответа сервера
  (`e.response?.data['message']`), не ключ локализации; UI показывает его как
  есть, без `AppLocalizations.tr()`.
- Мастер не продвигается дальше `enterEmail` при ошибке — гость может
  исправить email и повторить попытку без ограничения количества попыток на
  клиенте (то же свойство, что и на успешном пути того же события).
- Ошибка не создаёт и не изменяет ни один персистентный объект — целиком
  живёт в state cubit'а (`ForgotPasswordData.errorMessage`), не пишется в
  Hive/БД.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом. Обнаруженные по ходу
нюансы (тихий отказ без сети, потенциальное необработанное исключение на
теле ответа не-`Map`, устаревающий `errorMessage`, переживающий успешную
попытку) зафиксированы в «Открытые вопросы и ограничения» — они не блокируют
документирование CURRENT, только описывают его точнее.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `EnterEmailStep` | CURRENT | UI шага: поле email, кнопка отправки, рендер `errorMessage` сырым (не локализованным) текстом |
| `lib/pages/forgot_password/presentation/widgets/forgot_password_view.dart` | `EnterCodeStep` | CURRENT | безусловно рендерит `errorMessage`, если он не `null` — не различает «новую» ошибку и устаревшую от предыдущей попытки |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.sendCode` | CURRENT | ловит `DioException`, откатывает состояние на `enterEmailStep` с `errorMessage` |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit.setEmail` | CURRENT | обновляет `email`, не трогая и не сбрасывая `errorMessage` |
| `lib/pages/forgot_password/cubit/forgot_password_state.dart` | `ForgotPasswordState.enterEmailStep` | CURRENT | вариант состояния, на который откатывается cubit при ошибке |
| `lib/pages/forgot_password/data/forgot_password_data.dart` | `ForgotPasswordData.errorMessage` | CURRENT | поле, несущее сырой текст ошибки между шагами; не сбрасывается автоматически при движении вперёд по мастеру |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.sendCodeToEmail` | CURRENT | `POST {Constants.authSerivceApi}/forgot-password`, без try/catch — пробрасывает исключение как есть |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | логирует через `Talker` и `rethrow`-ит исключение из `dio.request` без изменений |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | Dio-клиент (`DioForNative`), выбрасывающий `DioException` на не-2xx ответ |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый путь auth-сервиса, используемый в запросе |

## Критерии приёмки

- При падении `AuthRepository.sendCodeToEmail` с `DioException`, у которой
  `response.data` — `Map` с ключом `message`, состояние cubit'а
  остаётся/возвращается в `ForgotPasswordState.enterEmailStep` с
  `currentStep == ForgotPasswordStep.enterEmail`.
- `state.data.errorMessage` равен строке `response.data['message']`.
- `state.data.email` не теряется — остаётся тем, что гость ввёл до попытки.
- UI (`EnterEmailStep`) показывает `errorMessage` как есть, без прогона через
  `AppLocalizations.tr()`.
- Мастер не переходит на `enterCode` — гость может повторить попытку с того
  же экрана.

## Связанные тесты

`test/pages/forgot_password_cubit_test.dart`, group `'UC-8/UC-9 — ForgotPasswordCubit.sendCode'`, test `'UC-38: DioException -> errorMessage из
тела ответа, остаётся на enterEmail'`.

## Открытые вопросы и ограничения

- Код не различает REJECTED (сервер осмысленно отклонил запрос, например
  email не найден) и ERROR (сеть/таймаут/ошибка сервера без осмысленного
  тела) — оба ловятся одной веткой `on DioException catch`, поэтому для этой
  ветки восстановления пароля нет отдельного `_REJECTED`-варианта use-case
  (аналогичный вывод — в [UC-2](UC-2-ACTOR-2-EVT-1-ENT-1-CREATE_ERROR-IN-AUTH.md) для саморегистрации).
- **Тихий отказ.** Если `DioException` пришла без `response` (обрыв
  сети/таймаут на уровне Dio), `e.response?.data['message']` короткозамыкается
  на `null` целиком (`?.` защищает всю цепочку после `e.response`, не только
  `.data`) — гость не видит вообще никакого сообщения об ошибке, экран
  выглядит так, будто просто ничего не произошло.
- **Потенциальное необработанное исключение.** Если сервер вернёт ошибку с
  телом, не являющимся `Map` (например HTML-страница прокси/шлюза), `e.response
  ?.data['message']` бросит исключение индексирования уже внутри самого
  `catch`-блока — не покрыто тестом, поведение не проверено.
- **Устаревшее сообщение об ошибке переживает успешную попытку.**
  `errorMessage`, установленный при неудаче, не сбрасывается ни `setEmail`,
  ни успешным `sendCode()` (`copyWith(currentStep: ...)` не трогает
  `errorMessage`) — оно продолжает отображаться на следующем шаге
  (`EnterCodeStep`, который рендерит `errorMessage` безусловно) вплоть до
  явного `prevStep()`. Обнаружено чтением кода, тестом не покрыто.
- Единственное место, где `errorMessage` гарантированно сбрасывается —
  `prevStep()` при возврате с `enterCode` на `enterEmail`; при движении вперёд
  по мастеру сброса нигде нет.
