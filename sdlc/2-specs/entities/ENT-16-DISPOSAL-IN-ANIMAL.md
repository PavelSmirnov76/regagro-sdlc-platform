# ENT-16 — Disposal

## Описание

Запись о выбытии одного животного — Drift-таблица `Disposals`. Одна запись на одно животное (групповое выбытие нескольких животных создаёт по одной строке на каждое, не одну групповую запись — тот же паттерн, что у [ENT-13](ENT-13-MOVEMENT-IN-ANIMAL.md)/[ENT-14](ENT-14-VACCINATION-IN-ANIMAL.md)). Отдельный сценарий той же формы — «перемещение между фермами одного владельца» — использует ту же таблицу, различаясь только заполненными `toId`/`toPlaceId` и жёстко закодированным id причины.

## Поля

| Поле | Тип | Комментарий |
|---|---|---|
| `id` | int?, autoincrement | локальный id |
| `guid` | text? | генерируется на клиенте при создании (`Uuid().v4()`) |
| `remoteId` | int? | серверный id — заполняется только для записей, загруженных с сервера |
| `userId` | int? | пользователь, создавший запись; `-1` при отсутствии авторизации |
| `animalId` | int? | ссылка на [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) |
| `placeId` | int? | место, из которого выбыло животное |
| `causeId` | int? | ссылка на причину выбытия ([ENT-5](ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md), HANDBOOKS) |
| `date` | DateTime? | дата выбытия |
| `createdAt` | DateTime? | |
| `updatedAt` | DateTime? | |
| `deletedAt` | DateTime? | заполняется только сервером в ответе (`deleted_at`), локально этой под-областью не используется |
| `fromId` | int? | ферма отправления (`remoteId` фермы) — для сценария «между фермами» |
| `toId` | int? | целевая ферма (только для сценария «между фермами», причина `causeId == 4`) |
| `toPlaceId` | int? | целевое место (только для сценария «между фермами») |
| `sync` | bool?, default false | признак отправки на сервер — единственный флаг состояния, как у [ENT-15](ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) (AnimalWeighing); нет отдельных `pending_edit`/`pending_delete`-признаков |

## Связи

- [ENT-11](ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — многие-к-одному по `animalId`. **Важный кросс-модульный инвариант**: создание Disposal НЕ помечает животное выбывшим локально — поля `disposed`/`deletedAt` на самом Animal заполняются только при следующей полной перезагрузке животных с сервера (см. `.claude/rules/domain-model.md`, инвариант 6).
- [ENT-5](ENT-5-DISPOSAL-REASON-IN-HANDBOOKS.md) (DisposalReason, HANDBOOKS) — причина выбытия; id `4` («между фермами одного владельца») жёстко закодирован в `AnimalDisposalData.betweenFarmsReasonId` и переключает форму на сценарий с выбором целевой фермы/места.
- [ENT-9](ENT-9-FARM-IN-FARM.md) (Farm, FARM) — `fromId`/`toId` ссылаются на фермы по `remoteId`, не изменяются этой под-областью.
- [ENT-10](ENT-10-PLACE-IN-FARM.md) (Place, FARM) — `placeId`/`toPlaceId` ссылаются на места, не изменяются этой под-областью.

## Инварианты

- **Нет мягкого удаления уже синхронизированной записи.** В отличие от Vaccination, здесь нет отдельного признака «помечено на удаление» — `sync` (bool) единственный флаг состояния, и он используется только для «ещё не отправлено» (`false`) vs «отправлено» (`true`). Отменить уже синхронизированное выбытие (например, ошибочно созданное) этим кодом невозможно в принципе — не просто недостижимо из UI, а отсутствует как концепция.
- **Отмена (удаление) ещё не отправленной записи — обычное «жёсткое» удаление**, доступное двумя независимо написанными путями (хаб «В работе» и экран дневного отчёта), как и у Movement.
- **Push отправляет батчами, сгруппированными по причине/месту отправления/целевому месту/минуте времени**, не по одной записи и не всё одним запросом — `_groupForSend` группирует по составному ключу `causeId_placeId_toPlaceId_timeKey` (минутная точность), animalIds батча передаются одним списком на группу.
- **Push и pull — последовательные шаги без собственной оркестрирующей защиты от сбоя**: `syncDisposals()` — `await sendDisposalsToApi(); await getReportsFromApiAndSave();` без try/catch на этом уровне. `sendDisposalsToApi` ловит исключение только для логирования и **пробрасывает его дальше** (`rethrow`) — если push отказал, `getReportsFromApiAndSave()` не вызывается вовсе в этом же проходе.
- **Pull перезаписывает локальную таблицу целиком, но только если сервер вернул непустой список** — `if (disposals.isNotEmpty) { dao.clear(); dao.insAll(...); }`, тот же паттерн, что у Movement (Vaccination и Weighing отличаются — там `clear()` безусловен).
- **При замене локального id животного на серверный связанные ещё не синхронизированные записи `Disposal` каскадно обновляются** — `DisposalRepository.changeIdUnsentAnimalFromUnsentDisposalList`, вызывается из `AnimalsRepository.updateAnimalId`.

## Исходный код

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `packages/sheep_farm_database/lib/entities/disposal/disposal.dart` | `Disposals`, `DisposalExtension.fromJsonRint` | CURRENT | таблица, конвертация ответа сервера |
| `lib/repositories/disposal/disposal_repository.dart` | `DisposalRepository.syncDisposals`, `sendDisposalsToApi`, `getReportsFromApiAndSave`, `_groupForSend`, `changeIdUnsentAnimalFromUnsentDisposalList` | CURRENT | push (батч по группам), pull, каскадное обновление `animalId` |
| `lib/pages/animal_disposal/animal_disposal_bloc.dart` | `AnimalDisposalBloc`, `AnimalDisposalData.betweenFarmsReasonId` | CURRENT | визард создания выбытия, включая сценарий «между фермами» |
