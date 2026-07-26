- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md), [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)

# UC-48 — Пользователь редактирует уже синхронизированное животное, локальное сохранение успешно

## Назначение

Пользователь правит породу/масть/дату рождения/пол уже синхронизированного
животного (`id >= 0`) через `AnimalEditBloc` и сохраняет изменения. Запись
[ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) обновляется только
локально, с флагом `needsUpdate: true` — сама отправка правки на сервер
откладывается до следующего sync-прохода
([EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)), а не выполняется
немедленно.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный одинаково; `AnimalEditBloc` не проверяет
статус авторизации сам по себе). Вход в сценарий обусловлен состоянием самого
животного, не пользователя: правка через этот блок доступна только для уже
синхронизированного животного (`id >= 0`) — для локального (`id < 0`) тот же
пункт меню карточки ведёт в отдельный `UnsentAnimalEditBloc`
(`Routes.unsentAnimalEdit`), не покрытый этим файлом.

## CURRENT

### Основной поток

1. Пользователь открывает карточку животного (`animal.animal.id >= 0`) и в
   меню действий выбирает пункт «Редактировать»
   (`l10n.animal_actions_edit`, `lib/pages/animal_card/animal_card_page.dart`)
   — ветка `animal.animal.id < 0` там же ведёт в `Routes.unsentAnimalEdit`,
   иначе — `context.pushNamed2(Routes.animalEdit, extra: animal.animalId)`.
2. `AnimalEditPage` (`lib/pages/animal_edit/animal_edit_page.dart`) читает
   `animalId` из `GoRouterState.of(context).getExtraByName<int?>`, создаёт
   `BlocProvider<AnimalEditBloc>(create: (_) =>
   AnimalEditBloc(animalId: animalId)..add(AnimalStart()))`.
3. `AnimalStart`-обработчик эмитит `AnimalEditInProgress`, проверяет
   `NetworkConnectivityService.hasConnection()` (при отсутствии сети —
   отдельный альтернативный поток, см. ниже, не часть этого успешного
   сценария), затем читает
   `_animalsRepository.getAnimalWithDetailsById(animalId)`,
   `GenerationsTypesRepository.getAll()`, `MarkerTypesRepository.getAll()`,
   `KindsRepository.getAllVisibleKinds()`. Поскольку животное уже
   синхронизировано, `getAnimalWithDetailsById` возвращает непустой
   `AnimalWithDetails` — вызывается `_data.addAnimal(...)`, догружающий
   `breeds`/`suits` по `kindId` животного (`BreedsRepository.getAllByKindId`,
   `SuitsRepository.getAllByKindId`, отсортированные без диакритики) и
   `mother`/`father` по `motherId`/`fatherId` (если заданы). Финально —
   `emit(AnimalEditSuccess(_data, updateControllers: true))`.
4. `_Body` (`animal_edit_page.dart`) на `updateControllers: true` заполняет
   текстовые контроллеры формы из `_data` и рендерит форму: вид — статичный
   `Text('${type}: ${data.kind?.name}')` (read-only, без обработчика правки —
   см. «Альтернативные потоки»), порода — `SearchDropdownField<Breed>` →
   `AnimalEditEventChangeBreed`, масть — `SearchDropdownField<Suit>` →
   `AnimalEditEventChangeSuit`, дата рождения — `RTextField.outline` с маской
   + `RDatePicker` → `AnimalEditEventChangeBirthDate`, пол —
   `DropdownButtonFormField<Gender>` → `AnimalEditEventChangeGender`, и кнопка
   «Сохранить» (`RElevatedButton`, key `'b1'`).
5. Пользователь меняет одно или несколько полей — каждое событие
   (`AnimalEditEventChangeBreed`/`ChangeSuit`/`ChangeBirthDate`/
   `ChangeGender`) синхронно обновляет `_data` через `copyWithWrapped` и
   эмитит `AnimalEditSuccess(_data)` (`ChangeBirthDate` дополнительно с
   `updateControllers: true`, чтобы переформатировать текст поля даты).
6. Пользователь нажимает «Сохранить»; `formKey.currentState?.validate() ==
   true` (валидаторы — обязательность породы/масти/даты рождения/пола через
   `Validator.flagLocalization`) → `bloc.add(AnimalEditEventSave())`.
