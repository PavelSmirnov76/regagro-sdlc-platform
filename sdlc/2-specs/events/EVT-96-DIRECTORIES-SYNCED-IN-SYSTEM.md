# EVT-96 — directories.synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy, HANDBOOKS) |

**Триггер.** Первый доменный шаг любого прохода (сразу после проверки
сети) — `DataUpdateBloc.loadDirectories()`, вызывается безусловно, для
гостя и авторизованного одинаково.

**Эффект.** Последовательно синхронизирует ~18 справочников HANDBOOKS
(`countries → kinds → breeds → suits → breedSuits → disposalReasons →
[vaccines+units, условно] → diseases → complexVaccines → injectionPlaces →
injectionMethods → vaccinationTypes → generationsTypes → ageGroups →
markerTypes → markerPlaces → kindMarkerPlaces → absenceReasons`), каждый с
`updatedAtGt: lastSyncDate`. Первый запуск (`lastSyncDate == null`) —
`clearAndInsertAll` (полная перезаливка) для каждого справочника; повторный —
`insertAll` (upsert только изменений). `vaccines`/`units` пропускаются
целиком, если есть неотправленные локальные вакцинации (чтобы не перетереть
ссылочные записи, на которые они опираются). «Последняя успешная
синхронизация» хранится в `SharedPreferences` (`last_directories_sync_date`/
`last_directories_sync_locale`), не в [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) —
смена языка интерфейса форсирует полный (не инкрементальный) реload
(сохранённая локаль перестаёт совпадать с текущей). Логин по логину/паролю
(не по refresh-токену) и переход в гостевой режим тоже форсируют полный
реload (`AuthRepository.clearDirectoriesLastSyncDate()`). Финальная запись
в журнал sync-прохода ошибочно уходит под категорией `generationsTypes`, а
не `directories` — см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md).

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc.loadDirectories`; `lib/data/services/app_cache_service.dart` →
`getDirectoriesLastSyncDate`, `saveDirectoriesLastSyncDate`,
`clearDirectoriesLastSyncDate`; `lib/repositories/auth/auth_repository.dart` →
`clearDirectoriesLastSyncDate` (вызовы из `loginWithoutAuthorization`,
`_getTokenDataFromApi`).
