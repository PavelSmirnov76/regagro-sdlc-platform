# UC-173 — Пользователь сохраняет видимость видов животных: весь каталог `Kind` перезаписывается локально одной транзакцией

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Пользователь на экране «Видимость видов»
(`/profile/work_settings/kinds_visibility_settings`) переключает видимость
отдельных видов животных (`Kind.visible`, R65) и/или использует «Выбрать
все»/«Снять все», затем нажимает «Сохранить»; в БД остаётся хотя бы один
видимый вид, поэтому сохранение проходит успешно —
`KindsVisibilitySettingsCubit.save()` записывает результат в локальную
Drift-таблицу `Kinds`. Happy-path сценарий события
[EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md)
(`kind_visibility.saved`). Отправка на сервер этим сценарием не
выполняется — это отдельный, условный шаг более позднего sync-прохода (см.
«Открытые вопросы» — там же задокументирован риск, что тот же sync-проход
способен молча стереть только что сохранённый здесь результат).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость и авторизованный обрабатываются одинаково: маршрут
`kinds_visibility_settings` не имеет route-guard по авторизации (весь модуль
`PROFILE`, см. [MOD-6](../modules/MOD-6-PROFILE.md)); ни
`KindsVisibilitySettingsPage`, ни `KindsVisibilitySettingsCubit` нигде не
проверяют `AppCacheService.isAuthorized()`.

## CURRENT

### Основной поток

1. Пользователь уже находится на `KindsVisibilitySettingsPage`, список видов
   загружен — `KindsVisibilitySettingsState.loaded(kinds: ...)` с полным
   каталогом `Kind` (включая уже скрытые вида, `visible == false`). Сама
   загрузка — отдельное событие
   ([EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md),
   [UC-171](UC-171-ACTOR-5-EVT-86-ENT-3-READ_OK-IN-PROFILE.md)), здесь не
   переспецифицируется.
2. Пользователь переключает `Switcher`-строку одного вида (`title:
   kind.name`, `value: kind.visible`) — `onChanged: (_) =>
   onChanged(kind)` (`kinds_visibility_settings_page.dart`) вызывает
   `context.read<KindsVisibilitySettingsCubit>().toggleKindVisibility(kind)`.
3. `toggleKindVisibility(kind)`: `index = state.kinds.indexWhere((k) =>
   k.id == kind.id)`; в этом сценарии индекс найден. `updatedKind =
   kind.copyWith(visible: !kind.visible)` — инвертирует значение того
   объекта `Kind`, что был передан из виджета (значение из `state` на
   момент отрисовки конкретной строки списка), не перечитывает
   `state.kinds[index]` заново — в этом сценарии это один и тот же объект,
   разницы не возникает. `updatedKinds = List<Kind>.from(state.kinds)..
   [index] = updatedKind`; `emit(KindsVisibilitySettingsState.loaded(kinds:
   updatedKinds))` — чисто в памяти кубита, ни один DAO/репозиторий не
   вызывается.
4. И/или пользователь нажимает «Снять все»/«Выбрать все»
   (`BlackCircleButton.secondary`, `l10n.deselect_all`/`l10n.select_all`) —
   `onDeselectAll: () => ...toggleAllKindsVisibility(false)` /
   `onSelectAll: () => onSelectAll(true)` (типизирован как
   `ValueChanged<bool>` = сам метод `toggleAllKindsVisibility`).
   `toggleAllKindsVisibility(value)`: `state.kinds.map((kind) =>
   kind.copyWith(visible: value)).toList()`, `emit(loaded(kinds:
   updatedKinds))` — тоже полностью в памяти, применяется сразу ко всему
   списку разом.
5. Шаги 2-4 могут повторяться в любом порядке и количестве — каждый вызов
   синхронно обновляет `state.kinds`, не обращаясь к БД.
