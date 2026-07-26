# EVT-1 — user.self_registered

| | |
|---|---|
| Инициатор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |

**Триггер.** Гость заполняет форму регистрации (страна, тип животных, email, пароль+подтверждение, имя — обязательные; остальное опционально) и подтверждает; `RegistrationCubit.submit`.

**Эффект.** `AuthRepository.registerSelf` отправляет данные сразу на сервер — локально ничего не сохраняется. Если юридическая форма не выбрана, отправляется значение по умолчанию. Ошибки не различаются на уровне репозитория (нет try/catch) и пробрасываются как есть; кубит показывает пользователю текст ошибки из ответа сервера.

**Исходный код.** `lib/pages/registration/cubit/registration_cubit.dart` → `RegistrationCubit.submit`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.registerSelf`.
