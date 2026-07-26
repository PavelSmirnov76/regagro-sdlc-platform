# UC-63 — Пользователь сохраняет вакцинацию для одного или нескольких животных — успех

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `CREATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — гость или
авторизованный, одинаково) проходит визард записи вакцинации
(`VaccinationBloc`/`VaccinationPage`) для одного предзаданного животного или для
нескольких выбранных животных места, выбирает болезни, вакцину (из справочника
или свободным текстом) и дату, подтверждает — для каждого выбранного животного
создаётся отдельная запись `Vaccination` (`sync: false`, `createdAt: now`,
локальная, без обращения к серверу), с собственным набором связанных болезней.
Happy-path сценарий события [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md)
(`vaccination.recorded`).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения. `VaccinationBloc` не импортирует и не проверяет `AuthRepository`
нигде в файле — вакцинация, как и перемещение, local-first: доступна одинаково
гостю и авторизованному пользователю, сохранение не делает ни одного сетевого
вызова. В отличие от `Movement` (`Movement.userId`), сохранённая `Vaccination`
вообще не хранит id пользователя, создавшего запись — колонка `author`
(text, nullable) не заполняется этим сценарием ни для гостя, ни для
авторизованного пользователя (см. «Бизнес-правила»).

## CURRENT

### Основной поток

1. Визард открывается одним из четырёх живых входов, все — без предзаполненной
   болезни/комплексной вакцины (`prefilledDiseaseId`/`prefilledComplexVaccineId`
   существуют как параметры `VaccinationPageArguments`, но ни один найденный
   вызывающий код в `lib/` их не передаёт — подтверждено `grep -rn
   "prefilledComplexVaccineId\|prefilledDiseaseId" lib/`, ноль совпадений вне
   самого `vaccination_bloc.dart`; см. «Открытые вопросы»):
   - `AnimalOperationsPage` (плитка «Вакцинация» для конкретного животного) →
     `VaccinationPageArguments.animal(animal: animal)`;
   - `OperationsPage` (плитка «Вакцинация» для места) →
     `VaccinationPageArguments.all(place: place)`;
   - `_MainContentState._onFabPressed`, ветка `Routes.animalVetCard` (FAB на
     экране ветеринарной карточки) →
     `VaccinationPageArguments.animal(animal: extra.animal)`;
   - `_MainContentState._onFabPressed`, ветка `Routes.animalVaccinations` (FAB
     на экране списка вакцинаций животного) — тот же вызов.
2. `VaccinationBloc` создаётся с этими аргументами; `_data` инициализируется
   сразу в конструкторе с `isSingle: arguments.isSingle`, `vaccinationDate:
   DateTime.now()` (дата вакцинации уже выставлена на «сегодня» ещё до
   `VaccinationEventStart`) и `presetPlace: arguments.presetPlace`; страница
   диспатчит `VaccinationEventStart()` в `BlocProvider.create`.
3. Обработчик `VaccinationEventStart`: грузит справочники (`vaccines`,
   `diseases`, `complexVaccines`, `injectionMethods` — отфильтрованные по
   `Constants.availableInjectionMethods`, `vaccinationTypes`, `units`),
   заполняет `filteredVaccines`/`filteredDiseases` тем же списком; ветка
   `isSingle`: перечитывает животное по id
   (`getAllAnimalsWithDetailsByFilters(ids: [arguments.animal!.animalId],
   isNotDeleted: null)`), и **только если оно найдено**
   (`animals.isNotEmpty`) — заполняет `selectedAnimalIds:
   [animals.first.animalId]` и сужает `filteredDiseases` по видам
   вакцинируемых животных (`DiseasesKindsRepository.getDiseasesKindsByKindIds`);
   ветка группы — грузит места фермы, и если передан `presetPlace`, сразу
   подгружает его животных (`_data.animals` в других use-case терминах —
   `animalsWithDetails`). Затем `_applyPrefilledDiseaseOrComplex()` — на всех
   четырёх живых входах не делает ничего, оба условия (`prefilledComplexVaccineId
   != null` / `prefilledDiseaseId != null`) ложны.
4. Реально проходимые шаги — `VaccinationData.currentSteps`: (место, только
   для группы без `presetPlace`) → **болезни** (`VaccinationStep.disease`,
   всегда) → **вакцина** (`VaccinationStep.vaccine`, всегда) → **дата**
   (`VaccinationStep.vaccinationDate`, всегда) → (**животные**, только для
   группы). Шаги `doseAndUnit`/`injectionMethod`/`series` определены в
   `enum VaccinationStep` и в `_Body._createStepWidgetByStep`, но **не входят
   в `currentSteps` ни при каком сочетании `isSingle`/`presetPlace`** — эти
   шаги физически никогда не рендерятся (см. «Бизнес-правила», «Открытые
   вопросы»).
5. Шаг «болезни» (`DiseaseStepPage`): множественный выбор через
   `MiltiSelectWidget` → `VaccinationEventChangeDisease(disease, isSelected)`
   — add/remove из `_data.selectedDiseases`, попутно сбрасывает
   `selectedComplexVaccine` на `null` и пересчитывает `filteredVaccines`;
   при `isSelected: true` дополнительно логирует выбор в
   `SelectionHistoryRepository.addOrUpdate(disease.name,
   SelectionHistoryType.disease, null)`.
6. Шаг «вакцина» (`VaccineStepPage`): `SearchDropdownField` — выбор из списка
   → `VaccinationEventChangeVaccine(vaccine)` (`selectedVaccine` записывается,
   выбор логируется в историю), либо ручной ввод текста →
   `VaccinationEventChangeVaccineText(text)` (`vaccineText` записывается,
   `selectedVaccine` **должен** сбрасываться в `null`, но фактически не
   сбрасывается — см. «Открытые вопросы», подтверждённый тестом баг). Поля
   `series`/`vaccinationType`/`productionDate`/`expirationDate` объявлены как
   параметры `VaccineStepPage` и как отдельные события/поля `VaccinationData`,
   но сам виджет не рендерит для них ни одного элемента UI (только
   создаёт неиспользуемые `TextEditingController`) — эти четыре поля не
   могут быть установлены пользователем этим экраном ни при каком действии.
7. Шаг «дата» (`VaccinationDateStepPage`): выбор даты вакцинации (по умолчанию
   — уже сегодня, из шага 2) и опционально даты следующей вакцинации →
   `VaccinationEventChangeVaccinationDate`/`VaccinationEventChangeNextVaccinationDate`.
8. Шаг «животные» (только групповой вход, `AnimalsStepPage`): множественный
   выбор чекбоксами → `VaccinationEventSelectAnimals(animals, isSelected)` —
   add/remove id из `Set` `selectedAnimalIds`. Кнопка перехода к диалогу
   подтверждения скрыта (`return null`, `_createButtonByStep`, кейс
   `VaccinationStep.animals`), пока `data.selectedAnimalIds` пуст — этот шаг
   физически не может быть завершён с нулём выбранных животных. Для
   одиночного входа последний шаг — «дата»: кнопка завершения показывается,
   если `vaccinationDateStepSuccess == true` (см. «Открытые вопросы» —
   эта проверка не гарантирует непустой `selectedAnimalIds`).
9. Кнопка завершения (`_finishButtons`) открывает `ConfirmSaveVaccinationDialog`
   (сводка: уникальные болезни из `vaccinationsForAddMore` ∪ `selectedDiseases`,
   счётчик `{выбрано животных} / {всего животных в списке}`). Пользователь
   нажимает «Подтвердить» → `_ConfirmSaveVaccinationDialogState.saveVaccination()`:
   `setState(isSaving: true)`, `await widget.onSave()`, `setState(isSaving:
   false, isSaved: true)`. Колбэк `onSave: () async { bloc.add(const
   VaccinationEventSave()); }` не содержит `await` перед диспатчем —
   `await widget.onSave()` возвращается сразу после синхронной постановки
   события в очередь bloc'а, не дожидаясь реального завершения обработчика
   (см. «Открытые вопросы», тот же паттерн, что и в
   [UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md) для перемещения).
10. Обработчик `VaccinationEventSave`:
    - эмитит `VaccinationSuccess(_data, isLoading: true, loadingMessage:
      'saving_data')`;
    - строит `updatedVaccinationsForAddMore` как копию `_data.vaccinationsForAddMore`
      (`Map<VaccinationsCompanion, List<Disease>>`);
    - если `_data.selectedAnimalIds` не пуст **и** (`selectedVaccine != null`
      **или** непустой `vaccineText`) **и** `vaccinationDate != null` —
      разрешает `finalVaccine`: если введён `vaccineText` без выбранного
      `selectedVaccine` — ищет вакцину с тем же именем без учёта регистра
      среди уже загруженных `_data.vaccines`; если не найдена — создаёт новую
      (`_vaccinesRepository.insert(VaccinesCompanion.insert(name:
      vaccineText.toLowerCase()))`, локальный объект `Vaccine(id: vaccineId,
      name: ...)` строится вручную, без повторного чтения из БД); затем для
      **каждого** `animalId` из `_data.selectedAnimalIds` строит
      `VaccinationsCompanion.insert(animalId:, vaccineId: finalVaccine.id,
      unitId: Value(selectedUnit?.id), dose: dose ?? 0,
      injectionMethodId: Value(selectedInjectionMethod?.id), vaccinationDate:,
      nextVaccinationDate: Value(...)/absent, vaccinationTypeId:
      Value(...)/absent, series: Value(...)/absent, productionDate:
      Value(...)/absent, expirationDate: Value(...)/absent, sync: const
      Value(false), createdAt: Value(DateTime.now()), updatedAt: absent,
      deletedAt: absent)`, разрешает список болезней (`selectedComplexVaccine
      != null` → `DiseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId`
      → `DiseasesRepository.getAllByIds`; иначе — `_data.selectedDiseases ??
      []`) и кладёт пару `companion -> diseases` в
      `updatedVaccinationsForAddMore`;
    - затем, **отдельным циклом**, для каждой записи в
      `updatedVaccinationsForAddMore` (включая только что построенные из
      текущей формы) вызывает `await _vaccinationRepository.saveVaccination(
      companion, diseases)`;
    - без исключения — `emit(VaccinationSuccess(_data))` (`isLoading`
      сброшен). Визард **не** закрывается автоматически — закрытие
      происходит по отдельному, явному `VaccinationEventExit`, диспатчимому
      только из кнопки «Готово» в диалоге после успеха.
11. `VaccinationsRepository.saveVaccination(vaccination, diseases)`:
    `vaccinationId = await insert(vaccination)` (→ `BaseDao.ins`,
    `InsertMode.insertOrReplace`; при отсутствующем `id` в `Companion` это —
    обычный insert с автоинкрементом); затем, **без `await`**,
    `_diseasesVaccinationsRepository.saveDiseasesVaccinations(vaccinationId,
    diseases.map((e) => e.id).toList())` (см. «Открытые вопросы» — гонка).
12. `DiseasesVaccinationsRepository.saveDiseasesVaccinations`: `await
    dao.clearByVaccinationId(vaccinationId)` (для новой записи — не находит
    ничего для удаления), затем `await insertAll(...)` — batch-вставка одной
    строки `DiseasesVaccination` на каждую болезнь.
13. Пользователь нажимает «Готово» (`isSaved == true`) → `widget.onExit`:
    `Navigator.of(context).pop()` закрывает диалог, затем `bloc.add(const
    VaccinationEventExit())` → `_onExit` эмитит `VaccinationExit` →
    `BlocConsumer.listener` в `VaccinationPage` реагирует `context.pop()` —
    закрывается вся страница визарда.

### Альтернативные потоки

- **Одиночное животное (`isSingle`)**: шаги «место» и «животные» отсутствуют
  в `currentSteps`; `selectedAnimalIds` уже заполнен на шаге `Start` (если
  животное найдено в БД по id) единственным элементом; кнопка завершения
  показывается на шаге «дата», как только `vaccinationDateStepSuccess ==
  true` — эта проверка не требует непустого `selectedAnimalIds` (см.
  «Открытые вопросы»).
- **Текст вакцины не совпадает ни с одной записью справочника** — новая
  `Vaccine` создаётся один раз на весь вызов `_onSave` (не на каждое
  животное) и переиспользуется для всех записей текущего сохранения.
- **Комплексная вакцина выбрана (`selectedComplexVaccine != null`)**: список
  болезней для сохраняемой записи берётся не из `selectedDiseases`, а
  разворачивается через
  `DiseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId` →
  `DiseasesRepository.getAllByIds`, отдельно на каждое выбранное животное
  (перед вызовом `saveVaccination`). **Механизм существует и работает в коде
  и в тестах уровня блока (`VaccinationEventAddMore`, ветка с комплексной
  вакциной), но недостижим ни с одного из четырёх живых входов в этот экран**
  — `selectedComplexVaccine` устанавливается только через
  `_applyPrefilledDiseaseOrComplex()` из `arguments.prefilledComplexVaccineId`,
  а этот параметр никем не передаётся (см. основной поток, шаг 1, и
  «Открытые вопросы»). В самом визарде нет ни одного элемента UI, который
  бы выбирал комплексную вакцину напрямую (`DiseaseStepPage` — это только
  множественный выбор отдельных `Disease`).
- **Сохранение после нескольких `VaccinationEventAddMore`**: `_onAddMore`
  копит по одной паре `companion -> diseases` в `_data.vaccinationsForAddMore`
  на каждый вызов (столько раз, сколько раз пользователь вызвал это
  событие), сбрасывая форму (`selectedAnimalIds`, `selectedVaccine`,
  `vaccineText`, `dose`, `selectedUnit`, `selectedInjectionMethod`,
  `vaccinationDate` — на новое «сейчас», `nextVaccinationDate`,
  `selectedVaccinationType`, `series`, `productionDate`, `expirationDate`)
  между накоплениями, но **не сохраняет ничего в БД сама** — реальная запись
  всех накопленных пар происходит только внутри `_onSave`, в одном общем
  цикле вместе с последней (текущей) формой. Итоговый эффект — несколько
  разных `Vaccination` за один `VaccinationEventSave`, с разными вакцинами
  и/или разными наборами болезней на разные подмножества животных.
  **Механизм полностью реализован и покрыт тестами на уровне
  `VaccinationBloc` (группа `'VaccinationEventAddMore'`), но `grep -rn
  "VaccinationEventAddMore\|\.add(.*AddMore" lib/` не находит ни одного
  места в `lib/`, кроме определения события и регистрации обработчика в
  самом `vaccination_bloc.dart` — ни один виджет `VaccinationPage` не
  диспатчит это событие.** Ни один из существующих тестов не проверяет
  комбинацию «несколько `AddMore`, затем `Save`» — тестируются по отдельности
  либо только `_onAddMore`, либо `_onSave` с одной формой (см. «Связанные
  тесты»).
- **Гость / нет текущей сессии**: поведение и результат идентичны —
  `VaccinationBloc` не читает `AuthRepository` вовсе, `Vaccination.author`
  не заполняется ни в одном из случаев.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность, совершающая переход: по одной новой строке на каждое выбранное
  животное (плюс по одной на каждую пару, накопленную через недостижимый
  `VaccinationEventAddMore`), все с `sync: false`, `createdAt: now`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только на
  чтение, для построения списка доступных для вакцинации животных
  (`getAllAnimalsWithDetailsByFilters`); этим сценарием не изменяется (в
  отличие от Movement, вакцинация не пишет ни одно поле `Animal`).
- `DiseasesVaccinations` (связочная таблица многие-ко-многим, свой `ENT` не
  заведён — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  «Связи») — по одной строке на каждую болезнь каждой сохранённой записи,
  вставляется отдельным вызовом сразу после вставки самой `Vaccination`.
- Справочники `Vaccine`, `Disease` (HANDBOOKS, [ENT-6](../entities/ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md)),
  `ComplexVaccine`, `Unit` ([ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md)),
  `InjectionMethod`, `VaccinationType` — читаются на `Start`; из них этим
  сценарием фактически пишется только `Vaccine` (при вводе нового текста
  вакцины, через `VaccinesRepository.insert`), остальные — только читаются.
- `Place`/`Farm` (модуль FARM, [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)/
  [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)) — только на чтение, для
  построения списка мест/животных группового входа; этим сценарием не
  изменяются.

### Бизнес-правила

- Одна запись `Vaccination` на одно животное — группового сохранения одной
  строкой на несколько животных не существует, тот же паттерн, что у
  [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement).
- Сохранение полностью локально: ни `_onSave`, ни `saveVaccination`, ни
  `saveDiseasesVaccinations` не делают ни одного сетевого вызова и не
  проверяют состояние сети.
- **Поля `dose`/`unitId`/`injectionMethodId`/`vaccinationTypeId`/`series`/
  `productionDate`/`expirationDate` в реально достижимом потоке всегда
  принимают значения по умолчанию** (`dose: 0`, остальные — `null`/`absent`):
  соответствующие шаги визарда (`doseAndUnit`, `injectionMethod`, и текстовые
  поля `series`/`vaccinationType`/`productionDate`/`expirationDate` внутри
  `VaccineStepPage`) не входят в `VaccinationData.currentSteps` и/или не
  рендерят элементов UI, которые вызывали бы соответствующие события —
  пользователь физически не может задать эти поля через этот экран сегодня.
- Список болезней сохраняемой записи — это `_data.selectedDiseases` в любом
  реально достижимом потоке (комплексная вакцина недостижима, см.
  «Альтернативные потоки»); если пользователь не выбрал ни одной болезни —
  сохраняется пустой список (`?? []`), поскольку выбор вакцины/даты уже
  достаточен для прохождения гейта на шаге 10, а болезнь отдельно не
  проверяется условием сохранения.
- Форма (`_data`) **не сбрасывается** после успешного `VaccinationEventSave`
  — в отличие от `_onAddMore`. `_onSave` строит и мутирует только локальную
  переменную `updatedVaccinationsForAddMore`, но никогда не записывает её
  обратно в `_data.vaccinationsForAddMore`, и не очищает
  `_data.selectedAnimalIds`/`selectedVaccine`/`selectedDiseases` и т.д.
- `Vaccination.author` не заполняется этим сценарием ни для гостя, ни для
  авторизованного пользователя — в отличие от `Movement.userId`, у
  `Vaccination` в текущем коде нет привязки к тому, кто её создал.
- Кнопка перехода к диалогу подтверждения на шаге «животные» (групповой
  вход) физически не отображается, пока `selectedAnimalIds` пуст — 0
  выбранных животных не может дойти до `VaccinationEventSave` этим путём.
  Для одиночного входа аналогичной защиты на шаге «дата» нет (см. «Открытые
  вопросы»).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован и работает как описано в CURRENT;
находки, перечисленные в «Открытые вопросы и ограничения», не блокируют его
выполнение для реально достижимых входов (без комплексной вакцины и без
`VaccinationEventAddMore`).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_operations/animal_operations_page.dart` | `AnimalOperationsPage` | CURRENT | вход №1 — вакцинация одного животного |
| `lib/pages/operations/operations_page.dart` | `OperationsPage` | CURRENT | вход №2 — вакцинация по месту (группа) |
| `lib/pages/main/main_page.dart` | `_MainContentState._onFabPressed` | CURRENT | входы №3/№4 — FAB на карточке/списке вакцинаций животного |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationPageArguments` (`.animal`/`.all`, `isSingle`, `prefilledDiseaseId`, `prefilledComplexVaccineId`) | CURRENT | аргументы точки входа; последние два параметра нигде не передаются живым кодом |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventStart>` | CURRENT | загрузка справочников, резолв животных/мест, `_applyPrefilledDiseaseOrComplex` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationData.currentSteps` | CURRENT | реально проходимые шаги; `doseAndUnit`/`injectionMethod`/`series` исключены при любых аргументах |
| `lib/pages/vaccination/steps/disease_step_page.dart` | `DiseaseStepPage` | CURRENT | множественный выбор болезней вручную |
| `lib/pages/vaccination/steps/vaccine_step_page.dart` | `VaccineStepPage` | CURRENT | выбор/ввод текста вакцины; поля series/type/production/expiration объявлены, но не рендерятся |
| `lib/pages/vaccination/steps/vaccination_date_step_page.dart` | `VaccinationDateStepPage` | CURRENT | выбор даты вакцинации/следующей вакцинации |
| `lib/pages/umiversal_step_page/animals_step_page.dart` | `AnimalsStepPage` | CURRENT | множественный выбор животных (групповой вход), кнопка скрыта при пустом выборе |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventChangeDisease>`, `.on<VaccinationEventChangeVaccine>`, `.on<VaccinationEventChangeVaccineText>`, `.on<VaccinationEventSelectAnimals>`, `.on<VaccinationEventChangeVaccinationDate>` | CURRENT | обработчики полей формы |
| `lib/pages/vaccination/vaccination_page.dart` | `_FloatingButtons._finishButtons`, `_createButtonByStep` | CURRENT | кнопка завершения, открытие диалога подтверждения |
| `lib/pages/vaccination/vaccination_page.dart` | `ConfirmSaveVaccinationDialog`, `_ConfirmSaveVaccinationDialogState.saveVaccination` | CURRENT | диалог подтверждения; `await widget.onSave()` не дожидается завершения `_onSave` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventSave>` | CURRENT | ядро сценария — построение `VaccinationsCompanion` на каждое животное, разворот комплексной вакцины, цикл `saveVaccination` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventAddMore>` | CURRENT | накопление формы в `vaccinationsForAddMore`; не диспатчится ни одним виджетом `lib/` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.saveVaccination` | CURRENT | `insert` + вызов `saveDiseasesVaccinations` без `await` |
| `lib/repositories/vaccination/diseases_vaccinations_repository.dart` | `DiseasesVaccinationsRepository.saveDiseasesVaccinations` | CURRENT | `clearByVaccinationId` + `insertAll` |
| `lib/repositories/vaccination/diseases_complex_vaccines_repository.dart` | `DiseasesComplexVaccinesRepository.getDiseaseIdsByComplexVaccineId` | CURRENT | разворот комплексной вакцины в список id болезней (недостижимая ветка) |
| `lib/repositories/vaccination/diseases_repository.dart` | `DiseasesRepository.getAllByIds` | CURRENT | резолв `Disease` по id для комплексной вакцины |
| `lib/repositories/vaccination/vaccines_repository.dart` | `VaccinesRepository.insert` (наследуется от `BaseRepository.insert`) | CURRENT | создание новой вакцины по свободному тексту |
| `lib/repositories/base_repository.dart` | `BaseRepository.insert`, `BaseRepository.insertAll` | CURRENT | делегируют в `dao.ins`/`dao.insAll` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.ins` | CURRENT | `insertOrReplace`, для новой строки без `id` — обычный insert с автоинкрементом |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` | CURRENT | таблица `Vaccination` |
| `packages/sheep_farm_database/lib/entities/vaccination/diseases/diseases_vaccinations_dao.dart` | `DiseasesVaccinationsDao.clearByVaccinationId` | CURRENT | удаление прежних связей болезней перед вставкой новых |
| `lib/pages/vaccination/vaccination_page.dart` | `_VaccinationPageState.build` (`BlocConsumer.listener`) | CURRENT | реагирует на `VaccinationExit` вызовом `context.pop`, на `VaccinationMessage` — snackbar |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc.on<VaccinationEventExit>` | CURRENT | эмитит `VaccinationExit`, закрывающий визард |

