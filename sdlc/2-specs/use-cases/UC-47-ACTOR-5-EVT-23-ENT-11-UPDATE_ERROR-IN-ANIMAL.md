# UC-47 — Сохранение правки ещё не синхронизированного животного отказывает технически: исключение перехватывается, снэкбар с общей ошибкой, экран не закрывается (ERROR)

## Назначение

Документирует ERROR-исход события [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md)
(`animal.local_edited`) так, как он реализован в
`UnsentAnimalEditBloc.on<UnsentAnimalEditEventSave>`: попытка сохранить правку
ещё не синхронизированного животного (`id < 0`) бросает исключение на одном из
локальных DB-вызовов (обновление [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)
и/или пересоздание его идентификаций — [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)).
Исключение перехватывается единым `catch` на весь обработчик, логируется через
`Talker`, и пользователю показывается общий, не специфичный для поля снэкбар —
экран редактирования при этом не закрывается, введённые значения не
сбрасываются. Это чисто технический сбой (Drift/SQLite или иное исключение
Dart), а не отказ бизнес-правила — сервер здесь вообще не участвует: правка
локального животного не уходит по сети, а сохраняется прямо в локальную
запись (см. [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md)).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково; экран и его бизнес-логика не
делают различий по статусу авторизации).

## CURRENT

### Основной поток

1. **Предпосылка.** У пользователя уже есть локально заведённое, ещё не
   синхронизированное животное (`Animal.id < 0`). Экран открывается двумя
   равнозначными путями — оба передают `animal.id` как `extra` в
   `context.pushNamed2(Routes.unsentAnimalEdit, extra: ...)`:
   - карточка животного → пункт «Редактировать» в нижнем шите
     (`_MoreSheetItem` в `lib/pages/animal_card/animal_card_page.dart`), где
     `if (animal.animal.id < 0)` ведёт на `Routes.unsentAnimalEdit`, а не на
     `Routes.animalEdit`;
   - список неотправленных животных (`UnsentAnimalsPage` →
     `RemovableLocalAnimalItem.onTap` в
     `lib/pages/unsent_animals/unsent_animals_page.dart`).
2. `UnsentAnimalEditPage` создаёт `UnsentAnimalEditBloc(unsentAnimalId:
   animalId)..add(UnsentAnimalStart())`. `on<UnsentAnimalStart>` подгружает
   животное через `_animalsRepository.getAnimalWithDetailsById(unsentAnimalId)`
   и наполняет `_data.localAnimal` — этот успешный запуск является
   предпосылкой сценария, не его частью (см. смежный сценарий OK).
3. Пользователь правит поля формы (вид/порода/масть/дата рождения/пол/
   кличка/идентификации/родословная) — каждое изменение уходит отдельным
   событием (`UnsentAnimalEditEventChange...`) и меняет только `_data` в
   памяти, ничего не пишет в БД.
4. Пользователь нажимает кнопку сохранения. `_SaveButton.onTap` в
   `unsent_animal_edit_page.dart` сначала вызывает
   `widget.formKey.currentState?.validate()`; только если валидация формы
   прошла (`== true`), диспатчится `UnsentAnimalEditEventSave()` — то есть
   сценарий этого use-case начинается **после** успешной клиентской валидации
   формы, отказ здесь не может быть отказом валидации (это отдельный,
   REJECTED-класс сценария, не документируемый здесь).
5. `on<UnsentAnimalEditEventSave>` в `UnsentAnimalEditBloc` выполняется целиком
   внутри одного `try`: читает `_authRepository.getUser()?.id`, разбирает
   `_data.parents` на `mother`/`father`, и (при `_data.localAnimal != null`)
   строит `animal = _data.localAnimal!.animal.copyWith(...)` — новый объект
   `Animal` с текущими значениями формы, в т.ч. `errors: const Value(null)`
   (сброс серверных ошибок — вступит в силу, только если `update` ниже
   реально дойдёт до БД, см. «Открытые вопросы»).
