# UC-93 — Пользователь открывает вкладку взвешиваний карточки животного

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает вкладку взвешиваний в карточке животного (тап по весу
на вет-статистике) и видит полную историю взвешиваний этого животного —
**все** записи независимо от `sync`-статуса (в отличие от вакцинаций, где
вкладка показывает только `sync == true`), отсортированные по дате по
возрастанию, плюс график и таблицу со среднесуточным привесом/увесом между
последовательными записями.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `AnimalWeighingsPage`, ни
`AnimalWeighingsCubit.load` не проверяют статус авторизации. Единственное
предусловие — переход с карточки конкретного животного, `animalId` которого
передаётся аргументом страницы.

## CURRENT

### Основной поток

1. Пользователь находится на `AnimalCardPage` и нажимает на блок веса
   (`AnimalStatisticsWidget.onWeightTap`, вызывается из
   `lib/pages/animal_card/animal_card_page.dart`) →
   `context.pushNamed2(Routes.animalWeighings, extra:
   AnimalWeighingsPageArguments(animalId: animalWithDetails.animalId))`.
2. `AnimalWeighingsPage.build` читает аргумент через
   `GoRouterState.of(context).getExtraByName<AnimalWeighingsPageArguments?>(Routes.animalWeighings)`
   и сразу форс-анврапит `arguments!.animalId!` (упадёт, если аргумент/id не
   передан — но единственная найденная точка входа, `AnimalCardPage`, всегда
   передаёт непустой `animalId`). Создаётся `BlocProvider(create: (context) =>
   AnimalWeighingsCubit()..load(animalId))`.
3. `AnimalWeighingsCubit.load(animalId)` эмитит `AnimalWeighingsState.loading()`
   (список пуст, `placeName` пуст).
4. `_animalWeightingsRepository
   .getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc([animalId])` →
   `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc`:
   `SELECT ... WHERE animal_id IN (...) ORDER BY weighing_date ASC` — **без**
   фильтра по `sync`, поэтому в результат попадают и уже синхронизированные, и
   ещё не отправленные (`sync == false`) строки этого животного.
5. `_animalsRepository.getAnimalWithDetailsById(animalId)` — животное для
   резолва места; может вернуть `null`, если животного с таким id локально нет
   (см. «Альтернативные потоки»).
6. `_placesRepository.getById(animal?.animal.placeId)` —
   `PlaceRepository.getById` немедленно возвращает `null`, если переданный id
   — `null` (в т.ч. когда шаг 5 вернул `null`), иначе ищет `Place` по
   `idRemote`.
7. Для каждой строки взвешивания из шага 4 строится `AnimalWeighingWithDetails`:
   - `animal`: **повторный** вызов `_animalsRepository
     .getAnimalWithDetailsById(animalWeighing.animalId)` — тот же `animalId`,
     что и на шаге 5 (весь список взвешиваний принадлежит одному животному),
     то есть одно и то же животное перечитывается из БД `1 + N` раз за один
     `load()` (N = число строк взвешивания), не переиспользуя результат шага
     5;
   - `unit`: `_unitsRepository.getById(unitId)`, только если
     `animalWeighing.unitId != null`, иначе `null`.
8. `animalWeighingWithDetails.sort(...)` — повторная сортировка по
   `weighingDate` по возрастанию в Dart, поверх уже отсортированного SQL-
   запросом (шаг 4) списка; результат не меняется, но запрос лишний.
9. `emit(AnimalWeighingsState.loaded(animalWeighings:
   animalWeighingWithDetails.toModel(), placeName: place?.name))`.
10. `_AnimalWeighingsBodyState.build` (в `AnimalWeighingsPage.build`, тот же
    файл) через `BlocBuilder` на `AnimalWeighingsLoaded` рендерит
    `AnimalWeighingWidget(animalWeighings: ..., onAnimalWeighingTap: (id) =>
    cubit.selectAnimalWeighing(id, singleSelection: true), onDismissSelection:
    () => cubit.clearSelection())` внутри `Scaffold` с `CustomAppBar(title:
    l10n.weight_title, subtitle: l10n.average_daily_gain)` — оба текста
    статичные локализованные строки, не зависят от `state.placeName` (см.
    «Бизнес-правила»).
