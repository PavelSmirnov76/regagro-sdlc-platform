# UC-96 — Хаб неотправленных взвешиваний («В работе») отказывает технически: `AnimalWeighingsCubit.loadNotSync` бросает исключение необработанным

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md)
(`animal_weighings.viewed_unsent`): пользователь открывает хаб ещё не
отправленных взвешиваний (обычно со сводного экрана «В работе»), а
`AnimalWeighingsCubit.loadNotSync`
(`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`)
бросает исключение при попытке прочитать строки `AnimalWeighing` с
`sync == false` — техническая ошибка (Drift/БД), не бизнес-отказ. **Как и у
`load()` (см. [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)),
здесь тоже нет `try/catch`** — перепроверено чтением метода целиком:
`loadNotSync()` эмитит `AnimalWeighingsState.loading()`, затем без единого
`try` идёт три последовательных `await` (репозиторий взвешиваний, затем в
цикле — репозиторий животных и, при наличии `unitId`, репозиторий единиц
измерения) и лишь в конце — финальный `emit(AnimalWeighingsState.loadedNotSync(...))`.
Исключение из любого из этих `await` пробрасывается наружу необработанным,
подтверждено существующим тестом (`getAllNotSuncAnimalWeighings` замокан на
`thenThrow`, ловится только `expectLater(..., throwsA(...))` со стороны
теста, не самим кубитом).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`
целиком: `AnimalWeighingsCubit` объявляет только четыре зависимости
(`_animalWeightingsRepository`, `_animalsRepository`, `_unitsRepository`,
`_placesRepository`) и не использует `AuthRepository` ни в одном методе,
включая `loadNotSync` — доступ к хабу неотправленных взвешиваний не зависит
от статуса авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`,
   `lib/pages/in_work/in_work_page.dart`) и тапает по плитке взвешивания
   (`EventTileData(... value: l10n.weighing, count: data.animalWeighingsCount,
   onTap: () => context.pushNamed2(Routes.unsentAnimalWeighings))`).
2. Открывается `UnsentAnimalWeighingsPage`
   (`lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart`,
   маршрут `Routes.unsentAnimalWeighings`, `lib/pages/routes.dart`). `build`
   создаёт `BlocProvider(create: (context) => AnimalWeighingsCubit()..loadNotSync(),
   ...)` — вызов `loadNotSync()` через каскадный оператор (`..`) не
   awaited колбэком `create`: `create` возвращает сам объект `AnimalWeighingsCubit`
   синхронно, а `Future<void>`, который вернул бы `loadNotSync()`, нигде не
   сохраняется и не ожидается — выполнение метода продолжается в фоне,
   независимо от построения виджета.
3. `AnimalWeighingsCubit.loadNotSync()` сразу эмитит
   `const AnimalWeighingsState.loading()` — единственный `emit` до конца
   метода либо до сбоя.
4. Метод вызывает `await _animalWeightingsRepository.getAllNotSuncAnimalWeighings()`
   (`lib/repositories/animal_weighing/animal_weighings_repository.dart` →
   `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` — тонкая обёртка
   `dao.getAllNotSuncAnimalWeighings()`, без `try/catch`) →
   `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart`
   → `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` — прямой Drift-select
   `(selectCurrent()..where((tbl) => tbl.sync.isValue(false))).get()`.
5. **Точка технического сбоя (этот сценарий).** Вызов бросает исключение — в
   тесте (`test/pages/animal_weighings_cubit_test.dart`) это воспроизводится
   на уровне репозитория:
   `when(() => animalWeighingsRepository.getAllNotSuncAnimalWeighings()).thenThrow(...)`
   (тот же приём, что и в UC-94 для `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`).
   `loadNotSync()` не обёрнут в `try/catch` — исключение пробрасывается из
   метода необработанным: возвращаемый им `Future<void>` отклоняется этим же
   исключением, ни следующая строка цикла, ни финальный `emit(AnimalWeighingsState.loadedNotSync(...))`
   не выполняются.
6. Отклонение распространяется наружу метода, но никто его не ожидает: шаг 2
   уже установил, что `create: (context) => AnimalWeighingsCubit()..loadNotSync()`
   не хранит и не awaits `Future`, возвращённый `loadNotSync()` — рождается
   необработанное отклонение `Future` (`unhandled Future rejection`) в
   текущей Dart Zone. `lib/main.dart` вызывает `runApp(const MyApp())`
   напрямую — строка `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const
   MyApp()), (error, stack) { getIt<Talker>().handle(error, stack); });`
   закомментирована целиком, приложение не оборачивает своё выполнение в
   `runZonedGuarded`/эквивалент с собственным обработчиком — точно та же
   инфраструктурная находка, что и в
   [UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md) и в
   [UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md).
