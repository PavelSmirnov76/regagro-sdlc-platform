# UC-172 — Чтение списка видов на экране «Видимость видов животных» падает: исключение никем не перехватывается, экран навсегда застревает на спиннере

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же экран, что описан в [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md) —
`KindsVisibilitySettingsCubit.load()` читает все `Kind` при открытии
«Видимость видов животных». Здесь описан путь, когда это чтение реально
бросает исключение.

В отличие от [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)
(соседний экран того же модуля, `NotificationsSettingsCubit.load()`), где
исключение хотя бы перехватывается собственным `try/catch` кубита и
логируется в `Talker` перед тем, как экран молча остаётся на неверных
дефолтах, здесь **нет вообще никакого перехватчика** на всём пути от
`dao.getAll()` до вызывающего кода: ни `KindsRepository.getAll()`
(унаследован от `BaseRepository`, не переопределён), ни `BaseRepository`,
ни `BaseDao.getAll()`, ни сам `KindsVisibilitySettingsCubit.load()` не
оборачивают этот вызов в `try/catch`. Это ближе по механике к под-ветке
«Hive-исключение внутри `BoardChatAvailabilityCubit`», задокументированной
как альтернативный поток в
[UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md) (там —
структурно недостижимый на сегодня побочный путь; здесь — единственный
путь для чтения списка видов, полностью достижимый и подтверждённый
тестом на уровне кубита).

Наблюдаемый пользователем итог: экран открывается, показывает
`CircularProgressIndicator` (`KindsVisibilitySettingsLoadingWidget`) и
остаётся в этом состоянии навсегда — ни ошибки, ни снэкбара, ни таймаута,
ни кнопки «повторить». Исключение не долетает ни до одного лога
приложения (`Talker`), потому что перехватывать его попросту некому;
единственное, что могло бы его увидеть — зона Dart по умолчанию, а
`runApp` в `lib/main.dart` не обёрнут в `runZonedGuarded` (соответствующий
вызов закомментирован). Дополнительно проверена и задокументирована
отдельным под-пунктом асимметрия с почти идентичным по смыслу кодом в
`FarmCreateCubit.loadData` (тот же `_kindsRepository.getAll()`, тот же
паттерн «отсортировать по имени», но обёрнутый в `try/catch` с
`errorMessage` в state) — см. «Альтернативные потоки».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость или авторизованный одинаково. Проверено чтением кода: единственная
точка входа на маршрут — `WorkSettingsItem` с
`l10n.profile_settings__kinds_visibility_settings` внутри
`WorkSettingsPage.build` (`lib/pages/profile_settings/presentation/work_settings_page.dart`),
`onTap: () => context.pushNamed2(Routes.kindsVisibilitySettings)` — без
какого-либо условия по `AppCacheService.isAuthorized()` вокруг самого
пункта. `WorkSettingsPage`, в свою очередь, открывается с кнопки
«Настройки» (`l10n.profile_settings__work_settings`) в `ProfileView.build`
(`lib/pages/profile/presentation/widgets/profile/profile_view.dart`) —
эта кнопка тоже не обёрнута ни в один `if (AppCacheService.isAuthorized())`
(единственный блок этого экрана, скрываемый условием, — секция BOARD,
`BlocBuilder<BoardChatAvailabilityCubit, bool>`, к «Настройкам» отношения
не имеет). Это подтверждает формулировку из
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md)/[MOD-6](../modules/MOD-6-PROFILE.md)
«весь раздел без route-guard по авторизации» буквально для этого
конкретного экрана — в отличие от найденного в
[UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md) расхождения
для соседнего экрана уведомлений, здесь кнопка-вход одинаково видна и
гостю, и авторизованному.

Полный путь маршрута — `/profile/work_settings/kinds_visibility_settings`
(`lib/pages/routes.dart`, вложенность `Routes.profile` → `Routes.workSettings`
→ `Routes.kindsVisibilitySettings`).

## CURRENT

### Основной поток

