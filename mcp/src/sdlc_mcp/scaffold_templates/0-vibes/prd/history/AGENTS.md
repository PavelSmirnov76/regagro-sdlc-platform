# PRD history — retired PRD versions

**Do not read anything here unless a task explicitly requires PRD history.**
Every citation in the tree resolves against the current PRD, including
deprecated requirements, which stay in it forever. Nothing here is needed to
answer "what is R7?" — reading it only spends context.

Read it only to answer why the PRD changed.

## Naming

```
PRD-{YYYY-MM-DD}.md
```

The date the version was **superseded**, not the date it was authored — so it
pairs with the raw folder that retired it.

## Every retired PRD carries a header

At the top of the file, before its original content:

- **superseded**: the date it stopped being current
- **why**: what changed, in one line
- **raw**: the dated `raw/` folder holding the data that obsoleted it

The header is the only permitted addition. The PRD's original content below it
is frozen — never corrected, never tidied.
