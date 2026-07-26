- **business task**: `BT-24` ([`../1-business-tasks/planning/BT-24-PLANNING-ANIMAL-WEIGH-DEDUP-MASS.md`](../1-business-tasks/planning/BT-24-PLANNING-ANIMAL-WEIGH-DEDUP-MASS.md))
- **spec**: `UC-316` ([`../2-specs/use-cases/UC-316-ACTOR-5-EVT-54-ENT-8-CREATE_OK-IN-ANIMAL.md`](../2-specs/use-cases/UC-316-ACTOR-5-EVT-54-ENT-8-CREATE_OK-IN-ANIMAL.md), supersedes `UC-113`), `ENT-8`
- **design**: не требуется — правка в DAO-слое, UI не меняется
- **tracker**: нет подключённого трекера (Yandex Tracker MCP недоступен в этой сессии) — по `RUNBOOK.md` шаг 6, этот файл является записью учёта. Внешний тикет-источник — `SHEEP-4`, пункт чек-листа 9

# Массовое взвешивание: дедуп «сегодняшней записи» ломается из-за неполной загрузки животного

## Объём

Единственная правка — `AnimalsDao._toListAnimalsWithDetails`
(`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart:495-547`):
добавить подтягивание `animalWeighings`, по образцу уже существующего в
`getAllAnimalsWithDetailsByFilters` (:400-401 — запрос
`db.animalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(aIds)`,
:432-434 — привязка к `AnimalWithDetails` по `animal.id`).

Это единственная точка причины бага — `WeighAnimalCubit._findTodayWeighing()`
(`weigh_animal_cubit.dart:54-64`) и вся логика insert/update вокруг нее
(`saveCurrentWeighingStayOnPage`/`saveWeighing`) уже корректны и не
требуют изменений; они просто получают неполные данные для животных,
найденных сканированием/поиском по номеру (массовое взвешивание), в
отличие от одиночной карточки.

Полное обоснование — `UC-316`.

## Критерии приёмки (definition of done)

- [ ] Повторное взвешивание животного в тот же день через массовый (сканирование/поиск) сценарий обновляет существующую сегодняшнюю запись, а не создаёт новую.
- [ ] Первое взвешивание животного за день — по-прежнему создаёт новую запись.
- [ ] Одиночный сценарий (карточка) — без изменений в поведении.
- [ ] Другие вызывающие места `_toListAnimalsWithDetails`/`searchAllAnimalsWithDetailsByNumbersAndName` (не только взвешивание) не регрессируют от добавления нового поля в результат.

## Реализационные заметки

- Не трогать `getAllAnimalsWithDetailsByFilters` — она уже корректна, используется как образец, не как объект правки.
- Добавить тест-кейс на дедуп через поисковый/сканирующий сценарий загрузки животного (сейчас не покрыт ни одним тестом) — не только на прямую загрузку по id.

## Зависимости

Нет блокирующих зависимостей.
