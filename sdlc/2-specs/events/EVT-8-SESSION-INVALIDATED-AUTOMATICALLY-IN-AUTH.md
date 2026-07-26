# EVT-8 — session.invalidated_automatically

| | |
|---|---|
| Инициатор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Модуль | [MOD-1](../modules/MOD-1-AUTH.md) |
| Сущность(и) | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |

**Триггер.** Стрим состояния авторизации сигнализирует потерю сессии не в ответ на явный [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md) (например токен стал недействителен) — приложение реагирует само, без действия пользователя.

**Эффект.** «Мягкий» выход — в отличие от [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md), повторный вызов очистки Hive-бокса не выполняется (сессия уже не считается валидной). Отдельное событие от [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md): инициатор другой (приложение, не пользователь), хотя итоговое состояние (нет сессии) то же самое.

**Исходный код.** `lib/pages/profile/bloc/auth_bloc.dart` → `AuthBloc` (подписка на `AuthRepository.getAuthStream()` в конструкторе); `lib/repositories/auth/auth_repository.dart` → `AuthRepository.getAuthStream`.
