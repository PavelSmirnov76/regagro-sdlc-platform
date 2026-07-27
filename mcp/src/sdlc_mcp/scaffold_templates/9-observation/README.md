# 9 — Observation

Watching the deployed system (`../8-deploy/`) in production. This **closes the
loop**: signals gathered here feed back into `../1-business-tasks/observation/`,
where they become the next round of planning and work.

Like stage 1's observation, signals are triaged by severity.

## Structure
- `errors/` — production failures and incidents that demand action.
- `warnings/` — risks and degradations worth attention before they become errors.
- `infos/` — neutral signals, metrics, and usage notes.

```
8-deploy/ → 9-observation/ → 1-business-tasks/observation/ → …
                            (loop back into planning)
```
