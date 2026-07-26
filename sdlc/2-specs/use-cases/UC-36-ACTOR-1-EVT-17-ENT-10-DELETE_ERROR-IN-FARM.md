# UC-36 — Удаление отделения при сохранении структуры фермы отказывает технически: `FarmsAndPlacesBloc._onDeletePlace` ловит исключение и эмитит `FarmsPageError`, которую никто не читает (ошибка)

## Назначение

Документирует ERROR-исход события [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
(`place.deletion_requested`) так, как он реализован в
`FarmsAndPlacesBloc._onDeletePlace`: исключение из `PlaceRepository.update`
(ветка уже синхронизированного места) или `PlaceRepository.delete` (ветка
ещё не синхронизированного места) перехватывается общим `catch`, и блок
эмитит `FarmsPageError` с текстом на русском. В отличие от аналогичного
ERROR-сценария правки фермы ([UC-24](UC-24-ACTOR-1-EVT-11-ENT-9-UPDATE_ERROR-IN-FARM.md)),
где обработчик недостижим из UI вовсе, `_onDeletePlace` реально вызывается
из настоящего пользовательского действия — кнопки «Сохранить структуру» на
экране настройки структуры фермы. Тем не менее, как зафиксировано ниже,
итоговая ошибка всё равно невидима пользователю: экран уже закрывается
синхронно до завершения обработки события, и вдобавок ни один виджет в
`lib/` не подписан на состояния `FarmsAndPlacesBloc`.

Бизнес-правило «нельзя удалить место, на котором остались животные» —
описанное в эффекте [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
— живёт в отдельном, более раннем шаге (`PlaceCreateCubit.removePlace`) и не
входит в этот сценарий: этот use-case — только про технический сбой самого
удаления в БД, уже после того как проверка на животных пройдена.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь;
имя актора наследуется от id события [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
в имени файла. Гостевой доступ сюда тоже фактически достижим (регистрация
фермы/структуры не требует авторизации), но актор зафиксирован тем же
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), что и инициатор события в его собственном файле.

## CURRENT

### Основной поток

1. На экране фермы (`FarmWithDetails`) пользователь открывает меню фермы —
   `FarmMoreMenuButton`
   (`lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`)
   — и выбирает пункт `l10n.farm_structure`, что вызывает
   `context.pushNamed(Routes.createPlace, extra:
   PlaceCreatePageArguments(farmId: farm.farm.remoteId!, existingPlaces:
   farm.placesWithAnimals.map((p) => p.place).toList()))`.
2. `PlaceCreatePage`
   (`lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`)
   читает `PlaceCreatePageArguments` из `GoRouterState.of(context).extra` и
   оборачивает `_PlaceCreateView` в `BlocProvider<PlaceCreateCubit>(farmId:
   ..., existingPlaces: ..., defaultPlaceNames: [...])`.
3. Пользователь нажимает иконку удаления у конкретной строки места в списке
   (`_PlaceItemState.build`, `onTap: () =>
   cubit.removePlace(widget.index)`).
4. `PlaceCreateCubit.removePlace(index)`: сбрасывает `errorMessage`; если у
   удаляемого места `idRemote != null`, проверяет через
   `_animalsRepository.getAllAnimalsWithDetailsByFilters(placeIds:
   [placeToRemove.idRemote ?? placeToRemove.id!])`, есть ли на нём животные
   — если есть, эмитит `state.copyWith(errorMessage:
   'move_all_animals_to_delete')` и выходит, ничего не удаляя (это
   отдельный, не документируемый здесь REJECTED-путь того же события). Если
   животных нет (или проверка вовсе пропущена, так как `idRemote == null`),
   место убирается из `state.places` в памяти и добавляется в
   `state.deletedPlaces` — реального обращения к `PlaceRepository` на этом
   шаге ещё нет.
5. Пользователь нажимает «Сохранить структуру»
   (`l10n.save_structure`, `BlackCircleButton`) в `place_create_page.dart`.
6. Обработчик `onTap` синхронно, без `await` на исход обработки: для каждого
   места из `cubit.getPlacesToSave()` диспатчит
   `FarmsPageEventEditPlace`/`FarmsPageEventAddPlace` в
   `context.read<FarmsAndPlacesBloc>()`; для каждого места из
   `cubit.getPlacesToDelete()` (включая место, удалённое на шаге 4) —
   `context.read<FarmsAndPlacesBloc>().add(FarmsPageEventDeletePlace(place))`;
   сразу вслед за циклами, всё в том же синхронном обработчике —
   `context.pop()`. Экран настройки структуры закрывается независимо от
   того, как впоследствии обработается событие удаления.
7. `FarmsAndPlacesBloc` регистрирует
   `on<FarmsPageEventDeletePlace>(_onDeletePlace)` в конструкторе; событие
   обрабатывается асинхронно уже после того, как `context.pop()` (шаг 6)
   вернул пользователя на предыдущий экран.
8. `_onDeletePlace`:
   ```dart
   try {
     if (event.place.idRemote != null) {
       final deletedPlace = event.place.copyWith(isDeleted: true);
       await _placeRepository.update(deletedPlace);
     } else {
       await _placeRepository.delete(event.place);
     }
     add(FarmsPageEventLoadFarms());
   } catch (e) {
     emit(FarmsPageError('Ошибка удаления места: ${e.toString()}'));
   }
   ```
9. В этом сценарии (ветка `idRemote != null`, соответствует единственному
   существующему тесту) `_placeRepository.update(deletedPlace)` бросает
   исключение — `PlaceRepository extends BaseRepository<PlacesDao, Place,
   $PlacesTable>`, `update` — унаследованный `Future<bool>
   update(Insertable<D> item) => dao.upd(item)`
   (`lib/repositories/base_repository.dart`), который вызывает
   `BaseDao.upd(item) => updateCurrent().replace(item)`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — обычный
   Drift `replace`, способный бросить исключение (ошибка Drift/SQLite или
   иное).
10. `catch (e)` ловит исключение и эмитит `FarmsPageError('Ошибка удаления
    места: ${e.toString()}')` — текст жёстко закодирован на русском (рядом
    комментарий `// todo tranlsate`), не идёт через `AppLocalizations`, и
    включает сырой `e.toString()` без фильтрации.
11. В этой ветке `add(FarmsPageEventLoadFarms())` не вызывается — список
    ферм/мест/животных не перезагружается.
12. Так как экран `PlaceCreatePage` уже закрыт синхронно на шаге 6, состояние
    `PlaceCreateCubit` (в т.ч. `state.deletedPlaces`, куда попало это место)
    к моменту эмиссии `FarmsPageError` уже не существует — у пользователя
    структурно нет возможности увидеть эту ошибку или повторить попытку
    удаления именно этого места из того же места UI.
13. **Ни один виджет в `lib/` не подписан на состояния `FarmsAndPlacesBloc`.**
    Проверено чтением всего `lib/`: нет ни одного `BlocBuilder<
    FarmsAndPlacesBloc, ...>`, `BlocConsumer<FarmsAndPlacesBloc, ...>` или
    `BlocListener<FarmsAndPlacesBloc, ...>` — единственные обращения к
    блоку за пределами его собственных файлов (`farms_page_bloc.dart`) — три
    вызова `context.read<FarmsAndPlacesBloc>().add(...)` в
    `place_create_page.dart` (шаг 6) и создание единственного экземпляра в
    `lib/main.dart`. Даже независимо от «гонки» с `context.pop()` (шаг 6/12),
    `FarmsPageError`, эмитированная на шаге 10, не показывается ни одному
    реальному пользователю ни при каких обстоятельствах.

### Альтернативные потоки

- **Ветка `idRemote == null` (место ещё не синхронизировано) с той же
  ошибкой.** Если удаляемое место ещё не имело `idRemote`,
  `_onDeletePlace` вызывает `await _placeRepository.delete(event.place)` —
  `BaseRepository.delete` → `dao.del(item)` →
  `BaseDao.del(item) => deleteCurrent().delete(item)`
  (`packages/sheep_farm_database/lib/entities/base_dao.dart`). Если этот
  вызов бросает исключение, обработка симметрична основному потоку (тот же
  общий `catch`, тот же текст ошибки), но у существующего теста
  («Связанные тесты») эта ветка не смоделирована — покрыт только
  `update`-путь.
- **OK-исход того же обработчика — не входит в этот сценарий.** Если
  `update`/`delete` завершается успешно, `_onDeletePlace` вызывает
  `add(FarmsPageEventLoadFarms())`, что в итоге эмитит
  `FarmsPageLoadedWithAnimals` — соседний исход того же
  [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md), не
  документируемый здесь.
- **REJECTED-путь того же события — тоже не входит в этот сценарий.** Если
  на удаляемом синхронизированном месте остались животные,
  `PlaceCreateCubit.removePlace` (шаг 4 основного потока) отклоняет
  удаление бизнес-правилом (`errorMessage: 'move_all_animals_to_delete'`)
  ещё до того, как `FarmsPageEventDeletePlace` вообще диспатчится —
  `FarmsAndPlacesBloc._onDeletePlace` в этой ветке не участвует. Это
  отдельный, ещё не специфицированный use-case c исходом
  `DELETE_REJECTED`, а не данный документ.
- Поиск по всему `lib/` за пределами `farms_page_bloc.dart`/
  `farms_page_event.dart` не находит других мест диспатча
  `FarmsPageEventDeletePlace`, кроме `place_create_page.dart` (шаг 6) —
  «либо с экрана фермы» из описания триггера [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  как отдельного, независимого входа не находит соответствия в текущем
  коде (см. «Открытые вопросы»).

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — сущность, чьё
  состояние пытается поменять сценарий (`isDeleted` либо физическое
  удаление строки); это же ENT-сегмент имени файла.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не
  пишется в этом сценарии; упомянута лишь потому, что `farmId`
  (`Place.farmId` → `Farm.remoteId`) задаёт контекст, в котором
  открывается `PlaceCreatePage` (шаг 1), и потому что `FarmsAndPlacesBloc`
  хранит `FarmRepository` как общую зависимость (используется другими
  обработчиками того же блока, не `_onDeletePlace`).

### Бизнес-правила

- Ветвление по `event.place.idRemote`: для уже синхронизированного места
  (`idRemote != null`) — мягкое удаление (`isDeleted: true` через
  `update`); для ещё не синхронизированного — прямое физическое удаление
  строки (`delete`). Оба вызова обёрнуты одним и тем же `catch`, дающим
  одинаковый текст ошибки независимо от того, какая из двух веток бросила
  исключение.
- Текст ошибки не локализован — жёстко закодированная русская строка
  `'Ошибка удаления места: ${e.toString()}'`, включающая сырой
  `e.toString()` без какой-либо фильтрации.
- Обработчик не делает retry и не восстанавливает состояние
  `PlaceCreateCubit` (которое к моменту ошибки уже уничтожено вместе с
  закрытым экраном, см. шаг 12) — при ошибке `update`/`delete` место
  просто остаётся в БД в прежнем виде, но пользователь уже находится на
  другом экране и не получает об этом никакого сигнала.
- Как зафиксировано в «Основном потоке» (шаг 13), выход `FarmsPageError` из
  этого обработчика ни на что не влияет за пределами потока состояний
  блока — ни снэкбар, ни иной UI-эффект в текущем коде не завязаны на это
  состояние.
- Проверка «на месте не осталось животных» (эффект, описанный в
  [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)) — не
  часть `_onDeletePlace`; она уже выполнена раньше, в
  `PlaceCreateCubit.removePlace` (шаг 4), и к моменту вызова
  `_onDeletePlace` больше не повторяется.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик, включая факт его достижимости из реального UI и
одновременную невидимость итоговой ошибки, полностью прослеживается в
существующем коде. Ветка `idRemote == null` (`delete()` бросает исключение)
— симметричный, но отдельно не воспроизведённый тестом вариант того же
`catch`; см. «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` (действие `l10n.farm_structure`) | CURRENT | точка входа в UI: переход на `Routes.createPlace` с текущими местами фермы |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `PlaceCreatePage`, `_PlaceCreateView`, `_PlaceItemState` (кнопка `l10n.save_structure`, удаление строки места) | CURRENT | собирает `placesToSave`/`placesToDelete` из кубита, диспатчит события в `FarmsAndPlacesBloc`, затем синхронно вызывает `context.pop()`, не дожидаясь обработки |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.removePlace` | CURRENT | помечает место к удалению в памяти (`state.deletedPlaces`), включая проверку «нет животных» — отдельный, REJECTED-путь того же события, не документируемый здесь |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onDeletePlace` | CURRENT | ветвление по `idRemote`, try/catch вокруг `update`/`delete`, эмитит `FarmsPageError` при исключении |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventDeletePlace` | CURRENT | событие, несущее `place` |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageError` | CURRENT | состояние-ошибка (`message`); ни один виджет в `lib/` на него не подписан |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageLoadedWithAnimals` | CURRENT | состояние, которое в этой ветке не эмитится (`add(LoadFarms)` пропущен) |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository` (`extends BaseRepository<PlacesDao, Place, $PlacesTable>`) | CURRENT | предоставляет `update`/`delete`, используемые обработчиком |
| `lib/repositories/base_repository.dart` | `BaseRepository.update`, `BaseRepository.delete` | CURRENT | `dao.upd(item)` / `dao.del(item)` — точки, откуда всплывает перехватываемое исключение |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd`, `BaseDao.del` | CURRENT | `updateCurrent().replace(item)` / `deleteCurrent().delete(item)` — реальные Drift-вызовы, способные бросить исключение |
| `lib/main.dart` | `MultiBlocProvider` → `BlocProvider<FarmsAndPlacesBloc>` | CURRENT | создаёт единственный экземпляр блока на всё приложение из трёх репозиториев `getIt` |

## Критерии приёмки

- При добавлении `FarmsPageEventDeletePlace(place)` с `place.idRemote !=
  null`, если `PlaceRepository.update` (через `BaseDao.upd`) бросает
  исключение, блок эмитит ровно одно состояние `FarmsPageError`, чьё
  `message` равно `'Ошибка удаления места: ' + e.toString()`; сам вызов
  `add(...)` не приводит к необработанному исключению снаружи блока
  (`completes`, а не `throwsA(...)`).
- Симметрично, при `place.idRemote == null` и `PlaceRepository.delete`
  (через `BaseDao.del`), бросающем исключение, — тот же паттерн
  `FarmsPageError('Ошибка удаления места: ...')` (пока не покрыто отдельным
  тестом, см. «Связанные тесты»).
- В обеих ветках `FarmsPageEventLoadFarms` не добавляется — список
  ферм/мест/животных не перезагружается после ошибки удаления.
- Экран `PlaceCreatePage`, из которого было инициировано удаление, уже
  закрыт (`context.pop()`) к моменту эмиссии `FarmsPageError` — независимо
  от исхода обработки события, навигация не ждёт его результата.
- Факт, что ни один экран не подписан на состояния `FarmsAndPlacesBloc` —
  часть текущего, подтверждённого чтением кода поведения; это не критерий
  для исправления в рамках этого документирующего прохода (TARGET ==
  CURRENT).

## Связанные тесты

- `test/pages/farms_and_places_bloc_test.dart`, group `'UC-12 —
  FarmsAndPlacesBloc._onDeletePlace ERROR'` (будет переименовано, не
  трогать сейчас), test `'update бросает -> FarmsPageError("Ошибка
  удаления места: ...")'` — прямое покрытие «Основного потока» (ветка
  `idRemote != null`): мок `placeRepository.update` бросает
  `Exception('db error')`, блок собирается через `buildLoadedBloc()` (уже в
  состоянии `FarmsPageLoadedWithAnimals`), затем добавляется
  `FarmsPageEventDeletePlace(_place(id: 1, idRemote: 1))`, и тест ждёт
  `FarmsPageError` с сообщением, содержащим `'Ошибка удаления места'`.
- **TBD — теста нет** на ветку `idRemote == null` («Альтернативные потоки»,
  `PlaceRepository.delete`, бросающий исключение) — в том же файле есть
  соседний OK-тест для этой ветки (group `'UC-11 —
  FarmsAndPlacesBloc._onDeletePlace'`, test `'idRemote == null -> прямое
  delete()'`), но его ERROR-аналог отсутствует.
- **TBD — теста нет** на UI-уровне: сценарий «пользователь удаляет место в
  `PlaceCreatePage`, нажимает "Сохранить структуру", `update`/`delete`
  падает» — не покрыт ни виджет-тестом, ни тестом `PlaceCreateCubit`; весь
  существующий тест — только блок-уровневый (`FarmsAndPlacesBloc` напрямую,
  без прохождения через `PlaceCreateCubit`/`place_create_page.dart`).

## Открытые вопросы и ограничения

- **Обработчик достижим из реального UI, но результат всё равно невидим —
  по двум независимым причинам одновременно.** В отличие от
  [UC-24](UC-24-ACTOR-1-EVT-11-ENT-9-UPDATE_ERROR-IN-FARM.md) (где
  `FarmsAndPlacesBloc._onEditFarm` вообще не диспатчится ни из какого
  экрана), `_onDeletePlace` реально вызывается из «Сохранить структуру» в
  `place_create_page.dart`. Тем не менее итоговая `FarmsPageError`
  структурно не может дойти до пользователя: (1) `context.pop()` в том же
  синхронном обработчике `onTap` выполняется сразу после диспатча событий,
  не дожидаясь их асинхронной обработки, и (2) ни один виджет в `lib/` не
  подписан на состояния `FarmsAndPlacesBloc` вовсе (тот же архитектурный
  пробел, что уже зафиксирован в [UC-24](UC-24-ACTOR-1-EVT-11-ENT-9-UPDATE_ERROR-IN-FARM.md)
  для других обработчиков того же блока). Фикс любой из этих двух причин
  (или обеих) — вопрос будущего TARGET-прохода, не решается в рамках этой
  документирующей задачи.
- **Расхождение пути файла в замороженных [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  и [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) — не исправляется в
  рамках этого прохода.** Оба файла цитируют
  `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart`,
  однако при чтении дерева реальный путь —
  `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart`
  (папка `farms_create` переименована в `places` уже после того, как эти
  спеки были написаны). [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  и [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) — уже существующие,
  замороженные артефакты; расхождение фиксируется здесь, а не правится в
  них.
- **Расхождение описания триггера в [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  — не исправляется в рамках этого прохода.** Файл события описывает
  триггер как «из мастера настройки структуры... либо с экрана фермы» —
  однако поиск по всему `lib/` находит только один диспатч
  `FarmsPageEventDeletePlace`: из мастера настройки структуры
  (`place_create_page.dart`). Отдельного действия «удалить место» прямо с
  экрана фермы (`FarmWithDetails`/`place_actions_widget.dart`) в текущем
  коде не найдено.
- Нужно ли когда-либо покрыть тестом ветку `idRemote == null` с
  исключением, писать ли отдельный use-case для REJECTED-исхода
  `PlaceCreateCubit.removePlace` (проверка животных), и стоит ли когда-либо
  дожидаться результата удаления перед `context.pop()` — вопросы будущего
  прохода, не разрешаются в рамках этой чисто документирующей задачи.
