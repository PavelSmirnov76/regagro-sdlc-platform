- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md), [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)

# UC-19 — Авторизованный пользователь удаляет аккаунт (успех)

## Назначение

Авторизованный пользователь окончательно удаляет свою учётную запись из
настроек профиля. Сценарий описывает успешный клиентский путь: запрос на
удаление уходит на сервер и не завершается исключением (см. «Открытые
вопросы» — это не всегда означает, что аккаунт реально удалён на сервере),
после чего приложение обязательно выполняет локальный логаут и очищает
локальный кеш сессии.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь. Доступность сценария целиком
гейтится `AppCacheService.isAuthorized()` (кэшированный флаг, не живая
проверка `AuthRepository.isAuthorized()`) — кнопка удаления аккаунта вообще не
рендерится, пока пользователь не авторизован; гостю ([ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md)) этот путь
недоступен.

## CURRENT

### Основной поток

1. Пользователь открывает раздел «Профиль» → аккордеон «Безопасность»
   (`_ProfileSettingsSecurity` в `ProfileSettingsView`). Кнопка удаления
   аккаунта (`_DeleteAccountButton`) отрендерена только когда
   `AppCacheService.isAuthorized() == true`.
2. Нажатие кнопки вызывает `_showDeleteAccountDialog(context)` — модальный
   `showDialog` (`useRootNavigator: true`) с `CustomDialog`: заголовок
   (`l10n.delete_account_title`), текст предупреждения
   (`l10n.delete_account_message`) и две кнопки — «Удалить»
   (`BlackCircleButton.secondary`) и «Отмена» (`BlackCircleButton`).
3. Пользователь нажимает «Удалить». Синхронный `onTap`, в этом порядке:
   `Navigator.of(dialogContext).pop(false)` закрывает диалог,
   `context.go(Routes.profile)` переходит на экран профиля,
   `AppCacheService.clearAllCache()` запускается **без `await`** (см.
   «Открытые вопросы»), и сразу следующей строкой —
   `authBloc.add(AuthEventDeleteAccount())` отправляет событие в `AuthBloc`.
4. `AppCacheService.clearAllCache()` очищает содержимое четырёх Hive-боксов
   (`AppCacheService._openBoxes`): бокс `NewAppVersionHive`
   (`AppUpdateRepository.newAppVersionBoxKey`), `AUTH_BOX`, `LOGIN_BOX` и
   `DEVELOPER_BOX` — шире, чем стирает `AuthRepository.logout()` (только
   `AUTH_BOX`, см. п. 7 и «Связанные сущности»).
5. `AuthBloc.on<AuthEventDeleteAccount>` эмитит `AuthSplashScreen()`.
6. Обработчик вызывает `await AuthRepository.deleteUser()` —
   `ApiMessage(link: '${Constants.authSerivceApi}/user', method:
   ApiMethod.delete)` через `ApiClient` (`farm_rpc`-инстанс). Тело ответа
   сервера не парсится и не используется — успех определяется исключительно
   отсутствием исключения, долетевшего из вызова.
7. Обработчик вызывает `await AuthRepository.logout()`. Так как на этот момент
   `isAuthorized()` ещё возвращает `true` (главный токен `deleteUser()` не
   трогал), выполняется полная ветка: `_getAuthBox().clear()` (стирает
   `AUTH_BOX` целиком — главный токен, `User`, серверные интеграции),
   `AppCacheService.setAuthorizedFlag(false)`, и публикация `false` в
   `_authStreamController` (см. п. 9 — этот же вызов запускает побочный
   эффект, отдельный от основной последовательности состояний).
8. Обработчик эмитит `AuthLogout()`, затем вызывает `_emitInitial(emit)`,
   который эмитит `AuthInitial(login: _login, password: _password,
   appVersion: ...)` — с теми же `_login`/`_password`, что уже были в памяти
   блока (этот обработчик их не сбрасывает).
9. Одновременно (асинхронно — `_authStreamController` создан как
   `StreamController.broadcast()`, без `sync: true`) публикация `false` из
   п. 7 доходит до `_authSubscription`, оформленной в конструкторе
   `AuthBloc`: `if (!event) add(AuthEventLogout(clearData: false))`. Это
   добавляет в очередь блока **второе** событие `AuthEventLogout`, чья
   обработка проходит тот же путь ещё раз: `AuthSplashScreen()` → (без
   повторного вызова `logout()`, так как `clearData: false`) → `AuthLogout()`
   → `_emitInitial` → второй `AuthInitial` с теми же значениями
   `_login`/`_password`, что и в п. 8.
