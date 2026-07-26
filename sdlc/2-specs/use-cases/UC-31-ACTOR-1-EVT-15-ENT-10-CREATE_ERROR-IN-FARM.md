- **derived from**: [EVT-15](../events/EVT-15-PLACE-CREATED-IN-FARM.md)

# UC-31 — Создание отделения фермы отказывает: локальная вставка проглатывается молча

## Назначение

Пользователь проходит мастер создания/редактирования структуры фермы и жмёт
«Сохранить структуру», но локальная запись нового отделения в Drift-БД
(`PlacesDao.insertPlaceReturning` / `PlacesDao.setPlaceNegativeRemoteId`,
вызываемые из `PlaceRepository.insertPlaceWithNegativeRemoteId`) бросает
исключение. В отличие от аналогичного сценария для фермы, здесь событие,
запускающее вставку (`FarmsPageEventAddPlace`), реально диспатчится из UI, и
у обработчика (`FarmsAndPlacesBloc._onAddPlace`) на бумаге есть собственный
`try/catch`, эмитящий `FarmsPageError`. Но сам репозиторий перехватывает
исключение на уровень ниже и никогда не пробрасывает его дальше — поэтому
для настоящего сбоя `PlacesDao` эта ветвь `_onAddPlace` недостижима, а
эмитированная (в гипотетическом случае) ошибка всё равно не имеет во всём
приложении ни одного потребителя.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь,
управляющий структурой своей фермы.

## CURRENT

### Основной поток

1. Пользователь в мастере создания/редактирования структуры
   (`PlaceCreatePage` → `_PlacesList.build`,
   `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`)
   заполняет список отделений и нажимает «Сохранить структуру»
   (`l10n.save_structure`). `cubit.getPlacesToSave()`
   (`PlaceCreateCubit.getPlacesToSave`) отфильтровывает места с пустым
   именем; для каждого оставшегося места без `idRemote` диспатчится
   `context.read<FarmsAndPlacesBloc>().add(FarmsPageEventAddPlace(place))`.
   Сразу после цикла диспатчей, не дожидаясь ни одного из асинхронных
   обработчиков блока, вызывается `context.pop()`.
2. `FarmsAndPlacesBloc._onAddPlace` (`lib/pages/farms_and_places/farms_page_bloc.dart`)
   получает событие внутри собственного `try`: вызывает
   `await _placeRepository.insertPlaceWithNegativeRemoteId(event.place)`.
3. Внутри `PlaceRepository.insertPlaceWithNegativeRemoteId`
   (`lib/repositories/place_repository/place_repository.dart`) — свой
   отдельный `try`: `await dao.insertPlaceReturning(place)` бросает
   исключение (например ошибка диска, повреждение локальной БД, любая
   другая ошибка `INSERT`, не связанная с бизнес-валидацией — пустые имена
   уже отфильтрованы кубитом на предыдущем шаге, а `Places.farmId` не несёт
   реального FK-ограничения на уровне схемы).
4. Исключение попадает в `catch (e, stackTrace)` того же метода
   (`PlaceRepository.insertPlaceWithNegativeRemoteId`):
   `log('insertPlaceWithNegativeRemoteId: Exception $e')` +
   `log(stackTrace.toString())`, после чего метод завершается нормально —
   `Future<void>` не пробрасывает исключение дальше и не возвращает вообще
   никакого признака отказа (даже обманчивого `0`, как в аналогичном
   сценарии для фермы).
5. Поэтому `await` внутри `FarmsAndPlacesBloc._onAddPlace` не бросает
   исключение — исполнение `try`-блока обработчика продолжается как при
   обычном успехе, и он безусловно вызывает `add(FarmsPageEventLoadFarms())`.
   Строка `catch (e) { emit(FarmsPageError('Ошибка создания места:
   ${e.toString()}')); }` того же обработчика для этого (реального)
   источника ошибки не выполняется вовсе.
6. `FarmsPageEventLoadFarms()` перезагружает список ферм/мест/животных
   (`FarmsAndPlacesBloc._onLoadFarms`) и эмитит
   `FarmsPageLoadedWithAnimals` — с тем же содержимым, что и до попытки:
   место не появилось, потому что `INSERT` не прошёл, но это никак не
   помечено как ошибка.
