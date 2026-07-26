# UC-65 — Пользователь редактирует ещё не отправленную вакцинацию через хаб неотправленных, сохранение успешно

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает ещё не отправленную (новую, `createdAt != null`) запись
вакцинации из хаба неотправленных (`UnsentVaccinationPage`) и сохраняет правку
через `UnsentVaccinationEditBloc.on<UnsentVaccinationEditEventSave>` (`_onSave`)
без исключения. Поля записи обновляются на месте; `updatedAt` остаётся
`Value.absent()`, потому что исходная запись уже была `createdAt != null` —
запись остаётся в состоянии «новая, не отправленная», не переходит в «правка
уже синхронизированной записи» (см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md)).
Тот же обработчик формально содержит и вторую ветку (`createdAt == null` →
ставит `updatedAt`), но она недостижима из UI — единственный живой вход в этот
блок, хаб неотправленных, по построению своего DAO-запроса
(`getNotSyncVaccinationsWithDetails`) отдаёт только строки с `createdAt !=
null`; это уже задокументированная находка ENT-14, здесь не переспецифицируется
как отдельный сценарий (см. «Альтернативные потоки»).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни `UnsentVaccinationEditBloc`,
ни `VaccinationsRepository` не проверяют статус авторизации на этом пути
(`grep -rn "isAuthorized\|AuthRepository"` по обоим файлам не находит ни одного
совпадения).

## CURRENT

### Основной поток

1. Точка входа — хаб неотправленных вакцинаций. `UnsentVaccinationPage`
   (`lib/pages/unsent_vaccination/unsent_vaccination_page.dart`) оборачивает
   `UnsentVaccinationCubit()..load()`, который наполняет список через
   `VaccinationsRepository.getNotSyncVaccinationsWithDetails()`. Этот DAO-запрос
   (`VaccinationsDao.getNotSyncVaccinationsWithDetails`,
   `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`)
   фильтрует `sync == false && deletedAt IS NULL && updatedAt IS NULL` — `createdAt`
   в фильтре не участвует вовсе, но на практике для любой строки, прошедшей этот
   фильтр и никогда не редактировавшейся через этот же экран, `createdAt !=
   null` (иначе строка была бы создана без `createdAt`, что не происходит ни в
   одном известном пути создания — см. «Бизнес-правила»).
2. Пользователь нажимает карточку — `_VaccinationCard.onTap` вызывает
   `context.pushNamed2(Routes.unsentVaccinationEdit, extra: v.id)`.
3. `UnsentVaccinationEditPage` (`lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart`)
   читает `vaccinationId` через
   `GoRouterState.of(context).getExtraByName<int?>(Routes.unsentVaccinationEdit)`
   (при `null` — фолбэк на второе имя маршрута, см. «Альтернативные потоки») и
   создаёт `BlocProvider(create: (context) =>
   UnsentVaccinationEditBloc(vaccinationId: vaccinationId)..add(const
   UnsentVaccinationEditStart()))`.
4. `on<UnsentVaccinationEditStart>` (`_onStart`) грузит запись через
   `_vaccinationRepository.getVaccinationsWithDetails(ids: [vaccinationId]).first`,
   справочники (`vaccines`, `diseases` — отфильтрованные по виду животного через
   `_filterDiseases`/`DiseasesKindsRepository.getDiseasesKindsByKindIds`, `units`,
   `injectionMethods`, `injectionPlaces`), строит `_data` со всеми текущими
   значениями (`vaccine`, `vaccineText`, `selectedDiseases`, `dose`, `unit`,
   `unitText`, `injectionMethod`, `injectionPlace`, `vaccinationDate`,
   `nextVaccinationDate`, `comment`, `productionDate`, `expirationDate`,
   `filteredVaccines`), эмитит `UnsentVaccinationEditSuccess(_data,
   updateControllers: true)`.
