# UC-119 — Пользователь открывает экран «Разведение» карточки животного, успех

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md) |
| Сущность | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает экран «Разведение» карточки уже зарегистрированного
животного и видит две вкладки — «Родители» (текущие мать/отец, если
привязаны или указаны текстом) и «Потомство» (все животные, у которых
`motherId`/`fatherId` указывает на просматриваемое животное). Одновременно с
этим экран заранее готовит два списка кандидатов (для последующей привязки
родителя/потомка — отдельные сценарии
[EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md)/[EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md)),
не только показывает уже сохранённые данные.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, разницы для этого сценария нет).

## CURRENT

### Основной поток

1. Пользователь находится на `AnimalCardPage`, в панели действий нажимает
   кнопку «Разведение» (`_AnimalCardToolbarAction` с `icon: Assets.reproduction`,
   `label: l10n.reproduction`) →
   `context.pushNamed2(Routes.reproduction, extra:
   ReproductionPageArguments(animal: animalWithDetails))`.
2. `Routes.reproduction` вложен под `Routes.animalDetails` (который вложен
   под `Routes.animalsRegistry`) в дереве маршрутов `routes.dart`, как
   родственный маршрут `Routes.animalHistory`/`Routes.animalEdit`.
   `ReproductionPage.build` читает аргумент через
   `GoRouterState.of(context).getExtraByName<ReproductionPageArguments>` и
   рендерит `ReproductionView(animal: animal)`.
3. `_ReproductionViewState.build` создаёт `BlocProvider<ReproductionCubit>` с
   `create: (context) { final cubit = ReproductionCubit(widget.animal)..load();
   … return cubit; }` — `load()` вызывается сразу же при создании кубита, без
   отдельного пользовательского действия. Изначальное состояние —
   `ReproductionState(animal: animal)` с `reproductionFilter:
   ReproductionFilter.parents` по умолчанию (вкладка «Родители» показывается
   первой).
4. `ReproductionCubit.load()` эмитит `state.copyWith(isLoading: true)`, затем
   читает `animalData = state.animal.animal` и берёт из неё исходные
   `motherBirk`/`fatherBirk`/`motherName`/`fatherName` (текстовые поля,
   заполняемые в том числе при ручном вводе «не зарегистрировано» — см.
   [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)).
5. **Резолв матери.** Если `state.animal.motherId != null` —
   `_animalsRepository.getAnimalWithDetailsById(motherId)`; если результат не
   `null`, `motherBirk`/`motherName` **замещаются** на
   `motherAnimal.firstMainNumber`/`motherAnimal.nameText` (не буквально
   «transponderId» — `firstMainNumber` берёт номер идентификации с флагом
   `main == true`, иначе `animal.number`, иначе `'-'`; `nameText` —
   `animal.name ?? '-'`). Если результат `null` (запись матери не найдена в
   локальной БД) — исходные `motherBirk` остаются без изменений.
6. **Резолв отца** — симметрично шагу 5, по `state.animal.fatherId` и
   `fatherAnimal.firstMainNumber`/`fatherAnimal.nameText`.
7. `Parents.fromInlineFields(motherId, fatherId, motherBirk, fatherBirk,
   motherName, fatherName, kindId: animalData.kindId)` строит `parents`:
   для каждого родителя запись добавляется в список, если хотя бы одно из
   `{id, birk, name}` не `null`; если ни один родитель не даёт ни одного
   непустого поля — `Parents.fromInlineFields` возвращает `null` целиком
   (`state.parents == null`).
8. `children = await _animalsRepository.getChildrenByParentId(animalId)` —
   без дополнительных фильтров/сортировки на уровне кубита; результат
   присваивается в `state.children` как есть (см. «Бизнес-правила» —
   DAO всё же применяет собственные фильтры по умолчанию).
