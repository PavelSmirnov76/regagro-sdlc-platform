# UC-192 — Очистка локальных данных при выходе отказывает: необработанное исключение из `clearUserData()` или из одного из двух fire-and-forget вызовов после него теряется без следа

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) |
| Сущность | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |

## Назначение

Тот же обработчик, что описан в [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md)
и в его успешном сценарии, [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md)
(`DataUpdateBloc.on<DataUpdateClear>`, `lib/blocs/data_update/data_update_bloc.dart`) —
здесь документируется отказ. [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md)
уже отметил (раздел «Альтернативные потоки»), что подробная спецификация
этого ERROR-пути — задача отдельного документа; это он.

Обработчик целиком — три строки, без единого `try/catch` и без единого
`emit(...)`:

```dart
on<DataUpdateClear>((event, emit) async {
  await _appDatabase.clearUserData();

  DefaultCacheManager().emptyCache();

  pref.setBool('have_any_language', false);
});
```

Это даёт **два структурно разных** источника отказа, ведущих к разным (но
одинаково незаметным пользователю) последствиям:

- **Ветка (а).** Сам `await _appDatabase.clearUserData()` бросает
  исключение. Поскольку вокруг этой строки нет `try/catch`, исключение
  всплывает из тела обработчика наружу — но не в вызывающий код напрямую, а
  в собственную обёртку пакета `bloc` вокруг каждого `on<E>`-обработчика
  (подтверждено чтением `bloc-9.0.1/lib/src/bloc.dart`, версия закреплена в
  `pubspec.lock`, см. «Технические зависимости»): там оно перехватывается,
  один раз логируется через зарегистрированный `Bloc.observer`
  (`TalkerBlocObserver`, `lib/injection_container.dart`) и затем
  **перебрасывается повторно** — уже внутри вызова, который сам пакет делает
  без `await` и без обработчика ошибок. Итог — исключение всё же становится
  необработанной ошибкой `Future` на уровне зоны Dart, просто на один шаг
  позже и после того, как след от него уже остался в логе `Talker`.
- **Ветка (б).** Один из двух вызовов **после** `await` —
  `DefaultCacheManager().emptyCache()` или
  `pref.setBool('have_any_language', false)` — бросает исключение
  асинхронно. Ни один из них не вызван с `await`: к моменту, когда любой из
  них в принципе мог бы отказать, тело обработчика уже полностью
  выполнилось и его собственный `Future<void>` уже успешно завершился.
  Поэтому такое исключение вообще не попадает под перехват, описанный в
  ветке (а), — оно не проходит ни через `Bloc.observer.onError`, ни через
  `Talker`, ни через что-либо ещё в приложении. Это строго более тихий
  отказ, чем ветка (а).

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — тот же пользователь и те же
три пути к `AuthLogout` (обычный выход, автоматическая потеря сессии,
запрос удаления аккаунта), что подробно разобраны в
[UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md), «Пользователь» —
не дублируется здесь. Как и там, сам актор, действующий в момент **этого**
сценария (отказа очистки), — не человек: `DataUpdateBloc.on<DataUpdateClear>`
выполняется без какого-либо пользовательского участия в момент вызова.
Дополнительно к уже описанному в UC-191: логаут в текущем UI инициируется
только с экрана профиля (кнопка внутри `ProfileView`), а `Routes.profile`
зарегистрирован как одна из веток `StatefulShellRoute`, обёрнутых снаружи
`MainPage` (`lib/pages/routes.dart`, `lib/pages/main/main_page.dart`) — то
есть `ProfilePage`'s собственный `BlocListener<AuthBloc, AuthState>`
(`lib/pages/profile/presentation/profile_page.dart`) и `MainPage`'s
`BlocListener<AuthBloc, AuthState>` оба одновременно подписаны на один и тот
же `AuthBloc` в момент, когда логаут вообще может произойти — см. «Основной
поток», шаг 2.

## CURRENT

### Основной поток

1. Один из трёх путей, разобранных в [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md),
   доводит `AuthBloc` до `emit(const AuthLogout())`.
