"""Local collaboration bus: seats, tasks, locks, directives, action mutex."""

from pathlib import Path

import pytest

from synapseforge.core.team_bus import TeamBus, open_bus, workspace_db


@pytest.fixture
def bus_env(tmp_path):
    db = tmp_path / "team.db"
    doc = tmp_path / "brief.md"
    doc.write_text("# Brief\nBuild the thing.\n", encoding="utf-8")
    return TeamBus(db), doc, tmp_path


def test_discussion_tasks_and_locks(bus_env):
    store, doc, _ = bus_env
    store.join("demo", "codex", "lead")
    shared = store.share_document("demo", "codex", str(doc))
    assert store.read_document("demo", document_id=shared["id"])["content"] == "# Brief\nBuild the thing.\n"
    msg = store.post_message("demo", "codex", "Please review", "question", "grok")
    visible = store.read_messages("demo", "grok")
    assert visible[-1]["id"] == msg["id"]
    task = store.create_task("demo", "codex", "Edit brief", files=[str(doc)])
    claimed = store.claim_task("demo", "grok", task["id"])
    assert claimed["assignee"] == "grok"
    with pytest.raises(ValueError, match="assigned"):
        store.claim_task("demo", "antigravity", task["id"])
    done = store.update_task("demo", "grok", task["id"], "done", "Reviewed")
    assert done["status"] == "done"
    assert store.status("demo")["file_locks"] == []


def test_duplicate_join_is_observer(tmp_path):
    db = tmp_path / "team.db"
    a = TeamBus(db, session_id="seat-a")
    b = TeamBus(db, session_id="seat-b")
    first = a.join("demo", "grok", "reviewer")
    assert first["already_online"] is False
    second = b.join("demo", "grok", "reviewer")
    assert second["already_online"] is True
    assert second["observer"] is True
    with pytest.raises(ValueError, match="seat occupied"):
        b.post_message("demo", "grok", "I am the duplicate")
    posted = a.post_message("demo", "grok", "occupant can speak")
    assert posted.get("deduplicated") is False


def test_message_dedup_and_human_directive(bus_env):
    store, _, _ = bus_env
    store.join("demo", "human", "user")
    first = store.post_message("demo", "human", "Stop submitting", "directive")
    again = store.post_message("demo", "human", "Stop submitting", "directive")
    assert first["id"] == again["id"]
    assert again["deduplicated"] is True
    assert first["kind"] == "directive"


def test_stale_lock_reclaim_and_action_mutex(tmp_path):
    db = tmp_path / "team.db"
    doc = tmp_path / "brief.md"
    doc.write_text("x", encoding="utf-8")
    holder = TeamBus(db, session_id="codex-1")
    other = TeamBus(db, session_id="grok-1")
    holder.join("demo", "codex", "lead")
    other.join("demo", "grok", "review")
    path = str(doc)
    holder.lock_files("demo", "codex", [path], lock_minutes=30)
    with pytest.raises(ValueError, match="file lock conflict"):
        other.lock_files("demo", "grok", [path])
    with holder.connection() as conn:
        conn.execute(
            "UPDATE participants SET last_seen=? WHERE room=? AND agent=?",
            ("2000-01-01T00:00:00+00:00", "demo", "codex"),
        )
    reclaimed = other.reclaim_stale_locks("demo", "grok")
    assert reclaimed["reclaimed"] == 1
    other.lock_files("demo", "grok", [path])
    claim = other.claim_action("demo", "grok", "submit:v12", ttl_seconds=60)
    assert claim["action_key"] == "submit:v12"
    with pytest.raises(ValueError, match="already claimed"):
        holder.claim_action("demo", "codex", "submit:v12", ttl_seconds=60)


def test_list_rooms_and_offline_status(bus_env):
    store, _, _ = bus_env
    store.join("alpha", "codex")
    rooms = store.list_rooms()["rooms"]
    assert any(r["name"] == "alpha" for r in rooms)
    status = store.status("alpha")
    assert status["participants"][0]["online"] is True
    assert "codex" in status["live_agents"]
    assert status["coordinator_silent"] is False


