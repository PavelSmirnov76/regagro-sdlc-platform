# ENT-17 — InventoryScanReport

## Описание

Одна отсканированная RFID/UHF-метка в рамках одной сессии инвентаризации
места содержания. Нет отдельной специализированной Drift-таблицы —
физически хранится в двух общих таблицах, разделяемых с недостижимыми из UI
типами «выход»/«вход» (`way_type` = `output`/`input`, см. «Инварианты»):

- `UnsentReportAnimals` — черновик сессии (пишется на каждый скан) → «готово
  к отправке» (после «Завершить» или выхода из режима правки).
- `ReportAnimals` — локальный кэш-читалка отчётов, уже подтверждённых
  сервером (перезагружается заново при каждом pull, окно «последний год»).

Строка в одной таблице не превращается в строку другой каким-либо
`id`-присвоением — при push исходные строки `UnsentReportAnimals` удаляются
целиком, а `ReportAnimals` заполняется отдельным, независимым pull-запросом.
«Одна и та же» метка до и после полного sync-прохода — это две физически
разные строки в разных таблицах, связанные только совпадением
`transponderId`/`sessionUuid`/`time`, не общим `id`.

## Поля

### `UnsentReportAnimals` (черновик / готово к отправке)

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id |
| `transponderId` | text | номер метки как есть, без нормализации в БД (нормализация до 15 символов происходит раньше, в `ScannerService`/`ScanningBloc`) |
| `type` | text (`way_type`) | `'inventory'` на любом реально достижимом пути; `'output'`/`'input'` пишутся только тестами, см. «Инварианты» |
| `time` | DateTime (`way_date`) | время скана; при `Save` все строки сессии нормализуются к минимальному времени сессии |
| `farmId` | int? | ферма места сканирования |
| `placeId` | int? | место сканирования |
| `readyToSend` | bool, default false (`ready_to_send`) | `false` — черновик (ещё сканируется/редактируется), `true` — сессия завершена, ждёт push |
| `sessionUuid` | text? | группирует строки одной сессии; появилось поздно в истории схемы (v87 из 97) — легаси-строки без него существуют только как тестовые фикстуры, не в реальных данных не старше этой миграции |

### `ReportAnimals` (кэш отчётов, подтверждённых сервером)

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id (не связан с `UnsentReportAnimals.id` той же метки) |
| `transponderId` | text | номер метки |
| `regagroId` | int? (`regagro_id`) | id животного, резолвленный **сервером** при приёме; не заполняется локально при записи со скана |
| `type` | text (`way_type`) | те же значения, что у `UnsentReportAnimals.type` |
| `time` | DateTime (`way_date`) | |
| `farmId` | int? | |
| `placeId` | int? | |
| `sessionUuid` | text? (`uuid`) | появилось на v88 из 97, на миграцию позже поля черновика |

## Связи

