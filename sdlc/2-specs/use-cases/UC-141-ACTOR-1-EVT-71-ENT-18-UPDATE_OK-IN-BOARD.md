# UC-141 — Пользователь переключает избранное на карточке объявления: сервер подтверждает, но сердечко (и state) не обновляются

| | |
|---|---|
| Актор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Событие | [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md) |
| Сущность | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| Результат | `UPDATE_OK` |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |

## Назначение

Пользователь тапает по сердечку на карточке объявления — единственный
реально подключённый в UI путь к [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md),
доступный сразу на трёх экранах, которые делят один и тот же `BoardCubit`:
общая лента (`BoardView`), «Мои объявления» (`MyAdsView`, `isMyAds: true`) и
«Избранное» (`FavouriteAdsView`, `isFavouriteAds: true`). Тап вызывает
`BoardCubit.toggleAdFavourite` → `AdRepository.setAdFavourite` →
`POST /selected-ads` (добавить) либо `DELETE /selected-ads/{id}` (убрать).
Сервер подтверждает переключение без ошибки — это `UPDATE_OK` с точки зрения
сети. Но локально, на двух экранах из трёх (общая лента и «Мои объявления»),
переключение **не видно вообще нигде** — ни в UI, ни даже во внутреннем
`state` самого `BoardCubit` — из-за неполного `Ad.props` (`Equatable`,
[ENT-18](../entities/ENT-18-AD-IN-BOARD.md)): `isFavourite` не входит в
список полей, участвующих в сравнении, поэтому переключённый и исходный
`Ad` считаются равными, `BoardState` (`@freezed`) — тоже равным, и
`Cubit.emit()` (пакет `bloc`) молча пропускает обновление целиком. Третий
экран, «Избранное», — исключение: там переключение убирает карточку из
списка целиком, а изменение *длины* списка не нуждается в поэлементном
сравнении через `Equatable`, поэтому там `UPDATE_OK` наблюдаем в полном
объёме. Контрастный, технически корректный путь существует —
`AdDetailCubit.toggleAdFavourite` использует `BoardAdDetailModel` (`@freezed`,
без этого дефекта), — но кнопка, которая должна его вызывать на детальной
карточке объявления, закомментирована в UI и недостижима ни при каких
действиях пользователя.

## Пользователь

[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) — авторизованный пользователь.
Ни `BoardCubit.toggleAdFavourite`, ни `AdRepository.setAdFavourite`,
ни `addAdToFavouritesFromApi`/`removeAdFromFavouritesFromApi` не вызывают
`AuthRepository.isAuthorized()` и не проверяют состояние сессии — на уровне
этого кода действие ничем не гейтится локально. Привязка сценария именно к
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), а не к
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) (гость=авторизован для
чтения), уже зафиксирована выше по дереву специфицирования — в
[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) («избранное» явно перечислено
как одна из мутаций этого актора в BOARD) и в
[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) («BOARD требует реальной
авторизации для этих действий, гость=авторизован работает только для
чтения»); фактическое обеспечение этого требования (если оно есть) —
целиком на уровне сети (токен, прикладываемый `AuthInterceptor` для клиента
`farm_rpc`, либо отказ на сервере), не проверяется локально в файлах,
рассматриваемых этим сценарием.

## CURRENT

### Основной поток

1. Пользователь находится на одном из трёх экранов, использующих один и тот
   же `BoardCubit` (`lib/pages/board/cubit/board_cubit.dart`): общая лента
   (`lib/pages/board/presentation/widgets/board_view.dart` —
   `BoardCubit()..load(page: 1)`), «Мои объявления»
   (`lib/pages/my_ads/presentation/my_ads_view.dart` —
   `BoardCubit()..load(page: 1, isMyAds: true)`) или «Избранное»
   (`lib/pages/favourite_ads/presentation/favourite_ads_view.dart` —
   `BoardCubit()..load(page: 1, isFavouriteAds: true)`, единственный из
   трёх, где `state.isOnlyFavouriteAds == true`). Все три рендерят сетку
   карточек через общий `BoardPopulated`
   (`lib/pages/board/presentation/widgets/board_populated.dart`).
