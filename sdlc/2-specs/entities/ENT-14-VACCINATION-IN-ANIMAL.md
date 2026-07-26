# ENT-14 — Vaccination

## Описание

Запись о вакцинации одного животного — Drift-таблица `Vaccinations`. Одна запись на одно животное (групповая вакцинация нескольких животных создаёт по одной строке на каждое, не одну групповую запись — тот же паттерн, что у [ENT-13](ENT-13-MOVEMENT-IN-ANIMAL.md), Movement). Список болезней, от которых сделана прививка, хранится отдельной связочной таблицей `DiseasesVaccinations` (многие-ко-многим), не колонкой на самой записи.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id |
| `shtpId` | int? | серверный id — заполняется только для записей, загруженных с сервера |
| `vaccineId` | int | ссылка на справочник `Vaccine` (VAC-локальный, ниже) |
| `dose` | double | |
| `animalId` | int | ссылка на [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) |
| `unitId` | int? | ссылка на `Unit` ([ENT-8](ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md), HANDBOOKS — кросс-модульный справочник, тот же, что у WEIGH) |
| `injectionMethodId` | int? | ссылка на справочник `InjectionMethod` (VAC-локальный) |
| `injectionPlaceId` | int? | ссылка на справочник `InjectionPlace` (VAC-локальный) |
| `notes` | text? | |
| `vaccinationDate` | DateTime | |
| `nextVaccinationDate` | DateTime? | `null` ⇒ вычисляемый статус всегда `absent` |
| `author` | text? | |
| `vaccinationTypeId` | int? | ссылка на справочник `VaccinationType` (VAC-локальный) |
| `series` | text? | |
| `productionDate` | DateTime? | |
| `expirationDate` | DateTime? | |
| `errors` | text? | текст ошибки последней неудачной попытки push |
| `sync` | bool, default false | признак отправки на сервер |
| `createdAt` | DateTime? | заполняется только для ещё не отправленной новой записи |
| `updatedAt` | DateTime? | заполняется только для правки уже синхронизированной записи |
| `deletedAt` | DateTime? | заполняется только для удаления уже синхронизированной записи |

## Связи

