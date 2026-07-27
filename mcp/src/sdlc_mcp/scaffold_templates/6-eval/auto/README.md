# Auto — machine-run evaluation

Everything a machine can judge without a human watching. One dated folder per
run.

A run leaves this folder when its verdicts reach `../DASHBOARD.md`.

## Structure

```
auto/2026-07-16/unit/
auto/2026-07-16/integration/
auto/2026-07-16/llm/
```

- `unit/` — single units in isolation.
- `integration/` — units together across a real boundary: API, database, queue.
- `llm/` — behaviour only a model can judge: tone, prose correctness, whether
  output satisfies an intent no matcher can express.

Past runs are never overwritten. That history is what makes a regression
visible.

Rules, and what each run folder must contain, are in [`AGENTS.md`](AGENTS.md).