1. Пользователь (гость или авторизованный) на `ProfileView` нажимает
   кнопку «Настройки» → `context.pushNamed2(Routes.workSettings)` →
   `WorkSettingsPage`; там нажимает пункт «Видимость видов животных» →
   `context.pushNamed2(Routes.kindsVisibilitySettings)`.
2. `KindsVisibilitySettingsPage.build()`
   (`lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart`)
   создаёт `BlocProvider(create: (context) => KindsVisibilitySettingsCubit()..load())` —
   `load()` запускается сразу при создании кубита, результат вызова (a
   `Future<void>`) отброшен: каскадный оператор `..` возвращает сам
   объект кубита, вызывающий код нигде не хранит и не ожидает `Future`,
   который вернул `load()`.
3. `KindsVisibilitySettingsCubit.load()`
   (`lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart`):
   первой строкой —
   `emit(KindsVisibilitySettingsState.loading(kinds: state.kinds))` — на
   первом входе `state.kinds` пуст (`KindsVisibilitySettingsState.initial()`
   в конструкторе кубита, `@Default([])`).
4. `final kinds = (await _kindsRepository.getAll())..sort(...)` —
   `_kindsRepository` — `KindsRepository`
   (`lib/repositories/kind/kinds_repository.dart`), не переопределяет
   `getAll()`; вызов уходит в унаследованный
   `BaseRepository<KindsDao, Kind, $KindsTable>.getAll()`
   (`lib/repositories/base_repository.dart`) → `dao.getAll()` →
   `KindsDao extends BaseDao<Kind, $KindsTable>`
   (`packages/sheep_farm_database/lib/entities/kind/kinds_dao.dart`), не
   переопределяет `getAll()` → `BaseDao.getAll()`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) →
   `selectCurrent().get()` — реальный Drift-запрос (`select(Kinds).get()`)
   к физической sqlite3-БД через `getIt<AppDatabase>().getDaoByType<KindsDao>()`.
   В этом сценарии вызов бросает исключение (диск/БД — например,
   `SqliteException`/обёрнутое drift-исключение при ошибке I/O, блокировке
   файла БД или порче данных).
5. Ни `KindsRepository.getAll()` (не переопределён — наследуется как есть),
   ни `BaseRepository.getAll()`, ни `KindsDao.getAll()` (тоже не
   переопределён), ни `BaseDao.getAll()` не оборачивают вызов в
   `try/catch`. Исключение всплывает необработанным из `await
   _kindsRepository.getAll()` внутри `load()` — а сам `load()` тоже не
   имеет `try/catch` вокруг этой строки (единственный метод класса,
   который вообще что-то читает из репозитория, целиком без обработки
   ошибок).
6. Дальнейшие строки `load()` (`..sort(...)`,
   `emit(KindsVisibilitySettingsState.loaded(kinds: kinds))` дважды подряд)
   не выполняются — метод завершается исключением, `Future<void>`,
   возвращённый `load()`, переходит в состояние ошибки.
7. Поскольку этот `Future` создан вызовом `..load()` в `create:` без
   `await` и без `.catchError`, никто не подписан на его завершение —
   исключение становится необработанной ошибкой `Future`, видимой (если
   вообще) только зоне Dart по умолчанию: `runApp` в `lib/main.dart` не
   обёрнут в `runZonedGuarded` (`runTalkerZonedGuarded(...)` закомментирован
   в `main()`), и никакой другой глобальный обработчик (`PlatformDispatcher.instance.onError`,
   `FlutterError.onError`) не настроен нигде в `lib/`
   (`grep -rn "PlatformDispatcher\|runZonedGuarded\|FlutterError.onError" lib/`
   находит только несюгие `PlatformDispatcher.instance.locale` в
   `language_service.dart`/`registration_cubit.dart`/`call_the_owner_cubit.dart`/`profile_edit_cubit.dart`,
   ни один не про обработку ошибок). Ни `Talker` (`getIt<Talker>()`), ни
   `dart:developer.log`, ни любой другой лог приложения не видит это
   исключение — оно не логируется нигде внутри приложения.