2. **Двойной диспатч.** И `ProfilePage`'s `BlocListener<AuthBloc, AuthState>`
   (`else if (state is AuthLogout) { context.read<DataUpdateBloc>().add(DataUpdateClear()); }`,
   `lib/pages/profile/presentation/profile_page.dart`), и `MainPage`'s
   `BlocListener<AuthBloc, AuthState>` (`lib/pages/main/main_page.dart`,
   `if (state is AuthLogout) { context.read<DataUpdateBloc>().add(DataUpdateClear()); ... }`)
   реагируют на одну и ту же эмиссию `AuthLogout` независимо друг от друга —
   оба смонтированы одновременно, поскольку `ProfilePage` рендерится как
   ветка того же `StatefulShellRoute`, который `MainPage` оборачивает. Оба
   вызывают `context.read<DataUpdateBloc>().add(DataUpdateClear())`. Итог:
   **два** отдельных события `DataUpdateClear` попадают в `DataUpdateBloc`
   на одну реальную попытку выхода — оба обрабатываются (по умолчанию
   `Bloc.transformer` конкурентен, ни `on<DataUpdateStartAll>`, ни
   `on<DataUpdateClear>` не передают собственный `transformer:`), см.
   «Альтернативные потоки».
3. `MainPage`'s обработчик, помимо диспатча, сразу же (без ожидания)
   сбрасывает оба навигационных стека и делает `context.go(Routes.profile)` —
   пользователь оказывается на экране профиля/входа независимо от исхода
   любой из двух копий `DataUpdateClear`, в точности как в
   [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md), шаг 3.
4. Для (как минимум одной из двух копий) события `DataUpdateClear`,
   `on<DataUpdateClear>` начинает выполнение: `await
   _appDatabase.clearUserData()`.

**Ветка (а) — `clearUserData()` бросает исключение.**

5. `clearUserData()` (`packages/sheep_farm_database/lib/database/database.dart`)
   — алиас на `clearAllClearableTables()`
   (`packages/sheep_farm_database/lib/database/database.clearable.dart`),
   сгенерированную одну Drift-`transaction()`, внутри которой `PRAGMA
   foreign_keys = OFF` действует на всё время последовательных `delete(table).go()`
   по 15 таблицам (см. [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md),
   шаг 6, для полного списка и порядка). **Классический FK-конфликт здесь
   структурно исключён именно этим переключением** — и это переключение не
   избыточно: порядок удаления в сгенерированном коде строго алфавитный, не
   по графу FK-зависимостей, а среди удаляемых таблиц есть настоящий
   FK-контракт, который алфавитный порядок нарушил бы, будь проверки
   включены — `Vaccinations.animalId` объявлен как
   `integer().customConstraint('REFERENCES animals(id) NOT NULL')()`
   (`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart`),
   а `vaccinations` удаляется **после** `animals` (алфавитно `v` > `a`) — то
   есть в момент `delete(animals).go()` строки `Vaccinations`, ссылающиеся на
   эти же `id`, ещё физически лежат в таблице. Аналогично
   `AnimalWeighings.animalId => integer().references(Animals, #id)()`
   (`packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart`),
   но эта таблица, напротив, удаляется **до** `animals` — конфликта не было
   бы и без выключенных проверок. Иными словами: `PRAGMA foreign_keys = OFF`
   в этом коде не защита «на всякий случай», а необходимое условие того,
   чтобы алфавитный порядок удаления вообще работал — при этом сама эта
   зависимость нигде не закреплена явно (ни тестом, ни комментарием рядом с
   генератором, `clearable_builder.dart`), только фактом, что переключение
   стоит на месте.
6. Остающиеся реалистичные источники исключения — не FK, а более низкого
   уровня: сбой файлового I/O (диск переполнен, файл БД повреждён), либо
   собственная ошибка драйвера/исполнителя запросов. Отдельно
   рассмотрена (но не подтверждена как реально воспроизводимая) гипотеза
   параллельного выполнения: `Bloc.transformer` по умолчанию конкурентен, и
   ни `on<DataUpdateStartAll>`, ни `on<DataUpdateClear>` не переопределяют
   его, поэтому в принципе пользователь мог бы инициировать выход, пока
   ранее запущенный `DataUpdateStartAll` ещё пишет в тот же `_appDatabase`
   (общий `getIt<AppDatabase>()`-синглтон) — но Drift сериализует реальное
   выполнение через единственный `QueryExecutor`/фоновый изолят
   (`NativeDatabase.createInBackground`, `packages/sheep_farm_database/lib/database/database.dart`,
   `_openConnection`), поэтому настоящая гонка на уровне SQL-исполнения
   маловероятна — это не подтверждённый, а лишь теоретически рассмотренный
   усилитель вероятности отказа, см. «Открытые вопросы».
