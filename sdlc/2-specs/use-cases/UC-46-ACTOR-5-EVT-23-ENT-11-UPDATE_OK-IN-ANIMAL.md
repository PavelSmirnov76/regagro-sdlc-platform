- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md), [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)

# UC-46 — Пользователь редактирует ещё не синхронизированное животное, локальное сохранение успешно

## Назначение

Пользователь правит данные уже зарегистрированного, но ещё не отправленного на
сервер животного (`Animal.id < 0`) через отдельный экран
`UnsentAnimalEditPage`/`UnsentAnimalEditBloc` — не `AnimalEditPage`, тот путь
только для уже синхронизированных животных (см.
[EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)). Правка
сохраняется прямо в ту же локальную строку: полная замена
[ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) по `id` плюс полная
пересборка идентификаций
([ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)). Сценарий
завершается успешно: обе операции репозитория проходят без исключения,
`errors` сбрасывается в `null`, `id` остаётся тем же отрицательным значением —
животное по-прежнему целиком уйдёт на сервер при следующей полной
синхронизации, отдельного флага отложенной отправки, в отличие от
[EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md), не требуется.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Доступ к экрану не требует
авторизации; единственное условие — животное уже зарегистрировано локально и
ещё не синхронизировано (`id < 0`).

## CURRENT

### Основной поток

1. Пользователь попадает на экран одним из двух подтверждённых кодом путей:
   списком неотправленных животных (`RemovableLocalAnimalItem.onTap` →
   `context.pushNamed2(Routes.unsentAnimalEdit, extra: item.animal.id)` в
   `lib/pages/unsent_animals/unsent_animals_page.dart`), либо из карточки
   животного через попап «Ещё» — пункт «Редактировать» при
   `animal.animal.id < 0` ведёт на тот же маршрут с
   `extra: animal.animalId` (`lib/pages/animal_card/animal_card_page.dart`).
2. `UnsentAnimalEditPage` читает `animalId` из
   `GoRouterState.of(context).getExtraByName<int?>(Routes.unsentAnimalEdit)` и
   создаёт `BlocProvider<UnsentAnimalEditBloc>(create: (context) =>
   UnsentAnimalEditBloc(unsentAnimalId: animalId)..add(UnsentAnimalStart()))`.
3. `UnsentAnimalEditBloc.on<UnsentAnimalStart>`: т.к. `unsentAnimalId < 0`
   (`isLocalEdit == true`), грузит `AnimalWithDetails` через
   `_animalsRepository.getAnimalWithDetailsById(unsentAnimalId)`, справочники
   (типы маркеров, виды, поколения), и т.к. животное найдено —
   `_data.addLocalAnimal(...)` заполняет породы/масти, ограниченные `kindId`
   животного, текущие идентификации (через
   `AnimalIdentificationForRegistration.fromAnimalIdentification`),
   мать/отца по id и `Parents.fromInlineFields(...)` из инлайн-полей
   животного (`motherId`/`fatherId`/`motherBirk`/`fatherBirk`/`motherName`/
   `fatherName`). Эмитит `UnsentAnimalEditSuccess(_data, updateControllers:
   true)`.
4. `_BodyState.build` (`unsent_animal_edit_page.dart`) при
   `state.updateControllers == true` заполняет `TextEditingController`ы вида,
   породы, масти, даты рождения, диапазона дат, пола, клички, номера УХФ и
   визуальной бирки из `_data`.
5. Пользователь правит только те поля, что реально подключены к диспетчеру
   событий на этом экране: порода (чип или `SearchDropdownField<Breed>` →
   `UnsentAnimalEditEventChangeBreed`), масть (чип или поиск →
   `UnsentAnimalEditEventChangeSuit`), пол (`_GenderToggle` →
   `UnsentAnimalEditEventChangeGender`), дата рождения (`CustomDatePicker.orange`
   или переключатель «дата неизвестна» →
   `UnsentAnimalEditEventChangeBirthDate`), номер транспондера и визуальной
   бирки (`RTextField.outline` →
   `UnsentAnimalEditEventChangeIdentification` с `markerTypeId:
   Constants.TransponderMarkerTypeId`/`Constants.BirkMarkerTypeId`). Вид
   животного показан как read-only чип (`onTap: null`); кличка, диапазон дат
   рождения, поколение и родословная на этом экране никак не редактируются —
   см. «Альтернативные потоки».