7. Пользователь тем временем уже видит предыдущий экран — `context.pop()`
   на шаге 1 выполнился синхронно задолго до того, как асинхронный вызов
   репозитория вообще завершился. Экран со списком мест фермы обновляется
   независимо от этого блока — через собственную подписку
   `MainNavigatorCubit` на `PlaceRepository.watchAll()`
   (`lib/pages/main_navigator/cubit/main_navigator_cubit.dart`); при
   проглоченном исключении строка не вставлена, стрим не эмитит новое
   значение, и отделение просто отсутствует в списке без какого-либо
   сообщения об ошибке.
8. Даже если бы `catch` в `_onAddPlace` сработал (см. «Альтернативные
   потоки» — путь, которым сегодня пользуется только юнит-тест),
   `emit(FarmsPageError(...))` был бы адресован состоянию
   `FarmsAndPlacesBloc`, у которого во всём `lib/` нет ни одного
   `BlocBuilder`/`BlocListener`/`BlocConsumer<FarmsAndPlacesBloc,
   FarmsPageState>` — единственные упоминания `FarmsPageState`/
   `FarmsPageError` вне файлов самого блока/событий/состояний отсутствуют
   (проверено `grep` по всему `lib/`). Даже теоретически достигнутая
   ошибка не привела бы ни к какому `SnackBar` или иной обратной связи.

### Альтернативные потоки

- **Падает второй шаг (`setPlaceNegativeRemoteId`), а не первый.** Если
  `dao.insertPlaceReturning(place)` успешно создаёт строку (получает
  реальный автоинкрементный `id`), но
  `dao.setPlaceNegativeRemoteId(newPlace)` — вызванный внутри
  `PlaceRepository.insertPlaceWithNegativeRemoteId` без `await`
  (`final result = dao.setPlaceNegativeRemoteId(newPlace);`) — падает уже
  после того, как синхронный участок `try`-блока репозитория формально
  выполнился, это исключение не попадает вообще ни в один `catch` во всей
  цепочке (ни в `catch` самого репозитория, тот уже вышел из своего `try`,
  ни тем более в `catch` `_onAddPlace`) — необработанное отклонение
  `Future`, видимое разве что в логах рантайма. В локальной БД остаётся
  осиротевшая строка `Place` с `idRemote == null` (не отрицательным) — она
  не попадёт под `PlaceRepository.getAllWithoutRemoteId()`
  (`idRemote.isSmallerThanValue(0)` не совпадает с `null`), то есть никогда
  не будет подхвачена следующим sync-проходом.
