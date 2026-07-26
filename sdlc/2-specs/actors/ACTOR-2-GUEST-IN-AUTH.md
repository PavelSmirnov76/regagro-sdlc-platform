# ACTOR-2 — Гость

## Идентичность

Пользователь без сохранённого главного токена (`AuthRepository.isAuthorized() == false`). Гостевой доступ выдаётся автоматически при первом холодном старте приложения — отдельного экрана выбора не показывается, сам гость ничего не выбирает, чтобы им стать. Гость видит экран логина/регистрации без ограничений.

## Цели

Зарегистрироваться, войти в существующий аккаунт, либо восстановить забытый пароль — всё это доступно без сети до момента отправки конкретного действия.

## Действия

Инициирует [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md) (саморегистрация), [EVT-2](../events/EVT-2-USER-LOGGED-IN-IN-AUTH.md) (вход в систему), [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) (автовход после регистрации/сброса пароля), [EVT-4](../events/EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md) (запрос кода восстановления пароля), [EVT-5](../events/EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md) (сброс пароля по коду) — все через `AuthBloc`/`RegistrationCubit`/`ForgotPasswordCubit`.

Взаимодействует с сущностями [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (TokenData).

## Ограничения

Ни одно из действий гостя не работает без сети — каждое (`login`, `registerSelf`, `sendCodeToEmail`, `resetPassword`) ждёт прямого ответа сервера, локального черновика нет.

## Исходный код

| Файл | Класс/метод | Роль |
|---|---|---|
| `lib/pages/profile/presentation/widgets/login/login_view.dart` | `LoginView` | экран входа/перехода на регистрацию |
| `lib/pages/registration/cubit/registration_cubit.dart` | `RegistrationCubit.submit` | саморегистрация |
| `lib/pages/forgot_password/cubit/forgot_password_cubit.dart` | `ForgotPasswordCubit` | восстановление пароля (3 шага) |
| `lib/repositories/auth/auth_repository.dart` | `login`, `registerSelf`, `sendCodeToEmail`, `resetPassword` | сетевые вызовы всех действий гостя |
