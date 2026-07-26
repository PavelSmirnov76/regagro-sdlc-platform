- **business task**: `BT-18` ([`../1-business-tasks/planning/BT-18-PLANNING-ANIMAL-REG-QR-VISUAL-TAG.md`](../1-business-tasks/planning/BT-18-PLANNING-ANIMAL-REG-QR-VISUAL-TAG.md), supersedes `BT-17`)
- **spec**: `UC-306` ([`../2-specs/use-cases/UC-306-ACTOR-5-EVT-24-ENT-5-CREATE_OK-IN-ANIMAL.md`](../2-specs/use-cases/UC-306-ACTOR-5-EVT-24-ENT-5-CREATE_OK-IN-ANIMAL.md), supersedes `UC-305` → `UC-52`), `ENT-5`, `ENT-6`
- **design**: нет `FIG-{n}` и не будет — по этому тикету дизайн-стадия не запускается ни по одному пункту (см. raw `SHEEP-4-clarifications.md`, «Общее»); визуальный вопрос закрыт переиспользованием готового `ScannerWidget`-паттерна
- **tracker**: нет подключённого трекера (Yandex Tracker MCP недоступен в этой сессии) — по `RUNBOOK.md` шаг 6, этот файл является записью учёта. Внешний тикет-источник — `SHEEP-4`, пункт чек-листа 1

# Добавить QR-считывание визуальной бирки на шаге «Маркирование»

## Объём

На шаге «Маркирование» (`IdentificationsStepPage`,
`lib/pages/animal_registration/step_pages/identifications_step_page.dart`)
добавить кнопку/иконку сканирования рядом с полем «Визуальная бирка» —
**иконка и логика запуска сканирования берутся из `ScannerWidget`**
(`lib/pages/weigh_animal/widgets/scanner_widget.dart`: иконка
`Assets.scanner`, ветвление «настройка устройства „камера как QR“ → либо
сразу `QRScanner.showInstant()`, либо сначала аппаратный
`ScannerService.startManualBarcodeScan()` с fallback на камеру»), а **не** из
`PassportQRScanner`/прямого вызова `QRScanner.showInstant()` без этой
логики — компонент должен быть профиль-нейтральным, без упоминаний
паспорта. Результат подставляется в `_birkController` тем же вызовом
(`widget.onNumberChanged`), каким сейчас заполняется поле с аппаратного
RFID-сканера (`_handleScanned`, :179-212).

Полное обоснование и CURRENT/TARGET-поведение — `UC-306`.

## Критерии приёмки (definition of done)

- [ ] На шаге «Маркирование» рядом с полем «Визуальная бирка» доступна кнопка/иконка сканирования (`Assets.scanner`, как в `ScannerWidget`).
- [ ] По нажатию воспроизводится логика `ScannerWidget.onPressed` (настройка «камера как QR» → аппаратный скан с fallback на камеру), не прямой вызов `QRScanner.showInstant()` в обход настройки устройства.
- [ ] После успешного сканирования считанное значение автоматически подставляется в поле визуальной бирки.
- [ ] В UI/коде новой кнопки нет упоминаний паспорта.
- [ ] Ручной ввод номера остаётся доступным без изменений.
- [ ] Повторное сканирование не создаёт вторую запись идентификации — перезаписывает то же поле.
- [ ] Не добавляется проверка формата/уникальности значения (сохраняется текущее отключённое состояние, `RINTAGLE-395`).
- [ ] Не добавляется отдельное сообщение об ошибке распознавания.
- [ ] Регрессия исключена: животное по-прежнему успешно появляется локально с отрицательным `id` (существующий тест группы `UC-306/53` проходит).

## Реализационные заметки

- Не форкать `QRScanner`/`PassportQRScanner` и не писать выбор источника скана заново — переиспользовать `ScannerWidget` целиком (если его API совместим с кастомной валидацией/`buildCounter`/фокус-роутингом поля бирки), либо вынести его `onPressed`-логику (`Assets.scanner`, `getSavedisUseCameraForQr()` → `startManualBarcodeScan()` → fallback `QRScanner.showInstant()` → `extractQrCode()`) в переиспользуемый метод/виджет и вызвать из существующего поля — не дублировать её копипастом.
- Подключать результат к `onNumberChanged(birkMarkerType, extractedNumber)`, где `birkMarkerType = _getBirkMarkerType()` — тот же путь, что у `_handleScanned` для аппаратного сканера.
- Тестовая группа `test/pages/animal_registration_bloc_test.dart` уже именуется `UC-306/53 — AnimalRegistrationEventSave — новое животное` (ссылка на `UC-306` уже добавлена в более раннем проходе; правило самопривязки теста к спеке, `use-cases/AGENTS.md`: `grep -r "UC-306" test/` должен находить тест). Новый функционал (кнопка сканирования) тестировать отдельным widget-тестом на `IdentificationsStepPage`.

## Зависимости

Нет блокирующих зависимостей — вся инфраструктура (`ScannerWidget`,
`QRScanner`, пакет `mobile_scanner`, `ScannerService`, `onNumberChanged`) уже
существует и используется в других экранах проекта. Дизайн-макета не будет —
см. `design` выше.