6. К моменту сохранения хотя бы один `Kind` в `state.kinds` остаётся с
   `visible == true` (условие этого сценария, `UPDATE_OK`, а не `REJECTED`
   — см. «Альтернативные потоки»). Пользователь нажимает кнопку
   `RElevatedButton` с текстом `l10n.save` (`floatingActionButton`,
   отрисовывается безусловно вне зависимости от состояния кубита) —
   `onTap: () { context.read<KindsVisibilitySettingsCubit>().save(); }`.
7. `save()`: проверяет `if (!state.kinds.any((e) => e.visible))` — в этом
   сценарии условие ложно, ветка отказа (см. «Альтернативные потоки») не
   выполняется.
8. `await _kindsRepository.updateAll(state.kinds)` —
   `state.kinds` здесь это **весь** каталог видов, изначально загруженный
   `load()` (`getAll()`, без фильтра), а не только те записи, чей `visible`
   реально изменился шагами 2-4. `KindsRepository`
   (`lib/repositories/kind/kinds_repository.dart`) не переопределяет
   `updateAll` — используется унаследованный
   `BaseRepository<KindsDao, Kind, $KindsTable>.updateAll(list) =>
   dao.updAll(list)` (`lib/repositories/base_repository.dart`).
9. `BaseDao.updAll(list)`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) оборачивает
   весь вызов в одну Drift `transaction()`; внутри — цикл `for (final i in
   list) { await upd(i); }`, где `upd(i) = updateCurrent().replace(item)`.
   `UpdateStatement.replace` (drift, `query_builder/statements/update.dart`)
   — операция «заменить всю строку по первичному ключу»: строится `WHERE`
   по `id` записи и обновляются **все** колонки значениями текущего
   Dart-объекта (`id`/`name`/`animalTypeId`/`visible`), а не только
   `visible`. Итог: **N отдельных `UPDATE ... WHERE id = ?`** (N = размер
   всего каталога, не только реально изменённых строк), выполненных внутри
   одной транзакции — не единый bulk-SQL-оператор.
10. Исключений в этом сценарии нет → `save()` продолжается после `await` и
    эмитит `KindsVisibilitySettingsState.saved(kinds: state.kinds)`.
11. `KindsVisibilitySettingsPage`'s `BlocConsumer.listener`:
    `state.whenOrNull(saved: (_) { ScaffoldMessenger.of(context)
    .showSnackBar(SnackBar(content: Text(AppLocalizations.of(context)!
    .profile_settings__successfully_saved))); context.pop(); })` —
    пользователь видит снекбар об успехе (сырой `ScaffoldMessenger`, не
    через хелпер `lib/widgets/app_snackbar.dart`, предписанный конвенцией
    проекта — см. «Открытые вопросы»), затем экран закрывается
    (`Navigator.pop`), возвращая пользователя на `WorkSettingsPage`.
12. Отправка изменения на сервер этим методом не выполняется. Push
    (`SettingsRepository.setSettingToSHTP()`, отправляет и `ProfileSettings`
    (R64), и текущий список видимых `Kind` через `_getVisibleKindIds()` =
    `_kindsRepository.getAllIdsByFilters(visible: true)`) вызывается только
    при следующем `DataUpdateStartAll` с `event.isUpdateData == true` —
    единственная точка вызова во всей кодовой базе, кнопка ручного
    «Обновить данные» на экране «В работе» (см.
    [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)). До этого
    момента результат этого сценария существует только в локальной БД — и
    подвергается риску, задокументированному в «Открытые вопросы».

### Альтернативные потоки

- **`toggleKindVisibility` с id, отсутствующим в `state.kinds` — тихий
  no-op.** `indexWhere` возвращает `-1`, метод возвращает управление сразу,
  без `emit` — переключатель на экране не меняется, ошибки не показывается
  (подтверждено тестом `'неизвестный id -> no-op'`).
