# ACTOR-3 — Приложение (автоматическая проверка сессии)

## Идентичность

Не человек — само приложение, действующее автоматически при каждом холодном старте, до какого-либо ввода пользователя. Отличается от [ACTOR-1](ACTOR-1-USER-IN-AUTH.md)/[ACTOR-2](ACTOR-2-GUEST-IN-AUTH.md) тем, что инициирует событие без явного человеческого жеста, и от системного sync-актора (заводится позже, при специфицировании модуля с sync-очередью) тем, что это не sync-проход, а разовая проверка при запуске — разные триггеры, разные акторы (`../events/AGENTS.md`, «Exactly one initiator per event»).

Также инициирует автоматическую потерю сессии: если стрим авторизации сигнализирует `false` не в ответ на явный logout пользователя (например токен стал недействителен), приложение само выполняет «мягкий» выход, не спрашивая пользователя.

## Цели

Определить, куда направить пользователя при старте: восстановить существующую сессию, продолжить как гость, либо (при полном отсутствии и сессии, и признака «уже был гостем») автоматически выдать гостевой доступ.

## Действия

Инициирует [EVT-6](../events/EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md) (сессия проверена при запуске) и [EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) (сессия аннулирована автоматически, не по явному действию пользователя) через `AuthBloc.on<AuthEventStart>` и подписку на `AuthRepository.getAuthStream()`.

**BOARD:** инициирует [EVT-79](../events/EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md)
(реактивная проверка доступности раздела BOARD по стране пользователя —
запускается автоматически при смене пользователя/гостевой страны/после
синхронизации справочника стран, не по явному действию пользователя) через
`BoardChatAvailabilityCubit`.

**SYSTEM (последний модуль в очереди):** инициирует [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)
(автоматический запуск полного sync-прохода сразу после `AuthEventStart`,
для гостя и авторизованного одинаково — не по явному действию пользователя)
и [EVT-100](../events/EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) (проверка
обновления приложения, автоматически сразу после успешного завершения
sync-прохода) через `MainPage`'s `BlocListener<AuthBloc>`/`AppUpdateBloc`.

Взаимодействует с сущностями [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (TokenData), [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS — читается, не редактируется), [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate), [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) (NewAppVersion).

## Ограничения

Обновление профиля пользователя с сервера при старте выполняется только если есть сеть; без сети используются исключительно локально сохранённые данные.

## Исходный код

| Файл | Класс/метод | Роль |
|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventStart>` | проверка сессии при старте |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.init`, `getAuthStream`, `loginWithoutAuthorization` | восстановление данных, стрим потери авторизации, автовыдача гостевого доступа |
