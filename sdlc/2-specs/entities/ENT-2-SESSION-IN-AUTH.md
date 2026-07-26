# ENT-2 — Session

## Описание

Текущая сессия авторизации — главный токен, список серверных интеграций и запомненный логин. Владеющий модуль: [MOD-1](../modules/MOD-1-AUTH.md). Не единый класс в коде — совокупность ключей трёх Hive-боксов, читаемых/записываемых через `AuthRepository`:

- `AUTH_BOX` — основной бокс сессии, ключи для главного токена, серверных интеграций, `User` ([ENT-1](ENT-1-USER-IN-AUTH.md)).
- `LOGIN_BOX` — запомненный последний логин (переживает logout).
- `DEVELOPER_BOX` — флаг режима разработчика, не часть пользовательской сессии.

Главный токен — типизированный класс-обёртка `TokenData` (`packages/sheep_farm_database/lib/entities/token_data/token_data.dart`, Hive-форма `TokenDataHive`, DTO `TokenDataDTO`).

## Поля

| Поле | Тип | Хранилище | Комментарий |
|---|---|---|---|
| `mainToken` | `TokenData?` | `AUTH_BOX` | Единственное поле, гейтящее `AuthRepository.isAuthorized()` |
| `user` | `User?` ([ENT-1](ENT-1-USER-IN-AUTH.md)) | `AUTH_BOX` | |
| `serverIntegrations` | `List<{link: String}>` | `AUTH_BOX` | Везде, где пишется, записывается как пустой список — ничего в коде его не читает |
| `lastLogin` | text | `LOGIN_BOX` | Переживает `logout()` |
| `guestCountryCode` | text? | `SharedPreferences` (не Hive) | Единственное поле, которое гость может сохранить о себе до входа — переиспользуется позже как подсказка |

`TokenData`: `tokenType`, `expiresIn`, `accessToken`, `refreshToken`, `error`, `errorDescription`, `message`; вычисляемые `bearerToken`, `isSuccess => accessToken != null`.

## Связи

- [ENT-1](ENT-1-USER-IN-AUTH.md) (User) — один-к-одному, `user`-поле хранится в том же боксе, читается/пишется вместе с токеном.

## Инварианты

- **`isAuthorized()` — единственное условие: валидный главный токен.** `AuthRepository.isAuthorized() => getMainTokenData() != null`.
- **Два независимых флага «авторизован», синхронизируемых вручную, не один.** `AuthRepository.isAuthorized()` (живая проверка по Hive-токену) и отдельный кэшированный `SharedPreferences`-флаг в `AppCacheService` синхронизируются только явными вызовами в нескольких местах (`login()`, старт приложения, `logout()`). Часть UI-кода читает кэшированный флаг, часть — живую проверку репозитория; ничто не гарантирует, что оба значения совпадают в любой конкретный момент.
- **`logout()` стирает весь `AUTH_BOX` целиком, не по ключам** — главный токен, `User`, серверные интеграции пропадают одновременно; `LOGIN_BOX`/`DEVELOPER_BOX` не трогаются.
- **Дефект: retry/refresh на 401/419 не реализован в HTTP-слое.** `AuthInterceptor.onError` детектирует истёкшую/невалидную авторизацию, помечает запрос флагом «повторный», но всегда пропускает ошибку дальше — не переиздаёт запрос и не обновляет токен ни при каком условии.
- **Гостевой доступ не пишет ни одного токена** — только пустые серверные интеграции и явный флаг «не авторизован». Сессия остаётся неавторизованной до первого настоящего входа.
- **`AppCacheService` хранит ещё один флаг рядом с сессией — «направление интеграции», всегда с фиксированным значением.** Метод, который его сохраняет, безусловно пишет одно и то же значение независимо от входных данных — на сегодня не влияет ни на одно ветвление в коде за пределами собственной проверки «уже сохранено ли значение хоть раз» при первом холодном старте (см. [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)). Похоже на неиспользуемый остаток более ранней архитектуры — кандидат на отдельную проверку и, вероятно, удаление вне рамок этого прохода спецификации.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository` | CURRENT | вся логика чтения/записи сессии |
| `packages/sheep_farm_database/lib/entities/token_data/token_data.dart` | `TokenData`/`TokenDataHive`/`TokenDataDTO` | CURRENT | типизированная обёртка главного токена |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized`/`setAuthorizedFlag` | CURRENT | кэшированный дубликат авторизационного флага |
| `lib/network/auth_interceptor.dart` | `AuthInterceptor.onError` | CURRENT | детекция 401/419 без retry/refresh |
| `lib/data/services/app_cache_service.dart` | `getGuestCountryCode`/`saveGuestCountryCode` | CURRENT | гостевой контекст, переиспользуется позже |
