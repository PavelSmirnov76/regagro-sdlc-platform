- **derived from**: [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)

# UC-2 — Ошибка саморегистрации гостя

## Назначение

Гость заполняет форму саморегистрации и подтверждает её, но попытка создать
учётную запись не завершается успехом — сервер либо сознательно отклонил
данные (например email уже занят), либо запрос технически не дошёл/не
получил ответа (нет сети, таймаут, ошибка сервера без тела). Код репозитория
не различает эти два случая — оба обрабатываются одной и той же веткой, без
отдельного бизнес-статуса REJECTED.

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — Гость.

## CURRENT

### Основной поток

1. Гость заполняет форму регистрации (страна, вид животных, email,
   пароль+подтверждение, имя — обязательные; юридическая форма и остальное —
   опционально) и нажимает подтвердить.
2. `RegistrationCubit.submit` эмитит `isSubmitting: true, isSuccess: false,
   errorMessage: null` и вызывает `AuthRepository.registerSelf` с
   `RegistrationRequest`, собранным из `state.data`.
3. `AuthRepository.registerSelf` не оборачивает вызов в try/catch — POST на
   `{authSerivceApi}/registration/self` уходит через `ApiClient`
   (`instanceName: 'farm_rpc'`); сервер отвечает не-успешным HTTP-кодом с
   телом вида `{"message": "Email занят"}`, и Dio выбрасывает `DioException`
   с непустым `response`.
4. Исключение пробрасывается из `registerSelf` наверх без изменений (нет
   try/catch в репозитории).
5. `RegistrationCubit.submit` ловит его веткой `on DioException catch (e)` и
   формирует `errorMessage` из `e.response?.data['message'].toString()`
   («Email занят»).
6. Эмитится `state.copyWith(isSubmitting: false, isSuccess: false,
   errorMessage: 'Email занят')`.
7. `RegistrationView`, слушая `BlocConsumer`, проверяет
   `state.errorMessage != null` (после `isSuccess` — не сработавшей) и
   показывает `SnackBar` с текстом
   `AppLocalizations.of(context)!.tr(state.errorMessage!.replaceFirst('Exception: ', ''))`.
   Форма остаётся на экране, гость может отредактировать данные и повторить
   попытку.

### Альтернативные потоки

- **Generic-исключение (не `DioException`).** Любая другая ошибка (например
  исключение, не связанное с HTTP-ответом) ловится веткой `catch (e)` без
  типа; `errorMessage = e.toString()`. Пользователь видит в `SnackBar` сырой
  текст исключения (после `replaceFirst('Exception: ', '')`) — сообщение не
  обязательно осмысленно для гостя.
- **`DioException` без `response`** (нет сети, таймаут на уровне Dio и т.п.).
  Исключение всё ещё попадает в ветку `on DioException catch (e)`
  (`response == null` не выводит его в другую ветку), но
  `e.response?.data['message'].toString()` короткозамыкается на `null` из-за
  `?.` в начале цепочки. Итог: `errorMessage` остаётся `null`,
  `isSubmitting`/`isSuccess` сбрасываются как обычно, но в `RegistrationView`
  условие `state.errorMessage != null` не выполняется — `SnackBar` не
  показывается вообще. Гость не получает никакой видимой обратной связи,
  кроме того что форма разблокировалась.
- **`DioException` с `response`, но `response.data` — `Map` без ключа
  `message`.** `errorMessage` становится буквальной строкой `'null'` (не
  настоящий `null`), и `SnackBar` показывает `AppLocalizations.tr('null')` —
  скорее всего нерелевантный/отсутствующий перевод, а не осмысленную ошибку.
- **`DioException` с `response`, но `response.data == null`.** `null['message']`
  бросает необработанное исключение внутри самого `catch`-блока — оно
  вылетает из `submit()` необработанным вместо того, чтобы превратиться в
  `errorMessage`. Это не CREATE_ERROR в задуманном смысле (аккуратный отказ с
  сообщением), а необработанный краш того же самого пути — см. «Открытые
  вопросы».

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — целевая сущность попытки создания: запись не появляется ни
  локально (регистрация ничего не пишет в БД/Hive до сетевого ответа), ни на
  сервере — попытка просто не удаётся.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session/TokenData) — явно **не** затрагивается: токен не
  создаётся, и `RegistrationView` вызывает
  `AuthEventAuthAfterRegistration` (автовход, [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)) только в ветке
  `state.isSuccess`, которая здесь не выполняется.

### Бизнес-правила

