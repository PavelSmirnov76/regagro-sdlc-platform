# UC-79 — Пользователь открывает хаб ещё не отправленных вакцинаций

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает отдельный экран-хаб, показывающий все локально
созданные, ещё ни разу не отправленные на сервер записи вакцинации —
обычно как один из пунктов сводного экрана «В работе», но фактически
достижимый с любого экрана через именованный маршрут. Экран — основа для
последующей правки ([EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md))
или удаления ([EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md))
конкретной ещё не отправленной записи.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
независимо от статуса авторизации (гость и авторизованный — одинаково).

## CURRENT

### Основной поток

1. Пользователь открывает экран «В работе» (`InWorkPage`) и нажимает плитку
   «Вакцинация» (`EventTileData` с `icon: Assets.eventVaccination`) —
   `onTap: () => context.pushNamed2(Routes.unsentVaccination)`. Плитка
   нажимаема независимо от количества записей: числовой бейдж на ней
   показывается только если `totalVacc > 0`
   (`totalVacc = vaccinationsCount + editableVaccinationsCount +
   deletableVaccinationsCount`, из `InWorkBloc`/`InWorkSuccess.data`), но сам
   `onTap` не гейтится этим условием — переход возможен и при бейдже `0`
   /отсутствии бейджа.
2. `Routes.unsentVaccination` — маршрут верхнего уровня (не
   `parentNavigatorKey: rootNavigatorKey`), с вложенным дочерним маршрутом
   `Routes.unsentVaccinationEdit` для последующей правки одной записи.
   `builder` создаёт `const UnsentVaccinationPage()`.
3. `UnsentVaccinationPage.build` оборачивает экран в
   `BlocProvider(create: (context) => UnsentVaccinationCubit()..load())` —
   `load()` вызывается ровно один раз, сразу при создании cubit'а, без
   отдельного триггера (pull-to-refresh или кнопки обновления на экране
   нет).
4. `UnsentVaccinationCubit()` уже стартует в состоянии
   `UnsentVaccinationLoading()` (аргумент конструктора `super`); `load()`
   немедленно эмитит ещё один `UnsentVaccinationLoading()` — избыточный, но
   безвредный повторный emit того же по смыслу состояния (класс не
   `Equatable`, `BlocBuilder` в любом случае просто перерисовывает тот же
   loader).
5. `load()` вызывает `_vaccinationsRepository.getNotSyncVaccinationsWithDetails()`
   (`VaccinationsRepository.getNotSyncVaccinationsWithDetails` →
   `VaccinationsDao.getNotSyncVaccinationsWithDetails`), оборачивая вызов в
   `try/catch`.
6. DAO строит join `vaccinations` (алиас) с `vaccines`, `units`,
   `injectionMethods`, `injectionPlaces`, `vaccinationTypes`
   (`leftOuterJoin` по каждому), с условиями `..where(sync.isValue(false))`,
   `..where(deletedAt.isNull())`, `..where(updatedAt.isNull())`,
   `..orderBy([OrderingTerm.desc(vaccinationDate)])`,
   `..groupBy([id])`. Явного условия `createdAt.isNotNull()` в этом запросе
   **нет** — по инварианту [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)
   («ровно один из трёх nullable-флагов может быть установлен
   одновременно») комбинация `sync=false ∧ deletedAt IS NULL ∧ updatedAt IS
   NULL` эквивалентна на практике «`createdAt != null`», но это следствие
   инварианта, а не явный предикат этого конкретного запроса (в отличие от
   `watchCountNotSync`, см. «Бизнес-правила»).
7. Для каждой строки результата DAO дополнительно запрашивает
   `AnimalWithDetails` (`AnimalsDao.getAnimalWithDetailsById`, отдельный
   запрос на строку — N+1) и список болезней вакцины
   (`VaccinationsDao._getDiseasesByLink`, тоже отдельный запрос на строку),
   вычисляет `vaccinationStatus`
   (`VaccinationsDao.calculateVaccinationStatus`) и собирает
   `VaccinationWithDetails`.
