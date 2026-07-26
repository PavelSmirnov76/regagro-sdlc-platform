# UC-167 — Пользователь открывает «Настройки уведомлений», локальные значения загружаются успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь открывает экран «Настройки уведомлений»
(`/profile/profile_settings/notifications_settings`) и видит текущие
локально сохранённые настройки уведомлений о вакцинации — за сколько дней
предупреждать и включена ли отправка на email (R64,
[ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)). Чтение строго
локальное (Drift), без сетевого вызова — сравни с push/pull этой же
сущности через `SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`,
которые выполняются только как часть отдельного sync-прохода
([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)), не при открытии этого
экрана.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, разницы для этого сценария нет: маршрут не имеет
route-guard по авторизации, как и весь модуль `PROFILE`, см.
[MOD-6](../modules/MOD-6-PROFILE.md)).

## CURRENT

### Основной поток

1. Пользователь находится на `ProfilePage` → нажимает иконку настроек
   (`profile_page_wrapper.dart`, `IconButton` внутри `if (showActionButtons)`)
   → `context.pushNamed2(Routes.profileSettings)` → `ProfileSettingsPage`
   (`lib/pages/profile/presentation/profile_settings_page.dart`) рендерит
   `ProfileSettingsView`.
2. На `ProfileSettingsView` пользователь нажимает `ProfileButton` с текстом
   `l10n.profile_settings__notifications_settings`
   (`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`)
   → `onTap: () => context.pushNamed2(Routes.notificationsSettings)`.
   `Routes.notificationsSettings` вложен под `Routes.profileSettings` (сам
   вложен под `Routes.profile`) в `routes.dart` — итоговый путь
   `/profile/profile_settings/notifications_settings`.
3. `NotificationsSettingsPage.build`
   (`lib/pages/profile_settings/presentation/notifications_settings_page.dart`)
   создаёт `BlocProvider` с `create: (context) =>
   NotificationsSettingsCubit()..load()` — `load()` вызывается сразу же при
   создании кубита, без отдельного действия пользователя на этом экране.
4. Конструктор `NotificationsSettingsCubit` (`lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart`)
   стартует с `NotificationsSettingsState.initial(NotificationSettingsData(
   daysToVaccination: null, sendVaccinationNotificationOnEmail: null))` —
   оба поля `null` до завершения `load()`.
5. `load()` синхронно (до первого `await`) эмитит
   `NotificationsSettingsState.loading(...)`, копируя текущие (на этот
   момент ещё `null`) значения `data` без изменений.
6. `final profileSettings = await _settingsRepository.getProfileSettings();`
   — `SettingsRepository.getProfileSettings()`
   (`lib/repositories/settings/settings_repository.dart`) → `dao.getAll()`
   (Drift, таблица `ProfileSettings`, локально, без сети) →
   `.firstOrNull`. В этом сценарии запрос завершается без исключения и
   возвращает единственную сохранённую строку (см. «Инварианты»
   [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) —
   репозиторий всегда трактует таблицу как одну строку,
   `clearAndInsertAll`).
7. `load()` эмитит `NotificationsSettingsState.loaded(NotificationSettingsData(
   daysToVaccination: profileSettings?.daysToVaccination ?? 7,
   sendVaccinationNotificationOnEmail:
   profileSettings?.sendVaccinationNotificationOnEmail ?? true))`. Дефолты
   `7`/`true` применяются, только если `profileSettings == null` целиком
   (таблица пуста) — если строка есть, но одно из её полей `null`
   (`daysToVaccination` объявлен `int?` в схеме), для этого конкретного поля
   всё равно сработает `?? 7`, потому что `??` применяется к результату
   обращения к полю, а не к наличию строки в целом.
