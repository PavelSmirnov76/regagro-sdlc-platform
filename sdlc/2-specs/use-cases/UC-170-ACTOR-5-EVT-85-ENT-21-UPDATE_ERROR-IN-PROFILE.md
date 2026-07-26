# UC-170 — Сохранение настроек уведомлений о вакцинации отказывает: локальная запись обрывается технической ошибкой, экран молча сбрасывает введённые значения

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же триггер, что описан в [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md) —
пользователь меняет дни-до-вакцинации и/или email-переключатель на экране
`NotificationsSettingsPage` и нажимает «Сохранить»
(`NotificationsSettingsCubit.save()`). Здесь сама локальная запись —
`SettingsRepository.saveProfileSettings` → `dao.clearAndInsertAll` — не
завершается успешно, а бросает исключение (это чисто локальная Drift/SQLite
операция, сеть в `save()` вообще не участвует — push на сервер выполняется
отдельно, отдельным sync-проходом, см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
Задокументирован полный путь от `catch` внутри кубита до того, что
реально видит пользователь на экране — и это не сообщение об ошибке, а
незаметный визуальный сброс введённых значений.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость и авторизованный проходят один и тот же код, экран открывается без
route-guard по авторизации, маршрут `Routes.notificationsSettings`,
`lib/pages/routes.dart`).

## CURRENT

### Основной поток

