- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)

# UC-102 — Удаление группы неотправленных выбытий отказывает: `UnsentDisposalsCubit.deleteGroup` перехватывает исключение молча, без пользовательского сообщения об ошибке

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `DELETE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md)
(`disposal.deleted_unsent`): пользователь удаляет карточку-группу ещё не
отправленных записей выбытия с экрана хаба «неотправленных», и вызов
репозитория, удаляющий одну из записей группы, бросает исключение.
`UnsentDisposalsCubit.deleteGroup` перехватывает это исключение общим
`try/catch` вокруг всего цикла, логирует его через `Talker` и завершается как
обычный успех — ни пользовательского сообщения об ошибке, ни изменения
состояния кубита для этого случая не существует. Экран, вызвавший удаление, не
дожидается результата `Future`, возвращаемого `deleteGroup`, поэтому даже если
бы кубит эмитил ошибочное состояние, наблюдать его было бы некому.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — действие доступно и гостю, и
авторизованному пользователю одинаково: хаб неотправленных выбытий не
проверяет статус авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает экран хаба неотправленных выбытий
   (`UnsentDisposalsPage` →
   `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart`),
   попадая туда с экрана «В работе» (`EventTileData` для `l10n.disposal` →
   `context.pushNamed2(Routes.unsentDisposals)`,
   `lib/pages/in_work/in_work_page.dart`). Маршрут зарегистрирован в
   `lib/pages/routes.dart` (`Routes.unsentDisposals` → `UnsentDisposalsPage`).
   `UnsentDisposalsPage.build` создаёт `BlocProvider(create: (context) =>
   UnsentDisposalsCubit()..load())`, дочерний виджет — `UnsentDisposalsView`.
2. `UnsentDisposalsView.build`
   (`lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_view.dart`)
   подписывается на `UnsentDisposalsCubit` через `BlocBuilder` и в состоянии
   `loaded(disposals)` рендерит `UnsentDisposalsPopulated`
   (`lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart`).
3. `UnsentDisposalsPopulated._groupByEvent` группирует
   `List<DisposalWithDetails>` в карточки `_DisposalEvent` по составному ключу
   `'${causeId}_${placeId}_$timeKey'` (`timeKey` — время до минуты,
   `DateFormat('HHmm')`, дата берётся из `d.disposal.date ?? d.disposal
   .createdAt ?? DateTime.now()`) — одна карточка представляет несколько
   записей `Disposal`, у которых совпадают причина выбытия, место и минута
   события.
4. Пользователь нажимает иконку удаления на карточке (`_DisposalEventCard`,
   `IconButton(icon: Icons.delete_outline, onPressed: onTapDelete)`), где
   `onTapDelete = () => onTapDelete(event.disposals)` — передаёт наверх весь
   список `DisposalWithDetails` этой карточки, без диалога подтверждения.
5. `UnsentDisposalsView` подключает этот колбэк напрямую к кубиту:
   `onTapDelete: context.read<UnsentDisposalsCubit>().deleteGroup` — вызов не
   оборачивается в `await`, `try/catch` или `.catchError(...)` на стороне
   виджета; `Future<void>`, возвращаемый `deleteGroup`, полностью игнорируется
   UI-слоем.
6. `UnsentDisposalsCubit.deleteGroup(disposals)`
   (`lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart`):
   ```dart
   Future<void> deleteGroup(List<DisposalWithDetails> disposals) async {
     try {
       for (final d in disposals) {
         await _disposalRepository.delete(d.disposal);
       }
     } catch (e) {
       getIt<Talker>().error('deleteGroup: error: $e');
     }
   }
   ```
   один `try/catch` оборачивает **весь** цикл — не отдельную итерацию.
7. `_disposalRepository.delete(...)` — `DisposalRepository`
   (`lib/repositories/disposal/disposal_repository.dart`) **не переопределяет**
   `delete`, поэтому вызов разрешается напрямую в базовую реализацию
   `BaseRepository<DisposalsDao, Disposal, $DisposalsTable>.delete`
   (`lib/repositories/base_repository.dart`) → `dao.del(item)` →
   `BaseDao.del` (`packages/sheep_farm_database/lib/entities/base_dao.dart`) =
   `deleteCurrent().delete(item)` — обычный Drift-вызов, без какого-либо
   отката связанных полей `Animal` (в отличие от `Movement`, у `Disposal` нет
   такого отката вообще — см. [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)).
8. В этом сценарии `dao.del(item)` бросает исключение — например ошибка
   Drift/SQLite, или исключение из мока в тесте (`Exception('db error')`).
9. Исключение всплывает из `_disposalRepository.delete(d.disposal)` внутри
   цикла `for` в `deleteGroup` и прерывает цикл — все элементы `disposals`,
   идущие в списке **после** упавшего, не проходят через `delete` вовсе, даже
   попытки не предпринимается.
10. `catch (e)` в `deleteGroup` перехватывает исключение и вызывает
    `getIt<Talker>().error('deleteGroup: error: $e')` — только сообщение
    исключения, без стектрейса. Исключение не перевыбрасывается (`rethrow`
    отсутствует) — `deleteGroup` возвращает нормально завершившийся
    `Future<void>`.
11. `UnsentDisposalsState`
    (`lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart`)
    — закрытый freezed-union из четырёх вариантов: `initial`, `loading`,
    `loaded(disposals)`, `empty`. Варианта для ошибки не существует вовсе —
    `deleteGroup` в принципе не может эмитить состояние-ошибку, даже если бы
    захотел.
12. Поскольку шаг 5 не дожидается `Future` от `deleteGroup`, а
    `UnsentDisposalsCubit` не эмитит после `deleteGroup` вообще ничего
    напрямую — единственный способ, которым экран узнаёт об изменении списка,
    это реактивная подписка в конструкторе кубита:
    `_disposalRepository.watchNotSyncDisposals().listen((_) => _reload())`,
    где `watchNotSyncDisposals` → `dao.watchAllNotSync()`
    (`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart`) —
    реактивный Drift-запрос по фильтру `sync == false`.
13. Итог: пользователь нажимает иконку удаления и не получает никакого
    сигнала о произошедшем сбое — ни снэкбара, ни индикации загрузки, ни
    изменения состояния экрана специально под ошибку. Единственное
    наблюдаемое пользователем следствие — карточка на экране может визуально
    измениться (см. «Альтернативные потоки», партиальное удаление) или
    остаться как есть, в зависимости от того, на каком элементе цикла
    произошёл сбой.

### Альтернативные потоки

- **Партиальное удаление группы.** Если исключение бросается не на первом
  элементе `disposals`, то предыдущие элементы группы к этому моменту уже
  успешно удалены отдельными `await`-вызовами (`delete` не обёрнут в общую
  Drift-транзакцию на уровне `deleteGroup`) — эти удаления не откатываются при
  последующем исключении. Реактивный `watchAllNotSync()` (шаг 12 основного
  потока) увидит изменившийся набор строк и вызовет `_reload()`, так что
  карточка на экране перерисуется с уменьшенным числом животных (`event
  .count`) или исчезнет вовсе, если удалились все её записи, кроме одной, на
  которой всё остановилось. Пользователь не может отличить этот случай от
  «удаление одной записи из группы было каким-то намеренным частичным
  действием» — сообщения об ошибке по-прежнему нет.
- **У `Disposal`, в отличие от `Movement`, нет отката связанных полей
  `Animal` вообще** — `DisposalRepository` не переопределяет `delete`, а
  создание/удаление записи `Disposal` никогда локально не меняет
  `Animal.placeId`/`disposed` (см. инвариант 6 в `.claude/rules/domain-model.md`
  и «Инварианты» [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md)). Поэтому
  здесь нет симметричного «Альтернативного потока» вроде рассинхронизации
  Animal/Movement, описанного в аналогичном use-case для перемещений — сбой
  удаления `Disposal` затрагивает только саму таблицу `Disposals`.
- **`load()`/`_reload()` кубита имеют собственный, независимый `try/catch`**
  (`UnsentDisposalsCubit.load`, `_reload`), который при ошибке репозитория
  эмитит `UnsentDisposalsState.empty()`, а не пробрасывает исключение выше.
  Это отдельный обработчик ошибок, не связанный с `deleteGroup`, — упомянут
  только как контраст: у `load`/`_reload` есть хоть какая-то (пусть и
  неточная — `empty` вместо специализированного «ошибка») реакция состояния,
  а у `deleteGroup` нет вовсе никакой.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — сегмент
  `ENT` имени файла; сущность, чьё удаление отказывает. При отказе строка
  (или её часть, для остальных элементов группы) остаётся в БД неудалённой.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — упомянута для
  контраста с симметричным сценарием у `Movement`: здесь `Animal` этим
  сценарием не затрагивается вовсе, ни при успехе, ни при отказе удаления.

### Бизнес-правила

- Один `try/catch` в `deleteGroup` оборачивает весь цикл, не итерацию —
  первое же исключение останавливает обработку всех оставшихся элементов
  группы без индивидуального отчёта по каждому.
- Перехваченное исключение только логируется (`Talker.error`, без
  стектрейса) и не пробрасывается — вызывающая сторона (`UnsentDisposalsView`)
  не может отличить успешное завершение группы от отказавшего технически,
  потому что оба случая возвращают один и тот же нормально завершившийся
  `Future<void>`.
- `UnsentDisposalsState` не содержит варианта для ошибки — архитектурно
  `deleteGroup` не имеет способа сообщить об отказе через состояние кубита,
  даже если бы вызывающий код дожидался результата.
- В отличие от `MovementReportRepository.delete`, `DisposalRepository.delete`
  — прямая базовая реализация без переопределения: нет никакого
  дополнительного шага (вроде отката `Animal.placeId`), который мог бы
  отказать «между» откатом и удалением строки — единственная точка отказа
  здесь — сам `dao.del(item)`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — обработчик полностью прослеживается чтением кода, включая факт,
что вызывающий UI не дожидается результата и не может среагировать на ошибку
в принципе. Единственный незакрытый разрыв — отсутствие теста на партиальное
удаление группы (когда исключение бросается не на первом элементе) —
зафиксирован в «Открытые вопросы и ограничения» и в «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/in_work/in_work_page.dart` | `EventTileData` для `l10n.disposal` (`onTap` → `context.pushNamed2(Routes.unsentDisposals)`) | CURRENT | точка входа — переход с экрана «В работе» |
| `lib/pages/routes.dart` | `Routes.unsentDisposals` (регистрация маршрута) | CURRENT | маршрут → `UnsentDisposalsPage` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/unsent_disposals_page.dart` | `UnsentDisposalsPage.build` | CURRENT | создаёт `UnsentDisposalsCubit()..load()` |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_view.dart` | `UnsentDisposalsView.build` (`onTapDelete: context.read<UnsentDisposalsCubit>().deleteGroup`) | CURRENT | подключает удаление карточки к кубиту без `await`/обработки результата |
| `lib/pages/animal_disposal/presentation/unsent_disposal/widgets/unsent_disposals_populated.dart` | `UnsentDisposalsPopulated._groupByEvent`, `_DisposalEventCard` (`IconButton(onPressed: onTapDelete)`) | CURRENT | группировка записей в карточку и кнопка удаления всей группы, без диалога подтверждения |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_cubit.dart` | `UnsentDisposalsCubit.deleteGroup` | CURRENT | цикл по группе, один `try/catch`, лог через `Talker`, без rethrow |
| `lib/pages/animal_disposal/cubit/unsent_disposal/unsent_disposals_state.dart` | `UnsentDisposalsState` (`initial`/`loading`/`loaded`/`empty`) | CURRENT | freezed-union без варианта ошибки |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository` (класс — не переопределяет `delete`) | CURRENT | использует базовую реализацию `BaseRepository.delete` без изменений |
| `lib/repositories/base_repository.dart` | `BaseRepository.delete` | CURRENT | `dao.del(item)` — единственная реализация `delete` для `Disposal` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.del` | CURRENT | `deleteCurrent().delete(item)` — реальный Drift-вызов, способный бросить исключение |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao.watchAllNotSync` | CURRENT | реактивный запрос, лежащий в основе `watchNotSyncDisposals`/`_reload` |

