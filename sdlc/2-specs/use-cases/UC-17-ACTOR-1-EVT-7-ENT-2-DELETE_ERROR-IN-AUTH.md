# UC-17 — Явный выход из аккаунта: локальный сбой очистки сессии (ошибка)

## Назначение

Авторизованный пользователь явно нажимает «выйти» в настройках профиля, как и
в успешном сценарии, но локальная очистка сессии — `AuthRepository.logout()`
— бросает исключение (например сбой ввода-вывода Hive-бокса). Обработчик
события `on<AuthEventLogout>` в `AuthBloc` не оборачивает вызов в try/catch —
известный, задокументированный дефект: ни `AuthLogout`, ни `AuthInitial` не
эмитятся, приложение зависает на состоянии `AuthSplashScreen`, экран выхода
из аккаунта не завершается, и пользователь не получает никакого сообщения об
ошибке.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — только авторизованный пользователь может явно выйти
из аккаунта; событие требует уже установленного главного токена.

## CURRENT

### Основной поток

1. Пользователь на экране настроек профиля (`_ProfileSettingsButtons` в
   `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`)
   нажимает кнопку «выйти» (`l10n.logout`).
2. Обработчик `onTap` синхронно, без `await`, выполняет три действия подряд:
   `context.go(Routes.profile)` (немедленная навигация на экран профиля),
   `AppCacheService.clearAllCache()` (запущен и не дожидается —
   `Future<void>` игнорируется вызывающим кодом) и
   `context.read<AuthBloc>().add(AuthEventLogout())` — `AuthEventLogout` с
   параметром по умолчанию `clearData: true`.
3. `AuthBloc.on<AuthEventLogout>` эмитит `AuthSplashScreen()` первым шагом.
4. Так как `event.clearData == true`, обработчик вызывает
   `await _authRepository.logout()` — **без try/catch вокруг вызова**.
5. `AuthRepository.logout()`: пользователь авторизован
   (`isAuthorized() == true`), поэтому метод получает бокс
   `_getAuthBox()` (`Hive.box<dynamic>(authBoxKey)`) и вызывает
   `await box.clear()`. В этом сценарии `box.clear()` бросает исключение
   (например сбой ввода-вывода на уровне Hive) — само тело `logout()` тоже не
   перехватывает эту ошибку, она пробрасывается как есть.
6. Исключение всплывает из `AuthRepository.logout()` прямо в тело обработчика
   `on<AuthEventLogout>` в `AuthBloc`, минуя `emit(const AuthLogout())` и
   `await _emitInitial(emit)` — эти две строки просто не выполняются.
7. Необработанное исключение внутри обработчика события `Bloc` перехватывается
   инфраструктурой `flutter_bloc` на уровне самого `Bloc` (не приложения) и
   уходит в `Bloc.observer` — в проекте это `TalkerBlocObserver`
   (`lib/injection_container.dart`), который логирует ошибку через `Talker`.
   Дальше по стриму состояний `AuthBloc` ничего не эмитится.
8. Итоговый поток состояний блока для этого события —
   `[AuthSplashScreen()]`, и только: `AuthLogout` не эмитится, `AuthInitial`
   не эмитится.
9. Слушатели, ожидающие `AuthLogout` (`MultiBlocListener` в
   `lib/pages/main/main_page.dart` и `BlocListener<AuthBloc, AuthState>` в
   `lib/pages/profile/presentation/profile_page.dart`), не срабатывают:
   `DataUpdateClear` не диспатчится в `DataUpdateBloc`, стеки
   `shellNavigatorMessagesKey`/`shellNavigatorMainNavigatorKey` не
   схлопываются, повторный `context.go(Routes.profile)` из
   `main_page.dart` не происходит (шаг 2 уже увёл пользователя на экран
   профиля средствами самой кнопки, независимо от исхода выхода).
10. Никакое сообщение об ошибке не показывается: ветка `AuthEventAuth`/
    `AuthEventStart` эмитит `AuthMessage(e.toString())` в своих catch-блоках,
    но у `on<AuthEventLogout>` catch-блока нет вовсе — `AuthMessage` не
    эмитится, и ни один `SnackBar`/`ScaffoldMessenger`, завязанный на это
    состояние (см. `profile_page.dart`), не появляется.