- **«Сохранить» нажато до/во время первого `load()`.** Кнопка сохранения
  ничем не блокируется на время загрузки (в отличие от чтения — см. также
  аналогичную находку [UC-169](UC-169-ACTOR-5-EVT-85-ENT-21-UPDATE_OK-IN-PROFILE.md)
  для `NotificationsSettingsCubit`). Если `save()` вызван, пока
  `state.kinds` ещё `[]` (`initial`/`loading`) — `[].any((e) => e.visible)`
  равно `false`, поэтому выполняется ветка отказа (см. ниже), а не эта.
  **Отличие от аналогичной гонки у уведомлений: здесь гонка не может молча
  испортить данные** — то же условие «хотя бы один вид виден», которое
  реализует REJECTED-бизнес-правило, срабатывает и на пустом списке, так
  что `updateAll([])` в этом случае вообще не вызывается.
- **`state.kinds.any((e) => e.visible)` ложно — REJECTED, отдельный
  сценарий, не этот.** Наступает при явном «Снять все», при ручном снятии
  видимости с каждого вида по отдельности, или в гонке выше. `save()`
  берёт `if`-ветку: `emit(KindsVisibilitySettingsState.failure(kinds:
  state.kinds, error: 'key'))`, `updateAll` не вызывается вообще. Отдельно
  задокументированный дефект этой ветки (уже зафиксирован на уровне
  [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md)): `error:
  'key'` — буквальная строка, не существующий ключ локализации;
  `AppLocalizationsExtension.tr()` (`lib/l10n/app_localization.dart`)
  возвращает вход без изменений, если ни один `case` в его `switch` не
  совпал, — пользователь в снекбаре (`failure: (kinds, error) =>
  ...Text(AppLocalizations.of(context)!.tr(error))`) видит слово «key», а
  не осмысленное сообщение. Не переспецифицируется здесь как отдельный
  use-case (эта спека покрывает только `UPDATE_OK`).
- **Строка `Kind`, чьи `name`/`animalTypeId` изменились в БД параллельно
  (например, во время sync-прохода, между открытием этого экрана и
  нажатием «Сохранить»), молча откатывается к значению на момент `load()`.**
  Поскольку `updAll`/`replace` перезаписывает всю строку (шаг 9 основного
  потока), а не только колонку `visible`, любое такое параллельное
  изменение конкретного `Kind` будет затёрто устаревшими `name`/
  `animalTypeId`, всё ещё лежащими в `state.kinds` этого кубита. Не
  воспроизведено тестом — вывод сделан статическим чтением
  `UpdateStatement.replace` (см. «Технические зависимости»).

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) — единственная сущность, чьё состояние меняется: локальная
  таблица `Kinds` обновляется целиком (каждая строка — отдельным `UPDATE`
  внутри одной транзакции), не только строки с реально изменённым
  `visible`.
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — не читается и не пишется этим сценарием напрямую, но
  делит с `Kind.visible` один и тот же сетевой контракт при последующем
  push/pull (`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`,
  один эндпоинт `user-settings/store`/`get-settings` на оба факта, R64+R65).
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не участвует:
  ни `Kinds`, ни вызванный здесь код не хранят и не проверяют
  идентификатор пользователя.

### Бизнес-правила

- Сохранение отклоняется (REJECTED, не этот сценарий), если после всех
  переключений не остаётся ни одного видимого вида — единственное
  бизнес-правило, охраняющее это событие.
- Сохранение — не diff-апдейт: весь загруженный каталог `Kind`
  перезаписывается построчно (`updAll` → цикл `replace` по каждой записи),
  включая записи, чей `visible` фактически не менялся пользователем в этой
  сессии экрана.
- `save()` никогда сам не инициирует сетевой запрос — push на сервер
  выполняется отдельно, системным актором
  ([ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)) и только при
  `DataUpdateStartAll(isUpdateData: true)` — см. шаг 12 основного потока и
  «Открытые вопросы» ниже.
