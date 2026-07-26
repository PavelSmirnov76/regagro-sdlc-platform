# UC-20 — Авторизованный пользователь удаляет аккаунт, сервер отклоняет запрос (ошибка проглатывается)

## Назначение

Авторизованный пользователь подтверждает удаление своего аккаунта в
модальном диалоге. Сервер отвечает ошибкой (любой, кроме одного конкретного
типа `error_type == "passwords.token"`), но `AuthRepository.deleteUser`
перехватывает эту ошибку и не пробрасывает её дальше — метод завершается как
обычный успех. `AuthBloc` не может отличить этот случай от настоящего
успешного удаления и всё равно выполняет локальный выход из аккаунта.
Пользователь видит переход на экран входа и воспринимает это как
подтверждение того, что аккаунт удалён, хотя на сервере он остался
нетронутым.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — действие доступно только авторизованному
пользователю (кнопка удаления аккаунта рендерится условно по
`AppCacheService.isAuthorized()`).

## CURRENT

### Основной поток

1. Авторизованный пользователь на экране настроек профиля видит кнопку
   удаления аккаунта (`_DeleteAccountButton`,
   `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`),
   видимую только когда `AppCacheService.isAuthorized()` истинно.
2. Нажатие открывает модальный диалог подтверждения
   (`_showDeleteAccountDialog`) с заголовком `l10n.delete_account_title` и
   текстом `l10n.delete_account_message`, кнопками «Удалить»/«Отмена».
3. Пользователь нажимает «Удалить» (`BlackCircleButton.secondary`,
   `onTap`): диалог закрывается (`Navigator.of(dialogContext).pop(false)`),
   выполняется переход на `Routes.profile`, **синхронно** вызывается
   `AppCacheService.clearAllCache()` — весь локальный Hive-кеш стирается
   немедленно, до какого-либо обращения к серверу и до знания результата
   запроса, — и диспатчится `authBloc.add(AuthEventDeleteAccount())`.
4. `AuthBloc.on<AuthEventDeleteAccount>` эмитит `AuthSplashScreen`, затем
   вызывает `await _authRepository.deleteUser()` без обёртки в try/catch.
5. `AuthRepository.deleteUser` отправляет `DELETE
   {Constants.authSerivceApi}/user` через RPC-клиент (`ApiClient`, instance
   name `farm_rpc`).
6. Сервер отвечает ошибкой: `rpcClientSHTP.call` бросает `DioException` с
   `response.data['error_type']`, равным любому значению, **отличному** от
   `"passwords.token"` (например `"some_other_error"`, или запрос вообще без
   `error_type`/без `response`).
7. `deleteUser` ловит исключение веткой `on DioException catch (e)`,
   логирует его через `Talker` (`getIt<Talker>().error(...)`), проверяет
   `e.response?.data['error_type'] == "passwords.token"` — условие ложно —
   и **не перевыбрасывает исключение**: `catch`-блок завершается без
   `throw`/`rethrow`, метод `deleteUser()` возвращает нормально
   завершившийся `Future<void>`.
8. `AuthBloc` продолжает выполнение как при успехе: вызывает `await
   _authRepository.logout()` — стирается весь `AUTH_BOX` (главный токен,
   `User`, серверные интеграции), `AppCacheService.setAuthorizedFlag(false)`,
   в auth-стрим публикуется `false`.
9. `AuthBloc` эмитит `AuthLogout`, затем `AuthInitial` (через
   `_emitInitial`) — пользователь видит экран входа.
10. Итог: пользователь наблюдает тот же UI-результат, что и при успешном
    удалении аккаунта (переход на экран логина, локальные данные стёрты),
    но аккаунт на сервере не удалён — сервер вернул ошибку, которая нигде
    не была показана пользователю и не остановила локальный логаут.

### Альтернативные потоки

