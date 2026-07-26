# UC-68 — Удаление неотправленной вакцинации отказывает: `VaccinationsRepository.deleteById` бросает исключение, `UnsentVaccinationCubit` эмитит `UnsentVaccinationError`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md)
(`vaccination.deleted_unsent`): пользователь удаляет одну ещё не отправленную
запись вакцинации либо несколько выбранных разом с экрана хаба
неотправленных, и `VaccinationsRepository.deleteById` бросает исключение.
`UnsentVaccinationCubit.delete`/`deleteSelected` перехватывают исключение и
эмитят `UnsentVaccinationError(message: e.toString(), ...)` — в отличие от
симметричного сценария у Movement/Disposal, здесь ошибка **видна
пользователю**: страница переключается на отдельный экран с сообщением. Для
`deleteSelected` при партии из нескольких id сбой на не-первом элементе
означает частичное удаление: элементы до сбойного уже удалены из БД и не
откатываются, сбойный элемент прерывает цикл, элементы после него не
обрабатываются вовсе.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — действие доступно и гостю, и
авторизованному пользователю одинаково: хаб неотправленных вакцинаций не
проверяет статус авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage` →
   `lib/pages/in_work/in_work_page.dart`) и нажимает плитку вакцинации
   (`EventTileData(... onTap: () => context.pushNamed2(Routes.unsentVaccination))`).
2. Маршрут `Routes.unsentVaccination` (`lib/pages/routes.dart`) открывает
   `UnsentVaccinationPage`
   (`lib/pages/unsent_vaccination/unsent_vaccination_page.dart`), которая в
   `build` создаёт `BlocProvider(create: (context) =>
   UnsentVaccinationCubit()..load())` — кубит создаётся и загружается ровно
   один раз, при первом построении провайдера.
3. `UnsentVaccinationCubit.load()`
   (`lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart`) читает
   `_vaccinationsRepository.getNotSyncVaccinationsWithDetails()` и эмитит
   `UnsentVaccinationLoaded(vaccinations: ..., selectedVaccinations: [])`.
4. Пользователь либо нажимает иконку удаления на карточке одной записи
   (`_VaccinationCard.onDelete` → `_showDeleteDialog(context, v)`), либо, если
   список не пуст, иконку «удалить отмеченные» в шапке
   (`IconButton(icon: Icons.delete_sweep_outlined, onPressed: () =>
   _showDeleteDialog(context, null))`) после того как выбрал записи чекбоксами
   (`UnsentVaccinationCubit.select`).
5. `_showDeleteDialog` показывает `AlertDialog` с кнопками «отмена»/«удалить»;
   при нажатии «удалить» вызывается, в зависимости от того, передана ли
   конкретная запись:
   - `vaccination == null` → `context.read<UnsentVaccinationCubit>().deleteSelected()`
     (партия по `state.selectedVaccinations`);
   - иначе → `context.read<UnsentVaccinationCubit>().delete(vaccination.id)`
     (одна запись).

   В обоих случаях сразу следующей строкой без `await` вызывается
   `Navigator.of(dialogContext).pop()` — диалог закрывается немедленно,
   не дожидаясь результата вызова кубита.
6. `UnsentVaccinationCubit.delete(vaccinationId)`:
   ```dart
   Future<void> delete(int vaccinationId) async {
     try {
       await _vaccinationsRepository.deleteById(vaccinationId);
       load();
     } catch (e) {
       emit(
         UnsentVaccinationError(
           message: e.toString(),
           selectedVaccinations: state.selectedVaccinations,
         ),
       );
     }
   }
   ```
7. `VaccinationsRepository.deleteById`
   (`lib/repositories/vaccination/vaccinations_repository.dart`) — `await
   dao.deleteById(vaccinationId)` → `VaccinationsDao.deleteById`
   (`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`):
   `(delete(vaccinations)..where((tbl) =>
   tbl.id.equals(vaccinationId))).go()` — обычный Drift DELETE без
   собственного `try/catch`.
8. В этом сценарии вызов `deleteById` бросает исключение (ошибка
   Drift/SQLite в реальном коде, `Exception('db error')` из мока в тесте).
   Исключение перехватывается `catch (e)` в `delete` — строка `load()`,
   идущая следом за `await deleteById(...)` в блоке `try`, не выполняется
   вовсе.
9. `catch (e)` строит `UnsentVaccinationError(message: e.toString(),
   selectedVaccinations: state.selectedVaccinations)` и эмитит его —
   `e.toString()` это полный текст исключения (например `'Exception: db
   error'` для `Exception('db error')`), `selectedVaccinations` — тот же
   список id, что был выбран **до** вызова `delete`/`deleteSelected`, без
   изменений.
