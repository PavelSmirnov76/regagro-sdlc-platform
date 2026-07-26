- **task**: [`../4-tasks/SHEEP-5-1-DISPOSAL-BETWEEN-FARMS-DESTINATION.md`](../4-tasks/SHEEP-5-1-DISPOSAL-BETWEEN-FARMS-DESTINATION.md) (`UC-319`)

# Реализовано

- **DB-миграция**: новая колонка `Disposals.toPlaceId` (`to_place_id`),
  `schemaVersion` 95 → 96, блок `if (from < 96)` в
  `packages/sheep_farm_database/lib/database/database.dart`.
- **`AnimalDisposalBloc`**: убрано исключение `.where((e) => e.id != 4)` при
  загрузке причин в `on<AnimalDisposalEventStart>` — причина `id == 4` теперь
  доступна для выбора. Тот же обработчик подтягивает `targetFarms` — все
  локально известные фермы владельца (`FarmRepository.getAll()`), кроме
  фермы-источника.
- Новые события/обработчики: `AnimalDisposalEventSelectTargetFarm` (грузит
  места выбранной целевой фермы через уже существующий
  `PlaceRepository.getAllWithThisFarmIdWithAnimals`, сбрасывает ранее
  выбранное целевое место) и `AnimalDisposalEventChangeTargetPlace`.
  `AnimalDisposalEventSelectReason` дополнительно сбрасывает целевые
  ферму/место при смене причины (флаги `clearSelectedTargetFarm`/
  `clearSelectedTargetPlace` в `copyWith`, т.к. существующий паттерн `??` в
  этом файле не умеет явно затирать в `null`).
- `AnimalDisposalData.currentSteps` — шаги `selectTargetFarm`/
  `selectTargetPlace` вставляются между `reason` и `animals`, только когда
  `isBetweenFarmsReason` (`selectedReason?.id == 4`, вынесено в именованный
  геттер/константу `betweenFarmsReasonId`, вместо голого литерала).
- **UI**: новый `SelectTargetFarmStepPage` (`lib/pages/animal_disposal/steps/`)
  — `RDropDownButton.outline` по фермам; шаг целевого места переиспользует
  существующий `SelectPlaceStepPage` один в один (тот же компонент, что и шаг
  места-источника), как и просил постановщик. `animal_disposal_page.dart` —
  новые кейсы в `_createStepWidget`, заголовки в `_TabBar._getTitles` (новый
  l10n-ключ `select_target_farm` для шага фермы; шаг места переиспользует
  существующий `select_place`).
- **`DisposalRepository.sendDisposalList`** — новое поле запроса `to_place_id`
  (заполняется из `toPlaceId` группы, `null` для остальных причин). Изначально
  было отправлено как `place_id` по буквальной формулировке постановщика;
  реальный бэк (422-ответ с текстом «Поле Отделение назначения обязательно
  для заполнения, когда присутствует Объект назначения», ключ ошибки
  `to_place_id`) подтвердил, что имя поля — `to_place_id`, исправлено по
  факту первого реального прогона.
  `_groupForSend`/`_DisposalSendGroup` учитывают `toPlaceId` в ключе
  группировки, чтобы записи с разным местом назначения не сливались в один
  запрос.
- **`on<AnimalDisposalEventSave>`** — для причины `id == 4` заполняет
  `toId`/`toPlaceId` из выбранных целевых фермы/места; для остальных причин —
  `null`, как и раньше. `fromId`/`toId` — `remoteId` ферм, не `id`/`idRemote`
  мест.
- **l10n**: новый ключ `select_target_farm` добавлен во все 9 `.arb`-файлов
  (`en`/`ru`/`es`/`fr`/`kk`/`pt`/`uz`/`vi`/`zh`), `flutter gen-l10n` прогнан.

## Проверено

- `dart run build_runner build --workspace --delete-conflicting-outputs` —
  без ошибок (drift-схема, `AnimalDisposalPageArguments` freezed-зависимости
  затронуты не были — сам bloc/data на Equatable, не freezed, как и весь
  остальной этот легаси-файл, см. решение ниже).
- `flutter analyze` — без замечаний по изменённым файлам и по всему проекту.
- `dart format` — применён, ожидаемые изменения переноса строк.
- **Тесты** (`test/pages/animal_disposal_bloc_test.dart`):
  - обновлён существующий тест `id 4 отфильтрован` → `id 4 больше не
    отфильтровывается` (`disposalReasons ids`, ожидание `[1, 4]`);
  - новая группа `UC-319 — AnimalDisposalEventSelectTargetFarm /
    ChangeTargetPlace` — загрузка мест выбранной фермы, сброс места при смене
    фермы, сброс целевых фермы/места при смене причины;
  - новая группа `AnimalDisposalData.currentSteps — причина «между фермами
    владельца»` — шаги вставляются/не вставляются в зависимости от причины;
  - новая группа `UC-319 — AnimalDisposalEventSave (причина «между фермами
    владельца»)` — `toId`/`toPlaceId` заполняются только для причины `id ==
    4`.
  - По ходу отладки новых тестов обнаружена и исправлена **гонка в самих
    тестах** (не в проде): синхронный `act`, добавляющий несколько событий
    подряд без ожидания, гонится с асинхронным `on<AnimalDisposalEventStart>`/
    `on<AnimalDisposalEventSelectTargetFarm>` — если асинхронный обработчик
    завершается позже синхронных, его безусловный `copyWith` (например
    `selectedAnimalIds: const []` в `EventStart` для не-`isSingle` случая)
    затирает уже установленные синхронными событиями поля. В проде
    недостижимо (UI не даёт взаимодействовать с шагами, пока `EventStart` не
    завершится), но добавление второго `await` в `EventStart` изменило тайминг
    ровно настолько, чтобы обнажить это в одном из существующих тестов
    (`fromId сохранённого Disposal...`). Починено на стороне тестов —
    `await pumpEventQueue()` между зависимыми событиями, не изменением
    прод-кода.
- `flutter test` — полный прогон (`1259` тестов) — зелёный.

## Отложено / не сделано

- Валидация «нельзя продолжить без выбранной целевой фермы/места» на уровне
  визарда — как и остальные шаги этого визарда, можно пропустить свайпом
  вкладок (см. `UC-319`, «TBD / BLOCKED»); не в объёме этой задачи.
- `DisposalReasonHelper` остаётся мёртвым кодом (уже так до этой задачи,
  `ENT-27` фиксирует факт) — не подключался и не удалялся.
- Миграция `AnimalDisposalBloc` на freezed `*Data`/`*State` — не выполнена: это
  существующий легаси-файл, использующий тот же `Equatable`-паттерн, что и
  соседний `AnimalMovementBloc` (не filters-семейство); полная архитектурная
  миграция вне объёма запрошенной фичи и не была запрошена пользователем.
