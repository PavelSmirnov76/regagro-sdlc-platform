# EVT-94 — full_sync_pass.triggered_manually

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |

**Триггер.** Два равнозначных входа: (а) кнопка «Синхронизировать данные»
на экране «В работе» — `DataUpdateBloc.add(DataUpdateStartAll(isUpdateData:
true))`; (б) кнопка «Повторить» на экране ошибки синхронизации
(`DataUpdatePage`) — `DataUpdateStartAll(showDataUpdatePage: false, again:
true)`.

**Эффект.** Тот же `on<DataUpdateStartAll>`, что и
[EVT-93](EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md).
Флаг `isUpdateData: true` (путь а) — единственный способ во всей кодовой
базе включить push пользовательских настроек на сервер
(`_settingsRepository.setSettingToSHTP()` внутри `_syncAllData`) —
намеренно привязан к явному ручному запуску, не к автоматическому старту.

**Исходный код.** `lib/pages/in_work/in_work_page.dart` → кнопка
«Синхронизировать данные»; `lib/pages/data_update/data_update_page.dart` →
кнопка «Повторить»; `lib/blocs/data_update/data_update_bloc.dart` →
`on<DataUpdateStartAll>`, `_syncAllData` (`isUpdateData` ветка).
