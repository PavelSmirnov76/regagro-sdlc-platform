# UC-175 — Сохранение видимости видов животных: необработанное исключение в `updateAll` делает нажатие «Сохранить» незаметным no-op

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же триггер, что описан в [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) —
пользователь на экране `KindsVisibilitySettingsPage` переключает видимость
видов животных и нажимает «Сохранить» (`KindsVisibilitySettingsCubit.save()`).
Здесь описана ветка, где бизнес-правило «хотя бы один вид видим» **пройдено**
(в отличие от [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md),
где отказ происходит раньше, до какого-либо обращения к репозиторию) —
`_kindsRepository.updateAll(state.kinds)` реально вызывается, и именно этот
вызов заканчивается технической ошибкой: исключение из Drift/sqlite3 внутри
батч-обновления `Kinds.visible`.

Проверено чтением всей цепочки: ни `KindsVisibilitySettingsCubit.save()`, ни
`KindsRepository` (не переопределяет `updateAll`), ни `BaseRepository.updateAll`,
ни `KindsDao` (не переопределяет `updAll`), ни `BaseDao.updAll` не оборачивают
этот вызов в `try/catch` — исключение всплывает необработанным до самого
вызывающего кода. А вызывающий код — `onTap: () {
context.read<KindsVisibilitySettingsCubit>().save(); }`
(`kinds_visibility_settings_page.dart`) — не `await`-ит и не перехватывает
возвращённый `Future<void>` вовсе. Итог принципиально отличается от уже
задокументированного `READ_ERROR` того же кубита
([UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md), метод
`load()`, где кубит успевает эмитить `loading` до отказа и застревает на
видимом бесконечном спиннере): здесь `save()` не эмитит вообще ничего до
строки, которая бросает исключение, поэтому состояние кубита не меняется
ни на йоту — пользователь не видит ни спиннера, ни снэкбара, ни какого-либо
признака того, что нажатие вообще было обработано. Кнопка «Сохранить»
выглядит так, будто нажатие было полностью проигнорировано.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
гость или авторизованный одинаково (маршрут без route-guard по авторизации,
как и весь [MOD-6](../modules/MOD-6-PROFILE.md); точка входа —
`WorkSettingsItem` в `WorkSettingsPage`, открытой с кнопки «Настройки» в
`ProfileView` — ни один из двух уровней навигации не проверяет авторизацию,
см. подробную проверку в [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)).
Полный путь маршрута — `/profile/work_settings/kinds_visibility_settings`
(`Routes.profile` → `Routes.workSettings` → `Routes.kindsVisibilitySettings`,
`lib/pages/routes.dart`).

## CURRENT

### Основной поток

1. Пользователь открывает «Видимость видов животных» —
   `KindsVisibilitySettingsPage.build()` создаёт `BlocProvider(create:
   (context) => KindsVisibilitySettingsCubit()..load())`. `load()` читает все
   `Kind` (`_kindsRepository.getAll()`), сортирует по имени, эмитит
   `KindsVisibilitySettingsState.loaded(kinds: kinds)` (дважды подряд,
   безобидный копипаст — см. [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md)).
   В этом сценарии чтение проходит успешно.
2. Пользователь переключает один или несколько видов
   (`toggleKindVisibility`/`toggleAllKindsVisibility` — чисто in-memory,
   эмитят новый `loaded(kinds: updatedKinds)`, репозиторий не вызывается ни
   разу), оставляя **хотя бы один** вид видимым.
3. Пользователь нажимает `RElevatedButton` «Сохранить»
   (`floatingActionButton` страницы) →
   `onTap: () { context.read<KindsVisibilitySettingsCubit>().save(); }` —
   вызов **не `await`-ится**: это синхронный `void`-колбэк, вызывающий
   асинхронный метод и отбрасывающий возвращённый `Future<void>`.
