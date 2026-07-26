# UC-49 — Редактирование уже синхронизированного животного отказывает технически: `AnimalsRepository.update` возвращает `false` или бросает исключение, форма не покидается (ERROR)

## Назначение

Документирует ERROR-исход события [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)
(`animal.edited_deferred`) так, как он реализован в обработчике
`on<AnimalEditEventSave>` внутри `AnimalEditBloc`: попытка сохранить правку уже
синхронизированного животного (`id >= 0`) технически отказывает — локальный
Drift-вызов `AnimalsRepository.update` либо возвращает `false` (ни одна строка
не затронута), либо бросает исключение. Это происходит **до** какой-либо
попытки связаться с сервером — сама отправка правки на сервер в этом сценарии
всегда отложена до следующего sync-прохода (см. [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md))
и здесь не начинается вовсе. Оба технических исхода перехватываются одним и
тем же кодом и приводят к одному и тому же пользовательскому сообщению.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково), редактирующий уже заведённое
и синхронизированное животное. В отличие от смежного [UC-24](UC-24-ACTOR-1-EVT-11-ENT-9-UPDATE_ERROR-IN-FARM.md)
(FARM), обработчик этого сценария достижим из реального UI-пути: карточка
животного → пункт меню «Редактировать» → (при `animal.animal.id >= 0`) →
`Routes.animalEdit` → `AnimalEditBloc` (см. «Основной поток», шаг 1).

## CURRENT

### Основной поток

1. Пользователь открывает карточку уже синхронизированного животного
   (`animal.animal.id >= 0`) и нажимает «Редактировать» в `_MoreSheetItem`
   (`lib/pages/animal_card/animal_card_page.dart`) — т.к. `id >= 0`, переход
   идёт по ветке `context.pushNamed2(Routes.animalEdit, extra:
   animal.animalId)` (ветка `id < 0` уводит на другой экран и блок, см.
   «Альтернативные потоки»).
2. `AnimalEditPage` (`lib/pages/animal_edit/animal_edit_page.dart`) создаёт
   `AnimalEditBloc(animalId: animalId)..add(AnimalStart())` через
   `BlocProvider`.
3. Обработчик `AnimalStart` загружает животное —
   `_animalsRepository.getAnimalWithDetailsById(animalId)` (возвращает
   `AnimalWithDetails` с `animal.id >= 0`) — и справочники, затем эмитит
   `AnimalEditSuccess(_data, updateControllers: true)`, заполняя форму
   текущими значениями.
4. Пользователь меняет одно или несколько полей — вид/породу/масть/дату
   рождения/пол/кличку/поколение/родословную — через соответствующие
   `AnimalEditEventChangeXxx` события; каждое обновляет только in-memory
   `_data` (`AnimalEditData`) и эмитит `AnimalEditSuccess(_data)`, ничего не
   записывая в БД.
5. Пользователь нажимает кнопку «Сохранить» (`RElevatedButton`, `key:
   Key('b1')`); после `formKey.currentState?.validate() == true` диспетчится
   `AnimalEditEventSave()`.
6. Обработчик `on<AnimalEditEventSave>` эмитит `AnimalEditInProgress()`, затем
   внутри `try`: собирает `mother`/`father` из `_data.parents` (если
   заданы) и строит `updated = edit.copyWith(kindId: ..., breedId: ...,
   suitId: ..., birthDate: ..., gender: ..., name: ..., generation: ...,
   birthDateFrom: ..., birthDateTo: ..., motherId: ..., motherBirk: ...,
   motherName: ..., fatherId: ..., fatherBirk: ..., fatherName: ...)`, где
   `edit = _data.animal!.animal` — ранее загруженная синхронизированная
   запись; остальные поля (`id`, `regagroId`, `farmId`/`placeId`, `userId`,
   `guid`, `errors` и т.д.) переносятся как есть.
7. Поскольку `updated.id >= 0`, вызывается
   `_animalsRepository.update(updated.copyWith(needsUpdate: const
   Value(true)))`. `AnimalsRepository` не переопределяет `update`, поэтому
   реально исполняется унаследованный `BaseRepository.update`
   (`lib/repositories/base_repository.dart`) → `dao.upd(item)` →
   `BaseDao.upd` (`packages/sheep_farm_database/lib/entities/base_dao.dart`)
   → `updateCurrent().replace(item)` — обычный Drift `replace`.
