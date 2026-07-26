# UC-53 — Sync отложенной правки животного отказывает: ошибка пишется в `errors`, но в этом же проходе стирается следующим шагом (ERROR)

## Назначение

Во время явного sync-прохода система отправляет на сервер локальные правки уже
синхронизированных животных (`needsUpdate: true`), отложенные ранее
([EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)). Когда отправка
конкретного животного отказывает — сервер отвечает неуспехом либо сам вызов
падает исключением — код на первый взгляд откладывает повтор на следующий
проход (`needsUpdate` этим шагом не сбрасывается). Но тот же самый проход,
непосредственно следующим шагом, безусловно перезагружает всю локальную
таблицу животных с сервера — и именно эта перезагрузка, а не сам отказ
отправки, окончательно решает судьбу правки: она стирается вместе с
`needsUpdate` уже до конца текущего прохода, а не на следующем.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая внутри
уже запущенного полного sync-прохода (`DataUpdateBloc`), не человек и не
отдельное решение пользователя на этом шаге. Сам проход запускается человеком
до этого — `DataUpdateStartAll` диспатчится из
`lib/pages/main/main_page.dart`, `lib/pages/data_update/data_update_page.dart`,
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`,
`lib/pages/in_work/in_work_page.dart` — сам механизм запуска прохода
принадлежит модулю `SYSTEM` (см. границу [MOD-4](../modules/MOD-4-ANIMAL.md)),
здесь не переопределяется.

## CURRENT

### Основной поток

1. **Предпосылка.** Пользователь ([ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md))
   ранее отредактировал уже синхронизированное животное (`id >= 0`) —
   [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md),
   `AnimalEditBloc.on<AnimalEditEventSave>`. Правка сохраняется вызовом
   `_animalsRepository.update(updated.copyWith(needsUpdate: const
   Value(true)))` — флаг взводится **только** когда `updated.id >= 0`; на
   сервер в этот момент ничего не отправляется.
2. Пользователь (независимо, в другой момент) запускает полный sync-проход.
   `DataUpdateBloc.on<DataUpdateStartAll>` проверяет сеть, и при авторизованном
   пользователе (`_authRepository.isAuthorized()`) вызывает
   `DataUpdateBloc._syncAuthData` → `updateAndSyncRegagro` →
   `DataUpdateBloc._syncAllData`.
3. `_syncAllData` выполняет фиксированную последовательность шагов без
   ветвления по результату предыдущих: `syncAllUnsentAnimals()` (см.
   [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)) →
   … → `_movementReportRepository.syncMovements()` →
   `_disposalRepository.syncDisposals()` → **`_syncEditedAnimals()` (этот
   сценарий)** → `loadAnimals(event, emit)` → `_vaccinationsRepository
   .syncVaccinations(true)`. Порядок жёстко зашит в коде, не настраивается.
4. `_syncEditedAnimals()` запрашивает `_animalsRepository.getAllNeedsUpdate()`
   → `AnimalsDao.getAllNeedsUpdate` (`needsUpdate.equals(true) &
   id.isBiggerOrEqualValue(0)`) — список `editedAnimals`.
5. Для каждого животного список обрабатывается **в цикле, независимо**, со
   своим собственным `try/catch` на итерацию — отказ одного не прерывает
   обработку остальных: `await _animalsRepository.updateAnimal(animal)`.
6. `updateAnimal()` формирует `PUT
   ${Constants.registrationServiceApi}/updateAnimal` через
   `getIt.get<ApiClient>(instanceName: 'farm_rpc')` с ограниченным набором
   полей (`id`, `guid`, `name`, `birth_date`, `breed_id`, `kind_id`,
   `suit_id`, `place_id`, `place_date`, `gender`, `generation`, `number`,
   `father_id`/`mother_id`/`father_birk`/`mother_birk`/`father_name`/
   `mother_name`) и парсит ответ в `UnsentAnimalResponse.fromJson(response)`.
7. Сервер отвечает статусом ≠ `1` (`result.isSuccess == false`) — **либо** сам
   вызов `rpcClient.call(message)` бросает исключение (нет внутреннего
   `try/catch` вокруг него в `updateAnimal()`, поэтому оно пробрасывается
   наружу к вызывающему коду). Два технически разных случая расходятся по
   разным веткам вызывающего кода (см. шаги 8–9).
8. Ветка `result.isSuccess == false` без исключения:
   `updateAnimal()` возвращает `false`. `_syncEditedAnimals()`: `ok == false`
   → `_animalsRepository.update(animal.copyWith(errors: const
   Value('updateAnimal failed')))` — **захардкоженная константная строка**,
   не реальный текст ошибки сервера, хотя тот же `result` (`UnsentAnimalResponse`,
   унаследован от `BaseResponse`) уже содержит настоящие `result.errors`/
   `result.message` — они отбрасываются на границе `updateAnimal()`, наружу
   уходит только `bool`.
9. Ветка исключения: перехватывается `catch (e)` в `_syncEditedAnimals()` →
   `getIt<Talker>().error(...)` (лог, не UI) → `_animalsRepository
   .update(animal.copyWith(errors: Value(e.toString())))` — здесь, в отличие
   от шага 8, реальный текст исключения всё-таки сохраняется.
10. В обеих ветках (8 и 9) `copyWith` **не указывает `needsUpdate`** — поле не
    трогается этим вызовом и остаётся `true`, как было получено из
    `getAllNeedsUpdate()`. Никакого `rethrow` нет — цикл продолжает следующее
    животное, а сам `_syncAllData` не видит никакого исключения от этого шага.
11. **Тот же самый проход**, сразу за `_syncEditedAnimals()`, безусловно
    выполняет `DataUpdateBloc.loadAnimals(event, emit)`:
    `await _animalsRepository.clear()` (`BaseRepository.clear` →
    `BaseDao.clear` → `DELETE` без всякого условия по всей таблице `Animals`),
    затем `_animalIdentificationsRepository.clear()`,
    `_animalWeighingsRepository.clearSync()`, затем
    `await _animalsRepository.syncAllAnimals()`.
12. `syncAllAnimals()` сам ещё раз выполняет `db.delete(db.animals).go()`
    внутри своей транзакции (второе, избыточное удаление той же таблицы),
    получает `localAnimals = await getAllLocalUnsynced()`
    (`AnimalsDao.getAllLocalUnsynced` — `id.isSmallerThanValue(0)`, то есть
    только животные, **вообще ещё не отправленные на сервер**), затем
    постранично получает животных с сервера (`_fetchAnimalsPage` →
    `AnimalsDto.fromJson` → `_animalFromApiJson` → `Animal.fromJson(a)`) и
    батчем вставляет их всех (`batch.insertAll(db.animals, animalData)`), а
    затем восстанавливает батчем только `localsToRestore` — те строки из
    `localAnimals`, чьего `id` нет среди только что вставленных серверных
    (`!serverIds.contains(a.id)`).
13. Отредактированное животное этого сценария — `id >= 0`, поэтому оно **не
    входит** ни в `localAnimals` (фильтр `id < 0`), ни, соответственно, в
    `localsToRestore`. Оно возвращается в таблицу исключительно той версией,
    которую вернул сервер, — а сервер эту правку так и не принял (шаг 7),
    поэтому вернувшаяся версия совпадает с той, что была **до** правки. JSON
    ответа сервера не содержит ключей `needs_update`/`errors` (это чисто
    клиентские поля бухгалтерии синка, сервер их эхом не возвращает), а
    оба поля модели — нативно `nullable()` без `withDefault` — значит,
    построенный из такого JSON `Animal` получает `needsUpdate: null` и
    `errors: null`, и именно с этими значениями строка перезаписывается в
    БД шагом `batch.insertAll`.
14. **Итог одного и того же прохода `DataUpdateStartAll`.** `errors`,
    записанный шагом 8 или 9, и `needsUpdate: true`, из-за которого
    предполагался повтор, оба стёрты уже здесь — не «на следующем проходе»,
    а до конца текущего. `getAllNeedsUpdate()` следующего прохода это
    животное больше не найдёт (`needsUpdate` теперь `null`, не `true`) —
    отправка не повторяется никогда, если пользователь не отредактирует
    животное заново (новое взведение `needsUpdate: true` — снова
    [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)). Весь
    `DataUpdateStartAll` при этом обычно завершается `DataUpdateSuccess` —
    ни возврат `false` из `updateAnimal`, ни последующая перезапись строки не
    долетают до внешнего `try/catch` в `on<DataUpdateStartAll>` как
    исключение.

### Альтернативные потоки

- **Несколько животных в `editedAnimals`, отказывает не все.** Поскольку
  каждое животное отправляется собственным отдельным HTTP-вызовом внутри
  цикла с собственным `try/catch`, успех одного не зависит от отказа
  другого — в отличие от батч-обновления мест
  ([UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)), где весь
  пакет атомарен. Но итоговая судьба одинакова для успешных и неуспешных
  строк на следующем шаге: успешные уже получили `needsUpdate: false,
  errors: null` явно (шаг «ok» в `_syncEditedAnimals`, не описан подробно в
  этом ERROR-сценарии) и `loadAnimals()` их не меняет содержательно (сервер
  подтверждает ту же версию); неуспешные — единственные, для кого
  перезапись шагом 11–13 фактически меняет наблюдаемое состояние (стирает
  только что записанный `errors`).
- **Два технически разных подтипа отказа объединены в один и тот же
  результат, но с разной степенью детализации.** Не-`1` статус ответа
  теряет содержательный текст сервера (заменяется константой
  `'updateAnimal failed'`), брошенное исключение — нет
  (`e.toString()` сохраняется). Тот же класс `UnsentAnimalResponse`,
  использованный здесь, в другом sync-сценарии этого же модуля —
  [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md),
  `AnimalsRepository._syncLocalAnimalFarm` / `DataUpdateBloc
  ._syncAllLocalAnimals` — сохраняет реальный `result.errorsJson`/
  `result.messageJson` в обеих ветках отказа. Здесь же ветка «штатного»
  отказа (без исключения) единственная во всём модуле теряет содержимое
  ответа сервера полностью — независимо от вывода шага 14 (оба варианта
  текста одинаково стираются следующим шагом), это самостоятельная,
  отдельно наблюдаемая находка.
- **`loadAnimals()`/`syncAllAnimals()` сама падает исключением** (например
  сеть пропадает между `PUT updateAnimal` и последующим постраничным `GET
  .../animals`). `loadAnimals()` оборачивает свой единственный внутренний
  вызов в `try { ... } catch (_) { rethrow; }` — исключение долетает до
  `_syncAllData` → … → внешнего `try/catch` в `on<DataUpdateStartAll>` →
  `DataUpdateFailure`. Но к этому моменту `await _animalsRepository.clear()`
  (первая строка `loadAnimals()`, до вызова `syncAllAnimals()`) уже
  выполнилась безусловно — вся локальная таблица `Animals` уже пуста, а
  восстановление (даже частичное, для `id < 0`) внутри `syncAllAnimals()`
  ещё не наступило. В этом случае и правка этого сценария, и **вообще все
  локальные животные** (включая ещё не отправленные `id < 0`) отсутствуют
  локально до следующего успешного прохода — риск шире, чем эта конкретная
  ERROR-ветка, но проходит через тот же код, что стирает результат этого
  сценария в основном потоке.
- **`editedAnimals` пуст** (нет ни одного животного с `needsUpdate: true`).
  Цикл `_syncEditedAnimals()` не выполняет ни одной итерации, шаг
  вырождается в no-op; сценарий не наступает вовсе.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — единственная
  сущность, чьи поля `errors`/`needsUpdate` меняются на обоих этапах: и на
  этапе записи ошибки (шаги 8–9), и на этапе последующей безусловной
  перезаписи всей строки данными с сервера (шаги 11–13).
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — сама правка этого сценария ([EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md))
  идентификации не касается, но шаг 11 (`loadAnimals()`) безусловно очищает
  (`_animalIdentificationsRepository.clear()`) и пересобирает всю таблицу
  `AnimalIdentifications` в рамках того же прохода, затрагивая в том числе
  идентификации животного из этого сценария.

### Бизнес-правила

- Каждое животное из `getAllNeedsUpdate()` обрабатывается независимо, в
  цикле, со своим собственным `try/catch` — отказ одного не прерывает
  обработку остальных и не прерывает `_syncAllData` (в отличие от
  батч-паттерна мест, [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md)).
- `needsUpdate` сбрасывается в `false` только в ветке успеха этого шага;
  сам шаг `_syncEditedAnimals()` никогда не сбрасывает его на отказе.
- Ровно тот же проход, следующим шагом (`loadAnimals`), безусловно
  перезаписывает всю таблицу `Animals` данными с сервера и не сохраняет
  `needsUpdate`/`errors` ни для одной строки `id >= 0`, которая не входит в
  отдельное множество «ещё не отправленных вовсе» (`id < 0`,
  `getAllLocalUnsynced`) — поэтому фактического повтора на следующем
  проходе не бывает: эффект отказа теряется бесследно в конце того же
  прохода, где возник, а не переживает его.
- `getAllNeedsUpdate()` фильтрует строго по `needsUpdate.equals(true)` (а не
  `IS NOT NULL` или аналогично) — после reload'а поле становится `null`, и
  животное перестаёт попадать в выборку без какого-либо явного, читаемого в
  одном месте сброса — сброс происходит побочно, как следствие того, что
  дефолт колонки для нового значения из JSON — `null`.
- `Animal.errors` — единственная видимая пользователю поверхность этого
  сценария: фильтр `showOnlyErrorAnimal`
  (`lib/pages/animal_filters/animal_filters_bloc.dart`,
  `AnimalFiltersEventSetShowOnlyErrorAnimal`) на экране списка животных
  (`lib/pages/animals/animals_bloc.dart`) показывает только животных, у
  которых `errors != null && errors.isNotEmpty`. Запрос списка — разовый
  (`_animalsRepository.getAnimalsWithoutFarm()` по событию), не поток —
  поэтому пользователь может увидеть этот `errors` только успев открыть
  список именно в промежутке между шагом 10 и шагом 13 одного и того же
  прохода.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — весь сценарий, включая интерференцию с непосредственно
следующим шагом прохода (`loadAnimals`), прослеживается по существующему
коду без пробелов, требующих уточнения у пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешний `try/catch` всего прохода; отказ одного животного до него не долетает — проход завершается `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` / `updateAndSyncRegagro` | CURRENT | путь вызова к `_syncAllData`, только для авторизованного пользователя |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAllData` | CURRENT | фиксированная последовательность шагов; `_syncEditedAnimals()` и `loadAnimals()` — соседние шаги без ветвления между ними |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncEditedAnimals` | CURRENT | ядро сценария: цикл по `getAllNeedsUpdate()`, запись `errors` на отказе/исключении, `needsUpdate` не трогается |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.loadAnimals` | CURRENT | безусловно следует сразу за `_syncEditedAnimals`; `clear()` + `syncAllAnimals()` стирают результат этого сценария для строк `id >= 0` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllNeedsUpdate` | CURRENT | делегирует в `AnimalsDao.getAllNeedsUpdate` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.updateAnimal` | CURRENT | `PUT .../updateAnimal`; парсит `UnsentAnimalResponse`, но наружу отдаёт только `bool` — `result.errors`/`result.message` отбрасываются на этой границе |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.clear` / `AnimalsRepository.update` | CURRENT | обёртки `BaseRepository`, используемые этим сценарием (`update` — запись `errors`) и следующим шагом (`clear` — стирание всей таблицы) |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.syncAllAnimals` | CURRENT | полный reload: повторное `db.delete`, вставка серверных данных, восстановление только `id < 0` из `getAllLocalUnsynced()` |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository._syncLocalAnimalFarm` / `syncLocalAnimal` | CURRENT | контрастный sync-путь [EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md) — тот же `UnsentAnimalResponse`, но `errorsJson`/`messageJson` сохраняются полноценно (используется в альтернативном потоке про асимметрию текста ошибки) |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllNeedsUpdate` | CURRENT | `needsUpdate.equals(true) & id.isBiggerOrEqualValue(0)` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllLocalUnsynced` | CURRENT | `id.isSmallerThanValue(0)` — множество, которое `syncAllAnimals()` бережёт от перезаписи |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `Animals.needsUpdate` / `Animals.errors` | CURRENT | оба — `nullable()`, без `withDefault`; JSON без соответствующих ключей даёт `null` |
| `packages/sheep_farm_database/lib/entities/animal/animals.dart` | `AnimalsDto._animalFromApiJson` / `Animal.fromJson` | CURRENT | разбор серверного ответа; ключи `needs_update`/`errors` в нём не участвуют |
| `packages/sheep_farm_database/lib/entities/base_response/base_response.dart` | `BaseResponse.isSuccess` / `isError` / `errorsJson` / `messageJson` | CURRENT | реальный текст ошибки сервера, доступный, но отбрасываемый `AnimalsRepository.updateAnimal` на неуспехе |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` / `BaseDao.upd` | CURRENT | drift-примитивы: `clear` — `DELETE` по всей таблице без условия, `upd` — `updateCurrent().replace(item)` по первичному ключу |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc.on<AnimalEditEventSave>` | CURRENT | предпосылка сценария — взведение `needsUpdate: true` при правке уже синхронизированного животного, см. [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md) |
| `lib/pages/animals/animals_bloc.dart` | `AnimalsBloc` (фильтр `showOnlyErrorAnimal`) | CURRENT | единственная пользовательская поверхность, читающая `Animal.errors`; разовый запрос, не поток |
| `lib/pages/animal_filters/animal_filters_bloc.dart` | `AnimalFiltersData.showOnlyErrorAnimal` / `AnimalFiltersEventSetShowOnlyErrorAnimal` | CURRENT | определение фильтра «только животные с ошибкой» |
| `lib/pages/main/main_page.dart`, `lib/pages/data_update/data_update_page.dart`, `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`, `lib/pages/in_work/in_work_page.dart` | диспатч `DataUpdateStartAll` | CURRENT | точки входа полного sync-прохода, внутри которого наступает этот сценарий |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API, используемый `updateAnimal` и постраничной загрузкой животных |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент обоих сетевых вызовов сценария (`updateAnimal` и последующий reload) |

## Критерии приёмки

- Если `AnimalsRepository.updateAnimal` возвращает `false` (ответ сервера со
  статусом ≠ `1`) для животного из `getAllNeedsUpdate()` — `_syncEditedAnimals`
  записывает `errors: 'updateAnimal failed'`, не трогая `needsUpdate` этим
  вызовом (проверяемо запросом строки сразу после шага, до следующего шага
  прохода).
- Если вызов `updateAnimal` бросает исключение — `errors` записывается как
  `e.toString()`, `needsUpdate` также не меняется этим вызовом.
- `_syncEditedAnimals()` продолжает обработку остальных животных списка после
  отказа одного и завершается без исключения (`completes`, не `throwsA`) —
  ни один отказ этого шага не поднимается до `_syncAllData`.
- Непосредственно за `_syncEditedAnimals()` в том же проходе выполняется
  `loadAnimals()`; если `syncAllAnimals()` успешно получает непустой список
  животных с сервера — локальная строка животного, для которого только что
  были записаны `errors`/`needsUpdate: true`, перезаписывается версией с
  сервера, где оба поля — `null` (не сохраняются), потому что животное
  (`id >= 0`) не входит в `getAllLocalUnsynced()`.
- `getAllNeedsUpdate()` на следующем полном проходе **не** возвращает это
  животное (`needsUpdate` уже не `true`, а `null`) — повторной отправки этой
  правки не происходит.
- Весь `DataUpdateStartAll` в этом сценарии завершается `DataUpdateSuccess`,
  не `DataUpdateFailure`, несмотря на то что как минимум одна правка не была
  принята сервером и в итоге безвозвратно потеряна.

## Связанные тесты

TBD — теста нет. `test/blocs/data_update_bloc_test.dart` не содержит ни
одного упоминания `needsUpdate`, `_syncEditedAnimals` или `updateAnimal`
(`grep -n "needsUpdate\|syncEditedAnimals\|updateAnimal" test/blocs/data_update_bloc_test.dart`
не находит ничего) — уровень `DataUpdateBloc`, на котором происходит и
запись `errors`, и последующая стирающая её перезагрузка, не покрыт вовсе.

Рядом существует `test/repositories/animals_repository_test.dart`, группа
`group('updateAnimal', ...)` (без анкера use-case id, ни старой, ни новой
нумерации) — покрывает только сам `AnimalsRepository.updateAnimal` в
изоляции: успешный ответ (`status: 1` → `true`) и неуспешный
(`status != 1` → `false`), оба без исключения. Она не покрывает: ветку
исключения внутри `updateAnimal`/`_syncEditedAnimals`, запись `errors` в
`_syncEditedAnimals` (обе ветки), и — что здесь основное — взаимодействие с
последующим `loadAnimals()`, стирающим только что записанные `errors`/
`needsUpdate` в рамках того же прохода.

## Открытые вопросы и ограничения

- **Проверенное расхождение с буквальным прочтением
  [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md).** Формулировка
  события («при отказе… текст ошибки записывается в поле `errors`… вместо
  повторной отправки в этом же проходе») сама по себе точна для шага
  `_syncEditedAnimals()` в изоляции, но создаёт впечатление, что повтор
  состоится позже, на следующем проходе. По коду это не так: непосредственно
  следующий шаг того же прохода (`loadAnimals`/`syncAllAnimals`) безусловно
  перезаписывает всю строку животного (`id >= 0`) версией с сервера без
  `errors`/`needsUpdate`, потому что это животное не входит в множество,
  которое `syncAllAnimals()` бережёт (`id < 0`, ещё не отправленные вовсе).
  Итог — не отложенный повтор, а тихая, безвозвратная потеря правки уже в
  конце текущего прохода — тот же по форме риск, что задокументирован для
  мест в [UC-40](UC-40-ACTOR-4-EVT-19-ENT-10-UPDATE_ERROR-IN-FARM.md), но
  вызванный не атомарностью батча, а порядком шагов внутри `_syncAllData`.
  Это зафиксировано здесь как факт о CURRENT-поведении, не исправляется в
  рамках этой чисто документирующей задачи; исправление самого
  [EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md) (замороженного
  артефакта) вне периметра.
- **Асимметрия текста ошибки между двумя технически разными отказами.**
  Ветка «сервер ответил, но неуспехом» теряет реальный текст ответа
  (заменяется константой `'updateAnimal failed'`), хотя тот же
  `UnsentAnimalResponse` содержит настоящие `errors`/`message`; ветка
  «вызов бросил исключение» этот текст сохраняет. Тот же класс ответа в
  соседнем sync-сценарии этого модуля
  ([EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md),
  `_syncAllLocalAnimals`) сохраняет содержимое в обеих ветках через
  `result.errorsJson`/`result.messageJson`. Само по себе не влияет на
  итоговый исход (оба варианта текста одинаково стираются следующим шагом
  прохода, см. пункт выше), но это самостоятельная находка сама по себе.
- **Нет журнальной записи об отказе.** Ни `_addDataUpdateSuccess`, ни
  `_addDataUpdateError` (запись в `DataUpdate` — журнал прохода, SYSTEM) не
  вызываются для отказа конкретного животного внутри `_syncEditedAnimals` —
  единственный след отказа: `Talker.error(...)` в логах приложения, плюс
  временное (до следующего шага того же прохода) значение `errors` в БД,
  видимое пользователю только в узком окне между шагами (см. следующий
  пункт).
- **Гонка при параллельном чтении.** `AnimalsBloc` (фильтр
  `showOnlyErrorAnimal`) выполняет разовый запрос, не поток/`watch` —
  теоретически пользователь может успеть увидеть `Animal.errors` этого
  животного, если откроет/обновит список животных именно в промежутке между
  завершением `_syncEditedAnimals()` и завершением `loadAnimals()` одного и
  того же прохода (между `await`-точками управление уступается event loop).
  Это гонка, не основной путь, и не проверялась экспериментально в рамках
  этого прохода.
- **Отсутствие отдельного события reload'а в глоссарии [MOD-4](../modules/MOD-4-ANIMAL.md).**
  Шаг, который фактически стирает результат этого сценария (`loadAnimals`/
  `AnimalsRepository.syncAllAnimals` — полная перезагрузка животных с
  сервера), не оформлен как собственное `EVT-*` в текущем перечне
  ([EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)…[EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md)),
  хотя для модуля `FARM` аналогичный reload оформлен отдельными событиями
  ([EVT-14](../events/EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md),
  [EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md)).
  Зафиксировано здесь как наблюдение для возможного будущего
  `spec-glossary`-прохода по [MOD-4](../modules/MOD-4-ANIMAL.md); не
  устраняется в рамках этой use-case-задачи.
- **`updateAnimal()` не отправляет `markerType`/идентификации на этом
  эндпоинте вовсе** (в отличие от `changeParentsAnimal`, использующего
  другой путь `/animals/updateAnimal`) — если правка [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)
  когда-либо расширится на идентификации, этот сценарий её не покроет без
  отдельного изменения `updateAnimal()`; вне периметра текущего CURRENT-факта.
