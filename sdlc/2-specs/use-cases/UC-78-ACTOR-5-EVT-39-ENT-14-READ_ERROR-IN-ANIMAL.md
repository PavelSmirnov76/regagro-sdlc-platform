# UC-78 — Просмотр вакцинаций животного: репозиторий бросает исключение, ошибка проглатывается тихо (ERROR)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Тот же триггер, что в успешном сценарии [EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md)
(`AnimalVaccinationsCubit.load`) — пользователь открывает вкладку вакцинаций
карточки животного — но чтение из репозитория падает исключением. Код ловит
исключение, логирует его через `Talker.error`, и эмитит ровно то же самое
состояние `AnimalVaccinationsState.loaded`, что и при успехе без единой
записи, — не отдельное error/failure-состояние. С точки зрения пользователя
это неотличимо от «у животного правда нет вакцинаций»: экран показывает
пустой список без какого-либо сообщения об ошибке, баннера или иконки
retry.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, роль не различается), открывший карточку
животного и вкладку вакцинаций. `AnimalVaccinationsCubit.load` также
перезапускается автоматически (без нового действия пользователя) реактивной
подпиской на `watchCountAllVaccinations()` — в этом случае «пользователь» на
этом конкретном шаге ничего не делает, вкладка уже открыта и просто
перерисовывается сама.

## CURRENT

### Основной поток

1. Пользователь на карточке животного ([AnimalVetCardPage](../../../lib/pages/animal_vet_card/presentations/animal_vet_card_page.dart))
   нажимает виджет последней вакцинации
   (`AnimalVetStatisticsWidget.onLastVaccinationTap` в
   `animal_vet_card_page.dart`) — единственная точка входа на этот экран в
   коде (`grep -rn "Routes.animalVaccinations" lib/` находит только
   объявление маршрута в `routes.dart`, сам `animal_vaccinations_page.dart`
   и этот один вызов `context.pushNamed2`).
2. `AnimalVaccinationsPage.build` создаёт `AnimalVaccinationsCubit(arguments!.animal)`
   через `BlocProvider` и сразу вызывает `..load()` — до первой отрисовки
   тела экрана.
3. `AnimalVaccinationsCubit.load()` эмитит `AnimalVaccinationsState.loading(animal: state.animal)`
   — сборка этого объекта не передаёт `selectedFastFilter`, поэтому поле
   принимает значение по умолчанию (`VaccinationFastFilter.gone`)
   независимо от того, какая вкладка (`gone`/`future`) была выбрана до этого
   вызова `load()`. UI в это время рендерит `AnimalVaccinationLoadingWidget`.
4. Cubit вызывает `_vaccinationsRepository.getVaccinationsWithDetailsByAnimalId(state.animal.animalId, sync: true)`.
   `VaccinationsRepository.getVaccinationsWithDetailsByAnimalId` — тонкий
   passthrough без собственного `try/catch`, напрямую делегирует в
   `VaccinationsDao.getVaccinationsWithDetailsByAnimalId`.
5. DAO строит один join-запрос (`Vaccinations` ⨝ `Vaccines`/`Units`/`InjectionMethods`/`InjectionPlaces`/`VaccinationTypes`,
   все — `leftOuterJoin`) и затем построчно (`for (final r in rows)`)
   достраивает `VaccinationWithDetails` для каждой строки — без `try/catch`
   вокруг этого цикла. Здесь бросается исключение: в этом use-case это
   исходное условие («репозиторий бросает исключение»), в тесте
   воспроизведено прямым `thenThrow(Exception('db error'))` на моке
   репозитория, но **в самом коде DAO есть как минимум один конкретный, не
   гипотетический источник такого исключения** — см. «Открытые вопросы».
6. Исключение не перехватывается ни в `VaccinationsDao`, ни в
   `VaccinationsRepository` — долетает до `try/catch` внутри
   `AnimalVaccinationsCubit.load()` в исходном виде.
7. `catch (e, stackTrace)` вызывает `getIt<Talker>().error("Error loading vaccinations: ${e.toString()} $stackTrace")`
   — единственным позиционным аргументом-строкой; ни `e`, ни `stackTrace` не
   передаются вторым/третьим параметром `Talker.error(message, [exception,
   stackTrace])`, они просто интерполированы в текст сообщения. Запись видна
   только в логах приложения (Talker), не пользователю.
