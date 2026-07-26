# UC-100 — Сохранение выбытия отказывает технически: `DisposalRepository.saveDisposals` бросает исключение, `AnimalDisposalBloc` эмитит `AnimalDisposalMessage`, форма не сбрасывается

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md)
(`disposal.recorded`): пользователь подтверждает оформление выбытия для
одного или нескольких животных (визард `AnimalDisposalBloc`), но
`DisposalRepository.saveDisposals` бросает исключение при попытке сохранить
строки `Disposal` — техническая ошибка (Drift/БД), не бизнес-отказ:
до этой точки все guard-условия визарда уже пройдены. `catch` в
`AnimalDisposalBloc.on<AnimalDisposalEventSave>` эмитит
`AnimalDisposalMessage('an_error_data')`, затем безусловно
`AnimalDisposalSuccess(_data)` — тот же объект `_data`, что был до попытки,
без единого изменения: выбранные животные, причина, целевая
ферма/место остаются в состоянии визарда (форма не сбрасывается).

В отличие от структурно аналогичных сценариев Vaccination
([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)) и Weighing
([UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)),
`DisposalRepository.saveDisposals` не итерирует записи по одной в цикле — это
один вызов `dao.insAll(disposals)`, то есть один Drift `batch()` на весь
список выбранных животных. Drift оборачивает `batch()` в одну транзакцию
(проверено чтением `Batch._commit` в установленной версии пакета,
`drift ^2.28.2`) — при исключении внутри неё откатывается целиком, поэтому
частичной записи (часть животных уже выбыла, часть — нет) в этом сценарии
не бывает: либо сохраняются все строки `Disposal` батча, либо ни одной.

Диалог подтверждения (`ConfirmSaveDisposalDialog`) переходит в состояние
«успех» практически сразу после того, как `bloc.add(const
AnimalDisposalEventSave())` синхронно поставил событие в очередь — тем же
паттерном, что и в Movement/Vaccination/Weighing, диалог не дожидается
реального результата `on<AnimalDisposalEventSave>`.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково: сам визард (шаги
`selectPlace`/`reason`/`selectTargetFarm`/`selectTargetPlace`/`animals`,
`AnimalDisposalData.currentSteps`) не проверяет авторизацию нигде.
В отличие от `VaccinationBloc`/`WeighAnimalCubit`
([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md),
[UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)),
`AnimalDisposalBloc.on<AnimalDisposalEventSave>` **читает** авторизацию —
`_authRepository.getUser()?.id ?? -1` — чтобы заполнить `Disposal.userId`
(`-1`, если пользователь не авторизован). Это чтение не влияет на исход
данного сценария: ошибка возникает позже, при `saveDisposals`, независимо от
того, каким получился `userId`.

## CURRENT

### Основной поток

1. Пользователь проходит шаги визарда до `AnimalDisposalStep.animals` —
   последнего в `AnimalDisposalData.currentSteps`. На этом шаге
   `_Body._createStepWidget` (`lib/pages/animal_disposal/animal_disposal_page.dart`,
   ветка `case AnimalDisposalStep.animals`) передаёt `AnimalsStepPage.onNext`
   локальную функцию, которая открывает:
   ```dart
   showDialog(
     context: context,
     builder: (context) => ConfirmSaveDisposalDialog(
       onSave: () async {
         bloc.add(const AnimalDisposalEventSave());
       },
       onExit: () {
         Navigator.of(context).pop();
         bloc.add(const AnimalDisposalEventExit());
       },
       animalsCount: data.selectedAnimalIds.length,
       reasonName: data.selectedReason?.name ?? '',
     ),
   );
   ```