1. `NotificationsSettingsPage` открывает `BlocProvider(create: (context) =>
   NotificationsSettingsCubit()..load())` — после `load()` состояние
   `loaded` с текущими сохранёнными значениями (или дефолтами `7`/`true`,
   если настроек ещё нет — см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
2. Пользователь двигает `HorizontalPicker` (дни, 1–30) и/или переключает
   `CupertinoSwitch` email-уведомления. Каждое взаимодействие синхронно
   вызывает `changeDaysToVaccination`/`changeSendVaccinationNotificationOnEmail`,
   которые эмитят `NotificationsSettingsState.loaded` с обновлённым
   `NotificationSettingsData` — только в памяти кубита, ничего ещё не
   сохранено.
3. Пользователь нажимает `BlackCircleButton` «Сохранить»
   (`floatingActionButton` страницы) → `context.read<NotificationsSettingsCubit>().save()`.
4. `save()` входит в `try`, строит `ProfileSettingsCompanion.insert(daysToVaccination:
   Value(state.data.daysToVaccination), sendVaccinationNotificationOnEmail:
   Value(state.data.sendVaccinationNotificationOnEmail ?? false))` и вызывает
   `await _settingsRepository.saveProfileSettings(...)`.
5. `SettingsRepository.saveProfileSettings` делегирует
   `dao.clearAndInsertAll([profileSettings])` —
   `BaseDao.clearAndInsertAll` оборачивает `delete(_currentTableInfo).go()` +
   `insAll(list)` одной `transaction()`. Здесь этот вызов (уровень
   Drift/SQLite) бросает исключение.
6. Исключение всплывает из `await _settingsRepository.saveProfileSettings(...)`
   прямо в `save()`, попадает в `catch (e)` — единственный перехват в этом
   методе.
7. `catch (e)`: `getIt.get<Talker>().error(e.toString())` — логирование,
   недоступное обычному пользователю в моменте отказа: `Talker` пишет в
   консоль/DevTools, а единственный экран приложения, монтирующий
   `TalkerScreen` (`profile_view.dart` → `_openLogs`, кнопка `ProfileButton`
   «Logger»), скрыт за `BlocBuilder<DeveloperModeBloc, DeveloperModeState>`
   и показывается только после `DeveloperModeEnabled` — включается 6
   нажатиями на скрытый элемент профиля (`DeveloperModeEventClickDeveloperMode`,
   `lib/blocs/developer_mode/developer_mode_bloc.dart`), персистентно
   сохраняется в Hive (`AuthRepository.isDeveloper`/`.setIsDeveloper`).
   Пользователь без предварительно включённого dev-режима эту ошибку нигде
   не увидит.
8. `emit(NotificationsSettingsState.failure(NotificationSettingsData(daysToVaccination:
   null, sendVaccinationNotificationOnEmail: null), e.toString()))` — обе
   величины, выбранные пользователем на шаге 2, заменяются `null`,
   независимо от того, что было введено.
9. `NotificationsSettingsPage` пересобирается с новым `state`.
   `BlocConsumer.listener` вызывает `state.whenOrNull(saved: (_) =>
   context.pop())` — для `failure` ни одна ветка `whenOrNull` не совпадает,
   `listener` не выполняет вообще ничего: экран не закрывается (в отличие от
   успеха), но и никакого `SnackBar`/диалога/иного сообщения об ошибке не
   показывается.
10. `builder`, тем не менее, использует новые данные `state.data` напрямую:
    `CupertinoSwitch(value: state.data.sendVaccinationNotificationOnEmail ??
    false, ...)` — становится `false`, даже если пользователь перед
    сохранением явно включил уведомления: переключатель визуально
    «выключается» сам по себе. `HorizontalPicker(initialValue:
    state.data.daysToVaccination ?? 5, ...)` получает новое значение `5`
    (не `null`) — `_HorizontalPickerState.didUpdateWidget` сравнивает
    `oldWidget.initialValue != widget.initialValue`, видит расхождение,
    пересчитывает `_selectedIndex = _resolveInitialIndex()` и вызывает
    `_controller.jumpToPage(_selectedIndex)`: ползунок визуально прыгает на
    день `5`. `onChanged` при этом не вызывается —
    он вызывается только один раз, из `initState` (`postFrameCallback`), не
    из `didUpdateWidget` — то есть кубит не получает никакого нового
    события об этом визуальном скачке, `state.data.daysToVaccination`
    внутри кубита остаётся `null`, хотя на экране показано `5`.
11. Итог, наблюдаемый пользователем: нажатие «Сохранить» не приводит ни к
    какому видимому сообщению об ошибке; экран остаётся открытым, но
    выбранные значения визуально сбрасываются (email-переключатель — на
    «выключено», дни — на `5`) без единого предупреждения, будто что-то
    было сброшено сервером или системой. На самом деле произошла локальная
    техническая ошибка записи, а старые сохранённые настройки в БД вообще
    не были тронуты — `clearAndInsertAll` выполняет `clear()` и `insAll()`
    в одной `transaction()`, поэтому если `insAll()` не завершился (или
    `clear()` откатился вместе с ним), прежняя строка `ProfileSettings`
    остаётся в БД как была.

### Альтернативные потоки

- **Повторное нажатие «Сохранить» сразу после ошибки, без повторного
  движения ползунка/переключателя.** Поскольку `HorizontalPicker` визуально
  прыгнул на `5`, но `onChanged` при этом не вызывался (см. шаг 10),
  `cubit.state.data.daysToVaccination` фактически остаётся `null` (не `5`).
  Повторный `save()` соберёт `ProfileSettingsCompanion.insert(daysToVaccination:
  Value(null), ...)` — колонка `daysToVaccination` объявлена `nullable()`
  (`packages/sheep_farm_database/lib/entities/profile_settings/profile_settings.dart`),
  поэтому запись пройдёт без ошибки схемы (если репозиторий на этот раз не
  бросит исключение), но значение «дней до вакцинации» будет тихо стёрто в
  `null` — хотя пользователь только что видел на экране `5`. Это отдельный,
  не покрываемый этим use-case побочный эффект самого сценария ошибки;
  фиксируется здесь как наблюдение, не специфицируется отдельно (обычный
  успешный `save()` уже полностью покрыт [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md)
  без учёта этой развилки).
- **Пользователь трогает переключатель/ползунок ПОСЛЕ `failure`, перед
  повторной попыткой сохранения.** Обычный вызов
  `changeDaysToVaccination`/`changeSendVaccinationNotificationOnEmail`,
  `emit(loaded(...))` с новыми данными — не отличается от обычного изменения
  вне сценария ошибки; предыдущее состояние `failure` не оставляет никакого
  видимого шрама для этой ветки.
- **`REJECTED`-ветки не существует.** Вызов `saveProfileSettings` — чисто
  локальная Drift-операция, никакой сервер не может «осознанно отклонить»
  её на этом шаге; всё, что долетает до `catch`, по определению `ERROR`.
- Реальный триггер исключения (переполнение диска, закрытая во время логаута
  БД, повреждение файла SQLite и т.п.) этой спекой не воспроизведён —
  эмпирически подтверждён только наблюдаемый эффект внутри кубита/UI (тест,
  см. «Связанные тесты», мокает `SettingsRepository.saveProfileSettings`,
  бросающий обычный `Exception('db error')` напрямую, не через настоящий
  Drift/SQLite стек).

### Связанные сущности

- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) (ProfileSettings) —
  сама update-операция, которая здесь обрывается: строка не перезаписывается
  (транзакция не коммитится полностью), прежнее сохранённое значение (если
  было) остаётся в БД нетронутым.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не участвует;
  `saveProfileSettings` не читает и не пишет пользователя.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) — не участвует; `Kind.visible` (R65) сохраняется отдельным
  экраном/кубитом, не этим методом.

