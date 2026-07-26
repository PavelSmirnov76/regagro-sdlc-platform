# UC-87 — Пользователь удаляет одно ещё не отправленное взвешивание с хаба «В работе», удаление успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `DELETE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует успешный (`DELETE_OK`) исход события
[EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md)
(`animal_weighing.deleted_unsent`) на экране хаба неотправленных взвешиваний
(`UnsentAnimalWeighingsPage`): пользователь безусловно («жёстко») удаляет одну
ещё не отправленную запись `AnimalWeighing` (`sync == false`) иконкой удаления
на строке списка — `AnimalWeighingsCubit.delete`. Метод делегирует физическое
удаление в унаследованный `BaseRepository.delete` (не переопределён в
`AnimalWeighingsRepository`) → `AnimalWeighingsDao`/`BaseDao.del` — обычный
Drift `DELETE` по первичному ключу `id`, без параметра «мягкого» удаления (у
`AnimalWeighing` вообще нет поля для этого).

**НАХОДКА, подтверждённая существующим тестом.** `_animalWeightingsRepository
.delete(animalWeighing)` внутри `delete()` вызывается **без `await`** — метод
сразу переходит к `await loadNotSync()`, не дожидаясь и никак не проверяя
результат вызова `repository.delete`. Разобрано подробнее в «Бизнес-правила»
и «Открытые вопросы и ограничения».

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: `UnsentAnimalWeighingsPage` не
проверяет статус авторизации. Единственное предусловие для показа самого
экрана — переход с плитки «Взвешивание» экрана «В работе»; единственное
предусловие для показа иконки удаления конкретной строки — эта строка вообще
отрисована в списке (список уже отфильтрован по `sync == false`).

## CURRENT

### Основной поток

1. Пользователь попадает на `UnsentAnimalWeighingsPage` с плитки «Взвешивание»
   экрана «В работе» (`EventTileData` с `count: data.animalWeighingsCount` →
   `onTap: () => context.pushNamed2(Routes.unsentAnimalWeighings)`,
   `lib/pages/in_work/in_work_page.dart`). Маршрут зарегистрирован в
   `lib/pages/routes.dart` (`Routes.unsentAnimalWeighings` →
   `UnsentAnimalWeighingsPage`, без аргументов конструктора).
2. `UnsentAnimalWeighingsPage.build` создаёт `BlocProvider(create: (context) =>
   AnimalWeighingsCubit()..loadNotSync())`. `loadNotSync()` эмитит
   `AnimalWeighingsState.loading()`, затем вызывает
   `_animalWeightingsRepository.getAllNotSuncAnimalWeighings()`
   (`AnimalWeighingsRepository` → `AnimalWeighingsDao
   .getAllNotSuncAnimalWeighings`, `SELECT ... WHERE sync = 0`). Для каждой
   строки строится `AnimalWeighingWithDetails` (животное — через
   `_animalsRepository.getAnimalWithDetailsById(animalWeighing.animalId)`,
   единица — через `_unitsRepository.getById(unitId)`, если `unitId != null`),
   список сортируется по `weighingDate` по возрастанию и эмитится как
   `AnimalWeighingsState.loadedNotSync(animalWeighings: ...toModel())`.
3. `UnsentAnimalWeighingsPage`'s `BlocBuilder` при
   `AnimalWeighingsLoadedNotSync` рендерит `AnimalWeighingListNotSyncWidget`
   со списком (`animalWeighings.map((e) => e.animalWeighing)`),
   `onTapDel: context.read<AnimalWeighingsCubit>().delete` — метод кубита
   передан как есть, без обёртки; `onTap` (переход на редактирование строки)
   к этому сценарию не относится.
4. Каждая строка списка (`AnimalWeighingListNotSyncWidget`) показывает иконку
   удаления (`Icons.delete_outline`) внутри `GestureDetector(onTap: onDelete)`
   — тап по ней немедленно, **без диалога подтверждения**, вызывает
   `onDelete()` → `onTapDel(animalWeighings[index].animalWeighing)` →
   `AnimalWeighingsCubit.delete(animalWeighing)` с конкретной строкой
   `AnimalWeighing` этой карточки.
