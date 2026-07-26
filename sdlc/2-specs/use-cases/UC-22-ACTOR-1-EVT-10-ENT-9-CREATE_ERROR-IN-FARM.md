- **derived from**: [EVT-10](../events/EVT-10-FARM-CREATED-IN-FARM.md)

# UC-22 — Создание фермы отказывает: локальная запись падает и проглатывается молча

## Назначение

Пользователь проходит мастер создания фермы и подтверждает сохранение, но
локальная запись в Drift-БД (`FarmsDao.insertFarmReturning` /
`FarmsDao.setFarmNegativeRemoteId`, вызываемые из
`FarmRepository.insertFarmWithNegativeRemoteId`) бросает исключение. Ни в
одном из двух возможных мест отказа ошибка не доходит до
`FarmCreateCubit.saveFarm` как исключение — она либо перехвачена и превращена
в `0` (первый шаг), либо вообще не может быть перехвачена окружающим
`try/catch`, потому что второй шаг вызван без `await` (см. «Основной поток» /
«Альтернативные потоки»). В обоих случаях кубит всё равно эмитит успех. Это
единственный отказный путь, который сегодня реально достижим из UI для
[EVT-10](../events/EVT-10-FARM-CREATED-IN-FARM.md) — см. «Открытые вопросы»
про параллельный, но недостижимый обработчик с корректной обработкой ошибки.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — Авторизованный пользователь.

## CURRENT

### Основной поток

1. Пользователь на шаге `FarmCreateStep.name`/`address`(/`kindsVisibility`
   для первой фермы) заполняет мастер создания фермы и на последнем шаге
   нажимает кнопку подтверждения (`_CircularProgressButton.onTap` в
   `farm_create_page.dart`), пройдя проверку `cubit.canSave()`.
2. Так как это первая ферма пользователя, перед сохранением вызывается
   `await cubit.saveKinds()` — не относится к этому сценарию.
3. Вызывается `await cubit.saveFarm()` (`FarmCreateCubit.saveFarm`).
   `state.farm.id == null` (ферма новая), поэтому выполняется ветка `else`:
   `_farmRepository.insertFarmWithNegativeRemoteId(state.farm)`.
4. Внутри `FarmRepository.insertFarmWithNegativeRemoteId` вызывается
   `dao.insertFarmReturning(farm)` — Drift выбрасывает исключение (например
   ошибка диска, повреждение локальной БД, любая другая ошибка `INSERT`, не
   связанная с бизнес-валидацией).
5. Исключение попадает в `catch (e, stackTrace)` того же метода:
   вызывается `log('insertFarmWithNegativeRemoteId: Exception $e')` и
   `log(stackTrace.toString())`, после чего метод **возвращает `0`** —
   исключение дальше не пробрасывается.
6. `FarmCreateCubit.saveFarm` получает `newFarmId == 0` как обычное успешное
   значение (никакого исключения ему не долетает) и эмитит
   `state.copyWith(farm: state.farm.copyWith(remoteId: Value(-newFarmId)))`
   — т.е. `remoteId = -0 = 0`.
7. Сразу следом эмитится `state.copyWith(isSuccess: true)` — код не различает
   «вставка реально удалась с новым id» и «вставка провалилась, вернулся
   дефолт 0» — оба случая ведут в одну и ту же ветку успеха.
