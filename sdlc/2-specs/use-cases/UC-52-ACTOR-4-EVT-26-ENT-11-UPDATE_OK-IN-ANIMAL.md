- **derived from**: [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md), [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)

# UC-52 — Система синхронизирует отложенную правку животного, сервер принимает обновление

## Назначение

Во время полного sync-прохода система отправляет на сервер локальные правки уже
синхронизированных животных (`id >= 0`), помеченные `needsUpdate: true` —
правки, ранее внесённые пользователем при редактировании животного
([EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)) и оставленные
до этого момента неотправленными — и сервер принимает конкретную правку без
ошибки. Это завершает цикл, начатый локальным редактированием: правка
перестаёт считаться неотправленной.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — Система (sync-проход).
Действует не по прямой команде пользователя на этот конкретный шаг: сам
полный проход запущен пользователем один раз (`DataUpdateStartAll`), дальше
`DataUpdateBloc` идёт по шагам автоматически, без участия человека на уровне
отдельного HTTP-вызова.

## CURRENT

### Основной поток

1. Пользователь авторизован; полный sync-проход уже прошёл проверку сети в
   `on<DataUpdateStartAll>` и вызвал `DataUpdateBloc._syncAuthData` (гейт —
   `_authRepository.isAuthorized()`). `_syncAuthData` идёт по фиксированной
   последовательности шагов: удаление мест, синхронизация ферм, синхронизация
   мест, отправка взвешиваний, затем `updateAndSyncRegagro(event, emit)`.
2. `updateAndSyncRegagro` (после собственной проверки условий повторного
   прохода) вызывает `_syncAllData(event, emit)`.
3. `_syncAllData` идёт по фиксированной последовательности: очистка журнала
   `DataUpdate`, загрузка пользователя, `syncAllUnsentAnimals()` (локально
   созданные животные, `id < 0` —
   [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md), отдельный
   сценарий), синхронизация настроек, `_movementReportRepository.syncMovements()`,
   `_disposalRepository.syncDisposals()`, затем **`_syncEditedAnimals()`** —
   этот сценарий — затем `loadAnimals(event, emit)` (полная перезагрузка
   списка животных с сервера, см. «Открытые вопросы»), затем синхронизация
   вакцинаций.
4. `_syncEditedAnimals()` вызывает `_animalsRepository.getAllNeedsUpdate()` →
   `AnimalsDao.getAllNeedsUpdate()` — запрос к локальной таблице `Animals` с
   условием `needsUpdate.equals(true) & id.isBiggerOrEqualValue(0)`: только
   уже синхронизированные животные, отредактированные через `AnimalEditBloc`
   и оставленные с `needsUpdate: true`. Пустой результат — шаг завершается
   без единого сетевого вызова, не сценарий этого файла.
5. Непустой список `editedAnimals` обрабатывается циклом `for (final animal in
   editedAnimals)` **по одному животному, с независимым `try`/`catch` на
   каждой итерации** — не единым батчем и не с общим булевым флагом успеха,
   как это устроено для ферм (см. «Бизнес-правила»).
6. Для каждого животного вызывается `AnimalsRepository.updateAnimal(animal)`:
   формируется `birthDate` (`DateFormat('yyyy-MM-dd hh:mm:ss')` от
   `animal.birthDate`, либо `DateTime.now()`) и `placeDate` (всегда
   `DateTime.now()` — не поле животного); тело запроса — ограниченный набор
   полей (`id`, `guid`, `name`, `birth_date`, `breed_id`, `kind_id`,
   `suit_id`, `place_id`, `place_date`, `gender`, `generation`, `number`,
   `father_id`, `mother_id`, `father_birk`, `mother_birk`, `father_name`,
   `mother_name`); запрос — `PUT
   ${Constants.registrationServiceApi}/updateAnimal` через
   `ApiClient(instanceName: 'farm_rpc')`.
