# UC-94 — Просмотр истории взвешиваний животного: репозиторий бросает исключение, `AnimalWeighingsCubit.load` не перехватывает его вообще

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же триггер, что в успешном сценарии [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md)
(`AnimalWeighingsCubit.load`) — пользователь открывает вкладку взвешиваний
карточки животного — но один из репозиториев, к которым обращается `load()`,
бросает исключение. В отличие от вакцинаций
([UC-78](UC-78-ACTOR-5-EVT-39-ENT-14-READ_ERROR-IN-ANIMAL.md),
`AnimalVaccinationsCubit.load`) и отчёта по перемещениям
(`MovementReportCubit.load`), у `AnimalWeighingsCubit.load` **нет вообще
никакого `try/catch`** вокруг тела метода. Исключение не перехватывается, не
логируется через `Talker`, и не превращается ни в какое состояние кубита —
`Future`, возвращаемый вызовом `load(animalId)`, просто отклоняется этим же
исключением. Проверено отдельно и для `loadNotSync()` (метод того же
кубита, используемый экраном «В работе» с хаба неотправленных) — структурно
идентичен: тоже без единого `try/catch`. Разницы между `load()` и
`loadNotSync()` в обработке ошибок нет — оба метода одинаково не защищены,
вопреки предположению, что раз один из них специфицируется отдельно, у него
может быть иная обработка.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `AnimalWeighingsCubit` не
объявляет и не использует `AuthRepository` ни в одном методе.

## CURRENT

### Основной поток

1. Пользователь на карточке животного открывает вкладку взвешиваний —
   переход на `Routes.animalWeighings` с `AnimalWeighingsPageArguments
   (animalId: ...)` (единственная точка входа, сборка страницы —
   `AnimalWeighingsPage.build`,
   `lib/pages/animal_weighings/pages/animal_weighings_page.dart`).
2. `AnimalWeighingsPage.build` создаёт `BlocProvider(create: (context) =>
   AnimalWeighingsCubit()..load(animalId))`. Каскадный оператор `..load(...)`
   возвращает сам объект `AnimalWeighingsCubit` (не `Future`, который вернул
   бы вызов `load`) — `create` завершается синхронно и штатно независимо от
   того, чем впоследствии закончится асинхронное выполнение `load()`;
   виджет-дерево (`_AnimalWeighingsBody` → `BlocBuilder` →
   `AnimalWeighingLoadingWidget`) строится нормально.
3. `AnimalWeighingsCubit.load(animalId)`:
   ```dart
   Future<void> load(int animalId) async {
     emit(const AnimalWeighingsState.loading());

     final animalWeighings = await _animalWeightingsRepository
         .getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc([animalId]);

     final animal = await _animalsRepository.getAnimalWithDetailsById(animalId);

     final place = await _placesRepository.getById(animal?.animal.placeId);

     final animalWeighingWithDetails = <AnimalWeighingWithDetails>[];

     for (final animalWeighing in animalWeighings) {
       animalWeighingWithDetails.add(
         AnimalWeighingWithDetails(
           animalWeighing: animalWeighing,
           animal: await _animalsRepository.getAnimalWithDetailsById(
             animalWeighing.animalId,
           ),
           unit: animalWeighing.unitId != null
               ? await _unitsRepository.getById(animalWeighing.unitId!)
               : null,
         ),
       );
     }
     // ... сортировка, emit(loaded(...))
   }
   ```
   Первая строка (`emit(loading())`) выполняется синхронно ещё до первой
   строки, которая может бросить исключение — состояние кубита переходит в
   `AnimalWeighingsLoading` гарантированно.