8. `NotificationsSettingsPage`'s `BlocConsumer` перестраивается: заголовок
   `CustomAppBar` (`l10n.profile_settings__notifications_settings`);
   `_SwitchRow` для `l10n.profile_settings__send_vaccination_notification_on_email`
   получает `value: state.data.sendVaccinationNotificationOnEmail ?? false`;
   `HorizontalPicker` получает `initialValue: state.data.daysToVaccination ??
   5` и перестраивает выбранную позицию через `didUpdateWidget` →
   `_resolveInitialIndex()` (не создаёт новый экземпляр state виджета,
   `PageController.jumpToPage` без анимации) на значение, пришедшее из
   `loaded`-состояния.

### Альтернативные потоки

- **В таблице `ProfileSettings` нет ни одной строки** (`dao.getAll()`
  возвращает `[]`, `.firstOrNull == null`) — шаг 7 применяет оба дефолта:
  `daysToVaccination: 7`, `sendVaccinationNotificationOnEmail: true`. Это
  состояние по умолчанию для устройства, ни разу не сохранявшего эти
  настройки локально (в т.ч. свежий гость или пользователь после логаута —
  таблица `@Clearable`, см.
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
- **Расхождение фолбэков между cubit'ом (`7`) и `HorizontalPicker`
  (`5`).** `NotificationsSettingsPage` передаёт в `HorizontalPicker`
  собственный фолбэк `?? 5`, отдельный от дефолта `?? 7`, зашитого в
  `NotificationsSettingsCubit.load()`. Наблюдаемо это расхождение только в
  узком окне: пока `state.data.daysToVaccination == null` — то есть на
  первом кадре после создания кубита, когда `state` уже успел стать
  `loading` (копия исходного `null`), но `loaded` ещё не эмитился (шаг 5,
  до завершения `await` на шаге 6). `HorizontalPicker.initState` в этот
  момент резолвит начальный индекс по `initialValue: 5` и, через
  `addPostFrameCallback`, синхронно вызывает `widget.onChanged(5)` —
  `NotificationsSettingsCubit.changeDaysToVaccination(5)`,
  **перезаписывая** `state.data.daysToVaccination` значением `5` **раньше**,
  чем шаг 6/7 успевает подставить туда `7` (или сохранённое значение) —
  Drift-запрос `getProfileSettings()` асинхронный и в общем случае
  завершается позже одного кадра отрисовки. Итоговое поведение зависит от
  относительной скорости: если `getProfileSettings()` резолвится раньше
  первого `addPostFrameCallback` — `loaded` перезатирает `5` актуальным
  значением, `HorizontalPicker.didUpdateWidget` синхронизирует позицию
  пикера обратно (не вызывая `onChanged` повторно); если наоборот —
  `state.data.daysToVaccination` остаётся `5` до тех пор, пока пользователь
  не выберет позицию сам, даже когда реально сохранённое или дефолтное
  значение — другое. На практике (локальный Drift-запрос) более вероятен
  первый вариант, но код не гарантирует порядок ни одной синхронизацией.
- **Ошибка чтения `dao.getAll()`** — не этот сценарий, см.
  `NotificationsSettingsState.failure` (отдельный `READ_ERROR`,
  использует те же дефолты `null`/`null` без применения `?? 7`/`?? true`,
  т.к. `failure` строит `NotificationSettingsData` напрямую с `null`-полями,
  не через ветку успеха).

### Связанные сущности

- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — читается целиком (`dao.getAll().firstOrNull`), не
  изменяется этим сценарием.

### Бизнес-правила

- Дефолты применяются на уровне cubit'а, не на уровне БД/DAO — таблица
  `ProfileSettings` не имеет строки-дефолта, дефолт `daysToVaccination: 7`,
  `sendVaccinationNotificationOnEmail: true` зашит буквально в
  `NotificationsSettingsCubit.load()` (см.
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md), «Поля»).
- Экран не инициирует ни push, ни pull к серверу — оба вызова
  (`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`) выполняются
  только как часть отдельного sync-прохода
  ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md),
  [MOD-6](../modules/MOD-6-PROFILE.md), «Граница»), не при открытии этого
  экрана — то, что видит пользователь здесь, отражает состояние локальной
  БД на момент открытия, не обязательно последнее серверное значение.
