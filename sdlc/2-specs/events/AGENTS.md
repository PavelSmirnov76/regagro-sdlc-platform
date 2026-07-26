EVENTS naming: `EVT-{number}-{NAME}-IN-{MODULE}`

Name the entity the event acts on, its trigger, and the state transition or side
effect it causes.

Cite the entity id the event acts on.

## An event is a fact, not a command — and outcome is not part of it

Name what happened, past tense (`FARM-CREATED`, not `CREATE-FARM`). An event
is true regardless of how the attempt it describes turns out.

**One fact, one `EVT`, never split by outcome.** Success, network error, and a
deliberate server rejection of the same attempt are not three events — they
are the same event cited by three different use-cases, differing only in
`RESULT` (`_OK` / `_ERROR` / `_REJECTED`, see `../use-cases/AGENTS.md`).
Splitting by outcome at the event level (`…-SUCCEEDED` / `…-FAILED`) just
re-encodes what `RESULT` already carries, one layer up, and the two copies
will drift. The rare exception is when the attempt and its outcome are
independently meaningful as separate facts on their own terms (e.g. an
attempt counted toward rate-limiting regardless of outcome) — decide that per
case, not by default.

**Exactly one initiator per event.** The actor who causes an event is part of
its definition, not incidental. If the same underlying fact can be caused by
two different actors — a human doing it directly, versus a system replaying
it during a sync pass — that is **two events**, not one event cited by
use-cases with different actors. A sync-triggered push of a locally-created
record is its own event (its own trigger condition: the sync pass reaching
that step), even when it exists to complete something a human event started.
Cite the earlier event as what this one completes; do not merge into it.
