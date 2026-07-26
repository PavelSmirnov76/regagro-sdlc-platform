# REGAGRO Livestock — pipeline law

What holds across every stage. Each stage's own `AGENTS.md` adds its naming and
generation rules on top and never restates what is here.

What each stage is *for* is in [`README.md`](README.md). This file is only what
an agent must obey.

## Running a pass

To run one cycle — absorb new data, update the PRD, and fan the change through
specs, design, and tasks — follow the procedure in `RUNBOOK.md`. This file is
the law that holds across every pass; the runbook is the order to apply it in.
Open `RUNBOOK.md` when you start a pass; it is not loaded for you, by design.

## Artifacts are closed for modification, open for extension

A generated artifact is **frozen** the instant it is written. Its content, its
id, and its citations never change. Work that would edit an artifact issues a
new one instead.

The only permitted changes to a frozen file are its **obsolescence header** and
its **location**. Nothing else, ever.

This is what makes the pipeline safe to re-run: apply the law to an unchanged
tree and nothing moves, because nothing is permitted to.

## Ids are permanent

Every id — `R{n}`, `BT-{n}`, `MOD-{n}`, `ACTOR-{n}`, `ENT-{n}`, `EVT-{n}`,
`UC-{n}`, `FIG-{n}`, `TC-{n}` — is allocated once. Never reused, never
renumbered. The next id is one past the highest ever issued, counting obsolete
ones.

Each id belongs to exactly one artifact type. Never name an artifact with
another type's id — every id resolves by glob, so an eval named `UC-12-…` makes
`**/UC-12-*.md` return two files and the resolver ambiguous.

Reissuing an id silently repoints every citation in the tree at the wrong
artifact. Nothing errors. That is why this rule has no exceptions.

## Cite IDs as Markdown links

Every citation must be a Markdown link that includes both:

* the stable artifact ID as the visible link text;
* the relative file path as the link target.

Correct:

```md
[ACTOR-1](../actors/ACTOR-1-FARMER-IN-AUTH.md)
```

Incorrect:

```md
ACTOR-1
```

```md
../actors/ACTOR-1-FARMER-IN-AUTH.md
```

```md
[../actors/ACTOR-1-FARMER-IN-AUTH.md](../actors/ACTOR-1-FARMER-IN-AUTH.md)
```

The visible text must always be the artifact ID because the ID identifies the artifact itself. The path is used only as the Markdown link target so the citation remains clickable.

Filenames begin with their artifact ID, so an artifact can be resolved by glob:

```text
**/ACTOR-1-*.md
```

Paths may change when files are moved or entombed, but the artifact ID must remain unchanged. When a file is moved, update only the Markdown link target; never change the visible artifact ID.


## One artifact per file

One actor per file. One event per file. One requirement per `R{n}`. Never one
file listing many — a file holding two artifacts cannot be frozen, cited, or
entombed independently.

## Traceability runs upstream

Every artifact cites the id(s) it was derived from. Upstream only: an artifact
never lists what was later derived *from* it, because recording that would mean
editing a frozen file every time a descendant appeared.

Supersession is the sole exception, and the only link that runs forward.

## Obsolescence

An artifact that no longer holds is **entombed** — never deleted, never
corrected:

1. Move it to `obsolete/` beside its live siblings.
2. Add a header at the top of the file stating **when**, **why**, and
   **superseded by** which id — or `none` if the concept is dropped outright.
3. The artifact replacing it cites `supersedes: <old-id>`.

Supersession is the only forward link in the pipeline. Without it, the current
definition of a concept becomes unfindable the moment its id changes.

## Staleness is derived, never written

A citation to an entombed id is stale. Record that nowhere — resolve the id and
look at where it lives. `obsolete/` **is** the marker. Writing a staleness flag
into the citing artifact would modify a frozen file for information already
derivable.

A live artifact citing an entombed id is **flagged for review, not
automatically entombed**. Most changes do not invalidate most dependents.
Entombing a whole subgraph because one id moved churns the tree and spends human
review on no-ops. A human decides which dependents actually died.

A frozen filename citing an entombed id is correct and stays. The id records
what the artifact was *derived from* — permanently true. It is provenance, not a
live pointer.

## New artifacts cite live ids only

A frozen artifact keeps its dead citations as history. A new artifact may not
create them: resolve every id you cite and confirm it is not in `obsolete/`
first. Building on an entombed foundation forfeits everything the freeze buys.

## A pass proposes; a human approves

Raw data changes the PRD. The PRD changes what is true downstream. An agent
computes the delta — which artifacts to issue, which to entomb, and the PRD
change driving each — and **presents it for approval before anything moves.**

Gate the plan, not the write. One reviewable decision per pass, not fifty.

## The PRD is a mutable container of frozen requirements

`0-vibes/prd/PRD.md` is the only PRD, and the only file rewritten in place. Its
previous versions go to `0-vibes/prd/history/`.

The requirements inside it are frozen like everything else: `R7`'s text never
changes. A requirement that no longer holds is marked deprecated **in place**,
stays in the current PRD forever, and a new `R{n}` is issued for what replaced
it.

That is what keeps `history/` purely forensic. Every citation in the tree
resolves against the current PRD alone, so no agent ever needs an old version to
answer "what is R7?" — which is what makes it safe to tell them not to look.

## Rules live in exactly one file

Agent rules live in `AGENTS.md`, tool-neutral, so any coding agent finds them —
not one vendor's alone. Each folder's `CLAUDE.md` is a stub importing its
`AGENTS.md` and every ancestor's, up to and including this one, because Claude
Code does not read `AGENTS.md` by default.

Never copy a rule into a `CLAUDE.md`. Never restate an ancestor's rule in a
child. If you are editing a `CLAUDE.md`, you are editing the wrong file.

## Two kinds of folder

- **Structure folders** — the numbered stages and their subfolders. Each carries
  `README.md`, `AGENTS.md`, and a `CLAUDE.md` stub.
- **Content folders** — `obsolete/`, `raw/<date>/`, `6-eval/auto/<date>/…`,
  `6-eval/manual/<date>/…`, and the folder an oversized
  file splits into. These hold data, not rules, and carry no convention files at
  all.

Never scaffold convention files into a content folder.

## Splitting oversized files

Only mutable files grow; frozen artifacts never do. In practice that means the
PRD alone. Past ~300 lines, split it into a folder named for the file without
its extension, keeping the parts addressable: `PRD.md` becomes `PRD/` holding
`PRD.md`, `PRD-Requirements.md`, and so on. Citations are by id, so a split
breaks nothing.

`AGENTS.md` and `README.md` never split — splitting would break the import
chain. One approaching 300 lines means too many rules, or a folder doing too
much. Cut it.

## Do not skip stages

A spec cites a planning task; a design cites a spec. Read a stage's `AGENTS.md`
before generating into it.