2. Карточка каждого объявления показывает `InkWell` с иконкой
   `Icons.favorite`/`Icons.favorite_border` (в зависимости от `ad.isFavourite`)
   поверх коллажа фото; по тапу — `context.read<BoardCubit>().toggleAdFavourite(ad.id)`.
3. `BoardCubit.toggleAdFavourite(id)`:
   - вычисляет направление переключения:
     `!state.ads.any((ad) => ad.id == id && ad.isFavourite)` — «сделать
     избранным», если ни один элемент текущего списка с этим `id` сейчас не
     помечен избранным;
   - `await _adRepository.setAdFavourite(id, nextValue)`.
4. `AdRepository.setAdFavourite(id, isFavourite)`
   (`lib/repositories/board/ad_repository.dart`) — тернарный диспетчер:
   `isFavourite == true` → `addAdToFavouritesFromApi(id)` (`POST
   ${Constants.boardServiceApi}/selected-ads`, тело `{'ad_id': id}`);
   `isFavourite == false` → `removeAdFromFavouritesFromApi(id)` (`DELETE
   ${Constants.boardServiceApi}/selected-ads/{id}`). Оба метода читают
   `response['status']`: `"1"` — возврат без исключения (этот сценарий);
   иначе — `throw Exception(response['message'])` (ветка `ERROR`, за
   границами этого файла).
5. Оба сетевых вызова в этом сценарии завершаются успешно, без исключения —
   `await` в шаге 3 продолжается сразу после.
6. `toggleAdFavourite` ветвится по `state.isOnlyFavouriteAds`:
   - **`false`** (общая лента, «Мои объявления»): `emit(state.copyWith(ads:
     state.ads.map((ad) => ad.id == id ? ad.copyWith(isFavourite:
     !ad.isFavourite) : ad).toList()))` — строит новый список, где элемент с
     этим `id` заменён копией с инвертированным `isFavourite`, остальные —
     те же ссылки;
   - **`true`** (экран «Избранное»): `emit(state.copyWith(ads:
     state.ads.where((ad) => ad.id != id).toList()))` — убирает элемент из
     списка целиком (см. отдельную ветку ниже).
7. **Дефект — ветка `isOnlyFavouriteAds == false`.** `Ad.props`
   (`lib/models/board/ad.dart`, `Equatable`) — это ровно `[id, userId, title,
   description, serviceTypeId, statusId, adTypeId, files, editAnimals,
   price]`; `isFavourite` в этот список **не входит**. Значит
   `ad.copyWith(isFavourite: !ad.isFavourite) == ad` — `true` по
   `Equatable`, поскольку все поля, реально участвующие в сравнении, не
   изменились. Сгенерированный `_BoardState.==`
   (`lib/pages/board/cubit/board_cubit.freezed.dart`) сравнивает поле `ads`
   через `const DeepCollectionEquality().equals(other._ads, _ads)` —
   поэлементно, тем же `Ad.==`; поскольку единственный изменившийся элемент
   считается равным старому, весь список признаётся равным, а остальные
   поля `BoardState` (`page`, `perPage`, `isLoading`, …) в этом сценарии не
   менялись — итог: `state.copyWith(ads: ...) == state` целиком, `true`.
8. `BoardCubit extends Cubit<BoardState>` (пакет `bloc`, версия из
   `pubspec.lock` — `9.0.1`). `Cubit.emit` делегирует в `BlocBase.emit`
   (`lib/src/bloc_base.dart`): `if (state == _state && _emitted) return;` —
   первая строка тела метода. Поскольку кандидат на эмит равен текущему
   `_state`, а `_emitted` уже `true` (после первого `load()` при открытии
   экрана), метод возвращается немедленно — `onChange(...)`, `_state =
   state` и `_stateController.add(_state)` **не выполняются вовсе**.
