# UC-169 — Пользователь сохраняет настройки уведомлений о вакцинации

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь на экране «Уведомления» (`NotificationsSettingsPage`) меняет
количество дней-до-вакцинации и/или переключатель отправки email-уведомления
и подтверждает сохранение. Локальная таблица `ProfileSettings` перезаписывается
целиком одной строкой; отправка изменения на сервер этим сценарием не
выполняется — это отдельный, условный шаг более позднего sync-прохода (см.
[ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md), «Инварианты»).
Happy-path сценарий события
[EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md)
(`vaccination_notification_settings.saved`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость и авторизованный обрабатываются одинаково. Маршрут экрана «Уведомления»
не имеет route-guard по авторизации (весь модуль `PROFILE` — см.
[MOD-6](../modules/MOD-6-PROFILE.md)); ни `NotificationsSettingsPage`, ни
`NotificationsSettingsCubit` нигде не проверяют `AppCacheService.isAuthorized()`.

## CURRENT

### Основной поток

1. `NotificationsSettingsPage` создаёт `BlocProvider(create: (context) =>
   NotificationsSettingsCubit()..load())` — загрузка текущих настроек
   (дефолт `daysToVaccination: 7`, `sendVaccinationNotificationOnEmail: true`,
   если строки в `ProfileSettings` ещё нет) относится к отдельному сценарию
   просмотра ([EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md)),
   здесь не переспецифицируется.
2. Пользователь двигает `HorizontalPicker` (значения `1..30`) — `onChanged`
   вызывает `NotificationsSettingsCubit.changeDaysToVaccination(value)`,
   который синхронно эмитит `NotificationsSettingsState.loaded(...)` с новым
   `daysToVaccination` и неизменным `sendVaccinationNotificationOnEmail`. Это
   чисто в памяти кубита — ни один DAO/репозиторий не вызывается.
3. И/или пользователь переключает `_SwitchRow`, привязанный к
   `state.data.sendVaccinationNotificationOnEmail` — `onChanged` вызывает
   `changeSendVaccinationNotificationOnEmail(value)`, аналогично эмитит
   `loaded` с новым значением флага.
4. Пользователь нажимает кнопку сохранения (`BlackCircleButton` в
   `floatingActionButton`, `title: l10n.save`) — `onTap:` вызывает
   `context.read<NotificationsSettingsCubit>().save()`.
5. `NotificationsSettingsCubit.save()` строит
   `ProfileSettingsCompanion.insert(daysToVaccination:
   Value(state.data.daysToVaccination), sendVaccinationNotificationOnEmail:
   Value(state.data.sendVaccinationNotificationOnEmail ?? false))` и вызывает
   `SettingsRepository.saveProfileSettings(profileSettings)`.
6. `SettingsRepository.saveProfileSettings` вызывает
   `dao.clearAndInsertAll([profileSettings])`
   (`BaseRepository.clearAndInsertAll` → `ProfileSettingsDao` наследует его
   от `BaseDao.clearAndInsertAll`). Это одна Drift-транзакция:
   `clear()` (`DELETE` всех строк таблицы `ProfileSettings`), затем
   `insAll([profileSettings])` (`INSERT` с `InsertMode.insertOrReplace`) —
   таблица не апдейтится по `id`/`userId`, а полностью пересоздаётся заново
   одной строкой (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md),
   «Инварианты» — «единственная строка таблицы полностью перезаписывается на
   каждое сохранение»).
7. Исключений нет → `save()` без ошибки продолжает выполнение и эмитит
   `NotificationsSettingsState.saved(NotificationSettingsData(daysToVaccination:
   state.data.daysToVaccination, sendVaccinationNotificationOnEmail:
   state.data.sendVaccinationNotificationOnEmail))` — то же значение,
   которое уже было в `state.data` на момент вызова `save()`.
8. `NotificationsSettingsPage`'s `BlocConsumer.listener`:
   `state.whenOrNull(saved: (_) { context.pop(); })` — единственная реакция
   UI на `saved` — закрыть экран (`Navigator.pop`), возвращаясь на предыдущий
   (обычно `ProfileSettingsPage`). Никакого success-снекбара или иного
   визуального подтверждения не показывается.
9. Отправка изменения на сервер этим методом не выполняется. Push
   (`SettingsRepository.setSettingToSHTP()`) вызывается только при следующем
   `DataUpdateStartAll` с `event.isUpdateData == true` — единственная точка
   вызова во всей кодовой базе, кнопка ручного «Обновить данные» на экране
   «В работе» (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
   До этого момента новое значение существует только в локальной БД.

### Альтернативные потоки

- **Два дополнительных переключателя на этом же экране не сохраняются
  вообще.** `_notifyOnNewMessages` и `_systemNotifications` в
  `_NotificationsSettingsPageState` — обычные поля `State` виджета
  (`bool _notifyOnNewMessages = true; bool _systemNotifications = false;`),
  меняются только через `setState`, никогда не читаются `save()` и не входят
  в `NotificationSettingsData`/`ProfileSettingsCompanion`. Переключение любого
  из них визуально работает (виджет перерисовывается), но эффект исчезает
  при повторном открытии экрана — значения всегда возвращаются к жёстко
  заданным `true`/`false` (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)).
