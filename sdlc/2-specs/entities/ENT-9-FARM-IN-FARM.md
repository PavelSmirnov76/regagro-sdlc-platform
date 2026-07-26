# ENT-9 — Farm

## Описание

Ферма (юридическая площадка СХТП) — Drift-таблица `Farms`, локальная запись до первой синхронизации, затем зеркалирует серверную.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id |
| `remoteId` | int? | серверный id; `null`/отрицательный до первой успешной синхронизации |
| `name` | text | |
| `address`/`fullAddress` | text | |
| `latitude`/`longitude` | double | координаты, выбранные на карте |
| `needUpdate` | bool, default false | взведён при локальной правке уже синхронизированной фермы — сигнал для следующего sync-прохода |
| `isDeleted` | bool, default false | читается в списках (`isDeleted != true`); write-путь на это поле отсутствует в коде — функциональности удаления фермы нет |
| `guid` | text | клиентский идентификатор |
| `countryId`/`regionId`/`districtId`/`localityId`/`streetId`/`house`/`building`/`apartment` | id/text | адресный справочник, id-поля, сам справочник не в этом модуле |

## Связи

- [ENT-10](ENT-10-PLACE-IN-FARM.md) (Place) — одна ферма содержит несколько мест, `Places.farmId` ссылается на `Farm.remoteId`.

## Инварианты

- **`isDeleted` — мёртвое поле по факту использования.** Столбец существует и читается везде через фильтр `isDeleted != true`, но ни один путь в коде не пишет в него `true` — функциональность удаления фермы физически отсутствует (см. `SDLC-REWRITE-PLAN.md`, «Статус — чистка кода»: соответствующий код был найден и удалён в этом же проходе). Поле и read-фильтры оставлены, потому что они не мертвы сами по себе — на практике `getAllToDelete()`-подобный запрос просто всегда возвращает пустой список.
- Новая ферма получает отрицательный локальный `remoteId`, заменяемый на серверный при успешной синхронизации; замена каскадно обновляет связанные места и животных (см. будущую спеку ANIMAL).

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `Farms`, `Farm` | CURRENT | таблица/модель |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository` | CURRENT | локальный CRUD + sync |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc` | CURRENT | локальное создание/редактирование |
