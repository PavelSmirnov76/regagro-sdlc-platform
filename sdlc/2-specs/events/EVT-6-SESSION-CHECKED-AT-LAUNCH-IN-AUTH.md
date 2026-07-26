# EVT-6 — session.checked_at_launch

| | |
|---|---|
| Инициатор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Каждый холодный старт приложения, до какого-либо ввода пользователя; `AuthBloc.on<AuthEventStart>`.

**Эффект.** Если есть сеть — профиль пользователя обновляется с сервера; без сети используются только локальные данные. Если ранее ни разу не было выдано ни сессии, ни гостевого доступа — приложение автоматически предоставляет гостевой доступ (см. [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md), поле-флаг первого запуска), не показывая отдельного экрана выбора. Иначе пользователь остаётся в том состоянии (авторизован/гость), которое уже сохранено.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc.on<AuthEventStart>`; `lib/repositories/auth/auth_repository.dart` → `AuthRepository.init`, `loginWithoutAuthorization`.
