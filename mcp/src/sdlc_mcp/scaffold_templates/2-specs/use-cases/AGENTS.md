USE-CASES naming:
`UC-{number}-ACTOR-{number}-EVT-{number}-ENT-{number}-{RESULT}-IN-{MODULE}`

The filename carries the derivation: primary actor, trigger event, primary
entity, outcome. A directory listing alone tells you who did what to which
entity, and how it ended.

Every id named in the filename must already exist — a use-case cannot invent its
actor, event, or entity, and must resolve each to a live artifact before citing
it.

The ids in the filename record what this use-case was **derived from**. They are
frozen with the name. If one of them is later entombed, this filename stays as
written: it is provenance, not a live pointer.