- **Гипотетический путь, реально покрытый только юнит-тестом.** Если бы
  `_placeRepository.insertPlaceWithNegativeRemoteId(event.place)` в
  принципе пробросило исключение наверх (сегодня невозможно при данной
  реализации репозитория, см. шаги 3–4 основного потока),
  `FarmsAndPlacesBloc._onAddPlace`'s собственный `catch (e) {
  emit(FarmsPageError('Ошибка создания места: ${e.toString()}')); }`
  сработал бы корректно. Именно этот путь эмулирует существующий тест
  (`test/pages/farms_and_places_bloc_test.dart`, group `'UC-8 — …ERROR'`),
  подставляя мок `PlaceRepository` с `thenThrow` прямо на уровне
  интерфейса репозитория, минуя реальную реализацию
  `insertPlaceWithNegativeRemoteId` и её внутренний swallow — тест
  проходит, но не описывает достижимое сегодня поведение приложения.
- **Пакетное сохранение нескольких новых мест за один тап.**
  `cubit.getPlacesToSave()` может вернуть сразу несколько мест без
  `idRemote` (например весь дефолтный набор при первой настройке
  структуры) — каждое диспатчится отдельным `FarmsPageEventAddPlace` и
  обрабатывается независимо; при проглоченном исключении на одном из них
  остальные вставляются как обычно, никакой агрегации ошибок или отката
  нет, и по состоянию блока невозможно определить, какое именно место не
  сохранилось.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — целевая сущность
  попытки создания. В основном потоке строка не создаётся вовсе; в
  альтернативном потоке («падает второй шаг») строка создаётся, но с
  `idRemote == null`, невидимая для дальнейшей синхронизации.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — только читается:
  `farmId` (сервер-id фермы), переданный в `PlaceCreatePageArguments`,
  используется как есть; этим сценарием не создаётся и не изменяется.

### Бизнес-правила

- `FarmsAndPlacesBloc._onAddPlace` синтаксически «обрабатывает» ошибку
  (`try/catch` → `FarmsPageError`), но эта ветвь недостижима для реального
  исключения `PlacesDao`, потому что `PlaceRepository.insertPlaceWithNegativeRemoteId`
  перехватывает исключение уровнем ниже и никогда не пробрасывает его
  дальше — та же схема (репозиторий глотает исключение, вызывающий код
  считает вызов успешным) уже встречалась при создании фермы; это не новая
  находка для модуля, а повторяющийся паттерн всех `insert*WithNegativeRemoteId`.
- `context.pop()` в `_PlacesList.build` не дожидается результата ни одного
  из диспатченных событий — переход на предыдущий экран происходит
  мгновенно, независимо от исхода вставки.
- Ни один виджет во всём `lib/` не подписан на `FarmsPageState` блока
  `FarmsAndPlacesBloc` — эмитированный `FarmsPageError` не приводит ни к
  какому визуальному эффекту, даже если бы код внутри `_onAddPlace`
  действительно его достиг.
- Экран со списком мест фермы обновляется независимо от
  `FarmsAndPlacesBloc` — через собственную подписку `MainNavigatorCubit` на
  `PlaceRepository.watchAll()`; при проглоченном исключении вставки строка
  не появляется в БД, стрим не эмитит новое значение, и место просто
  отсутствует в списке без какого-либо сообщения об ошибке.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — все факты по этому сценарию проверены чтением
`lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`,
`lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart`,
`lib/pages/farms_and_places/farms_page_bloc.dart`,
`lib/repositories/place_repository/place_repository.dart`,
`packages/sheep_farm_database/lib/entities/place/places_dao.dart`,
`packages/sheep_farm_database/lib/entities/place/places.dart` и
`lib/pages/main_navigator/cubit/main_navigator_cubit.dart`, плюс `grep` по
всему `lib/` на предмет потребителей `FarmsPageState`.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `_PlacesList.build` | CURRENT | кнопка «Сохранить структуру»: диспатчит `FarmsPageEventAddPlace` на каждое новое место, затем безусловный `context.pop()` без ожидания результата |
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.getPlacesToSave` | CURRENT | фильтрует места с пустым именем перед диспатчем; сам не выполняет запись в БД |
| `lib/pages/farms_and_places/farms_page_event.dart` | `FarmsPageEventAddPlace` | CURRENT | событие блока, несущее создаваемый `Place` |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onAddPlace` | CURRENT | вызывает `PlaceRepository.insertPlaceWithNegativeRemoteId` внутри `try/catch`, эмитящего `FarmsPageError`; ветвь `catch` недостижима для исключения, проглатываемого уровнем ниже |
| `lib/pages/farms_and_places/farms_page_state.dart` | `FarmsPageError` | CURRENT | состояние-носитель сообщения об ошибке; не имеет ни одного потребителя в UI |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.insertPlaceWithNegativeRemoteId` | CURRENT | собственный `try/catch` перехватывает исключение из обоих шагов DAO и не пробрасывает его дальше |
| `packages/sheep_farm_database/lib/entities/place/places_dao.dart` | `PlacesDao.insertPlaceReturning`, `PlacesDao.setPlaceNegativeRemoteId` | CURRENT | два шага локальной записи; второй вызывается без `await` |
| `packages/sheep_farm_database/lib/entities/place/places.dart` | `Places`, `Place` | CURRENT | таблица/модель; `farmId` не несёт реального FK-ограничения на уровне схемы |
| `lib/pages/main_navigator/cubit/main_navigator_cubit.dart` | подписка на `PlaceRepository.watchAll()` | CURRENT | независимый от `FarmsAndPlacesBloc` источник обновления видимого пользователю списка мест |

## Критерии приёмки

- При исключении внутри `dao.insertPlaceReturning` строка `Place` не
  создаётся, и никакая ошибка нигде не отображается пользователю —
  `FarmsAndPlacesBloc._onAddPlace` безусловно вызывает
  `add(FarmsPageEventLoadFarms())`, как при успехе.
- `PlaceRepository.insertPlaceWithNegativeRemoteId` в этом случае
  завершается без исключения (`Future<void>` не отклоняется) — вызывающий
  код не получает никакого сигнала отказа.
- `catch (e) { emit(FarmsPageError(...)); }` внутри `_onAddPlace`
  эмитирует ошибку только тогда, когда сам вызов
  `insertPlaceWithNegativeRemoteId` пробрасывает исключение (сегодня
  недостижимо при реальной реализации репозитория) — эта ветвь
  подтверждена только тестом с моком на уровне интерфейса репозитория.