8. **Технический отказ, ветка А.** `replace` завершается без исключения, но
   возвращает `false` (например, в таблице `Animals` больше нет строки с
   этим `id` — запись была удалена/выбыла до попытки сохранения): `ok ==
   false`, выполняется `else`-ветка, эмитится
   `AnimalEditMessage('an_error_data')`; `AnimalEditExit` не эмитится.
9. **Технический отказ, ветка Б.** Вызов бросает исключение (ошибка
   Drift/SQLite или любое другое исключение, всплывающее из DAO): оно
   перехватывается в `catch (e)`; в debug-сборке (`kDebugMode`)
   дополнительно пишется `log('Возникла ошибка при сохранении данных $e')`;
   безусловно вызывается `getIt<Talker>().error(e)`; затем эмитится тот же
   `AnimalEditMessage('an_error_data')`.
10. В обеих ветках, после `try/catch`, обработчик безусловно эмитит ещё раз
    `AnimalEditSuccess(_data)` — с тем же `_data`, что и до попытки
    сохранения (`updateControllers` по умолчанию `false`, поэтому текстовые
    контроллеры формы не перезаписываются, но и не сбрасываются — введённые
    пользователем значения остаются видны на экране).
11. В UI `BlocConsumer.listener` (`animal_edit_page.dart`) реагирует на
    `AnimalEditMessage`, показывая `SnackBar` с
    `AppLocalizations.of(context)!.tr('an_error_data')` — локализованный, но
    не различающий причину текст, один и тот же для обеих технических веток.
    Поскольку `AnimalEditExit` не эмитировался, `Navigator.of(context).pop()`
    не вызывается — пользователь остаётся на экране редактирования.
12. Повтора/backoff нет: пользователь может просто снова нажать «Сохранить»
    — форма не потеряла введённые значения (шаг 10).
13. Ни отредактированные поля животного, ни `needsUpdate` фактически не
    записываются в БД в этом сценарии — строка `Animals` остаётся такой же,
    какой была до попытки сохранения.

### Альтернативные потоки

- **OK-исход того же обработчика — не входит в этот сценарий.** Если `ok ==
  true`, эмитится `AnimalEditExit` + `AnimalEditMessage('animal_successfully_saved')`,
  и экран закрывается (`Navigator.of(context).pop()`) — это соседний, не
  документируемый здесь исход того же [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md).
- **Животное ещё не синхронизировано (`id < 0`) при вызове того же
  обработчика `AnimalEditEventSave`.** `updated.id >= 0` ложно, поэтому
  `needsUpdate: true` не выставляется вовсе — результат относится к другому
  событию, [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md)
  (правка ещё не синхронизированного животного), не к EVT-24.
  `AnimalEditBloc` технически не проверяет и не запрещает `id < 0` — эта
  ветка исполняется, если вызвать блок напрямую (см. «Связанные тесты»), но
  в реальном UI недостижима: `_MoreSheetItem` в `animal_card_page.dart`
  маршрутизирует `animal.animal.id < 0` на `Routes.unsentAnimalEdit` и
  отдельный `UnsentAnimalEditBloc`
  (`lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart`), у которого
  своя ERROR-ветка (`test/pages/unsent_animal_edit_bloc_test.dart`, группы
  `UC-63`/`UC-64`) — не описывается этим документом.
- Отсутствие интернета проверяется только в обработчике `AnimalStart`
  (`NetworkConnectivityService.hasConnection()`), не в
  `AnimalEditEventSave` — сам вызов `update` пишет исключительно локально (в
  Drift/SQLite) и не требует сети; технический отказ, документируемый
  здесь, никак не связан с сетевым доступом.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность, чьё
  состояние (в т.ч. `needsUpdate`) сценарий пытается изменить; это же
  ENT-сегмент имени файла. При техническом отказе строка фактически не
  меняется.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — читается только на шаге загрузки формы
  (`AnimalStart`) для отображения; сам обработчик `AnimalEditEventSave` её
  не читает и не пишет — изменения идентификаций, введённые через
  `AnimalEditEventChangeIdentification`, не включаются в объект, передаваемый
  в `update` (см. «Открытые вопросы»).

### Бизнес-правила

- `needsUpdate: true` добавляется в объект, передаваемый в `update`, только
  когда `updated.id >= 0`; сам факт передачи не гарантирует запись — при
  техническом отказе (обе ветки, шаги 8–9) реальное значение поля в БД не
  меняется.
- Оба технических исхода — `ok == false` и брошенное исключение —
  обрабатываются одинаково и приводят к идентичному пользовательскому
  сообщению `an_error_data`; код не различает и не сообщает пользователю
  причину отказа.
