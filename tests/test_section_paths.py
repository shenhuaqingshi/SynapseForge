from synapseforge.core.file_lock import AutoSectionLock
from synapseforge.core.local_agent_cli import LocalAgentCLIManager
from synapseforge.core.section_paths import resolve_section_path


def test_numeric_section_does_not_match_longer_prefix(tmp_path):
    sec = tmp_path / "sections"
    sec.mkdir()
    one = sec / "01_abstract.md"
    ten = sec / "10_conclusion.md"
    one.write_text("# one\n", encoding="utf-8")
    ten.write_text("# ten\n", encoding="utf-8")
    assert resolve_section_path(tmp_path, "1") == one
    assert resolve_section_path(tmp_path, "sec_01") == one
    assert resolve_section_path(tmp_path, "01") == one
    assert resolve_section_path(tmp_path, "10") == ten
    assert resolve_section_path(tmp_path, "sec_10") == ten


def test_exact_stem_wins(tmp_path):
    sec = tmp_path / "sections"
    sec.mkdir()
    target = sec / "04_consensus.md"
    target.write_text("# c\n", encoding="utf-8")
    (sec / "14_appendix.md").write_text("# a\n", encoding="utf-8")
    assert resolve_section_path(tmp_path, "04_consensus") == target
    assert resolve_section_path(tmp_path, "sec_04") == target


def test_local_cli_and_lock_use_exact_section(tmp_path):
    sec = tmp_path / "sections"
    sec.mkdir()
    one = sec / "01_abstract.md"
    ten = sec / "10_conclusion.md"
    one.write_text("# one\n", encoding="utf-8")
    ten.write_text("# ten\n", encoding="utf-8")
    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    assert mgr._resolve_section_file("1") == one
    assert mgr._resolve_section_file("10") == ten
    with AutoSectionLock("1", "Drafter", workspace_root=tmp_path) as lock:
        res = lock.write_draft("# rewritten one\n")
        assert res["ok"] is True
    assert one.read_text(encoding="utf-8") == "# rewritten one\n"
    assert ten.read_text(encoding="utf-8") == "# ten\n"