- [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — **нет FK на уровне БД**.
  Сопоставление метка↔животное всегда вычисляется на клиенте, в момент
  отображения, через [ENT-12](ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (`AnimalIdentification`, поиск по `markerTypeId == Constants.TransponderMarkerTypeId`
  совпадающей строкой с `transponderId`) — не хранится как ссылка ни в одной
  из двух таблиц этой сущности. При push на сервер `animal_id` резолвится
  клиентом на лету для payload'а, но **не сохраняется** обратно в
  `UnsentReportAnimals`; `ReportAnimals.regagroId` заполняется только из
  ответа сервера при следующем pull.
- [ENT-10](ENT-10-PLACE-IN-FARM.md) (Place, FARM) — `placeId`, место, в
  котором проводится инвентаризация; не изменяется этой под-областью.
- [ENT-9](ENT-9-FARM-IN-FARM.md) (Farm, FARM) — `farmId`, не изменяется этой
  под-областью.

## Инварианты

- **Разделяемые таблицы с недостижимым легаси-типом.** Обе таблицы
  спроектированы на несколько значений `way_type` («инвентаризация»,
  «выход», «вход» — экран-проход через ворота), но `ScanningPageArgs`
  (`lib/pages/scanning/scanning_page.dart`) имеет единственный конструктор —
  `.inventory(...)`, который всегда создаёт `type: 'inventory'`; ни в одном
  месте `lib/` не создаётся тип `'output'`/`'input'` вне тестов. Согласуется
  с тем, что `ScannerOperation.values` в настройках устройств
  (`packages/sheep_farm_database/lib/entities/devices/devices.dart`)
  содержит только `inventory` — переключатель операции «проход» скрыт из
  UI. Ветка кода `ScanningBloc`, обслуживающая нелегаси (не-uuid) сессии без
  `sessionUuid`, живёт только в тестах.
- **Черновик персистится на каждый скан, не только при завершении.**
  `ScanningBloc.on<ScanningEventAddAnimal>` дедуплицирует по
  `transponderId` (обновляет время существующей строки вместо дублирования)
  и сразу же переписывает весь черновик сессии в БД
  (`UnsentReportAnimalsRepository.replaceDraftSession`/`replaceDraftSessionByUuid` —
  полное удаление строк сессии и вставка заново, не точечный upsert).
- **Смена места посреди новой (не-edit) сессии инвентаризации обнуляет
  накопленные сканы и заводит новый `sessionUuid`** — `ScanningBloc.on<ScanningEventChangePlace>`,
  ветка `_isInventory && !isEditMode`. Строки прежнего (брошенного)
  `sessionUuid`, уже записанные в БД предыдущими сканами, при этом явно не
  удаляются — потенциально осиротевшие черновые строки остаются в
  `UnsentReportAnimals` до следующего логаута (`@Clearable()`) либо до
  ручного повторного попадания на то же место с новой сессией.
- **Правка уже сохранённой (ещё не отправленной) сессии** — открытие через
  `editSessionUuid`/`editPlaceId` (хаб «В работе» → карточка сессии):
  `ScanningStart` помечает сессию черновиком (`markSessionAsDraftByUuid`,
  снимает `readyToSend`) и подгружает уже отсканированные строки заново;
  повторное завершение (кнопка «Завершить» **или** уход с экрана кнопкой
  «назад» — `ScanningBloc.close()` при `isEditMode && _canPersistSession`
  доперсистит сессию как ready-to-send без явного подтверждения
  пользователя) помечает её снова `readyToSend = true`.
- **`readyToSend` — тихий no-op, если место не выбрано.** `ScanningEventSave`
  при `_canPersistSession == false` (место не выбрано) не вызывает ни
  `markSessionReadyToSend`, ни `replaceDraftSession`, но всё равно эмитит
  `ScanningExit`, как при успехе — экран закрывается без сообщения
  пользователю о том, что ничего не сохранено.
- **Push — единый batch-запрос на все `readyToSend == true` строки сразу**
  (`UnsentReportAnimalsRepository.sync`, `POST /exit-event`), не по сессиям и
  не по одной записи; `animal_id` в payload резолвится на клиенте по
  совпадению `transponderId`, но передаётся только если найден — иначе поле
  просто отсутствует, разрешение остаётся на сервере.
- **Push не проверяет тело ответа сервера.** `CustomDioClient.call` не
  бросает исключение на HTTP 200 с `{"status": "error", ...}` в теле;
  `sync()` только логирует ответ (`log('response: $response')`), не
  проверяет `response['status']`. `DataUpdateBloc.updateAndSyncSHTP()`
  безусловно вызывает `_reportsRepository.clear()` (весь локальный кэш
  `ReportAnimals`, все типы) и `_unsentReportsRepository.deleteAllReadyToSend()`
  (все `readyToSend == true` строки, все типы) сразу после `sync()`,
  независимо от того, принял ли сервер данные логически — **при
  content-уровневом отказе сервера данные сканирования теряются
  безвозвратно**, локальных копий не остаётся. Сетевое исключение (в отличие
  от логического отказа) прерывает выполнение раньше `clear()`/`deleteAllReadyToSend()` —
  в этом случае данные сохраняются и будут отправлены повторно на следующем
  проходе.
- **`@Clearable()` на обеих таблицах** — при логауте (`clearAllClearableTables()`)
  теряются как ещё не отправленные (`readyToSend == true` или `false`), так
  и локально закэшированные подтверждённые сервером строки.
- **Дублирование логики сопоставления метка↔животное с разной областью
  видимости.** Во время живого сканирования (`InventoryScanStepPage._computeSections`)
  «чужие известные» метки ищутся только среди мест **той же фермы**; на
  экране готового отчёта (`InventoryReportDetailsCubit`/`InventoryReportDetailsView._computeSections`)
  — среди **всех** мест независимо от фермы. Одна и та же метка животного с
  другой фермы во время сканирования показывается как «неизвестный номер», а
  после сохранения на экране отчёта — как «известное животное с другого
  объекта».

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals.dart` | `UnsentReportAnimals` | CURRENT | таблица черновика/готовой к отправке сессии |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao` | CURRENT | `getAllByFilters`, `getBySessionUuid`, `markSessionReadyToSendByUuid`, `markSessionAsDraftByUuid`, `deleteAllReadyToSend`, `deleteDraftBySessionUuid` |
| `packages/sheep_farm_database/lib/entities/reports_animals/report_animals.dart` | `ReportAnimals` | CURRENT | таблица локального кэша подтверждённых сервером отчётов |
| `packages/sheep_farm_database/lib/entities/reports_animals/report_animals_dao.dart` | `ReportAnimalsDao` | CURRENT | `getAllByFilters` |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.sync`, `replaceDraftSessionByUuid`, `markSessionReadyToSendByUuid`, `markSessionAsDraftByUuid`, `getSessionReportsByUuid`, `getInventoryReadySessions` | CURRENT | push, draft-персист на каждый скан, чтение сессии по uuid |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc`, `ScanningEventAddAnimal`, `ScanningEventSave`, `ScanningEventChangePlace`, `ScanningStart` | CURRENT | визард сканирования (создание/правка сессии) |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | итоговый отчёт по сессии/дню |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | хаб неотправленных сессий |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncSHTP` | CURRENT | оркестрация push → clear кэша → deleteAllReadyToSend → pull |
