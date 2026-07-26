# UC-86 — Правка взвешивания технически отказывает: `AnimalWeighingsRepository.update` бросает исключение, необработанное вплоть до диалога подтверждения (ERROR)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md) |
| Сущность | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md)
(`animal_weighing.edited`), когда `_animalWeighingsRepository.update(updated)`
внутри `WeighAnimalCubit.saveEditedWeighing` бросает исключение вместо того,
чтобы вернуть `false`. В отличие от [UC-49](UC-49-ACTOR-5-EVT-24-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)
(Animal), где оба технических исхода — `false` и исключение — перехватываются
одним и тем же `try/catch` и приводят к одному сообщению пользователю, здесь
такого `try/catch` нет вообще ни в самом `saveEditedWeighing`, ни в
вызывающем коде (`ConfirmEditWeighDialog._save`). Это тот же класс дефекта,
что и у ERROR-исхода записи нового взвешивания (событие [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md),
см. [UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)) —
исключение пробрасывается наружу необработанным на каждом уровне цепочки
вызовов.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения (гость и авторизованный — одинаково), правящий одну запись
взвешивания через `WeighAnimalCubit.saveEditedWeighing`. Сценарий достижим из
реального UI-пути: экран взвешивания (`WeighAnimalPage`) в режиме
редактирования → диалог подтверждения `ConfirmEditWeighDialog` → кнопка
«Сохранить» (см. «Основной поток», шаги 1–4).

## CURRENT

### Основной поток

1. Пользователь открывает `WeighAnimalPage` (`Routes.weighAnimal`) в режиме
   редактирования одного взвешивания — либо явно, передав `animalWeighingId`
   через `WeighAnimalPageArguments` (например, из хаба неотправленных), либо
   неявно: `animalId` передан без `animalWeighingId`, и
   `WeighAnimalCubit.initialize` через `_findTodayWeighing` сам находит
   взвешивание за сегодняшний день у этого животного (по любому
   `sync`-статусу) и заполняет `selectedAnimalWeighingId`. В обоих случаях
   `data.selectedAnimalWeighingId != null`, поэтому в
   `_WeighAnimalWeighingViewState` вычисляется `isEditMode == true`.
2. Пользователь меняет вес/единицу/отметку здоровья через
   `updateWeight`/`updateUnit`/`updateIsHealthy` — эти правки живут только в
   `state.data` (`WeighAnimalData`), ничего не пишут в БД.
3. Пользователь нажимает кнопку завершения → `onFinishTap`
   (`lib/pages/weigh_animal/pages/weigh_animal_page.dart`). Поскольку
   `isEditMode == true` и `cubit.hasEditChanges()` вернул `true` (сравнение
   текущих полей с закэшированным `_initialAnimalWeighing`), открывается
   `showDialog` с `ConfirmEditWeighDialog(onSave: cubit.saveEditedWeighing,
   onComplete: ...)`.
4. Пользователь нажимает «Сохранить» в диалоге (`BlackCircleButton`, `onTap:
   _save`, `enabled: !isSaving`). `_ConfirmEditWeighDialogState._save()`:
   `setState(() => isSaving = true)`, затем `final ok = await
   widget.onSave();` — то есть `await cubit.saveEditedWeighing()`. Никакого
   `try/catch` вокруг этого `await` нет.
5. Внутри `WeighAnimalCubit.saveEditedWeighing()`: guard-проверки проходят
   (`id`, `animal`, `weight` заданы), собирается `AnimalWeighingsCompanion
   updated` (тот же `id`, `animalId`, вес/юнит/дата/`sync: false`/`isHealthy`
   из текущего состояния и `_initialAnimalWeighing`), и вызывается `final ok
   = await _animalWeighingsRepository.update(updated);` — вся функция
   `saveEditedWeighing` целиком не содержит `try/catch`.
6. `AnimalWeighingsRepository` не переопределяет `update`, поэтому реально
   исполняется унаследованный `BaseRepository.update`
   (`lib/repositories/base_repository.dart`) → `dao.upd(item)` →
   `AnimalWeighingsDao` наследует `BaseDao.upd`
   (`packages/sheep_farm_database/lib/entities/base_dao.dart`) без
   переопределения → `updateCurrent().replace(item)` — обычный Drift
   `replace`, способный бросить исключение (ошибка драйвера/SQLite, закрытая
   БД, конфликт схемы и т.п.).