- **Полное отсутствие ответа сервера** (`e.response == null` — обрыв
  сети/таймаут на уровне Dio). `e.response?.data['error_type']`
  короткозамыкается на `null`, что тоже не равно `"passwords.token"` — тот
  же код проглатывает исключение тем же образом. Для `deleteUser` отдельного
  теста на этот под-случай нет (есть только для `resetPassword`, тот же
  паттерн кода), но ветка идентична по чтению кода.
- **`error_type == "passwords.token"`.** Формально тот же метод содержит
  ветку, которая в этом случае **бросает** `ResetPasswordError`. Поскольку
  `AuthBloc.on<AuthEventDeleteAccount>` не оборачивает вызов `deleteUser()` в
  try/catch, это исключение не перехватывается обработчиком события — оно
  всплывает необработанным из тела `on<AuthEventDeleteAccount>`, ни `AuthLogout`,
  ни `AuthInitial` не эмитятся, пользователь остаётся видеть последний
  эмитированный `AuthSplashScreen`. Это другое поведение (видимый сбой
  вместо тихого «успеха»), отдельный код-путь того же [EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md), вне рамок
  этого конкретного сценария (который специфицирует именно случай тихого
  проглатывания).
- **`AppCacheService.clearAllCache()` не откатывается.** Поскольку кеш
  стирается синхронно в UI-обработчике кнопки ещё до диспатча события и до
  любого сетевого ответа, эта операция необратима независимо от исхода
  `deleteUser()` — даже в этой ошибочной ветке локальный кеш уже потерян к
  моменту, когда становится известно, что сервер отклонил удаление.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — целевая сущность операции (аккаунт, который
  пытаются удалить); в этой ветке сервер отклоняет удаление, но локальный
  объект `User` всё равно исчезает вместе со всем `AUTH_BOX` на шаге
  `logout()`.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — главный токен и связанные Hive-ключи стираются
  локальным `logout()`, несмотря на то что серверная сессия/аккаунт могли
  остаться действительными (сервер не подтвердил удаление).

### Бизнес-правила

- `deleteUser()` копирует проверку `errorType` из `resetPassword()` (`==
  "passwords.token"`) — тип ошибки, семантически относящийся к сбросу пароля
  по токену, не к удалению аккаунта; для сценария удаления это условие не
  имеет продуктового смысла и на практике действует как «пропустить любую
  реальную ошибку сервера».
- Единственный код сервера, который вообще что-то бросает из `deleteUser` —
  `"passwords.token"`; любой другой код (или его полное отсутствие)
  обрабатывается тем же путём, что и полный успех.
- Локальный логаут в `AuthBloc.on<AuthEventDeleteAccount>` не обусловлен
  подтверждённым результатом серверного удаления — он выполняется
  безусловно после того, как `deleteUser()` не бросил исключение, независимо
  от того, было ли оно фактически успешным на сервере.
- Стирание локального кеша (`AppCacheService.clearAllCache()`) происходит
  до сетевого вызова, а не после подтверждения успеха — порядок операций
  делает результат необратимым для клиента заранее.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не существует отдельного блокирующего пункта для документирования — сценарий
