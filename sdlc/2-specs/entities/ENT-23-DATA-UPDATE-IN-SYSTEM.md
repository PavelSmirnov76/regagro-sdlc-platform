# ENT-23 — DataUpdate

## Описание

Журнал полного sync-прохода — Drift-таблица `DataUpdates`
(`packages/sheep_farm_database/lib/entities/data_update/data_updates.dart`).
Фиксирует факт успешного или неудавшегося обновления по «категории»
данных. Полностью очищается в начале каждого полного прохода
(`_syncAllData()` → `_clearDataUpdates()`) — не накопительный лог истории,
а снимок текущего прохода.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | |
| `updatedAt` | DateTime? | дата успешного обновления категории |
| `serviceAreaId` | int? | «на данный момент не используется» (комментарий в коде) — мёртвое поле |
| `dataCategoryId` | `DataCategory` (int enum) | см. ниже |
| `errorDataKey` | text? | ключ данных, на которых случилась ошибка |
| `errorMessage` | text? | полный текст ошибки |

`isError` (расширение) — `errorDataKey != null || errorMessage != null`.

`DataCategory` — 9 значений (порядок фиксирован, «добавлять перечисления
можно только с конца»): `directories, animals, user, reports, syncReports,
syncUnsentAnimals, syncDisposalListService, generations, generationsTypes`.
Doc-комментарии enum'а перечисляют таблицы старой схемы (`AddressTypes`,
`DisposalStatuses`, `EnterpriseAddresses`, `KindGroups`, `LegalForms` и
т.д.) — они не соответствуют актуальным таблицам HANDBOOKS (`Kinds`,
`Breeds`, `Suits`, `DisposalReasons` и т.д.) — устаревшая документация
внутри самого файла, не влияющая на поведение.

## Связи

Не ссылается ни на одну другую сущность по FK — это независимый лог,
читаемый и писаный только оркестрацией `DataUpdateBloc`.

## Инварианты

- **`@Clearable()`** — стирается при логауте вместе с остальными
  пользовательскими таблицами.
- **Пишется только двумя методами**: `_addDataUpdateSuccess(category)`
  (без ошибки) — вызывается из `loadUser`, `loadAnimals`, `loadShtp`,
  `loadDirectories`; `_addDataUpdateError(category, key, message)` —
  вызывается только из верхнеуровневого `catch` `on<DataUpdateStartAll>`.
- **Категория `directories` фактически никогда не записывается.**
  `loadDirectories()` инициализирует внутреннее поле категории значением
  `DataCategory.directories`, но по ходу метода переставляет его на
  `DataCategory.generationsTypes` (последнее явное присвоение внутри
  метода) и не возвращает обратно — финальная запись успеха уходит под
  категорией `generationsTypes`, не `directories`. Категория `directories`
  из 9 значений enum'а нигде фактически не встречается в самой таблице.
- **За один реальный проход в таблицу попадает не более 3-4 успешных
  строк** (`user`, `animals`, `reports`, ошибочно-`generationsTypes` вместо
  `directories`) — категории `syncReports`, `syncUnsentAnimals`,
  `syncDisposalListService`, `generations` никогда не фиксируются как
  успешные отдельными строками.
- **Решающая роль в `updateAndSyncRegagro`**: сравнение
  `dataUpdates.length < DataCategory.values.length` (9) используется как
  признак «проход был неполным/прерванным, нужно сделать полный
  `_syncAllData()`». Поскольку реально в таблице никогда не набирается 9
  строк (см. выше), это условие **истинно всегда**, независимо от
  `event.again` — альтернативная ветка (`event.fullUpdate`) фактически
  недостижима (усугубляется тем, что ни один из 5 мест диспатча
  `DataUpdateStartAll` не передаёт `fullUpdate: true`). Задуманное
  разделение «докат прерванного прохода» vs «полная перезагрузка» не
  работает — каждый авторизованный проход выполняет полный `_syncAllData()`.
- **`errorDataUpdates.isNotEmpty` добавляет фиксированную задержку 15
  секунд** перед повтором — поскольку журнал чистится в начале каждого
  `_syncAllData()`, ошибка «переживает» ровно один следующий проход.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/data_update/data_updates.dart` | `DataUpdates`, `DataCategory`, `DataKey`, `DataUpdateExtension.isError` | CURRENT | таблица, категории, ключи, вычисляемый признак ошибки |
| `lib/repositories/data_update/data_updates_repository.dart` | `DataUpdatesRepository` | CURRENT | тонкая обёртка над `BaseRepository` — `getAll`/`insert`/`clear`/`getById` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._addDataUpdateSuccess`, `_addDataUpdateError`, `_clearDataUpdates`, `updateAndSyncRegagro`, `loadDirectories` | CURRENT | вся запись/чтение журнала, ошибка категории `directories` |