## Критерии приёмки

- По нажатию «Подтвердить» в `ConfirmSaveVaccinationDialog` (после того как
  `_data.selectedAnimalIds` не пуст, задана вакцина — выбранная или текстом
  — и задана `vaccinationDate`) выполняется ровно один вызов
  `VaccinationsRepository.saveVaccination` на каждый id из
  `_data.selectedAnimalIds` (плюс на каждую пару, накопленную через
  недостижимый `VaccinationEventAddMore`, если такая накоплена).
- Каждый переданный `VaccinationsCompanion` — новая запись с `animalId`,
  равным обрабатываемому животному, `vaccineId`, равным `finalVaccine.id`,
  `sync.value == false`, непустым `createdAt`.
- Если введён `vaccineText` без совпадения с существующей вакциной (без
  учёта регистра) и без выбранной `selectedVaccine` — выполняется ровно один
  вызов `VaccinesRepository.insert` за весь `VaccinationEventSave`, и
  полученный id используется как `vaccineId` для всех животных этого
  сохранения.
- Список болезней, переданный в `saveVaccination`, равен
  `_data.selectedDiseases` (или `[]`, если не выбрано ни одной) в любом
  реально достижимом потоке — комплексная вакцина не участвует, пока
  `selectedComplexVaccine` недостижим из UI.
