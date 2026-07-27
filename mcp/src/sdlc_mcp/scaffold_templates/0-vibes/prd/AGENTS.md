# PRD

`PRD.md` is the only PRD. One per project, one file, that exact name. It is the
single mutable artifact in the pipeline — everything downstream is frozen, and
this is where change enters.

## Requirements are the interface

Every artifact in this tree traces upstream to an `R{n}` here. Planning tasks
cite them, specs expand them, eval validates against them. They are the atom the
whole pipeline is built on, so they carry its strictest rules.

- **Number every requirement `R{n}`.** One requirement per number. Never a
  compound — "R4: users can log in and reset passwords" is two requirements
  wearing one id, and half of it can never be deprecated on its own.
- **Each is atomic and realizable as use-cases.** Nothing tests a requirement
  directly — `6-eval/` tests the use-cases that realize it, and a requirement is
  satisfied only through them. So the bar is: can a concrete use-case be derived
  from this, with an actor, a trigger, and an outcome someone can check? "The
  system should be fast" yields none. "Search returns in under 200ms at p95"
  yields one.
- **`R{n}` is permanent.** Never renumbered, never reused, never reworded. The
  next id is one past the highest ever issued, counting deprecated ones.
- **A requirement that no longer holds is deprecated in place** — marked dead,
  kept in this file forever, naming the `R{n}` that replaced it. It never leaves
  `PRD.md`. Changing what a requirement *means* is a new `R{n}`, never an edit.

The last two are what keep `history/` forensic. Every citation in the tree
resolves against this file alone, so no agent ever needs an old version to
answer "what is R7?" — which is what makes it safe to tell them not to look.

## Updating the PRD

The PRD is answerable to `../raw/`. When raw data contradicts it:

1. Copy the current `PRD.md` to `history/PRD-{YYYY-MM-DD}.md`, dated the day it
   is superseded, with the header that folder's `AGENTS.md` requires.
2. Write the new `PRD.md`: deprecate what died, issue new `R{n}` for what
   replaced it, and leave untouched everything the raw data did not touch.
3. Propose the downstream delta — which artifacts this invalidates — and get it
   approved before anything downstream moves.

Never edit raw to match the PRD. Raw is the evidence; the PRD is the claim.

## What the PRD owns

The PRD is the source of truth for **intent** — what we are building and why. It
is not the source of truth for behavior (that is `2-specs/`) or for appearance
(that is `3-design/figma/`).

When the PRD and a spec disagree about *what should happen*, the PRD wins and
the spec is stale. When they disagree about *how it works*, the spec is more
specific and the PRD was never meant to say.

Write requirements wide enough to cover the project. This is the one document
that should not need rewriting when a module is added.

## Required sections

These, and nothing else by default:

- **Purpose & scope** — what this product is, and its boundary
- **Goals and non-goals** — non-goals especially; they are what stops scope
  creep three stages downstream
- **Requirements** — numbered `R{n}`, grouped however suits the project
- **Success metrics** — what "working" means at the product level. `6-eval/`
  measures use-cases; these are how you know the use-cases added up to the
  thing you wanted.

## Sections to include only when real

Stakeholders · market assessment and demographics · assumptions · constraints ·
dependencies · technical, usability, environmental, support and interaction
requirements · workflow plans, timelines and milestones · evaluation plan.

Add one when it says something true about *this* project. A heading with nothing
real under it is worse than no heading — it reads as answered. A required
template manufactures exactly that, which is why the list above is a menu and
not a checklist.