5. `AnimalWeighingsCubit.delete`:
   ```dart
   Future<void> delete(AnimalWeighing animalWeighing) async {
     _animalWeightingsRepository.delete(animalWeighing);

     await loadNotSync();
   }
   ```
   Вызов `_animalWeightingsRepository.delete(animalWeighing)` **не
   дожидается своего `Future`** (нет `await`, нет присваивания в переменную,
   результат никак не проверяется) — метод сразу переходит к следующей
   строке. Метод целиком не обёрнут в `try`/`catch` — в отличие от
   `AnimalWeighingsCubit.deleteImmediate` (соседний, недостижимый из UI путь,
   см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)), у `delete`
   вообще нет обработки исключений ни на одном из двух вызовов.
6. `AnimalWeighingsRepository.delete` не переопределён — это унаследованный
   `BaseRepository<AnimalWeighingsDao, AnimalWeighing,
   $AnimalWeighingsTable>.delete(item)` → `dao.del(item)` → `BaseDao.del` =
   `deleteCurrent().delete(item)` — Drift `DeleteStatement.delete`, удаляющий
   строку по совпадению первичного ключа (`id`) переданного `item`; физическое
   (`hard`) удаление, `AnimalWeighing` не имеет поля вроде `deletedAt`/
   `isDeleted`.
7. `await loadNotSync()` в шаге 5 выполняется и дожидается своего результата
   как обычно (шаг 2: `loading()` → `getAllNotSuncAnimalWeighings()` →
   `loadedNotSync(...)`). Поскольку сам вызов `repository.delete(...)` из
   предыдущей строки не был дождан, `Future`, который возвращает
   `cubit.delete(animalWeighing)` вызывающему коду, резолвится **как только
   резолвится `loadNotSync()`** — независимо от того, успел ли к этому
   моменту реально завершиться (успешно или с исключением) сам вызов
   `repository.delete`.
8. Удалённая строка (в реальном, не замоканном случае) отсутствует в новом
   списке, полученном на шаге 7 запросом `getAllNotSuncAnimalWeighings()` —
   но это следствие того, что `delete`/`loadNotSync` выполняются
   последовательно в одном и том же вызове кубита на одном и том же
   drift-соединении, а не явной гарантии дождаться завершения удаления перед
   перечитыванием (см. «Открытые вопросы и ограничения»).

### Альтернативные потоки

- Диалога подтверждения перед удалением на этом экране нет вовсе — тап по
  иконке сразу инициирует удаление; отдельного сценария «пользователь
  передумал» для этого экрана не существует.
- **Исключение внутри `repository.delete(animalWeighing)`.** Поскольку вызов
  не обёрнут ни в `try`/`catch`, ни дождан через `await`, исключение из него
  становится необработанной асинхронной ошибкой (`Future`, брошенный без
  слушателя) — она не попадает ни в состояние кубита (нет отдельного
  error-состояния у `AnimalWeighingsState`, см. `animal_weighings_state.dart`
  — только `initial`/`loading`/`loaded`/`loadedNotSync`), ни в лог через
  `Talker` (в отличие от `deleteImmediate`, который явно логирует ошибку).
  `loadNotSync()` в это время выполняется независимо от исхода `delete` и
  доходит до `loadedNotSync` штатно. Отдельный `RESULT = DELETE_ERROR` для
  этого сценария не описан — по коду нет ветки, которая бы отличала его от
  успеха на уровне состояния кубита или экрана.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  сущность сегмента `ENT`: строка физически удаляется из таблицы
  `AnimalWeighings` по первичному ключу `id`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается только
  «вбок», через `_animalsRepository.getAnimalWithDetailsById` при построении
  списка (шаг 2, для отображения данных животного на строке); этим сценарием
  не изменяется никак — в отличие от удаления неотправленного перемещения
  ([UC-56](UC-56-ACTOR-5-EVT-28-ENT-13-DELETE_OK-IN-ANIMAL.md)), у удаления
  взвешивания нет побочного эффекта на поля `Animal`.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается только «вбок» тем же образом (единица измерения веса
  строки), не изменяется.

### Бизнес-правила