2. Пользователь нажимает «Подтвердить» —
   `_ConfirmSaveDisposalDialogState.saveDisposal()`:
   ```dart
   Future<void> saveDisposal() async {
     setState(() => isSaving = true);
     await widget.onSave();
     if (mounted) {
       setState(() {
         isSaving = false;
         isSaved = true;
       });
     }
   }
   ```
   `widget.onSave` — тело лямбды `() async { bloc.add(const
   AnimalDisposalEventSave()); }` не содержит `await`: `bloc.add(...)`
   синхронно кладёт событие в очередь `Bloc`, и `await widget.onSave()`
   резолвится сразу после этого — не дожидаясь, пока
   `on<AnimalDisposalEventSave>` реально завершит попытку (успешно или с
   ошибкой).
3. `setState(() { isSaving = false; isSaved = true; })` выполняется
   практически сразу (здесь, в отличие от аналогичного диалога Vaccination,
   есть проверка `if (mounted)` перед этим `setState`) — `AnimatedSwitcher`
   переключает тело диалога на `_successSaveWidget` (заголовок
   `animals_disposed`, Lottie-анимация `Assets.imSuccessAnimation`, кнопка
   «Готово» → `widget.onExit`). Кнопка «Подтвердить»
   (`enabled: !isSaving`, здесь `isSaving` реально читается в `build()`, в
   отличие от мёртвого одноимённого поля в аналогичных диалогах
   Vaccination/Weighing) успевает побывать недоступной лишь на время между
   двумя `setState`, а затем сам `_confirmSaveWidget` перестаёт
   рендериться — независимо от того, каким исходом завершится реальная
   попытка сохранения.
4. Независимо от диалога, в `AnimalDisposalBloc.on<AnimalDisposalEventSave>`
   начинает выполняться реальная работа:
   ```dart
   emit(
     AnimalDisposalSuccess(
       _data,
       isLoading: true,
       loadingMessage: 'saving_data',
     ),
   );
   ```
   — меняет состояние страницы визарда под диалогом (`_BodyBuilder` рисует
   `CircularProgressIndicatorWithText` поверх формы, пока `isLoading ==
   true`); самого диалога это не касается.
5. Внутри `try`:
   ```dart
   final animals = await _animalsRepository.getAllByFilters(
     ids: _data.selectedAnimalIds,
   );
   final userId = _authRepository.getUser()?.id ?? -1;
   final now = DateTime.now();
   final disposals = <Disposal>[];
   final isBetweenFarms = _data.isBetweenFarmsReason;
   for (final animal in animals) {
     disposals.add(
       Disposal(
         animalId: animal.id,
         placeId: animal.placeId ?? _data.fromPlace?.place.idRemote,
         causeId: _data.selectedReason?.id,
         date: now,
         createdAt: now,
         updatedAt: now,
         sync: false,
         remoteId: null,
         guid: const Uuid().v4(),
         userId: userId,
         fromId: _data.farm?.remoteId,
         toId: isBetweenFarms ? _data.selectedTargetFarm?.remoteId : null,
         toPlaceId: isBetweenFarms
             ? _data.selectedTargetPlace?.place.idRemote
             : null,
       ),
     );
   }
   ```
   строится по одной записи `Disposal` на каждое животное, возвращённое
   `getAllByFilters(ids: _data.selectedAnimalIds)` — уже выбранные ранее в
   визарде id. `id` самого `Disposal` не передаётся (колонка `nullable()
   .autoIncrement()` в `Disposals`, `packages/sheep_farm_database/lib/entities/disposal/disposal.dart`)
   — присваивается Drift'ом при вставке.
6. **Точка технического сбоя (этот сценарий).**
   ```dart
   await _disposalRepository.saveDisposals(disposals);
   emit(AnimalDisposalSuccess(_data));
   ```
   `DisposalRepository.saveDisposals` — `Future<void> saveDisposals(List<Disposal>
   disposals) async => dao.insAll(disposals);`, единственный вызов. В этом
   сценарии он бросает исключение (тест мокает `disposalRepository
   .saveDisposals(any())` на `thenThrow(Exception('db error'))`). Строка
   `emit(AnimalDisposalSuccess(_data));` сразу после него не достигается.
