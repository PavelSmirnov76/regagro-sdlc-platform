# ENT-3 — Taxonomy (Kind / Breed / Suit / BreedSuit)

## Описание

Таксономия животных: вид (`Kind`), порода (`Breed`), масть (`Suit`), и связка порода-масть (`BreedSuit`, какие масти допустимы для какой породы). Четыре отдельные Drift-таблицы, объединённые здесь одной сущностью, потому что они образуют один справочный домен и всегда читаются вместе при построении списков выбора.

- `Kinds` (`packages/sheep_farm_database/lib/entities/kind/kinds.dart`) — `id`, `name`, `animalTypeId`, `visible` (флаг видимости вида в списках выбора — см. «Инварианты»).
- `Breeds` (`packages/sheep_farm_database/lib/entities/breed/breeds.dart`) — порода, ссылается на `Kind` по `kindId`.
- `Suits` (`packages/sheep_farm_database/lib/entities/suit/suits.dart`) — масть.
- `BreedSuits` (`packages/sheep_farm_database/lib/entities/breed/breed_suits.dart`) — связка допустимых пар порода-масть.

## Поля

| Поле | Таблица | Nullable | Комментарий |
|---|---|---|---|
| `id` | все четыре | нет | autoincrement |
| `name` | все четыре | нет | |
| `animalTypeId` | `Kinds` | да | |
| `visible` | `Kinds` | нет, default `true` | видимость вида в списках выбора приложения |
| `kindId` | `Breeds` | — | связь с `Kind` |

## Связи

- `Kind` → `Breed` (один-ко-многим, по `kindId`).
- `Breed`/`Suit` → `BreedSuit` (многие-ко-многим через связочную таблицу).

## Инварианты

- **`Kind.visible`** — единственное поле этой сущности, которым управляет пользователь напрямую (настройка видимости видов животных в приложении, потребляется другими модулями — REG при выборе вида, PROFILE при настройке видимости). Сама таксономия (список видов/пород/мастей и их связи) синхронизируется с сервера целиком, локально не редактируется.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/kind/kinds.dart` | `Kinds`, `Kind`, `KindsDto` | CURRENT | таблица/модель/DTO вида |
| `packages/sheep_farm_database/lib/entities/breed/breeds.dart` | `Breeds`, `Breed` | CURRENT | таблица/модель породы |
| `packages/sheep_farm_database/lib/entities/suit/suits.dart` | `Suits`, `Suit` | CURRENT | таблица/модель масти |
| `packages/sheep_farm_database/lib/entities/breed/breed_suits.dart` | `BreedSuits`, `BreedSuit` | CURRENT | связка порода-масть |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository` | CURRENT | синхронизация видов |
| `lib/repositories/breed/breeds_repository.dart` | `BreedsRepository` | CURRENT | синхронизация пород |
| `lib/repositories/suit/suits_repository.dart` | `SuitsRepository` | CURRENT | синхронизация мастей |
| `lib/repositories/breed_suit/breed_suits_repository.dart` | `BreedSuitsRepository` | CURRENT | синхронизация связки |