6. `await _animalsRepository.update(animal)` — `AnimalsRepository` не
   переопределяет `update`, это унаследованный
   `BaseRepository.update(Insertable<D> item) => dao.upd(item)`
   (`lib/repositories/base_repository.dart`), который делегирует в
   `BaseDao.upd(item) => updateCurrent().replace(item)`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — обычный
   drift `replace` по первичному ключу (`animal.id`, который здесь
   отрицательный).
7. **Этот вызов бросает исключение** (ошибка drift/SQLite — например,
   нарушение ограничения на уровне таблицы `Animals`/`Kinds` и т.п., либо
   любое другое исключение, всплывающее из DAO/цепочки `Future`). Это ветка,
   прямо воспроизведённая тестом (см. «Связанные тесты») — мок
   `animalsRepository.update(any())` настроен `thenThrow(Exception('db
   error'))`.
8. Исключение перехватывается общим `catch (e)` обработчика:
   `getIt<Talker>().error(e)` — логирует исключение (без стека вызовов: сюда
   передаётся только `e`, второй, опциональный параметр `Talker.error` со
   стек-трейсом не заполняется, в отличие, например, от
   `AnimalsRepository.sendIdentificationToApi`, который логирует и `e`, и
   `stackTrace`).
9. Сразу после логирования эмитится `UnsentAnimalEditMessage('an_error_data')`
   — единственное, что происходит в `catch`-ветке. `'an_error_data'` — общий,
   не специфичный для этого экрана ключ локализации (`lib/l10n/app_en.arb`:
   `"An error occurred while processing data"`), переиспользуемый ещё в
   `data_update_bloc.dart`, `animal_edit_bloc.dart`, `scanning_bloc.dart`,
   `animal_disposal_bloc.dart`, `vaccination_bloc.dart`,
   `animal_movement_bloc.dart` — не собственный текст для правки локального
   животного.
10. После `catch`-блока (а не внутри него) выполняется общий для обеих веток
    финальный вызов: `emit(UnsentAnimalEditSuccess(_data))`. Важно:
    **`_data` не менялся этим обработчиком вообще** — локальные переменные
    `animal`/`mother`/`father` строились только для передачи в `update`, но
    никогда не присваивались обратно в `_data` — поэтому состояние экрана
    после ошибки идентично состоянию до нажатия кнопки сохранения: все
    введённые значения формы остаются на месте, ничего не сбрасывается и не
    перезатирается.
11. `UnsentAnimalEditExit()` **не эмитится** в этой ветке (в отличие от
    успешного пути, где `emit(UnsentAnimalEditMessage(
    'animal_successfully_saved')); emit(const UnsentAnimalEditExit());`
    следуют одно за другим перед финальным `Success`) — поэтому
    `UnsentAnimalEditPage`'s `BlocConsumer.listener` не вызывает
    `Navigator.of(context).pop()`: экран остаётся открытым.
12. Тот же `listener` реагирует на `UnsentAnimalEditMessage` показом снэкбара:
    `rootScaffoldMessengerKey.currentState?.showSnackBar(SnackBar(content:
    Text(AppLocalizations.of(context)!.tr(state.message))))`
    (`lib/pages/routes.dart`: `rootScaffoldMessengerKey`) — не через
    `lib/widgets/app_snackbar.dart` (`showAppSnackBarError`/`showAppSnackBarInfo`
    и т.д.), а через ad-hoc `SnackBar` с дефолтным оформлением темы, в обход
    принятого в проекте хелпера.
13. Никакого повтора/retry, отката ранее изменённых локальных полей (нечего
    откатывать — `_data` не трогался) или иной реакции нет — на этом
    обработка события заканчивается, пользователь может нажать сохранение
    повторно с теми же или изменёнными значениями формы.

### Альтернативные потоки