- Обработчик `VaccinationEventSave` не делает ни одного сетевого вызова и не
  эмитит `VaccinationExit` напрямую — визард закрывается только по
  отдельному `VaccinationEventExit`.
- `AnimalsStepPage` (групповой вход) не показывает кнопку перехода к
  подтверждению, пока `selectedIds` пуст.

## Связанные тесты

- `test/pages/vaccination_bloc_test.dart`, group `'UC-63 — VaccinationBloc._onSave (локально)'`,
  test `'успех -> saveVaccination(sync:false) вызван для каждого выбранного
  животного, сеть не используется'` — основной поток этого use-case: один
  выбранный id + выбранная вакцина, `VaccinationEventSave`, проверка, что
  `saveVaccination` вызван ровно один раз с ожидаемыми `animalId`/`vaccineId`/
  `sync: false`. Имя группы использует старую нумерацию (`UC-81`) — не
  переименовывается в рамках этого файла.
- Группа `'UC-64 — VaccinationBloc._onSave ERROR (локально)'` в этом же файле
  в это use-case не входит — покрывает ветку `ERROR` (`saveVaccination`
  бросает исключение → `VaccinationMessage('an_error_data')`).
- `test/pages/vaccination_bloc_test.dart`, group `'VaccinationEventAddMore'`
  — покрывает накопление формы в `vaccinationsForAddMore`, включая ветку с
  комплексной вакциной, но **не** покрывает сам сценарий этого файла: ни
  один тест этой группы не диспатчит следом `VaccinationEventSave`, чтобы
  проверить реальное сохранение накопленных через `AddMore` записей в одном
  вызове `Save` (альтернативный поток «сохранение после нескольких
  add-more» из этого файла).