8. При успехе cubit эмитит `UnsentVaccinationLoaded(vaccinations: <список>,
   selectedVaccinations: [])` — выбор всегда сбрасывается на пустой список
   независимо от того, что было выбрано до вызова `load()` (в отличие от
   `loadSilent()`, который пытается, но фактически не может сохранить
   выбор — отдельная, уже задокументированная находка в тестах, не предмет
   этого файла).
9. `BlocBuilder<UnsentVaccinationCubit, UnsentVaccinationState>` в
   `UnsentVaccinationPage` рендерит по типу состояния:
   - `UnsentVaccinationLoading` → `BottomSheetPageWrapper` с
     `CustomLottieLoader`.
   - `UnsentVaccinationLoaded` **с непустым** `vaccinations` →
     `ListView.separated` из `_VaccinationCard` (вакцина, список болезней,
     дата вакцинации, баннер ошибки, если `errors` не `null`/не пусто),
     `onTap` каждой карточки — переход на
     `Routes.unsentVaccinationEdit` с `extra: v.id`.
   - `UnsentVaccinationLoaded` **с пустым** `vaccinations` →
     `BottomSheetPageWrapper` с `ProgressMessage.notFound(message:
     l10n.list_is_empty)` — это второе, отдельное успешное состояние экрана
     (тот же `RESULT` `READ_OK`, другой визуальный итог).
10. Кнопка массового удаления в `AppBar` (`Icons.delete_sweep_outlined`)
    показывается только когда состояние — `UnsentVaccinationLoaded` и
    `vaccinations` непусто (`if (state is! UnsentVaccinationLoaded ||
    state.vaccinations.isEmpty) return const SizedBox.shrink()`) — в
    пустом варианте кнопки массового удаления корректно нет.

### Альтернативные потоки

- **Пустой список (`UnsentVaccinationLoaded` с `vaccinations.isEmpty`).**
  Не ошибка — `getNotSyncVaccinationsWithDetails()` вернул `[]` (нет ни
  одной ещё не отправленной новой записи вакцинации). Экран показывает
  `ProgressMessage.notFound(l10n.list_is_empty)` вместо списка, кнопка
  массового удаления скрыта. Тот же `RESULT` (`READ_OK`), просто без
  элементов — не отдельный use-case, см. шаг 9 выше.
- **Исключение внутри `getNotSyncVaccinationsWithDetails()`.** Перехватывается
  `catch (e)`, cubit эмитит `UnsentVaccinationError(message: e.toString(),
  selectedVaccinations: [])`; страница рендерит
  `ProgressMessage.somethingWentWrong(message: state.message)`. Другой
  `RESULT` (`READ_ERROR`) для того же события — за границами этого файла;
  тестово заякорен отдельной группой `UC-299` (см. «Связанные тесты»).
- **Возврат с экрана правки записи (`Routes.unsentVaccinationEdit`) без
  повторной загрузки.** Переход на правку выполняется без `await` и без
  обработки результата (`onTap: () => context.pushNamed2(...)`, без чтения
  возвращаемого значения); родительский `UnsentVaccinationCubit` не
  пересоздаётся (вложенный маршрут пушится поверх того же экрана-хаба) и
  `load()` повторно не вызывается. После правки записи через этот же хаб
  список, показанный этим сценарием, не обновляется автоматически — см.
  «Открытые вопросы».

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  единственная сущность, чьё состояние отображает этот экран; читается
  только подмножество с `createdAt != null` (по построению запроса, см.
  шаг 6).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — подгружается
  построчно (`AnimalWithDetails`) для каждой отображаемой записи
  вакцинации, хотя на самой карточке (`_VaccinationCard`) поля животного
  не показываются напрямую — используется только для построения модели
  `VaccinationWithDetails.animal`.
- [ENT-6](../entities/ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md)
  (DiseasesKind/Disease, HANDBOOKS) — список болезней вакцины подгружается
  построчно и показывается в карточке (`diseasesStr`).
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается join'ом при построении `VaccinationWithDetails`
  (поле `unit`), на карточке этого экрана не отображается.
- Справочники `Vaccine`, `InjectionMethod`, `InjectionPlace`,
  `VaccinationType` (VAC-локальные, без собственного `ENT`, см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «Связи») —
  подтягиваются тем же join'ом; из них на карточке показывается только имя
  вакцины (`vaccination.vaccine.name`).