- **Тот же факт (`Kind.visible`) редактируется вторым, независимо
  написанным путём** — шаг `FarmCreateStep.kindsVisibility` мастера
  создания первой фермы (`FarmCreateCubit.toggleKindVisibility`/
  `.toggleAllKindsVisibility`/`.saveKinds`,
  `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart`,
  модуль `FARM`, уже специфицирован —
  [UC-21](UC-21-ACTOR-1-EVT-10-ENT-9-CREATE_OK-IN-FARM.md)). Логика
  toggle почти идентична (тот же паттерн `indexWhere` + `copyWith` +
  замена элемента списка), но реализована отдельно, в другом кубите, без
  общего кода. Разница между двумя путями: `FarmCreateCubit.saveKinds()`
  **не имеет собственной REJECTED-проверки** «хотя бы один вид виден» —
  она там реализована только косвенно, через `canProceedToNextStep()`
  (`case FarmCreateStep.kindsVisibility: return state.kinds.any((k) =>
  k.visible)`), которая гейтит кнопку «Далее»/«Сохранить» мастера, а не сам
  вызов `saveKinds()`; `updateAll` в обоих путях — один и тот же метод
  `KindsRepository.updateAll`. Ни один из двух путей не знает о
  незавершённых изменениях другого — конфликт между ними не
  обнаруживается и не предотвращается.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (переключение видимости в памяти, батч-обновление
`Kinds` через `updateAll`, переход в `saved`, снекбар + закрытие экрана)
полностью реализован и подтверждён тестом на уровне кубита (см. «Связанные
тесты»). Находки в «Альтернативные потоки»/«Открытые вопросы» описывают
неожиданное, но не падающее с ошибкой поведение существующего кода — они не
блокируют основной поток.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `KindsVisibilitySettingsPage.build`, `KindsVisibilitySettingsListWidget` (`Switcher.onChanged`, `BlackCircleButton.secondary` select/deselect all, `RElevatedButton` save), `BlocConsumer.listener` | CURRENT | UI-триггеры (`toggleKindVisibility`/`toggleAllKindsVisibility`/`save`), реакция на `saved` (снекбар через `ScaffoldMessenger` + `context.pop()`) и `failure` (снекбар с `tr(error)`) |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.toggleKindVisibility`, `.toggleAllKindsVisibility`, `.save` | CURRENT | сборка обновлённого `state.kinds`, бизнес-правило «хотя бы один видимый», вызов репозитория, эмиты `loaded`/`saved`/`failure` |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_state.dart` | `KindsVisibilitySettingsState` (`.loaded`, `.saved`, `.failure`) | CURRENT | freezed-состояния экрана, общее поле `kinds` |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository` | CURRENT | не переопределяет `updateAll` — используется унаследованный из `BaseRepository`; также `getAllIdsByFilters`, используемый последующим push (шаг 12) |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | `dao.updAll(list)` — единственная точка вызова из кубита |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `.upd`, `.updateCurrent` | CURRENT | транзакция + цикл индивидуальных `replace()`-обновлений, не единый bulk SQL |
| `packages/sheep_farm_database/lib/entities/kind/kinds.dart` | `Kinds`, `Kind`, `KindsDtoMapper.toModel` | CURRENT | таблица/модель; `toModel()` жёстко проставляет `visible: true` для строк, приходящих с сервера (см. «Открытые вопросы») |
| `packages/sheep_farm_database/lib/database/database.g.dart` | `Kind` (сгенерированный `DataClass`/`Insertable`) | CURRENT (генерируется) | `copyWith`, используемый обоими toggle-методами; полная замена строки через `UpdateStatement.replace` |
| `lib/injection_container.dart` | `getIt.registerLazySingleton<KindsRepository>` | CURRENT | DI-регистрация, используемая кубитом |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadDirectories`, `._syncAuthData`, `.updateAndSyncRegagro`, `._syncAllData` | CURRENT | полный sync-проход, в котором задействован результат этого сценария — см. «Открытые вопросы» |
| `lib/repositories/settings/settings_repository.dart` | `SettingsRepository.setSettingToSHTP`, `.getSettingFromSHTP`, `._setVisibleKinds`, `._getVisibleKindIds` | CURRENT | push/pull `Kind.visible` на/с сервера, единственный механизм, способный восстановить сохранённое здесь значение после сброса `loadDirectories()` |
| `lib/repositories/auth/auth_repository.dart` | (логаут/удаление аккаунта) `AppCacheService.clearDirectoriesLastSyncDate` | CURRENT | сбрасывает инкрементальный baseline директорий — следующий sync-проход снова полный, см. «Открытые вопросы» |
| `lib/data/services/app_cache_service.dart` | `AppCacheService.getDirectoriesLastSyncDate`, `.saveDirectoriesLastSyncDate`, `.clearDirectoriesLastSyncDate` | CURRENT | признак «инкрементальный/полный» директорийный sync |
| `packages/sheep_farm_database/lib/entities/kind/kinds_dao.dart` | `KindsDao.getAllKindWithDetailsByFilters` | CURRENT | **находка**: безусловно фильтрует `.where((tbl) => tbl.visible.equals(true))` независимо от того, что передал вызывающий код — см. «Открытые вопросы» |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository.getAllKindWithDetailsByFilters` | CURRENT | принимает параметр `visible` (по умолчанию `true`), но не передаёт его в `dao.getAllKindWithDetailsByFilters(ids: ids)` вообще — параметр декоративный |
| `lib/pages/board/board_filters/board_filters_bloc.dart` | вызов `_kindsRepository.getAllKindWithDetailsByFilters(visible: null, ...)` | CURRENT | пытается явно запросить видов без фильтра по видимости, но из-за находки выше всё равно получает только видимые |
| `lib/pages/vaccination_filters/vaccination_filters_bloc.dart` | вызов `_kindsRepository.getAll()` | CURRENT | игнорирует `Kind.visible` полностью — показывает и скрытые виды тоже, в отличие от остальных фильтров |
| `lib/pages/animal_filters/animal_filters_bloc.dart` | вызов `_kindsRepository.getAllVisibleKinds()` | CURRENT | корректно уважает `Kind.visible` — контрольный пример для сравнения |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.toggleKindVisibility`, `.toggleAllKindsVisibility`, `.saveKinds`, `.canProceedToNextStep` (`case kindsVisibility`) | CURRENT | второй, независимо написанный путь записи того же факта — см. «Бизнес-правила» |