9. Следствие сильнее, чем «UI не перерисовался»: сам геттер `cubit.state`
   продолжает возвращать прежний объект `BoardState` — конкретный `Ad`
   внутри него по-прежнему хранит значение `isFavourite` **до** тапа, хотя
   запрос к серверу на шаге 4 уже успешно завершился. Это воспроизводимо на
   чистом уровне Dart-объектов, без привлечения дерева виджетов (см.
   «Связанные тесты»).
10. Ничего не сигнализирует об этом пользователю: исключения нет,
    `state.isError` остаётся `false`. `BlocBuilder<BoardCubit, BoardState>`
    (в `board_view.dart`/`my_ads_view.dart`) не получает уведомления об
    изменении — сердечко на карточке продолжает отображать ту же иконку,
    что и до тапа.
11. **Ветка `isOnlyFavouriteAds == true` (экран «Избранное») — единственная,
    где `UPDATE_OK` наблюдаем.** Список, полученный `.where((ad) => ad.id !=
    id)`, отличается от исходного по **длине** (при условии, что `id`
    действительно был в списке — а он есть, поскольку это единственный
    экран, показывающий только уже избранные объявления), и
    `DeepCollectionEquality` признаёт списки разной длины неравными без
    необходимости поэлементного сравнения через `Ad.==`. Следовательно
    `state != _state`, `BlocBase.emit` продолжает штатно: `_state`
    обновляется, `_stateController` уведомляет подписчиков, `BlocBuilder`
    перерисовывает сетку — карточка визуально и в `state` пропадает из
    списка «Избранное».

### Альтернативные потоки

- **Направление переключения на дефектных экранах (обе стороны).** Тест
  `'уже избранное объявление -> setAdFavourite вызывается с false (снятие с
  избранного)'` подтверждает, что `nextValue` корректно вычисляется в обе
  стороны (добавить/убрать) — сама логика вычисления направления не
  затронута дефектом, затронуто только последующее локальное отображение
  результата; дефект одинаково маскирует и добавление, и снятие с
  избранного.
- **Правильный, но недостижимый путь — детальная карточка.**
  `AdDetailCubit.toggleAdFavourite` (`lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart`)
  вызывает тот же `AdRepository.setAdFavourite`, но эмитит
  `state.copyWith(ad: state.ad.copyWith(isFavourite: !state.ad.isFavourite))`,
  где `state.ad` — `BoardAdDetailModel` (`@freezed`,
  `lib/pages/board_ad_detail/data/board_ad_detail_model.dart`): генерируемое
  freezed-сравнение включает **все** поля, включая `isFavourite`, поэтому
  здесь `state != _state` всегда корректно при реальном изменении, `emit`
  проходит штатно, дефекта нет. Однако кнопка, которая должна вызывать этот
  метод, закомментирована целиком в
  `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart`
  (`BoardAdDetailView.build`, `actions:` списка `AppBarSettings`) — блок
  `IconButtonForTextField(icon: model.isFavourite ? ... : ...,  onPressed: ()
  { context.read<AdDetailCubit>().toggleAdFavourite(model.adId); })`
  целиком в комментарии. Технически корректная реализация существует, но ни
  одно действие пользователя не может её вызвать.
- **Гость / нет сессии.** Ни один из файлов этого сценария не проверяет
  `AuthRepository.isAuthorized()` — при отсутствии токена локальный код
  ведёт себя идентично (тот же вызов, тот же дефект); реальное поведение
  сервера для неавторизованного запроса этим сценарием не проверяется (см.
  «Пользователь»).
- **Тот же класс дефекта, другое поле, не этот сценарий.**
  `BoardCubit.viewAd` (инкремент `viewsCount` при открытии карточки)
  страдает буквально тем же механизмом (`viewsCount` тоже отсутствует в
  `Ad.props`) — задокументировано отдельным «НАХОДКА»-тестом в том же
  файле, но это другое событие/сценарий, не относящийся к
  [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md); упоминается
  здесь только как соседний факт (см. «Открытые вопросы»).

### Связанные сущности

- [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad) — сущность, чьё поле
  `isFavourite` меняется на сервере этим сценарием; локально объект `Ad`
  пересобирается корректно (`copyWith`), но неполный `Equatable.props`
  делает пересборку неотличимой от отсутствия изменений для любого кода,
  полагающегося на `==` (в данном случае — генерируемое сравнение
  `BoardState`).