11. `AnimalWeighingWidget.build` вызывает `buildGainData(animalWeighings)`
    (`lib/pages/animal_weighings/utils/animal_weighing_gain_utils.dart`):
    список ещё раз копируется и сортируется по `weighingDate` ASC (третья по
    счёту сортировка того же критерия за один цикл экрана — после SQL `ORDER
    BY` на шаге 4 и Dart-сортировки на шаге 8), затем на каждую запись, начиная
    со второй по дате:
    - `weightChange = current.weight - previous.weight`;
    - `daysBetween = max(1, dateOnly(current.weighingDate)
      .difference(dateOnly(previous.weighingDate)).inDays)` — минимум 1 день,
      даже если обе записи в один календарный день;
    - `dailyGain = weightChange / daysBetween`;
    - `gainDelta = dailyGain - previousDailyGain`, если для предыдущей записи
      `dailyGain` уже был посчитан, иначе `null`.
    Для самой ранней по дате записи `dailyGain`/`gainDelta`/`weightChange` —
    `null` (базы для сравнения нет).
12. Виджет рендерит `GraphWidget` (столбцы веса по датам по возрастанию) и
    `DraggableScrollableSheet` с таблицей строк в **обратном** порядке (по
    убыванию даты — `animalWeighings[length - 1 - index]`), на каждой строке —
    дата, вес (`formatWeightDisplay`) и `_GainCell` с `dailyGain`/
    `weightChange` из `gainById`, если они не `null`.

### Альтернативные потоки

- **Животное не найдено локально.** Если `getAnimalWithDetailsById(animalId)`
  на шаге 5 возвращает `null` (например, животное было удалено, а
  `animalId` в аргументе устарел) — `_placesRepository.getById(null)`
  вызывается явно с `null` и сам возвращает `null` без исключения;
  `placeName` состояния остаётся `null`. Список взвешиваний на шаге 4 при
  этом запрашивается независимо, по `animalId` напрямую — теоретически может
  быть непустым, даже если сущность `Animal` уже отсутствует; итог всё равно
  `READ_OK` (подтверждено тестом «животное не найдено», см. «Связанные
  тесты»).
- **Реактивация состояния без клика пользователя.**
  `_AnimalWeighingsBodyState.activate()` вызывает `load(animalId)` повторно.
  `State.activate()` — не аналог первого открытия вкладки (это делает
  `BlocProvider.create` в `AnimalWeighingsPage.build`, шаг 2), а колбэк,
  который фреймворк вызывает только когда `Element` этого поддерева
  реактивируется после `deactivate` без полного пересоздания (например, при
  репарентинге через `GlobalKey`) — то же событие/`RESULT`, но без явного
  действия пользователя в этот конкретный момент; не покрыто отдельным
  тестом, реальная частота срабатывания в этом экране не проверялась.
- **Необработанное исключение внутри `load()`.** Метод целиком не обёрнут в
  `try`/`catch` — если любой из вызовов на шагах 4–7 бросает исключение,
  `Future`, возвращаемый `load(animalId)`, завершается с ошибкой; поскольку
  `BlocProvider(create: (context) => AnimalWeighingsCubit()..load(animalId))`
  не дожидается и не обрабатывает этот `Future`, состояние кубита так и
  остаётся `AnimalWeighingsLoading` — экран показывает
  `AnimalWeighingLoadingWidget` (`CircularProgressIndicator`) бесконечно,
  без сообщения об ошибке пользователю. Отдельного `RESULT = READ_ERROR` для
  [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md)
  на сегодня не существует ни в коде (нет ветки, которая бы отличала его от
  `READ_OK` на уровне состояния), ни в дереве спек — в отличие от вакцинаций
  ([EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md),
  где такая ветка явно перехватывается и описана отдельным use-case
  `READ_ERROR`).