- **Исключение бросает не `AnimalsRepository.update`, а один из двух
  последующих вызовов внутри того же `try`.** Если `update(animal)`
  завершается успешно, но `_animalIdentificationsRepository.deleteAll(
  _data.localAnimal!.animalIdentifications)` (вызывается только когда старый
  список идентификаций непуст) или последующий
  `_animalIdentificationsRepository.insertAll(animalIdentifications)`
  (вызывается только когда новый список непуст) бросает исключение — оба
  падают в тот же самый `catch (e)`, с тем же самым исходом: `Talker.error`,
  `UnsentAnimalEditMessage('an_error_data')`, без `Exit`. Кода, различающего
  эти три точки отказа, нет — они неотличимы друг от друга по итоговому
  состоянию блока и относятся к одному и тому же `UPDATE_ERROR`-сценарию, не
  к разным use-case (тот же принцип, что в соседнем модуле FARM — см.
  [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)). Существующий
  тест покрывает только первую из трёх точек (`update` бросает) — см.
  «Связанные тесты».
- **`_data.localAnimal == null` на момент `EventSave`.** Обработчик пропускает
  весь `if (_data.localAnimal != null) { ... }`-блок целиком (включая
  `update`/`deleteAll`/`insertAll`) и падает сквозь `try` без исключения —
  `catch` не срабатывает вовсе, эмитится только финальный
  `UnsentAnimalEditSuccess(_data)`, без `Message`/`Exit`. Это не отказ (нет
  брошенного исключения, ничего не пытались писать в БД) — покрыто отдельным
  тестом (`UnsentAnimalEditEventSave — доп. ветка`), но не входит в этот
  UPDATE_ERROR use-case: сюда причисляется только ветка, где исключение
  реально брошено.
- **OK-исход того же обработчика — не входит в этот сценарий.** Если все три
  DB-вызова (`update`/`deleteAll`/`insertAll`) завершаются без исключения,
  обработчик эмитит `UnsentAnimalEditMessage('animal_successfully_saved')`,
  затем `UnsentAnimalEditExit()`, затем `UnsentAnimalEditSuccess(_data)` —
  соседний, не документируемый здесь исход того же
  [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md).
- **Правка уже синхронизированного животного (`id >= 0`) — другой код, другой
  сценарий.** Карточка животного при `animal.animal.id >= 0` ведёт на
  `Routes.animalEdit`/`AnimalEditBloc`, не на `UnsentAnimalEditBloc` — это
  [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md), отдельный
  use-case с собственной ERROR-веткой, не описываемый здесь.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность,
  которую пытается обновить сценарий (`AnimalsRepository.update`); это же
  `ENT`-сегмент имени файла. При ошибке строка в БД не меняется (drift
  `replace` — атомарный DML-вызов; если он бросает исключение, сама операция
  не применяется).
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — пересоздаётся тем же обработчиком сразу после
  `Animal.update` (`deleteAll` старых записей + `insertAll` новых); при ошибке
  именно на этом шаге возможно рассогласованное промежуточное состояние (см.
  «Открытые вопросы»).

### Бизнес-правила

- Сохранение целиком локальное — сервер не участвует ни на одном шаге этого
  сценария (в отличие от аналогичной правки уже синхронизированного животного,
  где `needsUpdate` откладывает реальную отправку до ближайшего sync-прохода).
- Клиентская валидация формы (`formKey.currentState.validate()`) — гейт,
  предшествующий диспатчу `UnsentAnimalEditEventSave` целиком на уровне
  виджета; сценарий этого use-case начинается только после того, как эта
  валидация уже пройдена, — отказ здесь никогда не является отказом
  валидации формы.
- Единый `catch` объединяет все возможные технические причины отказа (drift/
  SQLite-исключение на `update`, на `deleteAll`, на `insertAll`, либо любое
  иное исключение внутри `try`, включая гипотетические сбои чтения
  `_authRepository.getUser()`) в один и тот же исход — сообщение не несёт
  никакой информации о том, какой именно шаг отказал.
