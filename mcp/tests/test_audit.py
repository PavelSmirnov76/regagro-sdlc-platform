from sdlc_mcp.audit import db, ledger


def test_record_and_history_in_memory():
    conn = db.connect(":memory:")
    ledger.start_session(conn, session_id="S-1", human="pavel", title="t")
    cid = ledger.record(
        conn,
        action="create_artifact",
        session_id="S-1",
        actor_human="pavel",
        actor_agent="claude-code",
        artifact_type="BT",
        artifact_id="BT-14",
        path="1-business-tasks/planning/BT-14-X.md",
        summary="new BT",
        new_content="# BT-14\n",
    )
    assert cid == 1
    rows = ledger.history(conn, artifact_id="BT-14")
    assert len(rows) == 1
    r = rows[0]
    assert r["action"] == "create_artifact"
    assert r["new_hash"] and r["prev_hash"] is None
    assert r["actor_human"] == "pavel"


def test_history_filters(tmp_path):
    conn = db.connect(tmp_path / "audit.db")
    ledger.record(conn, action="entomb", artifact_id="MOD-1", artifact_type="MOD")
    ledger.record(conn, action="create_artifact", artifact_id="MOD-3", artifact_type="MOD")
    ledger.record(conn, action="prd_edit", artifact_type="PRD")
    assert len(ledger.history(conn, artifact_type="MOD")) == 2
    assert len(ledger.history(conn, action="entomb")) == 1
    assert len(ledger.history(conn, artifact_id="MOD-3")) == 1
    assert len(ledger.history(conn)) == 3


def test_history_orders_recent_first_and_limits(tmp_path):
    conn = db.connect(tmp_path / "audit.db")
    for i in range(5):
        ledger.record(conn, action="note", summary=f"n{i}")
    rows = ledger.history(conn, limit=2)
    assert len(rows) == 2
    assert rows[0]["summary"] == "n4"  # most recent first


def test_db_parent_dirs_created(tmp_path):
    p = tmp_path / "nested" / "deep" / "audit.db"
    db.connect(p)
    assert p.exists()
