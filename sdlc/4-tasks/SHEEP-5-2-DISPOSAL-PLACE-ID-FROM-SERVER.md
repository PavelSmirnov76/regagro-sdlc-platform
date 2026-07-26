- **business task**: `BT-27` ([`../1-business-tasks/planning/BT-27-PLANNING-ANIMAL-DISP-PLACE-ID-FROM-SERVER.md`](../1-business-tasks/planning/BT-27-PLANNING-ANIMAL-DISP-PLACE-ID-FROM-SERVER.md))
- **spec**: `UC-320` ([`../2-specs/use-cases/UC-320-ACTOR-2-EVT-77-ENT-27-READ_OK-IN-ANIMAL.md`](../2-specs/use-cases/UC-320-ACTOR-2-EVT-77-ENT-27-READ_OK-IN-ANIMAL.md), supersedes `UC-159`), `ENT-27`
- **design**: не требуется — правка в repository-слое, UI не меняется напрямую (следствие — календарь снова показывает записи)
- **tracker**: нет подключённого трекера в этой сессии — по `RUNBOOK.md` шаг 6, этот файл является записью учёта

# Заполнять `placeId`/`toPlaceId` выбытия буквально из ответа сервера, убрать обогащение через текущее место животного

## Объём

Единственный файл — `lib/repositories/disposal/disposal_repository.dart`:

- `getReportsFromApiAndSave` — при разборе каждой записи ответа присваивать
  `placeId = Value(json['from_place_id'] as int?)` (новая, эта задача) вместо
  вызова `_enrichWithPlaceId`; `toPlaceId` заполняется автоматически через уже
  существующую в схеме `@JsonKey('to_place_id')`-аннотацию (см. `SHEEP-5-1` —
  колонка добавляется той задачей), отдельного кода не требует.
- `_enrichWithPlaceId` — удалить целиком (единственный вызывающий код).

Полное обоснование — `UC-320`.

## Критерии приёмки (definition of done)

- [ ] После pull записи `placeId` равен `from_place_id` ответа (или `null`, если
      сервер не прислал).
- [ ] После pull `toPlaceId` записи равен `to_place_id` ответа (или `null`).
- [ ] `_enrichWithPlaceId` удалено, `AnimalsDao`/`AnimalsRepository` больше не
      читаются этим методом ради обогащения `placeId`.
- [ ] Выбытие с непустым `from_place_id` отображается в
      `ReportsDayQuery.countDisposals`/day-list для соответствующего места/дня.
- [ ] `flutter test` — зелёный.

## Реализационные заметки

- Тест `test/repositories/disposal_repository_test.dart` не существовал ранее
  (`UC-159` было отмечено TBD) — создать его в рамках этой задачи, по образцу
  `UC-320` (мокать/подавать сырой JSON с `from_place_id`/`to_place_id`,
  проверять итоговые `placeId`/`toPlaceId` на сохранённой записи), не
  ограничиваться проверкой одного лишь `DisposalRepository` через моки
  Dio-ответа целиком.

## Зависимости

Требует колонку `toPlaceId` из `SHEEP-5-1` (DB-миграция); независимо от
остальной части `SHEEP-5-1` (шаги визарда).
