# UC-168 — Чтение настроек уведомлений о вакцинации падает: экран без единого видимого сигнала остаётся с дефолтами, отличными от дефолтов кубита

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же экран, что описан в [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md) —
`NotificationsSettingsCubit.load()` читает локальные настройки уведомлений о
вакцинации при открытии экрана «Настройки уведомлений». Здесь описан путь,
когда это чтение реально бросает исключение — в отличие от
[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) (BOARD), где
технический `READ_ERROR` структурно недостижим, потому что репозиторий сам
глотает исключение, здесь исключение **никем не перехватывается** до
`try/catch` самого кубита — `SettingsRepository.getProfileSettings()` не
имеет собственного `try/catch`, и ни `BaseRepository`, ни `BaseDao` его не
оборачивают. Это полноценный, реально наблюдаемый в коде и в тесте `failure`-переход.

Наблюдаемый пользователем итог, тем не менее, почти так же тих, как в
BOARD-сценарии — но по другой причине. Ошибка ловится и логируется в
`Talker` (не пользователю — только в лог приложения), состояние кубита
переходит в отдельный, отличимый от остальных `failure`-вариант, но
`NotificationsSettingsPage` не показывает для него **ничего**: ни `SnackBar`,
ни текста, ни изменения вида экрана — `BlocConsumer.listener` реагирует
только на `saved`, `builder` не делает разбора по варианту состояния вовсе,
а читает только числовые/булевы поля `state.data`, у которых на `failure`
всегда `null`. Экран в итоге выглядит как обычная форма с независимыми
inline-дефолтами самого виджета (переключатель выключен, слайдер на 5 днях)
— **не совпадающими** с дефолтами, которые тот же кубит использует при
легитимном «настроек ещё нет» (`?? true`, `?? 7`, см.
[ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)). Дополнительно
проверена и задокументирована отдельным под-пунктом возможность тихой потери
ранее сохранённых настроек, если пользователь нажмёт «Сохранить» на этом
экране, не тронув ни один контрол — см. «Альтернативные потоки».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения.
**Уточнение, найденное при проверке кода этого сценария:** фактически
достижим только **авторизованный** пользователь. Единственная точка входа на
маршрут — блок `ProfileButton` с `l10n.profile_settings__notifications_settings`
внутри `_ProfileSettingsButtons`
(`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`),
а сам `_ProfileSettingsButtons` рендерится в `ProfileSettingsView.build` только
под условием `if (AppCacheService.isAuthorized())`
(`profile_settings_view.dart`) — гостю (`AppCacheService.isAuthorized() ==
false`, `lib/data/services/app_cache_service.dart`) этот блок вообще не
показывается на `ProfileSettingsPage`, кнопки «Настройки уведомлений» гость не
видит и нажать не может. Сам маршрут `Routes.notificationsSettings`
(`lib/pages/routes.dart`) при этом не имеет собственного `redirect`/guard на
уровне `go_router` — ограничение целиком на уровне видимости
кнопки-входа, не роутера. Это расходится с формулировкой «гость или
авторизованный одинаково, без route-guard», уже зафиксированной в
[UC-167](UC-167-ACTOR-5-EVT-84-ENT-21-READ_OK-IN-PROFILE.md),
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) и
[MOD-6](../modules/MOD-6-PROFILE.md) — все три говорят именно про отсутствие
guard'а на уровне роутера (что верно), не про фактическую недостижимость
кнопки-входа для гостя (что тоже верно, но отдельный факт). Эти три файла уже
заморожены и не редактируются здесь; расхождение зафиксировано в «Открытые
вопросы и ограничения» ниже, не как исправление их текста.

