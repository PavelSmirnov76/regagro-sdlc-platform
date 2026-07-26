# 6 — Eval

Evaluation of the results (`../5-results/`) against the use-cases
(`../2-specs/use-cases/`). Did what we built do what it was supposed to? The
**quality gate**.

An item passes this stage when every use-case serving its requirement has a
passing verdict on `DASHBOARD.md`, and moves on to `../7-security-check/`.

## Why use-cases, not requirements

A use-case is the only spec you can actually run: actor, trigger, entity,
outcome — that is a test. Actors, entities, and events are definitions.
Requirements are intent, satisfied only through the use-cases that realize them.
So evaluation happens at the use-case level, and the dashboard rolls it up to
the requirement.

## Structure

```
6-eval/
├── auto/<date>/{unit,integration,llm}/   machine-run evidence
├── manual/<date>/test_cases/             human-run test cases, ISO 29119-3
└── DASHBOARD.md                          the roll-up: is R7 satisfied?
```

One dated folder per run, `YYYY-MM-DD`. Past runs are never overwritten — that
history is what makes a regression visible rather than silently replaced.

## The dashboard is the answer to "are we done?"

`DASHBOARD.md` states, per requirement, every use-case serving it and that
use-case's latest verdict. It is the only place that question is answerable by
looking; the trace from a requirement down to its use-cases otherwise runs
through business tasks and specs.

A requirement with no test cases is **untested**, not passing. The dashboard
says so explicitly — a green that means "we never looked" is worse than no
dashboard at all.

## Every file carries a test-case table

Any file here opens with a table of the test cases it covers, each row citing
the use-case id it exercises. Open any file and the mapping is right there.

Naming, verdicts, and the rules for evidence are in [`AGENTS.md`](AGENTS.md).
