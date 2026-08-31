import pytest
from pathlib import Path
from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError, SectionLockManager


def test_auto_section_lock_lifecycle(tmp_path):
    sec_id = "sec_04_test"
    agent_a = "Drafter-Narrative"

    # 1. Enter lock context
    with AutoSectionLock(section_id=sec_id, agent_name=agent_a, workspace_root=tmp_path) as lock:
        # Check lock file exists on disk
        lock_mgr = SectionLockManager(workspace_root=tmp_path)
        locked_info = lock_mgr.is_locked(sec_id)
        assert locked_info is not None
        assert locked_info["agent_name"] == agent_a

        # 2. Another agent attempts to modify while locked -> Must fail!
        agent_b = "Critic-Adversarial"
        with pytest.raises(SectionLockedError):
            with AutoSectionLock(section_id=sec_id, agent_name=agent_b, workspace_root=tmp_path):
                pass

        # Perform safe write under lock
        test_file = tmp_path / "sections" / "04_test.md"
        res = lock.write_draft("# Test Draft Content", target_file_path=test_file)
        assert res["ok"] is True
        assert test_file.exists()

    # 3. Exited context -> Lock must be automatically released!
    lock_mgr = SectionLockManager(workspace_root=tmp_path)
    assert lock_mgr.is_locked(sec_id) is None

    # Now agent B can acquire without any error!
    with AutoSectionLock(section_id=sec_id, agent_name=agent_b, workspace_root=tmp_path) as lock_b:
        assert lock_mgr.is_locked(sec_id)["agent_name"] == agent_b


def test_auto_section_lock_release_on_exception(tmp_path):
    sec_id = "sec_02_crash"
    agent = "Drafter-CrashTest"

    # Ensure lock releases even if code crashes with an unhandled exception
    try:
        with AutoSectionLock(section_id=sec_id, agent_name=agent, workspace_root=tmp_path):
            raise RuntimeError("Simulated agent unexpected failure!")
    except RuntimeError:
        pass

    # Verify lock was automatically freed
    lock_mgr = SectionLockManager(workspace_root=tmp_path)
    assert lock_mgr.is_locked(sec_id) is None
