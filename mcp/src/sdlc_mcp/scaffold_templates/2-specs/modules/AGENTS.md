MODULES naming: `MOD-{number}-{NAME}.md`

A module is the unit a planning business task (`BT-{number}-PLANNING-…`) maps
onto, and — through its `{NAME}` — the `-IN-{MODULE}` suffix on every actor,
entity, event, and use-case id in the tree. That makes `{NAME}` the single
most-copied string in the spec graph, so it is not free text.

## The name is a key. Discipline it.

`AUTH` in one id and `Authentication` in another belong to the same module and
nothing knows it — the graph forks and every `-IN-…` downstream inherits the
fork. To prevent that, `{NAME}` is:

- **One UPPERCASE token, no hyphens.** Hyphens delimit the id
  (`ACTOR-1-FARMER-IN-AUTH`), so a hyphen inside a name breaks parsing. `AUTH`,
  never `auth`, `Auth`, or `auth-service`.
- **A domain-area noun** — the part of the product this module owns. Not a
  technical layer (`BILLING`, not `CONTROLLERS`) and not a single action
  (`CHECKOUT` the area, not `ADD-COUPON` the deed).
- **Unique across all modules.** The name is the suffix key; two modules sharing
  a name is the same fork by another route.
- **Taken from the PRD and business-task vocabulary**, not coined here. If the
  PRD calls it "the ledger", the module is `LEDGER` — so the word a stakeholder
  used survives all the way into the spec ids.

## The name is frozen with the id

Once allocated, `{NAME}` never changes — every `-IN-{NAME}` in the tree is
pinned to it. A module whose meaning changes is entombed and a new `MOD-{n}`
issued under a new name; the old name is never repurposed and never edited in
place.

## Define modules before any other spec

Every other spec names its module inside its own frozen id, so a module invented
after the fact leaves those ids pointing at nothing. Before writing `-IN-AUTH`,
resolve it: a `MOD-*-AUTH.md` must already exist. `-IN-{MODULE}` everywhere in
`2-specs/` means exactly this name.

## Each module states

- the actors, entities, and events it owns
- its boundary — what it explicitly does not own

## Example names

Illustrative, not a fixed taxonomy — replace with this project's own domains:

`AUTH` · `BILLING` · `CATALOG` · `SEARCH` · `NOTIFY` · `PROFILE` · `LEDGER` ·
`INVENTORY`
