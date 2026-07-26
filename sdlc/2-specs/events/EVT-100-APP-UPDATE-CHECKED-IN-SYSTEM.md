# EVT-100 — app_update.checked

| | |
|---|---|
| Инициатор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) |

**Триггер.** Автоматически, сразу после успешного завершения полного
sync-прохода ([EVT-93](EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)/[EVT-94](EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md),
`DataUpdateSuccess` в `data_update_page.dart`) — `AppUpdateBloc.add(
AppUpdateEventCheckUpdate(showModalMessage: true))`. Также вручную — кнопка
проверки обновлений/иконка refresh внутри уже открытого `AppUpdatePage`.

**Эффект.** Вне прод-сборки (`!Constants.isProd`) — обработчик молча
ничего не делает. В проде — `AppUpdateRepository.checkNewVersionRintIos`
(единственный оставшийся источник, обращается к `itunes.apple.com/lookup`,
безусловно для любой платформы, включая Android — см.
[ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md)); если версия
новее — `AppUpdateNewVersion`, иначе `AppUpdateMessage('no_updates_required')`.
«Обязательное» обновление (`immediate == true`, блокирующий `WillPopScope`
на `AppUpdatePage`) структурно недостижимо — единственный источник всегда
передаёт `immediate: false`.

**Исходный код.** `lib/pages/data_update/data_update_page.dart` →
диспатч после `DataUpdateSuccess`; `lib/blocs/app_update/app_update_bloc.dart` →
`on<AppUpdateEventCheckUpdate>`; `lib/repositories/app_update/app_update_repository.dart` →
`checkNewVersionRintIos`; `lib/pages/app_update/app_update_page.dart`.