10. Каждое полученное состояние `AuthLogout` (то есть дважды, по числу п. 8 и
    п. 9) независимо ловят два разных `BlocListener<AuthBloc, AuthState>`:
    - `MainPage.build` — диспатчит `DataUpdateBloc.add(DataUpdateClear())`,
      вызывает `popUntil` до первого маршрута на обоих shell-навигаторах
      (`shellNavigatorMessagesKey`/`shellNavigatorMainNavigatorKey`) и
      `context.go(Routes.profile)`;
    - `_ProfilePageState.build` (уже открытая на `Routes.profile` страница,
      см. п. 3) — тоже диспатчит `DataUpdateBloc.add(DataUpdateClear())`.
    Итого `DataUpdateClear()` диспетчится до четырёх раз за один сценарий
    удаления аккаунта (два независимых слушателя × два прохода `AuthLogout`).
    Это тот же путь UI-реакции, что и при обычном выходе из аккаунта
    ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md), [UC-16](UC-16-ACTOR-1-EVT-7-ENT-2-DELETE_OK-IN-AUTH.md)).
11. `ProfilePage`'s `BlocProvider<ProfileEditCubit>` пересоздаётся при
    навигации на `Routes.profile`; `ProfileEditCubit.load()` видит
    `_authRepository.isAuthorized() == false` (главный токен уже стёрт) и
    эмитит состояние с `currentUserData: null` — `ProfilePage.build` при
    `currentUserData == null` рендерит `LoginView` вместо `ProfileView`,
    пользователь визуально оказывается на экране входа.

### Альтернативные потоки

- **`deleteUser()` бросает `ResetPasswordError` (`error_type ==
  "passwords.token"`) или иное исключение, не перехваченное внутри
  `deleteUser()`/`logout()`.** `on<AuthEventDeleteAccount>` не оборачивает
  вызовы в try/catch — исключение вылетает из обработчика необработанным,
  стрим блока застревает на `AuthSplashScreen()`, не доходя ни до
  `AuthLogout`, ни обратно до рабочего состояния. Отдельный сценарий (иной
  `RESULT`), не описан этим use-case.
- **Сеть недоступна ещё до вызова.** Как и все сценарии [MOD-1](../modules/MOD-1-AUTH.md), вызов
  online-only; при обрыве соединения `deleteUser()`/`logout()` бросают
  сетевое исключение — тот же альтернативный поток выше, не эта ветка.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — сущность сегмента `ENT` в id: запрос удаления адресован
  именно этой учётной записи на сервере (`DELETE {authSerivceApi}/user`);
  локально закешированный `User` в `AUTH_BOX` стирается вместе с остальным
  содержимым бокса на шаге 7 (и ещё раньше — на шаге 4, вместе со всем боксом,
  через `clearAllCache()`).
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session) — стирается дважды разными путями: сначала целиком (вместе
  с `AUTH_BOX`, `LOGIN_BOX`, `DEVELOPER_BOX`) через `AppCacheService
  .clearAllCache()` на шаге 4, до сетевого вызова; затем ещё раз, только
  `AUTH_BOX`, через `AuthRepository.logout()` на шаге 7. В отличие от обычного
  выхода ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)), где `LOGIN_BOX` (запомненный `lastLogin`) явно переживает
  `logout()` (см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), «Инварианты»), при удалении аккаунта запомненный
  логин тоже стирается — из-за предварительного `clearAllCache()`, а не
  из-за `logout()` самого по себе.

### Бизнес-правила

- Сценарий доступен только авторизованному пользователю — гейт на уровне UI
  (`AppCacheService.isAuthorized()`), кнопка не рендерится для гостя.
- Обязательное модальное подтверждение — само действие происходит только по
  явному нажатию «Удалить» в диалоге; закрытие диалога или «Отмена» не
  порождают ни `AuthEventDeleteAccount`, ни какой-либо другой эффект.
- Локальная очистка кеша (4 Hive-бокса) запускается ДО сетевого вызова
  удаления и не ожидает (`await`) собственного завершения — порядок
  завершения между очисткой кеша и сетевым удалением не гарантирован (см.
  «Открытые вопросы»).
- На сервере порядок строго последовательный: сначала `DELETE /user`, затем
  `logout()` — обработчик явно `await`-ит оба вызова один за другим
  (`verifyInOrder` в тесте).
- Успех определяется исключительно отсутствием исключения из `deleteUser()` —
  тело ответа сервера не парсится, аналогично `resetPassword`/
  `sendCodeToEmail` ([EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md)/[EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)).
- Терминальная последовательность состояний блока (`AuthSplashScreen` →
  `AuthLogout` → `AuthInitial`) идентична последовательности обычного выхода
  из аккаунта с `clearData: true` ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)) — удаление аккаунта не вводит
  собственного терминального состояния.
