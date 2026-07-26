Evaluate `5-results/` against the **use-cases** in `2-specs/use-cases/` — never
against requirements directly, and never against the implementation's own
assumptions.

A use-case is the only spec that is executable: it names an actor, a trigger, an
entity, and an outcome, which is a test. Actors, entities, and events are
definitions — there is nothing to run. A requirement is intent, and is satisfied
only through the use-cases that realize it.

## Structure

```
6-eval/
├── auto/<date>/{unit,integration,llm}/   machine-run test cases
├── manual/<date>/test_cases/             human-run test cases
└── DASHBOARD.md                          the roll-up
```

`<date>` is `YYYY-MM-DD`, one folder per run, so lexical order is chronological.

Everything below `auto/` and `manual/` is a **content folder** — no `README.md`,
`AGENTS.md`, or `CLAUDE.md` inside a dated folder or a type folder. The rules for
`unit/`, `integration/`, `llm/`, and `test_cases/` live in `auto/AGENTS.md` and
`manual/AGENTS.md`.

## A test case has one set of fields — auto and manual are the same animal

Auto and manual are two ways to *execute* one test-case concept, not two
concepts. Every test case, run by a machine or a human, records the same fields
(aligned to ISO/IEC/IEEE 29119-3):

| Field | Meaning |
|-------|---------|
| **identifier** | `TC-{number}` — permanent, never reused |
| **objective** | what this case establishes |
| **use-case** | the `UC-{number}` it exercises — cite by id, never by path |
| **priority** | how much a failure here matters |
| **preconditions** | the state the system must be in before the first step |
| **inputs & steps** | numbered, each unambiguous and independently checkable |
| **expected result** | what a pass looks like, per step where it matters |
| **actual result** | recorded **at execution**, from what happened — never predicted |
| **verdict** | `PASS` · `FAIL` · `BLOCKED` |

`auto/` records these as machine-readable `record.json`; `manual/` records them
as documented cases a person executes. Same fields, different executor — which
is the whole reason their metrics roll up together on one dashboard.

A row with no `use-case` proves nothing: it is an assertion about the system that
nothing in the pipeline asked for. `actual result` written before the run is not
evidence of anything.

`BLOCKED` is a real verdict and is **not** `FAIL` — a test that could not run has
told you nothing about the system, and collapsing it into `FAIL` invents
evidence. It is neither a pass nor a failure on the dashboard; it is its own
column. A `BLOCKED` record must state **what would unblock it** — "not
authenticated: sign in to the Chrome on 127.0.0.1:9222", not just "blocked."

## An expected result is a claim about the *system* — ground it, never assume it

A verdict is only as good as the expected result it checks against. Write every
expected result from behaviour you have **observed or documented**, never from
how you assume the system works. An assumed expectation turns a healthy system
into a `FAIL`: a case that asserts "the submit button is disabled until a title
is entered" fails a form that enables the button from render and enforces the
title on submit — the defect is in the case, not the system. Contrast an
expectation that anticipated real behaviour — "the URL carries an integer",
which held even though the first issue was numbered `#2` — and passed.

## When the case is wrong, not the system

`FAIL` means the **system** did not do what a sound case expected. It does not
mean the case's expectation was wrong — there is deliberately no verdict for
that, because a defective case is not evidence about the system at all.

When a run reveals a false expectation, do not leave a misleading `FAIL`
standing, and do not edit the case — it is frozen. **Supersede it**: issue a new
`TC-{n}` that reproduces it with the expectation corrected (its record carries a
`reproduces` field naming the old id), and **entomb the defective case** in
`obsolete/` with a tombstone saying which expectation was false and which `TC`
replaced it.

The dashboard rolls up **live cases only**. An entombed case never counts, so a
corrected expectation stops dragging its use-case red the instant its case is
entombed — which is the whole reason a wrong case is superseded rather than left
to sit at `FAIL`.

## Every file opens with its test-case table

Any file in this stage — auto or manual, evidence or verdict — opens with a
table of the cases it covers, columns drawn from the fields above, each row
citing its `use-case` id. Open any file and the mapping is right there.

## The dashboard

`DASHBOARD.md` is the roll-up, and the only place "is `R7` satisfied?" is
answerable by looking. The trace from a requirement to its use-cases otherwise
runs through business tasks and specs — two hops, both by search.

Because auto and manual share the field set, the dashboard sums them directly:
per requirement, every use-case serving it, its latest **live** verdict, and the
run — auto or manual, with its date — that produced it. Entombed cases are
excluded. No translation between two metric systems, because there is only one.

A requirement with no test cases is **untested**, which is not the same as
passing. Say so on its row. A dashboard that renders "no results" as green is
worse than no dashboard.

Regenerate the dashboard on every run. It is a **view**, not a frozen artifact —
overwritten each time, the freeze does not apply. The durable records are the
dated run folders it reads.
