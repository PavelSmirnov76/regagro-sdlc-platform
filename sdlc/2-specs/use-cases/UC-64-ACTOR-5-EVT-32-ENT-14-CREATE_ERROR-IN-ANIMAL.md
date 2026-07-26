# UC-64 — Запись вакцинации отказывает технически: `saveVaccination` бросает исключение, `VaccinationBloc._onSave` откатывается к прежнему `_data`

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `CREATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md)
(`vaccination.recorded`): пользователь подтверждает запись вакцинации для
одного или нескольких животных, но `VaccinationBloc._onSave`
(`lib/pages/vaccination/vaccination_bloc.dart`) ловит исключение, брошенное
при попытке сохранить строку `Vaccination` — техническая ошибка (Drift/БД),
не бизнес-отказ. `catch` эмитит `VaccinationMessage('an_error_data')`, затем
безусловно `VaccinationSuccess(_data)` — тот же `_data`, что был до попытки,
без каких-либо изменений: выбранные животные/вакцина/дата/болезни остаются
в состоянии.

Как и у аналогичного сценария для перемещения животных, диалог подтверждения
(`ConfirmSaveVaccinationDialog`) переходит в состояние «успех» практически
сразу после того, как `bloc.add(const VaccinationEventSave())` синхронно
поставил событие в очередь — не дожидаясь, пока `_onSave` реально завершит
(успешно или с ошибкой) попытку. Это верно для любого исхода
`VaccinationEventSave`, но именно в `ERROR`-исходе расхождение между тем, что
увидел пользователь, и тем, что реально произошло в БД, наиболее заметно.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`lib/pages/vaccination/vaccination_bloc.dart` целиком: `VaccinationBloc` не
объявляет и не использует `AuthRepository` ни в одном обработчике, включая
`_onSave` — в отличие от `AnimalMovementBloc`, здесь нет даже попытки прочитать
пользователя. Поле `Vaccination.author` (text?, [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md))
не заполняется этим потоком вовсе — `VaccinationsCompanion.insert(...)` в
`_onSave` не передаёт `author`, значение остаётся `Value.absent()`.

## CURRENT

### Основной поток

1. Пользователь проходит шаги визарда (`disease` → `vaccine` → `vaccinationDate`
   → для группы ещё `animals`) до последнего шага в
   `VaccinationData.currentSteps` — `VaccinationStep.animals` для батч-режима
   (`!isSingle`) или `VaccinationStep.vaccinationDate` для одиночного животного
   (`isSingle`). Оба случая рендерят кнопку через
   `_FloatingButtons._finishButtons`, которая по нажатию «Сохранить и завершить»
   открывает `showDialog(... ConfirmSaveVaccinationDialog(onSave: () async {
   bloc.add(const VaccinationEventSave()); }, onExit: ..., data: data))`
   (`lib/pages/vaccination/vaccination_page.dart`).
2. Пользователь нажимает «Подтвердить» в диалоге —
   `_ConfirmSaveVaccinationDialogState.saveVaccination()`:
   ```dart
   void saveVaccination() async {
     setState(() { isSaving = true; });
     await widget.onSave();
     setState(() { isSaving = false; isSaved = true; });
   }
   ```
   `widget.onSave` — это `() async { bloc.add(const VaccinationEventSave()); }`;
   тело лямбды не содержит `await`, поэтому `await widget.onSave()` резолвится
   сразу после того, как событие синхронно поставлено в очередь `Bloc`, а не
   после того, как `on<VaccinationEventSave>` реально отработает.
3. `setState(() { isSaving = false; isSaved = true; })` выполняется
   практически сразу — `AnimatedSwitcher` переключает тело диалога на
   `_successSaveWidget` (заголовок `vaccination_data_saved`, Lottie-анимация
   `Assets.imSuccessAnimation`, кнопка «Готово» → `widget.onExit`). Поле
   `isSaving` нигде не читается в `build()` — индикатор загрузки внутри
   диалога фактически никогда не рендерится.
4. Независимо от диалога, в `VaccinationBloc.on<VaccinationEventSave>`
   (`_onSave`) начинает выполняться реальная работа: сначала
   `emit(VaccinationSuccess(_data, isLoading: true, loadingMessage:
   'saving_data'))` — меняет состояние страницы под диалогом, самого диалога
   не касается (`_BodyBuilder` рендерит `CircularProgressIndicatorWithText`
   поверх формы, пока `isLoading == true`).
5. Внутри `try`: локальная копия `updatedVaccinationsForAddMore` инициализируется
   из `_data.vaccinationsForAddMore` (уже накопленные, но ещё не сохранённые
   батчи из предыдущих `VaccinationEventAddMore`, если они были). Если
   `_data.selectedAnimalIds` не пусты, выбраны вакцина/текст вакцины и задана
   `_data.vaccinationDate`, для текущего выбора строится дополнительный набор:
   при необходимости создаётся новая `Vaccine` (`await
   _vaccinesRepository.insert(VaccinesCompanion.insert(name:
   _data.vaccineText!.toLowerCase()))`, если введённый текст не совпал ни с
   одной существующей вакциной), затем для каждого `animalId` из
   `_data.selectedAnimalIds` собирается `VaccinationsCompanion.insert(...,
   sync: Value(false), createdAt: Value(DateTime.now()), updatedAt:
   Value.absent(), deletedAt: Value.absent())` и добавляется в
   `updatedVaccinationsForAddMore`. Если выбрана комплексная вакцина
   (`selectedComplexVaccine != null`), список болезней разворачивается через
   `_diseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId(...)` +
   `_diseasesRepository.getAllByIds(...)` — заново, на каждой итерации цикла
   по животным.
6. **Точка технического сбоя (этот сценарий).**
   ```dart
   for (final vaccination in updatedVaccinationsForAddMore.keys) {
     await _vaccinationRepository.saveVaccination(
       vaccination,
       updatedVaccinationsForAddMore[vaccination] ?? [],
     );
   }
   emit(VaccinationSuccess(_data));
   ```
   `_vaccinationRepository.saveVaccination(...)` брошенное исключение (в тесте
   — `thenThrow(Exception('db error'))` без ветвления по конкретной строке)
   перехватывается:
   ```dart
   } catch (e, st) {
     getIt<Talker>().handle(e, st);
     emit(VaccinationMessage('an_error_data'));
     emit(VaccinationSuccess(_data));
   }
   ```
   В отличие от `AnimalMovementBloc.on<AnimalMovementEventSave>`
   ([UC-55](UC-55-ACTOR-5-EVT-27-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), здесь
   `catch (e, st)` захватывает стек-трейс, и `Talker.handle(e, st)` вызывается
   с ним. `_data` в обработчике не переприсваивается — второй `emit` несёт тот
   же объект, что был передан в `emit` на шаге 4.
7. На `vaccination_page.dart` `BlocConsumer<VaccinationBloc,
   VaccinationState>` без `listenWhen` реагирует на `VaccinationMessage`:
   ```dart
   ScaffoldMessenger.of(context).showSnackBar(
     SnackBar(content: Text(AppLocalizations.of(context)!.tr(state.message))),
   );
   ```
   Обычный `SnackBar`, не хелпер `showAppSnackBarError`
   (`lib/widgets/app_snackbar.dart`). `'an_error_data'` — реальный ключ `.arb`
   (`lib/l10n/app_ru.arb`: `"Произошла ошибка при обработке данных"`),
   `AppLocalizations.tr` (`lib/l10n/app_localization.dart`) резолвит его в
   переведённую строку.
8. **Диалог подтверждения так и не узнаёт об ошибке.** Так как на шаге 2
   `await widget.onSave()` уже завершился и `isSaved` уже стал `true` ещё до
   того, как шаг 6 вообще начал выполняться, диалог остаётся на
   `_successSaveWidget` независимо от исхода реальной попытки сохранения.
   Единственный способ закрыть диалог после этого — кнопка «Готово»
   (`widget.onExit`) или крестик `CustomDialog.onClose`, который при
   `isSaved == true` тоже вызывает `widget.onExit()`:
   ```dart
   onExit: () {
     Navigator.of(context).pop();
     bloc.add(const VaccinationEventExit());
   },
   ```
   Оба пути ведут к одному и тому же: диалог закрывается,
   `on<VaccinationEventExit>` эмитит `VaccinationExit()`, слушатель страницы
   вызывает `context.pop()` — вся страница вакцинации закрывается. У
   пользователя нет пути остаться на этой же странице и повторить попытку
   после того, как диалог уже показал успех — хотя на уровне данных `_data`
   к повторной попытке готов (см. «Открытые вопросы»).

### Альтернативные потоки

- **Один и тот же `catch` покрывает четыре независимых по происхождению
  точки сбоя**: вставку новой `Vaccine` (`_vaccinesRepository.insert`, шаг 5),
  разворачивание комплексной вакцины
  (`_diseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId`),
  подгрузку болезней по id (`_diseasesRepository.getAllByIds`) и сам
  `_vaccinationRepository.saveVaccination` (протестированная точка, шаг 6).
  Отличить в UI, какая именно из четырёх операций отказала, по тексту
  сообщения невозможно — все реагируют одинаково.
- **Частичная запись при нескольких животных/накопленных батчах.**
  `updatedVaccinationsForAddMore` может содержать больше одной записи: и от
  текущего выбора (`for (final animalId in _data.selectedAnimalIds)` строит
  по одному `VaccinationsCompanion` на каждое выбранное животное), и от ранее
  накопленных через `VaccinationEventAddMore` батчей. Цикл на шаге 6 вызывает
  `saveVaccination` по одной записи за раз, без общей транзакции между
  итерациями — `insert(vaccination)` внутри `saveVaccination` коммитит
  строку `Vaccination` немедленно. Если исключение брошено на N-й записи,
  строки `1..N-1` уже сохранены в БД, `N`-я и все последующие — нет.
- **Новая `Vaccine` может остаться закоммиченной, даже если вся операция в
  итоге завершается `ERROR`.** Создание новой вакцины по свободному тексту
  (шаг 5) выполняется и коммитится ДО цикла `saveVaccination` (шаг 6) —
  если исключение произойдёт в этом цикле, уже вставленная строка `Vaccine`
  не откатывается: пользователь получит сообщение об ошибке, но новая вакцина
  в справочнике уже появится. `_data.vaccines` при этом не обновляется (в
  отличие от `_onAddMore`, который явно делает `vaccines: Wrapped(vaccines)`
  после аналогичной вставки) — в памяти bloc'а список вакцин остаётся
  устаревшим.
- **`saveDiseasesVaccinations` вызывается без `await` внутри
  `VaccinationsRepository.saveVaccination`**
  (`lib/repositories/vaccination/vaccinations_repository.dart`):
  ```dart
  Future<void> saveVaccination(
    VaccinationsCompanion vaccination,
    List<Disease> diseases,
  ) async {
    final vaccinationId = await insert(vaccination);

    _diseasesVaccinationsRepository.saveDiseasesVaccinations(
      vaccinationId,
      diseases.map((e) => e.id).toList(),
    );
  }
  ```
  `saveDiseasesVaccinations` (`lib/repositories/vaccination/diseases_vaccinations_repository.dart`)
  — реальная асинхронная работа с БД (`dao.clearByVaccinationId` +
  `insertAll`), но её `Future` не дожидается вызывающим кодом. Если `insert`
  строки `Vaccination` прошёл успешно, а `saveDiseasesVaccinations` бросает
  исключение асинхронно (уже после того, как `Future` от `saveVaccination`
  зарезолвился), это исключение **не попадёт** в `catch` `_onSave` —
  `_onSave` этой ошибки не увидит и продолжит цикл/эмитит успех, при этом
  строка `Vaccination` останется без связанных строк `DiseasesVaccinations`.
  Этот путь не документируется как `CREATE_ERROR` данного use-case (сценарий,
  который здесь специфицируется, — исключение из самого `saveVaccination`,
  как это воспроизводит существующий тест), но напрямую примыкает к нему как
  недостижимый для `_onSave`-catch источник несогласованности.
- **Ретрай тем же `_data` рискует задублировать уже сохранённые строки.**
  `_onSave` не обновляет `_data.vaccinationsForAddMore` по итогам своей
  работы (в отличие от `_onAddMore`) — ни при успехе, ни при ошибке. Если бы
  пользователь повторно инициировал `VaccinationEventSave` с тем же `_data`
  (гипотетически, поскольку в текущем UI до этого дело не доходит — см. шаг
  8 основного потока), цикл на шаге 5 заново построил бы те же
  `VaccinationsCompanion` для `_data.selectedAnimalIds`, включая animalId,
  чья вакцинация уже была успешно закоммичена до сбоя на более поздней
  итерации первой попытки.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  целевая сущность попытки создания. В зависимости от того, на какой из
  четырёх точек (альтернативные потоки) произошёл сбой, ноль, часть или (при
  сбое на самой ранней точке) все строки `Vaccination` из
  `updatedVaccinationsForAddMore` могут остаться несохранёнными.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только
  читается (через `animalId`, уже выбранный на более раннем шаге визарда);
  `_onSave` не перечитывает и не изменяет ни одного животного — в отличие от
  Movement, вакцинация не пишет ничего в `Animal`.
  `AnimalsRepository` в `_onSave` не используется вовсе.
- `Vaccine` (VAC-локальный справочник, без собственного `ENT` — см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) — может получить
  новую строку до точки сбоя (см. альтернативные потоки); при сбое эта
  вставка не откатывается.
- `Disease`, `ComplexVaccine` (VAC-локальные справочники, без собственного
  `ENT`) — только читаются, для разворачивания списка болезней вакцинации;
  само чтение — один из альтернативных источников исключения.
- `DiseasesVaccinations` (связочная таблица, без собственного `ENT`, часть
  описания [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)) — пишется
  внутри `saveVaccination`, но без `await` (см. альтернативные потоки);
  её отдельный сбой не относится к этому catch.

### Бизнес-правила

- Технический сбой (исключение из вставки/чтения на уровне Drift/DAO)
  классифицируется как `CREATE_ERROR`, а не `CREATE_REJECTED` — до этой точки
  guard-условие (`selectedAnimalIds.isNotEmpty && (selectedVaccine != null ||
  vaccineText не пуст) && vaccinationDate != null`) уже дало `true` для
  текущего выбора; отказ происходит на уровне хранения, не бизнес-валидации.
- Один и тот же `catch (e, st)` в `on<VaccinationEventSave>` покрывает
  четыре независимых по происхождению точки сбоя и реагирует на все
  одинаково — `VaccinationMessage('an_error_data')` плюс безусловный
  повторный `VaccinationSuccess(_data)`.
- Переключение диалога подтверждения в состояние «успех» **не зависит от
  результата** `on<VaccinationEventSave>` — оно управляется исключительно
  тем, что `bloc.add(...)` (постановка события в очередь) завершается
  раньше, чем сам обработчик. Верно для любого исхода, но для `ERROR`
  расхождение наиболее заметно.
- `saveVaccination` вызывается по одной `Vaccination`-записи за раз, без
  общей транзакции между итерациями цикла и без транзакции, охватывающей
  также предшествующую вставку новой `Vaccine` — технический сбой в
  середине оставляет БД в промежуточном состоянии, а обработчик bloc'а не
  различает это от сбоя, при котором вообще ничего не записалось.
- `VaccinationBloc` не читает и не использует авторизацию/пользователя ни в
  одном обработчике — `Vaccination.author` этим потоком не заполняется.
- Шаги визарда `VaccinationStep.doseAndUnit`/`series`/`injectionMethod`
  предусмотрены в `_createStepWidgetByStep`/`_createButtonByStep`/
  `stepSuccessesForButtons`, но `VaccinationData.currentSteps` их не
  включает ни при каком сочетании `isSingle`/`presetPlace` — соответствующие
  поля (`dose`, `selectedUnit`, `selectedInjectionMethod`, `series`,
  `productionDate`, `expirationDate`) остаются на значениях по умолчанию
  (`0`/`null`) в `VaccinationsCompanion`, которую пытается сохранить
  `_onSave`, если сценарий не задаёт их каким-то не найденным в `_onSave`/
  `_onStart` путём.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба ключевых альтернативных потока (частичная запись
по нескольким записям в цикле; необождённый `saveDiseasesVaccinations`)
прослеживаются чтением `lib/pages/vaccination/vaccination_bloc.dart`,
`lib/pages/vaccination/vaccination_page.dart`,
`lib/repositories/vaccination/vaccinations_repository.dart`,
`lib/repositories/vaccination/diseases_vaccinations_repository.dart`,
`lib/repositories/vaccination/vaccines_repository.dart`,
`lib/repositories/base_repository.dart`,
`packages/sheep_farm_database/lib/entities/base_dao.dart` и
`lib/l10n/app_localization.dart`. Отсутствие `await` внутри лямбды `onSave`
диалога и внутри `saveDiseasesVaccinations` перепроверено чтением
исходников напрямую, а не восстановлено по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventSave>` (`_onSave`) | CURRENT | единственный `try/catch` на четыре источника исключения; эмитит `VaccinationMessage('an_error_data')`, логирует через `Talker.handle(e, st)` со стек-трейсом, затем безусловно `VaccinationSuccess(_data)` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationData.currentSteps` | CURRENT | список шагов визарда — не включает `doseAndUnit`/`series`/`injectionMethod`, поэтому соответствующие поля остаются дефолтными в момент сбоя |
| `lib/pages/vaccination/vaccination_event.dart` | `VaccinationEventSave` | CURRENT | событие, запускающее сохранение |
| `lib/pages/vaccination/vaccination_state.dart` | `VaccinationMessage`, `VaccinationSuccess` | CURRENT | состояния, участвующие в сценарии ошибки |
| `lib/pages/vaccination/vaccination_page.dart` | `ConfirmSaveVaccinationDialog`, `_ConfirmSaveVaccinationDialogState.saveVaccination`, `_FloatingButtons._finishButtons` | CURRENT | единственный живой путь к `VaccinationEventSave`; диалог переходит в `_successSaveWidget` сразу после постановки события в очередь, независимо от исхода обработчика |
| `lib/pages/vaccination/vaccination_page.dart` | `BlocConsumer<VaccinationBloc, VaccinationState>.listener` | CURRENT | показывает `SnackBar` (не `showAppSnackBarError`) по `VaccinationMessage`; вызывается на каждое состояние — `listenWhen` не задан |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.saveVaccination` | CURRENT | `insert(vaccination)` awaited (протестированная точка сбоя), затем `saveDiseasesVaccinations` вызывается без `await` |
| `lib/repositories/vaccination/diseases_vaccinations_repository.dart` | `DiseasesVaccinationsRepository.saveDiseasesVaccinations` | CURRENT | реальная асинхронная работа с БД, вызывается без `await` из `saveVaccination` — исключение отсюда не попадёт в `catch` `_onSave` |
| `lib/repositories/vaccination/vaccines_repository.dart` | `VaccinesRepository` (наследует `BaseRepository.insert`) | CURRENT | альтернативный источник исключения (вставка новой вакцины по свободному тексту), выполняется до цикла `saveVaccination` |
| `lib/repositories/vaccination/diseases_complex_vaccines_repository.dart` | `DiseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId` | CURRENT | альтернативный источник исключения, вызывается по разу на каждое животное в цикле |
| `lib/repositories/vaccination/diseases_repository.dart` | `DiseasesRepository.getAllByIds` | CURRENT | альтернативный источник исключения |
| `lib/repositories/base_repository.dart` | `BaseRepository.insert` | CURRENT | `dao.ins(item)` — обёртка, используемая `saveVaccination`/`VaccinesRepository` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins` | CURRENT | непосредственная Drift-вставка одной строки |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` | CURRENT | схема таблицы, чья строка не коммитится при сбое `insert` |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` | CURRENT | резолвит `'an_error_data'` в переведённую строку |
| `lib/l10n/app_ru.arb` | `an_error_data` | CURRENT | перевод ключа для текущей локали по умолчанию |

## Критерии приёмки

- При исключении из `_vaccinationRepository.saveVaccination(...)` внутри
  цикла `on<VaccinationEventSave>` bloc эмитит `VaccinationMessage
  ('an_error_data')`, затем `VaccinationSuccess` — без промежуточных
  состояний, кроме уже эмитированного в начале обработчика
  `VaccinationSuccess(_data, isLoading: true, loadingMessage:
  'saving_data')`.
- То же самое эмитируется при исключении из вставки новой вакцины
  (`_vaccinesRepository.insert`), из `_diseasesComplexVaccinesRepository
  .getDiseaseIdsByComplexVaccineId` или из `_diseasesRepository.getAllByIds`
  — один и тот же `catch` без ветвления по источнику.
- `getIt<Talker>().handle(e, st)` вызывается ровно один раз на пойманное
  исключение, со стек-трейсом (`catch (e, st)`).
- `_data`, переданный в `VaccinationSuccess` после ошибки, — тот же объект,
  что был до попытки сохранения (не пересоздаётся catch-веткой): выбранные
  животные, вакцина, дата, болезни остаются без изменений.
- Строки `Vaccination`, для которых `saveVaccination` успел выполниться до
  того элемента цикла, на котором брошено исключение, остаются
  закоммиченными в БД.
- Диалог подтверждения (`ConfirmSaveVaccinationDialog`) переходит в
  `_successSaveWidget` сразу после `bloc.add(const VaccinationEventSave())`,
  независимо от того, каким состоянием впоследствии завершится
  `on<VaccinationEventSave>` — успехом или `VaccinationMessage
  ('an_error_data')`.

## Связанные тесты

- `test/pages/vaccination_bloc_test.dart`, group `'UC-64 — VaccinationBloc._onSave ERROR (локально)'`,
  test `'ветка "локально": saveVaccination бросает -> VaccinationMessage("an_error_data"), форма не сброшена'`
  — прямое покрытие: `vaccinationsRepository.saveVaccination(any(), any())`
  замокан на `thenThrow(Exception('db error'))`, после
  `VaccinationEventSave()` проверяется, что поток состояний содержит
  `VaccinationMessage` со значением `'an_error_data'` и что последнее
  состояние — `VaccinationSuccess` с `data.selectedAnimalIds == [1]`
  (форма не сброшена).
- Соседняя group `'UC-63 — VaccinationBloc._onSave (локально)'` в том же
  файле покрывает `CREATE_OK`-исход того же обработчика, не документируемый
  здесь.
- **TBD — теста нет** на сбой в `_vaccinesRepository.insert` (вставка новой
  вакцины по свободному тексту) — тот же `catch`, но отдельно не проверен.
- **TBD — теста нет** на сбой в `_diseasesComplexVaccinesRepository
  .getDiseaseIdsByComplexVaccineId`/`_diseasesRepository.getAllByIds`.
- **TBD — теста нет** на частичную запись при нескольких выбранных
  животных/накопленных батчах (сбой на N-й итерации цикла `saveVaccination`,
  1..N-1 уже закоммичены) — существующий тест использует ровно одно
  выбранное животное.
- **TBD — теста нет** на несогласованность от неawait-нутого
  `saveDiseasesVaccinations` внутри `VaccinationsRepository.saveVaccination`.
- **TBD — теста нет** на поведение самого диалога `ConfirmSaveVaccinationDialog`/
  `_ConfirmSaveVaccinationDialogState.saveVaccination` — ни успешный, ни
  ошибочный переход в `_successSaveWidget` не проверяется ни одним
  widget-тестом (в `test/` нет файла для `vaccination_page.dart`); вывод об
  «оптимистичном» UI сделан по чтению кода.

## Открытые вопросы и ограничения

- **Оптимистичный переход диалога в «успех» — намеренное решение или
  недосмотр?** Как и в структурно аналогичном сценарии для перемещения
  ([UC-55](UC-55-ACTOR-5-EVT-27-ENT-13-CREATE_ERROR-IN-ANIMAL.md)), ничего в
  коде/комментариях не фиксирует, был ли выбор `Future<void> Function()
  onSave` без ожидания реального результата бло­ка осознанным или случайным
  следствием того, что `onSave` вызывает `bloc.add(...)`, а не дожидается
  соответствующего состояния из `bloc.stream`.
- **Гонка между `VaccinationEventExit` и асинхронным завершением `_onSave`.**
  Пакет `bloc` (транзитивная зависимость `flutter_bloc: ^9.1.1`, версия
  `bloc-9.2.0` в `pubspec.lock`) реализует `emit` так, что `if (isClosed)
  return;` — вызов `emit(...)` после закрытия bloc'а тихо ничего не делает
  (не бросает исключение). Поскольку диалог переходит в «успех» практически
  сразу после `bloc.add`, пользователь может нажать «Готово»
  (`widget.onExit` → `bloc.add(const VaccinationEventExit())` →
  `context.pop()`, что закрывает `VaccinationPage` и приводит к закрытию
  `BlocProvider`-managed bloc'а) раньше, чем `_onSave` успеет дойти до своего
  `catch` и эмитить `VaccinationMessage`/`VaccinationSuccess`. Если так,
  пользователь вообще не увидит snackbar об ошибке — эмиты после `isClosed`
  просто теряются. Это не проверено ни одним тестом и зависит от таймингов
  реального выполнения (`VaccinationEventSave` и `VaccinationEventExit` —
  разные типы событий, обрабатываемые независимо, по умолчанию
  конкурентно), но подтверждается чтением исходников `vaccination_page.dart`
  и пакета `bloc`.
- **Незаawait-нутый `saveDiseasesVaccinations` — намеренная оптимизация или
  забытый `await`?** Ничего в коде не объясняет, почему
  `VaccinationsRepository.saveVaccination` не дожидается этого вызова, в то
  время как соседний метод `updateVaccination` в том же файле дожидается
  аналогичного вызова `saveDiseasesVaccinations` до `await update(vaccination)`.
- **Мёртвые шаги визарда.** `VaccinationStep.doseAndUnit`/`series`/
  `injectionMethod` реализованы в `_createStepWidgetByStep`/
  `_createButtonByStep`/`stepSuccessesForButtons`, но `VaccinationData
  .currentSteps` никогда их не включает — соответствующие поля формы
  недостижимы для заполнения через этот визард. Является ли это
  преднамеренным отключением шагов или недосмотром — не зафиксировано нигде
  в коде/комментариях.
- **`isSaving` в `_ConfirmSaveVaccinationDialogState` — мёртвое состояние**,
  тот же паттерн, что и в аналогичном диалоге для перемещения: выставляется,
  но не читается в `build()`.
- **Финальная ветка `onTap`, переданная `VaccinationPage` в `_FloatingButtons`
  (`else { ... bloc.add(const VaccinationEventSave()); }`), выглядит
  недостижимой.** Последний элемент `VaccinationData.currentSteps` всегда
  рендерится через `_finishButtons`/`ConfirmSaveVaccinationDialog`
  (`case VaccinationStep.animals`/`case VaccinationStep.vaccinationDate` с
  `data.isSingle`), а не через `_onTap`, который единственно приводит к
  вызову этой ветки `onTap`. Не удалось найти сочетание `isSingle`/
  `presetPlace`, при котором любой другой шаг оказался бы последним в
  `currentSteps`. Если наблюдение верно, единственный живой путь к
  `VaccinationEventSave` — диалог подтверждения, документированный выше.