def test_duplicate_task_same_files_is_reused(bus_env):
    store, doc, _ = bus_env
    store.join("demo", "grok", "review")
    first = store.create_task("demo", "grok", "实现 v16：行为分流", files=[str(doc)])
    assert first.get("deduplicated") is False
    second = store.create_task(
        "demo", "grok", "实现并提交 v16：2000x1 行为特征分流", files=[str(doc)]
    )
    assert second.get("deduplicated") is True
    assert second["id"] == first["id"]
    tasks = store.list_tasks("demo")
    assert len([t for t in tasks if t["status"] != "done"]) == 1


def test_same_files_new_work_after_done(bus_env):
    store, doc, _ = bus_env
    store.join("demo", "antigravity", "impl")
    first = store.create_task("demo", "antigravity", "实现 v16", files=[str(doc)])
    store.claim_task("demo", "antigravity", first["id"])
    store.update_task("demo", "antigravity", first["id"], "done", "shipped")
    nxt = store.create_task("demo", "antigravity", "实现 v17", files=[str(doc)])
    assert nxt.get("deduplicated") is False
    assert nxt["id"] != first["id"]


def test_coordinator_silent_after_heartbeat_expires(bus_env):
    store, _, _ = bus_env
    store.join("demo", "codex", "lead")
    store.join("demo", "grok", "review")
    with store.connection() as conn:
        conn.execute(
            "UPDATE participants SET last_seen=? WHERE room=? AND agent=?",
            ("2000-01-01T00:00:00+00:00", "demo", "codex"),
        )
    status = store.status("demo")
    assert status["coordinator_silent"] is True
    assert "codex" in status["silent_agents"]
    assert "grok" in status["live_agents"]
    waited = store.wait_for_activity("demo", "grok", after_message_id=0, timeout_seconds=0)
    assert waited["coordinator_silent"] is True
    assert "codex" in waited["silent_agents"]


def test_find_live_workspace_room(bus_env):
    store, doc, tmp_path = bus_env
    workspace = str(tmp_path)
    store.join("live-room", "grok", "review", workspace=workspace)
    found = store.find_live_workspace_room(workspace)
    assert found is not None
    assert found["name"] == "live-room"
    assert store.find_live_workspace_room(str(Path(workspace) / "missing")) is None


def test_lock_path_must_stay_in_workspace(bus_env):
    store, doc, tmp_path = bus_env
    store.join("demo", "codex", "lead", workspace=str(tmp_path))
    store.lock_files("demo", "codex", [str(doc)])
    with pytest.raises(ValueError, match="outside the room workspace"):
        store.lock_files("demo", "codex", ["/tmp/synapseforge-not-in-workspace.txt"])


def test_leave_drops_locks_and_marks_offline(bus_env):
    store, doc, tmp_path = bus_env
    store.join("demo", "grok", "review", workspace=str(tmp_path))
    store.lock_files("demo", "grok", [str(doc)])
    left = store.leave("demo", "grok")
    assert left["status"] == "offline"
    assert left["unlocked"] == 1
    status = store.status("demo")
    grok = next(p for p in status["participants"] if p["agent"] == "grok")
    assert grok["status"] == "offline"
    assert status["file_locks"] == []


def test_claim_action_mutex_is_per_agent_not_session(tmp_path):
    db = tmp_path / "team.db"
    a = TeamBus(db, session_id="shared-mcp")
    b = TeamBus(db, session_id="shared-mcp")
    a.join("demo", "antigravity", "impl")
    b.join("demo", "grok", "review")
    claimed = a.claim_action("demo", "antigravity", "push:main", ttl_seconds=60)
    assert claimed["agent"] == "antigravity"
    with pytest.raises(ValueError, match="already claimed"):
        b.claim_action("demo", "grok", "push:main", ttl_seconds=60)
    renewed = a.claim_action("demo", "antigravity", "push:main", ttl_seconds=60)
    assert renewed["agent"] == "antigravity"


def test_open_bus_uses_workspace_db(tmp_path):
    bus = open_bus(workspace=tmp_path)
    expected = workspace_db(tmp_path)
    assert bus.db_path == expected
    bus.join("paper", "human", "author", workspace=str(tmp_path))
    assert expected.exists()