4. `KindsVisibilitySettingsCubit.save()`
   (`lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart`):
   `if (!state.kinds.any((e) => e.visible))` — ложно (хотя бы один вид
   видим), ветка отказа (`emit(failure(...))`, [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md))
   не выполняется. Управление переходит к `await
   _kindsRepository.updateAll(state.kinds);` — **единственной** оставшейся
   строке метода перед `emit(saved(...))`.
5. `KindsRepository.updateAll` не переопределён — вызов уходит в
   унаследованный `BaseRepository<KindsDao, Kind,
   $KindsTable>.updateAll(list)` (`lib/repositories/base_repository.dart`) →
   `dao.updAll(list)`.
6. `KindsDao` (`packages/sheep_farm_database/lib/entities/kind/kinds_dao.dart`)
   тоже не переопределяет `updAll` — вызов уходит в
   `BaseDao.updAll` (`packages/sheep_farm_database/lib/entities/base_dao.dart`):
   `transaction(() async { for (final i in list) { await upd(i); } })` —
   построчное `upd(i)` (`updateCurrent().replace(item)`, реальный Drift
   `UPDATE` к физической sqlite3-БД) внутри одной Drift-транзакции.
7. В этом сценарии один из вызовов `upd(i)` бросает исключение — техническая
   ошибка на уровне Drift/sqlite3 (например, ошибка I/O диска, блокировка
   файла БД другим процессом/потоком, повреждение данных, либо любое другое
   исключение `sqlite3`/drift; ровно тот же класс причин, что уже
   зафиксирован для чтения того же справочника в
   [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)).
8. `transaction()` перехватывает исключение только для того, чтобы
   откатить все изменения, уже сделанные внутри этой же транзакции (включая
   уже обработанные до сбоя строки того же вызова `updateAll`), и
   **пробрасывает то же исключение дальше** — ни одна строка `Kind` из
   этого вызова не сохраняется в БД, частичной записи не происходит.
9. Исключение всплывает необработанным: из `BaseDao.updAll` → из
   `BaseRepository.updateAll` (чистая делегация, без `try/catch`) → из
   `KindsRepository.updateAll` (не переопределён) → из строки `await
   _kindsRepository.updateAll(state.kinds);` внутри `save()`. **Ни один код
   на этом пути не содержит `try/catch`** — `save()` целиком, кроме уже
   пройденного условия шага 4, не имеет вокруг этого вызова никакой
   обработки ошибок.
10. `Future<void>`, возвращённый `save()`, завершается с этой ошибкой. Единая
    во всей кодовой базе точка вызова (`kinds_visibility_settings_page.dart`,
    шаг 3) не подписана на него — ни `await`, ни `.then`, ни `.catchError`.
    Это становится необработанной асинхронной ошибкой `Future` по
    стандартной семантике Dart.
11. Внутренний `try/catch` `BlocBase.emit()` (`bloc-9.0.1/lib/src/bloc_base.dart`) —
    единственный механизм, вызывающий `BlocObserver.onError`/`onError()` для
    `Cubit`, — здесь не участвует вовсе: он оборачивает только сам вызов
    `_stateController.add()`/`onChange()` внутри `emit()` и явные вызовы
    `addError()`. После шага 4 `emit()` в этом сценарии больше не вызывается
    ни разу до самого исключения — перехватывать нечего. `Bloc.observer =
    TalkerBlocObserver(...)` (`lib/injection_container.dart`) не получает
    вызов `onError` и, следовательно, не пишет ничего в `Talker`.
12. `lib/main.dart`, `main()`, вызывает `runApp(const MyApp())` напрямую —
    альтернативная строка `runTalkerZonedGuarded(getIt<Talker>(), () =>
    runApp(const MyApp()), (error, stack) =>
    getIt<Talker>().handle(error, stack))`, которая перенаправляла бы
    необработанные ошибки зоны в `Talker`, закомментирована. Другого
    `PlatformDispatcher.instance.onError`/`FlutterError.onError` нигде в
    `lib/` не зарегистрировано (тот же вывод, что уже подтверждён grep'ом в
    [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)) — эта
    ошибка не логируется нигде внутри приложения, видна (если вообще) только
    в консоли отладки/DevTools как «Unhandled exception».