7. Если `clearUserData()` всё же бросает исключение по любой из этих
   причин — Drift автоматически откатывает `transaction()` целиком: ни одна
   из 15 таблиц не остаётся частично очищенной, все они сохраняют своё
   состояние до попытки в точности таким, каким оно было (контраст с
   [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md), где после
   успеха все 15 пусты).
8. Исключение всплывает из `await _appDatabase.clearUserData()` наружу тела
   `on<DataUpdateClear>` — обработчик не оборачивает эту строку ни в какой
   `try/catch`. Дальше вступает внутренняя механика самого пакета `bloc`
   (`Bloc.on<E>`, `bloc-9.0.1/lib/src/bloc.dart`, подтверждено прямым
   чтением исходника зависимости, версия закреплена в `pubspec.lock`):
   переданный обработчик вызывается внутри локальной `handleEvent()`,
   написанной как
   `try { await handler(event, emitter); } catch (error, stackTrace) { onError(error, stackTrace); rethrow; } finally { onDone(); }`.
9. `onError(error, stackTrace)` здесь — это `BlocBase.onError`, который
   безусловно вызывает `_blocObserver.onError(this, error, stackTrace)`.
   `Bloc.observer` во всём приложении — единственный экземпляр
   `TalkerBlocObserver`, зарегистрированный в `lib/injection_container.dart`
   (`Bloc.observer = TalkerBlocObserver(talker: loger, ...)`). Его
   собственная реализация `onError`
   (`talker_bloc_logger-5.0.1/lib/talker_bloc_logger_observer.dart`) делает
   ровно одно: `_talker.error('${bloc.runtimeType}', error, stackTrace)` —
   то есть **это исключение действительно попадает в лог `Talker`**,
   просматриваемый через `TalkerScreen`, открываемый из `ProfileView`
   (тот же единственный путь просмотра, что уже отмечен в
   [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md) для
   другого сценария).
10. Сразу за вызовом `onError` в том же `catch`-блоке `bloc` делает
    `rethrow`. Но сама `handleEvent()` вызвана строкой `handleEvent();` —
    **без `await`, без `.then`/`.catchError`** — внутри callback'а, который
    `on<E>` передаёт Stream-трансформеру. Никто не ждёт и не обрабатывает
    `Future`, которым эта функция в итоге завершается. Значит, исключение
    (уже залогированное на шаге 9) становится **дополнительно** необработанной
    ошибкой `Future` в текущей зоне Dart.
11. `lib/main.dart`'s `main()` вызывает `runApp(...)` напрямую — нигде в
    `lib/` не встречается ни `runZonedGuarded`, ни переопределение
    `PlatformDispatcher.instance.onError`, ни `FlutterError.onError`
    (`grep -rn "runZonedGuarded\|PlatformDispatcher\|FlutterError.onError" lib/`
    не находит ни одного места, задающего пользовательский обработчик
    необработанных асинхронных ошибок в корневой зоне; единственные
    найденные упоминания `PlatformDispatcher` — не про `onError`, а про
    `.instance.locale`). Значит, необработанная ошибка `Future` с шага 10
    доходит до зоны по умолчанию — на практике это означает вывод
    диагностики в консоль/лог движка (`Unhandled exception:` + стек), без
    падения изолята, без снэкбара, без какого-либо иного эффекта, видимого
    пользователю.
