"""sdlc-mcp — an MCP server that guards the SDLC law and audits every change.

The package is layered:

* ``law/``        — pure functions implementing the SDLC pipeline law
                    (frozen artifacts, entombment, PRD-in-place, permanent ids).
* ``audit/``      — the SQLite change ledger ("who changed what, when").
* ``transcript/`` — append-only per-session JSONL logs.
* ``integrations/`` — git / APK build / Telegram (interfaces + fakes now).
* ``service.py``  — the application service that composes law + audit +
                    transcript; every mutation goes through it.
* ``server.py``   — the FastMCP server exposing the service as MCP tools.
"""

__version__ = "0.1.0"