13. Наблюдаемый пользователем итог: **ничего не происходит**. `state`
    кубита остаётся точно тем же `KindsVisibilitySettingsState.loaded(kinds:
    ...)`, что был перед нажатием «Сохранить» (переключённый, но так и не
    сохранённый набор) — переход ни в `saved`, ни в `failure` не
    происходит. `BlocConsumer.listener` в `KindsVisibilitySettingsPage`
    реагирует только на `state.whenOrNull(saved: ..., failure: ...)` — ни
    одна из веток не срабатывает: снэкбара нет (ни успеха, ни ошибки),
    `context.pop()` не вызывается (он есть только в ветке `saved`). Экран
    остаётся открытым, переключатели показывают ровно то, что пользователь
    успел переключить руками.
14. `Kinds.visible` в БД не меняется ни для одной строки этого вызова (шаг
    8, откат транзакции). С этого момента экран показывает выбор, который
    физически не сохранён: если пользователь покинет экран
    (`Navigator.pop`/системная кнопка «назад»), несохранённые переключения
    теряются безвозвратно и без предупреждения; повторное открытие экрана
    пересоздаёт кубит и `load()` возвращает реальные (не изменённые этим
    неудавшимся вызовом) значения из БД.

### Альтернативные потоки

- **Успешный путь — не этот сценарий.** Если `updateAll` не бросает
  исключения, `save()` продолжает `emit(saved(kinds: state.kinds))` —
  отдельный `UPDATE_OK`-сценарий, не описываемый здесь (покрыт тестом,
  group `'UC-173 — KindsVisibilitySettingsCubit.save'`, см. «Связанные
  тесты»).
- **`REJECTED` — не этот сценарий.** Если ни один вид не остаётся видимым,
  `save()` отказывает раньше, до какого-либо вызова `updateAll` — это
  [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md);
  там нет ни сети, ни исключения, отказ — осознанное решение бизнес-правила
  кубита. Здесь, напротив, условие уже пройдено — отказывает сам вызов
  репозитория, а не логика кубита.
- **Атомарность транзакции — единственная гарантия в этом сценарии, и она
  не сообщается пользователю.** В отличие от инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  (б)), где логический отказ сервера приводит к **безвозвратному** удалению
  уже принятых локально данных без отката, здесь `transaction()` гарантирует
  «всё или ничего» на уровне физической БД — ни одна строка `Kind` не
  сохраняется частично. Но это чисто внутреннее свойство хранилища:
  пользователю ничего не сообщается ни о попытке, ни об её исходе — данные
  технически в безопасности (остаются такими же, как до попытки), но
  наблюдаемый эффект для пользователя — «кнопка не работает».
- **Тот же класс пробела, что и у `load()` этого же кубита
  ([UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)), но
  с другим наблюдаемым исходом.** Оба публичных метода
  `KindsVisibilitySettingsCubit`, обращающиеся к репозиторию (`load()`,
  `save()`), не содержат ни одного `try/catch`, и оба вызываются с
  отброшенным `Future` (`..load()` в `create:` страницы, `.save()` в
  `onTap` без `await`) — ни один из двух путей этого кубита к БД не имеет
  обработки ошибок. Разница — только в том, что `load()` успевает эмитить
  `loading` до отказа (значит UI показывает видимый бесконечный спиннер),
  тогда как `save()` не эмитит ничего до сбоя (значит UI не показывает
  вообще никакого признака попытки) — оба одинаково не долетают ни до
  `Talker`, ни до пользователя.