4. Один из четырёх обращений к репозиториям бросает исключение:
   `_animalWeightingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
   `_animalsRepository.getAnimalWithDetailsById` (вызывается дважды — один
   раз для самого животного вкладки, второй раз внутри цикла на каждую
   строку взвешивания; оба вызова идентичны по последствиям),
   `_placesRepository.getById`, или `_unitsRepository.getById` внутри цикла.
   Метод целиком не обёрнут ни в один `try/catch` — исключение
   останавливает выполнение немедленно в точке броска.
5. Ни `animalWeighingWithDetails.sort(...)`, ни финальный `emit(
   AnimalWeighingsState.loaded(...))` не выполняются. Состояние кубита
   остаётся `AnimalWeighingsLoading` — тем самым, что было выставлено
   на шаге 3 — навсегда, если ничто не вызовет `load`/`loadNotSync` заново.
6. `Future<void>`, возвращаемый вызовом `load(animalId)`, отклоняется этим же
   исключением. Поскольку в шаге 2 он вызван каскадом (`..load(animalId)`) и
   нигде не awaited и не имеет `.catchError`, это — необработанное отклонение
   `Future` («fire-and-forget»): оно не долетает ни до `BlocProvider`, ни до
   `BlocBuilder`, ни до какого-либо явного обработчика приложения.
7. `lib/main.dart`: `main()` вызывает `runApp(const MyApp())` напрямую;
   строка `runTalkerZonedGuarded(getIt<Talker>(), () => runApp(const
   MyApp()), (error, stack) { getIt<Talker>().handle(error, stack); });`
   закомментирована целиком — приложение не оборачивает своё выполнение в
   `runZonedGuarded` с собственным обработчиком. Необработанное отклонение
   `Future` из шага 6 не попадает ни в `Talker`, ни в какой-либо другой явный
   error-handler приложения.
8. Наблюдаемый пользователем эффект — **не** сбой построения экрана (дерево
   виджетов уже было построено на шаге 2, до того, как исключение вообще
   произошло) и **не** крах приложения: `BlocBuilder` продолжает
   отображать `AnimalWeighingLoadingWidget` (`Center(child:
   CircularProgressIndicator())`) неограниченно долго, потому что состояние
   кубита так и не покидает `AnimalWeighingsLoading`. На экране нет ни
   кнопки повтора, ни какого-либо текста ошибки — только вечный спиннер.

### Альтернативные потоки

- **Повторный вызов через `activate()`.** `_AnimalWeighingsBodyState`
  переопределяет `activate()` (редкое событие жизненного цикла — виджет
  повторно вставлен в дерево, например при смене позиции в дереве по
  `GlobalKey`) и безусловно вызывает `context.read<AnimalWeighingsCubit>()
  .load(widget.animalId)` заново — тем же незащищённым способом (тоже без
  `await` со стороны вызывающего кода, тоже без перехвата исключения). При
  повторном срабатывании этого коллбэка на фоне уже показанного вечного
  спиннера ничего не меняется: кубит снова эмитит `loading()`, затем снова
  падает на том же (или другом) обращении к репозиторию.
- **Сбой на разных из четырёх обращений к репозиторию даёт идентичный
  результат.** Код не различает, какая именно зависимость бросила
  исключение — `AnimalWeighingsRepository`, `AnimalsRepository`,
  `PlaceRepository` или `UnitsRepository`; во всех четырёх случаях эффект
  один и тот же (шаги 4–8 основного потока).
- **`loadNotSync()` того же кубита (используется `UnsentAnimalWeighingsPage`,
  хаб «В работе») ведёт себя идентично при аналогичном сбое** — тоже без
  `try/catch`, тоже отклоняет свой `Future` необработанным. Единственное
  отличие в вызывающем коде: `UnsentAnimalWeighingsPage` тоже вызывает его
  через каскад (`AnimalWeighingsCubit()..loadNotSync()`), без `await` —
  тот же паттерн «fire-and-forget», тот же итоговый вечный спиннер на своём
  экране. Отдельный use-case для этого сценария (`loadNotSync`) —
  [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md), не
  этот файл.
- **Сравнение с Vaccination ([UC-78](UC-78-ACTOR-5-EVT-39-ENT-14-READ_ERROR-IN-ANIMAL.md)).**
  `AnimalVaccinationsCubit.load` при том же виде сбоя (исключение в
  репозитории) **перехватывает** его собственным `try/catch`, логирует через
  `getIt<Talker>().error(...)` и эмитит `AnimalVaccinationsState.loaded(...,
  vaccinations: [])` — `Future`, возвращаемый `load()`, успешно резолвится
  (`completes`, не `throwsA`), а экран показывает пустой список вместо
  вечного спиннера. С точки зрения пользователя оба сценария одинаково не
  показывают явного сообщения об ошибке, но технически это два разных
  дефекта: у Vaccination ошибка тихо проглатывается (Future успешен, но
  информация потеряна), у Weighing ошибка вообще не перехватывается (Future
  падает, экран зависает).
- **Сравнение с Movement (`MovementReportCubit.load`,
  `lib/pages/movement_report/cubit/movement_report_cubit.dart`).** Этот
  cubit — отчёт по перемещениям, ближайший в кодовой базе аналог «просмотра
  истории» для Movement — тоже оборачивает тело `load()` в `try/catch` и при
  исключении явно эмитит `MovementReportState.error(e.toString())` —
  отдельное, видимое состояние, которое `_Body`/`build` экрана отчёта может
  показать пользователю. И Vaccination, и Movement, таким образом, гарантируют
  завершение своего `load()` без пробрасывания исключения наружу; Weighing —
  нет.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  сущность, которую пытается прочитать сценарий; при сбое ни одна запись
  этого животного не попадает в UI, независимо от того, сколько их реально
  есть в БД.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается дважды
  за вызов `load()`: один раз для самого животного вкладки (используется
  только для получения `placeId`), второй раз — на каждую строку
  взвешивания внутри цикла (`AnimalWeighingWithDetails.animal`); сбой на
  любом из этих чтений одинаково обрывает весь метод.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается на каждую строку взвешивания, только если
  `unitId != null`; сбой здесь — тот же итоговый эффект.
- Место (`Farm`/`Place`, модуль [FARM](../modules/MOD-3-FARM.md)) — читается
  через `PlaceRepository.getById(animal?.animal.placeId)` для заголовка
  экрана (`placeName`); сбой здесь — тот же итоговый эффект, хотя сама эта
  сущность не специфицирована отдельным `ENT` в модуле ANIMAL.

### Бизнес-правила

- **НАХОДКА — полное отсутствие обработки исключений.**
  `AnimalWeighingsState` — freezed-union из четырёх вариантов
  (`initial`/`loading`/`loaded`/`loadedNotSync`), в нём нет варианта
  «ошибка». Но, в отличие от вакцинаций (где такой вариант тоже отсутствует,
  но код всё равно гарантированно приходит к `loaded` с пустым списком),
  здесь код при сбое вообще не доходит ни до какого `emit` после
  `loading()` — кубит физически не может показать «пусто» вместо «ошибка»,
  он просто останавливается на `loading` навсегда.
- **Экран строится нормально, зависает, а не падает.** `BlocProvider.create`
  — синхронный колбэк; каскад `..load(animalId)` возвращает объект кубита,
  а не `Future` вызова `load`, поэтому построение виджет-дерева не зависит
  от исхода асинхронного `load()`. Сбой проявляется как вечный спиннер, а
  не как ошибка построения дерева виджетов.
- **Необработанное исключение теряется полностью молча.** `lib/main.dart`
  не оборачивает `runApp` в `runZonedGuarded`/`runTalkerZonedGuarded` (вызов
  `runTalkerZonedGuarded` закомментирован целиком) — исключение из
  «fire-and-forget» вызова `load()`/`loadNotSync()` не попадает ни в
  `Talker`, ни в какой-либо иной обработчик приложения.
- **`load()` и `loadNotSync()` одинаково не защищены** — нет асимметрии
  между экраном истории взвешиваний животного и хабом «В работе»: оба пути
  этого кубита ведут себя идентично при сбое репозитория.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий (отсутствие `try/catch`, отклонение `Future`,
отсутствие логирования, вечный спиннер на экране) прослеживается по
существующему коду полностью, без пробелов, требующих уточнения у
пользователя. Единственная содержательная неопределённость (реальное
наблюдаемое поведение необработанного отклонения `Future` в запущенном
приложении, а не только по семантике Dart Zones) зафиксирована в «Открытые
вопросы и ограничения», не как пробел документации.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `AnimalWeighingsPage.build` | CURRENT | точка входа — `BlocProvider(create: (context) => AnimalWeighingsCubit()..load(animalId))`; каскад не awaited |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `_AnimalWeighingsBodyState.activate` | CURRENT | повторно вызывает `load(widget.animalId)` тем же незащищённым способом на редком событии жизненного цикла |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `_AnimalWeighingsBodyState.build` (`BlocBuilder`) | CURRENT | рендерит `AnimalWeighingLoadingWidget` для `AnimalWeighingsInitial`/`AnimalWeighingsLoading`/`default`-ветки — остаётся на этом состоянии неограниченно долго, если `load()` падает |
| `lib/pages/animal_weighings/widgets/animal_weighing_loading_widget.dart` | `AnimalWeighingLoadingWidget` | CURRENT | `Center(child: CircularProgressIndicator())` — единственное, что видит пользователь на этом пути |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.load` | CURRENT | ядро сценария — без `try/catch` вокруг всех четырёх обращений к репозиториям |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | структурно идентичен `load()` по отсутствию обработки ошибок — проверено отдельно, разницы нет |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState` (`initial`/`loading`/`loaded`/`loadedNotSync`) | CURRENT | freezed-union без варианта «ошибка»; при сбое ни один из четырёх вариантов не эмитится после `loading` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | тонкий passthrough в DAO, без собственного `try/catch` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | Drift `SELECT ... WHERE animal_id IN (...) ORDER BY weighing_date`, без `try/catch` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | вызывается дважды за один `load()` (заголовок вкладки + на каждую строку цикла); сбой любого вызова одинаково обрывает метод |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById` | CURRENT | резолвит место животного для `state.placeName` |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository.getById` | CURRENT | резолвит единицу измерения строки, только если `unitId != null` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit.load` | CURRENT | контрастный сосед ([UC-78](UC-78-ACTOR-5-EVT-39-ENT-14-READ_ERROR-IN-ANIMAL.md)) — перехватывает исключение, логирует, эмитит `loaded([])`; `Future` резолвится успешно |
| `lib/pages/movement_report/cubit/movement_report_cubit.dart` | `MovementReportCubit.load` | CURRENT | контрастный сосед — перехватывает исключение, эмитит явное `MovementReportState.error(...)` |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` вызывается напрямую; вызов `runTalkerZonedGuarded(...)` с обработчиком `getIt<Talker>().handle(error, stack)` закомментирован целиком — необработанные асинхронные исключения не попадают ни в один явный error-handler приложения |

## Критерии приёмки

- Если любой из четырёх репозиториев, к которым обращается
  `AnimalWeighingsCubit.load(animalId)`
  (`AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
  `AnimalsRepository.getAnimalWithDetailsById`, `PlaceRepository.getById`,
  `UnitsRepository.getById`), бросает исключение, `load(animalId)` не
  перехватывает его — возвращаемый `Future<void>` отклоняется тем же
  исключением (`throwsA(...)`, а не `completes`).