7. ```dart
   } catch (e) {
     emit(const AnimalDisposalMessage('an_error_data'));
     getIt<Talker>().handle(e);
   }
   ```
   Перехватывает исключение **без стек-трейса** (`catch (e)`, не `catch (e,
   st)` — в отличие от `VaccinationBloc._onSave`,
   [UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)):
   `Talker.handle(e)` вызывается с `stackTrace` по умолчанию `null`. Сначала
   эмитится сообщение, затем логируется — порядок операций внутри `catch`
   тоже отличается от Vaccination, где `Talker.handle` вызывается первым.
   `_data` нигде в этом обработчике не переприсваивается.
8. Безусловно, после блока `try/catch` (выполняется на обеих ветках — и
   успеха, и ошибки):
   ```dart
   emit(AnimalDisposalSuccess(_data));
   ```
   — тот же объект `_data`, что использовался всё это время. `isLoading`
   возвращается к дефолтному `false`, `loadingMessage` — к `''`. Это и есть
   наблюдаемый факт «форма не сбрасывается»: `_data.selectedAnimalIds`,
   `_data.selectedReason`, `_data.selectedTargetFarm`/`selectedTargetPlace`,
   `_data.fromPlace` и всё остальное остаются ровно такими же, какими были
   до постановки `AnimalDisposalEventSave` в очередь — ничего не очищается,
   и никакого автоматического перехода на другой шаг визарда не происходит.
9. На `AnimalDisposalPage` `BlocConsumer<AnimalDisposalBloc,
   AnimalDisposalState>.listener` реагирует на `AnimalDisposalMessage`:
   ```dart
   ScaffoldMessenger.of(context).showSnackBar(
     SnackBar(
       content: Text(AppLocalizations.of(context)!.tr(state.message)),
     ),
   );
   ```
   Обычный `SnackBar`, не хелпер `showAppSnackBarError`
   (`lib/widgets/app_snackbar.dart`). `'an_error_data'` — реальный ключ
   `.arb` (`lib/l10n/app_ru.arb`: `"Произошла ошибка при обработке
   данных"`), резолвится через `AppLocalizations.tr`
   (`lib/l10n/app_localization.dart`).
10. Поскольку диалог подтверждения уже переключился на `_successSaveWidget`
    на шаге 3 независимо от реального исхода, `SnackBar` шага 9 — единственный
    канал, которым эта ошибка вообще может дойти до пользователя, и то лишь
    если диалог (маршрут `showDialog`) не закрывает его визуально и страница
    визарда/бло к этому моменту ещё живы (см. «Открытые вопросы»).

### Альтернативные потоки

- **Тот же `catch` покрывает и более раннюю точку — `_animalsRepository
  .getAllByFilters(ids: _data.selectedAnimalIds)` (шаг 5), до вызова
  `saveDisposals`.** Существующий тест воспроизводит только сбой самого
  `saveDisposals`; сбой в `getAllByFilters` тем же обработчиком не
  протестирован отдельно.
- **Нет риска частичной записи.** В отличие от Vaccination
  ([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)) и Weighing
  ([UC-84](UC-84-ACTOR-5-EVT-42-ENT-15-CREATE_ERROR-IN-ANIMAL.md)), где цикл
  вставляет по одной записи без общей транзакции и сбой на N-й итерации
  оставляет `1..N-1` уже закоммиченными, здесь `saveDisposals` — один вызов
  `dao.insAll(disposals)`, то есть один Drift `batch()`
  (`packages/sheep_farm_database/lib/entities/base_dao.dart`,
  `BaseDao.insAll`). Drift оборачивает `batch()` в одну транзакцию
  (`Batch._commit`, пакет `drift ^2.28.2`, не входит в этот репозиторий,
  проверено чтением установленной версии из pub-cache) — при исключении
  внутри неё откатывается целиком: либо сохраняются все строки `Disposal`
  батча, либо ни одной.