## Критерии приёмки

- При вызове `deleteGroup(disposals)`, если `DisposalRepository.delete`
  бросает исключение на любом элементе `disposals`, `deleteGroup` завершает
  свой `Future<void>` без исключения (`completes`, а не `throwsA(...)`).
- Исключение логируется ровно один раз через `getIt<Talker>().error(...)`.
- Ни один элемент `disposals`, идущий в списке после упавшего, не проходит
  через `DisposalRepository.delete` в рамках того же вызова `deleteGroup`.
- Ни в одном состоянии `UnsentDisposalsState`, ни в UI не появляется
  сообщение об ошибке — с точки зрения интерфейса результат неотличим от
  `DELETE_OK`, если ни одна запись не была успешно удалена, и от частичного
  `DELETE_OK`, если часть записей группы успела удалиться до сбоя.

## Связанные тесты

`test/pages/unsent_disposals_cubit_test.dart`, group `'UC-102 — UnsentDisposalsCubit.deleteGroup'` (старая нумерация, переименуется отдельным
контролируемым проходом — не трогать сейчас), test `'отказ -> залогировано
через Talker, исключение не пробрасывается'`: мок
`disposalRepository.delete(any())` бросает `Exception('db error')`, `await
expectLater(cubit.deleteGroup([_disposal()]), completes)` проверяет
отсутствие проброса, `verify(() => getIt<Talker>().error(any())).called(1)`
проверяет факт логирования. Тест вызывает `deleteGroup` со списком из **одного**
элемента (`_disposal()`) — соседний OK-тест того же файла, group `'UC-101 —
UnsentDisposalsCubit.deleteGroup'`, покрывает успешный путь (группа из двух
записей, `delete` вызывается дважды).

