- **derived from**: [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)

# UC-35 — Пользователь пытается удалить отделение, на котором остались закреплённые животные: удаление отклонено (REJECTED)

## Назначение

Пользователь в мастере настройки структуры фермы нажимает удаление
(корзину) на уже существующем отделении (`Place`, у которого назначен
`idRemote`). Перед любым изменением данных клиент проверяет, не осталось ли
на этом месте закреплённых (не выбывших) животных. Если хотя бы одно есть —
бизнес-правило осознанно отклоняет удаление: место остаётся в списке
без изменений, пользователю показывается сообщение об ошибке (ключ
`move_all_animals_to_delete`), ни локальная БД, ни сервер не затрагиваются.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь;
имя актора наследуется от id события [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
в имени файла. Мастер настройки структуры фермы (`PlaceCreatePage`), где
происходит этот сценарий, не проверяет авторизацию сам по себе, но
единственные найденные в коде точки входа на этот экран (см. «Основной
поток», шаг 1) доступны только из экранов, уже требующих существующей
фермы — гостевого пути к этому экрану не найдено.

## CURRENT

### Основной поток

1. Пользователь открывает мастер настройки структуры фермы
   (`PlaceCreatePage`, `Routes.createPlace`) с непустым `existingPlaces` —
   найдены два таких входа: пункт меню «Структура фермы»
   (`FarmMoreMenuButton`, `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart`)
   и тап по пустому описанию площади на экране отдельного места
   (`lib/pages/place/place_page.dart`). Оба передают
   `PlaceCreatePageArguments(farmId: farm.farm.remoteId!, existingPlaces:
   farm.placesWithAnimals.map((p) => p.place).toList())` — то есть реальные,
   уже существующие в БД места фермы, у части которых может быть назначен
   `idRemote` (положительный — уже синхронизированный с сервером, либо
   отрицательный — локально созданный, ещё не отправленный, но уже
   получивший локальный «серверный» id по конвенции
   `PlaceRepository.insertPlaceWithNegativeRemoteId`).
2. `PlaceCreatePage.build` создаёт `BlocProvider<PlaceCreateCubit>` с этими
   `existingPlaces`; так как список не пуст, `PlaceCreateCubit._initializePlaces`
   не подставляет стандартный набор мест (общее стадо и т.д.) —
   `state.places` равен переданным `existingPlaces` как есть.
3. Пользователь видит список отделений (`_PlacesList` →
   `ListView.separated` по `state.places`) и нажимает иконку корзины
   (`Icons.delete_forever`) у конкретного отделения — `_PlaceItem`
   (`onTap: () => cubit.removePlace(widget.index)`,
   `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`).
4. `PlaceCreateCubit.removePlace(index)`
   (`lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart`)
   первым делом сбрасывает предыдущую ошибку:
   `emit(state.copyWith(errorMessage: null))` — не мутация домена, только
   UI-состояние.
5. `placeToRemove = updatedPlaces[index]`. Так как `placeToRemove.idRemote != null`
   (условие сценария), метод вызывает
   `_animalsRepository.getAllAnimalsWithDetailsByFilters(placeIds:
   [placeToRemove.idRemote ?? placeToRemove.id!])` — фактически всегда
   `placeIds: [placeToRemove.idRemote]`, так как `idRemote` уже проверен
   ненулевым; `??` на `placeToRemove.id!` в этой ветке недостижим.
6. `AnimalsRepository.getAllAnimalsWithDetailsByFilters` делегирует в
   `AnimalsDao.getAllAnimalsWithDetailsByFilters`
   (`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart`),
   которая строит запрос с join'ом `Places` по
   `placeAlias.idRemote.equalsExp(aAlias.placeId)` и фильтрует
   `aAlias.placeId.isIn(placeIds)`; по умолчанию `isNotDeleted: true` и
   `isDisposal: false`, поэтому дополнительно накладывается
   `aAlias.deletedAt.isNull()` — считаются только ещё не выбывшие животные.
7. Запрос возвращает непустой список — на месте есть хотя бы одно не
   выбывшее животное с `Animal.placeId == placeToRemove.idRemote`.
8. `removePlace` эмитит `state.copyWith(errorMessage:
   'move_all_animals_to_delete')` и немедленно `return` — до этой точки
   `updatedPlaces`/`state.places`/`state.deletedPlaces` не менялись; после
   `return` они тоже не меняются. Ни `PlaceRepository`, ни
   `FarmsAndPlacesBloc`, ни какой-либо сетевой вызов в этой ветке не
   задействуются вообще.
9. `_PlacesList`'s `BlocConsumer<PlaceCreateCubit, PlaceCreateState>`
   (`listener`, `listenWhen: previous.errorMessage != current.errorMessage`)
   реагирует на изменение `errorMessage` и вызывает
   `showAppSnackBarError(context, context.tr(state.errorMessage!))`
   (`lib/widgets/app_snackbar.dart`,
   `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart`).
   `context.tr` резолвит динамический ключ через ручной маппинг
   `AppLocalization` (`lib/l10n/app_localization.dart`, `case
   'move_all_animals_to_delete': return move_all_animals_to_delete;`) —
   локализованный текст (`lib/l10n/app_ru.arb`: «Для удаления переместите
   всех животных») показывается красным snackbar'ом
   (`showAppSnackBarError`).
10. `_PlacesList.builder` перестраивается тем же неизменным
    `state.places` — отделение остаётся в списке на том же месте, доступным
    для повторной попытки удаления (например, после того как пользователь
    перенесёт животных в другое место через отдельный сценарий перемещения,
    вне рамок этого use-case).

### Альтернативные потоки

- **`placeToRemove.idRemote == null`** (место создано в этой же сессии
  мастера и ещё ни разу не сохранялось) — проверка животных вообще не
  выполняется (условие `if (placeToRemove.idRemote != null)` ложно),
  удаление происходит безусловно. Это не входит в этот сценарий (нет
  проверки → не может быть REJECTED по этой причине), но выполняется тем же
  методом — покрыто отдельным тестом (см. «Связанные тесты»).
- **`idRemote != null`, но животных на месте нет** — `getAllAnimalsWithDetailsByFilters`
  возвращает пустой список, `removePlace` не эмитит ошибку, удаляет место из
  `state.places` и добавляет его в `state.deletedPlaces` (с `idRemote` как
  есть, если он положителен, либо принудительно обнулённым, если он
  отрицателен). Соседний OK-исход того же метода, не документируется в этом
  use-case.
- **Что происходит с местом дальше, если удаление НЕ было отклонено.**
  `deletedPlaces` физически ни во что не превращается, пока пользователь не
  нажмёт «Сохранить структуру» (`BlackCircleButton`,
  `_PlacesList.builder`) — тогда для каждого элемента
  `cubit.getPlacesToDelete()` диспетчится
  `context.read<FarmsAndPlacesBloc>().add(FarmsPageEventDeletePlace(place))`.
  `FarmsAndPlacesBloc._onDeletePlace`
  (`lib/pages/farms_and_places/farms_page_bloc.dart`) **не выполняет
  собственную проверку животных** — он безусловно либо мягко удаляет
  (`isDeleted: true` через `_placeRepository.update`, когда `idRemote !=
  null`), либо физически удаляет строку (`_placeRepository.delete`, когда
  `idRemote == null`) то место, которое уже прошло проверку в
  `PlaceCreateCubit.removePlace`. Это не альтернативный путь к REJECTED —
  этот обработчик не может произвести REJECTED-исход сам по себе, он лишь
  исполняет решение, уже принятое кубитом.
- **Повторно достижимый REJECTED для локально созданного, ещё не
  синхронизированного места.** Место, впервые созданное и сохранённое через
  этот же мастер, получает отрицательный `idRemote` через
  `PlaceRepository.insertPlaceWithNegativeRemoteId`
  (`lib/repositories/place_repository/place_repository.dart`) в момент
  обработки `FarmsPageEventAddPlace`. Если после этого пользователю в этом
  месте закрепляют животное (вне рамок этого use-case — сценарий модуля
  ANIMAL/REG, ещё не специфицированного) и пользователь снова открывает
  мастер структуры фермы и пробует удалить это же место — проверка на шаге
  5 сработает и для отрицательного `idRemote` точно так же, как для
  положительного; отдельно покрыто тестом с `idRemote: -5` (см. «Связанные
  тесты»), хотя тот конкретный тест проверяет ветку без животных, а не
  REJECTED.

### Связанные сущности

- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place) — ENT-сегмент имени
  файла; сущность, чьё удаление отклоняется. Ни одно поле строки `Place` не
  меняется в этом сценарии — ни в памяти кубита (`state.places` остаётся
  прежним), ни в БД.