6. Каждый обработчик правки эмитит `UnsentAnimalEditInProgress()`, затем
   свежий `UnsentAnimalEditSuccess(_data, ...)` — все изменения живут только в
   памяти блока (`_data`), без обращения к БД животного.
7. Пользователь нажимает `_SaveButton`; страница вызывает
   `widget.formKey.currentState?.validate()` (валидатор номера транспондера —
   длина ровно 15 + `Validator.animalIdentificationLocalization`; у визуальной
   бирки валидатора нет, `validator: (_) => null`) и только при успехе
   диспатчит `UnsentAnimalEditEventSave()`.
8. `on<UnsentAnimalEditEventSave>`: вычисляет `mother`/`father` из
   `_data.parents` (не меняется в рамках этого сценария — на экране нет
   обработчика, диспатчащего `UnsentAnimalEditEventChangePedigree`), собирает
   `animal = _data.localAnimal!.animal.copyWith(...)` — `userId`, `number`
   (из `_data.animalIdentifications.firstOrNull?.number`), `kindId`,
   `breedId`, `suitId`, `birthDate`, `gender`, `generation`, `name`, `errors:
   const Value(null)`, `motherId`/`motherBirk`/`motherName`,
   `fatherId`/`fatherBirk`/`fatherName`, `birthDateFrom`/`birthDateTo`
   (только если `_data.isUnsentAnimalBirthDateRangeSuccess`, иначе `null`) —
   и вызывает `await _animalsRepository.update(animal)` →
   `BaseRepository<AnimalsDao, Animal, $AnimalsTable>.update` → `dao.upd(item)`
   → `BaseDao.upd` = `updateCurrent().replace(item)`: полная замена строки по
   `id`, сам `id` не меняется (остаётся тем же отрицательным значением, шаг
   замены id на серверный из этого сценария не выполняется).
9. Исходные строки идентификации (`_data.localAnimal!.animalIdentifications`)
   удаляются целиком через
   `_animalIdentificationsRepository.deleteAll(...)`, затем текущие
   in-memory `_data.animalIdentifications` вставляются заново как новые
   строки (новые autoincrement `id`) через
   `_animalIdentificationsRepository.insertAll(...)`, построенные как
   `AnimalIdentificationsCompanion.insert(userId, createdAt: animal.createdAt,
   animalId: animal.id, markerTypeId: ai.markerTypeId, identificationReasonId:
   1 /* локальная константа, не из исходной строки */, markerDate:
   ai.markerDate, number: ai.number, markerPlaceId: ai.markerPlaceId,
   otherMarkerPlace: ai.otherMarkerPlace, main: ai.main, isEmission: true
   /* всегда true */)`.
10. При успехе эмитит `UnsentAnimalEditMessage('animal_successfully_saved')`,
    затем `UnsentAnimalEditExit()`, затем `UnsentAnimalEditSuccess(_data)`.
11. `UnsentAnimalEditPage`'s `BlocConsumer.listener`: на
    `UnsentAnimalEditMessage` показывает снекбар через
    `rootScaffoldMessengerKey.currentState?.showSnackBar` с
    `AppLocalizations.of(context)!.tr(state.message)`; на
    `UnsentAnimalEditExit` вызывает `Navigator.of(context).pop()`.

### Альтернативные потоки

- **`unsentAnimalId >= 0` при открытии экрана.** `isLocalEdit == false`,
  `localAnimal` не запрашивается, `on<UnsentAnimalStart>` эмитит
  `UnsentAnimalEditFailure()` — этот сценарий сюда не попадает (экран вообще
  предназначен только для `id < 0`, см. точки входа в «Основной поток»).
- **`unsentAnimalId < 0`, но животное не найдено в БД** (`getAnimalWithDetailsById`
  вернул `null`) — тоже `UnsentAnimalEditFailure()`, до какого-либо
  редактирования дело не доходит.