5. `_Body.build` (`unsent_vaccination_edit_page.dart`) при
   `state.updateControllers == true` заполняет все `TextEditingController`ы
   (вакцина, даты производства/годности/вакцинации/следующей вакцинации, доза,
   единица, метод и место введения, комментарий) значениями из `_data`. Экран
   всегда рендерится с `isRegagro: false` (литерал в вызове `_Body(...)` внутри
   `UnsentVaccinationEditPage.build`), поэтому вакцина и единица измерения — это
   всегда `SearchDropdownField` с автодополнением, не `_dropDownButton` (ветка
   `isRegagro == true` в этом же файле мертва на этом экране).
6. Пользователь правит любые поля через соответствующие
   `UnsentVaccinationEditEventChange...`-события — каждое меняет только
   `_data` в памяти и переэмитит `UnsentVaccinationEditSuccess(_data)`, без
   обращения к БД.
7. Пользователь нажимает `RElevatedButton` (`key: 'save_button'`);
   `onTap` вызывает `formKey.currentState?.validate()` и только при `true`
   диспатчит `UnsentVaccinationEditEventSave()`.
8. `on<UnsentVaccinationEditEventSave>` (`_onSave`): эмитит
   `UnsentVaccinationEditInProgress()`, затем определяет `finalVaccine`:
   если `_data.vaccineText` непусто и `_data.vaccine == null` (пользователь
   печатал в поле вакцины и не подтвердил существующий вариант тапом — событие
   `UnsentVaccinationEditEventChangeVaccineText` сбрасывает `vaccine` в `null`
   при каждом наборе текста), ищется существующая `Vaccine` по точному
   регистронезависимому совпадению имени среди уже загруженных `_data.vaccines`;
   если не найдена — вставляется новая строка `Vaccine`
   (`_vaccinesRepository.insert(VaccinesCompanion.insert(name:
   text.toLowerCase()))`) и `finalVaccine` строится из полученного `id`.
   `finalUnit = _data.unit` — без аналогичной логики свободного текста (правка
   единицы измерения по свободному тексту убрана, см. комментарий `// Removed
   free-text unit editing...` в `unsent_vaccination_edit_event.dart`).
9. Собирается `updatedVaccination = VaccinationsCompanion(id:
   Value(vaccinationId), vaccineId, dose, unitId, animalId:
   Value(_data.vaccination!.animal.animal.id) /* исходное животное, экран не
   даёт его сменить */, injectionMethodId, injectionPlaceId, vaccinationDate,
   nextVaccinationDate, notes: comment, updatedAt: _data.vaccination?.createdAt
   == null ? Value(DateTime.now()) : const Value.absent())`. Для этого сценария
   исходная запись всегда `createdAt != null` (см. шаг 1), поэтому ветка
   вычисляется в `const Value.absent()` — подтверждено тестом (см. «Связанные
   тесты»).
10. `await _vaccinationRepository.updateVaccination(updatedVaccination,
    _data.selectedDiseases ?? [])` не бросает исключение (happy path этого
    файла). Внутри `updateVaccination`
    (`lib/repositories/vaccination/vaccinations_repository.dart`):
    - `_diseasesVaccinationsRepository.saveDiseasesVaccinations(id,
      diseaseIds)` вызывается **без `await`** (fire-and-forget) — сам метод
      делает `await dao.clearByVaccinationId(id)` затем `await
      insertAll(...)` (`lib/repositories/vaccination/diseases_vaccinations_repository.dart`),
      полностью заменяя связки `DiseasesVaccinations` на текущий
      `_data.selectedDiseases`.
    - `await update(vaccination)` → `BaseRepository.update` → `dao.upd(item)`
      → `BaseDao.upd` = `updateCurrent().replace(item)`
      (`packages/sheep_farm_database/lib/entities/base_dao.dart`) — единственный
      реальный вызов, который этот шаг ждёт.
