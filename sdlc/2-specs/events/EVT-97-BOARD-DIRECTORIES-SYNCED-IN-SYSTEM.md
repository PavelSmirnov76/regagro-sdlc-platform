# EVT-97 — board_directories.synced

| | |
|---|---|
| Инициатор | [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD) |

**Триггер.** Сразу после
[EVT-96](EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md), безусловно, для гостя и
авторизованного одинаково — `DataUpdateBloc._loadBoardDirectories()`.

**Эффект.** Синхронизирует 4 справочника BOARD (типы объявлений/статусы/
атрибуты/типы услуг — см. [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)),
каждый с `updatedAtGt`, равным тому же самому `directoriesSyncBaseline`,
что был прочитан **до** запуска
[EVT-96](EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) — единый общий «снимок»
момента начала прохода, разделяемый между HANDBOOKS- и BOARD-справочниками,
отдельного ключа для BOARD нет. Не пишет собственную запись в журнал
sync-прохода ([ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md)) —
успех/факт синка BOARD-справочников нигде отдельно не фиксируется.

**Исходный код.** `lib/blocs/data_update/data_update_bloc.dart` →
`DataUpdateBloc._loadBoardDirectories`; `lib/repositories/board/board_ad_types_repository.dart`,
`board_ad_statuses_repository.dart`, `board_attributes_repository.dart`,
`board_service_types_repository.dart` → соответствующие `sync*` методы.