- Сообщение об ошибке — общий, переиспользуемый в приложении ключ
  `'an_error_data'`, не специфичный ни для животного, ни для этого экрана.
- Экран не закрывается и не сбрасывает введённые пользователем значения —
  повторная попытка сохранения возможна немедленно, без повторного открытия
  экрана.
- Обработчик не откатывает уже выполненные до отказа шаги (нет транзакции,
  оборачивающей `update`+`deleteAll`+`insertAll` вместе) и не проверяет
  булев результат, который в норме (без исключения) возвращает
  `AnimalsRepository.update` — см. «Открытые вопросы».

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик, включая единственную протестированную точку отказа
(`AnimalsRepository.update` бросает исключение) и общую для всех трёх
DB-вызовов обработку ошибок, полностью прослеживается в существующем коде и
покрыт тестом на уровне блока.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_MoreSheetItem` (действие «Редактировать», ветка `animal.animal.id < 0`) | CURRENT | точка входа №1 — карточка животного ведёт на `Routes.unsentAnimalEdit`, а не `Routes.animalEdit`, именно для ещё не синхронизированного животного |
| `lib/pages/unsent_animals/unsent_animals_page.dart` | `_List` (`RemovableLocalAnimalItem.onTap`) | CURRENT | точка входа №2 — список неотправленных животных, тот же переход |
| `lib/pages/routes.dart` | маршрут `Routes.unsentAnimalEdit` (`CustomGoRoute.fade`) | CURRENT | регистрация экрана `UnsentAnimalEditPage` в дереве `go_router` |
| `lib/pages/routes.dart` | `rootScaffoldMessengerKey` | CURRENT | глобальный ключ `ScaffoldMessengerState`, через который экран показывает снэкбар с ошибкой |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_page.dart` | `_SaveButton.onTap` | CURRENT | гейт клиентской валидации формы перед диспатчем `UnsentAnimalEditEventSave` |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_page.dart` | `UnsentAnimalEditPage.build` → `BlocConsumer.listener` | CURRENT | показывает `SnackBar` по `UnsentAnimalEditMessage`, вызывает `Navigator.of(context).pop()` только по `UnsentAnimalEditExit` (в этой ветке не эмитится) |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart` | `UnsentAnimalEditBloc.on<UnsentAnimalEditEventSave>` | CURRENT | единый `try/catch` на весь обработчик; в `catch` — `Talker.error(e)` + `emit(UnsentAnimalEditMessage('an_error_data'))`, без `Exit`; `_data` этим обработчиком не изменяется |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_event.dart` | `UnsentAnimalEditEventSave` | CURRENT | событие без полей — весь payload берётся из уже накопленного `_data` блока |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_state.dart` | `UnsentAnimalEditMessage`, `UnsentAnimalEditSuccess`, `UnsentAnimalEditExit` | CURRENT | состояния, участвующие в этой ветке (`Message`+`Success`) и в соседней успешной ветке (дополнительно `Exit`) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (`extends BaseRepository<AnimalsDao, Animal, $AnimalsTable>`) | CURRENT | не переопределяет `update` — использует базовую реализацию; протестированная точка отказа сценария |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` / `deleteAll` / `insertAll` | CURRENT | `dao.upd(item)` / `dao.delAll(list)` / `dao.insAll(list)` — тонкие обёртки, возврат `update` (`Future<bool>`) в этом обработчике не читается |
| `lib/repositories/animal_identification/animal_identification_repository.dart` | `AnimalIdentificationsRepository` | CURRENT | не переопределяет `deleteAll`/`insertAll` — базовая реализация `BaseRepository` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` / `delAll` / `insAll` | CURRENT | `upd` — `updateCurrent().replace(item)`, реальный drift-вызов, способный бросить исключение; `delAll`/`insAll` — транзакция/батч поверх `del`/`insertAll(mode: insertOrReplace)` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `AnimalExtension.errorsMap` / `errorsByKey` | CURRENT | источник серверных ошибок, отображаемых под полями формы; на пути этого сценария не меняется, т.к. `_data.localAnimal` не переприсваивается при ошибке (см. «Открытые вопросы») |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` (`case 'an_error_data'`) | CURRENT | ручной маппинг динамического ключа `state.message` на локализованную строку |
| `lib/l10n/app_en.arb` | ключ `"an_error_data"` | CURRENT | `"An error occurred while processing data"` — текст, реально показанный пользователю |
| `lib/injection_container.dart` | регистрация `TalkerFlutter.init` | CURRENT | источник синглтона `getIt<Talker>()`, используемого в `catch`-ветке для логирования |

## Критерии приёмки

- Если `_data.localAnimal != null` и любой из трёх вызовов —
  `AnimalsRepository.update`, `AnimalIdentificationsRepository.deleteAll`,
  `AnimalIdentificationsRepository.insertAll` — бросает исключение,
  `UnsentAnimalEditBloc` эмитит ровно `UnsentAnimalEditMessage('an_error_data')`
  и затем `UnsentAnimalEditSuccess(_data)`; `add(UnsentAnimalEditEventSave())`
  не приводит к необработанному исключению снаружи блока (`completes`, а не
  `throwsA(...)`).
- В этой ветке `UnsentAnimalEditExit` не эмитится ни разу — экран не
  закрывается.
- `_data` (в т.ч. `_data.localAnimal`, `_data.animalIdentifications` и все
  прочие поля формы) после ошибки идентичен состоянию непосредственно перед
  диспатчем `UnsentAnimalEditEventSave` — обработчик не производит частичных
  или ошибочных мутаций состояния экрана.
- `getIt<Talker>().error(e)` вызывается ровно один раз на попытку сохранения,
  предшествуя эмиссии `UnsentAnimalEditMessage`.

## Связанные тесты

- `test/pages/unsent_animal_edit_bloc_test.dart`, group `'UC-47 — UnsentAnimalEditEventSave'`, test `'ошибка сохранения -> UnsentAnimalEditMessage(
  "an_error_data"), без Exit'` — прямое покрытие «Основного потока»: мок
  `animalsRepository.update(any())` настроен `thenThrow(Exception('db
  error'))`, блок доводится до `UnsentAnimalEditSuccess` с заполненным
  `localAnimal` (`bloc.stream.firstWhere(...)` после `UnsentAnimalStart`),
  затем добавляется `UnsentAnimalEditEventSave()`; тест ждёт состояние
  `UnsentAnimalEditMessage('an_error_data')`, дополнительно проверяет через
  `pumpEventQueue()` + накопленный список состояний, что это сообщение
  реально было в потоке, и что итоговое `bloc.state` — `UnsentAnimalEditSuccess`
  (не `Failure`, не что-то иное).