## Критерии приёмки

- `toggleKindVisibility(kind)`/`toggleAllKindsVisibility(value)` синхронно
  обновляют `state.kinds` (инвертируя/устанавливая `visible` для одного
  вида или всех сразу), не обращаясь к репозиторию.
- Если после переключений `state.kinds.any((e) => e.visible) == true`,
  вызов `save()` приводит ровно к одному вызову
  `KindsRepository.updateAll(state.kinds)` со всем текущим in-memory
  списком (не только изменёнными записями).
- После успешного `updateAll` таблица `Kinds` содержит те же `id`/`name`/
  `animalTypeId` и обновлённые значения `visible`, что были в `state.kinds`
  на момент вызова, для **каждой** строки каталога.
- При успехе кубит эмитит `KindsVisibilitySettingsState.saved(kinds:
  state.kinds)`; ни один сетевой вызов (`setSettingToSHTP`) этим методом не
  выполняется.
- `KindsVisibilitySettingsPage` реагирует на `saved` показом снекбара
  `profile_settings__successfully_saved` и вызовом `context.pop()`.
- Если ни один вид не остаётся видимым, `updateAll` не вызывается вообще —
  это отдельный, REJECTED-сценарий, не покрываемый критериями этого файла.

## Связанные тесты

- `test/pages/kinds_visibility_settings_cubit_test.dart`, group `'UC-173 —
  KindsVisibilitySettingsCubit.save'`, test `'есть видимые виды -> updateAll
  вызван, saved'` — подтверждает шаги 6-10 основного потока: мокнутый
  `KindsRepository.getAll()` отвечает одним видимым `Kind`, `updateAll(any())`
  мокнут успехом; после `load()` + `save()` состояние переходит в `saved`, и
  `updateAll` вызван ровно один раз. Имя группы — старая нумерация (см.
  предисловие задачи); якорь `grep -r "UC-173" test/` работает уже сегодня.
  Группа названа по прежней нумерации id — переименование под `UC-173`
  выполняется отдельным контролируемым проходом, не этой задачей.
