# UC-88 — Удаление неотправленного взвешивания из хаба «В работе» технически отказывает: `repository.delete` не await-ится и не обёрнут в `try/catch` — рождается необработанное (unhandled) исключение, не пойманное вообще нигде в коде

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md)
(`animal_weighing.deleted_unsent`): пользователь удаляет ещё не отправленное
взвешивание [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) с экрана
хаба «В работе», и вызов репозитория, отвечающий за само удаление строки,
завершается отказом — Future, которую он возвращает, отклоняется (Drift/SQLite
ошибка на реальном `DELETE`-запросе).

Это не просто «ошибка проглочена молча» (как в соседних ERROR-документах MOVE,
см. [UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md) и
[UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md), где хотя бы
есть `try/catch`, пусть даже пустой или только с логированием). Здесь
`AnimalWeighingsCubit.delete` вообще не оборачивает вызов удаления ни в
`await`, ни в `try/catch` — отклонённая Future не присваивается переменной, не
передаётся в `.then`/`.catchError`, никем не наблюдается. Это превращает её в
классическое необработанное асинхронное исключение (unhandled rejection) в
терминах Dart: оно не долетает до `catch`-блока этого метода вообще, потому
что метод даже не пытается на неё посмотреть. Соседний, парный OK-исход того
же метода (успешное удаление) описывается отдельным use-case-документом того
же события — на момент написания этого файла он в дереве `sdlc/2-specs/` ещё
не существует, поэтому здесь не цитируется markdown-ссылкой (см. «Открытые
вопросы»).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково, хаб «В работе» не проверяет
статус авторизации), удаляющий строку неотправленного взвешивания прямо со
своего экрана в хабе.

## CURRENT

### Основной поток

1. **Точка входа.** Пользователь открывает хаб «В работе»
   (`InWorkPage`/`InWorkBloc`, `lib/pages/in_work/in_work_page.dart`) и
   тапает по плитке «Взвешивание» (`EventTileData(... value: l10n.weighing,
   count: data.animalWeighingsCount, onTap: () =>
   context.pushNamed2(Routes.unsentAnimalWeighings))`).
2. Открывается `UnsentAnimalWeighingsPage`
   (`lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart`),
   зарегистрированная в `lib/pages/routes.dart` под именем
   `Routes.unsentAnimalWeighings`. `BlocProvider` создаёт
   `AnimalWeighingsCubit()..loadNotSync()` — список неотправленных
   взвешиваний загружается один раз при открытии экрана, не как реактивный
   `watch`-поток.
3. В состоянии `AnimalWeighingsLoadedNotSync` рендерится
   `AnimalWeighingListNotSyncWidget`
   (`lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart`),
   которому передаётся `onTapDel: context.read<AnimalWeighingsCubit>().delete`
   — прямое связывание, без обёртки `await`/`try` на стороне страницы.
4. Внутри `AnimalWeighingListNotSyncWidget` каждая строка — `_WeighingCard` с
   `GestureDetector(onTap: onDelete, child: Icon(Icons.delete_outline, ...))`,
   где `onDelete = () => onTapDel(animalWeighings[index].animalWeighing)`.
   Тип поля `onTapDel` — `void Function(AnimalWeighing animalWeighing)`, то
   есть синхронный `VoidCallback`-подобный колбэк: `Future<void>`, реально
   возвращаемая `cubit.delete(...)`, отбрасывается уже на этой границе —
   ни `GestureDetector`, ни `_WeighingCard`, ни сам виджет-список не видят её
   вообще, ни в успешном, ни в отказавшем случае.
5. Пользователь нажимает иконку удаления. Вызывается
   `AnimalWeighingsCubit.delete` (`lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart`):
   ```dart
   Future<void> delete(AnimalWeighing animalWeighing) async {
     _animalWeightingsRepository.delete(animalWeighing);

     await loadNotSync();
   }
   ```
   Вызов `_animalWeightingsRepository.delete(animalWeighing)` **не
   await-ится** (отсутствует ключевое слово `await`) и не оборачивается ни в
   `try`, ни в `.catchError(...)` — возвращаемая им `Future<int>` ни разу не
   присваивается переменной и никем не удерживается.
