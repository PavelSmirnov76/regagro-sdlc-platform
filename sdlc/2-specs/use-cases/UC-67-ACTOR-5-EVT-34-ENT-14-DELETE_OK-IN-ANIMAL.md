# UC-67 — Пользователь удаляет неотправленную вакцинацию — одну с карточки или несколько отмеченных разом, удаление успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует успешный (`DELETE_OK`) исход события
[EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md)
(`vaccination.deleted_unsent`) на экране хаба неотправленных вакцинаций
(`UnsentVaccinationPage`): пользователь безусловно («жёстко») удаляет из
локальной таблицы `Vaccinations` либо одну ещё не отправленную запись —
иконкой удаления на карточке (`UnsentVaccinationCubit.delete`), либо несколько
записей разом — иконкой «удалить отмеченные» в шапке экрана
(`UnsentVaccinationCubit.deleteSelected`). Оба метода делегируют физическое
удаление в `VaccinationsRepository.deleteById` → `VaccinationsDao.deleteById`
(безусловный `DELETE ... WHERE id = ?`, без параметра «мягкого» удаления).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `UnsentVaccinationPage`
не проверяет статус авторизации. Единственное предусловие для показа самого
экрана — переход с плитки «Вакцинация» экрана «В работе»; единственное
предусловие для показа иконки «удалить отмеченные» — список загруженных
неотправленных вакцинаций не пуст (иконка на карточке видна всегда, раз
карточка отрисована).

## CURRENT

### Основной поток

1. Пользователь попадает на `UnsentVaccinationPage` с плитки «Вакцинация»
   экрана «В работе» (`EventTileData` → `onTap: () =>
   context.pushNamed2(Routes.unsentVaccination)`,
   `lib/pages/in_work/in_work_page.dart`). Маршрут зарегистрирован в
   `lib/pages/routes.dart` (`Routes.unsentVaccination` →
   `UnsentVaccinationPage`, без аргументов конструктора).