- `test/pages/kinds_visibility_settings_cubit_test.dart`, group
  `'KindsVisibilitySettingsCubit.toggleKindVisibility'` (без номера UC),
  test `'переключает visible у нужного вида'` — подтверждает шаг 3
  основного потока; test `'неизвестный id -> no-op'` — подтверждает
  соответствующую альтернативную ветку.
- `test/pages/kinds_visibility_settings_cubit_test.dart`, group
  `'KindsVisibilitySettingsCubit.toggleAllKindsVisibility'` (без номера
  UC), test `'выставляет visible всем сразу'` — подтверждает шаг 4
  основного потока.
- `test/pages/kinds_visibility_settings_cubit_test.dart`, group `'UC-174 —
  KindsVisibilitySettingsCubit.save REJECTED'` — покрывает соседнюю,
  REJECTED-ветку (не эту), упомянута здесь только для полноты картины по
  файлу.
- **TBD — теста нет** на то, что `updateAll` реально перезаписывает весь
  каталог целиком (N отдельных `replace()` внутри одной транзакции, не diff
  по изменённым записям) — существующий тест мокает
  `KindsRepository.updateAll` целиком и не проверяет содержимое переданного
  списка относительно того, что реально хранится в БД на уровне DAO.
- **TBD — теста нет** на гонку «`save()` вызван до завершения `load()`» —
  ни один существующий тест не вызывает `save()` без предварительного
  `load()`.
- **TBD — теста нет** на взаимодействие с `DataUpdateBloc.loadDirectories`/
  `SettingsRepository` (перезапись `Kind.visible` sync-проходом после
  сохранения этим сценарием) — ни `kinds_visibility_settings_cubit_test.dart`,
  ни известные тесты `data_update_bloc`/`settings_repository` не
  воспроизводят эту последовательность целиком.
- **TBD — теста нет** на второй путь записи того же факта
  (`FarmCreateCubit.saveKinds`) в сочетании с этим экраном.

## Открытые вопросы и ограничения

- **Полный sync-проход способен молча стереть только что сохранённый здесь
  результат, и для гостя — без какого-либо механизма восстановления.**
  `DataUpdateBloc.on<DataUpdateStartAll>` при **любом** запуске (гость или
  авторизованный) сперва вызывает `loadDirectories()`
  (`data_update_bloc.dart`), который тянет виды с сервера
  (`KindsRepository.getKindsFromApi`) и мапит их через
  `KindsDtoMapper.toModel()` — эта функция **жёстко проставляет `visible:
  true`** каждой строке, приходящей с сервера, независимо от того, что
  сохранил пользователь. Если на момент прохода
  `AppCacheService.getDirectoriesLastSyncDate(...) == null` (самый первый
  прогон, и любой прогон **после логаута** — `AuthRepository` сбрасывает
  этот baseline через `clearDirectoriesLastSyncDate()`), `loadDirectories`
  идёт по non-incremental ветке — `_kindsRepository.clearAndInsertAll(kinds)`
  — и заменяет **всю** таблицу `Kinds` целиком, безусловно сбрасывая
  `visible` каждого вида в `true`. Единственный код, способный вернуть
  реальные пользовательские значения после этого в том же проходе —
  `SettingsRepository.getSettingFromSHTP()` → `_setVisibleKinds(settings)`,
  вызываемый из `_syncAllData()` (`data_update_bloc.dart`) безусловно, но
  сам `_syncAllData()` достижим только через
  `_syncAuthData()` → `updateAndSyncRegagro()`, а `_syncAuthData()`
  вызывается только при `_authRepository.isAuthorized()`. **Для гостя это
  условие никогда не истинно** — значит для гостя `loadDirectories()`
  может сбросить `Kind.visible` в `true`, и ничто в кодовой базе это не
  восстановит: следующее открытие этого же экрана после такого прохода
  покажет пользователю, что все виды снова видимы, будто сохранение из
  этого сценария никогда не происходило. Для авторизованного пользователя
  восстановление дополнительно зависит от отдельного, не связанного с
  видами условия внутри `updateAndSyncRegagro()` (`dataUpdates.length <
  _totalDataUpdatesCount`/`errorDataUpdates.isNotEmpty`/`event.again`/
  `event.fullUpdate`), решающего, войдёт ли проход в `_syncAllData()`
  вообще. Не воспроизведено интеграционным тестом — вывод сделан
  статическим чтением `data_update_bloc.dart`, `kinds.dart`,
  `settings_repository.dart`, `auth_repository.dart`,
  `app_cache_service.dart` (все — см. «Технические зависимости»).
