# UC-44 — Регистрация нового животного через визард завершается успехом

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гость или
авторизованный, одинаково) проходит визард регистрации животного и подтверждает
на чекауте; животное сохраняется локально с отрицательным id, без обращения к
серверу. Happy-path сценарий события
[EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)
(`animal.registered_locally`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения. Регистрация — local-first сценарий: доступна одинаково гостю и
авторизованному пользователю, не требует сети и не инициирует ни один
sync-шаг (это отдельный проход, см. [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md)).

## CURRENT

### Основной поток

1. Пользователь открывает визард регистрации (`AnimalRegistrationPage`),
   опционально с аргументами `farmId`/`placeId`
   (`AnimalRegistrationPageArguments`). `AnimalRegistrationBloc` создаётся с
   этими значениями и сразу получает `AnimalRegistrationStart()`.
2. Обработчик `AnimalRegistrationStart` загружает справочники (типы маркеров,
   фермы, места+животные по ним, виды/породы/масти, поколения, снимок уже
   использованных номеров идентификации) в `_data`. Если аргумент `placeId`
   разрешился в найденное место — `_data.place` заполняется уже на этом шаге.
3. Реально проходимые шаги визарда — `AnimalRegistrationData.singleSteps`
   (= `currentSteps`): **место** (`AnimalRegistrationStep.farmPlace`,
   показывается, только если `_data.place == null`, т.е. только когда
   аргумент `placeId` не был передан или не разрешился) → **вид**
   (`AnimalRegistrationEventChangeKind` → `filterDataByKind`, пересчитывает
   зависимые справочники пород/мастей/типов маркеров) → **порода**
   (`AnimalRegistrationEventChangeBreed`) → **масть**
   (`AnimalRegistrationEventChangeSuit`) → **пол**
   (`AnimalRegistrationEventChangeGender`) → **дата рождения**
   (`AnimalRegistrationEventChangeBirthDate`) → **маркировка**
   (`IdentificationsStepPage`) → **чекаут** (`CheckoutStepPage`). Другие шаги,
   определённые в `AnimalRegistrationStep` (родословная, поколение, кличка,
   доп. информация, диапазон дат рождения, паспорт+чип, создание фермы),
   в `singleSteps` не входят и в этом визарде недостижимы.
4. На шаге маркировки `_IdentificationsStepPageState.initState` вызывает
   `_addIdentification()`: если для выбранного вида в справочнике найден тип
   маркера-транспондера (`Constants.TransponderMarkerTypeId`) — диспатчится
   `AnimalRegistrationEventAddIdentification` для него первым; затем, если
   найден тип маркера-бирки (`Constants.BirkMarkerTypeId`) — тем же событием
   вторым. Обработчик `AnimalRegistrationEventAddIdentification` вставляет
   новую запись в **начало** списка
   (`[newItem, ..._data.animalIdentifications]`) — поэтому после обоих
   вызовов бирка (добавлена второй) оказывается **первым** элементом списка,
   а транспондер (добавлен первым) — вторым. Пользователь вводит номера через
   `AnimalRegistrationEventChangeNumberIdentification`; поле транспондера
   валидируется (`Validator.animalIdentificationLocalization`), поле бирки —
   без валидации (см. «Открытые вопросы»).
5. На чекауте пользователь нажимает «Зарегистрировать»
   (`CheckoutStepPage.onRegister`) → `bloc.add(const
   AnimalRegistrationEventSave())`.
6. Bloc создан без `editAnimal` (`_editAnimal == null`), поэтому обработчик
   `AnimalRegistrationEventSave` идёт по ветке нового животного и вызывает
   `saveAnimal()`.
7. `saveAnimal()`:
   - берёт текущий `_data.animalIdentifications` как есть;
   - `priorityNumber = animalIdentifications.firstOrNull?.number` — из-за
     порядка вставки на шаге 4 это на практике номер **бирки**, а не
     транспондера, если заполнены оба;
   - `mother`/`father` вычисляются из `_data.parents`, но на этом реально
     проходимом сценарии всегда `null` — шаг родословной не входит в
     `singleSteps` (принадлежит под-области REPRO, вне этого use-case);
   - `localId = await _animalsRepository.nextLocalAnimalId()` →
     `AnimalsDao.nextLocalAnimalId` — `MIN(id) WHERE id < 0`, минус 1 (или
     `-1`, если локальных животных ещё нет вообще);
   - строит `AnimalsCompanion.insert(...)`: `id = localId`, `userId` — id
     текущего пользователя или `-1` для гостя (`_authRepository.getUser()?.id
     ?? -1`), `number = priorityNumber`, `kindId`/`breedId`/`suitId`/`gender`/
     `birthDate`/`generation`/`placeId`/`farmId`/`name` — из `_data`,
     **`isMobile: true`** (жёстко, не из `_data`), `birthDateFrom`/
     `birthDateTo: null` (шаг диапазона дат недостижим в этом визарде);
   - фильтрует `animalIdentifications` по `ai.number.isNotEmpty` — **только
     заполненные** средства маркирования превращаются в
     `AnimalIdentificationsCompanion.insert(...)` (`identificationReasonId: 1`
     и `isEmission: true` — жёстко для всех, `animalId: 0` — плейсхолдер,
     переписывается в DAO реальным id);
   - вызывает `_animalsRepository.insertAnimalWithDetailsCompanion(animal:
     ..., animalIdentifications: ...)` → `AnimalsDao
     .insertAnimalWithDetailsCompanion` — одна Drift-транзакция: вставляет
     `Animal`, затем (если список идентификаций не пуст) вставляет их с
     реальным `animalId`, полученным из вставки животного;
   - возвращает `localId`.
8. Обработчик `AnimalRegistrationEventSave` эмитит `AnimalRegistrationExit
   (unsentAnimalId: localId)`, затем — безусловно, вне `try`/`catch` — ещё раз
   `AnimalRegistrationSuccess(_data)` с неизменёнными данными формы (см.
   «Открытые вопросы»).
9. `AnimalRegistrationPage`'s `BlocConsumer.listener` реагирует на
   `AnimalRegistrationExit`: `context.pop(state.unsentAnimalId)` — визард
   закрывается, вызывающий экран получает новый (отрицательный) `id`
   животного как результат.

### Альтернативные потоки

- **`AnimalRegistrationEventSaveAndAddAnother`** (кнопка «Добавить ещё» на
  чекауте, `CheckoutStepPage.onAddAnother` →
  `bloc.add(const AnimalRegistrationEventSaveAndAddAnother())`): выполняет тот
  же `saveAnimal()` (тот же переход `CREATE_OK`), но **не** эмитит
  `AnimalRegistrationExit` — визард не закрывается. После сохранения
  сбрасывается только часть `_data`: пол (`gender: null`), дата рождения
  (`birthDate: null`), все средства маркирования
  (`animalIdentifications: []`), кличка (`name: null`), родители
  (`parents: null`) — вид (`kind`), порода (`breed`), масть (`suit`), ферма
  (`farm`) и место (`place`) остаются как были; эмитится
  `AnimalRegistrationSuccess(_data)`. `animal_registration_page.dart` после
  диспатча события ждёт `Future.delayed(600ms)` и переключает `TabController`
  обратно на шаг пола (`AnimalRegistrationStep.gender`), позволяя ввести
  следующее животное того же вида/породы/масти на той же ферме/месте без
  повторного прохождения этих шагов.
- Аргумент `placeId` не передан или не разрешился в найденное место — шаг
  «место» показывается первым; в остальном поток тот же.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность,
  совершающая переход: новая строка с `id < 0`, `isMobile: true`,
  `number` — из первого элемента списка идентификаций.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — создаётся в той же транзакции; только записи с
  непустым `number` попадают в БД.
- Kind/Breed/Suit — справочники модуля
  [HANDBOOKS](../modules/MOD-2-HANDBOOKS.md) ([ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md));
  ANIMAL только ссылается на них по id (`kindId`/`breedId`/`suitId`), сама их
  не меняет.
- Farm/Place — справочник модуля [FARM](../modules/MOD-3-FARM.md)
  ([ENT-9](../entities/ENT-9-FARM-IN-FARM.md)/[ENT-10](../entities/ENT-10-PLACE-IN-FARM.md));
  ANIMAL только ссылается на них по `farmId`/`placeId`.

### Бизнес-правила

- Только заполненные (`number.isNotEmpty`) идентификации сохраняются вместе с
  животным — пустые записи, добавленные автоматически на шаге маркировки, но
  не заполненные пользователем, отбрасываются перед вставкой.
- `Animal.number` берётся из первого элемента списка идентификаций, а не
  специально из транспондера — из-за порядка добавления (транспондер первым,
  бирка вторым, но вставка в начало списка) это на практике номер бирки.
- `isMobile` всегда `true` для животного, созданного через этот визард,
  независимо от статуса авторизации пользователя.
- Гость и авторизованный пользователь проходят одинаковый путь; единственная
  разница — значение `userId` (`-1` для гостя вместо id пользователя).
- Регистрация полностью local-first: сценарий не делает ни одного сетевого
  вызова — сохранение атомарно происходит в одной локальной Drift-транзакции.
- Новый локальный `id` вычисляется в момент вызова `saveAnimal()` (на
  чекауте), а не при старте визарда — `nextLocalAnimalId()` пересчитывается
  заново на каждый вызов `saveAnimal()`, в том числе внутри одного визарда при
  повторном сохранении через «Добавить ещё».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и покрыт тестами (см. «Связанные
тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_registration/animal_registration_page.dart` | `AnimalRegistrationPageArguments` | CURRENT | аргументы точки входа визарда (`farmId`/`placeId` и др.) |
| `lib/pages/animal_registration/animal_registration_page.dart` | `_AnimalRegistrationPageState.build` (`BlocProvider`/`BlocConsumer.listener`) | CURRENT | создаёт `AnimalRegistrationBloc`, реагирует на `AnimalRegistrationExit` вызовом `context.pop` |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationStart>` | CURRENT | загрузка справочников, инициализация `_data`, разрешение `place`/`farm` по аргументам |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationData.singleSteps`/`currentSteps` | CURRENT | реально проходимые шаги визарда, условный шаг `farmPlace` |
| `lib/pages/animal_registration/step_pages/identifications_step_page.dart` | `_IdentificationsStepPageState._addIdentification` | CURRENT | порядок автодобавления: транспондер первым, бирка второй |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventAddIdentification>` | CURRENT | вставка новой идентификации в начало списка |
| `lib/pages/animal_registration/step_pages/checkout_step_page.dart` | `CheckoutStepPage` (`onRegister`/`onAddAnother`) | CURRENT | кнопки чекаута, диспатч `AnimalRegistrationEventSave`/`AnimalRegistrationEventSaveAndAddAnother` |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventSave>` | CURRENT | ветка нового животного вызывает `saveAnimal()`, эмитит `AnimalRegistrationExit`, затем `AnimalRegistrationSuccess` |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.saveAnimal` | CURRENT | построение `AnimalsCompanion`/`AnimalIdentificationsCompanion`, вызов `insertAnimalWithDetailsCompanion` |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventSaveAndAddAnother>` | CURRENT | альтернативный поток: тот же `saveAnimal()`, сброс части `_data`, визард не закрывается |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.nextLocalAnimalId` | CURRENT | делегирует в DAO |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.nextLocalAnimalId` | CURRENT | `MIN(id) WHERE id < 0`, минус 1 |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.insertAnimalWithDetailsCompanion` | CURRENT | делегирует в DAO |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.insertAnimalWithDetailsCompanion` | CURRENT | транзакция: вставка `Animal`, затем идентификаций с реальным `animalId` |

## Критерии приёмки

- При нажатии «Зарегистрировать» на чекауте визарда (без предварительного
  `editAnimal`) выполняется ровно один вызов
  `AnimalsRepository.insertAnimalWithDetailsCompanion`, без сетевых вызовов.
- Переданный в этот вызов `AnimalsCompanion.id` равен значению, которое
  вернул `AnimalsRepository.nextLocalAnimalId()` для этого сохранения, и оно
  отрицательно.
- `AnimalsCompanion.isMobile` всегда `true`.
- `AnimalsCompanion.number` равен `number` первого элемента списка
  идентификаций на момент сохранения (не обязательно транспондера).
- Список `AnimalIdentificationsCompanion`, переданный в этот вызов, содержит
  только записи с непустым `number` — пустые (в т.ч. автоматически
  добавленные заготовки без введённого номера) отсутствуют.
- После обработки события bloc эмитит `AnimalRegistrationExit` с
  `unsentAnimalId`, равным id только что созданного животного; страница
  визарда реагирует на это состояние закрытием (`context.pop`) с этим
  значением.
- `AnimalRegistrationEventSaveAndAddAnother` тоже вызывает
  `insertAnimalWithDetailsCompanion` ровно один раз, но не переводит bloc в
  состояние `AnimalRegistrationExit`; после обработки `gender`, `birthDate`,
  `name`, `animalIdentifications`, `parents` в состоянии сброшены, а `kind`,
  `breed`, `suit`, `farm`, `place` — нет.

## Связанные тесты

- `test/pages/animal_registration_bloc_test.dart`, group `'UC-44/UC-45 — AnimalRegistrationEventSave — новое животное'`, первый `blocTest`
  (`'сохраняет животное локально через insertAnimalWithDetailsCompanion,
  эмитит Exit'`) — покрывает основной поток этого use-case: добавление
  идентификации, ввод номера, `AnimalRegistrationEventSave`, проверка
  `AnimalsCompanion.id` и что в БД попала ровно одна (заполненная)
  идентификация. Второй `blocTest` этой же группы (`'ошибка сохранения ->
  AnimalRegistrationMessage, затем откат в Success'`) — сценарий `ERROR`, не
  принадлежит этому (`CREATE_OK`) файлу.
- `test/pages/animal_registration_bloc_test.dart`, group
  `'AnimalRegistrationEventSaveAndAddAnother'` — покрывает альтернативный
  поток: сохранение и сброс `gender`/`birthDate`/`name`/
  `animalIdentifications`, один вызов `insertAnimalWithDetailsCompanion`. Имя
  группы не содержит собственной ссылки на `UC-44` (старая нумерация,
  переименование — отдельный контролируемый проход, не в рамках этого файла).

Группа `'UC-54 — AnimalRegistrationEventSaveWithoutIdentifier'` в этом же
файле в это use-case не входит — событие `AnimalRegistrationEventSaveWithoutIdentifier`
не диспатчится нигде в `lib/` (нет вызывающего сайта в
`animal_registration_page.dart` или где-либо ещё), т.е. недостижимо через
реальный визард; см. «Открытые вопросы».

## Открытые вопросы и ограничения

- `AnimalRegistrationEventSaveWithoutIdentifier` определено и обрабатывается в
  `AnimalRegistrationBloc`, покрыто тестом (`test/pages/
  animal_registration_bloc_test.dart`, group `'UC-54 —
  AnimalRegistrationEventSaveWithoutIdentifier'`), но ни в
  `animal_registration_page.dart`, ни где-либо ещё в `lib/` нет вызывающего
  сайта (`grep` по `lib/` на `AnimalRegistrationEventSaveWithoutIdentifier`
  находит только определение события и его обработчик) — событие
  недостижимо через реальный визард сегодня. Не рассматривается как
  альтернативный поток этого use-case; факт, зафиксированный здесь как
  контекст для дальнейшей ревизии, не разбираемый глубже в рамках этого
  файла.
- Поле бирки (`birkMarkerType`) на шаге маркировки не валидируется вообще —
  `identifications_step_page.dart` содержит закомментированный блок
  `validator`/`maxLength` с пометкой `RINTAGLE-395 06.05.2026 Убрана
  валидация у бирки`. Поле транспондера при этом валидируется
  (`Validator.animalIdentificationLocalization`). Так как `Animal.number` в
  этом сценарии на практике берётся из номера бирки (см. «Основной поток»,
  шаг 7), приоритетный номер животного может не проходить никакой проверки
  формата/дубликатов на этом шаге визарда — факт, зафиксированный здесь,
  дальше не разбираемый.
- После успешного сохранения обработчик `AnimalRegistrationEventSave` эмитит
  `AnimalRegistrationExit(unsentAnimalId: localId)`, а затем безусловно (вне
  `try`/`catch`) ещё раз `AnimalRegistrationSuccess(_data)` — с той же,
  неизменённой `_data`. Так как страница уже реагирует на `Exit` вызовом
  `context.pop`, вторая эмиссия внешне не наблюдаема; неясно, преднамеренный
  ли это «сброс» состояния (на случай, если что-то в UI успеет отреагировать
  до `pop`) или остаток кода, общего с error-веткой. Не разбирается дальше в
  рамках этого файла.
- Нет проверки на гонку между двумя параллельными вызовами `saveAnimal()`
  (например быстрым двойным нажатием «Зарегистрировать»/«Добавить ещё») —
  `nextLocalAnimalId()` читает `MIN(id)` отдельным запросом до вставки, без
  явной транзакционной изоляции между чтением и записью на уровне
  `AnimalRegistrationBloc`; сама вставка животного и идентификаций уже внутри
  одной транзакции (`AnimalsDao.insertAnimalWithDetailsCompanion`), но
  вычисление `localId` — нет. Не воспроизведено и не разбирается глубже в
  рамках этого файла.