- Независимо от того, эмитирована ли `FarmsPageError`, ни один экран
  приложения не показывает пользователю никакого сообщения об ошибке
  создания места — ни через слушатель `FarmsAndPlacesBloc` (его нет), ни
  через уже закрытый к этому моменту экран мастера (`context.pop()`
  выполняется до завершения асинхронной вставки).
- Если падает именно второй шаг (`setPlaceNegativeRemoteId`, не
  дожидаемый), в локальной БД остаётся строка `Place` с `idRemote == null`,
  не попадающая под `PlaceRepository.getAllWithoutRemoteId()` и потому
  никогда не синхронизируемая.

## Связанные тесты

`test/pages/farms_and_places_bloc_test.dart`, group `'UC-8 —
FarmsAndPlacesBloc._onAddPlace ERROR'` (будет переименовано, не трогать
сейчас), test `'insertPlaceWithNegativeRemoteId бросает -> FarmsPageError("Ошибка
создания места: ...")'` — покрывает только гипотетический путь из
«Альтернативные потоки»: мок `PlaceRepository.insertPlaceWithNegativeRemoteId`
подставлен с `thenThrow` на уровне интерфейса, минуя реальный внутренний
swallow метода.

TBD — теста нет на уровне `PlaceRepository`/`PlacesDao` против реальной
(in-memory) БД, который воспроизвёл бы настоящее исключение
`dao.insertPlaceReturning` и подтвердил бы, что оно проглатывается и не
долетает до `FarmsAndPlacesBloc._onAddPlace`.

TBD — теста нет на сценарий «падает второй шаг» (`setPlaceNegativeRemoteId`
не дожидается и роняется асинхронно) и на осиротевшую строку с
`idRemote == null`.

TBD — теста нет на факт отсутствия слушателя `FarmsPageState`/
`FarmsPageError` в UI — сейчас проверено только чтением кода (`grep` по
`lib/`), не тестом.

## Открытые вопросы и ограничения

- **Двухуровневое проглатывание исключения делает основной сценарий
  CREATE_ERROR полностью ненаблюдаемым.** `PlaceRepository.insertPlaceWithNegativeRemoteId`
  перехватывает исключение из `dao.insertPlaceReturning`/
  `dao.setPlaceNegativeRemoteId` и только логирует его, никогда не
  пробрасывая и не возвращая признак отказа (`Future<void>`). Из-за этого
  внешний `try/catch` в `FarmsAndPlacesBloc._onAddPlace`, эмитящий
  `FarmsPageError`, не может сработать на ошибке именно этого вызова —
  реальный сбой создания отделения неотличим от успеха ни на уровне
  репозитория, ни на уровне блока.
- **Существующий тест группы `'UC-8'` создаёт ложное чувство покрытия.**
  Он проверяет обработчик `_onAddPlace` в изоляции через мок на уровне
  интерфейса репозитория, а не реальную цепочку `PlacesDao` →
  `PlaceRepository` → `FarmsAndPlacesBloc`, которая сегодня гарантированно
  не пробрасывает исключение так далеко.
- **`FarmsPageError`, даже будучи эмитированной, не имеет ни одного
  потребителя.** Во всём `lib/` нет ни одного
  `BlocBuilder`/`BlocListener`/`BlocConsumer<FarmsAndPlacesBloc,
  FarmsPageState>` — только регистрация `BlocProvider<FarmsAndPlacesBloc>`
  в `lib/main.dart` и диспатч событий из `place_create_page.dart`. Эта
  ветвь мертва дважды: недостижима изнутри репозитория и не была бы увидена
  снаружи блока, даже если бы её достигла.
- **`context.pop()` не дожидается результата.** По построению экрана
  пользователь физически не может увидеть реакцию на эту (или любую
  другую) ошибку создания места, поскольку экран, на котором она могла бы
  отобразиться, уже закрыт к моменту завершения асинхронного вызова
  репозитория.
- Если падает именно второй шаг (`setPlaceNegativeRemoteId`), осиротевшая
  строка `Place` с `idRemote == null` навсегда выпадает из
  `PlaceRepository.getAllWithoutRemoteId()` и, соответственно, из любого
  будущего sync-прохода — не специфицировано отдельным use-case, так как
  дальнейшая отправка на сервер ([EVT-18](../events/EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md))
  такую строку вообще не увидит.
