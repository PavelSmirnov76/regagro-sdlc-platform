from sdlc_mcp.transcript.session import SessionLog, new_session_id


def test_session_id_format():
    sid = new_session_id()
    assert sid.startswith("S-")
    assert len(sid.split("-")) >= 3


def test_append_and_read(tmp_path):
    log = SessionLog(tmp_path, "S-test")
    log.append("human_request", text="add QR scan")
    log.append("tool_call", tool="business_task_create", args={"name": "BOARD"})
    events = log.read()
    assert [e["kind"] for e in events] == ["human_request", "tool_call"]
    assert events[0]["text"] == "add QR scan"
    assert events[1]["args"]["name"] == "BOARD"
    assert (tmp_path / "S-test.jsonl").exists()


def test_read_empty_session(tmp_path):
    assert SessionLog(tmp_path, "S-none").read() == []