- Как и все сценарии [MOD-1](../modules/MOD-1-AUTH.md), вызов полностью online-only: нет локального
  черновика удаления и нет отложенной синхронизации.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью реализован, TARGET не добавляет нового
объёма работы.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_DeleteAccountButton` | CURRENT | кнопка удаления аккаунта, видна только при `AppCacheService.isAuthorized()` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_showDeleteAccountDialog` | CURRENT | модальный диалог подтверждения; по «Удалить» — `Navigator.pop`, `context.go(Routes.profile)`, `AppCacheService.clearAllCache()` (без `await`), затем `AuthEventDeleteAccount` |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized` | CURRENT | гейтит видимость кнопки (кэшированный флаг) |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearAllCache` | CURRENT | очищает 4 Hive-бокса (`_openBoxes`) до сетевого вызова удаления |
| `lib/data/services/app_cache_service.dart` | `AppCacheService._openBoxes` | CURRENT | перечисляет боксы, которые чистит `clearAllCache`: `NewAppVersionHive`, `AUTH_BOX`, `LOGIN_BOX`, `DEVELOPER_BOX` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventDeleteAccount>` | CURRENT | эмитит `AuthSplashScreen`, вызывает `deleteUser()` затем `logout()`, эмитит `AuthLogout()` → `_emitInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc` (конструктор, `_authSubscription`) | CURRENT | подписка на `getAuthStream()`; при получении `false` добавляет второе `AuthEventLogout(clearData: false)` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._emitInitial` | CURRENT | эмитит терминальный `AuthInitial(login: _login, password: _password, ...)` |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventDeleteAccount` | CURRENT | событие-триггер, без полей |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthLogout` | CURRENT | терминальное состояние, общее с обычным выходом ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.deleteUser` | CURRENT | `DELETE {Constants.authSerivceApi}/user`; глотает любую ошибку, кроме `error_type == "passwords.token"` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | стирает `AUTH_BOX`, выставляет флаг авторизации в `false`, публикует `false` в поток авторизации |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | определяет, идёт ли `logout()` по полной ветке очистки (актуально в п. 7 основного потока) |
| `lib/pages/main/main_page.dart` | `MainPage.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | на каждое `AuthLogout` — `DataUpdateClear`, `popUntil` на обоих shell-навигаторах, `context.go(Routes.profile)` |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | на каждое `AuthLogout` — второй независимый `DataUpdateClear`; рендерит `LoginView`, когда `ProfileEditCubit.currentUserData == null` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | `_authRepository.isAuthorized() == false` → `currentUserData: null`, переключает `ProfilePage` на экран входа |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый URL auth-сервиса, используемый в пути `/user` |

## Критерии приёмки

- Кнопка удаления аккаунта видна только когда `AppCacheService.isAuthorized()
  == true`; для неавторизованного пользователя она не рендерится.
- Действие требует явного подтверждения в модальном диалоге — событие
  `AuthEventDeleteAccount` отправляется только по нажатию «Удалить», не по
  закрытию диалога и не по «Отмена».
- `AuthRepository.deleteUser()` отправляет ровно один запрос с методом
  `ApiMethod.delete` на путь, оканчивающийся `/user`.
- `on<AuthEventDeleteAccount>` вызывает `deleteUser()` и `logout()` строго в
  этом порядке и эмитит последовательность `AuthSplashScreen()` →
  `AuthLogout()` → `AuthInitial`.
- После завершения обработчика `AuthRepository.isAuthorized()` возвращает
  `false` — главный токен и `User` удалены из `AUTH_BOX`.
- `AppCacheService.clearAllCache()` очищает `NewAppVersionHive`-бокс,
  `AUTH_BOX`, `LOGIN_BOX` и `DEVELOPER_BOX`.
- Приложение переходит на экран профиля и рендерит `LoginView` так же, как
  при обычном выходе ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md), [UC-16](UC-16-ACTOR-1-EVT-7-ENT-2-DELETE_OK-IN-AUTH.md)) — через `BlocListener`'ы в
  `MainPage` и `ProfilePage`, реагирующие на `AuthLogout`.

## Связанные тесты

- `test/blocs/auth_bloc_test.dart`, group `'UC-19 — AuthEventDeleteAccount'`, test `'удаляет
  пользователя, затем выходит из сессии'` — проверяет
  `verifyInOrder([deleteUser(), logout()])` и последовательность состояний
  `AuthSplashScreen()` → `AuthLogout()` → `isA<AuthInitial>()` при
  замоканном `AuthRepository`.
- `test/repositories/auth_repository_test.dart`, group `'UC-8/UC-9 (sendCodeToEmail) / UC-10/UC-11/UC-12 (resetPassword) / UC-19/UC-20 (deleteUser)'`, test `'UC-47:
  deleteUser отправляет DELETE на /user'` — проверяет метод (`ApiMethod
  .delete`) и путь (`endsWith('/user')`) отправленного `ApiMessage`.

