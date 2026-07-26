- **derived from**: [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md), [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md)

# UC-18 — Приложение автоматически завершает сессию без явного выхода пользователя

## Назначение

Стрим состояния авторизации (`AuthRepository.getAuthStream()`) эмитит `false`
не в рамках явного нажатия «выйти» пользователем ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)) — приложение
реагирует само: `AuthBloc`, подписанный на этот стрим с момента своего
создания, диспатчит `AuthEventLogout(clearData: false)` и доводит состояние до
того же логаут-экрана, что и после явного выхода, но не вызывает повторно
`AuthRepository.logout()` — сессия к этому моменту уже не считается валидной,
дополнительная очистка Hive-бокса не требуется.

## Пользователь

[ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) — не человек, приложение действует автоматически, без
человеческого жеста в момент самого события. Человек, чья сессия здесь
завершается, до этого был [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) (авторизован); инициатор
именно этого перехода — не он, а сам `AuthBloc` в реакции на стрим.

## CURRENT

### Основной поток

1. `AuthBloc` в конструкторе подписывается на
   `AuthRepository.getAuthStream()`: `_authSubscription =
   _authRepository.getAuthStream().listen((event) async { if (!event)
   add(AuthEventLogout(clearData: false)); })`. Подписка живёт с момента
   создания `AuthBloc` до вызова `close()`.
2. Стрим эмитит `false` не в ответ на диспатч `AuthEventLogout(clearData:
   true)` пользователем ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md), отдельный сценарий) — сама эмиссия
   происходит внутри `AuthRepository` без прямого участия человека в этот
   момент (конкретные текущие источники такой эмиссии — см. «Альтернативные
   потоки»).
3. Слушатель диспатчит `AuthEventLogout(clearData: false)`.
4. `AuthBloc.on<AuthEventLogout>`: эмитит `AuthSplashScreen()`; поскольку
   `event.clearData == false`, `AuthRepository.logout()` НЕ вызывается — Hive
   AUTH_BOX (главный токен, `User`, `serverIntegrations`) этим обработчиком не
   трогается; затем эмитит `AuthLogout()`, затем вызывает `_emitInitial(emit)`,
   которое эмитит `AuthInitial(login: _login, password: _password, appVersion:
   ...)`.
5. Экраны вне [MOD-1](../modules/MOD-1-AUTH.md), слушающие `AuthBloc` через `BlocListener<AuthBloc,
   AuthState>`, реагируют на `AuthLogout` тем же кодом, что и после явного
   выхода: `_ProfilePageState.build` и `MainPage.build` диспатчат
   `DataUpdateClear()` в `DataUpdateBloc`; `MainPage.build` дополнительно
   вызывает `popUntil` на обоих shell-навигаторах (`shellNavigatorMessagesKey`,
   `shellNavigatorMainNavigatorKey`) и `context.go(Routes.profile)`;
   `ChatsView.build` вызывает `ChatsCubit.clear()`. Это принадлежит границе
   других модулей/экранов, не самому [MOD-1](../modules/MOD-1-AUTH.md), но входит в наблюдаемый эффект
   сценария.

### Альтернативные потоки

- **Явный выход пользователя ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md), `clearData: true`).** Отдельный
  сценарий: тот же обработчик `on<AuthEventLogout>` дополнительно вызывает
  `AuthRepository.logout()`, стирающий весь `AUTH_BOX`. Не описывается этим
  файлом.
- **Текущие конкретные источники эмиссии `false`, подтверждённые чтением
  `auth_repository.dart`:**
  - `AuthRepository.logout()` сам эмитит `_authStreamController.sink.add(false)`
    сразу после явной очистки бокса — то есть при явном выходе (альтернативный
    поток выше) эта же подписка получает эхо и повторно диспатчит
    `AuthEventLogout(clearData: false)` поверх уже идущей обработки исходного
    события; повторный диспатч безвреден: `clearData: false` не трогает Hive
    повторно, а bloc уже находится в терминальном для логаута состоянии.
  - `AuthRepository.init()` (вызывается из `on<AuthEventStart>`, [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md), на
    каждом холодном старте) безусловно пушит `isAuthorized()` в стрим; если
    пользователь не авторизован (гость либо сессия уже пуста), это тоже
    `false` и тоже вызывает этот же обработчик — параллельно со стартовым
    потоком [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md).
- **Подписка уже отменена.** `AuthBloc.close()` вызывает
  `_authSubscription.cancel()` — после этого дальнейшие эмиссии стрима не
  обрабатываются (bloc уничтожен).

### Связанные сущности

- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) — сущность события [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) по определению: эмиссия
  `false` в `AuthRepository.getAuthStream()` фиксирует конец действующей
  сессии. Фактическая очистка Hive-бокса (`AUTH_BOX`) этим обработчиком не
  выполняется — предполагается, что к моменту эмиссии сессия уже недействительна
  иным путём (см. инвариант [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) про отсутствие retry/refresh на 401/419).
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) — хранится в том же `AUTH_BOX`, что и главный токен; в
  отличие от явного выхода ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)), этот обработчик НЕ стирает запись `User`
  (нет вызова `logout()`); если бокс уже был очищен другим путём до эмиссии
  `false`, `User` уже отсутствовал независимо от этого сценария.

### Бизнес-правила

- `clearData: false` → `AuthRepository.logout()` не вызывается — нет повторной
  очистки Hive-бокса сессии.