- Единственный способ убрать запись с этого экрана — физическое удаление по
  `id`; поле, отличающее «мягко удалённую» запись, у `AnimalWeighing` вообще
  отсутствует как концепция.
- Удаление одной строки не показывает диалог подтверждения — эффект
  наступает немедленно по тапу на иконку.
- **НАХОДКА.** `AnimalWeighingsCubit.delete` вызывает
  `_animalWeightingsRepository.delete(animalWeighing)` без `await` и без
  обработки исключений, затем безусловно `await loadNotSync()`. Как следствие:
  - `Future`, возвращаемый `cubit.delete(...)` вызывающему коду
    (`onTapDel`/тесту), отражает только завершение `loadNotSync()`, не
    завершение самого удаления — вызывающий код не может ни дождаться
    реального завершения удаления, ни узнать о его отказе через этот вызов.
  - Список, который показывает `loadedNotSync`, полагается на то, что
    `getAllNotSuncAnimalWeighings()` внутри `loadNotSync()` фактически
    выполнится после того, как удаление уже применилось к таблице — это не
    гарантировано на уровне кода вызывающего метода (`await` на
    `repository.delete` отсутствует), только фактическим порядком постановки
    операций на одно и то же drift-соединение (см. «Открытые вопросы»).
  - Ни одно исключение из `repository.delete` не может быть показано
    пользователю через этот путь — у `AnimalWeighingsState` нет
    error-варианта, а сам вызов ничем не обёрнут.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не заблокировано — сценарий полностью реализован, достижим из реального UI
(шаги 1–5) и покрыт тестом на успешную ветку и отдельно на саму находку
(«без `await`», см. «Связанные тесты»). Находки, перечисленные в «Открытые
вопросы и ограничения», не блокируют выполнение сценария — `RESULT =
DELETE_OK` наступает независимо от них при штатном (не бросающем
исключение) `repository.delete`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | плитка «Взвешивание» (`EventTileData.onTap` → `context.pushNamed2(Routes.unsentAnimalWeighings)`) | CURRENT | точка входа — переход с экрана «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentAnimalWeighings` (регистрация маршрута) | CURRENT | маршрут → `UnsentAnimalWeighingsPage` |
| `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart` | `UnsentAnimalWeighingsPage.build` | CURRENT | создаёт `AnimalWeighingsCubit()..loadNotSync()`, подключает `onTapDel: context.read<AnimalWeighingsCubit>().delete` |
| `lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart` | `AnimalWeighingListNotSyncWidget` (`GestureDetector(onTap: onDelete)`, иконка `Icons.delete_outline`) | CURRENT | UI-триггер удаления строки, без диалога подтверждения |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.delete` | CURRENT | эффект [EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md) — вызов `repository.delete` без `await` и без `try`/`catch`, затем `await loadNotSync()` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | перезагрузка списка после удаления, источник `AnimalWeighingsState.loadedNotSync` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState` (`initial`/`loading`/`loaded`/`loadedNotSync`) | CURRENT | нет отдельного error-варианта — исключение из `repository.delete` не может быть отражено в состоянии |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository` (не переопределяет `delete`), `getAllNotSuncAnimalWeighings` | CURRENT | `delete` — унаследованный `BaseRepository.delete`; `getAllNotSuncAnimalWeighings` — источник списка при перезагрузке |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | делегирует в `dao.del(item)` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — физическое удаление строки по первичному ключу |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` | CURRENT | `SELECT ... WHERE sync = 0` — источник списка и до, и после удаления |

## Критерии приёмки

- Тап по иконке удаления строки в `UnsentAnimalWeighingsPage` немедленно, без
  диалога подтверждения, вызывает `AnimalWeighingsCubit.delete` ровно один раз
  с `AnimalWeighing` этой строки.
- `delete(animalWeighing)` вызывает
  `AnimalWeighingsRepository.delete(animalWeighing)` ровно один раз с
  переданной строкой — но не дожидается результата этого вызова перед тем,
  как перейти к `loadNotSync()`.
- `delete(animalWeighing)` при любом исходе (в т.ч. если `Future` от
  `repository.delete` к этому моменту ещё не резолвился) доходит до `await
  loadNotSync()` и завершается вместе с ним — сценарий не виснет и не падает
  из-за неawait-нутого вызова.
- После завершения `delete(animalWeighing)` состояние кубита —
  `AnimalWeighingsLoadedNotSync` (получено через `loadNotSync()`), список в
  нём — актуальный результат `getAllNotSuncAnimalWeighings()` на момент этого
  запроса.
- Реальное (не замоканное) физическое удаление строки — Drift `DELETE` по
  первичному ключу `id`, не по `animalId` и не по составному совпадению
  прочих полей.

## Связанные тесты

- `test/pages/animal_weighings_cubit_test.dart`, group `'UC-87 —
  AnimalWeighingsCubit.delete (неотправленное)'` (старая нумерация,
  переименуется отдельным контролируемым проходом — не трогать сейчас), test
  `'успех -> repository.delete вызван, список перезагружен через
  loadNotSync'` — покрывает основной поток: `animalWeighingsRepository
  .delete(weighing)` (мокнутый) вызывается один раз, после `await
  cubit.delete(weighing)` состояние — `AnimalWeighingsLoadedNotSync`.
