# ENT-10 — Place

## Описание

Отделение (место содержания животных внутри фермы) — Drift-таблица `Places`.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id |
| `idRemote` | int? | серверный id |
| `farmId` | int | ссылка на [ENT-9](ENT-9-FARM-IN-FARM.md) (`Farm.remoteId`) |
| `name` | text | |
| `description` | text | используется и как «площадь» на экране создания структуры фермы |
| `needUpdate` | bool, default false | взведён при локальной правке уже синхронизированного места |
| `isDeleted` | bool, default false | **живой**, в отличие от [ENT-9](ENT-9-FARM-IN-FARM.md) — реально проставляется при удалении места |

## Связи

- [ENT-9](ENT-9-FARM-IN-FARM.md) (Farm) — многие-к-одному по `farmId`.

## Инварианты

- **Удаление места — единственная реально работающая «delete» операция в этом модуле**, в отличие от фермы. Для уже синхронизированного места (`idRemote != null`) удаление — это мягкое `isDeleted: true` + `needUpdate`-подобная пометка для sync-прохода; для ещё не синхронизированного — прямое физическое удаление локальной строки.
- Удаление разрешено только если на месте не осталось закреплённых животных — проверяется на клиенте перед вызовом удаления, не на сервере.
- При первой настройке структуры фермы предлагается стандартный набор мест (общее стадо, взрослые животные, молодняк, детская, карантин) — не хранится отдельно, это просто предзаполнение формы создания, а не отдельная сущность/статус.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository` | CURRENT | локальный CRUD + sync |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onDeletePlace` | CURRENT | мягкое/физическое удаление в зависимости от `idRemote` |
| `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart` | `PlaceCreateCubit._initializePlaces`, `removePlace` | CURRENT | стандартный набор мест при первой настройке, проверка «нет животных» перед удалением |
