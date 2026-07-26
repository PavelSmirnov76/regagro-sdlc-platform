# UC-211 — Просмотр посуточного отчёта по перемещениям успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-105](../events/EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) |
| Сущность | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Экран дневного отчёта по перемещениям для конкретных даты и пары мест
(отправления/назначения) — тот же экран, с которого доступно удаление
([EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md)). Ранее
отложенный пробел (часть `R26` из PRD) — закрыт этим же способом, что и
аналогичные посуточные отчёты VAC/WEIGH/DISP/INV.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — тот же, что для остальных
сценариев MOVE.

## CURRENT

### Основной поток

1. Экран открывается из календаря событий или из хаба неотправленных
   ([EVT-104](../events/EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md), с
   `isUnsent: true`) — `Routes.movementReport`, аргументы
   `MovementReportPageArgs { date, fromPlaceId, toPlaceId, fromPlaceName?,
   toPlaceName?, isUnsent = false }`.
2. `MovementReportView` создаёт `MovementReportCubit()..load(args)`.
3. `load(args)`: `emit(loading())`, `day = DateUtils.dateOnly(args.date)`,
   `all = await _movementRepo.getMovementsWithDetailsByFilters(sync: null)`
   (без фильтра по признаку отправки — берутся и отправленные, и
   неотправленные перемещения).
4. Фильтрует `all` в памяти: дата совпадает с `day` (`placeDate ?? createdAt`),
   `fromId == args.fromPlaceId`, `placeId == args.toPlaceId`.
5. Группирует совпавшие по возрастной группе/виду животного
   (`MovementAnimalGroup`), собирает транспондерные номера
   (`Constants.TransponderMarkerTypeId`) для карточек животных.
6. `emit(MovementReportState.loaded(date: ..., fromPlaceName: ...,
   toPlaceName: ..., totalAnimals: matching.length, groups: ...))`.
7. Рендер через общий `EventReportScaffold`/`EventReportBody`; при
   `isUnsent == true` доступна кнопка удаления через `MoreMenuWidget`.

### Альтернативные потоки

- **`toggleGroup(int index)`.** Синхронно переключает `isExpanded` у группы по
  индексу; no-op, если состояние ещё не `loaded` — не отдельный use-case,
  чисто UI-раскрытие уже загруженных данных.

### Связанные сущности

Нет дополнительных — сценарий целиком в рамках [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md).

### Бизнес-правила

- Фильтрация чтения использует `sync: null` (и отправленные, и
  неотправленные), тогда как удаление в этом же кубите (`deleteEvent`)
  использует `sync: false` — асимметрия между чтением отчёта и удалением: с
  экрана отчёта для уже отправленных перемещений видно, что они были, но
  удалить их с этого экрана нельзя (кнопка удаления зависит от `args.isUnsent`,
  проставляемого вызывающей стороной, а не пересчитывается по данным самого
  перемещения).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.load`, `toggleGroup` | CURRENT | загрузка и группировка отчёта |
| `lib/pages/movement_report/presentation/movement_report_page.dart` | `MovementReportPage` | CURRENT | экран |
| `lib/pages/movement_report/presentation/widgets/movement_report_view.dart` | `MovementReportView` | CURRENT | создаёт кубит, читает `args` |
| `lib/repositories/movement_report/movement_report_repository.dart` | `MovementReportRepository.getMovementsWithDetailsByFilters` | CURRENT | источник данных |

## Критерии приёмки

- Успех -> группирует по `kind`, учитывает только совпадающие по дате+
  from+to перемещения, `totalAnimals` = число совпавших.

## Связанные тесты

- `test/pages/movement_report_cubit_test.dart`, группа `'UC-211 —
  MovementReportCubit.load'` (ранее `'UC-309 — MovementReportCubit.load'` —
  число принадлежало старой, дорефакторинговой нумерации, переименована в
  рамках этого же прохода) — тест `'успех -> группирует по kind, считает
  только совпадающие по дате+from+to'`.

## Открытые вопросы и ограничения

Нет.
