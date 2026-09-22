import json
import time
from pathlib import Path

import pytest

from synapseforge.core.file_lock import (
    AutoSectionLock,
    SectionLockedError,
    SectionLockManager,
    pid_alive,
)


def test_auto_section_lock_lifecycle(tmp_path):
    sec_id = "sec_04_test"
    agent_a = "Drafter-Narrative"
    agent_b = "Critic-Adversarial"

    with AutoSectionLock(section_id=sec_id, agent_name=agent_a, workspace_root=tmp_path) as lock:
        lock_mgr = SectionLockManager(workspace_root=tmp_path)
        locked_info = lock_mgr.is_locked(sec_id)
        assert locked_info is not None
        assert locked_info["agent_name"] == agent_a
        assert locked_info["pid"] > 0

        with pytest.raises(SectionLockedError):
            with AutoSectionLock(section_id=sec_id, agent_name=agent_b, workspace_root=tmp_path):
                pass

        test_file = tmp_path / "sections" / "04_test.md"
        res = lock.write_draft("# Test Draft Content", target_file_path=test_file)
        assert res["ok"] is True
        assert test_file.exists()

    lock_mgr = SectionLockManager(workspace_root=tmp_path)
    assert lock_mgr.is_locked(sec_id) is None

    with AutoSectionLock(section_id=sec_id, agent_name=agent_b, workspace_root=tmp_path) as lock_b:
        assert lock_mgr.is_locked(sec_id)["agent_name"] == agent_b


def test_auto_section_lock_release_on_exception(tmp_path):
    sec_id = "sec_02_crash"
    agent = "Drafter-CrashTest"

    try:
        with AutoSectionLock(section_id=sec_id, agent_name=agent, workspace_root=tmp_path):
            raise RuntimeError("Simulated agent unexpected failure!")
    except RuntimeError:
        pass

    lock_mgr = SectionLockManager(workspace_root=tmp_path)
    assert lock_mgr.is_locked(sec_id) is None


def test_write_draft_requires_held_lock(tmp_path):
    lock = AutoSectionLock("sec_01", "Drafter", workspace_root=tmp_path)
    with pytest.raises(SectionLockedError):
        lock.write_draft("nope")


def test_heartbeat_extends_expiry(tmp_path):
    with AutoSectionLock("sec_hb", "Drafter", workspace_root=tmp_path, timeout_seconds=30) as lock:
        first = lock.heartbeat()
        time.sleep(0.05)
        second = lock.heartbeat()
        assert second["expires_at"] >= first["expires_at"]
        assert second["last_heartbeat"] >= first["last_heartbeat"]


def _write_ghost_lock(tmp_path, section_id="sec_dead"):
    locks_dir = tmp_path / ".synapse" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_file = locks_dir / f"{section_id}.lock"
    lock_file.write_text(
        json.dumps(
            {
                "section_id": section_id,
                "agent_name": "Ghost-Agent",
                "locked_at": time.time(),
                "expires_at": time.time() + 3600,
                "pid": 999999999,
                "platform": "test",
            }
        ),
        encoding="utf-8",
    )
    return lock_file


def test_dead_pid_lock_is_not_active(tmp_path):
    lock_file = _write_ghost_lock(tmp_path, "sec_dead")
    mgr = SectionLockManager(workspace_root=tmp_path)
    assert mgr.is_locked("sec_dead") is None
    assert not lock_file.exists()


def test_reclaim_stale_drops_dead_pid_locks(tmp_path):
    lock_file = _write_ghost_lock(tmp_path, "sec_ghost")
    mgr = SectionLockManager(workspace_root=tmp_path)
    result = mgr.reclaim_stale()
    assert result["reclaimed"] >= 1
    assert not lock_file.exists()


def test_pid_alive_current_process():
    assert pid_alive(0) is None
    assert pid_alive(-1) is None
    assert pid_alive(__import__("os").getpid()) is True