- **Другой, не бросающий исключение путь того же метода `upd`, не
  относящийся к этому use-case.** `updateCurrent().replace(item)` возвращает
  `bool` (было ли реально что-то изменено) и сам по себе не бросает
  исключение при «0 затронутых строк» — например, если `Kind` с данным `id`
  был удалён из таблицы между `load()` и нажатием «Сохранить» (гипотетически
  возможно при полном пересинке справочника с сервера в параллель). Такой
  случай не порождает исключения и, следовательно, не является предметом
  этого `UPDATE_ERROR`-сценария — это отдельный, здесь не
  специфицированный путь «тихая частичная запись без исключения при
  устаревшем id».

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS, узкая грань `Kind.visible`) — сущность, чью запись этот
  сценарий не может завершить: ни одна строка `Kinds` не изменяется в БД
  (откат транзакции, шаг 8), тогда как in-memory `state.kinds` кубита
  продолжает показывать переключённый пользователем (но не сохранённый)
  набор до выхода с экрана.
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — не участвует: `save()` — чисто локальная операция,
  сеть здесь не задействована вовсе (в отличие от последующей отправки на
  сервер того же `visibleKinds` через `SettingsRepository.setSettingToSHTP`,
  которая относится к отдельному, sync-этапу [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md),
  не к этому сценарию).
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не участвует;
  `save()` не читает и не пишет пользователя.

### Бизнес-правила

- **Условие «хотя бы один вид видим» — пройдено, это предпосылка этого
  сценария, не его предмет.** Отказ здесь происходит после этой проверки,
  на уровне физического хранилища, а не бизнес-логики кубита.
- **Нет ни одного перехватчика ошибок на всём пути записи.** Ни `save()`,
  ни `KindsRepository`, ни `BaseRepository`, ни `KindsDao`, ни `BaseDao` не
  оборачивают `updateAll`/`updAll`/`upd` в `try/catch` — при технической
  ошибке хранилища единственная реакция системы — рассинхронизация
  in-memory состояния кубита (продолжает показывать несохранённый выбор) и
  физического состояния БД (остаётся неизменным), без единого сигнала
  пользователю в любую сторону.
- **Атомарность на уровне БД не означает наблюдаемость для пользователя.**
  `transaction()` гарантирует, что частичная запись невозможна — либо все
  строки текущего вызова `updateAll` применяются, либо ни одна. Это
  предотвращает худший класс дефекта (испорченные наполовину данные), но не
  компенсирует отсутствие какого-либо UI-сигнала об отказе.
- **Нет ретрая.** Единственный способ попытаться сохранить снова —
  повторно нажать «Сохранить» на том же экране (кубит и его in-memory
  `state.kinds` не пересоздаются) — ничего в UI не подсказывает
  пользователю, что предыдущая попытка не удалась и её стоит повторить.

## TARGET

TARGET не отличается от CURRENT — это документирующий проход по уже
существующему коду, не работа над исправлением дефекта.

## TBD / BLOCKED

