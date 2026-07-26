# EVT-95 — local_data.cleared

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |

**Триггер.** Довершает [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md) (выход из
аккаунта, `ACTOR-1`) — также фактически срабатывает после
[EVT-8](EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) (автоматическая
потеря сессии, `ACTOR-3`), так как оба пути ведут к одному и тому же
`AuthLogout` в `MainPage`. `MainPage.on<AuthLogout>` диспатчит
`DataUpdateBloc.add(DataUpdateClear())`.

**Эффект.** `_appDatabase.clearUserData()` — очищает только таблицы,
помеченные `@Clearable()` (пользовательские/транзакционные: `Animals`,
`Movements`, `Vaccinations`, `AnimalWeighings`, `Disposals`, `Farms`,
`Places`, `UnsentReportAnimals`, `ReportAnimals`, `ProfileSettings`,
`DataUpdates` и др.) — справочники `HANDBOOKS`/`BOARD` (`Kinds`, `Breeds`,
`Countries`, `BoardAdTypes` и т.д., не `@Clearable`) и настройки сканера
(`Devices`, не `@Clearable`) переживают логаут на этом же устройстве — это
и есть механизм R71 «справочники остаются доступны офлайн», проявляющийся
именно здесь. Ещё два действия того же обработчика выполняются **без
`await`** (`DefaultCacheManager().emptyCache()`,
`pref.setBool('have_any_language', false)`) — обработчик и вызвавший его
код завершаются раньше, чем эти операции реально произойдут.

**Исходный код.** `lib/pages/main/main_page.dart` → `on<AuthLogout>`;
`lib/blocs/data_update/data_update_bloc.dart` → `on<DataUpdateClear>`;
`packages/sheep_farm_database/lib/database/database.dart` → `clearUserData`,
`clearAllClearableTables`.