Действие пользователя, инициирующее сценарий: на `ProfileSettingsPage`
нажатие блока `l10n.profile_settings__notifications_settings` вызывает
`context.pushNamed2(Routes.notificationsSettings)` — единственная найденная в
коде точка входа на этот маршрут (`grep -rn "notificationsSettings" lib` вне
`routes.dart` даёт только `profile_settings_view.dart:171`). Полный путь —
`/profile/profile_settings/notifications_settings`
(`lib/pages/routes.dart`, вложенность `Routes.profile` → `Routes.profileSettings`
→ `Routes.notificationsSettings`).

## CURRENT

### Основной поток

1. Авторизованный пользователь на `ProfileSettingsPage` нажимает блок
   «Настройки уведомлений» (виден только при `AppCacheService.isAuthorized()
   == true`, см. «Пользователь») → `context.pushNamed2(Routes.notificationsSettings)`.
2. `NotificationsSettingsPage.build()` создаёт
   `BlocProvider(create: (context) => NotificationsSettingsCubit()..load())` —
   `load()` запускается сразу при создании кубита, синхронно с построением
   провайдера, без ожидания первого кадра и без отдельного пользовательского
   действия «обновить».
3. `NotificationsSettingsCubit.load()`: сначала
   `emit(NotificationsSettingsState.loading(NotificationSettingsData(daysToVaccination: state.data.daysToVaccination, sendVaccinationNotificationOnEmail: state.data.sendVaccinationNotificationOnEmail)))` —
   переносит вперёд то, что уже было в `state.data` (на первом входе — оба
   `null`, из `NotificationsSettingsState.initial(...)` в конструкторе).
4. `final profileSettings = await _settingsRepository.getProfileSettings();` →
   `SettingsRepository.getProfileSettings()`
   (`lib/repositories/settings/settings_repository.dart`) →
   `await dao.getAll()` → `ProfileSettingsDao extends BaseDao` →
   `BaseDao.getAll()` (`packages/sheep_farm_database/lib/entities/base_dao.dart`)
   → `selectCurrent().get()` — реальный Drift-запрос
   (`select(ProfileSettings).get()`) к физической sqlite3-БД через
   `getIt<AppDatabase>().getDaoByType<ProfileSettingsDao>()`
   (`lib/repositories/base_repository.dart`). Ни `SettingsRepository.getProfileSettings`,
   ни `BaseRepository`, ни `BaseDao.getAll` не оборачивают этот вызов в
   `try/catch` — это единственный слой, где вообще есть перехват, дальше по
   стеку. В этом сценарии вызов бросает исключение (диск/БД — например,
   `SqliteException`/обёрнутое drift-исключение при ошибке I/O, блокировке
   файла БД или порче данных).
5. Исключение всплывает необработанным до `try` в `NotificationsSettingsCubit.load()`
   (шаг 3) — единственного перехватчика на этом пути.
6. `catch (e)`: `getIt.get<Talker>().error(e.toString())` — логирование
   только во внутренний `Talker` приложения (видно разработчику через
   встроенный лог-вьюер/консоль, не пользователю никаким образом); затем
   `emit(NotificationsSettingsState.failure(NotificationSettingsData(daysToVaccination: null, sendVaccinationNotificationOnEmail: null), e.toString()))` —
   в отличие от эмиссии `loading` на шаге 3, здесь **не** переносится
   вперёд предыдущее значение `state.data` — оба поля жёстко захардкожены в
   `null`, независимо от того, что там было до вызова `load()`.
7. `BlocConsumer.listener` в `NotificationsSettingsPage`
   (`lib/pages/profile_settings/presentation/notifications_settings_page.dart`):
   `state.whenOrNull(saved: (_) { context.pop(); })` — ветки `failure` нет
   вовсе, значит на этот `emit` listener не делает ничего: ни `SnackBar`, ни
   навигации, ни любого другого побочного эффекта.
