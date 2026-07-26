# UC-28 — Sync правки фермы отказывает: `break` вместо `continue` останавливает весь батш обновлений (ERROR)

## Назначение

Во время явного sync-прохода система отправляет на сервер локальные правки
уже синхронизированных ферм (`needUpdate: true`) по одной, в цикле. Если хотя
бы одна ферма в этом батче отвечает отказом (не `status == "1"`) или сам
запрос падает исключением, весь цикл останавливается (`break`, не
`continue`) — все фермы, идущие в очереди после отказавшей, в этом проходе не
отправляются вовсе, даже если их правки уже давно ждут своей очереди. Хуже
того: следующий шаг того же прохода — безусловная полная перезагрузка ферм с
сервера — стирает признак «требует отправки» для всех ферм разом, поэтому ни
одна из непереданных правок не будет повторена и на следующем проходе тоже:
эффект — не отложенная отправка, а тихая потеря правки.

## Пользователь

[ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) — система, действующая внутри
уже запущенного полного sync-прохода (`DataUpdateBloc`); не человек и не
отдельное решение пользователя на этом шаге. Сам проход перед этим запускается
человеком или автоматически (см. `lib/pages/main/main_page.dart`,
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`,
`lib/pages/in_work/in_work_page.dart`, `lib/pages/data_update/data_update_page.dart`)
— сам механизм запуска прохода принадлежит модулю `SYSTEM` (см. границу
[MOD-3](../modules/MOD-3-FARM.md)), здесь не переопределяется.

## CURRENT

### Основной поток

1. **Предпосылка.** Как минимум две уже синхронизированные фермы (`remoteId`
   положительный) были локально отредактированы ранее —
   [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md),
   `FarmsAndPlacesBloc._onEditFarm` — каждая правка выставила
   `needUpdate: true` и сохранила изменённые поля локально; на сервер ничего
   ещё не отправлялось. Условно — фермы A, B, C в этом порядке в локальной
   БД.
2. Запускается полный sync-проход: `DataUpdateBloc.on<DataUpdateStartAll>`
   проверяет сеть, затем (пользователь авторизован) вызывает
   `DataUpdateBloc._syncAuthData`, которая безусловно вызывает
   `DataUpdateBloc._syncFarms()` — без `try/catch` вокруг этого вызова.
3. `_syncFarms()` выполняет три шага строго по порядку, каждый со своим
   `await`, без ветвления по результату предыдущего:
   `_storeFarmsToRDS()` → `_updateFarmsOnRDS()` (этот сценарий) →
   `_loadFarmsFromRDS()`.
4. `_updateFarmsOnRDS()` запрашивает `FarmRepository.getAllToUpdate()` —
   `needUpdate.equals(true) & remoteId.isNotNull()` — получает список A, B, C.
5. `FarmRepository.updateFarmsOnRDS(farms)` идёт по списку в цикле, для
   каждой фермы отправляя `PUT
   ${Constants.registrationServiceApi}/farms/update` через
   `getIt.get<ApiClient>(instanceName: 'farm_rpc')`:
   - ферма A: сервер отвечает `status == "1"` → `success = true`, цикл
     продолжается (`continue`, неявно — просто следующая итерация);
   - ферма B: сервер отвечает любым статусом, отличным от `"1"`, **либо**
     сам вызов бросает исключение (например `DioException`, таймаут/нет
     сети) — оба случая обрабатываются одинаково: `success = false;
     break;`. Ферма C **не отправляется вообще** — до неё цикл не
     доходит.
6. `updateFarmsOnRDS` возвращает `false` (последнее установленное значение
   `success`). Обратно в `DataUpdateBloc._updateFarmsOnRDS`: `isUpdated ==
   false` → выполняется только `log('_updateFarmsOnRDS: Failed to update
   farms on RDS')` в `else`-ветке. **Ветка `if (isUpdated)`, вызывающая
   `_farmRepository.updateAll(farmsToUpdate.map((f) =>
   f.copyWith(needUpdate: false))...)`, не выполняется вовсе** — это
   касается и фермы A, чья правка на сервере уже фактически принята: её
   локальный `needUpdate` тоже не сбрасывается на этом шаге.
7. Никакое исключение наружу не пробрасывается — `_updateFarmsOnRDS()`
   (метод бло́ка) завершается нормально, `_syncFarms()` продолжает со
   следующим шагом безусловно.
8. `_loadFarmsFromRDS()` вызывает `FarmRepository.getAllFarmsFromRDS()` →
   `GET ${Constants.registrationServiceApi}/farms`. В типичном случае (сервер
   отвечает `status == "1"` и в системе вообще есть фермы) ответ непустой.
9. `if (res.isEmpty) return;` — условие ложно (ответ непустой), поэтому
   выполняется `await _farmRepository.clear()` (полностью удаляет все строки
   таблицы `Farms`), затем `await _farmRepository.insertAll(res)`. Каждый
   элемент `res` — `FarmsCompanion`, построенный
   `FarmExtension.fromJsonRDS`, который **не указывает `needUpdate` вовсе** —
   при вставке (`InsertMode.insertOrReplace`) используется дефолт колонки,
   `Constant(false)` (`Farms.needUpdate`,
   `boolean().withDefault(const Constant(false))`).
10. Итоговое локальное состояние после этого одного прохода:
    - **Ферма A** (правка дошла до сервера) — локальная строка заменена
      актуальными серверными данными, включая правку; `needUpdate`
      корректно оказывается `false` — но не потому, что шаг 6 его сбросил
      (он этого не сделал), а потому, что шаг 9 перезаписал всю строку
      заново.
    - **Ферма B** (правка отклонена/упала с ошибкой) — локальная строка
      заменена **старыми, досерверными** данными; правка полностью потеряна,
      `needUpdate` сброшен в `false` — следующий проход её уже не найдёт
      через `getAllToUpdate()` и не повторит попытку.
    - **Ферма C** (не была даже отправлена, просто из-за `break` на B) —
      та же судьба, что и у B: локальная правка стирается тем же reload'ом,
      `needUpdate` сброшен, повторной попытки не будет.
11. Весь `DataUpdateStartAll` при этом всё равно завершается
    `DataUpdateSuccess` (см. `on<DataUpdateStartAll>`) — ни одно исключение
    не долетело до внешнего `try/catch`, поэтому пользователь не видит
    никакого сообщения об ошибке. `Farms.needUpdate` нигде не читается ни
    одним виджетом (проверено по всему `lib/`) — в интерфейсе также нет
    никакого индикатора «правка не отправлена» ни до, ни после этого
    прохода.

### Альтернативные потоки

- **Отказавшая ферма — последняя (или единственная) в списке.** Поведение
  идентично основному потоку по сути: `break` просто не пропускает больше ни
  одной итерации после неё, потому что их и не было. Итог тот же —
  `updateFarmsOnRDS` возвращает `false`, `updateAll` не вызывается,
  последующий reload стирает `needUpdate` и данные правки этой фермы.
- **Два разных технических подтипа отказа объединены в один и тот же
  результат.** Не-`"1"` статус ответа сервера и брошенное исключение
  (сеть/таймаут) обрабатываются кодом абсолютно одинаково — оба ведут к
  `success = false; break;` без какого-либо различения причины дальше по
  потоку (ни в возвращаемом значении, ни в логах, кроме текста самого
  сообщения). Поэтому оба технических подтипа — часть этого же
  `UPDATE_ERROR`-сценария, не два разных use-case.
- **Перезагрузка списка (шаг 8) сама падает исключением** (например сеть
  пропала между PUT-вызовами и последующим GET). В отличие от
  `updateFarmsOnRDS`, `getAllFarmsAndPlacesFromRDS` не оборачивает сам вызов
  `rpcClientSHTP.call(message)` в `try/catch` — исключение здесь
  пробрасывается наружу через `_loadFarmsFromRDS` → `_syncFarms` →
  `_syncAuthData` → внешний `try/catch` в `on<DataUpdateStartAll>` →
  `DataUpdateFailure`. В этом случае reload (шаг 9) не происходит вовсе,
  поэтому `needUpdate: true` фермы B и C **сохраняется** локально — их
  правки при этом не теряются и будут повторно предложены к отправке на
  следующем полном проходе. Это не основной, а более редкий побочный
  случай — обратный по исходу основному потоку при внешне похожей причине
  («не долетело до сервера»).
- **Перезагрузка (шаг 8) возвращает пустой список** (`response['status'] !=
  "1"` именно на этом GET-запросе, отдельном от PUT-вызовов из шага 5). Тогда
  `if (res.isEmpty) return;` срабатывает раньше `clear()`/`insertAll()` —
  локальные фермы не трогаются вовсе, `needUpdate: true` у B и C
  сохраняется, они будут повторно предложены на следующем проходе. Как и
  предыдущий пункт — расходится с основным потоком только потому, что
  reload в этот раз не долетел до фактической перезаписи локальной таблицы.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — единственная сущность,
  чьё состояние (данные полей и флаг `needUpdate`) меняется на всех этапах
  этого сценария: и на этапе неудачной отправки правки, и на этапе
  последующей безусловной перезаписи через reload.

### Бизнес-правила

- Фермы, требующие обновления на сервере, отправляются по одной, отдельными
  HTTP PUT-запросами, не батчем — как и создание ([EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md)), но с другой
  стратегией на отказ: создание использует `continue` (частичный успех
  поддерживается — см. `FarmRepository.storeFarmsOnRDS`), обновление
  использует `break` (частичный успех внутри одного прохода не
  поддерживается: все фермы после первой отказавшей просто не пытаются
  отправиться).
- Успех/неудача батча обновления фиксируется одним общим `bool` на весь
  вызов `updateFarmsOnRDS`, не по каждой ферме отдельно — поэтому даже
  ферма, чей персональный PUT-ответ был `status == "1"`, не получает
  собственного, независимого от соседей по батчу, сброса `needUpdate` на
  этом шаге.
- Последующая полная перезагрузка списка ферм с сервера
  ([EVT-14](../events/EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md)) выполняется в рамках того же прохода безусловно, сразу после
  попытки обновления, без какой-либо связи с её результатом — именно она, а
  не сама неудавшаяся отправка, окончательно определяет судьбу локальной
  правки: непереданные изменения замещаются серверной (для них — устаревшей)
  версией, а признак «требует отправки» сбрасывается в дефолтное значение
  колонки вместе с остальными полями строки.
- Ни неудача самой отправки, ни последующая потеря правки при reload не
  порождают ни исключения, долетающего до `DataUpdateStartAll`, ни какого-либо
  состояния ошибки, ни записи, видимой пользователю где-либо в UI — единственный
  след — текстовые сообщения в лог (`log(...)`), не выводимые никуда за пределы
  логов приложения.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — весь сценарий, включая переход к следующему шагу
(`_loadFarmsFromRDS`) и его взаимодействие с уже неудавшимся обновлением,
прослеживается по существующему коду без пробелов, требующих уточнения у
пользователя.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc.on<DataUpdateStartAll>` | CURRENT | внешний `try/catch` прохода; ошибки, проглоченные внутри репозитория, до него не долетают — проход завершается `DataUpdateSuccess` |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncAuthData` | CURRENT | вызывает `_syncFarms()` без собственной обработки ошибок вокруг него |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._syncFarms` | CURRENT | фиксированная последовательность `_storeFarmsToRDS` → `_updateFarmsOnRDS` → `_loadFarmsFromRDS`, все шаги безусловны |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._updateFarmsOnRDS` | CURRENT | получает фермы с `needUpdate:true`, вызывает `FarmRepository.updateFarmsOnRDS`; сбрасывает `needUpdate` только при `isUpdated == true` для всего батча целиком |
| `lib/blocs/data_update/data_update_bloc.dart` | `DataUpdateBloc._loadFarmsFromRDS` | CURRENT | безусловно следует за `_updateFarmsOnRDS`; при непустом ответе сервера полностью очищает и перезаписывает локальную таблицу `Farms` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.updateFarmsOnRDS` | CURRENT | цикл `PUT .../farms/update` по одной ферме; `break` (не `continue`) при первом не-`"1"` статусе или исключении |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllToUpdate` | CURRENT | запрос ферм: `needUpdate.equals(true) & remoteId.isNotNull()` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsFromRDS` | CURRENT | `GET .../farms` для последующего reload; вызывает `getAllFarmsAndPlacesFromRDS` |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getAllFarmsAndPlacesFromRDS` | CURRENT | сам сетевой вызов не обёрнут в `try/catch` — исключение здесь пробрасывается наружу, в отличие от `updateFarmsOnRDS` |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `Farms.needUpdate` | CURRENT | `BoolColumn`, `withDefault(const Constant(false))` |
| `packages/sheep_farm_database/lib/entities/farm/farms.dart` | `FarmExtension.fromJsonRDS` | CURRENT | конвертация серверного JSON в `FarmsCompanion`; поле `needUpdate` не указывается — берётся дефолт колонки |
| `lib/repositories/base_repository.dart` | `BaseRepository.clear` / `insertAll` / `updateAll` | CURRENT | обёртки над `BaseDao`, используемые reload'ом (`clear`+`insertAll`) и несостоявшимся сбросом флага (`updateAll`) |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.clear` / `insAll` / `updAll` | CURRENT | drift-примитивы: `clear` удаляет все строки, `insAll` — `insertOrReplace` батчем, `updAll` — `upd` по одной записи в транзакции |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onEditFarm` | CURRENT | путь, которым локальная правка (предпосылка сценария) выставляет `needUpdate: true` — см. [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) |
| `lib/constants.dart` | `Constants.registrationServiceApi` | CURRENT | базовый путь API ферм, используемый в PUT/GET-запросах |
| `lib/network/api_client/api_client.dart` | `ApiClient` (instance `'farm_rpc'`) | CURRENT | HTTP-клиент, через который идут все PUT/GET-вызовы этого сценария |

## Критерии приёмки

- Если в батче из N ≥ 2 ферм с `needUpdate: true` какая-либо ферма, кроме
  последней в списке, получает от сервера статус, отличный от `"1"`, либо PUT
  завершается исключением — `FarmRepository.updateFarmsOnRDS` возвращает
  `false`, и ни один следующий по списку PUT-запрос не выполняется (проверяемо
  подсчётом вызовов мока).
- `DataUpdateBloc._updateFarmsOnRDS` при `isUpdated == false` не вызывает
  `FarmRepository.updateAll` вовсе — ни для отказавшей фермы, ни для
  предшествовавших ей в списке, чей персональный PUT ранее завершился
  успешно.
- `_updateFarmsOnRDS()`/`_syncFarms()` завершаются без исключения
  (`completes`, а не `throwsA(...)`) — сбой не всплывает выше по цепочке
  вызовов.
- Если следующий за этим `_loadFarmsFromRDS()` получает непустой ответ от
  `GET .../farms`, локальная таблица `Farms` полностью перезаписывается, и
  `needUpdate` каждой перезаписанной строки становится `false` — в том числе
  для ферм, чья правка не дошла до сервера в этом же проходе.
- Полный проход `DataUpdateStartAll` в этом сценарии завершается
  `DataUpdateSuccess`, не `DataUpdateFailure`, несмотря на то что как минимум
  одна ферма не была обновлена на сервере.

## Связанные тесты

TBD — теста нет. На уровне `data_update_bloc.dart` для sync-сценариев ферм
(в т.ч. этого) тестов не существует: `test/blocs/data_update_bloc_test.dart`
содержит только тест конструирования блока и тест `DataUpdateClear`, ни
`_syncFarms`, ни `_updateFarmsOnRDS`, ни `FarmRepository.updateFarmsOnRDS`
там не упоминаются. Отдельного `test/repositories/farm_repository_test.dart`
в репозитории не существует вовсе — `grep -rl "updateFarmsOnRDS"
test/` не находит ни одного файла.

## Открытые вопросы и ограничения

- **Задокументированный, не устраняемый в этом проходе (TARGET == CURRENT)
  риск тихой потери данных.** Комбинация «`break` вместо `continue`» +
  «безусловный reload сразу следующим шагом, стирающий `needUpdate` через
  дефолт колонки независимо от того, дошла ли правка до сервера» означает,
  что для любой фермы, чья правка не была принята сервером в конкретном
  проходе (сама отказавшая, и любая другая в очереди после неё, даже не
  подвергавшаяся попытке), эффект — не «попробуем на следующем проходе», а
  безвозвратная потеря правки уже в этом же проходе — при обычном,
  непустом ответе GET-эндпоинта ферм.
- **Отсутствие любого пользовательского сигнала.** `Farms.needUpdate` не
  читается ни одним виджетом в `lib/` — ни до, ни после такого прохода
  пользователь не видит признака «правка не отправлена» или «правка была
  отменена»; весь проход репортится как `DataUpdateSuccess`.
- **Асимметрия create/update, не разрешаемая здесь.** [EVT-12](../events/EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) (создание)
  поддерживает частичный успех через `continue`, [EVT-13](../events/EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md) (обновление) — нет;
  должна ли стратегия обновления соответствовать стратегии создания —
  вопрос будущего TARGET-прохода, не решается в рамках этой чисто
  документирующей задачи.
- **Два параллельных кода, устанавливающих ту же предпосылку.** Помимо
  `FarmsAndPlacesBloc._onEditFarm` ([EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md)), `FarmCreateCubit.saveFarm` (ветка
  `state.farm.id != null`, `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart`)
  тоже выставляет `needUpdate: true` при сохранении уже существующей фермы —
  два разных экранных пути приводят к одной и той же предпосылке этого
  сценария; не реконсилировано и не описывается подробнее здесь, так как
  сама предпосылка (а не то, как именно она возникла) — предмет [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md).