9. `availableParents = await _animalsRepository.getAllAnimalsWithDetailsByFilters(
   kindIds: [state.animal.kind!.id], birthDateRange: DateTimeRange(start:
   DateTime(1900,1,1), end: state.animal.birthDate!), isShowRemoteSource:
   null)` — кандидаты того же вида, с датой рождения не позже даты рождения
   просматриваемого животного (включительно).
10. `availableChildren` — второй, отдельный вызов того же метода с
    `birthDateRange: DateTimeRange(start: state.animal.birthDate!, end:
    DateTime.now())` — кандидаты того же вида, с датой рождения не раньше
    даты рождения просматриваемого животного (включительно).
11. Эмитится финальное состояние: `parents`, `children`, `isLoading: false`,
    `addPparentsData: AddParentData(availableParents: availableParents)`,
    `addChildrenData: AddChildrenData(availableChildren: availableChildren)`.
12. `ReproductionView` перерисовывается через `BlocConsumer`: вкладка
    «Родители» (`ParentsWidget`) показывает мать/отца из `state.parents`
    (карточки `StatisticCardWidget`, `l10n.date_is_missing`, если родитель не
    найден вовсе); вкладка «Потомство» (`ChildrenWidget`) показывает
    `state.children` списком; счётчик потомков в
    `ReproductionFastFilterWidget` берётся из `state.children.length`.

### Альтернативные потоки

- **Родитель не привязан к записи, но указан текстом («не
  зарегистрировано»).** `motherId == null`, но `motherBirk` (или
  `motherName`) не `null` — шаг 5 не выполняется (условие `motherId != null`
  ложно), исходный текстовый `motherBirk` идёт в `Parents.fromInlineFields`
  как есть, с `id: null` — на UI отображается как обычная запись матери, без
  визуальной пометки «не найдено» отдельно от случая ниже.
- **`motherId` задан, но животное с этим id не найдено в локальной БД**
  (`getAnimalWithDetailsById` вернул `null`) — исходные `motherBirk`
  сохраняются без изменений; поведение неотличимо от предыдущего
  альтернативного потока на уровне итогового состояния (оба дают запись с
  `id: null`, текстовым `transponderId`).
- **Ни один родитель не задан вовсе** (ни `motherId`/`motherBirk`/`motherName`,
  ни `fatherId`/`fatherBirk`/`fatherName`) — `Parents.fromInlineFields`
  возвращает `null`, `state.parents == null`; вкладка «Родители» рендерит обе
  карточки (мать/отец) в состоянии «пусто» (`l10n.date_is_missing`, иконка
  `Assets.plus`).
- **У животного нет потомков** — `getChildrenByParentId` возвращает `[]`,
  `state.children` остаётся пустым списком, счётчик вкладки «Потомство» — 0.
- **Кандидатов для одного из справочных списков не нашлось** —
  `availableParents`/`availableChildren` остаются пустыми списками; это не
  влияет на отображение уже сохранённых родителей/потомков, только на
  автокомплит в модалках привязки (другой сценарий).

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — **используется
  дважды в рамках одного и того же прохода `load()`, как два разных
  экземпляра одной и той же сущности**: (1) просматриваемое животное
  (`state.animal`, аргумент экрана, источник `motherId`/`fatherId`/
  `motherBirk`/`fatherBirk`/`kindId`/`birthDate`) и (2) каждое из животных,
  найденных через `getAnimalWithDetailsById(motherId/fatherId)`,
  `getChildrenByParentId`, и оба вызова `getAllAnimalsWithDetailsByFilters` —
  все они читают ту же Drift-таблицу `Animals`, просто другие строки
  (родитель, потомок, кандидат).

### Бизнес-правила

- **Резолв родителя не по «transponderId», а по `firstMainNumber`.**
  `firstMainNumber` — номер идентификации с флагом `main == true`, при её
  отсутствии — `animal.number`, при отсутствии обоих — `'-'`; это не
  обязательно транспондер конкретно (см.
  `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart`
  → `AnimalWithDetailsExtension.firstMainNumber`).
