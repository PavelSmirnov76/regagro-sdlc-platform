# UC-95 — Пользователь открывает хаб ещё не отправленных взвешиваний

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает отдельный экран-хаб (`UnsentAnimalWeighingsPage`),
показывающий все локально созданные/отредактированные, ещё не отправленные на
сервер записи `AnimalWeighing` (`sync == false`) **по всем животным фермы
сразу** — не по одному животному, в отличие от истории взвешиваний конкретного
животного ([EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md)).
Экран — обычно один из пунктов сводного экрана «В работе» — основа для
последующей правки ([EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md),
см. [UC-85](UC-85-ACTOR-5-EVT-43-ENT-15-UPDATE_OK-IN-ANIMAL.md)) или удаления
([EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md), см.
[UC-87](UC-87-ACTOR-5-EVT-44-ENT-15-DELETE_OK-IN-ANIMAL.md)) конкретной строки.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `UnsentAnimalWeighingsPage`,
ни `AnimalWeighingsCubit`, ни `AnimalWeighingsRepository` не проверяют статус
авторизации на этом пути (`grep -rn "isAuthorized\|AuthRepository"` по
`lib/pages/animal_weighings/` не находит ни одного совпадения). Единственное
предусловие — переход с плитки «Взвешивание» экрана «В работе» (или
напрямую по имени маршрута `Routes.unsentAnimalWeighings`, у которого нет
собственных аргументов).

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`) и нажимает плитку
   «Взвешивание» (`EventTileData` с `icon: Assets.eventWeighing`,
   `count: data.animalWeighingsCount`) —
   `onTap: () => context.pushNamed2(Routes.unsentAnimalWeighings)`
   (`lib/pages/in_work/in_work_page.dart`). Плитка нажимаема независимо от
   значения `count` — `onTap` не гейтится проверкой количества (в отличие от
   бейджа плитки «Вакцинация», где ноль скрывает сам бейдж, но не блокирует
   переход).
2. `Routes.unsentAnimalWeighings` — маршрут верхнего уровня, зарегистрирован
   в `lib/pages/routes.dart` (`CustomGoRoute.fade(name: ...,
   builder: (context, state) => const UnsentAnimalWeighingsPage())`), без
   собственных аргументов конструктора.
3. `UnsentAnimalWeighingsPage.build` оборачивает тело в
   `BlocProvider(create: (context) => AnimalWeighingsCubit()..loadNotSync())`
   — `loadNotSync()` вызывается ровно один раз, сразу при создании кубита, без
   отдельного триггера (pull-to-refresh или кнопки обновления на экране нет).
4. `AnimalWeighingsCubit` стартует в состоянии `AnimalWeighingsState.initial()`
   (аргумент конструктора `super`); `loadNotSync()` сразу эмитит
   `AnimalWeighingsState.loading()`.
5. `loadNotSync()` вызывает
   `_animalWeightingsRepository.getAllNotSuncAnimalWeighings()`
   (`AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` →
   `AnimalWeighingsDao.getAllNotSuncAnimalWeighings`) — Drift-запрос `SELECT
   * FROM animal_weighings WHERE sync = 0`, **без ограничения по
   `animalId`** (в отличие от `load(animalId)`, который фильтрует
   `getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc([animalId])`) и без
   какого-либо иного предиката — у `AnimalWeighing` нет полей
   `deletedAt`/`updatedAt`, различающих «новую» и «отредактированную ранее
   отправленную» запись (см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)),
   так что оба случая попадают в этот список одинаково.
6. Для каждой строки результата (тип `AnimalWeighing`) метод строит
   `AnimalWeighingWithDetails`:
   - `animal: await _animalsRepository.getAnimalWithDetailsById(animalWeighing.animalId)`
     — отдельный запрос на строку (N+1), независимо от того, что несколько
     строк могут ссылаться на одно и то же животное;
   - `unit: animalWeighing.unitId != null ? await
     _unitsRepository.getById(animalWeighing.unitId!) : null` — тоже
     построчно, только когда `unitId` задан.
7. Собранный список сортируется на месте:
   `animalWeighingWithDetails.sort((a, b) =>
   a.animalWeighing.weighingDate.compareTo(b.animalWeighing.weighingDate))`
   — по возрастанию (`ASC`) по `weighingDate`. Это единственный из трёх
   методов кубита (`load`, `loadNotSync`, `initWithoutLoad`), где сортировка
   влияет на итоговый порядок карточек — все три сортируют идентично по
   возрастанию.
8. Кубит эмитит `AnimalWeighingsState.loadedNotSync(animalWeighings:
   animalWeighingWithDetails.toModel())` — `toModel()`
   (`AnimalWeighingModelMapper`, `lib/pages/animal_weighings/data/animal_weighing_model.dart`)
   заворачивает каждый элемент в `AnimalWeighingModel(animalWeighing: e)` с
   `isSelected: false` по умолчанию. **`placeName` в этом состоянии не
   заполняется** (остаётся `null` по значению `@Default`) — в отличие от
   `load(animalId)`, который явно резолвит `place` через
   `_placesRepository.getById(animal?.animal.placeId)` и передаёт
   `placeName: place?.name`; глобальный список по всем животным логически не
   привязан к одному месту.
9. `BlocBuilder<AnimalWeighingsCubit, AnimalWeighingsState>` в
   `UnsentAnimalWeighingsPage` рендерит по типу состояния (`switch`):
   - `AnimalWeighingsInitial`/`AnimalWeighingsLoading` (и любой иной,
     необработанный явно тип — общий `_` фолбэк) →
     `BottomSheetPageWrapper` с `CustomLottieLoader`.
   - `AnimalWeighingsLoadedNotSync(:final animalWeighings)` →
     `BottomSheetPageWrapper` с `AnimalWeighingListNotSyncWidget`, которому
     передаются `animalWeighings.map((e) => e.animalWeighing).toList()`
     (развёрнутые `AnimalWeighingWithDetails`, без обёртки `isSelected`),
     `onTapDel: context.read<AnimalWeighingsCubit>().delete` и `onTap`
     (переход на правку — вне этого сценария).
10. `AnimalWeighingListNotSyncWidget.build`: если переданный список пуст —
    возвращает `Center(child: ProgressMessage.notFound(message:
    l10n.list_is_empty))`; иначе — `ListView.separated` из карточек
    `_WeighingCard` (номер животного, дата+время взвешивания, вес с единицей
    измерения, иконка удаления). Проверка на пустоту выполняется **в самом
    виджете списка**, а не как отдельный branch `switch` в
    `UnsentAnimalWeighingsPage` (в отличие от аналогичного экрана вакцинаций,
    `UnsentVaccinationPage`, где пустой/непустой варианты различаются на
    уровне `switch` страницы) — оба случая используют одно и то же состояние
    кубита `AnimalWeighingsLoadedNotSync`.

### Альтернативные потоки

- **Пустой список (`AnimalWeighingsLoadedNotSync` с `animalWeighings.isEmpty`).**
  Не ошибка — `getAllNotSuncAnimalWeighings()` вернул `[]` (нет ни одной
  ещё не отправленной записи взвешивания). Кубит эмитит тот же вариант
  состояния, что и при непустом результате; разницу рисует
  `AnimalWeighingListNotSyncWidget` (см. шаг 10) — `ProgressMessage.notFound`
  вместо списка карточек. Тот же `RESULT` (`READ_OK`), другой визуальный
  итог — не отдельный use-case.
- **Исключение внутри `getAllNotSuncAnimalWeighings()` или построчных запросов
  (`getAnimalWithDetailsById`/`unitsRepository.getById`).** `loadNotSync()`
  целиком **не обёрнут в `try`/`catch`** (в отличие от `deleteImmediate` в
  том же кубите) — исключение пробрасывается наружу необработанным, минуя
  состояние кубита; `AnimalWeighingsState` не имеет отдельного
  error-варианта (`initial`/`loading`/`loaded`/`loadedNotSync` — и всё, см.
  `animal_weighings_state.dart`). `BlocProvider(create: ... ..loadNotSync())`
  не перехватывает такое исключение отдельно — практический эффект для
  пользователя (падение `Future` внутри построения провайдера, необработанный
  виджетом) этим файлом не прослеживался дальше по стеку. Отдельный `RESULT =
  READ_ERROR` для этого сценария не описан — по коду нет ветки, которая бы
  явно отличала его от успеха на уровне состояния экрана.
- **Возврат с экрана правки записи (`Routes.weighAnimal`) без повторной
  загрузки, если правка не привела к `result == true`.** `onTap` в
  `UnsentAnimalWeighingsPage` дожидается (`await`) результата навигации и
  вызывает `context.read<AnimalWeighingsCubit>().loadNotSync()` только когда
  `result == true` — при `result` = `false`/`null` (пользователь закрыл экран
  правки без сохранения) список не перезагружается автоматически. Сама
  правка — предмет [UC-85](UC-85-ACTOR-5-EVT-43-ENT-15-UPDATE_OK-IN-ANIMAL.md),
  здесь фиксируется только то, что этот `READ_OK`-сценарий не всегда
  перезапускается по возврату.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  единственная сущность, чьё состояние отображает этот экран; читаются все
  строки с `sync == false` по всем животным сразу, без дополнительного
  предиката (ни `deletedAt`, ни `updatedAt` у сущности нет).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — подгружается
  построчно (`AnimalWithDetails`, N+1) для каждой отображаемой записи
  взвешивания; на карточке показывается только `animal.number`.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается построчно, только когда у строки задан `unitId`;
  показывается на карточке рядом с весом (`unit?.name`).

### Бизнес-правила

- **Список этого экрана глобален по всем животным фермы** — единственный
  явный предикат запроса — `sync == false`, без фильтра по `animalId` (в
  отличие от [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md),
  который всегда ограничен одним животным).
- **`placeName` не резолвится в этом сценарии** — поле состояния существует
  (используется методом `load(animalId)` для истории одного животного), но
  `loadNotSync()` его не заполняет; на UI это не имеет эффекта, поскольку
  `UnsentAnimalWeighingsPage` не читает `state.placeName` вообще.
- Список сортируется по `weighingDate` **по возрастанию** (`ASC`, старые
  записи — вверху экрана).
- Экран не подписан на изменения таблицы `AnimalWeighings` реактивно
  (`watch`); `loadNotSync()` — разовый запрос на момент построения кубита,
  повторно вызывается только явно (`delete()` и успешный возврат из
  правки — оба вызывают `loadNotSync()` заново).
- `AnimalWeighingModel.isSelected` всегда `false` сразу после `toModel()` —
  выбор в этом сценарии никак не задействован (`UnsentAnimalWeighingsPage` не
  вызывает `selectAnimalWeighing`); поле существует для другого экрана
  (тип `AnimalWeighingModel` общий на все состояния кубита).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (оба варианта успеха: непустой список и пустой список)
полностью реализован и достижим из реального UI.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (плитка `EventTileData` с `icon: Assets.eventWeighing`) | CURRENT | обычная точка входа — переход по `Routes.unsentAnimalWeighings` |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (подписка на `AnimalWeighingsRepository.watchCountNotSync`) | CURRENT | считает бейдж плитки; не используется самим экраном-хабом напрямую |
| `lib/pages/routes.dart` | `Routes.unsentAnimalWeighings` | CURRENT | имя/путь маршрута → `UnsentAnimalWeighingsPage`, без аргументов |
| `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart` | `UnsentAnimalWeighingsPage.build` | CURRENT | создаёт кубит, вызывает `loadNotSync()` один раз, рендерит все состояния (`switch`) |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | предмет этого файла — загрузка глобального списка неотправленных |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState.loadedNotSync`, `AnimalWeighingWithDetails` | CURRENT | целевое состояние и модель строки (`AnimalWeighingsState` не имеет error-варианта) |
| `lib/pages/animal_weighings/data/animal_weighing_model.dart` | `AnimalWeighingModel`, `AnimalWeighingModelMapper.toModel` | CURRENT | обёртка строки с `isSelected` для UI-состояния |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.getAllNotSuncAnimalWeighings` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` | CURRENT | `SELECT ... WHERE sync = 0` — единственный предикат, без ограничения по `animalId` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAnimalWithDetailsById` | CURRENT | построчная (N+1) подгрузка животного для каждой записи взвешивания |
| `lib/repositories/unit/units_repository.dart` | `UnitsRepository.getById` | CURRENT | построчная подгрузка единицы измерения, только при заданном `unitId` |
| `lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart` | `AnimalWeighingListNotSyncWidget.build`, `_WeighingCard` | CURRENT | UI списка/карточки; сама решает, показывать список или `list_is_empty` |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.notFound` | CURRENT | UI пустого состояния |
| `lib/widgets/loader/custom_lottie_loader.dart` | `CustomLottieLoader` | CURRENT | UI состояния загрузки |

