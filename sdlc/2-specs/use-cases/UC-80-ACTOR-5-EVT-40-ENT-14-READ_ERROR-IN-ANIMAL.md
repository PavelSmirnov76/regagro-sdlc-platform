# UC-80 — Хаб неотправленных вакцинаций не грузится: `UnsentVaccinationCubit.load` ловит исключение

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md) |
| Сущность | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md)
(`vaccinations.viewed_unsent`): пользователь открывает хаб ещё не отправленных
вакцинаций, но `UnsentVaccinationCubit.load`
(`lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart`) ловит
исключение, брошенное при попытке прочитать неотправленные записи через
`VaccinationsRepository.getNotSyncVaccinationsWithDetails()` — техническая
ошибка (Drift/БД), не бизнес-отказ и не «список пуст». `catch` эмитит
`UnsentVaccinationError` с `message: e.toString()` — сырой текст исключения,
без перевода и без логирования, — и страница вместо списка/пустого состояния
показывает полноэкранное сообщение об ошибке с этим же сырым текстом.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково. Проверено чтением
`unsent_vaccination_cubit.dart` целиком: `UnsentVaccinationCubit` не
объявляет и не использует `AuthRepository` ни в одном методе, включая
`load` — доступ к экрану не зависит от статуса авторизации.

## CURRENT

### Основной поток

1. Пользователь открывает сводный экран «В работе» (`InWorkPage`) и нажимает
   на плитку вакцинаций — `onTap: () =>
   context.pushNamed2(Routes.unsentVaccination)`
   (`lib/pages/in_work/in_work_page.dart`). Это единственный найденный вход
   на этот экран во всём приложении (`grep` по `Routes.unsentVaccination` в
   `lib/` не находит других мест навигации на этот маршрут).
2. `Routes.unsentVaccination` (`lib/pages/routes.dart`) резолвится в
   `UnsentVaccinationPage`. `build` оборачивает страницу в `BlocProvider(create:
   (context) => UnsentVaccinationCubit()..load())` — `load()` вызывается сразу
   при создании кубита, без ожидания какого-либо ввода пользователя.
3. `load()` синхронно эмитит `UnsentVaccinationLoading()` (страница показывает
   `CustomLottieLoader` внутри `BottomSheetPageWrapper`), затем внутри `try`
   вызывает `await _vaccinationsRepository.getNotSyncVaccinationsWithDetails()`.
4. **Точка технического сбоя (этот сценарий).**
   `_vaccinationsRepository.getNotSyncVaccinationsWithDetails()`
   (`lib/repositories/vaccination/vaccinations_repository.dart`) — тонкая
   обёртка, делегирующая целиком в `VaccinationsDao
   .getNotSyncVaccinationsWithDetails()`
   (`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`);
   любое исключение, брошенное на любом шаге этого DAO-метода (сам
   join-запрос `query.get()`, либо любой из вложенных await-вызовов внутри
   цикла по строкам — см. «Альтернативные потоки»), долетает наверх без
   изменений, так как ни `VaccinationsRepository`, ни промежуточный
   `BaseRepository` не оборачивают вызов в собственный `try/catch`.
5. `catch (e)` в `UnsentVaccinationCubit.load` перехватывает исключение:
   ```dart
   } catch (e) {
     emit(
       UnsentVaccinationError(message: e.toString(), selectedVaccinations: []),
     );
   }
   ```
   Логирования (`Talker` или аналог) в этой ветке нет — исключение нигде не
   попадает в лог приложения, единственный след — то, что дошло до `emit`.
   `selectedVaccinations` явно сбрасывается в пустой список (тот же паттерн,
   что и в успешной ветке `load()`).