- Animal — сущность модуля ANIMAL/REG (ещё не специфицирован отдельным
  `ENT-*` в этом дереве, см. границу [MOD-3](../modules/MOD-3-FARM.md), «что
  модуль explicitly не владеет») — сценарий только читает строки `Animal` по
  `placeId`/`deletedAt`, ничего в них не пишет; именно наличие таких строк —
  единственное условие, отличающее REJECTED от соседнего OK-исхода.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm) — не читается и не
  пишется этим сценарием напрямую; упоминается только как контекст входа
  (оба найденных входа в мастер передают `farmId: farm.farm.remoteId!`).

### Бизнес-правила

- Удаление отделения отклоняется тогда и только тогда, когда одновременно:
  (а) у отделения уже назначен какой-либо `idRemote` (не важно, положительный
  синхронизированный или отрицательный локальный) и (б) хотя бы одно
  животное с `Animal.placeId == idRemote` ещё не выбыло
  (`Animal.deletedAt == null`).
- Отклонение происходит строго до какого-либо изменения данных: ни
  `state.places`/`state.deletedPlaces` кубита, ни строка `Place` в БД, ни
  сервер не затрагиваются — единственный эффект REJECTED-ветки —
  `state.errorMessage`.
- Отклонение не является ошибкой сохранения (нет исключения, нет catch) — это
  осознанная бизнес-проверка перед попыткой изменения данных, что и
  квалифицирует исход как `REJECTED`, а не `ERROR`.
