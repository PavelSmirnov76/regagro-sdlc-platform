# ENT-21 — ProfileSettings

## Описание

Настройки уведомлений о вакцинации — сколько дней предупреждать и включена
ли отправка на email (R64). Drift-таблица `ProfileSettings`
(`packages/sheep_farm_database/lib/entities/profile_settings/profile_settings.dart`),
**одна строка на пользователя в физическом смысле не гарантируется типом** —
репозиторий всегда работает с таблицей как с единственной строкой
(`clearAndInsertAll`).

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | |
| `userId` | int? | объявлено в схеме, но не используется нигде в коде кроме объявления колонки — не читается, не пишется ни одним репозиторием |
| `daysToVaccination` | int? | за сколько дней до вакцинации предупреждать; дефолт при отсутствии — `7` (жёстко в `NotificationsSettingsCubit.load()`) |
| `sendVaccinationNotificationOnEmail` | bool, default `true` | |

Отдельный сетевой DTO — `SettingsMap`/`Settings`
(`packages/sheep_farm_database/lib/entities/settings/settings.dart`,
`@JsonSerializable`), не связанный с `ProfileSettings` общим
Drift-конвертером:
```dart
{ visibleKinds: List<int>? ("visible_kinds"), daysToVaccination: int? ("days_to_vaccination"),
  sendVaccinationNotificationOnEmail: bool? ("send_vaccination_report_on_email") }
```
Обратите внимание — JSON-ключ `send_vaccination_report_on_email` содержит
слово «report», тогда как и Dart-поле, и колонка Drift называются
«notification» — расхождение имени контракта, не влияющее на
работоспособность (маппинг явный через `@JsonKey`), но требующее внимания
при будущих изменениях контракта.

`visibleKinds` в том же сетевом DTO относится к R65 (см.
[ENT-3](ENT-3-TAXONOMY-IN-HANDBOOKS.md)), не к этой таблице — оба
R64/R65-факта передаются на сервер **одним и тем же** запросом
(`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`).

## Связи

- Не имеет FK на [ENT-1](ENT-1-USER-IN-AUTH.md) (User) на уровне БД —
  `userId` объявлен, но мёртв.
- Синхронизируется тем же сетевым вызовом, что и видимость видов
  ([ENT-3](ENT-3-TAXONOMY-IN-HANDBOOKS.md), HANDBOOKS) — один
  `user-settings/store`/`user-settings/get-settings` эндпоинт на оба факта.

## Инварианты

- **`@Clearable()`** — при логауте (`DataUpdateClear` → `clearUserData()`)
  сбрасывается; в отличие от [ENT-22](ENT-22-DEVICE-IN-PROFILE.md) (не
  `@Clearable`) и `Kind.visible` (не `@Clearable`) — асимметрия в скоупе
  данных между тремя настройками этого модуля: уведомления — per-account,
  устройства/видимость видов — per-device, переживают смену аккаунта на том
  же устройстве.
- **Локальные правки могут быть молча перезаписаны сервером.** Push
  (`SettingsRepository.setSettingToSHTP()`, отправляет и эту таблицу, и
  текущий список видимых `Kind`) вызывается в `DataUpdateBloc._syncAllData`
  только если `event is DataUpdateStartAll && event.isUpdateData == true` —
  единственное место в кодовой базе, передающее `isUpdateData: true`, —
  кнопка ручного обновления на экране «В работе». Pull
  (`getSettingFromSHTP()`, перезаписывает и эту таблицу, и `Kind.visible`
  содержимым с сервера) вызывается **безусловно**, на каждый
  `_syncAllData`. Практическое следствие: пользователь меняет настройки →
  сохраняет локально → любой ДРУГОЙ триггер `DataUpdateStartAll` без
  `isUpdateData` (логин, ретрай на экране обновления, ресинк после смены
  языка) перетирает несинхронизированные локальные изменения старыми
  серверными без предупреждения.
- **Единственная строка таблицы полностью перезаписывается на каждое
  сохранение** (`SettingsRepository.saveProfileSettings` →
  `dao.clearAndInsertAll([...])`) — не upsert по `userId`/`id`.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings.dart` | `ProfileSettings` | CURRENT | таблица |
| `packages/sheep_farm_database/lib/entities/settings/settings.dart` | `Settings`, `SettingsMap` | CURRENT | сетевой DTO, объединяет R64+R65 в одном контракте |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.getProfileSettings`, `saveProfileSettings`, `setSettingToSHTP`, `getSettingFromSHTP` | CURRENT | локальный CRUD + push/pull |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit` | CURRENT | экран настроек уведомлений |
