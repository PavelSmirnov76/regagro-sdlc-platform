"""``sdlc-audit`` — a convenient command to read the change history.

Examples::

    sdlc-audit history --artifact BT-14
    sdlc-audit history --type MOD --limit 20
    sdlc-audit history --session S-20260726-101500-ab12
"""

from __future__ import annotations

import argparse
import sqlite3

from ..config import load_config
from . import db, ledger


def _fmt_row(r: sqlite3.Row) -> str:
    return (
        f"[{r['id']:>4}] {r['ts']}  {r['action']:<18} "
        f"{(r['artifact_id'] or '-'):<10} {(r['actor_human'] or '-'):<12} "
        f"{r['summary'] or ''}"
    )


def cmd_history(args: argparse.Namespace) -> int:
    cfg = load_config()
    conn = db.connect(args.db or cfg.audit_db)
    rows = ledger.history(
        conn,
        artifact_id=args.artifact,
        artifact_type=args.type,
        session_id=args.session,
        action=args.action,
        since=args.since,
        until=args.until,
        limit=args.limit,
    )
    if not rows:
        print("(no changes recorded)")
        return 0
    for r in reversed(rows):  # print chronologically
        print(_fmt_row(r))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdlc-audit", description="Query the SDLC change ledger."
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("history", help="show change history")
    h.add_argument("--artifact", help="filter by artifact id, e.g. BT-14")
    h.add_argument("--type", help="filter by artifact type, e.g. MOD")
    h.add_argument("--session", help="filter by session id")
    h.add_argument("--action", help="filter by action, e.g. entomb")
    h.add_argument("--since", help="ISO timestamp lower bound")
    h.add_argument("--until", help="ISO timestamp upper bound")
    h.add_argument("--limit", type=int, default=100)
    h.add_argument("--db", help="path to the audit db (defaults to configured)")
    h.set_defaults(func=cmd_history)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
