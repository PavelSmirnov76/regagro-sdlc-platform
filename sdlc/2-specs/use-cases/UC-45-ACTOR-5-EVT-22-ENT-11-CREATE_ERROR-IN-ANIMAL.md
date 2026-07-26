# UC-45 — Регистрация нового животного отказывает технически: исключение из `saveAnimal()` перехватывается только в одном из трёх мест, откуда этот метод вызывается

## Назначение

Документирует `ERROR`-исход [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)
(`animal.registered_locally`): пользователь доходит до чекаута визарда
регистрации нового животного, но локальная запись в Drift-БД
(`AnimalsRepository.nextLocalAnimalId` / `AnimalsRepository.insertAnimalWithDetailsCompanion`,
вызываемые из `AnimalRegistrationBloc.saveAnimal`) бросает исключение —
техническая ошибка (диск, повреждение БД, любая другая ошибка `INSERT`,
не связанная с бизнес-валидацией), не бизнес-отказ.

`saveAnimal()` — общий метод, вызываемый из **трёх** разных обработчиков
событий `AnimalRegistrationBloc`, и все три реагируют на одно и то же
исключение по-разному: основной поток этого файла —
`on<AnimalRegistrationEventSave>` (кнопка «Зарегистрировать» на чекауте),
который единственный доводит ошибку до пользователя через снэкбар. Два
других вызова описаны в «Альтернативные потоки» ниже — один вовсе не
перехватывает исключение, второй перехватывает, но недостижим из
реального UI сегодня.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость или авторизованный одинаково; код основного потока не
делает проверки `isAuthorized()` на этой ветке `on<AnimalRegistrationEventSave>`.

## CURRENT

### Основной поток

1. Пользователь проходит визард регистрации нового животного (вызов
   `AnimalRegistrationBloc()` без `editAnimal` — `_editAnimal == null`) до
   шага чекаута (`AnimalRegistrationStep.checkout`,
   `lib/pages/animal_registration/step_pages/checkout_step_page.dart`,
   `CheckoutStepPage`) и нажимает кнопку регистрации: `onTap: onRegister`,
   что в `animal_registration_page.dart` вызывает
   `bloc.add(const AnimalRegistrationEventSave())`.
2. Обработчик `on<AnimalRegistrationEventSave>` в `AnimalRegistrationBloc`:
   так как `_editAnimal == null`, весь блок для случая редактирования
   (`if (_editAnimal != null) { ... }`) пропускается — выполняется ветка
   нового животного:
   ```dart
   try {
     int unsentAnimalId = await saveAnimal();
     emit(AnimalRegistrationExit(unsentAnimalId: unsentAnimalId));
   } catch (e, st) {
     getIt<Talker>().error(
       'при сохранении данных регистрации животного $e, st: $st',
     );
     emit(
       const AnimalRegistrationMessage(
         'Возникла ошибка при сохранении данных',
       ),
     );
   }
   emit(AnimalRegistrationSuccess(_data));
   ```
3. `saveAnimal()` сначала вызывает
   `final localId = await _animalsRepository.nextLocalAnimalId();` —
   Drift-запрос `MIN(id)` среди отрицательных `id`
   (`AnimalsDao.nextLocalAnimalId`). Если этот запрос бросает исключение
   (ошибка диска/повреждение локальной БД — именно эта точка
   замоделирована существующим тестом, см. «Связанные тесты»), исключение
   сразу всплывает из `saveAnimal()`, не дойдя до формирования
   `AnimalsCompanion` и до вызова вставки.
4. Если `nextLocalAnimalId()` завершился успешно, `saveAnimal()`
   продолжает и вызывает
   `_animalsRepository.insertAnimalWithDetailsCompanion(animal: ...,
   animalIdentifications: ...)`, которая делегирует в
   `AnimalsDao.insertAnimalWithDetailsCompanion` — единая Drift-транзакция
   (`db.transaction<int>(...)`): сначала `ins(animal)`, затем (если есть
   хотя бы одна заполненная идентификация) `animalIdentificationsDao.insAll(...)`
   тем же `animalId`. Исключение на любом из двух шагов транзакции
   (constraint violation, ошибка Drift/SQLite и т.п.) откатывает
   транзакцию целиком — ни строка `Animals`, ни строки
   `AnimalIdentifications` не сохраняются частично.