- **Замена происходит только при успешном резолве, иначе остаются
  исходные текстовые поля.** `motherBirk`/`fatherBirk`, сохранённые прямо на
  просматриваемом животном, — источник истины по умолчанию; резолв через
  `getAnimalWithDetailsById` — попытка получить более свежие данные,
  молча отбрасываемая при неудаче (запись не найдена).
- **`getChildrenByParentId` наследует фильтры DAO по умолчанию, хотя вызов
  из кубита их не указывает явно.** `AnimalsDao.getChildrenByParentId`
  сперва выбирает id животных с `motherId == parentId OR fatherId ==
  parentId` (без фильтра `isNotDeleted`/`source` на этом шаге), затем
  дозагружает детали через `getAllAnimalsWithDetailsByFilters(ids: …)` —
  **без** явного `isNotDeleted`/`isShowRemoteSource`/`animalParentId`, из-за
  чего применяются дефолты сигнатуры DAO: `isNotDeleted: true` (выбывшие/
  удалённые потомки исключаются), `isShowRemoteSource: false` (потомки с
  непустым `animal.source` исключаются), `animalParentId == null` →
  `WHERE animalParentId IS NULL` (потомки, зарегистрированные как часть
  составной группы — `isSuperGroup`/`animalParentId`, — исключаются). Ни
  один из этих трёх фильтров не упомянут ни в `ReproductionCubit`, ни в
  UI — обнаружено чтением `AnimalsDao.getAllAnimalsWithDetailsByFilters`.
- **`availableParents`/`availableChildren` разделены строго по `birthDate`
  просматриваемого животного, оба конца диапазона включительны.**
  `AnimalsDao.getAllAnimalsWithDetailsByFilters` использует
  `isBiggerOrEqualValue`/`isSmallerOrEqualValue` — животное с датой рождения
  ровно равной `state.animal.birthDate` попадает **в оба** списка
  кандидатов одновременно (родителей и потомков).
- **Кандидаты фильтруются тем же дефолтом `animalParentId == null`, что и
  потомки** — составные/групповые животные не предлагаются ни в качестве
  кандидата-родителя, ни кандидата-потомка. `isShowRemoteSource` для
  кандидатов кубит явно переопределяет на `null` (в отличие от потомков,
  где остаётся дефолт `false`) — фильтр по `source` для кандидатов снят,
  для уже привязанных потомков — нет; расхождение не задокументировано и,
  судя по отсутствию комментария в коде, не намеренное.
- **Оба списка кандидатов не исключают само просматриваемое животное по
  id.** Ни `load()`, ни `AnimalsDao.getAllAnimalsWithDetailsByFilters` не
  фильтруют по `id != state.animal.animalId` — при совпадающем виде и
  граничной дате рождения животное может оказаться кандидатом самому себе
  (частично отсекается позже, при построении автокомплита в модалках
  привязки, не в `load()`).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и достижим с единственной точки
