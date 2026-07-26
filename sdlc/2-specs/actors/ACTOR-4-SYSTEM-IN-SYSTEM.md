# ACTOR-4 — Система (sync-проход)

## Идентичность

Не человек — приложение, действующее во время явного, запускаемого пользователем полного sync-прохода (`DataUpdateBloc`), отправляя и получая данные с сервера. Отличается от [ACTOR-3](ACTOR-3-APP-IN-AUTH.md) (тот действует один раз при холодном старте, вне sync-прохода) — разные триггеры, разные акторы (`../events/AGENTS.md`, «Exactly one initiator per event»).

Это сквозной актор: первым модулем, которому он понадобился, оказался FARM (суффикс тогда был `-IN-FARM`), но его идентичность (что значит «действовать во время sync-прохода») определяется не бизнес-логикой FARM, а самим sync-пайплайном, специфицируемым модулем `SYSTEM`. Теперь, когда `SYSTEM` написан (последний модуль пересборки), суффикс перенесён на `-IN-SYSTEM` — файл переименован, все входящие ссылки в дереве обновлены на новый путь, видимый id (`ACTOR-4`) не изменился (`../actors/AGENTS.md`, «Refinement for actors used broadly»; `../AGENTS.md`, «Paths may change when files are moved... never change the visible artifact ID»). Тот же порядок, каким в прошлой версии дерева обычный пользователь был перенесён на `-IN-AUTH`.

## Цели

Синхронизировать локальные изменения с сервером и получить актуальные данные с сервера для каждой сущности, у которой есть sync-шаг в `DataUpdateBloc` — без участия пользователя в момент каждого отдельного сетевого вызова (сам проход инициирован пользователем один раз, дальше идёт автоматически). Это цель на уровне всего sync-прохода, не конкретного модуля — ниже, в «Действия», перечислены только события тех модулей, которые уже специфицированы на сегодня; список будет расти по мере пересборки `2-specs/` дальше, не переписываться заново (`../actors/AGENTS.md`, «Cross-cutting actors get one home»).

## Действия

**FARM:** инициирует [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md), [EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md), [EVT-14](../events/EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md), [EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md), [EVT-19](../events/EVT-19-PLACE-UPDATE-SYNCED-IN-FARM.md), [EVT-20](../events/EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md), [EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md) через `DataUpdateBloc`. Взаимодействует с сущностями [ENT-9](../entities/ENT-9-FARM-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md).

**ANIMAL (все семь под-областей, ретроактивно добавлено сюда при специфицировании PROFILE — этот абзац следовало дополнять по ходу ANIMAL, пропуск исправлен, не переписывая уже готовые под-области заново):** инициирует [EVT-30](../events/EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-31](../events/EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md) (MOVE), [EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-36](../events/EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-38](../events/EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md) (VAC), [EVT-45](../events/EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-46](../events/EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md) (WEIGH), [EVT-53](../events/EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-54](../events/EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md) (DISP), [EVT-63](../events/EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md)/[EVT-64](../events/EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md) (INV — REG/REPRO переиспользуют события REG, отдельных sync-шагов не заводят) через `DataUpdateBloc`. Взаимодействует также с сущностями [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

**PROFILE:** инициирует [EVT-90](../events/EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md), [EVT-91](../events/EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md), [EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) через `DataUpdateBloc._suncDevices`. Взаимодействует также с сущностью [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md).

**SYSTEM:** инициирует [EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)
(справочники HANDBOOKS) и [EVT-97](../events/EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md)
(справочники BOARD) — первые два безусловных доменных шага любого
sync-прохода, до FARM/ANIMAL/PROFILE. Взаимодействует также с сущностями
[ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy, HANDBOOKS) и
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD).

SYSTEM — последний модуль пересборки; этот абзац закрывает перечень
действий этого актора на сегодня, дальше пополняется только если в дереве
появится восьмой модуль.

## Ограничения

Фермы (создание/обновление) отправляются на сервер по одной, в цикле — частичный успех возможен, не откатывает уже отправленные записи. Места (создание/обновление/удаление), напротив, отправляются единым батч-запросом на весь набор сразу — успех/отказ там all-or-nothing на уровне ответа сервера, без per-item детализации. Два разных сетевых паттерна в одном и том же sync-проходе, не унифицированы.

## Исходный код

| Файл | Класс/метод | Роль |
|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `_syncFarms`, `_syncPlaces`, `_storeFarmsToRDS`, `_updateFarmsOnRDS`, `_loadFarmsFromRDS`, `_storePlacesToRDS`, `_updatePlacesOnRDS`, `_loadPlacesFromRDS`, `_deletePlacesFromRDS` | оркестрация sync-прохода для ферм/мест |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.storeFarmsOnRDS`, `updateFarmsOnRDS`, `getAllFarmsFromRDS` | сетевые вызовы для ферм |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.storePlacesOnRDS`, `updatePlacesOnRDS`, `deletePlacesOnRDS`, `getAllPlacesFromRDS` | сетевые вызовы для мест |