7. Сервер отвечает телом, из которого строится `UnsentAnimalResponse.fromJson(response)`;
   `result.isSuccess` (унаследовано от `BaseResponse.isSuccess`) — `status ==
   1`, числовое сравнение (не строковое `"1"`, как у ферм). Для этого
   сценария — `isSuccess == true`.
8. `updateAnimal`, не дожидаясь (`await` отсутствует), вызывает `dao.upd(animal)`
   — записывает обратно тот же объект `animal`, переданный на вход, без
   изменения `needsUpdate`/`errors` (они всё ещё в состоянии, которое было до
   этого шага) — и сразу возвращает `true`.
9. Обратно в `_syncEditedAnimals`: `ok == true` → выполняется
   `_animalsRepository.update(animal.copyWith(needsUpdate: const Value(false),
   errors: const Value(null)))` — второй, уже дождавшийся (`await`) вызов,
   идущий через `BaseRepository.update` → `dao.upd` → drift
   `updateCurrent().replace(item)` (замена строки по первичному ключу). Это
   единственный вызов, который фактически сбрасывает `needsUpdate` в `false`
   и очищает `errors`.
10. Цикл переходит к следующему животному списка `editedAnimals` независимо
    от исхода текущего — успех или неудача одного животного не влияет на
    обработку остальных.
11. После завершения цикла `_syncEditedAnimals()` возвращается;
    `_syncAllData` безусловно переходит к `loadAnimals(event, emit)` —
    следующему шагу того же прохода (см. «Открытые вопросы»).

### Альтернативные потоки

- **Пустой список к обновлению.** `getAllNeedsUpdate()` возвращает `[]` → шаг
  завершается без сетевого вызова и без изменения локальных данных. Не
  сценарий этого файла.
- **Сервер отвечает `status != 1` для конкретного животного.** `ok == false`
  → выполняется другая ветка: `_animalsRepository.update(animal.copyWith(errors:
  const Value('updateAnimal failed')))` — `needsUpdate` остаётся `true`,
  записывается текст ошибки. Другой `RESULT` (`UPDATE_ERROR`), не описан
  этим файлом.
- **PUT-вызов бросает исключение** (например сеть/таймаут) — пойман
  `catch`-блоком этой же итерации: `_animalsRepository.update(animal.copyWith(errors:
  Value(e.toString())))` — `needsUpdate` остаётся `true`. Тот же `RESULT`
  (`UPDATE_ERROR`), другой технический подтип, не описан этим файлом.
- **В одном и том же списке `editedAnimals` — несколько животных, одни
  приняты сервером, другие отклонены/упали с исключением.** Поскольку
  результат не агрегируется в общий флаг и цикл не прерывается (`break`), это
  — не общий батч-исход, как у ферм ([UC-27](UC-27-ACTOR-4-EVT-13-ENT-9-UPDATE_OK-IN-FARM.md)/
  [UC-28](UC-28-ACTOR-4-EVT-13-ENT-9-UPDATE_ERROR-IN-FARM.md)), а независимый
  исход на каждое животное: те, что приняты сервером, всё равно получают свой
  `needsUpdate: false` этим сценарием, даже если другие животные того же
  списка в этом же проходе завершились ошибкой.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — сущность
  сегмента `ENT` в id: `needsUpdate` переходит `true → false`, `errors`
  очищается до `null`, для каждого успешно принятого сервером животного
  индивидуально — не батчем, как у [ENT-9](../entities/ENT-9-FARM-IN-FARM.md)
  (Farm) в аналогичном сценарии ферм.

### Бизнес-правила

- Животные с отложенной правкой отправляются на `/updateAnimal` по одной, в
  цикле, каждая со своим независимым `try`/`catch` — успех или неудача одной
  записи никак не влияет на обработку остальных записей того же списка.
  Отличается и от `storeFarmsOnRDS` (частичный успех через `continue`, общий
  бул на списке), и от `updateFarmsOnRDS` (общий бул на списке, `break` на
  первой неудаче) — здесь нет ни общего флага, ни `break` вовсе: каждое
  животное самодостаточно.
