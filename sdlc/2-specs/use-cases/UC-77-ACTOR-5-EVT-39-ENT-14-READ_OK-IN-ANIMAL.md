# UC-77 — Пользователь открывает вкладку вакцинаций карточки животного

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Пользователь открывает вкладку вакцинаций в карточке животного (из вет-карты)
и видит список уже синхронизированных с сервером записей вакцинации этого
животного, с вычисленным на лету статусом каждой записи, разделённых на
«прошедшие» и «будущие» — с возможностью переключить быстрый фильтр
прошедшие/будущие и применить дополнительные фильтры без повторного похода в
БД.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость или авторизованный, разницы для этого сценария нет).

## CURRENT

### Основной поток

1. Пользователь находится на `AnimalVetCardPage` и нажимает на блок
   последней/следующей вакцинации
   (`AnimalVetStatisticsWidget.onLastVaccinationTap`) →
   `context.pushNamed2(Routes.animalVaccinations, extra:
   AnimalVaccinationsPageArguments(animal: animalWithDetails))`.
2. `AnimalVaccinationsPage.build` читает аргумент через
   `GoRouterState.of(context).getExtraByName<AnimalVaccinationsPageArguments?>`
   и создаёт `BlocProvider(create: (context) =>
   AnimalVaccinationsCubit(arguments!.animal)..load())`.
3. Конструктор `AnimalVaccinationsCubit` сразу подписывается на
   `_vaccinationsRepository.watchCountAllVaccinations()` — стрим количества
   строк **всей** таблицы `Vaccinations`, без фильтра по `animalId`; на каждое
   новое значение подписчик безусловно вызывает `load()` (см.
   «Альтернативные потоки»).
4. `load()` эмитит `AnimalVaccinationsState.loading(animal: state.animal)`.
5. `_allVaccinations = await
   _vaccinationsRepository.getVaccinationsWithDetailsByAnimalId(
   state.animal.animalId, sync: true)` — репозиторий делегирует в
   `VaccinationsDao.getVaccinationsWithDetailsByAnimalId(animalId: ...,
   sync: true)`: жёсткий фильтр `vaccination.sync == true` (только уже
   подтверждённые сервером записи), join с `Vaccine`/`Unit`/
   `InjectionMethod`/`InjectionPlace`/`VaccinationType`, отдельно на каждую
   строку — `AnimalWithDetails` через `db.animalsDao.getAnimalWithDetailsById`,
   список болезней через `_getDiseasesByLink` (читает `DiseasesVaccinations` +
   `Disease` напрямую, не через `DiseasesKind`), `ComplexVaccine` и
   вычисленный `vaccinationStatus` через `calculateVaccinationStatus`
   (`absent`/`completed`/`overdue`/`soon`/`actual`, порог «скоро» —
   `ProfileSettings.daysToVaccination`, по умолчанию 30 дней).
6. `_applyFilters()` вызывается. При первом открытии `_currentFilters ==
   null`, поэтому ветка «без фильтров»: эмитится
   `AnimalVaccinationsState.loaded` с:
   - `allVaccinations: latestVaccinationsPerDiseasesList(_allVaccinations)` —
     дедуп по множеству id болезней, оставляя запись с более поздней
     `vaccinationDate` на каждое уникальное множество;
   - `vaccinations: _allVaccinations.map((v) =>
     v.toVaccinationCardItem(false)).toList()` — весь список, `author` и
     `vaccinationDate` показаны как есть;
   - `futureVaccinations: _getNextVaccinations(_allVaccinations)` — подмножество
     с `isFutureVaccination == true` (статус ∈ {`actual`, `soon`, `overdue`} и
     `nextVaccinationDate != null`), смаплено с `isFutureVaccination: true` —
     `author` подавляется в `null`, показываемая дата — `nextVaccinationDate`;
   - `selectedFastFilter: state.selectedFastFilter` — сохраняется из
     предыдущего состояния (по умолчанию `VaccinationFastFilter.gone`).
7. `AnimalVaccinationsPage` перерисовывается через `BlocBuilder`; состояние —
   `AnimalVaccinationsLoaded`, `currentVaccinationsList` (геттер в
   `animal_vaccinations_state.dart`) выбирает `vaccinations` или
   `futureVaccinations` в зависимости от `selectedFastFilter` — по умолчанию
   `gone` ⇒ показываются `vaccinations` (прошедшие).
8. `AnimalVaccinationsView` рендерит список `VaccinationCardItem`: названия
   болезней, имя вакцины, отформатированную дату, автора.