- Тот же файл, group `'UC-87 — AnimalWeighingsCubit.delete (находка — без
  await, без try/catch)'` (тоже старая нумерация), test `'cubit.delete()
  завершается, даже если Future от repository.delete() ещё не резолвился —
  вызов брошен'` — покрывает находку напрямую: `repository.delete` мокнут на
  never-resolving `Completer<int>().future`; `await cubit.delete(weighing)`
  тем не менее успешно завершается (`completes`), `deleteCompleter
  .isCompleted` остаётся `false` в момент этой проверки, и состояние уже —
  `AnimalWeighingsLoadedNotSync` — прямое доказательство того, что
  `loadNotSync()` не зависит от фактического завершения `repository.delete`.

## Открытые вопросы и ограничения

- **`AnimalWeighingsCubit.delete` не дожидается `repository.delete(...)` и не
  оборачивает его в `try`/`catch`.** Подтверждено тестом с `Completer`,
  описанным выше. Практическое следствие для реального (не замоканного)
  `AnimalWeighingsRepository`/Drift: код не даёт явной гарантии (`await`),
  что физическое удаление строки успело примениться к таблице раньше, чем
  `getAllNotSuncAnimalWeighings()` внутри последующего `loadNotSync()`
  прочитает её заново — то, что удалённая строка на практике не появляется
  в перезагруженном списке, зависит от порядка, в котором Drift
  сериализует операции на одном соединении/executor'е, а не от явной
  синхронизации в коде кубита. Заявить чтением одного только этого файла,
  гарантирован ли этот порядок при всех условиях (несколько параллельных
  вызовов `delete`, конкурентные операции с той же таблицей из другого
  места приложения в этот момент), нельзя — отдельный тест против настоящей
  (in-memory) БД, не мокнутого репозитория, отсутствует.
- **Исключение из `repository.delete` теряется молча.** Если `repository
  .delete(animalWeighing)` бросает исключение (например ошибка на уровне
  БД), это исключение никем не перехватывается: ни `cubit.delete` (нет
  `try`/`catch`), ни глобальный обработчик — `grep -rn` по `lib/` не находит
  ни `runZonedGuarded`, ни `PlatformDispatcher.instance.onError` нигде в
  приложении. У `AnimalWeighingsState` нет error-варианта в принципе
  (`initial`/`loading`/`loaded`/`loadedNotSync` — и всё), так что даже если
  бы исключение было поймано, отразить его в UI этого экрана сегодня
  нечем. Пользователь в любом случае увидит только перезагруженный список
  (шаг 7 основного потока) без какого-либо сообщения об ошибке удаления.
- Этот же метод (`delete`) не проверяет, что переданная строка
  действительно всё ещё `sync == false` на момент вызова — безопасность
  целиком опирается на то, что она пришла из уже отфильтрованного списка
  `loadedNotSync` (тот же паттерн, что и в `deleteById` вакцинаций, см.
  [UC-67](UC-67-ACTOR-5-EVT-34-ENT-14-DELETE_OK-IN-ANIMAL.md)); отдельно не
  проверено тестом для этой сущности.