8. `state` кубита остаётся равным тому, что было эмитировано на шаге 3 —
   `KindsVisibilitySettingsState.loading(kinds: [])` — навсегда, до тех
   пор пока сам экземпляр кубита не будет уничтожен (выход с экрана).
9. `BlocConsumer` в `KindsVisibilitySettingsPage.build()`: `state.when(...,
   loading: (_) => const KindsVisibilitySettingsLoadingWidget(), ...)` —
   `builder` продолжает рисовать `Center(child: CircularProgressIndicator())`.
   `listener` (`state.whenOrNull(saved: ..., failure: ...)`) не
   срабатывает вовсе — состояние `loading` не входит ни в одну из двух
   обрабатываемых веток.
10. Пользователь видит бесконечный спиннер на экране «Видимость видов
    животных»: кнопка «Сохранить» (`floatingActionButton`,
    `RElevatedButton`) при этом всё равно отображается и активна (её
    видимость не зависит от `state`), но нажатие на неё вызывает
    `KindsVisibilitySettingsCubit.save()`, которое читает
    `state.kinds.any((e) => e.visible)` — на пустом списке `any` возвращает
    `false`, значит `save()` уходит в свою собственную ветку отказа:
    `emit(KindsVisibilitySettingsState.failure(kinds: [], error: 'key'))`
    (см. «Альтернативные потоки»).

### Альтернативные потоки

- **(а) Нажатие «Сохранить» на застрявшем экране — не no-op, а отдельный
  штатный отказ бизнес-правила, маскирующий изначальную техническую
  ошибку.** Пока кубит завис на `loading` (пустой `state.kinds`), кнопка
  «Сохранить» остаётся активной. Нажатие вызывает `save()`:
  `state.kinds.any((e) => e.visible)` на `[]` — `false` → `emit(failure(kinds:
  [], error: 'key'))`, `_kindsRepository.updateAll` не вызывается вовсе.
  Теперь `BlocConsumer.listener` **срабатывает** — ветка `failure` описана
  (`ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
  Text(AppLocalizations.of(context)!.tr('key'))))`) — но `tr('key')`
  возвращает буквальный текст `'key'` (тот же известный дефект, что уже
  задокументирован в [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md)
  для случая «пользователь осознанно снял все галочки»): пользователь
  видит снэкбар со словом «key», выглядящий как обычная валидационная
  ошибка «не выбран ни один вид», а не как признак того, что сам список
  видов не загрузился. Технический `READ_ERROR` шага 4–7 маскируется под
  бизнес-`REJECTED` из `save()`, неотличимый от легитимного «пользователь
  сам снял все галочки».
- **(б) Асимметрия с почти идентичным по смыслу кодом в `FarmCreateCubit`
  того же репозитория.** `FarmCreateCubit.loadData`
  (`lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart`,
  модуль `FARM`, уже специфицирован) при `isFirstFarm == true` выполняет
  почти тот же вызов — `kinds = (await _kindsRepository.getAll())..sort((a,
  b) => a.name.compareTo(b.name))` — но **внутри `try { ... } catch (e) {
  emit(state.copyWith(isLoading: false, errorMessage: e.toString())); }`**,
  оборачивающего весь метод `loadData`. То же самое исключение от того же
  самого `_kindsRepository.getAll()` в этом сценарии-соседе приводит к
  видимому, отличимому состоянию (`errorMessage` в `FarmCreateState`), а не
  к вечному `loading`. Подтверждено чтением обоих файлов — это не общий
  паттерн проекта для мест, читающих `KindsRepository.getAll()`, а именно
  асимметрия между двумя независимо написанными путями к одной и той же
  таблице `Kinds`.
