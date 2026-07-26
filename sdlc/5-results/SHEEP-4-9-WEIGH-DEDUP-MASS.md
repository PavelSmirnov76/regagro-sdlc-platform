- **task**: [`../4-tasks/SHEEP-4-9-WEIGH-DEDUP-MASS.md`](../4-tasks/SHEEP-4-9-WEIGH-DEDUP-MASS.md) (`UC-316`)

# Реализовано

Единственная правка — `AnimalsDao._toListAnimalsWithDetails`
(`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart`):
добавлено подтягивание `animalWeighings` через
`db.animalWeighingsDao.getAnimalWeighingsByAnimalIdsOrderByWeighingDateAsc(animalIds)`,
по образцу уже существующего кода в `getAllAnimalsWithDetailsByFilters`.
`WeighAnimalCubit._findTodayWeighing()`/`saveCurrentWeighingStayOnPage()`/
`saveWeighing()` не менялись — баг был только во входных данных
(`AnimalWithDetails.animalWeighings`), не в логике дедупа.

## Проверено

- `flutter analyze` по обоим изменённым файлам — без замечаний.
- **Новый интеграционный тест** (реальная in-memory БД, не моки) в
  `test/repositories/animals_repository_test.dart`, группа `UC-316 —
  searchAllAnimalsWithDetailsByNumbersAndName подтягивает animalWeighings` —
  вставляет животное и взвешивание напрямую в БД, ищет животное через
  `AnimalsRepository.searchAllAnimalsWithDetailsByNumbersAndName` (тот же
  путь, что `WeighAnimalCubit.getAnimals()` в массовом сценарии), проверяет,
  что `animalWeighings` в результате не пусто. Это единственный способ
  реально проверить фикс — тесты `WeighAnimalCubit` мокают
  `AnimalsRepository` целиком и не могут воспроизвести баг DAO-уровня.
- `flutter test test/repositories/animals_repository_test.dart
  test/pages/weigh_animal_cubit_test.dart` — все 49 тестов проходят
  (регрессия исключена).
- `dart format` применён (в `animals_repository_test.dart` — большой diff по
  переносам строк, файл ранее не форматировался по актуальному стандарту
  ширины 80 — ожидаемо согласно `CLAUDE.md`).

## Отложено / не сделано

Ничего — объём задачи полностью покрыт правкой и тестом.
