# Observation

The listening half of stage 1: signals gathered from the running system,
users, and operations that feed planning. Observations are triaged by severity.

## Structure
- `errors/` — things that are broken and demand action.
- `warnings/` — risks and degradations worth attention before they become errors.
- `infos/` — neutral signals, metrics, and notes for context.

Observations feed `../planning/`, which shapes them into plans and priorities.

Naming conventions in [`AGENTS.md`](AGENTS.md).