8. `BlocConsumer.builder` перестраивает тот же `Scaffold` без разбора по
   варианту состояния — читает только `state.data.sendVaccinationNotificationOnEmail ?? false`
   (переключатель `_SwitchRow` показывает выключенным) и
   `state.data.daysToVaccination ?? 5` (`HorizontalPicker.initialValue`
   показывает 5) — оба значения жёстко зашиты в самой странице, отдельно от
   дефолтов, которые `load()` использует при легитимном «настроек ещё нет,
   но чтение прошло успешно» (`?? true` / `?? 7`, см.
   [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md),
   [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md)).
9. Итог, видимый пользователем: экран выглядит как обычная форма с
   выключенным переключателем и слайдером на 5 днях — неотличимо от первого
   легитимного открытия без сохранённых настроек, за тем исключением, что
   легитимные дефолты другие (включено, 7 дней). Кнопка «Сохранить»
   (`BlackCircleButton` в `floatingActionButton`) отображается и активна как
   обычно — её видимость и доступность не зависят от варианта состояния.

### Альтернативные потоки

- **(а) Сохранение поверх непрочитанных данных тихо стирает ранее
  сохранённые настройки.** Если пользователь, видя неотличимый от
  легитимного пустого состояния экран, нажмёт «Сохранить», не тронув ни
  переключатель, ни слайдер: `save()` вызывает
  `_settingsRepository.saveProfileSettings(ProfileSettingsCompanion.insert(daysToVaccination: Value(state.data.daysToVaccination), sendVaccinationNotificationOnEmail: Value(state.data.sendVaccinationNotificationOnEmail ?? false)))` —
  при `state.data` из шага 6 это `Value(null)` и `Value(false)`. Внутри —
  `saveProfileSettings` → `dao.clearAndInsertAll([...])`
  (`BaseDao.clearAndInsertAll`) — полностью очищает таблицу `ProfileSettings`
  и вставляет одну строку `(daysToVaccination: NULL, sendVaccinationNotificationOnEmail: false)`,
  безвозвратно заменяя любые значения, реально сохранённые до этого
  отказавшего `load()` (например, `daysToVaccination: 3` — эта запись
  теряется, даже не будучи прочитанной). Эта операция — независимая,
  полностью успешная запись: кубит переходит в `saved`,
  `NotificationsSettingsPage`'s `listener` реагирует (`context.pop()`) как на
  штатное успешное сохранение — визуально неотличимо от случая, когда
  пользователь осознанно выключил уведомления и выбрал 5 дней. То есть
  техническая ошибка **чтения** приводит к тихой потере данных через
  отдельную, полностью штатную операцию **записи**.
- **(б) Асимметрия с соседним экраном того же модуля.** `KindsVisibilitySettingsPage`
  (`lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart`)
  — тот же паттерн `BlocProvider(create: (context) => XxxCubit()..load())` +
  `BlocConsumer` — явно обрабатывает `failure` в своём `listener`:
  `failure: (kinds, error) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppLocalizations.of(context)!.tr(error))))`.
  `NotificationsSettingsPage` не делает этого вовсе. Подтверждено чтением
  обоих файлов — это не общий паттерн проекта для подобных read-экранов
  `PROFILE`, а именно асимметрия внутри одного модуля между двумя похожими
  экранами.
- **(в) Правки, сделанные во время самого запроса, стираются тем же
  жёстко захардкоженным `null`/`null`.** Эмиссия `loading` на шаге 3
  переносит вперёд `state.data` (см. шаг 3), но эмиссия `failure` на шаге 6
  — нет: она безусловно конструирует `NotificationSettingsData(daysToVaccination: null, sendVaccinationNotificationOnEmail: null)`
  вне зависимости от того, что было в `state.data` к этому моменту.
  Структурно это означает, что если пользователь успеет вызвать
  `changeDaysToVaccination`/`changeSendVaccinationNotificationOnEmail` (оба
  доступны через контролы на экране без ожидания завершения `load()`) в
  узком окне между шагом 3 и срабатыванием `catch` на шаге 6 — например,
  ровно то время, пока СУБД пытается ответить и в итоге бросает
  исключение — эти правки не сохраняются нигде и полностью перекрываются
  `null`/`null`. Не воспроизведено эмпирически (требует гонки между
  пользовательским вводом и async-исключением), но прослежено статически по
  обоим методам кубита.