### Бизнес-правила

- `try/catch` вокруг `save()` — единственная защита от исключения; нет
  отдельной классификации ошибок, поэтому любое исключение на этом пути
  всегда `ERROR`, никогда `REJECTED`.
- Экран не показывает пользователю никакого сообщения об ошибке ни в каком
  виде (`SnackBar`/диалог/текст) на самой странице настроек уведомлений —
  единственный канал, `Talker.error()`, доступен только через отдельный,
  скрытый за dev-режимом экран (`profile_view.dart` → `_openLogs` →
  `TalkerScreen`), не связанный с этим экраном напрямую и не всплывающий
  автоматически.
- Состояние `failure` сбрасывает оба поля `NotificationSettingsData` в
  `null`, что через `builder` визуально «стирает» пользовательский ввод на
  экране (переключатель — выключен, дни — `5`), создавая обманчивое
  впечатление сброса настроек, хотя фактическая причина — техническая
  ошибка сохранения, а данные в БД не менялись.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий целиком прослеживается
статическим чтением кода (`notifications_settings_cubit.dart`,
`notifications_settings_page.dart`, `settings_repository.dart`,
`horizontal_picker.dart`) и подтверждён тестом на уровне кубита (мок
репозитория, без реального Drift/SQLite стека) — см. «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit.save` | CURRENT | `try/catch` вокруг `saveProfileSettings`; при исключении логирует через `Talker.error` и эмитит `failure` с обнулённым `NotificationSettingsData` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit.changeDaysToVaccination`, `.changeSendVaccinationNotificationOnEmail` | CURRENT | синхронные сеттеры, формирующие `state.data` до нажатия «Сохранить» |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_state.dart` | `NotificationsSettingsState.failure`, `NotificationSettingsData` | CURRENT | freezed-состояние ошибки и его payload (оба поля nullable, обнуляются при `failure`) |
| `lib/pages/profile_settings/presentation/notifications_settings_page.dart` | `_NotificationsSettingsPageState.build` (`BlocConsumer.listener`) | CURRENT | обрабатывает только ветку `saved` (`context.pop()`); ветка `failure` не имеет обработчика — UI не показывает ошибку |
| `lib/pages/profile_settings/presentation/notifications_settings_page.dart` | `_SwitchRow` (`CupertinoSwitch.value`), `HorizontalPicker(initialValue:)` | CURRENT | читают `state.data` напрямую с фолбэками `?? false`/`?? 5` — визуально «сбрасываются» при `failure` |
| `lib/widgets/horizontal_picker/horizontal_picker.dart` | `_HorizontalPickerState.didUpdateWidget` | CURRENT | реагирует на изменение `initialValue` после `failure` — `jumpToPage` без повторного вызова `onChanged` |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.saveProfileSettings` | CURRENT | локальный вызов `dao.clearAndInsertAll` — единственный источник исключения в этом сценарии; сеть не участвует |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clearAndInsertAll`, `.clear` | CURRENT | атомарная транзакция `delete`+`insert` — источник потенциального Drift/SQLite исключения |
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings.dart` | `ProfileSettings` | CURRENT | таблица с nullable `daysToVaccination` — допускает `Value(null)` без ошибки схемы (см. «Альтернативные потоки») |
| `lib/injection_container.dart` | регистрация `Talker` (`TalkerFlutter.init`) | CURRENT | логирование в консоль/DevTools |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `_openLogs` (монтирует `TalkerScreen`) | CURRENT | единственный экран приложения, показывающий содержимое `Talker` пользователю; кнопка видна только при `DeveloperModeEnabled` |
| `lib/blocs/developer_mode/developer_mode_bloc.dart` | `DeveloperModeBloc.on<DeveloperModeEventClickDeveloperMode>` | CURRENT | 6 нажатий на скрытый элемент профиля включают dev-режим персистентно (`AuthRepository.setIsDeveloper`) — единственный путь, открывающий доступ к `TalkerScreen` |

