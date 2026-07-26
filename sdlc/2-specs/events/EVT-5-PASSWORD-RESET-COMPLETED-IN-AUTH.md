# EVT-5 — password_reset.completed

| | |
|---|---|
| Инициатор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Гость вводит полученный код, новый пароль и подтверждение; `ForgotPasswordCubit` завершающий шаг.

**Эффект.** `AuthRepository.resetPassword` — один запрос с email/кодом/новым паролем/подтверждением. Если сервер сообщает, что код неверен/истёк — пользователя возвращают на шаг ввода кода. Любая другая ошибка сервера или сети завершает вызов без исключения — пароль фактически не меняется, но вызывающий код об этом не узнаёт. Успех запускает [EVT-3](EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md).

**Исходный код.** `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` → `ForgotPasswordCubit`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.resetPassword`.