Блокеров для документирования нет. Весь сценарий — необработанное
исключение внутри `BaseDao.updAll` (вызванного из `KindsRepository.updateAll`
→ `BaseRepository.updateAll`), отсутствие какого-либо перехватчика на всём
пути до `KindsVisibilitySettingsCubit.save()`, и то, что вызывающий код
(`kinds_visibility_settings_page.dart`) не `await`-ит и не перехватывает
возвращённый `Future` — прослеживается статическим чтением всей цепочки
файлов, перечисленных в «Технические зависимости». Ни один существующий
тест этот путь не воспроизводит (см. «Связанные тесты»). Реальный
технический источник исключения (диск, блокировка файла БД, повреждение
данных) эмпирически не воспроизведён — тот же уровень уверенности, что и в
[UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md) для чтения
того же справочника. Исправление (например, `try/catch` вокруг
`updateAll` с видимым пользователю `failure`-состоянием, аналогично уже
существующей ветке `save()` для `REJECTED`) в рамках этого документирующего
прохода не выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.save` | CURRENT | предмет сценария; после пройденной проверки `state.kinds.any((e) => e.visible)` вызывает `await _kindsRepository.updateAll(state.kinds)` без единого `try/catch` вокруг этого вызова |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_state.dart` | `KindsVisibilitySettingsState.loaded`/`.saved`/`.failure` | CURRENT | в этом сценарии кубит остаётся в `loaded` (последнем эмитированном перед `save()` состоянии) — ни `saved`, ни `failure` не достигаются |
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `KindsVisibilitySettingsPage.build` (`floatingActionButton.onTap`, `BlocConsumer.listener`) | CURRENT | `onTap: () { context.read<KindsVisibilitySettingsCubit>().save(); }` — `Future`, возвращённый `save()`, не `await`-ится и не перехватывается; `listener` реагирует только на `saved`/`failure`, ни одна ветка не срабатывает в этом сценарии |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository` | CURRENT | не переопределяет `updateAll` — используется как есть из `BaseRepository`, без собственной обработки ошибок |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | прямая делегация в `dao.updAll(list)`, без `try/catch` |
| `packages/sheep_farm_database/lib/entities/kind/kinds_dao.dart` | `KindsDao` | CURRENT | Drift DAO над таблицей `Kinds`, не переопределяет `updAll`/`upd` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll`, `.upd` | CURRENT | `updAll` — построчный `upd` внутри одной Drift-`transaction()`; при исключении внутри неё транзакция откатывается целиком и то же исключение пробрасывается вызывающему коду; `upd` — реальный Drift `UPDATE` (`updateCurrent().replace(item)`), источник технического исключения в этом сценарии |
| `lib/main.dart` | `main()` (`runApp(const MyApp())`, закомментированный `runTalkerZonedGuarded`) | CURRENT | подтверждает отсутствие глобального перехватчика необработанных ошибок `Future` в приложении — та же находка, что уже зафиксирована в [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md) |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | не получает вызов `onError` в этом сценарии — `BlocBase.emit()` не вызывается ни разу после отказавшего `updateAll`, а именно `emit()` — единственный триггер `onError`/`BlocObserver.onError` для `Cubit` |
| `lib/pages/routes.dart` | `Routes.profile`/`.workSettings`/`.kindsVisibilitySettings` | CURRENT | вложенность маршрута `/profile/work_settings/kinds_visibility_settings` |

## Критерии приёмки

- Если на момент вызова `save()` в `state.kinds` есть хотя бы один элемент
  с `visible == true` (условие шага 4 ложно), и вызов `_kindsRepository.updateAll(state.kinds)`
  бросает исключение любого типа, оно всплывает необработанным из
  `KindsVisibilitySettingsCubit.save()` — ни одного `emit` после начала
  метода не происходит.
- `Kinds.visible` не меняется в БД ни для одной строки этого вызова
  (Drift-транзакция откатывается целиком при исключении внутри неё).
- `state` кубита остаётся равным тому значению `loaded(kinds: ...)`, что
  было до вызова `save()` — переход ни в `saved`, ни в `failure` не
  происходит.
- `KindsVisibilitySettingsPage` не показывает ни `SnackBar`, ни какой-либо
  другой видимый признак отказа или успеха; `context.pop()` не вызывается,
  экран остаётся открытым.
- Ошибка не появляется ни в одном логе приложения — `TalkerBlocObserver.onError`
  не вызывается (в этом сценарии `emit()` после начала `save()` не
  вызывается ни разу), `getIt<Talker>()` нигде в `save()`/`KindsRepository.updateAll`/
  `BaseRepository.updateAll`/`BaseDao.updAll` не используется.
- Повторная попытка сохранить возможна только повторным нажатием «Сохранить»
  на том же экземпляре кубита; выход с экрана без успешного сохранения
  теряет переключённый, но не сохранённый выбор без предупреждения.

## Связанные тесты

`test/pages/kinds_visibility_settings_cubit_test.dart` существует, но
покрывает только успешные и осознанно-отклонённые комбинации:

- group `'UC-171 — KindsVisibilitySettingsCubit.load'`, test `'загружает и
  сортирует kinds по имени'`.
- group `'KindsVisibilitySettingsCubit.toggleKindVisibility'`, тесты
  `'переключает visible у нужного вида'`, `'неизвестный id -> no-op'`.
- group `'KindsVisibilitySettingsCubit.toggleAllKindsVisibility'`, test
  `'выставляет visible всем сразу'`.