- Успех отдельного запроса определяется исключительно числовым сравнением
  `status == 1` (`BaseResponse.isSuccess`) — тело ответа дальше не парсится
  обратно в поля животного; авторитетна локальная копия, ушедшая в запросе,
  за вычетом двух явно сброшенных полей.
- Тело запроса `/updateAnimal` — фиксированный, ограниченный набор полей;
  любая локальная правка поля вне этого набора (например владелец, адрес,
  координаты, фото) не будет отправлена этим шагом, даже если сама строка
  помечена `needsUpdate: true`.
- Фактический локальный сброс `needsUpdate`/`errors` происходит вызовом
  `_animalsRepository.update(...)` внутри `_syncEditedAnimals`, отдельным от
  вызова `dao.upd(animal)` внутри самого `AnimalsRepository.updateAnimal` —
  последний не дожидается своего выполнения (`await` отсутствует) и пишет
  назад тот же объект без изменения `needsUpdate`/`errors`.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде; тестового покрытия для него на
уровне `data_update_bloc.dart` нет, см. «Связанные тесты».

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | последовательность шагов авторизованного прохода: фермы/места → взвешивания → `updateAndSyncRegagro` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.updateAndSyncRegagro` | CURRENT | вызывает `_syncAllData` при выполнении условий (первый проход/повтор после ошибок) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | фиксирует порядок: movements/disposals → `_syncEditedAnimals` (этот сценарий) → `loadAnimals` → vaccinations |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncEditedAnimals` | CURRENT | получает животных с `needsUpdate: true`, по одному, с независимым `try`/`catch`, отправляет через `updateAnimal`; при успехе сбрасывает `needsUpdate`/`errors` локально |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllNeedsUpdate` | CURRENT | делегирует в `dao.getAllNeedsUpdate` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllNeedsUpdate` | CURRENT | фильтр `needsUpdate.equals(true) & id.isBiggerOrEqualValue(0)` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateAnimal` | CURRENT | `PUT {registrationServiceApi}/updateAnimal` с ограниченным набором полей; успех — `UnsentAnimalResponse.isSuccess` (`status == 1`); на успехе — не дождавшийся (`await` отсутствует) `dao.upd(animal)` |
| `packages/sheep_farm_database/lib/entities/animal/local_animals_groups.dart` | `UnsentAnimalResponse` | CURRENT | парсинг ответа `/updateAnimal` |
| `packages/sheep_farm_database/lib/entities/base_response/base_response.dart` | `BaseResponse.isSuccess` | CURRENT | `status == 1`, числовое сравнение |
| `lib/repositories/base_repository.dart` | `BaseRepository.update` | CURRENT | делегирует в `dao.upd`; вызывается блоком отдельно, для фактического сброса `needsUpdate`/`errors` |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.upd` | CURRENT | `updateCurrent().replace(item)` — drift-замена строки по первичному ключу |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals.needsUpdate` | CURRENT | nullable boolean-колонка, флаг «есть неотправленная правка» |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals.errors` | CURRENT | nullable text-колонка, текст последней ошибки/успеха отправки |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc` (обработчик `AnimalEditEventSave`) | CURRENT | путь, которым устанавливается предпосылка сценария — `needsUpdate: true` при сохранении правки уже синхронизированного животного, см. [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md) |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | безусловный следующий шаг того же прохода — полная очистка и перезагрузка таблицы `Animals` с сервера, независимо от исхода этого сценария |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncAllAnimals` | CURRENT | вызывается `loadAnimals`; в рамках `_syncAllData` вызывается без `fromDate` — полный, не инкрементальный ресинк |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API животных |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент, через который идёт `PUT /updateAnimal` |

## Критерии приёмки

- Животное с `needsUpdate == true` и `id >= 0` → включается в
  `getAllNeedsUpdate()` и попадает в обработку `_syncEditedAnimals`.