5. В обоих случаях (шаг 3 или шаг 4) исключение долетает до `catch (e, st)`
   обработчика `on<AnimalRegistrationEventSave>` — никакого промежуточного
   `try/catch` внутри `saveAnimal()` самого по себе нет.
6. `catch`-блок логирует через
   `getIt<Talker>().error('при сохранении данных регистрации животного $e, st: $st')`
   и эмитит `AnimalRegistrationMessage('Возникла ошибка при сохранении данных')`
   — жёстко закодированная русская строка, не ключ `.arb`.
7. Безусловно, вне зависимости от исхода `try/catch`, обработчик следом
   эмитит `AnimalRegistrationSuccess(_data)` — тот же `_data`, что был до
   попытки сохранения: введённые пользователем значения полей визарда не
   сбрасываются и не теряются. `AnimalRegistrationExit` в этой ветке не
   эмитится вовсе — визард не закрывается.
8. В `animal_registration_page.dart` `BlocConsumer<AnimalRegistrationBloc,
   AnimalRegistrationState>.listener` реагирует на
   `AnimalRegistrationMessage`:
   ```dart
   ScaffoldMessenger.of(context).showSnackBar(
     SnackBar(content: Text(AppLocalizations.of(context)!.tr(state.message))),
   );
   ```
   `AppLocalizations.tr` (`lib/l10n/app_localization.dart`) прогоняет
   переданную строку через `switch`; строка
   `'Возникла ошибка при сохранении данных'` ни под один `case` не
   попадает и уходит в `default: return key;` — метод возвращает саму
   строку без перевода. Снэкбар на практике показывает корректный русский
   текст в любой локали приложения, но не потому что это переведённый
   ключ, а потому что «ключ» уже и есть готовый текст.
9. Пользователь остаётся на экране чекаута (`AnimalRegistrationSuccess`),
   видит снэкбар с сообщением об ошибке и может повторно нажать кнопку
   регистрации — данные визарда для повтора не потеряны.

### Альтернативные потоки

- **`AnimalRegistrationEventSaveAndAddAnother` — тот же `saveAnimal()`
  вызван без `try/catch` вовсе.**
  ```dart
  on<AnimalRegistrationEventSaveAndAddAnother>((event, emit) async {
    // Сначала сохраняем животное
    await saveAnimal();

    // Сбрасываем некоторые данные (оставляем вид, породу и другую базовую информацию)
    _data = _data.copyWithWrapped(
      gender: const Wrapped(null),
      birthDate: const Wrapped(null),
      animalIdentifications: Wrapped(List.empty()),
      name: const Wrapped(null),
      parents: const Wrapped(null),
    );

    emit(AnimalRegistrationSuccess(_data));
  });
  ```
  Если `saveAnimal()` бросает то же самое исключение (шаг 3 или 4
  основного потока), оно не перехватывается этим обработчиком вообще —
  строка сброса полей и `emit(AnimalRegistrationSuccess(_data))` не
  выполняются, обработчик завершается необработанным исключением. В
  приложении зарегистрирован единственный глобальный `Bloc.observer =
  TalkerBlocObserver(...)` (`lib/injection_container.dart`) — по
  документированному поведению `flutter_bloc`, исключение внутри
  `on<Event>`-обработчика перехватывается самим `Bloc` и передаётся в
  `onError`/`BlocObserver.onError`, не приводя к падению приложения, но и
  не порождая **ни одного** состояния для этого `add()` — ни
  `AnimalRegistrationMessage`, ни `AnimalRegistrationSuccess`, ни
  `AnimalRegistrationExit`. Пользователь не получает вообще никакой
  видимой реакции на нажатие «Сохранить и добавить другое» (кроме лога,
  видимого только через `Talker`); это не проверено эмпирически запуском
  реального сценария, только чтением кода `flutter_bloc` и его
  документированной семантики.