- `BoardState` (`@freezed`, `lib/pages/board/cubit/board_state.dart`) — не
  отдельная сущность домена, а технический контейнер состояния экрана;
  упоминается здесь потому, что именно его сгенерированное поэлементное
  сравнение (`DeepCollectionEquality` поверх `Ad.==`) — механизм, через
  который дефект `Ad.props` доходит до `Cubit.emit`.

### Бизнес-правила

- Доменный факт «объявление в избранном у этого пользователя» после
  успешного запроса всегда соответствует серверной истине — этот сценарий
  не описывает расхождение с сервером, только расхождение между сервером и
  тем, что видит (и на что может дальше опираться) один и тот же процесс
  на клиенте до следующей полной перезагрузки списка (`load`/`refresh`).
- Ветка удаления карточки на экране «Избранное» — не осознанное исправление
  дефекта, а побочный эффект другой формы мутации (изменение длины списка,
  а не поля элемента); тот же код, примени его к любому полю, кроме
  удаления целого элемента, снова упёрся бы в тот же неполный `Ad.props`.
- Не существует отдельного пути, который заново перечитывал бы объявление с
  сервера сразу после успешного `setAdFavourite` — единственный способ,
  которым лента/«Мои объявления» когда-либо увидят корректный
  `isFavourite`, — это следующий независимый `load()`/`refresh()`
  (например, pull-to-refresh или повторное открытие экрана), не что-либо,
  сделанное этим сценарием.

## TARGET

TARGET не отличается от CURRENT — это документирующий проход, фиксирующий
уже существующее поведение (включая уже известный, ранее задокументированный
в [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)/[EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md)
дефект), а не проход по исправлению кода.

## TBD / BLOCKED