- **Живого пути к ретраю тем же `_data` нет.** Кнопка «Подтвердить»
  перестаёт рендериться, как только `isSaved` становится `true` (шаг 3) —
  практически сразу после постановки события в очередь, ещё до того, как
  реальный результат `saveDisposals` вообще становится известен. Дальше
  доступна только кнопка «Готово» (`onExit`), ведущая к
  `AnimalDisposalEventExit` и закрытию всей страницы визарда — гипотетический
  повторный вызов `AnimalDisposalEventSave` с тем же `_data` из этого экрана
  недостижим. (Если бы он был достижим — поскольку `Disposal.id`
  `nullable().autoIncrement()` и никогда не передаётся явно, повторная
  вставка создала бы новые, отдельные строки, а не конфликт по `id`.)
- **Смежная, но не идентичная находка того же потока создания (тот же
  тестовый файл).** Group `'НАХОДКА — AnimalDisposalEventStart без
  try/catch, необработанное исключение вместо AnimalDisposalFailure (см.
  ENT-16)'` показывает, что инициализация визарда
  (`AnimalDisposalEventStart`, а не `AnimalDisposalEventSave`) вообще не
  обёрнута в `try/catch` — необработанное исключение (например, Null check
  operator, если `presetPlace` ссылается на ферму, отсутствующую в локальной
  БД: `(await _farmRepository.getById(arguments.presetPlace!.farmId))!`)
  происходит раньше, чем пользователь успевает дойти до кнопки
  «Сохранить». Это не тот же сценарий (другое событие-триггер, другая точка
  отказа, другой — вернее, полностью отсутствующий — catch), но тот же bloc
  и та же сущность [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), и это
  единственный существующий на сегодня test group, документирующий, что
  `AnimalDisposalFailure` — состояние, которое `animal_disposal_page.dart`
  умеет отрисовать, но `AnimalDisposalEventStart` никогда не эмитит.

### Связанные сущности

- [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) (Disposal) — целевая
  сущность попытки создания. При сбое внутри `saveDisposals` не сохраняется
  ни одна строка батча (см. «Альтернативные потоки» — единая транзакция);
  при сбое раньше, в `getAllByFilters`, до `saveDisposals` дело вообще не
  доходит.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только
  читается: `_animalsRepository.getAllByFilters(ids:
  _data.selectedAnimalIds)` возвращает уже выбранных на более раннем шаге
  визарда животных (`animal.id`, `animal.placeId`). Ни одно животное не
  изменяется этим обработчиком.
- [ENT-5](../entities/ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason,
  HANDBOOKS) — только читается как `_data.selectedReason`, выбранный на
  более раннем шаге визарда; справочник причин не изменяется.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только читается:
  `_data.farm`/`_data.selectedTargetFarm` заполняют `fromId`/`toId`
  строящихся `Disposal`, ничего не изменяется.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — только
  читается: `_data.fromPlace`/`_data.selectedTargetPlace` заполняют
  `placeId`/`toPlaceId`, ничего не изменяется.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — только читается
  через `_authRepository.getUser()?.id ?? -1`, чтобы заполнить
  `Disposal.userId`; чтение не влияет на исход сценария.

### Бизнес-правила

- Технический сбой (исключение из `saveDisposals`/`getAllByFilters` на
  уровне Drift/DAO) классифицируется как `CREATE_ERROR`, а не
  `CREATE_REJECTED` — до этой точки визард уже провёл пользователя через все
  шаги (`currentSteps`), guard-условия каждого шага уже выполнены; отказ
  происходит на уровне хранения, не бизнес-валидации.
- Один и тот же `catch (e)` в `on<AnimalDisposalEventSave>` покрывает обе
  независимые по происхождению точки сбоя (`getAllByFilters`,
  `saveDisposals`) и реагирует на обе одинаково —
  `AnimalDisposalMessage('an_error_data')` плюс безусловный повторный
  `AnimalDisposalSuccess(_data)`.
- `saveDisposals` вызывается один раз на весь батч (`dao.insAll`, один
  Drift `batch()`) — сбой откатывает всю попытку целиком, частичная запись
  невозможна (в отличие от Vaccination/Weighing, где цикл вставляет записи
  по одной без общей транзакции).