- **`AnimalRegistrationEventSaveWithoutIdentifier` — тот же `saveAnimal()`,
  перехвачен, но иначе, и недостижим из UI.**
  ```dart
  on<AnimalRegistrationEventSaveWithoutIdentifier>((event, emit) async {
    emit(AnimalRegistrationSendingToServer(_data));
    try {
      final unsentAnimalId = await saveAnimal();
      emit(AnimalRegistrationExit(unsentAnimalId: unsentAnimalId));
    } catch (e, st) {
      getIt<Talker>().error(
        'при сохранении животного без идентификатора $e, st: $st',
      );
      _data = _data.copyWithWrapped(
        error: Wrapped(e.toString().replaceFirst('Exception: ', '')),
      );
      emit(AnimalRegistrationSuccess(_data));
    }
  });
  ```
  При том же исключении этот обработчик логирует через `Talker`, кладёт
  текст ошибки в `_data.error` (без префикса `'Exception: '`) и эмитит
  `AnimalRegistrationSuccess(_data)` — **не** эмитит
  `AnimalRegistrationMessage`, снэкбара не будет. `_data.error` читается
  только `AdditionalInformationStepPage` (`error: data.error` в
  `animal_registration_page.dart`) — шаг «Дополнительная информация», не
  шаг чекаута, откуда фактически вызывается сохранение. Ещё важнее:
  `AnimalRegistrationEventSaveWithoutIdentifier` **не диспатчится ни из
  одного экрана** — проверено `grep` по всему `lib/`: единственные
  упоминания класса — его собственное определение в
  `animal_registration_event.dart` и регистрация обработчика в
  `animal_registration_bloc.dart`; единственный вызов `.add(...)` этого
  события во всём репозитории — в
  `test/pages/animal_registration_bloc_test.dart`. Комментарий над классом
  события («Сохранение животного локально без идентификатора (для
  неавторизованных пользователей)») описывает намерение, для которого в
  текущем UI нет кнопки/триггера — этот путь как CURRENT-поведение
  реального пользователя не воспроизводим, только программным вызовом
  события (в т.ч. тестом).
- **Ветка `_editAnimal != null` того же обработчика `on<AnimalRegistrationEventSave>`
  не входит в этот сценарий.** Если открыть визард с `editAnimal` (правка,
  не создание), выполняется другая ветка (`_isEditingLocalAnimal` /
  `_animalsRepository.updateAnimal`) — она относится к
  [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md)/[EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md),
  не к [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md), и не
  документируется этим файлом.
- **`CREATE_OK`-исход того же обработчика не входит в этот сценарий.** Если
  оба вызова (`nextLocalAnimalId`, `insertAnimalWithDetailsCompanion`)
  завершаются успешно, обработчик эмитит `AnimalRegistrationExit` внутри
  `try` — соседний исход того же [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md),
  не документируемый здесь.

### Связанные сущности

- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — целевая
  сущность попытки создания; ни в основном потоке, ни в альтернативном
  потоке `SaveAndAddAnother` строка не появляется в БД при исключении
  (транзакция откатывается целиком либо исключение происходит до входа в
  неё). Поле `Animal.errors` в этом сценарии не используется — оно
  предназначено для серверных ошибок по полям после попытки синхронизации
  ([EVT-25](../events/EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md)), а не
  для локальных технических сбоев на этапе первичного сохранения; текст
  ошибки в этом сценарии живёт только в состоянии bloc'а
  (`AnimalRegistrationMessage`/`_data.error`), не персистится.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — пишется в той же Drift-транзакции, что и
  `Animal` (`AnimalsDao.insertAnimalWithDetailsCompanion`); откатывается
  вместе с ней при исключении. Если исключение произошло раньше, на шаге
  `nextLocalAnimalId()`, до транзакции дело вообще не доходит — собранные
  к этому моменту `AnimalIdentificationsCompanion` просто отбрасываются
  как обычные объекты в памяти, ни одного обращения к БД для них не было.