6. `AnimalWeighingsRepository` не переопределяет `delete` — вызывается
   базовая реализация `BaseRepository<AnimalWeighingsDao, AnimalWeighing,
   $AnimalWeighingsTable>.delete` (`lib/repositories/base_repository.dart`):
   `Future<int> delete(Insertable<D> item) => dao.del(item);` — которая, в
   свою очередь, вызывает `BaseDao.del`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`):
   `Future<int> del(Insertable<D> item) => deleteCurrent().delete(item);` —
   реальный Drift `DELETE`-запрос к `NativeDatabase`.
7. **Технический отказ.** Реальный `DELETE`-запрос отклоняется (например,
   ошибка Drift/SQLite: занятое соединение, повреждённая БД, нарушение
   ограничения и т. п.). Поскольку весь путь от шага 5 до этого запроса не
   содержит ни одного `await`/`catchError` со стороны `AnimalWeighingsCubit.delete`,
   отклонение этой `Future<int>` никем не наблюдается: оно не поднимается по
   стеку вызовов `delete()` (метод к этому моменту уже перешёл к следующей
   строке своего тела — `await loadNotSync()` — не дожидаясь исхода
   предыдущего вызова), не попадает ни в один `catch`, не логируется через
   `Talker`/`log`. Формально это — необработанное асинхронное исключение
   (unhandled rejection): текущая Zone-обвязка Dart (в приложении нет ни
   `runZonedGuarded`, ни переопределения `FlutterError.onError`/
   `PlatformDispatcher.instance.onError` — проверено поиском по всему `lib/`,
   совпадений нет) в лучшем случае выведет его в консоль/лог как
   неатрибутированную ошибку, не привязанную ни к какому пользовательскому
   действию, ни к экрану, ни к сущности — диагностировать причину постфактум
   по логам практически невозможно; никакого механизма отправки в
   crash-репортинг для этого пути тоже не настроено.
8. Независимо от исхода шага 7, `await loadNotSync()` (тот же файл,
   `AnimalWeighingsCubit.loadNotSync`) выполняется безусловно: заново читает
   `getAllNotSuncAnimalWeighings()`, обогащает каждую строку данными животного
   и единицы измерения, сортирует по дате и эмитит
   `AnimalWeighingsState.loadedNotSync`. Поскольку реального удаления не
   произошло (`DELETE` отклонён), тапнутая строка возвращается в списке как
   есть — визуально экран выглядит так, будто ничего не произошло: ни
   снэкбара, ни индикатора ошибки, ни изменения состояния кубита,
   специфичного для отказа (`AnimalWeighingsState` — закрытый freezed-union
   всего из четырёх вариантов: `initial`/`loading`/`loaded`/`loadedNotSync`,
   варианта ошибки не существует архитектурно).
9. Поскольку `loadNotSync()` — одноразовый снимок (`Future`-based
   `getAllNotSuncAnimalWeighings()`), а не реактивный Drift `watch()`, список
   на экране больше не обновится сам собой — даже если бы отклонённый на шаге
   7 `DELETE` каким-то образом всё же довыполнился чуть позже (после того как
   `loadNotSync()` уже прочитал старые данные), строка осталась бы видна на
   экране до следующего явного перезапроса (повторное открытие экрана,
   ручное удаление ещё раз и т. п.).

### Альтернативные потоки

- **OK-исход того же метода — не входит в этот документ.** Если Future,
  возвращаемая `_animalWeightingsRepository.delete(animalWeighing)`, разрешается
  успешно (строка реально удаляется), наблюдаемое пользователем поведение на
  шаге 8 отличается только фактическим содержимым перечитанного списка
  (строки больше нет) — само же отсутствие какой-либо обратной связи об
  успехе (нет снэкбара `showAppSnackBarSuccess` и т. п.) идентично описанному
  здесь отказу. Описывается отдельным use-case-документом того же события —
  см. «Открытые вопросы».
- **Гипотетический синхронный throw до какого-либо `await`.** Если исключение
  бросается синхронно внутри цепочки `BaseRepository.delete` →
  `BaseDao.del` → `deleteCurrent().delete(item)` ещё до того, как
  Drift-исполнитель успевает вернуть управление в event loop (маловероятно
  для реального `NativeDatabase`, но не исключено для мок-реализаций в
  тестах или при программной ошибке в самом вызове), то, поскольку
  `AnimalWeighingsCubit.delete` объявлен как `async`, этот синхронный throw
  перехватывается инфраструктурой `async`/`await` самого Dart и превращается
  в отклонённую `Future<void>`, которую возвращает уже сам `cubit.delete(...)`
  — то есть отказ «переезжает» с внутренней Future репозитория на внешнюю
  Future метода кубита. Итог для пользователя не меняется: эта внешняя Future
  тоже отбрасывается на шаге 4 (`void Function(AnimalWeighing) onTapDel`),
  тем же самым способом, тем же самым «fire-and-forget»-вызовом — просто
  необработанное исключение материализуется на другом объекте `Future`,
  видимо для одного и того же наблюдателя (никого).
- **Более полная параллель — `AnimalWeighingsCubit.deleteImmediate`.**
  Соседний метод того же класса (удаление уже синхронизированного
  взвешивания, недостижимый ни с одного экрана — см.
  [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md)) хотя бы
  оборачивает свой вызов `deleteByIdFromAPI` в `try/catch` с логированием
  через `getIt<Talker>().error(...)`. Метод `delete`, описываемый в этом
  документе — единственный из двух методов удаления в этом классе, где даже
  такого минимального перехвата нет вообще.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing) —
  сущность, чьё удаление технически отказывает; это же `ENT`-сегмент имени
  файла. Строка остаётся в таблице `AnimalWeighings` неудалённой.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — не изменяется
  этим сценарием напрямую (в отличие от Movement, удаление взвешивания не
  откатывает никакое поле животного), но читается заново для каждой строки
  внутри безусловного `loadNotSync()` (шаг 8, `getAnimalWithDetailsById`) —
  часть перечитанного списка, показанного пользователю после отказавшей
  попытки удаления.

### Бизнес-правила

- `_animalWeightingsRepository.delete(animalWeighing)` вызывается без `await`
  и без какой-либо обработки ошибки — единственный из всех документированных
  на сегодня ERROR-путей DELETE в модуле ANIMAL, где нет вообще никакого
  перехвата (ни `try/catch`, ни `.catchError`), а не просто перехвата без
  логирования/сообщения.
- `await loadNotSync()` выполняется безусловно сразу после вызова удаления —
  не зависит от того, успел ли реально завершиться (тем более — успешно
  завершиться) вызов `delete(animalWeighing)` к этому моменту.
- `AnimalWeighingsState` не содержит варианта ошибки — архитектурно
  `AnimalWeighingsCubit.delete` не может сообщить об отказе через состояние,
  даже если бы её `try/catch` появился.
- Правило проекта показывать ошибки через `lib/widgets/app_snackbar.dart`
  (`.claude/rules/ui-architecture.md`) в этом методе не применяется вовсе — ни
  при отказе, ни при успехе; ни сам метод, ни вызывающий UI не производят
  никакой обратной связи об исходе операции удаления.
- В приложении нет глобального обработчика необработанных асинхронных ошибок
  (`runZonedGuarded`, `FlutterError.onError`, `PlatformDispatcher.instance.onError`) —
  проверено поиском по всему `lib/`, совпадений нет — поэтому отклонение
  Future на шаге 7 не перехватывается ничем даже на уровне всего приложения,
  не только этого метода.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено с точки зрения прослеживаемости кода — отсутствие `await`/
`try/catch` в `AnimalWeighingsCubit.delete` и отсутствие глобального
обработчика необработанных ошибок в приложении полностью подтверждены чтением
кода. Единственный практический разрыв — тест, который бы напрямую
воспроизвёл реальное отклонение/исключение `repository.delete()` (а не только
факт «Future не дожидается»), написать безопасно затруднительно текущими
средствами тестовой инфраструктуры — см. «Связанные тесты» и «Открытые
вопросы».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `InWorkPage` (плитка `EventTileData(value: l10n.weighing, onTap: () => context.pushNamed2(Routes.unsentAnimalWeighings))`) | CURRENT | точка входа: переход в хаб неотправленных взвешиваний из хаба «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentAnimalWeighings` | CURRENT | константа маршрута, регистрация `UnsentAnimalWeighingsPage` в `go_router` |
| `lib/pages/animal_weighings/pages/unsent_animal_weighings_page.dart` | `UnsentAnimalWeighingsPage.build` (`create: (context) => AnimalWeighingsCubit()..loadNotSync()`, `onTapDel: context.read<AnimalWeighingsCubit>().delete`) | CURRENT | точка входа экрана хаба; связывает удаление строки напрямую с методом кубита, без `await`/обработки результата |
| `lib/pages/animal_weighings/widgets/animal_weighing_list_not_sync_widget.dart` | `AnimalWeighingListNotSyncWidget`, `_WeighingCard` (`onDelete`, `GestureDetector(onTap: onDelete)`) | CURRENT | синхронная цепочка тапа: `VoidCallback`-подобный колбэк отбрасывает `Future<void>`, возвращаемую `cubit.delete(...)` |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.delete` | CURRENT | не await-ит и не оборачивает в `try/catch` вызов `_animalWeightingsRepository.delete`; безусловно вызывает `loadNotSync()` следом |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.loadNotSync` | CURRENT | безусловный перезапрос списка сразу после (не дожидаясь) вызова удаления |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_state.dart` | `AnimalWeighingsState` (`initial`/`loading`/`loaded`/`loadedNotSync`) | CURRENT | закрытый freezed-union без варианта ошибки |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository` | CURRENT | не переопределяет `delete` — реально вызывается базовая реализация |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | `dao.del(item)` — реализация, унаследованная `AnimalWeighingsRepository` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — реальный Drift `DELETE`-запрос, источник отказа |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings` | CURRENT | запрос, лежащий в основе безусловного перечитывания на шаге 8 |

## Критерии приёмки

- При вызове `AnimalWeighingsCubit.delete(animalWeighing)`, если Future,
  возвращаемая `_animalWeightingsRepository.delete(animalWeighing)`, отклоняется
  (или ещё не разрешилась к моменту завершения `delete(...)`), сам вызов
  `delete(animalWeighing)` тем не менее завершается нормально (`completes`, а
  не `throwsA(...)`) — потому что метод никогда не дожидается этой Future и
  не может увидеть её отказ.
- Ни один вызов `Talker`/`log`/иного логирования не происходит внутри
  `AnimalWeighingsCubit.delete` — в методе нет `try/catch`, соответственно нет
  и точки, где такой вызов мог бы находиться.
- `loadNotSync()` вызывается и успешно эмитит `AnimalWeighingsLoadedNotSync`
  независимо от того, что произошло (или ещё не произошло) с Future от
  `_animalWeightingsRepository.delete(...)`.
- Ни в одном варианте `AnimalWeighingsState`, ни в UI не появляется сообщение
  об ошибке — с точки зрения интерфейса результат неотличим от `DELETE_OK`
  (см. основной поток, шаг 8).

## Связанные тесты

`test/pages/animal_weighings_cubit_test.dart`, group `'UC-87 —
AnimalWeighingsCubit.delete (находка — без await, без try/catch)'`
(переименуется отдельным контролируемым проходом позже, не трогать сейчас),
test `'cubit.delete() завершается, даже если Future от repository.delete() ещё
не резолвился — вызов брошен'`: мок `animalWeighingsRepository.delete(any())`
настроен возвращать `Future`, привязанную к незавершённому `Completer<int>`;
тест проверяет `await expectLater(cubit.delete(weighing), completes)` и явно
утверждает `deleteCompleter.isCompleted == false` после этого — то есть
`cubit.delete()` завершился, не дождавшись внутренней Future репозитория. Это
прямое, хоть и косвенное (через незавершённый, а не отклонённый `Completer`)
доказательство корневой причины этого сценария: отсутствие `await`.