12. Ни на одном из шагов 5–11 не эмитится ни одно состояние
    `DataUpdateBloc` — `emit(DataUpdateFailure(...))`/`_emitError`
    (`DataUpdateBloc._emitError`, `_addDataUpdateError`) существуют только
    внутри `catch` `on<DataUpdateStartAll>` (`grep -n "_emitError\b"
    lib/blocs/data_update/data_update_bloc.dart` даёт единственное
    вхождение вызова, вне `on<DataUpdateClear>`) — этот сценарий их не
    достигает вовсе, поэтому ни строки в `DataUpdates`, ни `DataUpdateFailure`
    для пользователя не появляется. Единственный `BlocListener<DataUpdateBloc,
    DataUpdateState>` в приложении (`main_page.dart`) реагирует только на
    `DataUpdateInProgress` — этому сценарию нечего было бы показать, даже
    если бы состояние эмитировалось.
13. Итоговый наблюдаемый эффект: пользователь уже переведён на экран
    профиля/входа (шаг 3, независимо от этого отказа) и воспринимает выход
    как обычный, тогда как каждая из 15 `@Clearable`-таблиц — `Animals`,
    `Farms`, `Vaccinations`, `Movements` и т.д. — на самом деле осталась
    полностью заполненной данными предыдущего аккаунта на этом устройстве,
    без какого-либо способа заметить это, кроме прямого просмотра БД или,
    для тех, кто знает искать, `TalkerScreen`.

**Ветка (б) — один из двух вызовов после `await` бросает исключение
асинхронно.**

14. `await _appDatabase.clearUserData()` (шаг 4) на этот раз успешен — 15
    таблиц очищены, как в [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md).
    Тело `on<DataUpdateClear>` продолжает: `DefaultCacheManager().emptyCache();`
    — вызов **без `await`** запускает `Future<void>`, но тело обработчика,
    не дожидаясь его, сразу переходит к следующей строке.
15. `pref.setBool('have_any_language', false);` — тоже **без `await`**
    (`pref` — модуль-уровневый `late final SharedPreferences`,
    `lib/main.dart`), тоже запускает `Future<bool>`, не дожидаясь его.
16. Это была последняя строка тела обработчика — сам `async`-обработчик
    `on<DataUpdateClear>` на этом успешно завершается (его собственный
    `Future<void>` резолвится без ошибки) **раньше**, чем любой из двух
    запущенных на шагах 14–15 `Future` в принципе успевает разрешиться, тем
    более — бросить исключение. Обёртка `bloc`, описанная в шагах 8–10
    (`try { await handler(...); } catch { onError(...); rethrow; }`),
    относится только к **этому**, уже успешно завершившемуся `Future` —
    отложенное исключение из `emptyCache()`/`setBool()` наступает уже
    **после** того, как `try` вокруг `await handler(...)` успешно вышел из
    блока `try`, поэтому не попадает под этот `catch` вовсе: ни `onError`,
    ни, следовательно, `Talker` этого исключения никогда не увидят. Это
    ключевое структурное отличие от ветки (а): там исключение хотя бы
    оставляет след в `Talker` перед тем как потеряться; здесь — не
    оставляет никакого следа нигде в приложении.
17. Оба Future (`emptyCache()`'s и `setBool()`'s), если один из них
    отклоняется, становятся независимыми, никем не ожидаемыми ошибками —
    та же судьба на уровне зоны Dart, что описана в шаге 11: консольная
    диагностика, без последствий для пользователя, без падения, без
    какого-либо состояния блока.
18. Конкретно для `DefaultCacheManager().emptyCache()`: чтением
    `flutter_cache_manager-3.4.1/lib/src/cache_store.dart`
    (`CacheStore.emptyCache`, версия закреплена в `pubspec.lock`)
    подтверждено, что это не заглушка, а настоящая асинхронная
    файловая/БД-операция — `provider.getAllObjects()`, затем по каждому
    объекту `_removeCachedFile` (удаление файла с диска), затем
    `provider.deleteAll(toRemove)` (запись в собственную, отдельную от
    `AppDatabase`, БД метаданных кэша) — правдоподобный, не чисто
    гипотетический источник `FileSystemException`, если директория кэша в
    этот момент недоступна для записи или была удалена параллельно. Для
    `pref.setBool(...)` — вызов через platform channel пакета
    `shared_preferences`, тоже в принципе способный бросить
    `PlatformException`, хотя конкретного воспроизводимого триггера в этом
    коде не найдено.