6. `UnsentVaccinationPage`'s `BlocBuilder<UnsentVaccinationCubit,
   UnsentVaccinationState>` реагирует на `state is UnsentVaccinationError`
   веткой:
   ```dart
   return BottomSheetPageWrapper(
     child: Center(
       child: ProgressMessage.somethingWentWrong(message: state.message),
     ),
   );
   ```
   `ProgressMessage.somethingWentWrong` (`lib/widgets/progress_bar/progress_message.dart`)
   рендерит `state.message` буквально через `Text(message, textAlign:
   TextAlign.center)` — без `AppLocalizations.tr(...)`, без хелпера
   `showAppSnackBarError` (`lib/widgets/app_snackbar.dart`). Пользователь
   видит `Exception: <исходный текст исключения>` (для реального Drift-сбоя
   — сырое сообщение платформенного исключения) вместо переведённого
   сообщения об ошибке.
7. Экран остаётся в этом состоянии до следующего действия пользователя.
   `UnsentVaccinationPage` не предоставляет кнопку «Повторить» — единственный
   способ выйти из `UnsentVaccinationError` — закрыть экран (кнопка «назад» в
   `CustomAppBar`) и открыть его заново с экрана «В работе», что пересоздаст
   `UnsentVaccinationCubit` и заново вызовет `load()`.

### Альтернативные потоки

- **Четыре независимых по происхождению точки внутри одного и того же DAO-вызова
  сходятся в один `catch`.** `VaccinationsDao.getNotSyncVaccinationsWithDetails`
  сначала выполняет один join-запрос (`query.get()` — фильтр `sync ==
  false && deletedAt IS NULL && updatedAt IS NULL`), затем для каждой
  полученной строки последовательно (не параллельно) вызывает: (а)
  `db.animalsDao.getAnimalWithDetailsById(vaccination.animalId)` — отдельный
  Drift-запрос по каждому животному; (б) `_getDiseasesByLink(vaccination.id)`
  → `_getDiseasesByVaccinationId` — запрос связочной таблицы
  `DiseasesVaccinations` плюс подгрузка болезней по id; (в)
  `calculateVaccinationStatus(vaccination)` — своя внутренняя логика (не
  проверялась на предмет собственных запросов к БД в рамках этого сценария,
  видна только сигнатура `Future<VaccinationStatusEnum>
  calculateVaccinationStatus(Vaccination vaccination)`). Исключение из любой
  из этих точек, для любой строки результата, всплывает наверх одинаково —
  `UnsentVaccinationCubit.load`'s `catch` не различает, какая именно строка
  или какая именно из четырёх операций отказала.
- **`getAnimalWithDetailsById` возвращающий `null` — не эта ветка.**
  Если конкретное животное не найдено (`animalWithDetails == null`), DAO
  подставляет заглушку (`AnimalWithDetails(animal: Animal(id:
  vaccination.animalId, kindId: 0, gender: 0))`) — это не исключение и не
  приводит к `UnsentVaccinationError`; сценарий, описанный здесь, требует
  реального брошенного исключения на одном из шагов, не отсутствия строки.
- **`loadSilent()` — соседний метод с похожим, но не идентичным поведением
  на исключении**, не документируется этим use-case (другой публичный вход,
  не связанный с `EVT-40`/этим экраном напрямую): `catch` там тоже эмитит
  `UnsentVaccinationError(message: e.toString(), ...)`, но пытается сохранить
  `state.selectedVaccinations` вместо явного сброса в `[]` — однако
  промежуточный `emit(UnsentVaccinationLoading())` без аргументов (перед
  `try`) уже стирает выбор до того, как код успевает его прочитать (см.
  `test/pages/unsent_vaccination_cubit_test.dart`, группа про баг
  `loadSilent`). `load()`, описанный в этом сценарии, не имеет этой проблемы:
  выбор явно и целенаправленно обнуляется на каждый вызов, независимо от
  исхода.

### Связанные сущности

- [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) (Vaccination) —
  целевая сущность чтения; при сбое ни одна строка (успешно прочитанная до
  точки сбоя или нет) не попадает в состояние экрана — `UnsentVaccinationError`
  несёт пустой список, а не частичный результат.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  для каждой строки вакцинации через `getAnimalWithDetailsById`
  (только чтение; ничего не изменяется), один из альтернативных источников
  исключения.

### Бизнес-правила

- Технический сбой чтения (исключение из Drift-запроса на любом из
  вложенных шагов DAO-метода) классифицируется как `READ_ERROR`, а не как
  «список пуст» — `UnsentVaccinationLoaded(vaccinations: [])` и
  `UnsentVaccinationError` — два разных, не путаемых в коде состояния;
  `UnsentVaccinationPage` рендерит их разными ветками (`ProgressMessage
  .notFound` со статическим `list_is_empty` против `ProgressMessage
  .somethingWentWrong` с сырым текстом исключения).
- Один и тот же `catch (e)` в `UnsentVaccinationCubit.load` покрывает все
  возможные источники исключения внутри `getNotSyncVaccinationsWithDetails()`
  (сам join-запрос и три вложенных await-вызова на каждую строку) без
  различения по источнику — сообщение пользователю всегда буквально
  `e.toString()` пойманного исключения, что бы оно ни было.
- В отличие от нескольких других мест в этом же файле-кубите
  (сравнимых по форме `catch`-блоков в `delete`/`deleteSelected`/`loadSilent`)
  ошибка на этом пути нигде не логируется (`Talker` не вызывается) —
  единственный след ошибки для разработчика — то, что видит пользователь на
  экране.
- Сообщение, показанное пользователю, — необработанный `e.toString()`, без
  прогона через `AppLocalizations.tr(...)` и без хелпера `showAppSnackBarError`;
  для реального (не мокнутого) Drift-исключения это будет техническая строка
  вида `Exception: <platform message>`, не рассчитанная на отображение
  конечному пользователю.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и точки возможного технического сбоя внутри
`VaccinationsDao.getNotSyncVaccinationsWithDetails` прослежены чтением
`lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart`,
`lib/pages/unsent_vaccination/unsent_vaccination_page.dart`,
`lib/repositories/vaccination/vaccinations_repository.dart`,
`packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart`,
`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` и
`lib/widgets/progress_bar/progress_message.dart` целиком — не восстановлено
по памяти.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/unsent_vaccination/unsent_vaccination_cubit.dart` | `UnsentVaccinationCubit.load` | CURRENT | единственный `try/catch` этого сценария; при исключении эмитит `UnsentVaccinationError(message: e.toString(), selectedVaccinations: [])`, без логирования |
| `lib/pages/unsent_vaccination/unsent_vaccination_state.dart` | `UnsentVaccinationError`, `UnsentVaccinationLoading`, `UnsentVaccinationLoaded` | CURRENT | состояния, участвующие в сценарии; legacy-паттерн (`abstract class` + ручные подклассы, не `freezed`) |
| `lib/pages/unsent_vaccination/unsent_vaccination_page.dart` | `UnsentVaccinationPage.build` (`BlocProvider`, `BlocBuilder`) | CURRENT | создаёт кубит и вызывает `load()` сразу при построении страницы; рендерит `ProgressMessage.somethingWentWrong(message: state.message)` при `UnsentVaccinationError` |
| `lib/pages/in_work/in_work_page.dart` | `InWorkPage` (плитка вакцинаций, `onTap`) | CURRENT | единственный найденный вход на `Routes.unsentVaccination` |
| `lib/pages/routes.dart` | `Routes.unsentVaccination` | CURRENT | маршрут, резолвящийся в `UnsentVaccinationPage` |
| `lib/repositories/vaccination/vaccinations_repository.dart` | `VaccinationsRepository.getNotSyncVaccinationsWithDetails` | CURRENT | тонкая обёртка (`return await dao.getNotSyncVaccinationsWithDetails();`) — не перехватывает исключение |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.getNotSyncVaccinationsWithDetails` | CURRENT | join-запрос по `Vaccinations` (фильтр `sync == false && deletedAt IS NULL && updatedAt IS NULL`) плюс по три вложенных await-вызова на каждую строку — реальный источник исключения в этом сценарии |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao._getDiseasesByLink` / `_getDiseasesByVaccinationId` | CURRENT | альтернативный источник исключения (запрос `DiseasesVaccinations` + подгрузка болезней), вызывается на каждую строку внутри `getNotSyncVaccinationsWithDetails` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations_dao.dart` | `VaccinationsDao.calculateVaccinationStatus` | CURRENT | альтернативный источник исключения, вызывается на каждую строку внутри `getNotSyncVaccinationsWithDetails` |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.getAnimalWithDetailsById` | CURRENT | альтернативный источник исключения (Drift-запрос по `animalId`), вызывается на каждую строку внутри `getNotSyncVaccinationsWithDetails` |
| `packages/sheep_farm_database/lib/entities/vaccination/vaccinations/vaccinations.dart` | `Vaccinations` | CURRENT | схема таблицы, читаемой join-запросом |
| `lib/widgets/progress_bar/progress_message.dart` | `ProgressMessage.somethingWentWrong` | CURRENT | рендерит `state.message` буквально через `Text(...)`, без перевода |
| `lib/repositories/base_repository.dart` | `BaseRepository` (базовый класс `VaccinationsRepository`) | CURRENT | не добавляет собственную обработку ошибок вокруг `dao`-вызовов |