### Альтернативные потоки

- **Переключение быстрого фильтра.** Пользователь нажимает
  `VaccinationFastFilterWidget` (прошедшие/будущие) →
  `setVaccinationFastFilter` — если значение изменилось, эмитится `loaded` с
  тем же `vaccinations`/`futureVaccinations` (уже посчитанными на шаге 6) и
  новым `selectedFastFilter`; повторного похода в репозиторий нет.
- **Применение фильтров экрана.** Иконка фильтра в `AppBar` открывается только
  если аргументы страницы не `null`; открывает `VaccinationFiltersDialog`
  через `showDialog<VaccinationFiltersData?>` — легаси-`Dialog`, не bottom
  sheet, в отличие от текущей конвенции фильтров сущностей проекта. После
  `cubit.applyFilters(filters)` кубит сохраняет `_currentFilters` и снова
  вызывает `_applyFilters()` — фильтрует уже закэшированный `_allVaccinations`
  через `VaccinationFiltersData.checkVaccinationWithDetails`, без повторного
  запроса к БД. В этой ветке эмитируемое состояние **не передаёт**
  `allVaccinations` (аргумент не указан ⇒ дефолт `[]`), в отличие от ветки без
  фильтров на шаге 6.
- **Реактивная перезагрузка без действия пользователя.** `watchCountAllVaccinations()`
  считает строки всей таблицы `Vaccinations` целиком — вакцинация,
  записанная/изменённая/удалённая для **любого другого** животного в
  приложении (либо строка, пришедшая через sync pass), меняет это число и
  вызывает `load()` заново, пока экран открыт — событие/`RESULT` то же самое
  (`READ_OK`), просто без клика пользователя по этому экрану.
- **Ошибка репозитория.** Если `getVaccinationsWithDetailsByAnimalId` бросает
  исключение — перехватывается, логируется через `Talker`, эмитится `loaded`
  с пустым `vaccinations` (и пустыми по умолчанию `futureVaccinations`/
  `allVaccinations`). Другой `RESULT` (`READ_ERROR`), не этот файл — покрыт
  соседним test group `'UC-78 — AnimalVaccinationsCubit.load'` в том же
  тестовом файле.
- **Экран группировки по болезням не открывается ниоткуда.**
  `VaccinationsByDiseasesCubit` (`lib/pages/animal_vaccinations/cubits/vaccinations_by_disease/`)
  существует, оборачивает тот же `VaccinationsRepository`, но не
  инстанцируется ни на одной странице/навигации — `grep -rn
  "VaccinationsByDiseasesCubit("` вне его собственной папки и
  `test/pages/vaccinations_by_diseases_cubit_test.dart` не находит ничего;
  недостижимая альтернативная презентация тех же данных.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  главный предмет чтения; читаются только строки с `sync == true`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — животное, чью
  карточку смотрит пользователь (`state.animal`, передано аргументом
  страницы); также перечитывается на каждую строку вакцинации через
  `AnimalsDao.getAnimalWithDetailsById` и используется предикатами
  `checkAnimalKind`/`checkFarm`/`checkPlace` фильтров.
- [ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit,
  HANDBOOKS) — читается join'ом в `getVaccinationsWithDetailsByAnimalId` для
  каждой строки, но не отображается: `VaccinationCardItem`/
  `AnimalVaccinationsView` не содержат поля единицы измерения дозы — данные
  запрашиваются, но не используются этим сценарием.

### Бизнес-правила

- **`sync: true` — жёсткий фильтр по умолчанию.** Вкладка показывает только
  уже подтверждённые сервером записи; локально созданные, ещё не отправленные
  записи вакцинации сюда не попадают (их — отдельный хаб неотправленных,
  [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md), вне
  этого файла).
- **Фильтрация — над уже загруженным в память списком.** И быстрый фильтр
  (прошедшие/будущие), и полноценные фильтры экрана (`applyFilters`)
  пересчитывают `vaccinations`/`futureVaccinations` из закэшированного
  `_allVaccinations`, не выполняя повторный запрос к `VaccinationsDao`.
- **Статус вакцинации — не хранится, пересчитывается при каждом чтении**
  (`VaccinationsDao.calculateVaccinationStatus`), включая порог «скоро»
  (`ProfileSettings.daysToVaccination`) на момент именно этого вызова
  `load()`.
- **Подписка на реактивную перезагрузку не сужена по животному** — любое
  изменение таблицы `Vaccinations` для любого другого животного вызывает
  полный повторный `load()` этого экрана, пока он открыт.
