# PRD — Product Requirements Document

The first structured artifact: turns raw vibes and real-world data into stated
product intent. It captures **what** we're building and **why**, at a product
level, before any of it is decomposed into business tasks in
`../../1-business-tasks/`.

`PRD.md` is the only PRD, and the only file in the pipeline rewritten rather
than superseded. Everything downstream is frozen — this is where change enters
and fans out.

An item leaves this stage when a requirement is numbered in `PRD.md` and a
planning task in `../../1-business-tasks/planning/` cites it.

## Structure

- `PRD.md` — the current PRD. The only one.
- `history/` — superseded versions, each naming the raw data that retired it.
  Forensic only: nothing there is needed to read the current PRD, because
  deprecated requirements stay in `PRD.md` forever.

## Why the requirements carry the weight

Every artifact in this pipeline traces upstream to an `R{n}` in this file.
Planning tasks cite them, specs expand them, eval validates against them. The
prose orients a human; the numbered requirements are what the rest of the tree
is actually built on — which is why they, and not the prose, carry the strictest
rules in the pipeline.

What a requirement must be, and how the PRD is updated when raw data contradicts
it, are in [`AGENTS.md`](AGENTS.md).
