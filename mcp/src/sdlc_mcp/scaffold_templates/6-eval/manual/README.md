# Manual — human-run evaluation

What a person has to judge. One dated folder per test round, each holding its
test cases.

A round leaves this folder when its verdicts reach `../DASHBOARD.md`.

## Structure

```
manual/2026-07-16/test_cases/
```

## Test cases are written for a stranger

Each is documented to the ISO/IEC/IEEE 29119-3 test case specification —
identifier, objective, the use-case it exercises, priority, preconditions,
inputs and steps, expected result, actual result, verdict.

The bar: a tester who has never seen this project can execute the case and reach
the same verdict. If two testers could reasonably disagree, the case is
underspecified — and that is the case's fault, not the tester's.

Rules in [`AGENTS.md`](AGENTS.md).