- **TBD — теста нет** на точки отказа из «Альтернативных потоков»:
  `AnimalIdentificationsRepository.deleteAll`/`insertAll`, бросающие
  исключение при успешном `AnimalsRepository.update` — в
  `unsent_animal_edit_bloc_test.dart` эти моки настраиваются только на успех
  (`thenAnswer((_) async {})`) в группе `'UC-46 — UnsentAnimalEditEventSave'`, отдельного теста с исключением именно на этих
  двух вызовах нет.
- **TBD — теста нет** на случай, когда `AnimalsRepository.update` не бросает
  исключение, а лишь возвращает `false` (drift `replace` не нашёл строку по
  первичному ключу) — см. «Открытые вопросы»; ни один существующий тест не
  стабит `animalsRepository.update` на `thenAnswer((_) async => false)`.

## Открытые вопросы и ограничения

- **Булев результат `AnimalsRepository.update` не проверяется.**
  `UnsentAnimalEditBloc` вызывает `await _animalsRepository.update(animal);`
  как отдельный оператор, не сохраняя и не проверяя возвращаемое значение.
  По документированной семантике drift (`UpdateStatement.replace`,
  `package:drift` — «Returns true if a row was affected by this operation»)
  `replace` **не бросает исключение**, если по первичному ключу не нашлось
  строки для замены, — он просто возвращает `false`. Если такое произойдёт
  (например, животное было удалено параллельно, пока форма была открыта),
  этот обработчик пойдёт **не** в описанную здесь `UPDATE_ERROR`-ветку, а
  продолжит выполнение как при успехе — попытается `deleteAll`/`insertAll`
  идентификации несуществующего уже `animalId`, и в итоге эмитит
  `animal_successfully_saved` + `Exit`, будто сохранение прошло. Это уже
  зафиксированная в `TESTING_CHECKLIST.md` (раздел 9.2) неточность — «ветка
  для локального животного не проверяет булев результат `update()`» — здесь
  она переописана применительно именно к ERROR-исходу: тихий `false` не
  порождает ERROR вовсе, только настоящее исключение попадает в этот
  use-case. Не устраняется в рамках этого документирующего прохода (TARGET
  == CURRENT).