### Связанные сущности

- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) (ProfileSettings) —
  единственная сущность, которую этот сценарий пытается прочитать (`dao.getAll()`
  на таблице `ProfileSettings`) и не может; в альтернативном потоке (а) она
  же полностью перезаписывается (`clearAndInsertAll`) значениями `NULL`/`false`,
  независимо от содержимого до отказа.
- **`Kind`/`Kind.visible`** ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md),
  HANDBOOKS) — **не читается и не изменяется** этим сценарием: в отличие от
  сетевого push/pull (`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`,
  см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)), локальный
  `getProfileSettings()`, используемый `NotificationsSettingsCubit`, трогает
  только таблицу `ProfileSettings` — граница подтверждена чтением
  `SettingsRepository.getProfileSettings` (не вызывает ничего, связанного с
  `KindsRepository`).

### Бизнес-правила

- Дефолты `daysToVaccination: 7`/`sendVaccinationNotificationOnEmail: true`
  (см. [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md))
  применяются кубитом только на ветке «чтение прошло успешно, но строки в
  таблице нет» (`profileSettings == null`) — этот сценарий (`READ_ERROR`) на
  них не попадает вовсе; UI при этом всё равно показывает какие-то дефолты,
  но собственные, зашитые в `notifications_settings_page.dart` (`?? 5`,
  `?? false`), а не дефолты кубита.
- Нет автоматического ретрая и нет ручной кнопки «повторить» на экране —
  единственный способ вызвать `load()` снова — полностью покинуть экран
  (`Navigator.pop`) и открыть его заново, что пересоздаёт
  `NotificationsSettingsCubit` с нуля.