входа (кнопка «Разведение» на карточке животного).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_AnimalCardToolbarAction` (кнопка «Разведение») | CURRENT | точка входа — единственный способ попасть на экран «Разведение» |
| `lib/pages/routes.dart` | `Routes.reproduction` | CURRENT | маршрут, вложен под `Routes.animalDetails` |
| `lib/pages/reproduction/presentation/reproduction_page.dart` | `ReproductionPage.build`, `ReproductionPageArguments` | CURRENT | читает аргумент маршрута, рендерит `ReproductionView` |
| `lib/pages/reproduction/presentation/widgets/reproduction_view.dart` | `_ReproductionViewState.build` | CURRENT | создаёт `ReproductionCubit(animal)..load()` сразу при построении, рендерит вкладки «Родители»/«Потомство» |
| `lib/pages/reproduction/cubit/reproduction_cubit.dart` | `ReproductionCubit.load` | CURRENT | основной метод сценария — резолв родителей, чтение потомков, построение двух списков кандидатов |
| `lib/pages/reproduction/cubit/reproduction_state.dart` | `ReproductionState` | CURRENT | freezed-состояние экрана (`parents`, `children`, `addPparentsData`, `addChildrenData`, `reproductionFilter`, `isLoading`) |
| `lib/pages/reproduction/data/add_parent_data.dart` | `AddParentData`, `AddChildrenData` | CURRENT | контейнеры списков кандидатов, заполняемые в конце `load()` |
| `lib/models/parents.dart` | `Parents.fromInlineFields` | CURRENT | строит (или возвращает `null`) обёртку `parents` из резолвленных полей матери/отца |
| `lib/widgets/items/animal_pedigree_item.dart` | `GenealogyAnimal` | CURRENT | базовый класс `Parents` (`id`/`transponderId`/`birthDate`/`gender`/`kindId`) |
| `lib/widgets/fast_filter/reproduction_fast_filter_widget.dart` | `ReproductionFilter` | CURRENT | enum вкладок «Родители»/«Потомство», по умолчанию `parents` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | резолв актуальных данных матери/отца по `motherId`/`fatherId` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getChildrenByParentId` | CURRENT | тонкая обёртка над DAO, без параметров |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | строит оба списка кандидатов (по одному вызову на каждый) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getChildrenByParentId` | CURRENT | `WHERE motherId = id OR fatherId = id`, затем делегирует детали в `getAllAnimalsWithDetailsByFilters(ids: …)` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | источник дефолтных фильтров `isNotDeleted`/`isShowRemoteSource`/`animalParentId`, применяемых молча ко всем трём вызовам этого сценария |
| `packages/sheep_farm_database/lib/entities/animal/animals_with_details.dart` | `AnimalWithDetailsExtension.firstMainNumber`, `.nameText`, `.kind`, `.birthDate` | CURRENT | поля, читаемые/подставляемые в `load()`; `kind`/`birthDate` нужны для не защищённых `!`-обращений в шагах 9–10 |

## Критерии приёмки

- Открытие экрана «Разведение» вызывает `ReproductionCubit.load()` ровно
  один раз, в момент создания кубита (без отдельного действия пользователя).
- Если `motherId`/`fatherId` заданы и `getAnimalWithDetailsById` находит
  животное — в `parents` попадают `firstMainNumber`/`nameText` найденного
  животного, а не исходные текстовые поля просматриваемого животного.
- Если `motherId`/`fatherId` заданы, но животное не найдено — в `parents`
  остаются исходные `motherBirk`/`fatherBirk` без изменений.
- Если ни для одного из родителей нет ни `id`, ни текстового номера, ни
  имени — `state.parents == null`.
- `state.children` равен результату `getChildrenByParentId(animalId)` без
  дополнительной фильтрации/сортировки на уровне кубита.
- `availableParents` и `availableChildren` формируются двумя отдельными
  вызовами `getAllAnimalsWithDetailsByFilters` с одинаковым `kindIds:
  [state.animal.kind!.id]` и взаимно исключающими (по границе, но
  включительно с обеих сторон) диапазонами дат рождения относительно
  `state.animal.birthDate`.
- `isLoading` переключается `true` → `false` по завершении `load()`
  независимо от того, найдены ли родители/потомки/кандидаты.

## Связанные тесты

`test/pages/reproduction_cubit_test.dart`, `group('UC-119 — ReproductionCubit.load')`:

- `'нет данных о родителях -> parents=null, справочники всё равно
  заполняются'` — `parents` равен `null`, `isLoading` — `false`,
  `addPparentsData`/`addChildrenData` не `null` (справочники заполняются
  даже при отсутствии родителей).
- `'motherId задан, мать найдена в репозитории -> motherBirk берётся из
  найденного животного'` — запись матери в `parents.parents` имеет `id`
  найденного животного и `transponderId`, равный номеру его транспондера.