7. Состояние кубита остаётся `AnimalWeighingsState.loading()` навсегда — это
   единственный `emit`, который успел выполниться. `AnimalWeighingsState`
   (`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart`)
   — freezed-union из ровно четырёх вариантов (`initial`/`loading`/`loaded`/
   `loadedNotSync`); варианта `error` не существует вовсе, эмитить его было
   бы некуда, даже если бы метод был обёрнут в `try/catch`.
8. `UnsentAnimalWeighingsPage`'s `BlocBuilder` реагирует на `state` через
   `switch`: ветка `AnimalWeighingsLoading()` (и запасная `_ =>`) рендерят
   `BottomSheetPageWrapper(child: Center(child: CustomLottieLoader(size:
   CustomLottieLoaderSize.small)))` — экран остаётся на спиннере навсегда,
   без какого-либо сообщения об ошибке.
9. Единственный способ выйти из этого состояния — уйти со страницы (стандартная
   кнопка «назад» `AppBar`, которую подставляет `CustomAppBar`, — она
   доступна, пока `Navigator` может выполнить `pop`, что верно для этого
   маршрута, открытого через `pushNamed2` с `InWorkPage`) и заново открыть
   хаб из `InWorkPage`, что создаёт новый `AnimalWeighingsCubit` и заново
   вызывает `loadNotSync()` — при устойчивой (не преходящей) причине сбоя
   результат идентичен.

### Альтернативные потоки

- **Второй вызов того же метода из того же экрана подвержен тому же
  дефекту.** `AnimalWeighingListNotSyncWidget.onTap` внутри
  `UnsentAnimalWeighingsPage.build` определён как:
  ```dart
  onTap: (aw) async {
    final result = await context.pushNamed2<bool?>(
      Routes.weighAnimal,
      extra: WeighAnimalPageArguments(
        animalId: aw.animalId,
        animalWeighingId: aw.id,
      ),
    );
    if (!context.mounted) return;
    if (result == true) {
      await context.read<AnimalWeighingsCubit>().loadNotSync();
    }
  }
  ```
  Тап по строке открывает правку взвешивания; при успешном возврате
  (`result == true`) страница вызывает `loadNotSync()` повторно, на этот раз
  формально `await`-нув его. Но сама эта `async`-функция передана как
  значение параметра `onTap` типа `void Function(AnimalWeighing animalWeighing)`
  (`AnimalWeighingListNotSyncWidget`, обычный Flutter-паттерн `async`-замыкания
  на месте `VoidCallback`-подобного колбэка) — вызывающий её `_WeighingCard`
  (`InkWell.onTap`) не ожидает и не может ожидать возвращённый ею `Future`.
  Если исключение брошено на этом втором вызове `loadNotSync()`, оно точно
  так же становится необработанным отклонением `Future` в текущей Zone — тот
  же сценарий, что и в основном потоке, просто с другой точкой входа
  (возврат из `WeighAnimalPage` вместо первичного открытия хаба).
- **Тот же сбой мог произойти и внутри цикла по строкам, а не только на
  первом чтении.** После успешного `getAllNotSuncAnimalWeighings()` метод
  для каждой строки вызывает `await _animalsRepository.getAnimalWithDetailsById(animalWeighing.animalId)`
  и, если `unitId != null`, `await _unitsRepository.getById(animalWeighing.unitId!)`
  — оба вызова находятся внутри того же необёрнутого тела метода; исключение
  из любого из них приводит к точно такому же необработанному отклонению и
  тому же зависанию на `AnimalWeighingsState.loading()`, просто позже в
  выполнении метода (после того как первый репозиторий уже вернул непустой
  список). Существующий тест (см. «Связанные тесты») мокает сбой только на
  уровне первого чтения.
- **Частичный успех первого чтения не помогает.** Поскольку `emit` вызван
  только один раз в начале метода, даже если `getAllNotSuncAnimalWeighings()`
  успешно вернул список и сбой произошёл только на построении деталей одной
  из строк цикла, пользователь не увидит вообще ничего из уже прочитанных
  данных — весь результат теряется вместе с необработанным исключением.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  целевая сущность чтения; при сбое ни одна строка с `sync == false` не
  попадает в UI, независимо от того, сколько их было в БД.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается через
  `_animalsRepository.getAnimalWithDetailsById(animalWeighing.animalId)` для
  каждой строки взвешивания (используется для отображения номера животного в
  `AnimalWeighingListNotSyncWidget`/`_WeighingCard`); не изменяется, само по
  себе может быть источником исключения (см. «Альтернативные потоки»).
