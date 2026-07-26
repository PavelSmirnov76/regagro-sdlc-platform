# EVT-9 — user.account_deletion_requested

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |

**Триггер.** Авторизованный пользователь подтверждает удаление аккаунта в модальном диалоге (доступно только авторизованному); `AuthBloc.on<AuthEventDeleteAccount>`.

**Эффект.** Локальный кеш очищается, затем `AuthRepository.deleteUser` отправляет запрос на удаление аккаунта серверу, и следом выполняется локальный выход (тот же путь, что [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md)). Любая серверная ошибка, кроме одного специфического типа, проглатывается без исключения — вызывающий код считает операцию успешной и делает локальный логаут, даже если аккаунт на сервере не был удалён.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc.on<AuthEventDeleteAccount>`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.deleteUser`.