## Критерии приёмки

- Если `SettingsRepository.saveProfileSettings` бросает исключение,
  `NotificationsSettingsCubit.save()` перехватывает его, логирует через
  `Talker.error`, и эмитит `NotificationsSettingsState.failure` с
  `NotificationSettingsData(daysToVaccination: null,
  sendVaccinationNotificationOnEmail: null)` и `error == e.toString()`.
- `NotificationsSettingsPage` не закрывается (`context.pop()` вызывается
  только на `saved`, не на `failure`) и не показывает пользователю
  `SnackBar`/диалог/иной текст ошибки.
- `CupertinoSwitch` и `HorizontalPicker` на экране после `failure`
  отображают «выключено»/`5` соответственно (через `?? false`/`?? 5`),
  независимо от значений, выбранных пользователем до нажатия «Сохранить».
- Строка `ProfileSettings` в БД остаётся такой же, какой была до неудачной
  попытки сохранения (`clearAndInsertAll` — атомарная транзакция).

## Связанные тесты

- `test/pages/notifications_settings_cubit_test.dart`, group `'UC-170 —
  NotificationsSettingsCubit.save ERROR'`, test `'ошибка репозитория ->
  failure, залогировано'` — мокает `repository.saveProfileSettings(any())`
  через `thenThrow(Exception('db error'))`, проверяет `_isFailure(cubit.state)
  == true` и `verify(() => getIt<Talker>().error(any())).called(1)`.
  Группа названа по прежней нумерации id (`UC-170`) — переименование под
  `UC-170` выполняется отдельным контролируемым проходом, не этой задачей;
  якорь `grep -r "UC-170" test/` заработает только после него.

## Открытые вопросы и ограничения

- **Визуальный сброс данных без единого сообщения об ошибке — не
  задокументированный ранее дефект юзабилити.** Пользователь, только что
  выбравший, например, 20 дней и включивший email-уведомления, после
  неудачного сохранения видит экран с «5 дней» и выключенным
  переключателем — неотличимо от того, будто он сам их так и не менял,
  никакого явного признака отказа операции не показывается ни на самом
  экране настроек, ни в виде какого-либо системного уведомления (см. ниже
  про `TalkerScreen`).
- **Расхождение дефолтов.** `HorizontalPicker.initialValue: state.data.daysToVaccination
  ?? 5` в `notifications_settings_page.dart` использует фолбэк `5`, тогда
  как бизнес-дефолт «нет сохранённых настроек» — `7`, зафиксированный в
  `NotificationsSettingsCubit.load()` и задокументированный в
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md). Эти два `5`
  и `7` — независимые константы в разных файлах, нигде не связанные общим
  источником; сценарий этого use-case дополнительно проявляет `5` как
  видимое пользователю число после ошибки, а не только как визуальную
  деталь `HorizontalPicker` до первой загрузки.
- Эмпирически не подтверждено, какое именно исключение Drift/SQLite
  реалистично возникает в проде на этом пути (диск, повреждение файла,
  закрытая во время логаута БД и т.п.) — тест воспроизводит только
  наблюдаемый эффект через мок репозитория с обычным `Exception`, не через
  настоящий Drift-стек.
- **`Talker.error()` технически не «в никуда», но практически недостижим для
  обычного пользователя.** `TalkerScreen` (`profile_view.dart` → `_openLogs`)
  показал бы эту ошибку текстом, но кнопка, открывающая его, скрыта за
  `DeveloperModeEnabled` — состоянием, включаемым 6 нажатиями на скрытый
  элемент профиля и не имеющим никакой подсказки в UI о своём существовании;
  для подавляющего большинства пользователей приложения (никогда не
  включавших dev-режим) эффект неотличим от полного отсутствия канала
  диагностики.
- Два «декоративных» переключателя на этом же экране
  (`_notifyOnNewMessages`, `_systemNotifications`, локальный `State`
  виджета) не относятся к [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  и не сохраняются `save()` (уже отмечено в
  [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md)) —
  этот сценарий ошибки их не затрагивает, но они физически на том же
  экране и визуально не отличаются от переключателя email-уведомлений, что
  может ввести в заблуждение при разборе бага пользователем/QA.