- Кнопка «Сохранить» не блокируется и не скрывается ни при `loading`, ни
  при `failure` — доступность записи не зависит от успеха предшествующего
  чтения.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (необработанное
исключение в `SettingsRepository.getProfileSettings()` → перехват и
логирование в `NotificationsSettingsCubit.load()` → `failure`-состояние без
какой-либо реакции UI, кроме собственных inline-дефолтов) подтверждён и
статическим чтением кода, и существующим тестом (см. «Связанные тесты»),
который мокает `SettingsRepository.getProfileSettings()` как бросающий
`Exception('db error')` — общего вида, не конкретно `SqliteException`;
реального отказа sqlite3-диска на уровне интеграционного/e2e-теста в
репозитории нет. Альтернативный поток (а) (тихая потеря ранее сохранённых
настроек через «Сохранить» сразу после отказавшего чтения) прослежен
статически по обоим методам кубита и репозитория, но не воспроизведён ни
одним тестом. Исправление (например, обработка `failure` в `listener` по
аналогии с `KindsVisibilitySettingsPage`, единые дефолты между кубитом и
страницей, блокировка «Сохранить» до успешного `load()`) в рамках этого
документирующего прохода не выполняется — это фиксация уже существующего
кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_cubit.dart` | `NotificationsSettingsCubit.load` | CURRENT | предмет основного потока — единственный перехватчик исключения на всём пути, `emit(failure(...))` жёстко на `null`/`null`, лог только в `Talker` |
| `lib/pages/profile_settings/cubit/notifications_settings/notifications_settings_state.dart` | `NotificationsSettingsState.failure`, `NotificationSettingsData` | CURRENT | форма `failure`-состояния — второй позиционный `error`, который UI не читает |
| `lib/pages/profile_settings/presentation/notifications_settings_page.dart` | `_NotificationsSettingsPageState.build`, `BlocConsumer.listener`/`.builder` | CURRENT | `listener` не содержит ветку `failure`; `builder` не различает варианты состояния, использует собственные `?? 5`/`?? false`, расходящиеся с дефолтами кубита; FAB «Сохранить» безусловен |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.getProfileSettings`, `.saveProfileSettings` | CURRENT | `getProfileSettings` — без своего `try/catch`, источник пробрасываемого исключения; `saveProfileSettings` — используется в альтернативном потоке (а), `dao.clearAndInsertAll` |
| `packages/sheep_farm_database/lib/entities/profile_settings/profile_settings_dao.dart` | `ProfileSettingsDao` | CURRENT | Drift DAO над таблицей `ProfileSettings`, без переопределений `BaseDao` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll`, `.clearAndInsertAll` | CURRENT | `getAll` — реальный Drift-запрос, источник технического исключения; `clearAndInsertAll` — полная перезапись таблицы без merge, используется в (а) |
| `lib/repositories/base_repository.dart` | `BaseRepository.dao` | CURRENT | `getIt<AppDatabase>().getDaoByType<BD>()` — плюс без собственного `try/catch` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build` (`if (AppCacheService.isAuthorized())`), `_ProfileSettingsButtons.onTap` | CURRENT | единственная найденная точка входа на маршрут — `context.pushNamed2(Routes.notificationsSettings)`; сам блок кнопок рендерится только для авторизованных, гостю не показывается |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.isAuthorized` | CURRENT | источник условия видимости кнопки-входа — `pref.getBool('is_authorized') ?? false` |
| `lib/pages/routes.dart` | `Routes.profile`/`.profileSettings`/`.notificationsSettings` | CURRENT | вложенность маршрута `/profile/profile_settings/notifications_settings` |
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `KindsVisibilitySettingsPage.build` (`listener`, ветка `failure`) | CURRENT | контрастный сосед в том же модуле — показывает `SnackBar` на `failure`, в отличие от этого сценария (см. «Альтернативные потоки», (б)) |

## Критерии приёмки

- Кнопка, ведущая на этот экран (`_ProfileSettingsButtons` →
  «Настройки уведомлений»), видна и доступна только при
  `AppCacheService.isAuthorized() == true`; сам маршрут
  `Routes.notificationsSettings` не проверяет авторизацию отдельно.
- Если `SettingsRepository.getProfileSettings()` (а конкретно —
  `dao.getAll()` внутри неё) бросает исключение любого типа,
  `NotificationsSettingsCubit.load()` перехватывает его в своём `catch`,
  вызывает `getIt.get<Talker>().error(e.toString())` ровно один раз и
  эмитит `NotificationsSettingsState.failure` с `NotificationSettingsData(daysToVaccination: null, sendVaccinationNotificationOnEmail: null)`
  и текстом исключения вторым параметром.
- `NotificationsSettingsPage`'s `BlocConsumer.listener` не производит
  никакого побочного эффекта (ни `SnackBar`, ни навигации) при получении
  `failure`-состояния — реагирует только на `saved`.
- `NotificationsSettingsPage`'s `BlocConsumer.builder` при `failure`
  показывает `_SwitchRow` выключенным (`?? false`) и `HorizontalPicker` со
  значением 5 (`?? 5`) — независимо от того, какие значения были в таблице
  `ProfileSettings` до отказавшего чтения.
- Кнопка «Сохранить» остаётся видимой и активной при `failure`; при нажатии
  без предварительного изменения переключателя/слайдера вызывает
  `saveProfileSettings` с `daysToVaccination: null`, `sendVaccinationNotificationOnEmail: false`
  и переводит таблицу `ProfileSettings` в это состояние через
  `clearAndInsertAll`, независимо от того, что было сохранено ранее.
- Повторное чтение возможно только через пересоздание
  `NotificationsSettingsCubit` (выход с экрана и повторный вход) — в самом
  коде страницы нет отдельного триггера повтора `load()`.

## Связанные тесты

`test/pages/notifications_settings_cubit_test.dart`, группа
`'UC-168 — NotificationsSettingsCubit.load ERROR'`, тест `'ошибка
репозитория -> failure, залогировано'`: мокает
`repository.getProfileSettings()` как бросающий `Exception('db error')`,
проверяет `_isFailure(cubit.state)` и
`verify(() => getIt<Talker>().error(any())).called(1)`.

