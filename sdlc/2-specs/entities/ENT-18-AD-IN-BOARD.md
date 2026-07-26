# ENT-18 — Ad

## Описание

Объявление доски (продажа животного — одного или нескольких — либо услуга).
**Полностью online-only**: `class Ad extends Equatable` (`lib/models/board/ad.dart`)
— обычный DTO, парсится из ответа API прямо в Cubit/Repository. Нет ни
Drift-таблицы, ни черновика/unsent-паттерна — в отличие от большинства
сущностей `ANIMAL`, здесь нет local-first: без сети лента/карточка/создание
объявления недоступны целиком.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int | серверный id |
| `userId` | int | автор объявления |
| `title` | String | заголовок |
| `description` | String | описание |
| `serviceTypeId` | int? | тип услуги — принимается и отправляется API, но ни одна степ-страница визарда создания не даёт пользователю его выбрать; поле фактически всегда `null` на клиенте |
| `statusId` | int? | статус объявления (справочник `board_ad_statuses`) |
| `adTypeId` | int? | тип объявления: `1` продажа, `3` услуга (единственные два выбираемые в визарде создания — `Constants.boardAdTypeIds`), `5` пропажа/lost, `6` найдено/found (полностью реализованы в коде визарда, но недоступны для выбора при создании — только при редактировании уже существующего объявления такого типа), «Стадо» — заявлен, помечен «в разработке», недоступен |
| `price` | String? | извлекается из общего списка `attributes` объявления по фиксированному `attribute_id == 13` |
| `files` | List\<String\> | пути/URL фотографий объявления |
| `animals` | List\<BoardAdAnimalSpec\> | вычисленные карточки животных для отображения (для продажи нескольких животных сразу) |
| `editAnimals` | List\<AdAnimalModel\> | те же животные в форме, пригодной для повторного редактирования формы |
| `phone` | String? | извлекается из `attributes` по `attribute_id == 9` |
| `address` | String? | извлекается из `attributes` по `attribute_id == 10` |
| `whenWasFoundText` | String? | только для `adTypeId == 6` (найдено); извлекается из `attributes` по `attribute_id == 12` |
| `payload` | `AdPayload?` | данные автора (имя/фамилия/email), из `json['payload']['author']` |
| `isFavourite` | bool, default false | признак «в избранном» текущего пользователя |
| `viewsCount` | int, default 0 | счётчик просмотров |

Цена/телефон/адрес/«когда нашлось» — не собственные поля объявления на
сервере, а generic «атрибуты» (`ad_attribute_values`, id атрибута жёстко
закодирован на клиенте: `9`=телефон, `10`=адрес, `12`=когда нашлось,
`13`=цена) — справочник атрибутов (`board_attributes`, `BoardAttributesRepository`)
синхронизируется локально (Drift), используется только этим модулем.

## Связи

- Справочники **используются только этим модулем**, описаны здесь как поля/
  связи, не заведены отдельными сущностями (тот же паттерн, что у справочников
  вакцинации внутри [ENT-14](ENT-14-VACCINATION-IN-ANIMAL.md)): `board_ad_types`
  (тип объявления), `board_ad_statuses` (статус), `board_attributes`
  (генерик-атрибуты: телефон/адрес/цена/«когда нашлось»), `board_service_types`
  (тип услуги, фактически мёртв на клиенте — см. выше).
- [ENT-19](ENT-19-CHAT-IN-BOARD.md) (Chat) — ссылается на объявление по `adId`,
  не наоборот; объявление не хранит список своих чатов.
- `AnimalIdentification`/`Kind`/`Breed`/`Suit` (HANDBOOKS/ANIMAL) — животные
  внутри объявления (`BoardAdAnimalSpec`/`AdAnimalModel`) ссылаются на вид/
  породу/масть по id для отображения, читаются, не изменяются этим модулем.