- **Иконка фильтра открывает легаси `Dialog`**
  (`VaccinationFiltersDialog`/`showDialog`), а не bottom sheet — расходится с
  документированной для проекта конвенцией фильтров сущностей.
- **Поле `allVaccinations` загруженного состояния — мёртвый путь данных.**
  Оно заполняется (`latestVaccinationsPerDiseasesList`) только в ветке без
  активных фильтров, сбрасывается в `[]` при применённых фильтрах, и в обоих
  случаях не читается ни `AnimalVaccinationsPage`, ни
  `AnimalVaccinationsView` — единственные потребители, геттеры
  `pinnedVaccinations`/`notPinnedVaccinations` в
  `AnimalVaccinationsStateExtension`, нигде не вызываются за пределами
  собственного файла состояния.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток полностью реализован.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_vet_card/presentations/animal_vet_card_page.dart` | `AnimalVetCardPage.build` (`AnimalVetStatisticsWidget.onLastVaccinationTap`) | CURRENT | точка входа — переход на вкладку вакцинаций из вет-карты |
| `lib/pages/routes.dart` | `Routes.animalVaccinations` | CURRENT | маршрут вкладки, вложен под `Routes.animalVetCard` |
| `lib/pages/animal_vaccinations/pages/animal_vaccinations_page.dart` | `AnimalVaccinationsPage.build` | CURRENT | создаёт кубит и вызывает `load()`, хостит быстрый фильтр, иконку фильтров и список |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit.load` | CURRENT | основной метод сценария: запрос `sync: true` строк по животному, запуск `_applyFilters` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit._applyFilters` | CURRENT | ветвление без фильтров / с фильтрами над закэшированным `_allVaccinations` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit._getNextVaccinations` | CURRENT | выделяет «будущие» по `isFutureVaccination` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_cubit.dart` | `AnimalVaccinationsCubit` (конструктор, подписка на `watchCountAllVaccinations()`) | CURRENT | безусловный авто-`load()` на любое изменение всей таблицы `Vaccinations` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_state.dart` | `AnimalVaccinationsStateExtension.currentVaccinationsList` | CURRENT | выбирает `vaccinations` или `futureVaccinations` по `selectedFastFilter` |
| `lib/pages/animal_vaccinations/cubits/animal_vaccinations/animal_vaccinations_state.dart` | `AnimalVaccinationsStateExtension.pinnedVaccinations`, `notPinnedVaccinations` | CURRENT | геттеры над `allVaccinations`, не вызываются ни одним экраном |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getVaccinationsWithDetailsByAnimalId` | CURRENT | тонкая обёртка над DAO, `sync` по умолчанию `true` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.watchCountAllVaccinations` | CURRENT | делегирует в DAO-стрим, источник реактивной перезагрузки |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getVaccinationsWithDetailsByAnimalId` | CURRENT | запрос+join'ы+вычисление статуса на каждую строку |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.calculateVaccinationStatus` | CURRENT | вычисляемый статус вакцинации, не хранится |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.watchCountAllVaccinations` | CURRENT | стрим количества строк всей таблицы, без фильтра по `animalId` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `VaccinationWithDetailsExtension.isFutureVaccination` | CURRENT | предикат разделения прошедшие/будущие |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_with_details.dart` | `latestVaccinationsPerDiseasesList` | CURRENT | дедуп по множеству болезней, питает неиспользуемое поле `allVaccinations` |
| `lib/pages/animal_vaccinations/data/vaccination_card_item.dart` | `VaccinationCardItemMapping.toVaccinationCardItem` | CURRENT | маппинг в UI-модель; для будущих записей подавляет `author`, подменяет дату на `nextVaccinationDate` |
| `lib/pages/animal_vaccinations/widgets/animal_vaccinations_view.dart` | `AnimalVaccinationsView.build` | CURRENT | рендер списка карточек |
| `lib/widgets/fast_filter/vaccination_fast_filter_widget.dart` | `VaccinationFastFilterWidget` | CURRENT | UI-переключатель прошедшие/будущие |
| `lib/pages/vaccination_filters/vaccination_filters_bloc.dart` | `VaccinationFiltersData.hasFilters`, `VaccinationFiltersData.checkVaccinationWithDetails` | CURRENT | предикат фильтрации, применяется клиентски над закэшированным списком |
| `lib/pages/vaccination_filters/vaccination_filters_dialog.dart` | `VaccinationFiltersDialog` | CURRENT | легаси `Dialog`-обёртка (не bottom sheet) для полноценных фильтров |
| `lib/pages/animal_vaccinations/cubits/vaccinations_by_disease/vaccinations_by_diseases_cubit.dart` | `VaccinationsByDiseasesCubit` | CURRENT | недостижимый экран группировки по болезням над тем же репозиторием |