- **`Kind.visible` — единственное поле этой сущности, о котором заботится
  этот экран, но не единственное потребляющее его чтение в приложении, и
  три независимых читателя расходятся в поведении.** `animal_filters_bloc.dart`
  корректно уважает флаг (`getAllVisibleKinds()`, `visible.equals(true)`).
  `vaccination_filters_bloc.dart` игнорирует флаг полностью
  (`_kindsRepository.getAll()`, без фильтра) — показывает пользователю в
  фильтре вакцинаций и скрытые виды тоже, будто этот экран для них не
  существует. `board_filters_bloc.dart` явно пытается получить виды **без**
  фильтра (`getAllKindWithDetailsByFilters(visible: null, ...)`), рассчитывая
  на параметр `visible` репозитория — но `KindsRepository.getAllKindWithDetailsByFilters`
  не передаёт этот параметр в DAO вообще, а
  `KindsDao.getAllKindWithDetailsByFilters` **жёстко** содержит
  `.where((tbl) => tbl.visible.equals(true))`, не читая никакой входной
  параметр — так что `board_filters_bloc.dart`, несмотря на явное
  намерение автора кода, тоже получает только видимые виды, просто не тем
  путём, который он выбрал. Итог: то, что этот сценарий сохраняет в
  `Kind.visible`, реально скрывает вид в двух из трёх мест (animal-, и
  board-фильтрах — второе случайно, из-за бага, а не из-за осознанного
  уважения флага) и не скрывает его вовсе в третьем (vaccination-фильтр) —
  расхождение поведения между потребителями одного и того же поля, не
  специфичное для этого use-case по происхождению, но напрямую
  затрагивающее наблюдаемый эффект его результата.
- **Второй независимый писатель того же факта** —
  `FarmCreateCubit.saveKinds()` (модуль `FARM`,
  [UC-21](UC-21-ACTOR-1-EVT-10-ENT-9-CREATE_OK-IN-FARM.md)) — вызывает тот
  же `KindsRepository.updateAll`, но собственной, не связанной с этим
  экраном копией toggle-логики и без собственной REJECTED-проверки внутри
  `saveKinds()` (гейт «хотя бы один видимый» реализован только в
  `canProceedToNextStep()`, блокирующем кнопку мастера, а не сам метод
  сохранения). Ни один из двух путей не знает о параллельных изменениях
  другого — конфликт (например, пользователь одновременно правит видимость
  на этом экране и проходит мастер создания первой фермы в другой
  вкладке/сессии — гипотетически, приложение не проверялось на реальную
  многозадачность подобного рода) не обнаруживается и не разрешается ни
  блокировкой, ни предупреждением.
- Снекбар успеха на этом экране показывается через сырой
  `ScaffoldMessenger.of(context).showSnackBar(...)`, а не через проектный
  хелпер `lib/widgets/app_snackbar.dart` (`showAppSnackBarSuccess`),
  предписанный конвенцией UI проекта — стилевое расхождение с
  [UC-169](UC-169-ACTOR-5-EVT-85-ENT-21-UPDATE_OK-IN-PROFILE.md) (сосед по
  модулю, вообще не показывающий снекбар на успехе), не влияющее на
  бизнес-логику этого сценария.
- Не проверено эмпирически на реальном устройстве/бэкенде — вывод обо всех
  находках сделан статическим чтением кода и подтверждён только
  модульным тестом уровня кубита с замоканным `KindsRepository` (см.
  «Связанные тесты»), без реального Drift/SQLite-стека и без реального
  прогона `DataUpdateBloc`.