11. Успех: эмитится `UnsentVaccinationEditMessage('vaccination_saved')`
    (локализован во всех `.arb`-файлах проекта, в отличие от
    `error_saving_vaccination` — см.
    [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md)), затем
    `UnsentVaccinationEditExit()`.
12. `UnsentVaccinationEditPage`'s `BlocConsumer.listener`: на `Message` —
    `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
    Text(AppLocalizations.of(context)!.tr(state.message))))`; на `Exit` —
    `Navigator.of(context).pop()`.
13. Итоговое состояние строки `Vaccinations` в БД: `sync` остаётся `false`,
    `deletedAt` остаётся `null`, и — что не очевидно из самого кода блока —
    `createdAt` тоже остаётся тем же значением, что было до правки (см.
    «Бизнес-правила», семантика `replace()` для отсутствующих в `Companion`
    полей проверена отдельно, эмпирически). Строка по-прежнему проходит
    фильтр `getNotSyncVaccinationsWithDetails()` и остаётся в хабе
    неотправленных — при следующем полном sync-проходе уйдёт на сервер целиком
    как обычное новое создание (`_sendVaccinationsToApi`, тот же запрос).

### Альтернативные потоки

- **`createdAt == null` (правка уже синхронизированной записи).** Тот же
  `_onSave` формально содержит ветку `updatedAt: Value(DateTime.now())`, но она
  недостижима с единственного живого входа на этот экран — уже
  задокументировано в [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) и не
  переспецифицируется здесь отдельным сценарием.
- **Второй маршрут на тот же экран (`Routes.unsentVaccinationEditFromEditable`)
  тоже недостижим.** `lib/pages/routes.dart` регистрирует его как отдельный
  (не вложенный в `unsentVaccination`) маршрут на тот же `UnsentVaccinationEditPage`;
  единственное место в `lib/`, откуда на него что-то навигирует —
  `lib/pages/vaccination_card/vaccination_card_page.dart`
  (`context.pushNamed2(Routes.unsentVaccinationEditFromEditable, extra:
  vaccination.id)`). Но сама `VaccinationCardPage`
  (`Routes.vaccinationCard`) нигде не открывается: `grep -rln
  "vaccinationCard" lib/` находит только `routes.dart` (регистрация) и сам
  `vaccination_card_page.dart` (чтение собственного `extra`) — ни один другой
  экран на неё не переходит. Транзитивно недостижим, тот же вывод, что и в
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md).
- **`_data.injectionMethod == null` в момент нажатия «Сохранить» — сценарий
  этого файла (`UPDATE_OK`) не достигается.** Форма проверяет поле метода
  введения через `_selectFlagValidator(context, data.isInjectionMethodSuccess)`
  (`_dropDownButton<InjectionMethod>`, рендерится безусловно, не зависит от
  `isRegagro`), а `isInjectionMethodSuccess` в `UnsentVaccinationEditData()` по
  умолчанию `true` и **не пересчитывается** при загрузке записи в `_onStart`
  (конструктор вызывается напрямую, без `copyWith`) — то есть форма считает
  поле заполненным, даже если загрученная запись имеет `injectionMethodId ==
  null`. Если пользователь не трогает это поле, `formKey.currentState.validate()`
  проходит, но `_onSave` строит `injectionMethodId:
  Value(_data.injectionMethod!.id)` через force-unwrap на `null` — это уводит
  сценарий в соседний `RESULT = UPDATE_ERROR`, подробно описанный в
  [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md). В отличие от
  `injectionMethod`, поле `unit` в живой (не-`isRegagro`) ветке этого экрана
  валидируется отдельным инлайн-валидатором, который проверяет
  `data.unit == null` напрямую (`SearchDropdownField<Unit>.validator`,
  `unsent_vaccination_edit_page.dart`), а не флаг `isUnitSuccess` — для `unit`
  этот же класс риска не воспроизводится, форма корректно блокирует сохранение,
  если `unit` не выбран.
  Это не гипотетический краевой случай: создающий блок
  (`VaccinationBloc`, `lib/pages/vaccination/vaccination_bloc.dart`) сам пишет
  `injectionMethodId: Value(_data.selectedInjectionMethod?.id)` (безопасная
  навигация, поле не обязательно), и шаг мастера `VaccinationStep.injectionMethod`
  вовсе не входит в `VaccinationData.currentSteps` (список активных шагов —
  `[selectPlace?, disease, vaccine, vaccinationDate, animals?]`) — то есть в
  обычном (не regagro) сценарии создания пользователю физически не показывается
  экран выбора метода введения, и созданная запись почти всегда имеет
  `injectionMethodId == null`. Другими словами: этот `UPDATE_OK`-сценарий
  реально достижим только если пользователь **сам** выберет метод введения в
  процессе этой самой правки (или запись изначально была создана с ним) — не
  автоматически для любой строки хаба неотправленных.