- **Альтернативная инициализация без чтения БД не вызывается ниоткуда.**
  `AnimalWeighingsCubit.initWithoutLoad(AnimalWithDetails animal)` строит то
  же `AnimalWeighingsState.loaded` напрямую из уже загруженного в память
  `animal.animalWeighings`, без обращения к `_animalWeightingsRepository`, и
  никогда не резолвит `placeName` (остаётся `null` в этой ветке). `grep -rn
  "initWithoutLoad"` вне `test/pages/animal_weighings_cubit_test.dart`
  ничего не находит — метод не вызывается ни с одной страницы/навигации,
  недостижимая альтернативная презентация этого же события.
- **Переход на запись нового взвешивания с той же вкладки.** Если на этой
  вкладке нажать FAB, `MainPage` (`lib/pages/main/main_page.dart`) читает тот
  же `AnimalWeighingsPageArguments` через `getExtraByName` и переходит на
  `Routes.weighAnimal` с `WeighAnimalPageArguments(animalId: extra.animalId!,
  hideNextAnimalButton: true)` — отдельный сценарий записи взвешивания
  ([EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md)/
  [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md)), не входит в
  этот файл — упомянут только как соседний путь, переиспользующий тот же
  аргумент страницы.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  главный предмет чтения; читаются строки **любого** `sync`-статуса этого
  животного.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — животное, чью
  карточку смотрит пользователь; читается для резолва места (шаг 5) и повторно
  на каждую строку взвешивания (шаг 7), но самим сценарием не изменяется.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — место
  содержания животного, читается для `placeName` состояния; вычисленное имя
  места фактически не отображается ни одним виджетом этого экрана (см.
  «Бизнес-правила»).
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — единица измерения веса, читается на каждую строку с
  `unitId != null`; отображается в таблице как суффикс веса
  (`unit?.name ?? l10n.weight_unit_kg`).

### Бизнес-правила

- **Без фильтра по `sync` — вся история животного.** В отличие от вкладки
  вакцинаций ([UC-77](UC-77-ACTOR-5-EVT-39-ENT-14-READ_OK-IN-ANIMAL.md),
  жёсткий фильтр `sync == true`), вкладка взвешиваний показывает
  синхронизированные и ещё не отправленные записи вперемешку, одним списком,
  отсортированным по дате.
- **`placeName` резолвится, но нигде не отображается.** `load()` вычисляет
  `placeName: place?.name` и кладёт его в состояние, но ни
  `AnimalWeighingsPage`/`_AnimalWeighingsBodyState`, ни `AnimalWeighingWidget`
  не читают `state.placeName` — заголовок/подзаголовок `CustomAppBar` на этом
  экране всегда статичные локализованные строки (`weight_title`,
  `average_daily_gain`). Проверено: `grep -rn "\.placeName"` вне
  `cubits/animal_weighings/` и сгенерированного `*.freezed.dart` не находит ни
  одного места чтения этого поля в модуле взвешиваний.
- **Среднесуточный привес/увес — вычисляется на лету на экране, не в кубите и
  не хранится.** `buildGainData` берёт уже загруженный список, пересчитывает
  на каждый рендер `AnimalWeighingWidget`; формула — `(текущий_вес -
  предыдущий_вес) / max(1, дней_между_датами_по_календарю)`, минимум 1 день
  даже для двух записей в один день; для самой ранней по дате записи привес
  не показывается.
- **Список сортируется трижды подряд одним и тем же критерием** — SQL `ORDER
  BY weighing_date ASC` в DAO (шаг 4), затем `List.sort` в `load()` (шаг 8),
  затем ещё раз копия сортируется внутри `buildGainData` (шаг 11); результат
  идемпотентен, лишняя работа не меняет исход.
- **Животное перечитывается избыточно.** `getAnimalWithDetailsById(animalId)`
  вызывается один раз для резолва места и затем ещё раз на каждую строку
  взвешивания (все вызовы — с одним и тем же `animalId`, так как весь список
  принадлежит одному животному) — результат первого вызова не кэшируется и не
  переиспользуется.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не заблокировано — основной поток полностью реализован, достижим из реального
