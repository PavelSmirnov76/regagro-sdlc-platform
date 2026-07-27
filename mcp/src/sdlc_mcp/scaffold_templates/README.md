# {{PROJECT_NAME}}

Work flows through ten numbered stages, from raw idea to running system and back
again. This README orients a human arriving cold. The rules agents must obey are
in [`AGENTS.md`](AGENTS.md); the step-by-step for running one cycle is in
[`RUNBOOK.md`](RUNBOOK.md).

## The pipeline

```
0-vibes/ → 1-business-tasks/ → 2-specs/ → 3-design/ → 4-tasks/
 idea/prd    observe & plan      specs      design    implementation
                                                           │
   ┌───────────────────────────────────────────────────────┘
   ▼
5-results/ → 6-eval/ → 7-security-check/ → 8-deploy/ → 9-observation/
  built       quality      security         release      watch → (loops back to 1)
```

It is a **loop**, not a line: `9-observation/` feeds signals back into
`1-business-tasks/observation/` to start the next cycle. Stages are never
skipped — a spec references a planning task, a design references a spec — so
every artifact traces upstream to the need that produced it.

## How the pipeline changes over time

The pipeline is applied over and over, not once. New real-world data lands in
`0-vibes/raw/<date>/`, the PRD absorbs it, and everything downstream adjusts.
Three properties make that safe to repeat:

- **Artifacts are frozen.** Once written, an artifact's content, id, and
  citations never change. Change means issuing a new artifact, not editing an
  old one — so re-running the pipeline over an unchanged tree does nothing.
- **Obsolete artifacts are entombed, not deleted.** They move to `obsolete/`
  with a header saying when they died, why, and what superseded them. The
  history stays readable and the audit trail stays whole.
- **A human approves each pass.** An agent proposes the delta — what to issue,
  what to entomb, and the PRD change driving it — and nothing moves until that
  plan is approved.

The full rules are in [`AGENTS.md`](AGENTS.md).

## The stages

### 0 — Vibes (`0-vibes/`)

The earliest, pre-planning stage: raw ideas, inspiration, and loose direction —
the **vibe**, before anything is structured.

- `0-vibes/raw/` — real-world data as it arrives, in dated folders. The
  unprocessed input the PRD is answerable to.
- `0-vibes/prd/` — the single Product Requirements Document: the first
  structured artifact, turning vibes and raw data into stated product intent.
  Previous versions live in `0-vibes/prd/history/`.

### 1 — Business tasks (`1-business-tasks/`)

Where work originates: **observation and planning**. Business needs, research,
stakeholder input, opportunities, and high-level plans. The "why" — problems
worth solving, before they are broken into concrete work.

- `1-business-tasks/observation/` — signals from the running system, users, and
  ops, triaged by severity: `errors/`, `warnings/`, `infos/`.
- `1-business-tasks/planning/` — plans, roadmaps, and priorities shaped from
  what observation surfaces.

### 2 — Specs (`2-specs/`)

Detailed **specifications** expanding planning tasks into concrete requirements:
behavior, data, edge cases, contracts, acceptance tests. The "how it should
work" — what an implementation is validated against.

- `2-specs/modules/` — functional units composing actors, entities, and events
  into behavior. Defined first; every other spec id names its module.
- `2-specs/actors/` — who or what interacts with the system.
- `2-specs/entities/` — domain objects and their data.
- `2-specs/events/` — things that happen: triggers, transitions, side effects.
- `2-specs/use-cases/` — end-to-end scenarios tying an actor + event + entity to
  a result.

### 3 — Design (`3-design/`)

**Design components** produced from specs, organized by target.

- `3-design/figma/` — the Figma file, design origin and source of truth for
  appearance.
- `3-design/react/` and `3-design/vue/` — component implementations.

Every component ships a Storybook story covering all of its internal states.

### 4 — Tasks (`4-tasks/`)

Concrete **implementation tasks** derived from specs and designs. Where
validated design becomes engineering work ready to build.

### 5 — Results (`5-results/`)

The **output of implementation**: what was actually built, each traceable back
to the task that produced it, and each honest about what was deferred.

### 6 — Eval (`6-eval/`)

**Evaluation** of results against specs — the quality gate. Test results,
acceptance checks, verdicts.

### 7 — Security check (`7-security-check/`)

**Security review** before shipping — the security gate. Vulnerabilities,
secrets, dependency risk, access concerns caught here rather than in production.

### 8 — Deploy (`8-deploy/`)

**Release** of security-cleared results. Deployment configs, release notes,
rollout and rollback plans.

### 9 — Observation (`9-observation/`)

**Watching the deployed system**, triaged by severity (`errors/`, `warnings/`,
`infos/`). Closes the loop: signals feed back into
`1-business-tasks/observation/` and the next cycle begins.

## Two files govern every folder

- **`README.md`** — for humans. Purpose, structure, and the one condition an
  item must meet to leave.
- **`AGENTS.md`** — for agents. The hard rules: ID schemes, required sets,
  generation instructions.

A `CLAUDE.md` stub sits beside them importing the `AGENTS.md` chain, because
Claude Code does not read `AGENTS.md` by default. It holds nothing else. **Every
rule lives in exactly one file** — if you find yourself editing a `CLAUDE.md`,
you are editing the wrong file.