7. Исключение, брошенное на этом шаге, не перехватывается нигде по всей
   цепочке вызовов: ни в `saveEditedWeighing` (нет `try/catch`), ни в
   `_ConfirmEditWeighDialogState._save` (только проверка `if (!ok)` после
   `await`, тоже без `try/catch`). `Future`, возвращаемый `_save()`,
   завершается с ошибкой.
8. `_save` передан в `BlackCircleButton` как `onTap: _save` — обычный
   fire-and-forget колбэк (`VoidCallback`); вызывающий код не `await`-ит его
   `Future`. Ошибка становится необработанной асинхронной ошибкой на верхнем
   уровне: `lib/main.dart` не оборачивает `runApp` в `runZonedGuarded`/не
   назначает `PlatformDispatcher.instance.onError` — единственная
   существующая в коде обёртка такого рода, `runTalkerZonedGuarded(...)`,
   закомментирована. Исключение не логируется через `Talker` (в отличие от
   большинства методов `AnimalWeighingsRepository`, где ошибки API
   перехватываются и идут в `getIt<Talker>().handle(...)`) и не показывается
   пользователю никаким `SnackBar`/сообщением.
9. Побочный эффект в UI: `setState(() => isSaving = true)` (шаг 4) уже
   выполнился, а код после `await` (`setState(() { isSaving = false; isSaved
   = ok; })`, `if (!ok) Navigator.of(context).pop();`) никогда не
   выполняется — кнопка «Сохранить» остаётся задизейблена (`enabled:
   !isSaving` → `false`) до тех пор, пока пользователь не покинет диалог
   иначе. Единственный доступный выход — кнопка закрытия (крестик) в
   `CustomDialog.onClose`, которая доступна и активна независимо от
   `isSaving`/`isSaved`: поскольку `isSaved == false`, она просто вызывает
   `Navigator.of(context).pop()` — диалог закрывается, экран взвешивания не
   закрывается (`cubit.exit` не вызывается), введённые пользователем правки
   в форме сохраняются в `state.data` как есть.
10. Строка `AnimalWeighings` в БД фактически не меняется — Drift-вызов
    `replace` не завершился успешно; `_initialAnimalWeighing` в кубите тоже
    не обновляется (обновление происходит только внутри блока `if (ok)`,
    который в этом сценарии не достигается).
11. Повтора/backoff нет: пользователь может закрыть диалог (шаг 9) и снова
    нажать кнопку завершения — `onFinishTap` заново проверит
    `hasEditChanges()` (по-прежнему `true`, т.к. состояние не изменилось) и
    откроет новый `ConfirmEditWeighDialog`.

### Альтернативные потоки

- **OK-исход того же обработчика — не входит в этот сценарий.** Если `update`
  вернёт `true` без исключения, `_save` выполняет `setState(() { isSaving =
  false; isSaved = true; })`, диалог показывает экран успеха
  (`weight_data_saved` + Lottie-анимация), и по нажатию «Готово»/крестика
  вызывается `widget.onComplete(reloadParent: true)` → `cubit.exit(...)` —
  соседний, не документируемый здесь исход того же
  [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md).
- **`update` возвращает `false` без исключения** (например, строка с этим
  `id` уже удалена из таблицы `AnimalWeighings` до вызова) — технически иной
  путь того же кода: `ok == false` доходит до `_save` без исключения,
  `setState` после `await` выполняется штатно, диалог закрывается через
  `Navigator.of(context).pop()` (`if (!ok)`), без сообщения об ошибке
  пользователю и без отдельного экрана. Это не тот же дефект, что
  документируется здесь (нет необработанного исключения), и в этом файле не
  разбирается подробно.
- **`id`/`animal` не заданы** (`state.data.selectedAnimalWeighingId == null`
  или `state.data.selectedAnimal == null`) или `weight` не задан — гварды в
  начале `saveEditedWeighing` возвращают `false` до вызова репозитория;
  `_animalWeighingsRepository.update` вообще не вызывается. Не относится к
  ERROR-исходу, документируемому здесь (нет попытки записи, нет
  исключения).
- Отсутствие интернета не проверяется нигде в этой цепочке —
  `_animalWeighingsRepository.update` пишет исключительно локально (Drift/
  SQLite) и не требует сети; исключение, документируемое здесь, никак не
  связано с сетевым доступом.

### Связанные сущности