**TBD — теста нет** на собственно отклонённую/брошенную Future
`repository.delete(...)` (то есть на настоящий ERROR, а не только на «Future
ещё не резолвилась»). Ни один существующий тест не настраивает
`animalWeighingsRepository.delete(any())` через `thenThrow(...)` или через
`Completer.completeError(...)`. Это не случайный пробел: поскольку вызов
внутри `AnimalWeighingsCubit.delete` не await-ится и не оборачивается,
по-настоящему отклонённая (`completeError`) или синхронно бросающая
(`thenThrow`) Future стала бы **реальным** необработанным асинхронным
исключением уже внутри самого тестового прогона (`flutter_test`
перехватывает такие ошибки через собственную guarded-зону и обычно
атрибутирует их как падение теста, в котором произошёл асинхронный сбой, — не
обязательно того `test()`, где стоит вызов) — то есть написание такого теста
«в лоб» рискует либо завалить сам тестовый файл, либо дать ложно-зелёный
результат с шумом в логах, не проверив ничего содержательного сверх уже
существующего теста на незавершённый `Completer`. Именно поэтому существующий
тест обходит это через никогда не завершаемый `Completer`, а не через реальное
отклонение.

## Открытые вопросы и ограничения

- **Это самый серьёзный класс ERROR-обработки среди документированных на
  сегодня DELETE-сценариев модуля ANIMAL.** У соседних ERROR-исходов MOVE
  ([UC-57](UC-57-ACTOR-5-EVT-28-ENT-13-DELETE_ERROR-IN-ANIMAL.md),
  [UC-59](UC-59-ACTOR-5-EVT-29-ENT-13-DELETE_ERROR-IN-ANIMAL.md)) исключение
  хотя бы попадает в `catch`-блок (иногда пустой, иногда с логированием) —
  оно физически перехвачено, просто ничего полезного с ним не делается.
  Здесь же исключение вообще не встречает `try` на своём пути — это
  качественно иной, более серьёзный дефект: необработанное асинхронное
  исключение, а не проглоченное синхронное. Зафиксировано как факт CURRENT,
  не исправляется в рамках этого документирующего прохода (TARGET ==
  CURRENT).