- group `'UC-174 — KindsVisibilitySettingsCubit.save REJECTED'`, test `'нет
  ни одного видимого вида -> failure, updateAll не вызывается'` — покрывает
  соседний, не этот сценарий ([UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md)).
- group `'UC-173 — KindsVisibilitySettingsCubit.save'`, test `'есть видимые
  виды -> updateAll вызван, saved'` — единственный тест, где `updateAll`
  реально вызывается с непустым `state.kinds`, но здесь он замокан
  успешным (`when(() => repository.updateAll(any())).thenAnswer((_) async
  {})`) — противоположный, не этот, исход.

Ни один из пяти существующих тестов не мокает `repository.updateAll(any())`
как бросающий исключение (`thenThrow`/аналог), и ни один не проверяет
состояние кубита после такого отказа.

**TBD — теста нет** на сценарий, описанный этим файлом: ни на сам отказ
`updateAll` при непустом множестве видимых видов, ни на итоговое состояние
кубита (должно остаться `loaded`, без перехода в `saved`/`failure`), ни на
поведение `KindsVisibilitySettingsPage` при таком отказе.

## Открытые вопросы и ограничения

- **Ни один из двух методов кубита, обращающихся к репозиторию, не имеет
  обработки ошибок.** Как и `load()` ([UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)),
  `save()` не оборачивает свой единственный вызов репозитория в `try/catch`
  — контраст с соседним экраном того же модуля
  (`NotificationsSettingsCubit.load()`,
  [UC-168](UC-168-ACTOR-5-EVT-84-ENT-21-READ_ERROR-IN-PROFILE.md)), где хотя
  бы есть `try/catch` с логированием в `Talker`, говорит скорее в пользу
  недосмотра, чем осознанного решения именно для этого кубита. Ничем в
  коде/комментариях это не зафиксировано как намеренное.
- **Атомарность транзакции — реальная защита данных, но она никак не
  сообщается пользователю.** В отличие от инвентаризации
  ([UC-126](UC-126-ACTOR-4-EVT-63-ENT-17-CREATE_ERROR-IN-ANIMAL.md), ветка
  (б)), где логический отказ сервера безвозвратно удаляет уже принятые
  локально данные, здесь откат транзакции гарантирует, что БД не
  повреждается частично — но с точки зрения пользователя итог всё равно
  неотличим от «кнопка ничего не делает»: нет ни снэкбара с ошибкой (как в
  [UC-174](UC-174-ACTOR-5-EVT-87-ENT-3-UPDATE_REJECTED-IN-PROFILE.md)), ни
  бесконечного спиннера (как в
  [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md)) — вообще
  никакого наблюдаемого эффекта.
- **Несохранённый выбор молча теряется при выходе с экрана.** Поскольку
  `state.kinds` продолжает показывать переключённый пользователем набор,
  а БД остаётся неизменной, пользователь может ошибочно считать, что
  изменения сохранены (визуально переключатели стоят в нужном положении) —
  до тех пор, пока не откроет экран заново и не увидит настоящие,
  несохранённые значения из БД. Ни один UI-элемент не предупреждает об этом
  расхождении в момент, когда оно возникает.
- Реальный технический источник исключения внутри `upd`/`updateCurrent().replace()`
  (диск, блокировка файла БД, повреждение данных) не воспроизведён
  эмпирически — этот документирующий проход, как и
  [UC-172](UC-172-ACTOR-5-EVT-86-ENT-3-READ_ERROR-IN-PROFILE.md), опирается
  на статическое чтение цепочки вызовов и на устройство
  `bloc`/`drift`, а не на реально воспроизведённый сбой.
- Тот же факт (`Kind.visible`) редактируется и вторым, независимо
  реализованным путём — шагом `FarmCreateStep.kindsVisibility` визарда
  создания фермы (`FarmCreateCubit`, модуль `FARM`) — не проверено, страдает
  ли тот код тем же отсутствием обработки ошибок при записи; вне рамок
  этого use-case (код принадлежит уже закрытому модулю `FARM`), уже
  отмечено как находка в [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md).