- Два переключателя на этом же экране (`_notifyOnNewMessages` —
  `l10n.profile_settings__notify_about_new_messages`,
  `_systemNotifications` — `l10n.profile_settings__system_notifications`)
  — чисто локальный `State` виджета `_NotificationsSettingsPageState`
  (`setState`), не читаются из `NotificationsSettingsCubit`/`ProfileSettings`
  и не сохраняются `save()` вообще: `load()` их не устанавливает, экран
  всегда показывает их в жёстко заданных начальных значениях
  (`true`/`false` соответственно) при каждом открытии, независимо от того,
  что пользователь выбирал в прошлый раз на этом же экране. Это не часть
  сценария `READ_OK`, описываемого этим файлом (который про
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)), но
  визуально расположены на том же экране и создают впечатление
  полноценных настроек — отмечено отдельно в «Открытые вопросы».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и достижим с единственной точки
входа (`ProfilePage` → иконка настроек → `ProfileSettingsPage` → кнопка
«Настройки уведомлений»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile_page_wrapper.dart` | `IconButton` (иконка настроек) | CURRENT | первый шаг маршрута — переход на `Routes.profileSettings` |
| `lib/pages/profile/presentation/profile_settings_page.dart` | `ProfileSettingsPage` | CURRENT | рендерит `ProfileSettingsView` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView` (кнопка «Настройки уведомлений») | CURRENT | точка входа именно на этот экран — `context.pushNamed2(Routes.notificationsSettings)` |
| `lib/pages/routes.dart` | `Routes.profile`, `Routes.profileSettings`, `Routes.notificationsSettings` | CURRENT | вложенность маршрута — итоговый путь `/profile/profile_settings/notifications_settings` |
| `lib/pages/profile_settings/presentation/notifications_settings_page.dart` | `NotificationsSettingsPage.build`, `_NotificationsSettingsPageState` | CURRENT | создаёт `NotificationsSettingsCubit()..load()`; локальные `_notifyOnNewMessages`/`_systemNotifications`, не связанные с cubit'ом; `HorizontalPicker` со своим фолбэком `?? 5` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit.load` | CURRENT | основной метод сценария — читает `SettingsRepository.getProfileSettings()`, эмитит `loaded` с дефолтами `7`/`true` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_state.dart` | `NotificationsSettingsState` (freezed union `initial`/`loading`/`loaded`/`saved`/`failure`), `NotificationSettingsData` | CURRENT | состояние экрана; `NotificationSettingsData` — обычный класс с `final` полями, не `freezed`/`Equatable` |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.getProfileSettings` | CURRENT | `dao.getAll().firstOrNull` — локальное, без сети |
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings_dao.dart` | `ProfileSettingsDao` (через `BaseRepository.dao`) | CURRENT | Drift DAO над таблицей `ProfileSettings` |
| `lib/widgets/horizontal_picker/horizontal_picker.dart` | `_HorizontalPickerState.initState`, `.didUpdateWidget`, `._resolveInitialIndex` | CURRENT | источник расхождения фолбэков — `initState` вызывает `onChanged(initialValue)` через `addPostFrameCallback`; `didUpdateWidget` только синхронизирует визуальную позицию, `onChanged` повторно не вызывает |

## Критерии приёмки

- Открытие экрана вызывает `NotificationsSettingsCubit.load()` ровно один
  раз, в момент создания кубита (без отдельного действия пользователя).
- Если `SettingsRepository.getProfileSettings()` возвращает сохранённую
  строку — `state.data.daysToVaccination`/`.sendVaccinationNotificationOnEmail`
  равны значениям этой строки (с `?? 7`/`?? true`, применяемым только к
  `null`-полю самой строки, не к отсутствию строки).
- Если `getProfileSettings()` возвращает `null` (таблица пуста) —
  `state.data.daysToVaccination == 7`,
  `state.data.sendVaccinationNotificationOnEmail == true`.
- Итоговое состояние — `NotificationsSettingsState.loaded`, независимо от
  того, была ли строка найдена или применены дефолты.
- Вызов не делает сетевых запросов (`setSettingToSHTP`/`getSettingFromSHTP`
  не вызываются этим сценарием).

## Связанные тесты

`test/pages/notifications_settings_cubit_test.dart`, группа `'UC-167 —
NotificationsSettingsCubit.load'` (имя группы — старая нумерация, до
переименования под текущие id, см. предисловие задачи; анкер `grep -r
"UC-167" test/` работает уже сегодня):