8. Cubit эмитит `AnimalVaccinationsState.loaded(animal: state.animal, vaccinations: [])`
   — **не** отдельное `AnimalVaccinationsFailure`/`AnimalVaccinationsError`
   состояние (такого состояния в `AnimalVaccinationsState` вообще нет —
   freezed-union состоит только из `initial`/`loading`/`loaded`). Остальные
   поля `loaded` берут значения по умолчанию: `futureVaccinations: []`,
   `allVaccinations: []`, `selectedFastFilter: VaccinationFastFilter.gone`.
   `_currentFilters` (приватное поле cubit'а с последним применённым
   фильтром) не читается и не сбрасывается на этом пути — `_applyFilters()`
   вообще не вызывается при ошибке (в отличие от успешного пути).
9. `AnimalVaccinationsPage`'s `BlocBuilder` получает `AnimalVaccinationsLoaded`
   с `vaccinations: []`/`futureVaccinations: []` и рендерит
   `AnimalVaccinationsView(vaccinations: currentVaccinationsList)` —
   `currentVaccinationsList` берёт `vaccinations` или `futureVaccinations` в
   зависимости от `selectedFastFilter`, в обоих случаях `[]`.
   `AnimalVaccinationsView` — обычный `ListView.separated`; при `itemCount == 0`
   он рендерит пустую прокручиваемую область без какого-либо текста-заглушки
   («ошибка», «нет данных» и т.п.) — в коде виджета нет ветки на пустой
   список вообще.
10. Иконка фильтра в `AppBar` (`cubit.currentFilters?.hasFilters`) не
    зависит от эмитнутого состояния — это прямое чтение поля `_currentFilters`
    cubit'а, которое ошибкой не затрагивается. Если у пользователя уже были
    применены фильтры до этой ошибки, иконка фильтра остаётся подсвеченной,
    хотя список, который она якобы фильтрует, сейчас пуст не из-за
    фильтрации, а из-за проглоченной ошибки.

### Альтернативные потоки

- **Ошибка на самой первой загрузке экрана.** `_allVaccinations` — приватное
  поле cubit'а, инициализированное `[]` при объявлении. Если первый вызов
  `load()` (из `..load()` в `AnimalVaccinationsPage.build`) сразу падает,
  `_allVaccinations` остаётся `[]` — реальных данных в памяти ещё не было, и
  наблюдаемый пустой экран действительно совпадает с «нечего показывать».
- **Ошибка на повторной (реактивной) загрузке после хотя бы одной успешной.**
  `_vaccinationsCountSubscription` в конструкторе перезапускает `load()` на
  каждое событие `watchCountAllVaccinations()`. Если такой повторный вызов
  падает, `_allVaccinations` **не перезаписывается** (присваивание —
  единственная строка внутри `try`, до которой исключение не дошло, либо
  которая сама и бросила исключение) — в памяти cubit'а остаётся последний
  успешно загруженный список, при этом эмитнутое состояние всё равно
  показывает `vaccinations: []`. Это создаёт скрытое расхождение между тем,
  что показано на экране (пусто), и тем, что реально лежит в
  `_allVaccinations` (последние успешные данные).
- **Пользователь открывает и применяет фильтры после того, как ошибка уже
  показала пустой список.** `AnimalVaccinationsPage`'s фильтр-кнопка вызывает
  `cubit.applyFilters(filters)` → `_currentFilters = filters; _applyFilters();`.
  `_applyFilters()` строит список **из `_allVaccinations`**, не из текущего
  эмитнутого (пустого) состояния. Если предпосылка из предыдущего пункта
  верна (ошибка случилась на реактивной перезагрузке, а не на самой первой),
  применение фильтра — **без единого нового обращения к репозиторию** —
  внезапно "оживляет" список из устаревших, ранее успешно загруженных данных,
  прямо противореча только что показанному пустому экрану. Тот же эффект
  наступит даже если применить фильтр с пустым/неизменным набором значений —
  `_applyFilters()` не различает «фильтр реально изменился» и «фильтр
  переприменён без изменений».