полностью реализован (пусть и дефектно) и частично покрыт тестом на уровне
репозитория. Незакрытый разрыв — отсутствие теста на уровне `AuthBloc` для
этой конкретной ветки — зафиксирован в «Открытые вопросы и ограничения» и в
«Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_DeleteAccountButton` | CURRENT | кнопка удаления аккаунта, видна только авторизованному |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_showDeleteAccountDialog` | CURRENT | диалог подтверждения; при подтверждении синхронно стирает кеш и диспатчит `AuthEventDeleteAccount` до знания результата запроса |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventDeleteAccount` | CURRENT | событие, инициирующее удаление аккаунта |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventDeleteAccount>` | CURRENT | вызывает `deleteUser()` без try/catch, затем безусловно `logout()` и эмитит `AuthLogout`/`AuthInitial` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.deleteUser` | CURRENT | отправляет `DELETE {Constants.authSerivceApi}/user`; ловит `DioException`, но перевыбрасывает только при `error_type == "passwords.token"` — любая другая ошибка молча проглатывается |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | стирает `AUTH_BOX` целиком, `AppCacheService.setAuthorizedFlag(false)`, публикует `false` в auth-стрим — вызывается безусловно после `deleteUser()` |
| `lib/repositories/auth/auth_repository.dart` | `ResetPasswordError` | CURRENT | исключение, которое бросается только в ветке `error_type == "passwords.token"` — в данном сценарии (любая другая ошибка) не создаётся |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearAllCache` | CURRENT | синхронно стирает локальный Hive-кеш ещё до вызова `deleteUser()` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSplashScreen`, `AuthLogout`, `AuthInitial` | CURRENT | состояния, эмитируемые в этой ветке — идентичны успешному пути |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый путь auth-сервиса, используемый в DELETE-запросе |

## Критерии приёмки

- При `DioException` от `DELETE {Constants.authSerivceApi}/user` с
  `error_type`, отличным от `"passwords.token"` (включая отсутствие
  `error_type` или отсутствие `response`), `AuthRepository.deleteUser()`
  завершается без исключения (`Future<void>` completes).
- После этого `AuthBloc.on<AuthEventDeleteAccount>` эмитит
  последовательность `AuthSplashScreen` → `AuthLogout` → `AuthInitial`, ту
  же, что при подтверждённом серверном успехе — на уровне состояний бота
  различить успех и эту ошибочную ветку невозможно.
- Локальный `AUTH_BOX` стирается (`logout()` выполняется) независимо от
  того, был ли аккаунт фактически удалён на сервере.
- Ни в одном состоянии бота, ни в UI не появляется сообщение об ошибке — с
  точки зрения интерфейса результат неотличим от `DELETE_OK`.

## Связанные тесты

`test/repositories/auth_repository_test.dart`, group `'UC-8/UC-9 (sendCodeToEmail) / UC-10/UC-11/UC-12 (resetPassword) / UC-19/UC-20 (deleteUser)'`,
test `'UC-49 БАГ: deleteUser — ошибка сервера, отличная от passwords.token,
молча проглатывается (метод завершается без исключения, аккаунт по факту не
удалён)'`.

На уровне `AuthBloc` отдельного теста на эту ветку нет: `test/blocs/auth_bloc_test.dart`,
group `'UC-19 — AuthEventDeleteAccount'` содержит один тест,
`'удаляет пользователя, затем выходит из сессии'`, где `authRepository.deleteUser()`
замокан как всегда успешный (`thenAnswer((_) async {})`) — ветка с ошибкой
сервера на уровне bloc'а не воспроизведена. TBD — теста на этом уровне нет.

## Открытые вопросы и ограничения

- **Repository-уровень протестирован, bloc-уровень для этой конкретной ветки
  — TBD.** Существующий bloc-тест мокает `deleteUser()` только успешным
  ответом; поведение `AuthBloc`, наблюдаемое в этом сценарии (безусловный
  логаут после того, как `deleteUser()` не бросил исключение), выведено
  чтением кода `auth_bloc.dart`, а не отдельным bloc-тестом на этот путь.
- Нет способа отличить настоящий `DELETE_OK` от этого `DELETE_ERROR` ни в
  одном состоянии `AuthBloc`, ни в UI — оба заканчиваются одинаковой
  последовательностью `AuthSplashScreen` → `AuthLogout` → `AuthInitial`.
  Пользователь не получает никакого сигнала о том, что сервер отклонил
  запрос.
- `AppCacheService.clearAllCache()` вызывается синхронно в обработчике
  кнопки диалога до диспатча `AuthEventDeleteAccount` и до какого-либо
  сетевого ответа — то есть локальные данные необратимо теряются даже в
  этой ошибочной ветке, независимо от последующего исхода `deleteUser()`.
- Условие `error_type == "passwords.token"` в `deleteUser()` дословно
  повторяет условие из `resetPassword()` — нет никаких признаков в коде,
  что оно осмысленно выбрано именно для сценария удаления аккаунта, а не
  скопировано.
