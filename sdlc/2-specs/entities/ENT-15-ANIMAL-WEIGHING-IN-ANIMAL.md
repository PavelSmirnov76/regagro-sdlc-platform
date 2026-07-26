# ENT-15 — AnimalWeighing

## Описание

Запись о взвешивании одного животного — Drift-таблица `AnimalWeighings`. Модель существенно проще, чем у [ENT-13](ENT-13-MOVEMENT-IN-ANIMAL.md) (Movement) и [ENT-14](ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination): один-единственный флаг `sync`, без отдельных `createdAt`/`updatedAt`/`deletedAt` — локально неотличимы «новая, ещё не отправленная» запись и «уже была отправлена, потом отредактирована» запись, обе просто `sync: false`; различить их можно только по `remoteId` (`null` ⇒ никогда не была на сервере).

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int, autoincrement | локальный id |
| `remoteId` | int? | серверный id (`animal_id` в ответе сервера, несмотря на имя) — заполняется только для записей, пришедших с сервера |
| `animalId` | int | ссылка на [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) |
| `weight` | double | |
| `weighingDate` | DateTime | |
| `unitId` | int? | ссылка на `Unit` ([ENT-8](ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md), HANDBOOKS — тот же кросс-модульный справочник, что у VAC) |
| `sync` | bool, default false | признак отправки на сервер — единственный флаг состояния |
| `isHealthy` | bool, default true | результат клинического осмотра в момент взвешивания |

## Связи

- [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — многие-к-одному по `animalId`; `AnimalWithDetails.animalWeighings` — живой join на эту же таблицу (не отдельно загруженное с сервера поле), используется как кэш при построении «сегодняшнего взвешивания» и в вычислении среднесуточного привеса.
- [ENT-8](ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) (Unit, HANDBOOKS) — единица измерения веса.

## Инварианты

- **Одно логическое состояние на два семантически разных случая.** `sync: false` означает и «ещё ни разу не отправленная запись» (`remoteId == null`), и «уже была на сервере, но отредактирована локально и требует повторной отправки» (`remoteId != null`) — в отличие от Vaccination/Movement здесь нет отдельного поля, различающего эти два случая для целей push; выбор пути push определяется исключительно тем, что `getAllNotSuncAnimalWeighings()` фильтрует только по `sync == false`.
- **Push не различает создание и правку на уровне протокола.** `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP` (единственный реально вызываемый push-путь, из `DataUpdateBloc`) отправляет батчем ВСЕ строки с `sync == false` на эндпоинт `POST .../weighing-event` (создание), без `id`/`remoteId` в теле запроса — включая строки, которые локально являются правкой уже синхронизированной записи (`remoteId != null`). Правильные раздельные методы для create/update по одной записи (`singleSendAnimalWeighingToAPI` → `POST .../weighing-event`, `singleEditAnimalWeighingToAPI` → `PUT .../weighing-update`, обе с явным `id`/`remoteId`) существуют в репозитории, но **не вызываются нигде в `lib/`** — мёртвый код. Следствие: правка уже отправленного взвешивания, за которой следует полный sync-проход, с высокой вероятностью создаёт на сервере дубликат weighing-event вместо обновления существующего.
- **НАХОДКА — удаление/повторная отправка уже синхронизированного взвешивания недостижимы из UI.** `AnimalWeighingsCubit.deleteImmediate` (immediate-удаление через `deleteByIdFromAPI` + немедленный re-pull через `getAnimalWeighingByAnimalGuidFromAPI`) технически реализован и покрыт тестами, но ни один виджет истории взвешиваний (`AnimalWeighingListWidget`) не вызывает его — там есть только выбор строки (`selectAnimalWeighing`), не удаление. `AnimalWeighingsCubit.initWithoutLoad` (альтернативный, не читающий из БД путь инициализации состояния) тоже нигде не вызывается.
- **Успешный полный push удаляет отправленные строки локально без прямой замены** — `if (animalId != null) dao.deleteAllByAnimalId(animalId) else dao.clear()`, не помечает `sync: true`. Локальные данные восстанавливаются позже, отдельным шагом: `DataUpdateBloc.loadAnimals` вызывает `AnimalWeighingsRepository.clearSync()` (удаляет все `sync: true` строки) непосредственно перед `AnimalsRepository.syncAllAnimals()`, которая заново вставляет весь набор взвешиваний, вложенный в ответ сервера по каждому животному (`batch.insertAll(db.animalWeighings, ...)`). Между этими двумя шагами (push весов и последующим полным reload животных) окно, в котором взвешивания конкретного животного временно отсутствуют локально.
- **Ни один из трёх найденных «сохраняющих» методов (`saveWeighing`, `saveEditedWeighing` через `saveCurrentWeighingStayOnPage`/финальный шаг) не обёрнут в `try/catch`** — исключение на последнем шаге сохранения пробрасывается наружу необработанным, в отличие от аналогичных мест у Vaccination/Movement, которые ловят исключение и показывают сообщение пользователю.
- **Режим правки определяется автоматически, не только явным переходом из хаба.** `WeighAnimalCubit.initialize` ищет взвешивание за сегодняшний день у животного (`_findTodayWeighing`, по любому `sync`-статусу) всякий раз, когда `animalWeighingId` не передан явно; если такое найдено — экран открывается сразу в режиме правки (`selectedAnimalWeighingId` заполнен), даже если пользователь думает, что открывает обычную запись нового взвешивания.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings.dart` | `AnimalWeighings`, `AnimalWeighingDto`, `AnimalWeighingDtoExtension.toAnimalWeighing` | CURRENT | таблица, DTO и конвертация ответа сервера |
| `packages/sheep_farm_database/lib/entities/animal_weighing/animal_weighings_dao.dart` | `AnimalWeighingsDao.getAllNotSuncAnimalWeighings`, `clearSync`, `deleteAllByAnimalId` | CURRENT | DAO-запросы по `sync`-состоянию |
| `lib/repositories/animal_weighing/animal_weighings_repository.dart` | `AnimalWeighingsRepository.storeAnimalWeighingsToSHTP`, `singleSendAnimalWeighingToAPI`, `singleEditAnimalWeighingToAPI`, `deleteByIdFromAPI`, `getAnimalWeighingByAnimalGuidFromAPI` | CURRENT | push (батч, единственный реально используемый) и мёртвые по-одной-записи create/update/delete/pull методы |
| `lib/pages/weigh_animal/cubits/weigh_animal_cubit/weigh_animal_cubit.dart` | `WeighAnimalCubit.saveWeighing`, `saveEditedWeighing`, `initialize` | CURRENT | создание (батч по нескольким животным) и правка (одна запись, авто-детект по дате) |
| `lib/pages/animal_weighings/cubits/animal_weighings/animal_weighings_cubit.dart` | `AnimalWeighingsCubit.delete`, `deleteImmediate`, `initWithoutLoad` | CURRENT | удаление неотправленной (живое); удаление синхронизированной и альтернативная инициализация — мёртвый код |
