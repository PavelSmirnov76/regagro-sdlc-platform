# ENT-8 — Misc directories (Unit, KindMarkerPlaces)

## Описание

Мелкие справочники, не заслуживающие каждый отдельной сущности — единицы измерения (`Unit`, для взвешивания и т.п.) и допустимые места крепления маркера/идентификации по видам (`KindMarkerPlaces`, используется на шаге маркировки при регистрации животного). Сгруппированы одной сущностью по тому же принципу, что и [ENT-1](ENT-1-USER-IN-AUTH.md) (Taxonomy) — общий справочный домен, нет самостоятельного сценария использования.

## Поля

- `Unit` (Drift `DataClass`, `packages/sheep_farm_database/lib/database/database.g.dart`) — `id`, `name`.
- `KindMarkerPlaces` (`packages/sheep_farm_database/lib/entities/kind_marker_places/kind_marker_places.dart`) — связка вида животного и допустимых мест крепления маркера.

## Связи

`Unit` читается модулем WEIGH; `KindMarkerPlaces` — модулем REG (шаг маркировки при регистрации). Оба будут специфицированы позже.

## Инварианты

Не редактируются локально — только синхронизация с сервера.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/database/database.g.dart` | `Unit` (Drift `DataClass`) | CURRENT | сгенерированная модель единиц измерения |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository` | CURRENT | синхронизация единиц измерения |
| `packages/sheep_farm_database/lib/entities/kind_marker_places/kind_marker_places.dart` | `KindMarkerPlaces` | CURRENT | таблица допустимых мест маркировки по виду |
| `lib/repositories/kind_marker_places/kind_marker_places_repository.dart` | `KindMarkerPlacesRepository` | CURRENT | синхронизация |