## Критерии приёмки

- При открытии вкладки вакцинаций кубит запрашивает
  `getVaccinationsWithDetailsByAnimalId(animalId, sync: true)` ровно один раз
  за вызов `load()` — только строки уже синхронизированных записей этого
  животного.
- Загруженное состояние разделяет строки на `vaccinations` (все) и
  `futureVaccinations` (подмножество с `isFutureVaccination == true`) без
  дополнительного запроса к БД.
- По умолчанию (`selectedFastFilter == VaccinationFastFilter.gone`) экран
  показывает `vaccinations` (прошедшие), не `futureVaccinations`.
- Переключение быстрого фильтра и применение/сброс фильтров экрана не
  вызывают повторный запрос к репозиторию — работают над уже загруженным
  `_allVaccinations`.
- Любое изменение (создание/правка/удаление/sync) строки таблицы
  `Vaccinations`, для любого животного, автоматически вызывает повторный
  `load()` этого экрана, пока он открыт — без действия пользователя.
- При исключении в репозитории состояние становится `loaded` с пустым
  `vaccinations`, ошибка логируется — исключение не всплывает в UI (другой
  `RESULT`, не этот файл).

## Связанные тесты

`test/pages/animal_vaccinations_cubit_test.dart`, group `'UC-77 —
AnimalVaccinationsCubit.load'`, test `'успех -> loaded с
vaccinations/futureVaccinations разделёнными по isFutureVaccination'`.

Соседняя ошибка-ветка того же `load()` покрыта отдельным group `'UC-78 —
AnimalVaccinationsCubit.load'` (другой `RESULT`, не этот файл). Реактивная
перезагрузка по `watchCountAllVaccinations` (альтернативный поток этого же
файла) фактически покрыта тестом в том же файле — group
`'AnimalVaccinationsCubit — реактивная подписка'`, test `'watchCountAllVaccinations
эмитит -> перезагружает список'` — но этот group **не назван** по конвенции
`UC-{id}` и потому не резолвится механическим `grep -r "UC-77" test/` как
привязанный к этому use-case (см. «Открытые вопросы»).

## Открытые вопросы и ограничения

- **Тест реактивной перезагрузки не привязан к UC-id.** Group
  `'AnimalVaccinationsCubit — реактивная подписка'` в
  `test/pages/animal_vaccinations_cubit_test.dart` реально проверяет
  альтернативный поток этого файла (авто-`load()` при эмите
  `watchCountAllVaccinations`), но не содержит анкера `UC-77` в имени —
  привязка не механическая, только по факту прочтения; переименование —
  отдельный проход, не в рамках этого документирующего файла.
- **Подписка на всю таблицу, а не на животное.** `watchCountAllVaccinations()`
  считает строки всей таблицы `Vaccinations` без фильтра по `animalId` —
  любое изменение, вызванное действием с совершенно другим животным (или
  sync-проходом), перезагружает этот экран, пока он открыт. Не проверялось,
  насколько заметно это на практике (перезагрузка дешёвая, локальная), но
  поведенчески это шире, чем можно было бы ожидать от вкладки одного
  животного.
- **Мёртвое поле `allVaccinations`/`pinnedVaccinations`/`notPinnedVaccinations`.**
  Заполняется в одной ветке (`_applyFilters` без активных фильтров),
  сбрасывается в другой (с фильтрами), но не читается ни одним экраном —
  похоже на остаток недоделанной или заброшенной функциональности (например,
  раздел «закреплённые» болезни в UI, который не был подключён либо был
  убран).
- **Недостижимый экран группировки по болезням.** `VaccinationsByDiseasesCubit`
  существует в коде, оборачивает тот же `VaccinationsRepository.getVaccinationsWithDetailsByAnimalId`,
  но ни одна страница/навигация его не создаёт — подтверждено `grep`
  за пределами его собственной папки и теста. Не описывается отдельным
  use-case, так как недостижим из UI.
- **Легаси `Dialog` вместо bottom sheet для фильтров.** `VaccinationFiltersDialog`
  открывается через `showDialog`, а не через `showModalBottomSheet` —
  расходится с документированной конвенцией фильтров сущностей проекта; факт
  зафиксирован, миграция — не предмет этого документирующего прохода.
