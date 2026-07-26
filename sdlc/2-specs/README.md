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
| [BT-1](../1-business-tasks/planning/BT-1-PLANNING-AUTH.md) | [MOD-1](modules/MOD-1-AUTH.md) | [R12](../0-vibes/prd/PRD.md), [R13](../0-vibes/prd/PRD.md), [R14](../0-vibes/prd/PRD.md), [R15](../0-vibes/prd/PRD.md), [R16](../0-vibes/prd/PRD.md), [R17](../0-vibes/prd/PRD.md), [R18](../0-vibes/prd/PRD.md) |
| [BT-2](../1-business-tasks/planning/BT-2-PLANNING-HANDBOOKS.md) | [MOD-2](modules/MOD-2-HANDBOOKS.md) | [R71](../0-vibes/prd/PRD.md), [R72](../0-vibes/prd/PRD.md) |
| [BT-3](../1-business-tasks/planning/BT-3-PLANNING-FARM.md) | [MOD-3](modules/MOD-3-FARM.md) | [R1](../0-vibes/prd/PRD.md)–[R11](../0-vibes/prd/PRD.md) |
| [BT-4](../1-business-tasks/planning/BT-4-PLANNING-ANIMAL-REG.md) | [MOD-4](modules/MOD-4-ANIMAL.md) (REG) | [R19](../0-vibes/prd/PRD.md)–[R24](../0-vibes/prd/PRD.md) |
| [BT-5](../1-business-tasks/planning/BT-5-PLANNING-ANIMAL-MOVE.md) | [MOD-4](modules/MOD-4-ANIMAL.md) (MOVE) | [R25](../0-vibes/prd/PRD.md)–[R27](../0-vibes/prd/PRD.md) |

Each subfolder's README carries the full index of its own artifacts.

## Each spec should cover
- Link back to its source task
- Behavior & user flows
- Data / API contracts
- Edge cases
- Acceptance tests
