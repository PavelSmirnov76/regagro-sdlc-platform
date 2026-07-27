BUSINESS TASKS naming: `BT-{number}-{type}-{title}.md`

One counter across the whole stage — observation and planning share it, so no
two business tasks ever carry the same number.

`{type}` is what kind of task it is:

| `{type}` | lives in |
|----------|----------|
| `ERROR` · `WARNING` · `INFO` | `observation/` — the severity it was triaged as |
| `PLANNING` | `planning/` |

`{title}` is what it is about. `BT-9-ERROR-CHECKOUT-TIMEOUT.md` is legible from
a listing; `BT-9.md` is not.

## Every business task connects to raw and to the PRD

Cite both:

- the `0-vibes/raw/<date>/` folder holding the real-world data that evidences it
- the PRD requirement(s) (`R{number}`) it serves

Raw is *why we believe it*. The requirement is *what it is for*. A task with
neither is an opinion. A task with raw but no requirement means the PRD is what
changes first — update it, then cite the `R{number}` that comes out.

Work originates here, in two halves that flow one way: signals land in
`observation/`, and `planning/` is shaped from what they surface — never the
reverse.

Do not create tasks at this level. Every task belongs in `observation/` or
`planning/`, and each half states what is specific to it.
