USE-CASES naming:
`UC-{number}-ACTOR-{number}-EVT-{number}-ENT-{number}-{RESULT}-IN-{MODULE}`

The filename carries the derivation: primary actor, trigger event, primary
entity, outcome. A directory listing alone tells you who did what to which
entity, and how it ended.

Every id named in the filename must already exist — a use-case cannot invent its
actor, event, or entity, and must resolve each to a live artifact before citing
it.

The ids in the filename record what this use-case was **derived from**. They are
frozen with the name. If one of them is later entombed, this filename stays as
written: it is provenance, not a live pointer.

## RESULT is a closed vocabulary, not free text

`RESULT = {CRUD}_{OUTCOME}`. `CRUD ⊂ {CREATE, READ, UPDATE, DELETE}`,
`OUTCOME ⊂ {OK, ERROR, REJECTED}`. Every use-case carries a real verb — never
a bare outcome with no CRUD prefix, even when the scenario looks like "just an
error." `REJECTED` means the operation reached its recipient and was
consciously declined by a business rule; `ERROR` means it never reached it
(network failure, exception, crash). This is closed deliberately — resist the
pull toward a free-text `RESULT` like `SESSION-ESTABLISHED`; a closed
vocabulary stays greppable across the whole corpus and surfaces real defects
that free text would hide (a missing branch shows up as a missing file, not a
prose difference).

## Sync is not a CRUD verb

A system actor replaying a locally-originated mutation during a sync pass is
still `CREATE_OK` / `UPDATE_OK` / `DELETE_OK` — never `SYNC_OK` or a
`SYNC-`-prefixed pseudo-verb. `ACTOR-{n}-SYSTEM` in the use-case id already
carries "this happened during a sync pass"; inventing a parallel verb for the
same fact duplicates information the id already states. It is still a
**different event** than the human-triggered original, though — see
`../events/AGENTS.md`.

## Required sections

`Назначение`, `Пользователь`, `CURRENT` (`Основной поток` / `Альтернативные
потоки` / `Связанные сущности` / `Бизнес-правила`), `TARGET`, `TBD / BLOCKED`,
`Технические зависимости`, `Критерии приёмки`, `Связанные тесты`, `Открытые
вопросы и ограничения`.

- **CURRENT** — how the scenario behaves in code today. Every claim checked
  against code, not assumed. If the scenario doesn't exist yet, one line: "не
  существует, сценарий новый" — expand in `TARGET` instead.
- **TARGET** — new or changed behavior. If it doesn't differ from `CURRENT`,
  one line saying so — never duplicate the text.
- **Связанные сущности** lists every entity the scenario touches, not just the
  one in the `ENT` segment of the id (that segment names whichever entity's
  state machine actually transitions here — a movement transitions
  `Movement`, not `Animal`, even though it also writes `Animal.placeId`;
  `Animal` still belongs in this section).
- **Технические зависимости** is this artifact type's version of the
  source-code table (see `../entities/AGENTS.md`) — same discipline, paths
  verified by reading, not memory.

## Tests link back by self-naming, not by hoping a doc stays in sync

A use-case's "Связанные тесты" section is a mechanical anchor, not a promise
someone remembers to update it: the test names its own use-case id in a
`group('UC-{id} — …')` (or a leading comment, for a bare `test(...)`), so the
link is always recoverable with `grep -r "UC-{id}" test/` even if this file's
prose goes stale. When writing or reviewing a test for a scenario that has a
spec, add the anchor in the same pass — don't leave it TBD if the test already
exists. If no test exists yet, say so plainly — "TBD — теста нет" is a
complete, correct answer.