- **Парный OK-исход того же метода (`animal_weighing.deleted_unsent` /
  `DELETE_OK`) на момент написания этого файла ещё не задокументирован
  отдельным use-case (`UC-87-ACTOR-5-EVT-44-ENT-15-DELETE_OK-IN-ANIMAL.md` в
  дереве `sdlc/2-specs/use-cases/` не найден).** Ссылка на него в этом
  документе намеренно дана простым текстом, не markdown-ссылкой — по правилу
  «новый артефакт цитирует только живые id» (`sdlc/AGENTS.md`, «New artifacts
  cite live ids only»). Как только этот файл появится, стоит добавить
  на него ссылку из «Назначения» и из «Альтернативных потоков» этого
  документа отдельной, контролируемой правкой (это разрешено — обновление
  цитаты на новый живой id не изменяет содержательного смысла уже написанных
  разделов).
- **Нет теста, напрямую воспроизводящего отклонённую/брошенную
  `repository.delete(...)`**, и по изложенной выше причине (риск реального
  unhandled exception внутри тестового прогона) написание такого теста
  безопасными средствами текущей инфраструктуры (`mocktail` + `flutter_test`)
  нетривиально — потребовало бы либо собственной guarded-зоны вокруг вызова,
  либо проверки через `FlutterError.onError`/`PlatformDispatcher.instance.onError`,
  ни один из которых сейчас не настроен ни в тестовом хелпере, ни в
  приложении. Вопрос, нужно ли писать такой тест (и как сделать это
  безопасно), не решается в рамках этого документирующего прохода.
- **Нужно ли вообще чинить это (`await` + `try/catch` + пользовательское
  сообщение об ошибке) — вопрос будущего TARGET-прохода**, не разрешается
  здесь: этот документ фиксирует только то, что есть в коде сегодня.