- **Вакцина введена свободным текстом, не совпадающим ни с одной существующей
  строкой** — при сохранении в справочник `Vaccine` вставляется новая строка
  (`_vaccinesRepository.insert`), это по-прежнему успешный (`UPDATE_OK`) для
  самой вакцинации исход, но с побочным эффектом на общий (не привязанный к
  конкретной вакцинации) справочник. Совпадение имени сравнивается без
  `trim()` — текст с отличающимися пробелами по краям не найдёт существующую
  строку и создаст дубликат с тем же видимым названием.
- **Сохранение бросает исключение** (например реальный, не замоканный отказ
  `update(vaccination)`, либо тот же null-check на `injectionMethod`/`unit`) —
  `RESULT = UPDATE_ERROR`, не этот файл — см.
  [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md).

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  сущность сегмента `ENT` в id: строка обновляется на месте через частичный
  `VaccinationsCompanion` + `replace()`; `createdAt`/`sync`/`deletedAt`
  переживают правку неизменными (см. «Бизнес-правила»), `updatedAt` остаётся
  `Value.absent()`.
- Связочная таблица `DiseasesVaccinations` (часть [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  без собственного `ENT`) — полностью пересоздаётся (`clearByVaccinationId` +
  `insertAll`) под `_data.selectedDiseases`, вызовом без `await` внутри
  `updateVaccination`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается только:
  `animalId` берётся из исходно загруженного `_data.vaccination!.animal.animal.id`,
  этот экран не даёт переназначить вакцинацию на другое животное.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — выбор обязателен на этом экране (собственный инлайн-валидатор),
  хотя необязателен при создании вакцинации.
- Справочники `Vaccine`, `InjectionMethod`, `InjectionPlace`, `Disease`
  (VAC-локальные и HANDBOOKS-каталоги, см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md))
  — `Vaccine` может получить новую строку как побочный эффект свободного
  текста; `InjectionMethod` — источник риска, уводящего в `UPDATE_ERROR` (см.
  «Альтернативные потоки»); `InjectionPlace` читается безопасно (`?.id`);
  `Disease` — список полностью заменяется на выбор пользователя.

### Бизнес-правила

- `updatedAt` вычисляется один раз, по значению `createdAt` **исходно
  загруженной** записи (`_data.vaccination?.createdAt`, зафиксированному на
  шаге `_onStart`, до какой-либо правки) — для этого файла всегда `!= null`,
  поэтому `updatedAt` остаётся `Value.absent()` и запись не покидает
  состояние «новая, не отправленная».