- **Половина обработчиков событий блока недостижима из этого экрана.**
  Прочтение всего `lib/` (`grep -rn` по каждому имени события вне
  `unsent_animal_edit_bloc.dart`/`unsent_animal_edit_event.dart`) не находит
  ни одного диспатча `UnsentAnimalEditEventChangeKind`,
  `UnsentAnimalEditEventChangeName`,
  `UnsentAnimalEditEventChangeBirthDateRange`,
  `UnsentAnimalEditEventChangeGeneration`,
  `UnsentAnimalEditEventChangePedigree` или отдельного (не через
  `ChangeIdentification`) `UnsentAnimalEditEventChangeTransponderNumber` —
  реализованы и оттестированы, но ни один виджет `UnsentAnimalEditPage` их не
  диспатчит. Практический эффект: вид, кличка, диапазон дат рождения,
  поколение и родословная всегда сохраняются такими, какими были загружены,
  через этот экран их поменять нельзя, хотя бизнес-логика для этого в блоке
  есть.
- **`_data.unsentAnimalIdentificationDuplicates` вычисляется, но нигде не
  читается на этом экране.** `UnsentAnimalEditEventChangeIdentification`
  ищет дубликаты номера+типа маркера среди локальных животных
  (`_animalIdentificationsRepository.getAllByFilters(...)`) и кладёт их в
  `_data.unsentAnimalIdentificationDuplicates`, но
  `UnsentAnimalEditPage`/`_Body` это поле нигде не используют (единственный
  читатель в `lib/` — `animal_registration_page.dart`, экран визарда
  регистрации, не этот). Собственный валидатор поля УХФ на этом экране вызывает
  `Validator.animalIdentificationLocalization` с
  `usedAnimalIdentificationNumbers: const []` — предупреждение о совпадающем
  номере на этом экране никогда не показывается, даже если найдено.
- **Сохранение падает с исключением** (например ошибка БД в
  `_animalsRepository.update`/`deleteAll`/`insertAll`) — отдельный сценарий,
  `RESULT = UPDATE_ERROR`, не описан этим файлом: `try`/`catch` вокруг всего
  обработчика ловит исключение, логирует его (`getIt<Talker>().error(e)`) и
  эмитит `UnsentAnimalEditMessage('an_error_data')` без `UnsentAnimalEditExit`
  — покрыто отдельным тестом (см. «Связанные тесты»).

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность
  сегмента `ENT` в id: полная замена строки по `id`
  (`updateCurrent().replace`), `id` не меняется, `errors` безусловно
  сбрасывается в `null`.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — все существующие строки удаляются и создаются
  заново (новые `id`), не патчатся; `Animal.number` берётся из первого
  элемента актуального in-memory списка идентификаций.

### Бизнес-правила

- Правка не взводит никакого флага отложенной отправки — `id < 0` уже само по
  себе гарантирует, что вся запись целиком уйдёт на сервер при следующей
  синхронизации (см. [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md)).
  Это отличает сценарий от [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)
  (`AnimalEditBloc`, `needsUpdate: true`).
- `AnimalsRepository.update` — полная замена строки по `id` (Drift `replace`),
  а не patch отдельных изменённых столбцов; любое поле `Animal`, явно не
  выставленное в `copyWith(...)` перед `update`, сохраняется тем, что уже
  лежало в `_data.localAnimal!.animal` на момент загрузки экрана — включая
  вид, кличку, диапазон дат рождения, поколение и родословную, реально не
  редактируемые через этот экран (см. «Альтернативные потоки»).
- Идентификации не патчатся, а полностью пересоздаются
  (`deleteAll` + `insertAll`) — при пересоздании `identificationReasonId`
  безусловно выставляется в локальную константу `1`, `isEmission` — в `true`,
  независимо от значений исходной удалённой строки; `clinic`,
  `complectNumber`, `description` и `isActive` исходной строки вовсе не
  переносятся, потому что `AnimalIdentificationForRegistration` (in-memory
  модель, которой оперирует блок) не хранит эти поля —
  `AnimalIdentificationForRegistration.fromAnimalIdentification` их не
  копирует, а `AnimalIdentificationsCompanion.insert` в обработчике сохранения
  их не передаёт.