- Сообщение об отклонении — фиксированный ключ локализации
  `move_all_animals_to_delete`, не зависящий от количества или атрибутов
  найденных животных.
- Повторная попытка удаления того же места после отклонения не имеет
  дополнительных ограничений (нет счётчика попыток, нет блокировки UI) —
  пользователь может нажимать удаление сколько угодно раз, пока на месте
  остаются животные.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Не выявлено — сценарий полностью прослеживается в существующем коде и
покрыт тестом на уровне кубита.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart` | `PlaceCreateCubit.removePlace` | CURRENT | проверяет наличие животных на месте (когда `idRemote != null`), эмитит `errorMessage` и прерывает выполнение при найденных животных |
| `lib/pages/farms_and_places/sub_pages/places/place_create_state.dart` | `PlaceCreateState.errorMessage` | CURRENT | поле состояния, несущее ключ отклонения |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.getAllAnimalsWithDetailsByFilters` | CURRENT | точка входа запроса животных по `placeIds` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAllAnimalsWithDetailsByFilters` | CURRENT | реальный SQL-запрос: `placeId.isIn(placeIds)` + `deletedAt.isNull()` по умолчанию (`isNotDeleted: true`) |
| `lib/pages/farms_and_places/sub_pages/places/place_create_page.dart` | `_PlaceItem` (иконка `Icons.delete_forever`), `_PlacesList` (`BlocConsumer` listener) | CURRENT | UI-вход (тап на удаление) и рендер сообщения об отклонении красным snackbar'ом |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` | CURRENT | отображает сообщение об отклонении |
| `lib/l10n/app_localization.dart` | `AppLocalization` (`case 'move_all_animals_to_delete'`) | CURRENT | маппинг динамического ключа ошибки на локализованную строку |
| `lib/l10n/app_ru.arb` | `move_all_animals_to_delete` | CURRENT | локализованный текст («Для удаления переместите всех животных») |
| `lib/pages/main_navigator/presentation/widgets/farm_actions_widget.dart` | `FarmMoreMenuButton` (пункт «Структура фермы») | CURRENT | вход №1 в мастер с реальными существующими местами (`farm.placesWithAnimals`) |
| `lib/pages/place/place_page.dart` | обработчик тапа по пустому описанию площади | CURRENT | вход №2 в тот же мастер, тоже с реальными существующими местами |
| `lib/pages/farms_and_places/sub_pages/farms_create/farm_create_page.dart` | `FarmCreatePage._onSuccess` | CURRENT | вход №3, но всегда с `existingPlaces: []` — этим входом REJECTED в первый же проход мастера недостижим |
| `lib/pages/farms_and_places/farms_page_bloc.dart` | `FarmsAndPlacesBloc._onDeletePlace` | CURRENT | downstream-обработчик уже отфильтрованных мест; собственной проверки животных не делает, REJECTED сам произвести не может |
| `lib/repositories/place_repository/place_repository.dart` | `PlaceRepository.insertPlaceWithNegativeRemoteId` | CURRENT | назначает отрицательный `idRemote` локально созданному месту — источник кейса «отрицательный `idRemote`, но проверка животных всё равно выполняется» |

## Критерии приёмки

- При `placeToRemove.idRemote != null` и непустом результате
  `AnimalsRepository.getAllAnimalsWithDetailsByFilters(placeIds:
  [placeToRemove.idRemote])` вызов `PlaceCreateCubit.removePlace(index)`
  оставляет `state.places` без изменений (то же место на том же индексе) и
  `state.deletedPlaces` без изменений.
