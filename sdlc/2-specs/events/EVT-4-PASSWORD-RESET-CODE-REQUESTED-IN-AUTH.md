# EVT-4 — password_reset.code_requested

| | |
|---|---|
| Инициатор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Гость вводит email на первом шаге восстановления пароля; `ForgotPasswordCubit`.

**Эффект.** `AuthRepository.sendCodeToEmail` отправляет запрос кода на email отдельным вызовом. Код на клиенте не валидируется — переход к следующему шагу мастера ничего не проверяет онлайн, реальная проверка кода происходит только при попытке сброса пароля ([EVT-5](EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)).

**Исходный код.** `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` → `ForgotPasswordCubit`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.sendCodeToEmail`.