## Критерии приёмки

- При исключении из `_vaccinationsRepository
  .getNotSyncVaccinationsWithDetails()` внутри `UnsentVaccinationCubit.load`
  кубит эмитит ровно последовательность: `UnsentVaccinationLoading()` →
  `UnsentVaccinationError(message: e.toString(), selectedVaccinations: [])`
  — без промежуточных состояний.
- `UnsentVaccinationError.message` — это буквально `e.toString()` пойманного
  исключения, без дополнительной обработки, маскировки или перевода в
  кубите.
- `UnsentVaccinationError.selectedVaccinations` — пустой список независимо от
  того, что было выбрано до вызова `load()` (в отличие от `loadSilent()`,
  который пытается сохранить выбор, но фактически тоже его теряет из-за
  отдельного бага).
- `UnsentVaccinationPage` при `state is UnsentVaccinationError` рендерит
  `ProgressMessage.somethingWentWrong(message: state.message)` внутри
  `BottomSheetPageWrapper`, а не список/пустое состояние/загрузку.
- Исключение из любого из трёх вложенных await-вызовов внутри цикла по
  строкам DAO-метода (`getAnimalWithDetailsById`, `_getDiseasesByLink`,
  `calculateVaccinationStatus`), а не только из самого `query.get()`,
  приводит к тому же исходу — `UnsentVaccinationError` в кубите.

