# EVT-67 — animal_inventory.report_exported

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |
| Сущность(и) | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

**Триггер.** С экрана итогового отчёта
([EVT-66](EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)) кнопка
`share` в AppBar (видна только при непустых данных) → модальный
`_ExportBottomSheet` → выбор «Экспорт в Excel» либо «Экспорт в PDF».

**Эффект.** Формирует файл (пакет `excel` либо `pdf`/`printing`) с теми же 4
секциями, что и экран, плюс полная таблица животных места со статусом
(`Учтено`/`Потеряно`/`С другого объекта` — жёстко закодированные русские
строки, без `l10n`, см.
[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)), и передаёт
его в системный диалог «поделиться». Не изменяет ни одну запись
`InventoryScanReport` — чисто экспортное действие.

**Исходный код.** `lib/pages/animals_inventory/presentation/inventory_report_details_view.dart` →
`_generateAndShareExcel`, `_generateAndSharePdf`, `_ExportBottomSheet`, `_getStatusText`.