- Состояние кубита после такого сбоя остаётся `AnimalWeighingsLoading` — не
  переходит ни в `AnimalWeighingsLoaded` (ни с пустым, ни с частичным
  списком), ни в какой-либо другой вариант.
- Ни один вызов `getIt<Talker>()` (или любого другого логгера) не происходит
  на этом пути — в отличие от `AnimalVaccinationsCubit.load`.
- `loadNotSync()` того же кубита при аналогичном сбое ведёт себя идентично
  `load()` — тоже отклоняет свой `Future`, тоже без логирования.
- Пользователь не получает никакого сообщения об ошибке и не видит кнопки
  повтора — экран остаётся на `AnimalWeighingLoadingWidget` (спиннер)
  неограниченно долго.

## Связанные тесты

TBD — теста нет. `test/pages/animal_weighings_cubit_test.dart` содержит
group `'UC-93 — AnimalWeighingsCubit.load (история конкретного животного)'`
(старая нумерация в названии группы) с ровно двумя тестами — `'успех ->
placeName из места животного, сортировка по дате, unit только при unitId'`
и `'животное не найдено -> getById места вызывается с null, placeName
остаётся null'` — оба покрывают только успешный путь; теста, где один из
моков репозитория настроен на `thenThrow`, в этой группе нет. Соседняя group
`'UC-95 — AnimalWeighingsCubit.loadNotSync (В работе, глобальный список
неотправленных)'` в том же файле — тоже только два теста, оба успешные
(`'успех -> ...'` и `'пустой список -> loadedNotSync с пустым списком''`),
теста на исключение тоже нет. Ни для `load()`, ни для `loadNotSync()` в
файле нет теста, аналогичного `'ошибка репозитория -> loaded с пустым
списком, залогировано'` из `test/pages/animal_vaccinations_cubit_test.dart`
(group `'UC-78 — AnimalVaccinationsCubit.load'`).

