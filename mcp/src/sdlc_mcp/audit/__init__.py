"""The audit ledger — a separate SQLite database recording every mutation.

Every change the service makes to the ``sdlc/`` tree writes one row to
``changes``: who (human + agent), what (action, artifact id/type/path), when,
and a content hash before/after. ``sdlc-audit history`` queries it.
"""