7. `AnimalEditEventSave`-обработчик эмитит `AnimalEditInProgress`, собирает
   `mother`/`father` из `_data.parents` (в этом сценарии обычно `null` — форма
   родословную не рендерит, см. «Альтернативные потоки»), и строит `updated =
   edit.copyWith(kindId: ..., breedId: Value(_data.breed?.id ?? edit.breedId),
   suitId: Value(...), birthDate: Value(_data.birthDate), gender:
   _data.gender?.id ?? edit.gender, name: Value(_data.name), generation:
   Value(_data.animal?.animal.generation), birthDateFrom/To: Value(...),
   motherId/motherBirk/motherName, fatherId/fatherBirk/fatherName)`, где
   `edit = _data.animal!.animal` — текущая загруженная запись как база;
   изменённые пользователем поля перекрывают её, остальные остаются как были.
8. Поскольку `updated.id >= 0` (условие сегмента `RESULT` этого файла) —
   вызывается `_animalsRepository.update(updated.copyWith(needsUpdate: const
   Value(true)))`. `AnimalsRepository.update` наследуется от
   `BaseRepository<AnimalsDao, Animal, $AnimalsTable>.update` → `dao.upd(item)`
   — обычный Drift-апдейт строки по `id`, **без какого-либо сетевого запроса**.
9. `update()` возвращает `true` → `emit(const AnimalEditExit())`, затем
   `emit(AnimalEditMessage('animal_successfully_saved'))`; в конце обработчика
   — ещё раз `emit(AnimalEditSuccess(_data))` (уже не влияет на экран, т.к.
   `BlocConsumer.listener` реагирует на `AnimalEditExit` раньше).
10. `BlocConsumer.listener` в `AnimalEditPage`: на `AnimalEditMessage` —
    `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
    Text(AppLocalizations.of(context)!.tr(state.message))))` (ad-hoc
    `ScaffoldMessenger`, не через `lib/widgets/app_snackbar.dart`); на
    `AnimalEditExit` — `Navigator.of(context).pop()`, экран закрывается.
11. Animal с `needsUpdate == true` остаётся в локальной БД; фактическая
    отправка на сервер — отдельное событие
    [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md), инициируемое
    следующим sync-проходом, не этим сценарием.

### Альтернативные потоки

- **Вид (`kindId`) — read-only на этой форме.** `AnimalEditEventChangeKind`
  объявлен и обработан в `AnimalEditBloc`, но всё тело обработчика
  закомментировано (`// emit(const AnimalEditInProgress()); ...`), и ни один
  виджет `animal_edit_page.dart` его не диспатчит (`grep -rn
  "AnimalEditEventChangeKind(" lib/` не находит вызовов вне объявления/теста)
  — вид животного технически неизменяем этим сценарием, хотя поле `kindId` в
  `AnimalEditEventSave` формально участвует в сборке `updated` (всегда равным
  прежнему значению, `_data.kind` заполняется из уже загруженного животного и
  не имеет способа измениться).
- **Кличка/номер/поколение/родословная поддержаны в блоке, но недостижимы
  через UI этого экрана.** `AnimalEditEventChangeName`,
  `AnimalEditEventChangeGeneration`, `AnimalEditEventChangeTransponderNumber`,
  `AnimalEditEventChangePedigree`, `AnimalEditEventChangeIdentification`
  реализованы в `AnimalEditBloc` и меняют `_data`, но ни один из
  соответствующих контроллеров/виджетов не отрисован в
  `animal_edit_page.dart` (поля кличка/номер/родословная присутствуют только
  как `TextEditingController`, без окружающего `RTextField`/поля формы) —
  `_data.name`/`_data.parents`/`_data.animalIdentifications` доходят до
  `AnimalEditEventSave` неизменными относительно того, с чем экран
  стартовал.
- **Отсутствие сети при открытии экрана.** `AnimalStart` вызывает
  `NetworkConnectivityService.hasConnection()`; при `false` —
  `emit(const AnimalEditExit())` + `emit(AnimalEditMessage('internet_connection_required'))`
  сразу закрывают экран с точки зрения пользователя (слушатель реагирует на
  `AnimalEditExit`), хотя код обработчика не делает `return` после этого и
  продолжает грузить справочники/животное и эмитить `AnimalEditSuccess` уже
  после того, как экран практически закрыт — см. «Открытые вопросы».
  Собственно локальное сохранение (шаги 7–9) сетевого запроса не делает
  вовсе, так что проверка сети относится только к открытию экрана, не к
  сохранению.
