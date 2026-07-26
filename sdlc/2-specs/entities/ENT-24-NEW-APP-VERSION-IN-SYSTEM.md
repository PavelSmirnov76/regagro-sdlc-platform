# ENT-24 — NewAppVersion

## Описание

Информация о доступной новой версии приложения (R70) — три представления в
одном файле `packages/sheep_farm_database/lib/entities/new_app_version/new_app_version.dart`,
персист только через Hive (нет Drift-таблицы):

- `NewAppVersion extends Equatable` — доменная модель.
- `NewAppVersionHive` (`@HiveType(typeId: 5)`) — форма для хранения в Hive.
- `NewAppVersionDTO` (`@JsonSerializable`) — сетевой DTO (используется только
  старым, уже удалённым Android/Regagro-путём — см. «Инварианты»).

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `number` | int | версия в числовом виде (`_versionStringToInt`) |
| `code` | String | версия строкой (`appInfo.version` из iTunes lookup) |
| `description` | String | описание/changelog (`releaseNotes`) |
| `immediate` | bool | «обязательное» обновление — единственный оставшийся источник (`checkNewVersionRintIos`) всегда передаёт `false`, см. «Инварианты» |
| `launchDate` | DateTime? | единственный оставшийся источник всегда передаёт `null` |
| `url` | String | ссылка в сторе (`trackViewUrl` из iTunes lookup) |
| `localPath` | String | путь к скачанному `.apk` — поле осталось от удалённого Android-пути скачивания, всегда пусто в живом коде |
| `isPlayMarket` | bool, default false | тоже остаток удалённого пути |

`isDownloaded` — `localPath.isNotEmpty` — вычисляется, но всегда `false` в
живом коде (`localPath` никогда не заполняется).

## Связи

Не связана ни с одной другой сущностью проекта.

## Инварианты

- **Единственный оставшийся источник проверки версии —
  `AppUpdateRepository.checkNewVersionRintIos`** — обращается к
  `https://itunes.apple.com/lookup` (Apple iTunes Lookup API) и вызывается
  **безусловно для любой платформы**, включая Android — на Android версия
  сборки фактически сравнивается с версией из iOS App Store, что лишено
  смысла. Коммит `f971f006` («remove deprecated constants. Remove
  Regagro», 2026-07-20) удалил: `checkNewVersion(fromApi:...)` (проверка
  через собственный бэкенд), `checkNewVersionRintAndroid` (парсинг HTML
  Google Play), события скачивания/установки `.apk`
  (`AppUpdateEventDownload`/`CancelDownload`/`Install`), зависимость от
  `AuthRepository.isDeveloper()`, импорт пакета `in_app_update`.
  `NewAppVersionDTO` (с реальным полем `immediate`/`launch_date` из
  бэкенда) остался в коде, но больше никем не создаётся — мёртвый класс.
- **«Обязательное» обновление (`immediate == true`) структурно
  недостижимо.** UI (`AppUpdatePage` — блокирующий `WillPopScope`,
  приоритетная иконка) полностью реализует сценарий принудительного
  обновления, но единственный источник данных всегда конструирует
  `immediate: false` — включить этот путь сейчас невозможно ни при каком
  реальном ответе сервера/стора.
- **`saveNewAppVersion` падает с `HiveError` при непустом `launchDate`.**
  `DateTime` не входит в базовые типы, сериализуемые `hive_ce` без
  адаптера; адаптер для поля `launchDate` не зарегистрирован. Сейчас
  недостижимо через реальный сценарий (единственный вызывающий код всегда
  передаёт `launchDate: null`), но сам метод репозитория содержит баг.
- **`AppUpdateBloc` работает только в prod-сборке** (`if (!Constants.isProd) return;`
  в начале обработчика — вне прод-сборки не эмитит вообще ничего).

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/new_app_version/new_app_version.dart` | `NewAppVersion`, `NewAppVersionHive`, `NewAppVersionDTO` | CURRENT (модель/Hive), мёртв (DTO, не создаётся) | три представления |
| `lib/repositories/app_update/app_update_repository.dart` | `AppUpdateRepository.checkNewVersionRintIos`, `saveNewAppVersion`, `getNewVersion`, `clear` | CURRENT | единственный живой источник проверки, локальное хранение |
| `lib/blocs/app_update/app_update_bloc.dart` | `AppUpdateBloc.on<AppUpdateEventCheckUpdate>` | CURRENT | оркестрация проверки |
| `lib/pages/app_update/app_update_page.dart` | `AppUpdatePage`, `_AppUpdatePageState` | CURRENT | блокирующий экран для `immediate == true` (структурно недостижимо) |
