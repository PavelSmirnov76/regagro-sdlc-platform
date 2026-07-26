ENTITIES naming: `ENT-{number}-{NAME}-IN-{MODULE}`

Specify fields, types, relationships, and invariants.

Cite in full the ids of other entities this one connects to.

## Cite real source, verified by reading

Every entity names the code it comes from: a table — File | Symbol | Status
(`CURRENT`/`TARGET`) | Role — one row per element mentioned, not one row for
"the whole feature." Verify every path by reading the file (grep/Read)
immediately before writing it down. Never restore a path from memory, and
never copy one out of another doc without checking it still resolves.

## Cite the symbol, never the line

A source-code reference names *what* — file and symbol (`ClassName.methodName`
if the bare name is ambiguous) — never *where*. Never append a line number or
line range. A symbol survives a refactor; a line number does not, and citing
one turns every unrelated edit earlier in the same file into a silent stale
citation nobody can detect without re-reading the whole file. This applies to
every source-code table in `2-specs/` — entities, modules, and a use-case's
`Технические зависимости` alike.