- `test/pages/vaccination_bloc_test.dart`, group
  `'VaccinationEventChangeVaccine/ChangeVaccineText'`, test `'БАГ:
  ChangeVaccineText после ранее выбранной вакцины из списка НЕ сбрасывает
  selectedVaccine — ...'` — не про сам `_onSave`, но напрямую объясняет,
  почему `finalVaccine` в шаге 10 основного потока может оказаться устаревшим
  значением вместо текста, только что введённого пользователем (см.
  «Открытые вопросы»).
- TBD — теста нет на уровне репозитория для
  `VaccinationsRepository.saveVaccination`: `test/repositories/vaccinations_repository_test.dart`
  не содержит ни одной группы с этим методом (`grep -n "saveVaccination"
  test/repositories/vaccinations_repository_test.dart` — 0 совпадений) —
  отсутствие `await` перед `saveDiseasesVaccinations` (см. «Открытые
  вопросы») не проверено ни одним тестом.
- TBD — теста нет на уровне, связывающем UI (`ConfirmSaveVaccinationDialog`
  → реальный `VaccinationBloc`) в одном widget/e2e-потоке — существующие
  тесты работают с блоком напрямую, без прохождения через диалог
  подтверждения.

## Открытые вопросы и ограничения

- **Комплексная вакцина недостижима из UI.** `selectedComplexVaccine`
  устанавливается только через `_applyPrefilledDiseaseOrComplex()` из
  `arguments.prefilledComplexVaccineId`; ни один из четырёх найденных
  вызывающих кодов (`AnimalOperationsPage`, `OperationsPage`,
  `_MainContentState._onFabPressed` ×2) этот параметр не передаёт, и в
  самом визарде нет элемента UI, выбирающего комплексную вакцину напрямую.
  Механизм полностью реализован и покрыт тестами уровня блока, но с текущих
  живых экранов вакцинация всегда сохраняется со списком отдельно выбранных
  болезней, никогда — через разворот комплексной вакцины.