- Каждое такое животное отправляется отдельным `PUT
  {registrationServiceApi}/updateAnimal` с телом из фиксированного набора
  полей — независимо от остальных животных того же списка (проверяемо
  подсчётом вызовов мока: неудача одного не блокирует и не прерывает вызовы
  для следующих).
- Сервер отвечает `status == 1` → `updateAnimal` возвращает `true` →
  `_syncEditedAnimals` вызывает `update(animal.copyWith(needsUpdate: false,
  errors: null))` для этого животного.
- Тело ответа сервера не парсится обратно в поля животного (кроме самого
  факта успеха) — локальная копия остаётся авторитетной за вычетом
  `needsUpdate`/`errors`.
- Успех или неудача одного животного списка не меняет поведения по
  отношению к другим животным того же списка — ни `break`, ни общий флаг
  успеха/неудачи не используются.
- Сразу по завершении цикла, в рамках того же прохода, безусловно
  выполняется `loadAnimals` (полная перезагрузка списка животных с сервера)
  — независимо от результата этого шага.

## Связанные тесты

TBD — теста нет. На уровне `data_update_bloc.dart` для этого sync-сценария
тестов не существует вовсе: `test/blocs/data_update_bloc_test.dart` не
содержит ни одного упоминания `_syncEditedAnimals`, `getAllNeedsUpdate` или
`syncAllUnsentAnimals` — покрывает только конструирование `DataUpdateBloc` и
обработку `DataUpdateClear`. `grep -rn "_syncEditedAnimals" test/` не находит
ни одного файла.

Рядом, но не самоименующимся анкором этого сценария, существует
`test/repositories/animals_repository_test.dart` → `group('updateAnimal', ...)`
(два теста: успешный ответ API и `status != 1`) — он проверяет изолированно
только сам HTTP-вызов `AnimalsRepository.updateAnimal`, не оркестрацию
`_syncEditedAnimals` (сброс `needsUpdate`/`errors`, независимую по каждому
животному обработку, поведение при исключении) и не цитирует `UC-52` ни в
`group`, ни в `test`.

## Открытые вопросы и ограничения

- **Не дождавшийся (`await`) `dao.upd(animal)` внутри
  `AnimalsRepository.updateAnimal`.** На успехе метод синхронно возвращает
  `true` сразу после запуска этого вызова, не дожидаясь его завершения; сам
  вызов пишет назад тот же объект `animal` без изменения `needsUpdate`/`errors`
  — фактический сброс этих полей выполняется исключительно последующим,
  уже дождавшимся вызовом `_animalsRepository.update(...)` в
  `_syncEditedAnimals`. Не проверялось в рамках этого прохода, действительно
  ли этот не дождавшийся вызов нужен вообще для этого пути (он не меняет ни
  одно поле относительно уже сохранённой строки) или это исторический
  остаток.
- **Немедленный безусловный полный reload сразу следующим шагом.**
  `loadAnimals` (тот же `_syncAllData`, следующий шаг) выполняет
  `_animalsRepository.clear()` + `syncAllAnimals()` без `fromDate` — то есть
  полную, не инкрементальную перезагрузку всей таблицы `Animals` с сервера,
  безусловно, независимо от исхода `_syncEditedAnimals`. Значит, локальная
  запись, сделанная этим сценарием (`needsUpdate: false`, `errors: null`),
  живёт лишь до этого следующего шага того же прохода — какое состояние
  реально «останется» для этой строки после прохода, зависит от того, что
  вернёт сервер по `/animals` для этого животного, а не от локальной записи
  этого сценария. Содержит ли ответ `/animals` поле `needs_update` для
  каждой строки (тем самым сохраняя или обнуляя сделанный этим сценарием
  сброс) не проверялось в рамках этого прохода — вне периметра.
- **Ограниченный набор отправляемых полей.** Тело `/updateAnimal` не
  покрывает весь набор полей [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)
  (например владелец, адрес/координаты, фото животного не отправляются) —
  правка такого поля остаётся невидимой для сервера этим шагом, даже если
  строка в целом помечена `needsUpdate: true` из-за другого изменённого поля.