### Бизнес-правила

- **Список этого экрана и числовой бейдж плитки «Вакцинация» на «В
  работе» считаются двумя разными DAO-запросами с разными явными
  предикатами.** `getNotSyncVaccinationsWithDetails` фильтрует по
  `sync=false ∧ deletedAt IS NULL ∧ updatedAt IS NULL` (без явного
  `createdAt.isNotNull()`); `VaccinationsDao.watchCountNotSync`
  (используемый `InWorkBloc` для `vaccinationsCount`) фильтрует по тем же
  трём условиям **плюс** явный `createdAt.isNotNull()`. При соблюдении
  инварианта ENT-14 (ровно один из трёх флагов установлен) оба запроса
  возвращают одинаковый набор строк; расхождение возможно только если
  где-то в кодовой базе появится строка с `sync=false` и всеми тремя
  датами `null` одновременно — не наблюдалось, но предикаты не
  идентичны буквально.
- Бейдж плитки «Вакцинация» на «В работе» — сумма трёх независимых счётчиков
  (`vaccinationsCount + editableVaccinationsCount + deletableVaccinationsCount`),
  а этот экран показывает только первую категорию. Поскольку, по находке
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), пути,
  порождающие `updatedAt`/`deletedAt` для уже синхронизированной записи, на
  сегодня недостижимы ни из одного экрана, на практике
  `editableVaccinationsCount`/`deletableVaccinationsCount` всегда должны
  быть `0`, и число на бейдже совпадает с числом карточек на этом экране —
  но это следствие недостижимости, а не то, что сам бейдж и список
  используют одну и ту же выборку.
- Выбор (`selectedVaccinations`) всегда безусловно очищается при успешном
  `load()`, независимо от того, что было выбрано ранее — сброс, не
  сохранение состояния.
- Экран не подписан на изменения таблицы `Vaccinations` реактивно
  (`watch`); `load()` — разовый запрос на момент построения cubit'а.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток (оба варианта успеха: непустой список и пустой
список) полностью реализован и достижим из UI.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `_InWorkPageState.build` (плитка `EventTileData` с `icon: Assets.eventVaccination`) | CURRENT | обычная точка входа — переход по `Routes.unsentVaccination` |
| `lib/pages/in_work/in_work_bloc.dart` | `InWorkBloc` (подписки на `watchCountNotSync`/`watchCountEditableVaccinations`/`watchCountDeletableVaccinations`) | CURRENT | считает суммарный бейдж плитки; не используется самим экраном-хабом напрямую |
| `lib/pages/routes.dart` | `Routes.unsentVaccination` | CURRENT | имя/путь маршрута, включает вложенный `Routes.unsentVaccinationEdit` |
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage.build` | CURRENT | создаёт cubit, вызывает `load()` один раз, рендерит все три состояния (включая раздельно непустой/пустой варианты `Loaded`) |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | предмет этого файла — загрузка списка |
| `lib/pages/unsent_vaccination/unsent_vaccination_state.dart` | `UnsentVaccinationLoading`, `UnsentVaccinationLoaded`, `UnsentVaccinationError` | CURRENT | состояния экрана (plain-классы, не `freezed`/`Equatable`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getNotSyncVaccinationsWithDetails` | CURRENT | тонкая делегация в DAO |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | основной join-запрос: `sync=false ∧ deletedAt IS NULL ∧ updatedAt IS NULL`, без явного `createdAt.isNotNull()` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.watchCountNotSync` | CURRENT | отдельный запрос для бейджа «В работе», с явным `createdAt.isNotNull()` — см. «Бизнес-правила» |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.calculateVaccinationStatus` | CURRENT | вычисляемый статус на каждую запись результата |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | построчная (N+1) подгрузка животного для каждой вакцинации |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `VaccinationWithDetails` | CURRENT | модель строки списка |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.notFound`, `ProgressMessage.somethingWentWrong` | CURRENT | UI пустого состояния / состояния ошибки |

## Критерии приёмки

- При открытии хаба (`Routes.unsentVaccination`) cubit вызывает `load()`
  ровно один раз без участия пользователя, независимо от текущего значения
  бейджа плитки «Вакцинация» на «В работе».
- Если `getNotSyncVaccinationsWithDetails()` вернул непустой список,
  состояние — `UnsentVaccinationLoaded` с этим списком и пустым
  `selectedVaccinations`; экран показывает карточки в порядке убывания
  `vaccinationDate`, кнопка массового удаления в `AppBar` видима.
- Если `getNotSyncVaccinationsWithDetails()` вернул пустой список,
  состояние — `UnsentVaccinationLoaded` с пустым `vaccinations` и пустым
  `selectedVaccinations`; экран показывает `list_is_empty`, кнопка
  массового удаления в `AppBar` скрыта — оба случая одинаковый `RESULT`
  (`READ_OK`), разный визуальный итог.
- Ни правка, ни «мягкое»/полное удаление уже синхронизированной записи не
  попадают в список этого экрана — запрос отбирает только строки,
  эквивалентные `createdAt != null` (по построению, через инвариант
  взаимоисключающих флагов [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).

## Связанные тесты

`test/pages/unsent_vaccination_cubit_test.dart`, группа `group('UC-79 —
UnsentVaccinationCubit.load', ...)` (старый id — будет переименована в
`UC-79` отдельным проходом) — один тест: `'load() успех ->
UnsentVaccinationLoaded с пустым selectedVaccinations'`. По умолчанию мок
`vaccinationsRepository.getNotSyncVaccinationsWithDetails()` в `setUp`
возвращает `[]`, поэтому этот тест фактически покрывает только вариант
**пустого списка** (`UnsentVaccinationLoaded` с `vaccinations.isEmpty`), не
именуя его так явно.