### Альтернативные потоки

- **Test-зона отличается от боевой зоны.** `flutter_test` оборачивает каждый
  `test`/`testWidgets` в собственную защищённую зону, которая **действительно**
  перехватывает необработанную асинхронную ошибку и проваливает тест —
  именно поэтому в этом же репозитории уже есть устоявшийся приём для
  намеренного воспроизведения точно такого класса дефекта: обернуть
  конструирование блока и `.add(...)` в `runZonedGuarded`, чтобы поймать
  ошибку до того, как она долетит до зоны самого теста (`test/pages/unsent_animal_edit_bloc_test.dart`,
  `test/pages/animals_bloc_test.dart`, `test/pages/animal_disposal_bloc_test.dart`,
  `test/pages/animal_edit_bloc_test.dart` — все про другие блоки, не про
  `DataUpdateBloc`, но задают ровно тот приём, которым этот сценарий можно
  было бы протестировать). В `test/blocs/data_update_bloc_test.dart` такой
  обёртки сегодня нет — см. «Связанные тесты».
- **Тот же паттерн уже дважды задокументирован в `TESTING_CHECKLIST.md`.**
  Раздел «Найденные баги» уже фиксирует именно этот обработчик:
  > `lib/blocs/data_update/data_update_bloc.dart`, `DataUpdateClear` — два
  > вызова без `await`.» `DefaultCacheManager().emptyCache();` и
  > `pref.setBool('have_any_language', false);` вызываются без `await`
  > внутри `async`-обработчика. Обработчик (и с ним
  > `bloc.add(DataUpdateClear())`) завершается раньше, чем эти операции
  > реально произойдут; если `emptyCache()`/`setBool()` бросят исключение —
  > оно станет необработанным (unhandled Future rejection), а не будет
  > замечено вызывающим кодом. Это тот же паттерн, что уже найден в
  > `AnimalsRepository.updateFarmId`/`updatePlaceId` — похоже, не единичный
  > случай, а повторяющаяся привычка в проекте забывать `await` на
  > «финальных» строках `async`-функций…

  Тот же файл отдельно фиксирует и четвёртое по счёту место с этой же
  привычкой (`unsent_vaccination_cubit.dart`, `delete`/`deleteSelected`) —
  этот сценарий, таким образом, не единичный дефект, а третий
  зарегистрированный случай одного и того же повторяющегося паттерна в
  проекте.
- **Тестовый `tearDown` того же файла — первая, эмпирическая, находка того
  же факта.** `test/blocs/data_update_bloc_test.dart`'s собственный `tearDown`
  оборачивает удаление временной директории в `try/catch (_) {}` с
  комментарием: «`DataUpdateClear` вызывает
  `DefaultCacheManager().emptyCache()` без `await`
  (fire-and-forget)… его фоновая запись в `tempDir` может ещё продолжаться в
  момент удаления папки здесь. Это гонка в самой уборке temp-директории
  теста, не в проверяемой логике — ошибку игнорируем». Это независимое,
  добытое авторами теста опытным путём подтверждение того же факта,
  описанного здесь статически.
- **Двойной диспатч (шаг 2) удваивает, а не устраняет, экспозицию.**
  Поскольку оба `BlocListener<AuthBloc, AuthState>` добавляют собственное
  событие `DataUpdateClear`, а `Bloc.transformer` по умолчанию конкурентен,
  оба обработчика реально выполняются — по сути, независимо повторяя всю
  последовательность шагов 4–18 дважды на одну попытку выхода. Для ветки
  (а) — вторая попытка `clearUserData()` на уже пустых 15 таблицах либо
  тоже успешна (транзакция без ошибок на пустых таблицах), либо, если
  первая копия ещё не завершила свою `transaction()` (Drift сериализует
  выполнение внутри одного `QueryExecutor`, вторая копия просто дождётся
  своей очереди — не ошибка сама по себе). Для ветки (б) — ровно вдвое
  больше шансов столкнуться с реальным I/O-сбоем `emptyCache()`/`setBool()`,
  поскольку оба независимых вызова этих методов запускаются параллельно.
  Идемпотентность самой очистки БД делает двойной диспатч в целом
  безобидным по конечному состоянию таблиц, но не по числу «незамеченных
  Future», порождаемых одним логаутом.

