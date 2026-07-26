# UC-66 — Сохранение правки ещё не отправленной вакцинации отказывает технически: исключение перехватывается, снэкбар с нелокализованным ключом, экран не закрывается, форма не сбрасывается (ERROR)

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует ERROR-исход события [EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md)
(`vaccination.edited_unsent`) — тот же обработчик, что и соседний OK-сценарий
(`UnsentVaccinationEditBloc.on<UnsentVaccinationEditEventSave>`), но
`VaccinationsRepository.updateVaccination` бросает исключение. Исключение
перехватывается единым `catch` на весь обработчик `_onSave`, логируется через
`Talker.handle`, пользователю показывается снэкбар — но с текстом ключа
локализации, которого не существует ни в одном `.arb`-файле проекта (см.
«Открытые вопросы»), — экран редактирования не закрывается, `_data` не
меняется обработчиком ни на йоту, повторная попытка сохранения возможна сразу.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения; экран правки неотправленной вакцинации и его бизнес-логика не
делают различий по статусу авторизации (гость и авторизованный — одинаково).

## CURRENT

### Основной поток

1. **Предпосылка.** У пользователя есть хотя бы одна ещё не отправленная,
   только что созданная запись вакцинации (`Vaccination.createdAt != null`).
   Список хаба неотправленных вакцинаций
   (`UnsentVaccinationPage` → `UnsentVaccinationCubit.load()` →
   `VaccinationsRepository.getNotSyncVaccinationsWithDetails()`,
   `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` /
   `unsent_vaccination_cubit.dart`) по построению DAO-запроса
   (`VaccinationsDao.getNotSyncVaccinationsWithDetails`) возвращает только
   такие строки — единственный живой путь на этот экран (см.
   [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), «НАХОДКА» про
   недостижимую ветку правки уже синхронизированной записи).
2. Пользователь нажимает карточку в списке — `_VaccinationCard.onTap`
   (`unsent_vaccination_page.dart`) вызывает
   `context.pushNamed2(Routes.unsentVaccinationEdit, extra: v.id)`.
3. `UnsentVaccinationEditPage` (`lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart`)
   читает `vaccinationId` из `extra` и создаёт
   `UnsentVaccinationEditBloc(vaccinationId: vaccinationId)..add(const UnsentVaccinationEditStart())`.
   `on<UnsentVaccinationEditStart>` подгружает запись через
   `_vaccinationRepository.getVaccinationsWithDetails(ids: [vaccinationId]).first`
   и наполняет `_data` текущими значениями (`vaccine`, `unit`,
   `injectionMethod`, `injectionPlace`, `dose`, даты и т.д.), затем эмитит
   `UnsentVaccinationEditSuccess(_data, updateControllers: true)` — это
   успешный запуск экрана, предпосылка сценария, не его часть.
4. Пользователь правит поля формы — каждое изменение уходит отдельным
   `UnsentVaccinationEditEventChange...`-событием, меняющим только `_data` в
   памяти (без записи в БД).
5. Пользователь нажимает кнопку сохранения — `RElevatedButton` с
   `key: const Key('save_button')` в `_Body.build`. `onTap` сначала вызывает
   `formKey.currentState?.validate() == true`; только тогда диспатчится
   `UnsentVaccinationEditEventSave()` — сценарий этого use-case начинается
   **после** успешной клиентской валидации формы, отказ здесь никогда не
   является отказом валидации.
6. `on<UnsentVaccinationEditEventSave>` (`_onSave`) выполняется целиком внутри
   одного `try`: эмитит `UnsentVaccinationEditInProgress()`, определяет
   `finalVaccine` (берётся из `_data.vaccine`, либо ищется/создаётся по
   `_data.vaccineText`), собирает `VaccinationsCompanion` с `id:
   Value(vaccinationId)` и полями формы, при этом `updatedAt` остаётся
   `Value.absent()`, потому что `_data.vaccination?.createdAt != null`
   (ветка «ещё не отправлена», единственная достижимая, см. шаг 1).