- Переключение диалога подтверждения в состояние «успех» **не зависит от
  результата** `on<AnimalDisposalEventSave>` — оно управляется исключительно
  тем, что `bloc.add(...)` (постановка события в очередь) резолвится раньше,
  чем сам обработчик. Верно для любого исхода, но для `ERROR` расхождение
  наиболее заметно.
- `AnimalDisposalBloc.on<AnimalDisposalEventSave>` читает авторизацию
  (`_authRepository.getUser()?.id ?? -1`) только чтобы заполнить
  `Disposal.userId` — это не влияет на то, произойдёт ли сбой.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных потока (единая транзакция вместо
цикла; недостижимость ретрая) прослеживаются чтением
`lib/pages/animal_disposal/animal_disposal_bloc.dart`,
`lib/pages/animal_disposal/animal_disposal_state.dart`,
`lib/pages/animal_disposal/animal_disposal_event.dart`,
`lib/pages/animal_disposal/animal_disposal_page.dart`,
`lib/repositories/disposal/disposal_repository.dart`,
`lib/repositories/animal/animals_repository.dart`,
`lib/repositories/auth/auth_repository.dart`,
`lib/repositories/base_repository.dart`,
`packages/sheep_farm_database/lib/entities/base_dao.dart`,
`packages/sheep_farm_database/lib/entities/disposal/disposal.dart`,
`packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` и
`lib/l10n/app_localization.dart`. Отсутствие стек-трейса в `catch (e)`,
проверка `if (mounted)` в `_ConfirmSaveDisposalDialogState.saveDisposal`, и
то, что `isSaving` реально читается в `build()` (в отличие от аналогичного
поля в диалогах Vaccination/Weighing), перепроверены чтением исходников
напрямую. Атомарность `dao.insAll` (единая транзакция на весь `batch()`)
перепроверена чтением `Batch._commit` в установленной версии пакета `drift
^2.28.2` (`~/.pub-cache/hosted/pub.dev/drift-2.28.2/lib/src/runtime/api/batch.dart`)
— этот файл не часть репозитория проекта, поэтому не входит в таблицу
«Технические зависимости» ниже, но факт был проверен, а не восстановлен по
памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc.on<AnimalDisposalEventSave>` | CURRENT | строит `Disposal` по одному на выбранное животное, вызывает `saveDisposals` одним батчем; `catch (e)` без стек-трейса эмитит `AnimalDisposalMessage('an_error_data')`, затем безусловно `AnimalDisposalSuccess(_data)` |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalData` | CURRENT | payload визарда — не пересоздаётся и не очищается этим обработчиком ни при успехе, ни при ошибке |
| `lib/pages/animal_disposal/animal_disposal_state.dart` | `AnimalDisposalMessage`, `AnimalDisposalSuccess` | CURRENT | состояния, участвующие в сценарии ошибки |
| `lib/pages/animal_disposal/animal_disposal_event.dart` | `AnimalDisposalEventSave` | CURRENT | событие, запускающее сохранение |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `_Body._createStepWidget` (ветка `case AnimalDisposalStep.animals`) | CURRENT | единственный живой путь к открытию `ConfirmSaveDisposalDialog`; передаёт `onSave: () async { bloc.add(const AnimalDisposalEventSave()); }` |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `ConfirmSaveDisposalDialog`, `_ConfirmSaveDisposalDialogState.saveDisposal` | CURRENT | переходит в `_successSaveWidget` сразу после постановки события в очередь, независимо от исхода обработчика; `if (mounted)` перед вторым `setState`; `isSaving` реально читается в `build()` (`enabled: !isSaving`) |
| `lib/pages/animal_disposal/animal_disposal_page.dart` | `BlocConsumer<AnimalDisposalBloc, AnimalDisposalState>.listener` | CURRENT | показывает обычный `SnackBar` (не `showAppSnackBarError`) по `AnimalDisposalMessage` |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.saveDisposals` | CURRENT | единственный вызов `dao.insAll(disposals)` — протестированная точка сбоя данного сценария |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllByFilters` | CURRENT | альтернативный источник исключения, тем же `catch`, не протестирован отдельно |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.getUser` | CURRENT | только читается; заполняет `userId` (`-1` при отсутствии авторизации), не связан с точкой сбоя |
| `lib/repositories/base_repository.dart` | `BaseRepository` (не переопределяет `insAll`) | CURRENT | `DisposalRepository` вызывает `dao.insAll` напрямую, минуя обёртки `BaseRepository.insert`/`update` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.insAll` | CURRENT | `batch((batch) => batch.insertAll(...))` — один Drift `batch()` на весь список, оборачивается в одну транзакцию |
| `packages/sheep_farm_database/lib/entities/disposal/disposal_dao.dart` | `DisposalsDao` | CURRENT | не переопределяет `insAll` из `BaseDao` |
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals` | CURRENT | схема таблицы; `id` — `nullable().autoIncrement()`, не передаётся явно при создании `Disposal` в bloc'е |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` | CURRENT | резолвит `'an_error_data'` в переведённую строку |
| `lib/l10n/app_ru.arb` | `an_error_data` | CURRENT | перевод ключа для текущей локали по умолчанию |