### Бизнес-правила

- Технический сбой (исключение из Drift/DAO) классифицируется как
  `CREATE_ERROR`, а не `CREATE_REJECTED` — отказ никогда не доходит до
  пользователя как осознанно предъявленное бизнес-решение, это чистая
  техническая ошибка слоя хранения.
- Единая Drift-транзакция (`db.transaction<int>(...)` в
  `AnimalsDao.insertAnimalWithDetailsCompanion`) гарантирует отсутствие
  частично сохранённого животного: либо `Animal` и все заполненные
  `AnimalIdentification` зафиксированы вместе, либо ни одна строка не
  появляется.
- Один и тот же вызов `saveAnimal()` из трёх разных обработчиков одного
  bloc'а обрабатывает идентичное исключение тремя разными способами: (а)
  `on<AnimalRegistrationEventSave>` (этот use-case) — снэкбар
  `AnimalRegistrationMessage` + откат в `AnimalRegistrationSuccess` без
  потери данных формы; (б) `on<AnimalRegistrationEventSaveAndAddAnother>`
  — исключение вообще не перехватывается, никакого состояния не
  эмитируется; (в) `on<AnimalRegistrationEventSaveWithoutIdentifier>` —
  перехватывается, но текст кладётся в `_data.error` вместо снэкбара, при
  этом сам путь недостижим из реального UI.
- Локальный `id`, вычисленный `nextLocalAnimalId()` до момента сбоя (если
  исключение произошло уже внутри `insertAnimalWithDetailsCompanion`, то
  есть после того как `localId` уже был получен), нигде не резервируется
  и не сохраняется — так как строка `Animal` не создаётся (транзакция
  откатывается), следующий вызов `nextLocalAnimalId()` на повторной
  попытке пересчитает тот же (или столь же отрицательный) `id` заново,
  коллизий это не создаёт.
- При ошибке в основном потоке `_data` не сбрасывается — пользователь
  может повторить попытку сохранения без повторного прохождения визарда.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — основной поток и оба альтернативных пути перехвата/отсутствия