- **(в) Другой класс отказа — конструктор кубита/репозитория, не сам
  `load()` — структурно другой, не описываемый этим сценарием.** Поле
  `final _kindsRepository = getIt.get<KindsRepository>()` и, внутри него,
  `final dao = getIt<AppDatabase>().getDaoByType<KindsDao>()`
  (`BaseRepository`) вычисляются синхронно в момент конструирования
  `KindsVisibilitySettingsCubit()`, то есть до вызова `load()`. Если бы
  `AppDatabase` не была ещё зарегистрирована в `getIt`
  (`getIt.registerSingleton<AppDatabase>(AppDatabase())` в
  `injection_container.dart` выполняется один раз, при старте приложения,
  задолго до открытия этого экрана) — исключение всплыло бы синхронно из
  `BlocProvider.create` в `main.dart`, до появления кубита в дереве
  провайдеров, принципиально другой отказ (аналогично альтернативному
  потоку (1) в [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)).
  При текущем порядке инициализации `main()` `AppDatabase` гарантированно
  уже зарегистрирована к моменту открытия любого экрана приложения — этот
  путь на практике не наступает и не является предметом данного сценария.

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS) — единственная сущность, которую этот сценарий пытается
  прочитать (`dao.getAll()` на таблице `Kinds`) и не может; в
  альтернативном потоке (а) `Kind.visible` не изменяется вовсе —
  `updateAll` не достигается, потому что `save()` отказывает раньше по
  собственному бизнес-правилу на пустом списке.

### Бизнес-правила

- Нет ретрая и нет ручной кнопки «повторить» на экране — единственный
  способ вызвать `load()` снова — полностью покинуть экран
  (`Navigator.pop`) и открыть его заново, что пересоздаёт
  `KindsVisibilitySettingsCubit` с нуля.
- Кнопка «Сохранить» не блокируется и не скрывается при `loading` —
  доступность записи не зависит от того, завершилось ли чтение.
