# ENT-1 — User

## Описание

Учётная запись владельца-аккаунта. Владеющий модуль: [MOD-1](../modules/MOD-1-AUTH.md). Три представления в одном файле `packages/sheep_farm_database/lib/entities/user/user.dart` — нет отдельной Drift-таблицы, это чистый application-level домен, персистентный только через Hive (см. [ENT-2](ENT-2-SESSION-IN-AUTH.md)).

- `User extends Equatable` — доменная модель.
- `UserHive` (`@HiveType`) — форма для хранения в Hive, конвертер `toUser()`.
- `UserDTO` (`@JsonSerializable`) — сетевой DTO, конвертеры `toUserHive()`/`toUser()`.

## Поля

| Поле | Тип | Nullable | Комментарий |
|---|---|---|---|
| `id` | int | нет | Серверный id |
| `name` | text | нет | |
| `email` | text | нет | Логин для входа/сброса пароля |
| `createdAt`/`updatedAt` | text | нет | Серверные метки времени, хранятся строкой |
| `firstName`/`lastName`/`patronymic` | text | да | `lastName` маппится из JSON-ключа `second_name` — расхождение имён между сетевым контрактом и доменной моделью |
| `organizationId` | int | да | |
| `phone`/`phoneNumberCode`/`phoneCountryIsoCode` | text | да | |
| `locale` | text | нет, default `'ru'` (`User.defaultLocale`) | |
| `organization` | `Organization?` | да | |
| `permissions` | `List<Permission>` | нет, default `[]` | Приходит с сервера, но не используется ни для каких решений в клиентском коде — см. «Инварианты» |
| `roles` | `List<Role>` | нет, default `[]` | Тоже приходит с сервера, тоже не используется |
| `countryId` | int | да | |

В том же файле определены `Veterinarian extends User` и `VeterinarianDto extends UserDTO` — специализация, не часть основного потока AUTH, не описывается здесь.

## Связи

- [ENT-2](ENT-2-SESSION-IN-AUTH.md) (Session) — один-к-одному, хранится вместе как часть авторизованной сессии, отдельным ключом в том же Hive-боксе. `isAuthorized()` проверяет только главный токен — `User` в гейтинге не участвует.

## Инварианты

- **`roles`/`permissions` — приходят с сервера, но подтверждённо не используются ни для одного решения в клиентском коде.** Именованные id-константы прав (`Permission`) не встречаются ни в одном вызывающем месте вне собственного файла модели.
- **JSON-ключ `second_name` ≠ имя поля `lastName`.** Любой код, читающий сырой ответ сервера напрямую (не через `UserDTO`), рискует перепутать порядок с `firstName`/`patronymic`.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `User` | CURRENT | доменная модель |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `UserHive` | CURRENT | Hive-персистентная форма |
| `packages/sheep_farm_database/lib/entities/user/user.dart` | `UserDTO` | CURRENT | сетевой DTO + конвертеры |
| `packages/sheep_farm_database/lib/entities/user/permission.dart` | `Permission` | CURRENT (данные), мёртв (потребление) | именованные id-константы прав, не используются в UI |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUser` | CURRENT | сохранение правки пользователя на сервере |
