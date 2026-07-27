# Modules

Functional units that compose actors, entities, and events into behavior — the
**how it fits together**.

A module is the unit a planning business task maps onto. Its name is the key the
rest of `2-specs/` is built around: it becomes the `-IN-{MODULE}` suffix on every
actor, entity, event, and use-case id, so a farmer in the auth module is
`ACTOR-1-FARMER-IN-AUTH`.

An item leaves this folder when the actors, entities, and events it names exist
in their own folders.

## Why the name carries weight

Because that name is copied into every spec id, an inconsistent name forks the
whole graph silently. Modules are therefore defined first, named from the PRD's
own vocabulary, and frozen — the naming discipline is in [`AGENTS.md`](AGENTS.md).

## Index
| Module | Source BT | Actors | Entities | Events |
|--------|-----------|--------|----------|--------|
|        |           |        |          |        |