- Никакого отката и повтора: обработчик не восстанавливает и не меняет
  `_data` при ошибке — форма остаётся в том состоянии, в котором была на
  момент нажатия «Сохранить».
- Логирование исключения безусловно идёт через `getIt<Talker>().error(e)`;
  дополнительный вывод через `log(...)` — только при `kDebugMode == true`.
- Известный баг равенства состояний: `AnimalEditMessage.props => []` —
  любые два экземпляра `AnimalEditMessage` равны друг другу независимо от
  текста (`AnimalEditMessage('an_error_data') ==
  AnimalEditMessage('animal_successfully_saved')` истинно). Это ослабляет
  строгость любой проверки вида `state == AnimalEditMessage('an_error_data')`
  — по коду обработчика эмитируется ровно один инстанс именно с этим
  текстом, но сравнение через `==` само по себе этого не гарантирует (см.
  «Открытые вопросы»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обе технические ветки отказа, включая факт недостижимости
ветки `id < 0` из реального UI, полностью прослеживаются в существующем коде
и покрыты тестами на уровне блока.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_card/animal_card_page.dart` | `_MoreSheetItem` (действие `animal_actions_edit`) | CURRENT | реальная UI-точка входа: для `animal.animal.id >= 0` маршрутизирует на `Routes.animalEdit`, для `id < 0` — на `Routes.unsentAnimalEdit` (другой блок) |
| `lib/pages/routes.dart` | `Routes.animalEdit` | CURRENT | константа маршрута экрана редактирования уже синхронизированного животного |
| `lib/pages/animal_edit/animal_edit_page.dart` | `AnimalEditPage`, `BlocProvider<AnimalEditBloc>` | CURRENT | точка входа экрана; создаёт блок с `animalId`, диспетчит `AnimalStart` |
| `lib/pages/animal_edit/animal_edit_page.dart` | `BlocConsumer<AnimalEditBloc, AnimalEditState>.listener` | CURRENT | показывает `SnackBar` на `AnimalEditMessage` (через `AppLocalizations.tr`); вызывает `Navigator.of(context).pop()` только на `AnimalEditExit` |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc` (`on<AnimalEditEventSave>`) | CURRENT | строит `updated` Animal, вызывает `update`, ловит исключение, эмитит `AnimalEditMessage('an_error_data')` без `AnimalEditExit` в обеих технических ветках |
| `lib/pages/animal_edit/animal_edit_event.dart` | `AnimalEditEventSave` | CURRENT | событие сохранения, без полезной нагрузки |
| `lib/pages/animal_edit/animal_edit_state.dart` | `AnimalEditMessage`, `AnimalEditExit`, `AnimalEditSuccess` | CURRENT | состояния; `AnimalEditMessage.props => []` — экземпляры равны друг другу независимо от текста |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository` (`extends BaseRepository<AnimalsDao, Animal, $AnimalsTable>`) | CURRENT | не переопределяет `update` — используется унаследованная реализация |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` — точка, откуда всплывает `false`/исключение |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — Drift-вызов; `false`, если ни одна строка не затронута, либо исключение |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao` | CURRENT | конкретный DAO животного, наследующий `BaseDao.upd` без переопределения |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals`, `Animal` | CURRENT | таблица/модель; `needsUpdate` — поле, которое сценарий пытается взвести |
| `lib/pages/unsent_animal_edit/unsent_animal_edit_bloc.dart` | `UnsentAnimalEditBloc` | CURRENT | реальный код, исполняемый для `id < 0` вместо `AnimalEditBloc` (см. «Альтернативные потоки») — иной сценарий, не описываемый здесь |

## Критерии приёмки

- При отправке `AnimalEditEventSave` в `AnimalEditBloc` для животного с
  `animal.id >= 0`, если `AnimalsRepository.update` (через `BaseDao.upd` →
  Drift `replace`) возвращает `false` **или** бросает исключение, блок
  эмитит `AnimalEditMessage('an_error_data')` и не эмитит `AnimalEditExit`;
  сам вызов `add(...)` не приводит к необработанному исключению снаружи
  блока (`completes`, а не `throwsA(...)`).
- В обеих ветках объект, переданный в `update`, содержит `needsUpdate: true`
  — независимо от того, что вызов затем технически проваливается; в
  реальной БД поле фактически не меняется, т.к. запись/транзакция не
  проходит.
- После обработки ошибки (обе ветки) блок безусловно эмитит ещё раз
  `AnimalEditSuccess(_data)` с тем же `_data`, что и до попытки сохранения —
  форма не сбрасывается и не закрывается.
- В ветке исключения `getIt<Talker>().error(e)` вызывается безусловно; вывод
  через `log(...)` — только при `kDebugMode == true`.
- UI показывает `SnackBar` с локализованным текстом `an_error_data` через
  `BlocConsumer.listener`; экран не закрывается, т.к. `Navigator.of(context).pop()`
  вызывается только на `AnimalEditExit`.
- Факт, что ветка `id < 0` внутри этого же обработчика недостижима из
  реального UI (маршрутизация уводит на `UnsentAnimalEditBloc`) — часть
  текущего, подтверждённого чтением кода поведения; не критерий для
  исправления в рамках этого документирующего прохода (TARGET == CURRENT).

## Связанные тесты

- `test/pages/animal_edit_bloc_test.dart`, group `'UC-49 — AnimalEditEventSave'`
  (переименуется отдельным контролируемым проходом позже, не трогать
  сейчас):
  - test `'update() возвращает false -> AnimalEditMessage("an_error_data"),
    без Exit'` — прямое покрытие ветки А («Основной поток», шаг 8): мок
    `animalsRepository.update` отвечает `false`, тест ждёт
    `AnimalEditMessage('an_error_data')` и проверяет, что
    `states.whereType<AnimalEditExit>()` пуст.
  - test `'update() бросает исключение -> AnimalEditMessage("an_error_data"),
    без Exit'` — прямое покрытие ветки Б («Основной поток», шаг 9): мок
    `animalsRepository.update` бросает `Exception('db error')`, та же
    проверка.
  - test `'животное локальное (id<0) -> update() без needsUpdate:true'` —
    покрывает «Альтернативные потоки» (ветка `id < 0`), но это OK-, а не
    ERROR-исход (`update` отвечает `true`); приведён здесь как единственный
    тест, напрямую упражняющий недостижимую из UI ветку `id < 0` того же
    обработчика.
- Смежно, не то же самое: `test/pages/animal_edit_bloc_test.dart`, group
  `'AnimalEditMessage — БАГ равенства'` — покрывает найденный дефект
  `props => []`, влияющий на строгость проверок `state ==
  AnimalEditMessage('an_error_data')` выше.
- **TBD — теста нет** на реальный UI-эффект (`SnackBar`/отсутствие
  `Navigator.pop`) в `animal_edit_page.dart` — покрытие есть только на
  уровне блока, не на уровне виджета/страницы.

## Открытые вопросы и ограничения

- **Баг равенства `AnimalEditMessage.props => []`.** Любые два экземпляра
  `AnimalEditMessage` равны друг другу независимо от текста — сравнение
  `state == AnimalEditMessage('an_error_data')` в тестах (документируемых
  здесь) технически проверяет только факт «эмитировался хоть один
  `AnimalEditMessage`», а не то, что его текст именно `'an_error_data'`. По
  коду обработчика в этой ветке эмитируется ровно один `AnimalEditMessage`,
  и его текст действительно `'an_error_data'` — баг равенства не меняет
  фактическое поведение прода, только ослабляет строгость теста. Не
  исправляется в рамках этого документирующего прохода.
- **Идентификационные метки не сохраняются при Save.** Форма позволяет
  менять идентификации животного (`AnimalEditEventChangeIdentification`),
  но обработчик `AnimalEditEventSave` не включает их ни в `updated`, ни в
  отдельный вызов какого-либо `AnimalIdentificationsRepository` — правки
  идентификаций не персистятся ни при успехе, ни при ошибке сохранения.
  Затрагивает оба исхода одинаково, не специфично для ERROR-ветки; не
  разрешается в рамках этого прохода.
- **Различение причины отказа не делается нигде выше по стеку.** «Запись не
  найдена» (`ok == false`) и «техническая ошибка БД/платформы» (исключение)
  неотличимы для пользователя и для теста — оба приводят к одному и тому же
  `an_error_data`. Фиксируется как факт текущего кода, не как дефект для
  исправления.
- Ветка `id < 0` внутри `AnimalEditBloc.AnimalEditEventSave` (см.
  «Альтернативные потоки») в реальном UI недостижима — не разрешается,
  оставлять ли этот код как unused-ветку блока или добавлять явную защиту —
  вопрос будущего TARGET-прохода.