- **`VaccinationEventAddMore` не диспатчится ни одним виджетом `lib/`.**
  Событие зарегистрировано и обработано в `VaccinationBloc`, читается для
  отображения (`vaccinationsForAddMore`/`animalIdsForAddMore` в
  `ConfirmSaveVaccinationDialog`), покрыто собственной группой тестов — но
  ни одна кнопка/действие в `VaccinationPage` его не вызывает. Альтернативный
  поток «сохранение после нескольких add-more», описанный в этом файле,
  сегодня достижим только программным диспатчем события напрямую (как в
  тестах), не через реальный экран.
- **`VaccinationsRepository.saveVaccination` не `await`-ит
  `saveDiseasesVaccinations`.** `Future<void> saveVaccination(...) async {
  final vaccinationId = await insert(vaccination);
  _diseasesVaccinationsRepository.saveDiseasesVaccinations(vaccinationId,
  ...); }` — последний вызов не содержит `await`, поэтому `Future`,
  возвращаемый `saveVaccination`, может завершиться раньше, чем реально
  завершится `clearByVaccinationId`/`insertAll` внутри
  `saveDiseasesVaccinations`. Цикл в `_onSave` (`await
  _vaccinationRepository.saveVaccination(...)`) ждёт только это укороченное
  завершение — гарантии, что связи `DiseasesVaccinations` уже физически
  записаны к моменту, когда цикл переходит к следующему животному или
  `_onSave` эмитит финальный `VaccinationSuccess`, нет. Не воспроизведено
  отдельным тестом, не разбирается глубже в рамках этого файла.
