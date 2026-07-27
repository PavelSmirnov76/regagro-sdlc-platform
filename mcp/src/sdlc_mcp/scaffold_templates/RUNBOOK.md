# Running a pass

The pipeline is applied **over and over**, not once. Each application is a
*pass*: new real-world data arrives, the PRD absorbs it, and the change fans out
downstream — specs, design, tasks — touching only what actually changed. This is
the procedure for one pass. The [`AGENTS.md`](AGENTS.md) law says what is always
true; this runbook says in what order to do it.

Two rules govern every step:

- **Diff, don't rewrite.** Every step is *find the difference and create it* —
  never *regenerate everything*. Artifacts are frozen; a change means issuing a
  new one and entombing the old, never editing in place. A pass that touches an
  artifact the new data did not change is doing it wrong. This is what makes the
  pipeline cheap to re-run: over an unchanged tree, a pass does nothing.
- **Propose, then apply.** Work out the whole delta first — what to create, what
  to entomb, and the change driving each — present it, and get a human's approval
  before anything moves. One reviewable decision per pass, not fifty.

The **first** pass is the special case where there is nothing to diff against, so
everything is new: the delta is computed against an empty tree.

---

## 1 — Capture in `0-vibes/`

Start every pass here. Drop the new real-world data into
`0-vibes/raw/<date>/` — logs, reports, research, transcripts, as it arrived,
uninterpreted. Then work the vibe: what does this data mean for the product?

Nothing leaves this stage as a loose vibe. The one exit is the PRD.

## 2 — Regenerate the PRD

The new data updates `0-vibes/prd/PRD.md`. Before rewriting it:

- Copy the current `PRD.md` to `0-vibes/prd/history/PRD-<date>.md`, dated the day
  it is superseded, with a header naming *when*, *why*, and which `raw/` folder
  drove it. The old PRD is **retired, not deleted** — it stays in `history/`
  forever.
- In the new `PRD.md`: deprecate the requirements that no longer hold *in place*
  (they keep their `R{n}` and stay in the file), and issue a new `R{n}` for
  whatever replaced them. Leave every requirement the data did not touch exactly
  as it was.

After this step, `PRD.md` is the single source of truth for intent, and its
`R{n}` list is what the rest of the pass diffs against.

## 3 — Diff business tasks against the new PRD

Go to `1-business-tasks/`. Read the current business tasks, then read the new
`PRD.md`, and find the gap: which requirements are new, which changed, which are
gone.

For each difference, create a business task (`BT-{n}-{type}-{title}`) citing the
`R{n}` it serves and the `raw/` folder behind it. A requirement that *changed*
means the business task serving it is now stale: issue a new `BT` and entomb the
old. **Create only the differences.** A business task whose requirement did not
change is already correct and frozen — leave it.

## 4 — Propagate the diff into `2-specs/`

For each new or superseding business task from step 3, update the specs it
implies — modules first, then actors, entities, events, and use-cases. A changed
use-case is a new `UC-{n}` that supersedes the old; the entombed one's
citations stay as history.

Again, only the specs the diff reaches. The specs for untouched business tasks
do not move.

## 5 — Propagate the diff into `3-design/`

For each changed use-case, update `3-design/` — new or superseding components
(`FIG-{n}`) for the behaviour that changed. Components serving use-cases the
diff never reached stay frozen.

## 6 — Turn the diff into tasks, and hand them to the tracker

Write the implementation work into `4-tasks/`, each task citing the spec and
design ids it implements. Then place the tasks where the team actually works:

- **If a task tracker is wired in** — Jira, YouTrack, Redmine, GitHub Issues,
  via an MCP server or API — create the tasks there, and record the returned
  issue id back in the `4-tasks/` artifact. The link is bidirectional: the
  tracker issue carries the pipeline task id, the pipeline task carries the
  tracker id, and neither can drift from the other.
- **If there is no tracker**, `4-tasks/` *is* the tracker of record.

Creating tracker issues is the one point in a pass that reaches outside the repo,
so it is the natural place for the *propose, then apply* gate to land: approve
the task list before it is pushed.

---

## The pass continues, and the loop closes

From `4-tasks/` the work is built (`5-results/`), evaluated (`6-eval/`),
security-checked (`7-security-check/`), and released (`8-deploy/`) — each stage
diffing only what the pass changed, each artifact frozen on write. Then
`9-observation/` watches it run, and what it surfaces becomes the `raw/` input of
the next pass. The loop turns again from step 1.