Это покрывает только сам кубит. **TBD — теста нет** на:

- поведение `NotificationsSettingsPage` при `failure` (отсутствие
  `SnackBar`/любой другой реакции `listener`, отображение `builder`'ом
  значений `?? 5`/`?? false`) — виджет-теста на этот экран в репозитории нет
  вовсе (`find test -iname "*notifications_settings*"` находит только файл
  теста кубита);
- альтернативный поток (а) — тихую потерю ранее сохранённых настроек при
  нажатии «Сохранить» сразу после отказавшего `load()`;
- альтернативный поток (в) — стирание правок, сделанных пользователем в
  окне между `loading` и `failure`.

## Открытые вопросы и ограничения

- **Точка входа на этот экран фактически недостижима для гостя, хотя три
  уже замороженных документа ([UC-167](UC-167-ACTOR-5-EVT-84-ENT-21-READ_OK-IN-PROFILE.md),
  [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md),
  [MOD-6](../modules/MOD-6-PROFILE.md)) описывают весь `PROFILE` как «без
  route-guard по авторизации, гость и авторизованный проходят один и тот же
  код».** Оба утверждения верны одновременно и не противоречат друг другу
  буквально — на уровне `go_router` действительно нет `redirect`/guard для
  `Routes.notificationsSettings`, но единственная кнопка, которая на него
  ведёт (`_ProfileSettingsButtons` в `profile_settings_view.dart`), обёрнута в
  `if (AppCacheService.isAuthorized())` и гостю просто не рисуется. Итог —
  гость не может дойти сюда обычной навигацией, только прямым deep-link'ом
  на именованный маршрут, если такой механизм в принципе используется в
  проекте (не проверялось в рамках этого прохода). Сам факт этого прохода —
  документирование `READ_ERROR`, а не пересмотр `Пользователь` для уже
  замороженного `UC-167`/`ACTOR-5`/`MOD-6`; несовпадение стоит свести к
  единой формулировке в следующем проходе по модулю (по правилам пайплайна —
  правкой не самих замороженных файлов, а решением на уровне ревью PRD).
- **Отсутствие реакции UI на `failure` — недосмотр или намеренное решение?**
  Ничем в коде/комментариях не зафиксировано. Контраст с
  `KindsVisibilitySettingsPage` (см. «Альтернативные потоки», (б)) —
  практически идентичный по структуре экран в том же модуле явно показывает
  ошибку пользователю — говорит скорее в пользу недосмотра, чем осознанного
  решения именно для этого экрана.
- **Два независимых набора дефолтов для одного и того же поля.** Кубит
  использует `?? 7`/`?? true` (документировано также в
  [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md)
  как узкое расхождение «до завершения `load()`»); страница использует
  `?? 5`/`?? false`. Для `READ_ERROR` это расхождение не узкое и не
  временное — `state.data` остаётся `null`/`null` до тех пор, пока
  пользователь не покинет и не откроет экран заново, то есть до конца жизни
  этого экземпляра экрана.
- **Возможность тихой потери данных через «Сохранить» после отказавшего
  чтения (альтернативный поток (а)) не имеет никакой защиты** — ни
  подтверждающего диалога, ни блокировки кнопки, ни проверки, было ли
  чтение успешным, перед тем как разрешить запись.
- Реальный технический источник исключения (диск, блокировка файла БД,
  повреждение данных) не воспроизведён эмпирически — и тест, и это
  документирование опираются на обобщённый `Exception`, подставленный в
  мок репозитория, а не на конкретный класс исключения, который в
  реальности бросил бы `drift`/`sqlite3`.