- Сознательный отказ сервера (REJECTED по смыслу — например email занят) и
  техническая недоступность (ERROR по смыслу — нет сети/сервер не ответил)
  обрабатываются в коде одной и той же веткой без разбора кода/типа ошибки
  ответа — на уровне репозитория и кубита это один и тот же случай. Именно
  поэтому у этого сценария нет отдельного `_REJECTED`-варианта: код не
  предоставляет для этого механизма.
- Данные формы при ошибке нигде не сохраняются вне state кубита — нет
  черновика/локальной записи; повторный submit отправляет по сути тот же
  payload заново.
- Пользователь не считается ни созданным, ни авторизованным — `isAuthorized()`
  (`AuthRepository`) остаётся `false`, т.к. никакой токен не был сохранён.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — все факты по этому сценарию проверены чтением
`lib/repositories/auth/auth_repository.dart` и
`lib/pages/registration/cubit/registration_cubit.dart`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.registerSelf` | CURRENT | сетевой POST-вызов саморегистрации без try/catch — любая ошибка пробрасывается как есть |
| `lib/repositories/auth/models/registration_request.dart` | `RegistrationRequest` | CURRENT | тело запроса, собираемое из `RegistrationData` перед отправкой |
| `lib/pages/registration/cubit/registration_cubit.dart` | `RegistrationCubit.submit` | CURRENT | вызывает `registerSelf`, ловит `DioException`/generic-исключение, формирует `errorMessage` |
| `lib/pages/registration/cubit/registration_state.dart` | `RegistrationState` | CURRENT | несёт `isSubmitting`/`isSuccess`/`errorMessage`, читаемые UI |
| `lib/pages/registration/presentation/widgets/registration_view.dart` | `RegistrationView` | CURRENT | показывает `SnackBar` с `errorMessage` гостю (при `errorMessage != null`); при `errorMessage == null` — молчит |

## Критерии приёмки

- При ошибке сервера с телом ответа, содержащим `message` (сознательный
  отказ, например email занят), гость видит текст этого сообщения в
  `SnackBar`.
- При технической ошибке без ответа сервера (`DioException` без `response`)
  форма разблокируется (`isSubmitting: false`), но `errorMessage` остаётся
  `null` и никакого `SnackBar` не показывается.
- При любом не-`DioException`-исключении гость видит текст исключения
  (`e.toString()`, без префикса `Exception: `) в `SnackBar`.
- Ни в одном из перечисленных случаев `User` не создаётся и авторизация не
  наступает.
- Сознательный отказ сервера и техническая недоступность неразличимы для
  кода — оба ведут к одной и той же форме состояния
  (`isSuccess: false`, разный или отсутствующий `errorMessage`).

## Связанные тесты

`test/pages/registration_cubit_test.dart`, group `'UC-1/UC-2 — RegistrationCubit.submit'`:

- test `'UC-30: DioException -> errorMessage из тела ответа'`
- test `'UC-31: generic исключение -> errorMessage с текстом исключения'`
- test `'UC-31: DioException без response -> errorMessage остаётся null'`
- test `'UC-30: DioException: response.data без ключа message -> errorMessage
  становится строкой "null" (сомнительно, но не падает)'` — тот же код,
  граничный случай тела ответа
- test `'UC-30 БАГ: DioException с response, но response.data == null ->
  необработанное исключение вместо errorMessage'` — тот же код, известный
  баг (см. «Открытые вопросы»)

## Открытые вопросы и ограничения

- **Известный баг** (зафиксирован также в `TESTING_CHECKLIST.md`):
  `e.response?.data['message'].toString()` в `RegistrationCubit.submit`
  падает необработанным исключением, если `response` не `null`, а
  `response.data` — `null` (сервер вернул ошибку с пустым телом). `?.`
  защищает только обращение к `e.response`, не к `.data`.
- Соседняя, более мелкая неточность того же метода: если `response.data` —
  `Map` без ключа `message`, `errorMessage` становится буквальной строкой
  `'null'`, а не настоящим `null` — далее уходит в `AppLocalizations.tr('null')`.
- Когда `DioException` приходит без `response` (типичный случай отсутствия
  сети), гость не получает вообще никакой видимой обратной связи —
  `SnackBar` не показывается, т.к. `errorMessage == null`. Это тихий отказ,
  неотличимый на экране от того, что ничего не произошло.
- Код не различает REJECTED (сервер сознательно отклонил данные по
  бизнес-причине) и ERROR (техническая недоступность) — оба ведут в одну и ту
  же ветку обработки. Это не баг конкретной строки, а отсутствие в
  `registerSelf`/`submit` разбора кода/типа ошибки ответа, которое сделало бы
  такое различие возможным.