7. `await _vaccinationRepository.updateVaccination(updatedVaccination,
   _data.selectedDiseases ?? [])` **бросает исключение** — это ветка, прямо
   воспроизведённая тестом: мок `vaccinationsRepository.updateVaccination(any(),
   any())` настроен `thenThrow(Exception('db error'))`.
8. Исключение перехватывается `catch (e, st)`: `getIt<Talker>().handle(e, st)`
   логирует исключение вместе со стек-трейсом (в отличие от аналогичной ERROR
   ветки `AnimalEdit`/`UnsentAnimalEdit`, где `Talker.error(e)` вызывается без
   стека — см. [UC-47](UC-47-ACTOR-5-EVT-23-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)).
9. Сразу после логирования эмитится
   `UnsentVaccinationEditMessage('error_saving_vaccination')`.
10. Сразу за ней эмитится `UnsentVaccinationEditSuccess(_data)` —
    **без** предшествующего `UnsentVaccinationEditExit()`. Важно: `_data` —
    та же самая ссылка, что была накоплена до нажатия «Сохранить»; локальные
    переменные `finalVaccine`/`finalUnit`/`updatedVaccination` этим
    обработчиком в `_data` не записываются ни при успехе, ни при ошибке —
    состояние формы после отказа идентично состоянию непосредственно перед
    сохранением.
11. `UnsentVaccinationEditPage`'s `BlocConsumer.listener`
    (`unsent_vaccination_edit_page.dart`) реагирует на `Message`:
    `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(
    AppLocalizations.of(context)!.tr(state.message))))` — обычный
    `ScaffoldMessenger`, не через `lib/widgets/app_snackbar.dart`. Ветка
    `else if (state is UnsentVaccinationEditExit) Navigator.of(context).pop();`
    не срабатывает — экран остаётся открытым.
12. `AppLocalizations.of(context)!.tr('error_saving_vaccination')`
    (`lib/l10n/app_localization.dart`, `AppLocalizationsExtension.tr`) не
    находит подходящего `case` в своём ручном `switch` — ключ
    `'error_saving_vaccination'` не заведён ни в одном из `.arb`-файлов
    проекта — и попадает в `default: return key;`. Пользователь буквально
    видит в снэкбаре нелокализованную строку `error_saving_vaccination`, а не
    человекочитаемый текст (см. «Открытые вопросы»).
13. Никакого retry/отката ранее выполненных операций внутри `try` нет —
    пользователь может нажать «Сохранить» повторно с теми же или изменёнными
    значениями немедленно.

### Альтернативные потоки

- **Исключение бросает не `updateVaccination`, а построение `finalVaccine`.**
  Если `_data.vaccineText` непусто и `_data.vaccine == null` (пользователь
  ввёл свободный текст, не совпадающий ни с одним элементом
  `_data.vaccines`), `_onSave` сначала вызывает `_vaccinesRepository.insert(
  VaccinesCompanion.insert(name: ...))`, создавая новую строку `Vaccine`.
  Если эта вставка успевает пройти, но последующий `updateVaccination`
  бросает — новая строка `Vaccine` **не откатывается**: вставка и
  `updateVaccination` не объединены в одну транзакцию. Повторное нажатие
  «Сохранить» с тем же текстом вставит ещё одну дублирующую строку `Vaccine`,
  потому что `_data.vaccine` этим обработчиком не обновляется (локальная
  переменная `finalVaccine` в `_data` не записывается). Не покрыто отдельным
  тестом.