- **Переключение вкладки gone/future (`setVaccinationFastFilter`) после
  ошибки.** В отличие от применения фильтра, этот метод читает списки из
  **уже эмитнутого** `state` (`AnimalVaccinationsLoaded.vaccinations`/`.futureVaccinations`),
  не из `_allVaccinations` — оба пусты после ошибки, поэтому переключение
  вкладки остаётся пустым на обеих вкладках и не воспроизводит
  расхождение предыдущего пункта.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность, которую пытается прочитать сценарий; при ошибке ни одна запись
  этого животного не попадает в UI, независимо от того, сколько их реально
  синхронизировано в БД.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — объект
  `AnimalWithDetails`, переданный в конструктор cubit'а и хранящийся в
  `state.animal` на всех состояниях экрана; сам не меняется этим сценарием,
  но `state.animal.animalId` — параметр упавшего запроса.
- Справочники `Vaccine`, `Unit`, `InjectionMethod`, `InjectionPlace`,
  `VaccinationType` (VAC-локальные, без собственного `ENT` — см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Связи») —
  join-запрос DAO читает все пять таблиц одним запросом; см. «Открытые
  вопросы» про force-unwrap на `Unit`/`InjectionMethod`.
- `Disease` (через `DiseasesVaccinations`, читается `_getDiseasesByLink`
  внутри того же цикла DAO) и `ComplexVaccine` (через
  `diseasesComplexVaccinesDao.getComplexVaccineByDiseasesIds`) — читаются на
  каждой строке того же цикла; исключение на любой из этих под-операций
  тоже приводит ровно к этому же сценарию (тот же необёрнутый `for`-цикл,
  тот же внешний `try/catch` в cubit'е).

### Бизнес-правила

- **НАХОДКА — тихое проглатывание ошибки.** `AnimalVaccinationsState` —
  freezed-union из трёх вариантов (`initial`/`loading`/`loaded`), в нём нет
  четвёртого «ошибка» варианта. Любое исключение при чтении вакцинаций
  животного превращается в `loaded` с пустым списком — тем же самым
  состоянием, которое эмитится, когда у животного действительно нет ни одной
  синхронизированной вакцинации. Пользователь не может отличить эти два
  случая ни по одному видимому признаку экрана: нет ни `SnackBar`, ни
  плашки ошибки, ни иконки retry — единственный след ошибки живёт в логах
  `Talker`, недоступных обычному пользователю.
- **Ошибка не восстанавливается автоматически без внешнего триггера.**
  Экран не делает повторных попыток сам; следующая попытка чтения произойдёт
  только при следующем событии `watchCountAllVaccinations()` (правка/удаление
  любой вакцинации где угодно в приложении) или при повторном открытии
  экрана — оба требуют не относящегося к этой ошибке действия.
- **`_allVaccinations` не синхронизирован с тем, что видно на экране, после
  ошибки на реактивной перезагрузке** — см. «Альтернативные потоки»: cubit
  хранит последний успешный результат в памяти, но показывает пустой список,
  и способен «оживить» его по несвязанному действию (применение фильтра) без
  нового успешного чтения.
- **Индикатор «есть активные фильтры» (иконка в `AppBar`) не зависит от
  результата загрузки** — это отдельное поле `cubit.currentFilters`, не часть
  `AnimalVaccinationsState`; ошибка загрузки его не сбрасывает и не
  устанавливает.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — весь сценарий (проброс исключения из DAO через репозиторий в
cubit, обработка в `catch`, итоговое состояние и его рендеринг) прослеживается
по существующему коду без пробелов, требующих уточнения у пользователя.
Единственная содержательная неопределённость — практическая достижимость
конкретного механизма исключения, описанного в «Открытые вопросы» —
зафиксирована там же, не как пробел документации.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit.load` | CURRENT | `try/catch` вокруг чтения; при исключении — `Talker.error` + `emit(AnimalVaccinationsState.loaded(..., vaccinations: []))`, без отдельного error-состояния |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit._applyFilters` / `applyFilters` | CURRENT | оперирует над кэшированным `_allVaccinations`, который НЕ очищается при ошибке — последующий вызов способен показать устаревшие данные без нового запроса |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_state.dart` | `AnimalVaccinationsState` / `AnimalVaccinationsLoaded` | CURRENT | freezed-union без варианта «ошибка»; поля `loaded` на этом пути принимают значения по умолчанию |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetailsByAnimalId` | CURRENT | тонкий passthrough в DAO без собственного `try/catch` — пробрасывает исключение без изменений |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetailsByAnimalId` | CURRENT | join-запрос и построчная сборка `VaccinationWithDetails` без `try/catch`; `r.readTableOrNull(unitAlias)!` и `r.readTableOrNull(injectionMethodAlias)!` — force-unwrap на легитимно nullable полях |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations.unitId`, `Vaccinations.injectionMethodId` | CURRENT | объявлены `integer().nullable()` — схема допускает `null`, в противоречии с force-unwrap в DAO |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccination_dto.dart` | `VaccinationDto.doseId`, `VaccinationDto.injectionTypeId`, `VaccinationDtoMapper.toCompanion` | CURRENT | единственный сегодняшний источник `sync=true` строк; DTO объявляет оба поля как `required int` (не nullable) — на практике текущий путь не производит `null` в этих колонках |
| `lib/pages/animal_vaccinations/pages/animal_vaccinations_page.dart` | `AnimalVaccinationsPage.build` | CURRENT | создаёт cubit, сразу вызывает `..load()`; `BlocBuilder` рендерит `AnimalVaccinationsView` одинаково для «пусто по правде» и «пусто из-за ошибки» |
| `lib/pages/animal_vaccinations/widgets/animal_vaccinations_view.dart` | `AnimalVaccinationsView` | CURRENT | `ListView.separated`; при `itemCount == 0` рендерит пустую область, без плейсхолдера ошибки/пустого состояния |
| `lib/pages/animal_vaccinations/widgets/animal_vaccination_loading_widget.dart` | `AnimalVaccinationLoadingWidget` | CURRENT | показывается только на `initial`/`loading`, не после ошибки (которая сразу переходит в `loaded`) |
| `lib/pages/animal_card/presentation/widgets/animal_statistics_widget.dart` | `AnimalVetStatisticsWidget.onLastVaccinationTap` | CURRENT | единственная точка входа на экран (вызывается из `AnimalVetCardPage`) |
| `lib/pages/animal_vet_card/presentations/animal_vet_card_page.dart` | `AnimalVetCardPage.build` | CURRENT | вызывает `context.pushNamed2(Routes.animalVaccinations, ...)` при тапе на последнюю вакцинацию |
| `lib/pages/routes.dart` | `Routes.animalVaccinations` | CURRENT | константа маршрута экрана |

## Критерии приёмки

- Если `VaccinationsRepository.getVaccinationsWithDetailsByAnimalId` бросает
  исключение любого типа, `AnimalVaccinationsCubit.load()` завершается без
  исключения (`completes`, а не `throwsA(...)`) — вызывающий код (страница)
  никогда не видит необработанное исключение.
- Итоговое состояние — `AnimalVaccinationsLoaded` с `vaccinations: []`, не
  `AnimalVaccinationsInitial`/`AnimalVaccinationsLoading` и не отдельное
  error-состояние (такого варианта в `AnimalVaccinationsState` нет).
- `getIt<Talker>().error(...)` вызывается ровно один раз на одну неудачную
  попытку `load()`.
- Ни `AnimalVaccinationsState`, ни рендер `AnimalVaccinationsPage`/`AnimalVaccinationsView`
  не содержат видимого пользователю признака ошибки (текста, иконки,
  `SnackBar`) на этом пути — проверяемо тем, что дерево виджетов при
  `vaccinations: []` идентично дереву при реальном отсутствии вакцинаций.

## Связанные тесты

`test/pages/animal_vaccinations_cubit_test.dart`, group `'UC-78 —
AnimalVaccinationsCubit.load'` (старая нумерация в названии группы, будет
переименовано отдельным проходом, не трогать сейчас) — один `test`:

- `'ошибка репозитория -> loaded с пустым списком, залогировано'` — мокает
  `repository.getVaccinationsWithDetailsByAnimalId(1, sync: true)` на
  `thenThrow(Exception('db error'))`, вызывает `cubit.load()`, проверяет
  `(cubit.state as AnimalVaccinationsLoaded).vaccinations` (`isEmpty`) и
  `verify(() => getIt<Talker>().error(any())).called(1)`.

Тест покрывает обработку исключения в cubit'е (соответствует шагам 6–8
основного потока), но не покрывает ни конкретный force-unwrap механизм DAO
(шаг 5, «Открытые вопросы»), ни поведение `_allVaccinations`/`applyFilters`
после ошибки (первый альтернативный поток про «оживление» устаревших
данных) — эти два аспекта верифицированы только чтением кода, отдельных
тестов на них нет.

## Открытые вопросы и ограничения

- **Тихое проглатывание ошибки — самый значимый факт этого сценария.**
  Отсутствие отдельного error-состояния в `AnimalVaccinationsState` означает,
  что для любого технического сбоя (обрыв БД на грани, повреждённая строка,
  исключение внутри join-запроса) пользователь видит ровно тот же экран, что
  и при честном «у этого животного нет вакцинаций». Это более выраженный
  случай той же общей проблемы, что уже задокументирована для генерического
  сообщения об ошибке при старте сессии
  ([UC-15](UC-15-ACTOR-3-EVT-6-ENT-2-READ_ERROR-IN-AUTH.md)) и для тихо
  проглатываемого сетевого сбоя push-шага вакцинации
  ([UC-72](UC-72-ACTOR-4-EVT-36-ENT-14-UPDATE_ERROR-IN-ANIMAL.md)): там хотя
  бы показывается общее сообщение об ошибке или временно пишется поле
  `errors` в БД — здесь не остаётся вообще никакого следа, видимого
  пользователю.