- **`dao.upd` (`updateCurrent().replace(item)`) с частичным `VaccinationsCompanion`
  ведёт себя как частичный patch, а не как полная замена строки — проверено
  эмпирически** (drift 2.28.2, `pubspec.lock`): поля, отсутствующие в
  собираемом `Companion` (`shtpId`, `author`, `vaccinationTypeId`, `series`,
  `productionDate`, `expirationDate`, `errors`, `createdAt`, `deletedAt` — ни
  у одного из них нет `.withDefault(...)` в определении таблицы,
  `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart`),
  остаются в БД такими, какими были до вызова — `UpdateStatement.replace`
  добавляет в SET-выражение только те колонки, у которых есть объявленный
  `defaultValue` и явное отсутствие значения в `Companion`; для колонки без
  default она просто не попадает в SET, и SQL её не трогает. Единственная
  колонка с `.withDefault(...)` в этой таблице — `sync` (`default false`); при
  её отсутствии в `Companion` она была бы сброшена в `false` — для любой
  строки, реально достижимой через этот блок, `sync` и так уже `false`, эффект
  не наблюдаем. Доктрина API drift (doc-comментарий у `replace()`: «Otherwise,
  the field will be reset to null») не описывает это исключение для колонок без
  default явно и буквально вводит в заблуждение при поверхностном чтении — этот
  вывод проверен отдельным ad hoc тестом на in-memory БД (не оставлен в
  репозитории, только процедура верификации, не сам тестовый файл), не
  постоянным тестом в дереве `test/` (см. «Связанные тесты»).
- Список болезней (`saveDiseasesVaccinations`) переписывается вызовом без
  `await` внутри `updateVaccination`, до `await update(vaccination)` — то есть
  оба запроса выполняются конкурентно с точки зрения Dart-уровня; гарантирует
  ли фактический порядок выполнения на одном drift/`NativeDatabase`-соединении,
  что связки болезней успевают записаться до того, как `_onSave` эмитит
  `vaccination_saved`/`Exit`, не проверено (см. «Открытые вопросы»,
  [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md) разбирает тот
  же вызов на стороне отказа).
- Три записи хранилища в рамках одного сохранения (опциональная вставка
  `Vaccine`, `saveDiseasesVaccinations`, `update(vaccination)`) не объединены
  в одну БД-транзакцию — не находится оборачивающего `transaction(...)` ни в
  `_onSave`, ни в `updateVaccination`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — успешная ветка полностью реализована в коде и покрыта тестом на уровне
