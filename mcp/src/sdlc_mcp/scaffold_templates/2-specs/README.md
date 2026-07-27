# 2 — Specs

Detailed specifications expanding the planning tasks from
`../1-business-tasks/planning/` — **how it should work**. A spec is the source
of truth an implementation is validated against.

An item leaves this stage when its design components are built in `../3-design/`.

## Structure
Specs are organized by concern. Each subfolder's `AGENTS.md` carries its own
naming scheme; [`AGENTS.md`](AGENTS.md) here holds only what applies across all
of them.

- `actors/` — who/what interacts with the system. The **who**. (`ACTOR-{n}-NAME`)
- `entities/` — domain objects and their data. The **what it's made of**. (`ENT-{n}-NAME`)
- `events/` — things that happen. The **what happens**. (`EVT-{n}-NAME`)
- `modules/` — functional units that compose actors, entities, and events into
  behavior. The **how it fits together**.
- `use-cases/` — end-to-end scenarios tying an actor + event + entity to a
  result. (`UC-{n}-ACTOR-{n}-EVT-{n}-ENT-{n}-RESULT`)

## Current specs

> Fill in once specs exist. Keep this table as the audit trail from a PRD
> requirement, through the planning task that carried it, to the module that
> implements it.

### Traceability: planning task → module
| PT | Module | PRD |
|----|--------|-----|
|    |        |     |

Each subfolder's README carries the full index of its own artifacts.

## Each spec should cover
- Link back to its source task
- Behavior & user flows
- Data / API contracts
- Edge cases
- Acceptance tests
