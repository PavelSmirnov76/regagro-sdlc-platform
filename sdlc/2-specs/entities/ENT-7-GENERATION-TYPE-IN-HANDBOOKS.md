# ENT-7 — GenerationsType

## Описание

Справочник типов поколений животного (используется в разведении/родословной — REPRO, будет специфицирован позже) — включает цветовую маркировку поколения (`GenerationTypeColorPicker` extension). Синхронизируется инкрементально.

## Поля

Стандартный набор справочника: `id`, `name`, плюс вычисляемый цвет через extension-метод, не хранимое поле.

## Связи

Читается только модулем REPRO (по id) — не владеет сценарием разведения, только списком типов.

## Инварианты

Не редактируется локально — только синхронизация с сервера.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/generations_types/generations_types.dart` | `GenerationsTypes`, `GenerationsType`, `GenerationTypeColorPicker` | CURRENT | таблица/модель/цветовая маркировка |
| `lib/repositories/generations_types_repository/generations_types_repository.dart` | `GenerationsTypesRepository.getTypesFromApi` | CURRENT | синхронизация |