2. `UnsentVaccinationPage.build` создаёт `BlocProvider(create: (context) =>
   UnsentVaccinationCubit()..load())`. `load()` вызывает
   `_vaccinationsRepository.getNotSyncVaccinationsWithDetails()`
   (`VaccinationsRepository` → `VaccinationsDao`), которая фильтрует строки
   `Vaccinations` по `sync == false && deletedAt IS NULL && updatedAt IS NULL
   && createdAt IS NOT NULL` — то есть строго ещё ни разу не отправленные
   новые записи (правка/«мягкое» удаление уже синхронизированной записи сюда
   не попадают в принципе — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
   Результат эмитится как `UnsentVaccinationLoaded(vaccinations: ...,
   selectedVaccinations: [])` — список выбранных всегда сбрасывается в пустой
   при каждом `load()`.
3. `UnsentVaccinationPage.build`'s `BlocBuilder` в `actions` шапки рендерит
   `IconButton(icon: Icons.delete_sweep_outlined, tooltip: l10n.delete)`
   только когда `state is UnsentVaccinationLoaded && state.vaccinations
   .isNotEmpty`; иначе — `SizedBox.shrink()`. Тело страницы рендерит список
   карточек `_VaccinationCard`, у каждой — `GestureDetector(onTap: onDelete,
   child: Icon(Icons.delete_outline, ...))` поверх даты вакцинации.
4. **Путь А — удаление одной записи.** Тап по иконке `delete_outline` карточки
   вызывает `onDelete` → `_showDeleteDialog(context, v)`, где `v` —
   `VaccinationWithDetails` этой карточки (`v != null`).
5. **Путь Б — удаление отмеченных разом.** Тап по иконке
   `delete_sweep_outlined` в шапке вызывает `_showDeleteDialog(context,
   null)`.
6. `_showDeleteDialog` (общий для обоих путей) открывает `AlertDialog`
   (`showDialog(useRootNavigator: true)`) с заголовком `l10n
   .delete_vaccination` («Удаление вакцинации») — текст один и тот же для
   единичного и группового удаления, без указания количества записей.
   Кнопка «Отмена» (`l10n.cancel`) вызывает `Navigator.of(dialogContext)
   .pop()` без обращения к кубиту. Кнопка «Удалить» (`l10n.delete`, красным)
   по нажатию: если `vaccination == null` (путь Б) — вызывает
   `context.read<UnsentVaccinationCubit>().deleteSelected()`; иначе (путь А)
   — `context.read<UnsentVaccinationCubit>().delete(vaccination.id)`; в обоих
   случаях сразу следующей строкой, не дожидаясь `Future` от вызова, диалог
   закрывается (`Navigator.of(dialogContext).pop()`) — UI не ждёт результата
   удаления и не может показать ошибку из этого места.
7. **`UnsentVaccinationCubit.delete(vaccinationId)`** (путь А):
   ```dart
   Future<void> delete(int vaccinationId) async {
     try {
       await _vaccinationsRepository.deleteById(vaccinationId);
       load();
     } catch (e) { ... }
   }
   ```
   `deleteById` → `VaccinationsDao.deleteById` выполняет `(delete(vaccinations)
   ..where((tbl) => tbl.id.equals(vaccinationId))).go()` — обычный Drift
   `DELETE`, безусловный по `id`; метод не проверяет `sync`/`createdAt` сам —
   безопасность целиком опирается на то, что `vaccinationId` пришёл из уже
   отфильтрованного списка `state.vaccinations` (шаг 2).
8. **`UnsentVaccinationCubit.deleteSelected()`** (путь Б):
   ```dart
   Future<void> deleteSelected() async {
     try {
       for (var id in state.selectedVaccinations) {
         await _vaccinationsRepository.deleteById(id);
       }
       load();
     } catch (e) { ... }
   }
   ```
   цикл вызывает `deleteById` последовательно (`await` на каждой итерации,
   не параллельно) для каждого id из `state.selectedVaccinations` — список
   заполняется только методами `UnsentVaccinationCubit.select`/`selectAll`.
   **По коду `lib/` (проверено `grep -rn` по всему дереву) ни один из этих
   двух методов не вызывается нигде, кроме самого кубита** — ни в
   `_VaccinationCard`, ни в `UnsentVaccinationPage`, ни где-либо ещё нет ни
   чекбокса, ни другого способа выбора отдельной записи. Единственный живой
   вызов `deleteSelected()` — из шага 6 (путь Б), и в момент этого вызова
   `state.selectedVaccinations` — это ровно тот пустой список `[]`, который
   `load()` эмитил на шаге 2 и который с тех пор никто не менял. Поэтому в
   реальном UI цикл шага 8 выполняется **ноль раз**: `deleteSelected()`
   успешно завершается, не вызвав `deleteById` вообще ни разу, и переходит к
   `load()` — то есть нажатие «удалить отмеченные» сегодня всегда сводится к
   диалогу подтверждения, за которым ничего не удаляется.
9. И `delete`, и `deleteSelected` вызывают `load()` **без `await`** в конце
   своего `try`-блока. `load()` — обычная `async`-функция, и её первая
   инструкция — синхронный `emit(UnsentVaccinationLoading())`, до первого
   `await` внутри неё самой. Поскольку вызывающий метод (`delete`/
   `deleteSelected`) не дожидается `Future`, возвращённого `load()`, он
   продолжает выполнение сразу после этого вызова, не блокируясь на
   асинхронном `getNotSyncVaccinationsWithDetails()` внутри `load()` — и
   тут же завершает свой собственный `Future<void>` (в теле метода после
   вызова `load()` больше нет инструкций). Итог: `Future`, возвращённый
   `cubit.delete(...)`/`cubit.deleteSelected()`, резолвится, когда
   `cubit.state` уже успело стать `UnsentVaccinationLoading` (эмитировано
   синхронно из `load()`), но ещё **не** стало `UnsentVaccinationLoaded` —
   это происходит только на следующем обороте event loop, когда
   `getNotSyncVaccinationsWithDetails()` внутри `load()` в свою очередь
   резолвится.
10. Когда `load()` внутри шага 9 в итоге дорезолвится, состояние переходит в
    `UnsentVaccinationLoaded` со свежим списком (по тому же фильтру, что и
    шаг 2) и заново пустым `selectedVaccinations: []`. Для пути А удалённая
    запись больше не входит в список; для пути Б (в реальном UI) список не
    меняется вовсе, так как ничего не было удалено. Если после пути А список
    опустел полностью — `UnsentVaccinationPage.build` рендерит
    `ProgressMessage.notFound` вместо списка, и иконка «удалить отмеченные» в
    шапке перестаёт отображаться (условие шага 3).

### Альтернативные потоки

- **Отмена в диалоге подтверждения** (кнопка «Отмена» или тап по барьеру —
  `showDialog` по умолчанию `barrierDismissible: true`, явно не
  переопределён) — `Navigator.of(dialogContext).pop()` без обращения к
  кубиту; ни `delete`, ни `deleteSelected` не вызываются, состояние и список
  не меняются.
- **Партиальность цикла `deleteSelected` при исключении на одной из
  итераций.** Один `try`/`catch` оборачивает весь `for`-цикл шага 8, не
  каждую итерацию отдельно: если `deleteById` бросает исключение на
  каком-то id из середины `state.selectedVaccinations`, все id, обработанные
  **до** него, уже физически удалены (откат не выполняется — вызовы не
  обёрнуты в общую Drift-транзакцию), а id **после** него в этом проходе не
  обрабатываются вовсе. В этом (`DELETE_OK`) сценарии исключений не бывает
  по определению, но сам механизм цикла (последовательный, без
  промежуточных чекпоинтов) — факт, действующий одинаково что при успехе,
  что при отказе; отдельный `RESULT = DELETE_ERROR` для этого не описан
  здесь.
- **`select()` брошен бы `UnsupportedError`, если бы что-то вызвало его до
  первого `load()`.** Состояние по умолчанию (`UnsentVaccinationState`'s
  базовый конструктор) использует `selectedVaccinations = const []` —
  неизменяемый список; `select()` пытается вызвать `.add()`/`.remove()` на
  нём. Поскольку `select()` в принципе не вызывается из `lib/` (см. шаг 8),
  это второй, независимый слой поломки того же самого «выбор для группового
  удаления не работает» — не наблюдаем сегодня только потому, что первый
  слой (отсутствие UI выбора) не даёт до него дойти.
- **Исключение внутри `deleteById` для пути А** (единичное удаление) —
  `catch` кубита эмитит `UnsentVaccinationError(message: e.toString(),
  selectedVaccinations: state.selectedVaccinations)`; в отличие от
  `UnsentVaccinationLoaded`, `UnsentVaccinationPage`'s `BlocBuilder`
  действительно реагирует на этот вариант (`ProgressMessage
  .somethingWentWrong`) — отдельный сценарий, `RESULT = DELETE_ERROR`, не
  описан этим файлом.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность сегмента `ENT`: строка (или строки) физически удаляются из
  таблицы `Vaccinations` методом `VaccinationsDao.deleteById`, который
  трогает только эту таблицу — ни джойн-таблица `DiseasesVaccinations`
  (список болезней, покрытых записью), ни что-либо ещё этим методом не
  затрагивается. Схема `DiseasesVaccinations.vaccinationId` объявлена как
  `REFERENCES vaccinations(id) NOT NULL` (`packages/sheep_farm_database/lib/
  entities/vaccination/diseases/diseases_vaccinations.dart`), но без `ON
  DELETE CASCADE`, и Dart-код `deleteById` не выполняет никакой очистки
  дочерних строк сам — см. «Открытые вопросы».
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  только «вбок», через джойн внутри `getNotSyncVaccinationsWithDetails`
  (для отображения имени/данных животного на карточке), но **не изменяется**
  этим сценарием никак: в отличие от аналогичного удаления неотправленного
  перемещения (см. [UC-56](UC-56-ACTOR-5-EVT-28-ENT-13-DELETE_OK-IN-ANIMAL.md)),
  у удаления вакцинации нет побочного эффекта на поля `Animal`.

### Бизнес-правила

- Оба способа удаления (одна запись / несколько разом) используют один и
  тот же диалог подтверждения с одним и тем же текстом заголовка — UI не
  различает единичное и групповое удаление в копирайте.
- Физическое (`deleteById`) удаление, а не мягкая пометка — единственный
  способ убрать запись с этого экрана; поле `deletedAt` у `Vaccination`
  вообще не участвует в этом сценарии (оно относится к недостижимому пути
  удаления уже синхронизированной записи, см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
- `deleteById` не имеет собственного условия безопасности (не проверяет
  `sync`/`createdAt`/`updatedAt`/`deletedAt` записи) — корректность целиком
  опирается на то, что вызывающий код (`delete`/`deleteSelected`) всегда
  передаёт id, взятый из списка, уже отфильтрованного
  `getNotSyncVaccinationsWithDetails`.
- И `delete`, и `deleteSelected` полагаются на побочный вызов `load()` (без
  `await`) как единственный способ обновить список на экране — ни один из
  двух методов не эмитит состояние с уменьшенным списком напрямую.
- В реальном UI групповое удаление (`deleteSelected`) сегодня эквивалентно
  «показать диалог подтверждения и ничего не удалить» — выбор отдельных
  записей нигде не реализован (см. «Открытые вопросы»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не заблокировано — оба метода (`delete`, `deleteSelected`) реализованы,
покрыты тестом на успешный исход и оба достижимы из реального UI (шаги 4–6).
Однако для `deleteSelected` «достижимость» ограничена вызовом метода как
такового: содержательный эффект (удаление хотя бы одной записи через путь Б)
недостижим сегодня ни при каких действиях пользователя, потому что ничто не
заполняет `state.selectedVaccinations` — см. «Открытые вопросы и
ограничения». Это не блокирует `RESULT = DELETE_OK` формально (метод
успешно завершается и в этом вырожденном случае), но означает, что
happy-path «пользователь отмечает несколько вакцинаций и удаляет их разом»
не существует в приложении на сегодня, только happy-path «пользователь
удаляет одну запись с карточки».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | плитка «Вакцинация» (`EventTileData.onTap` → `context.pushNamed2(Routes.unsentVaccination)`) | CURRENT | точка входа — переход с экрана «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentVaccination` (регистрация маршрута) | CURRENT | маршрут → `UnsentVaccinationPage` |
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage.build`, `_showDeleteDialog`, `_VaccinationCard` (`GestureDetector(onTap: onDelete)`) | CURRENT | создаёт `UnsentVaccinationCubit()..load()`; иконки удаления (карточка/шапка); общий диалог подтверждения для обоих путей |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.delete` | CURRENT | эффект EVT-34, путь А — единичное удаление, `deleteById` + `load()` без `await` |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.deleteSelected` | CURRENT | эффект EVT-34, путь Б — цикл `deleteById` по `state.selectedVaccinations`, `load()` без `await` |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.select`, `selectAll`, `vaccitanionIsSelected` | CURRENT | заполнение/чтение `selectedVaccinations` — ни один вызывающий сайт в `lib/` за пределами самого кубита не найден |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | перечитывает список после удаления, сбрасывает `selectedVaccinations` в `[]` |
| `lib/pages/unsent_vaccination/unsent_vaccination_state.dart` | `UnsentVaccinationState`, `UnsentVaccinationLoading`, `UnsentVaccinationLoaded`, `UnsentVaccinationError` | CURRENT | `selectedVaccinations = const []` по умолчанию — источник `UnsupportedError`, если `select()` вызвать до первого `load()` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.deleteById` | CURRENT | тонкая обёртка над DAO |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.deleteById`, `getNotSyncVaccinationsWithDetails` | CURRENT | безусловный `DELETE ... WHERE id = ?`; источник списка (фильтр `sync == false && createdAt IS NOT NULL && updatedAt IS NULL && deletedAt IS NULL`) |
| `packages/sheep_farm_database/lib/entities/vaccination/diseases/diseases_vaccinations.dart` | `DiseasesVaccinations` (`vaccinationId` — `REFERENCES vaccinations(id) NOT NULL`, без `ON DELETE CASCADE`) | CURRENT | дочерняя таблица, не затрагиваемая `deleteById` напрямую — см. «Открытые вопросы» |
| `packages/sheep_farm_database/lib/database/database.dart` | `AppDatabase._openConnection` | CURRENT | точка открытия соединения — не выставляет `PRAGMA foreign_keys = ON`, см. «Открытые вопросы» |

## Критерии приёмки

- Тап по иконке `delete_outline` карточки открывает диалог подтверждения;
  подтверждение вызывает `UnsentVaccinationCubit.delete(vaccination.id)`
  ровно один раз с id именно этой карточки.
- Тап по иконке `delete_sweep_outlined` в шапке (видимой только при непустом
  списке) открывает тот же диалог; подтверждение вызывает
  `UnsentVaccinationCubit.deleteSelected()` ровно один раз.
- `delete(id)` вызывает `VaccinationsRepository.deleteById(id)` ровно один
  раз с переданным id.
- `deleteSelected()` вызывает `VaccinationsRepository.deleteById` один раз
  для каждого id, присутствующего в `state.selectedVaccinations` на момент
  вызова, последовательно, в порядке списка; при пустом
  `state.selectedVaccinations` (текущее поведение реального UI) —
  `deleteById` не вызывается ни разу, метод всё равно успешно завершается.
- Сразу после `await cubit.delete(id)` (или `await cubit.deleteSelected()`)
  состояние кубита — `UnsentVaccinationLoading`, а не `UnsentVaccinationLoaded`
  — переход в `Loaded` происходит только на следующем обороте event loop.
- После успешного завершения `load()`, вызванного изнутри `delete`/
  `deleteSelected`, `selectedVaccinations` в новом состоянии — пустой список
  независимо от того, что было в нём до вызова.

## Связанные тесты

- `test/pages/unsent_vaccination_cubit_test.dart`, group `'UC-67 —
  UnsentVaccinationCubit.delete/deleteSelected'` (старая нумерация,
  переименуется отдельным контролируемым проходом — не трогать сейчас):
  - test `'delete -> deleteById вызван, затем перезагрузка списка (load() без
    await — см. находку ниже)'` — покрывает путь А: `deleteById(5)`
    вызывается один раз, после `pumpEventQueue()` состояние —
    `UnsentVaccinationLoaded`.
  - test `'deleteSelected -> deleteById вызван для каждого выбранного id
    (load() без await — см. находку ниже)'` — покрывает путь Б, но **через
    прямой вызов `cubit.select(1, true)`/`cubit.select(2, true)` из теста**,
    а не через реальный UI (который, как установлено выше, никогда не
    вызывает `select`) — тест демонстрирует, что механизм цикла работает
    корректно при непустом `selectedVaccinations`, не то, что до этого
    состояния можно дойти, действуя в приложении.
- Тот же файл, group `'UC-67 — delete()/deleteSelected() вызывают load() без
  await (находка)'`, test `'сразу после await delete() состояние ещё
  UnsentVaccinationLoading, а не Loaded'` — покрывает находку из шага 9
  основного потока напрямую (`expect(cubit.state, isA<UnsentVaccinationLoading>())`
  сразу после `await cubit.delete(5)`, затем `Loaded` после
  `pumpEventQueue()`).
- Тот же файл, group `'НАХОДКА — select()/selectAll() до первого load()'`,
  test `'select() на состоянии по умолчанию (const []) -> Unsupported
  operation вместо мягкого поведения'` — подтверждает второй, независимый
  слой поломки группового выбора (см. «Альтернативные потоки»).
- Тот же файл, group `'UC-68 — UnsentVaccinationCubit.delete/deleteSelected
  ERROR'` — покрывает соседний `RESULT = DELETE_ERROR` (в т.ч. партиальность
  цикла `deleteSelected` при отказе на середине партии), не этот файл.

**TBD — теста нет** на уровне виджета/страницы (`UnsentVaccinationPage`,
`_showDeleteDialog`, header `IconButton`): весь существующий тест — только
на уровне кубита с замоканным `VaccinationsRepository`. В частности, нет
теста, который рендерит `UnsentVaccinationPage` целиком, нажимает иконку
«удалить отмеченные» без предварительного вызова `select()` и проверяет, что
`deleteById` не вызывается ни разу (факт из шага 8 выведен чтением кода
`_VaccinationCard`/`UnsentVaccinationPage`/`UnsentVaccinationCubit` и
grep-поиском по `lib/`, не подтверждён отдельным виджет-тестом).

**TBD — теста нет** на уровне репозитория/DAO против настоящей (in-memory)
БД: во всех существующих тестах `VaccinationsRepository` замокан целиком —
не проверено ни реальное поведение `VaccinationsDao.deleteById` (SQL
`DELETE ... WHERE id = ?`), ни судьба строк `DiseasesVaccinations`,
ссылающихся на удалённую запись (см. «Открытые вопросы»).

## Открытые вопросы и ограничения

- **Групповое удаление (`deleteSelected`) недостижимо содержательно ни из
  какого действия пользователя в реальном приложении.** Иконка «удалить
  отмеченные» существует и видна (при непустом списке), диалог
  подтверждения работает, `deleteSelected()` вызывается — но
  `state.selectedVaccinations` всегда пуст в момент этого вызова, потому что
  ни один экран/виджет не вызывает `UnsentVaccinationCubit.select`/
  `selectAll` (подтверждено `grep -rn` по всему `lib/`; единственные вызовы
  этих методов во всём дереве — из `test/pages/unsent_vaccination_cubit_test
  .dart`). Второй, независимый слой той же проблемы: если бы что-то вызвало
  `select()` до первого `load()`, оно бы упало с `UnsupportedError`, так как
  состояние по умолчанию использует `const []` (см. «Альтернативные
  потоки»). Итог — на сегодня единственный работающий сценарий этого экрана
  — удаление ровно одной записи за раз, кнопкой на карточке.
- **`load()` вызывается без `await` внутри `delete()`/`deleteSelected()`.**
  `Future`, который эти методы возвращают вызывающему коду, резолвится, пока
  `cubit.state` ещё `UnsentVaccinationLoading`, а не после того, как список
  успел перечитаться (`UnsentVaccinationLoaded`). Любой код, который в
  будущем добавит `await` на вызов `delete`/`deleteSelected` и сразу
  прочитает `cubit.state`, ожидая увидеть обновлённый список, получит
  устаревшее (или промежуточное `Loading`) состояние.
- **Цикл `deleteSelected` не атомарен** (актуально только если бы
  `selectedVaccinations` когда-нибудь стал непустым): один `try`/`catch` на
  весь `for`, без per-item обработки и без общей транзакции — отказ
  посередине партии оставляет уже обработанные id удалёнными, а необработанные
  — нетронутыми, без какого-либо отчёта пользователю о том, где именно
  остановилась обработка (это `RESULT = DELETE_ERROR`, не описанный этим
  файлом, но сам механизм — факт основного потока, воспроизводимый и в
  успешном случае, если бы список был непустым).
- **`deleteById` не имеет собственного условия безопасности.** DAO-метод
  выполняет безусловный `DELETE ... WHERE id = ?` без проверки `sync`/
  `createdAt`/`updatedAt`/`deletedAt` — сегодня единственные вызывающие
  сайты передают id из уже отфильтрованного списка неотправленных записей,
  но сам метод ничего не мешало бы вызвать и с id уже синхронизированной
  записи (жёстко удалив её), появись такой вызывающий код в будущем.
- **Судьба строк `DiseasesVaccinations`, ссылающихся на удалённую
  вакцинацию, не установлена чтением кода однозначно.**
  `VaccinationsDao.deleteById` — однотабличный `DELETE`, без какой-либо
  явной очистки `DiseasesVaccinations`; в схеме этой таблицы объявлено
  `vaccinationId INTEGER REFERENCES vaccinations(id) NOT NULL`, но без `ON
  DELETE CASCADE`. Заблокирует ли SQLite сам `DELETE` (если бы ограничение
  внешнего ключа реально проверялось на этом соединении) или оставит
  дочерние строки осиротевшими (если проверка выключена) — зависит от того,
  включён ли `PRAGMA foreign_keys` на используемом соединении. По коду
  `_openConnection` (`packages/sheep_farm_database/lib/database/database
  .dart`) явного `PRAGMA foreign_keys = ON` при открытии соединения нет;
  единственные два места во всём дереве, где этот PRAGMA вообще
  упоминается, — `AppDatabase.clearAllClearableTables`
  (`database.clearable.dart`), где он выключается и затем снова включается
  вокруг разового массового удаления при логауте. Утверждать однозначно, что
  происходит с обычным `deleteById` вне этого потока, нельзя без отдельного
  теста против настоящей БД (такого теста нет, см. «Связанные тесты»).
- Общий текст диалога подтверждения («Удаление вакцинации») не различает
  «удалить одну запись» и «удалить отмеченные» — не функциональная проблема,
  но при появлении рабочего группового выбора в будущем стоит пересмотреть
  копирайт (не разбирается глубже в рамках этого документирующего прохода).