- **`update()` возвращает `false` или бросает исключение** — отдельный
  сценарий, `RESULT = UPDATE_ERROR`, этим файлом не описан (см.
  `test/pages/animal_edit_bloc_test.dart`, группа `'UC-49 — AnimalEditEventSave'`).
- **Животное локальное (`id < 0`)** технически недостижимо в рамках этого
  файла — вход в `AnimalEditBloc` для `id < 0` не происходит через реальную
  навигацию (см. «Пользователь»); тем не менее сам `AnimalEditEventSave`
  структурно поддерживает и эту ветку (`needsUpdate` не выставляется при
  `id < 0`) — она проверена тестом внутри той же группы `'UC-59'`, а не
  отдельным use-case, так как в продукте недостижима.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность
  сегмента `ENT` в id: обновляемая запись; поля `breedId`/`suitId`/
  `birthDate`/`gender` заменяются пользовательским вводом, `kindId`/`name`/
  `generation`/родительские поля переносятся как были (недостижимы для
  правки на этой форме), `needsUpdate` взводится в `true`.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается вместе с животным
  (`animal.animalIdentifications`) и используется только для отображения
  (`firstMainNumber` в подзаголовке `CustomAppBar`); этим сценарием не
  создаётся, не меняется и не удаляется — `AnimalEditEventSave` не пишет в
  таблицу `AnimalIdentifications`.

### Бизнес-правила

- `needsUpdate: true` выставляется **только** когда `updated.id >= 0`
  (`updated.id >= 0 ? updated.copyWith(needsUpdate: const Value(true)) :
  updated`) — инвариант [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), это
  и есть условие, отличающее этот сценарий (`RESULT = UPDATE_OK` для уже
  синхронизированного животного) от локальной правки ещё не отправленного
  животного.
- `AnimalsRepository.update` → `dao.upd` — полная замена строки по `id`
  (Drift), не частичный patch отдельных изменённых столбцов; любое поле
  `Animal`, не выставленное явно в `updated.copyWith(...)` внутри
  `AnimalEditEventSave`, сохраняется тем, что уже лежало в `edit =
  _data.animal!.animal` на момент вызова.
- Сохранение — синхронное с точки зрения UI (пользователь видит успех сразу
  после локальной записи в БД); собственно отправка на сервер откладывается
  на следующий sync-проход, как и для правки фермы/места
  ([EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md),
  [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md)) — этот же паттерн
  повторяется в модуле [MOD-4](../modules/MOD-4-ANIMAL.md).
  `AnimalEditEventSave` не оборачивает шаги 7–8 избирательно: весь блок целиком
  в `try`/`catch`, поэтому и ошибка сборки `updated`, и ошибка самого
  `update()` приводят к одному и тому же `AnimalEditMessage('an_error_data')`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом на успешную ветку
(`test/pages/animal_edit_bloc_test.dart`, группа `'UC-48 — AnimalEditEventSave'`). Уровень sync-прохода
([EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md), фактическая
отправка отложенной правки на сервер) тестами уровня
`lib/blocs/data_update/data_update_bloc.dart` не покрыт вовсе — TBD, теста
нет.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_MoreSheetItem` (пункт `animal_actions_edit`) | CURRENT | реальная точка входа — ветвление по `animal.animal.id < 0` на `Routes.unsentAnimalEdit`/`Routes.animalEdit` |
| `lib/pages/animal_edit/animal_edit_page.dart` | `AnimalEditPage.build`, `_Body.build` | CURRENT | читает `animalId` из `GoRouterState`, создаёт `AnimalEditBloc`, рендерит форму (порода/масть/дата рождения/пол + кнопка сохранить), слушает `AnimalEditMessage`/`AnimalEditExit` |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalStart>` | CURRENT | загружает животное и справочники, проверяет сеть (см. «Альтернативные потоки») |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalEditEventSave>` | CURRENT | собирает `updated` из `_data`, при `updated.id >= 0` взводит `needsUpdate: true`, вызывает `_animalsRepository.update` |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalEditEventChangeBreed>`, `on<AnimalEditEventChangeSuit>`, `on<AnimalEditEventChangeBirthDate>`, `on<AnimalEditEventChangeGender>` | CURRENT | реально достижимые сеттеры формы |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalEditEventChangeKind>` | CURRENT (мёртвый обработчик) | тело закомментировано, недиспатчится из UI |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalEditEventChangeName>`, `on<AnimalEditEventChangeGeneration>`, `on<AnimalEditEventChangeTransponderNumber>`, `on<AnimalEditEventChangePedigree>`, `on<AnimalEditEventChangeIdentification>` | CURRENT (недостижимо из UI) | реализованы, но не имеют соответствующего поля формы в `animal_edit_page.dart` |
| `lib/pages/animal_edit/animal_edit_event.dart` | `AnimalEditEventSave` | CURRENT | событие сохранения |
| `lib/pages/animal_edit/animal_edit_state.dart` | `AnimalEditSuccess`, `AnimalEditExit`, `AnimalEditMessage`, `AnimalEditInProgress` | CURRENT | состояния экрана |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (наследует `BaseRepository<AnimalsDao, Animal, $AnimalsTable>.update`) | CURRENT | делегирует в `dao.upd`, без сетевого вызова |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` |
| `lib/services/network_connectivity_service.dart` | `NetworkConnectivityService.hasConnection` | CURRENT | проверка сети при открытии экрана (не при сохранении) |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals`, `Animal`, `needsUpdateKey` | CURRENT | таблица/модель, поле `needsUpdate` |