## Критерии приёмки

- При открытии хаба (`Routes.unsentAnimalWeighings`) кубит вызывает
  `loadNotSync()` ровно один раз без участия пользователя, независимо от
  текущего значения бейджа плитки «Взвешивание» на «В работе».
- `getAllNotSuncAnimalWeighings()` фильтрует строки исключительно по
  `sync == false`, по всем животным сразу — без ограничения по `animalId`.
- Итоговое состояние — `AnimalWeighingsLoadedNotSync`, список в нём
  отсортирован по `weighingDate` по возрастанию; `placeName` в этом состоянии
  всегда `null` (не резолвится).
- Если список пуст — экран показывает `ProgressMessage.notFound`
  (`l10n.list_is_empty`) вместо списка карточек; если непуст — карточки в
  порядке возрастания даты, у каждой — номер животного, дата/время, вес с
  единицей измерения (если `unitId` задан) и иконка удаления. Оба случая —
  один и тот же `RESULT` (`READ_OK`).

## Связанные тесты

`test/pages/animal_weighings_cubit_test.dart`, группа `'UC-95 —
AnimalWeighingsCubit.loadNotSync (В работе, глобальный список неотправленных)'`
(старый id — будет переименована в `UC-95` отдельным проходом):

- test `'успех -> сортирует по дате, unit только при unitId, placeName не
  резолвится'` — покрывает непустой вариант: два взвешивания разных животных
  с разными датами, мокнутый `getAllNotSuncAnimalWeighings()` возвращает их в
  порядке `id: 2` (позже по дате), `id: 1` (раньше); после `loadNotSync()`
  итоговый порядок — `[1, 2]` (сортировка по дате по возрастанию сработала),
  `state.placeName` — `isNull`, тип состояния —
  `AnimalWeighingsLoadedNotSync`. Второе взвешивание без `unitId` —
  `unitsRepository.getById` для него не вызывается (проверяется неявно, через
  мок только для `unitId: 7`).