UI (шаги 1–2) и покрыт тестом на обе ветки основного/альтернативного потока
(успех и «животное не найдено», см. «Связанные тесты»). Ветка необработанного
исключения (см. «Альтернативные потоки») не заблокирована технически, но не
описана отдельным `RESULT = READ_ERROR` — сегодня в коде нет распознаваемой
ошибочной ветки, которую можно было бы задокументировать как отдельный
use-case; это открытый вопрос, не блокер для `READ_OK`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `AnimalStatisticsWidget` (`onWeightTap` → `context.pushNamed2(Routes.animalWeighings, ...)`) | CURRENT | точка входа — переход на вкладку взвешиваний из карточки животного |
| `lib/pages/routes.dart` | `Routes.animalWeighings` | CURRENT | маршрут → `AnimalWeighingsPage` |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `AnimalWeighingsPage.build` | CURRENT | читает аргумент страницы, создаёт кубит и вызывает `load(animalId)` |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `AnimalWeighingsPageArguments` | CURRENT | контейнер аргумента (`animalId`) |
| `lib/pages/animal_weighings/pages/animal_weighings_page.dart` | `_AnimalWeighingsBodyState.activate` | CURRENT | повторный `load(animalId)` при реактивации `State` без клика пользователя |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.load` | CURRENT | основной метод сценария — запрос списка (без фильтра `sync`), резолв места, сборка `AnimalWeighingWithDetails` на строку |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.initWithoutLoad` | CURRENT | недостижимая альтернативная инициализация без чтения БД и без резолва `placeName` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState.loaded` (`AnimalWeighingsLoaded`) | CURRENT | целевое состояние сценария — `animalWeighings` + `placeName` |
| `lib/pages/animal_weighings/data/animal_weighing_model.dart` | `AnimalWeighingModelMapper.toModel` | CURRENT | маппинг `List<AnimalWeighingWithDetails>` → `List<AnimalWeighingModel>` |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | источник списка — без фильтра по `sync` |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc` | CURRENT | `SELECT ... ORDER BY weighing_date ASC`, без фильтра `sync` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | читается для резолва места и повторно на каждую строку взвешивания |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.getById` | CURRENT | резолв `placeName`; возвращает `null` немедленно при `placeId == null` |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository.getById` | CURRENT | единица измерения веса на строку, только при `unitId != null` |
| `lib/pages/animal_weighings/widgets/animal_weighing_list_widget.dart` | `AnimalWeighingWidget.build` | CURRENT | рендер графика и таблицы, вызывает `buildGainData` |
| `lib/pages/animal_weighings/utils/animal_weighing_gain_utils.dart` | `buildGainData` | CURRENT | расчёт среднесуточного привеса/увеса между последовательными записями |
| `lib/pages/animal_weighings/widgets/animal_weighing_loading_widget.dart` | `AnimalWeighingLoadingWidget` | CURRENT | что видит пользователь в `initial`/`loading`, включая случай необработанного исключения (см. «Альтернативные потоки») |
| `lib/pages/main/main_page.dart` | `MainPage` (обработка FAB на пути `Routes.animalWeighings` → `context.pushNamed2(Routes.weighAnimal, ...)`) | CURRENT | соседний сценарий записи взвешивания, переиспользующий тот же аргумент страницы — вне этого use-case |

## Критерии приёмки

- При вызове `AnimalWeighingsCubit.load(animalId)` репозиторий
  `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc([animalId])` вызывается
  ровно один раз и возвращает строки **любого** `sync`-статуса этого
  животного.
- Итоговый `state.animalWeighings` отсортирован по `weighingDate` по
  возрастанию.
- `state.placeName` равен имени места животного (`place.name`), где `place`
  получен через `PlaceRepository.getById(animal?.animal.placeId)`; если
  животное не найдено — `getById` вызывается с `null`, `placeName` остаётся
  `null`, исключения не возникает.
- Для строки с `unitId != null` в `AnimalWeighingWithDetails.unit` подставлен
  соответствующий `Unit`; при `unitId == null` — `unit` равен `null`.