8. `finally`-блок `saveFarm` эмитит `isSubmitting: false`.
9. `FarmCreatePage`'s `BlocListener` (`listenWhen: (context, state) =>
   state.isSuccess`) срабатывает и вызывает `_onSuccess(context,
   state.farm.remoteId!)` — `context.pop()` и переход на
   `Routes.createPlace` с `PlaceCreatePageArguments(farmId: 0, ...)`.
10. Пользователь не видит никакой ошибки, никакого `SnackBar` — на экране
    происходит обычный переход дальше по мастеру, как будто ферма успешно
    создана, хотя ни одна строка в локальной БД не появилась.

### Альтернативные потоки

- **Ошибка внутри `dao.setFarmNegativeRemoteId`, а не `dao.insertFarmReturning`
  — не перехватывается вообще, даже той же функцией.**
  `insertFarmWithNegativeRemoteId` вызывает второй шаг без `await`:
  `final result = dao.setFarmNegativeRemoteId(newFarm);` — `result` получает
  сам объект `Future<int>` (используется только в лог-строке
  `log('...Finish: $result')`, которая печатает `Instance of 'Future<int>'`,
  а не итоговое значение), и метод сразу возвращает `newFarm.id!`, не
  дожидаясь исхода `UPDATE`. `setFarmNegativeRemoteId` — тоже `async`-метод;
  по семантике Dart вызов `async`-функции никогда не бросает исключение
  синхронно в точке вызова (даже если тело падает до первого `await`, как
  её собственная проверка `if (farm.id == null) throw
  InvalidDataException(...)`) — он всегда возвращает `Future`, в данном
  случае уже завершившийся с ошибкой. Так как этот `Future` не
  `await`-ится и не оборачивается в `catch`, внешний `try/catch` метода
  `insertFarmWithNegativeRemoteId` **не видит эту ошибку вообще** — он к
  этому моменту уже синхронно вышел из `try`-блока и вернул значение.
  Ошибка становится необработанным исключением «повисшего» `Future`,
  видимым только на уровне зоны/консоли Dart, никак не связанным с
  вызывающим кодом (проверено запуском эквивалентного минимального примера:
  вызов `async`-функции, бросающей до первого `await`, возвращается
  нормально, а исключение всплывает отдельно и позже, минуя окружающий
  `try/catch` вызывающей стороны).
  Разница с основным потоком: `FarmCreateCubit.saveFarm` получает от
  `insertFarmWithNegativeRemoteId` **настоящий положительный** `newFarm.id!`
  (не `0`) и эмитит `remoteId: Value(-newFarmId)` — на вид валидный
  отрицательный `remoteId` в state кубита, — хотя реальная строка `Farms` в
  локальной БД может так и остаться с `remoteId == null` (если `UPDATE` не
  выполнился/не завершился). Получается расхождение между state кубита
  (правдоподобный отрицательный `remoteId`) и фактической БД (`remoteId ==
  null`), не обнаруживаемое ни кубитом, ни UI, ни следующим шагом мастера.
  Такая осиротевшая строка не попадёт под
  `FarmRepository.getAllWithoutRemoteId()`
  (`remoteId.isSmallerThanValue(0)` не выполняется для `null`), то есть не
  будет подхвачена и следующим sync-проходом.
- **Параллельный, но недостижимый из UI обработчик с корректной обработкой
  ошибки.** В `FarmsAndPlacesBloc._onAddFarm`
  (`lib/pages/farms_and_places/farms_page_bloc.dart`) есть отдельный
  обработчик события `FarmsPageEventAddFarm`, который вызывает тот же
  `_farmsRepository.insertFarmWithNegativeRemoteId(event.farm)`, но обёрнут
  в `try/catch`, реально показывающий отказ:
  `emit(FarmsPageError('Ошибка создания фермы: ${e.toString()}'))`. Однако
  `FarmsPageEventAddFarm` нигде не диспатчится из UI-кода приложения (по
  всему `lib/` есть только регистрация обработчика и определение класса
  события — ни одного `.add(FarmsPageEventAddFarm(...))` вне самого файла
  блока). Этот путь недостижим для пользователя сегодня и описывает не
  текущее поведение приложения, а лишь то, как правильно обработанная
  ошибка выглядела бы в соседнем, неиспользуемом коде.

### Связанные сущности

- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — целевая сущность
  попытки создания. В основном потоке строка не создаётся вовсе; в
  альтернативном потоке (ошибка внутри `setFarmNegativeRemoteId`) строка
  создаётся с реальным `id`, но `remoteId` в БД так и остаётся `null`, хотя
  state кубита уже показывает правдоподобный отрицательный `remoteId`.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — не создаётся и не
  читается в этом сценарии, но `_onSuccess` всё равно передаёт
  `farmId: state.farm.remoteId!` (`0` в основном потоке, либо
  правдоподобный, но не соответствующий реальной БД отрицательный `id` в
  альтернативном) в аргументы следующего экрана мастера
  (`Routes.createPlace`) — Place реально создаётся уже за пределами этого
  use-case, потенциально со ссылкой на несуществующую/не найденную по
  этому `remoteId` ферму.

### Бизнес-правила

- `FarmRepository.insertFarmWithNegativeRemoteId` перехватывает исключение
  только из **первого**, `await`-енного шага (`dao.insertFarmReturning`) —
  в этом случае возвращает `0` вместо того, чтобы пробросить ошибку или
  вернуть `null`/специальный маркер отказа.
- Второй шаг (`dao.setFarmNegativeRemoteId`) вызывается без `await` — его
  исключение тем же `try/catch` не перехватывается в принципе, а становится
  необработанным исключением необрабатываемого `Future`, полностью
  независимым от результата, который метод возвращает вызывающему коду.
- `FarmCreateCubit.saveFarm` не имеет собственного `try/catch` вокруг вызова
  `insertFarmWithNegativeRemoteId` (только `finally` для сброса
  `isSubmitting`) — и ему это не нужно в текущем поведении, поскольку
  репозиторий никогда не пробрасывает исключение дальше вызывающему коду
  (первый шаг — перехвачен и превращён в `0`; второй — не долетает до
  вызывающего кода вовсе); `isSuccess: true` эмитится безусловно после
  вызова, без проверки результата на признак отказа.
- `newFarmId == 0` — единственный сигнал отказа именно **первого** шага,
  доступный кубиту, но он никак не проверяется (`0` обрабатывается тем же
  кодом, что и любой другой положительный `id`). Отказ **второго** шага
  кубиту вообще ничем не сигнализируется — он получает настоящий
  положительный `id`, как при полном успехе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — все факты по этому сценарию проверены чтением
`lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart`,
`lib/repositories/farm_repository/farm_repository.dart`,
`packages/sheep_farm_database/lib/entities/farm/farms_dao.dart`,
`lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` и
`lib/pages/farms_and_places/farms_page_bloc.dart`. Утверждение про то, что
неawait-енное исключение внутри `async`-функции не долетает до окружающего
`try/catch` вызывающей стороны, дополнительно перепроверено запуском
минимального эквивалентного примера на `dart` (не только прочитано по
памяти о языке).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_cubit.dart` | `FarmCreateCubit.saveFarm` | CURRENT | вызывает вставку фермы, эмитит `isSuccess: true` безусловно, без проверки результата на отказ |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_state.dart` | `FarmCreateState` | CURRENT | несёт `farm`/`isSuccess`/`isSubmitting`, читаемые UI; не имеет отдельного поля-признака ошибки сохранения |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.insertFarmWithNegativeRemoteId` | CURRENT | перехватывает исключение первого (`await`-енного) шага и возвращает `0`; второй шаг вызван без `await`, его исключение этим же `catch` не перехватывается |
| `packages/sheep_farm_database/lib/entities/farm/farms_dao.dart` | `FarmsDao.insertFarmReturning`, `FarmsDao.setFarmNegativeRemoteId` | CURRENT | два шага локальной записи; оба могут бросить исключение, но только первый вызывается через `await` и виден вызывающему коду |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage._onSuccess`, `BlocListener<FarmCreateCubit, FarmCreateState>` (`listenWhen: state.isSuccess`) | CURRENT | безусловно переходит на создание места по `state.farm.remoteId!`, не проверяя, что ферма реально сохранена |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onAddFarm` | CURRENT | параллельный обработчик той же вставки с корректным `try/catch` → `FarmsPageError`, но не достижим из UI (см. «Открытые вопросы») |