- test `'пустой список -> loadedNotSync с пустым списком'` — мокнутый
  `getAllNotSuncAnimalWeighings()` возвращает `[]`; после `loadNotSync()`
  `state.animalWeighings` пуст, тип состояния — тот же
  `AnimalWeighingsLoadedNotSync`.

## Открытые вопросы и ограничения

- **Хаб не обновляется реактивно.** `loadNotSync()` — разовый вызов на момент
  создания кубита; если после открытия экрана где-то ещё (фоновым
  sync-проходом или взвешиванием другого животного из другого места
  приложения) появится/исчезнет ещё не отправленная запись, уже открытый
  экран этого не увидит без повторного вызова `loadNotSync()` (явно из
  `delete()` или из `onTap` при `result == true`) либо без полного
  пересоздания экрана.
- **Исключение внутри `loadNotSync()` не перехватывается и не отражается в
  состоянии.** `AnimalWeighingsState` не имеет error-варианта в принципе —
  даже если бы исключение из `getAllNotSuncAnimalWeighings()` или построчных
  запросов было поймано, отразить его в UI этого экрана сегодня нечем;
  отдельный `RESULT = READ_ERROR` для этого сценария не описан.
- **N+1 при построении списка.** На каждую запись — отдельный запрос
  животного и (при наличии `unitId`) отдельный запрос единицы измерения; не
  проверялось, при каком практическом размере очереди неотправленных
  взвешиваний это становится заметно пользователю.
- **Возврат с экрана правки перезагружает список только при `result ==
  true`.** При отмене правки без сохранения список не обновляется
  автоматически — не имеет практического значения для этого сценария (данные
  не менялись), но стоит иметь в виду при последующей работе с этим экраном.
- **`placeName` в состоянии игнорируется UI этого экрана.** Поле не заполняется
  `loadNotSync()` и не читается `UnsentAnimalWeighingsPage` — не дефект, но
  фиксирует, что часть общего состояния `AnimalWeighingsState` актуальна
  только для другого метода (`load`), не для этого сценария.