- `'motherId задан, мать НЕ найдена в репозитории -> используются исходные
  motherBirk животного'` — запись матери сохраняет исходный текстовый
  `transponderId`, несмотря на заданный `motherId`.
- `'fatherId задан, отец найден в репозитории -> fatherBirk берётся из
  найденного животного'` — симметричный тест для отца.
- `'children заполняется результатом getChildrenByParentId'` — `state.children`
  равен списку, который вернул мок `getChildrenByParentId(5)`.
- `'availableParents фильтруются датой рождения ДО текущего животного,
  availableChildren — ПОСЛЕ'` — проверяет ровно два вызова
  `getAllAnimalsWithDetailsByFilters` (шесть захваченных именованных
  аргументов — по три на вызов) и что `parentsRange.end == birthDate`,
  `childrenRange.start == birthDate`.

Имя группы уже содержит `UC-202` (старый id, до переименования — по
конвенции проекта группа будет переименована в `UC-119` отдельным проходом,
не в рамках этого файла); анкер `grep -r "UC-202" test/` находит её сегодня.

## Открытые вопросы и ограничения

- **`load()` не обёрнут в `try/catch`.** В отличие от `saveParent`/`saveChild`
  в том же файле (которые ловят исключение, логируют через `Talker.error` и
  сбрасывают `isLoading: false`), `load()` не перехватывает ошибки вовсе —
  исключение из любого из пяти `await` (резолв матери/отца, потомки, два
  списка кандидатов) уйдёт необработанным из `Future`, а `isLoading: true`,
  выставленный в начале метода, никогда не сбросится обратно — экран
  застрянет в состоянии загрузки.
- **`state.animal.kind!.id` и `state.animal.birthDate!` — необработанные
  null-assertion'ы.** Оба поля (`Kind? kind`, `DateTime? birthDate` на
  `AnimalWithDetails`) нативно нулабельны. Для `birthDate` есть
  верифицированный код, где он реалистично остаётся `null`: в
  `AnimalRegistrationBloc.saveAnimal` поле `birthDate` пишется безусловно
  как `Value(_data.birthDate)`, тогда как `birthDateFrom`/`birthDateTo`
  заполняются только при `_data.isBirthDateRangeStepSuccess` — то есть
  животное, для которого при регистрации использовался шаг диапазона дат, а
  не шаг одной даты, может дойти до этого экрана с `birthDate == null` и
  уронить `load()` на шаге 9 (см. выше). Кнопка «Разведение» на карточке
  животного не делает никакой предварительной проверки перед переходом.
- **Дефолтные фильтры DAO (`isNotDeleted`, `isShowRemoteSource`,
  `animalParentId`) применяются молча ко всем трём вызовам сценария**, не
  будучи явно упомянутыми ни в `ReproductionCubit`, ни где-либо в UI — см.
  «Бизнес-правила». В частности, потомки/кандидаты, относящиеся к составной
  группе (`isSuperGroup`/`animalParentId != null`), никогда не появятся ни
  во вкладке «Потомство», ни в автокомплитах привязки — не найдено
  указаний, что это осознанное продуктовое решение, а не побочный эффект
  того, что вызовы не передают этот параметр явно.
- **Кандидаты в родители/потомки не исключают само просматриваемое
  животное по `id`.** Отсечение (частичное, только для потомков) происходит
  позже, в модалках привязки ([EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md)/[EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md),
  другой use-case) — сам `load()`, специфицируемый этим файлом, строит
  списки кандидатов без такой проверки.
- **Тестовая группа именована по старому id (`UC-202`), не по `UC-119`.**
  Переименование — отдельный проход, оговорено в задаче на этот файл; ссылка
  в разделе «Связанные тесты» верна на сегодняшний день, но `grep -r
  "UC-119" test/` пока ничего не найдёт.