- `'успех, настройки на сервере есть -> loaded с ними'` — мокает
  `repository.getProfileSettings()` результатом `ProfileSetting(id: 1,
  daysToVaccination: 3, sendVaccinationNotificationOnEmail: false)`,
  проверяет `_isLoaded(cubit.state) == true`,
  `cubit.state.data.daysToVaccination == 3`,
  `cubit.state.data.sendVaccinationNotificationOnEmail == false`.
- `'настроек ещё нет (null) -> дефолты: 7 дней, включённые уведомления'` —
  мокает `repository.getProfileSettings()` результатом `null`, проверяет
  `cubit.state.data.daysToVaccination == 7`,
  `cubit.state.data.sendVaccinationNotificationOnEmail == true`.

Оба под-теста подтверждают именно ветку успеха (`READ_OK`), описанную этим
файлом; смежная группа `'UC-168 — NotificationsSettingsCubit.load ERROR'` в
том же файле покрывает отдельный сценарий отказа, не этот.

Ни `HorizontalPicker`, ни расхождение фолбэков `7`/`5` (см. «Альтернативные
потоки») не покрыты ни одним из этих тестов — оба теста проверяют только
`cubit.state`, полученный напрямую вызовом `cubit.load()`, без построения
виджета `NotificationsSettingsPage`/`HorizontalPicker` (`find test -iname
"*notifications_settings*"` находит только этот один файл, без
widget-теста страницы). **TBD — теста нет** на расхождение фолбэков и на
локальные, не сохраняемые переключатели `_notifyOnNewMessages`/
`_systemNotifications`.

## Открытые вопросы и ограничения

- **Расхождение дефолта `HorizontalPicker` (`5`) и дефолта cubit'а (`7`) —
  не проверено эмпирически, какая сторона выигрывает гонку.** Вывод в
  «Альтернативные потоки» о том, что локальный Drift-запрос обычно успевает
  раньше первого `addPostFrameCallback`, сделан статическим чтением кода
  (порядок `await`/`addPostFrameCallback` в Flutter event loop), не
  подтверждён ни одним запущенным widget-тестом — см. «Связанные тесты»,
  TBD. Ничем в коде не зафиксировано, было ли расхождение `7`/`5`
  намеренным (два разработчика писали значения независимо) или опечаткой.
- **Два переключателя на этом же экране (`_notifyOnNewMessages`,
  `_systemNotifications`) визуально неотличимы от настоящих настроек, но
  не сохраняются нигде.** Пользователь может выключить/включить их,
  нажать «Сохранить» (`save()` их не читает и не пишет) и после повторного
  открытия экрана обнаружить, что оба вернулись к исходным `true`/`false`
  — не задокументировано нигде как временная заглушка или сознательно
  decorative UI; выглядит как незавершённая функциональность.
- Не проверено эмпирически на реальном устройстве (например, поведение
  `HorizontalPicker` при заметной задержке Drift-запроса, скажем, на очень
  большой локальной БД) — вывод сделан статическим чтением кода
  `NotificationsSettingsCubit`/`HorizontalPicker`, подтверждён только
  модульным тестом уровня cubit'а без реального виджетного дерева.