10. Исключение не пробрасывается (`rethrow` отсутствует) — `delete`
    возвращает нормально завершившийся `Future<void>` в любом случае, успех
    это или ошибка.
11. `UnsentVaccinationPage`'s `BlocBuilder<UnsentVaccinationCubit,
    UnsentVaccinationState>` реагирует на новое состояние веткой `else if
    (state is UnsentVaccinationError)`: рендерит
    `BottomSheetPageWrapper(child: Center(child:
    ProgressMessage.somethingWentWrong(message: state.message)))` — вместо
    списка вакцинаций показывается полноэкранное сообщение (картинка + текст
    исключения), без кнопки повтора и без снэкбара
    (`lib/widgets/progress_bar/progress_message.dart`,
    `ProgressMessage.somethingWentWrong` — только `image` и `Text(message)`,
    никакого действия).

### Альтернативные потоки

- **Партия (`deleteSelected`) — сбой не на первом элементе.**
  ```dart
  Future<void> deleteSelected() async {
    try {
      for (var id in state.selectedVaccinations) {
        await _vaccinationsRepository.deleteById(id);
      }
      load();
    } catch (e) {
      emit(
        UnsentVaccinationError(
          message: e.toString(),
          selectedVaccinations: state.selectedVaccinations,
        ),
      );
    }
  }
  ```
  Один `try/catch` оборачивает **весь** цикл `for`, не отдельную итерацию.
  Если, например, выбраны id `[1, 2, 3]` и `deleteById(2)` бросает
  исключение: `deleteById(1)` к этому моменту уже успешно выполнился
  (запись `1` реально удалена из БД, откат отсутствует — ни `deleteSelected`,
  ни `VaccinationsRepository.deleteById`/`VaccinationsDao.deleteById` не
  оборачивают цикл в Drift-транзакцию), исключение на `id == 2` прерывает
  `for` немедленно — `deleteById(3)` не вызывается вовсе (`verifyNever`).
  Итог: запись `1` удалена, запись `2` не удалена (сбой), запись `3` не
  удалена (не дошли), и всё это скрыто за одним и тем же
  `UnsentVaccinationError`, не различающим три эти исхода.
- **`state.selectedVaccinations` в ошибочном состоянии не меняется.**
  `UnsentVaccinationError` получает `selectedVaccinations:
  state.selectedVaccinations` — тот же список id, что был выбран до вызова,
  включая id уже удалённых записей (в примере выше — `1`) и id, до которых
  цикл не дошёл (`3`). Поскольку `UnsentVaccinationPage` в состоянии
  `UnsentVaccinationError` не рендерит список вообще (см. основной поток,
  шаг 11), это расхождение сейчас ничем не наблюдаемо в UI — но обновление
  затронутых записей `selectedVaccinations` для соответствия реальному
  состоянию БД не делается.
- **Диалог подтверждения закрывается до получения результата.**
  Поскольку `_showDeleteDialog` вызывает `Navigator.of(dialogContext).pop()`
  сразу после запуска `delete`/`deleteSelected`, не дожидаясь `Future`,
  пользователь не видит индикатор ожидания между нажатием «удалить» и
  моментом, когда страница переключается в состояние ошибки — переход
  происходит асинхронно и незаметно для диалога, который к этому моменту уже
  закрыт.
- **Единственный способ увидеть список снова после ошибки — покинуть и
  заново открыть экран.** Ни `delete`, ни `deleteSelected` не вызывают
  `load()` на ошибочном пути. `BlocProvider` в `UnsentVaccinationPage`
  создаёт `UnsentVaccinationCubit` и вызывает `load()` только один раз, при
  первом построении провайдера — повторный вход в `Routes.unsentVaccination`
  создаёт новый экземпляр кубита с чистым состоянием и заново запускает
  `load()`.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сегмент `ENT` имени файла и единственная сущность, которую фактически
  затрагивает эта операция: `VaccinationsDao.deleteById` — точечный DELETE по
  `id`, ничего больше не читает и не пишет. [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)
  (Animal, на которое ссылается `Vaccination.animalId`) и связочная таблица
  `DiseasesVaccinations` (болезни, покрытые записью) в этом сценарии **не
  затрагиваются** ни при успехе, ни при ошибке — `deleteById` не выполняет
  никакого каскадного удаления и не читает животное.

### Бизнес-правила

- Один `try/catch` в `delete`/`deleteSelected` оборачивает весь вызов
  (соответственно один вызов `deleteById` или весь цикл `for`), а не
  отдельную попытку — для `deleteSelected` первое же исключение
  останавливает обработку всех оставшихся элементов партии.
- Уже выполненные до сбоя `deleteById`-вызовы внутри `deleteSelected` не
  откатываются — нет обёртывающей Drift-транзакции ни на одном из
  задействованных уровней (`UnsentVaccinationCubit`,
  `VaccinationsRepository`, `VaccinationsDao`).
- Перехваченное исключение конвертируется в `UnsentVaccinationError(message:
  e.toString(), ...)` и не пробрасывается дальше — `delete`/`deleteSelected`
  всегда возвращают нормально завершившийся `Future<void>`, отличить
  программно снаружи успех от ошибки можно только по итоговому состоянию
  кубита, не по исключению.
- `load()` (перечитывание списка неотправленных вакцинаций) вызывается
  только на успешном пути, сразу после `await deleteById(...)`, без `await`
  перед самим вызовом `load()` — на ошибочном пути `load()` не вызывается
  вовсе.
- В отличие от симметричного сценария Movement (`UnsentMovementsCubit.deleteGroup`,
  см. [UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md)),
  здесь ошибка **видна пользователю** — `UnsentVaccinationState` содержит
  явный вариант `UnsentVaccinationError`, и `UnsentVaccinationPage` подписана
  на него через `BlocBuilder`, переключая тело страницы на
  `ProgressMessage.somethingWentWrong(message: state.message)`.
- `UnsentVaccinationError` не содержит структурированной информации о том,
  какой конкретно id (при партии) вызвал исключение — только сырой текст
  исключения целиком, общий на весь вызов.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик полностью прослеживается чтением кода, включая
формирование сообщения об ошибке и факт, что партия прерывается на первом же
сбойном элементе без отката предыдущих. Незакрытые разрывы (отсутствие
виджет-теста страницы, отсутствие структурированного per-id отчёта об
ошибке) зафиксированы в «Связанные тесты» и «Открытые вопросы и
ограничения».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `EventTileData(... onTap: () => context.pushNamed2(Routes.unsentVaccination))` | CURRENT | точка входа на экран хаба неотправленных вакцинаций |
| `lib/pages/routes.dart` | `Routes.unsentVaccination` | CURRENT | регистрация маршрута → `UnsentVaccinationPage` |
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage.build`, `UnsentVaccinationPage._showDeleteDialog`, `_VaccinationCard.onDelete` | CURRENT | UI хаба, диалог подтверждения, ветка рендера `UnsentVaccinationError` |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.delete`, `UnsentVaccinationCubit.deleteSelected` | CURRENT | try/catch вокруг вызова(ов) `deleteById`, эмит `UnsentVaccinationError` без rethrow |
| `lib/pages/unsent_vaccination/unsent_vaccination_state.dart` | `UnsentVaccinationError`, `UnsentVaccinationLoaded` | CURRENT | freezed-less состояния кубита; `UnsentVaccinationError` без варианта retry |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.deleteById` | CURRENT | тонкая обёртка над `dao.deleteById`, без собственного `try/catch` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.deleteById` | CURRENT | точечный Drift DELETE по `id`, источник исключения в этом сценарии |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.somethingWentWrong` | CURRENT | полноэкранное сообщение об ошибке без действия «повторить» |

