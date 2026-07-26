# UC-171 — Пользователь открывает «Видимость видов животных», список видов загружается успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь открывает экран «Видимость видов»
(`/profile/work_settings/kinds_visibility_settings`) и видит полный список
видов животных ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md),
таксономия — HANDBOOKS) с текущим значением флага `Kind.visible` (R65) у
каждого, чтобы затем включить/выключить показ отдельных видов в списках
выбора приложения (сохранение — отдельное событие,
[EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md), не этот
сценарий). Чтение строго локальное (Drift), без сетевого вызова.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, разницы для этого сценария нет: маршрут не имеет
route-guard по авторизации, как и весь модуль `PROFILE`, см.
[MOD-6](../modules/MOD-6-PROFILE.md)).

## CURRENT

### Основной поток

1. Пользователь находится на `ProfilePage` → `ProfileView` → нажимает
   `ProfileButton` с текстом `l10n.profile_settings__work_settings`
   (`lib/pages/profile/presentation/widgets/profile/profile_view.dart`) →
   `context.pushNamed2(Routes.workSettings)` → `WorkSettingsPage`
   (`lib/pages/profile_settings/presentation/work_settings_page.dart`).
2. На `WorkSettingsPage` пользователь нажимает `WorkSettingsItem` с текстом
   `l10n.profile_settings__kinds_visibility_settings` → `onTap: () =>
   context.pushNamed2(Routes.kindsVisibilitySettings)`.
   `Routes.kindsVisibilitySettings` вложен под `Routes.workSettings` (сам
   вложен под `Routes.profile`) в `routes.dart` — итоговый путь
   `/profile/work_settings/kinds_visibility_settings`.
3. `KindsVisibilitySettingsPage.build`
   (`lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart`)
   создаёт `BlocProvider` с `create: (context) =>
   KindsVisibilitySettingsCubit()..load()` — `load()` вызывается сразу же
   при создании кубита, без отдельного действия пользователя на этом
   экране.
4. Конструктор `KindsVisibilitySettingsCubit`
   (`lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart`)
   стартует с `KindsVisibilitySettingsState.initial(kinds: [])`.
5. `load()` синхронно (до первого `await`) эмитит
   `KindsVisibilitySettingsState.loading(kinds: state.kinds)`, копируя
   текущий (на этот момент ещё пустой) список без изменений.
6. `final kinds = (await _kindsRepository.getAll())..sort((a, b) =>
   a.name.compareTo(b.name));` — `KindsRepository.getAll()`
   (`lib/repositories/kind/kinds_repository.dart`) не переопределён в самом
   репозитории, наследуется от `BaseRepository<KindsDao, Kind,
   $KindsTable>.getAll()` (`lib/repositories/base_repository.dart`) →
   `dao.getAll()` → `BaseDao.getAll()` (`packages/sheep_farm_database/lib/entities/base_dao.dart`)
   → `selectCurrent().get()` — `SELECT * FROM kinds` целиком, **без**
   `WHERE`-условия по `visible` и без какой-либо иной фильтрации. В этом
   сценарии запрос завершается без исключения и возвращает все строки
   таблицы `Kinds`, включая уже скрытые пользователем ранее (`visible ==
   false`) — иначе их нельзя было бы снова включить с этого экрана.
7. `load()` эмитит `KindsVisibilitySettingsState.loaded(kinds: kinds)` —
   список уже отсортирован по имени на предыдущем шаге (сортировка через
   `List.sort`, обычное лексикографическое сравнение Dart-строк, не
   локале-зависимое).
8. Сразу же, без единого `await` между шагами, `load()` эмитит
   `KindsVisibilitySettingsState.loaded(kinds: kinds)` **второй раз** —
   `emit(...)` буквально продублирован в коде метода, оба вызова передают
   одну и ту же переменную `kinds` (один и тот же объект `List<Kind>`, не
   две отдельные копии). Наблюдаемых отличий у второго эмита от первого
   нет — данные идентичны по значению и по ссылке.
9. `KindsVisibilitySettingsPage`'s `BlocConsumer` перестраивается: `listener`
   обрабатывает только `saved`/`failure` через `state.whenOrNull(...)` —
   `loaded` в `listener` не участвует вообще, поэтому дублирующий эмит не
   вызывает никакого дополнительного побочного эффекта (снекбар, навигация
   и т.п.), только лишний холостой `builder`-ребилд с тем же деревом
   виджетов. `builder` рендерит `KindsVisibilitySettingsListWidget(kinds:
   kinds, onChanged: ..., onSelectAll: ..., onDeselectAll: ...)`.
10. Пользователь видит: заголовок `CustomAppBar` с
    `l10n.profile_settings__kinds_visibility_settings`; сверху — две кнопки
    `BlackCircleButton.secondary` (`l10n.deselect_all` /
    `l10n.select_all`); список `ListView.separated` из `Switcher`-строк, по
    одной на вид, с `title: kind.name` и `value: kind.visible`; внизу —
    плавающая кнопка `l10n.save`. Переключение отдельного/всех
    видов и сохранение — отдельные действия/события
    ([EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md)), не
    покрываются этим `READ_OK`-сценарием.