- **Три DB-вызова не обёрнуты в одну транзакцию.** `update` (Animal),
  `deleteAll` (старые идентификации), `insertAll` (новые идентификации)
  выполняются последовательно, каждый — отдельный вызов репозитория. Если
  `update` успешен, но `deleteAll` бросает исключение — животное в БД уже
  обновлено новыми полями формы, а старые идентификации остаются нетронутыми
  (новые не вставлены, т.к. до `insertAll` выполнение не дошло) — итоговое
  состояние [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md) не
  соответствует ни старому, ни новому вводу пользователя.
  Если `update`+`deleteAll` успешны, но `insertAll` бросает — животное
  теряет вообще все идентификации (старые удалены, новые не вставлены). Оба
  случая маршрутизируются в тот же самый `UnsentAnimalEditMessage(
  'an_error_data')`, неотличимый от случая, где вообще ничего не записалось
  (`update` бросает первым) — пользователь не может по тексту ошибки понять,
  осталось ли животное в консистентном состоянии. Не покрыто тестом (см.
  «Связанные тесты»).
- **`Talker.error(e)` вызывается без стек-трейса.** Сигнатура `Talker.error`
  принимает необязательный второй параметр со стек-трейсом (используется,
  например, в `AnimalsRepository.sendIdentificationToApi` —
  `getIt<Talker>().error('...: $e, stackTrace: $stackTrace')`); в этом
  обработчике передаётся только `e` — при разборе прод-логов место фактического
  падения внутри `try` (какой из трёх DB-вызовов) не восстановить только по
  залогированному исключению.
- **Снэкбар идёт в обход `lib/widgets/app_snackbar.dart`.** UI-конвенция
  проекта (`.claude/rules/ui-architecture.md`) предписывает
  `showAppSnackBarError`/`showAppSnackBarInfo`/`showAppSnackBarSuccess` вместо
  ad-hoc `ScaffoldMessenger`/`SnackBar`; `UnsentAnimalEditPage.build` вызывает
  `rootScaffoldMessengerKey.currentState?.showSnackBar(SnackBar(...))`
  напрямую и для этой ошибки, и для успеха (`animal_successfully_saved`) —
  расхождение с текущей конвенцией, зафиксированное здесь как факт CURRENT,
  не исправляемое в рамках этого документирующего прохода.
- **Сообщение общее для всего приложения, не для этого экрана.** Ключ
  `'an_error_data'` переиспользуется как минимум в шести других
  bloc/cubit-обработчиках (`data_update_bloc.dart`, `animal_edit_bloc.dart`,
  `scanning_bloc.dart`, `animal_disposal_bloc.dart`, `vaccination_bloc.dart`,
  `animal_movement_bloc.dart`) — по тексту снэкбара пользователь не может
  понять, что именно не сохранилось.