## Критерии приёмки

- При исключении внутри `dao.insertFarmReturning` строка `Farm` не
  создаётся вовсе, `insertFarmWithNegativeRemoteId` возвращает `0`, и
  `FarmCreateCubit.saveFarm` тем не менее эмитит `isSuccess: true` и
  `state.farm.remoteId == 0`.
- При исключении внутри `dao.setFarmNegativeRemoteId` (после того как
  `dao.insertFarmReturning` уже создал строку) `insertFarmWithNegativeRemoteId`
  возвращает настоящий положительный `id` строки, `FarmCreateCubit.saveFarm`
  эмитит `isSuccess: true` и правдоподобный отрицательный
  `state.farm.remoteId`, при этом реальная строка `Farms` в БД остаётся с
  `remoteId == null`.
- Ни в одном из двух случаев `FarmCreateCubit.saveFarm` не эмитит
  `errorMessage` и не отличает отказ от успеха.
- Пользователь не получает никакого `SnackBar`/сообщения об ошибке и
  переходит на экран создания места — с `farmId: 0` в первом случае, с
  правдоподобным, но не соответствующим реальной БД `farmId` во втором.
- `FarmsAndPlacesBloc._onAddFarm` при том же самом исключении из
  `insertFarmWithNegativeRemoteId` эмитит `FarmsPageError` с текстом,
  содержащим `'Ошибка создания фермы'` — но этот обработчик недостижим ни
  из одного экрана приложения.