### Альтернативные потоки

- **В таблице `Kinds` нет ни одной строки** — `getAll()` возвращает `[]`,
  сортировка no-op, `loaded` эмитится (дважды, как в основном потоке) с
  пустым списком; `ListView.separated` с `itemCount: 0` рендерит пустую
  прокручиваемую область без отдельного текста-заглушки «пусто» — то же
  визуальное поведение, что у `loading`/`initial` (тот же
  `Column`/`Expanded`, просто без строк внутри `ListView`), никакого
  специального empty-state экрана нет.
- **`_kindsRepository.getAll()` бросает исключение** — метод `load()`
  не оборачивает вызов в `try/catch`, а сам кубит создаётся выражением
  `KindsVisibilitySettingsCubit()..load()` внутри `create:` без `await` со
  стороны вызывающего кода — исключение не имеет обработчика на своём
  пути и всплывает как необработанная ошибка в `Future`, возвращаемом
  `load()` (в зависимости от окружения — необработанный `Future`-error в
  Zone/тесте, либо перехват `FlutterError`/Zone-обработчиком приложения на
  проде). Кубит при этом никогда не эмитит `loaded` — состояние застревает
  на `loading` (или на `initial`, если ошибка возникла ещё до первого
  `emit`), и `KindsVisibilitySettingsPage` показывает
  `KindsVisibilitySettingsLoadingWidget` (спиннер) бессрочно, т.к. и
  `initial`, и `loading` рендерят один и тот же виджет. Технический
  `READ_ERROR` для этого события в коде не имеет собственного состояния
  (в отличие от `save()`, где `failure` — осознанный REJECTED-путь для
  бизнес-правила «хотя бы один вид виден», не для ошибки чтения) — не этот
  сценарий, см. «Открытые вопросы».

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) — читается целиком, без фильтра по `visible`; не изменяется
  этим сценарием (изменение — `toggleKindVisibility`/
  `toggleAllKindsVisibility`/`save()`, часть
  [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md), не этого
  события).

### Бизнес-правила

- Экран всегда показывает полный каталог видов, включая уже скрытые —
  иначе скрытый вид нельзя было бы снова сделать видимым с этого же экрана.
- Сортировка — только на уровне представления (в кубите, после чтения из
  БД), не влияет на хранимые значения и не персистится отдельно.
- Чтение не инициирует ни push, ни pull к серверу — синхронизация
  `Kind.visible` (как часть общего контракта с
  [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md),
  `SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`) выполняется
  только как часть отдельного sync-прохода
  ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md),
  [MOD-6](../modules/MOD-6-PROFILE.md), «Граница»), не при открытии этого
  экрана — то, что видит пользователь здесь, отражает состояние локальной
  БД на момент открытия.
- `Kind.visible` дополнительно редактируется независимым, отдельно
  написанным путём при онбординге первой фермы (`FarmCreateCubit`, шаг
  `FarmCreateStep.kindsVisibility`, тем же
  `KindsRepository.getAll`/`updateAll`, модуль `FARM`, см.
  [UC-21](UC-21-ACTOR-1-EVT-10-ENT-9-CREATE_OK-IN-FARM.md)) — этот экран
  просто перечитывает таблицу заново, поэтому покажет любое значение,
  сохранённое последним по любому из двух путей; ни один из путей не знает
  о незавершённых изменениях другого (нет ни блокировки, ни
  предупреждения о конфликте).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и достижим с единственной точки