Блокеров для документирования нет. Основной поток (обе ветки —
`isOnlyFavouriteAds == false` и `== true`) и контрастный недостижимый путь
(`AdDetailCubit`) воспроизведены статическим чтением кода
(`Ad.props` → сгенерированный `_BoardState.==` → `BlocBase.emit`) и
подтверждены существующими прогоняемыми тестами (см. «Связанные тесты»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/board/presentation/widgets/board_populated.dart` | `BoardPopulated` (`InkWell.onTap` → `toggleAdFavourite`) | CURRENT | UI-триггер — сердечко на карточке, общий виджет для всех трёх экранов |
| `lib/pages/board/presentation/widgets/board_view.dart` | `_BoardViewState.build` (`BlocProvider(create: (_) => BoardCubit()..load(page: 1))`) | CURRENT | точка входа №1 — общая лента, `isOnlyFavouriteAds == false` |
| `lib/pages/my_ads/presentation/my_ads_view.dart` | `MyAdsView.build` (`BoardCubit()..load(page: 1, isMyAds: true)`) | CURRENT | точка входа №2 — «Мои объявления», `isOnlyFavouriteAds == false` |
| `lib/pages/favourite_ads/presentation/favourite_ads_view.dart` | `FavouriteAdsView.build` (`BoardCubit()..load(page: 1, isFavouriteAds: true)`) | CURRENT | точка входа №3 — «Избранное», единственный с `isOnlyFavouriteAds == true` |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit.toggleAdFavourite` | CURRENT | ядро сценария — вычисляет направление, вызывает repository, ветвится по `isOnlyFavouriteAds` |
| `lib/pages/board/cubit/board_state.dart` | `BoardState` (`@freezed`, поле `ads: List<Ad>`) | CURRENT | контейнер состояния экрана |
| `lib/pages/board/cubit/board_cubit.freezed.dart` | `_BoardState.==` (сгенерирован) | CURRENT | `const DeepCollectionEquality().equals(other._ads, _ads)` — источник маскировки дефекта в ветке `isOnlyFavouriteAds == false` |
| `lib/models/board/ad.dart` | `Ad.props` (`Equatable`) | CURRENT | не включает `isFavourite` (и ряд других изменяемых после загрузки полей) |
| `lib/models/board/ad.dart` | `Ad.copyWith` | CURRENT | строит новый `Ad` с инвертированным `isFavourite` — но новый и старый экземпляр равны по `props` |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.setAdFavourite`, `.addAdToFavouritesFromApi`, `.removeAdFromFavouritesFromApi` | CURRENT | `POST /selected-ads` (добавить) / `DELETE /selected-ads/{id}` (убрать); throw при `response['status'] != "1"` |
| `lib/constants.dart` | `Constants.boardServiceApi` | CURRENT | базовый путь эндпоинтов доски |
| `/Users/pavelsmirnov/.pub-cache/hosted/pub.dev/bloc-9.0.1/lib/src/bloc_base.dart` | `BlocBase.emit` | CURRENT (внешний пакет `bloc`, версия закреплена в `pubspec.lock`) | `if (state == _state && _emitted) return;` — пропускает эмит целиком, включая обновление `_state`, при равном кандидате |
| `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` | `AdDetailCubit.toggleAdFavourite` | CURRENT | контрастный, технически корректный путь — свободен от этого дефекта |
| `lib/pages/board_ad_detail/data/board_ad_detail_model.dart` | `BoardAdDetailModel` (`@freezed`) | CURRENT | модель детальной карточки — все поля, включая `isFavourite`, участвуют в сгенерированном сравнении |
| `lib/pages/board_ad_detail/presentation/board_ad_detail_view.dart` | `BoardAdDetailView.build` (закомментированный `IconButtonForTextField`) | CURRENT | единственная кнопка, способная вызвать корректный путь, — закомментирована целиком, недостижима из UI |

## Критерии приёмки

- После успешного `AdRepository.setAdFavourite` на экране общей ленты или
  «Мои объявления» (`state.isOnlyFavouriteAds == false`)
  `cubit.state.ads.singleWhere((ad) => ad.id == id).isFavourite` равно
  значению **до** тапа — переключение не отражается ни в `state`, ни, тем
  более, в UI, независимо от направления (добавление/снятие).
- На экране «Избранное» (`state.isOnlyFavouriteAds == true`) после
  успешного снятия с избранного элемент с этим `id` отсутствует в
  `cubit.state.ads` — единственная ветка, где результат `UPDATE_OK`
  наблюдаем целиком.
- Ни в одной из двух веток не возникает исключения и не выставляется
  `state.isError == true` — дефект в основной ветке полностью тихий.
- `AdRepository.setAdFavourite(id, true)` формирует `POST
  ${Constants.boardServiceApi}/selected-ads` с телом `{'ad_id': id}`;
  `setAdFavourite(id, false)` — `DELETE
  ${Constants.boardServiceApi}/selected-ads/{id}`.
- `AdDetailCubit.toggleAdFavourite`, вызванный напрямую (минуя
  закомментированную кнопку), корректно обновляет `state.ad.isFavourite` —
  контрольное подтверждение того, что дефект локализован именно в
  `Ad.props`/`BoardCubit`, а не в самом сетевом вызове или в домене
  «избранное» как таковом.

## Связанные тесты

- `test/pages/board_cubit_test.dart`, group `'UC-141 — BoardCubit.toggleAdFavourite'`:
  - `'сервер подтверждает переключение, но иконка НЕ обновляется — НАХОДКА'` —
    прямое подтверждение основного дефекта: мокает
    `adRepository.setAdFavourite(9, true)` успехом, вызывает
    `cubit.toggleAdFavourite(9)`, подтверждает вызов repository
    (`verify(...).called(1)`), но `cubit.state.ads.single.isFavourite`
    остаётся `false` вместо ожидаемого `true`.
  - `'уже избранное объявление -> setAdFavourite вызывается с false (снятие
    с избранного)'` — подтверждает корректность вычисления направления
    переключения, без проверки визуального/`state`-отображения результата.
  - `'на экране "Избранное" (isOnlyFavouriteAds) -> toggle убирает карточку
    из списка целиком'` — прямое подтверждение единственной наблюдаемой
    ветки: после `toggleAdFavourite` карточка с этим `id` пропадает из
    `cubit.state.ads`.