## Открытые вопросы и ограничения

- `AppCacheService.clearAllCache()` в `_showDeleteAccountDialog` вызывается
  без `await` перед `authBloc.add(AuthEventDeleteAccount())` — гонка: нет
  гарантии, что локальные Hive-боксы будут физически очищены раньше, чем
  обработчик `AuthEventDeleteAccount` начнёт (или даже успеет закончить)
  сетевые вызовы `deleteUser()`/`logout()`.
- Известный дефект, скопированный из `resetPassword` (см. [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md), [UC-11](UC-11-ACTOR-2-EVT-5-ENT-1-UPDATE_REJECTED-IN-AUTH.md)):
  `AuthRepository.deleteUser` перехватывает только `DioException` и
  пробрасывает исключение лишь при `error_type == "passwords.token"` — любая
  другая ошибка сервера или сети молча проглатывается, и `deleteUser()`
  завершается так, будто аккаунт удалён, хотя на сервере он мог остаться.
  Обработчик `on<AuthEventDeleteAccount>` в этом случае проходит именно эту,
  `DELETE_OK`-ветку — то есть часть случаев, ошибочно приводящих к клиентскому
  «успеху», относится к этому же use-case, а не к отдельному сценарию ошибки.
  Подтверждено тестом `'UC-49 БАГ: deleteUser — ошибка сервера, отличная от
  passwords.token, молча проглатывается...'`
  (`test/repositories/auth_repository_test.dart`).
- `error_type == "passwords.token"` — единственная ветка, которую `deleteUser`
  явно различает и пробрасывает как `ResetPasswordError`; она скопирована из
  `resetPassword` ([EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)), и семантически «неверный/истёкший код сброса
  пароля» не имеет отношения к удалению аккаунта — похоже на нерефлексированный
  copy-paste, а не осознанное бизнес-правило для [EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md). Эта ветка не имеет
  собственного теста для `deleteUser` (только для `resetPassword`) и не
  покрывается этим use-case (другой `RESULT`).
- Реактивная подписка `AuthBloc` на `getAuthStream()` добавляет второе,
  избыточное событие `AuthEventLogout(clearData: false)` при каждом успешном
  удалении аккаунта, потому что `AuthRepository.logout()`, вызванный внутри
  `on<AuthEventDeleteAccount>`, публикует `false` в тот же поток, на который
  подписан сам блок (см. основной поток, п. 9–10). Это приводит к повторной
  эмиссии `AuthSplashScreen()` → `AuthLogout()` → `AuthInitial` и к повторному
  срабатыванию обоих `BlocListener`'ов (`MainPage` и `ProfilePage`) — второй
  `DataUpdateClear` от каждого, второй `popUntil`, второй
  `context.go(Routes.profile)`. Конечные значения идентичны первому проходу,
  поэтому пользователь этого не замечает — но это задокументированная лишняя
  работа, не смоделированная явно в коде. Существующий bloc-тест не ловит
  этот эффект, потому что мокирует `AuthRepository` целиком — реальный
  `logout()` (с публикацией в поток) в тесте не выполняется. Тот же механизм,
  с тем же выводом, уже задокументирован для обычного выхода ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md),
  [UC-16](UC-16-ACTOR-1-EVT-7-ENT-2-DELETE_OK-IN-AUTH.md), «Альтернативные потоки») — здесь он верен один-в-один, потому что
  этот сценарий вызывает тот же `AuthRepository.logout()`.
- `AppCacheService.clearAllCache()` дополнительно стирает `LOGIN_BOX`
  (запомненный `lastLogin`) и `DEVELOPER_BOX` — в отличие от изолированного
  `AuthRepository.logout()`, который трогает только `AUTH_BOX`, а
  `LOGIN_BOX`/`DEVELOPER_BOX` явно переживают именно этот метод (см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md),
  «Инварианты»). Полный сценарий удаления аккаунта стирает больше локального
  состояния, чем один только `logout()`, — включая запомненный логин. Тот же
  разрыв между «инвариантом метода» и «полным пользовательским путём» уже
  задокументирован для обычного выхода ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md), [UC-16](UC-16-ACTOR-1-EVT-7-ENT-2-DELETE_OK-IN-AUTH.md)), который тоже
  вызывает `clearAllCache()` из своей кнопки — но не является этим же
  вызовом: два разных места в UI (`_ProfileSettingsButtons` для выхода,
  `_showDeleteAccountDialog` для удаления аккаунта) независимо дублируют
  один и тот же паттерн «`clearAllCache()` без `await`, затем событие
  `AuthBloc`».