### Связанные сущности

- [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate) —
  предмет этого UC: в ветке (а), если `clearUserData()` отказывает,
  таблица `DataUpdates` (как и остальные 14) **не** очищается вовсе —
  откат всей транзакции целиком, прямой контраст с
  [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md); в ветке
  (б) она, напротив, успевает очиститься (шаг 14), и предметом отказа
  становятся уже не Drift-таблицы, а Hive-флаг языка/файловый кэш.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal),
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination),
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing)
  и остальные 12 `@Clearable`-таблиц, перечисленные в
  [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md) — в ветке
  (а) все они точно так же остаются нетронутыми (откат транзакции целиком,
  не выборочно); `Vaccinations` дополнительно значима здесь как конкретное
  доказательство того, зачем нужен `PRAGMA foreign_keys = OFF` (шаг 5).
- `HANDBOOKS`/`BOARD`-справочники и [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md)
  (Device) — не затрагиваются этим сценарием ни в одной из веток, как и в
  [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md) (не
  `@Clearable`).

### Бизнес-правила

- Нет отдельного механизма ретрая/компенсации для любой из двух веток —
  единственный способ повторить попытку — новый цикл логаута/удаления
  аккаунта, который заново диспатчит `DataUpdateClear` с нуля.
- В ветке (а) невозможно частичное состояние 15 таблиц (транзакция —
  «всё или ничего»), но возможно совершенно немое расхождение между
  «пользователь считает себя вышедшим» (UI уже на экране профиля, шаг 3) и
  «предыдущий аккаунт всё ещё физически виден в локальной БД» — то самое
  расхождение, ради предотвращения которого существует
  [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) как факт.
- `DataUpdateClearSuccess` остаётся мёртвым классом состояния независимо от
  исхода (см. [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md),
  «Открытые вопросы») — успех и обе ветки отказа этого сценария
  неразличимы для остального приложения ещё сильнее, чем сам успех уже
  неразличим ни для чего: на успешном пути хотя бы нет исключения вовсе, на
  обоих ошибочных путях нет даже этого.
- Двойной диспатч (см. «Альтернативные потоки») — не осознанное бизнес-решение
  «выполнить очистку дважды для надёжности», а, по всему видимому из кода,
  побочный эффект того, что `MainPage` и `ProfilePage` независимо
  подписаны на один и тот же `AuthBloc` и оба реагируют на `AuthLogout`
  одинаковым кодом — ничем в коде не зафиксировано, что это было
  спроектировано намеренно.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет. Обе ветки прослежены статическим чтением