11. Поскольку `box.clear()` не завершился успешно, `AUTH_BOX` фактически не
    очищен — главный токен/`User`/`serverIntegrations` остаются в Hive.
    Строка `await AppCacheService.setAuthorizedFlag(false)` в `logout()`
    находится после вызова `box.clear()`, поэтому тоже не выполняется, как и
    `_authStreamController.sink.add(false)` — реактивная подписка
    `AuthBloc._authSubscription` на `getAuthStream()` (которая иначе сама
    диспатчит `AuthEventLogout(clearData: false)`) не получает сигнала.
    Итог: `AuthRepository.isAuthorized()` продолжает возвращать `true`, сессия
    формально остаётся активной несмотря на то, что пользователь инициировал
    выход.

### Альтернативные потоки

- **Пользователь пробует выйти повторно.** Так как `AuthBloc` не перешёл ни в
  `AuthLogout`, ни в `AuthInitial`, а остался «застрявшим» на последнем
  эмитнутом состоянии (`AuthSplashScreen`), кнопка выхода при повторном нажатии
  снова диспатчит `AuthEventLogout()` — каждый повтор проходит тот же путь
  (шаги 3–8) и снова заканчивается тем же необработанным исключением, если
  первопричина сбоя (например повреждённый Hive-бокс) не устранена сама
  собой.
- **`AppCacheService.clearAllCache()` (шаг 2) и `AuthRepository.logout()`
  (шаг 5) — два независимых пути очистки Hive, оба трогают тот же
  `AUTH_BOX`, оба не await'ятся синхронно друг относительно друга.**
  `clearAllCache()` открывает боксы через `Hive.openBox<dynamic>(...)`,
  включая `authBoxKey` с шифрованием (`AppCacheService._openBoxes` в
  `lib/data/services/app_cache_service.dart`), тогда как
  `AuthRepository._getAuthBox()` ожидает, что бокс уже открыт синхронным
  `Hive.box<dynamic>(authBoxKey)`. Оба вызова из шага 2 запущены без `await` в
  необъявленном `async`-обработчике `onTap` — гонка между ними как
  правдоподобная причина реального (не только смоделированного тестом) сбоя
  `box.clear()` не подтверждена тестом и вынесена в «Открытые вопросы».
- **Автоматический выход того же события ([ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md), «мягкий»
  логаут через `_authSubscription`)** диспатчит то же `AuthEventLogout`, но с
  `clearData: false` — в этой ветке `_authRepository.logout()` вообще не
  вызывается (`if (event.clearData) { await _authRepository.logout(); }`), а
  значит этот конкретный дефект (падение внутри `logout()`) для
  автоматического выхода недостижим тем же путём; это отдельный сценарий,
  не описываемый этим use-case.

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — центральная сущность: `logout()` должен стереть
  весь `AUTH_BOX` (главный токен, `User`, `serverIntegrations`), но из-за
  необработанного исключения делает это не полностью или не делает вовсе;
  `isAuthorized()` продолжает опираться на несостоявшуюся очистку.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — хранится в том же `AUTH_BOX`, что и токен; при
  несостоявшейся `box.clear()` объект `User` тоже остаётся в Hive, хотя
  пользователь визуально считает, что вышел.

### Бизнес-правила

- Единственная ветка `AuthEventLogout`, реально вызывающая
  `AuthRepository.logout()`, — это `event.clearData == true` (значение по
  умолчанию конструктора `AuthEventLogout`); обработчик события целиком не
  имеет try/catch, поэтому любое исключение из `logout()` (не только
  Hive-специфичное) обрывает весь остаток обработчика.
- Нет отличия между «сервер отклонил» и «локальная ошибка» — на этом пути
  сервер вообще не участвует: `AuthRepository.logout()` — чисто локальная
  Hive-операция, исключение может быть только техническим сбоем клиента
  (ERROR, не REJECTED).
- Отсутствие try/catch в `on<AuthEventLogout>` — асимметрия по сравнению с
  `on<AuthEventAuth>`/`on<AuthEventStart>` в том же файле, у которых есть
  catch-блок, эмитирующий `AuthMessage` и откатывающийся на `AuthInitial`
  через защитный вызов того же `_authRepository.logout()` (вызванный без
  `await` — сам по себе отдельный, задокументированный в тестах риск не в
  этой ветке) — для `AuthEventLogout` эквивалентного отката не предусмотрено
  вовсе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий (включая дефект) полностью воспроизведён в коде и покрыт