блока (репозиторий замокан целиком). Достижимость этого конкретного исхода на
практике сужена предусловием на `injectionMethod` (см. «Альтернативные
потоки») — это не блокирует код, но означает, что `UPDATE_OK` не гарантирован
для произвольной строки хаба неотправленных без участия пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage.build` (`_VaccinationCard.onTap`) | CURRENT | точка входа — карточка в хабе неотправленных |
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | источник списка через `getNotSyncVaccinationsWithDetails` |
| `lib/pages/routes.dart` | `Routes.unsentVaccination`, `Routes.unsentVaccinationEdit`, `Routes.unsentVaccinationEditFromEditable`, `Routes.vaccinationCard` | CURRENT | регистрация маршрутов, включая транзитивно недостижимый второй вход |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart` | `UnsentVaccinationEditPage.build` | CURRENT | чтение `vaccinationId` из `extra` (два возможных имени маршрута), создание блока, `isRegagro: false` литерально |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_page.dart` | `_Body.build` (поле `unit` — `SearchDropdownField<Unit>.validator`, поле `injectionMethod` — `_dropDownButton` + `_selectFlagValidator`) | CURRENT | клиентская валидация; `unit` проверяет фактическое значение, `injectionMethod` — только вспомогательный флаг |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditBloc._onStart` | CURRENT | загрузка записи + справочников, `UnsentVaccinationEditData(...)` без пересчёта `isInjectionMethodSuccess` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditBloc._onSave` | CURRENT | предмет сценария |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_event.dart` | `UnsentVaccinationEditEventSave` | CURRENT | событие без полей, весь payload — из накопленного `_data` |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_state.dart` | `UnsentVaccinationEditMessage`, `UnsentVaccinationEditExit`, `UnsentVaccinationEditSuccess` | CURRENT | состояния успешной ветки |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.updateVaccination`, `getNotSyncVaccinationsWithDetails` | CURRENT | персист изменений; подтверждение, что строка остаётся в unsent-хабе |
| `lib/repositories/vaccination/diseases_vaccinations_repository.dart` | `DiseasesVaccinationsRepository.saveDiseasesVaccinations` | CURRENT | clear+reinsert связок болезней, вызов без `await` |
| `lib/repositories/vaccination/vaccines_repository.dart` | `VaccinesRepository.insert` | CURRENT | побочная вставка новой `Vaccine` при свободном тексте |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | делегирует в `dao.upd` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` | CURRENT | схема — только `sync` имеет `.withDefault(...)`, остальные nullable-поля без default |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | фильтр unsent-хаба — `sync`/`deletedAt`/`updatedAt`, без проверки `createdAt` |
| `lib/pages/vaccination/vaccination_bloc.dart` | `VaccinationBloc` (`currentSteps`, `injectionMethodId: Value(_data.selectedInjectionMethod?.id)`) | CURRENT | создающий блок — подтверждает, что `injectionMethodId == null` типично для строк, попадающих в этот сценарий |
| `lib/pages/vaccination_card/vaccination_card_page.dart` | `_Body.build` (кнопка редактирования → `Routes.unsentVaccinationEditFromEditable`) | CURRENT | второй, транзитивно недостижимый вход в тот же блок |
| `lib/l10n/app_ru.arb` (и остальные `app_*.arb`), `lib/l10n/app_localization.dart` | `vaccination_saved` | CURRENT | локализованное сообщение об успехе |

## Критерии приёмки

- Открытие экрана правки для ещё не отправленной вакцинации (`createdAt !=
  null`) загружает запись и справочники, эмитит `UnsentVaccinationEditSuccess`
  с `updateControllers == true`.
- Успешное сохранение вызывает `VaccinationsRepository.updateVaccination` ровно
  один раз с `VaccinationsCompanion`, чей `id` равен исходному `vaccinationId`
  и чьё поле `updatedAt` отсутствует (`Value.absent()`, `.present == false`).
- Список болезней записи заменяется на `_data.selectedDiseases` через
  `DiseasesVaccinationsRepository.saveDiseasesVaccinations`.
- После сохранения строка `Vaccinations` сохраняет `sync == false`,
  `deletedAt == null` и исходный `createdAt` (не сбрасывается частичным
  `replace()`) — по-прежнему проходит фильтр
  `getNotSyncVaccinationsWithDetails()` и остаётся в хабе неотправленных.
- Успех эмитит `UnsentVaccinationEditMessage('vaccination_saved')` (реально
  локализованный ключ), затем `UnsentVaccinationEditExit()`; страница
  показывает снекбар и вызывает `Navigator.of(context).pop()`.
- Этот исход достижим только если на момент сохранения `_data.injectionMethod
  != null` — иначе тот же обработчик приводит к `RESULT = UPDATE_ERROR`
  (см. [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md)).

## Связанные тесты

- `test/pages/unsent_vaccination_edit_bloc_test.dart`, group
  `'UC-65 — UnsentVaccinationEditBloc._onSave (createdAt != null, ещё не
  отправлена)'` (старая нумерация, переименуется отдельным контролируемым
  проходом — не трогать сейчас), test `'сохранение -> updateVaccination с
  updatedAt=absent, строка остаётся unsent'`: фикстура (`_fixture` helper)
  всегда включает non-null `vaccine`/`unit`/`injectionMethod`
  (`id: 4, name: 'в/м'`), `VaccinationsRepository` замокан целиком
  (`MockVaccinationsRepository`); тест проверяет, что `bloc.stream` доходит до
  `UnsentVaccinationEditExit`, и что захваченный аргумент
  `updateVaccination(captureAny(), any())` — `VaccinationsCompanion` с
  `id.value == 11` и `updatedAt.present == false`.