- **Латентный null-check на `unit`/`injectionMethod`, а не отказ репозитория.**
  `VaccinationsCompanion` в `_onSave` строит `unitId: Value(finalUnit?.id ??
  _data.unit!.id)` и `injectionMethodId: Value(_data.injectionMethod!.id)` —
  оба через force-unwrap (`!`), хотя оба поля нативно nullable: `unitId` и
  `injectionMethodId` в таблице `Vaccinations`
  (`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart`)
  объявлены `integer().nullable()`, а `Unit? unit`/`InjectionMethod?
  injectionMethod` в `VaccinationWithDetails` — тоже nullable. Клиентский
  валидатор этих полей (`_selectFlagValidator`, `unsent_vaccination_edit_page.dart`)
  проверяет только служебный флаг `isUnitSuccess`/`isInjectionMethodSuccess`,
  который в `UnsentVaccinationEditData()` по умолчанию `true` и переключается
  в `false` только явным изменением соответствующего поля пользователем — **не
  реальное значение поля**. Если открываемая запись изначально имеет `unit ==
  null` и/или `injectionMethod == null` (обе колонки допускают это, и
  `VaccinationBloc` — создающий блок, из которого эти строки попадают в хаб —
  сам пишет `unitId`/`injectionMethodId` через `Value(x?.id)`, то есть тоже не
  требует их обязательного заполнения), и пользователь не трогает именно эти
  два поля, `formKey.currentState.validate()` проходит без единой ошибки, а
  `_onSave` бросает `Null check operator used on a null value` — тот же самый
  `catch`, то же самое сообщение, тот же откат в `Success(_data)` без `Exit`.
  Неотличимо от протестированного отказа `updateVaccination` по итоговому
  поведению бота. Не покрыто отдельным тестом.
- **OK-исход того же обработчика — не входит в этот сценарий.** Если
  `updateVaccination` не бросает исключение, `_onSave` эмитит
  `UnsentVaccinationEditMessage('vaccination_saved')`, затем
  `UnsentVaccinationEditExit()`, затем финальный `UnsentVaccinationEditSuccess(
  _data)` (то же, что в тестовой группе `'UC-65 — UnsentVaccinationEditBloc._onSave (createdAt != null, ещё не отправлена)'`
  того же файла) — соседний, не документируемый здесь исход.
- **Правка уже синхронизированной записи (`createdAt == null`) — технически
  существует в том же обработчике, но недостижима из UI.** Единственный вход в
  этот экран — хаб неотправленных, чья выборка (шаг 1) по определению не
  содержит таких строк; второй маршрут на этот же `UnsentVaccinationEditPage`
  (`Routes.unsentVaccinationEditFromEditable`) навигируется только из
  `vaccination_card_page.dart`, который сам нигде не открывается (см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)). Не входит в этот
  ERROR use-case.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность, которую пытается обновить сценарий; сегмент `ENT` имени файла.
  При отказе на `await update(vaccination)` сама строка `Vaccinations` не
  меняется (drift `replace` — атомарный DML). Но см. следующий пункт про
  `DiseasesVaccinations` — возможное частичное изменение связанных данных той
  же сущности при использовании реальной, не замоканной реализации
  `updateVaccination`.
- Связочная таблица `DiseasesVaccinations` (часть [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  не имеет отдельного `ENT`) — `VaccinationsRepository.updateVaccination`
  (`lib/repositories/vaccination/vaccinations_repository.dart`) вызывает
  `_diseasesVaccinationsRepository.saveDiseasesVaccinations(...)` **без
  `await`** (fire-and-forget), а сразу следом — `await update(vaccination)`.
  Это значит, что запись/перезапись связок «вакцинация↔болезни»
  (`clearByVaccinationId` + `insertAll`,
  `lib/repositories/vaccination/diseases_vaccinations_repository.dart`)
  запускается независимо и продолжает выполняться в фоне даже если
  `update(vaccination)` тут же бросает исключение — итоговая ошибка,
  показанная пользователю («не сохранено»), не гарантирует, что список
  болезней вакцинации не изменился. Существующий тест мокает
  `VaccinationsRepository.updateVaccination` целиком (через
  `MockVaccinationsRepository`), поэтому эту деталь реальной реализации не
  проверяет — установлено только чтением кода (см. «Открытые вопросы»).
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  только: `_data.vaccination!.animal.animal.id` используется как
  `animalId` в собираемом `VaccinationsCompanion`; этим сценарием не
  изменяется.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается из `_data.unit`; при `null` — см. «Альтернативные
  потоки», источник null-check исключения.
- Справочники `Vaccine`, `InjectionMethod`, `InjectionPlace` (VAC-локальные,
  без собственного `ENT` — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md))
  — `Vaccine` может получить новую строку как побочный эффект попытки
  сохранения (см. «Альтернативные потоки»); `InjectionMethod` — источник
  второго null-check пути.