- **`ConfirmSaveVaccinationDialogState.saveVaccination()` не дожидается
  реального завершения `_onSave`** — колбэк `onSave` диспатчит
  `VaccinationEventSave` без `await` перед этим (`bloc.add(...)` синхронен),
  поэтому диалог переключается в состояние «успех» сразу после постановки
  события в очередь, не после того, как `saveVaccination`/`saveDiseasesVaccinations`
  реально отработали. Тот же паттерн, что и в
  [UC-54](UC-54-ACTOR-5-EVT-27-ENT-13-CREATE_OK-IN-ANIMAL.md) для
  перемещения. Не воспроизведено, не разбирается глубже.
- **Подтверждённый тестом баг `Wrapped(null)` в `_onChangeVaccineText`.**
  `copyWithWrapped(selectedVaccine: null, ...)` передаёт голый `null`
  (не `Wrapped(null)`), что на типе `Wrapped<Vaccine?>?` неотличимо от
  «аргумент не передан» — `selectedVaccine` не сбрасывается. Если
  пользователь сперва выбрал вакцину из списка, а затем отредактировал
  текстовое поле, `_data.selectedVaccine` остаётся старым не-`null`
  значением; в шаге 10 основного потока условие «использовать `vaccineText`»
  (`vaccineText != null && vaccineText.isNotEmpty && selectedVaccine ==
  null`) из-за этого ложно, и сохраняется **прежде выбранная**, а не
  только что введённая вакцина. Подтверждено тестом с явной пометкой «БАГ»
  (см. «Связанные тесты»); не исправлено, не разбирается глубже.