- Итоговый переход состояния (`AuthSplashScreen` → `AuthLogout` →
  `AuthInitial`) и наблюдаемый эффект в UI (сброс `DataUpdateBloc`, `popUntil`
  до первого маршрута, переход на `Routes.profile`, очистка `ChatsCubit`) —
  те же, что и после явного выхода ([EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)); совпадение эффекта не делает это
  тем же событием — инициатор другой (приложение, а не пользователь).
- Стрим авторизации — единственный канал, по которому `AuthBloc` узнаёт о
  потере сессии без прямого пользовательского действия; других механизмов
  (push-уведомление, периодический опрос и т.п.) в коде нет.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью прослеживается в существующем коде и покрыт
тестами (см. «Связанные тесты»), с оговоркой про механизм триггера (см.
«Открытые вопросы и ограничения»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc` (подписка на `getAuthStream()` в конструкторе) | CURRENT | реагирует на `false` в стриме диспатчем `AuthEventLogout(clearData: false)` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventLogout>` | CURRENT | `AuthSplashScreen` → (если `clearData`) `logout()` → `AuthLogout` → `_emitInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc._emitInitial` | CURRENT | финальный переход в `AuthInitial` |
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.close` | CURRENT | `_authSubscription.cancel()` — момент, после которого стрим больше не обрабатывается |
| `lib/pages/profile/bloc/auth_event.dart` | `AuthEventLogout` | CURRENT | поле `clearData` (default `true`), здесь передаётся `false` |
| `lib/pages/profile/bloc/auth_state.dart` | `AuthLogout` / `AuthInitial` | CURRENT | целевые состояния сценария |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getAuthStream` | CURRENT | экспонирует `Stream<bool>` поверх `_authStreamController` |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.logout` | CURRENT | один из текущих источников эмиссии `false` (эхо после явной очистки при [EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)) |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.init` | CURRENT | другой источник эмиссии `isAuthorized()` (в т.ч. `false`) на каждом холодном старте |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized` | CURRENT | условие, чьё текущее значение отражается в стриме |
| `lib/network/auth_interceptor.dart` | `AuthInterceptor.onError` | CURRENT | детектирует 401/419, но не вызывает `logout()` и не толкает `false` в стрим сам — не является наблюдаемым в коде источником этого сценария |
| `lib/pages/profile/presentation/profile_page.dart` | `_ProfilePageState.build` | CURRENT | `BlocListener<AuthBloc, AuthState>` на `AuthLogout` → `DataUpdateClear()` |
| `lib/pages/main/main_page.dart` | `MainPage.build` | CURRENT | `BlocListener<AuthBloc, AuthState>` на `AuthLogout` → `DataUpdateClear()`, `popUntil` обоих shell-навигаторов, `context.go(Routes.profile)` |
| `lib/pages/chats/presentation/chats_view.dart` | `ChatsView.build` | CURRENT | `BlocListener<AuthBloc, AuthState>` на `AuthLogout` → `ChatsCubit.clear()` |

## Критерии приёмки

- Когда `AuthRepository.getAuthStream()` эмитит `false` не как прямой ответ на
  пользовательский диспатч `AuthEventLogout(clearData: true)`, `AuthBloc`
  без участия пользователя эмитит `AuthSplashScreen` → `AuthLogout` →
  `AuthInitial`.
- При этом `AuthRepository.logout()` НЕ вызывается — метод должен быть
  проверен как `verifyNever` в тесте на этот путь.
- Итоговое состояние `AuthInitial` достигается так же, как и на явном выходе,
  несмотря на разный обработчик-инициатор.

## Связанные тесты

`test/blocs/auth_bloc_test.dart`, group `'UC-16/UC-18 — AuthEventLogout'`, test
`'clearData: false -> НЕ вызывает logout() у репозитория'`; и group `'UC-18 — AuthBloc реактивная подписка на getAuthStream'`, test `'поток эмитит false -> диспатчится AuthEventLogout(clearData:false),
сессия завершается без явной очистки Hive'` — первый проверяет реакцию обработчика на сам факт
`clearData: false`, второй — что диспатч действительно происходит в ответ на
эмиссию стрима.

## Открытые вопросы и ограничения

- Единственные подтверждённые чтением источники эмиссии `false` в
  `getAuthStream()` — собственный `AuthRepository.logout()` (эхо сразу после
  явной очистки бокса) и `AuthRepository.init()` при холодном старте, когда
  `isAuthorized()` уже `false`. Ни один из них не воспроизводит буквально
  пример из [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) («токен стал недействителен на бэкенде» без явного вызова
  `logout()`, независимо от Auth-Bloc'а) — в проверенном коде нет отдельного
  места, которое бы детектировало именно server-side инвалидацию токена
  (истечение/отзыв) и толкало `false` в стрим в ответ; `AuthInterceptor.onError`
  детектирует 401/419, но не вызывает `logout()` и не пишет в стрим (см.
  инвариант [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) про отсутствие retry/refresh). То есть механизм, ради
  которого документирован этот сценарий, на практике сегодня наблюдается
  только как побочный эффект двух перечисленных внутренних вызовов, а не как
  отдельный «детектор потери сессии».
- Тест на реактивную подписку эмулирует эмиссию `false` напрямую через
  подменённый `StreamController<bool>` (мок `AuthRepository.getAuthStream()`),
  не через реальный `AuthRepository` — сам механизм построения такой эмиссии
  на практике (предыдущий пункт) отдельным тестом не покрыт.
