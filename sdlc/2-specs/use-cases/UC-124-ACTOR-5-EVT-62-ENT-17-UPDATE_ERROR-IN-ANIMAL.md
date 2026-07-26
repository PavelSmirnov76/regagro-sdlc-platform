# UC-124 — Правка сессии инвентаризации отказывает без следа: `ScanningBloc.close()` бросает исключение из `markSessionReadyToSendByUuid` без своего `try/catch`, а экран к этому моменту уже закрыт

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

[EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) завершается
одним из двух путей — явно (кнопка «Завершить», `ScanningEventSave`) либо
неявно (уход с экрана назад, `ScanningBloc.close()`). Этот файл — про отказ
на **неявном** пути: `ScanningBloc.close()` при `isEditMode && _canPersistSession`
безусловно вызывает `markSessionReadyToSendByUuid`/`markSessionReadyToSend`
**без собственного `try/catch`**. Если этот вызов бросает исключение
(например, Drift/SQLite-исключение из-за гонки с уже закрывающимся
соединением, диска и т.п.), оно не перехватывается нигде в этой цепочке
вызовов и становится необработанной асинхронной ошибкой — при этом экран, на
котором можно было бы показать пользователю сообщение об ошибке, к этому
моменту уже закрыт (см. «Основной поток», шаг 12).

Второй, независимо достижимый путь к тому же `RESULT` в этом же
edit-режиме — явный «Завершить» (`ScanningEventSave`): та же
`markSessionReadyToSend*`-операция там уже обёрнута в `try/catch`, идентичный
техническому пути [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)
(см. [UC-122](UC-122-ACTOR-5-EVT-61-ENT-17-CREATE_ERROR-IN-ANIMAL.md), где
этот общий обработчик разобран подробно) — здесь этот путь описан только
кратко, во «Альтернативных потоках», без повторения того же разбора.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково (`ScanningBloc` нигде не
проверяет статус авторизации). Пользователь ранее уже завершил сессию
инвентаризации ([EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md)),
теперь открывает её на правку из хаба «В работе» (`UnsentInventoriesPage`) и
уходит с экрана правки назад, не нажимая «Завершить».

## CURRENT

### Основной поток

1. Ранее (отдельный проход, [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md))
   пользователь завершил сессию инвентаризации: строки `UnsentReportAnimals`
   с данным `sessionUuid` имеют `readyToSend == true`.
2. Пользователь открывает `UnsentInventoriesPage`
   (`lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart`),
   список построен через `UnsentInventoriesCubit.load()` →
   `_reportAnimalsRepo.getInventoryReadySessions()` →
   `UnsentReportAnimalsDao.getInventoryReadySessions()` — строго
   `type == 'inventory' && readyToSend == true`. Тап по карточке сессии →
   `UnsentInventoriesPage._openEditMode` → `context.pushNamed2(Routes.scanning,
   extra: ScanningPageArgs.inventory(farm: item.farmWithDetails, editPlaceId:
   item.placeId, editSessionUuid: item.sessionUuid, ...))` — результат
   навигации **не** ожидается (`await` отсутствует).
3. `ScanningPage.build` создаёт `BlocProvider(create: (context) =>
   ScanningBloc()..add(ScanningStart(..., editPlaceId:, editSessionUuid:)))`.
4. `ScanningBloc.on<ScanningStart>`: ветка `event.editSessionUuid != null &&
   selectedScanningType != null` — `_data = _data.copyWith(place:,
   scannedAnimals: [], isEditMode: true, skipPlaceStep: true, sessionUuid:
   event.editSessionUuid)`, затем `await
   _unsentReportsRepository.markSessionAsDraftByUuid(event.editSessionUuid!)` —
   переводит те же строки обратно в `readyToSend == false` **до того, как
   пользователь сделал хоть одно действие правки**. Существующие строки
   сессии перезагружаются (`_loadSessionFromStorage`), эмитится
   `ScanningSuccess`.
5. Пользователь на экране правки (`isEditMode == true`) — просматривает или
   добавляет сканы (каждый новый скан сразу персистится отдельно,
   `_persistDraftScanReports`, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md));
   решает уйти назад, не нажимая «Завершить».
6. `_ScanningPageState`'s `WillPopScope.onWillPop`
   (`lib/pages/scanning/scanning_page.dart`): если `_currentIndex > 0` —
   переключает на предыдущий шаг и блокирует pop (`return false`); только на
   `_currentIndex == 0` возвращает `true`, разрешая обычный pop маршрута.
