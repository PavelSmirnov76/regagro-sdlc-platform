# ENT-12 — AnimalIdentification

## Описание

Идентификационная запись животного (транспондер, бирка и другие типы маркеров) — Drift-таблица `AnimalIdentifications`. Несколько записей на одно животное.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | |
| `animalId` | int | ссылка на [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) |
| `markerTypeId` | int? | тип маркера (транспондер/бирка/…), справочник — [HANDBOOKS](../modules/MOD-2-HANDBOOKS.md), не описан отдельной сущностью в этом проходе |
| `number` | text | номер маркера |
| `main` | bool | признак основного маркера — при регистрации транспондер всегда помечается основным, бирка — нет |
| `isActive` | bool | |
| `markerPlaceId`/`otherMarkerPlace` | int?/text? | место крепления маркера — справочник [ENT-8](ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (`KindMarkerPlaces`) |
| `markerDate` | DateTime? | влияет на валидацию (см. «Инварианты») |
| `identificationReasonId` | int? | |
| `complectNumber`/`description`/`clinic` | text? | |
| `errors` | text? | серверные ошибки по записи |
| `isEmission` | bool | |

## Связи

- [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — многие-к-одному по `animalId`.

## Инварианты

- **Только заполненные записи попадают в БД при регистрации** — идентификатор без введённого номера отбрасывается перед сохранением.
- **Валидация номера зависит от даты маркировки и типа маркера.** Для записей с `markerDate` до 1 марта 2024 года и определёнными «старыми» типами маркеров проверки минимальной/максимальной длины и формата номера не применяются — исторические послабления для уже промаркированных ранее животных.
- **Проверка на дублирующийся номер при регистрации** сравнивает введённый номер+тип маркера со снимком уже загруженных локальных животных на момент старта визарда, не с live-данными сервера.
- **`Animal.number`** (см. [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md)) заполняется из первого элемента списка идентификаций при сохранении — из-за порядка добавления на шаге маркировки это на практике номер бирки, а не транспондера, даже если пользователь воспринимает транспондер как основной идентификатор.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/animal_identification/animal_identifications.dart` | `AnimalIdentifications`, `AnimalIdentification` | CURRENT | таблица/модель |
| `lib/pages/animal_registration/step_pages/identifications_step_page.dart` | `IdentificationsStepPage` | CURRENT | шаг маркировки визарда регистрации |
| `lib/utilts/validator.dart` | `Validator.animalIdentificationLocalization` | CURRENT | валидация номера с учётом даты/типа маркера |