### Бизнес-правила

- Единый `catch (e, st)` объединяет все возможные причины отказа внутри
  `_onSave` (реальное исключение репозитория при `update(vaccination)`,
  создание новой строки `Vaccine`, null-check на `unit`/`injectionMethod`) в
  один и тот же исход — сообщение не несёт информации о том, какая именно
  причина сработала.
- Клиентская валидация формы (`formKey.currentState.validate()`) —
  предшествующий диспатчу `EventSave` гейт на уровне виджета, но не
  гарантирует, что все поля, которые обработчик читает через force-unwrap
  (`unit`, `injectionMethod`), реально не `null` — валидатор проверяет только
  отдельный булев флаг, не значение поля (см. «Альтернативные потоки»).
- Сообщение об ошибке — ключ `'error_saving_vaccination'`, специфичный для
  этого обработчика (не переиспользуемый в других bloc/cubit проекта, в
  отличие от `'an_error_data'` в [UC-47](UC-47-ACTOR-5-EVT-23-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)),
  но при этом полностью нелокализованный: ни в одном `.arb`-файле, ни в
  ручном мэппинге `AppLocalizationsExtension.tr` этого ключа нет.
- Экран не закрывается и не сбрасывает введённые пользователем значения —
  повторная попытка сохранения возможна немедленно.
- Обработчик не откатывает уже выполненные до отказа шаги (создание
  `Vaccine`, фоновый вызов `saveDiseasesVaccinations`) — нет общей
  транзакции, оборачивающей всё содержимое `try`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — основной поток (исключение из `VaccinationsRepository.updateVaccination`)