- `save()` трактует пустой `state.kinds` (в т.ч. полученный из-за
  незавершённого/упавшего `load()`, а не только из-за осознанного «снять
  все галочки» пользователем) как то же самое бизнес-условие «не выбран ни
  один вид» — оба случая неотличимы на уровне `state.kinds.any((e) =>
  e.visible)`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Основной сценарий (необработанное
исключение в `KindsRepository.getAll()` → отсутствие какого-либо
перехватчика на всём пути до `KindsVisibilitySettingsCubit.load()` →
кубит навсегда остаётся в `loading` → UI показывает бесконечный спиннер)
подтверждён статическим чтением кода всех перечисленных файлов; ни один
существующий тест этот путь не воспроизводит (см. «Связанные тесты»).
Альтернативный поток (а) (нажатие «Сохранить» на застрявшем экране →
`failure` с текстом «key», маскирующее исходный технический отказ под
бизнес-отказ) прослежен статически по обоим методам кубита, но не
воспроизведён ни одним тестом. Исправление (например, `try/catch` вокруг
`load()` по аналогии с `NotificationsSettingsCubit`/`FarmCreateCubit`,
видимый пользователю признак ошибки, блокировка «Сохранить» до успешного
`load()`) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.load` | CURRENT | предмет основного потока — единственный метод, читающий репозиторий; ни один перехватчик исключения на всём его теле |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_state.dart` | `KindsVisibilitySettingsState.loading`/`.failure` | CURRENT | `loading` — состояние, в котором кубит навсегда застревает; `failure` — достижимо только из `save()`, не из `load()` |
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `KindsVisibilitySettingsPage.build` (`BlocProvider.create`, `BlocConsumer.builder`/`.listener`) | CURRENT | `create: (context) => KindsVisibilitySettingsCubit()..load()` — результат `load()` не ожидается и не перехватывается; `builder` для `loading` — бесконечный спиннер; `listener` не имеет ветки на `loading` |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository` | CURRENT | не переопределяет `getAll()` — используется как есть из `BaseRepository`, без собственного `try/catch` |
| `lib/repositories/base_repository.dart` | `BaseRepository.getAll`, `.dao` | CURRENT | `getAll()` — прямой проброс в `dao.getAll()`, без обработки ошибок; `dao` — `getIt<AppDatabase>().getDaoByType<BD>()`, вычисляется синхронно при конструировании репозитория (см. альтернативный поток (в)) |
| `packages/sheep_farm_database/lib/entities/kind/kinds_dao.dart` | `KindsDao` | CURRENT | Drift DAO над таблицей `Kinds`, не переопределяет `getAll()` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.getAll`, `.selectCurrent` | CURRENT | `getAll()` — реальный Drift-запрос (`selectCurrent().get()`), источник технического исключения в этом сценарии |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.loadData` | CURRENT | контрастный сосед — тот же `_kindsRepository.getAll()`, но обёрнутый в `try/catch` с видимым `errorMessage` (см. «Альтернативные потоки», (б)) |
| `lib/pages/profile_settings/presentation/work_settings_page.dart` | `WorkSettingsPage.build`, `WorkSettingsItem.onTap` | CURRENT | единственная найденная точка входа на маршрут — не обёрнута ни в какое условие авторизации |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `ProfileView.build` (кнопка «Настройки») | CURRENT | кнопка, ведущая на `WorkSettingsPage` — тоже без условия авторизации (единственный гейт на этом экране — секция BOARD, к этой кнопке отношения не имеющая) |
| `lib/pages/routes.dart` | `Routes.profile`/`.workSettings`/`.kindsVisibilitySettings` | CURRENT | вложенность маршрута `/profile/work_settings/kinds_visibility_settings` |
| `lib/main.dart` | `main()` (`runApp(const MyApp())`, закомментированный `runTalkerZonedGuarded`) | CURRENT | подтверждает отсутствие глобального перехватчика необработанных ошибок `Future` в приложении |
| `lib/injection_container.dart` | `getItInit()` (`getIt.registerSingleton<AppDatabase>(AppDatabase())`) | CURRENT | подтверждает, что `AppDatabase` зарегистрирована задолго до открытия любого экрана — альтернативный поток (в) на практике не наступает |

## Критерии приёмки

- Если `dao.getAll()` внутри `KindsRepository.getAll()` (через `BaseRepository`/`BaseDao`)
  бросает исключение любого типа, `KindsVisibilitySettingsCubit.load()` не
  перехватывает его — исключение становится необработанной ошибкой
  `Future`, возвращённого `load()`.
- Ни один `emit` после `emit(loading(...))` (шаг 3) не выполняется — кубит
  остаётся в `KindsVisibilitySettingsState.loading(kinds: [])` до
  уничтожения экземпляра (выход с экрана).
- Исключение не появляется ни в одном логе приложения — `getIt<Talker>()`
  не вызывается нигде в `load()`.
- `KindsVisibilitySettingsPage` показывает `CircularProgressIndicator`
  бесконечно; `BlocConsumer.listener` не производит никакого побочного
  эффекта для состояния `loading`.
- Кнопка «Сохранить» остаётся видимой и активной при `loading`; нажатие на
  неё на пустом `state.kinds` уходит в `save()`'s собственную ветку отказа
  (`failure(kinds: [], error: 'key')`) — с тем же известным дефектом текста
  `'key'` вместо переведённого сообщения, что и в
  [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md).
- Повторное чтение возможно только через пересоздание
  `KindsVisibilitySettingsCubit` (выход с экрана и повторный вход) — в
  самом коде страницы нет отдельного триггера повтора `load()`.
- Кнопка-вход на этот экран (`WorkSettingsItem` → `ProfileView`'s кнопка
  «Настройки») видна и доступна одинаково гостю и авторизованному
  пользователю — ни один из двух уровней навигации не проверяет
  авторизацию.

## Связанные тесты

`test/pages/kinds_visibility_settings_cubit_test.dart` существует и
покрывает только успешные комбинации:

- group `'UC-171 — KindsVisibilitySettingsCubit.load'`, test `'загружает и
  сортирует kinds по имени'`.