- `test/repositories/ad_repository_test.dart`, group `'UC-141 —
  AdRepository.setAdFavourite'`:
  - `'isFavourite:true -> POST /selected-ads с ad_id'`.
  - `'isFavourite:false -> DELETE /selected-ads/{id}'`.
- `test/pages/ad_detail_cubit_test.dart`, group `'НАХОДКА —
  AdDetailCubit.toggleAdFavourite (мёртвый код, недостижим из UI — см.
  MOD-5-BOARD/ENT-14)'` — контрастное подтверждение: тест `'успех ->
  локальный флаг обновлён (BoardAdDetailModel — freezed, не страдает
  багом BoardCubit/Ad.props)'` показывает, что тот же серверный вызов, при
  freezed-модели вместо `Equatable`-DTO, корректно обновляет `state.ad.isFavourite`.
  Название группы ссылается на `ENT-14` — устаревшая нумерация с прошлого
  прохода специфицирования (модуль `ANIMAL`), процитирована здесь дословно,
  как она реально написана в файле, без исправления.
- Старая нумерация групп (`UC-141` во всех трёх файлах) относится к прежней
  схеме id и не переименована на момент написания этой спеки —
  переименование в `UC-141` выполняется отдельным контролируемым проходом,
  не этой задачей; якорь `grep -r "UC-141" test/` заработает только после
  него.
- В этот use-case намеренно не входят (ветка `ERROR`, отдельный будущий
  файл): `test/pages/board_cubit_test.dart`, group `'UC-142 —
  BoardCubit.toggleAdFavourite ERROR (известный дефект — без try/catch)'`;
  `test/repositories/ad_repository_test.dart`, group `'UC-142 —
  AdRepository.addAdToFavouritesFromApi/removeAdFromFavouritesFromApi ERROR'`.

## Открытые вопросы и ограничения

- **Корректный путь существует, но требует одной строки в UI, не
  переделки `BoardCubit`.** Раскомментирование кнопки в
  `BoardAdDetailView.build` сделало бы избранное рабочим на детальной
  карточке (freezed-модель уже свободна от дефекта), но никак не исправило
  бы ленту/«Мои объявления» — они используют `BoardCubit`/`Ad`, не
  `AdDetailCubit`/`BoardAdDetailModel`, и потребовали бы отдельного
  исправления (расширение `Ad.props` либо перевод `Ad`/`BoardState` на
  freezed-паттерн, как уже отмечено в
  [ENT-18](../entities/ENT-18-AD-IN-BOARD.md)). Ни то, ни другое не
  выполняется в рамках этого документирующего прохода.
- **Тот же класс дефекта затрагивает `viewsCount`** (`BoardCubit.viewAd`,
  задокументирован отдельным «НАХОДКА»-тестом в том же файле) — общий
  корень (неполный `Ad.props`) означает, что расширение `props` до полного
  списка полей исправило бы оба независимо обнаруженных сценария разом, а
  не только избранное. `viewAd`, помимо этого, — мёртвый код (не вызывается
  нигде в `lib/`), поэтому его собственный дефект на практике никогда не
  наблюдается пользователем; сюда упомянут только для полноты картины по
  общему корню.
- **Не проверено на уровне виджета.** Существующие тесты подтверждают
  дефект на уровне `Cubit`-состояния (`cubit.state` действительно не
  меняется) — этого уже достаточно, чтобы исключить перерисовку на любом
  вышестоящем уровне (виджет не может перерисоваться от уведомления,
  которого не было), но отдельного `testWidgets`/golden-теста, вживую
  показывающего неизменную иконку на экране, нет.
- **Гостевой доступ к этому действию не проверен эмпирически.** Локальный
  код не содержит проверки авторизации ни на одном шаге этого сценария;
  что происходит при реальном вызове от имени гостя (сервер отклоняет
  запрос / принимает так же, как от авторизованного) — не установлено ни
  чтением кода, ни тестом, за пределами утверждения из
  [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), что BOARD «требует
  реальной авторизации» для мутаций.