## Критерии приёмки

- Открытие карточки уже синхронизированного животного (`id >= 0`) и выбор
  «Редактировать» ведёт на `Routes.animalEdit`, не `Routes.unsentAnimalEdit`.
- `AnimalStart` при наличии сети загружает животное и справочники и эмитит
  `AnimalEditSuccess` с непустым `data.animal`.
- Изменение породы/масти/даты рождения/пола на форме отражается в `_data` без
  ошибки; вид (`kindId`) не имеет способа измениться через UI этого экрана.
- `AnimalEditEventSave` при валидной форме вызывает
  `AnimalsRepository.update` ровно один раз с копией животного, где
  `id == updated.id` (без изменения знака) и `needsUpdate == true`, если
  исходный `id >= 0`.
- Успешный `update()` (`true`) эмитит `AnimalEditExit` и
  `AnimalEditMessage('animal_successfully_saved')` — экран закрывается,
  пользователь видит снекбар с текстом успеха; ни одного сетевого запроса
  при этом не выполняется.

## Связанные тесты

- `test/pages/animal_edit_bloc_test.dart`, группа `'UC-48 — AnimalEditEventSave'`, тест `'успех -> Animal.update() с needsUpdate:true
  (id >= 0), Exit + сообщение об успехе'` — покрывает основной поток этого
  файла целиком: захватывает переданный в `update()` объект и проверяет
  `id == 5`/`needsUpdate == true`.
- Уровень [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)
  (фактическая отправка отложенной правки на сервер через
  `lib/blocs/data_update/data_update_bloc.dart`) — TBD, теста нет.

## Открытые вопросы и ограничения

- **`AnimalStart` не делает `return` после отказа по сети.** При
  `!isNetworkConnected` блок эмитит `AnimalEditExit` +
  `AnimalEditMessage('internet_connection_required')`, но продолжает
  выполнение того же обработчика — грузит животное/справочники и эмитит ещё
  `AnimalEditSuccess(_data, updateControllers: true)` уже после сигнала о
  закрытии экрана. Практического следствия для пользователя не имеет
  (`Navigator.pop()` в листенере уже отработал на `AnimalEditExit`), но
  является реальной раздвоенностью потока состояний, не единственным
  корректным путём выхода — обнаружено при чтении кода, не задокументировано
  отдельным use-case (сценарий отказа по сети не имеет собственного `RESULT`
  файла — реальное сохранение не требует сети вовсе, так что сама проверка
  на этом экране избыточна относительно того, что дальше происходит в
  `AnimalEditEventSave`).
- **Снекбар об успехе идёт через ad-hoc `ScaffoldMessenger.showSnackBar`**, а
  не через `lib/widgets/app_snackbar.dart` (`showAppSnackBarSuccess`/…),
  которого требует `.claude/rules/ui-architecture.md` для новых мест —
  зафиксировано здесь как факт существующего кода, не решение в рамках этого
  прохода (frozen use-case описывает CURRENT, не переписывает его).
- **`kindId`/`name`/`generation`/родословная участвуют в сборке `updated`
  внутри `AnimalEditEventSave`, но не имеют способа измениться на этой
  форме** — при последующем изменении дизайна (если поля добавят на форму)
  этот файл перестанет описывать полный набор изменяемых полей и потребует
  нового use-case, а не правки этого (сценарий заморожен).