- В этом случае `state.errorMessage` становится равным ровно
  `'move_all_animals_to_delete'`.
- Ни один метод `PlaceRepository`, ни `FarmsAndPlacesBloc.add(...)` не
  вызываются как следствие отклонённого вызова `removePlace`.
- Отклонение срабатывает одинаково независимо от знака `idRemote`
  (положительный синхронизированный либо отрицательный локальный) — важно
  только, что он не `null`.
- UI показывает ровно одно сообщение об ошибке (красный snackbar) через
  `showAppSnackBarError` с локализованным текстом ключа
  `move_all_animals_to_delete` при каждом изменении `errorMessage`.

## Связанные тесты

- `test/pages/place_create_cubit_test.dart`, group
  `'PlaceCreateCubit.removePlace'` (будет переименовано, не трогать сейчас),
  test `'idRemote задан, есть привязанные животные -> errorMessage, место не
  удаляется'` — прямое покрытие «Основного потока»: мок
  `animalsRepository.getAllAnimalsWithDetailsByFilters(placeIds: [30])`
  возвращает непустой список (`AnimalWithDetails`), после
  `cubit.removePlace(0)` тест проверяет `cubit.state.places` (`hasLength(1)`)
  и `cubit.state.errorMessage == 'move_all_animals_to_delete'`.
- `test/pages/place_create_cubit_test.dart`, тот же group, test
  `'idRemote:null (ещё не отправлено на сервер) -> удаляется без проверки
  животных'` — покрывает соседний путь без проверки («Альтернативные
  потоки», первый пункт), не сам REJECTED.
- `test/pages/place_create_cubit_test.dart`, тот же group, test `'idRemote
  задан, животных нет -> удаляется, попадает в deletedPlaces'` — соседний
  OK-исход того же метода.
- `test/pages/place_create_cubit_test.dart`, тот же group, test `'idRemote
  отрицательный (локальное, не отправленное) -> deletedPlaces получает
  idRemote:null'` — подтверждает, что отрицательный `idRemote` проходит ту
  же проверку `getAllAnimalsWithDetailsByFilters`, но не для случая с
  животными (в этом тесте список животных пуст) — прямого теста на
  REJECTED именно с отрицательным `idRemote` нет.
- **TBD — теста нет** на `FarmsAndPlacesBloc._onDeletePlace`,
  подтверждающего, что этот обработчик не выполняет собственную проверку
  животных (см. «Альтернативные потоки») — существующие тесты
  `test/pages/farms_and_places_bloc_test.dart` (группы старой нумерации
  UC-1..UC-12) для `_onDeletePlace` не были прочитаны отдельно в рамках
  этого прохода и не проверялись специально на этот факт.

## Открытые вопросы и ограничения

- **Расхождение с путём к файлу в [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  — не исправляется в рамках этого прохода.** Файл события ссылается на
  `lib/pages/farms_and_places/sub_pages/farms_create/place_create_cubit.dart`
  — такого пути в репозитории не существует; реальный файл —
  `lib/pages/farms_and_places/sub_pages/places/place_create_cubit.dart`
  (подтверждено поиском по всему `lib/` — других файлов с именем
  `place_create_cubit.dart` нет). [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  — уже существующий, замороженный артефакт; расхождение фиксируется здесь,
  а не правится в нём.
- **Расхождение с описанием второго триггера в [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md)
  — тоже не исправляется здесь.** Файл события описывает удаление отделения
  как достижимое «из мастера настройки структуры... либо с экрана фермы;
  `FarmsAndPlacesBloc.on<FarmsPageEventDeletePlace>`», формулировка которого
  можно прочитать как два независимых пути принятия решения об удалении.
  При чтении кода `FarmsPageEventDeletePlace` диспетчится из ровно одного
  места во всём `lib/` — кнопки «Сохранить структуру» в том же самом
  мастере (`place_create_page.dart`), и только для мест, уже прошедших
  проверку в `PlaceCreateCubit.removePlace`. `_onDeletePlace` сам не
  содержит проверки животных и не может произвести REJECTED-исход — это
  исполнитель уже принятого решения, а не отдельный источник этого
  сценария.
- Реальная UI-достижимость сценария «отрицательный `idRemote` + есть
  животные» (место создано локально, ещё не синхронизировано, но уже имеет
  закреплённое животное) прослежена по коду (`PlaceRepository.insertPlaceWithNegativeRemoteId`
  назначает отрицательный `idRemote` сразу при сохранении структуры), но не
  подтверждена сквозным/widget-тестом — только по отдельности проверенными
  юнит-тестами кубита и репозитория.