- [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — многие-к-одному по `animalId`.
- `DiseasesVaccinations` — многие-ко-многим с `Disease`, по `vaccinationId`/`diseaseId`; какие болезни покрывает конкретная запись вакцинации.
- [ENT-6](ENT-6-DISEASE-CATALOG-IN-HANDBOOKS.md) (DiseasesKind, HANDBOOKS) — читается при построении списка болезней/вакцин, доступных для вида вакцинируемого животного.
- [ENT-8](ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit, HANDBOOKS) — единица измерения дозы.
- Справочники `Vaccine`, `Disease`, `InjectionMethod`, `InjectionPlace`, `VaccinationType`, `ComplexVaccine` — не имеют собственного `ENT`, т.к. используются исключительно внутри VAC, ни один другой модуль на них не ссылается (в отличие от `Unit`/`DiseasesKind`, вынесенных в HANDBOOKS как кросс-модульные). `ComplexVaccine` — группа болезней, выбираемая одним пунктом в UI записи вакцинации; на саму запись `Vaccination` не сохраняется, перед сохранением разворачивается в конкретный список `Disease` через `DiseasesComplexVaccinesRepository`.

## Инварианты

- **Три независимых локальных состояния кодируются комбинацией трёх nullable-полей**, тот же принцип, что у Movement/Disposal: `createdAt != null` ⇒ новая, ещё ни разу не отправленная запись; `updatedAt != null` (при `createdAt == null`) ⇒ правка уже синхронизированной записи, ожидающая push; `deletedAt != null` (при `createdAt == null`, `updatedAt == null`) ⇒ удаление уже синхронизированной записи, ожидающее push. Ровно один из этих флагов может быть установлен одновременно — DAO-запросы (`getNotSyncVaccinationsWithDetails`/`getEditableVaccinationsWithDetails`/`getDeletableVaccinationsWithDetails`) эксклюзивно фильтруют по этой комбинации.
- **Push отправляет каждое из трёх состояний отдельным HTTP-запросом на общий эндпоинт `vaccination-group-actions`**, в фиксированном порядке delete → update → create (см. [EVT-35](../events/EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md)–[EVT-37](../events/EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md)); delete и update отправляются одним батчем на все подходящие строки разом, create — по одной записи за раз, с независимым результатом на каждую.
- **НАХОДКА — путь удаления/правки уже синхронизированной записи существует в коде, но недостижим из UI.** `VaccinationsRepository.markVaccinationForDeletion` (ставит `deletedAt`) вызывается только из `VaccinationCardPage`, чья навигационная запись (`Routes.vaccinationCard`) нигде не используется в приложении — экран не открывается ни с одного другого экрана. `UnsentVaccinationEditBloc._onSave`'s ветка `createdAt == null ⇒ ставит updatedAt` тоже не может сработать через единственный живой вход в этот блок (`UnsentVaccinationPage`, список из `getNotSyncVaccinationsWithDetails` — та выборка по определению возвращает только строки с `createdAt != null`). На сегодня `Vaccination` может быть удалена только целиком (hard delete, `deleteById`, доступно только для ещё не отправленной новой записи через `UnsentVaccinationCubit.delete`/`deleteSelected`) — «мягкое» удаление уже отправленной записи не запускается ниоткуда.
- **Push-исключение `create`-шага пробрасывается наружу и может прервать остальной sync pass**, `update`/`delete`-шаги (`_updateVaccinationFromApi`/`_deleteVaccinationFromApi`) перехватывают исключение внутри себя и не пробрасывают — тот же паттерн частичной устойчивости к сбоям, что у `MovementReportCubit.deleteEvent` (пустой `catch`).
- **Ни одна неотправленная строка не теряется при полном sync-проходе.** Перед `dao.clear()` весь набор ещё не синхронизированных строк (`sync == false`, независимо от того, новая она, в правке или в удалении) считывается в память и вставляется обратно после `pull`, если явно не запрошено `isDeleteErrors: true` — обычный пользовательский sync-запуск этот флаг не передаёт.
- **Вычисляемый статус вакцинации не хранится**, пересчитывается при каждом чтении через `VaccinationsDao.calculateVaccinationStatus`: `absent` (нет `nextVaccinationDate`) → `completed` (все болезни вакцины уже покрыты более поздней записью с той же или более новой датой) → `overdue`/`soon`/`actual` (по разнице `nextVaccinationDate` и текущей даты, порог «скоро» — настраиваемый `daysToVaccination`, по умолчанию 30 дней).
- **История животного (read-only список) показывает только уже синхронизированные записи** (`sync: true` по умолчанию, параметр `sync` в `getVaccinationsWithDetailsByAnimalId`).
- **При замене локального id животного на серверный все связанные записи `Vaccination` каскадно обновляются** на новый `animalId` (`AnimalsRepository.updateAnimalId`).

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` | CURRENT | таблица |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.calculateVaccinationStatus`, `markVaccinationForDeletion`, `removeFromUnsyncList`, `getNotSyncVaccinationsWithDetails`, `getEditableVaccinationsWithDetails`, `getDeletableVaccinationsWithDetails` | CURRENT | вычисление статуса, DAO-запросы по трём состояниям |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.syncVaccinations`, `saveVaccination`, `updateVaccination`, `markVaccinationForDeletion`, `removeFromUnsyncList` | CURRENT | push (delete/update/create), pull, локальные CRUD-операции |
| `lib/pages/vaccination_card/vaccination_card_page.dart` | `VaccinationCardPage` | CURRENT | недостижимый экран удаления уже синхронизированной записи |
| `lib/pages/unsent_vaccination/unsent_vaccination_edit_bloc.dart` | `UnsentVaccinationEditBloc._onSave` | CURRENT | правка неотправленной записи; ветка правки уже синхронизированной недостижима |