входа (`ProfilePage` → «Рабочие настройки» → `WorkSettingsPage` → «Видимость
видов»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileButton` («Рабочие настройки») | CURRENT | первый шаг маршрута — переход на `Routes.workSettings` |
| `lib/pages/profile_settings/presentation/work_settings_page.dart` | `WorkSettingsPage`, `WorkSettingsItem` («Видимость видов») | CURRENT | точка входа именно на этот экран — `context.pushNamed2(Routes.kindsVisibilitySettings)` |
| `lib/pages/routes.dart` | `Routes.profile`, `Routes.workSettings`, `Routes.kindsVisibilitySettings` | CURRENT | вложенность маршрута — итоговый путь `/profile/work_settings/kinds_visibility_settings` |
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `KindsVisibilitySettingsPage.build`, `KindsVisibilitySettingsListWidget`, `KindsVisibilitySettingsLoadingWidget` | CURRENT | создаёт `KindsVisibilitySettingsCubit()..load()`; `listener` обрабатывает только `saved`/`failure`; `builder` рендерит список/спиннер по состоянию |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.load` | CURRENT | основной метод сценария — читает `KindsRepository.getAll()`, сортирует, эмитит `loaded` дважды подряд с одним и тем же списком |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_state.dart` | `KindsVisibilitySettingsState` (freezed union `initial`/`loading`/`loaded`/`saved`/`failure`) | CURRENT | состояние экрана |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository` | CURRENT | не переопределяет `getAll()` — используется унаследованный из `BaseRepository` |
| `lib/repositories/base_repository.dart` | `BaseRepository.getAll` | CURRENT | `dao.getAll()`, без фильтров |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll` | CURRENT | `selectCurrent().get()` — `SELECT * FROM kinds` целиком |
| `packages/sheep_farm_database/lib/entities/kind/kinds.dart` | `Kinds`, `Kind` | CURRENT | таблица/модель, `visible` — `BoolColumn`, default `true` |
| `lib/injection_container.dart` | `getIt.registerLazySingleton<KindsRepository>` | CURRENT | регистрация DI, используемая `KindsVisibilitySettingsCubit._kindsRepository` |

## Критерии приёмки

- Открытие экрана вызывает `KindsVisibilitySettingsCubit.load()` ровно один
  раз, в момент создания кубита (без отдельного действия пользователя).
- Если `KindsRepository.getAll()` завершается успешно — итоговое состояние
  `KindsVisibilitySettingsState.loaded` содержит **все** строки таблицы
  `Kinds`, включая скрытые (`visible == false`), отсортированные по `name`.
- Пустая таблица `Kinds` также приводит к `loaded` (с пустым списком), не к
  `failure`.
- Сценарий не делает сетевых запросов.
- `state.kinds` в итоговом `loaded`-состоянии — тот же список (по ссылке),
  что был получен из `getAll()` и отсортирован; повторный `emit` того же
  `loaded` не создаёт новый список и не меняет наблюдаемые данные.

## Связанные тесты

`test/pages/kinds_visibility_settings_cubit_test.dart`, группа `'UC-171 —
KindsVisibilitySettingsCubit.load'` (имя группы — старая нумерация, до
переименования под текущие id, см. предисловие задачи; анкер `grep -r
"UC-171" test/` работает уже сегодня):

- `'загружает и сортирует kinds по имени'` — мокает `repository.getAll()`
  результатом из двух видов в «неправильном» порядке (`Собака` id 1,
  `Баран` id 2), вызывает `cubit.load()`, проверяет
  `_isLoaded(cubit.state) == true` и
  `cubit.state.kinds.map((k) => k.name) == ['Баран', 'Собака']`.

Тест проверяет только итоговое состояние после `await cubit.load()`
целиком, не количество/последовательность промежуточных эмитов — **TBD —
теста нет** отдельно на то, что `loaded` эмитится дважды подряд (сам
дублирующий эмит из «Основной поток», шаг 8, ничем не покрыт: финальное
состояние идентично что при одном, что при двух `emit`, так что и тест, и
пользовательский интерфейс не различают эти два случая). Также **TBD —
теста нет** ни на пустую таблицу (`getAll()` → `[]`), ни на исключение из
`getAll()` (см. «Альтернативные потоки»), ни виджет-теста самой
`KindsVisibilitySettingsPage`/`KindsVisibilitySettingsListWidget` (`find
test -iname "*kinds_visibility*"` находит только этот один
cubit-тест-файл).

## Открытые вопросы и ограничения

- **Дублирующий `emit(loaded)` — не проверено, намеренно ли это или
  копипаст-артефакт.** Функционально безвреден (тот же список по ссылке,
  `listener` не реагирует на `loaded`), но лишний ребилд `BlocConsumer` на
  каждое открытие экрана ничем не документирован как сознательный приём
  (например, «форсировать перерисовку»/debounce) — выглядит как случайно
  продублированная строка кода.
- **Незащищённое исключение в `getAll()` не имеет отдельного
  `READ_ERROR`-состояния.** В отличие от `NotificationsSettingsCubit`
  (сосед по модулю, `failure` — осознанный `READ_ERROR`), здесь
  единственное состояние `failure` существует только для бизнес-правила
  «нет ни одного видимого вида» при `save()` (REJECTED), не для сбоя
  чтения — технический сбой `getAll()` оставляет экран в вечном
  `loading`, не сообщая пользователю ничего. Не проверено, есть ли
  отдельный запланированный use-case на этот технический путь для
  [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md).
- **Два независимых, не связанных друг с другом кода правят один и тот же
  факт (`Kind.visible`)** — этот экран и шаг `kindsVisibility` мастера
  создания первой фермы (`FarmCreateCubit`,
  [UC-21](UC-21-ACTOR-1-EVT-10-ENT-9-CREATE_OK-IN-FARM.md)). Ни блокировки,
  ни предупреждения о том, что значение могло быть изменено другим путём
  между открытием и сохранением, нет ни в одном из двух мест — отмечено
  как находка на уровне границы модуля
  ([MOD-6](../modules/MOD-6-PROFILE.md), «Граница»), не переспецифицируется
  повторно в `FARM`.
- Не проверено эмпирически на реальном устройстве (например, поведение при
  очень большом каталоге видов/задержке Drift-запроса) — вывод сделан
  статическим чтением кода `KindsVisibilitySettingsCubit`, подтверждён
  только модульным тестом уровня кубита без реального виджетного дерева.
