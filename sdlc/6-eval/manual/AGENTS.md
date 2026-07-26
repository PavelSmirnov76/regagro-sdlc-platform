Human execution of the shared test-case fields (see `../AGENTS.md`). One dated
folder per test round, `YYYY-MM-DD`.

## A case is a frozen spec; a run is dated evidence

Keep the two apart, the same way `auto/` does:

- The **test case** is the spec — `TC-{n}`, its objective, preconditions,
  inputs, steps, and expected results. Frozen. It says what to check.
- A **run** is one execution of that case — what a tester actually saw. Dated
  evidence, regenerated, never frozen.

Layout — each case gets its own folder, each run its own folder beneath it:

```
manual/<date>/test_cases/TC-{n}-{TITLE}/
├── TC-{n}-{TITLE}.md              the case, plus this round's verdict
└── runs/
    └── test_run_{type}_{number}/  one execution — {type} is the surface: web, mobile, api
        ├── transcript.md          who ran it, the environment, the step log
        └── screenshots/           time-ordered, one per named step
```

## A run must record

- the use-case exercised, and its positive-path result
- a **transcript**: who executed it — a person, or an agent driving a browser —
  the browser and viewport, the resolved value of every `{placeholder}` the case
  names (`{owner}/{repo}`, `{tester_handle}`, `{number}`), and a step-by-step log
  of observed against expected
- **screenshots** in strict time order, each captured at the step it names, each
  with a one-line commentary stating what it shows and whether it matched

A run may also carry a desired-behaviour description, an acceptance checkbox
list, and — on failure — steps to reproduce.

## Lifecycle stage

Every case names its stage, so its state reads at a glance:

| Stage | Meaning |
|-------|---------|
| `ready for test` | written, not yet run |
| `testing` | in execution |
| `ready for release` | passed |
| `needs to rework` | the **case** is defective, not the system — supersede it (`../AGENTS.md`) |
| `is not actual` | superseded, or the behaviour it checked is gone — entomb it |

`needs to rework` and `is not actual` are where a case leaves the live set: the
first names a false expectation to correct with a new `TC-{n}`, the second is the
entombment that follows. Neither is a `FAIL` against the system.

## Documented to ISO/IEC/IEEE 29119-3

Each case is written to the ISO/IEC/IEEE 29119-3 test case specification so a
tester who has never seen this project can execute it and reach the same verdict.
Verify field names and structure against the standard itself before claiming
conformance — the field set in `../AGENTS.md` is the working set, not a citation
of the clause.

## Written for a stranger

"Log in and check it works" is not a test case: no precondition, no input, no
checkable expected result. If two testers could reasonably reach different
verdicts, the case is underspecified — and the fault is the case, not the tester.

## Record deviations, never silently conform

When a run departs from the case — a capture tool emits `.jpg` where the case
said `.png` — record it as a deviation and state whether it affects any expected
result. A silent conformance hides what actually happened.

## The human records the actual result

Filled at execution from what happened, never before. `BLOCKED` when the case
could not be run — a person's judgment that setup failed is still a recorded
verdict, not a `FAIL`.