## Критерии приёмки

- При исключении из `_disposalRepository.saveDisposals(...)` (или, тем же
  `catch`, из `_animalsRepository.getAllByFilters`) внутри
  `on<AnimalDisposalEventSave>` bloc эмитит ровно: `AnimalDisposalSuccess
  (_data, isLoading: true, loadingMessage: 'saving_data')`, затем
  `AnimalDisposalMessage('an_error_data')`, затем `AnimalDisposalSuccess
  (_data)` — без иных промежуточных состояний.
- `getIt<Talker>().handle(e)` вызывается ровно один раз на пойманное
  исключение, без стек-трейса (`catch (e)`, не `catch (e, st)`).
- `_data`, переданный в финальный `AnimalDisposalSuccess`, — тот же объект,
  что был до попытки сохранения: выбранные животные, причина, целевая
  ферма/место, `fromPlace`, `filtersData` остаются без изменений.
- Поскольку `saveDisposals` делегирует единственному Drift `batch()`
  (`dao.insAll`), при исключении внутри него не сохраняется ни одна строка
  `Disposal` из батча выбранных животных — частичная запись невозможна.
- Диалог подтверждения (`ConfirmSaveDisposalDialog`) переходит в
  `_successSaveWidget` сразу после `bloc.add(const
  AnimalDisposalEventSave())`, независимо от того, каким состоянием
  впоследствии завершится `on<AnimalDisposalEventSave>` — успехом или
  `AnimalDisposalMessage('an_error_data')`.
- Единственный видимый пользователю сигнал об ошибке на этом пути — обычный
  `SnackBar` на `AnimalDisposalPage` с текстом ключа `an_error_data`; ни
  `AnimalDisposalFailure`, ни `showAppSnackBarError` здесь не участвуют.

## Связанные тесты

- `test/pages/animal_disposal_bloc_test.dart`, group `'UC-100 —
  AnimalDisposalEventSave'`, test `'ошибка сохранения ->
  AnimalDisposalMessage("an_error_data")'` — прямое покрытие:
  `disposalRepository.saveDisposals(any())` замокан на
  `thenThrow(Exception('db error'))`, после `AnimalDisposalEventSave()`
  проверяется, что поток состояний — ровно `[isLoading: true,
  AnimalDisposalMessage('an_error_data'), isLoading: false]`. (Групповое имя
  со старым номером `UC-100` — идентификатор будет переименован отдельным
  проходом; сам тест уже покрывает ровно этот сценарий.)
- Соседняя group `'UC-99 — AnimalDisposalEventSave'` в том же файле
  покрывает `CREATE_OK`-исход того же обработчика (включая ветку «между
  фермами владельца» в отдельной group `'UC-99 —
  AnimalDisposalEventSave (причина «между фермами владельца»)'`), не
  документируемый здесь.