- Тот же файл, group `'НАХОДКА — UnsentVaccinationEditBloc._onSave (createdAt
  == null, уже синхронизирована) — ...'` — покрывает недостижимую ветку, см.
  [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), не этот файл.
- Соседний `RESULT = UPDATE_ERROR` — group `'UC-66 — UnsentVaccinationEditBloc._onSave
  ERROR (createdAt != null)'`, того же файла — см.
  [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md), не этот файл.
- **TBD — теста нет**, что мок `updateVaccination` в существующем тесте
  скрывает реальное поведение репозитория целиком: ни семантика частичного
  `replace()` (выживание `createdAt`/`author`/`series`/… при реальном, не
  замоканном вызове), ни фактический порядок исполнения `saveDiseasesVaccinations`
  (без `await`) относительно `update(vaccination)`, ни побочная вставка новой
  `Vaccine` при свободном тексте — ничего из этого не проверяется ни одним
  найденным тестом на уровне репозитория/DAO.
- **TBD — теста нет** на прецедент из «Альтернативные потоки»: запись,
  изначально загруженная с `injectionMethod == null`, открытая на правку без
  изменения этого поля — ни в этом файле, ни в `unsent_vaccination_edit_bloc_test.dart`
  нет фикстуры с `injectionMethod: null`, воспроизводящей ни успешный, ни
  ошибочный исход для этого прецедента (симметрично тому же пробелу,
  зафиксированному в [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md)).

## Открытые вопросы и ограничения

- **`UPDATE_OK` не гарантирован для произвольной строки хаба неотправленных.**
  Поскольку `VaccinationStep.injectionMethod` не входит в
  `VaccinationData.currentSteps` создающего мастера (`VaccinationBloc`), почти
  любая вакцинация, дошедшая до хаба неотправленных стандартным путём
  создания, имеет `injectionMethodId == null`; форма экрана правки не
  сигнализирует об этом как об ошибке (стале-флаг `isInjectionMethodSuccess`),
  и сохранение без явного выбора метода введения уводит в `UPDATE_ERROR`,
  не в этот файл. Открытый вопрос: осознанное упрощение (метод введения
  действительно не нужен большинству пользователей) или недосмотр,
  унаследованный от асимметрии `?.id` (создание) / `!.id` (эта правка).
- **Частичная семантика `replace()` нигде не задокументирована и не закреплена
  тестом.** Поведение, при котором отсутствующие в `Companion` поля без
  `.withDefault(...)` не сбрасываются, — это деталь реализации drift
  (`UpdateStatement.replace`), от которой сейчас неявно зависит сохранность
  `createdAt`/`author`/`series`/`productionDate`/`expirationDate`/`shtpId`/
  `errors` при каждой правке через этот экран. Если в будущем к любой из этих
  колонок добавят `.withDefault(...)`, она начнёт молча сбрасываться при каждом
  сохранении — ничего в коде или тестах сейчас не предупредит об этой
  регрессии.
- **Порядок исполнения `saveDiseasesVaccinations` (без `await`) относительно
  `update(vaccination)` не проверен.** На успешном пути это не проявляется
  видимой ошибкой (оба вызова в итоге выполняются), но нет теста,
  подтверждающего, что список болезней гарантированно дописан в БД к моменту,
  когда `_onSave` эмитит `vaccination_saved`/`Exit` — см. также разбор того же
  вызова со стороны отказа в
  [UC-66](UC-66-ACTOR-5-EVT-33-ENT-14-UPDATE_ERROR-IN-ANIMAL.md).
- **Свободный текст вакцины сравнивается без `trim()`.** Совпадающее по сути,
  но отличающееся начальными/конечными пробелами название создаст дублирующую
  строку `Vaccine` вместо переиспользования существующей — не покрыто тестом.
- Второй маршрут на этот экран (`Routes.unsentVaccinationEditFromEditable`) и
  ветка `createdAt == null` остаются технически реализованными, но
  недостижимыми — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md),
  не переоткрывается здесь отдельным вопросом.
