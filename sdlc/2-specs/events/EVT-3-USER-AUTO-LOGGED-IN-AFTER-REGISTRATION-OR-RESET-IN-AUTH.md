# EVT-3 — user.auto_logged_in_after_registration_or_reset

| | |
|---|---|
| Инициатор | [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Сразу после успешной саморегистрации ([EVT-1](EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)) либо успешного сброса пароля ([EVT-5](EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md)) — приложение само выполняет вход тем же email и (новым) паролем, без повторного ввода. `AuthBloc.on<AuthEventAuthAfterRegistration>` — отдельный обработчик от обычного входа ([EVT-2](EVT-2-USER-LOGGED-IN-IN-AUTH.md)), не переиспользует его код напрямую.

**Эффект.** Тот же сетевой путь, что у [EVT-2](EVT-2-USER-LOGGED-IN-IN-AUTH.md) (`AuthRepository.login`), но вызванный автоматически, не по прямому действию пользователя на экране логина. Если вызов падает с ошибкой, обработчик не оборачивает его в try/catch — экран зависает в состоянии загрузки вместо возврата к понятному сообщению.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc.on<AuthEventAuthAfterRegistration>`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.login`.