- [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing)
  — сущность, чью единственную строку сценарий пытается обновить; это же
  ENT-сегмент имени файла. При техническом отказе строка фактически не
  меняется.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  только (`state.data.selectedAnimal`, тип `AnimalWithDetails`) для
  `animalId` объекта `updated`; сам обработчик `saveEditedWeighing` животное
  не изменяет и не перечитывает.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — `unitId`, переносимый в `updated` из `state.data.selectedUnit`
  либо из `_initialAnimalWeighing.unitId`; справочник только читается, не
  меняется.

### Бизнес-правила

- `saveEditedWeighing` не содержит `try/catch` вокруг вызова
  `_animalWeighingsRepository.update` — единственная защита от сбоя записи,
  доступная во всей цепочке вызовов, отсутствует полностью (в отличие от
  `AnimalEditBloc.on<AnimalEditEventSave>`, см. [UC-49](UC-49-ACTOR-5-EVT-24-ENT-11-UPDATE_ERROR-IN-ANIMAL.md),
  где оба технических исхода перехватываются одним `catch`).
  `ConfirmEditWeighDialog._save` тоже не перехватывает исключение —
  единственная проверка в вызывающем коде — `if (!ok)` уже после успешного
  (без исключения) `await`.
- Никакого логирования исключения не происходит нигде в этой цепочке —
  ни `getIt<Talker>()`, ни `log(...)`, в отличие от большинства сетевых
  методов `AnimalWeighingsRepository` (`storeAnimalWeighingsToSHTP`,
  `singleSendAnimalWeighingToAPI` и т.п.), которые ловят и логируют ошибки
  API-вызовов через `getIt<Talker>().handle(e, stackTrace)`.
  `saveEditedWeighing` работает исключительно с локальным Drift-вызовом и не
  проходит ни через один из этих логирующих путей.
- Никакого отката и повтора: ни кубит, ни диалог не восстанавливают и не
  меняют состояние при ошибке — единственный способ выйти из зависшего
  состояния диалога (кнопка «Сохранить» задизейблена навсегда) — кнопка
  закрытия (крестик), всегда активная независимо от `isSaving`.
- `_initialAnimalWeighing` (используемый `hasEditChanges` для последующих
  сравнений) обновляется только внутри блока `if (ok)` внутри
  `saveEditedWeighing` — при исключении этот блок не достигается, локальный
  кэш кубита остаётся прежним.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено дополнительно к найденному дефекту (отсутствие `try/catch` на
обоих уровнях цепочки вызовов) — сценарий полностью прослеживается в
существующем коде; сам дефект зафиксирован как факт CURRENT, не как то, что
исправляется в рамках этого документирующего прохода.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `WeighAnimalPage`, `WeighAnimalPageArguments` | CURRENT | точка входа экрана; читает аргументы маршрута, создаёт `WeighAnimalCubit`, вызывает `initialize` |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `_WeighAnimalWeighingViewState.onFinishTap` | CURRENT | вычисляет `isEditMode`, при `hasEditChanges() == true` открывает `showDialog(ConfirmEditWeighDialog)` |
| `lib/pages/weigh_animal/pages/weigh_animal_page.dart` | `ConfirmEditWeighDialog`, `_ConfirmEditWeighDialogState._save` | CURRENT | вызывающий код без `try/catch`; `await widget.onSave()` без обработки исключения, только `if (!ok)` после успешного возврата |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveEditedWeighing` | CURRENT | строит `AnimalWeighingsCompanion`, вызывает `repository.update` без `try/catch` вокруг вызова |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.hasEditChanges`, `initialize`, `_findTodayWeighing` | CURRENT | gate, решающий, показывать ли диалог правки; автоопределение режима правки при инициализации |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository` (`extends BaseRepository<AnimalWeighingsDao, AnimalWeighing, $AnimalWeighingsTable>`) | CURRENT | не переопределяет `update` — используется унаследованная реализация |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` — без `try/catch`, точка, откуда всплывает исключение |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — Drift-вызов, источник возможного исключения |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao` | CURRENT | конкретный DAO взвешивания, наследующий `BaseDao.upd` без переопределения |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings`, `AnimalWeighing` | CURRENT | таблица/модель, чью единственную строку сценарий пытается обновить |
| `lib/widgets/custom_dialog/custom_dialog.dart` | `CustomDialog` | CURRENT | кнопка закрытия (крестик), активная независимо от `isSaving`/`isSaved` — единственный доступный выход из зависшего диалога |
| `lib/widgets/button/button.dart` | `BlackCircleButton` (`onTap` типа `VoidCallback`) | CURRENT | принимает `_save` (`Future<void> Function()`) как fire-and-forget колбэк, не `await`-ит его `Future` |
| `lib/main.dart` | `main`, `MyApp` | CURRENT | `runApp` не обёрнут в `runZonedGuarded`/`PlatformDispatcher.instance.onError`; единственная такая обёртка (`runTalkerZonedGuarded`) закомментирована — необработанная асинхронная ошибка не логируется и не показывается пользователю |