- group `'KindsVisibilitySettingsCubit.toggleKindVisibility'`, тесты
  `'переключает visible у нужного вида'`, `'неизвестный id -> no-op'`.
- group `'KindsVisibilitySettingsCubit.toggleAllKindsVisibility'`, test
  `'выставляет visible всем сразу'`.
- group `'UC-174 — KindsVisibilitySettingsCubit.save REJECTED'`, test `'нет
  ни одного видимого вида -> failure, updateAll не вызывается'`.
- group `'UC-173 — KindsVisibilitySettingsCubit.save'`, test `'есть
  видимые виды -> updateAll вызван, saved'`.

Ни один из пяти тестов не мокает `repository.getAll()` (через `when(() =>
repository.getAll()).thenThrow(...)` или аналог) как бросающий исключение —
каждый тест, где `load()` вызывается, предварительно стабит `getAll()`
успешным `thenAnswer`. Ни в одном из существующих тестов не проверяется
итоговое состояние `KindsVisibilitySettingsCubit` после брошенного
репозиторием исключения.

**TBD — теста нет** на сценарий, описанный этим файлом: ни на сам
необработанный `Future`-отказ `load()` (кубит должен остаться в
`loading` навсегда), ни на альтернативный поток (а) (нажатие «Сохранить»
на пустом `state.kinds` после отказавшего чтения → `failure` с `error:
'key'`).

## Открытые вопросы и ограничения

- **Отсутствие любого перехватчика — недосмотр или намеренное решение?**
  Ничем в коде/комментариях не зафиксировано. Контраст с
  `FarmCreateCubit.loadData` (альтернативный поток (б)) — тот же вызов
  `_kindsRepository.getAll()`, обёрнутый в `try/catch` — говорит скорее в
  пользу недосмотра, чем осознанного решения именно для этого экрана.
  Контраст с `NotificationsSettingsCubit.load()`
  ([UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)), где
  хотя бы есть `try/catch` с логированием в `Talker`, усиливает то же
  наблюдение — из трёх похожих read-экранов модуля `PROFILE`
  (`KindsVisibilitySettingsCubit`, `NotificationsSettingsCubit`,
  `FarmCreateCubit` — последний формально в `FARM`, но использует тот же
  репозиторий) только этот не имеет вообще никакой обработки ошибок.
- **«Вечный спиннер» — более тихий и более вредный отказ, чем оба уже
  задокументированных read-экрана модуля.** И `NotificationsSettingsPage`
  ([UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)), и
  `BoardChatAvailabilityCubit` ([UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md))
  в своих READ_ERROR-сценариях в итоге показывают пользователю **какой-то**
  экран (пусть с неверными дефолтами или скрытым разделом) — здесь
  пользователь не получает вообще ничего, кроме бесконечной загрузки, без
  какого-либо способа понять, что произошла ошибка, и без способа выйти,
  кроме системной кнопки «назад».
- **Альтернативный поток (а) маскирует технический `READ_ERROR` под
  бизнес-`REJECTED`.** Если пользователь всё же нажмёт «Сохранить» на
  застрявшем экране, единственный видимый сигнал — снэкбар с буквальным
  текстом «key» — тем же известным дефектом локализации, что уже описан в
  [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) для
  случая, когда пользователь сам осознанно снял все галочки. Два
  принципиально разных по природе сценария (техническая ошибка чтения vs.
  осознанный отказ бизнес-правила) неотличимы друг от друга по итоговому
  UI.
- Реальный технический источник исключения (диск, блокировка файла БД,
  повреждение данных) не воспроизведён эмпирически — этот документирующий
  проход, как и оба процитированных эталона
  ([UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md),
  [UC-158](UC-158-ACTOR-3-EVT-79-ENT-4-READ_ERROR-IN-BOARD.md)), опирается
  на статическое чтение цепочки вызовов, не на воспроизведённый реальный
  сбой `drift`/`sqlite3`.