Вариант **непустого списка** отдельного теста под этим (или любым другим)
UC-якорем не имеет: в файле есть единственный тест с непустым результатом
`getNotSyncVaccinationsWithDetails()` — внутри группы без UC-номера
(`'UnsentVaccinationCubit.loadSilent/selectAll/vaccitanionIsSelected'`,
тест `'selectAll(true) выбирает все загруженные вакцинации;
selectAll(false) очищает выбор'`), но его assertions проверяют только
`selectAll`/`selectedVaccinations`, не сам факт корректной загрузки
непустого `Loaded`-состояния — совпадение по данным, не целевой тест этого
сценария.

**TBD — нет отдельного, явно заякоренного теста непустого варианта
`UnsentVaccinationLoaded` для `UC-79`.**

(Ошибочная ветка `load()` заякорена отдельно, группой `'UC-80 —
UnsentVaccinationCubit.load ERROR'` — другой `RESULT`, не предмет этого
файла.)

## Открытые вопросы и ограничения

- **Хаб не обновляется реактивно.** `load()` — разовый вызов на момент
  создания cubit'а; если после открытия экрана где-то ещё (например,
  фоновым sync-проходом или из другого места приложения) появится/исчезнет
  ещё не отправленная запись вакцинации, уже открытый экран этого не
  увидит без полного пересоздания (выход и повторный вход в хаб) либо без
  вызова `delete()`/`deleteSelected()` (которые сами вызывают `load()`
  повторно).
- **Возврат с экрана правки не перезагружает список.** Переход на
  `Routes.unsentVaccinationEdit` не дожидается результата и не вызывает
  `load()` по возвращении — после правки записи через этот хаб
  отображаемая карточка может остаться со старыми значениями до следующего
  события, вызывающего `load()`. Сама логика правки — предмет отдельного
  use-case ([EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md)),
  здесь фиксируется только то, что этот READ_OK-сценарий не перезапускается
  автоматически.
- **Явный предикат count-запроса и list-запроса не идентичен буквально**
  (см. «Бизнес-правила») — совпадение результатов сегодня зависит от
  инварианта ENT-14, не проверяется в момент чтения самим кодом.
- **N+1 при построении списка.** На каждую запись — отдельный запрос
  животного и отдельный запрос болезней; не проверялось, при каком
  практическом размере ещё не отправленной очереди это становится заметно
  пользователю (список ограничен количеством локально созданных, ещё не
  отправленных вакцинаций между sync-проходами — как правило, невелик).
- **Непустой вариант `UnsentVaccinationLoaded` не имеет собственного
  заякоренного теста** — см. «Связанные тесты».