- `Unit` ([ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md),
  HANDBOOKS) — читается условно, только когда `animalWeighing.unitId != null`,
  через `_unitsRepository.getById(...)`; не изменяется.

### Бизнес-правила

- Технический сбой (исключение из чтения `AnimalWeighing`/`Animal`/`Unit`)
  классифицируется как `READ_ERROR`, а не `READ_REJECTED` — сценарий не
  содержит ни одного бизнес-guard'а: `loadNotSync()` либо строит список из
  того, что прочитано, либо технически падает целиком.
- `AnimalWeighingsCubit.loadNotSync` — ни первый (навигация из «В работе»),
  ни второй (повторный вызов после успешной правки взвешивания) вызов — не
  перехватывает исключение; оба разделяют одну и ту же необработанную
  Future-цепочку до `main.dart`.
- Один и тот же freezed-union `AnimalWeighingsState` не имеет варианта
  `error` вовсе — даже гипотетическое добавление `try/catch` в `loadNotSync`
  потребовало бы сначала добавить такой вариант в state, которого сегодня
  нет ни у этого метода, ни у `load()` ([UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных потока (второй вызов из
`onTap`-колбэка после правки; сбой внутри цикла по деталям строки, а не
только на первом чтении) прослеживаются чтением
`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`,
`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart`,
`lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart`,
`lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart`,
`lib/pages/in_work/in_work_page.dart`,
`lib/repositories/animal_weighing/animal_weighings_repository.dart`,
`packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart`
и `lib/main.dart`. Отсутствие `try/catch` вокруг `loadNotSync`, отсутствие
`await`/сохранения `Future` со стороны `create: (context) =>
AnimalWeighingsCubit()..loadNotSync()` и то, что `runTalkerZonedGuarded` в
`lib/main.dart` закомментирован, перепроверены чтением исходников напрямую,
а не восстановлены по памяти или скопированы из
[UC-94](UC-94-ACTOR-5-EVT-47-ENT-15-READ_ERROR-IN-ANIMAL.md).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | единственная точка сценария; один `emit(loading())` в начале, три необёрнутых `await` подряд (репозиторий взвешиваний, затем в цикле — животные и, условно, единицы измерения), без `try/catch` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState` (`initial`/`loading`/`loaded`/`loadedNotSync`) | CURRENT | freezed-union без варианта `error` — кубит физически не может сообщить об ошибке через состояние |
| `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart` | `UnsentAnimalWeighingsPage.build` | CURRENT | `create: (context) => AnimalWeighingsCubit()..loadNotSync()` — каскад не сохраняет и не awaits возвращённый `Future`; второй вызов `loadNotSync()` — в `onTap`-колбэке после успешной правки, тоже без внешнего awaiter'а из-за сигнатуры `VoidCallback`-подобного параметра |
| `lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart` | `AnimalWeighingListNotSyncWidget`, `onTap` (тип `void Function(AnimalWeighing animalWeighing)`) | CURRENT | сигнатура параметра, из-за которой `async`-замыкание вызывающей страницы не может быть awaited изнутри виджета |
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (`EventTileData` плитки взвешивания) | CURRENT | точка входа — `onTap: () => context.pushNamed2(Routes.unsentAnimalWeighings)` |
| `lib/pages/routes.dart` | `Routes.unsentAnimalWeighings` | CURRENT | константа имени/пути маршрута |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` | CURRENT | тонкая обёртка `dao.getAllNotSuncAnimalWeighings()`, без `try/catch` — протестированная (мокнутая) точка сбоя |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` | CURRENT | реальная (немокнутая) реализация — прямой Drift-select по `sync == false` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | вызывается в цикле для каждой строки; альтернативная (непротестированная) точка сбоя того же необёрнутого метода |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository.getById` | CURRENT | вызывается в цикле условно (`unitId != null`); альтернативная (непротестированная) точка сбоя |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` вызывается напрямую; вызов `runTalkerZonedGuarded(...)` с обработчиком `getIt<Talker>().handle(error, stack)` закомментирован целиком — необработанное отклонение `Future` не попадает ни в один явный error-handler приложения |

## Критерии приёмки

- При исключении из `_animalWeightingsRepository.getAllNotSuncAnimalWeighings()`
  внутри `AnimalWeighingsCubit.loadNotSync()` метод не перехватывает его —
  возвращаемый `Future<void>` отклоняется тем же исключением
  (`throwsA(isA<Exception>())`).
- До этой точки эмитится ровно одно состояние —
  `const AnimalWeighingsState.loading()`; финальный
  `emit(AnimalWeighingsState.loadedNotSync(...))` не выполняется.
- То же самое верно при исключении из `_animalsRepository.getAnimalWithDetailsById`
  или (условно) `_unitsRepository.getById` внутри цикла построения деталей —
  один и тот же необёрнутый метод, без ветвления по источнику.
- `UnsentAnimalWeighingsPage`, построенная поверх этого кубита, остаётся на
  `AnimalWeighingsLoading()`/спиннере (`CustomLottieLoader`) бессрочно — ни
  один вариант `AnimalWeighingsState` не несёт сообщения об ошибке.
- Повторный вызов `loadNotSync()` (из `create` при первом открытии либо из
  `onTap` после правки взвешивания) возможен только через полное пересоздание
  `AnimalWeighingsCubit`/страницы либо через тот же `onTap`-путь — в обоих
  случаях исключение распространяется тем же необработанным образом.

## Связанные тесты

- `test/pages/animal_weighings_cubit_test.dart`, group
  `'UC-95 — AnimalWeighingsCubit.loadNotSync (В работе, глобальный список
  неотправленных)'` — в текущем виде группа содержит только два теста, оба
  `READ_OK`: `'успех -> сортирует по дате, unit только при unitId, placeName
  не резолвится'` и `'пустой список -> loadedNotSync с пустым списком'`; ни
  один из них не мокает исключение. (Групповое имя со старым номером
  `UC-133` — идентификатор будет переименован отдельным проходом; сам файл
  проверен полностью через `grep`/`Read` — теста на `ERROR`-исход `loadNotSync`
  нет нигде в файле.)
- **TBD — теста нет** на `READ_ERROR`-исход `loadNotSync()` — ни для сбоя на
  `getAllNotSuncAnimalWeighings()`, ни для сбоя внутри цикла
  (`getAnimalWithDetailsById`/`getById`).
- **TBD — теста нет** на поведение `UnsentAnimalWeighingsPage`/
  `AnimalWeighingListNotSyncWidget` в подвисшем состоянии `loading` (в
  `test/` нет widget-теста ни для одного из этих файлов) — вывод о
  бессрочном спиннере сделан по чтению кода `switch` в `build`, а не по
  запуску приложения.
- **TBD — теста нет** на второй вызов `loadNotSync()` из `onTap`-колбэка
  после успешной правки взвешивания (`result == true`) и на распространение
  исключения именно с этой точки входа.

## Открытые вопросы и ограничения

- **Реальное поведение необработанного отклонения `Future` из `create:`
  каскада и из `async`-замыкания `onTap` в запущенном приложении не
  проверено ни одним widget/integration-тестом.** Из чтения `lib/main.dart`
  (`runApp` без `runZonedGuarded`/`runTalkerZonedGuarded`) следует, что оно
  не попадает ни в `Talker`, ни в явный обработчик приложения — но точный
  наблюдаемый эффект (тихо теряется в консоли, показывает framework-овый
  красный экран в debug-сборке, или иное, специфичное для версии
  Flutter/Dart) не подтверждён запуском самого приложения, только чтением
  кода и семантики Dart Zones/Futures. Тот же открытый вопрос уже
  зафиксирован для соседних сценариев
  ([UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)).
- **Почему ни `load()`, ни `loadNotSync()` не получили `try/catch` и
  `error`-вариант состояния?** `AnimalWeighingsState` — freezed-union без
  единого варианта `error` в принципе, в отличие от, например,
  `VaccinationReportState.error` ([UC-82](UC-82-ACTOR-5-EVT-41-ENT-14-READ_ERROR-IN-ANIMAL.md)).
  Ничего в коде/комментариях не объясняет, является ли отсутствие такого
  варианта преднамеренным решением или недосмотром — сегодняшняя находка
  ENT-15 фиксирует только отсутствие `try/catch` в трёх «сохраняющих»
  методах (`saveWeighing`/`saveEditedWeighing`/финальный шаг), не
  распространяя её явно на read-методы `load`/`loadNotSync`; этот use-case
  расширяет ту же находку на чтение.
- **Единственный выход из подвисшего экрана — уйти и открыть хаб заново.**
  Ни `RefreshIndicator`, ни явной кнопки «повторить» в
  `UnsentAnimalWeighingsPage` нет — при устойчивой причине сбоя повторное
  открытие приведёт к тому же результату.
- **Второй вызов `loadNotSync()` (после успешной правки) технически
  `await`-нут внутри своего `async`-замыкания, но само замыкание передаётся
  как `void Function(...)`-колбэк и потому не awaited снаружи** — с точки
  зрения распространения исключения это эквивалентно первому вызову из
  `create`, просто по другой причине (сигнатура типа параметра, а не
  каскадный оператор); не подтверждено отдельным тестом.
