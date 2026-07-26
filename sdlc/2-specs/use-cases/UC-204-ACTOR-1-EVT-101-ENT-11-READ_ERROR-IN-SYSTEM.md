# UC-204 — Открытие посуточного списка событий отказывает — как техническим сбоем загрузчика, так и подтверждённым багом агрегации регистрации

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же экран, что в [UC-203](UC-203-ACTOR-1-EVT-101-ENT-11-READ_OK-IN-SYSTEM.md) —
`ReportsDayListCubit.load`/`FarmDayListCubit.load` перехватывают исключение
общим `try/catch` и эмитят `error(message)`. Найдены и подтверждены тестом
**два независимых источника** отказа:

- (а) технический сбой `ReportsDayDataLoader.load(farmId:)` (любой из 7
  репозиториев внутри `Future.wait` бросает исключение);
- (б) **подтверждённый багом дефект агрегации** —
  `ReportsDayQuery.buildRegistrationItem` бросает `Exception('Created at is
  null')`, если **любое** животное фермы (не только из просматриваемых
  места/дня) имеет `createdAt == null` — ломая загрузку всего дня из-за
  полностью не относящейся к этому дню/месту записи.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — тот же, что в
[UC-203](UC-203-ACTOR-1-EVT-101-ENT-11-READ_OK-IN-SYSTEM.md).

## CURRENT

### Основной поток

1. `ReportsDayListCubit.load`/`FarmDayListCubit.load`: `emit(loading)` →
   `try { ... rawData = await _dataLoader.load(farmId:); ... } catch (e) {
   emit(error(e.toString())); }`.
2. Экран показывает состояние ошибки (текст исключения как есть,
   `e.toString()` — не локализованное сообщение, не структурированная
   ошибка).

### Альтернативные потоки

- **(а) Технический сбой `ReportsDayDataLoader`.** Любой из 7 репозиториев
  внутри `Future.wait` (движения/выбытия/инвентаризация/животные/
  вакцинации/причины выбытия и др. — см.
  [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)) бросает
  исключение — тот же загрузчик, что уже использует календарь
  ([UC-200](UC-200-ACTOR-1-EVT-99-ENT-11-READ_ERROR-IN-SYSTEM.md)), тот же
  класс отказа.
- **(б) Баг агрегации регистрации — подтверждён тестом.**
  `ReportsDayQuery.buildRegistrationItem` итерирует **все** животные фермы
  (`rawData.animals`, не отфильтрованные по месту/дню заранее) и для
  каждого читает `createdAt` — если хотя бы у одного из них это поле
  `null`, метод бросает `Exception('Created at is null')` **до** того, как
  успевает отфильтровать по фактическому месту/дню. Тест подтверждает это
  буквально: животное с `placeId: 500`, `createdAt: null`, при просмотре
  дня для `place: idRemote: 10` (другое место) — загрузка всего дня всё
  равно проваливается с этим исключением. Единственная строка `catch`
  общая для веток (а) и (б) — пользователь не может отличить «сеть/БД
  недоступны» от «где-то на этой ферме есть животное без даты регистрации,
  вообще не относящееся к просматриваемому месту/дню».

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — поле
  `createdAt`/дата регистрации; баг (б) читает это поле у ВСЕХ животных
  фермы, не только у тех, что относятся к текущему месту/дню.

### Бизнес-правила

- `error(message)` — единственное состояние отказа, без разделения на
  типы ошибок; сообщение — сырой `e.toString()`.
- Баг (б) — единственный найденный в этой под-области случай, когда
  ПОЛНОСТЬЮ НЕ ОТНОСЯЩЕЕСЯ к просматриваемому месту/дню животное ломает
  загрузку всего экрана.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — оба сценария воспроизводятся
статическим чтением кода и подтверждены существующими тестами.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/reports_day_list/cubit/reports_day_list_cubit.dart` | `ReportsDayListCubit.load` (catch) | CURRENT | общий catch для обеих веток, уровень места |
| `lib/pages/reports_day_list/cubit/farm_day_list_cubit.dart` | `FarmDayListCubit.load` (catch) | CURRENT | общий catch, уровень фермы |
| `lib/pages/reports_day_list/data/reports_day_query.dart` | `ReportsDayQuery.buildRegistrationItem` | CURRENT | источник бага (б) — бросает на `createdAt == null` у любого животного фермы |
| `lib/pages/reports_day_list/data/reports_day_data_loader.dart` | `ReportsDayDataLoader.load` | CURRENT | источник ветки (а) |

## Критерии приёмки

- Исключение из `ReportsDayDataLoader.load` -> `error(e.toString())`.
- Наличие на ферме хотя бы одного животного с `createdAt == null` ->
  `error('Created at is null'-содержащее сообщение)`, независимо от того,
  относится ли это животное к просматриваемым месту/дню.

## Связанные тесты

- `test/pages/reports_day_list_cubit_test.dart`, группа `'UC-204 —
  ReportsDayListCubit.load ERROR'` (ранее `UC-304`, переименована в рамках
  этого же прохода) — тест `'dataLoader бросает -> error с текстом
  исключения'` (ветка а) и тест `'BUG: животное фермы без даты регистрации
  ломает загрузку дня, даже если оно не относится ни к месту, ни к дню'`
  (ветка б, багу присвоено явное описание "BUG" в самом тесте).
- `test/pages/farm_day_list_cubit_test.dart`, группа `'UC-204 —
  FarmDayListCubit.load ERROR'` (ранее `UC-302`, переименована в рамках
  этого же прохода) — та же ветка (а) для уровня фермы.

## Открытые вопросы и ограничения

- Не проверено, воспроизводится ли баг (б) также и в `FarmDayListCubit`
  (тот же `ReportsDayQuery`, но `FarmDayListCubit` не строит элемент
  регистрации напрямую через `buildRegistrationItem` в своём коде — см.
  `entriesForPlace`, требует отдельной проверки, не проводилась в рамках
  этого документа).
