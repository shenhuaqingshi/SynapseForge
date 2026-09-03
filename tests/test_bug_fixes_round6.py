"""Regression tests for path-safe section ids, lock files, and prompt role ids."""

from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError
from synapseforge.core.section_paths import resolve_section_path
from synapseforge.core.user_prompts import UserPromptManager


def test_resolve_section_path_rejects_traversal(tmp_path):
    outside = tmp_path.parent / f"escaped_{tmp_path.name}.md"
    path = resolve_section_path(tmp_path, f"../escaped_{tmp_path.name}", create_dir=True)
    assert path.parent.resolve() == (tmp_path / "sections").resolve()
    assert path.name == f"escaped_{tmp_path.name}.md"
    assert not outside.exists()


def test_file_lock_stays_inside_locks_dir(tmp_path):
    lock = AutoSectionLock("../outside", "Agent", tmp_path)
    assert lock.lock_file_path.parent == tmp_path / ".synapse" / "locks"
    assert lock.lock_file_path.name == "outside.lock"


def test_write_draft_rejects_path_escape(tmp_path):
    outside = tmp_path.parent / f"draft_escape_{tmp_path.name}.md"
    with AutoSectionLock("sec_01", "Agent", tmp_path) as lock:
        try:
            lock.write_draft("nope", target_file_path=outside)
            escaped = True
        except SectionLockedError:
            escaped = False
    assert escaped is False
    assert not outside.exists()


def test_user_prompt_rejects_path_role_id(tmp_path):
    mgr = UserPromptManager(tmp_path, auto_init_report_spec=False)
    res = mgr.set_prompt("../evil", "should not write")
    assert res.get("ok") is False
    assert not list(tmp_path.glob("evil.md"))
