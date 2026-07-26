# EVT-93 — full_sync_pass.triggered_automatically

| | |
|---|---|
| Инициатор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |

**Триггер.** Автоматически, при каждом холодном старте приложения — сразу
после проверки сессии ([EVT-6](EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md),
`AuthBloc.on<AuthEventStart>` эмитит `AuthToMain`) `MainPage`'s
`BlocListener<AuthBloc>` диспатчит `DataUpdateBloc.add(DataUpdateStartAll(
again: await hasConnection(), showDataUpdatePage: true))` — для гостя и
авторизованного пользователя одинаково.

**Эффект.** `DataUpdateBloc.on<DataUpdateStartAll>`: проверка сети
(единственный сетевой гейт для всего прохода — при отсутствии сети процесс
не стартует вовсе, даже справочники не загружаются) → `loadDirectories()`
([EVT-96](EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)) → `_loadBoardDirectories()`
([EVT-97](EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md)) → если
авторизован — `_syncAuthData()` (фермы/места/животные/отчёты/устройства,
уже специфицированы в `FARM`/`ANIMAL`/`PROFILE`) → `DataUpdateSuccess`.
Внутри `_syncAuthData` → `updateAndSyncRegagro()` решает «докат или полный
проход» — см. [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), эта
развилка фактически сломана и всегда выбирает полный `_syncAllData()`.

**Исходный код.** `lib/pages/main/main_page.dart` →
`BlocListener<AuthBloc>`; `lib/pages/profile/bloc/auth_bloc.dart` →
`on<AuthEventStart>`; `lib/blocs/data_update/data_update_bloc.dart` →
`on<DataUpdateStartAll>`, `_syncAuthData`, `updateAndSyncRegagro`, `_syncAllData`.