## Связанные тесты

`test/pages/unsent_vaccination_cubit_test.dart`, group `'UC-80 —
UnsentVaccinationCubit.load ERROR'`, test `'load() исключение ->
UnsentVaccinationError'` — мокает
`vaccinationsRepository.getNotSyncVaccinationsWithDetails()` на
`thenThrow(Exception('db error'))` и проверяет `cubit.state` через
`isA<UnsentVaccinationError>()`.

## Открытые вопросы и ограничения

- **Существующий тест не проверяет содержимое `message`.** Он утверждает
  только `isA<UnsentVaccinationError>()`, но не `expect((cubit.state as
  UnsentVaccinationError).message, contains('db error'))` — в отличие от
  соседнего теста на `delete()` в том же файле (group `'UC-96'`), который
  такую проверку делает. Формально критерий «`message` — это буквально
  `e.toString()`» верифицирован только чтением кода кубита, не этим тестом.
- **Отсутствие логирования (`Talker`) в этой ветке — осознанное решение
  или недосмотр?** Ничего в коде/комментариях не объясняет, почему
  `catch` в `load()` не логирует исключение, хотя структурно аналогичные
  `catch`-блоки в других частях приложения (например
  `VaccinationBloc._onSave`, [UC-64](UC-64-ACTOR-5-EVT-32-ENT-14-CREATE_ERROR-IN-ANIMAL.md))
  вызывают `getIt<Talker>().handle(e, st)`. При реальном сбое разработчик
  не получит след в логе — только то, что успеет заметить/сообщить
  пользователь.
- **Сырой `e.toString()` в UI — не рассчитан на пользователя.** `ProgressMessage
  .somethingWentWrong` рендерит текст исключения буквально, без перевода
  и без хелпера `showAppSnackBarError`; для реального Drift/платформенного
  исключения пользователь увидит техническую строку, а не понятное
  сообщение об ошибке. Не проверено, является ли это осознанным
  временным решением (debug-режим) или отправленным в прод поведением —
  ничего в коде не различает окружения на этом пути.
- **Нет пути «повторить» без возврата назад.** `UnsentVaccinationError` не
  предлагает кнопку retry — единственный способ заново вызвать `load()`
  — закрыть экран и открыть его заново с `InWorkPage`, что пересоздаёт
  `UnsentVaccinationCubit` целиком.
- **Собственная внутренняя логика `calculateVaccinationStatus`** (может ли
  она сама бросить исключение, зависящее от данных, а не только от сбоя
  соединения с БД) не разбиралась подробно в рамках этого сценария —
  проверена только её сигнатура и точка вызова внутри
  `getNotSyncVaccinationsWithDetails`, не её тело целиком.