перехвата полностью прослеживаются чтением
`lib/pages/animal_registration/animal_registration_bloc.dart`,
`lib/pages/animal_registration/animal_registration_page.dart`,
`lib/repositories/animal/animals_repository.dart`,
`packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` и
`lib/l10n/app_localization.dart`. Недостижимость
`AnimalRegistrationEventSaveWithoutIdentifier` из UI перепроверена `grep`
по всему `lib/`, а не восстановлена по памяти. Поведение `flutter_bloc`
при необработанном исключении внутри `on<Event>` (ветка
`SaveAndAddAnother`) — установлено по документированной семантике
пакета, не подтверждено отдельным эмпирическим запуском именно этого
сценария в этом репозитории (см. «Открытые вопросы»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventSave>` (ветка `_editAnimal == null`) | CURRENT | перехватывает исключение `saveAnimal()`, эмитит `AnimalRegistrationMessage`, затем безусловно `AnimalRegistrationSuccess`; `AnimalRegistrationExit` не эмитится |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.saveAnimal` | CURRENT | вызывает `nextLocalAnimalId()` и `insertAnimalWithDetailsCompanion()` — источник исключения для всех трёх обработчиков |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventSaveAndAddAnother>` | CURRENT | вызывает `saveAnimal()` без `try/catch` — исключение не перехватывается вообще (альт. поток) |
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc.on<AnimalRegistrationEventSaveWithoutIdentifier>` | CURRENT | тот же `try/catch`-паттерн, но кладёт текст ошибки в `_data.error` вместо снэкбара; событие не диспатчится ни из одного экрана `lib/` (альт. поток, недостижим) |
| `lib/pages/animal_registration/animal_registration_event.dart` | `AnimalRegistrationEventSave`, `AnimalRegistrationEventSaveAndAddAnother`, `AnimalRegistrationEventSaveWithoutIdentifier` | CURRENT | три события, ведущие к одному и тому же `saveAnimal()` |
| `lib/pages/animal_registration/animal_registration_state.dart` | `AnimalRegistrationMessage`, `AnimalRegistrationSuccess`, `AnimalRegistrationExit`, `AnimalRegistrationSendingToServer` | CURRENT | состояния, участвующие в трёх путях |
| `lib/pages/animal_registration/animal_registration_page.dart` | `CheckoutStepPage.onRegister`, `BlocConsumer<AnimalRegistrationBloc, AnimalRegistrationState>.listener` | CURRENT | UI-триггер основного потока (`onRegister` → `AnimalRegistrationEventSave()`) и обработка `AnimalRegistrationMessage` через `ScaffoldMessenger`/`SnackBar` |
| `lib/pages/animal_registration/animal_registration_page.dart` | `AdditionalInformationStepPage` (`error: data.error`) | CURRENT | единственное место, читающее `_data.error` — шаг «Дополнительная информация», не шаг чекаута |
| `lib/l10n/app_localization.dart` | `AppLocalizations.tr` | CURRENT | `default: return key;` — нелокализованный fallback, из-за которого хардкод-строка отображается как есть |
| `lib/repositories/animal/animals_repository.dart` | `AnimalsRepository.nextLocalAnimalId`, `AnimalsRepository.insertAnimalWithDetailsCompanion` | CURRENT | тонкие обёртки над DAO, сами исключение не перехватывают |
| `packages/sheep_farm_database/lib/entities/animal/animals_dao.dart` | `AnimalsDao.nextLocalAnimalId`, `AnimalsDao.insertAnimalWithDetailsCompanion` | CURRENT | источник технического исключения; вторая — единая Drift-транзакция (`Animals` + `AnimalIdentifications`) |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | глобальный `BlocObserver` — единственная точка, куда долетает необработанное исключение из ветки `SaveAndAddAnother` (логирование, не пользовательская обратная связь) |

## Критерии приёмки

- При исключении из `nextLocalAnimalId()` или
  `insertAnimalWithDetailsCompanion()` внутри `saveAnimal()`, вызванного
  из `on<AnimalRegistrationEventSave>` (ветка нового животного), bloc
  эмитит ровно `[AnimalRegistrationMessage('Возникла ошибка при
  сохранении данных'), isA<AnimalRegistrationSuccess>()]` — без
  `AnimalRegistrationExit`.
- Ни строка `Animals`, ни строки `AnimalIdentifications` не сохраняются в
  локальной БД при этом исключении, независимо от того, произошло ли оно
  до входа в транзакцию (`nextLocalAnimalId`) или внутри неё
  (`insertAnimalWithDetailsCompanion`).
- `_data` в финальном `AnimalRegistrationSuccess` идентичен `_data` до
  попытки сохранения.
- Тот же вызов `saveAnimal()` из `on<AnimalRegistrationEventSaveAndAddAnother>`
  при том же исключении не эмитит ни одного состояния для этого `add()` —
  обработчик завершается необработанным исключением, видимым только через
  `TalkerBlocObserver`.
- Тот же вызов из `on<AnimalRegistrationEventSaveWithoutIdentifier>` при
  том же исключении эмитит `AnimalRegistrationSuccess` с `_data.error`,
  заполненным текстом исключения (без префикса `'Exception: '`), но не
  эмитит `AnimalRegistrationMessage`; на практике этот путь не достижим ни
  с одного экрана приложения сегодня.

## Связанные тесты

- `test/pages/animal_registration_bloc_test.dart`, group `'UC-44/UC-45 — AnimalRegistrationEventSave — новое животное'`, test `'ошибка сохранения ->
  AnimalRegistrationMessage, затем откат в Success'` — прямое покрытие
  основного потока: `animalsRepository.nextLocalAnimalId()` замокан на
  `thenThrow(Exception('db error'))`, ожидается
  `[const AnimalRegistrationMessage('Возникла ошибка при сохранении данных'),
  isA<AnimalRegistrationSuccess>()]`.
- `test/pages/animal_registration_bloc_test.dart`, group `'UC-54 —
  AnimalRegistrationEventSaveWithoutIdentifier'` — единственный тест
  группы покрывает только успешный путь (гость без идентификатора,
  `insertAnimalWithDetailsCompanion` отвечает успешно, ожидается
  `AnimalRegistrationSendingToServer` → `AnimalRegistrationExit`).
  **TBD — теста нет** на ошибочную ветку этого обработчика (исключение из
  `saveAnimal()` внутри `SaveWithoutIdentifier`, приводящее к
  `_data.error`).
- `test/pages/animal_registration_bloc_test.dart`, group
  `'AnimalRegistrationEventSaveAndAddAnother'` — единственный тест группы
  тоже покрывает только успешный путь (сохранение + сброс части полей).
  **TBD — теста нет** на исключение из `saveAnimal()` в этой ветке — в
  коде нет `try/catch`, поэтому такой тест мог бы проверить только сам
  факт, что исключение действительно всплывает наружу необработанным
  (`throwsA(...)` на уровне `bloc.add`/стрима), а не какой-либо
  пользовательский исход.

## Открытые вопросы и ограничения

- **Три разных обработчика одного bloc'а по-разному реагируют на одно и
  то же исключение `saveAnimal()`.** Ничего в коде/комментариях не
  фиксирует, было ли это осознанным решением (например: «сохранение без
  снэкбара — временная заглушка для ещё не подключённого потока») или
  случайным расхождением, возникшим по мере добавления новых событий
  поверх уже существующего `saveAnimal()`.
- **`AnimalRegistrationEventSaveWithoutIdentifier` — код без UI-триггера.**
  Проверено `grep` по всему `lib/`: событие определено, обработчик
  зарегистрирован, есть модульный тест, но ни одна кнопка/действие не
  диспатчит его. Останется ли это намеренной точкой расширения для
  будущего гостевого потока или это устаревший, никогда не подключённый
  код — не зафиксировано.
- **Необработанное исключение в `on<AnimalRegistrationEventSaveAndAddAnother>`
  не подтверждено эмпирически.** Вывод о том, что `flutter_bloc`
  перехватывает такое исключение на уровне самого `Bloc` (через
  `onError`/`BlocObserver.onError`), не порождая пользовательского
  состояния и не роняя приложение, сделан по документированной семантике
  пакета, а не запуском конкретного сценария в этом репозитории (в
  отличие, например, от проверки семантики `async`-функций в
  [UC-22](UC-22-ACTOR-1-EVT-10-ENT-9-CREATE_ERROR-IN-FARM.md), где
  утверждение было дополнительно перепроверено минимальным запускаемым
  примером).
- **Снэкбар основного потока «переведён» только по совпадению.**
  `AnimalRegistrationMessage('Возникла ошибка при сохранении данных')`
  проходит через `AppLocalizations.tr(...)`, но это не ключ `.arb`, а уже
  готовый русский текст; `tr()` возвращает его как есть по `default:
  return key;`. Сообщение отображается корректно сегодня только потому,
  что оно уже написано на языке интерфейса по умолчанию — оно не будет
  переведено, если/когда язык интерфейса переключат на любой другой.
- **`_data.error` (ветка `SaveWithoutIdentifier`) отображается не на том
  шаге, где вызывается сохранение.** Поле читается только
  `AdditionalInformationStepPage` — даже если бы этот путь стал достижим
  из UI, пользователь, находящийся на шаге чекаута в момент вызова
  `AnimalRegistrationEventSaveWithoutIdentifier`, не увидел бы текст
  ошибки без перехода на другой шаг визарда.