## Связанные тесты

`test/pages/farm_create_cubit_test.dart`, group `'FarmCreateCubit.saveFarm'`
(будет переименовано, не трогать сейчас) — TBD, теста на этот сценарий
(отказ/проглатывание ошибки при `farm.id == null`) нет: все три существующих
теста группы покрывают только успешную вставку, `update`-ветку и
`isSubmitting`-защиту от повторного вызова.

`test/pages/farms_and_places_bloc_test.dart`, group `'UC-2 —
FarmsAndPlacesBloc._onAddFarm ERROR'`:

- test `'insertFarmWithNegativeRemoteId бросает -> FarmsPageError("Ошибка
  создания фермы: ...")'` — покрывает тот же исходный вызов репозитория, но
  через недостижимый из UI обработчик `FarmsAndPlacesBloc._onAddFarm`, не
  через `FarmCreateCubit.saveFarm` из основного потока этого use-case.

## Открытые вопросы и ограничения

- **Известный дефект.** `FarmRepository.insertFarmWithNegativeRemoteId`
  проглатывает любое исключение и возвращает `0` вместо того, чтобы
  пробросить ошибку или вернуть `null`. `FarmCreateCubit.saveFarm` не
  проверяет `newFarmId` на `0` и безусловно эмитит `isSuccess: true`. В
  итоге отказ создания фермы неотличим от успеха ни в состоянии кубита, ни
  на экране — пользователь не получает вообще никакой обратной связи об
  ошибке.
- **Второй известный дефект, отдельный от первого.**
  `dao.setFarmNegativeRemoteId(newFarm)` вызывается в
  `insertFarmWithNegativeRemoteId` без `await` — её исключение (в т.ч.
  собственную синхронную по виду проверку `if (farm.id == null) throw
  InvalidDataException(...)`, которая по семантике Dart `async`-функций всё
  равно не бросается синхронно в точку вызова) окружающий `try/catch` не
  перехватывает вообще: он к этому моменту уже вернул значение. Если
  исключение всё же происходит на этом шаге (после того как
  `insertFarmReturning` уже создал строку), в локальной БД остаётся
  осиротевшая запись `Farm` с `remoteId == null` — она не подпадает под
  фильтр `FarmRepository.getAllWithoutRemoteId()`
  (`remoteId.isSmallerThanValue(0)` не выполняется для `null`), то есть
  никогда не будет подобрана следующим sync-проходом. При этом
  `FarmCreateCubit.saveFarm` получает от `insertFarmWithNegativeRemoteId`
  настоящий положительный `id` (не `0`) и выставляет в state кубита
  правдоподобный отрицательный `remoteId`, которого в реальной БД не
  существует — расхождение между state кубита и БД, не обнаруживаемое
  никаким кодом в этом сценарии.
- В коде существует параллельный, корректно обрабатывающий эту же ошибку
  путь — `FarmsAndPlacesBloc._onAddFarm` — но `FarmsPageEventAddFarm`
  нигде не диспатчится из UI (проверено `grep` по всему `lib/`). Это
  мёртвый код с точки зрения пользовательского пути: он показывает, как
  должна была бы выглядеть обработка ошибки, но не участвует в реальном
  сценарии создания фермы через мастер.
- `_onSuccess(context, state.farm.remoteId!)` использует `!` — переход на
  создание места происходит безусловно при обоих отказных сценариях: с
  `farmId: 0` (отказ первого шага) или с правдоподобным, но не
  соответствующим реальной БД `farmId` (отказ второго шага) — что дальше
  происходит на экране создания места в этих условиях, не специфицировано
  этим use-case.