## Критерии приёмки

- При вызове `delete(id)`, если `VaccinationsRepository.deleteById` бросает
  исключение, `UnsentVaccinationCubit` эмитит `UnsentVaccinationError` с
  `message`, содержащим текст исключения (`e.toString()`).
- `delete(id)`/`deleteSelected()` никогда не пробрасывают исключение
  наружу — вызывающий код получает нормально завершённый `Future<void>`
  (`completes`), а не `throwsA(...)`, независимо от исхода.
- При партии из нескольких id (`deleteSelected`), если исключение бросается
  не на первом элементе — все id до сбойного успевают пройти через
  `deleteById` и остаются удалёнными в БД (без отката), сбойный элемент
  прерывает цикл, все id после него ни разу не передаются в `deleteById`.
- `load()` не вызывается ни в `delete`, ни в `deleteSelected` на ошибочном
  пути — список, отображавшийся до вызова, этим путём не обновляется.
- `UnsentVaccinationPage` в состоянии `UnsentVaccinationError` показывает
  `ProgressMessage.somethingWentWrong(message: state.message)` вместо
  списка, без кнопки/действия повтора.

## Связанные тесты

`test/pages/unsent_vaccination_cubit_test.dart`, group `'UC-68 —
UnsentVaccinationCubit.delete/deleteSelected ERROR'`:

- test `'delete -> deleteById бросает -> UnsentVaccinationError с
  сообщением'`: мок `vaccinationsRepository.deleteById(5)` бросает
  `Exception('db error')`; после `await cubit.delete(5)` состояние —
  `UnsentVaccinationError`, `(cubit.state as
  UnsentVaccinationError).message` содержит `'db error'`.
- test `'deleteSelected -> сбой в середине партии -> уже удалённые остаются
  удалёнными, UnsentVaccinationError'`: моки `deleteById(1)` и `deleteById(3)`
  успешны, `deleteById(2)` бросает `Exception('db error')`; выбраны id `1, 2,
  3`; после `await cubit.deleteSelected()` — `verify(deleteById(1)).called(1)`,
  `verify(deleteById(2)).called(1)`, `verifyNever(deleteById(3))`, состояние —
  `UnsentVaccinationError`.

**TBD — теста нет** на уровне виджета/страницы (`UnsentVaccinationPage`) —
вывод о том, что состояние `UnsentVaccinationError` рендерится через
`ProgressMessage.somethingWentWrong` без кнопки повтора, и что диалог
закрывается до получения результата, получен чтением кода страницы, не
отдельным виджет-тестом.

**TBD — теста нет** на партию из более чем трёх элементов или на сбой,
происходящий на **первом** элементе партии (`deleteSelected([id])`, где сам
единственный элемент бросает исключение) — существующий ERROR-тест партии
покрывает только сбой на среднем элементе списка из трёх.

## Открытые вопросы и ограничения

- **Единственный способ пользователя перезагрузить список после ошибки —
  покинуть экран и открыть его заново.** `UnsentVaccinationCubit` создаётся и
  вызывает `load()` только один раз, в `BlocProvider.create`
  (`UnsentVaccinationCubit()..load()`); ни `delete`, ни `deleteSelected` не
  вызывают `load()` на ошибочном пути, и в `UnsentVaccinationState` нет
  метода/события "повторить загрузку" из состояния ошибки.
- **`UnsentVaccinationError` не сообщает, какой именно id вызвал
  исключение** — ни при одиночном `delete`, ни при партии `deleteSelected`.
  При частичном отказе партии (см. «Альтернативные потоки») пользователь и
  разработчик, глядя только на UI/состояние кубита, не могут отличить,
  сколько записей реально удалено, а сколько — нет.
- **`selectedVaccinations`, перенесённый в состояние ошибки, не
  корректируется под фактический результат частичного удаления** — список
  выбранных id остаётся тем же, что был до вызова, включая id уже удалённых
  записей. Сейчас это ничем не наблюдаемо (список не рендерится в состоянии
  ошибки), но стало бы несоответствием при любом будущем изменении UI,
  показывающем список одновременно с ошибкой.
- **Нет Drift-транзакции вокруг цикла `deleteSelected`** — вопрос, нужно ли
  сделать групповое удаление атомарным (полный откат при частичном отказе)
  или, наоборот, явно сообщать пользователю «удалено N из M» вместо единого
  сообщения об ошибке, не решается в рамках этой документирующей задачи —
  предмет будущего TARGET-прохода.