полностью прослеживается чтением кода и покрыт тестом на уровне блока.
Альтернативные пути к тому же самому исходу (создание `Vaccine` без отката,
null-check на `unit`/`injectionMethod`, фоновый вызов
`saveDiseasesVaccinations` без `await`) архитектурно не заблокированы —
они реально достижимы, но не сопровождаются отдельным тестом (см. «Связанные
тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage` (`_VaccinationCard.onTap` → `context.pushNamed2(Routes.unsentVaccinationEdit, extra: v.id)`) | CURRENT | точка входа — карточка из хаба неотправленных вакцинаций |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | наполняет список хаба через `getNotSyncVaccinationsWithDetails` — источник предпосылки `createdAt != null` |
| `lib/pages/routes.dart` | `Routes.unsentVaccinationEdit` (`CustomGoRoute.fade`) | CURRENT | регистрация маршрута экрана правки |
| `lib/pages/routes.dart` | `Routes.unsentVaccinationEditFromEditable` | CURRENT | второй, недостижимый на практике маршрут на тот же экран (см. «Альтернативные потоки») |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart` | `_UnsentVaccinationEditPageState.build` → `BlocConsumer.listener` | CURRENT | показывает `SnackBar` (обычный `ScaffoldMessenger`, не `app_snackbar.dart`) по `Message`; `pop()` только по `Exit` (не эмитится в этой ветке) |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart` | `_Body` → `RElevatedButton` (`key: 'save_button'`) | CURRENT | гейт клиентской валидации формы перед диспатчем `UnsentVaccinationEditEventSave` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart` | `_selectFlagValidator` | CURRENT | валидатор `vaccine`/`unit`/`injectionMethod`/`injectionPlace` — проверяет только `isXSuccess`-флаг, не фактическое значение поля |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditBloc._onSave` | CURRENT | единый `try/catch`; в `catch` — `Talker.handle(e, st)` + `emit(Message('error_saving_vaccination'))` + `emit(Success(_data))`, без `Exit` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditData` (конструктор, `isUnitSuccess`/`isInjectionMethodSuccess` по умолчанию `true`) | CURRENT | источник латентного null-check пути (см. «Альтернативные потоки») |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_event.dart` | `UnsentVaccinationEditEventSave` | CURRENT | событие без полей — весь payload берётся из накопленного `_data` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_state.dart` | `UnsentVaccinationEditMessage`, `UnsentVaccinationEditSuccess`, `UnsentVaccinationEditExit` | CURRENT | состояния этой ветки (`Message`+`Success`) и соседней успешной ветки (дополнительно `Exit`) |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.updateVaccination` | CURRENT | протестированная точка отказа (мок); реальная реализация вызывает `saveDiseasesVaccinations` без `await`, затем `await update(vaccination)` |
| `lib/repositories/vaccination/diseases_vaccinations_repository.dart` | `DiseasesVaccinationsRepository.saveDiseasesVaccinations` | CURRENT | вызывается без `await` внутри `updateVaccination` — исключение отсюда не попадает в `try/catch` бота |
| `lib/repositories/vaccination/vaccines_repository.dart` | `VaccinesRepository.insert` | CURRENT | побочная вставка новой строки `Vaccine` при свободном тексте — не откатывается при последующем отказе `updateVaccination` |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | `dao.upd(item)` — реальная точка исключения, покрытая тестом через мок репозитория целиком |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — реальный drift-вызов |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` (`unitId`, `injectionMethodId` — `integer().nullable()`) | CURRENT | источник nullable-полей, задействованных в латентном null-check пути |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `VaccinationWithDetails` (`Unit? unit`, `InjectionMethod? injectionMethod`) | CURRENT | прокидывает nullable-поля в `_data` при `_onStart` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc` (сохранение через `unitId: Value(finalUnit?.id)`, `injectionMethodId: Value(_data.selectedInjectionMethod?.id)`) | CURRENT | создающий блок — тоже не требует обязательного заполнения `unit`/`injectionMethod`, подтверждает достижимость null-значений в записях, попадающих в хаб |
| `lib/l10n/app_localization.dart` | `AppLocalizationsExtension.tr` (`default: return key;`) | CURRENT | подтверждает, что нераспознанный ключ `'error_saving_vaccination'` показывается как есть, без перевода |
| `lib/injection_container.dart` | регистрация `TalkerFlutter.init` | CURRENT | источник синглтона `getIt<Talker>()`, используемого в `catch`-ветке |

## Критерии приёмки

- Если `_data.vaccination != null` и `VaccinationsRepository.updateVaccination`
  бросает исключение, `UnsentVaccinationEditBloc` эмитит ровно
  `UnsentVaccinationEditMessage('error_saving_vaccination')` и затем
  `UnsentVaccinationEditSuccess(_data)`; `add(UnsentVaccinationEditEventSave())`
  не приводит к необработанному исключению снаружи бота (`completes`, не
  `throwsA(...)`).
- В этой ветке `UnsentVaccinationEditExit` не эмитится ни разу — экран не
  закрывается.
- `_data` (в т.ч. `_data.vaccination`, все текущие значения полей формы)
  после ошибки идентичен состоянию непосредственно перед диспатчем
  `UnsentVaccinationEditEventSave` — обработчик не производит частичных или
  ошибочных мутаций состояния экрана.
- `getIt<Talker>().handle(e, st)` вызывается ровно один раз на попытку
  сохранения, предшествуя эмиссии `UnsentVaccinationEditMessage`.

## Связанные тесты

`test/pages/unsent_vaccination_edit_bloc_test.dart`, group `'UC-66 — UnsentVaccinationEditBloc._onSave ERROR (createdAt != null)'`,
test `'updateVaccination бросает -> UnsentVaccinationEditMessage("error_saving_vaccination"), форма не сброшена'`:
мок `vaccinationsRepository.updateVaccination(any(), any())` настроен
`thenThrow(Exception('db error'))`, блок доводится до
`UnsentVaccinationEditSuccess` (`buildStartedBloc`), затем добавляется
`UnsentVaccinationEditEventSave()`; тест накапливает все состояния потока
через подписку (`bloc.stream.listen(states.add)`), ждёт `Success`, проверяет,
что среди накопленных состояний встречается
`UnsentVaccinationEditMessage('error_saving_vaccination')`, и что последнее
состояние — `UnsentVaccinationEditSuccess` с `data.vaccination?.id == 13`
(тем же `id`, что был у записи до отказа).

**TBD — теста нет** на альтернативные точки отказа того же `catch`:
`VaccinationsRepository.updateVaccination` в существующем тесте мокается
целиком — сценарии «`VaccinationsRepository.updateVaccination` не мокан, а
реальная реализация, и `_diseasesVaccinationsRepository.saveDiseasesVaccinations`
бросает исключение фоново», «`_vaccinesRepository.insert` бросает при
свободном тексте вакцины» и «`_data.unit`/`_data.injectionMethod` — `null`,
form-валидатор их пропускает, `_onSave` падает на force-unwrap» не
воспроизведены ни одним тестом.

## Открытые вопросы и ограничения

- **Ключ локализации `'error_saving_vaccination'` не существует нигде в
  проекте.** Проверено поиском по всем `.arb`-файлам (`lib/l10n/app_*.arb`) и
  по ручному `switch` в `AppLocalizationsExtension.tr`
  (`lib/l10n/app_localization.dart`) — совпадений нет; `default: return key;`
  возвращает сам ключ. Пользователь при отказе сохранения видит в снэкбаре
  буквально строку `error_saving_vaccination`, а не текст на каком-либо из
  поддерживаемых языков (в отличие от переиспользуемого, но осмысленного
  `'an_error_data'` в аналогичной ветке [UC-47](UC-47-ACTOR-5-EVT-23-ENT-11-UPDATE_ERROR-IN-ANIMAL.md)).
  Не устраняется в рамках этого документирующего прохода (TARGET == CURRENT).
- **`updateVaccination` не атомарен: связки болезней пишутся без ожидания
  результата.** `VaccinationsRepository.updateVaccination` вызывает
  `_diseasesVaccinationsRepository.saveDiseasesVaccinations(...)` без
  `await`, затем `await update(vaccination)` — оба вызова выполняются
  конкурентно. При реальном (не замоканном полностью, как в существующем
  тесте) отказе `update(vaccination)` фоновый вызов, обновляющий
  `DiseasesVaccinations`, может успеть завершиться независимо от исхода
  «главной» операции — итоговая ошибка, показанная пользователю, не
  гарантирует консистентности между полями самой записи `Vaccination` и её
  списком болезней. Не покрыто тестом — установлено только чтением кода.
- **Латентный null-check на `unit`/`injectionMethod` при незаполненных
  исходных данных.** `_selectFlagValidator` в форме проверяет только
  вспомогательный флаг (`isUnitSuccess`/`isInjectionMethodSuccess`, по
  умолчанию `true`), не фактическое значение `data.unit`/`data.injectionMethod`
  — при этом `_onSave` строит `VaccinationsCompanion` через force-unwrap
  (`_data.unit!.id`, `_data.injectionMethod!.id`). Обе колонки — nullable в
  БД, и создающий блок (`VaccinationBloc`) не требует их обязательного
  заполнения при первом сохранении. Запись с изначально `null` `unit`/
  `injectionMethod`, открытая на редактирование без прикосновения к этим
  двум полям, гарантированно попадёт в этот же ERROR-исход по совершенно
  другой причине (программная ошибка null-safety, а не отказ БД/сети) —
  пользователю это неотличимо. Не покрыто тестом.
- **Побочная вставка `Vaccine` не откатывается при последующем отказе.** Если
  свободный текст вакцины не совпал ни с одной существующей записью,
  `_vaccinesRepository.insert(...)` создаёт новую строку `Vaccine` до вызова
  `updateVaccination`; при отказе последнего эта строка остаётся в
  справочнике, а повторное нажатие «Сохранить» с тем же текстом создаст
  дубликат (`_data.vaccine` не обновляется обработчиком). Не покрыто тестом.
- **Единый `catch` не различает ни одну из перечисленных причин по тексту
  сообщения** — тот же класс ограничения, что и в аналогичном сценарии
  модуля ANIMAL, см. [UC-47](UC-47-ACTOR-5-EVT-23-ENT-11-UPDATE_ERROR-IN-ANIMAL.md).