тестом. Гипотеза о реальном (не смоделированном) триггере сбоя — гонка между
`AppCacheService.clearAllCache()` и `AuthRepository.logout()` за один и тот же
Hive-бокс — не подтверждена отдельным тестом и вынесена в «Открытые вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_ProfileSettingsButtons` | CURRENT | кнопка «выйти»: `context.go(Routes.profile)` → `AppCacheService.clearAllCache()` (не await'ится) → `AuthEventLogout()` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventLogout>` | CURRENT | обработчик без try/catch; эмитит `AuthSplashScreen`, затем при `clearData == true` вызывает `_authRepository.logout()` без защиты от исключений |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventLogout` | CURRENT | событие, `clearData` по умолчанию `true` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthSplashScreen` | CURRENT | последнее эмитнутое состояние в этой ветке — приложение «зависает» на нём |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthLogout` | CURRENT | состояние, которое должно было эмититься следующим, но не эмитится |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthMessage` | CURRENT | состояние для сообщения об ошибке — не эмитится в этой ветке, в отличие от catch-блоков `AuthEventAuth`/`AuthEventStart` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | стирает `AUTH_BOX` целиком через `_getAuthBox().clear()`; не оборачивает вызов в try/catch |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository._getAuthBox` | CURRENT | `Hive.box<dynamic>(authBoxKey)` — синхронный доступ, предполагает уже открытый бокс |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.clearAllCache` | CURRENT | параллельный, независимый путь очистки того же `AUTH_BOX` (через `clearHiveBoxes`/`_openBoxes`), запущенный без `await` из того же `onTap` |
| `lib/pages/main/main_page.dart` | `MultiBlocListener` (`BlocListener<AuthBloc, AuthState>`) | CURRENT | слушает `AuthLogout` для `DataUpdateClear` и схлопывания навигации — не срабатывает, если `AuthLogout` не эмитится |
| `lib/pages/profile/presentation/profile_page.dart` | `BlocListener<AuthBloc, AuthState>` | CURRENT | слушает `AuthMessage`/`AuthLogout` для снекбара и `DataUpdateClear` — ни один вариант не срабатывает в этой ветке |
| `lib/injection_container.dart` | `Bloc.observer` (`TalkerBlocObserver`) | CURRENT | перехватывает необработанное исключение из обработчика события `Bloc` и логирует его через `Talker`; не эмитит состояние и не показывает ничего пользователю |

## Критерии приёмки

- При падении `AuthRepository.logout()` (например исключение при
  `box.clear()`) поток состояний `AuthBloc` для события `AuthEventLogout()`
  состоит ровно из одного состояния — `AuthSplashScreen()`.
- `AuthLogout` не эмитится; `AuthInitial` не эмитится.
- Исключение долетает до `Bloc`-инфраструктуры (наблюдаемо через `errors` в
  `blocTest`/`Bloc.observer`), не роняя изолят и не показывая пользователю
  никакого сообщения.
- `AuthMessage` не эмитится ни на одном шаге этой ветки.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-17 — AuthEventLogout ERROR (известный дефект — локальный сбой очистки не обрабатывается)'`.

## Открытые вопросы и ограничения

- **Известный дефект, не пофикшен.** `on<AuthEventLogout>` в `AuthBloc` —
  единственный основной обработчик события выхода без try/catch в файле;
  все остальные (`AuthEventAuth`, `AuthEventStart`) откатываются на
  `AuthMessage` + `AuthInitial`. Симметричный фикс (try/catch с откатом на
  `AuthMessage`/`AuthInitial`, аналогично соседним обработчикам) выходит за
  рамки этого прохода документирования CURRENT.
- **Правдоподобный, но не подтверждённый тестом реальный триггер.**
  `AppCacheService.clearAllCache()` (шаг 2 основного потока) и
  `AuthRepository.logout()` (шаг 5) независимо и без взаимного `await`
  обращаются к одному и тому же `AUTH_BOX`: первый — асинхронным
  `Hive.openBox` с шифрованием, второй — синхронным `Hive.box`, ожидающим
  бокс уже открытым. Гонка между ними как источник настоящего (не
  смоделированного мокой) исключения при `box.clear()` не проверена
  отдельным интеграционным тестом.
- **Сессия может остаться формально активной.** Так как `box.clear()` не
  завершается, `AppCacheService.setAuthorizedFlag(false)` и
  `_authStreamController.sink.add(false)` внутри `logout()` (обе строки идут
  после `box.clear()`) тоже не выполняются — `AuthRepository.isAuthorized()`
  продолжает видеть валидный главный токен уже после того, как пользователь
  нажал «выйти». Не проверено, что происходит при следующем холодном старте
  приложения в этом состоянии — вне рамок этого use-case.
- Повторное нажатие кнопки выхода после сбоя не имеет отдельной защиты от
  повторных попыток (нет дебаунса/дизейбла кнопки на этом экране) — при
  сохраняющейся первопричине сбоя каждое нажатие проходит тот же путь и
  заканчивается тем же логированием без видимого пользователю эффекта.