- Итоговое состояние — `AnimalWeighingsLoaded`.
- `AnimalWeighingWidget` вычисляет `dailyGain` по формуле `(вес_текущей -
  вес_предыдущей) / max(1, дней_между_датами)` для каждой записи, кроме самой
  ранней по дате (для неё `dailyGain == null`).

## Связанные тесты

`test/pages/animal_weighings_cubit_test.dart`, group `'UC-93 —
AnimalWeighingsCubit.load (история конкретного животного)'` (старая
нумерация — переименуется отдельным контролируемым проходом, не трогать
сейчас):

- test `'успех -> placeName из места животного, сортировка по дате, unit
  только при unitId'` — покрывает основной поток: два взвешивания одного
  животного (разные `id`, одно с `unitId`), `placeName` резолвится в `'Ферма
  Юг'`, список приходит отсортированным по `weighingDate` ASC (`[1, 2]`),
  `unit` подставлен только для строки с `unitId`, итоговое состояние —
  `AnimalWeighingsLoaded`.
- test `'животное не найдено -> getById места вызывается с null, placeName
  остаётся null'` — покрывает альтернативный поток «животное не найдено»:
  `getAnimalWithDetailsById` возвращает `null`, `placeRepository.getById(null)`
  вызван (`verify(...).called(1)`), `placeName` — `null`, список взвешиваний —
  пуст.

Ветка необработанного исключения внутри `load()` (альтернативный поток) тестом
не покрыта — `TBD — теста нет`. Реактивация через `_AnimalWeighingsBodyState
.activate()` тестом не покрыта — `TBD — теста нет`. Недостижимость
`initWithoutLoad` из UI подтверждена не тестом, а `grep`, см. «Альтернативные
потоки»; сам метод покрыт отдельными тестами того же файла (`await
cubit.initWithoutLoad(...)`), но это не тест этого use-case — `initWithoutLoad`
не вызывается на пути, который описывает этот файл.

## Открытые вопросы и ограничения

- **Нет `RESULT = READ_ERROR` для этого события.** `load()` не оборачивает ни
  один из своих вызовов в `try`/`catch` — при исключении состояние навсегда
  остаётся `AnimalWeighingsLoading`, пользователь видит бесконечный
  `CircularProgressIndicator`, ошибка нигде не логируется и не показывается.
  В отличие от вакцинаций ([UC-78](UC-78-ACTOR-5-EVT-39-ENT-14-READ_ERROR-IN-ANIMAL.md)),
  для этого события сегодня невозможно написать осмысленный
  `READ_ERROR`-сценарий, потому что в коде нет ветки, которая явно отличала бы
  ошибку от `READ_OK`.
- **`placeName` — вычисляется, но нигде не отображается.** Похоже на остаток
  недоделанной или убранной функциональности (например, подзаголовок с
  именем места, который должен был заменить статичный
  `average_daily_gain`); подтверждено `grep` по всем потребителям поля вне
  файлов кубита/состояния.
- **Тройная сортировка одного и того же списка по одному критерию** (SQL,
  `load()`, `buildGainData`) и **избыточное повторное чтение того же
  животного** (`getAnimalWithDetailsById` — раз для места, затем на каждую
  строку) не влияют на корректность итога в засвидетельствованных тестах, но
  являются лишней нагрузкой на БД, пропорциональной числу строк взвешивания;
  не проверялось, заметно ли это на реальных объёмах данных.
- **`_AnimalWeighingsBodyState.activate()` не покрыт тестом и не подтверждён
  как практически достижимый путь** в этом конкретном экране (зависит от
  того, репарentится ли когда-либо `Element` этого поддерева через
  `GlobalKey`/аналогичный механизм) — зафиксирован как факт кода, не как
  проверенное поведение.
- **`AnimalWeighingsCubit.initWithoutLoad` — недостижимый мёртвый код**, как и
  зафиксировано в [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md);
  не описывается отдельным use-case, так как ни одна страница/навигация его не
  вызывает.