- **Конкретный, не только гипотетический источник исключения найден в DAO,
  но его сегодняшняя достижимость из живых данных не доказана.**
  `VaccinationsDao.getVaccinationsWithDetailsByAnimalId` делает
  `r.readTableOrNull(unitAlias)!` и `r.readTableOrNull(injectionMethodAlias)!`
  — force-unwrap результата `leftOuterJoin`, хотя `Vaccinations.unitId` и
  `Vaccinations.injectionMethodId` объявлены `nullable()` в самой таблице
  (в отличие от соседних `injectionPlaceAlias`/`vaccinationTypeAlias` в том
  же методе, которые корректно читаются через `readTableOrNull` без `!`).
  Если бы в БД оказалась `sync == true`-строка с `unitId == null` или
  `injectionMethodId == null`, чтение этой ОДНОЙ строки бросило бы
  исключение, которое (из-за отсутствия `try/catch` вокруг `for`-цикла)
  оборвало бы весь метод — и, по цепочке этого сценария, скрыло бы от
  пользователя ВСЕ вакцинации животного, а не только проблемную строку.
  Проверка кода единственного сегодняшнего пути записи `sync=true` данных
  (`VaccinationDtoMapper.toCompanion`, из `VaccinationDto.doseId`/`.injectionTypeId`,
  оба объявлены `required int`, не `int?`) показывает, что при штатной работе
  сервер обязан всегда присылать оба значения — поэтому вопрос пользователю:
  является ли это реальным риском (например, если сервер когда-либо начнёт
  присылать `null`, это сломает не эту строку, а более раннюю десериализацию
  DTO — отдельный сценарий) или чисто теоретическим несоответствием схемы и
  кода, которое стоит поправить проактивно вне периметра этой документирующей
  задачи.
- **`_allVaccinations` не сбрасывается при ошибке.** После ошибки на
  реактивной перезагрузке (см. «Альтернативные потоки») cubit хранит
  последний успешный результат в памяти, но показывает пустой список — любое
  последующее применение фильтра, даже без реального изменения набора
  значений, покажет устаревшие данные без нового обращения к репозиторию.
  Не проверено тестом, зафиксировано только чтением кода
  (`_applyFilters()` читает `_allVaccinations`, не `state`).
  Вопрос пользователю: ожидаемое поведение (кэш как «последнее известное
  хорошее состояние») или скрытый баг, который стоит явно задокументировать
  в `TARGET` отдельной задачей.
- **Логирование не передаёт объект исключения/стектрейс отдельными
  параметрами.** `Talker.error(message, [exception, stackTrace])` поддерживает
  структурированную передачу, но вызов в коде передаёт только одну строку,
  где `e`/`stackTrace` уже интерполированы текстом — минорная потеря
  структуры лога, не влияющая на поведение, видимое пользователю.
- Сценарий отражает поведение исключительно `AnimalVaccinationsCubit.load`
  (read-путь карточки животного); аналогичные по духу, но отдельно
  специфицируемые ошибки чтения существуют и для хаба неотправленных
  вакцинаций ([EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md))
  и посуточного отчёта ([EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md))
  — не покрыты этим use-case, каждый использует свой cubit/bloc с
  потенциально другой обработкой ошибок.