**TBD — теста нет** на партиальное удаление группы (список из нескольких
элементов, где исключение бросается не на первом) — существующий ERROR-тест
проверяет только группу из одного элемента, поэтому не демонстрирует, что
предыдущие успешно удалённые элементы группы остаются удалёнными, а
последующие — нет.

**TBD — теста нет** на уровне виджета/страницы (`UnsentDisposalsView`,
`UnsentDisposalsPopulated`) — весь существующий тест только на уровне кубита;
факт, что UI не дожидается `Future` от `deleteGroup` и поэтому не может
показать ошибку, выведен чтением кода `unsent_disposals_view.dart`, а не
отдельным виджет-тестом.

## Открытые вопросы и ограничения

- **Нет способа отличить полный успех, частичный успех и полный отказ
  `deleteGroup` ни в одном состоянии кубита, ни в UI.** Все три исхода
  возвращают один и тот же нормально завершившийся `Future<void>`, и
  единственная видимая пользователю обратная связь — косвенная, через
  реактивный пересчёт списка (`watchNotSyncDisposals`), а не через осознанный
  сигнал об ошибке.
- **Вызывающий UI не дожидается результата `deleteGroup` в принципе**
  (`onTapDelete: context.read<UnsentDisposalsCubit>().deleteGroup` без
  `await`) — даже если бы `UnsentDisposalsState` завтра получил вариант
  ошибки, текущий `_DisposalEventCard`/`UnsentDisposalsPopulated` не подписан
  на него никаким `BlocListener`/`BlocConsumer` в этом дереве виджетов, и
  потребовал бы отдельного изменения, не входящего в рамки этого
  документирующего прохода (TARGET == CURRENT).
- Нужно ли когда-либо сделать удаление группы атомарным (единая транзакция на
  всю группу с полным откатом при частичном отказе), и нужно ли добавлять
  вариант ошибки в `UnsentDisposalsState` с пользовательским сообщением —
  вопросы будущего TARGET-прохода, не разрешаются в рамках этой чисто
  документирующей задачи.
