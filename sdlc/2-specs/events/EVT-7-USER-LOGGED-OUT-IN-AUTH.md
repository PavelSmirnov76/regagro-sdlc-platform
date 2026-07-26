# EVT-7 — user.logged_out

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Авторизованный пользователь явно нажимает «выйти»; `AuthBloc.on<AuthEventLogout>`.

**Эффект.** `AuthRepository.logout` стирает весь авторизационный Hive-бокс целиком (главный токен, пользователь, серверные интеграции) — запомненный логин переживает выход. Если сам вызов бросает исключение, обработчик не перехватывает её — состояние приложения зависает вместо перехода на экран логина.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc.on<AuthEventLogout>`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.logout`.