- **Нажатие «Сохранить» до завершения `load()` пишет `null`/`false` поверх
  уже сохранённого значения.** Кнопка сохранения отрисовывается в
  `floatingActionButton` безусловно, независимо от состояния кубита
  (`initial`/`loading`/`loaded`/`failure`) — `builder` не блокирует и не
  прячет её на время загрузки. `NotificationsSettingsCubit()..load()`
  запускает `load()` синхронно при создании кубита, но до разрешения
  `await _settingsRepository.getProfileSettings()` состояние — `initial`
  (поля `null`/`null`) или, сразу после первого `emit` внутри `load()`,
  `loading` с теми же `null`-полями, скопированными из `state.data` на
  момент вызова. Если пользователь успевает тапнуть «Сохранить» в этом окне
  (реалистично — при заметно медленном первом обращении к Drift на холодном
  старте), `save()` вызывается с `state.data.daysToVaccination == null` и
  `state.data.sendVaccinationNotificationOnEmail == null`:
  `ProfileSettingsCompanion.insert(daysToVaccination: Value(null),
  sendVaccinationNotificationOnEmail: Value(null ?? false))` —
  `clearAndInsertAll` без ошибки записывает строку с `daysToVaccination:
  null`, `sendVaccinationNotificationOnEmail: false`, безвозвратно стирая
  любое ранее сохранённое значение. Исключения при этом не бросается — кубит
  всё равно эмитит `saved`, то есть с точки зрения `RESULT`-классификации
  это тот же `UPDATE_OK`, просто с неожиданным содержимым записи. Не
  воспроизведено автоматическим тестом (см. «Открытые вопросы»).
- **`SettingsRepository.saveProfileSettings` бросает исключение** (например
  ошибка Drift) — внешний `try/catch` в `save()` ловит его, логирует через
  `Talker.error` и эмитит `NotificationsSettingsState.failure(...)` —
  отдельный use-case (`UPDATE_ERROR`), не этот.

### Связанные сущности

- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) (ProfileSettings) —
  единственная сущность, чьё состояние меняется: локальная таблица
  полностью перезаписывается одной строкой на каждый вызов `save()`.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не читается и не
  пишется этим сценарием: колонка `ProfileSettings.userId` объявлена в схеме,
  но мертва (см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)),
  так что сохранение не привязывается к конкретному пользователю на уровне
  БД.

### Бизнес-правила

- Сохранение — не upsert по `id`/`userId`: `dao.clearAndInsertAll` внутри
  одной транзакции удаляет все существующие строки и вставляет ровно одну
  новую с переданными полями.
- `save()` никогда сам не инициирует сетевой запрос — push настроек на
  сервер полностью отделён и выполняется системным актором
  ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) только при
  `DataUpdateStartAll(isUpdateData: true)`; при любом другом триггере
  полного sync-прохода (логин, повторная попытка на экране обновления,
  ресинк после смены языка) выполняется только безусловный pull
  (`getSettingFromSHTP()`), который может молча перетереть только что
  сохранённое здесь значение старым серверным — уже задокументированный
  инвариант [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md), не
  специфичный для этого use-case, но напрямую следующий из его результата.
- `sendVaccinationNotificationOnEmail` в отправляемую строку попадает как
  `state.data.sendVaccinationNotificationOnEmail ?? false` — если поле
  почему-то `null` на момент сохранения, записывается `false`
  («выключено»), а не сохраняется предыдущее значение и не выбрасывается
  ошибка.