- **Смежная находка, другой сценарий** — group `'НАХОДКА —
  AnimalDisposalEventStart без try/catch, необработанное исключение вместо
  AnimalDisposalFailure (см. ENT-16)'` в том же файле, тесты
  `'presetPlace ссылается на ферму, которой нет в локальной БД
  (farmRepository.getById -> null) -> Null check operator'` и `'единичное
  животное без привязанной фермы (animal.farm == null) -> Null check
  operator'` — показывают, что инициализация визарда
  (`AnimalDisposalEventStart`), а не сам `Save`, вообще не имеет
  `try/catch`: необработанное исключение происходит раньше, чем
  пользователь успевает нажать «Сохранить». Не тот же сценарий (другое
  событие-триггер, отсутствующий, а не «form-preserving», catch), но тот же
  bloc и та же сущность [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md).
- **TBD — теста нет** на сбой в `_animalsRepository.getAllByFilters` (тот же
  `catch`, но отдельно не проверен).
- **TBD — теста нет** на поведение самого диалога `ConfirmSaveDisposalDialog`/
  `_ConfirmSaveDisposalDialogState.saveDisposal` — ни успешный, ни ошибочный
  переход в `_successSaveWidget` не проверяется ни одним widget-тестом (в
  `test/` нет файла для `animal_disposal_page.dart`); вывод об
  «оптимистичном» UI сделан по чтению кода.

## Открытые вопросы и ограничения

- **Оптимистичный переход диалога в «успех» — намеренное решение или
  недосмотр?** Как и в структурно аналогичных сценариях для вакцинации
  ([UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md)) и
  взвешивания, ничего в коде/комментариях не фиксирует, был ли выбор
  `Future<void> Function() onSave` без ожидания реального результата
  bloc'а осознанным или случайным следствием того, что `onSave` вызывает
  `bloc.add(...)`, а не дожидается соответствующего состояния из
  `bloc.stream`.
- **Гонка между `AnimalDisposalEventExit` и асинхронным завершением
  `on<AnimalDisposalEventSave>`.** Поскольку диалог переходит в «успех»
  практически сразу после `bloc.add`, пользователь может нажать «Готово»
  (`widget.onExit` → `Navigator.of(context).pop()` +
  `bloc.add(const AnimalDisposalEventExit())` → в слушателе страницы
  `context.pop()`, закрывающий `AnimalDisposalPage` и, соответственно,
  `BlocProvider`-managed bloc) раньше, чем
  `on<AnimalDisposalEventSave>` успеет дойти до своего `catch` и эмитить
  `AnimalDisposalMessage`/`AnimalDisposalSuccess`. Если так — `emit` после
  закрытия bloc'а в используемой версии пакета `bloc` тихо ничего не делает,
  и пользователь вообще не увидит `SnackBar` об ошибке. Не проверено ни
  одним тестом и зависит от таймингов реального выполнения, но
  правдоподобно по чтению `animal_disposal_page.dart` и семантики emit
  после `isClosed`.
- **Видимость `SnackBar` за ещё открытым диалогом не проверена.** Если
  `AnimalDisposalMessage` приходит раньше, чем пользователь успел нажать
  «Готово» (диалог `showDialog` всё ещё открыт поверх `AnimalDisposalPage`),
  фактическая видимость `SnackBar` под модальным барьером диалога не
  подтверждена ни одним widget/integration-тестом — только чтением кода.
- **Почему `catch` здесь без стек-трейса (`catch (e)`), в отличие от
  `VaccinationBloc._onSave` (`catch (e, st)`)?** Ничего в коде/комментариях
  не объясняет это расхождение между структурно идентичными обработчиками
  разных под-областей одного модуля.
- **Отсутствие живого пути к ретраю** (см. «Альтернативные потоки») означает,
  что даже будь `_data` подготовлен к повторной попытке (он не изменяется
  при ошибке), пользователь не может инициировать `AnimalDisposalEventSave`
  повторно с этого экрана после того, как диалог уже показал «успех» —
  единственный выход отсюда — закрытие всей страницы визарда.