- `Country` ([ENT-4](ENT-4-COUNTRY-IN-HANDBOOKS.md), HANDBOOKS) — адрес
  объявления содержит страну по коду; `Country.boardEnabled` определяет саму
  доступность этого модуля целиком (см. событие проверки доступности) — читается,
  не редактируется здесь.

## Инварианты

- **Equatable `props` не включает большинство изменяемых после первой
  загрузки полей** (`lib/models/board/ad.dart`): в список входят только
  `id, userId, title, description, serviceTypeId, statusId, adTypeId, files,
  editAnimals, price` — `isFavourite`, `viewsCount`, `phone`, `address`,
  `whenWasFoundText`, `payload`, `animals` **отсутствуют**. Поскольку
  `BoardState` (`@freezed`) сравнивается глубоко, а `flutter_bloc` пропускает
  `emit()` при `state == _state`, изменение любого из отсутствующих в `props`
  полей (в первую очередь `isFavourite`/`viewsCount` — единственные два, что
  реально меняются в рантайме после toggle/просмотра) **не вызывает
  перерисовку UI**, даже если запрос к серверу прошёл успешно и локальный
  объект был корректно пересобран с новым значением.
- **Множественный выбор фильтров (вид/порода/масть) не работает на сервере.**
  `AdRepository.getAds` отправляет только `kindList.firstOrNull`/`breedList.firstOrNull`/
  `suitList.firstOrNull` — если пользователь выбрал несколько значений в
  диалоге фильтров, реально применяется только первое; `ad_type_ids[]`,
  наоборот, передаётся полным массивом.
- **Онлайн-only, без сети — недоступно целиком.** Нет офлайн-черновика
  объявления; неудачное создание/правка теряет введённые пользователем
  данные экрана только на уровне того, что форма не сбрасывается (см. события
  публикации/правки), но ничего не сохраняется даже локально до следующей
  попытки.
- **Типы объявлений «Пропажа»(5)/«Найдено»(6) недостижимы из визарда
  создания**, хотя вся бизнес-логика для них реализована и работает при
  редактировании уже существующего объявления такого типа
  (`Constants.boardAdTypeIds = [3, 1]` ограничивает шаг выбора типа;
  `BoardAdCreateData.fromAd` не накладывает это же ограничение при
  инициализации формы для правки).

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/models/board/ad.dart` | `Ad`, `AdResponse`, `AdPayload` | CURRENT | DTO объявления, парсинг ответа API, неполный `props` |
| `lib/models/board/ad_animal_model.dart` | `AdAnimalModel` | CURRENT | DTO животного внутри объявления, для повторного редактирования формы |
| `lib/models/board/ad_create_request.dart` | `AdCreateRequest` | CURRENT | билдер multipart-тела запроса создания/редактирования, генерик-атрибуты |
| `lib/repositories/board/ad_repository.dart` | `AdRepository.getAds`, `getMyAds`, `getFavouriteAds`, `createAd`, `updateAd`, `deleteAd`, `viewAd`, `setAdFavourite` | CURRENT | все CRUD-операции объявления |
| `lib/repositories/board/board_ad_types_repository.dart`, `board_ad_statuses_repository.dart`, `board_attributes_repository.dart`, `board_service_types_repository.dart` | соответствующие `*Repository` | CURRENT | справочники, используемые только этим модулем |
| `packages/sheep_farm_database/lib/entities/board/` | таблицы `board_ad_types`/`board_ad_statuses`/`board_attributes`/`board_service_types` | CURRENT | локальный кэш справочников (миграция `from < 79`) |
| `lib/pages/board/cubit/board_cubit.dart` | `BoardCubit` | CURRENT | лента/«Мои»/«Избранное» — один Cubit на все три сценария |
| `lib/pages/board_ad_detail/cubit/ad_detail_cubit.dart` | `AdDetailCubit` | CURRENT | детальная карточка |
| `lib/pages/board_ad_create/bloc/board_ad_create_bloc.dart` | `BoardAdCreateBloc` | CURRENT | визард создания/редактирования |