кода целиком, включая внутреннюю механику пакета `bloc`
(`bloc-9.0.1/lib/src/bloc.dart`) и `flutter_cache_manager`
(`flutter_cache_manager-3.4.1/lib/src/cache_store.dart`), обе версии
закреплены в `pubspec.lock`. Конкретный, эмпирически подтверждённый триггер
для самого исключения `clearUserData()` (ветка а) не найден — единственные
правдоподобные причины (сбой I/O, повреждение файла БД, гипотетическая
конкурентная запись с параллельным `DataUpdateStartAll`) не воспроизведены
ни тестом, ни на реальном устройстве; это фиксируется как открытый вопрос,
не как блокер. Возможное исправление (например, `try/catch` вокруг всего
обработчика, `await` для двух хвостовых вызовов, устранение двойного
диспатча) в рамках этого документирующего прохода не выполняется — это
фиксация уже существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateClear>` | CURRENT | весь предмет сценария — три вызова, без `try/catch`, без `emit(...)` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>`, `_emitError`, `_addDataUpdateError` | CURRENT | существуют только для другого события — ни разу не достигаются этим сценарием |
| `lib/pages/main/main_page.dart` | `BlocListener<AuthBloc, AuthState>` внутри `MainPage.build` | CURRENT | один из двух независимых диспатчеров `DataUpdateClear()` на одну эмиссию `AuthLogout`; навигация на профиль не ждёт исхода |
| `lib/pages/profile/presentation/profile_page.dart` | `BlocListener<AuthBloc, AuthState>` внутри `_ProfilePageState.build` | CURRENT | второй, независимый диспатчер `DataUpdateClear()` на ту же эмиссию `AuthLogout` |
| `lib/pages/routes.dart` | `StatefulShellRoute`, ветка `Routes.profile` | CURRENT | причина, по которой `ProfilePage` и `MainPage` смонтированы и подписаны одновременно |
| `packages/sheep_farm_database/lib/database/database.dart` | `AppDatabase.clearUserData`, `_openConnection` | CURRENT | алиас на `clearAllClearableTables`; `NativeDatabase.createInBackground` — фоновый изолят, сериализующий реальное выполнение SQL |
| `packages/sheep_farm_database/lib/database/database.clearable.dart` | `ClearableExtension.clearAllClearableTables` | CURRENT | `PRAGMA foreign_keys = OFF/ON`, одна `transaction()` — авто-откат при исключении на любом `delete(...).go()` |
| `packages/sheep_farm_database/lib/clearable/clearable_builder.dart` | `ClearableAggregateBuilder._buildOutput` | CURRENT | источник алфавитного (не по FK-графу) порядка удаления — причина, по которой `PRAGMA` небезызвестна |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations.animalId` (`REFERENCES animals(id) NOT NULL`) | CURRENT | конкретное доказательство: реальный FK-контракт, который алфавитный порядок нарушил бы без `PRAGMA OFF` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings.animalId` (`.references(Animals, #id)`) | CURRENT | второй реальный FK-контракт на `animals`; эта таблица удаляется раньше `animals`, конфликта не создала бы и без `PRAGMA` |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | единственный регистрируемый `BlocObserver` проекта — источник того, что ветка (а) хотя бы логируется |
| `lib/main.dart` | `main()` (`runApp(...)` без `runZonedGuarded`), `late final SharedPreferences pref` | CURRENT | отсутствие обёртки корневой зоны — причина, по которой необработанная ошибка любой из двух веток не имеет иного эффекта, кроме консольного вывода |
| `lib/pages/profile/presentation/widgets/profile/profile_view.dart` | `TalkerScreen` | CURRENT | единственное место в приложении, где виден лог, оставленный веткой (а) |
| `pubspec.lock` | зависимость `bloc` (`9.0.1`) | внешняя | версия пакета, чья внутренняя реализация `Bloc.on<E>`/`handleEvent` (`bloc-9.0.1/lib/src/bloc.dart`, `catch { onError(...); rethrow; }`, вызов `handleEvent();` без `await`) определяет судьбу исключения из ветки (а) |
| `pubspec.lock` | зависимость `talker_bloc_logger` (`5.0.1`) | внешняя | `TalkerBlocObserver.onError` (`talker_bloc_logger_observer.dart`) — единственная точка, реально логирующая ветку (а) |
| `pubspec.lock` | зависимость `flutter_cache_manager` (`3.4.1`) | внешняя | `CacheStore.emptyCache` (`cache_store.dart`) — настоящая асинхронная файловая/БД-операция, предмет ветки (б) |

## Критерии приёмки

- Если `await _appDatabase.clearUserData()` внутри `on<DataUpdateClear>`
  бросает исключение любого типа, ни одна из 15 `@Clearable`-таблиц не
  остаётся частично очищенной (Drift откатывает `transaction()` целиком).
- То же исключение (ветка а) один раз попадает в лог `Talker` через
  `Bloc.observer.onError` (`TalkerBlocObserver`), после чего становится
  необработанной ошибкой `Future` уровня зоны Dart — без `DataUpdateFailure`,
  без строки в `DataUpdates`, без какого-либо сообщения пользователю.
- Если вместо этого отказывает `DefaultCacheManager().emptyCache()` или
  `pref.setBool('have_any_language', false)` (ветка б) — 15 таблиц к этому
  моменту уже успешно очищены; само исключение не проходит через
  `Bloc.observer.onError`/`Talker` вовсе и становится необработанной
  ошибкой `Future`, не оставляя следа нигде в приложении.