7. `Navigator` снимает маршрут `ScanningPage` со стека; Flutter уничтожает
   поддерево виджетов страницы, включая `BlocProvider<ScanningBloc>`. Его
   `dispose`-колбэк (`flutter_bloc` 9.1.1,
   `lib/src/bloc_provider.dart` → `InheritedProvider<T>(..., dispose: (_,
   bloc) => bloc.close(), ...)`) вызывается из `InheritedProvider.dispose()` —
   обычного синхронного `void dispose()` (`provider` 6.1.5,
   `lib/src/inherited_provider.dart`). Возвращаемый `bloc.close()` `Future<void>`
   при этом **не ожидается** (`await` невозможен внутри синхронного `dispose()`)
   и никуда не сохраняется.
8. Внутри `ScanningBloc.close()`: подписки на сканер отменяются,
   `_commonChannel.invokeMethod('clear')`; затем, поскольку
   `_data.isEditMode == true` и `_canPersistSession == true` (ферма/место/тип
   сканирования заданы из preset'а edit-режима), и поскольку `_isInventory &&
   _data.sessionUuid != null` — выполняется ветка по uuid: `await
   _unsentReportsRepository.markSessionReadyToSendByUuid(_data.sessionUuid!)`.
   Весь этот `if`-блок находится прямо в теле `close()`, без собственного
   `try`/`catch` — единственная защита от исключений во всём методе.
9. Если `UnsentReportAnimalsDao.markSessionReadyToSendByUuid` (обычный Drift
   `update(unsentReportAnimals)..where(...).write(...)`) бросает исключение —
   например, СУБД/соединение уже в процессе закрытия, диск, любой другой
   Drift/SQLite-сбой — оно всплывает прямо из `await` внутри `close()` и
   становится ошибкой `Future<void>`, который `close()` возвращает.
10. Поскольку вызывающая сторона — `provider`'s `dispose: (_, bloc) =>
    bloc.close()` — не ожидает и не подписывается на этот `Future`, отказ
    никем не наблюдается: это необработанная асинхронная ошибка, которую Dart
    передаёт в обработчик текущей `Zone`. `main()` (`lib/main.dart`) вызывает
    `runApp(const MyApp())` напрямую — альтернатива с `runZonedGuarded`
    присутствует в исходнике только закомментированной строкой; ни
    `runZonedGuarded`, ни `FlutterError.onError`/`PlatformDispatcher.instance.onError`
    нигде в `lib/` не переопределены (`grep -rn "runZonedGuarded\|FlutterError.onError\|PlatformDispatcher.instance.onError"
    lib/` не находит ни одного совпадения, кроме несвязанных чтений
    `PlatformDispatcher.instance.locale`). Итоговый приёмник этой ошибки —
    целиком дефолтное поведение Flutter/Dart, ничем в этом приложении не
    настроенное.
11. Собственный механизм `ScanningBloc` тоже не видит этот отказ: внутренний
    `Bloc.observer`/`onError` пакета `bloc` оборачивает только выполнение
    `on<Event>`-обработчиков, не переопределённый `close()` — исключение
    из шага 9 не проходит и через этот путь тоже. Оно также не логируется
    через `Talker` — в отличие от `catch`-блока `on<ScanningEventSave>` (см.
    «Альтернативные потоки»), здесь никакого логирования нет вовсе.
12. К моменту шага 9 экран `ScanningPage` уже снят со стека (это произошло на
    шаге 7, раньше, чем стартовал сам вызов) — показать пользователю
    snackbar/диалог об ошибке было бы невозможно, даже если бы исключение
    перехватывалось. `UnsentInventoriesPage._openEditMode` тоже не ожидает
    результат `pushNamed2` — сообщить об отказе некому и на уровне
    вызывающего экрана. Отказ невидим целиком: не залогирован, не показан
    пользователю, не отражён ни в одном состоянии/репозитории.
13. Эффект на данные: строки `UnsentReportAnimals` этой сессии остаются с
    `readyToSend == false` — тем самым, в которое их перевёл шаг 4
    (`markSessionAsDraftByUuid`), — навсегда, если только пользователь не
    попадёт на тот же `sessionUuid` снова. Но `UnsentInventoriesCubit.load`/
    `UnsentReportAnimalsDao.getInventoryReadySessions()` (шаг 2) отбирают
    строго `readyToSend == true` — эта же сессия **пропадает из хаба «В
    работе»** после отказа, и никакого другого экрана, листающего
    `readyToSend == false`-строки по `sessionUuid`, в `lib/` нет
    (`grep -rn "readyToSend" lib/` — единственные потребители: сам
    `ScanningBloc` через `getSessionReportsByUuid` (нужен уже известный
    `sessionUuid`, которого пользователю взять неоткуда) и хаб, отобранный
    выше). Строки физически остаются в `UnsentReportAnimals` (не удаляются),
    но становятся недостижимы ни из одного экрана — до логаута
    (`@Clearable()`, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)),
    который стирает их целиком, вместе со всеми остальными неотправленными
    строками.

### Альтернативные потоки

- **Явное «Завершить» в edit-режиме (`ScanningEventSave`) — второй источник
  того же `RESULT`, уже покрытый общим кодом.** `on<ScanningEventSave>`
  вызывает `_markSessionReadyToSend()` (та же по сути операция) внутри
  собственного `try/catch`: при исключении — `getIt<Talker>().error('при
  сохранении данных $e, st: $st')` (видно через `TalkerScreen` из профиля) и
  `emit(ScanningMessage('an_error_data'))` — пользователь **видит** снекбар,
  пока экран ещё смонтирован, в отличие от основного потока этого файла.
  Идентичный по механике технический путь уже разобран подробно для
  [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) в
  [UC-122](UC-122-ACTOR-5-EVT-61-ENT-17-CREATE_ERROR-IN-ANIMAL.md) — здесь тот
  же код исполняется при `isEditMode == true`, что делает исход `UPDATE_ERROR`
  (EVT-62), а не `CREATE_ERROR` (EVT-61); полный разбор — там, не повторяется
  здесь.
- **`close()` выполняется повторно и после успешного явного «Завершить».**
  `_data.isEditMode` не сбрасывается нигде после входа в edit-режим — значит,
  после успешного `ScanningEventSave` (шаг emits `ScanningExit`, слушатель
  вызывает `context.pop`) снятие `ScanningPage` со стека всё равно вызывает
  `ScanningBloc.close()`, и `close()` **безусловно** повторяет тот же вызов
  `markSessionReadyToSendByUuid` ещё раз — избыточно, но безобидно при
  успехе. Если именно этот, второй по счёту вызов бросит исключение (успешный
  `ScanningEventSave` не гарантирует, что и повторный вызов в `close()`
  тоже пройдёт), дефект этого файла наступает **даже после видимого
  пользователю успешного сохранения** — не только на пути «назад». Не
  зафиксировано нигде в коде/комментариях как осознанное поведение.
- **`_canPersistSession == false` в момент ухода с экрана.** Тогда `close()`
  просто пропускает весь блок (`if (_data.isEditMode && _canPersistSession)`)
  — ни вызова, ни исключения, тот же «тихий no-op», что документирован в
  [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) для
  `ScanningEventSave`. На практике вход в edit-режим всегда предустанавливает
  валидные ферму/место/тип из уже сохранённой сессии, так что эта ветка
  скорее теоретическая. Не `UPDATE_ERROR` — не этот файл.
- **`close()` без исключения (успех)** — штатный путь ухода с экрана назад;
  `RESULT = UPDATE_OK`, отдельный use-case (не этот файл).

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport / `UnsentReportAnimals`) — сущность сегмента `ENT` в
  id: при отказе строки сессии остаются `readyToSend == false` (переведены
  туда шагом 4, `markSessionAsDraftByUuid`), не удаляются, но становятся
  недостижимы ни из одного экрана хаба.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — `placeId`
  сессии, читается для preset'а edit-режима, этим сценарием не изменяется.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — `farmId` сессии,
  аналогично не изменяется.

### Бизнес-правила

- В edit-режиме (`isEditMode == true`) уход с экрана `ScanningPage` **любым**
  способом — назад ИЛИ после явного «Завершить» — вызывает
  `ScanningBloc.close()`, который безусловно пытается
  `markSessionReadyToSendByUuid`/`markSessionReadyToSend`, если
  `_canPersistSession == true`, без собственного `try/catch`.
- Если этот вызов бросает исключение, оно становится необработанной
  асинхронной ошибкой (`BlocProvider`'s `dispose: (_, bloc) => bloc.close()`
  не ожидает и не перехватывает возвращаемый `Future`); не проходит через
  `Bloc.observer`/`onError` пакета `bloc` (тот оборачивает только
  `on<Event>`); не логируется через `Talker` нигде на этом пути.
- К моменту, когда этот вызов вообще стартует, экран уже закрыт (снятие со
  стека — причина уничтожения `BlocProvider`, а не следствие) — сообщить
  пользователю об ошибке в принципе некому, независимо от того, перехватить
  ли исключение.
- Данные не удаляются, но становятся недостижимыми: `readyToSend == false`
  строки сессии не отображаются нигде, кроме как через уже известный
  `sessionUuid` — единственный экран, который мог бы этот `sessionUuid`
  подсказать (хаб «В работе»), сам фильтрует строго `readyToSend == true` и
  эту же сессию после отказа больше не покажет.
- `REJECTED` для этого сценария структурно недостижим — здесь нет сетевого
  вызова и нет решения сервера; единственная альтернатива исходу `OK` —
  технический сбой локальной БД, что и есть `ERROR`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — сценарий воспроизводится статическим
чтением кода целиком: `ScanningBloc.close()` →
`UnsentReportAnimalsRepository.markSessionReadyToSendByUuid` →
`UnsentReportAnimalsDao.markSessionReadyToSendByUuid`, плюс механика
`dispose`-колбэка `BlocProvider`/`InheritedProvider` (`flutter_bloc` 9.1.1,
`provider` 6.1.5) и отсутствие `runZonedGuarded`/кастомного
`FlutterError.onError` в `lib/main.dart`. Возможное исправление (например,
обернуть блок в `close()` в свой `try/catch` с логированием через `Talker`,
либо завести отдельный «черновики» экран для `readyToSend == false` строк) в
рамках этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.close` | CURRENT | безусловно персистит edit-режим сессию при любом закрытии bloc'а; без собственного `try/catch` вокруг `markSessionReadyToSendByUuid`/`markSessionReadyToSend` |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningStart>` | CURRENT | вход в edit-режим: `markSessionAsDraftByUuid` переводит сессию в `readyToSend == false` до какой-либо правки |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc.on<ScanningEventSave>`, `_markSessionReadyToSend` | CURRENT | второй, уже обёрнутый в `try/catch` источник того же исхода — см. [UC-122](UC-122-ACTOR-5-EVT-61-ENT-17-CREATE_ERROR-IN-ANIMAL.md) |
| `lib/pages/scanning/scanning_bloc.dart` | `ScanningBloc._canPersistSession`, `_isInventory` | CURRENT | геттеры, определяющие, какая из двух веток `close()` выполняется и выполняется ли она вообще |
| `lib/pages/scanning/scanning_page.dart` | `ScanningPage.build` (`BlocProvider`), `_ScanningPageState.build` (`WillPopScope.onWillPop`) | CURRENT | создаёт/уничтожает `ScanningBloc`; разрешает pop (и тем самым disposal) только когда `_currentIndex == 0` |
| `lib/pages/unsent_inventories/presentation/unsent_inventories_page.dart` | `UnsentInventoriesPage._openEditMode` | CURRENT | точка входа в edit-режим из хаба; не ожидает результат навигации |
| `lib/pages/unsent_inventories/cubit/unsent_inventories_cubit.dart` | `UnsentInventoriesCubit.load` | CURRENT | список хаба строится строго по `readyToSend == true` — источник «исчезновения» сессии после отказа |
| `lib/repositories/unsent_report_animal/unsent_report_animals_repository.dart` | `UnsentReportAnimalsRepository.markSessionReadyToSendByUuid`, `markSessionAsDraftByUuid` | CURRENT | тонкая делегация в DAO, без собственного `try/catch` |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.markSessionReadyToSendByUuid` | CURRENT | сам Drift `update(...).write(...)` вызов — источник потенциального исключения |
| `packages/sheep_farm_database/lib/entities/unsent_report_animal/unsent_report_animals_dao.dart` | `UnsentReportAnimalsDao.getInventoryReadySessions` | CURRENT | тот же фильтр `readyToSend == true`, подтверждает «исчезновение» сессии из хаба |
| `lib/main.dart` | `main`, `MyApp.build` | CURRENT | подтверждает отсутствие `runZonedGuarded`/кастомного `FlutterError.onError` во всём приложении — необработанная ошибка уходит в дефолтный обработчик Flutter/Dart |

## Критерии приёмки

- В edit-режиме (`isEditMode == true`) закрытие `ScanningPage` любым способом
  (назад через `WillPopScope`, либо после успешного/неуспешного явного
  «Завершить») вызывает `ScanningBloc.close()`, который при
  `_canPersistSession == true` безусловно вызывает
  `markSessionReadyToSendByUuid`/`markSessionReadyToSend`, без своего
  `try/catch`.
- Если этот вызов бросает исключение, оно не перехватывается ни в `close()`,
  ни в `Bloc.observer`/`onError` пакета `bloc`, ни где-либо ещё в этой цепочке
  — становится необработанной асинхронной ошибкой, не логируется через
  `Talker`.
- К моменту этого вызова `ScanningPage` уже снят со стека навигации —
  показать пользователю сообщение об ошибке невозможно даже в принципе,
  независимо от перехвата исключения.
- Строки `UnsentReportAnimals` этой сессии остаются `readyToSend == false`
  (уже переведены туда при входе в edit-режим) и не появляются больше ни в
  одном экране хаба «В работе» (`UnsentInventoriesCubit.load` фильтрует
  строго `readyToSend == true`) — сессия становится недостижима, пока не
  будет стёрта логаутом (`@Clearable()`).
- Явное «Завершить» в edit-режиме реализует тот же исход через уже
  существующий `try/catch` (`on<ScanningEventSave>`), с логированием через
  `Talker` и видимым пользователю снекбаром — см.
  [UC-122](UC-122-ACTOR-5-EVT-61-ENT-17-CREATE_ERROR-IN-ANIMAL.md).

## Связанные тесты

TBD — теста нет ни на один из двух путей. `test/pages/scanning_bloc_test.dart`,
group `'UC-123 — ScanningStart (editSessionUuid)'`, test `'editSessionUuid
задан, сессия найдена с животными -> восстанавливает scannedAnimals и
openAnimalsStep'` — единственный тест, который вообще исполняет `close()` в
edit-режиме (`addTearDown(bloc.close)`, с комментарием в самом тесте: «close()
персистит сессию заново, т.к. isEditMode:true после этого теста»), но
`markSessionReadyToSendByUuid` там замокан на успех
(`.thenAnswer((_) async {})`) — покрывает только успешную ветку, не отказ.
Ни один тест файла не использует `thenThrow` (`grep -n "thenThrow" test/pages/scanning_bloc_test.dart`
не находит совпадений) — ни для `close()`, ни для `on<ScanningEventSave>`.
Технически тест возможен: замокать
`unsentReportsRepository.markSessionReadyToSendByUuid(any())` на
`thenThrow(...)`, довести bloc до `isEditMode == true` (как в тесте
`UC-123`) и проверить `expect(bloc.close(), throwsA(...))` — в отличие от
продакшн-пути (где `Future` от `bloc.close()` отбрасывается вызывающей
стороной `provider`), прямой вызов `bloc.close()` в тесте, как и обычный
`addTearDown(bloc.close)`, действительно проксирует исключение вызывающей
стороне (здесь — `flutter_test`), так что такой тест смог бы это подтвердить.
Такого теста на сегодня нет.

## Открытые вопросы и ограничения

- **Итоговый приёмник необработанной ошибки не проверен эмпирически.**
  Вывод о том, что исключение из `close()` уходит в дефолтный
  `Zone`/`PlatformDispatcher`-обработчик Flutter, сделан статическим чтением
  `lib/main.dart` (нет `runZonedGuarded`, нет кастомного `FlutterError.onError`)
  и исходников пакетов `flutter_bloc`/`provider` — не подтверждено запуском
  приложения на реальном устройстве/эмуляторе с намеренно брошенным
  исключением.
- **Повторный вызов `close()` после успешного явного «Завершить» не
  зафиксирован как осознанное поведение** (см. «Альтернативные потоки») —
  `_data.isEditMode` не сбрасывается нигде после входа в edit-режим, поэтому
  тот же безусловный блок `close()` выполняется ещё раз даже после уже
  показанного пользователю успеха; является ли повторный вызов осознанной
  идемпотентной подстраховкой или просто не учтённым побочным эффектом —
  нигде не отражено.
- **Отсутствие отдельного экрана для `readyToSend == false` сессий —
  структурная причина того, что любой сбой на этом шаге (не только этот,
  через исключение, но в принципе любое прерывание до завершения
  `markSessionReadyToSendByUuid`, включая принудительное закрытие
  приложения ОС) делает сессию невосстановимой через UI.** Является ли это
  осознанным продуктовым решением (черновики не должны быть видны отдельно от
  готовых к отправке) или недосмотром — не зафиксировано.
- Общий технический путь `on<ScanningEventSave>` (второй источник этого же
  `RESULT`) разобран подробно в
  [UC-122](UC-122-ACTOR-5-EVT-61-ENT-17-CREATE_ERROR-IN-ANIMAL.md) — этот файл
  сознательно не повторяет тот разбор, только ссылается на него; если
  UC-122 будет пересмотрен, стоит перепроверить, что ссылка здесь остаётся
  точной.