## Критерии приёмки

- Если `_animalWeighingsRepository.update` бросает исключение внутри
  `WeighAnimalCubit.saveEditedWeighing`, ни один `try/catch` в коде проекта
  (ни в `saveEditedWeighing`, ни в `ConfirmEditWeighDialog._save`) его не
  перехватывает — `Future`, возвращаемый `saveEditedWeighing()`, и `Future`,
  возвращаемый `_save()`, оба завершаются с ошибкой (`throwsA(...)`, а не
  `completes` с булевым значением).
- Кубит не эмитит `state.error` и не показывает пользователю никакого
  сообщения в этом сценарии — `BlocListener` в `weigh_animal_page.dart`,
  реагирующий на `curr.error != null`, не срабатывает, потому что
  исключение никогда не доходит до какого-либо `emit`/`catch` внутри кубита.
- В диалоге `ConfirmEditWeighDialog` состояние `isSaving == true`,
  выставленное перед вызовом `onSave`, не сбрасывается обратно в `false` —
  кнопка «Сохранить» остаётся задизейблена; кнопка закрытия (крестик)
  остаётся доступной и по нажатию закрывает диалог без сохранения.
- Строка `AnimalWeighing` в БД не меняется; `_initialAnimalWeighing` в
  кубите не обновляется (блок синхронизации внутри `if (ok)` не
  достигается).
- Факт отсутствия `try/catch` на обоих уровнях цепочки — часть текущего,
  подтверждённого чтением кода поведения; не критерий для исправления в
  рамках этого документирующего прохода (TARGET == CURRENT).

## Связанные тесты

TBD — теста нет. `test/pages/weigh_animal_cubit_test.dart` содержит группу
`group('UC-85 — WeighAnimalCubit.hasEditChanges/saveEditedWeighing', ...)`
(идентификатор `UC-115` — устаревшая нумерация, будет переименована отдельным
проходом позже, не трогать сейчас) с тестами на guard-ветку (`id`/`animal` не
заданы) и на успешный исход (`update` отвечает `true`), но ни один
существующий тест не мокает `animalWeighingsRepository.update` так, чтобы он
бросал исключение — сценарий, документируемый здесь, кодом тестов не
покрыт.

## Открытые вопросы и ограничения

- **Полное отсутствие обработки ошибок по всей цепочке вызовов.** В отличие
  от `AnimalEditBloc` ([UC-49](UC-49-ACTOR-5-EVT-24-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)),
  где хотя бы один уровень (`try/catch` в блоке) перехватывает исключение и
  показывает пользователю сообщение, здесь ни `saveEditedWeighing`, ни
  `ConfirmEditWeighDialog._save` не перехватывают ничего — пользователь не
  получает никакого сообщения об ошибке, а диалог зависает в состоянии
  «сохранение», пока не будет закрыт вручную через крестик. Фиксируется как
  факт текущего кода, не разрешается в рамках этого документирующего
  прохода.
- **Ошибка становится необработанной асинхронной ошибкой уровня приложения.**
  Поскольку `_save` вызывается как обычный `onTap`-колбэк без `await` со
  стороны `BlackCircleButton`, а `main.dart` не настраивает
  `runZonedGuarded`/`PlatformDispatcher.instance.onError`, исключение не
  попадает ни в один лог/крашрепортинг проекта (`Talker` в частности) — оно
  просто нигде не фиксируется. Тот же класс проблемы, что у
  [UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)
  (`saveWeighing`/`ConfirmSaveWeighDialog`).
- Различение причины отказа («строка удалена до вызова» → `false` без
  исключения, vs «техническая ошибка БД/платформы» → исключение) не
  делается нигде по стеку — оба технических исхода из «Основного потока» и
  «Альтернативных потоков» неотличимы для пользователя (ни один не
  показывает сообщение), но ведут себя по-разному внутри `_save`
  (исключение зависает диалог, `false` штатно закрывает его). Фиксируется
  как факт текущего кода.