- Ни в одной из двух веток не эмитится ни одно состояние `DataUpdateBloc` —
  `state` остаётся таким же, каким было до диспатча `DataUpdateClear`.
- Переход на экран профиля/входа (`MainPage`'s обработчик `AuthLogout`)
  происходит независимо от исхода любой из двух копий `DataUpdateClear`
  (двойной диспатч, шаг 2) — пользователь не получает никакого визуального
  отличия между успехом и любой из двух веток отказа.

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` содержит единственный
тест на это событие — `blocTest('DataUpdateClear очищает пользовательские
данные БД', ...)` (прямой верхнеуровневый `blocTest`, без `group()`, без
номера use-case в названии на сегодня — присвоение номера этому тесту
делается отдельным проходом, не этим документом). Тест использует реальный
in-memory `AppDatabase` (`registerTestGetIt()` → `createTestDatabase()`) и
проверяет только `pref.getBool('have_any_language')` после успешного
прогона — ни `clearUserData()`, ни `emptyCache()`/`setBool()` не форсируются
на исключение ни в этом, ни в каком-либо другом тесте репозитория
(`grep -rn "DataUpdateClear" test/` — единственное совпадение, этот же
файл). Ни двойной диспатч (шаг 2), ни ветка (а), ни ветка (б) не
воспроизведены тестом.

Проект уже располагает готовым приёмом для написания такого теста —
`runZonedGuarded` вокруг конструирования блока/`.add(...)`, как в
`test/pages/unsent_animal_edit_bloc_test.dart`/`animals_bloc_test.dart`/
`animal_disposal_bloc_test.dart`/`animal_edit_bloc_test.dart` (см.
«Альтернативные потоки») — но ни один из этих файлов не относится к
`DataUpdateBloc`.

## Открытые вопросы и ограничения

- **Конкретный триггер ветки (а) не подтверждён эмпирически.** FK-конфликт
  структурно исключён (`PRAGMA foreign_keys = OFF`, обоснование — шаг 5);
  сбой I/O диска и гипотетическая конкурентная запись рассмотрены как
  правдоподобные, но ни один не воспроизведён ни тестом, ни на реальном
  устройстве. Возможно, что в реальной эксплуатации эта ветка на практике
  никогда не срабатывает — оценка вероятности вне рамок этого
  документирующего прохода.
- **Двойной диспатч `DataUpdateClear` (шаг 2) не упомянут ни в
  [EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md), ни в
  [UC-191](UC-191-ACTOR-1-EVT-95-ENT-23-DELETE_OK-IN-SYSTEM.md).** Найден
  при подготовке именно этого документа (чтением `profile_page.dart` вместе
  с `routes.dart`) — не зафиксировано, было ли это учтено при написании
  события, или это самостоятельная новая находка. Само по себе не является
  ERROR-сценарием (оба диспатча по отдельности идемпотентны на пустых
  таблицах), но удваивает окно, в котором могла бы проявиться любая из двух
  веток этого документа.
- **Talker-лог ветки (а) виден только тому, кто явно откроет `TalkerScreen`
  из профиля** — то есть практически только разработчику/QA, не обычному
  пользователю; для обычного пользователя обе ветки (а) и (б) неотличимы по
  наблюдаемому эффекту (никакого).
- **`runZonedGuarded` в `main()` отсутствует не только для этого сценария** —
  как показывает `grep`, во всём `lib/` нет ни одной точки, ловящей
  необработанные асинхронные ошибки корневой зоны; это системное, не
  специфичное для `DataUpdateClear` свойство приложения, отдельно
  подтверждённое здесь для полноты, не предмет исправления этим документом.
- Не проверено эмпирически на реальном устройстве/сборке — вывод сделан
  статическим чтением кода (`DataUpdateBloc.on<DataUpdateClear>` →
  `AppDatabase.clearUserData` → `ClearableExtension.clearAllClearableTables`;
  `bloc-9.0.1/lib/src/bloc.dart`; `flutter_cache_manager-3.4.1/lib/src/cache_store.dart`),
  не запущенным тестом с форсированным исключением (см. «Связанные тесты» —
  TBD).
