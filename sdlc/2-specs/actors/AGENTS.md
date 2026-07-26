ACTORS naming: `ACTOR-{number}-{NAME}-IN-{MODULE}`

Define each actor's identity, goals, and permissions.

Cite the entities and events this actor interacts with, by id.

Do not list the actor's use-cases. Use-cases are derived after actors, and each
names its actor in its own filename — `../use-cases/` already answers "which
use-cases involve `ACTOR-1`". Recording it here would mean editing a frozen file
every time a new use-case appeared.

## Cross-cutting actors get one home, not one copy per module

Some actors are not specific to any one module — a generic authenticated user,
or a system actor that only ever acts during a sync pass. Define that actor
**once**, under whichever module needed it first; every other module's events
and use-cases just cite that same `ACTOR-{n}` id going forward. Never mint a
second `ACTOR-{n}-SYSTEM-IN-{OTHER-MODULE}` for the same actor — that is the
same fork `../modules/AGENTS.md` warns about for module names, one level up.

The `-IN-{MODULE}` suffix on a cross-cutting actor's id records where it was
first authored, not an exclusivity fence — **for an actor used by one or two
modules beyond its home**, this reading is enough and nothing more needs
checking.

**Refinement for actors used broadly (four or more modules)**: at that scale,
"first authored" starts drifting from "makes sense" — the module that happened
to need the actor first is not necessarily the module whose own business logic
defines what it means to be that actor. When the two diverge, the suffix names
the module that **defines** the actor (its own logic is the actor's
identity — e.g. `AUTH.isAuthorized()` is what "authorized user" *means*), not
the module of first use. Re-point the suffix once, when the gap is found; do
not chase every future addition of a new consuming module.