- Успешное сохранение не показывает пользователю никакого подтверждения,
  кроме закрытия экрана (`context.pop()` по `saved`) — нет ни snackbar, ни
  иного визуального сигнала.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (перезапись `ProfileSettings` через `clearAndInsertAll`,
переход в `saved`, закрытие экрана) полностью реализован и покрыт тестом на
уровне кубита (см. «Связанные тесты»); находки в «Альтернативные потоки»/
«Открытые вопросы» (гонка с `load()`, недостижимость двух декоративных
переключателей) описывают неожиданное, но не падающее с ошибкой поведение
существующего кода — они не блокируют исполнение основного потока.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/presentation/notifications_settings_page.dart` | `_NotificationsSettingsPageState.build`, `BlocConsumer.listener` | CURRENT | UI-триггер (`BlackCircleButton.onTap` → `save()`), реакция на `saved` (`context.pop()`), локальные декоративные переключатели `_notifyOnNewMessages`/`_systemNotifications` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit.save`, `.changeDaysToVaccination`, `.changeSendVaccinationNotificationOnEmail`, `.load` | CURRENT | сборка `ProfileSettingsCompanion`, вызов репозитория, эмиты `loaded`/`saved`/`failure` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_state.dart` | `NotificationsSettingsState` (`.saved`, `.loaded`, `.failure`), `NotificationSettingsData` | CURRENT | freezed-состояния экрана и plain data-класс полей |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.saveProfileSettings`, `.getProfileSettings` | CURRENT | локальный CRUD поверх `ProfileSettingsDao`; `saveProfileSettings` — единственная точка вызова `clearAndInsertAll` для этой таблицы |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clearAndInsertAll`, `.clear`, `.insAll` | CURRENT | реализация «удалить всё + вставить заново» одной транзакцией |
| `lib/repositories/base_repository.dart` | `BaseRepository.clearAndInsertAll` | CURRENT | проброс вызова от репозитория к DAO |
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings_dao.dart` | `ProfileSettingsDao` | CURRENT | DAO таблицы `ProfileSettings`, без переопределений поверх `BaseDao` |
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings.dart` | `ProfileSettings`, `ProfileSettingsCompanion` | CURRENT | Drift-таблица/companion — `daysToVaccination` (`int?`), `sendVaccinationNotificationOnEmail` (`bool`, default `true`) |
| `lib/injection_container.dart` | `getIt.registerLazySingleton<SettingsRepository>` | CURRENT | DI-регистрация `SettingsRepository(getIt.get<KindsRepository>())` |

## Критерии приёмки

- `changeDaysToVaccination(value)`/`changeSendVaccinationNotificationOnEmail(value)`
  синхронно обновляют соответствующее поле `NotificationSettingsData` в
  `state`, не затрагивая другое поле и не обращаясь к репозиторию.
- Вызов `save()` приводит ровно к одному вызову
  `SettingsRepository.saveProfileSettings` с
  `ProfileSettingsCompanion.insert(daysToVaccination:
  Value(state.data.daysToVaccination), sendVaccinationNotificationOnEmail:
  Value(state.data.sendVaccinationNotificationOnEmail ?? false))`.
- После успешного `saveProfileSettings` таблица `ProfileSettings` содержит
  ровно одну строку с сохранёнными значениями (эффект `clearAndInsertAll` —
  предыдущие строки удалены).
- При успехе `save()` эмитит `NotificationsSettingsState.saved(...)` с теми
  же значениями полей, что были в `state.data` перед вызовом; ни один
  сетевой вызов (`setSettingToSHTP`) этим методом не выполняется.
- `NotificationsSettingsPage` реагирует на `saved` вызовом `context.pop()`
  без показа snackbar.

## Связанные тесты

- `test/pages/notifications_settings_cubit_test.dart`, group `'UC-169 —
  NotificationsSettingsCubit.save'`, test `'успех -> saveProfileSettings
  вызван, saved'` — подтверждает шаги 5-7 основного потока: мокнутый
  `SettingsRepository.saveProfileSettings(any())` отвечает успехом, после
  `changeDaysToVaccination(5)` + `save()` состояние переходит в `saved`, и
  `saveProfileSettings` вызван ровно один раз.
- `test/pages/notifications_settings_cubit_test.dart`, group
  `'NotificationsSettingsCubit — сеттеры'` (без номера UC), test
  `'changeDaysToVaccination/changeSendVaccinationNotificationOnEmail
  обновляют data'` — подтверждает шаги 2-3 (сеттеры меняют `state.data`
  независимо друг от друга).
- **TBD — теста нет** на гонку «`save()` вызван до завершения `load()`»
  (запись `null`/`false` поверх ранее сохранённого значения, см.
  «Альтернативные потоки») — ни один существующий тест не вызывает `save()`
  без предварительного awaited `load()`/сеттера, воспроизводящего реальный
  порядок эмитов `initial`→`loading`→…
- **TBD — теста нет** на то, что переключатели `_notifyOnNewMessages`/
  `_systemNotifications` не сохраняются — это чисто виджет-уровневое
  поведение (`_NotificationsSettingsPageState`), не покрытое ни одним
  widget-тестом в репозитории.

## Открытые вопросы и ограничения

- **Гонка между `load()` и преждевременным `save()` может стереть
  сохранённое значение `null`/`false` без ошибки.** Кнопка сохранения ничем
  не блокируется на время загрузки — см. «Альтернативные потоки». Не
  воспроизведено тестом; масштаб проблемы (насколько вероятно на реальных
  устройствах при обычной скорости Drift) не оценивался в рамках этого
  use-case.
- **Асимметрия дефолта `daysToVaccination` между кубитом и `HorizontalPicker`.**
  `NotificationsSettingsCubit.load()` использует дефолт `7`
  (`profileSettings?.daysToVaccination ?? 7`), тогда как сам виджет
  `HorizontalPicker(initialValue: state.data.daysToVaccination ?? 5, ...)`
  использует другой дефолт (`5`) на случай `null`. Наблюдаемого эффекта на
  сам `save()` (описываемый этим use-case) нет, поскольку к моменту
  штатного взаимодействия пользователя `daysToVaccination` уже не `null`
  (заполнено `load()`); расхождение проявляется только в уже описанном окне
  гонки выше. Не разбирается глубже в рамках этого файла.
- **Два декоративных переключателя на экране создают у пользователя
  ложное впечатление управляемых настроек**, хотя технически ничего не
  сохраняют и не читают ни при каком сценарии (см. «Альтернативные потоки»)
  — уже отмечено на уровне сущности
  ([ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)), здесь не
  переоткрывается как новая находка.
