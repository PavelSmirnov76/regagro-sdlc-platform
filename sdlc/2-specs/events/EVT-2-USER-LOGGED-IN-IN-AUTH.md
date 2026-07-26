# EVT-2 — user.logged_in

| | |
|---|---|
| Инициатор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Гость вводит логин/пароль и подтверждает; пустые поля отклоняются на клиенте без обращения к серверу. `AuthBloc.on<AuthEventAuth>`.

**Эффект.** `AuthRepository.login` требует активное соединение (проверяется до сетевого вызова), выполняет OAuth password grant, затем сразу запрашивает профиль тем же токеном. Успех — токен и пользователь сохраняются в зашифрованный Hive-бокс, кэшированный флаг авторизации проставляется в `true`. Неверные учётные данные различаются как осознанный отказ сервера; отсутствие сети или другая ошибка — как техническая.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc.on<AuthEventAuth>`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.login`.