## Открытые вопросы и ограничения

- **Реальное поведение необработанного отклонения `Future` в запущенном
  приложении не проверено ни одним widget/integration-тестом.** Вывод о том,
  что экран не падает, а зависает на спиннере, сделан по чтению кода
  (`BlocProvider.create` — синхронный колбэк, каскад возвращает кубит, а не
  `Future`; `lib/main.dart` не использует `runZonedGuarded`) и по семантике
  Dart Zones для fire-and-forget `Future`, а не по факту запуска реального
  приложения — тот же класс ограничения, что уже зафиксирован в
  [UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md) для другого
  метода той же сущности.
- **Почему WEIGH, в отличие от VAC/MOVE, не получил `try/catch` вокруг
  чтения?** [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) уже
  фиксирует ту же находку для **сохраняющих** методов (`saveWeighing`,
  `saveEditedWeighing`) — этот файл распространяет её на **читающий** метод
  (`load`/`loadNotSync`), для которого отдельно эта асимметрия с
  Vaccination/Movement ранее не была задокументирована. Ничего в коде или
  комментариях не объясняет, преднамеренно ли это или недосмотр.
- **Стоит ли добавлять `AnimalWeighingsState` вариант ошибки и/или
  `try/catch` в `load`/`loadNotSync`, аналогично `MovementReportState.error`
  или хотя бы паттерну Vaccination (тихий пустой список)?** Не решено этим
  документирующим файлом — распространяется на оба метода одинаково,
  вопрос пользователю, если поведение должно измениться.
- **Отсутствует тест, параметризованный по тому, какая из четырёх
  зависимостей бросает исключение.** Существующие успешные тесты покрывают
  только штатный путь; ни для одной из четырёх точек (`getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`,
  `getAnimalWithDetailsById` ни в одном из двух мест вызова,
  `PlaceRepository.getById`, `UnitsRepository.getById`) нет теста,
  подтверждающего конкретно её `thenThrow`.
- Сценарий отражает поведение исключительно `AnimalWeighingsCubit.load`
  (вкладка истории взвешиваний одного животного); аналогичный по духу, но
  отдельно специфицируемый сбой чтения существует для хаба неотправленных
  ([EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md)) —
  упомянут здесь как структурно идентичный (см. «Альтернативные потоки»),
  но не покрыт этим use-case как отдельный `RESULT`/файл.
