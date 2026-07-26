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
| [MOD-1](MOD-1-AUTH.md) | [BT-1](../../1-business-tasks/planning/BT-1-PLANNING-AUTH.md) | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md), [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) | [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)…[EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md) |
| [MOD-2](MOD-2-HANDBOOKS.md) | [BT-2](../../1-business-tasks/planning/BT-2-PLANNING-HANDBOOKS.md) | нет своих — синк справочников инициирует [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md), см. SYSTEM | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)…[ENT-8](../entities/ENT-8-MISC-DIRECTORIES-IN-HANDBOOKS.md) | нет своих — см. [MOD-7](MOD-7-SYSTEM.md) ([EVT-96](../events/EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md)) |
| [MOD-3](MOD-3-FARM.md) | [BT-3](../../1-business-tasks/planning/BT-3-PLANNING-FARM.md) | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) | [EVT-10](../events/EVT-10-FARM-CREATED-IN-FARM.md)…[EVT-21](../events/EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md) |
| [MOD-4](MOD-4-ANIMAL.md) | [BT-4](../../1-business-tasks/planning/BT-4-PLANNING-ANIMAL-REG.md)…[BT-10](../../1-business-tasks/planning/BT-10-PLANNING-ANIMAL-INV.md) (по одной BT на под-область — REG/MOVE/VAC/WEIGH/DISP/REPRO/INV) | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md)…[ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) (REPRO не завело своей — поля на ENT-11) | [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md)…[EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) — модуль закрыт целиком |
| [MOD-5](MOD-5-BOARD.md) | [BT-11](../../1-business-tasks/planning/BT-11-PLANNING-BOARD.md) | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) (все три переиспользованы) | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md), [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md), [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) | [EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md)…[EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) |
| [MOD-6](MOD-6-PROFILE.md) | [BT-12](../../1-business-tasks/planning/BT-12-PLANNING-PROFILE.md) | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) (обе переиспользованы) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md), [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (переиспользованы, узкие грани), [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md), [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) | [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md)…[EVT-92](../events/EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) |
| [MOD-7](MOD-7-SYSTEM.md) | [BT-13](../../1-business-tasks/planning/BT-13-PLANNING-SYSTEM.md) | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md), [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md), [ACTOR-4](../actors/ACTOR-4-SYSTEM-IN-SYSTEM.md) (все три переиспользованы) | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md), [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) | [EVT-93](../events/EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md)…[EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md) — последний модуль, `2-specs/` закрыт целиком |