- `errors: const Value(null)` сбрасывает любые ранее сохранённые серверные
  ошибки валидации (`Animal.errorsMap`, см.
  [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)) при каждом успешном
  локальном сохранении, независимо от того, поменялись ли реально
  проблемные поля.
- Три записи в хранилище (`update` животного, `deleteAll` и `insertAll`
  идентификаций) выполняются последовательными `await` вне единой
  БД-транзакции — прочтение `on<UnsentAnimalEditEventSave>` не находит
  оборачивающего `transaction(...)`. Падение между `deleteAll` и `insertAll`
  оставило бы животное без единой строки идентификации.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован и покрыт тестом на успешную ветку (см.
«Связанные тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/unsent_animals/unsent_animals_page.dart` | `_List.build` (`RemovableLocalAnimalItem.onTap`) | CURRENT | точка входа №1 — список неотправленных животных |
| `lib/pages/animal_card/animal_card_page.dart` | попап «Ещё» → пункт «Редактировать» (ветка `animal.animal.id < 0`) | CURRENT | точка входа №2 — карточка животного |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_page.dart` | `UnsentAnimalEditPage.build`, `_BodyState.build` | CURRENT | чтение `animalId` из `GoRouterState` extra, создание блока, форма — только breed/suit/gender/birthDate/УХФ/бирка реально подключены к диспетчеру событий |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart` | `UnsentAnimalEditBloc.on<UnsentAnimalStart>` | CURRENT | загрузка `localAnimal` + справочников, `addLocalAnimal` |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart` | `UnsentAnimalEditBloc.on<UnsentAnimalEditEventSave>` | CURRENT | сохранение: `update` животного + `deleteAll`/`insertAll` идентификаций |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (наследует `BaseRepository<AnimalsDao, Animal, $AnimalsTable>.update`) | CURRENT | делегирует в `dao.upd` |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository` (наследует `BaseRepository<AnimalIdentificationsDao, AnimalIdentification, $AnimalIdentificationsTable>.deleteAll`/`.insertAll`) | CURRENT | удаление/вставка строк идентификации |
| `lib/repositories/base_repository.dart` | `BaseRepository.update`, `BaseRepository.deleteAll`, `BaseRepository.insertAll` | CURRENT | делегирование в `BaseDao` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd`, `BaseDao.delAll`, `BaseDao.insAll` | CURRENT | `upd` = `updateCurrent().replace(item)` — полная замена строки по `id` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals`, `Animal`, `AnimalExtension.errorsMap`/`errorsByKey` | CURRENT | таблица/модель; поле `errors`, сбрасываемое при сохранении |
| `packages/sheep_farm_database/lib/entities/animal_identification/animal_identifications.dart` | `AnimalIdentifications`, `AnimalIdentificationsCompanion`, `AnimalIdentificationForRegistration` | CURRENT | пересоздаваемые строки идентификации; поля, не переносимые из исходной строки при пересборке |
| `lib/models/parents.dart` | `Parents.fromInlineFields` | CURRENT | восстановление родителей из инлайн-полей животного при старте экрана |
| `lib/utilts/validator.dart` | `Validator.animalIdentificationLocalization` | CURRENT | валидация номера транспондера на этом экране (`usedAnimalIdentificationNumbers` всегда пустой) |

## Критерии приёмки

- Открытие экрана для `animalId < 0`, найденного в БД, эмитит
  `UnsentAnimalEditSuccess` с заполненными контроллерами породы/масти/пола/
  даты рождения/УХФ/бирки (`updateControllers == true`).
- Правка породы, масти, пола, даты рождения, номера УХФ и номера бирки через
  подключённые обработчики событий отражается в `_data` без вызова
  `AnimalsRepository`/`AnimalIdentificationsRepository`.
- Успешное сохранение вызывает `AnimalsRepository.update` ровно один раз с
  животным, чей `id` равен исходному отрицательному `id` (не меняется) и
  `errors == null`.
- Успешное сохранение также вызывает
  `AnimalIdentificationsRepository.deleteAll` с исходным списком
  идентификаций этого животного и затем `.insertAll` с числом новых строк,
  равным `_data.animalIdentifications.length`.
- Успех эмитит `UnsentAnimalEditMessage('animal_successfully_saved')`, затем
  `UnsentAnimalEditExit()`, затем `UnsentAnimalEditSuccess(_data)`; страница
  показывает снекбар и вызывает `Navigator.of(context).pop()`.

## Связанные тесты

- `test/pages/unsent_animal_edit_bloc_test.dart`, group `'UC-46 — UnsentAnimalEditEventSave'` (старая нумерация, переименуется отдельным
  контролируемым проходом — не трогать сейчас), test `'успех -> обновляет
  животное на месте (id остаётся отрицательным), пересоздаёт идентификации
  (deleteAll+insertAll)'` — покрывает этот сценарий.
- Тот же файл, group `'UC-47 — UnsentAnimalEditEventSave'` (тоже старая
  нумерация), test `'ошибка сохранения -> UnsentAnimalEditMessage("an_error_data"),
  без Exit'` — покрывает соседний `RESULT = UPDATE_ERROR`, не этот файл.
- Дальнейшая судьба этого животного (оно остаётся `id < 0` и уходит на сервер
  при следующем полном sync-проходе целиком, как обычное локальное создание —
  не отдельным «edit-sync» путём, см. [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)) —
  **TBD — теста нет**: `test/blocs/data_update_bloc_test.dart` не содержит ни
  одной группы, помеченной `EVT-25`/`EVT-26`, и не проверяет, что именно
  отредактированные этим сценарием поля доживают до сервера.

## Открытые вопросы и ограничения

- **Значительная часть публичного API блока недостижима из UI.**
  `UnsentAnimalEditEventChangeKind`/`ChangeName`/`ChangeBirthDateRange`/
  `ChangeGeneration`/`ChangePedigree`/отдельный `ChangeTransponderNumber`
  реализованы и оттестированы, но `UnsentAnimalEditPage` их не диспатчит —
  вид, кличка, диапазон дат рождения, поколение и родословная на этом экране
  фактически не редактируемы, хотя полное сохранение (`copyWith` в
  `on<UnsentAnimalEditEventSave>`) формально их учитывает. Требует внимания
  при следующей ревизии — не собственный дефект этого use-case (он описывает
  то, что реально достижимо и успешно), но источник путаницы при чтении
  одного только кода блока.
- **`_data.unsentAnimalIdentificationDuplicates` вычисляется, но никогда не
  показывается на этом экране** — собственный inline-валидатор поля УХФ
  всегда передаёт `usedAnimalIdentificationNumbers: const []`, то есть
  предупреждение о дублирующемся номере маркера, которое показывает визард
  регистрации, на этом экране никогда не появляется, даже если бэкенд-запрос
  дубликат нашёл.
- **Пересборка идентификаций теряет метаданные исходной строки.**
  `identificationReasonId` при пересоздании всегда выставляется в `1`,
  `isEmission` — всегда в `true`; `clinic`/`complectNumber`/`description`/
  `isActive` исходной строки не переносятся вовсе, т.к.
  `AnimalIdentificationForRegistration` их не хранит. Для животного,
  идентификации которого изначально сохранялись с другим
  `identificationReasonId`/`isEmission`/дополнительными полями (например,
  через визард регистрации), любое сохранение через этот экран тихо
  нормализует их — не проверено в рамках этого файла, насколько это осознанное
  упрощение или недосмотр.
- **Три записи хранилища в `on<UnsentAnimalEditEventSave>` не объединены в
  одну БД-транзакцию** — `update` животного, `deleteAll` и `insertAll`
  идентификаций идут последовательными `await` без оборачивающего
  `transaction(...)`; падение между `deleteAll` и `insertAll` оставило бы
  животное без единой строки идентификации до следующей успешной попытки
  сохранения.
- Downstream-судьба отредактированных этим сценарием полей на следующем
  sync-проходе не проверена тестами (см. «Связанные тесты») — открытый вопрос
  для будущей use-case спеки по [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md).
