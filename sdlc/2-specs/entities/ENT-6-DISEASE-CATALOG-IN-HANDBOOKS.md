# ENT-6 — DiseasesKind (каталог болезней/вакцин по видам)

## Описание

Связка «болезнь/вакцина — вид животного», к которому она применима (`DiseasesKinds`) — определяет, какие вакцины доступны к выбору при записи вакцинации для конкретного вида животного. Синхронизируется инкрементально.

## Поля

Связочная сущность: `diseaseId`/`vaccineId`, `kindId` — стандартный набор, см. `packages/sheep_farm_database/lib/entities/vaccination/diseases/diseases_kinds.dart`.

## Связи

Читается модулем VAC (будет специфицирован позже) при построении списка доступных вакцин для вида животного; ссылается на [ENT-3](ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy, `Kind`) по `kindId`.

## Инварианты

Не редактируется локально — только синхронизация с сервера.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/vaccination/diseases/diseases_kinds.dart` | `DiseasesKinds`, `DiseasesKind` | CURRENT | таблица/модель связки болезнь/вакцина-вид |
| `lib/repositories/vaccination/diseases_kinds_repositiory.dart` | `DiseasesKindsRepository` | CURRENT | чтение/синхронизация связки |