- **Форма не сбрасывается после успешного `Save`.** В отличие от
  `_onAddMore`, `_onSave` не пишет `updatedVaccinationsForAddMore` обратно в
  `_data` и не очищает `selectedAnimalIds`/`selectedVaccine`/`selectedDiseases`
  — при повторном (например, случайном двойном) диспатче
  `VaccinationEventSave` до навигации прочь со страницы форма и, если бы
  `AddMore` был достижим, `vaccinationsForAddMore` были бы обработаны и
  сохранены повторно. Не воспроизведено отдельным тестом.
- **Поля `dose`/`unitId`/`injectionMethodId`/`vaccinationTypeId`/`series`/
  `productionDate`/`expirationDate` всегда дефолтны в реально достижимом
  потоке**, поскольку соответствующие шаги исключены из `currentSteps`
  и/или не рендерятся `VaccineStepPage` — расхождение с описанием визарда в
  [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md) («вакцина →
  дата → доза/единица → способ введения»), которое в этой части кода не
  подтверждается: этих шагов пользователь сегодня не проходит.
- **`vaccinatedAnimals` никогда не заполняется.** Поле объявлено, есть
  параметр `copyWithWrapped`, но ни один обработчик события не вызывает его
  с непустым значением — `_hasAlreadyVaccinatedSelectedAnimals` всегда
  `false`, поэтому проверка «животное уже вакцинировано», заложенная в
  `vaccinationDateStepSuccess`, фактически ничего не блокирует.
- **Гипотетический тихий no-op для одиночного входа.** Если животное,
  переданное в `VaccinationPageArguments.animal`, не находится в БД на шаге
  `Start` (`animals.isEmpty`), `selectedAnimalIds` остаётся пустым, но
  кнопка завершения на шаге «дата» всё равно показывается, как только
  `vaccinationDateStepSuccess == true` (эта проверка не зависит от
  `selectedAnimalIds`). При таком диспатче `Save` внутренний `if` в шаге 10
  основного потока не выполняется, `updatedVaccinationsForAddMore` остаётся
  пустой картой, цикл сохранения не делает ни одного вызова — пользователь
  видит анимацию успеха, ничего не сохранено. Не воспроизведено ни одним
  тестом, чисто теоретический разбор кода.
